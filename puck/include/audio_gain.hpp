#pragma once

#include <cstdint>
#include <vector>

namespace calypso {

// Multiplies samples by gain with saturation to [-32768, 32767]. gain <= 1 leaves pcm unchanged.
void apply_gain(std::vector<std::int16_t>& pcm, float gain);

// Root-mean-square of pcm, normalized to 0..1 (sample / 32768). Empty -> 0.
float pcm_rms(const std::vector<std::int16_t>& pcm);

}  // namespace calypso
