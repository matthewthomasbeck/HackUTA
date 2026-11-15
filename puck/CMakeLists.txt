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
)

target_include_directories(calypso_puck PRIVATE include)

find_package(Threads REQUIRED)
target_link_libraries(calypso_puck PRIVATE Threads::Threads)
