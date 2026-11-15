#include "calypso_puck/config.hpp"

#include <cstdlib>

namespace calypso_puck {
namespace {

std::string env_or(const char* key, const std::string& fallback) {
  const char* v = std::getenv(key);
  return (v && *v) ? std::string(v) : fallback;
}

int env_int_or(const char* key, int fallback) {
  const char* v = std::getenv(key);
  if (!v || !*v) {
    return fallback;
  }
  return std::atoi(v);
}

}  // namespace

Config load_config_from_env() {
  Config c;
  c.base_url = env_or("CALYPSO_BASE_URL", "");
  c.api_token = env_or("CALYPSO_API_TOKEN", "");
  c.mic_device = env_or("PUCK_MIC", "");
  c.frame_ms = env_int_or("PUCK_FRAME_MS", 30);
  c.sound_backend = env_or("PUCK_SOUND_BACKEND", "cpu");
  c.sound_every_n = env_int_or("PUCK_SOUND_EVERY_N", 1);
  c.queue_path = env_or("PUCK_QUEUE_PATH", "data/puck_queue.db");
  return c;
}

}  // namespace calypso_puck
