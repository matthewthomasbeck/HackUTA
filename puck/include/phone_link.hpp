#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// Bluetooth (or BLE GATT) link to the iPhone app for offline emergency ID.
// Stubbed — online HTTP path does not use this.
class PhoneLink {
 public:
  PhoneLink() = default;
  ~PhoneLink();

  PhoneLink(const PhoneLink&) = delete;
  PhoneLink& operator=(const PhoneLink&) = delete;

  // Scan / pair / open GATT to the app. Stub returns false.
  bool init(const std::string& adapter, const std::string& peer_name);

  bool connect();
  bool is_connected() const;

  // Push "who is talking" to the phone. Stub no-op.
  bool send_who_is_talking(const WhoIsTalking& who);

  void disconnect();
  void shutdown();

 private:
  bool connected_ = false;
  // TODO: BlueZ / BLE session
};

}  // namespace calypso
