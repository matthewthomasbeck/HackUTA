#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// NCS2 + local STT / voice-fingerprint models. Offline path only for now.
class Models {
 public:
  Models() = default;
  ~Models();

  Models(const Models&) = delete;
  Models& operator=(const Models&) = delete;

  // Start NCS2, load STT + voice-fingerprint graphs. Vague on purpose.
  bool init(const std::string& ncs2_device,
            const std::string& stt_model_path,
            const std::string& voice_model_path);

  // Run chunk through loaded models. Output unused until offline brainstorm.
  bool infer(const AudioChunk& chunk, ModelOutput& out);

  void shutdown();

 private:
  bool ready_ = false;
  // TODO: OpenVINO / NCS2 handles
};

}  // namespace calypso
