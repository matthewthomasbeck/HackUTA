#pragma once

#include "accelerators.hpp"
#include "types.hpp"

#include <string>

namespace calypso {

// Offline voice-fingerprint (+ optional local STT). Default backend = CPU
// (sherpa-onnx / titanet). Swap to Coral/NCS2 via set_backend when ready.
class Models {
 public:
  Models() = default;
  ~Models();

  Models(const Models&) = delete;
  Models& operator=(const Models&) = delete;

  // Load voice (+ optional STT) graphs. Pass Accelerators for TPU later.
  bool init(InferBackend backend,
            const std::string& voice_model_path,
            const std::string& stt_model_path,
            Accelerators* accelerators);

  // Switch runtime without changing the online upload path. Stub no-op.
  bool set_backend(InferBackend backend);

  InferBackend backend() const;
  bool ready() const;

  // Run voice fingerprint on a (already concatenated) offline clip.
  // Fills out.who ("who is talking") + optional embedding/transcript.
  bool infer(const AudioChunk& clip, ModelOutput& out);

  void shutdown();

 private:
  bool ready_ = false;
  InferBackend backend_ = InferBackend::Cpu;
  Accelerators* accelerators_ = nullptr;
  // TODO: sherpa-onnx / ONNX Runtime / TPU session handles
};

}  // namespace calypso
