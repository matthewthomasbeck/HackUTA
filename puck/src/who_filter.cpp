#include "who_filter.hpp"

namespace calypso {

bool should_report_who(const WhoIsTalking& who, float min_score) {
  if (who.status == WhoIsTalking::Status::Identified) {
    return true;
  }
  return who.score >= min_score;
}

}  // namespace calypso
