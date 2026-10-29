# Слепая обратная спецификация (`teamlead/reverse-spec.md`)

Документ реконструирован по итоговому `candidate.diff` (`bridges/agy-bridge/server.py` и `tests/test_agy_bridge_resilience.py`).

## 1. Фактически изменённые файлы

1. **`bridges/agy-bridge/server.py` (изменён):**
   - Добавлен pure-Python wire-парсер protobuf `_extract_step_thinking(blob, stop_event)` для чтения поля `20` (вложенного сообщения `PLANNER_RESPONSE`) и подполя `3` (UTF-8 текста мышления) с пропуском wire-типов `0, 1, 2, 5`, проверкой `stop_event` каждые 64 тега и безопасной обрезкой незавершённой многобайтовой UTF-8 последовательности на промежуточных снимках (`status=8`).
   - В `_TranscriptTail` / `Run` встроен вспомогательный read-only опрос SQLite `conversations/<cid>.db` (`sqlite3.connect("file:...?mode=ro", uri=True, timeout=0.05, check_same_thread=False)`, `PRAGMA query_only=ON`, `PRAGMA busy_timeout=50`) с ограничением `LIMIT 16` и `CASE WHEN length(step_payload) <= 262144 THEN step_payload ELSE NULL END`.
   - Реализована пошаговая дедупликация между SQLite и `transcript_full.jsonl` по ключу `idx == step_index` с раздельным учётом `observed_len`/`observed_sha256` и `delivered_len`/`delivered_sha256`, флагами `finalized` и `diverged`, заморозкой выдачи шага при `divergence` (`sqlite_snapshot_divergence` / `sqlite_transcript_divergence`) и монотонным продвижением `poll_watermark`.
   - Реализован семантический canary (`SHADOW -> LIVE`) по идентичности бинаря `agy` `(st_mtime_ns, st_size)`, pre-spawn водяной знак на `resume` (`base_idx = max(t_max, db_max) + 1`, при ошибке pre-spawn SQLite — `turn_mode="OFF"`), реестр активных владельцев `_active_cid_owners` под `_session_store_lock`.
   - Реализованы защитные механизмы Highload & Resilience: целочисленный per-turn token bucket `N(Δt) <= 3 + 2*Δt`, процессный retry budget в десятых долях, 3-состояний circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN` с `probe_gen`) под `_sqlite_guard_lock`, потолок `MAX_REASONING_BYTES_PER_TURN = 2 MiB` и runtime kill-switch `SQLITE_REASONING_ENABLED` (`dynamic_config.json` с TTL 1.0 с + env `AGY_SQLITE_REASONING_ENABLED`) с немедленным `conn.interrupt()`.
   - Исправлены RC-2 (детерминированный post-EOF drain полным окном `0.35 с` и атомарная постановка единственного `("done", ...)` под `run._emit_lock` в `try/finally`), RC-3 (учёт отданного в SSE `reasoning` в `delivered`, запрещающий повтор хода после выдачи мышления клиенту) и RC-4 (изоляция `_session_store` от фоновых запросов без инструментов `tools_count == 0`).
   - В `/health` добавлены 4 аддитивных диагностических поля (`sqlite_reasoning_mode`, `sqlite_breaker_state`, `sqlite_divergence_count`, `sqlite_drain_deadline_count`). Устранены все 12 baseline-ошибок `basedpyright`.

2. **`tests/test_agy_bridge_resilience.py` (аддитивно расширен):**
   - Все 22 исходных теста сохранены без единой удалённой или изменённой строки (`VER-006`).
   - Добавлено 75 новых тестовых метода в классах `unittest.TestCase`, покрывающих все 51 обязательный идентификатор `VER-007` (`TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92`, `AO-01..AO-12`) и нагрузочный оракул `tc93` / `l2_harness` (`VER-010`).

### Дополнения по итогам ревью (J3-001, J3-002, MINOR-2, J3-003)
- **F-005 / J3-001 (`_drain_post_eof`)**: эвристический ранний выход `planner_final` (`final_planner and quiet >= 2`) полностью удалён (`server.py:1954-1992`); досрочный выход после `DRAIN_MIN_S` допускается исключительно по `end_marker` (`END_TURN`/`TURN_COMPLETE`) или `stop_event`, иначе выдерживается полное окно `DRAIN_WINDOW_S = 0.35 s` (`exit=window`), проверено тестом `test_ao03_planner_final_with_two_quiet_selects_holds_full_window` (`tests/test_agy_bridge_resilience.py:2389`).
- **F-008 / J3-002 (`_TranscriptTail._state`)**: при достижении `len(self.seen) >= MAX_STEPS_TRACKED` (128) и отсутствии финализированных шагов ниже `poll_watermark` вызывается `self._sqlite_off('seen_cap')` И вытесняется старейший ключ `del self.seen[min(self.seen)]` (`server.py:1668-1678`), гарантируя инвариант `len(self.seen) <= 128`, проверено тестом `test_seen_cap_evicts_oldest_when_no_finalized_below_watermark` (`tests/test_agy_bridge_resilience.py:2165`).
- **MINOR-2 (`_compat_promote`)**: чтение `current = _agy_binary_identity()` перенесено внутрь критической секции `with _sqlite_guard_lock:` (`server.py:1000-1006`).
- **L3 Gate (J3-005)**: живая проверка `VER-011` на `:9887` выполняется строго после `ACCEPT` Совета Тимлидов и **до** создания/вливания MR (`feature/agy-realtime-reasoning` -> `dev` -> `main`).
