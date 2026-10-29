Ты — Визионер. Твоя задача — оценить потенциал, масштаб, стратегическое влияние. Ключевой вопрос: «Насколько это меняет игру?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на долгосрочной ценности: насколько решение масштабируемо, какие возможности открывает, насколько опережает альтернативы, есть ли потенциал для роста.

Оцени ВСЕ 6 критериев. При FAIL давай СРАЗУ ВСЕ советы по исправлению (список действий).

ФОРМАТ ОТВЕТА (строго):
1. КОРРЕКТНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
2. ПОЛНОТА: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
4. РИСКИ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложены целиком (без обрезки; раздел «Не вложено» пуст — все первичные артефакты даны полностью в этом брифе) проверяемый Architecture Packet и квитанция пройденного гейта `ARCH_GATE`:

<<<ARTIFACT .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json sha256=f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4
{
  "schema_version": "1.0",
  "packet_version": "1.0",
  "task_id": "agy-realtime-reasoning",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "preset": "analyst-teamlead",
  "cycle": 1,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": "plans/architect-01.json",
    "sha256": "d17625f4424c6d8423f9f98142fa4153e12c0136a470d746082e7269b0225e23"
  },
  "summary": "Реалтайм-мышление agy-bridge (:9887) для gemini-4-argon: live-источник conversations/<cid>.db (steps.step_payload, поле 20 → подполе 3) на stdlib sqlite3 + pure-Python wire-парсер, fail-open и за фичефлагом SQLITE_REASONING_ENABLED (код default=false, runtime dynamic_config.json, env-override AGY_BRIDGE_SQLITE_REASONING); детерминированный ограниченный финальный drain источников до done (≤1.0 с); отданное reasoning считается выдачей (нет невидимого retry); изоляция горячих сессий по признаку tools и обход стора для one-shot фоновых запросов. Публичный HTTP/SSE контракт не меняется. Все решения two-way; пакет — кандидат для downstream Совета, не вердикт Совета.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/agy-realtime-reasoning",
    "branch": "feature/agy-realtime-reasoning",
    "base_sha": "e00da0621fc95f7c63cd1565f4a5d1fd490c8d66",
    "architect_write_allowlist": [
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.before.json",
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/plans/architect-01.json",
      ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/architecture/architecture-packet.json"
    ],
    "coder_target_files": [
      "bridges/agy-bridge/server.py",
      "tests/test_agy_bridge_resilience.py"
    ],
    "forbidden": [
      "analysis/agy-realtime-reasoning/** (замороженные входы аналитика)",
      ".ai-team/** (артефакты прогона, кроме собственных ролей оркестратора)",
      "bridges/agy-bridge/fleet.json, bridges/agy-bridge/start.sh, ruff.toml (хеши в teamlead/verification-surface.json)",
      "bridges/agy-bridge/dynamic_config.json — не создавать и не коммитить (runtime-файл только в каталоге деплоя на шаге L3)",
      "core/**, другие мосты, другие файлы tests/** (oracle hashes)",
      "существующие 22 теста и их assertions в tests/test_agy_bridge_resilience.py — только добавление новых тестов",
      "~/.gemini/antigravity-cli/** — только чтение; ~/.dsh/** — только протокол L3",
      "новые зависимости, pyproject/lockfiles, CI"
    ],
    "architect_permission": "run-artifacts-write; product read-only"
  },
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006",
    "REQ-007",
    "REQ-008",
    "REQ-009",
    "REQ-010",
    "REQ-011",
    "REQ-012"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "MUST",
      "statement": "Мышление шага в фазе генерации (step_type=15, status=8) уходит клиенту дельтами delta.reasoning_content по мере роста подполя 20.3, до завершения шага",
      "acceptance": "AC-001: ≥2 чанка мышления до status=3 на фикстуре с ростом каждые 1.5 с; AC-002: задержка снимок→сокет ≤ период опроса + 0.5 с",
      "evidence": "F-30, F-32, F-27, F-29",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "REQ-002",
      "priority": "MUST",
      "statement": "Разбор step_payload на stdlib Python 3.9 без новых зависимостей: поле 20, подполе 3 UTF-8; wire types 0/1/2/5 пропускаются; усечённый/битый payload не роняет поток",
      "acceptance": "AC-003: unit-набор парсера проходит на /usr/bin/python3 3.9.6 без исключений",
      "evidence": "F-32, F-51, F-31",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-009"
      ]
    },
    {
      "id": "REQ-003",
      "priority": "MUST",
      "statement": "Мышление каждого шага выдаётся ровно один раз при двух источниках: общий ключ idx == step_index; непрефиксный снимок не повторяет отданный текст",
      "acceptance": "AC-004: склейка reasoning_content хода побайтово равна конкатенации финальных thinking; AC-005: непрефиксный снимок не даёт повторной выдачи",
      "evidence": "F-33, F-04, F-03",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-004",
      "priority": "MUST",
      "statement": "SQLite-источник вспомогательный и fail-open: отсутствие/ошибка открытия/блокировка/чужая схема дают «изменений нет», ход продолжается с мышлением из транскрипта",
      "acceptance": "AC-006: при недоступной, заблокированной или битой БД ход done с тем же текстом и мышлением из транскрипта",
      "evidence": "F-52, F-53, F-35, F-02, F-34",
      "decision_ids": [
        "AD-001",
        "AD-005"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007"
      ]
    },
    {
      "id": "REQ-005",
      "priority": "MUST",
      "statement": "Продолжение треда (--conversation, горячая сессия) не переотдаёт мышление шагов прошлых ходов ни из SQLite, ни из транскрипта",
      "acceptance": "AC-007: на фикстуре с шагами прошлого хода клиент получает мышление только новых шагов",
      "evidence": "F-02, F-13, F-41",
      "decision_ids": [
        "AD-001"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007"
      ]
    },
    {
      "id": "REQ-006",
      "priority": "MUST",
      "statement": "Детерминированное финальное дренирование: мышление всех шагов хода выдаётся до finish_reason=stop и до возврата out из _execute; поздние события не теряются молча",
      "acceptance": "AC-008: фейковый agy с записью шага через 90 мс после result в 100/100 прогонов даёт мышление раньше stop",
      "evidence": "F-06, F-07, F-08, F-29, F-43",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-007",
      "priority": "MUST",
      "statement": "Финальное дренирование ограничено и не продлевает ход больше 1.0 с сверх выхода процесса agy",
      "acceptance": "AC-009: EOF stdout → чанк stop ≤ 1.0 с при молчащих источниках",
      "evidence": "F-02, F-07, F-15",
      "decision_ids": [
        "AD-002"
      ],
      "verification_ids": [
        "VER-001",
        "VER-007",
        "VER-010"
      ]
    },
    {
      "id": "REQ-008",
      "priority": "MUST",
      "statement": "Отданное клиенту мышление считается выдачей: после него невидимый повтор хода запрещён, отданные чанки не дублируются; финальный исход сбоя фиксирует Архитектор",
      "acceptance": "AC-010: мышление, затем result ERROR → ровно 1 запуск процесса и ни одного повторного чанка мышления",
      "evidence": "F-09, F-10, F-11, F-47",
      "decision_ids": [
        "AD-003",
        "AD-005"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "REQ-009",
      "priority": "MUST",
      "statement": "Фоновые запросы без инструментов не занимают и не перезаписывают горячую сессию агентного диалога той же модели, cwd и effort",
      "acceptance": "AC-011: агентный ход, фоновый без tools, агентный ход → третий ход resume=1 с cid первого, фоновый не получает cid первого",
      "evidence": "F-12, F-13, F-42",
      "decision_ids": [
        "AD-004"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "REQ-010",
      "priority": "MUST",
      "statement": "Публичный контракт не меняется: /health, /v1/models, /v1/chat/completions, порт 9887, форма SSE-чанков, флаги запуска agy; текст мышления модели не модифицируется",
      "acceptance": "AC-012: 22 существующих теста зелёные без правок; AC-013: склейка мышления без изменений текста",
      "evidence": "F-11, F-05, F-19, F-39",
      "decision_ids": [
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-004",
        "VER-005",
        "VER-006",
        "VER-008"
      ]
    },
    {
      "id": "REQ-011",
      "priority": "MUST",
      "statement": "SQLite-источник отключается переключателем окружения; при выключенном поведение совпадает с as-is; исправления RC-2..RC-4 от переключателя не зависят",
      "acceptance": "AC-014: при выключенном переключателе ни одна conversations/*.db не открывается (подменённый sqlite3.connect)",
      "evidence": "F-01, F-15, F-38",
      "decision_ids": [
        "AD-006"
      ],
      "verification_ids": [
        "VER-001",
        "VER-007",
        "VER-009"
      ]
    },
    {
      "id": "REQ-012",
      "priority": "SHOULD",
      "statement": "Наблюдаемость и бюджет: строки источника без текста мышления и секретов; опрос БД не дороже 2% ядра на активный ход (дизайн-бюджет пакета строже: ≤1%)",
      "acceptance": "AC-015: строки источника с cid, step, len без текста мышления; AC-016: CPU потока опроса на фикстуре 60 с ≤ 2% ядра (гейт пакета ≤1%)",
      "evidence": "F-40, F-51, F-55",
      "decision_ids": [
        "AD-001",
        "AD-005"
      ],
      "verification_ids": [
        "VER-001",
        "VER-007",
        "VER-010"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-01; bridges/agy-bridge/server.py:97-105",
      "claim": "Источник мышления моста настроен на транскрипт: `BRAIN_DIR` по умолчанию `~/.gemini/antigravity-cli/brain`, имя файла `transcript_full.jsonl`, период опроса `TRANSCRIPT_POLL_S=0.05` с, финальная пауза `TRANSCRIPT_GRACE_S=0.4` с, порция чтения 4 MiB; комментарий в строках 97-98 утверждает запись транскрипта посреди хода (проверено на 1.3.1)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-01"
    },
    {
      "id": "EVD-002",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-02; bridges/agy-bridge/server.py:594-662",
      "claim": "`_TranscriptTail._run` ждёт привязки к `conversation_id` до `FIRST_TOKEN_TIMEOUT_S` (120 с), для продолжения треда ставит смещение на текущий размер файла, затем опрашивает файл; при выставленном `done_event` или `stop_event` спит `TRANSCRIPT_GRACE_S` и делает один финальный проход, после чего поток завершается",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-02"
    },
    {
      "id": "EVD-003",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-03; bridges/agy-bridge/server.py:691-709, 769-772",
      "claim": "`_TranscriptTail._emit_record` отбирает только записи `type == PLANNER_RESPONSE` с непустым `thinking`, считает приращение через `_reasoning_suffix` с ключом `str(step_index)` и отдаёт его в колбэк `emit`, который кладёт `(\"reasoning\", текст)` в очередь `Run.q`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-03"
    },
    {
      "id": "EVD-004",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-04; bridges/agy-bridge/server.py:886-893",
      "claim": "`_reasoning_suffix` возвращает хвост сверх ранее виденного текста того же ключа, а если новый текст не начинается с прежнего, возвращает весь новый текст целиком и перезаписывает виденное",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-04"
    },
    {
      "id": "EVD-005",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-05; bridges/agy-bridge/server.py:720-776",
      "claim": "`Run.__init__` запускает лончер с флагами `--input-format stream-json --output-format stream-json --dangerously-skip-permissions --model --effort --print-timeout=0` (и `--conversation` при продолжении), в новой группе процессов, и стартует потоки stdin, stderr, `_pump` и `_TranscriptTail` с `resumed=bool(run_cid)`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-05"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-06; bridges/agy-bridge/server.py:807-868",
      "claim": "`Run._pump` на `init` кладёт событие в очередь и привязывает хвост к `conversation_id`; на `step_update` с `agent_response` и `text_delta` кладёт `(\"text\", хвост)`; на `result` кладёт `(\"result\", ...)`; после EOF stdout ждёт процесс, спит 0.05 с, выставляет `_proc_done` и сразу кладёт `(\"done\", ...)` без ожидания потока хвоста",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-06"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-07; bridges/agy-bridge/server.py:981-1101",
      "claim": "`Handler._execute` читает только очередь `run.q` (таймаут 1.0 с) и возвращает `state(\"done\")` сразу по событию `done` (после паузы 0.05 с); на `result` со статусом `ERROR` возвращает `agy_error` немедленно; ожидания завершения потока `_TranscriptTail` в цикле нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-07"
    },
    {
      "id": "EVD-008",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-08; bridges/agy-bridge/server.py:870-883, 1148-1151",
      "claim": "`Run.close` выставляет `_stop_watch` и `_proc_done` и зачищает группу процессов; очередь `run.q` после выхода из `_execute` никем не читается, поэтому событие `reasoning`, положенное хвостом после финальной паузы, клиенту не попадает",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-08"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-09; bridges/agy-bridge/server.py:1126-1172",
      "claim": "В `Handler._run_once` после неуспешной попытки флаг `delivered = bool(out.get(\"text\") or out.get(\"tool_calls\"))` не учитывает `out[\"reasoning\"]`; при `not delivered` и состояниях `agy_error`, `pump_error`, `done` выполняется невидимый повтор (до 2 попыток, пауза `2*attempt` с), а горячая сессия при `agy_error` без выдачи переходит в холодный повтор с полной историей",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-09"
    },
    {
      "id": "EVD-010",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-10; bridges/agy-bridge/server.py:999-1006, 1015-1024",
      "claim": "`_execute` возвращает в `out` поле `reasoning` (склейка отданных клиенту кусков мышления), а `tool_calls` всегда пустой список, то есть `delivered` на практике зависит только от текста",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-10"
    },
    {
      "id": "EVD-011",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-11; bridges/agy-bridge/server.py:1438-1501",
      "claim": "`_serve_sse` шлёт первый чанк `{\"role\":\"assistant\",\"content\":\"\"}`, мышление отдаёт чанками `delta.reasoning_content`, а при ошибке после начала потока пишет кадр `data: {\"error\": ...}` и затем `data: [DONE]`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-11"
    },
    {
      "id": "EVD-012",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-12; bridges/agy-bridge/server.py:1368-1385",
      "claim": "Ключ горячей сессии `sess_key = (model_id, cwd, effort)` не содержит признака наличия `tools`, числа сообщений или ключа кэша промпта; `_session_claim` вызывается для любого запроса без явного `conversation_id`, а `tools_count` вычисляется отдельно и в ключ не входит",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-12"
    },
    {
      "id": "EVD-013",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-13; bridges/agy-bridge/server.py:116-130, 477-516",
      "claim": "`_session_commit` перезаписывает запись хранилища, если `cid` завершившегося хода отличается от сохранённого; `_session_claim` пропускает занятую (`_in_flight_cids`) сессию и тогда запрос стартует холодным; TTL простоя 45 мин, жизни 24 ч, потолок 30 ходов",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-13"
    },
    {
      "id": "EVD-014",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-14; grep -rn _LAST_CONV bridges/agy-bridge/ core/ (0 строк); bridges/agy-bridge/server.py:128-130",
      "claim": "Глобальной переменной `_LAST_CONV` в мосте нет (0 совпадений grep по `bridges/agy-bridge/` и `core/`); роль «последнего разговора» выполняет словарь `_session_store` с ключом `sess_key`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-14"
    },
    {
      "id": "EVD-015",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-15; bridges/agy-bridge/server.py:88-95, 336, 1029-1056; core/watchdog.py:27-30",
      "claim": "Таймауты моста: `KEEPALIVE_S=15`, `FIRST_TOKEN_TIMEOUT_S=120` (порог по первому любому JSON-событию stdout), `TIMEOUT_S=1800`, `QUEUE_TIMEOUT_S=900`, `MAX_CONCURRENT=4` по умолчанию; `IDLE_TIMEOUT_S` берётся из `core.watchdog` (300 с), проверка сторожа не чаще `WATCHDOG_INTERVAL_S=5` с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-15"
    },
    {
      "id": "EVD-016",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-16; bridges/agy-bridge/server.py:1479-1480",
      "claim": "Keepalive моста — SSE-комментарий `: keepalive`, он не несёт ни `content`, ни `reasoning_content` и в UI ничего не показывает",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-16"
    },
    {
      "id": "EVD-017",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-17; bridges/agy-bridge/server.py:341, 1057-1058",
      "claim": "Событие `reasoning` входит в `_ACTIVITY_KINDS` и сбрасывает таймер неактивности сторожа через `controller.on_activity`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-17"
    },
    {
      "id": "EVD-018",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-18; bridges/agy-bridge/server.py:807-813, 839-843; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl строки 4-11",
      "claim": "Docstring `_pump` описывает `text_delta` как накопительный снимок, а живой поток 1.4.9 присылает непересекающиеся приращения (например, `Прочитан общий канон ~/Мо`, затем `й диск/`); корректный вывод сейчас обеспечивает ветка «не префикс → весь текст» из `_reasoning_suffix`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-18"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-19; bridges/agy-bridge/server.py:1413-1436",
      "claim": "Нестриминговый путь `_serve_json` кладёт склеенное мышление в `message.reasoning_content`, то есть гонка финального дренирования затрагивает и ответ без `stream`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-19"
    },
    {
      "id": "EVD-020",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-20; bridges/agy-bridge/server.py:1088-1101",
      "claim": "На `done` при пустом потоке текста `_execute` подставляет `final_text` из `result.response`, после чего ход считается `done`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-20"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-21; ls bridges/agy-bridge/ (fleet.json, server.py, start.sh); grep -n \"def test_\" tests/test_agy_bridge_resilience.py",
      "claim": "Файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет: каталога `tests` у моста нет, тесты моста лежат в корневом `tests/test_agy_bridge_resilience.py` (709 строк, классы IdleDetection, ExecuteLoop, KillSwitch, ErrorContract, KillGroup, FetchViaPlaywrightHotfix)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-21"
    },
    {
      "id": "EVD-022",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-22; grep -n по словам TranscriptTail, reasoning, sess_key, delivered в tests/test_agy_bridge_resilience.py (строки 248, 354, 363)",
      "claim": "Тестов на `_TranscriptTail`, финальное дренирование, флаг `delivered` и `sess_key` нет: слово `reasoning` встречается только в тестах вида активности сторожа",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-22"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-23; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-unittest.log, baseline-pytest.log",
      "claim": "Базовая линия моста зелёная: `python3 -m unittest tests.test_agy_bridge_resilience` дал `Ran 22 tests in 2.082s OK` (exit 0); `python3 -m pytest` недоступен (в python3.14 нет модуля pytest)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-23"
    },
    {
      "id": "EVD-024",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-24; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full.log",
      "claim": "Полный прогон `uvx pytest -q -p no:cacheprovider tests/` без `PYTHONPATH` падает на сборке `tests/test_adaptive_idle_watchdog.py` с `ModuleNotFoundError: No module named 'core'` (exit 2); полный набор требует `PYTHONPATH=.`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-24"
    },
    {
      "id": "EVD-025",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-25; ~/.local/bin/agy --version; ls -la ~/.local/bin/agy*; ls ~/.gemini/antigravity-cli/",
      "claim": "Установлен `agy` 1.4.9: `~/.local/bin/agy --version` печатает `1.4.9`, бинарь `~/.local/bin/agy.real` 193540240 байт от 2026-10-28 11:50; каталога `~/.gemini/antigravity-cli/releases/` нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-25"
    },
    {
      "id": "EVD-026",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-26; bridges/agy-bridge/fleet.json (technical_ref, models[0])",
      "claim": "`fleet.json` устарел относительно рантайма: `technical_ref.agy_version` равен `1.3.1`; `gemini-4-argon` имеет efforts low/medium/high и `default_effort=high`, `default_model` каталога `gemini-3.8-flash`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-26"
    },
    {
      "id": "EVD-027",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-27; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl",
      "claim": "Живой поток `stream-json` 1.4.9 (cid `c6910a34`): `init`, `step_update` user_input DONE, два шага `unknown` DONE, семь `agent_response` ACTIVE с `text_delta`, финальный DONE с `usage.thinking_tokens=1460`, затем `result` (`duration_seconds=19.8653`); ни одно событие не несёт текста мышления",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-27"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-28; KB tools/dsh-bridges-cli-agent-bridge.md строки 361-365 (дизассемблирование agy.real 1.4.9)",
      "claim": "В 1.4.9 Go-структура `steps.StepUpdatePayload` пакета printmode сериализует `text_delta` и `thinking_tokens`, но не поле `thinking` или `thinking_delta`, хотя в protobuf `StepUpdate` поле `thinking_delta` (field 10) объявлено",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-28"
    },
    {
      "id": "EVD-029",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-29; KB tools/dsh-bridges-cli-agent-bridge.md строки 369-373; /tmp/cel-runs/agy-streaming-research-20261029/checks.tsv строка step-3",
      "claim": "Живой замер `gemini-4-argon --effort high` (cid `82188e72`): stdout молчит с 4.81 с по 23.52 с; `transcript_full.jsonl` заморожен на 66213 байтах после `step_index=2`; запись `step_index=3` (`PLANNER_RESPONSE` с `thinking`) появилась в 23.87 с, на 90 мс позже события `result` (23.78 с); `Handler._execute` вышел по `done` в 23.83 с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-29"
    },
    {
      "id": "EVD-030",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-30; KB tools/dsh-bridges-cli-agent-bridge.md строки 374-376; checks.tsv step-3-live-stream-probe",
      "claim": "В том же замере строка `idx=3, step_type=15, status=8` файла `~/.gemini/antigravity-cli/conversations/<cid>.db` обновлялась во время мышления: 10.66 с (523 B), 12.19 с (810 B), 14.97 с (1088 B), 20.06 с (1419 B), 23.36 с (2156 B), то есть интервалы 1.5-5.1 с",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-30"
    },
    {
      "id": "EVD-031",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-31; sqlite3 \"file:<db>?mode=ro&immutable=1\" \".tables\" \".schema steps\" (отчёт explorer Zone D); PRAGMA table_info(steps) в poc_pb.py",
      "claim": "Схема таблицы `steps`: `idx integer PRIMARY KEY, step_type integer, status integer, has_subtrajectory, metadata blob, error_details blob, permissions blob, task_details blob, render_info blob, step_payload blob, step_format integer`, индексы по `status` и `step_type`; в БД также таблицы `battle_mode_infos, executor_metadata, gen_metadata, parent_references, trajectory_meta, trajectory_metadata_blob`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-31"
    },
    {
      "id": "EVD-032",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-32; python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/poc_pb.py 82188e72-6eca-4f23-a0b3-2257ec43bd60",
      "claim": "PoC-парсер wire-формата на stdlib (varint, wire types 0/1/2/5) извлёк из `82188e72` строки: idx 0 `step_type=14` (2020 B), idx 1 и 2 `step_type=90` (40132 B и 25094 B), idx 3 `step_type=15 status=3` (10068 B) с полем 20, в котором подполе 1 = 196 символов, подполе 3 = 1875 символов, подполе 6 встречается 1 раз, подполе 8 = 196 символов",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-32"
    },
    {
      "id": "EVD-033",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-33; python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/cmp2.py <cid>",
      "claim": "Финальный текст мышления из SQLite (`step_type=15`, поле 20.3) побайтово равен полю `thinking` записи `PLANNER_RESPONSE` транскрипта при `idx == step_index` на трёх разговорах: `82188e72` (1875 символов, есть не-ASCII), `fa92a264` (1080, есть не-ASCII), `57172100` (5561, только ASCII); в `4a1067cc` шагов `step_type=15` с мышлением нет ни в БД, ни в транскрипте",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-33"
    },
    {
      "id": "EVD-034",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-34; xxd -s 18 -l 2 <db>; file <db>; ls -la ~/.gemini/antigravity-cli/conversations (отчёт explorer Zone D)",
      "claim": "Файлы `conversations/*.db` в режиме WAL (байты 18-19 заголовка `0x02 0x02`, `last written using SQLite version 3053002, page size 32768`); у закрытых разговоров файлов `-wal` и `-shm` нет, в каталоге найдено только 4 таких файла от 2026-10-28",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-34"
    },
    {
      "id": "EVD-035",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-35; poc_pb.py вывод `sqlite 3.53.4`; отчёт explorer Zone D вопрос 5",
      "claim": "Python `sqlite3.connect(\"file:<db>?mode=ro\", uri=True)` (SQLite 3.53.4) читает закрытую БД разговора без ошибок, а CLI `sqlite3 -readonly <путь>` на той же БД вернул `unable to open database file (14)`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-35"
    },
    {
      "id": "EVD-036",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-36; ls ~/.gemini/antigravity-cli/brain/82188e72-.../.system_generated/logs/chunks/*; ls ~/.gemini/antigravity/brain/82188e72-.../.system_generated/logs/ (No such file)",
      "claim": "Рядом с транскриптом CLI держит копии `chunks/transcript/00000000.jsonl` и `chunks/transcript_full/00000000.jsonl`; разговорный каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, а не `~/.gemini/antigravity/brain/<cid>/` (в последнем для `82188e72` каталога логов нет)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-36"
    },
    {
      "id": "EVD-037",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-37; KB tools/dsh-bridges-cli-agent-bridge.md строка 359 (`~/.gemini/antigravity/builtin/skills/antigravity_guide/references/sdk.md`)",
      "claim": "Python SDK `google-antigravity` возвращает мысли только постфактум (`response.thoughts` после блокирующего `send()`), стримингового генератора мыслей нет",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-37"
    },
    {
      "id": "EVD-038",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-38; plutil -p ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist; readlink; shasum -a 256 (отчёт explorer Zone D)",
      "claim": "LaunchAgent `com.user.dsh-agy-bridge` запускает `/bin/bash ~/.dsh/bridges/agy-bridge/start.sh`, логи в `~/.dsh/bridges/agy-bridge/logs/bridge.err` и `bridge.out`, env `AGY_BRIDGE_MAX_CONCURRENT=8`, `AGY_BRIDGE_PORT=9887`, `AGY_BRIDGE_QUEUE_TIMEOUT=1800`; `~/.dsh/bridges/agy-bridge` — обычный каталог, не симлинк, и его `server.py` побайтово равен репозиторному (sha256 `c4e52312…e747`)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-38"
    },
    {
      "id": "EVD-039",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-39; curl -s -m 3 http://127.0.0.1:9887/health",
      "claim": "`/health` моста: `ok=true`, `transport=agy-stream-json`, `model=gemini-3.8-flash`, `active=0`, `max_concurrent=8`, `hot_sessions=2`, `uptime_s=26273`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-39"
    },
    {
      "id": "EVD-040",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-40; grep -cF по ~/.dsh/bridges/agy-bridge/logs/bridge.err",
      "claim": "`bridge.err` (2891 строк, без дат): `reasoning-emit` 888, `tail-emit` 893, `tail-timeout` 0, `tail-rewrite` 0, `exec model=` 301, `done model=` 266, `transient failure` 29, `hot session failed` 4; пять строк `tail-emit` не имеют парной `reasoning-emit`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-40"
    },
    {
      "id": "EVD-041",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-41; grep/awk по bridge.err",
      "claim": "Из 301 запуска 156 с `tools=0` и 145 с `tools>0`; `resume=1` у 45, `resume=0` у 256",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-41"
    },
    {
      "id": "EVD-042",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-42; awk-группировка exec-строк bridge.err, строки 969-970, 1255-1256, 2792-2793",
      "claim": "В логе 21 пара запусков одной модели в одну секунду, где один `tools>0` с большим промптом и `effort_source=request`, а второй `tools=0` с промптом 492-721 байт и `effort_source=default` на соседнем клиентском порту (например, 01:09:38 `gemini-3.8-flash` 78282 B против 674 B; 23:20:29 и 19:09:44 `gemini-4-argon`)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-42"
    },
    {
      "id": "EVD-043",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-43; awk по init/reasoning-emit/done в bridge.err; строки 965, 968, 986, 1337, 1804, 1875",
      "claim": "Среди ходов `gemini-4-argon` с `state=done`: без инструментов (`tool_events=0`) 28, из них 6 без единой строки `reasoning-emit` для своего cid; с инструментами 23, без мышления 0",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-43"
    },
    {
      "id": "EVD-044",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-44; bridge.err строки 2777-2782",
      "claim": "Одношаговый ход `926e03fa` (`gemini-4-argon`, wall 46.6 с): `tail-emit step=3 len=5342` и `reasoning-emit n=1` записаны в ту же секунду 01:08:22, что и `done`, то есть всё мышление пришло клиенту одним чанком в конце хода; так же ход `496587c9` (len 3935, wall 55.2 с)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-44"
    },
    {
      "id": "EVD-045",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-45; bridge.err строки 2735, 2844, 2846, 2891 и подсчёт reasoning-emit",
      "claim": "Многошаговый ход `9ccb5526` с инструментами шёл 856.5 с и 1068.0 с (два хода, 52 и 46 событий инструментов) и отдал 37 и 22 куска мышления через транскрипт",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-45"
    },
    {
      "id": "EVD-046",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-46; bridge.err строки 2768, 2787, 2800 и done-строка 01:09:56",
      "claim": "2026-10-29 в 01:07-01:09 аккаунт agy получал `Individual quota reached ... Resets in 54h2xm` на `gemini-4-argon` и `gemini-3.8-flash`, а мост выполнял `transient failure ... retry 1` и `hot session failed ... cold fallback`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-46"
    },
    {
      "id": "EVD-047",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-47; KB tools/dsh-bridges-cli-agent-bridge.md строки 377-380; bridge.err строки 2844, 2891",
      "claim": "База знаний фиксирует сценарий RC-3 на `cid=9ccb5526` (мышление Шага 1 затёрто кадром ошибки после сбоя квоты), а в `bridge.err` оба хода `9ccb5526` завершились `state=done rc=0`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-47"
    },
    {
      "id": "EVD-048",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-48; /tmp/cel-runs/agy-streaming-research-20261029/close.md",
      "claim": "Ресерч 2026-10-29 закрыт со статусом ГОТОВО, источник реалтайма зафиксирован как SQLite `conversations/<cid>.db`, таблица `steps`, protobuf field 20.3",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-48"
    },
    {
      "id": "EVD-049",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-49; git log --oneline -5 -- bridges/agy-bridge/server.py; git log -1; git status --porcelain",
      "claim": "Последняя правка `bridges/agy-bridge/server.py` в истории — коммит `b9a9648` (resilience watchdog, process group kill, EYE-33873); ветка `feature/agy-realtime-reasoning` на HEAD `e00da06` (2026-10-28 03:32 MSK), рабочее дерево до анализа содержало только `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-49"
    },
    {
      "id": "EVD-050",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-50; bridges/agy-bridge/server.py:104, 594, 807, 1154, 1377",
      "claim": "Номера строк брифа расходятся с кодом: `_TranscriptTail` в 594-709 (в брифе 553-702), `Run._pump` в 807-868 (в брифе 920-935), `TRANSCRIPT_GRACE_S` в строке 104 (в брифе 626), период опроса 0.05 с (в брифе 0.15 с); строки `delivered` (1154) и `sess_key` (1377) совпадают",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-50"
    },
    {
      "id": "EVD-051",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-51; ps -o pid,rss,etime,command -p 45973; grep -n exec ~/.dsh/bridges/agy-bridge/start.sh (строка 23); lsof -p 45973 (36 строк); /usr/bin/python3 -c sqlite3.sqlite_version",
      "claim": "Боевой процесс моста (PID 45973, uptime 07:24:29) запущен `start.sh` строкой `exec /usr/bin/python3 server.py`, то есть системным Python 3.9.6 из CommandLineTools со встроенной SQLite 3.54.0; RSS 20512 KiB, открытых дескрипторов 36",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-51"
    },
    {
      "id": "EVD-052",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-52; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/ro_probe.py на dbcopy/t.db обоими интерпретаторами",
      "claim": "На копии закрытой WAL-БД разговора (без файлов `-wal` и `-shm`) системный Python 3.9.6 открывает её с `mode=ro` с ошибкой `unable to open database file`, с `mode=ro&immutable=1` читает 4 строки, с `mode=ro&nolock=1` падает; Homebrew Python 3.14.7 (SQLite 3.53.4) читает и с `mode=ro`, и с `immutable=1`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-52"
    },
    {
      "id": "EVD-053",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-53; ro_probe.py, запущенный при живом rw-соединении к dbcopy/t.db",
      "claim": "Пока на ту же копию открыто читающе-пишущее соединение другого процесса (файл `-shm` существует), системный Python 3.9.6 открывает её с `mode=ro` и читает 4 строки",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-53"
    },
    {
      "id": "EVD-054",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-54; launchctl limit maxfiles; ulimit -n; sysctl net.inet.ip.portrange.first net.inet.ip.portrange.last net.inet.tcp.msl",
      "claim": "Лимиты хоста: `launchctl limit maxfiles` 65536 (soft) и unlimited (hard), `ulimit -n` в оболочке 1048576, диапазон эфемерных портов 49152-65535 (16384 порта), `net.inet.tcp.msl` 15000 мс (TIME_WAIT 30 с)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-54"
    },
    {
      "id": "EVD-055",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-55; grep -F \" exec model=\" bridge.err, группировка по времени uniq -c",
      "claim": "Пиковая частота запусков по `bridge.err` — 6 строк `exec` в одну секунду (15:03:40), следующая — 4 (15:27:38)",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-55"
    },
    {
      "id": "EVD-056",
      "kind": "document",
      "ref": "analysis/agy-realtime-reasoning/evidence-ledger.md#F-56; /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full2.log",
      "claim": "Полный набор `PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/` на HEAD `e00da06`: 3 failed, 896 passed, 8103 subtests passed за 363.6 с; красные тесты вне `agy-bridge`: `test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess`, `test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k`, `test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child`",
      "collected_at": "2026-10-29",
      "analyst_fact_id": "F-56"
    },
    {
      "id": "EVD-057",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:477-516 (_session_claim/_invalidate/_commit), 594-709 (_TranscriptTail), 807-868 (Run._pump), 870-893 (Run.close, _reasoning_suffix), 981-1101 (Handler._execute), 1103-1187 (_run_once), 1368-1400 (do_POST sess_key)",
      "claim": "Архитектор выборочно перепроверил символы ledger на HEAD e00da06: F-02..F-13 подтверждены (sleep 0.05 + done без join хвоста, grace 0.4 после done_event, delivered без reasoning, sess_key=(model_id,cwd,effort), _session_claim для любого запроса без conversation_id)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-058",
      "kind": "command",
      "ref": "cd ~/tmp/cli-agent-bridge/agy-realtime-reasoning && PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -B -m unittest tests.test_agy_bridge_resilience",
      "claim": "Baseline моста на боевом интерпретаторе Python 3.9.6 (SQLite 3.54.0): Ran 22 tests in 2.076s OK, rc=0",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-059",
      "kind": "command",
      "ref": "uvx ruff check --no-cache bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "claim": "ruff 0.17.3 с ruff.toml (E4/E7/E9/F): All checks passed, rc=0 — порог 0 ошибок замораживается как есть",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-060",
      "kind": "command",
      "ref": "uvx basedpyright --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "claim": "basedpyright 1.40.2 на baseline: 12 errors, 868 warnings (server.py 611, tests 257). Ошибки: server.py reportArgumentType×5 (строки 259, 282, 832, 1371, 1385), reportCallIssue×1 (259), reportIncompatibleMethodOverride×3 (928, 1529, 1544); tests reportUninitializedInstanceVariable×2 (165), reportPossiblyUnboundVariable×1 (557). Порог Teamlead basedpyright_errors=0 на baseline недостижим без правки чужого кода — замораживается baseline-aware гейт «не больше baseline по каждой паре (файл, правило)»",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-061",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/teamlead/verification-surface.json",
      "claim": "Замороженная поверхность Teamlead: base_sha e00da06, baseline 22 passed, новые тесты разрешены только в tests/test_agy_bridge_resilience.py, existing_oracle_assertions_mutable=false, хеши 39 oracle-файлов tests/, конфиги ruff.toml/fleet.json/start.sh; уровни L1 (ruff+basedpyright+pytest+unittest на /usr/bin/python3), L2 clean-room, L3 :9887 после ACCEPT и merge",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-062",
      "kind": "code",
      "ref": "bridges/agy-bridge/fleet.json:29-31 admission; bridges/agy-bridge/server.py:1511-1548 Server._conn_sem",
      "claim": "Ingress ограничен max_http_connections=32 (BoundedSemaphore, переполнение → raw 503), тело — max_inflight_body_bytes=67108864",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-063",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:125, 969-979 (_slots, _acquire_slot), 1126-1172 (retry loop)",
      "claim": "Слоты исполнения — BoundedSemaphore(MAX_CONCURRENT); ожидание слота до QUEUE_TIMEOUT_S опросом по 1 с (код 900 с, деплой 1800 с по F-38); повтор хода — до 2 попыток с фиксированной паузой time.sleep(2*attempt), горячий срыв → холодный повтор без паузы; процессного retry budget нет",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-064",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:1531 DYNAMIC_CONFIG_PATH, 1831-1858 _read_dynamic_config_enabled, 1913-1933 env override",
      "claim": "In-repo прецедент (влит в dev коммитом a269342): runtime-фичефлаг в dynamic_config.json рядом с server.py, stat-кэш (mtime_ns,size), кодовый default=false, env-override; принят Советом zen-realtime-reasoning как stdlib-аналог GigaRC без рестарта",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-065",
      "kind": "code",
      "ref": "core/context_resilience.py:254-300 (флаги GigaRC: Flags, FlagSource)",
      "claim": "Репозиторный аналог GigaRC — локальный атомарный JSON-снимок флагов, все флаги по умолчанию выключены; подтверждает канон «новое поведение за флагом, default=false»",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-066",
      "kind": "command",
      "ref": "python3 -I ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/validate_role_plan.py plans/architect-01.before.json --role architect --phase before",
      "claim": "Установленный validate_role_plan.py не принимает --role (argparse: unrecognized arguments, rc=2); тот же файл без --role: PASS architect role plan valid for before. Роль проверяется внутри JSON",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-067",
      "kind": "command",
      "ref": "python3 -I ~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/scripts/worktree_fingerprint.py --root <repo> --exclude .ai-team/runs/analyst-teamlead-agy-reasoning-20261029 --compare fingerprints/architect-before.json",
      "claim": "Продуктовое дерево не изменено ролью: WORKTREE_UNCHANGED aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb files=12839 (промежуточная и финальная сверка)",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-068",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:1107-1125, 1179-1187",
      "claim": "Строка O-EXIT `done model=...` пишется после try/finally; ранние выходы _run_once (no slot, launcher_unavailable) возвращаются без строки done — пробел телеметрии baseline",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-069",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:47 (from __future__ import annotations), 1453 (dict | None)",
      "claim": "Модуль совместим с 3.9 только при сохранении отложенных аннотаций; новый код не может использовать runtime-синтаксис 3.10+ (match, X | Y вне аннотаций, zip(strict=))",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-070",
      "kind": "code",
      "ref": "bridges/agy-bridge/server.py:47-76 (imports)",
      "claim": "Корни импортов baseline: __future__, hashlib, json, os, queue, re, select, shutil, signal, socket, subprocess, sys, threading, time, uuid, http, pathlib, typing, core; дизайн добавляет только stdlib sqlite3 и random",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-071",
      "kind": "command",
      "ref": "git check-ignore -v bridges/agy-bridge/dynamic_config.json; grep -n dynamic_config .gitignore",
      "claim": ".gitignore игнорирует только __pycache__/; bridges/agy-bridge/dynamic_config.json не игнорируется — его отсутствие в git контролирует VER-008",
      "collected_at": "2026-10-29"
    },
    {
      "id": "EVD-072",
      "kind": "command",
      "ref": "dry-run замороженных команд VER-004/006/007/008/009 на HEAD e00da06",
      "claim": "Команды исполнимы: VER-004 errors 12 over_baseline {} rc=0; VER-006 OK rc=0; VER-007 MISSING 47 ids rc=1; VER-008 rc=1 (diff пуст); VER-009 FAIL no sqlite3.connect rc=1 — красные до реализации ожидаемо, зелёные обязаны стать после Coder",
      "collected_at": "2026-10-29"
    }
  ],
  "risk_triggers": [
    "trust-boundary"
  ],
  "assumptions": [
    {
      "id": "ASM-001",
      "class": "continuable",
      "source_open_ids": "OPEN-01",
      "statement": "Подполе 20.3 растёт префиксно между снимками status=8. Дизайн не зависит от допущения для корректности: правило append-only не повторяет отданный текст, расхождение (divergence) не эмитится, логируется и размыкает SQLite breaker",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-030",
        "EVD-033",
        "EVD-004"
      ]
    },
    {
      "id": "ASM-002",
      "class": "continuable",
      "source_open_ids": "OPEN-02, OPEN-12",
      "statement": "Во время хода agy держит БД разговора открытой (есть -shm), поэтому /usr/bin/python3 3.9.6 читает её с mode=ro; immutable=1 допустим только когда писателя нет (до spawn для resumed-водяного знака и после выхода процесса в drain). Ошибка открытия = «изменений нет»",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-052",
        "EVD-053",
        "EVD-030",
        "EVD-035"
      ]
    },
    {
      "id": "ASM-003",
      "class": "continuable",
      "source_open_ids": "OPEN-03",
      "statement": "Номера step_type=15, status=8, поле 20, подполе 3 привязаны к agy 1.4.9; несовпадение схемы распознаётся (нет таблицы/колонок, divergence) и отключает источник breaker'ом, мышление идёт из транскрипта; после автоапдейта agy L3 S1 повторяется",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-025",
        "EVD-028",
        "EVD-031"
      ]
    },
    {
      "id": "ASM-004",
      "class": "continuable",
      "source_open_ids": "OPEN-04",
      "statement": "6 одношаговых ходов argon без мышления объясняются гонкой drain и/или смещением хвоста при продолжении; AD-001 (водяной знак до spawn) и AD-002 закрывают обе причины",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-043",
        "EVD-006",
        "EVD-002"
      ]
    },
    {
      "id": "ASM-005",
      "class": "continuable",
      "source_open_ids": "OPEN-05",
      "statement": "cwd фонового запроса DSH совпадает с основным; изоляция AD-004 не зависит от cwd",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-042",
        "EVD-012",
        "EVD-013"
      ]
    },
    {
      "id": "ASM-006",
      "class": "continuable",
      "source_open_ids": "OPEN-06",
      "statement": "Сбой после отданного reasoning завершается кадром data:{error} + [DONE] (неизменный as-is контракт ошибок после старта потока), без невидимого повтора; альтернатива stop+частичный ответ ждёт решения владельца (Q-002)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-011",
        "EVD-047"
      ]
    },
    {
      "id": "ASM-007",
      "class": "continuable",
      "source_open_ids": "OPEN-07",
      "statement": "L3 выполняется на аккаунте agy с квотой (штатное переключение) или после сброса квоты; без L3 сдача не засчитывается",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-046"
      ]
    },
    {
      "id": "ASM-008",
      "class": "continuable",
      "source_open_ids": "OPEN-08",
      "statement": "Цели отзывчивости: первая дельта ≤5 с от начала генерации шага, интервал ≤6 с, добавка drain ≤1.0 с; при SQLITE_POLL_S=0.5 и интервале записи ≤5.1 с дизайн даёт ≤5.6 с между дельтами",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-030"
      ]
    },
    {
      "id": "ASM-009",
      "class": "continuable",
      "source_open_ids": "OPEN-09, OPEN-10, OPEN-11, OPEN-16",
      "statement": "Вне объёма MR: fleet.json technical_ref (1.3.1) и комментарии про 1.3.1 (fleet.json защищён хешем Teamlead), трактовка text_delta в _pump (_reasoning_suffix для текста не меняется), agentapi не исследуется, 3 красных теста полного набора вне agy-bridge — набор красных до/после сравнивается",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-026",
        "EVD-018",
        "EVD-056",
        "EVD-061"
      ]
    },
    {
      "id": "ASM-010",
      "class": "continuable",
      "source_open_ids": "brief architect-01 (пример AGY_SQLITE_REASONING=1)",
      "statement": "Переключатель SQLite-источника: кодовый default=false + runtime dynamic_config.json (SQLITE_REASONING_ENABLED) + env-override AGY_BRIDGE_SQLITE_REASONING (0 — kill-switch, 1 — принудительно вкл.); включение на :9887 — шаг L3. Отклонение от примера брифа (default=1) по канону «фича за флагом default=false, kill-switch без рестарта» и in-repo прецеденту zen; владелец может выбрать default=1 (Q-004)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-064",
        "EVD-065",
        "EVD-038"
      ]
    },
    {
      "id": "ASM-011",
      "class": "continuable",
      "source_open_ids": "baseline debt",
      "statement": "Унаследованные отклонения baseline (ожидание слота до 900/1800 с, ожидающие слота до 24 > 2M, 12 ошибок basedpyright, неограниченная Run.q) этим MR не ухудшаются и закрываются отдельной задачей по решению владельца (Q-005)",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-060",
        "EVD-062",
        "EVD-063"
      ]
    }
  ],
  "drivers": [
    "RC-1: нет live-источника мышления — пустой UI 15-45 с (F-27..F-30, F-44)",
    "RC-2: гонка финального drain теряет мышление последнего шага (F-06..F-08, F-29, F-43)",
    "RC-3: отданное reasoning не считается выдачей → невидимый повтор/дубли (F-09..F-11, F-46, F-47)",
    "RC-4: sess_key без признака tools → фоновый запрос уводит conversation_id диалога (F-12..F-14, F-41, F-42)",
    "Ограничения: боевой /usr/bin/python3 3.9.6 + stdlib, неизменный HTTP/SSE контракт, только чтение файлов agy, fail-open (F-51..F-53, REQ-002/004/010)"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-012",
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "AD-005",
        "AD-006"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; 0 failed; passed ≥ 22 + все новые тесты (TC/AO из VER-007); 22 существующих теста зелёные без правок",
      "environment": "Чистый clone/worktree кандидата, cwd=repo_root, uvx pytest; без сети, без ~/.gemini и ~/.dsh владельца: фикстурные AGY_BRIDGE_BRAIN/AGY_BRIDGE_CONVERSATIONS/фейковый AGY_LAUNCHER во временном каталоге раннера",
      "owner": "Verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "AD-001",
        "RISK-002",
        "RISK-012"
      ],
      "kind": "command",
      "command": "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /usr/bin/python3 -m unittest tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; вывод «OK»; тот же набор тестов зелёный на боевом интерпретаторе Python 3.9.6 (SQLite 3.54.x), включая парсер и SQLite fail-open на закрытой WAL-БД",
      "environment": "macOS /usr/bin/python3 3.9.6 (CommandLineTools), cwd=repo_root, PYTHONDONTWRITEBYTECODE=1; зелёный прогон только на Python 3.14 не засчитывается",
      "owner": "Verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "REQ-010"
      ],
      "kind": "command",
      "command": "uvx ruff check bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py",
      "expected": "exit 0; «All checks passed!» (baseline EVD-059 зелёный)",
      "environment": "cwd=repo_root, uvx ruff (≥0.17.3) с ruff.toml репозитория",
      "owner": "Verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "REQ-010",
        "RISK-011"
      ],
      "kind": "command",
      "command": "uvx basedpyright --outputjson bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py | python3 -I -c \"import json,sys,collections; d=json.load(sys.stdin); c=collections.Counter((x['file'].rsplit('/',1)[-1],x.get('rule')) for x in d['generalDiagnostics'] if x['severity']=='error'); base={('server.py','reportArgumentType'):5,('server.py','reportCallIssue'):1,('server.py','reportIncompatibleMethodOverride'):3,('test_agy_bridge_resilience.py','reportUninitializedInstanceVariable'):2,('test_agy_bridge_resilience.py','reportPossiblyUnboundVariable'):1}; over={k:v for k,v in c.items() if v>base.get(k,0)}; print('errors',sum(c.values()),'over_baseline',over); sys.exit(1 if over else 0)\"",
      "expected": "exit 0; over_baseline {} — число ошибок по каждой паре (файл, правило) не больше baseline EVD-060 (всего ≤12); новые ошибки запрещены; предупреждения не гейтятся",
      "environment": "cwd=repo_root, uvx basedpyright 1.40.x, python3 -I для подсчёта",
      "owner": "Verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": [
        "REQ-010",
        "QA-006"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider -rf tests/",
      "expected": "Строки FAILED ровно три baseline-теста F-56: test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess, test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k, test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child; новых красных нет",
      "environment": "Чистый clone кандидата, cwd=repo_root, PYTHONPATH=., uvx pytest; ~6 мин, запускать в фоне",
      "owner": "Teamlead"
    },
    {
      "id": "VER-006",
      "requirement_ids": [
        "REQ-010",
        "QA-006"
      ],
      "kind": "command",
      "command": "test \"$(git diff --unified=0 e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/test_agy_bridge_resilience.py | grep -cE '^-[^-]')\" = 0 && test -z \"$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- tests/ core/ | grep -vx 'tests/test_agy_bridge_resilience.py')\" && echo OK",
      "expected": "exit 0 и «OK»: в tests/test_agy_bridge_resilience.py нет удалённых/изменённых строк относительно e00da06 (только добавления), другие файлы tests/ и core/ не изменены",
      "environment": "git clone кандидата с доступным base e00da0621fc95f7c63cd1565f4a5d1fd490c8d66, HEAD = коммит кандидата",
      "owner": "Teamlead"
    },
    {
      "id": "VER-007",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-011",
        "REQ-012",
        "AD-005",
        "THREAT-001",
        "THREAT-002",
        "THREAT-003",
        "THREAT-004",
        "THREAT-005"
      ],
      "kind": "command",
      "command": "python3 -I - <<'PY'\nimport re,sys,pathlib\ns=pathlib.Path('tests/test_agy_bridge_resilience.py').read_text(encoding='utf-8')\ngot=set()\nfor n in re.findall(r'def (test_\\w+)\\(',s):\n    got|=set(re.findall(r'(tc\\d{2}|ao\\d{2})',n))\nneed={'tc%02d'%i for i in list(range(1,13))+[20,21,23,24,30,31,32,33,40,41,42,43,44,50,51,60,61,62,63,70,71,72,80,81,82,91,92]}|{'ao%02d'%i for i in range(1,9)}\nmiss=sorted(need-got)\nprint('MISSING '+' '.join(miss) if miss else 'OK %d ids'%len(need)); sys.exit(1 if miss else 0)\nPY",
      "expected": "exit 0; «OK 47 ids»: имена тестовых функций покрывают TC-01..12, 20, 21, 23, 24, 30..33, 40..44, 50, 51, 60..63, 70..72, 80..82, 91, 92 и архитектурные оракулы AO-01..AO-08 (в имени test_..._tcNN / _aoNN, допускается несколько id в одном имени)",
      "environment": "cwd=repo_root, python3 -I",
      "owner": "Teamlead"
    },
    {
      "id": "VER-008",
      "requirement_ids": [
        "REQ-010",
        "RISK-011",
        "AD-006"
      ],
      "kind": "command",
      "command": "test \"$(git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 HEAD -- . ':(exclude).ai-team' ':(exclude)analysis' | sort | tr '\\n' ' ')\" = \"bridges/agy-bridge/server.py tests/test_agy_bridge_resilience.py \" && test -z \"$(git ls-files bridges/agy-bridge/dynamic_config.json)\" && echo OK",
      "expected": "exit 0 и «OK»: изменены ровно bridges/agy-bridge/server.py и tests/test_agy_bridge_resilience.py (вне .ai-team и analysis); bridges/agy-bridge/dynamic_config.json не в git; нет правок fleet.json/start.sh/ruff.toml/core/зависимостей",
      "environment": "git clone кандидата, HEAD = коммит кандидата",
      "owner": "Teamlead"
    },
    {
      "id": "VER-009",
      "requirement_ids": [
        "REQ-002",
        "REQ-011",
        "AD-001",
        "AD-006",
        "THREAT-003",
        "BND-003"
      ],
      "kind": "command",
      "command": "python3 -I - <<'PY'\nimport ast,sys,pathlib\nsrc=pathlib.Path('bridges/agy-bridge/server.py').read_text(encoding='utf-8')\nt=ast.parse(src)\nallowed={'__future__','hashlib','json','os','queue','re','select','shutil','signal','socket','subprocess','sys','threading','time','uuid','http','pathlib','typing','core','sqlite3','random'}\nroots=set()\nfor n in ast.walk(t):\n    if isinstance(n,ast.Import):\n        roots|={a.name.split('.')[0] for a in n.names}\n    elif isinstance(n,ast.ImportFrom) and n.level==0:\n        roots.add((n.module or '').split('.')[0])\ncalls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='connect' and isinstance(n.func.value,ast.Name) and n.func.value.id=='sqlite3']\nnouri=[c.lineno for c in calls if not any(k.arg=='uri' and isinstance(k.value,ast.Constant) and k.value.value is True for k in c.keywords)]\nrw=[n.lineno for n in ast.walk(t) if isinstance(n,ast.Constant) and isinstance(n.value,str) and 'mode=rw' in n.value]\nneed=[x for x in ('AGY_BRIDGE_SQLITE_REASONING','SQLITE_REASONING_ENABLED','AGY_BRIDGE_CONVERSATIONS','mode=ro') if x not in src]\nerrs=[]\nif sorted(roots-allowed): errs.append('non-stdlib imports %s'%sorted(roots-allowed))\nif not calls: errs.append('no sqlite3.connect call')\nif nouri: errs.append('sqlite3.connect without uri=True at %s'%nouri)\nif rw: errs.append('write-mode URI at %s'%rw)\nif need: errs.append('missing %s'%need)\nprint('FAIL: '+'; '.join(errs) if errs else 'OK'); sys.exit(1 if errs else 0)\nPY",
      "expected": "exit 0 и «OK»: корни импортов ⊆ stdlib baseline ∪ {sqlite3, random}; каждый sqlite3.connect с uri=True; нет URI mode=rw/rwc; присутствуют AGY_BRIDGE_SQLITE_REASONING, SQLITE_REASONING_ENABLED, AGY_BRIDGE_CONVERSATIONS и mode=ro",
      "environment": "cwd=repo_root, python3 -I (ast)",
      "owner": "Verifier"
    },
    {
      "id": "VER-010",
      "requirement_ids": [
        "REQ-001",
        "REQ-003",
        "REQ-006",
        "REQ-007",
        "REQ-012",
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-008",
        "RISK-005",
        "RISK-006",
        "RISK-007"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный гейт L2 clean-room (execution-evidence.md + evidence-manifest.sha256 в run_dir/teamlead): мост поднят из кандидата на /usr/bin/python3 с фейковым AGY_LAUNCHER и фикстурами AGY_BRIDGE_BRAIN/AGY_BRIDGE_CONVERSATIONS, AGY_BRIDGE_SQLITE_REASONING=1, writer-процесс обновляет WAL-БД рядом 523→810→1088→1419→2156 байт с интервалами 1.53/2.78/5.09/3.30 с. PASS только если одновременно: TC-20 ≥2 чанка до status=3; TC-22 снимок→сокет ≤ SQLITE_POLL_S+0.5 с на каждом снимке; TC-60 и TC-61 100/100; TC-62 EOF→stop ≤1.0 с; TC-93 CPU потока опроса ≤1% ядра на ход при 8 параллельных фикстурах за 60 с; writer ни разу не получил SQLITE_BUSY; в bridge.err нет текста мышления фикстуры",
      "environment": "Отдельный clean-room worktree кандидата, временные каталоги, без сети и без доступа к ~/.gemini и ~/.dsh владельца; /usr/bin/python3 3.9.6",
      "owner": "Teamlead"
    },
    {
      "id": "VER-011",
      "requirement_ids": [
        "REQ-001",
        "REQ-008",
        "REQ-009",
        "QA-001",
        "QA-002",
        "QA-005",
        "QA-007",
        "QA-010",
        "RISK-001",
        "RISK-003",
        "RISK-008",
        "THREAT-005"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный гейт L3 (handoff-qa.md §6) на 127.0.0.1:9887 после ACCEPT Совета и merge MR: бэкап ~/work/backups/agy-bridge-<ts>/, копия server.py + sha256, kickstart, /health. Фаза A (флаг выключен): S3 изоляция — второй агентный ход resume=1 с тем же cid; S4 у всех ходов есть мышление до stop; квотный/ошибочный ход без повторного чанка мышления. Фаза B: атомарная запись dynamic_config.json {SQLITE_REASONING_ENABLED: true} в каталог деплоя без рестарта; S1 первый чанк reasoning_content ≤5 с от начала генерации шага и интервалы ≤6 с, мышление раньше stop; S2 блок Think обновляется по шагам, в bridge.err строки sqlite-emit без текста. Откат: SQLITE_REASONING_ENABLED=false (мгновенно) или восстановление бэкапа + kickstart. Отчёт ПРОВЕРЕНО ЛЁГКИМ/ТЯЖЁЛЫМ/НЕ ПРОВЕРЕНО; непустое НЕ ПРОВЕРЕНО = не сдано",
      "environment": "Боевой LaunchAgent com.user.dsh-agy-bridge, существующий рабочий чат DSH, gemini-4-argon effort high, аккаунт agy с квотой; факты в ~/Мой диск/tmp/trace/<дата>/agy-realtime-reasoning/<run-id>/",
      "owner": "Teamlead"
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-1: откуда и как брать мышление шага в реальном времени, не ломая ход и контракт?",
      "choice": "Live-источник conversations/<cid>.db: stdlib sqlite3 только на чтение (mode=ro) + pure-Python парсер wire-формата step_payload (поле 20 → подполе 3, UTF-8), опрос в том же потоке, что и _TranscriptTail, с общей дедупликацией по str(idx)==str(step_index); fail-open, водяной знак для resume, breaker и флаг AD-006",
      "alternatives": [
        "B: только транскрипт с более частым опросом — запись шага появляется после DONE (F-29), реалтайма не даёт",
        "C: thinking_delta из stdout stream-json — не сериализуется в agy 1.4.9 (F-27, F-28)",
        "D: Python SDK google-antigravity — мысли только после блокирующего send() (F-37) и новая зависимость",
        "E: CLI sqlite3 подпроцессом — ошибка 14 на той же БД (F-35) и процесс на каждый опрос",
        "F: локальный agentapi — не исследован (OPEN-11), нет фактов"
      ],
      "drivers": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-010",
        "REQ-012",
        "Python 3.9.6 stdlib (F-51)",
        "файлы agy только на чтение (handoff §10)"
      ],
      "consequences": [
        "Мост читает внутреннюю недокументированную схему agy 1.4.9: при автоапдейте источник может замолчать — смягчено breaker'ом, транскрипт остаётся минимальным источником (N_floor=1)",
        "Один дополнительный SQLite read-соединение и ≤2 запроса/с на активный ход; CPU ≤1% ядра на ход (гейт L2)",
        "Правило выдачи мышления становится append-only (_reasoning_delta); _reasoning_suffix для text_delta в _pump не меняется",
        "Откат: флаг SQLITE_REASONING_ENABLED=false/env 0 — поведение источника мышления as-is"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-030",
        "EVD-031",
        "EVD-032",
        "EVD-033",
        "EVD-052",
        "EVD-053",
        "EVD-004",
        "EVD-018"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-01..12, 20..24, 30..33, 40..44, 50, 51, 91, 92, AO-01, AO-05, AO-07, AO-08 зелёные; VER-002 на /usr/bin/python3 зелёный"
      },
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-009",
        "VER-010",
        "VER-011"
      ],
      "details": {
        "component": "Источник мышления хода — один daemon-поток на Run (развитие _TranscriptTail; имя класса — зона Coder). Владеет словарём seen (единственный писатель, без замков), читает transcript_full.jsonl каждые TRANSCRIPT_POLL_S=0.05 с (as-is) и conversations/<cid>.db каждые SQLITE_POLL_S, эмитит только через emit-колбэк ('reasoning', str) в Run.q. Граница совместимости F-03/F-06/F-07 не меняется",
        "enablement": "sqlite_enabled вычисляется один раз в Run.__init__: AD-006 flag (env override → dynamic_config.json → false) И breaker разрешает (AD-005/AO-01). Первая инструкция пути SQLite: if not sqlite_enabled: return (H-CPU-I3)",
        "db_path": "CONV_DIR = Path(env AGY_BRIDGE_CONVERSATIONS) или ~/.gemini/antigravity-cli/conversations; путь CONV_DIR / (cid + '.db') строится только если cid fullmatch ^[0-9A-Fa-f-]{8,64}$ (regex — константа модуля) и resolved parent == CONV_DIR.resolve(); иначе источник выключен на ход + одна строка лога",
        "open": "sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=0.05, isolation_level=None, check_same_thread=True) в потоке источника; PRAGMA query_only=ON; PRAGMA cache_size=-1024. Соединение живёт до выхода потока и закрывается в finally. Ошибка connect/execute (OperationalError unable to open/locked/busy) = «изменений нет», повтор на следующем опросе, одна строка sqlite-open-fail на ход. Явных транзакций нет: каждый SELECT autocommit, курсор вычитывается fetchall() сразу — читатель не держит snapshot между опросами",
        "query": "Один запрос на опрос (K_calls=1): SELECT idx, length(step_payload), step_payload FROM steps WHERE step_type = 15 AND status = 8 AND idx >= ? ORDER BY idx LIMIT 4. Константы STEP_TYPE_PLANNER=15, STEP_STATUS_GENERATING=8 привязаны к agy 1.4.9. Строки с неизменной length(step_payload) не парсятся повторно (S-HERD-I3 аналог, AO-05); payload > 1 MiB пропускается с логом",
        "watermark_resume": "Свежий разговор: base_idx=0. Resumed (run_cid известен до spawn): до Popen читается MAX(idx)+1 через '?mode=ro&immutable=1' (писателя этого cid нет: _in_flight_cids, ход ещё не запущен; бюджет ≤0.1 с; любая ошибка → base_idx=None). Транскрипт для resumed берёт offset = размер файла ДО spawn (а не после bind) — закрывает TC-51. При base_idx=None выбираются только строки status=8 — завершённые шаги прошлых ходов (status=3) не попадают в выборку",
        "parser": "Чистая функция bytes → str ('' = мышления нет), без I/O и логов, без рекурсии: varint ≤10 байт; tag = field<<3|wt; wt0 — пропуск varint, wt1 — 8 байт, wt5 — 4 байта, wt2 — длина varint ≤ остатка; wt3/4/6/7 или выход за границу → ''. Корневое поле 20 (wt2) → вложенный разбор → подполе 3 (wt2) → bytes.decode('utf-8') strict; UnicodeDecodeError → ''. Повторные вхождения — последнее побеждает. memoryview без копий; payload ≤1 MiB. Исключения наружу не выходят",
        "dedup": "Общий seen по ключу str(idx)/str(step_index). Новая функция выдачи мышления append-only: text.startswith(prev) → text[len(prev):]; prev.startswith(text) → '' (устаревший/короче снимок); иначе → '' + сигнал divergence (лог reasoning-divergent cid step len_prev len_new, breaker.trip). seen[key] хранит отданный текст, не перезаписывается расходящимся снимком. Транскрипт (DONE) — авторитет финального текста: склейка = финальный thinking (AC-004)",
        "observability": "Строки stderr: sqlite-on/off cid=<8> reason=flag|env|breaker|cid; sqlite-emit cid=<8> step=N len=L; sqlite-open-fail cid=<8> err=<класс исключения>; sqlite-schema-mismatch cid=<8>; reasoning-divergent; drain cid=<8> ms=… emitted=…; reasoning-late-drop. Без текста мышления, промптов и секретов (TC-92, THREAT-004)"
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-2: как гарантировать, что мышление последнего шага (запись через ~90 мс после result) уходит до done, не продлевая ход больше 1.0 с?",
      "choice": "Join-before-done: Run._pump после EOF и proc.wait() ставит _proc_done, ждёт завершения финального drain потока источника (join с жёстким бюджетом) и только затем кладёт ('done', …); FIFO очереди гарантирует, что _execute прочитает все reasoning до done. Drain — опрос с ранним выходом по сигналу полноты, DRAIN_MIN_S=0.25, DRAIN_MAX_S=0.6",
      "alternatives": [
        "B: _execute после done ждёт поток источника и дочитывает очередь — размазывает ответственность lifecycle между Handler и Run",
        "C: отдельный маркер конца источника и ожидание двух маркеров в _execute — больше состояний в презентационном цикле и все ветки выхода _execute",
        "D: увеличить паузу _pump больше TRANSCRIPT_GRACE_S — остаётся гонкой по времени и добавляет фиксированную задержку всем ходам"
      ],
      "drivers": [
        "REQ-006",
        "REQ-007",
        "REQ-010",
        "T-LIFE/v1",
        "R-BULK-I1"
      ],
      "consequences": [
        "Ход завершается позже EOF на 0.25..0.6 с (ранний выход при полноте), EOF→done ≤0.8 с, EOF→stop ≤0.85 с ≤1.0 с",
        "События источника после закрытия drain не ставятся в очередь, а логируются reasoning-late-drop (нет тихой потери)",
        "Поток источника без bind (нет init) и при stop_event выходит сразу — нет 120-секундного висения и лишних 0.4 с в close"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-006",
        "EVD-007",
        "EVD-008",
        "EVD-029",
        "EVD-043"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-60 (20 прогонов в L1), TC-61, TC-62, TC-63, AO-03, AO-04 зелёные; L2 VER-010 100/100"
      },
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-010"
      ],
      "details": {
        "pump_order": "EOF stdout → rc=proc.wait() → sleep 0.05 (stderr, as-is) → t_exit=monotonic(); _proc_done.set() → tail.thread.join(timeout=DRAIN_MAX_S+0.15) → если жив: лог drain-timeout, drain_closed=True → q.put(('done', …)). pump_error: _proc_done.set(), drain_closed=True, как сейчас без join",
        "drain_loop": "На _proc_done (не stop): до deadline=t_exit+DRAIN_MAX_S цикл каждые 0.05 с: чтение транскрипта; опрос SQLite (если включён; при ошибке mode=ro после выхода процесса — одна попытка '?mode=ro&immutable=1', писателя уже нет). Ранний выход: elapsed ≥ DRAIN_MIN_S И размер транскрипта не менялся 2 чтения подряд И каждый шаг, виденный SQLite в генерации, имеет запись транскрипта. Иначе выход по deadline",
        "stop_path": "stop_event (Run.close: client_gone/timeout/ошибка) → немедленный выход без grace-сна; соединение SQLite закрывается в finally",
        "unbound": "Ожидание bind прерывается при _proc_done или stop_event (сейчас только stop/120 с) — join в _pump не может зависнуть",
        "late_events": "emit после drain_closed не кладёт в очередь: лог reasoning-late-drop cid step len (REQ-006 «не теряются молча»)",
        "budget": "DRAIN_MAX_S = clamp(env AGY_BRIDGE_TRANSCRIPT_GRACE, 0.1, 0.8), дефолт меняется 0.4→0.6 и трактуется как максимум окна drain; DRAIN_MIN_S=min(0.25, DRAIN_MAX_S). EOF→done ≤ 0.05+0.6+0.15=0.8 с; _execute +0.05 (as-is) → ≤0.85 с ≤1.0 с"
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-3: как защитить уже отданный клиенту reasoning при сбое на следующем шаге?",
      "choice": "Отданное потоковое мышление — выдача: delivered = bool(text or tool_calls or (stream and reasoning)); после выдачи нет ни невидимого повтора, ни холодного fallback горячей сессии; исход — неизменный контракт ошибки после старта потока: data:{error} + [DONE]; отданные чанки не повторяются. JSON-режим не меняется (там мышление клиенту ещё не отдано)",
      "alternatives": [
        "B: явный флаг «байты отданы» из колбэков on_text/on_reasoning — точнее, но шире правка колбэков и тестовых заглушек; эквивалентен A для SSE",
        "C: stop с частичным ответом вместо кадра ошибки — сохраняет блок Think, но маскирует сбой и меняет контракт ошибки; вынесено владельцу (Q-002)",
        "D: учитывать reasoning и в JSON-режиме — лишает нестриминговые запросы безопасного повтора без пользы"
      ],
      "drivers": [
        "REQ-008",
        "REQ-010",
        "R-BULK-I2",
        "NON_IDEMPOTENT_RETRY"
      ],
      "consequences": [
        "При квотной ошибке после мышления клиент получает кадр error вместо повторного хода: 1 spawn вместо 2-3 (F-46)",
        "Горячая сессия после сбоя всё так же инвалидируется (as-is), но холодный повтор поверх отданного мышления не запускается",
        "Если DSH затирает Think кадром ошибки (F-47) — UX-риск RISK-008 остаётся до решения владельца"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-046",
        "EVD-047"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-70 (1 запуск, 0 повторных чанков), TC-71 (нет холодного повтора), TC-72 (повтор до выдачи сохранён) зелёные"
      },
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "RC-4: как не дать фоновым запросам DSH без инструментов занять или перезаписать горячую сессию агентного диалога?",
      "choice": "Комбинация A+B: sess_key = (model_id, cwd, effort, agentic) где agentic = tools_count > 0; запросы one-shot без инструментов (tools_count == 0 и в messages нет role=assistant) не вызывают _session_claim и не коммитят сессию (ctx sess_key=None). Явный conversation_id клиента — как сейчас",
      "alternatives": [
        "A отдельно: только признак tools в ключе — фоновые заголовки разных чатов продолжали бы разговоры друг друга (утечка контекста между чатами)",
        "B отдельно: только обход для one-shot — многоходовые plain-диалоги без tools всё ещё делили бы ключ с агентным",
        "C: ключ по хешу первого user-сообщения/prompt_cache_key — поле в запросах DSH не исследовано (F-12), выше риск ложных промахов"
      ],
      "drivers": [
        "REQ-009",
        "THREAT-005",
        "M-SEM/v1"
      ],
      "consequences": [
        "Фоновая генерация заголовка всегда холодная и без коммита — её cid не попадает в стор",
        "Первый ход plain-чата без tools не коммитится; горячая сессия plain-чата появляется со второго хода (небольшая цена, RISK-009)",
        "После рестарта моста стор пуст (as-is): формат ключа меняется без миграции"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-012",
        "EVD-013",
        "EVD-041",
        "EVD-042"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-80, TC-81, TC-82 зелёные; лог exec содержит sess=agentic|plain|oneshot"
      },
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-007",
        "VER-011"
      ]
    },
    {
      "id": "AD-005",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Какие resilience-guardrails нужны на изменяемых путях, чтобы закрыть R-BULK-I2/I3, S-HERD-I2 и O-EXIT без расширения объёма?",
      "choice": "(1) Процессный token-bucket retry budget: capacity B_retry_max=3, старт 3, +0.2 токена на первичный запрос, min_reserve=0.0; любой повтор (включая hot→cold fallback) тратит 1 токен, нет токена — нет повтора + лог retry-budget-exhausted. (2) Пауза повтора Full Jitter U(0, min(2.0, 2.0·2^(a-1))) через инъецируемый модульный RNG вместо фиксированных 2·attempt с. (3) SQLite breaker процесса: 3 подряд хода со схемной ошибкой/битой БД/divergence → OPEN на 600·U(0.8,1.2) с (divergence — сразу OPEN), затем HALF_OPEN ровно на один пробный ход; ошибки открытия/блокировки не считаются. (4) Одна строка O-EXIT done на каждом выходе _run_once, включая no-slot и launcher_unavailable, с полями источника",
      "alternatives": [
        "Оставить as-is: 1 повтор на каждый запрос без процессного бюджета — при квотном шторме (F-46) нагрузка на agy удваивается, R-BULK-I2 не закрыт",
        "Только per-request лимит без bucket — не ограничивает суммарные повторы за окно",
        "Без breaker — после автоапдейта agy каждый ход тратит опросы на неверную схему и может эмитить расходящийся текст"
      ],
      "drivers": [
        "R-BULK-I2",
        "R-BULK-I3",
        "S-HERD-I2",
        "O-EXIT/v1",
        "REQ-004",
        "REQ-008",
        "REQ-012"
      ],
      "consequences": [
        "Под штормом сбоев часть запросов вернёт ошибку без повтора (RISK-010)",
        "Пауза повтора становится случайной в [0, 2] с; тесты используют инъецированный RNG без wall-clock",
        "Логи done появляются и на ранних выходах; существующий префикс `done model=` сохранён для grep (F-40)"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-063",
        "EVD-068",
        "EVD-046"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; AO-01 (breaker: OPEN без connect, HALF_OPEN ровно 1 проба), AO-02 (N_retries ≤ floor(0.2·N)+3 при N=100), AO-06 (done-строка на всех выходах) зелёные"
      },
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    {
      "id": "AD-006",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как включать/выключать SQLite-источник (REQ-011) с мгновенным kill-switch и без нарушения канона фичефлагов?",
      "choice": "Фичефлаг SQLITE_REASONING_ENABLED (boolean) в runtime dynamic_config.json рядом с server.py (деплой: ~/.dsh/bridges/agy-bridge/dynamic_config.json; в git не коммитится), stat-кэш (mtime_ns,size), чтение один раз на ход; отсутствие/битый/не-boolean → false; кодовый default=false. Env AGY_BRIDGE_SQLITE_REASONING: 0/false/off — принудительно выключено (kill-switch поверх файла), 1/true/on — принудительно включено (L2, диагностика), иначе — значение файла. RC-2..RC-4 и AD-005 от флага не зависят",
      "alternatives": [
        "Env AGY_SQLITE_REASONING с default=1 (пример брифа) — новое поведение включено без флага-«выключено по умолчанию», kill-switch требует правки plist и рестарта",
        "Env с default=0 и включение через plist — включение и откат только через рестарт LaunchAgent",
        "Расширить core/context_resilience FlagSource — вне target_files и чужая зона core/"
      ],
      "drivers": [
        "REQ-011",
        "канон «фича за флагом default=false, kill-switch без рестарта» (EVD-065)",
        "REUSE in-repo прецедента zen (EVD-064)"
      ],
      "consequences": [
        "После деплоя server.py поведение мышления as-is до явного включения флага на шаге L3 (фаза B)",
        "Kill-switch — запись false в файл без рестарта; env 0 — аварийное выключение через рестарт",
        "Отклонение от примера брифа (default=1) вынесено владельцу (Q-004)"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-064",
        "EVD-065",
        "EVD-071"
      ],
      "confirmation": {
        "kind": "test",
        "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/test_agy_bridge_resilience.py",
        "expected": "exit 0; TC-91 (флаг выкл → sqlite3.connect call_count==0), AO-05 зелёные; VER-009 и VER-008 зелёные"
      },
      "verification_ids": [
        "VER-001",
        "VER-007",
        "VER-008",
        "VER-009",
        "VER-011"
      ]
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "performance",
      "source": "DSH client",
      "stimulus": "argon пишет мышление шага в БД снимками 523→2156 байт с интервалами 1.5-5.1 с",
      "environment": "здоровый ход, флаг включён, /usr/bin/python3",
      "artifact": "bridges/agy-bridge/server.py источник мышления",
      "response": "чанки reasoning_content до завершения шага",
      "response_measure": "≥2 чанка до status=3; снимок→сокет ≤ SQLITE_POLL_S+0.5 = 1.0 с; первая дельта ≤5 с от начала генерации шага",
      "verification_ids": [
        "VER-001",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "QA-002",
      "quality": "usability",
      "source": "владелец в DSH",
      "stimulus": "фаза мышления 15-45 с",
      "environment": "боевой :9887, gemini-4-argon high",
      "artifact": "SSE-поток моста",
      "response": "блок Think обновляется во время мышления",
      "response_measure": "интервал между дельтами мышления ≤6 с (ASM-008)",
      "verification_ids": [
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "agy 1.4.9",
      "stimulus": "запись PLANNER_RESPONSE через 90 мс после result и немедленный выход",
      "environment": "фейковый лончер",
      "artifact": "Run._pump + drain источника",
      "response": "мышление последнего шага до finish_reason=stop",
      "response_measure": "100/100 прогонов (L2), 20/20 в L1; EOF→stop ≤1.0 с",
      "verification_ids": [
        "VER-001",
        "VER-010"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "файловая система / agy",
      "stimulus": "БД отсутствует, закрыта (unable to open на 3.9.6), заблокирована, битая или без таблицы steps",
      "environment": "флаг включён",
      "artifact": "SQLite-источник",
      "response": "fail-open: ход done, мышление из транскрипта",
      "response_measure": "0 исключений наружу; текст и мышление равны прогону без SQLite; ход не дольше REQ-007",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-005",
      "quality": "reliability",
      "source": "agy",
      "stimulus": "Individual quota reached после отданного мышления",
      "environment": "SSE, горячая или холодная сессия",
      "artifact": "Handler._run_once",
      "response": "без невидимого повтора; data:{error}+[DONE]",
      "response_measure": "ровно 1 spawn; 0 повторных чанков мышления",
      "verification_ids": [
        "VER-001",
        "VER-011"
      ]
    },
    {
      "id": "QA-006",
      "quality": "compatibility",
      "source": "DSH и существующие тесты",
      "stimulus": "любой запрос после изменения",
      "environment": "кандидат MR",
      "artifact": "HTTP/SSE контракт :9887",
      "response": "форма чанков, эндпоинты, порт и флаги agy неизменны",
      "response_measure": "22 legacy теста зелёные без правок; набор красных полного прогона совпадает с baseline (3)",
      "verification_ids": [
        "VER-001",
        "VER-005",
        "VER-006"
      ]
    },
    {
      "id": "QA-007",
      "quality": "reliability",
      "source": "DSH",
      "stimulus": "агентный ход, параллельный фоновый запрос заголовка без tools, агентный ход",
      "environment": "одна модель/cwd/effort",
      "artifact": "_session_store / sess_key",
      "response": "агентный диалог продолжает свой разговор",
      "response_measure": "третий ход resume=1 с cid первого; фоновый не получает cid первого",
      "verification_ids": [
        "VER-001",
        "VER-011"
      ]
    },
    {
      "id": "QA-008",
      "quality": "cost",
      "source": "8 параллельных ходов",
      "stimulus": "опрос БД 60 с",
      "environment": "/usr/bin/python3, фикстуры",
      "artifact": "поток источника",
      "response": "ограниченное CPU",
      "response_measure": "≤1% ядра на ход (≤0.08 ядра на 8 ходов ≤0.05×2.0 ядра)",
      "verification_ids": [
        "VER-010"
      ]
    },
    {
      "id": "QA-009",
      "quality": "security",
      "source": "agy stdout / файлы agy",
      "stimulus": "cid с ../ или мусор в step_payload",
      "environment": "любой ход",
      "artifact": "путь БД и парсер",
      "response": "нет открытия вне CONV_DIR, нет записи, нет исключения",
      "response_measure": "0 вызовов connect для невалидного cid; парсер возвращает '' на всех усечениях; в логах нет текста мышления",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ]
    },
    {
      "id": "QA-010",
      "quality": "operability",
      "source": "оператор",
      "stimulus": "аварийное выключение SQLite-источника",
      "environment": "боевой :9887",
      "artifact": "dynamic_config.json / env",
      "response": "следующий ход идёт as-is без SQLite",
      "response_measure": "запись SQLITE_REASONING_ENABLED=false действует со следующего хода без рестарта; env 0 — после kickstart",
      "verification_ids": [
        "VER-001",
        "VER-011"
      ]
    },
    {
      "id": "QA-011",
      "quality": "testability",
      "source": "Verifier",
      "stimulus": "прогон L1",
      "environment": "/usr/bin/python3 3.9.6 и uvx pytest",
      "artifact": "tests/test_agy_bridge_resilience.py",
      "response": "детерминированные оракулы без wall-clock флаков",
      "response_measure": "оба интерпретатора зелёные; тайминговые пороги только в L2",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "Handler.do_POST / _serve_sse / _serve_json",
      "responsibility": "OpenAI framing и единственный writer сокета; вычисляет agentic/oneshot и sess_key; форму чанков не меняет",
      "allowed_dependencies": [
        "Run.q кортежи (init/text/reasoning/tool_trace/result/done/pump_error)",
        "API стора сессий",
        "_run_once"
      ],
      "forbidden_dependencies": [
        "прямой доступ к sqlite3/транскрипту",
        "новые поля SSE или synthetic status-текст",
        "текст мышления в логах"
      ],
      "verification_ids": [
        "VER-001",
        "VER-006"
      ]
    },
    {
      "id": "BND-002",
      "component": "Run (lifecycle процесса agy) и Run._pump",
      "responsibility": "spawn/stdout/stderr, порядок join-before-done, бюджет drain, close и зачистка группы",
      "allowed_dependencies": [
        "источник мышления (start/bind/join)",
        "AdaptiveTimeoutController",
        "_kill_group"
      ],
      "forbidden_dependencies": [
        "разбор step_payload",
        "сон сверх бюджета drain",
        "запись в Handler/wfile"
      ],
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    {
      "id": "BND-003",
      "component": "Источник мышления хода (транскрипт + SQLite)",
      "responsibility": "только чтение transcript_full.jsonl и conversations/<cid>.db (mode=ro), владение seen, append-only выдача, fail-open, breaker-учёт, диагностические строки без текста",
      "allowed_dependencies": [
        "stdlib sqlite3/pathlib/json/re",
        "pure-парсер",
        "emit-колбэк",
        "_log"
      ],
      "forbidden_dependencies": [
        "запись в ~/.gemini",
        "Handler/wfile",
        "сторонние пакеты",
        "_reasoning_suffix для мышления"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-009"
      ]
    },
    {
      "id": "BND-004",
      "component": "Pure wire-парсер step_payload",
      "responsibility": "bytes → str|'' по полю 20.3 без исключений",
      "allowed_dependencies": [
        "встроенные типы, memoryview"
      ],
      "forbidden_dependencies": [
        "I/O",
        "логирование",
        "рекурсия",
        "глобальное состояние"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "BND-005",
      "component": "Стор горячих сессий (_session_claim/_commit/_invalidate)",
      "responsibility": "изоляция классов сессий agentic/plain, обход one-shot",
      "allowed_dependencies": [
        "_session_store_lock"
      ],
      "forbidden_dependencies": [
        "переиспользование между классами",
        "коммит one-shot запросов"
      ],
      "verification_ids": [
        "VER-001"
      ]
    },
    {
      "id": "BND-006",
      "component": "Политика повтора в _run_once",
      "responsibility": "учёт выдачи (text/tool_calls/streamed reasoning), retry budget, jitter, O-EXIT done на всех выходах",
      "allowed_dependencies": [
        "процессный retry bucket",
        "инъецируемый RNG",
        "_log"
      ],
      "forbidden_dependencies": [
        "повтор после выдачи",
        "бесконечные/небюджетные повторы"
      ],
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "agy-bridge SSE/JSON",
      "consumer": "DSH OpenAI reader",
      "change": "reasoning_content приходит раньше и большим числом чанков во время генерации шага (при включённом флаге); последний шаг больше не теряется гонкой drain. Разрешено текущей задачей REQ-001/REQ-006",
      "compatibility": "Форма чанка, порядок role→reasoning→content→stop→usage→[DONE], поля и текст мышления не меняются; при выключенном флаге — только исправление drain",
      "verification_ids": [
        "VER-001",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "Handler._run_once",
      "consumer": "DSH",
      "change": "Сбой после отданного в поток мышления даёт data:{error}+[DONE] вместо невидимого повтора/холодного fallback. Разрешено REQ-008",
      "compatibility": "Кадр ошибки после старта потока — существующий контракт (F-11); JSON-режим без изменений",
      "verification_ids": [
        "VER-001"
      ]
    },
    {
      "id": "CD-003",
      "type": "behavior",
      "producer": "стор горячих сессий",
      "consumer": "DSH диалоги",
      "change": "Горячие сессии разделены по agentic; one-shot запросы без tools не используют стор. Разрешено REQ-009",
      "compatibility": "API и /health (hot_sessions) неизменны; явный conversation_id клиента как раньше; после рестарта стор пуст (as-is)",
      "verification_ids": [
        "VER-001",
        "VER-011"
      ]
    },
    {
      "id": "CD-004",
      "type": "behavior",
      "producer": "конфигурация моста",
      "consumer": "оператор / LaunchAgent",
      "change": "Новые необязательные env AGY_BRIDGE_SQLITE_REASONING, AGY_BRIDGE_SQLITE_POLL (0.5 с, clamp 0.2..2.0), AGY_BRIDGE_CONVERSATIONS; runtime-флаг SQLITE_REASONING_ENABLED в dynamic_config.json; AGY_BRIDGE_TRANSCRIPT_GRACE трактуется как максимум окна drain (0.6, clamp 0.1..0.8). Разрешено REQ-011/REQ-007",
      "compatibility": "Аддитивно: без файла и env поведение источника мышления as-is; деплойный env (F-38) не меняется",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ]
    },
    {
      "id": "CD-005",
      "type": "behavior",
      "producer": "Handler._run_once",
      "consumer": "DSH",
      "change": "Повторы ограничены процессным retry budget и идут с Full Jitter паузой [0,2] с (AD-005)",
      "compatibility": "Одиночный сбой до выдачи по-прежнему повторяется один раз; под штормом часть запросов получает ошибку без повтора",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "context",
      "question": "Кто взаимодействует с мостом и какие границы внешние?",
      "artifact_ref": "architecture/architecture-packet.json#views[0].diagram + scope + BND-001",
      "diagram": "graph LR; DSH-->|HTTP SSE Bearer loopback :9887|Bridge[agy-bridge]; Bridge-->|spawn stream-json|Agy[agy 1.4.9]; Agy-->|write|Transcript[(brain/<cid>/transcript_full.jsonl)]; Agy-->|write WAL|Db[(conversations/<cid>.db)]; Bridge-.->|read only|Transcript; Bridge-.->|read only mode=ro|Db; Op[оператор]-->|dynamic_config.json|Bridge"
    },
    {
      "id": "VIEW-002",
      "type": "component",
      "question": "Как распределены обязанности внутри server.py?",
      "artifact_ref": "architecture/architecture-packet.json#boundaries BND-001..BND-006 + views[1].diagram",
      "diagram": "graph TD; Handler-->RunOnce[_run_once: delivered, retry budget, O-EXIT]; RunOnce-->Run; Run-->Pump[_pump]; Run-->Src[источник мышления: транскрипт+SQLite, seen, breaker]; Src-->Parser[pure wire-парсер]; Pump-->|join-before-done|Src; Src-->|emit reasoning|Q[(Run.q)]; Pump-->|text/result/done|Q; RunOnce-->|_execute читает|Q; Handler-->Store[стор сессий: agentic/plain/oneshot]"
    },
    {
      "id": "VIEW-003",
      "type": "dynamic",
      "question": "Какой порядок событий гарантирует мышление до stop и ограничение 1.0 с?",
      "artifact_ref": "architecture/architecture-packet.json#AD-002.details + views[2].diagram",
      "diagram": "sequenceDiagram; agy->>Pump: result; agy->>Transcript: PLANNER_RESPONSE (+90 мс); agy-->>Pump: EOF; Pump->>Pump: wait, sleep 0.05, _proc_done; Pump->>Src: join(≤0.75 с); Src->>Q: reasoning (drain 0.25..0.6 с); Src-->>Pump: exit; Pump->>Q: done; Execute->>Q: reasoning, done (FIFO); Execute->>Client: reasoning_content, stop"
    },
    {
      "id": "VIEW-004",
      "type": "dfd",
      "question": "Где проходят trust boundaries и куда идут чувствительные данные?",
      "artifact_ref": "architecture/architecture-packet.json#threat_model + views[3].diagram",
      "diagram": "graph LR; Client-->|prompt, Bearer|Bridge; Bridge-->|prompt stdin|Agy; Agy-->|thinking bytes|Db; Db-->|step_payload bytes, untrusted|Parser; Parser-->|thinking str|Client; Bridge-->|cid8, step, len, без текста|Log[(bridge.err)]"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Автоапдейт agy меняет номера полей/статусов: источник молчит или отдаёт не тот текст (F-25, F-28)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Строгий фильтр step_type=15/status=8 и strict UTF-8; divergence против транскрипта → breaker OPEN; транскрипт остаётся источником; L3 S1 после автоапдейта",
      "verification_ids": [
        "VER-001",
        "VER-011"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "mode=ro на 3.9.6 не открывает закрытую WAL-БД (F-52) — нет live-дельт",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Соединение держится на ход, повтор открытия на каждом опросе, immutable=1 только без писателя; fail-open; L1/L2 на /usr/bin/python3",
      "verification_ids": [
        "VER-002",
        "VER-010"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Квота аккаунта agy блокирует L3 (F-46)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Штатное переключение аккаунта или ожидание сброса; без L3 «готово» запрещено",
      "verification_ids": [
        "VER-011"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Непрефиксный снимок дублирует или искажает мышление (F-04)",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Append-only выдача: расхождение не эмитится, логируется, размыкает breaker; остаток шага теряется только в аномалии и виден в логе",
      "verification_ids": [
        "VER-001"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "6-8 параллельных ходов умножают опросы файлов (F-55)",
      "probability": "low",
      "impact": "low",
      "mitigation": "1 запрос/0.5 с на ход, повторный парсинг только при смене length, бюджет CPU ≤1% на ход в L2",
      "verification_ids": [
        "VER-010"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Читатель мешает писателю agy (SQLITE_BUSY, рост WAL из-за удержания snapshot)",
      "probability": "low",
      "impact": "medium",
      "mitigation": "query_only, autocommit-SELECT с немедленным fetchall, нет явных транзакций, timeout 0.05 с; L2 проверяет отсутствие SQLITE_BUSY у writer",
      "verification_ids": [
        "VER-001",
        "VER-010"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Drain удлиняет каждый ход",
      "probability": "low",
      "impact": "low",
      "mitigation": "Ранний выход по сигналу полноты после 0.25 с; потолок 0.6 с; EOF→stop ≤1.0 с",
      "verification_ids": [
        "VER-001",
        "VER-010"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "Кадр error после отданного мышления затирает блок Think в DSH (F-47, OPEN-06)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Контракт ошибки неизменен и честен; альтернатива stop+частичный ответ — решение владельца Q-002; проверка в L3",
      "verification_ids": [
        "VER-011"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Обход стора для one-shot снижает долю горячих продолжений plain-чатов",
      "probability": "low",
      "impact": "low",
      "mitigation": "Горячая сессия plain-чата со второго хода; корректность не страдает (холодный ход с полной историей)",
      "verification_ids": [
        "VER-001"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "Retry budget отказывает в законном повторе после шторма",
      "probability": "low",
      "impact": "low",
      "mitigation": "Ёмкость 3 токена, +0.2 на первичный запрос; лог retry-budget-exhausted",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    {
      "id": "RISK-011",
      "scenario": "Унаследованные отклонения baseline (ожидание слота 900/1800 с, ожидающие >2M, 12 ошибок basedpyright) воспринимаются как новые",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Зафиксированы как baseline_debt с evidence; VER-004 запрещает рост по каждой паре; VER-008 запрещает правки вне target_files; закрытие — отдельная задача (Q-005)",
      "verification_ids": [
        "VER-004",
        "VER-008"
      ]
    },
    {
      "id": "RISK-012",
      "scenario": "Синтаксис 3.10+ в новом коде роняет мост на /usr/bin/python3 3.9.6",
      "probability": "low",
      "impact": "high",
      "mitigation": "Обязательный VER-002 на боевом интерпретаторе; from __future__ import annotations сохраняется",
      "verification_ids": [
        "VER-002"
      ]
    },
    {
      "id": "RISK-013",
      "scenario": "Текст мышления или секрет попадает в bridge.err",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Строки источника только cid8/step/len/класс ошибки; TC-92 проверяет отсутствие текста фикстуры",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    }
  ],
  "threat_model": {
    "required": true,
    "assets": [
      "текст мышления и промпты пользователя",
      "целостность файлов разговоров agy (conversations/*.db, brain/*)",
      "AGY_BRIDGE_KEY (Bearer)",
      "соответствие горячая сессия → conversation_id (контекст диалога)"
    ],
    "trust_boundaries": [
      "DSH ↔ мост: HTTP loopback с Bearer (as-is)",
      "мост ↔ процесс agy: stdout NDJSON (cid из init — недоверенный вход для построения пути)",
      "мост ↔ файлы состояния agy: байты step_payload и транскрипт — недоверенный вход парсера; доступ только на чтение",
      "мост → bridge.err: журнал без текста и секретов"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Подделанный/битый step_payload (огромная длина varint, неподдерживаемые wire types, бесконечный цикл) роняет поток или съедает CPU/память",
        "mitigation": "Проверка длины ≤ остатка, varint ≤10 байт, payload ≤1 MiB, без рекурсии, линейный проход, все исключения поглощаются → ''",
        "verification_ids": [
          "VER-001",
          "VER-002",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "cid с ../ или абсолютным путём ведёт к открытию файла вне conversations",
        "mitigation": "Константный regex ^[0-9A-Fa-f-]{8,64}$ и проверка resolved parent == CONV_DIR; иначе источник выключен на ход",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Мост пишет в БД agy или повреждает её (rw-режим, immutable при живом писателе)",
        "mitigation": "Только file:…?mode=ro, PRAGMA query_only=ON, immutable=1 только без писателя; статический гейт VER-009",
        "verification_ids": [
          "VER-007",
          "VER-009"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "Утечка текста мышления/секретов в логи",
        "mitigation": "Диагностика только cid8/step/len/класс ошибки; _mask_secrets для ошибок as-is; TC-92",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      {
        "id": "THREAT-005",
        "scenario": "Фоновый запрос получает контекст агентного диалога (утечка между чатами) или наоборот",
        "mitigation": "AD-004: класс сессии в ключе и обход стора для one-shot",
        "verification_ids": [
          "VER-001",
          "VER-007",
          "VER-011"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "HTTP/SSE/JSON контракт, порт 9887, флаги agy и текст мышления неизменны (REQ-010); новые env и runtime-флаг аддитивны; без флага источник мышления as-is, исправления RC-2..RC-4 действуют всегда",
    "migration": "NOT_APPLICABLE: у моста нет persisted state — _session_store в памяти (смена формата ключа без миграции, после рестарта стор пуст как и сейчас); файлы agy только читаются; схема agy не меняется мостом",
    "rollout": "L1 (VER-001..009) → L2 clean-room (VER-010) → downstream Совет (ACCEPT) → MR → merge человеком → L3 (VER-011): бэкап, копия server.py в ~/.dsh/bridges/agy-bridge/, sha256, kickstart; фаза A с выключенным флагом (RC-2..RC-4), фаза B — атомарная запись dynamic_config.json с SQLITE_REASONING_ENABLED=true без рестарта",
    "rollback": "Мгновенно: SQLITE_REASONING_ENABLED=false в dynamic_config.json (следующий ход as-is) или env AGY_BRIDGE_SQLITE_REASONING=0 + kickstart; полностью: восстановить бэкап server.py из ~/work/backups/agy-bridge-<ts>/, launchctl kickstart -k gui/$(id -u)/com.user.dsh-agy-bridge, /health и один живой ход",
    "feature_flag": "SQLITE_REASONING_ENABLED (runtime dynamic_config.json рядом с server.py, stat-кэш, кодовый default=false) + env override AGY_BRIDGE_SQLITE_REASONING; прецедент EVD-064/065",
    "mixed_version": "Один процесс, без rolling update: старая и новая версии не работают одновременно; при kickstart горячие сессии теряются (as-is)",
    "agy_version_pin": "Схема step_type=15/status=8/20.3 подтверждена на agy 1.4.9; после автоапдейта agy — повтор L3 S1, breaker защищает от молчаливого искажения"
  },
  "approval": {
    "status": "APPROVED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": ".ai-team/runs/analyst-teamlead-agy-reasoning-20261029/route-manifest.json (routing_approval=auto, approved_by_user=true)",
    "rationale": "Все AD-001..AD-006 two-way, approval_required=false: человеческих one-way решений нет. status=APPROVED означает валидированный пакет-кандидат для downstream Архитектурного Совета (route-manifest downstream_panel=true), а не вердикт Совета и не ARCH_GATE_PASS. Вопросы владельцу Q-001..Q-005 — класса МОЖНО ПРОДОЛЖИТЬ"
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2: схема не требует независимого review внутри пакета; downstream внешний Совет обязателен по route-manifest (downstream_panel=true). Автор не выносит PASS Совета и ARCH_GATE_PASS"
  },
  "open_questions": [
    {
      "id": "Q-001",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-08: принимаете ли цели — первая дельта мышления ≤5 с, интервал ≤6 с, добавка drain ≤1.0 с?",
      "disposition": "Допущение ASM-008 принято в VER-010/VER-011; ответ меняет только пороги L2/L3"
    },
    {
      "id": "Q-002",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-06: после отданного мышления при сбое показывать кадр ошибки (выбрано, as-is контракт) или stop с частичным ответом?",
      "disposition": "AD-003 выбирает кадр ошибки без невидимого повтора; смена — отдельный two-way delta"
    },
    {
      "id": "Q-003",
      "class": "continuable",
      "blocking": false,
      "question": "OPEN-07: L3 вести на другом аккаунте agy или ждать сброса квоты (~54 ч от 2026-10-29 01:09 MSK)?",
      "disposition": "Без L3 сдача не засчитывается (VER-011)"
    },
    {
      "id": "Q-004",
      "class": "continuable",
      "blocking": false,
      "question": "Флаг SQLite-источника: оставить кодовый default=false + включение через dynamic_config.json на L3 (выбрано по канону) или включить по умолчанию, как в примере брифа (default=1)?",
      "disposition": "AD-006; смена дефолта — одна константа и отдельный two-way delta"
    },
    {
      "id": "Q-005",
      "class": "continuable",
      "blocking": false,
      "question": "Принять унаследованные отклонения baseline (ожидание слота до 1800 с > 0.30·SLA, ожидающие слота до 24 > 2M, 12 ошибок basedpyright, неограниченная Run.q) как отдельную задачу?",
      "disposition": "ASM-011; этот MR их не ухудшает (VER-004, VER-008)"
    }
  ],
  "protected_paths": [
    ".ai-team/",
    "analysis/agy-realtime-reasoning/",
    "bridges/agy-bridge/fleet.json",
    "bridges/agy-bridge/start.sh",
    "ruff.toml",
    "core/"
  ],
  "materialization": [],
  "deferred": [],
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/§7.2",
    "field_count": 46,
    "units": "СИ: время s, CPU cores, память MiB, rates req/s|conn/s|stat/s, соединения, дескрипторы, токены; векторы [d] по d ∈ {conversations_db (на файл cid), transcript_file (на ход), agy_process_slots}, [c] по классам staleness, (s) по {node_ephemeral (loopback)}",
    "contour": "Один локальный демон LaunchAgent com.user.dsh-agy-bridge на рабочей станции (не k8s): «под» = процесс моста, W=1 (ThreadingHTTPServer, потоки)",
    "required_hl_env_fields": {
      "P_steady": 1,
      "P_hpa_max": 1,
      "maxSurge_pct": 0.0,
      "maxSurge_abs": 0,
      "maxUnavailable_pct": 0.0,
      "maxUnavailable_abs": 0,
      "P_terminating_overlap": 0,
      "P_live": 1,
      "P_avail_min": 1,
      "W": 1,
      "N_proc": 1,
      "N_proc_steady": 1,
      "N_proc_avail_min": 1,
      "CPU_limit_per_pod": 2.0,
      "κ_skew": 1.0,
      "u_bg_worker": 0.12,
      "U_pod_sidecars": 0.0,
      "Mem_limit_per_pod": 512,
      "Mem_rss_worker_max": 96,
      "Mem_shared_max": 32,
      "RPS_peak": 6,
      "A_max": 2,
      "SLA_p99_s": 1800,
      "N_entities_max": 1000,
      "Limit_dep_share[d]": {
        "conversations_db": 4,
        "transcript_file": 4,
        "agy_process_slots": 8
      },
      "Limit_dep_rps[d]": {
        "conversations_db": 20,
        "transcript_file": 200
      },
      "W_fetchers[d]": {
        "conversations_db": 1,
        "transcript_file": 1
      },
      "J_init_s[d]": {
        "conversations_db": 0.0,
        "transcript_file": 0.0
      },
      "J_pod_s[d]": {
        "conversations_db": 0.0,
        "transcript_file": 0.0
      },
      "T_poll_s[d]": {
        "conversations_db": 0.5,
        "transcript_file": 0.05
      },
      "K_calls[d]": {
        "conversations_db": 1,
        "transcript_file": 1
      },
      "T_base_s[d]": {
        "conversations_db": 0.5,
        "turn_retry": 2.0
      },
      "T_cap_s[d]": {
        "conversations_db": 0.5,
        "turn_retry": 2.0
      },
      "Max_stale_age_s[c]": {
        "reasoning_snapshot": 5.6,
        "hot_session": 2700,
        "dynamic_config": 0,
        "auth_secret": 0
      },
      "Min_healthy_ratio": null,
      "B_retry_max": 3,
      "min_reserve_retry_rps": 0.0,
      "FD_worker": 132,
      "ulimit_n": 65536,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 6
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 32
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16384
      },
      "T_hold_s(s)": {
        "node_ephemeral": 30
      },
      "SNAT_ips_count(s)": {
        "node_ephemeral": 1
      },
      "HOTPATH_MODULES": [
        "Handler.do_POST",
        "Handler._serve_sse",
        "Handler._serve_json",
        "Handler._run_once",
        "Handler._execute",
        "Run.__init__ (флаг/водяной знак)",
        "Run._pump",
        "источник мышления: _TranscriptTail._run/_read/_emit_record + SQLite-опрос",
        "pure wire-парсер step_payload",
        "append-only выдача мышления",
        "_reasoning_suffix (text_delta)",
        "чтение dynamic_config.json (stat-кэш, раз на ход)"
      ]
    },
    "field_units": {
      "P_steady": "pods",
      "P_hpa_max": "pods",
      "maxSurge_pct": "ratio",
      "maxSurge_abs": "pods",
      "maxUnavailable_pct": "ratio",
      "maxUnavailable_abs": "pods",
      "P_terminating_overlap": "pods",
      "P_live": "pods",
      "P_avail_min": "pods",
      "W": "proc/pod",
      "N_proc": "processes",
      "N_proc_steady": "processes",
      "N_proc_avail_min": "processes",
      "CPU_limit_per_pod": "cores",
      "κ_skew": "ratio",
      "u_bg_worker": "cores",
      "U_pod_sidecars": "cores",
      "Mem_limit_per_pod": "MiB",
      "Mem_rss_worker_max": "MiB",
      "Mem_shared_max": "MiB",
      "RPS_peak": "req/s",
      "A_max": "attempts/req",
      "SLA_p99_s": "s",
      "N_entities_max": "items",
      "Limit_dep_share[d]": "connections",
      "Limit_dep_rps[d]": "req/s",
      "W_fetchers[d]": "proc/pod",
      "J_init_s[d]": "s",
      "J_pod_s[d]": "s",
      "T_poll_s[d]": "s",
      "K_calls[d]": "calls",
      "T_base_s[d]": "s",
      "T_cap_s[d]": "s",
      "Max_stale_age_s[c]": "s",
      "Min_healthy_ratio": "ratio",
      "B_retry_max": "tokens",
      "min_reserve_retry_rps": "req/s",
      "FD_worker": "descriptors",
      "ulimit_n": "descriptors",
      "λ_new_conn_per_pod(s)": "conn/s",
      "C_active_in_scope(s)": "connections",
      "N_pods_in_scope(s)": "pods",
      "Port_range_size(s)": "ports",
      "T_hold_s(s)": "s",
      "SNAT_ips_count(s)": "IPs",
      "HOTPATH_MODULES": "list[str]"
    },
    "field_sources": {
      "P_steady": "F-38: один процесс LaunchAgent (EVD-038)",
      "P_hpa_max": "F-38: автомасштабирования нет",
      "maxSurge_pct": "F-38: KeepAlive, без rolling update",
      "maxSurge_abs": "вычислено ceil(1×0.0)=0",
      "maxUnavailable_pct": "F-38",
      "maxUnavailable_abs": "вычислено floor(1×0.0)=0",
      "P_terminating_overlap": "F-38: рестарт launchctl kickstart, _kill_all при SIGTERM",
      "P_live": "вычислено 1+0+0=1",
      "P_avail_min": "вычислено max(1,1-0)=1",
      "W": "F-51: один процесс /usr/bin/python3",
      "N_proc": "вычислено 1×1",
      "N_proc_steady": "вычислено 1×1",
      "N_proc_avail_min": "вычислено 1×1",
      "CPU_limit_per_pod": "оценка: бюджет демона на рабочей станции (лимита ОС нет)",
      "κ_skew": "один процесс",
      "u_bg_worker": "дизайн: 8 ходов × (опрос транскрипта 0.005 + опрос БД 0.01) ядра; измерение — TC-93 в L2",
      "U_pod_sidecars": "F-05: agy — внешние процессы своей группы, не CPU моста",
      "Mem_limit_per_pod": "оценка: бюджет демона",
      "Mem_rss_worker_max": "F-51: 20 MiB idle + 8 ходов × (буфер транскрипта ≤4 MiB + кэш SQLite 1 MiB + payload/seen ≤3 MiB)",
      "Mem_shared_max": "оценка: -shm WAL-index на соединение (32 KiB×8) + запас",
      "RPS_peak": "F-55: 6 exec в одну секунду (всплеск)",
      "A_max": "F-09: 2 попытки",
      "SLA_p99_s": "F-15: TIMEOUT_S=1800 — потолок хода",
      "N_entities_max": "F-45: сотни шагов на разговор; выборка ограничена LIMIT 4 строк status=8",
      "Limit_dep_share[d]": "conversations_db/transcript_file — бюджет моста на файл (дизайн-учёт, не квота вендора: писатель agy + читатель моста + диагностика + запас); agy_process_slots — MAX_CONCURRENT деплоя 8 (F-38, bulkhead, не пул соединений)",
      "Limit_dep_rps[d]": "дизайн-учёт локального файла (не внешняя квота): ограничивает долю времени, когда читатель держит snapshot; реальный предел — CPU (H-CPU-I5)",
      "W_fetchers[d]": "AD-001: один поток источника на активный ход и на файл",
      "J_init_s[d]": "AD-001: опрос стартует по init своего хода, общего старта нет",
      "J_pod_s[d]": "один процесс",
      "T_poll_s[d]": "AD-001: SQLITE_POLL_S=0.5 (clamp 0.2..2.0); транскрипт 0.05 as-is (F-01)",
      "K_calls[d]": "AD-001: один SELECT на опрос; транскрипт — один stat (+read при росте)",
      "T_base_s[d]": "SQLite — следующий опрос; повтор хода — AD-005 Full Jitter с базой 2.0",
      "T_cap_s[d]": "AD-005: U(0, min(2.0, 2.0·2^(a-1))), A_max=2",
      "Max_stale_age_s[c]": "reasoning_snapshot = 5.1 (F-30) + 0.5 опрос; hot_session = SESSION_IDLE_TTL_S 2700 (F-13); dynamic_config читается каждый ход (0); auth_secret статичен в env до рестарта (0)",
      "Min_healthy_ratio": "N/A: нет пула нод; минимальный источник мышления — транскрипт (N_floor=1)",
      "B_retry_max": "AD-005: процессный bucket 3 токена",
      "min_reserve_retry_rps": "AD-005: 0.0",
      "FD_worker": "F-51: 36 idle + 8 ходов × 8 (3 пайпа, транскрипт, db/-wal/-shm, клиентский сокет) + до 32 ingress сокетов = 132",
      "ulimit_n": "F-54: launchctl limit maxfiles soft 65536",
      "λ_new_conn_per_pod(s)": "F-55: до 6 подключений DSH в секунду по loopback",
      "C_active_in_scope(s)": "EVD-062: max_http_connections=32",
      "N_pods_in_scope(s)": "один процесс на хосте",
      "Port_range_size(s)": "F-54: 49152-65535",
      "T_hold_s(s)": "F-54: TIME_WAIT 2×MSL 15 с",
      "SNAT_ips_count(s)": "loopback, без SNAT",
      "HOTPATH_MODULES": "F-03, F-06, F-07 + AD-001/002/003/004/006"
    },
    "memory_closure_check": {
      "status": "PASS",
      "unit": "MiB",
      "lhs_mib": 128,
      "rhs_mib": 409.6,
      "substitution": "W·Mem_rss_worker_max + Mem_shared_max = 1·96 + 32 = 128 ≤ 0.80·512 = 409.6 MiB; запас 281.6 MiB",
      "evidence_level": "дизайн-оценка; измерено только 20 MiB idle (F-51)"
    },
    "operational_profile": {
      "active_turns_max": 8,
      "code_default_max_concurrent": 4,
      "deployed_max_concurrent": 8,
      "sqlite_connections_max": "8 (≤1 на активный ход, на разные файлы cid)",
      "sqlite_queries_per_s_max": "16 (8 ходов × 2/с) по разным файлам",
      "drain_budget_s": "0.25..0.6 (EOF→stop ≤1.0)",
      "threads_per_turn": "stdin, stderr, pump, источник мышления — без нового потока"
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0-§3.4, §7.2-§7.3",
    "status_semantics": "PASS — проектная замкнутость инварианта для изменяемых путей; runtime-оракул обязателен в L1/L2 (VER-001/002/007/010) и ещё не выполнен. N/A — только отсутствие функции на новом пути с двойным доказательством (git diff + граф вызовов), не waiver. BASELINE_DEBT — унаследованное отклонение, не вносимое и не ухудшаемое этим MR (VER-004/VER-008), вынесено владельцу (Q-005); новое нарушение = FAIL = REJECT",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "substitution": "46/46 канонических ключей с field_units и field_sources; память 1·96+32=128 ≤ 409.6 MiB; N/A-гейты несут na_proof",
        "oracle": "set(required_hl_env_fields)==set(field_units)==set(field_sources)==46 канонических ключей SSoT §3.0; пересчёт неравенства памяти; каждый N/A содержит na_proof",
        "verification_ids": [
          "VER-007",
          "VER-010"
        ],
        "evidence_level": "design; семантические проверки пакета выполнены при сборке"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "conversations_db (на файл): C = N_proc 1 × (G_reload 1 × pool 0 + dedicated 1) = 1 ≤ 0.60×4 = 2.4; transcript_file: 1 ≤ 2.4; G_reload=1 — горячего reload нет, соединение создаётся после bind и закрывается при выходе потока (close-before-create по ходу)",
        "oracle": "AO-04: на ход ровно один sqlite3.connect и один close; после 20 ходов открытых соединений 0",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Новый путь не вводит пулов: одно соединение на ход, ожидания нет (timeout 0.05 с → «изменений нет»). Унаследованный bulkhead _slots — BASELINE_DEBT BD-002",
        "oracle": "AO-04: при блокировке БД опрос возвращается без ожидания сверх timeout, второй connect не создаётся",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ],
        "baseline_debt": "BD-002"
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "fork() нет (Popen exec agy); соединение создаётся в потоке источника своего хода (check_same_thread=True), не в обработчике и не глобально; закрывается в finally",
        "oracle": "AO-04: id соединения один на ход, после выхода потока closed; глобальных соединений нет (VER-009 ast)",
        "verification_ids": [
          "VER-001",
          "VER-009"
        ]
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "Отмена = stop_event (Run.close): поток выходит ≤ SQLITE_POLL_S + timeout 0.05 с и закрывает соединение в finally; join в _pump ограничен",
        "oracle": "AO-04: 50 циклов stop во время опроса → открытых соединений 0, живых потоков источника 0",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "FD 132 ≤ 0.70·65536 = 45875.2; порты 6·1·30 + 32 = 212 ≤ 0.50·(1·16384) = 8192",
        "oracle": "Расчётный тест по HL-ENV (AO-04 считает FD хода: +3 на SQLite и закрытие всех)",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Холодный старт моста не запускает поллеров (W_fetchers при t=0 равно 0); поллер стартует по init своего хода и опрашивает свой файл: λ_fetch на файл = 1, B = K·(λ+4√λ+4) = 1·(1+4+4) = 9 ≤ 0.50·20 = 10; R_poll = 1·1·1/0.5 = 2 ≤ 0.20·20 = 4 (БД), транскрипт 1/0.05 = 20 ≤ 0.20·200 = 40. Limit_dep_rps — дизайн-учёт локального файла, не внешняя квота",
        "oracle": "Расчётный тест по HL-ENV; AO-05 счётчик запросов на опрос == 1",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Пауза повтора хода — Full Jitter U(0, min(2.0, 2.0·2^(a-1))) через инъецируемый RNG (AD-005). Пересев CSPRNG после fork и джиттер периодического поллера неприменимы: fork() нет, каждый поллер опрашивает свой локальный файл без общей зависимости",
        "oracle": "AO-02: инъецированный RNG u∈{0.0,0.5,1.0} → паузы ровно {0.0,1.0,2.0} с",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "S-HERD-I3": {
        "status": "PASS",
        "substitution": "Аналог conditional fetch: неизменная length(step_payload) → парсер не вызывается (call_count==0), seen[key] тот же объект",
        "oracle": "AO-05: 10 опросов неизменной строки → parser.call_count == 1",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "S-HERD-I4": {
        "status": "N/A",
        "reason": "TTL-кэшей с сетевым дозапросом нет; на файл ровно один поллер-владелец (поток своего хода) — singleflight не нужен. Классификация ошибок соблюдена: ошибки открытия/блокировки не кэшируются (повтор на следующем опросе), детерминированные схемные ошибки выключают источник на ход и учитываются breaker'ом",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-001",
          "VER-009"
        ]
      },
      "S-HERD-I5": {
        "status": "N/A",
        "reason": "Нет снапшота Control Plane/readiness-зависимости: /health не меняется; staleness мышления ≤5.6 с; секрет статичен в env",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-001",
          "VER-006"
        ]
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "PASS",
        "substitution": "Нет routing Snapshot; выборка по индексу step_type + диапазону PK idx с LIMIT 4; seen — dict O(1) по ключу шага",
        "oracle": "AO-05: число запросов и вызовов парсера на опрос не растёт с числом строк steps (100 → 1000)",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "Regex cid и SQL — константы модуля; dynamic_config.json парсится только при смене (mtime_ns,size); парсер на memoryview без копий; deepcopy/pydantic нет",
        "oracle": "AO-05: при неизменном dynamic_config.json json.loads.call_count == 1 на 10 ходов; re.compile в цикле опроса не вызывается",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Первая инструкция SQLite-пути — if not sqlite_enabled: return; при выключенном флаге sqlite3.connect и парсер не вызываются; логи источника ограничены (одна строка ошибки открытия на ход)",
        "oracle": "TC-91: флаг выкл → connect.call_count == 0, parser.call_count == 0",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "H-CPU-I4": {
        "status": "N/A",
        "reason": "asyncio/event loop и горячего reload Snapshot нет: ThreadingHTTPServer + потоки; разбор payload ≤40 KB идёт в потоке источника своего хода",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-009"
        ]
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "t_req_total = 0.010 + 2·0.005 = 0.020 CPU-s (оценка); Util_worker = 1.0·6·0.020/(1·1) + 0.12 = 0.24 ≤ 0.70; Pod = 1·0.24 + 0 = 0.24 ≤ 0.80·2.0 = 1.6; Feature: для долгоживущих потоковых ходов RPS·Δt = N_active·u_poll (закон Литтла) = 8·0.01 = 0.08 ≤ 0.05·(1·2.0) = 0.10",
        "oracle": "Расчётный тест по HL-ENV + L2 TC-93 измеряет ≤1% ядра на ход",
        "verification_ids": [
          "VER-007",
          "VER-010"
        ]
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "Изменяемый критический путь: T_crit_aux(a) = водяной знак resumed 0.1 + drain 0.6 + 0.05 + 0.15 + 0.05 = 0.95 с; T_backoff(1) ≤ 2.0 с; Σ по A_max=2: 2·0.95 + 2.0 = 3.9 с ≤ 0.30·1800 = 540 с; при deadline-remaining ≤ 0 повтор не стартует (as-is TIMEOUT_S). Унаследованное ожидание слота QUEUE_TIMEOUT_S (900 код / 1800 деплой) — BASELINE_DEBT BD-001",
        "oracle": "AO-03: на FakeClock drain завершается не позже DRAIN_MAX_S, join ограничен; статический пересчёт неравенства",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ],
        "baseline_debt": "BD-001"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "Процессный token-bucket: capacity 3, +0.2 на первичный, reserve 0 → N_retries ≤ floor(0.2·N_req) + 3. Bulkhead-семафор _slots унаследован (ожидание вместо мгновенного fallback) — BASELINE_DEBT BD-002",
        "oracle": "AO-02: 100 падающих запросов → повторов ≤ 23",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ],
        "baseline_debt": "BD-002"
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Fail-open: SQLite и транскрипт; fail-closed: Bearer-авторизация (as-is). SQLite breaker: K=3 подряд хода со схемной ошибкой/divergence → OPEN на 600·U(0.8,1.2) с без connect (0 с), затем HALF_OPEN ровно один пробный ход",
        "oracle": "AO-01: после 3 сбоев connect.call_count не растёт; после сдвига FakeClock 10 одновременных ходов → ровно 1 пробный connect",
        "verification_ids": [
          "VER-001",
          "VER-007"
        ]
      },
      "R-BULK-I4": {
        "status": "N/A",
        "reason": "Нет пула нод/карантина/Panic-Open: единственный апстрим agy. Аналог N_floor=1 соблюдён: транскрипт никогда не выключается, выключается только вспомогательный SQLite",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-001"
        ]
      },
      "R-BULK-I5": {
        "status": "N/A",
        "reason": "Нет прокси-нод и доменных origin: разделять origin_health и node_health нечего",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
          "current_git_diff_output": "",
          "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
          "git_diff_files": [
            "bridges/agy-bridge/server.py",
            "tests/test_agy_bridge_resilience.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
          "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
        },
        "verification_ids": [
          "VER-001"
        ]
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Поток источника живёт не дольше хода: выход при stop_event сразу, при _proc_done — после drain ≤0.6 с, без bind — сразу по _proc_done; соединение SQLite закрывается в finally; _pump ждёт поток с бюджетом; Run.close зачищает группу as-is",
      "oracle": "AO-04: 20 ходов → threading.active_count() возвращается к исходному, открытых соединений 0",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Одна строка done model=… state=… на каждом выходе _run_once (включая no slot и launcher_unavailable) с полями rc, conversation, turns, tool_events, out_bytes, wall_s, err + reasoning_chunks, sqlite=on|off|breaker|open_fail, sqlite_emits, drain_ms, retries, retry_tokens",
      "oracle": "AO-06: перехват _log на всех ветках выхода → ровно одна строка done с обязательными полями",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    "M_SEM_v1": {
      "status": "PASS",
      "substitution": "Семантическая изоляция классов горячих сессий: допустимое множество для claim исключает чужой класс (agentic ≠ plain), one-shot не участвует; новых пулов нет (_slots общий as-is)",
      "oracle": "TC-80..TC-82",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ]
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "conversations/<cid>.db SELECT (live)",
        "path": "bg (поток источника хода)",
        "timeout_budget": "connect/execute timeout 0.05 с; период 0.5 с",
        "bulkhead": "1 соединение на ход, ≤8 на процесс",
        "circuit_breaker": "K=3 ходов / 600·U(0.8,1.2) с / HALF_OPEN=1 ход",
        "failure_mode_fallback": "Fail-Open: «изменений нет», мышление из транскрипта"
      },
      {
        "dependency_operation": "conversations/<cid>.db водяной знак resumed (immutable)",
        "path": "control (до spawn)",
        "timeout_budget": "≤0.1 с",
        "bulkhead": "1 открытие на resumed-ход",
        "circuit_breaker": "общий SQLite breaker",
        "failure_mode_fallback": "Fail-Open: base_idx=None → выборка только status=8"
      },
      {
        "dependency_operation": "transcript_full.jsonl stat/read",
        "path": "bg",
        "timeout_budget": "локальный read ≤4 MiB за проход; период 0.05 с",
        "bulkhead": "1 читатель на ход",
        "circuit_breaker": "нет (минимальный источник, N_floor)",
        "failure_mode_fallback": "Fail-Open: «мышления нет» (as-is)"
      },
      {
        "dependency_operation": "финальный drain источников",
        "path": "hot (между EOF и done)",
        "timeout_budget": "0.25..0.6 с + join 0.15 с",
        "bulkhead": "поток своего хода",
        "circuit_breaker": "n/a (жёсткий deadline)",
        "failure_mode_fallback": "по deadline — done; поздние события → лог reasoning-late-drop"
      },
      {
        "dependency_operation": "процесс agy (spawn, stdout)",
        "path": "hot",
        "timeout_budget": "FIRST_TOKEN 120 с, idle 300 с, TIMEOUT 1800 с (as-is)",
        "bulkhead": "_slots MAX_CONCURRENT (as-is, BD-002)",
        "circuit_breaker": "retry budget 3 токена + Full Jitter (AD-005)",
        "failure_mode_fallback": "до выдачи — один повтор при наличии токена; после выдачи — data:{error}+[DONE]"
      },
      {
        "dependency_operation": "dynamic_config.json",
        "path": "control (раз на ход)",
        "timeout_budget": "stat + json.loads только при смене",
        "bulkhead": "n/a",
        "circuit_breaker": "n/a",
        "failure_mode_fallback": "Fail-Closed для фичи: нет/битый файл → флаг false (поведение as-is)"
      }
    ],
    "baseline_debt": [
      {
        "id": "BD-001",
        "code": "R-BULK-I1",
        "fact": "Ожидание слота _acquire_slot до QUEUE_TIMEOUT_S 900 с (код) / 1800 с (деплой) > 0.30·1800 = 540 с",
        "evidence_ids": [
          "EVD-063",
          "EVD-038"
        ],
        "delta_effect": "не меняется (VER-008 + AO-03 не трогают _acquire_slot)"
      },
      {
        "id": "BD-002",
        "code": "C-MULT-I2 / R-BULK-I2",
        "fact": "_slots BoundedSemaphore(M) с ожидающими до 32−M (деплой 24 > 2·8; код 28 > 2·4), ожидание вместо мгновенного fallback",
        "evidence_ids": [
          "EVD-062",
          "EVD-063"
        ],
        "delta_effect": "не меняется"
      },
      {
        "id": "BD-003",
        "code": "канон gate basedpyright",
        "fact": "12 ошибок basedpyright на baseline в target-файлах",
        "evidence_ids": [
          "EVD-060"
        ],
        "delta_effect": "рост запрещён по каждой паре (VER-004)"
      },
      {
        "id": "BD-004",
        "code": "UNBOUNDED_QUEUE",
        "fact": "Run.q = queue.Queue() без maxsize",
        "evidence_ids": [
          "EVD-057"
        ],
        "delta_effect": "новые события мышления ограничены длиной финального thinking (сумма дельт ≤ финального текста), без амплификации"
      }
    ],
    "non_waivable_stop_codes": [
      "HL-ENV-01",
      "C-MULT-I1",
      "C-MULT-I2",
      "C-MULT-I3",
      "C-MULT-I4",
      "C-MULT-I5",
      "S-HERD-I1",
      "S-HERD-I2",
      "S-HERD-I3",
      "S-HERD-I4",
      "S-HERD-I5",
      "H-CPU-I1",
      "H-CPU-I2",
      "H-CPU-I3",
      "H-CPU-I4",
      "H-CPU-I5",
      "R-BULK-I1",
      "R-BULK-I2",
      "R-BULK-I3",
      "R-BULK-I4",
      "R-BULK-I5",
      "T-LIFE/v1",
      "O-EXIT/v1",
      "M-SEM/v1"
    ],
    "summary": {
      "PASS": 19,
      "N/A": 5,
      "FAIL": 0,
      "BASELINE_DEBT_refs": [
        "BD-001",
        "BD-002"
      ],
      "meaning": "проектные инварианты; runtime-оракулы L1/L2 и L3 ещё не выполнены"
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "DAG: Handler → _run_once → Run → {_pump, источник мышления → парсер}; парсер и стор без обратных зависимостей",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Источник не пишет в сокет, Handler не читает файлы agy; парсер без I/O",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ],
      "evidence_level": "design; L1 required"
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "SQLite-опрос и парсер — отдельные единицы рядом с _TranscriptTail; Handler не расширяется ветвлениями источников. Размер server.py унаследован",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Оба источника сводятся к кортежу ('reasoning', str) в Run.q — граница F-03/F-06/F-07",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит прежние SSE/JSON; внутренние idx/status/payload наружу не уходят",
      "verification_ids": [
        "VER-001",
        "VER-006"
      ],
      "evidence_level": "design; L1 required"
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "SQLite timeout 0.05 с, водяной знак ≤0.1 с, drain ≤0.6 с, join ≤0.75 с; остальные таймауты as-is",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "A_max=2 и процессный bucket 3 токена; SQLite-опрос — фиксированный период, без циклов повторов",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "Retry budget + Full Jitter; после выдачи повторов нет",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "Поллеры по ходам на разные файлы, старт по init; общего опрашиваемого ресурса нет",
      "verification_ids": [
        "VER-010"
      ],
      "evidence_level": "design; L2 required"
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "Run.q без maxsize унаследована (BD-004); новые события ограничены длиной финального мышления, без амплификации",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Ingress 32 соединения, слоты MAX_CONCURRENT (as-is); источник не опережает писателя — опрос 0.5 с",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не используется: ThreadingHTTPServer и потоки",
      "verification_ids": [
        "VER-009"
      ],
      "evidence_level": "design",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only e00da0621fc95f7c63cd1565f4a5d1fd490c8d66 -- bridges/agy-bridge tests/test_agy_bridge_resilience.py",
        "current_git_diff_output": "",
        "current_product_fingerprint": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
        "git_diff_files": [
          "bridges/agy-bridge/server.py",
          "tests/test_agy_bridge_resilience.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {_serve_sse, _serve_json} -> _run_once -> {_acquire_slot, Run.__init__ -> {_launcher, Popen, источник мышления.start}, _execute -> Run.q, Run.close -> _kill_group}; Run._pump -> {Run.q, источник.bind/join}; источник мышления -> {transcript stat/read -> _emit_record, sqlite3.connect(mode=ro) -> SELECT steps -> wire-парсер -> append-only выдача -> emit}. Нет вызовов asyncio, fork, HTTP-клиентов, Redis/PG/Vault/Control Plane, TTL-кэшей с дозапросом, пулов нод/карантина/origin health; /health не зависит от SQLite",
        "future_diff_gate": "Текущий пустой diff доказывает read-only Stage 2, а не отсутствие будущих вызовов: VER-009 (ast импорты/connect/URI), VER-008 (allowlist файлов) и VER-001/VER-007 (AO-оракулы) повторно подтверждают N/A на диффе кандидата до ARCH-приёмки кода"
      }
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Опрос со sleep периода, ожидания через Event.wait/join с таймаутом; busy-loop нет",
      "verification_ids": [
        "VER-001",
        "VER-010"
      ],
      "evidence_level": "design; L1/L2 required"
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "Соединение SQLite закрывается в finally потока; файлы транскрипта открываются через with; поток завершается по stop/drain",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "Новых подпроцессов нет; _kill_group с reap лидера as-is",
      "verification_ids": [
        "VER-001"
      ],
      "evidence_level": "design; L1 required"
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "seen — единственный писатель (поток источника); порядок reasoning→done через FIFO и join; стор под замком; поздние emit после drain_closed логируются",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Повтор хода только до выдачи (text/tool_calls/потоковое reasoning); после — кадр ошибки",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Эндпоинты, порт, форма чанков и флаги agy неизменны; поведенческие дельты CD-001..CD-005 разрешены текущими REQ",
      "verification_ids": [
        "VER-001",
        "VER-005",
        "VER-006"
      ],
      "evidence_level": "design; L1 required"
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Drain до done; поздние события и divergence логируются; fail-open не теряет транскрипт",
      "verification_ids": [
        "VER-001",
        "VER-010"
      ],
      "evidence_level": "design; L1/L2 required"
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Ошибки sqlite3/парсера поглощаются с классом в логе; ошибки agy — as-is классификатор и кадр ошибки",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ],
      "evidence_level": "design; L1 required"
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "Новых секретов нет; ключ только из env; в логах без текста и токенов",
      "verification_ids": [
        "VER-001",
        "VER-007"
      ],
      "evidence_level": "design; L1 required"
    }
  },
  "status_protocol_examples": {
    "client_status_messages": "Мост не добавляет synthetic status-текст в поток (REQ-010: текст модели не модифицируется); примеры ниже — протокол статусов гейта для оркестратора/Teamlead",
    "gate_pass": "ARCH_GATE: PASS packet=architecture/architecture-packet.json stop_codes=21/21 (PASS 16, N/A 5, FAIL 0) + T-LIFE/O-EXIT/M-SEM PASS",
    "gate_blocked": "ARCH_GATE: BLOCKED ARCH_STOP_<код> — <инвариант>: <факт>; вердикт REJECT до исправления, техдолг не допускается",
    "stop_codes": {
      "ARCH_STOP_HL_ENV_01": {
        "code": "HL-ENV-01",
        "trigger": "нет любого из 46 полей, неравенство памяти нарушено или N/A без двойного доказательства",
        "example": "BLOCKED ARCH_STOP_HL_ENV_01 missing field T_poll_s[d]",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I1": {
        "code": "C-MULT-I1",
        "trigger": "C_dep(d) > 0.60·Limit_dep_share[d]",
        "example": "BLOCKED ARCH_STOP_C_MULT_I1 conversations_db C=3 > 2.4",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I2": {
        "code": "C-MULT-I2",
        "trigger": "пул без жёсткого предела/таймаута ожидания или max_waiters > 2M в новом коде",
        "example": "BLOCKED ARCH_STOP_C_MULT_I2 sqlite connect waits unbounded",
        "current": "PASS (BD-002 унаследован)"
      },
      "ARCH_STOP_C_MULT_I3": {
        "code": "C-MULT-I3",
        "trigger": "соединение создаётся глобально/в обработчике или до fork",
        "example": "BLOCKED ARCH_STOP_C_MULT_I3 module-level sqlite3.connect",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I4": {
        "code": "C-MULT-I4",
        "trigger": "stop/отмена оставляет открытое соединение или живой поток",
        "example": "BLOCKED ARCH_STOP_C_MULT_I4 open connections after close = 1",
        "current": "PASS"
      },
      "ARCH_STOP_C_MULT_I5": {
        "code": "C-MULT-I5",
        "trigger": "FD > 0.70·ulimit_n или порты > 50%",
        "example": "BLOCKED ARCH_STOP_C_MULT_I5 FD 50000 > 45875",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I1": {
        "code": "S-HERD-I1",
        "trigger": "пачечный залп или стационарный опрос выше 50%/20% лимита",
        "example": "BLOCKED ARCH_STOP_S_HERD_I1 R_poll 8 > 4 q/s",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I2": {
        "code": "S-HERD-I2",
        "trigger": "фиксированная пауза повтора без jitter / неинъецируемый RNG",
        "example": "BLOCKED ARCH_STOP_S_HERD_I2 retry sleep fixed 2s",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I3": {
        "code": "S-HERD-I3",
        "trigger": "повторный парсинг неизменных данных",
        "example": "BLOCKED ARCH_STOP_S_HERD_I3 parser.call_count 10 on unchanged row",
        "current": "PASS"
      },
      "ARCH_STOP_S_HERD_I4": {
        "code": "S-HERD-I4",
        "trigger": "появился TTL-кэш с дозапросом без singleflight или негативный кэш транзиентных ошибок",
        "example": "BLOCKED ARCH_STOP_S_HERD_I4 open-fail cached for turn",
        "current": "N/A"
      },
      "ARCH_STOP_S_HERD_I5": {
        "code": "S-HERD-I5",
        "trigger": "появилась readiness-зависимость от снапшота без политики staleness",
        "example": "BLOCKED ARCH_STOP_S_HERD_I5 /health depends on sqlite",
        "current": "N/A"
      },
      "ARCH_STOP_H_CPU_I1": {
        "code": "H-CPU-I1",
        "trigger": "линейный рост работы опроса с числом строк steps",
        "example": "BLOCKED ARCH_STOP_H_CPU_I1 full table scan per poll",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I2": {
        "code": "H-CPU-I2",
        "trigger": "re.compile/json.loads конфига/deepcopy на горячем пути",
        "example": "BLOCKED ARCH_STOP_H_CPU_I2 json.loads dynamic_config per chunk",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I3": {
        "code": "H-CPU-I3",
        "trigger": "выключенный флаг не даёт нулевую стоимость",
        "example": "BLOCKED ARCH_STOP_H_CPU_I3 connect called with flag off",
        "current": "PASS"
      },
      "ARCH_STOP_H_CPU_I4": {
        "code": "H-CPU-I4",
        "trigger": "появился event loop/reload-путь с блокировкой > 2 мс",
        "example": "BLOCKED ARCH_STOP_H_CPU_I4 asyncio loop blocked by parser",
        "current": "N/A"
      },
      "ARCH_STOP_H_CPU_I5": {
        "code": "H-CPU-I5",
        "trigger": "нарушено любое из трёх неравенств CPU",
        "example": "BLOCKED ARCH_STOP_H_CPU_I5 feature 0.16 > 0.10 cores",
        "current": "PASS"
      },
      "ARCH_STOP_R_BULK_I1": {
        "code": "R-BULK-I1",
        "trigger": "Σ вспомогательных ожиданий изменяемого пути > 0.30·SLA или drain без deadline",
        "example": "BLOCKED ARCH_STOP_R_BULK_I1 drain unbounded",
        "current": "PASS (BD-001 унаследован)"
      },
      "ARCH_STOP_R_BULK_I2": {
        "code": "R-BULK-I2",
        "trigger": "повторы без процессного бюджета",
        "example": "BLOCKED ARCH_STOP_R_BULK_I2 retries 100 > 23",
        "current": "PASS (BD-002 унаследован)"
      },
      "ARCH_STOP_R_BULK_I3": {
        "code": "R-BULK-I3",
        "trigger": "нет breaker/HALF_OPEN>1 или fail-closed вспомогательной зависимости",
        "example": "BLOCKED ARCH_STOP_R_BULK_I3 half-open probes 10",
        "current": "PASS"
      },
      "ARCH_STOP_R_BULK_I4": {
        "code": "R-BULK-I4",
        "trigger": "появился пул нод с карантином без post-eviction предиката",
        "example": "BLOCKED ARCH_STOP_R_BULK_I4 transcript source disabled",
        "current": "N/A"
      },
      "ARCH_STOP_R_BULK_I5": {
        "code": "R-BULK-I5",
        "trigger": "появились прокси-ноды без разделения origin/node health",
        "example": "BLOCKED ARCH_STOP_R_BULK_I5 node marked bad for origin error",
        "current": "N/A"
      }
    }
  },
  "architect_oracles": {
    "AO-01": "SQLite breaker: 3 подряд схемных сбоя → OPEN, connect не вызывается; после сдвига FakeClock на 600·U(0.8,1.2) с — ровно один пробный ход; успех → CLOSED, сбой → OPEN; divergence → сразу OPEN",
    "AO-02": "Retry budget и Full Jitter: 100 падающих запросов → повторов ≤ floor(0.2·100)+3 = 23; RNG u∈{0,0.5,1} → паузы {0.0,1.0,2.0} с; hot→cold fallback тратит токен",
    "AO-03": "Drain: на FakeClock/инъецированных часах поток источника завершает drain не позже DRAIN_MAX_S, ранний выход после DRAIN_MIN_S при полноте; _pump ставит done после join; emit после drain_closed → лог reasoning-late-drop, в очередь не попадает",
    "AO-04": "T-LIFE/C-MULT: на ход один sqlite3.connect и один close; stop во время опроса → поток завершён и соединение закрыто; 20 ходов → active_count и открытые соединения возвращаются к исходным",
    "AO-05": "H-CPU/S-HERD: один SELECT на опрос; неизменная length → парсер не вызывается; dynamic_config.json парсится один раз при неизменном stat",
    "AO-06": "O-EXIT: ровно одна строка done с обязательными полями на каждой ветке выхода _run_once (done, agy_error, pump_error, client_gone, timeout, no slot, launcher_unavailable)",
    "AO-07": "Путь БД: cid с ../, /, пустой или не по regex → connect не вызывается; resolved parent == CONV_DIR",
    "AO-08": "Только чтение: все URI connect начинаются с file: и содержат mode=ro; immutable=1 только для водяного знака до spawn и после выхода процесса; явных BEGIN нет"
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46: ключи required_hl_env_fields == field_units == field_sources == таблица SSoT §3.0 (распарсена из architecture.md)",
    "memory_closure": "1·96+32=128 ≤ 409.6 MiB",
    "stop_codes": "21 канонических кодов в resilience_gates ({'PASS': 16, 'N/A': 5}) + T-LIFE/O-EXIT/M-SEM; status_protocol_examples.stop_codes: 21 ARCH_STOP_* биективно",
    "legacy_antipatterns": "21 ключ в порядке эталонной схемы",
    "verification_owner": "{'Verifier': 5, 'Teamlead': 6}; Coder не владеет ни одной проверкой",
    "decisions": "6 решений, все two-way, ≥2 альтернатив, approval_required=false",
    "evidence_refs": "72 EVD (56 фактов аналитика F-01..F-56 + 16 собственных архитектора); все verification_ids/evidence_ids разрешаются",
    "na_proof": "каждый N/A несёт git diff (пустой на Stage 2), fingerprint и транзитивный граф вызовов",
    "schema_vs_semantics": "Установленный validate_architecture_packet.py не проверяет high_load_envelope/resilience_gates/legacy/status_protocol — эти проверки выполнены сборочным скриптом архитектора; ни схема, ни дизайн-проверки не доказывают runtime PASS"
  },
  "handoff_state": {
    "next_role": "Orchestrator → downstream Архитектурный Совет (route-manifest downstream_panel=true) → Coder (claude-cli/codex-cli по route-manifest) только после ARCH_GATE_PASS",
    "coder_must_read": [
      "architecture/architecture-packet.json",
      "analysis/agy-realtime-reasoning/handoff-qa.md (TC-кейсы)",
      "teamlead/verification-surface.json"
    ],
    "red_green": "Регрессионные тесты TC/AO пишутся до фикса и красные на e00da06 (VER-007 MISSING на baseline — EVD-072)"
  }
}
ARTIFACT_END>>>

<<<ARTIFACT .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/receipts/arch-gate.json sha256=b64f7ccdd765ff1ab13399b58267132cc715990e0a9c3ee925ebac9c90813953
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "criticality": "S2",
  "packet_sha256": "f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4",
  "verification_surface_sha256": "bfdda127ad86e2497f8bab40790015668e3196ae033677cf181d4a9dfc5eeab4",
  "protected_paths_sha256": "388ccd7b2843e8f7719d7ed0c552e9fc6365604834adb3ea8181c6020892f498",
  "architect_worktree_sha256": "aed3274571859b39f08788443955470300be30a9dfd8ea5d0e994001433a0bbb",
  "materialized_targets": 0
}
ARTIFACT_END>>>

КОНТЕКСТ:
Ниже приложены целиком формулировка цели владельца (`goal.md`), конверт задачи (`task.json`), полный аналитический пакет этапа 1 (`handoff-architect.md`, `evidence-ledger.md`, `research-plan.md`, `open-questions.md`, `handoff-qa.md`), а также стандарты проекта и Python-архитектуры (`aisdlc-gcge/AGENTS.md`, `aisdlc-gcge/skills/architecture.md`, `aisdlc-gcge/agents/scope-and-contracts.md`), соблюдение которых (включая все пункты `Definition of Done overlay` и все 5 групп Highload & Resilience гейтов `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`) входит в твои обязательные проверки:

<<<ARTIFACT /tmp/cel-runs/analyst-teamlead-agy-reasoning-20261029/goal.md sha256=89f0ce1d33cdf7c68e9d7f319cfd6c19de77a08368d63b6687203d79a7f98435
# Цель: analyst-teamlead-agy-reasoning-20261029

- **Задача:** Реализовать по пресету `analyst-teamlead` (S2) реалтайм-стриминг размышлений (`reasoning_content`) в `bridges/agy-bridge/server.py` из SQLite `~/.gemini/antigravity-cli/conversations/<cid>.db` (`steps.step_payload` protobuf field `20.3`) во время генерации, синхронизировать финальное дренирование `_TranscriptTail` с `Run._pump`, сохранить отданный `reasoning` во флаге `delivered` при mid-turn ошибках и изолировать `sess_key` от фоновых запросов без инструментов; провести через Совет Тимлидов (`ARCH_PANEL` и `COUNCIL`), влить MR в `dev` и `main`, задеплоить в `~/.dsh/bridges/agy-bridge/server.py` (`:9887`) и проверить тяжёлым путём L3.
- **Терминальный критерий:**
  1. `SA-DOD-001..008 PASS` на `analysis/agy-realtime-reasoning/`.
  2. `ARCH_GATE PASS` + `ARCH_PANEL PASS` (`verify_panel_proof.py exit=0`).
  3. `CODE_GATE PASS` + `Verifier / FINAL_GATE PASS` + `Clean-room L2 PASS`.
  4. `COUNCIL ACCEPT` (`verify_panel_proof.py exit=0`, `pol-receipt/1`).
  5. Remote-first MR открыт и влит в `origin/dev`, затем `dev -> main` влит в `origin/main`, локальный checkout синхронизирован (`git pull --ff-only`).
  6. Обновлённый `bridges/agy-bridge/server.py` задеплоен в `~/.dsh/bridges/agy-bridge/server.py`, сервис `:9887` перезапущен и проверен живым SSE-запросом к `gemini-4-argon` (`reasoning_effort=high`) с реальным стримингом чанков `reasoning_content` во время фазы размышления.
ARTIFACT_END>>>

<<<ARTIFACT .ai-team/runs/analyst-teamlead-agy-reasoning-20261029/task.json sha256=288d4aecc5c0a52a88367cde5bda624e59c51517d46ecbc612c64a04283fde19
{
  "task_id": "agy-realtime-reasoning",
  "run_id": "analyst-teamlead-agy-reasoning-20261029",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "downstream_panel": true,
  "reviewer_skip": true,
  "parent_skill": "analyst-teamlead",
  "goal": "Реалтайм-стриминг размышлений (reasoning_content) в agy-bridge (:9887) из SQLite ~/.gemini/antigravity-cli/conversations/<cid>.db (steps.step_payload protobuf 20.3) во время генерации, синхронизация финального дренирования _TranscriptTail с Run._pump, сохранение отданного reasoning при mid-turn ошибках и изоляция sess_key от фоновых запросов без инструментов.",
  "target_files": [
    "bridges/agy-bridge/server.py",
    "tests/test_agy_bridge_resilience.py"
  ],
  "architecture_gate": {
    "packet_sha256": "f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4",
    "verification_surface_sha256": "bfdda127ad86e2497f8bab40790015668e3196ae033677cf181d4a9dfc5eeab4",
    "protected_paths_sha256": "388ccd7b2843e8f7719d7ed0c552e9fc6365604834adb3ea8181c6020892f498"
  }
}
ARTIFACT_END>>>

<<<ARTIFACT analysis/agy-realtime-reasoning/handoff-architect.md sha256=cb1ecde9e00f06d72b75e43f973add3ab93ca27433d7145cbf8ec4f4800b17cd
# Handoff to Architect: реалтайм-размышление `agy-bridge` (:9887) для `gemini-4-argon` (agy-realtime-reasoning)

Дата: 2026-10-29 (MSK). Автор: System Analyst (Stage 1, preset `analyst-teamlead`). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — `evidence-ledger.md` (`F-01..F-56`), вопросы — `open-questions.md` (`OPEN-01..OPEN-16`, блокеров нет), план — `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: при работе `gemini-4-argon` (agy 1.4.9) через `agy-bridge` в DSH фаза размышления длится 15-45+ с, и всё это время UI пуст
(«висит как будто бы не работает»). Нужно видеть размышление в реальном времени, по мере генерации.

Подтверждены четыре причины. RC-1 определяет, есть ли реалтайм вообще; RC-2..RC-4 ломают уже существующую выдачу мышления.

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | Нет live-источника мышления на текущем пути. Stdout `stream-json` 1.4.9 не сериализует `thinking`/`thinking_delta` и молчит всю фазу мышления; `transcript_full.jsonl`, который опрашивает `_TranscriptTail`, получает запись `PLANNER_RESPONSE` только после завершения шага. При этом SQLite `~/.gemini/antigravity-cli/conversations/<cid>.db` (таблица `steps`, `step_type=15`, `status=8`) обновляется каждые 1.5-5.1 с, а подполе 20.3 `step_payload` содержит накопленное мышление | F-27, F-28, F-29, F-30, F-32, F-33, F-01, F-02, F-44 |
| RC-2 | Гонка финального дренирования. `Run._pump` после EOF ждёт 0.05 с и ставит `("done")`; `_execute` выходит по `done` немедленно, а `_TranscriptTail` после `done_event` спит 0.4 с и только потом дочитывает файл; событие, положенное в очередь после выхода `_execute`, никто не читает. Запись последнего шага ложится в транскрипт на 90 мс позже `result`. В логе 6 из 28 одношаговых ходов argon завершились без единого куска мышления, 5 `tail-emit` не дошли до `reasoning-emit` | F-06, F-07, F-08, F-02, F-29, F-40, F-43 |
| RC-3 | `delivered = bool(text or tool_calls)` не учитывает уже отданное клиенту мышление (`tool_calls` всегда пуст). После сбоя на следующем шаге мост выполняет невидимый повтор поверх отданного `reasoning_content` либо шлёт кадр `error` после него | F-09, F-10, F-11, F-46, F-47 |
| RC-4 | `sess_key = (model_id, cwd, effort)` не различает основной агентный диалог (`tools>0`) и фоновый запрос DSH без инструментов (генерация заголовка: `tools=0`, промпт 0.5-0.7 KB, `effort_source=default`), которые приходят в ту же секунду. Фоновый запрос либо забирает горячую сессию основного диалога и дописывает в неё свой ход, либо стартует холодным и перезаписывает запись `_session_store` своим `cid`, после чего следующий ход основного диалога продолжает чужой разговор | F-12, F-13, F-14, F-41, F-42 |

Цепочка следствий: RC-1 даёт пустой экран на 15-45 с даже на здоровом ходе, а мышление приходит одним куском в конце (F-44); RC-2 иногда
теряет и этот кусок; RC-3 портит уже показанное мышление при сбое квоты (F-46); RC-4 подменяет контекст диалога при параллельном фоновом
запросе. Реалтайм-источник без исправления RC-2..RC-4 проблему владельца не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (stream:true) --HTTP SSE--> Handler.do_POST (:9887)                                       F-38, F-39
  do_POST: sess_key=(model,cwd,effort) -> _session_claim -> ctx                               F-12, F-13
  _serve_sse: 200 + role-chunk -> _run_once -> _execute                                       F-11
  _run_once: attempt 1..2, delivered=text/tool_calls, hot->cold fallback                      F-09, F-10
  Run: launcher agy-cli.sh --input-format/--output-format stream-json (new pgid)              F-05
    stdout NDJSON -> _pump: init->bind(cid); agent_response.text_delta->("text");
                            result->("result"); EOF -> sleep 0.05 -> ("done")                 F-06, F-18
    _TranscriptTail: poll 0.05 s transcript_full.jsonl -> PLANNER_RESPONSE.thinking
                     -> _reasoning_suffix -> ("reasoning"); on done: sleep 0.4 -> 1 read      F-01, F-02, F-03, F-04
  _execute: q.get(1.0) -> on_reasoning/on_text -> SSE delta; "done" -> return               F-07, F-08, F-17
  keepalive ": keepalive" каждые 15 с тишины (невидим в UI)                                   F-16, F-15
agy 1.4.9 (вне моста):
  stdout: init ... [тишина всю фазу мышления] ... agent_response text_delta ... result         F-27, F-28, F-29
  transcript_full.jsonl: запись шага только после DONE, +90 мс после result                   F-29, F-36
  conversations/<cid>.db (WAL): steps(idx, step_type=15, status=8 -> 3, step_payload 20.3)   F-30, F-31, F-32, F-34
```

Граница совместимости (факт): всё, что выше очереди `Run.q`, оперирует кортежами `("reasoning", текст)`, `("text", текст)`, `("done", ...)`
(F-03, F-06, F-07). Любой новый источник, сводимый к тем же кортежам, не требует правки SSE-кадрирования и контракта клиента.

## 3. Верифицируемые требования

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие измеримые формулировки (полная матрица проверок — `handoff-qa.md`).
Пороги отзывчивости — рабочие допущения из `open-questions.md` (вопрос о числовых целях), до ответа владельца.

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Мышление шага в фазе генерации (`step_type=15`, `status=8`) уходит клиенту дельтами `delta.reasoning_content` по мере роста подполя 20.3, до завершения шага | F-30, F-32, F-27, F-29 | AC-001: при фикстуре БД, в которой подполе 20.3 растёт каждые 1.5 с, клиент получает не меньше 2 чанков мышления до перехода шага в `status=3`; AC-002: задержка от записи снимка в БД до записи чанка в сокет не больше периода опроса плюс 0.5 с |
| REQ-002 | MUST | Разбор `step_payload` выполняется на стандартной библиотеке Python 3.9 (без новых зависимостей): поле 20 корневого сообщения, подполе 3 как UTF-8; неизвестные поля и wire types 0/1/2/5 пропускаются; усечённый или битый payload не роняет поток и не даёт исключения наружу | F-32, F-51, F-31 | AC-003: unit-набор парсера (многобайтовый varint, кириллица UTF-8, wire types 0/1/2/5, усечение на каждой позиции) проходит на `/usr/bin/python3` 3.9.6 без исключений |
| REQ-003 | MUST | Мышление каждого шага выдаётся ровно один раз при работе двух источников (SQLite и `transcript_full.jsonl`): общий ключ `idx == step_index`, итоговая склейка равна финальному `thinking` шага; непрефиксный снимок не повторяет уже отданный текст | F-33, F-04, F-03 | AC-004: склейка всех чанков `reasoning_content` хода побайтово равна конкатенации финальных `thinking` шагов из транскрипта; AC-005: фикстура с непрефиксным снимком не даёт повторной выдачи отданного префикса |
| REQ-004 | MUST | SQLite-источник вспомогательный и fail-open: отсутствие БД, ошибка открытия (включая `unable to open database file` на системном Python), блокировка, неизвестная схема или поля дают «изменений нет», ход продолжается, мышление идёт из транскрипта как сейчас | F-52, F-53, F-35, F-02, F-34 | AC-006: при недоступной, заблокированной или битой БД ход завершается `done` с тем же текстом и мышлением из транскрипта, что и без SQLite-источника |
| REQ-005 | MUST | Продолжение треда (`--conversation`, горячая сессия) не переотдаёт мышление шагов прошлых ходов ни из SQLite, ни из транскрипта | F-02, F-13, F-41 | AC-007: на фикстуре БД с шагами прошлого хода клиент получает мышление только шагов, появившихся после старта текущего хода |
| REQ-006 | MUST | Детерминированное финальное дренирование: мышление всех шагов хода (включая последний, записанный до 90 мс после `result` и после выхода процесса) выдаётся клиенту до чанка `finish_reason="stop"` и до возврата `out` из `_execute`; события источников после выхода `_execute` не теряются молча | F-06, F-07, F-08, F-29, F-43 | AC-008: фейковый agy, пишущий запись шага через 90 мс после `result` и выходящий сразу, в 100 из 100 прогонов даёт чанк мышления раньше `finish_reason="stop"` |
| REQ-007 | MUST | Финальное дренирование ограничено по времени и не продлевает ход больше 1.0 с сверх момента выхода процесса agy | F-02, F-07, F-15 | AC-009: время от EOF stdout фейкового agy до чанка `stop` не больше 1.0 с при молчащих источниках мышления |
| REQ-008 | MUST | Отданное клиенту мышление считается выдачей: после него невидимый повтор хода запрещён и уже отданные чанки не дублируются; финальный исход сбоя после мышления определяет Архитектор (кадр ошибки или частичный ответ) | F-09, F-10, F-11, F-47 | AC-010: фейковый agy, отдавший мышление и затем `result` со статусом ERROR, даёт ровно 1 запуск процесса и ни одного повторного чанка мышления |
| REQ-009 | MUST | Фоновые запросы без инструментов (генерация заголовка DSH) не занимают и не перезаписывают горячую сессию агентного диалога с инструментами той же модели, `cwd` и effort | F-12, F-13, F-42 | AC-011: последовательность «агентный ход, фоновый ход без tools, агентный ход» даёт третьему ходу `resume=1` с `cid` первого хода, а фоновый ход не получает `cid` первого хода |
| REQ-010 | MUST | Публичный контракт не меняется: эндпоинты `/health`, `/v1/models`, `/v1/chat/completions`, порт 9887, форма SSE-чанков (`role`-чанк, `reasoning_content`, `content`, `stop`, `usage`, кадр `error`, `[DONE]`), флаги запуска agy; текст мышления модели не модифицируется | F-11, F-05, F-19, F-39 | AC-012: 22 существующих теста `tests/test_agy_bridge_resilience.py` зелёные без правок; AC-013: склейка мышления без изменений текста модели |
| REQ-011 | MUST | SQLite-источник отключается переключателем окружения (имя и дефолт задаёт Архитектор); при выключенном переключателе поведение моста совпадает с as-is, исправления RC-2..RC-4 от переключателя не зависят | F-01, F-15, F-38 | AC-014: при выключенном переключателе ни одна БД `conversations/*.db` не открывается (проверка через подменённый `sqlite3.connect`) |
| REQ-012 | SHOULD | Наблюдаемость и бюджет: диагностические строки источника (cid-префикс, шаг, длина, задержка дренирования, ошибка открытия) без текста мышления и секретов; опрос БД не дороже 2% одного ядра на активный ход | F-40, F-51, F-55 | AC-015: в `bridge.err` после хода есть строки источника с полями cid, step, len и нет текста мышления; AC-016: CPU потока опроса на фикстуре 60 с не больше 2% ядра |

## 4. Сравнение вариантов (по фактам, без выбора)

### 4.1. Live-источник мышления (RC-1)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Опрос SQLite `conversations/<cid>.db` (`mode=ro`) с парсером wire-формата, транскрипт остаётся источником для DONE-шагов и fallback | Подполе 20.3 растёт в `status=8` каждые 1.5-5.1 с (F-30); парсер на stdlib работает на реальных БД (F-32); финальный текст равен транскрипту (F-33); боевой Python 3.9.6 открывает WAL-БД с `mode=ro` только при живом пишущем соединении (F-52, F-53); схема внутренняя и меняется автоапдейтом (OPEN-03) | выполнимо с условиями: fail-open, переключатель, учёт окна после выхода agy |
| B. Только транскрипт (as-is) с более частым опросом | Запись шага появляется только после DONE (F-29); частота опроса не влияет на отсутствие данных во время генерации | невыполнимо для реалтайма |
| C. Поле `thinking_delta` в stdout `stream-json` | Поле объявлено в protobuf, но не сериализуется printmode 1.4.9 (F-28); в живом потоке его нет (F-27) | невыполнимо на 1.4.9 |
| D. Python SDK `google-antigravity` | Мысли только после блокирующего `send()` (F-37) | невыполнимо для реалтайма |
| E. Чтение БД через CLI `sqlite3` подпроцессом | `sqlite3 -readonly` дал ошибку 14 на той же БД (F-35); подпроцесс на каждый опрос | выполнимо с условиями, уступает A по стоимости |
| F. Локальный `agentapi` из `~/.gemini/antigravity-cli/bin/` | Не исследовался (OPEN-11) | нет данных |

Параметры варианта A для решения Архитектора (факты, не выбор):
- Путь БД: `~/.gemini/antigravity-cli/conversations/<cid>.db`, где `cid` — из события `init` (F-06, F-30). Каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/` (F-36).
- Выборка: таблица `steps`, колонки `idx`, `step_type`, `status`, `step_payload`, индексы по `status` и `step_type` (F-31). Размер payload строки — от 2 до 40 KB (F-32), шагов в длинном ходе — сотни (F-45).
- Ключ дедупликации: `idx` БД равен `step_index` транскрипта (F-33); существующая функция `_reasoning_suffix` ведёт виденный текст по строковому ключу (F-04).
- Открытие: Python 3.9.6 + `mode=ro` на закрытой WAL-БД падает, при открытом writer работает; `immutable=1` читает закрытую БД (F-52, F-53, OPEN-02, OPEN-12).
- Поток опроса может быть отдельным или частью `_TranscriptTail` (общая очередь `Run.q`, F-03).

### 4.2. Синхронизация финального дренирования (RC-2)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. `_pump` перед `("done")` вызывает синхронный финальный проход источников с ограничением времени | Сейчас `_pump` ставит `done` через 0.05 с после EOF (F-06); запись шага приходит через 90 мс после `result` (F-29) | выполнимо |
| B. `_execute` после `done` ждёт сигнал завершения потоков источников (join с таймаутом) и дочитывает очередь | `_execute` читает очередь до `done` и выходит (F-07); `Run.close` останавливает хвост (F-08) | выполнимо |
| C. Отдельный маркер конца источника в очереди и ожидание двух маркеров (`done` и конец источника) | Очередь уже несёт типизированные кортежи (F-03, F-06) | выполнимо |
| D. Увеличить паузу `_pump` до значения больше `TRANSCRIPT_GRACE_S` | Остаётся гонкой по времени, добавляет задержку всем ходам (F-02, F-06) | выполнимо с условиями, недетерминировано |

### 4.3. Учёт выдачи (RC-3)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Добавить `out.get("reasoning")` в условие `delivered` | Поле `reasoning` уже возвращается из `_execute` (F-10) | выполнимо |
| B. Явный флаг «байты отданы клиенту», выставляемый колбэками `on_text`/`on_reasoning` | Колбэки централизованы в `_serve_sse` (F-11) | выполнимо |

### 4.4. Изоляция горячих сессий (RC-4)

| Вариант | Фактура | Вердикт |
|---|---|---|
| A. Признак наличия инструментов в `sess_key` | `tools_count` уже вычислен до ключа (F-12); фоновые запросы имеют `tools=0` (F-42) | выполнимо |
| B. Не занимать и не коммитить горячую сессию для запросов без инструментов с одним сообщением | `_session_claim`/`_session_commit` вызываются условно уже сейчас (F-12, F-13) | выполнимо |
| C. Ключ по признаку диалога (хеш первого user-сообщения или `prompt_cache_key`) | KB фиксирует отсутствие `prompt_cache_key` в ключе (F-12); поле в запросах DSH не исследовалось | выполнимо с условиями |

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Контракт | Лимиты | Режимы отказа |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` | HTTP/1.1, OpenAI SSE или JSON, Bearer | Ingress от DSH | `_serve_sse`, `_serve_json` (F-11, F-19) | тело до 32 MiB, 32 соединения, 8 слотов (F-38, F-39) | 503 overloaded, 504 timeout, 502 agy_error, кадр `error` в SSE (F-11) |
| `GET /health` | HTTP JSON без авторизации | Ingress | `ok`, `active`, `max_concurrent`, `hot_sessions` (F-39) | нет | нет |
| Лончер `agy-cli.sh` | подпроцесс, NDJSON stdin/stdout | Egress | флаги из F-05 | `MAX_CONCURRENT` (F-15, F-38) | `Individual quota reached` (F-46), `first_token_timeout`, `idle_timeout` (F-15) |
| `transcript_full.jsonl` | файл JSONL, только чтение | Egress (чтение) | `PLANNER_RESPONSE.thinking`, `step_index` (F-03, F-33) | порция 4 MiB (F-01) | файл отсутствует или переписан — «мышления нет» (F-02) |
| `conversations/<cid>.db` | SQLite WAL, только чтение | Egress (чтение), новый | `steps.step_payload`, поле 20.3 (F-31, F-32) | строки 2-40 KB (F-32) | ошибка открытия на Python 3.9.6 без `-shm` (F-52) |

## 6. NFR-набросок (наблюдаемые величины)

- Длительность фазы мышления `gemini-4-argon --effort high`: около 19 с тишины stdout в замере (F-29); одношаговые ходы 46.6-55.2 с (F-44).
- Частота записи мышления в БД: 1.5-5.1 с между снимками (F-30).
- Агентные ходы с инструментами: 856.5 с и 1068.0 с, 22-37 кусков мышления через транскрипт (F-45).
- Пик нагрузки: 6 запусков в одну секунду (F-55), `max_concurrent=8` (F-39).
- Ресурсы процесса моста: RSS 20 MiB, 36 дескрипторов (F-51).

## 7. Конверт `HL-ENV/v1`

Контур — один локальный демон LaunchAgent на рабочей станции, не k8s. Поля пода трактуются как «один процесс моста», значения без замера
помечены `оценка`. Единицы СИ.

### 7.1. Канонические 46 полей `REQUIRED_HL_ENV_FIELDS` (`architecture.md`, таблица 3.0)

| № | Поле | Значение | Источник |
|---|---|---|---|
| 1 | `P_steady` | 1 pod (один процесс LaunchAgent) | F-38 |
| 2 | `P_hpa_max` | 1 pod | F-38 |
| 3 | `maxSurge_pct` | 0.0 | F-38 (KeepAlive, без выкатки) |
| 4 | `maxSurge_abs` | 0 pods | вычислено |
| 5 | `maxUnavailable_pct` | 0.0 | F-38 |
| 6 | `maxUnavailable_abs` | 0 pods | вычислено |
| 7 | `P_terminating_overlap` | 0 pods (рестарт через launchctl, `_kill_all` при SIGTERM) | F-38 |
| 8 | `P_live` | 1 pod | вычислено |
| 9 | `P_avail_min` | 1 pod | вычислено |
| 10 | `W` | 1 proc/pod | F-51 |
| 11 | `N_proc` | 1 process | вычислено |
| 12 | `N_proc_steady` | 1 process | вычислено |
| 13 | `N_proc_avail_min` | 1 process | вычислено |
| 14 | `CPU_limit_per_pod` | 2.0 cores (бюджет рабочей станции, оценка) | оценка |
| 15 | `κ_skew` | 1.0 (один процесс) | F-51 |
| 16 | `u_bg_worker` | 0.02 cores на активный ход (опрос транскрипта 20 раз в секунду плюс опрос БД, оценка) | F-01, оценка |
| 17 | `U_pod_sidecars` | 0.0 cores в процессе моста (agy — внешние процессы в своей группе) | F-05 |
| 18 | `Mem_limit_per_pod` | 512 MiB (бюджет демона, оценка) | оценка |
| 19 | `Mem_rss_worker_max` | 64 MiB (измерено 20 MiB без нагрузки, запас на 8 ходов) | F-51 |
| 20 | `Mem_shared_max` | 32 MiB (буферы чтения транскрипта 4 MiB на ход, оценка) | F-01 |
| 21 | `RPS_peak` | 6 req/s (пик запусков в одну секунду) | F-55 |
| 22 | `A_max` | 2 attempts/req | F-09 |
| 23 | `SLA_p99_s` | 1800 s сквозной потолок хода; цель первой дельты мышления 5 s (допущение) | F-15, open-questions |
| 24 | `N_entities_max` | сотни шагов `steps` на разговор (в логе до 52 событий инструментов на ход) | F-45 |
| 25 | `Limit_dep_share[d]` | agy: 8 процессов; БД разговоров: 1 соединение только для чтения на активный ход, до 8 | F-38, F-39 |
| 26 | `Limit_dep_rps[d]` | БД: до 1/T_poll на ход, при 0.5 s до 16 открытий в секунду на 8 ходов (оценка) | оценка |
| 27 | `W_fetchers[d]` | 1 поток опроса на активный ход | F-02 |
| 28 | `J_init_s[d]` | 0 s (опрос стартует по `init`) | F-06 |
| 29 | `J_pod_s[d]` | 0 s (один процесс) | F-38 |
| 30 | `T_poll_s[d]` | транскрипт 0.05 s; БД — выбор Архитектора при интервале записи 1.5-5.1 s | F-01, F-30 |
| 31 | `K_calls[d]` | 1 SELECT на опрос | оценка |
| 32 | `T_base_s[d]` | 2 s (пауза перед повтором хода `2*attempt`) | F-09 |
| 33 | `T_cap_s[d]` | 2 s (одна пауза, второй попытки нет) | F-09 |
| 34 | `Max_stale_age_s[c]` | мышление: 6 s (интервал записи 5.1 s плюс опрос, допущение); горячая сессия: 2700 s простоя | F-30, F-13 |
| 35 | `Min_healthy_ratio` | N/A: один апстрим без пула кандидатов | F-05 |
| 36 | `B_retry_max` | 1 повтор на запрос | F-09 |
| 37 | `min_reserve_retry_rps` | 0.0 req/s | F-09 |
| 38 | `FD_worker` | 36 без нагрузки; плюс до 6 на ход (3 пайпа, транскрипт, БД, `-shm`, оценка) | F-51 |
| 39 | `ulimit_n` | 65536 (launchd soft) | F-54 |
| 40 | `λ_new_conn_per_pod(s)` | до 6 conn/s с loopback от DSH | F-55 |
| 41 | `C_active_in_scope(s)` | до 32 соединений (admission) | F-39 |
| 42 | `N_pods_in_scope(s)` | 1 | F-38 |
| 43 | `Port_range_size(s)` | 16384 ports (49152-65535) | F-54 |
| 44 | `T_hold_s(s)` | 30 s (TIME_WAIT = 2 × MSL 15 s) | F-54 |
| 45 | `SNAT_ips_count(s)` | 1 (loopback, без SNAT) | F-54 |
| 46 | `HOTPATH_MODULES` | `Handler.do_POST`, `_serve_sse`, `_run_once`, `_execute`, `Run._pump`, `_TranscriptTail._read`, `_TranscriptTail._emit_record`, `_reasoning_suffix`, новый опрос БД и парсер wire-формата | F-03, F-06, F-07 |

Замыкание памяти: `W × Mem_rss_worker_max + Mem_shared_max = 64 + 32 = 96 MiB ≤ 0.80 × 512 = 409.6 MiB` (PASS, оценка).

### 7.2. 46 идентификаторов из брифа (дословно)

| № | Поле | Значение | Источник |
|---|---|---|---|
| 1 | `W` | 1 процесс | F-51 |
| 2 | `P_pods` | 1 | F-38 |
| 3 | `G_reload` | 0 (горячей перезагрузки нет, рестарт через launchctl) | F-38 |
| 4 | `T_threads_per_worker` | до 32 потоков соединений плюс 4 потока на ход (stdin, stderr, pump, хвост) × 8 ходов | F-05, F-39 |
| 5 | `Limit_dep_total` | 8 одновременных процессов agy | F-38 |
| 6 | `Limit_dep_share` | 1.0 (весь лимит agy у одного моста) | F-38 |
| 7 | `Pool_app_size` | 8 слотов `_slots` | F-38, F-39 |
| 8 | `Pool_app_overflow` | 0; ожидание слота до 1800 s | F-38 |
| 9 | `Max_in_flight_per_worker` | 8 ходов | F-39 |
| 10 | `N_roles` | 1 | F-38 |
| 11 | `W_role` | 1 | F-51 |
| 12 | `Pool_role_size` | 8 | F-39 |
| 13 | `Pool_role_overflow` | 0 | F-38 |
| 14 | `M_other_apps_max` | другие мосты DSH на том же хосте, общих пулов с agy-bridge нет | F-38 |
| 15 | `Ephemeral_port_range_size` | 16384 | F-54 |
| 16 | `TIME_WAIT_s` | 30 s | F-54 |
| 17 | `ulimit_n` | 65536 | F-54 |
| 18 | `FD_non_socket_overhead` | до 6 на ход (пайпы, транскрипт, БД, `-shm`, оценка) | F-51 |
| 19 | `N_bg_tasks` | 4 потока на ход сейчас, плюс поток опроса БД, если он отдельный | F-05 |
| 20 | `T_poll_s` | 0.05 s транскрипт; БД — выбор Архитектора | F-01, F-30 |
| 21 | `Jitter_Ratio` | 0.0 | F-02 |
| 22 | `Startup_Delay_Range_s` | 0 s | F-06 |
| 23 | `K_calls` | 1 | оценка |
| 24 | `Limit_dep_rps` | БД: до 16 открытий в секунду на 8 ходов при опросе 0.5 s (оценка) | оценка |
| 25 | `Cold_start_concurrent_pods` | 1 | F-38 |
| 26 | `Singleflight_Scope` | ход (у каждого хода свой `cid` и свой файл БД) | F-02, F-30 |
| 27 | `Cache_TTL_s` | 2700 s (простой горячей сессии) | F-13 |
| 28 | `Max_stale_age_s` | 6 s для мышления (допущение) | F-30 |
| 29 | `Payload_bytes_max` | 40 KB на строку `steps` (наблюдено), тело HTTP до 32 MiB | F-32, F-38 |
| 30 | `N_items_max` | сотни шагов на разговор | F-45 |
| 31 | `Hot_path_call_rate_rps` | 20 опросов транскрипта в секунду на ход плюс опрос БД | F-01 |
| 32 | `CPU_budget_pct_per_core` | 2% ядра на активный ход для опроса БД | REQ-012 |
| 33 | `Serde_lib` | `json` и `sqlite3` из stdlib, собственный разбор wire-формата | F-32, F-51 |
| 34 | `P_avail_min` | 1 | F-38 |
| 35 | `Mem_limit_per_pod` | 512 MiB (оценка) | оценка |
| 36 | `Mem_rss_worker_max` | 64 MiB | F-51 |
| 37 | `Mem_shared_max` | 32 MiB | F-01 |
| 38 | `SLA_p99_s` | 1800 s потолок хода; первая дельта мышления 5 s (допущение) | F-15 |
| 39 | `T_connect_s` | N/A для файла БД; loopback HTTP без таймаута подключения | F-11 |
| 40 | `T_read_s` | 1.0 s ожидание очереди; первый JSON stdout 120 s; неактивность 300 s | F-07, F-15 |
| 41 | `Retries_max` | 1 | F-09 |
| 42 | `Retry_Budget_pct` | 100% (до одного повтора на каждый запрос) | F-09 |
| 43 | `Retry_Window_s` | 2 s | F-09 |
| 44 | `Min_Retry_Floor_rps` | 0.0 | F-09 |
| 45 | `N_candidates` | 2 источника мышления (SQLite, транскрипт) | F-30, F-29 |
| 46 | `N_floor` | 1 (транскрипт остаётся минимальным источником) | F-02 |

## 8. Гейты Highload & Resilience (as-is и ограничения для дизайна)

- `C-MULT/v1`: соединения к БД — по одному только для чтения на активный ход, не больше 8 (F-39); дескрипторы `36 + 8 × 6 = 84 ≤ 0.70 × 65536` (F-51, F-54) — PASS (оценка); соединение к БД закрывается вместе с ходом (`Run.close`, F-08).
- `S-HERD/v1`: поллеров внешних сервисов нет, опрос локальных файлов; одновременный старт 6 ходов (F-55) даёт 6 независимых опросов разных файлов, общего ресурса кроме CPU нет.
- `H-CPU/v1`: разбор payload до 40 KB (F-32) на каждый опрос; для ограничения CPU (REQ-012) выборка только строк шага в генерации и шагов после старта хода — решение Архитектора.
- `R-BULK/v1`: повтор хода — не более 1 (F-09); источник мышления в повторах не участвует.
- `T-LIFE/v1`: потоки источников живут не дольше хода и завершаются в `Run.close` (F-08); финальное дренирование ограничено 1.0 с (REQ-007).
- `O-EXIT/v1`: строка `done model=... state=...` уже есть на каждом ходе (F-40); расширение полями источника — REQ-012.
- `M-SEM/v1`: единый пул слотов `_slots` (F-38); новых пулов не появляется.
- Режимы отказа зависимостей: SQLite-источник — `Fail-Open` (REQ-004); транскрипт — `Fail-Open` (as-is, F-02); авторизация моста — `Fail-Closed` (as-is, F-11).

## 9. Non-Goals

- Не менять публичный HTTP-контракт, порт 9887 и форму SSE (REQ-010).
- Не менять DSH, лончер `agy-cli.sh`, бинарь agy и его файлы состояния (БД и транскрипт открываются только на чтение).
- Не модифицировать текст мышления модели.
- Не менять каталог моделей, efforts и логику выбора аккаунта.
- Не исправлять трактовку `text_delta` как накопительного снимка (риск зафиксирован в `open-questions.md`).
- Не вводить внешние зависимости Python: боевой интерпретатор — `/usr/bin/python3` 3.9.6 (F-51).

## 10. Forbidden Scope

- Запись в `~/.gemini/antigravity-cli/conversations/*.db`, `brain/`, создание файлов рядом с ними со стороны моста (кроме служебных файлов SQLite, создаваемых самим режимом чтения).
- Правка чужих мостов и `core/` без явного обоснования Архитектора.
- Запись секретов и текста мышления в логи и артефакты.
- Деплой в `~/.dsh/bridges/agy-bridge/` и рестарт LaunchAgent вне протокола L3 из `handoff-qa.md`; каталог деплоя — копия, а не симлинк (F-38).
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-56`.
- `blocking open questions`: пусто.
- `assumptions`: вопросы со статусом ASSUMPTION и DEFERRED из `open-questions.md` (префиксный рост 20.3, открытие WAL на Python 3.9.6, стабильность схемы, причины 6 ходов без мышления, `cwd` фонового запроса, финальный кадр после сбоя, квота для L3, числовые цели, `fleet.json`, `text_delta`, `agentapi`, `immutable=1`).
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): тишина UI 15-45 с при мышлении (F-29, F-44); цель — первая дельта до 5 с от начала генерации шага, интервал до 6 с, дренирование до 1.0 с.
- `risks`: R1 — смена схемы protobuf после автоапдейта agy (F-25, F-28); R2 — `mode=ro` не открывает закрытую WAL-БД на боевом Python 3.9.6 (F-52); R3 — квота аккаунта блокирует L3 (F-46); R4 — повторная выдача мышления при непрефиксном снимке (F-04); R5 — 6 параллельных ходов удваивают опросы файлов (F-55).

## 12. Обратный канал в требования и бриф

Противоречий фактов с REQ-ID нет. Расхождения с брифом, не меняющие объём работ:
- Тесты моста лежат в `tests/test_agy_bridge_resilience.py`, файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет (F-21).
- Каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, каталога релизов `~/.gemini/antigravity-cli/releases/1.4.9` нет (F-36, F-25).
- `_LAST_CONV` в коде нет, используется `_session_store` (F-14).
- Номера строк и период опроса в брифе устарели (F-50).
- Базовая линия полного набора уже содержит 3 красных теста вне `agy-bridge` (F-56); 22 теста моста зелёные (F-23).
- Stdout `stream-json` 1.4.9 несёт не только `init` и `result`: после фазы мышления идут `step_update` с `text_delta` видимого текста (F-27).
ARTIFACT_END>>>

<<<ARTIFACT analysis/agy-realtime-reasoning/evidence-ledger.md sha256=e9c8afb2684a7621e9fdb0455640e86f972aab600989142119fb440397842ff1
# Evidence Ledger: agy-realtime-reasoning (agy-bridge :9887, реалтайм-размышление gemini-4-argon)

Дата сбора: 2026-10-29 (MSK). Ветка `feature/agy-realtime-reasoning` (HEAD `e00da06`). Роль: System Analyst (Stage 1, preset `analyst-teamlead`).
Формат факта: `[F-NN] утверждение | источник | YYYY-MM-DD`. Пути без `~/` — относительно корня репозитория
`~/tmp/cli-agent-bridge/agy-realtime-reasoning/`. Код продукта не менялся. PoC-скрипты и логи аналитика лежат вне репозитория:
`/tmp/cel-runs/agy-realtime-reasoning-sa-20261029/` (`poc_pb.py`, `cmp2.py`, `baseline-*.log`). Секреты не выносились:
значение `AGY_BRIDGE_KEY` не читалось, из логов взяты только счётчики и строки без токенов.

## 1. Код моста: источник мышления и транскрипт

[F-01] Источник мышления моста настроен на транскрипт: `BRAIN_DIR` по умолчанию `~/.gemini/antigravity-cli/brain`, имя файла `transcript_full.jsonl`, период опроса `TRANSCRIPT_POLL_S=0.05` с, финальная пауза `TRANSCRIPT_GRACE_S=0.4` с, порция чтения 4 MiB; комментарий в строках 97-98 утверждает запись транскрипта посреди хода (проверено на 1.3.1) | bridges/agy-bridge/server.py:97-105 | 2026-10-29
[F-02] `_TranscriptTail._run` ждёт привязки к `conversation_id` до `FIRST_TOKEN_TIMEOUT_S` (120 с), для продолжения треда ставит смещение на текущий размер файла, затем опрашивает файл; при выставленном `done_event` или `stop_event` спит `TRANSCRIPT_GRACE_S` и делает один финальный проход, после чего поток завершается | bridges/agy-bridge/server.py:594-662 | 2026-10-29
[F-03] `_TranscriptTail._emit_record` отбирает только записи `type == PLANNER_RESPONSE` с непустым `thinking`, считает приращение через `_reasoning_suffix` с ключом `str(step_index)` и отдаёт его в колбэк `emit`, который кладёт `("reasoning", текст)` в очередь `Run.q` | bridges/agy-bridge/server.py:691-709, 769-772 | 2026-10-29
[F-04] `_reasoning_suffix` возвращает хвост сверх ранее виденного текста того же ключа, а если новый текст не начинается с прежнего, возвращает весь новый текст целиком и перезаписывает виденное | bridges/agy-bridge/server.py:886-893 | 2026-10-29
[F-05] `Run.__init__` запускает лончер с флагами `--input-format stream-json --output-format stream-json --dangerously-skip-permissions --model --effort --print-timeout=0` (и `--conversation` при продолжении), в новой группе процессов, и стартует потоки stdin, stderr, `_pump` и `_TranscriptTail` с `resumed=bool(run_cid)` | bridges/agy-bridge/server.py:720-776 | 2026-10-29
[F-06] `Run._pump` на `init` кладёт событие в очередь и привязывает хвост к `conversation_id`; на `step_update` с `agent_response` и `text_delta` кладёт `("text", хвост)`; на `result` кладёт `("result", ...)`; после EOF stdout ждёт процесс, спит 0.05 с, выставляет `_proc_done` и сразу кладёт `("done", ...)` без ожидания потока хвоста | bridges/agy-bridge/server.py:807-868 | 2026-10-29
[F-07] `Handler._execute` читает только очередь `run.q` (таймаут 1.0 с) и возвращает `state("done")` сразу по событию `done` (после паузы 0.05 с); на `result` со статусом `ERROR` возвращает `agy_error` немедленно; ожидания завершения потока `_TranscriptTail` в цикле нет | bridges/agy-bridge/server.py:981-1101 | 2026-10-29
[F-08] `Run.close` выставляет `_stop_watch` и `_proc_done` и зачищает группу процессов; очередь `run.q` после выхода из `_execute` никем не читается, поэтому событие `reasoning`, положенное хвостом после финальной паузы, клиенту не попадает | bridges/agy-bridge/server.py:870-883, 1148-1151 | 2026-10-29
[F-09] В `Handler._run_once` после неуспешной попытки флаг `delivered = bool(out.get("text") or out.get("tool_calls"))` не учитывает `out["reasoning"]`; при `not delivered` и состояниях `agy_error`, `pump_error`, `done` выполняется невидимый повтор (до 2 попыток, пауза `2*attempt` с), а горячая сессия при `agy_error` без выдачи переходит в холодный повтор с полной историей | bridges/agy-bridge/server.py:1126-1172 | 2026-10-29
[F-10] `_execute` возвращает в `out` поле `reasoning` (склейка отданных клиенту кусков мышления), а `tool_calls` всегда пустой список, то есть `delivered` на практике зависит только от текста | bridges/agy-bridge/server.py:999-1006, 1015-1024 | 2026-10-29
[F-11] `_serve_sse` шлёт первый чанк `{"role":"assistant","content":""}`, мышление отдаёт чанками `delta.reasoning_content`, а при ошибке после начала потока пишет кадр `data: {"error": ...}` и затем `data: [DONE]` | bridges/agy-bridge/server.py:1438-1501 | 2026-10-29
[F-12] Ключ горячей сессии `sess_key = (model_id, cwd, effort)` не содержит признака наличия `tools`, числа сообщений или ключа кэша промпта; `_session_claim` вызывается для любого запроса без явного `conversation_id`, а `tools_count` вычисляется отдельно и в ключ не входит | bridges/agy-bridge/server.py:1368-1385 | 2026-10-29
[F-13] `_session_commit` перезаписывает запись хранилища, если `cid` завершившегося хода отличается от сохранённого; `_session_claim` пропускает занятую (`_in_flight_cids`) сессию и тогда запрос стартует холодным; TTL простоя 45 мин, жизни 24 ч, потолок 30 ходов | bridges/agy-bridge/server.py:116-130, 477-516 | 2026-10-29
[F-14] Глобальной переменной `_LAST_CONV` в мосте нет (0 совпадений grep по `bridges/agy-bridge/` и `core/`); роль «последнего разговора» выполняет словарь `_session_store` с ключом `sess_key` | grep -rn _LAST_CONV bridges/agy-bridge/ core/ (0 строк); bridges/agy-bridge/server.py:128-130 | 2026-10-29
[F-15] Таймауты моста: `KEEPALIVE_S=15`, `FIRST_TOKEN_TIMEOUT_S=120` (порог по первому любому JSON-событию stdout), `TIMEOUT_S=1800`, `QUEUE_TIMEOUT_S=900`, `MAX_CONCURRENT=4` по умолчанию; `IDLE_TIMEOUT_S` берётся из `core.watchdog` (300 с), проверка сторожа не чаще `WATCHDOG_INTERVAL_S=5` с | bridges/agy-bridge/server.py:88-95, 336, 1029-1056; core/watchdog.py:27-30 | 2026-10-29
[F-16] Keepalive моста — SSE-комментарий `: keepalive`, он не несёт ни `content`, ни `reasoning_content` и в UI ничего не показывает | bridges/agy-bridge/server.py:1479-1480 | 2026-10-29
[F-17] Событие `reasoning` входит в `_ACTIVITY_KINDS` и сбрасывает таймер неактивности сторожа через `controller.on_activity` | bridges/agy-bridge/server.py:341, 1057-1058 | 2026-10-29
[F-18] Docstring `_pump` описывает `text_delta` как накопительный снимок, а живой поток 1.4.9 присылает непересекающиеся приращения (например, `Прочитан общий канон ~/Мо`, затем `й диск/`); корректный вывод сейчас обеспечивает ветка «не префикс → весь текст» из `_reasoning_suffix` | bridges/agy-bridge/server.py:807-813, 839-843; /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl строки 4-11 | 2026-10-29
[F-19] Нестриминговый путь `_serve_json` кладёт склеенное мышление в `message.reasoning_content`, то есть гонка финального дренирования затрагивает и ответ без `stream` | bridges/agy-bridge/server.py:1413-1436 | 2026-10-29
[F-20] На `done` при пустом потоке текста `_execute` подставляет `final_text` из `result.response`, после чего ход считается `done` | bridges/agy-bridge/server.py:1088-1101 | 2026-10-29

## 2. Тесты и базовая линия

[F-21] Файла `bridges/agy-bridge/tests/test_agy_bridge.py` нет: каталога `tests` у моста нет, тесты моста лежат в корневом `tests/test_agy_bridge_resilience.py` (709 строк, классы IdleDetection, ExecuteLoop, KillSwitch, ErrorContract, KillGroup, FetchViaPlaywrightHotfix) | ls bridges/agy-bridge/ (fleet.json, server.py, start.sh); grep -n "def test_" tests/test_agy_bridge_resilience.py | 2026-10-29
[F-22] Тестов на `_TranscriptTail`, финальное дренирование, флаг `delivered` и `sess_key` нет: слово `reasoning` встречается только в тестах вида активности сторожа | grep -n по словам TranscriptTail, reasoning, sess_key, delivered в tests/test_agy_bridge_resilience.py (строки 248, 354, 363) | 2026-10-29
[F-23] Базовая линия моста зелёная: `python3 -m unittest tests.test_agy_bridge_resilience` дал `Ran 22 tests in 2.082s OK` (exit 0); `python3 -m pytest` недоступен (в python3.14 нет модуля pytest) | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-unittest.log, baseline-pytest.log | 2026-10-29
[F-24] Полный прогон `uvx pytest -q -p no:cacheprovider tests/` без `PYTHONPATH` падает на сборке `tests/test_adaptive_idle_watchdog.py` с `ModuleNotFoundError: No module named 'core'` (exit 2); полный набор требует `PYTHONPATH=.` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full.log | 2026-10-29

## 3. agy 1.4.9: stdout, транскрипт, SQLite

[F-25] Установлен `agy` 1.4.9: `~/.local/bin/agy --version` печатает `1.4.9`, бинарь `~/.local/bin/agy.real` 193540240 байт от 2026-10-28 11:50; каталога `~/.gemini/antigravity-cli/releases/` нет | ~/.local/bin/agy --version; ls -la ~/.local/bin/agy*; ls ~/.gemini/antigravity-cli/ | 2026-10-29
[F-26] `fleet.json` устарел относительно рантайма: `technical_ref.agy_version` равен `1.3.1`; `gemini-4-argon` имеет efforts low/medium/high и `default_effort=high`, `default_model` каталога `gemini-3.8-flash` | bridges/agy-bridge/fleet.json (technical_ref, models[0]) | 2026-10-29
[F-27] Живой поток `stream-json` 1.4.9 (cid `c6910a34`): `init`, `step_update` user_input DONE, два шага `unknown` DONE, семь `agent_response` ACTIVE с `text_delta`, финальный DONE с `usage.thinking_tokens=1460`, затем `result` (`duration_seconds=19.8653`); ни одно событие не несёт текста мышления | /tmp/cel-runs/agy-streaming-research-20261029/live_stream_json.jsonl | 2026-10-29
[F-28] В 1.4.9 Go-структура `steps.StepUpdatePayload` пакета printmode сериализует `text_delta` и `thinking_tokens`, но не поле `thinking` или `thinking_delta`, хотя в protobuf `StepUpdate` поле `thinking_delta` (field 10) объявлено | KB tools/dsh-bridges-cli-agent-bridge.md строки 361-365 (дизассемблирование agy.real 1.4.9) | 2026-10-29
[F-29] Живой замер `gemini-4-argon --effort high` (cid `82188e72`): stdout молчит с 4.81 с по 23.52 с; `transcript_full.jsonl` заморожен на 66213 байтах после `step_index=2`; запись `step_index=3` (`PLANNER_RESPONSE` с `thinking`) появилась в 23.87 с, на 90 мс позже события `result` (23.78 с); `Handler._execute` вышел по `done` в 23.83 с | KB tools/dsh-bridges-cli-agent-bridge.md строки 369-373; /tmp/cel-runs/agy-streaming-research-20261029/checks.tsv строка step-3 | 2026-10-29
[F-30] В том же замере строка `idx=3, step_type=15, status=8` файла `~/.gemini/antigravity-cli/conversations/<cid>.db` обновлялась во время мышления: 10.66 с (523 B), 12.19 с (810 B), 14.97 с (1088 B), 20.06 с (1419 B), 23.36 с (2156 B), то есть интервалы 1.5-5.1 с | KB tools/dsh-bridges-cli-agent-bridge.md строки 374-376; checks.tsv step-3-live-stream-probe | 2026-10-29
[F-31] Схема таблицы `steps`: `idx integer PRIMARY KEY, step_type integer, status integer, has_subtrajectory, metadata blob, error_details blob, permissions blob, task_details blob, render_info blob, step_payload blob, step_format integer`, индексы по `status` и `step_type`; в БД также таблицы `battle_mode_infos, executor_metadata, gen_metadata, parent_references, trajectory_meta, trajectory_metadata_blob` | sqlite3 "file:<db>?mode=ro&immutable=1" ".tables" ".schema steps" (отчёт explorer Zone D); PRAGMA table_info(steps) в poc_pb.py | 2026-10-29
[F-32] PoC-парсер wire-формата на stdlib (varint, wire types 0/1/2/5) извлёк из `82188e72` строки: idx 0 `step_type=14` (2020 B), idx 1 и 2 `step_type=90` (40132 B и 25094 B), idx 3 `step_type=15 status=3` (10068 B) с полем 20, в котором подполе 1 = 196 символов, подполе 3 = 1875 символов, подполе 6 встречается 1 раз, подполе 8 = 196 символов | python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/poc_pb.py 82188e72-6eca-4f23-a0b3-2257ec43bd60 | 2026-10-29
[F-33] Финальный текст мышления из SQLite (`step_type=15`, поле 20.3) побайтово равен полю `thinking` записи `PLANNER_RESPONSE` транскрипта при `idx == step_index` на трёх разговорах: `82188e72` (1875 символов, есть не-ASCII), `fa92a264` (1080, есть не-ASCII), `57172100` (5561, только ASCII); в `4a1067cc` шагов `step_type=15` с мышлением нет ни в БД, ни в транскрипте | python3 -I /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/cmp2.py <cid> | 2026-10-29
[F-34] Файлы `conversations/*.db` в режиме WAL (байты 18-19 заголовка `0x02 0x02`, `last written using SQLite version 3053002, page size 32768`); у закрытых разговоров файлов `-wal` и `-shm` нет, в каталоге найдено только 4 таких файла от 2026-10-28 | xxd -s 18 -l 2 <db>; file <db>; ls -la ~/.gemini/antigravity-cli/conversations (отчёт explorer Zone D) | 2026-10-29
[F-35] Python `sqlite3.connect("file:<db>?mode=ro", uri=True)` (SQLite 3.53.4) читает закрытую БД разговора без ошибок, а CLI `sqlite3 -readonly <путь>` на той же БД вернул `unable to open database file (14)` | poc_pb.py вывод `sqlite 3.53.4`; отчёт explorer Zone D вопрос 5 | 2026-10-29
[F-36] Рядом с транскриптом CLI держит копии `chunks/transcript/00000000.jsonl` и `chunks/transcript_full/00000000.jsonl`; разговорный каталог мозга — `~/.gemini/antigravity-cli/brain/<cid>/`, а не `~/.gemini/antigravity/brain/<cid>/` (в последнем для `82188e72` каталога логов нет) | ls ~/.gemini/antigravity-cli/brain/82188e72-.../.system_generated/logs/chunks/*; ls ~/.gemini/antigravity/brain/82188e72-.../.system_generated/logs/ (No such file) | 2026-10-29
[F-37] Python SDK `google-antigravity` возвращает мысли только постфактум (`response.thoughts` после блокирующего `send()`), стримингового генератора мыслей нет | KB tools/dsh-bridges-cli-agent-bridge.md строка 359 (`~/.gemini/antigravity/builtin/skills/antigravity_guide/references/sdk.md`) | 2026-10-29

## 4. Рантайм и деплой :9887

[F-38] LaunchAgent `com.user.dsh-agy-bridge` запускает `/bin/bash ~/.dsh/bridges/agy-bridge/start.sh`, логи в `~/.dsh/bridges/agy-bridge/logs/bridge.err` и `bridge.out`, env `AGY_BRIDGE_MAX_CONCURRENT=8`, `AGY_BRIDGE_PORT=9887`, `AGY_BRIDGE_QUEUE_TIMEOUT=1800`; `~/.dsh/bridges/agy-bridge` — обычный каталог, не симлинк, и его `server.py` побайтово равен репозиторному (sha256 `c4e52312…e747`) | plutil -p ~/Library/LaunchAgents/com.user.dsh-agy-bridge.plist; readlink; shasum -a 256 (отчёт explorer Zone D) | 2026-10-29
[F-39] `/health` моста: `ok=true`, `transport=agy-stream-json`, `model=gemini-3.8-flash`, `active=0`, `max_concurrent=8`, `hot_sessions=2`, `uptime_s=26273` | curl -s -m 3 http://127.0.0.1:9887/health | 2026-10-29
[F-40] `bridge.err` (2891 строк, без дат): `reasoning-emit` 888, `tail-emit` 893, `tail-timeout` 0, `tail-rewrite` 0, `exec model=` 301, `done model=` 266, `transient failure` 29, `hot session failed` 4; пять строк `tail-emit` не имеют парной `reasoning-emit` | grep -cF по ~/.dsh/bridges/agy-bridge/logs/bridge.err | 2026-10-29
[F-41] Из 301 запуска 156 с `tools=0` и 145 с `tools>0`; `resume=1` у 45, `resume=0` у 256 | grep/awk по bridge.err | 2026-10-29
[F-42] В логе 21 пара запусков одной модели в одну секунду, где один `tools>0` с большим промптом и `effort_source=request`, а второй `tools=0` с промптом 492-721 байт и `effort_source=default` на соседнем клиентском порту (например, 01:09:38 `gemini-3.8-flash` 78282 B против 674 B; 23:20:29 и 19:09:44 `gemini-4-argon`) | awk-группировка exec-строк bridge.err, строки 969-970, 1255-1256, 2792-2793 | 2026-10-29
[F-43] Среди ходов `gemini-4-argon` с `state=done`: без инструментов (`tool_events=0`) 28, из них 6 без единой строки `reasoning-emit` для своего cid; с инструментами 23, без мышления 0 | awk по init/reasoning-emit/done в bridge.err; строки 965, 968, 986, 1337, 1804, 1875 | 2026-10-29
[F-44] Одношаговый ход `926e03fa` (`gemini-4-argon`, wall 46.6 с): `tail-emit step=3 len=5342` и `reasoning-emit n=1` записаны в ту же секунду 01:08:22, что и `done`, то есть всё мышление пришло клиенту одним чанком в конце хода; так же ход `496587c9` (len 3935, wall 55.2 с) | bridge.err строки 2777-2782 | 2026-10-29
[F-45] Многошаговый ход `9ccb5526` с инструментами шёл 856.5 с и 1068.0 с (два хода, 52 и 46 событий инструментов) и отдал 37 и 22 куска мышления через транскрипт | bridge.err строки 2735, 2844, 2846, 2891 и подсчёт reasoning-emit | 2026-10-29
[F-46] 2026-10-29 в 01:07-01:09 аккаунт agy получал `Individual quota reached ... Resets in 54h2xm` на `gemini-4-argon` и `gemini-3.8-flash`, а мост выполнял `transient failure ... retry 1` и `hot session failed ... cold fallback` | bridge.err строки 2768, 2787, 2800 и done-строка 01:09:56 | 2026-10-29
[F-47] База знаний фиксирует сценарий RC-3 на `cid=9ccb5526` (мышление Шага 1 затёрто кадром ошибки после сбоя квоты), а в `bridge.err` оба хода `9ccb5526` завершились `state=done rc=0` | KB tools/dsh-bridges-cli-agent-bridge.md строки 377-380; bridge.err строки 2844, 2891 | 2026-10-29
[F-48] Ресерч 2026-10-29 закрыт со статусом ГОТОВО, источник реалтайма зафиксирован как SQLite `conversations/<cid>.db`, таблица `steps`, protobuf field 20.3 | /tmp/cel-runs/agy-streaming-research-20261029/close.md | 2026-10-29
[F-49] Последняя правка `bridges/agy-bridge/server.py` в истории — коммит `b9a9648` (resilience watchdog, process group kill, EYE-33873); ветка `feature/agy-realtime-reasoning` на HEAD `e00da06` (2026-10-28 03:32 MSK), рабочее дерево до анализа содержало только `.ai-team/runs/analyst-teamlead-agy-reasoning-20261029/` | git log --oneline -5 -- bridges/agy-bridge/server.py; git log -1; git status --porcelain | 2026-10-29
[F-50] Номера строк брифа расходятся с кодом: `_TranscriptTail` в 594-709 (в брифе 553-702), `Run._pump` в 807-868 (в брифе 920-935), `TRANSCRIPT_GRACE_S` в строке 104 (в брифе 626), период опроса 0.05 с (в брифе 0.15 с); строки `delivered` (1154) и `sess_key` (1377) совпадают | bridges/agy-bridge/server.py:104, 594, 807, 1154, 1377 | 2026-10-29

## 5. Рантайм Python и ограничения хоста

[F-51] Боевой процесс моста (PID 45973, uptime 07:24:29) запущен `start.sh` строкой `exec /usr/bin/python3 server.py`, то есть системным Python 3.9.6 из CommandLineTools со встроенной SQLite 3.54.0; RSS 20512 KiB, открытых дескрипторов 36 | ps -o pid,rss,etime,command -p 45973; grep -n exec ~/.dsh/bridges/agy-bridge/start.sh (строка 23); lsof -p 45973 (36 строк); /usr/bin/python3 -c sqlite3.sqlite_version | 2026-10-29
[F-52] На копии закрытой WAL-БД разговора (без файлов `-wal` и `-shm`) системный Python 3.9.6 открывает её с `mode=ro` с ошибкой `unable to open database file`, с `mode=ro&immutable=1` читает 4 строки, с `mode=ro&nolock=1` падает; Homebrew Python 3.14.7 (SQLite 3.53.4) читает и с `mode=ro`, и с `immutable=1` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/ro_probe.py на dbcopy/t.db обоими интерпретаторами | 2026-10-29
[F-53] Пока на ту же копию открыто читающе-пишущее соединение другого процесса (файл `-shm` существует), системный Python 3.9.6 открывает её с `mode=ro` и читает 4 строки | ro_probe.py, запущенный при живом rw-соединении к dbcopy/t.db | 2026-10-29
[F-54] Лимиты хоста: `launchctl limit maxfiles` 65536 (soft) и unlimited (hard), `ulimit -n` в оболочке 1048576, диапазон эфемерных портов 49152-65535 (16384 порта), `net.inet.tcp.msl` 15000 мс (TIME_WAIT 30 с) | launchctl limit maxfiles; ulimit -n; sysctl net.inet.ip.portrange.first net.inet.ip.portrange.last net.inet.tcp.msl | 2026-10-29
[F-55] Пиковая частота запусков по `bridge.err` — 6 строк `exec` в одну секунду (15:03:40), следующая — 4 (15:27:38) | grep -F " exec model=" bridge.err, группировка по времени uniq -c | 2026-10-29
[F-56] Полный набор `PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/` на HEAD `e00da06`: 3 failed, 896 passed, 8103 subtests passed за 363.6 с; красные тесты вне `agy-bridge`: `test_b_guard.py::TestTm018Guard::test_tm018_live_check_subprocess`, `test_muse_bridge_killpg.py::AllowedModelsSyncTest::test_t00_models_and_health_include_wonder_models_400k`, `test_rpc_rework.py::TestRpcWriteDeadline::test_rw011_shutdown_all_within_budget_with_stuck_child` | /tmp/cel-runs/agy-realtime-reasoning-sa-20261029/baseline-full2.log | 2026-10-29
ARTIFACT_END>>>

<<<ARTIFACT analysis/agy-realtime-reasoning/research-plan.md sha256=81dffc06ac79c490968e7efb8321f464d5963f414fcc6bd67a278a99d5985e32
# Research Plan: agy-realtime-reasoning (реалтайм-размышление `agy-bridge` в DSH)

Роль: System Analyst (Stage 1, preset `analyst-teamlead`), тип — as-is обследование + feasibility study, глубина — standard (S2).
Дата: 2026-10-29 (MSK). Ветка `feature/agy-realtime-reasoning`. Артефакты: `analysis/agy-realtime-reasoning/`.
Владелец вывода: владелец продукта (расхождения «ожидали X, оказалось Y»); финальная архитектура — `architect-software-product`.

## 1. Scope

Запрос владельца: при работе `gemini-4-argon` (Antigravity `agy` 1.4.9) через `agy-bridge` (`127.0.0.1:9887`) в DSH фаза размышления
длится 15-45+ с и в UI ничего не отображается («висит как будто бы не работает»). Нужно видеть размышление в реальном времени.

В периметре: `bridges/agy-bridge/server.py`, `bridges/agy-bridge/fleet.json`, `tests/test_agy_bridge_resilience.py`, `core/watchdog.py` (чтение),
живое состояние `agy` 1.4.9 (`~/.gemini/antigravity-cli/brain/`, `~/.gemini/antigravity-cli/conversations/`), развёрнутый мост
`~/.dsh/bridges/agy-bridge/` и его `bridge.err`, материалы ресерча `/tmp/cel-runs/agy-streaming-research-20261029/` и KB
`tools/dsh-bridges-cli-agent-bridge.md`.
Вне периметра: правка кода, деплой, изменение DSH, смена моделей и аккаунтов, другие мосты.

## 2. Проверяемые гипотезы (исход — в `evidence-ledger.md`)

| Гипотеза | Итог | Основание |
|---|---|---|
| RC-1: у `agy` 1.4.9 в stdout и в `transcript_full.jsonl` нет мышления во время шага генерации | подтверждена | F-27, F-28, F-29 |
| RC-1a: live-источник есть — SQLite `conversations/<cid>.db`, `steps.step_payload`, поле 20.3 | подтверждена замером ресерча и PoC парсера | F-30, F-32, F-33 |
| RC-2: `("done")` ставится в очередь раньше финальной дочитки хвоста, мышление последнего шага теряется | подтверждена по коду; в логах 6 из 28 одношаговых ходов argon без мышления | F-06, F-07, F-08, F-43 |
| RC-3: флаг `delivered` не учитывает отданное мышление | подтверждена по коду; живой случай в логе не найден | F-09, F-10, F-47 |
| RC-4: `sess_key` не различает основной диалог и фоновый запрос без инструментов | подтверждена по коду и парам запросов в логе | F-12, F-13, F-42 |
| Брифовые пути и номера строк точны | частично опровергнута: путь тестов, путь `brain`, строки и период опроса расходятся | F-21, F-36, F-50 |

## 3. Зоны обследования (без пересечений)

- Зона A (код моста): `server.py` строки 97-109, 594-893, 981-1501 — аналитик.
- Зона B (контракт `agy` 1.4.9): stdout `stream-json`, транскрипт, KB-реверс printmode — аналитик по артефактам ресерча.
- Зона C (данные): SQLite `conversations/<cid>.db`, PoC парсера protobuf и сверка с транскриптом в `/tmp` — аналитик.
- Зона D (рантайм): plist, деплой, `/health`, `bridge.err` — Task explorer (read-only), параллельно зонам A-C.

## 4. Методология

1. Факт или открытый вопрос: каждое утверждение — строка `[F-NN]` с источником и датой, иначе запись в `open-questions.md`.
2. Эмпирика важнее чтения: тайминги взяты из живого замера ресерча (`checks.tsv`, KB), PoC парсера прогнан на реальных БД в режиме только чтения.
3. Секреты не выносятся: ключ моста не читался, из логов взяты счётчики и строки без токенов.
4. Код продукта не менялся; PoC и логи — `/tmp/cel-runs/agy-realtime-reasoning-sa-20261029/`.
5. Архитектура не выбирается: варианты сравниваются в `handoff-architect.md` с вердиктом «выполнимо / с условиями / невыполнимо».
6. Живой прогон agy в этом анализе не делался: квота аккаунта исчерпана (F-46), использованы замеры ресерча того же дня.

## 5. Реестр спайков

Формат строки: `ID | вопрос | источник | метод | таймбокс | deliverable | критерий закрытия | зависит/блокирует | статус | результат | факт | отметка` (таймбокс и факт — минуты).

INV-01 | Где теряется живое мышление на пути от agy до SSE | server.py:594-893 и 981-1101 | чтение кода по строкам | 20 | карта потока в handoff-architect | найден путь reasoning от источника до клиента | блокирует INV-07 | closed | F-03 | 15 | ok
INV-02 | Отдаёт ли agy 1.4.9 мышление в stdout stream-json | live_stream_json.jsonl и KB-реверс printmode | сверка живого потока и реверса | 15 | факт о составе событий | показан полный состав событий хода | нет | closed | F-27 | 10 | ok
INV-03 | Когда пишется transcript_full.jsonl относительно result | KB замер cid 82188e72 и checks.tsv | сверка таймингов | 15 | тайминги записи | тайминги записи шага и result зафиксированы | нет | closed | F-29 | 10 | ok
INV-04 | Есть ли live-источник мышления в SQLite и как его разобрать | ~/.gemini/antigravity-cli/conversations/<cid>.db | PoC парсера wire-формата в /tmp | 30 | poc_pb.py и схема steps | подполе 20.3 извлечено на реальной БД | нет | closed | F-32 | 20 | ok
INV-05 | Совпадает ли мышление SQLite и транскрипта по шагу | три разговора 2026-10-29 | PoC сравнения cmp2.py | 15 | таблица равенства | равенство по idx и step_index показано | зависит от INV-04 | closed | F-33 | 10 | ok
INV-06 | Режим журнала БД и чтение только на чтение | заголовок файла БД и sqlite3 | xxd, file, PoC на Python | 15 | факт о WAL и режиме ro | режим журнала и способ открытия установлены | нет | closed | F-34 | 10 | ok
INV-07 | Гонка финального дренирования хвоста и done | server.py:807-868 и 981-1101; bridge.err | чтение кода и статистика логов | 25 | доля ходов без мышления | механизм и частота зафиксированы | зависит от INV-01 | closed | F-43 | 20 | ok
INV-08 | Учитывает ли флаг delivered отданное мышление | server.py:1103-1187 | чтение кода | 15 | условие повтора | условие повтора описано | нет | closed | F-09 | 10 | ok
INV-09 | Коллизия sess_key с фоновыми запросами DSH | server.py:477-516 и 1368-1385; bridge.err | код и пары exec-строк | 20 | примеры пар | найдены пары основной плюс фоновый | нет | closed | F-42 | 15 | ok
INV-10 | Базовая линия тестов моста и полного набора | tests/ | unittest и uvx pytest | 15 | логи прогонов | результат зафиксирован | нет | closed | F-23 | 10 | ok
INV-11 | Деплой и рантайм моста :9887 | plist, ~/.dsh/bridges/agy-bridge, /health | Task explorer read-only | 15 | факт о деплое | путь деплоя и sha256 сверены | нет | closed | F-38 | 10 | ok
INV-12 | Растёт ли поле 20.3 строго префиксно между снимками status=8 | живой опрос БД во время генерации | ряд снимков payload | 20 | ряд снимков | префиксное свойство проверено | нет | open | OPEN-01 | 0 | живой прогон не делался: квота исчерпана (F-46)

## 6. Статус выполнения

- Закрыто 11 из 12 спайков; спайк о префиксном росте поля 20.3 переведён в `open-questions.md` с рабочим допущением (класс «МОЖНО ПРОДОЛЖИТЬ»).
- Таймбоксы не превышены.
- Выходы: `evidence-ledger.md` (F-01..F-50), `open-questions.md`, `handoff-architect.md`, `handoff-qa.md`.
- Потребители: Архитектор (`handoff-architect.md`), QA (`handoff-qa.md`); `handoff-dev.md` не готовится (класс S2, вход в разработку через ARCH_GATE).
ARTIFACT_END>>>

<<<ARTIFACT analysis/agy-realtime-reasoning/open-questions.md sha256=47b16bab51b31bb06c35fb02d08dbd3409a9cfb057a52e828d079054a20d9202
# Open Questions: agy-realtime-reasoning

Дата: 2026-10-29 (MSK). Блокеров нет: ни один вопрос не останавливает ветку Архитектора, все вопросы класса «МОЖНО ПРОДОЛЖИТЬ».
Статус записан префиксом в поле «что мешает закрыть»: `CLOSED` — закрыт фактами ledger, `ASSUMPTION` — открыт, но закрыт рабочим допущением,
`DEFERRED` — отложен с рабочим допущением. Статусов `open` без допущения нет.
Формат строки — по канону скилла (`OPEN-NN | класс | вопрос | что мешает закрыть | кто нужен | риск | допущение`), а не markdown-таблица из брифа:
оракул `SA-DOD-004` принимает только такой формат строк. Смысловые колонки брифа сохранены: «Допущение / закрытие» — поля 4 и 7, «Статус» — префикс поля 4.

OPEN-01 | МОЖНО ПРОДОЛЖИТЬ | Растёт ли текст поля 20.3 строго префиксно между снимками строки в status=8 | ASSUMPTION: ряд промежуточных payload не сохранялся, подтверждены только монотонный рост размера (F-30) и равенство финального текста транскрипту (F-33) | Coder-спайк, QA | при непрефиксной перезаписи `_reasoning_suffix` отдаёт текст шага целиком повторно (F-04) | Рост префиксный; непрефиксный снимок не приводит к повторной выдаче уже отданного текста (REQ-003)
OPEN-02 | МОЖНО ПРОДОЛЖИТЬ | Держит ли agy БД разговора открытой (с файлом `-shm`) всё время хода, чтобы системный Python 3.9.6 мог читать её в режиме `mode=ro` | ASSUMPTION: боевой Python 3.9.6 не открывает закрытую WAL-БД с `mode=ro` (F-52), но открывает при живом пишущем соединении (F-53); живой опрос ресерча прошёл (F-30), интерпретатор того опроса не записан | Coder-спайк на `/usr/bin/python3` | на дренировании после выхода agy и до первого открытия БД чтение падает | Во время хода чтение `mode=ro` работает; ошибка открытия трактуется как «изменений нет», источник fail-open, а окно после выхода agy закрывает транскрипт или `immutable=1` по выбору Архитектора (REQ-004, REQ-006)
OPEN-03 | МОЖНО ПРОДОЛЖИТЬ | Стабильны ли номера полей (`step_type=15`, `status=8`, поле 20, подполе 3) между версиями agy | ASSUMPTION: схема внутренняя и не документирована, бинарь обновляется фоновым автоапдейтером (F-25, F-28) | владелец, Architect | после обновления agy источник молча перестанет давать дельты | Привязка к 1.4.9; несовпадение схемы распознаётся и логируется, мышление продолжает идти из транскрипта (REQ-004, REQ-012)
OPEN-04 | МОЖНО ПРОДОЛЖИТЬ | Чем вызваны 6 одношаговых ходов argon без мышления: гонкой дренирования, пустым мышлением модели или смещением хвоста при продолжении треда | ASSUMPTION: 4 из 6 случаев — продолжения (turns 2-3), лог не различает причины (F-43) | QA | неверная оценка вклада RC-2 | Все три причины закрываются требованиями REQ-005 и REQ-006 вместе
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | Совпадает ли `cwd` фонового запроса DSH (генерация заголовка) с `cwd` основного диалога | ASSUMPTION: `cwd` в `bridge.err` не пишется; пары запросов видны (F-42), коллизия ключа следует из кода (F-12, F-13) | QA на живом DSH | изоляция по одному признаку `tools` окажется неполной | Совпадает; изоляция обязательна независимо от `cwd`
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | Какой финальный SSE-исход нужен, если сбой случился после уже отданного мышления: кадр `error` или `stop` с частичным ответом | ASSUMPTION: KB фиксирует затирание блока мышления кадром ошибки (F-47), в `bridge.err` случай не подтверждён | владелец, Architect | регрессия отображения в DSH | Невидимый повтор после отданного мышления запрещён; выбор финального кадра за Архитектором
OPEN-07 | МОЖНО ПРОДОЛЖИТЬ | Можно ли провести живую приёмку L3 при исчерпанной квоте agy | ASSUMPTION: квота аккаунта сбрасывается примерно через 54 ч от 01:09 MSK 2026-10-29 (F-46) | владелец | L3 откладывается | L3 выполняется на аккаунте с квотой (переключение штатным `antigravity-account-switch.sh`) или после сброса
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | Какие числовые цели отзывчивости принимает владелец | ASSUMPTION: владелец сформулировал проблему без чисел | владелец | критерии приёмки останутся субъективными | Первая дельта мышления не позже 5 с после начала генерации шага; интервал между дельтами в фазе мышления не больше 6 с (максимум интервала записи в F-30 равен 5.1 с); добавка финального дренирования к времени хода не больше 1.0 с
OPEN-09 | МОЖНО ПРОДОЛЖИТЬ | Обновлять ли `fleet.json technical_ref.agy_version` и комментарии про 1.3.1 | DEFERRED: на поведение не влияет (F-26, F-01, F-18) | Architect | путаница в документации моста | Входит в MR как документационная правка
OPEN-10 | МОЖНО ПРОДОЛЖИТЬ | Исправлять ли трактовку `text_delta` как накопительного снимка | ASSUMPTION: вывод сейчас корректен благодаря ветке «не префикс → весь текст» (F-18, F-04); сбой возможен, только если новая дельта начинается с текста предыдущей | Architect | редкая потеря фрагмента видимого текста | Вне объёма этого MR, фиксируется как риск
OPEN-11 | МОЖНО ПРОДОЛЖИТЬ | Подходит ли локальный `~/.gemini/antigravity-cli/bin/agentapi` как альтернативный live-источник | DEFERRED: не исследовался в этом анализе | Architect | пропущен более устойчивый API | Не рассматривается, основной кандидат — чтение SQLite
OPEN-12 | МОЖНО ПРОДОЛЖИТЬ | Пригоден ли режим `immutable=1` для опроса БД | ASSUMPTION: на закрытой БД `immutable=1` читает на обоих интерпретаторах (F-52); `immutable=1` сообщает SQLite, что файл не меняется, поэтому для БД, в которую agy ещё пишет, он не годится | Coder-спайк | чтение устаревших страниц во время хода | Во время хода используется `mode=ro`; `immutable=1` допустим только после выхода процесса agy
OPEN-13 | МОЖНО ПРОДОЛЖИТЬ | Где лежат тесты моста и как запускать полный набор | CLOSED: тесты в `tests/test_agy_bridge_resilience.py` (F-21), набор моста зелёный через `unittest` (F-23), полный набор требует `PYTHONPATH=.` (F-24) | никто | нет | не требуется
OPEN-14 | МОЖНО ПРОДОЛЖИТЬ | Верны ли пути из брифа к `brain` и к релизу agy | CLOSED: каталог разговора — `~/.gemini/antigravity-cli/brain/<cid>/` (F-36), каталога `releases/` нет, бинарь — `~/.local/bin/agy.real` (F-25) | никто | нет | не требуется
OPEN-15 | МОЖНО ПРОДОЛЖИТЬ | Существует ли `_LAST_CONV`, упомянутый в брифе | CLOSED: переменной нет, её роль выполняет `_session_store` (F-14) | никто | нет | не требуется
OPEN-16 | МОЖНО ПРОДОЛЖИТЬ | Входят ли 3 красных теста полного набора вне `agy-bridge` в объём этого MR | DEFERRED: тесты относятся к `b_guard`, `muse-bridge` и `rpc`, на HEAD до изменений уже красные (F-56) | владелец, Architect | Full Suite Gate перед MR не будет полностью зелёным | Не входят; в отчёте MR фиксируется, что набор красных тестов до и после изменений совпадает

## ВОПРОСЫ ВЛАДЕЛЬЦУ

1. [МОЖНО ПРОДОЛЖИТЬ] Принимаете ли цели: первая дельта мышления до 5 с от начала генерации, интервал между дельтами до 6 с, добавка дренирования до 1.0 с? Почему нужен: от них зависят период опроса и критерии приёмки. Допущение: приняты. После ответа: QA фиксирует пороги в L3.
2. [МОЖНО ПРОДОЛЖИТЬ] Какой финальный кадр показывать, если сбой случился после отданного мышления: ошибку или частичный ответ со `stop`? Почему нужен: от этого зависит, сохранится ли блок Think в DSH. Допущение: выбор за Архитектором, невидимый повтор запрещён. После ответа: Архитектор фиксирует контракт.
3. [МОЖНО ПРОДОЛЖИТЬ] Живую приёмку L3 вести на другом аккаунте agy (квота текущего исчерпана) или ждать сброса около 54 ч? Почему нужен: без L3 сдача тяжёлым путём невозможна. Допущение: переключение аккаунта штатным скриптом. После ответа: QA планирует окно L3.
ARTIFACT_END>>>

<<<ARTIFACT analysis/agy-realtime-reasoning/handoff-qa.md sha256=5ed84fc039f7fea5983404442461e734ec9dae03f57359e2bb441dfae6cb7afe
# Handoff to QA: реалтайм-размышление `agy-bridge` (:9887) для `gemini-4-argon` (agy-realtime-reasoning)

Дата: 2026-10-29 (MSK). Автор: System Analyst (Stage 1). Потребитель: QA / Verifier и Coder (тесты red→green до фикса).
Требования и критерии — `handoff-architect.md` (REQ-001..REQ-012, AC-001..AC-016); факты — `evidence-ledger.md` (F-01..F-56); допущения — `open-questions.md`.
Ниже — матрица проверок, тест-кейсы и протокол живой приёмки. Формулировки AC не переписываются: здесь только способ проверки.

## 1. Тестовые контуры и команды

| Контур | Команда | Факт базовой линии |
|---|---|---|
| L1 тесты моста | `cd ~/tmp/cli-agent-bridge/agy-realtime-reasoning && /usr/bin/python3 -m unittest tests.test_agy_bridge_resilience` | 22 теста OK за 2.1 с (F-23) |
| L1 полный набор | `cd ~/tmp/cli-agent-bridge/agy-realtime-reasoning && PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/` | 3 failed вне agy-bridge, 896 passed, 363.6 с (F-56); без `PYTHONPATH` падает сборка (F-24) |
| L2 интеграция без сети | фейковый лончер `AGY_LAUNCHER=<скрипт>` плюс фикстурные `AGY_BRIDGE_BRAIN` и каталог БД во временной папке | у моста есть переменные `AGY_LAUNCHER`, `AGY_BRIDGE_BRAIN` (F-01, F-05) |
| L3 живая приёмка | боевой мост `127.0.0.1:9887`, DSH, `gemini-4-argon --effort high` | раздел 6 |

Интерпретатор для L1 парсера и SQLite-кейсов — обязательно `/usr/bin/python3` 3.9.6 (боевой рантайм, F-51); Homebrew 3.14 ведёт себя
иначе на закрытой WAL-БД (F-52), поэтому зелёный прогон только на 3.14 не засчитывается.

## 2. Матрица верификации AC

| AC | REQ | Уровень | Способ проверки | Кейсы |
|---|---|---|---|---|
| AC-001 | REQ-001 | L2 | фикстура БД с растущим подполем 20.3 каждые 1.5 с; счёт чанков `reasoning_content` до перехода в `status=3` | TC-20, TC-21 |
| AC-002 | REQ-001 | L2 | метки времени записи снимка и прихода чанка на клиентском сокете | TC-22 |
| AC-003 | REQ-002 | L1 | unit-набор парсера на `/usr/bin/python3` | TC-01..TC-12 |
| AC-004 | REQ-003 | L2 | склейка чанков против финальных `thinking` транскрипта | TC-30, TC-31 |
| AC-005 | REQ-003 | L1/L2 | непрефиксный снимок 20.3 | TC-32 |
| AC-006 | REQ-004 | L2 | БД отсутствует, заблокирована, битая, чужая схема | TC-40..TC-44 |
| AC-007 | REQ-005 | L2 | продолжение треда с шагами прошлого хода в БД и транскрипте | TC-50, TC-51 |
| AC-008 | REQ-006 | L2 | фейковый agy с записью шага через 90 мс после `result`, 100 прогонов | TC-60, TC-61 |
| AC-009 | REQ-007 | L2 | время от EOF stdout до чанка `stop` | TC-62 |
| AC-010 | REQ-008 | L2 | мышление, затем `result` ERROR; счёт запусков и повторных чанков | TC-70, TC-71 |
| AC-011 | REQ-009 | L2 | агентный ход, фоновый без tools, агентный ход | TC-80..TC-82 |
| AC-012 | REQ-010 | L1 | 22 существующих теста без правок | TC-90 |
| AC-013 | REQ-010 | L2 | побайтовое сравнение мышления | TC-30 |
| AC-014 | REQ-011 | L1 | переключатель выключен, подменённый `sqlite3.connect` не вызывается | TC-91 |
| AC-015 | REQ-012 | L2 | строки источника в stderr без текста мышления | TC-92 |
| AC-016 | REQ-012 | L2 | CPU потока опроса за 60 с | TC-93 |

## 3. Тест-кейсы red→green (регрессионные тесты пишутся до фикса)

Каждый кейс: вход → ожидаемый результат. «Красный на HEAD» означает, что кейс обязан падать на `e00da06` и проходить после фикса.

### 3.1. Парсер wire-формата `step_payload` (REQ-002, AC-003)

Фикстуры собираются вручную из байтов (тег = `field << 3 | wire_type`, длина — varint). Реальный пример формы: `step_type=15`, поле 20,
подполя 1, 3, 6, 8 (F-32).

- TC-01 (позитив): поле 20 с подполем 3 = `"abc"` → `"abc"`.
- TC-02 (многобайтовый varint длины): подполе 3 длиной 300 байт (длина кодируется 2 байтами `0xAC 0x02`) и 70000 байт (3 байта) → текст полностью.
- TC-03 (многобайтовый тег): тег поля 20 занимает 2 байта (`0xA2 0x01`, как в F-32) → разбирается; поле с номером больше 2^14 → пропускается.
- TC-04 (UTF-8 кириллица): подполе 3 = `"Размышляю о задаче"` → тот же текст; многобайтовый символ на границе снимка не порождает `�` в склейке.
- TC-05 (битый UTF-8): подполе 3 с последовательностью `0xFF 0xFE` → без исключения, поведение замены символов зафиксировано тестом.
- TC-06 (wire type 0): перед полем 20 varint-поля 1 и 2 → пропускаются.
- TC-07 (wire type 1): fixed64-поле перед полем 20 → пропускается на 8 байт.
- TC-08 (wire type 5): fixed32-поле → пропускается на 4 байта.
- TC-09 (wire type 2 чужой): length-delimited поля 4, 21 → пропускаются; повторяющееся подполе 6 (`ToolCall`) не влияет на 20.3.
- TC-10 (неподдерживаемые wire types 3, 4, 6, 7): разбор останавливается без исключения, результат «мышления нет».
- TC-11 (усечение): payload из TC-02, обрезанный на каждой позиции от 0 до `len-1` → ни одного исключения, результат либо пустой, либо префикс без мусора.
- TC-12 (нет поля 20 / пустой payload / `None`) → «мышления нет».

### 3.2. Живой источник SQLite (REQ-001, AC-001, AC-002)

Фикстура: временная БД со схемой `steps` из F-31 в режиме WAL, writer в отдельном процессе обновляет строку `idx=3, step_type=15, status=8`
каждые 1.5 с, текст 20.3 растёт: 523 → 810 → 1088 → 1419 → 2156 байт (ряд из F-30), затем `status=3`.

- TC-20: клиент получает не меньше 2 чанков мышления до `status=3` (красный на HEAD: мост читает только транскрипт, F-01).
- TC-21: шаг без мышления (`step_type=90`, F-32) → ни одного чанка мышления.
- TC-22: задержка от коммита снимка до записи чанка в сокет не больше периода опроса плюс 0.5 с (по меткам времени).
- TC-23 (граница): writer обновляет снимок чаще периода опроса (каждые 0.1 с) → итоговая склейка всё равно равна финальному тексту.
- TC-24 (многошаговый ход): шаги `idx=3` и `idx=7` с мышлением → порядок чанков совпадает с порядком шагов.

### 3.3. Дедупликация SQLite и транскрипта (REQ-003, AC-004, AC-005, AC-013)

- TC-30: оба источника видят шаг `idx=3 == step_index=3` с одинаковым финальным текстом (как в F-33) → склейка `reasoning_content` побайтово равна `thinking` один раз.
- TC-31: транскрипт отдаёт шаг раньше БД (порядок источников обратный) → дублей нет.
- TC-32: снимок 20.3 сменился непрефиксно (`"abc"` → `"abX..."`) → уже отданный текст не повторяется (на HEAD `_reasoning_suffix` вернул бы текст целиком, F-04).
- TC-33: кириллица и ASCII-шаги (как `fa92a264` и `57172100`, F-33) → равенство склейки.

### 3.4. Fail-open SQLite (REQ-004, AC-006)

- TC-40: файла БД нет → ход `done`, мышление из транскрипта как на HEAD.
- TC-41: закрытая WAL-БД без `-shm` на `/usr/bin/python3` с `mode=ro` (ошибка `unable to open database file`, F-52) → исключение не выходит наружу, ход `done`.
- TC-42: БД под эксклюзивной блокировкой writer'а (`BEGIN EXCLUSIVE` в другом процессе) → опрос пропускается, ход не зависает дольше REQ-007.
- TC-43: таблицы `steps` нет или нет колонки `step_payload` → «мышления нет», одна диагностическая строка в stderr, ход `done`.
- TC-44: мусор вместо файла БД (случайные байты) → то же, что TC-43.

### 3.5. Продолжение треда (REQ-005, AC-007)

- TC-50: БД содержит шаги `idx=0..3` прошлого хода с мышлением, запуск с `--conversation` → клиент получает мышление только новых шагов `idx>=4`.
- TC-51: транскрипт содержит записи прошлого хода, а новая запись появляется через 50 мс после `init` → новая запись не теряется (кейс для одного из объяснений 6 ходов без мышления, F-43).

### 3.6. Финальное дренирование (REQ-006, REQ-007, AC-008, AC-009)

Фейковый лончер печатает `init`, через 1 с `result`, сразу выходит, а отдельный процесс дописывает `PLANNER_RESPONSE` в транскрипт через 90 мс после `result` (F-29).

- TC-60: чанк мышления приходит раньше `finish_reason="stop"` в 100 из 100 прогонов (красный на HEAD: F-06, F-07, F-08).
- TC-61: нестриминговый запрос (`stream=false`) содержит `message.reasoning_content` (F-19) в 100 из 100 прогонов.
- TC-62: источники молчат → время от EOF до `stop` не больше 1.0 с.
- TC-63 (граница): запись появляется через 1.5 с после выхода → ход завершается в пределах REQ-007 без мышления, без зависания и без исключения.

### 3.7. Учёт выдачи при сбое (REQ-008, AC-010)

- TC-70: фейковый agy отдаёт шаг с мышлением, затем `result` со `status=ERROR` и `Individual quota reached` (F-46) → 1 запуск процесса, чанки мышления не повторяются (красный на HEAD: `delivered` без `reasoning`, F-09).
- TC-71: горячая сессия, мышление отдано, затем `agy_error` → нет холодного повтора с полной историей поверх отданного потока.
- TC-72 (негатив): сбой до любой выдачи → прежний невидимый повтор сохраняется (as-is, F-09).

### 3.8. Изоляция горячих сессий (REQ-009, AC-011)

- TC-80: агентный запрос (`tools` из 34 элементов) → `done` с `cid=A`; фоновый запрос той же модели, `cwd`, effort без `tools`, одно сообщение → не получает `cid=A`; следующий агентный запрос → `resume=1` с `cid=A` (красный на HEAD: F-12, F-13).
- TC-81: фоновый запрос стартует, пока агентный ход держит `cid=A` (`_in_flight_cids`), и завершается раньше → запись горячей сессии агентного диалога остаётся `A`.
- TC-82: два фоновых запроса подряд → между собой могут делить сессию или нет (решение Архитектора), агентную не трогают.

### 3.9. Совместимость, переключатель, наблюдаемость (REQ-010..REQ-012)

- TC-90: 22 теста `tests/test_agy_bridge_resilience.py` зелёные без правок; полный набор — те же 3 красных теста, что на HEAD (F-56), новых красных нет.
- TC-91: переключатель SQLite-источника выключен → `sqlite3.connect` не вызывается, поведение совпадает с HEAD по TC-60 ожиданиям после фикса RC-2.
- TC-92: stderr после TC-20 содержит строки источника с cid-префиксом, шагом, длиной и не содержит текста мышления фикстуры.
- TC-93: CPU потока опроса за 60 с при 8 параллельных фикстурах не больше 2% ядра на ход.

## 4. Режимы отказа и краевые случаи

| Режим | Источник | Ожидание |
|---|---|---|
| Квота аккаунта исчерпана | F-46 | ход завершается `agy_error`, отданное мышление не дублируется (TC-70) |
| Автоапдейт agy меняет схему | F-25, F-28 | SQLite-источник молча отключается, транскрипт работает (TC-43) |
| Закрытая WAL-БД на Python 3.9.6 | F-52 | fail-open (TC-41) |
| Запись шага после `result` | F-29 | дренирование (TC-60) |
| Параллельный фоновый запрос DSH | F-42 | изоляция сессий (TC-80, TC-81) |
| Клиент ушёл посреди мышления | F-07, F-11 | `client_gone`, группа процессов убита, источники остановлены |
| Шесть ходов стартуют в одну секунду | F-55 | независимые опросы, без общих блокировок |

## 5. Тестовые данные и стенды

- Реальные БД для сверки формы (только чтение, не коммитить в репозиторий): `~/.gemini/antigravity-cli/conversations/82188e72-6eca-4f23-a0b3-2257ec43bd60.db`, `fa92a264-8039-40dc-a716-37f7f64ea9e3.db`, `57172100-e4cf-4553-a0b6-f0af14c28a80.db` (F-33). Тексты мышления в фикстуры не копируются — синтетические строки.
- PoC парсера и сравнения: `/tmp/cel-runs/agy-realtime-reasoning-sa-20261029/poc_pb.py`, `cmp2.py`, `ro_probe.py` (не продуктовый код, только эталон формы).
- Ряд размеров снимков для фикстуры: 523, 810, 1088, 1419, 2156 байт с интервалами 1.53, 2.78, 5.09, 3.30 с (F-30).

## 6. Живая приёмка L3 на `:9887` (тяжёлый путь)

Предусловия: MR-ветка прошла панели; квота аккаунта agy доступна (сейчас исчерпана, F-46, решение по аккаунту — у владельца);
каталог деплоя `~/.dsh/bridges/agy-bridge/` — копия, не симлинк (F-38).

1. Бэкап боевого `server.py` в `~/work/backups/agy-bridge-<ts>/`, копирование нового `server.py` в `~/.dsh/bridges/agy-bridge/`, сверка sha256 с репозиторием.
2. Рестарт: `launchctl kickstart -k gui/$(id -u)/com.user.dsh-agy-bridge`; `curl -s -m 3 http://127.0.0.1:9887/health` — `ok=true` (лёгкий путь, недостаточен).
3. Сценарий S1 (одношаговый ход с долгим мышлением): в существующем рабочем чате DSH выбрать `gemini-4-argon`, effort high, задать вопрос, требующий рассуждения 20+ с. Зафиксировать: время до первой строки Think, число обновлений блока Think до появления ответа, наличие мышления после завершения хода.
4. Параллельно S1 снять поток напрямую: `curl -sN http://127.0.0.1:9887/v1/chat/completions -H "Authorization: Bearer $AGY_BRIDGE_KEY" -d '{"model":"gemini-4-argon","stream":true,"messages":[...]}' | while IFS= read -r l; do printf '%s %s\n' "$(date +%s.%N)" "${l:0:80}"; done` — ключ только из окружения, не печатать. Критерии: первый чанк `reasoning_content` не позже 5 с от начала генерации шага, интервалы между чанками мышления не больше 6 с, чанк мышления раньше `stop`.
5. Сценарий S2 (агентный ход с инструментами, 3+ шага): блок Think обновляется по шагам во время работы, а не пачкой в конце; в `bridge.err` есть строки SQLite-источника.
6. Сценарий S3 (изоляция сессий): новый чат DSH, два хода подряд с инструментами; DSH сам шлёт фоновый запрос заголовка (пара `tools=0` в ту же секунду, F-42). Проверка: второй агентный ход в `bridge.err` с `resume=1` и тем же `conversation=` префиксом, что первый; ответ второго хода опирается на контекст первого.
7. Сценарий S4 (повторы): три хода S1 подряд и два параллельных чата — у всех ходов есть мышление (сравнить с базовой линией 6 из 28 без мышления, F-43).
8. Сбор фактов: выдержка `bridge.err` (без ключей), метки времени чанков, скриншот блока Think DSH; путь — `~/Мой диск/tmp/trace/2026-10-29/agy-realtime-reasoning/<run-id>/`.
9. Откат при провале: вернуть бэкап, `launchctl kickstart -k`, `/health`, один живой ход S1.

Отчёт L3 по форме: `ПРОВЕРЕНО ЛЁГКИМ` / `ПРОВЕРЕНО ТЯЖЁЛЫМ` (сценарий + факт) / `НЕ ПРОВЕРЕНО`; при непустом «НЕ ПРОВЕРЕНО» сдача не засчитывается.

## 7. Риски приёмки

- Квота аккаунта agy исчерпана (F-46): L3 откладывается или идёт на другом аккаунте.
- Расхождение интерпретаторов: зелёные L1 на Python 3.14 при красных на `/usr/bin/python3` 3.9.6 (F-51, F-52).
- Полный набор уже красный в 3 тестах вне моста (F-56): сравнивать наборы красных тестов до и после.
- Номера полей protobuf привязаны к agy 1.4.9 (F-25, F-28): после автоапдейта L3 повторяется.

## 8. Трассируемость

REQ-001 → TC-20..TC-24; REQ-002 → TC-01..TC-12; REQ-003 → TC-30..TC-33; REQ-004 → TC-40..TC-44; REQ-005 → TC-50, TC-51;
REQ-006 → TC-60, TC-61, TC-63; REQ-007 → TC-62, TC-63; REQ-008 → TC-70..TC-72; REQ-009 → TC-80..TC-82; REQ-010 → TC-90, TC-30;
REQ-011 → TC-91; REQ-012 → TC-92, TC-93. L3: S1..S4.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md sha256=7e606a52d977e281e8eedc9f0482a0d8d83008a2106fc3d27bee00f3c62d384a
# AGENTS

Ты работаешь в Python backend-проекте на Litestar.

## Язык общения

Пользователь — носитель русского языка, поэтому общение в чате и любой текст, который человек читает глазами (docstrings, комментарии в коде, **описания коммитов**), — на русском. Идентификаторы (имена переменных, функций, классов, файлов) — на английском, как принято в коде.

| Где | Какой язык |
|---|---|
| Сообщения в чате (планы, статус, объяснения, ответы на вопросы) | Русский |
| Сообщения в чате при ошибках/конфликтах | Русский |
| Commit messages — **тэги** (`feat:`, `fix:`, `refactor:`, `chore:`, scope) | Английский — это формат Conventional Commits, парсится changelog-генераторами |
| Commit messages — **описание** после двоеточия | **Русский** — это текст для команды, его читают люди |
| Префиксы `[agent]` / `[manual]` / `[assisted]` | Английский — это маркер, не текст |
| Docstrings в коде | Русский — пользователь читает их в IDE через hover |
| Комментарии в коде (`# объясняет почему`) | Русский |
| Названия переменных, функций, классов, файлов | Английский |

Если поймал себя что начал писать описание коммита или docstring по-английски — остановись и переформулируй по-русски.

Примеры docstring:

✅ Правильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Обрезает URL до max_length символов, добавляя '...' в конце.

    Args:
        url: URL для обрезки.
        max_length: Максимальная длина результата (по умолчанию 50).

    Returns:
        Обрезанный URL с эллипсисом, либо исходный URL если он короче max_length.

    Raises:
        ValueError: Если max_length меньше длины эллипсиса.
    """
    # Если URL уже короткий — возвращаем как есть, без аллокации
    if len(url) <= max_length:
        return url
    ...
```

❌ Неправильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate a URL to max_length characters, adding ellipsis at the end.
    ...
    """
    # Return as-is if URL is already short
    ...
```

## Главные правила

1. Сначала прочитай этот файл и релевантные тематические файлы из `.agents/`.
2. **При ошибке — Identify → Assess → Communicate → Solutions.** Не предлагай
   workaround сразу — сначала пойми, почему упало. Severity-уровни и алгоритм
   реакции — в `.agents/agents/error-handling.md`.
3. Не меняй архитектуру проекта без явной причины.
4. Все изменения должны быть минимально достаточными.
5. Любое изменение кода должно сопровождаться проверкой:
   - `uv run ruff check .`
   - `uv run basedpyright`
   - `uv run pytest -q`
6. Для изменений схемы и БД читай `.agents/agents/database.md`.
7. Если меняется публичное API, обнови тесты и README.
8. Перед подготовкой MR прочитай `.agents/agents/mr.md`.
9. Для hotfix обязательно прочитай `.agents/agents/hotfix.md`.
10. На каждый баг должен появиться regression test.
11. Не добавляй зависимости без необходимости.
12. Перед началом работы создай ветку по правилу именования веток проекта.
13. Архитектурные решения с ≥ 2 альтернативами и дорогим откатом оформляй как
    ADR с options analysis (см. `.agents/agents/docs.md`, раздел «ADR-full»).
14. Если задача дата-инженерная (ETL, Airflow DAG, Kafka-воркеры, ClickHouse,
    выгрузка в S3) — читай `.agents/agents/data-engineering.md`.
15. **Согласованный внешний контракт не менять без явного указания в текущей
    задаче.** HTTP/event/data/CLI/SDK, уже согласованные с внешними
    исполнителями, заморожены. «Улучшить», соседняя задача, свой архитектурный
    черновик — не разрешение. Нет явной фразы «измени контракт / breaking /
    обнови схему» → STOP, ASK. Канон: `.agents/agents/scope-and-contracts.md`.
16. **Работать только в рамках своей задачи.** Scope = текущий промпт и текущий
    Jira-KEY. Чужие KEY/MR не открывать, не чинить и не отчитываться по их
    статусу «заодно». Чужой тикет — только если текущая постановка явно
    называет его зависимостью, и тогда только факт зависимости. Канон: тот же
    `scope-and-contracts.md`.
17. **Сдача — через MR на remote, если remote есть.** Не коммитить и не пушить
    в `main` / `master` / `dev`. Коммит живёт на своей ветке, затем push + MR.
    Канон: `.agents/agents/mr.md`. Merge MR — человек, пока не сказано «смержи».
    После merge на remote обязательно обновить локальную target-ветку через
    fast-forward и сверить её `HEAD` с remote. Локальный merge до MR запрещён.

## Подход к работе

Поведение агента управляется **правилами** (`.agents/`) и **алгоритмами**
(`.skills/`). Это конвейер: пришла задача → агент читает релевантный skill →
выполняет шаги → проверки → коммит на своей ветке → MR на remote (если remote есть).
Отдельный «план в чате с ожиданием ОК»
не требуется — `.skills/*.md` уже содержит пошаговый алгоритм.

Если задача сложная и хочется разведать прежде чем писать код:

- **Используй встроенный Plan mode** AI-IDE (в Claude Code, Cursor, Continue,
  Codex CLI). В этом режиме агент только читает файлы и описывает что
  собирается сделать, не пишет и не запускает команды. Это быстрее и дешевле
  чем эмуляция через «покажи план в чате, жди подтверждения».
- **Артефакты задачи** (заметки, отчёты code review, ADR, временные
  результаты) можно складывать в `Tasks/<JIRA-KEY>/` рядом с кодом, чтобы
  при возврате к задаче через день было видно где остановились. Это
  опциональный паттерн, не обязательное «всегда пиши план в md».
- **Architecture-документ** для большой задачи (≥ 1 дня работы, несколько
  модулей, breaking change) — отдельный жанр, см. `.agents/skills/architecture.md`.
  Это не «approval gate», это рабочий артефакт с C1+C2 диаграммами и
  списком задач T1-TN.

В конце задачи — короткий отчёт с URL MR (или явно «remote нет»). Не ждать
фразы «делай MR». Правки оператора — уже после открытого MR, не вместо него.

## Правила именования веток

Ветки должны называться в соответствии с типом задачи и Jira key.

Формат ветки:

`<type>/<JIRA-KEY>-<short-description>`

Где:
- `type` — тип задачи: `feature`, `bugfix`, `hotfix`, `deploy` (релиз/выкат — см. `.agents/skills/devops-release.md`)
- `JIRA-KEY` — идентификатор задачи в Jira, например `PROJ-123`
- `short-description` — короткое описание в `kebab-case`

Примеры:
- `feature/PROJ-123-add-link-archive`
- `bugfix/PROJ-456-fix-empty-title-validation`
- `hotfix/PROJ-789-fix-production-db-timeout`

Правила:
- использовать латиницу, цифры, `/` и дефисы;
- не использовать пробелы;
- не использовать длинные описания;
- для задач из Jira всегда включать Jira key в имя ветки;
- тип ветки должен соответствовать типу задачи.

## Правила коммитов и измерение вклада агента

Каждый коммит должен быть помечен тегом в начале сообщения:

- `[agent]` — diff агента принят без существенных правок (точечные правки имён/форматирования допустимы)
- `[assisted]` — основу сделал агент, но ты переписал значимую часть (логика, структура, >20% строк)
- `[manual]` — код написан вручную без участия агента

Три тега вместо двух нужны потому, что бинарное деление «агент/не агент» врёт в сторону агента: коммит, где ты взял идею из diff и переписал половину, честнее считать как `[assisted]`, а не `[agent]`. Это совпадает с индустриальной практикой: self-reported «AI-assisted» обычно ~40%, но реально AI-authored (без правок) — около 27%.

Формат — Conventional Commits, тэги английские (`feat:`/`fix:`/`refactor:`/`chore:`), **описание после двоеточия — на русском** (см. таблицу «Язык общения» выше).

Примеры:
```
[agent] feat(api): добавить эндпоинт PATCH /links/{id} и тесты
[assisted] refactor(services): переработать сервисный слой после черновика агента
[manual] docs(readme): исправить опечатку
[agent] test(links): добавить regression-тест на валидацию заголовка с пробелами
[manual] chore(deps): обновить pytest до >=9.0.3 для CVE-2025-71176
```

После выполнения каждой задачи выводи итоговый блок:

```
[agent | assisted | manual] <короткое описание задачи на русском>
Files: <количество файлов изменено>
Tests: <добавлено/изменено>
Checks: ruff ✅  basedpyright ✅  pytest ✅
```

## Что делать когда `git commit` падает с pre-commit-хуком

В этом репозитории стоят pre-commit-хуки (ruff, basedpyright, bandit, pip-audit, gitleaks, end-of-file-fixer, trailing-whitespace, и т.д.). Каждый `git commit` прогоняет их **до** создания коммита. Возможны три исхода:

### Исход A: Все хуки `Passed` — коммит создан

Ничего делать не надо. Покажи `git log -1 --stat` в подтверждение.

### Исход B: Хук **автофиксанул** файлы (`files were modified by this hook`)

Так работают `end-of-file-fixer`, `trailing-whitespace`, `ruff format`, `ruff check --fix`. Они **сами** правят файлы и сигнализируют что коммит надо повторить.

Действия:
1. Посмотри какие файлы изменены: `git status`.
2. `git add` этих файлов.
3. `git commit -m "..."` повторно с тем же сообщением.

На втором заходе автофиксы уже применены — хук пройдёт `Passed`.

### Исход C: Хук нашёл **реальную ошибку** (например `basedpyright` или `bandit`)

Это **не** автофикс — это ошибка которую надо понять и исправить. Действия:

1. Прочитай вывод хука. У каждой ошибки есть путь к файлу, номер строки и описание.
2. Открой файл, разбери что не так:
   - **basedpyright**: чаще всего нет аннотации типа, или `Any` где должен быть конкретный тип, или доступ к `None` без проверки. Добавь аннотацию или `# pyright: ignore[<ruleId>]` с комментарием **почему** именно это игнор оправдан.
   - **bandit**: нашёл небезопасную конструкцию (`subprocess(shell=True)`, `yaml.load` без `SafeLoader`, и т.д.). Перепиши на безопасный вариант. Не используй `# nosec` без объяснения.
   - **pip-audit**: CVE в зависимости. Если это твой код добавил эту зависимость — обнови её до fix-версии **отдельным коммитом** (`[manual] chore(deps): обновить <package> для CVE-XXXX`). Если CVE в чужой зависимости которую ты не трогал — см. `.agents/agents/security.md`, секция «pip-audit».
3. Исправь, добавь в индекс (`git add`), коммить снова.
4. Если 3 раза подряд хук падает на одном и том же — остановись, опиши пользователю что именно ошибка говорит и в чём конфликт. Не зацикливайся.

Расширенный алгоритм реакции на любые ошибки (не только pre-commit) — в
`.agents/agents/error-handling.md` (severity Critical/High/Medium/Low + правило
«Identify → Assess → Communicate → Solutions»).

### Что **запрещено** делать

- **`git commit --no-verify`** — обход всех хуков, **никогда**.
- **`SKIP=hook git commit ...`** — пропуск конкретных хуков, **никогда** (единственное исключение — учебный демо в Шаге 6.2 no-rules-variant, описано в `.agents/agents/security.md`).
- **`PRE_COMMIT_ALLOW_NO_CONFIG=1`** — это срабатывает когда `.pre-commit-config.yaml` отсутствует. Если ты эту переменную увидел в подсказке git'а — конфиг **потерян**, восстанови его (`git show HEAD:.pre-commit-config.yaml > .pre-commit-config.yaml`), не обходи.

Подробности — в `.agents/agents/security.md`, секция «Pre-commit хуки — никаких обходов».

## Конвертация документации в Confluence Wiki Markup

Если нужно преобразовать `.md` файл в Confluence Wiki Markup для вставки через `Other macros → Markup → Confluence wiki`:

**Читай файл с правилами перед конвертацией:**
```
.agents/md-to-confluence-rules.md
```

Файл лежит в корне каталога `agents_ skills/` (на уровень выше `agents/`).

Он содержит:
- точные команды bash для конвертации (pandoc + sed + clean-jira-escapes.py)
- таблицу типичных ошибок и их решений
- скрипт проверки результата (три проверки должны вернуть 0)
- структуру папок для готовых `.txt` файлов

**Правило:** никогда не конвертируй вручную и не придумывай правила на лету — всё в `md-to-confluence-rules.md`.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md sha256=906aab1ea3b7cda57b9d788a3dd105f2f6d2e7be159a699eccaf3f93f6bba400
---
name: architecture
description: >
  Python-overlay для универсального architect-software-product: применяет командные
  границы Litestar/FastAPI, async SQLAlchemy, Pydantic, Alembic, HTTP/event/data
  contracts и Python verification surface к Architecture Packet. Использовать только
  вместе с universal Architect для S2/S3-задач в Python-бэкенде.
---

# Architecture — Python overlay

Этот файл не задаёт второй архитектурный процесс. Сначала полностью выполнить:

1. `~/Мой диск/skils/ai-sdlc/universal/architect-software-product/SKILL.md`;
2. его `references/protocol.md`;
3. `.agents/agents/architecture.md`, `.agents/agents/docs.md` и корневой `AGENTS.md`
   конкретного репозитория.

Главный выход остаётся один:
`.ai-team/runs/<run-id>/architecture/architecture-packet.json` с
`profile=python-aisdlc-gcge`.

## Приоритет правил

1. Утверждённые требования и решения владельца.
2. `AGENTS.md`, действующие ADR и реальный код репозитория.
3. Этот Python-overlay.
4. Общие defaults модели.

Личный baseline и стек «по привычке» не использовать. Если проект не Litestar/FastAPI
или не следует описанным слоям, зафиксировать фактический стек и не навязывать шаблон.

## Входной evidence

До решения открыть и сослаться в packet минимум на:

- точки входа API/consumer/job;
- service/domain/repository границы;
- модели и migrations затронутых данных;
- `pyproject.toml`/lockfile и реальные версии;
- существующие тесты, CI-команды и архитектурные правила;
- последний успешный аналог изменения, если он есть.

Использовать `rg`, import graph и чтение символов. Название файла, класса или метода
не включать в handoff, если их существование не подтверждено кодом.

## Python-specific boundaries

Если репозиторий следует командному слоению, проверить:

```text
api/ → services/ → repository → models
          ↓
        domain
```

- route/handler: transport, validation, вызов service, response;
- service: business policy, без импорта ORM model;
- repository: storage operations и mapping;
- domain: infrastructure-independent entities/contracts;
- внешний I/O: отдельный client/adapter с timeout и typed errors.

Не добавлять слой ради схемы. Для другого фактического устройства описать существующие
границы и минимальную delta, а не перестраивать проект без требования.

В `boundaries[]` указать allowed/forbidden dependencies и `verification_ids`.
Исполняемый import contract предлагать только если он окупается и одобрен как новая
dependency/process delta.

## Async и failure semantics

Для async Python явно спроектировать:

- timeout для каждой I/O-операции и cleanup;
- cancellation и partial failure;
- retry только для перечисленных transient errors;
- idempotency/deduplication для повторов;
- concurrency limit, backpressure и порядок результатов;
- ownership соединений, сессий и транзакций.

`time.sleep`, sync HTTP/DB client внутри async flow и бесконечный retry запрещены.
Для dynamic/paginated/streaming источника определить аккумуляцию и независимый сигнал
полноты; один snapshot не считается полным источником.

## Contract deltas

В `contract_deltas[]` фиксировать только изменения:

- Pydantic/DTO: поля, типы, required/default/nullability и validation;
- HTTP: method/path/request/response/error/status/idempotency/versioning;
- event: producer/consumer/schema/order/dedup/replay/compatibility;
- data: owner/schema/index/constraints/retention/classification;
- dependency: package, verified version range, purpose, operational cost и exit path.

Cross-repo mirror, compatibility window и mixed-version behavior указывать явно.
Breaking change, auth/security model, новая major dependency и cross-service contract —
one-way decision с человеческим approval.

`contract_deltas[]` непустой только если **текущая** задача явно требует сменить
контракт. Иначе пакет `BLOCKED`, а не «улучшенный» контракт. Канон:
`.agents/agents/scope-and-contracts.md`. Архитектор не ходит в чужие KEY.

## Data и migrations

Если меняется persisted state:

- Alembic migration и downgrade/forward-fix policy;
- online/offline характер DDL, lock и длительность;
- backfill/checkpoint/retry/dedup;
- совместимость старого и нового кода во время rollout;
- контроль целостности до/после;
- rollback без предположения, что потерянные данные восстановятся сами.

В `evolution` нельзя писать просто `NOT_APPLICABLE`: добавить проверяемую причину.

## ADR и proposals

Формат и путь ADR брать из `.agents/agents/docs.md` и существующего `docs/adr/INDEX.md`.
Не создавать `docs/architecture/adr/` параллельно командному каталогу.

- ADR-lite — локальное обратимое решение.
- ADR-full — дорогой откат, несколько репозиториев, NFR/security, спор или ≥3 опции.
- Sensitivity check и PoC применять по командному ADR-full contract.

Architect пишет proposal только в `architecture/proposals/`. Он не выполняет
`uv add`, не меняет `pyproject.toml`, lockfile, CI, migrations и product code.
Такие изменения перечисляются в contract/materialization plan и проходят approval.

## Views

Не требовать C1+C2 механически. Выбрать минимальный набор:

- Context/Container — меняются system ownership или внешние связи;
- Component — новое внутреннее разделение, которое Coder может понять неоднозначно;
- Dynamic/sequence — async flow, retry, transaction или несколько сервисов;
- Deployment — rollout, queue, worker, storage или failure domain;
- DFD — sensitive data, auth или trust boundary.

Каждый `views[]` содержит вопрос и artifact reference.

## Python verification surface

Включить exact команды из репозитория. Если применим стандартный командный набор:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest -q
```

Дополнить targeted regression, contract/integration/migration/runtime checks. Не писать
несуществующую команду ради заполнения packet. Verifier обязан запустить полный frozen
набор; Coder log не заменяет независимое выполнение.

Для каждого изменения определить чувствительность:

- bugfix: red без fix → green с fix;
- новый contract: negative/boundary test;
- migration: upgrade + data check + допустимая rollback/forward-fix проверка;
- concurrency/time/network: повтор/seed/fault injection по риску;
- architecture boundary: нарушение действительно делает arch-test красным.

## Что Architect не делает

- Не создаёт ветки и коммиты.
- Не пишет готовую реализацию и не фиксирует внутренние сигнатуры без контрактной причины.
- Не разбивает работу на искусственные задачи «≤1 день»; порядок реализации формирует
  Orchestrator/Coder по утверждённому packet.
- Не устанавливает зависимости и не ослабляет существующие gates.
- Не выдаёт self-eval или grep по заголовкам за architecture review.
- Не меняет согласованный внешний контракт без явного указания в текущей задаче.
- Не разворачивает исследование на соседние Jira-KEY.

## Definition of Done overlay

- Universal Architecture Packet валиден в `approved` phase.
- Все Python-утверждения подтверждены кодом/конфигом/официальной документацией.
- Слои, async semantics и ownership отражают реальный проект.
- Contract deltas содержат compatibility и verification IDs.
- Stateful change имеет migration/rollout/rollback и integrity checks.
- Verification surface содержит реальные project commands и targeted checks.
- ADR path/format не конфликтует с `.agents/agents/docs.md`.
- Architect не изменил product worktree.
- `contract_deltas[]` пуст либо в текущей задаче есть явное указание менять
  согласованный внешний контракт (`.agents/agents/scope-and-contracts.md`).

## Эскалация

`BLOCKED`, если отсутствует NFR, schema ownership, compatibility policy, право на
breaking/security/dependency decision или способ проверить критичный contract. Не
додумывать значения и не передавать Coder условный пакет как approved.

<!-- HL-RESILIENCE-GATES-V5 -->
## Обязательные Highload & Resilience гейты (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)

Единый источник правды (SSoT) всех формул, 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` и 21 стоп-кода — `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`). Архитектурный пакет **не может** получить статус `approved` без:

1. **`HL-ENV-01`**: полностью заполненной таблицы из 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` в единицах СИ с указанием источников, проверкой замыкания памяти $W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} \le 0.80 \times \text{Mem\_limit\_per\_pod}$ и двойного доказательства для любого `N/A` (`git diff` + транзитивный граф `callers/callees`).
2. **`C-MULT-I1..I5`**: многоролевого и многопоколенческого расчёта соединений $C_{\text{dep}}(d) \le 0.60 \times \text{Limit\_dep\_share}[d]$ по всем ролям (`crawler`, `llm`, `pod_fetcher`, `control_plane`, `migrations_cron`) с учётом $G_{\text{reload}} \in \{1, 2\}$, `BlockingConnectionPool`, `max_waiters <= 2M`, запрета сокетов до `fork()` и бюджета портов/FD (`<= 50%` портов, `<= 70% ulimit_n`).
3. **`S-HERD-I1..I5`**: расчёта пачечного стартового залпа $B_{\text{dep, 1s}}(d) = K_{\text{calls}}[d] \cdot (\lambda_{\text{fetch}}(d) + 4\sqrt{\lambda_{\text{fetch}}(d)} + 4) \le 0.50 \times \text{Limit\_dep\_rps}[d]$ и стационарного поллинга $R_{\text{poll}}(d) \le 0.20 \times \text{Limit\_dep\_rps}[d]$, пересева CSPRNG после `fork()`, `If-None-Match` (`304`), cancellation-safe `singleflight` и политики `Max_stale_age_s[c]`.
4. **`H-CPU-I1..I5`**: доказательства $O(1)/O(\log N)$ индексов на иммутабельном `Snapshot`, отсутствия парсинга/аллокаций на горячем пути (`if not enabled: return` первой строкой), неблокирующей доставки `Snapshot` $\le 2\text{ мс}$ на тик event loop (`mmap` / кооперативные батчи `sleep(0)`) и выполнения трёх неравенств CPU на $P_{\text{avail\_min}}$.
5. **`R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`**: заполненной `Dependency Failure Matrix`, бюджета дедлайнов $\le 0.30 \times \text{SLA}_{\text{p99\_s}}$, Token-Bucket Retry Budget, `Circuit Breaker` (`HALF_OPEN=1`), двухэтапного фильтра `M-SEM/v1` + post-eviction предиката `Panic-Open` ($|V_{\text{healthy}}| - 1 \ge N_{\text{floor}}$) и разделения `origin_health` vs `node_health`.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md sha256=25f91ad5fa5cc92f9372e5fe89b0fc0d83f2e8445ba6eb1e966cf78f4e6828cd
# Scope задачи и согласованные внешние контракты

Два жёстких правила. Нарушение — блокирующий FAIL ревью и приёмки, не follow-up
и не «улучшение заодно». Полный текст живёт здесь; скиллы ролей ссылаются
и ставят бинарный пункт в критерии приёмки.

Читать при любой разработке: фича, багфикс, рефакторинг, hotfix, архитектура,
ревью, MR, цикл техлида.

## 1. Согласованный внешний контракт не менять без явного указания

Если контракт уже согласован с внешними исполнителями — другими сервисами,
командами, потребителями HTTP/event/data/CLI/SDK, аналитикой — его нельзя
менять, расширять, сужать, переименовывать и «улучшать», пока текущая задача
явно это не требует.

### Что считается внешним контрактом

- HTTP: method, path, query, request/response DTO, status, error body, auth,
  идемпотентность, версия.
- Событие / очередь / топик: имя, схема, обязательность полей, типы,
  nullability, порядок, совместимость.
- Публичный CLI, SDK, shared-library API.
- Формат файла, протокол, контракт аналитики/событийки.
- Cross-repo зеркало той же схемы.

Внутренняя реализация за неизменной границей (сервис, репозиторий, SQL,
логи, метки, тесты потребителя не ломающие) — не контракт.

### Что считается явным указанием

Фраза в **текущей** постановке (промпт, Jira этой KEY, AC этой задачи):
«измени контракт», «breaking», «обнови схему / DTO / API / событие»,
«согласуй с \<команда/сервис\>». Без такой фразы права менять контракт нет.

Не является указанием:

- «сделай лучше / удобнее / правильнее»;
- соседняя задача, эпик, чужой MR, страница Confluence «как будет»;
- архитектурный документ, который агент сам написал в этом же заходе;
- «потребители подстроятся», «это же совместимо, если добавить поле».

Добавление поля, смена default, переименование, смена типа на совместимый,
новый код ошибки на старом пути — тоже изменение контракта.

### Что делать

1. До кода найти согласованную границу в зоне изменения (спека, Confluence,
   Pydantic/DTO, OpenAPI, схема события, KB `contracts/`).
2. Если задача требует её менять, а в постановке этого нет — **STOP, ASK**.
   Не чинить «заодно». Не предлагать breaking как часть текущей сдачи.
3. Если указание есть — delta контракта, совместимость, потребители и
   verification явным пунктом в AC; иначе задача не готова к коду.

## 2. Работаем только в рамках своей задачи

Scope = текущий промпт и, если есть, текущий Jira-KEY. Чужие задачи не
открывать, не ревьюить, не чинить и не отчитываться по их статусу.

### Запрещено

- Искать и пересказывать статус соседних KEY / MR / стендов «заодно».
- «Пока смотрел, увидел EYE-XXXX — там вот что».
- Тащить скоуп, AC, фикс или рефакторинг из другой задачи в текущий diff.
- Отвечать на вопрос по одной задаче отчётом по доске / эпику / чужим тикетам.

### Можно

- Прочитать другой тикет, только если **текущая** постановка явно называет
  его зависимостью (`blocked by` / `relates` / «зависит от KEY»). Тогда —
  только факт зависимости, не статус-отчёт по чужой работе.
- Ответить по другой задаче, только если владелец **этим промптом** её
  спросил. Это новый запрос, не расширение текущего.

Неясная граница KEY → ASK, не гадать и не ходить по доске.

## Критерии приёмки (копировать в DoD роли)

- [ ] Diff не меняет согласованный внешний контракт, либо в текущей задаче
      есть явное указание это сделать и delta зафиксирована.
- [ ] Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в
      отчёте отсутствуют, если их не спросили.

Нет любого пункта → задача не сдана, ревью `CHANGES_REQUESTED` / приёмка
не ACCEPT.
ARTIFACT_END>>>

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и по исходникам, 2026-10-29):
- Репозиторий `cli-agent-bridge` (ветка `feature/agy-realtime-reasoning` от `origin/dev`): автономный Python stdlib-мост `bridges/agy-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9887`, боевой запуск под `/usr/bin/python3` 3.9.6 через LaunchAgent `com.user.dsh-agy-bridge`), тесты в `tests/test_agy_bridge_resilience.py` (22 теста зелёные).
- Установленный CLI `~/.gemini/antigravity-cli/releases/1.4.9/agy` (`1.4.9`) в режиме `--output-format stream-json` не выводит `thinking` в stdout, а `transcript_full.jsonl` получает шаг `PLANNER_RESPONSE` только после `DONE` (`[F-27]..[F-29]`).
- Локальная SQLite-база `~/.gemini/antigravity-cli/conversations/<cid>.db` (WAL, таблица `steps`, `step_type=15`, `status=8` GENERATING -> `status=3` DONE) обновляется каждые 1.5–5.1 с, а подполе `20.3` в `step_payload` содержит накопленный текст `thinking` (`[F-30]..[F-34]`).
- На системном `/usr/bin/python3` (SQLite 3.51.0) открытие WAL-БД с `mode=ro` работает при живом процессе-писателе `agy` (наличие `-shm`), а на закрытой WAL-БД падает с `unable to open database file`, тогда как `immutable=1` читает закрытую БД (`[F-52]`, `[F-53]`).
- Подтверждены 4 корневые причины (`RC-1` live-источник мышления из SQLite `20.3` с дедупликацией с `transcript_full.jsonl`, `RC-2` синхронизация финального дренирования `_TranscriptTail` до `done`, `RC-3` учёт `reasoning` в `delivered`, `RC-4` изоляция горячих сессий `_session_store` от фоновых запросов без `tools`).
Анти-галлюцинация по факт-карте: технологии, пути, версии и поведение CLI из списка выше проверены на целевой машине; по сведениям, которых нет в факт-карте и приложенных артефактах, указывается «не могу проверить».

РЕЖИМ: architecture
Модификатор режима `architecture`: Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки. Усиленные критерии режима `architecture` (вес ×1.5 на агрегации): 5. АЛЬТЕРНАТИВЫ и 4. РИСКИ.

Обязанность места 3 из 3 по ранжированию (`seed_recheck_duty: да`): независимо пересчитай `SEED = sha256(seed_input)` и `ranked_order` по правилам `models.md` п.1.1/1.2 для дословной строки `seed_input = "analyst-teamlead-agy-reasoning-20261029:arch:r1:f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4:0000000000000000000000000000000000000000000000000000000000000000"` (ожидаемый `seed_hex = 26149a09fd4cb31876e4573461ae5123f4c7aa3dfe39fd36cf3b061f7288f3b5`, `ranked_order = ["claude-sonnet-5-5-high", "muse-wonder-full-1.0", "gemini-4-argon-high", "gpt-6.1-sol-high"]` при исключении автора `Anthropic`).

Инструкции судье Архитектурного Совета Тимлидов (раунд R1, цикл 1, проход a1):
- Если ты уже видел эту задачу, код или артефакты в другой роли — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически.
- Проверь соответствие Architecture Packet каждому требованию `REQ-001..REQ-012`, каждому приёмочному критерию `AC-001..AC-016` и разделам `handoff-architect.md`.
- Проверь, что все архитектурные решения опираются на факты `[F-NN]` и каждый факт `[F-NN]` находится в приложенном `evidence-ledger.md`.
- Проверь альтернативы: в Architecture Packet должно быть рассмотрено ≥2 альтернативы с явной причиной выбора; если в пакете меньше двух альтернатив или нет причины выбора — ставь FAIL по пункту об альтернативах (критерий 5. АЛЬТЕРНАТИВЫ).
- Проверь архитектурные границы и слои (`boundaries`), внешние контракты (`contract_deltas`), сценарии качества (тайминги отзывчивости, конверт `HL-ENV/v1` из 46 полей и расчёты `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`), модель угроз и защиту секретов (`threat_model`), а также проверяемость `verification_surface` и все пункты `Definition of Done overlay` из `aisdlc-gcge/skills/architecture.md`.
- FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.
- FAIL без оговорок: (1) пакет меняет согласованный внешний контракт без явного указания в постановке задачи (`scope-and-contracts.md`); (2) работа или пакет выходит за рамки текущей задачи.
- Оцени все 6 критериев `universal-panel` (1. КОРРЕКТНОСТЬ, 2. ПОЛНОТА, 3. РЕАЛИЗУЕМОСТЬ, 4. РИСКИ, 5. АЛЬТЕРНАТИВЫ, 6. СООТВЕТСТВИЕ КОНТЕКСТУ) по единому блоку формата ответа из промпта твоей роли в начале брифа.

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-with-architect/references/arch-council.md#L25-L31 sha256=2938e840cbd02bff4ae6fa9bbf158560ba506c615e302ed99fac607bf7a08dc7
- mode.txt = architecture; Альтернативы/Риски ×1.5, два усиленных FAIL = RED FLAG.
- ARCH_ROOT = <RUN>/arch-panel/cycle-<N>/a<A>/; A — arch_panel_to_architect, первый a1; тот же индекс в brief-review.
- Вердикт → summarizer → Architect, не Coder.

## 1a. Выход после R1 и обязательный маршрут (единый инвариант)

Вход: три валидных R1, достоверный consensus-ledger.md с lineage и transport proof PASS. PASS считается по вердиктам мест (APPROVE/ACCEPT); OPEN_BLOCKING/CONFLICT — по открытым находкам.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L95-L114 sha256=f83795a3eb87705bd3a1e9c766a286354f0717813c9f36842478fc661866f6d4
- был ли более простой/дешёвый путь достичь того же в main, оправдан ли выбор → АЛЬТЕРНАТИВЫ;
- архитектурные границы/слои, соответствие правилам проекта → СООТВЕТСТВИЕ КОНТЕКСТУ.
Нет содержательного наблюдения по критерию — ставь PASS/INCONCLUSIVE, не выдумывай FAIL.

ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД (обязательно, оба режима):
1. Найденный FAIL проход НЕ завершает. Дойди до последней подкатегории рубрики и
   только потом пиши вердикт. ЗАПРЕЩЕНО обрывать поиск на первой найденной ошибке.
2. Выдай ВСЕ замечания сразу одним списком F-блоков, blocking и non-blocking вместе
   (поле priority). ЗАПРЕЩЕНЫ: поштучная выдача («главное сейчас, остальное после
   исправления»), откладывание («проверю в следующем раунде»), резерв про запас.
3. Один дефект класса X в нескольких местах — ОДИН F-блок со ВСЕМИ местами
   (locations: file:line, …), найденными поиском по всему diff. Формулы «и т.п.»,
   «и другие места», «например» вместо перечисления недопустимы.
4. Разные root cause в одном месте — разные F-блоки. Каждый F-блок самодостаточен:
   file:line, правило, evidence (цитата), ожидаемое исправление, критерий проверки,
   priority.
5. Перед вердиктом пройди список подкатегорий второй раз (self-sweep) и допиши
   пропущенное, пометив [sweep].
6. Последние строки ответа: `COVERAGE: <k>/<K> подкатегорий` и
   `FINDINGS_COMPLETE: <N>` (N = число F-блоков). Нет строк, k<K или N ≠ числу
ARTIFACT_END>>>
Примечание для режима `arch`: в блоке «ПОЛНОТА ВЫДАЧИ» выше слово «diff» читается как «Architecture Packet», а вместо `file:line` используются допустимые якоря (а)–(г) из блока «ЯКОРЯ ПАКЕТА».

Итоговую строку общего вердикта выводи строго с одним из значений `PASS`, `NEEDS WORK` или `RED FLAG` (без точки и комментариев в той же строке), а сразу после неё — обязательные строки покрытия и числа находок из п.6 блока «ПОЛНОТА ВЫДАЧИ».

---
PANEL-NONCE: f59080f9c39fff6d
ARTIFACT-SHA256: f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: f59080f9c39fff6d» и «ARTIFACT-SHA256: f0471a6116bcea5831736dee36a85386c27f2758b7c41fdc354e96aa793229f4».
