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
    if PID_PATH.exists():
        pid = int(PID_PATH.read_text().strip())
        try:
            os.kill(pid, 0)  # check if process is alive
            print(
                f"An Odin server is already running (pid {pid}).\n"
                f"  To stop it:   odin stop\n"
                f"  To view it:   odin watch  or  http://localhost:6271",
                file=sys.stderr,
            )
            sys.exit(1)
        except ProcessLookupError:
            pass  # stale pid file — let the server clean it up and start normally

    from odin.server import run
    asyncio.run(run(retention=args.retention))


def cmd_stop(_args) -> None:
    if not PID_PATH.exists():
        print("No running Odin server found (no ~/.odin.pid).", file=sys.stderr)
        sys.exit(1)
    pid = int(PID_PATH.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for the process to exit so the port is free before returning
        for _ in range(20):
            import time
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        print(f"Odin server (pid {pid}) stopped.")
    except ProcessLookupError:
        print(f"No process with pid {pid} — cleaning up stale files.", file=sys.stderr)
        for path in (SOCKET_PATH, PID_PATH):
            if path.exists():
                path.unlink()


def cmd_watch(_args) -> None:
    from odin.viewer import watch
    try:
        asyncio.run(watch())
    except KeyboardInterrupt:
        pass


def _shell_hello(label: str, total: int | None = None) -> dict:
    # Use the parent shell's PID so all odin calls from the same script
    # share one session panel.
    return {"type": "hello", "label": label, "pid": os.getppid(),
            "host": socket.gethostname(), "total": total}


def cmd_progress(args) -> None:
    total = int(args.total) if args.total else None
    _send_oneshot([
        _shell_hello(args.label, total),
        {"type": "progress", "value": int(args.value)},
        {"type": "suspend"},
    ])


def cmd_info(args) -> None:
    _send_oneshot([
        _shell_hello(args.label),
        {"type": "info", "message": args.message},
        {"type": "suspend"},
    ])


def cmd_warning(args) -> None:
    _send_oneshot([
        _shell_hello(args.label),
        {"type": "warning", "message": args.message},
        {"type": "suspend"},
    ])


def cmd_error(args) -> None:
    _send_oneshot([
        _shell_hello(args.label),
        {"type": "error", "message": args.message},
        {"type": "suspend"},
    ])


def cmd_done(args) -> None:
    _send_oneshot([
        _shell_hello(args.label),
        {"type": "done"},
    ])


def main() -> None:
    from odin import __version__
    parser = argparse.ArgumentParser(prog="odin", description="Odin progress reporting")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
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

    p = sub.add_parser("done", help="Mark a shell session as finished (shell use)")
    p.add_argument("label")

    args = parser.parse_args()
    dispatch = {
        "serve": cmd_serve,
        "stop": cmd_stop,
        "watch": cmd_watch,
        "progress": cmd_progress,
        "info": cmd_info,
        "warning": cmd_warning,
        "error": cmd_error,
        "done": cmd_done,
    }
    dispatch[args.command](args)
