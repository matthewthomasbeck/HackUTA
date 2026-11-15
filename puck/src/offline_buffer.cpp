#include "offline_buffer.hpp"

namespace calypso {

OfflineBuffer::OfflineBuffer(int target_ms) {
  set_target_ms(target_ms);
}

void OfflineBuffer::set_target_ms(int target_ms) {
  target_ms_ = target_ms > 0 ? target_ms : 2000;
}

int OfflineBuffer::target_ms() const {
  return target_ms_;
}

void OfflineBuffer::clear() {
  pcm_.clear();
  has_start_ = false;
  buffered_ms_ = 0;
}

std::optional<AudioChunk> OfflineBuffer::push(const AudioChunk& chunk) {
  if (chunk.pcm.empty() || chunk.duration_ms <= 0) {
    return std::nullopt;
  }

  if (!has_start_) {
    start_ = chunk.ts;
    has_start_ = true;
  }

  pcm_.insert(pcm_.end(), chunk.pcm.begin(), chunk.pcm.end());
  buffered_ms_ += chunk.duration_ms;

  if (buffered_ms_ < target_ms_) {
    return std::nullopt;
  }

  AudioChunk out;
  out.pcm = std::move(pcm_);
  out.ts = start_;
  out.duration_ms = buffered_ms_;
  clear();
  return out;
}

}  // namespace calypso
