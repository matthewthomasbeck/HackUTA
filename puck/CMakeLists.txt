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
  src/accelerators.cpp
  src/phone_link.cpp
  src/offline_buffer.cpp
  src/voice_gallery.cpp
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

# sherpa-onnx for Titanet-small voice fingerprints (optional but required for
# offline ID). Pass -DCALYPSO_SHERPA_ROOT=/path/to/prefix
set(CALYPSO_SHERPA_ROOT "" CACHE PATH "sherpa-onnx install prefix")
if(CALYPSO_SHERPA_ROOT)
  find_path(SHERPA_ONNX_INCLUDE_DIR
    NAMES sherpa-onnx/c-api/c-api.h
    HINTS
      "${CALYPSO_SHERPA_ROOT}/include"
      "${CALYPSO_SHERPA_ROOT}"
  )
  find_library(SHERPA_ONNX_LIBRARY
    NAMES sherpa-onnx-c-api sherpa-onnx
    HINTS
      "${CALYPSO_SHERPA_ROOT}/lib"
      "${CALYPSO_SHERPA_ROOT}/lib64"
      "${CALYPSO_SHERPA_ROOT}/build/lib"
  )
  if(SHERPA_ONNX_INCLUDE_DIR AND SHERPA_ONNX_LIBRARY)
    target_compile_definitions(calypso_puck PRIVATE CALYPSO_HAS_SHERPA=1)
    target_include_directories(calypso_puck PRIVATE "${SHERPA_ONNX_INCLUDE_DIR}")
    target_link_libraries(calypso_puck PRIVATE "${SHERPA_ONNX_LIBRARY}")
    message(STATUS "sherpa-onnx found — offline voice ID enabled")
    message(STATUS "  include: ${SHERPA_ONNX_INCLUDE_DIR}")
    message(STATUS "  library: ${SHERPA_ONNX_LIBRARY}")
  else()
    message(WARNING "CALYPSO_SHERPA_ROOT set but sherpa-onnx not found — voice ID disabled")
  endif()
else()
  message(STATUS "CALYPSO_SHERPA_ROOT unset — offline voice ID compiled out")
endif()
