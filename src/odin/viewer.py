import asyncio
import json
import os
import select
import signal
import sys
import threading
from datetime import datetime

import aiohttp
from rich.console import Console
from rich.live import Live
from rich.table import Table

HTTP_PORT = 6271
console = Console()


def _fmt_eta(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        m, r = divmod(s, 60)
        return f"{m}m {r:02d}s"
    h, rem = divmod(s, 3600)
    return f"{h}h {rem // 60:02d}m"


def _status_style(status: str) -> str:
    return {
        "running": "green",
        "done": "dim",
        "failed": "bold red",
        "died": "bold red",
        "warning": "yellow",
        "error": "red",
    }.get(status, "white")


def _render(sessions: list[dict]) -> Table:
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("Host", style="cyan", no_wrap=True)
    table.add_column("Label", style="bold")
    table.add_column("Progress", min_width=20)
    table.add_column("ETA", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Message")

    for s in sessions:
        status = s.get("status", "?")
        value = s.get("value")
        total = s.get("total")

        if value is not None and total:
            pct = value / total
            bar_width = 20
            filled = int(bar_width * pct)
            bar = "█" * filled + "░" * (bar_width - filled)
            progress = f"{bar} {value}/{total}"
        elif value is not None:
            progress = f"{value} items"
        else:
            progress = ""

        eta = f"~{_fmt_eta(s['eta_seconds'])}" if s.get("eta_seconds") is not None else ""

        style = _status_style(status)

        last = s.get("last_message") or ""
        mtype = s.get("last_message_type")
        msg_colour = {"warning": "yellow", "error": "red"}.get(mtype or "", "")
        if last:
            text = f"[{msg_colour}]{last}[/{msg_colour}]" if msg_colour else last
            if not total:
                text = f"[bold]{text}[/bold]"
            ts = datetime.fromtimestamp(s["message_at"]).strftime("%H:%M:%S") if s.get("message_at") else ""
            message = f"{text} [dim]({ts})[/dim]" if ts else text
        else:
            message = ""

        table.add_row(
            s.get("host", ""),
            s.get("label", ""),
            progress,
            eta,
            f"[{style}]{status}[/{style}]",
            message,
        )
    return table


def _watch_keys(stop: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    """Background thread: set stop event when 'q' is pressed."""
    try:
        import tty
        import termios
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
        old = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            while not stop.is_set():
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch in ("q", "Q"):
                        loop.call_soon_threadsafe(stop.set)
                        break
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass  # not a TTY or platform lacks tty/termios


async def watch() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, stop.set)

    key_thread = threading.Thread(target=_watch_keys, args=(stop, loop), daemon=True)
    key_thread.start()

    url = f"ws://localhost:{HTTP_PORT}/ws"
    sessions: list[dict] = []

    with Live(console=console, refresh_per_second=4) as live:
        console.print(
            f"Watching Odin server at localhost:{HTTP_PORT} — press [bold]q[/bold] or Ctrl-C to quit",
            style="dim",
        )
        while not stop.is_set():
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.ws_connect(url) as ws:
                        while not stop.is_set():
                            try:
                                msg = await asyncio.wait_for(ws.receive(), timeout=0.5)
                            except asyncio.TimeoutError:
                                continue
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                sessions = data.get("sessions", [])
                                live.update(_render(sessions))
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except (aiohttp.ClientConnectorError, OSError):
                if not stop.is_set():
                    console.print("Server not available, retrying in 2s…", style="dim")
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        pass

    key_thread.join(timeout=0.5)
