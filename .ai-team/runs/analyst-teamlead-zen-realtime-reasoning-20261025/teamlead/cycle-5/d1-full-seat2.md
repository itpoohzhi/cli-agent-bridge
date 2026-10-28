PANEL-NONCE: 5f4c8610f7fae22d
ARTIFACT-SHA256: c9530b1b9b6113a97457c299f4970c7a2a5ad6a55605bbd243c97a09c5a85da4

AGREE F-001 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3552` — ветка `elif etype == "error"` пишет `error` / `transient_error` / `terminal="failed"` и делает `break`, не ставя `result["delivered"]`; `server.py:3563` так же ставит `exit_reason="timeout"` без `delivered`. `server.py:3309` и `server.py:3349` для `first_event_timeout` и обрыва тела prompt этот флаг ставят. Потребители `server.py:5619` и `server.py:6911` при `delivered=False` и отсутствии токенов возвращают fallback на `run`.
AGREE F-002 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6235` — legacy SSE сравнивает `now_s - attempt_start > max(float(FIRST_TOKEN_TIMEOUT_S), 120.0)`. Serve-путь `server.py:3314` сравнивает с сырым `FIRST_TOKEN_TIMEOUT_S`. Порог ниже 120 с, включая дефолт 60 с, на legacy не действует (REQ-007, AC-010).
AGREE F-003 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3235` — `sse_resp.readline()` без лимита; `server.py:2613` — `raw.extend(chunk)` без потолка тела. Приоритет non-blocking оставляю: это локальный serve моста, а не смена контракта; blocking-дыра доставки — F-001.
AGREE F-004 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:1949` — `isinstance(read_obj, int)` пропускает `bool`; для `input`/`output`/`reasoning` отсекается только `bool`, знак не проверяется. Накопление через `_as_int` обнуляет `bool`, отрицательные целые проходят. Приоритет non-blocking верный.
AGREE F-005 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3584`, `server.py:3595`, `server.py:3607` — два `join(0.5)`, затем interrupt и DELETE с `deadline=monotonic()+0.35`, и только потом `lease.cleanup()`. Спроектированная сумма с окнами SIGTERM/SIGKILL может превысить 7 с AC-011. Оставляю non-blocking: прошлый цикл понизил FU-006 до non-blocking; неограниченное капание `getresponse`/`read1` уже blocking в F-012 и этот фикс не отменяет.
AGREE F-013 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:3552` и `server.py:3556` — тот же выход `etype=="error"` без `delivered`; `server.py:5618` и `server.py:6911` уходят в `run`. Это тот же корень, что F-001; F-001 полнее, потому что покрывает и `timeout` на `server.py:3563`.
AGREE F-014 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:6231` и `server.py:6235` — тот же пол `120.0`, что F-002.
AGREE F-015 rev=1 — проверил: `bridges/opencode-zen-bridge/server.py:5094` — `on_idle` в JSON `Run.execute` ставит только `client_gone` и зовёт `_stop_proc`. Часов первого события, первого токена и паузы нет; `server.py:5147` классифицирует ошибку провайдера, не молчание. REQ-006/REQ-007 и AC-008..AC-010 не ограничены SSE. Тот же корень, что открытый F-008.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 закрыт для HTTP-статуса prompt и обрыва тела после заголовков (`server.py:3309`, `server.py:3349`), но не для SSE-ошибки выполнения и дедлайна попытки. F-001 и F-013: при `headers_at` и `session.execution.failed` либо `timeout` до токенов `delivered` остаётся False, и auto вызывает `run`. F-002 и F-014: legacy SSE глушит `FIRST_TOKEN_TIMEOUT_S` полом 120 с.
   СОВЕТЫ (при FAIL): на `server.py:3552` и `server.py:3563` ставить `result["delivered"]` из `prompt_status["headers_at"]` или уже отданных токенов; при истине — `serve-retry` через `allow_retry` либо терминальная ошибка, без `Run.execute`, `_spawn_with_stdin` и `record_success()` (`server.py:5619`, `server.py:6911`). На `server.py:6235` сравнивать ровно с `FIRST_TOKEN_TIMEOUT_S`. Оракулы: auto, stream и JSON, заголовки prompt 200, затем transient SSE-error и отдельно deadline-timeout; legacy SSE с порогом 0.8 с и событием без токена даёт `first_token_timeout`.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=RW-002, RW-003, RW-004 и FU-001..FU-004 остаются закрытыми. F-015: non-stream JSON не классифицирует `first_event_timeout`, `first_token_timeout` и `stall_timeout` и ждёт `TIMEOUT_S`. Открытый F-009: матрица `test_step_interruption.py` идёт через shebang fake-CLI и выбирает `run`, поэтому AC-016 и AC-017 на serve не доказаны целиком.
   СОВЕТЫ (при FAIL): в `Run.execute` завести те же три watchdog и убийство группы внутри `MAX_TOTAL_SPAWNS` (`server.py:5094`). Прогнать сценарии AC-016 на serve-дельтах и сравнить unmapped-повтор и `finish_reason` с legacy (F-009).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Транспорт на stdlib и `opencode` v2.1.2 осуществим, kill-switch по умолчанию `run`. Выкат блокируют открытые F-010 и F-011: `_spawn_serve` (`server.py:2731`) не принимает deadline и отмену и держит свои окна handshake/listener; дренаж stderr родителя стартует только после проверки listener (`server.py:2844`), а helper пишет stderr синхронно (`server.py:181`).
   СОВЕТЫ (при FAIL): протащить остаток дедлайна и отмену через startup и подписку `/api/event`; отмена не должна становиться `ServeUnavailable` с fallback. Запускать дренаж stderr сразу после `Popen` и ограничить его байтами. Оракул: несколько MiB до bind, в том числе без LF; истёкший deadline не запускает helper.

4. РИСКИ: VERDICT=FAIL
   WHY=L2 зелёный: 451 pytest, 451 unittest, корневой прогон и обратный порядок, RED sensitivity rc=1. Это не закрывает F-001: второй вызов Zen после уже принятого prompt. Открытый F-012: `getresponse` (`server.py:2604`) и `read1` (`server.py:2610`) могут удерживать cleanup дольше абсолютного deadline, и `lease.cleanup` не достигается. F-003, F-004 и F-005 оставляю non-blocking. Секреты, allowlist и маскирование по проверенным оракулам держатся.
   СОВЕТЫ (при FAIL): закрыть F-001 регрессией без второго upstream. Прерывать текущую HTTP-фазу по deadline и в cleanup не читать ненужное тело; группа исчезает в пределах AC-011, слот возвращается (F-012). VER-006/VER-007 остаются DEFERRED_L3 до ACCEPT.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на попытку с откатом на `run` до барьера доставки закрывает отсутствие дельт у `opencode run` и сохраняет ротацию IP. Прямой Zen HTTP по фактам анализа не доказан, общий демон её ломает. Дефекты F-001..F-015 чинятся внутри этой схемы; переписывания транспорта не требуется.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Конверт удержан: три разрешённых файла, замороженные `_run_env` и Google-срез, публичные пути и форма SSE, без чужих KEY и без внешних зависимостей. Не выполнен прямой пункт feature.md: таймаут на каждом шаге цепочки, включая cleanup. F-010 не передаёт дедлайн в старт, F-012 не гарантирует абсолютный предел HTTP-фазы до `killpg`.
   СОВЕТЫ (при FAIL): протащить `remaining deadline` в `_spawn_serve` и в `_serve_http` так, чтобы фаза обрывалась по бюджету, а не только проверялась между блокирующими `recv`. Повторить clean-room L2 после правки.

POSITIONS: 8/8
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
