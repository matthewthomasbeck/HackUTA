#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace calypso {

// Build a mono s16le WAV (PCM) blob at sample_rate Hz.
std::string pcm16_to_wav(const std::vector<std::int16_t>& pcm, int sample_rate);

// Read a mono (or first-channel) PCM16 WAV into samples + sample_rate.
// Returns false on unsupported formats / IO errors.
bool read_wav_file(const std::string& path, std::vector<std::int16_t>& pcm,
                   int& sample_rate);

}  // namespace calypso

