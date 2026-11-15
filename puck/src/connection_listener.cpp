#include "connection_listener.hpp"

#include "gallery_json.hpp"

#include <chrono>
#include <iostream>
#include <vector>

namespace calypso {

ConnectionListener::ConnectionListener(BackendLink& link, StateMachine& sm,
                                       Models& models, int retry_sec,
                                       int check_sec, bool force_offline)
    : link_(link),
      sm_(sm),
      models_(models),
      retry_sec_(retry_sec),
      check_sec_(check_sec),
      force_offline_(force_offline) {}

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

void ConnectionListener::sync_gallery() {
  std::string body;
  if (!link_.get_gallery(body)) {
    return;
  }
  std::vector<EnrolledSpeaker> speakers;
  if (!parse_puck_gallery(body, speakers)) {
    std::cerr << "gallery sync: failed to parse /puck/gallery body ("
              << body.size() << " bytes)\n";
    return;
  }
  models_.replace_gallery(std::move(speakers));
  const std::size_t n = models_.gallery_size();
  if (n != last_gallery_size_) {
    std::cerr << "gallery sync: " << n << " speaker(s) from cloud\n";
    last_gallery_size_ = n;
  }
}

void ConnectionListener::run() {
  while (!stop_.load()) {
    if (force_offline_) {
      // MODE=offline: stay on the emergency path even if the backend is up.
      sm_.set_mode(RunMode::Offline);
      // Still pull gallery so FaceTime enrollments land on the Pi.
      if (link_.is_connected() || link_.connect()) {
        sync_gallery();
      }
      std::this_thread::sleep_for(std::chrono::seconds(check_sec_));
      continue;
    }

    if (link_.is_connected()) {
      sm_.set_mode(RunMode::Online);
      sync_gallery();
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
      sync_gallery();
    }
  }
}

}  // namespace calypso
