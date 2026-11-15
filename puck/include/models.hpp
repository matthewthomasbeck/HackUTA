#pragma once

#include "accelerators.hpp"
#include "types.hpp"
#include "voice_gallery.hpp"

#include <mutex>
#include <memory>
#include <string>
#include <vector>

namespace calypso {

// Offline voice fingerprint with nemo_en_titanet_small (192-d) via sherpa-onnx.
// Build with -DCALYPSO_SHERPA_ROOT=... to enable real inference; otherwise init
// fails closed and offline infer no-ops.
class Models {
 public:
  Models();
  ~Models();

  Models(const Models&) = delete;
  Models& operator=(const Models&) = delete;

  // Load Titanet ONNX, enroll GALLERY_DIR/<Name>/*.wav (bootstrap until the
  // first successful cloud gallery sync), keep Accelerators for a future TPU
  // swap (ignored on CPU MVP).
  bool init(InferBackend backend,
            const std::string& voice_model_path,
            const std::string& stt_model_path,
            const std::string& gallery_dir,
            float match_threshold,
            Accelerators* accelerators);

  bool set_backend(InferBackend backend);
  InferBackend backend() const;
  bool ready() const;
  std::size_t gallery_size() const;

  // Replace-all from GET /puck/gallery. Empty list clears local speakers
  // (cloud deleted everyone). Thread-safe vs infer().
  void replace_gallery(std::vector<EnrolledSpeaker> speakers);

  // Embed clip → match gallery → fill out.who (+ out.voice_embedding).
  bool infer(const AudioChunk& clip, ModelOutput& out);

  void shutdown();

 private:
  struct SherpaState;  // only defined when CALYPSO_HAS_SHERPA

  bool embed_pcm(const std::vector<std::int16_t>& pcm, int sample_rate,
                 std::vector<float>& out_embedding);
  bool enroll_gallery_dir(const std::string& gallery_dir);

  bool ready_ = false;
  InferBackend backend_ = InferBackend::Cpu;
  Accelerators* accelerators_ = nullptr;
  float match_threshold_ = 0.55f;
  VoiceGallery gallery_;
  mutable std::mutex gallery_mu_;
  std::unique_ptr<SherpaState> sherpa_;
};

}  // namespace calypso
