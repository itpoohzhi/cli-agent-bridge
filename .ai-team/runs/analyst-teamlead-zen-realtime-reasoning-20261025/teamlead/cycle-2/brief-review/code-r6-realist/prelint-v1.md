# Пре-линт brief-review [L] + Python-first: code R6, cycle 2, место realist (v1)

- `brief_path`: `brief-v1.md`
- `brief_sha256`: `34fc1d7eebf7cd6cfe6840372485401efb38e21321e65feb992a12565fbcc8c9`
- `python_first_elapsed_s`: `0.009637` (целевой бюджет < 0.1 с)
- `python_first_covered_count`: `86` (остаток LLM: `8` ID)

| ID | Метод | Результат |
|---|---|---|
| SK-C-01 | D9 выдержка council.md#L65-L117 после промпта роли и до факт-карты | pass |
| SK-C-10 | D9 обёртки целых файлов task envelope (goal.md, task.json, handoff-architect.md) | pass |
| SK-C-11 | D9 обёртки candidate-manifest.json, candidate.diff, candidate-cycle1-to-cycle2.diff, panel-rework-brief.json и нового тестового файла с SHA256 | pass |
| SK-C-15 | D9 обёртки verification-surface.json, environment-manifest.json, verification-traceability.md, evidence-manifest.sha256 | pass |
| SK-C-19 | отсутствие PR_DESCRIPTION.md вне ARTIFACT и на диске | pass |
| JD-01 | prompt-realist.txt + пустая строка, ФОРМАТ ОТВЕТА (строго) == 1 | pass |
| HY-01 | слот (claude-sonnet-5-5-high, claude-p) | N/A |
| HY-03 | закрытый список плейсхолдеров вне ARTIFACT | pass |

## Python-first покрытые цитаты (covered)

| ID | Источник | Диапазон в brief-v1.md | Цитата (префикс) |
|---|---|---|---|
| BR-01 | L133-L133 | `При запуске DeepSeek (`deepseek-` |
| BR-02 | L134-L134 | `Полный цикл `analyst-teamlead` п` |
| BR-03 | L135-L135 | `Проведена живая проверка тяжёлым` |
| BR-04 | L143-L143 | `"criticality": "S2"` |
| BR-05 | L164-L164 | `Подтверждены три независимые при` |
| BR-06 | L14674-L14674 | `Вне периметра: правка кода, депл` |
| BR-07 | L117-L117 | `Модификатор режима `code`: Переч` |
| BR-08 | L199-L199 | `AC-002: накладные расходы моста ` |
| BR-09 | L200-L200 | `| REQ-002 | MUST | Публичный кон` |
| BR-10 | L201-L201 | `| REQ-003 | MUST | Прежний путь ` |
| BR-11 | L202-L202 | `| REQ-004 | MUST | Первая видима` |
| BR-12 | L203-L203 | `| REQ-005 | MUST | Статусные стр` |
| BR-13 | L203-L203 | `AC-007: `_messages_to_prompt` не` |
| BR-14 | L204-L204 | `| REQ-006 | MUST | Watchdog перв` |
| BR-15 | L205-L205 | `| REQ-007 | MUST | Watchdog перв` |
| BR-16 | L205-L205 | `AC-010: порог первого токена даё` |
| BR-17 | L206-L206 | `| REQ-008 | MUST | Отсутствие ос` |
| BR-18 | L206-L206 | `AC-012: ход 1 образца (24.4 с на` |
| BR-19 | L207-L207 | `| REQ-009 | MUST | Потолок `MAX_` |
| BR-20 | L207-L207 | `AC-014: размышление не дедуплици` |
| BR-21 | L208-L208 | `| REQ-010 | MUST | `ToolCallPars` |
| BR-22 | L209-L209 | `| REQ-011 | MUST | Завершение ша` |
| BR-23 | L210-L210 | `| REQ-012 | MUST | Встроенные ин` |
| BR-24 | L211-L211 | `| REQ-013 | MUST | Ротация чисты` |
| BR-25 | L212-L212 | `| REQ-014 | SHOULD | `usage` соб` |
| BR-26 | L213-L213 | `| REQ-015 | MUST | Секреты не пи` |
| BR-27 | L214-L214 | `| REQ-016 | MUST | Наблюдаемость` |
| BR-28 | L215-L215 | `| REQ-017 | SHOULD | Базовая лин` |
| BR-29 | L215-L215 | `AC-023: результат не зависит от ` |
| BR-30 | L216-L216 | `| REQ-018 | MUST | Прямой Google` |
| BR-31 | L217-L217 | `| REQ-019 | SHOULD | Развёрнутая` |
| BR-32 | L117-L117 | `Модификатор режима `code`: Переч` |
| BR-33 | L310-L310 | `operational_profile` |
| BR-34 | L375-L375 | `Не менять публичный HTTP-контрак` |
| BR-35 | L376-L376 | `Не менять DSH (бандл `app.asar`)` |
| BR-36 | L377-L377 | `Не модифицировать текст размышле` |
| BR-37 | L378-L378 | `Не менять модель, список моделей` |
| BR-38 | L379-L379 | `Не трогать `muse-bridge`, другие` |
| BR-39 | L380-L380 | `Не вводить новые внешние зависим` |
| BR-40 | L384-L384 | `Изменение чужих файлов репозитор` |
| BR-41 | L385-L385 | `Запись секретов (ключи, пароль s` |
| BR-42 | L386-L386 | `Мутирующие действия на боевом ко` |
| BR-43 | L387-L387 | `Использование `security find-gen` |
| BR-44 | L388-L388 | `Правка `opencode.db` и общего ка` |
| BR-45 | L389-L389 | `Коммит в `main`, `master`, `dev`` |
| BR-46 | L156-L156 | `evidence-ledger.md` |
| BR-47 | L255-L255 | `Цели отзывчивости владельцем не ` |
| BR-48 | L156-L156 | `research-plan.md` |
| BR-49 | L14553-L14553 | `aisdlc-gcge/AGENTS.md` |
| BR-50 | L14553-L14553 | `aisdlc-gcge/AGENTS.md` |
| BR-51 | L14553-L14553 | `aisdlc-gcge/AGENTS.md` |
| BR-52 | L238-L238 | `## 5. Инвентарь контрактов (as-i` |
| BR-53 | L106-L106 | `Локальный `model_georouter` (`12` |
| BR-54 | L190-L190 | `всё ниже `parse_opencode_event` ` |
| BR-55 | L222-L222 | `выполнимо с условиями` |
| BR-56 | L388-L388 | `и общего каталога состояния` |
| BR-57 | L204-L204 | `| REQ-006 | MUST | Watchdog перв` |
| SK-C-02 | L37-L37 | `FAIL без привязки к файлу/строке` |
| SK-C-03 | L42-L42 | `- diff меняет согласованный внеш` |
| SK-C-04 | L44-L44 | `- работа, diff или отчёт выходит` |
| SK-C-05 | L61-L61 | `Нет содержательного наблюдения п` |
| SK-C-06 | L117-L117 | `Модификатор режима `code`: Переч` |
| SK-C-07 | L114-L114 | `Анти-галлюцинация: перед тем как` |
| SK-C-08 | L117-L117 | `Результаты тестов и статических ` |
| SK-C-09 | L117-L117 | `регрессий и соответствие каждому` |
| SK-C-12 | L9224-L9224 | `<<<ARTIFACT .ai-team/runs/analys` |
| SK-C-13 | L11553-L11553 | `<<<ARTIFACT .ai-team/runs/analys` |
| SK-C-14 | L14164-L14164 | `<<<ARTIFACT .ai-team/runs/analys` |
| SK-C-16 | L14954-L14954 | `<<<ARTIFACT ~/Мой диск/skils/ai-` |
| SK-C-17 | L102-L102 | `📋 ФАКТ-КАРТА (проверено оркестра` |
| SK-C-18 | L15191-L15191 | `<<<ARTIFACT ~/Мой диск/skils/ai-` |
| SK-C-20 | L14857-L14857 | `Обязательное указание судье пере` |
| SK-T-01 | L14859-L14859 | `<<<ARTIFACT ~/Мой диск/skils/ai-` |
| SK-T-02 | L14554-L14554 | `aisdlc-gcge/skills/feature.md` |
| SK-T-03 | L14554-L14554 | `aisdlc-gcge/skills/feature.md` |
| SK-P-01 | L14553-L14553 | `aisdlc-gcge/AGENTS.md` |
| SK-P-02 | L14561-L14561 | `aisdlc-gcge/agents/scope-and-con` |
| SK-P-03 | L14555-L14555 | `aisdlc-gcge/agents/code.md` |
| SK-P-04 | L14556-L14556 | `aisdlc-gcge/agents/python-standa` |
| SK-P-05 | L14902-L14902 | `Зелёный прогон ≠ корректно` |
| SK-P-06 | L14558-L14558 | `aisdlc-gcge/agents/security.md` |
| SK-P-07 | L14559-L14559 | `aisdlc-gcge/agents/error-handlin` |
| SK-P-08 | L14560-L14560 | `aisdlc-gcge/agents/logging.md` |
| JD-03 | L117-L117 | `суди ЗАНОВО, не подтверждай прош` |
| JD-04 | L7-L7 | `ФОРМАТ ОТВЕТА (строго):` |
| JD-07 | L119-L119 | `РЕШЕНИЕ ДЛЯ ОЦЕНКИ:` |

ИТОГ ПРЕ-ЛИНТА: PASS
