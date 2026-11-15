#pragma once

#include "types.hpp"

#include <cstdint>
#include <string>

namespace calypso {

struct Config {
  std::string backend_ip;
  std::uint16_t backend_port = 0;
  std::string api_token;

  std::string mic_device;  // ALSA name, or "sine" for test tone
  float mic_gain = 1.0f;   // MIC_GAIN software gain, clamped to [1, 32]

  // MODE=online|offline — offline force-tests the emergency path
  ModeSetting mode = ModeSetting::Online;

  int chunk_ms = 30;              // mic read size (both modes)
  int segment_ms = 3000;          // online: buffer then POST
  int offline_segment_ms = 3000;  // offline: longer clips → stabler embeddings
  int connect_retry_sec = 5;
  int connection_check_sec = 2;

  // TPU_MODE drives offline infer. INFER_BACKEND is kept as a mirror.
  TpuMode tpu_mode = TpuMode::Off;
  InferBackend infer_backend = InferBackend::Cpu;
  std::string coral_device;  // optional USB path hint
  // Edge-TPU-compiled Titanet (or staged placeholder until edgetpu_compiler).
  std::string coral_model_path =
      "models/nemo_en_titanet_small_edgetpu.tflite";
  std::string ncs2_device;
  std::string stt_model_path;
  std::string voice_model_path =
      "models/nemo_en_titanet_small.onnx";  // titanet-small (host / sherpa)
  std::string gallery_dir = "gallery";
  float voice_match_threshold = 0.45f;  // 0.55 was too strict for lav + 1 speaker
  float min_speech_rms = 0.02f;         // skip quiet windows before embed
  float voice_min_score = 0.2f;         // below this, an unmatched clip is noise, not "someone new"

  std::string spool_dir = "/var/lib/calypso-puck/spool";
  int spool_max_mb = 512;

  std::string bt_adapter;     // e.g. hci0
  std::string bt_peer_name;   // phone / app advertisement name
  // Drop file for BLE sidecar (scripts/ble_who_peripheral.py)
  std::string who_drop_path = "/tmp/calypso_who.json";
};

bool load_config(const std::string& path, Config& out);

}  // namespace calypso
