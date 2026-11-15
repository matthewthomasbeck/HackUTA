#include "phone_link.hpp"

#include "who_json.hpp"

#include <fstream>
#include <iostream>

namespace calypso {

PhoneLink::~PhoneLink() {
  shutdown();
}

bool PhoneLink::init(const std::string& /*adapter*/,
                     const std::string& /*peer_name*/,
                     const std::string& who_drop_path) {
  who_drop_path_ =
      who_drop_path.empty() ? "/tmp/calypso_who.json" : who_drop_path;
  ready_ = true;
  std::cerr << "phone: who drop file → " << who_drop_path_
            << " (run scripts/ble_who_peripheral.py)\n";
  return true;
}

bool PhoneLink::connect() {
  // Drop-file path is always "connected" once init'd; BLE sidecar is separate.
  return ready_;
}

bool PhoneLink::is_connected() const {
  return ready_;
}

bool PhoneLink::send_who_is_talking(const WhoIsTalking& who) {
  if (!ready_ || who_drop_path_.empty()) {
    return false;
  }

  const std::string json = who_to_json(who);
  if (json.size() > 180) {
    std::cerr << "phone: who JSON too long (" << json.size()
              << " > 180) — BLE may drop it\n";
  }

  const std::string tmp = who_drop_path_ + ".tmp";
  {
    std::ofstream out(tmp, std::ios::binary | std::ios::trunc);
    if (!out) {
      std::cerr << "phone: failed to write " << tmp << "\n";
      return false;
    }
    out << json;
    if (!out) {
      return false;
    }
  }
  if (std::rename(tmp.c_str(), who_drop_path_.c_str()) != 0) {
    std::cerr << "phone: rename to " << who_drop_path_ << " failed\n";
    return false;
  }
  return true;
}

void PhoneLink::disconnect() {}

void PhoneLink::shutdown() {
  ready_ = false;
}

}  // namespace calypso
