# Бриф роли Coder: Раздельные таймауты TTFT (25s) и Idle (15s) в opencode-zen-bridge

Скилл роли: `~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/bugfix.md`

## 0. Нормативный контекст
- Задача выполняется по пресету `~/Мой диск/skils/ai-sdlc/universal/analyst-teamlead/SKILL.md` (прямая директива владельца: «по скилу аналтик техлид»).
- По скиллу пресета:
  «Фаза 2: Одиночный архитектор (`architect-software-product`) с лёгким лупом. Коллегиальная архитектурная панель НЕ созывается... Coder стартует сразу после валидного `ARCH_GATE_PASS` approved-пакета Архитектора.»
- Архитектурный пакет утверждён: `validate_architecture_packet.py --phase approved` exit 0, sha256=`e5290e3ab9d3e9da69dd6620e18a9cb1f9baa1b7725c24499b0b06041ae298f1`.
- Совет Тимлидов с независимыми судьями и `panel-proof.json` запускается в Фазе 3 (`teamlead-gate`, `mode=code`) ПОСЛЕ реализации кода для приёмки MR.

## 1. Роль и задача
Ты — внешний исполнитель роли `Coder` (модель `claude-sonnet-5-5`, effort: `high`, транспорт: `claude -p`).
Твоя задача — реализовать утверждённое архитектурное решение (AD-001 из `.ai-team/runs/zen-bridge-ttft-timeout-20261102/architecture/architecture-packet.json`): заменить жесткий дедлайн 25с на раздельные таймауты TTFT (25с) и Idle (15с) в `bridges/opencode-zen-bridge/server.py` с покрытием тестами в `tests/test_bridges_speedup_resilience.py`.

## 2. Инварианты
- Изменения вносятся ТОЛЬКО в нашем коде `cli-agent-bridge` (запрет на правку вендорских пакетов/бинарников).
- Все параметры конфигурируемы через переменные окружения без хардкода:
  - `BRIDGE_ZEN_TTFT_TIMEOUT_S` (fallback на `BRIDGE_ZEN_TIMEOUT_S`, default 25.0s)
  - `BRIDGE_ZEN_IDLE_TIMEOUT_S` (default 15.0s)
  - `BRIDGE_ZEN_TOTAL_TIMEOUT_S` (default 180.0s)
- Сохранение 100% обратной совместимости API и существующих тестов.

## 3. Что конкретно нужно сделать

### А. В `bridges/opencode-zen-bridge/server.py`:
1. В районе строк 345–375:
   - Реализовать:
   ```python
   def _zen_ttft_timeout(model: str, prompt: str) -> float:
       """Сужение таймаута до первого токена (TTFT) только для целевых моделей на большом промпте."""
       models = {
           "deepseek-v4.1-flash-free",
           *filter(
               None, re.split(r"[,\s]+", os.environ.get("BRIDGE_ZEN_TIMEOUT_MODELS", ""))
           ),
       }
       threshold = _positive_int(os.environ.get("BRIDGE_ZEN_LARGE_PROMPT_BYTES"), 8192)
       if model in models and len(prompt.encode("utf-8")) > threshold:
           return min(
               TIMEOUT_S,
               _zen_positive_float(
                   "BRIDGE_ZEN_TTFT_TIMEOUT_S",
                   _zen_positive_float("BRIDGE_ZEN_TIMEOUT_S", 25.0),
               ),
           )
       return TIMEOUT_S

   def _zen_idle_timeout() -> float:
       """Таймаут неактивности между чанками стрима после получения первого токена."""
       return _zen_positive_float("BRIDGE_ZEN_IDLE_TIMEOUT_S", 15.0)

   def _zen_total_timeout(model: str = "", prompt: str = "") -> float:
       """Общий дедлайн запроса (по умолчанию 180 с или TIMEOUT_S)."""
       return min(
           TIMEOUT_S,
           _zen_positive_float("BRIDGE_ZEN_TOTAL_TIMEOUT_S", min(180.0, TIMEOUT_S)),
       )

   def _zen_execution_timeout(model: str, prompt: str) -> float:
       """Обратная совместимость: возвращает ttft_timeout для targeted моделей."""
       return _zen_ttft_timeout(model, prompt)
   ```

2. В классе `_RequestAttempts` (строки ~2948):
   - Добавить: `self.t0 = time.monotonic()`.

3. При создании `_RequestAttempts` (строки ~6431, 6572, 7898, 9287):
   - Заменить `time.monotonic() + _zen_execution_timeout(...)` на `time.monotonic() + _zen_total_timeout(...)`.
   - В `_set_zen_policy` (строка ~7032): `self._zen_targeted = _zen_ttft_timeout(model, prompt) < TIMEOUT_S`.
   - При вычислении `t0` для `_serve_one_attempt` (строки ~7388, 8975) и таймеров статуса (строки ~8006, 8260, 8393, 8412):
     использовать `getattr(attempts, "t0", attempts.deadline - _zen_total_timeout(model, prompt))`.

4. В `_serve_one_attempt` (строки ~4365–5085):
   - Получить `ttft_timeout = _zen_ttft_timeout(model, prompt)` и `idle_timeout = _zen_idle_timeout()`.
   - Убедиться, что `last_token_at = prompt_send_start`.
   - В цикле `while time.monotonic() < deadline:`:
     - Если `result["first_token_at"] is None`:
       `if now - prompt_send_start >= ttft_timeout:` -> `result["exit_reason"] = "timeout"`, `result["delivered"] = _is_delivered()`, `break`.
     - Если `result["first_token_at"] is not None`:
       `if now - last_token_at >= idle_timeout:` -> `result["exit_reason"] = "timeout"`, `result["delivered"] = _is_delivered()`, `break`.
     - При получении чанка (reasoning, content/text, tool event): `last_token_at = time.monotonic()`.

5. В потоковом watchdog-режиме (строки ~8300–8325):
   - Согласовать проверку `now_s - attempt_start > ttft_timeout` и `now_s - last_token_at > idle_timeout`.

### Б. В `tests/test_bridges_speedup_resilience.py`:
1. Убедиться, что `test_zen_byte_timeout_selection` проходит (он проверяет `_zen_execution_timeout`).
2. Добавить тесты:
   - `test_zen_split_timeouts`: проверяет дефолты и чтение `BRIDGE_ZEN_TTFT_TIMEOUT_S`, `BRIDGE_ZEN_IDLE_TIMEOUT_S`, `BRIDGE_ZEN_TOTAL_TIMEOUT_S`.
   - `test_zen_stream_continues_past_ttft`: эмулирует стрим, где токены поступают каждые 0.05с в течение 0.3с при TTFT=0.1s и idle=0.2s, и подтверждает, что стрим НЕ обрывается на 0.1с дедлайне, а успешно доставляется полностью.

## 4. Верификация
- Запустить: `PYTHONPATH=. .venv/bin/pytest tests/test_bridges_speedup_resilience.py -v`.
- Все тесты должны пройти с exit 0.
