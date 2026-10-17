Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

Инструменты не вызывай: всё нужное уже во входе; ответ — только JSON по схеме.

Ты — ревьювер брифов. Ниже бриф, который получит один судья панели техлидов.
Твоя задача — проверить БРИФ, а не решение внутри него.

Проверяешь:
1. Полноту и точность бизнес-требований: каждое требование из ИСТОЧНИКОВ ENVELOPE
   должно быть в брифе.
2. Наличие каждой обязательной проверки из ЧЕК-ЛИСТА.
3. Пункты места (раздел «Параметры места» чек-листа).
4. Гигиену: утечки и раздувание.

Не делаешь:
- не оцениваешь качество кода, diff или архитектуры и не выносишь по ним вердикт;
- не добавляешь требований от себя: требование существует, только если оно есть в
  ИСТОЧНИКАХ ENVELOPE, ИСТОЧНИКАХ СКИЛЛОВ или в ЧЕК-ЛИСТЕ;
- не угадываешь намерения оркестратора: чего нет в тексте брифа, того нет.

Правила по пунктам чек-листа (каждый ID из ЧЕК-ЛИСТА, кроме раздела «Исключено»,
ровно один раз):
- Пункты с пометкой [L] в ЧЕК-ЛИСТЕ отсутствуют: их проверяет оркестратор. Правило
  цитаты ниже — только для пунктов без [L].
- Ровно один блок ФОРМАТ ОТВЕТА в БРИФЕ; дубль — HY-02/B3.
- Пункт [P] (должно быть): `covered` — только если в брифе есть фрагмент, полностью
  выполняющий пункт; `evidence_quote` — дословная копия этого фрагмента из БРИФА
  (до 300 символов, без перефразирования, без многоточий внутри). Если пункт
  требует артефакт «целиком», цитата подтверждает только его наличие (начало
  блока), а `covered` — только если в брифе нет пометки об обрезке этого артефакта: записи о нём в
  «Не вложено» или адреса выдержки `#L<a>-L<b>` в его обёртке `<<<ARTIFACT`.
  Выполнено частично — `partial`. Не нашёл — `missing`, `evidence_quote` пустая.
  Не можешь решить — `uncertain`.
- HY-06: формулировка пункта чек-листа, вставленная в бриф как самостоятельный
  текст без соответствующего первичного артефакта или шапки, не выполняет пункт —
  такой пункт `missing`.
- Пункт [N] (не должно быть): нарушения нет — `covered`, `evidence_quote` пустая.
  Нарушение есть — `missing`, `evidence_quote` — дословный нарушающий фрагмент.
- Пункт [P/N]: смотри «Параметры места», определи, что требуется для этого
  места, и применяй правило [P] или [N].
- `fix` — одна строка: что именно добавить, убрать или заменить в брифе. Для
  `covered` — пустая строка.
- Перед каждым `missing` для [P] перечитай бриф целиком: пропустить есть хуже, чем
  найти.

Проход по упущениям: сверь ИСТОЧНИКИ ENVELOPE с разделом BR чек-листа и ИСТОЧНИКИ
СКИЛЛОВ с разделами SK-T/SK-P. Каждое требование источника (цель, условие AC,
граница «в скоупе/вне скоупа», ограничение контракта, факт [F-NN], на который
опирается решение, обязательный пункт тип-скилла или сработавшего стандарта для
этих путей), для которого нет строки чек-листа, — в `unmapped_requirements` с
дословной цитатой из источника.
Проверь также раздел «Исключено»: если основание исключения не подтверждается
источником — это тоже `unmapped_requirements`.

Флаги (каждый — с дословной цитатой из БРИФА):
- `leakage_flags`: L1 мнение оркестратора об артефакте; L2 ожидаемый вердикт или
  подсказка; L3 выводы других судей в раунде R1 или комментарии к ним в R2 (в R2
  сами вердикты R1, приложенные дословно по шаблону дебата, — не утечка); L4
  давление: сроки, «владелец ждёт», ссылка на авторитет.
- `bloat_flags`: B1 пересказ вместо первичного артефакта; B2 непервичные дампы
  (логи вне гейтов, файлы вне diff, материалы прошлых циклов); B3 дубли одного
  артефакта; B4 инструкции, не относящиеся к панели.
  Первичные артефакты пакета целиком (envelope, diff, логи гейтов,
  execution-evidence, reviewer.json, Architecture Packet, handoff, ledger) — не
  раздувание.

Выведи ТОЛЬКО один JSON-объект, без markdown-ограждений и текста вокруг, поля в
этом порядке:

{
  "items": [
    {"id": "BR-01", "evidence_quote": "<дословно или пусто>", "status": "covered|partial|missing|uncertain", "fix": "<одна строка или пусто>"}
  ],
  "unmapped_requirements": [
    {"source": "<путь источника>", "quote": "<дословно из источника>", "fix": "<одна строка>"}
  ],
  "bloat_flags": [
    {"category": "B1|B2|B3|B4", "quote": "<дословно из брифа>", "fix": "<одна строка>"}
  ],
  "leakage_flags": [
    {"category": "L1|L2|L3|L4", "quote": "<дословно из брифа>", "fix": "<одна строка>"}
  ],
  "verdict": "APPROVE|REJECT"
}

`verdict` = `APPROVE` только если все `items` в статусе `covered`, а три списка
пусты; иначе `REJECT`.
Невалидны чужие имена ключей во вложенных объектах: flag/source_quote вместо
category/quote, лишний summary и т.п.

## ЧЕК-ЛИСТ
# Чек-лист brief-review: arch D1, cycle 1, a3, run muse-wonder-approval-20261015, поколение g1
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
SK-A-15 [P, условный] | Только раунды D<k> и C1: в брифе есть блок `ПРАВИЛА ДЕБАТОВ` (D<k>, `council-consensus.md` §4) / `ПРАВИЛА СОГЛАСИЯ` (C1, `council-consensus.md` §6) и ровно один блок `ФОРМАТ ОТВЕТА (строго)` на бриф (JD-04). `covered` — цитата заголовка блока; блока нет — `missing`. R1 и forced-dissent — в «Исключено» с основанием «не D/C1-раунд» (forced-dissent — по JD-06). Дословность шаблона и обёртку D9 сверяет пре-линт оркестратора (`council-consensus.md` §5 п.2), не Reviewer
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе
JD-03 [P] | «суди ЗАНОВО, не подтверждай прошлый вердикт автоматически»
JD-04 [P] | Ровно один блок «ФОРМАТ ОТВЕТА (строго)» на весь brief-v<K>.md (в hat-промпте или в judge-prompt); дубль = HY-02/B3. Блок в judge-prompt — дословно по universal-panel: 6 критериев, `VERDICT=PASS\ | FAIL\ | INCONCLUSIVE`, WHY, СОВЕТЫ, ОБЩИЙ ВЕРДИКТ. Блок в hat-промпте — как в `prompt-<hat>.txt` (JD-01, побайтно); отсутствие в нём `INCONCLUSIVE` — не дефект брифа, второй блок ради него запрещён
JD-06 [P/N] | R1: чужих вердиктов нет (N). R2-дебат: вердикт своей роли R1 и вердикты двух других — дословно, по шаблону `universal-panel` ШАГ 2 (P). Forced dissent — по его шаблону (P)
JD-07 [P] | Факт-карта и строка режима присутствуют; порядок блоков — по шаблону промпта universal-panel ШАГ 1 (arch) / teamlead-gate «Как передавать пакет» (code); секция КОНТЕКСТ присутствует; формат ответа — последний блок judge-prompt, если он в judge-prompt; блок формата в промпте шляпы (JD-01, JD-04) — требование «последний блок» не применяется
JD-08 [N] | Бриф самодостаточен: нет ссылок на «как обсуждали», «см. выше в чате», на файлы, которые судья не получит, как на единственный носитель содержания; в том числе на пути под каталогами с точкой на Google Drive (`.ai-team/…` в `~/Мой диск/…`) — они синхронизируются ненадёжно
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами (режим, формат, правила FAIL, границы). Блок формата в hat-промпте без `INCONCLUSIVE` при шапке тимлида с PASS/INCONCLUSIVE (SK-C-05, SK-C-08) — не противоречие (JD-04: `prompt-<hat>.txt` не меняется)
HY-04 [N] | Нет секретов (токены, ключи, пароли)
HY-05 [N] | Нет следов brief-review: «исправлено по замечанию», ссылок на вердикт ревьювера
HY-06 [N] | Формулировки пунктов чек-листа не вставлены в бриф как самостоятельный текст без соответствующего первичного артефакта/шапки; такой пункт считается отсутствующим
## Исключено
SK-A-11 | основание: раунд D1 внутри прохода a2 — полный актуальный пакет + delta + вывод panel-rework-summarizer поданы в R1 этого прохода (checklist-sources.md: «новый чек-лист R1»); в D/C1 подаются вердикты R1 a2, леджер и протокол | источник: brief-review/references/checklist-sources.md#SK-A
JD-05 | основание: seed_recheck_duty: нет (место не с наименьшим рангом) | источник: manifest.json
## Параметры места
panel: arch | round: D1 | round_type: R2-дебат | hat: realist
hat_prompt: ~/work/universal-panel/prompt-realist.txt
seat_slot: gpt-6.1-sol-high
seat_kind: panel-judge
seed_recheck_duty: нет | ranked_position: 3 из 3
architect_slot: claude-sonnet-5-5-high


## ИСТОЧНИКИ ENVELOPE
### /tmp/cel-runs/muse-wonder-serve-approval/goal.md
# ЦЕЛЬ (старт 2026-10-15 00:0x MSK)
Результат: muse-bridge (:9886, ~/work/src/cli-agent-bridge/bridges/muse-bridge/server.py) на моделях Wonder не теряет ход при `serve needs interaction (approval/request)` — не перезапускает его с нуля (exec-fallback = x2 времени + выброс 7 мин мышления) и не выглядит зависшим в DSH ("Deep diving 8m48s"), на длинной (>400k) сессии.
Критерий (тяжёлый путь): ПАНЕЛЬ ACCEPT (panel-proof.json PASS, pol-receipt/1) по коду + clean-room + ЖИВОЙ ход в DSH-слоте владельца (muse-wonder-full-1.0 Max, сессия «ai dizrapt»/длинная): ход завершается без fallback-рестарта с нуля, тайминги записаны; регрессий нет (67+ тестов).
Preset: «аналитик техлид» (default). Критичность: S2 (боевой мост) -> ДЕФОЛТ.
Ветка: НЕ dev (в dev не коммитить) -> bugfix/<...>.
Дедлайн: нет (доводить до победы).

### /Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/task.json
{
  "task_id": "REQ-MUSE-002",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "criticality_reason": "боевой мост DSH->Meta Muse (:9886), поведение ходов и протокол serve/exec, деплой через launchd",
  "title": "muse-bridge: не перезапускать ход с нуля при approval/request, ретрай net-timeout, живость долгих ходов Wonder",
  "requirement_ids": [
    "REQ-MUSE-002",
    "REQ-MUSE-003",
    "REQ-MUSE-004"
  ],
  "branch_policy": "не dev; ветка bugfix/muse-wonder-approval-retry-liveness (создаётся Coder-ом после арх-панели)",
  "base_sha": "1f1071a2330574bf90b53bbcaa65d3bf5bc29c2b",
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "setup": "default",
  "contract_freeze": "внешний OpenAI-совместимый контракт моста (/v1/chat/completions, /health, /v1/models) не менять без явного пункта; допустимы только аддитивные SSE-кадры внутри существующих полей",
  "architecture_gate": {
    "packet_sha256": "38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c",
    "verification_surface_sha256": "b3e1c7beacd1efc55a183920762f330d54f2dcc6f6d9e0634306aa70a4b70c6b",
    "protected_paths_sha256": "23b893508ca791df60756570bf930589bd15d122a3a0aa3dceb8d1b4952e58f6"
  }
}

### /Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/handoff-architect.md
# Handoff архитектору: muse-wonder-approval-and-upstream-timeouts

## 1. Контекст и целевые требования (REQ-ID)

Настоящий пакет передаёт результаты системного анализа по теме `muse-wonder-approval-and-upstream-timeouts` для проектирования изменений в `bridges/muse-bridge/server.py` (ветка `dev`, репозиторий `/Users/aazhiry1/work/src/cli-agent-bridge`).

Целевые требования:
- **REQ-MUSE-002:** При получении `approval/request` или `userInput/request` от `muse serve` ход не должен перезапускаться с нуля через `muse exec` с потерей накопленного времени мышления [F-01], [F-02], [F-03], [F-06], [F-07].
- **REQ-MUSE-003:** Транзиентная ошибка транспорта `transport error [net-timeout]: timed out waiting for response data (meta stream)` не должна приводить к немедленному отказу хода без контролируемого повтора, когда повтор допустим [F-12], [F-13], [F-14].
- **REQ-MUSE-004:** Во время длительного мышления модели (`muse-wonder-full-1.0`, `effort=max`) клиент DSH по SSE должен получать признаки жизни и прогресса мышления в реальном времени, а не только буферизованный в конце хода блок `reasoning_content` [F-16], [F-17], [F-18], [F-19].

Требование **REQ-MUSE-001** (прунинг контекста 400k/320k/200k для чужих/длинных сессий) уже реализовано в рабочем дереве `bridges/muse-bridge/server.py` и подтверждено логами `context_prune` [F-07], в рамках данного пакета выступает как ограничение совместимости [F-49].

Владелец решений: пользователь aazhiry1. Глубина исследования: standard, шесть спайков INV-01..INV-06 закрыты, остаток записан как OPEN-NN (`open-questions.md`). Модельные ходы Meta в рамках анализа не запускались, кроме уже существовавших прогонов бенча [F-44].

## 2. Architecture drivers

Каждый драйвер выведен из фактов, выбор решения здесь не делается.

- **AD-1 (REQ-MUSE-002). Ход теряется целиком при любом запросе взаимодействия.** Единственная точка обработки `approval/request` и `userInput/request` безусловно бросает `ServeUnavailable` без ответа серверу, блок `finally` убивает группу процессов serve, накопленное состояние хода теряется, мост запускает `muse exec` с полным исходным промптом [F-01] [F-02] [F-03]. Цена: 275 с и 412 с мышления на wonder (повтор в exec: 455 с до net-timeout) [F-42] [F-07], до 1521 с повтора на spark [F-41].
- **AD-2 (REQ-MUSE-002). Протокол даёт клиенту управление approval, мост им не пользуется.** Сервер ждёт решения клиента: ответ на запрос только подтверждает показ, решение идёт командой `approval/decide` с `choiceId`, `requirementId`, `commandId` [F-23] [F-28]; режим approval выбирается клиентом при `session/start` или `session/setApprovalMode` из четырёх значений [F-29] [F-32]. Мост не передаёт `approvalMode` и работает на серверном default `promptUnmatched` [F-08] [F-30].
- **AD-3 (REQ-MUSE-002). Комментарий моста о потолке режима не подтверждён.** Комментарий в `server.py:1824-1829` утверждает, что любой явный `approvalMode` отвергается `approval_mode_ceiling`. На 1.4.7 и 1.4.8 при флагах моста все четыре режима приняты, отказ -32030 есть в логе только на 1.4.2 [F-30] [F-31].
- **AD-4 (REQ-MUSE-002). Причина approval не известна.** Payload запроса не логируется, каталог инструментов без хода не получен; неизвестно, какой инструмент вызвал approval на wonder при `--disable-write --disable-shell` [F-04] [F-37]. Схема допускает subject видов shell, fileAccess, network, unixSocket, process, tool [F-26].
- **AD-5 (REQ-MUSE-002). Общий путь для spark и wonder.** 27 из 29 переходов в exec приходятся на muse-spark-*, код не ветвится по модели; любое изменение обработки approval затрагивает оба семейства [F-40].
- **AD-6 (REQ-MUSE-003). Мост не ретраит net-timeout.** Повтор в exec срабатывает только по подстроке `network connection could not be opened`; `net-timeout` помечен как не повторяемый [F-12]. Ошибка приходит как stderr CLI, место её определения в мосте отсутствует [F-45].
- **AD-7 (REQ-MUSE-003). Сбои не коррелируют с размером промпта и effort на имеющейся выборке.** Бенч: 800 KB на max прошёл за 281.3 с, 800 KB на high упал за 31.5 с; короткие сбои на 20 с встречаются и на effort=low, и на max без prune [F-44] [F-43]. Внешний слой нестабилен: в логе форвардера прокси 3893 повтора для api.meta.ai [F-46].
- **AD-8 (REQ-MUSE-003). Повтор ограничен состоянием SSE.** Прошлый цикл закрепил правило: повтор допустим до первого контентного кадра, после первой дельты запрещён [F-49]. Новый live-стрим (AD-9) меняет эту границу.
- **AD-9 (REQ-MUSE-004). Клиент видит только пустые data-чанки.** SSE открывается до запуска serve, затем каждые 15 с идёт data-чанк с пустым `content`; summary.N накапливаются в памяти и выдаются одним куском после хода [F-16] [F-17]. Тесты закрепляют отсутствие `: keepalive` в теле [F-20].
- **AD-10 (REQ-MUSE-004). Эталон live-стрима есть в соседнем мосте.** Droid-мост отдаёт `content` и `reasoning_content` дельтами с коалесценцией 40 мс, таймаутом записи 3 с и SSE-комментарием `: keepalive` [F-18].
- **AD-11 (REQ-MUSE-004). Реакция клиента неизвестна.** Документации DSH о idle-watchdog нет; единственные клиентские параметры: `timeoutMs` и `streamIdleTimeoutMs` по 1900000 мс, `maxRetries: 0` [F-19] [F-47]. Мост проверен только на ~600 с по комментарию кода [F-47].
- **AD-12 (REQ-MUSE-003 и REQ-MUSE-004). Версия 1.4.8 добавляет наблюдаемость повторов провайдера.** Уведомление `turn/modelRetryScheduled` сообщает о паузе повтора до завершения хода [F-36].
- **AD-13 (все REQ). Среда меняется под ногами.** Лаунчер Muse CLI автообновился с 1.4.7 до 1.4.8 в 2026-10-15 05:29 MSK; схемы совпадают по approval и методам [F-36].

## 3. As-is границы

Границы системы и потоки (каждый поток привязан к факту):

- DSH (клиент, OpenAI-совместимый, SSE) → muse-bridge `:9886` (`bridges/muse-bridge/server.py`) по HTTP `POST /v1/chat/completions` [F-19] [F-16]. Клиентские таймауты 1900000 мс, повторов клиента нет [F-19].
- muse-bridge → `muse serve` (stdio, JSON-RPC, MSP), один процесс на запрос с флагами `--disable-write --disable-shell --trust-workspace --no-session-log`, сессия не сохраняется [F-09] [F-02]. Запросы: `initialize`, `initialized`, `session/start`, `turn/start` [F-08].
- muse-bridge → `muse exec` (CLI, прямой путь и fallback) с флагами `--yolo --disable-web-tools --disable-reminders`; exec запускается с полным промптом через `--prompt-file` [F-09] [F-03].
- `muse` → Meta API через обёртку `muse-cli.sh` и форвардер прокси `127.0.0.1:10816` → верхний прокси ProxyRack. Внешний слой, вне контроля моста [F-46] [F-22].
- Деплой: репозиторий `bridges/muse-bridge/server.py` и копия в `~/.dsh/bridges/muse-bridge/server.py` побайтово идентичны; процесс под launchd `com.user.dsh-muse-bridge` [F-21] [F-51].
- Параллелизм: `MAX_CONCURRENT=2`, ожидание слота до 1800 с, затем HTTP 503 [F-21].

Внутри границы моста: сборка argv, цикл чтения serve без idle-таймаута (тишина до дедлайна 1800 с), `SERVE_SPAWN_TIMEOUT_S=30 с` на рукопожатие, повтор exec по сетевой подстроке, повтор по hard threshold с прунингом [F-15] [F-12] [F-49].

Вне границы: логика approval-судьи Meta (в serve отключена, в exec включена по умолчанию, в мосте подавлена `--yolo`) [F-11], политика прокси, UI DSH.

## 4. Контракты (инвентарь, только факты)

### 4.1 MSP (serve, JSON-RPC по stdio)

- Версия схемы: отпечаток 1.4.7 `sha256:6de32db08bbb` (совпадает с логом моста); 1.4.8 по методам и approval идентична, 69 методов, добавлено уведомление `turn/modelRetryScheduled` [F-22] [F-25] [F-36].
- Серверные запросы, требующие ответа: `approval/request`, `userInput/request`; результат RequestReceipt (пустой объект) [F-23].
- Серверные уведомления: `approval/requested`, `approval/updated`, `approval/resolved`, `userInput/requested`, `userInput/settled`, `session/approvalModeChanged` [F-24].
- Клиентские команды: `approval/decide`, `approval/listPending`, `session/setApprovalMode`, `userInput/answer|cancel|clarify|interrupt`, `turn/cancel`, `turn/interrupt`, `turn/steer` [F-25].
- `approval/decide`: обязательные `approvalId`, `choiceId`, `commandId`, `requirementId`, `sessionId`; результат `status=accepted` и `terminal`; при `terminal=false` придёт обновлённый `approval/request` [F-28].
- Ошибки: -32050 approvalNotFound, -32051 approvalAlreadyResolved, -32052 approvalChoiceInvalid, -32053 approvalRequirementStale, -32054 approvalReviewerUnavailable, -32030 commandRejected [F-28].
- Режимы: `allowAll`, `promptUnmatched`, `onRequest`, `denyUnmatched` (закрытый enum); default при отсутствии поля и при `null` — `promptUnmatched`; смена режима действует со следующего действия и не решает ожидающий approval [F-29] [F-30] [F-32].
- Способы прекратить ожидание: `approval/decide` с решением `denied` или `abort`, `turn/cancel`, `turn/interrupt`; «отклонить без решения» по проводу отсутствует; влияние отмены хода на pending approval не описано [F-23] [F-33].
- Данные хода: `item/delta` (поле `field`, например `summary.0`), `turn/completed` с `terminal`, `error`, `usage`, `timeToFirstTokenMs` [F-35].
- Внешний источник сообщает для 1.3.0, что serve не завершает ожидание решения по таймеру (проверено 360 с); для 1.4.x это не проверялось [F-39].

### 4.2 OpenAI-совместимый SSE моста (`:9886`)

- При `stream:true` HTTP 200 `text/event-stream` и role-кадр отправляются до ожидания слота и запуска serve; признак жизни: data-чанк `{"content": ""}` каждые 15 с (`MUSE_BRIDGE_KEEPALIVE_S`) [F-16].
- После хода: один кадр `reasoning_content`, затем `tool_calls`, `content` кусками около 300 символов, `finish_reason`, `usage`, `[DONE]` [F-17].
- Ошибка после начала SSE уходит кадром `error` и `[DONE]`, частичный текст отбрасывается [F-17] [F-12].
- Клиентский контракт DSH: `api: openai-completions`, `supportsReasoningEffort: true`, окна wonder 400000 токенов [F-19].
- Эталон live-контракта: droid-мост `:9882` (дельты `content` и `reasoning_content`, комментарий `: keepalive`, таймаут записи 3 с) [F-18].

### 4.3 Режимы отказа (as-is)

| Ситуация | Поведение |
|---|---|
| `approval/request` или `userInput/request` | `ServeUnavailable`, serve убивается, exec с нуля [F-01] [F-02] [F-03] |
| net-timeout в exec | ошибка клиенту, повтора нет [F-12] |
| сетевая подстрока «could not be opened» в exec | один повтор exec [F-12] |
| hard threshold контекста | прунинг и один повтор до первого контентного кадра [F-49] |
| клиент отключился | процесс убивается, fallback не запускается [F-03] |

## 5. NFR-набросок (фактические значения)

Baseline-значения для quality scenarios:

- Serve-ход wonder без approval: 8-94 с на коротких промптах (24 хода), 205-237 с на длинных [F-43].
- Serve-ход wonder до approval: 275 с и 412 с [F-42].
- Повтор в exec после approval на wonder: 455 с до net-timeout при промпте 768118 символов; в первом инциденте 2242 с до отключения клиента при промпте 1326216 символов [F-07] [F-06].
- Net-timeout на wonder: 20 с (effort=low и effort=max), 452 с с текстом «after 2 provider attempts» [F-43].
- Бенч exec на wonder: 100 KB за 51.1 с, 400 KB за 251.2 с, 800 KB за 281.3 с (max); 1200 KB упал за 236.1 с (сетевой отказ после 5 попыток провайдера); 800 KB на high упал за 31.5 с [F-44]. Выборка пять точек (OPEN-02).
- Интервал признаков жизни клиенту: 15 с, пустой data-чанк; шаг прогресса reasoning: ни одного до конца хода [F-16] [F-17].
- Клиентские таймауты DSH: 1900000 мс общий и idle; повторов нет [F-19]. Таймаут хода моста 1800 с, повтор exec получает полный таймер заново [F-15].
- Квота: 2 одновременных запуска [F-21].
- Живой сбой serve 2026-10-15 00:10:10: 20 с до net-timeout при том, что короткий exec `PONG` на тот же слот проходит [F-43] [F-46].

Риски (для `risks`):
- R-1: ответ на approval без знания запрошенного действия (OPEN-01, OPEN-07).
- R-2: повтор поверх повторов провайдера CLI (OPEN-05) увеличивает время сбоя; в бенче видны попытки 3/4 и 4/4 [F-44].
- R-3: live-стрим меняет границу безопасного повтора (AD-8) [F-49].
- R-4: незакоммиченные изменения моста и тестов (+2941 строк) и совпадение копии с репозиторием делают откат единственной точкой возврата [F-51].
- R-5: изменение затрагивает spark (27 из 29 случаев) [F-40].
- R-6: смена версии CLI вне контроля моста [F-36] (OPEN-09).

## 6. Ограничения изменения и откат

- Тесты, закрепляющие текущее поведение, потребуют решения: `test_approval_falls_back_to_exec_without_decide` (нет `approval/decide`, переход в exec), `test_s1_data_ticks_before_done_preserve_content_and_tools` (нет `: keepalive` в теле), `test_t18_...`, `test_t27_...`, класс R4 [F-20] [F-52]. Теста на долгую тишину до approval нет [F-52].
- Прогон тестов: 67 passed на старте анализа; команда `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py` (из брифа).
- Каталоги вне зоны: профили DSH `~/.dsh/profiles/{web,desktop}/cordis.patch.yml`; не трогать `muse-spark-*` без явной причины [F-21] [F-19].
- Деплой по плану прошлого цикла: резервная копия, правка репозитория и тестов, копия в `~/.dsh/bridges/muse-bridge/`, перезапуск launchd, проверка `/health` и `/v1/models`; откат возвратом резервной копии и перезапуском [F-51] [F-49].
- Сдача по канону владельца требует проверки на живой работе (дёрнуть ход wonder большого размера), а не только тестов; модельные ходы выполняет исполнитель после решения архитектора.

## 7. Расхождения с исходными допущениями (обратный канал)

- Комментарий `server.py:1824-1829` о том, что явный `approvalMode` отвергается потолком, не воспроизведён на 1.4.7 и 1.4.8 [F-30] [F-31]. Влияет на формулировку REQ-MUSE-002, не меняет его.
- Число approval-переходов в логе 29, а не 30 [F-05]; число методов схемы 69, а не 68 [F-25].
- README репозитория описывает keepalive как SSE-комментарий, код шлёт пустые data-чанки [F-48]. Влияет на REQ-MUSE-004.
- Эталон внешнего проекта (1.3.0) утверждает, что запрос `approval/request` не приходит; на 1.4.7 мост получил именно этот метод [F-39].

## 8. Blocking open questions

- **OPEN-07 (БЛОКЕР):** политика approval для неинтерактивного моста (авторазрешение, отказ или передача решения пользователю DSH). Блокирует выбор решения по REQ-MUSE-002; ветки REQ-MUSE-003 и REQ-MUSE-004 продолжаются независимо.

## 9. Assumptions (OPEN-NN МОЖНО ПРОДОЛЖИТЬ)

- ASM-01 (OPEN-01): запросить approval может любой не отключённый флагами serve инструмент; мост получает логирование безопасных полей params (toolName, subject.kind, protectedWrite, judgeEscalated, список choiceId и decision) без rawArgs.
- ASM-02 (OPEN-02): net-timeout не зависит от размера и effort в пределах бенча; проектирование повтора без привязки к размеру.
- ASM-03 (OPEN-03): клиент опирается на `streamIdleTimeoutMs=1900000`; паттерн droid-моста применим к DSH.
- ASM-04 (OPEN-04): summary.N могут приходить по ходу хода; проверка добавлением отметок времени.
- ASM-05 (OPEN-05): повторы CLI независимы от повторов моста; повтор моста ограничивается малым числом попыток; `turn/modelRetryScheduled` наблюдается через логирование.
- ASM-06 (OPEN-06): `approval/decide` с решением `denied` допускает продолжение хода, при отсутствии прогресса ход завершается `turn/cancel`.
- ASM-07 (OPEN-08): net-timeout внешний транзиентный фактор; повтор логируется.
- ASM-08 (OPEN-09): схемы 1.4.7 и 1.4.8 эквивалентны по approval и протоколу; `serverInfo.version` проверяется при каждом старте.

## 10. Feasibility-заключение по направлениям (без выбора)

Варианты, которые допускают факты; выбор принадлежит архитектору.

| Направление | Вариант | Факты | Вердикт |
|---|---|---|---|
| REQ-MUSE-002 | ответ на `approval/request` командой `approval/decide` | [F-23] [F-28] | выполнимо с условиями: нужен `choiceId` из `availableChoices`, payload неизвестен (OPEN-01, OPEN-07) |
| REQ-MUSE-002 | явный `approvalMode` при `session/start` | [F-29] [F-30] | выполнимо: все четыре режима приняты на 1.4.7 и 1.4.8; последствия режима для хода не наблюдались (OPEN-01, OPEN-07) |
| REQ-MUSE-002 | `session/setApprovalMode` после старта | [F-32] | выполнимо: принят, действует со следующего действия, ожидающий approval не решает |
| REQ-MUSE-002 | `turn/cancel` или `turn/interrupt` вместо exec с нуля | [F-33] | выполнимо с условиями: влияние на pending approval не описано (OPEN-06); отмена хода сама не сохраняет мышление |
| REQ-MUSE-003 | ограниченный повтор net-timeout в мосте | [F-12] [F-44] [F-49] | выполнимо с условиями: до первого контентного кадра, учёт повторов провайдера (OPEN-05), граница повтора зависит от выбора по REQ-MUSE-004 |
| REQ-MUSE-004 | live-доставка `reasoning_content` по `item/delta` | [F-17] [F-18] [F-35] | выполнимо с условиями: время прихода summary.N не установлено (OPEN-04) |
| REQ-MUSE-004 | SSE-комментарий `: keepalive` вместо пустого data-чанка | [F-18] [F-20] [F-47] | выполнимо с условиями: реакция клиента не проверена (OPEN-03), текущий тест закрепляет обратное |
| REQ-MUSE-004 | событие `turn/modelRetryScheduled` как признак жизни | [F-36] | выполнимо с условиями: только 1.4.8, на живом ходе не наблюдалось (OPEN-05) |

## 11. Маппинг в architecture-packet.json

- `evidence`: ссылки [F-01]..[F-52] из `evidence-ledger.md`.
- `blocking open questions`: OPEN-07.
- `assumptions`: ASM-01..ASM-08 (OPEN-01..06, 08, 09).
- `boundaries/contracts`: разделы 3 и 4.
- `quality scenarios`: раздел 5 (baseline).
- `risks`: R-1..R-6 раздела 5.
- Трассировка: REQ-MUSE-002 → AD-1..AD-5; REQ-MUSE-003 → AD-6..AD-8, AD-12; REQ-MUSE-004 → AD-9..AD-12.

### /Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/evidence-ledger.md
[F-01] В bridges/muse-bridge/server.py единственная точка обработки approval/request и userInput/request в ServeRun.execute (_handle_event) безусловно выбрасывает ServeUnavailable без отправки JSON-RPC ответа | bridges/muse-bridge/server.py:1757-1762 (Explorer A [A-01][A-03]) | 2026-10-15
[F-02] При выбросе ServeUnavailable блок finally в ServeRun.execute вызывает self.close() и убивает процесс-группу muse serve, теряя накопленные final_text, deltas, summary_parts, summaries, usage, turn_id и session_id | bridges/muse-bridge/server.py:1748-1755,1945-1948 (Explorer A [A-04][A-05]) | 2026-10-15
[F-03] При перехвате ServeUnavailable в run_attempt мост (если клиент не отключился) логирует fallback и запускает новый процесс muse exec с полным исходным промптом attempt_prompt с нуля (via=exec-after-serve-fallback) | bridges/muse-bridge/server.py:2400-2446 (Explorer A [A-06][A-14]) | 2026-10-15
[F-04] Параметры события approval/request (какой инструмент или разрешение запрошено) нигде в мосте не логируются и не сохраняются: в лог и исключение попадает только имя метода | bridges/muse-bridge/server.py:1761-1762,2429 (Explorer A [A-07]) | 2026-10-15
[F-05] В логе bridge.log зафиксировано ровно 29 строк serve needs interaction (approval/request): 27 на моделях muse-spark-* и 2 на muse-wonder-full-1.0 (effort=max); число 30 из отчёта Explorer B не воспроизведено | grep -c 'serve needs interaction' bridge.log дал 29, grep по wonder дал 2 (строки 1034 и 1249); сумма по версиям 2+8+17+2=29 (Explorer D [D-32]) | 2026-10-15
[F-06] В инциденте 2026-10-13 23:20:04 ход muse-wonder-full-1.0 (effort=max) в serve через 275 с получил approval/request (23:24:39), перезапустился в exec (prompt_chars=1326216) и через 2242 с завершился отключением клиента (client gone) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1034-1042 (Explorer B [B-08][B-09]) | 2026-10-15
[F-07] В инциденте 2026-10-14 23:50:43 ход muse-wonder-full-1.0 (effort=max, после context_prune 408666->319789 токенов) через 412 с получил approval/request (23:57:35), перезапустился в exec (prompt_chars=768118) и через 455 с упал в 00:05:10 с ошибкой transport error [net-timeout]: timed out waiting for response data (meta stream) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1243-1252 (Explorer A [A-08][A-09], Explorer B [B-08][B-10][B-11]) | 2026-10-15
[F-08] При вызове session/start мост передаёт только commandId, workspaceRoot, providerId="meta", modelId и не передаёт поле approvalMode | bridges/muse-bridge/server.py:1824-1829 (Explorer A [A-10][A-31], Explorer B [B-06]) | 2026-10-15
[F-09] Флаги запуска muse serve в мосте: --disable-write --disable-shell --trust-workspace --no-session-log --provider meta --model <id>; при этом в muse exec дополнительно передаются --yolo --disable-web-tools --disable-reminders | bridges/muse-bridge/server.py:1380-1401,1648-1659 (Explorer A [A-12][A-15]) | 2026-10-15
[F-10] В CLI muse 1.4.7-R6101.1 подкоманда muse serve --help не имеет флагов --approval-mode, --yolo, --disable-approval, --approval-judge, --permission-profile, --disable-web-tools, --disable-reminders; режим подтверждения в serve выбирается только по протоколу MSP | muse-cli.sh serve --help / muse-cli.sh exec --help (Explorer B [B-17][B-18][B-19]) | 2026-10-15
[F-11] В соответствии с публичным тикетом meta-models/muse-code-sdk#80 в режиме muse serve встроенный LLM approval judge отключён (outcome="disabled", reason="setting_off"), тогда как в muse exec он по умолчанию включён (--approval-judge on) и дополнительно в мосте подавлен флагом --yolo | https://github.com/meta-models/muse-code-sdk/issues/80 (Explorer B [B-15][B-25]) | 2026-10-15
[F-12] В bridges/muse-bridge/server.py сетевой повтор в exec срабатывает только по подстроке NETWORK_RETRY_MARKER = "network connection could not be opened"; ошибка "transport error [net-timeout]: timed out waiting for response data (meta stream)" имеет retryable=False и мостом не ретраится | bridges/muse-bridge/server.py:114,2435-2445 (Explorer A [A-21]) | 2026-10-15
[F-13] В логе bridge.log ошибка net-timeout на muse-wonder-full-1.0 зафиксирована как на коротких интервалах ~20 с (2026-10-14 13:04:34 effort=low; 2026-10-15 00:10:10 effort=max без prune), так и на длинных ходах 452 с (2026-10-14 20:39:01 с текстом "after 2 provider attempts") и 455 с (2026-10-15 00:05:10 в exec-fallback) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1250-1252 (Explorer B [B-13]) | 2026-10-15
[F-14] В бенчмарке /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv на muse-wonder-full-1.0 промпты 100 KB (51.1 с), 400 KB (251.2 с) и 800 KB (281.3 с) на effort=max прошли с rc=0, а промпт 1200 KB (max) упал за 236.1 с с ошибкой "network connection could not be opened within 15 seconds (after 5 provider attempts)" и повторный прогон 800 KB (high) упал за 31.5 с с ошибкой "transport error [net-timeout]: timed out waiting for response data (meta stream)" | /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv:1-6 | 2026-10-15
[F-15] Таймаут хода в мосте задаётся MUSE_BRIDGE_TIMEOUT_S = 1800 с (и для serve, и для exec отдельно; при fallback на exec таймер 1800 с стартует заново); таймаут инициализации serve SERVE_SPAWN_TIMEOUT_S = 30.0 с; отдельного idle-таймаута чтения в цикле serve нет | bridges/muse-bridge/server.py:65,138,1455-1460,1696-1725 (Explorer A [A-16][A-17][A-18][A-19][A-20]) | 2026-10-15
[F-16] При stream:true мост сразу (до ожидания слота и запуска serve) отправляет HTTP 200 text/event-stream, стартовый role-чанк и запускает поток _keepalive_loop, который каждые KEEPALIVE_S = 15 с шлёт SSE data-чанк с пустой дельтой {"content": ""}, а не SSE-комментарий ": keepalive" | bridges/muse-bridge/server.py:1185,2034-2070 (Explorer A [A-24][A-25], Explorer C [C-11][C-12]) | 2026-10-15
[F-17] Во время выполнения хода в serve дельты item/delta с полями summary.N накапливаются в памяти (summary_parts / summaries) и не отправляются клиенту до завершения ServeRun.execute; после окончания хода _send_sse отправляет весь reasoning_content одним чанком и затем режет финальный content по ~300 символов | bridges/muse-bridge/server.py:1781-1796,1890-1895,2170-2198 (Explorer A [A-27], Explorer C [C-13]) | 2026-10-15
[F-18] В соседнем droid-мосте (/Users/aazhiry1/work/src/cli-agent-bridge/server.py, порт :9882) реализована live-отправка SSE-дельт content и reasoning_content через sse_writer с коалесценцией ~40 мс и таймаутом записи LIVE_WRITE_TIMEOUT_S = 3 с, а также keepalive в виде SSE-комментария ": keepalive\n\n" каждые 15 с | /Users/aazhiry1/work/src/cli-agent-bridge/server.py:130,134-137,4894-4926,5118-5157 (Explorer C [C-15][C-16]) | 2026-10-15
[F-19] В профилях клиента DSH (web и desktop cordis.patch.yml) для провайдера muse-bridge заданы api: openai-completions, timeoutMs: 1900000, streamIdleTimeoutMs: 1900000, retryPolicy: {mode: normal, maxRetries: 0}, supportsReasoningEffort: true | /Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml:426-437, /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml:327-338 (Explorer C [C-01][C-02]) | 2026-10-15
[F-20] Существующие тесты в tests/test_muse_bridge_killpg.py жёстко проверяют текущее поведение: test_approval_falls_back_to_exec_without_decide проверяет отсутствие approval/decide в rpc.jsonl и переход в exec при approval/request, а test_s1_data_ticks_before_done_preserve_content_and_tools проверяет отсутствие b": keepalive" в SSE-теле | tests/test_muse_bridge_killpg.py:1182-1185,1278-1305 (Explorer A [A-25][A-36]) | 2026-10-15
[F-21] Лимит параллельных запусков моста MAX_CONCURRENT = 2 (ожидание слота до TIMEOUT_S = 1800 с, далее HTTP 503); деплой-копия /Users/aazhiry1/.dsh/bridges/muse-bridge/server.py побайтово идентична репозиторной bridges/muse-bridge/server.py и управляется launchd-агентом com.user.dsh-muse-bridge | bridges/muse-bridge/server.py:66,2375-2384 (Explorer A [A-22][A-40], Explorer C [C-19][C-33]) | 2026-10-15
[F-22] Схема MSP экспортируется офлайн командой schema generate-json-schema --out DIR (и generate-ts); отпечаток схемы 1.4.7 sha256:6de32db08bbb совпадает со строкой serve init в bridge.log; повторный экспорт 1.4.8 дал msp.schema.json и manifest.json в стабильной поверхности | muse-cli.sh schema generate-json-schema --out /tmp/sa-verify/s: wrote manifest.json, msp.schema.json (stable surface); /tmp/cel-runs/muse-wonder-serve-approval/explorer-D-msp-approval.md D-01 | 2026-10-15
[F-23] Сервер шлёт клиенту ровно два запроса, требующих ответа: approval/request и userInput/request; результат обоих RequestReceipt (пустой объект) означает только «показано», решение идёт отдельной клиентской командой approval/decide или userInput/answer; ошибка или обрыв соединения оставляют запрос pending и он переиздаётся при следующем subscribe; отклонить без решения по проводу нельзя | python3 -I: sorted(requests) в /tmp/sa-verify/s/msp.schema.json дал approval/request, userInput/request; $defs.RequestReceipt.description (Explorer D D-02 D-03) | 2026-10-15
[F-24] Уведомления сервера по approval и userInput: approval/requested, approval/updated, approval/resolved, userInput/requested, userInput/settled, session/approvalModeChanged; мост обрабатывает по имени метода только approval/request и userInput/request и не реагирует на approval/requested | schema notifications (Explorer D D-04 D-21); bridges/muse-bridge/server.py:1761-1762 | 2026-10-15
[F-25] Клиентские методы approval и ввода: approval/decide, approval/listPending, session/setApprovalMode, userInput/answer, userInput/cancel, userInput/clarify, userInput/interrupt, turn/cancel, turn/interrupt, turn/steer, turn/start, session/start; всего 69 методов и в схеме 1.4.7, и в схеме 1.4.8 (число 68 из отчёта Explorer D не воспроизведено); метода перечисления инструментов нет | python3 -I: len(methods)=69 для обеих схем, symmetric difference множеств методов пуст; /tmp/cel-runs/muse-wonder-serve-approval/explorer-D/schema-json/msp.schema.json | 2026-10-15
[F-26] ApprovalRequestParams содержит обязательные approvalId, availableChoices, currentRequirementId, itemId, judgeEscalated, protectedWrite, rawArgs, sessionId, sourceRange, subject, taskId, toolCallId, toolName, turnId, viewCursor; subject.kind принимает значения shell, fileAccess, network, unixSocket, process, tool | схема $defs.ApprovalRequestParams (строка 277 в файле 1.4.7) и $defs.ApprovalSubject (строка 572) (Explorer D D-06 D-37) | 2026-10-15
[F-27] ApprovalChoice содержит choiceId (произвольная строка без enum), decision, label, scope, acceptsFeedback, rulePreview; enum ApprovalDecision (открытый): approved, approvedForSession, approvedPolicyAmendment, denied, deniedPolicyAmendment, timedOut, abort; конкретные значения choiceId на живом ходе не получены | схема $defs.ApprovalChoice, ApprovalDecision (строки 87 164 в файле 1.4.7) (Explorer D D-07 D-35) | 2026-10-15
[F-28] ApprovalDecideParams требует approvalId, choiceId (из текущих availableChoices, иначе -32052), commandId (UUIDv7), requirementId (равен currentRequirementId, устаревший даёт -32053), sessionId; результат содержит status accepted и признак terminal (false означает что придёт обновлённый approval/request); коды ошибок: -32050 approvalNotFound, -32051 approvalAlreadyResolved, -32052 approvalChoiceInvalid, -32053 approvalRequirementStale, -32054 approvalReviewerUnavailable, -32030 commandRejected | схема $defs.ApprovalDecideParams, ApprovalDecideResult и список errors (Explorer D D-08 D-09 D-11) | 2026-10-15
[F-29] ApprovalMode задан закрытым enum allowAll, promptUnmatched, onRequest, denyUnmatched; поле session/start.approvalMode принимает значение enum либо null; при отсутствии поля и при явном null сервер выбирает собственный default; session/start описан как единственная поверхность, объявляющая политику неинтерактивного запуска | python3 -I: $defs.ApprovalMode.enum в /tmp/sa-verify/s/msp.schema.json дал allowAll, promptUnmatched, onRequest, denyUnmatched; $defs.SessionStartParams.properties.approvalMode.description (Explorer D D-12 D-13) | 2026-10-15
[F-30] На serve 1.4.8 при аргументах моста (--disable-write --disable-shell --trust-workspace --no-session-log) session/start без approvalMode вернул эффективный режим promptUnmatched с source startup; на 1.4.7 и 1.4.8 явные allowAll, promptUnmatched, onRequest, denyUnmatched приняты и вернулись как эффективные режимы; на 1.4.7 так же принят null | python3 -I /tmp/cel-runs/muse-wonder-serve-approval/explorer-D/poc_session_start.py omitted (мой прогон, 1.4.8, 1.96 с, stderr пуст); probe-null.json probe-promptUnmatched.json probe-onRequest.json в той же папке (Explorer D D-24..D-29) | 2026-10-15
[F-31] Отказ -32030 approval_mode_ceiling в bridge.log встречается только на serve 1.4.2 (2026-10-05 11:44:20 и 11:45:13), на 1.4.3 1.4.4 1.4.6 1.4.7 таких строк нет; на 1.4.7 и 1.4.8 явный approvalMode не отвергнут, поэтому комментарий моста server.py:1824-1829 о том что любое явное значение отвергается не подтверждён на этих версиях | bridge.log строки 260 и 267; PoC probe-*.json (Explorer D D-30 D-31); bridges/muse-bridge/server.py:1824-1829 | 2026-10-15
[F-32] session/setApprovalMode после старта принял все четыре режима подряд, включая повышение до allowAll, с applyOutcome completed и source approvalReconfigure; по описанию схемы смена режима действует со следующего действия и не решает уже ожидающий approval ретроактивно | мой прогон poc_session_start.py omitted на 1.4.8 (четыре ответа status accepted); $defs.SessionSetApprovalModeParams/Result (Explorer D D-14 D-33) | 2026-10-15
[F-33] Способы прекратить ожидающий approval по проводу: approval/decide с выбором decision denied или abort, turn/cancel {commandId, sessionId, turnId?}, turn/interrupt {commandId, sessionId, turnId?, retract?} (ход завершён когда пришёл turn/completed с terminal cancelled); влияние turn/cancel и turn/interrupt на запись pending approval в схеме не описано | схема $defs.TurnCancelParams, TurnInterruptParams, RequestReceipt (Explorer D D-15) | 2026-10-15
[F-34] Ввод пользователя: userInput/request несёт questions с options и selection, необязательный autoResolutionMs; ответ userInput/answer, отказ userInput/cancel, дополнение userInput/clarify, userInput/interrupt прерывает запрос и останавливает ход; исходы userInputOutcome: answered, cancelled, interrupted, clarified, timedOut, aborted | схема $defs.UserInputRequestParams (строка 8077) и UserInputOutcome (строка 8035) (Explorer D D-16) | 2026-10-15
[F-35] turn/completed несёт terminal (completed, failed, cancelled), необязательные durationMs, timeToFirstTokenMs, usage и error с kind, message, retryable, quota; item/delta несёт delta, itemId, sessionId, viewCursor и необязательный field (например summary.0, output); виды item включают reasoning, toolCall, webSearch, subagent, workflow, hookRun | схема $defs.TurnCompletedParams, ItemDeltaParams (строка 2474), ItemKind (Explorer D D-17 D-18) | 2026-10-15
[F-36] Лаунчер muse автообновился с 1.4.7 до 1.4.8-R6256.1 в 2026-10-15 05:29 MSK (бинарь 1.4.7 удалён); схемы 1.4.7 и 1.4.8 совпадают по методам, requests и определениям approval; 1.4.8 добавляет уведомление turn/modelRetryScheduled, описанное как наблюдаемая до завершения хода пауза провайдерского повтора модели с полями attempt, maxAttempts, retryDelayMs, errorKind | muse-cli.sh --version дал Muse Code 1.4.8 (1.4.8-R6256.1); python3 -I: turn/modelRetryScheduled in notifications True для 1.4.8, множества методов равны; $defs.TurnModelRetryScheduledParams.description | 2026-10-15
[F-37] Реальный payload approval/request (toolName, subject, choiceId) на живом ходе не получен; каталог инструментов без хода не найден: ни методы схемы, ни результат session/start, ни muse exec --help, ни model-profile show не перечисляют инструменты | Explorer D D-35 D-36 D-38; probe-*.json (поля session/start result); muse-cli.sh exec --help | 2026-10-15
[F-38] В muse serve --help нет флагов approval-mode, yolo, disable-approval, approval-judge, permission-profile, а ключей таймаутов и ретраев в тексте помощи нет: единственный универсальный флаг -c/--config KEY=VALUE (значения JSON); в muse exec --help есть --approval-mode untrusted/on-request/never, --approval-judge, --yolo, --disable-approval, --max-model-steps, --user-input-auto-resolve | muse-cli.sh serve --help: grep по config, timeout, retry нашёл только строку --config <KEY=VALUE>; muse-cli.sh exec --help: grep по timeout, retry, max-model-steps нашёл только --max-model-steps; Explorer D D-39 | 2026-10-15
[F-39] Публичное наблюдение стороннего проекта на Muse Code 1.3.0: approvals в serve приходят уведомлениями approval/requested, ответ клиента approval/decide с requirementId, варианты allow_once и abort, «Serve never times them out; tested for 360 s», совет «Never omit the mode: a durable host defaults to allowAll»; расхождение с 1.4.7: схема 1.4.7 содержит и запрос approval/request, и уведомления, а мост на 1.4.7 получил именно метод approval/request | https://github.com/kontourai/station/issues/2452 (Explorer B [B-27] и DISCREPANCY); схема 1.4.7 requests | 2026-10-15
[F-40] По версиям serve сбоев с передачей хода в exec по approval/request: 1.4.2 два, 1.4.3 восемь, 1.4.4 семнадцать, 1.4.7 два, 1.4.6 ноль; все 27 случаев на muse-spark-* и оба случая на muse-wonder-full-1.0 проходят один и тот же код ServeRun.execute без ветвления по модели | python3 -I скан bridge.log (Explorer D D-32); bridges/muse-bridge/server.py:1757-1762 | 2026-10-15
[F-41] Для 27 случаев на muse-spark-* исход выполнения после перехода в exec в таблице Explorer B: успешное завершение на интервале от 19 с до 1521 с, один обрыв по таймеру rc=-9 на 257 с, один ход до 1800 с с обрезкой, одно отключение клиента; повтор с нуля стоит до 25 минут | /tmp/cel-runs/muse-wonder-serve-approval/explorer-B-runtime-cli.md раздел B1 (строки таблицы по spark) | 2026-10-15
[F-42] Время serve-хода wonder до approval: 275 с (2026-10-13 23:20:04, approval в 23:24:39) и 412 с (2026-10-14 23:50:43, approval в 23:57:35), то есть пользователь теряет 4-7 минут мышления; других событий в логе между serve turn и approval нет кроме /health | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1034 и 1243-1250 (мой повтор sed по строкам) | 2026-10-15
[F-43] Тайминги serve-ходов wonder в логе с 2026-10-13 без approval: 8-94 с на коротких промптах (24 хода) и 205 с, 232 с, 237 с на длинных; сбои net-timeout: 20 с (2026-10-14 13:04:34, effort=low), 452 с (2026-10-14 20:39:01, текст «after 2 provider attempts»), 20 с дважды в 2026-10-15 00:10:10 (effort=max, без prune) | /tmp/cel-runs/muse-wonder-serve-approval/explorer-B-runtime-cli.md B2 и B-13; bridge.log:1250-1252 | 2026-10-15
[F-44] Бенч exec на wonder: прогон 800 KB на effort=max прошёл за 281.3 с, а прогон 800 KB на effort=high упал за 31.5 с с net-timeout, то есть сбой не коррелирует с размером промпта и effort на этой выборке из пяти строк; в строке 1200 KB в stderr видны повторы потока модели «retrying meta model stream in 500ms (attempt 3/4)» и «(attempt 4/4)» перед финалом «after 5 provider attempts» | /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv (cat, 5 строк данных, фоновый процесс завершён) | 2026-10-15
[F-45] Текст ошибки «timed out waiting for response data (meta stream)» в коде моста отсутствует: мост передаёт stderr CLI как есть и распознаёт только подстроку «network connection could not be opened»; значение формулировки «after N provider attempts» и ключ конфигурации таймаута провайдера в справке CLI и в мосте не найдены | grep -n по трём строкам net-timeout, timed out waiting, provider attempts в bridges/muse-bridge/server.py вернул пустой результат; bridges/muse-bridge/server.py:114 | 2026-10-15
[F-46] Форвардер прокси 127.0.0.1:10816 (общий для нескольких приложений) пишет в лог 151006 строк; повторы «retry … timed out» встречаются 26789 раз, из них для api.meta.ai:443 3893 повтора, повторов «incomplete SOCKS5 reply» 32; верхний прокси global.rotating.proxyrack.net | grep -c 'retry api.meta.ai', grep -c 'retry .*timed out', grep -c 'retry .*incomplete SOCKS5' и wc -l в /Users/aazhiry1/Library/Logs/Factory/proxyrack-forward.log | 2026-10-15
[F-47] Комментарий в коде моста фиксирует причину пустых data-чанков: OpenAI SDK в DeepSeek Harness ждал заголовков до своего таймаута около 600 с и обрывал долгий ход как Request timed out; влияние пустых чанков, reasoning_content и SSE-комментариев на idle-watchdog клиента pi-ai в документации DSH не найдено, требует живой проверки по докстрингу моста | bridges/muse-bridge/server.py:27-28,1182-1185 (Explorer C [C-09][C-10][C-07]) | 2026-10-15
[F-48] README репозитория утверждает что muse-мост держит соединение SSE-комментариями «: keepalive», код отправляет пустые data-чанки; README развёрнутой копии устарел (строки о non-stream JSON и отсутствии SSE) | /Users/aazhiry1/work/src/cli-agent-bridge/README.md:28-37 против bridges/muse-bridge/server.py:2064-2070 (Explorer C [C-30][C-31][C-32]) | 2026-10-15
[F-49] Прошлый прогон REQ-MUSE-001 зафиксировал в своём плане правило: повтор после ошибки допустим только до первого контентного кадра, а при добавлении live-стриминга повтор после первой дельты запрещён (_content_started); пруннинг и повтор по hard threshold реализованы в рабочем дереве (HARD_THRESHOLD_ERR_SUBSTR в server.py:87-88) | .ai-team/runs/muse-wonder-foreign-session-20261014/arch-spec.md:168-173 (Explorer C [C-22][C-23]); grep -n HARD_THRESHOLD_ERR_SUBSTR в server.py | 2026-10-15
[F-50] Решение прошлого цикла bridge-heal: обработку approval через approval/decide оставили закрытой («keep ServeUnavailable»): двухшаговый handshake, при отказе модель в serve может зациклить повторы; на тот момент форма параметров approval/request в мосте и тестах не была описана (фикстура теста шлёт params пустым объектом) | .ai-team/runs/muse-bridge-heal-20261014/context/open-questions.md:9 (Explorer A [A-13][A-33]); tests/test_muse_bridge_killpg.py:1012 | 2026-10-15
[F-51] Рабочее дерево ветки dev содержит незакоммиченные изменения моста и тестов (server.py +1018 строк, тесты +1983 строки; 2941 вставок, 60 удалений) и неотслеживаемые каталоги .ai-team/ и analysis/; деплой-копия побайтово идентична репозиторной; в каталоге деплоя лежит резервная копия server.py.bak-1791815617 | git diff --stat и git status --short в /Users/aazhiry1/work/src/cli-agent-bridge; cmp bridges/muse-bridge/server.py /Users/aazhiry1/.dsh/bridges/muse-bridge/server.py вернул IDENT; ls /Users/aazhiry1/.dsh/bridges/muse-bridge/ | 2026-10-15
[F-52] Тесты, закрепляющие поведение при ServeUnavailable: test_t18_serve_fallback_and_network_retry_preserve_context_retry_budget, test_t27_serve_unavailable_with_reflected_prompt_does_not_leak_to_log, класс R4 (клиент отключился при живом serve, exec не запускается); теста на долгую тишину перед approval нет, задержка в фикстуре только sleep | tests/test_muse_bridge_killpg.py:348-380,2068,2554,2585-2618,989-1021 (Explorer A [A-37][A-38][A-39]) | 2026-10-15

### /Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/research-plan.md
INV-01 | Какие методы approval и userInput, режимы approvalMode, поля session/start и session/setApprovalMode, форма события, requirementId, варианты решений и отмена хода заданы в MSP-схеме | вывод muse schema через обёртку muse-cli.sh и пути в схеме | interface analysis: экспорт схемы и разбор путей | 30 | факты схемы с путями и значениями enum | каждый пункт закрыт фактом или OPEN | блокирует INV-02 и INV-03 | closed | F-23 | 10 | факты F-22 F-23 F-24 F-25 F-26 F-27 F-28 F-29 F-33 F-34 F-35; число методов 69 вместо 68 у Explorer D
INV-02 | Какие approvalMode принимает session/start на serve 1.4.7 и 1.4.8 при флагах моста и что отвечает denyUnmatched | живой PoC в /tmp без модельного хода: initialize, session/start, session/setApprovalMode | feasibility PoC read-only JSON-RPC | 30 | точные ответы сервера по каждому режиму | каждый режим закрыт ответом или OPEN | зависит от INV-01 | closed | F-30 | 6 | факты F-30 F-31 F-32; отказ approval_mode_ceiling воспроизведён не был, он в логе только на 1.4.2
INV-03 | Какой инструмент запрашивает approval на Wonder при выключенных write и shell | схема, справка CLI exec и serve, лог моста, документы Meta | code inspection и log analysis и interface analysis | 30 | установленный триггер или план добычи payload | триггер назван с источником или OPEN с планом добычи | зависит от INV-01 | closed | F-37 | 8 | NOT FOUND: payload и каталог инструментов без модельного хода не получены; остаток в OPEN-01 с планом логирования
INV-04 | Где задаётся net-timeout, что значит after N provider attempts, влияют ли effort и размер промпта, есть ли ключи таймаутов и ретраев | лог моста, server.py, справка exec и serve, бенч results.tsv, лог форвардера прокси | log analysis и code inspection и interface analysis | 30 | происхождение ошибки и сводка по бенчу | каждое подвопрошение закрыто фактом или OPEN | независимый | closed | F-45 | 12 | факты F-12 F-13 F-14 F-38 F-43 F-44 F-45 F-46; происхождение и семантика попыток не найдены, остаток в OPEN-02 OPEN-05 OPEN-08
INV-05 | Что доступно в serve в реальном времени и что DSH делает с пустыми чанками, reasoning_content и SSE-комментариями | server.py моста, server.py droid-моста, профили cordis.patch.yml, схема item/delta | code inspection и interface analysis | 30 | факты о item/delta и поведении клиента | каждое подвопрошение закрыто фактом или OPEN | независимый | closed | F-47 | 8 | факты F-16 F-17 F-18 F-19 F-35 F-36 F-47 F-48; поведение клиента и время прихода summary.N не найдены, остаток в OPEN-03 OPEN-04
INV-06 | Какие тесты, квоты, деплой и откат ограничивают изменение и каково влияние на muse-spark | tests/test_muse_bridge_killpg.py, server.py, деплой в ~/.dsh, git status | code inspection и document analysis | 15 | перечень ограничений и протокол отката фактами | каждое ограничение закрыто фактом или OPEN | независимый | closed | F-52 | 6 | факты F-20 F-21 F-40 F-41 F-49 F-50 F-51 F-52; протокол отката берётся из плана прошлого цикла: резервная копия, копия в ~/.dsh, перезапуск launchd

### /tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md
2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)
2026-10-15 13:39 MSK | находки арх-панели F-002, F-003, F-004, F-006 (OBJECT автора при C1, PAUSED_OWNER) | владелец выбрал в чате по каждой: «blocking (Рекомендуется)» | опции: blocking / non-blocking / excluded | итог: все четыре blocking, входят в instructions для Architect delta

## Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2 (PAUSED_OWNER, ответы AskUserQuestion, явные)
- F-001 (барьер повтора / ненаблюдаемое действие, ASM-010 vs AD-003): **blocking**
- F-002 (таймаут live-записи после захвата _wlock, AD-004/BND-004): **blocking**
- F-003 (бюджет 1800 с без резерва на cleanup/выдачу, grace после cancel): **non-blocking** (учесть в брифе Coder)
- F-004 (потеря reasoning при расхождении snapshot, CD-001): **non-blocking** (учесть в брифе Coder)
- F-005 (откат denyUnmatched обходится exec --yolo, AD-006/AD-007): **blocking**
Итог: вердикт a2 = NEEDS WORK (3 blocking: F-001, F-002, F-005) → panel-rework-summarizer → Architect delta a3 (arch_panel_to_architect: использовано 1, будет 2 из 5).

## Решения оркестратора по директиве владельца «хватит спрашивать, делай сам как принято в индустрии» (2026-10-15 ~22:50 MSK) — вопросы Architect a3
- Q-010 (at-least-once для ненаблюдаемых действий): НЕТ. Принято решение Architect: по умолчанию `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=pre-action` (повтор только до записи `turn/start`). Переключение на `observed-items` — без изменения кода, только после живого аудита ASM-010 (закрытие тяжёлым путём) и отдельной записи здесь. Обоснование: неидемпотентные побочные эффекты по индустриальной практике не повторяют; write/shell отключены флагами serve (EVD-005), остаточный риск — web/MCP.
- Q-009 (обход -32030 клиентским approve): НЕТ (exec-fallback по AD-006, при denyUnmatched — без exec).
- Q-001 (selective deny по protectedWrite/judgeEscalated): после сбора живых payload; сейчас только логирование.
- Q-004 (summary только в конце хода): решается спайком VER-013 до реализации AD-004; при NOT_MET REQ-MUSE-004 сообщается как не выполнено.


## ИСТОЧНИКИ СКИЛЛОВ
### /Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md
---
name: architecture
description: >
  Python-overlay для универсального architect-software-product: применяет командные
  границы Litestar/FastAPI, async SQLAlchemy, Pydantic, Alembic, HTTP/event/data
  contracts и Python verification surface к Architecture Packet. Использовать только
  вместе с universal Architect для S2/S3-задач в Python-бэкенде.
---

# Architecture — Python overlay

Этот файл не задаёт второй архитектурный процесс. Сначала полностью выполнить:

1. `~/Мой диск/skils/ai-sdlc/universal/architect-software-product/SKILL.md`;
2. его `references/protocol.md`;
3. `.agents/agents/architecture.md`, `.agents/agents/docs.md` и корневой `AGENTS.md`
   конкретного репозитория.

Главный выход остаётся один:
`.ai-team/runs/<run-id>/architecture/architecture-packet.json` с
`profile=python-aisdlc-gcge`.

## Приоритет правил

1. Утверждённые требования и решения владельца.
2. `AGENTS.md`, действующие ADR и реальный код репозитория.
3. Этот Python-overlay.
4. Общие defaults модели.

Личный baseline и стек «по привычке» не использовать. Если проект не Litestar/FastAPI
или не следует описанным слоям, зафиксировать фактический стек и не навязывать шаблон.

## Входной evidence

До решения открыть и сослаться в packet минимум на:

- точки входа API/consumer/job;
- service/domain/repository границы;
- модели и migrations затронутых данных;
- `pyproject.toml`/lockfile и реальные версии;
- существующие тесты, CI-команды и архитектурные правила;
- последний успешный аналог изменения, если он есть.

Использовать `rg`, import graph и чтение символов. Название файла, класса или метода
не включать в handoff, если их существование не подтверждено кодом.

## Python-specific boundaries

Если репозиторий следует командному слоению, проверить:

```text
api/ → services/ → repository → models
          ↓
        domain
```

- route/handler: transport, validation, вызов service, response;
- service: business policy, без импорта ORM model;
- repository: storage operations и mapping;
- domain: infrastructure-independent entities/contracts;
- внешний I/O: отдельный client/adapter с timeout и typed errors.

Не добавлять слой ради схемы. Для другого фактического устройства описать существующие
границы и минимальную delta, а не перестраивать проект без требования.

В `boundaries[]` указать allowed/forbidden dependencies и `verification_ids`.
Исполняемый import contract предлагать только если он окупается и одобрен как новая
dependency/process delta.

## Async и failure semantics

Для async Python явно спроектировать:

- timeout для каждой I/O-операции и cleanup;
- cancellation и partial failure;
- retry только для перечисленных transient errors;
- idempotency/deduplication для повторов;
- concurrency limit, backpressure и порядок результатов;
- ownership соединений, сессий и транзакций.

`time.sleep`, sync HTTP/DB client внутри async flow и бесконечный retry запрещены.
Для dynamic/paginated/streaming источника определить аккумуляцию и независимый сигнал
полноты; один snapshot не считается полным источником.

## Contract deltas

В `contract_deltas[]` фиксировать только изменения:

- Pydantic/DTO: поля, типы, required/default/nullability и validation;
- HTTP: method/path/request/response/error/status/idempotency/versioning;
- event: producer/consumer/schema/order/dedup/replay/compatibility;
- data: owner/schema/index/constraints/retention/classification;
- dependency: package, verified version range, purpose, operational cost и exit path.

Cross-repo mirror, compatibility window и mixed-version behavior указывать явно.
Breaking change, auth/security model, новая major dependency и cross-service contract —
one-way decision с человеческим approval.

`contract_deltas[]` непустой только если **текущая** задача явно требует сменить
контракт. Иначе пакет `BLOCKED`, а не «улучшенный» контракт. Канон:
`.agents/agents/scope-and-contracts.md`. Архитектор не ходит в чужие KEY.

## Data и migrations

Если меняется persisted state:

- Alembic migration и downgrade/forward-fix policy;
- online/offline характер DDL, lock и длительность;
- backfill/checkpoint/retry/dedup;
- совместимость старого и нового кода во время rollout;
- контроль целостности до/после;
- rollback без предположения, что потерянные данные восстановятся сами.

В `evolution` нельзя писать просто `NOT_APPLICABLE`: добавить проверяемую причину.

## ADR и proposals

Формат и путь ADR брать из `.agents/agents/docs.md` и существующего `docs/adr/INDEX.md`.
Не создавать `docs/architecture/adr/` параллельно командному каталогу.

- ADR-lite — локальное обратимое решение.
- ADR-full — дорогой откат, несколько репозиториев, NFR/security, спор или ≥3 опции.
- Sensitivity check и PoC применять по командному ADR-full contract.

Architect пишет proposal только в `architecture/proposals/`. Он не выполняет
`uv add`, не меняет `pyproject.toml`, lockfile, CI, migrations и product code.
Такие изменения перечисляются в contract/materialization plan и проходят approval.

## Views

Не требовать C1+C2 механически. Выбрать минимальный набор:

- Context/Container — меняются system ownership или внешние связи;
- Component — новое внутреннее разделение, которое Coder может понять неоднозначно;
- Dynamic/sequence — async flow, retry, transaction или несколько сервисов;
- Deployment — rollout, queue, worker, storage или failure domain;
- DFD — sensitive data, auth или trust boundary.

Каждый `views[]` содержит вопрос и artifact reference.

## Python verification surface

Включить exact команды из репозитория. Если применим стандартный командный набор:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest -q
```

Дополнить targeted regression, contract/integration/migration/runtime checks. Не писать
несуществующую команду ради заполнения packet. Verifier обязан запустить полный frozen
набор; Coder log не заменяет независимое выполнение.

Для каждого изменения определить чувствительность:

- bugfix: red без fix → green с fix;
- новый contract: negative/boundary test;
- migration: upgrade + data check + допустимая rollback/forward-fix проверка;
- concurrency/time/network: повтор/seed/fault injection по риску;
- architecture boundary: нарушение действительно делает arch-test красным.

## Что Architect не делает

- Не создаёт ветки и коммиты.
- Не пишет готовую реализацию и не фиксирует внутренние сигнатуры без контрактной причины.
- Не разбивает работу на искусственные задачи «≤1 день»; порядок реализации формирует
  Orchestrator/Coder по утверждённому packet.
- Не устанавливает зависимости и не ослабляет существующие gates.
- Не выдаёт self-eval или grep по заголовкам за architecture review.
- Не меняет согласованный внешний контракт без явного указания в текущей задаче.
- Не разворачивает исследование на соседние Jira-KEY.

## Definition of Done overlay

- Universal Architecture Packet валиден в `approved` phase.
- Все Python-утверждения подтверждены кодом/конфигом/официальной документацией.
- Слои, async semantics и ownership отражают реальный проект.
- Contract deltas содержат compatibility и verification IDs.
- Stateful change имеет migration/rollout/rollback и integrity checks.
- Verification surface содержит реальные project commands и targeted checks.
- ADR path/format не конфликтует с `.agents/agents/docs.md`.
- Architect не изменил product worktree.
- `contract_deltas[]` пуст либо в текущей задаче есть явное указание менять
  согласованный внешний контракт (`.agents/agents/scope-and-contracts.md`).

## Эскалация

`BLOCKED`, если отсутствует NFR, schema ownership, compatibility policy, право на
breaking/security/dependency decision или способ проверить критичный contract. Не
додумывать значения и не передавать Coder условный пакет как approved.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.

### Список файлов Architecture Packet (arch)
/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json
/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/arch-gate-a3.json
/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/task.json
/tmp/cel-runs/muse-wonder-serve-approval/goal.md
/tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md
/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/handoff-architect.md
/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/evidence-ledger.md
/Users/aazhiry1/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/open-questions.md
/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md
/Users/aazhiry1/work/src/cli-agent-bridge/docs/adr/0003-muse-serve-approval-allowall.md
/Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md


## БРИФ
<<<BRIEF_BEGIN
Ты — Реалист. Твоя задача — оценить реализуемость, ресурсы, сроки, зависимости. Ключевой вопрос: «Что нужно чтобы это взлетело?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на практической применимости: можно ли это реально внедрить, какие зависимости нужны, что блокирует, сколько усилий потребует.

Оцени ВСЕ 6 критериев. При FAIL давай СРАЗУ ВСЕ советы по исправлению (список действий).

ФОРМАТ ОТВЕТА (строго):
1. КОРРЕКТНОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
2. ПОЛНОТА: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
4. РИСКИ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS|FAIL
   WHY=<обоснование>
   СОВЕТЫ (при FAIL): <список конкретных действий>
ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG

PANEL-NONCE: aae4804df6379017
ARTIFACT-SHA256: 38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: aae4804df6379017» и «ARTIFACT-SHA256: 38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c».

Ты — судья архитектурного совета техлидов, идёт совещание (раунд D1). Предмет оценки — Architecture Packet задачи muse-bridge (мост DeepSeek Harness → Meta Muse), а не код. Ниже: пакет и приложения, вердикты раунда 1 (твоей роли и двух других ролей, дословно), сводный леджер находок и правила раунда. Цель совещания — согласованное решение по КАЖДОЙ находке. Суди ЗАНОВО, чужой вердикт автоматически не подтверждай; позиция меняется только с ARG или NEW.

РЕЖИМ: architecture. Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки.

КОНТЕКСТ. Владелец сообщил, что модель Muse Wonder в DeepSeek Harness «вообще не работает»: ход мышления до 7 минут, затем молчаливый перезапуск с нуля через exec и сетевой обрыв. Цель задачи, критерий готовности, REQ-ID и границы (внешний контракт моста заморожен) — в приложенных goal.md и task.json. Предыдущий этап (REQ-MUSE-001, прунинг контекста) уже в рабочем дереве и не пересматривается.

Анти-галлюцинация и факт-карта. Перед FAIL «нет X / не описано Y» перечитай приложенные артефакты целиком и не помечай то, что в тексте уже есть. Сущности из приложенного ledger и факт-карты существуют. Чего нет в приложенных материалах и ты не уверен — пиши «не могу проверить», это не FAIL. Инструментов тебе не нужно: все входы ниже. Не изменяй никакие файлы.

ФАКТ-КАРТА (проверено оркестратором 2026-10-15; источники — в приложенном ledger):
- Muse CLI автообновился с 1.4.7 до 1.4.8 (15.10.2026 05:29 MSK); по методам, режимам approval и ошибкам схемы MSP stable они эквивалентны (ledger).
- На muse serve 1.4.7 и 1.4.8 явный approvalMode при session/start принимается для allowAll, promptUnmatched, onRequest, denyUnmatched; отказ approval_mode_ceiling (-32030) в логах моста встречался только на serve 1.4.2 (ledger).
- Решение владельца по политике approval: «Авторазрешение (allowAll)» (файл owner-decisions.md, приложен).
- Сетевые сбои Meta-стрима воспроизводились независимо от размера промпта (бенч в ledger); форвардер прокси 127.0.0.1:10816 — внешняя нестабильная зависимость вне репозитория.

Проверь пакет по существу: границы и слои, внешние контракты (HTTP, SSE, MSP JSON-RPC, CLI), сценарии качества (NFR) и их измеримость, модель угроз и trust boundary, evolution (совместимость, rollout, rollback), verification surface и protected_paths. В пакете у каждого нового решения должны быть ≥2 альтернативы с причиной выбора; их отсутствие — FAIL по критерию АЛЬТЕРНАТИВЫ. Проверь, что решения опираются на факты [F-NN], и что каждый [F-NN] найден в приложенном evidence ledger; пункты Python-overlay architecture.md и правила проекта приложены ниже.

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L100-L118 sha256=56d2bff7f8ee1b11fd6e7b8a37722bb5fde599a0b9b7d5470684dd91c952991c
ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД (обязательно, оба режима):
1. Найденный FAIL проход НЕ завершает. Дойди до последней подкатегории рубрики и
   только потом пиши вердикт. ЗАПРЕЩЕНО обрывать поиск на первой найденной ошибке.
2. Выдай ВСЕ замечания сразу одним списком F-блоков, blocking и non-blocking вместе
   (поле priority). ЗАПРЕЩЕНЫ: поштучная выдача («главное сейчас, остальное после
   исправления»), откладывание («проверю в следующем раунде»), резерв про запас.
3. Один дефект класса X в нескольких местах — ОДИН F-блок со ВСЕМИ местами
   (locations: file:line, …), найденными поиском по всему diff. Формулы «и т.п.»,
   «и другие места», «например» вместо перечисления недопустимы.
4. Разные root cause в одном месте — разные F-блоки. Каждый F-блок самодостаточен:
   file:line, правило, evidence (цитата), ожидаемое исправление, критерий проверки,
   priority.
5. Перед вердиктом пройди список подкатегорий второй раз (self-sweep) и допиши
   пропущенное, пометив [sweep].
6. Последние строки ответа: `COVERAGE: <k>/<K> подкатегорий` и
   `FINDINGS_COMPLETE: <N>` (N = число F-блоков). Нет строк, k<K или N ≠ числу
   F-блоков — вердикт malformed.
7. Дефект вне дельты цикла тоже выдаётся с меткой [pre-existing] — молчание о найденном ради «дельты» запрещено.
   Приоритет по месту (§3, «Diff-scope»): в файле, изменённом задачей, — blocking; в коде вне скоупа задачи — non-blocking.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-with-architect/references/arch-council.md#L25-L31 sha256=78e4fbebce9b7ba2db216de31e2177c350d031c4f650537a480bbced50fd1874
ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)
Везде, где правила или формат ответа говорят «file:line», допустим один из якорей:
(а) architecture-packet.json:<N> — строка N поданной копии пакета;
(б) architecture-packet.json#<ID> — ID сущности пакета (AD-, QA-, VER-, EVD-, ASM-NNN, ID границы, contract delta, угрозы, риска);
(в) <файл proposals>:<N> — строка приложенного proposal-файла (ADR и др.);
(г) [F-NN] — факт из приложенного evidence ledger.
Цитата правила репозитория, ADR или architecture.md допустима, как и в правилах ниже. Якорь вне перечня или не существующий в поданных файлах ссылкой не считается.
ARTIFACT_END>>>

ВЕРДИКТ ТВОЕЙ РОЛИ В РАУНДЕ 1 (Реалист):
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r18/seats/1/verdict.md#L3-L39 sha256=2670e0b24f208e14402d1a70895ccd9aad96a7b2b370a2eb051d9c67b38e5982
Подтверждение канона: общий канон ~/Мой диск/Context/AGENTS.md прочитан целиком до <!-- КАНОН-КОНЕЦ -->; проектных файлов AGENTS.md, .agents/AGENTS.md, CLAUDE.md в приложенных материалах нет (по arch-spec.md §0 в репозитории отсутствуют).
F-блоки: нет.
FIXCHECK RW-001: fixed — architecture-packet.json#AD-003 — ACTION_POSSIBLE защёлкивается до записи turn/start (serve) и при старте процесса (exec), область по умолчанию pre-action запрещает повтор/fallback после неё при любой ошибке, observed-items только после Q-010 и закрытия ASM-010; acceptance закрыт T-R07/T-R07b в architecture-packet.json#VER-002 для serve и exec (ровно один побочный эффект).
FIXCHECK RW-002: fixed — architecture-packet.json#AD-004 — единый бюджет LIVE_WRITE_TIMEOUT_S=3 с на вызов _sse_write по монотонным часам охватывает ожидание _wlock и запись для всех писателей, зависший клиент уходит в _client_gone/killpg; acceptance закрыт T-L08b в architecture-packet.json#VER-003, где первым блокируется keepalive-кадр.
FIXCHECK RW-003: fixed — architecture-packet.json#AD-006 — при denyUnmatched exec --yolo запрещён в любой роли единым предикатом в run_attempt (architecture-packet.json#EVD-029) с контролируемым терминальным исходом exec_fallback_disabled; acceptance закрыт матрицей T-A11b/T-A14 в architecture-packet.json#VER-001 при сохранении одного пре-турнового exec для allowAll.
SUB Корректность/1.1: PASS — architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007 связаны единым предикатом допуска architecture-packet.json#BND-003 без противоречий счётчиков.
SUB Корректность/1.2: PASS — architecture-packet.json#AD-002 (защёлкивание, grace от защёлкивания, CONTROL_WRITE_TIMEOUT_S), architecture-packet.json#AD-003 (E = D − FINISH_RESERVE_S, turn/start без ack, EOF/ошибки записи после turn/start терминальны).
SUB Корректность/1.3: PASS — architecture-packet.json#EVD-008, architecture-packet.json#EVD-029, architecture-packet.json#EVD-030 опираются на [F-30], [F-28], [F-18]; потребление live reasoning клиентом честно понижено до architecture-packet.json#ASM-003.
SUB Полнота/2.1: PASS — architecture-packet.json#AD-001, architecture-packet.json#AD-002 покрывают REQ-MUSE-002, architecture-packet.json#AD-003 — REQ-MUSE-003 в заявленной области pre-action, architecture-packet.json#AD-004 — REQ-MUSE-004, architecture-packet.json#AD-005 наследует REQ-MUSE-001.
SUB Полнота/2.2: PASS — architecture-packet.json#ASM-010, architecture-packet.json#ASM-011, architecture-packet.json#ASM-012, architecture-packet.json#Q-004, architecture-packet.json#Q-010 имеют наблюдаемые пути закрытия, architecture-packet.json#VER-013 гейтит реализацию AD-004.
SUB Реализуемость/3.1: PASS — architecture-packet.json#BND-001, architecture-packet.json#BND-002, architecture-packet.json#BND-003, architecture-packet.json#BND-004 ложатся на существующие Handler/ServeRun/Run одного файла без новых зависимостей, фейковый MSP расширяется по architecture-packet.json#VER-001.
SUB Реализуемость/3.2: PASS — architecture-packet.json#AD-007, architecture-packet.json#VER-008 задают деплой копией server.py, bootout/bootstrap для смены режима и учение отката allowAll -> denyUnmatched -> allowAll.
SUB Риски/4.1: PASS — architecture-packet.json#THREAT-001, architecture-packet.json#AD-001 при сохранённых --disable-write --disable-shell и песочнице, architecture-packet.json#AD-007 делает откат denyUnmatched реальным без exec.
SUB Риски/4.2: PASS — architecture-packet.json#THREAT-002, architecture-packet.json#QA-002 запрещают rawArgs и тела вопросов, свободные строки аудита проходят allowlist-рендер, канарейки закреплены в architecture-packet.json#VER-001.
SUB Риски/4.3: PASS — architecture-packet.json#THREAT-003, architecture-packet.json#RISK-002, architecture-packet.json#RISK-005, architecture-packet.json#AD-006 ограничивают циклы, повторы, удержание слотов и автообновление CLI; прокси честно оставлен внешней зависимостью.
SUB Альтернативы/5.1: PASS — architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007 содержат по несколько альтернатив с причинами отклонения.
SUB Альтернативы/5.2: PASS — architecture-packet.json#QA-009, architecture-packet.json#AD-003 фиксируют потолок MAX_CONCURRENT=2, процесс на запрос и очередь до E − MIN_ATTEMPT_REMAINING_S без роста параллелизма от повторов.
SUB Соответствие контексту/6.1: PASS — architecture-packet.json#CD-001 является единственной дельтой внутри существующего delta.reasoning_content, внешний контракт и профили DSH заморожены architecture-packet.json#AD-005.
SUB Соответствие контексту/6.2: PASS — architecture-packet.json#BND-005 отражает фактический stdlib-стек репозитория вместо навязанного Litestar/FastAPI слоения, protected_paths и baseline-коммит отделены.
SUB Соответствие контексту/6.3: PASS — architecture-packet.json#VER-001, architecture-packet.json#VER-002, architecture-packet.json#VER-003, architecture-packet.json#VER-005, architecture-packet.json#VER-007, architecture-packet.json#VER-009, architecture-packet.json#VER-012, architecture-packet.json#VER-013 задают red->green, полный набор, тяжёлый путь и спайк до дорогого блока.
1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Решения взаимно согласованы: политика session/start (AD-001), внутриходовой decide с терминальным защёлкиванием (AD-002), позитивная граница ACTION_POSSIBLE и единый предикат нового процесса (AD-003), единый предел _sse_write (AD-004) и режимный запрет exec при denyUnmatched (AD-006/AD-007) опираются на EVD-008, EVD-026, EVD-029, EVD-030 и факты [F-28], [F-30]; арифметика D/E/FINISH_RESERVE_S сходится с худшей уборкой 12 с и grace 15 с.
2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-MUSE-002 закрыт сохранением хода, REQ-MUSE-003 честно закрыт только в доказуемой области pre-action с зафиксированной ценой RISK-009 и путём расширения Q-010, REQ-MUSE-004 не объявляется выполненным без спайка VER-013 и тяжёлого пути VER-009; ограничение REQ-MUSE-001 наследовано AD-005, все ASM/Q имеют способ закрытия логом, спайком или решением владельца.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Что нужно, чтобы взлетело, названо и доступно: один файл моста и один файл тестов, stdlib без новых зависимостей, расширение существующей фикстуры install_protocol_wrapper, три этапа red->green с гейтом VER-013 перед самым неопределённым блоком, деплой копией под launchd и учение VER-008; основная стоимость — детерминированные фейковые тесты времени и блокировок, внешние зависимости Meta/ProxyRack и автообновление CLI не блокируют этапы 1 и 2.
4. РИСКИ: VERDICT=PASS
   WHY=Главный риск allowAll принят владельцем и ограничен флагами хоста и песочницей, аудит не переобещан полным, секреты закрыты allowlist и канарейками, удержание обоих слотов ограничено счётчиками, grace, единым пределом записи и абсолютным дедлайном, а операционный откат denyUnmatched после a3 действительно снимает авторазрешения ценой доступности RISK-010.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового решения есть как минимум две альтернативы с причиной выбора; на уровне архитектуры выбранный инкрементальный однопроцессный мост обоснованно выигрывает у статус-кво exec-рестарта, у denyUnmatched/promptUnmatched с denied и у переписывания на очередь-писатель или async-шлюз при текущем масштабе одного владельца; при росте нагрузки ломается не корректность, а пропускная способность: процесс на запрос при MAX_CONCURRENT=2, очередь с предусмотренной ошибкой после E−120 с, внешний прокси и provider attempts CLI.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Замороженный внешний контракт задачи соблюдён, CD-001 остаётся внутри существующего поля reasoning_content с явной семантикой расхождения, фактический стек репозитория не заменяется шаблоном overlay, baseline REQ-MUSE-001 отделяется первым коммитом, protected_paths сторожит VER-012, а verification surface содержит реальные команды репозитория, полный набор тестов и тяжёлый путь владельца.
RECHECK: seed_hex=281cbe27 ranked_order=muse-wonder-full-1.0,gemini-4-argon-high,gpt-6.1-sol-high,claude-sonnet-5-5-high результат=OK
ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 0
VERDICT: PASS
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ (вердикты раунда 1 двух других ролей; две служебные строки маркеров раунда R1 в выдержках опущены):
Эксперт Скептик:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r18/seats/2/verdict.md#L3-L41 sha256=d4902bfa73aec6a1831473770bec92626c2703a9ee869583af7f07d69de41f73
Подтверждаю: прочитал общий канон ~/Мой диск/Context/AGENTS.md целиком до <!-- КАНОН-КОНЕЦ -->; проектные файлы правил (AGENTS.md, .agents/AGENTS.md, .agents/CLAUDE.md, CLAUDE.md) в рабочей папке отсутствуют.

FIXCHECK RW-001: fixed — architecture-packet.json#AD-003 — ненаблюдаемый барьер a2 заменён позитивной защёлкой ACTION_POSSIBLE (до записи первого байта turn/start в serve и при старте процесса в exec, EVD-029); в области по умолчанию pre-action повтор и fallback после защёлки запрещены при любой ошибке и пустом stdout, упразднён внутренний сетевой повтор exec, компромисс для mid-turn net-timeout явно оформлен в RISK-009 и Q-010, а в VER-002 добавлены сценарии T-R07 (заглушка с побочным эффектом без item/approval/текста для serve и exec даёт ровно 1 попытку и 1 эффект) и T-R07b (опциональная область observed-items с warning).
FIXCHECK RW-002: fixed — architecture-packet.json#AD-004 — LIVE_WRITE_TIMEOUT_S=3 с сделан единым бюджетом одного вызова _sse_write по time.monotonic(), охватывающим и ожидание захвата _wlock (acquire с остатком бюджета), и запись в сокет с восстановлением таймаута до освобождения замка для всех писателей (role, keepalive, live-sink, терминальная выдача, [DONE], BND-004, EVD-030); в VER-003 добавлен сценарий T-L08b, где под _wlock первым блокируется keepalive-кадр, после чего приходит summary-дельта, и слот с группой serve освобождаются за короткий предел без ожидания 300 с.
FIXCHECK RW-003: fixed — architecture-packet.json#AD-006 — при активном MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched запуск exec (--yolo) запрещён в любой роли (fallback и повтор) в единственной точке создания Run (run_attempt, BND-003, EVD-029); при -32030 и любых пре-турновых сбоях serve запрос завершается контролируемым отказом 502/SSE error с причиной exec_fallback_disabled(denyUnmatched), область действия отражена в AD-006, AD-007, evolution.rollback и docs/adr/0003-muse-serve-approval-allowall.md:122-141, а в VER-001 и VER-010 добавлены проверки матрицы T-A11b и T-A14.

SUB 1/1.1: PASS — решения AD-001..AD-007 взаимно согласованы: единый предикат допуска нового процесса в architecture-packet.json#AD-003 и #BND-003 связывает защёлку ACTION_POSSIBLE, терминальную деградацию #AD-002, границу _content_started из #AD-004 и запрет exec при denyUnmatched из #AD-006/#AD-007 без противоречий между счётчиками и бюджетами.
SUB 1/1.2: PASS — граничные условия и режимы отказа закрыты: в architecture-packet.json#AD-002 задано единое правило защёлкивания на любую ошибку approval/decide кроме benign -32051 (все коды [F-28]) и любую ошибку userInput/cancel, CONTROL_WRITE_TIMEOUT_S=5 с на запись управляющей команды и отсчёт APPROVAL_CANCEL_GRACE_S=15 с по time.monotonic() от момента защёлкивания включая запись cancel/decide (T-A09c); в #AD-003 выделен резерв FINISH_RESERVE_S=35 с между E и D и порог старта попытки MIN_ATTEMPT_REMAINING_S=120 с (T-R08, T-R10).
SUB 1/1.3: PASS — все утверждения пакета EVD-001..EVD-030 опираются на факты [F-01]..[F-52] приложенного evidence ledger и проверенные ссылки на код; в architecture-packet.json#EVD-015, #AD-004 и #CD-001 статус потребления live reasoning_content клиентом DSH и роли пустых data-чанков приведён в строгое соответствие с допущением #ASM-003 и фактами [F-18], [F-47], а коллизия имён F-NNN устранена переименованием находок панели в PF-a1-NNN и PF-a2-NNN.
SUB 2/2.1: PASS — целевые требования покрыты: REQ-MUSE-002 закрыт решениями architecture-packet.json#AD-001, #AD-002, #AD-006, #AD-007; REQ-MUSE-003 закрыт в доказуемо безопасной пре-турновой области решением #AD-003 с явной фиксацией ограничения для mid-turn сбоев в #RISK-009 и #VER-009; REQ-MUSE-004 закрыт решением #AD-004 со спайком-гейтом #VER-013 и диагностикой #VER-011; ограничения REQ-MUSE-001 сохранены без пересмотра в #AD-005 и #VER-004.
SUB 2/2.2: PASS — открытые вопросы OPEN-01..OPEN-09 и Q-001..Q-010 разложены в architecture-packet.json#ASM-001..#ASM-012; блокер OPEN-07 закрыт владельцем (#ASM-009, #EVD-009), для закрытия #ASM-010 добавлен безопасный журнал инструментальных item и полей timeToFirstTokenMs/usage в #BND-002 и #VER-001 (T-A15), а для OPEN-04 введён предреализационный спайк #VER-013.
SUB 3/3.1: PASS — изменения локализованы в существующих компонентах bridges/muse-bridge/server.py (ApprovalPolicy #BND-001, ServeRun #BND-002, Handler.run_attempt #BND-003, Handler._sse_write/_send_sse #BND-004) и одном тестовом файле tests/test_muse_bridge_killpg.py без новых внешних зависимостей и слоёв.
SUB 3/3.2: PASS — выкат и откат в architecture-packet.json#evolution и #AD-007 опираются на реальный механизм launchd (#EVD-027): шаг 0 отделяет baseline REQ-MUSE-001 отдельным коммитом, этапы 1–3 идут через red→green с гейтом #VER-013 перед этапом 3, а операционный откат политики на denyUnmatched выполняется через EnvironmentVariables в plist + launchctl bootout/bootstrap с обратимым учением в #VER-008.
SUB 4/4.1: PASS — модель угроз и границы доверия зафиксированы в architecture-packet.json#threat_model (#THREAT-001..#THREAT-004): флаги --disable-write --disable-shell и песочница сохранены (#EVD-005), approvedPolicyAmendment запрещён (#AD-002), журнал честно определён как аудит остаточных решений и наблюдаемых item kind без обещания полного аудита скрытых действий при allowAll, а режим отката denyUnmatched не обходится запуском exec --yolo (#AD-006, #AD-007).
SUB 4/4.2: PASS — защита секретов и данных обеспечена в architecture-packet.json#BND-001, #BND-002 и #THREAT-002: rawArgs и тела вопросов userInput никогда не логируются, свободные строки toolName и choiceId проходят allowlist-рендер с ограничением длины 64 и обрезкой списка до 8 элементов, отражённые промпты вычищаются, что проверяется канареечными тестами T-A10 и T-A15 в #VER-001.
SUB 4/4.3: PASS — эксплуатационные риски наложения повторов (#RISK-002), нестабильности внешнего прокси 127.0.0.1:10816 (#EVD-012, [F-46]), автообновления CLI 1.4.7→1.4.8 (#RISK-005, #AD-006, [F-36]) и снижения доступности при denyUnmatched (#RISK-010) явно оценены и закрыты верифицируемыми мерами (#QA-008, #QA-009, #VER-002, #VER-008).
SUB 5/5.1: PASS — каждое новое решение (architecture-packet.json#AD-001, #AD-002, #AD-003, #AD-004, #AD-006, #AD-007) содержит от 4 до 8 содержательных альтернатив с явными причинами отказа и привязкой к фактам [F-NN] и результатам спайков.
SUB 5/5.2: PASS — поведение при росте нагрузки и деградации апстрима проанализировано в architecture-packet.json#QA-004, #QA-006, #QA-009 и #THREAT-003: удержание одного из MAX_CONCURRENT=2 слотов на весь запрос не позволяет ретраям умножать параллельные процессы, очередь ограничена порогом MIN_ATTEMPT_REMAINING_S=120 с до E, а зависший клиент сбрасывается за LIVE_WRITE_TIMEOUT_S=3 с.
SUB 6/6.1: PASS — внешний OpenAI-контракт (/v1/chat/completions, /health, /v1/models) заморожен в соответствии с task.json и architecture-packet.json#AD-005; единственная дельта #CD-001 остаётся внутри существующего поля delta.reasoning_content и при расхождении snapshot сохраняет авторитетный текст F целиком после разделителя без молчаливой потери (#AD-004, T-L07).
SUB 6/6.2: PASS — пакет соблюдает правила репозитория и Python-overlay skills/architecture.md: не навязывает шаблон Litestar/FastAPI поверх stdlib-сервера, задаёт явные таймауты на каждую I/O-фазу и cleanup, фиксирует ADR 0003 в формате ADR-full с совпадением sha256 в architecture-packet.json#materialization и защищает внескоупные файлы в #protected_paths (#VER-012).
SUB 6/6.3: PASS — поверхность верификации architecture-packet.json#VER-001..#VER-013 полна и самодостаточна: включает точные команды pytest/ruff/basedpyright/git diff, негативные и граничные тесты red→green (T-A01..T-A15, T-R01..T-R10, T-L01..T-L08c), спайк #VER-013, изолированный стенд с заглушкой #VER-010 и бинарный gate сдачи тяжёлым путём в живом DSH-слоте владельца #VER-009.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Все три блокирующих замечания прошлого прохода (RW-001, RW-002, RW-003) и все десять follow-up пунктов устранены без внутренних противоречий. В AD-003 ненадёжный наблюдаемый барьер заменён позитивной защёлкой ACTION_POSSIBLE (до записи первого байта turn/start в serve и при старте процесса в exec, EVD-029), в AD-004 единый 3-секундный бюджет _sse_write охватывает и ожидание _wlock, и запись в сокет для всех писателей (EVD-030), в AD-006/AD-007 исключён обход политики denyUnmatched через exec --yolo, а в AD-002/AD-003 введён резерв FINISH_RESERVE_S=35 с и отсчёт grace 15 с по time.monotonic() от момента защёлкивания деградации. Все факты [F-01]..[F-52] и статус допущений ASM-001..ASM-012 переданы точно.
2. ПОЛНОТА: VERDICT=PASS
   WHY=Пакет покрывает REQ-MUSE-002, REQ-MUSE-003 и REQ-MUSE-004 при сохранении инвариантов REQ-MUSE-001 (AD-005). Осознанный компромисс по REQ-MUSE-003 (в безопасной области по умолчанию pre-action повторяются только пре-турновые сбои serve, тогда как mid-turn net-timeout 20–452 с остаётся терминальным до закрытия ASM-010 и решения Q-010) явно оформлен в RISK-009, VER-009 и VER-010. Для закрытия открытых вопросов предусмотрены исполнимые механизмы: спайк тайминга первой дельты VER-013 до реализации этапа 3 (OPEN-04) и безопасное логирование инструментальных item kind с полями timeToFirstTokenMs/usage (ASM-010, OPEN-01).
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Архитектура опирается на существующую структуру bridges/muse-bridge/server.py и тестовую обёртку install_protocol_wrapper в tests/test_muse_bridge_killpg.py без введения сторонних библиотек. План выката разделён на отделение baseline-коммита REQ-MUSE-001 (шаг 0) и три изолированных этапа red→green, а процедура операционного переключения MUSE_BRIDGE_APPROVAL_MODE учитывает заморозку EnvironmentVariables в launchd и использует проверенную последовательность правки plist с launchctl bootout/bootstrap и учением VER-008.
4. РИСКИ: VERDICT=PASS
   WHY=Модель угроз (THREAT-001..THREAT-004) и реестр рисков (RISK-001..RISK-011) закрывают безопасность, логирование и эксплуатацию: запрет --disable-sandbox и сохранение --disable-write --disable-shell, отказ от выбора approvedPolicyAmendment, санитизация toolName и choiceId по allowlist до 64 символов без логирования rawArgs и вопросов userInput, защита от зависания слотов при заблокированном stdin serve (CONTROL_WRITE_TIMEOUT_S=5 с и принудительный killpg по grace 15 с) и честная фиксация границ применимости аудита и отката политики.
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового решения AD-001..AD-004, AD-006, AD-007 приведено от 4 до 8 альтернатив с предметным обоснованием выбора. Сравнение с альтернативными архитектурами подтверждает адекватность пакета: (1) асинхронный single-writer SSE с ограниченной очередью кадров на запрос вместо синхронного _sse_write с 3-секундным бюджетом захвата _wlock и записи (AD-004) развязал бы чтение stdout serve и сокет клиента, но для грубых summary.N-дельт неоправданно усложняет финализацию _send_sse и политику переполнения ради того же 3-секундного предела; (2) пул долгоживущих pre-warmed процессов muse serve (по аналогии с ADR 0001 droid-моста) вместо процесса на запрос (AD-003, AD-006) убрал бы накладные расходы spawn/handshake на каждый запрос, но потребовал бы сложной очистки состояния сессии и песочницы после зависших approval и отменённых ходов; (3) барьер повтора по наблюдаемым событиям observed-items по умолчанию вместо строгого pre-action ACTION_POSSIBLE (AD-003) позволил бы автоматически переигрывать mid-turn net-timeout, но нарушил бы запрет на дублирование ненаблюдаемых неидемпотентных действий модели при allowAll (ASM-010, THREAT-004). При росте нагрузки первым ломается пропускная способность из-за потолка MAX_CONCURRENT=2 (EVD-013, [F-21]) и модели «процесс serve на запрос»: два длинных хода мышления Wonder (205–412 с, [F-42], [F-43]) полностью занимают оба слота, а запросы в очереди после отправки стартовых SSE-заголовков ждут освобождения слота и при снижении остатка бюджета до E ниже MIN_ATTEMPT_REMAINING_S=120 с отсекаются ошибкой 503/SSE error (AD-003, QA-004); вторым узким местом становится внешний форвардер прокси 127.0.0.1:10816 ([F-46]), деградация которого вызывает mid-turn net-timeout, не подлежащие повтору в режиме pre-action (RISK-009).
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт моста сохранён, единственная контрактная дельта CD-001 аддитивна внутри поля delta.reasoning_content и при расхождении финального snapshot F с отправленным префиксом P доставляет F целиком после разделителя без потери текста (AD-004). Требования Python-overlay (таймауты на все I/O и cleanup, идемпотентность повторов, защита protected_paths через VER-012, ADR-full с точным sha256 материализации и обязательный тяжёлый путь VER-009 в живом слоте владельца) выполнены полностью.
ОБЩИЙ ВЕРДИКТ: PASS

COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 0
VERDICT: PASS
ARTIFACT_END>>>

Эксперт Визионер:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r18/seats/3/verdict.md#L3-L72 sha256=17bf0da9f1bfab7d1b688d806b16313b8354302b50526c37b11147caff514665

Общий канон `~/Мой диск/Context/AGENTS.md` прочитан целиком из сообщения до `<!-- КАНОН-КОНЕЦ -->`. Python-overlay прочитан; проектные файлы правил отдельно не читались, по приложенной спецификации они отсутствуют.

### F-001 — Пре-турновый approval не включён в общий барьер повтора

- **Якоря:** architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#BND-002, architecture-packet.json#BND-003, architecture-packet.json#ASM-010, architecture-packet.json#THREAT-004, architecture-packet.json#VER-002.
- **Правило:** RW-001 требует запрещать повтор после возможного исполнения действия, а не только после начала генерации хода.
- **Evidence:** AD-003 защёлкивает `ACTION_POSSIBLE` для serve «ДО записи первого байта turn/start». Его предикат для `pre-action` проверяет отсутствие этой защёлки и approval-деградации, но не отсутствие approval-трафика или отправленного разрешения. При этом приложенная спецификация прямо предусматривает approval во время setup через тот же обработчик с отправкой `decide`. BND-002 отдельно запрещает exec-fallback «после approval-трафика», однако это ограничение не перенесено в общий предикат запуска процессов.
- **Дефект:** разрешённый во время setup запрос ещё не устанавливает описанный `ACTION_POSSIBLE`. Следующий пре-турновый транзиентный сбой по AD-003 допускает новый serve. Отсутствие действия здесь не доказано; запрет exec в BND-002 проблему повторного serve не закрывает. Это архитектурная неоднозначность, а не утверждение, что такой payload уже наблюдался.
- **Ожидаемое исправление:** включить пре-турновый approval/decide в необратимый барьер допуска любого нового процесса либо запретить разрешающие команды до `turn/start`. Согласовать AD-002, AD-003, BND-002, BND-003 и THREAT-004.
- **Критерий проверки:** расширить VER-002 сценарием: approval во время setup → разрешающий `decide` → побочный эффект заглушки → транзиентный сбой до `turn/start`. Второй serve и exec отсутствуют, эффект один, терминальный исход один. Команда: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval or TransientRetry'`.
- **priority:** blocking.
- **Связь с rework:** RW-001 закрыт для сценариев после `turn/start` и запуска exec, но общий инвариант закрыт лишь частично.

### F-002 [sweep] — Предел отдельного SSE-кадра не ограничивает всю финальную выдачу

- **Якоря:** architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#BND-003, architecture-packet.json#BND-004, architecture-packet.json#QA-004, architecture-packet.json#VER-002, architecture-packet.json#VER-003, architecture-packet.json#ASM-012.
- **Правило:** заявленный end-to-end бюджет должен включать конечную выдачу ответа и иметь измеримый оракул; клиентский предел составляет 1900 с [F-19].
- **Evidence:** AD-003 называет D «потолком всей работы запроса», но успешную выдачу помещает в запас между D и клиентскими 1900 с. AD-004 ограничивает только «ОДИН вызов _sse_write». Резерв ASM-012 рассчитан на два терминальных кадра, тогда как успешный content выдаётся множеством кадров [F-17]. Общий дедлайн всей успешной выдачи не определён.
- **Дефект:** конечный предел каждого кадра не ограничивает сумму ожиданий, записей и межкадровых пауз. Клиент может принимать каждый кадр быстрее 3 с, но весь ответ закончится после клиентского таймаута. Текущие T-L08 проверяют переставшего читать клиента, а T-R10 — зависшую модель, не эту ветку.
- **Ожидаемое исправление:** однозначно определить, ограничивает D вычисление или весь запрос. Задать абсолютный дедлайн финальной выдачи не позже клиентского предела с запасом; ограничить им каждый следующий кадр и паузу, определить исход при исчерпании. Либо доказать достаточность бюджета ограничением размера ответа и общей длительности выдачи.
- **Критерий проверки:** добавить в VER-003 успешное завершение модели около E и длинную финальную выдачу клиенту, который продолжает читать, причём каждая запись укладывается в 3 с, а их сумма превышает оставшийся бюджет. Проверить конечное завершение соединения и освобождение ресурсов в установленный общий срок. Команда: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or TransientRetry'`.
- **priority:** blocking.

FIXCHECK RW-001: not-fixed — architecture-packet.json#AD-003 — T-R07 закрывает ненаблюдаемый эффект после turn/start и запуска exec, но пре-турновый разрешающий approval остаётся вне общего барьера, см. F-001.
FIXCHECK RW-002: fixed — architecture-packet.json#AD-004 — единый бюджет охватывает захват _wlock и запись всех писателей; VER-003 содержит keepalive-first сценарий T-L08b.
FIXCHECK RW-003: fixed — architecture-packet.json#AD-006 — denyUnmatched запрещает любой exec; VER-001 содержит матрицу режима и пре-турновых отказов с сохранением fallback для allowAll.

SUB 1/1.1: FAIL — architecture-packet.json#AD-003 и architecture-packet.json#BND-002 расходятся по барьеру approval во время setup, F-001.
SUB 1/1.2: FAIL — architecture-packet.json#AD-004 ограничивает кадр, но не суммарную финальную выдачу, F-002.
SUB 1/1.3: PASS — факты о причинах рестарта, режимах и протоколе согласуются с [F-01]–[F-03], [F-28]–[F-30], [F-35], [F-36].
SUB 2/2.1: PASS — architecture-packet.json#AD-001, architecture-packet.json#AD-003, architecture-packet.json#AD-004 и architecture-packet.json#AD-005 покрывают требования с явно названной ценой RISK-009.
SUB 2/2.2: FAIL — architecture-packet.json#ASM-010 не закрывает пре-турновое разрешение; ветка длительной успешной выдачи не имеет общего оракула, F-001/F-002.
SUB 3/3.1: PASS — architecture-packet.json#BND-001–BND-004 сохраняют фактические stdlib/потоковые границы без новых зависимостей.
SUB 3/3.2: PASS — architecture-packet.json#AD-007, architecture-packet.json#VER-008 и architecture-packet.json#RISK-006 задают обратимый выкат, учение переключения и сохранение baseline.
SUB 4/4.1: FAIL — architecture-packet.json#THREAT-004 не обеспечивает заявленное отсутствие повторного эффекта после setup-approval, F-001.
SUB 4/4.2: PASS — architecture-packet.json#THREAT-002 и architecture-packet.json#BND-001 ограничивают аудит; неполнота инструментального журнала названа явно.
SUB 4/4.3: FAIL — architecture-packet.json#QA-004 не подкреплён общим пределом успешной выдачи, F-002; ограничение повторов RISK-009 само по себе принято.
SUB 5/5.1: PASS — architecture-packet.json#AD-001, AD-002, AD-003, AD-004, AD-006, AD-007 имеют минимум две альтернативы и причины выбора; AD-005 наследуется.
SUB 5/5.2: PASS — architecture-packet.json#QA-009 и [F-21], [F-43] позволяют определить предел роста: два долгих хода насыщают исполнителей, далее растёт очередь, а не производительность.
SUB 6/6.1: PASS — architecture-packet.json#CD-001 использует существующее SSE-поле; профили, маршруты и флаги безопасности остаются в границах задачи.
SUB 6/6.2: PASS — architecture-packet.json#BND-001–BND-005 соответствуют фактическому стеку и принципу Python-overlay «не добавлять слой ради схемы».
SUB 6/6.3: FAIL — architecture-packet.json#VER-001–VER-013 содержат red→green, полный suite и тяжёлый путь, но не два необходимых отрицательных сценария F-001/F-002.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Основной путь согласован, но общий предикат допуска процесса пропускает setup-approval, а предел финальной выдачи не замкнут.
   СОВЕТЫ (при FAIL): закрыть барьер F-001; определить и проверить общий дедлайн выдачи F-002.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Требования, ограничения и открытые вопросы описаны; две пограничные ветки остаются без непротиворечивого поведения.
   СОВЕТЫ (при FAIL): добавить setup-approval в модель состояний; добавить длительную успешную выдачу в QA и verification surface.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Решение остаётся локальным для моста и тестов. Политика, транспорт, повторы и SSE разделены без перестройки проекта. Выкат и операционный откат конкретны.

4. РИСКИ: VERDICT=FAIL
   WHY=AllowAll разрешён владельцем, отказ от небезопасных внутриходовых повторов оправдан. Однако setup-approval оставляет обход барьера, а покадровый timeout не гарантирует соблюдение клиентского бюджета.
   СОВЕТЫ (при FAIL): применить общий необратимый барьер ко всем разрешающим действиям; ограничить всю финальную выдачу абсолютным дедлайном.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Против exec-only архитектуры выбранный подход сохраняет дорогое мышление и MSP-прогресс. Против интерактивного посредника не требует нового канала DSH. Отдельный SSE-писатель с ограниченной очередью лучше развязывает чтение и запись, но добавляет управление переполнением и финализацией, пока неоправданное при двух исполнителях. При росте нагрузки первыми ограничениями станут очередь ожидающих HTTP-запросов и общий upstream; увеличение MAX_CONCURRENT само по себе их не устраняет.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Это ценное повышение надёжности адаптера, не новая масштабируемая платформа. Границы задачи соблюдены, но пакет пока неоднозначен как основа для Coder. Проверки оценены по описанию, не запускались.
   СОВЕТЫ (при FAIL): синхронизировать решения и границы по F-001; расширить замороженные проверки сценариями F-001/F-002. Не объявлять устранёнными внутриходовые net-timeout, оставленные RISK-009.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 2
VERDICT: NEEDS WORK
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/a3/consensus-ledger.md sha256=6ca8d5cb664a30a9f9b768f5e3db2ad5139c8b54047a3473cc38db2bb7fe799e
# consensus-ledger (арх-панель, cycle 1, a3)

### F-001
- origin: Визионер · R1 · F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 Визионер):
> ### F-001 — Пре-турновый approval не включён в общий барьер повтора
>
> - **Якоря:** architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#BND-002, architecture-packet.json#BND-003, architecture-packet.json#ASM-010, architecture-packet.json#THREAT-004, architecture-packet.json#VER-002.
> - **Правило:** RW-001 требует запрещать повтор после возможного исполнения действия, а не только после начала генерации хода.
> - **Evidence:** AD-003 защёлкивает `ACTION_POSSIBLE` для serve «ДО записи первого байта turn/start». Его предикат для `pre-action` проверяет отсутствие этой защёлки и approval-деградации, но не отсутствие approval-трафика или отправленного разрешения. При этом приложенная спецификация прямо предусматривает approval во время setup через тот же обработчик с отправкой `decide`. BND-002 отдельно запрещает exec-fallback «после approval-трафика», однако это ограничение не перенесено в общий предикат запуска процессов.
> - **Дефект:** разрешённый во время setup запрос ещё не устанавливает описанный `ACTION_POSSIBLE`. Следующий пре-турновый транзиентный сбой по AD-003 допускает новый serve. Отсутствие действия здесь не доказано; запрет exec в BND-002 проблему повторного serve не закрывает. Это архитектурная неоднозначность, а не утверждение, что такой payload уже наблюдался.
> - **Ожидаемое исправление:** включить пре-турновый approval/decide в необратимый барьер допуска любого нового процесса либо запретить разрешающие команды до `turn/start`. Согласовать AD-002, AD-003, BND-002, BND-003 и THREAT-004.
> - **Критерий проверки:** расширить VER-002 сценарием: approval во время setup → разрешающий `decide` → побочный эффект заглушки → транзиентный сбой до `turn/start`. Второй serve и exec отсутствуют, эффект один, терминальный исход один. Команда: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval or TransientRetry'`.
> - **priority:** blocking.
> - **Связь с rework:** RW-001 закрыт для сценариев после `turn/start` и запуска exec, но общий инвариант закрыт лишь частично.

### F-002
- origin: Визионер · R1 · F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 Визионер):
> ### F-002 [sweep] — Предел отдельного SSE-кадра не ограничивает всю финальную выдачу
>
> - **Якоря:** architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#BND-003, architecture-packet.json#BND-004, architecture-packet.json#QA-004, architecture-packet.json#VER-002, architecture-packet.json#VER-003, architecture-packet.json#ASM-012.
> - **Правило:** заявленный end-to-end бюджет должен включать конечную выдачу ответа и иметь измеримый оракул; клиентский предел составляет 1900 с [F-19].
> - **Evidence:** AD-003 называет D «потолком всей работы запроса», но успешную выдачу помещает в запас между D и клиентскими 1900 с. AD-004 ограничивает только «ОДИН вызов _sse_write». Резерв ASM-012 рассчитан на два терминальных кадра, тогда как успешный content выдаётся множеством кадров [F-17]. Общий дедлайн всей успешной выдачи не определён.
> - **Дефект:** конечный предел каждого кадра не ограничивает сумму ожиданий, записей и межкадровых пауз. Клиент может принимать каждый кадр быстрее 3 с, но весь ответ закончится после клиентского таймаута. Текущие T-L08 проверяют переставшего читать клиента, а T-R10 — зависшую модель, не эту ветку.
> - **Ожидаемое исправление:** однозначно определить, ограничивает D вычисление или весь запрос. Задать абсолютный дедлайн финальной выдачи не позже клиентского предела с запасом; ограничить им каждый следующий кадр и паузу, определить исход при исчерпании. Либо доказать достаточность бюджета ограничением размера ответа и общей длительности выдачи.
> - **Критерий проверки:** добавить в VER-003 успешное завершение модели около E и длинную финальную выдачу клиенту, который продолжает читать, причём каждая запись укладывается в 3 с, а их сумма превышает оставшийся бюджет. Проверить конечное завершение соединения и освобождение ресурсов в установленный общий срок. Команда: `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or TransientRetry'`.
> - **priority:** blocking.
ARTIFACT_END>>>

РАУНД: D1 из ≤3; последний: нет; место: Реалист
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002; N=2

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council-consensus.md#L94-L107 sha256=449fb0f0a19694dc56727b87a61df4bd905ae12eeae40fe2f766a01b263303b2
ПРАВИЛА ДЕБАТОВ (номер раунда, признак «последний» и твоё место — в строке РАУНД выше; слот, транспорт и шляпа — по жребию этого раунда)
Всё выше — дословные копии, без комментариев оркестратора. Суди заново, чужой вердикт автоматически не подтверждай.
Цель — согласованное решение по КАЖДОЙ находке со status=OPEN, а не победа.
1. По каждой находке из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО — ровно одна позиция (по своей неоспоренной находке — только если меняешь её); позиции по находкам вне строки не засчитываются и не ошибка:
   AGREE F-NNN rev=<r> — проверил: <file:line> — что увидел сам
   DISPUTE F-NNN — класс: invalid | duplicate_of:F-MMM | out_of_scope | foreign_key — контр-evidence: <file:line или цитата правила> — почему неверно
   AMEND F-NNN — priority=<blocking|non-blocking>; locations=<file:line,…>; fix=<…> — причина: <file:line или цитата правила>
   WITHDRAW F-NNN — только своя находка — ARG или NEW (как в п.2); проверил: <file:line>
   INCONCLUSIVE F-NNN — что нужно для проверки (не голос)
2. Первая твоя позиция по находке — не смена, ARG/NEW для неё не нужен (в том числе если ты заменил выбывшего судью или получил шляпу по новому жребию раунда: прежние позиции шляпы — история в леджере). Смена своей прошлой позиции (включая AMEND/WITHDRAW своей находки) — только с `ARG: <место/раунд «дословная цитата коллеги»>` (довод коллеги) либо `NEW: <file:line>` (твоя новая проверка, которой не было в прошлых репликах) и с твоей собственной проверкой <file:line>. Смена без ARG/NEW — malformed. Повторить прежнюю позицию без нового довода можно.
3. Вопросы коллеге — не более 3 за раунд (в последнем раунде вопросов нет), адресно: `Q→<место>: F-NNN <file:line> — вопрос` (id вопросу присваивает оркестратор, ты его не пишешь). На вопросы из строки ВОПРОСЫ К ТЕБЕ: `A←Q-<id из строки> — ответ + <file:line>`; ответ без проверяемой ссылки не считается ответом.
4. Взаимоисключающие фиксы двух находок: `CONFLICT F-a↔F-b — почему`.
5. Новая находка — полный F-блок: blocking — с меткой [late-R2], non-blocking — без метки, в леджер; позиции по OPEN-находкам она не заменяет. Найденная в последнем раунде решается правилом потолка без обсуждения.
6. Ответ: строки позиций/вопросов/ответов, затем ФОРМАТ ОТВЕТА (6 критериев; при FAIL — ссылки на F-NNN; INCONCLUSIVE критерия — что нужно для проверки). SUB-строки и COVERAGE в D-раунде не нужны (правило шапки о них относится к R1); `FINDINGS_COMPLETE: <N>` — только если в ответе есть новые F-блоки (N — их число). Последние строки: `POSITIONS: <n>/<N>` (n — число твоих позиций по находкам из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО, N — их число из строки) и `ANSWERS: <a>/<A>` (A — число вопросов в строке ВОПРОСЫ К ТЕБЕ), при новых F-блоках — ещё `FINDINGS_COMPLETE`.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ architecture-packet:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json sha256=38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c
{
  "schema_version": "1.0",
  "task_id": "REQ-MUSE-002",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": ".ai-team/runs/muse-wonder-approval-20261015/plans/architect-03.json",
    "sha256": "2a305b66a592611de9f2c9103513c1989384bb595078d8e6b30d8bb4b454f3fb"
  },
  "spec_path": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md",
  "requirement_ids": [
    "REQ-MUSE-002",
    "REQ-MUSE-003",
    "REQ-MUSE-004"
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1757-1762 (ServeRun.execute._handle_event), :1945-1948 (finally close)",
      "claim": "F-01/F-02: единственная обработка approval/request и userInput/request безусловно бросает ServeUnavailable без JSON-RPC ответа; finally убивает группу serve, состояние хода теряется. Перепроверено архитектором 2026-10-15 (grep путь+символ, строки совпадают с ledger)"
    },
    {
      "id": "EVD-002",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:2400-2446 (Handler.run_attempt), :2411-2446",
      "claim": "F-03: перехват ServeUnavailable запускает muse exec с полным attempt_prompt с нуля (via=exec-after-serve-fallback); при _client_gone exec не запускается. Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-003",
      "kind": "command",
      "ref": "~/.dsh/bridges/muse-bridge/logs/bridge.log:1034-1042 и :1243-1252; grep -c 'serve needs interaction' = 29 (27 spark, 2 wonder)",
      "claim": "F-05/F-06/F-07/F-42: ходы wonder до approval 275 с (13.10, повтор 2242 с до client gone, prompt 1326216 симв.) и 412 с (14.10, повтор 455 с до net-timeout, prompt 768118 симв.); цена перезапуска на spark до 1521 с (F-41)"
    },
    {
      "id": "EVD-004",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1816-1829 (session/start)",
      "claim": "F-08/F-31: session/start передаёт только commandId, workspaceRoot, providerId=meta, modelId без approvalMode; комментарий о потолке approval_mode_ceiling на 1.4.7/1.4.8 не подтверждён, отказы -32030 в логе только на 1.4.2. Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-005",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1648-1659 (serve argv), :1380-1401 (exec argv)",
      "claim": "F-09: serve запускается с --disable-write --disable-shell --trust-workspace --no-session-log; exec дополнительно --yolo --disable-web-tools --disable-reminders; --disable-sandbox нигде не передаётся"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "MSP schema 1.4.7/1.4.8 $defs.RequestReceipt, ApprovalDecideParams/Result (Explorer D D-02/D-03/D-08/D-09); evidence-ledger F-23/F-28",
      "claim": "F-23/F-28: серверных запросов ровно два (approval/request, userInput/request), результат RequestReceipt только подтверждает показ; решение идёт approval/decide с choiceId из availableChoices, commandId UUIDv7, requirementId равным currentRequirementId, sessionId; terminal=false означает обновлённый approval/request; отклонить без решения по проводу нельзя"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "MSP schema $defs.ApprovalMode, SessionStartParams.approvalMode, SessionSetApprovalModeParams (Explorer D D-12/D-13/D-14); F-29/F-32",
      "claim": "F-29/F-32: ApprovalMode закрытый enum allowAll/promptUnmatched/onRequest/denyUnmatched; без поля и при null серверный default; session/start единственная поверхность политики неинтерактивного запуска; setApprovalMode действует со следующего действия и не решает pending approval"
    },
    {
      "id": "EVD-008",
      "kind": "command",
      "ref": "python3 -I /tmp/cel-runs/muse-wonder-serve-approval/explorer-D/poc_session_start.py (probe-*.json, без turn/start)",
      "claim": "F-30: на serve 1.4.7 и 1.4.8 при флагах моста все четыре явных approvalMode приняты и возвращены как эффективные; без поля эффективный режим promptUnmatched (source startup); setApprovalMode принял все четыре режима подряд (F-32)"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "/tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md (2026-10-15 05:44 MSK)",
      "claim": "OPEN-07 закрыт владельцем: политика approval неинтерактивного моста Авторазрешение (allowAll); риск принят владельцем при сохранённых --disable-write --disable-shell и включённой песочнице"
    },
    {
      "id": "EVD-010",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:114 (NETWORK_RETRY_MARKER), :2435-2445",
      "claim": "F-12/F-45: сетевой повтор exec срабатывает один раз только по подстроке network connection could not be opened и только внутри exec-after-serve-fallback; net-timeout мостом не ретраится, текст ошибки в коде моста не определяется. Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-011",
      "kind": "command",
      "ref": "/tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv:2-6; bridge.log (F-13/F-43)",
      "claim": "F-14/F-44/F-43: бенч wonder exec max 100 KB 51.1 с ok, 400 KB 251.2 с ok, 800 KB 281.3 с ok, 1200 KB 236.1 с fail (after 5 provider attempts), 800 KB high 31.5 с fail net-timeout; в логе net-timeout за 20 с на effort low и max и за 452 с (after 2 provider attempts); serve-ходы wonder без approval 8-94 с (24 хода) и 205-237 с на длинных"
    },
    {
      "id": "EVD-012",
      "kind": "command",
      "ref": "grep -c по ~/Library/Logs/Factory/proxyrack-forward.log (151006 строк): retry timed out 26789, для api.meta.ai:443 3893 (F-46)",
      "claim": "F-46: внешний слой Meta через форвардер 127.0.0.1:10816 на ProxyRack нестабилен; источник net-timeout вне моста, сопоставления времён с ходами нет (OPEN-08)"
    },
    {
      "id": "EVD-013",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:65-66, :138, :1696-1697, :1455-1460, :2375-2384",
      "claim": "F-15/F-21: TIMEOUT_S=1800 отдельно на serve-ход и на каждый exec Run (при fallback таймер заново), SERVE_SPAWN_TIMEOUT_S=30 на handshake, idle-таймаута чтения serve нет, MAX_CONCURRENT=2 с ожиданием слота до 1800 с далее 503. Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-014",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1185, :2034-2070, :1781-1796, :2151-2198",
      "claim": "F-16/F-17: SSE 200 и role-кадр уходят до хода, каждые KEEPALIVE_S=15 с идёт data-чанк с пустым content (не SSE-комментарий); summary.N копятся в памяти и уходят одним reasoning_content после хода, content кусками около 300 символов. Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-015",
      "kind": "code",
      "ref": "server.py:130,134-137 (droid-мост :9882, LIVE_WRITE_TIMEOUT_S=3, коалесценция около 40 мс, : keepalive)",
      "claim": "F-18: соседний droid-мост того же DSH отдаёт content и reasoning_content live-дельтами и SSE-комментарием : keepalive каждые 15 с. Потребление live reasoning_content клиентом DSH фактом ledger не подтверждено: ledger описывает только отправку со стороны droid-моста, потребление клиентом — допущение ASM-003 (ASSUMED)"
    },
    {
      "id": "EVD-016",
      "kind": "code",
      "ref": "~/.dsh/profiles/web/cordis.patch.yml:426-437, desktop:327-338",
      "claim": "F-19: клиент DSH для muse-bridge api=openai-completions, timeoutMs=1900000, streamIdleTimeoutMs=1900000, maxRetries=0, supportsReasoningEffort=true; документации idle-watchdog нет (OPEN-03)"
    },
    {
      "id": "EVD-017",
      "kind": "code",
      "ref": "tests/test_muse_bridge_killpg.py:979-1021 (install_protocol_wrapper), :1181-1185, :1278-1305, :2068, :2582",
      "claim": "F-20/F-52: тесты закрепляют старое поведение (test_approval_falls_back_to_exec_without_decide требует отсутствия approval/decide; test_s1 требует отсутствия : keepalive); фикстура approval шлёт params пустым объектом; baseline файла 67 passed (task envelope). Перепроверено 2026-10-15"
    },
    {
      "id": "EVD-018",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:87-88, :766, :1966, :2172, :2452-2528; .ai-team/runs/muse-wonder-foreign-session-20261014/architecture-packet.json AD-001..AD-004",
      "claim": "F-49: REQ-MUSE-001 в рабочем дереве (лимит 400000, цель 320000, retry 200000, ровно один контекстный retry только до первого контентного кадра _content_started, отдельный счётчик от сетевого retry); гарантии прошлого пакета наследуются без пересмотра"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "MSP schema 1.4.7 fp sha256:6de32db08bbb и 1.4.8 (F-22/F-25/F-36); muse-cli.sh --version = 1.4.8-R6256.1 (проверено 2026-10-15)",
      "claim": "F-36: лаунчер автообновился 1.4.7 -> 1.4.8 2026-10-15 05:29 MSK; методы/requests/approval-определения совпадают (69 методов); 1.4.8 добавляет уведомление turn/modelRetryScheduled (attempt, maxAttempts, retryDelayMs, errorKind); мост логирует serverInfo.version и schema fingerprint при каждом serve init (server.py:1810-1812)"
    },
    {
      "id": "EVD-020",
      "kind": "command",
      "ref": "cmp bridges/muse-bridge/server.py ~/.dsh/bridges/muse-bridge/server.py = IDENT; ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist; launchctl list (com.user.dsh-muse-bridge); git status ветка dev, M server.py и тесты +2941 строк (F-51)",
      "claim": "F-21/F-51: деплой-копия побайтово равна репозиторной, процесс под launchd com.user.dsh-muse-bridge (start.sh exec python3 server.py, ключ из env или ~/.dsh/.env); рабочее дерево dev несёт незакоммиченные REQ-MUSE-001 правки, откат опирается на бэкап"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "MSP schema $defs.ApprovalRequestParams/ApprovalSubject/ApprovalChoice (Explorer D D-06/D-07/D-35/D-38); F-26/F-27/F-37",
      "claim": "F-37/OPEN-01: живой payload approval/request не получен (toolName, subject, choiceId неизвестны); схема требует toolName, subject.kind из shell/fileAccess/network/unixSocket/process/tool, protectedWrite, judgeEscalated, rawArgs, availableChoices с choiceId свободной строкой и decision из открытого enum; каталога инструментов без хода нет"
    },
    {
      "id": "EVD-022",
      "kind": "url",
      "ref": "https://github.com/meta-models/muse-code-sdk/issues/80",
      "claim": "F-11: в muse serve встроенный LLM approval judge отключён (outcome=disabled), в exec включён по умолчанию и в мосте подавлен --yolo; serve --help фиксирует, что песочница конструируется хостом и по проводу не торгуется, approval mode выбирается только на проводе (F-10)"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": ".ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/findings-ledger.md, verdict-a1.md, handoff/panel-rework-brief-arch-a1.json",
      "claim": "Арх-панель cycle-1 a1: NEEDS WORK; blocking PF-a1-001, PF-a1-005, PF-a1-007, PF-a1-011 CONSENTED и PF-a1-002, PF-a1-003, PF-a1-004, PF-a1-006 OWNER_DECIDED blocking (owner-decisions.md 2026-10-15 13:39 MSK); non-blocking PF-a1-008..PF-a1-010, PF-a1-013..PF-a1-021; PF-a1-012 excluded duplicate_of PF-a1-005; саммаризатор свернул их в RW-001..RW-008 и FU-001..FU-012"
    },
    {
      "id": "EVD-024",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1992 (Handler._sse_write под _wlock, wfile.write+flush), :1953 (Handler.timeout=300); server.py (droid-мост):134 LIVE_WRITE_TIMEOUT_S=3, :5124 settimeout на live-записи",
      "claim": "Перепроверено 2026-10-15: запись SSE в muse-мосте ограничена только общим timeout соединения 300 с, отдельного предела живой записи нет; соседний droid-мост того же клиента ограничивает live-запись 3 с через settimeout сокета на время записи (PF-a1-004, F-18)"
    },
    {
      "id": "EVD-025",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:ServeRun.execute._handle_event (kinds по item/started|completed, summary_parts по индексам), :2375-2384 (цикл ожидания слота), Handler.do_POST (_sse_begin до acquire слота)",
      "claim": "Перепроверено 2026-10-15: ServeRun уже различает kind элементов item/started и item/completed (reasoning, agentMessage и прочие) и копит summary_parts по индексам, поэтому признак инструментальной активности наблюдаем в существующем цикле чтения; ожидание слота идёт после отправки SSE-заголовков и ограничено только TIMEOUT_S без учёта последующего выполнения (PF-a1-002)"
    },
    {
      "id": "EVD-026",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1242-1272 (_terminate_run: proc.wait 5.0 дважды, _wait_group_exit 2.0), :1606-1636 (ServeRun._send: дедлайн записи через time.time()), :1856 (цикл хода на time.time())",
      "claim": "Перепроверено 2026-10-15: худший случай уборки группы равен 5+5+2=12 с; дедлайны записи в stdin и чтения хода считаются на wall clock time.time(), а не на монотонных часах; отдельного предела записи управляющей команды нет"
    },
    {
      "id": "EVD-027",
      "kind": "url",
      "ref": "https://dev.to/bokuwalily/editing-the-plist-changed-nothing-launchd-kept-running-my-old-30s-timeout-until-31-lines-of-bash-10d9 ; https://thrysoee.dk/launchctl/",
      "claim": "Проверено веб-поиском 2026-10-15: launchd читает plist при bootstrap и замораживает EnvironmentVariables в определении задачи; launchctl kickstart -k перезапускает процесс, но plist не перечитывает; применение правки plist требует bootout и затем bootstrap (после bootout возможна гонка: bootstrap может вернуть ошибку 5, нужен повтор; не вызывать из процесса самой службы). На этой машине последовательность ещё не прогонялась (ASM-012)"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "evidence-ledger [F-35]: $defs.TurnCompletedParams (durationMs, timeToFirstTokenMs, usage, error — необязательные), ItemKind (reasoning, toolCall, webSearch, subagent, workflow, hookRun)",
      "claim": "turn/completed может нести timeToFirstTokenMs и usage; значение их отсутствия (ни одного токена модели в ходе) схемой не определено и не проверялось на живом сбое — кандидат позитивного сигнала отсутствия действия, но не доказательство; журнал ServeRun в a3 собирает его наличие на каждом транзиентном терминале для закрытия ASM-010"
    },
    {
      "id": "EVD-029",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1838-1849 (turn/start через _send, статус accepted проверяется после записи), :2400-2446 (run_attempt — единственное место, создающее Run/exec; три вхождения Run( в файле)",
      "claim": "Перепроверено 2026-10-15: между записью turn/start в stdin serve и разбором ack модель уже может начать ход (ack может потеряться при обрыве), поэтому граница возможного действия — запись, а не принятый ack; exec запускается только из run_attempt (fallback и повтор), прямого exec-пути без serve в мосте нет"
    },
    {
      "id": "EVD-030",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1992-2018 (_sse_write: with self._wlock без предела ожидания), :2064-2070 (_keepalive_loop), :1985, :2039, :2075, :2171 (прочие входы в _wlock), :1953 (Handler.timeout=300)",
      "claim": "Перепроверено 2026-10-15: все писатели SSE (role-кадр, keepalive, live-sink, терминальная выдача, [DONE]) идут через _sse_write с неограниченным по времени захватом _wlock; предел записи — только общий timeout соединения 300 с, действующий после захвата; прочие входы в _wlock (смена фазы, _content_started) — короткие секции без I/O"
    }
  ],
  "risk_triggers": [
    "security",
    "trust-boundary"
  ],
  "assumptions": [
    {
      "id": "ASM-001",
      "statement": "OPEN-01: запросить approval может любой не отключённый флагами serve инструмент; мост логирует только безопасные поля params (toolName, subject.kind, protectedWrite, judgeEscalated, список choiceId и decision) без rawArgs и тел вопросов userInput",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-002",
      "statement": "OPEN-02: net-timeout не зависит от размера промпта и effort в пределах бенча из пяти точек; повтор проектируется без привязки к размеру",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-003",
      "statement": "OPEN-03: клиент DSH опирается на streamIdleTimeoutMs=1900000 и уже потребляет live reasoning_content от droid-моста; пустые data-чанки keepalive сохраняются без перехода на SSE-комментарии",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-004",
      "statement": "OPEN-04: item/delta с field summary.N могут приходить по ходу хода; мост логирует время первой summary-дельты от старта хода. Диагностический факт (VER-011) приёмку REQ-MUSE-004 не заменяет: при дельтах только в конце хода требование остаётся NOT_MET (RW-007)",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-005",
      "statement": "OPEN-05: повторы провайдера внутри CLI независимы от повторов моста; повтор моста ограничен малым числом попыток и общим дедлайном, turn/modelRetryScheduled только логируется",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-006",
      "statement": "OPEN-06: влияние turn/cancel и denied на pending approval и продолжение модели схемой не описано, поэтому мост фиксирует локальный неуспешный исход в момент входа в approval-деградацию (терминальное защёлкивание AD-002), ждёт turn/completed не дольше grace 15 с и убивает группу serve; поведение сервера после denied локальный исход не меняет",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-007",
      "statement": "OPEN-08: net-timeout внешний транзиентный фактор (ProxyRack, форвардер :10816 или сторона Meta); мост повтор ограничивает и логирует, источник не чинит",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-008",
      "statement": "OPEN-09: схемы CLI 1.4.7 и 1.4.8 эквивалентны по approval и протоколу хода; serverInfo.version и fingerprint схемы проверяются логом при каждом старте serve, неизвестная версия ход не блокирует",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-009",
      "statement": "OPEN-07: политика approval неинтерактивного моста авторазрешение allowAll на session/start по решению владельца 2026-10-15 05:44 MSK при сохранённых --disable-write --disable-shell и включённой песочнице",
      "status": "VALIDATED",
      "class": "blocker",
      "evidence_ids": [
        "EVD-009",
        "EVD-008"
      ]
    },
    {
      "id": "ASM-010",
      "statement": "Полнота и порядок инструментальных событий MSP не доказаны (RW-003 a2, PF-a2-001): действие модели без предшествующего item/started|completed (kind вне reasoning/agentMessage), approval/request|requested и userInput/request фактами не исключено (каталог и payload неизвестны, EVD-021; summaries могут приходить только в конце хода, OPEN-04). Поэтому наблюдаемый барьер НЕ используется как доказательство отсутствия действия: допуск повтора и fallback в области по умолчанию pre-action строится на ACTION_POSSIBLE (запись turn/start для serve, старт процесса для exec, EVD-029), а наблюдаемый барьер a2 остаётся только в опциональной области observed-items (AD-003) и для контекстного повтора AD-005 (явный отказ провайдера по размеру контекста; остаток риска унаследован от baseline REQ-MUSE-001). План закрытия для расширения области: (1) журнал ServeRun по каждому item kind вне {reasoning, agentMessage} и поля timeToFirstTokenMs/usage транзиентного терминала (PF-a2-006, EVD-028) копится на живых ходах; (2) подтверждение вендору/по схеме инварианта «item/started предшествует исполнению инструмента» либо семантики отсутствия timeToFirstTokenMs; (3) только затем отдельное решение владельца (Q-010) и новый delta-пакет либо включение области observed-items",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-011",
      "statement": "Расхождение финального snapshot summaries F с уже отправленным live-префиксом P (F не начинается с P) на практике не ожидается: дельты summary.0 — приращения, а item/completed несёт тот же текст; при расхождении мост выбирает дублирование вместо потери (AD-004). Частота расхождений измеряется счётчиком reasoning_diverged в логе (VER-009, VER-011); ненулевая частота выносится владельцу",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    },
    {
      "id": "ASM-012",
      "statement": "Значения новых временных констант выбраны из фактов кода и бенча и не измерялись на живом ходе: CONTROL_WRITE_TIMEOUT_S=5 с (запись управляющей команды в stdin заведомо живого serve; меньше grace 15 с), MIN_ATTEMPT_REMAINING_S=120 с (выше 51.1 с и 94 с, EVD-011), FINISH_RESERVE_S=35 с (grace 15 + худшая уборка 12 + два терминальных кадра по 3 с = 33 с, EVD-026); последовательность bootout/bootstrap для смены режима на этой машине ещё не прогонялась (EVD-027) и закрывается учением VER-008; все значения — модульные константы, обратимы без изменения контрактов",
      "status": "ASSUMED",
      "class": "continuable",
      "evidence_ids": []
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "one-way",
      "question": "Какую политику approval объявляет неинтерактивный мост сессии muse serve, чтобы ход не перезапускался с нуля (REQ-MUSE-002)?",
      "choice": "approvalMode=allowAll в session/start для каждого ServeRun (все модели, включая muse-spark-*); эффективный режим из результата логируется; флаги serve и песочница без изменений, --disable-sandbox не передаётся. Решение владельца по OPEN-07 (EVD-009), детализация в proposals/docs/adr/0003-muse-serve-approval-allowall.md",
      "alternatives": [
        "denyUnmatched на session/start: ход сохраняется, несопоставленные действия отклоняются без запроса; исход хода после отказа не наблюдался (OPEN-06)",
        "оставить default promptUnmatched и отвечать approval/decide с denied: риск повторных запросов того же действия зафиксирован прошлым циклом (F-50)",
        "передача решения пользователю DSH: канала в замороженном OpenAI-контракте нет, ход ждёт человека без серверного таймера (F-39)",
        "статус-кво ServeUnavailable с exec-рестартом: измеренные потери 275-412 с мышления и до 2242 с повтора (EVD-003)"
      ],
      "drivers": [
        "REQ-MUSE-002: ни один approval/userInput не стоит полного переигрыва промпта (768118-1326216 символов в инцидентах)",
        "у моста нет интерактивного пользователя, клиент DSH без канала approval и без повторов (EVD-016)",
        "allowAll принят сервером на 1.4.7 и 1.4.8 при флагах моста (EVD-008), session/start штатная поверхность политики (EVD-007)",
        "write/shell отключены при конструировании хоста serve и по проводу не включаются (EVD-005, EVD-022)"
      ],
      "consequences": [
        "модель получает авторазрешение для инструментов, не отключённых флагами serve (subject.kind network/tool и другие по EVD-021); компенсация аудит-логом решений в AD-002 и threat model пакета",
        "поведение общее для muse-spark-* (27 из 29 исторических переходов) и muse-wonder-* без ветвления по модели",
        "смена политики в будущем локализована в поле session/start и границе ApprovalPolicy (BND-001), остальной пакет от выбора не зависит",
        "тест test_approval_falls_back_to_exec_without_decide закрепляет противоположный контракт и заменяется по AD-002, это смена контракта поведения по REQ-MUSE-002, а не ослабление"
      ],
      "approval_required": true,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; в rpc.jsonl фейкового MSP session/start содержит approvalMode=allowAll, serve argv без --disable-sandbox и с --disable-write --disable-shell, ход с approval завершается via=serve без запуска exec"
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Что мост делает внутри хода, если при allowAll сервер всё же прислал approval/request, approval/requested или userInput/request?",
      "choice": "Тот же ход продолжается: на запрос с id уходит receipt result={} тем же id, затем approval/decide с choiceId только из текущих availableChoices (decision=approved предпочтительнее approvedForSession, approvedPolicyAmendment не выбирается, requirementId дословно равен currentRequirementId, commandId через существующий _uuid7, sessionId из params); approve отправляется только при сконфигурированном режиме allowAll (AD-007). approval/requested без id ведёт к тому же decide без receipt, повтор по паре approvalId+requirementId подавляется дедупликацией, ошибка -32051 считается benign; terminal=false обрабатывается следующим обновлённым запросом; userInput/request получает receipt и userInput/cancel без передачи вопросов клиенту. Границы на ход: не более 10 approval/decide суммарно, включая финальный отказной decide, и не более 3 userInput/cancel (константы модуля); одиннадцатого decide не существует — при исчерпанном счёте деградация идёт сразу через turn/cancel. Терминальное защёлкивание отказа (единое правило): отсутствие разрешающего choice, ЛЮБАЯ ошибка approval/decide кроме benign -32051 (коды схемы [F-28]: -32050, -32052, -32053, -32054 approvalReviewerUnavailable, -32030 commandRejected) и ЛЮБАЯ ошибка userInput/cancel, превышение границы, ошибка либо превышение предела записи stdin после отправленного turn/start (receipt, decide, cancel) один раз переводят ход в локально зафиксированный неуспешный исход: при наличии выбора abort/denied и свободном счёте уходит один такой decide, иначе один turn/cancel; после защёлкивания новые разрешения и повторные входы в деградацию запрещены, дальнейшие approval/userInput запросы только логируются без команд, а любой последующий ответ сервера (повторный request, terminal=false, успешный turn/completed, молчание) локальный исход не меняет — поздний успешный текст отбрасывается, клиент получает ровно один терминальный исход. Grace APPROVAL_CANCEL_GRACE_S=15 с отсчитывается по time.monotonic() от момента локального защёлкивания (_approval_degraded=True) и ВКЛЮЧАЕТ саму попытку записи turn/cancel или отказного decide в stdin: запись ограничена остатком grace, заблокированный stdin grace не продлевает; мост ждёт turn/completed не дольше остатка grace, затем убивает группу процессов serve, отдаёт терминальную ошибку и освобождает слот; дедлайн 1800 с для освобождения слота не ожидается. Ошибка записи stdin и транспортный сбой при обработке approval после отправленного turn/start не бросают ServeUnavailable с exec-fallback: исход — та же терминальная деградация без нового процесса (единый предикат допуска AD-003/BND-003). Каждое решение логируется одной строкой безопасных полей через существующую редакцию без rawArgs; toolName и choiceId в логе рендерятся только при совпадении с [A-Za-z0-9_.:-] длиной до 64, иначе как redacted с длиной и префиксом sha256, список choiceId в логе обрезан 8 значениями (сырые значения для команды decide не меняются). Запись в stdin serve после turn/start ограничена дедлайном хода E (AD-003), а не setup-окном 30 с, при этом запись каждой управляющей команды (receipt, decide, cancel) ограничена CONTROL_WRITE_TIMEOUT_S=5 с и остатком до E (ASM-012): превышение защёлкивает деградацию, дальше действует grace с принудительным killpg",
      "alternatives": [
        "decide с denied при любом запросе: действие отклоняется, продолжение хода после отказа не наблюдалось (OPEN-06), противоречит смыслу allowAll из AD-001",
        "немедленный turn/cancel при любом запросе: ход теряется без переигрыва, REQ-MUSE-002 выполнен только формально, результат пользователю ошибка вместо ответа",
        "сохранить ServeUnavailable и exec-рестарт как fallback: возвращает измеренную потерю EVD-003 и двойной вызов модели",
        "exec как последний шаг approval-деградации до _content_started (FU-004/PF-a1-013): отклонена — после увиденного approval и попыток decide инструмент мог уже выполниться (барьер RW-003), а 27 успешных exec-переходов spark за 19-1521 с происходили при старом ServeUnavailable, где мост ничего не разрешал; потеря «терминальная ошибка вместо ответа» принята с измеримым условием пересмотра: каждая деградация логируется approval_degraded с флагами content_started и tool_activity, и первый же такой случай на тяжёлом пути или в эксплуатации ставится владельцу на пересмотр отдельным delta",
        "детерминированный deny/abort при protectedWrite=true или judgeEscalated=true внутри allowAll (FU-003/PF-a1-010): отклонена в этом delta — живой payload и семантика полей не наблюдались (EVD-021), в serve approval judge отключён (EVD-022), write отключён хостом (EVD-005), а исход хода после denied неизвестен (ASM-006) с риском цикла повторов прошлого цикла (F-50 в ledger); оба признака пишутся в аудит, селективное правило вводится отдельным решением владельца по собранным payload (Q-001)"
      ],
      "drivers": [
        "receipt не меняет состояние, решение обязано идти отдельной командой, отклонить без решения нельзя (EVD-006)",
        "choiceId свободная строка без enum и живой payload неизвестен, поэтому выбор только из availableChoices по полю decision (EVD-021)",
        "approval приходил через 275 с и 412 с после старта хода при setup-окне записи 30 с (EVD-003, EVD-013): без продления _write_until decide упал бы в ServeUnavailable",
        "MAX_CONCURRENT=2: цикл запросов внутри хода обязан иметь счётный предел помимо дедлайна 1800 с (EVD-013)",
        "предел команд и терминальный исход обязаны оставаться истинными при любом ответе сервера после denied (PF-a1-006); два хода, проигнорировавшие cancel, не должны держать оба слота MAX_CONCURRENT=2 до 1800 с (PF-a1-011)",
        "заблокированный stdin serve не должен продлевать ни grace, ни слот: отсчёт grace идёт от защёлкивания по монотонным часам, а запись управляющей команды имеет собственный конечный предел (PF-a2-003, EVD-026)"
      ],
      "consequences": [
        "ServeRun получает отправку JSON-RPC ответа по чужому id и учёт pending decide в главном цикле (голые ack чужих rid по-прежнему игнорируются, ошибка pending decide ведёт в деградацию)",
        "политика выбора изолирована чистой границей ApprovalPolicy (BND-001): смена AD-001 не трогает транспорт, ретрай и SSE",
        "userInput без пользователя завершается cancelled; если модель после этого завершает ход ошибкой, действует существующий путь model error без fallback",
        "фикстура install_protocol_wrapper расширяется реальным payload с availableChoices и ветками terminal=false и userInput; старый тест approval заменяется, тесты ServeUnavailable для прочих транспортных сбоев сохраняются",
        "терминальное защёлкивание делает поздний успешный turn/completed недостижимым для клиента: цена однозначности исхода при неизвестной семантике denied (ASM-006); счётчик деградаций approval_degraded в логе — вход условия пересмотра FU-004",
        "grace 15 с равен одному интервалу keepalive 15 с (EVD-014) и входит в резерв между исполнительным дедлайном E и потолком D запроса (AD-003); влияние cancel на pending approval внутри grace не используется как опора: очистку гарантирует убийство группы (F-33 в ledger)",
        "дедлайны записи и чтения ServeRun переводятся с time.time() на time.monotonic() (EVD-026): grace, CONTROL_WRITE_TIMEOUT_S и E не зависят от скачков wall clock"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; receipt и decide в rpc.jsonl, choiceId из availableChoices, второй запрос при terminal=false решён, userInput отменён, границы 10 (включая финальный отказной decide, одиннадцатого нет) и 3 останавливают цикл, после denied повторный request, terminal=false, успешный terminal и молчание сервера дают один локальный терминальный исход без exec (T-A13), фейковый serve без ответа на cancel теряет группу и слот не позже grace (T-A09b), ошибка записи receipt/decide после turn/start не запускает exec, канарейки rawArgs и choiceId отсутствуют в логе дословно, approval позже setup-окна решается в том же ходе; T-A08 параметризован по всем кодам [F-28] (-32050, -32052, -32053, -32054, -32030 защёлкивают, -32051 benign) и по ошибке userInput/cancel; T-A09c: stdin заблокирован до деградации — группа убита и слот свободен не позже grace от защёлкивания; T-A15: журнал инструментальных item без аргументов (канарейка)"
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как ограниченно повторять транзиентный net-timeout и родственные транспортные сбои, не нарушая бюджет контекстного retry и идемпотентность SSE (REQ-MUSE-003)?",
      "choice": "Единый транзиентный повтор на уровне цикла попыток Handler вместо внутреннего exec-only повтора, единый абсолютный дедлайн запроса и допуск нового процесса только при позитивном доказательстве отсутствия действия. (1) Бюджет: якорь — приём запроса Handler (time.monotonic()); D = TIMEOUT_S (1800 с по умолчанию) от приёма — потолок всей работы запроса; исполнительный дедлайн E = D − FINISH_RESERVE_S (35 с = grace 15 + худшая уборка группы 12 + два терминальных кадра по 3 с, EVD-026, ASM-012): очередь, попытки и паузы живут до E, grace деградации, убийство группы и терминальная выдача — в резерве между E и D; успешная выдача после завершённой попытки идёт в запас 100 с между D и клиентскими 1900 с (EVD-016). Каждая попытка получает только остаток до E; ожидание слота завершается предусмотренной ошибкой (503 до заголовков SSE либо SSE error после них), когда остаток до E меньше MIN_ATTEMPT_REMAINING_S; новый процесс (старт из очереди, повтор, fallback) при таком остатке не стартует. MIN_ATTEMPT_REMAINING_S=120 с по умолчанию (env MUSE_BRIDGE_MIN_ATTEMPT_S, читается при старте): выше самого короткого успешного хода wonder 51.1 с и serve-ходов 8-94 с (EVD-011), 30 с SERVE_SPAWN_TIMEOUT_S остаётся только окном handshake; цена — запрос в очереди получает слот не позже E−120 с. Все дедлайны и паузы считаются на time.monotonic(). (2) Граница возможного действия ACTION_POSSIBLE на попытку: serve — защёлкивается ДО записи первого байта turn/start (а не по ack: ack может потеряться, EVD-029); exec — при успешном старте процесса с промптом. Любая дальнейшая ошибка попытки (EOF, чтение, запись, дедлайн, terminal failed, транзиентный маркер) оставляет её ACTION_POSSIBLE: действие модели нельзя исключить ни отсутствием item/approval сигналов, ни пустым stdout exec, ни смертью группы (ASM-010). (3) Предикат допуска нового процесса (serve-повтор, внутренний serve→exec fallback, транзиентный повтор): клиент на месте; _content_started ложен; approval-деградация не защёлкнута; НИ ОДНА прежняя попытка запроса не имеет ACTION_POSSIBLE (область повтора pre-action, по умолчанию); прежние группы подтверждены мёртвыми; остаток до E не меньше MIN_ATTEMPT_REMAINING_S; счётчики не исчерпаны; тот же слот без повторного acquire; для exec-процесса дополнительно режим approval не denyUnmatched (AD-006, AD-007: exec всегда с --yolo). Следствие: автоматический повтор и fallback возможны только после сбоев ДО записи turn/start (spawn, handshake, session/start, до-турновый транспорт); транзиентный net-timeout посреди хода и любой сбой exec-попытки после старта процесса терминальны с ровно одним исходом клиенту; на serve пре-турновый сбой с транзиентным маркером повторяется новым serve-процессом (до 2 раз, паузы 2 с и 4 с плюс джиттер до 1 с), иначе или после исчерпания — один exec-fallback. REQ-MUSE-003 в области по умолчанию выполняется только в этой доказуемо безопасной области; цена названа в RISK-009 и Q-010. (4) Область повтора — переключатель владельца: env MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE ∈ {pre-action (по умолчанию), observed-items}, читается при старте. observed-items заменяет условие «нет ACTION_POSSIBLE» барьером наблюдаемой активности a2 (approval/request|requested, userInput/request, любой отправленный decide и любой item с kind вне {reasoning, agentMessage} на serve — EVD-025; непустой текст или summaries результата для exec) и тем самым принимает at-least-once для действий без наблюдаемых сигналов; включается только после записанного решения владельца по Q-010 и закрытия ASM-010; при старте с observed-items мост пишет warning, каждый повтор — строку retry_scope; невалидное значение останавливает старт процесса. (5) Контекстный повтор REQ-MUSE-001 (AD-005, hard threshold) сохраняет гарантию «не более одного и только до первого контентного кадра»: он гейтится условиями (3) кроме ACTION_POSSIBLE, вместо которого действует наблюдаемый барьер (4): hard threshold — явный отказ провайдера по размеру контекста, а не неопределённый таймаут; остаток риска ненаблюдаемого действия унаследован от baseline REQ-MUSE-001 и записан в ASM-010. (6) Класс транзиентной ошибки только по явным маркерам ([net-timeout], timed out waiting for response data, transport_connect_unreachable, network connection could not be opened); на serve источник — для пре-турновых сбоев текст ошибки setup, для терминала хода (используется только в области observed-items) конкатенация turn/completed.error.kind и error.message до редакции, на exec — сырой stderr; retryable сам по себе класс не даёт; состояния timeout, spawn_failed, client_gone не повторяются. Не более 2 транзиентных повторов; вызовов run_attempt не более 3 без контекстного повтора и не более 4 с ним (1 + 1 контекстный + 2 транзиентных), процессов не более 8; счётчик отдельный от контекстного retry ADR-001.3, при hard threshold приоритет у контекстного повтора. Глобальный circuit breaker не вводится: слот удерживается на весь ход, повторы не повышают параллельную нагрузку выше MAX_CONCURRENT=2 (PF-a1-019, QA-009)",
      "alternatives": [
        "только расширить список маркеров внутреннего exec-повтора: serve net-timeout по-прежнему терминальная ошибка без второй попытки, бюджет и fallback взаимодействуют неявно",
        "повтор только внутри ServeRun новым serve-процессом: exec-путь и exec-after-fallback остаются без покрытия, два механизма повтора расходятся",
        "без повтора моста с опорой на provider attempts CLI: бенч и лог показывают финальный отказ после исчерпания попыток провайдера (EVD-011), REQ-MUSE-003 не выполнен",
        "повтор после первой live reasoning-дельты с подавлением уже отправленного префикса (FU-005/PF-a1-014): отклонена — текст второй попытки генерируется заново и равенство префиксов не гарантировано, подавление по байтам может потерять или склеить разный текст, а барьер инструментальной активности повтор всё равно запрещает в части случаев; вместо неё измеряется доля ходов, где первая дельта опережает транзиентный сбой: лог первой дельты (AD-004) плюс строка retry_blocked на терминале с _content_started, доля считается по bridge.log при диагностике VER-011",
        "запрет повтора после записи turn/start без переключателя (чистый pre-action без области observed-items): проще, но любое будущее решение владельца о принятии at-least-once потребует нового delta-пакета и кода; выбран pre-action по умолчанию с переключателем, включаемым только решением владельца (Q-010)",
        "позитивный сигнал отсутствия действия по turn/completed (timeToFirstTokenMs/usage отсутствуют, EVD-028) вместо ACTION_POSSIBLE: отклонена в a3 — семантика отсутствия полей схемой не определена и на живом сбое не проверена; журнал полей включён для закрытия ASM-010, использование сигнала — только новым delta",
        "повтор по ненаблюдаемому барьеру a2 как условие по умолчанию: отклонена по PF-a2-001 (владелец: blocking) — ASM-010 признаёт, что действие без сигналов не исключено, а at-least-once владельцем не принималась (THREAT-004)",
        "отдельный лимит очереди вместо единого бюджета от приёма (подрешение a2): отклонена — два независимых лимита допускают сумму больше клиентских 1900 с, единый D с исполнительным E проще и проверяем T-R08/T-R10"
      ],
      "drivers": [
        "быстрые сбои за 20 с и 31.5 с при успешных ходах 51.1-281.3 с оставляют запас бюджета 1800 с на свежий процесс и новое соединение (EVD-011, EVD-013)",
        "CLI уже повторяет поток провайдера (attempt 3/4, 4/4, after 5 provider attempts), поэтому повтор моста мал и ограничен (EVD-011, ASM-005)",
        "клиентский предел 1900 с запрещает складывать полные 1800 с на попытку (EVD-016)",
        "повтор после первого контентного кадра ломает идемпотентность потока, инвариант EVD-018 расширяется на первую live reasoning-дельту из AD-004",
        "ожидание слота до 1800 с плюс выполнение до 1800 с превышают клиентские 1900 с, поэтому бюджет считается от приёма запроса и распространяется на fallback (PF-a1-002, EVD-013, EVD-016)",
        "отсутствие SSE-контента, пустой stdout и смерть процесса не исключают уже выполненного внешнего действия при allowAll и неизвестном каталоге инструментов (PF-a2-001, EVD-021, ASM-010): допуск повтора обязан опираться на позитивное доказательство отсутствия действия — только граница ACTION_POSSIBLE его даёт",
        "минимальный успешный ход wonder 51.1 с и serve-ходы 8-94 с (EVD-011) делают порог остатка 30 с бессмысленным для старта попытки (PF-a2-008); обязательные фазы после попытки (grace, уборка до 12 с, выдача) требуют резерва внутри D (PF-a2-003, EVD-026)"
      ],
      "consequences": [
        "ServeRun и Run получают остаток бюджета вместо полного TIMEOUT_S на повторных попытках; контекстный повтор второй попытки получает тот же остаток, что ужесточает прежний допущенный предел 2xTIMEOUT_S до исходного замысла ADR-001.3",
        "худший случай остановок ограничен суммой пауз не более 8 с внутри бюджета 1800 с; частичный текст упавших попыток по-прежнему отбрасывается, клиенту виден один терминальный исход",
        "non-stream JSON повторяется на тех же условиях, так как кадров клиенту до исхода нет",
        "контекстный повтор REQ-MUSE-001 гейтится предикатом AD-003 (барьер наблюдаемой активности вместо ACTION_POSSIBLE и остаток до E): гарантия «ровно не более одного и только до первого контентного кадра» (AD-005) сохраняется как верхняя граница, число фактических повторов может только уменьшиться",
        "очередь при насыщении завершается предусмотренной ошибкой раньше клиентского обрыва 1900 с вместо ожидания слота полные 1800 с плюс ход; поведение при поднятом оператором TIMEOUT_S выше 1900 с вне гарантии против профиля DSH EVD-016",
        "REQ-MUSE-003 в области по умолчанию закрывает только пре-турновые транзиентные сбои serve; наблюдавшиеся в логе net-timeout по длительности (до 452 с от старта хода, EVD-011) посреди хода остаются видимым пользователю терминальным отказом без повтора: честно NOT_MET для этих инцидентов до решения Q-010 (RISK-009)",
        "внутренний однократный network retry exec (NETWORK_RETRY_MARKER, baseline REQ-MUSE-001, EVD-010) упраздняется: после старта exec-процесса повтор запрещён; пре-турновый сбой serve по-прежнему уходит в один exec-fallback",
        "нулевое действие по умолчанию безопасно: второй побочный эффект невозможен там, где ACTION_POSSIBLE защёлкнут; в области observed-items остаток ненаблюдаемого действия принят владельцем явно и виден в логе",
        "ожидание слота при насыщении завершается предусмотренной ошибкой не позже E−120 с (цена порога MIN_ATTEMPT_REMAINING_S); вне гарантии остаётся оператор с TIMEOUT_S выше 1900 с"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
        "expected": "exit 0; область по умолчанию: заглушка выполняет наблюдаемый побочный эффект без item/started|completed, approval/request и без выходного текста и возвращает net-timeout ПОСЛЕ записи turn/start — ровно одна попытка, ровно один побочный эффект, один терминальный исход (T-R07); то же для exec (эффект, пустой stdout, маркер в stderr): один процесс, один эффект; пре-турновый сбой serve с маркером повторяется новым serve (до 2 раз, T-R01), EOF рукопожатия до записи turn/start уходит в один exec; summary→EOF, summary→ошибка чтения, approval→ошибка записи, cancel→EOF и turn/start без ack exec не запускают (T-R06); область observed-items (T-R07b): тот же сбой без сигналов повторяется с warning и строкой retry_scope, при инструментальном item повтор запрещён; контекстный счётчик транзиентом не расходуется (test_t18); три параллельных запроса при двух занятых слотах и остатке меньше MIN_ATTEMPT_REMAINING_S получают предусмотренную ошибку внутри E (T-R08), модель, висящая до E, даёт терминальный исход до D и свободный слот (T-R10), серия net-timeout под двумя ходами не превышает 2 процессов (T-R09)"
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Что получает SSE-клиент во время долгого мышления, кроме пустых keepalive-чанков (REQ-MUSE-004)?",
      "choice": "Live reasoning_content только на serve-пути с единым пределом записи и префикс-монотонной публикацией. ServeRun через sink Handler сообщает о приросте summary по мере накопления (дельты summary.N и списки item/completed проходят один путь накопления summary_parts/summaries, как сегодня); сокет, _wlock и фазы SSE принадлежат Handler. Единый предел записи (PF-a2-002): LIVE_WRITE_TIMEOUT_S=3 с (имя прежнее, как в droid-мосте того же клиента, EVD-015, EVD-024) — бюджет ОДНОГО вызова _sse_write, отсчитываемый по time.monotonic() от входа в вызов и охватывающий И ожидание _wlock (acquire с остатком бюджета), И запись (timeout сокета на остаток бюджета на время записи, прежнее значение восстанавливается до освобождения замка; timeout sendall в CPython — общий на вызов). Предел действует на ВСЕХ писателей — role-кадр, keepalive, live-sink, терминальная выдача и [DONE]: это правка одной точки _sse_write, а не live-sink. Прочие входы в _wlock (смена фазы, _content_started) — короткие секции без I/O и ожидают только держателя, время удержания которого ограничено тем же пределом (EVD-030). Исчерпание бюджета на любой из стадий (замок или запись) или частичная запись кадра означает зависшего клиента: live отключается, соединение считается разорванным (частично записанный кадр [DONE] не гарантирует), в _sse_write срабатывает существующий путь ухода клиента — флаг _client_gone и убийство группы serve, слот освобождается за предел 3 с плюс подтверждение смерти группы; поэтому цикл чтения MSP блокируется живой записью не дольше 3 с на кадр независимо от того, какой писатель держит замок, и дедлайн хода медленным клиентом не срывается. Флаг _content_started выставляется внутри той же критической секции _sse_write до записи первой фактически отправляемой непустой reasoning-дельты (форма — параметр или колбэк вызова, зона Coder). Публикация префикс-монотонна и порядка задним числом не меняет: до заморозки live отдаёт только прирост summary_parts[0]; заморозка наступает при первой дельте с индексом больше 0, при item/completed reasoning или в конце хода — дальше всё только копится в буфер. Финальное согласование в _send_sse: F — сегодняшняя сборка join по накопленным summaries, P — уже отправленный live-текст. Если F начинается с P, доотдаётся только хвост F[len(P):]. Если нет (расхождение, не ожидается — ASM-011), потеря авторитетного текста запрещена: после уже отправленного P клиенту отправляется разделитель \"\\n\\n\" и авторитетный текст F ЦЕЛИКОМ отдельным абзацем (допускается дублирование части текста, потеря исключена); расхождение логируется счётчиком reasoning_diverged с длинами P, F и общего префикса без текста; non-stream ответ всегда несёт авторитетную F. Повтор финального snapshot хвоста не даёт. Пустой data-keepalive каждые 15 с сохраняется без перехода на SSE-комментарии; content и tool_calls по-прежнему буферизуются до конца хода; первая фактически отправленная непустая reasoning-дельта закрывает окно повторов (буферизованная, но не отправленная дельта флага не ставит); turn/modelRetryScheduled логируется полями attempt/maxAttempts/retryDelayMs/errorKind и клиенту текстом не отдаётся; время первой summary-дельты от старта хода логируется для диагностики OPEN-04 (VER-011), приёмку VER-009 оно не заменяет; non-stream ответы без изменений. Реализация AD-004 стартует только после PASS спайка VER-013 (этап 3 rollout)",
      "alternatives": [
        "SSE-комментарий : keepalive по образцу droid-моста вместо пустых data-чанков: реакция pi-ai на комментарии не проверена (OPEN-03), тест test_s1 закрепляет обратное, выигрыш против working keepalive не показан фактами",
        "live content вместе с reasoning: частичная tool-разметка утекает клиенту до разбора _split_tool_calls по полному тексту, нужен потоковый парсер уровня droid-моста вне объёма REQ-MUSE-004",
        "статус-кво буферизации: клиент 205-237 с длинных ходов и дольше видит только пустые чанки, прогресс мышления не показан (EVD-011, EVD-014)",
        "ограниченная очередь кадров с отдельным потоком-писателем вместо ограниченного синхронного sink: отклонена — summaries грубые куски протокола, а не токены (EVD-014), отдельная очередь добавляет политику переполнения и гонку с финализацией _send_sse ради того же наблюдаемого предела 3 с",
        "повтор после первой live-дельты с подавлением отправленного reasoning-префикса (FU-005/PF-a1-014): отклонена в AD-003 — вторая попытка генерирует текст заново без гарантии общего префикса; конфликт REQ-MUSE-004 и REQ-MUSE-003 измеряется долей ходов «первая дельта раньше сбоя» по логам первой дельты и retry_blocked",
        "отдельный короткий предел только на live-sink, как в a2 (3 с после захвата _wlock): отклонена по PF-a2-002 (владелец: blocking) — keepalive и финальная выдача пишут под тем же замком с timeout 300 с, поэтому sink ждёт замок до 300 с ещё до установки своего предела; единый предел в _sse_write закрывает всех писателей одной правкой",
        "авторитетный хвост F[c:] по общему префиксу c при расхождении: отклонена — склейка P и произвольного хвоста даёт искажённый текст; потеря F[c:] при успешном ответе (a2) не принята PF-a2-004 (владелец: non-blocking, учесть); выбрано дублирование F целиком отдельным абзацем",
        "стримить только «доказанно устойчивый» префикс источника: MSP такой гарантии не даёт (ASM-011, ordering summary.N не гарантирован), поэтому устойчивость обеспечивается заморозкой по индексу 0 и финальным согласованием, а не доказательством источника"
      ],
      "drivers": [
        "droid-мост отправляет тому же клиенту live reasoning_content, поле и форма чанка моста не меняются; потребление клиентом — допущение ASM-003 (EVD-015, EVD-016)",
        "пустые data-чанки держат соединение по комментарию в коде моста против клиентского ожидания заголовков около 600 с; влияние на idle-watchdog клиента в ledger не найдено — допущение ASM-003 ([F-47], EVD-014)",
        "summary.N единственный прогресс мышления в MSP v1, сырой reasoning-текст протокол не стримит (docstring ServeRun, EVD-014)",
        "первая live-дельта сдвигает границу безопасного повтора, инвариант обязан быть явным (EVD-018)",
        "гарантии порядка summary.N в MSP нет (F-35 в ledger): последовательность 0:a, 1:b, 0:c нельзя превратить хвостом в итоговую сборку по индексам, поэтому публикация замораживается до согласования со snapshot (PF-a1-005, PF-a1-012)",
        "все писатели делят _wlock, а предел сегодня только общий timeout соединения 300 с после захвата (EVD-024, EVD-030): ограничить нужно ожидание замка И запись в точке _sse_write, иначе зависший keepalive держит замок до 300 с, а sink и слот — вместе с ним (PF-a2-002); эталон предела того же клиента — 3 с (EVD-015)",
        "порядок summary.N не гарантирован (ASM-011): авторитетный итог F обязан дойти до клиента даже при расхождении с отправленным P — дублирование приемлемее молчаливого усечения (PF-a2-004)"
      ],
      "consequences": [
        "тест test_s1 сохраняется по keepalive и дополняется порядком кадров; exec-ходы live reasoning не имеют и поведение не меняют",
        "если сервер шлёт summaries только в конце хода (OPEN-04), REQ-MUSE-004 остаётся NOT_MET и блокирует приёмку набора требований (VER-009), а факт фиксируется отдельной диагностикой VER-011; соединение при этом по-прежнему держит keepalive",
        "все записи SSE по-прежнему только через _sse_write из Handler (один вход с единым пределом ожидания замка и записи), ServeRun сокет не трогает (BND-004)",
        "при нескольких summary-индексах live после заморозки молчит до согласования: прогресс в этом случае показывает keepalive и финальный хвост, зато опубликованный порядок никогда не переписывается",
        "единственный contract delta пакета CD-001: reasoning_content приходит несколькими кадрами вместо одного, порядок reasoning раньше content сохранён; в расширяющем случае (F начинается с P) конкатенация равна прежнему единому значению; при расхождении (не ожидается) клиент получает P + разделитель + F целиком — дублирование допускается, потеря исключена, расхождение видно в логе (счётчик reasoning_diverged)",
        "предел 3 с теперь действует и на keepalive и на терминальную выдачу: клиент, не принимающий данные 3 с подряд, считается зависшим на любой стадии ответа (как в droid-мосте); медленный, но читающий клиент не затронут (RISK-011)"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
        "expected": "exit 0; reasoning-дельты приходят до финального кадра по префикс-монотонному правилу: interleaved-индексы и поздний меньший индекс не переставляют опубликованное (T-L06); расхождение: P=\"a\", F=\"b\\n\\nc\" даёт клиенту \"a\" + \"\\n\\n\" + \"b\\n\\nc\" (авторитетный текст целиком, потери нет), дубль хвоста при расширяющем F отсутствует, расхождение логируется счётчиком (T-L07); клиент, переставший читать: (а) заполняет буфер live-дельтами, (б) ПЕРВЫМ блокируется keepalive-кадр под _wlock, затем приходит summary-дельта, (в) блокируется терминальная выдача — во всех трёх случаях sink и писатели возвращаются не позже LIVE_WRITE_TIMEOUT_S, группа serve мертва и слот свободен за предел плюс подтверждение смерти (а не за 300 с), второй клиент получает полный ответ (T-L08a/b/c); пустые keepalive-чанки сохранены и : keepalive отсутствует, ровно один [DONE] в неаварийных ветках"
      }
    },
    {
      "id": "AD-005",
      "status": "INHERITED",
      "kind": "inherited",
      "question": "Какие ранее принятые гарантии этот пакет наследует без пересмотра?",
      "choice": "REQ-MUSE-001 целиком: единый лимит context_length 400000 у wonder-моделей, прунинг до 320000 с обязательным набором и атомарными tool-группами, ровно один контекстный retry до 200000 только до первого контентного кадра, редакция секретов и отражённых промптов, структурный лог context_prune; внешний OpenAI-контракт моста заморожен (/v1/chat/completions, /health, /v1/models, формы ответов и коды); окна muse-spark-* 1048576 не меняются; serve/exec флаги безопасности по EVD-005 не ослабляются",
      "alternatives": [],
      "drivers": [
        "прошлый пакет muse-wonder-foreign-session-20261014 AD-001..AD-004 уже в рабочем дереве и подтверждён логами context_prune (EVD-018)",
        "task envelope замораживает внешний контракт и запрещает переоткрывать REQ-MUSE-001"
      ],
      "consequences": [
        "новые повторы AD-003 живут в отдельных счётчиках и не меняют семантику контекстного retry, кроме общего остатка бюджета по AD-003",
        "регрессия Context-тестов блокирует сдачу наравне с новыми тестами (VER-004, VER-005)"
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-018",
        "EVD-005",
        "EVD-016"
      ],
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'ContextPrune or ContextRetry or AllowedModelsSync'",
        "expected": "exit 0; пороги 400000/320000/200000, обязательный набор, один контекстный повтор и окна моделей без изменений"
      }
    },
    {
      "id": "AD-006",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как мост переживает смену версии Muse CLI и возврат потолка approvalMode при автообновлении лаунчера?",
      "choice": "Каждый ServeRun логирует serverInfo.version, fingerprint схемы и эффективный approvalMode сессии. Отказ session/start с -32030 approval_mode_ceiling на явном режиме клиентским автоодобрением не обходится: ServeRun прерывается до записи turn/start как транспортный ServeUnavailable с warning (версия сервера и код -32030). Дальше решает единый предикат допуска AD-003: при настроенном allowAll Handler выполняет ровно один внутренний exec-fallback (второй session/start без approvalMode и внутриходового approve поверх серверного promptUnmatched не происходит); при настроенном denyUnmatched (AD-007) exec-fallback ЗАПРЕЩЁН — exec всегда запускается с --yolo и автоматически разрешает действия модели (EVD-005), то есть нарушил бы выбранную оператором политику: запрос завершается контролируемым терминальным исходом (HTTP 502 до заголовков SSE либо SSE error с одним [DONE]) с причиной exec_fallback_disabled(denyUnmatched), serve-процесс один, exec не стартует. Правило едино для всех пре-турновых сбоев serve (spawn, handshake EOF и таймаут, session/start без sessionId, -32030) и для любых других путей запуска exec: единственное место, создающее exec-процесс, — run_attempt (EVD-029), предикат допуска там же. Неизвестная версия CLI ход не блокирует и отдельно помечается в логе init; закрепление версии лаунчера вне объёма (OPEN-09)",
      "alternatives": [
        "жёсткий отказ хода на неизвестной версии: автообновление 1.4.7 -> 1.4.8 без участия моста остановило бы боевой мост (EVD-019)",
        "терминальный отказ хода при -32030 без exec: на версии с потолком каждый ход завершается ошибкой вместо существующего exec-пути, хотя сбой произошёл до turn/start и переигрывать нечего",
        "повторный session/start без approvalMode с опорой на внутриходовый decide approve (поведение пакета a1): отклонена до явного решения владельца — при серверном default promptUnmatched безусловное approve реализует allowAll на стороне клиента в обход потолка, а решение владельца AD-001 относится к полю session/start и обход ceiling не разрешает (PF-a1-009, Q-009)",
        "exec с --approval-mode never вместо --yolo при denyUnmatched: флаг присутствует в справке exec ([F-38]), но семантика never не проверена и не эквивалентна политике denyUnmatched на проводе serve (отказ без запроса) — без модельного хода и документации отклонена; пересмотр — только после отдельной пробы и решения владельца",
        "запрет fallback только при -32030, остальные пре-турновые сбои — в exec --yolo: отклонена — любой запуск exec при denyUnmatched автоматически разрешает действия, переключатель обязан сохранять политику при любой деградации транспорта (PF-a2-005)"
      ],
      "drivers": [
        "потолок существовал на 1.4.2 и отсутствует на 1.4.7/1.4.8, поведение зависит от версии (EVD-004, EVD-008)",
        "лаунчер обновляется сам и удаляет прежний бинарь, мост версию не контролирует (EVD-019)",
        "exec всегда с --yolo, а переключатель denyUnmatched обещает отсутствие автоматических разрешений: любой exec-запуск при этом режиме противоречит обещанию (PF-a2-005, EVD-005, EVD-029)"
      ],
      "consequences": [
        "фейковая фикстура получает ветку отказа -32030 на первый session/start",
        "на версии с потолком поведение честно деградирует к существующему exec-пути (exec уже работает с --yolo вне MSP-потолка) ценой потери serve-хода только на таких версиях; на 1.4.7/1.4.8 потолок не воспроизводится (EVD-004, EVD-008), поэтому боевой путь не меняется",
        "политика AD-001 на ходе с -32030 помечается в логе неприменённой по потолку сервера, а не эмулируется клиентом",
        "при denyUnmatched недоступность serve на пре-турновой фазе ведёт к терминальной ошибке вместо exec — осознанная потеря доступности ради сохранения политики (RISK-010)",
        "при allowAll согласованная ветка пре-турнового exec-fallback сохраняется без изменений (в тесте матрицы T-A14/T-A11b)"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; allowAll: при -32030 на session/start второго session/start и approval/decide в rpc.jsonl нет, warning с версией в логе, ровно один exec-fallback до записи turn/start доводит ход, serve-процесс один (T-A11); denyUnmatched × {-32030, EOF handshake, таймаут handshake, session/start без sessionId, spawn failed}: exec-argv отсутствует (--yolo не вызывается), serve не более одного процесса, один терминальный исход 502 или SSE error с причиной exec_fallback_disabled и один [DONE] (T-A11b); allowAll × тот же набор пре-турновых сбоев — ровно один exec (T-A14)"
      }
    },
    {
      "id": "AD-007",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как оператору сменить режим approval боевого моста без правки кода при откате политики или после аудита первых живых payload, и что именно обещает режим denyUnmatched?",
      "choice": "Env-переключатель MUSE_BRIDGE_APPROVAL_MODE читается при старте процесса в ряд существующих env-констант (TIMEOUT_S, MAX_CONCURRENT, KEEPALIVE_S): допустимы только allowAll и denyUnmatched, значение по умолчанию allowAll по AD-001; выбранное значение уходит в session/start и одновременно гейтит approve в ApprovalPolicy (при denyUnmatched остаточный запрос уходит в отказную деградацию AD-002, approve не отправляется никогда); невалидное значение останавливает старт процесса с ошибкой в логе. Область действия denyUnmatched (PF-a2-005): мост нигде не разрешает действия модели автоматически — serve получает denyUnmatched, approve не отправляется И ни один exec-процесс (он всегда с --yolo, EVD-005) не запускается ни в какой роли: ни fallback, ни повтор (AD-006, AD-003); цена — при недоступном serve на пре-турновой фазе запрос завершается терминальной ошибкой (RISK-010). Применение режима на боевой машине (PF-a2-007): правка блока EnvironmentVariables в ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist, затем bootout и bootstrap задачи (launchctl bootout gui/$(id -u)/com.user.dsh-muse-bridge; launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist) из внешней оболочки, не из процесса моста; одного launchctl kickstart -k недостаточно — он plist не перечитывает (EVD-027); после bootout дождаться исчезновения метки, при ошибке 5 повторить bootstrap. Проверка: serve init в bridge.log несёт эффективный approvalMode; обратный переход — тем же путём (учение VER-008). Деплой новой копии server.py по-прежнему kickstart -k (plist не меняется)",
      "alternatives": [
        "смена режима только правкой кода и redeploy с явной фиксацией в ADR (deferred пакета a1): откат one-way решения безопасности дорог и медленен именно в инциденте",
        "переключение HTTP-ручкой моста в рантайме: новая внешняя поверхность управления в замороженном контракте и лишняя trust boundary ради редкой операции",
        "чтение режима из ~/.dsh/.env при старте вместо plist: позволило бы обойтись kickstart -k, но неизвестно, подгружает ли start.sh что-либо, кроме ключа (EVD-020); отклонена до проверки start.sh, остаётся кандидатом отдельного delta",
        "denyUnmatched только для serve с сохранением exec --yolo как fallback (a2): отклонена по PF-a2-005 (владелец: blocking) — «откат политики», который при сбое serve снова включает автоматическое исполнение, не является откатом"
      ],
      "drivers": [
        "allowAll — one-way решение безопасности владельца (AD-001), цена его отката должна быть операцией, а не релизом (PF-a1-020)",
        "мост уже читает TIMEOUT_S, MAX_CONCURRENT и KEEPALIVE_S из окружения при старте (EVD-013, server.py:65-66,1185), новый переключатель не вводит второй механизм конфигурации",
        "заявленный быстрый откат должен быть проверен на реальном канале launchd, а не только чтением env внутри процесса (PF-a2-007, EVD-027)"
      ],
      "consequences": [
        "значение по умолчанию и смысл AD-001 не меняются: без env мост объявляет allowAll; операторский denyUnmatched виден в логе эффективного режима каждого хода (AD-006)",
        "deferred пакета про env-переопределение сужается до остальных констант повторов и границ",
        "режим denyUnmatched — режим повышенной безопасности и пониженной доступности: serve недоступен — ход не выполняется, а не уходит в автоисполнение; полный откат кода возвращает baseline со всеми его exec --yolo-путями и откатом политики не является",
        "применение режима требует bootout/bootstrap, а не kickstart: runbook и учение в VER-008, ADR 0003 фиксирует последовательность"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched session/start несёт denyUnmatched, approve не отправляется (T-A14), в комбинации с -32030 и прочими пре-турновыми сбоями serve exec --yolo не вызывается и запрос завершается контролируемым отказом (T-A11b); без env — allowAll и согласованный fallback; невалидное значение останавливает старт с ошибкой в логе; на боевой машине учение VER-008 allowAll → denyUnmatched → allowAll подтверждает эффективный approvalMode в serve init после каждого шага"
      }
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "reliability",
      "source": "модель muse-wonder-full-1.0 effort=max в serve",
      "stimulus": "approval/request через 275-412 с мышления на длинном промпте (768118-1326216 символов)",
      "environment": "боевой мост :9886, stream=true, клиент DSH на месте",
      "artifact": "ServeRun и ApprovalPolicy моста",
      "response": "тот же процесс serve продолжает ход после receipt и approval/decide, exec не запускается, второй turn/start не уходит; при деградации локальный исход фиксируется один раз, поздние ответы сервера его не меняют, группа и слот освобождаются не позже grace 15 с, отсчитанного по монотонным часам от защёлкивания деградации (включая попытку записи cancel или отказного decide), даже если stdin serve заблокирован",
      "response_measure": "в фейковом MSP ровно один turn/start и нет exec-argv; после denied четыре поведения сервера (повторный request, terminal=false, успешный terminal, молчание) дают один терминальный исход и не более 10 decide суммарно; игнорирующий cancel serve мёртв и слот свободен в пределах grace при ужатых константах теста; на тяжёлом пути в bridge.log строка решения approval и done via=serve без fallback exec по этому ходу; при заблокированном stdin перед деградацией (T-A09c) время от защёлкивания до убитой группы и свободного слота не больше grace плюс уборка при ужатых константах",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ]
    },
    {
      "id": "QA-002",
      "quality": "security",
      "source": "модель запрашивает действие с subject.kind tool или network при allowAll",
      "stimulus": "approval/request с rawArgs, содержащим канарейку секрета",
      "environment": "serve с --disable-write --disable-shell, песочница включена",
      "artifact": "аудит-лог решений моста",
      "response": "действие авторазрешено только в пределах неотключённых инструментов, в лог попадает одна строка безопасных полей",
      "response_measure": "строка лога содержит только разрешённые поля аудита решений моста; toolName и choiceId не из allowlist [A-Za-z0-9_.:-] до 64 символов дословно в лог не попадают (канарейки в rawArgs и в choiceId отсутствуют в логе, JSON и SSE); serve argv без --disable-sandbox",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "транспорт Meta через ProxyRack",
      "stimulus": "транзиентный сбой пре-турновой фазы serve (spawn, handshake, session/start) с маркером net-timeout или родственным; для наблюдавшихся посреди хода net-timeout 20-452 с (EVD-011) повтор по умолчанию недопустим (ACTION_POSSIBLE, RISK-009)",
      "environment": "до первого контентного кадра, клиент на месте, stream и non-stream",
      "artifact": "цикл попыток Handler",
      "response": "мост повторяет пре-турновую фазу свежим serve-процессом в пределах E и отдаёт один успешный исход; посреди хода net-timeout терминален по умолчанию и повторяется только в области observed-items по решению владельца (Q-010)",
      "response_measure": "ровно 2 попытки serve при одном пре-турновом сбое с маркером, пауза 2 с плюс джиттер до 1 с, один [DONE] и ни одного error-кадра между попытками, суммарно не дольше E от приёма запроса включая ожидание слота; net-timeout после записи turn/start даёт ровно 1 попытку (область по умолчанию)",
      "verification_ids": [
        "VER-002",
        "VER-010"
      ]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "транспорт Meta через ProxyRack",
      "stimulus": "net-timeout на каждой попытке, включая длинный сбой 452 с из лога; отдельно — три и более одновременных запроса при двух занятых слотах с задержанными serve и fallback",
      "environment": "клиент на месте, MAX_CONCURRENT=2",
      "artifact": "цикл попыток Handler и освобождение слота",
      "response": "после исчерпания повторов один терминальный отказ существующего формата 502 или SSE error с одним [DONE]; ожидавший слот запрос получает ответ внутри исполнительного бюджета либо предусмотренную ошибку до клиентского предела 1900 с, а не обрыв клиента; попытка получает только остаток до E, обязательные фазы (grace, уборка, терминальная выдача) укладываются в резерв между E и D",
      "response_measure": "вызовов run_attempt не более 3 без контекстного повтора и не более 4 с ним одинаково в AD-003, QA-004 и VER-002; сумма пауз не более 8 с; D = TIMEOUT_S = 1800 с от приёма запроса при значениях по умолчанию, E = D − FINISH_RESERVE_S (35 с); запрос с остатком до E меньше MIN_ATTEMPT_REMAINING_S (120 с) не стартует новый процесс и получает предусмотренную ошибку; модель, висящая до E, даёт терминальный исход не позже D и свободный слот (T-R10); успешная выдача после попытки укладывается в запас 100 с до клиентских 1900 с; все группы процессов мертвы и слот освобождён ровно один раз",
      "verification_ids": [
        "VER-002",
        "VER-005",
        "VER-001"
      ]
    },
    {
      "id": "QA-005",
      "quality": "compatibility",
      "source": "serve присылает первую summary-дельту, затем ход падает net-timeout",
      "stimulus": "транзиентная ошибка после первой live reasoning-дельты клиенту; отдельно — заглушка выполняет наблюдаемый побочный эффект БЕЗ item/started|completed, approval/request и выходного текста и затем возвращает net-timeout после записи turn/start (serve) либо с пустым stdout (exec)",
      "environment": "stream=true, live reasoning включён AD-004",
      "artifact": "граница _content_started",
      "response": "повтор и fallback запрещены (ACTION_POSSIBLE защёлкнут), клиент получает один терминальный error и один [DONE] без дубля reasoning, побочный эффект выполнен ровно один раз",
      "response_measure": "ровно 1 попытка и ровно 1 побочный эффект в обеих ветках заглушки (serve и exec) в области pre-action по умолчанию (T-R07); ровно 1 попытка при _content_started истинном; сбой до записи turn/start с транзиентным маркером повторяется по QA-003; в области observed-items (T-R07b) заглушка без сигналов повторяется с warning и retry_scope, заглушка с инструментальным item — нет; в логе есть время первой дельты, строка retry_blocked и поля timeToFirstTokenMs/usage транзиентного терминала для закрытия ASM-010",
      "verification_ids": [
        "VER-002",
        "VER-003"
      ]
    },
    {
      "id": "QA-006",
      "quality": "usability",
      "source": "владелец ждёт длинный ход wonder 205-237 с и дольше",
      "stimulus": "serve присылает summary.N по ходу мышления",
      "environment": "stream=true, клиент DSH с streamIdleTimeoutMs=1900000",
      "artifact": "SSE-поток моста",
      "response": "клиент получает reasoning_content приростами до конца хода, разрывы между любыми кадрами закрывает keepalive 15 с; клиент, переставший читать, не удерживает цикл чтения MSP, процесс и слот дольше LIVE_WRITE_TIMEOUT_S ни при блокировке live-записи, ни при блокировке keepalive или терминальной выдачи под общим замком",
      "response_measure": "первый reasoning-кадр строго раньше терминального кадра в фейковом тесте с задержанными дельтами, порядок и текст соответствуют префикс-монотонному правилу AD-004 без дублей; на тяжёлом пути в UI виден прирост reasoning во время мышления и лог первой дельты меньше длительности хода; приход дельт только в конце хода фиксируется диагностикой VER-011 и оставляет REQ-MUSE-004 невыполненным, приёмку не даёт; ожидание _wlock и запись каждого кадра SSE укладываются в единый бюджет LIVE_WRITE_TIMEOUT_S=3 с на вызов _sse_write: в тесте, где первым блокируется keepalive-кадр, а затем приходит summary-дельта, sink возвращается не позже предела, группа мертва и слот свободен за предел плюс подтверждение смерти, второй клиент обслуживается (T-L08b); при расхождении snapshot авторитетный текст F доходит клиенту целиком (T-L07)",
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-011"
      ]
    },
    {
      "id": "QA-007",
      "quality": "compatibility",
      "source": "обычный короткий запрос DSH любой модели, включая muse-spark-*",
      "stimulus": "ход без approval, без транзиентных сбоев, stream и non-stream",
      "environment": "мост после выката, профили DSH без изменений",
      "artifact": "внешний контракт /v1/chat/completions, /health, /v1/models",
      "response": "формы ответов, коды, порядок финальных кадров и окна моделей как до изменения; внутреннее поле approvalMode клиенту не видно",
      "response_measure": "полный файл тестов зелён включая прежние 67, /health и /v1/models отдают прежние context_length (wonder 400000, spark 1048576)",
      "verification_ids": [
        "VER-004",
        "VER-005",
        "VER-008"
      ]
    },
    {
      "id": "QA-008",
      "quality": "operability",
      "source": "автообновление Muse CLI, как переход 1.4.7 -> 1.4.8 ночью 15.10",
      "stimulus": "новая версия возвращает -32030 на явный approvalMode или меняет fingerprint схемы",
      "environment": "боевой мост без пересборки, следующий ход после обновления",
      "artifact": "ServeRun init и session/start",
      "response": "ход не эмулирует allowAll поверх серверного потолка: ServeRun прерывается до записи turn/start с warning; при allowAll ровно один exec-fallback доводит ход, при denyUnmatched exec не запускается и запрос завершается контролируемым отказом; версия и fingerprint видны в логе",
      "response_measure": "фейковая ветка -32030 не даёт второго session/start и approval/decide в том же процессе; allowAll — один exec и завершённый ход, denyUnmatched — ноль exec-процессов (нет --yolo в argv), один terminal 502/SSE error и один [DONE]; то же для EOF handshake, таймаута handshake, spawn failed; строка serve init содержит версию сервера и эффективный режим на каждом ходе; учение VER-008 allowAll → denyUnmatched → allowAll подтверждает эффективный режим в bridge.log",
      "verification_ids": [
        "VER-001",
        "VER-008"
      ]
    },
    {
      "id": "QA-009",
      "quality": "operability",
      "source": "транспорт Meta через ProxyRack при общей деградации",
      "stimulus": "серия net-timeout под двумя параллельными ходами при MAX_CONCURRENT=2",
      "environment": "оба слота заняты, клиенты на месте, до первых контентных кадров",
      "artifact": "циклы попыток Handler и счётчик параллельных процессов",
      "response": "повторы идут внутри уже занятых слотов с паузами, параллелизм процессов не растёт, оба запроса завершаются внутри исполнительного дедлайна E без взаимной блокировки слотов",
      "response_measure": "одновременно не более 2 процессов модели на мост, на запрос не более 4 вызовов run_attempt и пауз суммарно не более 8 с, слоты освобождены по одному разу; глобального circuit breaker нет осознанно, поскольку удерживаемый слот не даёт повторам повысить параллельную нагрузку (FU-010)",
      "verification_ids": [
        "VER-002"
      ]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "ApprovalPolicy (чистое решение по снимку params внутри server.py)",
      "responsibility": "по params approval или userInput выдать действие approve с конкретным choiceId (только при сконфигурированном allowAll по AD-007), deny/abort, cancel-user-input или fail-turn и аудит-запись решений моста только безопасными полями с allowlist-рендером toolName и choiceId; единственное место знания политики AD-001; селективных запретов по protectedWrite/judgeEscalated до живых payload не содержит (FU-003 отклонён с обоснованием в AD-002)",
      "allowed_dependencies": [
        "stdlib",
        "_redact_secrets для аудит-строки"
      ],
      "forbidden_dependencies": [
        "ServeRun._send и любой I/O",
        "subprocess",
        "Handler и SSE-сокет",
        "чтение rawArgs дальше факта наличия",
        "глобальное изменяемое состояние между ходами",
        "логирование choiceId и toolName дословно без allowlist-рендера и предела длины"
      ],
      "verification_ids": [
        "VER-001"
      ]
    },
    {
      "id": "BND-002",
      "component": "ServeRun (MSP-транспорт одного хода serve)",
      "responsibility": "процесс serve на запрос, handshake с approvalMode и деградацией AD-006, receipt и команды decide/cancel/turn-cancel строго по решению BND-001, дедупликация и границы решений, терминальное защёлкивание отказа с grace 15 с и убийством группы, классификация транспортных сбоев до и после записи turn/start для предиката допуска Handler, фиксация инструментальной активности item/approval для того же предиката, накопление текста и summaries, вызов live-sink Handler без владения сокетом; защёлкивание ACTION_POSSIBLE ДО записи turn/start и доведение флага (а также списка item kind и признака approval-трафика) до Handler; предел записи управляющей команды CONTROL_WRITE_TIMEOUT_S и grace от монотонного момента защёлкивания; безопасный журнал каждого item/started|completed с kind вне {reasoning, agentMessage} (только kind и toolName по allowlist [A-Za-z0-9_.:/-]{1,64}, без rawArgs), счётчик таких item и поля timeToFirstTokenMs/usage транзиентного терминала в итоговой строке хода",
      "allowed_dependencies": [
        "ApprovalPolicy (BND-001)",
        "_uuid7",
        "_log",
        "_terminate_run",
        "live-sink колбэк Handler"
      ],
      "forbidden_dependencies": [
        "прямая запись в SSE-сокет",
        "запуск exec Run",
        "захват _slots",
        "решение политики вне BND-001",
        "логирование rawArgs и тел вопросов",
        "ServeUnavailable с exec-fallback после записи turn/start или после approval-трафика",
        "новые MSP-команды после терминального защёлкивания, кроме одного turn/cancel ветки деградации",
        "журнал аргументов инструментов и rawArgs в строках item",
        "ожидание управляющей команды дольше остатка grace или CONTROL_WRITE_TIMEOUT_S"
      ],
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-009"
      ]
    },
    {
      "id": "BND-003",
      "component": "Handler, цикл попыток хода (run_attempt и окружающие повторы)",
      "responsibility": "абсолютный дедлайн запроса D от приёма и исполнительный E = D − FINISH_RESERVE_S на ожидание слота, попытки и паузы, резерв E..D на grace, уборку и терминальную выдачу; единый предикат допуска любого нового процесса: клиент на месте, нет _content_started, нет защёлкнутой approval-деградации, нет ACTION_POSSIBLE у прежних попыток (область pre-action; в области observed-items — барьер наблюдаемой активности), прежние группы мертвы, остаток до E не меньше MIN_ATTEMPT_REMAINING_S, для exec — режим approval не denyUnmatched; serve-first с exec fallback только до записи turn/start, отдельные счётчики контекстного (не более 1, барьер наблюдаемой активности по AD-003 п.5) и транзиентного (не более 2) повторов, один слот на весь ход; единственное место создания exec-процесса",
      "allowed_dependencies": [
        "ServeRun (BND-002)",
        "Run (exec)",
        "_prune_messages и _context_limit",
        "_slots один acquire на запрос",
        "_watch_client"
      ],
      "forbidden_dependencies": [
        "повторный _slots.acquire для повтора",
        "повтор при _content_started или ушедшем клиенте",
        "второй контекстный retry",
        "полный TIMEOUT_S каждой повторной попытке",
        "content-кадры между попытками",
        "новый процесс в обход единого предиката допуска, включая внутренний fallback после turn/start",
        "ожидание слота или попытка за абсолютным дедлайном от приёма запроса",
        "exec-процесс при настроенном denyUnmatched в любой роли (fallback, повтор)",
        "новый процесс после защёлкнутого ACTION_POSSIBLE в области pre-action",
        "дедлайны и паузы на time.time() вместо time.monotonic()"
      ],
      "verification_ids": [
        "VER-002",
        "VER-004",
        "VER-001"
      ]
    },
    {
      "id": "BND-004",
      "component": "Handler, SSE-эмиттер (_sse_begin, _keepalive_loop, live reasoning sink, _send_sse)",
      "responsibility": "единственный писатель в сокет: role-кадр, пустой keepalive 15 с в фазе OPEN, live reasoning только префикс-монотонно до заморозки с финальным согласованием (startswith → хвост, иначе разделитель и F целиком), единый предел LIVE_WRITE_TIMEOUT_S=3 с на каждый вызов _sse_write — ожидание _wlock и запись одним бюджетом для ВСЕХ писателей (role, keepalive, live-sink, терминальная выдача, [DONE]); исчерпание бюджета или частичная запись переводит соединение в ветку ушедшего клиента с убийством группы; _content_started только фактически отправляемой дельтой внутри той же критической секции до записи; один [DONE] в неаварийных ветках",
      "allowed_dependencies": [
        "_sse_write под _wlock",
        "_sse_chunk",
        "_split_sse_chunks"
      ],
      "forbidden_dependencies": [
        "запись в обход _sse_write",
        "удержание _wlock во время выполнения модели",
        "live content и tool_calls до конца хода",
        "SSE-комментарии keepalive в этом изменении",
        "исключения live-записи в ServeRun",
        "неограниченное по времени ожидание _wlock любым писателем",
        "удержание _wlock записью дольше остатка бюджета LIVE_WRITE_TIMEOUT_S",
        "предел записи только на live-sink при неограниченных keepalive и терминальной выдаче",
        "публикация reasoning вне префикс-монотонного правила и потеря авторитетного текста F при расхождении snapshot"
      ],
      "verification_ids": [
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "BND-005",
      "component": "Внешняя эксплуатационная граница (DSH, muse CLI и Meta, прокси :10816, launchd-зеркало)",
      "responsibility": "мост не меняет профили DSH, лаунчер и прокси; деплой только копией server.py в ~/.dsh/bridges/muse-bridge/ и перезапуском com.user.dsh-muse-bridge после бэкапа; источник net-timeout и версии CLI остаются внешними рисками; незакоммиченный baseline REQ-MUSE-001 отделяется первым отдельным коммитом до правок REQ-MUSE-002..004, diff Coder по protected_paths пуст, правки тестов ограничены заменой approval-теста, обновлением test_t18 и добавлением классов Approval, TransientRetry и LiveReasoning в tests/test_muse_bridge_killpg.py",
      "allowed_dependencies": [
        "~/.dsh/bridges/muse-bridge/server.py зеркало",
        "launchctl kickstart com.user.dsh-muse-bridge",
        "GET /health и /v1/models с ключом моста"
      ],
      "forbidden_dependencies": [
        "правки cordis.patch.yml профилей DSH в этом изменении",
        "закрепление или откат версии Muse CLI мостом",
        "изменения форвардера ProxyRack",
        "записи muse-spark-* в профилях"
      ],
      "verification_ids": [
        "VER-008",
        "VER-009",
        "VER-012"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "muse-bridge SSE на POST /v1/chat/completions stream=true, только serve-путь",
      "consumer": "клиент DSH (openai-completions, OpenAI SDK и pi-ai)",
      "change": "delta.reasoning_content приходит несколькими кадрами по ходу мышления вместо одного кадра после хода по префикс-монотонному правилу AD-004 (публикуется только прирост summary.0 до заморозки); поле, форма чанка chat.completion.chunk, порядок reasoning раньше tool_calls и content, финальные кадры и [DONE] без изменений; в расширяющем случае (авторитетная сборка F начинается с отправленного P) конкатенация дельт равна прежнему единому значению; при расхождении (не ожидается, ASM-011) клиент получает уже отправленный P, разделитель \"\\n\\n\" и авторитетный F целиком — часть текста может быть показана дважды, потеря исключена, расхождение логируется счётчиком",
      "compatibility": "аддитивная фрагментация существующего поля плюс сформулированная семантика редкого расхождения (дублирование вместо потери): OpenAI-стрим определён накоплением дельт; droid-мост того же DSH уже отправляет клиенту live reasoning_content (EVD-015), потребление клиентом — допущение ASM-003, профиль объявляет supportsReasoningEffort=true (EVD-016); non-stream JSON, exec-ходы, /health и /v1/models не затронуты; новых полей, путей и кодов нет",
      "verification_ids": [
        "VER-003",
        "VER-009"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "dynamic",
      "question": "Как ход переживает approval внутри serve: session/start allowAll, receipt, decide, terminal=false, userInput/cancel, терминальное защёлкивание, grace 15 с и деградация без exec после turn/start?",
      "artifact_ref": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md#2-req-muse-002-approval-без-перезапуска-хода"
    },
    {
      "id": "VIEW-002",
      "type": "dynamic",
      "question": "Как граница ACTION_POSSIBLE, единый предикат допуска нового процесса, абсолютный дедлайн D с исполнительным E и очередью, область повтора, _content_started и уход клиента ограничивают fallback и оба вида повторов?",
      "artifact_ref": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md#3-req-muse-003-ограниченный-повтор-транзиентных-сбоев"
    },
    {
      "id": "VIEW-003",
      "type": "dfd",
      "question": "Где границы доверия allowAll: промпт, инструменты модели, аудит-лог, сеть через прокси?",
      "artifact_ref": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md#5-безопасность-и-угрозы"
    },
    {
      "id": "VIEW-004",
      "type": "deployment",
      "question": "Как изменение доезжает до боевого моста :9886 и откатывается без потери REQ-MUSE-001?",
      "artifact_ref": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md#7-выкат-проверка-и-откат"
    }
  ],
  "evolution": {
    "compatibility": "Внешний OpenAI-контракт заморожен, единственный дельта-эффект CD-001 внутри существующего поля; non-stream, exec-путь, /health, /v1/models, окна моделей и профили DSH без изменений; смешанных версий внутри одного процесса нет, перезапуск моста атомарно меняет поведение всех новых ходов, идущие ходы завершаются старым процессом только до перезапуска launchd; ожидание слота при насыщении теперь завершается той же формой предусмотренной ошибки внутри исполнительного дедлайна E от приёма вместо ожидания полных 1800 с плюс ход (RW-002), форм ответов это не меняет; порог старта попытки MIN_ATTEMPT_REMAINING_S=120 с и резерв FINISH_RESERVE_S=35 с сдвигают момент предусмотренной ошибки при насыщении очереди раньше (не позже E−120 с от приёма), форм ответов это не меняет; единый предел 3 с на запись SSE действует на всех писателей (RISK-011)",
    "migration": "NOT_APPLICABLE: персистентных данных и схем хранения нет, serve-сессия создаётся на запрос с --no-session-log, состояние повторов и approval живёт только внутри хода; обновляются код репозитория, тесты и деплой-копия server.py",
    "rollout": "Шаг 0: незакоммиченный baseline REQ-MUSE-001 в дереве dev (2941 вставка, EVD-020) отделяется первым отдельным коммитом на ветке bugfix/muse-wonder-approval-retry-liveness (или предварительной фиксацией владельцем): его diff дословно равен снимку дерева до работы, дальнейшие коммиты содержат только дельту REQ-MUSE-002..004, git diff baseline..HEAD правок REQ-MUSE-001 не включает. Этапы с red затем green и отдельной проверкой каждого: этап 1 — REQ-MUSE-002 (AD-002, AD-006, AD-007: approve/decide, деградация, denyUnmatched без exec, журнал инструментальных item; тесты класса Approval); этап 2 — дедлайн и предикат допуска (AD-003: ACTION_POSSIBLE, E/D, MIN_ATTEMPT_REMAINING_S, область повтора; класс TransientRetry); этап 3 — live (AD-004: единый предел _sse_write, заморозка, согласование; класс LiveReasoning) стартует ТОЛЬКО после PASS спайка VER-013 (при FAIL AD-004 не реализуется, пакет возвращается владельцу). Затем бэкап repo и зеркала server.py в ~/work/backups с датой; после ACCEPT панели и MR человеком копия server.py в ~/.dsh/bridges/muse-bridge/server.py, launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge (plist при деплое кода не менялся), проверка VER-008 с учением отката, затем тяжёлый путь VER-009 владельцем и диагностика VER-011; строка ADR 0003 добавляется в docs/adr/INDEX.md тем же MR после материализации proposal оркестратором. В dev напрямую не коммитить",
    "rollback": "Быстрый операционный откат политики без кода (AD-007): MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched — правка EnvironmentVariables в ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist, затем launchctl bootout gui/$(id -u)/com.user.dsh-muse-bridge и launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist из внешней оболочки (kickstart -k plist не перечитывает, EVD-027; при ошибке 5 после bootout повторить bootstrap). Область действия: в этом режиме мост нигде не авторазрешает действия модели — serve получает denyUnmatched, approve не отправляется и exec --yolo не запускается ни как fallback, ни как повтор: при недоступном serve на пре-турновой фазе запрос завершается контролируемым отказом (502 или SSE error), доступность ниже, чем при allowAll (RISK-010). Возврат — тем же путём на allowAll (учение VER-008). Полный откат кода: восстановить server.py из бэкапа в репозитории и в ~/.dsh/bridges/muse-bridge/server.py и перезапустить com.user.dsh-muse-bridge kickstart; данные не мигрировали, профили DSH не менялись, поведение возвращается к baseline (ServeUnavailable с exec --yolo и буферизованный reasoning целиком) и откатом политики approval не является"
  },
  "threat_model": {
    "required": true,
    "assets": [
      "файлы рабочего каталога serve (WORKSPACE моста) и доступные модели через инструменты данные",
      "исходящая сеть модели через прокси 127.0.0.1:10816",
      "содержимое промптов и секреты в bridge.log",
      "два слота параллелизма боевого моста :9886"
    ],
    "trust_boundaries": [
      "DSH -> мост: loopback 127.0.0.1:9886 с MUSE_BRIDGE_KEY",
      "мост -> muse serve: stdio JSON-RPC, политика approval на проводе при песочнице хоста",
      "модель -> инструменты serve: --disable-write и --disable-shell при конструировании хоста, песочница включена",
      "muse -> Meta: обёртка muse-cli.sh и внешний ProxyRack вне контроля моста"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Промпт или данные хода склоняют модель вызвать не отключённый флагами инструмент (network, webSearch, иной tool subject), и allowAll выполняет его без человека, включая отправку содержимого рабочего каталога наружу",
        "mitigation": "Write и shell остаются отключены хостом, песочница не отключается, workspace ограничен каталогом моста. Журнал является аудитом решений моста по остаточным approval-запросам, а не полным аудитом всех разрешённых при allowAll действий: действие, разрешённое сервером без остаточного запроса, строки в журнале может не иметь, и отсутствие строки не доказывает отсутствие инструментального действия (FU-001). Полный аудит инструментов отдельным источником в этом пакете не обещается; селективный запрет по факту payload отложен до данных OPEN-01 и не выдумывается, операционный откат режима — AD-007. Операционный откат denyUnmatched теперь действительно снимает автоматические разрешения: exec --yolo при нём не запускается ни в какой роли (AD-006, AD-007, T-A11b); журнал инструментальных item (kind и безопасный toolName без аргументов, PF-a2-006) даёт аудит наблюдаемых инструментальных действий отдельно от остаточных approval-запросов",
        "verification_ids": [
          "VER-001",
          "VER-009"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "Логирование approval уносит rawArgs, вопросы userInput или отражённый промпт с секретами в bridge.log и ответы клиенту",
        "mitigation": "Allowlist полей аудита в BND-001, запрет rawArgs и тел вопросов, рендер свободных строк toolName и choiceId только из [A-Za-z0-9_.:-] длиной до 64 с обрезкой списка choiceId до 8 и заменой остальных на redacted с префиксом sha256, вся диагностика через _redact_secrets и удаление отражённых промптов попыток как в REQ-MUSE-001, канареечные тесты на rawArgs и на choiceId (FU-009)",
        "verification_ids": [
          "VER-001",
          "VER-005"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Цикл approval или userInput внутри хода либо каскад повторов удерживает оба слота MAX_CONCURRENT=2 и блокирует мост для владельца",
        "mitigation": "Счётные границы 10 decide и 3 cancel на ход с терминальным защёлкиванием, grace 15 с от защёлкивания по монотонным часам с принудительным killpg даже при заблокированном stdin, предел записи управляющей команды 5 с, абсолютный дедлайн D и исполнительный E с резервом, не более 2 транзиентных повторов внутри удерживаемого слота (в области по умолчанию — только пре-турновых), единый предел 3 с на ожидание замка и запись каждого кадра SSE любым писателем с веткой зависшего клиента, надзор ухода клиента убивает группу, слот один на ход с карантином неподтверждённой смерти",
        "verification_ids": [
          "VER-001",
          "VER-002",
          "VER-003"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "Транзиентный повтор переигрывает промпт после частичных побочных эффектов первой попытки и удваивает действие или вывод",
        "mitigation": "Позитивное доказательство отсутствия действия вместо наблюдаемого барьера: новый процесс допускается только если ни у одной прежней попытки не защёлкнут ACTION_POSSIBLE — для serve защёлка ставится ДО записи turn/start, для exec — при старте процесса; после неё повтор и fallback запрещены при любой ошибке, любом тексте stderr, пустом stdout и подтверждённой смерти группы, потому что действие без item/approval сигналов фактами не исключено (ASM-010). Дополнительно требуются отсутствие контентного кадра, подтверждённая смерть прежних групп, остаток до E и клиент на месте. Опциональная область observed-items (барьер a2) принимает ненаблюдаемый остаток at-least-once только после записанного решения владельца (Q-010) и с warning в логе; контекстный повтор AD-005 сохраняет наблюдаемый барьер, остаток унаследован от baseline REQ-MUSE-001",
        "verification_ids": [
          "VER-002",
          "VER-003"
        ]
      }
    ]
  },
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Авторазрешённое действие неизвестно до первого живого payload: инструмент инцидентов wonder при отключённых write и shell не установлен (OPEN-01)",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Флаги хоста и песочница сохранены, аудит решений моста по остаточным запросам с первого хода, тяжёлый путь владельца сверяет лог решений с ожидаемой работой и отдельно фиксирует ходы без остаточного запроса (отсутствие строки не трактуется как отсутствие действия); селективная политика только отдельным решением по собранным payload, быстрый откат режима — AD-007; журнал инструментальных item по kind собирает данные для OPEN-01 помимо остаточных approval-запросов (VER-009 выбирает такие ходы отдельно)",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Повторы моста складываются с повторами провайдера CLI и растягивают отказ при живом общем сбое транспорта (OPEN-05, OPEN-08)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Не более 2 транзиентных повторов с паузами суммарно не более 8 с внутри удерживаемого слота и исполнительного дедлайна E от приёма, поэтому параллельная нагрузка не превышает MAX_CONCURRENT=2 и глобальный circuit breaker осознанно не вводится (QA-009); modelRetryScheduled логируется для разбора наложения",
      "verification_ids": [
        "VER-002",
        "VER-010"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "Live reasoning сужает окно безопасного повтора; при ошибке учёта хвоста или расхождении snapshot с отправленным префиксом клиент теряет или дублирует часть reasoning в финале",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Префикс-монотонная публикация AD-004: до заморозки стримится только прирост summary.0, финальный хвост доотдаётся только когда сборка расширяет отправленное; при расхождении выбрано дублирование — разделитель и авторитетный F целиком, потеря исключена, счётчик reasoning_diverged в логе (ASM-011); _content_started только внутри критической секции записи фактически отправляемой дельты; парные тесты interleaved и расхождения snapshot (T-L06, T-L07)",
      "verification_ids": [
        "VER-002",
        "VER-003"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Общий код меняет поведение muse-spark-*, на которые приходятся 27 из 29 исторических approval-переходов, без отдельного живого сценария",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Фейковые тесты гоняют spark как модель фикстуры ServeRun, окна и лимиты spark не меняются, тяжёлый путь включает короткий контрольный ход spark после wonder",
      "verification_ids": [
        "VER-001",
        "VER-005",
        "VER-009"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Автообновление Muse CLI меняет схему MSP или возвращает потолок approvalMode между выкатом и следующим ходом (OPEN-09)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "AD-006: версия и fingerprint в логе каждого хода; потолок -32030 не обходится клиентским approve — ход один раз уходит в существующий exec-fallback до turn/start с warning; неизвестная версия не останавливает мост",
      "verification_ids": [
        "VER-001",
        "VER-008"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Незакоммиченный REQ-MUSE-001 в дереве dev и единственная деплой-копия делают откат зависимым от бэкапа, ошибка копирования затирает рабочее состояние",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Baseline REQ-MUSE-001 отделяется первым отдельным коммитом до правок REQ-MUSE-002..004 (FU-008), дальнейший diff baseline..HEAD его не содержит; отдельная ветка, бэкап обеих копий server.py в ~/work/backups до перезаписи, проверка diff по protected_paths (VER-012), cmp зеркала и health после перезапуска до тяжёлого пути",
      "verification_ids": [
        "VER-005",
        "VER-008"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Summary-дельты на effort=max приходят только в конце хода, и прогресс REQ-MUSE-004 недостижим текущим источником reasoning (OPEN-04)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Лог времени первой дельты на каждом serve-ходе и отдельная диагностика VER-011 фиксируют факт, но приёмку не дают: REQ-MUSE-004 остаётся NOT_MET/BLOCKED и блокирует сдачу набора требований; дальше нужен отдельный согласованный путь прогресса или явное изменение требования владельцем новым delta-пакетом, а не закрытие наблюдением; до реализации AD-004 тайминг первой дельты замеряется дешёвым спайком VER-013 на одном живом ходе wonder max: при дельтах только в конце хода AD-004 не реализуется и пакет возвращается владельцу (PF-a2-013)",
      "verification_ids": [
        "VER-003",
        "VER-009",
        "VER-013"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "Форма живого availableChoices отличается от схемы фикстуры (scope, policy amendment, пустой список), и decide получает -32052 или выбирает лишнее разрешение",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Выбор только из текущих choices по decision с запретом policy amendment; ошибки decide и пустые списки ведут в терминальное защёлкивание AD-002 без exec и без повторных команд, аудит пишет отрендеренный список choiceId для сверки с первым живым ходом",
      "verification_ids": [
        "VER-001",
        "VER-009"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Область повтора pre-action оставляет наблюдавшиеся net-timeout посреди хода (20-452 с от старта хода, EVD-011) терминальным отказом без повтора: REQ-MUSE-003 по умолчанию закрывает только пре-турновые сбои, польза повтора для владельца мала до решения Q-010",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Цена принята явно ради безопасности (at-least-once владельцем не принималась, THREAT-004): приёмка фиксирует REQ-MUSE-003 как выполненный только в области pre-action (VER-010, VER-009), доля транзиентных терминалов посреди хода считается по логу (retry_blocked, VER-011); расширение — переключатель MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=observed-items после решения владельца Q-010 и закрытия ASM-010 по журналу item kind и полям timeToFirstTokenMs/usage",
      "verification_ids": [
        "VER-002",
        "VER-009",
        "VER-010",
        "VER-011"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "При denyUnmatched недоступность serve на пре-турновой фазе (spawn, handshake, -32030) завершает ходы терминальной ошибкой вместо exec: доступность моста падает, пока включён откат политики",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Осознанная цена сохранения политики (AD-006, AD-007): режим включается оператором на время инцидента и возвращается учением allowAll; тест T-A11b подтверждает контролируемый исход; полный откат кода возвращает baseline вместе с его exec --yolo",
      "verification_ids": [
        "VER-001",
        "VER-008"
      ]
    },
    {
      "id": "RISK-011",
      "scenario": "Единый предел 3 с на ожидание замка и запись SSE принимает за зависшего клиента, который читает медленнее 3 с на кадр на любой стадии ответа, и обрывает его ход",
      "probability": "low",
      "impact": "medium",
      "mitigation": "Клиент DSH — loopback на той же машине, эталон предела тот же 3 с в droid-мосте того же клиента (EVD-015); кадры мелкие (около 300 символов, EVD-014); предел — модульная константа, обратима без изменения контрактов; случаи обрыва видны строкой client gone mid-stream",
      "verification_ids": [
        "VER-003",
        "VER-009"
      ]
    }
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-MUSE-002",
        "AD-001",
        "AD-002",
        "AD-006",
        "QA-001",
        "QA-002",
        "QA-008",
        "BND-001",
        "BND-002",
        "RISK-001",
        "RISK-004",
        "RISK-005",
        "RISK-008",
        "THREAT-001",
        "THREAT-002",
        "THREAT-003",
        "AD-007",
        "RISK-010",
        "BND-003",
        "QA-004"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
      "expected": "exit 0; red без фикса и green с фиксом: allowAll в session/start при env по умолчанию и denyUnmatched при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched без approve (T-A14); receipt и decide с choiceId из availableChoices, terminal=false, userInput/cancel; границы 10 включая финальный отказной decide и 3; терминальное защёлкивание при четырёх ответах сервера после denied (T-A13); T-A08 параметризован по кодам [F-28] -32050, -32052, -32053, -32054, -32030 (защёлкивают) и -32051 (benign) и по ошибке userInput/cancel; игнорирующий cancel serve теряет группу и слот не позже grace (T-A09b), то же при заблокированном stdin ДО деградации (T-A09c: grace считается от защёлкивания, группа убита killpg); деградация без exec; ошибка записи receipt/decide после turn/start без exec; allowAll: -32030 без второго session/start и без decide с одним exec-fallback (T-A11); denyUnmatched × {-32030, EOF handshake, таймаут handshake, session/start без sessionId, spawn failed}: exec-argv отсутствует, один терминальный исход 502/SSE error с причиной exec_fallback_disabled, один [DONE], а allowAll × тот же набор — ровно один exec (T-A11b, T-A14); журнал инструментальных item содержит kind и безопасный toolName и не содержит аргументов (канарейка), счётчик в итоговой строке хода (T-A15); канарейки rawArgs и choiceId отсутствуют в логе дословно (T-A10)",
      "environment": "локальный репозиторий, фейковый MSP через расширенный install_protocol_wrapper, модельных ходов нет",
      "owner": "verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-MUSE-003",
        "AD-003",
        "QA-003",
        "QA-004",
        "QA-005",
        "BND-003",
        "RISK-002",
        "RISK-003",
        "THREAT-003",
        "THREAT-004",
        "QA-009",
        "RISK-009"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
      "expected": "exit 0; область по умолчанию pre-action: (а) заглушка serve выполняет наблюдаемый побочный эффект (запись маркера) БЕЗ item/started|completed, approval/request и выходного текста, затем после записи turn/start возвращает net-timeout — ровно одна попытка, ровно один побочный эффект, один терминальный исход и один [DONE] (T-R07, red до фикса: сегодня/в a2 второй эффект возможен); (б) то же для exec: эффект, пустой stdout, маркер в stderr — один процесс, один эффект; (в) turn/start без ack, summary→EOF, summary→ошибка чтения, approval→ошибка записи receipt/decide, cancel→EOF — exec не запускается, один исход (T-R06), EOF рукопожатия до записи turn/start один раз уходит в exec; пре-турновый сбой serve с каждым из четырёх маркеров повторяется новым serve (до 2 раз, паузы 2 с и 4 с плюс джиттер до 1 с, в тестах ужаты monkeypatch), ровно 2 попытки и один [DONE] без error между (T-R01); три сбоя дают терминальную ошибку после не более 3 вызовов run_attempt без контекстного повтора и не более 4 с ним, процессов не более 8; нет нового процесса после _content_started, после approval-защёлкивания, при уходе клиента, неподтверждённой смерти группы, остатке до E меньше MIN_ATTEMPT_REMAINING_S и на состояния timeout и spawn_failed (T-R03); область observed-items (T-R07b): та же заглушка без сигналов повторяется с warning и retry_scope, заглушка с инструментальным item — нет; невалидное значение MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE останавливает старт; контекстный повтор AD-005 с барьером наблюдаемой активности и контекстный счётчик транзиентом не расходуется (T-R04, test_t18); дедлайн от приёма: три запроса при двух занятых слотах получают ответ или предусмотренную ошибку внутри E, запрос с остатком меньше порога процесс не стартует (T-R08); модель, висящая до E, даёт терминальный исход не позже D и свободный слот (T-R10); серия net-timeout под двумя ходами — не более 2 процессов (T-R09)",
      "environment": "локальный репозиторий, фейковые serve и exec с терминальными ошибками net-timeout",
      "owner": "verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "REQ-MUSE-004",
        "AD-004",
        "QA-005",
        "QA-006",
        "BND-002",
        "BND-004",
        "CD-001",
        "RISK-003",
        "RISK-007",
        "THREAT-004",
        "RISK-011"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
      "expected": "exit 0; дельты reasoning_content до финального кадра по префикс-монотонному правилу: interleaved-индексы и поздний меньший индекс не переставляют опубликованное (T-L06); расхождение snapshot: P=\"a\", F=\"b\\n\\nc\" даёт клиенту \"a\" + \"\\n\\n\" + \"b\\n\\nc\" (авторитетный текст целиком, без потери, дубль допускается), при расширяющем F хвост без дубля, расхождение логируется счётчиком reasoning_diverged (T-L07); клиент, переставший читать: T-L08a — заполнение буфера live-дельтами; T-L08b — ПЕРВЫМ блокируется keepalive-кадр под _wlock (red до фикса: sink ждёт замок до Handler.timeout), затем в цикл чтения MSP приходит summary-дельта; T-L08c — блокируется терминальная выдача; во всех трёх sink и писатели возвращаются не позже LIVE_WRITE_TIMEOUT_S (ужат в тесте), группа serve мертва и слот свободен за предел плюс подтверждение смерти, второй клиент получает полный ответ; пустые data-keepalive сохранены, : keepalive отсутствует, ровно один [DONE] в неаварийных ветках, обычный сбой live-записи ход исключением ServeRun не роняет",
      "environment": "локальный репозиторий, фейковый MSP с задержанными item/delta summary.N и item/completed",
      "owner": "verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "AD-005",
        "QA-007",
        "BND-003"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'ContextPrune or ContextRetry or AllowedModelsSync'",
      "expected": "exit 0; гарантии REQ-MUSE-001 без изменений: 400000/320000/200000, обязательный набор, атомарность tool-пар, ровно один контекстный повтор до первого контентного кадра",
      "environment": "локальный репозиторий, pytest через uv --no-project",
      "owner": "verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": [
        "REQ-MUSE-002",
        "REQ-MUSE-003",
        "REQ-MUSE-004",
        "AD-005",
        "QA-002",
        "QA-004",
        "QA-007",
        "BND-004",
        "RISK-004",
        "RISK-006",
        "THREAT-002"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py",
      "expected": "exit 0; весь файл зелён: прежний baseline 67 passed сохранён по смыслу, заменён только тест approval-контракта и обновлён test_t18 по AD-003, добавлены тесты Approval, TransientRetry и LiveReasoning сценариев delta-a2 (T-A09b, T-A11, T-A13, T-A14, T-R06..T-R09, T-L06..T-L08); прочие правки тестов вне этого списка, удаления и skip ради зелени запрещены (FU-007)",
      "environment": "локальный репозиторий, ветка Coder от фактического дерева dev",
      "owner": "verifier"
    },
    {
      "id": "VER-006",
      "requirement_ids": [
        "AD-005",
        "QA-007"
      ],
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge && .venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright",
      "expected": "ruff exit 0 по набору E4/E7/E9/F из ruff.toml; basedpyright 0 errors как baseline брифа, число предупреждений зафиксировано в отчёте verifier против baseline 1448 без новых errors в изменённых файлах",
      "environment": "локальный репозиторий с .venv (ruff и basedpyright присутствуют в .venv/bin)",
      "owner": "verifier"
    },
    {
      "id": "VER-007",
      "requirement_ids": [
        "REQ-MUSE-002",
        "REQ-MUSE-003",
        "REQ-MUSE-004",
        "QA-007"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/",
      "expected": "exit 0; Full Suite Gate перед MR по всему каталогу tests без deselect и skip правок",
      "environment": "локальный репозиторий, pyproject.toml отсутствует, поэтому uv --no-project",
      "owner": "verifier"
    },
    {
      "id": "VER-008",
      "requirement_ids": [
        "QA-007",
        "QA-008",
        "BND-005",
        "RISK-005",
        "RISK-006",
        "AD-007",
        "RISK-010"
      ],
      "kind": "command",
      "command": "cmp bridges/muse-bridge/server.py ~/.dsh/bridges/muse-bridge/server.py && launchctl list | grep com.user.dsh-muse-bridge && curl -sS -m 5 -H \"Authorization: Bearer $MUSE_BRIDGE_KEY\" http://127.0.0.1:9886/health && curl -sS -m 5 -H \"Authorization: Bearer $MUSE_BRIDGE_KEY\" http://127.0.0.1:9886/v1/models",
      "expected": "зеркало побайтово равно репозиторию, launchd-агент зарегистрирован, /health и /v1/models отвечают 200 с wonder context_length 400000 и spark 1048576; в свежем bridge.log после первого хода видны serve init с версией CLI и approvalMode allowAll; учение отката (PF-a2-007, EVD-027): правка EnvironmentVariables в ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist на MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched, launchctl bootout gui/$(id -u)/com.user.dsh-muse-bridge, bootstrap с повтором при ошибке 5, затем в bridge.log serve init с approvalMode=denyUnmatched после первого хода; возврат на allowAll тем же путём и serve init с approvalMode=allowAll; после каждого шага /health 200",
      "environment": "боевая машина владельца после kickstart; ключ подхватывается из окружения или ~/.dsh/.env без печати секрета в вывод",
      "owner": "verifier"
    },
    {
      "id": "VER-009",
      "requirement_ids": [
        "REQ-MUSE-002",
        "REQ-MUSE-003",
        "REQ-MUSE-004",
        "QA-001",
        "QA-006",
        "BND-005",
        "CD-001",
        "RISK-001",
        "RISK-004",
        "RISK-007",
        "RISK-008",
        "THREAT-001",
        "RISK-009",
        "RISK-011"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate тяжёлого пути и успешной приёмки REQ-MUSE-002..004: в существующем DSH-слоте владельца на длинной сессии живые ходы muse-wonder-full-1.0 effort=max рабочего размера с вызовом инструмента, повторный ход и два параллельных хода завершаются без fallback exec по approval и без потери хода; REQ-MUSE-004 засчитывается только реальным pre-terminal приростом reasoning в UI во время мышления, подтверждённым логом первой summary-дельты строго раньше конца хода, — сценарий «summary только при завершении» этот gate не проходит; ходы с остаточным approval-запросом и без него зафиксированы отдельно, отсутствие аудит-строки не считается доказательством отсутствия инструментального действия; done via=serve; короткий контрольный ход muse-spark проходит. Без этого gate слова готово и работает запрещены. Дополнительно в отчёте сдачи отдельной выборкой: ходы с инструментальными item (по журналу kind, PF-a2-006) отдельно от ходов без них; счётчик reasoning_diverged за тяжёлые ходы (ненулевой — владельцу, ASM-011); REQ-MUSE-003 засчитывается ТОЛЬКО в области pre-action: net-timeout посреди хода без повтора фиксируется как ожидаемое поведение по умолчанию и как NOT_MET для инцидентов EVD-011 до решения Q-010 (RISK-009)",
      "environment": "живой DSH-слот владельца, боевой мост :9886 после VER-008, модельные ходы выполняет владелец или verifier его руками, не Coder",
      "owner": "owner"
    },
    {
      "id": "VER-010",
      "requirement_ids": [
        "REQ-MUSE-003",
        "AD-003",
        "QA-003",
        "RISK-002",
        "RISK-009"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate: на отдельном экземпляре моста на другом порту с MUSE_BRIDGE_CLI на заглушку: (а) пре-турновый транзиентный сбой serve (handshake или session/start с маркером) на первой попытке и успех на второй — запросы JSON и SSE завершаются успехом после ровно одного повтора внутри E от приёма; (б) net-timeout после записи turn/start на каждой попытке — терминальный 502 или SSE error и один [DONE] после ровно одной попытки без второго запуска заглушки и без второго побочного эффекта (маркер-файл заглушки содержит одну запись); (в) при MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=observed-items тот же сбой без сигналов повторяется с warning в логе; (г) при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched и -32030 заглушка exec не вызывается; боевой мост не затронут",
      "environment": "отдельный экземпляр моста с заглушкой CLI, не боевой :9886",
      "owner": "verifier"
    },
    {
      "id": "VER-011",
      "requirement_ids": [
        "REQ-MUSE-004",
        "QA-006",
        "RISK-007"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Диагностический бинарный gate закрытия OPEN-04, приёмкой не является: для каждого тяжёлого хода VER-009 в bridge.log есть строка времени первой summary-дельты и длительность хода, а отчёт сдачи явно записывает REQ-MUSE-004 как MET только при pre-terminal дельте и как NOT_MET/BLOCKED при дельтах только в конце хода; при NOT_MET набор требований сданным не объявляется и требуется отдельный согласованный путь прогресса или явное изменение требования владельцем. Здесь же по тем же логам считается доля транзиентных сбоев после первой дельты (retry_blocked) для метрики FU-005",
      "environment": "живой DSH-слот владельца и bridge.log боевого моста :9886 после VER-008, разбор выполняет verifier по логам тяжёлых ходов владельца, не Coder",
      "owner": "verifier"
    },
    {
      "id": "VER-012",
      "requirement_ids": [
        "AD-005",
        "QA-007",
        "BND-005",
        "RISK-006"
      ],
      "kind": "command",
      "command": "git -C /Users/aazhiry1/work/src/cli-agent-bridge diff --name-only BASELINE..HEAD -- ruff.toml pyrightconfig.json server.py docs/adr/0001-persistent-droid-bridge.md docs/adr/0002-multi-binary-hub.md",
      "expected": "пустой вывод: ни один защищённый путь после отдельного baseline-коммита REQ-MUSE-001 не изменён; BASELINE подставляется верификатором хэшем baseline-коммита из rollout (шаг 0), docs/adr/0003 меняется только материализацией оркестратора exact bytes, а не правкой Coder (FU-007, FU-008)",
      "environment": "локальный репозиторий, ветка Coder после baseline-коммита",
      "owner": "verifier"
    },
    {
      "id": "VER-013",
      "requirement_ids": [
        "REQ-MUSE-004",
        "AD-004",
        "QA-006",
        "RISK-007"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate спайка OPEN-04 ДО реализации AD-004 (этап 3 rollout; PF-a2-013): verifier одноразовым MSP-клиентом-зондом вне продуктового кода и вне коммитов (скрипт в ~/work/tmp) запускает против реального muse serve с флагами моста ОДИН ход muse-wonder-full-1.0 effort=max на промпте около 100 KB и записывает секунды от turn/start до первой item/delta summary.N и до turn/completed, число summary-дельт и индексы; PASS: первая дельта раньше terminal не менее чем на один интервал keepalive (15 с) либо несколько дельт по ходу; результат записывается в Q-004/OPEN-04. FAIL (дельты только в конце хода): Coder не реализует AD-004 (этап 3), оркестратор возвращает пакет Architect с вопросом владельцу по REQ-MUSE-004",
      "environment": "живая машина владельца, один модельный ход (квота Meta), боевой мост не затрагивается",
      "owner": "verifier"
    }
  ],
  "protected_paths": [
    "docs/adr/0003-muse-serve-approval-allowall.md",
    "ruff.toml",
    "pyrightconfig.json",
    "docs/adr/0001-persistent-droid-bridge.md",
    "docs/adr/0002-multi-binary-hub.md",
    "server.py"
  ],
  "materialization": [
    {
      "source": "architecture/proposals/docs/adr/0003-muse-serve-approval-allowall.md",
      "target": "docs/adr/0003-muse-serve-approval-allowall.md",
      "sha256": "721ba63d70a47d85bde9d364c48703273fae9fe43d41c7c57613aacef1b90b24"
    }
  ],
  "approval": {
    "status": "APPROVED",
    "decision_ids": [
      "AD-001"
    ],
    "approved_by": "owner (aazhiry1)",
    "evidence_ref": "/tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md"
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null
  },
  "open_questions": [
    {
      "id": "Q-001",
      "question": "OPEN-01: какой инструмент и какие choiceId приходят в живом approval/request на wonder при --disable-write --disable-shell; закрывается аудит-логом первого живого хода, селективная политика после этого отдельным решением; после сбора payload владельцу отдельно ставится вопрос селективного deny при protectedWrite/judgeEscalated (FU-003 в этом delta отклонён с обоснованием в AD-002)",
      "blocking": false
    },
    {
      "id": "Q-002",
      "question": "OPEN-02: зависимость net-timeout от effort и размера промпта на выборке больше пяти точек бенча; проектирование идёт без привязки к размеру",
      "blocking": false
    },
    {
      "id": "Q-003",
      "question": "OPEN-03: сбрасывают ли idle-watchdog клиента DSH SSE-комментарии на сессиях дольше 600 с; в этом пакете keepalive остаётся пустыми data-чанками, вопрос нужен только для будущего перехода на комментарии",
      "blocking": false
    },
    {
      "id": "Q-004",
      "question": "OPEN-04: приходят ли summary.N по ходу хода на effort=max и за сколько секунд до конца; закрывается до реализации AD-004 дешёвым спайком VER-013 (этап 3 стартует только при PASS), затем диагностикой VER-011 на живых ходах. При ответе «только в конце» AD-004 не реализуется, REQ-MUSE-004 остаётся NOT_MET и пакет возвращается владельцу",
      "blocking": false
    },
    {
      "id": "Q-005",
      "question": "OPEN-05: семантика after N provider attempts и конфигурируемые ключи повторов CLI, приход turn/modelRetryScheduled на живом ходе 1.4.8; мост ограничивается своими 2 повторами и логированием",
      "blocking": false
    },
    {
      "id": "Q-006",
      "question": "OPEN-06: гасит ли turn/cancel pending approval и как модель ведёт себя после denied; пакет от ответа не зависит — локальный исход фиксирует терминальное защёлкивание AD-002, очистку гарантирует grace 15 с с убийством группы",
      "blocking": false
    },
    {
      "id": "Q-007",
      "question": "OPEN-08: источник net-timeout между ProxyRack, форвардером :10816 и стороной Meta; вне моста, на выбор повтора не влияет",
      "blocking": false
    },
    {
      "id": "Q-008",
      "question": "OPEN-09: политика закрепления версии Muse CLI при автообновлении лаунчера; мост только логирует версию и деградирует по AD-006",
      "blocking": false
    },
    {
      "id": "Q-009",
      "question": "FU-002: разрешает ли владелец обход серверного approval_mode_ceiling (-32030) клиентским approve поверх promptUnmatched; до явного разрешения AD-006 уводит такие ходы в exec-fallback, разрешение потребует записи в owner-decisions, ADR 0003 новой материализацией и delta AD-006",
      "blocking": false
    },
    {
      "id": "Q-010",
      "question": "PF-a2-001: принимает ли владелец семантику at-least-once для действий модели без наблюдаемых сигналов ради повтора транзиентного net-timeout ПОСРЕДИ хода (после записи turn/start) и для exec-попыток? По умолчанию (безопасно) НЕТ: область повтора pre-action, посреди хода net-timeout терминален — REQ-MUSE-003 закрывает только пре-турновые сбои (RISK-009). «Да» включается переключателем MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=observed-items (AD-003) после записи решения в owner-decisions и закрытия ASM-010; решение относится и к уже унаследованному контекстному повтору AD-005",
      "blocking": false
    }
  ],
  "deferred": [
    "селективная политика approval по собранным живым payload (deny по toolName, subject.kind, protectedWrite, judgeEscalated) отдельным решением владельца после OPEN-01 (FU-003)",
    "обход approval_mode_ceiling клиентским approve только по явному решению владельца (Q-009, FU-002)",
    "exec как последний шаг approval-деградации при срабатывании измеримого условия пересмотра по логу approval_degraded (FU-004)",
    "переход keepalive на SSE-комментарии : keepalive и правка формулировки README после живой проверки OPEN-03",
    "live-стрим content с потоковым разбором tool-разметки уровня droid-моста",
    "проброс turn/modelRetryScheduled клиенту отдельным сигналом вместо только лога",
    "закрепление версии Muse CLI против автообновления лаунчера (OPEN-09)",
    "env-переопределение остальных констант повторов, границ approval и grace; режим approval вынесен в AD-007 (FU-011)",
    "глобальный cooldown или circuit breaker повторов, если наблюдение QA-009 в эксплуатации покажет рост нагрузки вопреки удерживаемым слотам (FU-010)",
    "расширение области автоматического повтора на сбои после записи turn/start и на exec: переключатель observed-items только по решению владельца Q-010 после закрытия ASM-010 (журнал item kind, поля timeToFirstTokenMs/usage, подтверждение вендору порядка item/started и исполнения инструмента)",
    "exec с --approval-mode never вместо --yolo как безопасный fallback при denyUnmatched — после отдельной пробы семантики и решения владельца (AD-006)",
    "режим approval из ~/.dsh/.env вместо plist — после проверки, что start.sh подгружает env-файл (AD-007)"
  ],
  "delta_a2": {
    "from_packet_sha256": "ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22",
    "panel_verdict_ref": ".ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/verdict-a1.md",
    "findings_ledger_ref": ".ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/findings-ledger.md",
    "rework_brief_ref": ".ai-team/runs/muse-wonder-approval-20261015/handoff/panel-rework-brief-arch-a1.json",
    "spec_path": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md",
    "delta_doc": ".ai-team/runs/muse-wonder-approval-20261015/architecture/delta-a2.md",
    "items": [
      {
        "id": "RW-001",
        "source_findings": [
          "F-001"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "AD-003",
          "BND-002",
          "BND-003",
          "VIEW-001",
          "VIEW-002",
          "VER-002",
          "EVD-023"
        ],
        "verification_ids": [
          "VER-002",
          "VER-001"
        ],
        "tests": [
          "T-R06"
        ],
        "note": "Единый предикат допуска любого нового процесса в AD-003/BND-003; exec-fallback только до принятого turn/start и до approval-трафика, после — EOF/ошибки чтения/записи stdin/таймаут терминальны без exec с ровно одним исходом; противоречие счётчика снято: fallback расходует дедлайн и лимит процессов и проходит тот же предикат"
      },
      {
        "id": "RW-002",
        "source_findings": [
          "F-002"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "QA-003",
          "QA-004",
          "BND-003",
          "VER-002",
          "VER-010",
          "EVD-025"
        ],
        "verification_ids": [
          "VER-002",
          "VER-010"
        ],
        "tests": [
          "T-R08"
        ],
        "note": "Абсолютный дедлайн TIMEOUT_S=1800 с от приёма запроса включает ожидание слота, попытки, fallback, паузы, grace и cleanup; ожидание слота и новая попытка обрываются за 30 с до дедлайна, запас до клиентских 1900 с — 100 с при значениях по умолчанию; потолок записан одинаково в AD-003 и QA-004"
      },
      {
        "id": "RW-003",
        "source_findings": [
          "F-003"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "THREAT-004",
          "QA-005",
          "ASM-010",
          "BND-002",
          "BND-003",
          "VER-002"
        ],
        "verification_ids": [
          "VER-002",
          "VER-003"
        ],
        "tests": [
          "T-R07"
        ],
        "note": "Выбран запрет повтора после наблюдаемого начала потенциально неидемпотентного инструмента: барьер item kind вне reasoning/agentMessage, approval/userInput трафик, любой decide, непустой текст exec; митигация THREAT-004 переписана без опоры только на флаги и смерть группы, ненаблюдаемый остаток — ASM-010 с планом закрытия; at-least-once не принята и AD-001 не покрывается"
      },
      {
        "id": "RW-004",
        "source_findings": [
          "F-004"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-004",
          "BND-002",
          "BND-004",
          "QA-006",
          "THREAT-003",
          "VER-003",
          "EVD-024"
        ],
        "verification_ids": [
          "VER-003"
        ],
        "tests": [
          "T-L08"
        ],
        "note": "LIVE_WRITE_TIMEOUT_S=3 с на кадр механизмом settimeout под _wlock с восстановлением, как в droid-мосте (EVD-015, EVD-024); таймаут/частичная запись — зависший клиент: live выключена, соединение разорвано без гарантии [DONE], группа убита, слот свободен в пределах предела плюс подтверждение смерти; очередь-писатель отклонена в альтернативах AD-004"
      },
      {
        "id": "RW-005",
        "source_findings": [
          "F-005",
          "F-012"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-004",
          "BND-004",
          "CD-001",
          "QA-006",
          "RISK-003",
          "VER-003"
        ],
        "verification_ids": [
          "VER-003"
        ],
        "tests": [
          "T-L06",
          "T-L07"
        ],
        "note": "Префикс-монотонная публикация: стримится только прирост summary.0 до заморозки (первая дельта индекса больше 0, item/completed reasoning или конец хода), финал доотдаёт хвост только при F.startswith(P), при расхождении дубль запрещён и расхождение логируется; F-012 закрыт этим же решением как duplicate_of F-005"
      },
      {
        "id": "RW-006",
        "source_findings": [
          "F-006"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "BND-002",
          "QA-001",
          "ASM-006",
          "VER-001"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [
          "T-A13"
        ],
        "note": "Терминальное защёлкивание отказа: предел 10 decide включает финальный abort/denied, одиннадцатого нет; после защёлкивания новых разрешений и повторных деградаций нет, локальный неуспешный исход не меняют повторный request, terminal=false, успешный terminal и молчание сервера; ровно один терминальный исход без exec во всех ветках"
      },
      {
        "id": "RW-007",
        "source_findings": [
          "F-007"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "VER-009",
          "VER-011",
          "RISK-007",
          "QA-006",
          "AD-004",
          "ASM-004"
        ],
        "verification_ids": [
          "VER-009",
          "VER-011",
          "VER-003"
        ],
        "tests": [],
        "note": "VER-009 разделён: успешная приёмка только при реальном pre-terminal приросте reasoning в DSH-слоте; диагностическое закрытие OPEN-04 вынесено в VER-011, ветка «либо лог фиксирует конец» из PASS убрана, при summary только в конце REQ-MUSE-004 равен NOT_MET/BLOCKED"
      },
      {
        "id": "RW-008",
        "source_findings": [
          "F-011"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "THREAT-003",
          "ASM-006",
          "QA-001",
          "QA-004",
          "VER-001"
        ],
        "verification_ids": [
          "VER-001",
          "VER-002"
        ],
        "tests": [
          "T-A09b"
        ],
        "note": "APPROVAL_CANCEL_GRACE_S=15 с после turn/cancel или decide(abort/denied), затем убийство группы serve, один терминальный исход и освобождение слота без ожидания 1800 с; pending approval внутри grace команд не получает, влияние cancel на него опорой не является"
      },
      {
        "id": "FU-001",
        "source_findings": [
          "F-008"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "THREAT-001",
          "AD-002",
          "RISK-001",
          "VER-009"
        ],
        "verification_ids": [
          "VER-001",
          "VER-009"
        ],
        "tests": [],
        "note": "Журнал назван аудитом решений моста по остаточным запросам; полный аудит инструментов не обещается, тяжёлый gate отдельно фиксирует ходы с запросом и без него"
      },
      {
        "id": "FU-002",
        "source_findings": [
          "F-009"
        ],
        "disposition": "accepted_without_owner_permission_path",
        "changed_ids": [
          "AD-006",
          "QA-008",
          "RISK-005",
          "VER-001",
          "Q-009"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [
          "T-A11"
        ],
        "note": "Выбран путь без разрешения на обход: при -32030 клиентское автоодобрение не включается, ход уходит в один exec-fallback до turn/start с warning; обход ceiling допустим только по будущему явному решению владельца Q-009 с записью в ADR 0003 новой материализацией"
      },
      {
        "id": "FU-003",
        "source_findings": [
          "F-010"
        ],
        "disposition": "rejected_with_rationale",
        "changed_ids": [
          "AD-002",
          "BND-001",
          "Q-001"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [],
        "note": "Deny при protectedWrite/judgeEscalated отклонён в этом delta: payload и семантика полей не наблюдались, judge в serve отключён, write отключён хостом, исход после denied неизвестен с риском цикла; признаки логируются, правило — отдельным решением владельца по payload; тест T-A12 поэтому не вводится"
      },
      {
        "id": "FU-004",
        "source_findings": [
          "F-013"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "RISK-004"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [],
        "note": "Альтернатива exec последним шагом деградации добавлена в AD-002 и отклонена из-за барьера RW-003; потеря исхода принята с измеримым условием пересмотра по логу approval_degraded, исторические 27 переходов spark отнесены к старому ServeUnavailable без разрешений моста"
      },
      {
        "id": "FU-005",
        "source_findings": [
          "F-014"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "AD-004",
          "QA-005",
          "VER-011"
        ],
        "verification_ids": [
          "VER-002",
          "VER-011"
        ],
        "tests": [],
        "note": "Альтернатива повтора с подавлением префикса добавлена в AD-003 и AD-004 и отклонена (нет гарантии общего префикса второй генерации); метрика доли «первая дельта раньше сбоя» считается по логам первой дельты и retry_blocked в VER-011"
      },
      {
        "id": "FU-006",
        "source_findings": [
          "F-015"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "QA-004",
          "AD-003",
          "VER-002",
          "VER-010"
        ],
        "verification_ids": [
          "VER-002"
        ],
        "tests": [],
        "note": "Числа приведены к одним: run_attempt не более 3 без контекстного повтора и не более 4 с ним (1 + 1 + 2) в AD-003, QA-004, VER-002 и VER-010"
      },
      {
        "id": "FU-007",
        "source_findings": [
          "F-016"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "protected_paths",
          "VER-012",
          "VER-005",
          "BND-005"
        ],
        "verification_ids": [
          "VER-012",
          "VER-005"
        ],
        "tests": [],
        "note": "protected_paths расширен точными файлами ruff.toml, pyrightconfig.json, ADR 0001 и 0002, корневого server.py; правки тестов ограничены явным списком в BND-005 и VER-005, проверка diff — VER-012"
      },
      {
        "id": "FU-008",
        "source_findings": [
          "F-017"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "evolution.rollout",
          "VIEW-004",
          "RISK-006",
          "BND-005",
          "VER-012"
        ],
        "verification_ids": [
          "VER-012",
          "VER-005"
        ],
        "tests": [],
        "note": "Шаг 0 rollout: baseline REQ-MUSE-001 отдельным коммитом до правок REQ-MUSE-002..004, diff baseline..HEAD содержит только новую дельту"
      },
      {
        "id": "FU-009",
        "source_findings": [
          "F-018"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "BND-001",
          "THREAT-002",
          "QA-002",
          "AD-002",
          "VER-001"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [
          "T-A10"
        ],
        "note": "toolName и choiceId в аудите только из [A-Za-z0-9_.:-] до 64 символов, список choiceId до 8, остальное redacted с длиной и sha256-префиксом; канарейка choiceId дословно в bridge.log не попадает, сырые значения в команде decide не меняются"
      },
      {
        "id": "FU-010",
        "source_findings": [
          "F-019"
        ],
        "disposition": "accepted_with_justified_refusal_of_breaker",
        "changed_ids": [
          "RISK-002",
          "AD-003",
          "THREAT-003",
          "QA-009",
          "VER-002"
        ],
        "verification_ids": [
          "VER-002"
        ],
        "tests": [
          "T-R09"
        ],
        "note": "Добавлены анализ и QA-009 «серия net-timeout под двумя ходами»; глобальный cooldown/circuit breaker отклонён с обоснованием: слот удерживается весь ход, параллельная нагрузка не растёт выше 2, длительность ограничивают паузы и абсолютный дедлайн; потолок заново не определяется и ссылается на RW-002"
      },
      {
        "id": "FU-011",
        "source_findings": [
          "F-020"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-007",
          "AD-002",
          "BND-001",
          "evolution.rollback",
          "VER-001"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [
          "T-A14"
        ],
        "note": "Введён env-переключатель MUSE_BRIDGE_APPROVAL_MODE (allowAll по умолчанию, denyUnmatched) новым AD-007; смена режима — env и перезапуск без правки кода, фиксация в ADR 0003 новой материализацией"
      },
      {
        "id": "FU-012",
        "source_findings": [
          "F-021"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "VER-002"
        ],
        "verification_ids": [
          "VER-002"
        ],
        "tests": [
          "T-R01"
        ],
        "note": "Источник транзиентного текста указан явно: serve — turn/completed.error с проверкой error.kind и error.message, exec — stderr; T-R01 требует фикстуру реальной формы serve-терминала с маркером в error.message из лога"
      }
    ]
  },
  "delta_a3": {
    "from_packet_sha256": "c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e",
    "panel_verdict_ref": ".ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/a2/verdict-a2.md",
    "findings_ledger_ref": ".ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/a2/findings-ledger.md",
    "rework_brief_ref": ".ai-team/runs/muse-wonder-approval-20261015/handoff/panel-rework-brief-arch-a2.json",
    "spec_path": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md",
    "delta_doc": ".ai-team/runs/muse-wonder-approval-20261015/architecture/delta-a3.md",
    "items": [
      {
        "id": "F-001",
        "rework_id": "RW-001",
        "ledger": "a2",
        "source_findings": [
          "F-001"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "ASM-010",
          "THREAT-004",
          "QA-003",
          "QA-005",
          "BND-002",
          "BND-003",
          "RISK-009",
          "Q-010",
          "EVD-028",
          "EVD-029",
          "VER-002",
          "VER-010",
          "VER-009"
        ],
        "verification_ids": [
          "VER-002",
          "VER-010",
          "VER-009"
        ],
        "tests": [
          "T-R07 (переписан)",
          "T-R07b",
          "T-R06 (расширен)",
          "T-R01 (пре-турновый)"
        ],
        "note": "Ненаблюдаемый барьер заменён позитивным доказательством: ACTION_POSSIBLE защёлкивается до записи turn/start (serve) и при старте процесса (exec); после него повтор и fallback запрещены при любой ошибке; область по умолчанию pre-action, опциональная observed-items (at-least-once) только по решению владельца Q-010. Цена честно названа: REQ-MUSE-003 закрывает только пре-турновые сбои (RISK-009). Контекстный повтор AD-005 сохранён с барьером наблюдаемой активности (do_not_change), остаток унаследован и записан в ASM-010"
      },
      {
        "id": "F-002",
        "rework_id": "RW-002",
        "ledger": "a2",
        "source_findings": [
          "F-002"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-004",
          "BND-004",
          "QA-006",
          "THREAT-003",
          "RISK-011",
          "EVD-030",
          "VER-003"
        ],
        "verification_ids": [
          "VER-003"
        ],
        "tests": [
          "T-L08a",
          "T-L08b (keepalive блокируется первым)",
          "T-L08c (терминальная выдача)"
        ],
        "note": "Единый предел LIVE_WRITE_TIMEOUT_S=3 с на вызов _sse_write: ожидание _wlock (acquire с остатком) и запись одним бюджетом для всех писателей; правка одной точки; зависший клиент — существующий путь _client_gone и killpg; _content_started в той же критической секции"
      },
      {
        "id": "F-005",
        "rework_id": "RW-003",
        "ledger": "a2",
        "source_findings": [
          "F-005"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-006",
          "AD-007",
          "QA-008",
          "BND-003",
          "RISK-010",
          "THREAT-001",
          "evolution.rollback",
          "EVD-029",
          "VER-001",
          "VER-008",
          "VER-010"
        ],
        "verification_ids": [
          "VER-001",
          "VER-008",
          "VER-010"
        ],
        "tests": [
          "T-A11b",
          "T-A14 (матрица режим × пре-турновый сбой)"
        ],
        "note": "При denyUnmatched exec (всегда --yolo) не запускается ни как fallback, ни как повтор; предикат допуска exec в единственной точке run_attempt; терминальный исход 502/SSE error с причиной exec_fallback_disabled; allowAll сохраняет один пре-турновый exec; область переключателя записана в AD-006, AD-007, evolution.rollback и ADR 0003"
      },
      {
        "id": "F-003",
        "rework_id": "FU-001",
        "ledger": "a2",
        "source_findings": [
          "F-003"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "AD-003",
          "QA-001",
          "QA-004",
          "BND-002",
          "BND-003",
          "EVD-026",
          "ASM-012",
          "VER-001",
          "VER-002"
        ],
        "verification_ids": [
          "VER-001",
          "VER-002"
        ],
        "tests": [
          "T-A09c",
          "T-R10"
        ],
        "note": "E = D − FINISH_RESERVE_S (35 с = grace 15 + уборка 12 + два кадра по 3 с); grace по time.monotonic() от защёлкивания и включает попытку записи cancel/decide; CONTROL_WRITE_TIMEOUT_S=5 с; дедлайны на монотонных часах"
      },
      {
        "id": "F-004",
        "rework_id": "FU-002",
        "ledger": "a2",
        "source_findings": [
          "F-004"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-004",
          "CD-001",
          "BND-004",
          "RISK-003",
          "ASM-011",
          "VER-003",
          "VER-009"
        ],
        "verification_ids": [
          "VER-003",
          "VER-009"
        ],
        "tests": [
          "T-L07 (переписан)"
        ],
        "note": "При расхождении snapshot авторитетный F доходит до клиента целиком после разделителя (дублирование допустимо, потеря исключена); CD-001 переформулирован честно; частота расхождений измеряется (ASM-011)"
      },
      {
        "id": "F-006",
        "rework_id": "FU-003",
        "ledger": "a2",
        "source_findings": [
          "F-006"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "BND-002",
          "ASM-010",
          "THREAT-001",
          "RISK-001",
          "VER-001",
          "VER-009"
        ],
        "verification_ids": [
          "VER-001",
          "VER-009"
        ],
        "tests": [
          "T-A15"
        ],
        "note": "Журнал каждого item kind вне reasoning/agentMessage (kind и toolName по allowlist, без rawArgs), счётчик в итоговой строке хода, поля timeToFirstTokenMs/usage транзиентного терминала; выборка таких ходов в VER-009"
      },
      {
        "id": "F-007",
        "rework_id": "FU-004",
        "ledger": "a2",
        "source_findings": [
          "F-007"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-007",
          "evolution.rollback",
          "evolution.rollout",
          "VER-008",
          "EVD-027",
          "ASM-012"
        ],
        "verification_ids": [
          "VER-008"
        ],
        "tests": [],
        "note": "Точный механизм: правка EnvironmentVariables в plist + launchctl bootout/bootstrap (kickstart -k plist не перечитывает); учение allowAll → denyUnmatched → allowAll с проверкой approvalMode в bridge.log"
      },
      {
        "id": "F-008",
        "rework_id": "FU-005",
        "ledger": "a2",
        "source_findings": [
          "F-008"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-003",
          "QA-004",
          "BND-003",
          "ASM-012",
          "VER-002"
        ],
        "verification_ids": [
          "VER-002"
        ],
        "tests": [
          "T-R08 (порог 120 с)"
        ],
        "note": "MIN_ATTEMPT_REMAINING_S=120 с (env MUSE_BRIDGE_MIN_ATTEMPT_S) для старта из очереди и повтора; 30 с остаётся только окном handshake; формулировка соотношения D, E и клиентских 1900 с уточнена"
      },
      {
        "id": "F-011",
        "rework_id": "FU-006",
        "ledger": "a2",
        "source_findings": [
          "F-011"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "VER-001"
        ],
        "verification_ids": [
          "VER-001"
        ],
        "tests": [
          "T-A08 (параметризован)",
          "T-A13"
        ],
        "note": "Единое правило: любая ошибка approval/decide кроме -32051 и любая ошибка userInput/cancel защёлкивает деградацию; тесты по всем кодам [F-28]"
      },
      {
        "id": "F-013",
        "rework_id": "FU-007",
        "ledger": "a2",
        "source_findings": [
          "F-013"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "VER-013",
          "RISK-007",
          "Q-004",
          "AD-004",
          "evolution.rollout"
        ],
        "verification_ids": [
          "VER-013",
          "VER-011"
        ],
        "tests": [],
        "note": "Спайк тайминга первой summary-дельты (VER-013) — гейт перед реализацией AD-004 (этап 3); FAIL останавливает live и возвращает пакет владельцу"
      },
      {
        "id": "F-014",
        "rework_id": "FU-008",
        "ledger": "a2",
        "source_findings": [
          "F-014"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "EVD-015",
          "AD-004",
          "CD-001",
          "ASM-003"
        ],
        "verification_ids": [
          "VER-003"
        ],
        "tests": [],
        "note": "Формулировки о клиенте и keepalive приведены к статусу ASM-003 (ASSUMED) и фактам [F-18], [F-47]; «доказано» заменено на «по комментарию в коде»"
      },
      {
        "id": "F-015",
        "rework_id": "FU-009",
        "ledger": "a2",
        "source_findings": [
          "F-015"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "AD-002",
          "AD-003",
          "AD-004",
          "AD-006",
          "AD-007",
          "EVD-023",
          "EVD-024",
          "EVD-025"
        ],
        "verification_ids": [],
        "tests": [],
        "note": "Ссылки на находки панели a1 в тексте пакета переименованы в PF-a1-NNN; на находки a2 — PF-a2-F-NNN; голых F-NNN вне delta_a2 и delta_a3 нет (проверка поиском)"
      },
      {
        "id": "F-016",
        "rework_id": "FU-010",
        "ledger": "a2",
        "source_findings": [
          "F-016"
        ],
        "disposition": "accepted",
        "changed_ids": [
          "materialization[0]",
          "arch-spec.md (шапка, статус)",
          "delta-a3.md"
        ],
        "verification_ids": [
          "VER-012"
        ],
        "tests": [],
        "note": "Шапка спеки AD-001..AD-007, статус сверен с receipts/arch-gate-a2.json (PASS); sha materialization[0] пересчитан после правки proposal ADR 0003 и сверен read-back"
      },
      {
        "id": "F-009",
        "ledger": "a2",
        "source_findings": [
          "F-009"
        ],
        "disposition": "excluded_by_panel",
        "changed_ids": [],
        "verification_ids": [],
        "tests": [],
        "note": "WITHDRAWN invalid_after_recheck"
      },
      {
        "id": "F-010",
        "ledger": "a2",
        "source_findings": [
          "F-010"
        ],
        "disposition": "excluded_by_panel",
        "changed_ids": [],
        "verification_ids": [],
        "tests": [],
        "note": "WITHDRAWN duplicate_of F-002"
      },
      {
        "id": "F-012",
        "ledger": "a2",
        "source_findings": [
          "F-012"
        ],
        "disposition": "excluded_by_panel",
        "changed_ids": [],
        "verification_ids": [],
        "tests": [],
        "note": "WITHDRAWN invalid_after_recheck"
      },
      {
        "id": "F-017",
        "ledger": "a2",
        "source_findings": [
          "F-017"
        ],
        "disposition": "excluded_by_panel",
        "changed_ids": [],
        "verification_ids": [],
        "tests": [],
        "note": "WITHDRAWN invalid_after_recheck"
      }
    ]
  }
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ receipt-ARCH_GATE:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/arch-gate-a3.json sha256=48a0080ebf3f661ec31daa750d1ab44b22eea8565e888f7acddcd2b7eb6885f1
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "packet_sha256": "38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c",
  "verification_surface_sha256": "b3e1c7beacd1efc55a183920762f330d54f2dcc6f6d9e0634306aa70a4b70c6b",
  "protected_paths_sha256": "23b893508ca791df60756570bf930589bd15d122a3a0aa3dceb8d1b4952e58f6",
  "architect_worktree_sha256": "ed90872d5f4866e6dc5f6985e09b91076839b4427d88287e1e228f2e8da21463",
  "materialized_targets": 1
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ task-envelope:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/task.json sha256=92866d20c06c6c922397d3d52f2b7ca47edb5c1f1c42b608aeed616a35c3ad75
{
  "task_id": "REQ-MUSE-002",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "criticality_reason": "боевой мост DSH->Meta Muse (:9886), поведение ходов и протокол serve/exec, деплой через launchd",
  "title": "muse-bridge: не перезапускать ход с нуля при approval/request, ретрай net-timeout, живость долгих ходов Wonder",
  "requirement_ids": [
    "REQ-MUSE-002",
    "REQ-MUSE-003",
    "REQ-MUSE-004"
  ],
  "branch_policy": "не dev; ветка bugfix/muse-wonder-approval-retry-liveness (создаётся Coder-ом после арх-панели)",
  "base_sha": "1f1071a2330574bf90b53bbcaa65d3bf5bc29c2b",
  "downstream_panel": true,
  "parent_skill": "analyst-teamlead",
  "setup": "default",
  "contract_freeze": "внешний OpenAI-совместимый контракт моста (/v1/chat/completions, /health, /v1/models) не менять без явного пункта; допустимы только аддитивные SSE-кадры внутри существующих полей",
  "architecture_gate": {
    "packet_sha256": "38f4662021162360c22138888a86cc2d2156faba7b61ee95cda18468c952754c",
    "verification_surface_sha256": "b3e1c7beacd1efc55a183920762f330d54f2dcc6f6d9e0634306aa70a4b70c6b",
    "protected_paths_sha256": "23b893508ca791df60756570bf930589bd15d122a3a0aa3dceb8d1b4952e58f6"
  }
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ goal:
<<<ARTIFACT /tmp/cel-runs/muse-wonder-serve-approval/goal.md sha256=9618c6ffd31474be118c0a9b18a8e111ef907da35d53d378ace4bbea9493ab15
# ЦЕЛЬ (старт 2026-10-15 00:0x MSK)
Результат: muse-bridge (:9886, ~/work/src/cli-agent-bridge/bridges/muse-bridge/server.py) на моделях Wonder не теряет ход при `serve needs interaction (approval/request)` — не перезапускает его с нуля (exec-fallback = x2 времени + выброс 7 мин мышления) и не выглядит зависшим в DSH ("Deep diving 8m48s"), на длинной (>400k) сессии.
Критерий (тяжёлый путь): ПАНЕЛЬ ACCEPT (panel-proof.json PASS, pol-receipt/1) по коду + clean-room + ЖИВОЙ ход в DSH-слоте владельца (muse-wonder-full-1.0 Max, сессия «ai dizrapt»/длинная): ход завершается без fallback-рестарта с нуля, тайминги записаны; регрессий нет (67+ тестов).
Preset: «аналитик техлид» (default). Критичность: S2 (боевой мост) -> ДЕФОЛТ.
Ветка: НЕ dev (в dev не коммитить) -> bugfix/<...>.
Дедлайн: нет (доводить до победы).
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ owner-decision:
<<<ARTIFACT /tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md sha256=5596e64b9881b75cf8c938d5a0855339a8800c2965922eb74e32e0b472e87a05
2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)
2026-10-15 13:39 MSK | находки арх-панели F-002, F-003, F-004, F-006 (OBJECT автора при C1, PAUSED_OWNER) | владелец выбрал в чате по каждой: «blocking (Рекомендуется)» | опции: blocking / non-blocking / excluded | итог: все четыре blocking, входят в instructions для Architect delta

## Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2 (PAUSED_OWNER, ответы AskUserQuestion, явные)
- F-001 (барьер повтора / ненаблюдаемое действие, ASM-010 vs AD-003): **blocking**
- F-002 (таймаут live-записи после захвата _wlock, AD-004/BND-004): **blocking**
- F-003 (бюджет 1800 с без резерва на cleanup/выдачу, grace после cancel): **non-blocking** (учесть в брифе Coder)
- F-004 (потеря reasoning при расхождении snapshot, CD-001): **non-blocking** (учесть в брифе Coder)
- F-005 (откат denyUnmatched обходится exec --yolo, AD-006/AD-007): **blocking**
Итог: вердикт a2 = NEEDS WORK (3 blocking: F-001, F-002, F-005) → panel-rework-summarizer → Architect delta a3 (arch_panel_to_architect: использовано 1, будет 2 из 5).

## Решения оркестратора по директиве владельца «хватит спрашивать, делай сам как принято в индустрии» (2026-10-15 ~22:50 MSK) — вопросы Architect a3
- Q-010 (at-least-once для ненаблюдаемых действий): НЕТ. Принято решение Architect: по умолчанию `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=pre-action` (повтор только до записи `turn/start`). Переключение на `observed-items` — без изменения кода, только после живого аудита ASM-010 (закрытие тяжёлым путём) и отдельной записи здесь. Обоснование: неидемпотентные побочные эффекты по индустриальной практике не повторяют; write/shell отключены флагами serve (EVD-005), остаточный риск — web/MCP.
- Q-009 (обход -32030 клиентским approve): НЕТ (exec-fallback по AD-006, при denyUnmatched — без exec).
- Q-001 (selective deny по protectedWrite/judgeEscalated): после сбора живых payload; сейчас только логирование.
- Q-004 (summary только в конце хода): решается спайком VER-013 до реализации AD-004; при NOT_MET REQ-MUSE-004 сообщается как не выполнено.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ handoff:
<<<ARTIFACT ~/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/handoff-architect.md sha256=ba82e6a0d0400b86945e760269df8691329a7af87ef7511ae5a810b61a3e2c18
# Handoff архитектору: muse-wonder-approval-and-upstream-timeouts

## 1. Контекст и целевые требования (REQ-ID)

Настоящий пакет передаёт результаты системного анализа по теме `muse-wonder-approval-and-upstream-timeouts` для проектирования изменений в `bridges/muse-bridge/server.py` (ветка `dev`, репозиторий `/Users/aazhiry1/work/src/cli-agent-bridge`).

Целевые требования:
- **REQ-MUSE-002:** При получении `approval/request` или `userInput/request` от `muse serve` ход не должен перезапускаться с нуля через `muse exec` с потерей накопленного времени мышления [F-01], [F-02], [F-03], [F-06], [F-07].
- **REQ-MUSE-003:** Транзиентная ошибка транспорта `transport error [net-timeout]: timed out waiting for response data (meta stream)` не должна приводить к немедленному отказу хода без контролируемого повтора, когда повтор допустим [F-12], [F-13], [F-14].
- **REQ-MUSE-004:** Во время длительного мышления модели (`muse-wonder-full-1.0`, `effort=max`) клиент DSH по SSE должен получать признаки жизни и прогресса мышления в реальном времени, а не только буферизованный в конце хода блок `reasoning_content` [F-16], [F-17], [F-18], [F-19].

Требование **REQ-MUSE-001** (прунинг контекста 400k/320k/200k для чужих/длинных сессий) уже реализовано в рабочем дереве `bridges/muse-bridge/server.py` и подтверждено логами `context_prune` [F-07], в рамках данного пакета выступает как ограничение совместимости [F-49].

Владелец решений: пользователь aazhiry1. Глубина исследования: standard, шесть спайков INV-01..INV-06 закрыты, остаток записан как OPEN-NN (`open-questions.md`). Модельные ходы Meta в рамках анализа не запускались, кроме уже существовавших прогонов бенча [F-44].

## 2. Architecture drivers

Каждый драйвер выведен из фактов, выбор решения здесь не делается.

- **AD-1 (REQ-MUSE-002). Ход теряется целиком при любом запросе взаимодействия.** Единственная точка обработки `approval/request` и `userInput/request` безусловно бросает `ServeUnavailable` без ответа серверу, блок `finally` убивает группу процессов serve, накопленное состояние хода теряется, мост запускает `muse exec` с полным исходным промптом [F-01] [F-02] [F-03]. Цена: 275 с и 412 с мышления на wonder (повтор в exec: 455 с до net-timeout) [F-42] [F-07], до 1521 с повтора на spark [F-41].
- **AD-2 (REQ-MUSE-002). Протокол даёт клиенту управление approval, мост им не пользуется.** Сервер ждёт решения клиента: ответ на запрос только подтверждает показ, решение идёт командой `approval/decide` с `choiceId`, `requirementId`, `commandId` [F-23] [F-28]; режим approval выбирается клиентом при `session/start` или `session/setApprovalMode` из четырёх значений [F-29] [F-32]. Мост не передаёт `approvalMode` и работает на серверном default `promptUnmatched` [F-08] [F-30].
- **AD-3 (REQ-MUSE-002). Комментарий моста о потолке режима не подтверждён.** Комментарий в `server.py:1824-1829` утверждает, что любой явный `approvalMode` отвергается `approval_mode_ceiling`. На 1.4.7 и 1.4.8 при флагах моста все четыре режима приняты, отказ -32030 есть в логе только на 1.4.2 [F-30] [F-31].
- **AD-4 (REQ-MUSE-002). Причина approval не известна.** Payload запроса не логируется, каталог инструментов без хода не получен; неизвестно, какой инструмент вызвал approval на wonder при `--disable-write --disable-shell` [F-04] [F-37]. Схема допускает subject видов shell, fileAccess, network, unixSocket, process, tool [F-26].
- **AD-5 (REQ-MUSE-002). Общий путь для spark и wonder.** 27 из 29 переходов в exec приходятся на muse-spark-*, код не ветвится по модели; любое изменение обработки approval затрагивает оба семейства [F-40].
- **AD-6 (REQ-MUSE-003). Мост не ретраит net-timeout.** Повтор в exec срабатывает только по подстроке `network connection could not be opened`; `net-timeout` помечен как не повторяемый [F-12]. Ошибка приходит как stderr CLI, место её определения в мосте отсутствует [F-45].
- **AD-7 (REQ-MUSE-003). Сбои не коррелируют с размером промпта и effort на имеющейся выборке.** Бенч: 800 KB на max прошёл за 281.3 с, 800 KB на high упал за 31.5 с; короткие сбои на 20 с встречаются и на effort=low, и на max без prune [F-44] [F-43]. Внешний слой нестабилен: в логе форвардера прокси 3893 повтора для api.meta.ai [F-46].
- **AD-8 (REQ-MUSE-003). Повтор ограничен состоянием SSE.** Прошлый цикл закрепил правило: повтор допустим до первого контентного кадра, после первой дельты запрещён [F-49]. Новый live-стрим (AD-9) меняет эту границу.
- **AD-9 (REQ-MUSE-004). Клиент видит только пустые data-чанки.** SSE открывается до запуска serve, затем каждые 15 с идёт data-чанк с пустым `content`; summary.N накапливаются в памяти и выдаются одним куском после хода [F-16] [F-17]. Тесты закрепляют отсутствие `: keepalive` в теле [F-20].
- **AD-10 (REQ-MUSE-004). Эталон live-стрима есть в соседнем мосте.** Droid-мост отдаёт `content` и `reasoning_content` дельтами с коалесценцией 40 мс, таймаутом записи 3 с и SSE-комментарием `: keepalive` [F-18].
- **AD-11 (REQ-MUSE-004). Реакция клиента неизвестна.** Документации DSH о idle-watchdog нет; единственные клиентские параметры: `timeoutMs` и `streamIdleTimeoutMs` по 1900000 мс, `maxRetries: 0` [F-19] [F-47]. Мост проверен только на ~600 с по комментарию кода [F-47].
- **AD-12 (REQ-MUSE-003 и REQ-MUSE-004). Версия 1.4.8 добавляет наблюдаемость повторов провайдера.** Уведомление `turn/modelRetryScheduled` сообщает о паузе повтора до завершения хода [F-36].
- **AD-13 (все REQ). Среда меняется под ногами.** Лаунчер Muse CLI автообновился с 1.4.7 до 1.4.8 в 2026-10-15 05:29 MSK; схемы совпадают по approval и методам [F-36].

## 3. As-is границы

Границы системы и потоки (каждый поток привязан к факту):

- DSH (клиент, OpenAI-совместимый, SSE) → muse-bridge `:9886` (`bridges/muse-bridge/server.py`) по HTTP `POST /v1/chat/completions` [F-19] [F-16]. Клиентские таймауты 1900000 мс, повторов клиента нет [F-19].
- muse-bridge → `muse serve` (stdio, JSON-RPC, MSP), один процесс на запрос с флагами `--disable-write --disable-shell --trust-workspace --no-session-log`, сессия не сохраняется [F-09] [F-02]. Запросы: `initialize`, `initialized`, `session/start`, `turn/start` [F-08].
- muse-bridge → `muse exec` (CLI, прямой путь и fallback) с флагами `--yolo --disable-web-tools --disable-reminders`; exec запускается с полным промптом через `--prompt-file` [F-09] [F-03].
- `muse` → Meta API через обёртку `muse-cli.sh` и форвардер прокси `127.0.0.1:10816` → верхний прокси ProxyRack. Внешний слой, вне контроля моста [F-46] [F-22].
- Деплой: репозиторий `bridges/muse-bridge/server.py` и копия в `~/.dsh/bridges/muse-bridge/server.py` побайтово идентичны; процесс под launchd `com.user.dsh-muse-bridge` [F-21] [F-51].
- Параллелизм: `MAX_CONCURRENT=2`, ожидание слота до 1800 с, затем HTTP 503 [F-21].

Внутри границы моста: сборка argv, цикл чтения serve без idle-таймаута (тишина до дедлайна 1800 с), `SERVE_SPAWN_TIMEOUT_S=30 с` на рукопожатие, повтор exec по сетевой подстроке, повтор по hard threshold с прунингом [F-15] [F-12] [F-49].

Вне границы: логика approval-судьи Meta (в serve отключена, в exec включена по умолчанию, в мосте подавлена `--yolo`) [F-11], политика прокси, UI DSH.

## 4. Контракты (инвентарь, только факты)

### 4.1 MSP (serve, JSON-RPC по stdio)

- Версия схемы: отпечаток 1.4.7 `sha256:6de32db08bbb` (совпадает с логом моста); 1.4.8 по методам и approval идентична, 69 методов, добавлено уведомление `turn/modelRetryScheduled` [F-22] [F-25] [F-36].
- Серверные запросы, требующие ответа: `approval/request`, `userInput/request`; результат RequestReceipt (пустой объект) [F-23].
- Серверные уведомления: `approval/requested`, `approval/updated`, `approval/resolved`, `userInput/requested`, `userInput/settled`, `session/approvalModeChanged` [F-24].
- Клиентские команды: `approval/decide`, `approval/listPending`, `session/setApprovalMode`, `userInput/answer|cancel|clarify|interrupt`, `turn/cancel`, `turn/interrupt`, `turn/steer` [F-25].
- `approval/decide`: обязательные `approvalId`, `choiceId`, `commandId`, `requirementId`, `sessionId`; результат `status=accepted` и `terminal`; при `terminal=false` придёт обновлённый `approval/request` [F-28].
- Ошибки: -32050 approvalNotFound, -32051 approvalAlreadyResolved, -32052 approvalChoiceInvalid, -32053 approvalRequirementStale, -32054 approvalReviewerUnavailable, -32030 commandRejected [F-28].
- Режимы: `allowAll`, `promptUnmatched`, `onRequest`, `denyUnmatched` (закрытый enum); default при отсутствии поля и при `null` — `promptUnmatched`; смена режима действует со следующего действия и не решает ожидающий approval [F-29] [F-30] [F-32].
- Способы прекратить ожидание: `approval/decide` с решением `denied` или `abort`, `turn/cancel`, `turn/interrupt`; «отклонить без решения» по проводу отсутствует; влияние отмены хода на pending approval не описано [F-23] [F-33].
- Данные хода: `item/delta` (поле `field`, например `summary.0`), `turn/completed` с `terminal`, `error`, `usage`, `timeToFirstTokenMs` [F-35].
- Внешний источник сообщает для 1.3.0, что serve не завершает ожидание решения по таймеру (проверено 360 с); для 1.4.x это не проверялось [F-39].

### 4.2 OpenAI-совместимый SSE моста (`:9886`)

- При `stream:true` HTTP 200 `text/event-stream` и role-кадр отправляются до ожидания слота и запуска serve; признак жизни: data-чанк `{"content": ""}` каждые 15 с (`MUSE_BRIDGE_KEEPALIVE_S`) [F-16].
- После хода: один кадр `reasoning_content`, затем `tool_calls`, `content` кусками около 300 символов, `finish_reason`, `usage`, `[DONE]` [F-17].
- Ошибка после начала SSE уходит кадром `error` и `[DONE]`, частичный текст отбрасывается [F-17] [F-12].
- Клиентский контракт DSH: `api: openai-completions`, `supportsReasoningEffort: true`, окна wonder 400000 токенов [F-19].
- Эталон live-контракта: droid-мост `:9882` (дельты `content` и `reasoning_content`, комментарий `: keepalive`, таймаут записи 3 с) [F-18].

### 4.3 Режимы отказа (as-is)

| Ситуация | Поведение |
|---|---|
| `approval/request` или `userInput/request` | `ServeUnavailable`, serve убивается, exec с нуля [F-01] [F-02] [F-03] |
| net-timeout в exec | ошибка клиенту, повтора нет [F-12] |
| сетевая подстрока «could not be opened» в exec | один повтор exec [F-12] |
| hard threshold контекста | прунинг и один повтор до первого контентного кадра [F-49] |
| клиент отключился | процесс убивается, fallback не запускается [F-03] |

## 5. NFR-набросок (фактические значения)

Baseline-значения для quality scenarios:

- Serve-ход wonder без approval: 8-94 с на коротких промптах (24 хода), 205-237 с на длинных [F-43].
- Serve-ход wonder до approval: 275 с и 412 с [F-42].
- Повтор в exec после approval на wonder: 455 с до net-timeout при промпте 768118 символов; в первом инциденте 2242 с до отключения клиента при промпте 1326216 символов [F-07] [F-06].
- Net-timeout на wonder: 20 с (effort=low и effort=max), 452 с с текстом «after 2 provider attempts» [F-43].
- Бенч exec на wonder: 100 KB за 51.1 с, 400 KB за 251.2 с, 800 KB за 281.3 с (max); 1200 KB упал за 236.1 с (сетевой отказ после 5 попыток провайдера); 800 KB на high упал за 31.5 с [F-44]. Выборка пять точек (OPEN-02).
- Интервал признаков жизни клиенту: 15 с, пустой data-чанк; шаг прогресса reasoning: ни одного до конца хода [F-16] [F-17].
- Клиентские таймауты DSH: 1900000 мс общий и idle; повторов нет [F-19]. Таймаут хода моста 1800 с, повтор exec получает полный таймер заново [F-15].
- Квота: 2 одновременных запуска [F-21].
- Живой сбой serve 2026-10-15 00:10:10: 20 с до net-timeout при том, что короткий exec `PONG` на тот же слот проходит [F-43] [F-46].

Риски (для `risks`):
- R-1: ответ на approval без знания запрошенного действия (OPEN-01, OPEN-07).
- R-2: повтор поверх повторов провайдера CLI (OPEN-05) увеличивает время сбоя; в бенче видны попытки 3/4 и 4/4 [F-44].
- R-3: live-стрим меняет границу безопасного повтора (AD-8) [F-49].
- R-4: незакоммиченные изменения моста и тестов (+2941 строк) и совпадение копии с репозиторием делают откат единственной точкой возврата [F-51].
- R-5: изменение затрагивает spark (27 из 29 случаев) [F-40].
- R-6: смена версии CLI вне контроля моста [F-36] (OPEN-09).

## 6. Ограничения изменения и откат

- Тесты, закрепляющие текущее поведение, потребуют решения: `test_approval_falls_back_to_exec_without_decide` (нет `approval/decide`, переход в exec), `test_s1_data_ticks_before_done_preserve_content_and_tools` (нет `: keepalive` в теле), `test_t18_...`, `test_t27_...`, класс R4 [F-20] [F-52]. Теста на долгую тишину до approval нет [F-52].
- Прогон тестов: 67 passed на старте анализа; команда `uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py` (из брифа).
- Каталоги вне зоны: профили DSH `~/.dsh/profiles/{web,desktop}/cordis.patch.yml`; не трогать `muse-spark-*` без явной причины [F-21] [F-19].
- Деплой по плану прошлого цикла: резервная копия, правка репозитория и тестов, копия в `~/.dsh/bridges/muse-bridge/`, перезапуск launchd, проверка `/health` и `/v1/models`; откат возвратом резервной копии и перезапуском [F-51] [F-49].
- Сдача по канону владельца требует проверки на живой работе (дёрнуть ход wonder большого размера), а не только тестов; модельные ходы выполняет исполнитель после решения архитектора.

## 7. Расхождения с исходными допущениями (обратный канал)

- Комментарий `server.py:1824-1829` о том, что явный `approvalMode` отвергается потолком, не воспроизведён на 1.4.7 и 1.4.8 [F-30] [F-31]. Влияет на формулировку REQ-MUSE-002, не меняет его.
- Число approval-переходов в логе 29, а не 30 [F-05]; число методов схемы 69, а не 68 [F-25].
- README репозитория описывает keepalive как SSE-комментарий, код шлёт пустые data-чанки [F-48]. Влияет на REQ-MUSE-004.
- Эталон внешнего проекта (1.3.0) утверждает, что запрос `approval/request` не приходит; на 1.4.7 мост получил именно этот метод [F-39].

## 8. Blocking open questions

- **OPEN-07 (БЛОКЕР):** политика approval для неинтерактивного моста (авторазрешение, отказ или передача решения пользователю DSH). Блокирует выбор решения по REQ-MUSE-002; ветки REQ-MUSE-003 и REQ-MUSE-004 продолжаются независимо.

## 9. Assumptions (OPEN-NN МОЖНО ПРОДОЛЖИТЬ)

- ASM-01 (OPEN-01): запросить approval может любой не отключённый флагами serve инструмент; мост получает логирование безопасных полей params (toolName, subject.kind, protectedWrite, judgeEscalated, список choiceId и decision) без rawArgs.
- ASM-02 (OPEN-02): net-timeout не зависит от размера и effort в пределах бенча; проектирование повтора без привязки к размеру.
- ASM-03 (OPEN-03): клиент опирается на `streamIdleTimeoutMs=1900000`; паттерн droid-моста применим к DSH.
- ASM-04 (OPEN-04): summary.N могут приходить по ходу хода; проверка добавлением отметок времени.
- ASM-05 (OPEN-05): повторы CLI независимы от повторов моста; повтор моста ограничивается малым числом попыток; `turn/modelRetryScheduled` наблюдается через логирование.
- ASM-06 (OPEN-06): `approval/decide` с решением `denied` допускает продолжение хода, при отсутствии прогресса ход завершается `turn/cancel`.
- ASM-07 (OPEN-08): net-timeout внешний транзиентный фактор; повтор логируется.
- ASM-08 (OPEN-09): схемы 1.4.7 и 1.4.8 эквивалентны по approval и протоколу; `serverInfo.version` проверяется при каждом старте.

## 10. Feasibility-заключение по направлениям (без выбора)

Варианты, которые допускают факты; выбор принадлежит архитектору.

| Направление | Вариант | Факты | Вердикт |
|---|---|---|---|
| REQ-MUSE-002 | ответ на `approval/request` командой `approval/decide` | [F-23] [F-28] | выполнимо с условиями: нужен `choiceId` из `availableChoices`, payload неизвестен (OPEN-01, OPEN-07) |
| REQ-MUSE-002 | явный `approvalMode` при `session/start` | [F-29] [F-30] | выполнимо: все четыре режима приняты на 1.4.7 и 1.4.8; последствия режима для хода не наблюдались (OPEN-01, OPEN-07) |
| REQ-MUSE-002 | `session/setApprovalMode` после старта | [F-32] | выполнимо: принят, действует со следующего действия, ожидающий approval не решает |
| REQ-MUSE-002 | `turn/cancel` или `turn/interrupt` вместо exec с нуля | [F-33] | выполнимо с условиями: влияние на pending approval не описано (OPEN-06); отмена хода сама не сохраняет мышление |
| REQ-MUSE-003 | ограниченный повтор net-timeout в мосте | [F-12] [F-44] [F-49] | выполнимо с условиями: до первого контентного кадра, учёт повторов провайдера (OPEN-05), граница повтора зависит от выбора по REQ-MUSE-004 |
| REQ-MUSE-004 | live-доставка `reasoning_content` по `item/delta` | [F-17] [F-18] [F-35] | выполнимо с условиями: время прихода summary.N не установлено (OPEN-04) |
| REQ-MUSE-004 | SSE-комментарий `: keepalive` вместо пустого data-чанка | [F-18] [F-20] [F-47] | выполнимо с условиями: реакция клиента не проверена (OPEN-03), текущий тест закрепляет обратное |
| REQ-MUSE-004 | событие `turn/modelRetryScheduled` как признак жизни | [F-36] | выполнимо с условиями: только 1.4.8, на живом ходе не наблюдалось (OPEN-05) |

## 11. Маппинг в architecture-packet.json

- `evidence`: ссылки [F-01]..[F-52] из `evidence-ledger.md`.
- `blocking open questions`: OPEN-07.
- `assumptions`: ASM-01..ASM-08 (OPEN-01..06, 08, 09).
- `boundaries/contracts`: разделы 3 и 4.
- `quality scenarios`: раздел 5 (baseline).
- `risks`: R-1..R-6 раздела 5.
- Трассировка: REQ-MUSE-002 → AD-1..AD-5; REQ-MUSE-003 → AD-6..AD-8, AD-12; REQ-MUSE-004 → AD-9..AD-12.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ ledger:
<<<ARTIFACT ~/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/evidence-ledger.md sha256=30d1e4b815b0ff0c7d6446b09704ae87684e2e2a4b1703d480630799f7ee89b6
[F-01] В bridges/muse-bridge/server.py единственная точка обработки approval/request и userInput/request в ServeRun.execute (_handle_event) безусловно выбрасывает ServeUnavailable без отправки JSON-RPC ответа | bridges/muse-bridge/server.py:1757-1762 (Explorer A [A-01][A-03]) | 2026-10-15
[F-02] При выбросе ServeUnavailable блок finally в ServeRun.execute вызывает self.close() и убивает процесс-группу muse serve, теряя накопленные final_text, deltas, summary_parts, summaries, usage, turn_id и session_id | bridges/muse-bridge/server.py:1748-1755,1945-1948 (Explorer A [A-04][A-05]) | 2026-10-15
[F-03] При перехвате ServeUnavailable в run_attempt мост (если клиент не отключился) логирует fallback и запускает новый процесс muse exec с полным исходным промптом attempt_prompt с нуля (via=exec-after-serve-fallback) | bridges/muse-bridge/server.py:2400-2446 (Explorer A [A-06][A-14]) | 2026-10-15
[F-04] Параметры события approval/request (какой инструмент или разрешение запрошено) нигде в мосте не логируются и не сохраняются: в лог и исключение попадает только имя метода | bridges/muse-bridge/server.py:1761-1762,2429 (Explorer A [A-07]) | 2026-10-15
[F-05] В логе bridge.log зафиксировано ровно 29 строк serve needs interaction (approval/request): 27 на моделях muse-spark-* и 2 на muse-wonder-full-1.0 (effort=max); число 30 из отчёта Explorer B не воспроизведено | grep -c 'serve needs interaction' bridge.log дал 29, grep по wonder дал 2 (строки 1034 и 1249); сумма по версиям 2+8+17+2=29 (Explorer D [D-32]) | 2026-10-15
[F-06] В инциденте 2026-10-13 23:20:04 ход muse-wonder-full-1.0 (effort=max) в serve через 275 с получил approval/request (23:24:39), перезапустился в exec (prompt_chars=1326216) и через 2242 с завершился отключением клиента (client gone) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1034-1042 (Explorer B [B-08][B-09]) | 2026-10-15
[F-07] В инциденте 2026-10-14 23:50:43 ход muse-wonder-full-1.0 (effort=max, после context_prune 408666->319789 токенов) через 412 с получил approval/request (23:57:35), перезапустился в exec (prompt_chars=768118) и через 455 с упал в 00:05:10 с ошибкой transport error [net-timeout]: timed out waiting for response data (meta stream) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1243-1252 (Explorer A [A-08][A-09], Explorer B [B-08][B-10][B-11]) | 2026-10-15
[F-08] При вызове session/start мост передаёт только commandId, workspaceRoot, providerId="meta", modelId и не передаёт поле approvalMode | bridges/muse-bridge/server.py:1824-1829 (Explorer A [A-10][A-31], Explorer B [B-06]) | 2026-10-15
[F-09] Флаги запуска muse serve в мосте: --disable-write --disable-shell --trust-workspace --no-session-log --provider meta --model <id>; при этом в muse exec дополнительно передаются --yolo --disable-web-tools --disable-reminders | bridges/muse-bridge/server.py:1380-1401,1648-1659 (Explorer A [A-12][A-15]) | 2026-10-15
[F-10] В CLI muse 1.4.7-R6101.1 подкоманда muse serve --help не имеет флагов --approval-mode, --yolo, --disable-approval, --approval-judge, --permission-profile, --disable-web-tools, --disable-reminders; режим подтверждения в serve выбирается только по протоколу MSP | muse-cli.sh serve --help / muse-cli.sh exec --help (Explorer B [B-17][B-18][B-19]) | 2026-10-15
[F-11] В соответствии с публичным тикетом meta-models/muse-code-sdk#80 в режиме muse serve встроенный LLM approval judge отключён (outcome="disabled", reason="setting_off"), тогда как в muse exec он по умолчанию включён (--approval-judge on) и дополнительно в мосте подавлен флагом --yolo | https://github.com/meta-models/muse-code-sdk/issues/80 (Explorer B [B-15][B-25]) | 2026-10-15
[F-12] В bridges/muse-bridge/server.py сетевой повтор в exec срабатывает только по подстроке NETWORK_RETRY_MARKER = "network connection could not be opened"; ошибка "transport error [net-timeout]: timed out waiting for response data (meta stream)" имеет retryable=False и мостом не ретраится | bridges/muse-bridge/server.py:114,2435-2445 (Explorer A [A-21]) | 2026-10-15
[F-13] В логе bridge.log ошибка net-timeout на muse-wonder-full-1.0 зафиксирована как на коротких интервалах ~20 с (2026-10-14 13:04:34 effort=low; 2026-10-15 00:10:10 effort=max без prune), так и на длинных ходах 452 с (2026-10-14 20:39:01 с текстом "after 2 provider attempts") и 455 с (2026-10-15 00:05:10 в exec-fallback) | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1250-1252 (Explorer B [B-13]) | 2026-10-15
[F-14] В бенчмарке /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv на muse-wonder-full-1.0 промпты 100 KB (51.1 с), 400 KB (251.2 с) и 800 KB (281.3 с) на effort=max прошли с rc=0, а промпт 1200 KB (max) упал за 236.1 с с ошибкой "network connection could not be opened within 15 seconds (after 5 provider attempts)" и повторный прогон 800 KB (high) упал за 31.5 с с ошибкой "transport error [net-timeout]: timed out waiting for response data (meta stream)" | /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv:1-6 | 2026-10-15
[F-15] Таймаут хода в мосте задаётся MUSE_BRIDGE_TIMEOUT_S = 1800 с (и для serve, и для exec отдельно; при fallback на exec таймер 1800 с стартует заново); таймаут инициализации serve SERVE_SPAWN_TIMEOUT_S = 30.0 с; отдельного idle-таймаута чтения в цикле serve нет | bridges/muse-bridge/server.py:65,138,1455-1460,1696-1725 (Explorer A [A-16][A-17][A-18][A-19][A-20]) | 2026-10-15
[F-16] При stream:true мост сразу (до ожидания слота и запуска serve) отправляет HTTP 200 text/event-stream, стартовый role-чанк и запускает поток _keepalive_loop, который каждые KEEPALIVE_S = 15 с шлёт SSE data-чанк с пустой дельтой {"content": ""}, а не SSE-комментарий ": keepalive" | bridges/muse-bridge/server.py:1185,2034-2070 (Explorer A [A-24][A-25], Explorer C [C-11][C-12]) | 2026-10-15
[F-17] Во время выполнения хода в serve дельты item/delta с полями summary.N накапливаются в памяти (summary_parts / summaries) и не отправляются клиенту до завершения ServeRun.execute; после окончания хода _send_sse отправляет весь reasoning_content одним чанком и затем режет финальный content по ~300 символов | bridges/muse-bridge/server.py:1781-1796,1890-1895,2170-2198 (Explorer A [A-27], Explorer C [C-13]) | 2026-10-15
[F-18] В соседнем droid-мосте (/Users/aazhiry1/work/src/cli-agent-bridge/server.py, порт :9882) реализована live-отправка SSE-дельт content и reasoning_content через sse_writer с коалесценцией ~40 мс и таймаутом записи LIVE_WRITE_TIMEOUT_S = 3 с, а также keepalive в виде SSE-комментария ": keepalive\n\n" каждые 15 с | /Users/aazhiry1/work/src/cli-agent-bridge/server.py:130,134-137,4894-4926,5118-5157 (Explorer C [C-15][C-16]) | 2026-10-15
[F-19] В профилях клиента DSH (web и desktop cordis.patch.yml) для провайдера muse-bridge заданы api: openai-completions, timeoutMs: 1900000, streamIdleTimeoutMs: 1900000, retryPolicy: {mode: normal, maxRetries: 0}, supportsReasoningEffort: true | /Users/aazhiry1/.dsh/profiles/web/cordis.patch.yml:426-437, /Users/aazhiry1/.dsh/profiles/desktop/cordis.patch.yml:327-338 (Explorer C [C-01][C-02]) | 2026-10-15
[F-20] Существующие тесты в tests/test_muse_bridge_killpg.py жёстко проверяют текущее поведение: test_approval_falls_back_to_exec_without_decide проверяет отсутствие approval/decide в rpc.jsonl и переход в exec при approval/request, а test_s1_data_ticks_before_done_preserve_content_and_tools проверяет отсутствие b": keepalive" в SSE-теле | tests/test_muse_bridge_killpg.py:1182-1185,1278-1305 (Explorer A [A-25][A-36]) | 2026-10-15
[F-21] Лимит параллельных запусков моста MAX_CONCURRENT = 2 (ожидание слота до TIMEOUT_S = 1800 с, далее HTTP 503); деплой-копия /Users/aazhiry1/.dsh/bridges/muse-bridge/server.py побайтово идентична репозиторной bridges/muse-bridge/server.py и управляется launchd-агентом com.user.dsh-muse-bridge | bridges/muse-bridge/server.py:66,2375-2384 (Explorer A [A-22][A-40], Explorer C [C-19][C-33]) | 2026-10-15
[F-22] Схема MSP экспортируется офлайн командой schema generate-json-schema --out DIR (и generate-ts); отпечаток схемы 1.4.7 sha256:6de32db08bbb совпадает со строкой serve init в bridge.log; повторный экспорт 1.4.8 дал msp.schema.json и manifest.json в стабильной поверхности | muse-cli.sh schema generate-json-schema --out /tmp/sa-verify/s: wrote manifest.json, msp.schema.json (stable surface); /tmp/cel-runs/muse-wonder-serve-approval/explorer-D-msp-approval.md D-01 | 2026-10-15
[F-23] Сервер шлёт клиенту ровно два запроса, требующих ответа: approval/request и userInput/request; результат обоих RequestReceipt (пустой объект) означает только «показано», решение идёт отдельной клиентской командой approval/decide или userInput/answer; ошибка или обрыв соединения оставляют запрос pending и он переиздаётся при следующем subscribe; отклонить без решения по проводу нельзя | python3 -I: sorted(requests) в /tmp/sa-verify/s/msp.schema.json дал approval/request, userInput/request; $defs.RequestReceipt.description (Explorer D D-02 D-03) | 2026-10-15
[F-24] Уведомления сервера по approval и userInput: approval/requested, approval/updated, approval/resolved, userInput/requested, userInput/settled, session/approvalModeChanged; мост обрабатывает по имени метода только approval/request и userInput/request и не реагирует на approval/requested | schema notifications (Explorer D D-04 D-21); bridges/muse-bridge/server.py:1761-1762 | 2026-10-15
[F-25] Клиентские методы approval и ввода: approval/decide, approval/listPending, session/setApprovalMode, userInput/answer, userInput/cancel, userInput/clarify, userInput/interrupt, turn/cancel, turn/interrupt, turn/steer, turn/start, session/start; всего 69 методов и в схеме 1.4.7, и в схеме 1.4.8 (число 68 из отчёта Explorer D не воспроизведено); метода перечисления инструментов нет | python3 -I: len(methods)=69 для обеих схем, symmetric difference множеств методов пуст; /tmp/cel-runs/muse-wonder-serve-approval/explorer-D/schema-json/msp.schema.json | 2026-10-15
[F-26] ApprovalRequestParams содержит обязательные approvalId, availableChoices, currentRequirementId, itemId, judgeEscalated, protectedWrite, rawArgs, sessionId, sourceRange, subject, taskId, toolCallId, toolName, turnId, viewCursor; subject.kind принимает значения shell, fileAccess, network, unixSocket, process, tool | схема $defs.ApprovalRequestParams (строка 277 в файле 1.4.7) и $defs.ApprovalSubject (строка 572) (Explorer D D-06 D-37) | 2026-10-15
[F-27] ApprovalChoice содержит choiceId (произвольная строка без enum), decision, label, scope, acceptsFeedback, rulePreview; enum ApprovalDecision (открытый): approved, approvedForSession, approvedPolicyAmendment, denied, deniedPolicyAmendment, timedOut, abort; конкретные значения choiceId на живом ходе не получены | схема $defs.ApprovalChoice, ApprovalDecision (строки 87 164 в файле 1.4.7) (Explorer D D-07 D-35) | 2026-10-15
[F-28] ApprovalDecideParams требует approvalId, choiceId (из текущих availableChoices, иначе -32052), commandId (UUIDv7), requirementId (равен currentRequirementId, устаревший даёт -32053), sessionId; результат содержит status accepted и признак terminal (false означает что придёт обновлённый approval/request); коды ошибок: -32050 approvalNotFound, -32051 approvalAlreadyResolved, -32052 approvalChoiceInvalid, -32053 approvalRequirementStale, -32054 approvalReviewerUnavailable, -32030 commandRejected | схема $defs.ApprovalDecideParams, ApprovalDecideResult и список errors (Explorer D D-08 D-09 D-11) | 2026-10-15
[F-29] ApprovalMode задан закрытым enum allowAll, promptUnmatched, onRequest, denyUnmatched; поле session/start.approvalMode принимает значение enum либо null; при отсутствии поля и при явном null сервер выбирает собственный default; session/start описан как единственная поверхность, объявляющая политику неинтерактивного запуска | python3 -I: $defs.ApprovalMode.enum в /tmp/sa-verify/s/msp.schema.json дал allowAll, promptUnmatched, onRequest, denyUnmatched; $defs.SessionStartParams.properties.approvalMode.description (Explorer D D-12 D-13) | 2026-10-15
[F-30] На serve 1.4.8 при аргументах моста (--disable-write --disable-shell --trust-workspace --no-session-log) session/start без approvalMode вернул эффективный режим promptUnmatched с source startup; на 1.4.7 и 1.4.8 явные allowAll, promptUnmatched, onRequest, denyUnmatched приняты и вернулись как эффективные режимы; на 1.4.7 так же принят null | python3 -I /tmp/cel-runs/muse-wonder-serve-approval/explorer-D/poc_session_start.py omitted (мой прогон, 1.4.8, 1.96 с, stderr пуст); probe-null.json probe-promptUnmatched.json probe-onRequest.json в той же папке (Explorer D D-24..D-29) | 2026-10-15
[F-31] Отказ -32030 approval_mode_ceiling в bridge.log встречается только на serve 1.4.2 (2026-10-05 11:44:20 и 11:45:13), на 1.4.3 1.4.4 1.4.6 1.4.7 таких строк нет; на 1.4.7 и 1.4.8 явный approvalMode не отвергнут, поэтому комментарий моста server.py:1824-1829 о том что любое явное значение отвергается не подтверждён на этих версиях | bridge.log строки 260 и 267; PoC probe-*.json (Explorer D D-30 D-31); bridges/muse-bridge/server.py:1824-1829 | 2026-10-15
[F-32] session/setApprovalMode после старта принял все четыре режима подряд, включая повышение до allowAll, с applyOutcome completed и source approvalReconfigure; по описанию схемы смена режима действует со следующего действия и не решает уже ожидающий approval ретроактивно | мой прогон poc_session_start.py omitted на 1.4.8 (четыре ответа status accepted); $defs.SessionSetApprovalModeParams/Result (Explorer D D-14 D-33) | 2026-10-15
[F-33] Способы прекратить ожидающий approval по проводу: approval/decide с выбором decision denied или abort, turn/cancel {commandId, sessionId, turnId?}, turn/interrupt {commandId, sessionId, turnId?, retract?} (ход завершён когда пришёл turn/completed с terminal cancelled); влияние turn/cancel и turn/interrupt на запись pending approval в схеме не описано | схема $defs.TurnCancelParams, TurnInterruptParams, RequestReceipt (Explorer D D-15) | 2026-10-15
[F-34] Ввод пользователя: userInput/request несёт questions с options и selection, необязательный autoResolutionMs; ответ userInput/answer, отказ userInput/cancel, дополнение userInput/clarify, userInput/interrupt прерывает запрос и останавливает ход; исходы userInputOutcome: answered, cancelled, interrupted, clarified, timedOut, aborted | схема $defs.UserInputRequestParams (строка 8077) и UserInputOutcome (строка 8035) (Explorer D D-16) | 2026-10-15
[F-35] turn/completed несёт terminal (completed, failed, cancelled), необязательные durationMs, timeToFirstTokenMs, usage и error с kind, message, retryable, quota; item/delta несёт delta, itemId, sessionId, viewCursor и необязательный field (например summary.0, output); виды item включают reasoning, toolCall, webSearch, subagent, workflow, hookRun | схема $defs.TurnCompletedParams, ItemDeltaParams (строка 2474), ItemKind (Explorer D D-17 D-18) | 2026-10-15
[F-36] Лаунчер muse автообновился с 1.4.7 до 1.4.8-R6256.1 в 2026-10-15 05:29 MSK (бинарь 1.4.7 удалён); схемы 1.4.7 и 1.4.8 совпадают по методам, requests и определениям approval; 1.4.8 добавляет уведомление turn/modelRetryScheduled, описанное как наблюдаемая до завершения хода пауза провайдерского повтора модели с полями attempt, maxAttempts, retryDelayMs, errorKind | muse-cli.sh --version дал Muse Code 1.4.8 (1.4.8-R6256.1); python3 -I: turn/modelRetryScheduled in notifications True для 1.4.8, множества методов равны; $defs.TurnModelRetryScheduledParams.description | 2026-10-15
[F-37] Реальный payload approval/request (toolName, subject, choiceId) на живом ходе не получен; каталог инструментов без хода не найден: ни методы схемы, ни результат session/start, ни muse exec --help, ни model-profile show не перечисляют инструменты | Explorer D D-35 D-36 D-38; probe-*.json (поля session/start result); muse-cli.sh exec --help | 2026-10-15
[F-38] В muse serve --help нет флагов approval-mode, yolo, disable-approval, approval-judge, permission-profile, а ключей таймаутов и ретраев в тексте помощи нет: единственный универсальный флаг -c/--config KEY=VALUE (значения JSON); в muse exec --help есть --approval-mode untrusted/on-request/never, --approval-judge, --yolo, --disable-approval, --max-model-steps, --user-input-auto-resolve | muse-cli.sh serve --help: grep по config, timeout, retry нашёл только строку --config <KEY=VALUE>; muse-cli.sh exec --help: grep по timeout, retry, max-model-steps нашёл только --max-model-steps; Explorer D D-39 | 2026-10-15
[F-39] Публичное наблюдение стороннего проекта на Muse Code 1.3.0: approvals в serve приходят уведомлениями approval/requested, ответ клиента approval/decide с requirementId, варианты allow_once и abort, «Serve never times them out; tested for 360 s», совет «Never omit the mode: a durable host defaults to allowAll»; расхождение с 1.4.7: схема 1.4.7 содержит и запрос approval/request, и уведомления, а мост на 1.4.7 получил именно метод approval/request | https://github.com/kontourai/station/issues/2452 (Explorer B [B-27] и DISCREPANCY); схема 1.4.7 requests | 2026-10-15
[F-40] По версиям serve сбоев с передачей хода в exec по approval/request: 1.4.2 два, 1.4.3 восемь, 1.4.4 семнадцать, 1.4.7 два, 1.4.6 ноль; все 27 случаев на muse-spark-* и оба случая на muse-wonder-full-1.0 проходят один и тот же код ServeRun.execute без ветвления по модели | python3 -I скан bridge.log (Explorer D D-32); bridges/muse-bridge/server.py:1757-1762 | 2026-10-15
[F-41] Для 27 случаев на muse-spark-* исход выполнения после перехода в exec в таблице Explorer B: успешное завершение на интервале от 19 с до 1521 с, один обрыв по таймеру rc=-9 на 257 с, один ход до 1800 с с обрезкой, одно отключение клиента; повтор с нуля стоит до 25 минут | /tmp/cel-runs/muse-wonder-serve-approval/explorer-B-runtime-cli.md раздел B1 (строки таблицы по spark) | 2026-10-15
[F-42] Время serve-хода wonder до approval: 275 с (2026-10-13 23:20:04, approval в 23:24:39) и 412 с (2026-10-14 23:50:43, approval в 23:57:35), то есть пользователь теряет 4-7 минут мышления; других событий в логе между serve turn и approval нет кроме /health | /Users/aazhiry1/.dsh/bridges/muse-bridge/logs/bridge.log:1034 и 1243-1250 (мой повтор sed по строкам) | 2026-10-15
[F-43] Тайминги serve-ходов wonder в логе с 2026-10-13 без approval: 8-94 с на коротких промптах (24 хода) и 205 с, 232 с, 237 с на длинных; сбои net-timeout: 20 с (2026-10-14 13:04:34, effort=low), 452 с (2026-10-14 20:39:01, текст «after 2 provider attempts»), 20 с дважды в 2026-10-15 00:10:10 (effort=max, без prune) | /tmp/cel-runs/muse-wonder-serve-approval/explorer-B-runtime-cli.md B2 и B-13; bridge.log:1250-1252 | 2026-10-15
[F-44] Бенч exec на wonder: прогон 800 KB на effort=max прошёл за 281.3 с, а прогон 800 KB на effort=high упал за 31.5 с с net-timeout, то есть сбой не коррелирует с размером промпта и effort на этой выборке из пяти строк; в строке 1200 KB в stderr видны повторы потока модели «retrying meta model stream in 500ms (attempt 3/4)» и «(attempt 4/4)» перед финалом «after 5 provider attempts» | /tmp/cel-runs/muse-wonder-serve-approval/bench/results.tsv (cat, 5 строк данных, фоновый процесс завершён) | 2026-10-15
[F-45] Текст ошибки «timed out waiting for response data (meta stream)» в коде моста отсутствует: мост передаёт stderr CLI как есть и распознаёт только подстроку «network connection could not be opened»; значение формулировки «after N provider attempts» и ключ конфигурации таймаута провайдера в справке CLI и в мосте не найдены | grep -n по трём строкам net-timeout, timed out waiting, provider attempts в bridges/muse-bridge/server.py вернул пустой результат; bridges/muse-bridge/server.py:114 | 2026-10-15
[F-46] Форвардер прокси 127.0.0.1:10816 (общий для нескольких приложений) пишет в лог 151006 строк; повторы «retry … timed out» встречаются 26789 раз, из них для api.meta.ai:443 3893 повтора, повторов «incomplete SOCKS5 reply» 32; верхний прокси global.rotating.proxyrack.net | grep -c 'retry api.meta.ai', grep -c 'retry .*timed out', grep -c 'retry .*incomplete SOCKS5' и wc -l в /Users/aazhiry1/Library/Logs/Factory/proxyrack-forward.log | 2026-10-15
[F-47] Комментарий в коде моста фиксирует причину пустых data-чанков: OpenAI SDK в DeepSeek Harness ждал заголовков до своего таймаута около 600 с и обрывал долгий ход как Request timed out; влияние пустых чанков, reasoning_content и SSE-комментариев на idle-watchdog клиента pi-ai в документации DSH не найдено, требует живой проверки по докстрингу моста | bridges/muse-bridge/server.py:27-28,1182-1185 (Explorer C [C-09][C-10][C-07]) | 2026-10-15
[F-48] README репозитория утверждает что muse-мост держит соединение SSE-комментариями «: keepalive», код отправляет пустые data-чанки; README развёрнутой копии устарел (строки о non-stream JSON и отсутствии SSE) | /Users/aazhiry1/work/src/cli-agent-bridge/README.md:28-37 против bridges/muse-bridge/server.py:2064-2070 (Explorer C [C-30][C-31][C-32]) | 2026-10-15
[F-49] Прошлый прогон REQ-MUSE-001 зафиксировал в своём плане правило: повтор после ошибки допустим только до первого контентного кадра, а при добавлении live-стриминга повтор после первой дельты запрещён (_content_started); пруннинг и повтор по hard threshold реализованы в рабочем дереве (HARD_THRESHOLD_ERR_SUBSTR в server.py:87-88) | .ai-team/runs/muse-wonder-foreign-session-20261014/arch-spec.md:168-173 (Explorer C [C-22][C-23]); grep -n HARD_THRESHOLD_ERR_SUBSTR в server.py | 2026-10-15
[F-50] Решение прошлого цикла bridge-heal: обработку approval через approval/decide оставили закрытой («keep ServeUnavailable»): двухшаговый handshake, при отказе модель в serve может зациклить повторы; на тот момент форма параметров approval/request в мосте и тестах не была описана (фикстура теста шлёт params пустым объектом) | .ai-team/runs/muse-bridge-heal-20261014/context/open-questions.md:9 (Explorer A [A-13][A-33]); tests/test_muse_bridge_killpg.py:1012 | 2026-10-15
[F-51] Рабочее дерево ветки dev содержит незакоммиченные изменения моста и тестов (server.py +1018 строк, тесты +1983 строки; 2941 вставок, 60 удалений) и неотслеживаемые каталоги .ai-team/ и analysis/; деплой-копия побайтово идентична репозиторной; в каталоге деплоя лежит резервная копия server.py.bak-1791815617 | git diff --stat и git status --short в /Users/aazhiry1/work/src/cli-agent-bridge; cmp bridges/muse-bridge/server.py /Users/aazhiry1/.dsh/bridges/muse-bridge/server.py вернул IDENT; ls /Users/aazhiry1/.dsh/bridges/muse-bridge/ | 2026-10-15
[F-52] Тесты, закрепляющие поведение при ServeUnavailable: test_t18_serve_fallback_and_network_retry_preserve_context_retry_budget, test_t27_serve_unavailable_with_reflected_prompt_does_not_leak_to_log, класс R4 (клиент отключился при живом serve, exec не запускается); теста на долгую тишину перед approval нет, задержка в фикстуре только sleep | tests/test_muse_bridge_killpg.py:348-380,2068,2554,2585-2618,989-1021 (Explorer A [A-37][A-38][A-39]) | 2026-10-15
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ open-questions:
<<<ARTIFACT ~/work/src/cli-agent-bridge/analysis/muse-wonder-approval-and-upstream-timeouts/open-questions.md sha256=cb59a312a295701af488eef9c4c35094146696cfc0b41b2008fe7f8e6a88d2ff
OPEN-01 | МОЖНО ПРОДОЛЖИТЬ | Какой инструмент или действие модели muse-wonder-full-1.0 вызвало approval/request в ходах 2026-10-13 23:24:39 и 2026-10-14 23:57:35 при флагах --disable-write и --disable-shell, и какие choiceId приходят в availableChoices на живом ходе | Мост логирует только имя метода без params [F-04]; каталог инструментов без хода не получен, модельный ход в рамках анализа запрещён [F-37] | разработчик моста (добыча payload) / владелец | Без payload нельзя оценить безопасность авторазрешения и достаточность отключения web и reminders; поведение choiceId (allow_once, abort) подтверждено только внешним источником [F-39] | Принять что запросить approval может любой не отключённый флагами serve инструмент; добавить в мост логирование безопасных полей params (toolName, subject.kind, protectedWrite, judgeEscalated, список choiceId и decision) без rawArgs и секретов
OPEN-02 | МОЖНО ПРОДОЛЖИТЬ | Зависит ли net-timeout от effort и размера промпта | Бенч закончен на пяти строках: сбои не упорядочены по размеру (800 KB max прошёл, 800 KB high упал за 31.5 с) [F-44]; выборка мала для вывода о зависимости | владелец (разрешение на дополнительные ходы Meta) / аналитик | Решение о выборе порога повтора и о необходимости подрезки контекста под net-timeout опирается на малую выборку | Считать net-timeout не зависящим от размера и effort в пределах бенча; проектировать повтор без привязки к размеру промпта
OPEN-03 | МОЖНО ПРОДОЛЖИТЬ | Сбрасывают ли внутренний idle-watchdog клиента pi-ai в DeepSeek Harness пустые data-чанки, SSE-комментарии ": keepalive" или дельты reasoning_content на живой сессии дольше 600 с | Докстринг моста требует отдельной живой проверки в DSH [F-47]; документации клиента нет | владелец / разработчик | При несовпадении формата признаков жизни с ожиданиями клиента обрыв возможен раньше streamIdleTimeoutMs=1900000 [F-19] | Опираться на streamIdleTimeoutMs=1900000 и на проверенный паттерн droid-моста (live reasoning_content, комментарий keepalive) [F-18]
OPEN-04 | МОЖНО ПРОДОЛЖИТЬ | Когда в реальном времени серверу serve приходят item/delta с field summary.N и приходят ли они до конца хода на effort=max | В логе моста нет отметок времени первой дельты, дельты накапливаются в памяти и выводятся после хода [F-17]; живой ход не запускался | разработчик моста (временное логирование первой дельты) | Если summaries приходят только в конце хода, REQ-MUSE-004 по прогрессу мышления неисполним без другого источника признаков жизни | Принять что summary.N могут приходить по ходу хода (схема допускает item/delta без привязки к завершению) [F-35]; проверка добавлением отметок времени
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | Что означает «after N provider attempts» в ошибках CLI, есть ли конфигурируемые через --config ключи таймаута и числа повторов провайдера, и приходит ли turn/modelRetryScheduled на живом ходе 1.4.8 | В справке CLI таких ключей нет, в коде моста строка ошибки не определяется [F-38][F-45]; документации Meta по ключам нет | владелец / источник Meta | Без знания о повторах CLI мост может удвоить повторы поверх повторов провайдера (в строке бенча видны попытки 3/4 и 4/4) [F-44] | Считать повторы CLI независимыми от моста и ограничивать повтор моста малым числом попыток; наблюдать turn/modelRetryScheduled в serve 1.4.8 через логирование
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | Прекращает ли turn/cancel или turn/interrupt ожидающий approval и как ведёт себя модель после ответа denied (повторный запрос того же действия, зацикливание) | Схема не описывает влияние отмены на pending approval [F-33]; решение прошлого цикла ссылается на риск зацикливания при отказе [F-50]; живой ход не запускался | разработчик моста / владелец | Выбор ответа на approval определяет, сможет ли ход завершиться без перезапуска | Принять что approval/decide с decision denied допускает продолжение хода, а при отсутствии прогресса ход завершается turn/cancel
OPEN-07 | БЛОКЕР | Какую политику approval для неинтерактивного моста допускает владелец: авторазрешение, отказ, либо передача решения пользователю DSH | Это решение владельца о безопасности и о границах доступа модели; схема допускает все четыре режима [F-29][F-30], payload запроса неизвестен [F-37] | владелец | Любой выбор меняет поведение REQ-MUSE-002 и риск выполнения действий моделью | —
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | Где источник net-timeout: прокси ProxyRack, форвардер :10816 или сторона Meta | Нет сопоставления времён сбоев хода с событиями форвардера: форвардер общий для нескольких приложений [F-46], в логе моста нет идентификатора соединения | владелец (сеть) | Если источник вне моста, ограниченный повтор может не снизить долю сбоев | Считать net-timeout внешним транзиентным фактором; повтор в мосте ограничить и логировать
OPEN-09 | МОЖНО ПРОДОЛЖИТЬ | Как фиксировать версию Muse CLI, если лаунчер автообновляется (1.4.7 → 1.4.8 в 2026-10-15 05:29) | Автообновление выполняет лаунчер, бинарь прошлой версии удаляется [F-36]; политики закрепления версии в моём доступе нет | владелец | Схема MSP и поведение serve могут измениться между перезапусками моста; PoC-проверки фактов привязаны к версии | Считать схемы 1.4.7 и 1.4.8 эквивалентными по approval и протоколу [F-36]; проверять serverInfo.version из initialize при каждом старте
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ arch-spec:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md sha256=d7034e48dfff640e4d2e3d77dc3a458ae3cdcfebad197b8a21fc0ad85db4311a
# Архитектурная спецификация: muse-bridge — approval без перезапуска хода, повтор net-timeout, живость долгих ходов

Статус пакета: `APPROVED` (delta a3 после арх-панели cycle-1 прохода a2 NEEDS WORK: blocking F-001, F-002, F-005 по решению владельца 2026-10-15 ~18:15 MSK и follow-up F-003, F-004, F-006, F-007, F-008, F-011, F-013..F-016; трассировка — секции `delta_a3` и `delta_a2` пакета, `architecture/delta-a3.md` и `delta-a2.md`; `ARCH_GATE` a2 — PASS (`receipts/arch-gate-a2.json`), валидатор фазы approved для a3 зелёный, повторный `ARCH_GATE` по a3 и проход панели a3 впереди).
Пакет: `.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json`.
ADR политики: `architecture/proposals/docs/adr/0003-muse-serve-approval-allowall.md`
(материализация в `docs/adr/0003-muse-serve-approval-allowall.md` оркестратором после approval).
Нумерация: AD-001..AD-007, QA, BND, RISK, THREAT, VER — как в пакете; ссылки на находки арх-панели: `PF-a1-NNN` (проход a1) и `PF-a2-NNN` (проход a2), чтобы не путать с фактами `[F-NN]`; факты [F-NN] —
`analysis/muse-wonder-approval-and-upstream-timeouts/evidence-ledger.md`;
EVD-NNN — evidence пакета.

## 0. Вход и свежесть фактов

- Требования: REQ-MUSE-002 (ход не перезапускается при `approval/request` /
  `userInput/request`), REQ-MUSE-003 (транзиентный `net-timeout` /
  `transport_connect_unreachable` не доходит до пользователя провалом, если устраним
  ограниченным повтором), REQ-MUSE-004 (признаки жизни и прогресс мышления в SSE).
  Критичность S2: боевой мост `:9886` под launchd.
- REQ-MUSE-001 (прунинг 400k/320k/200k) уже в рабочем дереве и наследуется без
  пересмотра (AD-005).
- Открытый блокер аналитика OPEN-07 (политика approval) закрыт владельцем
  2026-10-15 05:44 MSK выбором `allowAll` (EVD-009, ASM-009 VALIDATED). Остальные
  OPEN-01..06, 08, 09 — класса «можно продолжить», оформлены ASM-001..008 и Q-001..008.
- Свежесть: факты ledger датированы 2026-10-15. Архитектор выборочно перепроверил по
  коду путь+символ факты F-01 (`server.py:1757-1762`), F-08/F-31 (`:1824-1829`),
  F-12 (`:114`, `:2438`), F-15 (`:65`, `:138`, `:1696`), F-16/F-17 (`:1185`,
  `:2064-2070`, `:2172-2175`), F-20 (тесты `:1181-1185`, `:1278-1305`), F-49
  (`:87-88`, `:2464`) — строки и поведение совпадают с ledger. Версия CLI на машине
  1.4.8-R6256.1 (`muse-cli.sh --version`, 2026-10-15).
- Проектных файлов правил (`AGENTS.md`, `.agents/`, `CLAUDE.md`) в репозитории нет;
  канон репозитория для этого изменения — сам код, `docs/adr/` (формат ADR-full
  0001/0002), `ruff.toml` (E4/E7/E9/F), `pyrightconfig.json` и прошлый пакет
  REQ-MUSE-001. `pyproject.toml` отсутствует, тесты запускаются через
  `uv run --no-project --with pytest`.

## 1. Контекст, фактическая система и замороженное

Фактический стек: один файл `bridges/muse-bridge/server.py` (2744 строки, stdlib,
`ThreadingHTTPServer`, потоки). Командное слоение Litestar/FastAPI из Python-overlay
к этому репозиторию не применяется; границы пакета описывают реальное устройство
(`Handler`, `ServeRun`, `Run`), новые слои и зависимости не вводятся.

Потоки as-is (каждый подтверждён evidence пакета):

```text
DSH (OpenAI SSE, timeout 1900 c, maxRetries 0)
  -> muse-bridge 127.0.0.1:9886 (Handler, MAX_CONCURRENT=2)
       -> ServeRun: muse serve по stdio MSP, процесс на запрос,
          --disable-write --disable-shell --trust-workspace --no-session-log
       -> Run (fallback и прямой путь): muse exec --yolo --disable-write
          --disable-shell --disable-web-tools --disable-reminders
  -> muse-cli.sh -> прокси 127.0.0.1:10816 -> ProxyRack -> Meta
```

Заморожено (AD-005): внешний контракт `/v1/chat/completions`, `/health`,
`/v1/models` (формы, коды, окна моделей); профили DSH; флаги безопасности обоих
путей; песочница включена (`--disable-sandbox` не появляется). Единственная
контрактная дельта — CD-001: фрагментация существующего `delta.reasoning_content`
на несколько кадров (§4). Поле `approvalMode` уходит только во внутренний MSP
между мостом и serve и клиенту не видно.

Измеренный baseline, на который опираются QA (без выдуманных NFR):

| Величина | Значение | Источник |
|---|---|---|
| Ход wonder до approval | 275 с, 412 с | EVD-003 |
| Повтор exec после approval | 455 с до net-timeout; 2242 с до client gone | EVD-003 |
| Net-timeout | 20 с (low и max), 452 с, бенч 31.5 с | EVD-011 |
| Успешные ходы бенча max | 100 KB 51.1 с; 400 KB 251.2 с; 800 KB 281.3 с | EVD-011 |
| Длинные serve-ходы wonder | 205 с, 232 с, 237 с | EVD-011 |
| Keepalive клиенту | пустой data-чанк каждые 15 с | EVD-014 |
| Дедлайн хода моста / handshake | 1800 с / 30 с | EVD-013 |
| Клиентские пределы DSH | 1900 с общий и idle, повторов нет | EVD-016 |
| Тестовый baseline | 67 passed; basedpyright 0 errors, 1448 warnings | task envelope |

## 2. REQ-MUSE-002: approval без перезапуска хода

Решения: AD-001 (политика, APPROVED владельцем), AD-002 (внутриходовая обработка, APPROVED),
AD-006 (потолок версии без обхода, APPROVED), AD-007 (env-переключатель режима, APPROVED). Границы: BND-001, BND-002.

### 2.1 Последовательность хода (VIEW-001)

```text
ServeRun: spawn serve (флаги без изменений)
  initialize -> лог serverInfo.version + schema fingerprint (уже есть)
  initialized (notify)
  session/start {commandId, workspaceRoot, providerId=meta, modelId,
                 approvalMode=<AD-007, по умолчанию "allowAll">}
    -> ошибка -32030: второго старта нет, ServeRun прерывается до turn/start
       с warning; allowAll — ровно один exec-fallback Handler (AD-006, без обхода
       потолка), denyUnmatched — терминальный отказ без exec (AD-006, AD-007)
    -> лог эффективного approvalMode из результата сессии
  turn/start -> главный цикл чтения до turn/completed или дедлайна хода
    approval/request (есть id):
      1) ответ {"id": <тот же id>, "result": {}}        (receipt, EVD-006)
      2) ApprovalPolicy(params) -> действие + аудит-запись
      3) approval/decide по действию; результат наблюдается в главном цикле
    approval/requested (нет id): тот же decide без receipt, дедупликация
    userInput/request: receipt -> userInput/cancel по политике
    turn/modelRetryScheduled: только лог (§4.3)
    item/delta summary.N: накопление + live-sink (§4)
```

### 2.2 Граница ApprovalPolicy (BND-001)

Чистое решение по снимку `params`, без I/O. Вход: поля снимка, которые политика
вправе читать (`approvalId`, `currentRequirementId`, `availableChoices`,
`sessionId`, `toolName`, `subject.kind`, `protectedWrite`, `judgeEscalated`;
для userInput — `userInputId`, `sessionId`, `toolName`). `rawArgs`, тела вопросов
и содержимое `subject` дальше `kind` политика не читает и никуда не пишет.
Выход — ровно одно действие:

- `approve(choiceId)` — выбор только из текущих `availableChoices`;
- `deny(choiceId)` — выбор с `decision` равным `abort` или `denied` (только ветка
  деградации §2.4);
- `cancel_user_input` — для `userInput/request`;
- `fail_turn` — разрешающего и отклоняющего выбора нет, транспорт завершает ход
  через `turn/cancel`.

Правило выбора разрешающего `choiceId` (детерминированно, по полю `decision`
каждого элемента `availableChoices`, не по строке `choiceId`):

1. первый выбор с `decision == "approved"`;
2. иначе первый с `decision == "approvedForSession"`;
3. `approvedPolicyAmendment` никогда не выбирается: смена политики выходит за
   решение владельца (EVD-009 фиксирует режим сессии, а не правку политики);
4. пустой или отсутствующий список, битый снимок — `fail_turn` ветки деградации.

Аудит-запись действия строится здесь же и содержит только: метод, `toolName`,
`subject.kind`, `protectedWrite`, `judgeEscalated`, список `choiceId` снимка,
выбранный `choiceId` и его `decision`, счётчик решения в ходе. Транспорт пишет её одной
строкой `_log` (редакция существующая). Свободные строки снимка рендерятся в лог
ограниченно (FU-009): `toolName` и каждый `choiceId` — только при `[A-Za-z0-9_.:-]`
и длине до 64, иначе `redacted` с длиной и префиксом sha256; список `choiceId`
обрезан 8 значениями. Команда `decide` получает сырые значения без изменений.
Approve политика выдаёт только при сконфигурированном `allowAll` (AD-007). Пример формы (значения иллюстративны):

```text
approval_decide tool=web_search subject=tool protected=0 judge=0 choices=[c1,c2] chosen=c1 decision=approved n=1
```

### 2.3 Транспорт decide в ServeRun (BND-002)

- Receipt: новый путь отправки ответа по серверному `id` дословно (тип id не
  преобразуется), тело `result: {}` (RequestReceipt, EVD-006). Ошибка записи после отправленного
  `turn/start` — терминальная деградация §2.4 без exec; до записи `turn/start` — транспортный
  `ServeUnavailable` ветки fallback §3.2. Классификацию (записан ли turn/start — ACTION_POSSIBLE, был ли
  approval-трафик, ошибка управляющей команды, защёлкнута ли деградация §2.4) ServeRun доводит до Handler,
  решение о новом процессе принимает только предикат BND-003.
- `approval/decide` параметры: `approvalId` и `sessionId` из снимка,
  `requirementId` — значение `currentRequirementId` снимка дословно (объект
  `{approvalId, sourceIndex}` по схеме, мост его не конструирует и не правит),
  `commandId` — существующий `_uuid7()`, `choiceId` — из политики. `feedback`
  не отправляется.
- Decide не ожидается рекурсивно внутри обработчика события: команда уходит,
  её `result`/`error` разбирает главный цикл по `rid` моста. Голые ack чужих rid
  по-прежнему игнорируются; `error` ожидающего decide ведёт в деградацию §2.4,
  кроме `-32051 approvalAlreadyResolved`, который логируется и ход продолжается
  (гонка request против requested). `result.terminal == false` ничего не требует:
  обновлённый `approval/request` придёт обычным событием и пройдёт тот же путь.
- Дедупликация: множество решённых пар (`approvalId`, дословное представление
  `currentRequirementId`) на ход. Повтор той же пары из `approval/requested`
  после `approval/request` второго decide не даёт.
- Критично: дедлайн записи в stdin. Сегодня `self._write_until` равен
  setup-дедлайну 30 с на весь `execute` (`server.py:1697-1698`), а approval в
  инцидентах приходил на 275 с и 412 с. После записи `turn/start` граница
  записи обязана стать дедлайном хода, иначе первый же decide упадёт в
  `ServeUnavailable` и вернёт exec-рестарт. Тест T-A07 (§6) это закрепляет.
- `userInput/request`: receipt, затем `userInput/cancel` с `commandId`,
  `sessionId`, `userInputId` из снимка. `userInput/interrupt` не применяется:
  по схеме он останавливает ход (EVD-006 через F-34), что противоречит REQ.
  Результат cancel наблюдается главным циклом так же, как decide.
- Уведомления `approval/updated`, `approval/resolved`,
  `session/approvalModeChanged`, `userInput/settled` только разбираются без
  действий (resolved допустимо логировать одной строкой без payload).

### 2.4 Границы цикла и деградация

На один ход: не более 10 `approval/decide` суммарно, **включая финальный
отказной decide**, и не более 3 `userInput/cancel` (константы модуля, §8).
Одиннадцатого decide не существует: при исчерпанном счёте деградация идёт сразу
через `turn/cancel`. Обоснование меры 10 как в a1: порядок выше единичного
наблюдения при жёстком пределе удержания слота; значение обратимо константой.

Терминальное защёлкивание отказа (RW-006, единое правило PF-a2-011). Триггеры: нет
разрешающего выбора; **любая** ошибка `approval/decide`, кроме benign `-32051`
(коды схемы `[F-28]`: `-32050`, `-32052`, `-32053`, `-32054 approvalReviewerUnavailable`,
`-32030 commandRejected`); **любая** ошибка `userInput/cancel`; превышение границы;
ошибка либо превышение предела записи stdin после отправленного `turn/start`. При первом триггере локальный исход хода
фиксируется неуспешным ровно один раз: при наличии выбора `abort`/`denied` и
свободном счёте уходит один такой decide, иначе один
`turn/cancel {commandId, sessionId, turnId}`. После защёлкивания: новых
разрешений и повторных входов в деградацию нет; дальнейшие `approval/request`
и `userInput/request` только логируются без команд; любой ответ сервера —
повторный request, `terminal=false`, успешный `turn/completed`, молчание —
локальный исход не меняет, поздний успешный текст отбрасывается, частичный
текст клиенту не уходит. Клиент получает ровно один терминальный исход
существующим форматом (502 или SSE error, один `[DONE]`). Влияние denied и
cancel на pending approval неизвестно (ASM-006) и опорой не служит.

Grace после деградации (RW-008, PF-a2-003): `APPROVAL_CANCEL_GRACE_S=15` с
(один интервал keepalive, входит в резерв §3.3) отсчитывается по `time.monotonic()` от момента
локального защёлкивания (`_approval_degraded=True`) и **включает саму попытку записи**
`turn/cancel` или отказного decide в stdin: запись ограничена остатком grace,
заблокированный stdin grace не продлевает. Запись любой управляющей команды (receipt,
decide, cancel) ограничена `CONTROL_WRITE_TIMEOUT_S=5` с (ASM-012) и остатком до
исполнительного дедлайна E; превышение защёлкивает деградацию. По истечении grace —
убийство группы процессов serve существующей механикой, терминальная ошибка,
освобождение слота. Ожидания дедлайна 1800 с ради слота здесь нет: два
проигнорировавших cancel (или заблокировавших stdin) хода мост целиком не блокируют.
Дедлайны ServeRun переводятся с `time.time()` на `time.monotonic()` (EVD-026).

Exec-рестарт по ветке деградации запрещён; альтернатива «exec последним шагом
деградации до `_content_started`» взвешена и отклонена в AD-002 (FU-004):
после approval-трафика ACTION_POSSIBLE §3.2 может быть уже защёлкнут.
Каждая деградация логируется `approval_degraded` с флагами `content_started`
и барьера активности — это измеримый вход условия её пересмотра.

Что меняется против a1 в fallback (RW-001, PF-a2-001): тихий exec fallback по
`ServeUnavailable` сохраняется **только до записи `turn/start`** (граница
`ACTION_POSSIBLE`, §3.2) и до любого approval-трафика (спавн, handshake,
`session/start`, EOF и RPC-ошибки setup, включая ветку `-32030` из AD-006) и только
если режим не `denyUnmatched` (PF-a2-005: exec всегда с `--yolo`, при `denyUnmatched` он
не запускается ни в какой роли — терминальный исход 502/SSE error с причиной
`exec_fallback_disabled`). После записи `turn/start` EOF, ошибка
чтения, ошибка записи stdin, дедлайн чтения и `turn/start` без ack — терминальные без exec;
`cancel` → EOF — ожидаемое подтверждение очистки, а не повод для fallback.
Ошибка модели (`terminal != completed`) по-прежнему не фолбэчится; при
ушедшем клиенте надзор убивает группу и ничего нового не стартует. Approval
во время setup-фазы (`await_result` маршрутизирует чужие сообщения в тот же
обработчик) проходит тот же путь: `sessionId` берётся из снимка, локальная
сессия моста может ещё не существовать.

## 3. REQ-MUSE-003: ограниченный повтор транзиентных сбоев

Решение AD-003 (APPROVED), граница BND-003. Внутренний однократный сетевой повтор внутри
exec-after-fallback (`server.py:2435-2445`, baseline REQ-MUSE-001) **упраздняется**: после
старта exec-процесса повтор запрещён (§3.2, ACTION_POSSIBLE); отдельного третьего пути повтора
не остаётся.

**Честная цена (a3, PF-a2-001, RISK-009).** Повтор допускается только там, где отсутствие
действия модели доказано: до записи `turn/start`. Посреди хода и на exec действие без
item/approval сигналов фактами не исключено (ASM-010), а семантика at-least-once владельцем
не принималась (THREAT-004). Поэтому наблюдавшиеся net-timeout длительностью до 452 с
(EVD-011) в области по умолчанию остаются терминальным отказом без повтора; REQ-MUSE-003
закрывается только для пре-турновых сбоев. Расширение — по решению владельца (Q-010).

### 3.1 Классификация (только явные маркеры)

Попытка считается транзиентно-транспортной, когда её сырой канал ошибки (до
редакции, как детектор hard threshold) содержит хотя бы одну подстроку:

| Маркер | Источник |
|---|---|
| `[net-timeout]` | лог и бенч (EVD-011) |
| `timed out waiting for response data` | лог и бенч (EVD-011) |
| `network connection could not be opened` | существующий `NETWORK_RETRY_MARKER` (EVD-010) |
| `transport_connect_unreachable` | текст REQ-MUSE-003; в логах на 2026-10-15 не засвидетельствован (grep пуст), тест синтетический |

Источник текста явный (FU-012): на serve для пре-турновых сбоев — текст ошибки setup (исключение ServeRun), а для терминала хода (используется только в области `observed-items`, §3.2 п.5) классификатор смотрит конкатенацию `turn/completed.error.kind` и `error.message` до редакции (поля схемы `[F-35]`), на exec — сырой stderr-канал ошибки; значения enum `kind` не выдумываются, маркеры ищутся в обоих полях. Классификатор — чистая проверка по образцу `_has_hard_threshold_marker`,
результат — флаг в словаре попытки по образцу `hard_threshold`. Поле
`retryable` ошибки serve само по себе класс не даёт: hard threshold тоже
`retryable=True` и принадлежит контекстному пути. Подстрока в обычном тексте
ответа при `rc == 0` повтор не запускает. Состояния `timeout`, `spawn_failed`,
`launcher_missing`, `client_gone` не повторяются при любом тексте: первое уже
исчерпало бюджет, остальные детерминистичны или бессмысленны без клиента.

### 3.2 Граница действия и условия допуска нового процесса (все одновременно)

**ACTION_POSSIBLE (PF-a2-001).** Флаг на попытку: serve — защёлкивается **до записи
первого байта `turn/start`** (не по ack: ack может потеряться, EVD-029); exec — при
успешном старте процесса с промптом. После защёлкивания любая ошибка попытки (EOF,
чтение, запись, дедлайн, `terminal=failed`, транзиентный маркер, пустой stdout, смерть
группы) флаг не снимает: отсутствие item/approval сигналов не доказывает отсутствия действия
(ASM-010). Любой допуск нового процесса в области по умолчанию требует, чтобы **ни одна**
прежняя попытка запроса не имела ACTION_POSSIBLE.

1. Попытка неуспешна и классифицирована транзиентной (§3.1) либо является пре-турновым
   сбоем serve; при этом не является hard threshold с доступным контекстным повтором
   (приоритет §3.3).
2. Транзиентных повторов в этом запросе было меньше 2 (отдельный счётчик запроса,
   не попытки). Внутренний serve→exec fallback счётчик не расходует только в
   до-турновой ветке, где исхода хода ещё не было, но проходит тот же предикат,
   тот же дедлайн и тот же лимит процессов — бесплатным он не является (RW-001).
3. Клиент на месте (`_client_gone` ложен и проба отрицательна) в момент решения
   и после паузы.
4. Контентные кадры не отправлялись: `_content_started` ложен. Пустые keepalive и
   role-кадр границей не являются; первая фактически отправленная live
   reasoning-дельта является (§4.2), буферизованная неотправленная — нет.
5. Область повтора (PF-a2-001, AD-003 п.4): по умолчанию `pre-action` — условие
   «нет ACTION_POSSIBLE у прежних попыток» (см. выше): новый процесс возможен только после
   сбоев до записи `turn/start` (spawn, handshake, `session/start`, до-турновый транспорт).
   Переключатель `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=observed-items` (читается при старте,
   невалидное значение останавливает старт) заменяет это условие барьером наблюдаемой
   активности a2: на serve не было `approval/request|requested`, `userInput/request`,
   отправленного decide и item с `kind` вне {`reasoning`, `agentMessage`} (ServeRun ведёт
   `kinds`, EVD-025), на exec результат не несёт текста и summaries — и тем самым **принимает
   at-least-once** для действий без наблюдаемых сигналов; включается только после записанного
   решения владельца (Q-010) и закрытия ASM-010; при старте warning, на каждый повтор — строка
   `retry_scope`. Approval-деградация не защёлкнута в обеих областях. Для exec-процесса
   дополнительно режим approval не `denyUnmatched` (§2.4).
6. Все группы процессов прежних попыток закрыты и `dead_confirmed` истинен;
   иначе действует существующий карантин слота, повтор не стартует.
7. Остаток до исполнительного дедлайна E (§3.3) не меньше `MIN_ATTEMPT_REMAINING_S=120` с
   (PF-a2-008); пауза повтора входит в бюджет.
8. Промпт повтора — тот же `attempt_prompt` текущей попытки дословно; прунинг на
   транзиентной ветке не выполняется.

Тот же предикат (пункты 3–7) гейтит до-турновый exec-fallback и серверный пре-турновый
повтор: новый процесс в обход предиката не стартует ни в одной ветке. Контекстный повтор
(hard threshold, AD-005) сохраняет гарантию «ровно один и до первого контентного кадра»
(`do_not_change`) и гейтится пунктами 3–7 с **барьером наблюдаемой активности** вместо
ACTION_POSSIBLE: hard threshold — явный отказ провайдера по размеру контекста, а не
неопределённый таймаут; остаток риска ненаблюдаемого действия унаследован от baseline
REQ-MUSE-001 и записан в ASM-010.

### 3.3 Бюджеты, дедлайн и взаимодействие счётчиков

- Бюджеты запроса (RW-002, PF-a2-003, PF-a2-008): якорь — приём запроса Handler
  (`time.monotonic()` до ожидания слота и первой попытки). `D = TIMEOUT_S`
  (1800 с при значениях по умолчанию) — потолок всей работы запроса.
  Исполнительный дедлайн `E = D − FINISH_RESERVE_S`, `FINISH_RESERVE_S = 35` с
  (grace 15 + худшая уборка группы 12 — `_terminate_run`: 5+5+2, EVD-026 — + два
  терминальных кадра по `LIVE_WRITE_TIMEOUT_S` 3 с = 33 с, округлено; ASM-012).
  Ожидание слота, все попытки, до-турновый fallback и паузы живут до `E`; grace §2.4,
  убийство группы и терминальная выдача — в резерве между `E` и `D`; успешная
  выдача после завершённой попытки идёт в запас 100 с между `D` и клиентскими
  1900 с (EVD-016; кадры по 300 символов с задержкой 5 мс — секунды, EVD-014).
  Каждая попытка получает только остаток до `E` (ServeRun — дедлайн чтения, Run —
  таймер); первая попытка при пустой очереди получает почти полный бюджет
  (`TIMEOUT_S − 35` с). Ожидание слота завершается предусмотренной ошибкой (503 до
  SSE-заголовков либо SSE error после них, формы прежние), когда остаток до `E`
  меньше `MIN_ATTEMPT_REMAINING_S` (120 с по умолчанию, env
  `MUSE_BRIDGE_MIN_ATTEMPT_S`, читается при старте); тот же порог запрещает и любой
  новый процесс (старт из очереди, повтор, fallback). Порог выбран выше самого
  короткого успешного хода wonder 51.1 с и serve-ходов 8–94 с (EVD-011); 30 с
  `SERVE_SPAWN_TIMEOUT_S` остаётся только окном handshake. Цена: запрос из очереди
  получает слот не позже `E − 120` с от приёма. Операторский `TIMEOUT_S` выше 1900 с
  гарантию запаса против клиентских 1900 с снимает, пакет её не обещает.
- Контекстный повтор (ровно 1, AD-005) получает тот же остаток до `E` и проходит
  предикат §3.2 (с барьером наблюдаемой активности, §3.2).
- Цикл запроса детерминирован: после каждой попытки сначала проверяется
  контекстный повтор (hard threshold, свой счётчик, прунённый промпт), затем
  транзиентный (свой счётчик, тот же промпт), иначе терминальный исход.
  Верхняя граница едина везде (FU-006): не более 3 вызовов `run_attempt` без
  контекстного повтора и не более 4 с ним (1 + 1 контекстный + 2
  транзиентных), не более 8 процессов с до-турновым fallback, все в одном
  слоте и внутри бюджета `E`. В области по умолчанию транзиентный повтор исполняется
  только после пре-турновых сбоев serve (новый serve-процесс, затем один exec-fallback),
  паузы 2/4 с + джиттер применяются к ним же.
- Паузы между транзиентными попытками: 2 с, затем 4 с, каждая плюс джиттер
  равномерно до 1 с; суммарно не более 8 с. Пауза спит срезами не дольше тика
  надзора клиента (0.25 с) и прерывается уходом клиента. Длительности читаются
  из модульных констант в момент повтора, чтобы тесты ужимали их monkeypatch,
  как сегодня ужимается `KEEPALIVE_S`.
- Нагрузка при деградации транспорта (FU-010, QA-009): слот удерживается на
  весь ход, поэтому повторы не поднимают параллельность выше
  `MAX_CONCURRENT=2`; глобальный cooldown и circuit breaker осознанно не
  вводятся, суммарную длительность ограничивают паузы и исполнительный дедлайн `E`.
- Между попытками клиенту не уходит ни error, ни [DONE]; keepalive фазы OPEN
  продолжается. Терминальный исход после исчерпания — существующий формат
  502 / SSE error с диагностикой последней попытки после редакции и удаления
  отражённых промптов всех попыток.

## 4. REQ-MUSE-004: живость и прогресс в SSE

Решение AD-004 (APPROVED), границы BND-002 и BND-004, дельта CD-001.

### 4.1 Что стримится, а что нет

Стримится только прирост reasoning summaries serve-пути. Content, tool_calls,
usage и финальный кадр — как сегодня, после завершения всех попыток: разбор
tool-разметки `_split_tool_calls` работает по полному тексту, и частичная
разметка клиенту не утекает. Exec-ходы summaries не дают и live не имеют.
Non-stream JSON не меняется, включая поле `reasoning_summaries` целиком.

### 4.2 Контракт live-sink и инвариант конкатенации

- ServeRun получает необязательный sink Handler и зовёт его синхронно из своего
  цикла чтения при каждом приросте summary: дельты `summary.N` и списки
  `summary` из `item/completed` проходят один путь накопления
  (`summary_parts`/`summaries`, как сегодня), чтобы текст без дельт не терялся.
  ServeRun сокет, `_wlock` и фазы SSE не знает и исключений записи не получает:
  sink возвращает только факт успеха.
- Единый предел записи (RW-004, PF-a2-002): `LIVE_WRITE_TIMEOUT_S=3` с (имя прежнее,
  эталон — droid-мост того же клиента, EVD-015) — бюджет **одного вызова `_sse_write`**,
  отсчитываемый по `time.monotonic()` от входа в вызов и охватывающий **и ожидание
  `_wlock`** (`acquire` с остатком бюджета), **и запись** (timeout сокета на остаток
  бюджета на время записи; прежнее значение восстанавливается до освобождения замка;
  timeout `sendall` в CPython общий на вызов). Предел действует на **всех писателей**:
  role-кадр, keepalive, live-sink, терминальная выдача и `[DONE]` — это правка одной
  точки `_sse_write`, а не live-sink (EVD-030: сегодня предел только `Handler.timeout=300`
  после захвата замка). Прочие входы в `_wlock` (смена фазы, `_content_started`) — короткие
  секции без I/O, ожидают только держателя, время удержания которого ограничено тем
  же пределом. Исчерпание бюджета на любой стадии (замок или запись) либо частичная
  запись кадра = зависший клиент: live отключается, соединение считается разорванным
  (частично записанный кадр `[DONE]` не гарантирует), `_sse_write` запускает существующий
  путь ухода клиента — флаг `_client_gone` и убийство группы; слот освобождается за
  предел 3 с плюс подтверждение смерти группы. Поэтому цикл чтения MSP блокируется
  живой записью не дольше 3 с на кадр **независимо от того, какой писатель держит
  замок**, и дедлайн хода медленным клиентом не срывается. Отдельной очереди кадров не
  вводится (отклонённая альтернатива AD-004). Цена — RISK-011: клиент, не принимающий
  данные 3 с, считается зависшим на любой стадии ответа.
- Префикс-монотонная публикация (RW-005). Порядок опубликованного задним
  числом не меняется: до заморозки live отдаёт только прирост
  `summary_parts[0]`. Заморозка наступает при первой дельте с индексом больше
  0, при `item/completed` reasoning или в конце хода; дальше дельты только
  копятся. Поздний меньший индекс (первой пришла `summary.1`) ничего не
  публикует до согласования. Финальное согласование в `_send_sse`: пусть `F`
  — сегодняшняя сборка `"\n\n".join(summaries)`, `P` — уже отправленный
  live-текст. Если `F` начинается с `P`, доотдаётся только хвост `F[len(P):]`
  (при полном live финального reasoning-кадра нет, повтор snapshot хвоста не
  даёт). Если нет (расхождение; не ожидается, ASM-011; PF-a2-004) — **потеря
  авторитетного текста запрещена**: после уже отправленного `P` клиенту уходит
  разделитель `"\n\n"` и авторитетный `F` **целиком** отдельным абзацем
  (допускается дублирование части текста, потери нет), расхождение логируется
  счётчиком `reasoning_diverged` с длинами `P`, `F` и общего префикса без текста.
  Пример: `P="a"`, `F="b\n\nc"` → клиент получает `a` + `\n\n` + `b\n\nc`. Так последовательность `0:"a" → 1:"b" → 0:"c"` даёт клиенту
  `"a"` + хвост `"c\n\nb"` = итоговую `"ac\n\nb"`, а расхождение
  `item/completed` с дельтами не дублирует и не переставляет текст.
  Non-stream ответ всегда несёт авторитетную сборку `F` целиком.
- Первый фактически отправляемый непустой reasoning-кадр выставляет
  `_content_started` внутри той же критической секции `_sse_write` до записи (форма —
  параметр или колбэк вызова, зона Coder) — с этого момента повторы §3
  и контекстный повтор запрещены; буферизованная, но не отправленная дельта
  флага не ставит.
- Keepalive без изменений: пустой data-чанк каждые 15 с в фазе OPEN (предел записи —
  общий, выше). Переход на SSE-комментарии droid-моста не делается (OPEN-03,
  deferred): пустые чанки держат клиента по комментарию в коде моста (влияние на
  idle-watchdog клиента в ledger не найдено, ASM-003, `[F-47]`), комментарии для
  muse-моста не проверены, а тест test_s1 закрепляет отсутствие `: keepalive` и
  сохраняется.

### 4.3 Наблюдаемость прогресса

- Первая summary-дельта хода логируется строкой с секундами от старта хода и
  индексом (без текста): это вход отдельной диагностики VER-011; приёмку VER-009 наблюдение не заменяет (RW-007). На транзиентном терминале при истинном `_content_started` пишется строка `retry_blocked` — пара логов даёт долю ходов «первая дельта раньше сбоя» для метрики FU-005.
  Существующая строка `reasoning summaries=... preview=` в конце хода не меняется.
- Журнал инструментальных item (PF-a2-006): каждый `item/started` и `item/completed` с
  `kind` вне {`reasoning`, `agentMessage`} логируется строкой с `kind` и `toolName` только при
  совпадении с allowlist `[A-Za-z0-9_.:/-]{1,64}` (иначе `redacted` с длиной), без `rawArgs`;
  счётчик таких item входит в итоговую строку хода; на каждом транзиентном терминале serve
  логируется наличие `timeToFirstTokenMs` и `usage` (EVD-028). Это исполнимый способ закрытия
  ASM-010 и аудит наблюдаемых инструментальных действий отдельно от остаточных approval-запросов
  (T-A15, VER-009).
- `turn/modelRetryScheduled` (только 1.4.8) логируется полями `attempt`,
  `maxAttempts`, `retryDelayMs`, `errorKind` и клиенту не отдаётся: текстовый
  проброс загрязнил бы reasoning и ложно закрыл окно повторов. Живость на время
  паузы провайдера держит keepalive.

## 5. Безопасность и угрозы

Границы доверия и потоки данных (VIEW-003):

```text
[DSH доверенный клиент владельца]
   |  промпт, история сессии            ^ SSE: reasoning/content
   v                                    |
[мост :9886, ключ, loopback] --аудит безопасных полей--> bridge.log
   |  MSP: session/start allowAll, receipt/decide
   v
[muse serve: песочница хоста, write/shell OFF] -> инструменты модели
   |  через muse-cli.sh и прокси :10816 (вне доверия моста)
   v
[Meta API]
```

Сводка угроз пакета: THREAT-001 (авторазрешённый инструмент и исходящая сеть),
THREAT-002 (утечка через аудит-лог), THREAT-003 (удержание слотов циклами и
повторами), THREAT-004 (переигрывание после частичных эффектов). Митигации и
проверки — в пакете по ID. Честный остаток: до первого живого payload (OPEN-01)
пакет не утверждает, какие именно действия будут авторазрешены на wonder;
утверждается только, что write и shell выключены хостом, песочница включена, а
каждое решение моста по остаточному запросу видно владельцу в логе (полный аудит действий без остаточного запроса пакет не обещает, FU-001); откат политики — env-переключатель AD-007: при `denyUnmatched` мост нигде не разрешает
действия автоматически (`exec --yolo` не запускается ни в какой роли, AD-006), цена — доступность
(RISK-010); применение — plist + `bootout`/`bootstrap` (§7). Селективный deny без payload не
проектируется: список запретов по догадке дал бы ложную границу.

## 6. План тестов (red → green, файл тот же)

Все тесты — в `tests/test_muse_bridge_killpg.py`, новый файл не создаётся.
Порядок: сначала падающие тесты нового контракта и регрессии на каждый REQ,
затем реализация. Фикстура `install_protocol_wrapper` расширяется, сохраняя
прежние сценарии: реальный payload approval с `availableChoices`, ответы на
`approval/decide` и `userInput/cancel`, ветка `terminal=false` со вторым
запросом, задержанные `item/delta summary.N`, терминалы с net-timeout для serve
и exec, ветка `-32030` на первый `session/start`, уведомление
`turn/modelRetryScheduled`. Параметры прежнего вызова `{"approval": True}` с
пустым payload остаются валидным входом деградации, а не нормой.

| ID | Класс (-k) | Проверка |
|---|---|---|
| T-A01 | Approval | `rpc.jsonl`: `session/start` несёт `approvalMode=allowAll`; serve argv с `--disable-write --disable-shell` и без `--disable-sandbox`; лог эффективного режима |
| T-A02 | Approval | approval с choices approved+abort: receipt тем же id, decide с approved `choiceId`, `requirementId` дословно, ход `via=serve`, exec-argv отсутствует, один `turn/start` |
| T-A03 | Approval | предпочтение `approved` над `approvedForSession`; только `approvedPolicyAmendment` в списке ведёт в деградацию, а не в выбор |
| T-A04 | Approval | `terminal=false`, затем обновлённый запрос с новым requirement: второй decide, ход завершён |
| T-A05 | Approval | только `approval/requested` без запроса: один decide без receipt; пара request+requested даёт один decide; `-32051` не роняет ход |
| T-A06 | Approval | `userInput/request`: receipt и `userInput/cancel`, ход продолжается; тела вопросов в логе нет |
| T-A07 | Approval | approval позже setup-окна (фикстура ужимает spawn-окно и задерживает запрос за него): decide уходит, exec не стартует (регрессия `_write_until`) |
| T-A08 | Approval | пустой `availableChoices`; ошибка decide **параметризована по всем кодам `[F-28]`**: `-32050`, `-32052`, `-32053`, `-32054`, `-32030` защёлкивают деградацию (abort/denied или `turn/cancel`, терминальная ошибка, exec не стартует), `-32051` benign и ход продолжается; отдельный кейс — ошибка `userInput/cancel` защёлкивает (PF-a2-011) |
| T-A09 | Approval | серия запросов сверх границ 10 и 3: ход остановлен деградацией без одиннадцатого decide, группа мертва, слот свободен |
| T-A09b | Approval | фейковый serve игнорирует `turn/cancel` и отказной decide (RW-008): группа мертва и слот освобождён не позже ужатого grace после деградации, клиенту один терминальный исход, exec не стартует |
| T-A09c | Approval | stdin serve заблокирован **до** деградации (фикстура перестаёт читать stdin): grace отсчитан от защёлкивания по монотонным часам и включает попытку записи cancel/decide, группа убита и слот свободен не позже ужатого grace плюс уборка, клиенту один терминальный исход (PF-a2-003) |
| T-A10 | Approval | канарейки в `rawArgs`, в вопросе userInput и в `choiceId`/`toolName` отсутствуют в логе дословно, JSON и SSE (FU-009); аудит-строка содержит только разрешённые поля с ограниченным рендером |
| T-A11 | Approval | allowAll, `-32030` на старт с явным режимом (FU-002): второго `session/start` и `approval/decide` нет, warning с версией, ровно один exec-fallback до записи `turn/start`, один процесс serve (AD-006) |
| T-A11b | Approval | denyUnmatched × {`-32030`, EOF handshake, таймаут handshake, `session/start` без `sessionId`, spawn failed} (PF-a2-005): exec-argv отсутствует (`--yolo` не вызывается), serve не более одного процесса, один терминальный исход 502 либо SSE error с причиной `exec_fallback_disabled` и один `[DONE]` |
| T-A13 | Approval | терминальное защёлкивание (RW-006): после denied сервер поочерёдно повторяет request, возвращает `terminal=false`, присылает успешный terminal, не завершает ход; во всех ветках не более 10 decide, exec нет, ровно один терминальный исход, поздний успех отброшен |
| T-A14 | Approval | env-режим (AD-007): `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` уходит в `session/start` и approve не отправляется; без env — `allowAll`; невалидное значение останавливает старт с ошибкой; **матрица режим × пре-турновый сбой serve** (PF-a2-005): denyUnmatched — exec не вызывается (T-A11b), allowAll — согласованный ровно один exec-fallback |
| T-A15 | Approval | журнал инструментальных item (PF-a2-006): строки с `kind` и безопасным `toolName` для item вне {reasoning, agentMessage}, канарейка в аргументах отсутствует в логе дословно, счётчик в итоговой строке хода, на транзиентном терминале залогировано наличие `timeToFirstTokenMs`/`usage` |
| T-R01 | TransientRetry | каждый из четырёх маркеров на **пре-турновом** сбое serve (setup с маркером в тексте ошибки): повтор новым serve и успех, ровно 2 попытки, один [DONE], нет error между; те же маркеры в `turn/completed.error` (реальная форма с `error.kind`/`error.message`, FU-012) и в stderr exec в области по умолчанию **не** повторяются (терминал, ровно одна попытка), а при `observed-items` — повторяются (T-R07b) |
| T-R02 | TransientRetry | три транзиентных отказа: ровно 3 попытки, терминальная ошибка прежнего формата, группы мертвы, слот освобождён один раз |
| T-R03 | TransientRetry | нет повтора: после первой live-дельты, при уходе клиента в паузе и во время попытки, при `dead_confirmed` ложном, при остатке до `E` меньше `MIN_ATTEMPT_REMAINING_S`, на `timeout` и `spawn_failed`, на маркере в успешном тексте |
| T-R04 | TransientRetry | hard threshold в приоритете: контекстный повтор с прунённым промптом, транзиентный счётчик не израсходован; обновлённый test_t18 сохраняет это утверждение |
| T-R05 | TransientRetry | повторная попытка получает только остаток до `E` от приёма (фикстура фиксирует переданный дедлайн/таймер меньше полного TIMEOUT_S) |
| T-R06 | TransientRetry | предикат допуска (RW-001): `turn/start` записан, но ack не пришёл (обрыв), summary→EOF, summary→ошибка чтения, approval→ошибка записи receipt/decide, cancel→EOF не запускают exec и дают один терминальный исход; EOF рукопожатия до записи `turn/start` один раз уходит в exec |
| T-R07 | TransientRetry | граница ACTION_POSSIBLE (PF-a2-001, red до фикса): заглушка serve пишет наблюдаемый маркер побочного эффекта БЕЗ `item/started|completed`, `approval/request` и выходного текста, затем после записи `turn/start` возвращает net-timeout — ровно одна попытка, **ровно один** побочный эффект, один терминальный исход; то же для exec (эффект, пустой stdout, маркер в stderr): один процесс, один эффект; сбой до записи `turn/start` с маркером допускает повтор |
| T-R07b | TransientRetry | область `observed-items` (`MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE`): заглушка без сигналов повторяется, в логе warning старта и `retry_scope` на повторе; заглушка с инструментальным item, approval либо непустым текстом exec — не повторяется; невалидное значение переключателя останавливает старт |
| T-R08 | TransientRetry | дедлайн от приёма (RW-002, PF-a2-008): три одновременных запроса при двух занятых слотах, задержанные serve и fallback; третий получает ответ или предусмотренную ошибку внутри `E` от приёма; запрос с остатком меньше ужатого `MIN_ATTEMPT_REMAINING_S` получает предусмотренную ошибку, процесс не стартует; слоты освобождены по одному разу |
| T-R10 | TransientRetry | бюджет E/D (PF-a2-003): модель висит до `E` (ужатые константы): терминальный исход клиенту и свободный слот не позже `D` от приёма, резерв `FINISH_RESERVE_S` не исчерпан попыткой, дополнительного полного grace после `D` нет |
| T-R09 | TransientRetry | серия net-timeout под двумя параллельными ходами (QA-009): одновременно не более 2 процессов, повторы внутри слотов с паузами, оба исхода внутри исполнительного дедлайна `E` |
| T-L01 | LiveReasoning | дельты `summary.0` и `summary.1` с задержкой: кадры reasoning до финального, порядок индексов, разделитель, конкатенация равна буферизованному варианту, финального дубля нет |
| T-L02 | LiveReasoning | summary только из `item/completed` без дельт не теряется ни в live, ни в non-stream `reasoning_summaries` |
| T-L03 | LiveReasoning + test_s1 | пустые keepalive-чанки сохранены, `: keepalive` отсутствует, один [DONE], content и tool_calls целы |
| T-L04 | LiveReasoning | сбой записи в середине live: ход не падает исключением ServeRun, live отключён, терминальный путь существующий |
| T-L05 | LiveReasoning | `turn/modelRetryScheduled` только в логе полями уведомления, в SSE текста нет, `_content_started` им не выставляется |
| T-L06 | LiveReasoning | out-of-order (RW-005): `0:a → 1:b → 0:c` и поздний меньший индекс (`1` раньше `0`): опубликованный порядок не переписывается, клиентская конкатенация равна сборке по индексам, потерь и дублей нет |
| T-L07 | LiveReasoning | расхождение snapshot (RW-005, PF-a2-004): `P="a"`, `F="b\n\nc"` → клиентский поток даёт `a` + `\n\n` + `b\n\nc` (авторитетный текст целиком, потери нет), в расширяющем случае хвост без дубля и повтор финального snapshot не дублирует, счётчик `reasoning_diverged` с длинами в логе, non-stream несёт авторитетную сборку |
| T-L08a | LiveReasoning | медленный клиент (RW-004): клиент не читает, заглушка заполняет буфер live-дельтами при ужатом `LIVE_WRITE_TIMEOUT_S`; sink возвращается не позже предела, группа мертва и слот свободен в пределах предела плюс подтверждение смерти, второй клиент получает полный ответ |
| T-L08b | LiveReasoning | **keepalive блокируется первым** (PF-a2-002, red до фикса): `KEEPALIVE_S` ужат, запись keepalive-кадра блокируется под `_wlock` (детерминированно — обёртка записи, блокирующаяся на остаток `connection.gettimeout()`, и/или реальный сокет с малыми буферами), затем в цикл чтения MSP приходит summary-дельта; sink и keepalive возвращаются не позже предела (а не за `Handler.timeout`), группа мертва, слот свободен, второй клиент обслужен |
| T-L08c | LiveReasoning | блокируется терминальная выдача (писатель — `_send_sse`) и `_sse_stop_keepalive` при зависшем keepalive: ожидание замка и запись ограничены тем же пределом, слот свободен, второй клиент обслужен |

Судьба существующих тестов, закрепляющих старое поведение:

| Тест | Было | Стало | Почему не ослабление |
|---|---|---|---|
| `test_approval_falls_back_to_exec_without_decide` | нет decide, обязателен exec | заменён T-A01..T-A11: decide обязателен, exec запрещён | REQ-MUSE-002 прямо отменяет этот контракт; проверки exec-флагов переезжают в тесты транспортного fallback, которые сохраняются |
| `test_t18_serve_fallback_and_network_retry_preserve_context_retry_budget` | внутренний exec network retry | транзиентный счётчик AD-003, утверждение про контекстный бюджет дословно сохранено (T-R04) | механизм обобщён, гарантия не снята |
| `test_t27_serve_unavailable_with_reflected_prompt_does_not_leak_to_log` | утечка на ServeUnavailable | сохраняется на транспортном ServeUnavailable; T-A10 добавляет approval-канарейку | покрытие расширено |
| `test_s1_data_ticks_before_done_preserve_content_and_tools` | нет `: keepalive`, пустые тики | сохраняется и дополняется T-L03 | AD-004 сознательно не меняет keepalive |
| класс R4 (клиент ушёл при живом serve) | exec не запускается | без изменений, плюс T-R03 на паузе повтора | инвариант сохранён и расширен |

Команды замороженной поверхности — VER-001..VER-007 пакета. Baseline до фикса
фиксируется тем же VER-005 на чистом дереве ветки (67 passed из envelope сверяется
фактом прогона Coder до правок).

## 7. Выкат, проверка и откат

1. Шаг 0 (FU-008): незакоммиченный baseline REQ-MUSE-001 отделяется первым
   отдельным коммитом на ветке `bugfix/muse-wonder-approval-retry-liveness`
   (task.json) от фактического дерева `dev` — его diff дословно равен снимку
   дерева до работы; либо владелец фиксирует baseline заранее. Дальнейшие
   коммиты содержат только дельту REQ-MUSE-002..004, `git diff baseline..HEAD`
   правок REQ-MUSE-001 не включает (проверка VER-012 заодно сторожит
   protected_paths). В `dev` не коммитит.
   **Этапы с red → green и отдельной проверкой каждого (PF-a2-013):** этап 1 —
   REQ-MUSE-002 (AD-002, AD-006, AD-007; класс `Approval`, VER-001); этап 2 — дедлайн и
   предикат допуска (AD-003; класс `TransientRetry`, VER-002); этап 3 — live (AD-004;
   класс `LiveReasoning`, VER-003) стартует **только после PASS спайка VER-013**
   (тайминг первой summary-дельты на одном живом ходе wonder max). При FAIL
   (дельты только в конце хода) AD-004 не реализуется, оркестратор возвращает пакет
   Architect с вопросом владельцу по REQ-MUSE-004.
2. Бэкап до деплоя: репозиторный и зеркальный `server.py` в `~/work/backups/`
   с датой в имени. Профили DSH в этом изменении не трогаются, их бэкап не нужен.
3. Оркестратор материализует ADR 0003 по `materialization[]` пакета exact bytes
   с read-back sha256 (в delta a3 proposal обновлён: область `denyUnmatched` без exec,
   механизм применения режима через plist и `bootout`/`bootstrap`, граница
   `ACTION_POSSIBLE` — материализованный файл заменяется отдельной операцией
   оркестратора, Coder его не правит; sha256 proposal и `materialization[0]` пакета — в
   `receipts/architect.json` итерации 3); Coder добавляет одну строку
   0003 в `docs/adr/INDEX.md` тем же MR. Merge — человек после ACCEPT.
4. Деплой в окно без активных ходов владельца (`kickstart -k` убивает текущий
   процесс моста): копия `bridges/muse-bridge/server.py` в
   `~/.dsh/bridges/muse-bridge/server.py`, затем
   `launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge`.
5. Лёгкий путь VER-008: `cmp` зеркала, агент в `launchctl list`, `/health` и
   `/v1/models` с ключом, свежий `serve init` с версией и `approvalMode` в логе,
   учение отката п.7. Лёгкий путь сдачей не является.
6. Тяжёлый путь VER-009 владельцем в живом слоте (длинная сессия, ход рабочего
   размера с инструментом, повтор, два параллельных, контрольный spark).
   Факты сдачи: строки аудита решений моста, `done via=serve` без
   `fallback exec`, реальный прирост reasoning в UI **во время** мышления,
   отсутствие терминального net-timeout без повторов в логе за эти ходы.
   Диагностика VER-011 по тем же логам записывает секунды до первой
   summary-дельты и вердикт по OPEN-04: дельты только в конце хода означают
   REQ-MUSE-004 = NOT_MET и приёмку не дают (RW-007). Ходы с остаточным
   approval-запросом и без него фиксируются отдельно (FU-001). Формат
   отчёта — блок ПРОВЕРЕНО канона владельца.
7. Откат: быстрый (AD-007, PF-a2-007, EVD-027) — `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched`: правка блока
   `EnvironmentVariables` в `~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist`, затем из
   внешней оболочки (не из процесса моста) `launchctl bootout gui/$(id -u)/com.user.dsh-muse-bridge`,
   дождаться исчезновения метки и `launchctl bootstrap gui/$(id -u)
   ~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist` (при ошибке 5 повторить); один
   `kickstart -k` plist не перечитывает. Область действия: мост нигде не авторазрешает действия
   — `approve` не отправляется и `exec --yolo` не запускается ни как fallback, ни как повтор;
   при недоступном serve на пре-турновой фазе запрос завершается отказом 502/SSE error
   (RISK-010). Возврат на `allowAll` — тем же путём. Учение `allowAll → denyUnmatched →
   allowAll` (VER-008) подтверждает эффективный `approvalMode` в `serve init` после каждого шага.
   Полный — вернуть обе копии `server.py` из бэкапа шага 2 и повторить `kickstart` (plist не
   менялся); это возврат к baseline с его `exec --yolo` и откатом политики не является.
   Состояния данных нет, профили не менялись, ADR 0003 при откате кода помечается
   Superseded отдельной правкой, файл не удаляется.

Риски выката сверх пакета: уже открытые слоты DSH перезапускать не нужно
(профили и окна не меняются — отличие от выката REQ-MUSE-001); ходы, идущие в
момент kickstart, оборвутся, поэтому шаг 4 делается вне живой работы; старая
копия `server.py.bak-1791815617` в каталоге деплоя откатом не считается.

## 8. Константы, трассировка, остаток

Новые константы модуля (имена рекомендуемые в стиле `TIMEOUT_S`, значения —
контракт пакета; точные идентификаторы выбирает Coder):

| Смысл | Значение | Основание |
|---|---|---|
| Режим сессии serve | `allowAll` по умолчанию; env `MUSE_BRIDGE_APPROVAL_MODE` ∈ {`allowAll`, `denyUnmatched`} | AD-001 (EVD-009), переключатель AD-007 |
| Максимум approval/decide на ход | 10, включая финальный отказной | §2.4 (RW-006), предел удержания слота |
| Максимум userInput/cancel на ход | 3 | §2.4 |
| Максимум транзиентных повторов на запрос | 2 | AD-003 против наложения на provider attempts |
| Область повтора | env `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE` ∈ {`pre-action` (по умолчанию), `observed-items`} | AD-003 п.4, PF-a2-001; `observed-items` — только по решению владельца Q-010 |
| Паузы повторов | 2 с, 4 с, джиттер до 1 с | суммарно не более 8 с внутри бюджета |
| Минимальный остаток для повтора и старта из очереди | `MIN_ATTEMPT_REMAINING_S=120` с до `E` (env `MUSE_BRIDGE_MIN_ATTEMPT_S`) | PF-a2-008: выше 51.1 с и 94 с (EVD-011); 30 с — только окно handshake, ASM-012 |
| Потолок и исполнительный дедлайн запроса | `D = TIMEOUT_S` (1800 с) от приёма; `E = D − FINISH_RESERVE_S` | RW-002 против клиентских 1900 с (EVD-016), §3.3 |
| Резерв завершения | `FINISH_RESERVE_S=35` с | grace 15 + уборка 12 + два кадра по 3 с (EVD-026), ASM-012 |
| Предел записи управляющей команды в stdin | `CONTROL_WRITE_TIMEOUT_S=5` с | PF-a2-003, меньше grace, ASM-012 |
| Grace после cancel / отказного decide | 15 с от защёлкивания (монотонные часы), включая попытку записи | RW-008, PF-a2-003: один интервал keepalive, в диапазоне панели 10–30 с |
| Предел записи SSE | 3 с на вызов `_sse_write` — ожидание `_wlock` плюс запись, все писатели (`LIVE_WRITE_TIMEOUT_S`) | RW-004, PF-a2-002: эталон droid-моста того же клиента (EVD-015, EVD-024, EVD-030) |
| Рендер свободных строк аудита | `[A-Za-z0-9_.:-]`, до 64 симв., список choiceId до 8 | FU-009, канарейка T-A10 |
| Маркеры транзиента | 4 подстроки §3.1 | лог, бенч, текст REQ, прежний маркер |

Трассировка: REQ-MUSE-002 → AD-001, AD-002, AD-006, AD-007 → QA-001, QA-002, QA-008 →
VER-001, VER-008, VER-009. REQ-MUSE-003 → AD-003 → QA-003, QA-004, QA-005, QA-009 → VER-002,
VER-010. REQ-MUSE-004 → AD-004, CD-001 → QA-005, QA-006 → VER-003, VER-009, VER-011, VER-013. Защищённые пути и baseline → BND-005 → VER-012. Полная трассировка delta — секции `delta_a3` и `delta_a2` пакета, `architecture/delta-a3.md` и `delta-a2.md`.
Наследство REQ-MUSE-001 → AD-005 → QA-007 → VER-004..VER-008.

Не-цели этого изменения: починка ProxyRack и форвардера `:10816`, UI и профили
DSH, закрепление версии CLI, live content, селективные запреты approval,
изменение exec-флагов и лимитов spark. Открытые вопросы Q-001..009 и deferred
пакета сдачу не блокируют и не закрываются молча: каждый имеет наблюдаемый
способ закрытия в логе или на тяжёлом пути.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ adr-0003:
<<<ARTIFACT ~/work/src/cli-agent-bridge/docs/adr/0003-muse-serve-approval-allowall.md sha256=721ba63d70a47d85bde9d364c48703273fae9fe43d41c7c57613aacef1b90b24
# 0003 — Неинтерактивный muse-bridge: approvalMode `allowAll` на `session/start` вместо перезапуска хода через `exec`

## Status

Accepted (2026-10-15). Формат: ADR-full — решение меняет границу доверия «модель → инструменты»
(безопасность) и поведение боевого моста DSH → Meta Muse (`:9886`, launchd
`com.user.dsh-muse-bridge`), откат требует смены режима и перезапуска моста.
Решение владельца принято 2026-10-15 05:44 MSK в чате: «Авторазрешение (allowAll)»
(запись: `/tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md`, вопрос OPEN-07).
Архитектурный пакет: `.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json`
(AD-001, AD-002, AD-006, AD-007; delta a3). Не отменяет ADR 0001/0002 и решения REQ-MUSE-001 (прунинг 400k/320k/200k).

## Y-формулировка

В контексте неинтерактивного моста `bridges/muse-bridge/server.py`, сталкиваясь с требованием
REQ-MUSE-002 «ход не перезапускается с нуля при `approval/request` / `userInput/request` от
`muse serve`», мы решили объявлять политику сессии полем `approvalMode: "allowAll"` в
`session/start` и внутри того же хода отвечать на остаточные запросы взаимодействия по протоколу
(receipt + `approval/decide`, `userInput/cancel`) вместо серверного default `promptUnmatched` с
молчаливым fallback на `muse exec` и вместо `denyUnmatched`, чтобы сохранить накопленное
мышление хода (275 с и 412 с в инцидентах 13–14.10.2026), принимая авторазрешение действий
модели в пределах инструментов, не отключённых флагами хоста serve, при сохранённых
`--disable-write --disable-shell` и включённой песочнице.

## Context

- Единственная обработка `approval/request` и `userInput/request` в мосте безусловно бросает
  `ServeUnavailable` без ответа серверу (`bridges/muse-bridge/server.py:1757-1762`); `finally`
  убивает группу процессов serve, состояние хода теряется, `run_attempt` запускает `muse exec`
  с полным исходным промптом (`server.py:2400-2446`). Цена на wonder: 275 с мышления + 2242 с
  повтора до отключения клиента (13.10) и 412 с + 455 с до `net-timeout` (14–15.10); на spark
  повторы до 1521 с. Всего в логе 29 таких переходов: 27 `muse-spark-*`, 2 `muse-wonder-full-1.0`
  (evidence-ledger [F-01]..[F-07], [F-40]-[F-42]).
- Протокол MSP отдаёт политику клиенту: `session/start` — единственная поверхность, объявляющая
  политику неинтерактивного запуска; режим — закрытый enum `allowAll | promptUnmatched |
  onRequest | denyUnmatched`; ответ на `approval/request` только подтверждает показ
  (RequestReceipt), решение идёт командой `approval/decide` с `choiceId` из текущих
  `availableChoices` и `requirementId`, равным `currentRequirementId` ([F-23], [F-28], [F-29]).
- Мост режим не передаёт и работает на default `promptUnmatched` ([F-08], [F-30]). Комментарий
  `server.py:1824-1829` о том, что любое явное значение отвергается потолком
  `approval_mode_ceiling`, на CLI 1.4.7 и 1.4.8 не воспроизведён: все четыре режима приняты
  PoC без модельного хода при флагах моста; отказ `-32030` есть в логе только на 1.4.2
  ([F-30], [F-31]).
- Постановка песочницы serve конструируется хостом и по проводу не торгуется
  (`muse serve --help`); у serve нет флагов approval — режим выбирается только по MSP ([F-10]).
  В serve встроенный LLM approval judge отключён; в exec моста approval уже подавлен `--yolo`
  ([F-11], [F-09]).
- Какой инструмент запросил approval на wonder при `--disable-write --disable-shell`, не
  установлено: payload не логируется, каталога инструментов без хода нет ([F-04], [F-37]).
  Схема допускает `subject.kind`: shell, fileAccess, network, unixSocket, process, tool ([F-26]).

## Decision drivers

1. Сохранение хода (REQ-MUSE-002): ни один запрос взаимодействия не должен стоить полного
   переигрыва промпта (768118–1326216 символов в инцидентах wonder).
2. Неинтерактивность: у моста нет пользователя, которому можно показать запрос; DSH-клиент —
   OpenAI-совместимый SSE без канала approval (`maxRetries: 0`, [F-19]).
3. Безопасность остаточной поверхности: write/shell отключены флагами хоста, песочница включена;
   что именно авторазрешено, должно быть видно оператору из лога без содержимого аргументов.
4. Обратимость эксплуатации: смена политики — одно поле `session/start` и одна граница
   `ApprovalPolicy`; откат — возврат прежнего `server.py` и перезапуск launchd.

## Considered options

- **Option A** — `allowAll` на `session/start` + внутриходовый `approval/decide` (approve) для
  остаточных запросов. Выбрана владельцем.
- **Option B** — `denyUnmatched` на `session/start` (несопоставленные действия отклоняются без
  запроса). Ход сохраняется, но действие модели отклоняется; поведение модели после отказа на
  живом ходе не наблюдалось ([F-33], OPEN-06).
- **Option C** — оставить default `promptUnmatched`, отвечать `approval/decide` с `denied`.
  Ход формально продолжается; прошлый цикл фиксировал риск зацикливания повторов при отказе
  ([F-50]); живой проверки нет.
- **Option D** — передача решения пользователю DSH. Канала в OpenAI-контракте моста нет;
  внешний контракт заморожен задачей.
- **Option E** — статус-кво: `ServeUnavailable` → `exec` с нуля. Нарушает REQ-MUSE-002 по факту
  инцидентов 13–15.10.

## Decision

Выбрана **Option A** решением владельца (см. Status). Архитектурные следствия фиксирует пакет
(AD-001/AD-002), в том числе: выбор разрешающего `choiceId` только из текущих `availableChoices`
по полю `decision` (`approved` предпочтительнее `approvedForSession`; `approvedPolicyAmendment`
не выбирать — смена политики выходит за решение владельца); при отсутствии разрешающего выбора —
контролируемая деградация внутри хода (`abort`/`denied`, иначе `turn/cancel`) с терминальной
ошибкой клиенту, без `exec`-рестарта; логирование каждого решения моста по остаточным approval-запросам только безопасными полями
(`toolName`, `subject.kind`, `protectedWrite`, `judgeEscalated`, список `choiceId`, выбранный
`decision`) через существующую редакцию, без `rawArgs`; свободные строки `toolName` и `choiceId`
в логе рендерятся ограниченным набором символов и длины. Журнал не является полным аудитом всех
действий, разрешённых сервером при `allowAll` без остаточного запроса.

### Y-rationale

A — единственный вариант, при котором действие, ради которого модель запросила разрешение,
выполняется в том же ходе: B и C сохраняют процесс, но отклоняют действие с ненаблюдавшимся
продолжением хода, D требует канала, которого нет в замороженном контракте, E — измеренная
причина потерь. Цена A ограничена хостом: `allowAll` не включает инструменты, отключённые при
конструировании serve (`--disable-write`, `--disable-shell`), и не отключает песочницу.

## Pros and cons of options

### Option A — allowAll + decide внутри хода
- ✅ Ход и действие сохраняются; режим принят на 1.4.7 и 1.4.8 ([F-30]).
- ✅ Политика объявлена на единственной штатной поверхности неинтерактивного запуска ([F-29]).
- ❌ Авторазрешает инструменты, не отключённые флагами serve (web/сеть/прочие tool-subjects);
  конкретный payload инцидентов неизвестен ([F-37]) — компенсатор: аудит-лог решений.
- ❌ Нужен внутриходовый обработчик receipt/decide (новая протокольная поверхность моста).

### Option B — denyUnmatched
- ✅ Ход не перезапускается, запросы не возникают, действие по умолчанию запрещено.
- ❌ Модель получает отказ вместо результата инструмента; исход хода после отказа не наблюдался.

### Option C — promptUnmatched + decide denied
- ✅ Минимальная смена режима (default сохраняется).
- ❌ Тот же ненаблюдавшийся исход после отказа плюс риск повторных запросов того же действия ([F-50]).

### Option D — решение пользователю DSH
- ✅ Человек в контуре каждого разрешения.
- ❌ Нет канала в замороженном OpenAI-контракте; ход висит до ответа человека (serve ожидание
  решения по таймеру не завершает — внешнее наблюдение 1.3.0, [F-39]).

### Option E — статус-кво (exec с нуля)
- ✅ Ноль нового протокольного кода.
- ❌ Измеренные потери 275–412 с мышления и до 2242 с повтора; 29 переходов в логе ([F-05]-[F-07]).

## Evaluation matrix

> Выбор сделан владельцем 2026-10-15; матрица документирует компромиссы, а не механизм выбора.
> Критерии и веса зафиксированы в пакете до реализации (AD-001).

| Критерий | Вес | A | B | C | D | E |
|---|---|---|---|---|---|---|
| Ход не теряется (REQ-MUSE-002) | 0.35 | 5 | 4 | 3 | 2 | 1 |
| Действие модели не блокируется молча | 0.20 | 5 | 1 | 1 | 3 | 3 |
| Ограниченность поверхности инструментов | 0.25 | 2 | 5 | 4 | 5 | 3 |
| Реализуемость в замороженном контракте | 0.20 | 4 | 5 | 4 | 1 | 5 |
| **Итого (взвешенно)** | | **4.05** | 3.85 | 3.05 | 2.75 | 2.70 |

## Consequences

- `session/start` моста передаёт `approvalMode: "allowAll"`; эффективный режим и `serverInfo.version`
  логируются при каждом старте serve. Отказ `-32030` (потолок старых версий) клиентским
  автоодобрением не обходится: при `allowAll` ход один раз уходит в существующий `exec`-fallback
  до записи `turn/start` с warning; при `denyUnmatched` `exec` (он всегда с `--yolo`) не запускается,
  запрос завершается контролируемым отказом 502/SSE error с причиной `exec_fallback_disabled`;
  второго старта без поля и `decide`-одобрений поверх серверного `promptUnmatched` нет (пакет
  AD-006; обход потолка — только по отдельному явному решению владельца).
- Режим переключается оператором без правки кода: `MUSE_BRIDGE_APPROVAL_MODE` (`allowAll` по
  умолчанию, `denyUnmatched` для отката) через `EnvironmentVariables` в
  `~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist` и `launchctl bootout` +
  `launchctl bootstrap gui/$(id -u)` из внешней оболочки (пакет AD-007); одного
  `launchctl kickstart -k` недостаточно — он plist не перечитывает. Значение по умолчанию и смысл
  решения владельца этим не меняются.
- Область `denyUnmatched`: мост нигде не разрешает действия модели автоматически — `serve` получает
  `denyUnmatched`, `approve` не отправляется и `exec --yolo` не запускается ни как fallback, ни как
  повтор. Цена — доступность: при недоступном `serve` на пре-турновой фазе запрос завершается
  терминальной ошибкой. Полный откат кода (восстановление `server.py`) возвращает baseline с его
  `exec --yolo`-путями и откатом политики не является.
- Автоматический повтор и exec-fallback допускаются только до записи `turn/start` на `serve`
  (граница возможного действия `ACTION_POSSIBLE`, пакет AD-003): действие модели без наблюдаемых
  сигналов нельзя исключить, поэтому после неё повтор запрещён; расширение области — только решением
  владельца (пакет Q-010, переключатель `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE`).
- Флаги serve не меняются: `--disable-write --disable-shell --trust-workspace --no-session-log`;
  `--disable-sandbox` не передаётся. Путь `exec` (`--yolo --disable-web-tools --disable-reminders`)
  не меняется.
- Изменение общее для `muse-spark-*` и `muse-wonder-*`: код обработки взаимодействия не
  ветвится по модели ([F-40]).
- Тест `test_approval_falls_back_to_exec_without_decide`, закрепляющий старое поведение,
  заменяется тестами нового контракта (пакет, VER-001); остальные гарантии REQ-MUSE-001 не
  пересматриваются.
- Откат: восстановить `server.py` из бэкапа в репозитории и в `~/.dsh/bridges/muse-bridge/`,
  перезапустить `com.user.dsh-muse-bridge`; персистентного состояния сессий нет
  (`--no-session-log`, процесс serve на запрос).

## Confirmation

- Фейковый MSP (`install_protocol_wrapper`): в `rpc.jsonl` есть `session/start` с
  `approvalMode: "allowAll"`, на `approval/request` уходят receipt и `approval/decide` с
  `choiceId` из `availableChoices`, процесс `exec` не запускается, ход завершается `via=serve`;
  при `-32030` второго `session/start` и `decide` нет, ход доводит один `exec`-fallback;
  при `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` старт несёт `denyUnmatched`, одобрений нет, а в
  комбинации с `-32030` и прочими пре-турновыми сбоями `serve` процесс `exec` (`--yolo`) не
  запускается и запрос завершается контролируемым отказом; на боевой машине учение
  `allowAll → denyUnmatched → allowAll` подтверждает эффективный `approvalMode` в `bridge.log`
  после каждого шага (пакет VER-008).
- Живой ход Wonder Full в DSH-слоте владельца (тяжёлый путь пакета, VER-009): в `bridge.log`
  видны `approvalMode=allowAll`, решения approval безопасными полями и `done via=serve` без
  `fallback exec` по этому ходу.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ python-overlay:
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md sha256=3ec402d6c3396fbd79946f5f7c4e9c12646beb66848c07eca6dd326bcd3b21ec
---
name: architecture
description: >
  Python-overlay для универсального architect-software-product: применяет командные
  границы Litestar/FastAPI, async SQLAlchemy, Pydantic, Alembic, HTTP/event/data
  contracts и Python verification surface к Architecture Packet. Использовать только
  вместе с universal Architect для S2/S3-задач в Python-бэкенде.
---

# Architecture — Python overlay

Этот файл не задаёт второй архитектурный процесс. Сначала полностью выполнить:

1. `~/Мой диск/skils/ai-sdlc/universal/architect-software-product/SKILL.md`;
2. его `references/protocol.md`;
3. `.agents/agents/architecture.md`, `.agents/agents/docs.md` и корневой `AGENTS.md`
   конкретного репозитория.

Главный выход остаётся один:
`.ai-team/runs/<run-id>/architecture/architecture-packet.json` с
`profile=python-aisdlc-gcge`.

## Приоритет правил

1. Утверждённые требования и решения владельца.
2. `AGENTS.md`, действующие ADR и реальный код репозитория.
3. Этот Python-overlay.
4. Общие defaults модели.

Личный baseline и стек «по привычке» не использовать. Если проект не Litestar/FastAPI
или не следует описанным слоям, зафиксировать фактический стек и не навязывать шаблон.

## Входной evidence

До решения открыть и сослаться в packet минимум на:

- точки входа API/consumer/job;
- service/domain/repository границы;
- модели и migrations затронутых данных;
- `pyproject.toml`/lockfile и реальные версии;
- существующие тесты, CI-команды и архитектурные правила;
- последний успешный аналог изменения, если он есть.

Использовать `rg`, import graph и чтение символов. Название файла, класса или метода
не включать в handoff, если их существование не подтверждено кодом.

## Python-specific boundaries

Если репозиторий следует командному слоению, проверить:

```text
api/ → services/ → repository → models
          ↓
        domain
```

- route/handler: transport, validation, вызов service, response;
- service: business policy, без импорта ORM model;
- repository: storage operations и mapping;
- domain: infrastructure-independent entities/contracts;
- внешний I/O: отдельный client/adapter с timeout и typed errors.

Не добавлять слой ради схемы. Для другого фактического устройства описать существующие
границы и минимальную delta, а не перестраивать проект без требования.

В `boundaries[]` указать allowed/forbidden dependencies и `verification_ids`.
Исполняемый import contract предлагать только если он окупается и одобрен как новая
dependency/process delta.

## Async и failure semantics

Для async Python явно спроектировать:

- timeout для каждой I/O-операции и cleanup;
- cancellation и partial failure;
- retry только для перечисленных transient errors;
- idempotency/deduplication для повторов;
- concurrency limit, backpressure и порядок результатов;
- ownership соединений, сессий и транзакций.

`time.sleep`, sync HTTP/DB client внутри async flow и бесконечный retry запрещены.
Для dynamic/paginated/streaming источника определить аккумуляцию и независимый сигнал
полноты; один snapshot не считается полным источником.

## Contract deltas

В `contract_deltas[]` фиксировать только изменения:

- Pydantic/DTO: поля, типы, required/default/nullability и validation;
- HTTP: method/path/request/response/error/status/idempotency/versioning;
- event: producer/consumer/schema/order/dedup/replay/compatibility;
- data: owner/schema/index/constraints/retention/classification;
- dependency: package, verified version range, purpose, operational cost и exit path.

Cross-repo mirror, compatibility window и mixed-version behavior указывать явно.
Breaking change, auth/security model, новая major dependency и cross-service contract —
one-way decision с человеческим approval.

`contract_deltas[]` непустой только если **текущая** задача явно требует сменить
контракт. Иначе пакет `BLOCKED`, а не «улучшенный» контракт. Канон:
`.agents/agents/scope-and-contracts.md`. Архитектор не ходит в чужие KEY.

## Data и migrations

Если меняется persisted state:

- Alembic migration и downgrade/forward-fix policy;
- online/offline характер DDL, lock и длительность;
- backfill/checkpoint/retry/dedup;
- совместимость старого и нового кода во время rollout;
- контроль целостности до/после;
- rollback без предположения, что потерянные данные восстановятся сами.

В `evolution` нельзя писать просто `NOT_APPLICABLE`: добавить проверяемую причину.

## ADR и proposals

Формат и путь ADR брать из `.agents/agents/docs.md` и существующего `docs/adr/INDEX.md`.
Не создавать `docs/architecture/adr/` параллельно командному каталогу.

- ADR-lite — локальное обратимое решение.
- ADR-full — дорогой откат, несколько репозиториев, NFR/security, спор или ≥3 опции.
- Sensitivity check и PoC применять по командному ADR-full contract.

Architect пишет proposal только в `architecture/proposals/`. Он не выполняет
`uv add`, не меняет `pyproject.toml`, lockfile, CI, migrations и product code.
Такие изменения перечисляются в contract/materialization plan и проходят approval.

## Views

Не требовать C1+C2 механически. Выбрать минимальный набор:

- Context/Container — меняются system ownership или внешние связи;
- Component — новое внутреннее разделение, которое Coder может понять неоднозначно;
- Dynamic/sequence — async flow, retry, transaction или несколько сервисов;
- Deployment — rollout, queue, worker, storage или failure domain;
- DFD — sensitive data, auth или trust boundary.

Каждый `views[]` содержит вопрос и artifact reference.

## Python verification surface

Включить exact команды из репозитория. Если применим стандартный командный набор:

```bash
uv run ruff format --check .
uv run ruff check .
uv run basedpyright
uv run pytest -q
```

Дополнить targeted regression, contract/integration/migration/runtime checks. Не писать
несуществующую команду ради заполнения packet. Verifier обязан запустить полный frozen
набор; Coder log не заменяет независимое выполнение.

Для каждого изменения определить чувствительность:

- bugfix: red без fix → green с fix;
- новый contract: negative/boundary test;
- migration: upgrade + data check + допустимая rollback/forward-fix проверка;
- concurrency/time/network: повтор/seed/fault injection по риску;
- architecture boundary: нарушение действительно делает arch-test красным.

## Что Architect не делает

- Не создаёт ветки и коммиты.
- Не пишет готовую реализацию и не фиксирует внутренние сигнатуры без контрактной причины.
- Не разбивает работу на искусственные задачи «≤1 день»; порядок реализации формирует
  Orchestrator/Coder по утверждённому packet.
- Не устанавливает зависимости и не ослабляет существующие gates.
- Не выдаёт self-eval или grep по заголовкам за architecture review.
- Не меняет согласованный внешний контракт без явного указания в текущей задаче.
- Не разворачивает исследование на соседние Jira-KEY.

## Definition of Done overlay

- Universal Architecture Packet валиден в `approved` phase.
- Все Python-утверждения подтверждены кодом/конфигом/официальной документацией.
- Слои, async semantics и ownership отражают реальный проект.
- Contract deltas содержат compatibility и verification IDs.
- Stateful change имеет migration/rollout/rollback и integrity checks.
- Verification surface содержит реальные project commands и targeted checks.
- ADR path/format не конфликтует с `.agents/agents/docs.md`.
- Architect не изменил product worktree.
- `contract_deltas[]` пуст либо в текущей задаче есть явное указание менять
  согласованный внешний контракт (`.agents/agents/scope-and-contracts.md`).

## Эскалация

`BLOCKED`, если отсутствует NFR, schema ownership, compatibility policy, право на
breaking/security/dependency decision или способ проверить критичный contract. Не
додумывать значения и не передавать Coder условный пакет как approved.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.
ARTIFACT_END>>>

ЗАВЕРШЕНИЕ ОТВЕТА (структура ответа для панели; блок ФОРМАТ ОТВЕТА выше — единственный формат шести критериев). Порядок: (1) две первые строки — маркеры (см. начало); (2) строки позиций по находкам из строки ПОЗИЦИИ ТРЕБУЮТСЯ ПО (по одной на находку, строго в форматах правил: AGREE F-NNN rev=<номер> — проверил: <якорь пакета> — что увидел сам; DISPUTE F-NNN — класс: invalid | duplicate_of:F-MMM | out_of_scope | foreign_key — контр-evidence: <якорь> — почему неверно; AMEND F-NNN — priority=...; locations=...; fix=... — причина: <якорь>; WITHDRAW F-NNN ...; INCONCLUSIVE F-NNN — что нужно для проверки), номер находки пиши как в леджере (трёхзначный, например F-001); (3) вопросы и ответы по правилам; (4) шесть критериев строго как в блоке ФОРМАТ ОТВЕТА; (5) `ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG`; (6) `POSITIONS: n/N` и `ANSWERS: a/A` (если в этом раунде есть новые F-блоки — ещё `FINDINGS_COMPLETE: число`); (7) последняя строка ответа — ровно `VERDICT: PASS`, `VERDICT: NEEDS WORK` или `VERDICT: RED FLAG`, без точки и пояснений. Якорь без существующей цели в поданных файлах ссылкой не считается. ВАЖНО: ответ без последней строки `VERDICT: ...` аннулируется (раунд придётся повторять); после неё не пиши ничего. FAIL без привязки к разделу пакета, [F-NN] или правилу не засчитывается. FAIL без оговорок: изменение согласованного внешнего контракта моста без явного указания в task envelope; выход за задачу.

BRIEF_END>>>