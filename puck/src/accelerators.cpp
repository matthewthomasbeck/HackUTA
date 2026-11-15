#include "accelerators.hpp"

namespace calypso {

Accelerators::~Accelerators() {
  shutdown();
}

bool Accelerators::init_coral(const std::string& /*device*/) {
  // TODO: open Edge TPU, load optional YAMNet / TPU graphs
  coral_ready_ = false;
  return coral_ready_;
}

bool Accelerators::init_ncs2(const std::string& /*device*/) {
  // TODO: open OpenVINO MYRIAD / NCS2 device
  ncs2_ready_ = false;
  return ncs2_ready_;
}

bool Accelerators::coral_ready() const {
  return coral_ready_;
}

bool Accelerators::ncs2_ready() const {
  return ncs2_ready_;
}

void Accelerators::shutdown() {
  // TODO: release Coral / NCS2 handles
  coral_ready_ = false;
  ncs2_ready_ = false;
}

}  // namespace calypso
