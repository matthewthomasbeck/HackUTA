#include "backend_link.hpp"

namespace calypso {

BackendLink::~BackendLink() {
  shutdown();
}

bool BackendLink::init(const std::string& ip, std::uint16_t port) {
  ip_ = ip;
  port_ = port;
  // TODO: allocate websocket / socket resources
  connected_ = false;
  return true;
}

bool BackendLink::connect() {
  // TODO: dial BACKEND_IP:BACKEND_PORT, upgrade to websocket if used
  connected_ = false;
  return connected_;
}

bool BackendLink::is_connected() const {
  return connected_;
}

bool BackendLink::send_audio_chunk(const AudioChunk& /*chunk*/) {
  if (!connected_) {
    return false;
  }
  // TODO: frame + send PCM / binary message
  return false;
}

void BackendLink::disconnect() {
  // TODO: close session, keep init state for reconnect
  connected_ = false;
}

void BackendLink::shutdown() {
  disconnect();
  // TODO: free socket resources
}

}  // namespace calypso
