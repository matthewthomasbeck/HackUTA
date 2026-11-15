#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace calypso {

// Build a mono s16le WAV (PCM) blob at sample_rate Hz.
std::string pcm16_to_wav(const std::vector<std::int16_t>& pcm, int sample_rate);

}  // namespace calypso
