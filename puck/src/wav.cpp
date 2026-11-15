#include "wav.hpp"

#include <cstring>

namespace calypso {
namespace {

void write_le16(std::string& out, std::uint16_t v) {
  out.push_back(static_cast<char>(v & 0xff));
  out.push_back(static_cast<char>((v >> 8) & 0xff));
}

void write_le32(std::string& out, std::uint32_t v) {
  out.push_back(static_cast<char>(v & 0xff));
  out.push_back(static_cast<char>((v >> 8) & 0xff));
  out.push_back(static_cast<char>((v >> 16) & 0xff));
  out.push_back(static_cast<char>((v >> 24) & 0xff));
}

}  // namespace

std::string pcm16_to_wav(const std::vector<std::int16_t>& pcm, int sample_rate) {
  const std::uint32_t data_bytes =
      static_cast<std::uint32_t>(pcm.size() * sizeof(std::int16_t));
  const std::uint16_t channels = 1;
  const std::uint16_t bits = 16;
  const std::uint32_t byte_rate =
      static_cast<std::uint32_t>(sample_rate) * channels * (bits / 8);
  const std::uint16_t block_align = channels * (bits / 8);

  std::string out;
  out.reserve(44 + data_bytes);
  out.append("RIFF", 4);
  write_le32(out, 36 + data_bytes);
  out.append("WAVE", 4);
  out.append("fmt ", 4);
  write_le32(out, 16);  // PCM fmt chunk size
  write_le16(out, 1);   // PCM
  write_le16(out, channels);
  write_le32(out, static_cast<std::uint32_t>(sample_rate));
  write_le32(out, byte_rate);
  write_le16(out, block_align);
  write_le16(out, bits);
  out.append("data", 4);
  write_le32(out, data_bytes);
  out.append(reinterpret_cast<const char*>(pcm.data()), data_bytes);
  return out;
}

}  // namespace calypso
