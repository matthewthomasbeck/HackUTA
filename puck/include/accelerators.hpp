#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// Optional USB accelerators. Stubbed — call during init; online path ignores them.
// Coral: YAMNet / future TPU graphs. NCS2: legacy OpenVINO MYRIAD option.
class Accelerators {
 public:
  Accelerators() = default;
  ~Accelerators();

  Accelerators(const Accelerators&) = delete;
  Accelerators& operator=(const Accelerators&) = delete;

  // Open Coral Edge TPU if present. Returns false if missing / stub.
  bool init_coral(const std::string& device);

  // Open NCS2 / MYRIAD if present. Returns false if missing / stub.
  bool init_ncs2(const std::string& device);

  bool coral_ready() const;
  bool ncs2_ready() const;

  void shutdown();

 private:
  bool coral_ready_ = false;
  bool ncs2_ready_ = false;
  // TODO: Coral / OpenVINO handles
};

}  // namespace calypso
