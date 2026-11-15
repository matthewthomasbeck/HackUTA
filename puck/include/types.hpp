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

// Where offline voice-fingerprint inference runs. Default CPU; TPU later.
enum class InferBackend {
  Cpu,
  Coral,
  Ncs2,
};

struct AudioChunk {
  std::vector<std::int16_t> pcm;  // 16 kHz mono s16le
  std::chrono::system_clock::time_point ts;
  int duration_ms = 0;
};

// "Who is talking" result for the phone (offline emergency path).
struct WhoIsTalking {
  enum class Status { Identified, Uncertain, Unknown };

  Status status = Status::Unknown;
  std::string person_id;
  std::string display_name;
  std::string relationship;
  float score = 0.f;
};

struct ModelOutput {
  std::string transcript;
  std::vector<float> voice_embedding;
  WhoIsTalking who;
};

}  // namespace calypso
