#pragma once

#include <cstdint>
#include <string>

namespace calypso_puck {

struct Config {
  std::string base_url;
  std::string api_token;
  std::string mic_device;
  int frame_ms = 30;  // WebRTC VAD: 10 | 20 | 30
  std::string sound_backend = "cpu";
  int sound_every_n = 1;
  std::string queue_path = "data/puck_queue.db";
};

// Loads from environment (CALYPSO_*, PUCK_*). Missing required keys leave
// empty strings; callers decide whether to fail at startup.
Config load_config_from_env();

}  // namespace calypso_puck
