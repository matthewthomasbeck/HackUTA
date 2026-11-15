#include "models.hpp"

namespace calypso {

Models::~Models() {
  shutdown();
}

bool Models::init(InferBackend backend,
                  const std::string& /*voice_model_path*/,
                  const std::string& /*stt_model_path*/,
                  Accelerators* accelerators) {
  // TODO: load titanet/sherpa on CPU; optionally bind Coral/NCS2 graphs
  backend_ = backend;
  accelerators_ = accelerators;
  ready_ = false;
  return ready_;
}

bool Models::set_backend(InferBackend backend) {
  // TODO: swap CPU ↔ Coral ↔ NCS2 session; keep same ModelOutput contract
  backend_ = backend;
  return false;
}

InferBackend Models::backend() const {
  return backend_;
}

bool Models::ready() const {
  return ready_;
}

bool Models::infer(const AudioChunk& /*clip*/, ModelOutput& out) {
  out = {};
  if (!ready_) {
    return false;
  }
  // TODO: embed clip → match local gallery → fill out.who (+ embedding)
  return false;
}

void Models::shutdown() {
  // TODO: release model sessions
  ready_ = false;
  accelerators_ = nullptr;
}

}  // namespace calypso
