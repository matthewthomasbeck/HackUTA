// THREAD 0 — main
// systemd launches the built binary (see systemd/calypso-puck.service).

#include "accelerators.hpp"
#include "backend_link.hpp"
#include "capture.hpp"
#include "config.hpp"
#include "connection_listener.hpp"
#include "models.hpp"
#include "phone_link.hpp"
#include "state_machine.hpp"
#include "types.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
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
  calypso::Accelerators accelerators;
  calypso::PhoneLink phone;
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

  // Optional sticks — stubs; failure is OK for CPU-only offline ID.
  if (!accelerators.init_coral(cfg.coral_device)) {
    std::cerr << "coral init skipped/stub\n";
  }
  if (!accelerators.init_ncs2(cfg.ncs2_device)) {
    std::cerr << "ncs2 init skipped/stub\n";
  }

  if (!phone.init(cfg.bt_adapter, cfg.bt_peer_name)) {
    std::cerr << "phone bluetooth init failed\n";
  } else if (!phone.connect()) {
    std::cerr << "phone bluetooth connect skipped/stub\n";
  }

  // Titanet-small on CPU; needs CALYPSO_SHERPA_ROOT at cmake time.
  if (!models.init(cfg.infer_backend, cfg.voice_model_path, cfg.stt_model_path,
                   cfg.gallery_dir, cfg.voice_match_threshold, &accelerators)) {
    std::cerr << "models init skipped/stub — offline infer will no-op\n";
  }

  const bool force_offline = (cfg.mode == calypso::ModeSetting::Offline);
  calypso::RunMode initial = calypso::RunMode::Offline;
  if (force_offline) {
    std::cerr << "MODE=offline — forcing Offline (skip health for run path)\n";
  } else {
    const bool online =
        wait_for_initial_connection(link, cfg.connect_retry_sec);
    initial = online ? calypso::RunMode::Online : calypso::RunMode::Offline;
  }
  std::cerr << "starting state machine in "
            << (initial == calypso::RunMode::Online ? "ONLINE" : "OFFLINE")
            << " mode\n";

  calypso::StateMachine sm(capture, link, models, phone,
                           cfg.offline_segment_ms);
  calypso::ConnectionListener listener(link, sm, cfg.connect_retry_sec,
                                       cfg.connection_check_sec,
                                       force_offline);

  sm.start(initial);       // listen thread + upload/infer worker
  listener.start();        // connection watch (no-op promote when forced)

  while (g_run.load()) {
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
  }

  std::cerr << "shutting down\n";
  listener.stop();
  sm.stop();
  models.shutdown();
  phone.shutdown();
  accelerators.shutdown();
  link.shutdown();
  capture.shutdown();
  return 0;
}
