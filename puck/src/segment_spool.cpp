#include "segment_spool.hpp"

#include <fcntl.h>
#include <unistd.h>

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>

#include "util.hpp"
#include "wav.hpp"

namespace calypso {
namespace fs = std::filesystem;

namespace {

constexpr int kSampleRate = 16000;

std::string json_escape(const std::string& s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') {
      o.push_back('\\');
      o.push_back(c);
    } else if (static_cast<unsigned char>(c) < 0x20) {
      o.push_back(' ');
    } else {
      o.push_back(c);
    }
  }
  return o;
}

// 2026-11-14T15:30:00.123Z -> 20261114T153000123Z
std::string compact_ts(const std::string& iso) {
  std::string o;
  for (char c : iso) {
    if (c != '-' && c != ':' && c != '.') o.push_back(c);
  }
  return o;
}

std::size_t find_value(const std::string& j, const std::string& key) {
  const std::string needle = "\"" + key + "\":";
  const auto p = j.find(needle);
  return p == std::string::npos ? p : p + needle.size();
}

std::string get_str(const std::string& j, const std::string& key) {
  auto p = find_value(j, key);
  if (p == std::string::npos || p >= j.size() || j[p] != '"') return "";
  ++p;
  std::string o;
  while (p < j.size() && j[p] != '"') {
    if (j[p] == '\\' && p + 1 < j.size()) ++p;
    o.push_back(j[p++]);
  }
  return o;
}

bool get_bool(const std::string& j, const std::string& key, bool dflt) {
  const auto p = find_value(j, key);
  if (p == std::string::npos) return dflt;
  return j.compare(p, 4, "true") == 0;
}

std::int64_t get_int(const std::string& j, const std::string& key) {
  const auto p = find_value(j, key);
  if (p == std::string::npos) return 0;
  try {
    return std::stoll(j.substr(p));
  } catch (...) {
    return 0;
  }
}

void write_atomic(const fs::path& final_path, const std::string& data) {
  const fs::path tmp = final_path.string() + ".tmp";
  const int fd = ::open(tmp.c_str(), O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (fd < 0) throw std::runtime_error("spool: cannot open " + tmp.string());
  std::size_t off = 0;
  while (off < data.size()) {
    const ssize_t n = ::write(fd, data.data() + off, data.size() - off);
    if (n < 0) {
      ::close(fd);
      throw std::runtime_error("spool: write failed " + tmp.string());
    }
    off += static_cast<std::size_t>(n);
  }
  if (::fsync(fd) != 0) {
    ::close(fd);
    throw std::runtime_error("spool: fsync failed " + tmp.string());
  }
  ::close(fd);
  fs::rename(tmp, final_path);
  // Persist the rename itself (the directory entry) across power loss.
  const int dfd = ::open(final_path.parent_path().c_str(), O_RDONLY);
  if (dfd >= 0) {
    ::fsync(dfd);  // best effort: some filesystems refuse fsync on a directory
    ::close(dfd);
  }
}

std::string read_file(const fs::path& p) {
  std::ifstream in(p, std::ios::binary);
  std::ostringstream ss;
  ss << in.rdbuf();
  return ss.str();
}

std::string item_json(const SpoolItem& it) {
  std::ostringstream o;
  o << "{\"segment_uuid\":\"" << json_escape(it.uuid) << "\",\"ts_start\":\""
    << json_escape(it.ts_start_iso) << "\",\"ts_end\":\""
    << json_escape(it.ts_end_iso)
    << "\",\"sound_tags\":[],\"local_text\":null,\"time_synced\":"
    << (it.time_synced ? "true" : "false");
  return o.str();
}

std::uint64_t file_size_or_0(const fs::path& p) {
  std::error_code ec;
  const auto s = fs::file_size(p, ec);
  return ec ? 0 : static_cast<std::uint64_t>(s);
}

}  // namespace

SegmentSpool::SegmentSpool(fs::path dir, std::uint64_t max_bytes)
    : dir_(std::move(dir)), max_bytes_(max_bytes) {
  fs::create_directories(dir_);
}

std::string SegmentSpool::meta_json(const SpoolItem& item) const {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  return item_json(item) + "}";
}

SpoolItem SegmentSpool::enqueue(const std::vector<std::int16_t>& pcm,
                                SpoolItem meta) {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  if (meta.uuid.empty()) meta.uuid = make_segment_uuid();
  const std::string stem = compact_ts(meta.ts_start_iso) + "_" + meta.uuid;
  meta.wav_path = dir_ / (stem + ".wav");
  meta.json_path = dir_ / (stem + ".json");

  const std::string wav = pcm16_to_wav(pcm, kSampleRate);
  std::string js = item_json(meta);
  js += ",\"_local\":{\"boot_id\":\"" + json_escape(meta.boot_id) +
        "\",\"boot_ms_start\":" + std::to_string(meta.boot_ms_start) +
        ",\"boot_ms_end\":" + std::to_string(meta.boot_ms_end) + "}}";

  // Evict oldest until the new item fits (never evict the new item itself).
  const std::uint64_t need = wav.size() + js.size();
  auto items = pending();
  std::uint64_t total = 0;
  for (const auto& it : items)
    total += file_size_or_0(it.wav_path) + file_size_or_0(it.json_path);
  std::size_t i = 0;
  while (total + need > max_bytes_ && i < items.size()) {
    total -= file_size_or_0(items[i].wav_path) + file_size_or_0(items[i].json_path);
    remove(items[i]);
    ++evicted_;
    ++i;
  }

  write_atomic(meta.wav_path, wav);
  write_atomic(meta.json_path, js);  // commit marker
  return meta;
}

std::vector<SpoolItem> SegmentSpool::pending() const {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  std::vector<SpoolItem> out;
  std::error_code ec;
  for (const auto& e : fs::directory_iterator(dir_, ec)) {
    if (!e.is_regular_file() || e.path().extension() != ".json") continue;
    fs::path wav = e.path();
    wav.replace_extension(".wav");
    if (!fs::exists(wav)) continue;
    const std::string j = read_file(e.path());
    SpoolItem it;
    it.uuid = get_str(j, "segment_uuid");
    if (it.uuid.empty()) continue;
    it.ts_start_iso = get_str(j, "ts_start");
    it.ts_end_iso = get_str(j, "ts_end");
    it.time_synced = get_bool(j, "time_synced", true);
    it.boot_id = get_str(j, "boot_id");
    it.boot_ms_start = get_int(j, "boot_ms_start");
    it.boot_ms_end = get_int(j, "boot_ms_end");
    it.wav_path = wav;
    it.json_path = e.path();
    out.push_back(std::move(it));
  }
  std::sort(out.begin(), out.end(), [](const SpoolItem& a, const SpoolItem& b) {
    return a.json_path.filename() < b.json_path.filename();
  });
  return out;
}

void SegmentSpool::remove(const SpoolItem& item) {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  std::error_code ec;
  fs::remove(item.json_path, ec);  // commit marker first
  fs::remove(item.wav_path, ec);
}

void SegmentSpool::rewrite_times(const SpoolItem& item,
                                 const std::string& ts_start_iso,
                                 const std::string& ts_end_iso) {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  std::error_code ec;
  if (!fs::exists(item.json_path, ec) || !fs::exists(item.wav_path, ec)) return;  // evicted
  SpoolItem it = item;
  it.ts_start_iso = ts_start_iso;
  it.ts_end_iso = ts_end_iso;
  it.time_synced = true;
  std::string js = item_json(it);
  js += ",\"_local\":{\"boot_id\":\"" + json_escape(it.boot_id) +
        "\",\"boot_ms_start\":" + std::to_string(it.boot_ms_start) +
        ",\"boot_ms_end\":" + std::to_string(it.boot_ms_end) + "}}";
  try {
    write_atomic(item.json_path, js);
  } catch (const std::exception&) {
  }
}

std::uint64_t SegmentSpool::evicted_count() const { return evicted_.load(); }
std::size_t SegmentSpool::depth() const {
  std::lock_guard<std::recursive_mutex> lock(mu_);
  return pending().size();
}

}  // namespace calypso
