add_library(AppCore STATIC runner.cpp runner.hpp)
target_link_libraries(AppCore PRIVATE Domain)
