#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// ALSA (or other) mic capture. Owns the device handle.
class Capture {
 public:
  Capture() = default;
  ~Capture();

  Capture(const Capture&) = delete;
  Capture& operator=(const Capture&) = delete;

  // Open mic_device (ALSA name / bus). Returns false on failure.
  bool init(const std::string& mic_device, int chunk_ms);

  // Block until one chunk_ms frame is ready, or return false on error/stop.
  bool read_chunk(AudioChunk& out);

  void shutdown();

 private:
  bool open_ = false;
  int chunk_ms_ = 30;
  // TODO: snd_pcm_t* / ring buffer
};

}  // namespace calypso
