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

# Архитектурное ревью: Совет Тимлидов (`arch-panel`, раунд 1, место 3 — `visionary`)

Вы — независимый судья Архитектурного Совета Тимлидов (`arch-panel`, место 3, роль `visionary`, слот `gpt-6.1-sol-high`).
Ваша задача — провести строгое архитектурное ревью `architecture-packet.json` (критичность `S2`, профиль `python-bridge-bugfix`, задача `ZEN-STEP-INTERRUPTION-001`, прогон `analyst-teamlead-zen-step-20261024`).

ВАЖНО:
1. Вы работаете в режиме read-only оценки переданного пакета: НЕ модифицируйте никакие файлы и НЕ вызывайте инструменты изменения диска. Все необходимые артефакты приведены ниже ПОЛНОСТЬЮ без каких-либо сокращений.
2. В вашем ответе ОБЯЗАТЕЛЬНО:
   - В первой же строке повторите точный маркер `PANEL-NONCE: <hex>`, который лончер добавит в шапку этого брифа.
   - Укажите строку `ARCH_PACKET_SHA256: 490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1`.
   - Дайте разбор по своей шляпе (`visionary`): полнота связки с фактами `[F-01]..[F-16]`, корректность `AD-001..AD-003` (включая вычитание `reasoning_tokens` из `output_tokens` в `_is_incomplete_tool_step` по `[F-09]`), покрытие 46 полей `HL-ENV/v1`, 4 гейтов `C-MULT`, `S-HERD`, `H-CPU`, `R-BULK` и 21 стоп-кода GCGE.
   - Укажите блок `FINDINGS:` (`NONE` при отсутствии блокеров, либо список `F1..Fn` с severity `BLOCKER`/`MAJOR`/`MINOR`).
   - В последней строке ответа выведите ровно одну из двух строк вердикта:
     `VERDICT: ACCEPT`
     или
     `VERDICT: REJECT`

ПОЛНОТА ВЫДАЧИ:
Все артефакты переданы целиком, без купюр, без пропусков и без маркеров усечения:
- `.ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json` (bytes=45540, lines=815, sha256=490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1)
- `.ai-team/runs/analyst-teamlead-zen-step-20261024/receipts/arch-gate.json` (bytes=804, lines=14, sha256=63a97dd2a0a8a2989f98d1587500c0a469dd440a9c6bc45576bebac20e1321c8)
- `.ai-team/runs/analyst-teamlead-zen-step-20261024/plans/architect-01.json` (bytes=3465, lines=47, sha256=10dbe86110f2f0d37b146c1cfa86667187240225984cd803f8d106de3cf9ff2a)
- `analysis/zen-step-interruption/handoff-architect.md` (bytes=14813, lines=107, sha256=5a2689a3d44d8633cc4d645dc2e38d5442129c5a2f2f2dee5fac546e6504877b)
- `analysis/zen-step-interruption/evidence-ledger.md` (bytes=15224, lines=18, sha256=2a1970995627f21414bd6db60e5b0e75b271e3782f84922a35abee68bbc1faef)
- `analysis/zen-step-interruption/open-questions.md` (bytes=1413, lines=3, sha256=7b19740d89539d3fcd60fe153871e52e7b1db99046977765ab5bdf683b435f01)
- `analysis/zen-step-interruption/handoff-qa.md` (bytes=5010, lines=21, sha256=4c16a8907ed920fb8225f300797cbec4ff6fe948ebc28c9ec3bb5c9288fd95fc)

ЯКОРЯ ПАКЕТА:
- `task_id`: `ZEN-STEP-INTERRUPTION-001`
- `run_id`: `analyst-teamlead-zen-step-20261024`
- `criticality`: `S2`
- `status`: `APPROVED`
- `packet_sha256`: `490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1`
- `architect_slot`: `claude-opus-5-5` (исключён из судей `arch-panel`, `SK-A-12` соблюдён)
- `requirement_ids`: `REQ-001..REQ-006`
- `evidence`: `EVD-001..EVD-016` (`[F-01]..[F-16]`)
- `decisions`: `AD-001`, `AD-002`, `AD-003`
- `verification_surface`: `VER-001`, `VER-002`, `VER-003` (`owner: verifier`)
- `quality_scenarios`: `QA-001..QA-004`
- `boundaries`: `BND-001..BND-003`
- `contract_deltas`: `CD-001..CD-002`
- `views`: `VIEW-001..VIEW-003`
- `risks`: `RISK-001..RISK-004`
- `hl_env_v1`: 46 полей `HL-ENV/v1` + 4 гейта (`C-MULT`, `S-HERD`, `H-CPU`, `R-BULK`) + 21 стоп-код GCGE

## Артефакты пакета (D9 формат)

<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json" bytes=45540 lines=815 sha256=490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1 encoding=utf-8>>>
{
  "schema_version": "1.0",
  "task_id": "ZEN-STEP-INTERRUPTION-001",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "criticality": "S2",
  "profile": "python-bridge-bugfix",
  "status": "APPROVED",
  "summary": "Устранение преждевременного обрыва многошаговых агентных цепочек в opencode-zen-bridge: двойная схема тегов <tool_invoke>/<tool_call> + алиас shell, немедленная остановка proc на mid-stream error, детектор оборванного tool-шага с вычитанием reasoning_tokens и ограниченный дозапрос, неблокирующий _StdoutFeed + SSE keepalive. Внешний HTTP/OpenAI контракт не меняется.",
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006"
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
    }
  ],
  "drivers": [
    "reliability: многошаговая цепочка не должна завершаться finish_reason=stop при оборванном tool-шаге (REQ-002..REQ-004)",
    "compatibility: внешний HTTP/OpenAI контракт, порт 127.0.0.1:9883 и формат SSE/JSON неизменны (REQ-006)",
    "operability: ограниченный бюджет попыток NATIVE_RETRY_LIMIT=2 / FAIL_RETRY_LIMIT=3 под единым deadline TIMEOUT_S (REQ-006)",
    "reliability: долгая фаза thinking не должна рвать SSE-соединение клиента (REQ-005)"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; все тесты моста (существующие 350+ и новые test_step_interruption.py) зелёные, 0 failed / 0 errors.",
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
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "QA-006",
        "BND-001",
        "BND-002",
        "BND-003",
        "CD-001",
        "RISK-001",
        "RISK-002",
        "RISK-003",
        "RISK-004",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-002",
      "kind": "command",
      "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
      "expected": "exit 0; файл test_step_interruption.py существует и покрывает QA-POS-01..03, QA-NEG-01..02, QA-BND-01..02, QA-FAIL-01..02 из handoff-qa.md; Ran N>=9 tests, OK.",
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
        "QA-001",
        "QA-002",
        "QA-003",
        "QA-004",
        "QA-005",
        "CD-001",
        "RISK-001",
        "RISK-002",
        "RISK-004",
        "THREAT-001"
      ]
    },
    {
      "id": "VER-003",
      "kind": "command",
      "command": "PYTHONPATH=/Users/aazhiry1/work/src/cli-agent-bridge uvx pytest -q -p no:cacheprovider /Users/aazhiry1/work/src/cli-agent-bridge/tests/",
      "expected": "exit 0; корневой набор tests/ (219 тестов на момент анализа) зелёный, 0 failed / 0 errors — регрессий в соседних мостах нет.",
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
        "EVD-008"
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
      "question": "Как обнаружить и восстановить оборванный инструментальный шаг (mid-stream error, синтетическое продолжение, проглоченный <tool_call>, преамбула намерения) без ложных ретраев на коротких финальных ответах?",
      "choice": "На mid-stream etype==\"error\" — немедленный _stop_proc(proc) (не даём opencode run запустить синтетический шаг), _strip_interrupted_notice вырезает строки _INTERRUPTED_RE из видимого текста; детерминированный _is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) по 5 признакам (mid-stream error; маркер _INTERRUPTED_RE; swallowed tokens; план тулов в reasoning при коротком видимом ответе <=600; короткая преамбула намерения <=420 символов/<=6 строк). Признак swallowed tokens вычитает reasoning: non_reasoning_output = max(0, output_tokens - reasoning_tokens) при reasoning_tokens > 0 and output_tokens >= reasoning_tokens, иначе output_tokens; срабатывает при len(stripped) <= 600 и non_reasoning_output - max(1, len(stripped)//3) >= SWALLOWED_TOKENS_MIN (35). При срабатывании — дозапрос _incomplete_tool_step_prompt(tool_names, partial_text) в _stream_sse и _serve_json, ограниченный attempt < NATIVE_RETRY_LIMIT (2) под общим deadline, с dedup_prefix в SSE.",
      "alternatives": [
        "Только останавливать proc на error без детектора (не покрывает проглоченный <tool_call> и преамбулы Turn 10/12)",
        "Детектор без вычитания reasoning_tokens (ложные дозапросы на коротких финальных ответах с большим reasoning, QA-NEG-01)",
        "Возвращать клиенту finish_reason=length/ошибку вместо дозапроса (DSH всё равно завершает ход или показывает ошибку)",
        "Неограниченный ретрай до появления tool_calls (UNBOUNDED_RETRY / RETRY_STORM)"
      ],
      "drivers": [
        "reliability",
        "operability",
        "compatibility"
      ],
      "evidence_ids": [
        "EVD-003",
        "EVD-004",
        "EVD-007",
        "EVD-009",
        "EVD-012"
      ],
      "consequences": [
        "Реальные сбои детектируются: 350-46=304>=35 (Turn 10), 133-56=77>=35 (Turn 12), маркер interrupted (Turn 11)",
        "Короткий финальный ответ с output=400 reasoning=385 даёт 15<35 -> без дозапроса",
        "Худший случай латентности — 3 запуска opencode run в рамках одного HTTP-запроса и одного слота",
        "Эвристика преамбулы (признак 5) может давать редкие ложные срабатывания; они ограничены 2 доп. попытками и fallback на накопленный текст"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-POS-03, QA-NEG-01, QA-NEG-02, QA-BND-01, QA-BND-02, QA-FAIL-01 зелёные."
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как проверять дедлайн и держать SSE-соединение живым во время долгой фазы thinking при блокирующем чтении proc.stdout?",
      "choice": "Фоновый daemon-поток _StdoutFeed читает for raw in proc.stdout в queue.Queue(); потребители берут строки get(timeout=0.25) в Run._execute_once (проверка deadline TIMEOUT_S) и get(timeout=1.0) в Handler._stream_sse, отправляя SSE-комментарий ': keepalive\\n\\n' при простое >= KEEPALIVE_INTERVAL_S = 15.0 с; по EOF поток кладёт sentinel.",
      "alternatives": [
        "selectors/select на pipe-дескрипторе (непереносимо с текстовым буфером Popen, сложнее)",
        "Переписать мост на asyncio (несоразмерный рефакторинг ThreadingHTTPServer)",
        "Оставить блокирующее чтение (нет keepalive и проверки дедлайна, EVD-006)"
      ],
      "drivers": [
        "reliability",
        "operability"
      ],
      "evidence_ids": [
        "EVD-006",
        "EVD-015"
      ],
      "consequences": [
        "Клиент получает keepalive каждые 15 с во время thinking, дедлайн проверяется каждые <=0.25/1.0 с",
        "+1 daemon-поток на активный запуск (<=6 одновременно), очередь ограничена выводом одного процесса",
        "CPU в ожидании ~0% (блокирующий get с таймаутом, без busy-wait)"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "python3 -m unittest discover -s /Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/tests -p \"test_step_interruption.py\" -v",
        "expected": "QA-FAIL-02 зелёный: keepalive при молчании stdout >KEEPALIVE_INTERVAL_S, по TIMEOUT_S ожидание разблокируется и proc остановлен."
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
      "response_measure": "<= NATIVE_RETRY_LIMIT=2 доп. попыток; 0 дубликатов префикса в SSE (QA-POS-03)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "модель",
      "stimulus": "короткий финальный ответ с output=400 reasoning=385 без признаков намерения",
      "environment": "emulate_tools=True",
      "artifact": "_is_incomplete_tool_step",
      "response": "детектор возвращает False, ответ отдаётся с первой попытки",
      "response_measure": "0 ложных дозапросов на QA-NEG-01/02; граница 34->False, 35->True (QA-BND-01)",
      "verification_ids": [
        "VER-001",
        "VER-002"
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
      "response_measure": "интервал keepalive <= 15 с +1 с; разблокировка ожидания <= 1 с после deadline (QA-FAIL-02)",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "QA-006",
      "quality": "compatibility",
      "source": "DSH Desktop и другие клиенты",
      "stimulus": "обычные запросы /health, /v1/models, /v1/chat/completions",
      "environment": "127.0.0.1:9883, после деплоя фикса",
      "artifact": "HTTP API моста",
      "response": "формат SSE/JSON OpenAI, порт и эндпоинты не изменились; суммарные попытки ограничены 2/3",
      "response_measure": "существующие 350+ тестов моста и 219 корневых тестов зелёные (QA-REG-01)",
      "verification_ids": [
        "VER-001",
        "VER-003"
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
      "component": "server.py: детектор и промпт дозапроса (_is_incomplete_tool_step, _strip_interrupted_notice, _incomplete_tool_step_prompt, _INTERRUPTED_RE, _REASONING_TOOL_PLAN_RE, _ACTION_INTENT_RE)",
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
        "VER-003"
      ]
    },
    {
      "id": "BND-003",
      "component": "server.py: исполнение и транспорт (Run._execute_once, Handler._stream_sse, Handler._serve_json, _StdoutFeed, _stop_proc, _slots, _StartupGate)",
      "responsibility": "Жизненный цикл opencode run, единый deadline, бюджет попыток, keepalive, уборка процессов; вызывает BND-001/BND-002, но не наоборот.",
      "allowed_dependencies": [
        "BND-001",
        "BND-002",
        "subprocess",
        "threading",
        "queue"
      ],
      "forbidden_dependencies": [
        "изменение внешних эндпоинтов и формата ответа OpenAI",
        "новые сторонние зависимости"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003"
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
      "artifact_ref": "architecture/architecture-packet.json#boundaries (BND-001..BND-003)"
    },
    {
      "id": "VIEW-003",
      "type": "deployment",
      "question": "Где и как запущен мост?",
      "artifact_ref": "~/Library/LaunchAgents/com.user.dsh-opencode-zen-bridge.plist (EVD-014): однопроцессный ThreadingHTTPServer 127.0.0.1:9883"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Ложное срабатывание признака 5 (преамбула намерения) или 4 (план в reasoning) на легитимном коротком ответе -> лишние запуски opencode run.",
      "probability": "medium",
      "impact": "low",
      "mitigation": "Вычитание reasoning_tokens, пороги длины 420/600, исключение таблиц/кода/финальных выводов; не более NATIVE_RETRY_LIMIT=2 доп. попыток; fallback на накопленный текст с finish_reason=stop; тесты QA-NEG-01/02.",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Дозапросы утраивают латентность хода (до 3 запусков opencode run) и удерживают слот _slots дольше.",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Единый deadline TIMEOUT_S на весь HTTP-запрос; слот берётся один раз на запрос; жёсткие лимиты 2/3; QA-BND-02.",
      "verification_ids": [
        "VER-001",
        "VER-002"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Апстрим начнёт вырезать и <tool_invoke> либо другие модели Zen (kimi-k2.5, qwen3.6-plus) имеют иной профиль токенов -> SWALLOWED_TOKENS_MIN=35 некалиброван.",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Детектор swallowed tokens остаётся вторым рубежом поверх двойной схемы тегов; порог вынесен в константу; Q-001 (OPEN-01) — калибровка на других моделях как follow-up; регрессионный набор VER-003.",
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
      "mitigation": "Сравнение по уже отправленному клиенту префиксу; если новая попытка не начинается с префикса — отправлять только новый хвост без повторения; тест QA-POS-03 проверяет отсутствие дубликата.",
      "verification_ids": [
        "VER-001",
        "VER-002"
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
        "mitigation": "Парсер маппит только имена из списка tools текущего запроса клиента; исполнение и разрешения остаются на стороне DSH (permission ask/approval); встроенные тулы opencode не исполняются в мосте (permission *=ask); дозапрос ограничен NATIVE_RETRY_LIMIT=2 и не расширяет набор тулов.",
        "verification_ids": [
          "VER-001",
          "VER-002"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "Внешний HTTP/OpenAI контракт неизменен; парсер принимает оба тега; новые константы KEEPALIVE_INTERVAL_S и SWALLOWED_TOKENS_MIN — внутренние.",
    "migration": "Миграции данных нет: мост stateless, opencode.db не модифицируется мостом.",
    "rollout": "Правка bridges/opencode-zen-bridge/server.py в репозитории -> синхронизация в ~/.dsh/bridges/opencode-zen-bridge/server.py -> перезапуск LaunchAgent com.user.dsh-opencode-zen-bridge -> живой многошаговый ход DSH на glm-5.3-flash-free (тяжёлый путь).",
    "rollback": "git revert коммита фикса + повторная синхронизация и перезапуск LaunchAgent; частичный kill-switch дозапросов без деплоя — OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES=0 (отключает и unmapped-ретрай)."
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
    "reviewer": "deterministic fail-closed validate_architecture_packet.py (draft+approved); S2 — независимое review не обязательно, downstream_panel=true (Совет Тимлидов) остаётся отдельным гейтом",
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
      "class": "МОЖНО ПРОДОЛЖИТЬ",
      "question": "Нужен ли отдельный env-флаг kill-switch детектора дозапроса (GigaRC к локальному мосту неприменим); сейчас частичный откат — OPENCODE_ZEN_BRIDGE_NATIVE_RETRIES=0.",
      "blocking": false
    }
  ],
  "protected_paths": [],
  "materialization": [],
  "deferred": [
    "Калибровка SWALLOWED_TOKENS_MIN на kimi-k2.5 / qwen3.6-plus (Q-001)",
    "Отдельный kill-switch детектора (Q-002)",
    "Логирование причины срабатывания детектора в bridge.log (signal=1..5) для наблюдаемости"
  ],
  "hl_env_v1": {
    "schema": "HL-ENV/v1",
    "workload": {
      "rps_sustained": 0.2,
      "rps_peak": 2.0,
      "concurrency_max": 6,
      "payload_p50_kb": 48,
      "payload_p99_kb": 480,
      "read_write_ratio": "10:90",
      "session_ttl_sec": 1800
    },
    "slo": {
      "latency_p50_ms": 8000,
      "latency_p95_ms": 45000,
      "latency_p99_ms": 180000,
      "availability_target": "99.5%",
      "error_budget_window": "30d"
    },
    "resources": {
      "cpu_Request_limit": "100m/2000m (local macOS LaunchAgent process)",
      "mem_request_limit_mb": "64/512",
      "workers_processes": 1,
      "threads_per_worker": 6,
      "db_pool_min_max": "0/1 (opencode CLI internal SQLite serialized via _StartupGate)",
      "conn_max_lifetime_sec": 1800,
      "network_bandwidth_mbps": 100
    },
    "timeouts_retries": {
      "connect_timeout_ms": 5000,
      "read_timeout_ms": 300000,
      "write_timeout_ms": 300000,
      "total_deadline_ms": 1800000,
      "max_retries": 2,
      "backoff_base_ms": 500,
      "backoff_max_ms": 2000,
      "jitter": "none (deterministic local subprocess retry)",
      "retry_budget_pct": 20
    },
    "backpressure_limits": {
      "queue_max_depth": 6,
      "rate_limit_rps": 2.0,
      "circuit_breaker_threshold": "MAX_CONCURRENT=6 semaphore + FAIL_RETRY_LIMIT=3",
      "bulkhead_partitions": "global _slots Semaphore(6) + _StartupGate(12s)",
      "max_batch_size": 1,
      "max_response_size_mb": 16
    },
    "data_storage": {
      "hot_dataset_gb": 1.8,
      "index_strategy": "opencode.db internal SQLite WAL indexes (not modified by bridge)",
      "partitioning_sharding": "none (single-host local SQLite)",
      "cache_hit_ratio_target": "N/A (stateless HTTP-to-CLI bridge)",
      "cache_ttl_sec": 0,
      "replication_lag_max_ms": 0
    },
    "observability_degradation": {
      "fallback_mode": "Return accumulated visible text with finish_reason=stop after NATIVE_RETRY_LIMIT=2 exhausted",
      "graceful_shutdown_sec": 5,
      "key_metrics": "bridge.log rc, tools, out_chars, retries, duration_s",
      "shed_load_trigger": "_slots.acquire(timeout=TIMEOUT_S) -> HTTP 503 slot timeout",
      "idempotency_key_source": "OpenAI request messages history + dedup_prefix on stream retry"
    },
    "field_count": 46,
    "memory_closure": "W=1 * Mem_rss_worker_max 512MB + Mem_shared_max 0 <= 0.80 * Mem_limit (локальный процесс macOS без cgroup-лимита; RSS моста ~64MB, opencode run — отдельные процессы вне бюджета моста). PASS.",
    "resilience_gates": {
      "C-MULT": {
        "status": "PASS",
        "rationale": "Один HTTP-запрос -> <= 1 + NATIVE_RETRY_LIMIT(2) запусков opencode run при неполном шаге и <= FAIL_RETRY_LIMIT(3) при аварийном выходе без текста, всё под единым deadline = monotonic() + TIMEOUT_S(1800s); по исчерпанию лимита или deadline цикл завершается без рекурсии. Каскадного умножения нет: мост — единственная роль, апстрим вызывается только через дочерний CLI.",
        "evidence_ids": [
          "EVD-003",
          "EVD-015"
        ]
      },
      "S-HERD": {
        "status": "PASS",
        "rationale": "Параллельные запуски, включая ретраи, сериализуют первые STARTUP_GATE_S=12s через _StartupGate (_STARTUP_LOCK), предотвращая конкурентный старт SQLite opencode.db; ретрай идёт внутри уже занятого слота, синхронного залпа нет; FAIL_RETRY_BACKOFF_S=0.8.",
        "evidence_ids": [
          "EVD-006",
          "EVD-015"
        ]
      },
      "H-CPU": {
        "status": "PASS",
        "rationale": "_StdoutFeed: блокирующее чтение в daemon-потоке + queue.Queue.get(timeout=0.25 JSON / 1.0 SSE); нет busy-wait, CPU в ожидании ~0%; детектор — O(len(text)) регэкспы на тексте <=600 символов, вызывается один раз на попытку.",
        "evidence_ids": [
          "EVD-006"
        ]
      },
      "R-BULK": {
        "status": "PASS",
        "rationale": "_slots=Semaphore(MAX_CONCURRENT=6) удерживается весь HTTP-запрос, ретраи не берут доп. слоты; при любом выходе из попытки (error, step_finish, таймаут, обрыв клиента) _stop_proc: killpg SIGTERM -> wait(5) -> SIGKILL — зомби opencode run не остаются; shed load — HTTP 503 по таймауту слота.",
        "evidence_ids": [
          "EVD-004",
          "EVD-006",
          "EVD-015"
        ]
      }
    },
    "gcge_stop_codes_checked": {
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
        "rationale": "attempt < NATIVE_RETRY_LIMIT=2, fail_retries < FAIL_RETRY_LIMIT=3."
      },
      "RETRY_STORM": {
        "status": "PASS",
        "rationale": "Ретраи внутри одного слота, max 6 параллельных запросов, лимиты 2/3, без умножения по слоям."
      },
      "THUNDERING_HERD": {
        "status": "PASS",
        "rationale": "_StartupGate сериализует старт opencode run на 12 с."
      },
      "UNBOUNDED_QUEUE": {
        "status": "PASS",
        "rationale": "queue.Queue в _StdoutFeed ограничена выводом одного процесса и временем жизни попытки; поток завершается по EOF/_stop_proc; max_response_size_mb=16."
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
        "rationale": "Проглоченный tool-шаг теперь детектируется и дозапрашивается; при исчерпании лимита клиент получает накопленный текст, а bridge.log фиксирует retries."
      },
      "UNHANDLED_UPSTREAM_ERROR": {
        "status": "PASS",
        "rationale": "Mid-stream etype=error обрабатывается: _stop_proc + детектор + дозапрос (REQ-002)."
      },
      "HARDCODED_SECRET": {
        "status": "PASS",
        "rationale": "Секретов не добавляется; изменения — теги, регэкспы, числовые константы."
      }
    }
  },
  "role_plan": {
    "path": "plans/architect-01.json",
    "sha256": "10dbe86110f2f0d37b146c1cfa86667187240225984cd803f8d106de3cf9ff2a"
  }
}
<<<ARTIFACT_END path=".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json" sha256=490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1>>>
<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/receipts/arch-gate.json" bytes=804 lines=14 sha256=63a97dd2a0a8a2989f98d1587500c0a469dd440a9c6bc45576bebac20e1321c8 encoding=utf-8>>>
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "ARCH_GATE_PASS",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "criticality": "S2",
  "packet_sha256": "490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1",
  "role_plan_sha256": "10dbe86110f2f0d37b146c1cfa86667187240225984cd803f8d106de3cf9ff2a",
  "verification_surface_sha256": "f4a348f60acc6373ff25cea51944638f948a885c3ae90b0e2e63e65e6f20432b",
  "protected_paths_sha256": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
  "architect_worktree_sha256": "e5163f07b7f53d846fc7689cf1a687570a273a72648c5b0cc7d393b0e92f2603",
  "materialized_targets": 0,
  "validator_output": "PASS: architecture packet is valid for approved; sha256=490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1"
}
<<<ARTIFACT_END path=".ai-team/runs/analyst-teamlead-zen-step-20261024/receipts/arch-gate.json" sha256=63a97dd2a0a8a2989f98d1587500c0a469dd440a9c6bc45576bebac20e1321c8>>>
<<<ARTIFACT path=".ai-team/runs/analyst-teamlead-zen-step-20261024/plans/architect-01.json" bytes=3465 lines=47 sha256=10dbe86110f2f0d37b146c1cfa86667187240225984cd803f8d106de3cf9ff2a encoding=utf-8>>>
{
  "schema_version": "1.0",
  "role": "architect",
  "run_id": "analyst-teamlead-zen-step-20261024",
  "task_id": "ZEN-STEP-INTERRUPTION-001",
  "model": "claude-opus-5-5",
  "effort": "high",
  "permissions": "run-artifacts-write",
  "steps": [
    {
      "id": "S1",
      "title": "Прочитать handoff-architect, evidence-ledger, open-questions, handoff-qa и скиллы architect-software-product + aisdlc-gcge/skills/architecture.md",
      "status": "DONE",
      "actual_evidence": "Прочитаны analysis/zen-step-interruption/{handoff-architect.md,evidence-ledger.md (F-01..F-16),open-questions.md (OPEN-01 МОЖНО ПРОДОЛЖИТЬ),handoff-qa.md}, SKILL.md, architecture.md §HL-RESILIENCE-GATES-V5, validate_architecture_packet.py."
    },
    {
      "id": "S2",
      "title": "Выборочно перепроверить свежесть ключевых фактов в продуктовом коде (read-only)",
      "status": "DONE",
      "actual_evidence": "bridges/opencode-zen-bridge/server.py: TOOL_CALL_OPEN=<tool_call> (стр.179), NATIVE_TOOL_ALIASES без ключа shell (стр.206-224), NATIVE_RETRY_LIMIT=2 (стр.233), FAIL_RETRY_LIMIT=3 (стр.238), _stop_proc killpg SIGTERM->SIGKILL (стр.435), _StartupGate/STARTUP_GATE_S=12 (стр.692-720), _slots (стр.725), etype==error без остановки (стр.1977); _StdoutFeed/_is_incomplete_tool_step/keepalive отсутствуют — фикса ещё нет, факты F-03..F-06 актуальны."
    },
    {
      "id": "S3",
      "title": "Принять решения AD-001..AD-003 (two-way), границы BND-001..003, contract delta CD-001, риски и threat model",
      "status": "DONE",
      "actual_evidence": "architecture/architecture-packet.json: decisions AD-001 (<tool_invoke>+<tool_call>, shell alias; EVD-005/008), AD-002 (_stop_proc на error + _strip_interrupted_notice + 5-сигнальный _is_incomplete_tool_step с non_reasoning_output = max(0, output_tokens - reasoning_tokens), NATIVE_RETRY_LIMIT=2), AD-003 (_StdoutFeed + KEEPALIVE_INTERVAL_S=15.0); RISK-001..004; THREAT-001; ASM-001/002 VALIDATED."
    },
    {
      "id": "S4",
      "title": "Заполнить HL-ENV/v1 (46 полей), гейты C-MULT/S-HERD/H-CPU/R-BULK и 21 стоп-код gcge",
      "status": "DONE",
      "actual_evidence": "hl_env_v1: подсчёт полей = 46, gcge_stop_codes_checked = 21 (python3 json-проверка); resilience_gates C-MULT/S-HERD/H-CPU/R-BULK = PASS с evidence_ids."
    },
    {
      "id": "S5",
      "title": "Заморозить verification surface VER-001..003 (owner=verifier) и провалидировать draft-пакет",
      "status": "DONE",
      "actual_evidence": "validate_architecture_packet.py --phase draft -> PASS: architecture packet is valid for draft; sha256=67f60635127400edfa2166916b6a4e99ec3912edfa0e63eaef17153881e16e9a (rc=0)."
    },
    {
      "id": "S6",
      "title": "Перевести пакет в APPROVED с role_plan.sha256, пройти approved-gate, записать receipts architect.json и arch-gate.json",
      "status": "DONE",
      "actual_evidence": "Approved-валидация с --run-dir и --role-plan выполняется по этому плану; результат и sha256 пакета фиксируются в receipts/architect.json и receipts/arch-gate.json (ARCH_GATE_PASS)."
    }
  ]
}
<<<ARTIFACT_END path=".ai-team/runs/analyst-teamlead-zen-step-20261024/plans/architect-01.json" sha256=10dbe86110f2f0d37b146c1cfa86667187240225984cd803f8d106de3cf9ff2a>>>
<<<ARTIFACT path="analysis/zen-step-interruption/handoff-architect.md" bytes=14813 lines=107 sha256=5a2689a3d44d8633cc4d645dc2e38d5442129c5a2f2f2dee5fac546e6504877b encoding=utf-8>>>
# Handoff to Architect: Устранение преждевременного обрывания многошаговых агентных цепочек в `opencode-zen-bridge`

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
4. **Блокирующее чтение `proc.stdout` без неблокирующей очереди и SSE keepalive (`[F-06]`, `[F-15]`), а также отсутствие алиаса `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`):**
   В OpenCode v2.1.2 встроенный shell-инструмент называется `"shell"` (отсутствовал в `NATIVE_TOOL_ALIASES` `[F-05]`), а блокирующий цикл `for raw in proc.stdout:` не позволял отправлять `: keepalive\n\n` каждые `15s` и проверять дедлайн во время долгой фазы `thinking` (`[F-06]`).

## 2. Требования к архитектурному решению (`REQ-001..REQ-006`)

- **`REQ-001` (Двойная схема XML-тегов `<tool_invoke>` + `<tool_call>`):** В системной инструкции эмуляции инструментов требовать от модели тег `<tool_invoke>{"name": ..., "arguments": ...}</tool_invoke>` (не вырезаемый апстримом `opencode.ai/zen` `[F-08]`), а в `ToolCallParser` и `_parse_tool_call_blocks` поддерживать оба тега (`<tool_invoke>` и `<tool_call>`) для полной обратной совместимости (`[F-05]`, `[F-08]`). Добавить `"shell"` в `NATIVE_TOOL_ALIASES` (`[F-05]`).
- **`REQ-002` (Немедленная остановка `proc` при `etype == "error"` и очистка маркеров обрыва):** В `Run._execute_once` и `Handler._stream_sse` при приходе `etype == "error"` (или при `rc != 0` после ошибки провайдера `ECONNRESET`/`ETIMEDOUT` без собранных `tool_calls`) немедленно останавливать дочерний процесс `_stop_proc(proc)`, чтобы не допускать запуска внутреннего синтетического шага `opencode run` (`[F-04]`, `[F-09]`), и вырезать строки `_INTERRUPTED_RE` из видимого текста.
- **`REQ-003` (Детектор оборванного инструментального шага `_is_incomplete_tool_step` с учётом `reasoning_tokens`):** Реализовать детерминированную функцию `_is_incomplete_tool_step(visible_text, reasoning_text, tool_names, had_mid_stream_error=False, output_tokens=0, reasoning_tokens=0) -> bool`, которая при `emulate_tools=True` и отсутствии распознанных `tool_calls` определяет оборванный шаг по 5 признакам:
  1. `had_mid_stream_error=True`;
  2. наличие маркера прерывания `_INTERRUPTED_RE` в `visible_text` или `reasoning_text`;
  3. **проглоченные токены (`swallowed_tokens`):** поскольку `tokens.output` в `opencode` включает `tokens.reasoning` (`[F-09]`), вычислять `non_reasoning_output = max(0, output_tokens - reasoning_tokens)` (если `reasoning_tokens > 0 and output_tokens >= reasoning_tokens`, иначе `output_tokens`), и при `len(stripped) <= 600` и `non_reasoning_output - max(1, len(stripped) // 3) >= SWALLOWED_TOKENS_MIN` (`35`) фиксировать проглоченный `<tool_call>` без ложных срабатываний на коротких финальных ответах с большим `reasoning`;
  4. явное упоминание имён клиентских инструментов (`tool_names`) и паттернов вызова (`_REASONING_TOOL_PLAN_RE`) в `reasoning_text` при коротком видимом ответе (`<= 600` символов);
  5. короткая преамбула намерения (`<= 420` символов, до 6 строк, без финального вывода/таблицы/кода), оканчивающаяся на `:` / `...` / `…` или содержащая глагол немедленного действия (`_ACTION_INTENT_RE`: `"Читаю вывод..."`, `"Собираю факты..."`, `"Теперь посмотрим..."`, `"Let's check..."`).
- **`REQ-004` (Цикл автоматического дозапроса `_incomplete_tool_step_prompt` в SSE и JSON режимах):** В `Handler._stream_sse` и `Handler._serve_json` при срабатывании `_is_incomplete_tool_step` выполнять до `NATIVE_RETRY_LIMIT` (`2`) повторных попыток (`attempt < NATIVE_RETRY_LIMIT`), передавая уже отправленный клиенту префикс текста в `_incomplete_tool_step_prompt(tool_names, partial_text)` и подавляя дублирование префикса в SSE через `dedup_prefix`.
- **`REQ-005` (Неблокирующий `_StdoutFeed` и SSE keepalive):** Заменить блокирующее чтение `for raw in proc.stdout:` на фоновый поток-читатель `_StdoutFeed` с `queue.Queue()`, проверяющий дедлайн `TIMEOUT_S` каждые `0.25s` в `Run._execute_once` и отправляющий `: keepalive\n\n` каждые `KEEPALIVE_INTERVAL_S = 15.0` секунд в `Handler._stream_sse` (`[F-06]`, `[F-15]`).
- **`REQ-006` (Сохранение публичных HTTP/OpenAI контрактов и бюджет ретраев):** Внешний HTTP API (`/health`, `/v1/models`, `/v1/chat/completions`), порт `127.0.0.1:9883` и формат SSE/JSON ответов OpenAI остаются неизменными (`[F-14]`, `[F-16]`). Суммарное число попыток в рамках одного HTTP-запроса жёстко ограничено существующими константами `NATIVE_RETRY_LIMIT = 2` и `FAIL_RETRY_LIMIT = 3` (`[F-03]`, `[F-15]`).

## 3. Обязательный конверт `HL-ENV/v1` (46 полей)

```yaml
schema: HL-ENV/v1
workload:
  rps_sustained: 0.2
  rps_peak: 2.0
  concurrency_max: 6
  payload_p50_kb: 48
  payload_p99_kb: 480
  read_write_ratio: "10:90"
  session_ttl_sec: 1800
slo:
  latency_p50_ms: 8000
  latency_p95_ms: 45000
  latency_p99_ms: 180000
  availability_target: "99.5%"
  error_budget_window: "30d"
resources:
  cpu_Request_limit: "100m/2000m (local macOS LaunchAgent process)"
  mem_request_limit_mb: "64/512"
  workers_processes: 1
  threads_per_worker: 6
  db_pool_min_max: "0/1 (opencode CLI internal SQLite serialized via _StartupGate)"
  conn_max_lifetime_sec: 1800
  network_bandwidth_mbps: 100
timeouts_retries:
  connect_timeout_ms: 5000
  read_timeout_ms: 300000
  write_timeout_ms: 300000
  total_deadline_ms: 1800000
  max_retries: 2
  backoff_base_ms: 500
  backoff_max_ms: 2000
  jitter: "none (deterministic local subprocess retry)"
  retry_budget_pct: 20
backpressure_limits:
  queue_max_depth: 6
  rate_limit_rps: 2.0
  circuit_breaker_threshold: "MAX_CONCURRENT=6 semaphore + FAIL_RETRY_LIMIT=3"
  bulkhead_partitions: "global _slots Semaphore(6) + _StartupGate(12s)"
  max_batch_size: 1
  max_response_size_mb: 16
data_storage:
  hot_dataset_gb: 1.8
  index_strategy: "opencode.db internal SQLite WAL indexes (not modified by bridge)"
  partitioning_sharding: "none (single-host local SQLite)"
  cache_hit_ratio_target: "N/A (stateless HTTP-to-CLI bridge)"
  cache_ttl_sec: 0
  replication_lag_max_ms: 0
observability_degradation:
  fallback_mode: "Return accumulated visible text with finish_reason=stop after NATIVE_RETRY_LIMIT=2 exhausted"
  graceful_shutdown_sec: 5
  key_metrics: "bridge.log rc, tools, out_chars, retries, duration_s"
  shed_load_trigger: "_slots.acquire(timeout=TIMEOUT_S) -> HTTP 503 slot timeout"
  idempotency_key_source: "OpenAI request messages history + dedup_prefix on stream retry"
```

## 4. Четыре гейта отказоустойчивости (`C-MULT`, `S-HERD`, `H-CPU`, `R-BULK`)

### 4.1. `C-MULT` — Каскадное умножение вызовов и таймаутов
- Внутри одного HTTP-запроса `/v1/chat/completions` цикл `while True:` ограничен `attempt < NATIVE_RETRY_LIMIT` (`2`, максимум 3 запуска `opencode run` при неполном tool-шаге) и `fail_retries < FAIL_RETRY_LIMIT` (`3` при аварийном выходе без текста) под единым глобальным `deadline = time.monotonic() + TIMEOUT_S` (`1800s`) (`[F-03]`, `[F-15]`).
- При исчерпании `NATIVE_RETRY_LIMIT = 2` или наступлении `deadline` цикл немедленно завершается без бесконечной рекурсии.

### 4.2. `S-HERD` — Защита от Thundering Herd при старте подпроцессов
- Все параллельные запросы сериализуют первые `STARTUP_GATE_S = 12.0` секунд жизни `opencode run` через `_StartupGate` (`_STARTUP_LOCK`), предотвращая конкурентные блокировки SQLite (`~/.local/share/opencode/opencode.db`) при одновременных ретраях (`[F-06]`, `[F-15]`).

### 4.3. `H-CPU` — Отсутствие busy-wait и CPU-спинов
- Чтение `proc.stdout` в `_StdoutFeed` выполняется блокирующим `for raw in self._proc.stdout:` в выделенном daemon-потоке и передаётся через `queue.Queue.get(timeout=0.25)` (в JSON-режиме) или `timeout=1.0` (в SSE-режиме), что исключает busy-wait и удерживает потребление CPU моста около 0% в ожидании ответа модели (`[F-06]`).

### 4.4. `R-BULK` — Изоляция ресурсов и уборка дочерних процессов
- Семафор `_slots = threading.Semaphore(MAX_CONCURRENT)` удерживается на протяжении всего HTTP-запроса (включая внутренние ретраи `attempt`), поэтому ретрай не захватывает дополнительные слоты сверх `MAX_CONCURRENT` (`[F-15]`).
- При любом выходе из попытки (ошибка `etype == "error"`, `step_finish`, таймаут, разрыв клиентского соединения) вызывается `_stop_proc(proc)` (`SIGTERM` -> `SIGKILL`), гарантирующий отсутствие зомби-процессов `opencode run` (`[F-04]`).
<<<ARTIFACT_END path="analysis/zen-step-interruption/handoff-architect.md" sha256=5a2689a3d44d8633cc4d645dc2e38d5442129c5a2f2f2dee5fac546e6504877b>>>
<<<ARTIFACT path="analysis/zen-step-interruption/evidence-ledger.md" bytes=15224 lines=18 sha256=2a1970995627f21414bd6db60e5b0e75b271e3782f84922a35abee68bbc1faef encoding=utf-8>>>
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
<<<ARTIFACT_END path="analysis/zen-step-interruption/evidence-ledger.md" sha256=2a1970995627f21414bd6db60e5b0e75b271e3782f84922a35abee68bbc1faef>>>
<<<ARTIFACT path="analysis/zen-step-interruption/open-questions.md" bytes=1413 lines=3 sha256=7b19740d89539d3fcd60fe153871e52e7b1db99046977765ab5bdf683b435f01 encoding=utf-8>>>
# Open Questions: Преждевременное обрывание многошаговых агентных цепочек в `opencode-zen-bridge`

- `OPEN-01` | `МОЖНО ПРОДОЛЖИТЬ` | Влияет на: точный расчёт дельты проглоченных токенов (`SWALLOWED_TOKENS_MIN = 35`) в `_is_incomplete_tool_step` для разных моделей `opencode.ai/zen` (`glm-5.3-flash-free`, `kimi-k2.5`, `qwen3.6-plus`). Как проверено: по данным `~/.local/share/opencode/opencode.db` (`[F-08]`, `[F-09]`) установлено, что `tokens.output` в `opencode` включает `tokens.reasoning` (`output=506, reasoning=156` на Ходе 10 и `output=499, reasoning=366` на Ходе 12), поэтому для защиты коротких финальных ответов с ненулевым `reasoning` от ложного дозапроса при расчёте `swallowed_tokens` необходимо вычитать `reasoning_tokens` (`non_reasoning_output = max(0, output_tokens - reasoning_tokens)` при `output_tokens >= reasoning_tokens`), что сохраняет 100% детекцию на реальных сбоях (`350 - 46 = 304 >= 35` и `133 - 56 = 77 >= 35`) и исключает ложные срабатывания. Стоп-факторов для перехода к проектированию нет.
<<<ARTIFACT_END path="analysis/zen-step-interruption/open-questions.md" sha256=7b19740d89539d3fcd60fe153871e52e7b1db99046977765ab5bdf683b435f01>>>
<<<ARTIFACT path="analysis/zen-step-interruption/handoff-qa.md" bytes=5010 lines=21 sha256=4c16a8907ed920fb8225f300797cbec4ff6fe948ebc28c9ec3bb5c9288fd95fc encoding=utf-8>>>
# Handoff to QA / Verifier: Тестовые сценарии для `opencode-zen-bridge`

## 1. Позитивные сценарии (Positive)
- **QA-POS-01 (Парсинг `<tool_invoke>` и `<tool_call>`):** Проверить, что `ToolCallParser` (в потоковом режиме по чанкам) и `_parse_tool_call_blocks` (в пакетном режиме) одинаково извлекают `name` и `arguments` как из `<tool_invoke>...</tool_invoke>`, так и из `<tool_call>...</tool_call>`, а `_build_tool_Constraint` instrucтирует модель использовать `<tool_invoke>` (`[F-05]`, `[F-08]`).
- **QA-POS-02 (Маппинг встроенного тула `"shell"` OpenCode v2.1.2):** Проверить, что `NATIVE_TOOL_ALIASES` отображает `"shell"` в клиентский инструмент `Execute` / `Bash` / `run_command` (`[F-05]`).
- **QA-POS-03 (Успешный дозапрос при проглоченном `<tool_call>`):** Когда попытка 1 возвращает короткую преамбулу (`len=138..168`) и `step_finish` с `output_tokens=506, reasoning_tokens=156` (`non_reasoning_output=350`, дельта `>= 35`) без `tool_calls`, мост автоматически запускает попытку 2 с `_incomplete_tool_step_prompt` и возвращает клиенту `finish_reason="tool_calls"` без дублирования преамбулы в SSE (`[F-07]`, `[F-09]`).

## 2. Негативные сценарии и защита от ложных срабатываний (Negative)
- **QA-NEG-01 (Отсутствие ложного дозапроса на коротком финальном ответе с большим `reasoning`):** Когда модель возвращает короткий финальный ответ (`"Готово, все проверки пройдены."` или `"Ответ: 42."`) без признаков намерения вызвать инструмент, при этом `step_finish` содержит `tokens={"output": 400, "reasoning": 385}` (где `output` включает `reasoning`, `non_reasoning_output = 15 < 35`), `_is_incomplete_tool_step` ОБЯЗАН вернуть `False`, а мост — завершиться с `finish_reason="stop"` с первой попытки (`[F-09]`, `OPEN-01`).
- **QA-NEG-02 (Отсутствие ложного дозапроса на длинном структурированном ответе):** Если видимый текст длиннее `420` символов или содержит кодовые блоки ``` / таблицы `| col |` и заканчивается двоеточием в конце абзаца без проглоченных токенов и без маркера прерывания, `_is_incomplete_tool_step` возвращает `False`.

## 3. Граничные условия (Boundary)
- **QA-BND-01 (Порог `SWALLOWED_TOKENS_MIN = 35`):** Проверить границу `non_reasoning_output - visible_est == 34` (`False`, если текст — обычный ответ) и `== 35` (`True` при `len(visible_text) <= 600`) (`[F-02]`, `[F-08]`, `[F-09]`).
- **QA-BND-02 (Исчерпание `NATIVE_RETRY_LIMIT = 2`):** Если все `1 + NATIVE_RETRY_LIMIT` (3) попыток возвращают только преамбулу без `tool_calls`, мост прекращает ретраи и корректно возвращает накопленный текст с `finish_reason="stop"` (`[F-03]`, `[F-15]`).

## 4. Сценарии отказов (Failure Modes)
- **QA-FAIL-01 (Обрыв провайдера `ECONNRESET` посреди стрима):** При приходе события `etype == "error"` (`read ECONNRESET`) после частичного текста `Run._execute_once` и `Handler._stream_sse` немедленно останавливают `proc` (`_stop_proc`), отбрасывают синтетическое продолжение `"I was interrupted right before making tool calls."` (`_strip_interrupted_notice`) и выполняют дозапрос вызова тула (`[F-04]`, `[F-09]`, `[F-12]`).
- **QA-FAIL-02 (Таймаут и SSE keepalive при зависшем `stdout`):** При молчании `proc.stdout` дольше `KEEPALIVE_INTERVAL_S` (`15s`) в SSE-поток отправляется комментарий `: keepalive\n\n`, а при превышении `TIMEOUT_S` `_StdoutFeed` разблокирует ожидание и завершает процесс (`[F-06]`, `[F-15]`).

## 5. Регрессионный контур (Regression)
- **QA-REG-01:** Полный прогон существующего набора тестов моста `bridges/opencode-zen-bridge/tests/` (`350+` unit/property тестов) и корневого набора `tests/` (`219` тестов) без единого падения.
<<<ARTIFACT_END path="analysis/zen-step-interruption/handoff-qa.md" sha256=4c16a8907ed920fb8225f300797cbec4ff6fe948ebc28c9ec3bb5c9288fd95fc>>>


---
PANEL-NONCE: 27c77b61c74099c1
ARTIFACT-SHA256: 490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 27c77b61c74099c1» и «ARTIFACT-SHA256: 490bc2f863e75c451c0fcf4bbae710958f7941d3d2db09e8779f703fad6ca0b1».
