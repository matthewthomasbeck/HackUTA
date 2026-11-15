#pragma once

#include "backend_link.hpp"
#include "state_machine.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// THREAD 1 — watches BackendLink (HTTP); flips StateMachine to Offline on drop,
// keeps retrying connect every retry_sec.
// When force_offline_ is true (MODE=offline), pins Offline and never promotes.
class ConnectionListener {
 public:
  ConnectionListener(BackendLink& link, StateMachine& sm, int retry_sec,
                     int check_sec, bool force_offline = false);
  ~ConnectionListener();

  ConnectionListener(const ConnectionListener&) = delete;
  ConnectionListener& operator=(const ConnectionListener&) = delete;

  void start();
  void stop();

 private:
  void run();

  BackendLink& link_;
  StateMachine& sm_;
  int retry_sec_;
  int check_sec_;
  bool force_offline_ = false;
  std::atomic<bool> stop_{false};
  std::thread thread_;
};

}  // namespace calypso
