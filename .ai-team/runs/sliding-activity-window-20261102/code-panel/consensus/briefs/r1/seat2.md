Ваша ролевая шляпа — РЕАЛИСТ. Сфокусируйтесь на реализуемости, простоте внедрения, минимальности диффа и эксплуатационных нюансах.
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
# Teamlead Council Code Review Package — `sliding-activity-window-20261102` (Rev 1)

## 1. Задача и бизнес-контекст (Task Envelope)
- **Инцидент:** В клиенте DeepSeek Harness при работе с моделью `Gemini 3.8 Flash (AGY) High` происходил обрыв стрима: `This turn failed upstream stream failed PI_AI_ERROR` ровно на 420-й секунде (7 минут).
- **Корневая причина:** В `adapters/passthrough_adapter.py` был зашит статический настенный лимит `DEFAULT_TOTAL_TIMEOUT_S = 420.0`. При вызове любых passthrough-моделей ровно через 420 секунд адаптер принудительно сбрасывал соединение с `TimeoutError`, даже если апстрим непрерывно генерировал токены и `reader.last_progress` регулярно обновлялся.
- **Требование пользователя:** Заменить статический настенный таймаут на интеллектуальное скользящее окно активности: если токены поступают — соединение живёт; счётчик неактивности сбрасывается при каждом полезном чанке апстрима; защита от вечного зацикливания через аварийный safety cap.
- **Архитектурный вердикт:** Архитектурный пакет утвержден (`validate_architecture_packet.py --phase approved` PASS sha256=77263d92f451c54139ce775b54e6bd6c2e25b12a2ca0ab654fe81315d90a6146).

---

## 2. Реализованные решения и паттерны отказоустойчивости

### 2.1. Паттерн Sliding Activity Window (`adapters/passthrough_adapter.py`)
- В `PassthroughLimits` добавлено поле `safety_cap_s: float = DEFAULT_SAFETY_CAP_S (3600.0)`.
- Поддержка конфигурации через переменную окружения `BRIDGE_SAFETY_CAP_S` (дефолт 3600.0 с).
- В `_TimedSseReader`:
  - `safety_deadline = start_time + limits.safety_cap_s` (абсолютный аварийный потолок).
  - Разделены счетчики активности: `last_input` (для каденса локальных keepalive-комментариев) и `last_upstream` (для фиксации реальных входящих байтов от апстрима, предотвращая самопродление через собственные пинги).
  - Адаптивный расчет дедлайна неактивности (тишины):
    `activity_base = self.last_progress if self.last_progress is not None else self.last_upstream`
    `idle_remaining = activity_base + self.limits.idle_timeout_s - now`
  - Таймаут ожидания очереди чанков вычисляется динамически: `remaining = min(idle_remaining, safety_remaining)`.
  - При получении каждого полезного чанка от апстрима `last_upstream` сбрасывается в `time.monotonic()`, продлевая скользящее окно.
- В `PassthroughAdapter.handle()`:
  - При обнаружении стриминга (`resp.status == 200` и `text/event-stream` в `Content-Type`) выставляется флаг `streaming.set()`.
  - Таймаут-вотчер отключает настенный дедлайн после перехода в режим стриминга, передавая управление адаптивному скользящему окну ридера (`_TimedSseReader`).

### 2.2. Синхронизация тестов и контрактов (`tests/test_stream_resilience.py`, `tests/test_http_presend_resilience.py`)
- В `tests/test_stream_resilience.py` добавлены 4 unit-теста:
  - `test_passthrough_limits_defaults_from_empty_env`: валидация дефолтов из пустого env (обратная совместимость).
  - `test_passthrough_limits_custom_env`: валидация считывания `BRIDGE_SAFETY_CAP_S`.
  - `test_passthrough_sliding_activity_window_extends_stream`: подтверждение, что стрим живет дольше `total_timeout_s`, если поступают токены.
  - `test_passthrough_safety_cap_terminates_infinite_stream`: подтверждение срабатывания аварийного `safety_cap_s` при бесконечном потоке.
- В `tests/test_http_presend_resilience.py`:
  - Ассерты синхронизированы с утвержденным контрактом structural DONE (`assert TERMINAL not in body`).

### 2.3. Нормативная база и скилы разработки
- В канон стоп-кодов `~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/references/hl-resilience-gates.md` добавлен обязательный стоп-код `L-LIVE/v1` (запрет прибивания активных стримов по настенным часам).
- В проектный `AGENTS.md` зафиксирован инвариант L2: сброс таймера неактивности и сдвиг дедлайна при получении каждого полезного чанка.

---

## 3. Манифест файлов кандидата (Candidate Manifest)
1. `adapters/passthrough_adapter.py`: `DEFAULT_SAFETY_CAP_S`, `PassthroughLimits.safety_cap_s`, `_TimedSseReader` sliding deadline, `last_upstream`, `streaming` event in `handle()`.
2. `tests/test_stream_resilience.py`: 4 новых unit-теста на скользящее окно и safety cap.
3. `tests/test_http_presend_resilience.py`: синхронизация проверки never replays с structural DONE.
4. `AGENTS.md`: инвариант L2 скользящего окна активности.
5. `~/Мой диск/skils/ai-sdlc/universal/orchestrate-coder-reviewer-summarizer/references/hl-resilience-gates.md`: стоп-код `L-LIVE/v1`.

---

## 4. Результаты верификации (Clean-Room Verification)
- `tests/test_stream_resilience.py`: **65 passed in 2.65s** (100% PASS).
- `tests/test_http_presend_resilience.py`: **13 passed in 3.19s** (100% PASS).
- `tests/test_passthrough_adapter.py`: **95 passed in 26.85s** (100% PASS).
- `ruff check`: All checks passed!
- Всего целевых и интеграционных тестов: **173 passed** (0 failures).

