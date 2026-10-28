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
# Чек-лист brief-review: arch R1, cycle 1, run analyst-teamlead-zen-realtime-reasoning-20261025, поколение g1
## BR — бизнес-требования
BR-01 [P] | «При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.» | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L7
BR-02 [P] | «Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).» | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L8
BR-03 [P] | «Проведена живая проверка тяжёлым путём на реальном мосту и DSH.» | источник: /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md#L9
BR-04 [P] | «"criticality": "S2"» и «"preset": "analyst-teamlead", "setup": "default"» | источник: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json#L4-L6
BR-05 [P] | «Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт»» (`RC-1`, `RC-2`, `RC-3`) | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L12-L19
BR-06 [P] | «Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).» | источник: analysis/zen-realtime-reasoning/research-plan.md#L16
BR-07 [P] | «REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага» и «AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L47
BR-08 [P] | «AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L47
BR-09 [P] | «REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883» и «AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L48
BR-10 [P] | «REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными» и «AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04)» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L49
BR-11 [P] | «REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима» и «AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L50
BR-12 [P] | «REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее» и «AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L51
BR-13 [P] | «AC-007: `_messages_to_prompt` не содержит статусных строк при реплее» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L51
BR-14 [P] | «REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку» и «AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L52
BR-15 [P] | «REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения» и «AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L53
BR-16 [P] | «AC-010: порог первого токена даёт `first_token_timeout`» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L53
BR-17 [P] | «REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с» и «AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L54
BR-18 [P] | «AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L54
BR-19 [P] | «REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка» и «AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L55
BR-20 [P] | «AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L55
BR-21 [P] | «REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты» и «AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L56
BR-22 [P] | «REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути» и «AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L57
BR-23 [P] | «REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native)» и «AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L58
BR-24 [P] | «REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта» и «AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`)» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L59
BR-25 [P] | «REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим» и «AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L60
BR-26 [P] | «REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование» и «AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey`» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L61
BR-27 [P] | «REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода» и «AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST`» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L62
BR-28 [P] | «REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс» и «AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L63
BR-29 [P] | «AC-023: результат не зависит от порядка тестов» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L63
BR-30 [P] | «REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается» и «AC-024: `test_google_direct.py` проходит без правок» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L64
BR-31 [P] | «REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой» и «AC-025: побайтовое совпадение после деплоя» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L65
BR-32 [P] | «REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет)» и «AC-026: тест красный на текущем коде и зелёный на новом (red to green)» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L66
BR-33 [P] | Рабочие целевые значения NFR и конверт `HL-ENV/v1` (`46 канонических полей REQUIRED_HL_ENV_FIELDS`, `operational_profile`, замыкание памяти `HL-ENV-01`, гейты `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`, оси `R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`) и риски `R1..R7` | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L97-L220
BR-34 [P] | Граница Non-Goal: «Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L223
BR-35 [P] | Граница Non-Goal: «Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L224
BR-36 [P] | Граница Non-Goal: «Не модифицировать текст размышления модели ради превью (OPEN-13).» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L225
BR-37 [P] | Граница Non-Goal: «Не менять модель, список моделей, логику выбора эффорта и каталог Zen.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L226
BR-38 [P] | Граница Non-Goal: «Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L227
BR-39 [P] | Граница Non-Goal: «Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L228
BR-40 [P] | Граница Forbidden Scope: «Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L232
BR-41 [P] | Граница Forbidden Scope: «Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L233
BR-42 [P] | Граница Forbidden Scope: «Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L234
BR-43 [P] | Граница Forbidden Scope: «Использование `security find-generic-password`.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L235
BR-44 [P] | Граница Forbidden Scope: «Правка `opencode.db` и общего каталога состояния `opencode` напрямую.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L236
BR-45 [P] | Граница Forbidden Scope: «Коммит в `main`, `master`, `dev`; merge выполняет человек.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L237
BR-46 [P] | База фактов `evidence-ledger.md` (`[F-01]..[F-16]` код моста, `[F-17]..[F-29]` эмпирика `opencode` v2.1.2 и `opencode serve`, `[F-30]..[F-34]` рантайм-инцидент, `[F-35]..[F-39]` потребитель DSH, `[F-40]..[F-41]` эталон `muse-bridge`, `[F-42]..[F-49]` базовая линия тестов и Таблица T1) приложена целиком без обрезки | источник: analysis/zen-realtime-reasoning/evidence-ledger.md#L11-L91
## SK — обязательные проверки
SK-A-01 [P] | Architecture Packet приложен целиком (не пересказ), без пометки об обрезке; совпадение SHA256 с receipt `ARCH_GATE` проверяет пре-линт SK-A-02 | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-03 [P] | `handoff-architect.md` и `evidence-ledger.md` приложены; указание судье проверить, что решения опираются на факты `[F-NN]` и каждый `[F-NN]` находится в ledger | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-04 [P] | `РЕЖИМ: architecture` + модификатор «Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки» | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-05 [P] | Указание: в пакете ≥2 альтернативы с причиной выбора; нет — FAIL по пункту об альтернативах | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-06 [P] | Указание проверить границы и слои, внешние контракты (HTTP/event/data/CLI/SDK), сценарии качества (NFR), модель угроз | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-07 [P] | FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-08 [P] | FAIL без оговорок: контракт вне envelope; выход за задачу | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-09 [P] | Оценка всех 6 критериев `universal-panel`; анти-галлюцинация и факт-карта (технологии/версии из пакета проверены) | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-10 [P] | Пункты `aisdlc-gcge/skills/architecture.md` (чек-лист/DoD) и правила проекта (`AGENTS.md`) видны судье | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-13 [P] | В брифе судьи есть блок «ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД» (`council.md` §1) со смысловыми указаниями: не обрывать поиск на первой ошибке, все замечания одним списком, один дефект в нескольких местах — один F-блок со всеми местами, self-sweep, последние строки `COVERAGE` / `FINDINGS_COMPLETE` | источник: brief-review/references/checklist-sources.md#SK-A
SK-A-14 [P] | В брифе судьи есть блок «ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)» с допустимыми якорями (а)–(г) (`arch-council.md` §2) | источник: brief-review/references/checklist-sources.md#SK-A
SK-T-01 [P] | «Universal Architecture Packet валиден в `approved` phase.» | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-02 [P] | «Все Python-утверждения подтверждены кодом/конфигом/официальной документацией.» | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-03 [P] | «Слои, async semantics и ownership отражают реальный проект.» (включая timeout для каждой I/O-операции и cleanup, cancellation, retry только для transient errors, concurrency limit/backpressure) | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-04 [P] | «Contract deltas содержат compatibility и verification IDs.» и «`contract_deltas[]` пуст либо в текущей задаче есть явное указание менять согласованный внешний контракт (`.agents/agents/scope-and-contracts.md`).» | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-05 [P] | «Stateful change имеет migration/rollout/rollback и integrity checks.» и «В `evolution` нельзя писать просто `NOT_APPLICABLE`: добавить проверяемую причину.» | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-06 [P] | «Verification surface содержит реальные project commands и targeted checks.» и чувствительность проверок (red без fix → green с fix, negative/boundary, concurrency/time/network) | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-07 [P] | «ADR path/format не конфликтует с `.agents/agents/docs.md`.» и «Architect не изменил product worktree.» | источник: aisdlc-gcge/skills/architecture.md#Definition-of-Done-overlay
SK-T-08 [P] | Обязательные Highload & Resilience гейты `architecture.md`: `HL-ENV-01` (46 атомарных полей `REQUIRED_HL_ENV_FIELDS` в СИ, замыкание памяти, двойное доказательство для `N/A`), `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1` | источник: aisdlc-gcge/skills/architecture.md#HL-RESILIENCE-GATES-V5
SK-P-01 [P] | «Diff не меняет согласованный внешний контракт, либо в текущей задаче есть явное указание это сделать и delta зафиксирована.» | источник: aisdlc-gcge/agents/scope-and-contracts.md#L79-L80
SK-P-02 [P] | «Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в отчёте отсутствуют, если их не спросили.» | источник: aisdlc-gcge/agents/scope-and-contracts.md#L81-L82
SK-P-03 [P] | Правила `aisdlc-gcge/AGENTS.md`: русский язык для описаний/docstrings/комментариев и английский для идентификаторов, минимально достаточные изменения без лишних зависимостей, регрессионные тесты и сдача через MR в целевую ветку без прямых коммитов в `main`/`master`/`dev` | источник: aisdlc-gcge/AGENTS.md#Главные-правила
## JD — пункты места
JD-02 [N] | Нет промпта другой шляпы и нет двух ролей в одном брифе | источник: brief-review/references/checklist-sources.md#JD
JD-03 [P] | «суди ЗАНОВО, не подтверждай прошлый вердикт автоматически» | источник: brief-review/references/checklist-sources.md#JD
JD-04 [P] | Ровно один блок «ФОРМАТ ОТВЕТА (строго)» на весь brief-v<K>.md (в hat-промпте или в judge-prompt); дубль = HY-02/B3 | источник: brief-review/references/checklist-sources.md#JD
JD-05 [P/N] | `seed_recheck_duty: да` → в брифе указание независимо пересчитать SEED и ranked_order по models.md п.1.1/1.2 с `seed_input` дословно; `нет` → такого указания нет | источник: brief-review/references/checklist-sources.md#JD
JD-06 [P/N] | R1: чужих вердиктов нет (N). R2-дебат: вердикт своей роли R1 и вердикты двух других — дословно, по шаблону `universal-panel` ШАГ 2 (P). Forced dissent — по его шаблону (P) | источник: brief-review/references/checklist-sources.md#JD
JD-07 [P] | Факт-карта и строка режима присутствуют; порядок блоков — по шаблону промпта universal-panel ШАГ 1 (arch); секция КОНТЕКСТ присутствует; блок формата в промпте шляпы (JD-01, JD-04) — требование «последний блок» не применяется | источник: brief-review/references/checklist-sources.md#JD
JD-08 [N] | Бриф самодостаточен: нет ссылок на «как обсуждали», «см. выше в чате», на файлы, которые судья не получит, как на единственный носитель содержания; в том числе на пути под каталогами с точкой на Google Drive (`.ai-team/…` в `~/Мой диск/…`) | источник: brief-review/references/checklist-sources.md#JD
## HY — гигиена
HY-02 [N] | Нет противоречий между разделами (режим, формат, правила FAIL, границы). Блок формата в hat-промпте без `INCONCLUSIVE` — не противоречие (JD-04: `prompt-<hat>.txt` не меняется) | источник: brief-review/references/checklist-sources.md#HY
HY-04 [N] | Нет секретов (токены, ключи, пароли) | источник: brief-review/references/checklist-sources.md#HY
HY-05 [N] | Нет следов brief-review: «исправлено по замечанию», ссылок на вердикт ревьювера | источник: brief-review/references/checklist-sources.md#HY
HY-06 [N] | Формулировки пунктов чек-листа не вставлены в бриф как самостоятельный текст без соответствующего первичного артефакта/шапки; такой пункт считается отсутствующим | источник: brief-review/references/checklist-sources.md#HY
## Исключено
SK-A-11 | основание: первый проход архитектурного совета (`cycle-1`, `a1`, возвратов `arch_panel_to_architect` не было; `state.json` `phase: "ARCH_PANEL"`, `last_transition: "ARCH_GATE_PASS"`) | источник: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json
SK-A-15 | основание: не D/C1-раунд (текущий раунд — `R1`, первичный независимый челлендж) | источник: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r1/manifest.json
SK-P-database | основание: в скоупе нет SQL/ORM/Alembic/миграций (`database.md` не срабатывает; `opencode.db` запрещено менять напрямую по Forbidden Scope) | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L236
SK-P-data-engineering | основание: в скоупе нет Airflow/Spark/ETL/DAG (`data-engineering.md` не срабатывает) | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L232
## Параметры места
panel: arch | round: R1 | round_type: R1 | hat: visionary
hat_prompt: ~/work/universal-panel/prompt-visionary.txt
seat_slot: claude-sonnet-5-5-high
seat_kind: panel-judge
seed_recheck_duty: нет | ranked_position: 2 из 3
architect_slot: gpt-6.1-sol-high

## ИСТОЧНИКИ ENVELOPE
### /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md
# Цель: Реалтайм-стриминг размышлений (reasoning) и шагов DeepSeek через мост opencode-zen-bridge в DSH

- Открыто: 2026-10-25 22:24:20 MSK
- Репозиторий (изолированный клон): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning` от `origin/dev`)
- Контур: `cel` + `analyst-teamlead` (`system-analyst` → `architect-software-product` → `Arch Panel` 3 судей → `Coder` → `Clean-Room L2` → `Code Council` 3 судей → открытый PR в `dev` + живая проверка тяжёлым путём).
- Бизнес-результат и критерий приёмки:
  1. При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.
  2. Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).
  3. Проведена живая проверка тяжёлым путём на реальном мосту и DSH.

### .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
    "verification_surface_sha256": "b13549592f01850ff16a8d56cbe3cd77383fde35bcc91a5cff503b9e209e2ae4",
    "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b"
  }
}

### analysis/zen-realtime-reasoning/handoff-architect.md
# Handoff to Architect: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — в `evidence-ledger.md` (`F-01..F-49`), вопросы — в `open-questions.md` (`OPEN-01..OPEN-17`, блокеров нет), план — в `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: видеть размышление DeepSeek в DSH в реальном времени при работе через `opencode-zen-bridge` (`127.0.0.1:9883`) и получить высокую
отзывчивость. Инцидент-образец — `session-423ca27f`, ход 2 шаг 5 (22:16:12 MSK): на экране только «Deep diving for 35s ···», затем более 780 с без единого токена (F-30, F-33).

Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | `opencode run --format json --thinking` v2.1.2 подписан только на `session.reasoning.ended` и `session.text.ended` и игнорирует `*.delta`: размышление и текст приходят одним блоком в самом конце шага (разница 0.00-0.17 мс), тишина stdout 1.9-2.7 с даже на здоровом вызове. Мост не может показать то, чего CLI не выдаёт | F-17, F-18, F-02, F-05 |
| RC-2 | Нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками; единственный потолок — `TIMEOUT_S=1800` с; холодный `--standalone` на БД 2.27 GB, пул ProxyRack и сериализующий `_StartupGate` дали зависания 780-856 с, а keepalive `{"content":""}` держал сокет DSH пустым | F-09, F-10, F-28, F-30, F-31, F-32, F-04 |
| RC-3 | В DSH строка `⚛ Think` не рисуется, пока нет непустого `reasoning_content`; пустые keepalive ничего не показывают; inline-превью свёрнутой строки обновляется только по завершённому абзацу (нужен `\n`) | F-36, F-37, F-04 |

Цепочка следствий: RC-1 лишает реалтайма здоровый вызов, RC-2 превращает больной вызов в многоминутную тишину, RC-3 делает любую тишину
для пользователя неотличимой от зависания (экран с таймером без содержимого). Реалтайм-транспорт без пунктов RC-2 и RC-3 проблему не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (pi-ai openai-completions, stream:true)  --HTTP SSE-->  Handler._stream_sse (:9883)        F-35, F-03
  Handler._stream_sse: 200+role-chunk -> _StartupGate -> spawn `opencode run ... --format json`  F-03, F-10, F-01
  opencode run (stdout JSON lines) -> _StdoutFeed(queue 4096) -> parse_opencode_event            F-14, F-02
     reasoning -> delta.reasoning_content (flush сразу)                                         F-05
     text      -> ToolCallParser.feed -> delta.content / delta.tool_calls                       F-05, F-06
     keepalive -> {"content": ""} раз в 15 с тишины                                              F-04
  opencode run --standalone -> opencode serve --stdio (дочерний) -> georouter :10830 -> Zen      F-30, F-26, F-27
  Пул ProxyRack: следующий порт на каждый spawn (env HTTP(S)_PROXY, loopback мимо)              F-15
DSH UI: непустой reasoning_content -> blockIsVisible -> ReasoningRow (превью по "\n")            F-36, F-37
DSH реплей: thinking -> assistant.reasoning_content -> мост игнорирует                          F-38, F-07
```

Граница совместимости (факт): всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)` (F-02, F-05); поэтому любой транспорт,
сводимый к тем же кортежам, не требует правки верхнего слоя (ретраи, парсер инструментов, usage, SSE-кадрирование).

## 3. Требования `REQ-001..REQ-020`

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие проверяемые формулировки (полная спецификация живёт в requirements и в `handoff-qa.md`).

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага | F-17, F-18, F-19 | AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс |
| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883 | F-35, F-34 | AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата |
| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными | F-43, F-40, F-42 | AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04) |
| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима | F-36, F-37, F-04, F-33 | AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме |
| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее | F-37, F-38, F-07, F-39 | AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее |
| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку | F-09, F-30, F-31 | AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с |
| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения | F-09, F-19, F-32 | AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout` |
| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с | F-14, F-30, F-33 | AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится |
| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка | F-11, F-12 | AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка |
| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты | F-06, F-05 | AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом |
| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути | F-05, F-11, F-43 | AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт |
| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native) | F-08, F-22, OPEN-07 | AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь |
| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта | F-10, F-11, F-15, F-32 | AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`) |
| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим | F-19, F-02 | AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры |
| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование | F-21, F-27 | AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey` |
| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода | F-32, F-30 | AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` |
| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс | F-45, F-46, F-47, F-48, F-49 | AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов |
| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок |
| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя |
| REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green) |

## 4. Варианты реализации RC-1 (сравнение по фактам, без выбора)

Вердикты: `выполнимо` / `выполнимо с условиями` / `невыполнимо`. Исходные данные по каждому — в ledger.

| Вариант | Суть | Задержка и реалтайм | Авторизация, маршрут, ротация IP | Изоляция встроенных инструментов | Параллелизм и SQLite | Тестируемость | Вердикт |
|---|---|---|---|---|---|---|---|
| L: только упрочнение legacy | `opencode run` остаётся, добавляются watchdog (REQ-006..008), статусные строки (REQ-004, REQ-005) | Реалтайма размышления нет: единый блок в конце шага (F-17, F-18); живость только за счёт статусных строк моста | Без изменений (F-15) | Без изменений (F-08) | Холодный spawn на каждый шаг сохраняется (F-28, F-30) | Полная: fake-CLI (F-43) | выполнимо; закрывает RC-2 и RC-3, но не RC-1 |
| A1: `opencode serve` короткоживущий на запрос, SSE `GET /api/event` | Мост поднимает `serve` на свободном порту с одноразовым паролем, создаёт сессию, шлёт prompt, читает дельты, затем `interrupt`/`DELETE` и `killpg` | Дельты размышления каждые 105-304 мс (median 127), первая дельта 1811 мс, text-дельты median 114 мс (F-19); старт сервера 109 мс (F-20) | Пароль случайный на процесс (F-21); env прокси задаётся на запуск, значит ротация сохраняется (F-15, OPEN-06); egress идёт через georouter (F-26, F-27) | Поле `permissions` в `POST /api/session` и `permission {"*":"deny"}` в конфиге (F-22), поведение не прогнано (OPEN-07) | Один процесс на запрос, idle RSS 152 MiB (F-20); БД та же 2.27 GB, нагрузка не мерилась (OPEN-08) | Нужен фейковый serve-сервер и адаптер событий; fake-CLI покрывает только legacy-путь (F-43) | выполнимо с условиями (OPEN-06, OPEN-07, OPEN-08) |
| A2: общий управляемый `opencode serve` (демон) | Один долгоживущий процесс; сессия на запрос | Те же дельты (F-19); нет холодного старта (фоновый `serve --service` уже работает, F-20) | Один набор env прокси на все запросы: общий IP упирается в дневной лимит (F-23, F-32); пароль на демон | Как в A1 | Общая БД и общий процесс, RSS 439 MiB у существующего демона (F-20); падение демона роняет все запросы | Тот же фейковый сервер; нужен супервизор и перезапуск | выполнимо с условиями; ротация IP не сохраняется без доработки (OPEN-06) |
| B: прямой OpenAI-совместимый HTTP-SSE к Zen | По образцу Google Direct (F-16): `http.client`, `readline`, дельты `reasoning_content` в реальном времени | Минимальная: без CLI, без БД, дельты как у апстрима (георутер отдаёт реалтайм, F-19) | Анонимный вызов без заголовков дал 429 `FreeUsageLimitError` напрямую и через пул (F-24, F-25); нужные заголовки или ключ неизвестны (OPEN-05); у `opencode` провайдера нет `apiKey` (F-27) | Не требуется: инструментов нет, эмуляция через `<tool_invoke>` остаётся | Нет SQLite и дочерних процессов | Лучшая: подмена HTTP-сервера, без `FAKE_OPENCODE` | выполнимо с условиями; осуществимость не доказана (OPEN-05) |
| C: гибрид | Приоритетный быстрый транспорт (A1 или B), при `ServeUnavailable`-подобном отказе тихий откат на legacy `opencode run`, как в muse-bridge | Реалтайм там, где транспорт доступен; legacy при отказе | Совмещает ограничения выбранных транспортов | Совмещает | Совмещает | Прецедент в репозитории: serve основной, exec запасной (F-40, F-41); fake-CLI тесты остаются на legacy-пути | выполнимо; объём работ максимальный |

Наблюдения для решения (факты, не выбор):
- Только A1/A2/B дают реалтайм на здоровом вызове; L не даёт, но самый дешёвый и закрывает RC-2/RC-3 (поэтапная поставка возможна: L затем A1/B/C).
- Квота Zen исчерпана на момент анализа (F-23): живая приёмка и PoC варианта B возможны после сброса около 03:00 MSK 2026-10-26.
- Совместимость с тестами: muse-bridge сохраняет exec-путь как резерв (F-40); у `opencode-zen-bridge` три модуля подменяют `OPENCODE_BIN` скриптом с событиями формата `run --format json` (F-43).
- Размер объёма ретраев и `_StdoutFeed` уже рассчитан на потоковые события (F-14); `step_finish` в `run` теряется (F-18), в serve есть `session.step.ended` с `tokens` (F-19).

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Аутентификация | Лимиты и режимы отказа | Тестовый контур |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` моста | HTTP SSE OpenAI (`stream:true`, `include_usage`) | Ingress от DSH | Bearer-ключ моста (значение не фиксируется) | слоты 6, ожидание 15 с, 12 ждущих, 503 при переполнении (F-13) | `tests/_http.py`, `test_step_interruption.py` (F-43) |
| `opencode run --format json` | stdout JSON-строки | Egress процесса | Нет (локальный CLI, белый список env) | потолок 1800 с, нет watchdog (F-09) | `FAKE_OPENCODE` (F-43) |
| `opencode serve` v2 | HTTP + SSE, Basic `opencode:<пароль>` | Egress | случайный пароль на процесс или `OPENCODE_SERVER_PASSWORD` (F-21) | старт 109 мс, API по OpenAPI (F-20, F-22) | тестового фейка нет |
| `model_georouter` :10830 | OpenAI-совместимый HTTP | Egress | нет у провайдера `opencode` (F-27) | `headers_timeout` 120 с, `inactivity_timeout` 300 с, 80+80 слотов, 3 pre-send повтора (F-26) | нет |
| Zen upstream `opencode.ai/inference/openai/v1` | OpenAI SSE | Egress | анонимный, дневной лимит (F-23..F-25) | `FreeUsageLimitError` 429 с `Retry-After` | нет |
| DSH `openai-completions` | SSE потребитель | Ingress | — | `streamIdleTimeoutMs` 1900000, `maxRetries` 0 (F-35) | живой DSH |

## 6. NFR-набросок (наблюдаемые величины)

- Нагрузка: 517 завершённых запросов за день, `deepseek-v4.1-flash-free` 44 (median 7.10 с, max 85.65 с) (F-32); пик параллелизма 6 (F-13).
- Задержка legacy: `step_start` 1.3-2.5 с, весь ответ 3.3-5.2 с одним блоком (F-17); реалтайм-путь serve: первая дельта размышления 1.8 с (F-19).
- Хвост: два запроса молчали 780-856 с с `out_chars=0` (F-30, F-31); `startup_gate_timeout` 72 за день (F-32).
- Ресурсы: мост RSS 22 MiB, 36 дескрипторов (F-29); idle serve 152 MiB, 20 дескрипторов (F-20); БД 2.27 GB (F-28).
- Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.

## 7. Конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS`)

Единицы СИ. Источники в комментариях; значения, не измеренные под нагрузкой, помечены `оценка`.

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1                      # один локальный демон LaunchAgent, F-34
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1                             # один Python-процесс ThreadingHTTPServer, F-12
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0           # бюджет рабочей станции, оценка
  kappa_skew: 1.0
  u_bg_worker: 0.02                # оценка
  U_pod_sidecars: 0.25             # дочерние процессы opencode, оценка
  Mem_limit_per_pod: 2147483648    # бюджет демона 2048 MiB, оценка
  Mem_rss_worker_max: 67108864     # 64 MiB; измерено 22 MiB, F-29
  Mem_shared_max: 1207959552       # 6 дочерних процессов по 192 MiB; idle serve 152 MiB, F-20
  RPS_peak: 0.2                    # 517 запросов за день, F-32
  A_max: 3                         # MAX_TOTAL_SPAWNS, F-11
  SLA_p99_s: 180.0                 # max наблюдаемый 85.65 с, F-32
  N_entities_max: 64
  Limit_dep_share_d: {georouter: 80, opencode_local_db: 10}   # georouter F-26; значение БД допущение эталона, OPEN-08
  Limit_dep_rps_d: {opencode_spawn: 1.0}                      # SPAWN_RATE_PER_S, F-11
  W_fetchers_d: 1
  J_init_s_d: 12.0                 # STARTUP_GATE_S, F-10
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0                 # KEEPALIVE_INTERVAL_S, F-04
  K_calls_d: 1
  T_base_s_d: 0.5                  # RETRY_BACKOFF_BASE_S, F-11
  T_cap_s_d: 2.0                   # RETRY_BACKOFF_CAP_S, F-11
  Max_stale_age_s_c: 0.0           # кэшей нет
  Min_healthy_ratio: 1.0
  B_retry_max: 6                   # RETRY_BUDGET_MAX, F-11
  min_reserve_retry_rps: 0.05      # RETRY_BUDGET_RESERVE_RPS, F-11
  FD_worker: 128                   # измерено 36 при active=0, F-29; запас под 6 потоков
  ulimit_n: 65536                  # launchctl limit maxfiles, F-29
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16384         # эфемерный диапазон 49152-65535
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12           # до 6 обработчиков и до 6 читателей stdout/SSE
  stdout_queue_max: 4096           # F-14
  ttft_visible_target_s: 1.0       # допущение, OPEN-11
  ttft_first_delta_target_s: 3.0   # допущение, OPEN-11; наблюдение serve 1.8 с, F-19
  first_event_watchdog_s: 20.0     # допущение, OPEN-11
  first_token_watchdog_s: 60.0     # допущение, OPEN-11
  stall_watchdog_s: 60.0           # допущение, OPEN-11
  client_gone_detect_s: 5.0        # допущение; сейчас 24.4 с, F-33
  keepalive_interval_s: 15.0       # F-04
  total_deadline_s: 1800           # TIMEOUT_S, F-09
  max_total_spawns: 3              # F-11
  startup_gate_s: 12               # F-10
  startup_wait_s: 5.0              # F-10
  bulkhead_max_concurrent: 6       # F-13
  slot_wait_s: 15.0                # F-13
  slot_max_waiters: 12             # F-13
  graceful_stop_s: 5               # SIGTERM затем SIGKILL, F-14
  serve_ready_s: 0.109             # F-20
```

Замыкание памяти (`HL-ENV-01`): `W × Mem_rss_worker_max + Mem_shared_max = 64 MiB + 1152 MiB = 1216 MiB ≤ 0.80 × 2048 MiB = 1638.4 MiB` (PASS, оценка). Для варианта A2 (общий демон, 439 MiB, F-20) вклад меньше.

## 8. Гейты Highload & Resilience (7 канонических + оси брифа)

### 8.1. Канонические гейты `architecture.md` (`#hl-env-and-four-gates-ssot`)

- `C-MULT/v1`:
  - `C-MULT-I1`: `1 × 1 × 6 = 6 ≤ 0.60 × 80 = 48` для георутера (F-26) — PASS; для локальной БД предел неизвестен (OPEN-08), поэтому ограничителем остаются `_StartupGate`, `SPAWN_RATE_PER_S` и семафор слотов (F-10, F-11, F-13).
  - `C-MULT-I2`: очереди ограничены (`_StdoutFeed` 4096, слоты 6, ждущих 12, ожидание 15 с) (F-13, F-14) — PASS; новый SSE-читатель обязан иметь такой же предел.
  - `C-MULT-I3`: семафоры и замки — синглтоны процесса (`W=1`) (F-12) — PASS.
  - `C-MULT-I4`: освобождение слота и остановка процесса в `finally` (F-14) — PASS как as-is; новые ресурсы (сессия serve, SSE-сокет) должны освобождаться там же.
  - `C-MULT-I5`: `FD_worker = 128 ≤ 0.70 × 65536`; порты `0.6 × 1 × 60 + 12 = 48 ≤ 0.50 × 16384 = 8192` — PASS (оценка).
- `S-HERD/v1`:
  - `S-HERD-I1`: серия холодных стартов сериализуется `_StartupGate` (F-10); у A1 старт сервера 109 мс (F-20).
  - `S-HERD-I2`: Full Jitter 0.5/2.0 уже в коде (F-11); повторы по watchdog обязаны использовать его.
  - `S-HERD-I3..I5`: N/A, поллеров Control Plane, `If-None-Match` и `singleflight` в мосте нет (граф вызовов as-is: `do_POST` → `_stream_sse`/`_serve_json` → запуск процесса); доказательство `git diff` предоставляет Architect после дизайна.
- `H-CPU/v1`:
  - `H-CPU-I2`: регулярные выражения компилируются при импорте (F-06, F-11); разбор SSE-дельт не должен вызывать `re.compile` в цикле.
  - `H-CPU-I3`: путь с выключенной новой функцией должен возвращаться за `O(1)` (kill-switch, REQ-003).
  - `H-CPU-I5`: оценка `0.02 + 0.2 × (0.02 + 3 × 0.05) = 0.054 ≤ 0.70` (PASS, не измерено); поток serve даёт около 10 событий в секунду на запрос (F-19), то есть до 60 разборов JSON в секунду на 6 запросах.
  - `H-CPU-I1`, `H-CPU-I4`: N/A (индексов маршрутизации и event loop нет).
- `R-BULK/v1`:
  - `R-BULK-I1`: вспомогательные ожидания `3 × 5.0 с (gate) + 0 + 1.0 + 2.0 = 18.0 с ≤ 0.30 × 180 = 54 с` (PASS); наихудший случай с watchdog первого события `3 × (20 + 5) + 3 = 78 с ≤ 180 с`.
  - `R-BULK-I2`: потолок запусков 3, бюджет повторов 6, слоты 6 (F-11, F-13) — PASS.
  - `R-BULK-I3`: классификация транзиентных и детерминированных ошибок существует (F-11, `_is_transient_stream_error`); новые причины watchdog относятся к транзиентным.
  - `R-BULK-I4`, `R-BULK-I5`: N/A (пула прокси-нод с health-ранжированием и мульти-тенантных пулов в мосте нет; прокси из пула — подстановка в env, F-15).
- `T-LIFE/v1`: каждый процесс и его читатель закрываются `_stop_proc` в `finally` (F-14); для A1/A2 добавляются `interrupt`, `DELETE` сессии и `killpg` (F-22).
- `O-EXIT/v1`: строка выхода на каждом `do_POST` уже есть (F-32); расширение полями — REQ-016.
- `M-SEM/v1`: N/A на этапе анализа (единый пул слотов `_slots`, F-12); подтверждение `git diff` и графа вызовов — за Architect.

### 8.2. Оси из брифа (`R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`)

В каноне этих меток нет (OPEN-15). Трактовка аналитика (допущение) и статус по фактам:

| Ось | Трактовка | Статус по фактам |
|---|---|---|
| `R-OUT` | исходы запроса и повторы (`exit_reason`, потолок A_max) | потолок есть (F-11); новые причины watchdog требуют кодов (REQ-016) |
| `M-CONF` | конфигурация и kill-switch новой функции | переменные окружения как у `STEP_RECOVERY` (F-11), REQ-003 |
| `F-DEG` | деградация: отказ быстрого транспорта не должен ломать ответ | прецедент serve→exec в muse-bridge (F-40); fail-open для статусных строк, fail-closed для политики инструментов (REQ-012) |
| `S-SEC` | секреты, пароль serve, изоляция инструментов | пароль случайный на процесс (F-21), `apiKey` не выгружался (F-27), REQ-015 |
| `X-BOUND` | границы процессов и ресурсов (killpg, FD, сессии) | F-14, F-29, REQ-008 |

## 9. Non-Goals

- Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).
- Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.
- Не модифицировать текст размышления модели ради превью (OPEN-13).
- Не менять модель, список моделей, логику выбора эффорта и каталог Zen.
- Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.
- Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.

## 10. Forbidden Scope

- Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.
- Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.
- Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.
- Использование `security find-generic-password`.
- Правка `opencode.db` и общего каталога состояния `opencode` напрямую.
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-49` (ledger).
- `blocking open questions`: пусто.
- `assumptions`: `OPEN-04..OPEN-17` с рабочими допущениями из `open-questions.md`.
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): первая видимая строка до 1.0 с; первая дельта размышления до 3.0 с; пауза до 15 с; молчание до 20 с (допущения OPEN-11), текущие значения в разделе 6.
- `risks`: R1 — прямой Zen без заголовков не осуществим (OPEN-05); R2 — потеря ротации IP при общем демоне (OPEN-06); R3 — встроенные инструменты `opencode` исполнятся при неверной политике (OPEN-07); R4 — контенция SQLite при параллельных serve (OPEN-08); R5 — квота Zen блокирует живую приёмку до около 03:00 MSK 2026-10-26 (F-23); R6 — дубли размышления при повторах (OPEN-14); R7 — красная базовая линия блокирует Full Suite Gate (OPEN-04).

## 12. Обратный канал в требования

Противоречий фактов с REQ-ID нет. Расхождение с брифом: в `tests/` 17 модулей `test_*.py`, а не 16 (F-42); ссылка на «16 модулей» в постановке неточна, на объём работ не влияет.

### analysis/zen-realtime-reasoning/evidence-ledger.md
# Evidence Ledger: zen-realtime-reasoning (opencode-zen-bridge, реалтайм-размышление)

Дата сбора: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Роль: System Analyst (Stage 1).
Формат факта: `[F-NN] (FACT-0NN) утверждение | источник | YYYY-MM-DD`. Секреты не выносятся
(пароль `opencode serve`, `apiKey`, креды ProxyRack, логины пула не воспроизводились и не сохранялись).
Пути с `~/` — домашний каталог. Пути без `~/` — относительно корня репозитория
`bridges/opencode-zen-bridge/`, если не указано иное.
Эмпирические PoC-скрипты и логи аналитика: `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`
(вне репозитория; код продукта не менялся).

## 1. Код моста (повторная сверка по исходнику)

[F-01] (FACT-001) Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`) | server.py:1146-1161, 966-969, 1617-1649 | 2026-10-25
[F-02] (FACT-002) `parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают | server.py:2417-2462 | 2026-10-25
[F-03] (FACT-003) `Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{"role":"assistant","content":""}` до `_StartupGate`, spawn и чтения stdout | server.py:3312-3327, 3399-3412 | 2026-10-25
[F-04] (FACT-004) Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{"content":""}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content` | server.py:49, 3437-3450, 865-952 | 2026-10-25
[F-05] (FACT-005) События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content` | server.py:3462-3493 | 2026-10-25
[F-06] (FACT-006) `ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len("<tool_invoke>")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям | server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323) | 2026-10-25
[F-07] (FACT-007) `_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает | server.py:1848-1888 | 2026-10-25
[F-08] (FACT-008) Конфиг `opencode` для дочернего процесса по умолчанию: `permission {"*":"ask"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1` | server.py:228-231 | 2026-10-25
[F-09] (FACT-009) В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с) | server.py:46, 3450, команда grep от 2026-10-25 | 2026-10-25
[F-10] (FACT-010) `_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start` | server.py:1197-1236, 3399-3411, 3451 | 2026-10-25
[F-11] (FACT-011) Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду | server.py:277, 287-298, 309-314, 1340-1368, 1471-1535 | 2026-10-25
[F-12] (FACT-012) Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор | server.py:1458-1470, 3989-3996 | 2026-10-25
[F-13] (FACT-013) `MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12` | server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK | 2026-10-25
[F-14] (FACT-014) `_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25` | server.py:848-862, 865-952 | 2026-10-25
[F-15] (FACT-015) Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст | server.py:1047-1082, 1093-1131; start.sh:24-31 | 2026-10-25
[F-16] (FACT-016) `_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({"reasoning_content": text})` в реальном времени; прецедент прямого маршрута для Option B | server.py:3127-3266 (reasoning emit около 3219) | 2026-10-25

## 2. Эмпирика `opencode` v2.1.2 (Zone B и PoC аналитика)

[F-17] (FACT-017) `opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1) | explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK) | 2026-10-25
[F-18] (FACT-018) Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended` | explorer-zone-b.md §2 | 2026-10-25
[F-19] (FACT-019) `opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1) | explorer-zone-b.md §1, §3 | 2026-10-25
[F-20] (FACT-020) Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB | sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK | 2026-10-25
[F-21] (FACT-021) Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode` | sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25 | 2026-10-25
[F-22] (FACT-022) OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate` | sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B) | 2026-10-25
[F-23] (FACT-023) PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {"*":"deny"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса | sa-poc/poc_serve.log | 2026-10-25
[F-24] (FACT-024) Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс | sa-poc/poc_georouter.log | 2026-10-25
[F-25] (FACT-025) Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена | sa-poc/poc_direct_zen_proxy.log | 2026-10-25
[F-26] (FACT-026) `model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz` | ~/.config/model-georouter/config.json (значения без секретов) | 2026-10-25
[F-27] (FACT-027) В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось) | ~/.config/opencode/opencode.json (обход ключей с маскированием) | 2026-10-25
[F-28] (FACT-028) `~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет | ls -l, opencode run --help от 2026-10-25 | 2026-10-25
[F-29] (FACT-029) Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard) | ps, lsof, launchctl limit от 2026-10-25 22:4x MSK | 2026-10-25

## 3. Рантайм и инцидент (Zone D)

[F-30] (FACT-030) Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет | explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK | 2026-10-25
[F-31] (FACT-031) Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода | explorer-zone-d.md §2 | 2026-10-25
[F-32] (FACT-032) Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10 | explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log | 2026-10-25
[F-33] (FACT-033) Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`) | explorer-zone-d.md §3 | 2026-10-25
[F-34] (FACT-034) Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK | explorer-zone-d.md §1; /health от 2026-10-25 | 2026-10-25

## 4. Потребитель: DSH Desktop

[F-35] (FACT-035) Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage` | ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C) | 2026-10-25
[F-36] (FACT-036) Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка) | 2026-10-25
[F-37] (FACT-037) UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===""` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\n` | client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка) | 2026-10-25
[F-38] (FACT-038) При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07) | app.asar openai-completions.js, смещения 116117903-116120153 | 2026-10-25
[F-39] (FACT-039) Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков | ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста | 2026-10-25

## 5. Эталон muse-bridge (ADR-0004)

[F-40] (FACT-040) `muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса | bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185 | 2026-10-25
[F-41] (FACT-041) `muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`) | bridges/muse-bridge/server.py:165, 4150-4156 | 2026-10-25

## 6. Тесты и базовая линия

[F-42] (FACT-042) В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`) | ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log | 2026-10-25
[F-43] (FACT-043) Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env` | tests/*.py (grep OPENCODE_BIN и _fake_cli) | 2026-10-25
[F-44] (FACT-044) Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`) | tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py | 2026-10-25
[F-45] (FACT-045) Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются | baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log | 2026-10-25
[F-46] (FACT-046) Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях | sa_iso_file.log | 2026-10-25
[F-47] (FACT-047) Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный | sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287 | 2026-10-25
[F-48] (FACT-048) Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду) | baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368 | 2026-10-25
[F-49] (FACT-049) `grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`) | git log -S от 2026-10-25 | 2026-10-25

## Таблица T1. Тайминги `opencode` (Zone B, модель `opencode/deepseek-v4.1-flash-free`, variant `high`, `elapsed_ms`)

| Режим | 1-е событие | 1-й reasoning | reasoning-событий | интервал дельт | 1-й text | событий всего | завершение |
|---|---:|---:|---:|---|---:|---:|---:|
| `run --format json` PIPE, фоновый сервис | 2378.85 | 4850.67 (1 блок, 768 симв.) | 1 | нет | 4850.80 | 3 | 4919.34 |
| `run --format json` PTY, фоновый сервис | 1315.53 | 3219.27 (1 блок, 285 симв.) | 1 | нет | 3219.44 | 3 | 3281.97 |
| `run --format json --standalone` PIPE | 2501.60 | 5137.26 (1 блок, 549 симв.) | 1 | нет | 5137.26 | 3 | 5213.40 |
| `run --format json --standalone` PTY | 2226.36 | 4941.59 (1 блок, 412 симв.) | 1 | нет | 4941.71 | 3 | 5023.95 |
| `opencode serve` v2, `GET /api/event` | 161.22 (`integration.updated`), 233.06 (`execution.started`) | 1810.98 (1-я дельта) | 10 дельт + started + ended | min 105.64, median 127.25, max 304.32 | 3260.64 (17 дельт, median 114.49) | 53 | 5558.06 |

## Сводка покрытия (для DoD)

Всего фактов: 49. Источники воспроизводимы командами и путями из колонки «источник». Факты F-23, F-24, F-25 фиксируют
состояние внешней квоты на 2026-10-25 22:4x MSK и могут измениться после сброса лимита.

### analysis/zen-realtime-reasoning/research-plan.md
# Research Plan: zen-realtime-reasoning (реалтайм-размышление `opencode-zen-bridge` в DSH)

Роль: System Analyst (Stage 1, preset `analyst-teamlead`), тип — feasibility study + as-is обследование, глубина — standard (S2).
Дата: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Артефакты: `analysis/zen-realtime-reasoning/`.
Владелец вывода: владелец продукта (расхождения «ожидали X, оказалось Y» принимает он; финальная архитектура — `architect-software-product`).

## 1. Scope

Запрос владельца: при запуске DeepSeek через `opencode-zen-bridge` (`127.0.0.1:9883`) в DSH видеть размышление в реальном
времени и получать отличную отзывчивость, чтобы было видно, что процесс идёт. Инцидент-образец: сессия `session-423ca27f`,
ход 2 шаг 5 (22:16:12 MSK), экран «Deep diving for 35s ···» без строки `⚛ Think`, затем молчание более 780 с.

В периметре исследования: код `bridges/opencode-zen-bridge/` (`server.py`, `start.sh`, `tests/`), эталон `bridges/muse-bridge/server.py`,
живой `opencode` v2.1.2 (CLI и `opencode serve`), локальный `model_georouter` (:10830), потребитель DSH Desktop (`app.asar`),
рантайм-логи моста за 2026-10-25.
Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).

## 2. Проверяемые гипотезы (исход — в `evidence-ledger.md`)

| Гипотеза | Итог | Основание |
|---|---|---|
| RC-1: `opencode run --format json` буферизует размышление и текст до конца шага, поэтому реалтайма нет даже на здоровом вызове | подтверждена | F-17, F-18 |
| RC-1a: реалтайм-путь на этом хосте существует (`opencode serve` v2 SSE, дельты каждые ~110-130 мс) | подтверждена (замер Zone B), повтор заблокирован квотой | F-19, F-23 |
| RC-1b: прямой анонимный HTTP-SSE к Zen как у Google Direct осуществим без `opencode` | не подтверждена: два PoC дали 429 | F-24, F-25 |
| RC-2: холодный spawn + отсутствие watchdog приводят к немым зависаниям на 13-14 минут | подтверждена по коду и логам | F-09, F-10, F-30, F-31 |
| RC-3: пустые keepalive не показывают ничего, а превью `⚛ Think` требует `\n` | подтверждена | F-36, F-37 |
| Три красных теста базовой линии — загрязнение теста либо реальное взаимодействие бюджетов повтора | обе причины присутствуют | F-47, F-48, F-49 |

## 3. Зоны обследования (веер Wave 1, без пересечений)

- Зона A (код моста и эталон): `server.py`, `muse-bridge` ADR-0004 — отчёт `explorer-zone-a.md`.
- Зона B (контракты и эмпирика `opencode`): CLI vs `opencode serve` vs wire Zen — отчёт `explorer-zone-b.md`.
- Зона C (потребитель): DSH `openai-completions`, `ReasoningRow`, `blockIsVisible` — отчёт `explorer-zone-c.md`.
- Зона D (рантайм): логи, зависшие PID, реконструкция скриншота — отчёт `explorer-zone-d.md`.
- Сверка аналитика (read-only, PoC в `/tmp`): повторная проверка кода по строкам, изоляция красных тестов, прямой HTTP-SSE PoC,
  OpenAPI `opencode serve`, структура журнала сессии DSH, ресурсы процессов.

## 4. Методология

1. Факт или открытый вопрос: каждое утверждение — строка `[F-NN]` с источником и датой, иначе запись в `open-questions.md`.
2. Эмпирика важнее чтения: тайминги `elapsed_ms` снимались по живым процессам, а не выводились из кода.
3. Секреты не выносятся: пароль `opencode serve`, `apiKey`, креды пула ProxyRack не печатались и не сохранялись; PoC использовали временный пароль и порт.
4. Код продукта не менялся; PoC-скрипты и логи лежат в `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`.
5. Выбор архитектуры не делается: варианты сравниваются по фактам в `handoff-architect.md`, вердикт — «выполнимо / с условиями / невыполнимо».
6. Квота Zen (`FreeUsageLimitError`) исчерпана на 22:4x MSK, поэтому часть замеров переведена в отложенные вопросы с условием повтора после сброса.

## 5. Реестр спайков

Формат строки: `ID | вопрос | источник | метод | таймбокс | deliverable | критерий закрытия | зависит/блокирует | статус | результат | факт | отметка`
(таймбокс и факт — минуты).

INV-01 | Где мост теряет реалтайм (маппинг событий и SSE-кадрирование) | server.py:2417-2462 и 3312-3493 | чтение кода и сверка с Zone A | 25 | таблица потока событий в ledger | найден участок и порядок отправки чанков | блокирует INV-02 | closed | F-05 | 18 | ok
INV-02 | Выдаёт ли `opencode run --format json` дельты размышления и текста | ~/.opencode/bin/opencode и живые запуски | замеры PIPE/PTY × standalone/сервис | 40 | таблица T1 | показано, что дельт нет и почему | зависит от INV-01 | closed | F-18 | 35 | ok
INV-03 | Реалтайм-путь `opencode serve` v2: события, тайминги, схема API | `GET /api/event`, OpenAPI v2.1.2 | живой SSE-замер и разбор OpenAPI | 40 | схема эндпоинтов и тайминги | задокументированы события и интервалы дельт | зависит от INV-02 | closed | F-19 | 38 | ok
INV-04 | Осуществим ли прямой анонимный HTTP-SSE к Zen (Option B) | server.py:3127-3266 и opencode.ai/inference | PoC через georouter и через CONNECT-туннель пула | 30 | вердикт осуществимости | получены токены либо зафиксирован отказ с причиной | блокирует выбор Option B | open | OPEN-05 | 22 | отказ 429 в обоих PoC, нужен повтор после сброса лимита
INV-05 | Чем ограничено ожидание первого токена (RC-2) | server.py:46, 1197-1236, 3450 и логи Zone D | grep по сторожам и разбор логов | 30 | перечень таймеров и бюджетов | подтверждено отсутствие TTFT и stall watchdog | зависит от INV-01 | closed | F-09 | 20 | ok
INV-06 | Контракт видимости размышления в DSH (RC-3) | app.asar, client.js, openai-completions.js | чтение бандла и подтверждение символов поиском | 30 | контракт `blockIsVisible` и `\n` | найдены условия появления строки Think | независим | closed | F-37 | 24 | ok
INV-07 | Возвращает ли DSH размышление мосту и что с ним делает мост | app.asar и server.py:1848-1888 | поиск `reasoning_content` в бандле и в `_render_turn` | 20 | вывод о безопасности статусных строк | найден путь реплея и точка игнорирования | зависит от INV-06 | closed | F-38 | 14 | ok
INV-08 | Совместимость с fake-CLI тестами и прецедент muse-bridge | tests/*.py и muse-bridge/server.py:338-4185 | grep OPENCODE_BIN и чтение fallback | 25 | карта тестов и паттерн fallback | описаны подмена CLI и паттерн serve-to-exec | независим | closed | F-43 | 19 | ok
INV-09 | Природа трёх красных тестов базовой линии | baseline_uvx_pytest.log и tests/test_step_interruption.py | прогон файла и подмножества, разбор логов | 30 | классификация причин | определены причины каждого из трёх тестов | независим | closed | F-47 | 26 | ok
INV-10 | Изоляция встроенных инструментов `opencode` в режиме serve | OpenAPI `permissions` и `session.tool.*` | чтение схемы, живой прогон заблокирован квотой | 30 | схема сопоставления событий | подтверждена эквивалентность с режимом run | блокирует контракт адаптера | open | OPEN-07 | 12 | схема есть, поведение не прогнано из-за free-limit
INV-11 | Параллелизм, SQLite и ресурсы нескольких процессов serve | opencode.db 2.27 GB и RSS процессов | замер idle RSS и FD, нагрузочный прогон не выполнен | 30 | оценка ресурсов | получены числа под параллельной нагрузкой | зависит от INV-03 | open | OPEN-08 | 10 | измерен только idle serve 152 MiB
INV-12 | Время до первого токена на тяжёлом промпте около 103 KB через serve | сессия 423ca27f и serve | замер после сброса квоты | 20 | таблица TTFT для 100 KB | получен TTFT при `prompt_chars` около 103088 | зависит от INV-03 | open | OPEN-09 | 5 | квота исчерпана до около 03:00 MSK 2026-10-26
INV-13 | Совместимость ротации чистых IP с долгоживущим serve | server.py:1047-1131 и config georouter | чтение кода и конфига | 25 | вывод о маршруте egress | определено, ходит ли serve напрямую либо через georouter | зависит от INV-04 | open | OPEN-06 | 15 | egress georouter известен, поведение прокси у serve не проверено
INV-14 | Инкрементально ли `ToolCallParser` отдаёт `content` при дельтах | server.py:2213-2338 | чтение алгоритма и существующих тестов | 20 | описание удерживаемого хвоста | задан максимум удерживаемых символов | независим | closed | F-06 | 11 | ok

## 6. Состав handoff-пакетов (потребители)

- `handoff-architect.md` — Architect (S2): корневые причины, требования `REQ-*`, сравнение вариантов, `HL-ENV/v1`, гейты, non-goals.
- `handoff-qa.md` — QA и Coder-тесты: red→green сценарии, живой тяжёлый путь, протокол замеров.
- `handoff-dev.md` не готовится: задача класса S2, вход в разработку только через Архитектора (ARCH_GATE).

## ИСТОЧНИКИ СКИЛЛОВ
### ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md
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

<!-- HL-RESILIENCE-GATES-V5 -->
## Обязательные Highload & Resilience гейты (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)

Единый источник правды (SSoT) всех формул, 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` и 21 стоп-кода — `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`). Архитектурный пакет **не может** получить статус `approved` без:

1. **`HL-ENV-01`**: полностью заполненной таблицы из 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` в единицах СИ с указанием источников, проверкой замыкания памяти $W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} \le 0.80 \times \text{Mem\_limit\_per\_pod}$ и двойного доказательства для любого `N/A` (`git diff` + транзитивный граф `callers/callees`).
2. **`C-MULT-I1..I5`**: многоролевого и многопоколенческого расчёта соединений $C_{\text{dep}}(d) \le 0.60 \times \text{Limit\_dep\_share}[d]$ по всем ролям (`crawler`, `llm`, `pod_fetcher`, `control_plane`, `migrations_cron`) с учётом $G_{\text{reload}} \in \{1, 2\}$, `BlockingConnectionPool`, `max_waiters <= 2M`, запрета сокетов до `fork()` и бюджета портов/FD (`<= 50%` портов, `<= 70% ulimit_n`).
3. **`S-HERD-I1..I5`**: расчёта пачечного стартового залпа $B_{\text{dep, 1s}}(d) = K_{\text{calls}}[d] \cdot (\lambda_{\text{fetch}}(d) + 4\sqrt{\lambda_{\text{fetch}}(d)} + 4) \le 0.50 \times \text{Limit\_dep\_rps}[d]$ и стационарного поллинга $R_{\text{poll}}(d) \le 0.20 \times \text{Limit\_dep\_rps}[d]$, пересева CSPRNG после `fork()`, `If-None-Match` (`304`), cancellation-safe `singleflight` и политики `Max_stale_age_s[c]`.
4. **`H-CPU-I1..I5`**: доказательства $O(1)/O(\log N)$ индексов на иммутабельном `Snapshot`, отсутствия парсинга/аллокаций на горячем пути (`if not enabled: return` первой строкой), неблокирующей доставки `Snapshot` $\le 2\text{ мс}$ на тик event loop (`mmap` / кооперативные батчи `sleep(0)`) и выполнения трёх неравенств CPU на $P_{\text{avail\_min}}$.
5. **`R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`**: заполненной `Dependency Failure Matrix`, бюджета дедлайнов $\le 0.30 \times \text{SLA}_{\text{p99\_s}}$, Token-Bucket Retry Budget, `Circuit Breaker` (`HALF_OPEN=1`), двухэтапного фильтра `M-SEM/v1` + post-eviction предиката `Panic-Open` ($|V_{\text{healthy}}| - 1 \ge N_{\text{floor}}$) и разделения `origin_health` vs `node_health`.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.

### ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md
# AGENTS

Ты работаешь в Python backend-проекте на Litestar.

## Язык общения

Пользователь — носитель русского языка, поэтому общение в чате и любой текст, который человек читает глазами (docstrings, комментарии в коде, **описания коммитов**), — на русском. Идентификаторы (имена переменных, функций, классов, файлов) — на английском, как принято в коде.

| Где | Какой язык |
|---|---|
| Сообщения в чате (планы, статус, объяснения, ответы на вопросы) | Русский |
| Сообщения в чате при ошибках/конфликтах | Русский |
| Commit messages — **тэги** (`feat:`, `fix:`, `refactor:`, `chore:`, scope) | Английский — это формат Conventional Commits, парсится changelog-генераторами |
| Commit messages — **описание** после двоеточия | **Русский** — это текст для команды, его читают люди |
| Префиксы `[agent]` / `[manual]` / `[assisted]` | Английский — это маркер, не текст |
| Docstrings в коде | Русский — пользователь читает их в IDE через hover |
| Комментарии в коде (`# объясняет почему`) | Русский |
| Названия переменных, функций, классов, файлов | Английский |

Если поймал себя что начал писать описание коммита или docstring по-английски — остановись и переформулируй по-русски.

Примеры docstring:

✅ Правильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Обрезает URL до max_length символов, добавляя '...' в конце.

    Args:
        url: URL для обрезки.
        max_length: Максимальная длина результата (по умолчанию 50).

    Returns:
        Обрезанный URL с эллипсисом, либо исходный URL если он короче max_length.

    Raises:
        ValueError: Если max_length меньше длины эллипсиса.
    """
    # Если URL уже короткий — возвращаем как есть, без аллокации
    if len(url) <= max_length:
        return url
    ...
```

❌ Неправильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate a URL to max_length characters, adding ellipsis at the end.
    ...
    """
    # Return as-is if URL is already short
    ...
```

## Главные правила

1. Сначала прочитай этот файл и релевантные тематические файлы из `.agents/`.
2. **При ошибке — Identify → Assess → Communicate → Solutions.** Не предлагай
   workaround сразу — сначала пойми, почему упало. Severity-уровни и алгоритм
   реакции — в `.agents/agents/error-handling.md`.
3. Не меняй архитектуру проекта без явной причины.
4. Все изменения должны быть минимально достаточными.
5. Любое изменение кода должно сопровождаться проверкой:
   - `uv run ruff check .`
   - `uv run basedpyright`
   - `uv run pytest -q`
6. Для изменений схемы и БД читай `.agents/agents/database.md`.
7. Если меняется публичное API, обнови тесты и README.
8. Перед подготовкой MR прочитай `.agents/agents/mr.md`.
9. Для hotfix обязательно прочитай `.agents/agents/hotfix.md`.
10. На каждый баг должен появиться regression test.
11. Не добавляй зависимости без необходимости.
12. Перед началом работы создай ветку по правилу именования веток проекта.
13. Архитектурные решения с ≥ 2 альтернативами и дорогим откатом оформляй как
    ADR с options analysis (см. `.agents/agents/docs.md`, раздел «ADR-full»).
14. Если задача дата-инженерная (ETL, Airflow DAG, Kafka-воркеры, ClickHouse,
    выгрузка в S3) — читай `.agents/agents/data-engineering.md`.
15. **Согласованный внешний контракт не менять без явного указания в текущей
    задаче.** HTTP/event/data/CLI/SDK, уже согласованные с внешними
    исполнителями, заморожены. «Улучшить», соседняя задача, свой архитектурный
    черновик — не разрешение. Нет явной фразы «измени контракт / breaking /
    обнови схему» → STOP, ASK. Канон: `.agents/agents/scope-and-contracts.md`.
16. **Работать только в рамках своей задачи.** Scope = текущий промпт и текущий
    Jira-KEY. Чужие KEY/MR не открывать, не чинить и не отчитываться по их
    статусу «заодно». Чужой тикет — только если текущая постановка явно
    называет его зависимостью, и тогда только факт зависимости. Канон: тот же
    `scope-and-contracts.md`.
17. **Сдача — через MR на remote, если remote есть.** Не коммитить и не пушить
    в `main` / `master` / `dev`. Коммит живёт на своей ветке, затем push + MR.
    Канон: `.agents/agents/mr.md`. Merge MR — человек, пока не сказано «смержи».
    После merge на remote обязательно обновить локальную target-ветку через
    fast-forward и сверить её `HEAD` с remote. Локальный merge до MR запрещён.

## Подход к работе

Поведение агента управляется **правилами** (`.agents/`) и **алгоритмами**
(`.skills/`). Это конвейер: пришла задача → агент читает релевантный skill →
выполняет шаги → проверки → коммит на своей ветке → MR на remote (если remote есть).
Отдельный «план в чате с ожиданием ОК»
не требуется — `.skills/*.md` уже содержит пошаговый алгоритм.

Если задача сложная и хочется разведать прежде чем писать код:

- **Используй встроенный Plan mode** AI-IDE (в Claude Code, Cursor, Continue,
  Codex CLI). В этом режиме агент только читает файлы и описывает что
  собирается сделать, не пишет и не запускает команды. Это быстрее и дешевле
  чем эмуляция через «покажи план в чате, жди подтверждения».
- **Артефакты задачи** (заметки, отчёты code review, ADR, временные
  результаты) можно складывать в `Tasks/<JIRA-KEY>/` рядом с кодом, чтобы
  при возврате к задаче через день было видно где остановились. Это
  опциональный паттерн, не обязательное «всегда пиши план в md».
- **Architecture-документ** для большой задачи (≥ 1 дня работы, несколько
  модулей, breaking change) — отдельный жанр, см. `.agents/skills/architecture.md`.
  Это не «approval gate», это рабочий артефакт с C1+C2 диаграммами и
  списком задач T1-TN.

В конце задачи — короткий отчёт с URL MR (или явно «remote нет»). Не ждать
фразы «делай MR». Правки оператора — уже после открытого MR, не вместо него.

## Правила именования веток

Ветки должны называться в соответствии с типом задачи и Jira key.

Формат ветки:

`<type>/<JIRA-KEY>-<short-description>`

Где:
- `type` — тип задачи: `feature`, `bugfix`, `hotfix`, `deploy` (релиз/выкат — см. `.agents/skills/devops-release.md`)
- `JIRA-KEY` — идентификатор задачи в Jira, например `PROJ-123`
- `short-description` — короткое описание в `kebab-case`

Примеры:
- `feature/PROJ-123-add-link-archive`
- `bugfix/PROJ-456-fix-empty-title-validation`
- `hotfix/PROJ-789-fix-production-db-timeout`

Правила:
- использовать латиницу, цифры, `/` и дефисы;
- не использовать пробелы;
- не использовать длинные описания;
- для задач из Jira всегда включать Jira key в имя ветки;
- тип ветки должен соответствовать типу задачи.

## Правила коммитов и измерение вклада агента

Каждый коммит должен быть помечен тегом в начале сообщения:

- `[agent]` — diff агента принят без существенных правок (точечные правки имён/форматирования допустимы)
- `[assisted]` — основу сделал агент, но ты переписал значимую часть (логика, структура, >20% строк)
- `[manual]` — код написан вручную без участия агента

Три тега вместо двух нужны потому, что бинарное деление «агент/не агент» врёт в сторону агента: коммит, где ты взял идею из diff и переписал половину, честнее считать как `[assisted]`, а не `[agent]`. Это совпадает с индустриальной практикой: self-reported «AI-assisted» обычно ~40%, но реально AI-authored (без правок) — около 27%.

Формат — Conventional Commits, тэги английские (`feat:`/`fix:`/`refactor:`/`chore:`), **описание после двоеточия — на русском** (см. таблицу «Язык общения» выше).

Примеры:
```
[agent] feat(api): добавить эндпоинт PATCH /links/{id} и тесты
[assisted] refactor(services): переработать сервисный слой после черновика агента
[manual] docs(readme): исправить опечатку
[agent] test(links): добавить regression-тест на валидацию заголовка с пробелами
[manual] chore(deps): обновить pytest до >=9.0.3 для CVE-2025-71176
```

После выполнения каждой задачи выводи итоговый блок:

```
[agent | assisted | manual] <короткое описание задачи на русском>
Files: <количество файлов изменено>
Tests: <добавлено/изменено>
Checks: ruff ✅  basedpyright ✅  pytest ✅
```

## Что делать когда `git commit` падает с pre-commit-хуком

В этом репозитории стоят pre-commit-хуки (ruff, basedpyright, bandit, pip-audit, gitleaks, end-of-file-fixer, trailing-whitespace, и т.д.). Каждый `git commit` прогоняет их **до** создания коммита. Возможны три исхода:

### Исход A: Все хуки `Passed` — коммит создан

Ничего делать не надо. Покажи `git log -1 --stat` в подтверждение.

### Исход B: Хук **автофиксанул** файлы (`files were modified by this hook`)

Так работают `end-of-file-fixer`, `trailing-whitespace`, `ruff format`, `ruff check --fix`. Они **сами** правят файлы и сигнализируют что коммит надо повторить.

Действия:
1. Посмотри какие файлы изменены: `git status`.
2. `git add` этих файлов.
3. `git commit -m "..."` повторно с тем же сообщением.

На втором заходе автофиксы уже применены — хук пройдёт `Passed`.

### Исход C: Хук нашёл **реальную ошибку** (например `basedpyright` или `bandit`)

Это **не** автофикс — это ошибка которую надо понять и исправить. Действия:

1. Прочитай вывод хука. У каждой ошибки есть путь к файлу, номер строки и описание.
2. Открой файл, разбери что не так:
   - **basedpyright**: чаще всего нет аннотации типа, или `Any` где должен быть конкретный тип, или доступ к `None` без проверки. Добавь аннотацию или `# pyright: ignore[<ruleId>]` с комментарием **почему** именно это игнор оправдан.
   - **bandit**: нашёл небезопасную конструкцию (`subprocess(shell=True)`, `yaml.load` без `SafeLoader`, и т.д.). Перепиши на безопасный вариант. Не используй `# nosec` без объяснения.
   - **pip-audit**: CVE в зависимости. Если это твой код добавил эту зависимость — обнови её до fix-версии **отдельным коммитом** (`[manual] chore(deps): обновить <package> для CVE-XXXX`). Если CVE в чужой зависимости которую ты не трогал — см. `.agents/agents/security.md`, секция «pip-audit».
3. Исправь, добавь в индекс (`git add`), коммить снова.
4. Если 3 раза подряд хук падает на одном и том же — остановись, опиши пользователю что именно ошибка говорит и в чём конфликт. Не зацикливайся.

Расширенный алгоритм реакции на любые ошибки (не только pre-commit) — в
`.agents/agents/error-handling.md` (severity Critical/High/Medium/Low + правило
«Identify → Assess → Communicate → Solutions»).

### Что **запрещено** делать

- **`git commit --no-verify`** — обход всех хуков, **никогда**.
- **`SKIP=hook git commit ...`** — пропуск конкретных хуков, **никогда** (единственное исключение — учебный демо в Шаге 6.2 no-rules-variant, описано в `.agents/agents/security.md`).
- **`PRE_COMMIT_ALLOW_NO_CONFIG=1`** — это срабатывает когда `.pre-commit-config.yaml` отсутствует. Если ты эту переменную увидел в подсказке git'а — конфиг **потерян**, восстанови его (`git show HEAD:.pre-commit-config.yaml > .pre-commit-config.yaml`), не обходи.

Подробности — в `.agents/agents/security.md`, секция «Pre-commit хуки — никаких обходов».

## Конвертация документации в Confluence Wiki Markup

Если нужно преобразовать `.md` файл в Confluence Wiki Markup для вставки через `Other macros → Markup → Confluence wiki`:

**Читай файл с правилами перед конвертацией:**
```
.agents/md-to-confluence-rules.md
```

Файл лежит в корне каталога `agents_ skills/` (на уровень выше `agents/`).

Он содержит:
- точные команды bash для конвертации (pandoc + sed + clean-jira-escapes.py)
- таблицу типичных ошибок и их решений
- скрипт проверки результата (три проверки должны вернуть 0)
- структуру папок для готовых `.txt` файлов

**Правило:** никогда не конвертируй вручную и не придумывай правила на лету — всё в `md-to-confluence-rules.md`.

### ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md
# Scope задачи и согласованные внешние контракты

Два жёстких правила. Нарушение — блокирующий FAIL ревью и приёмки, не follow-up
и не «улучшение заодно». Полный текст живёт здесь; скиллы ролей ссылаются
и ставят бинарный пункт в критерии приёмки.

Читать при любой разработке: фича, багфикс, рефакторинг, hotfix, архитектура,
ревью, MR, цикл техлида.

## 1. Согласованный внешний контракт не менять без явного указания

Если контракт уже согласован с внешними исполнителями — другими сервисами,
командами, потребителями HTTP/event/data/CLI/SDK, аналитикой — его нельзя
менять, расширять, сужать, переименовывать и «улучшать», пока текущая задача
явно это не требует.

### Что считается внешним контрактом

- HTTP: method, path, query, request/response DTO, status, error body, auth,
  идемпотентность, версия.
- Событие / очередь / топик: имя, схема, обязательность полей, типы,
  nullability, порядок, совместимость.
- Публичный CLI, SDK, shared-library API.
- Формат файла, протокол, контракт аналитики/событийки.
- Cross-repo зеркало той же схемы.

Внутренняя реализация за неизменной границей (сервис, репозиторий, SQL,
логи, метки, тесты потребителя не ломающие) — не контракт.

### Что считается явным указанием

Фраза в **текущей** постановке (промпт, Jira этой KEY, AC этой задачи):
«измени контракт», «breaking», «обнови схему / DTO / API / событие»,
«согласуй с \<команда/сервис\>». Без такой фразы права менять контракт нет.

Не является указанием:

- «сделай лучше / удобнее / правильнее»;
- соседняя задача, эпик, чужой MR, страница Confluence «как будет»;
- архитектурный документ, который агент сам написал в этом же заходе;
- «потребители подстроятся», «это же совместимо, если добавить поле».

Добавление поля, смена default, переименование, смена типа на совместимый,
новый код ошибки на старом пути — тоже изменение контракта.

### Что делать

1. До кода найти согласованную границу в зоне изменения (спека, Confluence,
   Pydantic/DTO, OpenAPI, схема события, KB `contracts/`).
2. Если задача требует её менять, а в постановке этого нет — **STOP, ASK**.
   Не чинить «заодно». Не предлагать breaking как часть текущей сдачи.
3. Если указание есть — delta контракта, совместимость, потребители и
   verification явным пунктом в AC; иначе задача не готова к коду.

## 2. Работаем только в рамках своей задачи

Scope = текущий промпт и, если есть, текущий Jira-KEY. Чужие задачи не
открывать, не ревьюить, не чинить и не отчитываться по их статусу.

### Запрещено

- Искать и пересказывать статус соседних KEY / MR / стендов «заодно».
- «Пока смотрел, увидел EYE-XXXX — там вот что».
- Тащить скоуп, AC, фикс или рефакторинг из другой задачи в текущий diff.
- Отвечать на вопрос по одной задаче отчётом по доске / эпику / чужим тикетам.

### Можно

- Прочитать другой тикет, только если **текущая** постановка явно называет
  его зависимостью (`blocked by` / `relates` / «зависит от KEY»). Тогда —
  только факт зависимости, не статус-отчёт по чужой работе.
- Ответить по другой задаче, только если владелец **этим промптом** её
  спросил. Это новый запрос, не расширение текущего.

Неясная граница KEY → ASK, не гадать и не ходить по доске.

## Критерии приёмки (копировать в DoD роли)

- [ ] Diff не меняет согласованный внешний контракт, либо в текущей задаче
      есть явное указание это сделать и delta зафиксирована.
- [ ] Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в
      отчёте отсутствуют, если их не спросили.

Нет любого пункта → задача не сдана, ревью `CHANGES_REQUESTED` / приёмка
не ACCEPT.

### brief-review/references/checklist-sources.md#SK-P
| Триггер в скоупе пакета | Стандарт | Применимость |
|---|---|---|
| Python-архитектура S2 (`profile=python-aisdlc-gcge`) | `aisdlc-gcge/skills/architecture.md` | сработал |
| Общие правила Python-проекта и MR | `aisdlc-gcge/AGENTS.md` | сработал |
| Внешние контракты HTTP/SSE/CLI и границы задачи | `aisdlc-gcge/agents/scope-and-contracts.md` | сработал |
| SQL, ORM, миграции, DDL/DML | `aisdlc-gcge/agents/database.md` | не сработал (нет БД/миграций в скоупе) |
| Airflow, Spark, ETL, DAG | `aisdlc-gcge/agents/data-engineering.md` | не сработал (нет ETL/DAG в скоупе) |

### ARCHITECTURE_PACKET_FILES
Список файлов Architecture Packet и входов ARCH_GATE:
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json`
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json`
- Целевая область реализации из пакета: `bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`, `bridges/opencode-zen-bridge/tests/test_zen_bridge.py`


## БРИФ
<<<BRIEF_BEGIN
Ты — Визионер. Твоя задача — оценить потенциал, масштаб, стратегическое влияние. Ключевой вопрос: «Насколько это меняет игру?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на долгосрочной ценности: насколько решение масштабируемо, какие возможности открывает, насколько опережает альтернативы, есть ли потенциал для роста.

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

Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложены целиком (без обрезки; раздел «Не вложено» пуст — все первичные артефакты даны полностью в этом брифе) проверяемый Architecture Packet и квитанция пройденного гейта `ARCH_GATE`:
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json sha256=e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02
{
  "schema_version": "1.0",
  "packet_version": "1.0",
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "cycle": 1,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": "plans/architect-01.json",
    "sha256": "d435226fff3370982e236d7e5bb885d341331d70a2022e67c4d9f8a594a5283c"
  },
  "summary": "Гибрид C/A1: короткоживущий serve v2 на попытку, общий нормализованный поток событий для SSE и JSON, run как kill-switch и безопасный pre-prompt fallback; grace-статусы, три watchdog и гарантированная уборка PGID. Это проектный контракт Stage 2, не утверждение о выполненных изменениях или живой приёмке.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/zen-realtime-reasoning",
    "branch": "feature/zen-realtime-reasoning",
    "architect_write_allowlist": [
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-01.before.json",
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-01.json",
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json"
    ],
    "coder_target_files": [
      "bridges/opencode-zen-bridge/server.py",
      "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
      "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
    ],
    "forbidden": [
      "analysis/zen-realtime-reasoning/** (frozen analyst inputs)",
      "bridges/muse-bridge/**",
      "прямой Google route и test_google_direct.py",
      "~/.dsh/** до отдельной rollout-фазы",
      "общие конфиги opencode/georouter, opencode.db, зависимости/lockfiles"
    ],
    "architect_permission": "run-artifacts-write; product read-only"
  },
  "requirement_ids": [
    "REQ-001",
    "REQ-002",
    "REQ-003",
    "REQ-004",
    "REQ-005",
    "REQ-006",
    "REQ-007",
    "REQ-008",
    "REQ-009",
    "REQ-010",
    "REQ-011",
    "REQ-012",
    "REQ-013",
    "REQ-014",
    "REQ-015",
    "REQ-016",
    "REQ-017",
    "REQ-018",
    "REQ-019",
    "REQ-020"
  ],
  "requirements": [
    {
      "id": "REQ-001",
      "priority": "MUST",
      "statement": "Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага",
      "acceptance": "AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс",
      "evidence": "F-17, F-18, F-19",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-002",
      "priority": "MUST",
      "statement": "Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883",
      "acceptance": "AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата",
      "evidence": "F-35, F-34",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-005"
      ]
    },
    {
      "id": "REQ-003",
      "priority": "MUST",
      "statement": "Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными",
      "acceptance": "AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04)",
      "evidence": "F-43, F-40, F-42",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-004",
      "priority": "MUST",
      "statement": "Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\\n` (статус подключения/ожидания модели), независимо от состояния апстрима",
      "acceptance": "AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме",
      "evidence": "F-36, F-37, F-04, F-33",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-005",
      "priority": "MUST",
      "statement": "Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее",
      "acceptance": "AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее",
      "evidence": "F-37, F-38, F-07, F-39",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-006",
      "priority": "MUST",
      "statement": "Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку",
      "acceptance": "AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с",
      "evidence": "F-09, F-30, F-31",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-007",
      "priority": "MUST",
      "statement": "Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения",
      "acceptance": "AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout`",
      "evidence": "F-09, F-19, F-32",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-008",
      "priority": "MUST",
      "statement": "Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с",
      "acceptance": "AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится",
      "evidence": "F-14, F-30, F-33",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-009",
      "priority": "MUST",
      "statement": "Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка",
      "acceptance": "AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка",
      "evidence": "F-11, F-12",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-010",
      "priority": "MUST",
      "statement": "`ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len(\"<tool_invoke>\")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты",
      "acceptance": "AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом",
      "evidence": "F-06, F-05",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-011",
      "priority": "MUST",
      "statement": "Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason=\"tool_calls\"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути",
      "acceptance": "AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт",
      "evidence": "F-05, F-11, F-43",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-012",
      "priority": "MUST",
      "statement": "Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native)",
      "acceptance": "AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь",
      "evidence": "F-08, F-22, OPEN-07",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-013",
      "priority": "MUST",
      "statement": "Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта",
      "acceptance": "AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`)",
      "evidence": "F-10, F-11, F-15, F-32",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-014",
      "priority": "SHOULD",
      "statement": "`usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим",
      "acceptance": "AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры",
      "evidence": "F-19, F-02",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "REQ-015",
      "priority": "MUST",
      "statement": "Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование",
      "acceptance": "AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey`",
      "evidence": "F-21, F-27",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-016",
      "priority": "MUST",
      "statement": "Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода",
      "acceptance": "AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST`",
      "evidence": "F-32, F-30",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-017",
      "priority": "SHOULD",
      "statement": "Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс",
      "acceptance": "AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов",
      "evidence": "F-45, F-46, F-47, F-48, F-49",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ]
    },
    {
      "id": "REQ-018",
      "priority": "MUST",
      "statement": "Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается",
      "acceptance": "AC-024: `test_google_direct.py` проходит без правок",
      "evidence": "F-16",
      "verification_ids": [
        "VER-001",
        "VER-003"
      ]
    },
    {
      "id": "REQ-019",
      "priority": "SHOULD",
      "statement": "Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой",
      "acceptance": "AC-025: побайтовое совпадение после деплоя",
      "evidence": "F-34, OPEN-17",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "REQ-020",
      "priority": "MUST",
      "statement": "В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет)",
      "acceptance": "AC-026: тест красный на текущем коде и зелёный на новом (red to green)",
      "evidence": "F-44",
      "verification_ids": [
        "VER-005"
      ]
    }
  ],
  "evidence": [
    {
      "id": "EVD-001",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-01; server.py:1146-1161, 966-969, 1617-1649",
      "claim": "Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-01"
    },
    {
      "id": "EVD-002",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-02; server.py:2417-2462",
      "claim": "`parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-02"
    },
    {
      "id": "EVD-003",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-03; server.py:3312-3327, 3399-3412",
      "claim": "`Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{\"role\":\"assistant\",\"content\":\"\"}` до `_StartupGate`, spawn и чтения stdout",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-03"
    },
    {
      "id": "EVD-004",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-04; server.py:49, 3437-3450, 865-952",
      "claim": "Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{\"content\":\"\"}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-04"
    },
    {
      "id": "EVD-005",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-05; server.py:3462-3493",
      "claim": "События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-05"
    },
    {
      "id": "EVD-006",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-06; server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323)",
      "claim": "`ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len(\"<tool_invoke>\")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-06"
    },
    {
      "id": "EVD-007",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-07; server.py:1848-1888",
      "claim": "`_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-07"
    },
    {
      "id": "EVD-008",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-08; server.py:228-231",
      "claim": "Конфиг `opencode` для дочернего процесса по умолчанию: `permission {\"*\":\"ask\"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-08"
    },
    {
      "id": "EVD-009",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-09; server.py:46, 3450, команда grep от 2026-10-25",
      "claim": "В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-09"
    },
    {
      "id": "EVD-010",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-10; server.py:1197-1236, 3399-3411, 3451",
      "claim": "`_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-10"
    },
    {
      "id": "EVD-011",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-11; server.py:277, 287-298, 309-314, 1340-1368, 1471-1535",
      "claim": "Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-11"
    },
    {
      "id": "EVD-012",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-12; server.py:1458-1470, 3989-3996",
      "claim": "Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-12"
    },
    {
      "id": "EVD-013",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-13; server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK",
      "claim": "`MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-13"
    },
    {
      "id": "EVD-014",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-14; server.py:848-862, 865-952",
      "claim": "`_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-14"
    },
    {
      "id": "EVD-015",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-15; server.py:1047-1082, 1093-1131; start.sh:24-31",
      "claim": "Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-15"
    },
    {
      "id": "EVD-016",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-16; server.py:3127-3266 (reasoning emit около 3219)",
      "claim": "`_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({\"reasoning_content\": text})` в реальном времени; прецедент прямого маршрута для Option B",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-16"
    },
    {
      "id": "EVD-017",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-17; explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK)",
      "claim": "`opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-17"
    },
    {
      "id": "EVD-018",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-18; explorer-zone-b.md §2",
      "claim": "Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-18"
    },
    {
      "id": "EVD-019",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-19; explorer-zone-b.md §1, §3",
      "claim": "`opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-19"
    },
    {
      "id": "EVD-020",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-20; sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK",
      "claim": "Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-20"
    },
    {
      "id": "EVD-021",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-21; sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25",
      "claim": "Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-21"
    },
    {
      "id": "EVD-022",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-22; sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B)",
      "claim": "OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-22"
    },
    {
      "id": "EVD-023",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-23; sa-poc/poc_serve.log",
      "claim": "PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {\"*\":\"deny\"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-23"
    },
    {
      "id": "EVD-024",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-24; sa-poc/poc_georouter.log",
      "claim": "Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-24"
    },
    {
      "id": "EVD-025",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-25; sa-poc/poc_direct_zen_proxy.log",
      "claim": "Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-25"
    },
    {
      "id": "EVD-026",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-26; ~/.config/model-georouter/config.json (значения без секретов)",
      "claim": "`model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-26"
    },
    {
      "id": "EVD-027",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-27; ~/.config/opencode/opencode.json (обход ключей с маскированием)",
      "claim": "В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-27"
    },
    {
      "id": "EVD-028",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-28; ls -l, opencode run --help от 2026-10-25",
      "claim": "`~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-28"
    },
    {
      "id": "EVD-029",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-29; ps, lsof, launchctl limit от 2026-10-25 22:4x MSK",
      "claim": "Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-29"
    },
    {
      "id": "EVD-030",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-30; explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK",
      "claim": "Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-30"
    },
    {
      "id": "EVD-031",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-31; explorer-zone-d.md §2",
      "claim": "Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-31"
    },
    {
      "id": "EVD-032",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-32; explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log",
      "claim": "Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-32"
    },
    {
      "id": "EVD-033",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-33; explorer-zone-d.md §3",
      "claim": "Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-33"
    },
    {
      "id": "EVD-034",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-34; explorer-zone-d.md §1; /health от 2026-10-25",
      "claim": "Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-34"
    },
    {
      "id": "EVD-035",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-35; ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C)",
      "claim": "Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-35"
    },
    {
      "id": "EVD-036",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-36; /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка)",
      "claim": "Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-36"
    },
    {
      "id": "EVD-037",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-37; client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка)",
      "claim": "UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===\"\"` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\\n`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-37"
    },
    {
      "id": "EVD-038",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-38; app.asar openai-completions.js, смещения 116117903-116120153",
      "claim": "При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-38"
    },
    {
      "id": "EVD-039",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-39; ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста",
      "claim": "Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-39"
    },
    {
      "id": "EVD-040",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-40; bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185",
      "claim": "`muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-40"
    },
    {
      "id": "EVD-041",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-41; bridges/muse-bridge/server.py:165, 4150-4156",
      "claim": "`muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-41"
    },
    {
      "id": "EVD-042",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-42; ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log",
      "claim": "В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-42"
    },
    {
      "id": "EVD-043",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-43; tests/*.py (grep OPENCODE_BIN и _fake_cli)",
      "claim": "Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env`",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-43"
    },
    {
      "id": "EVD-044",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-44; tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py",
      "claim": "Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-44"
    },
    {
      "id": "EVD-045",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-45; baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log",
      "claim": "Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-45"
    },
    {
      "id": "EVD-046",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-46; sa_iso_file.log",
      "claim": "Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-46"
    },
    {
      "id": "EVD-047",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-47; sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287",
      "claim": "Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-47"
    },
    {
      "id": "EVD-048",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-48; baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368",
      "claim": "Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-48"
    },
    {
      "id": "EVD-049",
      "kind": "document",
      "ref": "analysis/zen-realtime-reasoning/evidence-ledger.md#F-49; git log -S от 2026-10-25",
      "claim": "`grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`)",
      "collected_at": "2026-10-25",
      "analyst_fact_id": "F-49"
    },
    {
      "id": "EVD-050",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:228-231",
      "claim": "permission=ask сохраняет native tool schema; комментарий baseline предупреждает: deny/tools:false может вызвать Zen 403."
    },
    {
      "id": "EVD-051",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/tests/test_step_interruption.py:67-145,150-190,388-415",
      "claim": "Fake CLI игнорирует argv, увеличивает counter до stdin.read(); reasoning_interrupted ожидает ровно Simple greeting.; общий сервер на класс."
    },
    {
      "id": "EVD-052",
      "kind": "command",
      "ref": "UV_OFFLINE=1 uvx ruff check --no-cache bridges/opencode-zen-bridge/server.py",
      "claim": "exit=1, единственный baseline E402 на zen_catalog import:67; ruff 0.17.2."
    },
    {
      "id": "EVD-053",
      "kind": "command",
      "ref": "UV_OFFLINE=1 uvx basedpyright bridges/opencode-zen-bridge/server.py",
      "claim": "exit=1, 2 errors (reportImplicitRelativeImport zen_catalog:67, reportConstantRedefinition CATALOG_SOURCE:131), 564 warnings; basedpyright 1.40.2 / pyright 1.1.414."
    },
    {
      "id": "EVD-054",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-zen-step-20261024/architecture/architecture-packet.json",
      "claim": "Подтверждённый предыдущий packet: schema layout high_load_envelope/resilience_gates/21 legacy checks. Берётся формат, не результаты исполнения/одобрения."
    },
    {
      "id": "EVD-055",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:848-862,2849-2867,3630-3698",
      "claim": "_stop_proc ранний return после leader exit может оставить descendants; несколько finally/except используют proc.kill вместо killpg. Новый lifecycle обязан закрыть эти пробелы для обоих транспортов."
    },
    {
      "id": "EVD-056",
      "kind": "command",
      "ref": "worktree_fingerprint.py --compare fingerprints/architect-before.json",
      "claim": "WORKTREE_UNCHANGED 2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334 files=152; промежуточная проверка Stage 2."
    },
    {
      "id": "EVD-057",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:2213-2340,3462-3534",
      "claim": "Парсер удерживает префикс тега, незакрытые/невалидные блоки на finish может выдать сырыми; emit_parsed_content -> _strip_broken_tool_blocks удаляет их. tool_use сейчас читает raw event.part, поэтому canonical adapter должен сохранить этот payload."
    },
    {
      "id": "EVD-058",
      "kind": "code",
      "ref": "tests/test_dsh_profile_config.py:7-15",
      "claim": "Root suite содержит optional чтение ~/.dsh; clean-room runner обязан не монтировать owner home. Команды VER не выполняют deploy и не требуют ~/.dsh."
    },
    {
      "id": "EVD-059",
      "kind": "document",
      "ref": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/route-manifest.json",
      "claim": "Preset analyst-teamlead, S2, profile python-aisdlc-gcge, architect run-artifacts-write, downstream_panel=true."
    },
    {
      "id": "EVD-060",
      "kind": "document",
      "ref": "Текущий Brief Stage 2, Steps 1–4",
      "claim": "Явно разрешены AD-001..004, baseline 3 tests, синтетический статус после grace, watchdog 20/60/60 и только run-артефакты."
    },
    {
      "id": "EVD-061",
      "kind": "code",
      "ref": "bridges/opencode-zen-bridge/server.py:_UpstreamBreaker.allow (1415-1428), _SlotBulkhead.__init__ (1265-1270)",
      "claim": "Baseline HALF_OPEN probe can be re-admitted after reset_s while first is active; default slots2/configured waiters12 exceed canonical2M unless effective clamp. Dedicated oracles freeze intended single-probe/effective bound without altering deployed6/12."
    }
  ],
  "risk_triggers": [
    "auth",
    "security",
    "trust-boundary"
  ],
  "assumptions": [
    {
      "id": "ASM-001",
      "class": "continuable",
      "source_open_ids": "OPEN-06/08",
      "statement": "Per-spawn env ротация и child192MiB design estimates; физический egress/SQLite6parallel проверяет H3.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-015",
        "EVD-020",
        "EVD-026"
      ]
    },
    {
      "id": "ASM-002",
      "class": "continuable",
      "source_open_ids": "OPEN-09/11",
      "statement": "TTFT first actual reasoning<=3s и pause goal15s — operational goals, не hard deterministic unit guarantee; watchdog default20/60/60 и status<=1s заданы текущим брифом.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-019",
        "EVD-060"
      ]
    },
    {
      "id": "ASM-003",
      "class": "continuable",
      "source_open_ids": "OPEN-12/13/14",
      "statement": "Статусы [мост] разрешены текущим брифом с grace; model bytes не меняем, retries без reasoning dedup.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-060"
      ]
    },
    {
      "id": "ASM-004",
      "class": "continuable",
      "source_open_ids": "OPEN-02/04",
      "statement": "Три baseline tests входят в Stage3 текущего брифа: expected spawns/finish/tool_calls согласовать cap3 и fresh per-test resilience.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-047",
        "EVD-048",
        "EVD-060"
      ]
    },
    {
      "id": "ASM-005",
      "class": "continuable",
      "source_open_ids": "OPEN-07",
      "statement": "Deny-all capability и equivalent ask-auto-reject должны пройти fake permission assertions; реальное no-file mutation доказывает H6, ещё не выполнено.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-022",
        "EVD-050"
      ]
    },
    {
      "id": "ASM-006",
      "class": "continuable",
      "source_open_ids": "OPEN-05/16",
      "statement": "Неподтверждённые direct Zen HTTP/другие run форматы не нужны выбранному A1/C, не утверждать их невозможность.",
      "status": "VALIDATED",
      "evidence_ids": [
        "EVD-024",
        "EVD-025"
      ]
    },
    {
      "id": "ASM-007",
      "class": "continuable",
      "source_open_ids": "OPEN-17",
      "statement": "Реальная deploy identity и DSH live acceptance — отдельный rollout шаг после clean-room, не требование доступа к ~/.dsh в VER.",
      "status": "ASSUMED",
      "evidence_ids": [
        "EVD-034",
        "EVD-058",
        "EVD-059"
      ]
    }
  ],
  "drivers": [
    "RC-1: run CLI буферизует reasoning до ended (F-17/F-18)",
    "RC-2: многоэтапные deadline и очистка вместо 780–856 с тишины",
    "RC-3: DSH видимость по непустому reasoning_content и завершённому абзацу",
    "REQ-002/003: стабильный OpenAI контракт и 17 legacy test modules",
    "REQ-012/013/015: запрет built-ins, per-spawn proxy rotation и секреты"
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-005",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-013",
        "REQ-014",
        "REQ-017",
        "REQ-018"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; 0 failed во всех существующих 17 модулях + dedicated suite; 3 baseline tests исправлены, production cap=3",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": [
        "REQ-002",
        "REQ-003",
        "REQ-011",
        "REQ-017"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && python3 -m unittest discover -s tests -p \"test_*.py\"",
      "expected": "exit 0; 0 failures/errors, запуск из bridge cwd (не из repo root), все новые tests используют unittest.TestCase или stdlib-compatible helper",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": [
        "REQ-002",
        "REQ-018"
      ],
      "kind": "command",
      "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/",
      "expected": "exit 0; root cross-bridge regression без живых owner ресурсов; environment-specific skips разрешены только унаследованные",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-004",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-017"
      ],
      "kind": "command",
      "command": "python3 - <<'VER004'\nimport collections, json, subprocess\ns=\"bridges/opencode-zen-bridge/server.py\"\nt=\"bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py\"\nr=subprocess.run([\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"check\",\"--no-cache\",\"--output-format=json\",s,t],capture_output=True,text=True)\nassert r.returncode in (0,1), r.stderr\nrd=json.loads(r.stdout)\nfrom pathlib import Path\nassert all(\"import zen_catalog\" in Path(s).read_text().splitlines()[x[\"location\"][\"row\"]-1] for x in rd), rd\nassert all(x[\"code\"]==\"E402\" and x[\"filename\"].endswith(\"/\"+s) and x[\"message\"]==\"Module level import not at top of file\" for x in rd) and len(rd)<=1, rd\nb=subprocess.run([\"uvx\",\"--from\",\"basedpyright==1.40.2\",\"basedpyright\",\"--outputjson\",s],capture_output=True,text=True)\nassert b.returncode in (0,1), b.stderr\nbd=json.loads(b.stdout); ds=bd[\"generalDiagnostics\"]\nallowed={\"reportImplicitRelativeImport\":\"zen_catalog\", \"reportConstantRedefinition\":\"CATALOG_SOURCE\"}\nerrs=[x for x in ds if x[\"severity\"]==\"error\"]\nassert all(x.get(\"rule\") in allowed and allowed[x[\"rule\"]] in x[\"message\"] for x in errs), errs\nassert all(n<=1 for n in collections.Counter(x[\"rule\"] for x in errs).values()), errs\nlimits={\"reportExplicitAny\":125,\"reportAny\":125,\"reportUnusedCallResult\":39,\"reportUnknownMemberType\":70,\"reportUnknownVariableType\":48,\"reportUnknownArgumentType\":35,\"reportUnusedFunction\":2,\"reportImplicitStringConcatenation\":27,\"reportUnannotatedClassAttribute\":81,\"reportUnusedParameter\":3,\"reportUnnecessaryIsInstance\":3,\"reportUnknownParameterType\":2,\"reportMissingParameterType\":2,\"reportUnreachable\":1,\"reportImplicitOverride\":1}\ncounts=collections.Counter(x.get(\"rule\",\"\") for x in ds if x[\"severity\"]==\"warning\")\nassert all(n<=limits.get(k,0) for k,n in counts.items()), counts\nprint(\"PASS baseline-aware VER-004; ruff inherited<=1 E402; pyright inherited<=2 errors; warnings within frozen per-rule budgets\",dict(counts))\nVER004",
      "expected": "exit 0 baseline overlay; новые lint/type errors запрещены. Это budget gate для существующего typed debt, НЕ заявление о полном чистом basedpyright. Legacy E402 разрешён только на zen_catalog import; 2 pyright error sites строго только указанные; warning rule budgets не растут.",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    },
    {
      "id": "VER-005",
      "requirement_ids": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-004",
        "REQ-005",
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-010",
        "REQ-011",
        "REQ-012",
        "REQ-013",
        "REQ-014",
        "REQ-015",
        "REQ-016",
        "REQ-017",
        "REQ-019",
        "REQ-020"
      ],
      "kind": "command",
      "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
      "expected": "exit 0; полный FakeServe v2 SSE, timing до конца upstream, grace/status, 3 watchdog, cancellation/PGID, fallback, pure reasoning, tools, 46 envelope fields + 21 stop-code/lifecycle invariants",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как получить настоящие reasoning/text delta и сохранить обратимый legacy-путь?",
      "choice": "Option C с A1 primary: один короткоживущий serve v2 на попытку, HTTP+SSE, run fallback только до отправки prompt; единый canonical event source для stream=True и stream=False.",
      "alternatives": [
        "A2: общий daemon — дешевле холодного старта, но единый env/IP и failure domain, риск лимита F-15/OPEN-06.",
        "B: прямой HTTP Zen — меньше ресурсов, но 429 F-24/F-25 и нет подтверждённого client context; не выбирается без PoC.",
        "L: только run watchdog/status — минимален, но не устраняет RC-1."
      ],
      "drivers": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-012",
        "REQ-013",
        "REQ-014",
        "F-19/F-20: 109 ms server start, 127/114 ms delta medians"
      ],
      "consequences": [
        "Дополнительные SSE/control sockets и lifecycle; предел активных детей не увеличивается.",
        "run-откат теряет realtime; это видимая деградация, не доказательство REQ-001.",
        "Откат флага/режима без миграций; публичная форма ответов неизменна."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-015",
        "EVD-017",
        "EVD-018",
        "EVD-019",
        "EVD-020",
        "EVD-021",
        "EVD-022",
        "EVD-024",
        "EVD-025",
        "EVD-040",
        "EVD-050",
        "EVD-051"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "configuration": {
          "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": {
            "default": false,
            "purpose": "без явного включения выполняется только run; первые инструкции optional serve-path проверяют флаг"
          },
          "OPENCODE_ZEN_BRIDGE_TRANSPORT": {
            "values": [
              "auto",
              "serve",
              "run"
            ],
            "default": "auto",
            "precedence": "TRANSPORT=run или REALTIME_SERVE_ENABLED=false -> run. true+auto -> безопасный eligibility-check, потом serve или run. true+serve -> force serve, ошибки capability/readiness явные без silent run fallback. Неизвестное значение -> ошибка конфигурации до bind."
          },
          "feature_flag_context": "Локальный stdlib-мост без gc_pytools/dynamic_config/GigaRC, как зафиксировано в эталоне. Не добавлять GigaRC/dependency/env propagation в другие системы; текущий бриф явно разрешает transport/env kill-switch. Новая ветвь default=false."
        },
        "auto_fake_compatibility": "В auto НЕ запускать --help/--version/serve ради probe на произвольном OPENCODE_BIN. После O(1) флага прочитать первые байты resolved executable и stat: shebang/текстовый launcher -> run без subprocess-пробы. Это покрывает все текущие fake scripts (включая basename opencode). Иначе bind/serve v2 handshake под readiness ceiling. Eligibility кэшируется по resolved path+mtime_ns+size, без смены глобальной модели/тестовых env. Force serve намеренно обходит shebang-фильтр для FakeServe; fake tests задают flag=true, mode=serve. Никакого распознавания по FAKE_OC_MODE/имени теста. Защита test_step counter: fallback не должен запускать fake CLI лишний раз. При flag=false любые legacy test-фикстуры остаются на run с прежним counter.",
        "spawn": "Перед КАЖДЫМ реальным Popen: общий _RequestAttempts/slot, spawn_limiter, _StartupGate, свежий _run_env(model_id) и _next_standalone_proxy. serve argv [launcher, serve, --hostname, 127.0.0.1, --port, ephemeral]; stdin=DEVNULL (EOF немедленно), start_new_session=True. Не передавать prompt argv/stdin serve. OS выбирает loopback port; если API не даёт port=0 адрес, reserve-bind(0), release, spawn с ограниченным retry race; не считать чужой listener своим.",
        "startup": "SERVE_READY_TIMEOUT_S=0.50: bounded local connect/openapi handshake, общий monotonic deadline; control socket slices <=0.25 s. Разрешён только authenticated v2 OpenAPI/event/session shape. Child EOF/unsupported serve/нет HTTP listener/несовместимый protocol -> ServeUnavailable. stdin=DEVNULL предотвращает stdin hang даже для force serve с legacy fake; exit/EOF проверяются сразу, без 5 s ожидания. stdout/stderr дренируются ограниченно и маскируются до лога. Пароль криптографически случайный per spawn, OPENCODE_SERVER_PASSWORD добавляется ПОСЛЕ whitelist, Basic opencode:<password>, никогда не в argv/URL/логе. Loopback http.client connection идёт напрямую, без env proxy и redirects.",
        "fallback_barrier": "Auto fallback разрешён только если prompt POST ещё НЕ НАЧАТ, нет model output/tool action, нет client_gone и security/auth failure. До fallback полностью interrupt/delete (если session создана), close socket, killpg/reap предыдущий serve. ServeUnavailable capability не считается ошибкой модели и не увеличивает breaker; фактический serve Popen всё равно расходует MAX_TOTAL_SPAWNS и токен spawn. Следующий run Popen требует общий attempts.allow_retry, _RetryBudget и Full Jitter, не может дать 4-й spawn. При исчезновении клиента fallback запрещён. HTTP 401/403, неожиданный auth/permission response -> fail-closed, никакого ослабления policy через run. Начиная с попытки отправки prompt (даже timeout с неизвестной доставкой) silent fallback запрещён; штатный transient retry возможен только в общей state machine и после cleanup, с явным retry-status.",
        "session_flow": "Сначала authenticate/readiness и deny-policy, затем POST /api/session(model с тем же provider/model#variant согласно v2 schema, location=текущий workdir, permissions); открыть и подтвердить подписку GET /api/event ДО POST /api/session/{id}/prompt с полным text. Отфильтровывать события только current session/execution; не выдавать чужую историю/старые события. Не вызывать generate или prompt повторно при timeout. Terminal success/failed — независимый сигнал полноты; EOF без terminal -> transport failure. На step.ended с DSH tool call прекратить дальнейшие шаги, interrupt/delete и cleanup.",
        "tool_policy": "Основная безопасная конфигурация — scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"deny\"} плюс deny-all session permissions; merge сохраняет provider/options, не пишет общий конфиг. F-50: deny может убрать tool schemas и вызвать Zen 403. Эквивалентная разрешённая изоляция для такого несовместимого клиента: permission=ask, session permission request -> немедленный API reply reject (никогда allow), пока prompt не начат подтверждены permission endpoints. При отсутствии безопасной deny/ask-auto-reject capability — fail-closed, не выполнять инструменты. Не переключать политику на лету после provider 403. Выбор совместимой policy проверяется FakeServe, а исполнение реально запрещено H6 перед rollout. События session.tool.* нормализуются в native mapping даже если denied: native/unmapped handling как legacy.",
        "event_contract": {
          "shape": "Iterator[tuple[str, dict]]; единая семантика событий в Handler._stream_sse и Run._execute_once (через _serve_json). Legacy parse_opencode_event сохранён, normalize boundary обеспечивает raw part для tool_use; forbidden: копировать все retry loops в новый transport.",
          "session.reasoning.delta": "(\"reasoning\", {reasoning_content: delta}); только delta bytes, ended не повторяет полный текст; reasoningEncryptedContent сохраняется reasoning_details через существующий mapping.",
          "session.text.delta": "(\"text\", {content: delta}) -> тот же ToolCallParser.feed или emit_content.",
          "session.step.ended": "(\"step_finish\", tokens с input/output/cached/reasoning), ровно один учёт по step id, не удваивать usage на execution terminal.",
          "session.tool.*": "(\"tool_use\", {part:{tool, state:{input,status}}, call_id}); адаптер legacy тоже вкладывает тот же canonical part; оба потребителя берут part из normalized payload. Стабильный call_id не допускает повторного DSH вызова на started/updated/ended одного инструмента. Допустим raw-event envelope внутри adapter для старых потребителей, но неизвестный tool type не игнорируется.",
          "session.step.failed / session.execution.failed": "(\"error\", {statusCode,message}) через существующий classifier; не удваивать одну failure cause.",
          "session.execution.succeeded": "terminal success metadata, не text/reasoning; гарантированно дренировать уже полученный step.ended перед финальным usage.",
          "other": "started/connected/lifecycle -> транспортные служебные события для first-event, не model token; unknown control events не исполняют actions.",
          "payload_validation": "Использовать v2 schema и фактические F-19/F-22 fixtures. Не угадывать field aliases по строке event name. SSE assembler поддерживает UTF-8 через incremental decoder, CRLF, multi-line data, comments и fragment boundaries; delta/ended сверяются на tool/reasoning/text fixtures. Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test до runtime enabling."
        },
        "non_stream": "serve используется и stream=False через общий source; Run копит чистые model reasoning/text/native/usage как сейчас. Synthetic [мост] статусы — только SSE presentation, в JSON reasoning_content не добавляются. Google direct dispatch остаётся первым и не создаёт serve/новые timers."
      }
    },
    {
      "id": "AD-002",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как дать DSH видимость <1 s без изменения быстрых reasoning-ответов?",
      "choice": "Один SSE-writer с grace=0.30 s и отдельными status delta, завершающимися newline; модельные дельты не дополняются переводами строк.",
      "alternatives": [
        "Безусловный status t=0 — надёжен для Think, но ломает точное Simple greeting. и добавляет синтетику в быстрый ответ.",
        "Пустой keepalive/HTTP comment — не включает blockIsVisible и не обновляет collapsed preview (F-36/37).",
        "Вставлять newline в каждую model delta — превью чаще, но нарушает AC-006 и журнал."
      ],
      "drivers": [
        "REQ-004",
        "REQ-005",
        "AC-005",
        "AC-006",
        "EVD-051"
      ],
      "consequences": [
        "Первый status появляется только на медленном старте. Реальные delta с естественными абзацами обновляют collapsed summary.",
        "Non-thinking/off запросы не получают искусственного thinking; проверяется отдельно.",
        "DSH хранит bridge statuses в reasoning; replay их игнорирует, как весь reasoning_content."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-007",
        "EVD-036",
        "EVD-037",
        "EVD-038",
        "EVD-039",
        "EVD-051"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "timer_anchor": "t_sse_open — flush первого role chunk. FIRST_STATUS_DELAY_S=0.30; тик writer <=0.05..0.10 s. Background setup/adapter НЕ блокирует writer на gate.acquire, rate wait, connect, POST prompt или join. Ровно один поток пишет self.wfile; worker передаёт события через bounded queue. Никаких независимых Timer-writers в wfile.",
        "eligibility": "Только non-Google SSE с effective thinking/reasoning включённым (effort непустой; default high считается включённым). Явные off/none из _map_effort исключают synthetic reasoning даже при долгом запуске. Это явное сужение AC-005: оно относится к thinking-enabled DSH, а fast-answer/off сохраняет текущий contract. Модельные reasoning, если пришли от upstream, не выдумывать/не подменять.",
        "initial": "На t>=0.30 при отсутствии уже ОТПРАВЛЕННОЙ непустой real reasoning_content/content delta и незавершённом запросе отправить {reasoning_content:\"[мост] Подключение к модели…\\n\"} с реальным LF, flush. Пробелы и empty keepalive не считаются real progress. При доступной real delta в том же тике сначала обработать очередь, затем проверить grace: fast fake <50ms не получает prefix. Если real text пришёл раньше grace, initial status не нужен — ответ уже видим. Если real reasoning пришёл раньше grace, Think видим без synthetic prefix; отсутствие LF в быстром Simple greeting. не даёт права мутировать текст.",
        "lifecycle": "Startup-gate/spawn wait статусы только после grace при фактическом ожидании, без немедленного prefix на быстром acquire. До первого real token при тишине heartbeat каждые 5.0 s: [мост] Ожидание первого токена (N с)… + LF. После real progress и затем настоящего stall можно каждые 5 s дать [мост] Ожидание продолжения… + LF. Статусы не сбрасывают transport/model watchdog timestamps и сами не считаются attempt_output. Нормальные 127 ms reasoning delta не сопровождаются heartbeat.",
        "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning.",
        "pure_reasoning": "Склейка model-origin delta равна upstream model bytes после унаследованной очистки известных interrupted artifacts; не добавлять LF для preview, пробелы и UTF-8 не переписывать. _strip_interrupted должен оставаться chunk-boundary-safe: распознанный interrupted marker удерживается/удаляется инкрементально, partial prefix не протекает; обычный текст не нормализуется. В тестах удалять synthetic delta по provenance/expected list, а не слепо вырезать любую модельную строку [мост].",
        "regression": "test_interrupted_artifact_removed_from_reasoning_stream: быстрая последовательность marker + Simple greeting. -> exactly Simple greeting., один run, zero status. В JSON тоже exactly. Slow FakeServe: first status <=1.0 s при заблокированном upstream; visible(text.strip) true, latestCompletedParagraphFirstLine получает завершённый LF. Natural reasoning LF обновляет collapsed row, bytes неизменны.",
        "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt."
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как ограничить тишину, быстро отменить запрос и не оставить дочерние процессы?",
      "choice": "Единый monotonic supervisor обоих транспортов с разными clocks first-event/first-token/stall, отменой на всех ожиданиях и идемпотентным group cleanup.",
      "alternatives": [
        "Только TIMEOUT_S=1800 — сохраняет многоминутный инцидент RC-2.",
        "Watchdog stdout.read/15 s keepalive без socket-check — пропускает зависание после стартового события и поздно видит disconnect.",
        "Убивать только leader proc.kill — оставляет serve/grandchildren и забытые sockets."
      ],
      "drivers": [
        "REQ-006",
        "REQ-007",
        "REQ-008",
        "REQ-009",
        "REQ-016",
        "T-LIFE/v1"
      ],
      "consequences": [
        "Несколько инъектируемых clocks/state, строгий единый writer и owned worker.",
        "Ретраи после частичного вывода могут повторить reasoning; граница отмечается status.",
        "Новые timeout exits транзиентные, budgets/потолки не расширяются."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-009",
        "EVD-010",
        "EVD-011",
        "EVD-014",
        "EVD-030",
        "EVD-033",
        "EVD-055",
        "EVD-061"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "thresholds": {
          "FIRST_EVENT_TIMEOUT_S": 20.0,
          "FIRST_TOKEN_TIMEOUT_S": 60.0,
          "STALL_TIMEOUT_S": 60.0,
          "env_prefix": "OPENCODE_ZEN_BRIDGE_",
          "validation": "положительное finite число; недопустимое -> ошибка старта, не бесконечный timeout"
        },
        "clocks": "watchdog attempt_start сразу перед gate/startup, поэтому gate/readiness не создаёт неучтённой тишины. first_event — первый валидный transport/server event (legacy step_start или validated serve readiness/SSE event), а не байт stderr/whitespace/comment/status мостa; clock одноразовый, поздние heartbeat его не продлевают. first_token — первый non-whitespace model reasoning/text/native tool intent, не encrypted-only/started/bridge status. stall запускается после first_token и обновляется только non-whitespace model delta/полезным tool event. Empty SSE ping и служебный шум не оживляют token/stall. Пределы проверять до/после каждой операции; total deadline неизменен на всех attempts.",
        "disconnect": "На каждой итерации/ожидании <=0.25 s проверять cancel flag и client socket select + recv(MSG_PEEK|MSG_DONTWAIT): EOF/ECONNRESET -> client_gone без чтения данных и без переключения wfile в nonblocking. Реальная bounded empty OpenAI keepalive каждые <=2.0 s тишины страхует разрыв, который TCP ещё не сигнализировал; write deadline <=0.5 s, без write на отдельном потоке. Poll, status, write и cleanup не блокируют supervisor на 15/5 s. Суммарное обнаружение контролируемого FIN/RST <=5.0 s. Полное исчезновение сети без FIN нельзя доказать одним MSG_PEEK — bounded write/OS transport timeout и fault injection отдельно, не обещать физически невозможный мгновенный детект blackhole.",
        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent.",
        "retry": "first_event_timeout/first_token_timeout/stall_timeout -> transient failure; после cleanup retry admission в _RequestAttempts, FAIL_RETRY_LIMIT и MAX_TOTAL_SPAWNS=3 без отдельного transport budget. _RetryBudget расходуется как provider retry; watchdog не выдавать за budget-free local sqlite error. Full Jitter min(cap=2,base=.5*2**retry), ограниченный remaining deadline. Sleep/pool/gate/rate waits cancellation-aware, poll<=.25; один slot удерживается на весь запрос и release exactly once в finally. failed last request -> breaker failure, recovered request -> success как текущий commit; HALF_OPEN не выдаёт лишнюю пробу. client_gone/deterministic 4xx/security denial -> без retry/fallback. HALF_OPEN проба имеет owner token до завершения/подтверждённого cleanup; никакой повторной живой пробы только из-за reset_s. FakeClock test активной пробы дольше cooldown обязателен, neutral client cancel не оставляет вечной занятости.",
        "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки."
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как сохранить инструменты/recovery на мелких дельтах и исправить baseline без ослабления защиты?",
      "choice": "Переиспользовать инкрементальный ToolCallParser и существующий recovery, обеспечить canonical native payload; исправить только несовместимые тестовые ожидания и изоляцию.",
      "alternatives": [
        "Копить всё до ended — легче parser/recovery, но вновь ломает realtime RC-1.",
        "Новый regex-parser на каждом delta — теряет разрезанные теги/JSON/UTF-8 и дублирует контракт.",
        "Поднять MAX_TOTAL_SPAWNS до 4 или отключить RetryBudget — скрывает baseline mismatch и нарушает REQ-009."
      ],
      "drivers": [
        "REQ-010",
        "REQ-011",
        "REQ-017",
        "AC-015",
        "AC-016",
        "F-47/F-48/F-49"
      ],
      "consequences": [
        "Минимальное изменение тестов без изменения production limits.",
        "Parser history/open block требует bounded memory; overflow — явный отказ, не silent drop.",
        "Перенос interrupted/step-failure проверок на fake v2 снижает риск transport-specific regressions."
      ],
      "approval_required": false,
      "evidence_ids": [
        "EVD-006",
        "EVD-043",
        "EVD-045",
        "EVD-047",
        "EVD-048",
        "EVD-049",
        "EVD-051",
        "EVD-057"
      ],
      "confirmation": {
        "kind": "test",
        "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
        "expected": "exit 0; dedicated negative/boundary/fake-transport assertions, плюс VER-001/002 green без расширения потолков"
      },
      "verification_ids": [
        "VER-001",
        "VER-005"
      ],
      "details": {
        "parser": "Каждый session.text.delta -> тот же parser.feed без промежуточного whole-step buffer. Outside genuine tool blocks удерживается только pending opener prefix <=max(len(<tool_call>),len(<tool_invoke>))-1=12 chars плюс нужный существующему code-context lookahead; open block удерживается до валидного close, JSON close внутри строки не закрывает блок. Genuine/unparsed/incomplete tool tags не попадают в delta.content: callbacks через _strip_broken_tool_blocks и chunk-safe finish; существующие намеренно цитированные теги в Markdown остаются документационным текстом по текущим parser fixtures (не выполнять их). Инвариант по всем split points и single-character chunks. Open-block/total-output/frame bounds проверяются отдельно, overflow -> explicit error+cleanup.",
        "step": "Accumulated raw text/reasoning/native + step.ended tokens -> _is_incomplete_tool_step/_incomplete_step_signal и _is_transient_stream_error. При step.ended с готовым вызовом немедленно завершить upstream, finish_reason=tool_calls; не пропускать SYNTHETIC Continue. Error до первого model output допускает bounded recovery upstream как legacy; поздняя transient error прерывает attempt, fatal 400/401/403/404/422 без retry. Bridge status не изменяет attempt_output/first_token/had_error. _strip_interrupted и _strip_broken_tool_blocks работают независимо от границ delta.",
        "baseline_tests": "В TestStepInterruptionLive.setUp заменить self.httpd.resilience на новый _Resilience (либо новый _RetryBudget с инъектируемыми часами + reset breaker/limiter), только когда прошлый request завершён, тесты класса последовательны. Ничего не сбрасывать в prod. В двух unmapped_retries_do_not_exhaust_incomplete_budget_{json,stream} оставить текущую fixture: первые 2 попытки unmapped, третья status/promise, 4-я запрещена. Ожидать runs==3, отсутствие tool_calls, finish_reason=stop, status/prelude ровно один раз; не ждать job_output/bash с несуществующего 4-го spawn. Добавить отдельный reachable<=3 сценарий unmapped -> incomplete -> calls и/или unit-oracle независимости счётчиков. Test_unmapped_then_error_stops_proc_json ожидает 2 и не зависит от предыдущих токенов бюджета. Все 17 legacy modules плюс новые tests green; production MAX_TOTAL_SPAWNS=3 не меняется.",
        "red_green": "Сначала dedicated tests на текущем коде: реальный socket read до release upstream Event, slow initial status, watchdog/cleanup и native delta split. Зафиксировать red (не import error), после Stage 3 green в VER-005 и полном VER-001/002. Stage 2 тестовый код не пишет и зелёное выполнение этой будущей поверхности не заявляет."
      }
    }
  ],
  "quality_scenarios": [
    {
      "id": "QA-001",
      "quality": "performance",
      "source": "DSH client",
      "stimulus": "upstream выпускает каждые150ms 10 reasoning delta и держит stream open",
      "environment": "здоровый FakeServe/локальный socket",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "writer flush до upstream terminal",
      "response_measure": "10 чанков получены до release Event; interarrival<500ms; bridge delay<=250ms",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-002",
      "quality": "usability",
      "source": "DSH thinking-enabled client",
      "stimulus": "cold start молчит/ждёт gate",
      "environment": "медленный upstream",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "grace status с LF, потом lifecycle status",
      "response_measure": "first visible<=1.0s, grace=.30s, без статусов на fast fake и off",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-003",
      "quality": "compatibility",
      "source": "legacy fake CLI",
      "stimulus": "fake script игнорирует argv и блокируется на stdin.read",
      "environment": "auto/default flag disabled либо auto shebang",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "один run без serve probe, reasoning exact Simple greeting.",
      "response_measure": "all17 modules green; runs==1, no synthetic prefix для fast fixture",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "upstream",
      "stimulus": "no event/no token/stall",
      "environment": "управляемые clocks/Events и hard silence",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "watchdog classification+bounded retry",
      "response_measure": "20/60/60 config, scaled tests, timeout+2s cleanup и spawns<=3",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-005",
      "quality": "reliability",
      "source": "DSH Stop/FIN",
      "stimulus": "отключение при gate/read/prompt/дельтах",
      "environment": "активные children/grandchildren",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "cancel->close->killpg->reap",
      "response_measure": "detect<=5s, orphan-free<=7s, slots/readers/sockets0",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-006",
      "quality": "security",
      "source": "модель/враждебный upstream",
      "stimulus": "native tools пытаются писать файл или запросить allow",
      "environment": "serve Basic loopback и deny/ask-reject",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "никогда allow, native event -> DSH tool tuple",
      "response_measure": "fake permission requests reject; false flag no secret allocation; live H6 отдельно",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-007",
      "quality": "operability",
      "source": "оператор",
      "stimulus": "любая terminal/early exit/успешный retry",
      "environment": "SSE или JSON, valid/malformed request",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "одна O-EXIT/v1 строка без secrets",
      "response_measure": "transport/first_event_ms/ttft_ms/exit_reason присутствуют; null не подделывается0",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-008",
      "quality": "testability",
      "source": "clean-room verifier",
      "stimulus": "clone не содержит ~/.dsh и новый transport fake",
      "environment": "Python>=3.11 stdlib tests",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "каждый VER полностью воспроизводим",
      "response_measure": "VER001..005 exit0 после Stage3, без owner home и Zen calls",
      "verification_ids": [
        "VER-001",
        "VER-002",
        "VER-003",
        "VER-004",
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    },
    {
      "id": "QA-009",
      "quality": "cost",
      "source": "6 parallel requests",
      "stimulus": "103KB prompt и fragmented output",
      "environment": "design envelope single-process",
      "artifact": "bridges/opencode-zen-bridge/server.py",
      "response": "resource manager bounds and overload",
      "response_measure": "memory1408<=1638.4MiB estimate; byte queue/FD/port and maxchild assertions",
      "verification_ids": [
        "VER-005"
      ],
      "analyst_qa_ref": "analysis/zen-realtime-reasoning/handoff-qa.md (QA IDs там отдельный исходный namespace)"
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "Handler._stream_sse / Handler._serve_json",
      "responsibility": "OpenAI framing/один SSE writer; display-status только stream; _serve_json сохраняет model output без synthetic status",
      "allowed_dependencies": [
        "common canonical source",
        "pure tool/recovery helpers",
        "per-Server resource manager"
      ],
      "forbidden_dependencies": [
        "DSH bundle/config writes",
        "raw serve events в public ответе",
        "новые Google behavior"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-002",
      "component": "managed serve/run source + per-Server resource manager",
      "responsibility": "Transport selection/auth, fresh env/proxy, bounded queue, lifecycle/PGID ownership и canonical event tuples",
      "allowed_dependencies": [
        "stdlib http.client/socket/subprocess/queue/threading/secrets",
        "_run_env/_RequestAttempts/_StartupGate",
        "pure event adapter"
      ],
      "forbidden_dependencies": [
        "wfile/client content writes",
        "внешние Python dependencies",
        "shared daemon/общий opencode config/db writes"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-003",
      "component": "ToolCallParser / recovery / normalize boundary",
      "responsibility": "Чистое инкрементальное преобразование text/native/events и interruption-safe accumulated reasoning",
      "allowed_dependencies": [
        "compiled regex/stdlib json",
        "tools клиента и primitive event payload"
      ],
      "forbidden_dependencies": [
        "network/process access",
        "global retry resets",
        "модификация model bytes для UI"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "BND-004",
      "component": "_Resilience/_RequestAttempts",
      "responsibility": "Один process-level bulkhead, rate/retry budget/breaker; per-request spawn count и deadlines",
      "allowed_dependencies": [
        "injected monotonic/RNG",
        "locks"
      ],
      "forbidden_dependencies": [
        "new independent transport retry budget",
        "production budget reset between requests",
        "cross-provider fallback"
      ],
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "bridge SSE presentation",
      "consumer": "DSH OpenAI completion reader",
      "change": "Grace=.30s synthetic [мост] status delta с LF для thinking-enabled slow/retry lifecycle; fast/off/JSON не получают prefix. Разрешено текущим Brief AD-002 и REQ-004/005.",
      "compatibility": "OpenAI chunk shape/finish/usage unchanged; no unconditional t0 status; user fast exact reasoning equality preserved. REQ004 scoped to thinking-enabled, real content раньше grace уже видим.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "CD-002",
      "type": "behavior",
      "producer": "transport supervisor",
      "consumer": "OpenAI caller and O-EXIT logs",
      "change": "Конечные first_event/first_token/stall deadlines и fast cancellation с error той же формы; telemetry fields и exit reasons по REQ006..009/016. Для нового enabled serve path byte-bound explicit overflow, без silent loss.",
      "compatibility": "Endpoints/status/error schema и Google path unchanged; многоминутная тишина намеренно прекращается; kill-switch отключает новый serve, watchdog/status для legacy остаются исправлением RC2/RC3.",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "context",
      "question": "Кто общается с мостом и какая граница остаётся внешней?",
      "artifact_ref": "architecture/architecture-packet.json#scope + boundaries BND-001; F-35"
    },
    {
      "id": "VIEW-002",
      "type": "container",
      "question": "Какие processes/sockets являются изолированным failure domain?",
      "artifact_ref": "architecture/architecture-packet.json#AD-001.details.spawn/session_flow + high_load_envelope.operational_profile"
    },
    {
      "id": "VIEW-003",
      "type": "dynamic",
      "question": "Как status/watchdog продолжают работать во время setup/retry/молчания?",
      "artifact_ref": "architecture/architecture-packet.json#AD-002/003.details + resilience_gates.dependency_failure_matrix"
    },
    {
      "id": "VIEW-004",
      "type": "dfd",
      "question": "Где проходят auth/secret/tool-action trust boundaries?",
      "artifact_ref": "architecture/architecture-packet.json#threat_model + AD-001.details.tool_policy/fallback_barrier"
    }
  ],
  "risks": [
    {
      "id": "RISK-001",
      "scenario": "deny удаляет tool schema, Zen403 или ask непреднамеренно исполняет tool",
      "probability": "high",
      "impact": "high",
      "mitigation": "Scoped deny baseline; если несовместим, заранее выбранный ask-auto-reject, никогда allow. Capability/permission failure fail-closed. FakeServe доказывает reject/mapping, live H6 требуется перед rollout.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-002",
      "scenario": "Proxy env не означает фактическую per-request clean IP ротацию через loopback georouter",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Сохранить _run_env на каждый child, test env calls/sequence; OPEN06 реальный egress/H3 нужно подтвердить. Shared daemon не использовать; тест env не объявлять доказательством clean IP.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-003",
      "scenario": "6 serve на sqlite2.27GB/192MiB оценке создают lock/memory spike",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Startup gate/rate+bounded6, output/queue budgets, memory1408MiB; cleanup retries. H3 RSS/FD/DB locks mandatory before enabling.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-004",
      "scenario": "Fast fake probe увеличит run counter или блокируется stdin",
      "probability": "high",
      "impact": "high",
      "mitigation": "auto shebang route directly run zero probes; force serve DEVNULL + .5s ready ceiling; cached stat key. Regress exact1run and no5s hang.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-005",
      "scenario": "Расщеплённые marker/tool/UTF8 или ended duplicate искажают reasoning/usage",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Canonical delta-only assembler, incremental scrubber, all split points, step-id dedup/native-call-id dedup; end barrier independent terminal.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-006",
      "scenario": "Корректный early-error upstream сам восстанавливается, но bridge status пометит had_output",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Status provenance отдельно от model counters, no had_output/clock reset; exact legacy early_error tests + FakeServe variant.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-007",
      "scenario": "Квота Zen/103KB TTFT/DSH rendering пока не проверены",
      "probability": "high",
      "impact": "high",
      "mitigation": "F23 observation может устареть; не утверждать текущую квоту, H0..H9 live acceptance после rollout. FakeSuite не заменяет UI/реальный egress.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-008",
      "scenario": "Полный lint/type gate красный до изменения",
      "probability": "high",
      "impact": "medium",
      "mitigation": "VER004 baseline-aware точные old error sites + warning per-rule budgets; не расширять allowance и не считать budget green чистым typing. Новый test file полный ruff.",
      "verification_ids": [
        "VER-004"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Prompt POST timeout уже после принятия способен удвоить generation при silent fallback",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Fallback barrier before first prompt send; after ambiguous acceptance только общий explicit transient retry с cleanup, status и cap; builtins cannot run.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    },
    {
      "id": "RISK-010",
      "scenario": "SIGTERM/leader exit оставляет descendant, старый cleanup ждёт15+5с",
      "probability": "high",
      "impact": "high",
      "mitigation": "PGID сохранён при spawn, group kill даже leader exited, cleanup bounded1.2s; собственный lifecycle реестр, никакого pkill; finally every branch.",
      "verification_ids": [
        "VER-001",
        "VER-005"
      ]
    }
  ],
  "threat_model": {
    "required": true,
    "assets": [
      "промпт и история владельца",
      "ключ моста, пароль serve и proxy credentials",
      "локальные файлы и процессы",
      "квота Zen и ресурсы станции"
    ],
    "trust_boundaries": [
      "DSH -> bridge OpenAI HTTP (auth без изменений)",
      "bridge -> одноразовый loopback serve Basic Auth",
      "serve -> georouter/Zen через унаследованный per-spawn env",
      "модель -> запрос инструмента: исполнение только в DSH"
    ],
    "threats": [
      {
        "id": "THREAT-001",
        "scenario": "Подмена локального serve listener/вывод случайного пароля в stdout",
        "mitigation": "Loopback127.0.0.1, generated password env before spawn, v2 handshake authenticated+no redirects, own process lifecycle. Не логировать Basic/header/body/raw stdout; всё маскируется перед log.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "Модель выдаёт builtin bash/write/edit, пока DSH думает, что это только предложение",
        "mitigation": "deny-all или ask+API immediate reject, never allow; unknown permission capability fail-closed. Native события только переводятся в DSH tool_calls/unmapped. Live H6 доказывает no file mutation.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Unrestricted parent env утекает в serve или proxy creds в ошибку",
        "mitigation": "_run_env whitelist как legacy, password добавляется только child env; no apiKey dump, redact stdout/stderr/exception before _log and response; тест secret sentinels.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "SSE из чужой session или reconnect replay приводит к чужому выводу/повтору инструмента",
        "mitigation": "Filter exact session/execution IDs, subscribe before prompt; no transparent reconnect replay после prompt; step/call IDs dedup; no raw events in public stream.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-005",
        "scenario": "Отмена клиента/oversized frame держит процессы и позволяет resource exhaustion",
        "mitigation": "bounded byte queue/frame/output and slots/waiters, finite per-operation deadlines, own PGID forced cleanup, zero orphan tests; output overflow не дропается молча.",
        "verification_ids": [
          "VER-005"
        ]
      }
    ]
  },
  "evolution": {
    "compatibility": "OpenAI endpoints/port/auth/format/Google route preserved; canonical source powers stream and JSON. Serve default-disabled, auto text scripts direct run. New statuses scoped thinking+grace; legacy pure fast reasoning unaffected.",
    "migration": "NOT_APPLICABLE: нет data schema/DB миграций и новых dependencies; opencode.db/shared config не менять. Each ephemeral session DELETE в cleanup; session history child creates via штатный API, prompt retention унаследован OpenCode, не выгружать в артефакты.",
    "rollout": "Stage2 validators+fingerprint -> downstream external architecture panel/proof (orchestrator) -> Stage3 tests red→green/code -> independent clean-room VER001..005 all green -> отдельный deploy/sync H0 -> canary enable flag=true auto и H1..H9. 103KB+6parallel×3, DSH Think screenshots/Stop, H6 запрещённая запись, egress proxy/RSS/FD. Пока это не пройдено, business result не сдан. Ничего из ~/.dsh не входит в clean-room VER.",
    "rollback": "REALTIME_SERVE_ENABLED=false либо TRANSPORT=run и контролируемый restart конфигурации возвращают legacy transport; сначала отменить active leases, zero orphans, no daemon overlap. Watchdog/status fixes остаются. Если они дали регресс — revert Stage3 commit и сверить копии H0, live legacy H9. В Stage2 rollback/deploy не выполняется.",
    "feature_flag": "Env switch вместо GigaRC в конкретном локальном stdlib контуре явно разрешён текущим брифом и имеет default=false; нельзя выдавать его за удалённый GigaRC без рестарта."
  },
  "approval": {
    "status": "NOT_REQUIRED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": null,
    "rationale": "Все AD two-way и следуют текущему брифу; публичный auth/контракт/данные не меняются. APPROVED ниже означает валидированный архитектурный контракт, не голос Совета."
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2. Независимый downstream architecture panel остаётся обязанностью оркестратора; здесь не запускается и не подменяется валидатором."
  },
  "open_questions": [
    {
      "id": "Q-001",
      "question": "OPEN08/09: Каковы measured RSS/CPU/SQLite contention/actual TTFT и proxy egress на103KB/6parallel?",
      "blocking": false,
      "disposition": "Не блокирует Stage2 contract; H1/H2/H3 блокируют runtime enabling до доказательства design budgets."
    },
    {
      "id": "Q-002",
      "question": "Какую policy совместимости реально поддерживает установленный v2: scoped deny или schema-preserving ask-auto-reject?",
      "blocking": false,
      "disposition": "Обе безопасные ветви заранее разрешены; FakeServe доказывает protocol, H6 доказывает реальный отказ file action до rollout. Не включать при неустановленной безопасной policy."
    }
  ],
  "protected_paths": [
    ".ai-team/",
    "analysis/zen-realtime-reasoning/"
  ],
  "materialization": [],
  "deferred": [
    "Живая приёмка H0..H9 и синхронизация ~/.dsh выполняются только rollout-этапом после clean-room verifier и downstream panel.",
    "OPEN-05/16: прямой Zen HTTP и другие CLI форматы не исследуются заново; текущая реализация использует подтверждённый v2 SSE.",
    "Измеренные CPU/RSS/FD и реальный proxy egress на 103 KB/6 parallel — обязательный rollout gate, не доказанный Stage 2 факт."
  ],
  "verification_policy": {
    "surface_frozen": true,
    "verification_implementation_owner": "Stage 3 Coder пишет tests/test_realtime_reasoning.py; Stage L2 Verifier независимо запускает каждый VER с 0 failed; тесты не считаются выполненными Stage 2",
    "REQ-019_clean_room": "VER-005 проверяет digest/rollout-manifest helper на двух временных fake files внутри sandbox, не ~/.dsh. Реальная синхронизация REQ-019 проверяется только H0 после отдельного rollout; невозможно подтвердить факт deploy чистым unit-тестом.",
    "timing": "FakeClock/RNG и Event-oracles для invariants; socket arrival/CPU реальные измерения отдельными measured/heavy unittest TestCase внутри dedicated suite (stdlib-discover тоже исполняет их). Тест timing держит upstream Event закрытым до чтения 10 дельт, deadline<500ms для interarrival и<=250ms bridge overhead; timeout helper аварийно освобождает Event, чтобы assertion failure не зависала. Не подменять arrival resp.read().",
    "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency."
  },
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "field_count": 46,
    "units": "SI: memory B (MiB=1048576B), times s, CPU cores, rates 1/s; векторы d и s именованы канонически",
    "required_hl_env_fields": {
      "P_steady": 1,
      "P_hpa_max": 1,
      "maxSurge_pct": 0.0,
      "maxSurge_abs": 0,
      "maxUnavailable_pct": 0.0,
      "maxUnavailable_abs": 0,
      "P_terminating_overlap": 0,
      "P_live": 1,
      "P_avail_min": 1,
      "W": 1,
      "N_proc": 1,
      "N_proc_steady": 1,
      "N_proc_avail_min": 1,
      "CPU_limit_per_pod": 2.0,
      "κ_skew": 1.0,
      "u_bg_worker": 0.02,
      "U_pod_sidecars": 0.25,
      "Mem_limit_per_pod": 2147483648,
      "Mem_rss_worker_max": 268435456,
      "Mem_shared_max": 1207959552,
      "RPS_peak": 0.2,
      "A_max": 3,
      "SLA_p99_s": 180.0,
      "N_entities_max": 64,
      "Limit_dep_share[d]": {
        "georouter": 80,
        "opencode_local_db": 10
      },
      "Limit_dep_rps[d]": {
        "opencode_spawn": 1.0
      },
      "W_fetchers[d]": {
        "opencode_spawn": 0
      },
      "J_init_s[d]": {
        "opencode_spawn": 12.0
      },
      "J_pod_s[d]": {
        "opencode_spawn": 12.0
      },
      "T_poll_s[d]": {
        "opencode_spawn": 15.0
      },
      "K_calls[d]": {
        "opencode_spawn": 0
      },
      "T_base_s[d]": {
        "opencode_spawn": 0.5
      },
      "T_cap_s[d]": {
        "opencode_spawn": 2.0
      },
      "Max_stale_age_s[c]": {
        "stateless_bridge": 0.0
      },
      "Min_healthy_ratio": 1.0,
      "B_retry_max": 6,
      "min_reserve_retry_rps": 0.05,
      "FD_worker": 128,
      "ulimit_n": 65536,
      "λ_new_conn_per_pod(s)": {
        "node_ephemeral": 3.0,
        "shared_snat": 1.8
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 24,
        "shared_snat": 12
      },
      "N_pods_in_scope(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "Port_range_size(s)": {
        "node_ephemeral": 16384,
        "shared_snat": 16384
      },
      "T_hold_s(s)": {
        "node_ephemeral": 60.0,
        "shared_snat": 60.0
      },
      "SNAT_ips_count(s)": {
        "node_ephemeral": 1,
        "shared_snat": 1
      },
      "HOTPATH_MODULES": [
        "bridges/opencode-zen-bridge/server.py"
      ]
    },
    "field_sources": {
      "P_steady": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_hpa_max": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxSurge_pct": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxSurge_abs": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxUnavailable_pct": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "maxUnavailable_abs": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_terminating_overlap": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_live": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "P_avail_min": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "W": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc_steady": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "N_proc_avail_min": "F-12/F-34; один локальный ThreadingHTTPServer/LaunchAgent, без HPA/rolling deployment; derived поля рассчитаны при single-process; план rollout без overlap.",
      "CPU_limit_per_pod": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "κ_skew": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "u_bg_worker": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "U_pod_sidecars": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "Mem_limit_per_pod": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "Mem_rss_worker_max": "F-29 baseline RSS=22MiB; Architect увеличил design bound с 64 до 256MiB для parent queues/accumulators 6 requests; это расчётная квота, H3 измеряет.",
      "Mem_shared_max": "F-20 idle serve=152MiB; OPEN-08 допущение 192MiB на активный child ×6=1152MiB; нагрузка ещё не измерена.",
      "RPS_peak": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "A_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "SLA_p99_s": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "N_entities_max": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "Limit_dep_share[d]": "F-26 georouter 80 direct slots; opencode_local_db=10 — design logical-child share из handoff, НЕ доказанный sqlite pool/max_connections; H3 проверяет фактическую contention и ≤6 children.",
      "Limit_dep_rps[d]": "F-11/server.py:309-314 — локально установленный spawn limiter 1/s, НЕ квота Zen/SQLite vendor. Запросы не являются pollers; не подставлять это число как upstream RPS quota.",
      "W_fetchers[d]": "F-12/F-14 и граф BND: новый source per-request, Control Plane/Snapshot poller не добавляется; 0 фоновых fetchers и 0 background calls. SSE keepalive не backend polling.",
      "J_init_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "J_pod_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "T_poll_s[d]": "F-10/F-04: 12s startup gate и 15s legacy keepalive как inherited nominal fields, фактических pollers=0. Новая client liveness cadence≤2s описана AD-003 и не backend poll.",
      "K_calls[d]": "F-12/F-14 и граф BND: новый source per-request, Control Plane/Snapshot poller не добавляется; 0 фоновых fetchers и 0 background calls. SSE keepalive не backend polling.",
      "T_base_s[d]": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "T_cap_s[d]": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "Max_stale_age_s[c]": "Stateless transport; новый Snapshot/secret TTL cache не создаётся. process-local capability boolean по stat не хранит secrets/model output и инвалидируется при mtime/size смене.",
      "Min_healthy_ratio": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
      "B_retry_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "min_reserve_retry_rps": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
      "FD_worker": "F-29 baseline parent36; расчёт parent ≤128 с 6 clients и ≤2 control/SSE connections per attempt + bounded stdout/stderr; child20 FD каждый (F-20) считаются отдельно, суммарно host<256.",
      "ulimit_n": "F-29 launchctl soft maxfiles=65536; не переносить значение вчерашнего reference packet=4096 как текущий факт.",
      "λ_new_conn_per_pod(s)": "Расчёт AD-001: readiness ≤3 connect attempts, control reusable per process + 1 SSE + egress; node ≤5×RPS_peak×A_max=3/s, active≤4×6=24; shared SNAT georouter pre_send_retries≤3 =>1.8/s, active12. Не измерено; H3 validate.",
      "C_active_in_scope(s)": "Расчёт AD-001: readiness ≤3 connect attempts, control reusable per process + 1 SSE + egress; node ≤5×RPS_peak×A_max=3/s, active≤4×6=24; shared SNAT georouter pre_send_retries≤3 =>1.8/s, active12. Не измерено; H3 validate.",
      "N_pods_in_scope(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "Port_range_size(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "T_hold_s(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "SNAT_ips_count(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
      "HOTPATH_MODULES": "HOTPATH_MODULES: текущий server.py, read-only symbol graph BND-001..004; новые проектные modules не нужны."
    },
    "operational_profile": {
      "model_event_rate_per_s_per_active": 10,
      "active_child_max": 6,
      "code_default_max_concurrent": 2,
      "deployed_max_concurrent": 6,
      "max_waiters_effective": "min(configured MAX_SLOT_WAITERS, 2*effective MAX_CONCURRENT) в общей _SlotBulkhead admission; code-default2/4, deploy6/12. Deployment6/12 unchanged, configured waiters variable не повышать.",
      "server_resource_manager": "один per-Server owner для bounded process/socket leases, после старта процесса, без parent live sockets before child exec",
      "threads_per_worker_upper_bound": 36,
      "thread_accounting": "6 handlers +≤6 managed adapter workers/readers +≤6 stderr drains +≤6 stdin feed (run only) +≤6 gate timers +6 reserve; новые timers не пишут в wfile. Все owned threads bounded/joined; worker не порождает дополнительный бесконечный reader. Временные reader/socket leases учитываются тем же manager.",
      "stdout_queue_max_events": 4096,
      "new_transport_queue_max_bytes": 1048576,
      "new_transport_max_sse_frame_bytes": 1048576,
      "new_transport_accumulated_output_budget_bytes": 8388608,
      "byte_limits_policy": "Только новый enabled transport, суммарный parent queue/raw/parser/dedup/visible output budget на request контролируется; превышение -> прежняя error shape + explicit output_overflow и cleanup, не молчаливое drop. Не вводить новый запрет на размер accepted prompt и не менять legacy limits. При нагрузке/длинном reasoning H3 измерить Python overhead и CPU.",
      "first_status_delay_s": 0.3,
      "status_heartbeat_s": 5.0,
      "first_event_timeout_s": 20,
      "first_token_timeout_s": 60,
      "stall_timeout_s": 60,
      "client_detect_s": 5,
      "client_probe_interval_s": 0.25,
      "client_keepalive_s": 2,
      "client_write_timeout_s": 0.5,
      "cleanup_budget_s": 1.2,
      "ready_budget_s": 0.5,
      "session_setup_budget_s": 0.2,
      "startup_wait_s": 5,
      "spawn_wait_s": 5,
      "slot_wait_s": 15,
      "spawn_rate_per_s": 1,
      "spawn_burst": 1,
      "total_deadline_s": 1800,
      "estimate_status": "Будущие design ceilings; SLA p99=180s рабочая цель аналитика, не гарантия worst-case sum трёх generation watchdog по60s+aux. Watchdogs не повышают TIMEOUT_S; H1/H2/H3 проверяют actual p99/TTFT перед rollout."
    },
    "memory_closure_check": {
      "status": "PASS",
      "lhs_bytes": 1476395008,
      "rhs_bytes": 1717986918.4,
      "substitution": "1×256MiB + 6×192MiB =1408MiB <= .80×2048MiB=1638.4MiB",
      "evidence_level": "design estimate, не measured peak; H3 — обязательный rollout gate"
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "substitution": "46 keys и 46 field_sources; memory=1476395008 <=1717986918.4 B, оценка. N/A содержит actual diff и граф, L2 обязан повторить на Coder diff.",
        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "roles: bridge=1 process, child session lease M=6, G_reload=1 close-before-create (fallback/retry cleanup до нового child), dedicated=0; другие роли=0. georouter 6<=.60×80=48. logical DB child bound6<=.60×10=6, это не измеренная физическая sqlite connection quota; opencode внутренний pool не увеличиваем, H3 проверяет database locks. Параллельный старый/new daemon rollout запрещён (P_overlap=0).",
        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Per-process manager: M=effective MAX_CONCURRENT (default2/deploy6), max_waiters<=2M (default clamp4/deploy12), wait<=15s; fixed max2 HTTP sockets/active serve (control keepalive+event), queue<=4096 events И <=1MiB, frame<=1MiB; no Redis SQL connection pool added. Общий ingress _SlotBulkhead обязан применять этот effective bound и при run, иначе default M=2/waiters12 нарушил бы 2M; не вводить вторую неучтённую очередь перед manager.",
        "oracle": "Блокировать M+2M leases, следующий fast-fail без Popen/connect, сокетов<=2M, queue byte-overflow explicit error; inspect configured ceilings. Нельзя снижать общий production slot count или повышать max_waiters.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I3": {
        "status": "PASS",
        "substitution": "Один server-owned manager/factory и _Resilience на процесс (100 запросов -> тот же id). Именованные leases для ephemeral per-attempt endpoints получают отдельные bounded control/SSE sockets только после child start. Это не reusable global-remote pool и не создание неучтённого клиента в Handler; требование A1 исключает shared daemon endpoint. Нет сокетов моста до child exec, close_fds; close manager в shutdown/release каждого lease.",
        "oracle": "Factory created_clients==1 per Server, pre-spawn transport sockets=0, session leases<=M; 100 calls same manager id; shutdown closes all leases/sockets/child groups. Отдельные socket endpoints не маскировать как singleton connection.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I4": {
        "status": "PASS",
        "substitution": "Любой timeout/cancel на slot/gate/ready/prompt/read/write вызывает общий finally; cleanup idempotent; counters waiters/in_use/children/sockets возвращаются0; disconnect не запускает retry.",
        "oracle": "50 controlled cancel cycles в каждой фазе через Events, cancel-before/after lease acquisition, counters==0; не считать daemon=True механизмом cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "C-MULT-I5": {
        "status": "PASS",
        "substitution": "Parent FD128<=.70×65536=45875.2; parent+6 children20FD<256 host descriptors. node ports:3×1×60+24=204<=8192; shared SNAT:1.8×1×60+12=120<=8192. Ceilings из field_sources — estimates; keepalive control reuse, readiness attempts<=3; close before next spawn.",
        "oracle": "Recompute both scope inequalities, count control connection creation/reuse (50 operations on one owned serve lease ->1 keepalive control TCP), readiness≤3 probes; leak counters FD/start/end stable; H3 измеряет реальные FD/egress.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "S_HERD": {
      "S-HERD-I1": {
        "status": "PASS",
        "substitution": "Snapshot/config startup/poll path absent: W_fetchers=0,K_calls=0 => batch K×(λ+4sqrtλ+4)=0<=.5×1=.5 и R_poll=0<=.2×1=.2. 1/s field — self-configured request spawn rate, НЕ неизвестная квота dependency; запрещено объявлять gate PASS через фиктивную внешнюю RPS. Request cold-start отдельно ограничен gate<=5s wait/12s hold + token bucket1/s burst1 для КАЖДОГО child включая fallback.",
        "oracle": "AST/transitive no backend poller; zero background I/O при idle; FakeClock spawn bucket max B+r*T; ≥6 parallel requests не делают 6 Popen одновременно. Startup gate release first validated event/own EOF/max hold, cancellation-safe.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "S-HERD-I2": {
        "status": "PASS",
        "substitution": "Full Jitter base=.5, cap=2 через injected RNG, cooldown10×U(.8,1.2). Bridge worker fork отсутствует; child exec не наследует RNG/secret state, serve password=secrets. При введении fork/poller обязательны post-fork SystemRandom/reseed и periodic jitter.",
        "oracle": "RNG points0/.5/1 дают0,.5*cap,cap; CSPRNG mocked count per child; inspect no fork worker; не запускать новый deterministic random.Random с одинаковым seed в каждом retry.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "S-HERD-I3": {
        "status": "N/A",
        "substitution": "Новый transport не создаёт Snapshot/config polling, If-None-Match или mutable indexed snapshot; conditional304 не имеет операции применения.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Новый transport не создаёт Snapshot/config polling, If-None-Match или mutable indexed snapshot; conditional304 не имеет операции применения.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "S-HERD-I4": {
        "status": "N/A",
        "substitution": "Новый transport не создаёт TTL-backed network cache или singleflight; process capability stat-key boolean не network TTL и не хранит ответ/секрет.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Новый transport не создаёт TTL-backed network cache или singleflight; process capability stat-key boolean не network TTL и не хранит ответ/секрет.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "S-HERD-I5": {
        "status": "N/A",
        "substitution": "Не вводится Control Plane/Snapshot/SWR/readiness endpoint; публичный /health unchanged; auth password живёт ровно до cleanup, 401 fail-closed.",
        "oracle": "AST/import/transitive absence oracle + actual Coder diff allowlist; на новом пути нет соответствующего cache/poller; секрет удаляется в cleanup.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Не вводится Control Plane/Snapshot/SWR/readiness endpoint; публичный /health unchanged; auth password живёт ровно до cleanup, 401 fail-closed.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      }
    },
    "H_CPU": {
      "H-CPU-I1": {
        "status": "N/A",
        "substitution": "Нет нового indexed routing Snapshot/selection по N_entities; canonical event dispatch по exact type O(1), bounded parser stream зависит от длины входа, не от N proxy nodes.",
        "oracle": "Dispatch-equivalence fixtures для всех event types, operation count независимо от N_entities. Absence Snapshot/routing graph и actual diff.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Нет нового indexed routing Snapshot/selection по N_entities; canonical event dispatch по exact type O(1), bounded parser stream зависит от длины входа, не от N proxy nodes.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "H-CPU-I2": {
        "status": "PASS",
        "substitution": "Regex compiled at import; нет per-delta json.loads правил/конфигов, model_validate/deepcopy/static label binding. json.loads одного входного SSE frame необходим для transport framing и не является forbidden config reload parse. Deny config merge один раз per attempt setup вне delta loop.",
        "oracle": "Спай на re._compile/config decoder/model_validate/typeadapter/deepcopy/static labels в delta loop ->0; wire decoder count==one per actual event, не full history; tool JSON parser exempt by input decoding purpose.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Первый guard optional serve branch проверяет realtime flag до UUID/password/clock/serve queue/threads/probe. flag=false -> прежний run O(1) transport-selection branch; watchdog/status — отдельное исправление RC2/RC3 для обоих транспортов, не скрытая serve allocation. У status helper первый guard thinking-enabled/SSE до форматирования/часов. Включённые data queues bounded put_nowait; overflow model events=explicit error+kill, не silent telemetry drop; optional telemetry drop increments dropped_total.",
        "oracle": "Flag=false spies serve allocator, password, UUID, probe, threads=0. Full bounded event queue->explicit overflow+cleanup, без ожидания; optional product event queue drop fail-open. status flag guard не отключает стандартные legacy errors.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "H-CPU-I4": {
        "status": "N/A",
        "substitution": "Мост ThreadingHTTPServer, нового async event loop/config reload Snapshot нет; parser/readers в owned worker, клиентский writer не блокируется setup I/O.",
        "oracle": "Actual diff/call graph no asyncio or snapshot reload path; server writer scheduling проверяется Event test.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Мост ThreadingHTTPServer, нового async event loop/config reload Snapshot нет; parser/readers в owned worker, клиентский writer не блокируется setup I/O.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "H-CPU-I5": {
        "status": "PASS",
        "substitution": "Inherited CPU estimates t_req=.02,t_attempt=.05; total=.17CPU-s, util=1×.2×.17/(1×1)+.02=.054<=.70; pod=.054+.25=.304<=.8×2=1.6; допускается Δt_feature<=.10 CPU-s/request =>Δcores=.2×.10=.02<=.05×(1×2)=.10. Event path up to60frames/s; никакого повторного full-history regex/JSON parse в delta loop. Дельта .10CPU-s — budget, не замер.",
        "oracle": "Fake workload CPU accounting/proportional operation count checks with deterministic sizes; measured/heavy scenario process_time профиль по50 controlled frames плюс H3 full length. FAIL budget -> нельзя включить serve, не объявлять estimate actual performance.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "R_BULK": {
      "R-BULK-I1": {
        "status": "PASS",
        "substitution": "Slot один раз15s + Amax3×(gate5+spawn-token5+ready.5+session-control.2+cleanup1.2)+backoff caps1+2 =53.7s<=.30×180=54s. Generation model wait отделён от auxiliary: first-event20, first-token60, stall60, TIMEOUT1800 общий. Каждый HTTP/control/session operation получает min(operation_budget,remaining); cleanup имеет отдельный финальный потолок1.2s, не skip при истёкшем request. После deadline ни spawn, ни prompt, ни sleep.",
        "oracle": "FakeClock recompute53.7<=54; exhaust setup subbudget and total deadline before each I/O ->zero further calls. Контроль setup aggregate .2s, ready.5s, cleanup1.2s (не сумма отдельных безлимитных вызовов). При снижении SLA/увеличении budget формула обязана стать FAIL до rollout.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I2": {
        "status": "PASS",
        "substitution": "Per-request Popen<=3, shared RetryBudget6 +.20/request+.05/s; Nreq100,Tw500 -> retries<=floor(20+25)+6=51. Transport fallback расходует тот же retry token; local capability failure не breaker/provider failure, но не бесплатный новый spawn. Bulkhead M6 waiters12 или effective2/4; в production ничего не сбрасывать.",
        "oracle": "FakeClock 100 failing primary requests -><=51 retries; tokens>=0; no spawn4 при комбинации serve-unavailable/watchdog/native/incomplete; тесты isolated _Resilience не ослабляют runtime caps.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I3": {
        "status": "PASS",
        "substitution": "Existing breaker threshold5,cooldown10×U(.8,1.2),HALF_OPEN=1. Watchdog/provider transient отмечаются attempt_done+commit; recovered success не накапливает pending failure. Bridge log fail-open, startup lock timeout fail-open; secret/auth/permission/unknown accepted prompt fail-closed. В baseline _UpstreamBreaker.allow lease пробы истекает по reset_s даже при ещё активном request (server.py:1415-1428); новый contract не разрешает вторую active HALF_OPEN пробу. Владение probe завершает success/failure или подтверждённый cancel/cleanup; время cooldown не освобождает живую пробу само.",
        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "R-BULK-I4": {
        "status": "N/A",
        "substitution": "Bridge не выбирает V_eligible, tenant nodes/health/quarantine; _next_standalone_proxy round-robin env, georouter owns selection. Не добавляется Panic-Open или перескок Google/провайдера при serve failure.",
        "oracle": "AST graph/diff запрет proxy-node-health, tenant routing, cross-pool fallback; preserving _model_route and _run_env branch.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Bridge не выбирает V_eligible, tenant nodes/health/quarantine; _next_standalone_proxy round-robin env, georouter owns selection. Не добавляется Panic-Open или перескок Google/провайдера при serve failure.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      },
      "R-BULK-I5": {
        "status": "N/A",
        "substitution": "Bridge видит одну logical model dependency и не ведёт origin_health/node_health; georouter остаётся владельцем таких решений. Новый watchdog не карантинит ProxyRack entry на все origins.",
        "oracle": "Отсутствие quarantine/node health mutation по actual diff + graph; injected error не меняет configured provider/model/proxy list.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "reason": "Bridge видит одну logical model dependency и не ведёт origin_health/node_health; georouter остаётся владельцем таких решений. Новый watchdog не карантинит ProxyRack entry на все origins.",
        "na_proof": {
          "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
          "current_git_diff_output": "",
          "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
          "git_diff_files": [
            "bridges/opencode-zen-bridge/server.py",
            "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
            "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
          ],
          "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
          "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
        }
      }
    },
    "T_LIFE_v1": {
      "status": "PASS",
      "substitution": "Request/attempt ownership включает PGID, stdout/stderr, SSE/control sockets, session id, queue/readers и startup gate. AD-003 cleanup на всех exits<=1.2s, child group reap; leader early-exit не оставляет grandchildren. Server shutdown manager запрещает новые leases и отменяет все активные, затем closes all.",
      "oracle": "VER-005: 50 cancellations + leader-exits-first descendant + blocked socket/readiness + partial prompt + overload/shutdown; zero active/waiters/children/readers/sockets; PIDs/PGIDs только свои.",
      "verification_ids": [
        "VER-005"
      ]
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется.",
      "oracle": "VER-005 table all exits incl 400/401/404/503/circuit, overflow, error, abort, successful retry; deterministic fake clock, no secret reflection.",
      "verification_ids": [
        "VER-005"
      ]
    },
    "M_SEM_v1": {
      "status": "N/A",
      "reason": "Bridge не имеет tenant/pool node selection; direct Google dispatch и configured model/provider уже разделены, никакой cross-provider recovery.",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
        "current_git_diff_output": "",
        "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
          "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
        "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
      },
      "oracle": "VER-001/003 Google direct unchanged, VER-005 no cross-provider fallback/proxy selection mutation.",
      "verification_ids": [
        "VER-001",
        "VER-003",
        "VER-005"
      ]
    },
    "dependency_failure_matrix": [
      {
        "dependency_operation": "serve/readiness + session init",
        "path": "hot/aux",
        "timeout_budget": "aggregate ready<=.5s, create+event-subscription+prompt-send<=.2s, capped remaining",
        "bulkhead": "manager leases<=M, control+SSE<=2M",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Capability unavailable before prompt in auto -> fully cleaned run retry; auth/security fail-closed, forced serve explicit error; once prompt starts no silent fallback"
      },
      {
        "dependency_operation": "opencode model execution (serve or run)",
        "path": "hot",
        "timeout_budget": "first-event20, first-token60, stall60, request TIMEOUT1800 common",
        "bulkhead": "_slots effectiveM, waiters<=2M, one child per slot",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Watchdog/transient -> cleanup + retry budget/jitter; no retry client_gone or fatal4xx; final explicit error even after partial output"
      },
      {
        "dependency_operation": "_StartupGate/_SpawnRateLimiter",
        "path": "hot/aux",
        "timeout_budget": "wait<=5 each, hold<=12; cancel poll<=.25",
        "bulkhead": "1 gate, token bucket1/s burst1",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Gate timeout fail-open as legacy; rate limiter not bypassed, every real child counted"
      },
      {
        "dependency_operation": "serve interrupt/delete and process cleanup",
        "path": "cleanup",
        "timeout_budget": "interrupt+delete aggregate<=.2, TERM grace<=.5, reap/join<=.5; total1.2",
        "bulkhead": "only own session/PGID, no new leases",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Best effort API failure never skips socket close/killpg; force SIGKILL, idempotent cleanup"
      },
      {
        "dependency_operation": "DSH SSE/client socket",
        "path": "hot",
        "timeout_budget": "probe<=.25, empty keepalive<=2 silence, write<=.5; detect<=5",
        "bulkhead": "single writer, bounded event queue1MiB/4096",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "FIN/RST ->client_gone+cleanup, no retry; slow consumer/overflow ->explicit terminal error if writable; hard write timeout cancels"
      },
      {
        "dependency_operation": "bridge.log",
        "path": "telemetry",
        "timeout_budget": "существующая synchronous append baseline; новые строки bounded/redacted, status write не зависит от log",
        "bulkhead": "existing _LOG_LOCK",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Fail-open OSError; не добавлять synchronous remote logger на request path"
      }
    ],
    "non_waivable_stop_codes": [
      "HL-ENV-01",
      "C-MULT-I1",
      "C-MULT-I2",
      "C-MULT-I3",
      "C-MULT-I4",
      "C-MULT-I5",
      "S-HERD-I1",
      "S-HERD-I2",
      "S-HERD-I3",
      "S-HERD-I4",
      "S-HERD-I5",
      "H-CPU-I1",
      "H-CPU-I2",
      "H-CPU-I3",
      "H-CPU-I4",
      "H-CPU-I5",
      "R-BULK-I1",
      "R-BULK-I2",
      "R-BULK-I3",
      "R-BULK-I4",
      "R-BULK-I5",
      "T-LIFE/v1",
      "O-EXIT/v1",
      "M-SEM/v1"
    ],
    "status_semantics": "PASS = проверенная полнота/замкнутость проектного guardrail; runtime assertion обязателен Stage3/L2 и ещё не выполнен. N/A = только отсутствие указанной функции на новом пути с двойным evidence; не waiver. Фактический FAIL/нет oracle -> REJECT, никакого техдолга вместо гейта.",
    "summary": {
      "PASS": 16,
      "N/A": 8,
      "FAIL": 0,
      "meaning": "projected design invariants only; implementation/runtime verification pending"
    }
  },
  "legacy_arch_antipattern_checks": {
    "ARCH_CYCLE_DETECTED": {
      "status": "PASS",
      "rationale": "Boundary DAG Handler/Run -> transport source -> stdlib I/O, pure parser/recovery без reverse imports; runtime evidence shared source исключает отдельные несовместимые циклы.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "LAYER_VIOLATION": {
      "status": "PASS",
      "rationale": "Pure parsers не знают HTTP/process; adapter не пишет в wfile; Handler отвечает за presentation.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "GOD_OBJECT": {
      "status": "PASS",
      "rationale": "Новый managed source/supervisor отдельный внутренний объект; не расширять монолитные Handler loops transport branching. Baseline размер server.py — унаследован, wholesale refactor вне scope.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "TIGHT_COUPLING": {
      "status": "PASS",
      "rationale": "Оба пути получают canonical (etype,payload), не OpenCode v2 objects; session/network cleanup скрыт adapter ownership.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "LEAKY_ABSTRACTION": {
      "status": "PASS",
      "rationale": "Клиент видит прежний OpenAI SSE/JSON. Password/session/control events не уходят в content; [мост] — явно разрешённый status REQ-005.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "MISSING_TIMEOUT": {
      "status": "PASS",
      "rationale": "Per-op+aggregate ready/session/cleanup deadlines,20/60/60 watchdog, write/probe limits; setup не блокирует SSE writer.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNBOUNDED_RETRY": {
      "status": "PASS",
      "rationale": "Каждый Popen, включая fallback, внутри MAX_TOTAL_SPAWNS3 и RetryBudget; нет альтернативного бесконечного startup loop.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RETRY_STORM": {
      "status": "PASS",
      "rationale": "Shared process budget+breaker+spawn rate1/s burst1; retry slot тот же, full jitter.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "THUNDERING_HERD": {
      "status": "PASS",
      "rationale": "gate и rate limiter перед каждым реальным child; pure local script eligibility без capability subprocess storm.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNBOUNDED_QUEUE": {
      "status": "PASS",
      "rationale": "Model event queue4096/1MiB +max frame1MiB+output budget8MiB; waiters<=2M; overflow явный fail, не silent drop.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "MISSING_BACKPRESSURE": {
      "status": "PASS",
      "rationale": "Slot6/max12 или code-default2/effective4, fail-fast overflow, bounded slow-client writes.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "BLOCKING_IO_IN_ASYNC": {
      "status": "N/A",
      "rationale": "asyncio не вводится; ThreadingHTTPServer, blocking upstream/setup в managed worker, single writer bounded.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required",
      "na_proof": {
        "current_git_diff_command": "git diff --name-only -- bridges/opencode-zen-bridge analysis/zen-realtime-reasoning",
        "current_git_diff_output": "",
        "current_product_fingerprint": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
        "git_diff_files": [
          "bridges/opencode-zen-bridge/server.py",
          "bridges/opencode-zen-bridge/tests/test_step_interruption.py",
          "bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py"
        ],
        "transitive_call_graph": "Handler.do_POST -> {Handler._stream_sse, Handler._serve_json -> Run.execute -> Run._execute_once}; common source -> {legacy _spawn_with_stdin/_StdoutFeed/parse_opencode_event, managed serve HTTP+SSE adapter}; both -> ToolCallParser/_split_tool_calls/_strip_interrupted/_strip_broken_tool_blocks/_incomplete_step_signal; common _RequestAttempts -> _Resilience(slots,spawn_limiter,retry_budget,breaker), _StartupGate, _run_env -> _next_standalone_proxy; cleanup -> interrupt/delete, sockets.close, own killpg/reap. Google branch dispatches before serve. No new callers outside Handler/tests, no bridge callers to Redis/PG/Vault, Control Plane/Snapshot fetch, asyncio, node eligibility/quarantine/singleflight. Catalog functions inherited, no new route snapshot/cache path introduced.",
        "future_diff_gate": "Текущее отсутствие diff доказывает read-only Stage2, а не отсутствие будущих вызовов. VER-005 использует AST/static/transitive callees/import oracles для всех declared N/A, VER-003 full regression; Verifier до разрешения rollout сверяет реальный Coder diff ровно с allowlist и отсутствием новых transitives. Любой новый poller/cache/snapshot/node-selection меняет применимость и требует Architect delta."
      }
    },
    "CPU_SPIN_WAIT": {
      "status": "PASS",
      "rationale": "Queue.get/select c конечным timeout, FakeClock/RNG tests; readiness<=3 connects, никакого busy-spin polling.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RESOURCE_LEAK": {
      "status": "PASS",
      "rationale": "Session interrupt/delete,socket close, thread join, PGID stop и slot release на всех paths; factory shutdown закрывает owned leases.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "ZOMBIE_SUBPROCESS": {
      "status": "PASS",
      "rationale": "killpg даже если leader вышел; TERM->KILL<=1.2s cleanup, reap wait, child/grandchild проверка.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "RACE_CONDITION": {
      "status": "PASS",
      "rationale": "Single writer; per-attempt state локален, shared manager/resilience locks; cleanup идемпотентен, close-before-create, port ownership/auth check.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "NON_IDEMPOTENT_RETRY": {
      "status": "PASS",
      "rationale": "Built-ins deny/ask-auto-reject никогда не исполняются; при неизвестной доставке prompt не silent fallback. Повтор может дублировать reasoning, имеет отдельный status; tool ids/key dedup.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "BREAKING_CONTRACT": {
      "status": "PASS",
      "rationale": "Port/endpoints/auth/Google route/schema не меняются; разрешённые behavior deltas явно CD и текущие REQ, fast reasoning exact preserved.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "SILENT_DATA_LOSS": {
      "status": "PASS",
      "rationale": "Delta и ended не удваиваются, step tokens учтены, EOF без terminal=error; parser splits/no raw tool leak; overflow explicit failure.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "UNHANDLED_UPSTREAM_ERROR": {
      "status": "PASS",
      "rationale": "Early/error/recovery и terminal failed через legacy classifier; 401 deterministic fail-closed, watchdog exits логируются.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    },
    "HARDCODED_SECRET": {
      "status": "PASS",
      "rationale": "secrets password per child env после whitelist; Basic header не логируется; mask before stdout/stderr/error artifact.",
      "verification_ids": [
        "VER-005"
      ],
      "evidence_level": "design; future L2 test required"
    }
  },
  "status_protocol_examples": {
    "initial": "[мост] Подключение к модели…\n",
    "retry": "[мост] Повтор попытки 2/3…\n",
    "waiting": "[мост] Ожидание первого токена (10 с)…\n"
  },
  "handoff_state": {
    "architecture_contract": "Stage2 approved-phase candidate; не ARCH_GATE_PASS, не council verdict",
    "implementation_tests": "NOT_RUN — код/tests Stage3 ещё не создавались",
    "live_acceptance": "NOT_RUN — H0..H9 отдельно; не менять ~/.dsh",
    "pending_orchestrator_actions": [
      "validate_arch_gate/внесение packet hash в task envelope",
      "external architecture panel и verify_panel_proof PASS перед Coder",
      "Stage3 Coder и clean-room L2 VER001..005",
      "rollout H0..H9"
    ]
  },
  "verification_acceptance_matrix": {
    "FakeServe": "stdlib subprocess fake implements serve argv, HTTP Basic401, GET /openapi.json and /api/event, POST session/prompt/interrupt, DELETE, permission request/reject. Tests set flag=true and transport=serve, so shebang auto compatibility does not skip real serve path. Hold upstream Event after first deltas, client readline sees data before release. No real model/Zen calls.",
    "mode_matrix": [
      "flag=false, auto/serve/run -> run, no serve allocation or Popen",
      "flag=true, run ->run",
      "flag=true, auto, legacy shebang ignores argv ->run once directly, counter1, stdin promptEOF",
      "flag=true, serve, FakeServe shebang ->full SSE v2; both JSON and stream",
      "flag=true, serve, fake legacy blocking stdin ->DEVNULL gives immediate EOF; ready failure<=.5s, explicit error, no5s hang",
      "flag=true, auto, binary unsupported/ready failure -> cleanup then run only pre-prompt, all Popen total<=3; exhausted budget stops",
      "serve401/permission failure/unknown prompt delivery/client_gone -> no silent fallback"
    ],
    "status_matrix": [
      "slow blank upstream + startup-gate/rate-wait: grace.30 first [мост] LF<=1s",
      "fast real reasoning/text before grace: no initial status; Simple greeting. exact",
      "off/none/nonthinking + slow upstream: no synthetic reasoning; normal content/keepalive/error unchanged",
      "whitespace/empty comments/status do not set first-token or attempt_output",
      "retry accepted after model reasoning: exactly one retry status, raw model bytes retained, no reasoning dedup",
      "normal127ms model reasoning: no periodic status, natural LF enables collapsed preview, no newline injected into model delta",
      "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes"
    ],
    "watchdog_matrix": [
      "first_event_timeout on silent legacy after process spawn and on fake serve event-less execution when no valid readiness/server event",
      "first_token_timeout on repeated started/control/keepalive events with no non-whitespace model token",
      "stall_timeout after first real model delta, comments/bridge statuses do not reset it",
      "first-event may be satisfied by valid serve readiness: an authenticated ready server with zero model tokens must timeout via first_token, not fabricate first_event failure",
      "all thresholds env configurable, tiny values/FakeClock; shared total deadline never resets; no retry4"
    ],
    "lifecycle_matrix": [
      "disconnect at gate/limiter/ready/prompt/blocked SSE/after reasoning, detect<=5s and PGID absent<=7s",
      "leader exits but descendant holds stdout; group still killed",
      "SIGTERM ignored ->SIGKILL, leader reaped, no child/grandchild",
      "success/tool step/error/fallback/shutdown each closes session/socket/threads/slot once",
      "byte queue/frame/output overflow explicit error (no silent model delta loss)",
      "50 cancel fault-injection cycles counters in_use/waiters/sessions/sockets/readers=0"
    ],
    "tools_matrix": [
      "every split point and single-char deltas for both tags, JSON embedded close strings/code quoting existing fixtures",
      "stream content before open tag visible immediately, pending genuine prefix<=12 plus inherited code-context lookahead",
      "unparsed/open genuine blocks stripped by existing wrapper, no raw tool tags in SSE content",
      "native call lifecycle normalized/dedup per call-id, mapped/unmapped behavior identical; no auto allow",
      "step.ended tokens input/output/cached/reasoning counted once then tool finish, no followup synthetic step",
      "early legacy error may recover; late transient/fatal error and incomplete recovery same on fake v2",
      "existing reasoning_interrupted and interrupted cleanup across delta boundaries"
    ],
    "baseline_matrix": [
      "two original budget fixtures:3 spawns, no fourth tool result, stop; separate fixture unmapped->incomplete->calls within3 proves counter separation",
      "fresh _Resilience/_RetryBudget per test, reverse fixed ordering plus isolated/full runner",
      "all17 existing modules untouched except the3 acknowledged assertions/isolation in test_step_interruption; no Google changes"
    ],
    "resilience_matrix": [
      "46 exact HL canonical keys+sources and memory inequality",
      "21 stop-code oracles + T-LIFE/O-EXIT/M-SEM, each N/A has actual diff + transitive AST proof",
      "new process/socket resource manager singleton and bounded lease count, 50 control keepalive operations1 connection per lease",
      "RPS token bucket/cancel/full jitter/retry budget/breaker HALF_OPEN1 via FakeClock/RNG",
      "wire event JSON decode allowed; config decode/re.compile/reparse-full-history on per-delta hot path forbidden",
      "HALF_OPEN active probe held across reset_s boundary: zero second probes until owner cleanup; common _SlotBulkhead code-default M2/waiters4 and deploy M6/waiters12, no second uncounted ingress queue."
    ],
    "rollout_boundary": "VER001..005 не обращаются к ~/.dsh. В root suite test_dsh_profile_config видит отсутствие live profile в clean-room и делает inherited skip. Actual REQ019 identity и H0..H9 отдельный rollout gate; fake digest fixture не подменяет read-back deployed file."
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46 exact key equality and field_sources equality against team architecture.md §3.0",
    "stop_codes": "21 main codes + T-LIFE/O-EXIT/M-SEM=24 unique",
    "legacy_antipatterns": "21 exact keys from approved reference schema",
    "verification_owner": "5/5 owner=verifier",
    "decisions": "4/4 two-way with >=2 genuine alternatives",
    "evidence_refs": "61 unique EVD IDs; decision/assumption references checked; EVD061 identifies existing HALF_OPEN and default waiter gaps.",
    "VER-004_syntax": "ast.parse PASS; actual future command pending test file Stage3",
    "status_protocol": "3/3 examples begin [мост], end actual LF",
    "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes."
  },
  "routing_profile": "standard"
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json sha256=f8e732b53fdebb15c338bb42b2f84ea6323cc00e0f39d57bbf842c5c39644a44
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "criticality": "S2",
  "packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
  "verification_surface_sha256": "b13549592f01850ff16a8d56cbe3cd77383fde35bcc91a5cff503b9e209e2ae4",
  "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b",
  "architect_worktree_sha256": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
  "materialized_targets": 0
}
ARTIFACT_END>>>

КОНТЕКСТ:
Ниже приложены целиком формулировка цели владельца, конверт задачи (`task.json`), аналитический пакет (`handoff-architect.md`, `evidence-ledger.md`, `research-plan.md`), а также стандарты проекта и Python-архитектуры (`aisdlc-gcge/AGENTS.md`, `aisdlc-gcge/skills/architecture.md`, `aisdlc-gcge/agents/scope-and-contracts.md`), соблюдение которых (включая все пункты `Definition of Done overlay` и все 5 групп Highload & Resilience гейтов `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`) входит в твои обязательные проверки:
<<<ARTIFACT /tmp/cel-runs/zen-realtime-reasoning-20261025/goal.md sha256=4d953bef55831514175b6bf4150dc2af3bef47489913b6dccc2d536df6c83528
# Цель: Реалтайм-стриминг размышлений (reasoning) и шагов DeepSeek через мост opencode-zen-bridge в DSH

- Открыто: 2026-10-25 22:24:20 MSK
- Репозиторий (изолированный клон): `/Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning` (ветка `feature/zen-realtime-reasoning` от `origin/dev`)
- Контур: `cel` + `analyst-teamlead` (`system-analyst` → `architect-software-product` → `Arch Panel` 3 судей → `Coder` → `Clean-Room L2` → `Code Council` 3 судей → открытый PR в `dev` + живая проверка тяжёлым путём).
- Бизнес-результат и критерий приёмки:
  1. При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.
  2. Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).
  3. Проведена живая проверка тяжёлым путём на реальном мосту и DSH.
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=5b1b470234e54ef85ca258da0000b5c1b2ba8b01d6bf1b163f1a670b5b133079
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
    "verification_surface_sha256": "b13549592f01850ff16a8d56cbe3cd77383fde35bcc91a5cff503b9e209e2ae4",
    "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b"
  }
}
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-architect.md sha256=9cd426324b8f49ddc760e3706e200709754a0a459b9e234f7b45b3b2669c6d9f
# Handoff to Architect: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребитель: `architect-software-product` (Stage 2, класс S2, вход в разработку только через ARCH_GATE).
Факты — в `evidence-ledger.md` (`F-01..F-49`), вопросы — в `open-questions.md` (`OPEN-01..OPEN-17`, блокеров нет), план — в `research-plan.md`.
Архитектура и стек здесь не выбираются: варианты сравниваются по фактам, решение за Архитектором.

## 1. Постановка и цепочка корневых причин

Запрос владельца: видеть размышление DeepSeek в DSH в реальном времени при работе через `opencode-zen-bridge` (`127.0.0.1:9883`) и получить высокую
отзывчивость. Инцидент-образец — `session-423ca27f`, ход 2 шаг 5 (22:16:12 MSK): на экране только «Deep diving for 35s ···», затем более 780 с без единого токена (F-30, F-33).

Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».

| Код | Причина | Ключевые факты |
|---|---|---|
| RC-1 | `opencode run --format json --thinking` v2.1.2 подписан только на `session.reasoning.ended` и `session.text.ended` и игнорирует `*.delta`: размышление и текст приходят одним блоком в самом конце шага (разница 0.00-0.17 мс), тишина stdout 1.9-2.7 с даже на здоровом вызове. Мост не может показать то, чего CLI не выдаёт | F-17, F-18, F-02, F-05 |
| RC-2 | Нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками; единственный потолок — `TIMEOUT_S=1800` с; холодный `--standalone` на БД 2.27 GB, пул ProxyRack и сериализующий `_StartupGate` дали зависания 780-856 с, а keepalive `{"content":""}` держал сокет DSH пустым | F-09, F-10, F-28, F-30, F-31, F-32, F-04 |
| RC-3 | В DSH строка `⚛ Think` не рисуется, пока нет непустого `reasoning_content`; пустые keepalive ничего не показывают; inline-превью свёрнутой строки обновляется только по завершённому абзацу (нужен `\n`) | F-36, F-37, F-04 |

Цепочка следствий: RC-1 лишает реалтайма здоровый вызов, RC-2 превращает больной вызов в многоминутную тишину, RC-3 делает любую тишину
для пользователя неотличимой от зависания (экран с таймером без содержимого). Реалтайм-транспорт без пунктов RC-2 и RC-3 проблему не закрывает.

## 2. As-is карта потока (каждая связь — факт)

```
DSH (pi-ai openai-completions, stream:true)  --HTTP SSE-->  Handler._stream_sse (:9883)        F-35, F-03
  Handler._stream_sse: 200+role-chunk -> _StartupGate -> spawn `opencode run ... --format json`  F-03, F-10, F-01
  opencode run (stdout JSON lines) -> _StdoutFeed(queue 4096) -> parse_opencode_event            F-14, F-02
     reasoning -> delta.reasoning_content (flush сразу)                                         F-05
     text      -> ToolCallParser.feed -> delta.content / delta.tool_calls                       F-05, F-06
     keepalive -> {"content": ""} раз в 15 с тишины                                              F-04
  opencode run --standalone -> opencode serve --stdio (дочерний) -> georouter :10830 -> Zen      F-30, F-26, F-27
  Пул ProxyRack: следующий порт на каждый spawn (env HTTP(S)_PROXY, loopback мимо)              F-15
DSH UI: непустой reasoning_content -> blockIsVisible -> ReasoningRow (превью по "\n")            F-36, F-37
DSH реплей: thinking -> assistant.reasoning_content -> мост игнорирует                          F-38, F-07
```

Граница совместимости (факт): всё ниже `parse_opencode_event` оперирует кортежами `(etype, payload)` (F-02, F-05); поэтому любой транспорт,
сводимый к тем же кортежам, не требует правки верхнего слоя (ретраи, парсер инструментов, usage, SSE-кадрирование).

## 3. Требования `REQ-001..REQ-020`

Приоритет `MUST`/`SHOULD`; критерии `AC-*` — краткие проверяемые формулировки (полная спецификация живёт в requirements и в `handoff-qa.md`).

| REQ | Приоритет | Требование | Факты | AC |
|---|---|---|---|---|
| REQ-001 | MUST | Дельты размышления и текста уходят клиенту по мере прихода из апстрима, а не в конце шага | F-17, F-18, F-19 | AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт; AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс |
| REQ-002 | MUST | Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883 | F-35, F-34 | AC-003: побайтовое совпадение формы чанков с текущей на наборе существующих тестов формата |
| REQ-003 | MUST | Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными | F-43, F-40, F-42 | AC-004: при выключенном новом транспорте проходят все 378 существующих тестов (после решения OPEN-04) |
| REQ-004 | MUST | Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\n` (статус подключения/ожидания модели), независимо от состояния апстрима | F-36, F-37, F-04, F-33 | AC-005: первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса даже при полностью молчащем апстриме |
| REQ-005 | MUST | Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее | F-37, F-38, F-07, F-39 | AC-006: объединённый `reasoning_content` без статусных строк побайтово равен тексту модели; AC-007: `_messages_to_prompt` не содержит статусных строк при реплее |
| REQ-006 | MUST | Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку | F-09, F-30, F-31 | AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с |
| REQ-007 | MUST | Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения | F-09, F-19, F-32 | AC-009: пауза больше порога после первого токена приводит к остановке и классификации `stall_timeout`; AC-010: порог первого токена даёт `first_token_timeout` |
| REQ-008 | MUST | Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с | F-14, F-30, F-33 | AC-011: после закрытия клиентского сокета процессы группы отсутствуют не позже чем через 7 с; AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится |
| REQ-009 | MUST | Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка | F-11, F-12 | AC-013: суммарно не более 3 запусков на запрос при любой комбинации причин; AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка |
| REQ-010 | MUST | `ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len("<tool_invoke>")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты | F-06, F-05 | AC-015: перебор границ чанков на фикстурах существующих тестов даёт тот же набор `tool_calls` и тот же `content`, что при подаче целым текстом |
| REQ-011 | MUST | Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason="tool_calls"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути | F-05, F-11, F-43 | AC-016: все сценарии `test_step_interruption.py` проходят на новом транспорте с фейковым потоком дельт |
| REQ-012 | MUST | Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native) | F-08, F-22, OPEN-07 | AC-017: фейковый поток с событием встроенного инструмента даёт тот же `unmapped`-повтор и тот же `finish_reason`, что legacy-путь |
| REQ-013 | MUST | Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта | F-10, F-11, F-15, F-32 | AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`) |
| REQ-014 | SHOULD | `usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим | F-19, F-02 | AC-019: поле `usage` финального чанка совпадает с эталонными значениями фикстуры |
| REQ-015 | MUST | Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование | F-21, F-27 | AC-020: `bridge.log` после прогона не содержит пароля serve и значений `apiKey` |
| REQ-016 | MUST | Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода | F-32, F-30 | AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` |
| REQ-017 | SHOULD | Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс | F-45, F-46, F-47, F-48, F-49 | AC-022: `uvx pytest -q -p no:cacheprovider tests/` без красных; AC-023: результат не зависит от порядка тестов |
| REQ-018 | MUST | Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок |
| REQ-019 | SHOULD | Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя |
| REQ-020 | MUST | В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green) |

## 4. Варианты реализации RC-1 (сравнение по фактам, без выбора)

Вердикты: `выполнимо` / `выполнимо с условиями` / `невыполнимо`. Исходные данные по каждому — в ledger.

| Вариант | Суть | Задержка и реалтайм | Авторизация, маршрут, ротация IP | Изоляция встроенных инструментов | Параллелизм и SQLite | Тестируемость | Вердикт |
|---|---|---|---|---|---|---|---|
| L: только упрочнение legacy | `opencode run` остаётся, добавляются watchdog (REQ-006..008), статусные строки (REQ-004, REQ-005) | Реалтайма размышления нет: единый блок в конце шага (F-17, F-18); живость только за счёт статусных строк моста | Без изменений (F-15) | Без изменений (F-08) | Холодный spawn на каждый шаг сохраняется (F-28, F-30) | Полная: fake-CLI (F-43) | выполнимо; закрывает RC-2 и RC-3, но не RC-1 |
| A1: `opencode serve` короткоживущий на запрос, SSE `GET /api/event` | Мост поднимает `serve` на свободном порту с одноразовым паролем, создаёт сессию, шлёт prompt, читает дельты, затем `interrupt`/`DELETE` и `killpg` | Дельты размышления каждые 105-304 мс (median 127), первая дельта 1811 мс, text-дельты median 114 мс (F-19); старт сервера 109 мс (F-20) | Пароль случайный на процесс (F-21); env прокси задаётся на запуск, значит ротация сохраняется (F-15, OPEN-06); egress идёт через georouter (F-26, F-27) | Поле `permissions` в `POST /api/session` и `permission {"*":"deny"}` в конфиге (F-22), поведение не прогнано (OPEN-07) | Один процесс на запрос, idle RSS 152 MiB (F-20); БД та же 2.27 GB, нагрузка не мерилась (OPEN-08) | Нужен фейковый serve-сервер и адаптер событий; fake-CLI покрывает только legacy-путь (F-43) | выполнимо с условиями (OPEN-06, OPEN-07, OPEN-08) |
| A2: общий управляемый `opencode serve` (демон) | Один долгоживущий процесс; сессия на запрос | Те же дельты (F-19); нет холодного старта (фоновый `serve --service` уже работает, F-20) | Один набор env прокси на все запросы: общий IP упирается в дневной лимит (F-23, F-32); пароль на демон | Как в A1 | Общая БД и общий процесс, RSS 439 MiB у существующего демона (F-20); падение демона роняет все запросы | Тот же фейковый сервер; нужен супервизор и перезапуск | выполнимо с условиями; ротация IP не сохраняется без доработки (OPEN-06) |
| B: прямой OpenAI-совместимый HTTP-SSE к Zen | По образцу Google Direct (F-16): `http.client`, `readline`, дельты `reasoning_content` в реальном времени | Минимальная: без CLI, без БД, дельты как у апстрима (георутер отдаёт реалтайм, F-19) | Анонимный вызов без заголовков дал 429 `FreeUsageLimitError` напрямую и через пул (F-24, F-25); нужные заголовки или ключ неизвестны (OPEN-05); у `opencode` провайдера нет `apiKey` (F-27) | Не требуется: инструментов нет, эмуляция через `<tool_invoke>` остаётся | Нет SQLite и дочерних процессов | Лучшая: подмена HTTP-сервера, без `FAKE_OPENCODE` | выполнимо с условиями; осуществимость не доказана (OPEN-05) |
| C: гибрид | Приоритетный быстрый транспорт (A1 или B), при `ServeUnavailable`-подобном отказе тихий откат на legacy `opencode run`, как в muse-bridge | Реалтайм там, где транспорт доступен; legacy при отказе | Совмещает ограничения выбранных транспортов | Совмещает | Совмещает | Прецедент в репозитории: serve основной, exec запасной (F-40, F-41); fake-CLI тесты остаются на legacy-пути | выполнимо; объём работ максимальный |

Наблюдения для решения (факты, не выбор):
- Только A1/A2/B дают реалтайм на здоровом вызове; L не даёт, но самый дешёвый и закрывает RC-2/RC-3 (поэтапная поставка возможна: L затем A1/B/C).
- Квота Zen исчерпана на момент анализа (F-23): живая приёмка и PoC варианта B возможны после сброса около 03:00 MSK 2026-10-26.
- Совместимость с тестами: muse-bridge сохраняет exec-путь как резерв (F-40); у `opencode-zen-bridge` три модуля подменяют `OPENCODE_BIN` скриптом с событиями формата `run --format json` (F-43).
- Размер объёма ретраев и `_StdoutFeed` уже рассчитан на потоковые события (F-14); `step_finish` в `run` теряется (F-18), в serve есть `session.step.ended` с `tokens` (F-19).

## 5. Инвентарь контрактов (as-is)

| Интерфейс | Протокол | Направление | Аутентификация | Лимиты и режимы отказа | Тестовый контур |
|---|---|---|---|---|---|
| `POST /v1/chat/completions` моста | HTTP SSE OpenAI (`stream:true`, `include_usage`) | Ingress от DSH | Bearer-ключ моста (значение не фиксируется) | слоты 6, ожидание 15 с, 12 ждущих, 503 при переполнении (F-13) | `tests/_http.py`, `test_step_interruption.py` (F-43) |
| `opencode run --format json` | stdout JSON-строки | Egress процесса | Нет (локальный CLI, белый список env) | потолок 1800 с, нет watchdog (F-09) | `FAKE_OPENCODE` (F-43) |
| `opencode serve` v2 | HTTP + SSE, Basic `opencode:<пароль>` | Egress | случайный пароль на процесс или `OPENCODE_SERVER_PASSWORD` (F-21) | старт 109 мс, API по OpenAPI (F-20, F-22) | тестового фейка нет |
| `model_georouter` :10830 | OpenAI-совместимый HTTP | Egress | нет у провайдера `opencode` (F-27) | `headers_timeout` 120 с, `inactivity_timeout` 300 с, 80+80 слотов, 3 pre-send повтора (F-26) | нет |
| Zen upstream `opencode.ai/inference/openai/v1` | OpenAI SSE | Egress | анонимный, дневной лимит (F-23..F-25) | `FreeUsageLimitError` 429 с `Retry-After` | нет |
| DSH `openai-completions` | SSE потребитель | Ingress | — | `streamIdleTimeoutMs` 1900000, `maxRetries` 0 (F-35) | живой DSH |

## 6. NFR-набросок (наблюдаемые величины)

- Нагрузка: 517 завершённых запросов за день, `deepseek-v4.1-flash-free` 44 (median 7.10 с, max 85.65 с) (F-32); пик параллелизма 6 (F-13).
- Задержка legacy: `step_start` 1.3-2.5 с, весь ответ 3.3-5.2 с одним блоком (F-17); реалтайм-путь serve: первая дельта размышления 1.8 с (F-19).
- Хвост: два запроса молчали 780-856 с с `out_chars=0` (F-30, F-31); `startup_gate_timeout` 72 за день (F-32).
- Ресурсы: мост RSS 22 MiB, 36 дескрипторов (F-29); idle serve 152 MiB, 20 дескрипторов (F-20); БД 2.27 GB (F-28).
- Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.

## 7. Конверт `HL-ENV/v1` (46 канонических полей `REQUIRED_HL_ENV_FIELDS`)

Единицы СИ. Источники в комментариях; значения, не измеренные под нагрузкой, помечены `оценка`.

```yaml
schema: HL-ENV/v1
required_hl_env_fields_46:
  P_steady: 1                      # один локальный демон LaunchAgent, F-34
  P_hpa_max: 1
  maxSurge_pct: 0.0
  maxSurge_abs: 0
  maxUnavailable_pct: 0.0
  maxUnavailable_abs: 0
  P_terminating_overlap: 0
  P_live: 1
  P_avail_min: 1
  W: 1                             # один Python-процесс ThreadingHTTPServer, F-12
  N_proc: 1
  N_proc_steady: 1
  N_proc_avail_min: 1
  CPU_limit_per_pod: 2.0           # бюджет рабочей станции, оценка
  kappa_skew: 1.0
  u_bg_worker: 0.02                # оценка
  U_pod_sidecars: 0.25             # дочерние процессы opencode, оценка
  Mem_limit_per_pod: 2147483648    # бюджет демона 2048 MiB, оценка
  Mem_rss_worker_max: 67108864     # 64 MiB; измерено 22 MiB, F-29
  Mem_shared_max: 1207959552       # 6 дочерних процессов по 192 MiB; idle serve 152 MiB, F-20
  RPS_peak: 0.2                    # 517 запросов за день, F-32
  A_max: 3                         # MAX_TOTAL_SPAWNS, F-11
  SLA_p99_s: 180.0                 # max наблюдаемый 85.65 с, F-32
  N_entities_max: 64
  Limit_dep_share_d: {georouter: 80, opencode_local_db: 10}   # georouter F-26; значение БД допущение эталона, OPEN-08
  Limit_dep_rps_d: {opencode_spawn: 1.0}                      # SPAWN_RATE_PER_S, F-11
  W_fetchers_d: 1
  J_init_s_d: 12.0                 # STARTUP_GATE_S, F-10
  J_pod_s_d: 12.0
  T_poll_s_d: 15.0                 # KEEPALIVE_INTERVAL_S, F-04
  K_calls_d: 1
  T_base_s_d: 0.5                  # RETRY_BACKOFF_BASE_S, F-11
  T_cap_s_d: 2.0                   # RETRY_BACKOFF_CAP_S, F-11
  Max_stale_age_s_c: 0.0           # кэшей нет
  Min_healthy_ratio: 1.0
  B_retry_max: 6                   # RETRY_BUDGET_MAX, F-11
  min_reserve_retry_rps: 0.05      # RETRY_BUDGET_RESERVE_RPS, F-11
  FD_worker: 128                   # измерено 36 при active=0, F-29; запас под 6 потоков
  ulimit_n: 65536                  # launchctl limit maxfiles, F-29
  lambda_new_conn_per_pod_s: 0.6
  C_active_in_scope_s: 12
  N_pods_in_scope_s: 1
  Port_range_size_s: 16384         # эфемерный диапазон 49152-65535
  T_hold_s_s: 60.0
  SNAT_ips_count_s: 1
  HOTPATH_MODULES: "bridges/opencode-zen-bridge/server.py"
operational_profile:
  threads_per_worker: 12           # до 6 обработчиков и до 6 читателей stdout/SSE
  stdout_queue_max: 4096           # F-14
  ttft_visible_target_s: 1.0       # допущение, OPEN-11
  ttft_first_delta_target_s: 3.0   # допущение, OPEN-11; наблюдение serve 1.8 с, F-19
  first_event_watchdog_s: 20.0     # допущение, OPEN-11
  first_token_watchdog_s: 60.0     # допущение, OPEN-11
  stall_watchdog_s: 60.0           # допущение, OPEN-11
  client_gone_detect_s: 5.0        # допущение; сейчас 24.4 с, F-33
  keepalive_interval_s: 15.0       # F-04
  total_deadline_s: 1800           # TIMEOUT_S, F-09
  max_total_spawns: 3              # F-11
  startup_gate_s: 12               # F-10
  startup_wait_s: 5.0              # F-10
  bulkhead_max_concurrent: 6       # F-13
  slot_wait_s: 15.0                # F-13
  slot_max_waiters: 12             # F-13
  graceful_stop_s: 5               # SIGTERM затем SIGKILL, F-14
  serve_ready_s: 0.109             # F-20
```

Замыкание памяти (`HL-ENV-01`): `W × Mem_rss_worker_max + Mem_shared_max = 64 MiB + 1152 MiB = 1216 MiB ≤ 0.80 × 2048 MiB = 1638.4 MiB` (PASS, оценка). Для варианта A2 (общий демон, 439 MiB, F-20) вклад меньше.

## 8. Гейты Highload & Resilience (7 канонических + оси брифа)

### 8.1. Канонические гейты `architecture.md` (`#hl-env-and-four-gates-ssot`)

- `C-MULT/v1`:
  - `C-MULT-I1`: `1 × 1 × 6 = 6 ≤ 0.60 × 80 = 48` для георутера (F-26) — PASS; для локальной БД предел неизвестен (OPEN-08), поэтому ограничителем остаются `_StartupGate`, `SPAWN_RATE_PER_S` и семафор слотов (F-10, F-11, F-13).
  - `C-MULT-I2`: очереди ограничены (`_StdoutFeed` 4096, слоты 6, ждущих 12, ожидание 15 с) (F-13, F-14) — PASS; новый SSE-читатель обязан иметь такой же предел.
  - `C-MULT-I3`: семафоры и замки — синглтоны процесса (`W=1`) (F-12) — PASS.
  - `C-MULT-I4`: освобождение слота и остановка процесса в `finally` (F-14) — PASS как as-is; новые ресурсы (сессия serve, SSE-сокет) должны освобождаться там же.
  - `C-MULT-I5`: `FD_worker = 128 ≤ 0.70 × 65536`; порты `0.6 × 1 × 60 + 12 = 48 ≤ 0.50 × 16384 = 8192` — PASS (оценка).
- `S-HERD/v1`:
  - `S-HERD-I1`: серия холодных стартов сериализуется `_StartupGate` (F-10); у A1 старт сервера 109 мс (F-20).
  - `S-HERD-I2`: Full Jitter 0.5/2.0 уже в коде (F-11); повторы по watchdog обязаны использовать его.
  - `S-HERD-I3..I5`: N/A, поллеров Control Plane, `If-None-Match` и `singleflight` в мосте нет (граф вызовов as-is: `do_POST` → `_stream_sse`/`_serve_json` → запуск процесса); доказательство `git diff` предоставляет Architect после дизайна.
- `H-CPU/v1`:
  - `H-CPU-I2`: регулярные выражения компилируются при импорте (F-06, F-11); разбор SSE-дельт не должен вызывать `re.compile` в цикле.
  - `H-CPU-I3`: путь с выключенной новой функцией должен возвращаться за `O(1)` (kill-switch, REQ-003).
  - `H-CPU-I5`: оценка `0.02 + 0.2 × (0.02 + 3 × 0.05) = 0.054 ≤ 0.70` (PASS, не измерено); поток serve даёт около 10 событий в секунду на запрос (F-19), то есть до 60 разборов JSON в секунду на 6 запросах.
  - `H-CPU-I1`, `H-CPU-I4`: N/A (индексов маршрутизации и event loop нет).
- `R-BULK/v1`:
  - `R-BULK-I1`: вспомогательные ожидания `3 × 5.0 с (gate) + 0 + 1.0 + 2.0 = 18.0 с ≤ 0.30 × 180 = 54 с` (PASS); наихудший случай с watchdog первого события `3 × (20 + 5) + 3 = 78 с ≤ 180 с`.
  - `R-BULK-I2`: потолок запусков 3, бюджет повторов 6, слоты 6 (F-11, F-13) — PASS.
  - `R-BULK-I3`: классификация транзиентных и детерминированных ошибок существует (F-11, `_is_transient_stream_error`); новые причины watchdog относятся к транзиентным.
  - `R-BULK-I4`, `R-BULK-I5`: N/A (пула прокси-нод с health-ранжированием и мульти-тенантных пулов в мосте нет; прокси из пула — подстановка в env, F-15).
- `T-LIFE/v1`: каждый процесс и его читатель закрываются `_stop_proc` в `finally` (F-14); для A1/A2 добавляются `interrupt`, `DELETE` сессии и `killpg` (F-22).
- `O-EXIT/v1`: строка выхода на каждом `do_POST` уже есть (F-32); расширение полями — REQ-016.
- `M-SEM/v1`: N/A на этапе анализа (единый пул слотов `_slots`, F-12); подтверждение `git diff` и графа вызовов — за Architect.

### 8.2. Оси из брифа (`R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND`)

В каноне этих меток нет (OPEN-15). Трактовка аналитика (допущение) и статус по фактам:

| Ось | Трактовка | Статус по фактам |
|---|---|---|
| `R-OUT` | исходы запроса и повторы (`exit_reason`, потолок A_max) | потолок есть (F-11); новые причины watchdog требуют кодов (REQ-016) |
| `M-CONF` | конфигурация и kill-switch новой функции | переменные окружения как у `STEP_RECOVERY` (F-11), REQ-003 |
| `F-DEG` | деградация: отказ быстрого транспорта не должен ломать ответ | прецедент serve→exec в muse-bridge (F-40); fail-open для статусных строк, fail-closed для политики инструментов (REQ-012) |
| `S-SEC` | секреты, пароль serve, изоляция инструментов | пароль случайный на процесс (F-21), `apiKey` не выгружался (F-27), REQ-015 |
| `X-BOUND` | границы процессов и ресурсов (killpg, FD, сессии) | F-14, F-29, REQ-008 |

## 9. Non-Goals

- Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).
- Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.
- Не модифицировать текст размышления модели ради превью (OPEN-13).
- Не менять модель, список моделей, логику выбора эффорта и каталог Zen.
- Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.
- Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.

## 10. Forbidden Scope

- Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.
- Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.
- Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.
- Использование `security find-generic-password`.
- Правка `opencode.db` и общего каталога состояния `opencode` напрямую.
- Коммит в `main`, `master`, `dev`; merge выполняет человек.

## 11. Маппинг в `architecture-packet.json`

- `evidence`: `F-01..F-49` (ledger).
- `blocking open questions`: пусто.
- `assumptions`: `OPEN-04..OPEN-17` с рабочими допущениями из `open-questions.md`.
- `boundaries/contracts`: раздел 5.
- `quality scenarios` (baseline): первая видимая строка до 1.0 с; первая дельта размышления до 3.0 с; пауза до 15 с; молчание до 20 с (допущения OPEN-11), текущие значения в разделе 6.
- `risks`: R1 — прямой Zen без заголовков не осуществим (OPEN-05); R2 — потеря ротации IP при общем демоне (OPEN-06); R3 — встроенные инструменты `opencode` исполнятся при неверной политике (OPEN-07); R4 — контенция SQLite при параллельных serve (OPEN-08); R5 — квота Zen блокирует живую приёмку до около 03:00 MSK 2026-10-26 (F-23); R6 — дубли размышления при повторах (OPEN-14); R7 — красная базовая линия блокирует Full Suite Gate (OPEN-04).

## 12. Обратный канал в требования

Противоречий фактов с REQ-ID нет. Расхождение с брифом: в `tests/` 17 модулей `test_*.py`, а не 16 (F-42); ссылка на «16 модулей» в постановке неточна, на объём работ не влияет.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/evidence-ledger.md sha256=2a5c9f7f8a8fc20573d69a4617da87bdfbf1f57e70681e7036ece27541fe0367
# Evidence Ledger: zen-realtime-reasoning (opencode-zen-bridge, реалтайм-размышление)

Дата сбора: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Роль: System Analyst (Stage 1).
Формат факта: `[F-NN] (FACT-0NN) утверждение | источник | YYYY-MM-DD`. Секреты не выносятся
(пароль `opencode serve`, `apiKey`, креды ProxyRack, логины пула не воспроизводились и не сохранялись).
Пути с `~/` — домашний каталог. Пути без `~/` — относительно корня репозитория
`bridges/opencode-zen-bridge/`, если не указано иное.
Эмпирические PoC-скрипты и логи аналитика: `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`
(вне репозитория; код продукта не менялся).

## 1. Код моста (повторная сверка по исходнику)

[F-01] (FACT-001) Мост запускает `opencode run -m <provider>/<model>#<variant> --thinking --format json` и добавляет `--standalone` для Zen-маршрутов в режиме каталога `dynamic`; промпт передаётся через stdin, процесс стартует в новой сессии процессов (`start_new_session=True`) | server.py:1146-1161, 966-969, 1617-1649 | 2026-10-25
[F-02] (FACT-002) `parse_opencode_event` отображает `reasoning` в `delta.reasoning_content`, `text` в `delta.content`, `step_finish` в usage, `error` в `{statusCode,message}`; любые другие типы (в т.ч. `step_start`, `part.delta`) возвращаются как `(etype, {})` и в SSE не попадают | server.py:2417-2462 | 2026-10-25
[F-03] (FACT-003) `Handler._stream_sse` отправляет HTTP 200 с заголовками SSE и первый чанк `{"role":"assistant","content":""}` до `_StartupGate`, spawn и чтения stdout | server.py:3312-3327, 3399-3412 | 2026-10-25
[F-04] (FACT-004) Единственная «живость» стрима до первого токена — `send_keepalive`: чанк `{"content":""}` после `KEEPALIVE_INTERVAL_S=15.0` с без строк stdout; сам чанк не содержит ни `reasoning_content`, ни непустого `content` | server.py:49, 3437-3450, 865-952 | 2026-10-25
[F-05] (FACT-005) События `reasoning` пишутся клиенту и сбрасываются (`flush`) сразу при получении строки; события `text` идут в `ToolCallParser.feed` (при `emulate_tools`) либо напрямую в `emit_content` | server.py:3462-3493 | 2026-10-25
[F-06] (FACT-006) `ToolCallParser` отдаёт текст вне тегов сразу и удерживает только хвост-префикс открывающего тега (не длиннее `len("<tool_invoke>")-1` символов) и открытый незакрытый блок `<tool_call>`/`<tool_invoke>`; инкрементальность поддерживается, если дельты приходят по частям | server.py:2213-2338 (в т.ч. `_drain` 2252-2297, `_pending_prefix` 2316-2323) | 2026-10-25
[F-07] (FACT-007) `_render_turn` и `_messages_to_prompt` используют у assistant-реплик только `content` и `tool_calls`; поле `reasoning_content` входящих сообщений в промпт модели не попадает | server.py:1848-1888 | 2026-10-25
[F-08] (FACT-008) Конфиг `opencode` для дочернего процесса по умолчанию: `permission {"*":"ask"}` и `provider.opencode.options.baseURL=http://127.0.0.1:10830/v1` | server.py:228-231 | 2026-10-25
[F-09] (FACT-009) В `server.py` нет ни TTFT-watchdog, ни watchdog первого события, ни watchdog паузы между чанками: поиск без учёта регистра по словам ttft, first_token, first_byte, stall, idle_timeout, FIRST_EVENT даёт 0 совпадений; единственный потолок ожидания — общий `deadline = now + TIMEOUT_S` (1800 с) | server.py:46, 3450, команда grep от 2026-10-25 | 2026-10-25
[F-10] (FACT-010) `_StartupGate.acquire` ждёт замок `STARTUP_WAIT_S=5.0` с и затем идёт без замка (fail-open); замок держится до первой stdout-строки либо `STARTUP_GATE_S=12` с; `gate.release()` вызывается на любую первую строку, включая `step_start` | server.py:1197-1236, 3399-3411, 3451 | 2026-10-25
[F-11] (FACT-011) Потолки повторов: `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT=min(3,MAX_TOTAL_SPAWNS-1)=2`, `NATIVE_RETRY_LIMIT=2`, Full Jitter `RETRY_BACKOFF_BASE_S=0.5`/`RETRY_BACKOFF_CAP_S=2.0`, `SPAWN_RATE_PER_S=1.0` и `SPAWN_BURST=1.0`, `_RetryBudget`: ёмкость 6, +0.20 за запрос, +0.05 в секунду | server.py:277, 287-298, 309-314, 1340-1368, 1471-1535 | 2026-10-25
[F-12] (FACT-012) Защиты процесса (`_Resilience`: слоты, spawn-limiter, retry-budget, breaker) создаются по одному экземпляру на `Server`; прод передаёт модульный `_DEFAULT_RESILIENCE`, каждый тестовый `Server` получает собственный набор | server.py:1458-1470, 3989-3996 | 2026-10-25
[F-13] (FACT-013) `MAX_CONCURRENT` по умолчанию в коде равен 2 (`OPENCODE_ZEN_BRIDGE_MAX_CONCURRENT`), деплой отвечает `max_concurrent=6`; `SLOT_WAIT_TIMEOUT_S=15.0`, `MAX_SLOT_WAITERS=12` | server.py:50, 303-305; GET http://127.0.0.1:9883/health от 2026-10-25 22:45 MSK | 2026-10-25
[F-14] (FACT-014) `_stop_proc` завершает группу процессов (`killpg` SIGTERM, затем SIGKILL); `_StdoutFeed` — daemon-поток с очередью `maxsize=4096`, `_STDOUT_POLL_S=0.25` | server.py:848-862, 865-952 | 2026-10-25
[F-15] (FACT-015) Для standalone окружение дочернего процесса собирается по белому списку, прокси берётся из пула ProxyRack по кругу на каждый новый spawn, loopback идёт мимо прокси; `start.sh` включает `OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`, если файл пула непуст | server.py:1047-1082, 1093-1131; start.sh:24-31 | 2026-10-25
[F-16] (FACT-016) `_stream_google_sse` — существующий прямой HTTP-SSE маршрут без `opencode run`: `http.client`, чтение `resp.readline()`, `ToolCallParser` на дельтах, `emit({"reasoning_content": text})` в реальном времени; прецедент прямого маршрута для Option B | server.py:3127-3266 (reasoning emit около 3219) | 2026-10-25

## 2. Эмпирика `opencode` v2.1.2 (Zone B и PoC аналитика)

[F-17] (FACT-017) `opencode run --format json --thinking` во всех четырёх режимах (PIPE/PTY × фоновый сервис/`--standalone`) выдаёт 3 события (`step_start`, `reasoning`, `text`) плюс `step_finish` не всегда; единственный `reasoning`-блок приходит в тот же момент, что и `text` (разница 0.00-0.17 мс); тишина stdout после `step_start` 1904-2716 мс; полное время 3282-5213 мс (таблица T1) | explorer-zone-b.md §1 (замер 2026-10-25 22:2x MSK) | 2026-10-25
[F-18] (FACT-018) Причина F-17 в бинарнике `~/.opencode/bin/opencode`: обработчик событий `opencode run` подписан на `session.reasoning.ended` и `session.text.ended` и игнорирует `session.reasoning.delta` и `session.text.delta`; `pty.openpty()` грануляцию не меняет; `step_finish` теряется, когда `session.wait` возвращается раньше слива `session.step.ended` | explorer-zone-b.md §2 | 2026-10-25
[F-19] (FACT-019) `opencode serve` (v2) отдаёт реалтайм: `GET /api/event` (SSE) — `session.execution.started` 233 мс, `session.reasoning.started` 1710 мс, первая `session.reasoning.delta` 1811 мс (58 симв.), 10 дельт размышления (434 симв.) с интервалами min 105.64 / median 127.25 / max 304.32 мс, первая `session.text.delta` 3261 мс, 17 text-дельт (median 114.49 мс), всего 53 события, завершение 5558 мс (таблица T1) | explorer-zone-b.md §1, §3 | 2026-10-25
[F-20] (FACT-020) Сервер `opencode serve --port P --hostname 127.0.0.1` готов к запросам за 109 мс (мой замер 109 мс; Zone B: 109-117 мс); простаивающий процесс занимает RSS 152 MiB и 20 дескрипторов; фоновый `opencode serve --service` (PID 43288, аптайм 3 суток) занимает RSS 439 MiB | sa-poc/serve_sse.py, ps -axo, lsof от 2026-10-25 22:4x MSK | 2026-10-25
[F-21] (FACT-021) Без пароля эндпоинты `opencode serve` (проверено на `GET /openapi.json`) отвечают 401; при старте без заданного пароля сервер печатает случайный пароль в вывод процесса (stdout/stderr); переменная окружения `OPENCODE_SERVER_PASSWORD` принимается, схема Basic-auth с логином `opencode` | sa-poc (curl --noproxy, 401 без заголовка, 200 с заголовком) от 2026-10-25 | 2026-10-25
[F-22] (FACT-022) OpenAPI `opencode serve` v2.1.2 содержит: `GET /api/event`, `POST /api/session` (поля `model`, `location`, `agent`, `permissions` типа `Permission.Ruleset`, `metadata`), `POST /api/session/{id}/prompt` (`text`, `files`, `delivery`, `resume`), `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`, `GET/POST /api/session/{id}/permission` и `/permission/{requestID}/reply`, `GET /api/session/active`, `POST /api/session/{id}/generate` | sa-poc: разбор /openapi.json v2.1.2 от 2026-10-25 (281456 B) | 2026-10-25
[F-23] (FACT-023) PoC аналитика через `opencode serve` (без standalone-прокси, с конфигом `permission {"*":"deny"}` и `baseURL` georouter) в 22:4x MSK завершился `session.step.failed`/`session.execution.failed` с `provider.free-limit` («Free usage limit reached») на 841 мс: анонимный дневной лимит Zen для IP хоста исчерпан, реалтайм-замер повторить нельзя до сброса | sa-poc/poc_serve.log | 2026-10-25
[F-24] (FACT-024) Прямой POST на `http://127.0.0.1:10830/v1/chat/completions` (georouter) без заголовка `Authorization` вернул HTTP 429 `FreeUsageLimitError`, `Retry-After: 15418` с (около 4 ч 17 мин); первый замер ответил за 2565 мс | sa-poc/poc_georouter.log | 2026-10-25
[F-25] (FACT-025) Прямой POST на `https://opencode.ai/inference/openai/v1/chat/completions` через CONNECT-туннель на запись пула ProxyRack без `Authorization` вернул HTTP 429 `FreeUsageLimitError` за 851 мс (1 выборка): способность прямого анонимного HTTP-SSE получать токены не подтверждена | sa-poc/poc_direct_zen_proxy.log | 2026-10-25
[F-26] (FACT-026) `model_georouter` (PID 29937, `127.0.0.1:10830`) конфиг: `direct_slots=80`, `proxy_slots=80`, `connect_timeout=12.0`, `headers_timeout=120.0`, `inactivity_timeout=300.0`, `pre_send_retries=3`, `total_egress_deadline=40`; маршрутизация по префиксу модели в пулы `direct`/`route-de`/`route-uz` | ~/.config/model-georouter/config.json (значения без секретов) | 2026-10-25
[F-27] (FACT-027) В `~/.config/opencode/opencode.json` у провайдера `opencode` задан только `options.baseURL=http://127.0.0.1:10830/v1` (поля `apiKey` нет); у `opencode-go` и `opencode-go-claude` есть `apiKey` (значение не выгружалось) | ~/.config/opencode/opencode.json (обход ключей с маскированием) | 2026-10-25
[F-28] (FACT-028) `~/.local/share/opencode/opencode.db` занимает 2 269 175 808 B (2.27 GB); `opencode run --help` v2.1.2 содержит `--standalone`, `--server <url>`, `--format` (значения default или json), `--thinking`, `--auto`; режима потокового вывода дельт у `run` нет | ls -l, opencode run --help от 2026-10-25 | 2026-10-25
[F-29] (FACT-029) Процесс моста (PID 85809): RSS 22 MiB, 36 открытых дескрипторов при `active=0`; `launchctl limit maxfiles` = 65536 (soft) и unlimited (hard) | ps, lsof, launchctl limit от 2026-10-25 22:4x MSK | 2026-10-25

## 3. Рантайм и инцидент (Zone D)

[F-30] (FACT-030) Запрос 22:16:12 MSK (`session-423ca27f`, ход 2, шаг 5, `prompt_chars=103088`): `opencode run -m opencode/deepseek-v4.1-flash-free#high --thinking --format json --standalone` (PID 11465) и дочерний `opencode serve --stdio --port 0` (PID 11488) молчали более 780 с (`out_chars=0`), у PID 11488 не было исходящих TCP-соединений; SSE-keepalive держал сокет DSH; на 22:45 MSK `/health` показывает `active=0`, процессов `opencode run` нет | explorer-zone-d.md §2, ps -axo от 2026-10-25 22:45 MSK | 2026-10-25
[F-31] (FACT-031) Запрос 22:12:57 MSK (`prompt_chars=108666`, PID 77098) молчал 856 с до `HTTP None: ECONNRESET`; повтор 1/2 (PID 25610/25611) завис на узле ProxyRack с нулём вывода | explorer-zone-d.md §2 | 2026-10-25
[F-32] (FACT-032) Сводка 2026-10-25 по `bridge.log`: 517 завершённых запросов (ok 509, client_gone 4, upstream_failed 4); `deepseek-v4.1-flash-free` 44 завершённых (ok 40), median 7.10 с, max 85.65 с; `startup_gate_timeout` 72 за день (grep -c без фильтра даты по текущему `bridge.log` даёт 99); `Free usage limit` 22; `ECONNRESET` 9; `stream retry` 10 | explorer-zone-d.md §2; grep -c на ~/.dsh/bridges/opencode-zen-bridge/logs/bridge.log | 2026-10-25
[F-33] (FACT-033) Ход 1 (22:15:31 MSK) на `opencode-zen-bridge`: 0 чанков за 10.7 с, пользователь переключился на `deepseek-account` (TTFT 0.71-0.88 с); мост заметил отключение клиента только через 24.4 с на keepalive (`duration_s=35.25`, `out_chars=0`) | explorer-zone-d.md §3 | 2026-10-25
[F-34] (FACT-034) Развёрнутый `~/.dsh/bridges/opencode-zen-bridge/server.py` совпадает с репозиторием (200 835 байт, mtime Oct 24 21:39); процесс слушает :9883 под LaunchAgent `com.user.dsh-opencode-zen-bridge`, `uptime_s=90313` на 2026-10-25 22:45 MSK | explorer-zone-d.md §1; /health от 2026-10-25 | 2026-10-25

## 4. Потребитель: DSH Desktop

[F-35] (FACT-035) Профиль DSH: `opencode-zen-bridge` — `api: openai-completions`, `baseURL: http://127.0.0.1:9883/v1`, `timeoutMs` и `streamIdleTimeoutMs` по 1900000, `retryPolicy.maxRetries: 0`, `reasoningEffort: high`, запрос с `stream: true` и `stream_options.include_usage` | ~/.dsh/profiles/desktop/cordis.patch.yml:9-14, 76-81, 176-225 (Zone C) | 2026-10-25
[F-36] (FACT-036) Потребитель `@earendil-works/pi-ai` (`openai-completions.js`) на каждый непустой `delta.reasoning_content`/`reasoning`/`reasoning_text` сразу порождает `thinking_start` (один раз) и `thinking_delta`; пустой `delta.content` событий не порождает; теги `<think>` в `content` не разбираются | /Applications/DeepSeek Harness.app/Contents/Resources/app.asar, openai-completions.js L384-425 (Zone C); смещения 116088536-116089722 в app.asar (моя проверка) | 2026-10-25
[F-37] (FACT-037) UI `@deepseek-ai/dsh-client-ui-chat/lib/client.js`: `RunningStatus` «Deep diving for N ···» монтируется при `session.running`; `blockIsVisible` скрывает блок с `text.trim()===""` (строка «Think» не рисуется до первой непустой дельты); `ReasoningRow` свёрнут по умолчанию, inline-превью `⚛ Think · <summary>` берётся из `latestCompletedParagraphFirstLine`, которая требует символ `\n` | client.js L5599-5637, L6134-6217, L7907-7911 (Zone C); app.asar содержит `latestCompletedParagraphFirstLine` 2 раза и `blockIsVisible` 21 раз (моя проверка) | 2026-10-25
[F-38] (FACT-038) При повторной отправке истории DSH кладёт непустые thinking-блоки обратно в assistant-сообщение полем `reasoning_content` (по `thinkingSignature`) и при `requiresReasoningContentOnAssistantMessages` добавляет пустой `reasoning_content`; мост это поле игнорирует (см. F-07) | app.asar openai-completions.js, смещения 116117903-116120153 | 2026-10-25
[F-39] (FACT-039) Журнал сессии DSH `session.v4.jsonl.zstd` хранит события `assistant/attempt` с массивом `stream[]` (по записи на чанк: `time`, `chunk.type`, `chunk.index`, `chunk.blockType`); блоки размышления записаны как тип `reasoning` (20 вхождений в сессии `423ca27f`), у хода 1 шага 1 `stream=[]` — совпадает с нулём чанков | ~/.dsh сессия 423ca27f, `zstd -dc`, разбор ключей без выгрузки текста | 2026-10-25

## 5. Эталон muse-bridge (ADR-0004)

[F-40] (FACT-040) `muse-bridge` использует основной транспорт `muse serve` (класс `ServeRun`, NDJSON JSON-RPC по stdio) и тихо падает на exec-путь при `ServeUnavailable` (в т.ч. «serve spawn failed», «serve stdout closed», «serve read timeout»); `ServeUnavailable` не считается ошибкой запроса | bridges/muse-bridge/server.py:338-339, 2096-2110, 4140-4185 | 2026-10-25
[F-41] (FACT-041) `muse-bridge` пишет живые события в `reasoning_content` через `_live_reasoning_sink` (запись с `LIVE_WRITE_TIMEOUT_S=3.0`, не фатальна), сбрасывает live-префикс на каждую попытку (`_reset_live_for_attempt`) | bridges/muse-bridge/server.py:165, 4150-4156 | 2026-10-25

## 6. Тесты и базовая линия

[F-42] (FACT-042) В `tests/` 17 модулей `test_*.py` (в брифе указано 16) плюс помощники `_fake_cli.py`, `_fixtures.py`, `_http.py`, `live_matrix.py`; всего 378 тестов (`3 failed, 375 passed, 3155 subtests passed in 125.01s`) | ls tests/; /tmp/cel-runs/zen-realtime-reasoning-20261025/baseline_uvx_pytest.log | 2026-10-25
[F-43] (FACT-043) Сценарий fake-CLI: тесты подменяют `server.OPENCODE_BIN` скриптом, который печатает построчно JSON-события формата `opencode run --format json` (`reasoning`, `text`, `step_finish`, `error`, `tool_use`); так работают `test_cli_failure.py:36-95`, `test_native_fallback.py:104-159`, `test_step_interruption.py:67-175`; хелперы `_fake_cli.py`/`_http.py` используют ещё `test_aliases`, `test_catalog`, `test_catalog_reload`, `test_run_env` | tests/*.py (grep OPENCODE_BIN и _fake_cli) | 2026-10-25
[F-44] (FACT-044) Ни один тест не измеряет реальное время прихода чанков: `test_step_interruption.py::_post` читает ответ целиком (`resp.read()`), `test_stream_thinking.py` проверяет только чистые функции (`_map_effort`, `parse_opencode_event`, `format_sse_chunk`) | tests/test_step_interruption.py:191-208, tests/test_stream_thinking.py | 2026-10-25
[F-45] (FACT-045) Базовая линия `uvx pytest -q -p no:cacheprovider tests/` на ветке: красные `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` (2 != 4), `..._stream` (2 != 4), `test_unmapped_then_error_stops_proc_json` (1 != 2); запуск запуск с командой `pytest` (`Failed to spawn: pytest`) и `python3 -m unittest discover` (17 ошибок импорта модулей) базовой линией не являются | baseline_uvx_pytest.log, baseline_pytest.log, baseline_unittest.log | 2026-10-25
[F-46] (FACT-046) Изоляция 1: весь `tests/test_step_interruption.py` отдельно даёт те же три красных теста (`3 failed, 104 passed, 7 subtests passed in 41.29s`), значит причина внутри этого файла, а не в других модулях | sa_iso_file.log | 2026-10-25
[F-47] (FACT-047) Изоляция 2 (`-k` на два теста): `budget_json` красный даже сам по себе — лог `retry denied (incomplete_step): MAX_TOTAL_SPAWNS=3 reached`, `total_spawns=3`, а тест ждёт `_runs()==4` (два повтора unmapped и один повтор незавершённого шага); `unmapped_then_error_stops_proc_json` в этом запуске зелёный | sa_iso_3tests.log; tests/test_step_interruption.py:405-415; server.py:287 | 2026-10-25
[F-48] (FACT-048) Красный `unmapped_then_error_stops_proc_json` и меньшие значения `total_spawns` в полном прогоне вызваны исчерпанием общего `_RetryBudget` (лог `retry denied (unmapped): retry budget exhausted`): класс `TestStepInterruptionLive` поднимает один `Server` в `setUpClass`, а бюджет ёмкостью 6 с пополнением 0.20 за запрос расходуется ретраями предыдущих тестов; результат зависит от порядка и времени (`+0.05` токена в секунду) | baseline_uvx_pytest.log (строки с `retry budget exhausted`); tests/test_step_interruption.py:154-166; server.py:1340-1368 | 2026-10-25
[F-49] (FACT-049) `grep MAX_TOTAL_SPAWNS tests/*.py` даёт 0 совпадений: ни один тест не меняет константу потолка; `MAX_TOTAL_SPAWNS` введён коммитом `6839125`, ожидание `_runs(), 4` добавлено коммитом `d452fc9` (`git log -S`) | git log -S от 2026-10-25 | 2026-10-25

## Таблица T1. Тайминги `opencode` (Zone B, модель `opencode/deepseek-v4.1-flash-free`, variant `high`, `elapsed_ms`)

| Режим | 1-е событие | 1-й reasoning | reasoning-событий | интервал дельт | 1-й text | событий всего | завершение |
|---|---:|---:|---:|---|---:|---:|---:|
| `run --format json` PIPE, фоновый сервис | 2378.85 | 4850.67 (1 блок, 768 симв.) | 1 | нет | 4850.80 | 3 | 4919.34 |
| `run --format json` PTY, фоновый сервис | 1315.53 | 3219.27 (1 блок, 285 симв.) | 1 | нет | 3219.44 | 3 | 3281.97 |
| `run --format json --standalone` PIPE | 2501.60 | 5137.26 (1 блок, 549 симв.) | 1 | нет | 5137.26 | 3 | 5213.40 |
| `run --format json --standalone` PTY | 2226.36 | 4941.59 (1 блок, 412 симв.) | 1 | нет | 4941.71 | 3 | 5023.95 |
| `opencode serve` v2, `GET /api/event` | 161.22 (`integration.updated`), 233.06 (`execution.started`) | 1810.98 (1-я дельта) | 10 дельт + started + ended | min 105.64, median 127.25, max 304.32 | 3260.64 (17 дельт, median 114.49) | 53 | 5558.06 |

## Сводка покрытия (для DoD)

Всего фактов: 49. Источники воспроизводимы командами и путями из колонки «источник». Факты F-23, F-24, F-25 фиксируют
состояние внешней квоты на 2026-10-25 22:4x MSK и могут измениться после сброса лимита.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/research-plan.md sha256=5cef25c8a8901b241e08ed31ba884d2178cf1ac445ceaf0e70f7c697ea282cbb
# Research Plan: zen-realtime-reasoning (реалтайм-размышление `opencode-zen-bridge` в DSH)

Роль: System Analyst (Stage 1, preset `analyst-teamlead`), тип — feasibility study + as-is обследование, глубина — standard (S2).
Дата: 2026-10-25 (MSK). Ветка `feature/zen-realtime-reasoning`. Артефакты: `analysis/zen-realtime-reasoning/`.
Владелец вывода: владелец продукта (расхождения «ожидали X, оказалось Y» принимает он; финальная архитектура — `architect-software-product`).

## 1. Scope

Запрос владельца: при запуске DeepSeek через `opencode-zen-bridge` (`127.0.0.1:9883`) в DSH видеть размышление в реальном
времени и получать отличную отзывчивость, чтобы было видно, что процесс идёт. Инцидент-образец: сессия `session-423ca27f`,
ход 2 шаг 5 (22:16:12 MSK), экран «Deep diving for 35s ···» без строки `⚛ Think`, затем молчание более 780 с.

В периметре исследования: код `bridges/opencode-zen-bridge/` (`server.py`, `start.sh`, `tests/`), эталон `bridges/muse-bridge/server.py`,
живой `opencode` v2.1.2 (CLI и `opencode serve`), локальный `model_georouter` (:10830), потребитель DSH Desktop (`app.asar`),
рантайм-логи моста за 2026-10-25.
Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).

## 2. Проверяемые гипотезы (исход — в `evidence-ledger.md`)

| Гипотеза | Итог | Основание |
|---|---|---|
| RC-1: `opencode run --format json` буферизует размышление и текст до конца шага, поэтому реалтайма нет даже на здоровом вызове | подтверждена | F-17, F-18 |
| RC-1a: реалтайм-путь на этом хосте существует (`opencode serve` v2 SSE, дельты каждые ~110-130 мс) | подтверждена (замер Zone B), повтор заблокирован квотой | F-19, F-23 |
| RC-1b: прямой анонимный HTTP-SSE к Zen как у Google Direct осуществим без `opencode` | не подтверждена: два PoC дали 429 | F-24, F-25 |
| RC-2: холодный spawn + отсутствие watchdog приводят к немым зависаниям на 13-14 минут | подтверждена по коду и логам | F-09, F-10, F-30, F-31 |
| RC-3: пустые keepalive не показывают ничего, а превью `⚛ Think` требует `\n` | подтверждена | F-36, F-37 |
| Три красных теста базовой линии — загрязнение теста либо реальное взаимодействие бюджетов повтора | обе причины присутствуют | F-47, F-48, F-49 |

## 3. Зоны обследования (веер Wave 1, без пересечений)

- Зона A (код моста и эталон): `server.py`, `muse-bridge` ADR-0004 — отчёт `explorer-zone-a.md`.
- Зона B (контракты и эмпирика `opencode`): CLI vs `opencode serve` vs wire Zen — отчёт `explorer-zone-b.md`.
- Зона C (потребитель): DSH `openai-completions`, `ReasoningRow`, `blockIsVisible` — отчёт `explorer-zone-c.md`.
- Зона D (рантайм): логи, зависшие PID, реконструкция скриншота — отчёт `explorer-zone-d.md`.
- Сверка аналитика (read-only, PoC в `/tmp`): повторная проверка кода по строкам, изоляция красных тестов, прямой HTTP-SSE PoC,
  OpenAPI `opencode serve`, структура журнала сессии DSH, ресурсы процессов.

## 4. Методология

1. Факт или открытый вопрос: каждое утверждение — строка `[F-NN]` с источником и датой, иначе запись в `open-questions.md`.
2. Эмпирика важнее чтения: тайминги `elapsed_ms` снимались по живым процессам, а не выводились из кода.
3. Секреты не выносятся: пароль `opencode serve`, `apiKey`, креды пула ProxyRack не печатались и не сохранялись; PoC использовали временный пароль и порт.
4. Код продукта не менялся; PoC-скрипты и логи лежат в `/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/`.
5. Выбор архитектуры не делается: варианты сравниваются по фактам в `handoff-architect.md`, вердикт — «выполнимо / с условиями / невыполнимо».
6. Квота Zen (`FreeUsageLimitError`) исчерпана на 22:4x MSK, поэтому часть замеров переведена в отложенные вопросы с условием повтора после сброса.

## 5. Реестр спайков

Формат строки: `ID | вопрос | источник | метод | таймбокс | deliverable | критерий закрытия | зависит/блокирует | статус | результат | факт | отметка`
(таймбокс и факт — минуты).

INV-01 | Где мост теряет реалтайм (маппинг событий и SSE-кадрирование) | server.py:2417-2462 и 3312-3493 | чтение кода и сверка с Zone A | 25 | таблица потока событий в ledger | найден участок и порядок отправки чанков | блокирует INV-02 | closed | F-05 | 18 | ok
INV-02 | Выдаёт ли `opencode run --format json` дельты размышления и текста | ~/.opencode/bin/opencode и живые запуски | замеры PIPE/PTY × standalone/сервис | 40 | таблица T1 | показано, что дельт нет и почему | зависит от INV-01 | closed | F-18 | 35 | ok
INV-03 | Реалтайм-путь `opencode serve` v2: события, тайминги, схема API | `GET /api/event`, OpenAPI v2.1.2 | живой SSE-замер и разбор OpenAPI | 40 | схема эндпоинтов и тайминги | задокументированы события и интервалы дельт | зависит от INV-02 | closed | F-19 | 38 | ok
INV-04 | Осуществим ли прямой анонимный HTTP-SSE к Zen (Option B) | server.py:3127-3266 и opencode.ai/inference | PoC через georouter и через CONNECT-туннель пула | 30 | вердикт осуществимости | получены токены либо зафиксирован отказ с причиной | блокирует выбор Option B | open | OPEN-05 | 22 | отказ 429 в обоих PoC, нужен повтор после сброса лимита
INV-05 | Чем ограничено ожидание первого токена (RC-2) | server.py:46, 1197-1236, 3450 и логи Zone D | grep по сторожам и разбор логов | 30 | перечень таймеров и бюджетов | подтверждено отсутствие TTFT и stall watchdog | зависит от INV-01 | closed | F-09 | 20 | ok
INV-06 | Контракт видимости размышления в DSH (RC-3) | app.asar, client.js, openai-completions.js | чтение бандла и подтверждение символов поиском | 30 | контракт `blockIsVisible` и `\n` | найдены условия появления строки Think | независим | closed | F-37 | 24 | ok
INV-07 | Возвращает ли DSH размышление мосту и что с ним делает мост | app.asar и server.py:1848-1888 | поиск `reasoning_content` в бандле и в `_render_turn` | 20 | вывод о безопасности статусных строк | найден путь реплея и точка игнорирования | зависит от INV-06 | closed | F-38 | 14 | ok
INV-08 | Совместимость с fake-CLI тестами и прецедент muse-bridge | tests/*.py и muse-bridge/server.py:338-4185 | grep OPENCODE_BIN и чтение fallback | 25 | карта тестов и паттерн fallback | описаны подмена CLI и паттерн serve-to-exec | независим | closed | F-43 | 19 | ok
INV-09 | Природа трёх красных тестов базовой линии | baseline_uvx_pytest.log и tests/test_step_interruption.py | прогон файла и подмножества, разбор логов | 30 | классификация причин | определены причины каждого из трёх тестов | независим | closed | F-47 | 26 | ok
INV-10 | Изоляция встроенных инструментов `opencode` в режиме serve | OpenAPI `permissions` и `session.tool.*` | чтение схемы, живой прогон заблокирован квотой | 30 | схема сопоставления событий | подтверждена эквивалентность с режимом run | блокирует контракт адаптера | open | OPEN-07 | 12 | схема есть, поведение не прогнано из-за free-limit
INV-11 | Параллелизм, SQLite и ресурсы нескольких процессов serve | opencode.db 2.27 GB и RSS процессов | замер idle RSS и FD, нагрузочный прогон не выполнен | 30 | оценка ресурсов | получены числа под параллельной нагрузкой | зависит от INV-03 | open | OPEN-08 | 10 | измерен только idle serve 152 MiB
INV-12 | Время до первого токена на тяжёлом промпте около 103 KB через serve | сессия 423ca27f и serve | замер после сброса квоты | 20 | таблица TTFT для 100 KB | получен TTFT при `prompt_chars` около 103088 | зависит от INV-03 | open | OPEN-09 | 5 | квота исчерпана до около 03:00 MSK 2026-10-26
INV-13 | Совместимость ротации чистых IP с долгоживущим serve | server.py:1047-1131 и config georouter | чтение кода и конфига | 25 | вывод о маршруте egress | определено, ходит ли serve напрямую либо через georouter | зависит от INV-04 | open | OPEN-06 | 15 | egress georouter известен, поведение прокси у serve не проверено
INV-14 | Инкрементально ли `ToolCallParser` отдаёт `content` при дельтах | server.py:2213-2338 | чтение алгоритма и существующих тестов | 20 | описание удерживаемого хвоста | задан максимум удерживаемых символов | независим | closed | F-06 | 11 | ok

## 6. Состав handoff-пакетов (потребители)

- `handoff-architect.md` — Architect (S2): корневые причины, требования `REQ-*`, сравнение вариантов, `HL-ENV/v1`, гейты, non-goals.
- `handoff-qa.md` — QA и Coder-тесты: red→green сценарии, живой тяжёлый путь, протокол замеров.
- `handoff-dev.md` не готовится: задача класса S2, вход в разработку только через Архитектора (ARCH_GATE).
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md sha256=7e606a52d977e281e8eedc9f0482a0d8d83008a2106fc3d27bee00f3c62d384a
# AGENTS

Ты работаешь в Python backend-проекте на Litestar.

## Язык общения

Пользователь — носитель русского языка, поэтому общение в чате и любой текст, который человек читает глазами (docstrings, комментарии в коде, **описания коммитов**), — на русском. Идентификаторы (имена переменных, функций, классов, файлов) — на английском, как принято в коде.

| Где | Какой язык |
|---|---|
| Сообщения в чате (планы, статус, объяснения, ответы на вопросы) | Русский |
| Сообщения в чате при ошибках/конфликтах | Русский |
| Commit messages — **тэги** (`feat:`, `fix:`, `refactor:`, `chore:`, scope) | Английский — это формат Conventional Commits, парсится changelog-генераторами |
| Commit messages — **описание** после двоеточия | **Русский** — это текст для команды, его читают люди |
| Префиксы `[agent]` / `[manual]` / `[assisted]` | Английский — это маркер, не текст |
| Docstrings в коде | Русский — пользователь читает их в IDE через hover |
| Комментарии в коде (`# объясняет почему`) | Русский |
| Названия переменных, функций, классов, файлов | Английский |

Если поймал себя что начал писать описание коммита или docstring по-английски — остановись и переформулируй по-русски.

Примеры docstring:

✅ Правильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Обрезает URL до max_length символов, добавляя '...' в конце.

    Args:
        url: URL для обрезки.
        max_length: Максимальная длина результата (по умолчанию 50).

    Returns:
        Обрезанный URL с эллипсисом, либо исходный URL если он короче max_length.

    Raises:
        ValueError: Если max_length меньше длины эллипсиса.
    """
    # Если URL уже короткий — возвращаем как есть, без аллокации
    if len(url) <= max_length:
        return url
    ...
```

❌ Неправильно:
```python
def truncate_url(url: str, max_length: int = 50) -> str:
    """Truncate a URL to max_length characters, adding ellipsis at the end.
    ...
    """
    # Return as-is if URL is already short
    ...
```

## Главные правила

1. Сначала прочитай этот файл и релевантные тематические файлы из `.agents/`.
2. **При ошибке — Identify → Assess → Communicate → Solutions.** Не предлагай
   workaround сразу — сначала пойми, почему упало. Severity-уровни и алгоритм
   реакции — в `.agents/agents/error-handling.md`.
3. Не меняй архитектуру проекта без явной причины.
4. Все изменения должны быть минимально достаточными.
5. Любое изменение кода должно сопровождаться проверкой:
   - `uv run ruff check .`
   - `uv run basedpyright`
   - `uv run pytest -q`
6. Для изменений схемы и БД читай `.agents/agents/database.md`.
7. Если меняется публичное API, обнови тесты и README.
8. Перед подготовкой MR прочитай `.agents/agents/mr.md`.
9. Для hotfix обязательно прочитай `.agents/agents/hotfix.md`.
10. На каждый баг должен появиться regression test.
11. Не добавляй зависимости без необходимости.
12. Перед началом работы создай ветку по правилу именования веток проекта.
13. Архитектурные решения с ≥ 2 альтернативами и дорогим откатом оформляй как
    ADR с options analysis (см. `.agents/agents/docs.md`, раздел «ADR-full»).
14. Если задача дата-инженерная (ETL, Airflow DAG, Kafka-воркеры, ClickHouse,
    выгрузка в S3) — читай `.agents/agents/data-engineering.md`.
15. **Согласованный внешний контракт не менять без явного указания в текущей
    задаче.** HTTP/event/data/CLI/SDK, уже согласованные с внешними
    исполнителями, заморожены. «Улучшить», соседняя задача, свой архитектурный
    черновик — не разрешение. Нет явной фразы «измени контракт / breaking /
    обнови схему» → STOP, ASK. Канон: `.agents/agents/scope-and-contracts.md`.
16. **Работать только в рамках своей задачи.** Scope = текущий промпт и текущий
    Jira-KEY. Чужие KEY/MR не открывать, не чинить и не отчитываться по их
    статусу «заодно». Чужой тикет — только если текущая постановка явно
    называет его зависимостью, и тогда только факт зависимости. Канон: тот же
    `scope-and-contracts.md`.
17. **Сдача — через MR на remote, если remote есть.** Не коммитить и не пушить
    в `main` / `master` / `dev`. Коммит живёт на своей ветке, затем push + MR.
    Канон: `.agents/agents/mr.md`. Merge MR — человек, пока не сказано «смержи».
    После merge на remote обязательно обновить локальную target-ветку через
    fast-forward и сверить её `HEAD` с remote. Локальный merge до MR запрещён.

## Подход к работе

Поведение агента управляется **правилами** (`.agents/`) и **алгоритмами**
(`.skills/`). Это конвейер: пришла задача → агент читает релевантный skill →
выполняет шаги → проверки → коммит на своей ветке → MR на remote (если remote есть).
Отдельный «план в чате с ожиданием ОК»
не требуется — `.skills/*.md` уже содержит пошаговый алгоритм.

Если задача сложная и хочется разведать прежде чем писать код:

- **Используй встроенный Plan mode** AI-IDE (в Claude Code, Cursor, Continue,
  Codex CLI). В этом режиме агент только читает файлы и описывает что
  собирается сделать, не пишет и не запускает команды. Это быстрее и дешевле
  чем эмуляция через «покажи план в чате, жди подтверждения».
- **Артефакты задачи** (заметки, отчёты code review, ADR, временные
  результаты) можно складывать в `Tasks/<JIRA-KEY>/` рядом с кодом, чтобы
  при возврате к задаче через день было видно где остановились. Это
  опциональный паттерн, не обязательное «всегда пиши план в md».
- **Architecture-документ** для большой задачи (≥ 1 дня работы, несколько
  модулей, breaking change) — отдельный жанр, см. `.agents/skills/architecture.md`.
  Это не «approval gate», это рабочий артефакт с C1+C2 диаграммами и
  списком задач T1-TN.

В конце задачи — короткий отчёт с URL MR (или явно «remote нет»). Не ждать
фразы «делай MR». Правки оператора — уже после открытого MR, не вместо него.

## Правила именования веток

Ветки должны называться в соответствии с типом задачи и Jira key.

Формат ветки:

`<type>/<JIRA-KEY>-<short-description>`

Где:
- `type` — тип задачи: `feature`, `bugfix`, `hotfix`, `deploy` (релиз/выкат — см. `.agents/skills/devops-release.md`)
- `JIRA-KEY` — идентификатор задачи в Jira, например `PROJ-123`
- `short-description` — короткое описание в `kebab-case`

Примеры:
- `feature/PROJ-123-add-link-archive`
- `bugfix/PROJ-456-fix-empty-title-validation`
- `hotfix/PROJ-789-fix-production-db-timeout`

Правила:
- использовать латиницу, цифры, `/` и дефисы;
- не использовать пробелы;
- не использовать длинные описания;
- для задач из Jira всегда включать Jira key в имя ветки;
- тип ветки должен соответствовать типу задачи.

## Правила коммитов и измерение вклада агента

Каждый коммит должен быть помечен тегом в начале сообщения:

- `[agent]` — diff агента принят без существенных правок (точечные правки имён/форматирования допустимы)
- `[assisted]` — основу сделал агент, но ты переписал значимую часть (логика, структура, >20% строк)
- `[manual]` — код написан вручную без участия агента

Три тега вместо двух нужны потому, что бинарное деление «агент/не агент» врёт в сторону агента: коммит, где ты взял идею из diff и переписал половину, честнее считать как `[assisted]`, а не `[agent]`. Это совпадает с индустриальной практикой: self-reported «AI-assisted» обычно ~40%, но реально AI-authored (без правок) — около 27%.

Формат — Conventional Commits, тэги английские (`feat:`/`fix:`/`refactor:`/`chore:`), **описание после двоеточия — на русском** (см. таблицу «Язык общения» выше).

Примеры:
```
[agent] feat(api): добавить эндпоинт PATCH /links/{id} и тесты
[assisted] refactor(services): переработать сервисный слой после черновика агента
[manual] docs(readme): исправить опечатку
[agent] test(links): добавить regression-тест на валидацию заголовка с пробелами
[manual] chore(deps): обновить pytest до >=9.0.3 для CVE-2025-71176
```

После выполнения каждой задачи выводи итоговый блок:

```
[agent | assisted | manual] <короткое описание задачи на русском>
Files: <количество файлов изменено>
Tests: <добавлено/изменено>
Checks: ruff ✅  basedpyright ✅  pytest ✅
```

## Что делать когда `git commit` падает с pre-commit-хуком

В этом репозитории стоят pre-commit-хуки (ruff, basedpyright, bandit, pip-audit, gitleaks, end-of-file-fixer, trailing-whitespace, и т.д.). Каждый `git commit` прогоняет их **до** создания коммита. Возможны три исхода:

### Исход A: Все хуки `Passed` — коммит создан

Ничего делать не надо. Покажи `git log -1 --stat` в подтверждение.

### Исход B: Хук **автофиксанул** файлы (`files were modified by this hook`)

Так работают `end-of-file-fixer`, `trailing-whitespace`, `ruff format`, `ruff check --fix`. Они **сами** правят файлы и сигнализируют что коммит надо повторить.

Действия:
1. Посмотри какие файлы изменены: `git status`.
2. `git add` этих файлов.
3. `git commit -m "..."` повторно с тем же сообщением.

На втором заходе автофиксы уже применены — хук пройдёт `Passed`.

### Исход C: Хук нашёл **реальную ошибку** (например `basedpyright` или `bandit`)

Это **не** автофикс — это ошибка которую надо понять и исправить. Действия:

1. Прочитай вывод хука. У каждой ошибки есть путь к файлу, номер строки и описание.
2. Открой файл, разбери что не так:
   - **basedpyright**: чаще всего нет аннотации типа, или `Any` где должен быть конкретный тип, или доступ к `None` без проверки. Добавь аннотацию или `# pyright: ignore[<ruleId>]` с комментарием **почему** именно это игнор оправдан.
   - **bandit**: нашёл небезопасную конструкцию (`subprocess(shell=True)`, `yaml.load` без `SafeLoader`, и т.д.). Перепиши на безопасный вариант. Не используй `# nosec` без объяснения.
   - **pip-audit**: CVE в зависимости. Если это твой код добавил эту зависимость — обнови её до fix-версии **отдельным коммитом** (`[manual] chore(deps): обновить <package> для CVE-XXXX`). Если CVE в чужой зависимости которую ты не трогал — см. `.agents/agents/security.md`, секция «pip-audit».
3. Исправь, добавь в индекс (`git add`), коммить снова.
4. Если 3 раза подряд хук падает на одном и том же — остановись, опиши пользователю что именно ошибка говорит и в чём конфликт. Не зацикливайся.

Расширенный алгоритм реакции на любые ошибки (не только pre-commit) — в
`.agents/agents/error-handling.md` (severity Critical/High/Medium/Low + правило
«Identify → Assess → Communicate → Solutions»).

### Что **запрещено** делать

- **`git commit --no-verify`** — обход всех хуков, **никогда**.
- **`SKIP=hook git commit ...`** — пропуск конкретных хуков, **никогда** (единственное исключение — учебный демо в Шаге 6.2 no-rules-variant, описано в `.agents/agents/security.md`).
- **`PRE_COMMIT_ALLOW_NO_CONFIG=1`** — это срабатывает когда `.pre-commit-config.yaml` отсутствует. Если ты эту переменную увидел в подсказке git'а — конфиг **потерян**, восстанови его (`git show HEAD:.pre-commit-config.yaml > .pre-commit-config.yaml`), не обходи.

Подробности — в `.agents/agents/security.md`, секция «Pre-commit хуки — никаких обходов».

## Конвертация документации в Confluence Wiki Markup

Если нужно преобразовать `.md` файл в Confluence Wiki Markup для вставки через `Other macros → Markup → Confluence wiki`:

**Читай файл с правилами перед конвертацией:**
```
.agents/md-to-confluence-rules.md
```

Файл лежит в корне каталога `agents_ skills/` (на уровень выше `agents/`).

Он содержит:
- точные команды bash для конвертации (pandoc + sed + clean-jira-escapes.py)
- таблицу типичных ошибок и их решений
- скрипт проверки результата (три проверки должны вернуть 0)
- структуру папок для готовых `.txt` файлов

**Правило:** никогда не конвертируй вручную и не придумывай правила на лету — всё в `md-to-confluence-rules.md`.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md sha256=906aab1ea3b7cda57b9d788a3dd105f2f6d2e7be159a699eccaf3f93f6bba400
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

<!-- HL-RESILIENCE-GATES-V5 -->
## Обязательные Highload & Resilience гейты (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)

Единый источник правды (SSoT) всех формул, 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` и 21 стоп-кода — `.agents/agents/architecture.md` (`#hl-env-and-four-gates-ssot`). Архитектурный пакет **не может** получить статус `approved` без:

1. **`HL-ENV-01`**: полностью заполненной таблицы из 46 атомарных полей `REQUIRED_HL_ENV_FIELDS` в единицах СИ с указанием источников, проверкой замыкания памяти $W \cdot \text{Mem\_rss\_worker\_max} + \text{Mem\_shared\_max} \le 0.80 \times \text{Mem\_limit\_per\_pod}$ и двойного доказательства для любого `N/A` (`git diff` + транзитивный граф `callers/callees`).
2. **`C-MULT-I1..I5`**: многоролевого и многопоколенческого расчёта соединений $C_{\text{dep}}(d) \le 0.60 \times \text{Limit\_dep\_share}[d]$ по всем ролям (`crawler`, `llm`, `pod_fetcher`, `control_plane`, `migrations_cron`) с учётом $G_{\text{reload}} \in \{1, 2\}$, `BlockingConnectionPool`, `max_waiters <= 2M`, запрета сокетов до `fork()` и бюджета портов/FD (`<= 50%` портов, `<= 70% ulimit_n`).
3. **`S-HERD-I1..I5`**: расчёта пачечного стартового залпа $B_{\text{dep, 1s}}(d) = K_{\text{calls}}[d] \cdot (\lambda_{\text{fetch}}(d) + 4\sqrt{\lambda_{\text{fetch}}(d)} + 4) \le 0.50 \times \text{Limit\_dep\_rps}[d]$ и стационарного поллинга $R_{\text{poll}}(d) \le 0.20 \times \text{Limit\_dep\_rps}[d]$, пересева CSPRNG после `fork()`, `If-None-Match` (`304`), cancellation-safe `singleflight` и политики `Max_stale_age_s[c]`.
4. **`H-CPU-I1..I5`**: доказательства $O(1)/O(\log N)$ индексов на иммутабельном `Snapshot`, отсутствия парсинга/аллокаций на горячем пути (`if not enabled: return` первой строкой), неблокирующей доставки `Snapshot` $\le 2\text{ мс}$ на тик event loop (`mmap` / кооперативные батчи `sleep(0)`) и выполнения трёх неравенств CPU на $P_{\text{avail\_min}}$.
5. **`R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`**: заполненной `Dependency Failure Matrix`, бюджета дедлайнов $\le 0.30 \times \text{SLA}_{\text{p99\_s}}$, Token-Bucket Retry Budget, `Circuit Breaker` (`HALF_OPEN=1`), двухэтапного фильтра `M-SEM/v1` + post-eviction предиката `Panic-Open` ($|V_{\text{healthy}}| - 1 \ge N_{\text{floor}}$) и разделения `origin_health` vs `node_health`.

## Remote-first контракт репозитория

Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и
выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный
merge не считается влитием: сначала merge MR на remote, затем fast-forward
локальной target-ветки. Для read-only роли это требование к handoff, а не
разрешение писать в product worktree, пушить или сливать MR.
ARTIFACT_END>>>
<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/scope-and-contracts.md sha256=25f91ad5fa5cc92f9372e5fe89b0fc0d83f2e8445ba6eb1e966cf78f4e6828cd
# Scope задачи и согласованные внешние контракты

Два жёстких правила. Нарушение — блокирующий FAIL ревью и приёмки, не follow-up
и не «улучшение заодно». Полный текст живёт здесь; скиллы ролей ссылаются
и ставят бинарный пункт в критерии приёмки.

Читать при любой разработке: фича, багфикс, рефакторинг, hotfix, архитектура,
ревью, MR, цикл техлида.

## 1. Согласованный внешний контракт не менять без явного указания

Если контракт уже согласован с внешними исполнителями — другими сервисами,
командами, потребителями HTTP/event/data/CLI/SDK, аналитикой — его нельзя
менять, расширять, сужать, переименовывать и «улучшать», пока текущая задача
явно это не требует.

### Что считается внешним контрактом

- HTTP: method, path, query, request/response DTO, status, error body, auth,
  идемпотентность, версия.
- Событие / очередь / топик: имя, схема, обязательность полей, типы,
  nullability, порядок, совместимость.
- Публичный CLI, SDK, shared-library API.
- Формат файла, протокол, контракт аналитики/событийки.
- Cross-repo зеркало той же схемы.

Внутренняя реализация за неизменной границей (сервис, репозиторий, SQL,
логи, метки, тесты потребителя не ломающие) — не контракт.

### Что считается явным указанием

Фраза в **текущей** постановке (промпт, Jira этой KEY, AC этой задачи):
«измени контракт», «breaking», «обнови схему / DTO / API / событие»,
«согласуй с \<команда/сервис\>». Без такой фразы права менять контракт нет.

Не является указанием:

- «сделай лучше / удобнее / правильнее»;
- соседняя задача, эпик, чужой MR, страница Confluence «как будет»;
- архитектурный документ, который агент сам написал в этом же заходе;
- «потребители подстроятся», «это же совместимо, если добавить поле».

Добавление поля, смена default, переименование, смена типа на совместимый,
новый код ошибки на старом пути — тоже изменение контракта.

### Что делать

1. До кода найти согласованную границу в зоне изменения (спека, Confluence,
   Pydantic/DTO, OpenAPI, схема события, KB `contracts/`).
2. Если задача требует её менять, а в постановке этого нет — **STOP, ASK**.
   Не чинить «заодно». Не предлагать breaking как часть текущей сдачи.
3. Если указание есть — delta контракта, совместимость, потребители и
   verification явным пунктом в AC; иначе задача не готова к коду.

## 2. Работаем только в рамках своей задачи

Scope = текущий промпт и, если есть, текущий Jira-KEY. Чужие задачи не
открывать, не ревьюить, не чинить и не отчитываться по их статусу.

### Запрещено

- Искать и пересказывать статус соседних KEY / MR / стендов «заодно».
- «Пока смотрел, увидел EYE-XXXX — там вот что».
- Тащить скоуп, AC, фикс или рефакторинг из другой задачи в текущий diff.
- Отвечать на вопрос по одной задаче отчётом по доске / эпику / чужим тикетам.

### Можно

- Прочитать другой тикет, только если **текущая** постановка явно называет
  его зависимостью (`blocked by` / `relates` / «зависит от KEY»). Тогда —
  только факт зависимости, не статус-отчёт по чужой работе.
- Ответить по другой задаче, только если владелец **этим промптом** её
  спросил. Это новый запрос, не расширение текущего.

Неясная граница KEY → ASK, не гадать и не ходить по доске.

## Критерии приёмки (копировать в DoD роли)

- [ ] Diff не меняет согласованный внешний контракт, либо в текущей задаче
      есть явное указание это сделать и delta зафиксирована.
- [ ] Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в
      отчёте отсутствуют, если их не спросили.

Нет любого пункта → задача не сдана, ревью `CHANGES_REQUESTED` / приёмка
не ACCEPT.
ARTIFACT_END>>>

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и по исходникам, 2026-10-25):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
⚠️ Используй факт-карту: если сущность в ней есть — она существует, НЕ ставь FAIL по «не существует/устарело». Чего в карте нет и ты не уверен — пиши «не могу проверить», а не FAIL. Перед тем как поставить FAIL «нет X / не описано Y», обязательно перечитай приложенный Architecture Packet целиком и не помечай отсутствующим то, что в пакете уже описано.

РЕЖИМ: architecture
Модификатор режима `architecture`: Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки. Усиленные критерии режима `architecture` (вес ×1.5 на агрегации): 5. АЛЬТЕРНАТИВЫ и 4. РИСКИ.

Инструкции судье Архитектурного Совета Тимлидов (раунд R1, цикл 1, проход a1):
- Если ты уже видел эту задачу, код или артефакты в другой роли — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически.
- Проверь соответствие Architecture Packet каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026`, каждому пункту разделов `Non-Goals` и `Forbidden Scope` из `handoff-architect.md`, а также проверь, что все архитектурные решения опираются на факты `[F-NN]` и каждый использованный факт `[F-NN]` действительно присутствует в приложенном `evidence-ledger.md`.
- Проверь альтернативы: в Architecture Packet должно быть рассмотрено ≥2 альтернативы с явной причиной выбора; если в пакете меньше двух альтернатив или нет причины выбора — ставь FAIL по пункту об альтернативах (критерий 5. АЛЬТЕРНАТИВЫ).
- Проверь архитектурные границы и слои (`boundaries`), внешние контракты (HTTP/event/data/CLI/SDK и пустоту/обоснованность `contract_deltas`), сценарии качества (NFR, тайминги отзывчивости, конверт `HL-ENV/v1` из 46 полей и расчёты `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`), модель угроз и защиту секретов (`threats` / `security`), а также проверяемость `verification_surface` и все пункты `Definition of Done overlay` из `aisdlc-gcge/skills/architecture.md`.
- FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.
- FAIL без оговорок: (1) пакет меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK) без явного указания в постановке задачи / task envelope (`scope-and-contracts.md`); (2) работа или пакет выходит за рамки текущей задачи (чужие Jira-KEY, чужой статус, правки чужих мостов или файлов «заодно»).
- Оцени все 6 критериев `universal-panel` (1. КОРРЕКТНОСТЬ, 2. ПОЛНОТА, 3. РЕАЛИЗУЕМОСТЬ, 4. РИСКИ, 5. АЛЬТЕРНАТИВЫ, 6. СООТВЕТСТВИЕ КОНТЕКСТУ) по единому блоку формата ответа из промпта твоей роли в начале брифа (нет содержательного замечания по критерию — ставь PASS, не выдумывай FAIL).

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-with-architect/references/arch-council.md#L25-L31 sha256=78e4fbebce9b7ba2db216de31e2177c350d031c4f650537a480bbced50fd1874
ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)
Везде, где правила или формат ответа говорят «file:line», допустим один из якорей:
(а) architecture-packet.json:<N> — строка N поданной копии пакета;
(б) architecture-packet.json#<ID> — ID сущности пакета (AD-, QA-, VER-, EVD-, ASM-NNN, ID границы, contract delta, угрозы, риска);
(в) <файл proposals>:<N> — строка приложенного proposal-файла (ADR и др.);
(г) [F-NN] — факт из приложенного evidence ledger.
Цитата правила репозитория, ADR или architecture.md допустима, как и в правилах ниже. Якорь вне перечня или не существующий в поданных файлах ссылкой не считается.
ARTIFACT_END>>>

<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/universal/teamlead-gate/references/council.md#L95-L114 sha256=ea021debac0bcd0bc61f8e34030659060aeac0dd77323259b2205ec904c0c73d
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
```
ARTIFACT_END>>>
Примечание для режима `arch`: в блоке «ПОЛНОТА ВЫДАЧИ» выше слово «diff» читается как «Architecture Packet», а вместо `file:line` используются допустимые якоря (а)–(г) из блока «ЯКОРЯ ПАКЕТА».

Итоговую строку общего вердикта выводи строго с одним из значений `PASS`, `NEEDS WORK` или `RED FLAG` (без точки и комментариев в той же строке), а сразу после неё — обязательные строки покрытия и числа находок из п.6 блока «ПОЛНОТА ВЫДАЧИ».

---
PANEL-NONCE: 8b2ee061b168b4d2
ARTIFACT-SHA256: e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: 8b2ee061b168b4d2» и «ARTIFACT-SHA256: e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02».

BRIEF_END>>>
