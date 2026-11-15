#include "uploader.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>

namespace calypso {
namespace fs = std::filesystem;

Uploader::Uploader(SegmentSpool& spool, PostFn post, const ClockSource& clock)
    : spool_(spool), post_(std::move(post)), clock_(clock) {}

std::chrono::milliseconds Uploader::next_backoff() {
  const auto cur = backoff_;
  backoff_ = std::min(backoff_ * 2, std::chrono::milliseconds(60000));
  return cur;
}

int Uploader::drain_once() {
  last_failed_ = false;
  correct_unsynced(spool_, clock_.now());
  int removed = 0;
  for (const auto& it : spool_.pending()) {
    std::ifstream in(it.wav_path, std::ios::binary);
    if (!in) continue;  // evicted underneath us
    std::ostringstream ss;
    ss << in.rdbuf();
    const int status = post_(ss.str(), spool_.meta_json(it));
    if ((status >= 200 && status < 300) || status == 409) {
      spool_.remove(it);
      ++removed;
    } else if (status >= 400 && status < 500) {
      std::cerr << "uploader: rejected " << it.uuid << " http=" << status << "\n";
      const fs::path dir = it.wav_path.parent_path() / "rejected";
      std::error_code ec;
      fs::create_directories(dir, ec);
      fs::rename(it.wav_path, dir / it.wav_path.filename(), ec);
      fs::rename(it.json_path, dir / it.json_path.filename(), ec);
    } else {
      last_failed_ = true;
      break;
    }
  }
  if (!last_failed_) backoff_ = std::chrono::milliseconds(1000);
  return removed;
}

void Uploader::run(std::atomic<bool>& stop) {
  while (!stop.load()) {
    drain_once();
    const auto wait = last_failed_ ? next_backoff() : std::chrono::milliseconds(1000);
    const auto deadline = std::chrono::steady_clock::now() + wait;
    while (!stop.load() && std::chrono::steady_clock::now() < deadline) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  }
}

}  // namespace calypso
