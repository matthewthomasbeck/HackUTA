#pragma once

#include "types.hpp"

#include <condition_variable>
#include <cstddef>
#include <deque>
#include <mutex>
#include <optional>

namespace calypso {

// Bounded SPSC/MPSC queue between capture and upload/infer.
// push never blocks the mic: if full, drops the oldest chunk.
class ChunkQueue {
 public:
  explicit ChunkQueue(std::size_t max_chunks = 200) : max_(max_chunks) {}

  void push(AudioChunk chunk) {
    {
      std::lock_guard<std::mutex> lock(mu_);
      if (closed_) {
        return;
      }
      if (q_.size() >= max_) {
        q_.pop_front();  // prefer fresh audio over blocking capture
        ++dropped_;
      }
      q_.push_back(std::move(chunk));
    }
    cv_.notify_one();
  }

  // Blocks until a chunk is available, closed, or stop_flag is true.
  // Returns nullopt if closed/stopped with nothing left.
  template <typename StopPred>
  std::optional<AudioChunk> pop_wait(StopPred&& stopped) {
    std::unique_lock<std::mutex> lock(mu_);
    cv_.wait(lock, [&] {
      return closed_ || stopped() || !q_.empty();
    });
    if (q_.empty()) {
      return std::nullopt;
    }
    AudioChunk c = std::move(q_.front());
    q_.pop_front();
    return c;
  }

  void close() {
    {
      std::lock_guard<std::mutex> lock(mu_);
      closed_ = true;
    }
    cv_.notify_all();
  }

  void reopen() {
    std::lock_guard<std::mutex> lock(mu_);
    closed_ = false;
  }

  std::size_t size() const {
    std::lock_guard<std::mutex> lock(mu_);
    return q_.size();
  }

  std::uint64_t dropped() const {
    std::lock_guard<std::mutex> lock(mu_);
    return dropped_;
  }

 private:
  mutable std::mutex mu_;
  std::condition_variable cv_;
  std::deque<AudioChunk> q_;
  std::size_t max_;
  bool closed_ = false;
  std::uint64_t dropped_ = 0;
};

}  // namespace calypso
