cmake_minimum_required(VERSION 3.16)
project(calypso_puck LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

add_executable(calypso_puck
  main.cpp
  src/config.cpp
  src/capture.cpp
  src/backend_link.cpp
  src/models.cpp
  src/state_machine.cpp
  src/connection_listener.cpp
  src/wav.cpp
  src/util.cpp
)

target_include_directories(calypso_puck PRIVATE include)

find_package(Threads REQUIRED)
find_package(CURL REQUIRED)
target_link_libraries(calypso_puck PRIVATE Threads::Threads CURL::libcurl)

# ALSA on the Pi / Linux. macOS can still build with MIC_DEVICE=sine.
find_package(ALSA)
if(ALSA_FOUND)
  target_compile_definitions(calypso_puck PRIVATE CALYPSO_HAS_ALSA=1)
  target_link_libraries(calypso_puck PRIVATE ALSA::ALSA)
  message(STATUS "ALSA found — real mic capture enabled")
else()
  message(STATUS "ALSA not found — use MIC_DEVICE=sine for online smoke tests")
endif()
