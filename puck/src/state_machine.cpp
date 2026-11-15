#include "state_machine.hpp"

#include <chrono>
#include <cmath>
#include <iostream>
#include <thread>

namespace calypso {
namespace {

// Mean absolute amplitude in [0, 1]. Cheap speech/silence gate.
float clip_rms(const AudioChunk& clip) {
  if (clip.pcm.empty()) {
    return 0.f;
  }
  double sum = 0.0;
  for (std::int16_t s : clip.pcm) {
    sum += std::fabs(static_cast<double>(s) / 32768.0);
  }
  return static_cast<float>(sum / static_cast<double>(clip.pcm.size()));
}

}  // namespace

StateMachine::StateMachine(Capture& capture, BackendLink& link, Models& models,
                           PhoneLink& phone, int offline_segment_ms,
                           SegmentSpool& spool, const ClockSource& clock,
                           int segment_ms, float min_speech_rms)
    : capture_(capture),
      link_(link),
      models_(models),
      phone_(phone),
      spool_(spool),
      segmenter_(segment_ms, clock),
      offline_buf_(offline_segment_ms),
      min_speech_rms_(min_speech_rms > 0.f ? min_speech_rms : 0.02f),
      queue_(/*max_chunks=*/200) {}

StateMachine::~StateMachine() {
  stop();
}

void StateMachine::start(RunMode initial) {
  mode_.store(initial);
  stop_.store(false);
  queue_.reopen();
  if (listen_thread_.joinable() || worker_thread_.joinable()) {
    return;
  }
  listen_thread_ = std::thread([this] { listen_loop(); });
  worker_thread_ = std::thread([this] { worker_loop(); });
  std::cerr << "state_machine: listen + worker threads started ("
            << (initial == RunMode::Online ? "ONLINE" : "OFFLINE") << ")\n";
}

void StateMachine::stop() {
  stop_.store(true);
  queue_.close();
  if (listen_thread_.joinable()) {
    listen_thread_.join();
  }
  if (worker_thread_.joinable()) {
    worker_thread_.join();
  }
}

void StateMachine::set_mode(RunMode mode) {
  const auto prev = mode_.exchange(mode);
  if (prev != mode) {
    // Voice ID runs in both modes, so the worker-owned OfflineBuffer is not
    // touched here (clearing it from this thread would race the worker).
    std::cerr << "state_machine: mode → "
              << (mode == RunMode::Online ? "ONLINE" : "OFFLINE") << "\n";
  }
}

RunMode StateMachine::mode() const {
  return mode_.load();
}

void StateMachine::listen_loop() {
  while (!stop_.load()) {
    AudioChunk chunk;
    if (!capture_.read_chunk(chunk)) {
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
      continue;
    }
    queue_.push(std::move(chunk));
  }
}

void StateMachine::worker_loop() {
  while (!stop_.load()) {
    auto chunk = queue_.pop_wait([this] { return stop_.load(); });
    if (!chunk) {
      if (stop_.load()) {
        break;
      }
      continue;
    }
    // Every chunk is spooled and run through voice ID in both modes: the
    // Uploader drains the spool, and the phone's "talking with" card needs
    // who-is-talking whether or not the backend is reachable.
    spool_chunk(*chunk);
    process_who(*chunk);
  }
}

void StateMachine::spool_chunk(const AudioChunk& chunk) {
  auto seg = segmenter_.push(chunk);
  if (!seg) {
    return;
  }
  try {
    spool_.enqueue(seg->first, seg->second);
  } catch (const std::exception& e) {
    std::cerr << "state_machine: spool enqueue failed: " << e.what() << "\n";
  }
}

void StateMachine::process_who(const AudioChunk& chunk) {
  // Keep CHUNK_MS frames from capture; OfflineBuffer builds a longer clip.
  auto clip = offline_buf_.push(chunk);
  if (!clip) {
    return;
  }

  // Skip silence / noise — those embeddings look like "uncertain strangers".
  const float rms = clip_rms(*clip);
  if (rms < min_speech_rms_) {
    std::cerr << "who is talking: (skip quiet clip rms=" << rms << ")\n";
    return;
  }

  ModelOutput out;
  if (!models_.infer(*clip, out)) {
    return;
  }

  // MVP: journalctl sees stderr from the systemd unit.
  switch (out.who.status) {
    case WhoIsTalking::Status::Identified:
      std::cerr << "who is talking: " << out.who.display_name
                << " (score=" << out.who.score << " rms=" << rms << ")\n";
      break;
    case WhoIsTalking::Status::Uncertain:
      std::cerr << "who is talking: uncertain (best_score=" << out.who.score
                << " rms=" << rms << ")\n";
      break;
    case WhoIsTalking::Status::Unknown:
      std::cerr << "who is talking: unknown (no gallery / no embedding)\n";
      break;
  }

  // PhoneLink writes the drop file; the BLE sidecar notifies the phone.
  (void)phone_.send_who_is_talking(out.who);
}

}  // namespace calypso
