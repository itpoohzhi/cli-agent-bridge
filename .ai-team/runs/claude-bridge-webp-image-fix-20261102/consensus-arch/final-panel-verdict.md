# final-panel-verdict.md (производный от consensus-ledger.json)

## Раздел А. Вердикт

Вердикт: ESCALATED

## Раздел Б. Находки

- F-001: BLOCKER-OPINION — RESOLVED
- F-002: NON_BLOCKING — RESOLVED
- F-003: NON_BLOCKING — RESOLVED
- F-004: NON_BLOCKING — RESOLVED
- F-005: NON_BLOCKING — RESOLVED
- F-007: BLOCKER-OPINION — RESOLVED
- F-008: BLOCKER-OPINION — ESCALATED
- F-009: BLOCKER-OPINION — RESOLVED
- F-010: BLOCKER-OPINION — ESCALATED
- F-011: NON_BLOCKING — RESOLVED
- F-006: NON_BLOCKING — RESOLVED
- F-012: NON_BLOCKING — RESOLVED
- F-013: NON_BLOCKING — RESOLVED
- F-014: NON_BLOCKING — RESOLVED

## Раздел В. Исключённые и эскалированные

- F-008: ESCALATED
- F-010: ESCALATED

## Раздел Г. Неблокирующие рекомендации

- F-002: ### F-002 NON_BLOCKING — таблица `_IMAGE_FORMATS` с `b"RIFF"` и `b"GIF8"` расходится со «строгим» сниффом
- F-003: ### F-003 NON_BLOCKING — подстрока `quota exhausted` слишком широкая, а два других маркера избыточны
- F-004: ### F-004 NON_BLOCKING — новые форматы расширяют поверхность атаки на декодеры нижестоящего CLI
- F-005: ### F-005 NON_BLOCKING — нет подтверждения прогона и несоответствие по файлам тестов
- F-011: ### F-011 NON_BLOCKING — подписочная квота приравнена к per-IP, маркеры избыточны
- F-006: ### F-006 NON_BLOCKING — читаемость WebP/GIF downstream и документация не закрыты
- F-012: ### F-012 NON_BLOCKING — Дублирование таблиц сигнатур и логики MIME-сниффинга между `server.py` и `core/tool_emulation.py`
- F-013: ### F-013 NON_BLOCKING — Неиспользуемое поле сигнатуры `magic` в кортеже `_IMAGE_FORMATS` после перехода на составные сигнатуры
- F-014: ### F-014 NON_BLOCKING — Избыточность частных подстрок квоты при наличии общего маркера `"quota exhausted"` в `_is_free_quota_error`
