#include "backend_link.hpp"

#include "capture.hpp"
#include "util.hpp"
#include "wav.hpp"

#include <curl/curl.h>

#include <iostream>
#include <sstream>

namespace calypso {
namespace {

size_t discard_write(char* /*ptr*/, size_t size, size_t nmemb, void* /*userdata*/) {
  return size * nmemb;
}

struct CurlGlobal {
  CurlGlobal() { curl_global_init(CURL_GLOBAL_DEFAULT); }
  ~CurlGlobal() { curl_global_cleanup(); }
};

CurlGlobal& curl_lifetime() {
  static CurlGlobal g;
  return g;
}

}  // namespace

BackendLink::~BackendLink() {
  shutdown();
}

bool BackendLink::init(const std::string& ip, std::uint16_t port,
                       const std::string& token, int segment_ms) {
  curl_lifetime();
  ip_ = ip;
  port_ = port;
  token_ = token;
  segment_ms_ = segment_ms > 0 ? segment_ms : 3000;
  connected_ = false;
  buf_.clear();
  buf_has_start_ = false;
  if (ip_.empty() || port_ == 0 || token_.empty()) {
    std::cerr << "backend: need BACKEND_IP, BACKEND_PORT, API_TOKEN\n";
    return false;
  }
  std::cerr << "backend: " << base_url() << " segment_ms=" << segment_ms_ << "\n";
  return true;
}

std::string BackendLink::base_url() const {
  return "http://" + ip_ + ":" + std::to_string(port_);
}

bool BackendLink::connect() {
  std::lock_guard<std::mutex> lock(mu_);
  CURL* curl = curl_easy_init();
  if (!curl) {
    connected_ = false;
    return false;
  }

  const std::string url = base_url() + "/health";
  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, discard_write);

  const CURLcode rc = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
  curl_easy_cleanup(curl);

  if (rc != CURLE_OK || http != 200) {
    std::cerr << "backend: connect failed (" << url << ") curl=" << rc
              << " http=" << http << "\n";
    connected_ = false;
    return false;
  }

  connected_ = true;
  std::cerr << "backend: connected\n";
  (void)post_health_locked();
  return true;
}

bool BackendLink::is_connected() const {
  std::lock_guard<std::mutex> lock(mu_);
  return connected_;
}

bool BackendLink::send_audio_chunk(const AudioChunk& chunk) {
  std::lock_guard<std::mutex> lock(mu_);
  if (chunk.pcm.empty()) {
    return connected_;
  }

  if (!buf_has_start_) {
    buf_start_ = chunk.ts;
    buf_has_start_ = true;
  }
  buf_.insert(buf_.end(), chunk.pcm.begin(), chunk.pcm.end());

  const int buffered_ms =
      static_cast<int>(buf_.size() * 1000 / static_cast<std::size_t>(kSampleRate));
  if (buffered_ms < segment_ms_) {
    return connected_;
  }
  return flush_locked();
}

bool BackendLink::flush_locked() {
  if (buf_.empty()) {
    return true;
  }
  const auto ts_start = buf_has_start_ ? buf_start_ : std::chrono::system_clock::now();
  const int dur_ms =
      static_cast<int>(buf_.size() * 1000 / static_cast<std::size_t>(kSampleRate));
  const auto ts_end = ts_start + std::chrono::milliseconds(dur_ms);

  std::vector<std::int16_t> pcm = std::move(buf_);
  buf_.clear();
  buf_has_start_ = false;

  if (!post_segment_locked(pcm, ts_start, ts_end)) {
    // Put audio back so a reconnect can retry (new uuid on next attempt).
    buf_ = std::move(pcm);
    buf_start_ = ts_start;
    buf_has_start_ = true;
    connected_ = false;
    return false;
  }
  connected_ = true;
  return true;
}

bool BackendLink::post_segment_locked(
    const std::vector<std::int16_t>& pcm,
    std::chrono::system_clock::time_point ts_start,
    std::chrono::system_clock::time_point ts_end) {
  const std::string uuid = make_segment_uuid();
  const std::string wav = pcm16_to_wav(pcm, kSampleRate);

  std::ostringstream meta;
  meta << "{"
       << "\"segment_uuid\":\"" << uuid << "\","
       << "\"ts_start\":\"" << format_iso8601_utc(ts_start) << "\","
       << "\"ts_end\":\"" << format_iso8601_utc(ts_end) << "\","
       << "\"sound_tags\":[],"
       << "\"local_text\":null"
       << "}";
  const std::string meta_json = meta.str();

  CURL* curl = curl_easy_init();
  if (!curl) {
    return false;
  }

  curl_mime* mime = curl_mime_init(curl);

  curl_mimepart* audio = curl_mime_addpart(mime);
  curl_mime_name(audio, "audio");
  curl_mime_filename(audio, "seg.wav");
  curl_mime_type(audio, "audio/wav");
  curl_mime_data(audio, wav.data(), wav.size());

  curl_mimepart* meta_part = curl_mime_addpart(mime);
  curl_mime_name(meta_part, "meta");
  curl_mime_data(meta_part, meta_json.c_str(), CURL_ZERO_TERMINATED);

  const std::string url = base_url() + "/puck/segments";
  const std::string auth = "Authorization: Bearer " + token_;
  struct curl_slist* headers = nullptr;
  headers = curl_slist_append(headers, auth.c_str());

  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_MIMEPOST, mime);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, discard_write);

  const CURLcode rc = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);

  curl_slist_free_all(headers);
  curl_mime_free(mime);
  curl_easy_cleanup(curl);

  if (rc != CURLE_OK || (http != 200 && http != 409)) {
    std::cerr << "backend: POST /puck/segments failed curl=" << rc
              << " http=" << http << " uuid=" << uuid << "\n";
    return false;
  }

  std::cerr << "backend: uploaded segment " << uuid << " (" << pcm.size()
            << " samples, http=" << http << ")\n";
  return true;
}

bool BackendLink::post_health_locked() {
  CURL* curl = curl_easy_init();
  if (!curl) {
    return false;
  }

  const std::string body =
      std::string("{\"ts\":\"") + format_iso8601_utc(std::chrono::system_clock::now()) +
      "\",\"queue_depth\":0,\"sound_backend\":\"none\",\"ms_per_segment\":null,"
      "\"time_synced\":true,\"battery_pct\":null,\"last_upload_ok\":true}";

  const std::string url = base_url() + "/puck/health";
  const std::string auth = "Authorization: Bearer " + token_;
  const std::string ctype = "Content-Type: application/json";
  struct curl_slist* headers = nullptr;
  headers = curl_slist_append(headers, auth.c_str());
  headers = curl_slist_append(headers, ctype.c_str());

  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_POST, 1L);
  curl_easy_setopt(curl, CURLOPT_POSTFIELDS, body.c_str());
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, discard_write);

  const CURLcode rc = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);

  if (rc != CURLE_OK || http != 200) {
    std::cerr << "backend: POST /puck/health failed curl=" << rc
              << " http=" << http << "\n";
    return false;
  }
  return true;
}

void BackendLink::disconnect() {
  std::lock_guard<std::mutex> lock(mu_);
  connected_ = false;
}

void BackendLink::shutdown() {
  std::lock_guard<std::mutex> lock(mu_);
  connected_ = false;
  buf_.clear();
  buf_has_start_ = false;
}

}  // namespace calypso
