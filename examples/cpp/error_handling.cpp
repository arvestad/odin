// Error handling: exceptions are automatically reported via RAII.
// If the loop throws, the viewer shows "failed" in red.
// Compile: g++ -std=c++17 -pthread -I../../cpp error_handling.cpp -o error_handling

#include "odin.hpp"
#include <chrono>
#include <stdexcept>
#include <thread>
#include <vector>

void process(int i) {
    if (i == 60) throw std::runtime_error("unexpected value at step 60");
}

int main() {
    std::vector<int> data(100);
    for (int i = 0; i < 100; ++i) data[i] = i;

    try {
        for (auto item : odin::track(data, "risky job")) {
            std::this_thread::sleep_for(std::chrono::milliseconds(40));
            process(item);
        }
    } catch (const std::exception& e) {
        // odin already reported the error and marked the job as failed
        return 1;
    }
}
