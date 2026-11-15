#pragma once

#include <chrono>
#include <string>

namespace calypso {

// Safe id for segment_uuid: hex, [A-Za-z0-9_-]{1,128}.
std::string make_segment_uuid();

// UTC with ms + Z, e.g. 2026-11-14T15:30:00.123Z
std::string format_iso8601_utc(std::chrono::system_clock::time_point tp);

}  // namespace calypso
