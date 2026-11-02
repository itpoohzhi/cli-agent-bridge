# Evidence White — Факты as-is по статическим таймаутам мостов

## 1. bridges/agy-bridge/server.py
- [W-01] В строках 230–240 заданы статические таймауты: `timeout_s = 1800`, `idle_timeout_s = 300.0`, `ext_idle_timeout_s = 1800.0`, `ext_max_timeout_s = 3600.0`.
- [W-02] В строке 2952 флаг `extended_timeout_enabled: bool = False` по умолчанию выключен. При дефолтной конфигурации стрим прибивается через 1800 с даже при постоянном потоке токенов.
- [W-03] В строках 6130–6145 при вызове `_TimedSseReader` дедлайн тишины привязан к локальному `ext_idle_timeout_s`, но при выключенном флаге `extended_timeout_enabled` жесткий настенный `timeout_s` (1800 с) прерывает сеанс.

## 2. bridges/claude-p-bridge/server.py
- [W-04] В строках 600–615 цикл чтения `run.q.get(timeout=POLL_INTERVAL_S)` не имеет адаптивного счетчика тишины (`idle_timeout_s`) и аварийного `safety_cap_s`. Если дочерний процесс CLI зависнет в мертвом блокирующем ожидании, цикл будет крутиться бесконечно, удерживая слот семафора `_slots`.
- [W-05] В строке 525 `time.monotonic() - waited > QUEUE_TIMEOUT_S` (900 с) — жесткий таймаут ожидания очереди, не продлевающийся при наличии активности в очереди.

## 3. bridges/opencode-zen-bridge/server.py
- [W-06] В строках 4901–4910 зафиксированы жесткие статические таймауты: `first_token_timeout` (120 с) и `stall_timeout` (60–120 с). При длительных фазах размышлений (deep reasoning), когда модель думает > 120 с без выдачи первых токенов, мост принудительно обрывает соединение с `first_token_timeout`.
- [W-07] Дедлайн ожидания SSE-событий в `_subscribe_deadline` не пересчитывается при получении сервисных или reasoning-кадров, что приводит к преждевременному разрыву длинных запросов.

## 4. adapters/passthrough_adapter.py
- [W-08] Успешно внедрен и проверен паттерн Sliding Activity Window: разделение `last_input` (keepalive) и `last_upstream` (полезные токены), динамический расчет `remaining = min(idle_remaining, safety_remaining)`. Все 78 тестов стриминга проходят зелёными (100% PASS).
