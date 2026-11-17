add_library(Physics STATIC physics.cpp)
target_link_libraries(Physics PRIVATE Math)
