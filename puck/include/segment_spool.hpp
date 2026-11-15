#pragma once

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace calypso {

struct SpoolItem {
  std::string uuid;
  std::string ts_start_iso, ts_end_iso;  // UTC, format_iso8601_utc
  bool time_synced = true;
  std::string boot_id;  // only meaningful when !time_synced
  std::int64_t boot_ms_start = 0, boot_ms_end = 0;  // CLOCK_BOOTTIME ms
  std::filesystem::path wav_path, json_path;
};

// Durable on-disk spool of audio segments. The .json file is the commit
// marker: a .wav without its .json is an orphan and is ignored.
class SegmentSpool {
 public:
  SegmentSpool(std::filesystem::path dir, std::uint64_t max_bytes);

  // Writes <ts_start_compact>_<uuid>.wav + .json atomically (tmp + fsync +
  // rename). Evicts oldest if over max_bytes. Generates a uuid if meta.uuid
  // is empty.
  SpoolItem enqueue(const std::vector<std::int16_t>& pcm, SpoolItem meta);
  std::vector<SpoolItem> pending() const;  // oldest first, by filename
  void remove(const SpoolItem& item);      // deletes both files
  void rewrite_times(const SpoolItem& item, const std::string& ts_start_iso,
                     const std::string& ts_end_iso);  // sets time_synced=true
  std::string meta_json(const SpoolItem& item) const;  // multipart "meta" body
  std::uint64_t evicted_count() const;
  std::size_t depth() const;

 private:
  std::filesystem::path dir_;
  std::uint64_t max_bytes_;
  std::uint64_t evicted_ = 0;
};

}  // namespace calypso
