Ты — Реалист. Твоя задача — оценить реализуемость, ресурсы, сроки, зависимости. Ключевой вопрос: «Что нужно чтобы это взлетело?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на практической применимости: можно ли это реально внедрить, какие зависимости нужны, что блокирует, сколько усилий потребует.

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
Ниже приложены целиком (без обрезки; раздел «Не вложено» пуст — все первичные артефакты даны полностью в этом брифе) актуальный Architecture Packet (редакция v3), квитанция пройденного гейта `ARCH_GATE`, механическая дельта `diff -u` между редакциями v2 и v3 с SHA-256 обеих редакций (`architecture-packet.v2-to-v3.diff`), а также первичный артефакт вывода `panel-rework-summarizer` (`handoff/panel-rework-brief-arch-a2.json`, `SK-A-11`, `arch-council.md` §4):
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
{
  "schema_version": "1.0",
  "packet_version": "3.0",
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "cycle": 3,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": "plans/architect-03.json",
    "sha256": "8e383a4a7ad0982736360cc1ba4be3fcf5d4a29d87fcafc8c5c03169f2044d3c"
  },
  "summary": "Cycle3 a2→a3 fix-from-panel: 6 RW + 8 FU закрыты на уровне архитектурной delta; OPENCODE_DB=:memory:, полный single-turn control, Keep-Alive owner proof, sanitized env и crash leases. APPROVED — кандидат для отдельного Совета a3, не ACCEPT/ARCH_GATE_PASS; Stage3/H0..H9 NOT_RUN.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/zen-realtime-reasoning",
    "branch": "feature/zen-realtime-reasoning",
    "architect_write_allowlist": [
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.before.json",
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.json",
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json"
    ],
    "coder_target_files": [
      "bridges/opencode-zen-bridge/server.py",
      "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
    ],
    "forbidden": [
      "analysis/zen-realtime-reasoning/** (frozen analyst inputs)",
      "bridges/muse-bridge/**",
      "прямой Google route и test_google_direct.py",
      "~/.dsh/** до отдельной rollout-фазы",
      "общие конфиги opencode/georouter, opencode.db, зависимости/lockfiles",
      "bridges/opencode-zen-bridge/dynamic_config.json не создавать/не коммитить; runtime ~/.dsh JSON только отдельный rollout operator H7"
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
    "REQ-012",
    "REQ-013",
    "REQ-014",
    "REQ-015",
    "REQ-016",
    "REQ-017",
    "REQ-018",
    "REQ-019",
    "REQ-020"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "MUST",
      "statement": "Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага",
      "acceptance": "AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс",
      "evidence": "F-17, F-18, F-19",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-002",
      "priority": "MUST",
      "statement": "Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883",
      "acceptance": "AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата",
      "evidence": "F-35, F-34",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "REQ-003",
      "priority": "MUST",
      "statement": "Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными",
      "acceptance": "AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04)",
      "evidence": "F-43, F-40, F-42",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-004",
      "priority": "MUST",
      "statement": "Thinking-enabled non-Google SSE: slow/no-progress request gives visible nonempty [мост] reasoning status with LF by1.0s after SSE open, after grace0.30s; fast model text/reasoning before grace suppresses initial synthetic status. Explicit off/none and JSON never get synthetic reasoning.",
      "acceptance": "AC-005 scoped per AD-002/CD-001: eligible blank upstream ->first status at0.30..1.0s after initial SSE role flush; real model delta before0.30s ->zero initial status; off/none/JSON ->zero synthetic reasoning. Model bytes immutable, fast Simple greeting. exact. Stall after first token>=15.0s requires heartbeat every15.0s until progress/terminal, bounded by stall watchdog60s.",
      "evidence": "F-36, F-37, F-04, F-33",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-005",
      "priority": "MUST",
      "statement": "Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее",
      "acceptance": "AC-006: concatenate model-origin deltas after removing synthetic by provenance (not prefix matching) equals model bytes, including literal model [мост]. Leading LF separator belongs entirely synthetic delta. AC-007 reasoning/status never replayed in prompt. Eligible status only per REQ-004; post-token stall threshold/interval15.0s mandatory, does not reset watchdog.",
      "evidence": "F-37, F-38, F-07, F-39",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-006",
      "priority": "MUST",
      "statement": "Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку",
      "acceptance": "AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с На serve локальный HTTP ready не считается execution event: после отправки prompt валидного события текущей session нет20s ->first_event_timeout+cleanup<=2s.",
      "evidence": "F-09, F-30, F-31",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-007",
      "priority": "MUST",
      "statement": "Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения",
      "acceptance": "AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout`",
      "evidence": "F-09, F-19, F-32",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-008",
      "priority": "MUST",
      "statement": "Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с",
      "acceptance": "AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится",
      "evidence": "F-14, F-30, F-33",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-009",
      "priority": "MUST",
      "statement": "Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка",
      "acceptance": "AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка",
      "evidence": "F-11, F-12",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-010",
      "priority": "MUST",
      "statement": "`ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len(\"<tool_invoke>\")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты",
      "acceptance": "AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом",
      "evidence": "F-06, F-05",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-011",
      "priority": "MUST",
      "statement": "Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason=\"tool_calls\"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути",
      "acceptance": "AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт",
      "evidence": "F-05, F-11, F-43",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-012",
      "priority": "MUST",
      "statement": "Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native)",
      "acceptance": "AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь",
      "evidence": "F-08, F-22, OPEN-07",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-013",
      "priority": "MUST",
      "statement": "REQ-013 уточнение под AC-018: per-spawn ротация _next_standalone_proxy и proxy env сохраняется на каждом child; _StartupGate, spawn rate, bulkhead и model Circuit Breaker действуют на обоих транспортах. loopback georouter baseURL=http://127.0.0.1:10830/v1 идёт по NO_PROXY в обход child HTTP_PROXY; смена реального Zen egress IP этим не гарантируется.",
      "acceptance": "AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`)",
      "evidence": "F-10, F-11, F-15, F-27, F-32; RW-005",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-014",
      "priority": "SHOULD",
      "statement": "`usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим",
      "acceptance": "AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры",
      "evidence": "F-19, F-02",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-015",
      "priority": "MUST",
      "statement": "Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование",
      "acceptance": "AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey`",
      "evidence": "F-21, F-27",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-016",
      "priority": "MUST",
      "statement": "Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода",
      "acceptance": "AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` first_event_ms=null до валидного session SSE исполнения после prompt; local ready не подставлять; transport_history различает _ServeHealth degradation.",
      "evidence": "F-32, F-30",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-017",
      "priority": "SHOULD",
      "statement": "Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс",
      "acceptance": "AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов",
      "evidence": "F-45, F-46, F-47, F-48, F-49",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-018",
      "priority": "MUST",
      "statement": "Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается",
      "acceptance": "AC-024: `test_google_direct.py` проходит без правок",
      "evidence": "F-16",
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "REQ-019",
      "priority": "SHOULD",
      "statement": "Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой",
      "acceptance": "AC-025: побайтовое совпадение после деплоя",
      "evidence": "F-34, OPEN-17",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-020",
      "priority": "MUST",
      "statement": "В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет)",
      "acceptance": "AC-026: тест красный на текущем коде и зелёный на новом (red to green)",
      "evidence": "F-44",
      "verification_ids": [
        "VER-005"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-01; server.py:1146-1161, 966-969, 1617-1649",
      "claim": "Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-01"
    },
    {
      "id": "EVD-002",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-02; server.py:2417-2462",
      "claim": "`parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-02"
    },
    {
      "id": "EVD-003",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-03; server.py:3312-3327, 3399-3412",
      "claim": "`Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{\"role\":\"assistant\",\"content\":\"\"}` до `_StartupGate`, spawn и чтения stdout",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-03"
    },
    {
      "id": "EVD-004",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-04; server.py:49, 3437-3450, 865-952",
      "claim": "Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{\"content\":\"\"}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-04"
    },
    {
      "id": "EVD-005",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-05; server.py:3462-3493",
      "claim": "События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-05"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-06; server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323)",
      "claim": "`ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len(\"<tool_invoke>\")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-06"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-07; server.py:1848-1888",
      "claim": "`_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-07"
    },
    {
      "id": "EVD-008",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-08; server.py:228-231",
      "claim": "Конфиг `opencode` для дочернего процесса по умолчанию: `permission {\"*\":\"ask\"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-08"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-09; server.py:46, 3450, команда grep от 2026-10-25",
      "claim": "В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-09"
    },
    {
      "id": "EVD-010",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-10; server.py:1197-1236, 3399-3411, 3451",
      "claim": "`_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-10"
    },
    {
      "id": "EVD-011",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-11; server.py:277, 287-298, 309-314, 1340-1368, 1471-1535",
      "claim": "Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-11"
    },
    {
      "id": "EVD-012",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-12; server.py:1458-1470, 3989-3996",
      "claim": "Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-12"
    },
    {
      "id": "EVD-013",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-13; server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK",
      "claim": "`MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-13"
    },
    {
      "id": "EVD-014",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-14; server.py:848-862, 865-952",
      "claim": "`_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-14"
    },
    {
      "id": "EVD-015",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-15; server.py:1047-1082, 1093-1131; start.sh:24-31",
      "claim": "Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-15"
    },
    {
      "id": "EVD-016",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-16; server.py:3127-3266 (reasoning emit около 3219)",
      "claim": "`_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({\"reasoning_content\": text})` в реальном времени; прецедент прямого маршрута для Option B",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-16"
    },
    {
      "id": "EVD-017",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-17; explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK)",
      "claim": "`opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-17"
    },
    {
      "id": "EVD-018",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-18; explorer-zone-b.md §2",
      "claim": "Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-18"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-19; explorer-zone-b.md §1, §3",
      "claim": "`opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-19"
    },
    {
      "id": "EVD-020",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-20; sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK",
      "claim": "Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-20"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-21; sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25",
      "claim": "Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-21"
    },
    {
      "id": "EVD-022",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-22; sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B)",
      "claim": "OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-22"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-23; sa-poc/poc_serve.log",
      "claim": "PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {\"*\":\"deny\"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-23"
    },
    {
      "id": "EVD-024",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-24; sa-poc/poc_georouter.log",
      "claim": "Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-24"
    },
    {
      "id": "EVD-025",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-25; sa-poc/poc_direct_zen_proxy.log",
      "claim": "Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-25"
    },
    {
      "id": "EVD-026",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-26; ~/.config/model-georouter/config.json (значения без секретов)",
      "claim": "`model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-26"
    },
    {
      "id": "EVD-027",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-27; ~/.config/opencode/opencode.json (обход ключей с маскированием)",
      "claim": "В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-27"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-28; ls -l, opencode run --help от 2026-10-25",
      "claim": "`~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-28"
    },
    {
      "id": "EVD-029",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-29; ps, lsof, launchctl limit от 2026-10-25 22:4x MSK",
      "claim": "Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-29"
    },
    {
      "id": "EVD-030",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-30; explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK",
      "claim": "Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-30"
    },
    {
      "id": "EVD-031",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-31; explorer-zone-d.md §2",
      "claim": "Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-31"
    },
    {
      "id": "EVD-032",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-32; explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log",
      "claim": "Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-32"
    },
    {
      "id": "EVD-033",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-33; explorer-zone-d.md §3",
      "claim": "Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-33"
    },
    {
      "id": "EVD-034",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-34; explorer-zone-d.md §1; /health от 2026-10-25",
      "claim": "Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-34"
    },
    {
      "id": "EVD-035",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-35; ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C)",
      "claim": "Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-35"
    },
    {
      "id": "EVD-036",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-36; /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка)",
      "claim": "Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-36"
    },
    {
      "id": "EVD-037",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-37; client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка)",
      "claim": "UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===\"\"` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\\n`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-37"
    },
    {
      "id": "EVD-038",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-38; app.asar openai-completions.js, смещения 116117903-116120153",
      "claim": "При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-38"
    },
    {
      "id": "EVD-039",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-39; ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста",
      "claim": "Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-39"
    },
    {
      "id": "EVD-040",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-40; bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185",
      "claim": "`muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-40"
    },
    {
      "id": "EVD-041",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-41; bridges/muse-bridge/server.py:165, 4150-4156",
      "claim": "`muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-41"
    },
    {
      "id": "EVD-042",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-42; ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log",
      "claim": "В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-42"
    },
    {
      "id": "EVD-043",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-43; tests/*.py (grep OPENCODE_BIN и _fake_cli)",
      "claim": "Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-43"
    },
    {
      "id": "EVD-044",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-44; tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py",
      "claim": "Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-44"
    },
    {
      "id": "EVD-045",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-45; baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log",
      "claim": "Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-45"
    },
    {
      "id": "EVD-046",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-46; sa_iso_file.log",
      "claim": "Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-46"
    },
    {
      "id": "EVD-047",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-47; sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287",
      "claim": "Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-47"
    },
    {
      "id": "EVD-048",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-48; baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368",
      "claim": "Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-48"
    },
    {
      "id": "EVD-049",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-49; git log -S от 2026-10-25",
      "claim": "`grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-49"
    },
    {
      "id": "EVD-050",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:228-231",
      "claim": "permission=ask сохраняет native tool schema; комментарий baseline предупреждает: deny/tools:false может вызвать Zen 403."
    },
    {
      "id": "EVD-051",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/tests/test_step_interruption.py:67-145,150-190,388-415",
      "claim": "Fake CLI игнорирует argv, увеличивает counter до stdin.read(); reasoning_interrupted ожидает ровно Simple greeting.; общий сервер на класс."
    },
    {
      "id": "EVD-052",
      "kind": "command",
      "ref": "UV_OFFLINE=1 uvx ruff check --no-cache bridges/opencode-zen-bridge/server.py",
      "claim": "exit=1, единственный baseline E402 на zen_catalog import:67; ruff 0.17.2."
    },
    {
      "id": "EVD-053",
      "kind": "command",
      "ref": "UV_OFFLINE=1 uvx basedpyright bridges/opencode-zen-bridge/server.py",
      "claim": "exit=1, 2 errors (reportImplicitRelativeImport zen_catalog:67, reportConstantRedefinition CATALOG_SOURCE:131), 564 warnings; basedpyright 1.40.2 / pyright 1.1.414."
    },
    {
      "id": "EVD-054",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json",
      "claim": "Подтверждённый предыдущий packet: schema layout high_load_envelope/resilience_gates/21 legacy checks. Берётся формат, не результаты исполнения/одобрения."
    },
    {
      "id": "EVD-055",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:848-862,2849-2867,3630-3698",
      "claim": "_stop_proc ранний return после leader exit может оставить descendants; несколько finally/except используют proc.kill вместо killpg. Новый lifecycle обязан закрыть эти пробелы для обоих транспортов."
    },
    {
      "id": "EVD-056",
      "kind": "command",
      "ref": "worktree_fingerprint.py --compare fingerprints/architect-before.json",
      "claim": "WORKTREE_UNCHANGED 2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334 files=152; промежуточная проверка Stage 2."
    },
    {
      "id": "EVD-057",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:2213-2340,3462-3534",
      "claim": "Парсер удерживает префикс тега, незакрытые/невалидные блоки на finish может выдать сырыми; emit_parsed_content -> _strip_broken_tool_blocks удаляет их. tool_use сейчас читает raw event.part, поэтому canonical adapter должен сохранить этот payload."
    },
    {
      "id": "EVD-058",
      "kind": "code",
      "ref": "tests/test_dsh_profile_config.py:7-15",
      "claim": "Root suite содержит optional чтение ~/.dsh; clean-room runner обязан не монтировать owner home. Команды VER не выполняют deploy и не требуют ~/.dsh."
    },
    {
      "id": "EVD-059",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/route-manifest.json",
      "claim": "Preset analyst-teamlead, S2, profile python-aisdlc-gcge, architect run-artifacts-write, downstream_panel=true."
    },
    {
      "id": "EVD-060",
      "kind": "document",
      "ref": "Текущий Brief Stage 2, Steps 1–4",
      "claim": "Явно разрешены AD-001..004, baseline 3 tests, синтетический статус после grace, watchdog 20/60/60 и только run-артефакты."
    },
    {
      "id": "EVD-061",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:_UpstreamBreaker.allow (1415-1428), _SlotBulkhead.__init__ (1265-1270)",
      "claim": "Baseline HALF_OPEN probe can be re-admitted after reset_s while first is active; default slots2/configured waiters12 exceed canonical2M unless effective clamp. Dedicated oracles freeze intended single-probe/effective bound without altering deployed6/12."
    },
    {
      "id": "EVD-062",
      "kind": "code",
      "ref": "~/.opencode/bin/opencode (v2.1.2), embedded JS byte offsets113098820,114613538,114616189,114617971,114628971,114631174,114634000..114636000,114980796,114994633,114622692,114978382,115017692,114596000..114596700",
      "claim": "Read-only source extraction: version2.1.2; Model.Ref {providerID,id,variant}; Permission.Ruleset array{action,resource,effect}, wire permission.asked+reply decision=reject; delta data.delta/sessionID/assistantMessageID/ordinal; TokenUsage.Info {input,output,reasoning,cache:{read,write}}; tool input.started/called/failed; session prompt delivery steer|queue,resume. binary SHA256 b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c. Synthetic frozen examples use source schemas, не live tool execution. Дополнительно source: active sessions response data — object record, не array; Session.StructuredError optional numeric status (100..599); /api/info gives app version+pid; OpenAPI.info.version=0.0.1, отдельная от CLI2.1.2.",
      "collected_at": "2026-10-26"
    },
    {
      "id": "EVD-063",
      "kind": "document",
      "ref": "/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/serve_sse.py + poc_serve.log; F-19/F-22/F-23",
      "claim": "Существующий analyst PoC использует lightweight GET /api/session/active; create model {providerID,id,variant}, location.directory; prompt files[] delivery=steer; data.id response. Сохранённый failed event {id,created,type,data:{sessionID,error:{type:provider.free-limit,message}}}. В cycle2 процесс opencode не запускался, provider не вызывался."
    },
    {
      "id": "EVD-064",
      "kind": "document",
      "ref": "handoff/panel-rework-brief-arch-a1.json + текущий Brief Architect cycle2 fix-from-panel",
      "claim": "14 обязательных RW и7 FU; exact explicit choices для default true, headers barrier, permission selector,MiB/typing; role write allowlist только3 JSON. Исходные расхождения R1 перечислены в panel_resolution_choices, не выданы за единогласное одобрение изменений."
    },
    {
      "id": "EVD-070",
      "kind": "command",
      "ref": "Owner-provided host probe in cycle3 brief: (cd bridges/opencode-zen-bridge && python3 -m unittest discover -s tests -p \"test_*.py\" -v)",
      "claim": "378 tests in122.956s; import errors0; exactly3 original assertion failures in test_step_interruption.py [F-47]..[F-49]. VER-002 achievable from bridge cwd without editing17 other modules. Supplied empirical result, not rerun by Architect.",
      "measurements": {
        "tests": 378,
        "elapsed_s": 122.956,
        "import_errors": 0,
        "failures": 3
      },
      "status": "OBSERVED_BASELINE_OWNER_SUPPLIED"
    },
    {
      "id": "EVD-071",
      "kind": "command",
      "ref": "Owner-provided provider-free opencode v2.1.2 serve isolation spike; binary offsets114651600/122016915",
      "claim": "OPENCODE_DB=:memory:, standard XDG_DATA_HOME: GET /api/session/active=200 {data:{}} in120.7ms; RSS160544KiB=156.8MiB; lsof0 open .db/SQLite files, common2.27GB DB not opened; auth.json stays readable for opencode-go/*. Empty XDG_DATA_HOME comparator137.9ms/RSS208400KiB=203.5MiB loses auth.json. No Zen call; real provider auth and /api/info response were NOT supplied, remain explicit Stage3 preflight/H3 gates.",
      "measurements": {
        "memory_db": {
          "active_status": 200,
          "active_body": {
            "data": {}
          },
          "startup_ms": 120.7,
          "rss_kib": 160544,
          "rss_mib": 156.8,
          "open_db_files": 0
        },
        "empty_xdg": {
          "startup_ms": 137.9,
          "rss_kib": 208400,
          "rss_mib": 203.5
        }
      },
      "status": "OBSERVED_PROVIDER_FREE_OWNER_SUPPLIED"
    },
    {
      "id": "EVD-072",
      "kind": "command",
      "ref": "Owner-provided VER-004 baseline: ruff==0.17.2; basedpyright==1.40.2, cwd bridge + /tmp --project include+absolute extraPaths",
      "claim": "Full server ruff format --diff:3216 diff lines and immutable _run_env hash1c51b28f…→85c9c344…; forbidden Google slices reformatted, hence changed-hunk range gate required. Root-cwd basedpyright80 errors is wrong import-root. Isolated bridge basedpyright: server3 errors (CATALOG_SOURCE130, optional proc.returncode3665/3666),564 warnings; step test0 import errors,162 warnings. Ruff check: server1E402:67, step test0 errors. New tests/test_realtime_reasoning.py NOT_PRESENT; formatting/typing of that file NOT_RUN until Stage3. Existing step full-format baseline not supplied; record NOT_RUN, do not assert PASS.",
      "baseline_files": {
        "server.py": {
          "ruff_E402": 1,
          "type_errors": 3,
          "warnings": 564,
          "format_diff_lines": 3216
        },
        "tests/test_step_interruption.py": {
          "ruff_errors": 0,
          "import_errors": 0,
          "warnings": 162,
          "format_status": "NOT_RUN_NOT_SUPPLIED"
        },
        "tests/test_realtime_reasoning.py": {
          "status": "NOT_PRESENT"
        }
      },
      "status": "OBSERVED_BASELINE_OWNER_SUPPLIED"
    },
    {
      "id": "EVD-073",
      "kind": "code",
      "ref": "PANEL-A2-F-003; read-only binary ~/.opencode/bin/opencode offsets114605908/115254160 verified during cycle3",
      "claim": "Form.Info={id,sessionID,title,metadata?,fields}; form.created.data.form wraps Info (session id NESTED); form.cancelled.data={id,sessionID}. Form.State pending|answered(answer)|cancelled(message?). source gate filters form.created via data.form.sessionID. Native CLI cancel/interrupt and input.ended.text fallback documented in a2 brief; frozen fixture synthetic, not live interactive success. Form.ID source prefix frm_; fixture uses frm_fixture_1 and one valid string field (key,type; title/required optional).",
      "status": "SOURCE_VERIFIED_NOT_RUNTIME"
    },
    {
      "id": "EVD-074",
      "kind": "document",
      "ref": "PANEL-A2-F-004/PANEL-A2-F-008; cycle3 rework brief",
      "claim": "Panel-measured lsof68.1ms serial/82.0..88.1ms with6 concurrent calls; budget0.35s, one SPAWN→READY proof then3 HTTP/1.1 Keep-Alive lanes. These are supplied panel measurements, not Architect runtime probe. Hard-kill lease reaper/watchdog and H0/H9 proposed tests NOT_RUN. No owner-confirmed exception supplied; cycle3b compliant default=false/runtime JSON removes need for exception, without claiming consent.",
      "status": "PANEL_EVIDENCE_DESIGN_PENDING"
    }
  ],
  "risk_triggers": [
    "auth",
    "security",
    "trust-boundary"
  ],
  "assumptions": [
    {
      "id": "ASM-001",
      "class": "continuable",
      "source_open_ids": "OPEN-06/08",
      "statement": "OPENCODE_DB=:memory: with standard XDG_DATA_HOME preserves auth input and avoids shared DB opening: EVD-071 provider-free120.7ms/156.8MiB/0.db. Actual6parallel RSS/valid provider auth/locks not proven; H3 required. Design combined serve/helper/lsof192MiB per active slot remains estimate, observation<=256MiB is not peak.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-015",
        "EVD-020",
        "EVD-026",
        "EVD-071"
      ]
    },
    {
      "id": "ASM-002",
      "class": "continuable",
      "source_open_ids": "OPEN-09/11",
      "statement": "TTFT first actual reasoning<=3s и pause goal15s — operational goals, не hard deterministic unit guarantee; watchdog default20/60/60 и status<=1s заданы текущим брифом.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-019",
        "EVD-060"
      ]
    },
    {
      "id": "ASM-003",
      "class": "continuable",
      "source_open_ids": "OPEN-12/13/14",
      "statement": "Статусы [мост] разрешены текущим брифом с grace; model bytes не меняем, retries без reasoning dedup. Design follows explicit role/rework brief, not independently validated owner decision or executed runtime acceptance. No claim of owner confirmation; verify at Stage3/H gates. Фичефлаг не требует human exception: кодовый default=false, runtime JSON=true только H7 после H3/H6, атомарный false/file removal/disable-file откат. Это архитектурный контракт, runtime NOT_RUN.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-060"
      ]
    },
    {
      "id": "ASM-004",
      "class": "continuable",
      "source_open_ids": "OPEN-02/04",
      "statement": "Три baseline tests входят в Stage3 текущего брифа: expected spawns/finish/tool_calls согласовать cap3 и fresh per-test resilience. Design follows explicit role/rework brief, not independently validated owner decision or executed runtime acceptance. No claim of owner confirmation; verify at Stage3/H gates.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-047",
        "EVD-048",
        "EVD-060"
      ]
    },
    {
      "id": "ASM-005",
      "class": "continuable",
      "source_open_ids": "OPEN-07",
      "statement": "Default ask_reject и optional env=deny проверяются FakeServe; живую совместимость обеих safe policies с Zen и no-file mutation доказывает H6. Автопереключения политик нет; отсутствие safe endpoint или401/403 fail-closed.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-022",
        "EVD-050"
      ]
    },
    {
      "id": "ASM-006",
      "class": "continuable",
      "source_open_ids": "OPEN-05/16",
      "statement": "Неподтверждённые direct Zen HTTP/другие run форматы не нужны выбранному A1/C, не утверждать их невозможность.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-024",
        "EVD-025"
      ]
    },
    {
      "id": "ASM-007",
      "class": "continuable",
      "source_open_ids": "OPEN-17",
      "statement": "Реальная deploy identity и DSH live acceptance — отдельный rollout шаг после clean-room, не требование доступа к ~/.dsh в VER.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-034",
        "EVD-058",
        "EVD-059"
      ]
    }
  ],
  "drivers": [
    "RC-1: run CLI буферизует reasoning до ended (F-17/F-18)",
    "RC-2: многоэтапные deadline и очистка вместо 780–856 с тишины",
    "RC-3: DSH видимость по непустому reasoning_content и завершённому абзацу",
    "REQ-002/003: стабильный OpenAI контракт и 17 legacy test modules",
    "REQ-012/013/015: запрет built-ins, per-spawn proxy env rotation (не доказанная Zen IP ротация), безопасные secrets/loopback ownership"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-005",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-013",
        "REQ-014",
        "REQ-017",
        "REQ-018"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; 0 failed во всех существующих 17 модулях + dedicated suite; 3 baseline tests исправлены, production cap=3",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-002",
        "REQ-003",
        "REQ-011",
        "REQ-017"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && python3 -m unittest discover -s tests -p \"test_*.py\"",
      "expected": "exit 0; 0 failures/errors, запуск из bridge cwd (не из repo root), все новые tests используют unittest.TestCase или stdlib-compatible helper",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier",
      "baseline": {
        "evidence_id": "EVD-070",
        "cwd": "bridges/opencode-zen-bridge",
        "tests": 378,
        "elapsed_s": 122.956,
        "import_errors": 0,
        "failures": 3,
        "status": "BASELINE_RED; target full green after allowed3test fixes"
      }
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "REQ-002",
        "REQ-018"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; root cross-bridge regression без живых owner ресурсов; environment-specific skips разрешены только унаследованные",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-017"
      ],
      "kind": "command",
      "command": "python3 - <<'VER004'\nimport ast, collections, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--check','--no-cache','--range',f'{start}:{end}',str(f)], cwd=root)\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-ver004-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
      "expected": "exit0 after Stage3. New file full ruff format; legacy added/modified hunks git diff-U0 origin/dev checked via ruff format --check --range start:end. Full lint all3, exactly inherited zen_catalog E402 site only excepted via server-only --extend-ignore E402 (new lint0); no noqa/config edit. Isolated bridge-cwd basedpyright temporary /tmp project, all3 errorCount0; new test0diagnostics/Any; server Any<=125 each, nonAny per-rule+total<=720, step<=194; new changed code0Any/0unused-call-result. Immutable _run_env and both Google function slices enforced separately VER-005. NOT_RUN until new file exists.",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox. Run command from repo_root; invokes basedpyright with cwd=absolute bridge and exact temporary include+extraPaths, never root pyrightconfig. origin/dev must exist locally (no implicit fetch); missing ref is FAIL, not empty-range bypass. Delete temporary project in finally.",
      "owner": "verifier",
      "baseline_transition": {
        "old": "v2 full-file ruff format changes3216diff lines/frozen hash; root pyright80 errors wrong imports; server564+step162 warnings, server3type errors in isolated config,1E402.",
        "new": "0 type errors on all3; reachability by lower-case mutable catalog source symbol and explicit proc is not None guards before both returncode uses. Existing import zen_catalog kept; only exact inherited E402 CLI exception, no blanket new E402. Legacy range gate preserves frozen byte slices. NonAny allowance explicit design delta with review a3, Any<=125 retained.",
        "owner": "Stage3 Coder in three-file allowlist; no test_run_env/start.sh/config edits; independent Verifier runs actual command; stage2 syntax/contract checks only."
      },
      "warning_policy": {
        "baseline": {
          "server_total": 564,
          "step_total": 162,
          "new_test": "NOT_PRESENT"
        },
        "server_total_max": 720,
        "step_total_max": 194,
        "new_test_total_max": 0,
        "new_changed_code": {
          "reportAny": 0,
          "reportExplicitAny": 0,
          "reportUnusedCallResult": 0
        },
        "rationale": "Server nonAny allowance+156 upper total and targeted per-rule ceilings for strict unknown/narrowing/unannotated members; step allowance+32 for isolated fresh resilience assertions. Explicit no-new-Any and no-unused-call-result in changed code; new tests zero diagnostics. Unlisted server rules0. Total cap remains even if per-rule sum greater. This is proposed architecture budget delta for a3, not silently frozen v2 ceiling; no type/lint suppression."
      }
    },
    {
      "id": "VER-005",
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
        "REQ-013",
        "REQ-014",
        "REQ-015",
        "REQ-016",
        "REQ-017",
        "REQ-019",
        "REQ-020"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
      "expected": "exit0, both independent GroupA and GroupB. All prior v2 oracles retained except explicitly superseded isolation/format/warning choices. GroupA no FakeServe; GroupB six frozen fixture families with nested form paths, complete JSON args fallback, reject/cancel+interrupt and zeroStep2; secret sentinels all3env branches; in-memory DB/auth;1lsof then persistent lanes; crash helper+startup reaper; fallback table counter oracle;15s stall heartbeat; 46keys/24gates; immutable raw function hashes; thread/FD/aux math. NOT_RUN Stage2. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN.",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier",
      "groups": {
        "A": {
          "name": "RC-2/RC-3 watchdog & killpg",
          "stage": "3a",
          "test_class": "TestLegacyWatchdogAndKillpg",
          "command": "cd bridges/opencode-zen-bridge && python3 -m unittest tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg -v",
          "dependencies": "FakeCLI only; never instantiate FakeServe; independent legacy supervisor/status/cap3/O-EXIT/baseline errors tests. Stdlib discover executes class.",
          "status": "NOT_RUN"
        },
        "B": {
          "name": "Serve transport & FakeServe",
          "stage": "3b",
          "test_class": "TestServeTransportAndFakeServe",
          "command": "cd bridges/opencode-zen-bridge && python3 -m unittest tests.test_realtime_reasoning.TestServeTransportAndFakeServe -v",
          "dependencies": "Frozen six-family fixtures; transport/env/listener/crash/fallback/health+normal resource oracles. Group A PASS precondition; failures identify own group immediately. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN.",
          "status": "NOT_RUN"
        }
      },
      "immutable_google_slices": {
        "source": "git show origin/dev:bridges/opencode-zen-bridge/server.py",
        "symbols": [
          "_stream_google_sse",
          "_execute_google_once"
        ],
        "method": "ast FunctionDef/AsyncFunctionDef lineno..end_lineno inclusive over raw bytes splitlines(keepends=True), including terminal LF; compare byte-identical with baseline for each function, not AST-equivalence; current frozen _run_env literal digest also mandatory."
      },
      "orphan_oracles": "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN."
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как получить настоящие reasoning/text delta и сохранить обратимый legacy-путь?",
      "choice": "Option C/A1: один ephemeral serve v2.1.2 на попытку; canonical source для SSE/JSON. В auto run fallback только до HTTP-заголовков ответа POST /prompt И до первого валидного события исполнения текущей сессии; после барьера никакого silent run fallback.",
      "alternatives": [
        "A2: общий daemon экономит холодный старт, но объединяет failure domain и child env; самостоятельная ротация egress внутри georouter не доказана ни для A1, ни для A2 (F-15/F-27).",
        "B: прямой HTTP Zen — меньше ресурсов, но 429 F-24/F-25 и нет подтверждённого client context; не выбирается без PoC.",
        "L: только run watchdog/status — минимален, но не устраняет RC-1.",
        "OPENCODE_DB=:memory: selected (EVD-071120.7ms/156.8MiB/0.db), preserves standard read-only auth.json; empty XDG_DATA_HOME137.9ms/203.5MiB breaks opencode-go auth unless explicitly passed read-only. Shared DB + _StartupGate rejected: shared mutation/locks violate frozen scope; no automatic fallback to that option.",
        "--port 0 + stdout port announcement considered: child picks own port but stable versioned stdout announcement not evidenced; would require new bounded parser/ownership proof. Choose parent-reserved ephemeral port + one lsof + persistent lanes; port race remains fail-closed with cap3.",
        "Two independent deliveries3a then3b considered per analyst§4. Stage3a: RC-2/RC-3 watchdog/status/killpg, baseline tests/O-EXIT/VER004 debt; Stage3b: serve behind selector. Chosen one feature branch and eventual MR to meet owner request «реалтайм размышления... доводи дело до мра», but implementation/verification staged3a→3b and Group A must pass without FakeServe. Separate future MR for3a possible only by owner scope decision; no new delivery promised here."
      ],
      "drivers": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-012",
        "REQ-013 / AC-018: per-spawn _next_standalone_proxy/env rotation; loopback georouter bypasses child HTTP_PROXY via NO_PROXY, не гарантия смены Zen egress IP",
        "REQ-014",
        "F-19/F-20: 109 ms server start, 127/114 ms delta medians"
      ],
      "consequences": [
        "Дополнительные SSE/control sockets и lifecycle; предел активных детей не увеличивается.",
        "run-откат теряет realtime; это видимая деградация, не доказательство REQ-001.",
        "Откат флага/режима без миграций; публичная форма ответов неизменна.",
        "Per-attempt in-memory SQLite via OPENCODE_DB=:memory:, standard XDG_DATA_HOME preserves auth; isolated owned zen-serve-state-* dirs/lease removed after kill/reap. No shared DB opens/writes.",
        "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-015",
        "EVD-017",
        "EVD-018",
        "EVD-019",
        "EVD-020",
        "EVD-021",
        "EVD-022",
        "EVD-024",
        "EVD-025",
        "EVD-040",
        "EVD-050",
        "EVD-051",
        "EVD-062",
        "EVD-063",
        "EVD-064",
        "EVD-070",
        "EVD-071",
        "EVD-072",
        "EVD-073",
        "EVD-074"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "configuration": {
          "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": {
            "default": false,
            "purpose": "Существующий env override: явные 0/false/no/off принудительно run; явные 1/true включают auto serve при native OPENCODE_BIN. Отсутствующий override использует boolean REALTIME_SERVE_ENABLED из DYNAMIC_CONFIG_PATH с кодовым default=false. Новые env не добавляются; start.sh заморожен."
          },
          "OPENCODE_ZEN_BRIDGE_TRANSPORT": {
            "values": [
              "auto",
              "serve",
              "run"
            ],
            "default": "auto",
            "precedence": "1) TRANSPORT=run OR существующий env OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED в {0,false,no,off} OR disable-serve по OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE OR открытый sticky TTL _ServeHealth ->строго run. Явный env/run guard раньше stat/serve allocations; файл и health до subprocess. 2) TRANSPORT=serve ->serve, даже при кодовом default=false, но не обходит пункт1/security; ошибки явные, без silent run fallback. 3) TRANSPORT=auto ->serve iff runtime boolean REALTIME_SERVE_ENABLED=true (либо env=1/true) AND OPENCODE_BIN подтверждён native opencode (не текстовый #! fake, кроме явного test-only override). Иначе прежний run --format json. Невалидный TRANSPORT ->config error."
          },
          "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY": {
            "values": [
              "ask_reject",
              "deny"
            ],
            "default": "ask_reject",
            "purpose": "Одна policy на attempt; ask_reject сохраняет tool schemas, немедленно отвечает decision=reject. deny выбирается env до запуска для отдельного H6, без пересборки. Нет автоматического deny↔ask_reject переключения ни до, ни после prompt; unsupported policy/capability -> fail-closed."
          },
          "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": {
            "default": "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
            "purpose": "Путь expanduser/resolve при конфигурации, без создания каталога. На входе нового запроса O(1) os.path.exists(); файл есть -> run без serve UUID/password/queue/thread/Popen/probes. Ошибка проверки пути -> безопасно run с redacted reason. Создание/удаление файла меняет выбор следующего запроса без рестарта; active leases завершаются или явно отменяются, без дублирования текущего prompt."
          },
          "SERVE_READY_TIMEOUT_S": 3.0,
          "SERVE_SESSION_SETUP_TIMEOUT_S": 2.0,
          "feature_flag_context": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git.",
          "DYNAMIC_CONFIG_PATH": {
            "value": "Path(__file__).resolve().parent / \"dynamic_config.json\"",
            "key": "REALTIME_SERVE_ENABLED",
            "type": "bool",
            "default": false,
            "reload": "На каждый новый запрос os.stat O(1), кэш по (st_mtime_ns, st_size), с учётом identity DYNAMIC_CONFIG_PATH для изолированных тестов. При неизменной паре без переоткрытия/JSON parsing; смена пары перечитывает bounded локальный JSON и публикует boolean snapshot под lock. Удаление, ошибка stat/read, битый JSON, неверный root или небулево значение ->false немедленно, без stale true. Ошибки чтения/валидации дают diagnostic warning без содержимого файла/секретов; повторяющийся warning ограничен, чтение ошибки можно повторить на следующем запросе. Не нужен restart Server/LaunchAgent.",
            "write": "Только rollout operator: tempfile в том же каталоге, mode0600, JSON boolean, os.replace атомарно; только после H3/H6 на H7. Локальный production файл ~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json вне git; Architect его не создаёт."
          }
        },
        "auto_fake_compatibility": "В git-клоне bridges/opencode-zen-bridge/dynamic_config.json отсутствует и не коммитится; default=false гарантирует прежний run для всех378 fake-CLI baseline tests REQ-003/AC-004, без опоры на shebang/имя теста/FAKE_OC_MODE. При explicit enabled auto дополнительно cached executable path+mtime_ns+size/first bytes: shebang/text ->run без --help/--version/serve subprocess; native opencode ->serve. Явный test-only eligibility override допустим только fixtures; force serve для FakeServe сохраняет первый kill-switch приоритет и stdin=DEVNULL. Explicit env false/run ->zero serve UUID/password/queue/threads/probes/Popen до file stat; default=false selector допускает только O(1) config stat, без serve allocations. При смене executable cache key старые capability/health инвалидируются.",
        "spawn": "На каждую реальную попытку общий _RequestAttempts/slot, единый admission deadline<=5.0s для _SpawnRateLimiter+_StartupGate (не два ожидания по5s), свежий _serve_env(model_id) поверх одного неизменного _run_env(model_id), новая per-spawn _next_standalone_proxy запись. Parent socket.bind((127.0.0.1,0)), getsockname()[1]; держать резерв до непосредственно Popen, затем close reserve и Popen([OPENCODE_BIN,serve,--hostname,127.0.0.1,--port,str(port)],stdin=DEVNULL,start_new_session=True,close_fds=True), сохранить child_pgid. Prompt/Basic password не передавать argv/stdin. До первого Authorization или prompt доказать owner listener по listener_ownership; при port race cleanup + новый порт только в оставшемся ready deadline, каждый новый Popen расходует общий cap3 и spawn token. Ни одного бесплатного spawn при EADDRINUSE. Apply serve_env_sanitization to ALL3 branches and data_isolation; keep standard XDG_DATA_HOME, set OPENCODE_DB=:memory:. Register crash-safe lease before readiness/auth and arm parent-death watchdog before admitting prompt, see crash_recovery. lsof owned helper once per successful spawn, not model attempt; no extra model Popen.",
        "startup": "SERVE_READY_TIMEOUT_S=3.0s (ready_budget_s=3.0): после owner proof лёгкий authenticated GET /api/session/active, HTTP200 + $.data object map of active sessions (empty={}); не качать 281KB /openapi.json на каждом spawn. Control I/O slices<=.25s, всего<=3 readiness TCP probes, remaining request deadline/cancel всегда проверяются. Child EOF/no listener/incompatible protocol -> ServeUnavailable. Пароль secrets per spawn в OPENCODE_SERVER_PASSWORD ПОСЛЕ whitelist, Basic opencode:<password>, никогда в argv/URL/log. stdout/stderr bounded drain+redact. HTTP на loopback напрямую без proxy/redirects. Readiness не устанавливает first_event_ms и не сбрасывает first_event/token часы.",
        "fallback_barrier": "State machine: ADMISSION -> SPAWN/OWNER/READY -> CREATE/SUBSCRIBE -> PROMPT_SENDING -> DELIVERED -> TERMINAL -> CLEANUP. Auto ServeUnavailable на старте/create/subscribe или до получения HTTP response headers POST /api/session/{id}/prompt допускает один budgeted run fallback, ТОЛЬКО если не было валидного события исполнения созданной session после начала отправки prompt, нет model/tool output, auth/security failure, cancel или deadline. Перед run полностью close/join/killpg/reap старую attempt, удалить temp data; новый Popen требует тот же retry token/Full Jitter/attempt ceiling<=3. С первого response header POST /prompt (любой status) ИЛИ первого session execution event после prompt delivery лачится DELIVERED=true; silent fallback и переключение на run для текущего запроса запрещены, включая отсутствие response body и headers-pending+SSE-started. Prompt POST исполняется daemon worker параллельно SSE; до header/события ожидание ограничено остатком first_event20s/first_token60s и total deadline. Даже до headers неизвестная доставка может дать повторную генерацию: допустимость этой границы явно задана текущим brief RW-001, это НЕ exactly-once; старый PGID должен быть убран до fallback, built-ins никогда allow. После barrier watchdog может выполнить только явный общий retry того же транспорта с retry-status/cleanup/cap, не скрытый run fallback. HTTP401/403/auth/permission/capability-security denial -> fail-closed без fallback/auto policy switching на любой фазе. Authoritative phase/event/counter table: fallback_decision_table. first_event20 preheader/noevent ->budgeted fallback_to_run; after anyheader ->explicit serve_retry. Error headers latch barrier before HTTP classification.",
        "session_flow": "После listener proof/readiness и подтверждения safe permission capability POST /api/session по session_wire.create; затем GET /api/event с HTTP200 text/event-stream и reader armed ДО отправки первого байта тела prompt. На create + subscribe один SERVE_SESSION_SETUP_TIMEOUT_S=2.0s, не включая model generation или ожидание POST /prompt response. Передать полный prompt в JSON body через единственный daemon delivery worker, одновременно читать SSE в owned reader; supervisor/SSE writer не ждут блокирующий POST и остаются cancel-aware. Один POST /prompt с delivery=steer,resume=true; transport HTTP headers/ошибки передаются supervisor как control events. First-event/token часы якорятся на prompt_send_start, не на HTTP ready/создание сессии. Filter data.sessionID==created_sid; реальные v2 события не содержат executionID, поэтому использовать own per-attempt session + prompt-send generation latch, event id дедуп и assistantMessageID step key, не выдумывать executionID. server.connected/session.created/global updates/pre-prompt events не считаются first execution. Terminal success/failed независим от text end; EOF без terminal -> protocol failure. step.ended с готовым DSH tool call -> остановить дальнейшее исполнение/cleanup. Include nested form.created.data.form.sessionID filtering before flat session filter. Mandatory reject/cancel then interrupt single_turn_control; never wait on prompt POST, never stream Step2.",
        "tool_policy": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6. _run_env does NOT sanitize every branch; _serve_env must apply serve_env_sanitization to all3 branches. Mandatory form.created→cancel and reject/cancel→immediate interrupt single_turn_control; JSON args fallback input.ended.data.text when called absent; no second-step output.",
        "event_contract": {
          "shape": "Iterator canonical tuples для обоих потребителей; object/TypedDict validation. Public OpenAI unchanged; legacy parser остаётся для run. Полные wire fixtures ниже frozen v2.1.2, metadata id/created synthetic, field paths подтверждены EVD-062/EVD-063.",
          "session.reasoning.delta": "$.data.delta -> (reasoning,{reasoning_content:delta}); delta bytes only, ended не повторяет full text. Если native encrypted metadata есть в started/ended, сохранять существующим reasoning_details mapping без повторной text delta.",
          "session.text.delta": "$.data.delta -> (text,{content:delta}) -> тот же ToolCallParser.feed/emit_content.",
          "session.step.ended": "$.data.tokens input/output/reasoning + $.data.tokens.cache.read -> canonical input/output/reasoning/cached; один учёт по $.data.assistantMessageID, terminal не удваивает usage.",
          "session.tool.*": "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side. On input.ended save $.data.text and parse JSON as object with runtime validation. Prefer called.data.input if present and valid; if called absent before failed/step.ended use completed input.ended.text, including streaming→failed. Never emit partial JSON; dedup by sessionID/assistantMessageID/call id. Both paths give identical mapped DSH tool_calls. Invalid JSON follows existing incomplete/unmapped recovery, not invented empty args.",
          "session.step.failed / session.execution.failed": "$.data.error {type,message,status?,response?,retryAfterMs?} ->canonical error{statusCode,message}: statusCode=$.data.error.status если integer100..599; иначе explicit known type mapping provider.free-limit429/auth401/permission denial403, unknown null. Terminal independent, one cause not counted twice.",
          "session.execution.succeeded": "terminal success metadata, не text/reasoning; гарантированно дренировать уже полученный step.ended перед финальным usage.",
          "other": "first_event latch только валидный execution/step/reasoning started текущей session после prompt; валидные current-session model delta также доказывают начало исполнения. server.connected, HTTPready, session.created, чужие session/control/comments/status не latch и не model token. form.created session lookup is nested data.form.sessionID; shared flat filter must special-case this valid envelope before discard.",
          "payload_validation": "Проверять exact field paths/types и mandatory sessionID до emit. Текущая schema shape mismatch -> invalid_serve_event (не пустая полезная delta), отдельный ServeHealth; permission capability mismatch ->security fail-closed. Incremental UTF8/CRLF/multiline SSE/comments/fragment boundaries, byte budgets как прежде. Никакого Coder-discovered protocol или aliases, которых нет в frozen source. Coder и FakeServe используют frozen expected независимо; мутации delta path/token/permission должны краснить тест даже если adapter и mock согласованно ошибочны.",
          "frozen_v2_1_2_fixtures": {
            "session.reasoning.delta": {
              "wire": {
                "id": "evt_fixture_1",
                "created": 1792957431001,
                "type": "session.reasoning.delta",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "ordinal": 0,
                  "delta": "Мысль без LF"
                }
              },
              "field_paths": {
                "session_id": "$.data.sessionID",
                "step_key": "$.data.assistantMessageID",
                "ordinal": "$.data.ordinal",
                "delta": "$.data.delta"
              },
              "canonical": {
                "etype": "reasoning",
                "payload": {
                  "reasoning_content": "Мысль без LF"
                }
              }
            },
            "session.text.delta": {
              "wire": {
                "id": "evt_fixture_2",
                "created": 1792957431002,
                "type": "session.text.delta",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "ordinal": 1,
                  "delta": "Ответ\n"
                }
              },
              "field_paths": {
                "delta": "$.data.delta",
                "session_id": "$.data.sessionID"
              },
              "canonical": {
                "etype": "text",
                "payload": {
                  "content": "Ответ\n"
                }
              }
            },
            "session.step.ended": {
              "wire": {
                "id": "evt_fixture_3",
                "created": 1792957431003,
                "type": "session.step.ended",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "finish": "stop",
                  "cost": 0,
                  "tokens": {
                    "input": 17,
                    "output": 9,
                    "reasoning": 4,
                    "cache": {
                      "read": 3,
                      "write": 2
                    }
                  }
                }
              },
              "field_paths": {
                "tokens": "$.data.tokens",
                "dedup_step_key": "$.data.assistantMessageID",
                "cached": "$.data.tokens.cache.read"
              },
              "canonical": {
                "etype": "step_finish",
                "payload": {
                  "input": 17,
                  "output": 9,
                  "cached": 3,
                  "reasoning": 4
                }
              },
              "note": "Реальный v2 wire cache:{read,write}; cached=cache.read в legacy canonical tuple. cache.write не суммировать с cached read. Canonical input/output/reasoning копировать по существующей семантике; считать раз по assistantMessageID. Отсутствие required tokens/cache/read — invalid_serve_event, не нули."
            },
            "session.permission.requested / session.tool.*": {
              "wire_event_name": "permission.asked",
              "logical_family": "session.permission.requested",
              "wire": {
                "id": "evt_fixture_4",
                "created": 1792957431004,
                "type": "permission.asked",
                "data": {
                  "id": "per_fixture_1",
                  "sessionID": "ses_fixture_1",
                  "action": "bash",
                  "resources": [
                    "*"
                  ],
                  "source": {
                    "type": "tool",
                    "messageID": "msg_fixture_1",
                    "id": "call_fixture_1"
                  }
                }
              },
              "field_paths": {
                "session_id": "$.data.sessionID",
                "request_id": "$.data.id",
                "tool_call_id": "$.data.source.id",
                "action": "$.data.action",
                "resources": "$.data.resources"
              },
              "reply": {
                "method": "POST",
                "path": "/api/session/ses_fixture_1/permission/per_fixture_1/reply",
                "body": {
                  "decision": "reject"
                },
                "success_status": 204
              },
              "tool_lifecycle": [
                {
                  "id": "evt_fixture_5",
                  "created": 1792957431005,
                  "type": "session.tool.input.started",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "name": "bash"
                  }
                },
                {
                  "id": "evt_fixture_6",
                  "created": 1792957431006,
                  "type": "session.tool.input.delta",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "delta": "{\"command\":\"printf probe\"}"
                  }
                },
                {
                  "id": "evt_fixture_7",
                  "created": 1792957431007,
                  "type": "session.tool.input.ended",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "text": "{\"command\":\"printf probe\"}"
                  }
                },
                {
                  "id": "evt_fixture_8",
                  "created": 1792957431008,
                  "type": "session.tool.called",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "input": {
                      "command": "printf probe"
                    },
                    "executed": false
                  }
                },
                {
                  "id": "evt_fixture_9",
                  "created": 1792957431009,
                  "type": "session.tool.failed",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "error": {
                      "type": "permission.rejected",
                      "message": "Rejected by bridge policy"
                    },
                    "executed": false
                  }
                },
                {
                  "id": "evt_fixture_10",
                  "created": 1792957431010,
                  "type": "permission.replied",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "requestID": "per_fixture_1",
                    "reply": "reject"
                  }
                }
              ],
              "canonical": {
                "etype": "tool_use",
                "payload": {
                  "part": {
                    "tool": "bash",
                    "state": {
                      "input": {
                        "command": "printf probe"
                      },
                      "status": "error"
                    }
                  },
                  "call_id": "call_fixture_1"
                }
              },
              "note": "Family label из brief — не имя wire event. В бинарнике нет session.permission.requested или session.tool.started: actual names permission.asked и session.tool.input.started/called/progress/success/failed. Имя tool копить из input.started; canonical payload emit после complete input/called, не исполнять по частичному JSON. Lifecycle updates не создают повторный DSH tool_call; own denied event не является model progress. Указанный failed message — синтетическое fixture значение типа error, не заявление о захваченном live отказе."
            },
            "session.execution.failed": {
              "wire": {
                "id": "evt_fixture_11",
                "created": 1792957431011,
                "type": "session.execution.failed",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "error": {
                    "type": "provider.free-limit",
                    "message": "Free usage limit reached"
                  }
                }
              },
              "field_paths": {
                "error": "$.data.error",
                "message": "$.data.error.message",
                "error_type": "$.data.error.type",
                "statusCode": "$.data.error.status if present integer100..599, else explicit type mapping"
              },
              "canonical": {
                "etype": "error",
                "payload": {
                  "statusCode": 429,
                  "message": "Free usage limit reached"
                }
              },
              "note": "provider.free-limit ->429; provider.auth/permission denial ->fatal401/403; неизвестный type сохраняется как явная ошибка с statusCode=null, не выдумывать retryability. step.failed + execution.failed одной cause дедуп без потери terminal. Numeric wire key status, not statusCode/data.statusCode; source Session.StructuredError. Missing numeric status allowed as in captured free-limit event."
            },
            "form.created / form.cancelled": {
              "wire": {
                "id": "evt_fixture_form_1",
                "created": 1792957431012,
                "type": "form.created",
                "data": {
                  "form": {
                    "id": "frm_fixture_1",
                    "sessionID": "ses_fixture_1",
                    "title": "Question",
                    "fields": [
                      {
                        "key": "answer",
                        "type": "string",
                        "title": "Question",
                        "required": true
                      }
                    ]
                  }
                }
              },
              "field_paths": {
                "session_id": "$.data.form.sessionID",
                "form_id": "$.data.form.id",
                "info": "$.data.form",
                "state": "Form.State=pending; Form.Info has no state field"
              },
              "cancel": {
                "method": "POST",
                "path": "/api/session/ses_fixture_1/form/frm_fixture_1/cancel",
                "body": null,
                "success": "HTTP2xx empty success; protocol preflight freezes exact success response from used endpoint schema; no fabricated reply/body"
              },
              "cancelled_wire": {
                "id": "evt_fixture_form_2",
                "created": 1792957431013,
                "type": "form.cancelled",
                "data": {
                  "id": "frm_fixture_1",
                  "sessionID": "ses_fixture_1"
                }
              },
              "state_schema": {
                "pending": {
                  "status": "pending"
                },
                "answered": {
                  "status": "answered",
                  "answer": {}
                },
                "cancelled": {
                  "status": "cancelled",
                  "message": "optional string"
                }
              },
              "canonical": {
                "etype": "control_only",
                "emit_model_text": false,
                "actions": [
                  "suppress Step2 immediately",
                  "cancel via control<=0.25s",
                  "interrupt own session",
                  "return accumulated mapped tool_calls or existing recovery"
                ]
              },
              "negative_mutations": [
                "flatten form.sessionID to data.sessionID -> reject invalid event, no foreign cancel",
                "missing form.id/fields/title ->invalid_serve_event",
                "foreign nested sessionID ->ignore",
                "form.cancelled wrong id/session ->not own success",
                "cancel endpoint failure ->fail-closed, no permission allow or Step2 output"
              ],
              "provenance": "EVD-073 source schema; synthetic ids/titles/empty fields, not observed runtime cancellation"
            }
          },
          "fixture_provenance": {
            "source": "EVD-062: read-only embedded schemas/API v2.1.2; EVD-063: analyst PoC script+failure envelope",
            "binary_sha256": "b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c",
            "examples": "Six source-schema families; synthetic ids/timestamps/texts, Form.Info wrapper verified EVD-073; no live tool success asserted.",
            "immutable_oracle": "В Stage3 fixture literals копируются в tests/test_realtime_reasoning.py; до adapter expectations сверить fixture canonical SHA256 с пакетным fingerprint. Менять fixture по реализации запрещено."
          },
          "frozen_fixture_sha256": "12456f8b4568c3f3b4c52677118748faf80512f376b2b1b2f467226ff94a1f38",
          "form.created / form.cancelled": "form.created uses data.form.sessionID/id (Form.Info nested); validate own session before action. Cancel immediately via POST /api/session/{id}/form/{formID}/cancel, no answer/allow; form.cancelled data.id/sessionID settles same form. Not a model token/first-event. Error->security fail-closed+kill. See single_turn_control.",
          "fixture_digest_serialization": "UTF-8 json.dumps(frozen_v2_1_2_fixtures,ensure_ascii=False,sort_keys=True,separators=(\",\",\":\")); no trailing LF"
        },
        "non_stream": "serve используется и stream=False через общий source; Run копит чистые model reasoning/text/native/usage как сейчас. Synthetic [мост] статусы — только SSE presentation, в JSON reasoning_content не добавляются. Google direct dispatch остаётся первым и не создаёт serve/новые timers.",
        "listener_ownership": {
          "protocol": [
            "Parent reserves127.0.0.1:0; release immediately before Popen explicit --port; saved child PGID. No Auth/prompt until proof.",
            "SPAWN→READY after port LISTEN: exactly once lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp, timeout0.35s; one listener_pid, os.getpgid(listener_pid)==child_pgid and proc.poll() is None. Mismatch/ambiguous/timeout counts _ServeHealth failure, zero secret bytes.",
            "After proof establish/retain3 HTTP/1.1 Keep-Alive connections: control, SSE, prompt. Loopback direct, redirects/proxy disabled. Before each authenticated request proc.poll() is None; never lsof in permission/form/interrupt/DELETE hot path.",
            "Cached proof bound to exact live child lease + sockets, never globally port-only. On dead proc close lanes and fail-closed, no Auth to replacement listener. On control disconnect one explicit reconnect with fresh proof<=0.35s before Auth; not transparent retry of sent request, no prompt replay. SSE/prompt disconnect closes attempt (no transparent reconnect).",
            "Reconnect is separate recovery budget outside fast control SLA; pending urgent permission/form cannot wait0.35s while claiming<=0.25s: terminate attempt fail-closed and kill own PGID. Cleanup never reconnects; broken control skips API and uses group kill.",
            "Foreign listener/PGID: no API or signals to foreign PID. Only own child cleanup; retry new port allowed within original ready3s/admission/cap3. lsof helper has own bounded PID lifecycle."
          ],
          "owner_probe_timeout_s": 0.35,
          "reconnect_budget_s": 0.35,
          "ready_deadline_includes": "lsof+keepalive setup+GET active and cache-miss protocol projection all within3.0s; repeated port attempt does not reset it.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "protocol_compatibility": {
          "version": "2.1.2",
          "cache_key": [
            "resolved executable path",
            "mtime_ns",
            "size"
          ],
          "handshake": "On changed executable stat key invalidate cache and revalidate owned child /api/info version+pid and bounded /openapi.json<=512KiB inside ready3s. app version2.1.2 is reference, NOT equality-only reject gate. Permit changed binary version/mtime iff canonical required-endpoints/schema/event projection hash equals validated reference projection. API info.version0.0.1 distinct. Required projection includes Model.Ref,Permission.Ruleset,PromptInput,TokenUsage/StructuredError,Form.Info/State and six fixture families + all used methods/path parameter schemas. No permission endpoint ->security fail-closed; benign other projection mismatch ->ServeUnavailable before prompt.",
          "invalidation": "mtime/size/path invalidate capability cache, not permanent ban. Same projection hash after recheck keeps serve, differing used schema routes new auto to run with explicit diagnostic reason. No accept-by-version-string alone; reference normalized projection freeze in first provider-free Stage3 preflight before enable. Arbitrary old raw hash is not a projection hash; never invent a digest.",
          "fixture_source_evidence_ids": [
            "EVD-062",
            "EVD-063"
          ],
          "cache_ownership": "Per-Server bounded capability record (only executable key/version/schema hashes/projection, no password/session/prompt). Один fill-owner на binary key; конкурентные fills ждут только remaining own ready3s без блокировки writer, owner cancellation снимает in-flight; никаких live sockets/passwords в cache. Это setup capability metadata, не ControlPlane/Snapshot polling.",
          "projection_freeze": "VER-005 independent expected fixtures anchor required field semantics; first provider-free preflight records normalized projection SHA256 from verified2.1.2 endpoint response; subsequent binary keys compare that immutable in-process reference. If no verified reference exists, exact fixture projection validation is mandatory before recording reference. New binary alone cannot self-certify expected schema. No new repo config/artifact outside allowlist.",
          "telemetry": "REQ-016/AC-021 explicitly authorize transport,first_event_ms,ttft_ms in O-EXIT/v1. Preserve existing keys/types and one-exit cardinality; no incompatible rename. Fallback reason and transport-history details may be adjacent bounded redacted BRIDGE-TRANSPORT/v1 diagnostic correlated by existing request id, so strict O-EXIT parsers remain valid. Log selected transport=serve|run and reason for stat/schema/degraded/disable fallback; /health unchanged."
        },
        "admission": "Один monotonic pre_spawn_deadline=now+min(5.0,remaining_request) охватывает _SpawnRateLimiter и _StartupGate. Сначала получить rate token с timeout=remaining_admission; gate может ждать только остаток этого же окна и fail-open по legacy, без добавочных5s; timeout rate token -> не spawn. Hold gate<=12s не является отдельным pre-spawn wait; release при готовности собственного child/EOF/finally, HTTP ready по-прежнему не событие модели. Cancel poll<=.25s, каждый Popen включая fallback/race учитывается _RequestAttempts<=3; token не обходить.",
        "session_wire": {
          "schema": "opencode serve v2.1.2, EVD-062/EVD-063; paths и JSON properties заморожены до Coder",
          "create": {
            "method": "POST",
            "path": "/api/session",
            "headers": {
              "Content-Type": "application/json",
              "Authorization": "Basic <ephemeral runtime secret, never stored>"
            },
            "body": {
              "location": {
                "directory": "<existing absolute request workdir>"
              },
              "model": {
                "providerID": "opencode",
                "id": "deepseek-v4.1-flash-free",
                "variant": "high"
              },
              "permissions": [
                {
                  "action": "*",
                  "resource": "*",
                  "effect": "ask"
                }
              ]
            },
            "success_status": 200,
            "response_id_path": "$.data.id",
            "permission_variant": "Для policy=deny тот же ruleset с effect=deny; ask_reject effect=ask + немедленный decision=reject. В API permissions — ARRAY rules, не config object {\"*\":\"ask\"}.",
            "model_mapping": "Тот же resolved provider/model#variant: отделить providerID и id; #high -> model.variant=\"high\"; effort off/none -> variant отсутствует, не #off. --thinking относится к CLI presentation; HTTP thinking задаётся существующим resolved variant без несуществующего поля thinking."
          },
          "subscribe": {
            "method": "GET",
            "path": "/api/event",
            "headers": {
              "Accept": "text/event-stream"
            },
            "success_status": 200,
            "body": "SSE data JSON envelope {id,created,type,data}; subscribe armed до prompt body, filter data.sessionID"
          },
          "prompt": {
            "method": "POST",
            "path": "/api/session/{id}/prompt",
            "body": {
              "text": "<full unchanged prompt>",
              "files": [],
              "delivery": "steer",
              "resume": true
            },
            "success_status": 200,
            "response": "$.data is Session.Inbox.User; $.data.id is inbox/message id, durable admission, не model completion",
            "delivery": "steer/queue — admission boundary, НЕ флаг неблокирующего HTTP. Для единственного fresh session input выбран steer; один POST, worker может блокироваться на headers/body параллельно чтению SSE. Не вызывать generate, resume повторно или повторный prompt при задержке ответа.",
            "budget": "Не session_setup2s. От prompt_send_start ограничен оставшимися first_event20s/first_token60s/общим TIMEOUT1800; при продвижении session событий supervisor не отменяет HTTP только потому, что истёк first_event, но total/cancel/terminal закрывают сокет. Response body не нужен для продолжения чтения событий после headers."
          },
          "permission_reply": {
            "method": "POST",
            "path": "/api/session/{id}/permission/{requestID}/reply",
            "body": {
              "decision": "reject"
            },
            "success_status": 204,
            "request_id_path": "$.data.id of permission.asked; session path id=$.data.sessionID",
            "note": "Wire key decision, не reply; permission.replied notification содержит reply=reject. Никогда once/always/allow.",
            "after_reply": "Immediately interrupt own session; barrier latched before reply; Step2 suppressed."
          },
          "cleanup": {
            "interrupt": "POST /api/session/{id}/interrupt",
            "delete": "DELETE /api/session/{id}",
            "aggregate_api_budget_s": 0.2,
            "connection_policy": "Use existing proven Keep-Alive control only; no lsof/reconnect. If unavailable skip API, kill owned PGID; do not add0.35s reconnect into0.20s API budget.",
            "interrupt_each_s": 0.09,
            "delete_each_s": 0.09,
            "scheduling_margin_s": 0.02
          },
          "readiness": {
            "method": "GET",
            "path": "/api/session/active",
            "success_status": 200,
            "response_example": {
              "data": {}
            },
            "schema": "$.data is record keyed by sessionID, not an array; source byte offset114978382",
            "budget": "part of ready_budget_s=3.0, not first_event; owner proof before auth"
          },
          "version_probe": {
            "method": "GET",
            "path": "/api/info",
            "response_example": {
              "version": "2.1.2",
              "pid": "<actual child PID integer>"
            },
            "note": "Пример pid placeholder только в документации, wire integer; owner PGID проверяется до Auth независимо от self-reported pid. appversion2.1.2 отличается от OpenAPI.info.version0.0.1. Once per executable stat key, withinready3s."
          },
          "form_cancel": {
            "method": "POST",
            "path": "/api/session/{id}/form/{formID}/cancel",
            "body": null,
            "form_id_path": "$.data.form.id",
            "session_id_path": "$.data.form.sessionID",
            "timeout_s": 0.25,
            "on_error": "fail-closed+kill own PGID; never reply/answer to question"
          }
        },
        "data_isolation": {
          "selected": "env[\"OPENCODE_DB\"] = \":memory:\" for every serve spawn; never use shared opencode.db/opencode-next.db. EVD-071 calibrates ready3.0s with120.7ms,156.8MiB<=256MiB and0 open SQLite files.",
          "XDG_DATA_HOME": "Preserve effective standard XDG_DATA_HOME from trusted base env (unset retains HOME default). Do not overwrite with empty directory: opencode-go/* must read standard opencode/auth.json. Shared auth file is read-only input; do not write/copy/log credentials. No readonly bind mount/symlink changes to owner filesystem.",
          "state_and_workdir": "Allocate one owned tempfile.mkdtemp(prefix=\"zen-serve-state-\") per attempt, with state/ and tmp/ subdirectories. Set XDG_STATE_HOME and TMPDIR to those paths. Popen cwd may use owned dir, but POST session location.directory remains existing request workdir; no silent change to tool-relative paths. Parent lease records exact temp root.",
          "catalog_and_auth": "Preserve OPENCODE_MODELS_PATH, generated OPENCODE_CONFIG/OPENCODE_CONFIG_CONTENT and provider settings from exactly one _run_env call, sanitized below on all3 branches; auth.json remains visible for glm-5.1,kimi-k2.5,minimax-m2.5,minimax-m2.7 via opencode-go/*. Provider-free accessibility is not proof of valid live provider credential (H3/H6).",
          "alternatives": {
            "empty_XDG_DATA_HOME": "Rejected for default: loses auth.json despite preserving models. If explicitly isolated later, read-only auth propagation must be separately verified without shared DB access.",
            "shared_DB_plus_StartupGate": "Rejected: violates no shared DB mutation/lock boundary; cannot use as fallback without owner scope approval."
          },
          "ownership": "Lease + finally remove owned zen-serve-state-* only after kill/reap/readers closed; no silent ignore_errors success, verify absence, record cleanup failure. Startup reaper handles crash remnants. Cleanup aggregate<=1.2s; H3 actual disk cleanup required.",
          "preflight": "EVD-071 covers GET /api/session/active; /api/info version+pid readback NOT supplied. Before freeze-to-Coder execution gate, Stage3 first provider-free preflight rechecks both /api/info and /api/session/active on chosen env, startup<=3s/RSS/files/auth visibility; no Zen quota. H3 actual provider auth/parallel RSS remain NOT_RUN.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "typing": "Decode wire JSON as object with isinstance narrowing/TypedDict; new code no Any/casts-to-Any/type-ignore. New test0diagnostics; new legacy ranges0reportAny/reportExplicitAny/reportUnusedCallResult. VER-004 uses isolated bridge cwd + ephemeral /tmp include/extraPaths, errorCount0all3, server Any<=125each and documented nonAny per-rule/total720, step194 (baseline564/162). Rename mutable internal CATALOG_SOURCE to lower-case across server references (no external HTTP key change); guard proc is not None at both returncode sites. No new module/config/dependency. Legacy format ranges only; all3 full lint with exact existing server-only E402 exception and no new E402.",
        "transport_health": {
          "owner": "_ServeHealth per Server, key=(resolved executable,mtime_ns,size), lock/monotonic; состояние отдельно от model _UpstreamBreaker",
          "consecutive_failure_threshold": 3,
          "degrade_ttl_s": 120.0,
          "degraded_transport": "run для новых auto requests",
          "counted_failures": [
            "first_event_timeout на serve после prompt и HTTP readiness, без валидных событий исполнения",
            "invalid_serve_event / incompatible schema projection / malformed required v2 fields",
            "serve SSE EOF без terminal; first_token_timeout только при доказанной protocol/capability причине, иначе model failure",
            "listener_ownership failure/ambiguous PID/PGID mismatch/lsof timeout, once per attempt",
            "serve spawn/ready/create/subscribe local transport failure; reconnect ownership timeout; schema mismatch"
          ],
          "not_counted": "Реальные provider errors (429/free-limit,5xx,provider network), explicit auth/permission/security failure, client_gone, slot rejection и transient child DB errors не маскировать transport failure. Если валидные execution events пришли, но model token нет, first_token_timeout сохраняет обычную provider classification при отсутствии доказанного protocol defect.",
          "state_machine": "HEALTHY consecutive0..2; третий законченный protocol-specific failure -> DEGRADED(until=now+120), последующие auto requests run без serve probe/Popen. Это НЕ повтор/переключение текущего DELIVERED prompt: транспорт текущего запроса закреплён, silent replay запрещён. В DEGRADED skipped requests не продлевают TTL. При TTL expiry ровно один HALF_OPEN serve probe request (другие auto requests run); только валидный terminal success со schema-valid source очищает consecutive/degraded. Failed protocol probe -> новый TTL120. Provider failure не объявлять protocol success/failure. Neutral cancel освобождает probe, не продлевает TTL. Force serve допускает диагностику только при закрытом sticky TTL, не обходя security/kill-switch/cap3. Открытый sticky TTL применяется до explicit serve согласно configuration precedence: force serve не обходит TTL; HALF_OPEN admission после expiry остаётся прежним.",
          "breaker_isolation": "Protocol-specific failure никогда не вызывает _UpstreamBreaker.failure/commit pending model failure. Provider failures сохраняют общий breaker threshold5/cooldown jitter/HALF_OPEN1. Нейтральный transport-only финальный запрос освобождает model probe lease после cleanup; success/failure не выдумывать. _RetryBudget и MAX_TOTAL_SPAWNS остаются общими даже для protocol retry/fallback.",
          "telemetry": "REQ-016/AC-021 explicitly authorize transport,first_event_ms,ttft_ms in O-EXIT/v1. Preserve existing keys/types and one-exit cardinality; no incompatible rename. Fallback reason and transport-history details may be adjacent bounded redacted BRIDGE-TRANSPORT/v1 diagnostic correlated by existing request id, so strict O-EXIT parsers remain valid. Log selected transport=serve|run and reason for stat/schema/degraded/disable fallback; /health unchanged.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "immutable_run_env": {
          "symbol": "bridges/opencode-zen-bridge/server.py:_run_env",
          "source_slice": "ast FunctionDef.lineno..end_lineno inclusive, raw file bytes splitlines(keepends=True), includes terminal LF",
          "sha256": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
          "test_run_env_sha256": "d3d0baf57f7ccae7dd7846ab98d3da43c588a35e7f076fabe074c1212f232e05",
          "start_sh_sha256": "5430e529627b3a705da4be7641a6d079408e3cf85b6ad3333330e34cb08c190c",
          "verification": "VER-005 compare literal hashes from frozen packet; _serve_env wrapper only, never recalculate expected from edited implementation"
        },
        "serve_env_sanitization": {
          "source": "Call immutable _run_env(model_id) exactly once, then build NEW env dictionary from exact allowlist on ALL branches standalone/base_url opencode-go/static; never env=dict(os.environ) passthrough.",
          "allowlist": [
            "PATH",
            "HOME",
            "USER",
            "LOGNAME",
            "SHELL",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TZ",
            "TERM",
            "COLORTERM",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "NO_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
            "no_proxy",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "NODE_EXTRA_CA_CERTS",
            "XDG_DATA_HOME",
            "XDG_CONFIG_HOME",
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_CONTENT",
            "OPENCODE_MODELS_PATH"
          ],
          "removal": "Deny always OPENCODE_ZEN_BRIDGE_*, arbitrary parent vars (SECRET_SENTINEL included) and unrelated *_API_KEY/*_TOKEN/*_SECRET. No broad OPENCODE_* or FAKE_* wildcard; only literal routing/config keys above. Tests inject explicit fake transport dependency, no production exception for secret sentinel. OPENCODE_DB/XDG_STATE_HOME/TMPDIR and server password are NOT inherited; generated after filter.",
          "compatibility": "Proxy credentials only in explicitly required _run_env-selected HTTP(S)/ALL_PROXY values, redacted end-to-end. Config JSON from trusted _run_env retains required provider/options and selected permissions; no merging arbitrary parent secret keys. Standard auth file accessible by preserved HOME/XDG_DATA_HOME; unrelated API keys never child env.",
          "overrides": "Then set OPENCODE_DB=:memory:, owned XDG_STATE_HOME/TMPDIR, merge scoped permission policy, and generate fresh OPENCODE_SERVER_PASSWORD last. Child-only secret, never argv/log/lease. Keep models/config on opencode-go and static branches.",
          "tests": "VER-005 GroupB parameterizes standalone, opencode-go/base_url, CATALOG_MODE=static; sentinels absent, route config/models/auth paths preserved, password fresh, common DB untouched, _run_env literal hash unchanged."
        },
        "single_turn_control": {
          "trigger": "permission.asked on own session or form.created.data.form.sessionID on own session. Immediately latch step_closed/output barrier BEFORE sending any control reply; retain accumulated raw/tool arguments and suppress every later-step text/reasoning.",
          "order": [
            "Do not wait for pending prompt HTTP response or step.ended. Snapshot already received complete tool args/call ids; continue only bounded same-step argument finalization, never wait for Step2.",
            "Use idle Keep-Alive control lane: permission reply decision=reject OR form cancel within0.25s of validated event, including scheduling+I/O; no lsof/reconnect on this path.",
            "Immediately POST /api/session/{id}/interrupt (<=0.10s) after rejection/cancellation; single-turn guard suppresses Step2 even if server races interrupt. On any control error fail-closed and group kill.",
            "If mapped complete native call available, return it exactly once to DSH with finish_reason=tool_calls; otherwise apply existing _incomplete_step_signal/unmapped-tool recovery under same cap3/retry budgets. Preserve raw model data/provenance.",
            "Final cleanup DELETE/close/kill/reap. Avoid duplicate interrupt if already succeeded; cancellation notifications never release Step2 barrier."
          ],
          "latency": "permission/form first reply<=0.25s; immediate subsequent interrupt<=0.10s is distinct control cost within model-execution phase. Final cleanup API aggregate<=0.20s; no new lsof. Only own session/PGID.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "crash_recovery": {
          "registry": "/tmp/opencode-zen-bridge-leases/; owner-UID directory mode0700, lease files0600, no symlinks (lstat + O_NOFOLLOW where supported), atomic replace and fsync before prompt admission. No name-wide scanning outside registry.",
          "lease_fields": [
            "schema_version",
            "owner_uid",
            "bridge_instance_id",
            "parent_pid",
            "parent_start_ts",
            "pid",
            "pgid",
            "port",
            "start_ts",
            "binary_realpath",
            "binary_marker=opencode serve",
            "temp_root",
            "temp_root_inode",
            "phase"
          ],
          "creation": "Write owned pre-spawn lease with temp root, phase=reserved before Popen; immediately after Popen atomically persist exact pid/pgid+ps start-time identity before READY/Auth/prompt. Parent bookkeeping thread per active lease watches the owned helper; parent-death enforcement itself is the paired helper holding the parent pipe. All included in thread/process budgets. Startup reaper required even if killed in persist gap. To cover spawn→lease update gap without unknown-child kill, spawn under lease-named stdlib helper which publishes child identity atomically and waits on parent pipe; EOF kills verified child PGID. Helper stdout/stderr not model data; new helper count boundedM and accounted below, not free model attempt. Implementation stays inside allowed server.py, stdlib -c helper only, no new script file.",
          "parent_death": "Helper owns parent pipe, checks EOF / os.getppid() and parent start identity; polling<=0.25s, no timeout killing live owner. On EOF closes lanes and TERM verified child PGID, grace0.50s then KILL and reap, remove only own recorded temp root. Helper process owns separate PGID and parent bridge retains helper identity. No secret in lease/helper argv. Helper exits on completed attempt, capped one per slot.",
          "startup_reaper": "Run before accepting bridge traffic (including disabled serve path): read only owner-UID valid leases. Live parent PID+matching parent_start_ts ->skip. If parent dead/mismatch, validate child ps pid,pgid,lstart,uid and command contains literal opencode serve --hostname 127.0.0.1 with exact recorded --port and binary path; os.getpgid(pid)==recorded pgid, start_ts matches. Recheck immediately before each signal and TERM→KILL. PID reuse, foreign uid, symlink, malformed/absent manifest or ambiguous identity ->no signal; redacted quarantine diagnostic, do not kill by name. Stored start_ts uses ps lstart identity plus monotonic instance nonce, not timestamp proximity alone.",
          "directory_cleanup": "Only recorded local temp_root with zen-serve-state- prefix, owner uid and recorded inode, no symlink, path resolved within tempfile.gettempdir; verify child/helper no longer active before rmtree and absence check. Do not delete another live attempt root. Missing ownership manifest ->do not discover/kill/remove by name. Dead-child orphan temp lease may be removed after ownership checks; retain error lease for diagnostics on failure.",
          "finally": "Normal finally closes pipe/helper, kills/reaps owned groups, removes temp root then lease. Never unlink manifest first or claim cleanup with ignore_errors. Startup reaper and helper idempotent under atomic lease ownership lock; races cannot signal reused PGID. All50 cancellation tests retained.",
          "tests": "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "fallback_decision_table": {
          "columns": [
            "phase",
            "event",
            "DELIVERED",
            "action",
            "ServeHealth_failure_increment",
            "UpstreamBreaker_failure_increment"
          ],
          "rows": [
            {
              "phase": "SPAWN/READY/CREATE/SUBSCRIBE",
              "event": "local spawn/ready/setup failure",
              "DELIVERED": "false",
              "action": "fallback_to_run",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "SPAWN→READY",
              "event": "ownership failure/timeout",
              "DELIVERED": "false",
              "action": "fallback_to_run",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "PROMPT_SENDING",
              "event": "first_event_timeout20s, no response headers and no valid execution SSE",
              "DELIVERED": "false",
              "action": "fallback_to_run",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "DELIVERED",
              "event": "first_event_timeout20s after headers, no valid execution SSE",
              "DELIVERED": "true",
              "action": "serve_retry",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "DELIVERED",
              "event": "first_token_timeout/stall with valid protocol and model silence",
              "DELIVERED": "true",
              "action": "serve_retry",
              "ServeHealth_failure_increment": 0,
              "UpstreamBreaker_failure_increment": 1
            },
            {
              "phase": "ANY",
              "event": "HTTP401/403 or permission/form/capability-security failure",
              "DELIVERED": "any",
              "action": "fail_closed",
              "ServeHealth_failure_increment": 0,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "ANY",
              "event": "HTTP400/404/422 invalid request",
              "DELIVERED": "any",
              "action": "fail_closed",
              "ServeHealth_failure_increment": 0,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "PRE_PROMPT",
              "event": "HTTP5xx local readiness/create/subscribe endpoint",
              "DELIVERED": "false",
              "action": "fallback_to_run",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "PROMPT_RESPONSE",
              "event": "HTTP429/provider5xx; headers received latch delivery",
              "DELIVERED": "true",
              "action": "serve_retry",
              "ServeHealth_failure_increment": 0,
              "UpstreamBreaker_failure_increment": 1
            },
            {
              "phase": "DELIVERED",
              "event": "invalid SSE/EOF without terminal proven protocol-only",
              "DELIVERED": "true",
              "action": "serve_retry",
              "ServeHealth_failure_increment": 1,
              "UpstreamBreaker_failure_increment": 0
            },
            {
              "phase": "ANY",
              "event": "client cancel/deadline/budget exhausted",
              "DELIVERED": "any",
              "action": "fail_closed",
              "ServeHealth_failure_increment": 0,
              "UpstreamBreaker_failure_increment": 0
            }
          ],
          "rules": "In auto fallback_to_run only before both barriers and before model/tool output, at most1 fallback after complete cleanup; force serve turns fallback_to_run into explicit failure. serve_retry means explicit admitted same-transport retry after cleanup/status, common cap3/retrytoken/FullJitter and remaining deadlines. If no budget ->fail_closed. Any response headers (including4xx/5xx) latch delivery before status classification. Upstream provider failure committed by existing per-request pending semantics once per cause, not per duplicate step/execution event. Security errors neutral to both health counters but fail-closed. lsof failure counter once per failed attempt;3 ->DEGRADED120s, next auto run without probes. Invalid protocol endpoint signature/security never bypassed by fallback."
        }
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как дать DSH видимость <1 s без изменения быстрых reasoning-ответов?",
      "choice": "Один SSE-writer с grace=0.30 s и отдельными status delta, завершающимися newline; модельные дельты не дополняются переводами строк.",
      "alternatives": [
        "Безусловный status t=0 — надёжен для Think, но ломает точное Simple greeting. и добавляет синтетику в быстрый ответ.",
        "Пустой keepalive/HTTP comment — не включает blockIsVisible и не обновляет collapsed preview (F-36/37).",
        "Вставлять newline в каждую model delta — превью чаще, но нарушает AC-006 и журнал."
      ],
      "drivers": [
        "REQ-004",
        "REQ-005",
        "AC-005",
        "AC-006",
        "EVD-051"
      ],
      "consequences": [
        "Первый status появляется только на медленном старте. Реальные delta с естественными абзацами обновляют collapsed summary.",
        "Non-thinking/off запросы не получают искусственного thinking; проверяется отдельно.",
        "DSH хранит bridge statuses в reasoning; replay их игнорирует, как весь reasoning_content."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-007",
        "EVD-036",
        "EVD-037",
        "EVD-038",
        "EVD-039",
        "EVD-051"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "timer_anchor": "t_sse_open — flush первого role chunk. FIRST_STATUS_DELAY_S=0.30; тик writer <=0.05..0.10 s. Background setup/adapter НЕ блокирует writer на gate.acquire, rate wait, connect, POST prompt или join. Ровно один поток пишет self.wfile; worker передаёт события через bounded queue. Никаких независимых Timer-writers в wfile.",
        "eligibility": "Только non-Google SSE с effective thinking/reasoning включённым (effort непустой; default high считается включённым). Явные off/none из _map_effort исключают synthetic reasoning даже при долгом запуске. Это явное сужение AC-005: оно относится к thinking-enabled DSH, а fast-answer/off сохраняет текущий contract. Модельные reasoning, если пришли от upstream, не выдумывать/не подменять.",
        "initial": "На t>=0.30 при отсутствии уже ОТПРАВЛЕННОЙ непустой real reasoning_content/content delta и незавершённом запросе отправить {reasoning_content:\"[мост] Подключение к модели…\\n\"} с реальным LF, flush. Пробелы и empty keepalive не считаются real progress. При доступной real delta в том же тике сначала обработать очередь, затем проверить grace: fast fake <50ms не получает prefix. Если real text пришёл раньше grace, initial status не нужен — ответ уже видим. Если real reasoning пришёл раньше grace, Think видим без synthetic prefix; отсутствие LF в быстром Simple greeting. не даёт права мутировать текст.",
        "lifecycle": "Before first real token eligible quiet request gets first status after grace0.30s, then [мост] Ожидание первого токена… with LF every5.0s. After useful model token, STALL_HEARTBEAT_INTERVAL_S=15.0: when upstream silent>=15.0s, MUST emit [мост] Ожидание продолжения… +LF and repeat every15.0s while stalled, including pause after very first token. Progress resets heartbeat schedule only from model clock; normal127ms delta never gets heartbeat. Synthetic statuses never reset first-event/first-token/stall watchdog clocks or had_output/usage. Single writer, leading LF separator synthetic provenance.",
        "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
        "pure_reasoning": "Склейка model-origin delta равна upstream model bytes после унаследованной очистки известных interrupted artifacts; не добавлять LF для preview, пробелы и UTF-8 не переписывать. _strip_interrupted должен оставаться chunk-boundary-safe: распознанный interrupted marker удерживается/удаляется инкрементально, partial prefix не протекает; обычный текст не нормализуется. В тестах удалять synthetic delta по provenance/expected list, а не слепо вырезать любую модельную строку [мост]. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
        "regression": "test_interrupted_artifact_removed_from_reasoning_stream: быстрая последовательность marker + Simple greeting. -> exactly Simple greeting., один run, zero status. В JSON тоже exactly. Slow FakeServe: first status <=1.0 s при заблокированном upstream; visible(text.strip) true, latestCompletedParagraphFirstLine получает завершённый LF. Natural reasoning LF обновляет collapsed row, bytes неизменны.",
        "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt. Остаточный межпровайдерский replay в DSH при ручной смене модели описан RISK-011; current bridge ignore не доказывает безопасность чужого provider.",
        "status_separator": "Перед любой synthetic [мост] delta, если ранее выданный модельный reasoning chunk не оканчивался LF и текущая видимая строка не завершена, prefix=\"\n\"; результат \"\n[мост] ...\n\". Весь prefix/status/trailing LF имеет synthetic provenance, отдельно от immutable model deltas. Если LF уже есть или модельного reasoning ещё не было, status начинается \"[мост]\" без добавочного LF. Единственный writer отслеживает line boundary; быстрый Simple greeting. до grace вообще не вызывает status helper. Фильтрация synthetic по provenance сохраняет AC-006 байт-в-байт и модельную строку, буквально начинающуюся [мост].",
        "STALL_HEARTBEAT_INTERVAL_S": 15.0
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как ограничить тишину, быстро отменить запрос и не оставить дочерние процессы?",
      "choice": "Единый monotonic supervisor обоих транспортов с разными clocks first-event/first-token/stall, отменой на всех ожиданиях и идемпотентным group cleanup.",
      "alternatives": [
        "Только TIMEOUT_S=1800 — сохраняет многоминутный инцидент RC-2.",
        "Watchdog stdout.read/15 s keepalive без socket-check — пропускает зависание после стартового события и поздно видит disconnect.",
        "Убивать только leader proc.kill — оставляет serve/grandchildren и забытые sockets."
      ],
      "drivers": [
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-016",
        "T-LIFE/v1"
      ],
      "consequences": [
        "Несколько инъектируемых clocks/state, строгий единый writer и owned worker.",
        "Ретраи после частичного вывода могут повторить reasoning; граница отмечается status.",
        "Новые timeout exits транзиентные, budgets/потолки не расширяются."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-014",
        "EVD-030",
        "EVD-033",
        "EVD-055",
        "EVD-061"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "thresholds": {
          "FIRST_EVENT_TIMEOUT_S": 20.0,
          "FIRST_TOKEN_TIMEOUT_S": 60.0,
          "STALL_TIMEOUT_S": 60.0,
          "env_prefix": "OPENCODE_ZEN_BRIDGE_",
          "validation": "положительное finite число; недопустимое -> ошибка старта, не бесконечный timeout"
        },
        "clocks": "Общий request deadline TIMEOUT_S=1800 якорится на request t0 и не сбрасывается. Local pre-spawn admission<=5.0s, SERVE_READY_TIMEOUT_S=3.0 и create+subscribe<=2.0 имеют отдельные часы до prompt. Для serve first_event20.0 и first_token60.0 начинаются в prompt_send_start перед первым байтом POST /prompt; first_event удовлетворяется только первым валидным SSE событием исполнения created session после этого момента (session.execution.started/session.step.started/session.reasoning.started, либо валидная текущая model delta). HTTP readiness/headers, server.connected/session.created, чужие/global updates, comments, bridge statuses не гасят first_event и не ставят first_event_ms. Headers POST устанавливают только delivered barrier. Для legacy сохраняется first valid run event/step_start от attempt_start перед startup. first_token — только non-whitespace model reasoning/text или полезный model tool intent; started/control/encrypted-only/reject notification не токен. stall стартует после first_token и обновляется полезными model delta/tool progress; empty ping/status не продлевают. first_event_ms и ttft_ms в O-EXIT относительно request t0, timeout ожидания serve first_event относительно prompt_send_start. При accepted prompt + zero session SSE ->first_event_timeout20s +cleanup<=1.2s, <=22s, не ожидание60s.",
        "disconnect": "На каждой итерации/ожидании <=0.25 s проверять cancel flag и client socket select + recv(MSG_PEEK|MSG_DONTWAIT): EOF/ECONNRESET -> client_gone без чтения данных и без переключения wfile в nonblocking. Реальная bounded empty OpenAI keepalive каждые <=2.0 s тишины страхует разрыв, который TCP ещё не сигнализировал; write deadline <=0.5 s, без write на отдельном потоке. Poll, status, write и cleanup не блокируют supervisor на 15/5 s. Суммарное обнаружение контролируемого FIN/RST <=5.0 s. Полное исчезновение сети без FIN нельзя доказать одним MSG_PEEK — bounded write/OS transport timeout и fault injection отдельно, не обещать физически невозможный мгновенный детект blackhole.",
        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent. После child kill/reap обязателен finally verified removal of owned zen-serve-state-* root (XDG_STATE_HOME/TMPDIR), preserve standard XDG_DATA_HOME; закрыть также daemon prompt delivery socket и join его в том же aggregate cleanup<=1.2s. Interrupt/delete только после ownership proof, никогда чужому listener. Fast API interrupt/delete each0.09s plus0.02 scheduling margin aggregate0.20; no lsof/reconnect. Normal helper pipe close/join and lease/temp deletion share remaining0.50s; crash_recovery covers death outside finally.",
        "retry": "Watchdog first_event/first_token/stall -> bounded common retry after full cleanup, _RequestAttempts/MAX_TOTAL_SPAWNS3/FAIL_RETRY_LIMIT/_RetryBudget/Full Jitter как ранее. Но serve-specific no-session-event/invalid_serve_event/EOF классифицируются _ServeHealth и НЕ _UpstreamBreaker; общие provider failures по-прежнему model breaker. При DELIVERED silent run fallback запрещён: retry текущего запроса остаётся явным на закреплённом транспорте, health TTL влияет только на последующие auto requests. Legacy watchdog сохраняет provider semantics. client_gone/fatal4xx/auth/permission ->no retry/fallback. HALF_OPEN owner token жив до завершения/cleanup, cooldown не допускает второй probe; neutral transport failure/cancel освобождает probe без fake provider success/failure. Slot один на запрос, release once; cancel-aware waits<=.25s; Full Jitter capped remaining. Decision table AD-001.fallback_decision_table is authoritative for phases/counter effects, including first_event before/after headers.",
        "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки. HTTP readiness НЕ first_event_ms: поле null до valid SSE execution current session после prompt_send_start. transport_history фиксирует отказ serve/TTL run или probe без secrets и phantom Popen; отдельный reason для protocol/model/security. early HTTP headers не ставят ни first_event_ms, ни ttft_ms."
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как сохранить инструменты/recovery на мелких дельтах и исправить baseline без ослабления защиты?",
      "choice": "Переиспользовать инкрементальный ToolCallParser и существующий recovery, обеспечить canonical native payload; исправить только несовместимые тестовые ожидания и изоляцию.",
      "alternatives": [
        "Копить всё до ended — легче parser/recovery, но вновь ломает realtime RC-1.",
        "Новый regex-parser на каждом delta — теряет разрезанные теги/JSON/UTF-8 и дублирует контракт.",
        "Поднять MAX_TOTAL_SPAWNS до 4 или отключить RetryBudget — скрывает baseline mismatch и нарушает REQ-009."
      ],
      "drivers": [
        "REQ-010",
        "REQ-011",
        "REQ-017",
        "AC-015",
        "AC-016",
        "F-47/F-48/F-49"
      ],
      "consequences": [
        "Минимальное изменение тестов без изменения production limits.",
        "Parser history/open block требует bounded memory; overflow — явный отказ, не silent drop.",
        "Перенос interrupted/step-failure проверок на fake v2 снижает риск transport-specific regressions."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-006",
        "EVD-043",
        "EVD-045",
        "EVD-047",
        "EVD-048",
        "EVD-049",
        "EVD-051",
        "EVD-057"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "parser": "Каждый session.text.delta -> тот же parser.feed без промежуточного whole-step buffer. Outside genuine tool blocks удерживается только pending opener prefix <=max(len(<tool_call>),len(<tool_invoke>))-1=12 chars плюс нужный существующему code-context lookahead; open block удерживается до валидного close, JSON close внутри строки не закрывает блок. Genuine/unparsed/incomplete tool tags не попадают в delta.content: callbacks через _strip_broken_tool_blocks и chunk-safe finish; существующие намеренно цитированные теги в Markdown остаются документационным текстом по текущим parser fixtures (не выполнять их). Инвариант по всем split points и single-character chunks. Open-block/total-output/frame bounds проверяются отдельно, overflow -> explicit error+cleanup.",
        "step": "Accumulated raw text/reasoning/native + step.ended tokens -> _is_incomplete_tool_step/_incomplete_step_signal и _is_transient_stream_error. При step.ended с готовым вызовом немедленно завершить upstream, finish_reason=tool_calls; не пропускать SYNTHETIC Continue. Error до первого model output допускает bounded recovery upstream как legacy; поздняя transient error прерывает attempt, fatal 400/401/403/404/422 без retry. Bridge status не изменяет attempt_output/first_token/had_error. _strip_interrupted и _strip_broken_tool_blocks работают независимо от границ delta. Native called.data.input absent: input.ended.data.text parsed once as complete JSON supplies tool arguments even streaming→failed. permission reject/form cancel latch single-turn barrier BEFORE control; immediately interrupt and return mapped tools or existing recovery, never Step2 output.",
        "baseline_tests": "В TestStepInterruptionLive.setUp заменить self.httpd.resilience на новый _Resilience (либо новый _RetryBudget с инъектируемыми часами + reset breaker/limiter), только когда прошлый request завершён, тесты класса последовательны. Ничего не сбрасывать в prod. В двух unmapped_retries_do_not_exhaust_incomplete_budget_{json,stream} оставить текущую fixture: первые 2 попытки unmapped, третья status/promise, 4-я запрещена. Ожидать runs==3, отсутствие tool_calls, finish_reason=stop, status/prelude ровно один раз; не ждать job_output/bash с несуществующего 4-го spawn. Добавить отдельный reachable<=3 сценарий unmapped -> incomplete -> calls и/или unit-oracle независимости счётчиков. Test_unmapped_then_error_stops_proc_json ожидает 2 и не зависит от предыдущих токенов бюджета. Все 17 legacy modules плюс новые tests green; production MAX_TOTAL_SPAWNS=3 не меняется.",
        "red_green": "Сначала dedicated tests на текущем коде: реальный socket read до release upstream Event, slow initial status, watchdog/cleanup и native delta split. Зафиксировать red (не import error), после Stage 3 green в VER-005 и полном VER-001/002. Stage 2 тестовый код не пишет и зелёное выполнение этой будущей поверхности не заявляет. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN."
      }
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "performance",
      "source": "DSH client",
      "stimulus": "upstream выпускает каждые150ms 10 reasoning delta и держит stream open",
      "environment": "здоровый FakeServe/локальный socket",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "writer flush до upstream terminal",
      "response_measure": "10 чанков получены до release Event; interarrival<500ms; bridge delay<=250ms",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-002",
      "quality": "usability",
      "source": "DSH thinking-enabled client",
      "stimulus": "cold start молчит/ждёт gate",
      "environment": "медленный upstream",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "grace status с LF, потом lifecycle status",
      "response_measure": "first visible<=1.0s, grace=.30s, без статусов на fast fake и off",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-003",
      "quality": "compatibility",
      "source": "legacy fake CLI",
      "stimulus": "fake script игнорирует argv и блокируется на stdin.read",
      "environment": "auto с кодовым default=false; runtime dynamic_config.json=true после H7/H3/H6 + native eligibility; explicit env disabled/run/disable-file/TTL ->run",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "один run без serve probe, reasoning exact Simple greeting.",
      "response_measure": "all17 modules green; runs==1, no synthetic prefix для fast fixture",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "upstream",
      "stimulus": "no event/no token/stall",
      "environment": "управляемые clocks/Events и hard silence",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "watchdog classification+bounded retry",
      "response_measure": "20/60/60 config, scaled tests, timeout+2s cleanup и spawns<=3",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-005",
      "quality": "reliability",
      "source": "DSH Stop/FIN",
      "stimulus": "отключение при gate/read/prompt/дельтах",
      "environment": "активные children/grandchildren",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "cancel->close->killpg->reap",
      "response_measure": "detect<=5s, orphan-free<=7s, slots/readers/sockets0",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-006",
      "quality": "security",
      "source": "модель/враждебный upstream",
      "stimulus": "native tools пытаются писать файл или запросить allow",
      "environment": "serve loopback с listener owner proof, default ask_reject или explicit deny",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "никогда allow, native event -> DSH tool tuple",
      "response_measure": "fake permission requests reject; false flag no secret allocation; live H6 отдельно",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-007",
      "quality": "operability",
      "source": "оператор",
      "stimulus": "любая terminal/early exit/успешный retry",
      "environment": "SSE или JSON, valid/malformed request",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "одна O-EXIT/v1 строка без secrets",
      "response_measure": "transport/first_event_ms/ttft_ms/exit_reason присутствуют; null не подделывается0",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-008",
      "quality": "testability",
      "source": "clean-room verifier",
      "stimulus": "clone не содержит ~/.dsh и новый transport fake",
      "environment": "Python>=3.11 stdlib tests",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "каждый VER полностью воспроизводим",
      "response_measure": "VER001..005 exit0 после Stage3, без owner home и Zen calls",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-004",
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-009",
      "quality": "cost",
      "source": "6 parallel requests",
      "stimulus": "103KB prompt и fragmented output",
      "environment": "design envelope single-process",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "resource manager bounds and overload",
      "response_measure": "Design:1*256+6*192=1408<=1638.4 MiB. H3 измеряет parent+6*child actual RSS и отсутствие database is locked на103KB×6×3; без H3 runtime PASS отсутствует.",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "Handler._stream_sse / Handler._serve_json",
      "responsibility": "OpenAI framing/один SSE writer; display-status только stream; _serve_json сохраняет model output без synthetic status",
      "allowed_dependencies": [
        "common canonical source",
        "pure tool/recovery helpers",
        "per-Server resource manager"
      ],
      "forbidden_dependencies": [
        "DSH bundle/config writes",
        "raw serve events в public ответе",
        "новые Google behavior"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-002",
      "component": "managed serve/run source + per-Server resource manager",
      "responsibility": "Transport selection, listener PID/PGID proof до Auth/prompt, fresh _serve_env/proxy и OPENCODE_DB=:memory:, standard read-only auth data and owned state/temp dirs, bounded HTTP/SSE/delivery leases, canonical wire adapter и cleanup",
      "allowed_dependencies": [
        "stdlib http.client/socket/subprocess/queue/threading/secrets",
        "_run_env/_RequestAttempts/_StartupGate",
        "pure event adapter"
      ],
      "forbidden_dependencies": [
        "wfile/client content writes",
        "внешние Python dependencies",
        "shared daemon/общий opencode config/db writes"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-003",
      "component": "ToolCallParser / recovery / normalize boundary",
      "responsibility": "Чистое инкрементальное преобразование text/native/events и interruption-safe accumulated reasoning",
      "allowed_dependencies": [
        "compiled regex/stdlib json",
        "tools клиента и primitive event payload"
      ],
      "forbidden_dependencies": [
        "network/process access",
        "global retry resets",
        "модификация model bytes для UI"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-004",
      "component": "_Resilience/_RequestAttempts",
      "responsibility": "Общий process bulkhead/rate/retry budget/model breaker; отдельно _ServeHealth для protocol-specific failures, per-request cap/deadline и prompt delivered barrier",
      "allowed_dependencies": [
        "injected monotonic/RNG",
        "locks"
      ],
      "forbidden_dependencies": [
        "new independent transport retry budget",
        "production budget reset between requests",
        "cross-provider fallback"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "bridge SSE presentation",
      "consumer": "DSH OpenAI completion reader",
      "change": "Grace=.30s synthetic [мост] status delta с LF для thinking-enabled slow/retry lifecycle; fast/off/JSON не получают prefix. Разрешено текущим Brief AD-002 и REQ-004/005. Mandatory eligible stall heartbeat threshold=interval15.0s even after first token; pre-token heartbeat5.0s; reasoning provenance and leading LF unchanged.",
      "compatibility": "OpenAI chunk shape/finish/usage unchanged; no unconditional t0 status; user fast exact reasoning equality preserved. REQ004 scoped to thinking-enabled, real content раньше grace уже видим.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "transport supervisor",
      "consumer": "OpenAI caller and O-EXIT logs",
      "change": "Конечные first_event/first_token/stall deadlines и fast cancellation с error той же формы; telemetry fields и exit reasons по REQ006..009/016. Для нового enabled serve path byte-bound explicit overflow, без silent loss.",
      "compatibility": "Endpoints/status/error schema и Google path unchanged; многоминутная тишина намеренно прекращается; kill-switch отключает новый serve, watchdog/status для legacy остаются исправлением RC2/RC3.",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "context",
      "question": "Кто общается с мостом и какая граница остаётся внешней?",
      "artifact_ref": "architecture/architecture-packet.json#scope + boundaries BND-001; F-35"
    },
    {
      "id": "VIEW-002",
      "type": "container",
      "question": "Какие processes/sockets являются изолированным failure domain?",
      "artifact_ref": "architecture/architecture-packet.json#AD-001.details.spawn/session_flow + high_load_envelope.operational_profile"
    },
    {
      "id": "VIEW-003",
      "type": "dynamic",
      "question": "Как status/watchdog продолжают работать во время setup/retry/молчания?",
      "artifact_ref": "architecture/architecture-packet.json#AD-002/003.details + resilience_gates.dependency_failure_matrix"
    },
    {
      "id": "VIEW-004",
      "type": "dfd",
      "question": "Где проходят auth/secret/tool-action trust boundaries?",
      "artifact_ref": "architecture/architecture-packet.json#threat_model + AD-001.details.tool_policy/fallback_barrier"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "deny удаляет tool schema, Zen403 или ask непреднамеренно исполняет tool",
      "probability": "high",
      "impact": "high",
      "mitigation": "Default ask_reject в отдельном _serve_env поверх byte-identical _run_env; wire permission.asked ->decision=reject немедленно, never once/always/allow. Env deny поддержан без пересборки, без automatic policy fallback. 401/403/нет safe endpoint fail-closed; FakeServe обе policy, реальный H6 обязателен.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Proxy env не означает фактическую per-request clean IP ротацию через loopback georouter",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Сохранять per-spawn _next_standalone_proxy env через неизменный _run_env; AC-018 проверяет последовательность записей пула. baseURL=http://127.0.0.1:10830/v1 georouter обходит child HTTP_PROXY по NO_PROXY (F-15/F-27); новый child не доказывает новую Zen IP. Shared daemon не выбирать ради failure isolation, не ради недоказанной egress ротации; конфиг georouter вне scope.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "6 serve на sqlite2.27GB/192MiB оценке создают lock/memory spike",
      "probability": "medium",
      "impact": "high",
      "mitigation": "OPENCODE_DB=:memory:, standard XDG_DATA_HOME/auth preserved, owned state/temp finally+crash reaper; EVD-071 zero common DB opens. H3 actual parent+all6serve/pairedhelpers/lsof<=1638.4MiB and zero locks on103KB×6×3; real auth not proven by provider-free access. disable-file retained on FAIL, no slot/retry increases.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Fast fake probe увеличит run counter или блокируется stdin",
      "probability": "high",
      "impact": "high",
      "mitigation": "При отсутствующем runtime config default=false ->run для378baseline. При enabled auto shebang ->one run без subprocess probes. Force serve stdinDEVNULL, ready<=3.0s/cancel-aware; первый kill-switch/TTL guard обязателен. Executable cache path+mtime_ns+size; config cache mtime_ns+size, invalid/missing boolean ->false с redacted warning. Exact counter regressions сохранены.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Расщеплённые marker/tool/UTF8 или ended duplicate искажают reasoning/usage",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Canonical delta-only assembler, incremental scrubber, all split points, step-id dedup/native-call-id dedup; end barrier independent terminal.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Корректный early-error upstream сам восстанавливается, но bridge status пометит had_output",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Status provenance отдельно от model counters, no had_output/clock reset; exact legacy early_error tests + FakeServe variant.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Квота Zen/103KB TTFT/DSH rendering пока не проверены",
      "probability": "high",
      "impact": "high",
      "mitigation": "F23 observation может устареть; не утверждать текущую квоту, H0..H9 live acceptance после rollout. FakeSuite не заменяет UI/реальный egress.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "Полный lint/type gate красный до изменения",
      "probability": "high",
      "impact": "medium",
      "mitigation": "EVD-072: full legacy format violates frozen bytes. VER-004 new file full format, legacy changed ranges via git diff-U0; local bridge-cwd temporary import-root, no repo config mutation. CATALOG_SOURCE mutable-name correction and proc None guards resolve3 type errors. Existing E402 only import zen_catalog baseline handled per-file CLI ignore with exact-site check, no noqa. Both Any<=125,0 Any/new warnings policy and explicit nonAny budgets; commands pendingStage3.",
      "verification_ids": [
        "VER-004"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Prompt POST timeout уже после принятия способен удвоить generation при silent fallback",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Текущий brief RW-001 выбирает HTTP response headers / первый current-session execution event как delivered barrier, вместо R1 начала POST. До headers и без события ServeUnavailable может fallback после полного kill/reap старого PGID; remote generation могла уже начаться, exactly-once не обещать. После barrier silent run запрещён; только явный same-transport retry+status/cap, no builtin execution. Source disagreement записан в panel_resolution_choices.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "SIGTERM/leader exit оставляет descendant, старый cleanup ждёт15+5с",
      "probability": "high",
      "impact": "high",
      "mitigation": "Normal cleanup<=1.2s; SIGKILL/kickstart-k outside finally protected by parent-pipe helper + safe startup lease reaper. Persist child identity before prompt; validate owner/ps start-time/PGID/cmd/inode and foreign-process negative tests. H0/H9 actual orphan sweep NOT_RUN.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-011",
      "scenario": "Статусы [мост] сохраняются DSH и при ручном переключении модели могут попасть reasoning_content другого provider (F-33/F-38/F-39)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Принятый остаточный риск: current bridge игнорирует весь replay reasoning, но чужой provider этого не обязан делать. Короткие статусы только grace/реальное ожидание не чаще5s и один на retry, no secrets/prompt text. Не менять DSH/provider контракты; уменьшить объём синтетики. Fake replay проверяет только этот мост, cross-provider H4 наблюдение не заменяет гарантии.",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "RISK-012",
      "scenario": "Serve SSE/protocol деградация ошибочно открывает общий model breaker и блокирует рабочий run",
      "probability": "high",
      "impact": "high",
      "mitigation": "_ServeHealth threshold3/TTL120/one recovery probe для новых auto requests, protocol failure не _UpstreamBreaker. Current accepted prompt не переигрывать скрыто. Fake5requests + expiry/probe/version-change cases; настоящие provider429/5xx сохраняют model breaker.",
      "verification_ids": [
        "VER-005"
      ]
    }
  ],
  "threat_model": {
    "required": true,
    "assets": [
      "промпт и история владельца",
      "ключ моста, пароль serve и proxy credentials",
      "локальные файлы и процессы",
      "квота Zen и ресурсы станции"
    ],
    "trust_boundaries": [
      "DSH -> bridge OpenAI HTTP (auth без изменений)",
      "bridge -> одноразовый loopback serve Basic Auth",
      "serve -> georouter/Zen через унаследованный per-spawn env",
      "модель -> запрос инструмента: исполнение только в DSH"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Подмена локального serve listener/вывод случайного пароля в stdout",
        "mitigation": "Parent bind loopback0/getport/release-before-Popen explicit port/newPGID; до Auth/prompt lsof listener PID->os.getpgid==childPGID, bounded<=.25s внутри ready3s. Foreign listener/owner unavailable ->zero secret/prompt bytes, cleanup own child only, bounded new port retry/cap3. Пароль secrets env до spawn, stdout redact, no redirects/proxy. VER-005 deliberate port takeover negative test.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "Модель выдаёт builtin bash/write/edit, пока DSH думает, что это только предложение",
        "mitigation": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6. _run_env does NOT sanitize every branch; _serve_env must apply serve_env_sanitization to all3 branches. Mandatory form.created→cancel and reject/cancel→immediate interrupt single_turn_control; JSON args fallback input.ended.data.text when called absent; no second-step output. {\"trigger\": \"permission.asked on own session or form.created.data.form.sessionID on own session. Immediately latch step_closed/output barrier BEFORE sending any control reply; retain accumulated raw/tool arguments and suppress every later-step text/reasoning.\", \"order\": [\"Do not wait for pending prompt HTTP response or step.ended. Snapshot already received complete tool args/call ids; continue only bounded same-step argument finalization, never wait for Step2.\", \"Use idle Keep-Alive control lane: permission reply decision=reject OR form cancel within0.25s of validated event, including scheduling+I/O; no lsof/reconnect on this path.\", \"Immediately POST /api/session/{id}/interrupt (<=0.10s) after rejection/cancellation; single-turn guard suppresses Step2 even if server races interrupt. On any control error fail-closed and group kill.\", \"If mapped complete native call available, return it exactly once to DSH with finish_reason=tool_calls; otherwise apply existing _incomplete_step_signal/unmapped-tool recovery under same cap3/retry budgets. Preserve raw model data/provenance.\", \"Final cleanup DELETE/close/kill/reap. Avoid duplicate interrupt if already succeeded; cancellation notifications never release Step2 barrier.\"], \"latency\": \"permission/form first reply<=0.25s; immediate subsequent interrupt<=0.10s is distinct control cost within model-execution phase. Final cleanup API aggregate<=0.20s; no new lsof. Only own session/PGID.\", \"verification_ids\": [\"VER-005\"]}",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Unrestricted parent env утекает в serve или proxy creds в ошибку",
        "mitigation": "_run_env only standalone branch whitelists; opencode-go/static inherit parent env baseline. New _serve_env filters exact allowlist on ALL3 branches before generated password/DB/state values, preserving only required routing/catalog/proxy/auth paths. OPENCODE_ZEN_BRIDGE_* and arbitrary API_KEY/TOKEN/SECRET sentinels absent; config/log/lease redacted. See AD-001.serve_env_sanitization; VER-005 branch matrix. _run_env remains byte-identical.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "SSE из чужой session или reconnect replay приводит к чужому выводу/повтору инструмента",
        "mitigation": "Filter exact data.sessionID и own prompt-send generation boundary; session v2 не даёт executionID, не ожидать выдуманного поля. subscribe armed before prompt, no transparent reconnect/replay after delivered; event id + assistantMessageID step/call id dedup; no foreign/raw events in public stream.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-005",
        "scenario": "Отмена клиента/oversized frame держит процессы и позволяет resource exhaustion",
        "mitigation": "bounded byte queue/frame/output and slots/waiters, finite per-operation deadlines, own PGID forced cleanup, zero orphan tests; output overflow не дропается молча. Crash leases + parent-pipe helper + startup reaper with uid/pid/pgid/start_ts/command/inode verification; no foreign signals/name-wide cleanup.",
        "verification_ids": [
          "VER-005"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "Existing public endpoints/schema/Google unchanged; run fallback retained. OPENCODE_DB=:memory: и standard auth/models/config сохранены. Кодовый default=false и отсутствие runtime JSON в git гарантируют378baseline по run; native auto включается атомарным runtime true только на H7 после H3/H6, без start.sh/restart/new env.",
    "migration": "No product DB migration. serve child SQLite memory only; never read/write/migrate shared opencode.db/opencode-next.db. Owned zen-serve-state-* dirs and UID registry leases are transient control state removed normally/following crash-safe reaper. Standard XDG_DATA_HOME/auth.json kept read-only.",
    "rollout": "Все H0..H9 NOT_RUN, external a3 ACCEPT+panel proof и независимые VER gates обязательны; Architect не выполняет rollout. H0 BLOCKING до sync/restart: проверить текущий env не force serve/true, отсутствие production dynamic_config.json либо boolean false; при прежнем enabled состоянии атомарно записать false, проверить read-back; дополнительный disable-serve разрешён. Снять старые PID/start/lease identity. H4 sync/read-back server.py hash; H5 launchctl kickstart с config absent/false: сразу dark run без окна serve; startup reaper0 старых собственных serve/helper/temp roots, чужие процессы untouched. На отдельном кандидате test-local dynamic_config.json=true и отдельный disable-file path: provider-free info/active, H3 реальные6parallel RSS/FD+OPENCODE_DB=:memory:, H6 live permission/tool isolation, Stage3a/A затем3b/B. На production до H7 run. H7 ТОЛЬКО после PASS H3 и H6: при env auto без explicit false и закрытом TTL подготовить tempfile в ~/.dsh/bridges/opencode-zen-bridge/,0600, записать {\"REALTIME_SERVE_ENABLED\":true}, os.replace в dynamic_config.json; убедиться дополнительный disable-serve отсутствует. Следующий native auto запрос на :9883 использует serve без правки start.sh и без повторного рестарта LaunchAgent. H8 повторяет живые проверки рабочего чата, H9 проверяет runtime false/true и disable-file same PID, отдельно kickstart-k crash recovery. Никакой выдачи design/NOT_RUN за runtime PASS.",
    "rollback": "Runtime kill-switch без рестарта: атомарно tempfile+os.replace mode0600 записать {\"REALTIME_SERVE_ENABLED\":false} в ~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json; либо удалить файл (default=false), либо создать disable-serve. Следующий auto запрос run без serve probes/allocations. Цель selector overhead <1мс проверяется VER-005/H9; это не измеренная гарантия задержки файловой записи/планировщика. Существующий explicit env=true имеет заданный override приоритет: в таком диагностическом процессе использовать disable-file для безусловного runtime rollback; production H0/H7 требуют auto без override. Env false/no/off/0 или TRANSPORT=run также force run, но изменение env живого процесса требует restart. In-flight leases drain/cancel, DELIVERED prompt не повторяется на run. H9 проверяет same PID, transport_history и повторные/параллельные вызовы; kickstart-k отдельно с config false/absent и identity-verified owned reaper. Stage2 ничего не деплоит. Все H0..H9 NOT_RUN.",
    "feature_flag": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git.",
    "H3_rollout_gate": {
      "status": "NOT_RUN",
      "scenario": "6 parallel реальных рабочих prompt около103KB +7th overload,3повтора; изолированный candidate перед production sync и повтор на боевом после safety допуска",
      "memory_unit": "MiB",
      "memory_inequality": "actual_parent_RSS + sum(RSS_serve + RSS_paired_helper + RSS_lsof_peak over M=6) <=0.80*2048=1638.4MiB; combined design per-slot192MiB includes helpers, not192+helpers.",
      "database_gate": "OPENCODE_DB=:memory:,0 shared SQLite opens/writes (lsof + disk identity snapshot);0database is locked/SQLITE_BUSY across6parallel×3; valid opencode-go auth without false401 tested separately from provider-free readiness.",
      "other_evidence": "Реальные RSS/FD/CPU/TTFT каждого запроса, parent/child peaks, все owned temp dirs удалены, zero orphan PGID; design child192MiB не подставлять вместо замера Include lsof one per spawn, helper/watchdog PIDs,18 admitted handler threads (6active+12waiters), consistent12 drains, observed FD/thread peaks and transport diagnostics. /api/info+active provider-free first; measured ready120.7ms is baseline not guarantee.",
      "on_fail": "Rollout enable запрещён: runtime config остаётся absent/false (и дополнительный disable-file остаётся, если поставлен). Не повышать slots6/12/retrycap3 и не менять shared env/config/DB."
    },
    "H0_precondition": {
      "status": "NOT_RUN",
      "blocking": true,
      "ordered_steps": [
        "verify production TRANSPORT=auto and no explicit enabled env override",
        "verify dynamic_config.json absent or boolean REALTIME_SERVE_ENABLED=false; if enabled atomically write false0600 and read-back before sync/restart",
        "optional additional disable-serve; preserve recorded safety state",
        "capture old PID/start/leases",
        "H4 sync candidate bytes/read-back hash",
        "H5 kickstart-k in dark run; reaper0 previous own serve/helper/temp roots",
        "candidate H3 six parallel RSS/FD memoryDB and H6 permission/tool isolation PASS before H7",
        "H7 atomic tempfile+os.replace0600 runtime true; remove optional disable-file only at this enable gate; no start.sh change/restart"
      ],
      "owner": "rollout operator; not Architect"
    },
    "H9_crash_recovery_gate": {
      "status": "NOT_RUN",
      "scenario": "Same live bridge PID: atomic runtime config false ->run, true ->serve при native+healthy, file deletion ->run; disable-serve дополнительно always run. Подтвердить selector overhead<1мс фактом, не обещанием. Отдельно parent hard kill/kickstart-k с active serve и последующий startup reaper:0 собственных orphan serve/helper/temp roots, чужие PID/PGID untouched."
    }
  },
  "approval": {
    "status": "NOT_REQUIRED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": null,
    "rationale": "FU-007 закрыт без исключений из канона: кодовый дефолт REALTIME_SERVE_ENABLED переведён в false, а включение на :9883 выполняется через локальный runtime dynamic_config.json (stat mtime_ns кэш без рестарта и без правки start.sh) строго на шаге H7 после прохождения H3/H6. Все AD обратимы (two-way); status=APPROVED означает валидированный архитектурный пакет-кандидат для Архитектурного Совета a3 (r4), а не вердикт Совета."
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2 schema review NOT_REQUIRED, but downstream external Council a3/proof is mandatory orchestration gate; Architect writes no vote or ACCEPT. Previous a2 NEEDS_WORK history retained."
  },
  "open_questions": [
    {
      "id": "Q-001",
      "question": "OPEN08/09: Каковы measured RSS/CPU/SQLite contention/actual TTFT и proxy egress на103KB/6parallel?",
      "blocking": false,
      "disposition": "Не блокирует Stage2 contract; H1/H2/H3 блокируют runtime enabling до доказательства design budgets."
    },
    {
      "id": "Q-002",
      "question": "H6: совместимы ли с реальным Zen default ask_reject и optional env=deny при гарантированном builtin rejection?",
      "blocking": false,
      "disposition": "Default выбран, автопереключения нет. FakeServe обе policy не доказывает live H6; неизвестная safe capability fail-closed, до H6 боевой disable-file не снимать."
    },
    {
      "id": "Q-003",
      "class": "continuable",
      "decision_required_human": false,
      "question": "FU-007 закрыт compliant flag delta: кодовый default=false плюс локальный runtime dynamic_config.json; human waiver не нужен.",
      "owner": "owner/orchestrator",
      "blocks": "Нет блокера policy; H3/H6/H7 и независимый a3 review остаются обязательны.",
      "evidence_ids": [
        "EVD-074"
      ],
      "blocking": false,
      "source_id": "FU-007/a2",
      "status": "RESOLVED",
      "disposition": "По явной финализации architect-cycle-3b; runtime проверки NOT_RUN."
    }
  ],
  "protected_paths": [
    ".ai-team/",
    "analysis/zen-realtime-reasoning/"
  ],
  "materialization": [],
  "deferred": [
    "Живая приёмка H0..H9 и синхронизация ~/.dsh выполняются только rollout-этапом после clean-room verifier и downstream panel.",
    "OPEN-05/16: прямой Zen HTTP и другие CLI форматы не исследуются заново; текущая реализация использует подтверждённый v2 SSE.",
    "Измеренные CPU/RSS/FD и реальный proxy egress на 103 KB/6 parallel — обязательный rollout gate, не доказанный Stage 2 факт.",
    "ADR-0005: оформить docs/adr/0005-zen-serve-realtime-reasoning.md и обновить docs/adr/INDEX.md отдельной задачей вне замороженного handoff-architect.md §10. Текущий Read-Only Product Gate разрешает только3 run JSON, поэтому materialization=[] и ADR/product docs здесь не создаются."
  ],
  "verification_policy": {
    "surface_frozen": true,
    "verification_implementation_owner": "Stage 3 Coder пишет tests/test_realtime_reasoning.py; Stage L2 Verifier независимо запускает каждый VER с 0 failed; тесты не считаются выполненными Stage 2",
    "REQ-019_clean_room": "VER-005 проверяет digest/rollout-manifest helper на двух временных fake files внутри sandbox, не ~/.dsh. Реальная синхронизация REQ-019 проверяется только H0 после отдельного rollout; невозможно подтвердить факт deploy чистым unit-тестом.",
    "timing": "FakeClock/RNG и Event-oracles для invariants; socket arrival/CPU реальные измерения отдельными measured/heavy unittest TestCase внутри dedicated suite (stdlib-discover тоже исполняет их). Тест timing держит upstream Event закрытым до чтения 10 дельт, deadline<500ms для interarrival и<=250ms bridge overhead; timeout helper аварийно освобождает Event, чтобы assertion failure не зависала. Не подменять arrival resp.read().",
    "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency.",
    "wire_fixture": "Six frozen source-schema families, canonical digest serialization explicit; five original family literals retained and nested form family added, adversarial mutations independent adapter/FakeServe.",
    "strict_typing": "Decode wire JSON as object with isinstance narrowing/TypedDict; new code no Any/casts-to-Any/type-ignore. New test0diagnostics; new legacy ranges0reportAny/reportExplicitAny/reportUnusedCallResult. VER-004 uses isolated bridge cwd + ephemeral /tmp include/extraPaths, errorCount0all3, server Any<=125each and documented nonAny per-rule/total720, step194 (baseline564/162). Rename mutable internal CATALOG_SOURCE to lower-case across server references (no external HTTP key change); guard proc is not None at both returncode sites. No new module/config/dependency. Legacy format ranges only; all3 full lint with exact existing server-only E402 exception and no new E402."
  },
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "field_count": 46,
    "units": "SSoT §3.0: memory MiB; times s, CPU cores, rates req/s or conn/s, connections/descriptors/tokens; векторы d и s по канону.",
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
      "u_bg_worker": 0.02,
      "U_pod_sidecars": 0.25,
      "Mem_limit_per_pod": 2048,
      "Mem_rss_worker_max": 256,
      "Mem_shared_max": 1152,
      "RPS_peak": 0.2,
      "A_max": 3,
      "SLA_p99_s": 180.0,
      "N_entities_max": 64,
      "Limit_dep_share[d]": {
        "georouter": 80,
        "opencode_local_db": 10
      },
      "Limit_dep_rps[d]": {
        "opencode_spawn": 1.0
      },
      "W_fetchers[d]": {
        "opencode_spawn": 0
      },
      "J_init_s[d]": {
        "opencode_spawn": 12.0
      },
      "J_pod_s[d]": {
        "opencode_spawn": 12.0
      },
      "T_poll_s[d]": {
        "opencode_spawn": 15.0
      },
      "K_calls[d]": {
        "opencode_spawn": 0
      },
      "T_base_s[d]": {
        "opencode_spawn": 0.5
      },
      "T_cap_s[d]": {
        "opencode_spawn": 2.0
      },
      "Max_stale_age_s[c]": {
        "stateless_bridge": 0.0
      },
      "Min_healthy_ratio": 1.0,
      "B_retry_max": 6,
      "min_reserve_retry_rps": 0.05,
      "FD_worker": 128,
      "ulimit_n": 65536,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 3.6,
        "shared_snat": 1.8
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 30,
        "shared_snat": 12
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16384,
        "shared_snat": 16384
      },
      "T_hold_s(s)": {
        "node_ephemeral": 60.0,
        "shared_snat": 60.0
      },
      "SNAT_ips_count(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "HOTPATH_MODULES": [
        "bridges/opencode-zen-bridge/server.py"
      ]
    },
    "field_sources": {
      "P_steady": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_hpa_max": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxSurge_pct": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxSurge_abs": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxUnavailable_pct": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxUnavailable_abs": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_terminating_overlap": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_live": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_avail_min": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "W": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc_steady": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc_avail_min": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "CPU_limit_per_pod": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "κ_skew": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "u_bg_worker": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "U_pod_sidecars": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "Mem_limit_per_pod": "handoff-architect §7 design budget2048MiB, normalized per SSoT§3.0/RW-011; host limit not measured, H3 mandatory.",
      "Mem_rss_worker_max": "F-29 parent baseline22MiB; design bound256MiB; H3 actual_parent_RSS_max measured in MiB.",
      "Mem_shared_max": "1152MiB=6*192MiB COMBINED per-slot budget for serve+parent-pipe helper+transient lsof, no192MiB extra helper allowance. EVD-071156.8MiB serve idle leaves35.2MiB nominal per-slot headroom, NOT proof of loaded peak. H3 sums actual parent+serve+helper+lsof RSS and must satisfy<=1638.4MiB; design fields remain2048/256/1152MiB a1.",
      "RPS_peak": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "A_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "SLA_p99_s": "180s normal-mode design goal from analyst envelope; degraded first-token failure profile3*60+51.6=231.6s separate explicit acceptance, not guaranteed180s or universal generation limit. See operational_profile.p99_criteria; actual measurements NOT_RUN.",
      "N_entities_max": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "Limit_dep_share[d]": "F-26 georouter 80 direct slots; opencode_local_db=10 — design logical-child share из handoff, НЕ доказанный sqlite pool/max_connections; H3 проверяет фактическую contention и ≤6 children.",
      "Limit_dep_rps[d]": "F-11/server.py:309-314 — локально установленный spawn limiter 1/s, НЕ квота Zen/SQLite vendor. Запросы не являются pollers; не подставлять это число как upstream RPS quota.",
      "W_fetchers[d]": "F-12/F-14 и граф BND: новый source per-request, Control Plane/Snapshot poller не добавляется; 0 фоновых fetchers и 0 background calls. SSE keepalive не backend polling.",
      "J_init_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "J_pod_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "T_poll_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "K_calls[d]": "F-12/F-14 и граф BND: новый source per-request, Control Plane/Snapshot poller не добавляется; 0 фоновых fetchers и 0 background calls. SSE keepalive не backend polling.",
      "T_base_s[d]": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "T_cap_s[d]": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "Max_stale_age_s[c]": "Stateless transport; новый Snapshot/secret TTL cache не создаётся. process-local capability boolean по stat не хранит secrets/model output и инвалидируется при mtime/size смене.",
      "Min_healthy_ratio": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "B_retry_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "min_reserve_retry_rps": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "FD_worker": "Design parent ceiling128 vs recalculated108=36baseline+18admittedclients+18lanes+12drains+6reserve+6lsof pipes+6watchdogpipe+6lease handles; helper/serve/lsof processFD separate. H3 verify per-process limits and344aggregate estimate.",
      "ulimit_n": "F-29 launchctl soft maxfiles=65536; не переносить значение вчерашнего reference packet=4096 как текущий факт.",
      "λ_new_conn_per_pod(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
      "C_active_in_scope(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
      "N_pods_in_scope(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "Port_range_size(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "T_hold_s(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "SNAT_ips_count(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "HOTPATH_MODULES": "HOTPATH_MODULES: текущий server.py, read-only symbol graph BND-001..004; новые проектные modules не нужны."
    },
    "operational_profile": {
      "model_event_rate_per_s_per_active": 10,
      "active_child_max": 6,
      "code_default_max_concurrent": 2,
      "deployed_max_concurrent": 6,
      "max_waiters_effective": "min(configured MAX_SLOT_WAITERS, 2*effective MAX_CONCURRENT) в общей _SlotBulkhead admission; code-default2/4, deploy6/12. Deployment6/12 unchanged, configured waiters variable не повышать.",
      "server_resource_manager": "один per-Server owner для bounded process/socket leases, после старта процесса, без parent live sockets before child exec",
      "threads_per_worker_upper_bound": 55,
      "thread_accounting": "Parent bound55=1server/accept loop +18 admitted handlers(6active+12waiting) +6supervisors/setup tasks +6SSE readers +6prompt delivery workers +12separate stdout/stderr drains +6parent-watchdog bookkeeping threads. No additional per-request gate timers; cancellation polls shared supervisors. lsof runs synchronously bounded0.35s on setup/supervisor,6 concurrent helpers max, no extra parent thread. Reaper startup-only (no overlap request workers). Parent-pipe helper at most6 single-thread processes, separately counted, not parent threads; at most6 actual serve +6 helper +6 transient lsof processes (18aux at peak). Rejected ingress handlers beyond admission exist transiently in ThreadingHTTPServer:55 is admitted-workload bound, not arbitrary SYN-flood guarantee; H3 measure transient rejection peaks, do not claim unlimited HTTP thread defense.",
      "stdout_queue_max_events": 4096,
      "new_transport_queue_max_bytes": 1048576,
      "new_transport_max_sse_frame_bytes": 1048576,
      "new_transport_accumulated_output_budget_bytes": 8388608,
      "byte_limits_policy": "Только новый enabled transport, суммарный parent queue/raw/parser/dedup/visible output budget на request контролируется; превышение -> прежняя error shape + explicit output_overflow и cleanup, не молчаливое drop. Не вводить новый запрет на размер accepted prompt и не менять legacy limits. При нагрузке/длинном reasoning H3 измерить Python overhead и CPU.",
      "first_status_delay_s": 0.3,
      "status_heartbeat_s": 5.0,
      "first_event_timeout_s": 20,
      "first_token_timeout_s": 60,
      "stall_timeout_s": 60,
      "client_detect_s": 5,
      "client_probe_interval_s": 0.25,
      "client_keepalive_s": 2,
      "client_write_timeout_s": 0.5,
      "cleanup_budget_s": 1.2,
      "ready_budget_s": 3.0,
      "session_setup_budget_s": 2.0,
      "slot_wait_s": 15,
      "spawn_rate_per_s": 1,
      "spawn_burst": 1,
      "total_deadline_s": 1800,
      "estimate_status": "Design targets only, including combined per-slot192MiB child+helper+lsof. EVD-071 idle156.8MiB is not6parallel peak. Normal p99<=180s goal; degraded3x60+51.6=231.6s distinct profile, live H3 NOT_RUN.",
      "pre_spawn_admission_budget_s": 5.0,
      "admission_policy": "_StartupGate + _SpawnRateLimiter делят один<=5.0s deadline на attempt; никакой суммы независимых5+5. Spawn token hard, gate wait fail-open только в остатке.",
      "session_setup_scope": "POST /api/session + GET /api/event subscription armed<=2.0s до prompt; POST /prompt worker waits по first_event20/first_token60,total1800 и concurrent SSE, не по session_setup.",
      "first_event_anchor": "serve prompt_send_start; first valid current-session execution SSE only; HTTPready/headers/control ignored; O-EXIT first_event_ms measured from request t0",
      "data_isolation": "OPENCODE_DB=:memory:; preserve standard XDG_DATA_HOME/auth; owned zen-serve-state-* state/tmp with finally+crash reaper.",
      "serve_health": {
        "threshold": 3,
        "ttl_s": 120.0,
        "scope": "per Server/binary key, new auto requests; no model breaker protocol failures"
      },
      "http_sockets_per_serve_max": 3,
      "fd_accounting": {
        "parent_baseline": 36,
        "admitted_client_sockets": 18,
        "serve_http_lanes": 18,
        "stdout_stderr_drains": 12,
        "reserved_port_sockets": 6,
        "lsof_capture_pipes": 6,
        "parent_watchdog_pipes": 6,
        "open_lease_files": 6,
        "parent_upper_bound": 108,
        "configured_envelope": 128,
        "aggregate_estimate": "parent128 +6serve*20 +6helper*8 +6lsof*8=344 descriptors system-wide design, per-process parent<=128, not claim aggregate<256. H3 actual per-process FD and system peaks."
      },
      "process_accounting": "6serve slots plus <=6parent-pipe stdlib helpers plus<=6lsof (one per active setup, no extra token-free model spawn). Each serve attempt consumes one _RequestAttempts token/spawn-limiter admission and may create exactly one paired helper; all<=3 model attempts/request. Helper/lsof separate owned bounded aux PIDs, never count them as model generations or ignore resource overhead. No lsof on control hot path.",
      "p99_criteria": {
        "status": "DESIGN_TARGET_NOT_MEASURED",
        "normal": "At declared0.2req/s, admitted6active/12waiters, healthy single attempt: empirical end-to-end completion p99<=180.0s including slot/admission/setup/cleanup; H1/H2/H3 record sample count and nearest-rank p99, never infer p99 from3samples.",
        "degraded": "Bounded synthetic failure-to-first-token profile with three60s watchdog attempts: elapsed<=231.6s (=3*60+51.6 aux), not <=180.0s. Fault-injection batch>=100eligible requests reports nearest-rank p99<=231.6s and cap3; retry budget may stop earlier. First-event-only failure profile3*20+51.6=111.6s. Healthy actual generation+post-token stalls remain under total1800s,231.6 is not universal completion guarantee.",
        "rollout": "Both normal p99 target and degraded-profile budget must be measured independently; no runtime SLA claim from arithmetic. If normal p99>180 or degraded synthetic p99>231.6, keep disabled and return evidence, do not increase caps/timeouts."
      },
      "stall_heartbeat_interval_s": 15.0
    },
    "memory_closure_check": {
      "status": "PASS",
      "unit": "MiB",
      "lhs_mib": 1408,
      "rhs_mib": 1638.4,
      "substitution": "W*Mem_rss_worker_max+Mem_shared_max=1*256+1152=1408 <=0.80*2048=1638.4 MiB",
      "evidence_level": "design estimate only; NOT measured runtime PASS",
      "runtime_gate": "H3 sum actual_parent_RSS + RSS(all6serve + allpaired helper + lsof peaks) <=1638.4MiB; combined slot budget192MiB, no hidden helper memory.103KB×6×3, zero sharedDB opens/locks, actual FD/CPU and temp cleanup. Idle156.8MiB not loaded PASS."
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
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "substitution": "46 exact keys/sources/field_units SSoT§3.0; memory inMiB:1*256+1152=1408<=0.80*2048=1638.4. N/A сохраняет actual diff и transitive graph; runtime H3 NOT_RUN.",
        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist. Assert memory units exact MiB and actual H3 inequalities separately; bytes вместо MiB FAIL. Recompute parent55admitted threads/108FD<=128, combined helper memory, normal p99 goal180 vs degraded3x60+51.6=231.6 distinct profile. Full-thread peak under arbitrary flood is not bounded by slot count alone.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "Bridge process1,6 exclusive serve leases,G_reload1; georouter6<=.60*80=48. Logical opencode_local_db6<=.60*10=6 is accounting not vendor pool. OPENCODE_DB=:memory: means0shared SQLite files; auth preserved at standard data dir. Helpers<=6/lsof<=6 bounded separately; combined child/helper/lsof estimate1152MiB and parent256 gives1408<=1638.4MiB, runtime PASS only H3 full sum and0locks.",
        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling. Fake XDG dirs unique per spawn and deleted on all exits; H3 real peaks/zero locks обязательны до enable, retry не маскирует lock failure; runtime_status NOT_RUN. Unique memory DB / state roots + standard read-only auth paths all3env branches; include helpers in H3 sum.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "runtime_status": "NOT_RUN_H3_REQUIRED"
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Per-process manager: M=effective MAX_CONCURRENT (default2/deploy6), max_waiters<=2M (default clamp4/deploy12), wait<=15s; fixed max3 HTTP sockets/active serve (reusable control+event+prompt delivery), queue<=4096 events И <=1MiB, frame<=1MiB; no Redis SQL connection pool added. Общий ingress _SlotBulkhead обязан применять этот effective bound и при run, иначе default M=2/waiters12 нарушил бы 2M; не вводить вторую неучтённую очередь перед manager.",
        "oracle": "Блокировать M+2M leases, следующий fast-fail без Popen/connect, сокетов<=3M, queue byte-overflow explicit error; inspect configured ceilings. Нельзя снижать общий production slot count или повышать max_waiters.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "Один server-owned manager/factory и _Resilience на процесс (100 запросов -> тот же id). Именованные leases для ephemeral per-attempt endpoints получают отдельные bounded control/SSE sockets только после child start. Это не reusable global-remote pool и не создание неучтённого клиента в Handler; требование A1 исключает shared daemon endpoint. Нет сокетов моста до child exec, close_fds; close manager в shutdown/release каждого lease.",
        "oracle": "Factory created_clients==1 per Server, pre-spawn transport sockets=0, session leases<=M; 100 calls same manager id; shutdown closes all leases/sockets/child groups. Отдельные socket endpoints не маскировать как singleton connection.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "Любой timeout/cancel на slot/gate/ready/prompt/read/write вызывает общий finally; cleanup idempotent; counters waiters/in_use/children/sockets возвращаются0; disconnect не запускает retry.",
        "oracle": "50 controlled cancel cycles в каждой фазе через Events, cancel-before/after lease acquisition, counters==0; не считать daemon=True механизмом cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "ParentFD estimate108<=envelope128<=.70*65536=45875.2. Systemwide parent128+6*serve20+6*helper8+6*lsof8=344design (not<256); each process independent ulimit check.3HTTP lanes/serve retained, lsof capture1pipe/helper<=6. Nodeports3.6*60+30=246<=8192; SNAT1.8*60+12=120<=8192.0extra network from lsof/helpers. H3 actualFD/thread/ports required.",
        "oracle": "Recompute both scope inequalities, count control connection creation/reuse (50 operations on one owned serve lease ->1 keepalive control TCP), readiness≤3 probes; leak counters FD/start/end stable; H3 измеряет реальные FD/egress. Assert one lsof per successful spawn including permission/form/interrupt/DELETE;3forced lsof timeouts count3ServeHealth->DEGRADED, next auto request no serve/helper/lsof Popen. No additional model tokens charged for lsof, but helper process ceilings enforced.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Snapshot/config startup/poll path absent: W_fetchers=0,K_calls=0 => batch K×(λ+4sqrtλ+4)=0<=.5×1=.5 и R_poll=0<=.2×1=.2. 1/s field — self-configured request spawn rate, НЕ неизвестная квота dependency; запрещено объявлять gate PASS через фиктивную внешнюю RPS. Request cold-start отдельно ограничен combined gate+token admission<=5.0s (gate hold<=12s, не additive wait) + token bucket1/s burst1 для КАЖДОГО child включая fallback.",
        "oracle": "AST/transitive no backend poller; zero background I/O при idle; FakeClock spawn bucket max B+r*T; ≥6 parallel requests не делают 6 Popen одновременно. Startup gate release first validated event/own EOF/max hold, cancellation-safe.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Full Jitter base=.5, cap=2 через injected RNG, cooldown10×U(.8,1.2). Bridge worker fork отсутствует; child exec не наследует RNG/secret state, serve password=secrets. При введении fork/poller обязательны post-fork SystemRandom/reseed и periodic jitter.",
        "oracle": "RNG points0/.5/1 дают0,.5*cap,cap; CSPRNG mocked count per child; inspect no fork worker; не запускать новый deterministic random.Random с одинаковым seed в каждом retry.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "S-HERD-I3": {
        "status": "N/A",
        "substitution": "Новый transport не создаёт Snapshot/config polling, If-None-Match или mutable indexed snapshot; conditional304 не имеет операции применения.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Новый transport не создаёт Snapshot/config polling, If-None-Match или mutable indexed snapshot; conditional304 не имеет операции применения.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "S-HERD-I4": {
        "status": "N/A",
        "substitution": "Новый transport не создаёт TTL-backed network cache или singleflight; process capability stat-key boolean не network TTL и не хранит ответ/секрет.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Новый transport не создаёт TTL-backed network cache или singleflight; process capability stat-key boolean не network TTL и не хранит ответ/секрет.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "S-HERD-I5": {
        "status": "N/A",
        "substitution": "Не вводится Control Plane/Snapshot/SWR/readiness endpoint; публичный /health unchanged; auth password живёт ровно до cleanup, 401 fail-closed.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Не вводится Control Plane/Snapshot/SWR/readiness endpoint; публичный /health unchanged; auth password живёт ровно до cleanup, 401 fail-closed.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "N/A",
        "substitution": "Нет нового indexed routing Snapshot/selection по N_entities; canonical event dispatch по exact type O(1), bounded parser stream зависит от длины входа, не от N proxy nodes.",
        "oracle": "Dispatch-equivalence fixtures для всех event types, operation count независимо от N_entities. Absence Snapshot/routing graph и actual diff.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Нет нового indexed routing Snapshot/selection по N_entities; canonical event dispatch по exact type O(1), bounded parser stream зависит от длины входа, не от N proxy nodes.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "Regex compiled at import; нет per-delta json.loads правил/конфигов, model_validate/deepcopy/static label binding. json.loads одного входного SSE frame необходим для transport framing и не является forbidden config reload parse. Serve ask_reject/deny config merge один раз per attempt setup вне delta loop.",
        "oracle": "Спай на re._compile/config decoder/model_validate/typeadapter/deepcopy/static labels в delta loop ->0; wire decoder count==one per actual event, не full history; tool JSON parser exempt by input decoding purpose.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Первые guards: explicit env disabled/TRANSPORT=run ->legacy до stat/UUID/password/clock/queue/threads/probe. Disable-file O(1)/open sticky TTL ->run; force serve только после этих guards. Auto dynamic config stat O(1) cache(mtime_ns,size), unchanged без JSON parsing/reopen, missing/invalid/unreadable/nonbool default=false; enabled native only ->serve. Config reload bounded, selector overhead<1мс — будущий VER005/H9 oracle, не измеренный PASS. Legacy watchdog/status RC2/RC3 остаются; status thinking+SSE guard before format, bounded put_nowait, explicit overflow+cleanup.",
        "oracle": "VER-005 spy explicit0/run/disable-file ->0 serve alloc/password/probe/extra Popen; while same process create/remove file next request toggles transport. Queue overflow explicit cleanup; no disabled UUID/serialization. File stat O(1), no recursive IO.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "H-CPU-I4": {
        "status": "N/A",
        "substitution": "Мост ThreadingHTTPServer, нового async event loop/config reload Snapshot нет; parser/readers в owned worker, клиентский writer не блокируется setup I/O.",
        "oracle": "Actual diff/call graph no asyncio or snapshot reload path; server writer scheduling проверяется Event test.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Мост ThreadingHTTPServer, нового async event loop/config reload Snapshot нет; parser/readers в owned worker, клиентский writer не блокируется setup I/O.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "Inherited CPU estimates t_req=.02,t_attempt=.05; total=.17CPU-s, util=1×.2×.17/(1×1)+.02=.054<=.70; pod=.054+.25=.304<=.8×2=1.6; допускается Δt_feature<=.10 CPU-s/request =>Δcores=.2×.10=.02<=.05×(1×2)=.10. Event path up to60frames/s; никакого повторного full-history regex/JSON parse в delta loop. Дельта .10CPU-s — budget, не замер.",
        "oracle": "Fake workload CPU accounting/proportional operation count checks with deterministic sizes; measured/heavy scenario process_time профиль по50 controlled frames плюс H3 full length. FAIL budget -> нельзя включить serve, не объявлять estimate actual performance.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "15.0 + 3 * (5.0 + 3.0 + 2.0 + 1.2) + 3.0 = 51.6 s <= 0.30 * 180 = 54.0 s; headroom=2.4s. Slot15 один раз, combined pre-spawn admission5 на attempt, owner/ready3, create+subscribe2, cleanup1.2, суммарный backoff cap1+2=3. Prompt POST/generation под first_event20/first_token60/stall60 и total1800, не session_setup. Каждому I/O timeout=min(phase_remaining,request_remaining); cleanup финальный<=1.2 даже после request deadline. После deadline ни spawn/prompt/sleep.",
        "oracle": "FakeClock recompute51.6<=54 и headroom>=2.0; admission gate+limiter sum<=5.0, ready3/create+subscribe2/cleanup1.2, prompt POST не входит в2s; slow create timeout ->one budgeted run pre-header; headers received or session event ->zero silent run, Popen<=3. Deadline exhausted->zero further I/O. Никаких leftover gate5+spawn5/ready.5/setup.2. Owner proof0.35 inside ready3s, no lsof in cleanup. Control reconnect0.35 is explicit recovery inside execution budget, never urgent-reply/cleanup SLA; urgent failure kills instead. Normal p99 and degraded231.6s criteria separate.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "Per-request Popen<=3, shared RetryBudget6 +.20/request+.05/s; Nreq100,Tw500 -> retries<=floor(20+25)+6=51. Transport fallback расходует тот же retry token; local capability failure не breaker/provider failure, но не бесплатный новый spawn. Bulkhead M6 waiters12 или effective2/4; в production ничего не сбрасывать.",
        "oracle": "FakeClock 100 failing primary requests -><=51 retries; tokens>=0; no spawn4 при комбинации serve-unavailable/watchdog/native/incomplete; тесты isolated _Resilience не ослабляют runtime caps.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Model _UpstreamBreaker threshold5/cooldown10*U(.8,1.2), HALF_OPEN1 owner не освобождается по одному cooldown до terminal/cleanup; provider failures/успешное восстановление как прежде. Отдельный _ServeHealth threshold3/TTL120/one recovery probe для serve protocol-only failures; first_event_timeout без session execution и invalid_serve_event НЕ model breaker failure, subsequent auto->run. Accepted current prompt не получает silent run fallback. Auth/permission/security401/403 fail-closed, no policy switch; client cancel neutral. TTL/run skips не продлевают outage; native binary key change инвалидирует capability/health. Resource/retry/slot caps едины.",
        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret. Отдельно five serve-protocol failures forced mode ->model breaker closed, no .failure calls; auto third failure arms120s,next auto run, no silent replay current request; atTTL exactly1probe, success resets, failed protocol rearms120; provider5 failures still open model breaker. Parametrize AD-001 fallback_decision_table rows exactly, counters once/cause. preheader20s->budgeted run, afterheader20s->explicit serve_retry; HTTP401/403 neverfallback; local preprompt5xx transport vs promptprovider5xx model. lsof proof timeout3->TTLrun/modelbreaker0.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I4": {
        "status": "N/A",
        "substitution": "Bridge не выбирает V_eligible, tenant nodes/health/quarantine; _next_standalone_proxy round-robin env, georouter owns selection. Не добавляется Panic-Open или перескок Google/провайдера при serve failure.",
        "oracle": "AST graph/diff запрет proxy-node-health, tenant routing, cross-pool fallback; preserving _model_route and _run_env branch.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Bridge не выбирает V_eligible, tenant nodes/health/quarantine; _next_standalone_proxy round-robin env, georouter owns selection. Не добавляется Panic-Open или перескок Google/провайдера при serve failure.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "R-BULK-I5": {
        "status": "N/A",
        "substitution": "Bridge видит одну logical model dependency и не ведёт origin_health/node_health; georouter остаётся владельцем таких решений. Новый watchdog не карантинит ProxyRack entry на все origins.",
        "oracle": "Отсутствие quarantine/node health mutation по actual diff + graph; injected error не меняет configured provider/model/proxy list.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Bridge видит одну logical model dependency и не ведёт origin_health/node_health; georouter остаётся владельцем таких решений. Новый watchdog не карантинит ProxyRack entry на все origins.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Normal attempt owns childPGID,control/SSE/prompt lanes,12drains bound,helper pipe/process,session and memoryDB/state root; cleanup<=1.2s includes API.2/TERM.5/reap-join-temp-lease.5. SIGKILL bypasses finally: parent-pipe helper then startup lease reaper validates ownerUID,parent/childPID start_ts,PGID,cmd/binary/port and temp inode; no name-wide kill, no removal without manifest. Standard XDG_DATA_HOME never deleted.",
      "oracle": "VER-005 both original50cancellations and hard-parent-death→next-start reaper, killed parent before/after READY, failed helper, PID reuse/foreign UID/PGID/symlink/foreign dir negatives.0old owned serve/descendant/helper/temp roots;0active/waiter/socket/reader counts. H0/H9 actual kickstart-k NOT_RUN.",
      "verification_ids": [
        "VER-005"
      ]
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется. first_event_ms только valid current-session execution SSE после prompt, относительно request t0; HTTPready/POST headers не являются first_event. transport_history/reason раздельно protocol/model/security/TTL, no phantom spawns. REQ-016/AC-021 authorize listed fields; fallback reason in adjacent BRIDGE-TRANSPORT/v1 diagnostic if strict O-EXIT parser; never rename/remove existing keys/types. Always log transport=serve|run with redacted cause; /health unchanged.",
      "oracle": "VER-005 table all exits incl 400/401/404/503/circuit, overflow, error, abort, successful retry; deterministic fake clock, no secret reflection.",
      "verification_ids": [
        "VER-005"
      ]
    },
    "M_SEM_v1": {
      "status": "N/A",
      "reason": "Bridge не имеет tenant/pool node selection; direct Google dispatch и configured model/provider уже разделены, никакой cross-provider recovery.",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
        "current_git_diff_output": "",
        "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
          "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
        "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
      },
      "oracle": "VER-001/003 Google direct unchanged, VER-005 no cross-provider fallback/proxy selection mutation.",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "serve/readiness + session init",
        "path": "hot/aux",
        "timeout_budget": "Owner proof+GET /api/session/active aggregate ready<=3.0s (cache-miss schema внутри3); POST session+GET event armed<=2.0s; POST prompt excluded, concurrent SSE/watchdogs",
        "bulkhead": "manager leases<=M, control+SSE+prompt delivery<=3M sockets",
        "circuit_breaker": "_ServeHealth3/TTL120/probe1 for protocol; _UpstreamBreaker5 for provider; auth/permission fail-closed",
        "failure_mode_fallback": "Auto ServeUnavailable до POST prompt response headers и до current-session execution event ->cleanup+budgeted run. Headers OR event latch delivered; then no silent run.401/403/permission missing never fallback."
      },
      {
        "dependency_operation": "opencode model execution (serve or run)",
        "path": "hot",
        "timeout_budget": "Serve first-event20/first-token60 от prompt_send_start; stall60 от useful token; requestTIMEOUT1800 common. HTTP readiness отдельно<=3 и не гасит first_event.",
        "bulkhead": "_slots effectiveM, waiters<=2M, one child per slot",
        "circuit_breaker": "Provider _UpstreamBreaker5/jitter/HALF_OPEN1; serve-specific invalid/no-event ->_ServeHealth3/TTL120 only",
        "failure_mode_fallback": "Watchdog ->cleanup+same-transport explicit budgeted retry; accepted current request never silent run. Protocol degradation directs NEW auto requests to run; fatal4xx/security/cancel no retry."
      },
      {
        "dependency_operation": "_StartupGate/_SpawnRateLimiter",
        "path": "hot/aux",
        "timeout_budget": "Shared pre-spawn admission<=5.0s total (gate wait only remaining after hard token); hold<=12 not additive, cancel poll<=.25",
        "bulkhead": "1 gate, token bucket1/s burst1",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Gate wait fail-open лишь в оставшемся5s; token timeout prohibits spawn, limiter never bypassed. No independent5+5 waits."
      },
      {
        "dependency_operation": "serve interrupt/delete and process cleanup",
        "path": "cleanup",
        "timeout_budget": "Existing verified Keep-Alive control only: interrupt<=.09+DELETE<=.09+.02 scheduling=.20;TERMgrace<=.50;all reap/join/helper/temp/lease<=.50;total1.20. No lsof/reconnect on cleanup.",
        "bulkhead": "only own session/PGID, no new leases",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Best effort API failure never skips socket close/killpg; force SIGKILL, idempotent cleanup"
      },
      {
        "dependency_operation": "DSH SSE/client socket",
        "path": "hot",
        "timeout_budget": "probe<=.25, empty keepalive<=2 silence, write<=.5; detect<=5",
        "bulkhead": "single writer, bounded event queue1MiB/4096",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "FIN/RST ->client_gone+cleanup, no retry; slow consumer/overflow ->explicit terminal error if writable; hard write timeout cancels"
      },
      {
        "dependency_operation": "bridge.log",
        "path": "telemetry",
        "timeout_budget": "существующая synchronous append baseline; новые строки bounded/redacted, status write не зависит от log",
        "bulkhead": "existing _LOG_LOCK",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Fail-open OSError; не добавлять synchronous remote logger на request path"
      },
      {
        "dependency_operation": "serve permission reject / form cancel / single-turn interrupt",
        "path": "hot/control",
        "timeout_budget": "reject or form cancel<=.25 from event, then interrupt<=.10; no await prompt/lsof/reconnect; second-step output barrier immediate.",
        "bulkhead": "Use one idle control connection; delivery worker uses separate bounded prompt socket, <=3 sockets per active serve",
        "circuit_breaker": "Security fail-closed, not model/protocol fallback",
        "failure_mode_fallback": "permission.asked->decision reject OR nested form.created->cancel; then immediate interrupt. Control failure ->fail-closed+group kill, no allow, no Step2 output."
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
    "status_semantics": "PASS = проверенная полнота/замкнутость проектного guardrail; runtime assertion обязателен Stage3/L2 и ещё не выполнен. N/A = только отсутствие указанной функции на новом пути с двойным evidence; не waiver. Фактический FAIL/нет oracle -> REJECT, никакого техдолга вместо гейта.",
    "summary": {
      "PASS": 16,
      "N/A": 8,
      "FAIL": 0,
      "meaning": "projected design invariants only; implementation/runtime verification pending"
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "Boundary DAG Handler/Run -> transport source -> stdlib I/O, pure parser/recovery без reverse imports; runtime evidence shared source исключает отдельные несовместимые циклы.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Pure parsers не знают HTTP/process; adapter не пишет в wfile; Handler отвечает за presentation.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "Новый managed source/supervisor отдельный внутренний объект; не расширять монолитные Handler loops transport branching. Baseline размер server.py — унаследован, wholesale refactor вне scope.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Оба пути получают canonical (etype,payload), не OpenCode v2 objects; session/network cleanup скрыт adapter ownership.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит прежний OpenAI SSE/JSON. Password/session/control events не уходят в content; [мост] — явно разрешённый status REQ-005.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "Per-op+aggregate ready/session/cleanup deadlines,20/60/60 watchdog, write/probe limits; setup не блокирует SSE writer.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "Каждый Popen, включая fallback, внутри MAX_TOTAL_SPAWNS3 и RetryBudget; нет альтернативного бесконечного startup loop.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "Shared process budget+breaker+spawn rate1/s burst1; retry slot тот же, full jitter.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "gate и rate limiter перед каждым реальным child; pure local script eligibility без capability subprocess storm.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "Model event queue4096/1MiB +max frame1MiB+output budget8MiB; waiters<=2M; overflow явный fail, не silent drop.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Slot6/max12 или code-default2/effective4, fail-fast overflow, bounded slow-client writes.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не вводится; ThreadingHTTPServer, blocking upstream/setup в managed worker, single writer bounded.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
        "current_git_diff_output": "",
        "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
          "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
        "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
      }
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Queue.get/select c конечным timeout, FakeClock/RNG tests; readiness<=3 connects, никакого busy-spin polling.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "Session interrupt/delete,socket close, thread join, PGID stop и slot release на всех paths; factory shutdown закрывает owned leases.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "killpg даже если leader вышел; TERM->KILL<=1.2s cleanup, reap wait, child/grandchild проверка.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "Single writer; per-attempt state локален, shared manager/resilience locks; cleanup идемпотентен, close-before-create, port ownership/auth check.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "ask_reject/deny never allow; explicit brief chooses responseheaders OR sessionexecution deliverybarrier. Beforebarrier unknown delivery may fallback only after ownedcleanup/cap; afterbarrier only explicit same-transport retry+status, never silentrun. Not exactly-once; tool IDs dedup.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Port/endpoints/auth/Google route/schema не меняются; разрешённые behavior deltas явно CD и текущие REQ, fast reasoning exact preserved.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Delta и ended не удваиваются, step tokens учтены, EOF без terminal=error; parser splits/no raw tool leak; overflow explicit failure.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Early/error/recovery и terminal failed через legacy classifier; 401 deterministic fail-closed, watchdog exits логируются.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "secrets password per child env после whitelist; Basic header не логируется; mask before stdout/stderr/error artifact.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    }
  },
  "status_protocol_examples": {
    "initial": "[мост] Подключение к модели…\n",
    "retry": "[мост] Повтор попытки 2/3…\n",
    "waiting": "[мост] Ожидание первого токена (10 с)…\n"
  },
  "handoff_state": {
    "architecture_contract": "Cycle3 APPROVED architecture candidate for external a3,6RW+8FU design resolutions; no Council verdict/ARCH_GATE_PASS from author.",
    "implementation_tests": "NOT_RUN; Stage3a GroupA then3b GroupB and independent VER001..005 required.",
    "live_acceptance": "NOT_RUN allH0..H9; policy compliant default=false/runtime H7, human exception NOT_REQUIRED; ~/.dsh not touched by Architect.",
    "pending_orchestrator_actions": [
      "External a3 council on v2→v3 diff with independent launch_seat/verify_panel_proof; no author vote.",
      "Validate finalized cycle3b packet and independent a3 council; FU007 policy compliant, no human waiver; no author Council vote.",
      "Update envelope/fingerprints/hashes after council; outside three-file Architect allowlist.",
      "Only then Stage3a/3b+C clean-room verification and H0..H9: dark absent/false through H4/H5, H7 runtime true after H3/H6."
    ]
  },
  "verification_acceptance_matrix": {
    "FakeServe": "Stdlib subprocess implements exact frozen_v2_1_2_fixtures API/SSE, Basic401, /api/session/active, /openapi.json only per binary-key first handshake, session/prompt/interrupt/delete/permission decision=reject. Tests force serve for shebang; no Zen calls. Independent fixed fixture digest oracle + deliberate field/schema mutations; fake/adapter mutual agreement alone insufficient. GET active returns {data:{}} not[]; once-per-key /api/info version+PID and API schema info.version0.0.1, independent binary appversion2.1.2; invalid numeric error.status must fail validation. Six families now include form.created.data.form and form.cancelled.data; replies support cancel and immediate interrupt, freeze negative fixture expectations independently.",
    "mode_matrix": [
      "Code default=false + git runtime JSON absent ->run for all378baseline (REQ003/AC004). Runtime boolean true/env1true + native MachO ->serve only after rollout H7/H3/H6; enabled shebang fake ->run without probes unless explicit test override.",
      "First priority TRANSPORT=run/env0falseNoOff/disable-file/sticky TTL ->run; then force serve with no silent fallback; then auto boolean dynamic config/envtrue AND native eligibility. Same-process config true/false/deletion and malformed/unreadable/nonboolean fail-safe false; unchanged stat key no reopen, warning redacted; no Server restart.",
      "force serve+FakeServe shebang ->v2 SSE/JSON, stdinDEVNULL; fake legacy blocking stdin ->EOF/ready failure<=3s explicit no silent run",
      "auto ServeUnavailable in spawn/create/subscribe or pre-response-headers prompt and no execution SSE ->complete cleanup then1budgeted run fallback; totalPopen<=3",
      "POST prompt headers arrived OR valid session execution SSE while headers pending ->delivered; zero silent run, remaining first-event/token clocks active; explicit security401/403/cancel no fallback at any phase",
      "Default ask_reject, env deny both frozen permission rules; unsupported policy/missing safe endpoints fail-closed, no automatic policy switching",
      "Auto _ServeHealth3protocol failures ->TTL120 run new requests; provider breaker remainsclosed for protocol-only, provider failures remain independent",
      "Compare frozen immutable_run_env function SHA256, tests/test_run_env.py/start.sh SHA256; preserving tests by editing expected hashes запрещено."
    ],
    "status_matrix": [
      "slow blank upstream + startup-gate/rate-wait: grace.30 first [мост] LF<=1s",
      "fast real reasoning/text before grace: no initial status; Simple greeting. exact",
      "off/none/nonthinking + slow upstream: no synthetic reasoning; normal content/keepalive/error unchanged",
      "whitespace/empty comments/status do not set first-token or attempt_output",
      "retry accepted after model reasoning: exactly one retry status, raw model bytes retained, no reasoning dedup",
      "normal127ms model reasoning: no periodic status, natural LF enables collapsed preview, no newline injected into model delta",
      "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes",
      "Model reasoning chunk без trailingLF ->synthetic delta \"\\n[мост] ...\\n\"; whole delta incl leading LF provenance=synthetic, model-only concatenation exact bytes, literal model [мост] survives; LF already present->no redundant prefix; fast Simple greeting.->zero statuses.",
      "After first model token pause>=15s mandatory waiting-continuation heartbeat every15s; silence threshold explicit, not optional5s. Firsttoken wait remains5s; status does not reset stall60."
    ],
    "watchdog_matrix": [
      "Serve HTTP ready success + accepted prompt headers but zero session SSE ->first_event_timeout at20s from prompt_send_start +cleanup<=1.2 (<22s); first_event_ms remainsnull",
      "Legacy first-event from attempt start until first valid run event/step_start; serve ready3 and create+subscribe2 bounded independently before prompt",
      "Current session execution.started/step.started/reasoning.started SSE after prompt satisfies first_event once; first_event_ms=request-relative; foreign sessions/pre-prompt started/server.connected/session.created/comments/status do not satisfy",
      "Valid started/control but no useful model token ->first_token_timeout60s; started/control/comments/reject not token, no indefinite reset",
      "After first useful model delta pause>stall60 ->stall_timeout; comments/bridge statuses/repeated transport noise do not reset",
      "POST prompt delivery blocked past2s while SSE progresses is permitted; supervisor/reader/writer concurrent and cancel-aware, no duplicate prompt; request totaldeadline neverreset, no retry4"
    ],
    "lifecycle_matrix": [
      "disconnect at gate/limiter/ready/prompt/blocked SSE/after reasoning, detect<=5s and PGID absent<=7s",
      "leader exits but descendant holds stdout; group still killed",
      "SIGTERM ignored ->SIGKILL, leader reaped, no child/grandchild",
      "success/tool step/error/fallback/shutdown each closes session/socket/threads/slot once",
      "byte queue/frame/output overflow explicit error (no silent model delta loss)",
      "50 cancel fault-injection cycles counters in_use/waiters/sessions/sockets/readers=0",
      "Foreign listener PID/PGID after reserve-release ->zero Authorization/password/prompt bytes, no foreign API/kill; bounded port retry ready3s and totalspawns<=3.",
      "Unique per-spawn zen-serve-state-* state/TMPDIR; OPENCODE_DB=:memory: on ALL3 branches, standard XDG_DATA_HOME/auth/model config retained; finally remove owned root+lease;50cancels + hard-parent-kill→helper/reaper restore0old processes/temp, foreign objects untouched.",
      "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN.",
      "1lsof per spawn then Keep-Alive; takeover beforeREADY0Authorization/prompt bytes, no foreign signals; control reconnect proof separate.35s, never lsof/repair in urgent control/cleanup."
    ],
    "tools_matrix": [
      "every split point and single-char deltas for both tags, JSON embedded close strings/code quoting existing fixtures",
      "stream content before open tag visible immediately, pending genuine prefix<=12 plus inherited code-context lookahead",
      "unparsed/open genuine blocks stripped by existing wrapper, no raw tool tags in SSE content",
      "native call lifecycle normalized/dedup per call-id, mapped/unmapped behavior identical; no auto allow",
      "step.ended tokens input/output/cached/reasoning counted once then tool finish, no followup synthetic step",
      "early legacy error may recover; late transient/fatal error and incomplete recovery same on fake v2",
      "existing reasoning_interrupted and interrupted cleanup across delta boundaries",
      "permission.asked {data.id,sessionID,action,resources,source} ->POST reply {decision:reject},status204; both ask_reject/deny modes; POST prompt may stayblocked while reject executes on separate control socket; never once/always/allow.",
      "Frozen wire tokens.cache.read/write ->canonical tokens{input,output,cached=cache.read,reasoning}; mutate delta path/cache envelope/permission lifecycle ->independent oracle fail, step assistantMessageID dedup, not invented wire stepID.",
      "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side. On input.ended save $.data.text and parse JSON as object with runtime validation. Prefer called.data.input if present and valid; if called absent before failed/step.ended use completed input.ended.text, including streaming→failed. Never emit partial JSON; dedup by sessionID/assistantMessageID/call id. Both paths give identical mapped DSH tool_calls. Invalid JSON follows existing incomplete/unmapped recovery, not invented empty args.",
      "form.created uses data.form.sessionID/id (Form.Info nested); validate own session before action. Cancel immediately via POST /api/session/{id}/form/{formID}/cancel, no answer/allow; form.cancelled data.id/sessionID settles same form. Not a model token/first-event. Error->security fail-closed+kill. See single_turn_control.",
      "permission reject and form cancel MUST immediately interrupt; Step2 output0 even if emitted concurrently, completed input.ended JSON tool mapping same as called.input. Cancel/reject failure fail-closed.",
      "Env secret-sentinel matrix standalone/opencode-go/base_url/static;0parent API_KEY/TOKEN/SECRET/arbitrary env, required config/models/auth preserved."
    ],
    "baseline_matrix": [
      "two original budget fixtures:3 spawns, no fourth tool result, stop; separate fixture unmapped->incomplete->calls within3 proves counter separation",
      "fresh _Resilience/_RetryBudget per test, reverse fixed ordering plus isolated/full runner",
      "all17 existing modules untouched except the3 acknowledged assertions/isolation in test_step_interruption; no Google changes",
      "AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN."
    ],
    "resilience_matrix": [
      "46 exact HL canonical keys+sources and memory inequality",
      "21 stop-code oracles + T-LIFE/O-EXIT/M-SEM, each N/A has actual diff + transitive AST proof",
      "new process/socket resource manager singleton and bounded lease count, 50 control keepalive operations1 connection per lease",
      "RPS token bucket/cancel/full jitter/retry budget/breaker HALF_OPEN1 via FakeClock/RNG",
      "wire event JSON decode allowed; config decode/re.compile/reparse-full-history on per-delta hot path forbidden",
      "HALF_OPEN active probe held across reset_s boundary: zero second probes until owner cleanup; common _SlotBulkhead code-default M2/waiters4 and deploy M6/waiters12, no second uncounted ingress queue.",
      "Combined gate+limiter5,ready3,create+subscribe2,cleanup1.2;15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; slowcreate->one preheader run; afterheader/event->no run; no fourthPopen.",
      "_ServeHealth force5protocol failures ->zero model breakerfail; auto3failures->next run untilTTL120, expiry oneprobe, successful terminalreset, protocolfailrearm; binarymtime+size change invalidates capability; real provider5 failures modelbreakerOPEN.",
      "Memory SSoT fields2048/256/1152 MiB exactly; design1408<=1638.4 not H3PASS.3HTTP sockets per serve supports immediate reject while promptHTTP pending; recalc nodeports246<=8192.",
      "Parent admitted threads55=1+18+6+6+6+12+6;parentFD108<=128, auxiliary processes6helper+6lsof included. Arbitrary rejected handler peak measured H3, not claimed bounded by slots.",
      "All phase×event actions and two health counter effects match fallback_decision_table; changedmtime+same used-schema projection->serve, mismatch->run+diagnostic;permission capability gap fail-closed.",
      "Normal p99<=180 goal measured separately; three60s firsttoken faultprofile+aux51.6<=231.6,>=100sample batch nearest-rank criterion. Universal TIMEOUT1800 unchanged."
    ],
    "rollout_boundary": "Все H0..H9 NOT_RUN, external a3 ACCEPT+panel proof и независимые VER gates обязательны; Architect не выполняет rollout. H0 BLOCKING до sync/restart: проверить текущий env не force serve/true, отсутствие production dynamic_config.json либо boolean false; при прежнем enabled состоянии атомарно записать false, проверить read-back; дополнительный disable-serve разрешён. Снять старые PID/start/lease identity. H4 sync/read-back server.py hash; H5 launchctl kickstart с config absent/false: сразу dark run без окна serve; startup reaper0 старых собственных serve/helper/temp roots, чужие процессы untouched. На отдельном кандидате test-local dynamic_config.json=true и отдельный disable-file path: provider-free info/active, H3 реальные6parallel RSS/FD+OPENCODE_DB=:memory:, H6 live permission/tool isolation, Stage3a/A затем3b/B. На production до H7 run. H7 ТОЛЬКО после PASS H3 и H6: при env auto без explicit false и закрытом TTL подготовить tempfile в ~/.dsh/bridges/opencode-zen-bridge/,0600, записать {\"REALTIME_SERVE_ENABLED\":true}, os.replace в dynamic_config.json; убедиться дополнительный disable-serve отсутствует. Следующий native auto запрос на :9883 использует serve без правки start.sh и без повторного рестарта LaunchAgent. H8 повторяет живые проверки рабочего чата, H9 проверяет runtime false/true и disable-file same PID, отдельно kickstart-k crash recovery. Никакой выдачи design/NOT_RUN за runtime PASS."
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46 exact key equality and field_sources/field_units equality against team architecture.md §3.0",
    "stop_codes": "21 main codes + T-LIFE/O-EXIT/M-SEM=24 unique",
    "legacy_antipatterns": "21 exact keys from approved reference schema",
    "verification_owner": "5/5 owner=verifier",
    "decisions": "4/4 two-way with >=2 genuine alternatives",
    "evidence_refs": "69 EVD records,49analyst facts; provided070..072, source073, panel074 clearly separated. EVD ids intentionally retain gap065..069; no fabricated missing observations.",
    "status_protocol": "3 templates begin[мост]/endLF; при model unterminated line весь дополнительный leading LF synthetic, template bytes модели не менять.",
    "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes.",
    "VER_004_syntax": "ast.parse PASS and changed-hunk regex tested for count+singleton; embedded commands NOT_RUN because new file NOT_PRESENT. Full3files independent Stage3/L2 required.",
    "rework_coverage": "Exactly6RW+8FU a2,16sourcefindings eachonce in rework_resolutions_a2; rework_resolutions is compatibility alias, not additional closures.21a1 historicalrecords retained.",
    "memory_units": "All46 canonical keys+field_sources+field_units; memory2048/256/1152 MiB;1408<=1638.4MiB",
    "aux_budget": "15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; old independent5+5/.5/.2 absent",
    "wire_evidence": "Sixfamilies, source Form.Info wrapper verified; delta/token/permission old literals unchanged; new digest calculated deterministically; candidate runtime NOT_RUN."
  },
  "routing_profile": "standard",
  "panel_resolution_choices": [
    {
      "ids": [
        "RW-001",
        "RW-007"
      ],
      "source_positions": [
        "PANEL-A1-F-001: headers response barrier",
        "RW-001.evidence: Seat2 начало POST barrier"
      ],
      "resolution": "Текущий explicit user brief выбирает response headers OR started session event; unknown pre-header delivery может fallback только после полного cleanup; after-header no silent run. Admission/create budgets отделены от prompt wait."
    },
    {
      "ids": [
        "RW-002"
      ],
      "source_positions": [
        "PANEL-A1-F-002: допускается один safe policy transition до prompt",
        "PANEL-A1-F-018: unsupported policy fail-closed без auto-switch"
      ],
      "resolution": "Default ask_reject и явный env deny, автоматического переключения НЕТ вообще. После accepted401/403 fatal; live H6 обязателен."
    },
    {
      "ids": [
        "RW-006",
        "RW-009"
      ],
      "source_positions": [
        "PANEL-A1-F-006: H3 обязателен до включения",
        "PANEL-A1-F-010: default=true без start.sh"
      ],
      "resolution": "Историческое a1 требование default=true superseded compliant delta cycle3b: кодовый default=false, runtime JSON absent/false до H7. Активация :9883 атомарным true после H3/H6 без start.sh/restart;378legacy идут run. Источник a1 сохраняется как история, без human waiver."
    },
    {
      "ids": [
        "RW-011",
        "RW-012"
      ],
      "source_positions": [
        "PANEL-A1-F-012: канон MiB, byte арифметика недостаточна",
        "PANEL-A1-F-013: strict0error вместо старого allowance"
      ],
      "resolution": "MiB exact values; type allowance удалён; существующие2errors — baseline debt для исправления Coder в server.py, не текущий PASS."
    },
    {
      "ids": [
        "RW-004",
        "RW-007"
      ],
      "source_positions": [
        "Brief logical session.permission.requested/tokens.cached",
        "EVD-062 actual v2.1.2 permission.asked/tokens.cache.read+write; permission reply decision"
      ],
      "resolution": "Freeze actual wire literals и canonical expected mapping, не изобретать отсутствующие поля/имена. Group labels сохранены в fixture families для механического verify-fixed."
    }
  ],
  "rework_source": {
    "path": "handoff/panel-rework-brief-arch-a2.json",
    "sha256": "baa297e7819579dc1cf779af370b16f385a7ede77d9538553713212b1475dc7f",
    "base_packet_path": "architecture/architecture-packet.v2.json",
    "base_packet_sha256": "c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d",
    "resolutions_count": 14,
    "blocking_count": 6,
    "nonblocking_count": 8,
    "findings_count": 16,
    "namespace": "a2 current rework_resolutions alias mirrors rework_resolutions_a2; a1 history in rework_resolutions_a1; IDs are unique within pass, not counted twice through alias."
  },
  "rework_resolutions_a1": [
    {
      "id": "RW-001",
      "source_findings": [
        "PANEL-A1-F-001"
      ],
      "status": "RESOLVED",
      "changes_made": "Pre-header fallback + session-event earlier barrier, explicit unknown-delivery risk and same-transport retries. create/subscribe budget separated from concurrent POST generation, cap3 unchanged.",
      "packet_locations": [
        "#/decisions/0/details/fallback_barrier",
        "#/decisions/0/details/session_wire",
        "#/resilience_gates/R_BULK/R-BULK-I1",
        "#/verification_acceptance_matrix/mode_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-002",
      "source_findings": [
        "PANEL-A1-F-002",
        "PANEL-A1-F-007",
        "PANEL-A1-F-018"
      ],
      "status": "RESOLVED",
      "changes_made": "Default ask_reject, env deny, _serve_env over byte-identical _run_env; decision=reject only, missing capability/401/403 fail-closed, no automatic policy transition.",
      "packet_locations": [
        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY",
        "#/decisions/0/details/tool_policy",
        "#/risks/0",
        "#/threat_model/threats/1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-003",
      "source_findings": [
        "PANEL-A1-F-003"
      ],
      "status": "RESOLVED",
      "changes_made": "Parent bind0/reserve/release-before-Popen explicitport; lsof PID/PGID proof before Authorization/prompt, foreign listener zero leakage/own cleanup and bounded retry.",
      "packet_locations": [
        "#/decisions/0/details/listener_ownership",
        "#/decisions/0/details/spawn",
        "#/threat_model/threats/0",
        "#/verification_acceptance_matrix/lifecycle_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-004",
      "source_findings": [
        "PANEL-A1-F-004"
      ],
      "status": "RESOLVED",
      "changes_made": "Five frozen fixture families with exact source-proven field paths+canonical expectation+SHA256; actual wire permission.asked, reply decision and tokens.cache.read normalized, not invented aliases.",
      "packet_locations": [
        "#/decisions/0/details/event_contract",
        "#/evidence/61",
        "#/verification_policy/wire_fixture"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-005",
      "source_findings": [
        "PANEL-A1-F-005"
      ],
      "status": "RESOLVED",
      "changes_made": "REQ-013/AD-001/RISK-002 guarantee only per-spawn proxy-env rotation AC-018; loopback georouter NO_PROXY bypasses child HTTP_PROXY, no guaranteed clean Zen IP.",
      "packet_locations": [
        "#/requirements/12",
        "#/decisions/0/drivers",
        "#/risks/1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-006",
      "source_findings": [
        "PANEL-A1-F-006"
      ],
      "status": "RESOLVED",
      "changes_made": "Per-spawn XDG_DATA_HOME+preserved OPENCODE_MODELS_PATH+finally rmtree, H3 actualRSS parent+6children<=1638.4MiB/zero DB locks103KB×6×3; no Stage2 runtime PASS.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/C_MULT/C-MULT-I1",
        "#/evolution/H3_rollout_gate"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-007",
      "source_findings": [
        "PANEL-A1-F-008"
      ],
      "status": "RESOLVED",
      "changes_made": "Lightweight active-session readiness3s; combined admission5s; create+subscribe2s; daemon POST delivery concurrent SSE; exact Model.Ref/providerID/id/variant and session permissions array; total51.6<=54.",
      "packet_locations": [
        "#/decisions/0/details/startup",
        "#/decisions/0/details/admission",
        "#/decisions/0/details/session_wire",
        "#/high_load_envelope/operational_profile",
        "#/resilience_gates/dependency_failure_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-008",
      "source_findings": [
        "PANEL-A1-F-009"
      ],
      "status": "RESOLVED",
      "changes_made": "Serve first_event20 only current-session execution SSE after prompt; HTTP readiness/headers ignored; independent clocks and request-relative first_event_ms, accepted-noevents timeout<=22s.",
      "packet_locations": [
        "#/decisions/2/details/clocks",
        "#/decisions/2/details/telemetry",
        "#/verification_acceptance_matrix/watchdog_matrix",
        "#/resilience_gates/O_EXIT_v1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-009",
      "source_findings": [
        "PANEL-A1-F-010"
      ],
      "status": "RESOLVED",
      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
      "packet_locations": [
        "#/decisions/0/details/configuration",
        "#/decisions/0/details/auto_fake_compatibility",
        "#/evolution/rollout",
        "#/evolution/feature_flag",
        "#/evolution/rollback",
        "#/approval"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true,
      "decision_required_human": false
    },
    {
      "id": "RW-010",
      "source_findings": [
        "PANEL-A1-F-011",
        "PANEL-A1-F-016"
      ],
      "status": "RESOLVED",
      "changes_made": "Tool-policy reference corrected to EVD-050+F-08; analyst IDs restricted49 facts, council refs PANEL-A1-F-NNN.",
      "packet_locations": [
        "#/decisions/0/details/tool_policy",
        "#/evidence/49",
        "#/semantic_checks/evidence_refs"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-011",
      "source_findings": [
        "PANEL-A1-F-012"
      ],
      "status": "RESOLVED",
      "changes_made": "SSoT46 exact fields/sources/units, memory2048/256/1152MiB and1408<=1638.4MiB across HL-ENV/memory closure.",
      "packet_locations": [
        "#/high_load_envelope/required_hl_env_fields",
        "#/high_load_envelope/units",
        "#/high_load_envelope/field_units",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-012",
      "source_findings": [
        "PANEL-A1-F-013"
      ],
      "status": "RESOLVED",
      "changes_made": "VER004 strict ruff format/check and basedpyright on all3files; zero errors, removed v1 error allowance; preserved server Any and other warning ceilings; inherited error debt explicitly assigned to Coder.",
      "packet_locations": [
        "#/verification_surface/3",
        "#/risks/7",
        "#/decisions/0/details/typing"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-013",
      "source_findings": [
        "PANEL-A1-F-017"
      ],
      "status": "RESOLVED",
      "changes_made": "Leading LF in entire synthetic status after unterminated model chunk, provenance filter preserves model bytes and literal model [мост]; fast Simple greeting unchanged.",
      "packet_locations": [
        "#/decisions/1/details/status_separator",
        "#/decisions/1/details/pure_reasoning",
        "#/verification_acceptance_matrix/status_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "RW-014",
      "source_findings": [
        "PANEL-A1-F-019"
      ],
      "status": "RESOLVED",
      "changes_made": "_ServeHealth threshold3/TTL120/one recovery probe newauto requests only; protocol failure neutral to model breaker; exact version/schema cache by binary stat; no silent accepted-prompt replay.",
      "packet_locations": [
        "#/decisions/0/details/transport_health",
        "#/decisions/0/details/protocol_compatibility",
        "#/decisions/2/details/retry",
        "#/resilience_gates/R_BULK/R-BULK-I3",
        "#/verification_acceptance_matrix/resilience_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-001",
      "source_findings": [
        "PANEL-A1-F-014"
      ],
      "status": "RESOLVED",
      "changes_made": "Isolated per-spawn XDG_DATA_HOME, preserve models path, cleanup finally; risk/H3 and lifetime updated.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/risks/2",
        "#/resilience_gates/T_LIFE_v1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-002",
      "source_findings": [
        "PANEL-A1-F-015"
      ],
      "status": "RESOLVED",
      "changes_made": "ADR0005+INDEX explicitly deferred outside frozen scope §10, materialization remains empty.",
      "packet_locations": [
        "#/deferred/3",
        "#/materialization"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-003",
      "source_findings": [
        "PANEL-A1-F-020"
      ],
      "status": "RESOLVED",
      "changes_made": "Residual cross-provider reasoning replay risk accepted and mitigation short/infrequent nonsecret statuses recorded.",
      "packet_locations": [
        "#/risks/10",
        "#/decisions/1/details/replay"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-004",
      "source_findings": [
        "PANEL-A1-F-021"
      ],
      "status": "RESOLVED",
      "changes_made": "ruff format --check explicitly covers all3files alongside linter.",
      "packet_locations": [
        "#/verification_surface/3"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-005",
      "source_findings": [
        "PANEL-A1-F-022"
      ],
      "status": "RESOLVED",
      "changes_made": "New JSON typed object+narrowing/TypedDict within server.py, no new module/allowlist expansion; reportAny/reportExplicitAny each<=125.",
      "packet_locations": [
        "#/decisions/0/details/typing",
        "#/verification_surface/3"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-006",
      "source_findings": [
        "PANEL-A1-F-023"
      ],
      "status": "RESOLVED",
      "changes_made": "File disable switch os.path.exists request-entry O(1), default ~/.dsh path/env override, same PID H9 toggle, no restart required; no live file modified.",
      "packet_locations": [
        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
        "#/evolution/rollback",
        "#/verification_acceptance_matrix/mode_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    },
    {
      "id": "FU-007",
      "source_findings": [
        "PANEL-A1-F-024"
      ],
      "status": "RESOLVED",
      "changes_made": "Budget51.6s<=54s, headroom2.4>=2.0, combinedadmission5+ready3+setup2+cleanup1.2 explicit.",
      "packet_locations": [
        "#/resilience_gates/R_BULK/R-BULK-I1",
        "#/high_load_envelope/operational_profile"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
      "pass": "a1",
      "historical": true
    }
  ],
  "rework_source_a1": {
    "path": "handoff/panel-rework-brief-arch-a1.json",
    "sha256": "d173ff674c5a105fd85ab00a2a276ebcfb92d9b7295523721e9eed6503e5ed96",
    "base_packet_path": "architecture/architecture-packet.v1.json",
    "base_packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
    "resolutions_count": 21,
    "blocking_count": 14,
    "nonblocking_count": 7,
    "namespace": "Analyst F-01..F-49; council PANEL-A1-F-001..024 = original brief finding ids prefixed PANEL-; RW/FU IDs unchanged"
  },
  "rework_resolutions_a1_note": "Historical a1 closure record retained; empty-XDG mechanism superseded by a2 RW002 memoryDB/auth, full-file format/no nonAny margin superseded RW001, default-enable approval clarified FU007. Original safety/bytehash/cap3/no-silent-replay/permission/units/status semantics retained. Histories are not current runtime PASS. Cycle3b supersedes default=true in historical a1 RW009 with code default=false and H7 runtime JSON, no human waiver; a1 source positions remain historical.",
  "rework_resolutions_a2": [
    {
      "id": "RW-001",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-001",
        "PANEL-A2-F-009"
      ],
      "changes_made": "Исполнимый VER004: full new-file/range legacy formatter, server-only exact E402 allowance, temporary /tmp bridge import-root,3legacy type error sites and explicit nonAny budgets; bytehash/Google oracle unchanged.",
      "packet_locations": [
        "#/verification_surface/3",
        "#/decisions/0/details/typing",
        "#/decisions/0/details/immutable_run_env",
        "#/risks/7",
        "#/evidence/66"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-002",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-002",
        "PANEL-A2-F-007"
      ],
      "changes_made": "OPENCODE_DB=:memory:,120.7ms/156.8MiB/0db EVD071; preserve standard auth/models/config, owned state+TMPDIR; /api/info preflight and real provider auth explicitly pending.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/decisions/0/details/serve_env_sanitization",
        "#/assumptions/0",
        "#/risks/2",
        "#/evolution/H3_rollout_gate",
        "#/evidence/65"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-003",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-003"
      ],
      "changes_made": "Nested form.created→cancel<=.25s, sixth frozen family, input.ended.text fallback, reject/cancel→immediate interrupt with Step2 output barrier and mapped calls/recovery.",
      "packet_locations": [
        "#/decisions/0/details/single_turn_control",
        "#/decisions/0/details/session_wire/form_cancel",
        "#/decisions/0/details/event_contract",
        "#/decisions/3/details/step",
        "#/threat_model/threats/1"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-004",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-004"
      ],
      "changes_made": "One lsof SPAWN→READY0.35s,3 persistent HTTP/1.1 lanes with proc.poll guard; explicit reconnect outside urgent/cleanup budgets, foreign listener0leak/0kill.",
      "packet_locations": [
        "#/decisions/0/details/listener_ownership",
        "#/decisions/0/details/session_wire/cleanup",
        "#/decisions/2/details/cleanup",
        "#/resilience_gates/C_MULT/C-MULT-I5"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-005",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-005"
      ],
      "changes_made": "Exact allowlist on all3_run_env branches before child-only secrets/overrides; OPENCODE_ZEN_BRIDGE_* and arbitrary parent secret sentinels absent, required routing/auth preserved.",
      "packet_locations": [
        "#/decisions/0/details/serve_env_sanitization",
        "#/threat_model/threats/2",
        "#/verification_acceptance_matrix/tools_matrix"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-006",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-006"
      ],
      "changes_made": "Atomic UID-scoped lease + parent-pipe helper and safe startup reaper, ps/PGID/start-time/binary/port/inode checks; hard-kill→next-start cleanup oracle and foreign-object negatives, H0/H9 NOT_RUN.",
      "packet_locations": [
        "#/decisions/0/details/crash_recovery",
        "#/resilience_gates/T_LIFE_v1",
        "#/verification_surface/4/orphan_oracles",
        "#/evolution/H0_precondition",
        "#/evolution/H9_crash_recovery_gate"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-001",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-008"
      ],
      "changes_made": "Owner proof errors counted once,3timeouts→DEGRADED; --port0 stdout considered unverified alternative; one bounded lsof/helper resource accounting included.",
      "packet_locations": [
        "#/decisions/0/details/transport_health/counted_failures",
        "#/decisions/0/alternatives",
        "#/high_load_envelope/operational_profile/thread_accounting",
        "#/resilience_gates/C_MULT/C-MULT-I5"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-002",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-010"
      ],
      "changes_made": "EVD070 actual supplied378tests/122.956s/0imports/3knownfailures frombridge cwd; no17module edits needed, future full-green gate preserved.",
      "packet_locations": [
        "#/verification_surface/1/baseline",
        "#/evidence/64"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-003",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-011"
      ],
      "changes_made": "Changed binary stat key revalidates used schema projection; same hash remains serve, mismatch run+reason; expected schema fixture independent. REQ016/AC021 authorized fields preserved, detail diagnostic adjacent if strict parser.",
      "packet_locations": [
        "#/decisions/0/details/protocol_compatibility",
        "#/decisions/2/details/telemetry",
        "#/resilience_gates/O_EXIT_v1"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-004",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-012"
      ],
      "changes_made": "Explicit phase/event→fallback/retry/fail and ServeHealth/model counter table, including20s pre-/post-header no-event; any headers latchDELIVERED before classification.",
      "packet_locations": [
        "#/decisions/0/details/fallback_decision_table",
        "#/decisions/0/details/fallback_barrier",
        "#/decisions/2/details/retry",
        "#/resilience_gates/R_BULK/R-BULK-I3"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-005",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-013"
      ],
      "changes_made": "REQ004/005 match thinking eligibility/grace.30,fast/off/JSON exclusions and immutable model bytes; mandatory post-token stall heartbeat threshold/interval15s, no watchdog resets.",
      "packet_locations": [
        "#/requirements/3",
        "#/requirements/4",
        "#/decisions/1/details/lifecycle",
        "#/decisions/1/details/STALL_HEARTBEAT_INTERVAL_S",
        "#/contract_deltas/0"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-006",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-014"
      ],
      "changes_made": "18admittedhandlers+readers/delivery/12drains/supervisors/watchdogs→55parentthreads;108FD<=128,helper/lsof process/memory included; normalp99goal180 vs degraded3*60+51.6=231.6 separately measured, flood caveat explicit.",
      "packet_locations": [
        "#/high_load_envelope/operational_profile/thread_accounting",
        "#/high_load_envelope/operational_profile/fd_accounting",
        "#/high_load_envelope/operational_profile/p99_criteria",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-007",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-015"
      ],
      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
      "packet_locations": [
        "#/approval",
        "#/assumptions/2",
        "#/assumptions/3",
        "#/evolution/H0_precondition",
        "#/evolution/rollout",
        "#/decisions/0/details/configuration",
        "#/evolution/rollback"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-008",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-016"
      ],
      "changes_made": "Considered split3a/3b delivery, one branch/MR for owner realtime outcome with staged execution. GroupA RC2/RC3 requires noFakeServe; GroupB independent tests localize serve failures.",
      "packet_locations": [
        "#/decisions/0/alternatives",
        "#/verification_surface/4/groups"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    }
  ],
  "rework_resolutions": [
    {
      "id": "RW-001",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-001",
        "PANEL-A2-F-009"
      ],
      "changes_made": "Исполнимый VER004: full new-file/range legacy formatter, server-only exact E402 allowance, temporary /tmp bridge import-root,3legacy type error sites and explicit nonAny budgets; bytehash/Google oracle unchanged.",
      "packet_locations": [
        "#/verification_surface/3",
        "#/decisions/0/details/typing",
        "#/decisions/0/details/immutable_run_env",
        "#/risks/7",
        "#/evidence/66"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-002",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-002",
        "PANEL-A2-F-007"
      ],
      "changes_made": "OPENCODE_DB=:memory:,120.7ms/156.8MiB/0db EVD071; preserve standard auth/models/config, owned state+TMPDIR; /api/info preflight and real provider auth explicitly pending.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/decisions/0/details/serve_env_sanitization",
        "#/assumptions/0",
        "#/risks/2",
        "#/evolution/H3_rollout_gate",
        "#/evidence/65"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-003",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-003"
      ],
      "changes_made": "Nested form.created→cancel<=.25s, sixth frozen family, input.ended.text fallback, reject/cancel→immediate interrupt with Step2 output barrier and mapped calls/recovery.",
      "packet_locations": [
        "#/decisions/0/details/single_turn_control",
        "#/decisions/0/details/session_wire/form_cancel",
        "#/decisions/0/details/event_contract",
        "#/decisions/3/details/step",
        "#/threat_model/threats/1"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-004",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-004"
      ],
      "changes_made": "One lsof SPAWN→READY0.35s,3 persistent HTTP/1.1 lanes with proc.poll guard; explicit reconnect outside urgent/cleanup budgets, foreign listener0leak/0kill.",
      "packet_locations": [
        "#/decisions/0/details/listener_ownership",
        "#/decisions/0/details/session_wire/cleanup",
        "#/decisions/2/details/cleanup",
        "#/resilience_gates/C_MULT/C-MULT-I5"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-005",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-005"
      ],
      "changes_made": "Exact allowlist on all3_run_env branches before child-only secrets/overrides; OPENCODE_ZEN_BRIDGE_* and arbitrary parent secret sentinels absent, required routing/auth preserved.",
      "packet_locations": [
        "#/decisions/0/details/serve_env_sanitization",
        "#/threat_model/threats/2",
        "#/verification_acceptance_matrix/tools_matrix"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "RW-006",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-006"
      ],
      "changes_made": "Atomic UID-scoped lease + parent-pipe helper and safe startup reaper, ps/PGID/start-time/binary/port/inode checks; hard-kill→next-start cleanup oracle and foreign-object negatives, H0/H9 NOT_RUN.",
      "packet_locations": [
        "#/decisions/0/details/crash_recovery",
        "#/resilience_gates/T_LIFE_v1",
        "#/verification_surface/4/orphan_oracles",
        "#/evolution/H0_precondition",
        "#/evolution/H9_crash_recovery_gate"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-001",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-008"
      ],
      "changes_made": "Owner proof errors counted once,3timeouts→DEGRADED; --port0 stdout considered unverified alternative; one bounded lsof/helper resource accounting included.",
      "packet_locations": [
        "#/decisions/0/details/transport_health/counted_failures",
        "#/decisions/0/alternatives",
        "#/high_load_envelope/operational_profile/thread_accounting",
        "#/resilience_gates/C_MULT/C-MULT-I5"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-002",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-010"
      ],
      "changes_made": "EVD070 actual supplied378tests/122.956s/0imports/3knownfailures frombridge cwd; no17module edits needed, future full-green gate preserved.",
      "packet_locations": [
        "#/verification_surface/1/baseline",
        "#/evidence/64"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-003",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-011"
      ],
      "changes_made": "Changed binary stat key revalidates used schema projection; same hash remains serve, mismatch run+reason; expected schema fixture independent. REQ016/AC021 authorized fields preserved, detail diagnostic adjacent if strict parser.",
      "packet_locations": [
        "#/decisions/0/details/protocol_compatibility",
        "#/decisions/2/details/telemetry",
        "#/resilience_gates/O_EXIT_v1"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-004",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-012"
      ],
      "changes_made": "Explicit phase/event→fallback/retry/fail and ServeHealth/model counter table, including20s pre-/post-header no-event; any headers latchDELIVERED before classification.",
      "packet_locations": [
        "#/decisions/0/details/fallback_decision_table",
        "#/decisions/0/details/fallback_barrier",
        "#/decisions/2/details/retry",
        "#/resilience_gates/R_BULK/R-BULK-I3"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-005",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-013"
      ],
      "changes_made": "REQ004/005 match thinking eligibility/grace.30,fast/off/JSON exclusions and immutable model bytes; mandatory post-token stall heartbeat threshold/interval15s, no watchdog resets.",
      "packet_locations": [
        "#/requirements/3",
        "#/requirements/4",
        "#/decisions/1/details/lifecycle",
        "#/decisions/1/details/STALL_HEARTBEAT_INTERVAL_S",
        "#/contract_deltas/0"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-006",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-014"
      ],
      "changes_made": "18admittedhandlers+readers/delivery/12drains/supervisors/watchdogs→55parentthreads;108FD<=128,helper/lsof process/memory included; normalp99goal180 vs degraded3*60+51.6=231.6 separately measured, flood caveat explicit.",
      "packet_locations": [
        "#/high_load_envelope/operational_profile/thread_accounting",
        "#/high_load_envelope/operational_profile/fd_accounting",
        "#/high_load_envelope/operational_profile/p99_criteria",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-007",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-015"
      ],
      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
      "packet_locations": [
        "#/approval",
        "#/assumptions/2",
        "#/assumptions/3",
        "#/evolution/H0_precondition",
        "#/evolution/rollout",
        "#/decisions/0/details/configuration",
        "#/evolution/rollback"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    },
    {
      "id": "FU-008",
      "pass": "a2",
      "status": "RESOLVED",
      "resolution_level": "architecture_contract",
      "source_findings": [
        "PANEL-A2-F-016"
      ],
      "changes_made": "Considered split3a/3b delivery, one branch/MR for owner realtime outcome with staged execution. GroupA RC2/RC3 requires noFakeServe; GroupB independent tests localize serve failures.",
      "packet_locations": [
        "#/decisions/0/alternatives",
        "#/verification_surface/4/groups"
      ],
      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
      "decision_required_human": false
    }
  ],
  "evidence_refs": [
    "EVD-070",
    "EVD-071",
    "EVD-072",
    "EVD-073",
    "EVD-074"
  ]
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json sha256=6182932f2017bf91a55cdf9023fa4d49b658a4785ede93da283c182a602d7083
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "criticality": "S2",
  "packet_sha256": "8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608",
  "verification_surface_sha256": "702966bd09cdee8d15b6487f1147cd5672558cf3882cda3fe24ae4a608e63d40",
  "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b",
  "architect_worktree_sha256": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
  "materialized_targets": 0
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v2-to-v3.diff sha256=dd78389fed71c7eb886e32398575396a7979ba597605da114f3f5bf41ce8e17b
# Mechanical unified diff (diff -u): Architecture Packet v2 -> v3
# old_revision: architecture-packet.v2.json sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d
# new_revision: architecture-packet.json sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
--- architecture-packet.v2.json (sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d)
+++ architecture-packet.json (v3 sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608)
@@ -2,3 +2,3 @@
   "schema_version": "1.0",
-  "packet_version": "2.0",
+  "packet_version": "3.0",
   "task_id": "zen-realtime-reasoning",
@@ -6,3 +6,3 @@
   "preset": "analyst-teamlead",
-  "cycle": 2,
+  "cycle": 3,
   "criticality": "S2",
@@ -11,6 +11,6 @@
   "role_plan": {
-    "path": "plans/architect-02.json",
-    "sha256": "8bede3e0b7daecf01212133dee566014df3472bb244fde2fbc09bedf3ef25f1e"
+    "path": "plans/architect-03.json",
+    "sha256": "8e383a4a7ad0982736360cc1ba4be3fcf5d4a29d87fcafc8c5c03169f2044d3c"
   },
-  "summary": "Гибрид C/A1, цикл 2 fix-from-panel: ephemeral serve v2.1.2 с точным wire-контрактом, ask_reject, отдельными readiness/session/watchdog бюджетами, pre-response-headers fallback и sticky transport health; run kill-switch без рестарта. APPROVED означает проектный контракт-кандидат для R2, не council PASS или живую приёмку.",
+  "summary": "Cycle3 a2→a3 fix-from-panel: 6 RW + 8 FU закрыты на уровне архитектурной delta; OPENCODE_DB=:memory:, полный single-turn control, Keep-Alive owner proof, sanitized env и crash leases. APPROVED — кандидат для отдельного Совета a3, не ACCEPT/ARCH_GATE_PASS; Stage3/H0..H9 NOT_RUN.",
   "scope": {
@@ -19,4 +19,4 @@
     "architect_write_allowlist": [
-      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.before.json",
-      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.json",
+      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.before.json",
+      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-03.json",
       ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json"
@@ -33,3 +33,4 @@
       "~/.dsh/** до отдельной rollout-фазы",
-      "общие конфиги opencode/georouter, opencode.db, зависимости/lockfiles"
+      "общие конфиги opencode/georouter, opencode.db, зависимости/lockfiles",
+      "bridges/opencode-zen-bridge/dynamic_config.json не создавать/не коммитить; runtime ~/.dsh JSON только отдельный rollout operator H7"
     ],
@@ -99,4 +100,4 @@
       "priority": "MUST",
-      "statement": "Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\\n` (статус подключения/ожидания модели), независимо от состояния апстрима",
-      "acceptance": "AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме",
+      "statement": "Thinking-enabled non-Google SSE: slow/no-progress request gives visible nonempty [мост] reasoning status with LF by1.0s after SSE open, after grace0.30s; fast model text/reasoning before grace suppresses initial synthetic status. Explicit off/none and JSON never get synthetic reasoning.",
+      "acceptance": "AC-005 scoped per AD-002/CD-001: eligible blank upstream ->first status at0.30..1.0s after initial SSE role flush; real model delta before0.30s ->zero initial status; off/none/JSON ->zero synthetic reasoning. Model bytes immutable, fast Simple greeting. exact. Stall after first token>=15.0s requires heartbeat every15.0s until progress/terminal, bounded by stall watchdog60s.",
       "evidence": "F-36, F-37, F-04, F-33",
@@ -110,3 +111,3 @@
       "statement": "Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее",
-      "acceptance": "AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее",
+      "acceptance": "AC-006: concatenate model-origin deltas after removing synthetic by provenance (not prefix matching) equals model bytes, including literal model [мост]. Leading LF separator belongs entirely synthetic delta. AC-007 reasoning/status never replayed in prompt. Eligible status only per REQ-004; post-token stall threshold/interval15.0s mandatory, does not reset watchdog.",
       "evidence": "F-37, F-38, F-07, F-39",
@@ -760,2 +761,77 @@
       "claim": "14 обязательных RW и7 FU; exact explicit choices для default true, headers barrier, permission selector,MiB/typing; role write allowlist только3 JSON. Исходные расхождения R1 перечислены в panel_resolution_choices, не выданы за единогласное одобрение изменений."
+    },
+    {
+      "id": "EVD-070",
+      "kind": "command",
+      "ref": "Owner-provided host probe in cycle3 brief: (cd bridges/opencode-zen-bridge && python3 -m unittest discover -s tests -p \"test_*.py\" -v)",
+      "claim": "378 tests in122.956s; import errors0; exactly3 original assertion failures in test_step_interruption.py [F-47]..[F-49]. VER-002 achievable from bridge cwd without editing17 other modules. Supplied empirical result, not rerun by Architect.",
+      "measurements": {
+        "tests": 378,
+        "elapsed_s": 122.956,
+        "import_errors": 0,
+        "failures": 3
+      },
+      "status": "OBSERVED_BASELINE_OWNER_SUPPLIED"
+    },
+    {
+      "id": "EVD-071",
+      "kind": "command",
+      "ref": "Owner-provided provider-free opencode v2.1.2 serve isolation spike; binary offsets114651600/122016915",
+      "claim": "OPENCODE_DB=:memory:, standard XDG_DATA_HOME: GET /api/session/active=200 {data:{}} in120.7ms; RSS160544KiB=156.8MiB; lsof0 open .db/SQLite files, common2.27GB DB not opened; auth.json stays readable for opencode-go/*. Empty XDG_DATA_HOME comparator137.9ms/RSS208400KiB=203.5MiB loses auth.json. No Zen call; real provider auth and /api/info response were NOT supplied, remain explicit Stage3 preflight/H3 gates.",
+      "measurements": {
+        "memory_db": {
+          "active_status": 200,
+          "active_body": {
+            "data": {}
+          },
+          "startup_ms": 120.7,
+          "rss_kib": 160544,
+          "rss_mib": 156.8,
+          "open_db_files": 0
+        },
+        "empty_xdg": {
+          "startup_ms": 137.9,
+          "rss_kib": 208400,
+          "rss_mib": 203.5
+        }
+      },
+      "status": "OBSERVED_PROVIDER_FREE_OWNER_SUPPLIED"
+    },
+    {
+      "id": "EVD-072",
+      "kind": "command",
+      "ref": "Owner-provided VER-004 baseline: ruff==0.17.2; basedpyright==1.40.2, cwd bridge + /tmp --project include+absolute extraPaths",
+      "claim": "Full server ruff format --diff:3216 diff lines and immutable _run_env hash1c51b28f…→85c9c344…; forbidden Google slices reformatted, hence changed-hunk range gate required. Root-cwd basedpyright80 errors is wrong import-root. Isolated bridge basedpyright: server3 errors (CATALOG_SOURCE130, optional proc.returncode3665/3666),564 warnings; step test0 import errors,162 warnings. Ruff check: server1E402:67, step test0 errors. New tests/test_realtime_reasoning.py NOT_PRESENT; formatting/typing of that file NOT_RUN until Stage3. Existing step full-format baseline not supplied; record NOT_RUN, do not assert PASS.",
+      "baseline_files": {
+        "server.py": {
+          "ruff_E402": 1,
+          "type_errors": 3,
+          "warnings": 564,
+          "format_diff_lines": 3216
+        },
+        "tests/test_step_interruption.py": {
+          "ruff_errors": 0,
+          "import_errors": 0,
+          "warnings": 162,
+          "format_status": "NOT_RUN_NOT_SUPPLIED"
+        },
+        "tests/test_realtime_reasoning.py": {
+          "status": "NOT_PRESENT"
+        }
+      },
+      "status": "OBSERVED_BASELINE_OWNER_SUPPLIED"
+    },
+    {
+      "id": "EVD-073",
+      "kind": "code",
+      "ref": "PANEL-A2-F-003; read-only binary ~/.opencode/bin/opencode offsets114605908/115254160 verified during cycle3",
+      "claim": "Form.Info={id,sessionID,title,metadata?,fields}; form.created.data.form wraps Info (session id NESTED); form.cancelled.data={id,sessionID}. Form.State pending|answered(answer)|cancelled(message?). source gate filters form.created via data.form.sessionID. Native CLI cancel/interrupt and input.ended.text fallback documented in a2 brief; frozen fixture synthetic, not live interactive success. Form.ID source prefix frm_; fixture uses frm_fixture_1 and one valid string field (key,type; title/required optional).",
+      "status": "SOURCE_VERIFIED_NOT_RUNTIME"
+    },
+    {
+      "id": "EVD-074",
+      "kind": "document",
+      "ref": "PANEL-A2-F-004/PANEL-A2-F-008; cycle3 rework brief",
+      "claim": "Panel-measured lsof68.1ms serial/82.0..88.1ms with6 concurrent calls; budget0.35s, one SPAWN→READY proof then3 HTTP/1.1 Keep-Alive lanes. These are supplied panel measurements, not Architect runtime probe. Hard-kill lease reaper/watchdog and H0/H9 proposed tests NOT_RUN. No owner-confirmed exception supplied; cycle3b compliant default=false/runtime JSON removes need for exception, without claiming consent.",
+      "status": "PANEL_EVIDENCE_DESIGN_PENDING"
     }
@@ -772,3 +848,3 @@
       "source_open_ids": "OPEN-06/08",
-      "statement": "Per-spawn proxy env rotation доказуема AC-018, Zen egress за georouter не определяется child HTTP_PROXY (F-15/F-27). child192MiB — design estimate; временный per-spawn XDG_DATA_HOME устраняет совместное открытие общей DB; фактический RSS/locks проверяет обязательный H3.",
+      "statement": "OPENCODE_DB=:memory: with standard XDG_DATA_HOME preserves auth input and avoids shared DB opening: EVD-071 provider-free120.7ms/156.8MiB/0.db. Actual6parallel RSS/valid provider auth/locks not proven; H3 required. Design combined serve/helper/lsof192MiB per active slot remains estimate, observation<=256MiB is not peak.",
       "status": "ASSUMED",
@@ -777,3 +853,4 @@
         "EVD-020",
-        "EVD-026"
+        "EVD-026",
+        "EVD-071"
       ]
@@ -795,4 +872,4 @@
       "source_open_ids": "OPEN-12/13/14",
-      "statement": "Статусы [мост] разрешены текущим брифом с grace; model bytes не меняем, retries без reasoning dedup.",
-      "status": "VALIDATED",
+      "statement": "Статусы [мост] разрешены текущим брифом с grace; model bytes не меняем, retries без reasoning dedup. Design follows explicit role/rework brief, not independently validated owner decision or executed runtime acceptance. No claim of owner confirmation; verify at Stage3/H gates. Фичефлаг не требует human exception: кодовый default=false, runtime JSON=true только H7 после H3/H6, атомарный false/file removal/disable-file откат. Это архитектурный контракт, runtime NOT_RUN.",
+      "status": "ASSUMED",
       "evidence_ids": [
@@ -805,4 +882,4 @@
       "source_open_ids": "OPEN-02/04",
-      "statement": "Три baseline tests входят в Stage3 текущего брифа: expected spawns/finish/tool_calls согласовать cap3 и fresh per-test resilience.",
-      "status": "VALIDATED",
+      "statement": "Три baseline tests входят в Stage3 текущего брифа: expected spawns/finish/tool_calls согласовать cap3 и fresh per-test resilience. Design follows explicit role/rework brief, not independently validated owner decision or executed runtime acceptance. No claim of owner confirmation; verify at Stage3/H gates.",
+      "status": "ASSUMED",
       "evidence_ids": [
@@ -889,3 +966,12 @@
       "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
-      "owner": "verifier"
+      "owner": "verifier",
+      "baseline": {
+        "evidence_id": "EVD-070",
+        "cwd": "bridges/opencode-zen-bridge",
+        "tests": 378,
+        "elapsed_s": 122.956,
+        "import_errors": 0,
+        "failures": 3,
+        "status": "BASELINE_RED; target full green after allowed3test fixes"
+      }
     },
@@ -911,10 +997,26 @@
       "kind": "command",
-      "command": "python3 - <<'VER004'\nimport collections, json, subprocess\nfrom pathlib import Path\nfiles = ['bridges/opencode-zen-bridge/server.py','bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py','bridges/opencode-zen-bridge/tests/test_step_interruption.py']\nassert all(Path(f).is_file() for f in files), files\nfor args in ([\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"format\",\"--check\",\"--no-cache\",*files], [\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"check\",\"--no-cache\",*files]):\n    subprocess.run(args, check=True)\nb = subprocess.run([\"uvx\",\"--from\",\"basedpyright==1.40.2\",\"basedpyright\",\"--outputjson\",*files], capture_output=True, text=True)\nassert b.returncode in (0,1), b.stderr\nreport = json.loads(b.stdout)\nds = report['generalDiagnostics']\nerrors = [d for d in ds if d['severity'] == 'error']\nassert report['summary']['errorCount'] == 0 and not errors, errors\nlimits = {'reportExplicitAny': 125, 'reportAny': 125, 'reportUnusedCallResult': 39, 'reportUnknownMemberType': 70, 'reportUnknownVariableType': 48, 'reportUnknownArgumentType': 35, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 81, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 3, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}\nserver = Path(files[0]).resolve()\nserver_warnings = [d for d in ds if d['severity']=='warning' and Path(d['file']).resolve()==server]\ncounts = collections.Counter(d.get('rule','') for d in server_warnings)\nassert all(n <= limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n# Both Any rules explicitly retain the frozen server.py ceiling even if absent in output.\nassert counts['reportAny'] <= 125 and counts['reportExplicitAny'] <= 125, dict(counts)\nprint('PASS VER-004: ruff format/check all 3 files, basedpyright 0 errors all 3, server frozen warning budgets',dict(counts))\nVER004",
-      "expected": "exit0; ruff format --check и ruff check на всех3 targetfiles без allowance; basedpyright severity==error ровно0 на всех3. server.py reportAny<=125/reportExplicitAny<=125 и остальные frozen rule warning budgets не растут. Прежние E402/2 type errors EVD052/053 не разрешены новым gate; Coder исправляет в allowlist без type-ignore/disable/изменения конфигов. Stage2 команду не запускает: новый testfile ещё не существует.",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "command": "python3 - <<'VER004'\nimport ast, collections, json, re, subprocess, tempfile\nfrom pathlib import Path\nroot = Path.cwd().resolve()\nbridge = root / 'bridges/opencode-zen-bridge'\nfiles = [bridge/'server.py', bridge/'tests/test_step_interruption.py', bridge/'tests/test_realtime_reasoning.py']\nassert all(f.is_file() for f in files), 'all three target files must exist after Stage3'\nruff = ['uvx','--from','ruff==0.17.2','ruff']\ndef run(args, **kw):\n    return subprocess.run(args, check=True, **kw)\ndef changed_ranges(file):\n    rel = str(file.relative_to(root))\n    diff = subprocess.check_output(['git','diff','--no-ext-diff','--no-color','-U0','origin/dev','--',rel], cwd=root, text=True)\n    # NEW tracked files must be added before final verification; --no-index alternative below covers untracked newfile.\n    result = []\n    for line in diff.splitlines():\n        m = re.match(r'^@@ -\\d+(?:,\\d+)? \\+(\\d+)(?:,(\\d+))? @@', line)\n        if m:\n            start = int(m.group(1)); count = int(m.group(2) or '1')\n            if count: result.append((start, start + count - 1))\n    return result\nranges = {f: changed_ranges(f) for f in files[:2]}\n# New file checked as a whole even before git add. Range gate never formats frozen legacy slices.\nrun([*ruff,'format','--check','--no-cache',str(files[2])], cwd=root)\nfor f in files[:2]:\n    for start, end in ranges[f]:\n        run([*ruff,'format','--check','--no-cache','--range',f'{start}:{end}',str(f)], cwd=root)\n# Full-file lint on all three. Only inherited E402 import site is excepted on server.\nlint = subprocess.run([*ruff,'check','--no-cache','--output-format','json',str(files[0])], cwd=root, capture_output=True, text=True)\nassert lint.returncode in (0,1), lint.stderr\nfindings = json.loads(lint.stdout)\nlines = files[0].read_text().splitlines()\nassert all(x['code']=='E402' and lines[x['location']['row']-1].strip()=='import zen_catalog as zc' for x in findings), findings\nassert sum(x['code']=='E402' for x in findings) <= 1\nrun([*ruff,'check','--no-cache','--extend-ignore','E402',str(files[0])], cwd=root)\nrun([*ruff,'check','--no-cache',str(files[1]),str(files[2])], cwd=root)\n# Exact isolated import-root. No repo pyrightconfig mutation; JSON deleted on every exit.\nproject = None\ntry:\n    with tempfile.NamedTemporaryFile(mode='w',suffix='.json',prefix='zen-ver004-',dir='/tmp',delete=False) as tmp:\n        project = Path(tmp.name)\n        json.dump({'include':[str(f) for f in files], 'extraPaths':[str(bridge.resolve())]},tmp)\n    b = subprocess.run(['uvx','--from','basedpyright==1.40.2','basedpyright','--project',str(project),'--outputjson'], cwd=bridge, capture_output=True, text=True)\n    assert b.returncode in (0,1), b.stderr\n    report = json.loads(b.stdout)\n    ds = report['generalDiagnostics']\n    assert report['summary']['errorCount']==0 and not [x for x in ds if x['severity']=='error'], ds\n    byfile = {f: [x for x in ds if Path(x['file']).resolve()==f] for f in files}\n    limits = {'reportExplicitAny':125,'reportAny':125,'reportUnusedCallResult':39,'reportUnknownMemberType':94,'reportUnknownVariableType':72,'reportUnknownArgumentType':55,'reportUnusedFunction':6,'reportImplicitStringConcatenation':35,'reportUnannotatedClassAttribute':105,'reportUnusedParameter':7,'reportUnnecessaryIsInstance':11,'reportUnknownParameterType':6,'reportMissingParameterType':4,'reportUnreachable':5,'reportImplicitOverride':3}\n    warnings = lambda f: [x for x in byfile[f] if x['severity']=='warning']\n    counts = collections.Counter(x.get('rule','') for x in warnings(files[0]))\n    assert all(n<=limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n    assert len(warnings(files[0]))<=720, len(warnings(files[0]))\n    assert len(warnings(files[1]))<=194, len(warnings(files[1]))\n    # New test file: zero warnings as well as zero errors, thus zero Any.\n    assert not byfile[files[2]], byfile[files[2]]\n    for f in files[:2]:\n        for x in byfile[f]:\n            line = x['range']['start']['line']+1\n            if any(lo<=line<=hi for lo,hi in ranges[f]):\n                assert x.get('rule') not in {'reportAny','reportExplicitAny','reportUnusedCallResult'}, x\n    # Do not introduce Any annotations/type ignores in added code in either legacy file.\n    for f in files[:2]:\n        src = f.read_text().splitlines()\n        for lo,hi in ranges[f]:\n            for line in src[lo-1:hi]:\n                assert not re.search(r'\\bAny\\b|type:\\s*ignore|pyright:\\s*ignore|#\\s*noqa|#\\s*fmt:\\s*off',line), (f,line)\n    print('PASS VER-004: all3 lint/type; legacy changed-range format; newfile whole format; server counts',dict(counts))\nfinally:\n    if project is not None: project.unlink(missing_ok=True)\nVER004",
+      "expected": "exit0 after Stage3. New file full ruff format; legacy added/modified hunks git diff-U0 origin/dev checked via ruff format --check --range start:end. Full lint all3, exactly inherited zen_catalog E402 site only excepted via server-only --extend-ignore E402 (new lint0); no noqa/config edit. Isolated bridge-cwd basedpyright temporary /tmp project, all3 errorCount0; new test0diagnostics/Any; server Any<=125 each, nonAny per-rule+total<=720, step<=194; new changed code0Any/0unused-call-result. Immutable _run_env and both Google function slices enforced separately VER-005. NOT_RUN until new file exists.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox. Run command from repo_root; invokes basedpyright with cwd=absolute bridge and exact temporary include+extraPaths, never root pyrightconfig. origin/dev must exist locally (no implicit fetch); missing ref is FAIL, not empty-range bypass. Delete temporary project in finally.",
       "owner": "verifier",
       "baseline_transition": {
-        "old": "v1 VER-004 разрешал1E402 и2errors server.py и пропускал test_step_interruption.py",
-        "new": "0 lint/format failures,0type errors на каждом из3files; server frozen warning budgets unchanged",
-        "owner": "Stage3 Coder устраняет pre-existing error sites в server.py; Verifier независимо проверяет. Новые Any запрещены, подавлять диагностику ради PASS нельзя."
+        "old": "v2 full-file ruff format changes3216diff lines/frozen hash; root pyright80 errors wrong imports; server564+step162 warnings, server3type errors in isolated config,1E402.",
+        "new": "0 type errors on all3; reachability by lower-case mutable catalog source symbol and explicit proc is not None guards before both returncode uses. Existing import zen_catalog kept; only exact inherited E402 CLI exception, no blanket new E402. Legacy range gate preserves frozen byte slices. NonAny allowance explicit design delta with review a3, Any<=125 retained.",
+        "owner": "Stage3 Coder in three-file allowlist; no test_run_env/start.sh/config edits; independent Verifier runs actual command; stage2 syntax/contract checks only."
+      },
+      "warning_policy": {
+        "baseline": {
+          "server_total": 564,
+          "step_total": 162,
+          "new_test": "NOT_PRESENT"
+        },
+        "server_total_max": 720,
+        "step_total_max": 194,
+        "new_test_total_max": 0,
+        "new_changed_code": {
+          "reportAny": 0,
+          "reportExplicitAny": 0,
+          "reportUnusedCallResult": 0
+        },
+        "rationale": "Server nonAny allowance+156 upper total and targeted per-rule ceilings for strict unknown/narrowing/unannotated members; step allowance+32 for isolated fresh resilience assertions. Explicit no-new-Any and no-unused-call-result in changed code; new tests zero diagnostics. Unlisted server rules0. Total cap remains even if per-rule sum greater. This is proposed architecture budget delta for a3, not silently frozen v2 ceiling; no type/lint suppression."
       }
@@ -946,5 +1048,32 @@
       "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
-      "expected": "exit0; exact frozen-v2.1.2 FakeServe fixture digest+negative mutations, delivery/concurrent reject, ask_reject/deny и _run_env hash, listener takeover zero leakage, budgets51.6, separate first_event20/readiness3, file kill-switch, ServeHealth3/TTL120 independent breaker, synthetic leading LF provenance, XDG cleanup, all prior tools/timing/lifecycle/resilience assertions. Implementation NOT_RUN Stage2.",
+      "expected": "exit0, both independent GroupA and GroupB. All prior v2 oracles retained except explicitly superseded isolation/format/warning choices. GroupA no FakeServe; GroupB six frozen fixture families with nested form paths, complete JSON args fallback, reject/cancel+interrupt and zeroStep2; secret sentinels all3env branches; in-memory DB/auth;1lsof then persistent lanes; crash helper+startup reaper; fallback table counter oracle;15s stall heartbeat; 46keys/24gates; immutable raw function hashes; thread/FD/aux math. NOT_RUN Stage2. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN.",
       "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
-      "owner": "verifier"
+      "owner": "verifier",
+      "groups": {
+        "A": {
+          "name": "RC-2/RC-3 watchdog & killpg",
+          "stage": "3a",
+          "test_class": "TestLegacyWatchdogAndKillpg",
+          "command": "cd bridges/opencode-zen-bridge && python3 -m unittest tests.test_realtime_reasoning.TestLegacyWatchdogAndKillpg -v",
+          "dependencies": "FakeCLI only; never instantiate FakeServe; independent legacy supervisor/status/cap3/O-EXIT/baseline errors tests. Stdlib discover executes class.",
+          "status": "NOT_RUN"
+        },
+        "B": {
+          "name": "Serve transport & FakeServe",
+          "stage": "3b",
+          "test_class": "TestServeTransportAndFakeServe",
+          "command": "cd bridges/opencode-zen-bridge && python3 -m unittest tests.test_realtime_reasoning.TestServeTransportAndFakeServe -v",
+          "dependencies": "Frozen six-family fixtures; transport/env/listener/crash/fallback/health+normal resource oracles. Group A PASS precondition; failures identify own group immediately. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN.",
+          "status": "NOT_RUN"
+        }
+      },
+      "immutable_google_slices": {
+        "source": "git show origin/dev:bridges/opencode-zen-bridge/server.py",
+        "symbols": [
+          "_stream_google_sse",
+          "_execute_google_once"
+        ],
+        "method": "ast FunctionDef/AsyncFunctionDef lineno..end_lineno inclusive over raw bytes splitlines(keepends=True), including terminal LF; compare byte-identical with baseline for each function, not AST-equivalence; current frozen _run_env literal digest also mandatory."
+      },
+      "orphan_oracles": "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN."
     }
@@ -961,3 +1090,6 @@
         "B: прямой HTTP Zen — меньше ресурсов, но 429 F-24/F-25 и нет подтверждённого client context; не выбирается без PoC.",
-        "L: только run watchdog/status — минимален, но не устраняет RC-1."
+        "L: только run watchdog/status — минимален, но не устраняет RC-1.",
+        "OPENCODE_DB=:memory: selected (EVD-071120.7ms/156.8MiB/0.db), preserves standard read-only auth.json; empty XDG_DATA_HOME137.9ms/203.5MiB breaks opencode-go auth unless explicitly passed read-only. Shared DB + _StartupGate rejected: shared mutation/locks violate frozen scope; no automatic fallback to that option.",
+        "--port 0 + stdout port announcement considered: child picks own port but stable versioned stdout announcement not evidenced; would require new bounded parser/ownership proof. Choose parent-reserved ephemeral port + one lsof + persistent lanes; port race remains fail-closed with cap3.",
+        "Two independent deliveries3a then3b considered per analyst§4. Stage3a: RC-2/RC-3 watchdog/status/killpg, baseline tests/O-EXIT/VER004 debt; Stage3b: serve behind selector. Chosen one feature branch and eventual MR to meet owner request «реалтайм размышления... доводи дело до мра», but implementation/verification staged3a→3b and Group A must pass without FakeServe. Separate future MR for3a possible only by owner scope decision; no new delivery promised here."
       ],
@@ -976,4 +1108,4 @@
         "Откат флага/режима без миграций; публичная форма ответов неизменна.",
-        "Новый процесс получает временный XDG_DATA_HOME: история/SQLite изолированы на попытку и удаляются в finally; общий opencode.db не открываем намеренно.",
-        "Default=true разрешён текущим rework-brief; production sync лишь после изолированного H3. Файл disable-serve удерживает боевой run до приёмки."
+        "Per-attempt in-memory SQLite via OPENCODE_DB=:memory:, standard XDG_DATA_HOME preserves auth; isolated owned zen-serve-state-* dirs/lease removed after kill/reap. No shared DB opens/writes.",
+        "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git."
       ],
@@ -995,3 +1127,8 @@
         "EVD-063",
-        "EVD-064"
+        "EVD-064",
+        "EVD-070",
+        "EVD-071",
+        "EVD-072",
+        "EVD-073",
+        "EVD-074"
       ],
@@ -1009,4 +1146,4 @@
           "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": {
-            "default": true,
-            "purpose": "В auto нативный Mach-O opencode сразу использует serve после разрешённой синхронизации server.py; start.sh неизменен. Явные 0/false выключают optional serve ветвь первой инструкцией."
+            "default": false,
+            "purpose": "Существующий env override: явные 0/false/no/off принудительно run; явные 1/true включают auto serve при native OPENCODE_BIN. Отсутствующий override использует boolean REALTIME_SERVE_ENABLED из DYNAMIC_CONFIG_PATH с кодовым default=false. Новые env не добавляются; start.sh заморожен."
           },
@@ -1019,3 +1156,3 @@
             "default": "auto",
-            "precedence": "REALTIME_SERVE_ENABLED=0/false или TRANSPORT=run -> run до stat/probe/allocations; затем существующий disable-file -> run; затем auto ServeHealth + shebang eligibility; иначе serve. Force serve обходит только shebang/health auto routing для FakeServe и диагностики, но не disable-file, выключенный флаг или security. Force serve errors явные, без silent fallback. Invalid value -> config error."
+            "precedence": "1) TRANSPORT=run OR существующий env OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED в {0,false,no,off} OR disable-serve по OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE OR открытый sticky TTL _ServeHealth ->строго run. Явный env/run guard раньше stat/serve allocations; файл и health до subprocess. 2) TRANSPORT=serve ->serve, даже при кодовом default=false, но не обходит пункт1/security; ошибки явные, без silent run fallback. 3) TRANSPORT=auto ->serve iff runtime boolean REALTIME_SERVE_ENABLED=true (либо env=1/true) AND OPENCODE_BIN подтверждён native opencode (не текстовый #! fake, кроме явного test-only override). Иначе прежний run --format json. Невалидный TRANSPORT ->config error."
           },
@@ -1035,10 +1172,18 @@
           "SERVE_SESSION_SETUP_TIMEOUT_S": 2.0,
-          "feature_flag_context": "Текущий explicit cycle-2 brief RW-009 разрешает default=true в локальном stdlib-мосте (прецеденты STEP_RECOVERY=1 и F-40), вместо общего GigaRC default=false. Новых dependencies/GigaRC/start.sh/env propagation не добавлять. Disable-file обеспечивает live kill-switch без рестарта; H3 обязателен до production rollout."
+          "feature_flag_context": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git.",
+          "DYNAMIC_CONFIG_PATH": {
+            "value": "Path(__file__).resolve().parent / \"dynamic_config.json\"",
+            "key": "REALTIME_SERVE_ENABLED",
+            "type": "bool",
+            "default": false,
+            "reload": "На каждый новый запрос os.stat O(1), кэш по (st_mtime_ns, st_size), с учётом identity DYNAMIC_CONFIG_PATH для изолированных тестов. При неизменной паре без переоткрытия/JSON parsing; смена пары перечитывает bounded локальный JSON и публикует boolean snapshot под lock. Удаление, ошибка stat/read, битый JSON, неверный root или небулево значение ->false немедленно, без stale true. Ошибки чтения/валидации дают diagnostic warning без содержимого файла/секретов; повторяющийся warning ограничен, чтение ошибки можно повторить на следующем запросе. Не нужен restart Server/LaunchAgent.",
+            "write": "Только rollout operator: tempfile в том же каталоге, mode0600, JSON boolean, os.replace атомарно; только после H3/H6 на H7. Локальный production файл ~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json вне git; Architect его не создаёт."
+          }
         },
-        "auto_fake_compatibility": "Auto: до любых serve allocations выполнить env/run/disable-file/health guards; затем cached stat+first bytes executable. Shebang #! или текстовый launcher -> run сразу, без --help/--version/serve subprocess. Это сохраняет 378 fake-CLI baseline tests при новом default=true, включая basename opencode; не проверять имя теста/FAKE_OC_MODE. Native Mach-O -> owned serve readiness. Eligibility/protocol metadata cache key=(resolved executable path,mtime_ns,size); смена ключа инвалидирует старую capability и transport health. Force serve обходит shebang для FakeServe, stdin=DEVNULL предотвращает stdin.read hang. false/run/disable-file spies: zero serve UUID/password/threads/probes/extra Popen; stat file разрешён только enabled selector.",
-        "spawn": "На каждую реальную попытку общий _RequestAttempts/slot, единый admission deadline<=5.0s для _SpawnRateLimiter+_StartupGate (не два ожидания по5s), свежий _serve_env(model_id) поверх одного неизменного _run_env(model_id), новая per-spawn _next_standalone_proxy запись. Parent socket.bind((127.0.0.1,0)), getsockname()[1]; держать резерв до непосредственно Popen, затем close reserve и Popen([OPENCODE_BIN,serve,--hostname,127.0.0.1,--port,str(port)],stdin=DEVNULL,start_new_session=True,close_fds=True), сохранить child_pgid. Prompt/Basic password не передавать argv/stdin. До первого Authorization или prompt доказать owner listener по listener_ownership; при port race cleanup + новый порт только в оставшемся ready deadline, каждый новый Popen расходует общий cap3 и spawn token. Ни одного бесплатного spawn при EADDRINUSE.",
+        "auto_fake_compatibility": "В git-клоне bridges/opencode-zen-bridge/dynamic_config.json отсутствует и не коммитится; default=false гарантирует прежний run для всех378 fake-CLI baseline tests REQ-003/AC-004, без опоры на shebang/имя теста/FAKE_OC_MODE. При explicit enabled auto дополнительно cached executable path+mtime_ns+size/first bytes: shebang/text ->run без --help/--version/serve subprocess; native opencode ->serve. Явный test-only eligibility override допустим только fixtures; force serve для FakeServe сохраняет первый kill-switch приоритет и stdin=DEVNULL. Explicit env false/run ->zero serve UUID/password/queue/threads/probes/Popen до file stat; default=false selector допускает только O(1) config stat, без serve allocations. При смене executable cache key старые capability/health инвалидируются.",
+        "spawn": "На каждую реальную попытку общий _RequestAttempts/slot, единый admission deadline<=5.0s для _SpawnRateLimiter+_StartupGate (не два ожидания по5s), свежий _serve_env(model_id) поверх одного неизменного _run_env(model_id), новая per-spawn _next_standalone_proxy запись. Parent socket.bind((127.0.0.1,0)), getsockname()[1]; держать резерв до непосредственно Popen, затем close reserve и Popen([OPENCODE_BIN,serve,--hostname,127.0.0.1,--port,str(port)],stdin=DEVNULL,start_new_session=True,close_fds=True), сохранить child_pgid. Prompt/Basic password не передавать argv/stdin. До первого Authorization или prompt доказать owner listener по listener_ownership; при port race cleanup + новый порт только в оставшемся ready deadline, каждый новый Popen расходует общий cap3 и spawn token. Ни одного бесплатного spawn при EADDRINUSE. Apply serve_env_sanitization to ALL3 branches and data_isolation; keep standard XDG_DATA_HOME, set OPENCODE_DB=:memory:. Register crash-safe lease before readiness/auth and arm parent-death watchdog before admitting prompt, see crash_recovery. lsof owned helper once per successful spawn, not model attempt; no extra model Popen.",
         "startup": "SERVE_READY_TIMEOUT_S=3.0s (ready_budget_s=3.0): после owner proof лёгкий authenticated GET /api/session/active, HTTP200 + $.data object map of active sessions (empty={}); не качать 281KB /openapi.json на каждом spawn. Control I/O slices<=.25s, всего<=3 readiness TCP probes, remaining request deadline/cancel всегда проверяются. Child EOF/no listener/incompatible protocol -> ServeUnavailable. Пароль secrets per spawn в OPENCODE_SERVER_PASSWORD ПОСЛЕ whitelist, Basic opencode:<password>, никогда в argv/URL/log. stdout/stderr bounded drain+redact. HTTP на loopback напрямую без proxy/redirects. Readiness не устанавливает first_event_ms и не сбрасывает first_event/token часы.",
-        "fallback_barrier": "State machine: ADMISSION -> SPAWN/OWNER/READY -> CREATE/SUBSCRIBE -> PROMPT_SENDING -> DELIVERED -> TERMINAL -> CLEANUP. Auto ServeUnavailable на старте/create/subscribe или до получения HTTP response headers POST /api/session/{id}/prompt допускает один budgeted run fallback, ТОЛЬКО если не было валидного события исполнения созданной session после начала отправки prompt, нет model/tool output, auth/security failure, cancel или deadline. Перед run полностью close/join/killpg/reap старую attempt, удалить temp data; новый Popen требует тот же retry token/Full Jitter/attempt ceiling<=3. С первого response header POST /prompt (любой status) ИЛИ первого session execution event после prompt delivery лачится DELIVERED=true; silent fallback и переключение на run для текущего запроса запрещены, включая отсутствие response body и headers-pending+SSE-started. Prompt POST исполняется daemon worker параллельно SSE; до header/события ожидание ограничено остатком first_event20s/first_token60s и total deadline. Даже до headers неизвестная доставка может дать повторную генерацию: допустимость этой границы явно задана текущим brief RW-001, это НЕ exactly-once; старый PGID должен быть убран до fallback, built-ins никогда allow. После barrier watchdog может выполнить только явный общий retry того же транспорта с retry-status/cleanup/cap, не скрытый run fallback. HTTP401/403/auth/permission/capability-security denial -> fail-closed без fallback/auto policy switching на любой фазе.",
-        "session_flow": "После listener proof/readiness и подтверждения safe permission capability POST /api/session по session_wire.create; затем GET /api/event с HTTP200 text/event-stream и reader armed ДО отправки первого байта тела prompt. На create + subscribe один SERVE_SESSION_SETUP_TIMEOUT_S=2.0s, не включая model generation или ожидание POST /prompt response. Передать полный prompt в JSON body через единственный daemon delivery worker, одновременно читать SSE в owned reader; supervisor/SSE writer не ждут блокирующий POST и остаются cancel-aware. Один POST /prompt с delivery=steer,resume=true; transport HTTP headers/ошибки передаются supervisor как control events. First-event/token часы якорятся на prompt_send_start, не на HTTP ready/создание сессии. Filter data.sessionID==created_sid; реальные v2 события не содержат executionID, поэтому использовать own per-attempt session + prompt-send generation latch, event id дедуп и assistantMessageID step key, не выдумывать executionID. server.connected/session.created/global updates/pre-prompt events не считаются first execution. Terminal success/failed независим от text end; EOF без terminal -> protocol failure. step.ended с готовым DSH tool call -> остановить дальнейшее исполнение/cleanup.",
-        "tool_policy": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
+        "fallback_barrier": "State machine: ADMISSION -> SPAWN/OWNER/READY -> CREATE/SUBSCRIBE -> PROMPT_SENDING -> DELIVERED -> TERMINAL -> CLEANUP. Auto ServeUnavailable на старте/create/subscribe или до получения HTTP response headers POST /api/session/{id}/prompt допускает один budgeted run fallback, ТОЛЬКО если не было валидного события исполнения созданной session после начала отправки prompt, нет model/tool output, auth/security failure, cancel или deadline. Перед run полностью close/join/killpg/reap старую attempt, удалить temp data; новый Popen требует тот же retry token/Full Jitter/attempt ceiling<=3. С первого response header POST /prompt (любой status) ИЛИ первого session execution event после prompt delivery лачится DELIVERED=true; silent fallback и переключение на run для текущего запроса запрещены, включая отсутствие response body и headers-pending+SSE-started. Prompt POST исполняется daemon worker параллельно SSE; до header/события ожидание ограничено остатком first_event20s/first_token60s и total deadline. Даже до headers неизвестная доставка может дать повторную генерацию: допустимость этой границы явно задана текущим brief RW-001, это НЕ exactly-once; старый PGID должен быть убран до fallback, built-ins никогда allow. После barrier watchdog может выполнить только явный общий retry того же транспорта с retry-status/cleanup/cap, не скрытый run fallback. HTTP401/403/auth/permission/capability-security denial -> fail-closed без fallback/auto policy switching на любой фазе. Authoritative phase/event/counter table: fallback_decision_table. first_event20 preheader/noevent ->budgeted fallback_to_run; after anyheader ->explicit serve_retry. Error headers latch barrier before HTTP classification.",
+        "session_flow": "После listener proof/readiness и подтверждения safe permission capability POST /api/session по session_wire.create; затем GET /api/event с HTTP200 text/event-stream и reader armed ДО отправки первого байта тела prompt. На create + subscribe один SERVE_SESSION_SETUP_TIMEOUT_S=2.0s, не включая model generation или ожидание POST /prompt response. Передать полный prompt в JSON body через единственный daemon delivery worker, одновременно читать SSE в owned reader; supervisor/SSE writer не ждут блокирующий POST и остаются cancel-aware. Один POST /prompt с delivery=steer,resume=true; transport HTTP headers/ошибки передаются supervisor как control events. First-event/token часы якорятся на prompt_send_start, не на HTTP ready/создание сессии. Filter data.sessionID==created_sid; реальные v2 события не содержат executionID, поэтому использовать own per-attempt session + prompt-send generation latch, event id дедуп и assistantMessageID step key, не выдумывать executionID. server.connected/session.created/global updates/pre-prompt events не считаются first execution. Terminal success/failed независим от text end; EOF без terminal -> protocol failure. step.ended с готовым DSH tool call -> остановить дальнейшее исполнение/cleanup. Include nested form.created.data.form.sessionID filtering before flat session filter. Mandatory reject/cancel then interrupt single_turn_control; never wait on prompt POST, never stream Step2.",
+        "tool_policy": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6. _run_env does NOT sanitize every branch; _serve_env must apply serve_env_sanitization to all3 branches. Mandatory form.created→cancel and reject/cancel→immediate interrupt single_turn_control; JSON args fallback input.ended.data.text when called absent; no second-step output.",
         "event_contract": {
@@ -1048,6 +1193,6 @@
           "session.step.ended": "$.data.tokens input/output/reasoning + $.data.tokens.cache.read -> canonical input/output/reasoning/cached; один учёт по $.data.assistantMessageID, terminal не удваивает usage.",
-          "session.tool.*": "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side.",
+          "session.tool.*": "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side. On input.ended save $.data.text and parse JSON as object with runtime validation. Prefer called.data.input if present and valid; if called absent before failed/step.ended use completed input.ended.text, including streaming→failed. Never emit partial JSON; dedup by sessionID/assistantMessageID/call id. Both paths give identical mapped DSH tool_calls. Invalid JSON follows existing incomplete/unmapped recovery, not invented empty args.",
           "session.step.failed / session.execution.failed": "$.data.error {type,message,status?,response?,retryAfterMs?} ->canonical error{statusCode,message}: statusCode=$.data.error.status если integer100..599; иначе explicit known type mapping provider.free-limit429/auth401/permission denial403, unknown null. Terminal independent, one cause not counted twice.",
           "session.execution.succeeded": "terminal success metadata, не text/reasoning; гарантированно дренировать уже полученный step.ended перед финальным usage.",
-          "other": "first_event latch только валидный execution/step/reasoning started текущей session после prompt; валидные current-session model delta также доказывают начало исполнения. server.connected, HTTPready, session.created, чужие session/control/comments/status не latch и не model token.",
+          "other": "first_event latch только валидный execution/step/reasoning started текущей session после prompt; валидные current-session model delta также доказывают начало исполнения. server.connected, HTTPready, session.created, чужие session/control/comments/status не latch и не model token. form.created session lookup is nested data.form.sessionID; shared flat filter must special-case this valid envelope before discard.",
           "payload_validation": "Проверять exact field paths/types и mandatory sessionID до emit. Текущая schema shape mismatch -> invalid_serve_event (не пустая полезная delta), отдельный ServeHealth; permission capability mismatch ->security fail-closed. Incremental UTF8/CRLF/multiline SSE/comments/fragment boundaries, byte budgets как прежде. Никакого Coder-discovered protocol или aliases, которых нет в frozen source. Coder и FakeServe используют frozen expected независимо; мутации delta path/token/permission должны краснить тест даже если adapter и mock согласованно ошибочны.",
@@ -1293,2 +1438,76 @@
               "note": "provider.free-limit ->429; provider.auth/permission denial ->fatal401/403; неизвестный type сохраняется как явная ошибка с statusCode=null, не выдумывать retryability. step.failed + execution.failed одной cause дедуп без потери terminal. Numeric wire key status, not statusCode/data.statusCode; source Session.StructuredError. Missing numeric status allowed as in captured free-limit event."
+            },
+            "form.created / form.cancelled": {
+              "wire": {
+                "id": "evt_fixture_form_1",
+                "created": 1792957431012,
+                "type": "form.created",
+                "data": {
+                  "form": {
+                    "id": "frm_fixture_1",
+                    "sessionID": "ses_fixture_1",
+                    "title": "Question",
+                    "fields": [
+                      {
+                        "key": "answer",
+                        "type": "string",
+                        "title": "Question",
+                        "required": true
+                      }
+                    ]
+                  }
+                }
+              },
+              "field_paths": {
+                "session_id": "$.data.form.sessionID",
+                "form_id": "$.data.form.id",
+                "info": "$.data.form",
+                "state": "Form.State=pending; Form.Info has no state field"
+              },
+              "cancel": {
+                "method": "POST",
+                "path": "/api/session/ses_fixture_1/form/frm_fixture_1/cancel",
+                "body": null,
+                "success": "HTTP2xx empty success; protocol preflight freezes exact success response from used endpoint schema; no fabricated reply/body"
+              },
+              "cancelled_wire": {
+                "id": "evt_fixture_form_2",
+                "created": 1792957431013,
+                "type": "form.cancelled",
+                "data": {
+                  "id": "frm_fixture_1",
+                  "sessionID": "ses_fixture_1"
+                }
+              },
+              "state_schema": {
+                "pending": {
+                  "status": "pending"
+                },
+                "answered": {
+                  "status": "answered",
+                  "answer": {}
+                },
+                "cancelled": {
+                  "status": "cancelled",
+                  "message": "optional string"
+                }
+              },
+              "canonical": {
+                "etype": "control_only",
+                "emit_model_text": false,
+                "actions": [
+                  "suppress Step2 immediately",
+                  "cancel via control<=0.25s",
+                  "interrupt own session",
+                  "return accumulated mapped tool_calls or existing recovery"
+                ]
+              },
+              "negative_mutations": [
+                "flatten form.sessionID to data.sessionID -> reject invalid event, no foreign cancel",
+                "missing form.id/fields/title ->invalid_serve_event",
+                "foreign nested sessionID ->ignore",
+                "form.cancelled wrong id/session ->not own success",
+                "cancel endpoint failure ->fail-closed, no permission allow or Step2 output"
+              ],
+              "provenance": "EVD-073 source schema; synthetic ids/titles/empty fields, not observed runtime cancellation"
             }
@@ -1298,6 +1517,8 @@
             "binary_sha256": "b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c",
-            "examples": "Пять минимальных семейств, synthetic ids/timestamps/texts; field/type schema extracted from binary, не live business/permission evidence.",
+            "examples": "Six source-schema families; synthetic ids/timestamps/texts, Form.Info wrapper verified EVD-073; no live tool success asserted.",
             "immutable_oracle": "В Stage3 fixture literals копируются в tests/test_realtime_reasoning.py; до adapter expectations сверить fixture canonical SHA256 с пакетным fingerprint. Менять fixture по реализации запрещено."
           },
-          "frozen_fixture_sha256": "896ae246586487a179d3be99947cc8455ed069a6e98b8b8628690158a1a80ac2"
+          "frozen_fixture_sha256": "12456f8b4568c3f3b4c52677118748faf80512f376b2b1b2f467226ff94a1f38",
+          "form.created / form.cancelled": "form.created uses data.form.sessionID/id (Form.Info nested); validate own session before action. Cancel immediately via POST /api/session/{id}/form/{formID}/cancel, no answer/allow; form.cancelled data.id/sessionID settles same form. Not a model token/first-event. Error->security fail-closed+kill. See single_turn_control.",
+          "fixture_digest_serialization": "UTF-8 json.dumps(frozen_v2_1_2_fixtures,ensure_ascii=False,sort_keys=True,separators=(\",\",\":\")); no trailing LF"
         },
@@ -1306,9 +1527,12 @@
           "protocol": [
-            "bind 127.0.0.1:0 -> getsockname -> release immediately before Popen explicit port/new PGID",
-            "Дождаться LISTEN без HTTP/Authorization; bounded lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp, только loopback listener PID, проверить os.getpgid(listener_pid)==child_pgid и child lease ещё жив. Несколько PID/ошибка lsof/PGID mismatch не являются успехом.",
-            "Проверка до первого Auth и повторно до отправки Auth на каждом новом TCP соединении; no redirects/no env proxy, connect только 127.0.0.1. Не доверять readiness чужого процесса.",
-            "Mismatch/EADDRINUSE -> abort attempt, ноль байт секрета/промпта чужому listener; закрыть собственный child/PGID, не посылать interrupt/delete чужому listener и не убивать чужой PID. Retry reserve/spawn только при remaining ready>0, admission/spawn token/cap соблюдены."
+            "Parent reserves127.0.0.1:0; release immediately before Popen explicit --port; saved child PGID. No Auth/prompt until proof.",
+            "SPAWN→READY after port LISTEN: exactly once lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp, timeout0.35s; one listener_pid, os.getpgid(listener_pid)==child_pgid and proc.poll() is None. Mismatch/ambiguous/timeout counts _ServeHealth failure, zero secret bytes.",
+            "After proof establish/retain3 HTTP/1.1 Keep-Alive connections: control, SSE, prompt. Loopback direct, redirects/proxy disabled. Before each authenticated request proc.poll() is None; never lsof in permission/form/interrupt/DELETE hot path.",
+            "Cached proof bound to exact live child lease + sockets, never globally port-only. On dead proc close lanes and fail-closed, no Auth to replacement listener. On control disconnect one explicit reconnect with fresh proof<=0.35s before Auth; not transparent retry of sent request, no prompt replay. SSE/prompt disconnect closes attempt (no transparent reconnect).",
+            "Reconnect is separate recovery budget outside fast control SLA; pending urgent permission/form cannot wait0.35s while claiming<=0.25s: terminate attempt fail-closed and kill own PGID. Cleanup never reconnects; broken control skips API and uses group kill.",
+            "Foreign listener/PGID: no API or signals to foreign PID. Only own child cleanup; retry new port allowed within original ready3s/admission/cap3. lsof helper has own bounded PID lifecycle."
           ],
-          "owner_probe_timeout_s": 0.25,
-          "ready_deadline_includes": "bind/spawn/owner probe, лёгкий authenticated GET /api/session/active и cache-miss protocol check вместе <=3.0s; retry port не продлевает deadline",
+          "owner_probe_timeout_s": 0.35,
+          "reconnect_budget_s": 0.35,
+          "ready_deadline_includes": "lsof+keepalive setup+GET active and cache-miss protocol projection all within3.0s; repeated port attempt does not reset it.",
           "verification_ids": [
@@ -1324,4 +1548,4 @@
           ],
-          "handshake": "На первом owned serve данного binary key один lightweight authenticated GET /api/info: JSON version==2.1.2 и pid с PGID==owned child group, затем один bounded GET /openapi.json<=512KiB; обе операции внутри того же aggregate ready_budget_s=3.0. OpenAPI.info.version==0.0.1 — версия API schema, НЕ версия CLI; не сравнивать её с2.1.2. Exact required-schema projection по Model.Ref, Permission.Ruleset, PromptInput, TokenUsage.Info/StructuredError/Event fixtures обязателен. Успешно сохранить app version+SHA256 raw OpenAPI+schema projection keyed(path,mtime_ns,size). Остальные spawn этого key только GET /api/session/active плюс PID/PGID ownership, без OpenAPI download и без --version Popen. Version/schema mismatch до prompt ->ServeUnavailable/_ServeHealth; permission capability gap ->security fail-closed.",
-          "invalidation": "mtime_ns/size/path change или fail exact projection -> invalidation; неизвестная patch/schema не считается compatible по одному наличию endpoint. Для новой версии нужен обновлённый подтверждённый fixture/Architect delta. Отсутствие безопасного permission endpoint — security failure, без run fallback.",
+          "handshake": "On changed executable stat key invalidate cache and revalidate owned child /api/info version+pid and bounded /openapi.json<=512KiB inside ready3s. app version2.1.2 is reference, NOT equality-only reject gate. Permit changed binary version/mtime iff canonical required-endpoints/schema/event projection hash equals validated reference projection. API info.version0.0.1 distinct. Required projection includes Model.Ref,Permission.Ruleset,PromptInput,TokenUsage/StructuredError,Form.Info/State and six fixture families + all used methods/path parameter schemas. No permission endpoint ->security fail-closed; benign other projection mismatch ->ServeUnavailable before prompt.",
+          "invalidation": "mtime/size/path invalidate capability cache, not permanent ban. Same projection hash after recheck keeps serve, differing used schema routes new auto to run with explicit diagnostic reason. No accept-by-version-string alone; reference normalized projection freeze in first provider-free Stage3 preflight before enable. Arbitrary old raw hash is not a projection hash; never invent a digest.",
           "fixture_source_evidence_ids": [
@@ -1330,3 +1554,5 @@
           ],
-          "cache_ownership": "Per-Server bounded capability record (only executable key/version/schema hashes/projection, no password/session/prompt). Один fill-owner на binary key; конкурентные fills ждут только remaining own ready3s без блокировки writer, owner cancellation снимает in-flight; никаких live sockets/passwords в cache. Это setup capability metadata, не ControlPlane/Snapshot polling."
+          "cache_ownership": "Per-Server bounded capability record (only executable key/version/schema hashes/projection, no password/session/prompt). Один fill-owner на binary key; конкурентные fills ждут только remaining own ready3s без блокировки writer, owner cancellation снимает in-flight; никаких live sockets/passwords в cache. Это setup capability metadata, не ControlPlane/Snapshot polling.",
+          "projection_freeze": "VER-005 independent expected fixtures anchor required field semantics; first provider-free preflight records normalized projection SHA256 from verified2.1.2 endpoint response; subsequent binary keys compare that immutable in-process reference. If no verified reference exists, exact fixture projection validation is mandatory before recording reference. New binary alone cannot self-certify expected schema. No new repo config/artifact outside allowlist.",
+          "telemetry": "REQ-016/AC-021 explicitly authorize transport,first_event_ms,ttft_ms in O-EXIT/v1. Preserve existing keys/types and one-exit cardinality; no incompatible rename. Fallback reason and transport-history details may be adjacent bounded redacted BRIDGE-TRANSPORT/v1 diagnostic correlated by existing request id, so strict O-EXIT parsers remain valid. Log selected transport=serve|run and reason for stat/schema/degraded/disable fallback; /health unchanged."
         },
@@ -1395,3 +1621,4 @@
             "request_id_path": "$.data.id of permission.asked; session path id=$.data.sessionID",
-            "note": "Wire key decision, не reply; permission.replied notification содержит reply=reject. Никогда once/always/allow."
+            "note": "Wire key decision, не reply; permission.replied notification содержит reply=reject. Никогда once/always/allow.",
+            "after_reply": "Immediately interrupt own session; barrier latched before reply; Step2 suppressed."
           },
@@ -1400,3 +1627,7 @@
             "delete": "DELETE /api/session/{id}",
-            "aggregate_api_budget_s": 0.2
+            "aggregate_api_budget_s": 0.2,
+            "connection_policy": "Use existing proven Keep-Alive control only; no lsof/reconnect. If unavailable skip API, kill owned PGID; do not add0.35s reconnect into0.20s API budget.",
+            "interrupt_each_s": 0.09,
+            "delete_each_s": 0.09,
+            "scheduling_margin_s": 0.02
           },
@@ -1420,2 +1651,11 @@
             "note": "Пример pid placeholder только в документации, wire integer; owner PGID проверяется до Auth независимо от self-reported pid. appversion2.1.2 отличается от OpenAPI.info.version0.0.1. Once per executable stat key, withinready3s."
+          },
+          "form_cancel": {
+            "method": "POST",
+            "path": "/api/session/{id}/form/{formID}/cancel",
+            "body": null,
+            "form_id_path": "$.data.form.id",
+            "session_id_path": "$.data.form.sessionID",
+            "timeout_s": 0.25,
+            "on_error": "fail-closed+kill own PGID; never reply/answer to question"
           }
@@ -1423,5 +1663,12 @@
         "data_isolation": {
-          "XDG_DATA_HOME": "На каждый serve spawn tempfile.mkdtemp(prefix=\"zen-serve-data-\") в локальном temp вне репозитория/Drive; env[\"XDG_DATA_HOME\"]=каталог. OPENCODE_MODELS_PATH сохраняется из _run_env, не терять standalone model catalog. Не копировать/не мигрировать/не редактировать общую ~/.local/share/opencode/opencode.db (2.27 GB, F-28).",
-          "ownership": "Путь принадлежит attempt lease; child создаёт собственный SQLite. После kill/reap и закрытия readers в finally shutil.rmtree(temp_data_dir,ignore_errors=True), на каждом exit, including spawn exception/port race/setup/auth/cancel/terminal. Cleanup idempotent; директории чужих attempts не трогать.",
-          "cleanup_budget": "Входит в aggregate cleanup<=1.2s. Реальный FS cleanup/RSS/DB locking проверяются H3; превышение запрещает enable, не выдавать ignore_errors за доказанное удаление.",
+          "selected": "env[\"OPENCODE_DB\"] = \":memory:\" for every serve spawn; never use shared opencode.db/opencode-next.db. EVD-071 calibrates ready3.0s with120.7ms,156.8MiB<=256MiB and0 open SQLite files.",
+          "XDG_DATA_HOME": "Preserve effective standard XDG_DATA_HOME from trusted base env (unset retains HOME default). Do not overwrite with empty directory: opencode-go/* must read standard opencode/auth.json. Shared auth file is read-only input; do not write/copy/log credentials. No readonly bind mount/symlink changes to owner filesystem.",
+          "state_and_workdir": "Allocate one owned tempfile.mkdtemp(prefix=\"zen-serve-state-\") per attempt, with state/ and tmp/ subdirectories. Set XDG_STATE_HOME and TMPDIR to those paths. Popen cwd may use owned dir, but POST session location.directory remains existing request workdir; no silent change to tool-relative paths. Parent lease records exact temp root.",
+          "catalog_and_auth": "Preserve OPENCODE_MODELS_PATH, generated OPENCODE_CONFIG/OPENCODE_CONFIG_CONTENT and provider settings from exactly one _run_env call, sanitized below on all3 branches; auth.json remains visible for glm-5.1,kimi-k2.5,minimax-m2.5,minimax-m2.7 via opencode-go/*. Provider-free accessibility is not proof of valid live provider credential (H3/H6).",
+          "alternatives": {
+            "empty_XDG_DATA_HOME": "Rejected for default: loses auth.json despite preserving models. If explicitly isolated later, read-only auth propagation must be separately verified without shared DB access.",
+            "shared_DB_plus_StartupGate": "Rejected: violates no shared DB mutation/lock boundary; cannot use as fallback without owner scope approval."
+          },
+          "ownership": "Lease + finally remove owned zen-serve-state-* only after kill/reap/readers closed; no silent ignore_errors success, verify absence, record cleanup failure. Startup reaper handles crash remnants. Cleanup aggregate<=1.2s; H3 actual disk cleanup required.",
+          "preflight": "EVD-071 covers GET /api/session/active; /api/info version+pid readback NOT supplied. Before freeze-to-Coder execution gate, Stage3 first provider-free preflight rechecks both /api/info and /api/session/active on chosen env, startup<=3s/RSS/files/auth visibility; no Zen quota. H3 actual provider auth/parallel RSS remain NOT_RUN.",
           "verification_ids": [
@@ -1430,3 +1677,3 @@
         },
-        "typing": "Новый wire JSON декодируется в object с явным isinstance/type narrowing и TypedDict, без Any/кастов Any/type-ignore для обхода. Новый модуль serve_transport.py запрещён текущим allowlist; всё внутри server.py. VER-004: formatter/linter на всех3 файлах, basedpyright severity==error ровно0 на всех3, server reportAny<=125 и reportExplicitAny<=125, остальные frozen per-rule warning budgets не растут.",
+        "typing": "Decode wire JSON as object with isinstance narrowing/TypedDict; new code no Any/casts-to-Any/type-ignore. New test0diagnostics; new legacy ranges0reportAny/reportExplicitAny/reportUnusedCallResult. VER-004 uses isolated bridge cwd + ephemeral /tmp include/extraPaths, errorCount0all3, server Any<=125each and documented nonAny per-rule/total720, step194 (baseline564/162). Rename mutable internal CATALOG_SOURCE to lower-case across server references (no external HTTP key change); guard proc is not None at both returncode sites. No new module/config/dependency. Legacy format ranges only; all3 full lint with exact existing server-only E402 exception and no new E402.",
         "transport_health": {
@@ -1439,8 +1686,10 @@
             "invalid_serve_event / incompatible schema projection / malformed required v2 fields",
-            "serve SSE EOF без terminal; first_token_timeout только при доказанной protocol/capability причине, иначе model failure"
+            "serve SSE EOF без terminal; first_token_timeout только при доказанной protocol/capability причине, иначе model failure",
+            "listener_ownership failure/ambiguous PID/PGID mismatch/lsof timeout, once per attempt",
+            "serve spawn/ready/create/subscribe local transport failure; reconnect ownership timeout; schema mismatch"
           ],
           "not_counted": "Реальные provider errors (429/free-limit,5xx,provider network), explicit auth/permission/security failure, client_gone, slot rejection и transient child DB errors не маскировать transport failure. Если валидные execution events пришли, но model token нет, first_token_timeout сохраняет обычную provider classification при отсутствии доказанного protocol defect.",
-          "state_machine": "HEALTHY consecutive0..2; третий законченный protocol-specific failure -> DEGRADED(until=now+120), последующие auto requests run без serve probe/Popen. Это НЕ повтор/переключение текущего DELIVERED prompt: транспорт текущего запроса закреплён, silent replay запрещён. В DEGRADED skipped requests не продлевают TTL. При TTL expiry ровно один HALF_OPEN serve probe request (другие auto requests run); только валидный terminal success со schema-valid source очищает consecutive/degraded. Failed protocol probe -> новый TTL120. Provider failure не объявлять protocol success/failure. Neutral cancel освобождает probe, не продлевает TTL. Force serve допускает диагностику, не обходя security/kill-switch/cap3.",
+          "state_machine": "HEALTHY consecutive0..2; третий законченный protocol-specific failure -> DEGRADED(until=now+120), последующие auto requests run без serve probe/Popen. Это НЕ повтор/переключение текущего DELIVERED prompt: транспорт текущего запроса закреплён, silent replay запрещён. В DEGRADED skipped requests не продлевают TTL. При TTL expiry ровно один HALF_OPEN serve probe request (другие auto requests run); только валидный terminal success со schema-valid source очищает consecutive/degraded. Failed protocol probe -> новый TTL120. Provider failure не объявлять protocol success/failure. Neutral cancel освобождает probe, не продлевает TTL. Force serve допускает диагностику только при закрытом sticky TTL, не обходя security/kill-switch/cap3. Открытый sticky TTL применяется до explicit serve согласно configuration precedence: force serve не обходит TTL; HALF_OPEN admission после expiry остаётся прежним.",
           "breaker_isolation": "Protocol-specific failure никогда не вызывает _UpstreamBreaker.failure/commit pending model failure. Provider failures сохраняют общий breaker threshold5/cooldown jitter/HALF_OPEN1. Нейтральный transport-only финальный запрос освобождает model probe lease после cleanup; success/failure не выдумывать. _RetryBudget и MAX_TOTAL_SPAWNS остаются общими даже для protocol retry/fallback.",
-          "telemetry": "O-EXIT transport_history и attempt reason различают serve_protocol_failure, serve_health_degraded/run, serve_health_probe, policy failure и provider failure; no secrets. Skipped serve не добавляет фиктивный spawn.",
+          "telemetry": "REQ-016/AC-021 explicitly authorize transport,first_event_ms,ttft_ms in O-EXIT/v1. Preserve existing keys/types and one-exit cardinality; no incompatible rename. Fallback reason and transport-history details may be adjacent bounded redacted BRIDGE-TRANSPORT/v1 diagnostic correlated by existing request id, so strict O-EXIT parsers remain valid. Log selected transport=serve|run and reason for stat/schema/degraded/disable fallback; /health unchanged.",
           "verification_ids": [
@@ -1456,2 +1705,181 @@
           "verification": "VER-005 compare literal hashes from frozen packet; _serve_env wrapper only, never recalculate expected from edited implementation"
+        },
+        "serve_env_sanitization": {
+          "source": "Call immutable _run_env(model_id) exactly once, then build NEW env dictionary from exact allowlist on ALL branches standalone/base_url opencode-go/static; never env=dict(os.environ) passthrough.",
+          "allowlist": [
+            "PATH",
+            "HOME",
+            "USER",
+            "LOGNAME",
+            "SHELL",
+            "LANG",
+            "LC_ALL",
+            "LC_CTYPE",
+            "TZ",
+            "TERM",
+            "COLORTERM",
+            "HTTP_PROXY",
+            "HTTPS_PROXY",
+            "ALL_PROXY",
+            "NO_PROXY",
+            "http_proxy",
+            "https_proxy",
+            "all_proxy",
+            "no_proxy",
+            "SSL_CERT_FILE",
+            "SSL_CERT_DIR",
+            "NODE_EXTRA_CA_CERTS",
+            "XDG_DATA_HOME",
+            "XDG_CONFIG_HOME",
+            "OPENCODE_CONFIG",
+            "OPENCODE_CONFIG_CONTENT",
+            "OPENCODE_MODELS_PATH"
+          ],
+          "removal": "Deny always OPENCODE_ZEN_BRIDGE_*, arbitrary parent vars (SECRET_SENTINEL included) and unrelated *_API_KEY/*_TOKEN/*_SECRET. No broad OPENCODE_* or FAKE_* wildcard; only literal routing/config keys above. Tests inject explicit fake transport dependency, no production exception for secret sentinel. OPENCODE_DB/XDG_STATE_HOME/TMPDIR and server password are NOT inherited; generated after filter.",
+          "compatibility": "Proxy credentials only in explicitly required _run_env-selected HTTP(S)/ALL_PROXY values, redacted end-to-end. Config JSON from trusted _run_env retains required provider/options and selected permissions; no merging arbitrary parent secret keys. Standard auth file accessible by preserved HOME/XDG_DATA_HOME; unrelated API keys never child env.",
+          "overrides": "Then set OPENCODE_DB=:memory:, owned XDG_STATE_HOME/TMPDIR, merge scoped permission policy, and generate fresh OPENCODE_SERVER_PASSWORD last. Child-only secret, never argv/log/lease. Keep models/config on opencode-go and static branches.",
+          "tests": "VER-005 GroupB parameterizes standalone, opencode-go/base_url, CATALOG_MODE=static; sentinels absent, route config/models/auth paths preserved, password fresh, common DB untouched, _run_env literal hash unchanged."
+        },
+        "single_turn_control": {
+          "trigger": "permission.asked on own session or form.created.data.form.sessionID on own session. Immediately latch step_closed/output barrier BEFORE sending any control reply; retain accumulated raw/tool arguments and suppress every later-step text/reasoning.",
+          "order": [
+            "Do not wait for pending prompt HTTP response or step.ended. Snapshot already received complete tool args/call ids; continue only bounded same-step argument finalization, never wait for Step2.",
+            "Use idle Keep-Alive control lane: permission reply decision=reject OR form cancel within0.25s of validated event, including scheduling+I/O; no lsof/reconnect on this path.",
+            "Immediately POST /api/session/{id}/interrupt (<=0.10s) after rejection/cancellation; single-turn guard suppresses Step2 even if server races interrupt. On any control error fail-closed and group kill.",
+            "If mapped complete native call available, return it exactly once to DSH with finish_reason=tool_calls; otherwise apply existing _incomplete_step_signal/unmapped-tool recovery under same cap3/retry budgets. Preserve raw model data/provenance.",
+            "Final cleanup DELETE/close/kill/reap. Avoid duplicate interrupt if already succeeded; cancellation notifications never release Step2 barrier."
+          ],
+          "latency": "permission/form first reply<=0.25s; immediate subsequent interrupt<=0.10s is distinct control cost within model-execution phase. Final cleanup API aggregate<=0.20s; no new lsof. Only own session/PGID.",
+          "verification_ids": [
+            "VER-005"
+          ]
+        },
+        "crash_recovery": {
+          "registry": "/tmp/opencode-zen-bridge-leases/; owner-UID directory mode0700, lease files0600, no symlinks (lstat + O_NOFOLLOW where supported), atomic replace and fsync before prompt admission. No name-wide scanning outside registry.",
+          "lease_fields": [
+            "schema_version",
+            "owner_uid",
+            "bridge_instance_id",
+            "parent_pid",
+            "parent_start_ts",
+            "pid",
+            "pgid",
+            "port",
+            "start_ts",
+            "binary_realpath",
+            "binary_marker=opencode serve",
+            "temp_root",
+            "temp_root_inode",
+            "phase"
+          ],
+          "creation": "Write owned pre-spawn lease with temp root, phase=reserved before Popen; immediately after Popen atomically persist exact pid/pgid+ps start-time identity before READY/Auth/prompt. Parent bookkeeping thread per active lease watches the owned helper; parent-death enforcement itself is the paired helper holding the parent pipe. All included in thread/process budgets. Startup reaper required even if killed in persist gap. To cover spawn→lease update gap without unknown-child kill, spawn under lease-named stdlib helper which publishes child identity atomically and waits on parent pipe; EOF kills verified child PGID. Helper stdout/stderr not model data; new helper count boundedM and accounted below, not free model attempt. Implementation stays inside allowed server.py, stdlib -c helper only, no new script file.",
+          "parent_death": "Helper owns parent pipe, checks EOF / os.getppid() and parent start identity; polling<=0.25s, no timeout killing live owner. On EOF closes lanes and TERM verified child PGID, grace0.50s then KILL and reap, remove only own recorded temp root. Helper process owns separate PGID and parent bridge retains helper identity. No secret in lease/helper argv. Helper exits on completed attempt, capped one per slot.",
+          "startup_reaper": "Run before accepting bridge traffic (including disabled serve path): read only owner-UID valid leases. Live parent PID+matching parent_start_ts ->skip. If parent dead/mismatch, validate child ps pid,pgid,lstart,uid and command contains literal opencode serve --hostname 127.0.0.1 with exact recorded --port and binary path; os.getpgid(pid)==recorded pgid, start_ts matches. Recheck immediately before each signal and TERM→KILL. PID reuse, foreign uid, symlink, malformed/absent manifest or ambiguous identity ->no signal; redacted quarantine diagnostic, do not kill by name. Stored start_ts uses ps lstart identity plus monotonic instance nonce, not timestamp proximity alone.",
+          "directory_cleanup": "Only recorded local temp_root with zen-serve-state- prefix, owner uid and recorded inode, no symlink, path resolved within tempfile.gettempdir; verify child/helper no longer active before rmtree and absence check. Do not delete another live attempt root. Missing ownership manifest ->do not discover/kill/remove by name. Dead-child orphan temp lease may be removed after ownership checks; retain error lease for diagnostics on failure.",
+          "finally": "Normal finally closes pipe/helper, kills/reaps owned groups, removes temp root then lease. Never unlink manifest first or claim cleanup with ignore_errors. Startup reaper and helper idempotent under atomic lease ownership lock; races cannot signal reused PGID. All50 cancellation tests retained.",
+          "tests": "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN.",
+          "verification_ids": [
+            "VER-005"
+          ]
+        },
+        "fallback_decision_table": {
+          "columns": [
+            "phase",
+            "event",
+            "DELIVERED",
+            "action",
+            "ServeHealth_failure_increment",
+            "UpstreamBreaker_failure_increment"
+          ],
+          "rows": [
+            {
+              "phase": "SPAWN/READY/CREATE/SUBSCRIBE",
+              "event": "local spawn/ready/setup failure",
+              "DELIVERED": "false",
+              "action": "fallback_to_run",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "SPAWN→READY",
+              "event": "ownership failure/timeout",
+              "DELIVERED": "false",
+              "action": "fallback_to_run",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "PROMPT_SENDING",
+              "event": "first_event_timeout20s, no response headers and no valid execution SSE",
+              "DELIVERED": "false",
+              "action": "fallback_to_run",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "DELIVERED",
+              "event": "first_event_timeout20s after headers, no valid execution SSE",
+              "DELIVERED": "true",
+              "action": "serve_retry",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "DELIVERED",
+              "event": "first_token_timeout/stall with valid protocol and model silence",
+              "DELIVERED": "true",
+              "action": "serve_retry",
+              "ServeHealth_failure_increment": 0,
+              "UpstreamBreaker_failure_increment": 1
+            },
+            {
+              "phase": "ANY",
+              "event": "HTTP401/403 or permission/form/capability-security failure",
+              "DELIVERED": "any",
+              "action": "fail_closed",
+              "ServeHealth_failure_increment": 0,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "ANY",
+              "event": "HTTP400/404/422 invalid request",
+              "DELIVERED": "any",
+              "action": "fail_closed",
+              "ServeHealth_failure_increment": 0,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "PRE_PROMPT",
+              "event": "HTTP5xx local readiness/create/subscribe endpoint",
+              "DELIVERED": "false",
+              "action": "fallback_to_run",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "PROMPT_RESPONSE",
+              "event": "HTTP429/provider5xx; headers received latch delivery",
+              "DELIVERED": "true",
+              "action": "serve_retry",
+              "ServeHealth_failure_increment": 0,
+              "UpstreamBreaker_failure_increment": 1
+            },
+            {
+              "phase": "DELIVERED",
+              "event": "invalid SSE/EOF without terminal proven protocol-only",
+              "DELIVERED": "true",
+              "action": "serve_retry",
+              "ServeHealth_failure_increment": 1,
+              "UpstreamBreaker_failure_increment": 0
+            },
+            {
+              "phase": "ANY",
+              "event": "client cancel/deadline/budget exhausted",
+              "DELIVERED": "any",
+              "action": "fail_closed",
+              "ServeHealth_failure_increment": 0,
+              "UpstreamBreaker_failure_increment": 0
+            }
+          ],
+          "rules": "In auto fallback_to_run only before both barriers and before model/tool output, at most1 fallback after complete cleanup; force serve turns fallback_to_run into explicit failure. serve_retry means explicit admitted same-transport retry after cleanup/status, common cap3/retrytoken/FullJitter and remaining deadlines. If no budget ->fail_closed. Any response headers (including4xx/5xx) latch delivery before status classification. Upstream provider failure committed by existing per-request pending semantics once per cause, not per duplicate step/execution event. Security errors neutral to both health counters but fail-closed. lsof failure counter once per failed attempt;3 ->DEGRADED120s, next auto run without probes. Invalid protocol endpoint signature/security never bypassed by fallback."
         }
@@ -1504,3 +1932,3 @@
         "initial": "На t>=0.30 при отсутствии уже ОТПРАВЛЕННОЙ непустой real reasoning_content/content delta и незавершённом запросе отправить {reasoning_content:\"[мост] Подключение к модели…\\n\"} с реальным LF, flush. Пробелы и empty keepalive не считаются real progress. При доступной real delta в том же тике сначала обработать очередь, затем проверить grace: fast fake <50ms не получает prefix. Если real text пришёл раньше grace, initial status не нужен — ответ уже видим. Если real reasoning пришёл раньше grace, Think видим без synthetic prefix; отсутствие LF в быстром Simple greeting. не даёт права мутировать текст.",
-        "lifecycle": "Startup-gate/spawn wait статусы только после grace при фактическом ожидании, без немедленного prefix на быстром acquire. До первого real token при тишине heartbeat каждые 5.0 s: [мост] Ожидание первого токена (N с)… + LF. После real progress и затем настоящего stall можно каждые 5 s дать [мост] Ожидание продолжения… + LF. Статусы не сбрасывают transport/model watchdog timestamps и сами не считаются attempt_output. Нормальные 127 ms reasoning delta не сопровождаются heartbeat. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
+        "lifecycle": "Before first real token eligible quiet request gets first status after grace0.30s, then [мост] Ожидание первого токена… with LF every5.0s. After useful model token, STALL_HEARTBEAT_INTERVAL_S=15.0: when upstream silent>=15.0s, MUST emit [мост] Ожидание продолжения… +LF and repeat every15.0s while stalled, including pause after very first token. Progress resets heartbeat schedule only from model clock; normal127ms delta never gets heartbeat. Synthetic statuses never reset first-event/first-token/stall watchdog clocks or had_output/usage. Single writer, leading LF separator synthetic provenance.",
         "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
@@ -1509,3 +1937,4 @@
         "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt. Остаточный межпровайдерский replay в DSH при ручной смене модели описан RISK-011; current bridge ignore не доказывает безопасность чужого provider.",
-        "status_separator": "Перед любой synthetic [мост] delta, если ранее выданный модельный reasoning chunk не оканчивался LF и текущая видимая строка не завершена, prefix=\"\n\"; результат \"\n[мост] ...\n\". Весь prefix/status/trailing LF имеет synthetic provenance, отдельно от immutable model deltas. Если LF уже есть или модельного reasoning ещё не было, status начинается \"[мост]\" без добавочного LF. Единственный writer отслеживает line boundary; быстрый Simple greeting. до grace вообще не вызывает status helper. Фильтрация synthetic по provenance сохраняет AC-006 байт-в-байт и модельную строку, буквально начинающуюся [мост]."
+        "status_separator": "Перед любой synthetic [мост] delta, если ранее выданный модельный reasoning chunk не оканчивался LF и текущая видимая строка не завершена, prefix=\"\n\"; результат \"\n[мост] ...\n\". Весь prefix/status/trailing LF имеет synthetic provenance, отдельно от immutable model deltas. Если LF уже есть или модельного reasoning ещё не было, status начинается \"[мост]\" без добавочного LF. Единственный writer отслеживает line boundary; быстрый Simple greeting. до grace вообще не вызывает status helper. Фильтрация synthetic по provenance сохраняет AC-006 байт-в-байт и модельную строку, буквально начинающуюся [мост].",
+        "STALL_HEARTBEAT_INTERVAL_S": 15.0
       }
@@ -1566,4 +1995,4 @@
         "disconnect": "На каждой итерации/ожидании <=0.25 s проверять cancel flag и client socket select + recv(MSG_PEEK|MSG_DONTWAIT): EOF/ECONNRESET -> client_gone без чтения данных и без переключения wfile в nonblocking. Реальная bounded empty OpenAI keepalive каждые <=2.0 s тишины страхует разрыв, который TCP ещё не сигнализировал; write deadline <=0.5 s, без write на отдельном потоке. Poll, status, write и cleanup не блокируют supervisor на 15/5 s. Суммарное обнаружение контролируемого FIN/RST <=5.0 s. Полное исчезновение сети без FIN нельзя доказать одним MSG_PEEK — bounded write/OS transport timeout и fault injection отдельно, не обещать физически невозможный мгновенный детект blackhole.",
-        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent. После child kill/reap обязателен finally shutil.rmtree(owned XDG_DATA_HOME,ignore_errors=True); закрыть также daemon prompt delivery socket и join его в том же aggregate cleanup<=1.2s. Interrupt/delete только после ownership proof, никогда чужому listener.",
-        "retry": "Watchdog first_event/first_token/stall -> bounded common retry after full cleanup, _RequestAttempts/MAX_TOTAL_SPAWNS3/FAIL_RETRY_LIMIT/_RetryBudget/Full Jitter как ранее. Но serve-specific no-session-event/invalid_serve_event/EOF классифицируются _ServeHealth и НЕ _UpstreamBreaker; общие provider failures по-прежнему model breaker. При DELIVERED silent run fallback запрещён: retry текущего запроса остаётся явным на закреплённом транспорте, health TTL влияет только на последующие auto requests. Legacy watchdog сохраняет provider semantics. client_gone/fatal4xx/auth/permission ->no retry/fallback. HALF_OPEN owner token жив до завершения/cleanup, cooldown не допускает второй probe; neutral transport failure/cancel освобождает probe без fake provider success/failure. Slot один на запрос, release once; cancel-aware waits<=.25s; Full Jitter capped remaining.",
+        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent. После child kill/reap обязателен finally verified removal of owned zen-serve-state-* root (XDG_STATE_HOME/TMPDIR), preserve standard XDG_DATA_HOME; закрыть также daemon prompt delivery socket и join его в том же aggregate cleanup<=1.2s. Interrupt/delete только после ownership proof, никогда чужому listener. Fast API interrupt/delete each0.09s plus0.02 scheduling margin aggregate0.20; no lsof/reconnect. Normal helper pipe close/join and lease/temp deletion share remaining0.50s; crash_recovery covers death outside finally.",
+        "retry": "Watchdog first_event/first_token/stall -> bounded common retry after full cleanup, _RequestAttempts/MAX_TOTAL_SPAWNS3/FAIL_RETRY_LIMIT/_RetryBudget/Full Jitter как ранее. Но serve-specific no-session-event/invalid_serve_event/EOF классифицируются _ServeHealth и НЕ _UpstreamBreaker; общие provider failures по-прежнему model breaker. При DELIVERED silent run fallback запрещён: retry текущего запроса остаётся явным на закреплённом транспорте, health TTL влияет только на последующие auto requests. Legacy watchdog сохраняет provider semantics. client_gone/fatal4xx/auth/permission ->no retry/fallback. HALF_OPEN owner token жив до завершения/cleanup, cooldown не допускает второй probe; neutral transport failure/cancel освобождает probe без fake provider success/failure. Slot один на запрос, release once; cancel-aware waits<=.25s; Full Jitter capped remaining. Decision table AD-001.fallback_decision_table is authoritative for phases/counter effects, including first_event before/after headers.",
         "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки. HTTP readiness НЕ first_event_ms: поле null до valid SSE execution current session после prompt_send_start. transport_history фиксирует отказ serve/TTL run или probe без secrets и phantom Popen; отдельный reason для protocol/model/security. early HTTP headers не ставят ни first_event_ms, ни ttft_ms."
@@ -1617,5 +2046,5 @@
         "parser": "Каждый session.text.delta -> тот же parser.feed без промежуточного whole-step buffer. Outside genuine tool blocks удерживается только pending opener prefix <=max(len(<tool_call>),len(<tool_invoke>))-1=12 chars плюс нужный существующему code-context lookahead; open block удерживается до валидного close, JSON close внутри строки не закрывает блок. Genuine/unparsed/incomplete tool tags не попадают в delta.content: callbacks через _strip_broken_tool_blocks и chunk-safe finish; существующие намеренно цитированные теги в Markdown остаются документационным текстом по текущим parser fixtures (не выполнять их). Инвариант по всем split points и single-character chunks. Open-block/total-output/frame bounds проверяются отдельно, overflow -> explicit error+cleanup.",
-        "step": "Accumulated raw text/reasoning/native + step.ended tokens -> _is_incomplete_tool_step/_incomplete_step_signal и _is_transient_stream_error. При step.ended с готовым вызовом немедленно завершить upstream, finish_reason=tool_calls; не пропускать SYNTHETIC Continue. Error до первого model output допускает bounded recovery upstream как legacy; поздняя transient error прерывает attempt, fatal 400/401/403/404/422 без retry. Bridge status не изменяет attempt_output/first_token/had_error. _strip_interrupted и _strip_broken_tool_blocks работают независимо от границ delta.",
+        "step": "Accumulated raw text/reasoning/native + step.ended tokens -> _is_incomplete_tool_step/_incomplete_step_signal и _is_transient_stream_error. При step.ended с готовым вызовом немедленно завершить upstream, finish_reason=tool_calls; не пропускать SYNTHETIC Continue. Error до первого model output допускает bounded recovery upstream как legacy; поздняя transient error прерывает attempt, fatal 400/401/403/404/422 без retry. Bridge status не изменяет attempt_output/first_token/had_error. _strip_interrupted и _strip_broken_tool_blocks работают независимо от границ delta. Native called.data.input absent: input.ended.data.text parsed once as complete JSON supplies tool arguments even streaming→failed. permission reject/form cancel latch single-turn barrier BEFORE control; immediately interrupt and return mapped tools or existing recovery, never Step2 output.",
         "baseline_tests": "В TestStepInterruptionLive.setUp заменить self.httpd.resilience на новый _Resilience (либо новый _RetryBudget с инъектируемыми часами + reset breaker/limiter), только когда прошлый request завершён, тесты класса последовательны. Ничего не сбрасывать в prod. В двух unmapped_retries_do_not_exhaust_incomplete_budget_{json,stream} оставить текущую fixture: первые 2 попытки unmapped, третья status/promise, 4-я запрещена. Ожидать runs==3, отсутствие tool_calls, finish_reason=stop, status/prelude ровно один раз; не ждать job_output/bash с несуществующего 4-го spawn. Добавить отдельный reachable<=3 сценарий unmapped -> incomplete -> calls и/или unit-oracle независимости счётчиков. Test_unmapped_then_error_stops_proc_json ожидает 2 и не зависит от предыдущих токенов бюджета. Все 17 legacy modules плюс новые tests green; production MAX_TOTAL_SPAWNS=3 не меняется.",
-        "red_green": "Сначала dedicated tests на текущем коде: реальный socket read до release upstream Event, slow initial status, watchdog/cleanup и native delta split. Зафиксировать red (не import error), после Stage 3 green в VER-005 и полном VER-001/002. Stage 2 тестовый код не пишет и зелёное выполнение этой будущей поверхности не заявляет."
+        "red_green": "Сначала dedicated tests на текущем коде: реальный socket read до release upstream Event, slow initial status, watchdog/cleanup и native delta split. Зафиксировать red (не import error), после Stage 3 green в VER-005 и полном VER-001/002. Stage 2 тестовый код не пишет и зелёное выполнение этой будущей поверхности не заявляет. AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN."
       }
@@ -1657,3 +2086,3 @@
       "stimulus": "fake script игнорирует argv и блокируется на stdin.read",
-      "environment": "auto/default true + shebang filter либо explicit disabled/run/disable-file",
+      "environment": "auto с кодовым default=false; runtime dynamic_config.json=true после H7/H3/H6 + native eligibility; explicit env disabled/run/disable-file/TTL ->run",
       "artifact": "bridges/opencode-zen-bridge/server.py",
@@ -1780,3 +2209,3 @@
       "component": "managed serve/run source + per-Server resource manager",
-      "responsibility": "Transport selection, listener PID/PGID proof до Auth/prompt, fresh _serve_env/proxy и isolated XDG_DATA_HOME, bounded HTTP/SSE/delivery leases, canonical wire adapter и cleanup",
+      "responsibility": "Transport selection, listener PID/PGID proof до Auth/prompt, fresh _serve_env/proxy и OPENCODE_DB=:memory:, standard read-only auth data and owned state/temp dirs, bounded HTTP/SSE/delivery leases, canonical wire adapter и cleanup",
       "allowed_dependencies": [
@@ -1839,3 +2268,3 @@
       "consumer": "DSH OpenAI completion reader",
-      "change": "Grace=.30s synthetic [мост] status delta с LF для thinking-enabled slow/retry lifecycle; fast/off/JSON не получают prefix. Разрешено текущим Brief AD-002 и REQ-004/005.",
+      "change": "Grace=.30s synthetic [мост] status delta с LF для thinking-enabled slow/retry lifecycle; fast/off/JSON не получают prefix. Разрешено текущим Brief AD-002 и REQ-004/005. Mandatory eligible stall heartbeat threshold=interval15.0s even after first token; pre-token heartbeat5.0s; reasoning provenance and leading LF unchanged.",
       "compatibility": "OpenAI chunk shape/finish/usage unchanged; no unconditional t0 status; user fast exact reasoning equality preserved. REQ004 scoped to thinking-enabled, real content раньше grace уже видим.",
@@ -1914,3 +2343,3 @@
       "impact": "high",
-      "mitigation": "В _serve_env temporary XDG_DATA_HOME per Popen, preserve OPENCODE_MODELS_PATH, finally rmtree after group cleanup; shared2.27GB DB не трогать. Design memory1408<=1638.4MiB не measured RSS. H3 до production sync:6 parallel103KB×3 +7th overload, max_actual_parent_RSS+6*max_actual_child_RSS<=0.80*2048MiB и ноль database is locked (ретрай не маскирует contention). FAIL->disable-file сохраняется, rollout запрещён; slots6/waiters12 не повышать.",
+      "mitigation": "OPENCODE_DB=:memory:, standard XDG_DATA_HOME/auth preserved, owned state/temp finally+crash reaper; EVD-071 zero common DB opens. H3 actual parent+all6serve/pairedhelpers/lsof<=1638.4MiB and zero locks on103KB×6×3; real auth not proven by provider-free access. disable-file retained on FAIL, no slot/retry increases.",
       "verification_ids": [
@@ -1925,3 +2354,3 @@
       "impact": "high",
-      "mitigation": "Auto shebang ->one run, no subprocess probes при default=true. Force serve stdin DEVNULL, ready<=3.0s/cancel-aware. Cache по path+mtime_ns+size; exact counter regressions остаются. Никакой fake5s stdin hang.",
+      "mitigation": "При отсутствующем runtime config default=false ->run для378baseline. При enabled auto shebang ->one run без subprocess probes. Force serve stdinDEVNULL, ready<=3.0s/cancel-aware; первый kill-switch/TTL guard обязателен. Executable cache path+mtime_ns+size; config cache mtime_ns+size, invalid/missing boolean ->false с redacted warning. Exact counter regressions сохранены.",
       "verification_ids": [
@@ -1969,3 +2398,3 @@
       "impact": "medium",
-      "mitigation": "VER-004 заменяет прежний overlay на strict formatter/linter/type checks всех3 files. Унаследованные E402 и2 type errors EVD052/053 честно baseline, их allowance удалён: Coder должен исправить в allowlist без подавления диагностики/конфига. severity error0, reportAny/reportExplicitAny<=125 server.py, прочие frozen warning budgets не растут; format may reveal debt, FAIL нельзя объявить PASS.",
+      "mitigation": "EVD-072: full legacy format violates frozen bytes. VER-004 new file full format, legacy changed ranges via git diff-U0; local bridge-cwd temporary import-root, no repo config mutation. CATALOG_SOURCE mutable-name correction and proc None guards resolve3 type errors. Existing E402 only import zen_catalog baseline handled per-file CLI ignore with exact-site check, no noqa. Both Any<=125,0 Any/new warnings policy and explicit nonAny budgets; commands pendingStage3.",
       "verification_ids": [
@@ -1990,3 +2419,3 @@
       "impact": "high",
-      "mitigation": "PGID сохранён при spawn, group kill даже leader exited, cleanup bounded1.2s; собственный lifecycle реестр, никакого pkill; finally every branch.",
+      "mitigation": "Normal cleanup<=1.2s; SIGKILL/kickstart-k outside finally protected by parent-pipe helper + safe startup lease reaper. Persist child identity before prompt; validate owner/ps start-time/PGID/cmd/inode and foreign-process negative tests. H0/H9 actual orphan sweep NOT_RUN.",
       "verification_ids": [
@@ -2043,3 +2472,3 @@
         "scenario": "Модель выдаёт builtin bash/write/edit, пока DSH думает, что это только предложение",
-        "mitigation": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
+        "mitigation": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6. _run_env does NOT sanitize every branch; _serve_env must apply serve_env_sanitization to all3 branches. Mandatory form.created→cancel and reject/cancel→immediate interrupt single_turn_control; JSON args fallback input.ended.data.text when called absent; no second-step output. {\"trigger\": \"permission.asked on own session or form.created.data.form.sessionID on own session. Immediately latch step_closed/output barrier BEFORE sending any control reply; retain accumulated raw/tool arguments and suppress every later-step text/reasoning.\", \"order\": [\"Do not wait for pending prompt HTTP response or step.ended. Snapshot already received complete tool args/call ids; continue only bounded same-step argument finalization, never wait for Step2.\", \"Use idle Keep-Alive control lane: permission reply decision=reject OR form cancel within0.25s of validated event, including scheduling+I/O; no lsof/reconnect on this path.\", \"Immediately POST /api/session/{id}/interrupt (<=0.10s) after rejection/cancellation; single-turn guard suppresses Step2 even if server races interrupt. On any control error fail-closed and group kill.\", \"If mapped complete native call available, return it exactly once to DSH with finish_reason=tool_calls; otherwise apply existing _incomplete_step_signal/unmapped-tool recovery under same cap3/retry budgets. Preserve raw model data/provenance.\", \"Final cleanup DELETE/close/kill/reap. Avoid duplicate interrupt if already succeeded; cancellation notifications never release Step2 barrier.\"], \"latency\": \"permission/form first reply<=0.25s; immediate subsequent interrupt<=0.10s is distinct control cost within model-execution phase. Final cleanup API aggregate<=0.20s; no new lsof. Only own session/PGID.\", \"verification_ids\": [\"VER-005\"]}",
         "verification_ids": [
@@ -2051,3 +2480,3 @@
         "scenario": "Unrestricted parent env утекает в serve или proxy creds в ошибку",
-        "mitigation": "_run_env whitelist как legacy, password добавляется только child env; no apiKey dump, redact stdout/stderr/exception before _log and response; тест secret sentinels. _serve_env wrapper не меняет _run_env и сохраняет model catalog, private XDG data удаляется finally.",
+        "mitigation": "_run_env only standalone branch whitelists; opencode-go/static inherit parent env baseline. New _serve_env filters exact allowlist on ALL3 branches before generated password/DB/state values, preserving only required routing/catalog/proxy/auth paths. OPENCODE_ZEN_BRIDGE_* and arbitrary API_KEY/TOKEN/SECRET sentinels absent; config/log/lease redacted. See AD-001.serve_env_sanitization; VER-005 branch matrix. _run_env remains byte-identical.",
         "verification_ids": [
@@ -2067,3 +2496,3 @@
         "scenario": "Отмена клиента/oversized frame держит процессы и позволяет resource exhaustion",
-        "mitigation": "bounded byte queue/frame/output and slots/waiters, finite per-operation deadlines, own PGID forced cleanup, zero orphan tests; output overflow не дропается молча.",
+        "mitigation": "bounded byte queue/frame/output and slots/waiters, finite per-operation deadlines, own PGID forced cleanup, zero orphan tests; output overflow не дропается молча. Crash leases + parent-pipe helper + startup reaper with uid/pid/pgid/start_ts/command/inode verification; no foreign signals/name-wide cleanup.",
         "verification_ids": [
@@ -2075,7 +2504,7 @@
   "evolution": {
-    "compatibility": "Публичные OpenAI endpoints/port/auth/schema и Google route неизменны, source общий для SSE/JSON. Default serve flag=true в auto только для нативного бинарника; shebang fake CLI остаётся run без probe, start.sh и _run_env byte-identical. Fast/off/JSON synthetic statuses как раньше исключены.",
-    "migration": "NOT_APPLICABLE: продуктовая схема/DB/dependencies не меняются; shared opencode.db/config не трогать. Каждый child получает свежий local-temp XDG_DATA_HOME и сохранённый OPENCODE_MODELS_PATH; наконец interrupt/delete/kill/reap и shutil.rmtree(...,ignore_errors=True). История ephemeral, долговременные prompt/secret артефакты не сохраняются.",
-    "rollout": "Stage2 packet cycle2/role-plan/schema/fingerprint -> external architecture Council R2+verify_panel_proof оркестратора -> Stage3 red→green+independent clean-room VER001..005 strict. Default=true НЕ разрешает обход H3: ДО синхронизации server.py в боевой :9883 отдельно изолированный candidate runtime с effectiveM6/waiters12, live103KB prompts6parallel+7th,3повтора и H3 memory/SQLite check. На боевом до допуска удерживать disable-file, который действует сразу при первом старте новой server.py; файлы ~/.dsh в Stage2 не создавать. Только H3 PASS и безопасная policy H6 разрешают H0 sync/read-back, без изменения start.sh; при удалении disable-file native Mach-O в auto сразу serve. После sync H1/H2/H3 повторно+DSH H4/H5/H6/H7/H8/H9; любой memory/DB/security FAIL немедленно disable-file и run. Не перекладывать pre-rollout safety на уже случившийся default-enable. На этом проходе все H0..H9 NOT_RUN.",
-    "rollback": "Мгновенный kill-switch без рестарта: создать OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE (default ~/.dsh/bridges/opencode-zen-bridge/disable-serve) -> следующий запрос run без serve allocations/probes; удаление файла возвращает auto при healthy transport. Env REALTIME_SERVE_ENABLED=0 или TRANSPORT=run также принудительно run (смена env уже живого процесса требует restart, не путать с file switch). In-flight leases drain/cancel, delivered prompt не повторять на run. H9 проверяет в живом existing DSH чате создание/удаление файла, неизменный PID сервиса, run/serve transport_history и успешные повторные/параллельные вызовы. Если status/watchdog regression -> отдельный rollback Stage3 commit+H0 identity. Stage2 rollback/deploy не выполняется.",
-    "feature_flag": "Explicit cycle2 RW-009/FU-006 override: default=true для локального auto-native пути, zero-serve-cost explicit disable и O(1) file switch без рестарта. Прецедент F-40/STEP_RECOVERY; GigaRC/start.sh dependencies вне allowlist. H3 и H6 обязательны до production enable.",
+    "compatibility": "Existing public endpoints/schema/Google unchanged; run fallback retained. OPENCODE_DB=:memory: и standard auth/models/config сохранены. Кодовый default=false и отсутствие runtime JSON в git гарантируют378baseline по run; native auto включается атомарным runtime true только на H7 после H3/H6, без start.sh/restart/new env.",
+    "migration": "No product DB migration. serve child SQLite memory only; never read/write/migrate shared opencode.db/opencode-next.db. Owned zen-serve-state-* dirs and UID registry leases are transient control state removed normally/following crash-safe reaper. Standard XDG_DATA_HOME/auth.json kept read-only.",
+    "rollout": "Все H0..H9 NOT_RUN, external a3 ACCEPT+panel proof и независимые VER gates обязательны; Architect не выполняет rollout. H0 BLOCKING до sync/restart: проверить текущий env не force serve/true, отсутствие production dynamic_config.json либо boolean false; при прежнем enabled состоянии атомарно записать false, проверить read-back; дополнительный disable-serve разрешён. Снять старые PID/start/lease identity. H4 sync/read-back server.py hash; H5 launchctl kickstart с config absent/false: сразу dark run без окна serve; startup reaper0 старых собственных serve/helper/temp roots, чужие процессы untouched. На отдельном кандидате test-local dynamic_config.json=true и отдельный disable-file path: provider-free info/active, H3 реальные6parallel RSS/FD+OPENCODE_DB=:memory:, H6 live permission/tool isolation, Stage3a/A затем3b/B. На production до H7 run. H7 ТОЛЬКО после PASS H3 и H6: при env auto без explicit false и закрытом TTL подготовить tempfile в ~/.dsh/bridges/opencode-zen-bridge/,0600, записать {\"REALTIME_SERVE_ENABLED\":true}, os.replace в dynamic_config.json; убедиться дополнительный disable-serve отсутствует. Следующий native auto запрос на :9883 использует serve без правки start.sh и без повторного рестарта LaunchAgent. H8 повторяет живые проверки рабочего чата, H9 проверяет runtime false/true и disable-file same PID, отдельно kickstart-k crash recovery. Никакой выдачи design/NOT_RUN за runtime PASS.",
+    "rollback": "Runtime kill-switch без рестарта: атомарно tempfile+os.replace mode0600 записать {\"REALTIME_SERVE_ENABLED\":false} в ~/.dsh/bridges/opencode-zen-bridge/dynamic_config.json; либо удалить файл (default=false), либо создать disable-serve. Следующий auto запрос run без serve probes/allocations. Цель selector overhead <1мс проверяется VER-005/H9; это не измеренная гарантия задержки файловой записи/планировщика. Существующий explicit env=true имеет заданный override приоритет: в таком диагностическом процессе использовать disable-file для безусловного runtime rollback; production H0/H7 требуют auto без override. Env false/no/off/0 или TRANSPORT=run также force run, но изменение env живого процесса требует restart. In-flight leases drain/cancel, DELIVERED prompt не повторяется на run. H9 проверяет same PID, transport_history и повторные/параллельные вызовы; kickstart-k отдельно с config false/absent и identity-verified owned reaper. Stage2 ничего не деплоит. Все H0..H9 NOT_RUN.",
+    "feature_flag": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git.",
     "H3_rollout_gate": {
@@ -2084,6 +2513,25 @@
       "memory_unit": "MiB",
-      "memory_inequality": "1*actual_parent_RSS_max + M*actual_child_RSS_max <=0.80*Mem_limit_per_pod; M=6; limit=2048MiB, rhs=1638.4MiB",
-      "database_gate": "Ноль database is locked/SQLITE_BUSY на isolated per-spawn XDG DB; ретрай в FAIL_RETRY_LIMIT не превращает lock failure в PASS. Shared2.27GB DB не изменяется.",
-      "other_evidence": "Реальные RSS/FD/CPU/TTFT каждого запроса, parent/child peaks, все owned temp dirs удалены, zero orphan PGID; design child192MiB не подставлять вместо замера",
-      "on_fail": "Rollout/enable запрещён, disable-file остаётся; не повышать slots6/12 или retry cap3. Не менять текущие shared env/config/DB."
+      "memory_inequality": "actual_parent_RSS + sum(RSS_serve + RSS_paired_helper + RSS_lsof_peak over M=6) <=0.80*2048=1638.4MiB; combined design per-slot192MiB includes helpers, not192+helpers.",
+      "database_gate": "OPENCODE_DB=:memory:,0 shared SQLite opens/writes (lsof + disk identity snapshot);0database is locked/SQLITE_BUSY across6parallel×3; valid opencode-go auth without false401 tested separately from provider-free readiness.",
+      "other_evidence": "Реальные RSS/FD/CPU/TTFT каждого запроса, parent/child peaks, все owned temp dirs удалены, zero orphan PGID; design child192MiB не подставлять вместо замера Include lsof one per spawn, helper/watchdog PIDs,18 admitted handler threads (6active+12waiters), consistent12 drains, observed FD/thread peaks and transport diagnostics. /api/info+active provider-free first; measured ready120.7ms is baseline not guarantee.",
+      "on_fail": "Rollout enable запрещён: runtime config остаётся absent/false (и дополнительный disable-file остаётся, если поставлен). Не повышать slots6/12/retrycap3 и не менять shared env/config/DB."
+    },
+    "H0_precondition": {
+      "status": "NOT_RUN",
+      "blocking": true,
+      "ordered_steps": [
+        "verify production TRANSPORT=auto and no explicit enabled env override",
+        "verify dynamic_config.json absent or boolean REALTIME_SERVE_ENABLED=false; if enabled atomically write false0600 and read-back before sync/restart",
+        "optional additional disable-serve; preserve recorded safety state",
+        "capture old PID/start/leases",
+        "H4 sync candidate bytes/read-back hash",
+        "H5 kickstart-k in dark run; reaper0 previous own serve/helper/temp roots",
+        "candidate H3 six parallel RSS/FD memoryDB and H6 permission/tool isolation PASS before H7",
+        "H7 atomic tempfile+os.replace0600 runtime true; remove optional disable-file only at this enable gate; no start.sh change/restart"
+      ],
+      "owner": "rollout operator; not Architect"
+    },
+    "H9_crash_recovery_gate": {
+      "status": "NOT_RUN",
+      "scenario": "Same live bridge PID: atomic runtime config false ->run, true ->serve при native+healthy, file deletion ->run; disable-serve дополнительно always run. Подтвердить selector overhead<1мс фактом, не обещанием. Отдельно parent hard kill/kickstart-k с active serve и последующий startup reaper:0 собственных orphan serve/helper/temp roots, чужие PID/PGID untouched."
     }
@@ -2095,3 +2543,3 @@
     "evidence_ref": null,
-    "rationale": "AD остаются reversible/two-way в рамках explicit cycle2 brief (EVD-064), включая headers barrier/default=true. APPROVED здесь — архитектурный кандидат, не ACCEPT Совета; R2 и packet/surface freeze обязательны до Coder."
+    "rationale": "FU-007 закрыт без исключений из канона: кодовый дефолт REALTIME_SERVE_ENABLED переведён в false, а включение на :9883 выполняется через локальный runtime dynamic_config.json (stat mtime_ns кэш без рестарта и без правки start.sh) строго на шаге H7 после прохождения H3/H6. Все AD обратимы (two-way); status=APPROVED означает валидированный архитектурный пакет-кандидат для Архитектурного Совета a3 (r4), а не вердикт Совета."
   },
@@ -2102,3 +2550,3 @@
     "evidence_ref": null,
-    "rationale": "S2: universal schema independent_review NOT_REQUIRED сохраняется; обязательный downstream Council R2 с отдельным proof ведёт оркестратор, эта роль не создаёт голос/вердикт."
+    "rationale": "S2 schema review NOT_REQUIRED, but downstream external Council a3/proof is mandatory orchestration gate; Architect writes no vote or ACCEPT. Previous a2 NEEDS_WORK history retained."
   },
@@ -2116,2 +2564,17 @@
       "disposition": "Default выбран, автопереключения нет. FakeServe обе policy не доказывает live H6; неизвестная safe capability fail-closed, до H6 боевой disable-file не снимать."
+    },
+    {
+      "id": "Q-003",
+      "class": "continuable",
+      "decision_required_human": false,
+      "question": "FU-007 закрыт compliant flag delta: кодовый default=false плюс локальный runtime dynamic_config.json; human waiver не нужен.",
+      "owner": "owner/orchestrator",
+      "blocks": "Нет блокера policy; H3/H6/H7 и независимый a3 review остаются обязательны.",
+      "evidence_ids": [
+        "EVD-074"
+      ],
+      "blocking": false,
+      "source_id": "FU-007/a2",
+      "status": "RESOLVED",
+      "disposition": "По явной финализации architect-cycle-3b; runtime проверки NOT_RUN."
     }
@@ -2135,4 +2598,4 @@
     "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency.",
-    "wire_fixture": "Frozen fixture literals + canonical digest в AD-001 event_contract обязаны использоваться независимым expected oracle. Изменение adapter+FakeServe одной ошибкой не должно сохранять green; corruption delta/token/permission field detection required.",
-    "strict_typing": "VER-004 all3files strict0errors, no inherited-error overlay; reportAny/reportExplicitAny server each<=125 и остальные per-rule budgets<=v1. Доказательство исполнения принадлежит clean-room L2, не этой Stage2 роли."
+    "wire_fixture": "Six frozen source-schema families, canonical digest serialization explicit; five original family literals retained and nested form family added, adversarial mutations independent adapter/FakeServe.",
+    "strict_typing": "Decode wire JSON as object with isinstance narrowing/TypedDict; new code no Any/casts-to-Any/type-ignore. New test0diagnostics; new legacy ranges0reportAny/reportExplicitAny/reportUnusedCallResult. VER-004 uses isolated bridge cwd + ephemeral /tmp include/extraPaths, errorCount0all3, server Any<=125each and documented nonAny per-rule/total720, step194 (baseline564/162). Rename mutable internal CATALOG_SOURCE to lower-case across server references (no external HTTP key change); guard proc is not None at both returncode sites. No new module/config/dependency. Legacy format ranges only; all3 full lint with exact existing server-only E402 exception and no new E402."
   },
@@ -2252,6 +2715,6 @@
       "Mem_rss_worker_max": "F-29 parent baseline22MiB; design bound256MiB; H3 actual_parent_RSS_max measured in MiB.",
-      "Mem_shared_max": "F-20 idle152MiB; design child192MiB*6=1152MiB aggregate child budget, not RSS measurement. Per-spawn XDG data preserves models path, eliminates intended shared SQLite open; H3 actual6child RSS and zero locks required.",
+      "Mem_shared_max": "1152MiB=6*192MiB COMBINED per-slot budget for serve+parent-pipe helper+transient lsof, no192MiB extra helper allowance. EVD-071156.8MiB serve idle leaves35.2MiB nominal per-slot headroom, NOT proof of loaded peak. H3 sums actual parent+serve+helper+lsof RSS and must satisfy<=1638.4MiB; design fields remain2048/256/1152MiB a1.",
       "RPS_peak": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
       "A_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
-      "SLA_p99_s": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
+      "SLA_p99_s": "180s normal-mode design goal from analyst envelope; degraded first-token failure profile3*60+51.6=231.6s separate explicit acceptance, not guaranteed180s or universal generation limit. See operational_profile.p99_criteria; actual measurements NOT_RUN.",
       "N_entities_max": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
@@ -2270,3 +2733,3 @@
       "min_reserve_retry_rps": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
-      "FD_worker": "F-29 parent36; bound128 covers6 clients +18 HTTP control/SSE/delivery sockets +12 drains+6 reserve sockets/handles, per-child20FD (F-20); parent+children<256 design, actual H3.",
+      "FD_worker": "Design parent ceiling128 vs recalculated108=36baseline+18admittedclients+18lanes+12drains+6reserve+6lsof pipes+6watchdogpipe+6lease handles; helper/serve/lsof processFD separate. H3 verify per-process limits and344aggregate estimate.",
       "ulimit_n": "F-29 launchctl soft maxfiles=65536; не переносить значение вчерашнего reference packet=4096 как текущий факт.",
@@ -2287,4 +2750,4 @@
       "server_resource_manager": "один per-Server owner для bounded process/socket leases, после старта процесса, без parent live sockets before child exec",
-      "threads_per_worker_upper_bound": 36,
-      "thread_accounting": "До6 handlers +6 SSE readers +6 daemon prompt delivery workers +6 bounded stdout/stderr drain workers +6 gate timers +6 reserve=36; run stdin feed заменяет serve delivery в том же attempt. Не добавлять сверх36 неучтённые workers; каждый owned socket/worker closed/joined вcleanup. HTTP leases: control + SSE + prompt delivery =3 per active serve, максимум18. Не блокировать reject behind POST.",
+      "threads_per_worker_upper_bound": 55,
+      "thread_accounting": "Parent bound55=1server/accept loop +18 admitted handlers(6active+12waiting) +6supervisors/setup tasks +6SSE readers +6prompt delivery workers +12separate stdout/stderr drains +6parent-watchdog bookkeeping threads. No additional per-request gate timers; cancellation polls shared supervisors. lsof runs synchronously bounded0.35s on setup/supervisor,6 concurrent helpers max, no extra parent thread. Reaper startup-only (no overlap request workers). Parent-pipe helper at most6 single-thread processes, separately counted, not parent threads; at most6 actual serve +6 helper +6 transient lsof processes (18aux at peak). Rejected ingress handlers beyond admission exist transiently in ThreadingHTTPServer:55 is admitted-workload bound, not arbitrary SYN-flood guarantee; H3 measure transient rejection peaks, do not claim unlimited HTTP thread defense.",
       "stdout_queue_max_events": 4096,
@@ -2310,3 +2773,3 @@
       "total_deadline_s": 1800,
-      "estimate_status": "Будущие design ceilings; SLA p99=180s рабочая цель аналитика, не гарантия worst-case sum трёх generation watchdog по60s+aux. Watchdogs не повышают TIMEOUT_S; H1/H2/H3 проверяют actual p99/TTFT перед rollout.",
+      "estimate_status": "Design targets only, including combined per-slot192MiB child+helper+lsof. EVD-071 idle156.8MiB is not6parallel peak. Normal p99<=180s goal; degraded3x60+51.6=231.6s distinct profile, live H3 NOT_RUN.",
       "pre_spawn_admission_budget_s": 5.0,
@@ -2315,3 +2778,3 @@
       "first_event_anchor": "serve prompt_send_start; first valid current-session execution SSE only; HTTPready/headers/control ignored; O-EXIT first_event_ms measured from request t0",
-      "data_isolation": "per-spawn tempfile XDG_DATA_HOME + finally rmtree, OPENCODE_MODELS_PATH preserved; common DB untouched",
+      "data_isolation": "OPENCODE_DB=:memory:; preserve standard XDG_DATA_HOME/auth; owned zen-serve-state-* state/tmp with finally+crash reaper.",
       "serve_health": {
@@ -2321,3 +2784,24 @@
       },
-      "http_sockets_per_serve_max": 3
+      "http_sockets_per_serve_max": 3,
+      "fd_accounting": {
+        "parent_baseline": 36,
+        "admitted_client_sockets": 18,
+        "serve_http_lanes": 18,
+        "stdout_stderr_drains": 12,
+        "reserved_port_sockets": 6,
+        "lsof_capture_pipes": 6,
+        "parent_watchdog_pipes": 6,
+        "open_lease_files": 6,
+        "parent_upper_bound": 108,
+        "configured_envelope": 128,
+        "aggregate_estimate": "parent128 +6serve*20 +6helper*8 +6lsof*8=344 descriptors system-wide design, per-process parent<=128, not claim aggregate<256. H3 actual per-process FD and system peaks."
+      },
+      "process_accounting": "6serve slots plus <=6parent-pipe stdlib helpers plus<=6lsof (one per active setup, no extra token-free model spawn). Each serve attempt consumes one _RequestAttempts token/spawn-limiter admission and may create exactly one paired helper; all<=3 model attempts/request. Helper/lsof separate owned bounded aux PIDs, never count them as model generations or ignore resource overhead. No lsof on control hot path.",
+      "p99_criteria": {
+        "status": "DESIGN_TARGET_NOT_MEASURED",
+        "normal": "At declared0.2req/s, admitted6active/12waiters, healthy single attempt: empirical end-to-end completion p99<=180.0s including slot/admission/setup/cleanup; H1/H2/H3 record sample count and nearest-rank p99, never infer p99 from3samples.",
+        "degraded": "Bounded synthetic failure-to-first-token profile with three60s watchdog attempts: elapsed<=231.6s (=3*60+51.6 aux), not <=180.0s. Fault-injection batch>=100eligible requests reports nearest-rank p99<=231.6s and cap3; retry budget may stop earlier. First-event-only failure profile3*20+51.6=111.6s. Healthy actual generation+post-token stalls remain under total1800s,231.6 is not universal completion guarantee.",
+        "rollout": "Both normal p99 target and degraded-profile budget must be measured independently; no runtime SLA claim from arithmetic. If normal p99>180 or degraded synthetic p99>231.6, keep disabled and return evidence, do not increase caps/timeouts."
+      },
+      "stall_heartbeat_interval_s": 15.0
     },
@@ -2330,3 +2814,3 @@
       "evidence_level": "design estimate only; NOT measured runtime PASS",
-      "runtime_gate": "H3: actual_parent_RSS_max+6*actual_child_RSS_max<=1638.4MiB; 103KB×6×3; zero database is locked, actual cleanup dirs/FD/CPU; FAIL forbids production enable"
+      "runtime_gate": "H3 sum actual_parent_RSS + RSS(all6serve + allpaired helper + lsof peaks) <=1638.4MiB; combined slot budget192MiB, no hidden helper memory.103KB×6×3, zero sharedDB opens/locks, actual FD/CPU and temp cleanup. Idle156.8MiB not loaded PASS."
     },
@@ -2387,3 +2871,3 @@
         "substitution": "46 exact keys/sources/field_units SSoT§3.0; memory inMiB:1*256+1152=1408<=0.80*2048=1638.4. N/A сохраняет actual diff и transitive graph; runtime H3 NOT_RUN.",
-        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist. Assert memory units exact MiB and actual H3 inequalities separately; bytes вместо MiB FAIL.",
+        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist. Assert memory units exact MiB and actual H3 inequalities separately; bytes вместо MiB FAIL. Recompute parent55admitted threads/108FD<=128, combined helper memory, normal p99 goal180 vs degraded3x60+51.6=231.6 distinct profile. Full-thread peak under arbitrary flood is not bounded by slot count alone.",
         "verification_ids": [
@@ -2397,4 +2881,4 @@
         "status": "PASS",
-        "substitution": "Roles bridge=1 process, M=6 exclusive child leases, G_reload=1 close-before-create; other roles0, no daemon overlap. georouter6<=.60*80=48; opencode_local_db design logical6<=.60*10=6 НЕ физическая SQLite pool quota. Каждый child own XDG_DATA_HOME и own DB, OPENCODE_MODELS_PATH preserved, shared2.27GB DB untouched. Design memory1408<=1638.4MiB, но runtime SQLite/memory PASS только после H3 actual parent+6child<=.80*2048MiB и zero database is locked на103KB×6×3.",
-        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling. Fake XDG dirs unique per spawn and deleted on all exits; H3 real peaks/zero locks обязательны до enable, retry не маскирует lock failure; runtime_status NOT_RUN.",
+        "substitution": "Bridge process1,6 exclusive serve leases,G_reload1; georouter6<=.60*80=48. Logical opencode_local_db6<=.60*10=6 is accounting not vendor pool. OPENCODE_DB=:memory: means0shared SQLite files; auth preserved at standard data dir. Helpers<=6/lsof<=6 bounded separately; combined child/helper/lsof estimate1152MiB and parent256 gives1408<=1638.4MiB, runtime PASS only H3 full sum and0locks.",
+        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling. Fake XDG dirs unique per spawn and deleted on all exits; H3 real peaks/zero locks обязательны до enable, retry не маскирует lock failure; runtime_status NOT_RUN. Unique memory DB / state roots + standard read-only auth paths all3env branches; include helpers in H3 sum.",
         "verification_ids": [
@@ -2434,4 +2918,4 @@
         "status": "PASS",
-        "substitution": "ParentFD128<=.70*65536=45875.2; parent+6children20FD<256 design. control+SSE+prompt=3HTTP sockets per child. node ports3.6*1*60+30=246<=8192; sharedSNAT1.8*1*60+12=120<=8192. Readiness<=3 connects; control reusable. Actual FD/RSS/cleanup/network closure H3 mandatory.",
-        "oracle": "Recompute both scope inequalities, count control connection creation/reuse (50 operations on one owned serve lease ->1 keepalive control TCP), readiness≤3 probes; leak counters FD/start/end stable; H3 измеряет реальные FD/egress.",
+        "substitution": "ParentFD estimate108<=envelope128<=.70*65536=45875.2. Systemwide parent128+6*serve20+6*helper8+6*lsof8=344design (not<256); each process independent ulimit check.3HTTP lanes/serve retained, lsof capture1pipe/helper<=6. Nodeports3.6*60+30=246<=8192; SNAT1.8*60+12=120<=8192.0extra network from lsof/helpers. H3 actualFD/thread/ports required.",
+        "oracle": "Recompute both scope inequalities, count control connection creation/reuse (50 operations on one owned serve lease ->1 keepalive control TCP), readiness≤3 probes; leak counters FD/start/end stable; H3 измеряет реальные FD/egress. Assert one lsof per successful spawn including permission/form/interrupt/DELETE;3forced lsof timeouts count3ServeHealth->DEGRADED, next auto request no serve/helper/lsof Popen. No additional model tokens charged for lsof, but helper process ceilings enforced.",
         "verification_ids": [
@@ -2562,3 +3046,3 @@
         "status": "PASS",
-        "substitution": "Первые serve guards: if disabled or TRANSPORT=run return legacy до UUID/password/clock/queue/threads/probe. Enabled selector проверяет O(1) os.path.exists(disable-file); present ->run до serve allocations/subprocess. auto health-degraded/shebang ->run без probe. Default=true native path не отменяет zero-serve-cost explicit disabled path; legacy watchdog/status остаются RC2/RC3 fixes. Status guard thinking+SSE до format; bounded put_nowait events, overflow explicit error+cleanup; optional telemetry drop counters.",
+        "substitution": "Первые guards: explicit env disabled/TRANSPORT=run ->legacy до stat/UUID/password/clock/queue/threads/probe. Disable-file O(1)/open sticky TTL ->run; force serve только после этих guards. Auto dynamic config stat O(1) cache(mtime_ns,size), unchanged без JSON parsing/reopen, missing/invalid/unreadable/nonbool default=false; enabled native only ->serve. Config reload bounded, selector overhead<1мс — будущий VER005/H9 oracle, не измеренный PASS. Legacy watchdog/status RC2/RC3 остаются; status thinking+SSE guard before format, bounded put_nowait, explicit overflow+cleanup.",
         "oracle": "VER-005 spy explicit0/run/disable-file ->0 serve alloc/password/probe/extra Popen; while same process create/remove file next request toggles transport. Queue overflow explicit cleanup; no disabled UUID/serialization. File stat O(1), no recursive IO.",
@@ -2605,3 +3089,3 @@
         "substitution": "15.0 + 3 * (5.0 + 3.0 + 2.0 + 1.2) + 3.0 = 51.6 s <= 0.30 * 180 = 54.0 s; headroom=2.4s. Slot15 один раз, combined pre-spawn admission5 на attempt, owner/ready3, create+subscribe2, cleanup1.2, суммарный backoff cap1+2=3. Prompt POST/generation под first_event20/first_token60/stall60 и total1800, не session_setup. Каждому I/O timeout=min(phase_remaining,request_remaining); cleanup финальный<=1.2 даже после request deadline. После deadline ни spawn/prompt/sleep.",
-        "oracle": "FakeClock recompute51.6<=54 и headroom>=2.0; admission gate+limiter sum<=5.0, ready3/create+subscribe2/cleanup1.2, prompt POST не входит в2s; slow create timeout ->one budgeted run pre-header; headers received or session event ->zero silent run, Popen<=3. Deadline exhausted->zero further I/O. Никаких leftover gate5+spawn5/ready.5/setup.2.",
+        "oracle": "FakeClock recompute51.6<=54 и headroom>=2.0; admission gate+limiter sum<=5.0, ready3/create+subscribe2/cleanup1.2, prompt POST не входит в2s; slow create timeout ->one budgeted run pre-header; headers received or session event ->zero silent run, Popen<=3. Deadline exhausted->zero further I/O. Никаких leftover gate5+spawn5/ready.5/setup.2. Owner proof0.35 inside ready3s, no lsof in cleanup. Control reconnect0.35 is explicit recovery inside execution budget, never urgent-reply/cleanup SLA; urgent failure kills instead. Normal p99 and degraded231.6s criteria separate.",
         "verification_ids": [
@@ -2623,3 +3107,3 @@
         "substitution": "Model _UpstreamBreaker threshold5/cooldown10*U(.8,1.2), HALF_OPEN1 owner не освобождается по одному cooldown до terminal/cleanup; provider failures/успешное восстановление как прежде. Отдельный _ServeHealth threshold3/TTL120/one recovery probe для serve protocol-only failures; first_event_timeout без session execution и invalid_serve_event НЕ model breaker failure, subsequent auto->run. Accepted current prompt не получает silent run fallback. Auth/permission/security401/403 fail-closed, no policy switch; client cancel neutral. TTL/run skips не продлевают outage; native binary key change инвалидирует capability/health. Resource/retry/slot caps едины.",
-        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret. Отдельно five serve-protocol failures forced mode ->model breaker closed, no .failure calls; auto third failure arms120s,next auto run, no silent replay current request; atTTL exactly1probe, success resets, failed protocol rearms120; provider5 failures still open model breaker.",
+        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret. Отдельно five serve-protocol failures forced mode ->model breaker closed, no .failure calls; auto third failure arms120s,next auto run, no silent replay current request; atTTL exactly1probe, success resets, failed protocol rearms120; provider5 failures still open model breaker. Parametrize AD-001 fallback_decision_table rows exactly, counters once/cause. preheader20s->budgeted run, afterheader20s->explicit serve_retry; HTTP401/403 neverfallback; local preprompt5xx transport vs promptprovider5xx model. lsof proof timeout3->TTLrun/modelbreaker0.",
         "verification_ids": [
@@ -2676,4 +3160,4 @@
       "status": "PASS",
-      "substitution": "Request/attempt ownership включает PGID, stdout/stderr, SSE/control sockets, session id, queue/readers и startup gate. AD-003 cleanup на всех exits<=1.2s, child group reap; leader early-exit не оставляет grandchildren. Server shutdown manager запрещает новые leases и отменяет все активные, затем closes all. Ownership включает isolated XDG_DATA_HOME и daemon delivery socket/thread; finally rmtree owned dir после kill/reap, never common DB. Foreign listener cleanup no API/kill to foreign PID.",
-      "oracle": "VER-005: 50 cancellations + leader-exits-first descendant + blocked socket/readiness + partial prompt + overload/shutdown; zero active/waiters/children/readers/sockets; PIDs/PGIDs только свои. Assert unique data dirs and deleted after all50 cancellations/partial prompt/port race; join delivery reader and no owned temp dirs.",
+      "substitution": "Normal attempt owns childPGID,control/SSE/prompt lanes,12drains bound,helper pipe/process,session and memoryDB/state root; cleanup<=1.2s includes API.2/TERM.5/reap-join-temp-lease.5. SIGKILL bypasses finally: parent-pipe helper then startup lease reaper validates ownerUID,parent/childPID start_ts,PGID,cmd/binary/port and temp inode; no name-wide kill, no removal without manifest. Standard XDG_DATA_HOME never deleted.",
+      "oracle": "VER-005 both original50cancellations and hard-parent-death→next-start reaper, killed parent before/after READY, failed helper, PID reuse/foreign UID/PGID/symlink/foreign dir negatives.0old owned serve/descendant/helper/temp roots;0active/waiter/socket/reader counts. H0/H9 actual kickstart-k NOT_RUN.",
       "verification_ids": [
@@ -2684,3 +3168,3 @@
       "status": "PASS",
-      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется. first_event_ms только valid current-session execution SSE после prompt, относительно request t0; HTTPready/POST headers не являются first_event. transport_history/reason раздельно protocol/model/security/TTL, no phantom spawns.",
+      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется. first_event_ms только valid current-session execution SSE после prompt, относительно request t0; HTTPready/POST headers не являются first_event. transport_history/reason раздельно protocol/model/security/TTL, no phantom spawns. REQ-016/AC-021 authorize listed fields; fallback reason in adjacent BRIDGE-TRANSPORT/v1 diagnostic if strict O-EXIT parser; never rename/remove existing keys/types. Always log transport=serve|run with redacted cause; /health unchanged.",
       "oracle": "VER-005 table all exits incl 400/401/404/503/circuit, overflow, error, abort, successful retry; deterministic fake clock, no secret reflection.",
@@ -2740,3 +3224,3 @@
         "path": "cleanup",
-        "timeout_budget": "interrupt+delete<=.2,TERM grace<=.5,reap/join delivery+SSE+owned rmtree within remaining .5; total<=1.2, bounded even on deadline",
+        "timeout_budget": "Existing verified Keep-Alive control only: interrupt<=.09+DELETE<=.09+.02 scheduling=.20;TERMgrace<=.50;all reap/join/helper/temp/lease<=.50;total1.20. No lsof/reconnect on cleanup.",
         "bulkhead": "only own session/PGID, no new leases",
@@ -2762,8 +3246,8 @@
       {
-        "dependency_operation": "serve permission rejection",
+        "dependency_operation": "serve permission reject / form cancel / single-turn interrupt",
         "path": "hot/control",
-        "timeout_budget": "Immediate control reply<=.25s capped request/phase remaining, never queued behind prompt response",
+        "timeout_budget": "reject or form cancel<=.25 from event, then interrupt<=.10; no await prompt/lsof/reconnect; second-step output barrier immediate.",
         "bulkhead": "Use one idle control connection; delivery worker uses separate bounded prompt socket, <=3 sockets per active serve",
         "circuit_breaker": "Security fail-closed, not model/protocol fallback",
-        "failure_mode_fallback": "permission.asked ->decision=reject; missing endpoint/bad reply401/403 ->cleanup+explicit error; never allow/once/always"
+        "failure_mode_fallback": "permission.asked->decision reject OR nested form.created->cancel; then immediate interrupt. Control failure ->fail-closed+group kill, no allow, no Step2 output."
       }
@@ -2992,10 +3476,10 @@
   "handoff_state": {
-    "architecture_contract": "Cycle2 fix-from-panel candidate APPROVED; 14 RW+7 FU resolved at design level, R2 council verdict и ARCH_GATE не выносятся этой ролью",
-    "implementation_tests": "NOT_RUN — код/tests Stage3 ещё не создавались",
-    "live_acceptance": "NOT_RUN — H0..H9 отдельно; не менять ~/.dsh",
+    "architecture_contract": "Cycle3 APPROVED architecture candidate for external a3,6RW+8FU design resolutions; no Council verdict/ARCH_GATE_PASS from author.",
+    "implementation_tests": "NOT_RUN; Stage3a GroupA then3b GroupB and independent VER001..005 required.",
+    "live_acceptance": "NOT_RUN allH0..H9; policy compliant default=false/runtime H7, human exception NOT_REQUIRED; ~/.dsh not touched by Architect.",
     "pending_orchestrator_actions": [
-      "Council R2 по diff v1→v2 и rework_resolutions; отдельные launch_seat/verify_panel_proof",
-      "Обновить task envelope packet/surface hashes и проверить ARCH_GATE с новыми role-plan/fingerprints (вне трёх разрешённых файлов роли)",
-      "Stage3 Coder, independent clean-room strict VER001..005",
-      "H3/H6 safety gates до production sync; H0..H9 live acceptance, ещё NOT_RUN"
+      "External a3 council on v2→v3 diff with independent launch_seat/verify_panel_proof; no author vote.",
+      "Validate finalized cycle3b packet and independent a3 council; FU007 policy compliant, no human waiver; no author Council vote.",
+      "Update envelope/fingerprints/hashes after council; outside three-file Architect allowlist.",
+      "Only then Stage3a/3b+C clean-room verification and H0..H9: dark absent/false through H4/H5, H7 runtime true after H3/H6."
     ]
@@ -3003,6 +3487,6 @@
   "verification_acceptance_matrix": {
-    "FakeServe": "Stdlib subprocess implements exact frozen_v2_1_2_fixtures API/SSE, Basic401, /api/session/active, /openapi.json only per binary-key first handshake, session/prompt/interrupt/delete/permission decision=reject. Tests force serve for shebang; no Zen calls. Independent fixed fixture digest oracle + deliberate field/schema mutations; fake/adapter mutual agreement alone insufficient. GET active returns {data:{}} not[]; once-per-key /api/info version+PID and API schema info.version0.0.1, independent binary appversion2.1.2; invalid numeric error.status must fail validation.",
+    "FakeServe": "Stdlib subprocess implements exact frozen_v2_1_2_fixtures API/SSE, Basic401, /api/session/active, /openapi.json only per binary-key first handshake, session/prompt/interrupt/delete/permission decision=reject. Tests force serve for shebang; no Zen calls. Independent fixed fixture digest oracle + deliberate field/schema mutations; fake/adapter mutual agreement alone insufficient. GET active returns {data:{}} not[]; once-per-key /api/info version+PID and API schema info.version0.0.1, independent binary appversion2.1.2; invalid numeric error.status must fail validation. Six families now include form.created.data.form and form.cancelled.data; replies support cancel and immediate interrupt, freeze negative fixture expectations independently.",
     "mode_matrix": [
-      "default flag=true+auto+native MachO ->serve после safety rollout; shebang fake ->run once no probe, all378baseline existing tests target green",
-      "explicit flag0/false or TRANSPORT=run ->run before serve allocations/stat/probe; enabled disable-file present ->run after one O(1)exists; create/remove file same process toggles next request without restart",
+      "Code default=false + git runtime JSON absent ->run for all378baseline (REQ003/AC004). Runtime boolean true/env1true + native MachO ->serve only after rollout H7/H3/H6; enabled shebang fake ->run without probes unless explicit test override.",
+      "First priority TRANSPORT=run/env0falseNoOff/disable-file/sticky TTL ->run; then force serve with no silent fallback; then auto boolean dynamic config/envtrue AND native eligibility. Same-process config true/false/deletion and malformed/unreadable/nonboolean fail-safe false; unchanged stat key no reopen, warning redacted; no Server restart.",
       "force serve+FakeServe shebang ->v2 SSE/JSON, stdinDEVNULL; fake legacy blocking stdin ->EOF/ready failure<=3s explicit no silent run",
@@ -3022,3 +3506,4 @@
       "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes",
-      "Model reasoning chunk без trailingLF ->synthetic delta \"\\n[мост] ...\\n\"; whole delta incl leading LF provenance=synthetic, model-only concatenation exact bytes, literal model [мост] survives; LF already present->no redundant prefix; fast Simple greeting.->zero statuses."
+      "Model reasoning chunk без trailingLF ->synthetic delta \"\\n[мост] ...\\n\"; whole delta incl leading LF provenance=synthetic, model-only concatenation exact bytes, literal model [мост] survives; LF already present->no redundant prefix; fast Simple greeting.->zero statuses.",
+      "After first model token pause>=15s mandatory waiting-continuation heartbeat every15s; silence threshold explicit, not optional5s. Firsttoken wait remains5s; status does not reset stall60."
     ],
@@ -3040,3 +3525,5 @@
       "Foreign listener PID/PGID after reserve-release ->zero Authorization/password/prompt bytes, no foreign API/kill; bounded port retry ready3s and totalspawns<=3.",
-      "Unique per-spawn XDG_DATA_HOME across6parallel/retries; _run_env bytehash unchanged, OPENCODE_MODELS_PATH retained; finally tempdir removed after all exits, 50cancel cycles and deliveryworker cleanup."
+      "Unique per-spawn zen-serve-state-* state/TMPDIR; OPENCODE_DB=:memory: on ALL3 branches, standard XDG_DATA_HOME/auth/model config retained; finally remove owned root+lease;50cancels + hard-parent-kill→helper/reaper restore0old processes/temp, foreign objects untouched.",
+      "VER-005 GroupB: hard kill parent after spawn before READY, after lease publish, during prompt; helper EOF cleanup, plus disabled-helper/reaper recovery on next bridge start;0 old owned serve/descendants/helper/temp dirs, foreign PID/PGID/start-time-reuse and foreign directories untouched. Normal50cancel counters remain0. H0/H9 actual kickstart -k tests still NOT_RUN.",
+      "1lsof per spawn then Keep-Alive; takeover beforeREADY0Authorization/prompt bytes, no foreign signals; control reconnect proof separate.35s, never lsof/repair in urgent control/cleanup."
     ],
@@ -3051,3 +3538,7 @@
       "permission.asked {data.id,sessionID,action,resources,source} ->POST reply {decision:reject},status204; both ask_reject/deny modes; POST prompt may stayblocked while reject executes on separate control socket; never once/always/allow.",
-      "Frozen wire tokens.cache.read/write ->canonical tokens{input,output,cached=cache.read,reasoning}; mutate delta path/cache envelope/permission lifecycle ->independent oracle fail, step assistantMessageID dedup, not invented wire stepID."
+      "Frozen wire tokens.cache.read/write ->canonical tokens{input,output,cached=cache.read,reasoning}; mutate delta path/cache envelope/permission lifecycle ->independent oracle fail, step assistantMessageID dedup, not invented wire stepID.",
+      "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side. On input.ended save $.data.text and parse JSON as object with runtime validation. Prefer called.data.input if present and valid; if called absent before failed/step.ended use completed input.ended.text, including streaming→failed. Never emit partial JSON; dedup by sessionID/assistantMessageID/call id. Both paths give identical mapped DSH tool_calls. Invalid JSON follows existing incomplete/unmapped recovery, not invented empty args.",
+      "form.created uses data.form.sessionID/id (Form.Info nested); validate own session before action. Cancel immediately via POST /api/session/{id}/form/{formID}/cancel, no answer/allow; form.cancelled data.id/sessionID settles same form. Not a model token/first-event. Error->security fail-closed+kill. See single_turn_control.",
+      "permission reject and form cancel MUST immediately interrupt; Step2 output0 even if emitted concurrently, completed input.ended JSON tool mapping same as called.input. Cancel/reject failure fail-closed.",
+      "Env secret-sentinel matrix standalone/opencode-go/base_url/static;0parent API_KEY/TOKEN/SECRET/arbitrary env, required config/models/auth preserved."
     ],
@@ -3056,3 +3547,4 @@
       "fresh _Resilience/_RetryBudget per test, reverse fixed ordering plus isolated/full runner",
-      "all17 existing modules untouched except the3 acknowledged assertions/isolation in test_step_interruption; no Google changes"
+      "all17 existing modules untouched except the3 acknowledged assertions/isolation in test_step_interruption; no Google changes",
+      "AC-026 / VER-005 / Clean-Room L2: tests/test_realtime_reasoning.py создаёт tmp_path / \"dynamic_config.json\" с {\"REALTIME_SERVE_ENABLED\":true}; monkeypatch.setattr(server, \"DYNAMIC_CONFIG_PATH\", cfg_path, raising=False). При переносе только этого testfile на непропатченный origin/dev нет AttributeError: реально POST /v1/chat/completions, RED именно на поведенческих realtime chunk intervals (чтение socket до upstream release), GREEN на новом коде. Та же Server instance: атомарно false в cfg_path ->следующий запрос run без restart; true ->serve при test eligibility override/native, deletion/invalid JSON/nonbool/unreadable ->false; unchanged (st_mtime_ns,st_size) ->нет reopen. Новый cfg stat key для переключения обеспечивается и проверяется тестом, без sleep-предположений. Existing378 tests не создают JSON и остаются run. Runtime результаты NOT_RUN."
     ],
@@ -3067,5 +3559,8 @@
       "_ServeHealth force5protocol failures ->zero model breakerfail; auto3failures->next run untilTTL120, expiry oneprobe, successful terminalreset, protocolfailrearm; binarymtime+size change invalidates capability; real provider5 failures modelbreakerOPEN.",
-      "Memory SSoT fields2048/256/1152 MiB exactly; design1408<=1638.4 not H3PASS.3HTTP sockets per serve supports immediate reject while promptHTTP pending; recalc nodeports246<=8192."
+      "Memory SSoT fields2048/256/1152 MiB exactly; design1408<=1638.4 not H3PASS.3HTTP sockets per serve supports immediate reject while promptHTTP pending; recalc nodeports246<=8192.",
+      "Parent admitted threads55=1+18+6+6+6+12+6;parentFD108<=128, auxiliary processes6helper+6lsof included. Arbitrary rejected handler peak measured H3, not claimed bounded by slots.",
+      "All phase×event actions and two health counter effects match fallback_decision_table; changedmtime+same used-schema projection->serve, mismatch->run+diagnostic;permission capability gap fail-closed.",
+      "Normal p99<=180 goal measured separately; three60s firsttoken faultprofile+aux51.6<=231.6,>=100sample batch nearest-rank criterion. Universal TIMEOUT1800 unchanged."
     ],
-    "rollout_boundary": "VER001..005 не обращаются к ~/.dsh. В root suite test_dsh_profile_config видит отсутствие live profile в clean-room и делает inherited skip. Actual REQ019 identity и H0..H9 отдельный rollout gate; fake digest fixture не подменяет read-back deployed file. Default=true не bypass: pre-production candidate H3/H6 mandatory, file disabled until safety PASS; H3 actualRSS + no DB locks103KB×6×3. H9 toggles file withoutrestart in existing chat. All H NOT_RUN in Stage2."
+    "rollout_boundary": "Все H0..H9 NOT_RUN, external a3 ACCEPT+panel proof и независимые VER gates обязательны; Architect не выполняет rollout. H0 BLOCKING до sync/restart: проверить текущий env не force serve/true, отсутствие production dynamic_config.json либо boolean false; при прежнем enabled состоянии атомарно записать false, проверить read-back; дополнительный disable-serve разрешён. Снять старые PID/start/lease identity. H4 sync/read-back server.py hash; H5 launchctl kickstart с config absent/false: сразу dark run без окна serve; startup reaper0 старых собственных serve/helper/temp roots, чужие процессы untouched. На отдельном кандидате test-local dynamic_config.json=true и отдельный disable-file path: provider-free info/active, H3 реальные6parallel RSS/FD+OPENCODE_DB=:memory:, H6 live permission/tool isolation, Stage3a/A затем3b/B. На production до H7 run. H7 ТОЛЬКО после PASS H3 и H6: при env auto без explicit false и закрытом TTL подготовить tempfile в ~/.dsh/bridges/opencode-zen-bridge/,0600, записать {\"REALTIME_SERVE_ENABLED\":true}, os.replace в dynamic_config.json; убедиться дополнительный disable-serve отсутствует. Следующий native auto запрос на :9883 использует serve без правки start.sh и без повторного рестарта LaunchAgent. H8 повторяет живые проверки рабочего чата, H9 проверяет runtime false/true и disable-file same PID, отдельно kickstart-k crash recovery. Никакой выдачи design/NOT_RUN за runtime PASS."
   },
@@ -3077,10 +3572,10 @@
     "decisions": "4/4 two-way with >=2 genuine alternatives",
-    "evidence_refs": "64 unique EVD IDs; analyst49 F-01..F-49 неизменны; council refs отдельный PANEL-F-NNN namespace; invalid analyst refs запрещены.",
+    "evidence_refs": "69 EVD records,49analyst facts; provided070..072, source073, panel074 clearly separated. EVD ids intentionally retain gap065..069; no fabricated missing observations.",
     "status_protocol": "3 templates begin[мост]/endLF; при model unterminated line весь дополнительный leading LF synthetic, template bytes модели не менять.",
     "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes.",
-    "VER_004_syntax": "Strict command compiled with ast.parse in cycle2; execution pending Stage3 because new test file absent",
-    "rework_coverage": "14RW+7FU exactly once in rework_resolutions; source_findings uses PANEL-F-NNN; resolved means architecture delta, NOT implementation/runtime PASS",
+    "VER_004_syntax": "ast.parse PASS and changed-hunk regex tested for count+singleton; embedded commands NOT_RUN because new file NOT_PRESENT. Full3files independent Stage3/L2 required.",
+    "rework_coverage": "Exactly6RW+8FU a2,16sourcefindings eachonce in rework_resolutions_a2; rework_resolutions is compatibility alias, not additional closures.21a1 historicalrecords retained.",
     "memory_units": "All46 canonical keys+field_sources+field_units; memory2048/256/1152 MiB;1408<=1638.4MiB",
     "aux_budget": "15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; old independent5+5/.5/.2 absent",
-    "wire_evidence": "Actual binary2.1.2 permission.asked/decision=reject and cache.read/write normalized explicitly; fixture SHA256 locked; five families independent adapter/mock oracle Readiness data map and appversion/api schema version separated; StructuredError.status numeric mapping frozen."
+    "wire_evidence": "Sixfamilies, source Form.Info wrapper verified; delta/token/permission old literals unchanged; new digest calculated deterministically; candidate runtime NOT_RUN."
   },
@@ -3094,3 +3589,3 @@
       "source_positions": [
-        "PANEL-F-001: headers response barrier",
+        "PANEL-A1-F-001: headers response barrier",
         "RW-001.evidence: Seat2 начало POST barrier"
@@ -3104,4 +3599,4 @@
       "source_positions": [
-        "PANEL-F-002: допускается один safe policy transition до prompt",
-        "PANEL-F-018: unsupported policy fail-closed без auto-switch"
+        "PANEL-A1-F-002: допускается один safe policy transition до prompt",
+        "PANEL-A1-F-018: unsupported policy fail-closed без auto-switch"
       ],
@@ -3115,6 +3610,6 @@
       "source_positions": [
-        "PANEL-F-006: H3 обязателен до включения",
-        "PANEL-F-010: default=true без start.sh"
-      ],
-      "resolution": "Default=true сохранён в коде design; candidate H3/H6 до production sync, боевой file switch удерживается до допуска. Нельзя сначала включить default, а потом искать RSS."
+        "PANEL-A1-F-006: H3 обязателен до включения",
+        "PANEL-A1-F-010: default=true без start.sh"
+      ],
+      "resolution": "Историческое a1 требование default=true superseded compliant delta cycle3b: кодовый default=false, runtime JSON absent/false до H7. Активация :9883 атомарным true после H3/H6 без start.sh/restart;378legacy идут run. Источник a1 сохраняется как история, без human waiver."
     },
@@ -3126,4 +3621,4 @@
       "source_positions": [
-        "PANEL-F-012: канон MiB, byte арифметика недостаточна",
-        "PANEL-F-013: strict0error вместо старого allowance"
+        "PANEL-A1-F-012: канон MiB, byte арифметика недостаточна",
+        "PANEL-A1-F-013: strict0error вместо старого allowance"
       ],
@@ -3143,3 +3638,14 @@
   ],
-  "rework_resolutions": [
+  "rework_source": {
+    "path": "handoff/panel-rework-brief-arch-a2.json",
+    "sha256": "baa297e7819579dc1cf779af370b16f385a7ede77d9538553713212b1475dc7f",
+    "base_packet_path": "architecture/architecture-packet.v2.json",
+    "base_packet_sha256": "c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d",
+    "resolutions_count": 14,
+    "blocking_count": 6,
+    "nonblocking_count": 8,
+    "findings_count": 16,
+    "namespace": "a2 current rework_resolutions alias mirrors rework_resolutions_a2; a1 history in rework_resolutions_a1; IDs are unique within pass, not counted twice through alias."
+  },
+  "rework_resolutions_a1": [
     {
@@ -3147,3 +3653,3 @@
       "source_findings": [
-        "PANEL-F-001"
+        "PANEL-A1-F-001"
       ],
@@ -3157,3 +3663,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3162,5 +3670,5 @@
       "source_findings": [
-        "PANEL-F-002",
-        "PANEL-F-007",
-        "PANEL-F-018"
+        "PANEL-A1-F-002",
+        "PANEL-A1-F-007",
+        "PANEL-A1-F-018"
       ],
@@ -3174,3 +3682,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3179,3 +3689,3 @@
       "source_findings": [
-        "PANEL-F-003"
+        "PANEL-A1-F-003"
       ],
@@ -3189,3 +3699,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3194,3 +3706,3 @@
       "source_findings": [
-        "PANEL-F-004"
+        "PANEL-A1-F-004"
       ],
@@ -3203,3 +3715,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3208,3 +3722,3 @@
       "source_findings": [
-        "PANEL-F-005"
+        "PANEL-A1-F-005"
       ],
@@ -3217,3 +3731,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3222,3 +3738,3 @@
       "source_findings": [
-        "PANEL-F-006"
+        "PANEL-A1-F-006"
       ],
@@ -3232,3 +3748,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3237,3 +3755,3 @@
       "source_findings": [
-        "PANEL-F-008"
+        "PANEL-A1-F-008"
       ],
@@ -3248,3 +3766,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3253,3 +3773,3 @@
       "source_findings": [
-        "PANEL-F-009"
+        "PANEL-A1-F-009"
       ],
@@ -3263,3 +3783,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3268,6 +3790,6 @@
       "source_findings": [
-        "PANEL-F-010"
-      ],
-      "status": "RESOLVED",
-      "changes_made": "Default=true+auto native, shebang directrun all378baseline target; file disable no restart. Candidate H3/H6 before prod sync+held disable-file reconciles mandatory safety gate.",
+        "PANEL-A1-F-010"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
       "packet_locations": [
@@ -3276,5 +3798,10 @@
         "#/evolution/rollout",
-        "#/evolution/feature_flag"
-      ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+        "#/evolution/feature_flag",
+        "#/evolution/rollback",
+        "#/approval"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true,
+      "decision_required_human": false
     },
@@ -3283,7 +3810,7 @@
       "source_findings": [
-        "PANEL-F-011",
-        "PANEL-F-016"
-      ],
-      "status": "RESOLVED",
-      "changes_made": "Tool-policy reference corrected to EVD-050+F-08; analyst IDs restricted49 facts, council refs PANEL-F-NNN.",
+        "PANEL-A1-F-011",
+        "PANEL-A1-F-016"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Tool-policy reference corrected to EVD-050+F-08; analyst IDs restricted49 facts, council refs PANEL-A1-F-NNN.",
       "packet_locations": [
@@ -3293,3 +3820,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3298,3 +3827,3 @@
       "source_findings": [
-        "PANEL-F-012"
+        "PANEL-A1-F-012"
       ],
@@ -3309,3 +3838,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3314,3 +3845,3 @@
       "source_findings": [
-        "PANEL-F-013"
+        "PANEL-A1-F-013"
       ],
@@ -3323,3 +3854,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3328,3 +3861,3 @@
       "source_findings": [
-        "PANEL-F-017"
+        "PANEL-A1-F-017"
       ],
@@ -3337,3 +3870,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3342,3 +3877,3 @@
       "source_findings": [
-        "PANEL-F-019"
+        "PANEL-A1-F-019"
       ],
@@ -3353,3 +3888,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3358,3 +3895,3 @@
       "source_findings": [
-        "PANEL-F-014"
+        "PANEL-A1-F-014"
       ],
@@ -3367,3 +3904,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3372,3 +3911,3 @@
       "source_findings": [
-        "PANEL-F-015"
+        "PANEL-A1-F-015"
       ],
@@ -3380,3 +3919,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3385,3 +3926,3 @@
       "source_findings": [
-        "PANEL-F-020"
+        "PANEL-A1-F-020"
       ],
@@ -3393,3 +3934,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3398,3 +3941,3 @@
       "source_findings": [
-        "PANEL-F-021"
+        "PANEL-A1-F-021"
       ],
@@ -3405,3 +3948,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3410,3 +3955,3 @@
       "source_findings": [
-        "PANEL-F-022"
+        "PANEL-A1-F-022"
       ],
@@ -3418,3 +3963,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3423,3 +3970,3 @@
       "source_findings": [
-        "PANEL-F-023"
+        "PANEL-A1-F-023"
       ],
@@ -3432,3 +3979,5 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     },
@@ -3437,3 +3986,3 @@
       "source_findings": [
-        "PANEL-F-024"
+        "PANEL-A1-F-024"
       ],
@@ -3445,6 +3994,8 @@
       ],
-      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN.",
+      "pass": "a1",
+      "historical": true
     }
   ],
-  "rework_source": {
+  "rework_source_a1": {
     "path": "handoff/panel-rework-brief-arch-a1.json",
@@ -3456,4 +4007,532 @@
     "nonblocking_count": 7,
-    "namespace": "Analyst F-01..F-49; council PANEL-F-001..024 = original brief finding ids prefixed PANEL-; RW/FU IDs unchanged"
-  }
+    "namespace": "Analyst F-01..F-49; council PANEL-A1-F-001..024 = original brief finding ids prefixed PANEL-; RW/FU IDs unchanged"
+  },
+  "rework_resolutions_a1_note": "Historical a1 closure record retained; empty-XDG mechanism superseded by a2 RW002 memoryDB/auth, full-file format/no nonAny margin superseded RW001, default-enable approval clarified FU007. Original safety/bytehash/cap3/no-silent-replay/permission/units/status semantics retained. Histories are not current runtime PASS. Cycle3b supersedes default=true in historical a1 RW009 with code default=false and H7 runtime JSON, no human waiver; a1 source positions remain historical.",
+  "rework_resolutions_a2": [
+    {
+      "id": "RW-001",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-001",
+        "PANEL-A2-F-009"
+      ],
+      "changes_made": "Исполнимый VER004: full new-file/range legacy formatter, server-only exact E402 allowance, temporary /tmp bridge import-root,3legacy type error sites and explicit nonAny budgets; bytehash/Google oracle unchanged.",
+      "packet_locations": [
+        "#/verification_surface/3",
+        "#/decisions/0/details/typing",
+        "#/decisions/0/details/immutable_run_env",
+        "#/risks/7",
+        "#/evidence/66"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-002",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-002",
+        "PANEL-A2-F-007"
+      ],
+      "changes_made": "OPENCODE_DB=:memory:,120.7ms/156.8MiB/0db EVD071; preserve standard auth/models/config, owned state+TMPDIR; /api/info preflight and real provider auth explicitly pending.",
+      "packet_locations": [
+        "#/decisions/0/details/data_isolation",
+        "#/decisions/0/details/serve_env_sanitization",
+        "#/assumptions/0",
+        "#/risks/2",
+        "#/evolution/H3_rollout_gate",
+        "#/evidence/65"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-003",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-003"
+      ],
+      "changes_made": "Nested form.created→cancel<=.25s, sixth frozen family, input.ended.text fallback, reject/cancel→immediate interrupt with Step2 output barrier and mapped calls/recovery.",
+      "packet_locations": [
+        "#/decisions/0/details/single_turn_control",
+        "#/decisions/0/details/session_wire/form_cancel",
+        "#/decisions/0/details/event_contract",
+        "#/decisions/3/details/step",
+        "#/threat_model/threats/1"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-004",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-004"
+      ],
+      "changes_made": "One lsof SPAWN→READY0.35s,3 persistent HTTP/1.1 lanes with proc.poll guard; explicit reconnect outside urgent/cleanup budgets, foreign listener0leak/0kill.",
+      "packet_locations": [
+        "#/decisions/0/details/listener_ownership",
+        "#/decisions/0/details/session_wire/cleanup",
+        "#/decisions/2/details/cleanup",
+        "#/resilience_gates/C_MULT/C-MULT-I5"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-005",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-005"
+      ],
+      "changes_made": "Exact allowlist on all3_run_env branches before child-only secrets/overrides; OPENCODE_ZEN_BRIDGE_* and arbitrary parent secret sentinels absent, required routing/auth preserved.",
+      "packet_locations": [
+        "#/decisions/0/details/serve_env_sanitization",
+        "#/threat_model/threats/2",
+        "#/verification_acceptance_matrix/tools_matrix"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-006",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-006"
+      ],
+      "changes_made": "Atomic UID-scoped lease + parent-pipe helper and safe startup reaper, ps/PGID/start-time/binary/port/inode checks; hard-kill→next-start cleanup oracle and foreign-object negatives, H0/H9 NOT_RUN.",
+      "packet_locations": [
+        "#/decisions/0/details/crash_recovery",
+        "#/resilience_gates/T_LIFE_v1",
+        "#/verification_surface/4/orphan_oracles",
+        "#/evolution/H0_precondition",
+        "#/evolution/H9_crash_recovery_gate"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-001",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-008"
+      ],
+      "changes_made": "Owner proof errors counted once,3timeouts→DEGRADED; --port0 stdout considered unverified alternative; one bounded lsof/helper resource accounting included.",
+      "packet_locations": [
+        "#/decisions/0/details/transport_health/counted_failures",
+        "#/decisions/0/alternatives",
+        "#/high_load_envelope/operational_profile/thread_accounting",
+        "#/resilience_gates/C_MULT/C-MULT-I5"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-002",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-010"
+      ],
+      "changes_made": "EVD070 actual supplied378tests/122.956s/0imports/3knownfailures frombridge cwd; no17module edits needed, future full-green gate preserved.",
+      "packet_locations": [
+        "#/verification_surface/1/baseline",
+        "#/evidence/64"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-003",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-011"
+      ],
+      "changes_made": "Changed binary stat key revalidates used schema projection; same hash remains serve, mismatch run+reason; expected schema fixture independent. REQ016/AC021 authorized fields preserved, detail diagnostic adjacent if strict parser.",
+      "packet_locations": [
+        "#/decisions/0/details/protocol_compatibility",
+        "#/decisions/2/details/telemetry",
+        "#/resilience_gates/O_EXIT_v1"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-004",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-012"
+      ],
+      "changes_made": "Explicit phase/event→fallback/retry/fail and ServeHealth/model counter table, including20s pre-/post-header no-event; any headers latchDELIVERED before classification.",
+      "packet_locations": [
+        "#/decisions/0/details/fallback_decision_table",
+        "#/decisions/0/details/fallback_barrier",
+        "#/decisions/2/details/retry",
+        "#/resilience_gates/R_BULK/R-BULK-I3"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-005",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-013"
+      ],
+      "changes_made": "REQ004/005 match thinking eligibility/grace.30,fast/off/JSON exclusions and immutable model bytes; mandatory post-token stall heartbeat threshold/interval15s, no watchdog resets.",
+      "packet_locations": [
+        "#/requirements/3",
+        "#/requirements/4",
+        "#/decisions/1/details/lifecycle",
+        "#/decisions/1/details/STALL_HEARTBEAT_INTERVAL_S",
+        "#/contract_deltas/0"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-006",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-014"
+      ],
+      "changes_made": "18admittedhandlers+readers/delivery/12drains/supervisors/watchdogs→55parentthreads;108FD<=128,helper/lsof process/memory included; normalp99goal180 vs degraded3*60+51.6=231.6 separately measured, flood caveat explicit.",
+      "packet_locations": [
+        "#/high_load_envelope/operational_profile/thread_accounting",
+        "#/high_load_envelope/operational_profile/fd_accounting",
+        "#/high_load_envelope/operational_profile/p99_criteria",
+        "#/high_load_envelope/memory_closure_check",
+        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-007",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-015"
+      ],
+      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
+      "packet_locations": [
+        "#/approval",
+        "#/assumptions/2",
+        "#/assumptions/3",
+        "#/evolution/H0_precondition",
+        "#/evolution/rollout",
+        "#/decisions/0/details/configuration",
+        "#/evolution/rollback"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-008",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-016"
+      ],
+      "changes_made": "Considered split3a/3b delivery, one branch/MR for owner realtime outcome with staged execution. GroupA RC2/RC3 requires noFakeServe; GroupB independent tests localize serve failures.",
+      "packet_locations": [
+        "#/decisions/0/alternatives",
+        "#/verification_surface/4/groups"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    }
+  ],
+  "rework_resolutions": [
+    {
+      "id": "RW-001",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-001",
+        "PANEL-A2-F-009"
+      ],
+      "changes_made": "Исполнимый VER004: full new-file/range legacy formatter, server-only exact E402 allowance, temporary /tmp bridge import-root,3legacy type error sites and explicit nonAny budgets; bytehash/Google oracle unchanged.",
+      "packet_locations": [
+        "#/verification_surface/3",
+        "#/decisions/0/details/typing",
+        "#/decisions/0/details/immutable_run_env",
+        "#/risks/7",
+        "#/evidence/66"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-002",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-002",
+        "PANEL-A2-F-007"
+      ],
+      "changes_made": "OPENCODE_DB=:memory:,120.7ms/156.8MiB/0db EVD071; preserve standard auth/models/config, owned state+TMPDIR; /api/info preflight and real provider auth explicitly pending.",
+      "packet_locations": [
+        "#/decisions/0/details/data_isolation",
+        "#/decisions/0/details/serve_env_sanitization",
+        "#/assumptions/0",
+        "#/risks/2",
+        "#/evolution/H3_rollout_gate",
+        "#/evidence/65"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-003",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-003"
+      ],
+      "changes_made": "Nested form.created→cancel<=.25s, sixth frozen family, input.ended.text fallback, reject/cancel→immediate interrupt with Step2 output barrier and mapped calls/recovery.",
+      "packet_locations": [
+        "#/decisions/0/details/single_turn_control",
+        "#/decisions/0/details/session_wire/form_cancel",
+        "#/decisions/0/details/event_contract",
+        "#/decisions/3/details/step",
+        "#/threat_model/threats/1"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-004",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-004"
+      ],
+      "changes_made": "One lsof SPAWN→READY0.35s,3 persistent HTTP/1.1 lanes with proc.poll guard; explicit reconnect outside urgent/cleanup budgets, foreign listener0leak/0kill.",
+      "packet_locations": [
+        "#/decisions/0/details/listener_ownership",
+        "#/decisions/0/details/session_wire/cleanup",
+        "#/decisions/2/details/cleanup",
+        "#/resilience_gates/C_MULT/C-MULT-I5"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-005",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-005"
+      ],
+      "changes_made": "Exact allowlist on all3_run_env branches before child-only secrets/overrides; OPENCODE_ZEN_BRIDGE_* and arbitrary parent secret sentinels absent, required routing/auth preserved.",
+      "packet_locations": [
+        "#/decisions/0/details/serve_env_sanitization",
+        "#/threat_model/threats/2",
+        "#/verification_acceptance_matrix/tools_matrix"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "RW-006",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-006"
+      ],
+      "changes_made": "Atomic UID-scoped lease + parent-pipe helper and safe startup reaper, ps/PGID/start-time/binary/port/inode checks; hard-kill→next-start cleanup oracle and foreign-object negatives, H0/H9 NOT_RUN.",
+      "packet_locations": [
+        "#/decisions/0/details/crash_recovery",
+        "#/resilience_gates/T_LIFE_v1",
+        "#/verification_surface/4/orphan_oracles",
+        "#/evolution/H0_precondition",
+        "#/evolution/H9_crash_recovery_gate"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-001",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-008"
+      ],
+      "changes_made": "Owner proof errors counted once,3timeouts→DEGRADED; --port0 stdout considered unverified alternative; one bounded lsof/helper resource accounting included.",
+      "packet_locations": [
+        "#/decisions/0/details/transport_health/counted_failures",
+        "#/decisions/0/alternatives",
+        "#/high_load_envelope/operational_profile/thread_accounting",
+        "#/resilience_gates/C_MULT/C-MULT-I5"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-002",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-010"
+      ],
+      "changes_made": "EVD070 actual supplied378tests/122.956s/0imports/3knownfailures frombridge cwd; no17module edits needed, future full-green gate preserved.",
+      "packet_locations": [
+        "#/verification_surface/1/baseline",
+        "#/evidence/64"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-003",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-011"
+      ],
+      "changes_made": "Changed binary stat key revalidates used schema projection; same hash remains serve, mismatch run+reason; expected schema fixture independent. REQ016/AC021 authorized fields preserved, detail diagnostic adjacent if strict parser.",
+      "packet_locations": [
+        "#/decisions/0/details/protocol_compatibility",
+        "#/decisions/2/details/telemetry",
+        "#/resilience_gates/O_EXIT_v1"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-004",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-012"
+      ],
+      "changes_made": "Explicit phase/event→fallback/retry/fail and ServeHealth/model counter table, including20s pre-/post-header no-event; any headers latchDELIVERED before classification.",
+      "packet_locations": [
+        "#/decisions/0/details/fallback_decision_table",
+        "#/decisions/0/details/fallback_barrier",
+        "#/decisions/2/details/retry",
+        "#/resilience_gates/R_BULK/R-BULK-I3"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-005",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-013"
+      ],
+      "changes_made": "REQ004/005 match thinking eligibility/grace.30,fast/off/JSON exclusions and immutable model bytes; mandatory post-token stall heartbeat threshold/interval15s, no watchdog resets.",
+      "packet_locations": [
+        "#/requirements/3",
+        "#/requirements/4",
+        "#/decisions/1/details/lifecycle",
+        "#/decisions/1/details/STALL_HEARTBEAT_INTERVAL_S",
+        "#/contract_deltas/0"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-006",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-014"
+      ],
+      "changes_made": "18admittedhandlers+readers/delivery/12drains/supervisors/watchdogs→55parentthreads;108FD<=128,helper/lsof process/memory included; normalp99goal180 vs degraded3*60+51.6=231.6 separately measured, flood caveat explicit.",
+      "packet_locations": [
+        "#/high_load_envelope/operational_profile/thread_accounting",
+        "#/high_load_envelope/operational_profile/fd_accounting",
+        "#/high_load_envelope/operational_profile/p99_criteria",
+        "#/high_load_envelope/memory_closure_check",
+        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-007",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-015"
+      ],
+      "changes_made": "Кодовый дефолт REALTIME_SERVE_ENABLED=false. Локальный runtime dynamic_config.json — stdlib-аналог dynamic_config.py/GigaRC автономного моста без внешних зависимостей: H0 отсутствие файла или boolean false удерживает run; H7 атомарно включает true только после успешных H3 (6 параллельных слотов RSS/FD с OPENCODE_DB=\":memory:\") и H6 (живая permission/tool изоляция на кандидате). Без исключений из канона, human waiver, новых env-переменных и правок start.sh; никакой записи dynamic_config.json в git. AC-004:378legacy run при отсутствии файла. AC-026/VER-005 Clean-Room L2: tmp_path JSON true и monkeypatch.setattr(server,\"DYNAMIC_CONFIG_PATH\",cfg_path,raising=False), RED на chunk timing против origin/dev, GREEN на новом; false runtime без restart.",
+      "packet_locations": [
+        "#/approval",
+        "#/assumptions/2",
+        "#/assumptions/3",
+        "#/evolution/H0_precondition",
+        "#/evolution/rollout",
+        "#/decisions/0/details/configuration",
+        "#/evolution/rollback"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    },
+    {
+      "id": "FU-008",
+      "pass": "a2",
+      "status": "RESOLVED",
+      "resolution_level": "architecture_contract",
+      "source_findings": [
+        "PANEL-A2-F-016"
+      ],
+      "changes_made": "Considered split3a/3b delivery, one branch/MR for owner realtime outcome with staged execution. GroupA RC2/RC3 requires noFakeServe; GroupB independent tests localize serve failures.",
+      "packet_locations": [
+        "#/decisions/0/alternatives",
+        "#/verification_surface/4/groups"
+      ],
+      "verification": "Pointers/coverage/digests validated in architect03; implementation VER004/005 and all H gates NOT_RUN. External a3 review required, no author vote.",
+      "decision_required_human": false
+    }
+  ],
+  "evidence_refs": [
+    "EVD-070",
+    "EVD-071",
+    "EVD-072",
+    "EVD-073",
+    "EVD-074"
+  ]
 }
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a2.json sha256=baa297e7819579dc1cf779af370b16f385a7ede77d9538553713212b1475dc7f
{
  "schema_version": "1.0",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "teamlead_cycle": 1,
  "panel_slug": "analyst-teamlead-zen-realtime-reasoning-20261025-arch-council-1-a2-r3",
  "panel_verdict": "NEEDS_WORK",
  "summarizer_slot": "gpt-6.1-sol",
  "instructions": [
    {
      "id": "RW-001",
      "priority": "blocking",
      "criterion": "РЕАЛИЗУЕМОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/verification_surface/3",
      "rule_ref": "Architecture verification surface; REQ-003; scope.forbidden; immutable_run_env; RISK-008; EVD-052/053",
      "action": "Architect: устранить deadlock VER-004 против VER-005/immutable_run_env и scope.forbidden. В пакете задать воспроизводимый basedpyright==1.40.2 с cwd моста и явным изолированным import-root/временным --project вне репозитория: server, zen_catalog и tests.* должны разрешаться внутри bridges/opencode-zen-bridge, а не в корневом хабе. Сохранить побайтовый _run_env и Google-direct: новый tests/test_realtime_reasoning.py проверять ruff==0.17.2 format целиком, legacy server.py/test_step_interruption.py — проверяемым гейтом изменённых диапазонов с конкретной исполнимой командой, без выдуманных CLI-флагов. Альтернативу AST-эквивалентности из F-001 описать как вариант пересогласования инварианта, не молча заменять замороженный hash. До freeze включить read-only baseline format/check/basedpyright с числами для существующих target-файлов и честным NOT_PRESENT для ещё не созданного testfile; назначить повтор на всех трёх после его создания. Зафиксировать допустимое исправление E402, import zen_catalog и CATALOG_SOURCE в allowlist без type-ignore/disable/правок общих конфигов; рассмотреть предварительную стадию 3a для долга. Явно обосновать достижимость warning limits (сумма 564, по неуказанным правилам 0), либо документировать согласованное изменение запаса, сохранив errorCount==0 и запрет новых Any. Синхронизировать expected, environment, baseline_transition, typing, risk и rework-resolution, не выдавая будущий Stage3 за PASS.",
      "acceptance": "В дельта-пакете VER-004 содержит конкретный cwd/import-root и воспроизводимые команды, EVD — фактические baseline результаты/версии/числа и статус отсутствующего нового файла. test_step_interruption.py разрешает локальный server.py: 0 ошибок отсутствующих атрибутов корневого хаба. Одновременный VER-004/VER-005 достижим после указанного погашения долга: 0 lint failures и type errors во всех трёх файлах, документированные лимиты предупреждений; frozen _run_env hash и Google-direct сохранены, конфиги/внешняя allowlist не изменены. Невыполненные проверки явно NOT_RUN; на чистом клоне baseline воспроизводим до Stage3.",
      "source": "F-001: skeptic · R1 · seat1-F-01; F-009: realist · R1 · seat2-F-4; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-001 — исходная находка:\n> - **F-01** (`priority: blocking`, критерии: `3. РЕАЛИЗУЕМОСТЬ`, `2. ПОЛНОТА`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)\n>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/verification_surface/3` `VER-004`, `#/decisions/0/details/immutable_run_env`, `#/verification_surface/4` `VER-005`, `#/scope/forbidden`); [server.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L66-L67), [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131); [pyrightconfig.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/pyrightconfig.json); [ruff.toml](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/ruff.toml).\n>   - **Нарушенное правило**: реализуемость и непротиворечивость замороженной `verification_surface` (`aisdlc-gcge/skills/architecture.md` §Python verification surface, `REQ-003`, `RW-002`, `RW-012`, `FU-004`).\n>   - **Доказательство**:\n>     1. Скрипт `VER-004` запускается из `cwd = repo_root` (`cwd=None`), где лежат корневые `/server.py`, `/tests/` и `pyrightconfig.json` (`\"extraPaths\": [\"tools\"]`). Прямой запуск `uvx --from basedpyright==1.40.2 basedpyright --outputjson bridges/opencode-zen-bridge/server.py bridges/opencode-zen-bridge/tests/test_step_interruption.py` даёт **`errorCount == 80`** (`2` в `server.py`, включая `import zen_catalog as zc` на строке 67 при дефисном каталоге `opencode-zen-bridge`, и `78` в `test_step_interruption.py`, где `import server` статически резолвится в корневой `/server.py`, в котором отсутствуют `ALLOWED_MODELS`, `OPENCODE_BIN`, `DEFAULTWORKDIR`, `_strip_interrupted`, `ToolCallParser.has_open_tool_call`). Аналогично упадёт и новый `tests/test_realtime_reasoning.py`, при том что `tests/_fake_cli.py`, `tests/_fixtures.py`, `tests/_http.py` вне `coder_target_files`, а `# pyright: ignore` и изменение `pyrightconfig.json` запрещены `VER-004.expected` и `scope.forbidden`.\n>     2. Корневой `ruff.toml` использует стандартный `line-length = 88`. В [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131) 11 строк имеют длину 90–108 символов: прогон `uvx --from ruff==0.17.2 ruff format` меняет `sha256` байтового среза `_run_env` с замороженного `1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31` на `85c9c344b339f188a7c97b802e431297aab0ef5b4bdd6ecaba46902962eeb104` (ломая `VER-005`) и переписывает ~1 250 строк `server.py` (`4021 -> 4976`), включая прямой Google route, трогать который запрещено `scope.forbidden` (`\"прямой Google route и test_google_direct.py\"`), тогда как `# fmt: off` запрещён `VER-004.expected` (`\"без type-ignore/disable/изменения конфигов\"`).\n>   - **Ожидаемое исправление**: (а) в `VER-004` запускать `basedpyright` с `cwd=\"bridges/opencode-zen-bridge\"` и сгенерированным во временном файле `/tmp` конфигом `--project` (указывающим `root` на `bridges/opencode-zen-bridge` без мутации репозитория), чтобы `server`, `zen_catalog` и `tests.*` резолвились строго внутри моста; (б) для `ruff format` проверять форматирование нового файла `tests/test_realtime_reasoning.py` целиком, а для legacy `server.py` и `test_step_interruption.py` — только изменённые ханки `git diff` (не трогая `_run_env` и Google-direct), либо заменить побайтовый SHA-256 среза `_run_env` на канонический AST-хэш при явном исключении Google-direct из форматирования.\n>   - **Критерий верификации**: команда `VER-004` на текущем `test_step_interruption.py` резолвит `bridges/opencode-zen-bridge/server.py` (`0` ошибок отсутствующих атрибутов корневого `/server.py`), а одновременное прохождение `VER-004` и `VER-005` сохраняет `immutable_run_env` и нулевой `git diff` по функциям Google-direct в `server.py`.\n\nF-009 — исходная находка:\n> **F-4** [РЕАЛИЗУЕМОСТЬ, blocking]\n> - Anchor: #VER-004 (`limits`), #RISK-008, #EVD-052/053.\n> - Evidence: сумма `limits` равна 125+125+39+70+48+35+2+27+81+3+3+2+2+1+1 = 564, то есть ровно базовым 564 предупреждениям. Запаса нет ни по одному правилу для ~1000+ строк нового кода: правила вне словаря получают лимит 0. Pre-existing E402 и 2 error-сайта (`zen_catalog` import, `CATALOG_SOURCE`) должны быть исправлены без `type-ignore`/конфигов; достижимость не проверена, а import-механизм связан с деплоем. `ruff format --check` на базовой линии для `server.py` и `test_step_interruption.py` не запускался (EVD-052/053 — только check и basedpyright); возможен реформат всего файла и шум в diff, что противоречит AGENTS.md п. 4.\n> - Исправление: до заморозки записать в evidence read-only базовые результаты `ruff format --check` и `basedpyright` по всем 3 файлам. Определить допустимый способ исправить import `zen_catalog`. Либо отдельный предварительный коммит/стадия 3a для долга. Либо явно заложить запас по правилам, не отменяя `errorCount==0`.\n> - Проверка: EVD с базовыми числами; VER-004 воспроизводим на чистом клоне до начала Stage 3.\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-001",
        "F-009"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/immutable_run_env"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/typing"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/scope/forbidden"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/risks/7"
        }
      ]
    },
    {
      "id": "RW-002",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/decisions/0/details/data_isolation",
      "rule_ref": "REQ-002; RW-006/FU-001 verify-fixed; ASM-001; RISK-003; EVD-063; сохранность auth и отсутствие общей DB mutation",
      "action": "Architect: переработать data_isolation без регрессии opencode-go/*. Сравнить штатный OPENCODE_DB=\":memory:\" v2.1.2 и per-spawn XDG_DATA_HOME; выбрать/обосновать изоляцию без записи/миграции общей opencode.db/opencode-next.db и без потери auth.json/credential. Оценить и зафиксировать OPENCODE_DB=\":memory:\"; при дополнительной XDG-изоляции обеспечить read-only auth либо явно описанный валидный auth-путь, сохранив OPENCODE_MODELS_PATH и byte-identical _run_env. Не лечить ложный 401 ослаблением auth fail-closed или replay. Включить недостающие standalone/opencode-go проверки VER-005. По F-007 до freeze или первой задачей Coder назначить дешёвый provider-free/zero-Zen-quota спайк выбранной изоляции (для сравнения — пустой XDG_DATA_HOME с сохранённым OPENCODE_MODELS_PATH): GET /api/info и /api/session/active, startup/readiness, RSS, созданные файлы/миграции/auth. Добавить фактическую EVD-калибровку ready<=3s; старые 109ms/1.8s/152MiB измерены с общими данными. При провале сравнить запасной вариант общей DB + _StartupGate из F-007, явно учитывая конфликт с запретом общей DB mutation/lock и необходимое согласование, а не включать его молча. Обновить ASM-001/RISK-003/H3 и связанные RW-006/FU-001.",
      "acceptance": "Пакет содержит сравнение и однозначный выбор изоляции/auth для standalone и opencode-go/*, с сохранением каталога моделей и запрета общей DB mutation. EVD со startup/RSS/файлами и обоими endpoint-ответами калибрует ready-бюджет; если спайк ещё не выполнен, явная первая задача и stop-gate до подтверждения вместо выдуманного PASS. VER-005 проверяет обе группы моделей: нет записи в общую opencode.db, OPENCODE_DB=\":memory:\" или доказанный эквивалент, auth доступен без утечки и без ложного ProviderAuthError 401. Реальную provider-auth совместимость отделить от provider-free спайка; runtime H3/RSS/locks остаются обязательны и не объявляются выполненными.",
      "source": "F-002: skeptic · R1 · seat1-F-02; F-007: realist · R1 · seat2-F-2; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-002 — исходная находка:\n> - **F-02** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `2. ПОЛНОТА`, `4. РИСКИ`, `5. АЛЬТЕРНАТИВЫ`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)\n>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/data_isolation`, `#/decisions/0/details/fallback_barrier`, `#/rework_resolutions/5` `RW-006`, `#/rework_resolutions/14` `FU-001`); [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1099-L1104); [opencode-go.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/opencode-go.json).\n>   - **Нарушенное правило**: сохранение работоспособности существующих моделей моста (`REQ-002` публичный контракт `/v1/models` + `/v1/chat/completions`, `RW-006`/`FU-001` изоляция без регрессий, оценка штатных альтернатив `5. АЛЬТЕРНАТИВЫ`).\n>   - **Доказательство**: для не-Google моделей маршрута `opencode-go/*` (`glm-5.1`, `kimi-k2.5`, `minimax-m2.5`, `minimax-m2.7`; см. [test_go_model_routing.py](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/tests/test_go_model_routing.py#L55-L120)) `_run_env` передаёт `OPENCODE_CONFIG=.../opencode-go.json` с `baseURL = \"http://127.0.0.1:10830/go/v1\"` без `apiKey`. В бинарнике `~/.opencode/bin/opencode` v2.1.2 (`@112656461`, `@121011124`, `@123591903`) учётные данные провайдера `opencode-go` загружаются из `XDG_DATA_HOME/opencode/auth.json` и импортируются миграцией `20260805200742_import_legacy_credentials` в таблицу `credential`. Установка пустого `env[\"XDG_DATA_HOME\"] = tempfile.mkdtemp(prefix=\"zen-serve-data-\")` на каждый `serve` spawn лишает `opencode serve` ключа `opencode-go`, вызывая `ProviderAuthError` (`provider.auth` -> 401), а правило `AD-001.details.fallback_barrier` (`\"HTTP401/403/auth/... -> fail-closed без fallback\"`) запрещает откат на `opencode run`. Одновременно в самом бинарнике `opencode` v2.1.2 (`@114651600`, `@122016915`) реализован штатный флаг `OPENCODE_DB=\":memory:\"`, отключающий файловую `opencode.db` и чтение `opencode-next.db` без создания/удаления SQLite на каждый запрос.\n>   - **Ожидаемое исправление**: задать в `_serve_env(model_id)` `env[\"OPENCODE_DB\"] = \":memory:\"` (оценив и зафиксировав это в `AD-001.details.data_isolation`); если дополнительно изолируется `XDG_DATA_HOME`, обеспечить для ветки `ALLOWED_MODELS[model_id].get(\"base_url\")` (`opencode-go/*`) сохранение read-only доступа к `auth.json` (симлинк/чтение без мутации общей `opencode.db`) либо явную маршрутизацию, исключающую ложный 401 `fail-closed`.\n>   - **Критерий верификации**: в `VER-005` добавлен тест `_serve_env` для обеих групп моделей (`standalone` Zen и `opencode-go/*`), подтверждающий отсутствие записи в `~/.local/share/opencode/opencode.db`, наличие `OPENCODE_DB=\":memory:\"` (или эквивалентной сохранности `auth.json` для `opencode-go/*`) и успешный прогон без 401 `ProviderAuthError`.\n\nF-007 — исходная находка:\n> **F-2** [РИСКИ/РЕАЛИЗУЕМОСТЬ, blocking]\n> - Anchor: #AD-001 (`details.data_isolation`), #ASM-001, #RISK-003, #EVD-063.\n> - Evidence: замеры [F-19]/[F-20] (старт 109 мс, первая дельта 1.8 с, RSS 152 MiB) сняты с общим каталогом данных. В цикле 2 opencode не запускался (EVD-063). Поведение `serve` при пустом `XDG_DATA_HOME` не проверено: нужны первичные миграции SQLite, состояние и auth. Влияние на 109 мс и ready≤3 с неизвестно. Не могу проверить.\n> - Исправление: до заморозки или первой задачей Coder выполнить дешёвый спайк без вызова провайдера и без расхода квоты Zen. Запустить `serve` с пустым `XDG_DATA_HOME` и сохранённым `OPENCODE_MODELS_PATH`, проверить `GET /api/info` и `/api/session/active`, записать время старта, RSS и созданные файлы. Добавить результат в evidence. При провале иметь запасное решение: общая БД плюс `_StartupGate`.\n> - Проверка: EVD с цифрами спайка; VER-005 использует их как калибровку ready-бюджета.\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-002",
        "F-007"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/assumptions/0"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/risks/2"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/evidence/62"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/fallback_barrier"
        }
      ]
    },
    {
      "id": "RW-003",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/decisions/0/details/tool_policy",
      "rule_ref": "REQ-011; REQ-012; AC-016; AC-017; THREAT-002; single-turn native tool mapping",
      "action": "Architect: дополнить tool_policy/session_flow/session_wire/event_contract и AD-004 step всеми тремя ветками v2.1.2: form.created немедленно отменять POST /api/session/{id}/form/{formID}/cancel через control lane <=0.25s с fail-closed; после permission.asked -> decision=reject или form cancel исключать Step2 посредством явного interrupt/границы single-turn и существующего _incomplete_step_signal/unmapped-tool recovery; восстанавливать JSON-аргументы из session.tool.input.ended.data.text, если session.tool.called.data.input отсутствует перед session.tool.failed/step.ended. Дополнить frozen fixtures шестым семейством form.created/form.cancelled по Form.Info/Form.State и негативными мутациями, сохранив пять существующих. Описать порядок сохранения DSH tool_calls, interrupt и cleanup без ожидания prompt POST и без побочного текста второго шага; синхронизировать THREAT-002 и VER-005.",
      "acceptance": "Дельта-пакет фиксирует wire endpoint/fields, single-turn порядок и независимые frozen expectations. VER-005 FakeServe: form.created отменяется <=0.25s без 60s зависания; error cancel/reject fail-closed; called.data.input и streaming->failed без called с input.ended.data.text дают одинаковые корректные DSH tool_calls; reject/cancel не допускают Step2 и не выпускают его текст в клиентский сокет. Эти оракулы указаны как будущие, если не исполнены.",
      "source": "F-003: skeptic · R1 · seat1-F-03; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-003 — исходная находка:\n> - **F-03** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `2. ПОЛНОТА`, `4. РИСКИ`)\n>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/tool_policy`, `#/decisions/0/details/session_flow`, `#/decisions/0/details/session_wire`, `#/decisions/0/details/event_contract`, `#/decisions/3/details/step`, `#/threat_model/threats/1` `THREAT-002`).\n>   - **Нарушенное правило**: полный отказ от выполнения/блокировки встроенных инструментов CLI в пользу клиента DSH и сохранение нативного маппинга инструментов (`REQ-011`, `REQ-012`, `AC-016`, `AC-017`, `THREAT-002`).\n>   - **Доказательство**: сверка с бинарником `~/.opencode/bin/opencode` v2.1.2 вскрывает три неучтённые механики:\n>     1. Интерактивные встроенные инструменты (`question`/forms, остающиеся включёнными из-за `EVD-050`/`F-08`) публикуют событие `form.created` (`@114605908`, `@115254160`), а не `permission.asked`; сам нативный клиент `opencode run` (`@122625575`, функция `J`) немедленно вызывает `client.session.form.cancel({sessionID, formID})`. В пакете v2 `form.created` отсутствует — вызов `question` приведёт к 60-секундному зависанию сессии до watchdog.\n>     2. В нативном клиенте `opencode run` (`@122625575`, функция `se`) сразу после `permission.reply(..., decision: \"reject\")` вызывается `client.session.interrupt({sessionID})`, поскольку сам по себе `decision: \"reject\"` в `opencode serve` переводит инструмент в `session.tool.failed` и продолжает агентный цикл во **второй шаг LLM (Step 2)**, стримя клиенту нерелевантный текст отказа и тратя квоту Zen, если вызов не был смаплен в DSH `tool_calls`.\n>     3. В редьюсере `opencode` v2.1.2 (`@115409671`, `@121654561`) событие `session.tool.failed` допустимо напрямую из состояния `status === \"streaming\"` (без предварительного `session.tool.called`), где входные аргументы содержатся только в строке `session.tool.input.ended.data.text`, тогда как `event_contract[\"session.tool.*\"]` опирается на `called(input, executed)`.\n>   - **Ожидаемое исправление**: (1) добавить в `tool_policy`, `session_wire` и `event_contract` обработку `form.created` -> немедленный `POST /api/session/{id}/form/{formID}/cancel` по control lane (`<=0.25 s`, `fail-closed` при ошибке); (2) указать fallback парсинга JSON-аргументов из `session.tool.input.ended.data.text`, если `session.tool.called` не пришёл до `failed`/`step.ended`; (3) зафиксировать правило single-turn прерывания: после любого `permission.asked -> reject` (или `form.created -> cancel`) мост не допускает запуска Step 2 в `opencode serve` — либо возвращает смапленный DSH `tool_calls` на границе шага и вызывает `interrupt`, либо немедленно шлёт `POST /api/session/{id}/interrupt` и применяет существующую логику `_incomplete_step_signal` / unmapped-tool recovery.\n>   - **Критерий верификации**: `FakeServe` в `VER-005` проверяет: (а) `form.created` отменяется за `<=0.25 s` без 60-секундного таймаута; (б) маппируемый нативный tool call восстанавливает аргументы как из `session.tool.called.data.input`, так и из `session.tool.input.ended.data.text`; (в) после `decision: \"reject\"` второй шаг генерации (`Step 2`) не стримит побочный текст в клиентский сокет.\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-003"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/session_flow"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/session_wire"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/event_contract"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/3/details/step"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/threat_model/threats/1"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        }
      ]
    },
    {
      "id": "RW-004",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/decisions/0/details/listener_ownership",
      "rule_ref": "R-BULK-I1; T-LIFE/v1; C-MULT/v1; REQ-001 AC-002; RW-003 verify-fixed",
      "action": "Architect: убрать lsof с каждого нового горячего HTTP-вызова. Зафиксировать однократную проверку LISTEN PID и os.getpgid(listener_pid)==child_pgid на SPAWN->READY до Auth/prompt; затем удерживать проверенные HTTP/1.1 Keep-Alive control, SSE и prompt соединения с proc.poll() is None перед отправкой Auth. Описать fail-closed поведение потери владения/жизни, открытия соединений и ограниченную повторную проверку при переоткрытии упавшего control-сокета с явным бюджетом >=0.30s; она не должна скрыто входить в <=0.10s interrupt/DELETE. Согласовать permission_reply<=0.25s, cleanup API aggregate<=0.20s и aggregate cleanup<=1.2s, включая накладные расходы и cap/spawn accounting. Сохранить нулевую утечку чужому listener и cleanup только своего PGID; cross-reference non-blocking FU-001 по health/resource/альтернативе port0.",
      "acceptance": "В пакете есть схема удерживаемых соединений и отдельный bounded reconnect path с замкнутыми бюджетами. VER-005 spy: ровно 1 lsof на успешный serve spawn, включая reply/interrupt/DELETE; takeover до READY -> 0 байт Authorization/промпта чужому listener, без API/kill чужого PID. Проверка живости обязательна до Auth; reconnect не обходится cached proof для чужого listener. H3 включает 6 параллельных запросов и учёт стоимости lsof (исходно 68.1ms, 82.0..88.1ms параллельно, 24–30 процессов при старой схеме); бюджетные утверждения согласованы во всех разделах.",
      "source": "F-004: skeptic · R1 · seat1-F-04; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-004 — исходная находка:\n> - **F-04** (`priority: blocking`, критерии: `1. КОРРЕКТНОСТЬ`, `4. РИСКИ`, `5. АЛЬТЕРНАТИВЫ`)\n>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/decisions/0/details/listener_ownership`, `#/decisions/0/details/tool_policy`, `#/decisions/0/details/session_wire/cleanup`, `#/decisions/2/details/cleanup`, `#/resilience_gates/C_MULT`).\n>   - **Нарушенное правило**: замыкание бюджетов времени на вспомогательных и cleanup-вызовах и учёт порождаемых подпроцессов (`R-BULK-I1`, `T-LIFE/v1`, `C-MULT/v1`, `REQ-001` AC-002 `<=250 ms`, `RW-003`).\n>   - **Доказательство**: `AD-001.details.listener_ownership` требует запускать `lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp` «до первого Auth и повторно до отправки Auth на каждом новом TCP соединении». На целевом Mac измеренное время одного вызова `lsof` составляет **`68.1 ms`**, а при 6 параллельных вызовах (`H3`) — **`82.0..88.1 ms`** на каждый вызов в отсутствие прочей нагрузки. При этом `session_wire.cleanup.aggregate_api_budget_s = 0.20` (`AD-003.cleanup`: `interrupt` `<=0.10 s` + `DELETE` `<=0.10 s`), а `permission_reply` имеет общий бюджет `<=0.25 s`. Открытие нового TCP-соединения с предварительным `lsof` (~85 мс) оставляет `<15 мс` на TCP+HTTP и гарантированно срывает `0.10 s` бюджет `interrupt`/`DELETE` под нагрузкой, а также порождает 24–30 неучтённых в `_SpawnRateLimiter` подпроцессов `lsof` на волну из 6 запросов.\n>   - **Ожидаемое исправление**: выполнять `lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp` и проверку `os.getpgid(listener_pid) == child_pgid` **однократно** после привязки порта на фазе `SPAWN -> READY`; далее использовать постоянное `HTTP/1.1 Keep-Alive` control-соединение (плюс одно `SSE`-соединение и одно `prompt`-соединение, открытые сразу после проверки владения), проверяя перед отправкой `Authorization` живость собственного процесса `proc.poll() is None` (пока дочерний процесс жив и держит `LISTEN` сокет на `127.0.0.1:<port>`, перехват порта другим процессом на macOS/POSIX невозможен; повторный `lsof` допустим только при переоткрытии упавшего control-сокета в пределах явного бюджета `>=0.30 s`).\n>   - **Критерий верификации**: в `VER-005` spy на запуск `lsof` подтверждает ровно `1` вызов `lsof` на успешный `serve` spawn (включая сценарий с `permission.asked -> reply` и финальным `interrupt`/`DELETE`), а негативный тест подмены listener до `READY` по-прежнему даёт `0` отправленных байт `Authorization`/промпта.\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-004"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/session_wire/cleanup"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/2/details/cleanup"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/resilience_gates/C_MULT"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        }
      ]
    },
    {
      "id": "RW-005",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/threat_model/threats/2",
      "rule_ref": "THREAT-003; защита родительского окружения; immutable_run_env",
      "action": "Architect: исправить ложную посылку THREAT-003 о всеобщем _run_env whitelist. Определить в _serve_env(model_id) явный allowlist/санитизацию результирующего env для всех трёх веток: standalone, base_url/opencode-go/* и CATALOG_MODE=static, до добавления одноразового OPENCODE_SERVER_PASSWORD. _run_env оставить побайтово неизменным. Описать необходимые config/catalog/proxy/auth переменные и безопасные исключения совместно с RW-002, исключив произвольные секреты родителя и bridge API key; не выводить значения секретов в evidence/logs. Обновить tool_policy, threat и VER-005.",
      "acceptance": "THREAT-003 больше не утверждает, что _run_env всегда фильтрует env. VER-005 secret-sentinel параметризован по трём веткам и подтверждает отсутствие OPENCODE_ZEN_BRIDGE_API_KEY/SECRET_SENTINEL и неразрешённых секретов в child env; нужные routing/catalog/auth сохранены, password только child-scoped, logs без значений секретов. Frozen hash _run_env не меняется.",
      "source": "F-005: skeptic · R1 · seat1-F-05; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-005 — исходная находка:\n> - **F-05** (`priority: blocking`, критерии: `2. ПОЛНОТА`, `4. РИСКИ`, `6. СООТВЕТСТВИЕ КОНТЕКСТУ`)\n>   - **Локация**: [architecture-packet.json](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json) (`#/threat_model/threats/2` `THREAT-003`, `#/decisions/0/details/tool_policy`, `#/decisions/0/details/immutable_run_env`); [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1093-L1131).\n>   - **Нарушенное правило**: защита секретов родительского окружения от утечки в дочерний HTTP-сервер (`THREAT-003`, `4. РИСКИ/безопасность`).\n>   - **Доказательство**: `THREAT-003` утверждает: `\"_run_env whitelist как legacy, password добавляется только child env... _serve_env wrapper не меняет _run_env\"`. Однако чтение [`_run_env`](file:///Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/bridges/opencode-zen-bridge/server.py#L1095-L1131) показывает, что строка 1095 копирует полный `env = dict(os.environ)`, а фильтрация по `_STANDALONE_ENV_ALLOWLIST` выполняется **только** внутри `elif _uses_standalone(model_id):` (строка 1108). В ветке `if ALLOWED_MODELS.get(model_id, {}).get(\"base_url\"):` (`opencode-go/*`, строки 1099–1103) и в ветке `else:` (`CATALOG_MODE=\"static\"`, строки 1127–1130) возвращается полный нефильтрованный `os.environ` родителя (включая `OPENCODE_ZEN_BRIDGE_API_KEY`, `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY` с логином/паролем и любые секреты окружения моста), который `_serve_env` передаст в HTTP-демон `opencode serve`.\n>   - **Ожидаемое исправление**: оставив `_run_env` побайтово неизменной, в обёртке `_serve_env(model_id)` явно фильтровать результирующий словарь окружения по белому списку допустимых переменных для всех веток моделей (либо гарантированно вычищать `OPENCODE_ZEN_BRIDGE_*`, `*_API_KEY`, `*_TOKEN`, `*_SECRET` и посторонние переменные родителя до добавления одноразового `OPENCODE_SERVER_PASSWORD`).\n>   - **Критерий верификации**: негативный тест secret-sentinel в `VER-005` проверяет `_serve_env(model_id)` на всех трёх ветках (`standalone`, `opencode-go/*` с `base_url`, `CATALOG_MODE=\"static\"`) и подтверждает отсутствие родительских секретов (`OPENCODE_ZEN_BRIDGE_API_KEY`, произвольного `SECRET_SENTINEL`) в окружении дочернего `opencode serve`.\n\n---\n\n## Находки Seat 2 (`realist`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-005"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/tool_policy"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/decisions/0/details/immutable_run_env"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        }
      ]
    },
    {
      "id": "RW-006",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#/decisions/0/details/spawn",
      "rule_ref": "T-LIFE/v1; ownership и PID-safe cleanup; F-14/F-30",
      "action": "Architect: закрыть смерть родителя вне finally: stdin=DEVNULL/start_new_session=True у serve не обеспечивают завершение при SIGKILL/рестарте моста. Определить реестр владения pid/pgid/start-time/owner-tag и owned temp dirs с PID-reuse-safe проверкой ps перед startup cleanup, либо доказуемый parent-death watchdog. Описать уборку только собственных подтверждённых сирот и zen-serve-data-* после crash/restart, без name-wide kill и без захвата чужих attempts; потеря ownership-manifest не даёт разрешения искать/убивать по имени. Обновить T_LIFE, VER-005 и rollout H0/H9 с повторным запуском после hard kill и LaunchAgent kickstart -k.",
      "acceptance": "В дельта-пакете определены механизм parent-death/recovery, идентификация владельца/времени старта, защита от PID reuse и правила удаления owned каталогов. VER-005: hard kill родителя -> следующий старт убирает его serve/потомков/каталоги, чужие PID/PGID/каталоги не затрагиваются; старые 50 cancellations сохранены. H0/H9 после kickstart -k проверяют 0 принадлежащих прошлому экземпляру serve/owned temp dirs и отсутствие потери ownership accounting. Runtime прогоны не объявлять состоявшимися в архитектурном пакете без evidence.",
      "source": "F-006: realist · R1 · seat2-F-1; findings-ledger.md a2, resolved_in=r3-majority",
      "evidence": "F-006 — исходная находка:\n> **F-1** [РИСКИ, blocking]\n> - Anchor: architecture-packet.json#AD-001 (`details.spawn`: `stdin=DEVNULL`, `start_new_session=True`), #T_LIFE_v1; [F-14], [F-30].\n> - Правило: T-LIFE/v1 (отсутствие осиротевших процессов).\n> - Evidence: legacy `opencode run` завершается при закрытии stdin/pipe. `opencode serve` — долгоживущий сервер, и со `stdin=DEVNULL` сам не завершится. Дочерний процесс в новой сессии не попадает под зачистку launchd при перезапуске или SIGKILL моста. Оракул T-LIFE покрывает только отмену внутри живого процесса: 50 отмен, нули счётчиков. Rollout включает перезапуск LaunchAgent (H0, H9).\n> - Исправление: добавить реестр владения (pid, pgid, время старта и метка владельца в имени temp-каталога или env). На старте моста добавить зачистку сирот и каталогов `zen-serve-data-*`, с проверкой по `ps` перед kill. Либо parent-death watchdog у дочернего процесса.\n> - Проверка: тест в VER-005 «жёсткий kill родителя → следующий запуск моста убирает serve и каталоги»; в H0/H9 после `kickstart -k` ноль процессов `serve`.\n\nОсобое мнение (дословно): visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-006"
      ],
      "related_locations": [
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/resilience_gates/T_LIFE_v1"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/verification_surface/4"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/evolution/rollout"
        },
        {
          "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
          "line_hint": "#/evolution/rollback"
        }
      ]
    }
  ],
  "non_blocking_followups": [
    {
      "id": "FU-001",
      "text": "Связано с RW-004, не дополнительный blocking: классифицировать owner-proof failure/timeout в _ServeHealth, кэшировать proof на keep-alive, учитывать lsof в thread/FD/cap accounting. Рассмотреть --port 0 + объявление порта через pipe с проверкой факта вывода, не считать его доказанным. VER-005: lsof timeout ×3 -> DEGRADED без лишних Popen.\n\nИсходная находка F-008 (дословно):\n> **F-3** [РИСКИ/АЛЬТЕРНАТИВЫ, non-blocking]\n> - Anchor: #AD-001 (`details.listener_ownership`, `details.transport_health.counted_failures`); [F-30].\n> - Evidence: owner-proof идёт через `lsof` с лимитом 0.25 с, повторяется на каждом новом TCP-соединении. Отказ или таймаут `lsof` даёт `ServeUnavailable`. В `counted_failures` он не перечислен. При таймаутах под 6 параллельными запросами каждый запрос тратит spawn и токен retry и уходит на `run`, а деградации не наступает. Subprocess `lsof` не учтён в потоках, FD и cap. [F-30] показывает, что `opencode` сам запускает `serve --port 0` как дочерний процесс; альтернатива «порт сообщает собственный дочерний процесс через его pipe» не рассмотрена. Выдаёт ли `serve` порт в stdout, не могу проверить.\n> - Исправление: классифицировать отказ owner-proof и учитывать его в `_ServeHealth`. Кэшировать проверку на keep-alive соединение. Учесть `lsof` в `thread_accounting`/FD. Занести альтернативу `--port 0` + объявление порта в AD-001 как рассмотренную.\n> - Проверка: оракул VER-005 «`lsof` timeout ×3 → DEGRADED, без лишних Popen».",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-008"
      ]
    },
    {
      "id": "FU-002",
      "text": "До freeze проверить baseline VER-002 из bridge cwd; записать число tests и failures/errors в EVD. F-45 фиксировал 17 import errors; если они остаются, скорректировать/снять недостижимый VER-002 без правок 17 модулей вне allowlist.\n\nИсходная находка F-010 (дословно):\n> **F-5** [РЕАЛИЗУЕМОСТЬ, non-blocking, снять до заморозки]\n> - Anchor: #VER-002; [F-45].\n> - Evidence: [F-45] фиксирует `python3 -m unittest discover` как «17 ошибок импорта». Пакет утверждает `exit 0` из cwd моста без базового прогона. Правка 17 существующих модулей вне allowlist, значит при сохранении ошибок VER-002 недостижим. Не могу проверить, что ошибки были только из-за cwd.\n> - Исправление: прогнать baseline VER-002 из cwd моста и записать в evidence. При красном — скорректировать или убрать VER-002.\n> - Проверка: EVD «VER-002 baseline = N tests OK» до freeze.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-010"
      ]
    },
    {
      "id": "FU-003",
      "text": "Рассмотреть совместимость по hash проекции схемы или explicit version allowlist вместо одного exact version; mtime/size invalidates cache с повторной проверкой. Транспорт/причину fallback писать в O-EXIT без изменения /health. Проверка: тот же schema hash после stat change сохраняет serve, другой -> run + явный O-EXIT.\n\nИсходная находка F-011 (дословно):\n> **F-6** [РИСКИ, non-blocking]\n> - Anchor: #AD-001 (`details.protocol_compatibility`).\n> - Evidence: совместимость требует `version==2.1.2` плюс exact-проекцию схемы. Любое обновление бинарника (mtime/size) делает serve недоступным, и мост молча деградирует на `run` до нового Architect-дельта. `/health` (неизменный) это не показывает.\n> - Исправление: допускать версии по совпадению хэша проекции схемы или allowlist в конфиге, выводить статус транспорта в лог O-EXIT. Изменение `/health` вне контракта — не требовать.\n> - Проверка: тест «смена mtime при той же проекции → serve остаётся; при другой → run + явная запись в O-EXIT».",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-011"
      ]
    },
    {
      "id": "FU-004",
      "text": "В AD-001 fallback_barrier/AD-003 retry/R-BULK-I3 добавить таблицу phase × event -> fallback/retry/fail × health counter, включая first_event_timeout до POST headers через 20s от prompt_send_start. Параметризовать VER-005 по фазам, сохранив запрет silent replay DELIVERED prompt.\n\nИсходная находка F-012 (дословно):\n> **F-7** [КОРРЕКТНОСТЬ, non-blocking]\n> - Anchor: #AD-001 (`details.fallback_barrier`), #AD-003 (`details.retry`), #R-BULK-I3.\n> - Evidence: при `first_event_timeout` (20 с от `prompt_send_start`) до получения заголовков POST не сказано: это «ServeUnavailable → run fallback» или «явный retry на serve» и считается ли попытка в `_ServeHealth`. Именно эта граница была предметом RW-001.\n> - Исправление: добавить в AD-001 таблицу решений «фаза × событие → действие (fallback/retry/fail) × счётчик health».\n> - Проверка: VER-005, параметризованный по фазам барьера.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-012"
      ]
    },
    {
      "id": "FU-005",
      "text": "Согласовать REQ-004/AC-005 и REQ-005 с thinking-eligibility/grace0.30s AD-002/CD-001; явно задать числовой stall threshold и обязательность heartbeat после первого токена. VER-005 expectations должны совпадать с requirements.\n\nИсходная находка F-013 (дословно):\n> **F-8** [КОРРЕКТНОСТЬ/ПОЛНОТА, non-blocking]\n> - Anchor: #REQ-004, #REQ-005, #AD-002 (`details.eligibility`, `details.lifecycle`), #CD-001.\n> - Evidence: REQ-004/AC-005 остались безусловными («даже при полностью молчащем апстриме»), а AD-002 сужает их до режима с thinking и grace 0.30 с. Для REQ-006/013/016 текст в v2 обновлён, для REQ-004 — нет. Порог «настоящего stall» для heartbeat «Ожидание продолжения» не задан (в тексте «можно»).\n> - Исправление: обновить acceptance REQ-004 и зафиксировать числовой порог и обязательность heartbeat после первого токена.\n> - Проверка: VER-005-оракулы совпадают с текстом REQ.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-013"
      ]
    },
    {
      "id": "FU-006",
      "text": "Пересчитать HL-ENV-01 threads/FD: ожидающие handlers дают до 6+12=18, lsof и drain threads учитывать согласованно (FD исходно 12, threads 6). Указать проверяемый p99 худшего случая: 3×60s +51.6s превышает SLA180s; не выдавать design estimate за закрытое SLA.\n\nИсходная находка F-014 (дословно):\n> **F-9** [РЕАЛИЗУЕМОСТЬ, non-blocking]\n> - Anchor: #operational_profile (`threads_per_worker_upper_bound`, `FD_worker`), #SLA_p99_s.\n> - Evidence: потоки: 6 handlers, но ThreadingHTTPServer держит потоки и для ожидающих (до 6+12=18); `lsof` не учтён. FD считает 12 дренажей, потоки — 6. Худший случай 3×first_token 60 с плюс вспомогательные 51.6 с превышает SLA 180 с (признано в `estimate_status`).\n> - Исправление: исправить расчёт потоков и FD (включая ожидающих и `lsof`); сформулировать допустимый p99 для худшего случая как проверяемый критерий.\n> - Проверка: пересчёт в HL-ENV-01.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-014"
      ]
    },
    {
      "id": "FU-007",
      "text": "Зафиксировать подтверждённое решение владельца о default=true/отступлении от GigaRC default=false в approval/evidence; если его нет, не выдумывать и оставить decision_required_human. Пересмотреть ASM-003/ASM-004 VALIDATED; H0 precondition — disable-file существует до production sync и launchctl kickstart, блокирующая проверка до H3/H6.\n\nИсходная находка F-015 (дословно):\n> **F-10** [СООТВЕТСТВИЕ КОНТЕКСТУ/РИСКИ, non-blocking]\n> - Anchor: #AD-001 (`feature_flag_context`), `approval.status=NOT_REQUIRED`, #ASM-003/#ASM-004, `evolution.rollout`.\n> - Evidence: дефолт `true` отступает от командного канона (удалённый флаг, дефолт `false`). Основание — только rework-бриф, и подтверждения владельца в `approval` нет. ASM-003/004 «VALIDATED» только ссылкой на бриф. Безопасность выката держится на ручном порядке: файл `disable-serve` должен существовать до синхронизации и рестарта, иначе serve включится на проде до H3/H6.\n> - Исправление: зафиксировать в `approval` или в evidence явное решение владельца. Сделать precondition в H0: «файл существует, проверка перед `launchctl kickstart`». Пересмотреть статусы ASM.\n> - Проверка: протокол H0 содержит проверку наличия файла как блокирующий шаг.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-015"
      ],
      "decision_required_human": true
    },
    {
      "id": "FU-008",
      "text": "Рассмотреть альтернативу поэтапной поставки L -> A1/B/C: Stage3a RC-2/RC-3 (watchdog, статусы, killpg, базовые тесты, O-EXIT и долг VER-004) с независимым VER, Stage3b serve за флагом. Разделить группы VER-005 так, чтобы 3a проходила без FakeServe; записать выбор/обоснование в AD-001 alternatives.\n\nИсходная находка F-016 (дословно):\n> **F-11** [АЛЬТЕРНАТИВЫ/РЕАЛИЗУЕМОСТЬ, non-blocking]\n> - Anchor: #AD-001 (`alternatives`: L), `handoff-architect.md` §4 («поэтапная поставка возможна: L затем A1/B/C»).\n> - Evidence: RC-2/RC-3 (watchdog, статусы, killpg, баз. тесты, O-EXIT) закрывают инцидент 780–856 с независимо от serve. Пакет сливает их с serve-транспортом в одну поставку внутри одного `server.py`.\n> - Исправление: разбить исполнение на стадии: 3a (RC-2/RC-3 плюс исправление базовых тестов и долг VER-004) с независимым VER, затем 3b (serve за флагом). Альтернативу «поэтапно» записать как рассмотренную.\n> - Проверка: VER-005 разделён на группы, стадия 3a проходит без FakeServe.",
      "reason": "visionary R1 PASS (0 F-блоков) → panel/arch/r3/seats/3/verdict.md",
      "source_findings": [
        "F-016"
      ]
    }
  ],
  "excluded": [],
  "findings_total": 16,
  "do_not_change": [
    "Читатель этого handoff — Architect по arch-council.md §3; coder_entry остаётся fix-from-panel. Не запускать Coder до нового архитектурного ACCEPT/freeze.",
    "В рамках rework менять Architecture Packet в разрешённом контуре Architect; продуктный код/тесты здесь не изменяются, спайки и runtime проверки этим summarizer не выполняются.",
    "Публичные /v1/models, /v1/chat/completions, /health и порт :9883; Google-direct route/test_google_direct.py, другие мосты и чужие задачи.",
    "Frozen Analyst inputs, byte-identical _run_env, test_run_env.py/start.sh, общие opencode/georouter конфиги, общая opencode.db и зависимости/lockfiles; не ослаблять их молча ради VER PASS.",
    "Согласованные cap3, no silent replay после delivery barrier, auth/security fail-closed, запрет allow/once/always и автоматического switching permission policy; протокольный breaker отдельно от model breaker.",
    "H0..H9/Stage3 остаются NOT_RUN до фактической проверки. Non-blocking follow-ups не становятся blocking; 16 findings покрыты ровно по одному месту без исключений."
  ],
  "coder_entry": "fix-from-panel",
  "iteration_budget_note": "Архитектурный возврат arch cycle1 a2 -> Architect cycle3 / delta v3; это не старт Coder и не новый голос/вердикт панели. 8 blocking findings сгруппированы в 6 RW по общей причине (VER-004: F-001+F-009; изоляция/auth: F-002+F-007); 8 non-blocking сохранены отдельно. Architect трассирует каждый RW в delta-plan/rework_resolutions с acceptance либо no_architecture_delta+evidence для следующего совета; кодовый teamlead_cycle остаётся 1, новый panel вызов этим handoff не запускается."
}
ARTIFACT_END>>>

КОНТЕКСТ:
Ниже приложены целиком формулировка цели владельца (`goal.md`), конверт задачи (`task.json`), полный аналитический пакет этапа 1 (`handoff-architect.md`, `evidence-ledger.md`, `research-plan.md`, `open-questions.md`, `handoff-qa.md`), а также стандарты проекта и Python-архитектуры (`aisdlc-gcge/AGENTS.md`, `aisdlc-gcge/skills/architecture.md`, `aisdlc-gcge/agents/scope-and-contracts.md`), соблюдение которых входит в твои обязательные проверки:
<<<ARTIFACT /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md sha256=4d953bef55831514175b6bf4150dc2af3bef47489913b6dccc2d536df6c83528
# Цель: Реалтайм-стриминг размышлений (reasoning) и шагов DeepSeek через мост opencode-zen-bridge в DSH

- Открыто: 2026-10-25 22:24:20 MSK
- Репозиторий (изолированный клон): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning` от `origin/dev`)
- Контур: `cel` + `analyst-teamlead` (`system-analyst` → `architect-software-product` → `Arch Panel` 3 судей → `Coder` → `Clean-Room L2` → `Code Council` 3 судей → открытый PR в `dev` + живая проверка тяжёлым путём).
- Бизнес-результат и критерий приёмки:
  1. При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.
  2. Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).
  3. Проведена живая проверка тяжёлым путём на реальном мосту и DSH.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=312a27bcf2c1443d32f2e032f0afd09e7f59d85f461c35bf677e134628afabd7
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608",
    "verification_surface_sha256": "702966bd09cdee8d15b6487f1147cd5672558cf3882cda3fe24ae4a608e63d40",
    "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b"
  }
}
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-architect.md sha256=9cd426324b8f49ddc760e3706e200709754a0a459b9e234f7b45b3b2669c6d9f
# Handoff to Architect: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — в `evidence-ledger.md` (`F-01..F-49`), вопросы — в `open-questions.md` (`OPEN-01..OPEN-17`, блокеров нет), план — в `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: видеть размышление DeepSeek в DSH в реальном времени при работе через `opencode-zen-bridge` (`127.0.0.1:9883`) и получить высокую
отзывчивость. Инцидент-образец — `session-423ca27f`, ход 2 шаг 5 (22:16:12 MSK): на экране только «Deep diving for 35s ···», затем более 780 с без единого токена (F-30, F-33).

Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | `opencode run --format json --thinking` v2.1.2 подписан только на `session.reasoning.ended` и `session.text.ended` и игнорирует `*.delta`: размышление и текст приходят одним блоком в самом конце шага (разница 0.00-0.17 мс), тишина stdout 1.9-2.7 с даже на здоровом вызове. Мост не может показать то, чего CLI не выдаёт | F-17, F-18, F-02, F-05 |
| RC-2 | Нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками; единственный потолок — `TIMEOUT_S=1800` с; холодный `--standalone` на БД 2.27 GB, пул ProxyRack и сериализующий `_StartupGate` дали зависания 780-856 с, а keepalive `{"content":""}` держал сокет DSH пустым | F-09, F-10, F-28, F-30, F-31, F-32, F-04 |
| RC-3 | В DSH строка `⚛ Think` не рисуется, пока нет непустого `reasoning_content`; пустые keepalive ничего не показывают; inline-превью свёрнутой строки обновляется только по завершённому абзацу (нужен `\n`) | F-36, F-37, F-04 |

Цепочка следствий: RC-1 лишает реалтайма здоровый вызов, RC-2 превращает больной вызов в многоминутную тишину, RC-3 делает любую тишину
для пользователя неотличимой от зависания (экран с таймером без содержимого). Реалтайм-транспорт без пунктов RC-2 и RC-3 проблему не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (pi-ai openai-completions, stream:true)  --HTTP SSE-->  Handler._stream_sse (:9883)        F-35, F-03
  Handler._stream_sse: 200+role-chunk -> _StartupGate -> spawn `opencode run ... --format json`  F-03, F-10, F-01
  opencode run (stdout JSON lines) -> _StdoutFeed(queue 4096) -> parse_opencode_event            F-14, F-02
     reasoning -> delta.reasoning_content (flush сразу)                                         F-05
     text      -> ToolCallParser.feed -> delta.content / delta.tool_calls                       F-05, F-06
     keepalive -> {"content": ""} раз в 15 с тишины                                              F-04
  opencode run --standalone -> opencode serve --stdio (дочерний) -> georouter :10830 -> Zen      F-30, F-26, F-27
  Пул ProxyRack: следующий порт на каждый spawn (env HTTP(S)_PROXY, loopback мимо)              F-15
DSH UI: непустой reasoning_content -> blockIsVisible -> ReasoningRow (превью по "\n")            F-36, F-37
DSH реплей: thinking -> assistant.reasoning_content -> мост игнорирует                          F-38, F-07
```

Граница совместимости (факт): всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)` (F-02, F-05); поэтому любой транспорт,
сводимый к тем же кортежам, не требует правки верхнего слоя (ретраи, парсер инструментов, usage, SSE-кадрирование).

## 3. Требования `REQ-001..REQ-020`

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие проверяемые формулировки (полная спецификация живёт в requirements и в `handoff-qa.md`).

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага | F-17, F-18, F-19 | AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс |
| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883 | F-35, F-34 | AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата |
| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными | F-43, F-40, F-42 | AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04) |
| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима | F-36, F-37, F-04, F-33 | AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме |
| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее | F-37, F-38, F-07, F-39 | AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее |
| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку | F-09, F-30, F-31 | AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с |
| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения | F-09, F-19, F-32 | AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout` |
| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с | F-14, F-30, F-33 | AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится |
| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка | F-11, F-12 | AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка |
| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты | F-06, F-05 | AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом |
| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути | F-05, F-11, F-43 | AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт |
| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native) | F-08, F-22, OPEN-07 | AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь |
| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта | F-10, F-11, F-15, F-32 | AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`) |
| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим | F-19, F-02 | AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры |
| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование | F-21, F-27 | AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey` |
| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода | F-32, F-30 | AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` |
| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс | F-45, F-46, F-47, F-48, F-49 | AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов |
| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок |
| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя |
| REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green) |

## 4. Варианты реализации RC-1 (сравнение по фактам, без выбора)

Вердикты: `выполнимо` / `выполнимо с условиями` / `невыполнимо`. Исходные данные по каждому — в ledger.

| Вариант | Суть | Задержка и реалтайм | Авторизация, маршрут, ротация IP | Изоляция встроенных инструментов | Параллелизм и SQLite | Тестируемость | Вердикт |
|---|---|---|---|---|---|---|---|
| L: только упрочнение legacy | `opencode run` остаётся, добавляются watchdog (REQ-006..008), статусные строки (REQ-004, REQ-005) | Реалтайма размышления нет: единый блок в конце шага (F-17, F-18); живость только за счёт статусных строк моста | Без изменений (F-15) | Без изменений (F-08) | Холодный spawn на каждый шаг сохраняется (F-28, F-30) | Полная: fake-CLI (F-43) | выполнимо; закрывает RC-2 и RC-3, но не RC-1 |
| A1: `opencode serve` короткоживущий на запрос, SSE `GET /api/event` | Мост поднимает `serve` на свободном порту с одноразовым паролем, создаёт сессию, шлёт prompt, читает дельты, затем `interrupt`/`DELETE` и `killpg` | Дельты размышления каждые 105-304 мс (median 127), первая дельта 1811 мс, text-дельты median 114 мс (F-19); старт сервера 109 мс (F-20) | Пароль случайный на процесс (F-21); env прокси задаётся на запуск, значит ротация сохраняется (F-15, OPEN-06); egress идёт через georouter (F-26, F-27) | Поле `permissions` в `POST /api/session` и `permission {"*":"deny"}` в конфиге (F-22), поведение не прогнано (OPEN-07) | Один процесс на запрос, idle RSS 152 MiB (F-20); БД та же 2.27 GB, нагрузка не мерилась (OPEN-08) | Нужен фейковый serve-сервер и адаптер событий; fake-CLI покрывает только legacy-путь (F-43) | выполнимо с условиями (OPEN-06, OPEN-07, OPEN-08) |
| A2: общий управляемый `opencode serve` (демон) | Один долгоживущий процесс; сессия на запрос | Те же дельты (F-19); нет холодного старта (фоновый `serve --service` уже работает, F-20) | Один набор env прокси на все запросы: общий IP упирается в дневной лимит (F-23, F-32); пароль на демон | Как в A1 | Общая БД и общий процесс, RSS 439 MiB у существующего демона (F-20); падение демона роняет все запросы | Тот же фейковый сервер; нужен супервизор и перезапуск | выполнимо с условиями; ротация IP не сохраняется без доработки (OPEN-06) |
| B: прямой OpenAI-совместимый HTTP-SSE к Zen | По образцу Google Direct (F-16): `http.client`, `readline`, дельты `reasoning_content` в реальном времени | Минимальная: без CLI, без БД, дельты как у апстрима (георутер отдаёт реалтайм, F-19) | Анонимный вызов без заголовков дал 429 `FreeUsageLimitError` напрямую и через пул (F-24, F-25); нужные заголовки или ключ неизвестны (OPEN-05); у `opencode` провайдера нет `apiKey` (F-27) | Не требуется: инструментов нет, эмуляция через `<tool_invoke>` остаётся | Нет SQLite и дочерних процессов | Лучшая: подмена HTTP-сервера, без `FAKE_OPENCODE` | выполнимо с условиями; осуществимость не доказана (OPEN-05) |
| C: гибрид | Приоритетный быстрый транспорт (A1 или B), при `ServeUnavailable`-подобном отказе тихий откат на legacy `opencode run`, как в muse-bridge | Реалтайм там, где транспорт доступен; legacy при отказе | Совмещает ограничения выбранных транспортов | Совмещает | Совмещает | Прецедент в репозитории: serve основной, exec запасной (F-40, F-41); fake-CLI тесты остаются на legacy-пути | выполнимо; объём работ максимальный |

Наблюдения для решения (факты, не выбор):
- Только A1/A2/B дают реалтайм на здоровом вызове; L не даёт, но самый дешёвый и закрывает RC-2/RC-3 (поэтапная поставка возможна: L затем A1/B/C).
- Квота Zen исчерпана на момент анализа (F-23): живая приёмка и PoC варианта B возможны после сброса около 03:00 MSK 2026-10-26.
- Совместимость с тестами: muse-bridge сохраняет exec-путь как резерв (F-40); у `opencode-zen-bridge` три модуля подменяют `OPENCODE_BIN` скриптом с событиями формата `run --format json` (F-43).
- Размер объёма ретраев и `_StdoutFeed` уже рассчитан на потоковые события (F-14); `step_finish` в `run` теряется (F-18), в serve есть `session.step.ended` с `tokens` (F-19).

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Аутентификация | Лимиты и режимы отказа | Тестовый контур |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` моста | HTTP SSE OpenAI (`stream:true`, `include_usage`) | Ingress от DSH | Bearer-ключ моста (значение не фиксируется) | слоты 6, ожидание 15 с, 12 ждущих, 503 при переполнении (F-13) | `tests/_http.py`, `test_step_interruption.py` (F-43) |
| `opencode run --format json` | stdout JSON-строки | Egress процесса | Нет (локальный CLI, белый список env) | потолок 1800 с, нет watchdog (F-09) | `FAKE_OPENCODE` (F-43) |
| `opencode serve` v2 | HTTP + SSE, Basic `opencode:<пароль>` | Egress | случайный пароль на процесс или `OPENCODE_SERVER_PASSWORD` (F-21) | старт 109 мс, API по OpenAPI (F-20, F-22) | тестового фейка нет |
| `model_georouter` :10830 | OpenAI-совместимый HTTP | Egress | нет у провайдера `opencode` (F-27) | `headers_timeout` 120 с, `inactivity_timeout` 300 с, 80+80 слотов, 3 pre-send повтора (F-26) | нет |
| Zen upstream `opencode.ai/inference/openai/v1` | OpenAI SSE | Egress | анонимный, дневной лимит (F-23..F-25) | `FreeUsageLimitError` 429 с `Retry-After` | нет |
| DSH `openai-completions` | SSE потребитель | Ingress | — | `streamIdleTimeoutMs` 1900000, `maxRetries` 0 (F-35) | живой DSH |

## 6. NFR-набросок (наблюдаемые величины)

- Нагрузка: 517 завершённых запросов за день, `deepseek-v4.1-flash-free` 44 (median 7.10 с, max 85.65 с) (F-32); пик параллелизма 6 (F-13).
- Задержка legacy: `step_start` 1.3-2.5 с, весь ответ 3.3-5.2 с одним блоком (F-17); реалтайм-путь serve: первая дельта размышления 1.8 с (F-19).
- Хвост: два запроса молчали 780-856 с с `out_chars=0` (F-30, F-31); `startup_gate_timeout` 72 за день (F-32).
- Ресурсы: мост RSS 22 MiB, 36 дескрипторов (F-29); idle serve 152 MiB, 20 дескрипторов (F-20); БД 2.27 GB (F-28).
- Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.

## 7. Конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS`)

Единицы СИ. Источники в комментариях; значения, не измеренные под нагрузкой, помечены `оценка`.

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1                      # один локальный демон LaunchAgent, F-34
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1                             # один Python-процесс ThreadingHTTPServer, F-12
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0           # бюджет рабочей станции, оценка
  kappa_skew: 1.0
  u_bg_worker: 0.02                # оценка
  U_pod_sidecars: 0.25             # дочерние процессы opencode, оценка
  Mem_limit_per_pod: 2147483648    # бюджет демона 2048 MiB, оценка
  Mem_rss_worker_max: 67108864     # 64 MiB; измерено 22 MiB, F-29
  Mem_shared_max: 1207959552       # 6 дочерних процессов по 192 MiB; idle serve 152 MiB, F-20
  RPS_peak: 0.2                    # 517 запросов за день, F-32
  A_max: 3                         # MAX_TOTAL_SPAWNS, F-11
  SLA_p99_s: 180.0                 # max наблюдаемый 85.65 с, F-32
  N_entities_max: 64
  Limit_dep_share_d: {georouter: 80, opencode_local_db: 10}   # georouter F-26; значение БД допущение эталона, OPEN-08
  Limit_dep_rps_d: {opencode_spawn: 1.0}                      # SPAWN_RATE_PER_S, F-11
  W_fetchers_d: 1
  J_init_s_d: 12.0                 # STARTUP_GATE_S, F-10
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0                 # KEEPALIVE_INTERVAL_S, F-04
  K_calls_d: 1
  T_base_s_d: 0.5                  # RETRY_BACKOFF_BASE_S, F-11
  T_cap_s_d: 2.0                   # RETRY_BACKOFF_CAP_S, F-11
  Max_stale_age_s_c: 0.0           # кэшей нет
  Min_healthy_ratio: 1.0
  B_retry_max: 6                   # RETRY_BUDGET_MAX, F-11
  min_reserve_retry_rps: 0.05      # RETRY_BUDGET_RESERVE_RPS, F-11
  FD_worker: 128                   # измерено 36 при active=0, F-29; запас под 6 потоков
  ulimit_n: 65536                  # launchctl limit maxfiles, F-29
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16384         # эфемерный диапазон 49152-65535
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12           # до 6 обработчиков и до 6 читателей stdout/SSE
  stdout_queue_max: 4096           # F-14
  ttft_visible_target_s: 1.0       # допущение, OPEN-11
  ttft_first_delta_target_s: 3.0   # допущение, OPEN-11; наблюдение serve 1.8 с, F-19
  first_event_watchdog_s: 20.0     # допущение, OPEN-11
  first_token_watchdog_s: 60.0     # допущение, OPEN-11
  stall_watchdog_s: 60.0           # допущение, OPEN-11
  client_gone_detect_s: 5.0        # допущение; сейчас 24.4 с, F-33
  keepalive_interval_s: 15.0       # F-04
  total_deadline_s: 1800           # TIMEOUT_S, F-09
  max_total_spawns: 3              # F-11
  startup_gate_s: 12               # F-10
  startup_wait_s: 5.0              # F-10
  bulkhead_max_concurrent: 6       # F-13
  slot_wait_s: 15.0                # F-13
  slot_max_waiters: 12             # F-13
  graceful_stop_s: 5               # SIGTERM затем SIGKILL, F-14
  serve_ready_s: 0.109             # F-20
```

Замыкание памяти (`HL-ENV-01`): `W × Mem_rss_worker_max + Mem_shared_max = 64 MiB + 1152 MiB = 1216 MiB ≤ 0.80 × 2048 MiB = 1638.4 MiB` (PASS, оценка). Для варианта A2 (общий демон, 439 MiB, F-20) вклад меньше.

## 8. Гейты Highload & Resilience (7 канонических + оси брифа)

### 8.1. Канонические гейты `architecture.md` (`#hl-env-and-four-gates-ssot`)

- `C-MULT/v1`:
  - `C-MULT-I1`: `1 × 1 × 6 = 6 ≤ 0.60 × 80 = 48` для георутера (F-26) — PASS; для локальной БД предел неизвестен (OPEN-08), поэтому ограничителем остаются `_StartupGate`, `SPAWN_RATE_PER_S` и семафор слотов (F-10, F-11, F-13).
  - `C-MULT-I2`: очереди ограничены (`_StdoutFeed` 4096, слоты 6, ждущих 12, ожидание 15 с) (F-13, F-14) — PASS; новый SSE-читатель обязан иметь такой же предел.
  - `C-MULT-I3`: семафоры и замки — синглтоны процесса (`W=1`) (F-12) — PASS.
  - `C-MULT-I4`: освобождение слота и остановка процесса в `finally` (F-14) — PASS как as-is; новые ресурсы (сессия serve, SSE-сокет) должны освобождаться там же.
  - `C-MULT-I5`: `FD_worker = 128 ≤ 0.70 × 65536`; порты `0.6 × 1 × 60 + 12 = 48 ≤ 0.50 × 16384 = 8192` — PASS (оценка).
- `S-HERD/v1`:
  - `S-HERD-I1`: серия холодных стартов сериализуется `_StartupGate` (F-10); у A1 старт сервера 109 мс (F-20).
  - `S-HERD-I2`: Full Jitter 0.5/2.0 уже в коде (F-11); повторы по watchdog обязаны использовать его.
  - `S-HERD-I3..I5`: N/A, поллеров Control Plane, `If-None-Match` и `singleflight` в мосте нет (граф вызовов as-is: `do_POST` → `_stream_sse`/`_serve_json` → запуск процесса); доказательство `git diff` предоставляет Architect после дизайна.
- `H-CPU/v1`:
  - `H-CPU-I2`: регулярные выражения компилируются при импорте (F-06, F-11); разбор SSE-дельт не должен вызывать `re.compile` в цикле.
  - `H-CPU-I3`: путь с выключенной новой функцией должен возвращаться за `O(1)` (kill-switch, REQ-003).
  - `H-CPU-I5`: оценка `0.02 + 0.2 × (0.02 + 3 × 0.05) = 0.054 ≤ 0.70` (PASS, не измерено); поток serve даёт около 10 событий в секунду на запрос (F-19), то есть до 60 разборов JSON в секунду на 6 запросах.
  - `H-CPU-I1`, `H-CPU-I4`: N/A (индексов маршрутизации и event loop нет).
- `R-BULK/v1`:
  - `R-BULK-I1`: вспомогательные ожидания `3 × 5.0 с (gate) + 0 + 1.0 + 2.0 = 18.0 с ≤ 0.30 × 180 = 54 с` (PASS); наихудший случай с watchdog первого события `3 × (20 + 5) + 3 = 78 с ≤ 180 с`.
  - `R-BULK-I2`: потолок запусков 3, бюджет повторов 6, слоты 6 (F-11, F-13) — PASS.
  - `R-BULK-I3`: классификация транзиентных и детерминированных ошибок существует (F-11, `_is_transient_stream_error`); новые причины watchdog относятся к транзиентным.
  - `R-BULK-I4`, `R-BULK-I5`: N/A (пула прокси-нод с health-ранжированием и мульти-тенантных пулов в мосте нет; прокси из пула — подстановка в env, F-15).
- `T-LIFE/v1`: каждый процесс и его читатель закрываются `_stop_proc` в `finally` (F-14); для A1/A2 добавляются `interrupt`, `DELETE` сессии и `killpg` (F-22).
- `O-EXIT/v1`: строка выхода на каждом `do_POST` уже есть (F-32); расширение полями — REQ-016.
- `M-SEM/v1`: N/A на этапе анализа (единый пул слотов `_slots`, F-12); подтверждение `git diff` и графа вызовов — за Architect.

### 8.2. Оси из брифа (`R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`)

В каноне этих меток нет (OPEN-15). Трактовка аналитика (допущение) и статус по фактам:

| Ось | Трактовка | Статус по фактам |
|---|---|---|
| `R-OUT` | исходы запроса и повторы (`exit_reason`, потолок A_max) | потолок есть (F-11); новые причины watchdog требуют кодов (REQ-016) |
| `M-CONF` | конфигурация и kill-switch новой функции | переменные окружения как у `STEP_RECOVERY` (F-11), REQ-003 |
| `F-DEG` | деградация: отказ быстрого транспорта не должен ломать ответ | прецедент serve→exec в muse-bridge (F-40); fail-open для статусных строк, fail-closed для политики инструментов (REQ-012) |
| `S-SEC` | секреты, пароль serve, изоляция инструментов | пароль случайный на процесс (F-21), `apiKey` не выгружался (F-27), REQ-015 |
| `X-BOUND` | границы процессов и ресурсов (killpg, FD, сессии) | F-14, F-29, REQ-008 |

## 9. Non-Goals

- Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).
- Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.
- Не модифицировать текст размышления модели ради превью (OPEN-13).
- Не менять модель, список моделей, логику выбора эффорта и каталог Zen.
- Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.
- Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.

## 10. Forbidden Scope

- Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.
- Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.
- Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.
- Использование `security find-generic-password`.
- Правка `opencode.db` и общего каталога состояния `opencode` напрямую.
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-49` (ledger).
- `blocking open questions`: пусто.
- `assumptions`: `OPEN-04..OPEN-17` с рабочими допущениями из `open-questions.md`.
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): первая видимая строка до 1.0 с; первая дельта размышления до 3.0 с; пауза до 15 с; молчание до 20 с (допущения OPEN-11), текущие значения в разделе 6.
- `risks`: R1 — прямой Zen без заголовков не осуществим (OPEN-05); R2 — потеря ротации IP при общем демоне (OPEN-06); R3 — встроенные инструменты `opencode` исполнятся при неверной политике (OPEN-07); R4 — контенция SQLite при параллельных serve (OPEN-08); R5 — квота Zen блокирует живую приёмку до около 03:00 MSK 2026-10-26 (F-23); R6 — дубли размышления при повторах (OPEN-14); R7 — красная базовая линия блокирует Full Suite Gate (OPEN-04).

## 12. Обратный канал в требования

Противоречий фактов с REQ-ID нет. Расхождение с брифом: в `tests/` 17 модулей `test_*.py`, а не 16 (F-42); ссылка на «16 модулей» в постановке неточна, на объём работ не влияет.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/evidence-ledger.md sha256=2a5c9f7f8a8fc20573d69a4617da87bdfbf1f57e70681e7036ece27541fe0367
# Evidence Ledger: zen-realtime-reasoning (opencode-zen-bridge, реалтайм-размышление)

Дата сбора: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Роль: System Analyst (Stage 1).
Формат факта: `[F-NN] (FACT-0NN) утверждение | источник | YYYY-MM-DD`. Секреты не выносятся
(пароль `opencode serve`, `apiKey`, креды ProxyRack, логины пула не воспроизводились и не сохранялись).
Пути с `~/` — домашний каталог. Пути без `~/` — относительно корня репозитория
`bridges/opencode-zen-bridge/`, если не указано иное.
Эмпирические PoC-скрипты и логи аналитика: `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`
(вне репозитория; код продукта не менялся).

## 1. Код моста (повторная сверка по исходнику)

[F-01] (FACT-001) Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`) | server.py:1146-1161, 966-969, 1617-1649 | 2026-10-25
[F-02] (FACT-002) `parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают | server.py:2417-2462 | 2026-10-25
[F-03] (FACT-003) `Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{"role":"assistant","content":""}` до `_StartupGate`, spawn и чтения stdout | server.py:3312-3327, 3399-3412 | 2026-10-25
[F-04] (FACT-004) Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{"content":""}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content` | server.py:49, 3437-3450, 865-952 | 2026-10-25
[F-05] (FACT-005) События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content` | server.py:3462-3493 | 2026-10-25
[F-06] (FACT-006) `ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len("<tool_invoke>")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям | server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323) | 2026-10-25
[F-07] (FACT-007) `_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает | server.py:1848-1888 | 2026-10-25
[F-08] (FACT-008) Конфиг `opencode` для дочернего процесса по умолчанию: `permission {"*":"ask"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1` | server.py:228-231 | 2026-10-25
[F-09] (FACT-009) В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с) | server.py:46, 3450, команда grep от 2026-10-25 | 2026-10-25
[F-10] (FACT-010) `_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start` | server.py:1197-1236, 3399-3411, 3451 | 2026-10-25
[F-11] (FACT-011) Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду | server.py:277, 287-298, 309-314, 1340-1368, 1471-1535 | 2026-10-25
[F-12] (FACT-012) Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор | server.py:1458-1470, 3989-3996 | 2026-10-25
[F-13] (FACT-013) `MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12` | server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK | 2026-10-25
[F-14] (FACT-014) `_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25` | server.py:848-862, 865-952 | 2026-10-25
[F-15] (FACT-015) Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст | server.py:1047-1082, 1093-1131; start.sh:24-31 | 2026-10-25
[F-16] (FACT-016) `_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({"reasoning_content": text})` в реальном времени; прецедент прямого маршрута для Option B | server.py:3127-3266 (reasoning emit около 3219) | 2026-10-25

## 2. Эмпирика `opencode` v2.1.2 (Zone B и PoC аналитика)

[F-17] (FACT-017) `opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1) | explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK) | 2026-10-25
[F-18] (FACT-018) Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended` | explorer-zone-b.md §2 | 2026-10-25
[F-19] (FACT-019) `opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1) | explorer-zone-b.md §1, §3 | 2026-10-25
[F-20] (FACT-020) Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB | sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK | 2026-10-25
[F-21] (FACT-021) Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode` | sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25 | 2026-10-25
[F-22] (FACT-022) OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate` | sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B) | 2026-10-25
[F-23] (FACT-023) PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {"*":"deny"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса | sa-poc/poc_serve.log | 2026-10-25
[F-24] (FACT-024) Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс | sa-poc/poc_georouter.log | 2026-10-25
[F-25] (FACT-025) Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена | sa-poc/poc_direct_zen_proxy.log | 2026-10-25
[F-26] (FACT-026) `model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz` | ~/.config/model-georouter/config.json (значения без секретов) | 2026-10-25
[F-27] (FACT-027) В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось) | ~/.config/opencode/opencode.json (обход ключей с маскированием) | 2026-10-25
[F-28] (FACT-028) `~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет | ls -l, opencode run --help от 2026-10-25 | 2026-10-25
[F-29] (FACT-029) Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard) | ps, lsof, launchctl limit от 2026-10-25 22:4x MSK | 2026-10-25

## 3. Рантайм и инцидент (Zone D)

[F-30] (FACT-030) Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет | explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK | 2026-10-25
[F-31] (FACT-031) Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода | explorer-zone-d.md §2 | 2026-10-25
[F-32] (FACT-032) Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10 | explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log | 2026-10-25
[F-33] (FACT-033) Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`) | explorer-zone-d.md §3 | 2026-10-25
[F-34] (FACT-034) Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK | explorer-zone-d.md §1; /health от 2026-10-25 | 2026-10-25

## 4. Потребитель: DSH Desktop

[F-35] (FACT-035) Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage` | ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C) | 2026-10-25
[F-36] (FACT-036) Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка) | 2026-10-25
[F-37] (FACT-037) UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===""` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\n` | client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка) | 2026-10-25
[F-38] (FACT-038) При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07) | app.asar openai-completions.js, смещения 116117903-116120153 | 2026-10-25
[F-39] (FACT-039) Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков | ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста | 2026-10-25

## 5. Эталон muse-bridge (ADR-0004)

[F-40] (FACT-040) `muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса | bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185 | 2026-10-25
[F-41] (FACT-041) `muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`) | bridges/muse-bridge/server.py:165, 4150-4156 | 2026-10-25

## 6. Тесты и базовая линия

[F-42] (FACT-042) В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`) | ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log | 2026-10-25
[F-43] (FACT-043) Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env` | tests/*.py (grep OPENCODE_BIN и _fake_cli) | 2026-10-25
[F-44] (FACT-044) Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`) | tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py | 2026-10-25
[F-45] (FACT-045) Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются | baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log | 2026-10-25
[F-46] (FACT-046) Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях | sa_iso_file.log | 2026-10-25
[F-47] (FACT-047) Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный | sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287 | 2026-10-25
[F-48] (FACT-048) Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду) | baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368 | 2026-10-25
[F-49] (FACT-049) `grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`) | git log -S от 2026-10-25 | 2026-10-25

## Таблица T1. Тайминги `opencode` (Zone B, модель `opencode/deepseek-v4.1-flash-free`, variant `high`, `elapsed_ms`)

| Режим | 1-е событие | 1-й reasoning | reasoning-событий | интервал дельт | 1-й text | событий всего | завершение |
|---|---:|---:|---:|---|---:|---:|---:|
| `run --format json` PIPE, фоновый сервис | 2378.85 | 4850.67 (1 блок, 768 симв.) | 1 | нет | 4850.80 | 3 | 4919.34 |
| `run --format json` PTY, фоновый сервис | 1315.53 | 3219.27 (1 блок, 285 симв.) | 1 | нет | 3219.44 | 3 | 3281.97 |
| `run --format json --standalone` PIPE | 2501.60 | 5137.26 (1 блок, 549 симв.) | 1 | нет | 5137.26 | 3 | 5213.40 |
| `run --format json --standalone` PTY | 2226.36 | 4941.59 (1 блок, 412 симв.) | 1 | нет | 4941.71 | 3 | 5023.95 |
| `opencode serve` v2, `GET /api/event` | 161.22 (`integration.updated`), 233.06 (`execution.started`) | 1810.98 (1-я дельта) | 10 дельт + started + ended | min 105.64, median 127.25, max 304.32 | 3260.64 (17 дельт, median 114.49) | 53 | 5558.06 |

## Сводка покрытия (для DoD)

Всего фактов: 49. Источники воспроизводимы командами и путями из колонки «источник». Факты F-23, F-24, F-25 фиксируют
состояние внешней квоты на 2026-10-25 22:4x MSK и могут измениться после сброса лимита.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/research-plan.md sha256=5cef25c8a8901b241e08ed31ba884d2178cf1ac445ceaf0e70f7c697ea282cbb
# Research Plan: zen-realtime-reasoning (реалтайм-размышление `opencode-zen-bridge` в DSH)

Роль: System Analyst (Stage 1, preset `analyst-teamlead`), тип — feasibility study + as-is обследование, глубина — standard (S2).
Дата: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Артефакты: `analysis/zen-realtime-reasoning/`.
Владелец вывода: владелец продукта (расхождения «ожидали X, оказалось Y» принимает он; финальная архитектура — `architect-software-product`).

## 1. Scope

Запрос владельца: при запуске DeepSeek через `opencode-zen-bridge` (`127.0.0.1:9883`) в DSH видеть размышление в реальном
времени и получать отличную отзывчивость, чтобы было видно, что процесс идёт. Инцидент-образец: сессия `session-423ca27f`,
ход 2 шаг 5 (22:16:12 MSK), экран «Deep diving for 35s ···» без строки `⚛ Think`, затем молчание более 780 с.

В периметре исследования: код `bridges/opencode-zen-bridge/` (`server.py`, `start.sh`, `tests/`), эталон `bridges/muse-bridge/server.py`,
живой `opencode` v2.1.2 (CLI и `opencode serve`), локальный `model_georouter` (:10830), потребитель DSH Desktop (`app.asar`),
рантайм-логи моста за 2026-10-25.
Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).

## 2. Проверяемые гипотезы (исход — в `evidence-ledger.md`)

| Гипотеза | Итог | Основание |
|---|---|---|
| RC-1: `opencode run --format json` буферизует размышление и текст до конца шага, поэтому реалтайма нет даже на здоровом вызове | подтверждена | F-17, F-18 |
| RC-1a: реалтайм-путь на этом хосте существует (`opencode serve` v2 SSE, дельты каждые ~110-130 мс) | подтверждена (замер Zone B), повтор заблокирован квотой | F-19, F-23 |
| RC-1b: прямой анонимный HTTP-SSE к Zen как у Google Direct осуществим без `opencode` | не подтверждена: два PoC дали 429 | F-24, F-25 |
| RC-2: холодный spawn + отсутствие watchdog приводят к немым зависаниям на 13-14 минут | подтверждена по коду и логам | F-09, F-10, F-30, F-31 |
| RC-3: пустые keepalive не показывают ничего, а превью `⚛ Think` требует `\n` | подтверждена | F-36, F-37 |
| Три красных теста базовой линии — загрязнение теста либо реальное взаимодействие бюджетов повтора | обе причины присутствуют | F-47, F-48, F-49 |

## 3. Зоны обследования (веер Wave 1, без пересечений)

- Зона A (код моста и эталон): `server.py`, `muse-bridge` ADR-0004 — отчёт `explorer-zone-a.md`.
- Зона B (контракты и эмпирика `opencode`): CLI vs `opencode serve` vs wire Zen — отчёт `explorer-zone-b.md`.
- Зона C (потребитель): DSH `openai-completions`, `ReasoningRow`, `blockIsVisible` — отчёт `explorer-zone-c.md`.
- Зона D (рантайм): логи, зависшие PID, реконструкция скриншота — отчёт `explorer-zone-d.md`.
- Сверка аналитика (read-only, PoC в `/tmp`): повторная проверка кода по строкам, изоляция красных тестов, прямой HTTP-SSE PoC,
  OpenAPI `opencode serve`, структура журнала сессии DSH, ресурсы процессов.

## 4. Методология

1. Факт или открытый вопрос: каждое утверждение — строка `[F-NN]` с источником и датой, иначе запись в `open-questions.md`.
2. Эмпирика важнее чтения: тайминги `elapsed_ms` снимались по живым процессам, а не выводились из кода.
3. Секреты не выносятся: пароль `opencode serve`, `apiKey`, креды пула ProxyRack не печатались и не сохранялись; PoC использовали временный пароль и порт.
4. Код продукта не менялся; PoC-скрипты и логи лежат в `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`.
5. Выбор архитектуры не делается: варианты сравниваются по фактам в `handoff-architect.md`, вердикт — «выполнимо / с условиями / невыполнимо».
6. Квота Zen (`FreeUsageLimitError`) исчерпана на 22:4x MSK, поэтому часть замеров переведена в отложенные вопросы с условием повтора после сброса.

## 5. Реестр спайков

Формат строки: `ID | вопрос | источник | метод | таймбокс | deliverable | критерий закрытия | зависит/блокирует | статус | результат | факт | отметка`
(таймбокс и факт — минуты).

INV-01 | Где мост теряет реалтайм (маппинг событий и SSE-кадрирование) | server.py:2417-2462 и 3312-3493 | чтение кода и сверка с Zone A | 25 | таблица потока событий в ledger | найден участок и порядок отправки чанков | блокирует INV-02 | closed | F-05 | 18 | ok
INV-02 | Выдаёт ли `opencode run --format json` дельты размышления и текста | ~/.opencode/bin/opencode и живые запуски | замеры PIPE/PTY × standalone/сервис | 40 | таблица T1 | показано, что дельт нет и почему | зависит от INV-01 | closed | F-18 | 35 | ok
INV-03 | Реалтайм-путь `opencode serve` v2: события, тайминги, схема API | `GET /api/event`, OpenAPI v2.1.2 | живой SSE-замер и разбор OpenAPI | 40 | схема эндпоинтов и тайминги | задокументированы события и интервалы дельт | зависит от INV-02 | closed | F-19 | 38 | ok
INV-04 | Осуществим ли прямой анонимный HTTP-SSE к Zen (Option B) | server.py:3127-3266 и opencode.ai/inference | PoC через georouter и через CONNECT-туннель пула | 30 | вердикт осуществимости | получены токены либо зафиксирован отказ с причиной | блокирует выбор Option B | open | OPEN-05 | 22 | отказ 429 в обоих PoC, нужен повтор после сброса лимита
INV-05 | Чем ограничено ожидание первого токена (RC-2) | server.py:46, 1197-1236, 3450 и логи Zone D | grep по сторожам и разбор логов | 30 | перечень таймеров и бюджетов | подтверждено отсутствие TTFT и stall watchdog | зависит от INV-01 | closed | F-09 | 20 | ok
INV-06 | Контракт видимости размышления в DSH (RC-3) | app.asar, client.js, openai-completions.js | чтение бандла и подтверждение символов поиском | 30 | контракт `blockIsVisible` и `\n` | найдены условия появления строки Think | независим | closed | F-37 | 24 | ok
INV-07 | Возвращает ли DSH размышление мосту и что с ним делает мост | app.asar и server.py:1848-1888 | поиск `reasoning_content` в бандле и в `_render_turn` | 20 | вывод о безопасности статусных строк | найден путь реплея и точка игнорирования | зависит от INV-06 | closed | F-38 | 14 | ok
INV-08 | Совместимость с fake-CLI тестами и прецедент muse-bridge | tests/*.py и muse-bridge/server.py:338-4185 | grep OPENCODE_BIN и чтение fallback | 25 | карта тестов и паттерн fallback | описаны подмена CLI и паттерн serve-to-exec | независим | closed | F-43 | 19 | ok
INV-09 | Природа трёх красных тестов базовой линии | baseline_uvx_pytest.log и tests/test_step_interruption.py | прогон файла и подмножества, разбор логов | 30 | классификация причин | определены причины каждого из трёх тестов | независим | closed | F-47 | 26 | ok
INV-10 | Изоляция встроенных инструментов `opencode` в режиме serve | OpenAPI `permissions` и `session.tool.*` | чтение схемы, живой прогон заблокирован квотой | 30 | схема сопоставления событий | подтверждена эквивалентность с режимом run | блокирует контракт адаптера | open | OPEN-07 | 12 | схема есть, поведение не прогнано из-за free-limit
INV-11 | Параллелизм, SQLite и ресурсы нескольких процессов serve | opencode.db 2.27 GB и RSS процессов | замер idle RSS и FD, нагрузочный прогон не выполнен | 30 | оценка ресурсов | получены числа под параллельной нагрузкой | зависит от INV-03 | open | OPEN-08 | 10 | измерен только idle serve 152 MiB
INV-12 | Время до первого токена на тяжёлом промпте около 103 KB через serve | сессия 423ca27f и serve | замер после сброса квоты | 20 | таблица TTFT для 100 KB | получен TTFT при `prompt_chars` около 103088 | зависит от INV-03 | open | OPEN-09 | 5 | квота исчерпана до около 03:00 MSK 2026-10-26
INV-13 | Совместимость ротации чистых IP с долгоживущим serve | server.py:1047-1131 и config georouter | чтение кода и конфига | 25 | вывод о маршруте egress | определено, ходит ли serve напрямую либо через georouter | зависит от INV-04 | open | OPEN-06 | 15 | egress georouter известен, поведение прокси у serve не проверено
INV-14 | Инкрементально ли `ToolCallParser` отдаёт `content` при дельтах | server.py:2213-2338 | чтение алгоритма и существующих тестов | 20 | описание удерживаемого хвоста | задан максимум удерживаемых символов | независим | closed | F-06 | 11 | ok

## 6. Состав handoff-пакетов (потребители)

- `handoff-architect.md` — Architect (S2): корневые причины, требования `REQ-*`, сравнение вариантов, `HL-ENV/v1`, гейты, non-goals.
- `handoff-qa.md` — QA и Coder-тесты: red→green сценарии, живой тяжёлый путь, протокол замеров.
- `handoff-dev.md` не готовится: задача класса S2, вход в разработку только через Архитектора (ARCH_GATE).
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/open-questions.md sha256=2b584b43026f570898d9ced218e0d989f2d1f460dded380ad38c0df6defba79f
# Open Questions: zen-realtime-reasoning

Дата: 2026-10-25 (MSK). Блокеров нет: ни один вопрос не останавливает ветку Архитектора. Все вопросы класса «МОЖНО ПРОДОЛЖИТЬ»;
статус закрытия (`RESOLVED` — закрыт фактами ledger, `DEFERRED` — отложен с рабочим допущением) записан префиксом в поле «что мешает закрыть».
Формат строки: `OPEN-NN | класс | вопрос | что мешает закрыть | кто нужен | риск | допущение`.

OPEN-01 | МОЖНО ПРОДОЛЖИТЬ | Отправляет ли DSH размышление обратно мосту и что мост с ним делает | RESOLVED: DSH кладёт thinking в assistant-сообщение полем `reasoning_content`, мост его игнорирует (F-38, F-07) | никто | синтетические статусные строки не попадут в промпт модели | не требуется
OPEN-02 | МОЖНО ПРОДОЛЖИТЬ | Почему красны три теста базовой линии: загрязнение теста или реальная ошибка бюджета | RESOLVED: два теста ждут 4 запуска при потолке `MAX_TOTAL_SPAWNS=3` (красные и в изоляции), третий красный из-за общего `_RetryBudget` на класс (F-47, F-48, F-49) | никто | красная базовая линия блокирует Full Suite Gate | не требуется
OPEN-03 | МОЖНО ПРОДОЛЖИТЬ | Есть ли в репозитории решение совместимости «потоковый транспорт плюс тесты на поддельном CLI» | RESOLVED: muse-bridge держит serve как основной путь и тихо падает на exec при `ServeUnavailable` (F-40) | никто | паттерн применим как факт, выбор за Архитектором | не требуется
OPEN-04 | МОЖНО ПРОДОЛЖИТЬ | Входит ли исправление трёх красных тестов базовой линии в MR этой фичи | DEFERRED: решение о границах MR принимает владелец вместе с Архитектором | владелец, Архитектор | MR не пройдёт Full Suite Gate при красной базе | Входит: ожидание 4 приводится к потолку 3 и бюджет повтора изолируется на тест, поведение продукта не меняется
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | Какие заголовки или ключ нужны прямому анонимному HTTP-SSE к Zen (Option B) | DEFERRED: два PoC без `Authorization` дали HTTP 429 `FreeUsageLimitError`, а квота исчерпана до около 03:00 MSK 2026-10-26 (F-24, F-25) | Architect и Coder-спайк после сброса лимита | Option B может оказаться неосуществимым без перехвата заголовков `opencode` | Option B считается «выполнимо с условиями» и не выбирается без успешного PoC
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | Совместима ли пер-запросная ротация чистых IP (пул ProxyRack) с одним долгоживущим `opencode serve` | DEFERRED: у `serve` один набор переменных прокси на процесс, а поведение прокси при `baseURL` на loopback-georouter не проверено (F-15, F-26) | Architect | общий IP упирается в дневной лимит (22 срабатывания за день, F-32) | Предполагается один короткоживущий `serve` на запрос (старт 109 мс, F-20), чтобы ротация сохранялась
OPEN-07 | МОЖНО ПРОДОЛЖИТЬ | Как в режиме serve изолируются встроенные инструменты `opencode` и как события `session.tool.*` соответствуют текущему `tool_use` | DEFERRED: схема `permissions` есть (F-22), живой прогон невозможен из-за free-limit (F-23) | Architect, Coder | модель выполнит встроенный инструмент вместо эмуляции DSH | Нужна явная политика `deny` для всех встроенных инструментов и адаптер событий к текущему формату `tool_use`
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | Выдержат ли шесть параллельных процессов serve блокировки SQLite `opencode.db` 2.27 GB и бюджет памяти | DEFERRED: измерен только простаивающий serve (RSS 152 MiB, F-20), нагрузочный прогон не делался | QA, Coder | `database is locked` при параллельном старте (прецедент в комментарии к `FAIL_RETRY_LIMIT`) | Верхняя оценка 192 MiB на процесс и сохранение `_StartupGate` и `SPAWN_RATE_PER_S`
OPEN-09 | МОЖНО ПРОДОЛЖИТЬ | Каков TTFT через serve на промпте около 103 KB как в инциденте | DEFERRED: квота исчерпана (F-23), повторить после сброса лимита около 03:00 MSK 2026-10-26 | QA | цель отзывчивости может не достигаться на тяжёлых промптах | Берётся замер Zone B на коротком промпте (первая дельта 1811 мс, F-19)
OPEN-10 | МОЖНО ПРОДОЛЖИТЬ | Что именно блокирует холодный `opencode run --standalone` до сети (у PID 11488 нет TCP-соединений) | DEFERRED: первопричина (SQLite, каталог моделей, фоновый сервис) не установлена (F-30) | Coder-спайк | зависания могут повторяться на новом транспорте | Митигация независима от причины: watchdog первого события и паузы между чанками с убийством группы процессов
OPEN-11 | МОЖНО ПРОДОЛЖИТЬ | Какие числовые цели отзывчивости принимает владелец | DEFERRED: владелец сформулировал «отличную отзывчивость» без чисел | владелец | критерии приёмки останутся субъективными | Первая видимая строка не позже 1.0 с, первая реальная дельта размышления не позже 3.0 с на здоровом апстриме, пауза между чанками не больше 15 с, отсутствие первого события не больше 20 с до явной ошибки или повтора
OPEN-12 | МОЖНО ПРОДОЛЖИТЬ | Допустимы ли синтетические статусные строки моста в `reasoning_content` | DEFERRED: DSH сохраняет их в журнале сессии и показывает в строке Think (F-37, F-39), мост при реплее их игнорирует (F-07) | владелец, Architect | статусный текст смешивается с мышлением модели в транскрипте | Допустимы короткие строки, оканчивающиеся символом новой строки, с префиксом «[мост]»
OPEN-13 | МОЖНО ПРОДОЛЖИТЬ | Допустимо ли менять текст размышления модели, вставляя переводы строк для обновления inline-превью | DEFERRED: превью требует `\n` (F-37), а изменение текста затрагивает журнал и реплей | владелец, Architect | искажение размышления модели | Текст модели не изменяется, живость обеспечивают только отдельные статусные строки
OPEN-14 | МОЖНО ПРОДОЛЖИТЬ | Как показывать размышление повторной попытки, если часть размышления уже отдана клиенту | DEFERRED: при потоковой выдаче дубли неизбежны, текущий `dedup_prefix` работает только для видимого текста | Architect | двоение блока Think в UI | Размышление не дедуплицируется, между попытками вставляется отдельная статусная строка
OPEN-15 | МОЖНО ПРОДОЛЖИТЬ | Как трактовать метки гейтов из брифа `R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND` | DEFERRED: в каноне `aisdlc-gcge/agents/architecture.md` этих меток нет, там `C-MULT`, `S-HERD`, `H-CPU`, `R-BULK`, `T-LIFE`, `O-EXIT`, `M-SEM` | владелец брифа | расхождение критериев приёмки гейтов | Заполнены 7 канонических гейтов и отдельная таблица доменных осей брифа с трактовкой аналитика
OPEN-16 | МОЖНО ПРОДОЛЖИТЬ | Дают ли режимы `opencode run --server <url>` и `--format default` потоковую выдачу | DEFERRED: проверялся только `--format json`, а справка показывает два формата без дельт (F-28) | Coder-спайк | пропущен более дешёвый путь | Не дают, путь через serve считается единственным готовым реалтаймом
OPEN-17 | МОЖНО ПРОДОЛЖИТЬ | Как синхронизировать копию `~/.dsh/bridges/opencode-zen-bridge/` и перезапустить LaunchAgent после MR | DEFERRED: деплой вне объёма анализа, развёрнутая копия сейчас идентична репозиторию (F-34) | владелец | живая проверка пойдёт на старой копии | Побайтовая сверка и перезапуск `com.user.dsh-opencode-zen-bridge` входят в живую приёмку

## ВОПРОСЫ ВЛАДЕЛЬЦУ

1. [МОЖНО ПРОДОЛЖИТЬ] Принимаете ли числовые цели отзывчивости (первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с)? Почему нужен: от них зависят пороги watchdog и критерии приёмки. Допущение: значения приняты. После ответа: пороги уходят в конфигурацию.
2. [МОЖНО ПРОДОЛЖИТЬ] Допустимы ли статусные строки моста с префиксом «[мост]» внутри блока Think? Почему нужен: они сохраняются в журнале DSH. Допущение: допустимы. После ответа: Architect фиксирует формат.
3. [МОЖНО ПРОДОЛЖИТЬ] Входит ли исправление трёх красных тестов базовой линии в этот MR? Почему нужен: от этого зависит Full Suite Gate. Допущение: входит. После ответа: QA включает правки тестов в план.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-qa.md sha256=d78c3855467d1d7c7a97a0a62ab7f8b79b311b48665a0327d04cffaa1ecf0e3b
# Handoff to QA: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребители: QA и Coder (написание тестов red→green), Reviewer, живая приёмка.
Требования — `REQ-001..REQ-020` в `handoff-architect.md`; факты — `F-01..F-49` в `evidence-ledger.md`; вопросы — `OPEN-01..OPEN-17` в `open-questions.md`.
Архитектурный транспорт (serve, прямой HTTP, гибрид) выбирает Architect; сценарии ниже сформулированы относительно «нового быстрого транспорта» и не зависят от выбора.

## 1. Тестовые контуры и команды

| ID | Контур | Команда или способ | Состояние |
|---|---|---|---|
| VER-001 | Основной набор | `cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/` | 378 тестов, на ветке красные 3 (F-42, F-45) |
| VER-002 | Только файл прерываний | `uvx pytest -q -p no:cacheprovider tests/test_step_interruption.py` | те же 3 красных (F-46) |
| VER-003 | Порядконезависимость | `uvx --with pytest-randomly pytest -q -p no:cacheprovider -p randomly tests/test_step_interruption.py` (3 разных `-p randomly_seed`) | после исправления базы красных нет при любом порядке |
| VER-004 | Fake-CLI | подмена `server.OPENCODE_BIN` скриптом с JSON-событиями (F-43), хелпер `allow_child_env` | рабочий |
| VER-005 | Fake-transport (новый) | локальный HTTP-сервер стандартной библиотеки, отдающий SSE по схеме транспорта | нужно написать |
| VER-006 | Живой мост | `http://127.0.0.1:9883` (LaunchAgent `com.user.dsh-opencode-zen-bridge`) | работает (F-34), квота Zen исчерпана (F-23) |
| VER-007 | Живой DSH | DSH Desktop, модель `DeepSeek V4.1 Flash (Zen) High`, `opencode-zen-bridge` | доступен (F-35) |

Базовой линией считается только `uvx pytest`: запуск с командой `pytest` и `python3 -m unittest discover` из корня не работают (F-45).
Ни один существующий тест не измеряет реальное время прихода чанков (F-44): `_post` читает ответ целиком `resp.read()`.

## 2. Красная базовая линия (до начала разработки)

| Тест | Симптом | Причина по фактам | Что проверять после правки |
|---|---|---|---|
| `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` | `2 != 4` в полном прогоне, `3 != 4` в изоляции | ожидание 4 запусков при потолке `MAX_TOTAL_SPAWNS=3` (F-47); в полном прогоне добавляется исчерпание `_RetryBudget` (F-48) | ожидание согласовано с потолком 3 либо потолок задан тестом явно; результат одинаков в изоляции и в полном прогоне |
| `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream` | `2 != 4` | то же | то же |
| `test_unmapped_then_error_stops_proc_json` | `1 != 2` только в составе класса, в изоляции зелёный | общий `_RetryBudget` одного `Server` на класс (`setUpClass`), токены расходуются предыдущими тестами (F-48) | бюджет повтора изолирован на тест (новый `_Resilience` или сброс токенов в `setUp`) |

Ни один тест не меняет `MAX_TOTAL_SPAWNS` (F-49); поведение продукта правкой этих тестов не меняется (OPEN-04: допущение «входит в MR»).
Контрольный критерий: три прогона VER-003 с разными seed и один прогон VER-001 — без красных.

## 3. Сценарии red→green (регрессионные тесты ДО фикса)

Обозначения: `FakeUpstream` — управляемый источник событий (fake-CLI либо fake-transport VER-005), у которого каждое событие выпускается по сигналу `threading.Event`
либо после заданной паузы; тест читает клиентский сокет построчно (`http.client` + `readline`, либо сырой `socket`) и фиксирует `time.monotonic()` прихода каждого чанка.

### 3.1. Реалтайм прихода чанков (REQ-001, REQ-020, AC-001, AC-002, AC-026)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-001 | `FakeUpstream` отдаёт 10 дельт размышления с паузой 150 мс и после десятой блокируется на `Event`, не закрывая поток | клиент получил все 10 `reasoning_content`-чанков до того, как тест освободил `Event`; интервалы между соседними чанками меньше 500 мс | да: новый транспорт отсутствует; на legacy-пути блок приходит целиком в конце (F-17) |
| QA-002 | то же для `content`: 17 text-дельт с паузой 114 мс, поток открыт | чанки `content` приходят инкрементально, сумма равна исходному тексту | да |
| QA-003 | замер накладных расходов: метка отправки дельты апстримом и метка записи в клиентский сокет | разница не больше 250 мс (AC-002), 50 дельт, p95 | да |
| QA-004 | характеризующий тест legacy: fake-CLI печатает JSON-строки `reasoning` с паузами и держит процесс | каждая строка видна клиенту без ожидания конца (текущее поведение F-05); тест страхует регресс, зелёный сразу | нет (контрольный) |
| QA-005 | порядок событий: размышление, затем текст, затем usage и `[DONE]` | порядок и `finish_reason` сохранены, `usage` присутствует (REQ-014, AC-019) | да |

### 3.2. Первая видимая реакция и контракт DSH (REQ-004, REQ-005, AC-005..AC-007)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-010 | `FakeUpstream` полностью молчит 5 с | первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса (сейчас только роль-чанк и keepalive с пустым `content` раз в 15 с, F-03, F-04) | да |
| QA-011 | формат статусной строки | строка начинается с «[мост]», не пустая после `strip()`, оканчивается `\n`; помощник `dsh_visible(text)` повторяет правило `blockIsVisible` (`text.strip() != ""`, F-37) | да |
| QA-012 | контракт превью | помощник `dsh_preview_ready(text)` возвращает истину только при наличии `\n` в завершённом абзаце (F-37); первая статусная строка проходит | да |
| QA-013 | текст модели не искажён | склейка `reasoning_content` без строк с префиксом «[мост]» побайтово равна исходному размышлению модели (AC-006, OPEN-13) | да |
| QA-014 | реплей истории | сообщение assistant с `reasoning_content`, содержащим статусные строки, не попадает в результат `_messages_to_prompt` (F-07, F-38, AC-007) | нет (контрольный: игнорирование уже есть) |
| QA-015 | пустая дельта и пробельная дельта | чанки с `reasoning_content` из пробелов не считаются «видимыми», статусная строка не подменяется ими | да |
| QA-016 | keepalive | пустой keepalive остаётся валидным парсируемым чанком (F-04), но не заменяет статусную строку | нет (контрольный) |

### 3.3. Watchdog, зависания, повторы (REQ-006..REQ-009, AC-008..AC-014)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-020 | процесс не выдаёт ни одного события | за порог first-event плюс 2 с группа убита, `exit_reason=first_event_timeout`, затем повтор или ошибка клиенту (пороги уменьшены переменными окружения до 1-2 с) | да (F-09: единственный потолок 1800 с) |
| QA-021 | события есть, токенов нет | `first_token_timeout` по порогу, повтор в пределах потолка | да |
| QA-022 | после первого токена поток замолкает | `stall_timeout` по порогу паузы, остановка и классификация | да |
| QA-023 | watchdog и потолок повторов | при подряд зависающих попытках запусков не больше 3 (`MAX_TOTAL_SPAWNS`), пауза между ними Full Jitter 0.5-2.0 с, `_RetryBudget` не уходит в минус (F-11, AC-013) | да |
| QA-024 | отдача размышления до зависания | после зависания второй попытки между попытками ровно одна статусная строка «[мост] повтор…», размышление не дедуплицируется (AC-014, OPEN-14) | да |
| QA-025 | осиротевшие процессы | fake-CLI порождает дочерний `sleep`; после watchdog, таймаута и ошибки ни один процесс группы не жив (проверка `os.killpg(pgid, 0)` и `ps`) (AC-011, F-14, F-30) | частично: убийство группы есть, а срабатывания по зависанию нет |
| QA-026 | отключение клиента | клиент закрывает сокет при полной тишине апстрима: процессы остановлены не позже 7 с, `exit_reason=client_gone` (ход 1 образца обнаруживал за 24.4 с, F-33, AC-011, AC-012) | да |
| QA-027 | `etype=error` до и после первого токена | поведение `test_step_interruption.py` сохраняется на новом транспорте: ранняя ошибка не убивает процесс, поздняя транзиентная ретраится, детерминированная (400, 401, 403, 404, 422) не ретраится | нет (контрольные, перенос на новый транспорт) |
| QA-028 | `FreeUsageLimitError` 429 | классифицируется как транзиентный отказ апстрима, не приводит к многоминутной тишине, ошибка клиенту содержит читаемое сообщение (F-23..F-25, F-32) | да |
| QA-029 | старт `startup_gate_timeout` | при ожидании замка более 5 с запуск идёт без замка (fail-open), статусная строка сообщает об ожидании (F-10, F-32) | частично |

### 3.4. Парсер инструментов на потоковых дельтах (REQ-010, REQ-011, AC-015, AC-016)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-030 | текст перед `<tool_invoke>` приходит дельтами | текст вне тега выдаётся до прихода закрывающего тега, удерживается не более `len("<tool_invoke>")-1` символов (F-06) | нет (контрольный на уровне парсера) |
| QA-031 | перебор всех границ разбиения на дельты для фикстур `test_tool_emulation.py` и `test_lenient_tool_call.py` | набор `tool_calls` и `content` идентичны подаче целым текстом | нет (контрольный) |
| QA-032 | сквозной потоковый путь нового транспорта с `emulate_tools` | те же результаты на уровне SSE-ответа | да |
| QA-033 | оба тега `<tool_call>` и `<tool_invoke>` внутри потока | вызовы распознаются, сырой тег не протекает в `content` (REQ-010) | да (на новом транспорте) |
| QA-034 | завершение шага с вызовом | процесс или сессия остановлены, `finish_reason="tool_calls"`, последующий хвост не отдаётся (F-05) | да (на новом транспорте) |
| QA-035 | все сценарии `test_step_interruption.py` (107 тестов) на фейковом потоке дельт | зелёные (AC-016) | да |
| QA-036 | встроенный инструмент `opencode` в потоке | событие приводится к `unmapped`/`native`, повтор и `finish_reason` как на legacy (REQ-012, AC-017) | да |

### 3.5. Совместимость, секреты, наблюдаемость (REQ-002, REQ-003, REQ-015, REQ-016, REQ-018)

| ID | Сценарий | Проверка |
|---|---|---|
| QA-040 | kill-switch выключает новый транспорт | все 378 существующих тестов зелёные без правок (кроме OPEN-04), `H-CPU-I3`: выключенный путь не делает лишней работы |
| QA-041 | форма публичного ответа | `/health`, `/v1/models`, чанки OpenAI SSE, `finish_reason`, `usage` совпадают с эталонными фикстурами (AC-003) |
| QA-042 | `test_google_direct.py` (52 теста) | зелёные без правок (REQ-018, F-16) |
| QA-043 | секреты | `bridge.log` и тело ответов не содержат пароля `opencode serve`, значений `apiKey`, кредов прокси (AC-020) |
| QA-044 | `O-EXIT/v1` | строка содержит `transport`, `first_event_ms`, `ttft_ms` и новые `exit_reason` на каждом выходе `do_POST` (AC-021) |
| QA-045 | ротация IP | два подряд запуска получают разные записи пула (подмена `_next_standalone_proxy`, AC-018, F-15) |
| QA-046 | параллелизм | 6 одновременных запросов проходят, 7-й ждёт слот до 15 с и получает 503 при переполнении очереди из 12 (F-13) |
| QA-047 | порядконезависимость | VER-003 с тремя seed без красных (AC-023) |

## 4. Режимы отказа и краевые случаи (вход для негативных тестов)

| Случай | Источник факта | Ожидаемое поведение |
|---|---|---|
| Дневной лимит Zen (`FreeUsageLimitError`, `provider.free-limit`) | F-23, F-24, F-25 | быстрый отказ с понятным текстом, без зависания |
| `ECONNRESET` посреди ответа | F-31, F-43 | транзиентная ошибка, повтор в пределах потолка |
| Процесс без вывода и без сети | F-30 | watchdog первого события, убийство группы |
| Узел пула ProxyRack без ответа | F-31 | повтор на следующей записи пула |
| `database is locked` при параллельном старте | комментарий к `FAIL_RETRY_LIMIT` (F-11) | транзиентный повтор до `FAIL_RETRY_LIMIT` |
| Промпт около 103 KB | F-30 | передача через stdin или тело запроса целиком, без `Argument list too long` |
| Тег `<tool_invoke>` разорван между дельтами | F-06 | удержание хвоста и корректный разбор |
| Дельта из пустой строки или пробелов | F-36 | не создаёт видимого блока, не считается токеном для watchdog первого токена |
| Закрытие клиентского сокета во время размышления | F-33 | остановка процессов не позже 7 с |
| Ответ 401 от `opencode serve` | F-21 | детерминированная ошибка без повтора, пароль не в логе |
| Порт `opencode serve` занят или сервер упал | F-20 | откат на legacy-путь (REQ-003) либо явная ошибка; зависает не более порога first-event |
| Размышление с шифрованными деталями (`reasoning_details`) | F-02 | сохраняется как в текущем `parse_opencode_event` |
| 7-й параллельный запрос | F-13 | ожидание слота до 15 с, затем 503 |
| Повтор после отданного размышления | OPEN-14 | одна статусная строка между попытками |

## 5. Тестовые данные и стенды

- Fake-CLI: существующий `FAKE_OPENCODE` (F-43), переменные `FAKE_OC_MODE`, `FAKE_OC_COUNTER` и другие, `allow_child_env` пропускает их через белый список env (THREAT-003).
- Fake-transport (VER-005): локальный HTTP-сервер, отдающий события по схеме выбранного транспорта. Для варианта `opencode serve` схема событий: `session.execution.started`,
  `session.step.started`, `session.reasoning.started`, `session.reasoning.delta`, `session.reasoning.ended`, `session.text.delta`, `session.step.ended` с `tokens`,
  `session.execution.succeeded`/`session.execution.failed` (F-19, F-22); запросы `POST /api/session`, `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`,
  `DELETE /api/session/{id}`, Basic-аутентификация `opencode:<пароль>`, без заголовка 401 (F-21).
  Для варианта прямого HTTP: OpenAI SSE `data: {...}` с `delta.reasoning_content` и `delta.content`, завершение `[DONE]`, ответ 429 с телом `FreeUsageLimitError` (F-24).
- Образцы таймингов реального апстрима для эмуляции пауз: первая дельта размышления 1811 мс, интервалы 105-304 мс, первая text-дельта 3261 мс (F-19).
- Тяжёлый промпт: синтетический текст около 103000 символов из файлов репозитория (без секретов), как `prompt_chars=103088` в образце (F-30).
- Журнал сессии DSH `session.v4.jsonl.zstd`: события `assistant/attempt` с `stream[]` и временем каждого чанка (F-39) — источник для проверки TTFT по данным DSH (`zstd -dc`, разбор ключей без выгрузки текста).
- Секретов в тестовых данных нет; пароль serve в тестах генерируется на запуск.

## 6. Живая приёмка тяжёлым путём (протокол)

Лёгкая проверка (health 200, зелёные тесты, пинг свежей сессии) необходима, но не достаточна. Сдача возможна только после пунктов H1-H6.
Предусловие: квота Zen сброшена (около 03:00 MSK 2026-10-26, F-23, OPEN-09) либо есть другой допустимый маршрут. Пока квоты нет, статус — «не сдано, жду живой ход».

| Шаг | Что делается | Критерий и фиксируемый факт |
|---|---|---|
| H0 | Снимок до: `curl --noproxy '*' http://127.0.0.1:9883/health`, `git rev-parse HEAD`, `sha256` репозиторной и развёрнутой копии `server.py` (REQ-019), `ps` без `opencode run`/`serve` кроме демона PID 43288, позиция конца `bridge.log` | зафиксированы значения; копии совпадают после деплоя |
| H1 | Замер по сокету на :9883, модель `deepseek-v4.1-flash-free`, `reasoning_effort=high`, короткий промпт (умножение 37 на 43 по шагам): метка прихода каждого чанка | первая статусная строка не позже 1.0 с; первая дельта размышления не позже 3.0 с; интервалы дельт меньше 500 мс; текст идёт инкрементально; таблица `elapsed_ms` в отчёт |
| H2 | Тот же замер на промпте около 103 KB (повтор образца `prompt_chars=103088`) | первая статусная строка не позже 1.0 с; первое событие модели не позже порога first-event либо явная ошибка; нет тишины дольше 15 с без статусной строки |
| H3 | Параллелизм: 6 одновременных запросов плюс 7-й, затем повтор серии 3 раза | все 6 стартуют, 7-й ждёт или получает 503; нет `database is locked` либо он ретраится; TTFT каждого записан; процессов-сирот после серии нет (`ps`) |
| H4 | DSH Desktop (`DeepSeek V4.1 Flash (Zen) High`): сценарий образца — многошаговая цепочка с шагами `Bash`; снимки экрана на +1 с, +5 с, +35 с | строка `⚛ Think · …` видна на +1 с; на +35 с экран не состоит из одного «Deep diving for 35s ···» (образец инцидента F-30); размышление растёт по мере прихода |
| H5 | Остановка из DSH (кнопка Stop) в середине размышления | в течение 7 с `ps` без процессов группы, строка `O-EXIT/v1` с `exit_reason=client_gone`; повторный запрос работает |
| H6 | Запрещённое действие в реальном ходе: просьба создать файл встроенным инструментом модели `/tmp/probe-<ts>.txt` | файл НЕ создан самим `opencode`, DSH получил `tool_call` (или отказ), политика `deny` подтверждена фактом на диске (REQ-012); пробный файл убран |
| H7 | Инъекция сбоя на отдельном экземпляре моста (другой порт, `OPENCODE_BIN` на скрипт, который молчит, пороги watchdog уменьшены) | `first_event_timeout` и повтор в пределах 3 запусков, процессы группы убраны; боевой экземпляр :9883 не затронут |
| H8 | Регресс цепочки с эмуляцией инструментов (`glm-5.3-flash-free`, сценарий `zen-step-interruption`) | цепочка не обрывается, `finish_reason="tool_calls"` на шагах с вызовом |
| H9 | Откат: выключение нового транспорта переменной kill-switch и перезапуск | мост возвращается к legacy-поведению, `/health` 200, живой запрос проходит (временный возврат допустим, итоговое состояние восстановить) |

Шаблон сдачи:

```
ПРОВЕРЕНО ЛЁГКИМ: <health, pytest, sha256 копий>
ПРОВЕРЕНО ТЯЖЁЛЫМ: <H1-H9: какие дёрнули + таблица elapsed_ms + пути скриншотов и выдержки bridge.log>
НЕ ПРОВЕРЕНО: <остаток>   (при непустом остатке слова «готово» и «работает» запрещены)
```

## 7. Риски приёмки

- Квота Zen: PoC и живая приёмка заблокированы до сброса лимита (F-23, F-24); результаты замеров Zone B сняты до исчерпания (F-19).
- Прямой HTTP-SSE без заголовков даёт 429 (F-24, F-25): если Architect выберет прямой транспорт, нужен отдельный спайк по заголовкам (OPEN-05).
- Нагрузочные свойства `opencode serve` при 6 параллельных процессах и БД 2.27 GB не измерены (OPEN-08): включить в H3 замер RSS и FD.
- Тесты `ReasoningRow` в репозитории проверяют только контракт данных (непустой текст, `\n`); отрисовку проверяет только живой DSH (H4).
- Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/` должна быть синхронизирована до H0 (F-34, OPEN-17).

## 8. Трассируемость сценариев

| REQ | Сценарии |
|---|---|
| REQ-001 | QA-001, QA-002, QA-003, QA-005, H1 |
| REQ-002 | QA-041 |
| REQ-003 | QA-040, H9 |
| REQ-004 | QA-010, H1, H4 |
| REQ-005 | QA-011, QA-012, QA-013, QA-014, QA-015 |
| REQ-006 | QA-020, QA-029, H2, H7 |
| REQ-007 | QA-021, QA-022 |
| REQ-008 | QA-025, QA-026, H5 |
| REQ-009 | QA-023, QA-024 |
| REQ-010 | QA-030, QA-031, QA-033 |
| REQ-011 | QA-027, QA-032, QA-034, QA-035, H8 |
| REQ-012 | QA-036, H6 |
| REQ-013 | QA-045 |
| REQ-014 | QA-005 |
| REQ-015 | QA-043 |
| REQ-016 | QA-044 |
| REQ-017 | раздел 2, QA-047 |
| REQ-018 | QA-042 |
| REQ-019 | H0 |
| REQ-020 | QA-001, QA-002 |
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

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и по исходникам, 2026-10-26):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
- Дополнительные эмпирические замеры на целевой машине (`EVD-070..EVD-072`): `python3 -m unittest discover -s tests -p "test_*.py" -v` из `cwd=bridges/opencode-zen-bridge` выполняет все 378 тестов без ошибок импорта; `OPENCODE_DB=":memory:"` нативно поддерживается в `opencode` `v2.1.2` (старт `opencode serve` 120.7 мс, RSS 156.8 MiB, `0` открытых `.db`/SQLite дескрипторов в `lsof` при сохранении чтения `~/.local/share/opencode/auth.json` для `opencode-go/*`); `basedpyright==1.40.2` из `cwd=bridges/opencode-zen-bridge` с абсолютным `extraPaths` даёт `0` ошибок импорта в тестах и `3` статические ошибки в `server.py`, а полный `ruff format --diff server.py` меняет 3216 строк неформатированного legacy-кода (включая `def _run_env` и Google-direct).
Анти-галлюцинация по факт-карте: технологии, пути, версии и поведение CLI из списка выше проверены на целевой машине; по сведениям, которых нет в факт-карте и приложенных артефактах, указывается «не могу проверить».

РЕЖИМ: architecture
Модификатор режима `architecture`: Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки. Усиленные критерии режима `architecture` (вес ×1.5 на агрегации): 5. АЛЬТЕРНАТИВЫ и 4. РИСКИ.

Инструкции судье Архитектурного Совета Тимлидов (проход `a3`, раунд дебатов `D1`):
- Если ты уже видел эту задачу, код или артефакты в другой роли или в прошлом проходе — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически.
- Проверь закрытие каждого обязательного пункта доработки `RW-001..RW-006` (а также сопутствующих `FU-001..FU-008`) из приложенного вывода `panel-rework-summarizer` (`handoff/panel-rework-brief-arch-a2.json`) в актуальном `architecture-packet.json` и механической дельте `architecture-packet.v2-to-v3.diff` (режим `verify-fixed`); если какой-либо `RW-NNN` не закрыт проверяемым изменением в пакете или доказательным обоснованием с evidence — зафиксируй находку F-блоком.
- Проверь соответствие Architecture Packet каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026`, рабочим целевым значениям отзывчивости, инвентарю контрактов as-is, положительному периметру `research-plan.md` (`bridges/opencode-zen-bridge/`, эталон `bridges/muse-bridge/server.py`, live-бинарник `opencode`, рендерер DSH Desktop) и каждому пункту разделов `Non-Goals` и `Forbidden Scope` из `handoff-architect.md`.
- Проверь, что все архитектурные решения опираются на факты `[F-NN]`, каждый факт `[F-NN]` находится в приложенном `evidence-ledger.md`, входной `evidence[]` открывает точки входа API/consumer/job, границы, данные, `pyproject.toml`/реальные версии, существующие тесты/CI-команды и успешный аналог (`bridges/muse-bridge/server.py`), а ни одно имя файла, класса или метода не включено без подтверждения кодом.
- Проверь альтернативы и ADR: в Architecture Packet должно быть рассмотрено ≥2 альтернативы с явной причиной выбора (меньше двух или без причины выбора — FAIL по критерию 5. АЛЬТЕРНАТИВЫ); выбор `ADR-lite` vs `ADR-full` соответствует триггерам (`architecture.md`), sensitivity check и PoC применены по контракту ADR-full, proposals пишутся только в `architecture/proposals/` без изменений `pyproject.toml`/lockfile/CI/migrations/product code, а каждый элемент `views[]` содержит вопрос и artifact reference.
- Проверь архитектурные границы и слои (`boundaries[]` с `allowed`/`forbidden` dependencies и `verification_ids`), потоковую семантику (аккумуляция и независимый сигнал полноты для streaming-источника), внешние контракты (HTTP/event/data/CLI/SDK, пустоту/обоснованность `contract_deltas[]`, явное указание cross-repo mirror, compatibility window и mixed-version behavior либо проверяемое неприменение, классификацию one-way решений с человеческим approval), сценарии качества (NFR, тайминги отзывчивости, конверт `HL-ENV/v1` из 46 полей и расчёты `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`), модель угроз и защиту секретов (`threats` / `security`), проверяемость `verification_surface` (независимое выполнение полного frozen набора ролью `Verifier`, не заменяемое логом `Coder`), соблюдение ограничений «Что Architect не делает» (отсутствие готовой реализации и необоснованной фиксации внутренних сигнатур, веток/коммитов, искусственной декомпозиции «≤1 день», установки зависимостей/ослабления гейтов и подмены независимого ревью self-eval), правил эскалации `BLOCKED` (без условного `approved`) и требований `aisdlc-gcge/AGENTS.md` (обязательные проверки `ruff format`, `ruff check`, `basedpyright`, `pytest` для любого изменения кода, `Identify → Assess → Communicate → Solutions`, префикс вклада `[agent]` + Conventional Commits, чтение `.agents/agents/mr.md` перед подготовкой MR, запрет `git commit --no-verify`, `SKIP=hook` и `PRE_COMMIT_ALLOW_NO_CONFIG`), а также все пункты `Definition of Done overlay` из `aisdlc-gcge/skills/architecture.md`.
- FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.
- FAIL без оговорок: (1) пакет меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK) без явного указания в постановке задачи / task envelope (`scope-and-contracts.md`); (2) работа или пакет выходит за рамки текущей задачи (чужие Jira-KEY, чужой статус, правки чужих мостов или файлов «заодно»).
- Оцени все 6 критериев `universal-panel` (1. КОРРЕКТНОСТЬ, 2. ПОЛНОТА, 3. РЕАЛИЗУЕМОСТЬ, 4. РИСКИ, 5. АЛЬТЕРНАТИВЫ, 6. СООТВЕТСТВИЕ КОНТЕКСТУ) по единому блоку формата ответа из промпта твоей роли в начале брифа.

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L95-L114 sha256=ea021debac0bcd0bc61f8e34030659060aeac0dd77323259b2205ec904c0c73d
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
   F-блоков — вердикт malformed.
7. Дефект вне дельты цикла тоже выдаётся с меткой [pre-existing] — молчание о найденном ради «дельты» запрещено.
   Приоритет по месту (§3, «Diff-scope»): в файле, изменённом задачей, — blocking; в коде вне скоупа задачи — non-blocking.
```
ARTIFACT_END>>>
Примечание для режима `arch`: в блоке «ПОЛНОТА ВЫДАЧИ» выше слово «diff» читается как «Architecture Packet», а вместо `file:line` используются допустимые якоря (а)–(г) из блока «ЯКОРЯ ПАКЕТА».

ВЕРДИКТ ТВОЕЙ РОЛИ В РАУНДЕ 1:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/arch-panel/cycle-1/a3/debate/r1/realist.md sha256=f421c85024ffca8427a1a3bf8607696b9a471278e1c8a878daf6a2df93e6a366
> PANEL-NONCE: 00d5fb3add1d4d24
> ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
> Прочитал общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`); проектные файлы правил в рабочей папке в брифе не вложены — не могу проверить.
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=RC-1 закрыт переходом на `opencode serve` SSE-дельты [F-19] вместо буферизующего `run` [F-17][F-18]; RW-002 закрыт `OPENCODE_DB=:memory:` с сохранением стандартного `auth.json` (EVD-071: 120.7 мс, 156.8 MiB, 0 открытых DB), RW-003 — шестым frozen-семейством `form.created/form.cancelled` с вложенным `data.form.sessionID`, `cancel<=0.25s`, fallback аргументов из `input.ended.data.text` и немедленным `interrupt` без Step2 (AD-001#single_turn_control, EVD-073), RW-005 — санитизацией env на всех трёх ветках `_run_env` при его побайтовой неизменности (AD-001#serve_env_sanitization, THREAT-003); fallback после барьера доставки запрещён, таблица фаза×событие×счётчики замкнута (AD-001#fallback_decision_table, FU-004).
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=Все REQ-001..REQ-020 и AC-001..AC-026 трассированы в VER-001..VER-005; REQ-004/REQ-005 согласованы с grace 0.30 с, thinking-eligibility и обязательным stall-heartbeat 15.0 с (FU-005, CD-001); шесть frozen wire-семейств v2.1.2 с дайджестом и негативными мутациями (AD-001#event_contract), 46 полей HL-ENV, 24 стоп-гейта, threat-model, H0..H9 честно помечены NOT_RUN и не выданы за PASS.
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Что нужно для взлёта задано исполнимо: только 3 файла Coder, stdlib без новых зависимостей, поставка стадийно 3a (GroupA без FakeServe) → 3b (GroupB FakeServe) (FU-008, VER-005#groups); RW-001 закрыт воспроизводимым VER-004 — isolated bridge-cwd basedpyright с временным `/tmp --project`, range-format legacy против полного format нового файла, baseline EVD-072 (3216 строк diff, 3 type errors, 564/162 warnings) с явными бюджетами и сохранением хэшей `_run_env`/Google-срезов; RW-004 — ровно один `lsof` 0.35 с на SPAWN→READY и далее 3 Keep-Alive lane с `proc.poll()` вместо `lsof` на горячем пути (EVD-074: 68.1 мс, 82.0..88.1 мс при 6 параллельных); VER-002 достижимость подтверждена EVD-070 (378 тестов, 0 import errors из bridge cwd).
> 4. РИСКИ: VERDICT=PASS
>    WHY=Главные риски закрыты гейтами, а не обещаниями: кодовый `default=false` + runtime `dynamic_config.json` только на H7 после H3/H6 (FU-007, без waiver и без правки `start.sh`), мгновенный откат false/удаление/disable-file без рестарта; RW-006 — UID-leases 0700/0600, parent-pipe helper и PID-reuse-safe startup reaper с проверкой pid/pgid/start-time/cmd/port/inode и негативами чужих PID (AD-001#crash_recovery, T-LIFE/v1); при росте нагрузки первым ломается память 6 слотов — дизайн 1×256+6×192=1408<=1638.4 MiB при idle 156.8 MiB оставляет лишь ~35 MiB/слот запаса, поэтому H3 с реальными 103 KB×6×3, суммой RSS serve+helper+lsof и 0 shared-DB обязателен и при FAIL включение запрещено; Zen-квота [F-23] и живая auth не заявлены доказанными.
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=Рассмотрено ≥2 альтернатив с причинами отказа: A2 общий демон (общий failure domain и env, недоказанная ротация egress через loopback-georouter [F-15][F-27]), B прямой HTTP Zen (429 без клиентского контекста [F-24][F-25]), L только legacy (не устраняет RC-1), пустой `XDG_DATA_HOME` (137.9 мс/203.5 MiB и потеря `auth.json` против `:memory:` EVD-071), shared DB+`_StartupGate` (мутация/локи общей DB вне scope), `--port 0`+stdout (нет подтверждённого стабильного объявления порта), две отдельные поставки 3a/3b (рассмотрена, выбрана одна ветка со стадийной верификацией) — AD-001#alternatives.
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Публичный контракт `/health`, `/v1/models`, `/v1/chat/completions`, OpenAI SSE, `finish_reason`, `usage`, порт :9883 и Google-direct неизменны (REQ-002/REQ-018); `contract_deltas` ограничены разрешённой презентацией статусов и watchdog-семантикой; scope не выходит за `bridges/opencode-zen-bridge/` (3 coder-файла), `dynamic_config.json` в git запрещён, `~/.dsh` только rollout H7; ARCH_GATE квитанция PASS на тот же `packet_sha256`, статус APPROVED честно обозначен как кандидат для Совета a3, а не ACCEPT.
> ОБЩИЙ ВЕРДИКТ: PASS
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/arch-panel/cycle-1/a3/debate/r1/skeptic.md sha256=a7117c6aba24ac8118a9ab99842d62ace3b1c826906ceaba57d2ab207cdff191
> PANEL-NONCE: e2fdf30bb07c8174
> ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
> Канон прочитан: AGENTS.md, 430 строк
>
> 1. КОРРЕКТНОСТЬ: VERDICT=FAIL
> WHY=В пакете одновременно записаны два несовместимых дерева процессов и валидация `form.created`, которая отвергает допустимую по исходной схеме форму. Оба места ломают уже заявленные RW-006 и RW-003.
> СОВЕТЫ (при FAIL):
> - Свести `AD-001.details.spawn`, `listener_ownership` и `crash_recovery.creation` к одному дереву: родительский `Popen` только stdlib-helper; helper сам запускает `opencode serve` и атомарно публикует pid/pgid/lstart в lease до READY/Auth/prompt.
> - Пересчитать потоки и FD под это же дерево.
> - В негативных мутациях `form.created` требовать `data.form.id`, вложенный `data.form.sessionID` и `fields`. `title` и `required` оставить необязательными, как в EVD-073.
> - Форма без `title` всё равно отменяется за ≤0.25 с. `invalid_serve_event` только при отсутствии id, session или fields.
>
> 2. ПОЛНОТА: VERDICT=FAIL
> WHY=Два нормативных текста статуса расходятся побайтно, а объявленная полной таблица fallback не содержит ветку protocol-caused `first_token_timeout`, которую отдельно считает `_ServeHealth`.
> СОВЕТЫ (при FAIL):
> - Оставить один шаблон ожидания первого токена. Либо убрать «(10 с)» из `status_protocol_examples.waiting`, либо вернуть тот же счётчик в `AD-002.details.lifecycle` и задать N от такта 5.0 с.
> - Добавить в `fallback_decision_table` строку: `first_token_timeout` при доказанном дефекте протокола/capability → `ServeHealth +1`, `UpstreamBreaker 0`. Текущую строку оставить только для тишины модели при валидном протоколе.
> - VER-005 сверяет одну байтовую строку статуса и обе строки таблицы.
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
> WHY=Команда VER-004 передаёт в `ruff format --range` пару `start:end`. У ruff 0.17.2 это `строка:колонка` без конца диапазона, и проверка захватывает хвост файла, включая замороженные `_run_env` и Google-срезы. Отдельно пакет требует переименовать `CATALOG_SOURCE`, а `tests/test_catalog_mode.py` вне allowlist читает старое имя.
> СОВЕТЫ (при FAIL):
> - Заменить аргумент на закрытый диапазон `--range={start}:1-{end+1}:1`. Если ruff расширяет логическую строку за hunk, гейт красный и не принимает сдвиг байтов `_run_env` (sha256 `1c51b28f…`) и `_stream_google_sse` / `_execute_google_once`.
> - Прогнать эту команду на текущем `server.py` с ранним synthetic hunk: хвост файла не должен попасть в diff форматтера.
> - Убрать требование переименовать атрибут `CATALOG_SOURCE`, либо явно добавить в allowlist только `tests/test_catalog_mode.py` и две ссылки на атрибут (строки 64 и 93). `type: ignore` и правка `pyrightconfig` не использовать. HTTP-ключ `catalog_source` не менять.
>
> 4. РИСКИ: VERDICT=FAIL
> WHY=При SIGKILL родителя дерево из `spawn` оставляет `opencode serve` без pid в lease: reaper не имеет права убивать неизвестного ребёнка. Форма без `title` уходит в `invalid_serve_event` и не отменяется, то есть вопрос снова висит до watchdog. Под ростом нагрузки внутри уже заданных 6 слотов формула CPU (`U_pod_sidecars=0.25`) не включает процессы node; design-гейт остаётся PASS, пока H3 не измерен.
> СОВЕТЫ (при FAIL):
> - Закрыть окно spawn→lease тем же helper-деревом из совета по корректности. VER-005: hard kill сразу после `Popen` и до READY не оставляет свой serve, чужие PID не трогает.
> - Отмена формы без `title` входит в oracle ≤0.25 с, без инкремента `_ServeHealth`.
> - В H3 оставить числовой стоп по RSS. Рядом записать, что насыщение CPU шестью `opencode serve` не ловится неравенством HL-ENV и до замера serve не включается.
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
> WHY=Сравнены и отвергнуты с причиной L (нет RC-1), A2 (общий failure domain и один env прокси), B (429 без PoC), пустой `XDG_DATA_HOME` (теряет `auth.json`), общая DB + `_StartupGate`, `--port 0` без доказанного объявления порта, и отдельный MR только на 3a. Выбран C/A1: короткий serve, `OPENCODE_DB=:memory:`, порт резервирует родитель. При росте выше 6 одновременных запросов bulkhead отвечает 503 и потолки не поднимаются. Внутри 6 слотов ломается незамеренный RSS/CPU serve+helper+lsof и дневная квота одного egress через georouter; это отдано в H3, а не в design-PASS.
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
> WHY=RW-001 требовал исполнимый range-гейт без выдуманного синтаксиса CLI и без переформатирования замороженных срезов. Текущая команда VER-004 этому не соответствует. Переименование `CATALOG_SOURCE` выходит за `coder_target_files` и ломает REQ-003: модуль `test_catalog_mode.py` в правках 17 модулей не разрешён. Публичный контракт `:9883` и Google-маршрут пакетом не расширяются; CD-001/CD-002 заданы REQ-004 и REQ-006.
> СОВЕТЫ (при FAIL):
> - Переписать `VER-004.command`, `expected` и `baseline_transition` под закрытый `--range` и отрицательную проверку на байты `_run_env` и Google-функций.
> - Согласовать имя `CATALOG_SOURCE` с allowlist до freeze. Пока тест вне трёх файлов читает старое имя, переименование в пакете запрещено.
> - Остальные 16 тестовых модулей, `start.sh`, `_run_env`, `pyproject`/lockfile и `~/.dsh` не расширять.
>
> F-01. priority=blocking. Якорь: architecture-packet.json#VER-004. Правило: RW-001, acceptance «воспроизводимые команды» и «без выдуманных CLI-флагов»; одновременно VER-005/`immutable_run_env`. Evidence: команда вызывает `ruff format --check --range {start}:{end}`. У ruff==0.17.2 формат такой: `<start_line>:<start_column>-<end_line>:<end_column>`; конец необязателен и тогда форматируется документ до EOF. Прогон: `--range 1:2` переписал весь файл; `--range 4:99` переписал хвост после точки старта. Ранний hunk в `server.py` поэтому требует формат замороженного тела (3216 строк diff, hash `_run_env` `1c51b28f…` → другой). Ожидание: закрытый диапазон и отказ гейта, если diff форматтера задевает `_run_env` или Google-функции. Проверка: synthetic early hunk на текущем `server.py` не помечает эти срезы unformatted.
>
> F-02. priority=blocking. Якорь: architecture-packet.json#AD-001 (`details.typing`), дубль в VER-004. Правило: REQ-003/AC-004, `coder_target_files`, FU-002 (17 модулей не править). Evidence: пакет требует «Rename mutable internal CATALOG_SOURCE to lower-case». Вне allowlist `tests/test_catalog_mode.py:64` делает `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 печатает `server.CATALOG_SOURCE`. Переименование атрибута роняет VER-001/VER-002; сохранение имени оставляет `reportConstantRedefinition`, а VER-004 требует `errorCount==0`. Ожидание: одно из двух явных решений в пакете — не переименовывать атрибут, либо добавить в allowlist только этот файл и две ссылки. Проверка: после Stage3 `test_catalog_mode` зелёный и basedpyright `errorCount==0` без `type: ignore`.
>
> F-03. priority=blocking. Якоря: architecture-packet.json#AD-001 `details.spawn`, `details.listener_ownership`, `details.crash_recovery`. Правило: T-LIFE/v1, RW-006. Evidence: spawn задаёт `Popen([OPENCODE_BIN, serve, --hostname, 127.0.0.1, --port, str(port)], stdin=DEVNULL, start_new_session=True)`. `crash_recovery.creation` задаёт другое дерево: «spawn under lease-named stdlib helper which publishes child identity atomically». Прямой `Popen` serve не публикует pid до отдельной записи lease; reaper при пустом pid убивать по имени не может. Ожидание: один текст дерева процессов и тот же учёт helper/FD. Проверка: VER-005 hard kill в щели после старта до READY даёт 0 своих serve и 0 чужих сигналов.
>
> F-04. priority=blocking. Якоря: architecture-packet.json#AD-001 `event_contract` negative_mutations формы; architecture-packet.json#EVD-073. Правило: RW-003, REQ-012, THREAT-002. Evidence: мутация «missing form.id/fields/title -> invalid_serve_event». EVD-073: у Form.Info `title` необязателен, session id лежит в `data.form.sessionID`. Форма без title становится protocol failure и не идёт в cancel ≤0.25 с, то есть вопрос снова ждёт watchdog. Ожидание: обязательны id, вложенный sessionID и fields; отсутствие title не мешает cancel и не увеличивает `_ServeHealth`. Проверка: FakeServe шлёт `form.created` без title, cancel уходит ≤0.25 с, Step2 в сокет не попадает.
>
> F-05. priority=non-blocking. Якоря: architecture-packet.json#AD-002 `status_protocol_examples.waiting` и `details.lifecycle`. Правило: FU-005, REQ-004/AC-005. Evidence: шаблон `"[мост] Ожидание первого токена (10 с)…\n"`, lifecycle — `"[мост] Ожидание первого токена…"` каждые 5.0 с, без счётчика. Ожидание: одна байтовая строка в шаблоне, lifecycle и VER-005. Проверка: тест падает при второй строке.
>
> F-06. priority=non-blocking. Якоря: architecture-packet.json#AD-001 `fallback_decision_table` и `transport_health.counted_failures`. Правило: FU-004, RISK-012. Evidence: таблица объявлена авторитетной и для `first_token_timeout` содержит только «valid protocol and model silence» → ServeHealth 0, UpstreamBreaker 1. `counted_failures` отдельно считает `first_token_timeout` счётчиком `_ServeHealth`, если доказан дефект протокола. Строки на этот случай в таблице нет. Ожидание: отдельная строка таблицы с ServeHealth +1 и UpstreamBreaker 0. Проверка: VER-005 параметризует обе причины и видит ровно один инкремент нужного счётчика.
>
> F-07. [sweep] priority=non-blocking. Якорь: architecture-packet.json#AD-003 `details.cleanup`. Правило: привязка утверждения к факту ledger. Evidence: cleanup ссылается на EVD-056 для убийства потомков после выхода leader. EVD-056 — это `WORKTREE_UNCHANGED`. Факт про `_stop_proc` и потомков — EVD-055. Ожидание: заменить ссылку на EVD-055, норматив killpg не менять. Проверка: в пакете нет утверждения, которое опирается на EVD-056 как на поведение процессов.
>
> F-08. [sweep] priority=non-blocking. Якоря: architecture-packet.json#AD-001 `listener_ownership`; `resilience_gates` C-MULT-I5 oracle. Правило: RW-004 (один lsof на горячем пути) против явного reconnect. Evidence: горячий путь permission/form/interrupt/DELETE — ровно один lsof на spawn. Тот же пакет разрешает один повторный proof ≤0.35 с при обрыве control. Оракул «exactly one lsof per successful spawn including permission/form/interrupt/DELETE» не отделяет этот recovery. Ожидание: счётчик 1 обязателен для reply/interrupt/DELETE; второй lsof допустим только в явном reconnect и не входит в бюджеты 0.25 с и 0.20 с. Проверка: spy VER-005 различает эти два сценария.
>
> SUB Корректность/логика: FAIL — architecture-packet.json#AD-001 spawn против crash_recovery
> SUB Корректность/граничные условия: FAIL — architecture-packet.json#EVD-073 title необязателен, мутация требует title
> SUB Корректность/обработка ошибок: FAIL — форма без title уходит в invalid_serve_event и не отменяется
> SUB Полнота/покрытие AC: FAIL — два байтовых шаблона ожидания токена, FU-005
> SUB Полнота/пропущенные ветки: FAIL — нет строки таблицы для protocol-caused first_token_timeout
> SUB Риски/безопасность: PASS — allowlist на трёх ветках, пароль после фильтра, ask_reject, 401/403 fail-closed
> SUB Риски/данные: PASS — OPENCODE_DB=:memory:, общая DB не открывается, auth остаётся в стандартном XDG_DATA_HOME
> SUB Риски/прод: FAIL — щель lease при SIGKILL и зависание question без title
> SUB Реализуемость: FAIL — VER-004 `--range start:end` и переименование CATALOG_SOURCE вне allowlist
> SUB Альтернативы: PASS — L, A2, B, пустой XDG, общая DB, --port 0 и отдельный MR 3a сравнены с причиной
> SUB Соответствие контексту: FAIL — RW-001 и REQ-003/coder_target_files не выполнены текстом пакета
>
> ОБЩИЙ ВЕРДИКТ: NEEDS WORK
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/arch-panel/cycle-1/a3/debate/r1/visionary.md sha256=64aa5ed18f5e6fc3571cee5156794b7f0b6a8b086a1e408c83419b7ab1a27061
> PANEL-NONCE: 87cbddecea408e18
> ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
>
> 1. КОРРЕКТНОСТЬ: VERDICT=PASS
>    WHY=RW-001..RW-006 закрыты проверяемыми изменениями. В пакете v3 они закрыты так:
>    - **RW-001 (VER-004):** команда считает формат по диапазонам изменений, принимает только один унаследованный E402, запускает basedpyright с изолированным import-root в `/tmp`. Хэш `_run_env` и срезы Google-direct заморожены.
>    - **RW-002:** выбран `OPENCODE_DB=:memory:` и сохранён стандартный `XDG_DATA_HOME`. Замер EVD-071: 120.7 мс, 156.8 MiB, 0 открытых БД, `auth.json` читается. Вариант с пустым XDG отвергнут, потому что теряет auth для `opencode-go/*`.
>    - **RW-003:** закрыт `single_turn_control`. `form.created.data.form.sessionID` обработан вложенным путём, cancel ≤0.25 с, затем немедленный interrupt и барьер Step2. Запасной путь для аргументов — `input.ended.text`. Добавлено шестое семейство фикстур, хэш пересчитан.
>    - **RW-004:** один `lsof` на spawn, затем 3 Keep-Alive канала и `proc.poll()`. Переподключение вынесено в отдельный бюджет 0.35 с.
>    - **RW-005:** allowlist среды применён ко всем трём веткам `_run_env`, который остаётся побайтово неизменным.
>    - **RW-006:** добавлены lease-реестр, parent-pipe helper и startup-reaper с проверкой uid/pid/pgid/lstart/inode.
>    
>    Контракты не меняются. `contract_deltas` содержит только CD-001 и CD-002, и оба разрешены заданием. Факты `[F-NN]` соответствуют ledger. Мелкие неточности — в F-001.
>    СОВЕТЫ (при FAIL): —
>
> 2. ПОЛНОТА: VERDICT=PASS
>    WHY=Все REQ-001..020 и AC-001..026 имеют VER, 6 семейств wire-фикстур дополнены негативными мутациями. Есть таблица «фаза × событие → действие × счётчик» (`fallback_decision_table`), 46 полей HL-ENV, 24 стоп-кода гейтов, `threat_model`, rollout H0..H9 и откат. Все 8 FU разобраны. Дельта v2→v3 не затрагивает Non-Goals и Forbidden Scope: `dynamic_config.json` явно запрещён к коммиту, мосты кроме эталона не тронуты. Нет только ADR-0005, он честно вынесен в `deferred`.
>    СОВЕТЫ (при FAIL): —
>
> 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
>    WHY=Всё реализуется на stdlib внутри трёх разрешённых файлов, зависимостей нет. Это уже подтверждено замерами: 378 тестов запускаются из cwd моста без ошибок импорта, `OPENCODE_DB=:memory:` работает на реальном бинарнике. Staged-поставка 3a→3b с независимыми группами тестов A и B позволяет локализовать сбои. Сложность высокая: serve-транспорт, helper, reaper и health в одном `server.py`. Она управляется явными бюджетами (51.6 с ≤ 54 с, 55 потоков, 108 FD ≤ 128), но остаётся самым дорогим местом реализации (F-001, F-003).
>    СОВЕТЫ (при FAIL): —
>
> 4. РИСКИ: VERDICT=PASS
>    WHY=Основные риски закрыты проектно:
>    - Безопасность: `ask_reject` без allow, fail-closed, нулевая утечка чужому listener, санитизация среды.
>    - Сироты после SIGKILL: reaper с защитой от переиспользования PID.
>    - Дубли промпта: барьер доставки и запрет тихого повтора после него.
>    - Деградация протокола: `_ServeHealth` отделён от model-breaker.
>    - Повторы: общий потолок 3 spawn сохранён.
>    
>    Всё runtime-неподтверждённое (H0..H9, RSS под нагрузкой, валидная provider-auth, квота Zen по F-23) честно помечено NOT_RUN и блокирует включение. Остаточные риски — F-002 и F-003.
>    СОВЕТЫ (при FAIL): —
>
> 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
>    WHY=В `decisions[].alternatives` рассмотрено больше двух вариантов с причинами отказа:
>    - A2 (общий daemon);
>    - B (прямой HTTP, отвергнут из-за 429 по F-24/F-25);
>    - L (только упрочнение legacy, не закрывает RC-1);
>    - shared DB с `_StartupGate`;
>    - `--port 0`;
>    - раздельные MR 3a/3b.
>    
>    Стратегически выбор верный. Гибрид C/A1 даёт реалтайм там, где транспорт доступен, сохраняет откат на `run`, как в muse-bridge (F-40), и не привязывает мост к недоказанному прямому маршруту. Задел на рост есть: проекционный хэш схемы пережидает обновления бинарника, а лимит параллелизма и пулы не меняются.
>    СОВЕТЫ (при FAIL): —
>
> 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
>    WHY=Пакет соответствует `architecture.md` overlay и `scope-and-contracts.md`. Публичный контракт `:9883`, Google-маршрут и `run`-путь неизменны. ADR-0005 корректно оформлен как отдельная задача без изменений `pyproject.toml` и lockfile. Фичефлаг (код `false`, runtime JSON включается на H7 после H3/H6) заявлен как соответствие канону без исключений. Это утверждение автора пакета, см. F-002.
>    Сверка SEED: `SHA-256(seed_input)` = `3c47808c39c110803deb7aab9bf9d9741531b6d33775152577f8f1ccb9a8ae6b`, совпадает с манифестом. `ranked_order` по `rank(slot)=SHA-256(SEED#slot)` пересчитан: gemini-4-argon-high, claude-sonnet-5-5-high, grok-4.7-high, gpt-6.1-sol-high, muse-wonder-full-1.0. Он совпадает с `panel/arch/r4/manifest.json`.
>    СОВЕТЫ (при FAIL): —
>
> F-БЛОКИ (все non-blocking)
>
> - **F-001** (non-blocking, 3. РЕАЛИЗУЕМОСТЬ)
>   - **Anchor:** architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`).
>   - **Дефект:** `spawn` описывает прямой `Popen([OPENCODE_BIN,serve,...], start_new_session=True)` и сохранение `child_pgid`. `crash_recovery.creation` говорит, что serve запускается под helper, который публикует идентичность ребёнка. Не зафиксировано, чьи `proc`/PGID использует `proc.poll()`, `os.getpgid(listener)==child_pgid` и `killpg`: serve или helper.
>   - **Исправление:** одной фразой задать топологию (helper-родитель или прямой serve плюс отдельный watchdog) и привязать `proc.poll()` и сравнение PGID к конкретному процессу.
>   - **Проверка:** оракул VER-005 GroupB явно проверяет PGID listener = PGID записанного serve при обеих ветках запуска.
> - **F-002** (non-blocking, 6. СООТВЕТСТВИЕ КОНТЕКСТУ)
>   - **Anchor:** architecture-packet.json#ASM-003, #Q-003, #AD-001 (`feature_flag_context`).
>   - **Дефект:** эквивалентность локального `dynamic_config.json` фичефлагу GigaRC канона объявлена автором пакета. Подтверждения владельца нет, статус ASM-003 — ASSUMED. Развёрнутый JSON лежит рядом с `server.py` в `~/.dsh`, и синхронизация каталога с удалением может его стереть.
>   - **Исправление:** оставить решение внешнему Совету a3 и владельцу. В H4/H5 зафиксировать, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json` и `disable-serve`.
>   - **Проверка:** H0 после sync читает файл обратно.
> - **F-003** (non-blocking, 4. РИСКИ)
>   - **Anchor:** architecture-packet.json#high_load_envelope (`operational_profile.p99_criteria`, `memory_closure_check`), #EVD-071.
>   - **Дефект:** запас памяти на слот в простое всего ~35 MiB (192 − 156.8) на serve плюс helper плюс lsof. Деградированный профиль 231.6 с превышает SLA 180 с. Оба признаны оценками.
>   - **Исправление:** H3 обязан фиксировать фактический суммарный RSS и p99 по выборке ≥100 в нормальном и деградированном профиле. При превышении serve остаётся выключенным, лимиты не повышаются. Это уже заложено, пункт нужно держать без смягчения.
>   - **Проверка:** H3 сравнивает суммарный RSS с 1638.4 MiB, а p99 — с 180 с и 231.6 с.
>
> ОБЩИЙ ВЕРДИКТ: PASS
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/arch-panel/cycle-1/a3/consensus-ledger.md sha256=441d69a7df441d01597e58df0ede6914845b3968345faeacb1b5ec4cb41c44d7
# Черновой консенсус-леджер находок Архитектурного Совета — Cycle 1 (`a3`, после `R1` `panel/arch/r4`)

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Раунд R1:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r4` (`panel-proof.json` `sha256=abddbe7d2b8b60086143ec49356c231f21f0d03ec05c51c06b7aaa3b0da6e9f9`, `verify_panel_proof exit=0`)
- **Проверяемый артефакт (v3):** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`sha256=8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608`)
- **Всего открытых находок после R1:** 11 (`F-001`..`F-008` от `skeptic`, `0` от `realist`, `F-009`..`F-011` от `visionary`)

---

## Находки Seat 1 (`skeptic`, `grok-4.7-high`, `xAI`, `cursor-agent`)

### F-001
- origin: skeptic · R1 · skeptic-F-01
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-01. priority=blocking. Якорь: architecture-packet.json#VER-004. Правило: RW-001, acceptance «воспроизводимые команды» и «без выдуманных CLI-флагов»; одновременно VER-005/`immutable_run_env`. Evidence: команда вызывает `ruff format --check --range {start}:{end}`. У ruff==0.17.2 формат такой: `<start_line>:<start_column>-<end_line>:<end_column>`; конец необязателен и тогда форматируется документ до EOF. Прогон: `--range 1:2` переписал весь файл; `--range 4:99` переписал хвост после точки старта. Ранний hunk в `server.py` поэтому требует формат замороженного тела (3216 строк diff, hash `_run_env` `1c51b28f…` → другой). Ожидание: закрытый диапазон и отказ гейта, если diff форматтера задевает `_run_env` или Google-функции. Проверка: synthetic early hunk на текущем `server.py` не помечает эти срезы unformatted.

### F-002
- origin: skeptic · R1 · skeptic-F-02
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-02. priority=blocking. Якорь: architecture-packet.json#AD-001 (`details.typing`), дубль в VER-004. Правило: REQ-003/AC-004, `coder_target_files`, FU-002 (17 модулей не править). Evidence: пакет требует «Rename mutable internal CATALOG_SOURCE to lower-case». Вне allowlist `tests/test_catalog_mode.py:64` делает `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 печатает `server.CATALOG_SOURCE`. Переименование атрибута роняет VER-001/VER-002; сохранение имени оставляет `reportConstantRedefinition`, а VER-004 требует `errorCount==0`. Ожидание: одно из двух явных решений в пакете — не переименовывать атрибут, либо добавить в allowlist только этот файл и две ссылки. Проверка: после Stage3 `test_catalog_mode` зелёный и basedpyright `errorCount==0` без `type: ignore`.

### F-003
- origin: skeptic · R1 · skeptic-F-03
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-03. priority=blocking. Якоря: architecture-packet.json#AD-001 `details.spawn`, `details.listener_ownership`, `details.crash_recovery`. Правило: T-LIFE/v1, RW-006. Evidence: spawn задаёт `Popen([OPENCODE_BIN, serve, --hostname, 127.0.0.1, --port, str(port)], stdin=DEVNULL, start_new_session=True)`. `crash_recovery.creation` задаёт другое дерево: «spawn under lease-named stdlib helper which publishes child identity atomically». Прямой `Popen` serve не публикует pid до отдельной записи lease; reaper при пустом pid убивать по имени не может. Ожидание: один текст дерева процессов и тот же учёт helper/FD. Проверка: VER-005 hard kill в щели после старта до READY даёт 0 своих serve и 0 чужих сигналов.

### F-004
- origin: skeptic · R1 · skeptic-F-04
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-04. priority=blocking. Якоря: architecture-packet.json#AD-001 `event_contract` negative_mutations формы; architecture-packet.json#EVD-073. Правило: RW-003, REQ-012, THREAT-002. Evidence: мутация «missing form.id/fields/title -> invalid_serve_event». EVD-073: у Form.Info `title` необязателен, session id лежит в `data.form.sessionID`. Форма без title становится protocol failure и не идёт в cancel ≤0.25 с, то есть вопрос снова ждёт watchdog. Ожидание: обязательны id, вложенный sessionID и fields; отсутствие title не мешает cancel и не увеличивает `_ServeHealth`. Проверка: FakeServe шлёт `form.created` без title, cancel уходит ≤0.25 с, Step2 в сокет не попадает.

### F-005
- origin: skeptic · R1 · skeptic-F-05
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-05. priority=non-blocking. Якоря: architecture-packet.json#AD-002 `status_protocol_examples.waiting` и `details.lifecycle`. Правило: FU-005, REQ-004/AC-005. Evidence: шаблон `"[мост] Ожидание первого токена (10 с)…\n"`, lifecycle — `"[мост] Ожидание первого токена…"` каждые 5.0 с, без счётчика. Ожидание: одна байтовая строка в шаблоне, lifecycle и VER-005. Проверка: тест падает при второй строке.

### F-006
- origin: skeptic · R1 · skeptic-F-06
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-06. priority=non-blocking. Якоря: architecture-packet.json#AD-001 `fallback_decision_table` и `transport_health.counted_failures`. Правило: FU-004, RISK-012. Evidence: таблица объявлена авторитетной и для `first_token_timeout` содержит только «valid protocol and model silence» → ServeHealth 0, UpstreamBreaker 1. `counted_failures` отдельно считает `first_token_timeout` счётчиком `_ServeHealth`, если доказан дефект протокола. Строки на этот случай в таблице нет. Ожидание: отдельная строка таблицы с ServeHealth +1 и UpstreamBreaker 0. Проверка: VER-005 параметризует обе причины и видит ровно один инкремент нужного счётчика.

### F-007
- origin: skeptic · R1 · skeptic-F-07
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-07. [sweep] priority=non-blocking. Якорь: architecture-packet.json#AD-003 `details.cleanup`. Правило: привязка утверждения к факту ledger. Evidence: cleanup ссылается на EVD-056 для убийства потомков после выхода leader. EVD-056 — это `WORKTREE_UNCHANGED`. Факт про `_stop_proc` и потомков — EVD-055. Ожидание: заменить ссылку на EVD-055, норматив killpg не менять. Проверка: в пакете нет утверждения, которое опирается на EVD-056 как на поведение процессов.

### F-008
- origin: skeptic · R1 · skeptic-F-08
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 skeptic=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> F-08. [sweep] priority=non-blocking. Якоря: architecture-packet.json#AD-001 `listener_ownership`; `resilience_gates` C-MULT-I5 oracle. Правило: RW-004 (один lsof на горячем пути) против явного reconnect. Evidence: горячий путь permission/form/interrupt/DELETE — ровно один lsof на spawn. Тот же пакет разрешает один повторный proof ≤0.35 с при обрыве control. Оракул «exactly one lsof per successful spawn including permission/form/interrupt/DELETE» не отделяет этот recovery. Ожидание: счётчик 1 обязателен для reply/interrupt/DELETE; второй lsof допустим только в явном reconnect и не входит в бюджеты 0.25 с и 0.20 с. Проверка: spy VER-005 различает эти два сценария.

---

## Находки Seat 3 (`visionary`, `claude-sonnet-5-5-high`, `Anthropic`, `claude-p`)

### F-009
- origin: visionary · R1 · visionary-F-001
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-001** (non-blocking, 3. РЕАЛИЗУЕМОСТЬ)
>   - **Anchor:** architecture-packet.json#AD-001 (`details.spawn`, `details.crash_recovery.creation`, `details.listener_ownership`).
>   - **Дефект:** `spawn` описывает прямой `Popen([OPENCODE_BIN,serve,...], start_new_session=True)` и сохранение `child_pgid`. `crash_recovery.creation` говорит, что serve запускается под helper, который публикует идентичность ребёнка. Не зафиксировано, чьи `proc`/PGID использует `proc.poll()`, `os.getpgid(listener)==child_pgid` и `killpg`: serve или helper.
>   - **Исправление:** одной фразой задать топологию (helper-родитель или прямой serve плюс отдельный watchdog) и привязать `proc.poll()` и сравнение PGID к конкретному процессу.
>   - **Проверка:** оракул VER-005 GroupB явно проверяет PGID listener = PGID записанного serve при обеих ветках запуска.

### F-010
- origin: visionary · R1 · visionary-F-002
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-002** (non-blocking, 6. СООТВЕТСТВИЕ КОНТЕКСТУ)
>   - **Anchor:** architecture-packet.json#ASM-003, #Q-003, #AD-001 (`feature_flag_context`).
>   - **Дефект:** эквивалентность локального `dynamic_config.json` фичефлагу GigaRC канона объявлена автором пакета. Подтверждения владельца нет, статус ASM-003 — ASSUMED. Развёрнутый JSON лежит рядом с `server.py` в `~/.dsh`, и синхронизация каталога с удалением может его стереть.
>   - **Исправление:** оставить решение внешнему Совету a3 и владельцу. В H4/H5 зафиксировать, что синхронизация копирует только `server.py` и не трогает `dynamic_config.json` и `disable-serve`.
>   - **Проверка:** H0 после sync читает файл обратно.

### F-011
- origin: visionary · R1 · visionary-F-003
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 visionary=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> - **F-003** (non-blocking, 4. РИСКИ)
>   - **Anchor:** architecture-packet.json#high_load_envelope (`operational_profile.p99_criteria`, `memory_closure_check`), #EVD-071.
>   - **Дефект:** запас памяти на слот в простое всего ~35 MiB (192 − 156.8) на serve плюс helper плюс lsof. Деградированный профиль 231.6 с превышает SLA 180 с. Оба признаны оценками.
>   - **Исправление:** H3 обязан фиксировать фактический суммарный RSS и p99 по выборке ≥100 в нормальном и деградированном профиле. При превышении serve остаётся выключенным, лимиты не повышаются. Это уже заложено, пункт нужно держать без смягчения.
>   - **Проверка:** H3 сравнивает суммарный RSS с 1638.4 MiB, а p99 — с 180 с и 231.6 с.
ARTIFACT_END>>>
RECHECK F-001: `uvx ruff@0.17.2 format --help | grep -A 5 -- "--range"` → `The <RANGE> uses the format <start_line>:<start_column>-<end_line>:<end_column> ... The end position is optional. You can write --range=2 to format the entire document starting from the second line.`
RECHECK F-002: `sed -n '60,96p' bridges/opencode-zen-bridge/tests/test_catalog_mode.py` → строка 64 `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 `'source': server.CATALOG_SOURCE`; проверка `uvx basedpyright` на `CATALOG_SOURCE: str = "static"` + `global CATALOG_SOURCE; CATALOG_SOURCE = "live"` → `rc=1, errorCount=1` (`reportConstantRedefinition`).

РАУНД: D1 из ≤3; последний: нет; место: realist (ротация debate_roster_mode=rotated вместо R1 realist muse-wonder-full-1.0, своих находок в R1 нет)
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004, F-005, F-006, F-007, F-008, F-009, F-010, F-011; N=11
ВОПРОСЫ К ТЕБЕ: нет (A=0)

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-with-architect/references/arch-council.md#L25-L31 sha256=78e4fbebce9b7ba2db216de31e2177c350d031c4f650537a480bbced50fd1874
ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)
Везде, где правила или формат ответа говорят «file:line», допустим один из якорей:
(а) architecture-packet.json:<N> — строка N поданной копии пакета;
(б) architecture-packet.json#<ID> — ID сущности пакета (AD-, QA-, VER-, EVD-, ASM-NNN, ID границы, contract delta, угрозы, риска);
(в) <файл proposals>:<N> — строка приложенного proposal-файла (ADR и др.);
(г) [F-NN] — факт из приложенного evidence ledger.
Цитата правила репозитория, ADR или architecture.md допустима, как и в правилах ниже. Якорь вне перечня или не существующий в поданных файлах ссылкой не считается.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council-consensus.md#L96-L109 sha256=9036a86a9ba6456cc1f55c88ae7563cbfb66ad35f48c13f3085f42e0ba8b8776
ПРАВИЛА ДЕБАТОВ (номер раунда, признак «последний» и твоя шапочка хода — в строке РАУНД выше; судья и слот — по проходу, шапочка меняется по ротации Скептик → Реалист → Визионер → Скептик)
Всё выше — дословные копии, без комментариев оркестратора. Суди заново, чужой вердикт автоматически не подтверждай.
Цель — согласованное решение по КАЖДОЙ находке со status=OPEN, а не победа. В этом ходе ты надел следующую шапочку: пересмотри все открытые находки с новой позиции, сними необоснованные блокеры (с evidence) и предложи компромисс (AMEND).
1. По каждой находке из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО — ровно одна позиция (по своей неоспоренной находке — только если меняешь её); позиции по находкам вне строки не засчитываются и не ошибка:
   AGREE F-NNN rev=<r> — проверил: <file:line> — что увидел сам
   DISPUTE F-NNN — класс: invalid | duplicate_of:F-MMM | out_of_scope | foreign_key — контр-evidence: <file:line или цитата правила> — почему неверно
   AMEND F-NNN — priority=<blocking|non-blocking>; locations=<file:line,…>; fix=<…> — причина: <file:line или цитата правила>
   WITHDRAW F-NNN — только своя находка — ARG или NEW (как в п.2); проверил: <file:line>
   INCONCLUSIVE F-NNN — что нужно для проверки (не голос)
2. Первая твоя позиция по находке — не смена, ARG/NEW для неё не нужен (в том числе если ты заменил выбывшего судью по транспортной лестнице; смена шапочки по ротации сменой позиции не считается, но и не освобождает от ARG/NEW при изменении твоей прежней позиции: прежние позиции — твоя история в леджере). Смена своей прошлой позиции (включая AMEND/WITHDRAW своей находки) — только с `ARG: <место/раунд «дословная цитата коллеги»>` (довод коллеги) либо `NEW: <file:line>` (твоя новая проверка, которой не было в прошлых репликах) и с твоей собственной проверкой <file:line>. Смена без ARG/NEW — malformed. Повторить прежнюю позицию без нового довода можно.
3. Вопросы коллеге — не более 3 за раунд (в последнем раунде вопросов нет), адресно: `Q→<место>: F-NNN <file:line> — вопрос` (id вопросу присваивает оркестратор, ты его не пишешь). На вопросы из строки ВОПРОСЫ К ТЕБЕ: `A←Q-<id из строки> — ответ + <file:line>`; ответ без проверяемой ссылки не считается ответом.
4. Взаимоисключающие фиксы двух находок: `CONFLICT F-a↔F-b — почему`.
5. Новая находка — полный F-блок: blocking — с меткой [late-R2], non-blocking — без метки, в леджер; позиции по OPEN-находкам она не заменяет. Найденная в последнем раунде решается правилом потолка без обсуждения.
6. Ответ: строки позиций/вопросов/ответов, затем ФОРМАТ ОТВЕТА (6 критериев; при FAIL — ссылки на F-NNN; INCONCLUSIVE критерия — что нужно для проверки). SUB-строки и COVERAGE в D-раунде не нужны (правило шапки о них относится к R1); `FINDINGS_COMPLETE: <N>` — только если в ответе есть новые F-блоки (N — их число). Последние строки: `POSITIONS: <n>/<N>` (n — число твоих позиций по находкам из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО, N — их число из строки) и `ANSWERS: <a>/<A>` (A — число вопросов в строке ВОПРОСЫ К ТЕБЕ), при новых F-блоках — ещё `FINDINGS_COMPLETE`.
ARTIFACT_END>>>

## Параллелизм
- Все независимые чтения (diff, AC-оракулы, правила, evidence) делай одной пачкой tool-calls, не по одному; независимые команды (grep, прогон проверок) — параллельно, долгие — в фон.
- За один проход проверь ВСЕ открытые находки и критерии; не останавливайся на первой находке.
- Других судей текущего раунда не жди и не угадывай их новые позиции (изоляция контекста).

Итоговую строку общего вердикта в конце блока 6 критериев выводи строго с одним из значений `PASS`, `NEEDS WORK` или `RED FLAG` (без точки и комментариев в той же строке), а в конце ответа приведи обязательные строки `POSITIONS:` (всего требуется позиций: 11) и `ANSWERS: 0/0` по п.6 блока «ПРАВИЛА ДЕБАТОВ».

---
PRIOR-LEDGER-SHA256: 441d69a7df441d01597e58df0ede6914845b3968345faeacb1b5ec4cb41c44d7
PANEL-NONCE: 775f3d038c5fe7ff
ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 775f3d038c5fe7ff» и «ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608».
