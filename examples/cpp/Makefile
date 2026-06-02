CXX      ?= g++
CXXFLAGS ?= -std=c++17 -pthread -I../../cpp -Wall -Wextra -O2

TARGETS = simple_loop reporter_demo error_handling

.PHONY: all clean

all: $(TARGETS)

%: %.cpp ../../cpp/odin.hpp
	$(CXX) $(CXXFLAGS) $< -o $@

clean:
	rm -f $(TARGETS)
