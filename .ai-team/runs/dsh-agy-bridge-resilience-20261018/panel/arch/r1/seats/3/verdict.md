PANEL-NONCE: c183fb8e62ef40b9
ARTIFACT-SHA256: d570c88bc41324d1171a9d7a5bfa8c5db29a2e8573b9f0c2c219e98ac8dcab36

Прочитан общий канон `~/Мой диск/Context/AGENTS.md` целиком (до `<!-- КАНОН-КОНЕЦ -->`); проектные файлы правил (`AGENTS.md`, `.agents/AGENTS.md`, `CLAUDE.md`) в рабочей папке проверены (отсутствуют).

# Архитектурное ревью (Раунд R1, место k=3, шляпа: Визионер)

## Сводная оценка с позиции шляпы «Визионер»

Стратегический вектор решения верен: включение `bridges/agy-bridge` в монорепозиторий `cli-agent-bridge` и отказ от «слепого» 1800-секундного ожидания в пользу адаптивного сторожевого таймера с контролем процессного дерева `pgid` убирают технический долг изолированного скрипта (`[F-11]`) и выравнивают архитектуру мостов (`droid`, `muse`, `agy`, а в перспективе — `opencode` и `codex`).

Однако сверка оцениваемых артефактов ([`architecture-packet.json`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/architecture-packet.json), [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md), [`0007-agy-bridge-resilience-watchdog.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0007-agy-bridge-resilience-watchdog.md)) с фактическим кодом единого ядра [`core/watchdog.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py), [`core/lifecycle.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py), [`~/.dsh/bridges/agy-bridge/server.py`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py) и [`fetch_via_playwright.py`](file:///Users/aazhiry1/%D0%9C%D0%BE%D0%B9%20%D0%B4%D0%B8%D1%81%D0%BA/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py) выявила **критические расхождения контрактов**, которые приведут к немедленному падению в рантайме (`TypeError`, `AttributeError`, `ModuleNotFoundError`, `SystemExit(1)` и обрушению `asyncio.gather`) при реализации спецификации «как написано».

---

## Оценка по 6 критериям рубрики

### 1. Проблема и границы (`problem_and_boundaries`)
**Критерий 1 — NEEDS_WORK**

- **Что сделано хорошо:** Первопричина 30-минутного зависания DSH декомпозирована точно и полно (`[F-01]`..`[F-11]`): сочетание фоновой задачи `run_command` с `WaitMsBeforeAsync` в `agy` (`[F-03]`), зависшего TLS-сокета к `status.claude.com` без `AbortSignal.timeout` в Chromium (`[F-05]`..`[F-07]`) и слепого цикла `while True` на 1800 с в `agy-bridge` (`[F-01]`, `[F-02]`).
- **Что требует доработки:**
  1. **Разрыв границ репозитория и деплоя (`ASM-001`):** В [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L11-L15) предложен bootstrap `REPO_ROOT = Path(__file__).resolve().parent.parent.parent`. Внутри репозитория (`bridges/agy-bridge/server.py`) это укажет на корень `cli-agent-bridge`, но при деплое копированием в `~/.dsh/bridges/agy-bridge/server.py` (откуда запускается `launchd`-служба `com.user.dsh-agy-bridge`) `parent.parent.parent` разрешится в `$HOME`, где нет пакета `core/`. Служба не стартует с `ModuleNotFoundError: No module named 'core'`. Необходимо зафиксировать единый для всех мостов механизм из ADR-0005 (`RW-008`): переменная окружения `DSH_BRIDGE_ROOT` и/или симлинк `~/.dsh/bridges/agy-bridge` на каталог в репозитории.
  2. **Состав переносимых артефактов `bridges/agy-bridge`:** В [`~/.dsh/bridges/agy-bridge/server.py`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py#L274-L280) вызов `_load_fleet()` выполняется на уровне импорта модуля и читает `ROOT / "fleet.json"`, завершая процесс через `raise SystemExit(1)` при отсутствии файла. В [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L8-L9) указан перенос только `server.py` без [`fleet.json`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/fleet.json), что сделает невозможным импорт модуля в `pytest`.
  3. **Межрепозиторная граница:** Скрипт [`fetch_via_playwright.py`](file:///Users/aazhiry1/%D0%9C%D0%BE%D0%B9%20%D0%B4%D0%B8%D1%81%D0%BA/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py) находится вне git-репозитория `cli-agent-bridge` (в проекте `~/Мой диск/Workshop/aibunker-workshop`). В архитектурном пакете нужно явно разделить поставку в git `cli-agent-bridge` и сопутствующий патч во внешнем воркшопе.

### 2. Контракты и инварианты (`contracts_and_invariants`)
**Критерий 2 — NEEDS_WORK**

- **Блокер 2.1 (Вымышленный API `ProcessWatchdog` и отказ от `AdaptiveTimeoutController`):**
  - В [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L18-L26) и [`0007-agy-bridge-resilience-watchdog.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0007-agy-bridge-resilience-watchdog.md#L46-L47) специфицирован код:
    - `self.watchdog = ProcessWatchdog(pgid=self.proc.pid, interval_s=2.0)`
    - `self.watchdog.on_activity()`
    - `metrics = run.watchdog.poll()`
    - `time.monotonic() - run.watchdog.last_activity_ts > IDLE_TIMEOUT_S`
  - В реальном [`core/watchdog.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L100-L330) класс [`ProcessWatchdog`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L100-L118) имеет сигнатуру `__init__(self, ps_timeout_s: float = PS_TIMEOUT_S, log_fn=None, rid="", turn_id="")` и методы `seed(pgid)`, `sample(pgid) -> WatchdogMetrics`, `forget(pgid)`. У него **нет** параметров `pgid`/`interval_s` (`TypeError`), **нет** методов `poll()`, `on_activity()`, `is_idle()` и поля `last_activity_ts` (`AttributeError`).
  - Вся двухконтурная логика (`idle_timeout_s`, `safety_cap_s`, `on_activity(kind)`, `register_pgid(pgid)` со снятием базового среза `seed`, `check(pgid) -> (should_stop, reason, metrics)` и `close()` с очисткой `watchdog.forget(pgid)`) уже реализована в [`AdaptiveTimeoutController`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L332-L450). С точки зрения архитектурного единства хаба `agy-bridge` обязан использовать именно `AdaptiveTimeoutController` (или реальный контракт `ProcessWatchdog.seed`/`sample`/`forget`), не создавая второй несовместимый диалект watchdog-а.
- **Блокер 2.2 (Потерянное требование интеграции с `core/lifecycle.py`):**
  - В цели задачи и `ASM-001` заявлено переиспользование [`core/lifecycle.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py), но в [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md) оно полностью опущено. В [`~/.dsh/bridges/agy-bridge/server.py`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py#L503-L512) обработчик `SIGTERM`/`SIGINT` (`_kill_all`) захватывает `_active_lock` и пишет в `stderr` прямо из signal frame, что нарушает инвариант `RW-007` (риск дедлока интерпретатора). Кроме того, в `KNOWN_CHILD_BINARIES` ([`core/lifecycle.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py#L42-L58)) необходимо добавить `"agy"`, `"agy-cli.sh"` и `"chromium"`.
- **Блокер 2.3 (Отсутствие маппинга `idle_timeout` в HTTP/SSE-контракте ошибок):**
  - В [`Handler._error_body`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py#L1091-L1117) обработаны `timeout` и `first_token_timeout`, но нет ветки `st == "idle_timeout"`. При возврате `state("idle_timeout", 124, ...)` метод провалится в fallback `agy exited rc=124` (HTTP 502 `proxy_error`) вместо контрактного HTTP 504 / SSE error-чанка с типом `idle_timeout`.
- **Блокер 2.4 (Конфликт констант `SAFETY_CAP_S` и `ASM-002`):**
  - В [`core/watchdog.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py#L28) `SAFETY_CAP_S = 3600.0`, тогда как в `ASM-002` и `boundaries_and_contracts` заявлен `watchdog_safety_cap_s: 1800.0` и переопределение порога неактивности через `AGY_BRIDGE_IDLE_TIMEOUT`. Спецификация должна явно передавать `idle_timeout_s=float(os.environ.get("AGY_BRIDGE_IDLE_TIMEOUT", IDLE_TIMEOUT_S))` и `safety_cap_s=float(TIMEOUT_S)` в `AdaptiveTimeoutController`.

### 3. Риски, отказы и деградация (`risks_and_degradation`)
**Критерий 3 — NEEDS_WORK**

- **Риск каскадного падения всего батча в `fetch_via_playwright.py`:**
  - В [`fetch_via_playwright.py`](file:///Users/aazhiry1/%D0%9C%D0%BE%D0%B9%20%D0%B4%D0%B8%D1%81%D0%BA/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py#L1324) и строке 1354 вызов `await asyncio.gather(*[worker(s) for s in ...])` выполняется без `return_exceptions=True`.
  - Если согласно [`arch-spec.md` §2.3](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L36-L38) просто обернуть вызов `_track_fetch_one` в `asyncio.wait_for(..., timeout=60.0)`, то при зависании одного источника (`claude_status`) неперехваченный `asyncio.TimeoutError` прервёт весь `asyncio.gather` и уничтожит результаты остальных 74 источников.
  - **Требуемое исправление в спецификации:** `asyncio.wait_for(..., timeout=60.0)` должен находиться **внутри** `_track_fetch_one` вокруг вызова `fn(...)` с перехватом `(asyncio.TimeoutError, TimeoutError)` и возвратом штатного кортежа деградации `(src_id, [], "timeout after 60s")`. Дополнительно в блоках `finally:` функций `fetch_one` и `fetch_one_no_rss` вызов `await page.close()` необходимо защитить коротким таймаутом `asyncio.wait_for(page.close(), timeout=5.0)` с подавлением исключений, иначе при отмене корутины по `wait_for` закрытие зависшей вкладки Chromium заблокирует `finally` навечно.
- **Риск образования зомби-лидера группы (`stat=Z`) и утечки памяти в `ProcessWatchdog`:**
  - В [`arch-spec.md` §2.1](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L28-L29) для `close()` указан только `os.killpg(self.proc.pid, signal.SIGKILL)`. Без последующего `self.proc.wait(timeout=...)` головной процесс `self.proc` останется в таблице процессов в состоянии zombie (`Z`), а без вызова `watchdog.forget(self.proc.pid)` словари `_prev_cpu_by_pgid` и `_seen_descendants_by_pgid` в долгоживущем процессе моста будут бесконечно расти.

### 4. Безопасность и секреты (`security_and_secrets`)
**Критерий 4 — PASS**

- В [`~/.dsh/bridges/agy-bridge/server.py`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py#L289-L310) реализована очистка `AGY_BRIDGE_KEY` из окружения дочернего процесса (`_launch_env()`) и маскирование секретов в логах (`_mask_secrets`).
- Создание отдельной процессной группы (`start_new_session=True`) гарантирует, что `os.killpg(self.proc.pid, ...)` затрагивает исключительно дерево конкретного хода `agy` и не может послать сигнал процессу самого моста или соседним слотам.

### 5. Наблюдаемость и эксплуатация (`observability_and_ops`)
**Критерий 5 — NEEDS_WORK**

- **Частота вызова `ps` в цикле `_execute` (Performance / Ops):**
  - В [`arch-spec.md` §2.1](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L20-L27) опрос watchdog помещён непосредственно в тело цикла `_execute`. Когда `agy` активно стримит текстовые или reasoning-дельты, `run.q.get(timeout=1.0)` возвращает десятки событий в секунду. Вызов `subprocess.run(["ps", ...])` на каждой итерации цикла приведёт к сотням форков `ps` в секунду и высокой нагрузке на ядро macOS.
  - Опрос `ps` (`AdaptiveTimeoutController.check`) должен выполняться **только** по таймауту очереди (`except queue.Empty:`) либо не чаще чем раз в `WATCHDOG_INTERVAL_S = 5.0` с, тогда как при получении событий `text`, `reasoning`, `tool_trace`, `init` из очереди достаточно неблокирующего вызова `controller.on_activity(kind)`.
- **Наблюдаемость старта инструментов (`[F-04]`):**
  - В [`Run._pump`](file:///Users/aazhiry1/.dsh/bridges/agy-bridge/server.py#L755) события `step_update` с `step_type == "tool"` пересылаются в очередь только при `step.get("state") == "DONE"`. Рекомендуется фиксировать и старт инструмента (`state in ("RUNNING", "IN_PROGRESS")`), чтобы сбрасывать таймер на старте шага и логировать имя запущенного нативного инструмента до того, как он уйдёт в длительное ожидание.
- **Фичефлаг (Kill-Switch):**
  - По стандарту ADR-0005 (`RW-009`) и `muse-bridge` необходимо поддержать env-флаг `BRIDGE_ENABLE_ADAPTIVE_WATCHDOG` / `DSH_BRIDGE_WATCHDOG_ENABLED` для возможности мгновенного отключения watchdog без отката кода.

### 6. План реализации, миграции и тестов (`implementation_and_test_plan`)
**Критерий 6 — NEEDS_WORK**

- В [`arch-spec.md` §2.2](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md#L31-L35) заявлены только 3 базовых теста (`test_watchdog_detects_inactive_process`, `test_watchdog_resets_on_cpu_activity`, `test_kill_group_cleans_descendants`).
- Для достижения заявленного `NFR-RES-03` (100% покрытие нового функционала отказоустойчивости) в тест-план `tests/test_agy_bridge_resilience.py` необходимо добавить:
  1. Тест сброса таймера по протокольным событиям (`text`, `reasoning`, `tool_trace`) через `AdaptiveTimeoutController.on_activity`.
  2. Тест корректного формирования HTTP 504 и SSE error-чанка при `state == "idle_timeout"` в `Handler._error_body`.
  3. Тест очистки состояния `watchdog.forget(pgid)` и отсутствия зомби-процесса после `run.close()`.
  4. Юнит-тест на `_track_fetch_one` с зависшей корутиной (`asyncio.sleep(100)`), подтверждающий, что истечение 60-секундного `wait_for` возвращает `(src_id, [], ...)` и не роняет соседние задачи в `asyncio.gather`.

---

## Сводка субрибрик

- `SUB architecture: CONCERN — Спецификация в arch-spec.md использует несуществующие в core/watchdog.py методы (ProcessWatchdog(pgid=..., interval_s=...), .poll(), .on_activity()) вместо AdaptiveTimeoutController, упускает интеграцию core/lifecycle.py и ломает резолв core.* при деплое в ~/.dsh/bridges/agy-bridge.`
- `SUB security: PASS — Очистка AGY_BRIDGE_KEY в дочернем окружении, маскирование секретов в логах и изоляция процессных групп через start_new_session=True соблюдены.`
- `SUB performance: CONCERN — Вызов ps на каждой итерации цикла _execute без троттлинга по интервалу/queue.Empty приведёт к шторму вызовов subprocess.run(["ps", ...]) во время стриминга токенов.`
- `SUB tests: CONCERN — Отсутствуют тесты на маппинг HTTP/SSE-ошибки idle_timeout в _error_body, импорт с fleet.json в репозитории и изоляцию TimeoutError внутри _track_fetch_one при групповом asyncio.gather.`

---

## Перечень обязательных правок перед передачей Coder-у

1. **Привести [`arch-spec.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md) и [`0007-agy-bridge-resilience-watchdog.md`](file:///Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0007-agy-bridge-resilience-watchdog.md) к реальному контракту [`core/watchdog.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/watchdog.py):**
   - Использовать `AdaptiveTimeoutController(idle_timeout_s=IDLE_TIMEOUT_S, safety_cap_s=TIMEOUT_S, finish_reserve_s=0.0, log_fn=_log)` + `controller.register_pgid(self.proc.pid)` в `Run.__init__`, `controller.on_activity(kind)` при событиях из очереди `run.q`, `controller.check(run.proc.pid)` по интервалу (`>= WATCHDOG_INTERVAL_S` или в ветке `except queue.Empty:`) и `controller.close()` в `Run.close()`.
2. **Доопределить контракт `Handler._error_body` и `Run.close()`:**
   - Добавить обработку `st == "idle_timeout"` в `_error_body(out)` (HTTP 504, `type: "idle_timeout"`).
   - В `_kill_group` / `Run.close()` гарантировать `proc.wait(timeout=...)` после `os.killpg(proc.pid, signal.SIGKILL)` для предотвращения накопления процессов в состоянии `Z`.
3. **Зафиксировать схему деплоя и `fleet.json`:**
   - Включить перенос `bridges/agy-bridge/fleet.json` в спецификацию.
   - В bootstrap `sys.path` в `bridges/agy-bridge/server.py` поддержать `DSH_BRIDGE_ROOT` (и симлинк при деплое в `~/.dsh/bridges/agy-bridge`), а также добавить `"agy"`, `"agy-cli.sh"` в `KNOWN_CHILD_BINARIES` в [`core/lifecycle.py`](file:///Users/aazhiry1/work/src/cli-agent-bridge/core/lifecycle.py).
4. **Защитить `asyncio.gather` в [`fetch_via_playwright.py`](file:///Users/aazhiry1/%D0%9C%D0%BE%D0%B9%20%D0%B4%D0%B8%D1%81%D0%BA/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py):**
   - Внести `asyncio.wait_for(..., timeout=60.0)` внутрь `_track_fetch_one` с перехватом `(asyncio.TimeoutError, TimeoutError)` и возвратом `(src_id, [], "timeout after 60s")`, а также обернуть `await page.close()` в `finally:` в защитный таймаут `5.0` с.

ОБЩИЙ ВЕРДИКТ: NEEDS_WORK
