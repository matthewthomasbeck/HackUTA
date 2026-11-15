#pragma once

#include <atomic>
#include <chrono>
#include <cstddef>
#include <filesystem>
#include <functional>
#include <string>

#include "clock_sync.hpp"
#include "segment_spool.hpp"

namespace calypso {

// Returns HTTP status, or -1 on a transport error.
using PostFn = std::function<int(const std::string& wav, const std::string& meta_json)>;

class Uploader {
 public:
  Uploader(SegmentSpool& spool, PostFn post, const ClockSource& clock);

  static constexpr std::size_t kMaxRejected = 200;

  // One pass: correct_unsynced, then post pending oldest-first. Unsynced items
  // from the current boot are held while the clock is unsynced. Stops at the
  // first transient failure (-1, 5xx, 401, 403, 408, 429). 2xx and 409 remove
  // the item; other 4xx move it to <spool>/rejected/ (capped at kMaxRejected
  // items, oldest pruned). Returns items removed (not counting rejected).
  int drain_once();
  std::size_t rejected_count() const { return rejected_.load(); }
  std::chrono::milliseconds next_backoff();  // 1s doubling to 60s; reset on a clean pass
  void run(std::atomic<bool>& stop);

 private:
  SegmentSpool& spool_;
  PostFn post_;
  const ClockSource& clock_;
  std::chrono::milliseconds backoff_{1000};
  bool last_failed_ = false;
  std::atomic<std::size_t> rejected_{0};
};

// Deletes the oldest items in a rejected/ dir beyond max_items; returns the count kept.
std::size_t prune_rejected(const std::filesystem::path& dir, std::size_t max_items);

}  // namespace calypso
