#include "models.hpp"

namespace calypso {

Models::~Models() {
  shutdown();
}

bool Models::init(const std::string& /*ncs2_device*/,
                  const std::string& /*stt_model_path*/,
                  const std::string& /*voice_model_path*/) {
  // TODO: open NCS2, load STT + voice-fingerprint models
  ready_ = false;
  return ready_;
}

bool Models::infer(const AudioChunk& /*chunk*/, ModelOutput& out) {
  out = {};
  if (!ready_) {
    return false;
  }
  // TODO: push chunk through models; fill transcript + embedding
  return false;
}

void Models::shutdown() {
  // TODO: release NCS2 / model handles
  ready_ = false;
}

}  // namespace calypso
