# Goal: dsh-timeout-finish-reason-20261102

- **Результат:** Устранено ложное предупреждение «Output token limit reached» в DeepSeek Harness при срабатывании таймаута хода в agy-bridge.
- **Критерий успеха:** `finish_reason="stop"` по умолчанию при graceful timeout, настраиваемость через `AGY_GRACEFUL_TIMEOUT_FINISH_REASON`, 100% зелёные тесты `pytest tests/test_agy_bridge_resilience.py`, вердикт PASS Совета Тимлидов по коду (`receipts/code-panel.json`).
- **Режим:** LIGHT (CEL).
