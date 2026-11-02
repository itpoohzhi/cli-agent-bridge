Ваша ролевая шляпа — ВИЗИОНЕР. Сфокусируйтесь на архитектурной согласованности, расширяемости и долгосрочной системной гармонии.
РАУНД: R1 (слепой, независимый)

Ты — независимый судья экспертной панели. Проверь пакет ниже заново,
не опираясь на чужие выводы: их в этом брифе нет.
Каждую находку оформи отдельным блоком вида:
### F-001 BLOCKER-SAFETY|BLOCKER-OPINION|NON_BLOCKING — суть одной строкой
с доказательством file:line. BLOCKER-SAFETY — только доказанный дефект
безопасности, утечка данных или сбой обязательных тестов.
Первыми двумя строками ответа повтори PANEL-NONCE и ARTIFACT-SHA256
из конца этого брифа. Последняя непустая строка ответа — строго
VERDICT: ACCEPT | PASS | NEEDS WORK | RED FLAG.

ПАКЕТ:
# Teamlead Council Code Review Package — `all-bridges-sliding-window-20261102` (Rev 1)

## 1. Задача и бизнес-контекст (Task Envelope)
- **Цель:** Сквозное устранение жестких настенных лимитов и внедрение скользящих окон активности во все мосты контура (`bridges/claude-p-bridge`, `bridges/opencode-zen-bridge`, `server.py`), где происходит генерация, передача или обработка стримов.
- **Архитектурный базис:** Архитектурный пакет утверждён Советом Тимлидов: `.ai-team/runs/all-bridges-sliding-window-20261102/architecture/architecture-packet.json` (`PANEL PROOF: .ai-team/runs/all-bridges-sliding-window-20261102/panel/arch/r4/panel-proof.json sha256=e5231c43ea8747233dc63b36be2e0aca75fc50fa0a47a80132254a20753502d7 verify_panel_proof exit=0`).
- **Исполнитель:** Coder (`claude-sonnet-5-5-high` через `claude -p`) в изолированной песочнице с последующим переносом и 100% подтверждением тестами.

---

## 2. Реализованные решения

### 2.1. Вотчдог со скользящим окном активности в `bridges/claude-p-bridge/server.py` (AD-001)
- Добавлен защищенный импорт `from core.watchdog import AdaptiveTimeoutController` сразу после настройки `sys.path` (строки 58-61).
- В `Handler._execute`:
  - Безопасное получение процесса и PID через `getattr(run, 'proc', None)` и `getattr(proc, 'pid', None)`.
  - Инициализация `AdaptiveTimeoutController` с параметрами `idle_timeout_s`, `safety_cap_s`, `io_wait_cap_s`, `watchdog_interval_s`.
  - Цикл стриминга обёрнут в `try...finally: if controller is not None: controller.close()`.
  - Троттлинг вызовов `controller.check(proc_pid)` по интервалу `watchdog_interval_s`.
  - Корректная обработка выхода: `child_exited` не прерывает ход, а позволяет дочитать очередь `done`; таймауты `idle_timeout` и `absolute_cap` завершают группу процесса через `_kill_group(proc)` и возвращают `state("timeout", 1)`.
  - Регистрация активности процесса через `controller.record_activity(kind)` на события `text`, `thinking` и `result`.
  - В `@staticmethod _error_body`: перехват статуса `timeout` и возврат кода 504 `upstream_timeout`.

### 2.2. Защищённый парсер настроек `~/.dsh/.env` (AD-002)
- Реализована функция `_read_dsh_env_file() -> dict[str, str]` со строгим whitelist `_ALLOWED_SETTINGS_KEYS`.
- Исключены любые секреты и авторизационные ключи (`*_KEY`).
- Функция **НЕ мутирует `os.environ`**, гарантируя полную изоляцию от окружения pytest и подпроцессов.
- Поддерживается синтаксис `export KEY=VAL`, снятие кавычек и перезапись дубликатов последним значением (паритет с shell).
- Двухступенчатый каскад `_get_setting` и `_get_positive_float`: `CLAUDE_P_BRIDGE_*` -> `BRIDGE_*` -> `default`.

### 2.3. Конфигурируемый `STALL_TIMEOUT_S` в `bridges/opencode-zen-bridge/server.py` (AD-003)
- Значение `STALL_TIMEOUT_S` читается через существующий изолированный хелпер `_zen_positive_float("OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S", 60.0)`, исключая жесткий хардкод.

### 2.4. Агент-агностический двухступенчатый fallback в `server.py` (AD-004)
- В функции `parse_live_write_timeout(default: float = 30.0) -> float` реализован приоритет:
  1. `BRIDGE_CLIENT_WRITE_TIMEOUT_S` (универсальный системный ключ);
  2. `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S` (обратная совместимость с Droid);
  3. `default` (30.0 с).

### 2.5. Детерминированные тесты L1 и изоляция окружения
- Создан новый тестовый модуль `tests/test_claude_p_watchdog.py` (7 тестов) с модульной фикстурой `isolated_claude_bridge`:
  - Изоляция `HOME` во временной папке;
  - Удаление ключей с префиксами `CLAUDE_P_BRIDGE_` и `BRIDGE_`;
  - Импорт моста под уникальным именем и `sys.modules.pop` в `finally`;
  - Тестирование безопасности парсера env, срабатывания таймаутов, пропуска `child_exited`, троттлинга проверок, регистрации активности и гарантированного закрытия контроллера.
- В `tests/test_stream_timeout_config.py` добавлена очистка `BRIDGE_CLIENT_WRITE_TIMEOUT_S` во все тесты и новый тест `test_live_write_timeout_priority`.

---

## 3. Манифест файлов кандидата (Candidate Manifest)
1. `bridges/claude-p-bridge/server.py`
2. `bridges/opencode-zen-bridge/server.py`
3. `server.py`
4. `tests/test_claude_p_watchdog.py`
5. `tests/test_stream_timeout_config.py`

---

## 4. Результаты верификации (Clean-Room Verification)
- Прогон регрессионного набора мостов и resilience:
  `uv run pytest -o pythonpath=. tests/test_claude_bridge.py tests/test_claude_p_watchdog.py tests/test_stream_timeout_config.py tests/test_stream_resilience.py tests/test_http_presend_resilience.py`
  **128 passed in 13.40s** (100% PASS).
- `ruff check`: All checks passed.

