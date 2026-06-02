# Odin

**Lightweight progress reporting for long-running computations.**

_Experimental release!_

Odin lets you monitor running programs — progress bars, warnings, errors — from a browser or terminal, with almost no extra code. Start a server, add two lines to your script, and watch it from anywhere.

```python
from odin import track

for item in track(my_list, label="processing"):
    do_work(item)
```

---

## Features

- **Minimal API** — wrapping an existing loop takes one line
- **Live browser dashboard** — auto-updating, no page refreshes
- **Terminal viewer** — `odin watch` for a rich live table in your terminal
- **Multi-language** — Python reporter library; shell one-liners via the `odin` CLI
- **Graceful fallback** — if no server is running, output goes to stderr (or your logger); your code keeps working
- **Process death detection** — reporters that crash or are killed are automatically marked as died
- **ETA estimation** — time-remaining shown once enough data has accumulated
- **Integrates with Python logging** — pass a `logger=` argument and Odin uses it as the fallback

---

## Installation

```bash
pip install odin
```

Requires Python 3.10+.

---

## Quickstart

**1. Start the server**

```bash
odin serve
```

Open `http://localhost:6271` in a browser. Or run `odin watch` in a second terminal for a terminal view.

**2. Report from Python**

Wrap any iterable with `track()`:

```python
from odin import track

for item in track(my_list, label="training"):
    process(item)
```

Or use `Reporter` directly for more control:

```python
from odin import Reporter

r = Reporter("simulation", total=1000)
for i in range(1000):
    run_step(i)
    r.progress(i + 1)
    if something_odd:
        r.warning("Step took longer than expected")
r.done()
```

Use it as a context manager and exceptions are reported automatically:

```python
with Reporter("risky job", total=100) as r:
    for i in range(100):
        r.progress(i + 1)
        do_work(i)          # if this raises, the error is reported before propagating
```

**3. Stop the server**

```bash
odin stop
```

---

## Shell usage

Report progress from shell scripts using the `odin` CLI:

```bash
odin progress "pipeline" 1 5
odin info     "pipeline" "Phase 1 complete"
odin warning  "pipeline" "Disk usage above 80%"
odin error    "pipeline" "Input file missing"
odin progress "pipeline" 5 5
```

---

## Integration with Python logging

Pass a standard `logging.Logger` and Odin uses it as the fallback when no server is running. Users who don't know about Odin get normal log output; users with a server running get the full dashboard.

```python
import logging
from odin import Reporter, track

log = logging.getLogger(__name__)

r = Reporter("job", total=100, logger=log)
# or
for item in track(data, label="job", logger=log):
    process(item)
```

---

## Message types

| Method | Meaning |
|---|---|
| `r.progress(value)` | Update progress (0 … total) |
| `r.info(message)` | Informational note |
| `r.warning(message)` | Something unexpected but non-fatal |
| `r.error(message)` | An error occurred |
| `r.done()` | Job finished cleanly (optional — the server also detects clean exit) |

---

## Server options

```
odin serve [--retention SECONDS]
```

`--retention` controls how long finished or died sessions remain visible before being removed (default: 30 seconds). Use `0` to keep them until the server restarts.

---

## How it works

Reporters connect to a Unix socket (`~/.odin`) on startup and hold the connection open. The server keeps only the latest state for each reporter and pushes updates to connected viewers over WebSocket. When a reporter's connection drops without a `done` message, the server marks it as died.

Because the server is single-threaded asyncio and each reporter has its own connection, there are no race conditions — multiple reporters writing simultaneously is safe by design.

---

## License

MIT
