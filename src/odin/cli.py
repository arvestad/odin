import argparse
import asyncio
import json
import os
import signal
import socket
import sys
from pathlib import Path

SOCKET_PATH = Path.home() / ".odin"
PID_PATH = Path.home() / ".odin.pid"


def _send_oneshot(messages: list[dict]) -> None:
    """Connect, send a sequence of messages, disconnect. Used by shell subcommands."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(SOCKET_PATH))
        for msg in messages:
            sock.sendall((json.dumps(msg) + "\n").encode())
        sock.close()
    except (FileNotFoundError, ConnectionRefusedError):
        # Server not running — print to stderr as fallback
        for msg in messages:
            if msg.get("type") not in ("hello", "done"):
                print(f"[odin:{msg.get('type')}] {msg.get('message', msg.get('value', ''))}", file=sys.stderr)


def cmd_serve(args) -> None:
    from odin.server import run
    asyncio.run(run(retention=args.retention))


def cmd_stop(_args) -> None:
    if not PID_PATH.exists():
        print("No running Odin server found (no ~/.odin.pid).", file=sys.stderr)
        sys.exit(1)
    pid = int(PID_PATH.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"Odin server (pid {pid}) stopped.")
    except ProcessLookupError:
        print(f"No process with pid {pid} — cleaning up stale files.", file=sys.stderr)
        for path in (SOCKET_PATH, PID_PATH):
            if path.exists():
                path.unlink()


def cmd_watch(_args) -> None:
    from odin.viewer import watch
    asyncio.run(watch())


def cmd_progress(args) -> None:
    total = int(args.total) if args.total else None
    _send_oneshot([
        {"type": "hello", "label": args.label, "pid": os.getpid(),
         "host": socket.gethostname(), "total": total},
        {"type": "progress", "value": int(args.value)},
        {"type": "done"},
    ])


def cmd_info(args) -> None:
    _send_oneshot([
        {"type": "hello", "label": args.label, "pid": os.getpid(), "host": socket.gethostname()},
        {"type": "info", "message": args.message},
        {"type": "done"},
    ])


def cmd_warning(args) -> None:
    _send_oneshot([
        {"type": "hello", "label": args.label, "pid": os.getpid(), "host": socket.gethostname()},
        {"type": "warning", "message": args.message},
        {"type": "done"},
    ])


def cmd_error(args) -> None:
    _send_oneshot([
        {"type": "hello", "label": args.label, "pid": os.getpid(), "host": socket.gethostname()},
        {"type": "error", "message": args.message},
        {"type": "done"},
    ])


def main() -> None:
    parser = argparse.ArgumentParser(prog="odin", description="Odin progress reporting")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="Start the Odin server")
    p.add_argument("--retention", type=float, default=30.0,
                   metavar="SECONDS",
                   help="How long to keep finished/died sessions (0 = forever, default: 30)")
    sub.add_parser("stop", help="Stop a running Odin server")
    sub.add_parser("watch", help="Terminal viewer")

    p = sub.add_parser("progress", help="Report a progress value (shell use)")
    p.add_argument("label")
    p.add_argument("value")
    p.add_argument("total", nargs="?")

    p = sub.add_parser("info", help="Send an info message (shell use)")
    p.add_argument("label")
    p.add_argument("message")

    p = sub.add_parser("warning", help="Send a warning (shell use)")
    p.add_argument("label")
    p.add_argument("message")

    p = sub.add_parser("error", help="Send an error (shell use)")
    p.add_argument("label")
    p.add_argument("message")

    args = parser.parse_args()
    dispatch = {
        "serve": cmd_serve,
        "stop": cmd_stop,
        "watch": cmd_watch,
        "progress": cmd_progress,
        "info": cmd_info,
        "warning": cmd_warning,
        "error": cmd_error,
    }
    dispatch[args.command](args)
