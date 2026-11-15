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

  // MODE=online|offline — offline force-tests the emergency path
  ModeSetting mode = ModeSetting::Online;

  int chunk_ms = 30;              // mic read size (both modes)
  int segment_ms = 3000;          // online: buffer then POST
  int offline_segment_ms = 2000;  // offline: concat then infer (separate)
  int connect_retry_sec = 5;
  int connection_check_sec = 2;

  InferBackend infer_backend = InferBackend::Cpu;
  std::string coral_device;
  std::string ncs2_device;
  std::string stt_model_path;
  std::string voice_model_path =
      "models/nemo_en_titanet_small.onnx";  // titanet-small
  std::string gallery_dir = "gallery";
  float voice_match_threshold = 0.55f;

  std::string bt_adapter;     // e.g. hci0
  std::string bt_peer_name;   // phone / app advertisement name
};

bool load_config(const std::string& path, Config& out);

}  // namespace calypso
