# Execution Evidence — `agy-picker-dedup-20261101`

## 1. Summary of Verified Scope
- **Repository files (`5` files, verified in both main worktree and isolated clean-room worktree):**
  1. `fleet.json` (`sha256=65cccda237a843e6ef4cc7129295f7548bcc90bb2e19e69777249c0bfe763ae8`)
  2. `server.py` (`sha256=cbad2a58722d4ff1965c23aea5a01cd7c612a723ccb882d110ff82014118bf18`)
  3. `tests/test_bridge_strict.py` (`sha256=201a174ff9cb2a8e70197a254d3d82efb218a3317c27a87f3d621fc92db8e132`)
  4. `tests/test_dsh_profile_config.py` (`sha256=37bb143c33aae411f71887e64b60a22cb83a25896ca806bfd952912da4129641`)
  5. `tests/test_request_attribution.py` (`sha256=da01a2997883eaa76748eab5dd4deab3f8203b36935a94120d63f2144d9cb925`)
- **External user profiles (`2` files, updated under exclusive `fcntl.flock` on `bridges/opencode-zen-bridge/state/sync.lock` with `0600` backups and CAS):**
  1. `/Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml`:
     - `pre_sha256`: `99a29cbcc0d50e1529a42a9b7f302ec0c50a86eacd40b6913f03b1fc5a199916` (`backup`: `/Users/aazhiry1/work/backups/agy-picker-dedup-20261101/desktop-cordis.patch.yml.bak`, mode `0600`)
     - `cas_post_sha256`: `0664e43ce1ae1e3499fe25d2754726c43bcd5cd553acd49587cf47a5af03f0ed` (mode `0600`)
     - `live_sha256`: `c359d573882dc3c1c58cdeaa5cd9fee63f57929d6ee64e514d9d36296d886325` (mode `0600`, re-serialized by live DSH Electron app PID 93816 upon `agent-default-model` change while preserving all deduplicated `agy-bridge` and `claude-p-bridge` models and `reasoningEfforts.medium = "medium"`)
  2. `/Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml`:
     - `pre_sha256`: `48029c858f3758be5b8b4a52348e04c6ff9ca099bd4c247ef82d72e9e5517119` (`backup`: `/Users/aazhiry1/work/backups/agy-picker-dedup-20261101/web-cordis.patch.yml.bak`, mode `0600`)
     - `cas_post_sha256`: `b8c16266d1cc99d8e201f6139a15c9813f34df2374f946b3c750e9761232f1a9` (`live_sha256=b8c16266d1cc99d8e201f6139a15c9813f34df2374f946b3c750e9761232f1a9`, mode `0600`)

## 2. Verification Matrix (`VER-001..VER-004` + Clean-Room + Live `RT-01..RT-06`)
| Check ID | Command / Oracle | Exit Code | Result |
|---|---|---|---|
| `VER-001` | `pytest tests/test_dsh_profile_config.py -v` (both real `~/.dsh/profiles/{desktop,web}/cordis.patch.yml` and synthetic CI fixture with `!!js` SafeLoader constructor, literal `'use !!js here'`, empty provider, negative effort-clone/medium->high checks) | `0` | PASS (`6 passed in 0.05s`; only `gemini-4-argon` and `gemini-3.8-flash` in `agy-bridge`; 0 effort clones in `agy-bridge` and `claude-p-bridge` models and `allowedModels`; `reasoningEfforts.medium == "medium"`, `xhigh/max == "high"`, `off: null`, `low: "low"`) |
| `VER-002` | `pytest tests/test_request_attribution.py tests/test_bridge_strict.py -v` | `0` | PASS (`ADVERTISE_EFFORT_ALIASES == "off"` by default; `GET /v1/models` advertises 0 effort aliases by default and honours `BRIDGE_ADVERTISE_EFFORT_ALIASES` override; `POST /v1/chat/completions` resolves all 8 aliases via `_resolve_model_alias`; both `gemini-3.8-flash` and `gemini-4-argon` low/medium/high and clamp minimal->low/xhigh->high covered) |
| `VER-003` | `pytest tests/test_fleet_v3.py tests/test_provider_scoping.py tests/test_openai_passthrough.py -v` | `0` | PASS (`fleet.json` schema v3 valid; `gemini-3.8-flash` and `gemini-4-argon` have `efforts: ["low", "medium", "high"]`; `test_openai_passthrough.py` passes `93 passed, 118 subtests passed`) |
| `VER-004` | `test_dsh_profile_config.py` AST verification of live `desktop` + `web` `cordis.patch.yml` + `dsh --profile web --dump-config` | `0` | PASS (`dsh --profile web --dump-config` exit `0`, `63787` bytes; `desktop` profile verified via `test_dsh_profile_models_are_deduplicated[desktop]` + live DSH Electron hot-reload persistence check) |
| `CLEAN-ROOM` | Detached worktree at `HEAD` + `git apply clean-room-5files.patch` (`sha256=4b18c4ecfdaae3594cd15288c9e4c2796fb74302fd9b05df82d4e79f51de0c76`) + 6-module `pytest` | `0` | PASS (`225 passed, 134 subtests passed in 48.40s`) |
| `RT-01` | `launchctl kickstart -k gui/$(id -u)/com.user.dsh-hub` -> `GET http://127.0.0.1:9882/v1/models` | `200` | PASS (`total=18`, down from 25; `gemini_ids=['gemini-3.8-flash', 'gemini-4-argon']`, `claude_ids=['claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-5-5']`, `0` effort clones) |
| `RT-02` | `GET http://127.0.0.1:9887/v1/models` (`com.user.dsh-agy-bridge`) | `200` | PASS (`total=6`, `gemini_ids=['gemini-3.8-flash', 'gemini-4-argon', 'gemini-3.7-flash', 'gemini-3.6-flash', 'gemini-3.1-pro']`, `0` effort clones) |
| `RT-03` | `POST http://127.0.0.1:9887/v1/chat/completions` (`model="gemini-3.8-flash"`, `reasoning_effort="medium"`) | `200` | PASS (`finish_reason="stop"`) |
| `RT-04` | `POST http://127.0.0.1:9882/v1/chat/completions` (`model="gemini-3.8-flash"`, `reasoning_effort="medium"`) | `200` | PASS (`finish_reason="stop"`) |
| `RT-05` | `POST http://127.0.0.1:9882/v1/chat/completions` (`model="gemini-3.8-flash-medium"`) | `200` | PASS (`model="gemini-3.8-flash"`, `finish_reason="stop"` — backward-compatible alias resolution on POST) |
| `RT-06` | Live DSH Desktop Electron (`PID 93816`) hot-reload of `~/.dsh/profiles/desktop/cordis.patch.yml` | `0` | PASS (re-serialized `desktop/cordis.patch.yml` preserves deduplicated `agy-bridge` and `claude-p-bridge` models and `reasoningEfforts.medium == "medium"`) |
| `HEAD-REPRO` (`S3-R1-001`) | Detached worktree at unmodified `HEAD` (`b442c2e`) without our diff: `pytest tests/test_muse_adapter.py tests/test_openai_passthrough.py -k "TestNativeHttp or TestPassthroughAuthFlagSource" -q` | `1` (identical to WT) | PASS (Counter-evidence: unmodified `HEAD` produces the exact same `18 failed, 5 passed, 164 deselected, 7 subtests passed in 3.01s` as working tree `2.94s`; isolated `pytest tests/test_openai_passthrough.py` passes `93 passed, 118 subtests passed, 0 failed`) |
| `RT-07` (`S3-R1-002`) | Live repeated `POST /v1/chat/completions` on `:9887` (`task-776.log`) and `:9882` (`task-786.log`: `base+medium` + `alias-post`) | `200` | PASS (`POST :9887 status=200 model=gemini-3.8-flash finish_reason=stop 'OK'`; `POST :9882 base+medium status=200 model=gemini-3.8-flash finish_reason=stop 'MEDIUM_OK'`; `POST :9882 alias-post status=200 model=gemini-3.8-flash finish_reason=stop 'ALIAS_OK'`) |
| `FLEET-SYNC` (`S3-R1-003`) | Direct JSON comparison of `fleet.json` and `bridges/agy-bridge/fleet.json` + `test_root_fleet_agy_models_efforts` | `0` | PASS (Both `fleet.json` and `bridges/agy-bridge/fleet.json` define `efforts: ["low", "medium", "high"]` for `gemini-3.8-flash` and `gemini-4-argon`) |
