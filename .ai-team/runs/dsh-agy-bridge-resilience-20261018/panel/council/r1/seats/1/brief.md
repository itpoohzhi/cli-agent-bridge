# Бриф судьи Совета Тимлидов (CODE-REVIEW, раунд R1, место k=1)

ВАЖНО: Ты — листовой судья Совета Тимлидов (НЕ оркестратор). НЕ открывай контур `cel`, НЕ создавай todo/таймеры и НЕ порождай вложенных сабагентов (`Task`, `invoke_subagent`, `muse`, `droid`, `claude`, `codex`) — прочитай артефакты из рабочего каталога и выдай финальный вердикт напрямую в этом ответе!

Ты принимаешь этот код как ТИМЛИД команды. Реши, взял бы ты этот diff в main.
Смотри как тимлид: соответствие task envelope и правилам проекта (AGENTS.md/AI-SDLC), архитектурные границы и слои, поддерживаемость (поймёт ли команда через полгода), достаточность тестов именно для этого изменения, риск регрессий, скрытый долг. Опирайся на пакет приёмки `code-review-package.md`.

## Твоя роль и шляпа
- Место: `k=1`, модель/слот: `claude-sonnet-5-5-high` (`Anthropic`)
- Назначенная шляпа: **Реалист** — проверяй эксплуатационную надёжность кода, корректность реализации `AdaptiveTimeoutController`, отсутствие гонок, корректность работы с процессами и группами на Darwin (macOS), обработку ошибок и качество тестов.
- Оценивай решение по всем 6 критериям рубрики.

## Цель задачи, Task Envelope
Задача `dsh-agy-bridge-resilience-20261018` (`S2`, тикет `EYE-33873`, пресет `analyst-teamlead`): устранить зависания DSH при работе с `agy-bridge`, перенести мост в состав монорепозитория `cli-agent-bridge`, внедрить двухконтурный watchdog (`IDLE_TIMEOUT_S = 300s`, `SAFETY_CAP_S = 1800s`), обеспечить уничтожение групп процессов и reaping зомби, пропатчить клиентский `fetch_via_playwright.py` таймаутом 60с на источники и 5с на закрытие страниц.

## Входные артефакты на диске (в рабочем каталоге)
1. Главный оцениваемый артефакт: `/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/dsh-agy-bridge-resilience-20261018/code-review-package.md` (sha256: `4d1e757f6e26f5be128ee56955265b37b8cb65ed126330db3c59de67da19fb23`)
2. Ветка: `feature/EYE-33873-agy-bridge-resilience` (коммит `b9a9648`)
3. Тесты: `tests/test_agy_bridge_resilience.py` (22 passed in 2.13s)
4. ADR: `docs/adr/0007-agy-bridge-resilience-watchdog.md`
5. Спецификация: `.ai-team/runs/dsh-agy-bridge-resilience-20261018/architecture/arch-spec.md`

## Рубрика оценки (6 обязательных критериев)
Оцени каждый из 6 критериев (`PASS` / `NEEDS_WORK` / `RED_FLAG`):
1. **Корректность (`correctness`)**
2. **Полнота (`completeness`)**
3. **Реализуемость (`feasibility`)**
4. **Риски (`risks`)**
5. **Альтернативы (`alternatives`)**
6. **Соответствие контексту (`context_conformance`)**

Выведи сводку субрибрик:
- `SUB architecture: PASS|CONCERN|FAIL — <1 строка>`
- `SUB security: PASS|CONCERN|FAIL — <1 строка>`
- `SUB performance: PASS|CONCERN|FAIL — <1 строка>`
- `SUB tests: PASS|CONCERN|FAIL — <1 строка>`

## ЖЁСТКИЙ ФОРМАТ ОТВЕТА (проверяется автоматом `verify_panel_proof.py`)
1. **Первые две непустые строки твоего ответа ОБЯЗАНЫ быть дословно:**
```
PANEL-NONCE: be0c9afb65428add
ARTIFACT-SHA256: 4d1e757f6e26f5be128ee56955265b37b8cb65ed126330db3c59de67da19fb23
```
Никакого текста ДО этих двух строк!
2. В теле ответа дай содержательный разбор кода со шляпой `Реалист`, оцени все 6 пунктов рубрики и выведи строки `SUB ...`. Для оценок критериев пиши `Критерий N — PASS`.
3. **Самая последняя непустая строка твоего ответа ОБЯЗАНА быть строго одной из трёх строк:**
`ОБЩИЙ ВЕРДИКТ: ACCEPT`
или
`ОБЩИЙ ВЕРДИКТ: NEEDS_WORK`
или
`ОБЩИЙ ВЕРДИКТ: RED_FLAG`

---
PANEL-NONCE: be0c9afb65428add
ARTIFACT-SHA256: 4d1e757f6e26f5be128ee56955265b37b8cb65ed126330db3c59de67da19fb23
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: be0c9afb65428add» и «ARTIFACT-SHA256: 4d1e757f6e26f5be128ee56955265b37b8cb65ed126330db3c59de67da19fb23».
