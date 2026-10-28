# Независимое свидетельство исполнения верификации (`execution-evidence.md`, run `analyst-teamlead-zen-realtime-reasoning-20261025`, cycle `12`)

- **Базовый коммит (`origin/dev`):** `7eda27f9d82732bab726a420e31ea2adc15c2c39`
- **Отпечаток рабочего дерева ДО Coder (`coder-15-before.json`):** `a44424343a049cdb62bc830eac9fe7bb2b3dd305a4df8dc76b978d252b4f6e39`
- **Отпечаток рабочего дерева ПОСЛЕ Coder (`coder-15-after.json`):** `51bd8af785a8e72e3938c734675d211f9b0521acd16c2ffc2ff0b4ec5f673842`
- **Clean-room контур L2:** отдельное `git worktree` от `origin/dev`, исполнено детерминированным `Verifier` (`run_cleanroom_l2.py`), не логами `Coder`.

## Сводная таблица проверок L2 и L3

| ID / Проверка | Уровень | Статус | Команда | CWD | Exit code | Wall (s) | Сырой лог | SHA-256 лога |
|---|---|---|---|---|---|---|---|---|
| `L2-RED-sensitivity` | L2 | `PASS (RED sensitivity rc!=0)` | `uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `1` | `111.8` | `l2-red.log` | `9b2c6c0c684851f0c5c0ac7d34d8a9ac85c2ac4690817fbdeaa47fdfffa64a34` |
| `VER-004-packet-command` | L2 | `PASS` | `/bin/zsh -lc python3 - <<'VER004' import ast, collections, hashlib, json, re, subprocess, tempfile from pathlib import Path root = Path.c...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `38.29` | `l2-green-ver004-packet.log` | `92c1eeec2c2515c845ec22372664124075f12498c774b48a791f79dd01a811a7` |
| `VER-004-ruff-format-new` | L2 | `PASS` | `uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `0.06` | `l2-green-ver004-ruff-format-new.log` | `d6c423602726d87cf66fba293ac3e20521cf056dd6e016cbdedddc5089a5ac0d` |
| `VER-001-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `423.35` | `l2-green-ver001-pytest.log` | `50f3283d64f3760fac2f76607508a430568761ec0a7f3bb231b0ca89c00e4254` |
| `VER-002-unittest` | L2 | `PASS` | `python3 -m unittest discover -s tests -p test_*.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `388.04` | `l2-green-ver002-unittest.log` | `6a83f06950711b275438413a8b04e8bc19a599d3bc87aaee5cba38eb776bc6df` |
| `VER-003-root-pythonpath-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `382.46` | `l2-green-ver003-pythonpath.log` | `abc1dc29b65e26d389d59e2fd84d62c475468add61c25d675b6f08e2affdabf5` |
| `VER-003b-root-pythonpath-zen-pytest` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom` | `0` | `422.86` | `l2-green-ver003b-zen-pythonpath.log` | `ce51cd18a36a43dcb76a416f5cd05be1b6c35d51349a8b896f7fedc8c6645423` |
| `VER-005-dedicated-realtime-suite` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `346.55` | `l2-green-ver005-dedicated.log` | `70ac05fa969f04b82e38cc1bf5e322422cf7d59e604d78b7628377e373fef834` |
| `AC-023-pytest-reversed` | L2 | `PASS` | `uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinki...` | `/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge` | `0` | `427.09` | `l2-green-ac023-reversed.log` | `9529bd0742f480dd803b9f2fed6371e166342fb2d46664d24ee13ae223ea3664` |
| `VER-006-live-sse-heavy-path` | L3 | `DEFERRED_L3` | `Rollout ladder H0..H9 + curl -N -sS http://127.0.0.1:9883/v1/chat/completions (deepseek-v4.1-flash-free High, stream=true, multi-turn + tools + disconnect cleanup)` | `~/.dsh/bridges/opencode-zen-bridge` |  |  |  |  |
| `VER-007-deployed-mirror-diff` | L3 | `DEFERRED_L3` | `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` | `~/tmp/cli-agent-bridge/zen-realtime-reasoning` |  |  |  |  |

> **Причина отсрочки `DEFERRED_L3` (`verification-integrity.md` §8, `acceptance-package.md` §3):** мутация живого боевого моста `~/.dsh/bridges/opencode-zen-bridge/server.py` (`127.0.0.1:9883`) запрещена до получения вердикта `ACCEPT` Совета Тимлидов (`Forbidden Scope` `handoff-architect.md`, `rollout H0..H9`). Сразу после `ACCEPT` Совета выполняется бэкап в `~/work/backups/`, синхронизация `server.py`, лестница `H0..H9` и живая heavy-path проверка с переводом строк `VER-006`/`VER-007` в `PASS` до открытия MR.

## Сырые логи независимого прогона L2 (`Clean-Room`)

### `L2-RED-sensitivity` (`l2-red.log`, `sha256=9b2c6c0c684851f0c5c0ac7d34d8a9ac85c2ac4690817fbdeaa47fdfffa64a34`)
```text
$ uvx --offline --from pytest==8.3.4 pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=1] [wall=111.8s]
--- STDOUT ---
FFFFFFF..FF.FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF.FFFFFFF.FFFFFFFFFFFFFFFF [ 54%]
FFFFFFFFFFFFF.F.FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF             [100%]
=================================== FAILURES ===================================
_ TestLegacyWatchdogAndKillpg.test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s>

    def test_c5_rw002_limiter_delay_half_second_still_emits_first_status_under_1s(
        self,
    ) -> None:
        """Cycle 5 RW-002: задержка слота 0.5 с сохраняет абсолютный срок статуса."""
        os.environ["FAKE_RT_MODE"] = "slow"
    
        def delayed(*_args: object, **_kw: object) -> bool:
            time.sleep(0.5)
            return True
    
        with mock.patch.object(
            self.bridge.httpd.resilience.spawn_limiter, "acquire", side_effect=delayed
        ):
            chunks, _ = self.bridge.post_stream_timed("жди")
        initial = [
            (at, text)
            for at, text in _deltas(chunks, "reasoning_content")
>           if server.STATUS_INITIAL.strip() in text
        ]
E       AttributeError: module 'server' has no attribute 'STATUS_INITIAL'

tests/test_realtime_reasoning.py:529: AttributeError
----------------------------- Captured stderr call -----------------------------
2026-10-28 01:05:53 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1023 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-28 01:05:53 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:05:55 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=6 emulate_tools=True retries=0 total_spawns=1
2026-10-28 01:05:55 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=6 duration_s=2.50
_ TestLegacyWatchdogAndKillpg.test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate _

self = <tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg testMethod=test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate>

        def test_c5_rw003_legacy_retry_separator_all_branches_and_thinking_gate(
            self,
        ) -> None:
            """Cycle 5 RW-003: один разделитель трёх recovery-веток только при thinking."""
            for branch in ("watchdog", "unmapped", "incomplete"):
                for effort in ("high", "off"):
                    with self.subTest(branch=branch, effort=effort):
                        counter = self.tmp / (branch + effort)
                        body = """#!/usr/bin/env python3
    import json, sys, time
    from pathlib import Path
    p = Path(COUNTER)
    n = int(p.read_text()) if p.exists() else 0
    p.write_text(str(n + 1))
    prompt = sys.stdin.read()
    def ev(o): print(json.dumps(o), flush=True)
    if n == 0:
        ev({"type": "reasoning", "part": {"text": "Первая мысль"}})
        if BRANCH == "watchdog": time.sleep(3)
        elif BRANCH == "unmapped":
            ev({"type": "tool_use", "part": {"tool": "todoread", "state": {"status": "error", "input": {}}}})
        else: ev({"type": "text", "part": {"text": "Проверяю файлы.<tool_call>{"}})
    else:
        ev({"type": "text", "part": {"text": "Ответ"}})
    ev({"type": "step_finish", "part": {"tokens": {"input": 1, "output": 1}}})
    """.replace("COUNTER", repr(str(counter))).replace("BRANCH", repr(branch))
                        server.OPENCODE_BIN = str(
                            _write_exe(self.tmp, "retry-legacy", body
... [фрагмент оракула AC-026 из середины лога (l2-red.log, sha256=9b2c6c0c684851f0c5c0ac7d34d8a9ac85c2ac4690817fbdeaa47fdfffa64a34)] ...
 = server.FIRST_EVENT_TIMEOUT_S
E       AttributeError: module 'server' has no attribute 'FIRST_EVENT_TIMEOUT_S'

tests/test_realtime_reasoning.py:633: AttributeError
_ TestServeTransportAndFakeServe.test_ac026_realtime_chunks_before_upstream_end _

self = <tests.test_realtime_reasoning.TestServeTransportAndFakeServe testMethod=test_ac026_realtime_chunks_before_upstream_end>

    def test_ac026_realtime_chunks_before_upstream_end(self) -> None:
        """AC-026: reasoning-чанки приходят, пока апстрим ещё идёт."""
        end_record = self.tmp / "upstream-ended"
        chunks, _elapsed = self.bridge.post_stream_timed(
            f"обычный запрос __end_record:{end_record}__"
        )
        reasoning = _deltas(chunks, "reasoning_content")
        model_reasoning = [
            (at, t) for at, t in reasoning if not t.lstrip("\n").startswith("[мост]")
        ]
>       self.assertGreaterEqual(len(model_reasoning), 5, chunks)
E       AssertionError: 1 not greater than or equal to 5 : [(0.0014347080141305923, {'id': 'chatcmpl-oczen-e2aa5263ee3a', 'object': 'chat.completion.chunk', 'created': 1793138769, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': ''}}]}), (1.333488457952626, {'id': 'chatcmpl-oczen-e2aa5263ee3a', 'object': 'chat.completion.chunk', 'created': 1793138769, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'reasoning_content': 'Поздняя мысль'}}]}), (1.3335514159407467, {'id': 'chatcmpl-oczen-e2aa5263ee3a', 'object': 'chat.completion.chunk', 'created': 1793138769, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {'content': 'Поздний ответ'}}]}), (1.5864297079388052, {'id': 'chatcmpl-oczen-e2aa5263ee3a', 'object': 'chat.completion.chunk', 'created': 1793138769, 'model': 'muse-spark-1.3-contributor-free', 'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}})]

tests/test_realtime_reasoning.py:2263: AssertionError
----------------------------- Captured stderr call -----------------------------
2026-10-28 01:06:09 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1125 cwd=/private/tmp/cel-runs/***/l2-cleanroom/bridges/opencode-zen-bridge/workspace
2026-10-28 01:06:09 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:06:10 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=13 emulate_tools=True retries=0 total_spawns=1
2026-10-28 01:06:10 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit
... [пропущено 193953 символов однотипного вывода; полный лог на диске receipts/l2-red.log sha256=9b2c6c0c684851f0c5c0ac7d34d8a9ac85c2ac4690817fbdeaa47fdfffa64a34] ...
ion_returns_diagnostic_json
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c12_rw004_unmapped_exhaustion_transport_matrix
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_fu003_json_transient_recovery_normalizes_and_deduplicates
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c5_rw001_prompt_headers_then_body_error_or_429_blocks_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw001_headers_at_blocks_run_fallback_on_sse_error_and_timeout
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw004_ac016_serve_step_interruption_matrix
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw004_ac017_unmapped_recovery_serve_vs_run_equivalence
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c6_rw005_startup_abort_never_falls_back_or_changes_serve_health
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c7_fu001_native_tool_call_captures_step_ended_usage
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c7_rw002_execution_started_before_prompt_headers_sets_delivered_and_blocks_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_fu001_multiple_native_tool_calls_same_step_preserved_next_step_excluded
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_fu002_legacy_spawn_rechecks_cancel_and_deadline_after_reservation
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw001_early_transient_error_after_execution_started_retries_serve_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw002_pre_delivery_surrogate_falls_back_to_run
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw002_unpaired_surrogate_raises_serve_protocol_error_in_sse_and_json
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c8_rw003_request_deadline_timeout_is_neutral_for_circuit_breaker
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_c9_rw001_idless_and_unconfirmed_native_step
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_canonical_frozen_fixtures
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_dynamic_config_switch_same_server
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_foreign_listener_rejected_and_startup_reaper
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_form_missing_title_cancels_without_step2
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu003_usage_once_across_distinct_retry_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu010_thinking_off_omits_retry_separator
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_fu011_cancelled_never_counts_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_helper_argv_validation_and_lease_dir
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_run_fallback_respects_total_spawn_cap
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_json_tool_calls_are_deduplicated
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_native_tool_and_permission_reject
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_prompt_http_4xx_fail_closed_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_proxy_pool_advances_once_per_serve_attempt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_retry_separator_once_and_delivery_barrier_is_monotonic
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw001_delivery_survives_unavailable_or_limiter
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw003_mkdtemp_failure_is_serve_unavailable
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw006_invalid_utf8_falls_back_and_recovers
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw007_split_interrupted_marker_at_every_boundary
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_rw008_provider_secrets_hidden_in_sse_json_and_log
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_400_fails_closed_without_health_increment
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_env_sanitized_all_branches
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_serve_health_and_fallback_table
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_pause_streams_all_deltas_and_single_initial_status
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_slow_serve_gets_status_and_no_status_on_fast
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_timeout_and_client_gone_never_count_as_success
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_choice_preserved_in_step_recovery_prompt
FAILED tests/test_realtime_reasoning.py::TestServeTransportAndFakeServe::test_tool_text_split_across_deltas
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c10_fu002_aux_budget_three_subscriptions_deterministic
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c10_rw004_tool_count_and_state_bytes_caps
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c10_rw005_locked_wfile_timeout_and_abort_without_lock
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c11_rw004_callback_error_logged_and_socket_aborted
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c12_rw001_drain_reject_preserves_neutral_exceptions
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c12_rw002_run_retry_preserves_partial_output_and_usage
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c12_rw003_drain_activity_extends_window_but_not_hard_deadline
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_c8_fu002_pre_spawn_gate_and_limiter_respect_deadline_and_client_disconnect
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_disable_file_overrides_forced_serve
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_elf_magic_and_tool_status
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_fu001_http_checks_deadline_and_cancellation_before_connect
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw004_native_calls_share_canonical_mapping
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw005_stop_group_after_leader_exit
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_rw008_error_payload_masks_message_and_detail
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_service_events_ignored_and_foreign_session
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_spawn_cap_and_proxy_rotation_helpers
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_surrogate_pair_and_broken_json
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_transport_matrix
FAILED tests/test_realtime_reasoning.py::TestReworkUnits::test_whitespace_delta_preserved_in_map
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_attempt_rotates_proxy_pool_once
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c10_fu002_exhausted_aux_budget_starts_no_attempt
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c10_rw004_tool_state_byte_cap_main_and_drain_cleanup
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw002_execution_wait_excluded_from_prompt_budget
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw002_exhausted_before_prompt_starts_no_http
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw002_first_sse_budget_across_real_attempts
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw002_prompt_headers_use_remaining_aux
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw002_security_control_time_debited_main_and_drain
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c11_rw006_name_and_id_caps_main_and_drain
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c12_rw001_main_control_disconnect_and_deadline_are_neutral
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c12_rw003_main_passes_attempt_deadline_to_active_drain
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c5_fu002_prompt_401_headers_classified_before_hanging_body
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c5_rw004_native_call_updates_last_token_at_no_premature_stall
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c6_fu001_oversized_sse_line_is_terminal_invalid_event
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c6_rw005_subscribe_deadline_and_disconnect_cleanup
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_c9_fu001_serve_queue_and_accumulated_byte_budget_enforced
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_never_event_gives_first_event_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_prompt_http_4xx_fails_closed_fast
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_silent_model_gives_first_token_timeout
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_sse_pause_over_half_second_keeps_stream_alive
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_stall_after_first_token
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_startup_gate_released_before_generation_ends
FAILED tests/test_realtime_reasoning.py::TestServeAttemptOracles::test_text_tool_call_closes_step_on_step_finish
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw005_spawn_serve_respects_deadline_and_client_disconnect_without_run_fallback
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw006_spawn_serve_drains_multi_mib_stderr_before_bind_without_deadlock
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c6_rw007_fu003_dripping_interrupt_delete_still_cleans_up_under_7s
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_c7_rw004_startup_http_phases_enforce_own_budget_under_long_request_deadline
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_client_gone_check_detects_reset_and_close
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_lease_cleanup_confirms_sigkill_in_separate_window
FAILED tests/test_realtime_reasoning.py::TestSpawnAndLeaseOracles::test_spawn_failures_leave_no_leftovers
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_fu001_fu002_sse_line_body_byte_caps_and_strict_usage_ints
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_rw007_absolute_deadline_interrupts_dripping_headers_and_body
FAILED tests/test_realtime_reasoning.py::TestCycle6HttpBounds::test_c6_rw007_skip_body_returns_immediately_after_headers
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_errno_imported_before_helper_branch
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_kills_surviving_group_and_removes_lease_last
FAILED tests/test_realtime_reasoning.py::TestHelperProcess::test_helper_survives_bad_stdin_without_name_error
125 failed, 7 passed in 111.61s (0:01:51)

--- STDERR ---
```

### `VER-004-packet-command` (`l2-green-ver004-packet.log`, `sha256=92c1eeec2c2515c845ec22372664124075f12498c774b48a791f79dd01a811a7`)
```text
$ /bin/zsh -lc python3 - <<'VER004'
import ast, collections, hashlib, json, re, subprocess, tempfile
from pathlib import Path
root = Path.cwd().resolve()
bridge = root / 'bridges/opencode-zen-bridge'
files = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']
assert all(f.is_file() for f in files), 'all three target files must exist after Stage3'
ruff = ['uvx','--from','ruff==0.17.2','ruff']
def run(args, **kw):
    return subprocess.run(args, check=True, **kw)
def changed_ranges(file):
    rel = str(file.relative_to(root))
    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)
    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.
    result = []
    for line in diff.splitlines():
        m = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if m:
            start = int(m.group(1)); count = int(m.group(2) or '1')
            if count: result.append((start, start + count - 1))
    return result

# Raw-byte contract: frozen expected digests originate in EVD-075, never candidate.
FROZEN = {
    '_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31',
    '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3',
    '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6',
}
baseline_raw = subprocess.check_output(['git','show','origin/dev:bridges/opencode-zen-bridge/server.py'], cwd=root)
def frozen_slices(raw):
    lines = raw.splitlines(keepends=True)
    nodes = {n.name:n for n in ast.walk(ast.parse(raw)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in FROZEN}
    assert set(nodes)==set(FROZEN)
    return {name:(node.lineno,node.end_lineno,b''.join(lines[node.lineno-1:node.end_lineno])) for name,node in nodes.items()}
baseline_slices = frozen_slices(baseline_raw)
def assert_frozen(candidate=files[0]):
    candidate_slices = frozen_slices(candidate.read_bytes())
    for name, expected in FROZEN.items():
        assert hashlib.sha256(baseline_slices[name][2]).hexdigest()==expected, ('frozen origin/dev changed',name)
        assert hashlib.sha256(candidate_slices[name][2]).hexdigest()==expected, ('immutable slice changed',name)
        assert candidate_slices[name][2]==baseline_slices[name][2], ('nonzero raw Google/_run_env diff',name)
    return candidate_slices
candidate_slices = assert_frozen()
server_diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',str(files[0].relative_to(root))],cwd=root,text=True)
for line in server_diff.splitlines():
    match = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
    if not match: continue
    old_start,old_count,new_start,new_count = int(match[1]),int(match[2] or '1'),int(match[3]),int(match[4] or '1')
    for start,count,table in [(old_start,old_count,baseline_slices),(new_start,new_count,candidate_slices)]:
        for name,(lo,hi,_) in table.items():
            # Zero-count insert/delete anchors represent the boundary after start.
            overlaps = (start<=hi and start+count-1>=lo) if count else (lo<=start<hi)
            assert not overlaps, ('VER-004 frozen-range hunk intersection',name,line)
# Public module constant/read API remains intact; compatibility test file is frozen.
tree = ast.parse(files[0].read_bytes())
assignments = [n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CATALOG_SOURCE' for t in n.targets)]
assert len(assignments)==1 and isinstance(assignments[0].value,ast.Constant) and assignments[0].value.value=='static'
assert any(isinstance(n,ast.FunctionDef) and n.name=='_set_catalog_source' for n in tree.body)
assert any(isinstance(n,ast.Import) and any(a.name=='zen_catalog' and a.asname=='zc' for a in n.names) for n in ast.walk(tree))
assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='import_module' and n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value=='zen_catalog' for n in ast.walk(tree))
assert any(isinstance(n,ast.FunctionDef) and n.name=='_run_serve_helper_cli' for n in tree.body), 'helper code must be lint/type checked in server.py'
helper_branch = next((n for n in tree.body if isinstance(n, ast.If) and ast.unparse(n.test) == "sys.argv[1:2] == ['--serve-helper']"), None)
assert helper_branch is not None and any(isinstance(n, ast.Raise) for n in helper_branch.body), 'early terminating helper dispatch required'
heavy = {'http.client', 'sqlite3', 'http.server', 'zen_catalog'}
def imported_names(node):
    if isinstance(node, ast.Import): return {a.name for a in node.names}
    if isinstance(node, ast.ImportFrom): return {node.module}
    return set()
assert not any(imported_names(n) & heavy for n in tree.body[:tree.body.index(helper_branch)])
assert any(isinstance(n, ast.Import) and any(a.name == 'zen_catalog' and a.asname == 'zc' for a in n.names) for n in helper_branch.orelse)
assert all(not isinstance(n, (ast.Assign, ast.AnnAssign, ast.Expr)) for n in tree.body[1:tree.body.index(helper_branch)]), 'no server initialization before helper exit'
assert not any(isinstance(n,ast.Global) and 'CATALOG_SOURCE' in n.names for n in ast.walk(tree))
run(['git','diff','--exit-code','origin/dev','--','bridges/opencode-zen-bridge/tests/test_catalog_mode.py'],cwd=root)

ranges = {f: changed_ranges(f) for f in files[:2]}
# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.
run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',str(files[2])], cwd=root)
for f in files[:2]:
    for start, end in ranges[f]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--check','--no-cache',f'--range={start}:1-{end}:999',str(f)], cwd=root)
assert_frozen()
# Exercise actual write-mode range formatting only on a disposable copy.
with tempfile.TemporaryDirectory(prefix='zen-arch6-probe-format-', dir='/tmp') as format_dir:
    formatted_copy = Path(format_dir) / 'server.py'
    formatted_copy.write_bytes(files[0].read_bytes())
    for start, end in ranges[files[0]]:
        run([*ruff,'format','--config',str(root / 'ruff.toml'),'--no-cache',f'--range={start}:1-{end}:999',str(formatted_copy)], cwd=root)
    assert formatted_copy.read_bytes() == files[0].read_bytes()
    assert_frozen(formatted_copy)
    assert_frozen()
    print('PASS write-mode frozen hashes', {name:hashlib.sha256(data[2]).hexdigest() for name,data in frozen_slices(formatted_copy.read_bytes()).items()})
# Full-file lint on all three. Only inherited E402 import site is excepted on server.
lint = subprocess.run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)
assert lint.returncode in (0,1), lint.stderr
findings = json.loads(lint.stdout)
lines = files[0].read_text().splitlines()
assert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings
assert sum(x['code']=='E402' for x in findings) <= 1
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)
run([*ruff,'check','--config',str(root / 'ruff.toml'),'--no-cache',str(files[1]),str(files[2])], cwd=root)
# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.
project = None
try:
    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-arch6-probe-project-',dir='/tmp',delete=False) as tmp:
        project = Path(tmp.name)
        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)
    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)
    assert b.returncode in (0,1), b.stderr
    report = json.loads(b.stdout)
    ds = report['generalDiagnostics']
    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds
    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}
    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}
    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']
    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))
    print('BASEDPYRIGHT summary',report['summary'])
    print('SERVER dict(counts)',dict(counts))
    print('SERVER warningCount',len(warnings(files[0])))
    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)
    assert len(warnings(files[0]))<=720, len(warnings(files[0]))
    assert len(warnings(files[1]))<=194, len(warnings(files[1]))
    # New test file: zero warnings as well as zero errors, thus zero Any.
    assert not byfile[files[2]], byfile[files[2]]
    for f in files[:2]:
        for x in byfile[f]:
            line = x['range']['start']['line']+1
            if any(lo<=line<=hi for lo,hi in ranges[f]):
                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x
    # Do not introduce Any annotations/type ignores in added code in either legacy file.
    for f in files[:2]:
        src = f.read_text().splitlines()
        for lo,hi in ranges[f]:
            for line in src[lo-1:hi]:
                assert not re.search(r'\bAny\b|type:\s*ignore|pyright:\s*ignore|#\s*noqa|#\s*fmt:\s*off',line), (f,line)
    run(['python3','-B','-m','unittest','tests.test_catalog_mode','-v'],cwd=bridge)
    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))
finally:
    if project is not None: project.unlink(missing_ok=True)
VER004
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=38.29s]
--- STDOUT ---
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file already formatted
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
1 file left unchanged
All checks passed!
All checks passed!
PASS write-mode frozen hashes {'_run_env': '1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31', '_execute_google_once': '88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6', '_stream_google_sse': '5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3'}
BASEDPYRIGHT summary {'filesAnalyzed': 3, 'errorCount': 0, 'warningCount': 764, 'informationCount': 0, 'timeInSec': 8.991}
SERVER dict(counts) {'reportExplicitAny': 123, 'reportAny': 116, 'reportUnusedCallResult': 34, 'reportUnknownMemberType': 73, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 47, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 28, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 4, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}
SERVER warningCount 591
PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts {'reportExplicitAny': 123, 'reportAny': 116, 'reportUnusedCallResult': 34, 'reportUnknownMemberType': 73, 'reportUnknownVariableType': 56, 'reportUnknownArgumentType': 47, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 28, 'reportUnannotatedClassAttribute': 98, 'reportUnusedParameter': 4, 'reportUnnecessaryIsInstance': 4, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}

--- STDERR ---
test_env_default_is_dynamic (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_env_static_and_legacy (tests.test_catalog_mode.ModeFromEnvironmentTest) ... ok
test_default_in_tests_is_dynamic (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_modes (tests.test_catalog_mode.ModeNormalizationTest) ... ok
test_aliases_still_work_in_static (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_never_reloads_by_mtime (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_routes_through_background_service (tests.test_catalog_mode.StaticModeTest) ... ok
test_static_uses_embedded_snapshot_and_ignores_state_file (tests.test_catalog_mode.StaticModeTest) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.290s

OK
```

### `VER-004-ruff-format-new` (`l2-green-ver004-ruff-format-new.log`, `sha256=d6c423602726d87cf66fba293ac3e20521cf056dd6e016cbdedddc5089a5ac0d`)
```text
$ uvx --from ruff==0.17.2 ruff format --check --no-cache tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=0.06s]
--- STDOUT ---
1 file already formatted

--- STDERR ---
```

### `VER-001-pytest` (`l2-green-ver001-pytest.log`, `sha256=50f3283d64f3760fac2f76607508a430568761ec0a7f3bb231b0ca89c00e4254`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=423.35s]
--- STDOUT ---
......................... [  4%]
............................................................................................................................................ [ 32%]
............................................................... [ 44%]
................................ [ 50%]
............................................. [ 59%]
................................................................. [ 72%]
.................................................................... [ 85%]
................................................................... [ 98%]
......                                                               [100%]
511 passed, 3387 subtests passed in 422.76s (0:07:02)

--- STDERR ---
```

### `VER-002-unittest` (`l2-green-ver002-unittest.log`, `sha256=6a83f06950711b275438413a8b04e8bc19a599d3bc87aaee5cba38eb776bc6df`)
```text
$ python3 -m unittest discover -s tests -p test_*.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=388.04s]
--- STDOUT ---

--- STDERR ---
..........2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=jev-1.13 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=jev-1.13-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=nemotron-3-ultra-free status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=test status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=claude-opus-5-5-backup status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=deepseek-v4.1-flash status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
2026-10-28 01:15:30 http "POST /v1/chat/completions HTTP/1.1" 400 -
2026-10-28 01:15:30 O-EXIT/v1 mode=json model=claude-haiku-5-5 status=400 exit_reason=bad_request rc=None total_spawns=0 retries=0 signal=0 tools=0 out_chars=0 transport=none first_event_ms=None ttft_ms=None transport_history=[] duration_s=0.00
.2026-10-28 01:15:30 http "GET /health HTTP/1.1" 200 -
.2026-10-28 01:15:30 http "GET /v1/models HTTP/1.1" 200 -
.2026-10-28 01:15:30 http "GET /v1/models HTTP/1.1" 401 -
........................2026-10-28 01:15:33 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpj9w22rt5/ws
2026-10-28 01:15:33 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:15:33 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=7 emulate_tools=False retries=0 total_spawns=1
2026-10-28 01:15:33 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=200 ttft_ms=200 transport_history=['run'] duration_s=0.45
.2026-10-28 01:15:33 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpj9w22rt5/ws
2026-10-28 01:15:34 exec cli failed rc=1 state=nonzero_exit stderr_tail='Error: Unexpected error\ndatabase is locked'
2026-10-28 01:15:34 exec failed rc=1 without output, retry 1/2 total_spawns=1/3: 'Error: Unexpected error\ndatabase is locked'
2026-10-28 01:15:34 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=32 cwd=/var/folders/2f/***/T/tmpj9w22rt5/ws
2026-10-28 01:15:35 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=
... [пропущено 172684 символов однотипного вывода; полный лог на диске receipts/l2-green-ver002-unittest.log sha256=6a83f06950711b275438413a8b04e8bc19a599d3bc87aaee5cba38eb776bc6df] ...
26-10-28 01:21:38 exec: step with tool call finished, stopping opencode run
2026-10-28 01:21:38 tool_call_unparsed bytes=7 head='{broken'
2026-10-28 01:21:38 dropped 1 unparsed tool block(s) from content
2026-10-28 01:21:38 done model=glm-5.3-flash-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=0 total_spawns=1
2026-10-28 01:21:38 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:38 O-EXIT/v1 mode=json model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=2 out_chars=0 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=0.03
.2026-10-28 01:21:38 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:38 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:39 tool_call_unparsed bytes=7 head='{broken'
2026-10-28 01:21:39 stream dropped 1 unparsed tool block(s) from content
2026-10-28 01:21:39 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-28 01:21:39 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1868 total_spawns=1/3
2026-10-28 01:21:40 stream: step with tool call finished, stopping opencode run
2026-10-28 01:21:40 stream done model=glm-5.3-flash-free rc=-15 tools=2 out_chars=78 emulate_tools=True retries=1 total_spawns=2
2026-10-28 01:21:40 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=2 tools=2 out_chars=78 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=1.03
.2026-10-28 01:21:40 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:40 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:40 tool_call_unparsed bytes=7 head='{broken'
2026-10-28 01:21:40 stream dropped 1 unparsed tool block(s) from content
2026-10-28 01:21:41 stream incomplete tool step: re-prompt 1/2 signal=2 total_spawns=1/3
2026-10-28 01:21:41 stream exec retry=1 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=1/3
2026-10-28 01:21:41 tool_call_unparsed bytes=7 head='{broken'
2026-10-28 01:21:41 stream dropped 1 unparsed tool block(s) from content
2026-10-28 01:21:42 stream incomplete tool step: re-prompt 2/2 signal=2 total_spawns=2/3
2026-10-28 01:21:42 stream exec retry=2 fail_retries=0 model=opencode/glm-5.3-flash-free prompt_chars=1777 total_spawns=2/3
2026-10-28 01:21:42 tool_call_unparsed bytes=7 head='{broken'
2026-10-28 01:21:42 stream dropped 1 unparsed tool block(s) from content
2026-10-28 01:21:42 stream incomplete tool step: retries exhausted (2) signal=2
2026-10-28 01:21:42 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=66 emulate_tools=True retries=2 total_spawns=3
2026-10-28 01:21:42 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=2 tools=0 out_chars=66 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=2.46
.2026-10-28 01:21:42 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:42 tool_call_recovered extra_braces=1
2026-10-28 01:21:42 stream: step with tool call finished, stopping opencode run
2026-10-28 01:21:42 stream done model=glm-5.3-flash-free rc=-15 tools=1 out_chars=0 emulate_tools=True retries=0 total_spawns=1
2026-10-28 01:21:42 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=-15 total_spawns=1 retries=0 signal=0 tools=1 out_chars=0 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=0.03
.2026-10-28 01:21:42 stream exec model=opencode/glm-5.3-flash-free -m opencode/glm-5.3-flash-free#high --standalone --thinking prompt_chars=1224 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:42 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:42 stream done model=glm-5.3-flash-free rc=0 tools=0 out_chars=7 emulate_tools=True retries=0 total_spawns=1
2026-10-28 01:21:42 O-EXIT/v1 mode=stream model=glm-5.3-flash-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=0.28
.2026-10-28 01:21:42 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=7872 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:43 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=7 retries=0 total_spawns=1
2026-10-28 01:21:43 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:43 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=1 retries=0 signal=0 tools=0 out_chars=7 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=0.28
.2026-10-28 01:21:43 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:43 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:43 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-28 01:21:43 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-28 01:21:43 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:44 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:44 unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-28 01:21:44 exec retry=2 (unmapped built-in tool) total_spawns=2/3
2026-10-28 01:21:44 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=2214 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:45 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-28 01:21:45 incomplete tool step: retries exhausted (0) signal=4
2026-10-28 01:21:45 done model=muse-spark-1.3-contributor-free rc=0 state=ok tools=0 out_chars=125 retries=2 total_spawns=3
2026-10-28 01:21:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:45 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=30 ttft_ms=30 transport_history=['run'] duration_s=2.29
.2026-10-28 01:21:45 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:45 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:45 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:45 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-28 01:21:45 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-28 01:21:46 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:46 stream unmapped built-in tools=['todoread']: re-prompt 2/2
2026-10-28 01:21:46 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=2214 total_spawns=2/3
2026-10-28 01:21:47 retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached
2026-10-28 01:21:47 stream incomplete tool step: retries exhausted (0) signal=4
2026-10-28 01:21:47 stream done model=muse-spark-1.3-contributor-free rc=0 tools=0 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-28 01:21:47 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=0 total_spawns=3 retries=2 signal=0 tools=0 out_chars=125 transport=run first_event_ms=28 ttft_ms=2029 transport_history=['run'] duration_s=2.29
.2026-10-28 01:21:47 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:47 exec: provider error mid-response (transient=True), stopping opencode run
2026-10-28 01:21:47 exec cli failed rc=1 state=provider_error stderr_tail='HTTP None: provider.transport: Connection lost: ECONNRESET'
2026-10-28 01:21:47 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:47 unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-28 01:21:47 exec retry=1 (unmapped built-in tool) total_spawns=1/3
2026-10-28 01:21:47 exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1715 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:48 exec: step with tool call finished, stopping opencode run
2026-10-28 01:21:48 done model=muse-spark-1.3-contributor-free rc=-15 state=nonzero_exit tools=2 out_chars=0 retries=1 total_spawns=2
2026-10-28 01:21:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:48 O-EXIT/v1 mode=json model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=2 retries=1 signal=0 tools=2 out_chars=0 transport=run first_event_ms=28 ttft_ms=28 transport_history=['run'] duration_s=1.03
.2026-10-28 01:21:48 stream exec model=opencode/muse-spark-1.3-contributor-free -m opencode/muse-spark-1.3-contributor-free#high --standalone --thinking prompt_chars=1216 cwd=/var/folders/2f/***/T/tmp7y_4_nm3/ws
2026-10-28 01:21:48 http "POST /v1/chat/completions HTTP/1.1" 200 -
2026-10-28 01:21:48 opencode built-in tool event: tool=todoread status=error mapped=False as=[]
2026-10-28 01:21:49 stream unmapped built-in tools=['todoread']: re-prompt 1/2
2026-10-28 01:21:49 stream exec retry=1 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1715 total_spawns=1/3
2026-10-28 01:21:51 stream incomplete tool step: re-prompt 1/2 signal=4 total_spawns=2/3
2026-10-28 01:21:51 stream exec retry=2 fail_retries=0 model=opencode/muse-spark-1.3-contributor-free prompt_chars=1900 total_spawns=2/3
2026-10-28 01:21:51 stream: step with tool call finished, stopping opencode run
2026-10-28 01:21:51 stream done model=muse-spark-1.3-contributor-free rc=-15 tools=2 out_chars=125 emulate_tools=True retries=2 total_spawns=3
2026-10-28 01:21:51 O-EXIT/v1 mode=stream model=muse-spark-1.3-contributor-free status=200 exit_reason=ok rc=-15 total_spawns=3 retries=2 signal=4 tools=2 out_chars=125 transport=run first_event_ms=28 ttft_ms=1030 transport_history=['run'] duration_s=2.68
.....2026-10-28 01:21:51 tool_strip_cap_hit max=16 dropping tail
2026-10-28 01:21:51 tool_strip_cap_hit max=16 dropping tail
2026-10-28 01:21:51 tool_strip_cap_hit max=16 dropping tail
..........................................................2026-10-28 01:21:53 tool_call_unparsed bytes=114 head='{"name": "read", "arguments": {"file_path": "/a"}} `<tool_call>`{"name": "read", "arguments": {"file_path": "/b"}}'
...2026-10-28 01:21:53 tool_call_unparsed bytes=23 head='<tool_call>{"name":"a"}'
2026-10-28 01:21:53 tool_call_unparsed bytes=47 head='{"name":"a"}<tool_call> <tool_call>{"name":"b"}'
2026-10-28 01:21:53 tool_call_unparsed bytes=23 head='{"name":"a"}<tool_call>'
.2026-10-28 01:21:53 tool_call_unparsed bytes=32 head='{"name": "a"} <tool_call>{broken'
..............................................
----------------------------------------------------------------------
Ran 511 tests in 387.846s

OK
```

### `VER-003-root-pythonpath-pytest` (`l2-green-ver003-pythonpath.log`, `sha256=abc1dc29b65e26d389d59e2fd84d62c475468add61c25d675b6f08e2affdabf5`)
```text
$ uvx pytest -q -p no:cacheprovider tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=382.46s]
--- STDOUT ---
.......................sss........................... [  5%]
..s..................................................................... [ 13%]
.......................................................... [ 20%]
........................................................................ [ 28%]
........................................................................ [ 36%]
................................. [ 40%]
.......................................................... [ 46%]
s............................................. [ 51%]
...................................................................... [ 59%]
.............................................................. [ 66%]
............................ [ 69%]
........................................... [ 74%]
................................................... [ 79%]
................................................................. [ 87%]
............................................................. [ 93%]
............................... [ 97%]
...................... [ 99%]
..                                                                       [100%]
894 passed, 5 skipped, 8103 subtests passed in 381.79s (0:06:21)

--- STDERR ---
```

### `VER-003b-root-pythonpath-zen-pytest` (`l2-green-ver003b-zen-pythonpath.log`, `sha256=ce51cd18a36a43dcb76a416f5cd05be1b6c35d51349a8b896f7fedc8c6645423`)
```text
$ uvx pytest -q -p no:cacheprovider bridges/opencode-zen-bridge/tests/
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom] [rc=0] [wall=422.86s]
--- STDOUT ---
......................... [  4%]
............................................................................................................................................ [ 32%]
............................................................... [ 44%]
................................ [ 50%]
............................................. [ 59%]
................................................................. [ 72%]
.................................................................... [ 85%]
................................................................... [ 98%]
......                                                               [100%]
511 passed, 3387 subtests passed in 422.57s (0:07:02)

--- STDERR ---
```

### `VER-005-dedicated-realtime-suite` (`l2-green-ver005-dedicated.log`, `sha256=70ac05fa969f04b82e38cc1bf5e322422cf7d59e604d78b7628377e373fef834`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=346.55s]
--- STDOUT ---
............................................................. [ 46%]
................................................................... [ 96%]
....                                                                     [100%]
132 passed, 232 subtests passed in 345.98s (0:05:45)

--- STDERR ---
```

### `AC-023-pytest-reversed` (`l2-green-ac023-reversed.log`, `sha256=9529bd0742f480dd803b9f2fed6371e166342fb2d46664d24ee13ae223ea3664`)
```text
$ uvx pytest -q -p no:cacheprovider tests/test_zen_catalog.py tests/test_tool_emulation.py tests/test_sync_yaml.py tests/test_stream_thinking.py tests/test_step_interruption.py tests/test_stdin_prompt.py tests/test_run_env.py tests/test_realtime_reasoning.py tests/test_native_fallback.py tests/test_lenient_tool_call.py tests/test_google_direct.py tests/test_go_model_routing.py tests/test_effort_mapping.py tests/test_cli_failure.py tests/test_catalog_reload.py tests/test_catalog_mode.py tests/test_catalog.py tests/test_aliases.py
[cwd=/tmp/cel-runs/zen-realtime-reasoning-20261025/l2-cleanroom/bridges/opencode-zen-bridge] [rc=0] [wall=427.09s]
--- STDOUT ---
.................................................................. [ 12%]
................................................................. [ 25%]
................................................................. [ 38%]
............................................................................. [ 53%]
...................................................................... [ 67%]
................................................................ [ 79%]
........................ [ 84%]
................ [ 87%]
................................. [ 93%]
............................ [ 99%]
...                                                               [100%]
511 passed, 3387 subtests passed in 426.79s (0:07:06)

--- STDERR ---
```

