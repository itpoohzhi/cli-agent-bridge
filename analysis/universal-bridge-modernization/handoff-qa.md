# Handoff-пакет для QA: Модернизация cli-agent-bridge

## 1. Область тестирования
1. **Параметризация лимитов b_guard и REQ-003:**
   - Значение по умолчанию: `BRIDGE_INSTR_LIMIT = 120000` (байт).
   - Чтение из `BRIDGE_INSTR_LIMIT` и fallback на `DROID_DSH_BRIDGE_INSTR_LIMIT`.
   - Граничные проверки: блок 120 000 проходит (True), 120 001 отклоняется (False/REQ003_SIZE_EXCEEDED).
   - Работа `b_guard.check_installed()` на актуальном размере канона (62 889 байт): статус `exit_code <= 1` (OK / warning), отсутствие перехода в `state = "unsafe"`.
2. **Отсутствие ложных отказов 503 в HTTP-шлюзе (:9882):**
   - Запросы к модели `muse-wonder-full-1.0` с блоком `agent-instructions` проходят с кодом 200 OK.
   - Запуск нативного `muse serve` и потоковая передача `reasoning_content` и `content`.
3. **Регрессионная устойчивость набора тестов:**
   - Все тесты в `tests/test_b_guard.py` должны проходить (100% PASS).
   - Все 72 теста в `tests/test_muse_adapter.py` должны проходить (100% PASS).
   - Все тесты интеграции хаба в `tests/test_hub_integration.py` должны проходить.

## 2. Тестовая матрица краевых случаев

| ID | Тест-кейс | Входные данные | Ожидаемый результат |
|---|---|---|---|
| TC-01 | Проверка канона при дефолтном лимите | canon_size=62889, limit=120000 | exit_code=1 (LOW_MARGIN_LOWER), REQ003_SIZE_EXCEEDED отсутствует |
| TC-02 | Проверка канона при выровненном maxBytes | canon_size=62889, maxBytes=121034, limit=120000 | exit_code=0 (чистый PASS, 0 warnings, 0 errors) |
| TC-03 | Переопределение лимита через BRIDGE_INSTR_LIMIT | BRIDGE_INSTR_LIMIT=150000 | BLOCK_LIMIT=150000 в runtime |
| TC-04 | Fallback на DROID_DSH_BRIDGE_INSTR_LIMIT | DROID_DSH_BRIDGE_INSTR_LIMIT=130000 (BRIDGE_INSTR_LIMIT unset) | BLOCK_LIMIT=130000 в runtime |
| TC-05 | Защита от невалидного значения лимита | BRIDGE_INSTR_LIMIT=garbage | Безопасный откат на дефолт 120000 |
| TC-06 | Живой запрос к Muse через хаб :9882 | POST /v1/chat/completions (model=muse-wonder-full-1.0) | HTTP 200, SSE stream c reasoning_content |
