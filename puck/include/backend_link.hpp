#pragma once

#include "types.hpp"

#include <cstdint>
#include <string>

namespace calypso {

// WebSocket (or TCP) link to the backend. Stub only — protocol TBD with Vishnu.
class BackendLink {
 public:
  BackendLink() = default;
  ~BackendLink();

  BackendLink(const BackendLink&) = delete;
  BackendLink& operator=(const BackendLink&) = delete;

  // Resolve IP:port and open the socket. Non-blocking connect OK.
  bool init(const std::string& ip, std::uint16_t port);

  // Attempt connect; returns true if the session is up.
  bool connect();

  bool is_connected() const;

  // Send one audio chunk upstream. Returns false if the socket dropped.
  bool send_audio_chunk(const AudioChunk& chunk);

  void disconnect();
  void shutdown();

 private:
  std::string ip_;
  std::uint16_t port_ = 0;
  bool connected_ = false;
  // TODO: websocket / socket fd
};

}  // namespace calypso
