#include <filesystem>
#include <atomic>
#include <thread>

#include "clock_sync.hpp"
#include "segment_spool.hpp"
#include "segmenter.hpp"
#include "test_main.hpp"
#include "uploader.hpp"
#include "util.hpp"

using namespace calypso;
namespace fs = std::filesystem;
using Tp = std::chrono::system_clock::time_point;

namespace {
fs::path fresh_dir() {
  const fs::path d = fs::temp_directory_path() / ("uploader_test_" + make_segment_uuid());
  fs::create_directories(d);
  return d;
}

struct FakeClock : ClockSource {
  ClockSnapshot snap;
  ClockSnapshot now() const override { return snap; }
};

Tp tp_from(const char* iso) {
  std::tm tm{};
  int ms = 0;
  std::sscanf(iso, "%d-%d-%dT%d:%d:%d.%dZ", &tm.tm_year, &tm.tm_mon, &tm.tm_mday,
              &tm.tm_hour, &tm.tm_min, &tm.tm_sec, &ms);
  tm.tm_year -= 1900;
  tm.tm_mon -= 1;
  return std::chrono::system_clock::from_time_t(timegm(&tm)) + std::chrono::milliseconds(ms);
}

std::vector<std::int16_t> pcm() { return std::vector<std::int16_t>(1600, 5); }

SpoolItem item(const std::string& start, bool synced = true, const std::string& boot = "b1",
               std::int64_t boot_ms = 0) {
  SpoolItem m;
  m.ts_start_iso = "2026-11-15T" + start + ".000Z";
  m.ts_end_iso = "2026-11-15T" + start + ".900Z";
  m.time_synced = synced;
  m.boot_id = boot;
  m.boot_ms_start = boot_ms;
  m.boot_ms_end = boot_ms + 900;
  return m;
}

ClockSnapshot synced_snap() {
  return {true, tp_from("2026-11-15T16:00:00.000Z"), 70000, "b1"};
}

std::string uuid_of(const std::string& meta) {
  const std::string k = "\"segment_uuid\":\"";
  const auto p = meta.find(k) + k.size();
  return meta.substr(p, meta.find('"', p) - p);
}
}  // namespace

TEST(test_drain_posts_oldest_first_and_removes) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:02"));
  s.enqueue(pcm(), item("10:00:00"));
  s.enqueue(pcm(), item("10:00:01"));
  FakeClock c;
  c.snap = synced_snap();
  std::vector<std::string> metas;
  Uploader u(s, [&](const std::string&, const std::string& m) { metas.push_back(m); return 200; }, c);
  CHECK_EQ(u.drain_once(), 3);
  CHECK_EQ(metas.size(), 3u);
  CHECK(metas[0].find("10:00:00") != std::string::npos);
  CHECK(metas[1].find("10:00:01") != std::string::npos);
  CHECK(metas[2].find("10:00:02") != std::string::npos);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_drain_stops_on_failure_keeps_uuid) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00"));
  s.enqueue(pcm(), item("10:00:01"));
  s.enqueue(pcm(), item("10:00:02"));
  FakeClock c;
  c.snap = synced_snap();
  int calls = 0;
  int fail_on = 2;
  std::vector<std::string> uuids;
  Uploader u(s, [&](const std::string&, const std::string& m) {
    ++calls;
    uuids.push_back(uuid_of(m));
    return calls == fail_on ? -1 : 200;
  }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK_EQ(calls, 2);
  CHECK_EQ(s.depth(), 2u);
  fail_on = -1;
  CHECK_EQ(u.drain_once(), 2);
  CHECK_EQ(uuids.size(), 4u);
  CHECK_EQ(uuids[2], uuids[1]);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_drain_deletes_on_duplicate_ack) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00"));
  FakeClock c;
  c.snap = synced_snap();
  Uploader u(s, [](const std::string&, const std::string&) { return 200; }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_rejected_4xx_moved_aside) {
  auto d = fresh_dir();
  SegmentSpool s(d, 1 << 20);
  auto bad = s.enqueue(pcm(), item("10:00:00"));
  s.enqueue(pcm(), item("10:00:01"));
  FakeClock c;
  c.snap = synced_snap();
  int calls = 0;
  Uploader u(s, [&](const std::string&, const std::string&) { return ++calls == 1 ? 422 : 200; }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK_EQ(calls, 2);
  CHECK_EQ(s.depth(), 0u);
  CHECK(fs::exists(d / "rejected" / bad.wav_path.filename()));
  CHECK(fs::exists(d / "rejected" / bad.json_path.filename()));
}

TEST(test_conflict_409_is_removed) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00"));
  FakeClock c;
  c.snap = synced_snap();
  Uploader u(s, [](const std::string&, const std::string&) { return 409; }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_5xx_stops_pass) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00"));
  s.enqueue(pcm(), item("10:00:01"));
  FakeClock c;
  c.snap = synced_snap();
  int calls = 0;
  Uploader u(s, [&](const std::string&, const std::string&) { ++calls; return 503; }, c);
  CHECK_EQ(u.drain_once(), 0);
  CHECK_EQ(calls, 1);
  CHECK_EQ(s.depth(), 2u);
}

TEST(test_correct_unsynced_same_boot) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00", false, "b1", 10000));
  FakeClock c;
  c.snap = synced_snap();
  std::string meta;
  Uploader u(s, [&](const std::string&, const std::string& m) { meta = m; return 200; }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK(meta.find("\"ts_start\":\"2026-11-15T15:59:00.000Z\"") != std::string::npos);
  CHECK(meta.find("\"ts_end\":\"2026-11-15T15:59:00.900Z\"") != std::string::npos);
  CHECK(meta.find("\"time_synced\":true") != std::string::npos);
}

TEST(test_correct_unsynced_returns_count) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00", false, "b1", 10000));
  s.enqueue(pcm(), item("10:00:01", false, "other", 10000));
  s.enqueue(pcm(), item("10:00:02", true));
  CHECK_EQ(correct_unsynced(s, synced_snap()), 1);
  ClockSnapshot unsynced = synced_snap();
  unsynced.synced = false;
  CHECK_EQ(correct_unsynced(s, unsynced), 0);
}

TEST(test_unsynced_other_boot_uploaded_unsynced) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00", false, "old-boot", 10000));
  FakeClock c;
  c.snap = synced_snap();
  std::string meta;
  Uploader u(s, [&](const std::string&, const std::string& m) { meta = m; return 200; }, c);
  CHECK_EQ(u.drain_once(), 1);
  CHECK(meta.find("\"time_synced\":false") != std::string::npos);
  CHECK(meta.find("\"ts_start\":\"2026-11-15T10:00:00.000Z\"") != std::string::npos);
}

TEST(test_backoff_doubles_and_caps) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00"));
  FakeClock c;
  c.snap = synced_snap();
  Uploader u(s, [](const std::string&, const std::string&) { return 200; }, c);
  const int expect[] = {1, 2, 4, 8, 16, 32, 60, 60};
  for (int e : expect) CHECK_EQ(u.next_backoff().count(), e * 1000);
  CHECK_EQ(u.drain_once(), 1);  // success resets
  CHECK_EQ(u.next_backoff().count(), 1000);
}

TEST(test_segmenter_assigns_ts_at_close) {
  FakeClock c;
  c.snap = {false, tp_from("2020-01-01T00:00:00.000Z"), 50000, "b1"};
  Segmenter seg(3000, c);
  const Tp t0 = tp_from("2026-11-15T12:00:00.000Z");
  std::optional<std::pair<std::vector<std::int16_t>, SpoolItem>> out;
  for (int i = 0; i < 3; ++i) {
    AudioChunk ch;
    ch.pcm.assign(16000, 1);  // 1000 ms
    ch.ts = t0 + std::chrono::seconds(i);
    ch.duration_ms = 1000;
    out = seg.push(ch);
    if (i < 2) CHECK(!out);
  }
  CHECK(out.has_value());
  CHECK_EQ(out->first.size(), 48000u);
  CHECK_EQ(out->second.ts_start_iso, std::string("2026-11-15T12:00:00.000Z"));
  CHECK_EQ(out->second.ts_end_iso, std::string("2026-11-15T12:00:03.000Z"));
  CHECK(!out->second.uuid.empty());
  CHECK(!out->second.time_synced);
  CHECK_EQ(out->second.boot_id, std::string("b1"));
  CHECK_EQ(out->second.boot_ms_end, 50000);
  CHECK_EQ(out->second.boot_ms_start, 47000);
}

TEST(test_concurrent_enqueue_and_drain) {
  SegmentSpool s(fresh_dir(), 1 << 24);
  std::atomic<bool> done{false};
  std::thread producer([&] {
    for (int i = 0; i < 50; ++i) {
      char buf[16];
      std::snprintf(buf, sizeof(buf), "10:%02d:%02d", i / 60, i % 60);
      s.enqueue(pcm(), item(buf));
    }
    done = true;
  });
  std::thread consumer([&] {
    while (!done.load()) {
      for (const auto& it : s.pending()) s.remove(it);
    }
  });
  producer.join();
  consumer.join();
  for (const auto& it : s.pending()) s.remove(it);
  CHECK_EQ(s.depth(), 0u);
  CHECK(s.pending().empty());
}

TEST(test_remove_and_rewrite_tolerate_evicted) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  auto it = s.enqueue(pcm(), item("10:00:00", false));
  s.remove(it);
  s.rewrite_times(it, "2026-11-15T11:00:00.000Z", "2026-11-15T11:00:01.000Z");
  s.remove(it);
  CHECK_EQ(s.depth(), 0u);
  CHECK(!fs::exists(it.json_path));
}

TEST(test_auth_and_rate_limit_keep_item_and_stop_pass) {
  for (int code : {401, 403, 408, 429}) {
    auto d = fresh_dir();
    SegmentSpool s(d, 1 << 20);
    s.enqueue(pcm(), item("10:00:00"));
    s.enqueue(pcm(), item("10:00:01"));
    FakeClock c;
    c.snap = synced_snap();
    int calls = 0;
    Uploader u(s, [&](const std::string&, const std::string&) { ++calls; return code; }, c);
    CHECK_EQ(u.drain_once(), 0);
    CHECK_EQ(calls, 1);
    CHECK_EQ(s.depth(), 2u);
    CHECK(!fs::exists(d / "rejected"));
    CHECK_EQ(u.rejected_count(), 0u);
  }
}

TEST(test_rejected_dir_is_capped) {
  auto d = fresh_dir();
  SegmentSpool s(d, 1 << 26);
  const int n = static_cast<int>(Uploader::kMaxRejected) + 5;
  for (int i = 0; i < n; ++i) {
    char buf[16];
    std::snprintf(buf, sizeof(buf), "10:%02d:%02d", i / 60, i % 60);
    s.enqueue(pcm(), item(buf));
  }
  FakeClock c;
  c.snap = synced_snap();
  Uploader u(s, [](const std::string&, const std::string&) { return 422; }, c);
  CHECK_EQ(u.drain_once(), 0);
  CHECK_EQ(s.depth(), 0u);
  CHECK_EQ(u.rejected_count(), Uploader::kMaxRejected);
  std::size_t jsons = 0, wavs = 0;
  for (const auto& e : fs::directory_iterator(d / "rejected")) {
    jsons += e.path().extension() == ".json";
    wavs += e.path().extension() == ".wav";
  }
  CHECK_EQ(jsons, Uploader::kMaxRejected);
  CHECK_EQ(wavs, Uploader::kMaxRejected);
  CHECK_EQ(prune_rejected(d / "rejected", 10), 10u);  // oldest pruned first
}

TEST(test_unsynced_same_boot_held_until_sync) {
  SegmentSpool s(fresh_dir(), 1 << 20);
  s.enqueue(pcm(), item("10:00:00", false, "b1", 10000));
  s.enqueue(pcm(), item("10:00:01", true));
  FakeClock c;
  c.snap = synced_snap();
  c.snap.synced = false;
  std::vector<std::string> metas;
  Uploader u(s, [&](const std::string&, const std::string& m) { metas.push_back(m); return 200; }, c);
  CHECK_EQ(u.drain_once(), 1);  // only the synced item goes up
  CHECK_EQ(metas.size(), 1u);
  CHECK(metas[0].find("10:00:01") != std::string::npos);
  CHECK_EQ(s.depth(), 1u);
  CHECK_EQ(u.drain_once(), 0);  // still unsynced: still held
  CHECK_EQ(metas.size(), 1u);
  c.snap.synced = true;
  CHECK_EQ(u.drain_once(), 1);
  CHECK_EQ(metas.size(), 2u);
  CHECK(metas[1].find("\"ts_start\":\"2026-11-15T15:59:00.000Z\"") != std::string::npos);
  CHECK(metas[1].find("\"time_synced\":true") != std::string::npos);
  CHECK_EQ(s.depth(), 0u);
}

TEST(test_segment_spanning_clock_sync_is_unsynced) {
  FakeClock c;
  c.snap = {false, tp_from("2020-01-01T00:00:00.000Z"), 50000, "b1"};
  Segmenter seg(2000, c);
  const Tp t0 = tp_from("2020-01-01T00:00:00.000Z");
  AudioChunk ch;
  ch.pcm.assign(16000, 1);
  ch.ts = t0;
  ch.duration_ms = 1000;
  CHECK(!seg.push(ch));
  c.snap.synced = true;  // NTP step lands mid-segment
  ch.ts = t0 + std::chrono::seconds(1);
  auto out = seg.push(ch);
  CHECK(out.has_value());
  CHECK(!out->second.time_synced);
  ch.ts = t0 + std::chrono::seconds(2);
  CHECK(!seg.push(ch));  // next segment starts synced
  ch.ts = t0 + std::chrono::seconds(3);
  out = seg.push(ch);
  CHECK(out.has_value() && out->second.time_synced);
}

int main() { return testing::run_all(); }
