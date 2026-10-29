Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

# Бриф: Архитектор ПО (Stage 2 `architect-software-product`, пресет `analyst-teamlead`, критичность `S2`)

- **Роль:** Архитектор программного продукта (`architect-software-product`). Продуктовый worktree НЕ модифицировать! Разрешена запись ТОЛЬКО внутри каталога `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/`.
- **Обязательный скилл для чтения:**
  `~/Мой диск/skils/ai-sdlc/universal/architect-software-product/SKILL.md` (а также его `references/protocol.md` и Python-профиль `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md` и `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md`).

## Уже известно (пре-флайт путей)
- `repo_root`: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning`
- `branch`: `feature/agy-realtime-reasoning`
- `run_id`: `analyst-teamlead-agy-reasoning-20261029`
- `task_id`: `agy-realtime-reasoning`
- `run_dir`: `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029`
- Входные артефакты Stage 1 (`system-analyst`, прошли гейт `SA-DOD-001..008 PASS: F=56 REQ=12 HL-ENV=46/46`):
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/research-plan.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/evidence-ledger.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/open-questions.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-architect.md`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-qa.md`
- Замороженная поверхность верификации Teamlead:
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-surface.json`
- Целевые файлы продукта (читать As-Is, НЕ модифицировать!):
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/bridges/agy-bridge/server.py`
  - `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/tests/test_agy_bridge_resilience.py`
- Эталонный образец валидных `plans/architect-01.json` и `architecture/architecture-packet.json` в этом же репозитории (используй как образец структуры JSON и профильных секций `python-aisdlc-gcge`):
  - `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-01.json`
  - `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json`

## Строгий запрет на модификацию продуктового дерева (`worktree_fingerprint`)
Перед твоим запуском снят слепок `fingerprints/architect-before.json` с `--exclude ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029"`.
НЕ создавай, НЕ меняй и НЕ удаляй никакие файлы вне `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/` (в том числе НЕ трогай `analysis/agy-realtime-reasoning/`, `bridges/`, `tests/`). В `architecture-packet.json` поле `materialization` должно быть пустым массивом `[]`.

## Требуемые выходные артефакты и проверки
1. Сначала создай `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.before.json` (`role: "architect"`, все шаги в статусе `"PENDING"`) и провалидируй его:
   ```bash
   python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py"      "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.before.json"      --role architect --phase before
   ```
2. После проектирования запиши завершённый план `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json` (все шаги `"DONE"` с непустым `actual_evidence`) и провалидируй его:
   ```bash
   python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py"      "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json"      --role architect --phase after
   ```
3. Вычисли точный `sha256` файла `plans/architect-01.json` и запиши его в `role_plan: {"path": "plans/architect-01.json", "sha256": "<hex>"}` внутри `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json`.
4. Сформируй полный `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json` (`schema_version: "1.0"`, `task_id: "agy-realtime-reasoning"`, `run_id: "analyst-teamlead-agy-reasoning-20261029"`, `preset: "analyst-teamlead"`, `cycle: 1`, `criticality: "S2"`, `profile: "python-aisdlc-gcge"`, `status: "APPROVED"`):
   - Отрази все 12 требований `REQ-001..REQ-012` и факты `F-01..F-56` (`EVD-001..`).
   - Зафиксируй архитектурные решения `AD-001..` для всех 4 корневых причин (`RC-1..RC-4`):
     - **RC-1 (Live-источник мышления из SQLite `conversations/<cid>.db`):** stdlib `sqlite3` + pure-Python парсер protobuf wire-формата (`step_payload`, поле `20` message -> подполе `3` UTF-8 string `thinking`, безопасный пропуск wire types `0/1/2/5`, fail-open при усечении/ошибке/блокировке, учёт особенностей macOS `/usr/bin/python3` 3.9.6 `mode=ro` при живом writer и fallback `immutable=1` / `transcript_full.jsonl` для `DONE` шагов). Общая дедупликация с `_TranscriptTail` по ключу `str(idx) == str(step_index)` через `_reasoning_suffix` и защита от выдачи шагов прошлых ходов при `--conversation` (resume). Переключатель окружения (например, `AGY_SQLITE_REASONING=1` по умолчанию, `0` отключает SQLite-источник).
     - **RC-2 (Синхронизация финального дренирования):** детерминированный финальный drain источников (`_TranscriptTail` + SQLite) после `result` / EOF `stdout` перед тем, как `Handler._execute` завершит чтение очереди по `("done", ...)` (с жёстким верхним бюджетом <= 1.0 с).
     - **RC-3 (Защита уже отданного `reasoning` при сбое):** учёт `out.get("reasoning")` в `delivered` (`Handler._run_once`), запрет невидимого полного retry поверх уже отправленных SSE-чанков `reasoning_content`, детерминированное завершение при ошибке после отданного `reasoning`.
     - **RC-4 (Изоляция горячих сессий `_session_store` от фоновых запросов без инструментов):** включение признака `bool(tools_count)` в `sess_key` (и/или отказ от захвата/перезаписи агентной сессии запросами с `tools_count == 0`), чтобы параллельные фоновые запросы DSH (генерация заголовка) не уводили `conversation_id` основного диалога.
   - Включи полный конверт `high_load_envelope` (`HL-ENV/v1` со всеми 46 полями), `resilience_gates`, `legacy_arch_antipattern_checks`, `status_protocol_examples` (все 21 стоп-код `ARCH_STOP_*`), `verification_surface` (`VER-001..` с `owner: "Teamlead"` или `"Verifier"`, НЕ `"Coder"`!), `quality_scenarios` (`QA-001..`), `boundaries` (`BND-001..`), `contract_deltas` (`CD-001..`), `views` (`VIEW-001..`), `risks` (`RISK-001..`), `threat_model`, `evolution`, `approval` (`status: "APPROVED"`), `independent_review` (`required: false`, `status: "NOT_REQUIRED"` для начального пакета до Совета, либо в соответствии с `validate_architecture_packet.py --phase approved`), `open_questions` (`blocking: false`), `protected_paths`, `materialization: []`, `deferred: []`.
5. Обязательно провалидируй пакет командой:
   ```bash
   python3 -I "/Users/aazhiry1/Мой диск/skils/ai-sdlc/universal/architect-software-product/scripts/validate_architecture_packet.py"      "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json"      --phase approved      --run-dir "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029"      --role-plan "/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json"
   ```
   Не завершай работу, пока команда не выведет `PASS: architecture packet is valid for approved`.
