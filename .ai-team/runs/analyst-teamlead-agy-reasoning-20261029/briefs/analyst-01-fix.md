# Доводка `handoff-architect.md` под строгий парсер `SA-DOD-004`

В файле `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-architect.md` на строке 48 заголовок:
`## 3. Требования \`REQ-001..REQ-012\``
содержит токены `REQ-001` и `REQ-012` **до** таблицы требований (строки 55–66).
Из-за того, что скрипт `SA-DOD-004` ищет **первое** вхождение каждого `REQ-NNN` в файле (`re.search(rf"{req}\b[^\n]*", arch)`), первое вхождение `REQ-001` и `REQ-012` попадает на заголовок строки 48, где нет `MUST/SHOULD`, `F-NN` и `AC-NNN`, и выдаёт:
`SA-DOD-004 FAIL: REQ-001 line lacks MUST/SHOULD, F-NN, or AC-NNN: REQ-001..REQ-012`

Что нужно сделать:
1. В `/Users/aazhiry1/tmp/cli-agent-bridge/agy-realtime-reasoning/analysis/agy-realtime-reasoning/handoff-architect.md` замени заголовок `## 3. Требования \`REQ-001..REQ-012\`` на `## 3. Верифицируемые требования` (и убедись, что до таблицы строк 55–66 ни один идентификатор `REQ-NNN` не встречается).
2. Никакие другие файлы в репозитории не меняй.
3. Ответь одной строкой: `SA-DOD-004 FIXED`.
