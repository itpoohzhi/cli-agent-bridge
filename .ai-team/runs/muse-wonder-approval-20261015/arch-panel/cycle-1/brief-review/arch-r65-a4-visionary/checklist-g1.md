# Чек-лист brief-review: arch C1, cycle 1, a4, run muse-wonder-approval-20261015, поколение g1
## Пре-линт [L]
SK-A-02 [L] | см. checklist-sources.md «Пре-линт [L]: методы» | источник: brief-review/references/checklist-sources.md
SK-A-12 [L] | см. checklist-sources.md «Пре-линт [L]: методы» | источник: brief-review/references/checklist-sources.md
JD-01 [L] | см. checklist-sources.md «Пре-линт [L]: методы» | источник: brief-review/references/checklist-sources.md
HY-01 [L] | см. checklist-sources.md «Пре-линт [L]: методы» | источник: brief-review/references/checklist-sources.md
HY-03 [L] | см. checklist-sources.md «Пре-линт [L]: методы» | источник: brief-review/references/checklist-sources.md
## BR — бизнес-требования
BR-01 | «Результат: muse-bridge (:9886, ~/work/src/cli-agent-bridge/bridges/muse-bridge/server.py) на моделях Wonder не теряет ход при `serve needs interaction (approval/request)` — не перезапускает его с нуля (exec-fallback = x2 времени + выброс 7 мин мышления) и не выглядит зависшим в DSH ("Deep diving 8m48s"), на длинной (>400k) сессии.» | источник: goal.md#Результат
BR-02 | «Критерий (тяжёлый путь): ПАНЕЛЬ ACCEPT (panel-proof.json PASS, pol-receipt/1) по коду + clean-room + ЖИВОЙ ход в DSH-слоте владельца (muse-wonder-full-1.0 Max, сессия «ai dizrapt»/длинная): ход завершается без fallback-рестарта с нуля, тайминги записаны; регрессий нет (67+ тестов).» | источник: goal.md#Критерий
BR-03 | «- **REQ-MUSE-002:** При получении `approval/request` или `userInput/request` от `muse serve` ход не должен перезапускаться с нуля через `muse exec` с потерей накопленного времени мышления [F-01], [F-02], [F-03], [F-06], [F-07].» | источник: handoff-architect.md#REQ-MUSE-002
BR-04 | «- **REQ-MUSE-003:** Транзиентная ошибка транспорта `transport error [net-timeout]: timed out waiting for response data (meta stream)` не должна приводить к немедленному отказу хода без контролируемого повтора, когда повтор допустим [F-12], [F-13], [F-14].» | источник: handoff-architect.md#REQ-MUSE-003
BR-05 | «- **REQ-MUSE-004:** Во время длительного мышления модели (`muse-wonder-full-1.0`, `effort=max`) клиент DSH по SSE должен получать признаки жизни и прогресса мышления в реальном времени, а не только буферизованный в конце хода блок `reasoning_content` [F-16], [F-17], [F-18], [F-19].» | источник: handoff-architect.md#REQ-MUSE-004
BR-06 | «Требование **REQ-MUSE-001** (прунинг контекста 400k/320k/200k для чужих/длинных сессий) уже реализовано в рабочем дереве `bridges/muse-bridge/server.py` и подтверждено логами `context_prune` [F-07], в рамках данного пакета выступает как ограничение совместимости [F-49].» | источник: handoff-architect.md#REQ-MUSE-001
BR-07 | «"contract_freeze": "внешний OpenAI-совместимый контракт моста (/v1/chat/completions, /health, /v1/models) не менять без явного пункта; допустимы только аддитивные SSE-кадры внутри существующих полей",» | источник: task.json#contract_freeze
BR-08 | «"branch_policy": "не dev; ветка bugfix/muse-wonder-approval-retry-liveness (создаётся Coder-ом после арх-панели)",» | источник: task.json#branch_policy
BR-09 | «"criticality_reason": "боевой мост DSH->Meta Muse (:9886), поведение ходов и протокол serve/exec, деплой через launchd",» | источник: task.json#criticality_reason
BR-10 | «2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)» | источник: owner-decisions.md#OPEN-07
BR-11 | «2026-10-15 13:39 MSK | находки арх-панели F-002, F-003, F-004, F-006 (OBJECT автора при C1, PAUSED_OWNER) | владелец выбрал в чате по каждой: «blocking (Рекомендуется)» | опции: blocking / non-blocking / excluded | итог: все четыре blocking, входят в instructions для Architect delta» | источник: owner-decisions.md#решение-13:39
## SK — обязательные проверки
SK-A-01 [P] | Architecture Packet приложен целиком (не пересказ), без пометки об обрезке; совпадение SHA256 с receipt `ARCH_GATE` проверяет пре-линт SK-A-02
SK-A-03 [P] | `handoff-architect.md` и `evidence-ledger.md` приложены; указание судье проверить, что решения опираются на факты `[F-NN]` и каждый `[F-NN]` находится в ledger
SK-A-04 [P] | `РЕЖИМ: architecture` + модификатор «Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки»
SK-A-05 [P] | Указание: в пакете ≥2 альтернативы с причиной выбора; нет — FAIL по пункту об альтернативах
SK-A-06 [P] | Указание проверить границы и слои, внешние контракты (HTTP/event/data/CLI/SDK), сценарии качества (NFR), модель угроз
SK-A-07 [P] | FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается
SK-A-08 [P] | FAIL без оговорок: контракт вне envelope; выход за задачу
SK-A-09 [P] | Оценка всех 6 критериев `universal-panel`; анти-галлюцинация и факт-карта (технологии/версии из пакета проверены)
SK-A-10 [P] | Пункты `aisdlc-gcge/skills/architecture.md` (чек-лист/DoD) и правила проекта (`AGENTS.md`) видны судье
SK-A-13 [P] | В брифе судьи есть блок «ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД» (`council.md` §1) со смысловыми указаниями: не обрывать поиск на первой ошибке, все замечания одним списком, один дефект в нескольких местах — один F-блок со всеми местами, self-sweep, последние строки `COVERAGE` / `FINDINGS_COMPLETE`. Проверяется в каждом раунде (R1, forced-dissent, D<k>, C1: пакет судьи собран как в R1, `council-consensus.md` §4 п.1, §6). Блок написан под код: для `arch` «diff» читается как «пакет», вместо `file:line` — якорь пакета (`arch-council.md` §1, §2; блок якорей — SK-A-14). Шапка тимлида (код) для `arch` не требуется — её отсутствие не дефект. `covered` — цитата заголовка блока и п.6; блока нет — `missing`. Побайтную дословность вставок D9 Reviewer не проверяет: её сверяет пре-линт оркестратора (`council-consensus.md` §5 п.2)
SK-A-14 [P] | В брифе судьи есть блок «ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)» с допустимыми якорями (а)–(г) (`arch-council.md` §2) — в каждом раунде (R1, forced-dissent, D<k>, C1); в D<k> он стоит перед `ПРАВИЛАМИ ДЕБАТОВ`, в C1 — перед `ПРАВИЛАМИ СОГЛАСИЯ`. Без него «file:line» из «ПОЛНОТЫ ВЫДАЧИ» и правил дебатов для пакета не определён. `covered` — цитата заголовка блока; блока нет или в нём нет перечня якорей (а)–(г) — `missing`. Дословность, обёртку D9 и sha256 выдержки сверяет пре-линт оркестратора (`council-consensus.md` §5 п.2), не Reviewer
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе
JD-03 [P] | «суди ЗАНОВО, не подтверждай прошлый вердикт автоматически»
JD-04 [P] | Ровно один блок «ФОРМАТ ОТВЕТА (строго)» на весь brief-v<K>.md (в hat-промпте или в judge-prompt); дубль = HY-02/B3. Блок в judge-prompt — дословно по universal-panel: 6 критериев, `VERDICT=PASS\ | FAIL\ | INCONCLUSIVE`, WHY, СОВЕТЫ, ОБЩИЙ ВЕРДИКТ. Блок в hat-промпте — как в `prompt-<hat>.txt` (JD-01, побайтно); отсутствие в нём `INCONCLUSIVE` — не дефект брифа, второй блок ради него запрещён
JD-05 [P/N] | `seed_recheck_duty: да` → в брифе указание независимо пересчитать SEED и ranked_order по models.md п.1.1/1.2 с `seed_input` дословно; `нет` → такого указания нет
JD-06 [P/N] | R1: чужих вердиктов нет (N). R2-дебат: вердикт своей роли R1 и вердикты двух других — дословно, по шаблону `universal-panel` ШАГ 2 (P). Forced dissent — по его шаблону (P)
JD-07 [P] | Факт-карта и строка режима присутствуют; порядок блоков — по шаблону промпта universal-panel ШАГ 1 (arch) / teamlead-gate «Как передавать пакет» (code); секция КОНТЕКСТ присутствует; формат ответа — последний блок judge-prompt, если он в judge-prompt; блок формата в промпте шляпы (JD-01, JD-04) — требование «последний блок» не применяется
JD-08 [N] | Бриф самодостаточен: нет ссылок на «как обсуждали», «см. выше в чате», на файлы, которые судья не получит, как на единственный носитель содержания; в том числе на пути под каталогами с точкой на Google Drive (`.ai-team/…` в `~/Мой диск/…`) — они синхронизируются ненадёжно
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами (режим, формат, правила FAIL, границы). Блок формата в hat-промпте без `INCONCLUSIVE` при шапке тимлида с PASS/INCONCLUSIVE (SK-C-05, SK-C-08) — не противоречие (JD-04: `prompt-<hat>.txt` не меняется)
HY-04 [N] | Нет секретов (токены, ключи, пароли)
HY-05 [N] | Нет следов brief-review: «исправлено по замечанию», ссылок на вердикт ревьювера
HY-06 [N] | Формулировки пунктов чек-листа не вставлены в бриф как самостоятельный текст без соответствующего первичного артефакта/шапки; такой пункт считается отсутствующим
## Исключено
SK-A-11 | основание: раунд C1 внутри прохода a4 — полный актуальный пакет + delta + вывод panel-rework-summarizer поданы в R1 этого прохода (checklist-sources.md: «новый чек-лист R1»); в D/C1 подаются вердикты R1 a2, леджер и протокол | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-15 | основание: раунд C1 — блок ПРАВИЛА СОГЛАСИЯ вместо ПРАВИЛ ДЕБАТОВ (проверяется по тексту брифа) | источник: council-consensus.md#6
## Параметры места
panel: arch | round: C1 | round_type: C1 | hat: visionary
hat_prompt: ~/work/universal-panel/prompt-visionary.txt
seat_slot: claude-sonnet-5-5-high
seat_kind: panel-judge
seed_recheck_duty: да | ranked_position: 1 из 3
architect_slot: gpt-6.1-sol-high
