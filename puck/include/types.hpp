#pragma once

#include <chrono>
#include <cstdint>
#include <string>
#include <vector>

namespace calypso {

enum class RunMode {
  Online,
  Offline,
};

struct AudioChunk {
  std::vector<std::int16_t> pcm;  // 16 kHz mono s16le
  std::chrono::system_clock::time_point ts;
  int duration_ms = 0;
};

// Placeholder until offline-mode brainstorm lands.
struct ModelOutput {
  std::string transcript;
  std::vector<float> voice_embedding;
};

}  // namespace calypso
