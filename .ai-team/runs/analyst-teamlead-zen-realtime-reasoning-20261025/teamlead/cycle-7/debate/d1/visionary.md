PANEL-NONCE: c62f1d0c7e63287f
ARTIFACT-SHA256: 5efd0909ef787d0125d23fe80ae837ad4d39d28975f2e455501c8f98b937f830

Канон прочитан: AGENTS.md, 430 строк. Корневого `AGENTS.md` в репозитории нет. Сужу заново по diff и строкам `server.py`.

AMEND F-001 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:6034,bridges/opencode-zen-bridge/server.py:7328; fix=разделить запрет fallback на run и допустимость serve-повтора ранней транзиентной ошибки без токенов — причина: приёмка RW-002 допускает терминальную ошибку, а не обязывает второй serve. NEW: server.py:6034 `if not _delivered_err and attempts.allow_retry("serve_transient_error")` против server.py:7328 `if not texts and attempts.allow_retry(...)` (JSON не требует `not delivered`). ARG: skeptic R1 «по правилам цикла N>=2 это non-blocking follow-up, не FAIL».

F-002 оставляю blocking. NEW: server.py:1785 `return value` отдаёт непарный surrogate; server.py:5800 `chunk.encode("utf-8")` и server.py:5692 `json.dumps(...).encode("utf-8")` не ловятся обработчиками server.py:7099 и server.py:5699 (`BrokenPipeError`/`ConnectionResetError`/`OSError`). `UnicodeEncodeError` — `ValueError`, не `OSError`.

AMEND F-003 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3818,bridges/opencode-zen-bridge/server.py:3829,bridges/opencode-zen-bridge/server.py:3309,bridges/opencode-zen-bridge/server.py:3316; fix=в окне закрытия шага собирать native-вызовы того же assistantMessageID, не только usage — причина: FU-001 и AC-016/AC-017 не требуют второго вызова одного сообщения. NEW: server.py:3818 `if emulate_tools:` затем `break` после `_drain_serve_step_usage`; дрейнер на server.py:3316 пропускает всё, кроме `session.step.ended`. ARG: skeptic R1 «остаточные наблюдения reverse-spec … не нарушают ни одного AC — … non-blocking follow-up, не FAIL».

AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:5904,bridges/opencode-zen-bridge/server.py:5905,bridges/opencode-zen-bridge/server.py:6536,bridges/opencode-zen-bridge/server.py:7194; fix=прерывать StartupGate и spawn limiter остатком дедлайна и client-gone как follow-up — причина: приёмка RW-004 покрывает HTTP-фазы, лимитер уже режется `attempts.remaining_s()`. NEW: server.py:5904 `gate.acquire()` затем server.py:5905 `min(SPAWN_WAIT_MAX_S, attempts.remaining_s())`. ARG: realist R1 «RW-004: стартовые фазы имеют собственные дедлайны».

F-005 оставляю blocking. NEW: server.py:2488 «Нейтральные итоги (таймаут …) не считаются», но server.py:5995 и server.py:7284 вызывают `attempts.attempt_done(True, False)` для `timeout`; `commit()` пишет `record_failure()`. Таблица server.py:1729–1736: deadline = fail_closed, оба инкремента 0. server.py:3382–3386 мапит `ServeStartupDeadlineExceeded` в `exit_reason="timeout"` и `delivered=True`.

F-006 оставляю non-blocking. RED `test_ac026` падает в `setUp` на `DYNAMIC_CONFIG_PATH` (`tests/test_realtime_reasoning.py:900`) до сокетных assertions; GREEN измеряет дельты.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=RW-001 и RW-002 в заявленном объёме закрыты: JSON сохраняет фазу watchdog и времена, `_is_delivered()` на server.py:3396–3402 включает `first_event_at`. F-001 больше не блокирует: после `session.execution.started` повтор serve не обязателен, терминальная ошибка допустима. Блокер — F-002: непарный surrogate проходит `_combine_surrogates` (server.py:1785) и рвёт UTF-8-сериализацию SSE (server.py:5800) и JSON `_send` (server.py:5692) вне классификации `invalid_serve_event`.
СОВЕТЫ (при FAIL): на границе serve отклонять непарный surrogate через `ServeProtocolError` до `.encode("utf-8")`; корректные пары оставлять без изменения текста; SSE и JSON должны давать cleanup и `O-EXIT` с `invalid_serve_event`.

2. ПОЛНОТА: VERDICT=PASS
WHY=REQ-001..REQ-020 и AC-001..AC-026 закрыты матрицей `verification-traceability.md`; VER-006/VER-007 законно `DEFERRED_L3`. FU-001 дочитывает usage одного native-шага. F-003 (второй вызов того же шага) и F-006 (качество RED) — non-blocking follow-up, AC не нарушают.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
WHY=RW-004 закрыт для HTTP-фаз: сторож только закрывает сокет, `_serve_http` проверяет фазу после `read1` и пропускает `settimeout` на закрытом fd. Транспорт по умолчанию выключен, откат — legacy `run`, зависимости вне stdlib не добавлены. F-004 — follow-up до spawn, не дыра фазовых бюджетов.

4. РИСКИ: VERDICT=FAIL
WHY=L2 зелёный: 471 passed, обратный порядок AC-023 rc=0, VER-004 errors=0, замороженные хэши совпали, RW-003 учитывает watchdog в breaker. Секреты, allowlist и `ask_reject` на месте. Блокер F-005: локальный `timeout` до prompt идёт в `attempt_done(True, False)` (server.py:5995, server.py:7284) и `commit()` открывает upstream breaker здорового провайдера, вопреки docstring server.py:2488 и строке таблицы server.py:1729–1736. F-002 — тот же класс необработанного падения на данных транспорта.
СОВЕТЫ (при FAIL): считать глобальный timeout нейтральным исходом: не вызывать `attempt_done(True, False)` и не делать `allow_retry` для дедлайна до prompt; `first_token_timeout` и `stall_timeout` по-прежнему учитывать как отказы upstream. Закрыть F-002 до сериализации.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=Короткоживущий `serve` с откатом на `run` закрывает реалтайм (RC-1) и сохраняет ротацию IP. Legacy-only реалтайма не даёт, прямой Zen не доказан, общий демон теряет ротацию. Дельта цикла 7 точечная, переписывания транспорта нет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
WHY=Ровно три файла конверта, `dependencies=[]`, публичная SSE-схема и порт сохранены, `[мост]` задан REQ-004/REQ-005, Google-direct и `_run_env` заморожены, `~/.dsh` до ACCEPT не мутировался. SEED RECHECK: `seed_hex=6ac3af291b0385acf0c4a6ed993775889c1291fbc8da93aa31a75ce5585f6e50`, `SEED=6ac3af29`; `ranked_order` по полному `seed_hex` совпал с манифестом r89: grok-4.7-high, muse-wonder-full-1.0, gemini-4-argon-high, gpt-6.1-sol-high, claude-sonnet-5-5-high.

POSITIONS: 0/0
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
