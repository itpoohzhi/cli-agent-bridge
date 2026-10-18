# 0005 — Сквозная отказоустойчивость общего слоя хаба: автономное доведение ходов (detached turns), адаптивный сторожевой таймер и плавный drain

## Status

Accepted (2026-10-17, ревизия a2 по замечаниям Архитектурного Совета RW-001..RW-010, FU-001..FU-004).
Формат: MADR-full / ADR-full.
Задача: `REQ-EYE-33873-RESILIENCE` (`EYE-33873`), Run ID: `dsh-bridge-resilience-20261017`, критичность: `S2`, профиль: `python-aisdlc-gcge`.
Архитектурный пакет: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/architecture-packet.json`.
Спецификация: `.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md`.
Расширяет: ADR 0001 (`0001-persistent-droid-bridge.md`), ADR 0002 (`0002-multi-binary-hub.md`), ADR 0004 (`0004-muse-live-streaming-all-steps.md`).

## Y-формулировка

В контексте мульти-бинарного хаба консольных агентов `cli-agent-bridge` (`server.py`, `core/`, `adapters/` и `bridges/muse-bridge/server.py`), обслуживающего клиент DeepSeek Harness (Desktop и Web), сталкиваясь с:
1. потерей многошаговых ходов при кратковременном разрыве клиентского TCP/SSE-соединения (переключение вкладки, сон ноутбука, перезагрузка UI) из-за принудительного вызова `_kill_current_run()` / `_kill_group()` на `client_gone` (`[F-10]`, `[F-12]`, `[F-34]`),
2. обрывом активных ходов с вызовами инструментов ровно на 1765-й секунде по слепому абсолютному дедлайну (`1800 - 35 с`) при живом и работающем дочернем процессе (`[F-16]`..`[F-25]`),
3. мгновенным уничтожением активных ходов при перезапуске моста через `launchctl` из-за отсутствия drain-режима и 5-секундного `ExitTimeOut` (`[F-01]`..`[F-09]`),
4. ошибкой старта сессии в веб-профиле DSH из-за незарегистрированной переменной `{{cwd}}` в `deployment:persona-suffix` (`[F-27]`..`[F-30]`),

мы решили:
1. Вынести управление жизненным циклом ходов, адаптивными таймаутами, сторожевым мониторингом процессов и плавной остановкой в **общий слой хаба** (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` и фасад `server.py`) без зависимости менеджера сессий от `core.tool_emulation`, обеспечив автоматическое разрешение импортов `core.*` в `bridges/muse-bridge/server.py` через `sys.path` bootstrap и `DSH_BRIDGE_ROOT`;
2. Отвязать выполнение хода модели от клиентского HTTP/SSE-сокета (**Detached Execution**): запретить убийство процесса модели при отсоединении клиента, доводить ход в фоне до естественного терминала, буферизовать поток событий (`kind: str` с passthrough неизвестных событий, SSE `id: <seq>`, `X-Turn-Id`) в кольцевом буфере `10 МиБ` (при вытеснении возвращать `410 Gone` с `GAP_DETECTED` и `X-Oldest-Available-Seq`) и на диске (`schema_version: "1.0"`, права `0600` в каталоге `0700`), а также предоставить явный эндпоинт отмены хода `POST /v1/turns/<turn_id>/cancel` (`DELETE /v1/turns/<turn_id>`) для немедленного гашения группы процессов (`SIGTERM` -> `2 с` -> `SIGKILL`) и освобождения слота семафора `MAX_CONCURRENT=2`;
3. Заменить слепой абсолютный дедлайн двухуровневым контроллером (**Adaptive Idle Timeout `300 с` + Safety Cap `3600 с` + `ProcessWatchdog`**), сбрасывающим таймер простоя **только** по событиям протокола (`reasoning`, `content`, `toolCall`), по положительному приросту CPU-времени (`cputime` delta в `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>`) или однократно при появлении нового дочернего PID (спящие процессы без прироста CPU таймер не сбрасывают; при сбое/таймауте `ps` действует fail-closed режим);
4. Реализовать **Graceful Shutdown & Drain** с неблокирующим обработчиком `SIGTERM`/`SIGINT` через `threading.Event` и выделенным фоновым потоком drain (новым запросам — `503 Retry-After: 5`, активным ходам — доведение до конца в окне `ExitTimeOut = 120 с` / `DRAIN_TIMEOUT_S = 110 с`, при таймауте — терминальный SSE error-чанк и `[DONE]`), дополнив старт хаба процедурой **Orphan Reaper** по реестру `children.json` и фичефлагами аварийного отключения (`DSH_BRIDGE_DETACHED_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED`);
5. Убрать `{{cwd}}` из секции `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml`, передавая рабочий каталог через `AGENTS.md` и окружение `DSH_CWD`,

чтобы исключить потерю вычислений, блокировку слотов семафора и оборванные стримы во всех бэкендах хаба (`droid`, `muse` и будущих адаптерах), принимая контролируемый расход памяти на буферизацию фоновых ходов (до 10 МиБ на ход, 128 МиБ глобально) и увеличение окна перезапуска `launchd` при наличии активных ходов до 120 секунд.

---

## Context

Расследование системного аналитика (`analysis/bridge-resilience/evidence-ledger.md`, факты `[F-01]`..`[F-34]`) подтвердило следующие факты:
- **`[F-01]`..`[F-09]`:** `bridges/muse-bridge/server.py` не перехватывает `SIGTERM` (`signal.signal` отсутствует), потоки `ThreadingHTTPServer` помечены `daemon_threads=True`, а `com.user.dsh-muse-bridge.plist` не задаёт `ExitTimeOut` (действует системный дефолт 5 с). В результате `launchctl kickstart -k` (инцидент `18:52:23`, `[F-10]`, `[F-11]`) мгновенно оборвал активный ход `01a14a8e` без записи `done`/`error` и без отправки финального кадра клиенту.
- **`[F-12]`, `[F-13]`, `[F-34]`:** Каждый запрос в `muse-bridge` порождает отдельную группу процессов `muse serve` (`start_new_session=True`) с `--no-session-log`. При любом разрыве клиентского сокета ход уничтожается, а следующий запрос открывает чистую сессию без сохранения прогресса. При этом в случае гибели самого моста по `SIGKILL` дочерние группы с `start_new_session=True` остаются сиротами.
- **`[F-16]`..`[F-26]`:** В `ServeRun.read_msg` и `MuseAdapter._run_exec` действовал только абсолютный дедлайн хода (`1800 - 35 = 1765 с`). Три боевых сбоя (`2026-10-16 22:58:26`, `2026-10-17 02:03:36`, `2026-10-17 14:06:27`) убили ходы ровно через 1765 с от старта, хотя дочерний процесс активно выполнял `toolCall` за 8 с, 16 с и 79 с до обрыва (`[F-24]`). Проверка живости ограничивалась `proc.poll()` без анализа CPU/I/O и дочерних PID (`[F-17]`), а записи `tool_item` в логе не имели `rid` запроса (`[F-24]`).
- **`[F-27]`..`[F-31]`:** В `~/.dsh/profiles/web/cordis.patch.yml:51-55` задан `suffix: Your working directory is {{cwd}}.`, который вызывает ошибку `unknown prompt variable "{{cwd}}" in section "deployment:persona-suffix"; registered variables: provider, model`.

---

## Decision Drivers

- **D1 (Надёжность стрима и сохранность вычислений):** Ход с вызовами инструментов должен доходить до `completion event` при рестарте моста и при временном отключении клиента (`[F-01]`..`[F-03]`, `[F-10]`, `[F-12]`).
- **D2 (Фоновая автономия хода и управляемая отмена):** Закрытие вкладки или кратковременный обрыв сети не должны убивать процесс модели (`[F-10]`, `[F-12]`, `[F-13]`, `[F-34]`), но явное нажатие Stop клиентом обязано немедленно завершать процессную группу и освобождать слот `MAX_CONCURRENT=2` (`RW-001`).
- **D3 (Адаптивность и точность таймаутов):** Активно работающий процесс не должен убиваться по слепому таймеру, но спящий процесс без прироста `cputime` не должен бесконечно продлевать `idle_timeout` (`RW-005`, `FU-004`).
- **D4 (Единообразие и безопасность в общем слое хаба):** Механизмы устойчивости должны жить в `core/` + `server.py` (ADR 0002), защищать эндпоинты `/v1/turns/*` Bearer-авторизацией, валидацией `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`) и правами `0600`/`0700` на дампы (`RW-002`).
- **D5 (Операционная безопасность, зачистка сирот и kill-switch):** Неблокирующий перехват сигналов (`RW-007`), уборка сирот при старте по `children.json` (`RW-004`), фичефлаги мгновенного отключения (`RW-009`) и чистый старт профиля DSH Web (`REQ-005`).

---

## Considered Options

### Вопрос 1: Где и как реализовать отказоустойчивость, фоновое доведение ходов и адаптивные таймауты?

- **Option A — Точечные патчи внутри каждого адаптера и отдельного `bridges/muse-bridge/server.py`:**
  - *Минусы:* Тройное дублирование многопоточного кода; расхождение поведения между `droid` и `muse`; нарушение ADR 0002 и директивы владельца №3.
- **Option B — Реализация в общем слое хаба (`core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` + фасад `server.py`) с переиспользованием в `muse-bridge` через `sys.path` bootstrap (Выбрано):**
  - *Плюсы:* Единая кодовая база и единые инварианты для всех бэкендов; чистая модульная граница без зависимости `TurnSessionManager` от `core.tool_emulation` (`FU-003`); прозрачный импорт `core.*` в `bridges/muse-bridge/server.py` через автодобавление корня `cli-agent-bridge` в `sys.path` и симлинк/переменную `DSH_BRIDGE_ROOT` (`RW-008`).
- **Option C — Внешний супервизор очереди и прокси-демон (Out-of-process Redis/SQLite broker):**
  - *Минусы:* Нарушает базовый инвариант проекта (zero external runtime dependencies, чистый Python stdlib, один процесс-хаб по ADR 0002).

### Вопрос 2: Поведение при разрыве клиентского соединения (`client_gone`), явной отмене и переполнении буфера

- **Option 2A — Немедленное убийство процесса (Status Quo):** *Отклонено:* приводит к потере 20–30 минут работы модели при любом переключении вкладки или сне ноутбука.
- **Option 2B — Detached Execution с кольцевым/дисковым буфером в `TurnSessionManager`, эндпоинтом отмены `/cancel` и `410 GAP_DETECTED` (Выбрано):**
  - При отсоединении сокета воркер хода продолжает работу в состоянии `RUNNING_DETACHED`, складывая события в `TurnBuffer` (`10 МиБ` на ход, `128 МиБ` глобально, снимок `workspace/state/turns/<turn_id>.json` со `schema_version: "1.0"` и правами `0600`).
  - При нажатии пользователем кнопки Stop вызывается `POST /v1/turns/<turn_id>/cancel` (или `DELETE /v1/turns/<turn_id>`), который переводит ход в `CANCELLED`, гасит группу `SIGTERM` -> `2 с` -> `SIGKILL` и немедленно освобождает слот `MAX_CONCURRENT=2` (`RW-001`).
  - При запросе клиентом `from_seq`, уже вытесненного из 10-мегабайтного кольцевого буфера, возвращается `HTTP 410 Gone` с кодом `GAP_DETECTED`, заголовком `X-Oldest-Available-Seq` и ссылкой на полный снимок состояния (`RW-006`).

### Вопрос 3: Механика таймаутов длительного хода и контроля активности

- **Option 3A — Только увеличенный абсолютный таймаут (3600 с):** *Отклонено:* зависший процесс удерживает слот 60 минут.
- **Option 3B — Сброс таймера при любом наличии дочернего процесса в `pgid`:** *Отклонено:* спящий потомок (`sleep`, `bash` в ожидании `stdin`) бесконечно сбрасывает `idle_timeout` до 3600 с (`RW-005`).
- **Option 3C — Адаптивный таймер неактивности (`IDLE_TIMEOUT_S = 300 с`) + `ProcessWatchdog` по приросту `cputime` и протокольным событиям + fail-closed `ps` + `SAFETY_CAP_S = 3600 с` (Выбрано):**
  - Таймер простоя сбрасывается только при поступлении событий протокола, при положительном приросте CPU-времени (`cputime` delta > 0) в `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>` или однократно в момент порождения нового дочернего PID. При сбое или таймауте `ps` (> `2 с`) действует fail-closed режим (таймер не сбрасывается).

---

## Decision Outcome

Выбрана комбинация **Option B + Option 2B + Option 3C** (решения `AD-001`..`AD-005`, сопоставленные с `REQ-001`..`REQ-005`):

1. **Модуль `core/turn_session_manager.py` (`AD-001`, `REQ-001`):**
   - Каждый ход получает валидируемый `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`) и детерминированный `turn_key = sha256(canonical_json([workspace, model_id, session_id_or_rid, digest_history_including_last_user_message]))` (`RW-003`). Автоматический re-attach при `POST /v1/chat/completions` без `X-Turn-Resume-Id` выполняется только к активным (нетерминальным) ходам, исключая ложную дедупликацию при перегенерации.
   - Колбэк `ctx.client_gone` возвращает `True` только при явной отмене хода (`POST /v1/turns/<turn_id>/cancel` / `DELETE /v1/turns/<turn_id>`) или истечении `DRAIN_TIMEOUT_S`, но никогда при разрыве TCP-сокета клиента.
   - При вызове `POST /v1/turns/<turn_id>/cancel` (или `DELETE /v1/turns/<turn_id>`) статус переходит в `CANCELLED`, группа `pgid` останавливается (`SIGTERM` -> `2 с` -> `SIGKILL`), слот семафора `MAX_CONCURRENT=2` немедленно освобождается, возвращается `200 {"ok": true, "turn_id": turn_id, "status": "cancelled"}` (`RW-001`).
   - `BufferedTurnEvent` использует открытый `kind: str` (passthrough неизвестных видов событий), SSE-ответы передают заголовок `X-Turn-Id` и поле `id: <seq>` в каждом кадре (`FU-002`), а дисковые снимки `workspace/state/turns/<turn_id>.json` маркируются `"schema_version": "1.0"` и создаются с правами `0600` в каталоге `0700` (`RW-002`, `RW-010`).
   - При вытеснении запрошенного `from_seq` из кольцевого буфера `10 МиБ` возвращается `HTTP 410 Gone` (`GAP_DETECTED`, `X-Oldest-Available-Seq`) со ссылкой на дамп состояния (`RW-006`).
   - Эндпоинты `/v1/turns/*` требуют проверки Bearer-токена и совпадения `owner_token_hash` (`RW-002`).

2. **Модуль `core/watchdog.py` (`AD-002`, `REQ-002`):**
   - `IDLE_TIMEOUT_S = 300 с` + `SAFETY_CAP_S = 3600 с` (с `FINISH_RESERVE_S = 35 с`).
   - `ProcessWatchdog` каждые `5 с` вызывает `ps -o pid=,ppid=,pgid=,stat=,cputime=,command= -g <pgid>` (таймаут `2.0 с`) и сбрасывает `idle_timeout` только при приросте `cputime` (`cpu_delta > 0`), при появлении нового дочернего PID или при событиях протокола (`RW-005`). Спящие процессы без прироста CPU таймер не сбрасывают; при ошибке/таймауте `ps` действует fail-closed режим (`FU-004`).
   - Все записи лога маркируются `rid=<id> turn_id=<id> pgid=<pgid>` с кодами причин `idle_timeout`, `absolute_cap`, `child_exited`, `drain_timeout`, `cancelled`.

3. **Общий слой хаба и поставка `core.*` (`AD-003`, `REQ-003`):**
   - Модули `core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` не зависят от `core.tool_emulation` (`FU-003`) и единообразно обслуживают `DroidAdapter` и `MuseAdapter`.
   - `bridges/muse-bridge/server.py` автоматически добавляет корень `cli-agent-bridge` в `sys.path` на старте (с поддержкой `DSH_BRIDGE_ROOT` и симлинка `core`), гарантируя доступность `core.*` в изолированном процессе (`RW-008`).

4. **Модуль `core/lifecycle.py`: Orphan Reaper, Неблокирующий Drain и Kill-Switch (`AD-004`, `REQ-004`):**
   - На старте хаба `HubLifecycleManager.reap_orphans_on_startup()` читает `workspace/state/children.json`, проверяет живые PID через `os.kill(pid, 0)` + имя команды в `ps` и уничтожает осиротевшие группы от упавших предыдущих инстансов (`SIGTERM` -> `SIGKILL`) (`RW-004`).
   - Обработчик `SIGTERM`/`SIGINT` в главном потоке только выставляет `threading.Event` (`shutdown_requested`) без захвата замков (`RW-007`). Процедура drain (`DRAIN_TIMEOUT_S = 110 с` при `ExitTimeOut = 120 с` в `launchd` plist) и `server.shutdown()` выполняется в выделенном фоновом потоке.
   - Фичефлаги `DSH_BRIDGE_DETACHED_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED` (по умолчанию `true`) позволяют оперативно отключить любой из новых механизмов без отката кода (`RW-009`).

5. **Исправление профиля DSH (`AD-005`, `REQ-005`):**
   - Из секции `deployment:persona-suffix` в `~/.dsh/profiles/web/cordis.patch.yml` удаляется `suffix: Your working directory is {{cwd}}.`. Контекст рабочей директории передаётся через `AGENTS.md` проекта и переменную окружения `DSH_CWD`.

---

## Pros and Cons of the Consequences

### Положительные последствия (Pros)
- **Нулевая потеря ходов и мгновенное освобождение слотов по Stop (QS-2, RW-001):** Разрыв сети не убивает ход, а нажатие Stop в UI вызывает `/v1/turns/<id>/cancel` и сразу освобождает слот `MAX_CONCURRENT=2`.
- **Точное детектирование как живых инструментов, так и зависших `sleep`-процессов (QS-3, RW-005):** Активные инструменты работают до `3600 с`, а спящие без CPU процессы и зависания прерываются за `300 с`.
- **Защита от сирот, дедлоков сигналов и уязвимостей доступа (RW-002, RW-004, RW-007):** Неблокирующий сигнальный цикл исключает дедлок в `serve_forever`, orphan reaper очищает зависшие группы при рестарте после `SIGKILL`, а `turn_id` regex + Bearer auth + `0600` защищают данные ходов.
- **Безопасный роллаут с kill-switch (RW-009):** Любую из трёх подсистем можно отключить переменной окружения за секунды.

### Отрицательные последствия и риски (Cons & Mitigations)
- **Вытеснение ранних чанков при ответе > 10 МиБ:** *Митигация:* честный ответ `410 Gone` (`GAP_DETECTED`, `X-Oldest-Available-Seq`) со ссылкой на полный агрегированный снимок `GET /v1/turns/<turn_id>` (`RW-006`).
- **Задержка рестарта сервиса при активном ходе:** *Митигация:* новые запросы сразу получают `503 Retry-After: 5`, а по истечении 110 с гарантирован чистый выход до прихода `SIGKILL` от `launchd` (120 с).

---

## Validation

Архитектурные инварианты и сценарии качества `QS-1`..`QS-6` проверяются автоматизированным набором тестов (`verification_surface` в `architecture-packet.json`):
1. `pytest tests/test_detached_turn_execution.py -q` — проверка detached-выполнения, явной отмены `POST /v1/turns/<id>/cancel` с освобождением слота, точного `turn_key` при перегенерации, `410 GAP_DETECTED`, валидации `turn_id` (`^[a-zA-Z0-9_-]{1,64}$`), Bearer-авторизации, прав `0600`/`0700`, `schema_version: "1.0"` и passthrough неизвестных `kind` (`REQ-001`, `AD-001`, `RW-001`..`RW-003`, `RW-006`, `RW-010`, `FU-002`).
2. `pytest tests/test_adaptive_idle_watchdog.py -q` — проверка сброса `idle_timeout` только при приросте `cputime` или событиях протокола, срабатывания `idle_timeout` на спящем дочернем процессе без прироста CPU, fail-closed режима при сбое `ps`, потолка `absolute_cap` (3600 с) и маркировки логов `rid`/`turn_id` (`REQ-002`, `AD-002`, `RW-005`, `FU-004`).
3. `pytest tests/test_graceful_shutdown_drain.py -q` — проверка неблокирующего обработчика `SIGTERM`/`SIGINT` через `threading.Event`, фонового потока drain, зачистки сирот по `children.json` на старте (`orphan reaper`), ответа `503 Retry-After: 5`, фичефлагов `DSH_BRIDGE_*_ENABLED` и SSE keepalive `<= 10 с` (`REQ-004`, `AD-004`, `RW-004`, `RW-007`, `RW-009`).
4. `pytest tests/test_backend_contract.py tests/test_hub_integration.py -q` — проверка единого контракта `core/` для `DroidAdapter` и `MuseAdapter`, отсутствия импорта `core.tool_emulation` в `core/turn_session_manager.py` и загрузки `core.*` в `bridges/muse-bridge/server.py` (`REQ-003`, `AD-003`, `RW-008`, `FU-003`).
5. `pytest tests/test_dsh_profile_config.py -q` — проверка отсутствия `{{cwd}}` в `deployment:persona-suffix` профиля `~/.dsh/profiles/web/cordis.patch.yml` (`REQ-005`, `AD-005`).
