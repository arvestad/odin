import io
import json
import socket
import threading
import time
from pathlib import Path

import pytest

import odin.reporter as reporter_mod
from odin import snakemake as sm

TEST_SOCKET = Path("/tmp/odin_test_snakemake.sock")


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


def _run_with_input(monkeypatch, capsys, lines, label="snakemake-test"):
    monkeypatch.setattr(reporter_mod, "SOCKET_PATH", TEST_SOCKET)
    monkeypatch.setattr("sys.stdin", io.StringIO("".join(lines)))
    sm.run(label=label)
    return capsys.readouterr()


# --- Regex unit tests ---------------------------------------------------

@pytest.mark.parametrize("line,expected", [
    ("5 of 20 steps (25%) done", (5, 20)),
    ("15 of 30 steps (50%) done", (15, 30)),
    ("1 of 1 steps (100%) done", (1, 1)),
])
def test_progress_re_matches(line, expected):
    m = sm.PROGRESS_RE.search(line)
    assert m is not None
    assert (int(m.group(1)), int(m.group(2))) == expected


@pytest.mark.parametrize("line", [
    "Building DAG of jobs...",
    "Job stats:",
    "Finished job 3.",
])
def test_progress_re_does_not_match(line):
    assert sm.PROGRESS_RE.search(line) is None


@pytest.mark.parametrize("line", [
    "Error in rule fastqc:",
    "WorkflowError:",
    "RuleException in line 10 of Snakefile:",
    "MissingInputException in rule align:",
    "Exiting because a job execution failed. Look above for error message",
])
def test_error_re_matches(line):
    assert sm.ERROR_RE.search(line) is not None


@pytest.mark.parametrize("line", [
    "5 of 20 steps (25%) done",
    "Finished job 3.",
    "Some unrelated log line mentioning an error deep inside it",
])
def test_error_re_does_not_match(line):
    assert sm.ERROR_RE.search(line) is None


# --- Streaming behaviour --------------------------------------------------

def test_passthrough_and_progress(mock_server, monkeypatch, capsys):
    lines = [
        "Building DAG of jobs...\n",
        "5 of 20 steps (25%) done\n",
        "10 of 20 steps (50%) done\n",
    ]
    out = _run_with_input(monkeypatch, capsys, lines)
    assert out.out == "".join(lines)

    time.sleep(0.1)
    msgs = [json.loads(line) for line in mock_server]
    assert msgs[0]["type"] == "hello"
    assert msgs[0]["total"] == 20
    progress_values = [m["value"] for m in msgs if m["type"] == "progress"]
    assert progress_values == [5, 10]
    assert msgs[-1]["type"] == "done"


def test_error_line_reported(mock_server, monkeypatch, capsys):
    lines = ["Error in rule fastqc:\n", "    jobid: 2\n"]
    out = _run_with_input(monkeypatch, capsys, lines)
    assert out.out == "".join(lines)

    time.sleep(0.1)
    msgs = [json.loads(line) for line in mock_server]
    assert msgs[0]["type"] == "hello"
    assert msgs[0]["total"] is None
    error_msgs = [m for m in msgs if m["type"] == "error"]
    assert len(error_msgs) == 1
    assert error_msgs[0]["message"] == "Error in rule fastqc:"
    assert msgs[-1]["type"] == "done"


def test_non_matching_lines_no_connection(monkeypatch, capsys):
    class ExplodingReporter:
        def __init__(self, *a, **k):
            raise AssertionError("Reporter should not be created for non-matching output")

    monkeypatch.setattr(sm, "Reporter", ExplodingReporter)
    lines = [
        "Building DAG of jobs...\n",
        "Job stats:\n",
        "Finished job 3.\n",
    ]
    out = _run_with_input(monkeypatch, capsys, lines)
    assert out.out == "".join(lines)
