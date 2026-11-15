#pragma once

#include "voice_gallery.hpp"

#include <string>
#include <vector>

namespace calypso {

// Parse GET /puck/gallery JSON into speakers. Returns false on malformed body.
bool parse_puck_gallery(const std::string& json, std::vector<EnrolledSpeaker>& out);

}  // namespace calypso
