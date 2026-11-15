#include "connection_listener.hpp"

#include <chrono>

namespace calypso {

ConnectionListener::ConnectionListener(BackendLink& link, StateMachine& sm,
                                       int retry_sec, int check_sec)
    : link_(link), sm_(sm), retry_sec_(retry_sec), check_sec_(check_sec) {}

ConnectionListener::~ConnectionListener() {
  stop();
}

void ConnectionListener::start() {
  stop_.store(false);
  if (thread_.joinable()) {
    return;
  }
  thread_ = std::thread([this] { run(); });
}

void ConnectionListener::stop() {
  stop_.store(true);
  if (thread_.joinable()) {
    thread_.join();
  }
}

void ConnectionListener::run() {
  while (!stop_.load()) {
    if (link_.is_connected()) {
      sm_.set_mode(RunMode::Online);
      std::this_thread::sleep_for(std::chrono::seconds(check_sec_));
      continue;
    }

    // Connection interrupted / never up: wait n seconds, then Offline,
    // while still retrying connect every n seconds.
    std::this_thread::sleep_for(std::chrono::seconds(retry_sec_));
    if (stop_.load()) {
      break;
    }

    if (!link_.connect()) {
      sm_.set_mode(RunMode::Offline);
    } else {
      sm_.set_mode(RunMode::Online);
    }
  }
}

}  // namespace calypso
