#pragma once

#include "backend_link.hpp"
#include "models.hpp"
#include "state_machine.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// THREAD 1 — watches BackendLink (HTTP); flips StateMachine to Offline on drop,
// keeps retrying connect every retry_sec. While reachable, replace-syncs the
// local voice gallery from GET /puck/gallery so the Pi stays 1:1 with cloud.
// When force_offline_ is true (MODE=offline), pins Offline and never promotes,
// but still probes the backend for gallery sync.
class ConnectionListener {
 public:
  ConnectionListener(BackendLink& link, StateMachine& sm, Models& models,
                     int retry_sec, int check_sec, bool force_offline = false);
  ~ConnectionListener();

  ConnectionListener(const ConnectionListener&) = delete;
  ConnectionListener& operator=(const ConnectionListener&) = delete;

  void start();
  void stop();

 private:
  void run();
  void sync_gallery();

  BackendLink& link_;
  StateMachine& sm_;
  Models& models_;
  int retry_sec_;
  int check_sec_;
  bool force_offline_ = false;
  std::size_t last_gallery_size_ = static_cast<std::size_t>(-1);
  std::atomic<bool> stop_{false};
  std::thread thread_;
};

}  // namespace calypso
