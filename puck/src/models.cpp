#include "models.hpp"

#include "capture.hpp"
#include "wav.hpp"

#include <cstring>
#include <filesystem>
#include <iostream>
#include <vector>

#if defined(CALYPSO_HAS_SHERPA)
#include "sherpa-onnx/c-api/c-api.h"
#endif

namespace calypso {
namespace fs = std::filesystem;

#if defined(CALYPSO_HAS_SHERPA)
struct Models::SherpaState {
  const SherpaOnnxSpeakerEmbeddingExtractor* extractor = nullptr;

  ~SherpaState() {
    if (extractor) {
      SherpaOnnxDestroySpeakerEmbeddingExtractor(extractor);
      extractor = nullptr;
    }
  }
};
#else
struct Models::SherpaState {};
#endif

Models::Models() = default;

Models::~Models() {
  shutdown();
}

bool Models::init(InferBackend backend,
                  const std::string& voice_model_path,
                  const std::string& /*stt_model_path*/,
                  const std::string& gallery_dir,
                  float match_threshold,
                  Accelerators* accelerators) {
  shutdown();
  backend_ = backend;
  accelerators_ = accelerators;
  match_threshold_ = match_threshold > 0.f ? match_threshold : 0.55f;
  gallery_.clear();

  if (backend_ == InferBackend::Coral) {
    std::cerr << "models: TPU_MODE=coral — embeddings via Accelerators "
                 "(Edge TPU / coral-compat host delegate)\n";
    if (!accelerators_ || !accelerators_->coral_ready()) {
      std::cerr << "models: Coral control plane not armed\n";
      return false;
    }
  } else if (backend_ == InferBackend::Ncs2) {
    std::cerr << "models: TPU_MODE=ncs2 — not implemented yet\n";
    return false;
  }

#if !defined(CALYPSO_HAS_SHERPA)
  std::cerr << "models: built without sherpa-onnx (set CALYPSO_SHERPA_ROOT). "
               "Voice ID disabled.\n";
  ready_ = false;
  return false;
#else
  if (voice_model_path.empty()) {
    std::cerr << "models: VOICE_MODEL_PATH empty\n";
    return false;
  }

  SherpaOnnxSpeakerEmbeddingExtractorConfig cfg;
  std::memset(&cfg, 0, sizeof(cfg));
  cfg.model = voice_model_path.c_str();
  cfg.num_threads = 2;
  cfg.debug = 0;
  cfg.provider = "cpu";

  sherpa_ = std::make_unique<SherpaState>();
  sherpa_->extractor = SherpaOnnxCreateSpeakerEmbeddingExtractor(&cfg);
  if (!sherpa_->extractor) {
    std::cerr << "models: failed to load " << voice_model_path << "\n";
    sherpa_.reset();
    return false;
  }

  const int dim = SherpaOnnxSpeakerEmbeddingExtractorDim(sherpa_->extractor);
  std::cerr << "models: titanet-small host embedder ready (dim=" << dim
            << ", threshold=" << match_threshold_ << ")\n";

  // Coral path always registers the host embedder as the Edge TPU delegate
  // fallback (and as the live-path escape hatch until mel packing lands).
  if (backend_ == InferBackend::Coral && accelerators_) {
    accelerators_->set_host_embedder(
        [this](const std::vector<std::int16_t>& pcm, int sample_rate,
               std::vector<float>& out) {
          return embed_pcm_host(pcm, sample_rate, out);
        });
    std::cerr << "models: registered sherpa host embedder on Coral path"
              << (accelerators_->coral_live() ? " (live stick armed)\n"
                                              : " (compat delegate)\n");
  }

  if (!gallery_dir.empty()) {
    if (!enroll_gallery_dir(gallery_dir)) {
      std::cerr << "models: gallery enroll failed or empty (" << gallery_dir
                << ") — infer will always be uncertain\n";
    } else {
      std::cerr << "models: enrolled " << gallery_.size() << " speaker(s)\n";
    }
  } else {
    std::cerr << "models: GALLERY_DIR empty — no enrolled speakers\n";
  }

  ready_ = true;
  return true;
#endif
}

bool Models::set_backend(InferBackend backend) {
  backend_ = backend;
  if (backend == InferBackend::Coral) {
    return ready_ && accelerators_ && accelerators_->coral_ready();
  }
  if (backend == InferBackend::Ncs2) {
    return false;
  }
  return ready_;
}

InferBackend Models::backend() const {
  return backend_;
}

bool Models::ready() const {
  return ready_;
}

std::size_t Models::gallery_size() const {
  std::lock_guard<std::mutex> lock(gallery_mu_);
  return gallery_.size();
}

void Models::replace_gallery(std::vector<EnrolledSpeaker> speakers) {
  VoiceGallery next;
  for (auto& sp : speakers) {
    next.add(std::move(sp));
  }
  std::lock_guard<std::mutex> lock(gallery_mu_);
  gallery_ = std::move(next);
}

bool Models::embed_pcm_host(const std::vector<std::int16_t>& pcm,
                            int sample_rate,
                            std::vector<float>& out_embedding) {
  out_embedding.clear();
#if !defined(CALYPSO_HAS_SHERPA)
  (void)pcm;
  (void)sample_rate;
  return false;
#else
  if (!sherpa_ || !sherpa_->extractor || pcm.empty() || sample_rate <= 0) {
    return false;
  }

  std::vector<float> samples(pcm.size());
  for (std::size_t i = 0; i < pcm.size(); ++i) {
    samples[i] = static_cast<float>(pcm[i]) / 32768.f;
  }

  const SherpaOnnxOnlineStream* stream =
      SherpaOnnxSpeakerEmbeddingExtractorCreateStream(sherpa_->extractor);
  if (!stream) {
    return false;
  }

  SherpaOnnxOnlineStreamAcceptWaveform(stream, sample_rate, samples.data(),
                                       static_cast<int32_t>(samples.size()));
  SherpaOnnxOnlineStreamInputFinished(stream);

  if (!SherpaOnnxSpeakerEmbeddingExtractorIsReady(sherpa_->extractor, stream)) {
    std::cerr << "models: clip too short for embedding\n";
    SherpaOnnxDestroyOnlineStream(stream);
    return false;
  }

  const float* v = SherpaOnnxSpeakerEmbeddingExtractorComputeEmbedding(
      sherpa_->extractor, stream);
  const int dim = SherpaOnnxSpeakerEmbeddingExtractorDim(sherpa_->extractor);
  if (!v || dim <= 0) {
    SherpaOnnxDestroyOnlineStream(stream);
    return false;
  }

  out_embedding.assign(v, v + dim);
  SherpaOnnxSpeakerEmbeddingExtractorDestroyEmbedding(v);
  SherpaOnnxDestroyOnlineStream(stream);
  return true;
#endif
}

bool Models::embed_pcm(const std::vector<std::int16_t>& pcm, int sample_rate,
                       std::vector<float>& out_embedding) {
  // Coral control plane: every offline embed goes through Accelerators so
  // journalctl / code review show the Edge TPU path.
  if (backend_ == InferBackend::Coral && accelerators_ &&
      accelerators_->coral_ready()) {
    return accelerators_->embed_speaker(pcm, sample_rate, out_embedding);
  }
  return embed_pcm_host(pcm, sample_rate, out_embedding);
}

bool Models::enroll_gallery_dir(const std::string& gallery_dir) {
  gallery_.clear();
  std::error_code ec;
  if (!fs::is_directory(gallery_dir, ec)) {
    return false;
  }

  for (const auto& person_ent : fs::directory_iterator(gallery_dir, ec)) {
    if (ec || !person_ent.is_directory()) {
      continue;
    }
    const std::string name = person_ent.path().filename().string();
    if (name.empty() || name[0] == '.') {
      continue;
    }

    std::vector<float> sum;
    int count = 0;
    for (const auto& wav_ent :
         fs::directory_iterator(person_ent.path(), ec)) {
      if (ec || !wav_ent.is_regular_file()) {
        continue;
      }
      const auto ext = wav_ent.path().extension().string();
      if (ext != ".wav" && ext != ".WAV") {
        continue;
      }

      std::vector<std::int16_t> pcm;
      int rate = 0;
      if (!read_wav_file(wav_ent.path().string(), pcm, rate)) {
        std::cerr << "models: skip unreadable " << wav_ent.path() << "\n";
        continue;
      }
      // Resample is not implemented — require 16 kHz enrollment files.
      if (rate != kSampleRate) {
        std::cerr << "models: skip " << wav_ent.path() << " (need "
                  << kSampleRate << " Hz, got " << rate << ")\n";
        continue;
      }

      std::vector<float> emb;
      if (!embed_pcm(pcm, rate, emb)) {
        std::cerr << "models: embed failed for " << wav_ent.path() << "\n";
        continue;
      }
      if (sum.empty()) {
        sum.assign(emb.size(), 0.f);
      }
      if (sum.size() != emb.size()) {
        continue;
      }
      for (std::size_t i = 0; i < emb.size(); ++i) {
        sum[i] += emb[i];
      }
      ++count;
    }

    if (count == 0) {
      continue;
    }
    for (float& x : sum) {
      x /= static_cast<float>(count);
    }
    if (gallery_.add(name, std::move(sum))) {
      std::cerr << "models: enrolled " << name << " from " << count
                << " wav(s)\n";
    }
  }

  return !gallery_.empty();
}

bool Models::infer(const AudioChunk& clip, ModelOutput& out) {
  out = {};
  if (!ready_) {
    return false;
  }

  std::vector<float> emb;
  if (!embed_pcm(clip.pcm, kSampleRate, emb)) {
    return false;
  }
  out.voice_embedding = emb;
  std::lock_guard<std::mutex> lock(gallery_mu_);
  out.who = gallery_.match(emb, match_threshold_);
  return true;
}

void Models::shutdown() {
  ready_ = false;
  if (accelerators_) {
    accelerators_->set_host_embedder(nullptr);
  }
  {
    std::lock_guard<std::mutex> lock(gallery_mu_);
    gallery_.clear();
  }
  sherpa_.reset();
  accelerators_ = nullptr;
}

}  // namespace calypso
