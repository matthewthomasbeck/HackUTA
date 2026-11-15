#include "capture.hpp"

namespace calypso {

Capture::~Capture() {
  shutdown();
}

bool Capture::init(const std::string& /*mic_device*/, int chunk_ms) {
  chunk_ms_ = chunk_ms;
  // TODO: snd_pcm_open / set rate 16 kHz mono
  open_ = false;
  return open_;
}

bool Capture::read_chunk(AudioChunk& out) {
  if (!open_) {
    return false;
  }
  // TODO: blocking ALSA read of chunk_ms_ frames
  out = {};
  out.duration_ms = chunk_ms_;
  return false;
}

void Capture::shutdown() {
  // TODO: snd_pcm_close
  open_ = false;
}

}  // namespace calypso
