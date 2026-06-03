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

SORT_KEYS  = {"t", "l", "p", "s", "m"}
SORT_LABEL = {"t": "Started", "l": "Label", "p": "Progress", "s": "Status", "m": "Message"}
SORT_NATURAL_DESC = {"p"}  # highest progress first by default
STATUS_PRIORITY = {"died": 0, "failed": 1, "error": 2, "warning": 3, "running": 4, "done": 5}


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


def _sort_sessions(sessions: list[dict], key: str, desc: bool) -> list[dict]:
    def sort_key(s: dict):
        if key == "t":
            return s.get("created_at") or 0
        if key == "l":
            return (s.get("label") or "").lower()
        if key == "p":
            value = s.get("value") or 0
            total = s.get("total")
            return value / total if total else value
        if key == "s":
            return STATUS_PRIORITY.get(s.get("status", "running"), 4)
        if key == "m":
            return (s.get("last_message") or "").lower()
        return 0
    return sorted(sessions, key=sort_key, reverse=desc)


def _render(sessions: list[dict], sort_key: str = "t", sort_desc: bool = False) -> Table:
    arrow = "↓" if sort_desc else "↑"
    hints = "  ·  ".join(
        f"[bold]{k}[/bold] {SORT_LABEL[k]}{' ' + arrow if k == sort_key else ''}"
        for k in ("t", "l", "p", "s", "m")
    )
    table = Table(
        show_header=True, header_style="bold", expand=True,
        caption=f" {hints}  ·  [bold]q[/bold] quit",
        caption_justify="left",
    )
    table.add_column("Host", style="cyan", no_wrap=True)
    table.add_column("Label", style="bold")
    table.add_column("Progress", min_width=20)
    table.add_column("ETA", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Message")

    for s in _sort_sessions(sessions, sort_key, sort_desc):
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


def _watch_keys(
    stop: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
    sort_state: dict,
) -> None:
    """Background thread: handle q (quit) and t/l/p/s/m (sort) keypresses."""
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
                    elif ch in SORT_KEYS:
                        if sort_state["key"] == ch:
                            sort_state["desc"] = not sort_state["desc"]
                        else:
                            sort_state["key"] = ch
                            sort_state["desc"] = ch in SORT_NATURAL_DESC
                        sort_state["changed"] = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    except Exception:
        pass


async def watch() -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, stop.set)

    sort_state: dict = {"key": "t", "desc": False, "changed": False}

    key_thread = threading.Thread(
        target=_watch_keys, args=(stop, loop, sort_state), daemon=True
    )
    key_thread.start()

    url = f"ws://localhost:{HTTP_PORT}/ws"
    sessions: list[dict] = []

    def current_render() -> Table:
        return _render(sessions, sort_state["key"], sort_state["desc"])

    with Live(console=console, refresh_per_second=4) as live:
        console.print(
            f"Watching Odin server at localhost:{HTTP_PORT} — "
            "press [bold]t/l/p/s/m[/bold] to sort · [bold]q[/bold] or Ctrl-C to quit",
            style="dim",
        )
        while not stop.is_set():
            try:
                async with aiohttp.ClientSession() as http:
                    async with http.ws_connect(url) as ws:
                        while not stop.is_set():
                            try:
                                msg = await asyncio.wait_for(ws.receive(), timeout=0.2)
                            except asyncio.TimeoutError:
                                if sort_state["changed"]:
                                    sort_state["changed"] = False
                                    live.update(current_render())
                                continue
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                sessions = data.get("sessions", [])
                                sort_state["changed"] = False
                                live.update(current_render())
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
