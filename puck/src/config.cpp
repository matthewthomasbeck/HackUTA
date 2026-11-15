#include "config.hpp"

#include <fstream>
#include <unordered_map>

namespace calypso {
namespace {

std::string trim(std::string s) {
  while (!s.empty() && (s.front() == ' ' || s.front() == '\t')) {
    s.erase(s.begin());
  }
  while (!s.empty() &&
         (s.back() == ' ' || s.back() == '\t' || s.back() == '\r')) {
    s.pop_back();
  }
  return s;
}

int parse_int(const std::string& s, int fallback) {
  if (s.empty()) {
    return fallback;
  }
  try {
    return std::stoi(s);
  } catch (...) {
    return fallback;
  }
}

ModeSetting parse_mode_setting(const std::string& s) {
  if (s == "offline") {
    return ModeSetting::Offline;
  }
  // default / "online" / anything else → health-driven online path
  return ModeSetting::Online;
}

InferBackend parse_infer_backend(const std::string& s) {
  if (s == "coral") {
    return InferBackend::Coral;
  }
  if (s == "ncs2") {
    return InferBackend::Ncs2;
  }
  return InferBackend::Cpu;
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
    const auto hash = line.find('#');
    if (hash != std::string::npos) {
      line = trim(line.substr(0, hash));
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
  out.backend_port =
      static_cast<std::uint16_t>(parse_int(get("BACKEND_PORT"), 0));
  out.api_token = get("API_TOKEN");
  out.mic_device = get("MIC_DEVICE");
  out.mode = parse_mode_setting(get("MODE"));
  out.chunk_ms = parse_int(get("CHUNK_MS"), 30);
  out.segment_ms = parse_int(get("SEGMENT_MS"), 3000);
  out.offline_segment_ms = parse_int(get("OFFLINE_SEGMENT_MS"), 2000);
  out.connect_retry_sec = parse_int(get("CONNECT_RETRY_SEC"), 5);
  out.connection_check_sec = parse_int(get("CONNECTION_CHECK_SEC"), 2);
  out.infer_backend = parse_infer_backend(get("INFER_BACKEND"));
  out.coral_device = get("CORAL_DEVICE");
  out.ncs2_device = get("NCS2_DEVICE");
  out.stt_model_path = get("STT_MODEL_PATH");
  out.voice_model_path = get("VOICE_MODEL_PATH");
  out.bt_adapter = get("BT_ADAPTER");
  out.bt_peer_name = get("BT_PEER_NAME");

  return !out.backend_ip.empty() && out.backend_port != 0 &&
         !out.api_token.empty() && !out.mic_device.empty();
}

}  // namespace calypso
