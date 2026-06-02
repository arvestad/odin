# Odin Wire Protocol

This document describes the communication protocol between reporters and the Odin server. It is intended to help developers implement a reporter in any language.

## Transport

Reporters connect to the server via a **Unix domain stream socket** at `~/.odin` (i.e. the file `.odin` in the user's home directory). The connection is **persistent**: the socket is opened when the reporter starts and held open until the reporter finishes. This allows the server to detect process death — if the connection drops without a prior `done` message, the server marks the session as died.

## Encoding

All messages are **newline-delimited JSON** (one JSON object per line, terminated by `\n`). There are no length-prefix headers or framing beyond the newline.

```
{"type":"progress","value":42}\n
{"type":"info","message":"Phase 1 complete"}\n
```

All string values must be valid UTF-8. JSON string escaping follows the JSON specification (RFC 8259).

## Session lifecycle

1. Open a TCP stream connection to `~/.odin`.
2. Send a **`hello`** message immediately. This registers the reporter with the server.
3. Send any number of **progress / info / warning / error** messages.
4. Optionally send a **`done`** message before closing. If the connection closes without `done`, the server marks the session as `died`.

## Message reference

### `hello` — required, must be the first message

| Field    | Type    | Required | Description |
|----------|---------|----------|-------------|
| `type`   | string  | yes      | `"hello"` |
| `label`  | string  | yes      | Human-readable name for this reporter |
| `pid`    | integer | yes      | Process ID of the reporting process |
| `host`   | string  | yes      | Hostname of the reporting machine |
| `total`  | integer | no       | Total number of steps, if known |

```json
{"type":"hello","label":"training","pid":1234,"host":"myserver","total":100}
```

### `progress` — update the current value

| Field   | Type    | Required | Description |
|---------|---------|----------|-------------|
| `type`  | string  | yes      | `"progress"` |
| `value` | integer | yes      | Current progress value (0 … total). Must not be negative. |

```json
{"type":"progress","value":42}
```

### `info` — informational note

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `type`    | string | yes      | `"info"` |
| `message` | string | yes      | The message text |

```json
{"type":"info","message":"Phase 1 complete, starting phase 2"}
```

### `warning` — non-fatal issue

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `type`    | string | yes      | `"warning"` |
| `message` | string | yes      | The message text |

```json
{"type":"warning","message":"Disk usage above 80%"}
```

### `error` — error condition

| Field     | Type   | Required | Description |
|-----------|--------|----------|-------------|
| `type`    | string | yes      | `"error"` |
| `message` | string | yes      | The message text |

```json
{"type":"error","message":"File not found: input.csv"}
```

### `done` — clean completion

| Field  | Type   | Required | Description |
|--------|--------|----------|-------------|
| `type` | string | yes      | `"done"` |

```json
{"type":"done"}
```

## Server behaviour

The server keeps only the **latest state** per session. Sessions are identified by the combination of `host`, `pid`, and `label` from the `hello` message.

- A session that receives `done` after a prior `error` is marked as `failed`.
- A session whose connection drops without `done` is marked as `died`.
- Completed sessions (`done`, `failed`, `died`) are removed after a configurable retention period (default 30 seconds).

## Minimal reporter implementation

A minimal reporter only needs to:

1. Open a Unix stream socket to `~/.odin` (handle `ENOENT` / `ECONNREFUSED` gracefully — fall back to stderr).
2. Send a `hello` message.
3. Send `progress`, `info`, `warning`, or `error` messages as needed.
4. Optionally send `done` before closing.

All messages must end with `\n`. No authentication, no handshake beyond `hello`.

## Example session (annotated)

```
→ {"type":"hello","label":"training","pid":9876,"host":"gpu01","total":100}
→ {"type":"progress","value":1}
→ {"type":"progress","value":2}
→ {"type":"info","message":"Checkpoint saved"}
→ {"type":"progress","value":50}
→ {"type":"warning","message":"GPU temperature high"}
→ {"type":"progress","value":100}
→ {"type":"done"}
[connection closed]
```

## Fallback behaviour

If `~/.odin` does not exist or the connection is refused, the reporter should fall back gracefully — for example, by writing progress to stderr or calling a user-supplied logging function. The reporter must not crash or block the calling code simply because no server is running.
