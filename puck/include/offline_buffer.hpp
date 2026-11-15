#pragma once

#include "types.hpp"

#include <chrono>
#include <cstdint>
#include <optional>
#include <vector>

namespace calypso {

// Offline-only: concat CHUNK_MS frames until OFFLINE_SEGMENT_MS, then emit one
// longer clip for voice-fingerprint inference.
// Does NOT touch BackendLink's online SEGMENT_MS buffer — reconnect keeps
// online upload behavior unchanged.
class OfflineBuffer {
 public:
  explicit OfflineBuffer(int target_ms = 2000);

  void set_target_ms(int target_ms);
  int target_ms() const;

  void clear();

  // Append one mic chunk. When enough audio is buffered, returns a concatenated
  // clip ready for Models::infer. Otherwise nullopt.
  std::optional<AudioChunk> push(const AudioChunk& chunk);

 private:
  int target_ms_ = 2000;
  std::vector<std::int16_t> pcm_;
  std::chrono::system_clock::time_point start_{};
  bool has_start_ = false;
  int buffered_ms_ = 0;
};

}  // namespace calypso
