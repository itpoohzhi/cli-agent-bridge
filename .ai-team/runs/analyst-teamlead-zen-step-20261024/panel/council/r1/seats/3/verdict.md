PANEL-NONCE: 578bcebed148bfc8
ARTIFACT-SHA256: 90b1d66499dceadac24f7990423b4c53b2ebd5b23247aaf50efe187851598b9e
Канон прочитан: AGENTS.md, 430 строк. Проектные AGENTS.md, .agents/AGENTS.md и CLAUDE.md в этом ходе не читались.

Приёмка с места Визионера: реализация `v5` в `bridges/opencode-zen-bridge/server.py` держит утверждённые контракты, границы и путь эволюции. SHA-256 файла на диске совпадает с хешем брифа.

**Контракты.** CD-001 соблюдён: для GLM протокол в промпте идёт на `<tool_invoke>`, `ToolCallParser` и `_parse_tool_call_blocks` принимают оба тега, история переписывается до отправки, алиас `shell` есть в `NATIVE_TOOL_ALIASES`. Внешний ответ клиенту остаётся OpenAI `tool_calls`. CD-002(б) соблюдён: успешный дозапрос заканчивается `finish_reason=tool_calls`. CD-003 соблюдён: слот ждёт не дольше 15 с, 13-й ожидающий получает мгновенный 503 `overloaded` (`bridge busy` / `slot_overflow`), открытый breaker отвечает 503 `upstream circuit open` без spawn. Порт, `/health`, `/v1/models`, `/v1/chat/completions` не менялись.

Носитель keepalive (CD-002(а)) — пустая content-дельта раз в 15 с, а не SSE-комментарий `: keepalive`. Пустая дельта — штатный чанк OpenAI, к видимому тексту ничего не добавляет и как раз сбрасывает watchdog клиента, ради которого дельта и введена. Схема чанка, эндпоинты и смысл «поток жив, пока stdout молчит» сохраняются. Это не разрыв внешнего контракта.

**Целостность решений.** AD-001…AD-004 сходятся с кодом. Детектор выключен первой проверкой `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY` и не трогает regex; 400/401/403/404/422 не ретраятся; mid-stream error сразу вызывает `_stop_proc`; `reasoning_tokens` вычитаются из output. Потолок `MAX_TOTAL_SPAWNS=3` общий для cli-failure, unmapped и incomplete step. Full Jitter: retry 1 → U(0, 1.0), retry 2 → U(0, 2.0). Несовпадение `dedup_prefix` отдаёт новый текст целиком и в SSE, и в JSON. `_StdoutFeed(maxsize=4096)` на `queue.Full` останавливает процесс. `_StartupGate` 5 с — fail-open. Token bucket 1.0/с не списывает токен, если ожидание длиннее бюджета. Retry budget 6 / +0.20 / +0.05. Breaker: 5 отказов, cooldown U(0.8, 1.2)×10 с, в HALF_OPEN одна проба. Парсер и детектор не зависят от proc и сокета; транспорт вызывает их, обратной зависимости нет.

Две более узкие формулы не ломают утверждённые числовые последствия. Оценка видимых токенов — `max(len//2, оценка по словам)`: для текста 168 символов и non-reasoning 133 остаётся 49 ≥ 35; для 138 символов и 350 — 281 ≥ 35. «Ответ: 42:» и «Итог проверки:» дают сигнал 0. Короткая преамбула без `:`/`...`/`…` дополнительно требует имя инструмента запроса; признак 5 по-прежнему требует глагол намерения.

**Эволюция и наблюдаемость.** Откат детектора — env `OPENCODE_ZEN_BRIDGE_STEP_RECOVERY=0` без выключения unmapped-ретрая; миграций данных нет; константы переопределяются env. `do_POST` в `finally` пишет одну строку `O-EXIT/v1` с `mode`, `model`, `status`, `exit_reason`, `rc`, `total_spawns`, `retries`, `signal`, `tools`, `out_chars`, `duration_s`. Поле `signal` закрывает отложенную наблюдаемость детектора. Выходы, названные в O-EXIT/v1 (401, 400, 404, 503 слота и breaker, 502, успех stream/json, timeout, client_gone), размечены и покрыты тестами. Успешный запрос после транзиентного обрыва не открывает breaker.

FINDINGS: NONE
VERDICT: ACCEPT