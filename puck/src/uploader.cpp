#include "uploader.hpp"

#include <algorithm>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>
#include <vector>

namespace calypso {
namespace fs = std::filesystem;

Uploader::Uploader(SegmentSpool& spool, PostFn post, const ClockSource& clock)
    : spool_(spool), post_(std::move(post)), clock_(clock) {
  const fs::path dir = spool_.dir() / "rejected";
  std::error_code ec;
  if (fs::is_directory(dir, ec)) rejected_.store(prune_rejected(dir, kMaxRejected));
}

std::chrono::milliseconds Uploader::next_backoff() {
  const auto cur = backoff_;
  backoff_ = std::min(backoff_ * 2, std::chrono::milliseconds(60000));
  return cur;
}

namespace {
// Pause the whole pass on these: the server or our credentials are the
// problem, not the item (a wrong API_TOKEN must not discard a day of audio).
bool transient(int status) {
  return status < 0 || status >= 500 || status == 401 || status == 403 ||
         status == 408 || status == 429;
}
}  // namespace

std::size_t prune_rejected(const fs::path& dir, std::size_t max_items) {
  std::error_code ec;
  std::vector<fs::path> metas;
  for (fs::directory_iterator d(dir, ec), end; !ec && d != end; d.increment(ec)) {
    if (d->path().extension() == ".json") metas.push_back(d->path());
  }
  std::sort(metas.begin(), metas.end());  // <ts>_<uuid>: oldest first
  std::size_t drop = metas.size() > max_items ? metas.size() - max_items : 0;
  for (std::size_t i = 0; i < drop; ++i) {
    fs::path wav = metas[i];
    wav.replace_extension(".wav");
    fs::remove(wav, ec);
    fs::remove(metas[i], ec);
  }
  return metas.size() - drop;
}

int Uploader::drain_once() {
  last_failed_ = false;
  const ClockSnapshot now = clock_.now();
  correct_unsynced(spool_, now);
  int removed = 0;
  for (const auto& it : spool_.pending()) {
    // Same-boot unsynced items are corrected once NTP syncs; hold them until
    // then. Only items from an earlier boot go up with time_synced=false.
    if (!it.time_synced && it.boot_id == now.boot_id && !now.synced) continue;
    std::ifstream in(it.wav_path, std::ios::binary);
    if (!in) continue;  // evicted underneath us
    std::ostringstream ss;
    ss << in.rdbuf();
    const int status = post_(ss.str(), spool_.meta_json(it));
    if ((status >= 200 && status < 300) || status == 409) {
      spool_.remove(it);
      ++removed;
    } else if (transient(status)) {
      if (status > 0) std::cerr << "uploader: http=" << status << ", pausing uploads\n";
      last_failed_ = true;
      break;
    } else {
      std::cerr << "uploader: rejected " << it.uuid << " http=" << status << "\n";
      const fs::path dir = it.wav_path.parent_path() / "rejected";
      std::error_code ec;
      fs::create_directories(dir, ec);
      fs::rename(it.wav_path, dir / it.wav_path.filename(), ec);
      fs::rename(it.json_path, dir / it.json_path.filename(), ec);
      rejected_.store(prune_rejected(dir, kMaxRejected));
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
