# Consolidated RCA Decision — Рекомендация аналитической панели

## 1. Корневая причина (RCA)
Исторически каждый мост (`agy-bridge`, `opencode-zen-bridge`, `claude-p-bridge`) реализовывал собственную ad-hoc логику таймаутов, используя жесткие статические настенные таймеры (`timeout_s`, `stall_timeout`, `first_token_timeout`). При длительных фазах генерации или размышлений модели (deep reasoning / tool use) эти таймеры принудительно обрывали живое соединение, несмотря на непрерывную генерацию полезных чанков.

## 2. Рекомендация архитектурного выбора
Коллегия аналитиков единогласно рекомендует реализацию **Варианта V2**:
1. Разработка универсального модуля ядра `core/sliding_window.py`:
   - `SlidingActivityWindow`: расчет дедлайна по формуле `deadline = min(last_activity + idle_timeout_s, start_time + safety_cap_s)`.
   - `is_useful_chunk(chunk)`: детерминированное распознавание полезных данных (непустой `content`, `reasoning_content`, `tool_calls`) и игнорирование пустых комментариев/heartbeat.
   - Graceful drain очереди перед генерацией терминального кадра при наступлении таймаута.
2. Подключение мостов через тонкую трансляцию транспорта:
   - `adapters/passthrough_adapter.py` (уже переведен и проверен).
   - `bridges/claude-p-bridge/server.py` (замена бесконечного цикла на `SlidingActivityWindow`).
   - `bridges/agy-bridge/server.py` (унификация дедлайна с ядром).
   - `bridges/opencode-zen-bridge/server.py` (унификация `stall_timeout` с активностью токенов).
