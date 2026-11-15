#include "util.hpp"

#include <cstdio>
#include <ctime>
#include <random>

namespace calypso {

std::string make_segment_uuid() {
  static thread_local std::mt19937_64 rng{std::random_device{}()};
  std::uniform_int_distribution<int> dist(0, 15);
  static constexpr char kHex[] = "0123456789abcdef";
  std::string id;
  id.reserve(32);
  for (int i = 0; i < 32; ++i) {
    id.push_back(kHex[dist(rng)]);
  }
  return id;
}

std::string format_iso8601_utc(std::chrono::system_clock::time_point tp) {
  using namespace std::chrono;
  const auto ms = duration_cast<milliseconds>(tp.time_since_epoch()) % 1000;
  const std::time_t secs = system_clock::to_time_t(tp);
  std::tm tm{};
#if defined(_WIN32)
  gmtime_s(&tm, &secs);
#else
  gmtime_r(&secs, &tm);
#endif
  char buf[64];
  std::snprintf(buf, sizeof(buf), "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
                tm.tm_year + 1900, tm.tm_mon + 1, tm.tm_mday, tm.tm_hour,
                tm.tm_min, tm.tm_sec, static_cast<int>(ms.count()));
  return buf;
}

}  // namespace calypso
