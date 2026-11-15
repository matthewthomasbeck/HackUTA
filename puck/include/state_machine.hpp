#pragma once

#include "backend_link.hpp"
#include "capture.hpp"
#include "chunk_queue.hpp"
#include "models.hpp"
#include "types.hpp"

#include <atomic>
#include <thread>

namespace calypso {

// Capture never shares a thread with upload/infer (those block on HTTP / NCS2).
//
//   THREAD listen  — ALSA/sine → ChunkQueue (never waits on network)
//   THREAD worker  — Online: queue → BackendLink
//                    Offline: queue → Models::infer
class StateMachine {
 public:
  StateMachine(Capture& capture, BackendLink& link, Models& models);
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
  void process_online(const AudioChunk& chunk);
  void process_offline(const AudioChunk& chunk);

  Capture& capture_;
  BackendLink& link_;
  Models& models_;
  ChunkQueue queue_;
  std::atomic<RunMode> mode_{RunMode::Offline};
  std::atomic<bool> stop_{false};
  std::thread listen_thread_;
  std::thread worker_thread_;
};

}  // namespace calypso
