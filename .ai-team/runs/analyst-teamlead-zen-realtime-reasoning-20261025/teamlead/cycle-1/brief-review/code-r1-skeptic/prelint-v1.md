# Пре-линт brief-review [L] + Python-first: code R1, cycle 1, место skeptic (v1)

- `brief_path`: `brief-v1.md`
- `brief_sha256`: `f3419caf2aee804bfb04f6e6988dee834ec018e5f5da369ddd60ec979bab088f`
- `python_first_elapsed_s`: `0.007473` (целевой бюджет < 0.1 с)
- `python_first_covered_count`: `87` (остаток LLM: `7` ID)

| ID | Метод | Результат |
|---|---|---|
| SK-C-01 | D9 выдержка council.md#L65-L117 после промпта роли и до факт-карты | pass |
| SK-C-10 | D9 обёртки целых файлов task envelope (goal.md, task.json, handoff-architect.md) | pass |
| SK-C-11 | D9 обёртки candidate-manifest.json, candidate.diff и нового тестовый файла с SHA256 | pass |
| SK-C-15 | D9 обёртки verification-surface.json, environment-manifest.json, verification-traceability.md, evidence-manifest.sha256 | pass |
| SK-C-19 | отсутствие PR_DESCRIPTION.md вне ARTIFACT и на диске | pass |
| JD-01 | prompt-skeptic.txt + пустая строка, ФОРМАТ ОТВЕТА (строго) == 1 | pass |
| HY-01 | слот (grok-4.7-high, cursor-agent) | N/A |
| HY-03 | закрытый список плейсхолдеров вне ARTIFACT | pass |

## Python-first покрытые цитаты (covered)

| ID | Источник | Диапазон в brief-v1.md | Цитата (префикс) |
|---|---|---|---|
| BR-01 | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L7 | L133-L133 | `При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridg...` |
| BR-02 | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L8 | L134-L134 | `Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proo...` |
| BR-03 | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L9 | L135-L135 | `Проведена живая проверка тяжёлым путём на реальном мосту и DSH....` |
| BR-04 | источник: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json#L4-L6 | L143-L143 | `"criticality": "S2"...` |
| BR-05 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L12-L19 | L163-L163 | `Подтверждены три независимые причины; устранять надо все три, иначе пользователь...` |
| BR-06 | источник: analysis/zen-realtime-reasoning/research-plan.md#L16 | L9194-L9194 | `Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кр...` |
| BR-07 | MUST | L117-L117 | `Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничны...` |
| BR-08 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L47 | L198-L198 | `AC-002: накладные расходы моста между приходом дельты и записью в сокет не больш...` |
| BR-09 | MUST | L199-L199 | `| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1...` |
| BR-10 | MUST | L200-L200 | `| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим ка...` |
| BR-11 | MUST | L201-L201 | `| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия S...` |
| BR-12 | MUST | L202-L202 | `| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префи...` |
| BR-13 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L51 | L202-L202 | `AC-007: `_messages_to_prompt` не содержит статусных строк при реплее...` |
| BR-14 | MUST | L203-L203 | `| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в ...` |
| BR-15 | MUST | L204-L204 | `| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) ...` |
| BR-16 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L53 | L204-L204 | `AC-010: порог первого токена даёт `first_token_timeout`...` |
| BR-17 | MUST | L205-L205 | `| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, тай...` |
| BR-18 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L54 | L205-L205 | `AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится...` |
| BR-19 | MUST | L206-L206 | `| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudg...` |
| BR-20 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L55 | L206-L206 | `AC-014: размышление не дедуплицируется, между попытками ровно одна статусная стр...` |
| BR-21 | MUST | L207-L207 | `| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаёт...` |
| BR-22 | MUST | L208-L208 | `| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс и...` |
| BR-23 | MUST | L209-L209 | `| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запреще...` |
| BR-24 | MUST | L210-L210 | `| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SP...` |
| BR-25 | SHOULD | L211-L211 | `| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового трансп...` |
| BR-26 | MUST | L212-L212 | `| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve...` |
| BR-27 | MUST | L213-L213 | `| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`fir...` |
| BR-28 | SHOULD | L214-L214 | `| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4...` |
| BR-29 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L63 | L214-L214 | `AC-023: результат не зависит от порядка тестов...` |
| BR-30 | MUST | L215-L215 | `| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google...` |
| BR-31 | SHOULD | L216-L216 | `| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/serve...` |
| BR-32 | MUST | L117-L117 | `Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничны...` |
| BR-33 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L97-L220 | L309-L309 | `operational_profile...` |
| BR-34 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L223 | L374-L374 | `Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002)....` |
| BR-35 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L224 | L375-L375 | `Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `Reason...` |
| BR-36 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L225 | L376-L376 | `Не модифицировать текст размышления модели ради превью (OPEN-13)....` |
| BR-37 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L226 | L377-L377 | `Не менять модель, список моделей, логику выбора эффорта и каталог Zen....` |
| BR-38 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L227 | L378-L378 | `Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json...` |
| BR-39 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L228 | L379-L379 | `Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Arc...` |
| BR-40 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L232 | L383-L383 | `Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов э...` |
| BR-41 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L233 | L384-L384 | `Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, а...` |
| BR-42 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L234 | L385-L385 | `Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск L...` |
| BR-43 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L235 | L386-L386 | `Использование `security find-generic-password`....` |
| BR-44 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L236 | L387-L387 | `Правка `opencode.db` и общего каталога состояния `opencode` напрямую....` |
| BR-45 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L237 | L388-L388 | `Коммит в `main`, `master`, `dev`; merge выполняет человек....` |
| BR-46 | источник: analysis/zen-realtime-reasoning/evidence-ledger.md#L11-L91 | L155-L155 | `evidence-ledger.md...` |
| BR-47 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L103 | L254-L254 | `Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: перв...` |
| BR-48 | источник: analysis/zen-realtime-reasoning/research-plan.md#Scope | L155-L155 | `research-plan.md...` |
| BR-49 | источник: aisdlc-gcge/AGENTS.md#Главные-правила | L9073-L9073 | `aisdlc-gcge/AGENTS.md...` |
| BR-50 | источник: aisdlc-gcge/AGENTS.md#Правила-коммитов-и-измерение-вклада-агента | L9073-L9073 | `aisdlc-gcge/AGENTS.md...` |
| BR-51 | источник: aisdlc-gcge/AGENTS.md#Что-запрещено-делать | L9073-L9073 | `aisdlc-gcge/AGENTS.md...` |
| BR-52 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#5 | L237-L237 | `## 5. Инвентарь контрактов (as-is)...` |
| BR-53 | источник: analysis/zen-realtime-reasoning/research-plan.md#Scope | L106-L106 | `Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRac...` |
| BR-54 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#2 | L189-L189 | `всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)`...` |
| BR-55 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#4 | L221-L221 | `выполнимо с условиями...` |
| BR-56 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L236 | L387-L387 | `и общего каталога состояния...` |
| BR-57 | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L259 | L203-L203 | `| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в ...` |
| SK-C-02 | источник: brief-review/references/checklist-sources.md#SK-C | L37-L37 | `FAIL без привязки к файлу/строке/правилу не засчитывается....` |
| SK-C-03 | источник: brief-review/references/checklist-sources.md#SK-C | L42-L42 | `- diff меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK), а в...` |
| SK-C-04 | источник: brief-review/references/checklist-sources.md#SK-C | L44-L44 | `- работа, diff или отчёт выходит за текущую задачу (чужие Jira-KEY, чужой...` |
| SK-C-05 | источник: brief-review/references/checklist-sources.md#SK-C | L61-L61 | `Нет содержательного наблюдения по критерию — ставь PASS/INCONCLUSIVE, не выдумыв...` |
| SK-C-06 | источник: brief-review/references/checklist-sources.md#SK-C | L117-L117 | `Модификатор режима `code`: Перечисли конкретные проверки: типы, ошибки, граничны...` |
| SK-C-07 | источник: brief-review/references/checklist-sources.md#SK-C | L114-L114 | `Анти-галлюцинация: перед тем как выставить FAIL «нет X», перечитай приложенный п...` |
| SK-C-08 | источник: brief-review/references/checklist-sources.md#SK-C | L117-L117 | `Результаты тестов и статических проверок бери только как факт из валидных строк ...` |
| SK-C-09 | источник: brief-review/references/checklist-sources.md#SK-C | L117-L117 | `Проверь соответствие кандидата каждому требованию `REQ-001..REQ-020`, каждому пр...` |
| SK-C-12 | источник: brief-review/references/checklist-sources.md#SK-C, acceptance-package.md#§3 | L4818-L4818 | `<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/recei...` |
| SK-C-13 | источник: brief-review/references/checklist-sources.md#SK-C | L6373-L6373 | `<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teaml...` |
| SK-C-14 | источник: brief-review/references/checklist-sources.md#SK-C | L8372-L8372 | `<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teaml...` |
| SK-C-16 | источник: brief-review/references/checklist-sources.md#SK-C | L9459-L9459 | `<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md...` |
| SK-C-17 | источник: brief-review/references/checklist-sources.md#SK-C | L102-L102 | `📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и дополнено логами гейто...` |
| SK-C-18 | источник: brief-review/references/checklist-sources.md#SK-C | L9696-L9696 | `<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contrac...` |
| SK-C-20 | источник: brief-review/references/checklist-sources.md#SK-C | L9362-L9362 | `Обязательное указание судье перед обёртками стандартов (вне тела обёрток `ARTIFA...` |
| SK-T-01 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md#Алгоритм-выполнения-задачи-на-новую-фичу | L9364-L9364 | `<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md...` |
| SK-T-02 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md#Критерии-приёмки | L9074-L9074 | `aisdlc-gcge/skills/feature.md...` |
| SK-T-03 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/feature.md#HL-RESILIENCE-GATES-V5 | L9074-L9074 | `aisdlc-gcge/skills/feature.md...` |
| SK-P-01 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md#Главные-правила | L9073-L9073 | `aisdlc-gcge/AGENTS.md...` |
| SK-P-02 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md | L9081-L9081 | `aisdlc-gcge/agents/scope-and-contracts.md...` |
| SK-P-03 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/code.md | L9075-L9075 | `aisdlc-gcge/agents/code.md...` |
| SK-P-04 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/python-standards.md | L9076-L9076 | `aisdlc-gcge/agents/python-standards.md...` |
| SK-P-05 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/testing.md | L9407-L9407 | `Зелёный прогон ≠ корректно...` |
| SK-P-06 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/security.md | L9078-L9078 | `aisdlc-gcge/agents/security.md...` |
| SK-P-07 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/error-handling.md | L9079-L9079 | `aisdlc-gcge/agents/error-handling.md...` |
| SK-P-08 | источник: ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/logging.md | L9080-L9080 | `aisdlc-gcge/agents/logging.md...` |
| JD-03 | источник: brief-review/references/checklist-sources.md#JD | L117-L117 | `суди ЗАНОВО, не подтверждай прошлый вердикт автоматически...` |
| JD-04 | источник: brief-review/references/checklist-sources.md#JD | L7-L7 | `ФОРМАТ ОТВЕТА (строго):...` |
| JD-05 | источник: brief-review/references/checklist-sources.md#JD | L11333-L11333 | `независимо пересчитай `seed_hex = SHA-256(seed_input)` (и первые 8 hex `SEED`) и...` |
| JD-07 | источник: brief-review/references/checklist-sources.md#JD | L119-L119 | `РЕШЕНИЕ ДЛЯ ОЦЕНКИ:...` |

ИТОГ ПРЕ-ЛИНТА: PASS
