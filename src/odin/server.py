import asyncio
import json
import os
import signal
import socket
import time
from collections import deque
from pathlib import Path

PID_PATH = Path.home() / ".odin.pid"

BUFFER_SIZE = 10

from aiohttp import web
import aiohttp

SOCKET_PATH = Path.home() / ".odin"
HTTP_PORT = 6271


class Session:
    def __init__(self, host: str, pid: int, label: str, total: int | None):
        self.id = f"{host}:{pid}:{label}"
        self.host = host
        self.pid = pid
        self.label = label
        self.total = total
        self.value: int | None = None
        self.status = "running"
        self.last_message: str | None = None
        self.last_message_type: str | None = None
        self.message_at: float | None = None
        self.updated = time.time()
        self.completed_at: float | None = None
        self.eta_seconds: float | None = None
        self.suspended: bool = False
        self._progress_buffer: deque[tuple[float, int]] = deque(maxlen=BUFFER_SIZE)

    def update_eta(self) -> None:
        if self.total is None or self.value is None:
            return
        self._progress_buffer.append((time.time(), self.value))
        if len(self._progress_buffer) < BUFFER_SIZE:
            return
        t0, v0 = self._progress_buffer[0]
        t1, v1 = self._progress_buffer[-1]
        elapsed = t1 - t0
        delta_v = v1 - v0
        if elapsed <= 0 or delta_v <= 0:
            self.eta_seconds = None
            return
        rate = delta_v / elapsed
        self.eta_seconds = (self.total - self.value) / rate

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "host": self.host,
            "pid": self.pid,
            "label": self.label,
            "total": self.total,
            "value": self.value,
            "status": self.status,
            "last_message": self.last_message,
            "last_message_type": self.last_message_type,
            "updated": self.updated,
            "message_at": self.message_at,
            "eta_seconds": self.eta_seconds,
        }


class OdinServer:
    def __init__(self, retention: float = 30.0):
        self.sessions: dict[str, Session] = {}
        self.ws_clients: set[web.WebSocketResponse] = set()
        self.retention = retention  # seconds; 0 = keep forever

    async def broadcast(self):
        if not self.ws_clients:
            return
        payload = json.dumps({"sessions": [s.to_dict() for s in self.sessions.values()]})
        dead = set()
        for ws in self.ws_clients:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.add(ws)
        self.ws_clients -= dead

    async def handle_reporter(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        session: Session | None = None
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = json.loads(line.decode())
                except json.JSONDecodeError:
                    continue

                mtype = msg.get("type")

                if mtype == "hello":
                    new = Session(
                        host=msg.get("host", socket.gethostname()),
                        pid=msg.get("pid", 0),
                        label=msg.get("label", "unknown"),
                        total=msg.get("total"),
                    )
                    # Reconnecting shell reporters: preserve progress state
                    existing = self.sessions.get(new.id)
                    if existing is not None and existing.suspended:
                        new.value = existing.value
                        new.last_message = existing.last_message
                        new.last_message_type = existing.last_message_type
                        new.message_at = existing.message_at
                        new.eta_seconds = existing.eta_seconds
                    session = new
                    self.sessions[session.id] = session
                    await self.broadcast()

                elif session is not None:
                    session.updated = time.time()

                    if mtype == "progress":
                        session.value = msg.get("value")
                        session.status = "running"
                        session.update_eta()
                    elif mtype == "info":
                        session.last_message = msg.get("message")
                        session.last_message_type = "info"
                        session.message_at = time.time()
                    elif mtype == "warning":
                        session.last_message = msg.get("message")
                        session.last_message_type = "warning"
                        session.message_at = time.time()
                        session.status = "warning"
                    elif mtype == "error":
                        session.last_message = msg.get("message")
                        session.last_message_type = "error"
                        session.message_at = time.time()
                        session.status = "error"
                    elif mtype == "suspend":
                        session.suspended = True
                        break  # connection will close; don't mark as died
                    elif mtype == "done":
                        session.status = "failed" if session.status == "error" else "done"
                        session.completed_at = time.time()
                        await self.broadcast()
                        break

                    await self.broadcast()

        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass
        finally:
            writer.close()
            if session is not None and session.status == "running" and not session.suspended:
                session.status = "died"
                session.completed_at = time.time()
                session.updated = time.time()
                await self.broadcast()

    async def cleanup_loop(self):
        while True:
            await asyncio.sleep(5)
            if self.retention == 0:
                continue
            cutoff = time.time() - self.retention
            expired = [sid for sid, s in self.sessions.items()
                       if s.completed_at is not None and s.completed_at < cutoff]
            if expired:
                for sid in expired:
                    del self.sessions[sid]
                await self.broadcast()

    async def handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.ws_clients.add(ws)
        # Send current state immediately on connect
        await ws.send_str(json.dumps({"sessions": [s.to_dict() for s in self.sessions.values()]}))
        try:
            async for _ in ws:
                pass  # clients don't send anything
        finally:
            self.ws_clients.discard(ws)
        return ws

    async def handle_state(self, request: web.Request) -> web.Response:
        return web.json_response({"sessions": [s.to_dict() for s in self.sessions.values()]})

    async def handle_index(self, request: web.Request) -> web.Response:
        index = Path(__file__).parent / "static" / "index.html"
        return web.Response(text=index.read_text(), content_type="text/html")

    def _cleanup(self) -> None:
        for path in (SOCKET_PATH, PID_PATH):
            if path.exists():
                path.unlink()

    async def start(self):
        for path in (SOCKET_PATH, PID_PATH):
            if path.exists():
                path.unlink()

        unix_server = await asyncio.start_unix_server(
            self.handle_reporter, path=str(SOCKET_PATH)
        )
        os.chmod(SOCKET_PATH, 0o600)

        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/state", self.handle_state)
        app.router.add_get("/ws", self.handle_ws)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "localhost", HTTP_PORT)
        await site.start()

        # Write pid only after all bindings succeed
        PID_PATH.write_text(str(os.getpid()))

        shutdown = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown.set)

        retention_msg = f"{self.retention}s" if self.retention else "forever"
        print(f"Odin server listening on {SOCKET_PATH}")
        print(f"Dashboard: http://localhost:{HTTP_PORT}/")
        print(f"Finished sessions retained for: {retention_msg}")

        asyncio.create_task(self.cleanup_loop())
        try:
            async with unix_server:
                await shutdown.wait()
        finally:
            self._cleanup()
            await runner.cleanup()  # releases port 6271


async def run(retention: float = 30.0):
    server = OdinServer(retention=retention)
    await server.start()
