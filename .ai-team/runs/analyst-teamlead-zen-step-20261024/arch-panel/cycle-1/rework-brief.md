# Сводка доработки после Цикла 1 Архитектурного Совета (rework-brief)

- **Run ID:** `analyst-teamlead-zen-step-20261024`
- **Роль:** `panel-rework-summarizer` (`claude-sonnet-5-5`, `high`, `claude-cli`)
- **Исходный раунд:** `.ai-team/runs/analyst-teamlead-zen-step-20261024/panel/arch/r1`
- **Вердикт раунда 1:** `NEEDS WORK` (Seat 2 `gemini-4-argon-high` = `ACCEPT`, Seat 3 `muse-wonder-full-1.0` = `ACCEPT`, Seat 1 `grok-4.7-high` = `NEEDS WORK` по `F1..F7`)

---

## Вывод `panel-rework-summarizer` (`claude-sonnet-5-5` `high`)

Две проверяемые цифры рецензента пересчитаны, обе верны:
1. Сумма листьев в семи старых группах `workload_envelope..observability_concurrency_envelope` (7+5+7+9+6+6+5) равна 45, а не 46, и использованы самодельные ключи вместо 46 канонических идентификаторов `REQUIRED_HL_ENV_FIELDS`.
2. Замыкание памяти в v4 не сходилось (`512 МБ > 0,80 × 512 = 409,6 МБ`).

### Часть 1. Что менять в архитектурном пакете (`architecture-packet.json` и `handoff-architect.md`)

1. **`F1 BLOCKER` — Канонический конверт `HL-ENV/v1` (46 атомарных полей `REQUIRED_HL_ENV_FIELDS`) и замыкание памяти:**
   - Включить все 46 точных идентификаторов `REQUIRED_HL_ENV_FIELDS` из `aisdlc-gcge/agents/architecture.md` §3.0:
     `P_steady`, `P_hpa_max`, `maxSurge_pct`, `maxSurge_abs`, `maxUnavailable_pct`, `maxUnavailable_abs`, `P_terminating_overlap`, `P_live`, `P_avail_min`, `W`, `N_proc`, `N_proc_steady`, `N_proc_avail_min`, `CPU_limit_per_pod`, `κ_skew`, `u_bg_worker`, `U_pod_sidecars`, `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max`, `RPS_peak`, `A_max`, `SLA_p99_s`, `N_entities_max`, `Limit_dep_share[d]`, `Limit_dep_rps[d]`, `W_fetchers[d]`, `J_init_s[d]`, `J_pod_s[d]`, `T_poll_s[d]`, `K_calls[d]`, `T_base_s[d]`, `T_cap_s[d]`, `Max_stale_age_s[c]`, `Min_healthy_ratio`, `B_retry_max`, `min_reserve_retry_rps`, `FD_worker`, `ulimit_n`, `λ_new_conn_per_pod(s)`, `C_active_in_scope(s)`, `N_pods_in_scope(s)`, `Port_range_size(s)`, `T_hold_s(s)`, `SNAT_ips_count(s)`, `HOTPATH_MODULES`.
   - Замыкание памяти с учётом дочерних процессов `opencode run`:
     - `Mem_limit_per_pod = 2147483648` байт (`2048 MiB`, локальный демон macOS LaunchAgent без cgroup limit, консервативный потолок инстанса `2 GiB`),
     - `W = 1` (один Python-процесс `ThreadingHTTPServer`),
     - `Mem_rss_worker_max = 67108864` байт (`64 MiB` RSS Python-процесса моста),
     - `Mem_shared_max = 1207959552` байт (`1152 MiB` = пик до `MAX_CONCURRENT = 6` одновременных дочерних процессов `opencode run` по `192 MiB` RSS каждый),
     - Проверка неравенства `HL-ENV-01`:
       $$W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} = 1 \times 64\text{ MiB} + 1152\text{ MiB} = 1216\text{ MiB} \le 0.80 \times 2048\text{ MiB} = 1638.4\text{ MiB} \quad (\text{PASS}).$$

2. **`F2 BLOCKER` — 21 канонический стоп-код (`HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5`), `Dependency Failure Matrix`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1` и ограничение `_StdoutFeed`:**
   - Заменить произвольные имена инвариантов на 21 канонический стоп-код `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` с численной подстановкой по формулам §3.1–3.4 и §7.2 `aisdlc-gcge/agents/architecture.md`.
   - Для каждого `N/A` указать двойное доказательство: (а) `git diff` затронутых файлов (`bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`) и (б) транзитивный граф `callers/callees` от точек входа `Handler.do_POST`, `_stream_response`, `_complete_response`, `_run_opencode`.
   - Добавить явную таблицу `Dependency Failure Matrix` и проверки `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`.
   - Ограничить очередь `_StdoutFeed`: `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`STDOUT_QUEUE_MAX = 4096`), при переполнении (`queue.Full`) логировать ошибку и останавливать дочерний процесс (`_stop_proc(proc)`), не допуская неограниченного роста кучи.

3. **`F3 MAJOR` — Единый потолок `A_max = 3` запусков `opencode run` на запрос, единый Full-Jitter backoff и согласование `_StartupGate` с `SLA_p99_s`:**
   - Ввести единый счётчик запусков `total_spawns` на один HTTP-запрос (`MAX_TOTAL_SPAWNS = 3`, т.е. `A_max = 3`: 1 первичный запуск + не более 2 ретраев суммарно по `fail_retries` и `attempt`) под общим `deadline = time.monotonic() + TIMEOUT_S`.
   - Унифицировать межатемптовую паузу по формуле Full Jitter из `S-HERD-I2`: `random.uniform(0.0, min(T_cap_s, T_base_s * (2 ** retry_num)))` (с инъектируемым `rng_fn` для детерминированных unit-тестов без wall-clock флаков, `T_base_s = 0.5`, `T_cap_s = 2.0`).
   - В `_StartupGate` освобождать слот сразу после первого полезного события (`step_start`/`text`/`reasoning`/`tool_use`) или завершения процесса (как уже реализовано, в среднем `~1.5–2.0 с`, а `STARTUP_GATE_S = 12.0` — лишь аварийный потолок зависшего старта), и явно отразить `SLA_p99_s = 180.0`, `latency_p95_ms = 90000`.

4. **`F4 MAJOR` — Сужение признака 5 (преамбула) и отдельный kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`:**
   - В `_is_incomplete_tool_step`: признак 5 (короткая преамбула с двоеточием `stripped.endswith(":")`) НЕ срабатывает по голому двоеточию без явного глагола намерения из `_ACTION_INTENT_RE` (`Let me ...:`, `I'll ...:`, `Сейчас я ...:`, `Давайте проверим...:`) либо без признаков 3/4. Короткий финальный ответ с двоеточием (например, `"Ответ: 42:"` или `"Результат проверки:"`) детерминированно возвращает `False`.
   - Ввести отдельный kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY` (дефолт `"1"`, при `"0"`/`"false"` отключает `_is_incomplete_tool_step` и step-recovery retry независимо от `OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES`).
   - Поднять `RISK-001` `impact` до `"medium"`.

5. **`F5 MAJOR` — Fallback при несовпадении `dedup_prefix` и фильтрация транзиентных `etype == "error"`:**
   - Если `attempt > 0` и новый текст `current` НЕ начинается с `dedup_prefix` (модель переформулировала ответ на ретрае), не терять и не обрезать текст: сбрасывать `dedup_prefix = ""` и отправлять клиенту весь новый текст `current[emitted_len:]`. Добавить unit-тест на несовпадающий `dedup_prefix`.
   - Для `etype == "error"` считать ошибку транзиентной (`had_mid_stream_error = True`) только если `statusCode` отсутствует/`None`/`0`/`408`/`429`/`>= 500` либо сообщение содержит транзиентный маркер (`timeout`, `timed out`, `econnreset`, `etimedout`, `socket hang up`, `interrupted`, `overloaded`, `rate limit`, `temporarily unavailable`, `fetch failed`, `network`). При детерминированных `statusCode in (400, 401, 403, 404, 422)` НЕ ретраить (`had_mid_stream_error = False`), а сразу возвращать ошибку. Добавить unit-тест на `401/400` vs `503/ECONNRESET`.

6. **`F6 MAJOR` & `F7 MINOR` (и `Seat 3 F1..F2`) — `CD-002`, привязка всех `EVD-001..016`, `threads_per_worker = 12` и `VER-004` (`diff -u` репо vs `~/.dsh`):**
   - Добавить `CD-002` в `contract_deltas` (SSE `: keepalive` комментарии каждые `15s` и восстановление наблюдаемого `finish_reason` со сломанного `"stop"` на целевой `"tool_calls"` при успешном ретрае).
   - Привязать все `EVD-001..EVD-016` к `AD-001..AD-003` и `RISK-001..RISK-004` (без висячих `EVD-*`).
   - Указать `threads_per_worker = 12` (`6` HTTP-хендлеров + `6` daemon-потоков `_StdoutFeed`).
   - Добавить `VER-004` в `verification_Hooks`: побайтовая идентичность `diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py` (`exit=0`).
