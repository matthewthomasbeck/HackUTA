#pragma once

#include <cstdint>
#include <string>

namespace calypso {

struct Config {
  std::string backend_ip;
  std::uint16_t backend_port = 0;
  std::string api_token;

  std::string mic_device;  // ALSA name, or "sine" for test tone

  int chunk_ms = 30;             // mic read size
  int segment_ms = 3000;         // buffer this much audio, then POST
  int connect_retry_sec = 5;
  int connection_check_sec = 2;

  // Offline / NCS2 — unused for online path
  std::string ncs2_device;
  std::string stt_model_path;
  std::string voice_model_path;
};

bool load_config(const std::string& path, Config& out);

}  // namespace calypso
