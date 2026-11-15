#pragma once

#include "types.hpp"

namespace calypso {

// Whether a voice-ID result is worth telling the phone about. An Uncertain or
// Unknown result whose best gallery score is below `min_score` matched nobody
// at all: it is almost always noise (rustle, breath, room), not a new person,
// so it must not become "Someone new" on the phone. Identified always reports.
bool should_report_who(const WhoIsTalking& who, float min_score);

}  // namespace calypso
