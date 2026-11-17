add_library(Simulation STATIC simulation.cpp)
target_link_libraries(Simulation PRIVATE Physics Math)
