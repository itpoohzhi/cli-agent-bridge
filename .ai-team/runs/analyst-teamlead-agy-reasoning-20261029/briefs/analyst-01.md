Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

# Бриф: Системный аналитик (Stage 1 `system-analyst`, пресет `analyst-teamlead`)

- **Роль:** Системный аналитик (только анализ As-Is, выявление корневых причин, формулировка верифицируемых требований `REQ-*`, критериев приёмки `AC-*`, `HL-ENV/v1` из 46 полей и передача `handoff-architect.md` + `handoff-qa.md`). Код продукта НЕ менять!
- **Обязательный скилл для чтения (ровно один):**
  `~/Мой диск/skils/ai-sdlc/universal/system-analyst/SKILL.md` (а также его `references/artifacts-and-handoff.md` и SSoT 46 полей `HL-ENV/v1` в `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md`).

## Уже известно (пре-флайт путей)
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning`
- `branch`: `feature/agy-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029`
- `analysis_dir` (куда записать 5 выходных файлов): `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning`
- Целевые файлы продукта (читать As-Is, НЕ модифицировать):
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/bridges/agy-bridge/server.py`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/bridges/agy-bridge/tests/test_agy_bridge.py`
- Первичные материалы проведённого ресерча (прочитать для фактов `F-NN` и точных таймингов):
  - `/tmp/cel-runs/agy-streaming-research-20261029/close.md`
  - `/Users/aazhiry1/Мой диск/Работа/Sber/knowledge-base/tools/dsh-bridges-cli-agent-bridge.md` (раздел про `agy-bridge (:9887)`)
- Образец успешно прошедшего `SA-DOD-001..008` анализа в этом же репозитории (можно сверить структуру и табличный формат 46 полей `HL-ENV/v1`):
  - `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/analysis/zen-realtime-reasoning/handoff-architect.md`

## Контекст задачи и подтверждённые факты исследования
Владелец сообщил: при работе с `gemini-4-argon` (Antigravity `agy` `1.4.9`) через `agy-bridge` (`127.0.0.1:9887`) в DSH во время фазы размышления (15–45+ секунд) размышления не отображаются в реальном времени («висит как будто бы не работает»).
Реверс-инжиниринг и живые замеры `agy` `1.4.9` (`~/.gemini/antigravity-cli/releases/1.4.9/agy`, `server.js`) выявили 4 корневые проблемы:
1. **RC-1 (Отсутствие live-источника `thinking` во время шага генерации):**
   - `agy --output-format stream-json` выдаёт на `stdout` только `system/init` на старте и финальный `result` в самом конце хода (через 20–45+ с), без дельт `thinking` и текста.
   - Файл `~/.gemini/antigravity/brain/<cid>/.system_generated/logs/transcript_full.jsonl`, который сейчас поллит `_TranscriptTail` (`bridges/agy-bridge/server.py:553-702`), обновляется процессом `agy` **только после завершения шага** (`status: "DONE"`). Пока модель думает (`status=8` `CORTEX_STEP_STATUS_GENERATING`), `transcript_full.jsonl` пуст или содержит только `USER_INPUT`.
   - При этом локальная SQLite-база `~/.gemini/antigravity-cli/conversations/<cid>.db` (таблица `steps`, `step_type = 15` `CORTEX_STEP_TYPE_PLANNER_RESPONSE`) обновляется процессом `agy` **в реальном времени каждые ~1.5–3 секунды** по мере генерации каждого абзаца размышления (`status = 8` `GENERATING` -> `status = 3` `DONE`).
   - В колонке `steps.step_payload` (protobuf binary message `CortexStepPlannerResponse` в поле `20` корневого `CortexStep`) хранятся:
     - subfield `1` (wire type 2, string): `response` (финальный текст шага)
     - subfield `3` (wire type 2, string): `thinking` (накопленный текст размышления шага, обновляется инкрементально в `status=8`)
     - subfield `6` (wire type 2, repeated message `ToolCall`): вызовы инструментов
   - Чтение `file:~/.gemini/antigravity-cli/conversations/<cid>.db?mode=ro` через стандартный модуль `sqlite3` (stdlib Python) и лёгкий pure-Python парсер protobuf wire-формата (varint + length-delimited поля `20 -> 3`) в `_TranscriptTail` (в дополнение к существующему чтению `transcript_full.jsonl` как fallback/источнику DONE-шагов) позволяет стримить `reasoning_content` дельты в реальном времени каждые 1.5–3 с во время `status=8`.
2. **RC-2 (Гонка финального дренирования `Run._pump` vs `_TranscriptTail` на одношаговых ходах):**
   - На коротких/одношаговых ответах `agy` печатает `{"event":"result"}` в `stdout` примерно за 90 мс **до** того, как дописывает финальный шаг в `transcript_full.jsonl` / `conversations/<cid>.db`.
   - Сейчас `Run._pump` (`bridges/agy-bridge/server.py:920-935`) при получении `event=="result"` делает лишь `time.sleep(0.05)` и сразу кладёт `("done", ...)` в очередь `self.q`, тогда как `_TranscriptTail` спит `TRANSCRIPT_GRACE_S = 0.4` с (`server.py:626`) и имеет интервал поллинга `0.15` с. В результате `Handler._execute` выходит из цикла чтения `self.q` по `("done", ...)` до того, как `_TranscriptTail` успевает вычитать финальную дельту `thinking`.
   - Нужна детерминированная синхронизация финального дренирования перед эмиссией `("done", ...)` (например, сигнал/вызов финального poll-прохода `_TranscriptTail` после `result`/`EOF` до постановки `("done", ...)` в очередь).
3. **RC-3 (Потеря уже отданного клиенту `reasoning` при ошибке на последующем шаге — `delivered` флаг в `Handler._run_once`):**
   - В `Handler._run_once` (`bridges/agy-bridge/server.py:1154`) флаг `delivered = bool(out.get("text") or out.get("tool_calls"))` не учитывает `out.get("reasoning")`.
   - Если на Шаге 1 мост уже отдал клиенту по SSE чанки `reasoning_content`, а на Шаге 2 произошёл сбой (например, rate limit или обрыв), `delivered` оказывается `False`, и мост либо идёт на полный retry с нуля (дублируя/ломая поток), либо шлёт терминальный error-чанк поверх уже отданного размышления. Учёт `out.get("reasoning")` (или явная защита уже отправленных SSE-чанков) предотвращает разрушение стрима.
4. **RC-4 (Коллизия `sess_key` с фоновыми запросами без инструментов, например генерацией заголовка чата в DSH):**
   - В `Handler._execute` (`bridges/agy-bridge/server.py:1377`) ключ сессии `sess_key = (model_id, cwd, effort)` не различает основной диалог (с `tools`) и параллельный фоновый запрос DSH на генерацию заголовка чата (`tools` пуст, `messages` длины 1). Фоновый запрос перезаписывает `_LAST_CONV[sess_key]`, уводя `conversation_id` основного чата. Добавление признака наличия `tools` (например, `bool(tools)`) в `sess_key` изолирует такие запросы.

## Требуемые выходные артефакты (строго в `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/`)
Создай все 5 файлов:
1. `research-plan.md` — план исследования, гипотезы, источники фактов, статус выполнения.
2. `evidence-ledger.md` — реестр пронумерованных фактов `F-01`, `F-02`, ... с точными ссылками на строки `bridges/agy-bridge/server.py`, `bridges/agy-bridge/tests/test_agy_bridge.py` и результаты живых замеров `agy` `1.4.9`.
3. `open-questions.md` — таблица `OPEN-01`, `OPEN-02`, ... с колонками `| ID | Класс | Вопрос | Допущение / закрытие | Статус |`. **ВАЖНО:** ни один вопрос не должен оставаться в статусе `open` / `не закрыт` / `pending` с классом `[BLOCKER]` (все вопросы должны быть закрыты фактами или явно помечены `[ASSUMPTION]` / `closed`, чтобы `SA-DOD-002` прошёл!).
4. `handoff-architect.md` — полный архитектурный handoff, содержащий:
   - Постановку и цепочку корневых причин (`RC-1..RC-4`) со ссылками на `F-NN`.
   - As-Is карту потока с привязкой к `F-NN`.
   - Таблицу требований `REQ-001..REQ-012` (каждый `REQ-NNN` в одной строке содержит приоритет `MUST` или `SHOULD`, ссылки на факты `F-NN` и измеримый критерий `AC-NNN` — требование `SA-DOD-004`!).
   - Сравнение вариантов дизайна (без навязывания одного решения вместо Архитектора, но с полной фактурой по SQLite `conversations/<cid>.db` protobuf `20.3` + fallback `transcript_full.jsonl`, синхронизации drain, `delivered` и `sess_key`).
   - Полный раздел `HL-ENV/v1` со всеми **46 атомарными полями** из `REQUIRED_HL_ENV_FIELDS` (`W`, `P_pods`, `G_reload`, `T_threads_per_worker`, `Limit_dep_total`, `Limit_dep_share`, `Pool_app_size`, `Pool_app_overflow`, `Max_in_flight_per_worker`, `N_roles`, `W_role`, `Pool_role_size`, `Pool_role_overflow`, `M_other_apps_max`, `Ephemeral_port_range_size`, `TIME_WAIT_s`, `ulimit_n`, `FD_non_socket_overhead`, `N_bg_tasks`, `T_poll_s`, `Jitter_Ratio`, `Startup_Delay_Range_s`, `K_calls`, `Limit_dep_rps`, `Cold_start_concurrent_pods`, `Singleflight_Scope`, `Cache_TTL_s`, `Max_stale_age_s`, `Payload_bytes_max`, `N_items_max`, `Hot_path_call_rate_rps`, `CPU_budget_pct_per_core`, `Serde_lib`, `P_avail_min`, `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max`, `SLA_p99_s`, `T_connect_s`, `T_read_s`, `Retries_max`, `Retry_Budget_pct`, `Retry_Window_s`, `Min_Retry_Floor_rps`, `N_candidates`, `N_floor`) — проверь, что все 46 идентификаторов дословно присутствуют в `handoff-architect.md` и каждый `F-NN` в `handoff-architect.md` объявлен в `evidence-ledger.md`!
5. `handoff-qa.md` — матрица верификации `AC-NNN`, позитивные/негативные/граничные тест-кейсы (включая unit-тесты парсера protobuf `20.3` с multi-byte varint, UTF-8 кириллицей, unknown wire types 0/1/2/5, truncated payload без краша, инкрементальными дельтами `status=8 -> status=3`, дедупликацией между SQLite и `transcript_full.jsonl`, синхронизацией финального drain при быстром `result`, сохранением `delivered` при `reasoning` и изоляцией `sess_key`), а также сценарий L3 тяжёлой проверки на `:9887`.

Перед завершением работы запусти композитный самочек `SA-DOD-001..008` из `analyst-teamlead/SKILL.md` на каталоге `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning` и убедись, что выводится `SA-DOD-001..008 PASS`, а `git status --porcelain` показывает изменения только в `analysis/agy-realtime-reasoning/` и `.ai-team/`.
