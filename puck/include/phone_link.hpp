#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// MVP phone path: write WhoIsTalking JSON to a drop file that
// scripts/ble_who_peripheral.py advertises over BLE (docs/puck-phone-ble.md).
// Full in-process BlueZ can replace this later without changing callers.
class PhoneLink {
 public:
  PhoneLink() = default;
  ~PhoneLink();

  PhoneLink(const PhoneLink&) = delete;
  PhoneLink& operator=(const PhoneLink&) = delete;

  // adapter unused for drop-file MVP; peer_name unused.
  // who_drop_path: file the BLE sidecar watches (default /tmp/calypso_who.json).
  bool init(const std::string& adapter, const std::string& peer_name,
            const std::string& who_drop_path = "/tmp/calypso_who.json");

  bool connect();
  bool is_connected() const;

  // Atomically write who JSON to the drop file for the BLE sidecar.
  bool send_who_is_talking(const WhoIsTalking& who);

  void disconnect();
  void shutdown();

 private:
  bool ready_ = false;
  std::string who_drop_path_;
};

}  // namespace calypso
