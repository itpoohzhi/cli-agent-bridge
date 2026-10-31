# Handoff-пакет для Coder (Разработчика): Модернизация cli-agent-bridge

## 1. Задачи и границы изменений
1. **`tools/b_guard.py`:**
   - Заменить жесткую константу `BLOCK_LIMIT = 60000` на динамическое чтение:
     ```python
     def _get_block_limit() -> int:
         raw = os.environ.get("BRIDGE_INSTR_LIMIT", os.environ.get("DROID_DSH_BRIDGE_INSTR_LIMIT", "120000"))
         try:
             val = int(raw)
             return val if val > 0 else 120000
         except (ValueError, TypeError):
             return 120000

     BLOCK_LIMIT = _get_block_limit()
     ```
   - В функции `check_installed(maxbytes, cwds, canon_path, limit: Optional[int] = None)` поддержать передачу `limit` с fallback на актуальный `BLOCK_LIMIT`.
   - В `self_test()` проверять граничные условия динамически вокруг текущего `BLOCK_LIMIT`.
2. **`server.py`:**
   - Заменить чтение `INSTR_BLOCK_LIMIT`:
     ```python
     INSTR_BLOCK_LIMIT = int(os.environ.get("BRIDGE_INSTR_LIMIT", os.environ.get("DROID_DSH_BRIDGE_INSTR_LIMIT", "120000")))
     ```
   - В `InstructionGuard._evaluate()` передавать актуальный `INSTR_BLOCK_LIMIT` в `b_guard.check_installed()`.
   - Добавить нейтральные переменные для авторизации и хоста:
     `BRIDGE_KEY = os.environ.get("BRIDGE_KEY", os.environ.get("DROID_DSH_BRIDGE_KEY", ""))`
     `BRIDGE_HOST = os.environ.get("BRIDGE_HOST", os.environ.get("DROID_DSH_BRIDGE_HOST", "127.0.0.1"))`
     `BRIDGE_PORT = int(os.environ.get("BRIDGE_PORT", os.environ.get("DROID_DSH_BRIDGE_PORT", "9882")))`
3. **`start.sh`:**
   - Обновить скрипт запуска: поддерживать экспорт `BRIDGE_HOST`, `BRIDGE_PORT`, `BRIDGE_KEY` и `BRIDGE_INSTR_LIMIT` с fallback на `DROID_*`.
   - Очистить вводные комментарии от упоминаний Droid как исключительного владельца моста.
4. **Тесты `tests/test_b_guard.py`:**
   - Обновить тесты границ `test_rw004_block_boundary...`, `test_rw004_cli_line_boundary...`, `test_tm018_limit_boundary...`, `test_tm018_canon_growth...`, `test_tm018_live_check_subprocess` с учетом нового значения по умолчанию 120 000 байт.

## 2. Non-Goals (что не делаем в этой итерации)
- Не трогаем сторонние вендорские приложения (DSH, Claude Code).
- Не удаляем принудительно фоновые standalone-мосты на портах :9887, :9883, :9881 до завершения полной приёмки хаба :9882.
