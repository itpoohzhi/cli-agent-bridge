# cli-agent-bridge

A universal bridge that plugs **vendor coding-agent CLIs** into any AI-agent stack
through a single **OpenAI-compatible API**. One port, one key, one model catalog —
on the other side, the vendor binaries do the work.

If a vendor ships a headless CLI for its agent — Factory Droid, Meta's Muse,
Claude Code, OpenAI Codex, Cursor, or anything similar — this bridge lets you
call it with plain `POST /v1/chat/completions`, from any framework, harness,
or script that speaks the OpenAI protocol.

## Features

- **OpenAI-compatible facade** — `POST /v1/chat/completions`, `GET /v1/models`,
  `GET /health`, SSE streaming, `tools` / `tool_calls` with `finish_reason`.
  Drop-in for any OpenAI client; existing harnesses connect with only a
  `base_url` + `api_key` change.
- **Multi-backend hub** — several vendor CLIs behind one port, one key, one
  catalog. Per-backend connection pools and health; `/health` aggregates them.
- **Tool-calling emulation** — for CLIs with text-only transport, the bridge
  renders tool schemas into the prompt and parses the model's answer back into
  `delta.tool_calls`, so agents keep their function-calling loop unchanged.
- **Hot resident sessions with configurable TTL** — chats stick to a
  long-lived backend process keyed by `prompt_cache_key` (sha256, never a
  path), with a `hot | restore | rebase | cold` lifecycle: a follow-up request
  with the same key resumes the same session instead of cold-starting.
  Idle eviction is tunable via `DROID_DSH_BRIDGE_IDLE_SECONDS` (default 2700 s).
- **Streaming + thinking out of the box** — SSE `stream: true` completions and
  non-streaming calls alike; the backend's thinking trace is translated into
  `reasoning_content`, tool blocks into `delta.tool_calls`.
- **Explicit reasoning and autonomy control** — per-request `reasoning_effort`
  (validated against the catalog, always forwarded) and a top-level
  `autonomy` switch (`low | medium | high | off`, default `high`) for how much
  freedom the downstream executor gets. Unknown values fail fast with `400` —
  nothing is coerced or defaulted silently.
- **Binary pinning & sandboxing** — backends start only if the binary matches
  the pinned `sha256` in the catalog; each run executes in its own locked-down
  directory (0600/0700), secrets are stripped from the child environment,
  cleanup is unconditional.
- **Overload protection** — admission limits on connections and body size with
  explicit `503 overloaded` / `413 payload_too_large`; per-backend concurrency
  caps, fail-closed when a required backend is down.
- **Image input** — PNG images (base64 or URL) up to configured limits.
- **Zero-dependency runtime** — the server is Python stdlib only
  (`ThreadingHTTPServer`); no framework to install or audit.
- **Operability** — structured journal log, read-only `fleet_check.py`
  preflight validator (catalog, profiles, live probes), 476-test `unittest`
  suite, ruff + basedpyright clean.

## Supported backends

Two adapters ship in this repo; any other vendor CLI joins the same way
([Adding a backend](#adding-a-backend)). Models are routed strictly
`model → backend` by the fleet catalog — no silent cross-backend fallback.

### `droid` — Factory Droid CLI (enabled by default)

- Transport: resident long-lived `droid exec` process per chat
  (stream-JSON-RPC); one chat completion = one turn in that process.
- Models served: `claude-sonnet-5-5` (default), `gemini-3.8-flash`, `grok-4.7`,
  `deepseek-v4.1-flash`, `gpt-6.1-sol`, `glm-5.3`.
- Concurrency: up to 4 chats in flight.
- Sessions: resident (`hot | restore | rebase | cold` plan), keyed-chat state on
  disk with restricted permissions.

### `muse` — Muse CLI, Meta's coding-agent CLI (opt-in)

- Transport: headless one-shot `muse exec` per request through a launcher
  wrapper; no sessions — every turn replays the request history.
- Models served: `muse-spark-1.3`, `muse-spark-1.3-contributor`.
- Concurrency: strictly 1 across all Muse adapters in the hub.
- Guardrails: binary `sha256` pin plus executable-wrapper check, re-verified
  after slot acquisition right before spawn; per-turn isolated directory
  removed unconditionally; secrets stripped from the child environment.

Enable it by flipping `backends.muse.enabled` to `true` in `fleet.json` (binary
pin and launcher wrapper required), then restart and run
`python3 fleet_check.py` — `/v1/models` picks the new models up automatically.

### Beyond this repo

The same hub pattern fronts other vendor CLIs in the author's setup —
cursor-agent and Claude Code run as sibling bridges behind the identical
OpenAI facade. They are separate deployments, not part of this repo; they
prove the point: one facade, any CLI behind it.

### Your CLI here

Any headless vendor CLI can be connected — you write one **adapter** (that's
what the connector layer is called here): a small class implementing the
`BackendAdapter` interface (`core/backend_adapter.py`), registered by `kind` in
`ADAPTER_KINDS` (`adapters/__init__.py`). Config alone can never load
arbitrary code, so a new CLI always lands as explicit, reviewable code plus
`fleet.json` entries — full recipe in
[Adding a backend](#adding-a-backend).

## Quick start

Requirements: Python 3.10+, and at least one vendor CLI installed
(e.g. Factory Droid `droid` for the default backend).

```bash
git clone https://github.com/itpoohzhi/cli-agent-bridge.git
cd cli-agent-bridge

# 1. Shared secret for the bridge API (any random string)
export DROID_DSH_BRIDGE_KEY="change-me"

# 2. Headless credential for the backend CLI, if it needs one
#    (Factory Droid example — never printed or logged by the bridge)
export FACTORY_API_KEY="..."

# 3. Start — listens on 127.0.0.1:9882 by default
./start.sh
```

Smoke test (no key needed for `/health`):

```bash
curl -s http://127.0.0.1:9882/health
curl -s -H "Authorization: Bearer $DROID_DSH_BRIDGE_KEY" \
  http://127.0.0.1:9882/v1/models
```

First completion (OpenAI protocol — works with any OpenAI client):

```bash
curl -s -H "Authorization: Bearer $DROID_DSH_BRIDGE_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude-sonnet-5-5",
          "messages": [{"role": "user", "content": "Say hi in one sentence."}]}' \
     http://127.0.0.1:9882/v1/chat/completions
```

Python example:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:9882/v1", api_key="change-me")
resp = client.chat.completions.create(
    model="claude-sonnet-5-5",
    messages=[{"role": "user", "content": "Say hi in one sentence."}],
)
print(resp.choices[0].message.content)
```

## Configuration

All runtime tuning is environment variables; the model fleet is `fleet.json`.

| Variable | Default | Purpose |
|---|---|---|
| `DROID_DSH_BRIDGE_KEY` | *(required)* | Bearer key for `/v1/*` |
| `DROID_DSH_BRIDGE_HOST` / `_PORT` | `127.0.0.1` / `9882` | Listen address |
| `DROID_DSH_BRIDGE_FLEET` | `./fleet.json` | Model catalog path |
| `DROID_DSH_BRIDGE_MODEL` | catalog default | Override default model |
| `DROID_DSH_BRIDGE_MAX_CONCURRENT` | `4` | Global concurrency cap |
| `DROID_DSH_BRIDGE_IDLE_SECONDS` | `2700` | Resident-session idle TTL |

`fleet.json` declares `backends` (kind, `enabled`, `max_concurrent`, binary
path + `sha256` pin, wrapper) and `models` (each bound to exactly one
`backend`, with allowed `reasoning_effort` levels). Unknown models and efforts
are rejected with `400` before any work starts — nothing is coerced silently.
Validate any edit before restart:

```bash
python3 fleet_check.py
```

Enable the Muse backend by flipping `backends.muse.enabled` to `true` once its
binary pin and launcher wrapper are in place; `/v1/models` will pick up its
models automatically.

## Adding a backend

1. Implement the `BackendAdapter` interface from `core/backend_adapter.py`
   (`qualify()` for binary checks, one method per turn) and register the new
   `kind` in `ADAPTER_KINDS` (`adapters/__init__.py`) — config alone can never
   load arbitrary code.
2. Add the backend entry + its models to `fleet.json`.
3. Cover it with `unittest` cases under `tests/` and run the full gate:
   `python3 -m unittest` (476 tests), `ruff check .`, `basedpyright`.

Tool parsing, admission, error taxonomy, and journaling are shared by all
backends — an adapter only deals with its own CLI transport.

## Layout

- `server.py` — the bridge (HTTP, auth, admission, hub facade).
- `core/` — hub contract: adapter interface, catalog validator, shared tool emulation.
- `adapters/` — vendor CLI adapters (`droid_adapter.py`, `muse_adapter.py`).
- `fleet.json` — backends + models catalog (schema 3).
- `fleet_check.py` — read-only preflight validator.
- `tools/b_guard.py` — offline instruction-budget guard.
- `tests/` — stdlib `unittest` suite.
- `docs/adr/` — architecture decisions (RPC mode, multi-binary hub).
- `start.sh` — launcher (key from env, then `exec python3 server.py`).

## Background

The project started as a single-vendor experiment driving one CLI; it has
since grown into the vendor-neutral hub described above. Old vendor-specific
docs may linger in `docs/` — the README is the current contract.

## License

MIT — see [LICENSE](LICENSE).
