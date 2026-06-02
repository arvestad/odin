import json
import logging
import os
import queue
import socket
import sys
import threading
from pathlib import Path
from typing import Callable, Iterable, Iterator, TypeVar

SOCKET_PATH = Path.home() / ".odin"

T = TypeVar("T")


class Reporter:
    def __init__(
        self,
        label: str,
        total: int | None = None,
        fallback: Callable[[str], None] | None = None,
        logger: logging.Logger | None = None,
    ):
        self.label = label
        self.total = total
        if fallback is not None:
            self._fallback = fallback
        elif logger is not None:
            self._fallback = self._make_logger_fallback(logger)
        else:
            self._fallback = self._default_fallback
        self._logger = logger
        self._sock: socket.socket | None = None
        self._queue: queue.SimpleQueue[str | None] = queue.SimpleQueue()
        self._thread = threading.Thread(target=self._sender, daemon=True)
        self._connected = False
        self._connect()
        self._thread.start()

    def _default_fallback(self, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            print(raw, file=sys.stderr)
            return
        mtype = msg.get("type")
        if mtype == "progress":
            total = f"/{self.total}" if self.total else ""
            print(f"[odin:{self.label}] {msg.get('value', '?')}{total}", file=sys.stderr)
        elif mtype in ("info", "warning", "error"):
            print(f"[odin:{self.label}] {mtype.upper()}: {msg.get('message', '')}", file=sys.stderr)
        elif mtype == "done":
            print(f"[odin:{self.label}] done", file=sys.stderr)

    def _make_logger_fallback(self, logger: logging.Logger) -> Callable[[str], None]:
        def fallback(raw: str) -> None:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.info(raw)
                return
            mtype = msg.get("type")
            if mtype == "progress":
                total = f"/{self.total}" if self.total else ""
                logger.info(f"[{self.label}] {msg.get('value', '?')}{total}")
            elif mtype == "info":
                logger.info(f"[{self.label}] {msg.get('message', '')}")
            elif mtype == "warning":
                logger.warning(f"[{self.label}] {msg.get('message', '')}")
            elif mtype == "error":
                logger.error(f"[{self.label}] {msg.get('message', '')}")
            elif mtype == "done":
                logger.info(f"[{self.label}] done")
        return fallback

    def _connect(self) -> None:
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(str(SOCKET_PATH))
            self._sock = sock
            self._connected = True
            self._send_raw({"type": "hello", "label": self.label,
                            "pid": os.getpid(), "host": socket.gethostname(),
                            "total": self.total})
        except (FileNotFoundError, ConnectionRefusedError):
            self._connected = False

    def _send_raw(self, msg: dict) -> None:
        if self._sock is None:
            return
        try:
            self._sock.sendall((json.dumps(msg) + "\n").encode())
        except OSError:
            self._connected = False
            self._sock = None
            msg = f"[odin:{self.label}] lost connection to server — falling back to stderr"
            if self._logger is not None:
                self._logger.warning(msg)
            else:
                print(msg, file=sys.stderr)

    def _sender(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                break
            if self._connected:
                self._send_raw(json.loads(item))
            else:
                self._fallback(item)

    def _enqueue(self, msg: dict) -> None:
        self._queue.put(json.dumps(msg))

    def progress(self, value: int) -> None:
        self._enqueue({"type": "progress", "value": value})

    def info(self, message: str) -> None:
        self._enqueue({"type": "info", "message": message})

    def warning(self, message: str) -> None:
        self._enqueue({"type": "warning", "message": message})

    def error(self, message: str) -> None:
        self._enqueue({"type": "error", "message": message})

    def done(self) -> None:
        self._enqueue({"type": "done"})
        self._queue.put(None)  # stop sender thread
        self._thread.join()
        if self._sock:
            self._sock.close()

    def __enter__(self) -> "Reporter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.error(f"{exc_type.__name__}: {exc_val}")
        self.done()


def track(
    iterable: Iterable[T],
    label: str,
    total: int | None = None,
    fallback: Callable[[str], None] | None = None,
    logger: logging.Logger | None = None,
) -> Iterator[T]:
    if total is None:
        try:
            total = len(iterable)  # type: ignore[arg-type]
        except TypeError:
            pass
    r = Reporter(label, total=total, fallback=fallback, logger=logger)
    try:
        for i, item in enumerate(iterable):
            yield item
            r.progress(i + 1)
    except Exception as exc:
        r.error(f"{type(exc).__name__}: {exc}")
        raise
    finally:
        r.done()
