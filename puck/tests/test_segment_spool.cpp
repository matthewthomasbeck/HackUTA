#include <filesystem>
#include <fstream>

#include "segment_spool.hpp"
#include "test_main.hpp"
#include "util.hpp"

using namespace calypso;
namespace fs = std::filesystem;

namespace {
fs::path fresh_dir() {
  const fs::path d = fs::temp_directory_path() / ("spool_test_" + make_segment_uuid());
  fs::create_directories(d);
  return d;
}
std::vector<std::int16_t> pcm(std::size_t n = 1600) { return std::vector<std::int16_t>(n, 7); }
SpoolItem meta(const std::string& start, bool synced = true) {
  SpoolItem m;
  m.uuid = make_segment_uuid();
  m.ts_start_iso = "2026-11-15T" + start + ".000Z";
  m.ts_end_iso = "2026-11-15T" + start + ".900Z";
  m.time_synced = synced;
  m.boot_id = "boot-abc";
  m.boot_ms_start = 1000;
  m.boot_ms_end = 1900;
  return m;
}
}  // namespace

TEST(test_enqueue_then_pending_roundtrip) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  auto m = meta("10:00:00");
  s.enqueue(pcm(), m);
  auto p = s.pending();
  CHECK_EQ(p.size(), 1u);
  CHECK_EQ(p[0].uuid, m.uuid);
  CHECK_EQ(p[0].ts_start_iso, m.ts_start_iso);
  CHECK_EQ(p[0].ts_end_iso, m.ts_end_iso);
  CHECK(p[0].time_synced);
  const auto j = s.meta_json(p[0]);
  CHECK(j.find("\"segment_uuid\":\"" + m.uuid + "\"") != std::string::npos);
  CHECK(j.find("\"time_synced\":true") != std::string::npos);
  CHECK(j.find("boot_id") == std::string::npos);
  CHECK(j.find("boot_ms") == std::string::npos);
}

TEST(test_uuid_stable_across_reopen) {
  auto d = fresh_dir();
  std::string uuid;
  {
    SegmentSpool s(d, 1 << 20);
    uuid = s.enqueue(pcm(), meta("10:00:00", false)).uuid;
  }
  SegmentSpool s2(d, 1 << 20);
  auto p = s2.pending();
  CHECK_EQ(p.size(), 1u);
  CHECK_EQ(p[0].uuid, uuid);
  CHECK(!p[0].time_synced);
  CHECK_EQ(p[0].boot_id, std::string("boot-abc"));
  CHECK_EQ(p[0].boot_ms_start, 1000);
}

TEST(test_pending_oldest_first) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), meta("10:00:06"));
  s.enqueue(pcm(), meta("10:00:00"));
  s.enqueue(pcm(), meta("10:00:03"));
  auto p = s.pending();
  CHECK_EQ(p.size(), 3u);
  CHECK(p[0].ts_start_iso.find("10:00:00") != std::string::npos);
  CHECK(p[1].ts_start_iso.find("10:00:03") != std::string::npos);
  CHECK(p[2].ts_start_iso.find("10:00:06") != std::string::npos);
}

TEST(test_rescan_ignores_tmp_and_orphans) {
  auto d = fresh_dir();
  std::ofstream(d / "x.wav.tmp") << "junk";
  std::ofstream(d / "y.wav") << "junk";
  std::ofstream(d / "z.json") << "{}";
  SegmentSpool s(d, 1 << 20);
  CHECK_EQ(s.pending().size(), 0u);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_cap_evicts_oldest) {
  auto d = fresh_dir();
  SegmentSpool probe(d, 1 << 20);
  auto it = probe.enqueue(pcm(), meta("09:00:00"));
  const auto one = fs::file_size(it.wav_path) + fs::file_size(it.json_path);
  probe.remove(it);
  SegmentSpool s(d, one * 2 + one / 2);
  s.enqueue(pcm(), meta("10:00:00"));
  s.enqueue(pcm(), meta("10:00:03"));
  s.enqueue(pcm(), meta("10:00:06"));
  auto p = s.pending();
  CHECK_EQ(p.size(), 2u);
  CHECK(p[0].ts_start_iso.find("10:00:03") != std::string::npos);
  CHECK(p[1].ts_start_iso.find("10:00:06") != std::string::npos);
  CHECK_EQ(s.evicted_count(), 1u);
}

TEST(test_rewrite_times_marks_synced) {
  auto d = fresh_dir();
  {
    SegmentSpool s(d, 1 << 20);
    auto it = s.enqueue(pcm(), meta("10:00:00", false));
    s.rewrite_times(it, "2026-11-15T11:11:11.000Z", "2026-11-15T11:11:12.000Z");
  }
  SegmentSpool s2(d, 1 << 20);
  auto p = s2.pending();
  CHECK_EQ(p.size(), 1u);
  CHECK(p[0].time_synced);
  CHECK_EQ(p[0].ts_start_iso, std::string("2026-11-15T11:11:11.000Z"));
  CHECK_EQ(p[0].ts_end_iso, std::string("2026-11-15T11:11:12.000Z"));
}

TEST(test_remove_deletes_both_files) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  auto it = s.enqueue(pcm(), meta("10:00:00"));
  CHECK(fs::exists(it.wav_path) && fs::exists(it.json_path));
  s.remove(it);
  CHECK(!fs::exists(it.wav_path));
  CHECK(!fs::exists(it.json_path));
  CHECK_EQ(s.depth(), 0u);
}

int main() { return testing::run_all(); }
