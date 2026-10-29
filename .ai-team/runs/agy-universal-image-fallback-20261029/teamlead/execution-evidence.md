# Clean-Room L2 Execution Evidence (Iteration 3 / Round D2) — `agy-universal-image-fallback-20261029`

- **Clean-Room Candidate Worktree:** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback-l2-cleanroom`
- **Clean-Room Base Worktree:** `/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback-l2-base`
- **Base Commit:** `012da99905ec27a6133afb4f3e768ff9b4426a8f`
- **Candidate Fingerprint (`coder-after.json`):** `0efcb715f698e2d4ce3c6b08f6f4a48113e02e7790d16ac74575f82c24175ed5`
- **Candidate Patch (`teamlead/candidate.patch`):** `sha256=5c441470d4541776a3188d3cbc84bc7ecc889262b8cfa1d30dc199de1aaa166c` (`114651` bytes)
- **Environment Manifest (`teamlead/environment-manifest.json`):** `sha256=91a9558939839fc1003ac6a449b34d7c24e35064a5b7f0eb8ca3523359b383b9`

## Verification Surface Results (`VER-001..VER-010`)

| Check ID | Status | Exit Code | Wall Time | Raw Log & SHA256 |
|---|---|---:|---:|---|
| `VER-001` | `PASS` | `0` | `0.88s` | `teamlead/logs/ver-001.log` (`82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`) |
| `VER-002` | `PASS` | `0` | `0.13s` | `teamlead/logs/ver-002.log` (`3bc53bf3e981a98a34a852e175bf9b77af841edea74fca595d9aedcbaf9a4938`) |
| `VER-003` | `PASS` | `0` | `113.33s` | `teamlead/logs/ver-003.log` (`ecf4333d9371481d3ce1e94319d541e2ef4b4a72585c1f573c44aca43f8bc0db`) |
| `VER-004` | `PASS` | `0` | `150.78s` | `teamlead/logs/ver-004.log` (`d472e9701f1fad6374746a8f0ca0565a2e486a519be773e4f26b8fea3e1d47b1`) |
| `VER-005` | `PASS_WITH_PREEXISTING` | `1` (BASE `1` / CAND `1`) | `962.37s` / `1130.88s` | `teamlead/logs/ver-005-base.log` (`0222aa69a36099d34a35fc7d6b24148ae2aaccf12743bb5c4c6d11d7c2b10bea`), `teamlead/logs/ver-005-candidate.log` (`dcbe85699969ede84fafae6545603b799ddeaa2e85703b4df384c7bbbbe1c993`) |
| `VER-006` | `PASS` | `0` | `12.36s` | `teamlead/logs/ver-006.log` (`963a686e963e11e2ee9201f870c1abf4cb38e3c003de4f4cd793621435a9f0c8`) |
| `VER-007` | `PASS` | `0` | `1.14s` | `teamlead/logs/ver-007.log` (`8adcc9f23488d66847e952064411b2e370c228c27b7e9e604751b293ef1e49e8`) |
| `VER-008` | `PASS` | `0` | `0.58s` | `teamlead/logs/ver-008.log` (`c1a4dd6239f34b49ed27d62b2384ca30b669cd544a7913d45fdbf12fd0169c5d`) |
| `VER-009` | `PASS` | `0` | `0.30s` | `teamlead/logs/ver-009.log` (`fcbea902f654b3c8e4e25a03499c4ab715fb35ffdf6afa2e96d580bb71e0681c`) |
| `VER-010` | `DEFERRED_L3` | — | — | Post-Council production deploy + live DSH acceptance (`verification-integrity.md` §6, §8) |

---

### VER-001 (exit `0`, `0.88s`)
```text
All checks passed!
```

### VER-002 (exit `0`, `0.13s`)
```text
2 files already formatted
```

### VER-003 (exit `0`, `113.33s` — `58/58` tests OK, including `test_uf01..test_uf10` and `F/G/H/I/J/K` dict-content subtests)
```text
[agy-bridge] 19:49:05 sqlite-off cid=adea8169 reason=flag
[agy-bridge] 19:49:06 drain cid=adea8169 ms=350 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 19:49:06 done model=gpt-oss-120b rc=0 state=done conversation=adea8169 turns=None tool_events=0 out_bytes=10 wall_s=0.6 err='' client=127.0.0.1:63735 ua=-
[agy-bridge] 19:49:06 image_reject detail=input_not_image
[agy-bridge] 19:49:06 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:63738
[agy-bridge] 19:49:06 exec model=gpt-oss-120b effort=medium effort_source=default prompt_bytes=401 tools=0 resume=0 sess=plain client=127.0.0.1:63739 ua=-
[agy-bridge] 19:49:06 init conversation=6d10efa8 tools=0 permission_mode=x
[agy-bridge] 19:49:06 turn_mode cid=6d10efa8 mode=OFF
[agy-bridge] 19:49:06 sqlite-off cid=6d10efa8 reason=flag
[agy-bridge] 19:49:06 drain cid=6d10efa8 ms=355 emitted=0 outcome=window_complete pending_steps=0 exit=window
[agy-bridge] 19:49:06 done model=gpt-oss-120b rc=0 state=done conversation=6d10efa8 turns=None tool_events=0 out_bytes=10 wall_s=0.5 err='' client=127.0.0.1:63739 ua=-
[agy-bridge] 19:49:06 image_reject detail=input_not_image
[agy-bridge] 19:49:06 reject reason=image_input_not_supported model=gpt-oss-120b model_len=12 client=127.0.0.1:63740
[agy-bridge] 19:49:08 image_sweep_removed count=1
ok

----------------------------------------------------------------------
Ran 58 tests in 112.808s

OK
```

### VER-004 (exit `0`, `150.78s` — `0` new basedpyright diagnostics)
```text
TYPECHECK_NO_NEW_DIAGNOSTICS_PASS baseline 792 candidate 787
```

### VER-005 (`PASS_WITH_PREEXISTING` per `verification-integrity.md` §8 — Full Repository Suite Across All 53 Test Files, `0` Ignored Directories, `0` Collection Errors)
- **Frozen Command:** `pytest -q` (run with `-rfE` for full failure tracebacks)
- **Non-Secret Environment (`teamlead/environment-manifest.json`):**
  - `PYTHONDONTWRITEBYTECODE=1`
  - `PYTHONPATH="/Users/aazhiry1/tmp/cli-agent-bridge/agy-universal-image-fallback/.ai-team/runs/agy-universal-image-fallback-20261029/teamlead:."`
  - `PYTEST_ADDOPTS="-p _pytest_multiroot -p no:cacheprovider"`
  - Native `arm64` interpreter: `/Users/aazhiry1/.local/share/uv/python/cpython-3.14.6-macos-aarch64-none/bin/python3`
- **How `_pytest_multiroot.py` (`sha256=d508c7c82e1aad2ab426af0ba748d1a1162608a3080a694d4ac4e88125ec35ed`) preserves 100% of the repository suite without `--ignore`:**
  - The repository contains two top-level `server.py` modules (`./server.py` for `droid-bridge` and `./bridges/opencode-zen-bridge/server.py` for `opencode-zen-bridge`) and two `tests/` packages (`./tests/` with 35 test files and `./bridges/opencode-zen-bridge/tests/` with 18 test files).
  - `_pytest_multiroot.py` hooks `pytest_collectstart` and `pytest_runtest_setup` to swap `sys.modules["server"]`, `sys.modules["tests.*"]`, and `sys.path` between `"root"` and `"zen"` modes, runs `test_agy_bridge_resilience.py` before `opencode-zen-bridge` inflates process-wide `ru_maxrss`, and calls `server.shutdown_all()` in `pytest_runtest_teardown` for `test_rpc_*`.
- **Full Collection Verification (`--collect-only -q`, `exit=0` on both `BASE` and `CANDIDATE`):**
  - `BASE` (`teamlead/logs/ver-005-base-collect.log`, `sha256=678739397fa9959138691eaf9bf75fb36571d140f59b3d5f7d91d835d7b7cc1d`): **`1,552` tests collected across all `53` test files (`18` in `bridges/opencode-zen-bridge/tests/` + `35` in `tests/`), `0` errors (`BASE_COLLECT_EXIT=0`)**.
  - `CANDIDATE` (`teamlead/logs/ver-005-candidate-collect.log`, `sha256=da7d0de2484031421f703c050517e7af468e1a756fc95ec0836790849421812f`): **`1,564` tests collected across all `53` test files (`+12` new `UniversalImageFallbackTests` test methods), `0` errors (`CANDIDATE_COLLECT_EXIT=0`)**.
  - Every baseline test ID in `BASE` is present and executed in `CANDIDATE` (`BASE_TEST_IDS <= CANDIDATE_TEST_IDS`, `CANDIDATE_TEST_IDS - BASE_TEST_IDS` = the 12 new `UniversalImageFallbackTests` methods).
- **Paired Clean-Room Execution Comparison (`BASE` vs `CANDIDATE`):**
  - **`BASE` (`012da99905ec27a6133afb4f3e768ff9b4426a8f`, `teamlead/logs/ver-005-base.log`, `sha256=0222aa69a36099d34a35fc7d6b24148ae2aaccf12743bb5c4c6d11d7c2b10bea`):**
    - `2 failed, 1550 passed, 11642 subtests passed in 962.37s (0:16:02)` (`BASE_EXIT=1`)
  - **`CANDIDATE` (`teamlead/logs/ver-005-candidate.log`, `sha256=dcbe85699969ede84fafae6545603b799ddeaa2e85703b4df384c7bbbbe1c993`):**
    - `2 failed, 1562 passed, 11813 subtests passed in 1130.88s (0:18:50)` (`CANDIDATE_EXIT=1`)
  - **Exact Pre-Existing Failure Multiset Comparison `(test_id, phase, exc_type, assertion)`:**
    1. `("tests/test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess", "call", "AssertionError", "AssertionError: 2 != 0 : mode=PLANNED maxbytes=106496 canon=/Users/aazhiry1/Мой диск/Context/AGENTS.md size=63079")` — present on `BASE` and `CANDIDATE` (untouched file `tests/test_b_guard.py` checks local `~/Мой диск/Context/AGENTS.md` byte budget).
    2. `("tests/test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k", "call", "AssertionError", "AssertionError: 1048576 != 400000 : wrong contextWindow for muse-wonder-full-1.0 in /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml")` — present on `BASE` and `CANDIDATE` (untouched file `tests/test_muse_bridge_killpg.py` reads local `~/.dsh/profiles/desktop/cordis.patch.yml`).
  - **Multiset Delta:** `CANDIDATE_FAILURES - BASE_FAILURES = ∅` (`CANDIDATE_FAILURES == BASE_FAILURES`, `2 == 2`, `0` new failures, `0` new errors, `+12` new passing tests, `+171` new passing subtests).

#### Raw Tail of `teamlead/logs/ver-005-base.log`
```text
                content = patch_path.read_text(encoding="utf-8")
                for model in wonder_models:
                    m = re.search(
                        rf"-\s+id:\s+{re.escape(model)}\b.*?contextWindow:\s+(\d+)",
                        content,
                        flags=re.DOTALL,
                    )
                    self.assertIsNotNone(m, f"{model} not found in {patch_path}")
                    assert m is not None
>                   self.assertEqual(
                        int(m.group(1)),
                        400_000,
                        f"wrong contextWindow for {model} in {patch_path}",
                    )
E                   AssertionError: 1048576 != 400000 : wrong contextWindow for muse-wonder-full-1.0 in /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml

tests/test_muse_bridge_killpg.py:1694: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-29 21:08:54 http "GET /health HTTP/1.1" 200 -
2026-10-29 21:08:54 http "GET /v1/models HTTP/1.1" 200 -
=========================== short test summary info ============================
FAILED tests/test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess
FAILED tests/test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k
2 failed, 1550 passed, 11642 subtests passed in 962.37s (0:16:02)
BASE_EXIT=1
```

#### Raw Tail of `teamlead/logs/ver-005-candidate.log`
```text
                content = patch_path.read_text(encoding="utf-8")
                for model in wonder_models:
                    m = re.search(
                        rf"-\s+id:\s+{re.escape(model)}\b.*?contextWindow:\s+(\d+)",
                        content,
                        flags=re.DOTALL,
                    )
                    self.assertIsNotNone(m, f"{model} not found in {patch_path}")
                    assert m is not None
>                   self.assertEqual(
                        int(m.group(1)),
                        400_000,
                        f"wrong contextWindow for {model} in {patch_path}",
                    )
E                   AssertionError: 1048576 != 400000 : wrong contextWindow for muse-wonder-full-1.0 in /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml

tests/test_muse_bridge_killpg.py:1694: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-29 20:50:56 http "GET /health HTTP/1.1" 200 -
2026-10-29 20:50:56 http "GET /v1/models HTTP/1.1" 200 -
=========================== short test summary info ============================
FAILED tests/test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess
FAILED tests/test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k
2 failed, 1562 passed, 11813 subtests passed in 1130.88s (0:18:50)
CANDIDATE_EXIT=1
```

### VER-006 (exit `0`, `12.36s` — exact 249,933-byte prefix preserved + `18/18` `test_images_strict.py` OK)
```text
2026-10-29T16:46:51Z http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-29T16:46:52Z exec model=deepseek-v4.1-flash effort=max effort_source=request autonomy=high autonomy_source=default prompt_bytes=493 images=1 image_bytes=64 image_types=image/png client=127.0.0.1:62650 ua=-
2026-10-29T16:46:52Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T16:46:52Z usage sess=sid-620e raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T16:46:52Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-620e resumed=0 turns=1 out_bytes=4 wall_s=0.4 err='' client=127.0.0.1:62650 ua=-
2026-10-29T16:46:52Z http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-29T16:46:52Z exec model=deepseek-v4.1-flash effort=max effort_source=request autonomy=high autonomy_source=default prompt_bytes=17 client=127.0.0.1:62656 ua=-
2026-10-29T16:46:52Z session_rpc chat=- key=0 path=ephemeral gen=0 sid=-
2026-10-29T16:46:53Z usage sess=sid-2619 raw=10/5 cache_read=- rep=10/5 resumed=0 turns=1
2026-10-29T16:46:53Z done model=deepseek-v4.1-flash rc=0 state=done sess=sid-2619 resumed=0 turns=1 out_bytes=4 wall_s=0.2 err='' client=127.0.0.1:62656 ua=-
2026-10-29T16:46:53Z http "POST /v1/chat/completions HTTP/1.1" 200 -
----------------------------------------------------------------------
Ran 18 tests in 11.480s

OK
```

### VER-007 (exit `0`, `1.14s`)
```text
QA_ASSERT_COVERAGE_PASS 50
```

### VER-008 (exit `0`, `0.58s`)
```text
SCOPE_FROZEN_PASS
```

### VER-009 (exit `0`, `0.30s`)
```text
STATIC_IMAGE_SECURITY_CONTRACT_PASS
```

### VER-010 (`DEFERRED_L3` per `verification-integrity.md` §6 & §8)
- **Status:** `DEFERRED_L3` (post-Council production rollout to `~/.dsh/bridges/agy-bridge/` and live owner DSH chat verification; per `verification-integrity.md` §6 & §8, L3 execution fields remain deferred until Council `ACCEPT` and are mandatory before MR/completion).
