#pragma once

// odin.hpp — C++ reporter for the Odin progress monitoring system
// Requires C++17 and POSIX (Linux, macOS)
//
// Basic usage:
//   odin::Reporter r("label", 100);   // label, optional total
//   r.progress(42);
//   r.info("some message");
//   r.done();                          // optional — destructor calls it too
//
//   for (auto& item : odin::track(container, "label")) { ... }

#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <iostream>
#include <mutex>
#include <optional>
#include <queue>
#include <sstream>
#include <string>
#include <thread>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

namespace odin {

namespace detail {

inline std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.size());
    for (unsigned char c : s) {
        if      (c == '"')  out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else                out += static_cast<char>(c);
    }
    return out;
}

inline std::string socket_path() {
    const char* home = std::getenv("HOME");
    return std::string(home ? home : "/tmp") + "/.odin";
}

inline std::string hostname() {
    char buf[256] = {};
    ::gethostname(buf, sizeof(buf) - 1);
    return buf;
}

} // namespace detail


class Reporter {
public:
    explicit Reporter(
        std::string label,
        std::optional<int> total = std::nullopt,
        std::function<void(const std::string&)> fallback = {}
    )
        : label_(std::move(label))
        , total_(total)
        , fd_(-1)
        , connected_(false)
        , running_(true)
        , done_called_(false)
    {
        if (fallback) {
            fallback_ = std::move(fallback);
        } else {
            fallback_ = [this](const std::string& msg) {
                std::cerr << "[odin:" << label_ << "] " << msg << "\n";
            };
        }
        sender_thread_ = std::thread(&Reporter::sender_loop, this);
        connect_to_server();
    }

    ~Reporter() { done(); }

    Reporter(const Reporter&) = delete;
    Reporter& operator=(const Reporter&) = delete;
    Reporter(Reporter&&) = delete;
    Reporter& operator=(Reporter&&) = delete;

    void progress(int value) {
        if (value < 0) {
            warning("progress() called with negative value ("
                    + std::to_string(value) + "), clamping to 0");
            value = 0;
        }
        enqueue("{\"type\":\"progress\",\"value\":" + std::to_string(value) + "}");
    }

    void info(const std::string& message) {
        enqueue("{\"type\":\"info\",\"message\":\"" + detail::json_escape(message) + "\"}");
    }

    void warning(const std::string& message) {
        enqueue("{\"type\":\"warning\",\"message\":\"" + detail::json_escape(message) + "\"}");
    }

    void error(const std::string& message) {
        enqueue("{\"type\":\"error\",\"message\":\"" + detail::json_escape(message) + "\"}");
    }

    void done() {
        if (done_called_.exchange(true)) return;
        enqueue("{\"type\":\"done\"}");
        stop_sender();
    }

private:
    std::string label_;
    std::optional<int> total_;
    std::function<void(const std::string&)> fallback_;

    int fd_;
    bool connected_;

    std::queue<std::string> queue_;
    std::mutex queue_mutex_;
    std::condition_variable queue_cv_;
    bool running_;
    std::thread sender_thread_;
    std::atomic<bool> done_called_;

    void connect_to_server() {
        int fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
        if (fd < 0) return;

        struct sockaddr_un addr{};
        addr.sun_family = AF_UNIX;
        std::string path = detail::socket_path();
        std::strncpy(addr.sun_path, path.c_str(), sizeof(addr.sun_path) - 1);

        if (::connect(fd, reinterpret_cast<struct sockaddr*>(&addr), sizeof(addr)) < 0) {
            ::close(fd);
            return;
        }

        fd_ = fd;
        connected_ = true;

        std::string hello = "{\"type\":\"hello\""
            ",\"label\":\""  + detail::json_escape(label_)           + "\""
            ",\"pid\":"      + std::to_string(::getpid())            +
            ",\"host\":\""   + detail::json_escape(detail::hostname()) + "\"";
        if (total_) hello += ",\"total\":" + std::to_string(*total_);
        hello += "}";
        send_raw(hello);
    }

    void send_raw(const std::string& msg) {
        if (fd_ < 0) return;
        std::string line = msg + "\n";
        if (::write(fd_, line.data(), line.size()) < 0) {
            std::cerr << "[odin:" << label_
                      << "] lost connection to server — falling back to stderr\n";
            ::close(fd_);
            fd_ = -1;
            connected_ = false;
        }
    }

    void enqueue(std::string msg) {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        queue_.push(std::move(msg));
        queue_cv_.notify_one();
    }

    void stop_sender() {
        {
            std::lock_guard<std::mutex> lock(queue_mutex_);
            running_ = false;
        }
        queue_cv_.notify_all();
        if (sender_thread_.joinable())
            sender_thread_.join();
        if (fd_ >= 0) { ::close(fd_); fd_ = -1; }
    }

    void sender_loop() {
        while (true) {
            std::string msg;
            {
                std::unique_lock<std::mutex> lock(queue_mutex_);
                queue_cv_.wait(lock, [this] { return !queue_.empty() || !running_; });
                if (queue_.empty()) break;
                msg = std::move(queue_.front());
                queue_.pop();
            }
            connected_ ? send_raw(msg) : fallback_(msg);
        }
        // Drain any messages enqueued before stop_sender() was called
        while (true) {
            std::string msg;
            {
                std::lock_guard<std::mutex> lock(queue_mutex_);
                if (queue_.empty()) break;
                msg = std::move(queue_.front());
                queue_.pop();
            }
            connected_ ? send_raw(msg) : fallback_(msg);
        }
    }
};


// track() — RAII range wrapper that reports progress automatically.
// Works with any container that has begin(), end(), and size().
// Requires C++17 (guaranteed copy elision for the return value).
//
// Example:
//   for (auto& item : odin::track(vec, "processing")) { ... }

template<typename Container>
class TrackRange {
public:
    TrackRange(Container& container, std::string label)
        : container_(container)
        , reporter_(std::move(label), static_cast<int>(std::size(container)))
    {}

    ~TrackRange() {
        if (std::uncaught_exceptions() > 0)
            reporter_.error("Iteration terminated by exception");
        // ~Reporter() calls done()
    }

    class Iterator {
    public:
        Iterator(Reporter& r, typename Container::iterator it, int idx)
            : reporter_(r), it_(it), idx_(idx) {}

        decltype(auto) operator*()  { return *it_; }
        decltype(auto) operator->() { return it_.operator->(); }

        Iterator& operator++() {
            ++it_;
            ++idx_;
            reporter_.progress(idx_);
            return *this;
        }

        bool operator!=(const Iterator& o) const { return it_ != o.it_; }

    private:
        Reporter& reporter_;
        typename Container::iterator it_;
        int idx_;
    };

    Iterator begin() { return {reporter_, container_.begin(), 0}; }
    Iterator end()   { return {reporter_, container_.end(),
                               static_cast<int>(std::size(container_))}; }

private:
    Container& container_;
    Reporter reporter_;
};

template<typename Container>
TrackRange<Container> track(Container& container, std::string label) {
    return TrackRange<Container>(container, std::move(label));
}

} // namespace odin
