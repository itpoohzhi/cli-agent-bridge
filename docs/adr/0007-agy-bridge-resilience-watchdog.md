# 0007 — Сквозная отказоустойчивость моста Antigravity CLI (`bridges/agy-bridge`): адаптивный сторожевой таймер неактивности, защита от зависания фоновых задач и интеграция в монорепозиторий хаба

## Status

Proposed (2026-10-18, ревизия r2 — учтены замечания Раунда 1 Архитектурного Совета, RW-001..RW-008; ожидает Раунд 2).
Формат: MADR-full / ADR-full.
Задача: `REQ-EYE-33873-AGY-RESILIENCE` (`EYE-33873`), Run ID: `dsh-agy-bridge-resilience-20261018`, критичность: `S2`, профиль: `python-aisdlc-gcge`.
Архитектурный пакет: `.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/architecture-packet.json`.
Спецификация: `.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md`.
Расширяет: ADR 0002 (`0002-multi-binary-hub.md`), ADR 0005 (`0005-resilient-hub-lifecycle-and-detached-turns.md`), ADR 0006 (`0006-universal-context-resilience.md`).

## Y-формулировка

В контексте мульти-бинарного хаба консольных агентов `cli-agent-bridge`, обслуживающего DeepSeek Harness (Desktop), сталкиваясь с:
1. 30-минутным мёртвым зависанием клиента DSH (`• This turn failed agy timed out after 1800s TIMEOUT`) из-за отсутствия контроля активности дочерних процессов в `agy-bridge` (`[F-01]`, `[F-02]`),
2. зависанием CLI `agy` в ожидании фоновых задач (`task-NNN`), вызванных нативными инструментами `run_command` с `WaitMsBeforeAsync` (`[F-03]`, `[F-04]`),
3. бесконечным зависанием браузерного процесса Chromium/Playwright при разрывах сетевых соединений (`SSL_ERROR_SYSCALL` на `status.claude.com`) из-за отсутствия внешнего таймаута в `fetch_via_playwright.py` (`[F-05]`, `[F-06]`, `[F-07]`),
4. утечкой дочерних процессов и зомби при сбоях моста и хранением `agy-bridge` вне git-репозитория (`[F-10]`, `[F-11]`),

мы решили:
1. Включить исходный код моста в монорепозиторий по пути `bridges/agy-bridge/server.py` (+ `start.sh`, `fleet.json`); корень репозитория добавляется в `sys.path` bootstrap-блоком `parents[2]` (как в `muse-bridge`), деплой в `~/.dsh/bridges/agy-bridge` — симлинк на каталог в репозитории (RW-006);
2. Интегрировать **существующий** `core.watchdog.AdaptiveTimeoutController(idle_timeout_s=IDLE_TIMEOUT_S, safety_cap_s=TIMEOUT_S, finish_reserve_s=0.0, log_fn=_log)` (а не несуществующий `ProcessWatchdog(pgid=…, interval_s=…)`) в `Run` и `Handler._execute` (RW-001, RW-002):
   - **Контур неактивности (`IDLE_TIMEOUT_S = 300.0` с):** таймер сбрасывается протокольными событиями (`text`, `reasoning`, `tool_trace`, `init` → `on_activity(kind)`), приростом CPU группы (`cpu_delta_s > 0`) или новыми потомками; при отсутствии прогресса ход завершается `state("idle_timeout", 124, …)`;
   - **Предохранительный потолок:** `safety_cap_s = TIMEOUT_S` (1800 с) и `finish_reserve_s = 0.0` — эффективный потолок ровно `TIMEOUT_S`, без удвоения (дефолт `core` — 3600 с, для `agy-bridge` не используется);
   - **Kill-switch:** `BRIDGE_ENABLE_ADAPTIVE_WATCHDOG` (`_is_watchdog_enabled()`, как в `muse-bridge`); при выключении `idle_timeout_s = TIMEOUT_S`, `watchdog_enabled=False` (RW-003);
3. Ввести клиентский контракт `idle_timeout`: HTTP 504 `type: "idle_timeout"` в `Handler._error_body` и тот же объект ошибки в SSE-кадре перед `data: [DONE]` (RW-004);
4. Гарантированная зачистка: `SIGTERM` группе → ожидание до 2,0 с → `SIGKILL` группе, если жива → **всегда** `proc.wait(timeout=5.0)` (нет зомби) (RW-005);
5. Hotfix `scripts/fetch_via_playwright.py` (проект `aibunker-workshop`): `asyncio.wait_for(…, 60.0)` вокруг вызова одного источника в `_track_fetch_one` с возвратом `(src_id, [], "timeout after 60s")` и ограничение `page.close()` через `asyncio.wait_for(…, 5.0)` (RW-007);
6. Покрыть тестами `tests/test_agy_bridge_resilience.py` с малыми таймаутами и/или мок-часами (RW-008),

чтобы исключить блокировку рабочих слотов DSH на 30 минут, оперативно информировать пользователя о зависании и гарантировать освобождение ресурсов.

---

## Decision Drivers

- **D1 (Оперативное прерывание зависаний):** при отсутствии прогресса ход прерывается за ≤ 310 с (300 с порога + ≤ 5 с троттлинг проверки + ≤ 2 с `ps` + 1 с тик очереди), а не за 1800 с.
- **D2 (Изоляция и гигиена процессов):** после завершения хода нет ни живых потомков, ни зомби-лидера группы.
- **D3 (Единая кодовая база):** `agy-bridge` версионируется в git, тестируется общим сьютом, использует `core.*`.
- **D4 (Сетевая надёжность сбора):** сбойный веб-источник не блокирует общий `asyncio.gather()`.
- **D5 (Обратимость):** фичефлаг-kill-switch возвращает прежнее поведение без перевыкладки кода.

---

## Considered Options

| Вариант | Вердикт |
|---|---|
| A. Использовать `AdaptiveTimeoutController` из `core.watchdog` (контроллер + `ProcessWatchdog` внутри) | **Выбран**: уже покрыт `tests/test_adaptive_idle_watchdog.py`, единая семантика с `muse-bridge` |
| B. Написать отдельный watchdog внутри `agy-bridge` | Отклонён: дубль кода, расхождение семантики (D3) |
| C. Только уменьшить `AGY_BRIDGE_TIMEOUT` до 300 с | Отклонён: ломает легитимные длинные ходы с тихим CPU-активным инструментом |
| D. Проверять `controller.check()` на каждом событии | Отклонён: шторм вызовов `ps` при быстром стриминге токенов (RW-001) |

---

## Decision Outcome

### 1. `bridges/agy-bridge/server.py` (RW-001, RW-002, RW-003, RW-006)

**Импорт и bootstrap:**

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

`Path.resolve()` раскрывает симлинк деплоя, поэтому `parents[2]` указывает на корень репозитория (не на `~/.dsh`).

**Константы и флаг:**

```python
IDLE_TIMEOUT_S = float(os.environ.get("AGY_BRIDGE_IDLE_TIMEOUT", _CORE_IDLE_TIMEOUT_S))  # невалидное/≤0 → 300.0 + лог

def _is_watchdog_enabled() -> bool:
    return os.environ.get("BRIDGE_ENABLE_ADAPTIVE_WATCHDOG", "1") not in ("0", "false", "no", "off")
```

**`Run.__init__`** — сразу после `Popen(start_new_session=True)`:

```python
enabled = _is_watchdog_enabled()
self.controller = AdaptiveTimeoutController(
    idle_timeout_s=IDLE_TIMEOUT_S if enabled else TIMEOUT_S,
    safety_cap_s=TIMEOUT_S,       # 1800 с; дефолт core 3600 с не используется
    finish_reserve_s=0.0,         # эффективный потолок = TIMEOUT_S
    watchdog_enabled=enabled,     # выключено: без вызовов ps
    log_fn=_log,
)
self.controller.register_pgid(self.proc.pid)
```

**`Handler._execute`:**
- на событиях очереди `init`, `text`, `reasoning`, `tool_trace` — `run.controller.on_activity(kind)`;
- проверка — **только** в ветке `except queue.Empty:` и не чаще `WATCHDOG_INTERVAL_S = 5.0` с (замер по `time.monotonic()`), чтобы быстрый стриминг не порождал шторм `ps`:

```python
should_stop, reason, _m = run.controller.check(run.proc.pid)
if should_stop and reason == "idle_timeout":
    return state("idle_timeout", 124, f"no activity for {IDLE_TIMEOUT_S:g}s")
if should_stop and reason == "absolute_cap":
    return state("timeout", 124, f"proxy timeout after {TIMEOUT_S}s")
# reason == "child_exited": НЕ ошибка — терминальное событие "done" придёт из очереди
```

Уточнение к RW-001: `check()` возвращает `should_stop=True` также с `reason="child_exited"` (штатное завершение группы). Это не отказ; цикл продолжает читать очередь до `done`/`pump_error`. `absolute_cap` отображается в существующее состояние `timeout`, чтобы не менять клиентский контракт 504 `timeout`.
- Существующие `deadline`, `first_token_timeout`, `_client_gone` сохраняются без изменений.

**`Run.close()`:** `controller.close()` (до закрытия потоков) + зачистка группы (п. 2).

### 2. Зачистка процессов (RW-005)

`_kill_group(proc)` переписывается:

1. `os.killpg(proc.pid, SIGTERM)`; `ProcessLookupError` игнорируется (группы уже нет);
2. ожидание до 2,0 с (опрос `proc.poll()` + `os.killpg(pgid, 0)`);
3. если группа жива — `os.killpg(proc.pid, SIGKILL)`; `PermissionError/OSError` → фолбэк `proc.kill()`;
4. **всегда**, в том числе после `ProcessLookupError`: `proc.wait(timeout=5.0)` (`TimeoutExpired` → лог `kill_group_wait_timeout`, не исключение).

Это устраняет ранний `return` текущей реализации, оставлявший `Z`-процесс.

### 3. Клиентский контракт ошибок (RW-004)

`Handler._error_body`:
```python
if st == "idle_timeout":
    return {"message": f"agy execution idle timeout after {IDLE_TIMEOUT_S:g}s "
                       "(no activity or progress in process group)",
            "type": "idle_timeout", "code": 504}
```
(при значении по умолчанию — `…after 300s…`). Для SSE существующая ветка `else` отправляет `data: {"error": {…}}\n\ndata: [DONE]\n\n` — новый тип наследует её без дополнительного кода; для JSON-режима — HTTP 504 через `self._send(err["code"], …)`.

### 4. Развёртывание и совместимость `core` (RW-006)

- В репозитории: `bridges/agy-bridge/{server.py,start.sh,fleet.json}` (`fleet.json` копируется из `~/.dsh/bridges/agy-bridge/fleet.json`); `logs/`, `workspace/`, `backups/` — в `.gitignore`.
- В `core/lifecycle.py` в `KNOWN_CHILD_BINARIES` добавляются `"agy"`, `"agy-cli.sh"`.
- Деплой: `~/.dsh/bridges/agy-bridge -> /Users/aazhiry1/work/src/cli-agent-bridge/bridges/agy-bridge` (симлинк). Перед заменой существующий каталог переносится в `~/work/backups/agy-bridge-<ts>/` (содержит `logs`, `workspace`, `backups`, `fleet.json`, `server.py`, `start.sh`).
- `start.sh`: `export PYTHONPATH="<repo-root>${PYTHONPATH:+:$PYTHONPATH}"` — страховка, если файл всё же скопирован, а не слинкован.
- Рестарт `com.user.dsh-agy-bridge` — только после приёмки (необратимое/внешнее действие).

**Расхождение с формулировкой RW-006:** в `~/.dsh/bridges/` каталоги `muse-bridge` и `droid-bridge` на момент r2 — **обычные каталоги с копиями `server.py`**, а не симлинки (проверено `ls -la`). Симлинк для `agy-bridge` — решение Совета; ссылка «как у muse-bridge» корректна лишь как целевой стандарт, не как существующий факт. Требует подтверждения владельца при деплое.

### 5. Hotfix `scripts/fetch_via_playwright.py` (RW-007)

Фактическая структура скрипта: `_track_fetch_one(src, ctx, ctx_r, cutoff, fn)` вызывает `fn(src, ctx, ctx_r, cutoff)` (`fetch_one`) либо `fn(src, ctx, cutoff)` (`fetch_one_no_rss`); функции `_fetch_one_url` в скрипте **нет** — оборачивается именно вызов `fn(...)`:

```python
try:
    coro = fn(src, ctx, ctx_r, cutoff) if fn.__name__ == "fetch_one" else fn(src, ctx, cutoff)
    return await asyncio.wait_for(coro, timeout=60.0)
except (asyncio.TimeoutError, TimeoutError):
    return (src_id, [], "timeout after 60s")
```

Все голые `await page.close()` (строки 641, 661, 885, 926, 970, 1031, 1167; строка 844 уже ограничена) → `await asyncio.wait_for(page.close(), timeout=5.0)` (через общий хелпер, `TimeoutError` логируется и подавляется). Дополнительно (эшелонированная защита, не RW): `AbortSignal.timeout(15000)` в `fetch(url, …)` внутри `EXTRACT_JS` (строка 508).

### 6. Тесты (RW-008)

`tests/test_agy_bridge_resilience.py`: малые таймауты (`idle_timeout_s=0.2`) и/или мок-часы (`clock=`) контроллера; покрытие — детекция неактивности; сброс по `cpu_delta > 0`; сброс по `on_activity`; fail-closed при деградации `ps`; HTTP 504 + SSE-кадр; уничтожение группы и сборка зомби; изоляция таймаута в `fetch_via_playwright.py`. Подробности — `arch-spec.md` §6.

---

## Consequences

**Положительные:** обнаружение зависания за ≈ 5 мин вместо 30; единая семантика с `muse-bridge`; мост под git и тестами; kill-switch.

**Отрицательные / риски:**
- `ps` раз в ≤ 5 с на каждый активный ход (при ≤ 32 соединений — приемлемо; троттлинг обязателен).
- Fail-closed при деградации `ps` может прервать CPU-активный, но «тихий» по протоколу ход через 300 с — смягчается kill-switch.
- Новый `type: "idle_timeout"` должен быть понятен клиенту DSH; до обновления клиента он отображается как общая 504-ошибка.
- Симлинк-деплой: `logs/`, `workspace/` физически окажутся в каталоге репозитория (игнорируются git).
- Hotfix лежит вне репозитория (`aibunker-workshop`): правка и его тест связаны через путь к файлу — тест пропускается (`skip`), если скрипта нет.
- `AGY_BRIDGE_IDLE_TIMEOUT` меньше фактического «тихого» окна инструмента может давать ложные прерывания; дефолт 300 с.

## Rollback

`BRIDGE_ENABLE_ADAPTIVE_WATCHDOG=0` в окружении службы + рестарт → прежнее поведение (`idle_timeout_s = TIMEOUT_S`, без `ps`); полный откат — вернуть каталог из `~/work/backups/agy-bridge-<ts>/` на место симлинка.
