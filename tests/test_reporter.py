import os
import socket
import threading
import time
from pathlib import Path

import pytest

from odin.reporter import Reporter, track

# Use a temp socket path so tests don't touch ~/.odin
TEST_SOCKET = Path("/tmp/odin_test.sock")


@pytest.fixture()
def mock_server():
    """A minimal server that collects received lines."""
    if TEST_SOCKET.exists():
        TEST_SOCKET.unlink()

    received: list[str] = []
    stop = threading.Event()

    def serve():
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(TEST_SOCKET))
        srv.listen(5)
        srv.settimeout(0.5)
        while not stop.is_set():
            try:
                conn, _ = srv.accept()
            except (socket.timeout, OSError):
                continue
            conn.settimeout(0.5)
            buf = b""
            while not stop.is_set():
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        received.append(line.decode())
                except (socket.timeout, OSError):
                    break
            conn.close()
        srv.close()
        if TEST_SOCKET.exists():
            TEST_SOCKET.unlink()

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    time.sleep(0.05)  # let socket bind
    yield received
    stop.set()
    t.join(timeout=2)


def make_reporter(label, total=None, monkeypatch=None):
    import odin.reporter as mod
    if monkeypatch:
        monkeypatch.setattr(mod, "SOCKET_PATH", TEST_SOCKET)
    r = Reporter.__new__(Reporter)
    import queue, threading
    r.label = label
    r.total = total
    r._fallback = lambda t: None
    r._sock = None
    r._queue = queue.SimpleQueue()
    r._connected = False
    r._thread = threading.Thread(target=r._sender, daemon=True)
    r._thread.start()

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(str(TEST_SOCKET))
    r._sock = sock
    r._connected = True
    r._send_raw({"type": "hello", "label": label, "pid": os.getpid(),
                  "host": socket.gethostname(), "total": total})
    return r


def test_fallback_when_no_server(tmp_path, monkeypatch):
    import odin.reporter as mod
    monkeypatch.setattr(mod, "SOCKET_PATH", tmp_path / "nosocket")
    messages = []
    r = Reporter("test", fallback=lambda m: messages.append(m))
    r.warning("hello")
    r.done()
    assert any("hello" in m for m in messages)


def test_track_basic(monkeypatch):
    import odin.reporter as mod
    monkeypatch.setattr(mod, "SOCKET_PATH", Path("/tmp/nonexistent_odin_xyz"))
    items = list(track([1, 2, 3], label="test"))
    assert items == [1, 2, 3]


def test_track_with_server(mock_server, monkeypatch):
    import odin.reporter as mod
    monkeypatch.setattr(mod, "SOCKET_PATH", TEST_SOCKET)

    items = list(track([10, 20, 30], label="mytrack"))
    assert items == [10, 20, 30]

    time.sleep(0.1)
    import json
    msgs = [json.loads(l) for l in mock_server]
    types = [m["type"] for m in msgs]
    assert types[0] == "hello"
    assert "progress" in types
    assert types[-1] == "done"
    progress_values = [m["value"] for m in msgs if m["type"] == "progress"]
    assert progress_values == [1, 2, 3]
