# Техническая спецификация: Устранение сбоев SSE-фрейминга (`finish_reason`), `ClientPayloadError`, `503 draining` и `unknown_tool`

- **ADR:** `docs/adr/0024-stream-drain-finish-reason.md`
- **Аналитический пакет:** `analysis/stream-drain-finish-reason/handoff-architect.md` (`REQ-001..REQ-005`)

## 1. Трассируемость требований (`REQ-001..REQ-005`)

| ID | Требование | Затронутые модули | Тестовые оракулы |
|---|---|---|---|
| `REQ-001` | Исключить повторную отправку HTTP 200 заголовков после `_keepalive_cb` и гарантировать `finish_reason` + `[DONE]` в SSE | `server.py`, `core/turn_session_manager.py` | `tests/test_stream_drain_finish_reason.py` (`test_server_sse_body_skips_duplicate_headers_and_frames_errors_with_stop`, `test_buffered_turn_error_event_emits_finish_reason_and_done`) |
| `REQ-002` | Перехватывать обрыв/ошибку upstream в `relay_sse` при открытых `choices` с эмиссией `_error_frame` (`finish_reason="stop"` + `[DONE]`) | `adapters/passthrough_adapter.py` | `tests/test_stream_drain_finish_reason.py` (`test_passthrough_upstream_error_chunk_emits_finish_reason_and_done`, `test_passthrough_done_without_finish_reason_when_untrusted_tools`, `test_passthrough_eof_after_open_choice_emits_error_frame_and_done`) |
| `REQ-003` | Защитить интерактивные запросы в очереди `QoSSlotManager` при `drain_event` (`BRIDGE_DRAIN_QOS_GRACE_S`) и поддержать `BRIDGE_DRAIN_HOLD_TIMEOUT_S` | `core/lifecycle.py`, `server.py` | `tests/test_stream_drain_finish_reason.py` (`test_qos_interactive_waiter_survives_drain_event_within_grace`, `test_lifecycle_wait_for_drain_hold_respects_timeout`) |
| `REQ-004` | Подавить спам `[Вызов инструмента: unknown_tool]` для безымянных MSP-событий и отбраковывать безымянные tool calls | `adapters/muse_msp.py`, `core/tool_emulation.py`, `core/turn_session_manager.py` | `tests/test_stream_drain_finish_reason.py` (`test_muse_msp_suppresses_unknown_tool_and_extracts_alternate_keys`, `test_sanitize_tool_call_rejects_empty_name_and_turn_buffer_omits_empty_name`) |
| `REQ-005` | Соблюсти модульные границы `M-MOD/v1` (`legacy_delta_loc <= 0` для файлов `>300` LOC, `fn_loc <= 40`, `args <= 5`, `cc <= 10`) | Все изменённые модули | `module-bounds-report.json`, `PRE_FILTER_VALIDATOR` |
