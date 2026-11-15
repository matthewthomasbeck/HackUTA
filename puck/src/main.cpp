#include "calypso_puck/config.hpp"

#include <iostream>

int main() {
  const auto cfg = calypso_puck::load_config_from_env();
  std::cerr << "calypso_puck scaffold — capture/VAD/queue not wired yet\n"
            << "  PUCK_MIC=" << cfg.mic_device << "\n"
            << "  PUCK_FRAME_MS=" << cfg.frame_ms << "\n"
            << "  PUCK_SOUND_BACKEND=" << cfg.sound_backend << "\n";
  return 0;
}
