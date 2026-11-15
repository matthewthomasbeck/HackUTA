// THREAD 0 — main
// systemd launches the built binary (see systemd/calypso-puck.service).

#include "backend_link.hpp"
#include "capture.hpp"
#include "config.hpp"
#include "connection_listener.hpp"
#include "models.hpp"
#include "state_machine.hpp"
#include "types.hpp"

#include <chrono>
#include <iostream>
#include <thread>

namespace {

// Wait up to retry_sec for an initial backend session.
// Returns true → Online; false → start Offline (listener keeps retrying).
bool wait_for_initial_connection(calypso::BackendLink& link, int retry_sec) {
  if (link.connect()) {
    return true;
  }
  std::cerr << "backend unreachable; waiting " << retry_sec << "s\n";
  std::this_thread::sleep_for(std::chrono::seconds(retry_sec));
  return link.connect();
}

}  // namespace

int main() {
  // 2. Config from config/.env (IP, port, mic bus, chunk size, retries).
  calypso::Config cfg;
  if (!calypso::load_config("config/.env", cfg)) {
    std::cerr << "failed to load config/.env\n";
    return 1;
  }

  calypso::Capture capture;
  calypso::BackendLink link;
  calypso::Models models;

  // 3. Pre-init peripherals + link + NCS2 models before the state machine.
  if (!capture.init(cfg.mic_device, cfg.chunk_ms)) {
    std::cerr << "mic init failed (stub)\n";
    // Stub: continue so the skeleton can be run without hardware.
  }
  if (!link.init(cfg.backend_ip, cfg.backend_port)) {
    std::cerr << "backend link init failed\n";
    return 1;
  }
  if (!models.init(cfg.ncs2_device, cfg.stt_model_path, cfg.voice_model_path)) {
    std::cerr << "NCS2 / model init failed (stub) — offline infer will no-op\n";
  }

  // 4–5. Connect or wait n seconds; then pick Online vs Offline.
  const bool online =
      wait_for_initial_connection(link, cfg.connect_retry_sec);
  const calypso::RunMode initial =
      online ? calypso::RunMode::Online : calypso::RunMode::Offline;
  std::cerr << "starting state machine in "
            << (online ? "ONLINE" : "OFFLINE") << " mode\n";

  calypso::StateMachine sm(capture, link, models);
  calypso::ConnectionListener listener(link, sm, cfg.connect_retry_sec,
                                       cfg.connection_check_sec);

  sm.start(initial);       // THREAD 2 — online/offline ticks
  listener.start();        // THREAD 1 — connection watch + reconnect

  // Block until signal handling exists; systemd Restart= covers crashes.
  while (true) {
    std::this_thread::sleep_for(std::chrono::hours(24));
  }

  listener.stop();
  sm.stop();
  models.shutdown();
  link.shutdown();
  capture.shutdown();
  return 0;
}
