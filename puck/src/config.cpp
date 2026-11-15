#include "config.hpp"

#include <fstream>
#include <sstream>
#include <unordered_map>

namespace calypso {
namespace {

std::string trim(std::string s) {
  while (!s.empty() && (s.front() == ' ' || s.front() == '\t')) {
    s.erase(s.begin());
  }
  while (!s.empty() && (s.back() == ' ' || s.back() == '\t' || s.back() == '\r')) {
    s.pop_back();
  }
  return s;
}

}  // namespace

bool load_config(const std::string& path, Config& out) {
  std::ifstream in(path);
  if (!in) {
    return false;
  }

  std::unordered_map<std::string, std::string> kv;
  std::string line;
  while (std::getline(in, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') {
      continue;
    }
    const auto eq = line.find('=');
    if (eq == std::string::npos) {
      continue;
    }
    kv[trim(line.substr(0, eq))] = trim(line.substr(eq + 1));
  }

  auto get = [&](const char* key) -> std::string {
    const auto it = kv.find(key);
    return it == kv.end() ? std::string{} : it->second;
  };

  out.backend_ip = get("BACKEND_IP");
  out.backend_port = static_cast<std::uint16_t>(std::stoi(get("BACKEND_PORT").empty() ? "0" : get("BACKEND_PORT")));
  out.mic_device = get("MIC_DEVICE");
  out.chunk_ms = get("CHUNK_MS").empty() ? 30 : std::stoi(get("CHUNK_MS"));
  out.connect_retry_sec =
      get("CONNECT_RETRY_SEC").empty() ? 5 : std::stoi(get("CONNECT_RETRY_SEC"));
  out.connection_check_sec =
      get("CONNECTION_CHECK_SEC").empty() ? 2 : std::stoi(get("CONNECTION_CHECK_SEC"));
  out.ncs2_device = get("NCS2_DEVICE");
  out.stt_model_path = get("STT_MODEL_PATH");
  out.voice_model_path = get("VOICE_MODEL_PATH");

  return !out.backend_ip.empty() && out.backend_port != 0 && !out.mic_device.empty();
}

}  // namespace calypso
