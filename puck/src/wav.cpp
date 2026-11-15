#include "wav.hpp"

#include <cstring>
#include <fstream>

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

namespace {

std::uint16_t read_le16(const char* p) {
  return static_cast<std::uint16_t>(static_cast<unsigned char>(p[0])) |
         (static_cast<std::uint16_t>(static_cast<unsigned char>(p[1])) << 8);
}

std::uint32_t read_le32(const char* p) {
  return static_cast<std::uint32_t>(static_cast<unsigned char>(p[0])) |
         (static_cast<std::uint32_t>(static_cast<unsigned char>(p[1])) << 8) |
         (static_cast<std::uint32_t>(static_cast<unsigned char>(p[2])) << 16) |
         (static_cast<std::uint32_t>(static_cast<unsigned char>(p[3])) << 24);
}

}  // namespace

bool read_wav_file(const std::string& path, std::vector<std::int16_t>& pcm,
                   int& sample_rate) {
  pcm.clear();
  sample_rate = 0;
  std::ifstream in(path, std::ios::binary);
  if (!in) {
    return false;
  }
  in.seekg(0, std::ios::end);
  const auto sz = static_cast<std::size_t>(in.tellg());
  in.seekg(0, std::ios::beg);
  if (sz < 44) {
    return false;
  }
  std::string buf(sz, '\0');
  in.read(buf.data(), static_cast<std::streamsize>(sz));
  if (!in) {
    return false;
  }
  if (std::memcmp(buf.data(), "RIFF", 4) != 0 ||
      std::memcmp(buf.data() + 8, "WAVE", 4) != 0) {
    return false;
  }

  std::uint16_t audio_format = 0;
  std::uint16_t channels = 0;
  std::uint16_t bits = 0;
  std::uint32_t rate = 0;
  const char* data_ptr = nullptr;
  std::uint32_t data_bytes = 0;

  std::size_t off = 12;
  while (off + 8 <= buf.size()) {
    const char* id = buf.data() + off;
    const std::uint32_t chunk_sz = read_le32(buf.data() + off + 4);
    const std::size_t payload = off + 8;
    if (payload + chunk_sz > buf.size()) {
      break;
    }
    if (std::memcmp(id, "fmt ", 4) == 0 && chunk_sz >= 16) {
      audio_format = read_le16(buf.data() + payload);
      channels = read_le16(buf.data() + payload + 2);
      rate = read_le32(buf.data() + payload + 4);
      bits = read_le16(buf.data() + payload + 14);
    } else if (std::memcmp(id, "data", 4) == 0) {
      data_ptr = buf.data() + payload;
      data_bytes = chunk_sz;
      break;
    }
    off = payload + chunk_sz + (chunk_sz & 1u);
  }

  if (audio_format != 1 || channels < 1 || bits != 16 || rate == 0 ||
      !data_ptr || data_bytes < 2) {
    return false;
  }

  const std::size_t n_samples = data_bytes / sizeof(std::int16_t);
  const std::int16_t* samples =
      reinterpret_cast<const std::int16_t*>(data_ptr);
  pcm.reserve(n_samples / channels);
  for (std::size_t i = 0; i + channels <= n_samples; i += channels) {
    pcm.push_back(samples[i]);  // first channel only
  }
  sample_rate = static_cast<int>(rate);
  return !pcm.empty();
}

}  // namespace calypso

