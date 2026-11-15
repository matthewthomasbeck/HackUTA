#include "audio_gain.hpp"

#include <cmath>

namespace calypso {

void apply_gain(std::vector<std::int16_t>& pcm, float gain) {
  if (gain <= 1.0f) {
    return;
  }
  for (auto& s : pcm) {
    const float v = static_cast<float>(s) * gain;
    if (v >= 32767.0f) {
      s = 32767;
    } else if (v <= -32768.0f) {
      s = -32768;
    } else {
      s = static_cast<std::int16_t>(std::lround(v));
    }
  }
}

float pcm_rms(const std::vector<std::int16_t>& pcm) {
  if (pcm.empty()) {
    return 0.f;
  }
  double sum = 0.0;
  for (std::int16_t s : pcm) {
    const double x = static_cast<double>(s) / 32768.0;
    sum += x * x;
  }
  return static_cast<float>(std::sqrt(sum / static_cast<double>(pcm.size())));
}

}  // namespace calypso
