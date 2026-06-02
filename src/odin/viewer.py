import asyncio
import json
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


async def watch() -> None:
    url = f"ws://localhost:{HTTP_PORT}/ws"
    sessions: list[dict] = []

    with Live(console=console, refresh_per_second=4) as live:
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url) as ws:
                        console.print(f"Connected to Odin server at localhost:{HTTP_PORT}", style="dim")
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                sessions = data.get("sessions", [])
                                live.update(_render(sessions))
                            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                                break
            except (aiohttp.ClientConnectorError, OSError):
                live.update(_render(sessions))
                console.print("Server not available, retrying in 2s…", style="dim")
                await asyncio.sleep(2)
