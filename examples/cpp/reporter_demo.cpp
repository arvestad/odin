// Direct Reporter usage: progress, info, warning, error messages
// Compile: g++ -std=c++17 -pthread -I../../cpp reporter_demo.cpp -o reporter_demo

#include "odin.hpp"
#include <chrono>
#include <thread>

int main() {
    odin::Reporter r("C++ pipeline", 100);

    for (int i = 0; i < 100; ++i) {
        std::this_thread::sleep_for(std::chrono::milliseconds(60));
        r.progress(i + 1);

        if (i == 20) r.info("Phase 1 complete");
        if (i == 49) r.warning("Memory usage climbing");
        if (i == 74) r.info("Phase 2 complete");
    }

    r.done(); // optional — destructor would call it anyway
}
