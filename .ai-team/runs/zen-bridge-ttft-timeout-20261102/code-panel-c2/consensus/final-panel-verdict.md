# final-panel-verdict.md (производный от consensus-ledger.json)

## Раздел А. Вердикт

Вердикт: ESCALATED

## Раздел Б. Находки

- F-001: BLOCKER-OPINION — RESOLVED
- F-002: BLOCKER-OPINION — RESOLVED
- F-003: NON_BLOCKING — RESOLVED
- F-004: NON_BLOCKING — RESOLVED
- F-005: NON_BLOCKING — RESOLVED
- F-006: NON_BLOCKING — RESOLVED
- F-007: BLOCKER-OPINION — RESOLVED
- F-008: BLOCKER-OPINION — RESOLVED
- F-009: NON_BLOCKING — RESOLVED
- F-010: BLOCKER-OPINION — ESCALATED
- F-011: BLOCKER-OPINION — ESCALATED
- F-012: BLOCKER-OPINION — ESCALATED
- F-013: BLOCKER-OPINION — RESOLVED
- F-014: BLOCKER-OPINION — RESOLVED
- F-015: NON_BLOCKING — RESOLVED

## Раздел В. Исключённые и эскалированные

- F-010: ESCALATED
- F-011: ESCALATED
- F-012: ESCALATED

## Раздел Г. Неблокирующие рекомендации

- F-003: ### F-003 NON_BLOCKING — в serve-пути TTFT не освобождается для активного tool
- F-004: ### F-004 NON_BLOCKING — нет тестов самого отказа: срабатывание TTFT и Idle, 504 и terminal SSE error
- F-005: ### F-005 NON_BLOCKING — защита от Idle для tool в `opencode run` опирается на события `running`/`pending`, подтверждённые только фейками
- F-006: ### F-006 NON_BLOCKING — устаревшие сообщения лога и нет GigaRC-флага для изменения поведения
- F-009: ### F-009 NON_BLOCKING — Idle-тест не проверяет обязательную ошибку SSE
- F-015: ### F-015 NON_BLOCKING — В zen-дифф включён несвязанный сдвиг ожидания passthrough-таймаута
