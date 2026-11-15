#include "backend_link.hpp"

#include "util.hpp"

#include <curl/curl.h>

#include <chrono>
#include <iostream>
#include <string>

namespace calypso {
namespace {

size_t discard_write(char* /*ptr*/, size_t size, size_t nmemb, void* /*userdata*/) {
  return size * nmemb;
}

size_t append_write(char* ptr, size_t size, size_t nmemb, void* userdata) {
  const std::size_t n = size * nmemb;
  auto* out = static_cast<std::string*>(userdata);
  out->append(ptr, n);
  return n;
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
                       const std::string& token) {
  curl_lifetime();
  ip_ = ip;
  port_ = port;
  token_ = token;
  connected_ = false;
  if (ip_.empty() || port_ == 0 || token_.empty()) {
    std::cerr << "backend: need BACKEND_IP, BACKEND_PORT, API_TOKEN\n";
    return false;
  }
  std::cerr << "backend: " << base_url() << "\n";
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
  return true;
}

bool BackendLink::is_connected() const {
  std::lock_guard<std::mutex> lock(mu_);
  return connected_;
}

int BackendLink::post_segment(const std::string& wav, const std::string& meta_json) {
  CURL* curl = curl_easy_init();
  if (!curl) {
    return -1;
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

  const int status = rc == CURLE_OK ? static_cast<int>(http) : -1;
  {
    std::lock_guard<std::mutex> lock(mu_);
    connected_ = status > 0 && status < 500;
  }
  if (status < 200 || status >= 300) {
    std::cerr << "backend: POST /puck/segments curl=" << rc << " http=" << http << "\n";
  }
  return status;
}

bool BackendLink::get_gallery(std::string& body_out) {
  body_out.clear();
  CURL* curl = curl_easy_init();
  if (!curl) {
    return false;
  }

  const std::string url = base_url() + "/puck/gallery";
  const std::string auth = "Authorization: Bearer " + token_;
  struct curl_slist* headers = nullptr;
  headers = curl_slist_append(headers, auth.c_str());

  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 15L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, append_write);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body_out);

  const CURLcode rc = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
  curl_slist_free_all(headers);
  curl_easy_cleanup(curl);

  if (rc != CURLE_OK || http != 200) {
    std::cerr << "backend: GET /puck/gallery failed curl=" << rc
              << " http=" << http << "\n";
    body_out.clear();
    return false;
  }
  return true;
}

bool BackendLink::post_health(std::size_t queue_depth, bool time_synced,
                              bool last_upload_ok) {
  CURL* curl = curl_easy_init();
  if (!curl) {
    return false;
  }

  const std::string body =
      std::string("{\"ts\":\"") + format_iso8601_utc(std::chrono::system_clock::now()) +
      "\",\"queue_depth\":" + std::to_string(queue_depth) +
      ",\"sound_backend\":\"none\",\"ms_per_segment\":null,\"time_synced\":" +
      (time_synced ? "true" : "false") + ",\"battery_pct\":null,\"last_upload_ok\":" +
      (last_upload_ok ? "true" : "false") + "}";

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
}

}  // namespace calypso
