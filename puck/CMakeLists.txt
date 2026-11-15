cmake_minimum_required(VERSION 3.16)
project(calypso_puck LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

option(CALYPSO_BUILD_TESTS "Build puck unit tests" OFF)

add_library(calypso_core STATIC
  src/who_filter.cpp
  src/config.cpp
  src/capture.cpp
  src/audio_gain.cpp
  src/backend_link.cpp
  src/models.cpp
  src/state_machine.cpp
  src/connection_listener.cpp
  src/accelerators.cpp
  src/phone_link.cpp
  src/who_json.cpp
  src/offline_buffer.cpp
  src/voice_gallery.cpp
  src/gallery_json.cpp
  src/people_json.cpp
  src/wav.cpp
  src/util.cpp
  src/segment_spool.cpp
  src/clock_sync.cpp
  src/segmenter.cpp
  src/uploader.cpp
)
target_include_directories(calypso_core PUBLIC include)

add_executable(calypso_puck main.cpp)
target_link_libraries(calypso_puck PRIVATE calypso_core)

add_executable(calypso_enroll enroll_main.cpp)
target_link_libraries(calypso_enroll PRIVATE calypso_core)

find_package(Threads REQUIRED)
find_package(CURL REQUIRED)
target_link_libraries(calypso_core PUBLIC Threads::Threads CURL::libcurl)

# ALSA on the Pi / Linux. macOS can still build with MIC_DEVICE=sine.
find_package(ALSA)
if(ALSA_FOUND)
  target_compile_definitions(calypso_core PUBLIC CALYPSO_HAS_ALSA=1)
  target_link_libraries(calypso_core PUBLIC ALSA::ALSA)
  message(STATUS "ALSA found — real mic capture enabled")
else()
  message(STATUS "ALSA not found — use MIC_DEVICE=sine for online smoke tests")
endif()

# sherpa-onnx for Titanet-small. Pass either the repo root OR the build dir:
#   -DCALYPSO_SHERPA_ROOT=$HOME/sherpa-onnx
#   -DCALYPSO_SHERPA_ROOT=$HOME/sherpa-onnx/build
set(CALYPSO_SHERPA_ROOT "" CACHE PATH "sherpa-onnx repo root or build dir")
if(CALYPSO_SHERPA_ROOT)
  get_filename_component(_sherpa_root "${CALYPSO_SHERPA_ROOT}" ABSOLUTE)
  # If they pointed at .../build, also search the parent repo for headers.
  get_filename_component(_sherpa_parent "${_sherpa_root}" DIRECTORY)

  find_path(SHERPA_ONNX_INCLUDE_DIR
    NAMES sherpa-onnx/c-api/c-api.h
    HINTS
      "${_sherpa_root}"
      "${_sherpa_root}/include"
      "${_sherpa_parent}"
      "${_sherpa_parent}/include"
    NO_DEFAULT_PATH
  )
  find_library(SHERPA_ONNX_LIBRARY
    NAMES sherpa-onnx-c-api
    HINTS
      "${_sherpa_root}/lib"
      "${_sherpa_root}/lib64"
      "${_sherpa_parent}/build/lib"
      "${_sherpa_root}/build/lib"
    NO_DEFAULT_PATH
  )
  # onnxruntime usually sits next to the sherpa libs in the same build/lib.
  find_library(ONNXRUNTIME_LIBRARY
    NAMES onnxruntime
    HINTS
      "${_sherpa_root}/lib"
      "${_sherpa_root}/lib64"
      "${_sherpa_parent}/build/lib"
      "${_sherpa_root}/build/lib"
    NO_DEFAULT_PATH
  )

  if(SHERPA_ONNX_INCLUDE_DIR AND SHERPA_ONNX_LIBRARY)
    target_compile_definitions(calypso_core PUBLIC CALYPSO_HAS_SHERPA=1)
    target_include_directories(calypso_core PUBLIC "${SHERPA_ONNX_INCLUDE_DIR}")
    target_link_libraries(calypso_core PUBLIC "${SHERPA_ONNX_LIBRARY}")
    if(ONNXRUNTIME_LIBRARY)
      target_link_libraries(calypso_core PUBLIC "${ONNXRUNTIME_LIBRARY}")
    endif()
    # So ./build/calypso_puck finds libsherpa-*.so at runtime without LD_LIBRARY_PATH.
    get_filename_component(_sherpa_libdir "${SHERPA_ONNX_LIBRARY}" DIRECTORY)
    set_target_properties(calypso_puck PROPERTIES
      BUILD_RPATH "${_sherpa_libdir}"
      INSTALL_RPATH "${_sherpa_libdir}"
    )
    message(STATUS "sherpa-onnx found — offline voice ID enabled")
    message(STATUS "  include: ${SHERPA_ONNX_INCLUDE_DIR}")
    message(STATUS "  library: ${SHERPA_ONNX_LIBRARY}")
    if(ONNXRUNTIME_LIBRARY)
      message(STATUS "  onnxruntime: ${ONNXRUNTIME_LIBRARY}")
    endif()
  else()
    message(WARNING "CALYPSO_SHERPA_ROOT set but sherpa-onnx not found — voice ID disabled")
    message(WARNING "  looked under: ${_sherpa_root} and ${_sherpa_parent}")
    message(WARNING "  include: ${SHERPA_ONNX_INCLUDE_DIR}")
    message(WARNING "  library: ${SHERPA_ONNX_LIBRARY}")
    message(WARNING "  tip: ls ~/sherpa-onnx/sherpa-onnx/c-api/c-api.h")
    message(WARNING "        ls ~/sherpa-onnx/build/lib/libsherpa-onnx-c-api*")
  endif()
else()
  message(STATUS "CALYPSO_SHERPA_ROOT unset — offline voice ID compiled out")
endif()

# Google Coral USB Edge TPU (libedgetpu + TFLite). Same binary layout as Whisker:
#   -DENABLE_CORAL=ON
#   -DTENSORFLOW_SOURCE_DIR=.../third_party/tensorflow
#   -DTFLITE_BINARY_DIR=.../third_party/tflite_build
#   -DEDGETPU_INCLUDE=.../third_party/coral/include
# Without ENABLE_CORAL the Coral *control plane* still builds (compat host
# delegate); live Invoke needs the stick + HAS_EDGETPU.
option(ENABLE_CORAL "Link libedgetpu + TFLite for live Edge TPU Invoke" OFF)
if(ENABLE_CORAL)
  if(NOT TENSORFLOW_SOURCE_DIR)
    if(DEFINED ENV{TENSORFLOW_SOURCE_DIR})
      set(TENSORFLOW_SOURCE_DIR "$ENV{TENSORFLOW_SOURCE_DIR}")
    else()
      message(FATAL_ERROR "ENABLE_CORAL=ON needs TENSORFLOW_SOURCE_DIR")
    endif()
  endif()
  if(NOT EDGETPU_INCLUDE)
    if(DEFINED ENV{EDGETPU_INCLUDE})
      set(EDGETPU_INCLUDE "$ENV{EDGETPU_INCLUDE}")
    else()
      set(EDGETPU_INCLUDE "${CMAKE_SOURCE_DIR}/third_party/coral/include")
    endif()
  endif()
  if(NOT EXISTS "${EDGETPU_INCLUDE}/edgetpu.h")
    message(FATAL_ERROR "edgetpu.h not found at ${EDGETPU_INCLUDE}")
  endif()
  if(NOT TFLITE_BINARY_DIR)
    if(DEFINED ENV{TFLITE_BINARY_DIR})
      set(TFLITE_BINARY_DIR "$ENV{TFLITE_BINARY_DIR}")
    else()
      set(TFLITE_BINARY_DIR "${CMAKE_SOURCE_DIR}/third_party/tflite_build")
    endif()
  endif()

  if(DEFINED ENV{EDGETPU_LIB} AND EXISTS "$ENV{EDGETPU_LIB}")
    set(EDGETPU_LIB "$ENV{EDGETPU_LIB}")
  else()
    find_library(EDGETPU_LIB
      NAMES edgetpu edgetpu.so.1 libedgetpu.so.1
      PATHS /usr/lib /usr/lib/aarch64-linux-gnu /usr/lib/arm-linux-gnueabihf
            /usr/local/lib
      REQUIRED
    )
  endif()
  find_library(LIBUSB_LIB NAMES usb-1.0)

  set(_tflite_a "${TFLITE_BINARY_DIR}/libtensorflow-lite.a")
  if(NOT EXISTS "${_tflite_a}")
    message(FATAL_ERROR "Prebuilt TFLite not found: ${_tflite_a}")
  endif()

  file(GLOB_RECURSE _tflite_raw_libs "${TFLITE_BINARY_DIR}/*.a")
  set(_tflite_static_libs "")
  foreach(_lib ${_tflite_raw_libs})
    get_filename_component(_name "${_lib}" NAME)
    if(_name MATCHES "fft4f2d")
      continue()
    endif()
    if(_name MATCHES "_test\\.a$" OR _name MATCHES "benchmark")
      continue()
    endif()
    list(APPEND _tflite_static_libs "${_lib}")
  endforeach()
  list(REMOVE_DUPLICATES _tflite_static_libs)

  target_compile_definitions(calypso_core PUBLIC CALYPSO_HAS_EDGETPU=1)
  target_include_directories(calypso_core PUBLIC
    "${TENSORFLOW_SOURCE_DIR}"
    "${EDGETPU_INCLUDE}"
  )
  if(EXISTS "${TFLITE_BINARY_DIR}/flatbuffers/include")
    target_include_directories(calypso_core PUBLIC
      "${TFLITE_BINARY_DIR}/flatbuffers/include")
  endif()
  target_link_libraries(calypso_core PUBLIC
    -Wl,--start-group
    ${_tflite_static_libs}
    -Wl,--end-group
    "${EDGETPU_LIB}"
    dl
  )
  if(LIBUSB_LIB)
    target_link_libraries(calypso_core PUBLIC "${LIBUSB_LIB}")
  endif()
  message(STATUS "Coral Edge TPU enabled (live Invoke)")
  message(STATUS "  edgetpu: ${EDGETPU_LIB}")
  message(STATUS "  tflite:  ${_tflite_a}")
else()
  message(STATUS "ENABLE_CORAL=OFF — Coral compat path only (no libedgetpu link)")
endif()

if(CALYPSO_BUILD_TESTS)
  enable_testing()
  add_executable(test_segment_spool tests/test_segment_spool.cpp)
  target_link_libraries(test_segment_spool PRIVATE calypso_core)
  add_test(NAME segment_spool COMMAND test_segment_spool)
  add_executable(test_uploader tests/test_uploader.cpp)
  target_link_libraries(test_uploader PRIVATE calypso_core)
  add_test(NAME uploader COMMAND test_uploader)
  add_executable(test_audio_gain tests/test_audio_gain.cpp)
  target_link_libraries(test_audio_gain PRIVATE calypso_core)
  add_test(NAME audio_gain COMMAND test_audio_gain)
  add_executable(test_who_filter tests/test_who_filter.cpp)
  target_link_libraries(test_who_filter PRIVATE calypso_core)
  add_test(NAME who_filter COMMAND test_who_filter)
  add_executable(test_people_json tests/test_people_json.cpp)
  target_link_libraries(test_people_json PRIVATE calypso_core)
  add_test(NAME people_json COMMAND test_people_json)
endif()
