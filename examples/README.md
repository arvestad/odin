# Odin examples

Start the server before running most examples:

```bash
odin serve
```

Then open `http://localhost:6271` in a browser, or run `odin watch` in a second terminal.

---

## Python examples

| File                    | Description                                                                                                      |
|-------------------------|------------------------------------------------------------------------------------------------------------------|
| `simple_loop.py`        | Minimal usage: wrap a loop with `track()`                                                                        |
| `demo2.py`              | Using `Reporter` directly with periodic `info()` messages                                                        |
| `multiple_reporters.py` | Three jobs running concurrently in threads, each with its own progress bar                                       |
| `open_ended.py` | Task with no known total — the bar shows a raw count instead of a percentage                                             |
| `messages.py`           | `info()` and `warning()` calls interspersed with progress updates                                                |
| `context_manager.py`    | `with Reporter(...) as r:` — randomly crashes mid-run so you can observe the error/died transition in the viewer |
| `demo3.py`              | Progress with random steps including negative values — demonstrates the negative-value clamping and warning       |
| `no_server.py`          | Run without starting `odin serve` first — output falls back to stderr and the script works regardless            |

## Shell examples

| File             | Description |
|------------------|---|
| `shell_demo.sh`  | A multi-step shell pipeline reporting progress with `odin progress` and `odin info` |
| `startserver.sh` | Convenience script to start the Odin server |
