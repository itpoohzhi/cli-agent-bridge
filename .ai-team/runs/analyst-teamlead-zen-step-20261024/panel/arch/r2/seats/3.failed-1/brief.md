# Бриф судьи Архитектурного Совета (arch-panel, Раунд 2, Seat 3: Визионер (Architecture Integrity / Contracts / Evolution & Observability))

- **Run ID:** `analyst-teamlead-zen-step-20261024`
- **Раунд:** `arch-panel` / `r2` (повторное рассмотрение после закрытия всех замечаний Раунда 1 `F1..F7` Seat 1 и `F1..F2` Seat 3 в пакете v5)
- **Роль судьи:** `visionary` — Визионер (Architecture Integrity / Contracts / Evolution & Observability)
- **Слот / модель:** `gpt-6.1-sol-high` (`OpenAI`, транспорт `codex`)
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json` (`sha256=1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565`)

PRIOR-LEDGER-SHA256: 274bc0f3b34e9d876af3b918495e249c4a37460c5121d763d9e62c4513a68b8b

## 1. Задача и предмет проверки в Раунде 2

В Раунде 1 (`r1`) места Seat 2 (`gemini-4-argon-high`) и Seat 3 (`muse-wonder-full-1.0`) вынесли `ACCEPT`, а Seat 1 (`grok-4.7-high`) вынес `NEEDS WORK` со списком замечаний `F1..F7` (и 2 минорных замечания от Seat 3).
Архитектор (`claude-opus-5-5`, `high`) выпустил ревизию v5 (`architecture-packet.json` + `plans/architect-02.json`), которая прошла автоматический гейт `validate_architecture_packet.py --phase approved` (`exit=0`) и закрыла все замечания Раунда 1:

1. **Закрыт `F1 BLOCKER` (`HL-ENV/v1` 46 канонических полей + замыкание памяти):**
   - В `high_load_envelope.required_hl_env_fields` включены все 46 точных идентификаторов `REQUIRED_HL_ENV_FIELDS` из `aisdlc-gcge/agents/architecture.md` §3.0 (`P_steady` .. `HOTPATH_MODULES`) с единицами СИ и источниками.
   - Замыкание памяти пересчитано с учётом `MAX_CONCURRENT = 6` дочерних процессов `opencode run`: `W * Mem_rss_worker_max + Mem_shared_max = 1 * 64 MiB + 1152 MiB = 1216 MiB <= 0.80 * 2048 MiB = 1638.4 MiB` (`PASS`).
2. **Закрыт `F2 BLOCKER` (21 стоп-код `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5`, `Dependency Failure Matrix`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`, `maxsize` в `_StdoutFeed`):**
   - Все 24 неснимаемых кода проверены численно (16 `PASS`, 8 `N/A` с двойным доказательством: `git_diff_files` + `transitive_call_graph`), добавлено решение `AD-004` (`SLOT_WAIT_TIMEOUT_S = 15.0`, `STARTUP_GATE_S = 5.0` fail-open, `_SpawnRateLimiter`, `_RetryBudget`, `_UpstreamBreaker`), обеспечивающее `R-BULK-I1` (`48.0 с <= 54.0 с`) и `S-HERD-I1` (`1.0 с^-1 <= 1.0 с^-1`).
   - Очередь `_StdoutFeed` ограничена `queue.Queue(maxsize=4096)` с вызовом `_stop_proc(proc)` при `queue.Full`.
3. **Закрыты `F3..F7` и `Seat 3 F1..F2`:**
   - Единый потолок `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`) на один HTTP-запрос и единый Full-Jitter backoff (`T_base_s = 0.5`, `T_cap_s = 2.0`).
   - Отдельный kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY` и суженный признак 5 (требует явного глагола действия `_ACTION_INTENT_RE`; короткий финальный ответ с двоеточием `"Ответ: 42:"` не вызывает ретрай).
   - Фильтрация транзиентных `etype == "error"` (`_is_transient_stream_error`: `400/401/403/404/422` не ретраятся) и сохранение полного текста при несовпадении `dedup_prefix`.
   - Добавлены `CD-002`, `CD-003`, привязаны все `EVD-001..017`, `threads_per_worker = 12`, и добавлены проверки `VER-004` (`diff -u` репо vs `~/.dsh`), `VER-005` и `VER-006`.

## 2. Инструкция по формату ответа судьи

1. Первые две непустые строки ответа заполняются по системному требованию лаунчера (`PANEL-NONCE` и `ARTIFACT-SHA256`).
2. Проверьте закрытие замечаний Раунда 1 (`F1..F7`) и целостность архитектурного пакета v5 с позиции вашей роли (`visionary`).
3. В конце ответа укажите канонический блок:
   - Если блокеров не осталось: `FINDINGS: NONE` и на следующей строке `VERDICT: ACCEPT`.
   - Если остались критические блокеры: перечислите их как `F1..Fn` и на последней строке укажите `VERDICT: NEEDS WORK` (или `VERDICT: RED FLAG`).

## 3. Встроенные артефакты (D9)

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json" sha256="1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565" bytes="109328">>>
{
  "schema_version": "1.0",
  "packet_version": "v5",
  "cycle": "cycle-2 (rework after arch-panel r1 NEEDS WORK: Seat 1 F1..F7, Seat 3 F1..F2)",
  "task_id": "ZEN-STEP-INTERRUPTION-001",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "criticality": "S2",
  "profile": "python-bridge-bugfix",
  "status": "APPROVED",
  "summary": "Устранение преждевременного обрыва многошаговых агентных цепочек в opencode-zen-bridge: двойная схема тегов <tool_invoke>/<tool_call> + алиас shell; немедленный _stop_proc на mid-stream etype==error с ретраем только транзиентных ошибок (_is_transient_stream_error); детектор оборванного tool-шага с узким признаком 5 (_ACTION_INTENT_RE) и отдельным kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY; единый потолок MAX_TOTAL_SPAWNS=3 (A_max) на HTTP-запрос, Full-Jitter backoff, process-level Retry Budget, Circuit Breaker (HALF_OPEN=1) и spawn token-bucket 1.0/с; ограниченные ожидания слота (15 с, max_waiters=12) и _StartupGate (5 с, fail-open); ограниченный _StdoutFeed (maxsize=4096) + SSE keepalive 15 с; fallback dedup_prefix без потери текста. HL-ENV/v1 (46 полей) и 21 стоп-код + T-LIFE/O-EXIT/M-SEM закрыты численно. Контрактные дельты: CD-001 (внутренний prompt), CD-002 (SSE keepalive + finish_reason recovery), CD-003 (ограниченное ожидание слота и 503 circuit open).",
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "statement": "Системная инструкция эмуляции требует <tool_invoke>{\"name\":...,\"arguments\":...}</tool_invoke>; ToolCallParser (поток) и _parse_tool_call_blocks (батч) принимают оба тега <tool_invoke> и <tool_call>; в NATIVE_TOOL_ALIASES добавлен ключ \"shell\".",
      "evidence_ids": [
        "EVD-005",
        "EVD-008"
      ]
    },
    {
      "id": "REQ-002",
      "statement": "На etype==\"error\" в Run._execute_once и Handler._stream_sse — немедленный _stop_proc(proc) и вырезание строк _INTERRUPTED_RE из видимого текста. had_mid_stream_error=True выставляется ТОЛЬКО если _is_transient_stream_error(ev): statusCode отсутствует/None/0/408/429/>=500 или message (lower) содержит econnreset|etimedout|timeout|timed out|socket hang up|interrupted|overloaded|rate limit|temporarily unavailable|fetch failed|network. statusCode in (400,401,403,404,422) -> had_mid_stream_error=False, без ретрая (Fail-Closed), ошибка отдаётся клиенту.",
      "evidence_ids": [
        "EVD-001",
        "EVD-004",
        "EVD-009",
        "EVD-012"
      ]
    },
    {
      "id": "REQ-003",
      "statement": "STEP_RECOVERY_ENABLED = os.environ.get(\"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY\", \"1\").strip().lower() not in (\"0\",\"false\",\"no\",\"off\") — отдельный kill-switch, независимый от OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES. _is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool: первой инструкцией `if not STEP_RECOVERY_ENABLED: return False`; вызывается только при emulate_tools=True и отсутствии распознанных tool_calls; 5 признаков, где признак 5 требует _ACTION_INTENT_RE (явный глагол немедленного действия) и НЕ срабатывает на голом завершающем ':' — \"Ответ: 42:\" и \"Итог проверки:\" -> False.",
      "evidence_ids": [
        "EVD-003",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011"
      ]
    },
    {
      "id": "REQ-004",
      "statement": "MAX_TOTAL_SPAWNS = 3 (A_max): суммарно по первичному запуску, fail_retries и attempt (step-recovery/unmapped) в Handler._stream_sse и Handler._serve_json не более 3 запусков opencode run на HTTP-запрос под единым deadline = time.monotonic() + TIMEOUT_S. Пауза между запусками — _retry_backoff_s(retry_num, rng_fn=random.uniform) = rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num))), RETRY_BACKOFF_BASE_S=0.5, RETRY_BACKOFF_CAP_S=2.0 (заменяет FAIL_RETRY_BACKOFF_S * n). В _stream_sse при attempt > 0: current.startswith(dedup_prefix) -> подавить уже отправленный префикс; если len(current) >= len(dedup_prefix) и not current.startswith(dedup_prefix) -> dedup_prefix = \"\" и клиенту отправляется current[emitted_len:] без потери текста.",
      "evidence_ids": [
        "EVD-003",
        "EVD-006",
        "EVD-015"
      ]
    },
    {
      "id": "REQ-005",
      "statement": "Блокирующий `for raw in proc.stdout` заменяется daemon-потоком _StdoutFeed с queue.Queue(maxsize=STDOUT_QUEUE_MAX), STDOUT_QUEUE_MAX = 4096; запись put_nowait, при queue.Full — флаг overflow, лог `stdout_overflow` и _stop_proc(proc) (попытка считается неуспешной, без неограниченного роста кучи). Потребители: get(timeout=0.25) в Run._execute_once (проверка deadline), get(timeout=1.0) в Handler._stream_sse с ': keepalive\\n\\n' при простое >= KEEPALIVE_INTERVAL_S = 15.0.",
      "evidence_ids": [
        "EVD-006",
        "EVD-013",
        "EVD-015"
      ]
    },
    {
      "id": "REQ-006",
      "statement": "Эндпоинты /health, /v1/models, /v1/chat/completions, порт 127.0.0.1:9883 и схема OpenAI совместимы; изменения наблюдаемого поведения зафиксированы только как CD-002 и CD-003; после деплоя bridges/opencode-zen-bridge/server.py побайтово совпадает с ~/.dsh/bridges/opencode-zen-bridge/server.py (VER-004).",
      "evidence_ids": [
        "EVD-014",
        "EVD-016"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "ledger_ref": "F-01",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1441-1486,1952-1981,2310-2358 (parse_opencode_event)",
      "claim": "step_finish возвращает только tokens и отбрасывает part.reason; etype==error извлекает statusCode/message."
    },
    {
      "id": "EVD-002",
      "ledger_ref": "F-02",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1961-1964,2329-2332,2412-2423,2541-2561",
      "claim": "Токены step_finish суммируются только для usage и не сравниваются с длиной видимого текста."
    },
    {
      "id": "EVD-003",
      "ledger_ref": "F-03",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:233-239,1874-1882,2379-2403,2420,2509-2519,2547 (Handler._stream_sse, Handler._serve_json)",
      "claim": "Ретрай только при unmapped (NATIVE_RETRY_LIMIT=2) или падении без вывода (FAIL_RETRY_LIMIT=3); оборванный tool-шаг завершается break + finish_reason=stop."
    },
    {
      "id": "EVD-004",
      "ledger_ref": "F-04",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:1977-1981,2338-2342",
      "claim": "etype==error посреди стрима только логируется, proc не останавливается -> opencode run запускает синтетический шаг продолжения."
    },
    {
      "id": "EVD-005",
      "ledger_ref": "F-05",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:179-224,349-390,1007-1096,1223-1385 (ToolCallParser, _parse_tool_call_blocks, NATIVE_TOOL_ALIASES)",
      "claim": "Парсер понимает только <tool_call>; в NATIVE_TOOL_ALIASES нет ключа shell (OpenCode v2.1.2)."
    },
    {
      "id": "EVD-006",
      "ledger_ref": "F-06",
      "kind": "code",
      "ref": "/tmp/zen-tests-20261024/bridge/server.py:43-44,641-656,692-725,753-785,975-993,1937-1941,2013,2297-2300",
      "claim": "Мост stateless на запрос; _slots Semaphore + _StartupGate; блокирующий for raw in proc.stdout без keepalive."
    },
    {
      "id": "EVD-007",
      "ledger_ref": "F-07",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_v2/ses_e9231183effexUq1AtanwPx1eg,session_message/msg_16dcee844001sbe9M6aE7ob0qb",
      "claim": "Ход 12: reasoning содержит план вызова тулов, text=168 символов преамбулы, finish=stop, tokens output=499 reasoning=366."
    },
    {
      "id": "EVD-008",
      "ledger_ref": "F-08",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_message/msg_16e398eba001wfHVse61q8hJUN,session_message/msg_16e3a015800106BnYiGKkyJ3WI",
      "claim": "На glm-5.3-flash-free тег <tool_invoke> проходит апстрим (len=283), тег <tool_call> вырезается (content=[], output=75)."
    },
    {
      "id": "EVD-009",
      "ledger_ref": "F-09",
      "kind": "document",
      "ref": "~/.local/share/opencode/opencode.db:session_v2/ses_e92752838ffeR1RI1LOyzoqDQU,ses_e9231183effexUq1AtanwPx1eg,ses_e9263c73fffeRuhHv7uSWVYnf7",
      "claim": "tokens.output включает tokens.reasoning; non_reasoning_output 350/133 против ~46/56 токенов видимого текста; после ECONNRESET синтетическое 'I was interrupted...' с finish=stop."
    },
    {
      "id": "EVD-010",
      "ledger_ref": "F-10",
      "kind": "document",
      "ref": "~/.dsh/storages/session_projcache/sessions/session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87.json:4881,5147,5454",
      "claim": "Три подряд оборванных хода пользователя (Turn 10/11/12) с короткими преамбулами."
    },
    {
      "id": "EVD-011",
      "ledger_ref": "F-11",
      "kind": "document",
      "ref": "~/.dsh/sessions/.../session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87/session.v4.jsonl.zstd:L261-L267",
      "claim": "assistant/message без tool/call и stopReason=stop -> DSH пишет step/end и turn/end completed."
    },
    {
      "id": "EVD-012",
      "ledger_ref": "F-12",
      "kind": "document",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14721",
      "claim": "Четыре инцидента коррелируют с opencode.db и журналом DSH: два ECONNRESET rc=1 tools=0 и два rc=0 tools=0 out_chars=138/168, retries=0."
    },
    {
      "id": "EVD-013",
      "ledger_ref": "F-13",
      "kind": "document",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14726",
      "claim": "Длительность оборванных запросов 8-44 с исключает TIMEOUT_S=1800 и Handler.timeout=300."
    },
    {
      "id": "EVD-014",
      "ledger_ref": "F-14",
      "kind": "document",
      "ref": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist:5-33, ~/.dsh/bridges/opencode-zen-bridge/start.sh:6-59",
      "claim": "LaunchAgent KeepAlive, MAX_CONCURRENT=6, однопроцессный ThreadingHTTPServer на 127.0.0.1:9883."
    },
    {
      "id": "EVD-015",
      "ledger_ref": "F-15",
      "kind": "code",
      "ref": "~/.dsh/bridges/opencode-zen-bridge/server.py:45-49,276-282,973-1006,2349,2667",
      "claim": "TIMEOUT_S=1800, Handler.timeout=300, MAX_CONCURRENT=6, STARTUP_GATE_S=12, NATIVE_RETRY_LIMIT=2, FAIL_RETRY_LIMIT=3."
    },
    {
      "id": "EVD-016",
      "ledger_ref": "F-16",
      "kind": "document",
      "ref": "~/.dsh/profiles/desktop/cordis.patch.yml:28-39,179,239",
      "claim": "DSH Desktop маршрутизирует провайдера opencode-zen на http://127.0.0.1:9883/v1."
    },
    {
      "id": "EVD-017",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py@sha256:03eadced631e090a73bcada5579f60bc71ad02858c6e0a72e1f615bd5838673b строки 43-44 (TIMEOUT_S, MAX_CONCURRENT default 2), 233-239 (NATIVE_RETRY_LIMIT, FAIL_RETRY_LIMIT, FAIL_RETRY_BACKOFF_S=0.8), 435-446 (_stop_proc), 692-725 (_StartupGate: _STARTUP_LOCK.acquire() без таймаута; _slots), 2196 (_slots.acquire(timeout=TIMEOUT_S)), 2297 (for raw in proc.stdout), 2386 (time.sleep(FAIL_RETRY_BACKOFF_S * fail_retries)), 2473-2476 (Run.execute из _serve_json)",
      "claim": "Свежая сверка кода (Cycle 2): ожидание слота до TIMEOUT_S=1800 с и ожидание _STARTUP_LOCK без таймаута — R-BULK-I1 без новых ограничений не замыкается; backoff линейный без джиттера; потолка суммарных запусков нет. Функций _complete_response/_stream_response/_run_opencode в коде нет — фактические точки: Handler.do_POST -> Handler._stream_sse | Handler._serve_json -> Run.execute -> Run._execute_once."
    }
  ],
  "risk_triggers": [],
  "assumptions": [
    {
      "id": "ASM-001",
      "statement": "tokens.output в step_finish opencode включает tokens.reasoning, поэтому non_reasoning_output = max(0, output_tokens - reasoning_tokens) корректно оценивает объём невидимого (проглоченного) не-reasoning вывода (OPEN-01 класса МОЖНО ПРОДОЛЖИТЬ).",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-007",
        "EVD-009"
      ]
    },
    {
      "id": "ASM-002",
      "statement": "Апстрим opencode.ai/zen (семейство GLM) вырезает <tool_call>, но пропускает нейтральный тег <tool_invoke> без потерь.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-008",
        "EVD-005"
      ]
    },
    {
      "id": "ASM-003",
      "statement": "Профиль памяти/CPU HL-ENV/v1 (Mem_rss_worker_max=64 MiB, 192 MiB RSS на opencode run, U_pod_sidecars=0.25) — инженерная оценка из handoff-architect.md §3 и rework-brief F1, а не замер; при MAX_CONCURRENT=6 (plist, EVD-014). Замер RSS под 6 параллельными запусками — пункт not_verified/hard-path у verifier.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-014",
        "EVD-015"
      ]
    }
  ],
  "drivers": [
    "reliability: многошаговая цепочка не должна завершаться finish_reason=stop при оборванном tool-шаге (REQ-002..REQ-004)",
    "compatibility: внешний HTTP/OpenAI контракт, порт 127.0.0.1:9883 и формат SSE/JSON совместимы; дельты только CD-002/CD-003 (REQ-006)",
    "operability: A_max=3 запуска на запрос, Retry Budget, Circuit Breaker и ограниченные ожидания под единым deadline (REQ-004)",
    "reliability: долгая фаза thinking не должна рвать SSE-соединение клиента; память ограничена (REQ-005)",
    "safety: отдельный kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY без деплоя кода (REQ-003)"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; все тесты моста (существующие и новые test_step_interruption.py) зелёные, 0 failed / 0 errors.",
      "environment": "local macOS, python3 через uvx pytest, фейковый opencode CLI (tests/_fake_cli.py), без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "QA-006",
        "QA-007",
        "QA-008",
        "BND-001",
        "BND-002",
        "BND-003",
        "CD-001",
        "CD-002",
        "CD-003",
        "RISK-001",
        "RISK-002",
        "RISK-003",
        "RISK-004",
        "RISK-005",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-002",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
      "expected": "exit 0; test_step_interruption.py покрывает QA-POS-01..03, QA-NEG-01..02, QA-BND-01..02, QA-FAIL-01..02 (handoff-qa.md) и класс HlResilienceOracles (VER-006); Ran N>=20 tests, OK.",
      "environment": "local macOS, системный python3 stdlib unittest, фейковый opencode CLI, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "AD-001",
        "AD-002",
        "AD-003",
        "AD-004",
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "QA-007",
        "QA-008",
        "CD-001",
        "CD-002",
        "RISK-001",
        "RISK-002",
        "RISK-004",
        "RISK-005",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-003",
      "kind": "command",
      "command": "PYTHONPATH=/Users/aazhiry1/work/src/cli-agent-bridge uvx pytest -q -p no:cacheprovider /Users/aazhiry1/work/src/cli-agent-bridge/tests/",
      "expected": "exit 0; корневой набор tests/ зелёный, 0 failed / 0 errors — регрессий в соседних мостах нет.",
      "environment": "local macOS, uvx pytest, PYTHONPATH=корень репозитория",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-006",
        "QA-006",
        "BND-001",
        "BND-002",
        "BND-003",
        "RISK-003"
      ]
    },
    {
      "id": "VER-004",
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge && diff -u bridges/opencode-zen-bridge/server.py ~/.dsh/bridges/opencode-zen-bridge/server.py",
      "expected": "exit 0, пустой вывод (после синхронизации деплоя). Baseline Cycle 2: репо sha256=03eadced…673b, ~/.dsh sha256=d619476e…de8a5 — сейчас различаются, проверка выполняется после rollout.",
      "environment": "local macOS, после копирования server.py в ~/.dsh и перед перезапуском LaunchAgent",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-006",
        "CD-002",
        "CD-003",
        "QA-006"
      ]
    },
    {
      "id": "VER-005",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k skips_step_recovery -k dedup_prefix_mismatch -k colon_not_incomplete -k error_401_not_retried -k error_econnreset_retried -v",
      "expected": "exit 0; Ran >=5 tests, OK. Обязательные тесты: test_serve_json_without_emulate_tools_skips_step_recovery (Handler._serve_json с emulate_tools=False — _is_incomplete_tool_step не вызывается, ровно 1 запуск; это фактическая точка, которую brief называл _complete_response — такой функции в коде нет, EVD-017); test_stream_dedup_prefix_mismatch_emits_full_text (переформулированный ответ на ретрае доходит клиенту целиком); test_short_final_answer_with_colon_not_incomplete ('Ответ: 42:' и 'Итог проверки:' -> False); test_mid_stream_error_401_not_retried (1 запуск, ошибка клиенту) и test_mid_stream_error_econnreset_retried (2 запуска, _stop_proc вызван).",
      "environment": "local macOS, системный python3 stdlib unittest, фейковый opencode CLI, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "AD-002",
        "AD-003",
        "QA-003",
        "QA-007",
        "RISK-001",
        "RISK-004"
      ]
    },
    {
      "id": "VER-006",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k HlResilienceOracles -v",
      "expected": "exit 0; детерминированные оракулы (FakeClock / инъекция rng_fn / call_count, без wall-clock): backoff u∈[0.0,0.5,1.0] -> [0.0, 0.5*cap_a, 1.0*cap_a] для retry_num 1..2 (S-HERD-I2); spawn token-bucket не более 1 запуска/с на FakeClock (S-HERD-I1); MAX_TOTAL_SPAWNS=3 на всех комбинациях fail_retries/attempt (R-BULK-I2); Retry Budget N_retries <= floor(0.2*N_req + 0.05*T_w) + 6 на 100 падающих запросах (R-BULK-I2); Circuit Breaker: 5 транзиентных отказов -> OPEN, после cooldown*U(0.8,1.2) из 10 потоков ровно 1 probe (R-BULK-I3); 13-й ожидающий слота при 6 занятых и 12 ждущих -> мгновенный 503 (C-MULT-I2); слот и waiters возвращаются в 0 после 50 прерванных запросов (C-MULT-I4); _StdoutFeed queue.Full -> _stop_proc (H-CPU-I3); STEP_RECOVERY_ENABLED=False -> детектор не трогает regex (spy call_count==0) (H-CPU-I3); spy re._compile/copy.deepcopy call_count==0 на горячем пути (H-CPU-I2); при clock.now()>=deadline следующая попытка не стартует (R-BULK-I1); расчётные тесты HL-ENV-01, C-MULT-I1, C-MULT-I5, H-CPU-I5, R-BULK-I1 по константам модуля. Ran N>=14 tests, OK.",
      "environment": "local macOS, системный python3 stdlib unittest, без сети",
      "owner": "verifier",
      "requirement_ids": [
        "REQ-004",
        "REQ-005",
        "AD-003",
        "AD-004",
        "QA-005",
        "QA-008",
        "RISK-002",
        "RISK-005",
        "CD-003"
      ]
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как доставить текстовые вызовы инструментов через апстрим opencode.ai/zen, который вырезает <tool_call>, и маппить встроенный shell OpenCode v2.1.2?",
      "choice": "Двойная схема тегов: системная инструкция эмуляции требует <tool_invoke>{\"name\":...,\"arguments\":...}</tool_invoke>; ToolCallParser (поток) и _parse_tool_call_blocks (батч) принимают оба тега <tool_invoke> и <tool_call>; в NATIVE_TOOL_ALIASES добавляется ключ \"shell\" с кандидатами клиентского shell-инструмента (как у \"bash\").",
      "alternatives": [
        "Оставить только <tool_call> и полагаться на ретрай-детектор (каждый шаг GLM тратит лишнюю попытку, детекция вероятностна)",
        "Перейти полностью на <tool_invoke> без поддержки <tool_call> (ломает модели/истории, уже выдающие <tool_call>)",
        "Перейти на JSON-only вывод без XML-тегов (большой рефакторинг парсера, хрупко на смешанном тексте)"
      ],
      "drivers": [
        "reliability",
        "compatibility"
      ],
      "evidence_ids": [
        "EVD-005",
        "EVD-008",
        "EVD-016"
      ],
      "evidence_refs": [
        "EVD-005",
        "EVD-008",
        "EVD-016"
      ],
      "consequences": [
        "Шаги GLM перестают терять вызовы на уровне апстрима (EVD-008)",
        "Обратная совместимость: <tool_call> продолжает распознаваться",
        "Парсер усложняется второй парой open/close-маркеров; потоковый буфер должен удерживать префикс обоих тегов"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-POS-01 и QA-POS-02 зелёные: оба тега дают одинаковые name/arguments, shell маппится в клиентский shell-инструмент."
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как обнаружить и восстановить оборванный инструментальный шаг (mid-stream error, синтетическое продолжение, проглоченный <tool_call>, преамбула намерения) без ложных ретраев на коротких финальных ответах и детерминированных ошибках?",
      "choice": "1) На etype==\"error\" — немедленный _stop_proc(proc) (opencode run не успевает запустить синтетический шаг) и _strip_interrupted_notice; had_mid_stream_error=True только если _is_transient_stream_error(ev) (statusCode None/0/408/429/>=500 или маркеры econnreset|etimedout|timeout|timed out|socket hang up|interrupted|overloaded|rate limit|temporarily unavailable|fetch failed|network); 400/401/403/404/422 -> False, Fail-Closed без ретрая. 2) Kill-switch STEP_RECOVERY_ENABLED = os.environ.get(\"OPENCODE_ZEN_BRIDGE_STEP_RECOVERY\", \"1\").strip().lower() not in (\"0\",\"false\",\"no\",\"off\"), независимый от OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES; при False детектор возвращает False первой инструкцией (O(1)). 3) _is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) — только при emulate_tools=True и отсутствии tool_calls; признаки: (1) транзиентная ошибка; (2) _INTERRUPTED_RE в visible/reasoning; (3) swallowed tokens: non_reasoning_output = max(0, output_tokens - reasoning_tokens) при reasoning_tokens>0 and output_tokens>=reasoning_tokens, иначе output_tokens; срабатывает при len(stripped)<=600 и non_reasoning_output - max(1, len(stripped)//3) >= SWALLOWED_TOKENS_MIN (35); (4) имена tool_names + _REASONING_TOOL_PLAN_RE в reasoning при видимом <=600; (5) УЗКАЯ преамбула: <=420 символов, <=6 строк, без таблицы/кода/_FINAL_CONCLUSION_RE, ОБЯЗАТЕЛЬНО совпадение _ACTION_INTENT_RE (явный глагол немедленного действия: 'Читаю…', 'Собираю факты…', 'Теперь посмотрим…', 'Let's check…', 'I'll run…') И (окончание на ':'/'...'/'…' ИЛИ длина <=220). Голое ':' без _ACTION_INTENT_RE и без признаков 3/4 -> False ('Ответ: 42:' -> False). 4) При срабатывании — дозапрос _incomplete_tool_step_prompt(tool_names, partial_text) в _stream_sse и _serve_json в рамках MAX_TOTAL_SPAWNS=3 и Retry Budget (AD-004). При успешном дозапросе с tool_calls клиент получает finish_reason=\"tool_calls\" вместо прежнего ошибочного \"stop\" (CD-002).",
      "alternatives": [
        "Только останавливать proc на error без детектора (не покрывает проглоченный <tool_call> и преамбулы Turn 10/12)",
        "Детектор без вычитания reasoning_tokens (ложные дозапросы на коротких финальных ответах с большим reasoning, QA-NEG-01)",
        "Возвращать клиенту finish_reason=length/ошибку вместо дозапроса (DSH всё равно завершает ход или показывает ошибку)",
        "Неограниченный ретрай до появления tool_calls (UNBOUNDED_RETRY / RETRY_STORM)",
        "Признак 5 по голому завершающему ':' без глагола намерения (ложные дозапросы на коротких финальных ответах — отклонено Seat 1 F4)",
        "Ретраить любой etype==error включая 401/403 (бесполезные запуски и задержка при детерминированных ошибках — отклонено Seat 1 F5)"
      ],
      "drivers": [
        "reliability",
        "operability",
        "compatibility"
      ],
      "evidence_ids": [
        "EVD-001",
        "EVD-002",
        "EVD-003",
        "EVD-004",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-012"
      ],
      "evidence_refs": [
        "EVD-001",
        "EVD-002",
        "EVD-003",
        "EVD-004",
        "EVD-007",
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-012"
      ],
      "consequences": [
        "Реальные сбои детектируются: 350-46=304>=35 (Turn 10), 133-56=77>=35 (Turn 12), маркер interrupted + ECONNRESET (Turn 11)",
        "Короткий финальный ответ с output=400 reasoning=385 даёт 15<35 -> без дозапроса; 'Ответ: 42:' -> без дозапроса",
        "401/403/400/404/422 не ретраятся: 1 запуск, ошибка клиенту без задержки",
        "Откат детектора без деплоя: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 в EnvironmentVariables plist + перезапуск LaunchAgent; unmapped-ретрай не затрагивается"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k skips_step_recovery -k dedup_prefix_mismatch -k colon_not_incomplete -k error_401_not_retried -k error_econnreset_retried -v",
        "expected": "VER-005 зелёный; плюс QA-POS-03, QA-NEG-01/02, QA-BND-01/02, QA-FAIL-01 в VER-002."
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как устроить цикл исполнения попыток: ограниченное чтение stdout, keepalive, дедлайн, единый потолок запусков, backoff и дедупликация SSE-префикса без потери текста?",
      "choice": "1) _StdoutFeed: daemon-поток читает proc.stdout в queue.Queue(maxsize=STDOUT_QUEUE_MAX), STDOUT_QUEUE_MAX=4096, put_nowait; при queue.Full — overflow=True, лог `stdout_overflow`, _stop_proc(proc) — попытка неуспешна (данные не дропаются молча); по EOF кладёт sentinel. Потребители: get(timeout=0.25) в Run._execute_once, get(timeout=1.0) в Handler._stream_sse; ': keepalive\\n\\n' при простое >= KEEPALIVE_INTERVAL_S=15.0. Один _StdoutFeed на живой proc; старый proc останавливается _stop_proc до следующего запуска (T-LIFE/v1). 2) MAX_TOTAL_SPAWNS=3 (A_max): единый счётчик total_spawns на HTTP-запрос в Handler._stream_sse и Handler._serve_json (через Run) суммирует первичный запуск, fail_retries и attempt; запуск №4 невозможен ни при какой комбинации классов ретрая; существующие NATIVE_RETRY_LIMIT/FAIL_RETRY_LIMIT остаются верхними границами внутри потолка. 3) _retry_backoff_s(retry_num, rng_fn=random.uniform) = rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num))), BASE=0.5, CAP=2.0: retry 1 -> U(0,1.0), retry 2 -> U(0,2.0); заменяет FAIL_RETRY_BACKOFF_S*n; сон не превышает deadline - monotonic(). 4) dedup_prefix в _stream_sse при attempt>0: если current.startswith(dedup_prefix) — emitted_len=len(dedup_prefix), подавить префикс; если len(current) >= len(dedup_prefix) и not current.startswith(dedup_prefix) — dedup_prefix=\"\" и клиенту уходит current[emitted_len:] (emitted_len — длина реально отправленного в этой попытке), текст не теряется (возможен видимый повтор формулировки — допустимо, потеря — нет). 5) _StartupGate: ранний release по первому полезному событию step_start/text/reasoning/tool_use или выходу процесса (типично ~1.5–2.0 с), STARTUP_GATE_S=12.0 — только аварийный потолок удержания; latency_p95_ms=90000, SLA_p99_s=180.0.",
      "alternatives": [
        "selectors/select на pipe-дескрипторе (непереносимо с текстовым буфером Popen, сложнее)",
        "Переписать мост на asyncio (несоразмерный рефакторинг ThreadingHTTPServer)",
        "Неограниченная queue.Queue() (UNBOUNDED_QUEUE, рост кучи — отклонено Seat 1 F2)",
        "Раздельные лимиты 2/3 без общего потолка (до 1+2+3=6 запусков на запрос — отклонено Seat 1 F3)",
        "Обрезать current до dedup_prefix при несовпадении (потеря текста — отклонено Seat 1 F5)"
      ],
      "drivers": [
        "reliability",
        "operability"
      ],
      "evidence_ids": [
        "EVD-006",
        "EVD-013",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "evidence_refs": [
        "EVD-006",
        "EVD-013",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "consequences": [
        "Клиент получает keepalive каждые 15 с во время thinking; дедлайн проверяется каждые <=0.25/1.0 с",
        "Память на поток чтения ограничена 4096 строками; переполнение = контролируемый отказ попытки",
        "Худший случай латентности — 3 запуска в одном слоте; паузы суммарно <= 1.0 + 2.0 = 3.0 с",
        "+1 daemon-поток на активный proc (<=6), threads_per_worker=12"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-FAIL-02 (keepalive/deadline), QA-POS-03 и test_stream_dedup_prefix_mismatch_emits_full_text, HlResilienceOracles: MAX_TOTAL_SPAWNS и backoff-точки — зелёные."
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как замкнуть неснимаемые гейты S-HERD-I1, R-BULK-I1..I3 и C-MULT-I2, если в текущем коде ожидание слота до 1800 с, _STARTUP_LOCK без таймаута и нет ни Retry Budget, ни Circuit Breaker (EVD-017)?",
      "choice": "1) Bulkhead слота: SLOT_WAIT_S = 15.0 (env OPENCODE_ZEN_BRIDGE_SLOT_WAIT_S) вместо TIMEOUT_S в _slots.acquire; SLOT_MAX_WAITERS = 12 (= 2 × MAX_CONCURRENT при 6) — счётчик ожидающих под lock, 13-й ожидающий получает немедленный 503 {\"error\":{\"message\":\"bridge busy\",\"type\":\"overloaded\"}} (существующий payload); счётчик уменьшается в finally. Применяется ко всем путям, разделяющим _slots (_stream_sse, _serve_json, _stream_google_sse). 2) _StartupGate.acquire: _STARTUP_LOCK.acquire(timeout=STARTUP_WAIT_S), STARTUP_WAIT_S = 5.0; при таймауте — Fail-Open (вспомогательная сериализация sqlite): запуск без удержания замка + лог `startup_gate_wait_timeout`; возможный «database is locked» классифицируется существующим _is_retryable_failure и укладывается в MAX_TOTAL_SPAWNS. 3) Spawn token-bucket _SpawnRateLimiter (capacity=1, refill SPAWN_RATE_PER_S = 1.0 токен/с = 0.50 × Limit_dep_rps[opencode_cli]), реализован резервированием (GCRA, FIFO по моменту резерва): t_start = max(now, next_free), next_free = t_start + 1/SPAWN_RATE_PER_S, wait = t_start - now; если wait > deadline - now — запуск отменяется; лимитер вызывается перед КАЖДЫМ Popen, включая fail-open; не обходится; ожидание токена <= (MAX_CONCURRENT-1)/SPAWN_RATE_PER_S = 5.0 с; инъекция clock для тестов. 4) Process-level Retry Budget _RetryBudget: capacity = B_retry_max = 6, старт = 6, +0.20 токена на каждый первичный запрос + min_reserve_retry_rps × Δt (0.05/с); каждый повторный запуск (номер 2 и 3) списывает 1 токен; нет токена -> повтор не выполняется, клиенту уходит результат последней попытки (накопленный текст с finish_reason=stop либо ошибка). 5) Circuit Breaker _UpstreamBreaker (per-process, зависимость opencode_cli): OPEN после CB_FAIL_THRESHOLD = 5 подряд транзиентных отказов попытки (транзиентная ошибка/rc!=0 без вывода/overflow), cooldown CB_RESET_S = 10.0 × U(0.8,1.2); в OPEN новые запуски не делаются (0 с, без spawn): первичный запрос -> 503 {\"error\":{\"message\":\"upstream circuit open\",\"type\":\"overloaded\"}} (SSE — через _sse_error), повтор -> отказ от повтора; HALF_OPEN — ровно 1 пробный запуск на процесс, остальные fast-fail до исхода пробы; успех -> CLOSED. Детерминированные 4xx в счётчик не входят.",
      "alternatives": [
        "Оставить ожидание слота TIMEOUT_S=1800 с (R-BULK-I1: sum T_wait = 1800 >> 54 с — неснимаемый FAIL)",
        "Fail-Closed по таймауту _StartupGate (503 при пачке из 6 одновременных стартов — регрессия параллельных сабагентов DSH)",
        "Считать S-HERD-I1 по формуле без лимитера (B=5.24 req/с > 1.0 — FAIL)",
        "Circuit Breaker только на путь ретраев (не соответствует R-BULK-I3: вызовы в OPEN должны уходить в fallback без обращения)"
      ],
      "drivers": [
        "reliability",
        "operability"
      ],
      "evidence_ids": [
        "EVD-006",
        "EVD-012",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "evidence_refs": [
        "EVD-006",
        "EVD-012",
        "EVD-014",
        "EVD-015",
        "EVD-017"
      ],
      "consequences": [
        "При 6 занятых слотах 7-й..18-й запросы ждут <= 15 с, 19-й получает 503 сразу; DSH видит тот же тип ошибки overloaded (CD-003)",
        "При 5 подряд транзиентных отказах апстрима мост ~8–12 с отвечает 503 без запусков, затем 1 probe",
        "Темп запусков opencode run <= 1.0/с при любой нагрузке; в типичном режиме (_StartupGate держит 1.5–2.0 с) лимитер не добавляет задержки",
        "Новые константы SLOT_WAIT_S, SLOT_MAX_WAITERS, STARTUP_WAIT_S, SPAWN_RATE_PER_S, B_RETRY_MAX, CB_FAIL_THRESHOLD, CB_RESET_S — env-переопределяемые, внутренние"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -k HlResilienceOracles -v",
        "expected": "VER-006 зелёный: token-bucket, Retry Budget, Breaker HALF_OPEN=1, bounded waiters, deadline-обрыв."
      }
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen (GLM)",
      "stimulus": "модель выдаёт вызов инструмента текстовым тегом",
      "environment": "emulate_tools=True, нормальная работа",
      "artifact": "_build_tool instruction + ToolCallParser/_parse_tool_call_blocks",
      "response": "вызов доходит до клиента как OpenAI tool_calls",
      "response_measure": "100% вызовов в <tool_invoke> и <tool_call> распознаются одинаково (QA-POS-01/02)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-002",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen",
      "stimulus": "блок <tool_call> проглочен, видна только короткая преамбула, step_finish output=506 reasoning=156",
      "environment": "emulate_tools=True, SSE и JSON",
      "artifact": "_is_incomplete_tool_step + цикл дозапроса",
      "response": "мост делает дозапрос и возвращает finish_reason=tool_calls без дублирования преамбулы",
      "response_measure": "суммарно <= MAX_TOTAL_SPAWNS=3 запусков на запрос; 0 дубликатов префикса и 0 потерь текста в SSE (QA-POS-03, dedup mismatch)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "модель",
      "stimulus": "короткий финальный ответ с output=400 reasoning=385 или 'Ответ: 42:' без глагола намерения",
      "environment": "emulate_tools=True",
      "artifact": "_is_incomplete_tool_step",
      "response": "детектор возвращает False, ответ отдаётся с первой попытки",
      "response_measure": "0 ложных дозапросов на QA-NEG-01/02 и 'Ответ: 42:'; граница 34->False, 35->True (QA-BND-01)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "сеть апстрима",
      "stimulus": "mid-stream etype=error (read ECONNRESET) после частичного текста",
      "environment": "SSE и JSON",
      "artifact": "Run._execute_once, Handler._stream_sse, _stop_proc, _strip_interrupted_notice",
      "response": "proc останавливается немедленно, синтетическое 'I was interrupted...' не попадает клиенту, выполняется дозапрос",
      "response_measure": "0 строк _INTERRUPTED_RE в ответе клиенту; 0 живых дочерних процессов после попытки (QA-FAIL-01)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-005",
      "quality": "operability",
      "source": "opencode run в фазе thinking",
      "stimulus": "stdout молчит дольше 15 с / дольше TIMEOUT_S",
      "environment": "SSE-стрим",
      "artifact": "_StdoutFeed + KEEPALIVE_INTERVAL_S",
      "response": "клиент получает ': keepalive', по дедлайну процесс останавливается",
      "response_measure": "интервал keepalive <= 15 с +1 с; разблокировка ожидания <= 1 с после deadline; очередь stdout <= 4096 (QA-FAIL-02)",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-006"
      ]
    },
    {
      "id": "QA-006",
      "quality": "compatibility",
      "source": "DSH Desktop и другие клиенты",
      "stimulus": "обычные запросы /health, /v1/models, /v1/chat/completions",
      "environment": "127.0.0.1:9883, после деплоя фикса",
      "artifact": "HTTP API моста",
      "response": "формат SSE/JSON OpenAI, порт и эндпоинты не изменились; дельты только CD-002/CD-003; репо == ~/.dsh",
      "response_measure": "существующие тесты моста и корневые tests/ зелёные (QA-REG-01); diff -u exit 0",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-004"
      ]
    },
    {
      "id": "QA-007",
      "quality": "reliability",
      "source": "апстрим opencode.ai/zen",
      "stimulus": "mid-stream etype=error со statusCode=401 (детерминированная) vs message 'read ECONNRESET' (транзиентная)",
      "environment": "SSE и JSON, emulate_tools=True",
      "artifact": "_is_transient_stream_error + цикл попыток",
      "response": "401 — без ретрая, ошибка клиенту; ECONNRESET — _stop_proc и повтор в рамках A_max и Retry Budget",
      "response_measure": "401: ровно 1 запуск; ECONNRESET: ровно 2 запуска, 0 живых дочерних процессов после запроса",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "QA-008",
      "quality": "operability",
      "source": "DSH Desktop (параллельные сабагенты) / деградация апстрима",
      "stimulus": "19 одновременных запросов при MAX_CONCURRENT=6; 5 подряд транзиентных отказов апстрима",
      "environment": "127.0.0.1:9883, FakeClock в тестах",
      "artifact": "_slots + SLOT_MAX_WAITERS, _UpstreamBreaker, _SpawnRateLimiter, _RetryBudget",
      "response": "6 работают, 12 ждут <= 15 с, 19-й — мгновенный 503; breaker OPEN -> 503 без spawn, затем 1 probe",
      "response_measure": "темп spawn <= 1.0/с; N_retries <= floor(0.2*N_req + 0.05*T_w) + 6; probe_calls == 1",
      "verification_ids": [
        "VER-001",
        "VER-006"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "server.py: слой парсинга (ToolCallParser, _parse_tool_call_blocks, _split_tool_calls, _native_to_tool_calls, NATIVE_TOOL_ALIASES)",
      "responsibility": "Чистое преобразование текста/нативных событий в OpenAI tool_calls; без I/O и без знания о ретраях.",
      "allowed_dependencies": [
        "stdlib json/re",
        "список tools клиента"
      ],
      "forbidden_dependencies": [
        "subprocess / proc",
        "Handler / сокет клиента",
        "глобальное состояние ретраев"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "BND-002",
      "component": "server.py: детектор и классификаторы (_is_incomplete_tool_step, _is_transient_stream_error, _strip_interrupted_notice, _incomplete_tool_step_prompt, _INTERRUPTED_RE, _REASONING_TOOL_PLAN_RE, _ACTION_INTENT_RE, _FINAL_CONCLUSION_RE, STEP_RECOVERY_ENABLED)",
      "responsibility": "Детерминированные чистые функции решения 'шаг оборван' и формирования промпта дозапроса.",
      "allowed_dependencies": [
        "stdlib re",
        "константы SWALLOWED_TOKENS_MIN и пороги длины"
      ],
      "forbidden_dependencies": [
        "subprocess / proc",
        "сеть",
        "время/рандом",
        "Handler"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "BND-003",
      "component": "server.py: исполнение и транспорт (Run._execute_once, Handler._stream_sse, Handler._serve_json, _StdoutFeed, _stop_proc, _slots + SLOT_MAX_WAITERS, _StartupGate, _SpawnRateLimiter, _RetryBudget, _UpstreamBreaker, _retry_backoff_s)",
      "responsibility": "Жизненный цикл opencode run, единый deadline, бюджет попыток, keepalive, уборка процессов; вызывает BND-001/BND-002, но не наоборот.",
      "allowed_dependencies": [
        "BND-001",
        "BND-002",
        "subprocess",
        "threading",
        "queue",
        "random (инъектируемый rng_fn)",
        "time.monotonic (инъектируемые часы в лимитерах)"
      ],
      "forbidden_dependencies": [
        "изменение внешних эндпоинтов и формата ответа OpenAI",
        "новые сторонние зависимости"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-006"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "opencode-zen-bridge (системная инструкция эмуляции тулов)",
      "consumer": "модель апстрима opencode.ai/zen через opencode run",
      "change": "Внутренний prompt-контракт мост->модель: модели предписывается тег <tool_invoke> вместо <tool_call>; мост продолжает принимать оба тега. Внешний HTTP/OpenAI контракт мост->DSH не меняется.",
      "compatibility": "backward-compatible: <tool_call> по-прежнему парсится; клиент видит те же OpenAI tool_calls и finish_reason",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "opencode-zen-bridge (Handler._stream_sse / Handler._serve_json)",
      "consumer": "DSH Desktop и другие OpenAI-совместимые клиенты 127.0.0.1:9883/v1",
      "change": "(а) В SSE-стриме при простое stdout >= 15 с мост шлёт строку-комментарий ': keepalive\\n\\n'; (б) при успешном восстановлении оборванного шага (AD-002) итоговый finish_reason ответа = \"tool_calls\" вместо прежнего ошибочного \"stop\", а tool_calls присутствуют в delta/message.",
      "compatibility": "backward-compatible: строки SSE, начинающиеся с ':', — комментарии и игнорируются клиентами (WHATWG HTML Living Standard, Server-sent events, 'If the line starts with a U+003A COLON character, ignore the line'); \"tool_calls\" — штатное значение finish_reason OpenAI Chat Completions; эндпоинты, порт и схема чанков не меняются. Mixed-version: клиенту безразлично, старый мост просто не шлёт keepalive. Явно требуется текущей задачей (handoff-architect.md REQ-005/REQ-006, rework-brief F6).",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-004"
      ]
    },
    {
      "id": "CD-003",
      "type": "behavior",
      "producer": "opencode-zen-bridge (Handler: _slots bulkhead, _UpstreamBreaker)",
      "consumer": "DSH Desktop и другие OpenAI-совместимые клиенты 127.0.0.1:9883/v1",
      "change": "Ожидание свободного слота ограничено SLOT_WAIT_S=15 с и SLOT_MAX_WAITERS=12 (было до TIMEOUT_S=1800 с без лимита ожидающих); при OPEN Circuit Breaker ответ HTTP 503 с message \"upstream circuit open\". Тип ошибки и статус прежние: 503 {\"error\":{\"type\":\"overloaded\"}}.",
      "compatibility": "backward-compatible по схеме: тот же HTTP 503 и error.type=overloaded, что уже отдаётся при таймауте слота; меняется только момент отказа (15 с вместо 1800 с) и добавляется новый message. Требуется закрытием неснимаемого R-BULK-I1/C-MULT-I2 (AD-004). Риск обработки 503 клиентом DSH — RISK-005, проверка — hard-path verifier.",
      "verification_ids": [
        "VER-001",
        "VER-004",
        "VER-006"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "dynamic",
      "question": "Как оборванный tool-шаг проходит через opencode run -> мост -> DSH и где вмешивается детектор/дозапрос?",
      "artifact_ref": "analysis/zen-step-interruption/handoff-architect.md#1-контекст-и-доказанная-корневая-причина"
    },
    {
      "id": "VIEW-002",
      "type": "component",
      "question": "Какие компоненты server.py меняются и в каком направлении зависимости?",
      "artifact_ref": "architecture/architecture-packet.json#boundaries (BND-001..BND-003) + decisions AD-003/AD-004"
    },
    {
      "id": "VIEW-003",
      "type": "deployment",
      "question": "Где и как запущен мост?",
      "artifact_ref": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): однопроцессный ThreadingHTTPServer 127.0.0.1:9883"
    },
    {
      "id": "VIEW-004",
      "type": "dynamic",
      "question": "Как выглядит цикл попыток одного HTTP-запроса с бюджетами (slot -> gate -> token -> spawn -> feed -> detector -> backoff -> retry/finish)?",
      "artifact_ref": "architecture/architecture-packet.json#resilience_gates.dependency_failure_matrix + R_BULK.R-BULK-I1"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Ложное срабатывание признака 5 (преамбула намерения) или 4 (план в reasoning) на легитимном коротком ответе -> лишние запуски opencode run и задержка ответа.",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Признак 5 требует _ACTION_INTENT_RE (голое ':' не триггерит); вычитание reasoning_tokens; пороги 420/600; исключение таблиц/кода/финальных выводов; MAX_TOTAL_SPAWNS=3 и Retry Budget; fallback на накопленный текст; kill-switch OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0; тесты QA-NEG-01/02 и VER-005.",
      "evidence_refs": [
        "EVD-007",
        "EVD-010",
        "EVD-011"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Дозапросы утраивают латентность хода (до 3 запусков) и удерживают слот _slots дольше; при шторме отказов — умножение нагрузки на апстрим.",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Единый deadline; слот берётся один раз на запрос; MAX_TOTAL_SPAWNS=3; Retry Budget (B_retry_max=6, +0.2/запрос); Circuit Breaker (5 отказов -> OPEN, HALF_OPEN=1); spawn token-bucket 1.0/с; QA-BND-02, VER-006.",
      "evidence_refs": [
        "EVD-013",
        "EVD-014",
        "EVD-015"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-006"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Апстрим начнёт вырезать и <tool_invoke> либо другие модели Zen (kimi-k2.5, qwen3.6-plus) имеют иной профиль токенов -> SWALLOWED_TOKENS_MIN=35 некалиброван.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Детектор swallowed tokens — второй рубеж поверх двойной схемы тегов; порог в константе; Q-001 — калибровка как follow-up; регрессия VER-003.",
      "evidence_refs": [
        "EVD-008",
        "EVD-009"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "dedup_prefix не совпадает с префиксом повторной попытки -> дублирование или потеря текста в SSE.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Совпадение — подавление отправленного префикса; несовпадение (len(current) >= len(dedup_prefix)) — dedup_prefix=\"\" и отправка current[emitted_len:] целиком (потеря исключена, возможен видимый повтор); тесты QA-POS-03 и test_stream_dedup_prefix_mismatch_emits_full_text (VER-005).",
      "evidence_refs": [
        "EVD-003",
        "EVD-006",
        "EVD-012",
        "EVD-016"
      ],
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Ограничение ожидания слота 15 с / max_waiters=12 и 503 'upstream circuit open' (CD-003) приводят к видимым ошибкам в DSH при пачке параллельных сабагентов, если DSH не ретраит 503 overloaded.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Тот же 503 overloaded, что уже отдаётся при таймауте слота; 18 одновременных запросов (6+12) обслуживаются без отказа; константы env-переопределяемые (OPENCODE_ZEN_BRIDGE_SLOT_WAIT_S); hard-path проверка verifier пачкой параллельных сабагентов DSH; при регрессии — поднять SLOT_WAIT_S в пределах R-BULK-I1 (<= 21 с при прочих бюджетах).",
      "evidence_refs": [
        "EVD-014",
        "EVD-017"
      ],
      "verification_ids": [
        "VER-001",
        "VER-006"
      ]
    }
  ],
  "threat_model": {
    "required": false,
    "reason": "S2 без risk_triggers: мост слушает только 127.0.0.1, auth/PII/новых внешних поверхностей не добавляется.",
    "assets": [
      "инструменты клиента DSH (исполнение shell/edit на машине владельца)",
      "история диалога (prompt) в stdin opencode run"
    ],
    "trust_boundaries": [
      "DSH Desktop -> мост 127.0.0.1:9883 (локальный HTTP)",
      "мост -> opencode run -> апстрим opencode.ai/zen (внешняя модель)"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Prompt-injection в выводе инструмента или ответе модели содержит <tool_invoke>/<tool_call> и порождает непредусмотренный tool_call; дозапрос повторно отправляет частичный текст модели.",
        "mitigation": "Парсер маппит только имена из списка tools текущего запроса клиента; исполнение и разрешения остаются на стороне DSH (permission ask/approval); встроенные тулы opencode не исполняются в мосте (permission *=ask); дозапрос ограничен MAX_TOTAL_SPAWNS=3 и Retry Budget и не расширяет набор тулов.",
        "verification_ids": [
          "VER-001",
          "VER-002"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "Внешний HTTP/OpenAI контракт совместим; дельты CD-002 (SSE-комментарий keepalive, finish_reason=tool_calls при восстановлении) и CD-003 (ограниченное ожидание слота, 503 circuit open) — backward-compatible по схеме; парсер принимает оба тега; новые константы — внутренние, env-переопределяемые.",
    "migration": "Миграций данных нет: мост stateless, opencode.db мостом не модифицируется; persisted state не меняется.",
    "rollout": "Правка bridges/opencode-zen-bridge/server.py (+ tests/test_step_interruption.py) -> VER-001..003, VER-005, VER-006 -> копирование в ~/.dsh/bridges/opencode-zen-bridge/server.py -> VER-004 (diff -u exit 0) -> перезапуск LaunchAgent com.user.dsh-opencode-zen-bridge -> живой многошаговый ход DSH на glm-5.3-flash-free и пачка параллельных сабагентов (тяжёлый путь).",
    "rollback": "Мгновенно без деплоя: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0 в EnvironmentVariables plist + перезапуск LaunchAgent (отключает только детектор/дозапрос, unmapped-ретрай сохраняется). Полный: git revert коммита фикса + повторная синхронизация ~/.dsh и перезапуск LaunchAgent; VER-004 подтверждает идентичность.",
    "feature_flag": "Канонический GigaRC-фичефлаг неприменим: локальный мост на машине владельца без gc_pytools/dynamic_config и без доступа к GigaRC; функциональный эквивалент kill-switch — env OPENCODE_ZEN_BRIDGE_STEP_RECOVERY (default \"1\", т.к. фикс — восстановление ожидаемого поведения, а не новая фича)."
  },
  "approval": {
    "status": "APPROVED",
    "decision_ids": [],
    "approved_by": "orchestrator (analyst-teamlead, routing_approval=auto, approved_by_user=true in route-manifest.json); one-way решений нет",
    "evidence_ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/route-manifest.json"
  },
  "independent_review": {
    "required": false,
    "status": "PASS",
    "reviewer": "deterministic fail-closed validate_architecture_packet.py (draft+approved); S2 — независимое review не обязательно; Архитектурный Совет (arch-panel cycle-2) — отдельный downstream-гейт",
    "evidence_ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/receipts/architect.json"
  },
  "open_questions": [
    {
      "id": "Q-001",
      "ledger_ref": "OPEN-01",
      "class": "МОЖНО ПРОДОЛЖИТЬ",
      "question": "Калибровка SWALLOWED_TOKENS_MIN=35 для других моделей Zen (kimi-k2.5, qwen3.6-plus): порог подтверждён только на glm-5.3-flash-free.",
      "blocking": false
    },
    {
      "id": "Q-002",
      "class": "ЗАКРЫТ",
      "question": "Отдельный env-флаг kill-switch детектора дозапроса — закрыт решением AD-002: OPENCODE_ZEN_BRIDGE_STEP_RECOVERY.",
      "blocking": false
    }
  ],
  "protected_paths": [],
  "materialization": [],
  "deferred": [
    "Калибровка SWALLOWED_TOKENS_MIN на kimi-k2.5 / qwen3.6-plus (Q-001)",
    "Логирование причины срабатывания детектора в bridge.log (signal=1..5) для наблюдаемости",
    "Замер фактического RSS opencode run под 6 параллельными запусками (ASM-003)"
  ],
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0 (REQUIRED_HL_ENV_FIELDS)",
    "field_count": 46,
    "units": "SI; память — в байтах (MiB = 1048576 B); время — с; CPU — cores; темпы — 1/с",
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
      "Mem_limit_per_pod": 2147483648,
      "Mem_rss_worker_max": 67108864,
      "Mem_shared_max": 1207959552,
      "RPS_peak": 0.2,
      "A_max": 3,
      "SLA_p99_s": 180.0,
      "N_entities_max": 64,
      "Limit_dep_share[d]": {
        "opencode_cli": 10
      },
      "Limit_dep_rps[d]": {
        "opencode_cli": 2.0
      },
      "W_fetchers[d]": {
        "opencode_cli": 1
      },
      "J_init_s[d]": {
        "opencode_cli": 12.0
      },
      "J_pod_s[d]": {
        "opencode_cli": 12.0
      },
      "T_poll_s[d]": {
        "opencode_cli": 15.0
      },
      "K_calls[d]": {
        "opencode_cli": 1
      },
      "T_base_s[d]": {
        "opencode_cli": 0.5
      },
      "T_cap_s[d]": {
        "opencode_cli": 2.0
      },
      "Max_stale_age_s[c]": {
        "stateless_bridge": 0.0
      },
      "Min_healthy_ratio": 1.0,
      "B_retry_max": 6,
      "min_reserve_retry_rps": 0.05,
      "FD_worker": 128,
      "ulimit_n": 4096,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 0.6,
        "shared_snat": 0.6
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 12,
        "shared_snat": 12
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16383,
        "shared_snat": 16383
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
      "P_steady": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): один процесс, KeepAlive, без k8s/HPA",
      "P_hpa_max": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): один процесс, KeepAlive, без k8s/HPA",
      "maxSurge_pct": "LaunchAgent: нет RollingUpdate, рестарт = стоп старого -> старт нового (один порт 9883)",
      "maxSurge_abs": "derived: ceil(P_hpa_max × maxSurge_pct) = ceil(1 × 0.0) = 0",
      "maxUnavailable_pct": "LaunchAgent: нет RollingUpdate",
      "maxUnavailable_abs": "derived: floor(P_steady × maxUnavailable_pct) = floor(1 × 0.0) = 0",
      "P_terminating_overlap": "bind 127.0.0.1:9883 исключает параллельную жизнь двух поколений (EVD-014)",
      "P_live": "derived: P_hpa_max + maxSurge_abs + P_terminating_overlap = 1 + 0 + 0 = 1",
      "P_avail_min": "derived: max(1, P_steady - maxUnavailable_abs) = max(1, 1 - 0) = 1",
      "W": "server.py ThreadingHTTPServer, один Python-процесс (EVD-006, EVD-014)",
      "N_proc": "derived: P_live × W = 1 × 1 = 1",
      "N_proc_steady": "derived: P_steady × W = 1",
      "N_proc_avail_min": "derived: P_avail_min × W = 1",
      "CPU_limit_per_pod": "handoff-architect.md §3 (cpu_limit_m=2000), бюджет демона на рабочей станции",
      "κ_skew": "W=1 — неравномерности между воркерами нет",
      "u_bg_worker": "handoff §3: GC/логирование/таймеры, оценка",
      "U_pod_sidecars": "handoff §3: дочерние opencode run в сетевом ожидании, оценка (ASM-003)",
      "Mem_limit_per_pod": "rework-brief F1: 2048 MiB бюджет LaunchAgent (без cgroup)",
      "Mem_rss_worker_max": "rework-brief F1: 64 MiB RSS Python-моста с _StdoutFeed maxsize=4096 (ASM-003)",
      "Mem_shared_max": "rework-brief F1: 6 × 192 MiB RSS opencode run = 1152 MiB (ASM-003)",
      "RPS_peak": "handoff §3 operational_profile.rps_peak; bridge.log (EVD-012/013)",
      "A_max": "AD-003: MAX_TOTAL_SPAWNS = 3",
      "SLA_p99_s": "handoff §3 latency_p99_ms=180000",
      "N_entities_max": "максимум tools в запросе DSH (allowed_map/canonical_map), handoff §4.3",
      "Limit_dep_share[d]": "handoff §4.1 C-MULT-I1: 10 слотов opencode CLI на хост (YAML §3 'Limit_dep_share_d: 6' — опечатка, принято 10 по расчёту C-MULT-I1)",
      "Limit_dep_rps[d]": "handoff §3 rate_limit_rps=2.0",
      "W_fetchers[d]": "один процесс моста",
      "J_init_s[d]": "server.py:720 STARTUP_GATE_S=12 (EVD-015)",
      "J_pod_s[d]": "server.py:720 STARTUP_GATE_S=12",
      "T_poll_s[d]": "KEEPALIVE_INTERVAL_S=15.0 (клиентский keepalive; поллинга зависимости нет)",
      "K_calls[d]": "1 opencode run на запуск",
      "T_base_s[d]": "AD-003 RETRY_BACKOFF_BASE_S=0.5",
      "T_cap_s[d]": "AD-003 RETRY_BACKOFF_CAP_S=2.0",
      "Max_stale_age_s[c]": "мост stateless: кэшей нет",
      "Min_healthy_ratio": "одна зависимость без пула нод: N_floor=1",
      "B_retry_max": "AD-004 _RetryBudget capacity",
      "min_reserve_retry_rps": "AD-004 _RetryBudget refill",
      "FD_worker": "оценка: 1 listen + 18 клиентских сокетов + 6×3 pipe + log + запас (см. C-MULT-I5)",
      "ulimit_n": "macOS launchd soft limit для агента (оценка; verifier: `launchctl limit maxfiles`)",
      "λ_new_conn_per_pod(s)": "handoff §3: локальные подключения DSH + исходящие opencode run",
      "C_active_in_scope(s)": "6 клиентских + 6 исходящих соединений",
      "N_pods_in_scope(s)": "один хост",
      "Port_range_size(s)": "macOS net.inet.ip.portrange 49152..65535 = 16384 (принято 16383)",
      "T_hold_s(s)": "TIME_WAIT 2×MSL, консервативно 60 с",
      "SNAT_ips_count(s)": "одна машина, без SNAT-пула",
      "HOTPATH_MODULES": "единственный модуль горячего пути моста"
    },
    "memory_closure_check": {
      "formula": "W * Mem_rss_worker_max + Mem_shared_max <= 0.80 * Mem_limit_per_pod",
      "substitution": "W * Mem_rss_worker_max + Mem_shared_max = 1 * 67108864 + 1207959552 = 1275068416 B (1216 MiB) <= 0.80 * Mem_limit_per_pod = 1717986918.4 B (1638.4 MiB) -> PASS",
      "lhs_bytes": 1275068416,
      "rhs_bytes": 1717986918.4,
      "result": "PASS"
    },
    "operational_profile": {
      "threads_per_worker": 12,
      "threads_breakdown": "6 HTTP handler threads (MAX_CONCURRENT=6 активных) + 6 daemon _StdoutFeed (1 на живой proc); ожидающие слота потоки (<= SLOT_MAX_WAITERS=12) блокированы и не исполняют код",
      "stdout_queue_max": 4096,
      "latency_p50_ms": 14000,
      "latency_p95_ms": 90000,
      "latency_p99_ms": 180000,
      "max_total_spawns": 3,
      "max_retries": 2,
      "rps_sustained": 0.05,
      "rps_peak": 0.2,
      "concurrency_max": 6,
      "payload_p50_kb": 48,
      "payload_p99_kb": 480,
      "cpu_limit_m": 2000,
      "mem_limit_mb": 2048,
      "workers_processes": 1,
      "connect_timeout_ms": 5000,
      "read_timeout_ms": 300000,
      "total_deadline_ms": 1800000,
      "backoff_base_ms": 500,
      "backoff_max_ms": 2000,
      "jitter_mode": "full_jitter",
      "slot_wait_s": 15.0,
      "slot_max_waiters": 12,
      "startup_wait_s": 5.0,
      "startup_gate_s": 12.0,
      "startup_gate_typical_release_s": "1.5-2.0",
      "spawn_rate_per_s": 1.0,
      "retry_budget_capacity": 6,
      "retry_budget_refill_per_req": 0.2,
      "circuit_breaker_threshold": 5,
      "circuit_breaker_reset_s": 10.0,
      "half_open_probes": 1,
      "keepalive_interval_sec": 15,
      "swallowed_tokens_min": 35,
      "graceful_shutdown_sec": 5,
      "max_response_size_mb": 16
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0–3.4, §7.2, §7.3",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "check": "len(required_hl_env_fields) == 46 и REQUIRED_HL_ENV_FIELDS ⊆ keys; источник у каждого поля (field_sources); memory closure 1275068416 B <= 1717986918.4 B; каждый N/A ниже — с git_diff_files + transitive_call_graph",
        "oracle": "VER-006: расчётный тест по константам модуля"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "roles: bridge_http_workers (N_proc=1, pool=_slots=MAX_CONCURRENT=6, G_reload=1 — _slots создаётся один раз при импорте, reload каталога семафор не пересоздаёт; dedicated=0); crawler/pod_fetcher/control_plane/migrations_cron = 0 процессов. C_dep(opencode_cli) = 1 × (1 × 6 + 0) = 6 <= 0.60 × 10 = 6.0 -> PASS. Повторы идут в том же слоте после _stop_proc (синхронный wait<=5 с) — одновременных детей <= 6. Расчёт при MAX_CONCURRENT=6 из plist (EVD-014); дефолт кода 2 (EVD-017) даёт 2 <= 6.0."
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Пул = _slots(M=6) с timeout T_wait_s=SLOT_WAIT_S=15.0 и max_waiters=SLOT_MAX_WAITERS=12 <= 2M=12; 13-й ожидающий -> немедленный 503 overloaded (аналог PoolWaitersExhaustedError); очередь stdout queue.Queue(maxsize=4096) (AD-003, AD-004)."
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "_slots, _STARTUP_LOCK, _SpawnRateLimiter, _RetryBudget, _UpstreamBreaker — синглтоны модуля (один процесс, fork() воркеров нет); новые объекты в обработчике не создаются, кроме per-request _StdoutFeed/_StartupGate (не сетевые клиенты). subprocess.Popen делает exec с close_fds=True (Python 3 default) — сокеты моста не наследуются."
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "asyncio нет; прерывания — исключения/BrokenPipe в потоке обработчика. _slots.release(), декремент waiters, gate.release() и _stop_proc(proc) — в try/finally в Handler._stream_sse, Handler._serve_json, Run._execute_once; оракул: после 50 прерванных запросов in_use==0, waiters==0 (VER-006)."
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "FD_worker = 128 <= 0.70 × 4096 = 2867.2 (оценка пика: 1 listen + 18 клиентских (6 активных + 12 ждущих) + 6 × 3 pipe + 1 log + ~20 прочих ≈ 58 <= 128). Порты для s ∈ {node_ephemeral, shared_snat}: 0.6 × 1 × 60.0 + 12 = 48 <= 0.50 × (1 × 16383) = 8191.5 -> PASS."
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Формульная граница: λ_fetch = P_live × W_fetchers / max(J_init_s, J_pod_s) = 1 × 1 / 12.0 = 0.0833 1/с; B = K_calls × (λ + 4√λ + 4) = 1 × (0.0833 + 1.1547 + 4) = 5.24 > 0.50 × 2.0 = 1.0 — формула НЕ проходит (константа +4 > 1.0), поэтому применена разрешённая каноном альтернатива: RPS Token-Bucket Rate-Limiter _SpawnRateLimiter (capacity=1, 1.0 токен/с) перед каждым Popen: B_dep,1s <= 1.0 <= 0.50 × Limit_dep_rps = 1.0 -> PASS. Поллинг зависимости отсутствует: R_poll(opencode_cli) = 0 <= 0.20 × 2.0 = 0.4 -> PASS (keepalive 15 с — к клиенту, не к зависимости). pod_fetcher/os.replace — N/A (роли нет).",
        "oracle": "VER-006: на FakeClock 10 конкурентных запусков дают <= 1 Popen в любом окне 1 с"
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Full Jitter: _retry_backoff_s(retry_num, rng_fn) = rng_fn(0, min(2.0, 0.5 × 2^retry_num)); retry 1: cap_1 = min(2.0, 1.0) = 1.0, u∈[0,0.5,1] -> [0.0, 0.5, 1.0]; retry 2: cap_2 = min(2.0, 2.0) = 2.0 -> [0.0, 1.0, 2.0]; jitter cooldown breaker 10.0 × U(0.8,1.2) ∈ [8.0, 12.0]. Пересев CSPRNG после fork() — N/A: fork() Python-воркеров нет (Popen сразу exec в opencode); поллеров с T_poll×U(0.8,1.2) нет.",
        "na_proof_for_subclauses": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I3": {
        "status": "N/A",
        "reason": "Нет поллеров Snapshot/DynamicConfig и условных fetch с ETag/If-None-Match: мост — stateless HTTP->CLI.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I4": {
        "status": "N/A",
        "reason": "Нет TTL-кэшей с сетевым дозапросом и singleflight; negative caching отсутствует.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "S-HERD-I5": {
        "status": "N/A",
        "reason": "Нет Snapshot/Control Plane/секретов в кэше; Max_stale_age_s[stateless_bridge] = 0; /health отвечает без зависимости от кэша.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "N/A",
        "reason": "Нет Snapshot-индексов маршрутизации; маппинг тулов — dict O(1) (canonical_map/allowed_map) на N_entities_max=64 tools запроса.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "_TOOL_BLOCK_RE, _INTERRUPTED_RE, _ACTION_INTENT_RE, _REASONING_TOOL_PLAN_RE, _FINAL_CONCLUSION_RE и маркеры _is_transient_stream_error компилируются при импорте модуля; в цикле событий и детекторе нет re.compile, copy.deepcopy, pydantic, json.loads конфигов (json.loads строки события opencode — разбор payload, не конфига); оракул spy re._compile/copy.deepcopy call_count==0 (VER-006)."
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Zero-Cost Disabled Path: `if not STEP_RECOVERY_ENABLED: return False` — первая инструкция _is_incomplete_tool_step до любых regex/аллокаций. Очередь _StdoutFeed: put_nowait в maxsize=4096; при Full — не drop (это данные ответа, drop = SILENT_DATA_LOSS), а overflow-флаг + _stop_proc + лог: вызов не блокирует поток-читатель. Телеметрия = _log под _LOG_LOCK с проглатыванием OSError (fail-open)."
      },
      "H-CPU-I4": {
        "status": "N/A",
        "reason": "В server.py нет asyncio event loop и горячего reload Snapshot; reload каталога моделей — вне изменённого пути.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "t_per_req_s = 0.02, t_per_attempt_s = 0.05 CPU-с; t_req_total = 0.02 + 3 × 0.05 = 0.17 с. Util_worker = κ × RPS_peak × t_req_total / (P_avail_min × W) + u_bg = 1.0 × 0.2 × 0.17 / (1 × 1) + 0.02 = 0.054 <= 0.70 -> PASS; W × Util + U_pod_sidecars = 0.054 + 0.25 = 0.304 <= 0.80 × 2.0 = 1.60 -> PASS; ΔCores_feature = RPS_peak × Δt = 0.2 × (2 × 0.05 + 0.001 детектор) = 0.0202 <= 0.05 × (1 × 2.0) = 0.10 -> PASS."
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "Σ_{a=1..3}(T_crit_aux(a) + T_wait(a) + T_backoff(a)): a=1: T_wait слота 15.0 + gate-wait 5.0 + token-wait 5.0 + backoff 0 = 25.0; a=2: 0 + 5.0 + 5.0 + cap_1 1.0 = 11.0; a=3: 0 + 5.0 + 5.0 + cap_2 2.0 = 12.0; итого 48.0 с <= 0.30 × 180.0 = 54.0 с -> PASS. Было бы: T_wait = TIMEOUT_S = 1800 с (EVD-017) -> FAIL, поэтому AD-004 вводит SLOT_WAIT_S/STARTUP_WAIT_S. T_call = min(TIMEOUT_S, deadline - monotonic()); при deadline - monotonic() <= 0 следующая попытка/сон не стартуют.",
        "oracle": "VER-006 (FakeClock, call_count==0 после deadline)"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "MAX_TOTAL_SPAWNS=3 на запрос + process Retry Budget (capacity 6, +0.20/первичный запрос, +0.05/с): для N_req=100 падающих запросов за T_w=500 с: N_retries <= floor(0.20×100 + 0.05×500) + 6 = floor(45) + 6 = 51 (без бюджета было бы до 200). Bulkhead: _slots(max_concurrent=6, max_waiters=12) с мгновенным 503 при переполнении."
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Fail-Closed: детерминированные 400/401/403/404/422 -> ошибка клиенту без повтора; Fail-Open: _StartupGate (таймаут 5 с -> запуск без замка), bridge.log (OSError проглатывается). Circuit Breaker opencode_cli: OPEN после 5 подряд транзиентных отказов, cooldown 10.0 × U(0.8,1.2) ∈ [8,12] с, в OPEN 503 без spawn за 0 с, HALF_OPEN — max_half_open_probes=1."
      },
      "R-BULK-I4": {
        "status": "N/A",
        "reason": "Нет пула прокси-нод/тенантов и V_eligible: единственная зависимость — бинарник OPENCODE_BIN; карантина нод нет.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      },
      "R-BULK-I5": {
        "status": "N/A",
        "reason": "Нет прокси-нод и разделения origin/node: ошибки апстрима opencode.ai/zen учитываются единым _UpstreamBreaker.",
        "na_proof": {
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
          ],
          "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
        }
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Каждый proc (start_new_session) закрывается _stop_proc (killpg SIGTERM -> wait 5 с -> SIGKILL) в finally перед следующим запуском и при выходе из запроса; _StdoutFeed (daemon) завершается по EOF после остановки proc; таймер _StartupGate — daemon и идемпотентный release; синглтоны лимитеров живут весь процесс, внешних клиентов нет. LaunchAgent stop -> SIGTERM процессу моста, дети в своих сессиях останавливаются finally-обработчиками активных запросов (graceful_shutdown_sec=5)."
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "На каждом выходе Handler.do_POST (401, 400 invalid json, 404, 503 bridge busy/circuit open, 502 opencode error, успех stream/json, overflow, deadline) — одна структурная строка bridge.log: mode, model, rc, tools, out_chars, retries/total_spawns, exit_reason, duration."
    },
    "M_SEM_v1": {
      "status": "N/A",
      "reason": "Нет пулов нод разных назначений (crawler/llm) и eligibility-фильтра: один локальный CLI на все запросы.",
      "na_proof": {
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py"
        ],
        "git_diff_method": "bridges/opencode-zen-bridge/ не отслеживается в HEAD (`git status --porcelain` -> '?? bridges/opencode-zen-bridge/'), поэтому git-diff-доказательство снимается как `git diff --no-index --stat <baseline server.py sha256=03eadced…673b, копия в run-dir Coder> bridges/opencode-zen-bridge/server.py` + `git status --porcelain -- bridges/opencode-zen-bridge`: изменены только server.py и tests/test_step_interruption.py",
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once, Handler._stream_google_sse (только _slots)}; callees: _slots(+waiters), _UpstreamBreaker, _RetryBudget, _StartupGate, _SpawnRateLimiter, subprocess.Popen(opencode run), _StdoutFeed, parse_opencode_event, ToolCallParser/_parse_tool_call_blocks/_split_tool_calls, _is_transient_stream_error, _is_incomplete_tool_step, _incomplete_tool_step_prompt, _retry_backoff_s, _stop_proc, _log; callers изменённых функций — только Handler.do_POST (HTTP) и тесты; транзитивно нет fork() воркеров, asyncio, Snapshot/Control Plane, поллеров, TTL-кэшей, singleflight, секретов, пула прокси-нод"
      }
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "opencode run (spawn+stream -> opencode.db + opencode.ai/zen)",
        "path": "hot",
        "timeout_budget": "T_call = min(TIMEOUT_S=1800, deadline - monotonic()); poll get(timeout=0.25 JSON / 1.0 SSE)",
        "bulkhead": "_slots max_concurrent=6 / max_waiters=12, SLOT_WAIT_S=15",
        "circuit_breaker": "OPEN после 5 подряд транзиентных отказов / cooldown 10×U(0.8,1.2) с / HALF_OPEN=1",
        "failure_mode_fallback": "транзиентная -> _stop_proc + повтор (A_max=3, Retry Budget, Full Jitter); детерминированная 4xx -> Fail-Closed ошибка клиенту; исчерпано -> накопленный текст finish_reason=stop или 502; OPEN -> 503 overloaded без spawn"
      },
      {
        "dependency_operation": "_StartupGate (сериализация старта sqlite opencode.db)",
        "path": "hot (aux)",
        "timeout_budget": "ожидание <= STARTUP_WAIT_S=5; удержание <= STARTUP_GATE_S=12 (типично 1.5–2.0)",
        "bulkhead": "1 держатель",
        "circuit_breaker": "нет (aux)",
        "failure_mode_fallback": "Fail-Open: запуск без замка + лог; 'database is locked' -> retryable failure в пределах A_max"
      },
      {
        "dependency_operation": "_SpawnRateLimiter (token-bucket запусков)",
        "path": "hot (aux)",
        "timeout_budget": "ожидание токена <= 5.0 с",
        "bulkhead": "capacity 1, 1.0 токен/с",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "не обходится; при deadline - monotonic() <= 0 запуск отменяется"
      },
      {
        "dependency_operation": "_StdoutFeed (очередь stdout)",
        "path": "hot",
        "timeout_budget": "get(timeout=0.25/1.0)",
        "bulkhead": "queue maxsize=4096",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "queue.Full -> overflow + _stop_proc, попытка неуспешна (засчитывается breaker), без silent drop"
      },
      {
        "dependency_operation": "Сокет клиента DSH (SSE/JSON)",
        "path": "hot",
        "timeout_budget": "Handler.timeout=300 с; keepalive каждые 15 с",
        "bulkhead": "по _slots",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "BrokenPipe/ConnectionReset -> _stop_proc, без повтора, лог O-EXIT"
      },
      {
        "dependency_operation": "bridge.log (телеметрия)",
        "path": "hot -> bg",
        "timeout_budget": "синхронный append под _LOG_LOCK",
        "bulkhead": "1 писатель",
        "circuit_breaker": "нет",
        "failure_mode_fallback": "Fail-Open: OSError проглатывается, 0 влияния на запрос"
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
      "PASS": 16,
      "N/A": 8,
      "FAIL": 0
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "BND-003 -> BND-001/BND-002, обратных зависимостей нет."
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Детектор и парсер — чистые функции без I/O (BND-001/BND-002 forbidden_dependencies)."
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "Новая логика выносится в отдельные функции/класс _StdoutFeed, а не в Handler; baseline-размер server.py — унаследованный долг."
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Детектор получает примитивы (строки, int, список имён), не объекты proc/Handler."
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит только OpenAI tool_calls/finish_reason; внутренние теги и ретраи скрыты."
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "Единый deadline TIMEOUT_S, get(timeout=0.25/1.0), _stop_proc wait(5), Handler.timeout=300."
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "MAX_TOTAL_SPAWNS=3 на запрос + Retry Budget (B_retry_max=6)."
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "A_max=3, Retry Budget, Circuit Breaker HALF_OPEN=1, ретраи внутри одного слота."
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "_StartupGate + _SpawnRateLimiter 1.0/с + Full Jitter backoff."
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "_StdoutFeed queue.Queue(maxsize=4096), queue.Full -> _stop_proc; waiters слота <= 12."
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Semaphore(6) + 503 по таймауту слота."
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не используется (ThreadingHTTPServer); блокирующее чтение stdout вынесено в выделенный поток."
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Ожидание через Queue.get(timeout), без циклов с sleep(0)/poll."
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "_stop_proc в finally каждой попытки; daemon-поток завершается по EOF после остановки процесса."
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "start_new_session + killpg SIGTERM -> wait -> SIGKILL на всех путях выхода, включая mid-stream error."
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "Состояние попытки локально для потока запроса; общий ресурс — только Queue (потокобезопасна) и _slots/_STARTUP_LOCK."
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Мост не исполняет инструменты (permission *=ask); ретрай повторяет только генерацию модели; уже отправленный SSE-префикс не дублируется (dedup_prefix)."
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Внешний HTTP/OpenAI контракт неизменен (REQ-006); CD-001 — внутренний, backward-compatible."
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Проглоченный tool-шаг детектируется и дозапрашивается; несовпадение dedup_prefix не теряет текст; overflow stdout — явный отказ, не drop."
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Mid-stream etype=error обрабатывается: _stop_proc + детектор + дозапрос (REQ-002)."
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "Секретов не добавляется; изменения — теги, регэкспы, числовые константы."
    }
  },
  "evidence_coverage": {
    "EVD-001..EVD-016": "все связаны: AD-001 {005,008,016}; AD-002 {001,002,003,004,007,009,010,011,012}; AD-003 {006,013,014,015,017}; AD-004 {006,012,014,015,017}; RISK-001 {007,010,011}; RISK-002 {013,014,015}; RISK-003 {008,009}; RISK-004 {003,006,012,016}; RISK-005 {014,017}"
  },
  "panel_findings_closure": {
    "Seat1-F1 BLOCKER": "high_load_envelope: schema HL-ENV/v1, field_count 46, 46 канонических ключей + field_sources, memory_closure_check PASS",
    "Seat1-F2 BLOCKER": "resilience_gates: 21 код + T-LIFE/O-EXIT/M-SEM, dependency_failure_matrix, двойное N/A-доказательство, non_waivable_stop_codes (24), _StdoutFeed maxsize=4096 + _stop_proc на queue.Full (AD-003, REQ-005)",
    "Seat1-F3 MAJOR": "MAX_TOTAL_SPAWNS=3 (AD-003, REQ-004), _retry_backoff_s Full Jitter, _StartupGate ранний release vs SLA_p99_s=180/p95=90 с; дополнительно AD-004 (ограниченные ожидания, token-bucket, Retry Budget, Breaker) — найдено при честной подстановке R-BULK-I1/S-HERD-I1",
    "Seat1-F4 MAJOR": "STEP_RECOVERY_ENABLED / OPENCODE_ZEN_BRIDGE_STEP_RECOVERY; признак 5 только с _ACTION_INTENT_RE; RISK-001 impact=medium",
    "Seat1-F5 MAJOR": "_is_transient_stream_error (REQ-002, AD-002); fallback dedup_prefix без потери (REQ-004, AD-003)",
    "Seat1-F6 MAJOR": "CD-002 (keepalive + finish_reason recovery); CD-003 (bulkhead/breaker 503)",
    "Seat1-F7 MINOR": "threads_per_worker=12 с разбивкой; все EVD-001..016 связаны",
    "Seat3-F1": "EVD-001..016 связаны с AD/RISK (evidence_coverage)",
    "Seat3-F2": "VER-004 diff -u репо vs ~/.dsh; VER-005 (emulate_tools=False, dedup mismatch, 'Ответ: 42:', 401 vs ECONNRESET)"
  },
  "role_plan": {
    "path": "plans/architect-02.json",
    "sha256": "27ff2ee9e1a7db6d3d48533dffc9280d2bf1197f6d605faced7ab0600f4a6bcb"
  }
}
<<<END ARTIFACT>>>

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/arch-panel/cycle-1/rework-brief.md" sha256="274bc0f3b34e9d876af3b918495e249c4a37460c5121d763d9e62c4513a68b8b" bytes="9585">>>
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
<<<END ARTIFACT>>>

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/arch-panel/cycle-1/verdict-a1.md" sha256="0e0e78a148bdb2b073b520ccfe1080a7105fcc6d458a95f270eb1199c249e825" bytes="2737">>>
# Вердикт Архитектурного Совета — Цикл 1 (`verdict-a1.md`)

- **Run ID:** `analyst-teamlead-zen-step-20261024`
- **Раунд:** `.ai-team/runs/analyst-teamlead-zen-step-20261024/panel/arch/r1`
- **Пакет архитектуры (v4):** `.ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json` (`sha256=490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1`)
- **Итоговый статус цикла 1:** `NEEDS WORK` (2 `ACCEPT`, 1 `NEEDS WORK`)

## Голоса судей (Cycle 1)

| Seat | Роль | Модель | Семейство | Транспорт | Вердикт | Ключевые замечания |
|---|---|---|---|---|---|---|
| **Seat 1** | Скептик (`skeptic`) | `grok-4.7-high` | `xAI` | `cursor-agent` | `NEEDS WORK` | `F1 BLOCKER` (46 канонических идентификаторов `REQUIRED_HL_ENV_FIELDS` + замыкание памяти), `F2 BLOCKER` (21 стоп-код `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5`, `Dependency Failure Matrix`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`, `maxsize` в `_StdoutFeed`), `F3 MAJOR` (единый потолок `A_max=3` запусков, Full-Jitter backoff, `SLA_p99_s`), `F4 MAJOR` (сужение признака 5 и отдельный kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`), `F5 MAJOR` (fallback `dedup_prefix` и транзиентный фильтр `etype=="error"`), `F6 MAJOR` (`CD-002`), `F7 MINOR` (привязка всех `EVD-*`, `threads_per_worker=12`, `VER-004` сверка с `~/.dsh`). |
| **Seat 2** | Реалист (`realist`) | `gemini-4-argon-high` | `Google` | `agy` | `ACCEPT` | `FINDINGS: NONE` (0 блокеров, решение минимально достаточное и закрывает все 5 режимов обрыва). |
| **Seat 3** | Визионер (`visionary`) | `muse-wonder-full-1.0` (замена `gpt-6.1-sol-high` 503) | `Meta` | `muse` | `ACCEPT` | 0 блокеров; 2 MINOR (`F1`: явная регрессия против протаскивания текстового ретрая в `_complete_response`; `F2`: в `VER-003`/верификации явно сверять идентичность `bridges/opencode-zen-bridge/server.py` и `~/.dsh/bridges/opencode-zen-bridge/server.py`). |

## Решение

Запустить Цикл 2 Архитектора (`claude-opus-5-5`, `high`, `claude-cli`) по брифам `rework-brief.md` и обновлённому `handoff-architect.md`, после чего провести Раунд 2 Архитектурного Совета (`.ai-team/runs/analyst-teamlead-zen-step-20261024/panel/arch/r2`).
<<<END ARTIFACT>>>

<<<ARTIFACT path="analysis/zen-step-interruption/handoff-architect.md" sha256="b4ca344f74aaf39c79b0d0416d9066b4c13b65f7f093b0628b71ce8a48067013" bytes="25577">>>
# Handoff to Architect: Устранение преждевременного обрывания многошаговых агентных цепочек в `opencode-zen-bridge` (v5)

## 1. Контекст и доказанная корневая причина (`[F-01]..[F-16]`)

В локальном мосте `bridges/opencode-zen-bridge/server.py` (обслуживающем `http://127.0.0.1:9883/v1` для DSH Desktop `[F-14]`, `[F-16]`) многошаговые агентные цепочки (`glm-5.3-flash-free` и др. модели с `emulate_tools=True`) обрываются посреди выполнения задачи с `finish_reason="stop"` и `tools=0` (`[F-10]`, `[F-11]`, `[F-12]`). Расследование по коду (`Zone A`), базе `opencode.db` (`Zone B`), журналу сессий DSH (`Zone C`) и логам моста (`Zone D`) выявило четыре взаимосвязанных механизма обрыва:

1. **Проглатывание тегов `<tool_call>` апстримом `opencode.ai/zen` (`[F-05]`, `[F-07]`, `[F-08]`, `[F-09]`):**
   Апстрим-провайдер `opencode.ai/zen` для семейства GLM (`glm-5.3-flash-free`) фильтрует/вырезает блоки `<tool_call>...</tool_call>` как служебные спец-токены (`[F-08]`: на промпте с `<tool_call>` возвращается `content=[]` при `tokens.output=75`, тогда как с нейтральным тегом `<tool_invoke>` возвращается валидный вызов `len(text)=283`). На Ходах 10 и 12 сессии `00e33abb-224c-4e4b-bd3d-6490f2bc9b87` модель сгенерировала короткую преамбулу намерения (`138` и `168` символов) и вызов инструмента (`non_reasoning_output = 350` и `133` токена), но блок `<tool_call>` был проглочен апстримом, а шаг закрылся с `finish="stop"` (`[F-07]`, `[F-09]`).
2. **Игнорирование `etype == "error"` (`ECONNRESET`) посреди стрима и склейка с синтетическим шагом `opencode run` (`[F-04]`, `[F-09]`, `[F-12]`):**
   На Ходе 11 (`14:11:56–14:12:27 MSK`) во время генерации произошёл обрыв соединения `ECONNRESET` (`[F-12]`). Исходный `server.py` при получении события `etype == "error"` не останавливал `proc` (`[F-04]`), из-за чего `opencode run` автоматически создал внутреннее синтетическое сообщение `"The previous response was interrupted..."`, на которое модель ответила текстом `"I was interrupted right before making tool calls..."` с `finish="stop"` без вызова тулов (`[F-09]`), а мост вернул этот склеенный текст клиенту как успешно завершённый ответ (`[F-03]`).
3. **Отсутствие детекции и ретрая оборванных инструментальных шагов в `Handler._stream_sse` и `Handler._serve_json` (`[F-01]`, `[F-02]`, `[F-03]`):**
   В исходном `server.py` ретрай при `emulate_tools=True` срабатывал только при `unmapped` нативных тулах (`NATIVE_RETRY_LIMIT = 2`) или при падении CLI с пустым выводом (`FAIL_RETRY_LIMIT = 3`) (`[F-03]`). Когда модель выдавала:
   - маркер прерванного ответа (`"I was interrupted right before making tool calls"`),
   - проглоченные токены (`non_reasoning_output - visible_est >= SWALLOWED_TOKENS_MIN`),
   - явный план вызова инструментов клиента в `reasoning` при короткой текстовой преамбуле без `tool_calls`,
   - или короткую статусную преамбулу намерения (`"Читаю вывод и проверяю состояние..."`, `"Собираю факты: ..."`),
   мост возвращал `finish_reason="stop"`, что приводило к немедленной записи `turn/end` в DSH (`[F-11]`).
4. **Блокирующее чтение `proc.stdout` без неблокирующей очереди с `maxsize` и SSE keepalive (`[F-06]`, `[F-15]`), а также отсутствие алиаса `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`):**
   В OpenCode v2.1.2 встроенный shell-инструмент называется `"shell"` (отсутствовал в `NATIVE_TOOL_ALIASES` `[F-05]`), а блокирующий цикл `for raw in proc.stdout:` не позволял отправлять `: keepalive\n\n` каждые `15s` и проверять дедлайн во время долгой фазы `thinking` (`[F-06]`).

## 2. Требования к архитектурному решению (`REQ-001..REQ-006`) с учётом замечаний Архитектурного Совета (`F1..F7`)

- **`REQ-001` (Двойная схема XML-тегов `<tool_invoke>` + `<tool_call>` и алиас `"shell"`):** В системной инструкции эмуляции инструментов требовать от модели тег `<tool_invoke>{"name": ..., "arguments": ...}</tool_invoke>` (не вырезаемый апстримом `opencode.ai/zen` `[F-08]`), а в `ToolCallParser` и `_parse_tool_call_blocks` поддерживать оба тега (`<tool_invoke>` и `<tool_call>`) для полной обратной совместимости (`[F-05]`, `[F-08]`). Добавить `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`).
- **`REQ-002` (Немедленная остановка `proc` при `etype == "error"`, классификация транзиентных ошибок и очистка маркеров обрыва):** В `Run._execute_once` и `Handler._stream_sse` при приходе `etype == "error"` немедленно останавливать дочерний процесс `_stop_proc(proc)`, чтобы не допускать запуска внутреннего синтетического шага `opencode run` (`[F-04]`, `[F-09]`), и вырезать строки `_INTERRUPTED_RE` из видимого текста. При этом выставлять `had_mid_stream_error = True` (разрешая ретрай) **только для транзиентных ошибок** (`_is_transient_stream_error(ev)`): когда `statusCode` отсутствует/`None`/`0`/`408`/`429`/`>= 500` или текст ошибки содержит транзиентный сетевой маркер (`econnreset`, `etimedout`, `timeout`, `timed out`, `socket hang up`, `interrupted`, `overloaded`, `rate limit`, `temporarily unavailable`, `fetch failed`, `network`), а для детерминированных клиентских/авторизационных ошибок `statusCode in (400, 401, 403, 404, 422)` НЕ ретраить (`had_mid_stream_error = False`) (`[F-12]`, закрытие `F5`).
- **`REQ-003` (Детектор оборванного инструментального шага `_is_incomplete_tool_step` с суженным признаком 5 и отдельным kill-switch `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY`):**
  - Ввести отдельный kill-switch `STEP_RECOVERY_ENABLED = os.environ.get("OPENCODE_ZEN_BRIDGE_STEP_RECOVERY", "1").strip().lower() not in ("0", "false", "no", "off")` (независимый от `OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES`, закрытие `F4`). При `not STEP_RECOVERY_ENABLED` функция `_is_incomplete_tool_step` немедленно возвращает `False`.
  - Реализовать детерминированную функцию `_is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool`, которая при `emulate_tools=True`, `STEP_RECOVERY_ENABLED=True` и отсутствии распознанных `tool_calls` определяет оборванный шаг по 5 признакам:
    1. `had_mid_stream_error=True` (только транзиентный `etype == "error"` или транзиентный сбой CLI);
    2. наличие маркера прерывания `_INTERRUPTED_RE` в `visible_text` или `reasoning_text`;
    3. **проглоченные токены (`swallowed_tokens`):** поскольку `tokens.output` в `opencode` включает `tokens.reasoning` (`[F-09]`), вычислять `non_reasoning_output = max(0, output_tokens - reasoning_tokens)` (если `reasoning_tokens > 0 and output_tokens >= reasoning_tokens`, иначе `output_tokens`), и при `len(stripped) <= 600` и `non_reasoning_output - max(1, len(stripped) // 3) >= SWALLOWED_TOKENS_MIN` (`35`) фиксировать проглоченный `<tool_call>`;
    4. явное упоминание имён клиентских инструментов (`tool_names`) и паттернов вызова (`_REASONING_TOOL_PLAN_RE`) в `reasoning_text` при коротком видимом ответе (`<= 600` символов);
    5. **узкая преамбула намерения (закрытие `F4`):** короткий текст (`<= 420` символов, до 6 строк, без финального вывода/таблицы/кода), который содержит **явный глагол намерения немедленного действия** (`_ACTION_INTENT_RE`: `"Читаю вывод..."`, `"Собираю факты..."`, `"Теперь посмотрим..."`, `"Let's check..."`, `"I'll run..."`) и при этом либо оканчивается на `:` / `...` / `…`, либо очень короток (`<= 220` символов). Голое двоеточие `:` в конце строки **без** `_ACTION_INTENT_RE` и без признаков 3/4 **не триггерит** ретрай (короткий финальный ответ `"Ответ: 42:"` или `"Итог проверки:"` возвращает `False`).
- **`REQ-004` (Единый потолок `A_max = 3` запусков на запрос, Full-Jitter backoff и безопасный fallback `dedup_prefix` в SSE/JSON):**
  - В `Handler._stream_sse` и `Handler._serve_json` ограничить **суммарное число запусков `opencode run` на один HTTP-запрос** константой `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`: 1 первичный запуск + не более 2 повторных запусков суммарно по `fail_retries` и `attempt`) под единым `deadline = time.monotonic() + TIMEOUT_S` (закрытие `F3`).
  - Унифицировать паузу между повторными запусками через функцию `_retry_backoff_s(retry_num, rng_fn=random.uniform)` по формуле Full Jitter из `S-HERD-I2`: `rng_fn(0.0, min(RETRY_BACKOFF_CAP_S, RETRY_BACKOFF_BASE_S * (2 ** retry_num)))`, где `RETRY_BACKOFF_BASE_S = 0.5`, `RETRY_BACKOFF_CAP_S = 2.0` (закрытие `F3`).
  - В `Handler._stream_sse` при `attempt > 0`: если новый накопленный текст `current` начинается с `dedup_prefix`, подавлять уже отправленный префикс (`emitted_len = len(dedup_prefix)`). Если же `len(current) >= len(dedup_prefix)` и `not current.startswith(dedup_prefix)` (модель переформулировала начало на ретрае), **не терять текст**: сбрасывать `dedup_prefix = ""` и отправлять клиенту весь новый текст `current[emitted_len:]` (закрытие `F5`).
- **`REQ-005` (Ограниченный `_StdoutFeed` с `maxsize=4096` и SSE keepalive):** Заменить блокирующее чтение `for raw in proc.stdout:` на фоновый поток-читатель `_StdoutFeed` с ограниченной очередью `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`STDOUT_QUEUE_MAX = 4096`). При переполнении очереди (`queue.Full`) выставлять флаг переполнения и останавливать процесс (`_stop_proc(proc)`), исключая неограниченный рост памяти (закрытие `F2`). Проверять дедлайн `TIMEOUT_S` каждые `0.25s` в `Run._execute_once` и отправлять `: keepalive\n\n` каждые `KEEPALIVE_INTERVAL_S = 15.0` секунд в `Handler._stream_sse` (`[F-06]`, `[F-15]`).
- **`REQ-006` (Сохранение публичных HTTP/OpenAI контрактов, `CD-002` и синхронизация репо с `~/.dsh`):** Внешний HTTP API (`/health`, `/v1/models`, `/v1/chat/completions`), порт `127.0.0.1:9883` и схема OpenAI остаются совместимыми (`[F-14]`, `[F-16]`). В `contract_deltas` явно зафиксировать `CD-002` (SSE `: keepalive` комментарии каждые `15s` и восстановление наблюдаемого `finish_reason` со сломанного `"stop"` на `"tool_calls"` при успешном ретрае), а в `VER-004` проверять побайтовое совпадение `bridges/opencode-zen-bridge/server.py` и `~/.dsh/bridges/opencode-zen-bridge/server.py` (закрытие `F6`, `F7`, `Seat 3 F2`).

## 3. Обязательный конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS` + эксплуатационный профиль)

Ниже заданы все 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` из `aisdlc-gcge/agents/architecture.md` §3.0 в единицах СИ (секунды, байты, ядра, 1/с) и производные параметры:

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0
  kappa_skew: 1.0
  u_bg_worker: 0.02
  U_pod_sidecars: 0.25
  Mem_limit_per_pod: 2147483648
  Mem_rss_worker_max: 67108864
  Mem_shared_max: 1207959552
  RPS_peak: 0.2
  A_max: 3
  SLA_p99_s: 180.0
  N_entities_max: 64
  Limit_dep_share_d: 6
  Limit_dep_rps_d: 2.0
  W_fetchers_d: 1
  J_init_s_d: 12.0
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0
  K_calls_d: 1
  T_base_s_d: 0.5
  T_cap_s_d: 2.0
  Max_stale_age_s_c: 0.0
  Min_healthy_ratio: 1.0
  B_retry_max: 6
  min_reserve_retry_rps: 0.05
  FD_worker: 128
  ulimit_n: 4096
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16383
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12
  stdout_queue_max: 4096
  latency_p50_ms: 14000
  latency_p95_ms: 90000
  latency_p99_ms: 180000
  rps_sustained: 0.05
  rps_peak: 0.2
  concurrency_max: 6
  payload_p50_kb: 48
  payload_p99_kb: 480
  read_write_ratio: "10:90"
  session_ttl_sec: 1800
  availability_target: "99.5%"
  error_budget_window: "30d"
  cpu_request_m: 100
  cpu_limit_m: 2000
  mem_request_mb: 64
  mem_limit_mb: 2048
  workers_processes: 1
  db_pool_min: 0
  db_pool_max: 1
  conn_max_lifetime_sec: 1800
  network_bandwidth_mbps: 100
  connect_timeout_ms: 5000
  read_timeout_ms: 300000
  write_timeout_ms: 300000
  total_deadline_ms: 1800000
  max_retries: 2
  max_total_spawns: 3
  backoff_base_ms: 500
  backoff_max_ms: 2000
  jitter_mode: "full_jitter"
  retry_budget_pct: 20
  queue_max_depth: 4096
  rate_limit_rps: 2.0
  circuit_breaker_threshold: 3
  bulkhead_max_concurrent: 6
  startup_gate_sec: 12
  max_batch_size: 1
  max_response_size_mb: 16
  hot_dataset_gb: 1.8
  cache_ttl_sec: 0
  replication_lag_max_ms: 0
  graceful_shutdown_sec: 5
  keepalive_interval_sec: 15
  swallowed_tokens_min: 35
```

### Пояснение к замыканию памяти (`HL-ENV-01`) и потокам (`threads_per_worker`)
- **Память (`HL-ENV-01`):** `W = 1` (один Python-процесс `ThreadingHTTPServer`), `Mem_rss_worker_max = 67 108 864 B` (`64 MiB` — верхняя оценка RSS самого Python-процесса моста с очередями `_StdoutFeed` `maxsize=4096`), `Mem_shared_max = 1 207 959 552 B` (`1152 MiB` = до `MAX_CONCURRENT = 6` одновременных дочерних процессов `opencode run` по `192 MiB` RSS каждый), `Mem_limit_per_pod = 2 147 483 648 B` (`2048 MiB` — бюджет локального демона `com.user.dsh-opencode-zen-bridge` на рабочей станции macOS). Проверка инварианта `HL-ENV-01`:
  $$W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} = 1 \times 64\text{ MiB} + 1152\text{ MiB} = 1216\text{ MiB} \le 0.80 \times 2048\text{ MiB} = 1638.4\text{ MiB} \quad (\text{PASS}).$$
- **Потоки (`threads_per_worker = 12`):** до `MAX_CONCURRENT = 6` потоков HTTP-хендлеров `ThreadingHTTPServer` + до `6` daemon-потоков `_StdoutFeed` (ровно 1 `_StdoutFeed` на активный `proc`, старый процесс завершается через `_stop_proc(proc)` до старта ретрая).

## 4. Семь гейтов отказоустойчивости (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`) и 21 стоп-код

### 4.1. `C-MULT` (`C-MULT-I1..I5`) — Мультипликация коннектов, подпроцессов, портов и FD
- **`C-MULT-I1`:** Единственная зависимость моста — локальный CLI `opencode run` (обращающийся к `opencode.db` и `opencode.ai/zen`), `Limit_dep_share[opencode_cli] = 10` слотов на хосте. В мосте `N_proc = 1`, `G_reload = 1`, семафор `_slots = threading.Semaphore(MAX_CONCURRENT)` (`6`) удерживается на весь HTTP-запрос (ретраи выполняются внутри захваченного слота после `_stop_proc(proc)`): $1 \times 1 \times 6 = 6 \le 0.60 \times 10 = 6.0$ (`PASS`).
- **`C-MULT-I2`:** Очередь чтения stdout каждого дочернего процесса ограничена `queue.Queue(maxsize=STDOUT_QUEUE_MAX)` (`4096`), а входные HTTP-запросы ограничены семафором `_slots.acquire(timeout=TIMEOUT_S)` с отказом `HTTP 503 {"error": "slot timeout"}` (`PASS`).
- **`C-MULT-I3`:** Семафор `_slots` и `_STARTUP_LOCK` — синглтоны уровня процесса (`N_proc = 1`, `fork()` воркеров нет, а дочерний `subprocess.Popen` делает `execve("opencode")` с `close_fds=True` по умолчанию в Python 3) (`PASS`).
- **`C-MULT-I4`:** Освобождение `_slots.release()` и `_stop_proc(proc)` обёрнуты в `try ... finally:` как в `Handler.do_POST`, так и в `Run._execute_once` и `Handler._stream_sse` (`PASS`).
- **`C-MULT-I5`:** `FD_worker = 128 <= 0.70 * ulimit_n = 2867.2` (`ulimit_n = 4096`); эфемерные порты: $\lambda_{\text{new\_conn}} \cdot N_{\text{pods}} \cdot T_{\text{hold\_s}} + C_{\text{active}} = 0.6 \times 1 \times 60 + 12 = 48 \le 0.50 \times (1 \times 16383) = 8191.5$ (`PASS`).

### 4.2. `S-HERD` (`S-HERD-I1..I5`) — Защита от Thundering Herd и Full-Jitter Backoff
- **`S-HERD-I1`:** Первые `STARTUP_GATE_S = 12.0` с старта `opencode run` сериализуются через `_StartupGate` (`_STARTUP_LOCK`), причём слот освобождается сразу по первому событию `step_start`/`text`/`reasoning`/`tool_use` (`gate.release()`). Темп старта $\lambda_{\text{fetch}} = 1 / 12.0 = 0.0833\text{ с}^{-1}$, пачечная граница $1 \cdot (0.0833 + 4\sqrt{0.0833} + 4) = 5.24\text{ с}^{-1}$ при serial gate фактически не превышает $1$ одновременный холодный старт (`PASS`).
- **`S-HERD-I2`:** Пауза между ретраями вычисляется через `_retry_backoff_s(retry_num, rng_fn)` с Full Jitter `rng_fn(0.0, min(T_cap_s, T_base_s * (2 ** retry_num)))` (`T_base_s = 0.5`, `T_cap_s = 2.0`), детерминированно тестируемой с инъекцией `rng_fn` на точках `u in [0.0, 0.5, 1.0]` (`PASS`).
- **`S-HERD-I3`, `S-HERD-I4`, `S-HERD-I5`:** `N/A` с двойным доказательством: (а) `git diff` затрагивает только `bridges/opencode-zen-bridge/server.py` и `bridges/opencode-zen-bridge/tests/test_step_interruption.py`; (б) транзитивный граф вызовов `Handler.do_POST -> _stream_response/_complete_response -> _stream_sse/_serve_json -> Run.execute/_execute_once` не содержит фоновых поллеров Control Plane, `If-None-Match` кэшей, `singleflight`-кэшей и ротации секретов (`stateless HTTP-to-CLI bridge`).

### 4.3. `H-CPU` (`H-CPU-I1..I5`) — Отсутствие busy-wait, предкомпилированные регулярные выражения и бюджет CPU
- **`H-CPU-I1`:** `N/A` (двойное доказательство по `git diff` и графу вызовов: мост не хранит routing-индексы нод; маппинг тулов `canonical_map` и `allowed_map` — $O(1)$ `dict` на `<= 64` инструментов запроса).
- **`H-CPU-I2`:** Все регулярные выражения (`_TOOL_BLOCK_RE`, `_INTERRUPTED_RE`, `_ACTION_INTENT_RE`, `_REASONING_TOOL_PLAN_RE`, `_FINAL_CONCLUSION_RE`) компилируются **один раз при импорте модуля** на уровне `server.py`; внутри цикла обработки SSE-событий и `_is_incomplete_tool_step` вызовов `re.compile` и `copy.deepcopy` нет (`PASS`).
- **`H-CPU-I3`:** При `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0` (`STEP_RECOVERY_ENABLED = False`) `_is_incomplete_tool_step` возвращает `False` за $O(1)$ на первой инструкции (`Zero-Cost Disabled Path`); очередь `_StdoutFeed` использует `maxsize=4096` с немедленной остановкой процесса при `queue.Full` (`PASS`).
- **`H-CPU-I4`:** `N/A` (двойное доказательство: в `server.py` нет `asyncio` event loop и нет горячего reload `Snapshot`).
- **`H-CPU-I5`:** При `RPS_peak = 0.2`, `A_max = 3`, CPU-времени Python-моста на попытку `t_per_attempt_s = 0.05 с` и `t_per_req_s = 0.02 с`:
  $$\text{Util}_{\text{worker}} = 0.02 + 0.2 \times (0.02 + 3 \times 0.05) = 0.054 \le 0.70, \quad \text{CPU}_{\text{pod}} = 0.054 + 0.25 = 0.304 \le 0.80 \times 2.0 = 1.60 \quad (\text{PASS}).$$

### 4.4. `R-BULK` (`R-BULK-I1..I5`) и `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`
- **`R-BULK-I1`:** Сумма вспомогательных ожиданий и межатемптовых пауз по `A_max = 3` попыткам: $\sum_{a=1}^{3} (T_{\text{crit\_aux\_s}}(a) + T_{\text{wait\_s}}(a) + T_{\text{backoff\_s}}(a)) \le (12.0 + 0) + (12.0 + 1.0) + (12.0 + 2.0) = 39.0\text{ с} \le 0.30 \times 180.0 = 54.0\text{ с}$ (`SLA_p99_s = 180.0`), а при `time.monotonic() >= deadline` цикл немедленно прерывается (`PASS`).
- **`R-BULK-I2`:** Потолок запусков `MAX_TOTAL_SPAWNS = 3` (`A_max = 3`) и семафор `_slots = Semaphore(6)` жёстко ограничивают параллелизм и число ретраев (`PASS`).
- **`R-BULK-I3`:** Классификатор `_is_transient_stream_error(ev)` разделяет транзиентные сетевые сбои (`ECONNRESET`, `ETIMEDOUT`, `429`, `5xx` -> ретрай) и детерминированные ошибки (`400`, `401`, `403`, `404`, `422` -> немедленный Fail-Closed без ретрая) (`PASS`).
- **`R-BULK-I4`, `R-BULK-I5`, `M-SEM/v1`:** `N/A` с двойным доказательством (`git diff` + граф вызовов `server.py`: мост проксирует запросы в единственный локальный бинарник `OPENCODE_BIN` без пула прокси-нод и без мульти-тенантных пулов `crawler`/`llm`).
- **`T-LIFE/v1`:** Жизненный цикл каждого дочернего `proc` и его daemon-потока `_StdoutFeed` детерминированно закрывается вызовом `_stop_proc(proc)` (`SIGTERM` -> `SIGKILL`) в `finally:` перед любым следующим `attempt` или выходом из запроса (`PASS`).
- **`O-EXIT/v1`:** На каждом выходе из `Handler.do_POST` (включая `503 slot timeout`, `400 invalid json`, ошибку `opencode` и успешный ответ) в `bridge.log` записывается структурная строка с `mode` (`stream`/`json`), `model`, `rc`, `tools`, `out_chars`, `duration` (`PASS`).
<<<END ARTIFACT>>>

<<<ARTIFACT path="analysis/zen-step-interruption/evidence-ledger.md" sha256="2a1970995627f21414bd6db60e5b0e75b271e3782f84922a35abee68bbc1faef" bytes="15224">>>
# Evidence Ledger: Преждевременное обрывание многошаговых агентных цепочек в `opencode-zen-bridge`

- [F-01] В исходном `server.py` (до фикса) NDJSON-события `opencode run --format json` разбираются функцией `parse_opencode_event` (потребляемой в `Run._execute_once` для non-stream и `Handler._stream_sse` для SSE): `etype == "text"` извлекает `part.get("text")`, `etype == "reasoning"` извлекает `part.get("text")` и `part.metadata.openai.reasoningEncryptedContent`, `etype == "error"` извлекает `statusCode` и `message`, `etype == "tool_use"` обрабатывается в циклах вызова (`part.tool`, `part.state.input`, `part.state.status`), а `etype == "step_finish"` возвращает только `tokens = _dict_or_empty(part.get("tokens"))`, полностью отбрасывая `part.get("reason")`. | /tmp/zen-tests-20261024/bridge/server.py:1441-1486,1952-1981,2310-2358 | 2026-10-24
- [F-02] В исходном `server.py` счётчики токенов из `step_finish` (`input`, `output`, `cached`, `reasoning`) суммируются в `usage[key]` (`Run._execute_once` строки 1961–1964, `Handler._stream_sse` строки 2329–2332) исключительно для формирования финального OpenAI `usage` (строки 2412–2423, 2541–2561) и никогда не сравниваются с длиной видимого текста для обнаружения проглоченных апстримом блоков `<tool_call>`. | /tmp/zen-tests-20261024/bridge/server.py:1961-1964,2329-2332,2412-2423,2541-2561 | 2026-10-24
- [F-03] В исходном `server.py` обработчики `Handler._stream_sse` (строки 2269–2403) и `Handler._serve_json` (строки 2466–2519) повторяют запуск `opencode run` только при падении CLI без вывода (`FAIL_RETRY_LIMIT = 3`, строки 238, 1874–1882, 2379–2390) либо когда нативное событие `tool_use` не удалось сопоставить со списком `tools` клиента (`unmapped` непуст, `NATIVE_RETRY_LIMIT = 2`, строки 233, 2392–2402, 2509–2518); если же шаг завершился с `reason="stop"` после преамбулы намерения, плана в `reasoning`, ошибки `ECONNRESET` или проглоченных токенов `<tool_call>` при `tool_calls == []` и `unmapped == []`, цикл немедленно прерывается (`break` на строках 2392–2393, 2509–2510) и возвращает клиенту `finish_reason="stop"` (строки 2420, 2547) без ретрая. | /tmp/zen-tests-20261024/bridge/server.py:233-239,1874-1882,2379-2403,2420,2509-2519,2547 | 2026-10-24
- [F-04] В исходном `server.py` при приходе события `etype == "error"` посреди стрима обработчик только логирует ошибку и добавляет её в `err_lines` (строки 1977–1981, 2338–2342) без остановки процесса `proc` (`_stop_proc`), позволяя `opencode run` самостоятельно запустить внутренний синтетический шаг продолжения (`"The previous response was interrupted..."` / `"I was interrupted right before making tool calls."`), который склеивается с преамбулой и завершается со статусом `stop` без вызова инструментов. | /tmp/zen-tests-20261024/bridge/server.py:1977-1981,2338-2342 | 2026-10-24
- [F-05] Текстовые вызовы тулов в исходном `server.py` разбираются классом `ToolCallParser` и функциями `_parse_tool_call_block`, `_parse_tool_call_blocks`, `_split_tool_calls` (строки 1007–1096, 1223–1385) только по тегам `<tool_call>...</tool_call>` (`TOOL_CALL_OPEN`/`TOOL_CALL_CLOSE`, строки 179–180), тогда как встроенные инструменты OpenCode CLI блокируются от локального исполнения через `OPENCODE_CONFIG_CONTENT` `"permission":{"*":"ask"}` (строки 186–189) и транслируются в OpenAI `tool_calls` через `_native_to_tool_calls` и `NATIVE_TOOL_ALIASES` (строки 206–224, 349–390, где в исходном `server.py` отсутствовал алиас `"shell"`, используемый в OpenCode v2.1.2). | /tmp/zen-tests-20261024/bridge/server.py:179-224,349-390,1007-1096,1223-1385 | 2026-10-24
- [F-06] Мост `opencode-zen-bridge` является stateless-сервисом на каждый HTTP-запрос: `do_POST` сериализует массив `messages` через `_messages_to_prompt` (строки 975–993) и передаёт его в `stdin` процесса `opencode run -m opencode/<id>[#variant] [--thinking] --format json [--standalone]` через `_spawn_with_stdin` (строки 641–656, 753–785); параллельность ограничена семафором `_slots = threading.Semaphore(MAX_CONCURRENT)` (строки 44, 725) и гейтом инициализации SQLite `_StartupGate` (`_STARTUP_LOCK`, `STARTUP_GATE_S = 12`, строки 692–720), а чтение `for raw in proc.stdout:` в исходном `server.py` блокировалось до прихода строки без фоновых SSE keepalive-пингов (строки 1937–1941, 2297–2300). | /tmp/zen-tests-20261024/bridge/server.py:43-44,641-656,692-725,753-785,975-993,1937-1941,2013,2297-2300 | 2026-10-24
- [F-07] В `~/.local/share/opencode/opencode.db` сессии `opencode v2.1.2` за `2026-10-24` записываются в таблицы `session_v2` и `session_message`: для оборванного Хода 12 (`15:07:18–15:07:27 MSK`, сессия `ses_e9231183effexUq1AtanwPx1eg`, модель `glm-5.3-flash-free`, `variant="max"`) в `session_message` записана строка `seq=5` (`id='msg_16dcee844001sbe9M6aE7ob0qb'`, `type='assistant'`), содержащая в `reasoning` явный план вызова инструментов (`"One message: job_output(bash-4a99049e1f764309) + bash check state.json + fix $RUN dates"`), а в `text` — только преамбулу длиной `len(text)=168` символов (`"**2026-10-24 13:56 MSK — статус по цели (обновляю туду каждую минуту).** Собираю факты: вывод fetch-джобы, состояние данных, правлю дату контура (реальная дата 24.10).\n"`) со статусом `finish="stop"` и `tokens={"input":114080,"output":499,"reasoning":366,"cache":{"read":0,"write":0}}`. | ~/.local/share/opencode/opencode.db:session_v2/ses_e9231183effexUq1AtanwPx1eg,session_message/msg_16dcee844001sbe9M6aE7ob0qb | 2026-10-24
- [F-08] Контраст со здоровыми инструментальными шагами в `opencode.db`: при использовании текстового тега `<tool_invoke>` на модели `glm-5.3-flash-free` (`ses_e91c671c2ffe1koNQ2kEjznIBR`, `msg_16e398eba001wfHVse61q8hJUN`, `seq=5`) апстрим `opencode.ai/zen` пропускает вызовы без потерь (`len(text)=283`, `<tool_invoke>{"name": "job_output", ...}</tool_invoke>`, `tokens={"input":20424,"output":128,"reasoning":0}`), тогда как на том же промпте с тегом `<tool_call>` (`ses_e91c5ff2cffet3cjmOVgMK8l2H`, `msg_16e3a015800106BnYiGKkyJ3WI`, `seq=7`) апстрим `opencode.ai/zen` вырезает блок `<tool_call>` целиком и возвращает пустой `content=[]`, `finish="stop"` при `tokens={"input":18255,"output":75,"reasoning":0}`. | ~/.local/share/opencode/opencode.db:session_message/msg_16e398eba001wfHVse61q8hJUN,session_message/msg_16e3a015800106BnYiGKkyJ3WI,part/prt_13c487e9b001vFizAzO1bN8pzv | 2026-10-24
- [F-09] Соотношение `tokens.output`, `tokens.reasoning` и `len(text)` в `opencode.db` (`session_v2`/`session_message`) доказывает, что `tokens.output` в `opencode` включает `tokens.reasoning`, а разница `non_reasoning_output = tokens.output - tokens.reasoning` при проглоченном `<tool_call>` кратно превышает объём видимого текста: (а) на Ходе 10 (`ses_e92752838ffeR1RI1LOyzoqDQU`, `msg_16d8ad84d001O6SQWVGmfgisIK`) `tokens={"input":113746,"output":506,"reasoning":156}` при `len(text)=138` символов (`non_reasoning_output = 350` токенов против ~46 токенов видимого текста, ~304 токена `<tool_call>` проглочены); (б) на Ходе 12 (`ses_e9231183effexUq1AtanwPx1eg`, `msg_16dcee844001sbe9M6aE7ob0qb`) `tokens={"input":114080,"output":499,"reasoning":366}` при `len(text)=168` символов (`non_reasoning_output = 133` токена против ~56 токенов видимого текста, ~77 токенов `<tool_call>` проглочены); (в) на Ходе 11 (`ses_e9263c73fffeRuhHv7uSWVYnf7`) после `ECONNRESET` на `seq=5` (`msg_16d9c399e001zT22uI1HfnZi5Z`) `opencode run` вставил синтетическое сообщение `seq=13` (`"The previous response was interrupted. Continue from where you left off without repeating completed content."`), на которое модель в `seq=16` (`msg_16d9c9809001cfEsm6azkM24y2`) ответила текстом `"I was interrupted right before making tool calls. Continue: collect fetch job output, fix run-dir dates, check state.json. All independent → one message, parallel calls."` со статусом `finish="stop"`. | ~/.local/share/opencode/opencode.db:session_v2/ses_e92752838ffeR1RI1LOyzoqDQU,session_v2/ses_e9231183effexUq1AtanwPx1eg,session_v2/ses_e9263c73fffeRuhHv7uSWVYnf7 | 2026-10-24
- [F-10] В проекционном кэше DSH `~/.dsh/storages/session_projcache/sessions/session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87.json` (`record.rows.turnOutline.val.turns`) зафиксированы три подряд оборванных хода пользователя: Turn 10 (`seq=168`, смещение `4881`, ответ `"Фетч завершён (exit 0). Читаю вывод и проверяю состояние. 🕐 [13:54 MSK] job_output fetch + правка дат $RUN на 20261024…"`), Turn 11 (`seq=251`, смещение `5147`, ответ `"**2026-10-24 13:55 MSK — Цель: новый прогон AI Disrupt (Collect → Score → TABLE-GATE), стоп на Select.** Туду (обновлен…"`) и Turn 12 (`seq=259`, смещение `5454`, ответ `"**2026-10-24 13:56 MSK — статус по цели (обновляю туду каждую минуту).** Собираю факты: вывод fetch-джобы, состояние да…"`). | ~/.dsh/storages/session_projcache/sessions/session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87.json:4881,5147,5454 | 2026-10-24
- [F-11] В полном журнале событий DSH `session.v4.jsonl.zstd` для `session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87` на Ходе 12 (`turn=12, step=1`, строки `L261–L267`, `seq=259..265`) после сообщения пользователя `"как деал?"` (`seq=262`) получено событие `assistant/message` (`L265`, `seq=263`, `responseId="chatcmpl-oczen-1ae55931e4ca"`), содержащее только блоки `reasoning` и `text` без `tool/call` и завершающий чанк `stopReason="stop"`, вследствие чего DSH записал `step/end` (`L266`, `seq=264`) и `turn/end` (`L267`, `seq=265`, `reason.kind="completed"`), полностью остановив выполнение задачи. | ~/.dsh/sessions/--Users-aazhiry1-~041C~043E~0439~0020~0434~0438~0441~043A-Workshop-aibunker-workshop--/session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87/session.v4.jsonl.zstd:L261-L267 | 2026-10-24
- [F-12] В `~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log` (строки `14571–14721`) все четыре инцидента `session-00e33abb-224c-4e4b-bd3d-6490f2bc9b87` точно коррелируют с `opencode.db` и `session.v4.jsonl.zstd`: (1) `13:52:13–13:52:57` (`prompt_chars=471145` -> `ECONNRESET` -> `rc=1 tools=0 out_chars=811 retries=0`), (2) `13:52:58–13:53:06` (`prompt_chars=309780` -> `rc=0 tools=0 out_chars=138 retries=0`, Turn 10), (3) `14:11:56–14:12:27` (`prompt_chars=309988` -> `ECONNRESET` -> `rc=1 tools=0 out_chars=791 retries=0`, Turn 11), (4) `15:07:18–15:07:27` (`prompt_chars=310809` -> `rc=0 tools=0 out_chars=168 retries=0`, Turn 12). | ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14721 | 2026-10-24
- [F-13] В `~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log` длительность всех оборванных запросов составила от 8 до 44 секунд (`44s`, `8s`, `31s`, `9s`), что исключает срабатывание общего таймаута процесса (`TIMEOUT_S = 1800`) или сокета (`Handler.timeout = 300`) и подтверждает, что обрыв происходит из-за отсутствия ретрая при `rc=1` после частичного текста (`ECONNRESET`) и при проглатывании тегов `<tool_call>` апстримом `opencode.ai/zen`. | /Users/aazhiry1/.dsh/bridges/opencode-zen-bridge/logs/bridge.log:14571-14726 | 2026-10-24
- [F-14] LaunchAgent `com.user.dsh-opencode-zen-bridge` запускает `/bin/bash /Users/aazhiry1/.dsh/bridges/opencode-zen-bridge/start.sh` (`KeepAlive=true`, `RunAtLoad=true`, `ThrottleInterval=5`, `OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT=6`), который поднимает однопроцессный `ThreadingHTTPServer` на `127.0.0.1:9883` из `/Users/aazhiry1/.dsh/bridges/opencode-zen-bridge/server.py`. | /Users/aazhiry1/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist:5-33, /Users/aazhiry1/.dsh/bridges/opencode-zen-bridge/start.sh:6-59 | 2026-10-24
- [F-15] Параметры рантайма `opencode-zen-bridge`: `TIMEOUT_S = 1800.0`, `Handler.timeout = 300`, `MAX_CONCURRENT = 6` (в LaunchAgent; дефолт в коде `2`), сериализация старта SQLite `_STARTUP_LOCK = threading.Lock()` с окном `STARTUP_GATE_S = 12.0` (`_StartupGate`), `NATIVE_RETRY_LIMIT = 2`, `FAIL_RETRY_LIMIT = 3`. | /Users/aazhiry1/.dsh/bridges/opencode-zen-bridge/server.py:45-49,276-282,973-1006,2349,2667 | 2026-10-24
- [F-16] Профиль DSH Desktop `~/.dsh/profiles/desktop/cordis.patch.yml` маршрутизирует провайдера `opencode-zen` (включая модель `glm-5.3-flash-free` / `GLM-5.3-Flash (Zen) Max`) на локальный мост `baseURL: http://127.0.0.1:9883/v1`. | /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml:28-39,179,239 | 2026-10-24
<<<END ARTIFACT>>>


---
PANEL-NONCE: a2af9742946ab043
ARTIFACT-SHA256: 1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: a2af9742946ab043» и «ARTIFACT-SHA256: 1053a4ca2e97d0eba0f350c3a71e13d8810c1a716e3b1e66a6c7ff0097e4f565».
