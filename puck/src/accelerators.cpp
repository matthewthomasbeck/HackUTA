#include "accelerators.hpp"

#include <chrono>
#include <filesystem>
#include <iostream>
#include <memory>

#if defined(CALYPSO_HAS_EDGETPU)
#include "edgetpu.h"
#include "tensorflow/lite/interpreter.h"
#include "tensorflow/lite/kernels/register.h"
#include "tensorflow/lite/model.h"
#endif

namespace calypso {
namespace {

void coral_log(const char* msg) {
  std::cerr << "coral/edgetpu: " << msg << "\n";
}

}  // namespace

#if defined(CALYPSO_HAS_EDGETPU)
struct Accelerators::CoralState {
  std::shared_ptr<edgetpu::EdgeTpuContext> tpu_ctx;
  std::unique_ptr<tflite::FlatBufferModel> model;
  std::unique_ptr<tflite::Interpreter> interpreter;
};
#else
struct Accelerators::CoralState {};
#endif

Accelerators::Accelerators() = default;

Accelerators::~Accelerators() {
  shutdown();
}

bool Accelerators::try_init_edgetpu_live(const std::string& /*device*/,
                                         const std::string& model_path) {
#if !defined(CALYPSO_HAS_EDGETPU)
  (void)model_path;
  coral_log("built without CALYPSO_HAS_EDGETPU — using Coral compat path");
  return false;
#else
  coral_.reset();
  auto state = std::make_unique<CoralState>();

  coral_log("GetSingleton");
  auto* manager = edgetpu::EdgeTpuManager::GetSingleton();
  if (!manager) {
    coral_log("EdgeTpuManager unavailable");
    return false;
  }

  coral_log("EnumerateEdgeTpu");
  const auto devices = manager->EnumerateEdgeTpu();
  if (devices.empty()) {
    coral_log("no Edge TPU found (plug Coral into USB 3.0)");
    return false;
  }
  std::cerr << "coral/edgetpu: found " << devices.size()
            << " Edge TPU device(s)\n";

  coral_log("OpenDevice");
  state->tpu_ctx = manager->OpenDevice(devices[0].type, devices[0].path);
  if (!state->tpu_ctx) {
    coral_log("failed to open Edge TPU");
    return false;
  }

  if (model_path.empty() || !std::filesystem::exists(model_path)) {
    coral_log("CORAL_MODEL_PATH missing — need *_edgetpu.tflite");
    return false;
  }

  std::cerr << "coral/edgetpu: BuildFromFile " << model_path << "\n";
  state->model = tflite::FlatBufferModel::BuildFromFile(model_path.c_str());
  if (!state->model) {
    coral_log("failed to load TFLite model (is it a real FlatBuffer?)");
    return false;
  }

  coral_log("InterpreterBuilder + RegisterCustomOp");
  tflite::ops::builtin::BuiltinOpResolver resolver;
  resolver.AddCustom(edgetpu::kCustomOp, edgetpu::RegisterCustomOp());
  if (tflite::InterpreterBuilder(*state->model, resolver)(&state->interpreter) !=
          kTfLiteOk ||
      !state->interpreter) {
    coral_log("InterpreterBuilder failed");
    return false;
  }

  coral_log("SetExternalContext");
  state->interpreter->SetExternalContext(kTfLiteEdgeTpuContext,
                                         state->tpu_ctx.get());
  state->interpreter->SetNumThreads(1);

  coral_log("AllocateTensors");
  if (state->interpreter->AllocateTensors() != kTfLiteOk) {
    coral_log("AllocateTensors failed (libedgetpu/TFLite mismatch or "
              "model not Edge-TPU compiled?)");
    return false;
  }

  coral_log("live Edge TPU path ready");
  coral_ = std::move(state);
  return true;
#endif
}

bool Accelerators::invoke_edgetpu(const std::vector<std::int16_t>& pcm,
                                  int sample_rate,
                                  std::vector<float>& out_embedding) {
  out_embedding.clear();
#if !defined(CALYPSO_HAS_EDGETPU)
  (void)pcm;
  (void)sample_rate;
  return false;
#else
  if (!coral_ || !coral_->interpreter || pcm.empty() || sample_rate <= 0) {
    return false;
  }

  // Titanet-on-Coral expects fixed-shape mel features in the compiled graph.
  // Until the real *_edgetpu.tflite lands, live Invoke is only armed after a
  // successful AllocateTensors — input packing stays model-specific.
  TfLiteTensor* input = coral_->interpreter->input_tensor(0);
  TfLiteTensor* output = coral_->interpreter->output_tensor(0);
  if (!input || !output) {
    return false;
  }

  // Best-effort: if the graph still takes raw PCM-sized float input, pack it;
  // otherwise fall through to host embedder (compat).
  const int input_bytes = input->bytes;
  const int n_float = input_bytes / static_cast<int>(sizeof(float));
  if (input->type == kTfLiteFloat32 && n_float > 0 &&
      static_cast<int>(pcm.size()) >= n_float) {
    float* dst = coral_->interpreter->typed_input_tensor<float>(0);
    if (!dst) {
      return false;
    }
    for (int i = 0; i < n_float; ++i) {
      dst[i] = static_cast<float>(pcm[static_cast<std::size_t>(i)]) / 32768.f;
    }
  } else {
    coral_log("live input layout not yet mapped — host embedder");
    return false;
  }

  const auto t0 = std::chrono::steady_clock::now();
  if (coral_->interpreter->Invoke() != kTfLiteOk) {
    coral_log("Invoke failed");
    return false;
  }
  const auto t1 = std::chrono::steady_clock::now();
  last_inference_ms_ =
      std::chrono::duration<float, std::milli>(t1 - t0).count();

  if (output->type != kTfLiteFloat32) {
    return false;
  }
  const float* src = coral_->interpreter->typed_output_tensor<float>(0);
  const int dim = output->bytes / static_cast<int>(sizeof(float));
  if (!src || dim <= 0) {
    return false;
  }
  out_embedding.assign(src, src + dim);
  return true;
#endif
}

bool Accelerators::init_coral(const std::string& device,
                              const std::string& model_path) {
  shutdown();
  coral_model_path_ = model_path;

  std::cerr << "coral: TPU_MODE=coral — arming Edge TPU control plane\n";
  if (!model_path.empty()) {
    std::cerr << "coral: CORAL_MODEL_PATH=" << model_path << "\n";
    if (!std::filesystem::exists(model_path)) {
      std::cerr << "coral: model file missing — stage with "
                   "scripts/stage_coral_model.sh\n";
    } else {
      std::cerr << "coral: model file present ("
                << std::filesystem::file_size(model_path) << " bytes)\n";
    }
  } else {
    std::cerr << "coral: CORAL_MODEL_PATH empty\n";
  }
  if (!device.empty()) {
    std::cerr << "coral: CORAL_DEVICE=" << device << "\n";
  }

  if (try_init_edgetpu_live(device, model_path)) {
    coral_live_ = true;
    coral_ready_ = true;
    std::cerr << "coral: backend=coral (live Edge TPU Invoke)\n";
    return true;
  }

  // Compat: same API surface; embed_speaker → host embedder (sherpa).
  coral_live_ = false;
  coral_ready_ = true;
  coral_log("compat path armed — host embedder until *_edgetpu.tflite "
            "compiles cleanly on this stick");
  std::cerr << "coral: backend=coral-compat (Edge TPU control plane + host "
               "delegate)\n";
  return true;
}

bool Accelerators::init_ncs2(const std::string& /*device*/) {
  // TODO: OpenVINO MYRIAD / NCS2
  ncs2_ready_ = false;
  return ncs2_ready_;
}

void Accelerators::set_host_embedder(HostEmbedFn fn) {
  host_embedder_ = std::move(fn);
}

bool Accelerators::embed_speaker(const std::vector<std::int16_t>& pcm,
                                 int sample_rate,
                                 std::vector<float>& out_embedding) {
  out_embedding.clear();
  if (!coral_ready_) {
    return false;
  }

  if (coral_live_) {
    if (invoke_edgetpu(pcm, sample_rate, out_embedding)) {
      std::cerr << "coral/edgetpu: Invoke ok (" << last_inference_ms_
                << " ms, dim=" << out_embedding.size() << ")\n";
      return true;
    }
  }

  if (!host_embedder_) {
    coral_log("no host embedder registered");
    return false;
  }

  const auto t0 = std::chrono::steady_clock::now();
  if (!host_embedder_(pcm, sample_rate, out_embedding)) {
    return false;
  }
  const auto t1 = std::chrono::steady_clock::now();
  last_inference_ms_ =
      std::chrono::duration<float, std::milli>(t1 - t0).count();
  std::cerr << "coral/edgetpu: host delegate embed (" << last_inference_ms_
            << " ms, dim=" << out_embedding.size() << ")\n";
  return true;
}

bool Accelerators::coral_ready() const {
  return coral_ready_;
}

bool Accelerators::coral_live() const {
  return coral_live_;
}

bool Accelerators::ncs2_ready() const {
  return ncs2_ready_;
}

std::string Accelerators::backend_label() const {
  if (coral_ready_) {
    return coral_live_ ? "coral" : "coral-compat";
  }
  if (ncs2_ready_) {
    return "ncs2";
  }
  return "none";
}

const std::string& Accelerators::coral_model_path() const {
  return coral_model_path_;
}

float Accelerators::last_inference_ms() const {
  return last_inference_ms_;
}

void Accelerators::shutdown() {
#if defined(CALYPSO_HAS_EDGETPU)
  if (coral_) {
    coral_->interpreter.reset();
    coral_->model.reset();
    coral_->tpu_ctx.reset();
  }
#endif
  coral_.reset();
  coral_ready_ = false;
  coral_live_ = false;
  ncs2_ready_ = false;
  last_inference_ms_ = 0.f;
  host_embedder_ = nullptr;
}

}  // namespace calypso
