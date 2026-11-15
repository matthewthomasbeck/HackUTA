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
#include <csignal>
#include <atomic>
#include <iostream>
#include <thread>

namespace {

std::atomic<bool> g_run{true};

void on_signal(int) { g_run.store(false); }

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
  std::signal(SIGINT, on_signal);
  std::signal(SIGTERM, on_signal);

  calypso::Config cfg;
  if (!calypso::load_config("config/.env", cfg)) {
    std::cerr << "failed to load config/.env "
                 "(need BACKEND_IP, BACKEND_PORT, API_TOKEN, MIC_DEVICE)\n";
    return 1;
  }

  calypso::Capture capture;
  calypso::BackendLink link;
  calypso::Models models;

  if (!capture.init(cfg.mic_device, cfg.chunk_ms)) {
    std::cerr << "mic init failed — set MIC_DEVICE to an ALSA name or 'sine'\n";
    return 1;
  }
  if (!link.init(cfg.backend_ip, cfg.backend_port, cfg.api_token,
                 cfg.segment_ms)) {
    std::cerr << "backend link init failed\n";
    return 1;
  }
  // Offline models stay stubbed; online path does not need them.
  if (!models.init(cfg.ncs2_device, cfg.stt_model_path, cfg.voice_model_path)) {
    std::cerr << "models init skipped/stub — offline infer will no-op\n";
  }

  const bool online =
      wait_for_initial_connection(link, cfg.connect_retry_sec);
  const calypso::RunMode initial =
      online ? calypso::RunMode::Online : calypso::RunMode::Offline;
  std::cerr << "starting state machine in "
            << (online ? "ONLINE" : "OFFLINE") << " mode\n";

  calypso::StateMachine sm(capture, link, models);
  calypso::ConnectionListener listener(link, sm, cfg.connect_retry_sec,
                                       cfg.connection_check_sec);

  sm.start(initial);       // listen thread + upload/infer worker
  listener.start();        // connection watch

  while (g_run.load()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }

  std::cerr << "shutting down\n";
  listener.stop();
  sm.stop();
  models.shutdown();
  link.shutdown();
  capture.shutdown();
  return 0;
}
