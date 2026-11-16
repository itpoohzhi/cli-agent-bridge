# HANDOFF: Универсальный Resident Worker Pool в `core/` (`cli-agent-bridge`) + тонкие stdio-адаптеры

**Дата фиксации:** 2026-11-16 08:50 MSK  
**Репозиторий проекта:** `/Users/aazhiry1/work/src/cli-agent-bridge`  
**Выбранное владельцем направление:** **Путь 2** — обобщить резидентный пул и управление горячими сессиями в универсальном слое `core/` с тонкими адаптерами/профилями протоколов (строго в рамках универсализма, без заточки `core/` под `agy`).  
**Артефакты предыдущего прогона (замеры и аудит):** `/tmp/cel-runs/deepseek-bridge-vs-desktop/` (`bench_measurements.log`, `bench_results.json`, `analyst_report_v2.md`, `loop_verdicts_v2.json`).

---

## 1. Суть проблемы и эмпирические замеры на стенде

При работе с моделями Antigravity (`agy`) через универсальный мост (`cli-agent-bridge :9882` -> `PassthroughAdapter` -> `bridges/agy-bridge :9887` -> `agy-cli.sh` -> `agy.real`) наблюдалась сильная задержка по сравнению с `Antigravity.app` и первоначальным замыслом моста (in-memory ускоритель с горячими сессиями).

### Живые замеры (`/tmp/cel-runs/deepseek-bridge-vs-desktop/bench_measurements.log`, модель `gemini-3.8-flash`, effort `low`)

| Режим | Прогон / Ход | TTFT (с) | Общее время (с) | Вывод |
| :--- | :--- | :---: | :---: | :--- |
| Холодный запуск (`spawn` на ход + `_kill_group`) | Прогон 1 | 2.80 | 6.26 | Детерминированный оверхед на каждый ход |
| Холодный запуск (`spawn` на ход + `_kill_group`) | Прогон 2 | 2.37 | 5.97 | Среднее TTFT = **2.585 с**, Total = **6.115 с** |
| Resident (`agy.real --input-format stream-json --output-format stream-json`) | Ход 1 (прогрев) | 2.57 | 5.37 | Однократная инициализация |
| Resident (`agy.real --input-format stream-json --output-format stream-json`) | **Ход 2 (горячий in-memory)** | **0.341** | **2.85** | **TTFT быстрее в ~7.6x**, **Total быстрее в ~2.15x** |

### Что выяснено по коду и CLI
1. **`agy.real` уже умеет работать резидентно** (`~/.local/bin/agy.real --help`):
   - `--input-format stream-json --output-format stream-json`: *«stream-json reads one NDJSON message per line from stdin and runs a turn for each; it requires --output-format stream-json»*.
   - `acp --stdio --process-per-session` (*Agent Client Protocol*, JSON-RPC 2.0 stdio-сервер со штатной отменой `session/cancel` и флагами `--worker`, `--process-per-session`).
2. **Почему сейчас медленно:**
   - `bridges/agy-bridge/server.py` на каждый HTTP-запрос спавнит `agy-cli.sh` -> `agy.real` (186 МБ), а в конце хода вызывает `ProcessSupervisor.kill_group(proc)` (`agy_runtime/process_supervisor.py`), уничтожая прогретый Go-рантайм, открытый HTTP/2 TLS-пул к CloudCode и состояние сессии в RAM.
3. **Что уже есть в `cli-agent-bridge` (`AGENTS.md` и `core/`):**
   - В `AGENTS.md` прописан жёсткий инвариант: `core/` и `server.py` полностью **агент-агностичны**; адаптеры (`adapters/`) — только тонкие трансляторы транспорта под единым контрактом `BackendAdapter` ([core/backend_adapter.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/backend_adapter.py)).
   - В [adapters/__init__.py](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/__init__.py) сейчас только `droid` (`DroidAdapter`), `muse` (`MuseAdapter`) и `passthrough` (`PassthroughAdapter`).
   - В `core/backend_adapter.py` уже заложен контракт `SESSIONS_RESIDENT = "resident"` и ключи каталога `"resident"`, `"pool_size"`.
   - Логика резидентных процессов (`hot | restore | rebase | cold`, idle-revive, проверка префикса истории `HistoryPrefixGuard` в `core/turn_session_manager.py`) сейчас фактически живёт в `server.py` под `DroidAdapter`, а остальные CLI-агенты (`agy`, `claude-p` и др.) работают через HTTP-прокси `PassthroughAdapter` на отдельные мосты в `bridges/*`.

---

## 2. Рассмотренные архитектурные варианты

### Вариант 1 (Альтернатива — локальный в `bridges/agy-bridge`)
- Оставить `:9882` и `PassthroughAdapter` без архитектурных изменений (максимум — общий HTTP keep-alive / UDS в `PassthroughAdapter`).
- Перевести только `bridges/agy-bridge` (`:9887`) на `AgySessionPool` без `_kill_group` после каждого хода.
- **Плюсы:** минимальный объём правок, полная изоляция специфики `agy`.
- **Минусы:** дублирование логики пула/LRU/TTL/lifecycle в каждом отдельном `*-bridge`; сохраняются отдельные HTTP-демоны под каждый CLI.

### Вариант 2 (ВЫБРАН ВЛАДЕЛЬЦЕМ — Универсальный Resident Pool в `core/` + тонкие адаптеры)
- **Принцип:** не затачивать `core/` или `server.py` под `agy`, а **обобщить резидентный пул и сессионную машину на уровне `core/`**, чтобы любой CLI-агент с поддержкой потокового `stdio` (`stream-json`, `stream-jsonrpc`, `ACP`) подключался как тонкий профиль/адаптер под единым контрактом `BackendAdapter(SESSIONS_RESIDENT)`.
- **Что нужно спроектировать и сделать:**
  1. **Универсальный `ResidentProcessPool` / `StdioSessionManager` в `core/`:**
     - Обобщить управление жизненным циклом долгоживущего stdio-процесса (выделив/унифицировав общую часть, которая сейчас в `server.py` обслуживает только `droid`): состояния `STARTING | IDLE | BUSY | DRAINING | DEAD`, `turn_lock`, чтение `stdout` фоновым reader-насосом без закрытия `stdin`, детекция границы хода через предикат/драйвер протокола, привязка к `session_id` и проверка префикса истории (`HistoryPrefixGuard` / `hot | restore | rebase | cold`, stateful delta routing).
     - Универсальное управление ресурсами (без хардкода — всё через конфиг/env по `AGENTS.md` §4): `pool_size` / `max_resident_workers`, `prewarm_workers`, `idle_ttl_s`, `lru_eviction`, контроль `max_rss_mb` / `max_turns` с graceful recycle, корректная обработка отмены (`SIGINT` или протокольный `cancel`) и `shutdown_all()`.
     - Небуферизованный I/O для пайпов (`bufsize=0`, `PYTHONUNBUFFERED=1`), `TCP_NODELAY` на сетевых сокетах фасада и отключение буферизации SSE.
  2. **Тонкие адаптеры/профили протоколов в `adapters/`:**
     - Единый универсальный адаптер для NDJSON stdio-агентов (например, `StdioResidentAdapter` или семейство тонких профилей поверх общего `BackendAdapter`), где конкретный агент (`agy`, `claude-p`, `codex` и др.) описывает только:
       * команду запуска и env/обёртку (для `agy` — `agy.real --input-format stream-json --output-format stream-json ...` с прокси `:10820` и generation guard);
       * сериализацию входящего хода в строку NDJSON и условие конца хода (например, `type == "result"`);
       * трансляцию входящих событий в единые `TurnEvent` ядра (`core/backend_adapter.py`);
       * изолированные расширения (если нужны как доказанное исключение по `AGENTS.md`, например чтение reasoning из SQLite для `agy` или в перспективе `ACP` JSON-RPC 2.0 драйвер с `session/cancel`).
     - Важно: `DroidAdapter` не сломать по контракту (ADR-0001, байт-в-байт поведение), либо мигрировать аккуратно/поэтапно, не нарушая существующих тестов.
     - `PassthroughAdapter` сохранить для внешних HTTP-мостов (добавив общий keep-alive пул, если требуется по месту).
  3. **Валидация и приёмка по регламенту `cli-agent-bridge`:**
     - Юнит- и E2E-тесты: `pytest tests/ -v`, `tests/test_agy_bridge_resilience.py`, `tests/test_stream_formatting_and_subagents.py`.
     - Смоук-раннер L3: `scripts/smoke_models.py --dry-run` и `--live`.
     - Живой бенчмарк до/после через `:9882` (проверка неизменности PID на ходах 1..N, TTFT < 450 мс на горячих ходах, параллельные сессии, отмена/таймауты без зомби-процессов).

---

## 3. Процесс работы в новой сессии

Работать строго по канону `~/Мой диск/Context/AGENTS.md` и `~/Мой диск/skils/cel/SKILL.md`:
1. Открыть новый контур `cel` (`$RUN=/tmp/cel-runs/universal-resident-pool/`).
2. Провести этап проектирования (`analyst-teamlead` / `architect-software-product` -> Совет Тимлидов `teamlead-gate` по `launch_seat.py` + `verify_panel_proof.py`) до написания кода.
3. Реализацию вести строго через `Coder` (Оркестратор ≠ Кодер), затем `Reviewer` / тесты L1-L3 + приёмка Совета Тимлидов и сдача тяжёлым путём с живыми замерами.

---

## 4. Готовый промпт для старта в сессии в папке проекта

```text
Изучи HANDOFF_RESIDENT_POOL_ARCHITECTURE.md в корне проекта cli-agent-bridge и AGENTS.md.
Я выбираю Путь 2: обобщить резидентный пул и управление горячими сессиями в универсальном слое core/ так, чтобы любой CLI-агент с потоковым stdio (stream-json, stream-jsonrpc, ACP) мог работать in-memory через тонкий адаптер/профиль протокола без заточки core/ под конкретного агента (и не ломая существующий DroidAdapter и PassthroughAdapter).

Проведи работу строго по канону (cel + ai-sdlc / architect -> Совет Тимлидов -> Coder -> тесты L1/L2/L3 + живые замеры тяжёлым путём):
1. Изучи существующую резидентную логику (server.py, adapters/droid_adapter.py, core/backend_adapter.py, core/turn_session_manager.py, bridges/agy-bridge/ и agy_runtime/).
2. Спроектируй универсальный ResidentProcessPool / StdioSessionManager в core/ и контракт тонких протокол-драйверов для адаптеров (с переключением agy на прямой резидентный stdio-адаптер как первого потребителя наряду с сохранением совместимости для остальных агентов).
3. Проведи архитектурный Совет Тимлидов, получи ACCEPT, реализуй через Coder, прогони тесты (pytest tests/ -v, resilience, stream formatting, smoke_models) и сдай результат с реальными замерами TTFT (холодный ход vs горячие ходы 2+ при неизменном PID через :9882).
```
