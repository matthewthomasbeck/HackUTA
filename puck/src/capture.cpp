#include "capture.hpp"

#include "audio_gain.hpp"

#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>
#include <thread>
#include <vector>

#if defined(CALYPSO_HAS_ALSA)
#include <alsa/asoundlib.h>
#endif

namespace calypso {
namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kSineHz = 440.0;

}  // namespace

Capture::~Capture() {
  shutdown();
}

bool Capture::init(const std::string& mic_device, int chunk_ms) {
  shutdown();
  chunk_ms_ = chunk_ms > 0 ? chunk_ms : 30;
  sine_phase_ = 0;

  if (mic_device == "sine") {
    sine_ = true;
    open_ = true;
    std::cerr << "capture: sine test source @ " << kSampleRate << " Hz, "
              << chunk_ms_ << " ms frames\n";
    return true;
  }

#if defined(CALYPSO_HAS_ALSA)
  snd_pcm_t* handle = nullptr;
  int err = snd_pcm_open(&handle, mic_device.c_str(), SND_PCM_STREAM_CAPTURE, 0);
  if (err < 0) {
    std::cerr << "capture: snd_pcm_open(" << mic_device
              << ") failed: " << snd_strerror(err) << "\n";
    return false;
  }
  err = snd_pcm_set_params(handle, SND_PCM_FORMAT_S16_LE,
                           SND_PCM_ACCESS_RW_INTERLEAVED,
                           /*channels=*/1, kSampleRate,
                           /*allow_resample=*/1,
                           /*latency_us=*/500000);
  if (err < 0) {
    std::cerr << "capture: snd_pcm_set_params failed: " << snd_strerror(err)
              << "\n";
    snd_pcm_close(handle);
    return false;
  }
  pcm_ = handle;
  sine_ = false;
  open_ = true;
  std::cerr << "capture: ALSA " << mic_device << " @ " << kSampleRate << " Hz, "
            << chunk_ms_ << " ms frames\n";
  return true;
#else
  std::cerr << "capture: ALSA not built; use MIC_DEVICE=sine for test tone\n";
  return false;
#endif
}

bool Capture::read_chunk(AudioChunk& out) {
  if (!open_) {
    return false;
  }

  const int frames = kSampleRate * chunk_ms_ / 1000;
  if (frames <= 0) {
    return false;
  }

  out = {};
  out.duration_ms = chunk_ms_;
  out.ts = std::chrono::system_clock::now();
  out.pcm.resize(static_cast<std::size_t>(frames));

  if (sine_) {
    for (int i = 0; i < frames; ++i) {
      const double t = static_cast<double>(sine_phase_++) / kSampleRate;
      const double s = std::sin(2.0 * kPi * kSineHz * t);
      out.pcm[static_cast<std::size_t>(i)] =
          static_cast<std::int16_t>(s * 0.2 * 32767.0);
    }
    apply_gain(out.pcm, gain_);
    // Pace like a real mic so we don't flood the backend.
    std::this_thread::sleep_for(std::chrono::milliseconds(chunk_ms_));
    return true;
  }

#if defined(CALYPSO_HAS_ALSA)
  auto* handle = static_cast<snd_pcm_t*>(pcm_);
  snd_pcm_sframes_t got =
      snd_pcm_readi(handle, out.pcm.data(), static_cast<snd_pcm_uframes_t>(frames));
  if (got == -EPIPE) {
    snd_pcm_prepare(handle);
    return false;
  }
  if (got < 0) {
    std::cerr << "capture: read error: " << snd_strerror(static_cast<int>(got))
              << "\n";
    return false;
  }
  if (got != frames) {
    out.pcm.resize(static_cast<std::size_t>(got));
    out.duration_ms = static_cast<int>(got * 1000 / kSampleRate);
  }
  apply_gain(out.pcm, gain_);
  return true;
#else
  return false;
#endif
}

void Capture::shutdown() {
#if defined(CALYPSO_HAS_ALSA)
  if (pcm_) {
    snd_pcm_close(static_cast<snd_pcm_t*>(pcm_));
    pcm_ = nullptr;
  }
#endif
  open_ = false;
  sine_ = false;
}

}  // namespace calypso
