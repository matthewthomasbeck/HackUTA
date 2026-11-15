// THREAD 0 — main
// systemd launches the built binary (see systemd/calypso-puck.service).

#include "accelerators.hpp"
#include "backend_link.hpp"
#include "capture.hpp"
#include "clock_sync.hpp"
#include "config.hpp"
#include "connection_listener.hpp"
#include "models.hpp"
#include "phone_link.hpp"
#include "segment_spool.hpp"
#include "state_machine.hpp"
#include "types.hpp"
#include "uploader.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <stdexcept>
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

  // The spool is where every segment lands, so fail fast and clearly if it
  // can't be created (systemd's StateDirectory= makes /var/lib/calypso-puck).
  std::unique_ptr<calypso::SegmentSpool> spool_ptr;
  try {
    spool_ptr = std::make_unique<calypso::SegmentSpool>(
        cfg.spool_dir,
        static_cast<std::uint64_t>(cfg.spool_max_mb > 0 ? cfg.spool_max_mb : 512) *
            1024ull * 1024ull);
    const std::filesystem::path probe =
        std::filesystem::path(cfg.spool_dir) / ".write_test";
    std::ofstream(probe) << "ok";
    if (!std::filesystem::exists(probe)) {
      throw std::runtime_error("directory is not writable");
    }
    std::filesystem::remove(probe);
  } catch (const std::exception& e) {
    std::cerr << "cannot use spool dir PUCK_SPOOL_DIR=" << cfg.spool_dir << ": "
              << e.what()
              << "\n  create it and make it writable by this user, or set "
                 "PUCK_SPOOL_DIR (systemd unit uses StateDirectory=calypso-puck)\n";
    return 1;
  }
  calypso::SegmentSpool& spool = *spool_ptr;

  calypso::Capture capture;
  calypso::BackendLink link;
  calypso::Accelerators accelerators;
  calypso::PhoneLink phone;
  calypso::Models models;

  if (!capture.init(cfg.mic_device, cfg.chunk_ms)) {
    std::cerr << "mic init failed — set MIC_DEVICE to an ALSA name or 'sine'\n";
    return 1;
  }
  capture.set_gain(cfg.mic_gain);
  std::cerr << "capture: MIC_GAIN=" << cfg.mic_gain << "\n";
  if (!link.init(cfg.backend_ip, cfg.backend_port, cfg.api_token)) {
    std::cerr << "backend link init failed\n";
    return 1;
  }

  // Accelerator control plane — TPU_MODE=coral arms Edge TPU (live or compat).
  if (cfg.tpu_mode == calypso::TpuMode::Coral) {
    std::cerr << "TPU_MODE=coral — initializing Google Coral USB Edge TPU\n";
    if (!accelerators.init_coral(cfg.coral_device, cfg.coral_model_path)) {
      std::cerr << "coral init failed\n";
    }
    // Dashboard always shows coral when the mode is selected.
    link.set_sound_backend("coral");
  } else if (cfg.tpu_mode == calypso::TpuMode::Ncs2) {
    if (!accelerators.init_ncs2(cfg.ncs2_device)) {
      std::cerr << "ncs2 init skipped/stub\n";
    }
    link.set_sound_backend(accelerators.backend_label());
  } else {
    std::cerr << "TPU_MODE=off — CPU sherpa-onnx path\n";
    link.set_sound_backend("none");
  }

  if (!phone.init(cfg.bt_adapter, cfg.bt_peer_name, cfg.who_drop_path)) {
    std::cerr << "phone init failed\n";
  } else if (!phone.connect()) {
    std::cerr << "phone connect skipped\n";
  }

  // Titanet host embedder (+ Coral routing when TPU_MODE=coral).
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

  calypso::SystemClock clock;
  std::atomic<bool> upload_stop{false};
  std::atomic<bool> last_upload_ok{true};
  calypso::Uploader uploader(
      spool,
      [&](const std::string& wav, const std::string& meta) {
        const int st = link.post_segment(wav, meta);
        last_upload_ok.store(st >= 200 && st < 300);
        return st;
      },
      clock);
  std::thread upload_thread([&] { uploader.run(upload_stop); });
  std::thread health_thread([&] {
    std::size_t last_rejected = 0;
    while (!upload_stop.load()) {
      link.post_health(spool.depth(), clock.now().synced, last_upload_ok.load());
      const std::size_t rejected = uploader.rejected_count();
      if (rejected != last_rejected) {  // not in /puck/health (shared contract)
        std::cerr << "health: rejected/ holds " << rejected << " segments (cap "
                  << calypso::Uploader::kMaxRejected << ")\n";
        last_rejected = rejected;
      }
      for (int i = 0; i < 100 && !upload_stop.load(); ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
    }
  });

  calypso::StateMachine sm(capture, link, models, phone,
                           cfg.offline_segment_ms, spool, clock,
                           cfg.segment_ms, cfg.min_speech_rms,
                           cfg.voice_min_score);
  calypso::ConnectionListener listener(link, sm, models, cfg.connect_retry_sec,
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
  upload_stop.store(true);  // uploader finishes its in-flight POST, then exits
  upload_thread.join();
  health_thread.join();
  models.shutdown();
  phone.shutdown();
  accelerators.shutdown();
  link.shutdown();
  capture.shutdown();
  return 0;
}
