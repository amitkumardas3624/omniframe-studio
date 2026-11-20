cmake_minimum_required(VERSION 3.18)
project(omniframe_native LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_omniframe_native omniframe_native.cpp)
target_compile_features(_omniframe_native PRIVATE cxx_std_17)

install(TARGETS _omniframe_native LIBRARY DESTINATION omniframe/_native RUNTIME DESTINATION omniframe/_native)
