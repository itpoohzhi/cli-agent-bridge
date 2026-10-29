# Stage 1: протокол проверок

Дата: 2026-10-29. Это протокол аналитических артефактов, не приёмка продукта или полного analyst-teamlead.

## Источник и несовместимость форматов

В analyst-teamlead/SKILL.md нет исполнимого композита SA-DOD: он делегирован system-analyst и его references/artifacts-and-handoff.md.
Дословный композит из references запущен в каталоге анализа, вывод сохранён в sa-dod-reference.log. Он печатает 6 проверок, не все 8; даты и REQ отдельно перечислены текстом скилла. Его SA-DOD-004 требует raw 7-column open-question строки. Прямой бриф требует markdown-таблицу из 5 колонок; приоритет отдан брифу, поэтому штатный SA-DOD-004 остаётся FORMAT FAIL. Встреча OPEN-05 в пояснении также входит в его счётчик строк. Никакого скрытого редактирования исходного композита нет.

Фактический stdout штатной команды:

```text
SA-DOD-001 PASS (34 facts)
SA-DOD-002 PASS (no guesses)
SA-DOD-003 PASS (5 spikes)
SA-DOD-004 FAIL: 12 vs 0
SA-DOD-006 PASS (no AC in handoff)
SA-DOD-008 PASS (timeboxes clean)
```

Команда штатного композита возвращает exit=0 даже при напечатанном FAIL: его echo не является корректным exit-code gate. Результат определялся по строкам вывода, не только по коду возврата.

## Проверка требований брифа

sa-dod-stage1.py — явно адаптированный проверяющий инструмент для формата этого брифа, не переиздание штатного композита. Выдаёт восемь строк и SA-DOD-001..008 PASS только при выполнении всех восьми условий, иначе exit=1. Машинный receipt: sa-dod-stage1.json.

Проверены: 34 уникальных ISO-dated факта, 11 закрытых вопросов с явными допущениями, пять 12-колоночных закрытых спайков, REQ-001..010 с MUST/SHOULD+F+AC, отсутствие необъявленных F и пропусков в диапазонах, ровно 46 строк текущей SSoT и ровно 46 идентификаторов брифа, QA на все AC и девять кодов, пять файлов и git scope. Структурная полнота HL не означает замыкания UNKNOWN численных бюджетов.

Адресная ручная сверка трёх фактов: F-02 — scan и handler до launcher; F-16 — max_types в эталоне против types в fleet; F-22 — порог 24 и allowlist из двух SQLite имён. Эти факты воспроизведены чтением текущих строк, не пересказом предыдущих агентов.

## Ограничения результата

Код продукта, профиль DSH и runtime-файлы не менялись. git diff --check не нашёл tracked whitespace ошибок; untracked markdown проверен структурным инструментом. Живые model calls, тесты продукта, деплой и L3 в Stage 1 не выполнялись. Предоставленный operator PNG probe сохранён с ограничением области доказательства. Нет архитектурного решения/панели, ACCEPT/MR или close.md.
Команд дольше 4 минут не было; фоновые внешние/модельные вызовы не запускались. Начальный вызов штатного скрипта с ошибочным относительным путём вернул ENOENT, затем исправленный абсолютный вызов выполнен и его вывод сохранён выше.

## Файлы результата и SHA256

- `~/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/evidence-ledger.md`: sha256=aba34816b5cf6425d4fbf19187a09edd5f7158797e442d488d68626576f887a9
- `~/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/handoff-architect.md`: sha256=35833dbdb32e6a00072c589ac1dc4a2dd133dbca83c2b497d6367be0b321e887
- `~/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/handoff-qa.md`: sha256=007cdac728cdd6754c6617cd749ed3361f0d19c9e1adae16a3c31a90ee352cee
- `~/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/open-questions.md`: sha256=63fe13ce25d80cb7bad68d25a57c8d1d6e58847b5b8be79dc395b555c55e5b76
- `~/tmp/cli-agent-bridge/agy-image-input-fix/analysis/agy-image-input-fix/research-plan.md`: sha256=67f3bfffc4e9df6b95ee8571c34ded4a397ad164f86787b3b935fe51dcf1243a
