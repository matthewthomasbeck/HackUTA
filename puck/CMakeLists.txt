cmake_minimum_required(VERSION 3.16)
project(calypso_puck LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_library(calypso_puck_lib
  src/config.cpp
)
target_include_directories(calypso_puck_lib PUBLIC include)

add_executable(calypso_puck src/main.cpp)
target_link_libraries(calypso_puck PRIVATE calypso_puck_lib)

include(CTest)
if(BUILD_TESTING)
  include(FetchContent)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.5.4
  )
  FetchContent_MakeAvailable(Catch2)

  add_executable(calypso_puck_tests tests/test_smoke.cpp)
  target_link_libraries(calypso_puck_tests PRIVATE calypso_puck_lib Catch2::Catch2WithMain)
  add_test(NAME calypso_puck_tests COMMAND calypso_puck_tests)
endif()
