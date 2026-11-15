#include "segmenter.hpp"

#include "capture.hpp"
#include "util.hpp"

namespace calypso {

Segmenter::Segmenter(int segment_ms, const ClockSource& clock)
    : segment_ms_(segment_ms > 0 ? segment_ms : 3000), clock_(clock) {}

std::optional<std::pair<std::vector<std::int16_t>, SpoolItem>> Segmenter::push(
    const AudioChunk& c) {
  if (c.pcm.empty()) return std::nullopt;
  if (!has_start_) {
    start_ = c.ts;
    has_start_ = true;
    start_synced_ = clock_.now().synced;
  }
  buf_.insert(buf_.end(), c.pcm.begin(), c.pcm.end());
  const std::int64_t ms =
      static_cast<std::int64_t>(buf_.size()) * 1000 / kSampleRate;
  if (ms < segment_ms_) return std::nullopt;

  const ClockSnapshot snap = clock_.now();
  SpoolItem it;
  it.uuid = make_segment_uuid();
  it.ts_start_iso = format_iso8601_utc(start_);
  it.ts_end_iso = format_iso8601_utc(start_ + std::chrono::milliseconds(ms));
  // Synced only if it was synced for the whole segment: a segment spanning an
  // NTP step keeps a pre-step ts_start, so treat it as unsynced; the uploader
  // then corrects it from boot time like any other same-boot unsynced item.
  it.time_synced = start_synced_ && snap.synced;
  it.boot_id = snap.boot_id;
  it.boot_ms_end = snap.boot_ms;
  it.boot_ms_start = snap.boot_ms - ms;

  std::vector<std::int16_t> pcm = std::move(buf_);
  buf_.clear();
  has_start_ = false;
  return std::make_pair(std::move(pcm), std::move(it));
}

}  // namespace calypso
