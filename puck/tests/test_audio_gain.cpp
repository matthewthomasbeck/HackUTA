#include <cmath>
#include <cstdint>
#include <vector>

#include "audio_gain.hpp"
#include "test_main.hpp"

using namespace calypso;

TEST(test_gain_one_is_identity) {
  std::vector<std::int16_t> p{1, -2, 30000, -32768};
  const auto orig = p;
  apply_gain(p, 1.0f);
  CHECK(p == orig);
}

TEST(test_gain_scales) {
  std::vector<std::int16_t> p{100, -100};
  apply_gain(p, 4.0f);
  CHECK_EQ(p[0], 400);
  CHECK_EQ(p[1], -400);
}

TEST(test_gain_saturates) {
  std::vector<std::int16_t> p{2000, -2000};
  apply_gain(p, 32.0f);
  CHECK_EQ(p[0], 32767);
  CHECK_EQ(p[1], -32768);
}

TEST(test_rms_known_signal) {
  std::vector<std::int16_t> p{16384, -16384};
  CHECK(std::fabs(pcm_rms(p) - 0.5f) < 1e-4f);
}

TEST(test_rms_empty_is_zero) {
  CHECK(pcm_rms({}) == 0.f);
}

int main() { return testing::run_all(); }
