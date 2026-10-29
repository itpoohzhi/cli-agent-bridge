# Матрица трассируемости верификации (`teamlead/verification-traceability.md`)

- **Run ID:** `analyst-teamlead-agy-reasoning-20261029`
- **Task ID:** `agy-realtime-reasoning`
- **Architecture Packet SHA-256:** `62a83bb2f0bfd9e9e975a05a5aea61991d27f49f642d1b810fc2a87dc4af2aab`
- **Base SHA:** `e00da0621fc95f7c63cd1565f4a5d1fd490c8d66`

## Поштучная матрица `REQ-001..REQ-012`, `AC-001..AC-016`, `AD-001..AD-006`, `AO-01..AO-12` и `VER-001..VER-012`

| Требование / Оракул | Архитектурное решение | Реализация в `bridges/agy-bridge/server.py` | Тестовые оракулы в `tests/test_agy_bridge_resilience.py` | Статус в Clean-Room L2 (`execution-evidence.md`) |
|---|---|---|---|---|
| `REQ-001` (`AC-001`, `AC-002`) | `AD-001` | `_TranscriptTail._poll_sqlite`, `_emit_reasoning`, опрос `steps` (`step_type=15, status=8`) | `TC-20`, `TC-21`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-002` (`AC-003`) | `AD-001` | `_extract_step_thinking` (pure-Python protobuf wire parser поля 20 -> 3, UTF-8 tail trim) | `TC-01..TC-12` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-003` (`AC-004`, `AC-005`) | `AD-001` (`F-001`, `F-003`, `F-008`) | Общий `seen[idx]` (`observed_*`, `delivered_*`, `finalized`, `diverged`), заморозка при divergence | `TC-23`, `TC-24`, `AO-10`, `AO-12` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-004` (`AC-006`) | `AD-001`, `AD-005` (`F-002`) | Fail-open `mode=ro` (`uri=True`, `query_only=ON`, `busy_timeout=50`), FSM breaker `AO-01` | `TC-30..TC-33`, `AO-01`, `AO-08` (`VER-003`, `VER-005`, `VER-007`, `VER-009`) | `PASS` (`exit_code=0`) |
| `REQ-005` (`AC-007`) | `AD-001` (`F-001`, `F-004`) | Pre-spawn водяной знак `base_idx = max(t_max, db_max) + 1`, `turn_mode="OFF"` без SQLite-якоря на resume | `TC-50`, `TC-51`, `AO-08`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-006` (`AC-008`) | `AD-002` (`F-005`) | `_pump` в `try/finally` с `_close_and_put_done`, полное окно `DRAIN_WINDOW_S = 0.35 s`, `_execute` до `done` | `TC-60..TC-63`, `AO-03`, `AO-11`, `tc93` (`VER-003`, `VER-005`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-007` (`AC-009`) | `AD-002` (`F-005`) | Ограниченный drain `EOF -> stop <= 1.0 s`, `conn.interrupt()` перед финальным `join` | `TC-62`, `TC-63`, `AO-03`, `tc93` (`VER-003`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-008` (`AC-010`) | `AD-003`, `AD-005` | В `_run_once` для `stream=True` отданное мышление (`delivered['reasoning_chars'] > 0`) запрещает тихий повтор | `TC-70..TC-72`, `AO-02`, `AO-11` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-009` (`AC-011`) | `AD-004` (`F-004`) | Изоляция `_session_store`: запросы без `tools` (`tools_count == 0`) не занимают и не перезаписывают горячую сессию | `TC-80..TC-82`, `AO-08` (`VER-003`, `VER-005`, `VER-007`) | `PASS` (`exit_code=0`) |
| `REQ-010` (`AC-012`, `AC-013`) | `AD-001..AD-004` | Сохранён контракт `:9887`, 22 старых теста без изменений (`VER-006`), 4 аддитивных поля `/health` | `AO-06`, 22 baseline-теста (`VER-001..VER-008`, `VER-012`) | `PASS` (`exit_code=0`) |
| `REQ-011` (`AC-014`) | `AD-006` (`F-006`) | `dynamic_config.json` (`SQLITE_REASONING_ENABLED`, TTL 1.0 s) + `AGY_SQLITE_REASONING_ENABLED`, kill-switch `<= 1.30 s` | `TC-91`, `AO-07`, `AO-09`, `tc93` (`VER-003`, `VER-007`, `VER-009`, `VER-010`) | `PASS` (`exit_code=0`) |
| `REQ-012` (`AC-015`, `AC-016`) | `AD-001`, `AD-005` (`F-008`) | Логи `sqlite-emit`/`sqlite-off`/`drain` без текста мышления, token bucket `N(Δt)<=3+2Δt`, `RSS<=112 MiB`, `CPU<=1%` | `TC-40..TC-44`, `TC-92`, `AO-04`, `AO-05`, `tc93` (`VER-003`, `VER-007`, `VER-010`) | `PASS` (`exit_code=0`) |
| `VER-011` (`L3 Live`) | Все `AD-001..AD-006` | Живая проверка на `:9887` после `ACCEPT` Совета и влития MR | Ручной/живой гейт `L3` | `DEFERRED_L3` (после `ACCEPT` Совета и merge MR) |

| `Full Suite Gate (J3-003)` | Отсутствие регрессий во всём репозитории (`tests/`) | `bridges/agy-bridge/server.py`, `tests/test_agy_bridge_resilience.py` | `VER-013`: `/usr/bin/python3 -m unittest discover -s tests` в чистой комнате на `base_sha` (899 тестов, 2 внешних падения `test_muse_bridge_killpg.py`) и на кандидате (974 теста = +75 новых в `test_agy_bridge_resilience.py`, те же 2 внешних падения, 0 новых регрессий) | `PASS` |
