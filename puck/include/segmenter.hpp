#pragma once

#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

#include "clock_sync.hpp"
#include "segment_spool.hpp"
#include "types.hpp"

namespace calypso {

// Buffers mic chunks until segment_ms of audio, then emits a spool-ready
// segment with a fresh uuid and clock metadata captured at close.
class Segmenter {
 public:
  Segmenter(int segment_ms, const ClockSource& clock);
  std::optional<std::pair<std::vector<std::int16_t>, SpoolItem>> push(const AudioChunk& c);

 private:
  int segment_ms_;
  const ClockSource& clock_;
  std::vector<std::int16_t> buf_;
  std::chrono::system_clock::time_point start_{};
  bool has_start_ = false;
  bool start_synced_ = false;  // clock sync state when the segment's first chunk arrived
};

}  // namespace calypso
