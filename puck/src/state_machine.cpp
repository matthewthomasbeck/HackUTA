#include "state_machine.hpp"

#include <chrono>
#include <iostream>
#include <thread>

namespace calypso {

StateMachine::StateMachine(Capture& capture, BackendLink& link, Models& models,
                           PhoneLink& phone, int offline_segment_ms,
                           SegmentSpool& spool, const ClockSource& clock,
                           int segment_ms)
    : capture_(capture),
      link_(link),
      models_(models),
      phone_(phone),
      spool_(spool),
      segmenter_(segment_ms, clock),
      offline_buf_(offline_segment_ms),
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
    // Drop partial offline concat so reconnect doesn't leak into the next clip.
    if (mode == RunMode::Online) {
      offline_buf_.clear();
    }
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
    // Every chunk is spooled in both modes; the Uploader drains the spool.
    spool_chunk(*chunk);
    if (mode_.load() == RunMode::Offline) {
      process_offline(*chunk);
    }
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

void StateMachine::process_offline(const AudioChunk& chunk) {
  // Keep CHUNK_MS frames from capture; OfflineBuffer builds a longer clip.
  auto clip = offline_buf_.push(chunk);
  if (!clip) {
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
                << " (score=" << out.who.score << ")\n";
      break;
    case WhoIsTalking::Status::Uncertain:
      std::cerr << "who is talking: uncertain (best_score=" << out.who.score
                << ")\n";
      break;
    case WhoIsTalking::Status::Unknown:
      std::cerr << "who is talking: unknown (no gallery / no embedding)\n";
      break;
  }

  // Phone path still stubbed — print is enough for offline MVP.
  (void)phone_.send_who_is_talking(out.who);
}

}  // namespace calypso
