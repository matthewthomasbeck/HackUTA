#include "state_machine.hpp"

#include <chrono>
#include <iostream>
#include <thread>

namespace calypso {

StateMachine::StateMachine(Capture& capture, BackendLink& link, Models& models,
                           PhoneLink& phone, int offline_segment_ms)
    : capture_(capture),
      link_(link),
      models_(models),
      phone_(phone),
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
    if (mode_.load() == RunMode::Online) {
      process_online(*chunk);
    } else {
      process_offline(*chunk);
    }
  }
}

void StateMachine::process_online(const AudioChunk& chunk) {
  if (!link_.send_audio_chunk(chunk)) {
    // Listener flips to Offline / reconnects; capture keeps filling the queue.
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

  // Deliver "who is talking" to the phone over Bluetooth (stub).
  (void)phone_.send_who_is_talking(out.who);
}

}  // namespace calypso
