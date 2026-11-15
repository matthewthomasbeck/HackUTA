#pragma once

#include "backend_link.hpp"
#include "capture.hpp"
#include "chunk_queue.hpp"
#include "clock_sync.hpp"
#include "models.hpp"
#include "offline_buffer.hpp"
#include "phone_link.hpp"
#include "segment_spool.hpp"
#include "segmenter.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// Capture never shares a thread with upload/infer (those block on HTTP / BT / NPU).
//
//   THREAD listen  — ALSA/sine → ChunkQueue (never waits on network)
//   THREAD worker  — BOTH modes: queue → Segmenter → SegmentSpool (durable;
//                    the Uploader thread drains it to the backend)
//                    and: queue → OfflineBuffer → Models::infer → PhoneLink (who → phone)
class StateMachine {
 public:
  StateMachine(Capture& capture, BackendLink& link, Models& models,
               PhoneLink& phone, int offline_segment_ms, SegmentSpool& spool,
               const ClockSource& clock, int segment_ms,
               float min_speech_rms = 0.02f, float voice_min_score = 0.2f);
  ~StateMachine();

  StateMachine(const StateMachine&) = delete;
  StateMachine& operator=(const StateMachine&) = delete;

  void start(RunMode initial);
  void stop();

  void set_mode(RunMode mode);
  RunMode mode() const;

 private:
  void listen_loop();
  void worker_loop();
  void spool_chunk(const AudioChunk& chunk);
  void process_who(const AudioChunk& chunk);

  Capture& capture_;
  BackendLink& link_;
  Models& models_;
  PhoneLink& phone_;
  SegmentSpool& spool_;
  Segmenter segmenter_;
  OfflineBuffer offline_buf_;
  float min_speech_rms_ = 0.02f;
  float voice_min_score_ = 0.2f;
  ChunkQueue queue_;
  std::atomic<RunMode> mode_{RunMode::Offline};
  std::atomic<bool> stop_{false};
  std::thread listen_thread_;
  std::thread worker_thread_;
};

}  // namespace calypso
