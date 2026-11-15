#include "test_main.hpp"
#include "who_filter.hpp"

using namespace calypso;

static WhoIsTalking who(WhoIsTalking::Status status, float score) {
  WhoIsTalking w;
  w.status = status;
  w.score = score;
  return w;
}

TEST(test_identified_always_reported) {
  CHECK(should_report_who(who(WhoIsTalking::Status::Identified, 0.50f), 0.2f));
}

TEST(test_low_score_uncertain_is_noise) {
  CHECK(!should_report_who(who(WhoIsTalking::Status::Uncertain, 0.03f), 0.2f));
  CHECK(!should_report_who(who(WhoIsTalking::Status::Uncertain, 0.199f), 0.2f));
}

TEST(test_voice_like_uncertain_is_reported) {
  CHECK(should_report_who(who(WhoIsTalking::Status::Uncertain, 0.2f), 0.2f));
  CHECK(should_report_who(who(WhoIsTalking::Status::Uncertain, 0.35f), 0.2f));
}

TEST(test_unknown_low_score_not_reported) {
  CHECK(!should_report_who(who(WhoIsTalking::Status::Unknown, 0.0f), 0.2f));
}

TEST(test_zero_min_score_reports_everything) {
  CHECK(should_report_who(who(WhoIsTalking::Status::Uncertain, 0.01f), 0.0f));
}
int main() { return testing::run_all(); }
