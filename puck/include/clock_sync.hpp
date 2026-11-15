#pragma once

#include <chrono>
#include <cstdint>
#include <string>

#include "segment_spool.hpp"

namespace calypso {

struct ClockSnapshot {
  bool synced;
  std::chrono::system_clock::time_point realtime;
  std::int64_t boot_ms;  // monotonic ms since boot (CLOCK_BOOTTIME)
  std::string boot_id;
};

class ClockSource {
 public:
  virtual ~ClockSource() = default;
  virtual ClockSnapshot now() const = 0;
};

// Linux: adjtimex() sync state, CLOCK_BOOTTIME, kernel boot_id.
// macOS: always synced, boot_id "darwin", CLOCK_MONOTONIC.
class SystemClock : public ClockSource {
 public:
  ClockSnapshot now() const override;
};

// For pending unsynced items captured in the current boot, once the clock is
// synced: ts = realtime_now - (boot_ms_now - boot_ms_capture). Returns count.
int correct_unsynced(SegmentSpool& spool, const ClockSnapshot& now);

}  // namespace calypso
