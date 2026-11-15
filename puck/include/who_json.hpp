#pragma once

#include "types.hpp"

#include <string>

namespace calypso {

// One WhoIsTalking as UTF-8 JSON for BLE `who` (docs/puck-phone-ble.md).
// Keys: status, person_id, display_name, relationship, score.
std::string who_to_json(const WhoIsTalking& who);

}  // namespace calypso
