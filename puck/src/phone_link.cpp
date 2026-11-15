#include "phone_link.hpp"

namespace calypso {

PhoneLink::~PhoneLink() {
  shutdown();
}

bool PhoneLink::init(const std::string& /*adapter*/,
                     const std::string& /*peer_name*/) {
  // TODO: open Bluetooth adapter, remember peer name / UUID
  connected_ = false;
  return true;  // init ok even if not yet connected
}

bool PhoneLink::connect() {
  // TODO: connect / reconnect to the phone app over BLE
  connected_ = false;
  return connected_;
}

bool PhoneLink::is_connected() const {
  return connected_;
}

bool PhoneLink::send_who_is_talking(const WhoIsTalking& /*who*/) {
  // TODO: serialize WhoIsTalking and notify the app characteristic
  if (!connected_) {
    return false;
  }
  return false;
}

void PhoneLink::disconnect() {
  connected_ = false;
}

void PhoneLink::shutdown() {
  // TODO: close BLE session
  connected_ = false;
}

}  // namespace calypso
