# 0018 — Очистка SwiftBar-мостов, масштабирование хаба до 128 сессий и конфигурируемость

## Status

Accepted. Материализация архитектурного ADR-001 из
`/tmp/cel-runs/bridges-swiftbar-scaling-20261101/architecture/adr/ADR-001-swiftbar-bridge-cleanup-and-hub-scaling.md`
(архитектурный пакет sha256 `9fe8f042c8c41f63cb57fe73d2c6828d453eb2e019ecb36de6f3c01b5fe7135a`,
Архитектурная панель PASS 3/3, `arch-panel-proof.json`).

## Context

Единый шлюз `cli-agent-bridge` на `:9882` (`com.user.dsh-hub`) обслуживает всех
локальных клиентов. Отдельные мосты `:9881`, `:9883`, `:9886`, `:9887` выгружены,
но SwiftBar продолжал их мониторить и показывал `DOWN`. Пул сессий хаба был
ограничен 4 (`MAX_CONCURRENT=4`, семафор 4, admission 32 соединения / 64 MB),
а эксплуатационные таймауты читались разрозненными именами окружения.

## Decision

- `server.py`: все эксплуатационные параметры читаются каскадом
  `_bridge_env` (`BRIDGE_*` -> `DROID_DSH_BRIDGE_*` -> дефолт):
  `MAX_CONCURRENT` 128, `QUEUE_TIMEOUT_S` 900.0, `TIMEOUT_S` 1800.0,
  `KEEPALIVE_S` 10.0, `IDLE_TIMEOUT_S` 120.0. Семафор `_slots` равен
  `MAX_CONCURRENT`; `TurnSessionManager.max_concurrent = max(MAX_CONCURRENT * 8, 256)`.
  Порождение процессов адаптеров остаётся ленивым (on-demand).
- `start.sh`: экспортирует `BRIDGE_MAX_CONCURRENT` и
  `BRIDGE_MAX_HTTP_CONNECTIONS` с дефолтом 128 (с сохранением
  `DROID_DSH_BRIDGE_MAX_CONCURRENT` как источника).
- `fleet.json`: `admission.max_http_connections` 128,
  `admission.max_inflight_body_bytes` 268435456 (256 MB);
  `max_concurrent` passthrough-адаптеров (`codex`, `agy`, `opencode-zen`,
  `claude-p`) поднят до 128.
- SwiftBar `bridges-monitor.sh`: словарь `BRIDGES` содержит только
  `9882: ('dsh-hub', 'com.user.dsh-hub')`, `10830: ('model-georouter', ...)`,
  `2455: ('codex-lb', ...)`; словарь и таймауты переопределяются через
  `SWIFTBAR_BRIDGES_JSON` / `~/.config/swiftbar/bridges.json` /
  `SWIFTBAR_*_TIMEOUT_S`. `restart-all`/`clean-zombies`/`restart-one`
  управляют `com.user.dsh-hub` через launchctl.
- `amsterdam-helper.sh` (`proxyrestart`, вызываемый из `restart-all`):
  kickstart `com.user.dsh-hub` наряду с прочими локальными прокси.

## Отклонение: muse `max_concurrent`

Задание требовало поднять `max_concurrent` до 128 и для `muse`, но адаптер
Muse сериализует ходы инвариантом `max_concurrent == 1`
(`adapters/muse_adapter.py`, `core/backend_adapter.py`:
`backend_muse_max_concurrent_invalid`). Эти файлы вне разрешённого скоупа
правок, а значение 128 в `fleet.json` делает каталог невалидным и ломает
старт сервера. Поэтому `muse` сохранён равным 1; масштабирование до 128
применено к хабу и passthrough-адаптерам. Снятие инварианта Muse — отдельная
задача с изменением адаптера.

## Consequences

Хаб принимает до 128 одновременных сессий без очередей и 503 при сохранении
нулевого потребления в простое. Меню SwiftBar не показывает выгруженные
мосты. Все лимиты настраиваются окружением/конфигом без правки кода;
обратная совместимость `DROID_DSH_BRIDGE_*` сохранена каскадом `_bridge_env`.
