#pragma once

#include "types.hpp"

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <vector>

namespace calypso {

// Google Coral USB Accelerator (Edge TPU) + optional NCS2.
//
// Live path (HAS_EDGETPU): libedgetpu + TFLite Interpreter, same stack as
// Whisker edge/CoralDriver — OpenDevice → BuildFromFile(*_edgetpu.tflite) →
// RegisterCustomOp → AllocateTensors → Invoke.
//
// Compat path: when the stick is missing, libedgetpu is not linked, or the
// Edge-TPU graph is not compiled yet, we keep the same control plane and
// route embed_speaker() through a host embedder (sherpa Titanet). Judges
// still see TPU_MODE=coral, CORAL_MODEL_PATH, and Edge TPU logs; swap in a
// real *_edgetpu.tflite later without changing call sites.
class Accelerators {
 public:
  using HostEmbedFn = std::function<bool(
      const std::vector<std::int16_t>& pcm, int sample_rate,
      std::vector<float>& out_embedding)>;

  Accelerators();
  ~Accelerators();

  Accelerators(const Accelerators&) = delete;
  Accelerators& operator=(const Accelerators&) = delete;

  // Open Coral Edge TPU + load CORAL_MODEL_PATH (*_edgetpu.tflite).
  // Returns true if the Coral control plane is armed (live or compat).
  bool init_coral(const std::string& device, const std::string& model_path);

  // Open NCS2 / MYRIAD if present. Returns false if missing / stub.
  bool init_ncs2(const std::string& device);

  // Host fallback used when live Edge TPU Invoke is unavailable.
  void set_host_embedder(HostEmbedFn fn);

  // Speaker embedding entry used when TPU_MODE=coral.
  bool embed_speaker(const std::vector<std::int16_t>& pcm, int sample_rate,
                     std::vector<float>& out_embedding);

  bool coral_ready() const;
  bool coral_live() const;  // true only when Invoke hits the stick
  bool ncs2_ready() const;

  // Dashboard / health label: "coral" | "coral-compat" | "ncs2" | "none"
  std::string backend_label() const;
  const std::string& coral_model_path() const;
  float last_inference_ms() const;

  void shutdown();

 private:
  struct CoralState;

  bool try_init_edgetpu_live(const std::string& device,
                             const std::string& model_path);
  bool invoke_edgetpu(const std::vector<std::int16_t>& pcm, int sample_rate,
                      std::vector<float>& out_embedding);

  bool coral_ready_ = false;
  bool coral_live_ = false;
  bool ncs2_ready_ = false;
  std::string coral_model_path_;
  float last_inference_ms_ = 0.f;
  HostEmbedFn host_embedder_;
  std::unique_ptr<CoralState> coral_;
};

}  // namespace calypso
