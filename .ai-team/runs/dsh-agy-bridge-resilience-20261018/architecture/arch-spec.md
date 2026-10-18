# Спецификация архитектуры: Отказоустойчивость agy-bridge и устранение таймаутов (ревизия r2)

Ревизия r2 — по итогам Раунда 1 Архитектурного Совета (RW-001..RW-008). ADR: `docs/adr/0007-agy-bridge-resilience-watchdog.md`.

## 1. Назначение
Адаптивный сторожевой таймер (`core.watchdog.AdaptiveTimeoutController`), предотвращение 1800-секундных зависаний и интеграция моста `bridges/agy-bridge` в репозиторий `cli-agent-bridge`.

## 2. Реальный API `core.watchdog` (сверено с `core/watchdog.py`)

| Элемент | Сигнатура / значение |
|---|---|
| Константы | `IDLE_TIMEOUT_S=300.0`, `SAFETY_CAP_S=3600.0`, `FINISH_RESERVE_S=35.0`, `WATCHDOG_INTERVAL_S=5.0`, `PS_TIMEOUT_S=2.0` |
| Конструктор | `AdaptiveTimeoutController(idle_timeout_s, safety_cap_s, finish_reserve_s, watchdog=None, watchdog_enabled=True, clock=time.monotonic, rid="", turn_id="", log_fn=None)` |
| `register_pgid(pgid: int)` | запоминает pgid, `watchdog.seed(...)` — базовый срез CPU |
| `on_activity(kind="protocol")` | сброс таймера неактивности (синоним `record_activity`) |
| `check(pgid=None)` | `(should_stop, reason, metrics)`; `reason ∈ {"absolute_cap","idle_timeout","child_exited"}` |
| `effective_cap_s()` | `safety_cap_s − finish_reserve_s` (при `finish_reserve_s=0.0` = `safety_cap_s`) |
| `close()` | `watchdog.forget(pgid)` |

Класса `ProcessWatchdog(pgid=…, interval_s=…)` с методами `poll()` / `idle_seconds` **не существует** — псевдокод r1 удалён. `ProcessWatchdog` используется только внутри контроллера (`sample(pgid)` → `WatchdogMetrics`, `has_progress`, `ps_degraded`).

Тонкости `check()`: (а) `absolute_cap` проверяется первым; (б) `child_exited` возвращается, когда группа не жива — это штатное завершение, **не** отказ; (в) при деградации/таймауте `ps` — fail-closed: `last_activity_ts` не обновляется.

## 3. Компоненты и изменения

### 3.1. `bridges/agy-bridge/server.py` (RW-001, RW-002, RW-003, RW-004, RW-005, RW-006)

**Перенос** из `~/.dsh/bridges/agy-bridge/server.py` в `bridges/agy-bridge/server.py` (+ `start.sh`, `fleet.json`). Исходный файл: `class Run` (~633), `Run.close` (~781), `Handler._execute` (~891), `Handler._error_body` (~1091), `_kill_group` (~489), SSE-ветка (~1370-1389). Модуль должен импортироваться без побочных эффектов (запуск сервера — под `if __name__ == "__main__"`), иначе тесты невозможны.

**Bootstrap `sys.path` (RW-006):**
```python
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.watchdog import (  # noqa: E402
    IDLE_TIMEOUT_S as _CORE_IDLE_TIMEOUT_S,
    WATCHDOG_INTERVAL_S,
    AdaptiveTimeoutController,
)
```
`resolve()` раскрывает симлинк деплоя → `parents[2]` = корень репозитория.

**Конфигурация и фичефлаг (RW-003):**
```python
IDLE_TIMEOUT_S = float(os.environ.get("AGY_BRIDGE_IDLE_TIMEOUT", _CORE_IDLE_TIMEOUT_S))  # невалидное/≤0 → 300.0 + _log

def _is_watchdog_enabled() -> bool:
    return os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1") not in ("0", "false", "no", "off")
```
Флаг читается на каждом создании `Run` (мгновенный kill-switch без правки кода; смена значения требует рестарта службы, т.к. окружение процесса фиксировано launchd).

**`Run.__init__` (RW-001, RW-002):** сразу после `Popen(..., start_new_session=True)`:
```python
enabled = _is_watchdog_enabled()
self.controller = AdaptiveTimeoutController(
    idle_timeout_s=IDLE_TIMEOUT_S if enabled else TIMEOUT_S,
    safety_cap_s=TIMEOUT_S,      # 1800.0; дефолт core 3600.0 не используется
    finish_reserve_s=0.0,        # эффективный потолок = TIMEOUT_S, без резерва
    watchdog_enabled=enabled,    # kill-switch: без вызовов ps
    log_fn=_log,
)
self.controller.register_pgid(self.proc.pid)
```
`watchdog_enabled=enabled` — дополнение архитектора к RW-001/003: выключенный watchdog не должен вызывать `ps`.

**`Handler._execute` (RW-001):**
1. События очереди `init`, `text`, `reasoning`, `tool_trace` → `run.controller.on_activity(kind)`. `result`, `done`, `pump_error` — терминальные, активностью не считаются.
2. Проверка — только в ветке `except queue.Empty:` (тик очереди 1,0 с) и не чаще `WATCHDOG_INTERVAL_S` (5,0 с) по `time.monotonic()`:
```python
now = time.monotonic()
if now - last_wd_check >= WATCHDOG_INTERVAL_S:
    last_wd_check = now
    should_stop, reason, _metrics = run.controller.check(run.proc.pid)
    if should_stop and reason == "idle_timeout":
        _log(f"watchdog idle_timeout pgid={run.proc.pid} idle>={IDLE_TIMEOUT_S:g}s")
        return state("idle_timeout", 124, f"no activity for {IDLE_TIMEOUT_S:g}s")
    if should_stop and reason == "absolute_cap":
        return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
    # reason == "child_exited": не отказ — ждём "done"/"pump_error" из очереди
```
Причина троттлинга: каждый `check()` запускает `ps` (до `PS_TIMEOUT_S=2.0` с); при быстром стриминге токенов вызов на каждое событие дал бы шторм. Во время потока событий таймер и так сбрасывается `on_activity`, поэтому пропуск проверки безопасен.
3. Уточнение к RW-001: «при `should_stop == True` возвращать `state(reason, 124, err)`» применяется к `idle_timeout` и `absolute_cap` (последний отображается в существующее `state("timeout")`, клиентский контракт 504 `timeout` не меняется); `child_exited` — штатное завершение и ошибкой не является.
4. Прежние проверки (`deadline`, `first_token_timeout`, `_client_gone`) не меняются. `idle_timeout` → `Run.close()` вызывается существующей цепочкой `finally` в `_run_once`.

**`Run.close()`:** `self.controller.close()` → зачистка группы (см. `_kill_group`) → закрытие потоков.

**`_kill_group(proc)` (RW-005):**
```text
1. os.killpg(pid, SIGTERM)            # ProcessLookupError → группы нет, перейти к п.4
2. ждать ≤ 2.0 с: пока proc.poll() is None или killpg(pid, 0) успешен
3. если группа жива: os.killpg(pid, SIGKILL)   # PermissionError/OSError → proc.kill()
4. ВСЕГДА: proc.wait(timeout=5.0)     # TimeoutExpired → _log("kill_group_wait_timeout"), без исключения
```
Нынешняя реализация делает ранний `return` при `ProcessLookupError` без `wait()` — источник зомби; п.4 это закрывает. `_kill_all` (shutdown) остаётся `SIGKILL` группам + `os._exit(0)`.

**`Handler._error_body` (RW-004):**
```python
if st == "idle_timeout":
    return {"message": f"agy execution idle timeout after {IDLE_TIMEOUT_S:g}s "
                       "(no activity or progress in process group)",
            "type": "idle_timeout", "code": 504}
```
- JSON-режим: `self._send(504, {"error": err})` (существующая ветка `_serve_json`).
- SSE-режим (заголовки 200 уже отправлены): существующая ветка `else` эмитит `data: {"error": {...,"type":"idle_timeout","code":504}}\n\n` и затем `data: [DONE]\n\n`. Новый тип наследует её без дополнительного кода; тест фиксирует это.

### 3.2. Деплой и `core` (RW-006)
- `bridges/agy-bridge/fleet.json` — копия `~/.dsh/bridges/agy-bridge/fleet.json`; `logs/`, `workspace/`, `backups/` в `.gitignore`.
- `core/lifecycle.py`: в `KNOWN_CHILD_BINARIES` добавить `"agy"`, `"agy-cli.sh"` (в проверке `reap_orphans` используется подстрочное сравнение с выводом `ps` — как и для уже имеющихся `sh`, `node`).
- Деплой: `~/.dsh/bridges/agy-bridge -> /Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge`. Порядок: (1) остановить службу; (2) перенести существующий каталог в `~/work/backups/agy-bridge-<ts>/`; (3) создать симлинк; (4) вернуть нужное состояние (`logs`, `workspace`) при необходимости; (5) запустить `com.user.dsh-agy-bridge`; (6) тяжёлая проверка живым ходом DSH. Рестарт службы — после приёмки.
- `start.sh`: `export PYTHONPATH="<repo-root>${PYTHONPATH:+:$PYTHONPATH}"` — страховка для копии вместо симлинка (при копии `parents[2]` указал бы на `~/.dsh`).
- **Расхождение:** `~/.dsh/bridges/muse-bridge` и `droid-bridge` сейчас — обычные каталоги с копиями `server.py`, не симлинки. Формулировка RW-006 «стандарт DSH, как у muse-bridge/droid-bridge» неверна как описание текущего состояния; симлинк принят как целевой стандарт по решению Совета, подтвердить при деплое.

### 3.3. Hotfix `aibunker-workshop/scripts/fetch_via_playwright.py` (RW-007)
Сверено с файлом: `_track_fetch_one(src, ctx, ctx_r, cutoff, fn)` (строка 1212) вызывает `fn(src, ctx, ctx_r, cutoff)` для `fetch_one` и `fn(src, ctx, cutoff)` для `fetch_one_no_rss`. Функции `_fetch_one_url` в скрипте нет — оборачивается этот вызов:
```python
try:
    coro = fn(src, ctx, ctx_r, cutoff) if fn.__name__ == "fetch_one" else fn(src, ctx, cutoff)
    return await asyncio.wait_for(coro, timeout=60.0)
except (asyncio.TimeoutError, TimeoutError):
    return (src_id, [], "timeout after 60s")
finally:   # прежний блок pending/completed сохраняется
    ...
```
Формат результата `(src_id, items, err)` совпадает с потребителем `for src_id, items, err in results`. Отмена по `wait_for` выполняет `finally` внутри `fn`, поэтому `page.close()` обязан быть ограничен.
- Все голые `await page.close()` (строки 641, 661, 885, 926, 970, 1031, 1167; строка 844 уже `wait_for(…, NAV_TIMEOUT_MS/1000)`) → `await asyncio.wait_for(page.close(), timeout=5.0)` через хелпер, подавляющий `TimeoutError`/`Exception` с логом.
- Эшелонированная защита (не RW): `AbortSignal.timeout(15000)` в `fetch(url, {...})` в `EXTRACT_JS` (строка 508).

## 4. Фичефлаги и откат
| Флаг | Значение по умолчанию | Эффект выключения |
|---|---|---|
| `BRIDGE_ENABLE_ADAPTIVE_WATCHDOG` | `1` | `idle_timeout_s = TIMEOUT_S`, без `ps` → поведение до фикса |
| `AGY_BRIDGE_IDLE_TIMEOUT` | `300` | порог неактивности (с); невалидное → 300 |
Откат: флаг `0` + рестарт службы; полный — вернуть каталог из `~/work/backups/agy-bridge-<ts>/`.

## 5. Граничные контракты
- `POST /v1/chat/completions`, `127.0.0.1:9887`, `com.user.dsh-agy-bridge`, лончер `~/.config/agy-launch/agy-cli.sh`.
- Новые состояния ошибок: `idle_timeout` → HTTP 504 `type: "idle_timeout"`; `absolute_cap` → прежний `timeout`.
- Время до прерывания: ≤ 300 + 5 (троттлинг) + 2 (`ps`) + 1 (тик очереди) = ≤ 308 с (бюджет 310 с).

## 6. Тестовый пакет `tests/test_agy_bridge_resilience.py` (RW-008)

Общие правила: без реальных ожиданий порядка минут; `idle_timeout_s=0.2`, `safety_cap_s` малый, `finish_reserve_s=0.0`; для логики без процессов — `clock=_FakeClock` и подставной `watchdog` (по образцу `tests/test_adaptive_idle_watchdog.py`). Модуль `bridges/agy-bridge/server.py` загружается через `importlib.util.spec_from_file_location` (каталог с дефисом; env `AGY_BRIDGE_KEY` задаётся до импорта). Процессы создаются с `start_new_session=True`, уничтожаются в `finally`/фикстуре.

| # | Тест | Сценарий / критерий |
|---|---|---|
| 1 | `test_idle_timeout_detected_for_sleeping_process` | `sleep 100`, `idle_timeout_s=0.2`; `check()` в цикле ≤ 2 с → `(True, "idle_timeout", …)` |
| 2 | `test_cpu_delta_resets_idle_timer` | busy-loop процесс (`python3 -I -c "while True: pass"`) или мок-метрики `cpu_delta_s>0`; окно > `idle_timeout_s` без `idle_timeout`, `last_activity_kind == "cpu_delta"` |
| 3 | `test_on_activity_resets_idle_timer` | мок-часы: `on_activity("text")` каждые 0.15 с при `idle=0.2` — не срабатывает; пауза 0.25 с — срабатывает; проверить все 4 вида (`text`, `reasoning`, `tool_trace`, `init`) |
| 4 | `test_ps_degraded_fail_closed` | подставной watchdog с `ps_degraded=True`: `last_activity_ts` не обновляется → `idle_timeout` по истечении порога; событие `watchdog_ps_degraded` залогировано |
| 5 | `test_check_throttled_in_execute` | в `_execute` при 100 событиях за 1 с `controller.check` вызывается не более 1 раза (счётчик-обёртка); при `queue.Empty` ≥ 5 с — вызывается |
| 6 | `test_child_exited_is_not_error` | `check()` → `child_exited`; `_execute` продолжает чтение очереди и завершается `state("done")` |
| 7 | `test_absolute_cap_maps_to_timeout` | `safety_cap_s=0.2`, `finish_reserve_s=0.0` → `reason=="absolute_cap"`; `_execute` → `state("timeout")` |
| 8 | `test_killswitch_disables_watchdog` | `BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0` → `controller.idle_timeout_s == TIMEOUT_S`, `watchdog_enabled is False`, `ps` не вызывается; значения `0/false/no/off` |
| 9 | `test_error_body_idle_timeout_http_504` | `Handler._error_body({"state":"idle_timeout"})` → `code 504`, `type "idle_timeout"`, текст содержит `idle timeout after 300s` |
| 10 | `test_sse_error_chunk_idle_timeout` | перехват `_emit`: при `idle_timeout` последовательность — кадр `data: {"error": {…"type":"idle_timeout","code":504}}\n\n`, затем `data: [DONE]\n\n`; JSON-режим отвечает HTTP 504 |
| 11 | `test_kill_group_cleans_descendants_and_reaps_zombie` | `sh -c 'sleep 100 & sleep 100 & wait'`; после `_kill_group`: `proc.returncode is not None`, `os.killpg(pgid, 0)` → `ProcessLookupError`, `ps -o stat= -p <pid>` пуст (нет `Z`) |
| 12 | `test_kill_group_reaps_when_group_already_gone` | процесс завершён заранее; `_kill_group` не падает и вызывает `proc.wait` (нет зомби) |
| 13 | `test_kill_group_escalates_to_sigkill` | процесс игнорирует `SIGTERM` (`trap '' TERM`); завершён ≤ 2.0 + 5.0 с, через `SIGKILL` |
| 14 | `test_fetch_one_timeout_isolated` | загрузить `fetch_via_playwright.py` по пути (env `AIBUNKER_FETCH_SCRIPT`, по умолчанию `~/Мой диск/Workshop/aibunker-workshop/scripts/fetch_via_playwright.py`; `pytest.skip`, если файла нет), `playwright` не требуется на уровне импорта; `fn` зависает, `wait_for` патчится на 0.1 с → результат `(src_id, [], "timeout after 60s")`, `_progress["pending"]` очищен, соседний источник в `asyncio.gather` завершается |
| 15 | `test_page_close_bounded` | `page.close()` зависает; хелпер возвращает управление ≤ 5.0 с (патч таймаута), исключение подавлено |

Критерии качества: тесты детерминированы (мок-часы там, где возможно), без `sleep` длиннее 2 с, процессы не остаются после теста; полный `uv run pytest -q` зелёный (Full Suite Gate).

## 7. Риски и открытые проверки для реализации
- `core.watchdog` рассчитан на macOS `ps`; тесты 1, 2, 11–13 — Darwin/POSIX (на других ОС `skipif`).
- Импорт `server.py` без побочных эффектов — условие тестируемости (проверить `if __name__ == "__main__"`).
- `AGY_BRIDGE_IDLE_TIMEOUT` в диапазоне, меньшем `FIRST_TOKEN_TIMEOUT_S` (120), не запрещён, но не рекомендуется.
- Подтвердить при деплое: симлинк vs копия (см. §3.2).
