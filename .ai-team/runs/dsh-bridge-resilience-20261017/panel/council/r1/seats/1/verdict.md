PANEL-NONCE: 02395c04abace879
ARTIFACT-SHA256: c4e4328ceba15cc6ac0d0c3052d38ad261d580a5f52156fc76dd2d9a5ba8079e

Подтверждаю: общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком до маркера `<!-- КАНОН-КОНЕЦ -->`; проектные артефакты и спецификации в рабочей папке (`/Users/aazhiry1/work/src/cli-agent-bridge`) изучены.

# Кодовый Совет Тимлидов (COUNCIL-ACCEPT, R1, место k=1) — Шляпа: Скептик

## Обзор со шляпой Скептика (краевые случаи, гонки, FD, безопасность, тайминги)

Проведена ревизия пакета [code-review-package.md](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/code-review-package.md), архитектурной спецификации [arch-spec.md](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md), [ADR-0005](file:///Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0005-resilient-hub-lifecycle-and-detached-turns.md) и исходного кода ключевых модулей:

1. **Утечки файловых дескрипторов и памяти (`TurnBuffer`, `ProcessWatchdog`, `MuseAdapter`):**
   - В [`_atomic_write_json_0600`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L783-L812) дескриптор `tempfile.mkstemp` передаётся в контекстный менеджер `with os.fdopen(fd, "wb")`, закрывающий FD при выходе, а блок `except BaseException:` гарантированно удаляет временный файл `tmp_path.unlink(missing_ok=True)`.
   - В [`MuseAdapter._run_exec`](file:///Users/aazhiry1/work/src/cli-agent-bridge/adapters/muse_adapter.py#L611-L648) дескрипторы двух пайпов рукопожатия (`ready_r`, `ready_w`, `gate_r`, `gate_w`) отслеживаются в `pipe_fds` и гарантированно закрываются как на штатном пути, так и в блоке `finally`.
   - В [`ProcessWatchdog._run_ps`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L148-L155) используется `subprocess.run(..., capture_output=True, timeout=self.ps_timeout_s)`, корректно закрывающий пайпы дочернего `ps` даже при `TimeoutExpired`.
   - В [`TurnBuffer`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L438-L513) ограничены не только события кольца `_events` (`MAX_TURN_TEXT_BYTES = 10 MiB`), но и аккумуляторы `_reasoning_chunks` / `_content_chunks` через `_append_bounded_text`, а также глобальное число хранимых ходов (`MAX_BUFFERED_TURNS = 128`, `MAX_TURN_BUFFER_TOTAL_BYTES = 128 MiB`) в [`_enforce_memory_caps_locked`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1005-L1037).
2. **Fail-closed при сбое `ps` и защита от спящих потомков на Darwin (`core/watchdog.py`):**
   - В [`ProcessWatchdog.sample`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L221-L275) перехват `subprocess.TimeoutExpired`, `OSError` и `proc.returncode != 0` логирует `watchdog_ps_degraded` и возвращает [`WatchdogMetrics`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L78-L98) с `ps_degraded=True`, для которого свойство `has_progress` строго равно `False`. Таймер неактивности при падении `ps` не сбрасывается (fail-closed).
   - Спящий дочерний процесс (`sleep`) после первичной регистрации в `seen_desc` даёт `new_descendants = ()` и `cpu_delta = 0.0` ([`core/watchdog.py:310-316`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L310-L316)), поэтому по истечении `IDLE_TIMEOUT_S = 300.0` срабатывает `idle_timeout` ([`core/watchdog.py:437-440`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L437-L440)).
3. **Безопасность `turn_id` и изоляция владельца (`RW-002`, `RW-008`):**
   - Строгий шаблон `TURN_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")` в [`validate_turn_id`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L48-L95) исключает Path Traversal (`../`, `/`, null-байты) на всех маршрутах `/v1/turns/*` и заголовках `X-Turn-Id`.
   - Изоляция между токенами обеспечивается сверкой `owner_token_hash` в [`get_turn`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1086-L1105) и [`get_turn_snapshot`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1107-L1141) с возвратом `HTTP 403 Forbidden`.

---

## Оценка по 6 критериям рубрики

### 1. КОРРЕКТНОСТЬ
Все три директивы владельца и требования Архитектурного Совета (`RW-001`..`RW-010`, `FU-001`..`FU-004`) выполнены в точном соответствии с целевым дизайном:
- **Директива 1 & RW-001/RW-003/RW-004/RW-007:** Отвязка выполнения хода от клиентского сокета реализована в [`core/turn_session_manager.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1143-L1309), интеграция в [`server.py:5275-5375`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L5275-L5375) и [`bridges/muse-bridge/server.py:3691-3758`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3691-L3758). Детерминированный [`compute_turn_key`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L173-L197) включает `cwd`, `model`, `session_id` и SHA-256 канонического JSON всей истории `messages` (включая последнее сообщение), а [`create_or_attach_turn`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1206-L1227) дедуплицирует только активные ходы, позволяя кнопке Regenerate создавать новый ход для завершённых сессий. Явная отмена `POST /v1/turns/<id>/cancel` и `DELETE /v1/turns/<id>` ([`cancel_turn`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1330-L1381)) немедленно освобождает слот семафора через [`release_slot_once`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L724-L738) до ожидания завершения группы `SIGTERM -> 2s -> SIGKILL`.
- **Директива 2 & RW-006:** [`AdaptiveTimeoutController`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L332-L450) и [`ProcessWatchdog`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L100-L330) обеспечивают `IDLE_TIMEOUT_S = 300.0` с и `SAFETY_CAP_S = 3600.0` с (`FINISH_RESERVE_S = 35.0` с).
- **Директива 3:** Вся логика отказоустойчивости вынесена в общий слой `core/` без импорта `core.tool_emulation` в `core/turn_session_manager.py` ([`core/turn_session_manager.py:15-45`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L15-L45)).
- **RW-010:** Из `~/.dsh/profiles/web/cordis.patch.yml` удалена невалидная переменная `{{cwd}}`, что проверяется тестом [`tests/test_dsh_profile_config.py:8-16`](file:///Users/aazhiry1/work/src/cli-agent-bridge/tests/test_dsh_profile_config.py#L8-L16).

Критерий 1 — PASS

### 2. ПОЛНОТА
Обработаны пограничные сценарии жизненного цикла:
- Переполнение кольцевого буфера 10 МиБ отслеживается через `oldest_available_seq` в [`TurnBuffer.check_gap`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L576-L596) и возвращает `HTTP 410 Gone` с `code="GAP_DETECTED"`, `oldest_available_seq`, `last_seq` и `snapshot_url`.
- Неблокирующий обработчик сигналов [`HubLifecycleManager.handle_signal`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L212-L219) выставляет только `self.shutdown_requested.set()`, исключая дедлоки в главном потоке.
- *Некритичные замечания Скептика (рекомендации на follow-up, не блокируют merge):*
  1. В [`server.py:5235`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L5235) и [`bridges/muse-bridge/server.py:3602`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3602) заголовок резюмирования читается как `X-Resume-Turn-Id`, тогда как в [arch-spec.md:280](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-bridge-resilience-20261017/architecture/arch-spec.md#L280) и сообщении об ошибке [`core/turn_session_manager.py:1169`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L1169) указан `X-Turn-Resume-Id` (стоит поддержать оба варианта заголовка наряду с `extra_body.resume_turn_id`).
  2. При ответе `410 Gone` в [`server.py:4671-4673`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L4671-L4673) `oldest_available_seq` передаётся в JSON-теле `exc.to_http_payload()`, но одноимённый HTTP-заголовок `X-Oldest-Available-Seq` явно не выставляется.
  3. В [`bridges/muse-bridge/server.py:3547`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L3547) условие очистки в `finally` (`if self._active_managed_turn is not None and not self._detach_on_disconnect:`) лучше привести к виду из корневого `server.py:5369` (`if managed_turn is not None and not attached_existing and managed_turn.is_active:`), чтобы при раннем отказе `503 bridge busy` до старта процесса запись хода сразу закрывалась в `TurnSessionManager`.

Критерий 2 — PASS

### 3. РЕАЛИЗУЕМОСТЬ
Решение написано исключительно на стандартной библиотеке Python (`threading`, `queue`, `subprocess`, `signal`, `tempfile`, `hashlib`, `hmac`), не вводит внешних зависимостей и не требует дополнительных инфраструктурных сервисов.
- В [`bridges/muse-bridge/server.py:60-62`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L60-L62) добавлен bootstrap `_REPO_ROOT` в `sys.path` для импорта `core.*`.
- Все три подсистемы закрыты операционными kill-switch флагами окружения (`DSH_BRIDGE_DETACHED_ENABLED` / `BRIDGE_DETACHED_TURNS_ENABLED`, `DSH_BRIDGE_WATCHDOG_ENABLED` / `BRIDGE_ADAPTIVE_WATCHDOG_ENABLED`, `DSH_BRIDGE_DRAIN_ENABLED` / `BRIDGE_DRAIN_ON_SHUTDOWN`) в [`core/turn_session_manager.py:107-141`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L107-L141).

Критерий 3 — PASS

### 4. РИСКИ
Потокобезопасность и управление процессами проработаны тщательно:
- Доступ к структурам `TurnBuffer`, `ManagedTurn` и `TurnSessionManager` синхронизирован через `threading.RLock` и `threading.Condition` ([`core/turn_session_manager.py:404, 675, 872-873`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L872-L873)).
- Освобождение семафора защищено идемпотентным [`ManagedTurn.release_slot_once`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/turn_session_manager.py#L724-L738), что исключает `ValueError: Semaphore released too many times` при гонке между `cancel_turn` и штатным `finally` потока исполнения.
- *Замечание Скептика по безопасности и `reap_orphans_on_startup`:*
  - В [`core/lifecycle.py:374-380`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L374-L380) проверка `_matches_expected_command` ищет подстроку `token in out_lower` по множеству `KNOWN_CHILD_BINARIES`, содержащему `"sh"` — из-за чего любая команда с подстрокой `"sh"` (например, `/bin/zsh` или `ssh`) даст совпадение. Поскольку туда попадают только живые PGID из защищённого `0600` файла `children.json`, созданного самим мостом, риск в эксплуатации минимален, однако в будущем лучше сверять `Path(comm).name in KNOWN_CHILD_BINARIES`.
  - В [`bridges/muse-bridge/server.py:385-386`](file:///Users/aazhiry1/work/src/cli-agent-bridge/bridges/muse-bridge/server.py#L385-L386) функцию `_auth_ok` рекомендуется перевести на `hmac.compare_digest` по аналогии с [`server.py:588-600`](file:///Users/aazhiry1/work/src/cli-agent-bridge/server.py#L588-L600).

Критерий 4 — PASS

### 5. АЛЬТЕРНАТИВЫ
Выбранная архитектура (единые модули `core/turn_session_manager.py`, `core/watchdog.py`, `core/lifecycle.py` с in-memory кольцевым буфером 10 МиБ и атомарным дисковым снапшотом завершённого хода) значительно чище, надёжнее и проще в сопровождении, чем дублирование таймеров в каждом адаптере или внедрение внешнего брокера очередей (Redis/SQLite), которое нарушило бы инвариант нулевых внешних зависимостей проекта.

Критерий 5 — PASS

### 6. СООТВЕТСТВИЕ КОНТЕКСТУ
Изменения полностью сохраняют обратную совместимость внешнего контракта OpenAI Chat Completions (`/v1/chat/completions`, формат SSE-чанков, 7 канонических ключей `/health` в `server.py`, схему `fleet.json` с добавлением опциональных `idle_timeout_s` и `safety_cap_s` в [`BACKEND_KEYS`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/backend_adapter.py#L173-L186)). Все 15 новых модульных тестов и 208 существующих регрессионных тестов проходят без ошибок, `ruff check` чист.

Критерий 6 — PASS

---

## Сводка субрибрик

- `SUB architecture: PASS — Чистая декомпозиция в core/ (turn_session_manager, watchdog, lifecycle) без циклических импортов и без зависимости от core.tool_emulation.`
- `SUB security: PASS — Строгая валидация turn_id (^[a-zA-Z0-9_-]{1,64}$), изоляция по owner_token_hash (403), атомарная запись снапшотов 0600 в каталоги 0700 и редактирование секретов.`
- `SUB performance: PASS — Кольцевой буфер жёстко ограничен 10 МиБ на ход и 128 МиБ глобально, опрос ps раз в 5 с с таймаутом 2 с и неблокирующий перехват сигналов через threading.Event.`
- `SUB tests: PASS — 15 новых целевых автотестов в 5 модулях покрывают detached-выполнение, 410 GAP_DETECTED, cancel с идемпотентным возвратом слота, fail-closed watchdog, drain 503 и профиль DSH.`

VERDICT: ACCEPT
