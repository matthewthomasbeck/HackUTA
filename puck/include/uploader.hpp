#pragma once

#include <atomic>
#include <chrono>
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

  // One pass: correct_unsynced, then post pending oldest-first; stops at the
  // first failure (-1 / 5xx). 2xx and 409 remove the item; other 4xx move it
  // to <spool>/rejected/. Returns items removed (not counting rejected).
  int drain_once();
  std::chrono::milliseconds next_backoff();  // 1s doubling to 60s; reset on a clean pass
  void run(std::atomic<bool>& stop);

 private:
  SegmentSpool& spool_;
  PostFn post_;
  const ClockSource& clock_;
  std::chrono::milliseconds backoff_{1000};
  bool last_failed_ = false;
};

}  // namespace calypso
