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
  // Stub structure only: concat logic intentionally empty for pipeline review.
  // TODO: append chunk.pcm; track start ts + buffered_ms_; when >= target_ms_,
  //       return AudioChunk{concatenated pcm, start, buffered_ms_} and clear.
  (void)chunk;
  return std::nullopt;
}

}  // namespace calypso
