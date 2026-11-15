#pragma once

#include "backend_link.hpp"
#include "state_machine.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// THREAD 1 — watches BackendLink (HTTP); flips StateMachine to Offline on drop,
// keeps retrying connect every retry_sec.
class ConnectionListener {
 public:
  ConnectionListener(BackendLink& link, StateMachine& sm, int retry_sec,
                     int check_sec);
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
  std::atomic<bool> stop_{false};
  std::thread thread_;
};

}  // namespace calypso
