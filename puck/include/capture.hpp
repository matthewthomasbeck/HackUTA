#pragma once

#include "types.hpp"

#include <cstdint>
#include <string>

namespace calypso {

inline constexpr int kSampleRate = 16000;

// Mic capture. Owns the device handle.
// MIC_DEVICE: ALSA name (e.g. plughw:1,0) on Linux, or "sine" for a test tone
// (no hardware — useful for laptop → backend smoke tests).
class Capture {
 public:
  Capture() = default;
  ~Capture();

  Capture(const Capture&) = delete;
  Capture& operator=(const Capture&) = delete;

  bool init(const std::string& mic_device, int chunk_ms);
  bool read_chunk(AudioChunk& out);
  // Software gain applied to every chunk (<= 1 = off). Set from MIC_GAIN.
  void set_gain(float gain) { gain_ = gain; }
  void shutdown();

 private:
  bool open_ = false;
  bool sine_ = false;
  int chunk_ms_ = 30;
  float gain_ = 1.0f;
  std::uint64_t sine_phase_ = 0;
#if defined(CALYPSO_HAS_ALSA)
  void* pcm_ = nullptr;  // snd_pcm_t*
#endif
};

}  // namespace calypso
