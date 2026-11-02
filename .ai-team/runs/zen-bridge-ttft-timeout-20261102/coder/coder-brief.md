# Бриф роли Coder: Раздельные таймауты TTFT (25s) и Idle (15s) в opencode-zen-bridge

Скилл роли: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

Ты — внешний исполнитель роли `Coder` (модель `gpt-6.1-sol`, effort: `high`, транспорт: `codex exec`).
Твоя задача — реализовать утверждённое архитектурное решение (AD-001 из `.ai-team/runs/zen-bridge-ttft-timeout-20261102/architecture/architecture-packet.json`) по замене монолитного дедлайна 25с на раздельные таймауты TTFT (25с) и Idle (15с) в `bridges/opencode-zen-bridge/server.py` с покрытием тестами в `tests/test_bridges_speedup_resilience.py`.

## 1. Контекст и инварианты
- Проект: `cli-agent-bridge` (OpenAI-compatible фасад и шлюз мостов).
- Главный принцип: универсальность и независимость от вендоров. Запрещена правка вендорского исходного кода. Изменения только в нашем репозитории.
- Запрет на хардкод параметров: таймауты должны конфигурироваться через переменные окружения с безопасными значениями по умолчанию.
- Сохранение 100% обратной совместимости API: честный возврат 504 Gateway Timeout / terminal SSE error при превышении TTFT (до первого токена) или Idle (между чанками).

## 2. Что нужно реализовать

### А. В `bridges/opencode-zen-bridge/server.py`:
1. В блоке таймаутов (строки ~340–375):
   - Реализовать функцию `_zen_ttft_timeout(model: str, prompt: str) -> float`:
     Для моделей из `BRIDGE_ZEN_TIMEOUT_MODELS` и `deepseek-v4.1-flash-free` при длине `len(prompt.encode("utf-8")) > _positive_int(os.environ.get("BRIDGE_ZEN_LARGE_PROMPT_BYTES"), 8192)`:
     возвращает `min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TTFT_TIMEOUT_S", _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0)))`.
     Для остальных моделей — возвращает `TIMEOUT_S`.
   - Реализовать функцию `_zen_idle_timeout() -> float`:
     возвращает `_zen_positive_float("BRIDGE_ZEN_IDLE_TIMEOUT_S", 15.0)`.
   - Реализовать функцию `_zen_total_timeout(model: str = "", prompt: str = "") -> float`:
     возвращает `min(TIMEOUT_S, _zen_positive_float("BRIDGE_ZEN_TOTAL_TIMEOUT_S", min(180.0, TIMEOUT_S)))`.
   - Сохранить функцию `_zen_execution_timeout(model: str, prompt: str) -> float` как обёртку/синоним `_zen_ttft_timeout(model, prompt)` для полной обратной совместимости с существующими тестами и вызовами.

2. В классе `_RequestAttempts` (строки ~2938):
   - Добавить сохранение времени старта: `self.t0 = time.monotonic()`.

3. При инициализации `attempts`:
   - В местах `_RequestAttempts(res, time.monotonic() + ...)` (строки ~6431, 6572, 7898, 9287) передавать дедлайн на базе `_zen_total_timeout(model, prompt)` (а не жесткий 25с дедлайн).
   - В `_set_zen_policy` (строка ~7032): `self._zen_targeted = _zen_ttft_timeout(model, prompt) < TIMEOUT_S`.
   - При вычислении `t0` для передачи в `_serve_one_attempt` (строки ~7388, 8975):
     использовать `getattr(attempts, "t0", attempts.deadline - _zen_total_timeout(model, prompt))`.
   - Аналогично для таймеров статуса (строки ~8006, 8260, 8393, 8412):
     использовать `getattr(attempts, "t0", attempts.deadline - _zen_total_timeout(model, prompt)) + FIRST_STATUS_DELAY_S`.

4. В функции `_serve_one_attempt` (строки ~4365–5085):
   - Получить локальные таймауты:
     `ttft_timeout = _zen_ttft_timeout(model, prompt)`
     `idle_timeout = _zen_idle_timeout()`
   - Убедиться, что `last_token_at = prompt_send_start` (или `t0`).
   - В основном цикле ожидания событий `while time.monotonic() < attempt_deadline:`:
     - Если `result["first_token_at"] is None`:
       проверять `if now - prompt_send_start >= ttft_timeout:` ->
       `result["exit_reason"] = "timeout"`, `result["delivered"] = _is_delivered()`, прерывать цикл (`break`).
     - Если `result["first_token_at"] is not None`:
       проверять `if now - last_token_at >= idle_timeout:` ->
       `result["exit_reason"] = "timeout"`, `result["delivered"] = _is_delivered()`, прерывать цикл (`break`).
     - При получении каждого токена (reasoning, content/text, tool delta/called) обновлять:
       `last_token_at = time.monotonic()`.

5. В потоковом watchdog-режиме (строки ~8300–8325):
   - Согласовать проверку таймаутов с `ttft_timeout` и `idle_timeout`.

### Б. В `tests/test_bridges_speedup_resilience.py`:
1. Убедиться, что тест `test_zen_byte_timeout_selection` проходит зелёным (он проверяет `_zen_execution_timeout`).
2. Добавить новый тест `test_zen_split_timeouts`, проверяющий:
   - Значения по умолчанию: `_zen_ttft_timeout` (25.0s для targeted, TIMEOUT_S для остальных), `_zen_idle_timeout` (15.0s), `_zen_total_timeout` (180.0s).
   - Чтение переменных окружения: `BRIDGE_ZEN_TTFT_TIMEOUT_S`, `BRIDGE_ZEN_IDLE_TIMEOUT_S`, `BRIDGE_ZEN_TOTAL_TIMEOUT_S`.
   - Fallback на `BRIDGE_ZEN_TIMEOUT_S` для TTFT, если `BRIDGE_ZEN_TTFT_TIMEOUT_S` не задан.
3. Добавить тест `test_zen_stream_continues_past_ttft`, эмулирующий стрим, где первый токен пришёл на 1-й секунде, а генерация длится дольше TTFT (например, чанки каждые 0.05с в течение 0.3с при ttft=0.1s и idle=0.2s), и подтверждающий, что стрим НЕ обрывается преждевременно по таймауту 0.1с.

## 3. Критерии приёмки
- Запуск: `PYTHONPATH=. .venv/bin/pytest tests/test_bridges_speedup_resilience.py -v` завершается с кодом 0 (100% pass).
- Регрессионный сьют: `PYTHONPATH=. .venv/bin/pytest tests/test_request_attribution.py tests/test_bridge_strict.py -v` проходит успешно (exit 0).
