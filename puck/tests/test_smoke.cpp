#include "calypso_puck/config.hpp"

#include <catch2/catch_test_macros.hpp>

TEST_CASE("load_config_from_env returns defaults", "[config]") {
  auto cfg = calypso_puck::load_config_from_env();
  REQUIRE(cfg.frame_ms == 30);
  REQUIRE(cfg.sound_backend == "cpu");
  REQUIRE(cfg.sound_every_n == 1);
}
