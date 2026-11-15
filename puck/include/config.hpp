#pragma once

#include <cstdint>
#include <string>

namespace calypso {

struct Config {
  // Backend socket
  std::string backend_ip;
  std::uint16_t backend_port = 0;

  // Mic ALSA / bus path from Spike D
  std::string mic_device;

  // Pipeline knobs
  int chunk_ms = 30;              // n ms audio frames
  int connect_retry_sec = 5;      // wait n seconds before offline / retry
  int connection_check_sec = 2;   // listener poll interval

  // NCS2 / local models (paths filled later)
  std::string ncs2_device;
  std::string stt_model_path;
  std::string voice_model_path;
};

// Loads key=value from config/.env (path relative to cwd or absolute).
// Returns false if the file is missing or required keys are absent.
bool load_config(const std::string& path, Config& out);

}  // namespace calypso
