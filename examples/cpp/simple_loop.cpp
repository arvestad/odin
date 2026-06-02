// Simple example: wrap a vector with odin::track()
// Compile: g++ -std=c++17 -pthread -I../../cpp simple_loop.cpp -o simple_loop

#include "odin.hpp"
#include <chrono>
#include <thread>
#include <vector>

int main() {
    std::vector<int> data(100);
    for (int i = 0; i < 100; ++i) data[i] = i;

    for (auto item : odin::track(data, "simple loop")) {
        (void)item;
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
}
