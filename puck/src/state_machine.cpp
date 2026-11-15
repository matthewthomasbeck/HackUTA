#include "state_machine.hpp"

#include <chrono>
#include <thread>

namespace calypso {

StateMachine::StateMachine(Capture& capture, BackendLink& link, Models& models)
    : capture_(capture), link_(link), models_(models) {}

StateMachine::~StateMachine() {
  stop();
}

void StateMachine::start(RunMode initial) {
  mode_.store(initial);
  stop_.store(false);
  if (thread_.joinable()) {
    return;
  }
  thread_ = std::thread([this] { run(); });
}

void StateMachine::stop() {
  stop_.store(true);
  if (thread_.joinable()) {
    thread_.join();
  }
}

void StateMachine::set_mode(RunMode mode) {
  mode_.store(mode);
}

RunMode StateMachine::mode() const {
  return mode_.load();
}

void StateMachine::run() {
  while (!stop_.load()) {
    if (mode_.load() == RunMode::Online) {
      run_online_tick();
    } else {
      run_offline_tick();
    }
  }
}

void StateMachine::run_online_tick() {
  AudioChunk chunk;
  if (!capture_.read_chunk(chunk)) {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    return;
  }
  if (!link_.send_audio_chunk(chunk)) {
    // Listener will flip mode; keep looping.
  }
}

void StateMachine::run_offline_tick() {
  AudioChunk chunk;
  if (!capture_.read_chunk(chunk)) {
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    return;
  }
  ModelOutput out;
  if (models_.infer(chunk, out)) {
    // Offline brainstorm: intentionally do nothing with `out` for now.
    (void)out;
  }
}

}  // namespace calypso
