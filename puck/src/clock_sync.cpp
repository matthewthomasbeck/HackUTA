#include "clock_sync.hpp"

#include <time.h>

#include <fstream>

#ifdef __linux__
#include <sys/timex.h>
#endif

#include "util.hpp"

namespace calypso {

ClockSnapshot SystemClock::now() const {
  ClockSnapshot s;
  s.realtime = std::chrono::system_clock::now();
  timespec ts{};
#ifdef __linux__
  timex tx{};
  tx.modes = 0;
  const int st = adjtimex(&tx);
  s.synced = st >= 0 && st != TIME_ERROR && !(tx.status & STA_UNSYNC);
  clock_gettime(CLOCK_BOOTTIME, &ts);
  std::ifstream in("/proc/sys/kernel/random/boot_id");
  std::getline(in, s.boot_id);
#else
  s.synced = true;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  s.boot_id = "darwin";
#endif
  s.boot_ms = static_cast<std::int64_t>(ts.tv_sec) * 1000 + ts.tv_nsec / 1000000;
  return s;
}

int correct_unsynced(SegmentSpool& spool, const ClockSnapshot& now) {
  if (!now.synced) return 0;
  int n = 0;
  for (const auto& it : spool.pending()) {
    if (it.time_synced || it.boot_id != now.boot_id) continue;
    const auto start = now.realtime - std::chrono::milliseconds(now.boot_ms - it.boot_ms_start);
    const auto end = now.realtime - std::chrono::milliseconds(now.boot_ms - it.boot_ms_end);
    spool.rewrite_times(it, format_iso8601_utc(start), format_iso8601_utc(end));
    ++n;
  }
  return n;
}

}  // namespace calypso
