#pragma once

#include "types.hpp"

#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>

namespace calypso {

// HTTP link to Vishnu's API (not a raw websocket).
// connect() probes GET /health. post_segment() is one multipart POST
// /puck/segments (wav + meta JSON, Bearer token); the spool + Uploader own
// buffering, retry and uuids. post_health() feeds the dashboard.
class BackendLink {
 public:
  BackendLink() = default;
  ~BackendLink();

  BackendLink(const BackendLink&) = delete;
  BackendLink& operator=(const BackendLink&) = delete;

  bool init(const std::string& ip, std::uint16_t port, const std::string& token);

  // GET /health — sets connected_.
  bool connect();

  bool is_connected() const;

  // Label for POST /puck/health sound_backend (e.g. "coral", "none").
  void set_sound_backend(std::string backend);

  // POST /puck/segments. Returns the HTTP status, or -1 on a transport error.
  // Updates connected_ (false on transport error / 5xx, true otherwise).
  int post_segment(const std::string& wav_bytes, const std::string& meta_json);

  // POST /puck/health. Returns true on 200.
  bool post_health(std::size_t queue_depth, bool time_synced, bool last_upload_ok);

  // GET /puck/gallery — full voice-print snapshot (Bearer token).
  // On 200, writes the response body into body_out and returns true.
  bool get_gallery(std::string& body_out);

  void disconnect();
  void shutdown();

 private:
  std::string base_url() const;

  std::string ip_;
  std::uint16_t port_ = 0;
  std::string token_;
  std::string sound_backend_ = "none";
  bool connected_ = false;

  mutable std::mutex mu_;  // guards connected_ only
};

}  // namespace calypso
