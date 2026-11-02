# final-panel-verdict.md (производный от consensus-ledger.json)

## Раздел А. Вердикт

Вердикт: ESCALATED

## Раздел Б. Находки

- F-001: BLOCKER-OPINION — RESOLVED
- F-002: BLOCKER-OPINION — RESOLVED
- F-003: BLOCKER-OPINION — ESCALATED
- F-004: NON_BLOCKING — RESOLVED
- F-005: NON_BLOCKING — RESOLVED
- F-006: NON_BLOCKING — RESOLVED
- F-007: NON_BLOCKING — RESOLVED

## Раздел В. Исключённые и эскалированные

- F-003: ESCALATED

## Раздел Г. Неблокирующие рекомендации

- F-004: ### F-004 NON_BLOCKING — Idle и Total не конфигурируются независимо: оба гейтятся значением TTFT
- F-005: ### F-005 NON_BLOCKING — `_attempts_t0`: eager-вычисление default в `getattr` ломает заявленную совместимость с заглушками
- F-006: ### F-006 NON_BLOCKING — Удержание admission-слота вырослo в 7,2 раза; trickle-стрим держит слот и процесс 180с
- F-007: ### F-007 NON_BLOCKING — Новая проверка затеняет существующие `first_token_timeout`/`stall_timeout`, размывая телеметрию причин
