cmake_minimum_required(VERSION 3.20)
project(ArchMindExternal LANGUAGES CXX)
add_executable(App main.cpp)
target_link_libraries(App PRIVATE definitely_not_real_lib)
