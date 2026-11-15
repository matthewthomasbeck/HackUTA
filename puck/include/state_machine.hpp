#pragma once

#include "backend_link.hpp"
#include "capture.hpp"
#include "models.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// THREAD 2 — single owner of the mic. Dispatches Online vs Offline.
// (Two concurrent mic readers would fight ALSA; modes share this thread.)
class StateMachine {
 public:
  StateMachine(Capture& capture, BackendLink& link, Models& models);
  ~StateMachine();

  StateMachine(const StateMachine&) = delete;
  StateMachine& operator=(const StateMachine&) = delete;

  void start(RunMode initial);
  void stop();

  void set_mode(RunMode mode);
  RunMode mode() const;

 private:
  void run();
  void run_online_tick();   // collect chunk → send to backend
  void run_offline_tick();  // collect chunk → local models → discard output

  Capture& capture_;
  BackendLink& link_;
  Models& models_;
  std::atomic<RunMode> mode_{RunMode::Offline};
  std::atomic<bool> stop_{false};
  std::thread thread_;
};

}  // namespace calypso
