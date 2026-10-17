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
# Чек-лист brief-review: arch D3, cycle 1, a2, run muse-wonder-approval-20261015, поколение g1
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
SK-A-11 | основание: раунд D3 внутри прохода a2 — полный актуальный пакет + delta + вывод panel-rework-summarizer поданы в R1 этого прохода (checklist-sources.md: «новый чек-лист R1»); в D/C1 подаются вердикты R1 a2, леджер и протокол | источник: brief-review/references/checklist-sources.md#SK-A
JD-05 | основание: seed_recheck_duty: нет (место не с наименьшим рангом) | источник: manifest.json
## Параметры места
panel: arch | round: D3 | round_type: R2-дебат | hat: realist
hat_prompt: ~/work/universal-panel/prompt-realist.txt
seat_slot: claude-sonnet-5-5-high
seat_kind: panel-judge
seed_recheck_duty: нет | ranked_position: 2 из 3
architect_slot: muse-wonder-full-1.0


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
    "packet_sha256": "c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e",
    "verification_surface_sha256": "7e03a3babf02d9f2981f2fef004fb5560b4499ec426ce257bece6f6f6e025a6f",
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
/Users/aazhiry1/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/arch-gate-a2.json
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

PANEL-NONCE: 13c0d68c8f2170d2
ARTIFACT-SHA256: c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 13c0d68c8f2170d2» и «ARTIFACT-SHA256: c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e».

Ты — судья архитектурного совета техлидов, идёт совещание (раунд D3). Предмет оценки — Architecture Packet задачи muse-bridge (мост DeepSeek Harness → Meta Muse), а не код. Ниже: пакет и приложения, вердикты раунда 1 (твоей роли и двух других ролей, дословно), сводный леджер находок и правила раунда. Цель совещания — согласованное решение по КАЖДОЙ находке. Суди ЗАНОВО, чужой вердикт автоматически не подтверждай; позиция меняется только с ARG или NEW.

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
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r9/seats/3/verdict.md#L3-L152 sha256=68bf6b31b27c38c4f2590256b81da40bd1572fe0fc2d4f4e0daa1ad33b5b252f

Режим: architecture. Я сравнивал решения с альтернативами из пакета (статус-кво exec-рестарт, denyUnmatched, очередь-писатель, повтор с подавлением префикса). Инструментов не использовал, файлы не менял.

## F-блоки

**F-1 [non-blocking] Закрытие ASM-010 и аудит инструментов не имеют механизма**
- Якорь: architecture-packet.json#ASM-010, #THREAT-001, #BND-002, arch-spec.md §4.3.
- Правило: каждая допущенная остаточная неопределённость должна иметь исполнимый способ закрытия.
- Evidence: ASM-010 говорит «закрывается сверкой item-kind аудита первых живых ходов». Ни в BND, ни в §4.3, ни в VER, ни в T-* логирование item-kind не описано. В §4.3 перечислены только первая summary-дельта, modelRetryScheduled и approval_degraded.
- Следствие: при allowAll сервер разрешает большинство действий сам, остаточных approval/request будет мало. Аудит решений моста окажется почти пустым, а ASM-010 нечем проверить.
- Исправление: добавить в ServeRun строку на каждый item/started и item/completed с kind не из {reasoning, agentMessage}. Поля только безопасные: kind и toolName через allowlist-рендер, без rawArgs. Добавить счётчик таких item в итоговую строку хода. Добавить тест на эту строку и пункт в VER-009: ходы с инструментальными item фиксируются отдельно.
- Критерий проверки: тест канарейки показывает, что в логе есть kind и нет аргументов. VER-009 содержит выборку ходов с item вне reasoning/agentMessage.

**F-2 [non-blocking] Быстрый откат политики через env launchd не проверяется и описан неоднозначно**
- Якорь: architecture-packet.json#AD-007, evolution.rollback, #VER-008, arch-spec.md §7 п.7.
- Правило: откат one-way решения безопасности должен быть проверен на реальном канале.
- Evidence: «правка env launchd и перезапуск» и `launchctl kickstart -k`. Пакет сам указывает, что агент живёт в `~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist` (EVD-020).
- Риск: насколько я знаю, kickstart не перечитывает правки plist. Нужно bootout/bootstrap, либо чтение переменной из `~/.dsh/.env`. Это я не могу проверить по приложенным материалам.
- Следствие: в T-A14 проверяется только чтение env внутри процесса. Реальная смена режима в деплое не проверяется нигде.
- Исправление: в rollback и ADR 0003 записать точную последовательность команд (какой файл правится, bootout/bootstrap или иной способ). В VER-008 добавить «учение»: поставить denyUnmatched, перезапустить, увидеть в serve init `approvalMode=denyUnmatched`, вернуть allowAll.
- Критерий проверки: в bridge.log после каждого шага виден ожидаемый эффективный режим.

**F-3 [non-blocking] Порог старта из очереди 30 с слишком мал, формулировка дедлайна неточна**
- Якорь: architecture-packet.json#AD-003, #QA-004, #BND-003, arch-spec.md §3.3 и §8.
- Правило: порог должен соответствовать наблюдаемой длительности полезного хода.
- Evidence: «остаток ≤30 с запрещает новую попытку», тот же порог 30 с для «старта из очереди». Минимальный успешный ход wonder в бенче 51.1 с ([F-14]), серверные ходы 8-94 с ([F-43]).
- Следствие: запрос, получивший слот с остатком 31 с, займёт слот и квоту Meta на ход, который почти наверняка не завершится.
- Второе замечание: AD-003 заявляет, что дедлайн «включает grace, cleanup и финальную выдачу». §3.3 при этом даёт первой попытке полный остаток до дедлайна. Реально cleanup и выдача уходят в запас 100 с до 1900 с.
- Исправление: ввести отдельную константу минимального остатка для старта из очереди и для повтора (например, не меньше 120 с, настраиваемую). Для порога 30 с оставить только смысл «handshake-окно». В AD-003 и QA-004 явно написать, что cleanup и выдача после дедлайна укладываются в запас до 1900 с.
- Критерий проверки: T-R08 проверяет, что запрос с остатком меньше нового порога получает предусмотренную ошибку, а не запуск процесса.

**F-4 [non-blocking] Асимметрия возможностей serve и exec не названа, `--config` не рассмотрен**
- Якорь: architecture-packet.json#EVD-005, #THREAT-001, #AD-001, [F-09], [F-10], [F-38].
- Правило: trust boundary должна учитывать отличие поверхности инструментов обоих путей.
- Evidence: exec запускается с `--disable-web-tools --disable-reminders` ([F-09]). У serve таких флагов нет ([F-10]). Единственный универсальный флаг serve — `-c/--config KEY=VALUE` ([F-38]).
- Следствие: при allowAll на serve web-инструменты не отключены, хотя прежний exec-fallback их отключал. Это расширение возможностей модели относительно пути, на который раньше попадали ходы с approval. Решение владельца его допускает, но пакет это не называет и не рассматривает `-c` как способ сузить поверхность.
- Исправление: записать асимметрию в THREAT-001 и в ADR 0003. Добавить альтернативу «сузить поверхность serve через `--config`». Ключи в справке не найдены, поэтому спайк без модельного хода: проверить, есть ли ключ отключения web-инструментов. Результат вынести отдельным решением владельца.
- Критерий проверки: в пакете есть явная запись об асимметрии и альтернатива с причиной выбора или отказа.

**F-5 [non-blocking, частично pre-existing] Предел 3 с применён только к live-записи, а не к каждой записи под `_wlock`**
- Якорь: architecture-packet.json#AD-004, #BND-004, EVD-024.
- Правило: ограничение времени записи должно закрывать всех писателей, с которыми sink делит замок.
- Evidence: «на время записи под _wlock сокету выставляется timeout 3 с» относится к live-кадру. Keepalive-поток и финальная выдача пишут через тот же `_sse_write` и по EVD-024 ограничены только `Handler.timeout=300`.
- Следствие: если keepalive-запись зависла на переполненном буфере, она держит `_wlock` до 300 с. Синхронный sink в цикле чтения MSP ждёт этот замок без предела. Это сценарий RW-004, но через другого писателя.
- Исправление: применить 3-секундный предел ко всем записям под `_wlock` (keepalive и финал). Либо ограничить время захвата замка в sink и считать его таймаут признаком зависшего клиента.
- Критерий проверки: T-L08 дополнить случаем, когда буфер заполнен и первым зависает keepalive-кадр. Слот и группа освобождаются в пределах предела.

**F-6 [non-blocking] [sweep] Список ошибок decide в AD-002 неполон относительно ledger**
- Якорь: architecture-packet.json#AD-002 (choice), arch-spec.md §2.3 и §2.4, [F-28].
- Evidence: AD-002 и §2.4 перечисляют триггеры защёлкивания -32050/-32052/-32053 и benign -32051. В [F-28] есть ещё -32054 approvalReviewerUnavailable и -32030 commandRejected. §2.3 говорит «любая error кроме -32051 ведёт в деградацию», то есть тексты расходятся.
- Исправление: записать одним правилом «любая ошибка decide и cancel, кроме -32051, защёлкивает отказ». Добавить -32054 и -32030 в тест T-A08 или T-A13.
- Критерий проверки: параметризованный тест на каждый код из [F-28].

**F-7 [non-blocking] Нет плана поставки по этапам и выключателей для повтора и live**
- Якорь: arch-spec.md §6 (около 35 тестов T-A/T-R/T-L), architecture-packet.json evolution.rollout и rollback, deferred «env-переопределение остальных констант».
- Правило: стоимость сопровождения и откат должны быть соразмерны объёму.
- Evidence: один файл server.py (2744 строки) и один файл тестов, который уже вырос на 2941 строку. В него добавляются ApprovalPolicy, терминальное защёлкивание, абсолютный дедлайн с предикатом допуска, барьер активности и live-sink с заморозкой. Откат: env только для режима approval, для повтора и live только полный redeploy.
- Исправление: разбить коммиты на этапы с red→green и отдельной проверкой каждого.
  1. REQ-MUSE-002 (AD-001/002/006/007).
  2. Дедлайн и предикат (AD-003).
  3. Live (AD-004).
  Добавить дешёвые env-выключатели для транзиентного повтора и live-reasoning, по образцу AD-007. Выключатель live позволит отключить его, не откатывая approval.
- Критерий проверки: пакет перечисляет этапы и выключатели. Тест на выключенный live возвращает прежний один reasoning-кадр.

**F-8 [non-blocking] Узкое место REQ-MUSE-004 (OPEN-04) выясняется после постройки самой сложной части**
- Якорь: architecture-packet.json#RISK-007, #VER-011, #ASM-004, #Q-004.
- Правило: самый дорогой по реализации блок не должен зависеть от недоказанного факта, если его можно проверить дёшево.
- Evidence: по RW-007 и VER-011 при summaries только в конце хода REQ-MUSE-004 остаётся NOT_MET/BLOCKED. Отдельного пути прогресса в пакете нет. Весь AD-004 (заморозка, префикс-монотонность, предел записи, T-L01..L08) строится до проверки факта, а проверка требует только временных меток.
- Исправление: добавить шаг до AD-004. Мост временно логирует первую summary-дельту на живом ходе (одна строка логирования, без остального). Владелец делает один ход wonder max. Результат записывается в OPEN-04. Если дельты приходят только в конце хода, остановить реализацию AD-004 и вернуться к пакету с вопросом владельцу.
- Критерий проверки: есть запись с секундами до первой дельты и длительностью хода до начала реализации live.

**F-9 [non-blocking] Утверждения про клиента поданы как факт без опоры в ledger**
- Якорь: architecture-packet.json#EVD-015, #AD-004 (drivers), #CD-001 compatibility, #ASM-003, [F-18], [F-47].
- Evidence: EVD-015 утверждает «клиент DSH live reasoning_content уже потребляет». В [F-18] описана только отправка со стороны droid-моста. ASM-003 те же слова называет допущением (ASSUMED). В drivers AD-004 «пустые data-чанки доказано держат соединение». [F-47] фиксирует только причину в комментарии кода, а влияние на idle-watchdog «не найдено».
- Исправление: в EVD-015 и в CD-001 переформулировать как допущение ASM-003. Заменить «доказано» на «по комментарию кода».
- Критерий проверки: формулировки в EVD-015, AD-004 и CD-001 совпадают со статусом ASM-003.

**F-10 [non-blocking] [sweep] Коллизия идентификаторов F-NNN и [F-NN]**
- Якорь: architecture-packet.json#AD-002 (drivers «F-006», «F-011»), #AD-003 (drivers «F-002», «F-003»), #AD-004 (drivers «F-005, F-012»), #AD-006 (alternatives «F-009»), #AD-007 (drivers «F-020»).
- Evidence: в тех же полях ledger ссылается как «F-50 в ledger», «F-35 в ledger». Голые трёхзначные F-NNN означают находки панели, которых в приложенном ledger нет. Читатель может принять их за двузначные факты [F-NN].
- Исправление: переименовать находки панели в PF-NNN или давать полное имя. Для ledger оставить только [F-NN].
- Критерий проверки: поиск по пакету не находит трёхзначных F-NNN вне delta_a2.

**F-11 [non-blocking] [sweep] Устаревший текст в arch-spec**
- Якорь: arch-spec.md (шапка, «Нумерация: AD-001..AD-006», строка статуса «повторный ARCH_GATE впереди»), architecture-packet.json#AD-007.
- Evidence: AD-007 существует, а шапка перечисляет AD-001..AD-006. Строка статуса говорит, что ARCH_GATE впереди, хотя приложен receipt arch-gate-a2.json со статусом PASS. Кроме того, delta-a2.md говорит, что материализованный ADR 0003 в `docs/` имеет sha `fcf1aea8…`. Приложение adr-0003 с путём в `docs/` имеет sha `4754421f…` (я не могу проверить, какой файл на диске).
- Исправление: привести шапку и статус к фактическому состоянию. Сверить sha файла в `docs/` с materialization[0].sha256.
- Критерий проверки: шапка перечисляет AD-001..AD-007, строка статуса соответствует receipt, sha файла в docs совпадает с пакетом.

**F-12 [non-blocking] Подрешения a2 не имеют отдельных альтернатив с причиной выбора**
- Якорь: architecture-packet.json#AD-002 (grace 15 с, защёлкивание), #AD-003 (абсолютный дедлайн, предикат и барьер), #AD-004 (префикс-монотонная заморозка).
- Правило: новое решение должно иметь ≥2 альтернативы с причиной выбора.
- Evidence: у каждого AD-NNN ≥2 альтернативы, так что формально критерий выполнен. Но отдельные подрешения a2 не имеют альтернатив: значение grace 15 с (обосновано только «диапазон панели 10–30 с»), абсолютный дедлайн против отдельного лимита очереди, барьер активности против запрета повтора после любого turn/start, префикс-монотонная заморозка против стриминга по item/completed.
- Исправление: добавить в соответствующие AD по одной-две альтернативы с причиной. В ASM-010 уже названа контингенция «ужесточить до turn/start», её стоит вынести в alternatives AD-003.
- Критерий проверки: каждое из перечисленных подрешений присутствует в alternatives соответствующего AD.

## Проверка исправлений

FIXCHECK RW-001: fixed — architecture-packet.json#AD-003 и #BND-003: единый предикат допуска, fallback только до принятого turn/start и до approval-трафика. #BND-002 forbidden запрещает ServeUnavailable с fallback после turn/start. T-R06 и VER-002 перечисляют summary→EOF, summary→ошибка чтения, approval→ошибка записи, cancel→EOF.
FIXCHECK RW-002: fixed — architecture-packet.json#AD-003, #QA-004, #BND-003: абсолютный дедлайн от приёма, 1800 с по умолчанию, включает ожидание слота, потолок записан одинаково в AD-003 и QA-004 (запас 100 с до 1900 с). T-R08 и VER-010 есть. Остаётся уточнение F-3.
FIXCHECK RW-003: fixed — architecture-packet.json#AD-003 (барьер активности), #THREAT-004, #ASM-010, #QA-005. Выбран запрет повтора, at-least-once не принята. THREAT-004 переписан без опоры только на write/shell и смерть группы. T-R07 с побочным эффектом до SSE-контента есть. Остаточная неопределённость вынесена в ASM-010, механизм закрытия неполон (F-1).
FIXCHECK RW-004: fixed — architecture-packet.json#AD-004, #BND-004, #EVD-024: LIVE_WRITE_TIMEOUT_S=3 с через settimeout под `_wlock` с восстановлением. Таймаут или частичная запись считаются зависшим клиентом, группа убивается, очередь-писатель отклонена в alternatives. T-L08 есть. Остаётся пробел по другим писателям под замком (F-5).
FIXCHECK RW-005: fixed — architecture-packet.json#AD-004, #BND-004, #CD-001: префикс-монотонная публикация, заморозка при первой дельте индекса больше 0 или item/completed, финальный хвост только при F.startswith(P), при расхождении дубля нет и расхождение логируется. T-L06 и T-L07 есть. Пример 0:a→1:b→0:c даёт «a» + «c\n\nb».
FIXCHECK RW-006: fixed — architecture-packet.json#AD-002 (choice) и #QA-001: предел 10 decide включает финальный отказной, одиннадцатого нет, терминальное защёлкивание. Повторный request, terminal=false, успешный terminal и молчание не меняют исход. T-A13 есть. Остаётся неполный список кодов ошибок (F-6).
FIXCHECK RW-007: fixed — architecture-packet.json#VER-009 и #VER-011: приёмка только при реальном pre-terminal приросте reasoning в DSH-слоте, ветка «лог фиксирует приход в конце» из PASS убрана. VER-011 диагностический. #RISK-007 и #QA-006 согласованы: при summary только в конце REQ-MUSE-004 = NOT_MET/BLOCKED.
FIXCHECK RW-008: fixed — architecture-packet.json#AD-002, #THREAT-003, #ASM-006, #QA-001: APPROVAL_CANCEL_GRACE_S=15 с после turn/cancel или отказного decide, затем убийство группы, терминальная ошибка, слот свободен без ожидания 1800 с. T-A09b и VER-001 есть.

## Подкатегории

SUB 1/1.1: PASS — решения AD-001..AD-007 согласованы. Предикат допуска в AD-003/BND-003 совпадает с запретами BND-002 и с AD-002 (деградация без exec). Мелкая неточность формулировок: F-6, F-11.
SUB 1/1.2: PASS — отказ записи после turn/start, зависший клиент, игнорирующий cancel serve, fallback до turn/start, исчерпание очереди описаны и покрыты T-A09b, T-A13, T-R06, T-R08, T-L08. Остатки: F-3, F-5.
SUB 1/1.3: PASS — EVD-001..EVD-025 опираются на [F-01]..[F-52], совпадения с ledger проверены (EVD-003, 011, 013, 016, 019). Неподкреплённые формулировки про клиента и коллизия идентификаторов: F-9, F-10.
SUB 2/2.1: PASS — REQ-MUSE-002 закрыт AD-001/002/006/007, REQ-MUSE-003 — AD-003, REQ-MUSE-004 — AD-004 с честным NOT_MET при дельтах только в конце. Ограничения REQ-MUSE-001 сохранены в AD-005 и VER-004.
SUB 2/2.2: PASS — ASM-001..010, Q-001..009 и deferred явно сформулированы и не блокируют. Несовершенства: F-1 (механизм закрытия ASM-010), F-8 (ранняя проверка OPEN-04).
SUB 3/3.1: PASS — все изменения внутри bridges/muse-bridge/server.py и тестов, зависимостей нет. Объём большой, этапность не описана: F-7.
SUB 3/3.2: PASS — бэкап, kickstart, baseline-коммит и VER-012 описаны, быстрый откат есть. Откат через env не проверен на канале деплоя: F-2. Гранулярность отката для retry/live: F-7.
SUB 4/4.1: PASS — allowAll принят владельцем (EVD-009), write и shell отключены хостом, песочница включена, аудит назван честно как аудит решений по остаточным запросам. Асимметрия web-инструментов и `--config` не рассмотрены: F-4.
SUB 4/4.2: PASS — allowlist-рендер toolName и choiceId, запрет rawArgs и тел вопросов, канарейки T-A10. Отсутствие аудита item-kind: F-1.
SUB 4/4.3: PASS — повторы ограничены (не более 2, паузы не более 8 с, внутри слота), прокси назван внешней зависимостью, версии логируются, -32030 обработан по AD-006. Порог остатка: F-3.
SUB 5/5.1: PASS — у каждого нового AD-001..AD-004, AD-006, AD-007 есть ≥2 альтернативы с причиной (AD-005 унаследован, пустой список допустим). Подрешения без отдельных альтернатив: F-12.
SUB 5/5.2: PASS — рост нагрузки разобран в QA-009 и RISK-002: слот удерживается на весь ход, параллелизм не выше 2, circuit breaker отклонён с обоснованием. Вырождение (мелкий остаток в очереди, поток запросов к нестабильному прокси) частично отражено в F-3.
SUB 6/6.1: PASS — контракт заморожен, единственная дельта CD-001 аддитивна и разрешена task envelope (аддитивные SSE-кадры внутри существующих полей). /health, /v1/models, коды и окна моделей не затронуты. Допущение про клиента: F-9.
SUB 6/6.2: PASS — профиль python-aisdlc-gcge применён к реальному устройству (один файл, потоки, stdlib), слои не навязаны. ADR-full, evolution с причиной NOT_APPLICABLE, protected_paths расширены. Устаревший текст спеки: F-11.
SUB 6/6.3: PASS — команды VER-001..VER-012 конкретны, red→green указаны, тяжёлый путь VER-009 исполняет владелец в живом слоте. Имена классов в VER-004 (ContextPrune и др.) не могу проверить по приложенным материалам.

## Шесть критериев

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Решения согласованы между собой и опираются на ledger. Все 8 RW закрыты. Остатки только в формулировках (F-6, F-9, F-10).
   СОВЕТЫ (при FAIL): —
2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-MUSE-002/003/004 покрыты, ограничения REQ-MUSE-001 унаследованы. Открытые вопросы оформлены и не блокируют. Механизм закрытия ASM-010 и ранняя проверка OPEN-04 приведены как рекомендации (F-1, F-8).
   СОВЕТЫ (при FAIL): —
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Всё реализуемо внутри server.py и одного файла тестов без новых зависимостей. Объём большой, поставка без этапов и без выключателей для retry и live (F-7), откат через env не проверен (F-2).
   СОВЕТЫ (при FAIL): —
4. РИСКИ: VERDICT=PASS
   WHY=Модель угроз, барьер активности, лимиты и grace покрывают основные сценарии. Остатки: асимметрия web-инструментов serve и exec (F-4), предел записи не для всех писателей (F-5), порог остатка в очереди (F-3).
   СОВЕТЫ (при FAIL): —
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового AD ≥2 альтернативы с причиной выбора и подтверждением командой. Подрешения a2 стоит дополнить (F-12).
   СОВЕТЫ (при FAIL): —
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт заморожен, дельта CD-001 разрешена envelope. Verification surface включает red→green, Full Suite Gate и тяжёлый путь. Расхождения в тексте спеки косметические (F-11).
   СОВЕТЫ (при FAIL): —

ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 12
VERDICT: PASS
ARTIFACT_END>>>

АРГУМЕНТЫ ДРУГИХ ЭКСПЕРТОВ (вердикты раунда 1 двух других ролей; две служебные строки маркеров раунда R1 в выдержках опущены):
Эксперт Скептик:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r9/seats/1/verdict.md#L3-L46 sha256=d522db54c4a861a9b9c993b41adbee5e71f1f3d171957ef756d809854189afb3
Подтверждаю: прочитал общий канон ~/Мой диск/Context/AGENTS.md целиком до <!-- КАНОН-КОНЕЦ --> и проектные правила (AGENTS.md, .agents/AGENTS.md, .agents/CLAUDE.md, CLAUDE.md — в рабочей папке отсутствуют).
RECHECK: seed_hex=43ff9973 ranked_order=gemini-4-argon-high,muse-wonder-full-1.0,gpt-6.1-sol-high,claude-sonnet-5-5-high результат=OK

FIXCHECK RW-001: fixed — architecture-packet.json#AD-003 — в AD-003, AD-002 и BND-003 определён единый предикат допуска любого нового процесса; внутренний exec-fallback разрешён только до принятого turn/start и до любого approval-трафика, а после turn/start EOF, ошибки чтения/записи stdin и дедлайн чтения завершают запрос терминально без exec (VER-002, T-R06).
FIXCHECK RW-002: fixed — architecture-packet.json#QA-004 — в AD-003, BND-003 и QA-004 введён единый абсолютный дедлайн запроса TIMEOUT_S=1800 с от момента приёма в Handler, включающий ожидание слота, все попытки, fallback, паузы, grace, cleanup и финальную выдачу, с отсечкой ожидания слота и старта новой попытки при остатке ≤30 с до дедлайна (VER-002, T-R08).
FIXCHECK RW-003: fixed — architecture-packet.json#THREAT-004 — в AD-003, BND-002, BND-003 и THREAT-004 зафиксирован барьер инструментальной активности (approval/userInput-трафик, любой decide, любой item с kind вне {reasoning, agentMessage} на serve и непустой ответ на exec), запрещающий fallback и оба вида повторов; ненаблюдаемый остаток выделен в ASM-010, тест побочного эффекта T-R07 включён в VER-002.
FIXCHECK RW-004: fixed — architecture-packet.json#AD-004 — в AD-004 и BND-004 синхронная запись live-sink под _wlock ограничена LIVE_WRITE_TIMEOUT_S=3 с на кадр через settimeout сокета с восстановлением; таймаут или частичная запись трактуется как зависший клиент без гарантии [DONE], запускает штатное убийство группы serve и освобождение слота (VER-003, T-L08).
FIXCHECK RW-005: fixed — architecture-packet.json#CD-001 — в AD-004, BND-004 и CD-001 введена префикс-монотонная публикация: до заморозки стримится только прирост summary_parts[0], заморозка наступает на первом индексе >0, item/completed reasoning или конце хода, а _send_sse доотдаёт хвост F[len(P):] только при F.startswith(P), исключая перестановку и дублирование (VER-003, T-L06, T-L07).
FIXCHECK RW-006: fixed — architecture-packet.json#AD-002 — в AD-002, BND-002 и QA-001 введено терминальное защёлкивание отказа: лимит 10 decide включает финальный abort/denied (11-го decide нет, сразу turn/cancel), после защёлкивания повторный request, terminal=false, поздний успешный turn/completed и молчание сервера не меняют локальный неуспешный исход и не запускают exec (VER-001, T-A13).
FIXCHECK RW-007: fixed — architecture-packet.json#VER-009 — в VER-009 приёмка REQ-MUSE-004 отделена от диагностики OPEN-04 и требует реального pre-terminal прироста reasoning в UI и логе первой дельты строго до конца хода; диагностика вынесена в VER-011, где приход дельт только в конце хода фиксирует REQ-MUSE-004 как NOT_MET/BLOCKED (RISK-007, ASM-004).
FIXCHECK RW-008: fixed — architecture-packet.json#THREAT-003 — в AD-002, ASM-006 и THREAT-003 введён APPROVAL_CANCEL_GRACE_S=15 с после отправки turn/cancel или отказного decide, по истечении которого группа процессов serve принудительно убивается и слот освобождается без ожидания 1800 с (VER-001, T-A09b).

SUB 1/1.1: PASS — логика решений AD-001..AD-007 взаимно согласована: единый предикат допуска нового процесса и абсолютный дедлайн в architecture-packet.json#AD-003 синхронизированы с терминальным защёлкиванием и grace в architecture-packet.json#AD-002, границей _content_started и префикс-монотонным live-стримом в architecture-packet.json#AD-004, обработкой -32030 до turn/start в architecture-packet.json#AD-006 и переключателем режима в architecture-packet.json#AD-007.
SUB 1/1.2: PASS — граничные условия и режимы отказа исчерпывающе определены: после принятого turn/start ошибки чтения/записи stdin и EOF не уходят в exec (architecture-packet.json#AD-002, architecture-packet.json#AD-003), лимит 10 decide включает финальный отказной decide, после защёлкивания любые ответы сервера игнорируются, зависший serve убивается через APPROVAL_CANCEL_GRACE_S=15 с, зависший SSE-клиент отсекается за LIVE_WRITE_TIMEOUT_S=3 с (architecture-packet.json#AD-004).
SUB 1/1.3: PASS — все утверждения пакета опираются на верифицированные факты леджера [F-01]..[F-52] и EVD-001..EVD-025 (architecture-packet.json#EVD-001, [F-23], [F-28], [F-30], [F-35], [F-49]).
SUB 2/2.1: PASS — целевые требования REQ-MUSE-002 (AD-001, AD-002, AD-006, AD-007), REQ-MUSE-003 (AD-003), REQ-MUSE-004 (AD-004, CD-001) и унаследованные ограничения REQ-MUSE-001 (architecture-packet.json#AD-005) полностью покрыты и протрассированы до QA-001..QA-009 и VER-001..VER-012.
SUB 2/2.2: PASS — все открытые вопросы оформлены как ASM-001..ASM-010 и Q-001..Q-009; единственный блокер OPEN-07 валидирован решением владельца (architecture-packet.json#ASM-009, architecture-packet.json#EVD-009), остаточный риск ненаблюдаемой инструментальной активности явно ограничен в architecture-packet.json#ASM-010, а риск прихода summary только в конце хода выделен в блокирующее условие приёмки architecture-packet.json#VER-009 и диагностику architecture-packet.json#VER-011.
SUB 3/3.1: PASS — изменения локализованы в существующих классах Handler и ServeRun внутри bridges/muse-bridge/server.py и чистой функции/объекте ApprovalPolicy без добавления новых внешних библиотек или слоёв (architecture-packet.json#BND-001, architecture-packet.json#BND-002, architecture-packet.json#BND-003, architecture-packet.json#BND-004).
SUB 3/3.2: PASS — стоимость сопровождения минимальна, незакоммиченный baseline REQ-MUSE-001 отделяется шагом 0 до правок задачи (architecture-packet.json:671), предусмотрен быстрый операционный откат политики через MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched без правки кода (architecture-packet.json#AD-007) и полный файловый откат из бэкапа.
SUB 4/4.1: PASS — граница доверия при allowAll явно описана в architecture-packet.json#THREAT-001 и docs/adr/0003-muse-serve-approval-allowall.md:18: флаги --disable-write --disable-shell и песочница хоста сохранены, обход потолка -32030 клиентским approve запрещён без отдельного решения владельца (architecture-packet.json#AD-006), журнал честно определён как аудит решений моста по остаточным запросам.
SUB 4/4.2: PASS — логирование в ApprovalPolicy защищено от инъекций и утечек секретов: rawArgs и тела вопросов userInput не читаются и не логируются, свободные строки toolName и choiceId ограничены регулярным выражением [A-Za-z0-9_.:-] длиной до 64 символов и списком до 8 элементов с хешированием остальных (architecture-packet.json#THREAT-002, architecture-packet.json#BND-001).
SUB 4/4.3: PASS — эксплуатационные риски наложения ретраев на прокси, зависания процессов и автообновления CLI закрыты абсолютным дедлайном 1800 с от приёма, удержанием слота MAX_CONCURRENT=2 без мультипликации параллельных процессов (architecture-packet.json#QA-009, architecture-packet.json#RISK-002) и деградацией при -32030 (architecture-packet.json#RISK-005).
SUB 5/5.1: PASS — каждое новое решение содержит не менее двух содержательных альтернатив с явной причиной выбора и отказа: AD-001 (4 альтернативы), AD-002 (5 альтернатив), AD-003 (4 альтернативы), AD-004 (5 альтернатив), AD-006 (3 альтернативы), AD-007 (2 альтернативы) (architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007).
SUB 5/5.2: PASS — поведение при росте нагрузки и деградации внешнего транспорта явно смоделировано и верифицируемо: в architecture-packet.json#QA-004 и architecture-packet.json#QA-009 определено, что ломается при насыщении очереди сверх MAX_CONCURRENT=2 (запросы в очереди отсекаются предусмотренной ошибкой за 30 с до абсолютного дедлайна 1800 с) и при мульти-индексных summary (live-стрим замораживается после summary.0 до финального согласования в architecture-packet.json#AD-004).
SUB 6/6.1: PASS — внешний OpenAI-контракт (/v1/chat/completions, /health, /v1/models) заморожен, единственная дельта architecture-packet.json#CD-001 является допустимой аддитивной фрагментацией delta.reasoning_content внутри существующего поля на serve-пути, выход за скоуп задачи отсутствует.
SUB 6/6.2: PASS — пакет соблюдает правила репозитория и ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md: фактический stdlib-стек зафиксирован без навязывания Litestar/FastAPI, все таймауты, backpressure и идемпотентность стрима/повторов специфицированы, ADR 0003 оформлен в формате ADR-full, protected_paths расширен (architecture-packet.json:918).
SUB 6/6.3: PASS — поверхность верификации VER-001..VER-012 содержит точные команды pytest/ruff/basedpyright/git diff, сценарии red→green для всех новых контрактов и разделённые бинарные гейты живой приёмки (architecture-packet.json#VER-009) и диагностики (architecture-packet.json#VER-011).

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Все блокирующие замечания первого прохода по корректности (RW-001, RW-002, RW-005, RW-006) полностью устранены. В AD-003 и BND-003 задан единый предикат допуска любого нового процесса: внутренний serve→exec fallback разрешён исключительно до принятого turn/start и до любого approval-трафика, а любые сбои чтения/записи/EOF после turn/start завершаются терминально без запуска exec. Абсолютный бюджет TIMEOUT_S=1800 с отсчитывается от приёма запроса в Handler и включает ожидание слота, попытки, fallback, паузы, grace 15 с и финальную выдачу с отсечкой за 30 с до дедлайна, что гарантирует запас 100 с до клиентского таймаута 1900 с ([F-19]). В AD-002 введено терминальное защёлкивание отказа и однозначный потолок в 10 команд approval/decide (включая финальный abort/denied). В AD-004 и CD-001 live-публикация сделана строго префикс-монотонной (стримится только прирост summary_parts[0] до заморозки, хвост доотдаётся по проверке startswith), что исключает перестановку и дублирование при произвольном порядке прихода дельт ([F-35]).
2. ПОЛНОТА: VERDICT=PASS
   WHY=Пакет полностью покрывает REQ-MUSE-002, REQ-MUSE-003, REQ-MUSE-004 и сохраняет ограничения REQ-MUSE-001 (AD-005). Замечание RW-007 закрыто: в VER-009 успешная приёмка REQ-MUSE-004 требует фактического pre-terminal прироста reasoning_content во время мышления, а диагностика OPEN-04 вынесена в отдельный гейт VER-011, где приход дельт только в конце хода явно оставляет требование в статусе NOT_MET/BLOCKED. Все открытые вопросы (Q-001..Q-009) и допущения (ASM-001..ASM-010) явно задокументированы и имеют планы закрытия.
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Архитектура опирается на уже существующие механизмы bridges/muse-bridge/server.py (Handler, ServeRun, Run, _wlock, _slots, _redact_secrets) и проверенный паттерн соседнего droid-моста (LIVE_WRITE_TIMEOUT_S=3 с через settimeout сокета, [F-18], EVD-024). План выката (evolution.rollout) отделяет незакоммиченный baseline REQ-MUSE-001 (2941 строка, [F-51]) отдельным коммитом шага 0 и защищает конфигурационные и соседние файлы через protected_paths и VER-012. Добавлен операционный переключатель MUSE_BRIDGE_APPROVAL_MODE (AD-007) для мгновенного отката политики без изменения кода.
4. РИСКИ: VERDICT=PASS
   WHY=Все блокирующие риски (RW-003, RW-004, RW-008) и follow-up замечания закрыты. Против дублирования неидемпотентных действий при повторе (THREAT-004) введён наблюдаемый барьер инструментальной активности (любой item вне reasoning/agentMessage, любой approval/userInput сигнал или отправленный decide на serve, непустой вывод на exec), а ненаблюдаемый остаток до сбора живых payload явно зафиксирован в ASM-010. Против блокировки чтения MSP медленным клиентом введён LIVE_WRITE_TIMEOUT_S=3 с под _wlock с переводом соединения в ветку ушедшего клиента и освобождением слота (AD-004). Против зависания слотов при игнорировании сервером turn/cancel введён APPROVAL_CANCEL_GRACE_S=15 с с принудительным убийством группы процессов (AD-002, THREAT-003). В аудит-логе ограничены длина и алфавит свободных строк toolName и choiceId (BND-001, THREAT-002), а при ошибке -32030 запрещён клиентский обход потолка поверх promptUnmatched (AD-006).
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового решения AD-001, AD-002, AD-003, AD-004, AD-006, AD-007 приведено от 2 до 5 альтернатив с чётким обоснованием отказа. На уровне архитектуры в целом выбранная схема (Stateful In-Turn MSP Resolution + Handler-Level Bounded Retry + Prefix-Monotonic Synchronous Live Sink под 3-секундным socket timeout) сопоставлена как минимум с двумя альтернативными архитектурами: (1) Архитектура пассивного отказа на уровне сессии или деградации в exec (session/start с denyUnmatched либо fallback в exec с --yolo на последнем шаге деградации до _content_started) — отвергнута, так как denyUnmatched блокирует целевое действие модели с неизвестным исходом хода ([F-33], [F-50]), а переход в exec после approval-трафика нарушает барьер неидемпотентной инструментальной активности (RW-003) и сбрасывает 275–412 с мышления ([F-06], [F-07]); (2) Архитектура асинхронного стриминга через выделенную очередь кадров с отдельным потоком-писателем и повтором после первой live-дельты с побайтовым подавлением отправленного префикса — отвергнута в AD-003 и AD-004, поскольку генерация второй попытки недетерминирована и не гарантирует совпадения префикса reasoning, а выделенная очередь усложняет синхронизацию с финальным _send_sse ради того же 3-секундного предела backpressure. При росте нагрузки в выбранной архитектуре в первую очередь ломаются три звена: (а) пропускная способность очереди слотов при MAX_CONCURRENT=2 ([F-21]) — если два длинных хода или серии ретраев удерживают оба слота дольше 1770 с, третий и последующие параллельные запросы отсекаются по условию остатка ≤30 с до абсолютного дедлайна 1800 с ошибкой 503 / SSE error (QA-004, T-R08); (б) окно доступности транзиентного ретрая (QA-005) — как только первая непустая дельта summary.0 уходит в сокет или срабатывает барьер инструментальной активности, сетевой сбой ProxyRack ([F-46]) на 200–450-й секунде хода уже не может быть повторён и приводит к терминальной ошибке; (в) живая гранулярность прогресса мышления при многосекционном reasoning — при появлении summary.1 и последующих индексов префикс-монотонный фильтр (AD-004) замораживает live-выдачу до конца хода, возвращая клиент к ожиданию на пустых keepalive-чанках до финального согласования.
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт моста заморожен в соответствии с task.json; единственная дельта CD-001 укладывается в разрешение на аддитивные SSE-кадры внутри существующего поля reasoning_content. Пакет полностью соответствует Python-overlay architecture.md, учитывает реальное состояние дерева dev, фиксирует полный набор автотестов (VER-001..VER-007), проверку неизменности защищённых путей (VER-012) и обязательную проверку тяжёлым путём на живом DSH-слоте владельца (VER-009).
ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 0
VERDICT: PASS
ARTIFACT_END>>>

Эксперт Визионер:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/panel/arch/r9/seats/2/verdict.md#L3-L95 sha256=5dd51e92083d21d0cdefdd78a7460576a0b34d50f8fe540388629e3f7b31dd9a

F-001 — Барьер повтора не исключает повторение ненаблюдаемого действия.
- Якоря: architecture-packet.json#AD-003, architecture-packet.json#ASM-010, architecture-packet.json#THREAT-004, architecture-packet.json#QA-005, architecture-packet.json#VER-002.
- Правило: RW-003 требует ограничить разрешение повтора, если инструментальное действие нельзя надёжно обнаружить; разрешение allowAll не означает принятия at-least-once.
- Evidence: ASM-010 признаёт: «действие без любого из этих сигналов до транзиентного сбоя фактами не исключено», однако разрешает повтор при чистом потоке reasoning/agentMessage. Для exec достаточен пустой результат. T-R07 проверяет только действие, сопровождаемое инструментальным item. Отсутствие текста exec также не доказывает отсутствие действия.
- Ожидаемое исправление: до подтверждения полноты и порядка инструментальных событий запрещать повтор после возможного начала исполнения либо обеспечить доказанную дедупликацию. Отдельно определить безопасное условие для exec. Наблюдение первых успешных ходов не считать доказательством отсутствия ненаблюдаемых эффектов.
- Критерий проверки: заглушка выполняет эффект без item/approval и без выходного текста, затем возвращает net-timeout; второго эффекта нет. Альтернатива — явное принятие владельцем семантики дублирования с соответствующим изменением пакета.
- priority: blocking.

F-002 — Таймаут live-записи не ограничивает ожидание общего замка.
- Якоря: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024, architecture-packet.json#VER-003.
- Правило: RW-004 требует ограниченного ожидания синхронного sink и сохранения чтения MSP при медленном клиенте.
- Evidence: timeout 3 с выставляется «на время записи под _wlock» и затем восстанавливается. Через тот же замок идут keepalive и финальная выдача. EVD-024 фиксирует прежний timeout соединения 300 с. Если keepalive уже заблокирован на записи, live-sink сначала ждёт замок и до установки своего трёхсекундного timeout не доходит.
- Ожидаемое исправление: распространить ограничение на все записи, конкурирующие за _wlock; ограничить ожидание замка остатком общего дедлайна. Либо выбрать единственного писателя с ограниченной очередью и явной политикой переполнения.
- Критерий проверки: клиент перестаёт читать; сначала блокируется keepalive, затем приходит summary. Процесс и слот освобождаются за установленный предел, второй клиент обслуживается. Существующего T-L08 только с заполнением live-дельтами недостаточно.
- priority: blocking.

F-003 — Абсолютный бюджет и grace объявлены, но распределение времени допускает их превышение.
- Якоря: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#QA-001, architecture-packet.json#QA-004, architecture-packet.json#BND-003, architecture-packet.json#VER-001, architecture-packet.json#VER-002.
- Правило: RW-002 включает cleanup и финальную выдачу в общий бюджет; RW-008 требует короткого освобождения слота после входа в деградацию.
- Evidence: попытке передаётся весь «остаток до дедлайна», хотя в тот же бюджет входят cleanup и выдача. Запись stdin после turn/start ограничена дедлайном хода, а grace начинается «после отправки turn/cancel или отказного decide». При заблокированном stdin отправка отмены может ждать оставшуюся часть 1800 с ещё до запуска grace. При исчерпании попыткой всего остатка времени на последующие обязательные фазы уже нет.
- Ожидаемое исправление: задать конечные бюджеты записи управляющей команды, завершения группы и финальной выдачи; вычислять дедлайн исполнения с резервом этих фаз. Grace отсчитывать от локального защёлкивания деградации, включая попытку отправки отмены; невозможность записать команду должна вести к принудительной очистке в том же пределе.
- Критерий проверки: добавить остановку чтения stdin перед деградацией и зависание модели до последнего разрешённого момента бюджета. Проверять время от приёма запроса и от защёлкивания деградации до исхода и освобождения слота. Сценарии должны укладываться в заявленные пределы без дополнительного полного grace после общего дедлайна.
- priority: blocking.

F-004 — Разрешена потеря reasoning за пределами допустимой фрагментации контракта.
- Якоря: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#BND-004, architecture-packet.json#RISK-003, architecture-packet.json#VER-003.
- Правило: task envelope разрешает только аддитивные SSE-кадры существующих полей; RW-005 требует согласования snapshot без потерь и дублей.
- Evidence: «если [F не начинается с P] — хвост не отправляется». При опубликованном P=`a` и авторитетном F=`b\n\nc` клиент останется с `a`, потеряет `b\n\nc` и получит успешное завершение. CD-001 при этом называет изменение «аддитивной фрагментацией», хотя меняется само значение reasoning. VER-003 сохраняет отсутствие потерь только «в расширяющем случае».
- Ожидаемое исправление: публиковать до завершения только доказанно устойчивый префикс источника и сохранить авторитетный итоговый текст. Если такой гарантии MSP получить нельзя, вынести изменение семантики расхождения на явное решение владельца новым delta-пакетом; молчаливое усечение успешного ответа не считать совместимой фрагментацией.
- Критерий проверки: несовместимый snapshot содержит дополнительный уникальный текст; проверка подтверждает сохранение согласованного значения без потерь и дублей либо явно утверждённый новый исход. Одного лога расхождения недостаточно.
- priority: blocking.

F-005 — Операционный откат в denyUnmatched может снова включить автоматическое исполнение через exec.
- Якоря: architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#QA-008, architecture-packet.json#VER-001, architecture-packet.json#RISK-001.
- Правило: заявленный переключатель безопасности должен сохранять выбранную политику при деградации транспорта и версии CLI.
- Evidence: AD-007 предлагает denyUnmatched как «быстрый операционный откат политики». AD-006 при отказе явного режима направляет запрос в exec, который остаётся с --yolo. Следовательно, отказ сервера принять denyUnmatched может привести к пути автоматического исполнения. T-A11 и T-A14 проверяют эти ветки раздельно.
- Ожидаемое исправление: в denyUnmatched запретить fallback в exec с --yolo и другие пути, не обеспечивающие выбранный режим; при невозможности сохранить политику завершать запрос контролируемым отказом. Отразить область действия переключателя в rollback и ADR.
- Критерий проверки: сочетание MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched с -32030 и другими setup-сбоями не запускает автоматически разрешающий exec; обычный allowAll сохраняет согласованную ветку fallback.
- priority: blocking.

FIXCHECK RW-001: fixed — architecture-packet.json#AD-003 — fallback ограничен setup до принятого turn/start; VER-002 содержит четыре требуемые запрещённые ветки T-R06.
FIXCHECK RW-002: not-fixed — architecture-packet.json#AD-003 — очередь включена в бюджет, но весь остаток отдаётся исполнению без обеспеченного резерва cleanup и выдачи; F-003.
FIXCHECK RW-003: not-fixed — architecture-packet.json#ASM-010 — ненаблюдаемое действие прямо допускается, но отсутствие сигналов всё ещё разрешает повтор; F-001.
FIXCHECK RW-004: not-fixed — architecture-packet.json#BND-004 — ограничена live-запись после захвата замка, ожидание занятого другим писателем замка остаётся вне этого ограничения; F-002.
FIXCHECK RW-005: not-fixed — architecture-packet.json#CD-001 — interleaved-индексы согласованы, однако несовместимый snapshot приводит к потере авторитетного текста; F-004.
FIXCHECK RW-006: fixed — architecture-packet.json#AD-002 — терминальный исход защёлкивается, предел десяти включает отказной decide, четыре поведения сервера покрыты T-A13.
FIXCHECK RW-007: fixed — architecture-packet.json#VER-009 — приёмка требует реального прогресса во время мышления; диагностика конца хода выделена в VER-011 и приёмку не заменяет.
FIXCHECK RW-008: not-fixed — architecture-packet.json#AD-002 — grace задан, но начинается после отправки команды, сама отправка допускает ожидание до дедлайна хода; F-003.

SUB 1/1.1: FAIL — architecture-packet.json#AD-004 и architecture-packet.json#CD-001 допускают потерю текста под заявлением совместимой фрагментации; F-004.
SUB 1/1.2: FAIL — architecture-packet.json#AD-002 и architecture-packet.json#AD-003 не обеспечивают пределы при заблокированном stdin и исчерпании бюджета; F-003.
SUB 1/1.3: PASS — [F-23], [F-28]–[F-32], [F-35]–[F-37] подтверждают протокольные основания; неизвестность полноты инструментальных событий явно признана в ASM-010.
SUB 2/2.1: FAIL — architecture-packet.json#AD-005 сохраняет ограничения REQ-MUSE-001, но REQ-MUSE-003 и REQ-MUSE-004 требуют исправлений F-001 и F-004.
SUB 2/2.2: FAIL — architecture-packet.json#ASM-010 оставляет существенное для безопасности повтора допущение continuable без безопасного ограничения; F-001.
SUB 3/3.1: PASS — architecture-packet.json#BND-001, architecture-packet.json#BND-002, architecture-packet.json#BND-003 сохраняют реализацию в существующем мосте без новых сервисов и зависимостей.
SUB 3/3.2: FAIL — architecture-packet.json#AD-007 упрощает эксплуатацию, но откат политики не выдерживает fallback AD-006; F-005.
SUB 4/4.1: FAIL — architecture-packet.json#THREAT-004 не закрывает повтор ненаблюдаемых эффектов; сочетание AD-006/AD-007 нарушает ожидаемое ограничение режима; F-001, F-005.
SUB 4/4.2: PASS — architecture-packet.json#THREAT-002 и architecture-packet.json#VER-001 задают ограниченный аудит, редакцию и канареечные проверки; полный аудит действий не обещается.
SUB 4/4.3: FAIL — architecture-packet.json#BND-004 и architecture-packet.json#QA-004 не обеспечивают заявленные пределы ожидания во всех I/O-ветках; F-002, F-003.
SUB 5/5.1: PASS — architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007 содержат минимум две альтернативы и причины выбора; AD-005 унаследован.
SUB 5/5.2: PASS — architecture-packet.json#QA-004 и architecture-packet.json#QA-009 рассматривают насыщение двух слотов; при росте нагрузки ограничителями становятся очередь, длительность удержания слотов и общий внешний прокси.
SUB 6/6.1: FAIL — architecture-packet.json#CD-001 выходит за разрешённую фрагментацию в ветке несовместимого snapshot; F-004.
SUB 6/6.2: FAIL — границы соответствуют фактическому стеку, но architecture-packet.json#THREAT-004 не удовлетворяет требованию Python-overlay об идемпотентности повторов, а CD-001 — ограничению contract delta; F-001, F-004.
SUB 6/6.3: FAIL — architecture-packet.json#VER-001, architecture-packet.json#VER-002, architecture-packet.json#VER-003 требуют дополнительных сочетаний отказов из F-001–F-005; red→green, Full Suite Gate, protected_paths и тяжёлый путь предусмотрены.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Разделение политики, MSP-транспорта и SSE удачно, но правила финального reasoning и временных бюджетов противоречат заявленным гарантиям.
   СОВЕТЫ (при FAIL): обеспечить устойчивый публикуемый префикс; устранить молчаливую потерю snapshot; распределить общий бюджет между исполнением, отменой, очисткой и выдачей.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Все требования трассированы, однако RW-002, RW-003, RW-004, RW-005 и RW-008 закрыты частично. Неизвестность инструментальной активности пока переносится в эксплуатацию вместе с разрешением повторов.
   СОВЕТЫ (при FAIL): ограничить повторы при недоказанной наблюдаемости; добавить проверки ненаблюдаемого эффекта, занятого keepalive-замка, заблокированного stdin, несовместимого snapshot и denyUnmatched вместе с fallback.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Масштаб изменения соответствует одному stdlib-мосту. Но предложенные механизмы пока не обеспечивают обещанные пределы времени и безопасный операционный откат.
   СОВЕТЫ (при FAIL): ограничить все конкурирующие SSE-записи и ожидание замка; запускать grace от защёлкивания отказа; запретить обход denyUnmatched через автоматически разрешающий exec.

4. РИСКИ: VERDICT=FAIL
   WHY=Риск allowAll принят владельцем и описан честно. Принятия повторных побочных эффектов нет; текущий барьер и переключатель отката оставляют дополнительные риски.
   СОВЕТЫ (при FAIL): закрыть F-001–F-003 и F-005; подтвердить отсутствие второго эффекта без инструментального события; проверить сохранение denyUnmatched при отказе session/start.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Для каждого нового AD есть требуемые альтернативы. Выбранный процесс serve на запрос сохраняет мышление и изолирует сбои лучше архитектуры exec-only, которая воспроизводит измеренные потери. Постоянный MSP-брокер с долговечными сессиями мог бы снизить стоимость запусков и открыть восстановление соединения, но потребовал бы управления жизненным циклом, изоляцией и восстановлением состояния за пределами задачи. При росте нагрузки нынешние два слота ограничивают пропускную способность: увеличиваются очередь и число ожидающих HTTP-соединений; повторы увеличивают занятость слотов. Поднятие MAX_CONCURRENT или добавление экземпляров переносит нагрузку на общий нестабильный прокси; локальный лимит не становится глобальным.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Пакет сохраняет фактический стек, существующие профили, ограничения REQ-MUSE-001 и необходимые проверки. Однако усечение reasoning при расхождении snapshot выходит за разрешённую аддитивную фрагментацию.
   СОВЕТЫ (при FAIL): сохранить согласованное значение reasoning либо получить отдельное разрешение на изменение семантики; синхронизировать CD-001, ADR, QA и VER; дополнить поверхность проверки сценариями F-001–F-005.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
COVERAGE: 15/15 подкатегорий
FINDINGS_COMPLETE: 5
VERDICT: NEEDS WORK
ARTIFACT_END>>>

ПРОТОКОЛ ДЕБАТОВ (ответы всех мест всех прошлых раундов):
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/a2/debate-transcript.md sha256=fe6687cab0e879c6da6844974b6b0fa822cdc9af685009f1eb78a288003d966a
## Раунд D1 (r10)

### D1 · Визионер · Anthropic · место 1
RECHECK: seed_hex=29426d37 ranked_order=muse-wonder-full-1.0,claude-sonnet-5-5-high,gemini-4-argon-high,gpt-6.1-sol-high результат=OK

AGREE F-006 rev=1 — проверил: architecture-packet.json#ASM-010, architecture-packet.json#BND-002, architecture-packet.json#EVD-025 — ASM-010 говорит «закрывается сверкой item-kind аудита первых живых ходов». EVD-025 подтверждает, что ServeRun уже различает kind. Но нигде в BND-002, THREAT-001 и arch-spec §4.3 нет требования писать строку на каждый item с kind вне {reasoning, agentMessage}. approval_degraded несёт только флаг tool_activity. Механизм закрытия ASM-010 не описан. Non-blocking, но это закрывающая проверка для моей F-001.

AGREE F-007 rev=1 — проверил: architecture-packet.json#AD-007, architecture-packet.json#EVD-020, evolution.rollback — rollback и AD-007 предписывают «правка env launchd + `launchctl kickstart -k`». Пакет не указывает, где живёт env: в plist или в `~/.dsh/.env`. Kickstart перезапускает процесс, но правки plist по общему знанию не перечитывает. Это я не могу проверить по приложенным материалам. T-A14 проверяет только чтение env внутри процесса. Реальная смена режима на канале деплоя нигде не проверяется. Non-blocking. Он усиливает мою F-005: быстрый откат должен быть проверенным.

AGREE F-008 rev=1 — проверил: architecture-packet.json#AD-003, architecture-packet.json#QA-004, architecture-packet.json#BND-003 — порог 30 с одновременно означает «handshake-окно» и «минимальный остаток для старта из очереди и повтора». Минимальный успешный ход wonder — 51.1 с ([F-14]). AD-003 заявляет, что дедлайн «включает grace, cleanup и финальную выдачу», хотя попытке отдаётся весь остаток. Часть про резерв фаз входит в мою F-003 (blocking); сам порог 30 с остаётся non-blocking.

AGREE F-009 rev=1 — проверил: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-09], [F-10], [F-38] — exec запускается с `--disable-web-tools --disable-reminders`, serve без них. THREAT-001 называет network и webSearch, но не говорит, что прежний exec-путь эти инструменты отключал. Альтернатива `-c/--config` не рассмотрена. Non-blocking: риск allowAll принят владельцем (EVD-009), нужна только явная запись и альтернатива.

DISPUTE F-010 — класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — это тот же root cause, что и F-002. Лимит 3 с применён только к live-записи, а keepalive и финал идут через тот же `_wlock` с timeout 300 с ([F-004]/EVD-024). Критерий проверки тот же: первым блокируется keepalive, потом приходит summary. Находки нужно слить. Приоритет оставить blocking по F-002: RW-004 из R1 остаётся not-fixed.

AGREE F-011 rev=1 — проверил: architecture-packet.json#AD-002, [F-28], arch-spec.md §2.3–§2.4 — AD-002 перечисляет триггеры защёлкивания -32050/-32052/-32053 и benign -32051. -32054 и -32030 из [F-28] не названы. §2.3 формулирует общее правило «любая error кроме -32051». Тексты расходятся, и общее правило нужно закрепить. Non-blocking.

AGREE F-012 rev=1 — проверил: architecture-packet.json#evolution.rollout, architecture-packet.json#evolution.rollback, architecture-packet.json#AD-007 — env-выключатель есть только для режима approval. Для транзиентного повтора и live-reasoning возврат возможен лишь полным redeploy. Это значимо для моей F-004: выключатель live позволил бы откатить спорную семантику reasoning без отката approval. Этапность коммитов и выключатели — рекомендации, поэтому non-blocking.

AGREE F-013 rev=1 — проверил: architecture-packet.json#RISK-007, architecture-packet.json#VER-011, architecture-packet.json#ASM-004 — по VER-009 при summary только в конце хода REQ-MUSE-004 равен NOT_MET. AD-004 вместе с T-L01..L08 строится до проверки этого факта, а проверка стоит одной строки лога. Рекомендация разумная. Non-blocking.

AGREE F-014 rev=1 — проверил: architecture-packet.json#EVD-015, architecture-packet.json#AD-004 (drivers), architecture-packet.json#CD-001, architecture-packet.json#ASM-003, [F-47] — EVD-015 и CD-001 подают «клиент DSH live reasoning_content уже потребляет» как факт, тогда как ASM-003 помечает это ASSUMED. [F-47] фиксирует только комментарий кода. Формулировку «доказано» в drivers AD-004 нужно заменить на «по комментарию кода». Это усиливает F-004: совместимость CD-001 опирается на допущение. Non-blocking.

AGREE F-015 rev=1 — проверил: architecture-packet.json#AD-002, #AD-003, #AD-004, #AD-006, #AD-007 (drivers и alternatives) — голые «F-006», «F-011», «F-002», «F-003», «F-005», «F-012», «F-009», «F-020» означают находки панели a1. Рядом стоят «F-NN в ledger» и [F-NN]. Текущий леджер тоже использует F-001..F-017, поэтому коллизия растёт. Нужен префикс PF-. Non-blocking.

AGREE F-016 rev=1 — проверил: arch-spec.md (шапка: «Нумерация: AD-001..AD-006»; строка статуса «повторный ARCH_GATE впереди»), architecture-packet.json#AD-007, receipts/arch-gate-a2.json — AD-007 существует, receipt со статусом PASS приложен. Шапка и статус устарели. По sha: materialization[0].sha256 в пакете равен 4754421f…, и приложенный ADR 0003 имеет тот же sha. Расхождение с `fcf1aea8…` из delta-a2.md не могу проверить, этот файл не приложен. Подтверждаю только часть про шапку и статус. Non-blocking.

AGREE F-017 rev=1 — проверил: architecture-packet.json#AD-002, #AD-003, #AD-004 (alternatives), ASM-010 — у каждого AD есть ≥2 альтернативы, формально критерий выполнен. Подрешения без собственной альтернативы: grace 15 с и барьер активности против запрета повтора после любого `turn/start`. Контингенция «ужесточить до turn/start» названа только в ASM-010, в alternatives её нет. После исправления F-001 она станет реальной альтернативой, и её надо вынести в AD-003. Non-blocking.

Q→Скептик: F-002 architecture-packet.json#BND-004 — в FIXCHECK RW-004 ты признал `fixed` по `LIVE_WRITE_TIMEOUT_S=3` с «под `_wlock`». Если keepalive-поток уже заблокирован в `wfile.write` на переполненном буфере (timeout соединения 300 с по EVD-024) и держит `_wlock`, где в BND-004 ограничено ожидание этого замка со стороны sink?

Q→Скептик: F-001 architecture-packet.json#ASM-010 — в SUB 4/4.3 ты принял барьер как закрывающий RW-003. ASM-010 прямо допускает действие без item, approval и непустого текста exec и всё же разрешает повтор. Какой пункт AD-003 или T-R07 проверяет повтор при чистом потоке reasoning/agentMessage, когда эффект произошёл без item?

Q→Реалист: F-005 architecture-packet.json#AD-006 — в F-2 ты рекомендуешь «учение» с `denyUnmatched`. AD-006 при -32030 уводит ход в exec-fallback с `--yolo` ([F-09]). Считаешь ли ты откат в `denyUnmatched` честным без запрета этого fallback, и проверяют ли T-A11 и T-A14 такое сочетание?

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Позиция R1 не изменилась. Правило F.startswith(P) (AD-004/CD-001) молча усекает reasoning (F-004). Бюджет и grace не защищены от блокировки stdin и исчерпания остатка (F-003). Лимит 3 с не покрывает ожидание `_wlock` (F-002; Реалист F-010 — тот же дефект). Слабая опора на клиента (F-014) усиливает F-004.
   СОВЕТЫ (при FAIL): исправить F-002, F-003, F-004; формулировки CD-001 и EVD-015 привести к статусу ASM-003 (F-014).
2. ПОЛНОТА: VERDICT=FAIL
   WHY=Повтор после ненаблюдаемого действия не закрыт (F-001). Механизма закрытия ASM-010 нет (F-006). Сочетание denyUnmatched и fallback в exec не покрыто тестами (F-005). Не проверены занятый keepalive-замок и заблокированный stdin (F-002, F-003).
   СОВЕТЫ (при FAIL): добавить T-сценарии по F-001, F-002, F-003, F-005; ввести строку item-kind в аудит (F-006); единым правилом описать ошибки decide и cancel (F-011).
3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Объём укладывается в один stdlib-мост. Но обещанные пределы времени достижимы не во всех I/O-ветках (F-002, F-003). Откат политики не проверен на канале деплоя и обходится fallback в exec (F-005, F-007). Поставка без этапов и без выключателей live/retry (F-012).
   СОВЕТЫ (при FAIL): ограничить ожидание замка и запись управляющих команд; уточнить последовательность отката и проверить её учением (F-007); разбить поставку на этапы и добавить выключатели (F-012).
4. РИСКИ: VERDICT=FAIL
   WHY=Allowall принят владельцем. Остаются риск дублирования ненаблюдаемого эффекта (F-001), автоматического exec при откате в denyUnmatched (F-005) и неназванная асимметрия web-инструментов serve и exec (F-009).
   СОВЕТЫ (при FAIL): закрыть F-001 и F-005; записать асимметрию и альтернативу `--config` (F-009); добавить аудит item-kind (F-006).
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового AD есть ≥2 альтернативы с причиной выбора. Арх-уровневое сравнение: exec-only воспроизводит измеренные потери; постоянный брокер MSP вынесен за рамки. При росте нагрузки ограничителями становятся два слота, очередь и общий нестабильный прокси; увеличение MAX_CONCURRENT переносит нагрузку на прокси. Подрешения без отдельных альтернатив (F-017) — non-blocking.
   СОВЕТЫ (при FAIL): —
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Ветка расхождения snapshot в CD-001 выходит за допустимую аддитивную фрагментацию (F-004). THREAT-004 не удовлетворяет требованию Python-overlay об идемпотентности повторов (F-001). Текст spec и коллизия идентификаторов (F-015, F-016) — non-blocking.
   СОВЕТЫ (при FAIL): исправить F-001 и F-004; привести шапку arch-spec и статус к фактическому (F-016); переименовать находки панели в PF-NNN (F-015).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 12/12
ANSWERS: 0/0
VERDICT: NEEDS WORK

### D1 · Реалист · Google · место 2
Подтверждаю: прочитал общий канон ~/Мой диск/Context/AGENTS.md целиком до <!-- КАНОН-КОНЕЦ --> и проектные правила (AGENTS.md, .agents/AGENTS.md, .agents/CLAUDE.md, CLAUDE.md — в рабочей папке отсутствуют).

DISPUTE F-001 — класс: invalid — контр-evidence: architecture-packet.json#AD-003, architecture-packet.json#ASM-010, architecture-packet.json#THREAT-004, architecture-packet.json#EVD-005, architecture-packet.json#EVD-025, [F-09], [F-13], [F-14], [F-35] — почему неверно: в модели чёрного ящика внешнего CLI-процесса требование Визионера («заглушка выполняет эффект без item/approval и без выходного текста, затем возвращает net-timeout; второго эффекта нет») невозможно выполнить иначе как полным запретом повторов после `turn/start` на `serve` и после запуска `exec`. Поскольку все `net-timeout` в логах и бенче происходят во время активного хода на 20–452-й секунде ([F-13], [F-14], architecture-packet.json#EVD-011), запрет повтора после возможного начала исполнения делает целевое требование REQ-MUSE-003 невыполнимым. Пакет уже использует все наблюдаемые сигналы протокола MSP (`item/started|completed` с `kind` вне `{reasoning, agentMessage}`, `approval/request|requested`, `userInput/request`, `approval/decide` по [F-35] и architecture-packet.json#EVD-025) при отключённых хостом `--disable-write --disable-shell` на `serve` и дополнительно `--disable-web-tools --disable-reminders` на `exec` ([F-09], architecture-packet.json#EVD-005), а неизвестность полного каталога инструментов до живого хода (OPEN-01) имеет согласованный класс `continuable` (`architecture-packet.json#ASM-010`). Добавление явного логирования инструментальных `item` для закрытия ASM-010 уже учтено в неблокирующей F-006.
AMEND F-002 — priority=non-blocking; locations=architecture-packet.json#AD-004,architecture-packet.json#BND-004,architecture-packet.json#EVD-024,architecture-packet.json#VER-003; fix=применять предел LIVE_WRITE_TIMEOUT_S=3 с внутри общего метода Handler._sse_write под _wlock ко всем записям открытого стрима (keepalive, live-sink, финальная выдача) и дополнить T-L08 случаем, когда на заполненном буфере первым блокируется keepalive-кадр — причина: architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — техническое наблюдение верно и совпадает с моей неблокирующей находкой F-010 (F-5 в R1), однако не блокирует архитектуру: все SSE-записи уже централизованы в единственном методе `Handler._sse_write` под `_wlock` с конечным `Handler.timeout=300` с (pre-existing по architecture-packet.json#EVD-024), поэтому распространение `settimeout(3)` на сам `_sse_write` не меняет ни границ компонентов BND-002/BND-004, ни контрактов пакета и прямо ложится в реализацию Coder.
AMEND F-003 — priority=non-blocking; locations=architecture-packet.json#AD-002,architecture-packet.json#AD-003,architecture-packet.json#QA-001,architecture-packet.json#QA-004,architecture-packet.json#BND-003; fix=отсчитывать APPROVAL_CANCEL_GRACE_S=15 с от момента локального защёлкивания деградации (ограничивая запись отказного decide или turn/cancel и ожидание turn/completed единым пределом min(deadline, latch_ts + 15 с)) и явно уточнить в AD-003 и QA-004, что пост-дедлайновый cleanup и финальная выдача укладываются в 100-секундный запас между TIMEOUT_S=1800 с и клиентским лимитом 1900 с — причина: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#EVD-016, [F-19] — в пакете уже заложен запас 100 с между дедлайном моста 1800 с и клиентским таймаутом 1900 с (`architecture-packet.json:378`, [F-19]), а `APPROVAL_CANCEL_GRACE_S=15` с уже ограничен общим дедлайном запроса (`architecture-packet.json:365`); кроме того, суммарный объём управляющих JSON-RPC команд в stdin за ход (<4 КБ при лимите 10 decide и 3 cancel) меньше буфера pipe ОС (16–64 КБ). Включение отправки команды отмены в само окно grace 15 с и уточнение формулировки буфера 100 с (перекликающееся с моей F-008) не меняют архитектурных решений и являются неблокирующим уточнением.
DISPUTE F-004 — класс: invalid — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#BND-004, [F-17], [F-35] — почему неверно: по замороженному OpenAI SSE-контракту (`architecture-packet.json#CD-001`) поток `delta.reasoning_content` является строго append-only, и отозвать уже отправленный в сокет префикс `P` невозможно. В схеме MSP ([F-35]) нет протокольного признака «доказанно неизменяемого префикса» до конца хода, поэтому требование публиковать дельты только при абсолютной гарантии совпадения с будущим `item/completed` равносильно возврату к полной буферизации до конца хода ([F-17]) и прямо противоречит REQ-MUSE-004. Во всех штатных сценариях MSP (последовательные и перемешанные индексы `0:a -> 1:b -> 0:c`, `item/completed` без дельт, `item/completed`, повторяющий или расширяющий дельты) алгоритм заморозки после `summary.0` в `architecture-packet.json#AD-004` сохраняет условие `F.startswith(P)` и доставляет полный текст без потерь и дублей (T-L01, T-L02, T-L06), а ветка `not F.startswith(P)` является исключительно защитой от дублирования при аномальном ответе сервера, переписавшего уже отправленный префикс.
AMEND F-005 — priority=non-blocking; locations=architecture-packet.json#AD-006,architecture-packet.json#AD-007,architecture-packet.json#QA-008,architecture-packet.json#VER-001; fix=при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched не выполнять fallback в exec при ошибке -32030 на session/start (завершать ход контролируемой ошибкой) и уточнить в AD-007 и evolution.rollback, что переключатель задаёт политику serve-сессии — причина: architecture-packet.json#AD-005, architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#EVD-005, architecture-packet.json#EVD-008, [F-09], [F-30], [F-31] — на актуальных версиях CLI 1.4.7 и 1.4.8 режим `denyUnmatched` доказанно принимается `session/start` без `-32030` ([F-30], [F-31], architecture-packet.json#EVD-008), сам переключатель AD-007 добавлен как дополнительное операционное удобство по неблокирующему замечанию прошлого цикла (FU-011), а `exec`-путь уже работает с `--disable-write --disable-shell --disable-web-tools --disable-reminders` ([F-09], architecture-packet.json#AD-005). Запрет перехода в `exec` по `-32030` при явно выставленном `denyUnmatched` — полезное, но неблокирующее уточнение краевой ветки.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Архитектурные решения AD-001..AD-007 непротиворечивы, опираются на проверенные факты леджера [F-01]..[F-52] и закрывают все 8 обязательных доработок RW-001..RW-008. Единый предикат допуска нового процесса (architecture-packet.json#AD-003, #BND-003) исключает запуск exec после принятого turn/start и после любого approval-трафика; терминальное защёлкивание отказа и лимит 10 decide (включая финальный отказной) обеспечивают ровно один терминальный исход (architecture-packet.json#AD-002); префикс-монотонная публикация summary.0 до заморозки (architecture-packet.json#AD-004, #CD-001) сохраняет порядок и полноту reasoning без дублей. Замечания F-002, F-003, F-005 уточнены как non-blocking, а F-001 и F-004 оспорены как противоречащие реализуемости REQ-MUSE-003 и REQ-MUSE-004 в рамках протоколов MSP и OpenAI SSE.
   СОВЕТЫ (при FAIL): нет
2. ПОЛНОТА: VERDICT=PASS
   WHY=Целевые требования REQ-MUSE-002 (AD-001, AD-002, AD-006, AD-007), REQ-MUSE-003 (AD-003) и REQ-MUSE-004 (AD-004, CD-001) полностью покрыты и протрассированы до сценариев качества QA-001..QA-009 и проверок VER-001..VER-012; ограничения REQ-MUSE-001 сохранены в AD-005. Приёмка живого прогресса (VER-009) строго отделена от диагностики времени прихода первой дельты (VER-011), а все допущения ASM-001..ASM-010 и открытые вопросы Q-001..Q-009 явно оформлены.
   СОВЕТЫ (при FAIL): нет
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Все изменения локализованы в существующем stdlib-мосте `bridges/muse-bridge/server.py` (границы ApprovalPolicy, ServeRun, Handler) и тестовом файле `tests/test_muse_bridge_killpg.py` без новых внешних зависимостей и сервисов. План выката (evolution.rollout) отделяет незакоммиченный baseline REQ-MUSE-001 (2941 строка, [F-51]) отдельным коммитом шага 0, предусматривает бэкап и быстрый откат политики через `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` (AD-007).
   СОВЕТЫ (при FAIL): нет
4. РИСКИ: VERDICT=PASS
   WHY=Модель угроз THREAT-001..THREAT-004 и реестр рисков RISK-001..RISK-008 закрывают основные эксплуатационные и безопасor-сценарии: сохранены флаги `--disable-write --disable-shell` и песочница хоста ([F-09], EVD-005), введены барьер инструментальной активности (AD-003), allowlist-рендер `toolName` и `choiceId` без `rawArgs` (BND-001, THREAT-002), принудительное завершение группы через `APPROVAL_CANCEL_GRACE_S=15` с (AD-002, THREAT-003) и отсечка медленного клиента за `LIVE_WRITE_TIMEOUT_S=3` с (AD-004, BND-004).
   СОВЕТЫ (при FAIL): нет
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=У каждого нового решения (AD-001, AD-002, AD-003, AD-004, AD-006, AD-007) приведено не менее двух содержательных альтернатив с причиной выбора и отказа. На уровне архитектуры системы выбранная схема (процесс `muse serve` на запрос с `allowAll` и внутриходовым `ApprovalPolicy`, синхронный префикс-монотонный live-sink под 3-секундным socket timeout и ограниченный повтор в `Handler` внутри удерживаемого слота) сопоставлена с двумя альтернативными архитектурами: (1) Архитектура `exec`-only или пассивного отказа `denyUnmatched` на уровне сессии с деградацией в `exec` — отвергнута, так как `exec`-рестарт воспроизводит потерю 275–412 с мышления и до 2242 с повтора ([F-06], [F-07], EVD-003) и не даёт `summary.N` для живого прогресса, а `denyUnmatched` блокирует целевой инструмент модели с неизвестным исходом хода ([F-33], [F-50]); (2) Архитектура выделенного асинхронного потока-писателя с очередью SSE-кадров и повтором после первой live-дельты с подавлением префикса — отвергнута в AD-003 и AD-004, поскольку генерация на второй попытке недетерминирована и не гарантирует совпадения префикса reasoning, а отдельная очередь усложняет синхронизацию с финальным `_send_sse` ради того же 3-секундного предела backpressure. При росте нагрузки в выбранной архитектуре последовательно ломаются: (а) очередь слотов при `MAX_CONCURRENT=2` ([F-21]) — при двух длительных ходах или сериях ретраев третий и последующие запросы ждут освобождения слота и отсекаются по порогу остатка ≤30 с до абсолютного дедлайна 1800 с с ошибкой 503 / SSE error (QA-004, T-R08); (б) доступность транзиентного повтора (QA-005) — после первой отправленной дельты `summary.0` или срабатывания барьера инструментальной активности сбой нестабильного внешнего прокси `127.0.0.1:10816` ([F-46]) уже не может быть повторён без нарушения идемпотентности SSE; (в) живая гранулярность прогресса мышления на многосекционных summaries — после прихода `summary.1` префикс-монотонный фильтр замораживает выдачу дельт до конца хода (AD-004).
   СОВЕТЫ (при FAIL): нет
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт моста (`/v1/chat/completions`, `/health`, `/v1/models`) заморожен по `task.json`, единственная контрактная дельта CD-001 укладывается в разрешение на аддитивные SSE-кадры внутри существующего поля `reasoning_content`. Пакет соответствует Python-overlay `architecture.md` с учётом фактического stdlib-стека, защищает `protected_paths` (VER-012) и требует полной проверки red→green, Full Suite Gate и живого прогона тяжёлым путём владельцем (VER-009).
   СОВЕТЫ (при FAIL): нет
ОБЩИЙ ВЕРДИКТ: PASS
POSITIONS: 5/5
ANSWERS: 0/0
VERDICT: PASS

### D1 · Скептик · OpenAI · место 3

AGREE F-001 rev=1 — проверил: architecture-packet.json#ASM-010, architecture-packet.json#AD-003, architecture-packet.json#THREAT-004 — отсутствие инструментального события прямо не гарантирует отсутствия действия, однако разрешает повтор; пустой результат exec также не доказывает безопасность повторного исполнения. ARG: Визионер/R1 «Наблюдение первых успешных ходов не считать доказательством отсутствия ненаблюдаемых эффектов». Это меняет мою прежнюю оценку RW-003: аудит выборки помогает диагностике, но не устанавливает гарантию идемпотентности.

AGREE F-002 rev=1 — проверил: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — timeout устанавливается после захвата общего замка; ожидающий sink не ограничен собственными тремя секундами, если замок удерживает keepalive с прежним timeout. ARG: Визионер/R1 «Если keepalive уже заблокирован на записи, live-sink сначала ждёт замок». Прежнее признание RW-004 полностью закрытым пересматриваю: ограничение отдельного писателя не ограничивает всю цепочку ожидания.

AGREE F-003 rev=1 — проверил: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#QA-004 — весь остаток бюджета передаётся попытке, хотя cleanup и финальная выдача заявлены внутри того же бюджета; grace начинается после отправки команды, запись которой может ждать дедлайна хода. ARG: Визионер/R1 «При заблокированном stdin отправка отмены может ждать оставшуюся часть 1800 с ещё до запуска grace». Следовательно, декларация абсолютного дедлайна пока не обеспечивает его выполнение; прежние оценки RW-002 и RW-008 пересматриваю.

AGREE F-004 rev=1 — проверил: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#VER-003 — при несовместимом snapshot авторитетный остаток не отправляется, а успешное завершение не запрещено. ARG: Визионер/R1 «клиент останется с `a`, потеряет `b\n\nc` и получит успешное завершение». Префикс-монотонность опубликованного потока не доказывает сохранение исходного значения reasoning; прежнее признание RW-005 полностью закрытым пересматриваю.

AGREE F-005 rev=1 — проверил: architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#VER-001 — denyUnmatched ограничивает session/start и ApprovalPolicy, но общий fallback по setup-сбою остаётся exec с --yolo. ARG: Визионер/R1 «T-A11 и T-A14 проверяют эти ветки раздельно». Переключатель, заявленный как откат политики, должен сохранять ограничение и при выборе другого транспорта.

AMEND F-006 — priority=non-blocking; locations=architecture-packet.json#ASM-010,architecture-packet.json#BND-002,architecture-packet.json#VER-009; fix=определить безопасный журнал наблюдаемых инструментальных item, счётчик на ход и канареечную проверку отсутствия аргументов; явно назвать этот журнал наблюдением событий, не доказательством полноты инструментального аудита — причина: architecture-packet.json#ASM-010 обещает закрытие через item-kind аудит, но architecture-packet.json#THREAT-001 справедливо не обещает полного аудита действий. Этот механизм полезен отдельно от обязательного исправления F-001 и не заменяет его.

AMEND F-007 — priority=non-blocking; locations=architecture-packet.json#AD-007,architecture-packet.json#VER-008,architecture-packet.json#BND-005; fix=указать точный источник переменной и процедуру применения изменения оператором; добавить обратимое учение denyUnmatched→allowAll с подтверждением эффективного режима нового процесса и новой сессии — причина: architecture-packet.json#AD-007 задаёт только «правка env launchd и перезапуск», а architecture-packet.json#VER-008 проверяет лишь allowAll. Утверждение, что именно kickstart обязательно не применит изменение, по представленным данным подтвердить нельзя.

AMEND F-008 — priority=non-blocking; locations=architecture-packet.json#AD-003,architecture-packet.json#QA-004; fix=оставить здесь только эффективность допуска попытки с малым остатком: явно описать компромисс и способ подобрать порог по наблюдаемым длительностям; противоречие общего дедлайна исправлять в F-003; не устанавливать обязательные 120 с без основания — причина: [F-43] содержит успешные serve-ходы за 8–94 с, поэтому 51,1 с из exec-бенча [F-14] не является нижней границей полезного хода. Остаток 31 с не гарантирует бесполезность запуска, хотя для длинного Wonder риск потратить квоту высок.

DISPUTE F-009 — класс: invalid — контр-evidence: architecture-packet.json#EVD-005 прямо перечисляет дополнительные запреты web/reminders у exec; architecture-packet.json#THREAT-001 прямо описывает webSearch, сеть и отправку данных наружу при allowAll — асимметрия и её существенное последствие уже представлены. [F-38] подтверждает существование универсального --config, но не существование ключа отключения этих инструментов. Исследовать такой ключ можно, однако его нерассмотрение само по себе не доказывает дефект принятой границы.

DISPUTE F-010 — класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — тот же корень: общий замок занят писателем, на которого трёхсекундный предел не распространён. Keepalive, финальную выдачу и проверку ожидания замка следует включить в единое исправление F-002.

AMEND F-011 — priority=non-blocking; locations=architecture-packet.json#AD-002,architecture-packet.json#VER-001; fix=согласовать общее правило обработки ошибок с перечислением кодов: любая ошибка approval/decide, кроме -32051, защёлкивает отказ; ошибки userInput/cancel также должны иметь явный терминальный путь; добавить параметризацию по кодам [F-28], включая -32054 и -32030 — причина: architecture-packet.json#AD-002 перечисляет только -32050/-32052/-32053. Исключение approvalAlreadyResolved нельзя без отдельного основания переносить на другие команды.

DISPUTE F-012 — класс: invalid — контр-evidence: architecture-packet.json#BND-005 предусматривает отдельный baseline и ограниченную зону изменения, architecture-packet.json#AD-007 предусматривает откат политики, а полный файловый откат описан в пакете — отсутствие дополнительных выключателей retry/live не означает отсутствия пути отката. Python-overlay прямо устанавливает: «порядок реализации формирует Orchestrator/Coder по утверждённому packet». Этапные коммиты и дополнительные выключатели могут быть полезны, но обязательность обоих предложений из приведённых правил не следует.

AGREE F-013 rev=1 — проверил: architecture-packet.json#ASM-004, architecture-packet.json#RISK-007, architecture-packet.json#VER-011 — источник pre-terminal прогресса остаётся допущением, а отрицательный результат блокирует приёмку всей группы требований. Ранняя проверка временных меток до реализации AD-004 уменьшит риск построить механизм, которому источник не предоставляет нужных данных. Проверку следует проводить ходом владельца; диагностическое закрытие вопроса по-прежнему не заменяет приёмку.

AGREE F-014 rev=1 — проверил: architecture-packet.json#EVD-015, architecture-packet.json#ASM-003, architecture-packet.json#AD-004, architecture-packet.json#CD-001 — [F-18] подтверждает реализацию отправителя, а не наблюдение клиентского накопления; [F-47] фиксирует комментарий кода и неизвестность idle-watchdog. Формулировки «уже потребляет» и «доказано» сильнее приложенного evidence и должны соответствовать статусу допущения.

AGREE F-015 rev=1 — проверил: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007 — трёхзначные ссылки на находки предыдущей панели используются рядом с фактами ledger без единообразного обозначения источника. Это дефект трассировки, а не отсутствие самих фактов: следует различить пространства идентификаторов и сохранить ссылки на исходную панель.

AMEND F-016 — priority=non-blocking; locations=architecture-packet.json#AD-007,architecture-packet.json#EVD-023; fix=обновить шапку arch-spec до AD-001..AD-007 и привести статус ARCH_GATE к приложенному receipt; снять утверждение о доказанном расхождении материализации — причина: приложенный ADR имеет sha256 4754421f51b6bce05710efdc273dd17a83c6ed773b6a93775394c77c795c0b2b, совпадающий с materialization пакета. Содержимое delta-a2.md здесь не приложено, поэтому его предполагаемое расхождение проверить нельзя.

DISPUTE F-017 — класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004 — каждый из этих новых AD содержит не менее двух альтернатив и причины отказа; сама находка признаёт выполнение этого условия. Приведённые правила не устанавливают отдельный минимум альтернатив для каждого параметра или механизма внутри AD. Исправления F-001–F-004 потребуют пересмотреть соответствующие компромиссы, но это не подтверждает самостоятельный дефект отсутствия альтернатив в текущем формате пакета.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=architecture-packet.json#AD-002 и #AD-003 не обеспечивают заявленное распределение временного бюджета; #AD-004 допускает успешный поток с потерей авторитетного reasoning. Основания: F-003, F-004.
   СОВЕТЫ (при FAIL): зарезервировать время отмены, очистки и финальной выдачи; ограничить управляющие записи; отсчитывать grace от локального защёлкивания отказа; обеспечить устойчивость публикуемого префикса либо согласовать отдельный исход при несовместимом snapshot вместо молчаливого усечения.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Требования, границы, QA и VER протрассированы, однако verification surface проверяет наблюдаемый эффект и отдельные ветки, пропуская существенные сочетания отказов. Основания: architecture-packet.json#VER-001, #VER-002, #VER-003; F-001–F-005.
   СОВЕТЫ (при FAIL): добавить сценарии эффекта без событий и текста, keepalive с занятым замком, заблокированного stdin, исчерпания бюджета перед cleanup, несовместимого snapshot и denyUnmatched вместе с setup-fallback; уточнить механизм наблюдения ASM-010 по F-006.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Реализация внутри существующего stdlib-моста достижима, но предложенная синхронная цепочка I/O пока не обеспечивает обещанные пределы освобождения процессов и слотов; переключатель отката не сохраняет политику на всех путях. Основания: architecture-packet.json#BND-003, #BND-004, #AD-007; F-002, F-003, F-005.
   СОВЕТЫ (при FAIL): ограничить ожидание общего замка и все конкурирующие записи; задать конечные бюджеты управляющих операций и завершения группы; запретить автоматически разрешающий exec в denyUnmatched; конкретизировать применение env и проверить откат по F-007.

4. РИСКИ: VERDICT=FAIL
   WHY=Владелец принял allowAll в пределах инструментов хоста, но не повторение побочных эффектов и не обход операторского denyUnmatched. Наблюдаемый барьер недостаточен для заявленной безопасности повторов, а медленный клиент способен задержать чтение MSP через другого писателя. Основания: architecture-packet.json#THREAT-003, #THREAT-004, #ASM-010; F-001–F-003, F-005.
   СОВЕТЫ (при FAIL): до доказанной наблюдаемости или дедупликации запрещать повтор после возможного начала исполнения, отдельно определить безопасное условие для exec; проверить отсутствие второго эффекта без сигналов; устранить блокировки и сохранить выбранную политику при всех setup-сбоях.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Все новые AD содержат минимум две альтернативы с обоснованием. Выбранный serve на запрос сохраняет состояние мышления лучше exec-only, который воспроизводит измеренный перезапуск [F-06], [F-07]. Архитектура с единственным SSE-писателем и ограниченной очередью отделяет чтение MSP от клиента, но добавляет управление переполнением и финализацией; текущий синхронный вариант проще, однако требует исправления F-002. При росте нагрузки два длинных хода или серии повторов занимают оба слота: растут очередь и число ожидающих HTTP-соединений, запросы достигают дедлайна. Увеличение числа экземпляров переносит нагрузку на общий нестабильный прокси [F-46]; локальный лимит 2 не ограничивает суммарную нагрузку нескольких экземпляров.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Фактический стек, границы ответственности, REQ-MUSE-001, protected_paths, Full Suite Gate и живой путь проверки учтены. Однако architecture-packet.json#CD-001 допускает изменение значения reasoning, тогда как task envelope разрешает только аддитивные SSE-кадры существующих полей. Основание: F-004.
   СОВЕТЫ (при FAIL): обеспечить сохранение согласованного значения reasoning при фрагментации либо получить явное разрешение на иную семантику отдельным delta-пакетом; синхронизировать AD-004, CD-001, QA и VER; исправить завышенные утверждения об evidence по F-014 и неоднозначность ссылок по F-015.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 17/17
ANSWERS: 0/0
VERDICT: NEEDS WORK

## Раунд D2 (r12)

### D2 · Скептик · Anthropic · место 1

Подтверждаю: полный текст канона ~/Мой диск/Context/AGENTS.md получен мной до `<!-- КАНОН-КОНЕЦ -->`. Проектные файлы правил (AGENTS.md, .agents/AGENTS.md, .agents/CLAUDE.md, CLAUDE.md) в рабочей папке не найдены: `ls` показал только manifest.json и seats.

RECHECK: seed_hex=fbee25ca ranked_order=claude-sonnet-5-5-high,muse-wonder-full-1.0,gemini-4-argon-high,gpt-6.1-sol-high результат=OK

AMEND F-001 — priority=non-blocking; locations=architecture-packet.json#ASM-010, architecture-packet.json#AD-003, architecture-packet.json#THREAT-004, architecture-packet.json#VER-009; fix=(1) вынести контингенцию «ужесточить барьер до принятого turn/start» в alternatives AD-003 с условием срабатывания (первый же контрпример в логе item-kind из F-006); (2) закрыть ASM-010 через журнал item-kind (F-006) и выборку в VER-009; (3) в ASM-010 прямо записать, что эффект без item/approval-сигнала протоколом не наблюдается — причина: architecture-packet.json#AD-003, architecture-packet.json#EVD-025, architecture-packet.json#EVD-005 — ARG: Реалист/D1 «невозможно выполнить иначе как полным запретом повторов после `turn/start` на `serve` и после запуска `exec`». Моя проверка: net-timeout в логах приходит на 20–452 с активного хода ([F-13], EVD-011), поэтому запрет повтора после любого turn/start делает REQ-MUSE-003 пустым. ServeRun уже различает kind у item/started и item/completed (EVD-025), а ItemKind включает toolCall и webSearch ([F-35]), так что инструментальное действие в штатном протоколе имеет item. Тест на эффект без item проверяет нарушение протокола сервером. Остаток явно назван в ASM-010 и имеет путь ужесточения. На exec write, shell, web и reminders выключены (EVD-005), так что побочные эффекты там ограничены.

AMEND F-002 — priority=non-blocking; locations=architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024, architecture-packet.json#VER-003; fix=применить LIVE_WRITE_TIMEOUT_S=3 с ко всем записям под `_wlock` (keepalive, live, финал) внутри `_sse_write`; исправить формулировку AD-004 «не дольше 3 с на кадр», которая сейчас неверна при занятом замке; добавить в T-L08 случай, когда первым зависает keepalive — причина: architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — ARG: Реалист/D1 «все SSE-записи уже централизованы в единственном методе `Handler._sse_write` под `_wlock` с конечным `Handler.timeout=300` с (pre-existing по architecture-packet.json#EVD-024)». Моя проверка по EVD-024 (`server.py:1992`, `:1953`): ожидание замка конечно, 300 с, и после него клиент считается ушедшим. Дедлайн хода 1800 с не срывается, а новая поверхность отказа ограничена задержкой освобождения слота. Текст гарантии «3 с» всё равно надо поправить, иначе он вводит в заблуждение.

AMEND F-003 — priority=non-blocking; locations=architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#QA-001, architecture-packet.json#QA-004, architecture-packet.json#BND-003; fix=отсчитывать APPROVAL_CANCEL_GRACE_S от момента локального защёлкивания (ожидание = min(дедлайн, latch_ts+15 с)); при невозможности записать команду сразу идти к убийству группы; в AD-003 и QA-004 записать, что cleanup и финальная выдача после дедлайна укладываются в запас 100 с до 1900 с — причина: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#EVD-016 — ARG: Реалист/D1 «суммарный объём управляющих JSON-RPC команд в stdin за ход (<4 КБ при лимите 10 decide и 3 cancel) меньше буфера pipe ОС (16–64 КБ)». Моя проверка: размер decide и cancel задаётся схемой [F-28] и ограничен счётом 10 и 3 (AD-002). Блокирующая запись возможна, только если pipe переполнен, а это практически недостижимо при таком объёме. Остаётся неточность формулировки «дедлайн включает cleanup» при том, что попытке отдаётся весь остаток.

AMEND F-004 — priority=non-blocking; locations=architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#VER-003, architecture-packet.json#RISK-003; fix=в CD-001 и ADR явно записать, что при F, не начинающемся с P, стрим остаётся с отправленным префиксом, а авторитетный F доступен в non-stream; поднять лог расхождения до warning со счётчиком; добавить в T-L07 проверку на счётчик и warning; расхождение как класс вынести в Q для владельца — причина: architecture-packet.json#AD-004, architecture-packet.json#CD-001 — ARG: Реалист/D1 «отозвать уже отправленный в сокет префикс `P` невозможно». Моя проверка по AD-004: P берётся только из summary_parts[0], а F собирается из тех же накопленных частей. Расхождение возможно, только если сервер переписал уже выданный текст item/completed. Выбор там один из двух зол: дубль с перекосом текста или пропуск хвоста. Пропуск хвоста затрагивает только вспомогательное reasoning_content, но не content и не tool_calls. Это принятый и записанный компромисс (AD-004 consequences), а не молчаливая потеря. Нужно только назвать его в CD-001.

AMEND F-005 — priority=non-blocking; locations=architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#QA-008, architecture-packet.json#VER-001; fix=в AD-007, rollback и ADR 0003 записать, что переключатель задаёт политику serve-сессии, а exec-fallback остаётся с `--yolo` и выключенными write, shell, web и reminders; либо запретить fallback при denyUnmatched и завершать ход контролируемой ошибкой; добавить тест на сочетание denyUnmatched с -32030 или EOF рукопожатия — причина: architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#EVD-005, architecture-packet.json#EVD-008 — ARG: Реалист/D1 «на актуальных версиях CLI 1.4.7 и 1.4.8 режим `denyUnmatched` доказанно принимается `session/start` без `-32030`». Моя проверка по EVD-005: поверхность exec (`--disable-write --disable-shell --disable-web-tools --disable-reminders`) уже поверхности serve при allowAll. Fallback при откате не расширяет права относительно состояния, из которого откатываются, и этот путь был до задачи. Расхождение с намерением оператора есть, но это пробел документации, а не эскалация.

AMEND F-006 — priority=non-blocking; locations=architecture-packet.json#ASM-010, architecture-packet.json#BND-002, architecture-packet.json#VER-009; fix=журнал item/started и item/completed с kind вне {reasoning, agentMessage} (kind и toolName через allowlist-рендер, без rawArgs), счётчик на ход, канарейка в тесте, выборка в VER-009; называть журнал наблюдением событий, а не полным аудитом — причина: architecture-packet.json#ASM-010, architecture-packet.json#THREAT-001 (позиция прежняя)

AMEND F-007 — priority=non-blocking; locations=architecture-packet.json#AD-007, architecture-packet.json#VER-008, architecture-packet.json#BND-005; fix=указать, где лежит env (plist или `~/.dsh/.env`) и точную процедуру применения; добавить в VER-008 обратимое учение denyUnmatched→allowAll с проверкой эффективного режима в serve init. Утверждение, что `kickstart` не перечитывает plist, по материалам не проверяется — причина: architecture-packet.json#AD-007, architecture-packet.json#EVD-020 (позиция прежняя)

AMEND F-008 — priority=non-blocking; locations=architecture-packet.json#AD-003, architecture-packet.json#QA-004; fix=описать компромисс допуска попытки при малом остатке и способ подобрать порог по наблюдаемым длительностям, не навязывая 120 с; противоречие формулировки дедлайна закрывается в F-003 — причина: [F-43] (serve-ходы 8–94 с), [F-14] (позиция прежняя)

DISPUTE F-009 — класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-38] — EVD-005 прямо перечисляет `--disable-web-tools --disable-reminders` у exec, THREAT-001 прямо называет webSearch и сеть при allowAll. Асимметрия и её последствие в пакете есть. [F-38] подтверждает только существование `--config`, а не ключа отключения этих инструментов. Спайк возможен, но как улучшение, а не дефект (позиция прежняя).

DISPUTE F-010 — класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — тот же корень: общий `_wlock` занят писателем без 3-секундного предела. Исправление и тест T-L08 те же, что в F-002 (позиция прежняя).

AMEND F-011 — priority=non-blocking; locations=architecture-packet.json#AD-002, architecture-packet.json#VER-001; fix=одно правило «любая ошибка approval/decide и cancel, кроме -32051, защёлкивает отказ»; параметризованный тест по кодам [F-28], включая -32054 и -32030; явный терминальный путь для ошибок userInput/cancel — причина: architecture-packet.json#AD-002, [F-28] (позиция прежняя)

DISPUTE F-012 — класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, цитата Python-overlay architecture.md «порядок реализации формирует Orchestrator/Coder по утверждённому packet» — отдельный baseline-коммит, откат политики через env и полный файловый откат в пакете есть. Этапность коммитов и выключатели retry/live полезны, но обязательными из правил не следуют (позиция прежняя).

AMEND F-016 — priority=non-blocking; locations=architecture-packet.json#AD-007, architecture-packet.json#EVD-023, arch-spec.md (шапка и строка статуса); fix=привести шапку к AD-001..AD-007 и статус к receipt arch-gate-a2.json; снять утверждение о расхождении sha материализации: приложенный ADR имеет sha 4754421f…, равный materialization[0], а delta-a2.md не приложен и проверить его нельзя — причина: architecture-packet.json#materialization, receipts/arch-gate-a2.json (позиция прежняя)

DISPUTE F-017 — класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004 — у каждого нового AD по 4–5 альтернатив с причинами отказа. Правила требуют ≥2 альтернативы на решение, а не на каждый параметр внутри него. Альтернатива «ужесточить до turn/start» войдёт в AD-003 по F-001 (позиция прежняя).

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Решения AD-001..AD-007 согласованы: единый предикат допуска нового процесса и абсолютный дедлайн (AD-003), терминальное защёлкивание и grace (AD-002), префикс-монотонный live-стрим (AD-004) и обработка -32030 до turn/start (AD-006) не противоречат друг другу. Остатки только формулировочные: гарантия «3 с» при занятом замке (F-002), распределение времени и grace (F-003), компромисс при расхождении snapshot (F-004). Все они non-blocking.
   СОВЕТЫ (при FAIL): —
2. ПОЛНОТА: VERDICT=PASS
   WHY=REQ-MUSE-002, 003 и 004 протрассированы до QA и VER, ограничения REQ-MUSE-001 унаследованы (AD-005). Приёмка REQ-MUSE-004 отделена от диагностики (VER-009 и VER-011). Остатки: механизм закрытия ASM-010 (F-006), учение по откату (F-007), коды ошибок decide (F-011).
   СОВЕТЫ (при FAIL): —
3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Всё делается внутри существующего stdlib-моста `server.py` и одного файла тестов без новых зависимостей. Эталон 3-секундной записи есть в соседнем droid-мосте (EVD-015, EVD-024). Откат есть и быстрый (env), и полный (бэкап).
   СОВЕТЫ (при FAIL): —
4. РИСКИ: VERDICT=PASS
   WHY=Риск allowAll принят владельцем (EVD-009) и честно описан в THREAT-001. Повторы закрыты барьером активности, абсолютным дедлайном и удержанием слота. Зависший serve убивается через grace 15 с. Остаточные риски (ненаблюдаемый эффект, F-001; полнота записи под замком, F-002) названы и имеют путь закрытия.
   СОВЕТЫ (при FAIL): —
5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбран serve на запрос с внутриходовым decide, ограниченным повтором в Handler и синхронным sink с пределом записи. Сопоставлено с тремя архитектурами:
   - exec-only воспроизводит измеренные потери 275–412 с и до 2242 с ([F-06], [F-07]);
   - пассивный denyUnmatched оставляет исход хода после отказа неизвестным ([F-33], [F-50]);
   - постоянный MSP-брокер с долговечными сессиями или очередь кадров с отдельным писателем снижают стоимость запуска и развязывают клиента, но требуют жизненного цикла, изоляции и политики переполнения вне задачи (отклонены в AD-004).

   При росте нагрузки ломается в таком порядке:
   - сначала слоты: MAX_CONCURRENT=2 удерживается на весь ход вместе с повторами, поэтому очередь растёт, а запросы сверх лимита отсекаются за 30 с до дедлайна 1800 с (QA-004, QA-009);
   - затем общий прокси 127.0.0.1:10816: поднятие лимита или число экземпляров переносит нагрузку на него ([F-46]), а локальный лимит глобальным не становится;
   - затем живость reasoning: при нескольких summary-индексах live замораживается после summary.0.

   Позиции по отдельным подрешениям (F-017) не блокируют.
   СОВЕТЫ (при FAIL): —
6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Внешний контракт заморожен, единственная дельта CD-001 аддитивна внутри существующего `reasoning_content`. Расхождение snapshot (F-004) затрагивает только вспомогательное поле и должно быть названо в CD-001. Пакет соответствует Python-overlay, protected_paths и Full Suite Gate предусмотрены, тяжёлый путь VER-009 выполняет владелец.
   СОВЕТЫ (при FAIL): —
ОБЩИЙ ВЕРДИКТ: PASS
POSITIONS: 14/14
ANSWERS: 0/0
VERDICT: PASS

### D2 · Визионер · Google · место 2
Подтверждаю: прочитал общий канон ~/Мой диск/Context/AGENTS.md целиком до <!-- КАНОН-КОНЕЦ --> и проектные правила (AGENTS.md, .agents/AGENTS.md, .agents/CLAUDE.md, CLAUDE.md — в рабочей папке отсутствуют).

AGREE F-006 rev=1 — проверил: architecture-packet.json#ASM-010, architecture-packet.json#BND-002, architecture-packet.json#THREAT-001, architecture-packet.json#VER-009 — ASM-010 ссылается на закрытие через item-kind аудит первых живых ходов, но в BND-002 и VER-009 не задано логирование наблюдаемых `item/started|completed` с `kind` вне `{reasoning, agentMessage}` и их счётчика на ход; при этом разделяю уточнение Скептика (D1), что такой журнал является наблюдением событий, а не доказательством полноты инструментального аудита и не заменяет исправление F-001.

AGREE F-007 rev=1 — проверил: architecture-packet.json#AD-007, architecture-packet.json#EVD-020, architecture-packet.json#VER-008, architecture-packet.json#BND-005 — AD-007 и rollback описывают смену режима как «правка env launchd и перезапуск», но точный источник переменной окружения и обратимое учение `denyUnmatched -> allowAll` с проверкой эффективного режима новой сессии в `bridge.log` в VER-008 не зафиксированы.

AGREE F-008 rev=1 — проверил: architecture-packet.json#AD-003, architecture-packet.json#QA-004, architecture-packet.json#BND-003, [F-14], [F-43] — единый порог 30 с используется одновременно как окно рукопожатия и как минимальный остаток бюджета для старта из очереди и повтора, хотя для длинных ходов Wonder ([F-14], [F-43]) запуск при остатке 31 с создаёт высокий риск бесполезного расхода квоты; компромисс выбора порога стоит описать явно, а резерв времени на cleanup и финальную выдачу внутри бюджета закрывать в рамках F-003.

DISPUTE F-009 — класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-09], [F-10], [F-38] — проверил: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, docs/adr/0003-muse-serve-approval-allowall.md:85 — ARG: Скептик/D1 «architecture-packet.json#EVD-005 прямо перечисляет дополнительные запреты web/reminders у exec; architecture-packet.json#THREAT-001 прямо описывает webSearch, сеть и отправку данных наружу при allowAll — асимметрия и её существенное последствие уже представлены». Перепроверил пакет и ADR 0003: различие флагов запуска `serve` и `exec` зафиксировано в EVD-005 и docs/adr/0003-muse-serve-approval-allowall.md:122, а риск вызова `webSearch`/`network` при `allowAll` явно описан в THREAT-001; отсутствие в `muse serve --help` документированных ключей `--config` для отключения инструментов уже проверено в [F-38].

DISPUTE F-010 — класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — находка описывает тот же корневой дефект и тот же сценарий проверки, что и F-002: предел `LIVE_WRITE_TIMEOUT_S=3` с выставляется только на live-запись после захвата `_wlock`, тогда как keepalive и финальная выдача пишут через тот же `Handler._sse_write` под `_wlock` с прежним `Handler.timeout=300` с.

AGREE F-011 rev=1 — проверил: architecture-packet.json#AD-002, architecture-packet.json#VER-001, [F-28] — в AD-002 перечислены только коды `-32050/-32052/-32053` и benign `-32051`, тогда как схема в [F-28] включает также `-32054 approvalReviewerUnavailable` и `-32030 commandRejected`; правило защёлкивания отказа при любой ошибке `approval/decide` кроме `-32051` и терминальной обработки ошибок `userInput/cancel` нужно сформулировать единообразно и проверить параметризацией по кодам [F-28].

DISPUTE F-012 — класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, architecture-packet.json:671 — проверил: architecture-packet.json#BND-005, architecture-packet.json#AD-007, architecture-packet.json:983 — ARG: Скептик/D1 «Python-overlay прямо устанавливает: «порядок реализации формирует Orchestrator/Coder по утверждённому packet». Этапные коммиты и дополнительные выключатели могут быть полезны, но обязательность обоих предложений из приведённых правил не следует». Перепроверил Python-overlay (`architecture.md`: порядок реализации формирует Orchestrator/Coder по утверждённому пакету) и раздел `evolution` пакета: отделение baseline-коммита шагом 0, операционный откат политики через `MUSE_BRIDGE_APPROVAL_MODE` (AD-007) и полный файловый откат из бэкапа уже специфицированы, а env-переопределение прочих констант явно отнесено в `deferred`.

AGREE F-016 rev=1 — проверил: architecture-packet.json#AD-007, architecture-packet.json#EVD-023, architecture-packet.json:929, docs/adr/0003-muse-serve-approval-allowall.md:1 — шапка `arch-spec.md` перечисляет `AD-001..AD-006` при наличии `AD-007` в пакете, а строка статуса упоминает предстоящий `ARCH_GATE` при уже выпущенном receipt `PASS`; при этом `sha256` приложенного `docs/adr/0003-muse-serve-approval-allowall.md` (`4754421f...`) совпадает с `materialization[0].sha256` в пакете, поэтому исправления требуют только шапка и строка статуса `arch-spec.md`.

DISPUTE F-017 — класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004 — проверил: architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#AD-004, architecture-packet.json#AD-006, architecture-packet.json#AD-007 — ARG: Скептик/D1 «каждый из этих новых AD содержит не менее двух альтернатив и причины отказа; сама находка признаёт выполнение этого условия. Приведённые правила не устанавливают отдельный минимум альтернатив для каждого параметра или механизма внутри AD». Перепроверил `decisions[]`: у каждого нового решения AD-001..AD-004, AD-006, AD-007 приведено от 2 до 5 содержательных альтернатив с причиной выбора и отказа, что полностью выполняет требование к альтернативам.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Правило финального согласования в architecture-packet.json#AD-004 и architecture-packet.json#CD-001 (`если F не начинается с P — хвост не отправляется`) допускает молчаливую потерю авторитетного текста reasoning при успешном завершении хода (F-004). Временная модель в architecture-packet.json#AD-002 и architecture-packet.json#AD-003 передаёт попытке весь остаток до дедлайна 1800 с без резерва на grace, cleanup и финальную выдачу и отсчитывает `APPROVAL_CANCEL_GRACE_S=15` с после отправки команды в stdin, где запись ограничена лишь дедлайном хода (F-003). Лимит `LIVE_WRITE_TIMEOUT_S=3` с в architecture-packet.json#BND-004 не ограничивает ожидание общего замка `_wlock`, если его удерживает keepalive или финальная запись с таймаутом 300 с (F-002). В пакете также оставлены неточности в списке кодов ошибок `decide` (F-011) и формулировках про клиента (F-014).
   СОВЕТЫ (при FAIL): распространить `LIVE_WRITE_TIMEOUT_S=3` с на все записи в `Handler._sse_write` под `_wlock` и ограничить ожидание замка (F-002); отсчитывать grace 15 с от момента локального защёлкивания отказа, включая попытку записи команды отмены, и зарезервировать бюджет на cleanup и финальную выдачу (F-003); исключить молчаливое усечение авторитетного reasoning при расхождении snapshot либо согласовать с владельцем явный исход при несовместимом snapshot (F-004); закрепить единое правило обработки кодов ошибок `decide` по [F-28] (F-011) и привести формулировки EVD-015/CD-001 к статусу допущения ASM-003 (F-014).

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Трассировка REQ-MUSE-002..004 выполнена, однако барьер повтора в architecture-packet.json#AD-003 и architecture-packet.json#ASM-010 допускает повтор после ненаблюдаемого инструментального действия на `serve` и после побочного эффекта с пустым текстом ответа на `exec` (F-001), а механизм логирования инструментальных `item` для закрытия ASM-010 в BND-002 и VER-009 не специфицирован (F-006). В `verification_surface` (architecture-packet.json#VER-001, #VER-002, #VER-003) отсутствуют проверки сочетания `denyUnmatched` с `-32030` и setup-fallback (F-005), блокировки `_wlock` на keepalive-кадре (F-002), заблокированного stdin при входе в деградацию (F-003) и сохранения авторитетного текста при несовместимом snapshot (F-004).
   СОВЕТЫ (при FAIL): закрыть риск повтора после возможного начала неидемпотентного исполнения на `serve` и `exec` либо получить явное решение владельца (F-001); добавить безопасный лог и счётчик инструментальных `item` вне `{reasoning, agentMessage}` для проверки ASM-010 (F-006); дополнить тестовую матрицу VER-001..VER-003 сценариями F-001..F-005 и F-011.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Решение остаётся в рамках одного stdlib-моста `bridges/muse-bridge/server.py`, но синхронная цепочка I/O в architecture-packet.json#BND-003 и architecture-packet.json#BND-004 не гарантирует заявленные времена освобождения процесса и слота при конкурирующей записи под `_wlock` и блокировке stdin (F-002, F-003). Операционный переключатель `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` (architecture-packet.json#AD-007) при ошибке `-32030` или сбое setup до `turn/start` уходит по architecture-packet.json#AD-006 в `exec` с флагом `--yolo`, нарушая выбранную политику отказа (F-005), а процедура применения env в launchd и учение отката в VER-008 не конкретизированы (F-007).
   СОВЕТЫ (при FAIL): ограничить все записи под `_wlock` 3-секундным таймаутом (F-002); включить запись отказного `decide`/`turn/cancel` в 15-секундный бюджет grace (F-003); запретить fallback в автоматически разрешающий `exec --yolo` при `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` (F-005); уточнить процедуру смены переменной окружения для launchd и добавить проверку переключения режима в VER-008 (F-007); провести ранний замер времени первой дельты по F-013.

4. РИСКИ: VERDICT=FAIL
   WHY=Владелец принял риск `allowAll` на `session/start` (architecture-packet.json#EVD-009), но не принимал семантику `at-least-once` для побочных эффектов при повторе (architecture-packet.json#THREAT-004, #ASM-010; F-001) и не принимал обход операторского режима `denyUnmatched` через `exec --yolo` при деградации запуска `serve` (architecture-packet.json#AD-006, #AD-007; F-005). Риск удержания слотов медленным клиентом и зависшим процессом `serve` в architecture-packet.json#THREAT-003 закрыт не полностью из-за ожидания `_wlock` и stdin вне коротких лимитов (F-002, F-003), а порог 30 с для старта из очереди повышает риск холостых запусков при насыщении (F-008).
   СОВЕТЫ (при FAIL): исключить повтор после возможного начала ненаблюдаемого действия на `serve` и `exec` (F-001); запретить переход в `exec --yolo` при `denyUnmatched` (F-005); закрыть обход лимитов времени через `_wlock` и stdin (F-002, F-003); добавить наблюдаемый журнал инструментальных `item` (F-006) и уточнить компромисс порога допуска из очереди (F-008).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Каждое новое архитектурное решение (architecture-packet.json#AD-001, #AD-002, #AD-003, #AD-004, #AD-006, #AD-007) содержит от 2 до 5 альтернатив с явным обоснованием выбора и отказа. На уровне архитектуры системы выбранная модель (изолированный процесс `muse serve` на запрос с `approvalMode=allowAll` и внутриходовым `ApprovalPolicy`, префикс-монотонный синхронный live-sink под коротким socket timeout и ограниченный повтор в `Handler` внутри удерживаемого слота) превосходит: (1) архитектуру `exec`-only или пассивного отказа `denyUnmatched` с fallback в `exec`, которая в `exec`-варианте воспроизводит потерю 275–412 с мышления и до 2242 с повтора ([F-06], [F-07], EVD-003) и не даёт `summary.N` по ходу генерации, а в `denyUnmatched` блокирует целевые действия модели с неизвестным исходом хода ([F-33], [F-50]); (2) архитектуру постоянного многоходового MSP-брокера с пулом живущих сессий и выделенной асинхронной очередью SSE-писателя, которая снизила бы накладные расходы спавна, но потребовала бы сложной синхронизации финализации SSE, очистки зависших состояний между запросами и управления жизненным циклом вне рамок однофайлового stdlib-моста. При росте нагрузки в выбранной архитектуре последовательно ломаются: (а) пропускная способность слотов `MAX_CONCURRENT=2` ([F-21], architecture-packet.json#QA-004, #QA-009) — два длинных хода или цепочки повторов удерживают оба слота, очередь HTTP-соединений растёт, а ожидающие запросы отсекаются по порогу остатка до абсолютного дедлайна 1800 с; (б) окно доступности транзиентного повтора (architecture-packet.json#QA-005) — после отправки первой дельты `summary.0` или срабатывания барьера активности сбои внешнего прокси ([F-46]) уже не могут быть повторены; (в) гранулярность live-прогресса при многосекционном reasoning (`summary.1+`), где префикс-монотонный фильтр замораживает выдачу до конца хода (architecture-packet.json#AD-004), а масштабирование числа воркеров переносит узкое место на нестабильный внешний форвардер `127.0.0.1:10816` ([F-46]).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Пакет учитывает фактический stdlib-стек, наследует ограничения REQ-MUSE-001 (architecture-packet.json#AD-005), защищает `protected_paths` (architecture-packet.json#VER-012) и требует проверки тяжёлым путём (architecture-packet.json#VER-009). Однако ветка несовместимого snapshot в architecture-packet.json#CD-001 и architecture-packet.json#AD-004, отбрасывающая хвост авторитетного reasoning при успешном ходе, выходит за разрешённую в `task.json` аддитивную фрагментацию существующих полей SSE (F-004), а допущение о повторе при ненаблюдаемых эффектах в architecture-packet.json#THREAT-004 не обеспечивает требование Python-overlay об идемпотентности повторов (F-001). Также требуют синхронизации коллизии идентификаторов `F-NNN` с `[F-NN]` (F-015) и устаревшая шапка `arch-spec.md` (F-016).
   СОВЕТЫ (при FAIL): обеспечить сохранение авторитетного значения reasoning без потерь при фрагментации либо вынести изменение семантики на явное решение владельца (F-004); обеспечить безопасный барьер идемпотентности повторов на `serve` и `exec` (F-001); развести префиксы находок панели `PF-NNN` и фактов леджера `[F-NN]` (F-015); обновить шапку и строку статуса `ARCH_GATE` в `arch-spec.md` (F-016).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 9/9
ANSWERS: 0/0
VERDICT: NEEDS WORK

### D2 · Реалист · OpenAI · место 3

AGREE F-001 rev=1 — проверил: architecture-packet.json#ASM-010, architecture-packet.json#AD-003, architecture-packet.json#THREAT-004, architecture-packet.json#VER-002 — пакет прямо допускает ненаблюдаемое действие, но разрешает повтор по отсутствию наблюдаемых сигналов; для exec отсутствие текста также не устанавливает отсутствие эффекта. ARG: Скептик/D1 «аудит выборки помогает диагностике, но не устанавливает гарантию идемпотентности». Меняю прежнюю позицию: невозможность гарантировать безопасность разрешённого повтора означает необходимость ограничить его допустимость. REQ-MUSE-003 в приложенном handoff требует повтор «когда повтор допустим», поэтому запрет небезопасного переисполнения требованию не противоречит. Решение владельца об allowAll не разрешает дублирование действий. До доказанной наблюдаемости или дедупликации нужны запрет повтора после возможного начала исполнения на serve и отдельно безопасное условие для exec либо явное принятие владельцем иной семантики.

AMEND F-002 — priority=blocking; locations=architecture-packet.json#AD-004,architecture-packet.json#BND-004,architecture-packet.json#EVD-024,architecture-packet.json#VER-003; fix=ограничить ожидание _wlock и все конкурирующие SSE-записи, включая keepalive и финализацию, согласованным пределом с учётом остатка дедлайна; при превышении запускать ограниченную очистку; дополнить T-L08 сценарием, где первым блокируется keepalive, затем приходит summary, и проверить освобождение группы и слота — причина: architecture-packet.json#AD-004 обещает блокировку чтения MSP не дольше 3 с, но ограничивает запись только после захвата замка. ARG: Скептик/D1 «ограничение отдельного писателя не ограничивает всю цепочку ожидания». Меняю прежнюю оценку приоритета: простота исправления в общем _sse_write не делает необеспеченную гарантию backpressure неблокирующей; новый live-sink зависит от существующего писателя с timeout 300 с.

AMEND F-003 — priority=blocking; locations=architecture-packet.json#AD-002,architecture-packet.json#AD-003,architecture-packet.json#QA-001,architecture-packet.json#QA-004,architecture-packet.json#BND-003,architecture-packet.json#VER-001,architecture-packet.json#VER-002; fix=сохранить заявленный общий бюджет 1800 с, выделив внутри него конечные бюджеты управляющих записей, завершения группы и финальной выдачи; исполнению передавать остаток за вычетом этих резервов; grace отсчитывать от локального защёлкивания отказа и включать в него попытку отправки отмены; проверить заблокированный stdin и исчерпание времени исполнения непосредственно перед cleanup — причина: architecture-packet.json#AD-003 и architecture-packet.json#QA-004 включают cleanup и выдачу в 1800 с, но весь остаток передают попытке; architecture-packet.json#AD-002 запускает grace после отправки команды. ARG: Скептик/D1 «весь остаток бюджета передаётся попытке, хотя cleanup и финальная выдача заявлены внутри того же бюджета». Меняю прежнюю позицию: запас до клиентских 1900 с не доказывает выполнение внутреннего потолка 1800 с. Моё прежнее предположение о достаточности буфера stdin также не заменяет предусмотренный предел I/O.

AGREE F-004 rev=1 — проверил: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#RISK-003, architecture-packet.json#VER-003 — при несовместимом F уже опубликованный P остаётся единственным reasoning, хвост отбрасывается, а успешное завершение не запрещено. ARG: Скептик/D1 «Префикс-монотонность опубликованного потока не доказывает сохранение исходного значения reasoning». Меняю прежнюю позицию: невозможность отозвать SSE-префикс объясняет ограничение реализации, но не разрешает успешную выдачу усечённого значения. Нужно подтвердить устойчивость публикуемого префикса либо определить при расхождении контролируемый неуспешный исход существующего формата, согласовав его совместимость в AD-004/CD-001/VER-003; иная успешная семантика требует отдельного разрешения владельца. Полная буферизация — не единственный возможный ответ на этот дефект.

AMEND F-005 — priority=blocking; locations=architecture-packet.json#AD-006,architecture-packet.json#AD-007,architecture-packet.json#QA-008,architecture-packet.json#VER-001,architecture-packet.json#RISK-001; fix=при denyUnmatched запретить любой переход в автоматически разрешающий exec, включая -32030 и остальные setup-сбои; при невозможности сохранить выбранную политику возвращать контролируемую ошибку; согласовать rollback и ADR и проверить сочетания режима с каждым разрешённым setup-fallback — причина: architecture-packet.json#AD-007 объявляет операционный откат политики, а architecture-packet.json#AD-006 сохраняет exec с --yolo. ARG: Скептик/D1 «Переключатель, заявленный как откат политики, должен сохранять ограничение и при выборе другого транспорта». Меняю прежнюю позицию: принятие denyUnmatched текущими версиями CLI не закрывает остальные setup-сбои и будущую смену версии, ради которой AD-006 введён. Проверки T-A11 и T-A14 по отдельности этого свойства не устанавливают.

WITHDRAW F-010 — ARG: Визионер/D1 «это тот же root cause, что и F-002»; проверил: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024 — моя находка описывает тот же общий замок и keepalive-писатель без трёхсекундного предела. Все места и проверку следует объединить в F-002; самостоятельного дефекта здесь нет.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=architecture-packet.json#AD-002 и #AD-003 не обеспечивают заявленные временные пределы во всех ветках; #AD-004 и #CD-001 допускают успешный ответ с потерей авторитетного reasoning. Основания: F-003, F-004.
   СОВЕТЫ (при FAIL): распределить бюджет между исполнением, управляющими записями, очисткой и выдачей; начинать grace от локального отказа; исключить успешное молчаливое усечение при несовместимом snapshot; согласовать AD, QA, CD и VER.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=Требования и границы протрассированы, однако architecture-packet.json#VER-001, #VER-002 и #VER-003 не проверяют существенные сочетания отказов F-001–F-005. Аудит первых ходов из #ASM-010 не доказывает полноту наблюдения эффектов.
   СОВЕТЫ (при FAIL): добавить проверки эффекта без событий и текста, занятого keepalive-замка, заблокированного stdin, исчерпания бюджета перед cleanup, несовместимого snapshot и denyUnmatched вместе с setup-fallback; сохранить канареечную проверку безопасного журнала по F-006, отделив наблюдаемость от гарантии идемпотентности.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Изменение осуществимо в существующем stdlib-мосте без новых сервисов и библиотек. Блокируют утверждение обещанные, но пока необеспеченные пределы освобождения ресурсов и откат политики: architecture-packet.json#BND-003, #BND-004, #AD-007; F-002, F-003, F-005. Существенные ресурсы — доработка протокольных фикстур, независимая проверка конкуренции и участие владельца в VER-009. Подтверждённой календарной оценки материалы не дают.
   СОВЕТЫ (при FAIL): закрыть F-002, F-003 и F-005 до передачи утверждённого пакета Coder; конкретизировать применение env и провести обратимое учение отката по F-007; проверить источник pre-terminal summaries до основной реализации live по F-013, поскольку отрицательный результат потребует пересмотра решения.

4. РИСКИ: VERDICT=FAIL
   WHY=AllowAll принят владельцем при сохранённых ограничениях хоста. Это не покрывает повтор ненаблюдаемого действия и обход операторского denyUnmatched. Нестабильный внешний прокси остаётся зависимостью, которую повтор не гарантирует восстановить. Основания: architecture-packet.json#THREAT-004, #ASM-010, #AD-006, #AD-007, #EVD-012; F-001–F-003, F-005.
   СОВЕТЫ (при FAIL): ограничить повтор безопасно установленными условиями либо согласовать семантику дублирования; обеспечить сохранение denyUnmatched на всех путях; ограничить всю цепочку I/O и cleanup; проверить отсутствие второго эффекта и своевременное освобождение обоих слотов при отказах.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Каждый новый AD содержит ≥2 альтернативы с причинами выбора. Serve на запрос сохраняет ход лучше exec-only, воспроизводящего измеренные потери [F-06], [F-07]. Единственный SSE-писатель с ограниченной очередью отделяет чтение MSP от медленного клиента, но требует управления переполнением и финализацией; синхронный sink проще при устранении F-002. Постоянный MSP-брокер потребовал бы дополнительного управления сессиями и восстановлением. При росте нагрузки сначала насыщаются два модельных слота: растут очередь, ожидающие HTTP-соединения и занятость ресурсов, затем срабатывают дедлайны. Повторы увеличивают длительность удержания слотов; несколько экземпляров переносят суммарную нагрузку на общий прокси [F-46]. Локальный лимит 2 глобальную нагрузку не ограничивает.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Фактический стек, REQ-MUSE-001, protected_paths, baseline, Full Suite Gate и тяжёлый путь учтены. Однако architecture-packet.json#CD-001 допускает изменение итогового значения reasoning под видом разрешённой фрагментации, а #AD-003 прямо признаёт непринятую семантику at-least-once при недостаточном барьере. Основания: F-004, F-001.
   СОВЕТЫ (при FAIL): устранить успешное усечение reasoning в пределах замороженного контракта либо получить отдельное разрешение на изменение семантики; ограничить небезопасные повторы; синхронизировать AD/CD/QA/VER и формулировки evidence по F-014, сохранив ограничения REQ-MUSE-001 и защищённых путей.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
POSITIONS: 6/6
ANSWERS: 0/0
VERDICT: NEEDS WORK
ARTIFACT_END>>>

СВОДНЫЙ ЛЕДЖЕР:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/arch-panel/cycle-1/a2/consensus-ledger.md sha256=2b08a236f982ccb05e9fa75f5ec406ba6a2061cc9f4b1094d6c1e1a84a11d148
# consensus-ledger (арх-панель, cycle 1, a2)

### F-001
- origin: Визионер · R1 · F-001
- rev: 2
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR | D1 Реалист=D Скептик=A | D2 Скептик=M Реалист=A
- dissent: Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-003, architecture-packet.json#ASM-010, architecture-packe»
- owner_decision: —
- amendments: rev 2 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Визионер):
> F-001 — Барьер повтора не исключает повторение ненаблюдаемого действия.
> - Якоря: architecture-packet.json#AD-003, architecture-packet.json#ASM-010, architecture-packet.json#THREAT-004, architecture-packet.json#QA-005, architecture-packet.json#VER-002.
> - Правило: RW-003 требует ограничить разрешение повтора, если инструментальное действие нельзя надёжно обнаружить; разрешение allowAll не означает принятия at-least-once.
> - Evidence: ASM-010 признаёт: «действие без любого из этих сигналов до транзиентного сбоя фактами не исключено», однако разрешает повтор при чистом потоке reasoning/agentMessage. Для exec достаточен пустой результат. T-R07 проверяет только действие, сопровождаемое инструментальным item. Отсутствие текста exec также не доказывает отсутствие действия.
> - Ожидаемое исправление: до подтверждения полноты и порядка инструментальных событий запрещать повтор после возможного начала исполнения либо обеспечить доказанную дедупликацию. Отдельно определить безопасное условие для exec. Наблюдение первых успешных ходов не считать доказательством отсутствия ненаблюдаемых эффектов.
> - Критерий проверки: заглушка выполняет эффект без item/approval и без выходного текста, затем возвращает net-timeout; второго эффекта нет. Альтернатива — явное принятие владельцем семантики дублирования с соответствующим изменением пакета.
> - priority: blocking.

### F-002
- origin: Визионер · R1 · F-002
- rev: 2
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking
- text (дословно, R1 Визионер):
> F-002 — Таймаут live-записи не ограничивает ожидание общего замка.
> - Якоря: architecture-packet.json#AD-004, architecture-packet.json#BND-004, architecture-packet.json#EVD-024, architecture-packet.json#VER-003.
> - Правило: RW-004 требует ограниченного ожидания синхронного sink и сохранения чтения MSP при медленном клиенте.
> - Evidence: timeout 3 с выставляется «на время записи под _wlock» и затем восстанавливается. Через тот же замок идут keepalive и финальная выдача. EVD-024 фиксирует прежний timeout соединения 300 с. Если keepalive уже заблокирован на записи, live-sink сначала ждёт замок и до установки своего трёхсекундного timeout не доходит.
> - Ожидаемое исправление: распространить ограничение на все записи, конкурирующие за _wlock; ограничить ожидание замка остатком общего дедлайна. Либо выбрать единственного писателя с ограниченной очередью и явной политикой переполнения.
> - Критерий проверки: клиент перестаёт читать; сначала блокируется keepalive, затем приходит summary. Процесс и слот освобождаются за установленный предел, второй клиент обслуживается. Существующего T-L08 только с заполнением live-дельтами недостаточно.
> - priority: blocking.

### F-003
- origin: Визионер · R1 · F-003
- rev: 2
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking
- text (дословно, R1 Визионер):
> F-003 — Абсолютный бюджет и grace объявлены, но распределение времени допускает их превышение.
> - Якоря: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet.json#QA-001, architecture-packet.json#QA-004, architecture-packet.json#BND-003, architecture-packet.json#VER-001, architecture-packet.json#VER-002.
> - Правило: RW-002 включает cleanup и финальную выдачу в общий бюджет; RW-008 требует короткого освобождения слота после входа в деградацию.
> - Evidence: попытке передаётся весь «остаток до дедлайна», хотя в тот же бюджет входят cleanup и выдача. Запись stdin после turn/start ограничена дедлайном хода, а grace начинается «после отправки turn/cancel или отказного decide». При заблокированном stdin отправка отмены может ждать оставшуюся часть 1800 с ещё до запуска grace. При исчерпании попыткой всего остатка времени на последующие обязательные фазы уже нет.
> - Ожидаемое исправление: задать конечные бюджеты записи управляющей команды, завершения группы и финальной выдачи; вычислять дедлайн исполнения с резервом этих фаз. Grace отсчитывать от локального защёлкивания деградации, включая попытку отправки отмены; невозможность записать команду должна вести к принудительной очистке в том же пределе.
> - Критерий проверки: добавить остановку чтения stdin перед деградацией и зависание модели до последнего разрешённого момента бюджета. Проверять время от приёма запроса и от защёлкивания деградации до исхода и освобождения слота. Сценарии должны укладываться в заявленные пределы без дополнительного полного grace после общего дедлайна.
> - priority: blocking.

### F-004
- origin: Визионер · R1 · F-004
- rev: 2
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR | D1 Реалист=D Скептик=A | D2 Скептик=M Реалист=A
- dissent: Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet»
- owner_decision: —
- amendments: rev 2 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Визионер):
> F-004 — Разрешена потеря reasoning за пределами допустимой фрагментации контракта.
> - Якоря: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet.json#BND-004, architecture-packet.json#RISK-003, architecture-packet.json#VER-003.
> - Правило: task envelope разрешает только аддитивные SSE-кадры существующих полей; RW-005 требует согласования snapshot без потерь и дублей.
> - Evidence: «если [F не начинается с P] — хвост не отправляется». При опубликованном P=`a` и авторитетном F=`b\n\nc` клиент останется с `a`, потеряет `b\n\nc` и получит успешное завершение. CD-001 при этом называет изменение «аддитивной фрагментацией», хотя меняется само значение reasoning. VER-003 сохраняет отсутствие потерь только «в расширяющем случае».
> - Ожидаемое исправление: публиковать до завершения только доказанно устойчивый префикс источника и сохранить авторитетный итоговый текст. Если такой гарантии MSP получить нельзя, вынести изменение семантики расхождения на явное решение владельца новым delta-пакетом; молчаливое усечение успешного ответа не считать совместимой фрагментацией.
> - Критерий проверки: несовместимый snapshot содержит дополнительный уникальный текст; проверка подтверждает сохранение согласованного значения без потерь и дублей либо явно утверждённый новый исход. Одного лога расхождения недостаточно.
> - priority: blocking.

### F-005
- origin: Визионер · R1 · F-005
- rev: 2
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking
- text (дословно, R1 Визионер):
> F-005 — Операционный откат в denyUnmatched может снова включить автоматическое исполнение через exec.
> - Якоря: architecture-packet.json#AD-006, architecture-packet.json#AD-007, architecture-packet.json#QA-008, architecture-packet.json#VER-001, architecture-packet.json#RISK-001.
> - Правило: заявленный переключатель безопасности должен сохранять выбранную политику при деградации транспорта и версии CLI.
> - Evidence: AD-007 предлагает denyUnmatched как «быстрый операционный откат политики». AD-006 при отказе явного режима направляет запрос в exec, который остаётся с --yolo. Следовательно, отказ сервера принять denyUnmatched может привести к пути автоматического исполнения. T-A11 и T-A14 проверяют эти ветки раздельно.
> - Ожидаемое исправление: в denyUnmatched запретить fallback в exec с --yolo и другие пути, не обеспечивающие выбранный режим; при невозможности сохранить политику завершать запрос контролируемым отказом. Отразить область действия переключателя в rollback и ADR.
> - Критерий проверки: сочетание MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched с -32030 и другими setup-сбоями не запускает автоматически разрешающий exec; обычный allowAll сохраняет согласованную ветку fallback.
> - priority: blocking.

### F-006
- origin: Реалист · R1 · F-1
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Реалист):
> **F-1 [non-blocking] Закрытие ASM-010 и аудит инструментов не имеют механизма**
> - Якорь: architecture-packet.json#ASM-010, #THREAT-001, #BND-002, arch-spec.md §4.3.
> - Правило: каждая допущенная остаточная неопределённость должна иметь исполнимый способ закрытия.
> - Evidence: ASM-010 говорит «закрывается сверкой item-kind аудита первых живых ходов». Ни в BND, ни в §4.3, ни в VER, ни в T-* логирование item-kind не описано. В §4.3 перечислены только первая summary-дельта, modelRetryScheduled и approval_degraded.
> - Следствие: при allowAll сервер разрешает большинство действий сам, остаточных approval/request будет мало. Аудит решений моста окажется почти пустым, а ASM-010 нечем проверить.
> - Исправление: добавить в ServeRun строку на каждый item/started и item/completed с kind не из {reasoning, agentMessage}. Поля только безопасные: kind и toolName через allowlist-рендер, без rawArgs. Добавить счётчик таких item в итоговую строку хода. Добавить тест на эту строку и пункт в VER-009: ходы с инструментальными item фиксируются отдельно.
> - Критерий проверки: тест канарейки показывает, что в логе есть kind и нет аргументов. VER-009 содержит выборку ходов с item вне reasoning/agentMessage.

### F-007
- origin: Реалист · R1 · F-2
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Реалист):
> **F-2 [non-blocking] Быстрый откат политики через env launchd не проверяется и описан неоднозначно**
> - Якорь: architecture-packet.json#AD-007, evolution.rollback, #VER-008, arch-spec.md §7 п.7.
> - Правило: откат one-way решения безопасности должен быть проверен на реальном канале.
> - Evidence: «правка env launchd и перезапуск» и `launchctl kickstart -k`. Пакет сам указывает, что агент живёт в `~/Library/LaunchAgents/com.user.dsh-muse-bridge.plist` (EVD-020).
> - Риск: насколько я знаю, kickstart не перечитывает правки plist. Нужно bootout/bootstrap, либо чтение переменной из `~/.dsh/.env`. Это я не могу проверить по приложенным материалам.
> - Следствие: в T-A14 проверяется только чтение env внутри процесса. Реальная смена режима в деплое не проверяется нигде.
> - Исправление: в rollback и ADR 0003 записать точную последовательность команд (какой файл правится, bootout/bootstrap или иной способ). В VER-008 добавить «учение»: поставить denyUnmatched, перезапустить, увидеть в serve init `approvalMode=denyUnmatched`, вернуть allowAll.
> - Критерий проверки: в bridge.log после каждого шага виден ожидаемый эффективный режим.

### F-008
- origin: Реалист · R1 · F-3
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Реалист):
> **F-3 [non-blocking] Порог старта из очереди 30 с слишком мал, формулировка дедлайна неточна**
> - Якорь: architecture-packet.json#AD-003, #QA-004, #BND-003, arch-spec.md §3.3 и §8.
> - Правило: порог должен соответствовать наблюдаемой длительности полезного хода.
> - Evidence: «остаток ≤30 с запрещает новую попытку», тот же порог 30 с для «старта из очереди». Минимальный успешный ход wonder в бенче 51.1 с ([F-14]), серверные ходы 8-94 с ([F-43]).
> - Следствие: запрос, получивший слот с остатком 31 с, займёт слот и квоту Meta на ход, который почти наверняка не завершится.
> - Второе замечание: AD-003 заявляет, что дедлайн «включает grace, cleanup и финальную выдачу». §3.3 при этом даёт первой попытке полный остаток до дедлайна. Реально cleanup и выдача уходят в запас 100 с до 1900 с.
> - Исправление: ввести отдельную константу минимального остатка для старта из очереди и для повтора (например, не меньше 120 с, настраиваемую). Для порога 30 с оставить только смысл «handshake-окно». В AD-003 и QA-004 явно написать, что cleanup и выдача после дедлайна укладываются в запас до 1900 с.
> - Критерий проверки: T-R08 проверяет, что запрос с остатком меньше нового порога получает предусмотренную ошибку, а не запуск процесса.

### F-009
- origin: Реалист · R1 · F-4
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005 прямо перечисляет дополнительные запреты web/reminde»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-38] — EVD-0»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-09], [F-10]»
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-4 [non-blocking] Асимметрия возможностей serve и exec не названа, `--config` не рассмотрен**
> - Якорь: architecture-packet.json#EVD-005, #THREAT-001, #AD-001, [F-09], [F-10], [F-38].
> - Правило: trust boundary должна учитывать отличие поверхности инструментов обоих путей.
> - Evidence: exec запускается с `--disable-web-tools --disable-reminders` ([F-09]). У serve таких флагов нет ([F-10]). Единственный универсальный флаг serve — `-c/--config KEY=VALUE` ([F-38]).
> - Следствие: при allowAll на serve web-инструменты не отключены, хотя прежний exec-fallback их отключал. Это расширение возможностей модели относительно пути, на который раньше попадали ходы с approval. Решение владельца его допускает, но пакет это не называет и не рассматривает `-c` как способ сузить поверхность.
> - Исправление: записать асимметрию в THREAT-001 и в ADR 0003. Добавить альтернативу «сузить поверхность serve через `--config`». Ключи в справке не найдены, поэтому спайк без модельного хода: проверить, есть ли ключ отключения web-инструментов. Результат вынести отдельным решением владельца.
> - Критерий проверки: в пакете есть явная запись об асимметрии и альтернатива с причиной выбора или отказа.

### F-010
- origin: Реалист · R1 · F-5
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=D Скептик=D | D2 Скептик=D Визионер=D Реалист=W
- dissent: Визионер D1 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Скептик D1 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Скептик D2 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Визионер D2 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-5 [non-blocking, частично pre-existing] Предел 3 с применён только к live-записи, а не к каждой записи под `_wlock`**
> - Якорь: architecture-packet.json#AD-004, #BND-004, EVD-024.
> - Правило: ограничение времени записи должно закрывать всех писателей, с которыми sink делит замок.
> - Evidence: «на время записи под _wlock сокету выставляется timeout 3 с» относится к live-кадру. Keepalive-поток и финальная выдача пишут через тот же `_sse_write` и по EVD-024 ограничены только `Handler.timeout=300`.
> - Следствие: если keepalive-запись зависла на переполненном буфере, она держит `_wlock` до 300 с. Синхронный sink в цикле чтения MSP ждёт этот замок без предела. Это сценарий RW-004, но через другого писателя.
> - Исправление: применить 3-секундный предел ко всем записям под `_wlock` (keepalive и финал). Либо ограничить время захвата замка в sink и считать его таймаут признаком зависшего клиента.
> - Критерий проверки: T-L08 дополнить случаем, когда буфер заполнен и первым зависает keepalive-кадр. Слот и группа освобождаются в пределах предела.

### F-011
- origin: Реалист · R1 · F-6
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Реалист):
> **F-6 [non-blocking] [sweep] Список ошибок decide в AD-002 неполон относительно ledger**
> - Якорь: architecture-packet.json#AD-002 (choice), arch-spec.md §2.3 и §2.4, [F-28].
> - Evidence: AD-002 и §2.4 перечисляют триггеры защёлкивания -32050/-32052/-32053 и benign -32051. В [F-28] есть ещё -32054 approvalReviewerUnavailable и -32030 commandRejected. §2.3 говорит «любая error кроме -32051 ведёт в деградацию», то есть тексты расходятся.
> - Исправление: записать одним правилом «любая ошибка decide и cancel, кроме -32051, защёлкивает отказ». Добавить -32054 и -32030 в тест T-A08 или T-A13.
> - Критерий проверки: параметризованный тест на каждый код из [F-28].

### F-012
- origin: Реалист · R1 · F-7
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005 предусматривает отдельный baseline и ограниченную зо»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, цитата Python-over»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, architecture-packe»
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-7 [non-blocking] Нет плана поставки по этапам и выключателей для повтора и live**
> - Якорь: arch-spec.md §6 (около 35 тестов T-A/T-R/T-L), architecture-packet.json evolution.rollout и rollback, deferred «env-переопределение остальных констант».
> - Правило: стоимость сопровождения и откат должны быть соразмерны объёму.
> - Evidence: один файл server.py (2744 строки) и один файл тестов, который уже вырос на 2941 строку. В него добавляются ApprovalPolicy, терминальное защёлкивание, абсолютный дедлайн с предикатом допуска, барьер активности и live-sink с заморозкой. Откат: env только для режима approval, для повтора и live только полный redeploy.
> - Исправление: разбить коммиты на этапы с red→green и отдельной проверкой каждого.
>   1. REQ-MUSE-002 (AD-001/002/006/007).
>   2. Дедлайн и предикат (AD-003).
>   3. Live (AD-004).
>   Добавить дешёвые env-выключатели для транзиентного повтора и live-reasoning, по образцу AD-007. Выключатель live позволит отключить его, не откатывая approval.
> - Критерий проверки: пакет перечисляет этапы и выключатели. Тест на выключенный live возвращает прежний один reasoning-кадр.

### F-013
- origin: Реалист · R1 · F-8
- rev: 1
- priority: non-blocking
- status: PENDING_C1
- outcome: non-blocking
- resolved_in: d1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-8 [non-blocking] Узкое место REQ-MUSE-004 (OPEN-04) выясняется после постройки самой сложной части**
> - Якорь: architecture-packet.json#RISK-007, #VER-011, #ASM-004, #Q-004.
> - Правило: самый дорогой по реализации блок не должен зависеть от недоказанного факта, если его можно проверить дёшево.
> - Evidence: по RW-007 и VER-011 при summaries только в конце хода REQ-MUSE-004 остаётся NOT_MET/BLOCKED. Отдельного пути прогресса в пакете нет. Весь AD-004 (заморозка, префикс-монотонность, предел записи, T-L01..L08) строится до проверки факта, а проверка требует только временных меток.
> - Исправление: добавить шаг до AD-004. Мост временно логирует первую summary-дельту на живом ходе (одна строка логирования, без остального). Владелец делает один ход wonder max. Результат записывается в OPEN-04. Если дельты приходят только в конце хода, остановить реализацию AD-004 и вернуться к пакету с вопросом владельцу.
> - Критерий проверки: есть запись с секундами до первой дельты и длительностью хода до начала реализации live.

### F-014
- origin: Реалист · R1 · F-9
- rev: 1
- priority: non-blocking
- status: PENDING_C1
- outcome: non-blocking
- resolved_in: d1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-9 [non-blocking] Утверждения про клиента поданы как факт без опоры в ledger**
> - Якорь: architecture-packet.json#EVD-015, #AD-004 (drivers), #CD-001 compatibility, #ASM-003, [F-18], [F-47].
> - Evidence: EVD-015 утверждает «клиент DSH live reasoning_content уже потребляет». В [F-18] описана только отправка со стороны droid-моста. ASM-003 те же слова называет допущением (ASSUMED). В drivers AD-004 «пустые data-чанки доказано держат соединение». [F-47] фиксирует только причину в комментарии кода, а влияние на idle-watchdog «не найдено».
> - Исправление: в EVD-015 и в CD-001 переформулировать как допущение ASM-003. Заменить «доказано» на «по комментарию кода».
> - Критерий проверки: формулировки в EVD-015, AD-004 и CD-001 совпадают со статусом ASM-003.

### F-015
- origin: Реалист · R1 · F-10
- rev: 1
- priority: non-blocking
- status: PENDING_C1
- outcome: non-blocking
- resolved_in: d1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-10 [non-blocking] [sweep] Коллизия идентификаторов F-NNN и [F-NN]**
> - Якорь: architecture-packet.json#AD-002 (drivers «F-006», «F-011»), #AD-003 (drivers «F-002», «F-003»), #AD-004 (drivers «F-005, F-012»), #AD-006 (alternatives «F-009»), #AD-007 (drivers «F-020»).
> - Evidence: в тех же полях ledger ссылается как «F-50 в ledger», «F-35 в ledger». Голые трёхзначные F-NNN означают находки панели, которых в приложенном ledger нет. Читатель может принять их за двузначные факты [F-NN].
> - Исправление: переименовать находки панели в PF-NNN или давать полное имя. Для ledger оставить только [F-NN].
> - Критерий проверки: поиск по пакету не находит трёхзначных F-NNN вне delta_a2.

### F-016
- origin: Реалист · R1 · F-11
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking
- text (дословно, R1 Реалист):
> **F-11 [non-blocking] [sweep] Устаревший текст в arch-spec**
> - Якорь: arch-spec.md (шапка, «Нумерация: AD-001..AD-006», строка статуса «повторный ARCH_GATE впереди»), architecture-packet.json#AD-007.
> - Evidence: AD-007 существует, а шапка перечисляет AD-001..AD-006. Строка статуса говорит, что ARCH_GATE впереди, хотя приложен receipt arch-gate-a2.json со статусом PASS. Кроме того, delta-a2.md говорит, что материализованный ADR 0003 в `docs/` имеет sha `fcf1aea8…`. Приложение adr-0003 с путём в `docs/` имеет sha `4754421f…` (я не могу проверить, какой файл на диске).
> - Исправление: привести шапку и статус к фактическому состоянию. Сверить sha файла в `docs/` с materialization[0].sha256.
> - Критерий проверки: шапка перечисляет AD-001..AD-007, строка статуса соответствует receipt, sha файла в docs совпадает с пакетом.

### F-017
- origin: Реалист · R1 · F-12
- rev: 1
- priority: non-blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-12 [non-blocking] Подрешения a2 не имеют отдельных альтернатив с причиной выбора**
> - Якорь: architecture-packet.json#AD-002 (grace 15 с, защёлкивание), #AD-003 (абсолютный дедлайн, предикат и барьер), #AD-004 (префикс-монотонная заморозка).
> - Правило: новое решение должно иметь ≥2 альтернативы с причиной выбора.
> - Evidence: у каждого AD-NNN ≥2 альтернативы, так что формально критерий выполнен. Но отдельные подрешения a2 не имеют альтернатив: значение grace 15 с (обосновано только «диапазон панели 10–30 с»), абсолютный дедлайн против отдельного лимита очереди, барьер активности против запрета повтора после любого turn/start, префикс-монотонная заморозка против стриминга по item/completed.
> - Исправление: добавить в соответствующие AD по одной-две альтернативы с причиной. В ASM-010 уже названа контингенция «ужесточить до turn/start», её стоит вынести в alternatives AD-003.
> - Критерий проверки: каждое из перечисленных подрешений присутствует в alternatives соответствующего AD.
ARTIFACT_END>>>

РАУНД: D3 из ≤3; последний: да; место: Реалист
ПОЗИЦИИ ТРЕБУЮТСЯ ПО: F-001, F-002, F-003, F-004, F-005, F-006, F-007, F-008, F-009, F-010, F-011, F-012, F-016, F-017; N=14

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
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json sha256=c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e
{
  "schema_version": "1.0",
  "task_id": "REQ-MUSE-002",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": ".ai-team/runs/muse-wonder-approval-20261015/plans/architect-02.json",
    "sha256": "d398bb3763ea5b8add424df39d8d24e91a9cda78b15bde23422e25a12531883e"
  },
  "spec_path": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md",
  "requirement_ids": ["REQ-MUSE-002", "REQ-MUSE-003", "REQ-MUSE-004"],
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
      "claim": "F-18: соседний droid-мост того же DSH отдаёт content и reasoning_content live-дельтами и SSE-комментарием : keepalive каждые 15 с; клиент DSH live reasoning_content уже потребляет"
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
      "claim": "Арх-панель cycle-1 a1: NEEDS WORK; blocking F-001, F-005, F-007, F-011 CONSENTED и F-002, F-003, F-004, F-006 OWNER_DECIDED blocking (owner-decisions.md 2026-10-15 13:39 MSK); non-blocking F-008..F-010, F-013..F-021; F-012 excluded duplicate_of F-005; саммаризатор свернул их в RW-001..RW-008 и FU-001..FU-012"
    },
    {
      "id": "EVD-024",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:1992 (Handler._sse_write под _wlock, wfile.write+flush), :1953 (Handler.timeout=300); server.py (droid-мост):134 LIVE_WRITE_TIMEOUT_S=3, :5124 settimeout на live-записи",
      "claim": "Перепроверено 2026-10-15: запись SSE в muse-мосте ограничена только общим timeout соединения 300 с, отдельного предела живой записи нет; соседний droid-мост того же клиента ограничивает live-запись 3 с через settimeout сокета на время записи (F-004, F-18)"
    },
    {
      "id": "EVD-025",
      "kind": "code",
      "ref": "bridges/muse-bridge/server.py:ServeRun.execute._handle_event (kinds по item/started|completed, summary_parts по индексам), :2375-2384 (цикл ожидания слота), Handler.do_POST (_sse_begin до acquire слота)",
      "claim": "Перепроверено 2026-10-15: ServeRun уже различает kind элементов item/started и item/completed (reasoning, agentMessage и прочие) и копит summary_parts по индексам, поэтому признак инструментальной активности наблюдаем в существующем цикле чтения; ожидание слота идёт после отправки SSE-заголовков и ограничено только TIMEOUT_S без учёта последующего выполнения (F-002)"
    }
  ],
  "risk_triggers": ["security", "trust-boundary"],
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
      "evidence_ids": ["EVD-009", "EVD-008"]
    },
    {
      "id": "ASM-010",
      "statement": "Барьер повтора (RW-003): MSP-поток item/started|completed с kind вне reasoning/agentMessage, approval/request|requested и userInput/request дают наблюдаемый признак начала инструментальной активности хода; действие без любого из этих сигналов до транзиентного сбоя фактами не исключено (каталог и payload неизвестны, EVD-021), поэтому повтор разрешён только при чистом потоке reasoning/agentMessage на serve и пустом тексте exec-попытки; закрывается сверкой item-kind аудита первых живых ходов (OPEN-01), при контрпримере барьер ужесточается до принятого turn/start отдельным delta-пакетом",
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
      "choice": "Тот же ход продолжается: на запрос с id уходит receipt result={} тем же id, затем approval/decide с choiceId только из текущих availableChoices (decision=approved предпочтительнее approvedForSession, approvedPolicyAmendment не выбирается, requirementId дословно равен currentRequirementId, commandId через существующий _uuid7, sessionId из params); approve отправляется только при сконфигурированном режиме allowAll (AD-007). approval/requested без id ведёт к тому же decide без receipt, повтор по паре approvalId+requirementId подавляется дедупликацией, ошибка -32051 считается benign; terminal=false обрабатывается следующим обновлённым запросом; userInput/request получает receipt и userInput/cancel без передачи вопросов клиенту. Границы на ход: не более 10 approval/decide суммарно, включая финальный отказной decide, и не более 3 userInput/cancel (константы модуля); одиннадцатого decide не существует — при исчерпанном счёте деградация идёт сразу через turn/cancel. Терминальное защёлкивание отказа: отсутствие разрешающего choice, ошибка decide (-32050/-32052/-32053), превышение границы или ошибка записи stdin после принятого turn/start (receipt, decide, cancel) один раз переводят ход в локально зафиксированный неуспешный исход: при наличии выбора abort/denied и свободном счёте уходит один такой decide, иначе один turn/cancel; после защёлкивания новые разрешения и повторные входы в деградацию запрещены, дальнейшие approval/userInput запросы только логируются без команд, а любой последующий ответ сервера (повторный request, terminal=false, успешный turn/completed, молчание) локальный исход не меняет — поздний успешный текст отбрасывается, клиент получает ровно один терминальный исход. После отправки turn/cancel или отказного decide мост ждёт turn/completed не дольше APPROVAL_CANCEL_GRACE_S=15 с, затем убивает группу процессов serve, отдаёт терминальную ошибку и освобождает слот; дедлайн 1800 с для освобождения слота не ожидается. Ошибка записи stdin и транспортный сбой при обработке approval после принятого turn/start не бросают ServeUnavailable с exec-fallback: исход — та же терминальная деградация без нового процесса (единый предикат допуска AD-003/BND-003). Каждое решение логируется одной строкой безопасных полей через существующую редакцию без rawArgs; toolName и choiceId в логе рендерятся только при совпадении с [A-Za-z0-9_.:-] длиной до 64, иначе как redacted с длиной и префиксом sha256, список choiceId в логе обрезан 8 значениями (сырые значения для команды decide не меняются). Запись в stdin serve после turn/start ограничена дедлайном хода, а не setup-окном 30 с",
      "alternatives": [
        "decide с denied при любом запросе: действие отклоняется, продолжение хода после отказа не наблюдалось (OPEN-06), противоречит смыслу allowAll из AD-001",
        "немедленный turn/cancel при любом запросе: ход теряется без переигрыва, REQ-MUSE-002 выполнен только формально, результат пользователю ошибка вместо ответа",
        "сохранить ServeUnavailable и exec-рестарт как fallback: возвращает измеренную потерю EVD-003 и двойной вызов модели",
        "exec как последний шаг approval-деградации до _content_started (FU-004/F-013): отклонена — после увиденного approval и попыток decide инструмент мог уже выполниться (барьер RW-003), а 27 успешных exec-переходов spark за 19-1521 с происходили при старом ServeUnavailable, где мост ничего не разрешал; потеря «терминальная ошибка вместо ответа» принята с измеримым условием пересмотра: каждая деградация логируется approval_degraded с флагами content_started и tool_activity, и первый же такой случай на тяжёлом пути или в эксплуатации ставится владельцу на пересмотр отдельным delta",
        "детерминированный deny/abort при protectedWrite=true или judgeEscalated=true внутри allowAll (FU-003/F-010): отклонена в этом delta — живой payload и семантика полей не наблюдались (EVD-021), в serve approval judge отключён (EVD-022), write отключён хостом (EVD-005), а исход хода после denied неизвестен (ASM-006) с риском цикла повторов прошлого цикла (F-50 в ledger); оба признака пишутся в аудит, селективное правило вводится отдельным решением владельца по собранным payload (Q-001)"
      ],
      "drivers": [
        "receipt не меняет состояние, решение обязано идти отдельной командой, отклонить без решения нельзя (EVD-006)",
        "choiceId свободная строка без enum и живой payload неизвестен, поэтому выбор только из availableChoices по полю decision (EVD-021)",
        "approval приходил через 275 с и 412 с после старта хода при setup-окне записи 30 с (EVD-003, EVD-013): без продления _write_until decide упал бы в ServeUnavailable",
        "MAX_CONCURRENT=2: цикл запросов внутри хода обязан иметь счётный предел помимо дедлайна 1800 с (EVD-013)",
        "предел команд и терминальный исход обязаны оставаться истинными при любом ответе сервера после denied (F-006); два хода, проигнорировавшие cancel, не должны держать оба слота MAX_CONCURRENT=2 до 1800 с (F-011)"
      ],
      "consequences": [
        "ServeRun получает отправку JSON-RPC ответа по чужому id и учёт pending decide в главном цикле (голые ack чужих rid по-прежнему игнорируются, ошибка pending decide ведёт в деградацию)",
        "политика выбора изолирована чистой границей ApprovalPolicy (BND-001): смена AD-001 не трогает транспорт, ретрай и SSE",
        "userInput без пользователя завершается cancelled; если модель после этого завершает ход ошибкой, действует существующий путь model error без fallback",
        "фикстура install_protocol_wrapper расширяется реальным payload с availableChoices и ветками terminal=false и userInput; старый тест approval заменяется, тесты ServeUnavailable для прочих транспортных сбоев сохраняются",
        "терминальное защёлкивание делает поздний успешный turn/completed недостижимым для клиента: цена однозначности исхода при неизвестной семантике denied (ASM-006); счётчик деградаций approval_degraded в логе — вход условия пересмотра FU-004",
        "grace 15 с равен одному интервалу keepalive 15 с (EVD-014) и входит в абсолютный дедлайн запроса AD-003; влияние cancel на pending approval внутри grace не используется как опора: очистку гарантирует убийство группы (F-33 в ledger)"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; receipt и decide в rpc.jsonl, choiceId из availableChoices, второй запрос при terminal=false решён, userInput отменён, границы 10 (включая финальный отказной decide, одиннадцатого нет) и 3 останавливают цикл, после denied повторный request, terminal=false, успешный terminal и молчание сервера дают один локальный терминальный исход без exec (T-A13), фейковый serve без ответа на cancel теряет группу и слот не позже grace (T-A09b), ошибка записи receipt/decide после turn/start не запускает exec, канарейки rawArgs и choiceId отсутствуют в логе дословно, approval позже setup-окна решается в том же ходе"
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как ограниченно повторять транзиентный net-timeout и родственные транспортные сбои, не нарушая бюджет контекстного retry и идемпотентность SSE (REQ-MUSE-003)?",
      "choice": "Единый транзиентный повтор на уровне цикла попыток Handler вместо внутреннего exec-only повтора и единый абсолютный дедлайн запроса: якорь — приём запроса Handler, бюджет TIMEOUT_S=1800 с при значениях по умолчанию включает ожидание слота, все попытки, внутренний fallback, паузы, grace деградации, cleanup и финальную выдачу; каждая попытка получает только остаток до дедлайна, ожидание слота завершается предусмотренной ошибкой (503 до заголовков SSE либо SSE error после них) не позже чем за 30 с до дедлайна, новая попытка при остатке не больше 30 с не стартует — при клиентском пределе 1900 с (EVD-016) остаётся запас 100 с на финальную выдачу. Единый предикат допуска любого нового процесса (serve-попытка, внутренний serve→exec fallback, контекстный повтор, транзиентный повтор): клиент на месте, _content_started ложен, approval-деградация не защёлкнута (AD-002), инструментальная активность не зафиксирована, прежние группы подтверждены мёртвыми, остаток бюджета больше 30 с, счётчики не исчерпаны, тот же слот без повторного acquire. Внутренний exec-fallback допустим только до принятого turn/start и до любого approval-трафика (спавн, handshake, session/start, EOF и RPC-ошибки setup): он расходует тот же дедлайн и лимит процессов и проходит тот же предикат, а счётчик транзиентных повторов не расходует только потому, что исхода хода ещё не было; после принятого turn/start EOF, ошибка чтения, ошибка записи stdin и дедлайн чтения завершают запрос терминально без exec. Барьер инструментальной активности: флаг хода защёлкивается при approval/request или approval/requested, userInput/request, любом отправленном decide и любом item с kind вне {reasoning, agentMessage} (EVD-025); для exec-попытки барьером считается непустой текст или summaries в её результате. Защёлкнутый барьер запрещает fallback и оба вида повторов (семантика at-least-once владельцем не принималась, AD-001 её не покрывает). Класс транзиентной ошибки только по явным маркерам ([net-timeout], timed out waiting for response data, transport_connect_unreachable из текста REQ-MUSE-003, существующий network connection could not be opened): на serve-пути источник текста — turn/completed.error, классификатор смотрит конкатенацию error.kind и error.message до редакции, на exec-пути — сырой stderr-канал ошибки; retryable сам по себе класс не даёт. Не более 2 транзиентных повторов с паузой 2 с затем 4 с плюс джиттер до 1 с, пауза прерывается уходом клиента; вызовов run_attempt не более 3 без контекстного повтора и не более 4 с ним (1 + 1 контекстный + 2 транзиентных), процессов не более 8; отдельный счётчик от контекстного retry ADR-001.3, при hard threshold приоритет у контекстного повтора с прунённым промптом; состояния timeout, spawn_failed, client_gone не повторяются. Глобальный circuit breaker не вводится: слот удерживается на весь ход, поэтому повторы не повышают параллельную нагрузку выше MAX_CONCURRENT=2, а суммарную длительность ограничивают паузы и абсолютный дедлайн (FU-010, QA-009)",
      "alternatives": [
        "только расширить список маркеров внутреннего exec-повтора: serve net-timeout по-прежнему терминальная ошибка без второй попытки, бюджет и fallback взаимодействуют неявно",
        "повтор только внутри ServeRun новым serve-процессом: exec-путь и exec-after-fallback остаются без покрытия, два механизма повтора расходятся",
        "без повтора моста с опорой на provider attempts CLI: бенч и лог показывают финальный отказ после исчерпания попыток провайдера (EVD-011), REQ-MUSE-003 не выполнен",
        "повтор после первой live reasoning-дельты с подавлением уже отправленного префикса (FU-005/F-014): отклонена — текст второй попытки генерируется заново и равенство префиксов не гарантировано, подавление по байтам может потерять или склеить разный текст, а барьер инструментальной активности повтор всё равно запрещает в части случаев; вместо неё измеряется доля ходов, где первая дельта опережает транзиентный сбой: лог первой дельты (AD-004) плюс строка retry_blocked на терминале с _content_started, доля считается по bridge.log при диагностике VER-011"
      ],
      "drivers": [
        "быстрые сбои за 20 с и 31.5 с при успешных ходах 51.1-281.3 с оставляют запас бюджета 1800 с на свежий процесс и новое соединение (EVD-011, EVD-013)",
        "CLI уже повторяет поток провайдера (attempt 3/4, 4/4, after 5 provider attempts), поэтому повтор моста мал и ограничен (EVD-011, ASM-005)",
        "клиентский предел 1900 с запрещает складывать полные 1800 с на попытку (EVD-016)",
        "повтор после первого контентного кадра ломает идемпотентность потока, инвариант EVD-018 расширяется на первую live reasoning-дельту из AD-004",
        "ожидание слота до 1800 с плюс выполнение до 1800 с превышают клиентские 1900 с, поэтому бюджет считается от приёма запроса и распространяется на fallback (F-002, EVD-013, EVD-016)",
        "отсутствие SSE-контента и смерть процесса не исключают уже выполненного внешнего действия при allowAll и неизвестном каталоге инструментов (F-003, EVD-021), поэтому повтор гейтится наблюдаемым барьером активности"
      ],
      "consequences": [
        "внутренний однократный network retry внутри exec-after-fallback поглощается транзиентным счётчиком; тест test_t18 обновляется с сохранением утверждения, что контекстный бюджет транзиентом не расходуется",
        "ServeRun и Run получают остаток бюджета вместо полного TIMEOUT_S на повторных попытках; контекстный повтор второй попытки получает тот же остаток, что ужесточает прежний допущенный предел 2xTIMEOUT_S до исходного замысла ADR-001.3",
        "худший случай остановок ограничен суммой пауз не более 8 с внутри бюджета 1800 с; частичный текст упавших попыток по-прежнему отбрасывается, клиенту виден один терминальный исход",
        "non-stream JSON повторяется на тех же условиях, так как кадров клиенту до исхода нет",
        "контекстный повтор REQ-MUSE-001 дополнительно гейтится тем же предикатом (барьер активности и абсолютный остаток): гарантия «ровно не более одного и только до первого контентного кадра» (AD-005) сохраняется как верхняя граница, число фактических повторов может только уменьшиться",
        "очередь при насыщении завершается предусмотренной ошибкой раньше клиентского обрыва 1900 с вместо ожидания слота полные 1800 с плюс ход; поведение при поднятом оператором TIMEOUT_S выше 1900 с вне гарантии против профиля DSH EVD-016"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
        "expected": "exit 0; net-timeout затем успех даёт ровно 2 попытки и один [DONE] без error между ними (serve-терминал с маркером в error.message и error.kind по T-R01, exec по stderr), три отказа дают терминальную ошибку после 3 попыток без контекстного и не более 4 с ним, нет нового процесса после _content_started, после защёлкнутой approval-деградации, после инструментального item заглушки с наблюдаемым побочным эффектом до любого SSE-контента (второй эффект отсутствует), при уходе клиента, неподтверждённой смерти группы и остатке не больше 30 с; summary→EOF, summary→ошибка чтения, approval→ошибка записи и cancel→EOF exec не запускают, а EOF рукопожатия до turn/start по-прежнему уходит в exec один раз; три параллельных запроса при двух занятых слотах завершаются ответом или предусмотренной ошибкой внутри абсолютного дедлайна от приёма"
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Что получает SSE-клиент во время долгого мышления, кроме пустых keepalive-чанков (REQ-MUSE-004)?",
      "choice": "Live reasoning_content только на serve-пути с ограниченной записью и префикс-монотонной публикацией. ServeRun через sink Handler сообщает о приросте summary по мере накопления (дельты summary.N и списки item/completed проходят один путь накопления summary_parts/summaries, как сегодня); сокет, _wlock и фазы SSE принадлежат Handler. Живая запись ограничена LIVE_WRITE_TIMEOUT_S=3 с на кадр: на время записи под _wlock сокету выставляется timeout 3 с с восстановлением прежнего значения после записи, как в droid-мосте того же клиента (EVD-015, EVD-024); синхронный sink поэтому блокирует цикл чтения MSP не дольше 3 с на кадр и не срывает дедлайн хода. Таймаут или частичная запись кадра означает зависшего клиента: live отключается, соединение считается разорванным (частично записанный кадр терминального [DONE] не гарантирует), группа serve убивается существующим путём ухода клиента, слот освобождается в пределах 3 с плюс подтверждение смерти группы. Публикация префикс-монотонна и порядка задним числом не меняет: до заморозки live отдаёт только прирост summary_parts[0]; заморозка наступает при первой дельте с индексом больше 0, при item/completed reasoning или в конце хода — дальше всё только копится в буфер. Финальное согласование в _send_sse: F — сегодняшняя сборка join по накопленным summaries, P — уже отправленный live-текст; если F начинается с P, доотдаётся только хвост F[len(P):], если нет — хвост не отправляется, расхождение логируется длинами без текста, дубль и перестановка исключены; non-stream ответ всегда несёт авторитетную F. Повтор финального snapshot хвоста не даёт. Пустой data-keepalive каждые 15 с сохраняется без перехода на SSE-комментарии; content и tool_calls по-прежнему буферизуются до конца хода; первая фактически отправленная непустая reasoning-дельта выставляет _content_started под _wlock и закрывает окно повторов (буферизованная, но не отправленная дельта флага не ставит); turn/modelRetryScheduled логируется полями attempt/maxAttempts/retryDelayMs/errorKind и клиенту текстом не отдаётся; время первой summary-дельты от старта хода логируется для диагностики OPEN-04 (VER-011), приёмку VER-009 оно не заменяет; non-stream ответы без изменений",
      "alternatives": [
        "SSE-комментарий : keepalive по образцу droid-моста вместо пустых data-чанков: реакция pi-ai на комментарии не проверена (OPEN-03), тест test_s1 закрепляет обратное, выигрыш против working keepalive не показан фактами",
        "live content вместе с reasoning: частичная tool-разметка утекает клиенту до разбора _split_tool_calls по полному тексту, нужен потоковый парсер уровня droid-моста вне объёма REQ-MUSE-004",
        "статус-кво буферизации: клиент 205-237 с длинных ходов и дольше видит только пустые чанки, прогресс мышления не показан (EVD-011, EVD-014)",
        "ограниченная очередь кадров с отдельным потоком-писателем вместо ограниченного синхронного sink: отклонена — summaries грубые куски протокола, а не токены (EVD-014), отдельная очередь добавляет политику переполнения и гонку с финализацией _send_sse ради того же наблюдаемого предела 3 с",
        "повтор после первой live-дельты с подавлением отправленного reasoning-префикса (FU-005/F-014): отклонена в AD-003 — вторая попытка генерирует текст заново без гарантии общего префикса; конфликт REQ-MUSE-004 и REQ-MUSE-003 измеряется долей ходов «первая дельта раньше сбоя» по логам первой дельты и retry_blocked"
      ],
      "drivers": [
        "тот же клиент DSH уже накапливает live reasoning_content от droid-моста, поле и форма чанка моста не меняются (EVD-015, EVD-016)",
        "пустые data-чанки доказано держат соединение против клиентского ожидания заголовков около 600 с (F-47 в ledger, EVD-014)",
        "summary.N единственный прогресс мышления в MSP v1, сырой reasoning-текст протокол не стримит (docstring ServeRun, EVD-014)",
        "первая live-дельта сдвигает границу безопасного повтора, инвариант обязан быть явным (EVD-018)",
        "синхронный sink под _wlock без предела записи останавливает чтение MSP и держит слот: сегодня предел только общий timeout соединения 300 с (EVD-024), эталон того же клиента — 3 с (EVD-015)",
        "гарантии порядка summary.N в MSP нет (F-35 в ledger): последовательность 0:a, 1:b, 0:c нельзя превратить хвостом в итоговую сборку по индексам, поэтому публикация замораживается до согласования со snapshot (F-005, F-012)"
      ],
      "consequences": [
        "единственный contract delta пакета CD-001: reasoning_content приходит несколькими кадрами вместо одного, порядок reasoning раньше content сохранён; равенство конкатенации прежнему единому значению гарантируется в расширяющем случае (F начинается с P), при расхождении snapshot с дельтами клиент сохраняет уже отправленный префикс без дубля, а расхождение видно в логе",
        "тест test_s1 сохраняется по keepalive и дополняется порядком кадров; exec-ходы live reasoning не имеют и поведение не меняют",
        "если сервер шлёт summaries только в конце хода (OPEN-04), REQ-MUSE-004 остаётся NOT_MET и блокирует приёмку набора требований (VER-009), а факт фиксируется отдельной диагностикой VER-011; соединение при этом по-прежнему держит keepalive",
        "все записи SSE по-прежнему только через _sse_write под _wlock из Handler, ServeRun сокет не трогает (BND-004)",
        "при нескольких summary-индексах live после заморозки молчит до согласования: прогресс в этом случае показывает keepalive и финальный хвост, зато опубликованный порядок никогда не переписывается"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
        "expected": "exit 0; reasoning-дельты приходят до финального кадра, interleaved-индексы, поздний меньший индекс, расхождение item/completed с дельтами и повтор snapshot не меняют порядок, не теряют и не дублируют текст в расширяющем случае и не дублируют при расхождении (T-L06, T-L07); клиент, переставший читать при заполненном буфере, освобождает процессы и слот в пределах ограниченного времени записи, второй клиент обслуживается (T-L08); пустые keepalive-чанки сохранены и : keepalive отсутствует, ровно один [DONE] в неаварийных ветках"
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
      "evidence_ids": ["EVD-018", "EVD-005", "EVD-016"],
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
      "choice": "Каждый ServeRun логирует serverInfo.version, fingerprint схемы и эффективный approvalMode сессии. Отказ session/start с -32030 approval_mode_ceiling на явном режиме клиентским автоодобрением не обходится: ServeRun прерывается до turn/start как транспортный ServeUnavailable с warning (версия сервера и код -32030), и Handler выполняет ровно один внутренний exec-fallback по единому предикату допуска AD-003 — второй session/start без approvalMode и внутриходового approve поверх серверного promptUnmatched не происходит. Неизвестная версия CLI ход не блокирует и отдельно помечается в логе init; закрепление версии лаунчера вне объёма (OPEN-09)",
      "alternatives": [
        "жёсткий отказ хода на неизвестной версии: автообновление 1.4.7 -> 1.4.8 без участия моста остановило бы боевой мост (EVD-019)",
        "терминальный отказ хода при -32030 без exec: на версии с потолком каждый ход завершается ошибкой вместо существующего exec-пути, хотя сбой произошёл до turn/start и переигрывать нечего",
        "повторный session/start без approvalMode с опорой на внутриходовый decide approve (поведение пакета a1): отклонена до явного решения владельца — при серверном default promptUnmatched безусловное approve реализует allowAll на стороне клиента в обход потолка, а решение владельца AD-001 относится к полю session/start и обход ceiling не разрешает (F-009, Q-009)"
      ],
      "drivers": [
        "потолок существовал на 1.4.2 и отсутствует на 1.4.7/1.4.8, поведение зависит от версии (EVD-004, EVD-008)",
        "лаунчер обновляется сам и удаляет прежний бинарь, мост версию не контролирует (EVD-019)"
      ],
      "consequences": [
        "фейковая фикстура получает ветку отказа -32030 на первый session/start",
        "на версии с потолком поведение честно деградирует к существующему exec-пути (exec уже работает с --yolo вне MSP-потолка) ценой потери serve-хода только на таких версиях; на 1.4.7/1.4.8 потолок не воспроизводится (EVD-004, EVD-008), поэтому боевой путь не меняется",
        "политика AD-001 на ходе с -32030 помечается в логе неприменённой по потолку сервера, а не эмулируется клиентом"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; при -32030 на session/start с явным режимом второго session/start и approval/decide в rpc.jsonl нет, warning с версией в логе, ровно один exec-fallback до turn/start доводит ход, serve-процесс один (T-A11)"
      }
    },
    {
      "id": "AD-007",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как оператору сменить режим approval боевого моста без правки кода при откате политики или после аудита первых живых payload?",
      "choice": "Env-переключатель MUSE_BRIDGE_APPROVAL_MODE читается при старте процесса в ряд существующих env-констант (TIMEOUT_S, MAX_CONCURRENT, KEEPALIVE_S): допустимы только allowAll и denyUnmatched, значение по умолчанию allowAll по AD-001; выбранное значение уходит в session/start и одновременно гейтит approve в ApprovalPolicy (при denyUnmatched остаточный запрос уходит в отказную деградацию AD-002, approve не отправляется никогда); невалидное значение останавливает старт процесса с ошибкой в логе. Смена режима — правка env launchd и перезапуск, без изменения кода",
      "alternatives": [
        "смена режима только правкой кода и redeploy с явной фиксацией в ADR (deferred пакета a1): откат one-way решения безопасности дорог и медленен именно в инциденте",
        "переключение HTTP-ручкой моста в рантайме: новая внешняя поверхность управления в замороженном контракте и лишняя trust boundary ради редкой операции"
      ],
      "drivers": [
        "allowAll — one-way решение безопасности владельца (AD-001), цена его отката должна быть операцией, а не релизом (F-020)",
        "мост уже читает TIMEOUT_S, MAX_CONCURRENT и KEEPALIVE_S из окружения при старте (EVD-013, server.py:65-66,1185), новый переключатель не вводит второй механизм конфигурации"
      ],
      "consequences": [
        "значение по умолчанию и смысл AD-001 не меняются: без env мост объявляет allowAll; операторский denyUnmatched виден в логе эффективного режима каждого хода (AD-006)",
        "deferred пакета про env-переопределение сужается до остальных констант повторов и границ"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched session/start несёт denyUnmatched и approve не отправляется, без env несёт allowAll, невалидное значение останавливает старт с ошибкой в логе; правка кода для смены режима не требуется (T-A14)"
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
      "response": "тот же процесс serve продолжает ход после receipt и approval/decide, exec не запускается, второй turn/start не уходит; при деградации локальный исход фиксируется один раз, поздние ответы сервера его не меняют, группа и слот освобождаются не позже grace 15 с после cancel или отказного decide",
      "response_measure": "в фейковом MSP ровно один turn/start и нет exec-argv; после denied четыре поведения сервера (повторный request, terminal=false, успешный terminal, молчание) дают один терминальный исход и не более 10 decide суммарно; игнорирующий cancel serve мёртв и слот свободен в пределах grace при ужатых константах теста; на тяжёлом пути в bridge.log строка решения approval и done via=serve без fallback exec по этому ходу",
      "verification_ids": ["VER-001", "VER-009"]
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
      "verification_ids": ["VER-001", "VER-005"]
    },
    {
      "id": "QA-003",
      "quality": "reliability",
      "source": "транспорт Meta через ProxyRack",
      "stimulus": "net-timeout за 20-31.5 с как в логе и бенче, затем здоровый ход 51.1-281.3 с",
      "environment": "до первого контентного кадра, клиент на месте, stream и non-stream",
      "artifact": "цикл попыток Handler",
      "response": "мост повторяет ход свежим процессом в пределах общего бюджета 1800 с и отдаёт один успешный исход",
      "response_measure": "ровно 2 попытки, пауза между ними 2 с плюс джиттер до 1 с, один [DONE] и ни одного error-кадра между попытками, суммарно не дольше абсолютного дедлайна TIMEOUT_S от приёма запроса, включая ожидание слота",
      "verification_ids": ["VER-002", "VER-010"]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "транспорт Meta через ProxyRack",
      "stimulus": "net-timeout на каждой попытке, включая длинный сбой 452 с из лога; отдельно — три и более одновременных запроса при двух занятых слотах с задержанными serve и fallback",
      "environment": "клиент на месте, MAX_CONCURRENT=2",
      "artifact": "цикл попыток Handler и освобождение слота",
      "response": "после исчерпания повторов один терминальный отказ существующего формата 502 или SSE error с одним [DONE]; ожидавший слот запрос получает ответ внутри абсолютного бюджета либо предусмотренную ошибку до клиентского предела 1900 с, а не обрыв клиента",
      "response_measure": "вызовов run_attempt не более 3 без контекстного повтора и не более 4 с ним одинаково в AD-003, QA-004 и VER-002; сумма пауз не более 8 с; остаток не больше 30 с останавливает повтор и ожидание слота раньше; абсолютный потолок от приёма запроса равен TIMEOUT_S=1800 с при значениях по умолчанию и включает очередь, выполнение, grace, cleanup и финальную выдачу; все группы процессов мертвы и слот освобождён ровно один раз",
      "verification_ids": ["VER-002", "VER-005"]
    },
    {
      "id": "QA-005",
      "quality": "compatibility",
      "source": "serve присылает первую summary-дельту, затем ход падает net-timeout",
      "stimulus": "транзиентная ошибка после первой live reasoning-дельты клиенту; отдельно — инструментальный item с побочным эффектом до любого SSE-контента, затем net-timeout",
      "environment": "stream=true, live reasoning включён AD-004",
      "artifact": "граница _content_started",
      "response": "повтор запрещён, клиент получает один терминальный error и один [DONE] без дубля reasoning",
      "response_measure": "ровно 1 попытка при _content_started истинном и ровно 1 попытка, когда заглушка выполнила наблюдаемый побочный эффект через инструментальный item до любого SSE-контента и затем вернула net-timeout (второго эффекта нет); тот же сбой до первой дельты и без инструментальной активности повторяется по QA-003; в логе есть время первой дельты и строка retry_blocked для метрики FU-005",
      "verification_ids": ["VER-002", "VER-003"]
    },
    {
      "id": "QA-006",
      "quality": "usability",
      "source": "владелец ждёт длинный ход wonder 205-237 с и дольше",
      "stimulus": "serve присылает summary.N по ходу мышления",
      "environment": "stream=true, клиент DSH с streamIdleTimeoutMs=1900000",
      "artifact": "SSE-поток моста",
      "response": "клиент получает reasoning_content приростами до конца хода, разрывы между любыми кадрами закрывает keepalive 15 с",
      "response_measure": "первый reasoning-кадр строго раньше терминального кадра в фейковом тесте с задержанными дельтами, порядок и текст соответствуют префикс-монотонному правилу AD-004 без дублей; на тяжёлом пути в UI виден прирост reasoning во время мышления и лог первой дельты меньше длительности хода; приход дельт только в конце хода фиксируется диагностикой VER-011 и оставляет REQ-MUSE-004 невыполненным, приёмку не даёт",
      "verification_ids": ["VER-003", "VER-009", "VER-011"]
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
      "verification_ids": ["VER-004", "VER-005", "VER-008"]
    },
    {
      "id": "QA-008",
      "quality": "operability",
      "source": "автообновление Muse CLI, как переход 1.4.7 -> 1.4.8 ночью 15.10",
      "stimulus": "новая версия возвращает -32030 на явный approvalMode или меняет fingerprint схемы",
      "environment": "боевой мост без пересборки, следующий ход после обновления",
      "artifact": "ServeRun init и session/start",
      "response": "ход не эмулирует allowAll поверх серверного потолка: ServeRun прерывается до turn/start с warning, ровно один exec-fallback доводит ход, версия и fingerprint видны в логе",
      "response_measure": "фейковая ветка -32030 не даёт второго session/start и approval/decide в том же процессе, даёт один exec и завершённый ход; строка serve init содержит версию сервера и эффективный режим на каждом ходе",
      "verification_ids": ["VER-001", "VER-008"]
    },
    {
      "id": "QA-009",
      "quality": "operability",
      "source": "транспорт Meta через ProxyRack при общей деградации",
      "stimulus": "серия net-timeout под двумя параллельными ходами при MAX_CONCURRENT=2",
      "environment": "оба слота заняты, клиенты на месте, до первых контентных кадров",
      "artifact": "циклы попыток Handler и счётчик параллельных процессов",
      "response": "повторы идут внутри уже занятых слотов с паузами, параллелизм процессов не растёт, оба запроса завершаются внутри абсолютного дедлайна без взаимной блокировки слотов",
      "response_measure": "одновременно не более 2 процессов модели на мост, на запрос не более 4 вызовов run_attempt и пауз суммарно не более 8 с, слоты освобождены по одному разу; глобального circuit breaker нет осознанно, поскольку удерживаемый слот не даёт повторам повысить параллельную нагрузку (FU-010)",
      "verification_ids": ["VER-002"]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "ApprovalPolicy (чистое решение по снимку params внутри server.py)",
      "responsibility": "по params approval или userInput выдать действие approve с конкретным choiceId (только при сконфигурированном allowAll по AD-007), deny/abort, cancel-user-input или fail-turn и аудит-запись решений моста только безопасными полями с allowlist-рендером toolName и choiceId; единственное место знания политики AD-001; селективных запретов по protectedWrite/judgeEscalated до живых payload не содержит (FU-003 отклонён с обоснованием в AD-002)",
      "allowed_dependencies": ["stdlib", "_redact_secrets для аудит-строки"],
      "forbidden_dependencies": [
        "ServeRun._send и любой I/O",
        "subprocess",
        "Handler и SSE-сокет",
        "чтение rawArgs дальше факта наличия",
        "глобальное изменяемое состояние между ходами",
        "логирование choiceId и toolName дословно без allowlist-рендера и предела длины"
      ],
      "verification_ids": ["VER-001"]
    },
    {
      "id": "BND-002",
      "component": "ServeRun (MSP-транспорт одного хода serve)",
      "responsibility": "процесс serve на запрос, handshake с approvalMode и деградацией AD-006, receipt и команды decide/cancel/turn-cancel строго по решению BND-001, дедупликация и границы решений, терминальное защёлкивание отказа с grace 15 с и убийством группы, классификация транспортных сбоев до и после принятого turn/start для предиката допуска Handler, фиксация инструментальной активности item/approval для того же предиката, накопление текста и summaries, вызов live-sink Handler без владения сокетом",
      "allowed_dependencies": ["ApprovalPolicy (BND-001)", "_uuid7", "_log", "_terminate_run", "live-sink колбэк Handler"],
      "forbidden_dependencies": [
        "прямая запись в SSE-сокет",
        "запуск exec Run",
        "захват _slots",
        "решение политики вне BND-001",
        "логирование rawArgs и тел вопросов",
        "ServeUnavailable с exec-fallback после принятого turn/start или после approval-трафика",
        "новые MSP-команды после терминального защёлкивания, кроме одного turn/cancel ветки деградации"
      ],
      "verification_ids": ["VER-001", "VER-003"]
    },
    {
      "id": "BND-003",
      "component": "Handler, цикл попыток хода (run_attempt и окружающие повторы)",
      "responsibility": "абсолютный дедлайн запроса от приёма (TIMEOUT_S при значениях по умолчанию) на ожидание слота, попытки, fallback, паузы, grace и cleanup; единый предикат допуска любого нового процесса: клиент на месте, нет _content_started, нет защёлкнутой approval-деградации, нет инструментальной активности, прежние группы мертвы, остаток больше 30 с; serve-first с exec fallback только до принятого turn/start, отдельные счётчики контекстного (не более 1) и транзиентного (не более 2) повторов, один слот на весь ход",
      "allowed_dependencies": ["ServeRun (BND-002)", "Run (exec)", "_prune_messages и _context_limit", "_slots один acquire на запрос", "_watch_client"],
      "forbidden_dependencies": [
        "повторный _slots.acquire для повтора",
        "повтор при _content_started или ушедшем клиенте",
        "второй контекстный retry",
        "полный TIMEOUT_S каждой повторной попытке",
        "content-кадры между попытками",
        "новый процесс в обход единого предиката допуска, включая внутренний fallback после turn/start",
        "ожидание слота или попытка за абсолютным дедлайном от приёма запроса"
      ],
      "verification_ids": ["VER-002", "VER-004"]
    },
    {
      "id": "BND-004",
      "component": "Handler, SSE-эмиттер (_sse_begin, _keepalive_loop, live reasoning sink, _send_sse)",
      "responsibility": "единственный писатель в сокет: role-кадр, пустой keepalive 15 с в фазе OPEN, live reasoning только префикс-монотонно до заморозки с финальным согласованием startswith без дубля, живая запись ограничена LIVE_WRITE_TIMEOUT_S=3 с на кадр выставлением timeout сокета под _wlock с восстановлением, таймаут или частичная запись переводит соединение в ветку ушедшего клиента с убийством группы, _content_started только фактически отправленной дельтой под _wlock, один [DONE] в неаварийных ветках",
      "allowed_dependencies": ["_sse_write под _wlock", "_sse_chunk", "_split_sse_chunks"],
      "forbidden_dependencies": [
        "запись в обход _sse_write",
        "удержание _wlock во время выполнения модели",
        "live content и tool_calls до конца хода",
        "SSE-комментарии keepalive в этом изменении",
        "исключения live-записи в ServeRun",
        "удержание _wlock живой записью дольше LIVE_WRITE_TIMEOUT_S",
        "публикация reasoning вне префикс-монотонного правила и финальный дубль при расхождении snapshot"
      ],
      "verification_ids": ["VER-003", "VER-005"]
    },
    {
      "id": "BND-005",
      "component": "Внешняя эксплуатационная граница (DSH, muse CLI и Meta, прокси :10816, launchd-зеркало)",
      "responsibility": "мост не меняет профили DSH, лаунчер и прокси; деплой только копией server.py в ~/.dsh/bridges/muse-bridge/ и перезапуском com.user.dsh-muse-bridge после бэкапа; источник net-timeout и версии CLI остаются внешними рисками; незакоммиченный baseline REQ-MUSE-001 отделяется первым отдельным коммитом до правок REQ-MUSE-002..004, diff Coder по protected_paths пуст, правки тестов ограничены заменой approval-теста, обновлением test_t18 и добавлением классов Approval, TransientRetry и LiveReasoning в tests/test_muse_bridge_killpg.py",
      "allowed_dependencies": ["~/.dsh/bridges/muse-bridge/server.py зеркало", "launchctl kickstart com.user.dsh-muse-bridge", "GET /health и /v1/models с ключом моста"],
      "forbidden_dependencies": [
        "правки cordis.patch.yml профилей DSH в этом изменении",
        "закрепление или откат версии Muse CLI мостом",
        "изменения форвардера ProxyRack",
        "записи muse-spark-* в профилях"
      ],
      "verification_ids": ["VER-008", "VER-009", "VER-012"]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "muse-bridge SSE на POST /v1/chat/completions stream=true, только serve-путь",
      "consumer": "клиент DSH (openai-completions, OpenAI SDK и pi-ai)",
      "change": "delta.reasoning_content приходит несколькими кадрами по ходу мышления вместо одного кадра после хода по префикс-монотонному правилу AD-004 (публикуется только прирост summary.0 до заморозки, финальный хвост доотдаётся лишь когда сборка расширяет отправленное); поле, форма чанка chat.completion.chunk, порядок reasoning раньше tool_calls и content, финальные кадры и [DONE] без изменений; в расширяющем случае конкатенация дельт равна прежнему единому значению, при расхождении snapshot с отправленным префиксом дубль не отправляется и расхождение логируется",
      "compatibility": "аддитивная фрагментация существующего поля: OpenAI-стрим определён накоплением дельт, тот же клиент уже накапливает live reasoning_content droid-моста (EVD-015), профиль объявляет supportsReasoningEffort=true (EVD-016); non-stream JSON, exec-ходы, /health и /v1/models не затронуты; новых полей, путей и кодов нет",
      "verification_ids": ["VER-003", "VER-009"]
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
      "question": "Как единый предикат допуска нового процесса, абсолютный дедлайн от приёма запроса с очередью, барьер инструментальной активности, _content_started и уход клиента ограничивают fallback и оба вида повторов?",
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
    "compatibility": "Внешний OpenAI-контракт заморожен, единственный дельта-эффект CD-001 внутри существующего поля; non-stream, exec-путь, /health, /v1/models, окна моделей и профили DSH без изменений; смешанных версий внутри одного процесса нет, перезапуск моста атомарно меняет поведение всех новых ходов, идущие ходы завершаются старым процессом только до перезапуска launchd; ожидание слота при насыщении теперь завершается той же формой предусмотренной ошибки внутри абсолютного дедлайна от приёма вместо ожидания полных 1800 с плюс ход (RW-002), форм ответов это не меняет",
    "migration": "NOT_APPLICABLE: персистентных данных и схем хранения нет, serve-сессия создаётся на запрос с --no-session-log, состояние повторов и approval живёт только внутри хода; обновляются код репозитория, тесты и деплой-копия server.py",
    "rollout": "Шаг 0: незакоммиченный baseline REQ-MUSE-001 в дереве dev (2941 вставка, EVD-020) отделяется первым отдельным коммитом на ветке bugfix/muse-wonder-approval-retry-liveness (или предварительной фиксацией владельцем): его diff дословно равен снимку дерева до работы, дальнейшие коммиты содержат только дельту REQ-MUSE-002..004, git diff baseline..HEAD правок REQ-MUSE-001 не включает (FU-008). Затем red затем green тесты; бэкап repo и зеркала server.py в ~/work/backups с датой; после ACCEPT панели и MR человеком копия server.py в ~/.dsh/bridges/muse-bridge/server.py, launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge, проверка VER-008, затем тяжёлый путь VER-009 владельцем и диагностика VER-011; строка ADR 0003 добавляется в docs/adr/INDEX.md тем же MR после материализации proposal оркестратором. В dev напрямую не коммитить",
    "rollback": "Быстрый операционный откат политики без кода: MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched в env launchd и перезапуск (AD-007). Полный откат: восстановить server.py из бэкапа в репозитории и в ~/.dsh/bridges/muse-bridge/server.py и перезапустить com.user.dsh-muse-bridge той же командой kickstart; данные не мигрировали, профили DSH не менялись, поведение возвращается к ServeUnavailable с exec-фолбэком и буферизованному reasoning целиком"
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
        "mitigation": "Write и shell остаются отключены хостом, песочница не отключается, workspace ограничен каталогом моста. Журнал является аудитом решений моста по остаточным approval-запросам, а не полным аудитом всех разрешённых при allowAll действий: действие, разрешённое сервером без остаточного запроса, строки в журнале может не иметь, и отсутствие строки не доказывает отсутствие инструментального действия (FU-001). Полный аудит инструментов отдельным источником в этом пакете не обещается; селективный запрет по факту payload отложен до данных OPEN-01 и не выдумывается, операционный откат режима — AD-007",
        "verification_ids": ["VER-001", "VER-009"]
      },
      {
        "id": "THREAT-002",
        "scenario": "Логирование approval уносит rawArgs, вопросы userInput или отражённый промпт с секретами в bridge.log и ответы клиенту",
        "mitigation": "Allowlist полей аудита в BND-001, запрет rawArgs и тел вопросов, рендер свободных строк toolName и choiceId только из [A-Za-z0-9_.:-] длиной до 64 с обрезкой списка choiceId до 8 и заменой остальных на redacted с префиксом sha256, вся диагностика через _redact_secrets и удаление отражённых промптов попыток как в REQ-MUSE-001, канареечные тесты на rawArgs и на choiceId (FU-009)",
        "verification_ids": ["VER-001", "VER-005"]
      },
      {
        "id": "THREAT-003",
        "scenario": "Цикл approval или userInput внутри хода либо каскад повторов удерживает оба слота MAX_CONCURRENT=2 и блокирует мост для владельца",
        "mitigation": "Счётные границы 10 decide и 3 cancel на ход с терминальным защёлкиванием, grace 15 с после cancel или отказного decide с убийством группы, абсолютный дедлайн запроса от приёма, не более 2 транзиентных повторов внутри удерживаемого слота, живая запись не дольше 3 с на кадр с веткой зависшего клиента, надзор ухода клиента убивает группу, слот один на ход с карантином неподтверждённой смерти",
        "verification_ids": ["VER-001", "VER-002"]
      },
      {
        "id": "THREAT-004",
        "scenario": "Транзиентный повтор переигрывает промпт после частичных побочных эффектов первой попытки и удваивает действие или вывод",
        "mitigation": "Повтор и fallback запрещены единым предикатом допуска после наблюдаемого начала потенциально неидемпотентного действия: барьер защёлкивается при approval/request|requested, userInput/request, любом decide и любом item с kind вне {reasoning, agentMessage} на serve и при непустом тексте exec-попытки; дополнительно требуются отсутствие контентного кадра, подтверждённая смерть прежних групп и остаток абсолютного дедлайна. Митигация не опирается только на отключённые write/shell, отсутствие кадра и смерть группы: ненаблюдаемая активность без item/approval сигналов остаётся явным остатком ASM-010 с планом закрытия аудитом OPEN-01; семантика at-least-once не принята и AD-001 не покрывается",
        "verification_ids": ["VER-002", "VER-003"]
      }
    ]
  },
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "Авторазрешённое действие неизвестно до первого живого payload: инструмент инцидентов wonder при отключённых write и shell не установлен (OPEN-01)",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Флаги хоста и песочница сохранены, аудит решений моста по остаточным запросам с первого хода, тяжёлый путь владельца сверяет лог решений с ожидаемой работой и отдельно фиксирует ходы без остаточного запроса (отсутствие строки не трактуется как отсутствие действия); селективная политика только отдельным решением по собранным payload, быстрый откат режима — AD-007",
      "verification_ids": ["VER-001", "VER-009"]
    },
    {
      "id": "RISK-002",
      "scenario": "Повторы моста складываются с повторами провайдера CLI и растягивают отказ при живом общем сбое транспорта (OPEN-05, OPEN-08)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Не более 2 транзиентных повторов с паузами суммарно не более 8 с внутри удерживаемого слота и абсолютного дедлайна от приёма, поэтому параллельная нагрузка не превышает MAX_CONCURRENT=2 и глобальный circuit breaker осознанно не вводится (QA-009); modelRetryScheduled логируется для разбора наложения",
      "verification_ids": ["VER-002", "VER-010"]
    },
    {
      "id": "RISK-003",
      "scenario": "Live reasoning сужает окно безопасного повтора и при ошибке учёта хвоста дублирует или теряет часть reasoning в финале",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Префикс-монотонная публикация AD-004: до заморозки стримится только прирост summary.0, финальный хвост доотдаётся только когда сборка расширяет отправленное, при расхождении дубль запрещён и расхождение логируется; _content_started только под _wlock на фактически отправленной дельте, парные тесты interleaved и расхождения snapshot (T-L06, T-L07)",
      "verification_ids": ["VER-002", "VER-003"]
    },
    {
      "id": "RISK-004",
      "scenario": "Общий код меняет поведение muse-spark-*, на которые приходятся 27 из 29 исторических approval-переходов, без отдельного живого сценария",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Фейковые тесты гоняют spark как модель фикстуры ServeRun, окна и лимиты spark не меняются, тяжёлый путь включает короткий контрольный ход spark после wonder",
      "verification_ids": ["VER-001", "VER-005", "VER-009"]
    },
    {
      "id": "RISK-005",
      "scenario": "Автообновление Muse CLI меняет схему MSP или возвращает потолок approvalMode между выкатом и следующим ходом (OPEN-09)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "AD-006: версия и fingerprint в логе каждого хода; потолок -32030 не обходится клиентским approve — ход один раз уходит в существующий exec-fallback до turn/start с warning; неизвестная версия не останавливает мост",
      "verification_ids": ["VER-001", "VER-008"]
    },
    {
      "id": "RISK-006",
      "scenario": "Незакоммиченный REQ-MUSE-001 в дереве dev и единственная деплой-копия делают откат зависимым от бэкапа, ошибка копирования затирает рабочее состояние",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Baseline REQ-MUSE-001 отделяется первым отдельным коммитом до правок REQ-MUSE-002..004 (FU-008), дальнейший diff baseline..HEAD его не содержит; отдельная ветка, бэкап обеих копий server.py в ~/work/backups до перезаписи, проверка diff по protected_paths (VER-012), cmp зеркала и health после перезапуска до тяжёлого пути",
      "verification_ids": ["VER-005", "VER-008"]
    },
    {
      "id": "RISK-007",
      "scenario": "Summary-дельты на effort=max приходят только в конце хода, и прогресс REQ-MUSE-004 недостижим текущим источником reasoning (OPEN-04)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Лог времени первой дельты на каждом serve-ходе и отдельная диагностика VER-011 фиксируют факт, но приёмку не дают: REQ-MUSE-004 остаётся NOT_MET/BLOCKED и блокирует сдачу набора требований; дальше нужен отдельный согласованный путь прогресса или явное изменение требования владельцем новым delta-пакетом, а не закрытие наблюдением",
      "verification_ids": ["VER-003", "VER-009"]
    },
    {
      "id": "RISK-008",
      "scenario": "Форма живого availableChoices отличается от схемы фикстуры (scope, policy amendment, пустой список), и decide получает -32052 или выбирает лишнее разрешение",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Выбор только из текущих choices по decision с запретом policy amendment; ошибки decide и пустые списки ведут в терминальное защёлкивание AD-002 без exec и без повторных команд, аудит пишет отрендеренный список choiceId для сверки с первым живым ходом",
      "verification_ids": ["VER-001", "VER-009"]
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
        "AD-007"
      ],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
      "expected": "exit 0; red без фикса и green с фиксом: allowAll в session/start при env по умолчанию и denyUnmatched при MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched без approve (T-A14), receipt и decide с choiceId из availableChoices, terminal=false, userInput/cancel, границы 10 включая финальный отказной decide и 3, терминальное защёлкивание при четырёх ответах сервера после denied (T-A13), игнорирующий cancel serve теряет группу и слот не позже grace (T-A09b), деградация без exec, ошибка записи receipt/decide после turn/start без exec, -32030 без второго session/start и без decide с одним exec-fallback (T-A11), канарейки rawArgs и choiceId отсутствуют в логе дословно (T-A10)",
      "environment": "локальный репозиторий, фейковый MSP через расширенный install_protocol_wrapper, модельных ходов нет",
      "owner": "verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": ["REQ-MUSE-003", "AD-003", "QA-003", "QA-004", "QA-005", "BND-003", "RISK-002", "RISK-003", "THREAT-003", "THREAT-004", "QA-009"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
      "expected": "exit 0; каждый маркер классифицируется из error.kind/error.message serve-терминала и из stderr exec (T-R01 с реальной формой turn/completed.error), не более 2 транзиентных повторов с паузами 2 с и 4 с плюс джиттер до 1 с (в тестах константы ужаты monkeypatch), вызовов run_attempt не более 3 без контекстного повтора и не более 4 с ним, абсолютный дедлайн от приёма включает ожидание слота и fallback: три параллельных запроса при двух занятых слотах завершаются ответом или предусмотренной ошибкой внутри бюджета (T-R08), серия net-timeout под двумя ходами не превышает 2 параллельных процессов (T-R09, QA-009); нет нового процесса после _content_started, после approval-защёлкивания, после инструментального item заглушки с побочным эффектом до SSE-контента (второй эффект отсутствует, T-R07), при уходе клиента, неподтверждённой смерти группы, остатке не больше 30 с и на состояния timeout и spawn_failed; summary→EOF, summary→ошибка чтения, approval→ошибка записи receipt/decide и cancel→EOF exec не запускают и дают ровно один терминальный исход, EOF рукопожатия до turn/start по-прежнему один раз уходит в exec (T-R06); контекстный счётчик транзиентом не расходуется (обновлённый test_t18)",
      "environment": "локальный репозиторий, фейковые serve и exec с терминальными ошибками net-timeout",
      "owner": "verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": ["REQ-MUSE-004", "AD-004", "QA-005", "QA-006", "BND-002", "BND-004", "CD-001", "RISK-003", "RISK-007", "THREAT-004"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
      "expected": "exit 0; дельты reasoning_content до финального кадра по префикс-монотонному правилу: interleaved-индексы и поздний меньший индекс не переставляют опубликованное (T-L06), расхождение item/completed с накопленными дельтами и повтор финального snapshot не дают дубля и логируют расхождение (T-L07), в расширяющем случае конкатенация равна буферизованному варианту без дубля хвоста; клиент, переставший читать и заполнивший буфер reasoning-дельтами, освобождает процессы и слот в пределах установленного времени живой записи при ужатых константах, второй клиент обслуживается (T-L08); пустые data-keepalive сохранены, : keepalive отсутствует, ровно один [DONE] в неаварийных ветках, обычный сбой live-записи ход исключением ServeRun не роняет",
      "environment": "локальный репозиторий, фейковый MSP с задержанными item/delta summary.N и item/completed",
      "owner": "verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": ["AD-005", "QA-007", "BND-003"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'ContextPrune or ContextRetry or AllowedModelsSync'",
      "expected": "exit 0; гарантии REQ-MUSE-001 без изменений: 400000/320000/200000, обязательный набор, атомарность tool-пар, ровно один контекстный повтор до первого контентного кадра",
      "environment": "локальный репозиторий, pytest через uv --no-project",
      "owner": "verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": ["REQ-MUSE-002", "REQ-MUSE-003", "REQ-MUSE-004", "AD-005", "QA-002", "QA-004", "QA-007", "BND-004", "RISK-004", "RISK-006", "THREAT-002"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py",
      "expected": "exit 0; весь файл зелён: прежний baseline 67 passed сохранён по смыслу, заменён только тест approval-контракта и обновлён test_t18 по AD-003, добавлены тесты Approval, TransientRetry и LiveReasoning сценариев delta-a2 (T-A09b, T-A11, T-A13, T-A14, T-R06..T-R09, T-L06..T-L08); прочие правки тестов вне этого списка, удаления и skip ради зелени запрещены (FU-007)",
      "environment": "локальный репозиторий, ветка Coder от фактического дерева dev",
      "owner": "verifier"
    },
    {
      "id": "VER-006",
      "requirement_ids": ["AD-005", "QA-007"],
      "kind": "command",
      "command": "cd /Users/aazhiry1/work/src/cli-agent-bridge && .venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright",
      "expected": "ruff exit 0 по набору E4/E7/E9/F из ruff.toml; basedpyright 0 errors как baseline брифа, число предупреждений зафиксировано в отчёте verifier против baseline 1448 без новых errors в изменённых файлах",
      "environment": "локальный репозиторий с .venv (ruff и basedpyright присутствуют в .venv/bin)",
      "owner": "verifier"
    },
    {
      "id": "VER-007",
      "requirement_ids": ["REQ-MUSE-002", "REQ-MUSE-003", "REQ-MUSE-004", "QA-007"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/",
      "expected": "exit 0; Full Suite Gate перед MR по всему каталогу tests без deselect и skip правок",
      "environment": "локальный репозиторий, pyproject.toml отсутствует, поэтому uv --no-project",
      "owner": "verifier"
    },
    {
      "id": "VER-008",
      "requirement_ids": ["QA-007", "QA-008", "BND-005", "RISK-005", "RISK-006"],
      "kind": "command",
      "command": "cmp bridges/muse-bridge/server.py ~/.dsh/bridges/muse-bridge/server.py && launchctl list | grep com.user.dsh-muse-bridge && curl -sS -m 5 -H \"Authorization: Bearer $MUSE_BRIDGE_KEY\" http://127.0.0.1:9886/health && curl -sS -m 5 -H \"Authorization: Bearer $MUSE_BRIDGE_KEY\" http://127.0.0.1:9886/v1/models",
      "expected": "зеркало побайтово равно репозиторию, launchd-агент зарегистрирован, /health и /v1/models отвечают 200 с wonder context_length 400000 и spark 1048576; в свежем bridge.log после первого хода видны serve init с версией CLI и approvalMode allowAll",
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
        "THREAT-001"
      ],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate тяжёлого пути и успешной приёмки REQ-MUSE-002..004: в существующем DSH-слоте владельца на длинной сессии живые ходы muse-wonder-full-1.0 effort=max рабочего размера с вызовом инструмента, повторный ход и два параллельных хода завершаются без fallback exec по approval и без потери хода; REQ-MUSE-004 засчитывается только реальным pre-terminal приростом reasoning в UI во время мышления, подтверждённым логом первой summary-дельты строго раньше конца хода, — сценарий «summary только при завершении» этот gate не проходит; ходы с остаточным approval-запросом и без него зафиксированы отдельно, отсутствие аудит-строки не считается доказательством отсутствия инструментального действия; done via=serve; короткий контрольный ход muse-spark проходит. Без этого gate слова готово и работает запрещены",
      "environment": "живой DSH-слот владельца, боевой мост :9886 после VER-008, модельные ходы выполняет владелец или verifier его руками, не Coder",
      "owner": "owner"
    },
    {
      "id": "VER-010",
      "requirement_ids": ["REQ-MUSE-003", "AD-003", "QA-003", "RISK-002"],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate: на отдельном экземпляре моста на другом порту с MUSE_BRIDGE_CLI на заглушку, отдающую net-timeout на первой попытке и успех на второй, запросы JSON и SSE завершаются успехом после ровно одного повтора внутри абсолютного бюджета от приёма; при net-timeout на всех попытках терминальный 502 или SSE error и один [DONE] после 3 попыток без контекстного повтора; боевой мост не затронут",
      "environment": "отдельный экземпляр моста с заглушкой CLI, не боевой :9886",
      "owner": "verifier"
    },
    {
      "id": "VER-011",
      "requirement_ids": ["REQ-MUSE-004", "QA-006", "RISK-007"],
      "kind": "manual",
      "command": null,
      "expected": "Диагностический бинарный gate закрытия OPEN-04, приёмкой не является: для каждого тяжёлого хода VER-009 в bridge.log есть строка времени первой summary-дельты и длительность хода, а отчёт сдачи явно записывает REQ-MUSE-004 как MET только при pre-terminal дельте и как NOT_MET/BLOCKED при дельтах только в конце хода; при NOT_MET набор требований сданным не объявляется и требуется отдельный согласованный путь прогресса или явное изменение требования владельцем. Здесь же по тем же логам считается доля транзиентных сбоев после первой дельты (retry_blocked) для метрики FU-005",
      "environment": "живой DSH-слот владельца и bridge.log боевого моста :9886 после VER-008, разбор выполняет verifier по логам тяжёлых ходов владельца, не Coder",
      "owner": "verifier"
    },
    {
      "id": "VER-012",
      "requirement_ids": ["AD-005", "QA-007", "BND-005", "RISK-006"],
      "kind": "command",
      "command": "git -C /Users/aazhiry1/work/src/cli-agent-bridge diff --name-only BASELINE..HEAD -- ruff.toml pyrightconfig.json server.py docs/adr/0001-persistent-droid-bridge.md docs/adr/0002-multi-binary-hub.md",
      "expected": "пустой вывод: ни один защищённый путь после отдельного baseline-коммита REQ-MUSE-001 не изменён; BASELINE подставляется верификатором хэшем baseline-коммита из rollout (шаг 0), docs/adr/0003 меняется только материализацией оркестратора exact bytes, а не правкой Coder (FU-007, FU-008)",
      "environment": "локальный репозиторий, ветка Coder после baseline-коммита",
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
      "sha256": "4754421f51b6bce05710efdc273dd17a83c6ed773b6a93775394c77c795c0b2b"
    }
  ],
  "approval": {
    "status": "APPROVED",
    "decision_ids": ["AD-001"],
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
      "question": "OPEN-04: приходят ли summary.N по ходу хода на effort=max и за сколько секунд до конца; закрывается диагностикой VER-011 по логу первой дельты. Вопрос не блокирует утверждение пакета, но при ответе «только в конце» блокирует приёмку REQ-MUSE-004 (VER-009 не проходит)",
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
    "глобальный cooldown или circuit breaker повторов, если наблюдение QA-009 в эксплуатации покажет рост нагрузки вопреки удерживаемым слотам (FU-010)"
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
        "source_findings": ["F-001"],
        "disposition": "accepted",
        "changed_ids": ["AD-002", "AD-003", "BND-002", "BND-003", "VIEW-001", "VIEW-002", "VER-002", "EVD-023"],
        "verification_ids": ["VER-002", "VER-001"],
        "tests": ["T-R06"],
        "note": "Единый предикат допуска любого нового процесса в AD-003/BND-003; exec-fallback только до принятого turn/start и до approval-трафика, после — EOF/ошибки чтения/записи stdin/таймаут терминальны без exec с ровно одним исходом; противоречие счётчика снято: fallback расходует дедлайн и лимит процессов и проходит тот же предикат"
      },
      {
        "id": "RW-002",
        "source_findings": ["F-002"],
        "disposition": "accepted",
        "changed_ids": ["AD-003", "QA-003", "QA-004", "BND-003", "VER-002", "VER-010", "EVD-025"],
        "verification_ids": ["VER-002", "VER-010"],
        "tests": ["T-R08"],
        "note": "Абсолютный дедлайн TIMEOUT_S=1800 с от приёма запроса включает ожидание слота, попытки, fallback, паузы, grace и cleanup; ожидание слота и новая попытка обрываются за 30 с до дедлайна, запас до клиентских 1900 с — 100 с при значениях по умолчанию; потолок записан одинаково в AD-003 и QA-004"
      },
      {
        "id": "RW-003",
        "source_findings": ["F-003"],
        "disposition": "accepted",
        "changed_ids": ["AD-003", "THREAT-004", "QA-005", "ASM-010", "BND-002", "BND-003", "VER-002"],
        "verification_ids": ["VER-002", "VER-003"],
        "tests": ["T-R07"],
        "note": "Выбран запрет повтора после наблюдаемого начала потенциально неидемпотентного инструмента: барьер item kind вне reasoning/agentMessage, approval/userInput трафик, любой decide, непустой текст exec; митигация THREAT-004 переписана без опоры только на флаги и смерть группы, ненаблюдаемый остаток — ASM-010 с планом закрытия; at-least-once не принята и AD-001 не покрывается"
      },
      {
        "id": "RW-004",
        "source_findings": ["F-004"],
        "disposition": "accepted",
        "changed_ids": ["AD-004", "BND-002", "BND-004", "QA-006", "THREAT-003", "VER-003", "EVD-024"],
        "verification_ids": ["VER-003"],
        "tests": ["T-L08"],
        "note": "LIVE_WRITE_TIMEOUT_S=3 с на кадр механизмом settimeout под _wlock с восстановлением, как в droid-мосте (EVD-015, EVD-024); таймаут/частичная запись — зависший клиент: live выключена, соединение разорвано без гарантии [DONE], группа убита, слот свободен в пределах предела плюс подтверждение смерти; очередь-писатель отклонена в альтернативах AD-004"
      },
      {
        "id": "RW-005",
        "source_findings": ["F-005", "F-012"],
        "disposition": "accepted",
        "changed_ids": ["AD-004", "BND-004", "CD-001", "QA-006", "RISK-003", "VER-003"],
        "verification_ids": ["VER-003"],
        "tests": ["T-L06", "T-L07"],
        "note": "Префикс-монотонная публикация: стримится только прирост summary.0 до заморозки (первая дельта индекса больше 0, item/completed reasoning или конец хода), финал доотдаёт хвост только при F.startswith(P), при расхождении дубль запрещён и расхождение логируется; F-012 закрыт этим же решением как duplicate_of F-005"
      },
      {
        "id": "RW-006",
        "source_findings": ["F-006"],
        "disposition": "accepted",
        "changed_ids": ["AD-002", "BND-002", "QA-001", "ASM-006", "VER-001"],
        "verification_ids": ["VER-001"],
        "tests": ["T-A13"],
        "note": "Терминальное защёлкивание отказа: предел 10 decide включает финальный abort/denied, одиннадцатого нет; после защёлкивания новых разрешений и повторных деградаций нет, локальный неуспешный исход не меняют повторный request, terminal=false, успешный terminal и молчание сервера; ровно один терминальный исход без exec во всех ветках"
      },
      {
        "id": "RW-007",
        "source_findings": ["F-007"],
        "disposition": "accepted",
        "changed_ids": ["VER-009", "VER-011", "RISK-007", "QA-006", "AD-004", "ASM-004"],
        "verification_ids": ["VER-009", "VER-011", "VER-003"],
        "tests": [],
        "note": "VER-009 разделён: успешная приёмка только при реальном pre-terminal приросте reasoning в DSH-слоте; диагностическое закрытие OPEN-04 вынесено в VER-011, ветка «либо лог фиксирует конец» из PASS убрана, при summary только в конце REQ-MUSE-004 равен NOT_MET/BLOCKED"
      },
      {
        "id": "RW-008",
        "source_findings": ["F-011"],
        "disposition": "accepted",
        "changed_ids": ["AD-002", "THREAT-003", "ASM-006", "QA-001", "QA-004", "VER-001"],
        "verification_ids": ["VER-001", "VER-002"],
        "tests": ["T-A09b"],
        "note": "APPROVAL_CANCEL_GRACE_S=15 с после turn/cancel или decide(abort/denied), затем убийство группы serve, один терминальный исход и освобождение слота без ожидания 1800 с; pending approval внутри grace команд не получает, влияние cancel на него опорой не является"
      },
      {
        "id": "FU-001",
        "source_findings": ["F-008"],
        "disposition": "accepted",
        "changed_ids": ["THREAT-001", "AD-002", "RISK-001", "VER-009"],
        "verification_ids": ["VER-001", "VER-009"],
        "tests": [],
        "note": "Журнал назван аудитом решений моста по остаточным запросам; полный аудит инструментов не обещается, тяжёлый gate отдельно фиксирует ходы с запросом и без него"
      },
      {
        "id": "FU-002",
        "source_findings": ["F-009"],
        "disposition": "accepted_without_owner_permission_path",
        "changed_ids": ["AD-006", "QA-008", "RISK-005", "VER-001", "Q-009"],
        "verification_ids": ["VER-001"],
        "tests": ["T-A11"],
        "note": "Выбран путь без разрешения на обход: при -32030 клиентское автоодобрение не включается, ход уходит в один exec-fallback до turn/start с warning; обход ceiling допустим только по будущему явному решению владельца Q-009 с записью в ADR 0003 новой материализацией"
      },
      {
        "id": "FU-003",
        "source_findings": ["F-010"],
        "disposition": "rejected_with_rationale",
        "changed_ids": ["AD-002", "BND-001", "Q-001"],
        "verification_ids": ["VER-001"],
        "tests": [],
        "note": "Deny при protectedWrite/judgeEscalated отклонён в этом delta: payload и семантика полей не наблюдались, judge в serve отключён, write отключён хостом, исход после denied неизвестен с риском цикла; признаки логируются, правило — отдельным решением владельца по payload; тест T-A12 поэтому не вводится"
      },
      {
        "id": "FU-004",
        "source_findings": ["F-013"],
        "disposition": "accepted",
        "changed_ids": ["AD-002", "RISK-004"],
        "verification_ids": ["VER-001"],
        "tests": [],
        "note": "Альтернатива exec последним шагом деградации добавлена в AD-002 и отклонена из-за барьера RW-003; потеря исхода принята с измеримым условием пересмотра по логу approval_degraded, исторические 27 переходов spark отнесены к старому ServeUnavailable без разрешений моста"
      },
      {
        "id": "FU-005",
        "source_findings": ["F-014"],
        "disposition": "accepted",
        "changed_ids": ["AD-003", "AD-004", "QA-005", "VER-011"],
        "verification_ids": ["VER-002", "VER-011"],
        "tests": [],
        "note": "Альтернатива повтора с подавлением префикса добавлена в AD-003 и AD-004 и отклонена (нет гарантии общего префикса второй генерации); метрика доли «первая дельта раньше сбоя» считается по логам первой дельты и retry_blocked в VER-011"
      },
      {
        "id": "FU-006",
        "source_findings": ["F-015"],
        "disposition": "accepted",
        "changed_ids": ["QA-004", "AD-003", "VER-002", "VER-010"],
        "verification_ids": ["VER-002"],
        "tests": [],
        "note": "Числа приведены к одним: run_attempt не более 3 без контекстного повтора и не более 4 с ним (1 + 1 + 2) в AD-003, QA-004, VER-002 и VER-010"
      },
      {
        "id": "FU-007",
        "source_findings": ["F-016"],
        "disposition": "accepted",
        "changed_ids": ["protected_paths", "VER-012", "VER-005", "BND-005"],
        "verification_ids": ["VER-012", "VER-005"],
        "tests": [],
        "note": "protected_paths расширен точными файлами ruff.toml, pyrightconfig.json, ADR 0001 и 0002, корневого server.py; правки тестов ограничены явным списком в BND-005 и VER-005, проверка diff — VER-012"
      },
      {
        "id": "FU-008",
        "source_findings": ["F-017"],
        "disposition": "accepted",
        "changed_ids": ["evolution.rollout", "VIEW-004", "RISK-006", "BND-005", "VER-012"],
        "verification_ids": ["VER-012", "VER-005"],
        "tests": [],
        "note": "Шаг 0 rollout: baseline REQ-MUSE-001 отдельным коммитом до правок REQ-MUSE-002..004, diff baseline..HEAD содержит только новую дельту"
      },
      {
        "id": "FU-009",
        "source_findings": ["F-018"],
        "disposition": "accepted",
        "changed_ids": ["BND-001", "THREAT-002", "QA-002", "AD-002", "VER-001"],
        "verification_ids": ["VER-001"],
        "tests": ["T-A10"],
        "note": "toolName и choiceId в аудите только из [A-Za-z0-9_.:-] до 64 символов, список choiceId до 8, остальное redacted с длиной и sha256-префиксом; канарейка choiceId дословно в bridge.log не попадает, сырые значения в команде decide не меняются"
      },
      {
        "id": "FU-010",
        "source_findings": ["F-019"],
        "disposition": "accepted_with_justified_refusal_of_breaker",
        "changed_ids": ["RISK-002", "AD-003", "THREAT-003", "QA-009", "VER-002"],
        "verification_ids": ["VER-002"],
        "tests": ["T-R09"],
        "note": "Добавлены анализ и QA-009 «серия net-timeout под двумя ходами»; глобальный cooldown/circuit breaker отклонён с обоснованием: слот удерживается весь ход, параллельная нагрузка не растёт выше 2, длительность ограничивают паузы и абсолютный дедлайн; потолок заново не определяется и ссылается на RW-002"
      },
      {
        "id": "FU-011",
        "source_findings": ["F-020"],
        "disposition": "accepted",
        "changed_ids": ["AD-007", "AD-002", "BND-001", "evolution.rollback", "VER-001"],
        "verification_ids": ["VER-001"],
        "tests": ["T-A14"],
        "note": "Введён env-переключатель MUSE_BRIDGE_APPROVAL_MODE (allowAll по умолчанию, denyUnmatched) новым AD-007; смена режима — env и перезапуск без правки кода, фиксация в ADR 0003 новой материализацией"
      },
      {
        "id": "FU-012",
        "source_findings": ["F-021"],
        "disposition": "accepted",
        "changed_ids": ["AD-003", "VER-002"],
        "verification_ids": ["VER-002"],
        "tests": ["T-R01"],
        "note": "Источник транзиентного текста указан явно: serve — turn/completed.error с проверкой error.kind и error.message, exec — stderr; T-R01 требует фикстуру реальной формы serve-терминала с маркером в error.message из лога"
      }
    ]
  }
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ receipt-ARCH_GATE:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/arch-gate-a2.json sha256=773f7d40a4c78e2ae410f1c4aee91ab633f82006861d5706ee3e6eb04209c065
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "packet_sha256": "c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e",
  "verification_surface_sha256": "7e03a3babf02d9f2981f2fef004fb5560b4499ec426ce257bece6f6f6e025a6f",
  "protected_paths_sha256": "23b893508ca791df60756570bf930589bd15d122a3a0aa3dceb8d1b4952e58f6",
  "architect_worktree_sha256": "777a3d55b0ef66fd65bc558d5a865d93befc1b3ffbe798753354de821d0d8ac9",
  "materialized_targets": 1
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ task-envelope:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/task.json sha256=a3e0a03b9fc8efaaad2a5806664560aad16e1eee1fe9f3c8ea4b9a462747c778
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
    "packet_sha256": "c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e",
    "verification_surface_sha256": "7e03a3babf02d9f2981f2fef004fb5560b4499ec426ce257bece6f6f6e025a6f",
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
<<<ARTIFACT /tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md sha256=72232aee6173f05735c8eb3c6ff98844757e79ddcabc85dbd8983403dc01465b
2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)
2026-10-15 13:39 MSK | находки арх-панели F-002, F-003, F-004, F-006 (OBJECT автора при C1, PAUSED_OWNER) | владелец выбрал в чате по каждой: «blocking (Рекомендуется)» | опции: blocking / non-blocking / excluded | итог: все четыре blocking, входят в instructions для Architect delta
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
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md sha256=4ab433db5f0649c0a7a3477401b0d785b7c3d34ad6ecdf9d3c697e79c31c55a6
# Архитектурная спецификация: muse-bridge — approval без перезапуска хода, повтор net-timeout, живость долгих ходов

Статус пакета: `APPROVED` (delta a2 после арх-панели cycle-1 NEEDS WORK: RW-001..RW-008, FU-001..FU-012; трассировка — секция `delta_a2` пакета и `architecture/delta-a2.md`; валидатор фазы approved зелёный, повторный ARCH_GATE впереди).
Пакет: `.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json`.
ADR политики: `architecture/proposals/docs/adr/0003-muse-serve-approval-allowall.md`
(материализация в `docs/adr/0003-muse-serve-approval-allowall.md` оркестратором после approval).
Нумерация: AD-001..AD-006, QA, BND, RISK, THREAT, VER — как в пакете; факты [F-NN] —
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
       с warning и ровно одним exec-fallback Handler (AD-006, без обхода потолка)
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
  преобразуется), тело `result: {}` (RequestReceipt, EVD-006). Ошибка записи после принятого
  `turn/start` — терминальная деградация §2.4 без exec; до `turn/start` — транспортный
  `ServeUnavailable` ветки fallback §3.2. Классификацию (принят ли turn/start, был ли
  approval-трафик, защёлкнут ли барьер активности §3.2) ServeRun доводит до Handler,
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
  инцидентах приходил на 275 с и 412 с. После принятого `turn/start` граница
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

Терминальное защёлкивание отказа (RW-006). Триггеры: нет разрешающего выбора,
ошибка decide `-32050/-32052/-32053`, превышение границы, ошибка записи stdin
после принятого `turn/start`. При первом триггере локальный исход хода
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

Grace после деградации (RW-008): после отправки `turn/cancel` или отказного
decide мост ждёт `turn/completed` не дольше `APPROVAL_CANCEL_GRACE_S=15` с
(один интервал keepalive, входит в абсолютный дедлайн §3.3); по истечении —
убийство группы процессов serve существующей механикой, терминальная ошибка,
освобождение слота. Ожидания дедлайна 1800 с ради слота здесь нет: два
проигнорировавших cancel хода мост целиком не блокируют.

Exec-рестарт по ветке деградации запрещён; альтернатива «exec последним шагом
деградации до `_content_started`» взвешена и отклонена в AD-002 (FU-004):
после approval-трафика барьер активности §3.2 может быть уже пройден.
Каждая деградация логируется `approval_degraded` с флагами `content_started`
и барьера активности — это измеримый вход условия её пересмотра.

Что меняется против a1 в fallback (RW-001): тихий exec fallback по
`ServeUnavailable` сохраняется **только до принятого `turn/start`** и до любого
approval-трафика (спавн, handshake, `session/start`, EOF и RPC-ошибки setup,
включая ветку `-32030` из AD-006). После принятого `turn/start` EOF, ошибка
чтения, ошибка записи stdin и дедлайн чтения — терминальные без exec;
`cancel` → EOF — ожидаемое подтверждение очистки, а не повод для fallback.
Ошибка модели (`terminal != completed`) по-прежнему не фолбэчится; при
ушедшем клиенте надзор убивает группу и ничего нового не стартует. Approval
во время setup-фазы (`await_result` маршрутизирует чужие сообщения в тот же
обработчик) проходит тот же путь: `sessionId` берётся из снимка, локальная
сессия моста может ещё не существовать.

## 3. REQ-MUSE-003: ограниченный повтор транзиентных сбоев

Решение AD-003 (APPROVED), граница BND-003. Внутренний однократный сетевой повтор внутри
exec-after-fallback (`server.py:2435-2445`) поглощается этим механизмом:
отдельного третьего пути повтора не остаётся.

### 3.1 Классификация (только явные маркеры)

Попытка считается транзиентно-транспортной, когда её сырой канал ошибки (до
редакции, как детектор hard threshold) содержит хотя бы одну подстроку:

| Маркер | Источник |
|---|---|
| `[net-timeout]` | лог и бенч (EVD-011) |
| `timed out waiting for response data` | лог и бенч (EVD-011) |
| `network connection could not be opened` | существующий `NETWORK_RETRY_MARKER` (EVD-010) |
| `transport_connect_unreachable` | текст REQ-MUSE-003; в логах на 2026-10-15 не засвидетельствован (grep пуст), тест синтетический |

Источник текста явный (FU-012): на serve классификатор смотрит конкатенацию `turn/completed.error.kind` и `error.message` до редакции (поля схемы F-35), на exec — сырой stderr-канал ошибки; значения enum `kind` не выдумываются, маркеры ищутся в обоих полях. Классификатор — чистая проверка по образцу `_has_hard_threshold_marker`,
результат — флаг в словаре попытки по образцу `hard_threshold`. Поле
`retryable` ошибки serve само по себе класс не даёт: hard threshold тоже
`retryable=True` и принадлежит контекстному пути. Подстрока в обычном тексте
ответа при `rc == 0` повтор не запускает. Состояния `timeout`, `spawn_failed`,
`launcher_missing`, `client_gone` не повторяются при любом тексте: первое уже
исчерпало бюджет, остальные детерминистичны или бессмысленны без клиента.

### 3.2 Условия повтора (все одновременно)

1. Попытка неуспешна (`rc != 0`) и классифицирована транзиентной (§3.1), при этом
   не является hard threshold с доступным контекстным повтором (приоритет §3.3).
2. Транзиентных повторов в этом запросе было меньше 2 (отдельный счётчик запроса,
   не попытки). Внутренний serve→exec fallback счётчик не расходует только в
   до-турновой ветке, где исхода хода ещё не было, но проходит тот же предикат,
   тот же дедлайн и тот же лимит процессов — бесплатным он не является (RW-001).
3. Клиент на месте (`_client_gone` ложен и проба отрицательна) в момент решения
   и после паузы.
4. Контентные кадры не отправлялись: `_content_started` ложен. Пустые keepalive и
   role-кадр границей не являются; первая фактически отправленная live
   reasoning-дельта является (§4.2), буферизованная неотправленная — нет.
5. Инструментальная активность не зафиксирована (барьер RW-003): на serve не было
   `approval/request|requested`, `userInput/request`, отправленного decide и item
   с `kind` вне {`reasoning`, `agentMessage`} (ServeRun уже ведёт `kinds` по
   item/started|completed, EVD-025); на exec результат попытки не несёт текста и
   summaries. Approval-деградация не защёлкнута.
6. Все группы процессов прежних попыток закрыты и `dead_confirmed` истинен;
   иначе действует существующий карантин слота, повтор не стартует.
7. Остаток абсолютного бюджета (§3.3) больше 30 с; пауза повтора входит в бюджет.
8. Промпт повтора — тот же `attempt_prompt` текущей попытки дословно; прунинг на
   транзиентной ветке не выполняется.

Тот же предикат (пункты 3–7) гейтит контекстный повтор и до-турновый
exec-fallback: новый процесс в обход предиката не стартует ни в одной ветке.
Для контекстного повтора это ужесточение только сужает прежнее условие
«ровно один и до первого контентного кадра» (AD-005 сохранён как верхняя
граница).

### 3.3 Бюджеты, дедлайн и взаимодействие счётчиков

- Абсолютный дедлайн запроса (RW-002): якорь — приём запроса Handler
  (monotonic до ожидания слота и первой попытки), бюджет равен `TIMEOUT_S`
  (1800 с при значениях по умолчанию) и включает ожидание слота, все попытки,
  до-турновый fallback, паузы, grace §2.4, cleanup и финальную выдачу. Каждая
  попытка получает только остаток до дедлайна (ServeRun — дедлайн чтения,
  Run — таймер); первая попытка при пустой очереди фактически получает полный
  `TIMEOUT_S`, как сегодня. Ожидание слота завершается предусмотренной
  ошибкой (503 до SSE-заголовков либо SSE error после них, формы прежние) не
  позже чем за `SERVE_SPAWN_TIMEOUT_S` (30 с) до дедлайна; остаток не больше
  30 с запрещает и новую попытку: меньше handshake-окна попытка не имеет
  шанса начаться. Против клиентских 1900 с (EVD-016) при значениях по
  умолчанию остаётся запас 100 с; операторский `TIMEOUT_S` выше 1900 с эту
  гарантию снимает, пакет её не обещает.
- Контекстный повтор (ровно 1, AD-005) получает тот же остаток абсолютного
  бюджета и проходит предикат §3.2.
- Цикл запроса детерминирован: после каждой попытки сначала проверяется
  контекстный повтор (hard threshold, свой счётчик, прунённый промпт), затем
  транзиентный (свой счётчик, тот же промпт), иначе терминальный исход.
  Верхняя граница едина везде (FU-006): не более 3 вызовов `run_attempt` без
  контекстного повтора и не более 4 с ним (1 + 1 контекстный + 2
  транзиентных), не более 8 процессов с до-турновым fallback, все в одном
  слоте и внутри абсолютного бюджета.
- Паузы между транзиентными попытками: 2 с, затем 4 с, каждая плюс джиттер
  равномерно до 1 с; суммарно не более 8 с. Пауза спит срезами не дольше тика
  надзора клиента (0.25 с) и прерывается уходом клиента. Длительности читаются
  из модульных констант в момент повтора, чтобы тесты ужимали их monkeypatch,
  как сегодня ужимается `KEEPALIVE_S`.
- Нагрузка при деградации транспорта (FU-010, QA-009): слот удерживается на
  весь ход, поэтому повторы не поднимают параллельность выше
  `MAX_CONCURRENT=2`; глобальный cooldown и circuit breaker осознанно не
  вводятся, суммарную длительность ограничивают паузы и абсолютный дедлайн.
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
- Ограниченное время живой записи (RW-004): Handler-sink пишет только через
  существующий `_sse_emit`/`_sse_write` под `_wlock`, только в фазе OPEN и при
  живом клиенте; на время живой записи сокету под тем же замком выставляется
  timeout `LIVE_WRITE_TIMEOUT_S=3` с восстановлением прежнего значения после
  записи — механизм соседнего droid-моста того же клиента (EVD-015, EVD-024;
  сегодня в muse-мосте предел только общий timeout соединения 300 с). Цикл
  чтения MSP блокируется не дольше 3 с на кадр, дедлайн хода медленным
  клиентом не срывается. Таймаут или частичная запись кадра = зависший
  клиент: live отключается, соединение считается разорванным (частично
  записанный кадр корректного `[DONE]` уже не гарантирует), дальше работает
  существующий путь ухода клиента — убийство группы и освобождение слота в
  пределах 3 с плюс подтверждение смерти группы. Отдельной очереди кадров не
  вводится (отклонённая альтернатива AD-004).
- Префикс-монотонная публикация (RW-005). Порядок опубликованного задним
  числом не меняется: до заморозки live отдаёт только прирост
  `summary_parts[0]`. Заморозка наступает при первой дельте с индексом больше
  0, при `item/completed` reasoning или в конце хода; дальше дельты только
  копятся. Поздний меньший индекс (первой пришла `summary.1`) ничего не
  публикует до согласования. Финальное согласование в `_send_sse`: пусть `F`
  — сегодняшняя сборка `"\n\n".join(summaries)`, `P` — уже отправленный
  live-текст. Если `F` начинается с `P`, доотдаётся только хвост `F[len(P):]`
  (при полном live финального reasoning-кадра нет, повтор snapshot хвоста не
  даёт); если нет — хвост не отправляется, расхождение логируется длинами без
  текста. Так последовательность `0:"a" → 1:"b" → 0:"c"` даёт клиенту
  `"a"` + хвост `"c\n\nb"` = итоговую `"ac\n\nb"`, а расхождение
  `item/completed` с дельтами не дублирует и не переставляет текст.
  Non-stream ответ всегда несёт авторитетную сборку `F` целиком.
- Первый фактически отправленный непустой reasoning-кадр выставляет
  `_content_started` под тем же замком до записи — с этого момента повторы §3
  и контекстный повтор запрещены; буферизованная, но не отправленная дельта
  флага не ставит.
- Keepalive без изменений: пустой data-чанк каждые 15 с в фазе OPEN. Переход на
  SSE-комментарии droid-моста не делается (OPEN-03, deferred): пустые чанки
  доказано держат этого клиента, комментарии для muse-моста не проверены, а
  тест test_s1 закрепляет отсутствие `: keepalive` и сохраняется.

### 4.3 Наблюдаемость прогресса

- Первая summary-дельта хода логируется строкой с секундами от старта хода и
  индексом (без текста): это вход отдельной диагностики VER-011; приёмку VER-009 наблюдение не заменяет (RW-007). На транзиентном терминале при истинном `_content_started` пишется строка `retry_blocked` — пара логов даёт долю ходов «первая дельта раньше сбоя» для метрики FU-005.
  Существующая строка `reasoning summaries=... preview=` в конце хода не меняется.
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
каждое решение моста по остаточному запросу видно владельцу в логе (полный аудит действий без остаточного запроса пакет не обещает, FU-001); откат политики — env-переключатель AD-007 и перезапуск (§7). Селективный deny без payload не
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
| T-A08 | Approval | пустой `availableChoices`, ошибка decide `-32052`: деградация abort/denied или `turn/cancel`, терминальная ошибка, exec не стартует |
| T-A09 | Approval | серия запросов сверх границ 10 и 3: ход остановлен деградацией без одиннадцатого decide, группа мертва, слот свободен |
| T-A09b | Approval | фейковый serve игнорирует `turn/cancel` и отказной decide (RW-008): группа мертва и слот освобождён не позже ужатого grace после деградации, клиенту один терминальный исход, exec не стартует |
| T-A10 | Approval | канарейки в `rawArgs`, в вопросе userInput и в `choiceId`/`toolName` отсутствуют в логе дословно, JSON и SSE (FU-009); аудит-строка содержит только разрешённые поля с ограниченным рендером |
| T-A11 | Approval | `-32030` на старт с явным режимом (FU-002): второго `session/start` и `approval/decide` нет, warning с версией, ровно один exec-fallback до `turn/start`, один процесс serve (AD-006) |
| T-A13 | Approval | терминальное защёлкивание (RW-006): после denied сервер поочерёдно повторяет request, возвращает `terminal=false`, присылает успешный terminal, не завершает ход; во всех ветках не более 10 decide, exec нет, ровно один терминальный исход, поздний успех отброшен |
| T-A14 | Approval | env-режим (AD-007): `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` уходит в `session/start` и approve не отправляется; без env — `allowAll`; невалидное значение останавливает старт с ошибкой |
| T-R01 | TransientRetry | каждый из четырёх маркеров: на serve в реальной форме `turn/completed.error` с маркером в `error.message` и учётом `error.kind` (FU-012), на exec в stderr: повтор и успех, ровно 2 попытки, один [DONE], нет error между |
| T-R02 | TransientRetry | три транзиентных отказа: ровно 3 попытки, терминальная ошибка прежнего формата, группы мертвы, слот освобождён один раз |
| T-R03 | TransientRetry | нет повтора: после первой live-дельты, при уходе клиента в паузе и во время попытки, при `dead_confirmed` ложном, при остатке бюджета не больше 30 с, на `timeout` и `spawn_failed`, на маркере в успешном тексте |
| T-R04 | TransientRetry | hard threshold в приоритете: контекстный повтор с прунённым промптом, транзиентный счётчик не израсходован; обновлённый test_t18 сохраняет это утверждение |
| T-R05 | TransientRetry | повторная попытка получает только остаток абсолютного бюджета от приёма (фикстура фиксирует переданный дедлайн/таймер меньше полного TIMEOUT_S) |
| T-R06 | TransientRetry | предикат допуска (RW-001): summary→EOF, summary→ошибка чтения, approval→ошибка записи receipt/decide, cancel→EOF не запускают exec и дают один терминальный исход; EOF рукопожатия до `turn/start` один раз уходит в exec |
| T-R07 | TransientRetry | барьер активности (RW-003): заглушка пишет наблюдаемый маркер побочного эффекта и шлёт инструментальный item до любого SSE-контента, затем net-timeout; второй попытки и второго эффекта нет; тот же сбой без item повторяется |
| T-R08 | TransientRetry | абсолютный дедлайн (RW-002): три одновременных запроса при двух занятых слотах, задержанные serve и fallback; третий получает ответ или предусмотренную ошибку внутри бюджета от приёма, слоты освобождены по одному разу |
| T-R09 | TransientRetry | серия net-timeout под двумя параллельными ходами (QA-009): одновременно не более 2 процессов, повторы внутри слотов с паузами, оба исхода внутри абсолютного дедлайна |
| T-L01 | LiveReasoning | дельты `summary.0` и `summary.1` с задержкой: кадры reasoning до финального, порядок индексов, разделитель, конкатенация равна буферизованному варианту, финального дубля нет |
| T-L02 | LiveReasoning | summary только из `item/completed` без дельт не теряется ни в live, ни в non-stream `reasoning_summaries` |
| T-L03 | LiveReasoning + test_s1 | пустые keepalive-чанки сохранены, `: keepalive` отсутствует, один [DONE], content и tool_calls целы |
| T-L04 | LiveReasoning | сбой записи в середине live: ход не падает исключением ServeRun, live отключён, терминальный путь существующий |
| T-L05 | LiveReasoning | `turn/modelRetryScheduled` только в логе полями уведомления, в SSE текста нет, `_content_started` им не выставляется |
| T-L06 | LiveReasoning | out-of-order (RW-005): `0:a → 1:b → 0:c` и поздний меньший индекс (`1` раньше `0`): опубликованный порядок не переписывается, клиентская конкатенация равна сборке по индексам, потерь и дублей нет |
| T-L07 | LiveReasoning | расхождение `item/completed` с дельтами и повтор финального snapshot (RW-005): дубль не отправляется, расхождение в логе длинами, non-stream несёт авторитетную сборку |
| T-L08 | LiveReasoning | медленный клиент (RW-004): клиент не читает, заглушка заполняет буфер дельтами при ужатом `LIVE_WRITE_TIMEOUT_S`; группа мертва и слот свободен в пределах предела, второй клиент получает полный ответ |

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
2. Бэкап до деплоя: репозиторный и зеркальный `server.py` в `~/work/backups/`
   с датой в имени. Профили DSH в этом изменении не трогаются, их бэкап не нужен.
3. Оркестратор материализует ADR 0003 по `materialization[]` пакета exact bytes
   с read-back sha256 (в delta a2 proposal обновлён: ветка `-32030` без обхода
   и env-переключатель AD-007 — материализованный файл заменяется отдельной
   операцией оркестратора, Coder его не правит); Coder добавляет одну строку
   0003 в `docs/adr/INDEX.md` тем же MR. Merge — человек после ACCEPT.
4. Деплой в окно без активных ходов владельца (`kickstart -k` убивает текущий
   процесс моста): копия `bridges/muse-bridge/server.py` в
   `~/.dsh/bridges/muse-bridge/server.py`, затем
   `launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge`.
5. Лёгкий путь VER-008: `cmp` зеркала, агент в `launchctl list`, `/health` и
   `/v1/models` с ключом, свежий `serve init` с версией и `approvalMode` в логе.
   Лёгкий путь сдачей не является.
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
7. Откат: быстрый — `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` в env launchd и kickstart (AD-007). Полный — вернуть обе копии `server.py` из бэкапа шага 2 и повторить kickstart.
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
| Паузы повторов | 2 с, 4 с, джиттер до 1 с | суммарно не более 8 с внутри бюджета |
| Минимальный остаток для повтора и старта из очереди | больше 30 с до абсолютного дедлайна | равен `SERVE_SPAWN_TIMEOUT_S`, §3.3 |
| Абсолютный бюджет запроса | `TIMEOUT_S` (1800 с) от приёма, включая ожидание слота | RW-002 против клиентских 1900 с (EVD-016) |
| Grace после cancel / отказного decide | 15 с | RW-008: один интервал keepalive, в диапазоне панели 10–30 с |
| Предел живой записи SSE | 3 с на кадр (`LIVE_WRITE_TIMEOUT_S`) | RW-004: эталон droid-моста того же клиента (EVD-015, EVD-024) |
| Рендер свободных строк аудита | `[A-Za-z0-9_.:-]`, до 64 симв., список choiceId до 8 | FU-009, канарейка T-A10 |
| Маркеры транзиента | 4 подстроки §3.1 | лог, бенч, текст REQ, прежний маркер |

Трассировка: REQ-MUSE-002 → AD-001, AD-002, AD-006, AD-007 → QA-001, QA-002, QA-008 →
VER-001, VER-009. REQ-MUSE-003 → AD-003 → QA-003, QA-004, QA-005, QA-009 → VER-002,
VER-010. REQ-MUSE-004 → AD-004, CD-001 → QA-005, QA-006 → VER-003, VER-009, VER-011. Защищённые пути и baseline → BND-005 → VER-012. Полная трассировка delta — секция `delta_a2` пакета и `architecture/delta-a2.md`.
Наследство REQ-MUSE-001 → AD-005 → QA-007 → VER-004..VER-008.

Не-цели этого изменения: починка ProxyRack и форвардера `:10816`, UI и профили
DSH, закрепление версии CLI, live content, селективные запреты approval,
изменение exec-флагов и лимитов spark. Открытые вопросы Q-001..009 и deferred
пакета сдачу не блокируют и не закрываются молча: каждый имеет наблюдаемый
способ закрытия в логе или на тяжёлом пути.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ adr-0003:
<<<ARTIFACT ~/work/src/cli-agent-bridge/docs/adr/0003-muse-serve-approval-allowall.md sha256=4754421f51b6bce05710efdc273dd17a83c6ed773b6a93775394c77c795c0b2b
# 0003 — Неинтерактивный muse-bridge: approvalMode `allowAll` на `session/start` вместо перезапуска хода через `exec`

## Status

Accepted (2026-10-15). Формат: ADR-full — решение меняет границу доверия «модель → инструменты»
(безопасность) и поведение боевого моста DSH → Meta Muse (`:9886`, launchd
`com.user.dsh-muse-bridge`), откат требует смены режима и перезапуска моста.
Решение владельца принято 2026-10-15 05:44 MSK в чате: «Авторазрешение (allowAll)»
(запись: `/tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md`, вопрос OPEN-07).
Архитектурный пакет: `.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json`
(AD-001, AD-002). Не отменяет ADR 0001/0002 и решения REQ-MUSE-001 (прунинг 400k/320k/200k).

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
  автоодобрением не обходится: ход один раз уходит в существующий `exec`-fallback до `turn/start`
  с warning, второго старта без поля и `decide`-одобрений поверх серверного `promptUnmatched`
  нет (пакет AD-006; обход потолка — только по отдельному явному решению владельца).
- Режим переключается оператором без правки кода: `MUSE_BRIDGE_APPROVAL_MODE` (`allowAll` по
  умолчанию, `denyUnmatched` для отката) в env launchd и перезапуск моста (пакет AD-007);
  значение по умолчанию и смысл решения владельца этим не меняются.
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
  при `MUSE_BRIDGE_APPROVAL_MODE=denyUnmatched` старт несёт `denyUnmatched` и одобрений нет.
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