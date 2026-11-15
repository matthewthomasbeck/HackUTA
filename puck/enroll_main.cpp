// calypso_enroll: record voice samples through the puck mic and upload them
// to POST /people/{id}/voice. Stop the puck service first (it owns the mic).

#include "audio_gain.hpp"
#include "capture.hpp"
#include "config.hpp"
#include "people_json.hpp"
#include "wav.hpp"

#include <curl/curl.h>

#include <chrono>
#include <cstdlib>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace {

size_t append_write(char* ptr, size_t size, size_t nmemb, void* userdata) {
  static_cast<std::string*>(userdata)->append(ptr, size * nmemb);
  return size * nmemb;
}

// Returns HTTP status, or -1 on transport failure. Body goes to `body`.
int http_request(const std::string& url, const std::string& token,
                 const std::string* wav, std::string& body) {
  body.clear();
  CURL* curl = curl_easy_init();
  if (!curl) {
    return -1;
  }
  curl_mime* mime = nullptr;
  if (wav) {
    mime = curl_mime_init(curl);
    curl_mimepart* part = curl_mime_addpart(mime);
    curl_mime_name(part, "audio");
    curl_mime_filename(part, "sample.wav");
    curl_mime_type(part, "audio/wav");
    curl_mime_data(part, wav->data(), wav->size());
    curl_easy_setopt(curl, CURLOPT_MIMEPOST, mime);
  } else {
    curl_easy_setopt(curl, CURLOPT_HTTPGET, 1L);
  }
  const std::string auth = "Authorization: Bearer " + token;
  struct curl_slist* headers = curl_slist_append(nullptr, auth.c_str());
  curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
  curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
  curl_easy_setopt(curl, CURLOPT_TIMEOUT, 60L);
  curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, append_write);
  curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);
  const CURLcode rc = curl_easy_perform(curl);
  long http = 0;
  curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http);
  curl_slist_free_all(headers);
  if (mime) {
    curl_mime_free(mime);
  }
  curl_easy_cleanup(curl);
  if (rc != CURLE_OK) {
    std::cerr << "request failed: " << curl_easy_strerror(rc) << "\n";
    return -1;
  }
  return static_cast<int>(http);
}

void usage() {
  std::cerr << "usage: calypso_enroll --name <Name> [--samples 3] "
               "[--seconds 8] [--config config/.env]\n";
}

}  // namespace

int main(int argc, char** argv) {
  std::string name;
  std::string config_path = "config/.env";
  int samples = 3;
  int seconds = 8;
  for (int a = 1; a < argc; ++a) {
    const std::string k = argv[a];
    if (a + 1 >= argc) {
      usage();
      return 2;
    }
    const std::string v = argv[++a];
    if (k == "--name") {
      name = v;
    } else if (k == "--samples") {
      samples = std::atoi(v.c_str());
    } else if (k == "--seconds") {
      seconds = std::atoi(v.c_str());
    } else if (k == "--config") {
      config_path = v;
    } else {
      usage();
      return 2;
    }
  }
  if (name.empty() || samples < 1 || seconds < 1) {
    usage();
    return 2;
  }

  calypso::Config cfg;
  if (!calypso::load_config(config_path, cfg)) {
    std::cerr << "failed to load " << config_path
              << " (need BACKEND_IP, BACKEND_PORT, API_TOKEN, MIC_DEVICE)\n";
    return 2;
  }

  curl_global_init(CURL_GLOBAL_DEFAULT);
  const std::string base =
      "http://" + cfg.backend_ip + ":" + std::to_string(cfg.backend_port);

  std::string body;
  const int st = http_request(base + "/people", cfg.api_token, nullptr, body);
  if (st != 200) {
    std::cerr << "GET /people failed (http=" << st << ")\n";
    curl_global_cleanup();
    return 2;
  }
  std::vector<calypso::PersonRef> people;
  if (!calypso::parse_people(body, people)) {
    std::cerr << "could not parse /people response\n";
    curl_global_cleanup();
    return 2;
  }
  std::string err;
  const auto id = calypso::find_person_id(people, name, err);
  if (!id) {
    std::cerr << err << "\n";
    curl_global_cleanup();
    return 2;
  }

  calypso::Capture capture;
  if (!capture.init(cfg.mic_device, cfg.chunk_ms)) {
    std::cerr << "could not open mic " << cfg.mic_device
              << " \xe2\x80\x94 stop the puck first: sudo systemctl stop calypso-puck\n";
    curl_global_cleanup();
    return 3;
  }
  capture.set_gain(cfg.mic_gain);

  int uploaded = 0;
  for (int n = 1; n <= samples; ++n) {
    std::cout << "Sample " << n << "/" << samples << ": read aloud for "
              << seconds << " seconds\xe2\x80\xa6 3 2 1 go" << std::endl;
    std::this_thread::sleep_for(std::chrono::seconds(1));

    std::vector<std::int16_t> pcm;
    const auto deadline =
        std::chrono::steady_clock::now() + std::chrono::seconds(seconds);
    while (std::chrono::steady_clock::now() < deadline) {
      calypso::AudioChunk chunk;
      if (!capture.read_chunk(chunk)) {
        break;
      }
      pcm.insert(pcm.end(), chunk.pcm.begin(), chunk.pcm.end());
    }
    const float rms = calypso::pcm_rms(pcm);
    std::cout << "rms=" << rms << std::endl;
    if (rms < cfg.min_speech_rms) {
      std::cout << "too quiet (rms=" << rms
                << " < MIN_SPEECH_RMS=" << cfg.min_speech_rms
                << "): clip the mic closer or raise MIC_GAIN" << std::endl;
      continue;
    }
    const std::string wav = calypso::pcm16_to_wav(pcm, calypso::kSampleRate);
    std::string resp;
    const int code =
        http_request(base + "/people/" + *id + "/voice", cfg.api_token, &wav, resp);
    std::cout << "HTTP " << code << " " << resp << std::endl;
    if (code >= 200 && code < 300) {
      ++uploaded;
    }
  }
  capture.shutdown();

  std::cout << "uploaded " << uploaded << "/" << samples << " samples for "
            << name << "\nRestart the puck: sudo systemctl start calypso-puck"
            << std::endl;
  curl_global_cleanup();
  return uploaded >= 1 ? 0 : 1;
}
