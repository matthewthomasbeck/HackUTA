#pragma once

#include "types.hpp"

#include <chrono>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

namespace calypso {

// HTTP link to Vishnu's API (not a raw websocket).
// Online path: buffer CHUNK_MS frames until SEGMENT_MS, then
// multipart POST /puck/segments (wav + meta JSON) with Bearer token.
// connect() probes GET /health; optional POST /puck/health for the dashboard.
class BackendLink {
 public:
  BackendLink() = default;
  ~BackendLink();

  BackendLink(const BackendLink&) = delete;
  BackendLink& operator=(const BackendLink&) = delete;

  bool init(const std::string& ip, std::uint16_t port, const std::string& token,
            int segment_ms);

  // GET /health — sets connected_.
  bool connect();

  bool is_connected() const;

  // Append one mic chunk; when SEGMENT_MS of audio is buffered, upload it.
  // Returns false if the upload failed (marks disconnected).
  bool send_audio_chunk(const AudioChunk& chunk);

  void disconnect();
  void shutdown();

 private:
  bool flush_locked();
  bool post_segment_locked(const std::vector<std::int16_t>& pcm,
                           std::chrono::system_clock::time_point ts_start,
                           std::chrono::system_clock::time_point ts_end);
  bool post_health_locked();
  std::string base_url() const;

  std::string ip_;
  std::uint16_t port_ = 0;
  std::string token_;
  int segment_ms_ = 3000;
  bool connected_ = false;

  mutable std::mutex mu_;
  std::vector<std::int16_t> buf_;
  std::chrono::system_clock::time_point buf_start_{};
  bool buf_has_start_ = false;
};

}  // namespace calypso
