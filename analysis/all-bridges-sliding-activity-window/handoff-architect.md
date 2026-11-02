# Handoff to Architect — Сквозное внедрение скользящих окон активности во все мосты (Rev 22, канонический)

## 1. Входные факты и матрица компонентов
- Карточка задачи: `analysis/all-bridges-sliding-activity-window/research-plan.md`
- Реестр фактов: `analysis/all-bridges-sliding-activity-window/evidence-ledger.md` (`[F-01]`..`[F-15]`)
- Анализ рисков: `analysis/all-bridges-sliding-activity-window/evidence-black.md` (`[B-01]`..`[B-24]`)
- Варианты архитектуры: `analysis/all-bridges-sliding-activity-window/competing-options.md` (Вариант V2)
- Рекомендация RCA: `analysis/all-bridges-sliding-activity-window/consolidated-rca-decision.md`

### Выверенная матрица компонентов системы
| Компонент / Файл | Фактическое состояние в коде | Реальная целевая дельта задачи |
|---|---|---|
| `bridges/claude-p-bridge/server.py` | В цикле `_execute` (`:600-615`) вотчдог отсутствует: `run.q.get(timeout=POLL_INTERVAL_S)` крутится бесконечно при зависании CLI | **ЦЕЛЕВАЯ ДЕЛЬТА 1**: Безопасный парсер настроек `_read_dsh_env_file() -> dict[str, str]` со строгим whitelist несекретных настроек (любые `*_KEY` исключены), последнее значение перезаписывает предыдущее (паритет с shell), возвращающий локальный словарь `_DSH_ENV` **БЕЗ мутации `os.environ`**. Размещение функций строго между `:98` и `:101`. Защищенный импорт `from core.watchdog import AdaptiveTimeoutController` сразу после настройки `sys.path` (`:58-61`). Каскадный геттер: `CLAUDE_P_BRIDGE_*` -> `BRIDGE_*` -> `default`; проверка `0 < val < float("inf")` без зависимости от `math`. Флаг `CLAUDE_P_BRIDGE_WATCHDOG_ENABLED` (дефолт `"1"`). Чтение и передача всех 4 параметров (`idle_timeout_s`, `safety_cap_s`, `io_wait_cap_s`, `watchdog_interval_s`). Безопасное чтение процесса `proc = getattr(run, "proc", None)` и `proc_pid = getattr(proc, "pid", None)` (100% совместимость с `FakeRun`). Контракт `should_stop, reason, _ = controller.check(proc_pid)` с реакцией на таймауты (`idle_timeout`, `absolute_cap`) и пропуском нормального выхода `child_exited`; троттлинг проверок в начале `while True:` по `controller.watchdog_interval_s`; вызов `record_activity(kind)` на `text`, `thinking` и `result`; в `@staticmethod _error_body`: перехват `st == "timeout"` -> 504; `try...finally` с закрытием контроллера |
| `bridges/opencode-zen-bridge/server.py` | Использует собственное пространство имён `BRIDGE_ZEN_*` и хелпер `_zen_positive_float` (`:338`). `STALL_TIMEOUT_S` (`:1946`) | **ЦЕЛЕВАЯ ДЕЛЬТА 2**: Чтение `STALL_TIMEOUT_S` через существующий хелпер `_zen_positive_float("OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S", 60.0)`, сохраняя чистую изоляцию от `BRIDGE_ZEN_IDLE_TIMEOUT_S` |
| `server.py` (Хаб) | Функция `parse_live_write_timeout(default: float = 30.0)` (`:394-406`) читает только `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` | **ЦЕЛЕВАЯ ДЕЛЬТА 3**: Двухступенчатый fallback: сначала проверяется `BRIDGE_CLIENT_WRITE_TIMEOUT_S`; если не задан или невалиден — проверяется `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S`; если оба отсутствуют/невалидны — возвращается переданный `default` |
| `tests/test_claude_p_watchdog.py` | Отсутствует | **ЦЕЛЕВАЯ ДЕЛЬТА 4**: Новый детерминированный набор unit-тестов L1 для вотчдога `claude-p-bridge`: модульная фикстура изоляции с `pytest.MonkeyPatch.context()`, очисткой префиксов и `sys.modules.pop` в `finally`, фильтрация секретов, мок `_kill_group`, срабатывание таймаутов, реакция на `child_exited`, сброс таймера активности, троттлинг проверок и закрытие контроллера в `finally` |
| `tests/test_stream_timeout_config.py` | Тестирует `parse_live_write_timeout` (`:9-37`) | **ЦЕЛЕВАЯ ДЕЛЬТА 5**: Добавление `monkeypatch.delenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", raising=False)` во все тесты таймаута и добавление unit-теста на двухступенчатый fallback и приоритет |
| `core/watchdog.py` | `AdaptiveTimeoutController` (`:359-515`) работает стабильно и проверен | Сохраняется в текущем проверенном виде без изменений |
| `adapters/passthrough_adapter.py` | Автономный `_TimedSseReader` (`:642-720`) с `last_upstream`, `idle_timeout_s`, `safety_cap_s` (173 теста PASS) | Сохраняется в неизменном эталонном виде |
| `bridges/agy-bridge/server.py` | Использует `AdaptiveTimeoutController` (`:5202`) и `on_activity` (`:6236`) | Сохраняется в рабочем виде, подтверждена совместимость |

---

## 2. NFR-Scale Card и параметры надежности

### 2.1. Изоляция сабагентов и предотвращение Deadlock
- Сабагенты Совета Тимлидов (`launch_seat.py`) вызываются через прямые терминальные CLI-транспорты (`claude -p`, `codex exec`) по таблице `panel_transports.json`, минуя HTTP-семафор хаба `MAX_CONCURRENT=128`. Это предотвращает взаимную блокировку родительских сессий и судейских процессов.
- На хабе `:9882` очередь ожидания слота семафора ограничена `QUEUE_TIMEOUT_S = 900` с (`server.py:383`).
- Семафор входящих сетевых соединений `_conn_sem` (`fleet.admission.max_http_connections`) при насыщении возвращает 503 `connection limit` (`server.py:7718-7733`).

### 2.2. Защита от медленного клиента (Целевая реализация в `server.py`)
```python
def _parse_valid_timeout(raw: str | None, low: float = 1.0, high: float = 300.0) -> float | None:
    if raw is None or not raw.strip():
        return None
    try:
        val = float(raw.strip())
        if math.isfinite(val) and low <= val <= high:
            return val
    except (ValueError, TypeError):
        pass
    return None

def parse_live_write_timeout(default: float = 30.0) -> float:
    # 1. Приоритет канонического имени:
    val = _parse_valid_timeout(os.getenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S"))
    if val is not None:
        return val
    # 2. Fallback на legacy имя Droid:
    val = _parse_valid_timeout(os.getenv("DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S"))
    if val is not None:
        return val
    # 3. Безопасный дефолт:
    return default
```

---

## 3. Архитектурное задание для architect-software-product

### 3.1. Внедрение вотчдога в `bridges/claude-p-bridge/server.py`

1. **Изолированный защищенный импорт контроллера (размещается сразу после настройки `sys.path` на `:58-61`, сохраняя fail-closed AD-002 для `core.tool_emulation` на `:63-86`):**
   ```python
   try:
       from core.watchdog import AdaptiveTimeoutController
   except ImportError:
       AdaptiveTimeoutController = None  # type: ignore[assignment,misc]
   ```

2. **Размещение функций конфигурации строго между `:98` и `:101` (после `_env_positive_int`, до объявления констант `ROOT`, `HOST`, `AUTH_KEY`):**
   - Строгий whitelist ключей конфигурации: чтение любых ключей авторизации (`*_KEY`) категорически запрещено!
   - Повторяющиеся ключи в файле: последнее значение перезаписывает предыдущее (паритет с shell).
   ```python
   _ALLOWED_SETTINGS_KEYS = frozenset({
       "CLAUDE_P_BRIDGE_WATCHDOG_ENABLED",
       "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S",
       "CLAUDE_P_BRIDGE_IO_WAIT_CAP_S",
       "CLAUDE_P_BRIDGE_SAFETY_CAP_S",
       "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S",
       "BRIDGE_IDLE_TIMEOUT_S",
       "BRIDGE_IO_WAIT_CAP_S",
       "BRIDGE_SAFETY_CAP_S",
       "BRIDGE_WATCHDOG_INTERVAL_S",
   })

   def _read_dsh_env_file() -> dict[str, str]:
       """Безопасно читает только несекретные настройки из ~/.dsh/.env.
       
       НЕ мутирует os.environ, гарантируя полную изоляцию от окружения pytest и подпроцессов.
       """
       env_file = Path.home() / ".dsh" / ".env"
       if not env_file.is_file():
           return {}
       res: dict[str, str] = {}
       try:
           with open(env_file, "r", encoding="utf-8") as f:
               for line in f:
                   line = line.strip()
                   if not line or line.startswith("#") or "=" not in line:
                       continue
                   if line.startswith("export "):
                       line = line[len("export "):].strip()
                   k, v = line.split("=", 1)
                   k = k.strip()
                   v = v.strip().strip("'\"")
                   if k in _ALLOWED_SETTINGS_KEYS:
                       res[k] = v
       except OSError:
           pass
       return res

   _DSH_ENV = _read_dsh_env_file()

   def _get_setting(name: str, fallback_name: str | None = None, default: str = "") -> str:
       """Двухступенчатый каскад чтения: os.environ -> _DSH_ENV -> fallback -> default."""
       for k in (name, fallback_name) if fallback_name else (name,):
           val = os.environ.get(k)
           if val is not None and val.strip():
               return val.strip()
           val = _DSH_ENV.get(k)
           if val is not None and val.strip():
               return val.strip()
       return default

   def _get_positive_float(name: str, fallback_name: str | None = None, default: float = 0.0) -> float:
       raw = _get_setting(name, fallback_name)
       if not raw:
           return default
       try:
           val = float(raw)
           return val if 0 < val < float("inf") else default
       except (ValueError, TypeError):
           return default
   ```

3. **Конфигурация параметров с каскадным fallback:**
   ```python
   def _is_watchdog_enabled() -> bool:
       raw = _get_setting("CLAUDE_P_BRIDGE_WATCHDOG_ENABLED", default="1").lower()
       return raw not in ("0", "false", "no", "off")

   CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S = _get_positive_float(
       "CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S", "BRIDGE_IDLE_TIMEOUT_S", 300.0
   )
   CLAUDE_P_BRIDGE_IO_WAIT_CAP_S = _get_positive_float(
       "CLAUDE_P_BRIDGE_IO_WAIT_CAP_S", "BRIDGE_IO_WAIT_CAP_S", 900.0
   )
   CLAUDE_P_BRIDGE_SAFETY_CAP_S = _get_positive_float(
       "CLAUDE_P_BRIDGE_SAFETY_CAP_S", "BRIDGE_SAFETY_CAP_S", 3600.0
   )
   CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S = _get_positive_float(
       "CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S", "BRIDGE_WATCHDOG_INTERVAL_S", 5.0
   )
   ```
   *Примечание по рантайму и семантике таймаутов:*
   - `idle_timeout_s` отслеживает паузы между фрагментами активности процесса. Согласно `core/watchdog.py:109-115`, I/O-grace действует при статусах процесса `S`, `D`, `I`, `U` (ожидание сокета/сети/диска). Поскольку дочерний процесс `claude` в ожидании сетевого ответа находится в состоянии `S` (sleep/wait), `AdaptiveTimeoutController` с активным `io_grace` расширяет окно неактивности до `CLAUDE_P_BRIDGE_IO_WAIT_CAP_S` (по умолчанию 900 с), предотвращая ложное прибивание при длительной генерации ответа.
   - `safety_cap_s` задаёт **абсолютный настенный потолок хода от момента старта** (`now - started_at >= effective_cap_s`, где `effective_cap_s = safety_cap_s - finish_reserve_s` = 3565 с при дефолте 3600 с). Он принудительно завершает ход даже при непрерывной генерации токенов для гарантированной защиты от бесконечного зацикливания генерации.
   - Сброс таймера активности: `_pump` передаёт в очередь `text`, `thinking` и `result`, на которые вызывается `record_activity(kind)`. При эмуляции инструментов вызовы формируются как фрагменты текста и регистрируются через `record_activity("text")`. Если процесс выполняет внутренние операции без передачи чанков в очередь, таймер активности обновляется в методе `check()` на основе прироста CPU или обнаружения дочерних процессов (`has_progress`).

4. **В методе `_execute` (в классе `Handler`):**
   - До блока `try:` объявляется контроллер и отметка времени последней проверки с безопасным чтением процесса (защита от отсутствия атрибута `proc` в `FakeRun`):
     ```python
     controller = None
     last_check_ts = time.monotonic()
     proc = getattr(run, "proc", None)
     proc_pid = getattr(proc, "pid", None) if proc is not None else None

     if _is_watchdog_enabled() and AdaptiveTimeoutController is not None and proc_pid:
         controller = AdaptiveTimeoutController(
             idle_timeout_s=CLAUDE_P_BRIDGE_IDLE_TIMEOUT_S,
             safety_cap_s=CLAUDE_P_BRIDGE_SAFETY_CAP_S,
             io_wait_cap_s=CLAUDE_P_BRIDGE_IO_WAIT_CAP_S,
             watchdog_interval_s=CLAUDE_P_BRIDGE_WATCHDOG_INTERVAL_S,
         )
         controller.register_pgid(proc_pid)
     ```
   - Цикл `while True:` оборачивается в `try...finally`:
     ```python
     try:
         while True:
             if _client_gone(self.connection):
                 return state("client_gone", 1)

             now = time.monotonic()
             if controller is not None and proc is not None and proc_pid and (now - last_check_ts >= controller.watchdog_interval_s):
                 last_check_ts = now
                 should_stop, reason, _ = controller.check(proc_pid)
                 if should_stop and reason in ("idle_timeout", "absolute_cap"):
                     _kill_group(proc)
                     return state("timeout", 1, f"claude-p watchdog: {reason}")
                 # Если reason == "child_exited" — это нормальный выход потомка,
                 # не убиваем процесс и ждем пока очередь дочитает событие "done"

             try:
                 kind, payload = run.q.get(timeout=POLL_INTERVAL_S)
             except queue.Empty:
                 if keepalive is not None and time.monotonic() - last_ka >= KEEPALIVE_S:
                     last_ka = time.monotonic()
                     if not keepalive():
                         return state("client_gone", 1)
                 continue

             if controller is not None and kind in ("text", "thinking", "result"):
                 controller.record_activity(kind)

             if kind == "text":
                 normalizer.feed_text(str(payload))
                 if gone[0]:
                     return state("client_gone", 1)
             elif kind == "thinking":
                 normalizer.feed_thinking(str(payload))
                 if gone[0]:
                     return state("client_gone", 1)
             elif kind == "result":
                 result_ev = payload
                 usage = payload.get("usage") or {}
             elif kind == "pump_error":
                 return state("pump_error", 1, str(payload))
             elif kind == "done":
                 normalizer.finish()
                 if gone[0]:
                     return state("client_gone", 1)
                 time.sleep(STDERR_DRAIN_S)
                 return state("done", payload, "".join(run.err_box))
     finally:
         if controller is not None:
             controller.close()
     ```

5. **В `@staticmethod _error_body(out: dict) -> Any`:**
   - В начало метода до проверок `is_error` и `rc != 0`:
     ```python
     st = str(out.get("state") or "")
     if st == "timeout":
         return {
             "message": str(out.get("err") or "upstream timeout"),
             "type": "upstream_timeout",
             "code": 504,
         }
     ```
   *(Примечание по SSE: в потоковом ответе ошибка транслируется через `format_stream_error_sse(..., finish_reason="stop")` согласно существующему контракту).*

### 3.2. Настройка в `bridges/opencode-zen-bridge/server.py`
Использование существующего хелпера `_zen_positive_float` (`:338`):
```python
STALL_TIMEOUT_S = _zen_positive_float(
    "OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S",
    60.0,
)
```

---

## 4. Верификационные требования и изоляция тестов

### 4.1. Набор тестов для claude-p вотчдога (`tests/test_claude_p_watchdog.py`)
Разрабатывается новый тестовый файл с детерминированными моками. Для полной изоляции от реального `~/.dsh/.env` разработчика используется модульная фикстура, которая изолирует `HOME` / `Path.home` и очищает окружение **до загрузки модуля** моста под уникальным именем:
```python
import importlib.util
from pathlib import Path
import sys
import uuid
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture(scope="module")
def isolated_claude_bridge(tmp_path_factory):
    tmp_home = tmp_path_factory.mktemp("fake_home")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", str(tmp_home))
        for key in list(sys.modules.get("os", __import__("os")).environ.keys()):
            if key.startswith("CLAUDE_P_BRIDGE_") or key.startswith("BRIDGE_"):
                mp.delenv(key, raising=False)
        module_name = f"claude_p_bridge_isolated_{uuid.uuid4().hex[:8]}"
        spec = importlib.util.spec_from_file_location(
            module_name,
            REPO_ROOT / "bridges" / "claude-p-bridge" / "server.py",
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = mod
        try:
            spec.loader.exec_module(mod)
            yield mod
        finally:
            sys.modules.pop(module_name, None)
```
Тестовые сценарии:
1. `test_claude_p_env_loader_security`: проверка, что `_read_dsh_env_file` изолирован, не мутирует `os.environ`, читает только разрешенные ключи из whitelist, последнее значение перезаписывает предыдущее, категорически игнорируя секреты (`CLAUDE_P_BRIDGE_KEY`, `BRIDGE_KEY`, `CODEX_LB_*`, `CURSOR_*`, `MUSE_*`).
2. `test_watchdog_timeout_trigger`: мокируется `_kill_group` (защита от вызова `os.killpg` на фейковом pid). Проверка, что при возврате `(True, "idle_timeout", ...)` вызывается мок `_kill_group`, возвращается статус `state("timeout", 1, ...)` и `_error_body` выдаёт код 504.
3. `test_child_exited_no_false_timeout`: проверка, что при возврате `(True, "child_exited", ...)` ход не прерывается ложным таймаутом, а очередь успешно дочитывает `done`.
4. `test_watchdog_throttle`: проверка, что `controller.check()` вызывается не чаще чем раз в `controller.watchdog_interval_s`.
5. `test_record_activity_calls`: проверка вызова `record_activity(kind)` на события `text`, `thinking` и `result`.
6. `test_controller_closed_in_finally`: проверка гарантированного вызова `controller.close()` при любом исходе хода.

### 4.2. Изоляция тестов конфигурации таймаутов (`tests/test_stream_timeout_config.py`)
1. Во всех тестах функции `parse_live_write_timeout` (`:9-37`) добавить `monkeypatch.delenv("BRIDGE_CLIENT_WRITE_TIMEOUT_S", raising=False)` для защиты от фонового окружения.
2. Добавить тест `test_live_write_timeout_priority`:
   - При валидном `BRIDGE_CLIENT_WRITE_TIMEOUT_S` берется оно.
   - При невалидном `BRIDGE_CLIENT_WRITE_TIMEOUT_S` и валидном `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` берется legacy.
   - При обоих невалидных возвращается переданный `default`.

### 4.3. Интеграционный прогон регрессий:
Обязательный прогон полного набора тестов моста:
`uv run pytest -o pythonpath=. tests/test_claude_bridge.py tests/test_claude_p_watchdog.py tests/test_stream_timeout_config.py tests/test_stream_resilience.py tests/test_http_presend_resilience.py` -> 100% PASS.
