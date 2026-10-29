# ROLE BRIEF — Coder (`coder-01`, Stage 3, LEAF SUBAGENT `AGENT_SPAWN_DEPTH=1`)

> **КРИТИЧЕСКОЕ ПРАВИЛО КОНТЕКСТА ЗАПУСКА (`AGENT_SPAWN_DEPTH=1`, `AGENTS.md` § «Глубина делегирования ≤ 1»):**
> 1. **ТЫ УЖЕ ЯВЛЯЕШЬСЯ ВНЕШНИМ САБАГЕНТОМ РОЛИ `Coder`** (`модель=claude-sonnet-5-5`, `effort=high`, `транспорт=claude -p`), запущенным главной сессией-оркестратором (`Antigravity`, семейство `Google`) в рамках открытого контура `cel` (`/tmp/cel-runs/agy-image-input-fix-20261029`) и `analyst-teamlead` (`.ai-team/runs/agy-image-input-fix-20261029`).
> 2. В `AGENTS.md` фраза «главная сессия файлы проекта не модифицирует» относится к родительскому оркестратору (`Antigravity`), который тебя вызвал! Для тебя (листового сабагента `Coder`, `AGENT_SPAWN_DEPTH=1`) действует правило **«Глубина делегирования ≤ 1 (субагент не порождает субагентов)»**.
> 3. **КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО** открывать собственный `/tmp/cel-runs/...`, делегировать работу дальше или вызывать `claude`, `agy-cli.sh`, `muse-cli.sh` или вложенный `codex`!
> 4. **ТВОЯ ПРЯМАЯ ОБЯЗАННОСТЬ В ЭТОМ ПРОЦЕССЕ:** лично создать `plans/coder-01.before.json`, лично отредактировать `bridges/agy-bridge/fleet.json`, `bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py`, лично прогнать все проверки `VER-001..VER-009`, и лично записать `plans/coder-01.json`, `handoffs/coder-01.json` и `coder.json`!

Skill: `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

- **Repository Root (`REPO`):** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix`
- **Run Directory (`RUN_DIR`):** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029`
- **Task ID:** `agy-image-input-fix`
- **Run ID:** `agy-image-input-fix-20261029`
- **Base Commit (`BASE_SHA`):** `5a19559426de7508d525e2bd465eff648665a6a7`
- **Iteration:** `1`

## 1. Mandatory Inputs to Read First

Read these files in full before writing any code:
1. `/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`
2. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/architecture/architecture-packet.json` (`sha256=ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466`)
3. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/panel/arch/final-panel-verdict.md` (**Раздел Б**, `F-001..F-010` mandatory safeguards!)
4. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/teamlead/verification-surface.json`
5. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/handoff-architect.md`
6. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/handoff-qa.md`
7. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/bridges/agy-bridge/fleet.json`
8. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/bridges/agy-bridge/server.py`
9. `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/tests/test_agy_bridge_resilience.py`

## 2. Strict Scope & Stop Conditions

- **Allowed Product Files to Modify (ONLY these 3 files outside `.ai-team/`):**
  1. `bridges/agy-bridge/fleet.json`
  2. `bridges/agy-bridge/server.py`
  3. `tests/test_agy_bridge_resilience.py` (**STRICTLY ADDITIVE**: do NOT delete or modify any existing lines in `tests/test_agy_bridge_resilience.py` so `VER-006` `git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py` shows `0` deleted lines!)
- **Forbidden Paths:**
  - Do NOT create or commit `bridges/agy-bridge/dynamic_config.json` in the repo (`VER-008` checks `git ls-files bridges/agy-bridge/dynamic_config.json` is empty and no untracked `bridges/agy-bridge/dynamic_config.json` remains; if a test uses a temp `dynamic_config.json`, use `tempfile`/`monkeypatch` on `_DYNAMIC_CONFIG_PATH` or clean up in `finally`!).
  - Do NOT modify `analysis/agy-image-input-fix/**`, `core/**`, `server.py` (root), `ruff.toml`, `bridges/agy-bridge/start.sh`, or any other test files.
- **No Git Mutations:** Do NOT run `git commit`, `git push`, `git reset`, `git checkout`, or `git stash`. Leave the modified files in the working tree for `CODE_GATE` and `Verifier`.
- **No Inline Type Ignore:** Do NOT add `# type: ignore` or `# pyright: ignore`.

## 3. Step-by-Step Execution Protocol

### Step 1: Write `plans/coder-01.before.json` and Validate `--phase before`
Before modifying any product file, create:
`/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.before.json`
with `schema_version: "1.0"`, `role: "coder"`, `task_id: "agy-image-input-fix"`, `run_id: "agy-image-input-fix-20261029"`, `iteration: 1`, `plan_kind: "full"`, `objective`, `inputs_read`, `stop_conditions`, `deviations: []`, and `steps` (`RP-01..RP-05`, all with `status: "PENDING"`), and validate it:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  --phase before \
  --role coder \
  "/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.before.json"
```

### Step 2: Implement `AD-001..AD-006` and `F-001..F-010` in `bridges/agy-bridge/fleet.json` and `bridges/agy-bridge/server.py`

1. **`bridges/agy-bridge/fleet.json` (`AD-001`):**
   - Update `technical_ref`:
     - `"agy_version": "1.4.9"`
     - `"agy_binary_path": "~/.local/bin/agy.real"`
     - `"agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423"`
   - Update `image_limits`:
     - `"max_images": 16`
     - `"max_image_bytes": 20971520`
     - `"max_total_image_bytes": 20971520`
     - `"max_body_bytes": 33554432`
     - `"types": ["image/png", "image/jpeg", "image/gif", "image/webp"]`
   - For `"gemini-4-argon"` and `"gemini-3.8-flash"` ONLY:
     - `"input": ["text", "image"]`
     - `"images": { "status": "confirmed", "method": "workspace-read", "verified_at": "2026-10-29", "proof": { "agy_binary_sha256": "35605054a9dc4591dd7e6ea83a9392238153d4c55d265512ed9b5b7f97cc0423", "impl_version": 1, "formats": ["image/png", "image/jpeg", "image/gif", "image/webp"], "efforts_proven": ["low", "medium", "high"], "command": "agy.real -p 'Read img-1.png' --add-dir <img_dir> --model <model> --effort <effort>" } }`
   - Keep the other 4 models (`gemini-4-argon-thinking`, `claude-sonnet-4-6`, `claude-opus-4-6`, `gpt-5.4`) with `"input": ["text"]` and `"images": {"status": "unsupported", "method": null, "verified_at": "2026-04-12", "proof": null}`.

2. **`bridges/agy-bridge/server.py` (`AD-001..AD-006` + `F-001..F-010`):**
   - **Constants & Locks (`AD-001`, `F-006`):**
     - `IMPLEMENTED_METHODS: dict[str, int] = {"workspace-read": 1}`
     - `METHOD_IMPL_VERSION = 1`
     - `IMAGE_PROBE = os.environ.get("AGY_IMAGE_PROBE", "").strip().lower() in ("1", "true", "yes")`
     - `_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}`
     - `_sha_cache_lock = threading.Lock()`
     - `_sha_cache: dict[str, tuple[tuple[int, int, int, int], str]] = {}` (keyed by `(st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)`, `F-006`)
     - `_image_flag_lock = threading.Lock()` (separate lock from `_sqlite_guard_lock`, `F-006`)
     - `_image_flag_cache: tuple[float, bool] = (0.0, False)`
     - `_active_img_dirs: set[str] = set()` (protected by `_active_lock`)
   - **Kill-Switch Flag `_is_image_input_enabled()` (`AD-001`, `F-001`, `F-006`):**
     - Check `os.environ.get("AGY_IMAGE_INPUT_ENABLED")`: if set (non-empty), return `False` for `("0", "false", "no", "off")` and `True` for `("1", "true", "yes", "on")` (fail-closed `False` for anything else).
     - Otherwise, under `_image_flag_lock` with `1.0` s `time.monotonic()` TTL cache, read `_DYNAMIC_CONFIG_PATH` (`Path(__file__).resolve().with_name("dynamic_config.json")`): if file exists, is regular file, `<= 65536` bytes, valid JSON `dict`, return `cfg.get("IMAGE_INPUT_ENABLED") is True` (strict boolean identity `=== True`; default `False` on missing/corrupt/non-bool).
   - **Chunked Binary Hash `_file_sha256(path: Path) -> str` (`AD-001`, `F-006`, `F-007`):**
     - Resolve `os.path.expanduser(str(path))` (and check `AGY_BRIDGE_AGY_BIN` env override if set for testing!).
     - `st1 = p.stat()`, key1 = `(st1.st_dev, st1.st_ino, st1.st_mtime_ns, st1.st_size)`. Check `_sha_cache` under `_sha_cache_lock`.
     - If miss, read in `1048576` (1 MiB) chunks using `with open(p, "rb") as f:` **outside** `_sha_cache_lock` (`F-006`, `F-007`), then `st2 = p.stat()`, verify `key2 == key1`, and store in `_sha_cache` under `_sha_cache_lock`. Return `""` on `OSError`.
   - **Capability & Proof Verification `_image_proof_reason(model_id: str, effort: str | None = None) -> str | None` (`AD-001`, `AD-002`):**
     - Look up `m = FLEET_MODELS.get(model_id)` and `img = m.get("images") or {}`.
     - Check `"image" in (m.get("input") or [])` and `status in ("confirmed", "probe")` (if `"probe"`, require `IMAGE_PROBE`).
     - Check `method = img.get("method")` is in `IMPLEMENTED_METHODS`.
     - Check `proof = img.get("proof")`: must be `dict`, `proof.get("impl_version") == IMPLEMENTED_METHODS[method]`.
     - Check `formats = proof.get("formats")` is a non-empty list and `set(IMAGE_LIMITS.get("types") or []).issubset(set(formats))`.
     - Check `efforts_proven = proof.get("efforts_proven")` is a list; if `effort` is resolved/given, check `effort in efforts_proven` (if `effort` is in `m["efforts"]` but not in `efforts_proven`, return `"effort_not_proven"`).
     - Check `expected_sha = proof.get("agy_binary_sha256")` (64 hex chars) against `_file_sha256(agy_bin_path)`: if mismatch or empty, return `"binary_sha_mismatch"`.
     - Return `None` when valid.
   - **Update `_model_supports_images(model_id: str) -> bool` and `/health` (`AD-001`, `F-008`):**
     - `_model_supports_images(model_id)` returns `bool(_is_image_input_enabled() and _image_proof_reason(model_id) is None)`.
     - In `/v1/models` and `/health`: `"images": any(_model_supports_images(mid) for mid in FLEET_MODELS)`.
   - **Image Validation & Two-Phase Memory Discipline (`AD-002`, `F-003`, `F-004`, `F-006`):**
     - Add `ImageReject(ValueError)` with `.reason` and `.code` (default `"image_input_not_supported"`) and `ImageSpoolError(RuntimeError)`.
     - `_collect_image_parts(messages: list[dict[str, Any]]) -> list[tuple[int, int, dict[str, Any]]]` extracts `(msg_index, global_index_1_based, part)` for all `part.get("type") == "image_url"` across `messages`.
     - **Fast path (`AD-002`):** If `_collect_image_parts(messages)` is empty (`0` image parts), `_collect_images` returns `[]` IMMEDIATELY (zero stat/hash/flag calls!).
     - When `parts` is non-empty, follow the exact ordered validation in `AD-002` + `F-003`:
       1) If `not _is_image_input_enabled()`: raise `ImageReject("image_input_disabled", "image_input_not_supported")`.
       2) Check model status (`"unsupported"` -> `ImageReject("status_unsupported")`, `"probe"` without `IMAGE_PROBE` -> `ImageReject("status_probe")`) and `_image_proof_reason(model_id, effort)` (if `"effort_not_proven"`, raise `ImageReject("unsupported_reasoning_effort", "unsupported_reasoning_effort")`; if any other proof failure, raise `ImageReject("image_proof_invalid", "image_input_not_supported")`).
       3) **Pre-check count (`F-003`):** Check `max_images = int(IMAGE_LIMITS.get("max_images", 16))` (`if max_images <= 0 or len(parts) > max_images: raise ImageReject("too_many_images", "too_many_images")` when `max_images > 0`, or `"image_input_not_supported"` if `max_images <= 0`).
       4) Iterate through `(msg_idx, global_idx, part)`:
          - Role of `messages[msg_idx]` must be `"user"` (`else raise ImageReject("non_user_image", "invalid_image_content")`).
          - Extract `url`: `part.get("image_url")` may be `{"url": "..."}` or string (`else raise ImageReject("invalid_image_url", "invalid_image_content")`).
          - Must start with `data:` case-insensitively (`else raise ImageReject("remote_or_file_url", "image_url_not_allowed")`).
          - Parse `data:<mime>;base64,<b64_payload>` case-insensitively (`F-006`): if missing `;base64,` or empty payload, raise `ImageReject("malformed_data_url", "invalid_image_content")`. Normalize `mime = mime.strip().lower()`.
          - Check `allowed_types = IMAGE_LIMITS.get("types") or []` (canonical `"types"`, NOT `"max_types"`!): if `mime not in allowed_types` or `mime not in _EXT`, raise `ImageReject("unsupported_mime", "unsupported_image_type")`.
          - **Pre-check base64 length BEFORE `b64decode` (`F-003`):** Strip ASCII whitespace from `b64_payload`; estimate decoded byte size `(len(b64_clean) * 3) // 4 - b64_clean.endswith("==") - (b64_clean.endswith("=") and not b64_clean.endswith("=="))`. If `est_size > max_image_bytes`, raise `ImageReject("image_too_large", "image_too_large")` without calling `b64decode`!
          - Decode with `base64.b64decode(b64_clean, validate=True)` (`except Exception: raise ImageReject("invalid_base64", "invalid_image_base64")`).
          - Check non-empty (`if not raw: raise ImageReject("empty_image", "invalid_image_content")`), sniff magic bytes (`_sniff_image_type(raw)`: PNG `\x89PNG\r\n\x1a\n`, JPEG `\xff\xd8\xff`, GIF `GIF87a`/`GIF89a`, WebP `RIFF....WEBP`), if `actual_mime is None` -> `ImageReject("unknown_magic", "unsupported_image_type")`, if `actual_mime != mime` -> `ImageReject("mime_mismatch", "image_type_mismatch")`.
          - Check exact `len(raw) > max_image_bytes` -> `ImageReject("image_too_large", "image_too_large")`, and cumulative `total_bytes + len(raw) > max_total_image_bytes` -> `ImageReject("images_too_large", "images_too_large")`.
          - Append `{"index": global_idx, "msg_index": msg_idx, "mime": mime, "ext": _EXT[mime], "size": len(raw), "data": raw, "b64": b64_clean, "path": img_dir / f"img-{global_idx}.{_EXT[mime]}"}`.
   - **Global 1-Based History Indexing & Resumed Prompt Slicing (`AD-003`):**
     - In `_content_to_text(content, img_counter: list[int] | None = None)`: when `img_counter` is passed, each `{"type": "image_url"}` part increments `img_counter[0]` and emits `[image {img_counter[0]}]`.
     - `_messages_to_prompt(messages, images=None)` numbers `[image 1]..[image K]` globally across all messages and appends `[attachments]\n` with `- <path> (mime, size bytes)\n` for all `K` images, plus:
       `Read every attached image file listed above using your file/image inspection tool (e.g. view_file) before answering.`
     - `_get_resumed_turn_prompt(messages, images=None)` finds `last_asst` (last index where `role == "assistant"`):
       - Initializes `img_counter = [sum count of image_url parts in messages[:last_asst + 1]]` so that `[image N]` markers in `messages[last_asst + 1:]` keep their exact global indices!
       - Filters `delta_images = [img for img in (images or []) if img.get("msg_index", 0) > last_asst]`.
       - Emits `[attachments]` ONLY if `delta_images` is non-empty, listing only `delta_images`! (Thus on Turn 2 text-only follow-up after Turn 1 with images, `delta_images` is empty, so Turn 2 prompt has no duplicate `[attachments]` block, while if hot session fails before delivery and falls back to cold `full_prompt`, all `1..K` images are staged in `img_dir` and listed in `full_prompt`!).
   - **`--add-dir <img_dir>` Isolation Without Mutating `cwd` or `sess_key` (`AD-004`):**
     - Do NOT replace `cwd` with `img_dir`! Keep `cwd` and `sess_key = (model_id, cwd, effort)` unchanged.
     - Pass `add_dir: Path | None = None` to `Run(..., add_dir=img_dir if images else None)`.
     - In `Run.__init__`, if `add_dir is not None`, append `["--add-dir", str(add_dir)]` to `cmd`.
   - **Slot-Bounded Spool Lifecycle, Recheck After Slot, & Orphan Sweep (`AD-005`, `F-002`, `F-004`, `F-007`):**
     - Before `_acquire_slot()`, allocate only the `Path` object `img_dir = WORKSPACE / f"img-{uuid.uuid4().hex}"` (0 filesystem ops before slot!).
     - Inside `_run_once`, **AFTER `_acquire_slot()`** and **BEFORE `_stage_images`**:
       1) **Recheck flag & proof (`F-002`):** If `images`: re-check `_is_image_input_enabled()` and `_image_proof_reason(model_id, effort)`! If disabled or proof invalid after waiting in queue, log reject and return HTTP 400 error state (`{"state": "image_reject", ...}`) with `0` `mkdir` and `0` `spawn`!
       2) Register `str(img_dir)` in `_active_img_dirs` under `_active_lock` BEFORE `os.mkdir`, then call `_stage_images(img_dir, images)`:
          - `os.mkdir(img_dir, 0o700)`
          - For each `img`: obtain bytes (`img.get("data") or base64.b64decode(img["b64"])`), open file with `os.open(str(img["path"]), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)` wrapped in `with os.fdopen(fd, "wb") as f: f.write(data)`, then set `img["data"] = b""` and `img.pop("b64", None)` immediately (`F-004`, `F-007`).
          - On any `OSError` in `_stage_images`, `shutil.rmtree(img_dir, ignore_errors=True)` and raise `ImageSpoolError` (which returns HTTP 500 `{"error": {"message": "image spool failed", "type": "image_spool_error", "code": 500}}` and logs `image_spool_error` with `0` `spawn`).
       3) In the outer `finally:` of `_run_once` (after `run.close()` on all attempts), remove `img_dir` via `shutil.rmtree` (logging `image_cleanup_error` on failure, `F-007`, `F-008`) and discard `str(img_dir)` from `_active_img_dirs` under `_active_lock`.
     - Implement `_sweep_workspace(cutoff_s: float = 3600.0)` (`AD-005`, `F-007`): iterate `os.scandir(WORKSPACE)` for entries starting with `"img-"`, skip if `entry.path in active_snapshot` (under `_active_lock`), skip if `entry.is_symlink()`, remove directories with `now - st.st_mtime > cutoff_s` (re-checking `entry.path not in _active_img_dirs` under `_active_lock`). Call `_sweep_workspace()` at startup and periodically.
   - **Log Event Unmasking & Model Sanitization (`AD-006`, `F-006`, `F-008`):**
     - Add to `_LOG_EVENT_NAMES`: `"image_input_not_supported"`, `"unsupported_reasoning_effort"`, `"invalid_reasoning_effort"`, `"unsupported_image_type"`, `"invalid_image_content"`, `"invalid_image_base64"`, `"image_url_not_allowed"`, `"image_type_mismatch"`, `"image_proof_invalid"`, `"images_too_large"`, `"image_too_large"`, `"too_many_images"`, `"image_spool_error"`, `"image_cleanup_error"`, `"image_sweep_removed"`.
     - Sanitize `model_id` in log strings (`re.sub(r"[\r\n\t]", "_", str(model_id))`) so newlines in user-supplied model names cannot forge log lines (`F-006`).

### Step 3: Add All Required Tests (`VER-007`: 40 IDs + `F-001..F-009`) to `tests/test_agy_bridge_resilience.py`
- **CRITICAL (`VER-006`):** Do NOT delete or modify a single existing line in `tests/test_agy_bridge_resilience.py`! Append your new `unittest.TestCase` classes at the end of `tests/test_agy_bridge_resilience.py`.
- Ensure the test method names in `tests/test_agy_bridge_resilience.py` cover ALL 40 required IDs checked by `VER-007`:
  - `img01`, `img02`, `img03`, `img04`, `img05`, `img06`, `img07`, `img08`, `img09`, `img10`
  - `hist01`, `hist02`, `hist03`, `hist04`, `hist05`, `hist06`, `hist07`, `hist08`, `hist09`, `hist10`
  - `life01`, `life02`, `life03`, `life04`, `life05`
  - `log01`, `log02`
  - `res01`, `res02`, `res03`
  - `ao01`, `ao02`, `ao03`, `ao04`, `ao05`, `ao06`, `ao07`, `ao08`, `ao09`, `ao10`
- Also include tests for `F-002` (flag/proof recheck after waiting on a busy slot -> 400, 0 `mkdir`, 0 `spawn`), `F-003` (count > 16 and oversized base64 rejected before `b64decode`), `F-005`/`res01` (integration with fake `AGY_LAUNCHER`, concurrent requests, 0 leaked FDs, `img-*` cleanup), `F-006` (control chars in `model`, case-insensitive `data:IMAGE/PNG;BASE64,`), and `F-007` (`ImageSpoolError` -> 500 `image_spool_error`, partial `img_dir` cleaned up).

### Step 4: Run and Pass All Verification Gates (`VER-001..VER-009`)
Run every command from `architecture/architecture-packet.json` (`verification_surface`) and verify `exit_code == 0`:
1. `VER-001`: `uvx ruff@0.17.3 check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py`
2. `VER-002`: `uvx ruff@0.17.3 format --check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py`
3. `VER-003`: `basedpyright@1.40.2` check (`0` errors, `0` new warnings vs `5a19559426de7508d525e2bd465eff648665a6a7`)
4. `VER-004`: `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py`
5. `VER-005`: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -B -m unittest discover -s tests -p "test_*agy*.py"`
6. `VER-006`: `git diff --numstat 5a19559426de7508d525e2bd465eff648665a6a7 -- tests/test_agy_bridge_resilience.py` (`0` deletions) + `PYTHONPATH=. uvx --from pytest==9.0.3 pytest -q -p no:cacheprovider tests/test_images_strict.py`
7. `VER-007`: AST check of all 40 IDs (`img01..10`, `hist01..10`, `life01..05`, `log01..02`, `res01..03`, `ao01..10`)
8. `VER-008`: Exact 3 changed files (`bridges/agy-bridge/fleet.json`, `bridges/agy-bridge/server.py`, `tests/test_agy_bridge_resilience.py`), no `dynamic_config.json`, and 5 frozen `analysis/agy-image-input-fix/*.md` SHA-256 hashes intact
9. `VER-009`: AST check of stdlib+core imports and no network calls in image helpers

### Step 5: Write `plans/coder-01.json`, `handoffs/coder-01.json`, and `coder.json` and Validate
1. Write `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.json` (`all steps status: "DONE"` with `evidence` and `actual_evidence`) and validate:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py" \
  --phase after \
  --role coder \
  "/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.json" \
  --before "/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/plans/coder-01.before.json"
```
2. Write `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/handoffs/coder-01.json` and copy it to `/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/coder.json`, and validate with `validate_handoff.py`:
```bash
python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_handoff.py" \
  coder \
  "/Users/aazhiry1/tmp/cli-agent-bridge/agy-image-input-fix/.ai-team/runs/agy-image-input-fix-20261029/coder.json"
```
