PANEL-NONCE: 43bf5503fa44d954
ARTIFACT-SHA256: c4e4328ceba15cc6ac0d0c3052d38ad261d580a5f52156fc76dd2d9a5ba8079e

Подтверждение чтения канона: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком (до маркера `<!-- КАНОН-КОНЕЦ -->`); в рабочей папке `.ai-team/runs/dsh-bridge-resilience-20261017/panel/council/r2` локальные проектные файлы правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) отсутствуют.

## Экспертное заключение судьи Кодового Совета Тимлидов (R2, k=1, шляпа: Реалист)

Как Тимлид в шляпе **Реалист**, я проверил соответствие представленного решения (`code-review-package.md`, `arch-spec.md`, `ADR-0005` и кода в рабочем дереве) трём ключевым директивам владельца, требованиям `RW-001..RW-010`, эксплуатационной надёжности в продакшене и отсутствию регрессий. Решение полностью готово к слиянию в `main`.

### 1. КОРРЕКТНОСТЬ
Все три ключевые директивы владельца и требования `RW-001..RW-010` реализованы в точном соответствии со спецификацией:
- **Директива 1 (Detached execution без убийства подпроцесса модели + явный cancel + Gap Replay):**
  - В [`core/turn_session_manager.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L646-L780) реализован `ManagedTurn` и потокобезопасный `TurnBuffer` ([`core/turn_session_manager.py:399-644`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L399-L644)) с кольцевым буфером 10 MiB (`MAX_TURN_TEXT_BYTES = 10 * 1024 * 1024`, строка 54) и глобальным потолком памяти 128 turns / 128 MiB (`MAX_ACTIVE_TURNS_IN_MEMORY = 128`, `MAX_GLOBAL_BUFFER_BYTES = 128 * 1024 * 1024`, строки 55–56; принудительное вытеснение терминальных ходов в `_enforce_memory_caps_locked`, строки 1005–1037).
  - При обрыве клиентского соединения (`BrokenPipeError` / `ConnectionResetError` / `TimeoutError`) как в [`server.py:3880-3921`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L3880-L3921), [`3991-3996`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L3991-L3996), [`4029-4034`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L4029-L4034), [`5649-5652`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L5649-L5652), [`5749-5753`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L5749-L5753), так и в [`bridges/muse-bridge/server.py:2805-2810`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L2805-L2810), [`3033-3041`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3033-L3041), [`3121-3129`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3121-L3129) вместо принудительного `_kill_current_run()` вызывается `TURN_MANAGER.mark_detached(turn_id)` ([`core/turn_session_manager.py:1298-1309`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1298-L1309)), переводящий ход в `RUNNING_DETACHED` с продолжением чтения stdout модели в `TurnBuffer`.
  - Явная отмена (`RW-001`) реализована в `TurnSessionManager.cancel_turn` ([`core/turn_session_manager.py:1330-1381`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1330-L1381)) и проброшена в HTTP-эндпоинты `POST /v1/turns/<id>/cancel` и `DELETE /v1/turns/<id>` ([`server.py:4774-4844`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L4774-L4844), [`4873-4911`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L4873-L4911), [`bridges/muse-bridge/server.py:3434-3470`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3434-L3470), [`3503-3526`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3503-L3526)): слот параллелизма освобождается немедленно через `turn.release_slot_once()` ([`core/turn_session_manager.py:724-738`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L724-L738)), а группа процессов PGID завершается каскадом `SIGTERM -> 2.0s -> SIGKILL` (`_terminate_pgid`, строки 1310–1329).
  - Детерминированный `turn_key` (`RW-003`) вычисляется в `compute_turn_key` ([`core/turn_session_manager.py:173-198`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L173-L198)) по SHA-256 от `[norm_cwd, norm_model, norm_session, messages_sha256]`, при этом дедупликация в `create_or_attach_turn` ([`core/turn_session_manager.py:1143-1278`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1143-L1278)) применяется строго к `ACTIVE_TURN_STATES`, сохраняя работоспособность Regenerate после завершения хода.
  - Вытеснение начала кольцевого буфера или рассинхрон `Last-Event-ID` / `offset` (`RW-004`, `RW-006`) строго перехватывается в `TurnBuffer.check_gap` ([`core/turn_session_manager.py:576-596`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L576-L596)) и `GapDetectedError` (строки 212–256), возвращая `HTTP 410 Gone` с JSON-ошибкой `GAP_DETECTED` ([`server.py:4666-4673`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L4666-L4673), [`bridges/muse-bridge/server.py:3348-3355`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3348-L3355)).
- **Директива 2 (Адаптивный таймаут 300с + потолок 3600с + Darwin `cputime` watchdog):**
  - В [`core/watchdog.py:27-31`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L27-L31) зафиксированы константы `IDLE_TIMEOUT_S = 300.0`, `SAFETY_CAP_S = 3600.0`, `FINISH_RESERVE_S = 35.0`, `WATCHDOG_INTERVAL_S = 5.0`, `PS_TIMEOUT_S = 2.0`.
  - Парсер `parse_cputime` ([`core/watchdog.py:43-75`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L43-L75)) корректно разбирает все форматы `ps` на macOS и Linux, а `WatchdogMetrics.has_progress` ([`core/watchdog.py:77-98`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L77-L98)) засчитывает прогресс только при `not ps_degraded and alive and (bool(new_descendants) or cpu_delta_s > 0.0)` (`RW-005`). Спящие дочерние процессы с нулевым приростом CPU не сбрасывают idle-таймер.
  - Дефолты `300` / `3600` синхронизированы во всех точках входа: [`adapters/muse_adapter.py:779`](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/muse_adapter.py#L779), [`adapters/droid_adapter.py:83-96`](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/droid_adapter.py#L83-L96), [`server.py:3829-3835`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L3829-L3835), [`bridges/muse-bridge/server.py:79-80`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L79-L80), [`162`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L162).
- **Директива 3 (Устойчивость в общем ядре `core/` + профили DSH):**
  - Вся логика сосредоточена в `core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` и `core/backend_adapter.py` (`TurnContext` на строках 77–109, `BACKEND_KEYS` на строках 173–186) и переиспользуется обоими серверами (`RW-008`).
  - В [`~/.dsh/profiles/web/cordis.patch.yml:51-55`](file:///Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml#L51-L55) и [`675-682`](file:///Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml#L675-L682) убрана подстановка `{{cwd}}` из `persona` и `deployment:persona-suffix`, что устраняет инвалидацию prompt-кэша при смене каталога (`RW-010`).

Критерий 1 — PASS

### 2. ПОЛНОТА
Решение закрывает все краевые случаи жизненного цикла и безопасности:
- **Безопасность файловой системы и секретов (`RW-002`):** `validate_turn_id` ([`core/turn_session_manager.py:93-95`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L93-L95)) проверяет идентификаторы по `^[a-zA-Z0-9_-]{1,64}$`; атомарная запись метаданных `_atomic_write_json_0600` ([`core/turn_session_manager.py:783-812`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L783-L812)) создаёт директории с правами `0700` и файлы с `0600`; функция `mask_secrets` ([`core/turn_session_manager.py:153-170`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L153-L170)) редактирует ключи и Bearer-токены до сохранения на диск.
- **Изоляция владельца хода (`RW-007`, `RW-008`):** сравнение токенов выполняется за константное время через `hmac.compare_digest` ([`core/turn_session_manager.py:144-150`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L144-L150), [`server.py:588-601`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L588-L601)); чужой `owner_token_hash` получает `HTTP 403 Forbidden`.
- **Fail-closed деградация `ps` (`FU-004`):** при `subprocess.TimeoutExpired`, `OSError` или ненулевом коде возврата `ProcessWatchdog.sample` ([`core/watchdog.py:221-275`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L221-L275)) выставляет `ps_degraded=True` и `has_progress=False`, гарантируя срабатывание `IDLE_TIMEOUT_S` и `SAFETY_CAP_S`.
- **Graceful Shutdown и Orphan Reaper (`RW-004`, `RW-007`):** обработчик сигнала `HubLifecycleManager.handle_signal` ([`core/lifecycle.py:212-220`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L212-L220)) неблокирующий и только взводит `self.shutdown_requested.set()`; `run_drain_once` ([`core/lifecycle.py:252-313`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L252-L313)) дренирует активные ходы до 110с (вписываясь в 120с `TimeoutStopSec` launchd/systemd) и отвечает `503 Service Unavailable` с `Retry-After: 5` на новые запросы; `reap_orphans_on_startup` ([`core/lifecycle.py:382-470`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L382-L470)) перед посылкой сигнала проверяет принадлежность PGID списку `KNOWN_CHILD_BINARIES` (строки 42–58), исключая убийство чужих процессов при переиспользовании PID ОС.

Критерий 2 — PASS

### 3. РЕАЛИЗУЕМОСТЬ
Решение спроектировано с прицелом на надёжную промышленную эксплуатацию:
- Используется исключительно стандартная библиотека Python (`threading`, `subprocess`, `os`, `signal`, `hashlib`, `hmac`, `tempfile`), без внешних зависимостей.
- Предусмотрены независимые feature-флаги аварийного отключения (`RW-009` в [`core/turn_session_manager.py:107-141`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L107-L141)): `BRIDGE_DETACHED_TURNS_ENABLED`, `BRIDGE_ADAPTIVE_WATCHDOG_ENABLED`, `BRIDGE_GRACEFUL_DRAIN_ENABLED`, позволяющие мгновенно переключить поведение в проде через env без отката релиза.
- Фоновый `cleanup_loop` ([`core/turn_session_manager.py:1049-1086`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1049-L1086)) автоматически очищает устаревшие файлы и завершённые ходы по TTL (`RETENTION_TTL_S = 1800.0`).

Критерий 3 — PASS

### 4. РИСКИ
Потенциальные риски многопоточности, утечек памяти и регрессий закрыты:
- **Concurrency safety:** все переходы состояний `ManagedTurn`, модификации `TurnBuffer` и индексные таблицы `TurnSessionManager` защищены `threading.Lock` и `threading.Condition` ([`core/turn_session_manager.py:415`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L415), [`676`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L676), [`891`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L891)). Освобождение слота идемпотентно через атомарный флаг `slot_released` под локом (`release_slot_once`, строки 724–738).
- **Тестовое покрытие:** 5 новых целевых тестовых модулей (15 тестов: [`tests/test_detached_turn_execution.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_detached_turn_execution.py), [`tests/test_adaptive_idle_watchdog.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_adaptive_idle_watchdog.py), [`tests/test_graceful_shutdown_drain.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_graceful_shutdown_drain.py), [`tests/test_turn_cancel_and_gap.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_turn_cancel_and_gap.py), [`tests/test_dsh_profile_config.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_dsh_profile_config.py)) проходят за 0.56s, а полный регрессионный прогон из 208 существующих тестов проходит без единого падения (`code-review-package.md:28-36`).

Критерий 4 — PASS

### 5. АЛЬТЕРНАТИВЫ
Выбранная архитектура in-process `TurnSessionManager` с `TurnBuffer` и лёгким JSON-журналом метаданных на диске оптимальна по соотношению надёжности и простоты:
- В отличие от внешних брокеров (Redis/SQLite WAL), решение не привносит сетевых точек отказа и блокировок БД.
- Чистота слоёв строго соблюдена (`FU-003`): `core/turn_session_manager.py` не импортирует `core.tool_emulation` или `http.server`; хук пост-обработки передаётся инверсией зависимостей через `post_process_fn`.

Критерий 5 — PASS

### 6. СООТВЕТСТВИЕ КОНТЕКСТУ
Все внешние контракты OpenAI-совместимого HTTP/SSE API (`/v1/chat/completions`, `/v1/responses`, `/v1/messages`, `/health`) полностью сохранены:
- При штатном соединении без обрыва клиент получает идентичный прежнему поток SSE/JSON с добавлением заголовка `X-Turn-Id` и поля `x_bridge_turn` в `/health` ([`core/turn_session_manager.py:1600-1632`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1600-L1632)).
- Оба моста (`server.py` и `bridges/muse-bridge/server.py`) используют единую реализацию из `core/`, исключая расхождение логики между адаптерами.

Критерий 6 — PASS

### Сводка субрибрик
- `SUB architecture: PASS — Чистое выделение core/turn_session_manager.py, core/watchdog.py и core/lifecycle.py без циклических зависимостей и с общим переиспользованием в обоих серверах.`
- `SUB security: PASS — Строгая валидация TURN_ID_RE, права 0600/0700, маскирование секретов, hmac.compare_digest для токенов и верификация PGID по KNOWN_CHILD_BINARIES.`
- `SUB performance: PASS — Опрос ps раз в 5с с 2с таймаутом и жёсткие лимиты памяти 10 MiB/turn и 128 MiB/global исключают утечки памяти и перегрузку CPU.`
- `SUB tests: PASS — 15 новых модульных и интеграционных автотестов покрывают все сценарии detached/cancel/gap/watchdog/drain/profile, 208 регрессионных тестов зелёные.`

VERDICT: ACCEPT
