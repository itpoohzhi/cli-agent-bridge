# ADR 0012: Универсальное извлечение и сквозной live-стриминг процесса мышления модели Muse в cli-agent-bridge

## Статус
ACCEPTED Коллегией Архитекторов (ревизия A7, единогласный вердикт ACCEPT 3/3: Google/gemini-4-argon-high, Meta/muse-wonder-full-1.0, OpenAI/gpt-6.1-sol-high; Proof-of-Launch PASS).

## Контекст и проблема
При взаимодействии с моделями семейства Meta Muse (`muse-wonder-full-1.0`, `muse-spark-1.3` и др.) в клиентах мульти-бинарного хаба `cli-agent-bridge` (включая DeepSeek Harness и веб-клиенты с поддержкой OpenAI SSE) пользователи сталкиваются с «эффектом черной дыры»: во время глубоких рассуждений модели (thinking phase) экран пуст или задерживается на десятки секунд/минут.

### Факты исследования (Evidence Ledger):
1. **F-01:** Установлена актуальная версия агента `Muse Code 1.4.14 (1.4.14-R7309.1)` (`~/.local/bin/muse-bin-1.4.14-R7309.1`).
2. **F-02:** Обёртка `~/.config/muse-launch/muse-cli.sh` реализует обязательный прокси-контур (:10816, proxyrack) и очистку `META_API_KEY`. Любой запуск бинарника Muse обязан идти через обёртку.
3. **F-03:** В режиме `muse exec --json` бинарник возвращает лишь `run.output.delta` (готовый ответ) и `run.usage` (`reasoning_tokens`), но полностью скрывает текст и дельты мыслей.
4. **F-04:** В режиме `muse serve` (stdio JSON-RPC, протокол MSP v1) Muse непрерывно генерирует события `item/started`, `item/delta` (`summary.0..N`), `item/completed` для `kind: "reasoning"`, а также события вызова инструментов `kind: "toolCall"`.
5. **F-05:** В standalone-мосте `bridges/muse-bridge/server.py` уже реализован класс `ServeRun` (ADR 0003, ADR 0004), парсящий MSP.
6. **F-06:** В мульти-бинарном хабе `cli-agent-bridge` адаптер `adapters/muse_adapter.py` до сих пор использует только `muse exec --json` и `STREAMING_EMULATED`, `sse_writer` не передается, а `TurnResult.reasoning` возвращается пустым.
7. **F-07:** Фасад `server.py` мульти-бинарного хаба уже обладает развитой архитектурой стриминга `reasoning_content` (дельты `reasoning_delta` в SSE).

### Главный архитектурный принцип (`AGENTS.md`):
- Запрещено модифицировать или патчить вендорские бинарники и скрипты Muse (`~/.local/bin/muse`, `muse-cli.sh`).
- Все изменения реализуются строго на универсальном слое `cli-agent-bridge`.

---

## Решение владельца (Owner Directive OD-001)
- **OD-001 (2026-10-31 00:07 MSK):** Фичефлаг GigaRC не нужен: достаточно настройки в локальной конфигурации `fleet.json` (`backends.muse.options.streaming_mode: "serve"` vs `"exec"`). Задача касается модернизации нашего собственного универсального моста `cli-agent-bridge`.

---

## Согласованные Архитектурные Решения (Ревизия A7)

### AD-001. Выбор протокольного слоя: Нативный MSP v1 в выделенном модуле `adapters/muse_msp.py`
- **Решение:** Протокольная логика MSP v1 выносится в чистый модуль `adapters/muse_msp.py`. `adapters/muse_adapter.py` подключает его при `streaming_mode == "serve"`.
- **Обоснование:** Изолирует протокольный парсер от логики операционной системы и слотов, соблюдая принцип Vendor Zero-Touch.

### AD-002. Модель жизненного цикла: Строгий Per-Turn запуск по stdio
- **Решение:** Процесс `muse serve` запускается **строго на один ход** (per-turn) исключительно по `stdio` (stdin/stdout ndjson RPC, без открытия TCP-портов) внутри изолированного каталога `workspace/muse/turn-<uuid>/` (`0700`).
- **Обоснование:**
  - Сохранение инвариантов безопасности `RW-001..RW-011`.
  - Предотвращение зависания сетевых сокетов к прокси-контуру `:10816`.
  - Предотвращение утечек памяти и дублирования истории чата.
  - По завершении хода вся группа процессов безусловно уничтожается `os.killpg(proc.pid, signal.SIGKILL)`, а каталог хода удаляется в блоке `finally`.

### AD-003. Изоляция стриминга, емкость очереди и защита от Pipe-дедлоков (macOS 64 КБ)
- **Решение:**
  - Поток чтения `stdout` процесса `muse serve` развязан с `sse_writer` через ограниченную очередь ёмкостью `LIVE_QUEUE_CAPACITY = 1000` элементов и `LIVE_QUEUE_MAX_BYTES = 1 MiB`; дельты режутся на куски `LIVE_DELTA_MAX_BYTES = 8 KiB`.
  - Читатель `stdout` выполняет неблокирующий `put_nowait()`. При `queue.Full` выставляется `live_degraded = True`, live-дельта отбрасывается для сетевого сокета, но поток чтения stdout НИКОГДА не блокируется, гарантируя устранение 64 КБ pipe-дедлока ядра macOS.
  - При таймауте сетевой записи `LIVE_WRITE_TIMEOUT_S = 3.0s` также выставляется `live_degraded = True`.

### AD-004. Семантика дельт и санитизация маркеров инструментов
- **Решение:**
  - Дельты отслеживаются по составному ключу `(item_id, idx)`: в `sse_writer("reasoning", delta)` передается строго инкрементальный прирост.
  - События `item/started` и `item/completed` (`kind == "toolCall"`) транслируются в блок рассуждений в виде текстовых маркеров прогресса:
    `\n\n[Вызов инструмента: {safe_tool}]\n`
    `\n[Инструмент {safe_tool} завершён]\n`
  - Имя инструмента валидируется регулярным выражением `^[A-Za-z0-9_.:-]{1,64}$`, невалидные имена заменяются на `unknown_tool`. Аргументы и полезная нагрузка в текстовый маркер рассуждений не включаются.

### AD-005. Всегда активная аккумуляция рассуждений и лимит памяти `MAX_TURN_TEXT_BYTES`
- **Решение:**
  - Аккумуляция в `TurnResult.reasoning` ведётся ВСЕГДА — и при `stream: true`, и при `stream: false`.
  - Общий размер текста хода подчинен лимиту `MAX_TURN_TEXT_BYTES = 10 MiB` (RW-006). При исчерпании лимита reasoning усекается первым с маркером `\n[reasoning truncated: turn text budget reached]\n`, отдавая приоритет завершению ответа модели.
  - Фасад `server.py` пробрасывает `TurnResult.reasoning` в поле `message.reasoning_content` ответа `ChatCompletionResponse`.

### AD-006. Локальная конфигурация в `fleet.json` (OD-001)
- **Решение:**
  - Режим управляется параметром `backends.muse.options.streaming_mode` в `fleet.json`.
  - По умолчанию (при отсутствии ключа) используется `"exec"` (`STREAMING_PSEUDO`) для обеспечения 100% обратной совместимости. Значение `"serve"` активирует нативный MSP v1 и стриминг мыслей (`STREAMING_NATIVE`).

### AD-007. EOF клиента делегирован TurnSessionManager
- **Решение:** адаптер не ведёт собственного флага мутаций и не решает об отмене. Обрыв сокета обрабатывается существующим автоматом `core/turn_session_manager.py` (`RUNNING_ATTACHED -> RUNNING_DETACHED`, ADR 0005): менеджер владеет ходом, применяет `TurnResult` к истории, держит сессионную блокировку и таймаут. Адаптер отключает live sink (`live_degraded = True`), дочитывает stdout до terminal и в `finally` выполняет `killpg` и удаление `turn-<uuid>`.
- **Обоснование:** наблюдение `item/started` не является барьером мутации (гонка, ложные срабатывания на read-only tools); единый владелец состояния исключает дублирование политики.

## План верификации (VER-001..VER-012)
- **VER-001:** Тест переключения режима в `fleet.json`: дефолт `exec`, явный `serve` (`tests/test_muse_adapter.py`).
- **VER-002:** Тест потокового разбора MSP v1 с эмуляцией mock stdio сервера и проверки инкрементальных дельт `(item_id, idx)` (`tests/test_muse_adapter.py`).
- **VER-003:** Тест генерации маркеров инструментов `[Вызов инструмента: ...]`, regex-санитизации и отсечения аргументов (`tests/test_muse_adapter.py`).
- **VER-004:** Тест аккумуляции рассуждений и лимита `MAX_TURN_TEXT_BYTES` с приоритетом ответа в обоих режимах стриминга (`tests/test_muse_adapter.py`, `tests/test_hub_integration.py`).
- **VER-005:** Тест backpressure: задержка `sse_writer` не вызывает дедлока pipe, выставляется `live_degraded = True` (`tests/test_muse_adapter.py`).
- **VER-006:** Тест очистки процессов: безусловный `os.killpg` и удаление каталога хода `turn-<uuid>` (`0700`) (`tests/test_muse_adapter.py`).
- **VER-007:** Тест переполнения очереди live sink: подача 2000 дельт при `LIVE_QUEUE_CAPACITY = 1000`, неблокирующий `put_nowait`, `live_degraded = True`, сохранение всех 2000 дельт в `TurnResult.reasoning` (`tests/test_muse_adapter.py`).
- **VER-008:** EOF клиента: `mark_detached`, адаптер не убивает процесс сам, live sink отключён, результат применяется один раз (`tests/test_muse_adapter.py`, `tests/test_turn_session_manager.py`).
- **VER-009:** Нарезка по границам кодовых точек UTF-8 и лимит размера дельты (`tests/test_muse_adapter.py`).
- **VER-010:** Устойчивость к stderr/stdin и запрет fallback на exec после начала вызова инструментов (`tests/test_muse_adapter.py`).
- **VER-011:** HTTP SSE: отсутствие повторов reasoning и проверка монотонности префикса при несовпадающем snapshot (`tests/test_muse_adapter.py`, `tests/test_hub_integration.py`).
- **VER-012:** Сериализация сокета sse_lock и барьер sink_closed (`tests/test_muse_adapter.py`).
