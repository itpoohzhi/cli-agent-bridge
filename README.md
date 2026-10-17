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
- **Live SSE streaming + thinking** — `stream: true` and non-streaming calls
  alike; the backend's thinking trace is translated into `reasoning_content`,
  tool blocks into `delta.tool_calls`. On the `droid` backend, `content` and
  `reasoning_content` deltas stream live as events arrive from the resident
  `droid exec` RPC stream (coalesced in ~40 ms windows, with bounded per-chunk
  write timeouts and explicit `stream_error` fail-close frames if a turn aborts
  after live bytes were sent), followed by tool-call chunks, a `finish_reason`
  chunk, a `usage` chunk, and `[DONE]`. The `muse` backend streams thinking in
  real time as well: every reasoning step and tool-progress marker is relayed
  live in `reasoning_content` (ADR 0004). Both `droid` and `muse` therefore
  deliver the model's thoughts as they happen.
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

- Transport: `muse serve` (MSP — Muse Server Protocol, JSON-RPC over
  stdin/stdout) with `approvalMode: "allowAll"` on `session/start`
  ([ADR 0003](docs/adr/0003-muse-serve-approval-allowall.md)), so interactive
  multi-step sessions run without a turn reset; headless one-shot `muse exec`
  through a launcher wrapper remains available. Wonder context is pruned
  (400k/320k/200k) and net-timeouts are retried.
- Tool access: Full Access — models can read and write files and run shell
  commands (`--disable-write` / `--disable-shell` are no longer passed).
- Streaming: live `reasoning_content` with the model's thoughts (`summary.*`
  steps) and text markers of tool progress (`[Вызов инструмента: ...]`)
  ([ADR 0004](docs/adr/0004-muse-live-streaming-all-steps.md)).
- Models served: `muse-spark-1.3`, `muse-spark-1.3-contributor`,
  `muse-wonder-1.0`, `muse-wonder-full-1.0`.
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
prove the point: one facade, any CLI behind it. How to connect them, and the
full port map, are in [Connecting Claude Code](#connecting-claude-code),
[Connecting Cursor and sibling bridges](#connecting-cursor-cursor-agent-and-sibling-bridges)
and [Ecosystem port and architecture map](#ecosystem-port-and-architecture-map).

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

## Connecting Claude Code

Claude Code can be reached three ways. Pick by direction: modes 1 and 2 expose
Claude **as a model behind** an OpenAI-compatible endpoint; mode 3 points the
`claude` CLI **at** an endpoint as a client.

### Mode 1: Native headless CLI bridge (`claude -p`)

A dedicated sibling bridge spawns the Claude Code CLI in headless mode, once per
turn:

```bash
claude -p --model <id> \
  --output-format stream-json \
  --permission-mode bypassPermissions \
  --tools ""
```

| Flag | Why |
|---|---|
| `-p` | Headless (print) mode: one prompt in, one response out, no TUI. |
| `--model <id>` | Selects the model, e.g. `claude-sonnet-5-5`. |
| `--output-format stream-json` | NDJSON event stream the bridge translates into OpenAI SSE chunks. |
| `--permission-mode bypassPermissions` | No interactive approval prompts — there is nobody to answer them. |
| `--tools ""` | Disables Claude Code's built-in tools; the model can only emit text. |

**Why tool calling is emulated.** With built-in tools off, the CLI is a
text-only transport. The bridge therefore:

1. renders the OpenAI `tools` JSON schemas into the system prompt;
2. instructs the model to answer with
   `<tool_call>{"name": ..., "arguments": ...}</tool_call>` blocks;
3. parses those blocks out of the text and re-emits them as OpenAI
   `delta.tool_calls` with `finish_reason="tool_calls"`.

The calling agent keeps its normal function-calling loop and never sees the
emulation.

**Port isolation.** Each model family gets its own bridge process and port, so
local CLI state and session locks never collide:

| Port | Bridge | Models |
|---|---|---|
| `:9884` | `claude-p-sonnet-bridge` | `claude-sonnet-5-5` |
| `:9881` | `claude-p-bridge` | `claude-opus-5-5`, `claude-haiku-5-5` |

### Mode 2: Factory Droid backend routing

The hub on `:9882` (this repo) routes `claude-sonnet-5-5` through the `droid`
backend (`backend: "droid"` in `fleet.json`, executed as `droid exec`). Unlike
mode 1 this gives **resident multi-turn sessions**: a stable `prompt_cache_key`
maps a chat onto one long-lived process (`hot | restore | rebase | cold`), so
follow-ups resume instead of cold-starting.

```bash
curl -s -H "Authorization: Bearer $DROID_DSH_BRIDGE_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude-sonnet-5-5",
          "prompt_cache_key": "my-chat-001",
          "messages": [{"role": "user", "content": "Continue where we left off."}]}' \
     http://127.0.0.1:9882/v1/chat/completions
```

### Mode 3: Claude Code as a client

To point the `claude` CLI itself at a bridge:

```bash
export ANTHROPIC_BASE_URL="http://127.0.0.1:9882/v1"
export ANTHROPIC_API_KEY="your-bridge-key"
claude
```

> **Protocol caveat.** `claude` speaks the Anthropic Messages API
> (`/v1/messages`). The hub in this repo exposes the OpenAI facade only
> (`/v1/chat/completions`, `/v1/models`, `/health`), so this setup works only
> if an Anthropic-compatible endpoint answers on that URL — for example an
> Anthropic→OpenAI translation proxy placed in front of the bridge. Without
> one, the CLI will receive `404`. Verify with
> `curl -i http://127.0.0.1:9882/v1/messages` before relying on it.

## Connecting Cursor (`cursor-agent`) and sibling bridges

Sibling bridges are standalone deployments that expose the same OpenAI facade
(`/v1/chat/completions`, `/v1/models`, `/health`) on their own ports. They are
not part of this repo; ports and models are listed in the
[port map](#ecosystem-port-and-architecture-map).

### Cursor Agent (`grok46-bridge`)

Wraps `cursor-agent -p` per request:

```bash
cursor-agent -p --model <id> \
  --output-format stream-json \
  --stream-partial-output \
  --force
```

- **Stdin streaming.** The prompt is fed through stdin, not argv, avoiding
  `E2BIG` (argument-list too long) on large contexts — up to **500k tokens**.
- **Live progressive thinking.** NDJSON events `type: thinking,
  subtype: delta` are forwarded straight into OpenAI SSE `reasoning_content`
  chunks as they arrive.
- **Out-of-quota detection.** When the Cursor plan is exhausted the bridge
  returns a structured `402 quota_exhausted` error instead of corrupted
  completion text.
- Models: `cursor-grok-4.6-high` (Grok 4.6/4.7 family).

### Google Antigravity CLI (`agy-bridge`)

- Port `:9885`; models `gemini-4-argon`, `gemini-3.8-flash`.
- Transport: `agy -p --output-format stream-json`.
- `grok46-bridge` is also mapped to `:9885`; a port can be bound by one process
  only, so run one of the two on a host and remap the other.

### OpenCode Zen / Go (`opencode-zen-bridge`)

- Ports `:9887` / `:9883`.
- Serves free-tier frontier models via the `opencode` CLI (for example
  `deepseek-v4.1-flash-free`).

### Meta Muse dedicated bridge (`muse-bridge`)

- Port `:9886`; source in `bridges/muse-bridge/` (`server.py`).
- Transport: MSP `muse serve` (JSON-RPC over stdin/stdout) with
  `approvalMode: "allowAll"`
  ([ADR 0003](docs/adr/0003-muse-serve-approval-allowall.md)), plus `muse exec`
  for one-shot runs.
- Live reasoning streaming of every step
  ([ADR 0004](docs/adr/0004-muse-live-streaming-all-steps.md)).
- Models: `muse-wonder-1.0`, `muse-spark-1.3`.

## Ecosystem port and architecture map

| Port | Service / bridge | Backend CLI / engine | Models served | Key characteristics |
|---|---|---|---|---|
| `:9881` | `claude-p-bridge` | `claude -p` | `claude-opus-5-5`, `claude-haiku-5-5` | Dedicated CLI bridge, tool-calling emulation |
| `:9882` | `cli-agent-bridge` (hub, this repo) | `droid exec` + `muse serve` | `claude-sonnet-5-5`, `gemini-3.8-flash`, `grok-4.7`, `gpt-6.1-sol`, `muse-wonder-1.0` | Multi-binary hub, resident sessions, catalog schema 3 |
| `:9884` | `claude-p-sonnet-bridge` | `claude -p` | `claude-sonnet-5-5` | Dedicated Sonnet 5.5 bridge |
| `:9885` | `grok46-bridge` / `agy-bridge` | `cursor-agent -p` / `agy -p` | `cursor-grok-4.6-high`, `gemini-4-argon` | 500k context, stdin streaming, progressive thinking |
| `:9886` | `muse-bridge` | `muse serve` + `muse exec` | `muse-wonder-1.0`, `muse-spark-1.3` | MSP JSON-RPC, `allowAll` approval, live reasoning |
| `:9887` (also `:9883`) | `opencode-zen-bridge` | `opencode` CLI | `deepseek-v4.1-flash-free`, etc. | Free-tier models |
| `:10830` | `model-georouter` | Direct routing | `gemini-4-argon-contributor` | Geo-distributed fallback proxy |

All bridges authenticate with a bearer key and answer `GET /health`; a client
needs only a `base_url` and `api_key` per port.

## Client and harness integration

The snippets below are copy-paste starting points. Replace the key
placeholders; keep ports as in the [map](#ecosystem-port-and-architecture-map).

### DeepSeek Harness (`cordis.patch.yml`)

The harness consumes each bridge as an OpenAI-compatible provider. The keys
below are a template — adapt field names to your harness version's schema.

```yaml
providers:
  droid-bridge:
    base_url: http://127.0.0.1:9882/v1
    api_key: ${DROID_DSH_BRIDGE_KEY}
    models: [claude-sonnet-5-5, gemini-3.8-flash, grok-4.7, gpt-6.1-sol]
  claude-code-bridge:
    base_url: http://127.0.0.1:9881/v1
    api_key: ${CLAUDE_P_BRIDGE_KEY}
    models: [claude-opus-5-5, claude-haiku-5-5]
  claude-code-sonnet-bridge:
    base_url: http://127.0.0.1:9884/v1
    api_key: ${CLAUDE_P_SONNET_BRIDGE_KEY}
    models: [claude-sonnet-5-5]
  muse-bridge:
    base_url: http://127.0.0.1:9886/v1
    api_key: ${MUSE_BRIDGE_KEY}
    models: [muse-wonder-1.0, muse-spark-1.3]
  opencode-zen-bridge:
    base_url: http://127.0.0.1:9887/v1
    api_key: ${OPENCODE_ZEN_BRIDGE_KEY}
    models: [deepseek-v4.1-flash-free]
```

### Cursor IDE / AI editors

Cursor takes a custom endpoint in **Settings → Models** (*OpenAI API Key* and
*Override OpenAI Base URL*). Cursor typically issues custom-endpoint requests
from its own backend, so `127.0.0.1` may be unreachable — expose the bridge
through a tunnel or reverse proxy if so. Editors that read a JSON provider
block (Continue-style `apiBase`) accept the same values:

```json
{
  "models": [
    {
      "title": "Claude Sonnet 5.5 (bridge)",
      "provider": "openai",
      "model": "claude-sonnet-5-5",
      "apiBase": "http://127.0.0.1:9884/v1",
      "apiKey": "your-bridge-key"
    }
  ]
}
```

### OpenAI Python SDK: streaming and `reasoning_content`

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:9882/v1", api_key="change-me")

stream = client.chat.completions.create(
    model="claude-sonnet-5-5",
    messages=[{"role": "user", "content": "Explain TCP slow start briefly."}],
    stream=True,
)

for chunk in stream:
    if not chunk.choices:  # e.g. the trailing usage chunk
        continue
    delta = chunk.choices[0].delta
    thinking = getattr(delta, "reasoning_content", None)
    if thinking:
        print(f"[thinking] {thinking}", end="", flush=True)
    if delta.content:
        print(delta.content, end="", flush=True)
print()
```

### cURL

```bash
# Streaming chat completion (SSE; thinking arrives as reasoning_content deltas)
curl -N -s -H "Authorization: Bearer $DROID_DSH_BRIDGE_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "claude-sonnet-5-5", "stream": true,
          "messages": [{"role": "user", "content": "Say hi in one sentence."}]}' \
     http://127.0.0.1:9882/v1/chat/completions

# Same call against the Meta Muse bridge
curl -N -s -H "Authorization: Bearer $MUSE_BRIDGE_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model": "muse-wonder-1.0", "stream": true,
          "messages": [{"role": "user", "content": "Say hi in one sentence."}]}' \
     http://127.0.0.1:9886/v1/chat/completions
```

## Layout

- `server.py` — the bridge (HTTP, auth, admission, hub facade); multi-binary hub on port 9882.
- `bridges/muse-bridge/` — standalone Meta Muse bridge service (`server.py`, port 9886).
- `core/` — hub contract: adapter interface, catalog validator, shared tool emulation.
- `adapters/` — vendor CLI adapters (`droid_adapter.py`, `muse_adapter.py`).
- `fleet.json` — backends + models catalog (schema 3).
- `fleet_check.py` — read-only preflight validator.
- `tools/b_guard.py` — offline instruction-budget guard.
- `tests/` — stdlib `unittest` suite.
- `docs/adr/` — architecture decisions (RPC mode, multi-binary hub, ADR 0003
  `muse serve` approval `allowAll`, ADR 0004 live streaming of all steps).
- `start.sh` — launcher (key from env, then `exec python3 server.py`).

## Background

The project started as a single-vendor experiment driving one CLI; it has
since grown into the vendor-neutral hub described above. Old vendor-specific
docs may linger in `docs/` — the README is the current contract.

## License

MIT — see [LICENSE](LICENSE).
