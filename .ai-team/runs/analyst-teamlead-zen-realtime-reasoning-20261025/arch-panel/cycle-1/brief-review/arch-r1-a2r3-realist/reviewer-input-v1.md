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
# Чек-лист brief-review: arch R1, cycle 1 (проход a2-r3), run analyst-teamlead-zen-realtime-reasoning-20261025, поколение g1
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
BR-47 [P] | «Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.» | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L103
BR-48 [P] | «Если работа этой роли меняет Git-репозиторий, перед сдачей обязательно прочитать и выполнить `~/Мой диск/skils/ai-sdlc/references/remote-mr-workflow.md`. Локальный merge не считается влитием: сначала merge MR на remote, затем fast-forward локальной target-ветки. Для read-only роли это требование к handoff, а не разрешение писать в product worktree, пушить или сливать MR.» | источник: aisdlc-gcge/skills/architecture.md#Remote-first-контракт-репозитория
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
SK-A-11 [P] | Повторный совет после доработки: полный актуальный Packet + delta + вывод `panel-rework-summarizer`, не только delta. Заголовок/резюме оркестратора не считается выводом panel-rework-summarizer; нет вывода или есть следы прошлого вердикта — missing, не covered | источник: brief-review/references/checklist-sources.md#SK-A
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
SK-A-15 | основание: не D/C1-раунд (текущий раунд — `R1` нового прохода после дельта-пакета, `arch-council.md` §4–§5) | источник: .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/arch/r3/manifest.json
SK-P-database | основание: в скоупе нет SQL/ORM/Alembic/миграций (`database.md` не срабатывает; `opencode.db` запрещено менять напрямую по Forbidden Scope) | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L236
SK-P-data-engineering | основание: в скоупе нет Airflow/Spark/ETL/DAG (`data-engineering.md` не срабатывает) | источник: analysis/zen-realtime-reasoning/handoff-architect.md#L232
## Параметры места
panel: arch | round: R1 | round_type: R1 | hat: realist
hat_prompt: ~/work/universal-panel/prompt-realist.txt
seat_slot: claude-sonnet-5-5-high
seat_kind: panel-judge
seed_recheck_duty: нет | ranked_position: 3 из 4
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
    "packet_sha256": "c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d",
    "verification_surface_sha256": "66e68ca767d07b24b7afacb40f8c84abde9f26837a50d38ccba03a3824a5ce84",
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
| Повторный проход арх-совета после доработки (`SK-A-11`, PoL v1.1 `r3`) | `arch-council.md` §4 + `select_round_seats.py:validate_prior_marker` (обязательная техническая строка `PRIOR-LEDGER-SHA256` в подвале PoL рядом с `PANEL-NONCE` и `ARTIFACT-SHA256`) | сработал |
| SQL, ORM, миграции, DDL/DML | `aisdlc-gcge/agents/database.md` | не сработал (нет БД/миграций в скоупе) |
| Airflow, Spark, ETL, DAG | `aisdlc-gcge/agents/data-engineering.md` | не сработал (нет ETL/DAG в скоупе) |

### ARCHITECTURE_PACKET_FILES
Список файлов Architecture Packet и входов прохода (`SK-A-11`):
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (актуальная редакция v2)
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json`
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v1-to-v2.diff` (механический `diff -u` v1→v2 с sha256 обеих редакций)
- `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a1.json` (полный вывод `panel-rework-summarizer`)
- Целевая область реализации из пакета: `bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`, `bridges/opencode-zen-bridge/tests/test_zen_bridge.py`


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

РЕШЕНИЕ ДЛЯ ОЦЕНКИ:
Ниже приложены целиком (без обрезки; раздел «Не вложено» пуст — все первичные артефакты даны полностью в этом брифе) актуальный Architecture Packet (редакция v2), квитанция пройденного гейта `ARCH_GATE`, механическая дельта `diff -u` между редакциями v1 и v2 с SHA-256 обеих редакций (`architecture-packet.v1-to-v2.diff`), а также полный вывод `panel-rework-summarizer` (`handoff/panel-rework-brief-arch-a1.json`, `SK-A-11`):
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d
{
  "schema_version": "1.0",
  "packet_version": "2.0",
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "cycle": 2,
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": "plans/architect-02.json",
    "sha256": "8bede3e0b7daecf01212133dee566014df3472bb244fde2fbc09bedf3ef25f1e"
  },
  "summary": "Гибрид C/A1, цикл 2 fix-from-panel: ephemeral serve v2.1.2 с точным wire-контрактом, ask_reject, отдельными readiness/session/watchdog бюджетами, pre-response-headers fallback и sticky transport health; run kill-switch без рестарта. APPROVED означает проектный контракт-кандидат для R2, не council PASS или живую приёмку.",
  "scope": {
    "repo_root": "~/tmp/cli-agent-bridge/zen-realtime-reasoning",
    "branch": "feature/zen-realtime-reasoning",
    "architect_write_allowlist": [
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.before.json",
      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.json",
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
      "acceptance": "AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с На serve локальный HTTP ready не считается execution event: после отправки prompt валидного события текущей session нет20s ->first_event_timeout+cleanup<=2s.",
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
      "statement": "REQ-013 уточнение под AC-018: per-spawn ротация _next_standalone_proxy и proxy env сохраняется на каждом child; _StartupGate, spawn rate, bulkhead и model Circuit Breaker действуют на обоих транспортах. loopback georouter baseURL=http://127.0.0.1:10830/v1 идёт по NO_PROXY в обход child HTTP_PROXY; смена реального Zen egress IP этим не гарантируется.",
      "acceptance": "AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`)",
      "evidence": "F-10, F-11, F-15, F-27, F-32; RW-005",
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
      "acceptance": "AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` first_event_ms=null до валидного session SSE исполнения после prompt; local ready не подставлять; transport_history различает _ServeHealth degradation.",
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
    },
    {
      "id": "EVD-062",
      "kind": "code",
      "ref": "~/.opencode/bin/opencode (v2.1.2), embedded JS byte offsets113098820,114613538,114616189,114617971,114628971,114631174,114634000..114636000,114980796,114994633,114622692,114978382,115017692,114596000..114596700",
      "claim": "Read-only source extraction: version2.1.2; Model.Ref {providerID,id,variant}; Permission.Ruleset array{action,resource,effect}, wire permission.asked+reply decision=reject; delta data.delta/sessionID/assistantMessageID/ordinal; TokenUsage.Info {input,output,reasoning,cache:{read,write}}; tool input.started/called/failed; session prompt delivery steer|queue,resume. binary SHA256 b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c. Synthetic frozen examples use source schemas, не live tool execution. Дополнительно source: active sessions response data — object record, не array; Session.StructuredError optional numeric status (100..599); /api/info gives app version+pid; OpenAPI.info.version=0.0.1, отдельная от CLI2.1.2.",
      "collected_at": "2026-10-26"
    },
    {
      "id": "EVD-063",
      "kind": "document",
      "ref": "/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/serve_sse.py + poc_serve.log; F-19/F-22/F-23",
      "claim": "Существующий analyst PoC использует lightweight GET /api/session/active; create model {providerID,id,variant}, location.directory; prompt files[] delivery=steer; data.id response. Сохранённый failed event {id,created,type,data:{sessionID,error:{type:provider.free-limit,message}}}. В cycle2 процесс opencode не запускался, provider не вызывался."
    },
    {
      "id": "EVD-064",
      "kind": "document",
      "ref": "handoff/panel-rework-brief-arch-a1.json + текущий Brief Architect cycle2 fix-from-panel",
      "claim": "14 обязательных RW и7 FU; exact explicit choices для default true, headers barrier, permission selector,MiB/typing; role write allowlist только3 JSON. Исходные расхождения R1 перечислены в panel_resolution_choices, не выданы за единогласное одобрение изменений."
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
      "statement": "Per-spawn proxy env rotation доказуема AC-018, Zen egress за georouter не определяется child HTTP_PROXY (F-15/F-27). child192MiB — design estimate; временный per-spawn XDG_DATA_HOME устраняет совместное открытие общей DB; фактический RSS/locks проверяет обязательный H3.",
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
      "statement": "Default ask_reject и optional env=deny проверяются FakeServe; живую совместимость обеих safe policies с Zen и no-file mutation доказывает H6. Автопереключения политик нет; отсутствие safe endpoint или401/403 fail-closed.",
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
    "REQ-012/013/015: запрет built-ins, per-spawn proxy env rotation (не доказанная Zen IP ротация), безопасные secrets/loopback ownership"
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
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
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
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
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
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
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
      "command": "python3 - <<'VER004'\nimport collections, json, subprocess\nfrom pathlib import Path\nfiles = ['bridges/opencode-zen-bridge/server.py','bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py','bridges/opencode-zen-bridge/tests/test_step_interruption.py']\nassert all(Path(f).is_file() for f in files), files\nfor args in ([\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"format\",\"--check\",\"--no-cache\",*files], [\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"check\",\"--no-cache\",*files]):\n    subprocess.run(args, check=True)\nb = subprocess.run([\"uvx\",\"--from\",\"basedpyright==1.40.2\",\"basedpyright\",\"--outputjson\",*files], capture_output=True, text=True)\nassert b.returncode in (0,1), b.stderr\nreport = json.loads(b.stdout)\nds = report['generalDiagnostics']\nerrors = [d for d in ds if d['severity'] == 'error']\nassert report['summary']['errorCount'] == 0 and not errors, errors\nlimits = {'reportExplicitAny': 125, 'reportAny': 125, 'reportUnusedCallResult': 39, 'reportUnknownMemberType': 70, 'reportUnknownVariableType': 48, 'reportUnknownArgumentType': 35, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 81, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 3, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}\nserver = Path(files[0]).resolve()\nserver_warnings = [d for d in ds if d['severity']=='warning' and Path(d['file']).resolve()==server]\ncounts = collections.Counter(d.get('rule','') for d in server_warnings)\nassert all(n <= limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n# Both Any rules explicitly retain the frozen server.py ceiling even if absent in output.\nassert counts['reportAny'] <= 125 and counts['reportExplicitAny'] <= 125, dict(counts)\nprint('PASS VER-004: ruff format/check all 3 files, basedpyright 0 errors all 3, server frozen warning budgets',dict(counts))\nVER004",
      "expected": "exit0; ruff format --check и ruff check на всех3 targetfiles без allowance; basedpyright severity==error ровно0 на всех3. server.py reportAny<=125/reportExplicitAny<=125 и остальные frozen rule warning budgets не растут. Прежние E402/2 type errors EVD052/053 не разрешены новым gate; Coder исправляет в allowlist без type-ignore/disable/изменения конфигов. Stage2 команду не запускает: новый testfile ещё не существует.",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier",
      "baseline_transition": {
        "old": "v1 VER-004 разрешал1E402 и2errors server.py и пропускал test_step_interruption.py",
        "new": "0 lint/format failures,0type errors на каждом из3files; server frozen warning budgets unchanged",
        "owner": "Stage3 Coder устраняет pre-existing error sites в server.py; Verifier независимо проверяет. Новые Any запрещены, подавлять диагностику ради PASS нельзя."
      }
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
      "expected": "exit0; exact frozen-v2.1.2 FakeServe fixture digest+negative mutations, delivery/concurrent reject, ask_reject/deny и _run_env hash, listener takeover zero leakage, budgets51.6, separate first_event20/readiness3, file kill-switch, ServeHealth3/TTL120 independent breaker, synthetic leading LF provenance, XDG cleanup, all prior tools/timing/lifecycle/resilience assertions. Implementation NOT_RUN Stage2.",
      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
      "owner": "verifier"
    }
  ],
  "decisions": [
    {
      "id": "AD-001",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как получить настоящие reasoning/text delta и сохранить обратимый legacy-путь?",
      "choice": "Option C/A1: один ephemeral serve v2.1.2 на попытку; canonical source для SSE/JSON. В auto run fallback только до HTTP-заголовков ответа POST /prompt И до первого валидного события исполнения текущей сессии; после барьера никакого silent run fallback.",
      "alternatives": [
        "A2: общий daemon экономит холодный старт, но объединяет failure domain и child env; самостоятельная ротация egress внутри georouter не доказана ни для A1, ни для A2 (F-15/F-27).",
        "B: прямой HTTP Zen — меньше ресурсов, но 429 F-24/F-25 и нет подтверждённого client context; не выбирается без PoC.",
        "L: только run watchdog/status — минимален, но не устраняет RC-1."
      ],
      "drivers": [
        "REQ-001",
        "REQ-002",
        "REQ-003",
        "REQ-012",
        "REQ-013 / AC-018: per-spawn _next_standalone_proxy/env rotation; loopback georouter bypasses child HTTP_PROXY via NO_PROXY, не гарантия смены Zen egress IP",
        "REQ-014",
        "F-19/F-20: 109 ms server start, 127/114 ms delta medians"
      ],
      "consequences": [
        "Дополнительные SSE/control sockets и lifecycle; предел активных детей не увеличивается.",
        "run-откат теряет realtime; это видимая деградация, не доказательство REQ-001.",
        "Откат флага/режима без миграций; публичная форма ответов неизменна.",
        "Новый процесс получает временный XDG_DATA_HOME: история/SQLite изолированы на попытку и удаляются в finally; общий opencode.db не открываем намеренно.",
        "Default=true разрешён текущим rework-brief; production sync лишь после изолированного H3. Файл disable-serve удерживает боевой run до приёмки."
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
        "EVD-051",
        "EVD-062",
        "EVD-063",
        "EVD-064"
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
            "default": true,
            "purpose": "В auto нативный Mach-O opencode сразу использует serve после разрешённой синхронизации server.py; start.sh неизменен. Явные 0/false выключают optional serve ветвь первой инструкцией."
          },
          "OPENCODE_ZEN_BRIDGE_TRANSPORT": {
            "values": [
              "auto",
              "serve",
              "run"
            ],
            "default": "auto",
            "precedence": "REALTIME_SERVE_ENABLED=0/false или TRANSPORT=run -> run до stat/probe/allocations; затем существующий disable-file -> run; затем auto ServeHealth + shebang eligibility; иначе serve. Force serve обходит только shebang/health auto routing для FakeServe и диагностики, но не disable-file, выключенный флаг или security. Force serve errors явные, без silent fallback. Invalid value -> config error."
          },
          "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY": {
            "values": [
              "ask_reject",
              "deny"
            ],
            "default": "ask_reject",
            "purpose": "Одна policy на attempt; ask_reject сохраняет tool schemas, немедленно отвечает decision=reject. deny выбирается env до запуска для отдельного H6, без пересборки. Нет автоматического deny↔ask_reject переключения ни до, ни после prompt; unsupported policy/capability -> fail-closed."
          },
          "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": {
            "default": "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
            "purpose": "Путь expanduser/resolve при конфигурации, без создания каталога. На входе нового запроса O(1) os.path.exists(); файл есть -> run без serve UUID/password/queue/thread/Popen/probes. Ошибка проверки пути -> безопасно run с redacted reason. Создание/удаление файла меняет выбор следующего запроса без рестарта; active leases завершаются или явно отменяются, без дублирования текущего prompt."
          },
          "SERVE_READY_TIMEOUT_S": 3.0,
          "SERVE_SESSION_SETUP_TIMEOUT_S": 2.0,
          "feature_flag_context": "Текущий explicit cycle-2 brief RW-009 разрешает default=true в локальном stdlib-мосте (прецеденты STEP_RECOVERY=1 и F-40), вместо общего GigaRC default=false. Новых dependencies/GigaRC/start.sh/env propagation не добавлять. Disable-file обеспечивает live kill-switch без рестарта; H3 обязателен до production rollout."
        },
        "auto_fake_compatibility": "Auto: до любых serve allocations выполнить env/run/disable-file/health guards; затем cached stat+first bytes executable. Shebang #! или текстовый launcher -> run сразу, без --help/--version/serve subprocess. Это сохраняет 378 fake-CLI baseline tests при новом default=true, включая basename opencode; не проверять имя теста/FAKE_OC_MODE. Native Mach-O -> owned serve readiness. Eligibility/protocol metadata cache key=(resolved executable path,mtime_ns,size); смена ключа инвалидирует старую capability и transport health. Force serve обходит shebang для FakeServe, stdin=DEVNULL предотвращает stdin.read hang. false/run/disable-file spies: zero serve UUID/password/threads/probes/extra Popen; stat file разрешён только enabled selector.",
        "spawn": "На каждую реальную попытку общий _RequestAttempts/slot, единый admission deadline<=5.0s для _SpawnRateLimiter+_StartupGate (не два ожидания по5s), свежий _serve_env(model_id) поверх одного неизменного _run_env(model_id), новая per-spawn _next_standalone_proxy запись. Parent socket.bind((127.0.0.1,0)), getsockname()[1]; держать резерв до непосредственно Popen, затем close reserve и Popen([OPENCODE_BIN,serve,--hostname,127.0.0.1,--port,str(port)],stdin=DEVNULL,start_new_session=True,close_fds=True), сохранить child_pgid. Prompt/Basic password не передавать argv/stdin. До первого Authorization или prompt доказать owner listener по listener_ownership; при port race cleanup + новый порт только в оставшемся ready deadline, каждый новый Popen расходует общий cap3 и spawn token. Ни одного бесплатного spawn при EADDRINUSE.",
        "startup": "SERVE_READY_TIMEOUT_S=3.0s (ready_budget_s=3.0): после owner proof лёгкий authenticated GET /api/session/active, HTTP200 + $.data object map of active sessions (empty={}); не качать 281KB /openapi.json на каждом spawn. Control I/O slices<=.25s, всего<=3 readiness TCP probes, remaining request deadline/cancel всегда проверяются. Child EOF/no listener/incompatible protocol -> ServeUnavailable. Пароль secrets per spawn в OPENCODE_SERVER_PASSWORD ПОСЛЕ whitelist, Basic opencode:<password>, никогда в argv/URL/log. stdout/stderr bounded drain+redact. HTTP на loopback напрямую без proxy/redirects. Readiness не устанавливает first_event_ms и не сбрасывает first_event/token часы.",
        "fallback_barrier": "State machine: ADMISSION -> SPAWN/OWNER/READY -> CREATE/SUBSCRIBE -> PROMPT_SENDING -> DELIVERED -> TERMINAL -> CLEANUP. Auto ServeUnavailable на старте/create/subscribe или до получения HTTP response headers POST /api/session/{id}/prompt допускает один budgeted run fallback, ТОЛЬКО если не было валидного события исполнения созданной session после начала отправки prompt, нет model/tool output, auth/security failure, cancel или deadline. Перед run полностью close/join/killpg/reap старую attempt, удалить temp data; новый Popen требует тот же retry token/Full Jitter/attempt ceiling<=3. С первого response header POST /prompt (любой status) ИЛИ первого session execution event после prompt delivery лачится DELIVERED=true; silent fallback и переключение на run для текущего запроса запрещены, включая отсутствие response body и headers-pending+SSE-started. Prompt POST исполняется daemon worker параллельно SSE; до header/события ожидание ограничено остатком first_event20s/first_token60s и total deadline. Даже до headers неизвестная доставка может дать повторную генерацию: допустимость этой границы явно задана текущим brief RW-001, это НЕ exactly-once; старый PGID должен быть убран до fallback, built-ins никогда allow. После barrier watchdog может выполнить только явный общий retry того же транспорта с retry-status/cleanup/cap, не скрытый run fallback. HTTP401/403/auth/permission/capability-security denial -> fail-closed без fallback/auto policy switching на любой фазе.",
        "session_flow": "После listener proof/readiness и подтверждения safe permission capability POST /api/session по session_wire.create; затем GET /api/event с HTTP200 text/event-stream и reader armed ДО отправки первого байта тела prompt. На create + subscribe один SERVE_SESSION_SETUP_TIMEOUT_S=2.0s, не включая model generation или ожидание POST /prompt response. Передать полный prompt в JSON body через единственный daemon delivery worker, одновременно читать SSE в owned reader; supervisor/SSE writer не ждут блокирующий POST и остаются cancel-aware. Один POST /prompt с delivery=steer,resume=true; transport HTTP headers/ошибки передаются supervisor как control events. First-event/token часы якорятся на prompt_send_start, не на HTTP ready/создание сессии. Filter data.sessionID==created_sid; реальные v2 события не содержат executionID, поэтому использовать own per-attempt session + prompt-send generation latch, event id дедуп и assistantMessageID step key, не выдумывать executionID. server.connected/session.created/global updates/pre-prompt events не считаются first execution. Terminal success/failed независим от text end; EOF без terminal -> protocol failure. step.ended с готовым DSH tool call -> остановить дальнейшее исполнение/cleanup.",
        "tool_policy": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
        "event_contract": {
          "shape": "Iterator canonical tuples для обоих потребителей; object/TypedDict validation. Public OpenAI unchanged; legacy parser остаётся для run. Полные wire fixtures ниже frozen v2.1.2, metadata id/created synthetic, field paths подтверждены EVD-062/EVD-063.",
          "session.reasoning.delta": "$.data.delta -> (reasoning,{reasoning_content:delta}); delta bytes only, ended не повторяет full text. Если native encrypted metadata есть в started/ended, сохранять существующим reasoning_details mapping без повторной text delta.",
          "session.text.delta": "$.data.delta -> (text,{content:delta}) -> тот же ToolCallParser.feed/emit_content.",
          "session.step.ended": "$.data.tokens input/output/reasoning + $.data.tokens.cache.read -> canonical input/output/reasoning/cached; один учёт по $.data.assistantMessageID, terminal не удваивает usage.",
          "session.tool.*": "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side.",
          "session.step.failed / session.execution.failed": "$.data.error {type,message,status?,response?,retryAfterMs?} ->canonical error{statusCode,message}: statusCode=$.data.error.status если integer100..599; иначе explicit known type mapping provider.free-limit429/auth401/permission denial403, unknown null. Terminal independent, one cause not counted twice.",
          "session.execution.succeeded": "terminal success metadata, не text/reasoning; гарантированно дренировать уже полученный step.ended перед финальным usage.",
          "other": "first_event latch только валидный execution/step/reasoning started текущей session после prompt; валидные current-session model delta также доказывают начало исполнения. server.connected, HTTPready, session.created, чужие session/control/comments/status не latch и не model token.",
          "payload_validation": "Проверять exact field paths/types и mandatory sessionID до emit. Текущая schema shape mismatch -> invalid_serve_event (не пустая полезная delta), отдельный ServeHealth; permission capability mismatch ->security fail-closed. Incremental UTF8/CRLF/multiline SSE/comments/fragment boundaries, byte budgets как прежде. Никакого Coder-discovered protocol или aliases, которых нет в frozen source. Coder и FakeServe используют frozen expected независимо; мутации delta path/token/permission должны краснить тест даже если adapter и mock согласованно ошибочны.",
          "frozen_v2_1_2_fixtures": {
            "session.reasoning.delta": {
              "wire": {
                "id": "evt_fixture_1",
                "created": 1792957431001,
                "type": "session.reasoning.delta",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "ordinal": 0,
                  "delta": "Мысль без LF"
                }
              },
              "field_paths": {
                "session_id": "$.data.sessionID",
                "step_key": "$.data.assistantMessageID",
                "ordinal": "$.data.ordinal",
                "delta": "$.data.delta"
              },
              "canonical": {
                "etype": "reasoning",
                "payload": {
                  "reasoning_content": "Мысль без LF"
                }
              }
            },
            "session.text.delta": {
              "wire": {
                "id": "evt_fixture_2",
                "created": 1792957431002,
                "type": "session.text.delta",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "ordinal": 1,
                  "delta": "Ответ\n"
                }
              },
              "field_paths": {
                "delta": "$.data.delta",
                "session_id": "$.data.sessionID"
              },
              "canonical": {
                "etype": "text",
                "payload": {
                  "content": "Ответ\n"
                }
              }
            },
            "session.step.ended": {
              "wire": {
                "id": "evt_fixture_3",
                "created": 1792957431003,
                "type": "session.step.ended",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "assistantMessageID": "msg_fixture_1",
                  "finish": "stop",
                  "cost": 0,
                  "tokens": {
                    "input": 17,
                    "output": 9,
                    "reasoning": 4,
                    "cache": {
                      "read": 3,
                      "write": 2
                    }
                  }
                }
              },
              "field_paths": {
                "tokens": "$.data.tokens",
                "dedup_step_key": "$.data.assistantMessageID",
                "cached": "$.data.tokens.cache.read"
              },
              "canonical": {
                "etype": "step_finish",
                "payload": {
                  "input": 17,
                  "output": 9,
                  "cached": 3,
                  "reasoning": 4
                }
              },
              "note": "Реальный v2 wire cache:{read,write}; cached=cache.read в legacy canonical tuple. cache.write не суммировать с cached read. Canonical input/output/reasoning копировать по существующей семантике; считать раз по assistantMessageID. Отсутствие required tokens/cache/read — invalid_serve_event, не нули."
            },
            "session.permission.requested / session.tool.*": {
              "wire_event_name": "permission.asked",
              "logical_family": "session.permission.requested",
              "wire": {
                "id": "evt_fixture_4",
                "created": 1792957431004,
                "type": "permission.asked",
                "data": {
                  "id": "per_fixture_1",
                  "sessionID": "ses_fixture_1",
                  "action": "bash",
                  "resources": [
                    "*"
                  ],
                  "source": {
                    "type": "tool",
                    "messageID": "msg_fixture_1",
                    "id": "call_fixture_1"
                  }
                }
              },
              "field_paths": {
                "session_id": "$.data.sessionID",
                "request_id": "$.data.id",
                "tool_call_id": "$.data.source.id",
                "action": "$.data.action",
                "resources": "$.data.resources"
              },
              "reply": {
                "method": "POST",
                "path": "/api/session/ses_fixture_1/permission/per_fixture_1/reply",
                "body": {
                  "decision": "reject"
                },
                "success_status": 204
              },
              "tool_lifecycle": [
                {
                  "id": "evt_fixture_5",
                  "created": 1792957431005,
                  "type": "session.tool.input.started",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "name": "bash"
                  }
                },
                {
                  "id": "evt_fixture_6",
                  "created": 1792957431006,
                  "type": "session.tool.input.delta",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "delta": "{\"command\":\"printf probe\"}"
                  }
                },
                {
                  "id": "evt_fixture_7",
                  "created": 1792957431007,
                  "type": "session.tool.input.ended",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "text": "{\"command\":\"printf probe\"}"
                  }
                },
                {
                  "id": "evt_fixture_8",
                  "created": 1792957431008,
                  "type": "session.tool.called",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "input": {
                      "command": "printf probe"
                    },
                    "executed": false
                  }
                },
                {
                  "id": "evt_fixture_9",
                  "created": 1792957431009,
                  "type": "session.tool.failed",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "assistantMessageID": "msg_fixture_1",
                    "id": "call_fixture_1",
                    "error": {
                      "type": "permission.rejected",
                      "message": "Rejected by bridge policy"
                    },
                    "executed": false
                  }
                },
                {
                  "id": "evt_fixture_10",
                  "created": 1792957431010,
                  "type": "permission.replied",
                  "data": {
                    "sessionID": "ses_fixture_1",
                    "requestID": "per_fixture_1",
                    "reply": "reject"
                  }
                }
              ],
              "canonical": {
                "etype": "tool_use",
                "payload": {
                  "part": {
                    "tool": "bash",
                    "state": {
                      "input": {
                        "command": "printf probe"
                      },
                      "status": "error"
                    }
                  },
                  "call_id": "call_fixture_1"
                }
              },
              "note": "Family label из brief — не имя wire event. В бинарнике нет session.permission.requested или session.tool.started: actual names permission.asked и session.tool.input.started/called/progress/success/failed. Имя tool копить из input.started; canonical payload emit после complete input/called, не исполнять по частичному JSON. Lifecycle updates не создают повторный DSH tool_call; own denied event не является model progress. Указанный failed message — синтетическое fixture значение типа error, не заявление о захваченном live отказе."
            },
            "session.execution.failed": {
              "wire": {
                "id": "evt_fixture_11",
                "created": 1792957431011,
                "type": "session.execution.failed",
                "data": {
                  "sessionID": "ses_fixture_1",
                  "error": {
                    "type": "provider.free-limit",
                    "message": "Free usage limit reached"
                  }
                }
              },
              "field_paths": {
                "error": "$.data.error",
                "message": "$.data.error.message",
                "error_type": "$.data.error.type",
                "statusCode": "$.data.error.status if present integer100..599, else explicit type mapping"
              },
              "canonical": {
                "etype": "error",
                "payload": {
                  "statusCode": 429,
                  "message": "Free usage limit reached"
                }
              },
              "note": "provider.free-limit ->429; provider.auth/permission denial ->fatal401/403; неизвестный type сохраняется как явная ошибка с statusCode=null, не выдумывать retryability. step.failed + execution.failed одной cause дедуп без потери terminal. Numeric wire key status, not statusCode/data.statusCode; source Session.StructuredError. Missing numeric status allowed as in captured free-limit event."
            }
          },
          "fixture_provenance": {
            "source": "EVD-062: read-only embedded schemas/API v2.1.2; EVD-063: analyst PoC script+failure envelope",
            "binary_sha256": "b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c",
            "examples": "Пять минимальных семейств, synthetic ids/timestamps/texts; field/type schema extracted from binary, не live business/permission evidence.",
            "immutable_oracle": "В Stage3 fixture literals копируются в tests/test_realtime_reasoning.py; до adapter expectations сверить fixture canonical SHA256 с пакетным fingerprint. Менять fixture по реализации запрещено."
          },
          "frozen_fixture_sha256": "896ae246586487a179d3be99947cc8455ed069a6e98b8b8628690158a1a80ac2"
        },
        "non_stream": "serve используется и stream=False через общий source; Run копит чистые model reasoning/text/native/usage как сейчас. Synthetic [мост] статусы — только SSE presentation, в JSON reasoning_content не добавляются. Google direct dispatch остаётся первым и не создаёт serve/новые timers.",
        "listener_ownership": {
          "protocol": [
            "bind 127.0.0.1:0 -> getsockname -> release immediately before Popen explicit port/new PGID",
            "Дождаться LISTEN без HTTP/Authorization; bounded lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp, только loopback listener PID, проверить os.getpgid(listener_pid)==child_pgid и child lease ещё жив. Несколько PID/ошибка lsof/PGID mismatch не являются успехом.",
            "Проверка до первого Auth и повторно до отправки Auth на каждом новом TCP соединении; no redirects/no env proxy, connect только 127.0.0.1. Не доверять readiness чужого процесса.",
            "Mismatch/EADDRINUSE -> abort attempt, ноль байт секрета/промпта чужому listener; закрыть собственный child/PGID, не посылать interrupt/delete чужому listener и не убивать чужой PID. Retry reserve/spawn только при remaining ready>0, admission/spawn token/cap соблюдены."
          ],
          "owner_probe_timeout_s": 0.25,
          "ready_deadline_includes": "bind/spawn/owner probe, лёгкий authenticated GET /api/session/active и cache-miss protocol check вместе <=3.0s; retry port не продлевает deadline",
          "verification_ids": [
            "VER-005"
          ]
        },
        "protocol_compatibility": {
          "version": "2.1.2",
          "cache_key": [
            "resolved executable path",
            "mtime_ns",
            "size"
          ],
          "handshake": "На первом owned serve данного binary key один lightweight authenticated GET /api/info: JSON version==2.1.2 и pid с PGID==owned child group, затем один bounded GET /openapi.json<=512KiB; обе операции внутри того же aggregate ready_budget_s=3.0. OpenAPI.info.version==0.0.1 — версия API schema, НЕ версия CLI; не сравнивать её с2.1.2. Exact required-schema projection по Model.Ref, Permission.Ruleset, PromptInput, TokenUsage.Info/StructuredError/Event fixtures обязателен. Успешно сохранить app version+SHA256 raw OpenAPI+schema projection keyed(path,mtime_ns,size). Остальные spawn этого key только GET /api/session/active плюс PID/PGID ownership, без OpenAPI download и без --version Popen. Version/schema mismatch до prompt ->ServeUnavailable/_ServeHealth; permission capability gap ->security fail-closed.",
          "invalidation": "mtime_ns/size/path change или fail exact projection -> invalidation; неизвестная patch/schema не считается compatible по одному наличию endpoint. Для новой версии нужен обновлённый подтверждённый fixture/Architect delta. Отсутствие безопасного permission endpoint — security failure, без run fallback.",
          "fixture_source_evidence_ids": [
            "EVD-062",
            "EVD-063"
          ],
          "cache_ownership": "Per-Server bounded capability record (only executable key/version/schema hashes/projection, no password/session/prompt). Один fill-owner на binary key; конкурентные fills ждут только remaining own ready3s без блокировки writer, owner cancellation снимает in-flight; никаких live sockets/passwords в cache. Это setup capability metadata, не ControlPlane/Snapshot polling."
        },
        "admission": "Один monotonic pre_spawn_deadline=now+min(5.0,remaining_request) охватывает _SpawnRateLimiter и _StartupGate. Сначала получить rate token с timeout=remaining_admission; gate может ждать только остаток этого же окна и fail-open по legacy, без добавочных5s; timeout rate token -> не spawn. Hold gate<=12s не является отдельным pre-spawn wait; release при готовности собственного child/EOF/finally, HTTP ready по-прежнему не событие модели. Cancel poll<=.25s, каждый Popen включая fallback/race учитывается _RequestAttempts<=3; token не обходить.",
        "session_wire": {
          "schema": "opencode serve v2.1.2, EVD-062/EVD-063; paths и JSON properties заморожены до Coder",
          "create": {
            "method": "POST",
            "path": "/api/session",
            "headers": {
              "Content-Type": "application/json",
              "Authorization": "Basic <ephemeral runtime secret, never stored>"
            },
            "body": {
              "location": {
                "directory": "<existing absolute request workdir>"
              },
              "model": {
                "providerID": "opencode",
                "id": "deepseek-v4.1-flash-free",
                "variant": "high"
              },
              "permissions": [
                {
                  "action": "*",
                  "resource": "*",
                  "effect": "ask"
                }
              ]
            },
            "success_status": 200,
            "response_id_path": "$.data.id",
            "permission_variant": "Для policy=deny тот же ruleset с effect=deny; ask_reject effect=ask + немедленный decision=reject. В API permissions — ARRAY rules, не config object {\"*\":\"ask\"}.",
            "model_mapping": "Тот же resolved provider/model#variant: отделить providerID и id; #high -> model.variant=\"high\"; effort off/none -> variant отсутствует, не #off. --thinking относится к CLI presentation; HTTP thinking задаётся существующим resolved variant без несуществующего поля thinking."
          },
          "subscribe": {
            "method": "GET",
            "path": "/api/event",
            "headers": {
              "Accept": "text/event-stream"
            },
            "success_status": 200,
            "body": "SSE data JSON envelope {id,created,type,data}; subscribe armed до prompt body, filter data.sessionID"
          },
          "prompt": {
            "method": "POST",
            "path": "/api/session/{id}/prompt",
            "body": {
              "text": "<full unchanged prompt>",
              "files": [],
              "delivery": "steer",
              "resume": true
            },
            "success_status": 200,
            "response": "$.data is Session.Inbox.User; $.data.id is inbox/message id, durable admission, не model completion",
            "delivery": "steer/queue — admission boundary, НЕ флаг неблокирующего HTTP. Для единственного fresh session input выбран steer; один POST, worker может блокироваться на headers/body параллельно чтению SSE. Не вызывать generate, resume повторно или повторный prompt при задержке ответа.",
            "budget": "Не session_setup2s. От prompt_send_start ограничен оставшимися first_event20s/first_token60s/общим TIMEOUT1800; при продвижении session событий supervisor не отменяет HTTP только потому, что истёк first_event, но total/cancel/terminal закрывают сокет. Response body не нужен для продолжения чтения событий после headers."
          },
          "permission_reply": {
            "method": "POST",
            "path": "/api/session/{id}/permission/{requestID}/reply",
            "body": {
              "decision": "reject"
            },
            "success_status": 204,
            "request_id_path": "$.data.id of permission.asked; session path id=$.data.sessionID",
            "note": "Wire key decision, не reply; permission.replied notification содержит reply=reject. Никогда once/always/allow."
          },
          "cleanup": {
            "interrupt": "POST /api/session/{id}/interrupt",
            "delete": "DELETE /api/session/{id}",
            "aggregate_api_budget_s": 0.2
          },
          "readiness": {
            "method": "GET",
            "path": "/api/session/active",
            "success_status": 200,
            "response_example": {
              "data": {}
            },
            "schema": "$.data is record keyed by sessionID, not an array; source byte offset114978382",
            "budget": "part of ready_budget_s=3.0, not first_event; owner proof before auth"
          },
          "version_probe": {
            "method": "GET",
            "path": "/api/info",
            "response_example": {
              "version": "2.1.2",
              "pid": "<actual child PID integer>"
            },
            "note": "Пример pid placeholder только в документации, wire integer; owner PGID проверяется до Auth независимо от self-reported pid. appversion2.1.2 отличается от OpenAPI.info.version0.0.1. Once per executable stat key, withinready3s."
          }
        },
        "data_isolation": {
          "XDG_DATA_HOME": "На каждый serve spawn tempfile.mkdtemp(prefix=\"zen-serve-data-\") в локальном temp вне репозитория/Drive; env[\"XDG_DATA_HOME\"]=каталог. OPENCODE_MODELS_PATH сохраняется из _run_env, не терять standalone model catalog. Не копировать/не мигрировать/не редактировать общую ~/.local/share/opencode/opencode.db (2.27 GB, F-28).",
          "ownership": "Путь принадлежит attempt lease; child создаёт собственный SQLite. После kill/reap и закрытия readers в finally shutil.rmtree(temp_data_dir,ignore_errors=True), на каждом exit, including spawn exception/port race/setup/auth/cancel/terminal. Cleanup idempotent; директории чужих attempts не трогать.",
          "cleanup_budget": "Входит в aggregate cleanup<=1.2s. Реальный FS cleanup/RSS/DB locking проверяются H3; превышение запрещает enable, не выдавать ignore_errors за доказанное удаление.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "typing": "Новый wire JSON декодируется в object с явным isinstance/type narrowing и TypedDict, без Any/кастов Any/type-ignore для обхода. Новый модуль serve_transport.py запрещён текущим allowlist; всё внутри server.py. VER-004: formatter/linter на всех3 файлах, basedpyright severity==error ровно0 на всех3, server reportAny<=125 и reportExplicitAny<=125, остальные frozen per-rule warning budgets не растут.",
        "transport_health": {
          "owner": "_ServeHealth per Server, key=(resolved executable,mtime_ns,size), lock/monotonic; состояние отдельно от model _UpstreamBreaker",
          "consecutive_failure_threshold": 3,
          "degrade_ttl_s": 120.0,
          "degraded_transport": "run для новых auto requests",
          "counted_failures": [
            "first_event_timeout на serve после prompt и HTTP readiness, без валидных событий исполнения",
            "invalid_serve_event / incompatible schema projection / malformed required v2 fields",
            "serve SSE EOF без terminal; first_token_timeout только при доказанной protocol/capability причине, иначе model failure"
          ],
          "not_counted": "Реальные provider errors (429/free-limit,5xx,provider network), explicit auth/permission/security failure, client_gone, slot rejection и transient child DB errors не маскировать transport failure. Если валидные execution events пришли, но model token нет, first_token_timeout сохраняет обычную provider classification при отсутствии доказанного protocol defect.",
          "state_machine": "HEALTHY consecutive0..2; третий законченный protocol-specific failure -> DEGRADED(until=now+120), последующие auto requests run без serve probe/Popen. Это НЕ повтор/переключение текущего DELIVERED prompt: транспорт текущего запроса закреплён, silent replay запрещён. В DEGRADED skipped requests не продлевают TTL. При TTL expiry ровно один HALF_OPEN serve probe request (другие auto requests run); только валидный terminal success со schema-valid source очищает consecutive/degraded. Failed protocol probe -> новый TTL120. Provider failure не объявлять protocol success/failure. Neutral cancel освобождает probe, не продлевает TTL. Force serve допускает диагностику, не обходя security/kill-switch/cap3.",
          "breaker_isolation": "Protocol-specific failure никогда не вызывает _UpstreamBreaker.failure/commit pending model failure. Provider failures сохраняют общий breaker threshold5/cooldown jitter/HALF_OPEN1. Нейтральный transport-only финальный запрос освобождает model probe lease после cleanup; success/failure не выдумывать. _RetryBudget и MAX_TOTAL_SPAWNS остаются общими даже для protocol retry/fallback.",
          "telemetry": "O-EXIT transport_history и attempt reason различают serve_protocol_failure, serve_health_degraded/run, serve_health_probe, policy failure и provider failure; no secrets. Skipped serve не добавляет фиктивный spawn.",
          "verification_ids": [
            "VER-005"
          ]
        },
        "immutable_run_env": {
          "symbol": "bridges/opencode-zen-bridge/server.py:_run_env",
          "source_slice": "ast FunctionDef.lineno..end_lineno inclusive, raw file bytes splitlines(keepends=True), includes terminal LF",
          "sha256": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
          "test_run_env_sha256": "d3d0baf57f7ccae7dd7846ab98d3da43c588a35e7f076fabe074c1212f232e05",
          "start_sh_sha256": "5430e529627b3a705da4be7641a6d079408e3cf85b6ad3333330e34cb08c190c",
          "verification": "VER-005 compare literal hashes from frozen packet; _serve_env wrapper only, never recalculate expected from edited implementation"
        }
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
        "lifecycle": "Startup-gate/spawn wait статусы только после grace при фактическом ожидании, без немедленного prefix на быстром acquire. До первого real token при тишине heartbeat каждые 5.0 s: [мост] Ожидание первого токена (N с)… + LF. После real progress и затем настоящего stall можно каждые 5 s дать [мост] Ожидание продолжения… + LF. Статусы не сбрасывают transport/model watchdog timestamps и сами не считаются attempt_output. Нормальные 127 ms reasoning delta не сопровождаются heartbeat. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
        "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
        "pure_reasoning": "Склейка model-origin delta равна upstream model bytes после унаследованной очистки известных interrupted artifacts; не добавлять LF для preview, пробелы и UTF-8 не переписывать. _strip_interrupted должен оставаться chunk-boundary-safe: распознанный interrupted marker удерживается/удаляется инкрементально, partial prefix не протекает; обычный текст не нормализуется. В тестах удалять synthetic delta по provenance/expected list, а не слепо вырезать любую модельную строку [мост]. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
        "regression": "test_interrupted_artifact_removed_from_reasoning_stream: быстрая последовательность marker + Simple greeting. -> exactly Simple greeting., один run, zero status. В JSON тоже exactly. Slow FakeServe: first status <=1.0 s при заблокированном upstream; visible(text.strip) true, latestCompletedParagraphFirstLine получает завершённый LF. Natural reasoning LF обновляет collapsed row, bytes неизменны.",
        "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt. Остаточный межпровайдерский replay в DSH при ручной смене модели описан RISK-011; current bridge ignore не доказывает безопасность чужого provider.",
        "status_separator": "Перед любой synthetic [мост] delta, если ранее выданный модельный reasoning chunk не оканчивался LF и текущая видимая строка не завершена, prefix=\"\n\"; результат \"\n[мост] ...\n\". Весь prefix/status/trailing LF имеет synthetic provenance, отдельно от immutable model deltas. Если LF уже есть или модельного reasoning ещё не было, status начинается \"[мост]\" без добавочного LF. Единственный writer отслеживает line boundary; быстрый Simple greeting. до grace вообще не вызывает status helper. Фильтрация synthetic по provenance сохраняет AC-006 байт-в-байт и модельную строку, буквально начинающуюся [мост]."
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
        "clocks": "Общий request deadline TIMEOUT_S=1800 якорится на request t0 и не сбрасывается. Local pre-spawn admission<=5.0s, SERVE_READY_TIMEOUT_S=3.0 и create+subscribe<=2.0 имеют отдельные часы до prompt. Для serve first_event20.0 и first_token60.0 начинаются в prompt_send_start перед первым байтом POST /prompt; first_event удовлетворяется только первым валидным SSE событием исполнения created session после этого момента (session.execution.started/session.step.started/session.reasoning.started, либо валидная текущая model delta). HTTP readiness/headers, server.connected/session.created, чужие/global updates, comments, bridge statuses не гасят first_event и не ставят first_event_ms. Headers POST устанавливают только delivered barrier. Для legacy сохраняется first valid run event/step_start от attempt_start перед startup. first_token — только non-whitespace model reasoning/text или полезный model tool intent; started/control/encrypted-only/reject notification не токен. stall стартует после first_token и обновляется полезными model delta/tool progress; empty ping/status не продлевают. first_event_ms и ttft_ms в O-EXIT относительно request t0, timeout ожидания serve first_event относительно prompt_send_start. При accepted prompt + zero session SSE ->first_event_timeout20s +cleanup<=1.2s, <=22s, не ожидание60s.",
        "disconnect": "На каждой итерации/ожидании <=0.25 s проверять cancel flag и client socket select + recv(MSG_PEEK|MSG_DONTWAIT): EOF/ECONNRESET -> client_gone без чтения данных и без переключения wfile в nonblocking. Реальная bounded empty OpenAI keepalive каждые <=2.0 s тишины страхует разрыв, который TCP ещё не сигнализировал; write deadline <=0.5 s, без write на отдельном потоке. Poll, status, write и cleanup не блокируют supervisor на 15/5 s. Суммарное обнаружение контролируемого FIN/RST <=5.0 s. Полное исчезновение сети без FIN нельзя доказать одним MSG_PEEK — bounded write/OS transport timeout и fault injection отдельно, не обещать физически невозможный мгновенный детект blackhole.",
        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent. После child kill/reap обязателен finally shutil.rmtree(owned XDG_DATA_HOME,ignore_errors=True); закрыть также daemon prompt delivery socket и join его в том же aggregate cleanup<=1.2s. Interrupt/delete только после ownership proof, никогда чужому listener.",
        "retry": "Watchdog first_event/first_token/stall -> bounded common retry after full cleanup, _RequestAttempts/MAX_TOTAL_SPAWNS3/FAIL_RETRY_LIMIT/_RetryBudget/Full Jitter как ранее. Но serve-specific no-session-event/invalid_serve_event/EOF классифицируются _ServeHealth и НЕ _UpstreamBreaker; общие provider failures по-прежнему model breaker. При DELIVERED silent run fallback запрещён: retry текущего запроса остаётся явным на закреплённом транспорте, health TTL влияет только на последующие auto requests. Legacy watchdog сохраняет provider semantics. client_gone/fatal4xx/auth/permission ->no retry/fallback. HALF_OPEN owner token жив до завершения/cleanup, cooldown не допускает второй probe; neutral transport failure/cancel освобождает probe без fake provider success/failure. Slot один на запрос, release once; cancel-aware waits<=.25s; Full Jitter capped remaining.",
        "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки. HTTP readiness НЕ first_event_ms: поле null до valid SSE execution current session после prompt_send_start. transport_history фиксирует отказ serve/TTL run или probe без secrets и phantom Popen; отдельный reason для protocol/model/security. early HTTP headers не ставят ни first_event_ms, ни ttft_ms."
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
      "environment": "auto/default true + shebang filter либо explicit disabled/run/disable-file",
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
      "environment": "serve loopback с listener owner proof, default ask_reject или explicit deny",
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
      "response_measure": "Design:1*256+6*192=1408<=1638.4 MiB. H3 измеряет parent+6*child actual RSS и отсутствие database is locked на103KB×6×3; без H3 runtime PASS отсутствует.",
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
      "responsibility": "Transport selection, listener PID/PGID proof до Auth/prompt, fresh _serve_env/proxy и isolated XDG_DATA_HOME, bounded HTTP/SSE/delivery leases, canonical wire adapter и cleanup",
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
      "responsibility": "Общий process bulkhead/rate/retry budget/model breaker; отдельно _ServeHealth для protocol-specific failures, per-request cap/deadline и prompt delivered barrier",
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
      "mitigation": "Default ask_reject в отдельном _serve_env поверх byte-identical _run_env; wire permission.asked ->decision=reject немедленно, never once/always/allow. Env deny поддержан без пересборки, без automatic policy fallback. 401/403/нет safe endpoint fail-closed; FakeServe обе policy, реальный H6 обязателен.",
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
      "mitigation": "Сохранять per-spawn _next_standalone_proxy env через неизменный _run_env; AC-018 проверяет последовательность записей пула. baseURL=http://127.0.0.1:10830/v1 georouter обходит child HTTP_PROXY по NO_PROXY (F-15/F-27); новый child не доказывает новую Zen IP. Shared daemon не выбирать ради failure isolation, не ради недоказанной egress ротации; конфиг georouter вне scope.",
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
      "mitigation": "В _serve_env temporary XDG_DATA_HOME per Popen, preserve OPENCODE_MODELS_PATH, finally rmtree after group cleanup; shared2.27GB DB не трогать. Design memory1408<=1638.4MiB не measured RSS. H3 до production sync:6 parallel103KB×3 +7th overload, max_actual_parent_RSS+6*max_actual_child_RSS<=0.80*2048MiB и ноль database is locked (ретрай не маскирует contention). FAIL->disable-file сохраняется, rollout запрещён; slots6/waiters12 не повышать.",
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
      "mitigation": "Auto shebang ->one run, no subprocess probes при default=true. Force serve stdin DEVNULL, ready<=3.0s/cancel-aware. Cache по path+mtime_ns+size; exact counter regressions остаются. Никакой fake5s stdin hang.",
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
      "mitigation": "VER-004 заменяет прежний overlay на strict formatter/linter/type checks всех3 files. Унаследованные E402 и2 type errors EVD052/053 честно baseline, их allowance удалён: Coder должен исправить в allowlist без подавления диагностики/конфига. severity error0, reportAny/reportExplicitAny<=125 server.py, прочие frozen warning budgets не растут; format may reveal debt, FAIL нельзя объявить PASS.",
      "verification_ids": [
        "VER-004"
      ]
    },
    {
      "id": "RISK-009",
      "scenario": "Prompt POST timeout уже после принятия способен удвоить generation при silent fallback",
      "probability": "medium",
      "impact": "high",
      "mitigation": "Текущий brief RW-001 выбирает HTTP response headers / первый current-session execution event как delivered barrier, вместо R1 начала POST. До headers и без события ServeUnavailable может fallback после полного kill/reap старого PGID; remote generation могла уже начаться, exactly-once не обещать. После barrier silent run запрещён; только явный same-transport retry+status/cap, no builtin execution. Source disagreement записан в panel_resolution_choices.",
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
    },
    {
      "id": "RISK-011",
      "scenario": "Статусы [мост] сохраняются DSH и при ручном переключении модели могут попасть reasoning_content другого provider (F-33/F-38/F-39)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Принятый остаточный риск: current bridge игнорирует весь replay reasoning, но чужой provider этого не обязан делать. Короткие статусы только grace/реальное ожидание не чаще5s и один на retry, no secrets/prompt text. Не менять DSH/provider контракты; уменьшить объём синтетики. Fake replay проверяет только этот мост, cross-provider H4 наблюдение не заменяет гарантии.",
      "verification_ids": [
        "VER-005"
      ]
    },
    {
      "id": "RISK-012",
      "scenario": "Serve SSE/protocol деградация ошибочно открывает общий model breaker и блокирует рабочий run",
      "probability": "high",
      "impact": "high",
      "mitigation": "_ServeHealth threshold3/TTL120/one recovery probe для новых auto requests, protocol failure не _UpstreamBreaker. Current accepted prompt не переигрывать скрыто. Fake5requests + expiry/probe/version-change cases; настоящие provider429/5xx сохраняют model breaker.",
      "verification_ids": [
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
        "mitigation": "Parent bind loopback0/getport/release-before-Popen explicit port/newPGID; до Auth/prompt lsof listener PID->os.getpgid==childPGID, bounded<=.25s внутри ready3s. Foreign listener/owner unavailable ->zero secret/prompt bytes, cleanup own child only, bounded new port retry/cap3. Пароль secrets env до spawn, stdout redact, no redirects/proxy. VER-005 deliberate port takeover negative test.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-002",
        "scenario": "Модель выдаёт builtin bash/write/edit, пока DSH думает, что это только предложение",
        "mitigation": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-003",
        "scenario": "Unrestricted parent env утекает в serve или proxy creds в ошибку",
        "mitigation": "_run_env whitelist как legacy, password добавляется только child env; no apiKey dump, redact stdout/stderr/exception before _log and response; тест secret sentinels. _serve_env wrapper не меняет _run_env и сохраняет model catalog, private XDG data удаляется finally.",
        "verification_ids": [
          "VER-005"
        ]
      },
      {
        "id": "THREAT-004",
        "scenario": "SSE из чужой session или reconnect replay приводит к чужому выводу/повтору инструмента",
        "mitigation": "Filter exact data.sessionID и own prompt-send generation boundary; session v2 не даёт executionID, не ожидать выдуманного поля. subscribe armed before prompt, no transparent reconnect/replay after delivered; event id + assistantMessageID step/call id dedup; no foreign/raw events in public stream.",
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
    "compatibility": "Публичные OpenAI endpoints/port/auth/schema и Google route неизменны, source общий для SSE/JSON. Default serve flag=true в auto только для нативного бинарника; shebang fake CLI остаётся run без probe, start.sh и _run_env byte-identical. Fast/off/JSON synthetic statuses как раньше исключены.",
    "migration": "NOT_APPLICABLE: продуктовая схема/DB/dependencies не меняются; shared opencode.db/config не трогать. Каждый child получает свежий local-temp XDG_DATA_HOME и сохранённый OPENCODE_MODELS_PATH; наконец interrupt/delete/kill/reap и shutil.rmtree(...,ignore_errors=True). История ephemeral, долговременные prompt/secret артефакты не сохраняются.",
    "rollout": "Stage2 packet cycle2/role-plan/schema/fingerprint -> external architecture Council R2+verify_panel_proof оркестратора -> Stage3 red→green+independent clean-room VER001..005 strict. Default=true НЕ разрешает обход H3: ДО синхронизации server.py в боевой :9883 отдельно изолированный candidate runtime с effectiveM6/waiters12, live103KB prompts6parallel+7th,3повтора и H3 memory/SQLite check. На боевом до допуска удерживать disable-file, который действует сразу при первом старте новой server.py; файлы ~/.dsh в Stage2 не создавать. Только H3 PASS и безопасная policy H6 разрешают H0 sync/read-back, без изменения start.sh; при удалении disable-file native Mach-O в auto сразу serve. После sync H1/H2/H3 повторно+DSH H4/H5/H6/H7/H8/H9; любой memory/DB/security FAIL немедленно disable-file и run. Не перекладывать pre-rollout safety на уже случившийся default-enable. На этом проходе все H0..H9 NOT_RUN.",
    "rollback": "Мгновенный kill-switch без рестарта: создать OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE (default ~/.dsh/bridges/opencode-zen-bridge/disable-serve) -> следующий запрос run без serve allocations/probes; удаление файла возвращает auto при healthy transport. Env REALTIME_SERVE_ENABLED=0 или TRANSPORT=run также принудительно run (смена env уже живого процесса требует restart, не путать с file switch). In-flight leases drain/cancel, delivered prompt не повторять на run. H9 проверяет в живом existing DSH чате создание/удаление файла, неизменный PID сервиса, run/serve transport_history и успешные повторные/параллельные вызовы. Если status/watchdog regression -> отдельный rollback Stage3 commit+H0 identity. Stage2 rollback/deploy не выполняется.",
    "feature_flag": "Explicit cycle2 RW-009/FU-006 override: default=true для локального auto-native пути, zero-serve-cost explicit disable и O(1) file switch без рестарта. Прецедент F-40/STEP_RECOVERY; GigaRC/start.sh dependencies вне allowlist. H3 и H6 обязательны до production enable.",
    "H3_rollout_gate": {
      "status": "NOT_RUN",
      "scenario": "6 parallel реальных рабочих prompt около103KB +7th overload,3повтора; изолированный candidate перед production sync и повтор на боевом после safety допуска",
      "memory_unit": "MiB",
      "memory_inequality": "1*actual_parent_RSS_max + M*actual_child_RSS_max <=0.80*Mem_limit_per_pod; M=6; limit=2048MiB, rhs=1638.4MiB",
      "database_gate": "Ноль database is locked/SQLITE_BUSY на isolated per-spawn XDG DB; ретрай в FAIL_RETRY_LIMIT не превращает lock failure в PASS. Shared2.27GB DB не изменяется.",
      "other_evidence": "Реальные RSS/FD/CPU/TTFT каждого запроса, parent/child peaks, все owned temp dirs удалены, zero orphan PGID; design child192MiB не подставлять вместо замера",
      "on_fail": "Rollout/enable запрещён, disable-file остаётся; не повышать slots6/12 или retry cap3. Не менять текущие shared env/config/DB."
    }
  },
  "approval": {
    "status": "NOT_REQUIRED",
    "decision_ids": [],
    "approved_by": null,
    "evidence_ref": null,
    "rationale": "AD остаются reversible/two-way в рамках explicit cycle2 brief (EVD-064), включая headers barrier/default=true. APPROVED здесь — архитектурный кандидат, не ACCEPT Совета; R2 и packet/surface freeze обязательны до Coder."
  },
  "independent_review": {
    "required": false,
    "status": "NOT_REQUIRED",
    "reviewer": null,
    "evidence_ref": null,
    "rationale": "S2: universal schema independent_review NOT_REQUIRED сохраняется; обязательный downstream Council R2 с отдельным proof ведёт оркестратор, эта роль не создаёт голос/вердикт."
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
      "question": "H6: совместимы ли с реальным Zen default ask_reject и optional env=deny при гарантированном builtin rejection?",
      "blocking": false,
      "disposition": "Default выбран, автопереключения нет. FakeServe обе policy не доказывает live H6; неизвестная safe capability fail-closed, до H6 боевой disable-file не снимать."
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
    "Измеренные CPU/RSS/FD и реальный proxy egress на 103 KB/6 parallel — обязательный rollout gate, не доказанный Stage 2 факт.",
    "ADR-0005: оформить docs/adr/0005-zen-serve-realtime-reasoning.md и обновить docs/adr/INDEX.md отдельной задачей вне замороженного handoff-architect.md §10. Текущий Read-Only Product Gate разрешает только3 run JSON, поэтому materialization=[] и ADR/product docs здесь не создаются."
  ],
  "verification_policy": {
    "surface_frozen": true,
    "verification_implementation_owner": "Stage 3 Coder пишет tests/test_realtime_reasoning.py; Stage L2 Verifier независимо запускает каждый VER с 0 failed; тесты не считаются выполненными Stage 2",
    "REQ-019_clean_room": "VER-005 проверяет digest/rollout-manifest helper на двух временных fake files внутри sandbox, не ~/.dsh. Реальная синхронизация REQ-019 проверяется только H0 после отдельного rollout; невозможно подтвердить факт deploy чистым unit-тестом.",
    "timing": "FakeClock/RNG и Event-oracles для invariants; socket arrival/CPU реальные измерения отдельными measured/heavy unittest TestCase внутри dedicated suite (stdlib-discover тоже исполняет их). Тест timing держит upstream Event закрытым до чтения 10 дельт, deadline<500ms для interarrival и<=250ms bridge overhead; timeout helper аварийно освобождает Event, чтобы assertion failure не зависала. Не подменять arrival resp.read().",
    "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency.",
    "wire_fixture": "Frozen fixture literals + canonical digest в AD-001 event_contract обязаны использоваться независимым expected oracle. Изменение adapter+FakeServe одной ошибкой не должно сохранять green; corruption delta/token/permission field detection required.",
    "strict_typing": "VER-004 all3files strict0errors, no inherited-error overlay; reportAny/reportExplicitAny server each<=125 и остальные per-rule budgets<=v1. Доказательство исполнения принадлежит clean-room L2, не этой Stage2 роли."
  },
  "high_load_envelope": {
    "schema": "HL-ENV/v1",
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "field_count": 46,
    "units": "SSoT §3.0: memory MiB; times s, CPU cores, rates req/s or conn/s, connections/descriptors/tokens; векторы d и s по канону.",
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
      "Mem_limit_per_pod": 2048,
      "Mem_rss_worker_max": 256,
      "Mem_shared_max": 1152,
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
        "node_ephemeral": 3.6,
        "shared_snat": 1.8
      },
      "C_active_in_scope(s)": {
        "node_ephemeral": 30,
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
      "Mem_limit_per_pod": "handoff-architect §7 design budget2048MiB, normalized per SSoT§3.0/RW-011; host limit not measured, H3 mandatory.",
      "Mem_rss_worker_max": "F-29 parent baseline22MiB; design bound256MiB; H3 actual_parent_RSS_max measured in MiB.",
      "Mem_shared_max": "F-20 idle152MiB; design child192MiB*6=1152MiB aggregate child budget, not RSS measurement. Per-spawn XDG data preserves models path, eliminates intended shared SQLite open; H3 actual6child RSS and zero locks required.",
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
      "FD_worker": "F-29 parent36; bound128 covers6 clients +18 HTTP control/SSE/delivery sockets +12 drains+6 reserve sockets/handles, per-child20FD (F-20); parent+children<256 design, actual H3.",
      "ulimit_n": "F-29 launchctl soft maxfiles=65536; не переносить значение вчерашнего reference packet=4096 как текущий факт.",
      "λ_new_conn_per_pod(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
      "C_active_in_scope(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
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
      "thread_accounting": "До6 handlers +6 SSE readers +6 daemon prompt delivery workers +6 bounded stdout/stderr drain workers +6 gate timers +6 reserve=36; run stdin feed заменяет serve delivery в том же attempt. Не добавлять сверх36 неучтённые workers; каждый owned socket/worker closed/joined вcleanup. HTTP leases: control + SSE + prompt delivery =3 per active serve, максимум18. Не блокировать reject behind POST.",
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
      "ready_budget_s": 3.0,
      "session_setup_budget_s": 2.0,
      "slot_wait_s": 15,
      "spawn_rate_per_s": 1,
      "spawn_burst": 1,
      "total_deadline_s": 1800,
      "estimate_status": "Будущие design ceilings; SLA p99=180s рабочая цель аналитика, не гарантия worst-case sum трёх generation watchdog по60s+aux. Watchdogs не повышают TIMEOUT_S; H1/H2/H3 проверяют actual p99/TTFT перед rollout.",
      "pre_spawn_admission_budget_s": 5.0,
      "admission_policy": "_StartupGate + _SpawnRateLimiter делят один<=5.0s deadline на attempt; никакой суммы независимых5+5. Spawn token hard, gate wait fail-open только в остатке.",
      "session_setup_scope": "POST /api/session + GET /api/event subscription armed<=2.0s до prompt; POST /prompt worker waits по first_event20/first_token60,total1800 и concurrent SSE, не по session_setup.",
      "first_event_anchor": "serve prompt_send_start; first valid current-session execution SSE only; HTTPready/headers/control ignored; O-EXIT first_event_ms measured from request t0",
      "data_isolation": "per-spawn tempfile XDG_DATA_HOME + finally rmtree, OPENCODE_MODELS_PATH preserved; common DB untouched",
      "serve_health": {
        "threshold": 3,
        "ttl_s": 120.0,
        "scope": "per Server/binary key, new auto requests; no model breaker protocol failures"
      },
      "http_sockets_per_serve_max": 3
    },
    "memory_closure_check": {
      "status": "PASS",
      "unit": "MiB",
      "lhs_mib": 1408,
      "rhs_mib": 1638.4,
      "substitution": "W*Mem_rss_worker_max+Mem_shared_max=1*256+1152=1408 <=0.80*2048=1638.4 MiB",
      "evidence_level": "design estimate only; NOT measured runtime PASS",
      "runtime_gate": "H3: actual_parent_RSS_max+6*actual_child_RSS_max<=1638.4MiB; 103KB×6×3; zero database is locked, actual cleanup dirs/FD/CPU; FAIL forbids production enable"
    },
    "field_units": {
      "P_steady": "pods",
      "P_hpa_max": "pods",
      "maxSurge_pct": "ratio",
      "maxSurge_abs": "pods",
      "maxUnavailable_pct": "ratio",
      "maxUnavailable_abs": "pods",
      "P_terminating_overlap": "pods",
      "P_live": "pods",
      "P_avail_min": "pods",
      "W": "proc/pod",
      "N_proc": "processes",
      "N_proc_steady": "processes",
      "N_proc_avail_min": "processes",
      "CPU_limit_per_pod": "cores",
      "κ_skew": "ratio",
      "u_bg_worker": "cores",
      "U_pod_sidecars": "cores",
      "Mem_limit_per_pod": "MiB",
      "Mem_rss_worker_max": "MiB",
      "Mem_shared_max": "MiB",
      "RPS_peak": "req/s",
      "A_max": "attempts/req",
      "SLA_p99_s": "s",
      "N_entities_max": "items",
      "Limit_dep_share[d]": "connections",
      "Limit_dep_rps[d]": "req/s",
      "W_fetchers[d]": "proc/pod",
      "J_init_s[d]": "s",
      "J_pod_s[d]": "s",
      "T_poll_s[d]": "s",
      "K_calls[d]": "calls",
      "T_base_s[d]": "s",
      "T_cap_s[d]": "s",
      "Max_stale_age_s[c]": "s",
      "Min_healthy_ratio": "ratio",
      "B_retry_max": "tokens",
      "min_reserve_retry_rps": "req/s",
      "FD_worker": "descriptors",
      "ulimit_n": "descriptors",
      "λ_new_conn_per_pod(s)": "conn/s",
      "C_active_in_scope(s)": "connections",
      "N_pods_in_scope(s)": "pods",
      "Port_range_size(s)": "ports",
      "T_hold_s(s)": "s",
      "SNAT_ips_count(s)": "IPs",
      "HOTPATH_MODULES": "list[str]"
    }
  },
  "resilience_gates": {
    "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
    "HL_ENV_v1": {
      "HL-ENV-01": {
        "status": "PASS",
        "substitution": "46 exact keys/sources/field_units SSoT§3.0; memory inMiB:1*256+1152=1408<=0.80*2048=1638.4. N/A сохраняет actual diff и transitive graph; runtime H3 NOT_RUN.",
        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist. Assert memory units exact MiB and actual H3 inequalities separately; bytes вместо MiB FAIL.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      }
    },
    "C_MULT": {
      "C-MULT-I1": {
        "status": "PASS",
        "substitution": "Roles bridge=1 process, M=6 exclusive child leases, G_reload=1 close-before-create; other roles0, no daemon overlap. georouter6<=.60*80=48; opencode_local_db design logical6<=.60*10=6 НЕ физическая SQLite pool quota. Каждый child own XDG_DATA_HOME и own DB, OPENCODE_MODELS_PATH preserved, shared2.27GB DB untouched. Design memory1408<=1638.4MiB, но runtime SQLite/memory PASS только после H3 actual parent+6child<=.80*2048MiB и zero database is locked на103KB×6×3.",
        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling. Fake XDG dirs unique per spawn and deleted on all exits; H3 real peaks/zero locks обязательны до enable, retry не маскирует lock failure; runtime_status NOT_RUN.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
        "runtime_status": "NOT_RUN_H3_REQUIRED"
      },
      "C-MULT-I2": {
        "status": "PASS",
        "substitution": "Per-process manager: M=effective MAX_CONCURRENT (default2/deploy6), max_waiters<=2M (default clamp4/deploy12), wait<=15s; fixed max3 HTTP sockets/active serve (reusable control+event+prompt delivery), queue<=4096 events И <=1MiB, frame<=1MiB; no Redis SQL connection pool added. Общий ingress _SlotBulkhead обязан применять этот effective bound и при run, иначе default M=2/waiters12 нарушил бы 2M; не вводить вторую неучтённую очередь перед manager.",
        "oracle": "Блокировать M+2M leases, следующий fast-fail без Popen/connect, сокетов<=3M, queue byte-overflow explicit error; inspect configured ceilings. Нельзя снижать общий production slot count или повышать max_waiters.",
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
        "substitution": "ParentFD128<=.70*65536=45875.2; parent+6children20FD<256 design. control+SSE+prompt=3HTTP sockets per child. node ports3.6*1*60+30=246<=8192; sharedSNAT1.8*1*60+12=120<=8192. Readiness<=3 connects; control reusable. Actual FD/RSS/cleanup/network closure H3 mandatory.",
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
        "substitution": "Snapshot/config startup/poll path absent: W_fetchers=0,K_calls=0 => batch K×(λ+4sqrtλ+4)=0<=.5×1=.5 и R_poll=0<=.2×1=.2. 1/s field — self-configured request spawn rate, НЕ неизвестная квота dependency; запрещено объявлять gate PASS через фиктивную внешнюю RPS. Request cold-start отдельно ограничен combined gate+token admission<=5.0s (gate hold<=12s, не additive wait) + token bucket1/s burst1 для КАЖДОГО child включая fallback.",
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
        "substitution": "Regex compiled at import; нет per-delta json.loads правил/конфигов, model_validate/deepcopy/static label binding. json.loads одного входного SSE frame необходим для transport framing и не является forbidden config reload parse. Serve ask_reject/deny config merge один раз per attempt setup вне delta loop.",
        "oracle": "Спай на re._compile/config decoder/model_validate/typeadapter/deepcopy/static labels в delta loop ->0; wire decoder count==one per actual event, не full history; tool JSON parser exempt by input decoding purpose.",
        "verification_ids": [
          "VER-005"
        ],
        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
      },
      "H-CPU-I3": {
        "status": "PASS",
        "substitution": "Первые serve guards: if disabled or TRANSPORT=run return legacy до UUID/password/clock/queue/threads/probe. Enabled selector проверяет O(1) os.path.exists(disable-file); present ->run до serve allocations/subprocess. auto health-degraded/shebang ->run без probe. Default=true native path не отменяет zero-serve-cost explicit disabled path; legacy watchdog/status остаются RC2/RC3 fixes. Status guard thinking+SSE до format; bounded put_nowait events, overflow explicit error+cleanup; optional telemetry drop counters.",
        "oracle": "VER-005 spy explicit0/run/disable-file ->0 serve alloc/password/probe/extra Popen; while same process create/remove file next request toggles transport. Queue overflow explicit cleanup; no disabled UUID/serialization. File stat O(1), no recursive IO.",
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
        "substitution": "15.0 + 3 * (5.0 + 3.0 + 2.0 + 1.2) + 3.0 = 51.6 s <= 0.30 * 180 = 54.0 s; headroom=2.4s. Slot15 один раз, combined pre-spawn admission5 на attempt, owner/ready3, create+subscribe2, cleanup1.2, суммарный backoff cap1+2=3. Prompt POST/generation под first_event20/first_token60/stall60 и total1800, не session_setup. Каждому I/O timeout=min(phase_remaining,request_remaining); cleanup финальный<=1.2 даже после request deadline. После deadline ни spawn/prompt/sleep.",
        "oracle": "FakeClock recompute51.6<=54 и headroom>=2.0; admission gate+limiter sum<=5.0, ready3/create+subscribe2/cleanup1.2, prompt POST не входит в2s; slow create timeout ->one budgeted run pre-header; headers received or session event ->zero silent run, Popen<=3. Deadline exhausted->zero further I/O. Никаких leftover gate5+spawn5/ready.5/setup.2.",
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
        "substitution": "Model _UpstreamBreaker threshold5/cooldown10*U(.8,1.2), HALF_OPEN1 owner не освобождается по одному cooldown до terminal/cleanup; provider failures/успешное восстановление как прежде. Отдельный _ServeHealth threshold3/TTL120/one recovery probe для serve protocol-only failures; first_event_timeout без session execution и invalid_serve_event НЕ model breaker failure, subsequent auto->run. Accepted current prompt не получает silent run fallback. Auth/permission/security401/403 fail-closed, no policy switch; client cancel neutral. TTL/run skips не продлевают outage; native binary key change инвалидирует capability/health. Resource/retry/slot caps едины.",
        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret. Отдельно five serve-protocol failures forced mode ->model breaker closed, no .failure calls; auto third failure arms120s,next auto run, no silent replay current request; atTTL exactly1probe, success resets, failed protocol rearms120; provider5 failures still open model breaker.",
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
      "substitution": "Request/attempt ownership включает PGID, stdout/stderr, SSE/control sockets, session id, queue/readers и startup gate. AD-003 cleanup на всех exits<=1.2s, child group reap; leader early-exit не оставляет grandchildren. Server shutdown manager запрещает новые leases и отменяет все активные, затем closes all. Ownership включает isolated XDG_DATA_HOME и daemon delivery socket/thread; finally rmtree owned dir после kill/reap, never common DB. Foreign listener cleanup no API/kill to foreign PID.",
      "oracle": "VER-005: 50 cancellations + leader-exits-first descendant + blocked socket/readiness + partial prompt + overload/shutdown; zero active/waiters/children/readers/sockets; PIDs/PGIDs только свои. Assert unique data dirs and deleted after all50 cancellations/partial prompt/port race; join delivery reader and no owned temp dirs.",
      "verification_ids": [
        "VER-005"
      ]
    },
    "O_EXIT_v1": {
      "status": "PASS",
      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется. first_event_ms только valid current-session execution SSE после prompt, относительно request t0; HTTPready/POST headers не являются first_event. transport_history/reason раздельно protocol/model/security/TTL, no phantom spawns.",
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
        "timeout_budget": "Owner proof+GET /api/session/active aggregate ready<=3.0s (cache-miss schema внутри3); POST session+GET event armed<=2.0s; POST prompt excluded, concurrent SSE/watchdogs",
        "bulkhead": "manager leases<=M, control+SSE+prompt delivery<=3M sockets",
        "circuit_breaker": "_ServeHealth3/TTL120/probe1 for protocol; _UpstreamBreaker5 for provider; auth/permission fail-closed",
        "failure_mode_fallback": "Auto ServeUnavailable до POST prompt response headers и до current-session execution event ->cleanup+budgeted run. Headers OR event latch delivered; then no silent run.401/403/permission missing never fallback."
      },
      {
        "dependency_operation": "opencode model execution (serve or run)",
        "path": "hot",
        "timeout_budget": "Serve first-event20/first-token60 от prompt_send_start; stall60 от useful token; requestTIMEOUT1800 common. HTTP readiness отдельно<=3 и не гасит first_event.",
        "bulkhead": "_slots effectiveM, waiters<=2M, one child per slot",
        "circuit_breaker": "Provider _UpstreamBreaker5/jitter/HALF_OPEN1; serve-specific invalid/no-event ->_ServeHealth3/TTL120 only",
        "failure_mode_fallback": "Watchdog ->cleanup+same-transport explicit budgeted retry; accepted current request never silent run. Protocol degradation directs NEW auto requests to run; fatal4xx/security/cancel no retry."
      },
      {
        "dependency_operation": "_StartupGate/_SpawnRateLimiter",
        "path": "hot/aux",
        "timeout_budget": "Shared pre-spawn admission<=5.0s total (gate wait only remaining after hard token); hold<=12 not additive, cancel poll<=.25",
        "bulkhead": "1 gate, token bucket1/s burst1",
        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
        "failure_mode_fallback": "Gate wait fail-open лишь в оставшемся5s; token timeout prohibits spawn, limiter never bypassed. No independent5+5 waits."
      },
      {
        "dependency_operation": "serve interrupt/delete and process cleanup",
        "path": "cleanup",
        "timeout_budget": "interrupt+delete<=.2,TERM grace<=.5,reap/join delivery+SSE+owned rmtree within remaining .5; total<=1.2, bounded even on deadline",
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
      },
      {
        "dependency_operation": "serve permission rejection",
        "path": "hot/control",
        "timeout_budget": "Immediate control reply<=.25s capped request/phase remaining, never queued behind prompt response",
        "bulkhead": "Use one idle control connection; delivery worker uses separate bounded prompt socket, <=3 sockets per active serve",
        "circuit_breaker": "Security fail-closed, not model/protocol fallback",
        "failure_mode_fallback": "permission.asked ->decision=reject; missing endpoint/bad reply401/403 ->cleanup+explicit error; never allow/once/always"
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
      "rationale": "ask_reject/deny never allow; explicit brief chooses responseheaders OR sessionexecution deliverybarrier. Beforebarrier unknown delivery may fallback only after ownedcleanup/cap; afterbarrier only explicit same-transport retry+status, never silentrun. Not exactly-once; tool IDs dedup.",
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
    "architecture_contract": "Cycle2 fix-from-panel candidate APPROVED; 14 RW+7 FU resolved at design level, R2 council verdict и ARCH_GATE не выносятся этой ролью",
    "implementation_tests": "NOT_RUN — код/tests Stage3 ещё не создавались",
    "live_acceptance": "NOT_RUN — H0..H9 отдельно; не менять ~/.dsh",
    "pending_orchestrator_actions": [
      "Council R2 по diff v1→v2 и rework_resolutions; отдельные launch_seat/verify_panel_proof",
      "Обновить task envelope packet/surface hashes и проверить ARCH_GATE с новыми role-plan/fingerprints (вне трёх разрешённых файлов роли)",
      "Stage3 Coder, independent clean-room strict VER001..005",
      "H3/H6 safety gates до production sync; H0..H9 live acceptance, ещё NOT_RUN"
    ]
  },
  "verification_acceptance_matrix": {
    "FakeServe": "Stdlib subprocess implements exact frozen_v2_1_2_fixtures API/SSE, Basic401, /api/session/active, /openapi.json only per binary-key first handshake, session/prompt/interrupt/delete/permission decision=reject. Tests force serve for shebang; no Zen calls. Independent fixed fixture digest oracle + deliberate field/schema mutations; fake/adapter mutual agreement alone insufficient. GET active returns {data:{}} not[]; once-per-key /api/info version+PID and API schema info.version0.0.1, independent binary appversion2.1.2; invalid numeric error.status must fail validation.",
    "mode_matrix": [
      "default flag=true+auto+native MachO ->serve после safety rollout; shebang fake ->run once no probe, all378baseline existing tests target green",
      "explicit flag0/false or TRANSPORT=run ->run before serve allocations/stat/probe; enabled disable-file present ->run after one O(1)exists; create/remove file same process toggles next request without restart",
      "force serve+FakeServe shebang ->v2 SSE/JSON, stdinDEVNULL; fake legacy blocking stdin ->EOF/ready failure<=3s explicit no silent run",
      "auto ServeUnavailable in spawn/create/subscribe or pre-response-headers prompt and no execution SSE ->complete cleanup then1budgeted run fallback; totalPopen<=3",
      "POST prompt headers arrived OR valid session execution SSE while headers pending ->delivered; zero silent run, remaining first-event/token clocks active; explicit security401/403/cancel no fallback at any phase",
      "Default ask_reject, env deny both frozen permission rules; unsupported policy/missing safe endpoints fail-closed, no automatic policy switching",
      "Auto _ServeHealth3protocol failures ->TTL120 run new requests; provider breaker remainsclosed for protocol-only, provider failures remain independent",
      "Compare frozen immutable_run_env function SHA256, tests/test_run_env.py/start.sh SHA256; preserving tests by editing expected hashes запрещено."
    ],
    "status_matrix": [
      "slow blank upstream + startup-gate/rate-wait: grace.30 first [мост] LF<=1s",
      "fast real reasoning/text before grace: no initial status; Simple greeting. exact",
      "off/none/nonthinking + slow upstream: no synthetic reasoning; normal content/keepalive/error unchanged",
      "whitespace/empty comments/status do not set first-token or attempt_output",
      "retry accepted after model reasoning: exactly one retry status, raw model bytes retained, no reasoning dedup",
      "normal127ms model reasoning: no periodic status, natural LF enables collapsed preview, no newline injected into model delta",
      "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes",
      "Model reasoning chunk без trailingLF ->synthetic delta \"\\n[мост] ...\\n\"; whole delta incl leading LF provenance=synthetic, model-only concatenation exact bytes, literal model [мост] survives; LF already present->no redundant prefix; fast Simple greeting.->zero statuses."
    ],
    "watchdog_matrix": [
      "Serve HTTP ready success + accepted prompt headers but zero session SSE ->first_event_timeout at20s from prompt_send_start +cleanup<=1.2 (<22s); first_event_ms remainsnull",
      "Legacy first-event from attempt start until first valid run event/step_start; serve ready3 and create+subscribe2 bounded independently before prompt",
      "Current session execution.started/step.started/reasoning.started SSE after prompt satisfies first_event once; first_event_ms=request-relative; foreign sessions/pre-prompt started/server.connected/session.created/comments/status do not satisfy",
      "Valid started/control but no useful model token ->first_token_timeout60s; started/control/comments/reject not token, no indefinite reset",
      "After first useful model delta pause>stall60 ->stall_timeout; comments/bridge statuses/repeated transport noise do not reset",
      "POST prompt delivery blocked past2s while SSE progresses is permitted; supervisor/reader/writer concurrent and cancel-aware, no duplicate prompt; request totaldeadline neverreset, no retry4"
    ],
    "lifecycle_matrix": [
      "disconnect at gate/limiter/ready/prompt/blocked SSE/after reasoning, detect<=5s and PGID absent<=7s",
      "leader exits but descendant holds stdout; group still killed",
      "SIGTERM ignored ->SIGKILL, leader reaped, no child/grandchild",
      "success/tool step/error/fallback/shutdown each closes session/socket/threads/slot once",
      "byte queue/frame/output overflow explicit error (no silent model delta loss)",
      "50 cancel fault-injection cycles counters in_use/waiters/sessions/sockets/readers=0",
      "Foreign listener PID/PGID after reserve-release ->zero Authorization/password/prompt bytes, no foreign API/kill; bounded port retry ready3s and totalspawns<=3.",
      "Unique per-spawn XDG_DATA_HOME across6parallel/retries; _run_env bytehash unchanged, OPENCODE_MODELS_PATH retained; finally tempdir removed after all exits, 50cancel cycles and deliveryworker cleanup."
    ],
    "tools_matrix": [
      "every split point and single-char deltas for both tags, JSON embedded close strings/code quoting existing fixtures",
      "stream content before open tag visible immediately, pending genuine prefix<=12 plus inherited code-context lookahead",
      "unparsed/open genuine blocks stripped by existing wrapper, no raw tool tags in SSE content",
      "native call lifecycle normalized/dedup per call-id, mapped/unmapped behavior identical; no auto allow",
      "step.ended tokens input/output/cached/reasoning counted once then tool finish, no followup synthetic step",
      "early legacy error may recover; late transient/fatal error and incomplete recovery same on fake v2",
      "existing reasoning_interrupted and interrupted cleanup across delta boundaries",
      "permission.asked {data.id,sessionID,action,resources,source} ->POST reply {decision:reject},status204; both ask_reject/deny modes; POST prompt may stayblocked while reject executes on separate control socket; never once/always/allow.",
      "Frozen wire tokens.cache.read/write ->canonical tokens{input,output,cached=cache.read,reasoning}; mutate delta path/cache envelope/permission lifecycle ->independent oracle fail, step assistantMessageID dedup, not invented wire stepID."
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
      "HALF_OPEN active probe held across reset_s boundary: zero second probes until owner cleanup; common _SlotBulkhead code-default M2/waiters4 and deploy M6/waiters12, no second uncounted ingress queue.",
      "Combined gate+limiter5,ready3,create+subscribe2,cleanup1.2;15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; slowcreate->one preheader run; afterheader/event->no run; no fourthPopen.",
      "_ServeHealth force5protocol failures ->zero model breakerfail; auto3failures->next run untilTTL120, expiry oneprobe, successful terminalreset, protocolfailrearm; binarymtime+size change invalidates capability; real provider5 failures modelbreakerOPEN.",
      "Memory SSoT fields2048/256/1152 MiB exactly; design1408<=1638.4 not H3PASS.3HTTP sockets per serve supports immediate reject while promptHTTP pending; recalc nodeports246<=8192."
    ],
    "rollout_boundary": "VER001..005 не обращаются к ~/.dsh. В root suite test_dsh_profile_config видит отсутствие live profile в clean-room и делает inherited skip. Actual REQ019 identity и H0..H9 отдельный rollout gate; fake digest fixture не подменяет read-back deployed file. Default=true не bypass: pre-production candidate H3/H6 mandatory, file disabled until safety PASS; H3 actualRSS + no DB locks103KB×6×3. H9 toggles file withoutrestart in existing chat. All H NOT_RUN in Stage2."
  },
  "semantic_checks": {
    "canonical_hl_field_set": "46/46 exact key equality and field_sources/field_units equality against team architecture.md §3.0",
    "stop_codes": "21 main codes + T-LIFE/O-EXIT/M-SEM=24 unique",
    "legacy_antipatterns": "21 exact keys from approved reference schema",
    "verification_owner": "5/5 owner=verifier",
    "decisions": "4/4 two-way with >=2 genuine alternatives",
    "evidence_refs": "64 unique EVD IDs; analyst49 F-01..F-49 неизменны; council refs отдельный PANEL-F-NNN namespace; invalid analyst refs запрещены.",
    "status_protocol": "3 templates begin[мост]/endLF; при model unterminated line весь дополнительный leading LF synthetic, template bytes модели не менять.",
    "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes.",
    "VER_004_syntax": "Strict command compiled with ast.parse in cycle2; execution pending Stage3 because new test file absent",
    "rework_coverage": "14RW+7FU exactly once in rework_resolutions; source_findings uses PANEL-F-NNN; resolved means architecture delta, NOT implementation/runtime PASS",
    "memory_units": "All46 canonical keys+field_sources+field_units; memory2048/256/1152 MiB;1408<=1638.4MiB",
    "aux_budget": "15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; old independent5+5/.5/.2 absent",
    "wire_evidence": "Actual binary2.1.2 permission.asked/decision=reject and cache.read/write normalized explicitly; fixture SHA256 locked; five families independent adapter/mock oracle Readiness data map and appversion/api schema version separated; StructuredError.status numeric mapping frozen."
  },
  "routing_profile": "standard",
  "panel_resolution_choices": [
    {
      "ids": [
        "RW-001",
        "RW-007"
      ],
      "source_positions": [
        "PANEL-F-001: headers response barrier",
        "RW-001.evidence: Seat2 начало POST barrier"
      ],
      "resolution": "Текущий explicit user brief выбирает response headers OR started session event; unknown pre-header delivery может fallback только после полного cleanup; after-header no silent run. Admission/create budgets отделены от prompt wait."
    },
    {
      "ids": [
        "RW-002"
      ],
      "source_positions": [
        "PANEL-F-002: допускается один safe policy transition до prompt",
        "PANEL-F-018: unsupported policy fail-closed без auto-switch"
      ],
      "resolution": "Default ask_reject и явный env deny, автоматического переключения НЕТ вообще. После accepted401/403 fatal; live H6 обязателен."
    },
    {
      "ids": [
        "RW-006",
        "RW-009"
      ],
      "source_positions": [
        "PANEL-F-006: H3 обязателен до включения",
        "PANEL-F-010: default=true без start.sh"
      ],
      "resolution": "Default=true сохранён в коде design; candidate H3/H6 до production sync, боевой file switch удерживается до допуска. Нельзя сначала включить default, а потом искать RSS."
    },
    {
      "ids": [
        "RW-011",
        "RW-012"
      ],
      "source_positions": [
        "PANEL-F-012: канон MiB, byte арифметика недостаточна",
        "PANEL-F-013: strict0error вместо старого allowance"
      ],
      "resolution": "MiB exact values; type allowance удалён; существующие2errors — baseline debt для исправления Coder в server.py, не текущий PASS."
    },
    {
      "ids": [
        "RW-004",
        "RW-007"
      ],
      "source_positions": [
        "Brief logical session.permission.requested/tokens.cached",
        "EVD-062 actual v2.1.2 permission.asked/tokens.cache.read+write; permission reply decision"
      ],
      "resolution": "Freeze actual wire literals и canonical expected mapping, не изобретать отсутствующие поля/имена. Group labels сохранены в fixture families для механического verify-fixed."
    }
  ],
  "rework_resolutions": [
    {
      "id": "RW-001",
      "source_findings": [
        "PANEL-F-001"
      ],
      "status": "RESOLVED",
      "changes_made": "Pre-header fallback + session-event earlier barrier, explicit unknown-delivery risk and same-transport retries. create/subscribe budget separated from concurrent POST generation, cap3 unchanged.",
      "packet_locations": [
        "#/decisions/0/details/fallback_barrier",
        "#/decisions/0/details/session_wire",
        "#/resilience_gates/R_BULK/R-BULK-I1",
        "#/verification_acceptance_matrix/mode_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-002",
      "source_findings": [
        "PANEL-F-002",
        "PANEL-F-007",
        "PANEL-F-018"
      ],
      "status": "RESOLVED",
      "changes_made": "Default ask_reject, env deny, _serve_env over byte-identical _run_env; decision=reject only, missing capability/401/403 fail-closed, no automatic policy transition.",
      "packet_locations": [
        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY",
        "#/decisions/0/details/tool_policy",
        "#/risks/0",
        "#/threat_model/threats/1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-003",
      "source_findings": [
        "PANEL-F-003"
      ],
      "status": "RESOLVED",
      "changes_made": "Parent bind0/reserve/release-before-Popen explicitport; lsof PID/PGID proof before Authorization/prompt, foreign listener zero leakage/own cleanup and bounded retry.",
      "packet_locations": [
        "#/decisions/0/details/listener_ownership",
        "#/decisions/0/details/spawn",
        "#/threat_model/threats/0",
        "#/verification_acceptance_matrix/lifecycle_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-004",
      "source_findings": [
        "PANEL-F-004"
      ],
      "status": "RESOLVED",
      "changes_made": "Five frozen fixture families with exact source-proven field paths+canonical expectation+SHA256; actual wire permission.asked, reply decision and tokens.cache.read normalized, not invented aliases.",
      "packet_locations": [
        "#/decisions/0/details/event_contract",
        "#/evidence/61",
        "#/verification_policy/wire_fixture"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-005",
      "source_findings": [
        "PANEL-F-005"
      ],
      "status": "RESOLVED",
      "changes_made": "REQ-013/AD-001/RISK-002 guarantee only per-spawn proxy-env rotation AC-018; loopback georouter NO_PROXY bypasses child HTTP_PROXY, no guaranteed clean Zen IP.",
      "packet_locations": [
        "#/requirements/12",
        "#/decisions/0/drivers",
        "#/risks/1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-006",
      "source_findings": [
        "PANEL-F-006"
      ],
      "status": "RESOLVED",
      "changes_made": "Per-spawn XDG_DATA_HOME+preserved OPENCODE_MODELS_PATH+finally rmtree, H3 actualRSS parent+6children<=1638.4MiB/zero DB locks103KB×6×3; no Stage2 runtime PASS.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/C_MULT/C-MULT-I1",
        "#/evolution/H3_rollout_gate"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-007",
      "source_findings": [
        "PANEL-F-008"
      ],
      "status": "RESOLVED",
      "changes_made": "Lightweight active-session readiness3s; combined admission5s; create+subscribe2s; daemon POST delivery concurrent SSE; exact Model.Ref/providerID/id/variant and session permissions array; total51.6<=54.",
      "packet_locations": [
        "#/decisions/0/details/startup",
        "#/decisions/0/details/admission",
        "#/decisions/0/details/session_wire",
        "#/high_load_envelope/operational_profile",
        "#/resilience_gates/dependency_failure_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-008",
      "source_findings": [
        "PANEL-F-009"
      ],
      "status": "RESOLVED",
      "changes_made": "Serve first_event20 only current-session execution SSE after prompt; HTTP readiness/headers ignored; independent clocks and request-relative first_event_ms, accepted-noevents timeout<=22s.",
      "packet_locations": [
        "#/decisions/2/details/clocks",
        "#/decisions/2/details/telemetry",
        "#/verification_acceptance_matrix/watchdog_matrix",
        "#/resilience_gates/O_EXIT_v1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-009",
      "source_findings": [
        "PANEL-F-010"
      ],
      "status": "RESOLVED",
      "changes_made": "Default=true+auto native, shebang directrun all378baseline target; file disable no restart. Candidate H3/H6 before prod sync+held disable-file reconciles mandatory safety gate.",
      "packet_locations": [
        "#/decisions/0/details/configuration",
        "#/decisions/0/details/auto_fake_compatibility",
        "#/evolution/rollout",
        "#/evolution/feature_flag"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-010",
      "source_findings": [
        "PANEL-F-011",
        "PANEL-F-016"
      ],
      "status": "RESOLVED",
      "changes_made": "Tool-policy reference corrected to EVD-050+F-08; analyst IDs restricted49 facts, council refs PANEL-F-NNN.",
      "packet_locations": [
        "#/decisions/0/details/tool_policy",
        "#/evidence/49",
        "#/semantic_checks/evidence_refs"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-011",
      "source_findings": [
        "PANEL-F-012"
      ],
      "status": "RESOLVED",
      "changes_made": "SSoT46 exact fields/sources/units, memory2048/256/1152MiB and1408<=1638.4MiB across HL-ENV/memory closure.",
      "packet_locations": [
        "#/high_load_envelope/required_hl_env_fields",
        "#/high_load_envelope/units",
        "#/high_load_envelope/field_units",
        "#/high_load_envelope/memory_closure_check",
        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-012",
      "source_findings": [
        "PANEL-F-013"
      ],
      "status": "RESOLVED",
      "changes_made": "VER004 strict ruff format/check and basedpyright on all3files; zero errors, removed v1 error allowance; preserved server Any and other warning ceilings; inherited error debt explicitly assigned to Coder.",
      "packet_locations": [
        "#/verification_surface/3",
        "#/risks/7",
        "#/decisions/0/details/typing"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-013",
      "source_findings": [
        "PANEL-F-017"
      ],
      "status": "RESOLVED",
      "changes_made": "Leading LF in entire synthetic status after unterminated model chunk, provenance filter preserves model bytes and literal model [мост]; fast Simple greeting unchanged.",
      "packet_locations": [
        "#/decisions/1/details/status_separator",
        "#/decisions/1/details/pure_reasoning",
        "#/verification_acceptance_matrix/status_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "RW-014",
      "source_findings": [
        "PANEL-F-019"
      ],
      "status": "RESOLVED",
      "changes_made": "_ServeHealth threshold3/TTL120/one recovery probe newauto requests only; protocol failure neutral to model breaker; exact version/schema cache by binary stat; no silent accepted-prompt replay.",
      "packet_locations": [
        "#/decisions/0/details/transport_health",
        "#/decisions/0/details/protocol_compatibility",
        "#/decisions/2/details/retry",
        "#/resilience_gates/R_BULK/R-BULK-I3",
        "#/verification_acceptance_matrix/resilience_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-001",
      "source_findings": [
        "PANEL-F-014"
      ],
      "status": "RESOLVED",
      "changes_made": "Isolated per-spawn XDG_DATA_HOME, preserve models path, cleanup finally; risk/H3 and lifetime updated.",
      "packet_locations": [
        "#/decisions/0/details/data_isolation",
        "#/risks/2",
        "#/resilience_gates/T_LIFE_v1"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-002",
      "source_findings": [
        "PANEL-F-015"
      ],
      "status": "RESOLVED",
      "changes_made": "ADR0005+INDEX explicitly deferred outside frozen scope §10, materialization remains empty.",
      "packet_locations": [
        "#/deferred/3",
        "#/materialization"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-003",
      "source_findings": [
        "PANEL-F-020"
      ],
      "status": "RESOLVED",
      "changes_made": "Residual cross-provider reasoning replay risk accepted and mitigation short/infrequent nonsecret statuses recorded.",
      "packet_locations": [
        "#/risks/10",
        "#/decisions/1/details/replay"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-004",
      "source_findings": [
        "PANEL-F-021"
      ],
      "status": "RESOLVED",
      "changes_made": "ruff format --check explicitly covers all3files alongside linter.",
      "packet_locations": [
        "#/verification_surface/3"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-005",
      "source_findings": [
        "PANEL-F-022"
      ],
      "status": "RESOLVED",
      "changes_made": "New JSON typed object+narrowing/TypedDict within server.py, no new module/allowlist expansion; reportAny/reportExplicitAny each<=125.",
      "packet_locations": [
        "#/decisions/0/details/typing",
        "#/verification_surface/3"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-006",
      "source_findings": [
        "PANEL-F-023"
      ],
      "status": "RESOLVED",
      "changes_made": "File disable switch os.path.exists request-entry O(1), default ~/.dsh path/env override, same PID H9 toggle, no restart required; no live file modified.",
      "packet_locations": [
        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
        "#/evolution/rollback",
        "#/verification_acceptance_matrix/mode_matrix"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    },
    {
      "id": "FU-007",
      "source_findings": [
        "PANEL-F-024"
      ],
      "status": "RESOLVED",
      "changes_made": "Budget51.6s<=54s, headroom2.4>=2.0, combinedadmission5+ready3+setup2+cleanup1.2 explicit.",
      "packet_locations": [
        "#/resilience_gates/R_BULK/R-BULK-I1",
        "#/high_load_envelope/operational_profile"
      ],
      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
    }
  ],
  "rework_source": {
    "path": "handoff/panel-rework-brief-arch-a1.json",
    "sha256": "d173ff674c5a105fd85ab00a2a276ebcfb92d9b7295523721e9eed6503e5ed96",
    "base_packet_path": "architecture/architecture-packet.v1.json",
    "base_packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
    "resolutions_count": 21,
    "blocking_count": 14,
    "nonblocking_count": 7,
    "namespace": "Analyst F-01..F-49; council PANEL-F-001..024 = original brief finding ids prefixed PANEL-; RW/FU IDs unchanged"
  }
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/receipts/arch-gate.json sha256=b890fe52af868a78f461e7f3d4779ad506a07b0b6de13c51dbba01740f9ef8a7
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "criticality": "S2",
  "packet_sha256": "c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d",
  "verification_surface_sha256": "66e68ca767d07b24b7afacb40f8c84abde9f26837a50d38ccba03a3824a5ce84",
  "protected_paths_sha256": "98f7f5f54622baf379b40bad458cf3ef2a1952644fb79fb662ebe11f70659d8b",
  "architect_worktree_sha256": "2bcabd4d9c9bdf3d108afbae3344a2b4e7350c7d697355529fc2360d73eb7334",
  "materialized_targets": 0
}
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.v1-to-v2.diff sha256=cf3492d3470a28a0b392f7fb0294fcbec6f02df131040469a3f9404e181951b3
# Mechanical unified diff (diff -u): Architecture Packet v1 -> v2
# old_revision: architecture-packet.v1.json sha256=e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02
# new_revision: architecture-packet.json sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d
--- architecture-packet.v1.json (sha256=e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02)
+++ architecture-packet.json (v2 sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d)
@@ -1,24 +1,24 @@
 {
   "schema_version": "1.0",
-  "packet_version": "1.0",
+  "packet_version": "2.0",
   "task_id": "zen-realtime-reasoning",
   "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
   "preset": "analyst-teamlead",
-  "cycle": 1,
+  "cycle": 2,
   "criticality": "S2",
   "profile": "python-aisdlc-gcge",
   "status": "APPROVED",
   "role_plan": {
-    "path": "plans/architect-01.json",
-    "sha256": "d435226fff3370982e236d7e5bb885d341331d70a2022e67c4d9f8a594a5283c"
+    "path": "plans/architect-02.json",
+    "sha256": "8bede3e0b7daecf01212133dee566014df3472bb244fde2fbc09bedf3ef25f1e"
   },
-  "summary": "Гибрид C/A1: короткоживущий serve v2 на попытку, общий нормализованный поток событий для SSE и JSON, run как kill-switch и безопасный pre-prompt fallback; grace-статусы, три watchdog и гарантированная уборка PGID. Это проектный контракт Stage 2, не утверждение о выполненных изменениях или живой приёмке.",
+  "summary": "Гибрид C/A1, цикл 2 fix-from-panel: ephemeral serve v2.1.2 с точным wire-контрактом, ask_reject, отдельными readiness/session/watchdog бюджетами, pre-response-headers fallback и sticky transport health; run kill-switch без рестарта. APPROVED означает проектный контракт-кандидат для R2, не council PASS или живую приёмку.",
   "scope": {
     "repo_root": "~/tmp/cli-agent-bridge/zen-realtime-reasoning",
     "branch": "feature/zen-realtime-reasoning",
     "architect_write_allowlist": [
-      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-01.before.json",
-      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-01.json",
+      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.before.json",
+      ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/plans/architect-02.json",
       ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json"
     ],
     "coder_target_files": [
@@ -119,7 +119,7 @@
       "id": "REQ-006",
       "priority": "MUST",
       "statement": "Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку",
-      "acceptance": "AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с",
+      "acceptance": "AC-008: фейковый транспорт без вывода завершается убийством и ретраем или ошибкой за порог плюс 2 с На serve локальный HTTP ready не считается execution event: после отправки prompt валидного события текущей session нет20s ->first_event_timeout+cleanup<=2s.",
       "evidence": "F-09, F-30, F-31",
       "verification_ids": [
         "VER-005"
@@ -192,9 +192,9 @@
     {
       "id": "REQ-013",
       "priority": "MUST",
-      "statement": "Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта",
+      "statement": "REQ-013 уточнение под AC-018: per-spawn ротация _next_standalone_proxy и proxy env сохраняется на каждом child; _StartupGate, spawn rate, bulkhead и model Circuit Breaker действуют на обоих транспортах. loopback georouter baseURL=http://127.0.0.1:10830/v1 идёт по NO_PROXY в обход child HTTP_PROXY; смена реального Zen egress IP этим не гарантируется.",
       "acceptance": "AC-018: два последовательных запуска получают разные записи пула прокси (проверка через подменённый `_next_standalone_proxy`)",
-      "evidence": "F-10, F-11, F-15, F-32",
+      "evidence": "F-10, F-11, F-15, F-27, F-32; RW-005",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -225,7 +225,7 @@
       "id": "REQ-016",
       "priority": "MUST",
       "statement": "Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода",
-      "acceptance": "AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST`",
+      "acceptance": "AC-021: строка `O-EXIT/v1` содержит перечисленные поля на каждом выходе `do_POST` first_event_ms=null до валидного session SSE исполнения после prompt; local ready не подставлять; transport_history различает _ServeHealth degradation.",
       "evidence": "F-32, F-30",
       "verification_ids": [
         "VER-005"
@@ -739,6 +739,25 @@
       "kind": "code",
       "ref": "bridges/opencode-zen-bridge/server.py:_UpstreamBreaker.allow (1415-1428), _SlotBulkhead.__init__ (1265-1270)",
       "claim": "Baseline HALF_OPEN probe can be re-admitted after reset_s while first is active; default slots2/configured waiters12 exceed canonical2M unless effective clamp. Dedicated oracles freeze intended single-probe/effective bound without altering deployed6/12."
+    },
+    {
+      "id": "EVD-062",
+      "kind": "code",
+      "ref": "~/.opencode/bin/opencode (v2.1.2), embedded JS byte offsets113098820,114613538,114616189,114617971,114628971,114631174,114634000..114636000,114980796,114994633,114622692,114978382,115017692,114596000..114596700",
+      "claim": "Read-only source extraction: version2.1.2; Model.Ref {providerID,id,variant}; Permission.Ruleset array{action,resource,effect}, wire permission.asked+reply decision=reject; delta data.delta/sessionID/assistantMessageID/ordinal; TokenUsage.Info {input,output,reasoning,cache:{read,write}}; tool input.started/called/failed; session prompt delivery steer|queue,resume. binary SHA256 b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c. Synthetic frozen examples use source schemas, не live tool execution. Дополнительно source: active sessions response data — object record, не array; Session.StructuredError optional numeric status (100..599); /api/info gives app version+pid; OpenAPI.info.version=0.0.1, отдельная от CLI2.1.2.",
+      "collected_at": "2026-10-26"
+    },
+    {
+      "id": "EVD-063",
+      "kind": "document",
+      "ref": "/tmp/cel-runs/zen-realtime-reasoning-20261025/sa-poc/serve_sse.py + poc_serve.log; F-19/F-22/F-23",
+      "claim": "Существующий analyst PoC использует lightweight GET /api/session/active; create model {providerID,id,variant}, location.directory; prompt files[] delivery=steer; data.id response. Сохранённый failed event {id,created,type,data:{sessionID,error:{type:provider.free-limit,message}}}. В cycle2 процесс opencode не запускался, provider не вызывался."
+    },
+    {
+      "id": "EVD-064",
+      "kind": "document",
+      "ref": "handoff/panel-rework-brief-arch-a1.json + текущий Brief Architect cycle2 fix-from-panel",
+      "claim": "14 обязательных RW и7 FU; exact explicit choices для default true, headers barrier, permission selector,MiB/typing; role write allowlist только3 JSON. Исходные расхождения R1 перечислены в panel_resolution_choices, не выданы за единогласное одобрение изменений."
     }
   ],
   "risk_triggers": [
@@ -751,7 +770,7 @@
       "id": "ASM-001",
       "class": "continuable",
       "source_open_ids": "OPEN-06/08",
-      "statement": "Per-spawn env ротация и child192MiB design estimates; физический egress/SQLite6parallel проверяет H3.",
+      "statement": "Per-spawn proxy env rotation доказуема AC-018, Zen egress за georouter не определяется child HTTP_PROXY (F-15/F-27). child192MiB — design estimate; временный per-spawn XDG_DATA_HOME устраняет совместное открытие общей DB; фактический RSS/locks проверяет обязательный H3.",
       "status": "ASSUMED",
       "evidence_ids": [
         "EVD-015",
@@ -796,7 +815,7 @@
       "id": "ASM-005",
       "class": "continuable",
       "source_open_ids": "OPEN-07",
-      "statement": "Deny-all capability и equivalent ask-auto-reject должны пройти fake permission assertions; реальное no-file mutation доказывает H6, ещё не выполнено.",
+      "statement": "Default ask_reject и optional env=deny проверяются FakeServe; живую совместимость обеих safe policies с Zen и no-file mutation доказывает H6. Автопереключения политик нет; отсутствие safe endpoint или401/403 fail-closed.",
       "status": "ASSUMED",
       "evidence_ids": [
         "EVD-022",
@@ -832,7 +851,7 @@
     "RC-2: многоэтапные deadline и очистка вместо 780–856 с тишины",
     "RC-3: DSH видимость по непустому reasoning_content и завершённому абзацу",
     "REQ-002/003: стабильный OpenAI контракт и 17 legacy test modules",
-    "REQ-012/013/015: запрет built-ins, per-spawn proxy rotation и секреты"
+    "REQ-012/013/015: запрет built-ins, per-spawn proxy env rotation (не доказанная Zen IP ротация), безопасные secrets/loopback ownership"
   ],
   "verification_surface": [
     {
@@ -853,7 +872,7 @@
       "kind": "command",
       "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/",
       "expected": "exit 0; 0 failed во всех существующих 17 модулях + dedicated suite; 3 baseline tests исправлены, production cap=3",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
       "owner": "verifier"
     },
     {
@@ -867,7 +886,7 @@
       "kind": "command",
       "command": "cd bridges/opencode-zen-bridge && python3 -m unittest discover -s tests -p \"test_*.py\"",
       "expected": "exit 0; 0 failures/errors, запуск из bridge cwd (не из repo root), все новые tests используют unittest.TestCase или stdlib-compatible helper",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
       "owner": "verifier"
     },
     {
@@ -879,7 +898,7 @@
       "kind": "command",
       "command": "PYTHONPATH=. uvx pytest -q -p no:cacheprovider tests/",
       "expected": "exit 0; root cross-bridge regression без живых owner ресурсов; environment-specific skips разрешены только унаследованные",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
       "owner": "verifier"
     },
     {
@@ -890,10 +909,15 @@
         "REQ-017"
       ],
       "kind": "command",
-      "command": "python3 - <<'VER004'\nimport collections, json, subprocess\ns=\"bridges/opencode-zen-bridge/server.py\"\nt=\"bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py\"\nr=subprocess.run([\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"check\",\"--no-cache\",\"--output-format=json\",s,t],capture_output=True,text=True)\nassert r.returncode in (0,1), r.stderr\nrd=json.loads(r.stdout)\nfrom pathlib import Path\nassert all(\"import zen_catalog\" in Path(s).read_text().splitlines()[x[\"location\"][\"row\"]-1] for x in rd), rd\nassert all(x[\"code\"]==\"E402\" and x[\"filename\"].endswith(\"/\"+s) and x[\"message\"]==\"Module level import not at top of file\" for x in rd) and len(rd)<=1, rd\nb=subprocess.run([\"uvx\",\"--from\",\"basedpyright==1.40.2\",\"basedpyright\",\"--outputjson\",s],capture_output=True,text=True)\nassert b.returncode in (0,1), b.stderr\nbd=json.loads(b.stdout); ds=bd[\"generalDiagnostics\"]\nallowed={\"reportImplicitRelativeImport\":\"zen_catalog\", \"reportConstantRedefinition\":\"CATALOG_SOURCE\"}\nerrs=[x for x in ds if x[\"severity\"]==\"error\"]\nassert all(x.get(\"rule\") in allowed and allowed[x[\"rule\"]] in x[\"message\"] for x in errs), errs\nassert all(n<=1 for n in collections.Counter(x[\"rule\"] for x in errs).values()), errs\nlimits={\"reportExplicitAny\":125,\"reportAny\":125,\"reportUnusedCallResult\":39,\"reportUnknownMemberType\":70,\"reportUnknownVariableType\":48,\"reportUnknownArgumentType\":35,\"reportUnusedFunction\":2,\"reportImplicitStringConcatenation\":27,\"reportUnannotatedClassAttribute\":81,\"reportUnusedParameter\":3,\"reportUnnecessaryIsInstance\":3,\"reportUnknownParameterType\":2,\"reportMissingParameterType\":2,\"reportUnreachable\":1,\"reportImplicitOverride\":1}\ncounts=collections.Counter(x.get(\"rule\",\"\") for x in ds if x[\"severity\"]==\"warning\")\nassert all(n<=limits.get(k,0) for k,n in counts.items()), counts\nprint(\"PASS baseline-aware VER-004; ruff inherited<=1 E402; pyright inherited<=2 errors; warnings within frozen per-rule budgets\",dict(counts))\nVER004",
-      "expected": "exit 0 baseline overlay; новые lint/type errors запрещены. Это budget gate для существующего typed debt, НЕ заявление о полном чистом basedpyright. Legacy E402 разрешён только на zen_catalog import; 2 pyright error sites строго только указанные; warning rule budgets не растут.",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
-      "owner": "verifier"
+      "command": "python3 - <<'VER004'\nimport collections, json, subprocess\nfrom pathlib import Path\nfiles = ['bridges/opencode-zen-bridge/server.py','bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py','bridges/opencode-zen-bridge/tests/test_step_interruption.py']\nassert all(Path(f).is_file() for f in files), files\nfor args in ([\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"format\",\"--check\",\"--no-cache\",*files], [\"uvx\",\"--from\",\"ruff==0.17.2\",\"ruff\",\"check\",\"--no-cache\",*files]):\n    subprocess.run(args, check=True)\nb = subprocess.run([\"uvx\",\"--from\",\"basedpyright==1.40.2\",\"basedpyright\",\"--outputjson\",*files], capture_output=True, text=True)\nassert b.returncode in (0,1), b.stderr\nreport = json.loads(b.stdout)\nds = report['generalDiagnostics']\nerrors = [d for d in ds if d['severity'] == 'error']\nassert report['summary']['errorCount'] == 0 and not errors, errors\nlimits = {'reportExplicitAny': 125, 'reportAny': 125, 'reportUnusedCallResult': 39, 'reportUnknownMemberType': 70, 'reportUnknownVariableType': 48, 'reportUnknownArgumentType': 35, 'reportUnusedFunction': 2, 'reportImplicitStringConcatenation': 27, 'reportUnannotatedClassAttribute': 81, 'reportUnusedParameter': 3, 'reportUnnecessaryIsInstance': 3, 'reportUnknownParameterType': 2, 'reportMissingParameterType': 2, 'reportUnreachable': 1, 'reportImplicitOverride': 1}\nserver = Path(files[0]).resolve()\nserver_warnings = [d for d in ds if d['severity']=='warning' and Path(d['file']).resolve()==server]\ncounts = collections.Counter(d.get('rule','') for d in server_warnings)\nassert all(n <= limits.get(rule,0) for rule,n in counts.items()), dict(counts)\n# Both Any rules explicitly retain the frozen server.py ceiling even if absent in output.\nassert counts['reportAny'] <= 125 and counts['reportExplicitAny'] <= 125, dict(counts)\nprint('PASS VER-004: ruff format/check all 3 files, basedpyright 0 errors all 3, server frozen warning budgets',dict(counts))\nVER004",
+      "expected": "exit0; ruff format --check и ruff check на всех3 targetfiles без allowance; basedpyright severity==error ровно0 на всех3. server.py reportAny<=125/reportExplicitAny<=125 и остальные frozen rule warning budgets не растут. Прежние E402/2 type errors EVD052/053 не разрешены новым gate; Coder исправляет в allowlist без type-ignore/disable/изменения конфигов. Stage2 команду не запускает: новый testfile ещё не существует.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "owner": "verifier",
+      "baseline_transition": {
+        "old": "v1 VER-004 разрешал1E402 и2errors server.py и пропускал test_step_interruption.py",
+        "new": "0 lint/format failures,0type errors на каждом из3files; server frozen warning budgets unchanged",
+        "owner": "Stage3 Coder устраняет pre-existing error sites в server.py; Verifier независимо проверяет. Новые Any запрещены, подавлять диагностику ради PASS нельзя."
+      }
     },
     {
       "id": "VER-005",
@@ -920,8 +944,8 @@
       ],
       "kind": "command",
       "command": "cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/test_realtime_reasoning.py",
-      "expected": "exit 0; полный FakeServe v2 SSE, timing до конца upstream, grace/status, 3 watchdog, cancellation/PGID, fallback, pure reasoning, tools, 46 envelope fields + 21 stop-code/lifecycle invariants",
-      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для baseline overlay. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
+      "expected": "exit0; exact frozen-v2.1.2 FakeServe fixture digest+negative mutations, delivery/concurrent reject, ask_reject/deny и _run_env hash, listener takeover zero leakage, budgets51.6, separate first_event20/readiness3, file kill-switch, ServeHealth3/TTL120 independent breaker, synthetic leading LF provenance, XDG cleanup, all prior tools/timing/lifecycle/resilience assertions. Implementation NOT_RUN Stage2.",
+      "environment": "Чистый clone/worktree, cwd=repo_root (кроме явного cd), Python>=3.11, uvx с pytest; ruff=0.17.2/basedpyright=1.40.2 для frozen strict VER-004. Изолированный verifier runner не монтирует home владельца/его ~/.dsh; live-only optional root tests skip. Без изменения HOME в пользовательской сессии, без обращений к production, сети Zen и без rollout. Temp fake CLI/HTTP/workdir создаёт runner в своём sandbox.",
       "owner": "verifier"
     }
   ],
@@ -931,9 +955,9 @@
       "status": "APPROVED",
       "kind": "two-way",
       "question": "Как получить настоящие reasoning/text delta и сохранить обратимый legacy-путь?",
-      "choice": "Option C с A1 primary: один короткоживущий serve v2 на попытку, HTTP+SSE, run fallback только до отправки prompt; единый canonical event source для stream=True и stream=False.",
+      "choice": "Option C/A1: один ephemeral serve v2.1.2 на попытку; canonical source для SSE/JSON. В auto run fallback только до HTTP-заголовков ответа POST /prompt И до первого валидного события исполнения текущей сессии; после барьера никакого silent run fallback.",
       "alternatives": [
-        "A2: общий daemon — дешевле холодного старта, но единый env/IP и failure domain, риск лимита F-15/OPEN-06.",
+        "A2: общий daemon экономит холодный старт, но объединяет failure domain и child env; самостоятельная ротация egress внутри georouter не доказана ни для A1, ни для A2 (F-15/F-27).",
         "B: прямой HTTP Zen — меньше ресурсов, но 429 F-24/F-25 и нет подтверждённого client context; не выбирается без PoC.",
         "L: только run watchdog/status — минимален, но не устраняет RC-1."
       ],
@@ -942,14 +966,16 @@
         "REQ-002",
         "REQ-003",
         "REQ-012",
-        "REQ-013",
+        "REQ-013 / AC-018: per-spawn _next_standalone_proxy/env rotation; loopback georouter bypasses child HTTP_PROXY via NO_PROXY, не гарантия смены Zen egress IP",
         "REQ-014",
         "F-19/F-20: 109 ms server start, 127/114 ms delta medians"
       ],
       "consequences": [
         "Дополнительные SSE/control sockets и lifecycle; предел активных детей не увеличивается.",
         "run-откат теряет realtime; это видимая деградация, не доказательство REQ-001.",
-        "Откат флага/режима без миграций; публичная форма ответов неизменна."
+        "Откат флага/режима без миграций; публичная форма ответов неизменна.",
+        "Новый процесс получает временный XDG_DATA_HOME: история/SQLite изолированы на попытку и удаляются в finally; общий opencode.db не открываем намеренно.",
+        "Default=true разрешён текущим rework-brief; production sync лишь после изолированного H3. Файл disable-serve удерживает боевой run до приёмки."
       ],
       "approval_required": false,
       "evidence_ids": [
@@ -964,7 +990,10 @@
         "EVD-025",
         "EVD-040",
         "EVD-050",
-        "EVD-051"
+        "EVD-051",
+        "EVD-062",
+        "EVD-063",
+        "EVD-064"
       ],
       "confirmation": {
         "kind": "test",
@@ -978,8 +1007,8 @@
       "details": {
         "configuration": {
           "OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED": {
-            "default": false,
-            "purpose": "без явного включения выполняется только run; первые инструкции optional serve-path проверяют флаг"
+            "default": true,
+            "purpose": "В auto нативный Mach-O opencode сразу использует serve после разрешённой синхронизации server.py; start.sh неизменен. Явные 0/false выключают optional serve ветвь первой инструкцией."
           },
           "OPENCODE_ZEN_BRIDGE_TRANSPORT": {
             "values": [
@@ -988,28 +1017,444 @@
               "run"
             ],
             "default": "auto",
-            "precedence": "TRANSPORT=run или REALTIME_SERVE_ENABLED=false -> run. true+auto -> безопасный eligibility-check, потом serve или run. true+serve -> force serve, ошибки capability/readiness явные без silent run fallback. Неизвестное значение -> ошибка конфигурации до bind."
+            "precedence": "REALTIME_SERVE_ENABLED=0/false или TRANSPORT=run -> run до stat/probe/allocations; затем существующий disable-file -> run; затем auto ServeHealth + shebang eligibility; иначе serve. Force serve обходит только shebang/health auto routing для FakeServe и диагностики, но не disable-file, выключенный флаг или security. Force serve errors явные, без silent fallback. Invalid value -> config error."
           },
-          "feature_flag_context": "Локальный stdlib-мост без gc_pytools/dynamic_config/GigaRC, как зафиксировано в эталоне. Не добавлять GigaRC/dependency/env propagation в другие системы; текущий бриф явно разрешает transport/env kill-switch. Новая ветвь default=false."
+          "OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY": {
+            "values": [
+              "ask_reject",
+              "deny"
+            ],
+            "default": "ask_reject",
+            "purpose": "Одна policy на attempt; ask_reject сохраняет tool schemas, немедленно отвечает decision=reject. deny выбирается env до запуска для отдельного H6, без пересборки. Нет автоматического deny↔ask_reject переключения ни до, ни после prompt; unsupported policy/capability -> fail-closed."
+          },
+          "OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE": {
+            "default": "~/.dsh/bridges/opencode-zen-bridge/disable-serve",
+            "purpose": "Путь expanduser/resolve при конфигурации, без создания каталога. На входе нового запроса O(1) os.path.exists(); файл есть -> run без serve UUID/password/queue/thread/Popen/probes. Ошибка проверки пути -> безопасно run с redacted reason. Создание/удаление файла меняет выбор следующего запроса без рестарта; active leases завершаются или явно отменяются, без дублирования текущего prompt."
+          },
+          "SERVE_READY_TIMEOUT_S": 3.0,
+          "SERVE_SESSION_SETUP_TIMEOUT_S": 2.0,
+          "feature_flag_context": "Текущий explicit cycle-2 brief RW-009 разрешает default=true в локальном stdlib-мосте (прецеденты STEP_RECOVERY=1 и F-40), вместо общего GigaRC default=false. Новых dependencies/GigaRC/start.sh/env propagation не добавлять. Disable-file обеспечивает live kill-switch без рестарта; H3 обязателен до production rollout."
         },
-        "auto_fake_compatibility": "В auto НЕ запускать --help/--version/serve ради probe на произвольном OPENCODE_BIN. После O(1) флага прочитать первые байты resolved executable и stat: shebang/текстовый launcher -> run без subprocess-пробы. Это покрывает все текущие fake scripts (включая basename opencode). Иначе bind/serve v2 handshake под readiness ceiling. Eligibility кэшируется по resolved path+mtime_ns+size, без смены глобальной модели/тестовых env. Force serve намеренно обходит shebang-фильтр для FakeServe; fake tests задают flag=true, mode=serve. Никакого распознавания по FAKE_OC_MODE/имени теста. Защита test_step counter: fallback не должен запускать fake CLI лишний раз. При flag=false любые legacy test-фикстуры остаются на run с прежним counter.",
-        "spawn": "Перед КАЖДЫМ реальным Popen: общий _RequestAttempts/slot, spawn_limiter, _StartupGate, свежий _run_env(model_id) и _next_standalone_proxy. serve argv [launcher, serve, --hostname, 127.0.0.1, --port, ephemeral]; stdin=DEVNULL (EOF немедленно), start_new_session=True. Не передавать prompt argv/stdin serve. OS выбирает loopback port; если API не даёт port=0 адрес, reserve-bind(0), release, spawn с ограниченным retry race; не считать чужой listener своим.",
-        "startup": "SERVE_READY_TIMEOUT_S=0.50: bounded local connect/openapi handshake, общий monotonic deadline; control socket slices <=0.25 s. Разрешён только authenticated v2 OpenAPI/event/session shape. Child EOF/unsupported serve/нет HTTP listener/несовместимый protocol -> ServeUnavailable. stdin=DEVNULL предотвращает stdin hang даже для force serve с legacy fake; exit/EOF проверяются сразу, без 5 s ожидания. stdout/stderr дренируются ограниченно и маскируются до лога. Пароль криптографически случайный per spawn, OPENCODE_SERVER_PASSWORD добавляется ПОСЛЕ whitelist, Basic opencode:<password>, никогда не в argv/URL/логе. Loopback http.client connection идёт напрямую, без env proxy и redirects.",
-        "fallback_barrier": "Auto fallback разрешён только если prompt POST ещё НЕ НАЧАТ, нет model output/tool action, нет client_gone и security/auth failure. До fallback полностью interrupt/delete (если session создана), close socket, killpg/reap предыдущий serve. ServeUnavailable capability не считается ошибкой модели и не увеличивает breaker; фактический serve Popen всё равно расходует MAX_TOTAL_SPAWNS и токен spawn. Следующий run Popen требует общий attempts.allow_retry, _RetryBudget и Full Jitter, не может дать 4-й spawn. При исчезновении клиента fallback запрещён. HTTP 401/403, неожиданный auth/permission response -> fail-closed, никакого ослабления policy через run. Начиная с попытки отправки prompt (даже timeout с неизвестной доставкой) silent fallback запрещён; штатный transient retry возможен только в общей state machine и после cleanup, с явным retry-status.",
-        "session_flow": "Сначала authenticate/readiness и deny-policy, затем POST /api/session(model с тем же provider/model#variant согласно v2 schema, location=текущий workdir, permissions); открыть и подтвердить подписку GET /api/event ДО POST /api/session/{id}/prompt с полным text. Отфильтровывать события только current session/execution; не выдавать чужую историю/старые события. Не вызывать generate или prompt повторно при timeout. Terminal success/failed — независимый сигнал полноты; EOF без terminal -> transport failure. На step.ended с DSH tool call прекратить дальнейшие шаги, interrupt/delete и cleanup.",
-        "tool_policy": "Основная безопасная конфигурация — scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"deny\"} плюс deny-all session permissions; merge сохраняет provider/options, не пишет общий конфиг. F-50: deny может убрать tool schemas и вызвать Zen 403. Эквивалентная разрешённая изоляция для такого несовместимого клиента: permission=ask, session permission request -> немедленный API reply reject (никогда allow), пока prompt не начат подтверждены permission endpoints. При отсутствии безопасной deny/ask-auto-reject capability — fail-closed, не выполнять инструменты. Не переключать политику на лету после provider 403. Выбор совместимой policy проверяется FakeServe, а исполнение реально запрещено H6 перед rollout. События session.tool.* нормализуются в native mapping даже если denied: native/unmapped handling как legacy.",
+        "auto_fake_compatibility": "Auto: до любых serve allocations выполнить env/run/disable-file/health guards; затем cached stat+first bytes executable. Shebang #! или текстовый launcher -> run сразу, без --help/--version/serve subprocess. Это сохраняет 378 fake-CLI baseline tests при новом default=true, включая basename opencode; не проверять имя теста/FAKE_OC_MODE. Native Mach-O -> owned serve readiness. Eligibility/protocol metadata cache key=(resolved executable path,mtime_ns,size); смена ключа инвалидирует старую capability и transport health. Force serve обходит shebang для FakeServe, stdin=DEVNULL предотвращает stdin.read hang. false/run/disable-file spies: zero serve UUID/password/threads/probes/extra Popen; stat file разрешён только enabled selector.",
+        "spawn": "На каждую реальную попытку общий _RequestAttempts/slot, единый admission deadline<=5.0s для _SpawnRateLimiter+_StartupGate (не два ожидания по5s), свежий _serve_env(model_id) поверх одного неизменного _run_env(model_id), новая per-spawn _next_standalone_proxy запись. Parent socket.bind((127.0.0.1,0)), getsockname()[1]; держать резерв до непосредственно Popen, затем close reserve и Popen([OPENCODE_BIN,serve,--hostname,127.0.0.1,--port,str(port)],stdin=DEVNULL,start_new_session=True,close_fds=True), сохранить child_pgid. Prompt/Basic password не передавать argv/stdin. До первого Authorization или prompt доказать owner listener по listener_ownership; при port race cleanup + новый порт только в оставшемся ready deadline, каждый новый Popen расходует общий cap3 и spawn token. Ни одного бесплатного spawn при EADDRINUSE.",
+        "startup": "SERVE_READY_TIMEOUT_S=3.0s (ready_budget_s=3.0): после owner proof лёгкий authenticated GET /api/session/active, HTTP200 + $.data object map of active sessions (empty={}); не качать 281KB /openapi.json на каждом spawn. Control I/O slices<=.25s, всего<=3 readiness TCP probes, remaining request deadline/cancel всегда проверяются. Child EOF/no listener/incompatible protocol -> ServeUnavailable. Пароль secrets per spawn в OPENCODE_SERVER_PASSWORD ПОСЛЕ whitelist, Basic opencode:<password>, никогда в argv/URL/log. stdout/stderr bounded drain+redact. HTTP на loopback напрямую без proxy/redirects. Readiness не устанавливает first_event_ms и не сбрасывает first_event/token часы.",
+        "fallback_barrier": "State machine: ADMISSION -> SPAWN/OWNER/READY -> CREATE/SUBSCRIBE -> PROMPT_SENDING -> DELIVERED -> TERMINAL -> CLEANUP. Auto ServeUnavailable на старте/create/subscribe или до получения HTTP response headers POST /api/session/{id}/prompt допускает один budgeted run fallback, ТОЛЬКО если не было валидного события исполнения созданной session после начала отправки prompt, нет model/tool output, auth/security failure, cancel или deadline. Перед run полностью close/join/killpg/reap старую attempt, удалить temp data; новый Popen требует тот же retry token/Full Jitter/attempt ceiling<=3. С первого response header POST /prompt (любой status) ИЛИ первого session execution event после prompt delivery лачится DELIVERED=true; silent fallback и переключение на run для текущего запроса запрещены, включая отсутствие response body и headers-pending+SSE-started. Prompt POST исполняется daemon worker параллельно SSE; до header/события ожидание ограничено остатком first_event20s/first_token60s и total deadline. Даже до headers неизвестная доставка может дать повторную генерацию: допустимость этой границы явно задана текущим brief RW-001, это НЕ exactly-once; старый PGID должен быть убран до fallback, built-ins никогда allow. После barrier watchdog может выполнить только явный общий retry того же транспорта с retry-status/cleanup/cap, не скрытый run fallback. HTTP401/403/auth/permission/capability-security denial -> fail-closed без fallback/auto policy switching на любой фазе.",
+        "session_flow": "После listener proof/readiness и подтверждения safe permission capability POST /api/session по session_wire.create; затем GET /api/event с HTTP200 text/event-stream и reader armed ДО отправки первого байта тела prompt. На create + subscribe один SERVE_SESSION_SETUP_TIMEOUT_S=2.0s, не включая model generation или ожидание POST /prompt response. Передать полный prompt в JSON body через единственный daemon delivery worker, одновременно читать SSE в owned reader; supervisor/SSE writer не ждут блокирующий POST и остаются cancel-aware. Один POST /prompt с delivery=steer,resume=true; transport HTTP headers/ошибки передаются supervisor как control events. First-event/token часы якорятся на prompt_send_start, не на HTTP ready/создание сессии. Filter data.sessionID==created_sid; реальные v2 события не содержат executionID, поэтому использовать own per-attempt session + prompt-send generation latch, event id дедуп и assistantMessageID step key, не выдумывать executionID. server.connected/session.created/global updates/pre-prompt events не считаются first execution. Terminal success/failed независим от text end; EOF без terminal -> protocol failure. step.ended с готовым DSH tool call -> остановить дальнейшее исполнение/cleanup.",
+        "tool_policy": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
         "event_contract": {
-          "shape": "Iterator[tuple[str, dict]]; единая семантика событий в Handler._stream_sse и Run._execute_once (через _serve_json). Legacy parse_opencode_event сохранён, normalize boundary обеспечивает raw part для tool_use; forbidden: копировать все retry loops в новый transport.",
-          "session.reasoning.delta": "(\"reasoning\", {reasoning_content: delta}); только delta bytes, ended не повторяет полный текст; reasoningEncryptedContent сохраняется reasoning_details через существующий mapping.",
-          "session.text.delta": "(\"text\", {content: delta}) -> тот же ToolCallParser.feed или emit_content.",
-          "session.step.ended": "(\"step_finish\", tokens с input/output/cached/reasoning), ровно один учёт по step id, не удваивать usage на execution terminal.",
-          "session.tool.*": "(\"tool_use\", {part:{tool, state:{input,status}}, call_id}); адаптер legacy тоже вкладывает тот же canonical part; оба потребителя берут part из normalized payload. Стабильный call_id не допускает повторного DSH вызова на started/updated/ended одного инструмента. Допустим raw-event envelope внутри adapter для старых потребителей, но неизвестный tool type не игнорируется.",
-          "session.step.failed / session.execution.failed": "(\"error\", {statusCode,message}) через существующий classifier; не удваивать одну failure cause.",
+          "shape": "Iterator canonical tuples для обоих потребителей; object/TypedDict validation. Public OpenAI unchanged; legacy parser остаётся для run. Полные wire fixtures ниже frozen v2.1.2, metadata id/created synthetic, field paths подтверждены EVD-062/EVD-063.",
+          "session.reasoning.delta": "$.data.delta -> (reasoning,{reasoning_content:delta}); delta bytes only, ended не повторяет full text. Если native encrypted metadata есть в started/ended, сохранять существующим reasoning_details mapping без повторной text delta.",
+          "session.text.delta": "$.data.delta -> (text,{content:delta}) -> тот же ToolCallParser.feed/emit_content.",
+          "session.step.ended": "$.data.tokens input/output/reasoning + $.data.tokens.cache.read -> canonical input/output/reasoning/cached; один учёт по $.data.assistantMessageID, terminal не удваивает usage.",
+          "session.tool.*": "Actual input.started(name), input.delta, input.ended(text), called(input,executed), progress(metadata), success/failed. Correlate data.sessionID+assistantMessageID+id; accumulate tool name/input, normalize tool_use part{tool,state{input,status}}+call_id. permission.asked отправляет decision=reject немедленно по отдельному control lane. Никакого встроенного allow или выполнения bridge-side.",
+          "session.step.failed / session.execution.failed": "$.data.error {type,message,status?,response?,retryAfterMs?} ->canonical error{statusCode,message}: statusCode=$.data.error.status если integer100..599; иначе explicit known type mapping provider.free-limit429/auth401/permission denial403, unknown null. Terminal independent, one cause not counted twice.",
           "session.execution.succeeded": "terminal success metadata, не text/reasoning; гарантированно дренировать уже полученный step.ended перед финальным usage.",
-          "other": "started/connected/lifecycle -> транспортные служебные события для first-event, не model token; unknown control events не исполняют actions.",
-          "payload_validation": "Использовать v2 schema и фактические F-19/F-22 fixtures. Не угадывать field aliases по строке event name. SSE assembler поддерживает UTF-8 через incremental decoder, CRLF, multi-line data, comments и fragment boundaries; delta/ended сверяются на tool/reasoning/text fixtures. Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test до runtime enabling."
+          "other": "first_event latch только валидный execution/step/reasoning started текущей session после prompt; валидные current-session model delta также доказывают начало исполнения. server.connected, HTTPready, session.created, чужие session/control/comments/status не latch и не model token.",
+          "payload_validation": "Проверять exact field paths/types и mandatory sessionID до emit. Текущая schema shape mismatch -> invalid_serve_event (не пустая полезная delta), отдельный ServeHealth; permission capability mismatch ->security fail-closed. Incremental UTF8/CRLF/multiline SSE/comments/fragment boundaries, byte budgets как прежде. Никакого Coder-discovered protocol или aliases, которых нет в frozen source. Coder и FakeServe используют frozen expected независимо; мутации delta path/token/permission должны краснить тест даже если adapter и mock согласованно ошибочны.",
+          "frozen_v2_1_2_fixtures": {
+            "session.reasoning.delta": {
+              "wire": {
+                "id": "evt_fixture_1",
+                "created": 1792957431001,
+                "type": "session.reasoning.delta",
+                "data": {
+                  "sessionID": "ses_fixture_1",
+                  "assistantMessageID": "msg_fixture_1",
+                  "ordinal": 0,
+                  "delta": "Мысль без LF"
+                }
+              },
+              "field_paths": {
+                "session_id": "$.data.sessionID",
+                "step_key": "$.data.assistantMessageID",
+                "ordinal": "$.data.ordinal",
+                "delta": "$.data.delta"
+              },
+              "canonical": {
+                "etype": "reasoning",
+                "payload": {
+                  "reasoning_content": "Мысль без LF"
+                }
+              }
+            },
+            "session.text.delta": {
+              "wire": {
+                "id": "evt_fixture_2",
+                "created": 1792957431002,
+                "type": "session.text.delta",
+                "data": {
+                  "sessionID": "ses_fixture_1",
+                  "assistantMessageID": "msg_fixture_1",
+                  "ordinal": 1,
+                  "delta": "Ответ\n"
+                }
+              },
+              "field_paths": {
+                "delta": "$.data.delta",
+                "session_id": "$.data.sessionID"
+              },
+              "canonical": {
+                "etype": "text",
+                "payload": {
+                  "content": "Ответ\n"
+                }
+              }
+            },
+            "session.step.ended": {
+              "wire": {
+                "id": "evt_fixture_3",
+                "created": 1792957431003,
+                "type": "session.step.ended",
+                "data": {
+                  "sessionID": "ses_fixture_1",
+                  "assistantMessageID": "msg_fixture_1",
+                  "finish": "stop",
+                  "cost": 0,
+                  "tokens": {
+                    "input": 17,
+                    "output": 9,
+                    "reasoning": 4,
+                    "cache": {
+                      "read": 3,
+                      "write": 2
+                    }
+                  }
+                }
+              },
+              "field_paths": {
+                "tokens": "$.data.tokens",
+                "dedup_step_key": "$.data.assistantMessageID",
+                "cached": "$.data.tokens.cache.read"
+              },
+              "canonical": {
+                "etype": "step_finish",
+                "payload": {
+                  "input": 17,
+                  "output": 9,
+                  "cached": 3,
+                  "reasoning": 4
+                }
+              },
+              "note": "Реальный v2 wire cache:{read,write}; cached=cache.read в legacy canonical tuple. cache.write не суммировать с cached read. Canonical input/output/reasoning копировать по существующей семантике; считать раз по assistantMessageID. Отсутствие required tokens/cache/read — invalid_serve_event, не нули."
+            },
+            "session.permission.requested / session.tool.*": {
+              "wire_event_name": "permission.asked",
+              "logical_family": "session.permission.requested",
+              "wire": {
+                "id": "evt_fixture_4",
+                "created": 1792957431004,
+                "type": "permission.asked",
+                "data": {
+                  "id": "per_fixture_1",
+                  "sessionID": "ses_fixture_1",
+                  "action": "bash",
+                  "resources": [
+                    "*"
+                  ],
+                  "source": {
+                    "type": "tool",
+                    "messageID": "msg_fixture_1",
+                    "id": "call_fixture_1"
+                  }
+                }
+              },
+              "field_paths": {
+                "session_id": "$.data.sessionID",
+                "request_id": "$.data.id",
+                "tool_call_id": "$.data.source.id",
+                "action": "$.data.action",
+                "resources": "$.data.resources"
+              },
+              "reply": {
+                "method": "POST",
+                "path": "/api/session/ses_fixture_1/permission/per_fixture_1/reply",
+                "body": {
+                  "decision": "reject"
+                },
+                "success_status": 204
+              },
+              "tool_lifecycle": [
+                {
+                  "id": "evt_fixture_5",
+                  "created": 1792957431005,
+                  "type": "session.tool.input.started",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "assistantMessageID": "msg_fixture_1",
+                    "id": "call_fixture_1",
+                    "name": "bash"
+                  }
+                },
+                {
+                  "id": "evt_fixture_6",
+                  "created": 1792957431006,
+                  "type": "session.tool.input.delta",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "assistantMessageID": "msg_fixture_1",
+                    "id": "call_fixture_1",
+                    "delta": "{\"command\":\"printf probe\"}"
+                  }
+                },
+                {
+                  "id": "evt_fixture_7",
+                  "created": 1792957431007,
+                  "type": "session.tool.input.ended",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "assistantMessageID": "msg_fixture_1",
+                    "id": "call_fixture_1",
+                    "text": "{\"command\":\"printf probe\"}"
+                  }
+                },
+                {
+                  "id": "evt_fixture_8",
+                  "created": 1792957431008,
+                  "type": "session.tool.called",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "assistantMessageID": "msg_fixture_1",
+                    "id": "call_fixture_1",
+                    "input": {
+                      "command": "printf probe"
+                    },
+                    "executed": false
+                  }
+                },
+                {
+                  "id": "evt_fixture_9",
+                  "created": 1792957431009,
+                  "type": "session.tool.failed",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "assistantMessageID": "msg_fixture_1",
+                    "id": "call_fixture_1",
+                    "error": {
+                      "type": "permission.rejected",
+                      "message": "Rejected by bridge policy"
+                    },
+                    "executed": false
+                  }
+                },
+                {
+                  "id": "evt_fixture_10",
+                  "created": 1792957431010,
+                  "type": "permission.replied",
+                  "data": {
+                    "sessionID": "ses_fixture_1",
+                    "requestID": "per_fixture_1",
+                    "reply": "reject"
+                  }
+                }
+              ],
+              "canonical": {
+                "etype": "tool_use",
+                "payload": {
+                  "part": {
+                    "tool": "bash",
+                    "state": {
+                      "input": {
+                        "command": "printf probe"
+                      },
+                      "status": "error"
+                    }
+                  },
+                  "call_id": "call_fixture_1"
+                }
+              },
+              "note": "Family label из brief — не имя wire event. В бинарнике нет session.permission.requested или session.tool.started: actual names permission.asked и session.tool.input.started/called/progress/success/failed. Имя tool копить из input.started; canonical payload emit после complete input/called, не исполнять по частичному JSON. Lifecycle updates не создают повторный DSH tool_call; own denied event не является model progress. Указанный failed message — синтетическое fixture значение типа error, не заявление о захваченном live отказе."
+            },
+            "session.execution.failed": {
+              "wire": {
+                "id": "evt_fixture_11",
+                "created": 1792957431011,
+                "type": "session.execution.failed",
+                "data": {
+                  "sessionID": "ses_fixture_1",
+                  "error": {
+                    "type": "provider.free-limit",
+                    "message": "Free usage limit reached"
+                  }
+                }
+              },
+              "field_paths": {
+                "error": "$.data.error",
+                "message": "$.data.error.message",
+                "error_type": "$.data.error.type",
+                "statusCode": "$.data.error.status if present integer100..599, else explicit type mapping"
+              },
+              "canonical": {
+                "etype": "error",
+                "payload": {
+                  "statusCode": 429,
+                  "message": "Free usage limit reached"
+                }
+              },
+              "note": "provider.free-limit ->429; provider.auth/permission denial ->fatal401/403; неизвестный type сохраняется как явная ошибка с statusCode=null, не выдумывать retryability. step.failed + execution.failed одной cause дедуп без потери terminal. Numeric wire key status, not statusCode/data.statusCode; source Session.StructuredError. Missing numeric status allowed as in captured free-limit event."
+            }
+          },
+          "fixture_provenance": {
+            "source": "EVD-062: read-only embedded schemas/API v2.1.2; EVD-063: analyst PoC script+failure envelope",
+            "binary_sha256": "b6dc81ec33e062a443e9d3eb1033e42f5d3e16acc4409970320cd26b9a215d0c",
+            "examples": "Пять минимальных семейств, synthetic ids/timestamps/texts; field/type schema extracted from binary, не live business/permission evidence.",
+            "immutable_oracle": "В Stage3 fixture literals копируются в tests/test_realtime_reasoning.py; до adapter expectations сверить fixture canonical SHA256 с пакетным fingerprint. Менять fixture по реализации запрещено."
+          },
+          "frozen_fixture_sha256": "896ae246586487a179d3be99947cc8455ed069a6e98b8b8628690158a1a80ac2"
         },
-        "non_stream": "serve используется и stream=False через общий source; Run копит чистые model reasoning/text/native/usage как сейчас. Synthetic [мост] статусы — только SSE presentation, в JSON reasoning_content не добавляются. Google direct dispatch остаётся первым и не создаёт serve/новые timers."
+        "non_stream": "serve используется и stream=False через общий source; Run копит чистые model reasoning/text/native/usage как сейчас. Synthetic [мост] статусы — только SSE presentation, в JSON reasoning_content не добавляются. Google direct dispatch остаётся первым и не создаёт serve/новые timers.",
+        "listener_ownership": {
+          "protocol": [
+            "bind 127.0.0.1:0 -> getsockname -> release immediately before Popen explicit port/new PGID",
+            "Дождаться LISTEN без HTTP/Authorization; bounded lsof -nP -a -iTCP:<port> -sTCP:LISTEN -Fp, только loopback listener PID, проверить os.getpgid(listener_pid)==child_pgid и child lease ещё жив. Несколько PID/ошибка lsof/PGID mismatch не являются успехом.",
+            "Проверка до первого Auth и повторно до отправки Auth на каждом новом TCP соединении; no redirects/no env proxy, connect только 127.0.0.1. Не доверять readiness чужого процесса.",
+            "Mismatch/EADDRINUSE -> abort attempt, ноль байт секрета/промпта чужому listener; закрыть собственный child/PGID, не посылать interrupt/delete чужому listener и не убивать чужой PID. Retry reserve/spawn только при remaining ready>0, admission/spawn token/cap соблюдены."
+          ],
+          "owner_probe_timeout_s": 0.25,
+          "ready_deadline_includes": "bind/spawn/owner probe, лёгкий authenticated GET /api/session/active и cache-miss protocol check вместе <=3.0s; retry port не продлевает deadline",
+          "verification_ids": [
+            "VER-005"
+          ]
+        },
+        "protocol_compatibility": {
+          "version": "2.1.2",
+          "cache_key": [
+            "resolved executable path",
+            "mtime_ns",
+            "size"
+          ],
+          "handshake": "На первом owned serve данного binary key один lightweight authenticated GET /api/info: JSON version==2.1.2 и pid с PGID==owned child group, затем один bounded GET /openapi.json<=512KiB; обе операции внутри того же aggregate ready_budget_s=3.0. OpenAPI.info.version==0.0.1 — версия API schema, НЕ версия CLI; не сравнивать её с2.1.2. Exact required-schema projection по Model.Ref, Permission.Ruleset, PromptInput, TokenUsage.Info/StructuredError/Event fixtures обязателен. Успешно сохранить app version+SHA256 raw OpenAPI+schema projection keyed(path,mtime_ns,size). Остальные spawn этого key только GET /api/session/active плюс PID/PGID ownership, без OpenAPI download и без --version Popen. Version/schema mismatch до prompt ->ServeUnavailable/_ServeHealth; permission capability gap ->security fail-closed.",
+          "invalidation": "mtime_ns/size/path change или fail exact projection -> invalidation; неизвестная patch/schema не считается compatible по одному наличию endpoint. Для новой версии нужен обновлённый подтверждённый fixture/Architect delta. Отсутствие безопасного permission endpoint — security failure, без run fallback.",
+          "fixture_source_evidence_ids": [
+            "EVD-062",
+            "EVD-063"
+          ],
+          "cache_ownership": "Per-Server bounded capability record (only executable key/version/schema hashes/projection, no password/session/prompt). Один fill-owner на binary key; конкурентные fills ждут только remaining own ready3s без блокировки writer, owner cancellation снимает in-flight; никаких live sockets/passwords в cache. Это setup capability metadata, не ControlPlane/Snapshot polling."
+        },
+        "admission": "Один monotonic pre_spawn_deadline=now+min(5.0,remaining_request) охватывает _SpawnRateLimiter и _StartupGate. Сначала получить rate token с timeout=remaining_admission; gate может ждать только остаток этого же окна и fail-open по legacy, без добавочных5s; timeout rate token -> не spawn. Hold gate<=12s не является отдельным pre-spawn wait; release при готовности собственного child/EOF/finally, HTTP ready по-прежнему не событие модели. Cancel poll<=.25s, каждый Popen включая fallback/race учитывается _RequestAttempts<=3; token не обходить.",
+        "session_wire": {
+          "schema": "opencode serve v2.1.2, EVD-062/EVD-063; paths и JSON properties заморожены до Coder",
+          "create": {
+            "method": "POST",
+            "path": "/api/session",
+            "headers": {
+              "Content-Type": "application/json",
+              "Authorization": "Basic <ephemeral runtime secret, never stored>"
+            },
+            "body": {
+              "location": {
+                "directory": "<existing absolute request workdir>"
+              },
+              "model": {
+                "providerID": "opencode",
+                "id": "deepseek-v4.1-flash-free",
+                "variant": "high"
+              },
+              "permissions": [
+                {
+                  "action": "*",
+                  "resource": "*",
+                  "effect": "ask"
+                }
+              ]
+            },
+            "success_status": 200,
+            "response_id_path": "$.data.id",
+            "permission_variant": "Для policy=deny тот же ruleset с effect=deny; ask_reject effect=ask + немедленный decision=reject. В API permissions — ARRAY rules, не config object {\"*\":\"ask\"}.",
+            "model_mapping": "Тот же resolved provider/model#variant: отделить providerID и id; #high -> model.variant=\"high\"; effort off/none -> variant отсутствует, не #off. --thinking относится к CLI presentation; HTTP thinking задаётся существующим resolved variant без несуществующего поля thinking."
+          },
+          "subscribe": {
+            "method": "GET",
+            "path": "/api/event",
+            "headers": {
+              "Accept": "text/event-stream"
+            },
+            "success_status": 200,
+            "body": "SSE data JSON envelope {id,created,type,data}; subscribe armed до prompt body, filter data.sessionID"
+          },
+          "prompt": {
+            "method": "POST",
+            "path": "/api/session/{id}/prompt",
+            "body": {
+              "text": "<full unchanged prompt>",
+              "files": [],
+              "delivery": "steer",
+              "resume": true
+            },
+            "success_status": 200,
+            "response": "$.data is Session.Inbox.User; $.data.id is inbox/message id, durable admission, не model completion",
+            "delivery": "steer/queue — admission boundary, НЕ флаг неблокирующего HTTP. Для единственного fresh session input выбран steer; один POST, worker может блокироваться на headers/body параллельно чтению SSE. Не вызывать generate, resume повторно или повторный prompt при задержке ответа.",
+            "budget": "Не session_setup2s. От prompt_send_start ограничен оставшимися first_event20s/first_token60s/общим TIMEOUT1800; при продвижении session событий supervisor не отменяет HTTP только потому, что истёк first_event, но total/cancel/terminal закрывают сокет. Response body не нужен для продолжения чтения событий после headers."
+          },
+          "permission_reply": {
+            "method": "POST",
+            "path": "/api/session/{id}/permission/{requestID}/reply",
+            "body": {
+              "decision": "reject"
+            },
+            "success_status": 204,
+            "request_id_path": "$.data.id of permission.asked; session path id=$.data.sessionID",
+            "note": "Wire key decision, не reply; permission.replied notification содержит reply=reject. Никогда once/always/allow."
+          },
+          "cleanup": {
+            "interrupt": "POST /api/session/{id}/interrupt",
+            "delete": "DELETE /api/session/{id}",
+            "aggregate_api_budget_s": 0.2
+          },
+          "readiness": {
+            "method": "GET",
+            "path": "/api/session/active",
+            "success_status": 200,
+            "response_example": {
+              "data": {}
+            },
+            "schema": "$.data is record keyed by sessionID, not an array; source byte offset114978382",
+            "budget": "part of ready_budget_s=3.0, not first_event; owner proof before auth"
+          },
+          "version_probe": {
+            "method": "GET",
+            "path": "/api/info",
+            "response_example": {
+              "version": "2.1.2",
+              "pid": "<actual child PID integer>"
+            },
+            "note": "Пример pid placeholder только в документации, wire integer; owner PGID проверяется до Auth независимо от self-reported pid. appversion2.1.2 отличается от OpenAPI.info.version0.0.1. Once per executable stat key, withinready3s."
+          }
+        },
+        "data_isolation": {
+          "XDG_DATA_HOME": "На каждый serve spawn tempfile.mkdtemp(prefix=\"zen-serve-data-\") в локальном temp вне репозитория/Drive; env[\"XDG_DATA_HOME\"]=каталог. OPENCODE_MODELS_PATH сохраняется из _run_env, не терять standalone model catalog. Не копировать/не мигрировать/не редактировать общую ~/.local/share/opencode/opencode.db (2.27 GB, F-28).",
+          "ownership": "Путь принадлежит attempt lease; child создаёт собственный SQLite. После kill/reap и закрытия readers в finally shutil.rmtree(temp_data_dir,ignore_errors=True), на каждом exit, including spawn exception/port race/setup/auth/cancel/terminal. Cleanup idempotent; директории чужих attempts не трогать.",
+          "cleanup_budget": "Входит в aggregate cleanup<=1.2s. Реальный FS cleanup/RSS/DB locking проверяются H3; превышение запрещает enable, не выдавать ignore_errors за доказанное удаление.",
+          "verification_ids": [
+            "VER-005"
+          ]
+        },
+        "typing": "Новый wire JSON декодируется в object с явным isinstance/type narrowing и TypedDict, без Any/кастов Any/type-ignore для обхода. Новый модуль serve_transport.py запрещён текущим allowlist; всё внутри server.py. VER-004: formatter/linter на всех3 файлах, basedpyright severity==error ровно0 на всех3, server reportAny<=125 и reportExplicitAny<=125, остальные frozen per-rule warning budgets не растут.",
+        "transport_health": {
+          "owner": "_ServeHealth per Server, key=(resolved executable,mtime_ns,size), lock/monotonic; состояние отдельно от model _UpstreamBreaker",
+          "consecutive_failure_threshold": 3,
+          "degrade_ttl_s": 120.0,
+          "degraded_transport": "run для новых auto requests",
+          "counted_failures": [
+            "first_event_timeout на serve после prompt и HTTP readiness, без валидных событий исполнения",
+            "invalid_serve_event / incompatible schema projection / malformed required v2 fields",
+            "serve SSE EOF без terminal; first_token_timeout только при доказанной protocol/capability причине, иначе model failure"
+          ],
+          "not_counted": "Реальные provider errors (429/free-limit,5xx,provider network), explicit auth/permission/security failure, client_gone, slot rejection и transient child DB errors не маскировать transport failure. Если валидные execution events пришли, но model token нет, first_token_timeout сохраняет обычную provider classification при отсутствии доказанного protocol defect.",
+          "state_machine": "HEALTHY consecutive0..2; третий законченный protocol-specific failure -> DEGRADED(until=now+120), последующие auto requests run без serve probe/Popen. Это НЕ повтор/переключение текущего DELIVERED prompt: транспорт текущего запроса закреплён, silent replay запрещён. В DEGRADED skipped requests не продлевают TTL. При TTL expiry ровно один HALF_OPEN serve probe request (другие auto requests run); только валидный terminal success со schema-valid source очищает consecutive/degraded. Failed protocol probe -> новый TTL120. Provider failure не объявлять protocol success/failure. Neutral cancel освобождает probe, не продлевает TTL. Force serve допускает диагностику, не обходя security/kill-switch/cap3.",
+          "breaker_isolation": "Protocol-specific failure никогда не вызывает _UpstreamBreaker.failure/commit pending model failure. Provider failures сохраняют общий breaker threshold5/cooldown jitter/HALF_OPEN1. Нейтральный transport-only финальный запрос освобождает model probe lease после cleanup; success/failure не выдумывать. _RetryBudget и MAX_TOTAL_SPAWNS остаются общими даже для protocol retry/fallback.",
+          "telemetry": "O-EXIT transport_history и attempt reason различают serve_protocol_failure, serve_health_degraded/run, serve_health_probe, policy failure и provider failure; no secrets. Skipped serve не добавляет фиктивный spawn.",
+          "verification_ids": [
+            "VER-005"
+          ]
+        },
+        "immutable_run_env": {
+          "symbol": "bridges/opencode-zen-bridge/server.py:_run_env",
+          "source_slice": "ast FunctionDef.lineno..end_lineno inclusive, raw file bytes splitlines(keepends=True), includes terminal LF",
+          "sha256": "1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31",
+          "test_run_env_sha256": "d3d0baf57f7ccae7dd7846ab98d3da43c588a35e7f076fabe074c1212f232e05",
+          "start_sh_sha256": "5430e529627b3a705da4be7641a6d079408e3cf85b6ad3333330e34cb08c190c",
+          "verification": "VER-005 compare literal hashes from frozen packet; _serve_env wrapper only, never recalculate expected from edited implementation"
+        }
       }
     },
     {
@@ -1057,11 +1502,12 @@
         "timer_anchor": "t_sse_open — flush первого role chunk. FIRST_STATUS_DELAY_S=0.30; тик writer <=0.05..0.10 s. Background setup/adapter НЕ блокирует writer на gate.acquire, rate wait, connect, POST prompt или join. Ровно один поток пишет self.wfile; worker передаёт события через bounded queue. Никаких независимых Timer-writers в wfile.",
         "eligibility": "Только non-Google SSE с effective thinking/reasoning включённым (effort непустой; default high считается включённым). Явные off/none из _map_effort исключают synthetic reasoning даже при долгом запуске. Это явное сужение AC-005: оно относится к thinking-enabled DSH, а fast-answer/off сохраняет текущий contract. Модельные reasoning, если пришли от upstream, не выдумывать/не подменять.",
         "initial": "На t>=0.30 при отсутствии уже ОТПРАВЛЕННОЙ непустой real reasoning_content/content delta и незавершённом запросе отправить {reasoning_content:\"[мост] Подключение к модели…\\n\"} с реальным LF, flush. Пробелы и empty keepalive не считаются real progress. При доступной real delta в том же тике сначала обработать очередь, затем проверить grace: fast fake <50ms не получает prefix. Если real text пришёл раньше grace, initial status не нужен — ответ уже видим. Если real reasoning пришёл раньше grace, Think видим без synthetic prefix; отсутствие LF в быстром Simple greeting. не даёт права мутировать текст.",
-        "lifecycle": "Startup-gate/spawn wait статусы только после grace при фактическом ожидании, без немедленного prefix на быстром acquire. До первого real token при тишине heartbeat каждые 5.0 s: [мост] Ожидание первого токена (N с)… + LF. После real progress и затем настоящего stall можно каждые 5 s дать [мост] Ожидание продолжения… + LF. Статусы не сбрасывают transport/model watchdog timestamps и сами не считаются attempt_output. Нормальные 127 ms reasoning delta не сопровождаются heartbeat.",
-        "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning.",
-        "pure_reasoning": "Склейка model-origin delta равна upstream model bytes после унаследованной очистки известных interrupted artifacts; не добавлять LF для preview, пробелы и UTF-8 не переписывать. _strip_interrupted должен оставаться chunk-boundary-safe: распознанный interrupted marker удерживается/удаляется инкрементально, partial prefix не протекает; обычный текст не нормализуется. В тестах удалять synthetic delta по provenance/expected list, а не слепо вырезать любую модельную строку [мост].",
+        "lifecycle": "Startup-gate/spawn wait статусы только после grace при фактическом ожидании, без немедленного prefix на быстром acquire. До первого real token при тишине heartbeat каждые 5.0 s: [мост] Ожидание первого токена (N с)… + LF. После real progress и затем настоящего stall можно каждые 5 s дать [мост] Ожидание продолжения… + LF. Статусы не сбрасывают transport/model watchdog timestamps и сами не считаются attempt_output. Нормальные 127 ms reasoning delta не сопровождаются heartbeat. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
+        "retry": "При действительно принятом retry ровно одна отдельная delta [мост] Повтор попытки 2/3… + LF, далее 3/3. Писать до ожидания backoff после retry admission, не при отказе бюджета. Даже после model reasoning статус не конкатенируется в model bytes. Raw model reasonings всех попыток не дедуплицировать; обычный content prefix dedup остаётся. Synthetic status никогда не участвует в _incomplete_tool_step_prompt, model had_output, usage или accumulated raw reasoning. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
+        "pure_reasoning": "Склейка model-origin delta равна upstream model bytes после унаследованной очистки известных interrupted artifacts; не добавлять LF для preview, пробелы и UTF-8 не переписывать. _strip_interrupted должен оставаться chunk-boundary-safe: распознанный interrupted marker удерживается/удаляется инкрементально, partial prefix не протекает; обычный текст не нормализуется. В тестах удалять synthetic delta по provenance/expected list, а не слепо вырезать любую модельную строку [мост]. Перед synthetic status применять status_separator: ведущий LF только в synthetic delta после незавершённой model строки, никогда не в model bytes; статус не входит в watchdog/usage/prompt.",
         "regression": "test_interrupted_artifact_removed_from_reasoning_stream: быстрая последовательность marker + Simple greeting. -> exactly Simple greeting., один run, zero status. В JSON тоже exactly. Slow FakeServe: first status <=1.0 s при заблокированном upstream; visible(text.strip) true, latestCompletedParagraphFirstLine получает завершённый LF. Natural reasoning LF обновляет collapsed row, bytes неизменны.",
-        "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt."
+        "replay": "_render_turn/_messages_to_prompt (server.py:1848-1888) по-прежнему игнорируют assistant.reasoning_content/reasoning_details. Ни bridge status, ни сырые reasonings не добавляются в повторный prompt. Остаточный межпровайдерский replay в DSH при ручной смене модели описан RISK-011; current bridge ignore не доказывает безопасность чужого provider.",
+        "status_separator": "Перед любой synthetic [мост] delta, если ранее выданный модельный reasoning chunk не оканчивался LF и текущая видимая строка не завершена, prefix=\"\n\"; результат \"\n[мост] ...\n\". Весь prefix/status/trailing LF имеет synthetic provenance, отдельно от immutable model deltas. Если LF уже есть или модельного reasoning ещё не было, status начинается \"[мост]\" без добавочного LF. Единственный writer отслеживает line boundary; быстрый Simple greeting. до grace вообще не вызывает status helper. Фильтрация synthetic по provenance сохраняет AC-006 байт-в-байт и модельную строку, буквально начинающуюся [мост]."
       }
     },
     {
@@ -1116,11 +1562,11 @@
           "env_prefix": "OPENCODE_ZEN_BRIDGE_",
           "validation": "положительное finite число; недопустимое -> ошибка старта, не бесконечный timeout"
         },
-        "clocks": "watchdog attempt_start сразу перед gate/startup, поэтому gate/readiness не создаёт неучтённой тишины. first_event — первый валидный transport/server event (legacy step_start или validated serve readiness/SSE event), а не байт stderr/whitespace/comment/status мостa; clock одноразовый, поздние heartbeat его не продлевают. first_token — первый non-whitespace model reasoning/text/native tool intent, не encrypted-only/started/bridge status. stall запускается после first_token и обновляется только non-whitespace model delta/полезным tool event. Empty SSE ping и служебный шум не оживляют token/stall. Пределы проверять до/после каждой операции; total deadline неизменен на всех attempts.",
+        "clocks": "Общий request deadline TIMEOUT_S=1800 якорится на request t0 и не сбрасывается. Local pre-spawn admission<=5.0s, SERVE_READY_TIMEOUT_S=3.0 и create+subscribe<=2.0 имеют отдельные часы до prompt. Для serve first_event20.0 и first_token60.0 начинаются в prompt_send_start перед первым байтом POST /prompt; first_event удовлетворяется только первым валидным SSE событием исполнения created session после этого момента (session.execution.started/session.step.started/session.reasoning.started, либо валидная текущая model delta). HTTP readiness/headers, server.connected/session.created, чужие/global updates, comments, bridge statuses не гасят first_event и не ставят first_event_ms. Headers POST устанавливают только delivered barrier. Для legacy сохраняется first valid run event/step_start от attempt_start перед startup. first_token — только non-whitespace model reasoning/text или полезный model tool intent; started/control/encrypted-only/reject notification не токен. stall стартует после first_token и обновляется полезными model delta/tool progress; empty ping/status не продлевают. first_event_ms и ttft_ms в O-EXIT относительно request t0, timeout ожидания serve first_event относительно prompt_send_start. При accepted prompt + zero session SSE ->first_event_timeout20s +cleanup<=1.2s, <=22s, не ожидание60s.",
         "disconnect": "На каждой итерации/ожидании <=0.25 s проверять cancel flag и client socket select + recv(MSG_PEEK|MSG_DONTWAIT): EOF/ECONNRESET -> client_gone без чтения данных и без переключения wfile в nonblocking. Реальная bounded empty OpenAI keepalive каждые <=2.0 s тишины страхует разрыв, который TCP ещё не сигнализировал; write deadline <=0.5 s, без write на отдельном потоке. Poll, status, write и cleanup не блокируют supervisor на 15/5 s. Суммарное обнаружение контролируемого FIN/RST <=5.0 s. Полное исчезновение сети без FIN нельзя доказать одним MSG_PEEK — bounded write/OS transport timeout и fault injection отдельно, не обещать физически невозможный мгновенный детект blackhole.",
-        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent.",
-        "retry": "first_event_timeout/first_token_timeout/stall_timeout -> transient failure; после cleanup retry admission в _RequestAttempts, FAIL_RETRY_LIMIT и MAX_TOTAL_SPAWNS=3 без отдельного transport budget. _RetryBudget расходуется как provider retry; watchdog не выдавать за budget-free local sqlite error. Full Jitter min(cap=2,base=.5*2**retry), ограниченный remaining deadline. Sleep/pool/gate/rate waits cancellation-aware, poll<=.25; один slot удерживается на весь запрос и release exactly once в finally. failed last request -> breaker failure, recovered request -> success как текущий commit; HALF_OPEN не выдаёт лишнюю пробу. client_gone/deterministic 4xx/security denial -> без retry/fallback. HALF_OPEN проба имеет owner token до завершения/подтверждённого cleanup; никакой повторной живой пробы только из-за reset_s. FakeClock test активной пробы дольше cooldown обязателен, neutral client cancel не оставляет вечной занятости.",
-        "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки."
+        "cleanup": "T-LIFE: после cancel/terminal/watchdog/error/overflow/tool step/success в одном finally: запретить новый prompt/spawn; serve interrupt и DELETE с общим cleanup API ceiling 0.20 s (каждый <=0.10 s, ошибки не блокируют kill); close SSE/control sockets для разблокировки reader; SIGTERM сохранённому own PGID даже если proc.poll уже завершён; grace<=0.50 s, затем SIGKILL тому же PGID при наличии; reap leader и join owned readers/writer <=0.50 s суммарно. Запрет blanket pkill, чужих PID и повторного сигнала переиспользованному PGID после подтверждённого cleanup. cleanup идемпотентен и защищён lock; kill также descendant при leader exit (EVD-056). Target watchdog+2 s и disconnect detect<=5 s + cleanup<=2 s, итог orphan-free<=7 s; не сохранять старые wait(15)+join(5)+kill-parent. После child kill/reap обязателен finally shutil.rmtree(owned XDG_DATA_HOME,ignore_errors=True); закрыть также daemon prompt delivery socket и join его в том же aggregate cleanup<=1.2s. Interrupt/delete только после ownership proof, никогда чужому listener.",
+        "retry": "Watchdog first_event/first_token/stall -> bounded common retry after full cleanup, _RequestAttempts/MAX_TOTAL_SPAWNS3/FAIL_RETRY_LIMIT/_RetryBudget/Full Jitter как ранее. Но serve-specific no-session-event/invalid_serve_event/EOF классифицируются _ServeHealth и НЕ _UpstreamBreaker; общие provider failures по-прежнему model breaker. При DELIVERED silent run fallback запрещён: retry текущего запроса остаётся явным на закреплённом транспорте, health TTL влияет только на последующие auto requests. Legacy watchdog сохраняет provider semantics. client_gone/fatal4xx/auth/permission ->no retry/fallback. HALF_OPEN owner token жив до завершения/cleanup, cooldown не допускает второй probe; neutral transport failure/cancel освобождает probe без fake provider success/failure. Slot один на запрос, release once; cancel-aware waits<=.25s; Full Jitter capped remaining.",
+        "telemetry": "_new_exit_state устанавливает transport=none, first_event_ms=null, ttft_ms=null до любого early exit. _log_exit на КАЖДОМ do_POST exit ровно один O-EXIT/v1 с transport(run|serve|google|none), first_event_ms и ttft_ms относительно request t0 (без status/keepalive), exit_reason и общими total_spawns/retries; attempt-local timings отдельно для диагностики. Путь с fallback показывает last transport и transport_history=[serve,run], секретов/промпта/endpoint password нет. Новый primary exit_reason не перетирается generic timeout; финальная успешная retry даёт ok + attempt exit history. Все 4 timeout/client codes проверяются на stream и JSON, including exits до попытки. HTTP readiness НЕ first_event_ms: поле null до valid SSE execution current session после prompt_send_start. transport_history фиксирует отказ serve/TTL run или probe без secrets и phantom Popen; отдельный reason для protocol/model/security. early HTTP headers не ставят ни first_event_ms, ни ttft_ms."
       }
     },
     {
@@ -1209,7 +1655,7 @@
       "quality": "compatibility",
       "source": "legacy fake CLI",
       "stimulus": "fake script игнорирует argv и блокируется на stdin.read",
-      "environment": "auto/default flag disabled либо auto shebang",
+      "environment": "auto/default true + shebang filter либо explicit disabled/run/disable-file",
       "artifact": "bridges/opencode-zen-bridge/server.py",
       "response": "один run без serve probe, reasoning exact Simple greeting.",
       "response_measure": "all17 modules green; runs==1, no synthetic prefix для fast fixture",
@@ -1253,7 +1699,7 @@
       "quality": "security",
       "source": "модель/враждебный upstream",
       "stimulus": "native tools пытаются писать файл или запросить allow",
-      "environment": "serve Basic loopback и deny/ask-reject",
+      "environment": "serve loopback с listener owner proof, default ask_reject или explicit deny",
       "artifact": "bridges/opencode-zen-bridge/server.py",
       "response": "никогда allow, native event -> DSH tool tuple",
       "response_measure": "fake permission requests reject; false flag no secret allocation; live H6 отдельно",
@@ -1302,7 +1748,7 @@
       "environment": "design envelope single-process",
       "artifact": "bridges/opencode-zen-bridge/server.py",
       "response": "resource manager bounds and overload",
-      "response_measure": "memory1408<=1638.4MiB estimate; byte queue/FD/port and maxchild assertions",
+      "response_measure": "Design:1*256+6*192=1408<=1638.4 MiB. H3 измеряет parent+6*child actual RSS и отсутствие database is locked на103KB×6×3; без H3 runtime PASS отсутствует.",
       "verification_ids": [
         "VER-005"
       ],
@@ -1332,7 +1778,7 @@
     {
       "id": "BND-002",
       "component": "managed serve/run source + per-Server resource manager",
-      "responsibility": "Transport selection/auth, fresh env/proxy, bounded queue, lifecycle/PGID ownership и canonical event tuples",
+      "responsibility": "Transport selection, listener PID/PGID proof до Auth/prompt, fresh _serve_env/proxy и isolated XDG_DATA_HOME, bounded HTTP/SSE/delivery leases, canonical wire adapter и cleanup",
       "allowed_dependencies": [
         "stdlib http.client/socket/subprocess/queue/threading/secrets",
         "_run_env/_RequestAttempts/_StartupGate",
@@ -1369,7 +1815,7 @@
     {
       "id": "BND-004",
       "component": "_Resilience/_RequestAttempts",
-      "responsibility": "Один process-level bulkhead, rate/retry budget/breaker; per-request spawn count и deadlines",
+      "responsibility": "Общий process bulkhead/rate/retry budget/model breaker; отдельно _ServeHealth для protocol-specific failures, per-request cap/deadline и prompt delivered barrier",
       "allowed_dependencies": [
         "injected monotonic/RNG",
         "locks"
@@ -1444,7 +1890,7 @@
       "scenario": "deny удаляет tool schema, Zen403 или ask непреднамеренно исполняет tool",
       "probability": "high",
       "impact": "high",
-      "mitigation": "Scoped deny baseline; если несовместим, заранее выбранный ask-auto-reject, никогда allow. Capability/permission failure fail-closed. FakeServe доказывает reject/mapping, live H6 требуется перед rollout.",
+      "mitigation": "Default ask_reject в отдельном _serve_env поверх byte-identical _run_env; wire permission.asked ->decision=reject немедленно, never once/always/allow. Env deny поддержан без пересборки, без automatic policy fallback. 401/403/нет safe endpoint fail-closed; FakeServe обе policy, реальный H6 обязателен.",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -1455,7 +1901,7 @@
       "scenario": "Proxy env не означает фактическую per-request clean IP ротацию через loopback georouter",
       "probability": "medium",
       "impact": "high",
-      "mitigation": "Сохранить _run_env на каждый child, test env calls/sequence; OPEN06 реальный egress/H3 нужно подтвердить. Shared daemon не использовать; тест env не объявлять доказательством clean IP.",
+      "mitigation": "Сохранять per-spawn _next_standalone_proxy env через неизменный _run_env; AC-018 проверяет последовательность записей пула. baseURL=http://127.0.0.1:10830/v1 georouter обходит child HTTP_PROXY по NO_PROXY (F-15/F-27); новый child не доказывает новую Zen IP. Shared daemon не выбирать ради failure isolation, не ради недоказанной egress ротации; конфиг georouter вне scope.",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -1466,7 +1912,7 @@
       "scenario": "6 serve на sqlite2.27GB/192MiB оценке создают lock/memory spike",
       "probability": "medium",
       "impact": "high",
-      "mitigation": "Startup gate/rate+bounded6, output/queue budgets, memory1408MiB; cleanup retries. H3 RSS/FD/DB locks mandatory before enabling.",
+      "mitigation": "В _serve_env temporary XDG_DATA_HOME per Popen, preserve OPENCODE_MODELS_PATH, finally rmtree after group cleanup; shared2.27GB DB не трогать. Design memory1408<=1638.4MiB не measured RSS. H3 до production sync:6 parallel103KB×3 +7th overload, max_actual_parent_RSS+6*max_actual_child_RSS<=0.80*2048MiB и ноль database is locked (ретрай не маскирует contention). FAIL->disable-file сохраняется, rollout запрещён; slots6/waiters12 не повышать.",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -1477,7 +1923,7 @@
       "scenario": "Fast fake probe увеличит run counter или блокируется stdin",
       "probability": "high",
       "impact": "high",
-      "mitigation": "auto shebang route directly run zero probes; force serve DEVNULL + .5s ready ceiling; cached stat key. Regress exact1run and no5s hang.",
+      "mitigation": "Auto shebang ->one run, no subprocess probes при default=true. Force serve stdin DEVNULL, ready<=3.0s/cancel-aware. Cache по path+mtime_ns+size; exact counter regressions остаются. Никакой fake5s stdin hang.",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -1521,7 +1967,7 @@
       "scenario": "Полный lint/type gate красный до изменения",
       "probability": "high",
       "impact": "medium",
-      "mitigation": "VER004 baseline-aware точные old error sites + warning per-rule budgets; не расширять allowance и не считать budget green чистым typing. Новый test file полный ruff.",
+      "mitigation": "VER-004 заменяет прежний overlay на strict formatter/linter/type checks всех3 files. Унаследованные E402 и2 type errors EVD052/053 честно baseline, их allowance удалён: Coder должен исправить в allowlist без подавления диагностики/конфига. severity error0, reportAny/reportExplicitAny<=125 server.py, прочие frozen warning budgets не растут; format may reveal debt, FAIL нельзя объявить PASS.",
       "verification_ids": [
         "VER-004"
       ]
@@ -1531,7 +1977,7 @@
       "scenario": "Prompt POST timeout уже после принятия способен удвоить generation при silent fallback",
       "probability": "medium",
       "impact": "high",
-      "mitigation": "Fallback barrier before first prompt send; after ambiguous acceptance только общий explicit transient retry с cleanup, status и cap; builtins cannot run.",
+      "mitigation": "Текущий brief RW-001 выбирает HTTP response headers / первый current-session execution event как delivered barrier, вместо R1 начала POST. До headers и без события ServeUnavailable может fallback после полного kill/reap старого PGID; remote generation могла уже начаться, exactly-once не обещать. После barrier silent run запрещён; только явный same-transport retry+status/cap, no builtin execution. Source disagreement записан в panel_resolution_choices.",
       "verification_ids": [
         "VER-001",
         "VER-005"
@@ -1545,6 +1991,26 @@
       "mitigation": "PGID сохранён при spawn, group kill даже leader exited, cleanup bounded1.2s; собственный lifecycle реестр, никакого pkill; finally every branch.",
       "verification_ids": [
         "VER-001",
+        "VER-005"
+      ]
+    },
+    {
+      "id": "RISK-011",
+      "scenario": "Статусы [мост] сохраняются DSH и при ручном переключении модели могут попасть reasoning_content другого provider (F-33/F-38/F-39)",
+      "probability": "medium",
+      "impact": "medium",
+      "mitigation": "Принятый остаточный риск: current bridge игнорирует весь replay reasoning, но чужой provider этого не обязан делать. Короткие статусы только grace/реальное ожидание не чаще5s и один на retry, no secrets/prompt text. Не менять DSH/provider контракты; уменьшить объём синтетики. Fake replay проверяет только этот мост, cross-provider H4 наблюдение не заменяет гарантии.",
+      "verification_ids": [
+        "VER-005"
+      ]
+    },
+    {
+      "id": "RISK-012",
+      "scenario": "Serve SSE/protocol деградация ошибочно открывает общий model breaker и блокирует рабочий run",
+      "probability": "high",
+      "impact": "high",
+      "mitigation": "_ServeHealth threshold3/TTL120/one recovery probe для новых auto requests, protocol failure не _UpstreamBreaker. Current accepted prompt не переигрывать скрыто. Fake5requests + expiry/probe/version-change cases; настоящие provider429/5xx сохраняют model breaker.",
+      "verification_ids": [
         "VER-005"
       ]
     }
@@ -1567,7 +2033,7 @@
       {
         "id": "THREAT-001",
         "scenario": "Подмена локального serve listener/вывод случайного пароля в stdout",
-        "mitigation": "Loopback127.0.0.1, generated password env before spawn, v2 handshake authenticated+no redirects, own process lifecycle. Не логировать Basic/header/body/raw stdout; всё маскируется перед log.",
+        "mitigation": "Parent bind loopback0/getport/release-before-Popen explicit port/newPGID; до Auth/prompt lsof listener PID->os.getpgid==childPGID, bounded<=.25s внутри ready3s. Foreign listener/owner unavailable ->zero secret/prompt bytes, cleanup own child only, bounded new port retry/cap3. Пароль secrets env до spawn, stdout redact, no redirects/proxy. VER-005 deliberate port takeover negative test.",
         "verification_ids": [
           "VER-005"
         ]
@@ -1575,7 +2041,7 @@
       {
         "id": "THREAT-002",
         "scenario": "Модель выдаёт builtin bash/write/edit, пока DSH думает, что это только предложение",
-        "mitigation": "deny-all или ask+API immediate reject, never allow; unknown permission capability fail-closed. Native события только переводятся в DSH tool_calls/unmapped. Live H6 доказывает no file mutation.",
+        "mitigation": "Default OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject: _serve_env(model_id) вызывает _run_env(model_id) ровно один раз, копирует/merge scoped OPENCODE_CONFIG_CONTENT permission={\"*\":\"ask\"} с сохранением provider/options/OPENCODE_MODELS_PATH, session permissions=[{action:\"*\",resource:\"*\",effect:\"ask\"}]. _run_env(model_id) оставить ПОБАЙТОВО неизменным, tests/test_run_env.py не менять. На wire permission.asked (логическая группа session.permission.requested) немедленно POST /api/session/{id}/permission/{data.id}/reply {decision:\"reject\"}; никогда allow/once/always. Reply через bounded control lane, не ожидает completion prompt POST, HTTP budget<=.25s и cancel/deadline; failure -> явный security error+cleanup, без деградации в разрешение. Env=deny выставляет config permission={\"*\":\"deny\"} и session effect=deny, без пересборки; если всё же пришёл ask, только reject. Неподдержанная policy/отсутствие safe permission capability -> fail-closed. Нет автоматического deny↔ask_reject switching даже до prompt: разница позиций R1 закрыта явным выбором безопасного селектора. После принятия prompt 401/403 никогда не дают run fallback. EVD-050 + F-08 объясняют Zen403 с deny; FakeServe проверяет оба режима и byte hash _run_env, реальную Zen совместимость/запрещённую запись доказывает только H6.",
         "verification_ids": [
           "VER-005"
         ]
@@ -1583,7 +2049,7 @@
       {
         "id": "THREAT-003",
         "scenario": "Unrestricted parent env утекает в serve или proxy creds в ошибку",
-        "mitigation": "_run_env whitelist как legacy, password добавляется только child env; no apiKey dump, redact stdout/stderr/exception before _log and response; тест secret sentinels.",
+        "mitigation": "_run_env whitelist как legacy, password добавляется только child env; no apiKey dump, redact stdout/stderr/exception before _log and response; тест secret sentinels. _serve_env wrapper не меняет _run_env и сохраняет model catalog, private XDG data удаляется finally.",
         "verification_ids": [
           "VER-005"
         ]
@@ -1591,7 +2057,7 @@
       {
         "id": "THREAT-004",
         "scenario": "SSE из чужой session или reconnect replay приводит к чужому выводу/повтору инструмента",
-        "mitigation": "Filter exact session/execution IDs, subscribe before prompt; no transparent reconnect replay после prompt; step/call IDs dedup; no raw events in public stream.",
+        "mitigation": "Filter exact data.sessionID и own prompt-send generation boundary; session v2 не даёт executionID, не ожидать выдуманного поля. subscribe armed before prompt, no transparent reconnect/replay after delivered; event id + assistantMessageID step/call id dedup; no foreign/raw events in public stream.",
         "verification_ids": [
           "VER-005"
         ]
@@ -1607,25 +2073,34 @@
     ]
   },
   "evolution": {
-    "compatibility": "OpenAI endpoints/port/auth/format/Google route preserved; canonical source powers stream and JSON. Serve default-disabled, auto text scripts direct run. New statuses scoped thinking+grace; legacy pure fast reasoning unaffected.",
-    "migration": "NOT_APPLICABLE: нет data schema/DB миграций и новых dependencies; opencode.db/shared config не менять. Each ephemeral session DELETE в cleanup; session history child creates via штатный API, prompt retention унаследован OpenCode, не выгружать в артефакты.",
-    "rollout": "Stage2 validators+fingerprint -> downstream external architecture panel/proof (orchestrator) -> Stage3 tests red→green/code -> independent clean-room VER001..005 all green -> отдельный deploy/sync H0 -> canary enable flag=true auto и H1..H9. 103KB+6parallel×3, DSH Think screenshots/Stop, H6 запрещённая запись, egress proxy/RSS/FD. Пока это не пройдено, business result не сдан. Ничего из ~/.dsh не входит в clean-room VER.",
-    "rollback": "REALTIME_SERVE_ENABLED=false либо TRANSPORT=run и контролируемый restart конфигурации возвращают legacy transport; сначала отменить active leases, zero orphans, no daemon overlap. Watchdog/status fixes остаются. Если они дали регресс — revert Stage3 commit и сверить копии H0, live legacy H9. В Stage2 rollback/deploy не выполняется.",
-    "feature_flag": "Env switch вместо GigaRC в конкретном локальном stdlib контуре явно разрешён текущим брифом и имеет default=false; нельзя выдавать его за удалённый GigaRC без рестарта."
+    "compatibility": "Публичные OpenAI endpoints/port/auth/schema и Google route неизменны, source общий для SSE/JSON. Default serve flag=true в auto только для нативного бинарника; shebang fake CLI остаётся run без probe, start.sh и _run_env byte-identical. Fast/off/JSON synthetic statuses как раньше исключены.",
+    "migration": "NOT_APPLICABLE: продуктовая схема/DB/dependencies не меняются; shared opencode.db/config не трогать. Каждый child получает свежий local-temp XDG_DATA_HOME и сохранённый OPENCODE_MODELS_PATH; наконец interrupt/delete/kill/reap и shutil.rmtree(...,ignore_errors=True). История ephemeral, долговременные prompt/secret артефакты не сохраняются.",
+    "rollout": "Stage2 packet cycle2/role-plan/schema/fingerprint -> external architecture Council R2+verify_panel_proof оркестратора -> Stage3 red→green+independent clean-room VER001..005 strict. Default=true НЕ разрешает обход H3: ДО синхронизации server.py в боевой :9883 отдельно изолированный candidate runtime с effectiveM6/waiters12, live103KB prompts6parallel+7th,3повтора и H3 memory/SQLite check. На боевом до допуска удерживать disable-file, который действует сразу при первом старте новой server.py; файлы ~/.dsh в Stage2 не создавать. Только H3 PASS и безопасная policy H6 разрешают H0 sync/read-back, без изменения start.sh; при удалении disable-file native Mach-O в auto сразу serve. После sync H1/H2/H3 повторно+DSH H4/H5/H6/H7/H8/H9; любой memory/DB/security FAIL немедленно disable-file и run. Не перекладывать pre-rollout safety на уже случившийся default-enable. На этом проходе все H0..H9 NOT_RUN.",
+    "rollback": "Мгновенный kill-switch без рестарта: создать OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE (default ~/.dsh/bridges/opencode-zen-bridge/disable-serve) -> следующий запрос run без serve allocations/probes; удаление файла возвращает auto при healthy transport. Env REALTIME_SERVE_ENABLED=0 или TRANSPORT=run также принудительно run (смена env уже живого процесса требует restart, не путать с file switch). In-flight leases drain/cancel, delivered prompt не повторять на run. H9 проверяет в живом existing DSH чате создание/удаление файла, неизменный PID сервиса, run/serve transport_history и успешные повторные/параллельные вызовы. Если status/watchdog regression -> отдельный rollback Stage3 commit+H0 identity. Stage2 rollback/deploy не выполняется.",
+    "feature_flag": "Explicit cycle2 RW-009/FU-006 override: default=true для локального auto-native пути, zero-serve-cost explicit disable и O(1) file switch без рестарта. Прецедент F-40/STEP_RECOVERY; GigaRC/start.sh dependencies вне allowlist. H3 и H6 обязательны до production enable.",
+    "H3_rollout_gate": {
+      "status": "NOT_RUN",
+      "scenario": "6 parallel реальных рабочих prompt около103KB +7th overload,3повтора; изолированный candidate перед production sync и повтор на боевом после safety допуска",
+      "memory_unit": "MiB",
+      "memory_inequality": "1*actual_parent_RSS_max + M*actual_child_RSS_max <=0.80*Mem_limit_per_pod; M=6; limit=2048MiB, rhs=1638.4MiB",
+      "database_gate": "Ноль database is locked/SQLITE_BUSY на isolated per-spawn XDG DB; ретрай в FAIL_RETRY_LIMIT не превращает lock failure в PASS. Shared2.27GB DB не изменяется.",
+      "other_evidence": "Реальные RSS/FD/CPU/TTFT каждого запроса, parent/child peaks, все owned temp dirs удалены, zero orphan PGID; design child192MiB не подставлять вместо замера",
+      "on_fail": "Rollout/enable запрещён, disable-file остаётся; не повышать slots6/12 или retry cap3. Не менять текущие shared env/config/DB."
+    }
   },
   "approval": {
     "status": "NOT_REQUIRED",
     "decision_ids": [],
     "approved_by": null,
     "evidence_ref": null,
-    "rationale": "Все AD two-way и следуют текущему брифу; публичный auth/контракт/данные не меняются. APPROVED ниже означает валидированный архитектурный контракт, не голос Совета."
+    "rationale": "AD остаются reversible/two-way в рамках explicit cycle2 brief (EVD-064), включая headers barrier/default=true. APPROVED здесь — архитектурный кандидат, не ACCEPT Совета; R2 и packet/surface freeze обязательны до Coder."
   },
   "independent_review": {
     "required": false,
     "status": "NOT_REQUIRED",
     "reviewer": null,
     "evidence_ref": null,
-    "rationale": "S2. Независимый downstream architecture panel остаётся обязанностью оркестратора; здесь не запускается и не подменяется валидатором."
+    "rationale": "S2: universal schema independent_review NOT_REQUIRED сохраняется; обязательный downstream Council R2 с отдельным proof ведёт оркестратор, эта роль не создаёт голос/вердикт."
   },
   "open_questions": [
     {
@@ -1636,9 +2111,9 @@
     },
     {
       "id": "Q-002",
-      "question": "Какую policy совместимости реально поддерживает установленный v2: scoped deny или schema-preserving ask-auto-reject?",
+      "question": "H6: совместимы ли с реальным Zen default ask_reject и optional env=deny при гарантированном builtin rejection?",
       "blocking": false,
-      "disposition": "Обе безопасные ветви заранее разрешены; FakeServe доказывает protocol, H6 доказывает реальный отказ file action до rollout. Не включать при неустановленной безопасной policy."
+      "disposition": "Default выбран, автопереключения нет. FakeServe обе policy не доказывает live H6; неизвестная safe capability fail-closed, до H6 боевой disable-file не снимать."
     }
   ],
   "protected_paths": [
@@ -1649,20 +2124,23 @@
   "deferred": [
     "Живая приёмка H0..H9 и синхронизация ~/.dsh выполняются только rollout-этапом после clean-room verifier и downstream panel.",
     "OPEN-05/16: прямой Zen HTTP и другие CLI форматы не исследуются заново; текущая реализация использует подтверждённый v2 SSE.",
-    "Измеренные CPU/RSS/FD и реальный proxy egress на 103 KB/6 parallel — обязательный rollout gate, не доказанный Stage 2 факт."
+    "Измеренные CPU/RSS/FD и реальный proxy egress на 103 KB/6 parallel — обязательный rollout gate, не доказанный Stage 2 факт.",
+    "ADR-0005: оформить docs/adr/0005-zen-serve-realtime-reasoning.md и обновить docs/adr/INDEX.md отдельной задачей вне замороженного handoff-architect.md §10. Текущий Read-Only Product Gate разрешает только3 run JSON, поэтому materialization=[] и ADR/product docs здесь не создаются."
   ],
   "verification_policy": {
     "surface_frozen": true,
     "verification_implementation_owner": "Stage 3 Coder пишет tests/test_realtime_reasoning.py; Stage L2 Verifier независимо запускает каждый VER с 0 failed; тесты не считаются выполненными Stage 2",
     "REQ-019_clean_room": "VER-005 проверяет digest/rollout-manifest helper на двух временных fake files внутри sandbox, не ~/.dsh. Реальная синхронизация REQ-019 проверяется только H0 после отдельного rollout; невозможно подтвердить факт deploy чистым unit-тестом.",
     "timing": "FakeClock/RNG и Event-oracles для invariants; socket arrival/CPU реальные измерения отдельными measured/heavy unittest TestCase внутри dedicated suite (stdlib-discover тоже исполняет их). Тест timing держит upstream Event закрытым до чтения 10 дельт, deadline<500ms для interarrival и<=250ms bridge overhead; timeout helper аварийно освобождает Event, чтобы assertion failure не зависала. Не подменять arrival resp.read().",
-    "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency."
+    "order": "Dedicated suite запускает selected TestStepInterruptionLive tests минимум в двух противоположных фиксированных порядках в subprocess/новых Server, включая error после budget tests; без случайных seed/dependency.",
+    "wire_fixture": "Frozen fixture literals + canonical digest в AD-001 event_contract обязаны использоваться независимым expected oracle. Изменение adapter+FakeServe одной ошибкой не должно сохранять green; corruption delta/token/permission field detection required.",
+    "strict_typing": "VER-004 all3files strict0errors, no inherited-error overlay; reportAny/reportExplicitAny server each<=125 и остальные per-rule budgets<=v1. Доказательство исполнения принадлежит clean-room L2, не этой Stage2 роли."
   },
   "high_load_envelope": {
     "schema": "HL-ENV/v1",
     "ssot": "~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/agents/architecture.md §3.0/7.2",
     "field_count": 46,
-    "units": "SI: memory B (MiB=1048576B), times s, CPU cores, rates 1/s; векторы d и s именованы канонически",
+    "units": "SSoT §3.0: memory MiB; times s, CPU cores, rates req/s or conn/s, connections/descriptors/tokens; векторы d и s по канону.",
     "required_hl_env_fields": {
       "P_steady": 1,
       "P_hpa_max": 1,
@@ -1681,9 +2159,9 @@
       "κ_skew": 1.0,
       "u_bg_worker": 0.02,
       "U_pod_sidecars": 0.25,
-      "Mem_limit_per_pod": 2147483648,
-      "Mem_rss_worker_max": 268435456,
-      "Mem_shared_max": 1207959552,
+      "Mem_limit_per_pod": 2048,
+      "Mem_rss_worker_max": 256,
+      "Mem_shared_max": 1152,
       "RPS_peak": 0.2,
       "A_max": 3,
       "SLA_p99_s": 180.0,
@@ -1725,11 +2203,11 @@
       "FD_worker": 128,
       "ulimit_n": 65536,
       "λ_new_conn_per_pod(s)": {
-        "node_ephemeral": 3.0,
+        "node_ephemeral": 3.6,
         "shared_snat": 1.8
       },
       "C_active_in_scope(s)": {
-        "node_ephemeral": 24,
+        "node_ephemeral": 30,
         "shared_snat": 12
       },
       "N_pods_in_scope(s)": {
@@ -1770,9 +2248,9 @@
       "κ_skew": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
       "u_bg_worker": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
       "U_pod_sidecars": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
-      "Mem_limit_per_pod": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
-      "Mem_rss_worker_max": "F-29 baseline RSS=22MiB; Architect увеличил design bound с 64 до 256MiB для parent queues/accumulators 6 requests; это расчётная квота, H3 измеряет.",
-      "Mem_shared_max": "F-20 idle serve=152MiB; OPEN-08 допущение 192MiB на активный child ×6=1152MiB; нагрузка ещё не измерена.",
+      "Mem_limit_per_pod": "handoff-architect §7 design budget2048MiB, normalized per SSoT§3.0/RW-011; host limit not measured, H3 mandatory.",
+      "Mem_rss_worker_max": "F-29 parent baseline22MiB; design bound256MiB; H3 actual_parent_RSS_max measured in MiB.",
+      "Mem_shared_max": "F-20 idle152MiB; design child192MiB*6=1152MiB aggregate child budget, not RSS measurement. Per-spawn XDG data preserves models path, eliminates intended shared SQLite open; H3 actual6child RSS and zero locks required.",
       "RPS_peak": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
       "A_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
       "SLA_p99_s": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
@@ -1790,10 +2268,10 @@
       "Min_healthy_ratio": "analysis/zen-realtime-reasoning/handoff-architect.md §7; оценка design envelope, не измеренный host limit/SLA; OPEN-08/09/11; перепроверить H1/H2/H3.",
       "B_retry_max": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
       "min_reserve_retry_rps": "F-11/server.py:287-314; max spawns=3, retry tokens=6, refill=.05/s, backoff=.5/2s.",
-      "FD_worker": "F-29 baseline parent36; расчёт parent ≤128 с 6 clients и ≤2 control/SSE connections per attempt + bounded stdout/stderr; child20 FD каждый (F-20) считаются отдельно, суммарно host<256.",
+      "FD_worker": "F-29 parent36; bound128 covers6 clients +18 HTTP control/SSE/delivery sockets +12 drains+6 reserve sockets/handles, per-child20FD (F-20); parent+children<256 design, actual H3.",
       "ulimit_n": "F-29 launchctl soft maxfiles=65536; не переносить значение вчерашнего reference packet=4096 как текущий факт.",
-      "λ_new_conn_per_pod(s)": "Расчёт AD-001: readiness ≤3 connect attempts, control reusable per process + 1 SSE + egress; node ≤5×RPS_peak×A_max=3/s, active≤4×6=24; shared SNAT georouter pre_send_retries≤3 =>1.8/s, active12. Не измерено; H3 validate.",
-      "C_active_in_scope(s)": "Расчёт AD-001: readiness ≤3 connect attempts, control reusable per process + 1 SSE + egress; node ≤5×RPS_peak×A_max=3/s, active≤4×6=24; shared SNAT georouter pre_send_retries≤3 =>1.8/s, active12. Не измерено; H3 validate.",
+      "λ_new_conn_per_pod(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
+      "C_active_in_scope(s)": "AD-001: <=3 readiness connects including reusable control, +1 SSE +1 prompt delivery +1 egress =6 per attempt; node<=6*.2*3=3.6conn/s; active<=5*6=30 incl client+3HTTP+egress. sharedSNAT1.8/active12 estimate unchanged; H3 validate.",
       "N_pods_in_scope(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
       "Port_range_size(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
       "T_hold_s(s)": "handoff-architect §7 локальный host (49152..65535 inclusive=16384); topology/SNAT=1 и TIME_WAIT=60s — design assumptions, внешний shared-SNAT capacity неизвестен; H3/rollout подтвердить.",
@@ -1808,7 +2286,7 @@
       "max_waiters_effective": "min(configured MAX_SLOT_WAITERS, 2*effective MAX_CONCURRENT) в общей _SlotBulkhead admission; code-default2/4, deploy6/12. Deployment6/12 unchanged, configured waiters variable не повышать.",
       "server_resource_manager": "один per-Server owner для bounded process/socket leases, после старта процесса, без parent live sockets before child exec",
       "threads_per_worker_upper_bound": 36,
-      "thread_accounting": "6 handlers +≤6 managed adapter workers/readers +≤6 stderr drains +≤6 stdin feed (run only) +≤6 gate timers +6 reserve; новые timers не пишут в wfile. Все owned threads bounded/joined; worker не порождает дополнительный бесконечный reader. Временные reader/socket leases учитываются тем же manager.",
+      "thread_accounting": "До6 handlers +6 SSE readers +6 daemon prompt delivery workers +6 bounded stdout/stderr drain workers +6 gate timers +6 reserve=36; run stdin feed заменяет serve delivery в том же attempt. Не добавлять сверх36 неучтённые workers; каждый owned socket/worker closed/joined вcleanup. HTTP leases: control + SSE + prompt delivery =3 per active serve, максимум18. Не блокировать reject behind POST.",
       "stdout_queue_max_events": 4096,
       "new_transport_queue_max_bytes": 1048576,
       "new_transport_max_sse_frame_bytes": 1048576,
@@ -1824,22 +2302,81 @@
       "client_keepalive_s": 2,
       "client_write_timeout_s": 0.5,
       "cleanup_budget_s": 1.2,
-      "ready_budget_s": 0.5,
-      "session_setup_budget_s": 0.2,
-      "startup_wait_s": 5,
-      "spawn_wait_s": 5,
+      "ready_budget_s": 3.0,
+      "session_setup_budget_s": 2.0,
       "slot_wait_s": 15,
       "spawn_rate_per_s": 1,
       "spawn_burst": 1,
       "total_deadline_s": 1800,
-      "estimate_status": "Будущие design ceilings; SLA p99=180s рабочая цель аналитика, не гарантия worst-case sum трёх generation watchdog по60s+aux. Watchdogs не повышают TIMEOUT_S; H1/H2/H3 проверяют actual p99/TTFT перед rollout."
+      "estimate_status": "Будущие design ceilings; SLA p99=180s рабочая цель аналитика, не гарантия worst-case sum трёх generation watchdog по60s+aux. Watchdogs не повышают TIMEOUT_S; H1/H2/H3 проверяют actual p99/TTFT перед rollout.",
+      "pre_spawn_admission_budget_s": 5.0,
+      "admission_policy": "_StartupGate + _SpawnRateLimiter делят один<=5.0s deadline на attempt; никакой суммы независимых5+5. Spawn token hard, gate wait fail-open только в остатке.",
+      "session_setup_scope": "POST /api/session + GET /api/event subscription armed<=2.0s до prompt; POST /prompt worker waits по first_event20/first_token60,total1800 и concurrent SSE, не по session_setup.",
+      "first_event_anchor": "serve prompt_send_start; first valid current-session execution SSE only; HTTPready/headers/control ignored; O-EXIT first_event_ms measured from request t0",
+      "data_isolation": "per-spawn tempfile XDG_DATA_HOME + finally rmtree, OPENCODE_MODELS_PATH preserved; common DB untouched",
+      "serve_health": {
+        "threshold": 3,
+        "ttl_s": 120.0,
+        "scope": "per Server/binary key, new auto requests; no model breaker protocol failures"
+      },
+      "http_sockets_per_serve_max": 3
     },
     "memory_closure_check": {
       "status": "PASS",
-      "lhs_bytes": 1476395008,
-      "rhs_bytes": 1717986918.4,
-      "substitution": "1×256MiB + 6×192MiB =1408MiB <= .80×2048MiB=1638.4MiB",
-      "evidence_level": "design estimate, не measured peak; H3 — обязательный rollout gate"
+      "unit": "MiB",
+      "lhs_mib": 1408,
+      "rhs_mib": 1638.4,
+      "substitution": "W*Mem_rss_worker_max+Mem_shared_max=1*256+1152=1408 <=0.80*2048=1638.4 MiB",
+      "evidence_level": "design estimate only; NOT measured runtime PASS",
+      "runtime_gate": "H3: actual_parent_RSS_max+6*actual_child_RSS_max<=1638.4MiB; 103KB×6×3; zero database is locked, actual cleanup dirs/FD/CPU; FAIL forbids production enable"
+    },
+    "field_units": {
+      "P_steady": "pods",
+      "P_hpa_max": "pods",
+      "maxSurge_pct": "ratio",
+      "maxSurge_abs": "pods",
+      "maxUnavailable_pct": "ratio",
+      "maxUnavailable_abs": "pods",
+      "P_terminating_overlap": "pods",
+      "P_live": "pods",
+      "P_avail_min": "pods",
+      "W": "proc/pod",
+      "N_proc": "processes",
+      "N_proc_steady": "processes",
+      "N_proc_avail_min": "processes",
+      "CPU_limit_per_pod": "cores",
+      "κ_skew": "ratio",
+      "u_bg_worker": "cores",
+      "U_pod_sidecars": "cores",
+      "Mem_limit_per_pod": "MiB",
+      "Mem_rss_worker_max": "MiB",
+      "Mem_shared_max": "MiB",
+      "RPS_peak": "req/s",
+      "A_max": "attempts/req",
+      "SLA_p99_s": "s",
+      "N_entities_max": "items",
+      "Limit_dep_share[d]": "connections",
+      "Limit_dep_rps[d]": "req/s",
+      "W_fetchers[d]": "proc/pod",
+      "J_init_s[d]": "s",
+      "J_pod_s[d]": "s",
+      "T_poll_s[d]": "s",
+      "K_calls[d]": "calls",
+      "T_base_s[d]": "s",
+      "T_cap_s[d]": "s",
+      "Max_stale_age_s[c]": "s",
+      "Min_healthy_ratio": "ratio",
+      "B_retry_max": "tokens",
+      "min_reserve_retry_rps": "req/s",
+      "FD_worker": "descriptors",
+      "ulimit_n": "descriptors",
+      "λ_new_conn_per_pod(s)": "conn/s",
+      "C_active_in_scope(s)": "connections",
+      "N_pods_in_scope(s)": "pods",
+      "Port_range_size(s)": "ports",
+      "T_hold_s(s)": "s",
+      "SNAT_ips_count(s)": "IPs",
+      "HOTPATH_MODULES": "list[str]"
     }
   },
   "resilience_gates": {
@@ -1847,8 +2384,8 @@
     "HL_ENV_v1": {
       "HL-ENV-01": {
         "status": "PASS",
-        "substitution": "46 keys и 46 field_sources; memory=1476395008 <=1717986918.4 B, оценка. N/A содержит actual diff и граф, L2 обязан повторить на Coder diff.",
-        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist.",
+        "substitution": "46 exact keys/sources/field_units SSoT§3.0; memory inMiB:1*256+1152=1408<=0.80*2048=1638.4. N/A сохраняет actual diff и transitive graph; runtime H3 NOT_RUN.",
+        "oracle": "set equality канонических 46 keys/field_sources; recompute memory; assert each N/A carries git diff and transitive proof; future Coder diff allowlist. Assert memory units exact MiB and actual H3 inequalities separately; bytes вместо MiB FAIL.",
         "verification_ids": [
           "VER-005"
         ],
@@ -1858,17 +2395,18 @@
     "C_MULT": {
       "C-MULT-I1": {
         "status": "PASS",
-        "substitution": "roles: bridge=1 process, child session lease M=6, G_reload=1 close-before-create (fallback/retry cleanup до нового child), dedicated=0; другие роли=0. georouter 6<=.60×80=48. logical DB child bound6<=.60×10=6, это не измеренная физическая sqlite connection quota; opencode внутренний pool не увеличиваем, H3 проверяет database locks. Параллельный старый/new daemon rollout запрещён (P_overlap=0).",
-        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling.",
+        "substitution": "Roles bridge=1 process, M=6 exclusive child leases, G_reload=1 close-before-create; other roles0, no daemon overlap. georouter6<=.60*80=48; opencode_local_db design logical6<=.60*10=6 НЕ физическая SQLite pool quota. Каждый child own XDG_DATA_HOME и own DB, OPENCODE_MODELS_PATH preserved, shared2.27GB DB untouched. Design memory1408<=1638.4MiB, но runtime SQLite/memory PASS только после H3 actual parent+6child<=.80*2048MiB и zero database is locked на103KB×6×3.",
+        "oracle": "FakeServe manager active_children peak<=M для retry/fallback/reload; old.closed before new.open; exact resource math для обеих declared shares; real H3 validates sqlite. Не выдавать fake logical quota за физический DB ceiling. Fake XDG dirs unique per spawn and deleted on all exits; H3 real peaks/zero locks обязательны до enable, retry не маскирует lock failure; runtime_status NOT_RUN.",
         "verification_ids": [
           "VER-005"
         ],
-        "evidence_level": "design contract; implementation oracle pending Stage3/L2"
+        "evidence_level": "design contract; implementation oracle pending Stage3/L2",
+        "runtime_status": "NOT_RUN_H3_REQUIRED"
       },
       "C-MULT-I2": {
         "status": "PASS",
-        "substitution": "Per-process manager: M=effective MAX_CONCURRENT (default2/deploy6), max_waiters<=2M (default clamp4/deploy12), wait<=15s; fixed max2 HTTP sockets/active serve (control keepalive+event), queue<=4096 events И <=1MiB, frame<=1MiB; no Redis SQL connection pool added. Общий ingress _SlotBulkhead обязан применять этот effective bound и при run, иначе default M=2/waiters12 нарушил бы 2M; не вводить вторую неучтённую очередь перед manager.",
-        "oracle": "Блокировать M+2M leases, следующий fast-fail без Popen/connect, сокетов<=2M, queue byte-overflow explicit error; inspect configured ceilings. Нельзя снижать общий production slot count или повышать max_waiters.",
+        "substitution": "Per-process manager: M=effective MAX_CONCURRENT (default2/deploy6), max_waiters<=2M (default clamp4/deploy12), wait<=15s; fixed max3 HTTP sockets/active serve (reusable control+event+prompt delivery), queue<=4096 events И <=1MiB, frame<=1MiB; no Redis SQL connection pool added. Общий ingress _SlotBulkhead обязан применять этот effective bound и при run, иначе default M=2/waiters12 нарушил бы 2M; не вводить вторую неучтённую очередь перед manager.",
+        "oracle": "Блокировать M+2M leases, следующий fast-fail без Popen/connect, сокетов<=3M, queue byte-overflow explicit error; inspect configured ceilings. Нельзя снижать общий production slot count или повышать max_waiters.",
         "verification_ids": [
           "VER-005"
         ],
@@ -1894,7 +2432,7 @@
       },
       "C-MULT-I5": {
         "status": "PASS",
-        "substitution": "Parent FD128<=.70×65536=45875.2; parent+6 children20FD<256 host descriptors. node ports:3×1×60+24=204<=8192; shared SNAT:1.8×1×60+12=120<=8192. Ceilings из field_sources — estimates; keepalive control reuse, readiness attempts<=3; close before next spawn.",
+        "substitution": "ParentFD128<=.70*65536=45875.2; parent+6children20FD<256 design. control+SSE+prompt=3HTTP sockets per child. node ports3.6*1*60+30=246<=8192; sharedSNAT1.8*1*60+12=120<=8192. Readiness<=3 connects; control reusable. Actual FD/RSS/cleanup/network closure H3 mandatory.",
         "oracle": "Recompute both scope inequalities, count control connection creation/reuse (50 operations on one owned serve lease ->1 keepalive control TCP), readiness≤3 probes; leak counters FD/start/end stable; H3 измеряет реальные FD/egress.",
         "verification_ids": [
           "VER-005"
@@ -1905,7 +2443,7 @@
     "S_HERD": {
       "S-HERD-I1": {
         "status": "PASS",
-        "substitution": "Snapshot/config startup/poll path absent: W_fetchers=0,K_calls=0 => batch K×(λ+4sqrtλ+4)=0<=.5×1=.5 и R_poll=0<=.2×1=.2. 1/s field — self-configured request spawn rate, НЕ неизвестная квота dependency; запрещено объявлять gate PASS через фиктивную внешнюю RPS. Request cold-start отдельно ограничен gate<=5s wait/12s hold + token bucket1/s burst1 для КАЖДОГО child включая fallback.",
+        "substitution": "Snapshot/config startup/poll path absent: W_fetchers=0,K_calls=0 => batch K×(λ+4sqrtλ+4)=0<=.5×1=.5 и R_poll=0<=.2×1=.2. 1/s field — self-configured request spawn rate, НЕ неизвестная квота dependency; запрещено объявлять gate PASS через фиктивную внешнюю RPS. Request cold-start отдельно ограничен combined gate+token admission<=5.0s (gate hold<=12s, не additive wait) + token bucket1/s burst1 для КАЖДОГО child включая fallback.",
         "oracle": "AST/transitive no backend poller; zero background I/O при idle; FakeClock spawn bucket max B+r*T; ≥6 parallel requests не делают 6 Popen одновременно. Startup gate release first validated event/own EOF/max hold, cancellation-safe.",
         "verification_ids": [
           "VER-005"
@@ -2013,7 +2551,7 @@
       },
       "H-CPU-I2": {
         "status": "PASS",
-        "substitution": "Regex compiled at import; нет per-delta json.loads правил/конфигов, model_validate/deepcopy/static label binding. json.loads одного входного SSE frame необходим для transport framing и не является forbidden config reload parse. Deny config merge один раз per attempt setup вне delta loop.",
+        "substitution": "Regex compiled at import; нет per-delta json.loads правил/конфигов, model_validate/deepcopy/static label binding. json.loads одного входного SSE frame необходим для transport framing и не является forbidden config reload parse. Serve ask_reject/deny config merge один раз per attempt setup вне delta loop.",
         "oracle": "Спай на re._compile/config decoder/model_validate/typeadapter/deepcopy/static labels в delta loop ->0; wire decoder count==one per actual event, не full history; tool JSON parser exempt by input decoding purpose.",
         "verification_ids": [
           "VER-005"
@@ -2022,8 +2560,8 @@
       },
       "H-CPU-I3": {
         "status": "PASS",
-        "substitution": "Первый guard optional serve branch проверяет realtime flag до UUID/password/clock/serve queue/threads/probe. flag=false -> прежний run O(1) transport-selection branch; watchdog/status — отдельное исправление RC2/RC3 для обоих транспортов, не скрытая serve allocation. У status helper первый guard thinking-enabled/SSE до форматирования/часов. Включённые data queues bounded put_nowait; overflow model events=explicit error+kill, не silent telemetry drop; optional telemetry drop increments dropped_total.",
-        "oracle": "Flag=false spies serve allocator, password, UUID, probe, threads=0. Full bounded event queue->explicit overflow+cleanup, без ожидания; optional product event queue drop fail-open. status flag guard не отключает стандартные legacy errors.",
+        "substitution": "Первые serve guards: if disabled or TRANSPORT=run return legacy до UUID/password/clock/queue/threads/probe. Enabled selector проверяет O(1) os.path.exists(disable-file); present ->run до serve allocations/subprocess. auto health-degraded/shebang ->run без probe. Default=true native path не отменяет zero-serve-cost explicit disabled path; legacy watchdog/status остаются RC2/RC3 fixes. Status guard thinking+SSE до format; bounded put_nowait events, overflow explicit error+cleanup; optional telemetry drop counters.",
+        "oracle": "VER-005 spy explicit0/run/disable-file ->0 serve alloc/password/probe/extra Popen; while same process create/remove file next request toggles transport. Queue overflow explicit cleanup; no disabled UUID/serialization. File stat O(1), no recursive IO.",
         "verification_ids": [
           "VER-005"
         ],
@@ -2064,8 +2602,8 @@
     "R_BULK": {
       "R-BULK-I1": {
         "status": "PASS",
-        "substitution": "Slot один раз15s + Amax3×(gate5+spawn-token5+ready.5+session-control.2+cleanup1.2)+backoff caps1+2 =53.7s<=.30×180=54s. Generation model wait отделён от auxiliary: first-event20, first-token60, stall60, TIMEOUT1800 общий. Каждый HTTP/control/session operation получает min(operation_budget,remaining); cleanup имеет отдельный финальный потолок1.2s, не skip при истёкшем request. После deadline ни spawn, ни prompt, ни sleep.",
-        "oracle": "FakeClock recompute53.7<=54; exhaust setup subbudget and total deadline before each I/O ->zero further calls. Контроль setup aggregate .2s, ready.5s, cleanup1.2s (не сумма отдельных безлимитных вызовов). При снижении SLA/увеличении budget формула обязана стать FAIL до rollout.",
+        "substitution": "15.0 + 3 * (5.0 + 3.0 + 2.0 + 1.2) + 3.0 = 51.6 s <= 0.30 * 180 = 54.0 s; headroom=2.4s. Slot15 один раз, combined pre-spawn admission5 на attempt, owner/ready3, create+subscribe2, cleanup1.2, суммарный backoff cap1+2=3. Prompt POST/generation под first_event20/first_token60/stall60 и total1800, не session_setup. Каждому I/O timeout=min(phase_remaining,request_remaining); cleanup финальный<=1.2 даже после request deadline. После deadline ни spawn/prompt/sleep.",
+        "oracle": "FakeClock recompute51.6<=54 и headroom>=2.0; admission gate+limiter sum<=5.0, ready3/create+subscribe2/cleanup1.2, prompt POST не входит в2s; slow create timeout ->one budgeted run pre-header; headers received or session event ->zero silent run, Popen<=3. Deadline exhausted->zero further I/O. Никаких leftover gate5+spawn5/ready.5/setup.2.",
         "verification_ids": [
           "VER-005"
         ],
@@ -2082,8 +2620,8 @@
       },
       "R-BULK-I3": {
         "status": "PASS",
-        "substitution": "Existing breaker threshold5,cooldown10×U(.8,1.2),HALF_OPEN=1. Watchdog/provider transient отмечаются attempt_done+commit; recovered success не накапливает pending failure. Bridge log fail-open, startup lock timeout fail-open; secret/auth/permission/unknown accepted prompt fail-closed. В baseline _UpstreamBreaker.allow lease пробы истекает по reset_s даже при ещё активном request (server.py:1415-1428); новый contract не разрешает вторую active HALF_OPEN пробу. Владение probe завершает success/failure или подтверждённый cancel/cleanup; время cooldown не освобождает живую пробу само.",
-        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret.",
+        "substitution": "Model _UpstreamBreaker threshold5/cooldown10*U(.8,1.2), HALF_OPEN1 owner не освобождается по одному cooldown до terminal/cleanup; provider failures/успешное восстановление как прежде. Отдельный _ServeHealth threshold3/TTL120/one recovery probe для serve protocol-only failures; first_event_timeout без session execution и invalid_serve_event НЕ model breaker failure, subsequent auto->run. Accepted current prompt не получает silent run fallback. Auth/permission/security401/403 fail-closed, no policy switch; client cancel neutral. TTL/run skips не продлевают outage; native binary key change инвалидирует capability/health. Resource/retry/slot caps едины.",
+        "oracle": "После5 failing requests OPEN без connect/spawn; FakeClock до cooldown десять concurrent HALF_OPEN ->ровно1 probe. Продвинуть clock ещё на>reset_s при заблокированной первой пробе: allow для остальных остаётся false. После owner cleanup проба освобождена и следующая ровно одна разрешена. fake401/403 не запускает run fallback и не выдаёт secret. Отдельно five serve-protocol failures forced mode ->model breaker closed, no .failure calls; auto third failure arms120s,next auto run, no silent replay current request; atTTL exactly1probe, success resets, failed protocol rearms120; provider5 failures still open model breaker.",
         "verification_ids": [
           "VER-005"
         ],
@@ -2136,15 +2674,15 @@
     },
     "T_LIFE_v1": {
       "status": "PASS",
-      "substitution": "Request/attempt ownership включает PGID, stdout/stderr, SSE/control sockets, session id, queue/readers и startup gate. AD-003 cleanup на всех exits<=1.2s, child group reap; leader early-exit не оставляет grandchildren. Server shutdown manager запрещает новые leases и отменяет все активные, затем closes all.",
-      "oracle": "VER-005: 50 cancellations + leader-exits-first descendant + blocked socket/readiness + partial prompt + overload/shutdown; zero active/waiters/children/readers/sockets; PIDs/PGIDs только свои.",
+      "substitution": "Request/attempt ownership включает PGID, stdout/stderr, SSE/control sockets, session id, queue/readers и startup gate. AD-003 cleanup на всех exits<=1.2s, child group reap; leader early-exit не оставляет grandchildren. Server shutdown manager запрещает новые leases и отменяет все активные, затем closes all. Ownership включает isolated XDG_DATA_HOME и daemon delivery socket/thread; finally rmtree owned dir после kill/reap, never common DB. Foreign listener cleanup no API/kill to foreign PID.",
+      "oracle": "VER-005: 50 cancellations + leader-exits-first descendant + blocked socket/readiness + partial prompt + overload/shutdown; zero active/waiters/children/readers/sockets; PIDs/PGIDs только свои. Assert unique data dirs and deleted after all50 cancellations/partial prompt/port race; join delivery reader and no owned temp dirs.",
       "verification_ids": [
         "VER-005"
       ]
     },
     "O_EXIT_v1": {
       "status": "PASS",
-      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется.",
+      "substitution": "Один O-EXIT/v1 до любого early return имеет mode/model/status, transport/first_event_ms/ttft_ms (null допустим до event), exit_reason, retries,total_spawns,duration; code first_event_timeout/first_token_timeout/stall_timeout/client_gone не теряется. first_event_ms только valid current-session execution SSE после prompt, относительно request t0; HTTPready/POST headers не являются first_event. transport_history/reason раздельно protocol/model/security/TTL, no phantom spawns.",
       "oracle": "VER-005 table all exits incl 400/401/404/503/circuit, overflow, error, abort, successful retry; deterministic fake clock, no secret reflection.",
       "verification_ids": [
         "VER-005"
@@ -2176,31 +2714,31 @@
       {
         "dependency_operation": "serve/readiness + session init",
         "path": "hot/aux",
-        "timeout_budget": "aggregate ready<=.5s, create+event-subscription+prompt-send<=.2s, capped remaining",
-        "bulkhead": "manager leases<=M, control+SSE<=2M",
-        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
-        "failure_mode_fallback": "Capability unavailable before prompt in auto -> fully cleaned run retry; auth/security fail-closed, forced serve explicit error; once prompt starts no silent fallback"
+        "timeout_budget": "Owner proof+GET /api/session/active aggregate ready<=3.0s (cache-miss schema внутри3); POST session+GET event armed<=2.0s; POST prompt excluded, concurrent SSE/watchdogs",
+        "bulkhead": "manager leases<=M, control+SSE+prompt delivery<=3M sockets",
+        "circuit_breaker": "_ServeHealth3/TTL120/probe1 for protocol; _UpstreamBreaker5 for provider; auth/permission fail-closed",
+        "failure_mode_fallback": "Auto ServeUnavailable до POST prompt response headers и до current-session execution event ->cleanup+budgeted run. Headers OR event latch delivered; then no silent run.401/403/permission missing never fallback."
       },
       {
         "dependency_operation": "opencode model execution (serve or run)",
         "path": "hot",
-        "timeout_budget": "first-event20, first-token60, stall60, request TIMEOUT1800 common",
+        "timeout_budget": "Serve first-event20/first-token60 от prompt_send_start; stall60 от useful token; requestTIMEOUT1800 common. HTTP readiness отдельно<=3 и не гасит first_event.",
         "bulkhead": "_slots effectiveM, waiters<=2M, one child per slot",
-        "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
-        "failure_mode_fallback": "Watchdog/transient -> cleanup + retry budget/jitter; no retry client_gone or fatal4xx; final explicit error even after partial output"
+        "circuit_breaker": "Provider _UpstreamBreaker5/jitter/HALF_OPEN1; serve-specific invalid/no-event ->_ServeHealth3/TTL120 only",
+        "failure_mode_fallback": "Watchdog ->cleanup+same-transport explicit budgeted retry; accepted current request never silent run. Protocol degradation directs NEW auto requests to run; fatal4xx/security/cancel no retry."
       },
       {
         "dependency_operation": "_StartupGate/_SpawnRateLimiter",
         "path": "hot/aux",
-        "timeout_budget": "wait<=5 each, hold<=12; cancel poll<=.25",
+        "timeout_budget": "Shared pre-spawn admission<=5.0s total (gate wait only remaining after hard token); hold<=12 not additive, cancel poll<=.25",
         "bulkhead": "1 gate, token bucket1/s burst1",
         "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
-        "failure_mode_fallback": "Gate timeout fail-open as legacy; rate limiter not bypassed, every real child counted"
+        "failure_mode_fallback": "Gate wait fail-open лишь в оставшемся5s; token timeout prohibits spawn, limiter never bypassed. No independent5+5 waits."
       },
       {
         "dependency_operation": "serve interrupt/delete and process cleanup",
         "path": "cleanup",
-        "timeout_budget": "interrupt+delete aggregate<=.2, TERM grace<=.5, reap/join<=.5; total1.2",
+        "timeout_budget": "interrupt+delete<=.2,TERM grace<=.5,reap/join delivery+SSE+owned rmtree within remaining .5; total<=1.2, bounded even on deadline",
         "bulkhead": "only own session/PGID, no new leases",
         "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
         "failure_mode_fallback": "Best effort API failure never skips socket close/killpg; force SIGKILL, idempotent cleanup"
@@ -2220,6 +2758,14 @@
         "bulkhead": "existing _LOG_LOCK",
         "circuit_breaker": "_UpstreamBreaker5/10×U(.8,1.2)/HALF_OPEN1 для model failure; local capability и cleanup не provider failure",
         "failure_mode_fallback": "Fail-open OSError; не добавлять synchronous remote logger на request path"
+      },
+      {
+        "dependency_operation": "serve permission rejection",
+        "path": "hot/control",
+        "timeout_budget": "Immediate control reply<=.25s capped request/phase remaining, never queued behind prompt response",
+        "bulkhead": "Use one idle control connection; delivery worker uses separate bounded prompt socket, <=3 sockets per active serve",
+        "circuit_breaker": "Security fail-closed, not model/protocol fallback",
+        "failure_mode_fallback": "permission.asked ->decision=reject; missing endpoint/bad reply401/403 ->cleanup+explicit error; never allow/once/always"
       }
     ],
     "non_waivable_stop_codes": [
@@ -2399,7 +2945,7 @@
     },
     "NON_IDEMPOTENT_RETRY": {
       "status": "PASS",
-      "rationale": "Built-ins deny/ask-auto-reject никогда не исполняются; при неизвестной доставке prompt не silent fallback. Повтор может дублировать reasoning, имеет отдельный status; tool ids/key dedup.",
+      "rationale": "ask_reject/deny never allow; explicit brief chooses responseheaders OR sessionexecution deliverybarrier. Beforebarrier unknown delivery may fallback only after ownedcleanup/cap; afterbarrier only explicit same-transport retry+status, never silentrun. Not exactly-once; tool IDs dedup.",
       "verification_ids": [
         "VER-005"
       ],
@@ -2444,26 +2990,27 @@
     "waiting": "[мост] Ожидание первого токена (10 с)…\n"
   },
   "handoff_state": {
-    "architecture_contract": "Stage2 approved-phase candidate; не ARCH_GATE_PASS, не council verdict",
+    "architecture_contract": "Cycle2 fix-from-panel candidate APPROVED; 14 RW+7 FU resolved at design level, R2 council verdict и ARCH_GATE не выносятся этой ролью",
     "implementation_tests": "NOT_RUN — код/tests Stage3 ещё не создавались",
     "live_acceptance": "NOT_RUN — H0..H9 отдельно; не менять ~/.dsh",
     "pending_orchestrator_actions": [
-      "validate_arch_gate/внесение packet hash в task envelope",
-      "external architecture panel и verify_panel_proof PASS перед Coder",
-      "Stage3 Coder и clean-room L2 VER001..005",
-      "rollout H0..H9"
+      "Council R2 по diff v1→v2 и rework_resolutions; отдельные launch_seat/verify_panel_proof",
+      "Обновить task envelope packet/surface hashes и проверить ARCH_GATE с новыми role-plan/fingerprints (вне трёх разрешённых файлов роли)",
+      "Stage3 Coder, independent clean-room strict VER001..005",
+      "H3/H6 safety gates до production sync; H0..H9 live acceptance, ещё NOT_RUN"
     ]
   },
   "verification_acceptance_matrix": {
-    "FakeServe": "stdlib subprocess fake implements serve argv, HTTP Basic401, GET /openapi.json and /api/event, POST session/prompt/interrupt, DELETE, permission request/reject. Tests set flag=true and transport=serve, so shebang auto compatibility does not skip real serve path. Hold upstream Event after first deltas, client readline sees data before release. No real model/Zen calls.",
+    "FakeServe": "Stdlib subprocess implements exact frozen_v2_1_2_fixtures API/SSE, Basic401, /api/session/active, /openapi.json only per binary-key first handshake, session/prompt/interrupt/delete/permission decision=reject. Tests force serve for shebang; no Zen calls. Independent fixed fixture digest oracle + deliberate field/schema mutations; fake/adapter mutual agreement alone insufficient. GET active returns {data:{}} not[]; once-per-key /api/info version+PID and API schema info.version0.0.1, independent binary appversion2.1.2; invalid numeric error.status must fail validation.",
     "mode_matrix": [
-      "flag=false, auto/serve/run -> run, no serve allocation or Popen",
-      "flag=true, run ->run",
-      "flag=true, auto, legacy shebang ignores argv ->run once directly, counter1, stdin promptEOF",
-      "flag=true, serve, FakeServe shebang ->full SSE v2; both JSON and stream",
-      "flag=true, serve, fake legacy blocking stdin ->DEVNULL gives immediate EOF; ready failure<=.5s, explicit error, no5s hang",
-      "flag=true, auto, binary unsupported/ready failure -> cleanup then run only pre-prompt, all Popen total<=3; exhausted budget stops",
-      "serve401/permission failure/unknown prompt delivery/client_gone -> no silent fallback"
+      "default flag=true+auto+native MachO ->serve после safety rollout; shebang fake ->run once no probe, all378baseline existing tests target green",
+      "explicit flag0/false or TRANSPORT=run ->run before serve allocations/stat/probe; enabled disable-file present ->run after one O(1)exists; create/remove file same process toggles next request without restart",
+      "force serve+FakeServe shebang ->v2 SSE/JSON, stdinDEVNULL; fake legacy blocking stdin ->EOF/ready failure<=3s explicit no silent run",
+      "auto ServeUnavailable in spawn/create/subscribe or pre-response-headers prompt and no execution SSE ->complete cleanup then1budgeted run fallback; totalPopen<=3",
+      "POST prompt headers arrived OR valid session execution SSE while headers pending ->delivered; zero silent run, remaining first-event/token clocks active; explicit security401/403/cancel no fallback at any phase",
+      "Default ask_reject, env deny both frozen permission rules; unsupported policy/missing safe endpoints fail-closed, no automatic policy switching",
+      "Auto _ServeHealth3protocol failures ->TTL120 run new requests; provider breaker remainsclosed for protocol-only, provider failures remain independent",
+      "Compare frozen immutable_run_env function SHA256, tests/test_run_env.py/start.sh SHA256; preserving tests by editing expected hashes запрещено."
     ],
     "status_matrix": [
       "slow blank upstream + startup-gate/rate-wait: grace.30 first [мост] LF<=1s",
@@ -2472,14 +3019,16 @@
       "whitespace/empty comments/status do not set first-token or attempt_output",
       "retry accepted after model reasoning: exactly one retry status, raw model bytes retained, no reasoning dedup",
       "normal127ms model reasoning: no periodic status, natural LF enables collapsed preview, no newline injected into model delta",
-      "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes"
+      "split interrupted marker filtering and split UTF8 must preserve all ordinary model bytes",
+      "Model reasoning chunk без trailingLF ->synthetic delta \"\\n[мост] ...\\n\"; whole delta incl leading LF provenance=synthetic, model-only concatenation exact bytes, literal model [мост] survives; LF already present->no redundant prefix; fast Simple greeting.->zero statuses."
     ],
     "watchdog_matrix": [
-      "first_event_timeout on silent legacy after process spawn and on fake serve event-less execution when no valid readiness/server event",
-      "first_token_timeout on repeated started/control/keepalive events with no non-whitespace model token",
-      "stall_timeout after first real model delta, comments/bridge statuses do not reset it",
-      "first-event may be satisfied by valid serve readiness: an authenticated ready server with zero model tokens must timeout via first_token, not fabricate first_event failure",
-      "all thresholds env configurable, tiny values/FakeClock; shared total deadline never resets; no retry4"
+      "Serve HTTP ready success + accepted prompt headers but zero session SSE ->first_event_timeout at20s from prompt_send_start +cleanup<=1.2 (<22s); first_event_ms remainsnull",
+      "Legacy first-event from attempt start until first valid run event/step_start; serve ready3 and create+subscribe2 bounded independently before prompt",
+      "Current session execution.started/step.started/reasoning.started SSE after prompt satisfies first_event once; first_event_ms=request-relative; foreign sessions/pre-prompt started/server.connected/session.created/comments/status do not satisfy",
+      "Valid started/control but no useful model token ->first_token_timeout60s; started/control/comments/reject not token, no indefinite reset",
+      "After first useful model delta pause>stall60 ->stall_timeout; comments/bridge statuses/repeated transport noise do not reset",
+      "POST prompt delivery blocked past2s while SSE progresses is permitted; supervisor/reader/writer concurrent and cancel-aware, no duplicate prompt; request totaldeadline neverreset, no retry4"
     ],
     "lifecycle_matrix": [
       "disconnect at gate/limiter/ready/prompt/blocked SSE/after reasoning, detect<=5s and PGID absent<=7s",
@@ -2487,7 +3036,9 @@
       "SIGTERM ignored ->SIGKILL, leader reaped, no child/grandchild",
       "success/tool step/error/fallback/shutdown each closes session/socket/threads/slot once",
       "byte queue/frame/output overflow explicit error (no silent model delta loss)",
-      "50 cancel fault-injection cycles counters in_use/waiters/sessions/sockets/readers=0"
+      "50 cancel fault-injection cycles counters in_use/waiters/sessions/sockets/readers=0",
+      "Foreign listener PID/PGID after reserve-release ->zero Authorization/password/prompt bytes, no foreign API/kill; bounded port retry ready3s and totalspawns<=3.",
+      "Unique per-spawn XDG_DATA_HOME across6parallel/retries; _run_env bytehash unchanged, OPENCODE_MODELS_PATH retained; finally tempdir removed after all exits, 50cancel cycles and deliveryworker cleanup."
     ],
     "tools_matrix": [
       "every split point and single-char deltas for both tags, JSON embedded close strings/code quoting existing fixtures",
@@ -2496,7 +3047,9 @@
       "native call lifecycle normalized/dedup per call-id, mapped/unmapped behavior identical; no auto allow",
       "step.ended tokens input/output/cached/reasoning counted once then tool finish, no followup synthetic step",
       "early legacy error may recover; late transient/fatal error and incomplete recovery same on fake v2",
-      "existing reasoning_interrupted and interrupted cleanup across delta boundaries"
+      "existing reasoning_interrupted and interrupted cleanup across delta boundaries",
+      "permission.asked {data.id,sessionID,action,resources,source} ->POST reply {decision:reject},status204; both ask_reject/deny modes; POST prompt may stayblocked while reject executes on separate control socket; never once/always/allow.",
+      "Frozen wire tokens.cache.read/write ->canonical tokens{input,output,cached=cache.read,reasoning}; mutate delta path/cache envelope/permission lifecycle ->independent oracle fail, step assistantMessageID dedup, not invented wire stepID."
     ],
     "baseline_matrix": [
       "two original budget fixtures:3 spawns, no fourth tool result, stop; separate fixture unmapped->incomplete->calls within3 proves counter separation",
@@ -2509,20 +3062,398 @@
       "new process/socket resource manager singleton and bounded lease count, 50 control keepalive operations1 connection per lease",
       "RPS token bucket/cancel/full jitter/retry budget/breaker HALF_OPEN1 via FakeClock/RNG",
       "wire event JSON decode allowed; config decode/re.compile/reparse-full-history on per-delta hot path forbidden",
-      "HALF_OPEN active probe held across reset_s boundary: zero second probes until owner cleanup; common _SlotBulkhead code-default M2/waiters4 and deploy M6/waiters12, no second uncounted ingress queue."
+      "HALF_OPEN active probe held across reset_s boundary: zero second probes until owner cleanup; common _SlotBulkhead code-default M2/waiters4 and deploy M6/waiters12, no second uncounted ingress queue.",
+      "Combined gate+limiter5,ready3,create+subscribe2,cleanup1.2;15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; slowcreate->one preheader run; afterheader/event->no run; no fourthPopen.",
+      "_ServeHealth force5protocol failures ->zero model breakerfail; auto3failures->next run untilTTL120, expiry oneprobe, successful terminalreset, protocolfailrearm; binarymtime+size change invalidates capability; real provider5 failures modelbreakerOPEN.",
+      "Memory SSoT fields2048/256/1152 MiB exactly; design1408<=1638.4 not H3PASS.3HTTP sockets per serve supports immediate reject while promptHTTP pending; recalc nodeports246<=8192."
     ],
-    "rollout_boundary": "VER001..005 не обращаются к ~/.dsh. В root suite test_dsh_profile_config видит отсутствие live profile в clean-room и делает inherited skip. Actual REQ019 identity и H0..H9 отдельный rollout gate; fake digest fixture не подменяет read-back deployed file."
+    "rollout_boundary": "VER001..005 не обращаются к ~/.dsh. В root suite test_dsh_profile_config видит отсутствие live profile в clean-room и делает inherited skip. Actual REQ019 identity и H0..H9 отдельный rollout gate; fake digest fixture не подменяет read-back deployed file. Default=true не bypass: pre-production candidate H3/H6 mandatory, file disabled until safety PASS; H3 actualRSS + no DB locks103KB×6×3. H9 toggles file withoutrestart in existing chat. All H NOT_RUN in Stage2."
   },
   "semantic_checks": {
-    "canonical_hl_field_set": "46/46 exact key equality and field_sources equality against team architecture.md §3.0",
+    "canonical_hl_field_set": "46/46 exact key equality and field_sources/field_units equality against team architecture.md §3.0",
     "stop_codes": "21 main codes + T-LIFE/O-EXIT/M-SEM=24 unique",
     "legacy_antipatterns": "21 exact keys from approved reference schema",
     "verification_owner": "5/5 owner=verifier",
     "decisions": "4/4 two-way with >=2 genuine alternatives",
-    "evidence_refs": "61 unique EVD IDs; decision/assumption references checked; EVD061 identifies existing HALF_OPEN and default waiter gaps.",
-    "VER-004_syntax": "ast.parse PASS; actual future command pending test file Stage3",
-    "status_protocol": "3/3 examples begin [мост], end actual LF",
-    "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes."
+    "evidence_refs": "64 unique EVD IDs; analyst49 F-01..F-49 неизменны; council refs отдельный PANEL-F-NNN namespace; invalid analyst refs запрещены.",
+    "status_protocol": "3 templates begin[мост]/endLF; при model unterminated line весь дополнительный leading LF synthetic, template bytes модели не менять.",
+    "schema_vs_semantics": "Installed packet validator does not inspect high_load_envelope/resilience_gates/legacy checks; above explicit semantic assertions supplement it. Neither schema nor design assertions prove runtime passes.",
+    "VER_004_syntax": "Strict command compiled with ast.parse in cycle2; execution pending Stage3 because new test file absent",
+    "rework_coverage": "14RW+7FU exactly once in rework_resolutions; source_findings uses PANEL-F-NNN; resolved means architecture delta, NOT implementation/runtime PASS",
+    "memory_units": "All46 canonical keys+field_sources+field_units; memory2048/256/1152 MiB;1408<=1638.4MiB",
+    "aux_budget": "15+3*(5+3+2+1.2)+3=51.6<=54,headroom2.4; old independent5+5/.5/.2 absent",
+    "wire_evidence": "Actual binary2.1.2 permission.asked/decision=reject and cache.read/write normalized explicitly; fixture SHA256 locked; five families independent adapter/mock oracle Readiness data map and appversion/api schema version separated; StructuredError.status numeric mapping frozen."
   },
-  "routing_profile": "standard"
+  "routing_profile": "standard",
+  "panel_resolution_choices": [
+    {
+      "ids": [
+        "RW-001",
+        "RW-007"
+      ],
+      "source_positions": [
+        "PANEL-F-001: headers response barrier",
+        "RW-001.evidence: Seat2 начало POST barrier"
+      ],
+      "resolution": "Текущий explicit user brief выбирает response headers OR started session event; unknown pre-header delivery может fallback только после полного cleanup; after-header no silent run. Admission/create budgets отделены от prompt wait."
+    },
+    {
+      "ids": [
+        "RW-002"
+      ],
+      "source_positions": [
+        "PANEL-F-002: допускается один safe policy transition до prompt",
+        "PANEL-F-018: unsupported policy fail-closed без auto-switch"
+      ],
+      "resolution": "Default ask_reject и явный env deny, автоматического переключения НЕТ вообще. После accepted401/403 fatal; live H6 обязателен."
+    },
+    {
+      "ids": [
+        "RW-006",
+        "RW-009"
+      ],
+      "source_positions": [
+        "PANEL-F-006: H3 обязателен до включения",
+        "PANEL-F-010: default=true без start.sh"
+      ],
+      "resolution": "Default=true сохранён в коде design; candidate H3/H6 до production sync, боевой file switch удерживается до допуска. Нельзя сначала включить default, а потом искать RSS."
+    },
+    {
+      "ids": [
+        "RW-011",
+        "RW-012"
+      ],
+      "source_positions": [
+        "PANEL-F-012: канон MiB, byte арифметика недостаточна",
+        "PANEL-F-013: strict0error вместо старого allowance"
+      ],
+      "resolution": "MiB exact values; type allowance удалён; существующие2errors — baseline debt для исправления Coder в server.py, не текущий PASS."
+    },
+    {
+      "ids": [
+        "RW-004",
+        "RW-007"
+      ],
+      "source_positions": [
+        "Brief logical session.permission.requested/tokens.cached",
+        "EVD-062 actual v2.1.2 permission.asked/tokens.cache.read+write; permission reply decision"
+      ],
+      "resolution": "Freeze actual wire literals и canonical expected mapping, не изобретать отсутствующие поля/имена. Group labels сохранены в fixture families для механического verify-fixed."
+    }
+  ],
+  "rework_resolutions": [
+    {
+      "id": "RW-001",
+      "source_findings": [
+        "PANEL-F-001"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Pre-header fallback + session-event earlier barrier, explicit unknown-delivery risk and same-transport retries. create/subscribe budget separated from concurrent POST generation, cap3 unchanged.",
+      "packet_locations": [
+        "#/decisions/0/details/fallback_barrier",
+        "#/decisions/0/details/session_wire",
+        "#/resilience_gates/R_BULK/R-BULK-I1",
+        "#/verification_acceptance_matrix/mode_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-002",
+      "source_findings": [
+        "PANEL-F-002",
+        "PANEL-F-007",
+        "PANEL-F-018"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Default ask_reject, env deny, _serve_env over byte-identical _run_env; decision=reject only, missing capability/401/403 fail-closed, no automatic policy transition.",
+      "packet_locations": [
+        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY",
+        "#/decisions/0/details/tool_policy",
+        "#/risks/0",
+        "#/threat_model/threats/1"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-003",
+      "source_findings": [
+        "PANEL-F-003"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Parent bind0/reserve/release-before-Popen explicitport; lsof PID/PGID proof before Authorization/prompt, foreign listener zero leakage/own cleanup and bounded retry.",
+      "packet_locations": [
+        "#/decisions/0/details/listener_ownership",
+        "#/decisions/0/details/spawn",
+        "#/threat_model/threats/0",
+        "#/verification_acceptance_matrix/lifecycle_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-004",
+      "source_findings": [
+        "PANEL-F-004"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Five frozen fixture families with exact source-proven field paths+canonical expectation+SHA256; actual wire permission.asked, reply decision and tokens.cache.read normalized, not invented aliases.",
+      "packet_locations": [
+        "#/decisions/0/details/event_contract",
+        "#/evidence/61",
+        "#/verification_policy/wire_fixture"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-005",
+      "source_findings": [
+        "PANEL-F-005"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "REQ-013/AD-001/RISK-002 guarantee only per-spawn proxy-env rotation AC-018; loopback georouter NO_PROXY bypasses child HTTP_PROXY, no guaranteed clean Zen IP.",
+      "packet_locations": [
+        "#/requirements/12",
+        "#/decisions/0/drivers",
+        "#/risks/1"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-006",
+      "source_findings": [
+        "PANEL-F-006"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Per-spawn XDG_DATA_HOME+preserved OPENCODE_MODELS_PATH+finally rmtree, H3 actualRSS parent+6children<=1638.4MiB/zero DB locks103KB×6×3; no Stage2 runtime PASS.",
+      "packet_locations": [
+        "#/decisions/0/details/data_isolation",
+        "#/high_load_envelope/memory_closure_check",
+        "#/resilience_gates/C_MULT/C-MULT-I1",
+        "#/evolution/H3_rollout_gate"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-007",
+      "source_findings": [
+        "PANEL-F-008"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Lightweight active-session readiness3s; combined admission5s; create+subscribe2s; daemon POST delivery concurrent SSE; exact Model.Ref/providerID/id/variant and session permissions array; total51.6<=54.",
+      "packet_locations": [
+        "#/decisions/0/details/startup",
+        "#/decisions/0/details/admission",
+        "#/decisions/0/details/session_wire",
+        "#/high_load_envelope/operational_profile",
+        "#/resilience_gates/dependency_failure_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-008",
+      "source_findings": [
+        "PANEL-F-009"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Serve first_event20 only current-session execution SSE after prompt; HTTP readiness/headers ignored; independent clocks and request-relative first_event_ms, accepted-noevents timeout<=22s.",
+      "packet_locations": [
+        "#/decisions/2/details/clocks",
+        "#/decisions/2/details/telemetry",
+        "#/verification_acceptance_matrix/watchdog_matrix",
+        "#/resilience_gates/O_EXIT_v1"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-009",
+      "source_findings": [
+        "PANEL-F-010"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Default=true+auto native, shebang directrun all378baseline target; file disable no restart. Candidate H3/H6 before prod sync+held disable-file reconciles mandatory safety gate.",
+      "packet_locations": [
+        "#/decisions/0/details/configuration",
+        "#/decisions/0/details/auto_fake_compatibility",
+        "#/evolution/rollout",
+        "#/evolution/feature_flag"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-010",
+      "source_findings": [
+        "PANEL-F-011",
+        "PANEL-F-016"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Tool-policy reference corrected to EVD-050+F-08; analyst IDs restricted49 facts, council refs PANEL-F-NNN.",
+      "packet_locations": [
+        "#/decisions/0/details/tool_policy",
+        "#/evidence/49",
+        "#/semantic_checks/evidence_refs"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-011",
+      "source_findings": [
+        "PANEL-F-012"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "SSoT46 exact fields/sources/units, memory2048/256/1152MiB and1408<=1638.4MiB across HL-ENV/memory closure.",
+      "packet_locations": [
+        "#/high_load_envelope/required_hl_env_fields",
+        "#/high_load_envelope/units",
+        "#/high_load_envelope/field_units",
+        "#/high_load_envelope/memory_closure_check",
+        "#/resilience_gates/HL_ENV_v1/HL-ENV-01"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-012",
+      "source_findings": [
+        "PANEL-F-013"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "VER004 strict ruff format/check and basedpyright on all3files; zero errors, removed v1 error allowance; preserved server Any and other warning ceilings; inherited error debt explicitly assigned to Coder.",
+      "packet_locations": [
+        "#/verification_surface/3",
+        "#/risks/7",
+        "#/decisions/0/details/typing"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-013",
+      "source_findings": [
+        "PANEL-F-017"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Leading LF in entire synthetic status after unterminated model chunk, provenance filter preserves model bytes and literal model [мост]; fast Simple greeting unchanged.",
+      "packet_locations": [
+        "#/decisions/1/details/status_separator",
+        "#/decisions/1/details/pure_reasoning",
+        "#/verification_acceptance_matrix/status_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "RW-014",
+      "source_findings": [
+        "PANEL-F-019"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "_ServeHealth threshold3/TTL120/one recovery probe newauto requests only; protocol failure neutral to model breaker; exact version/schema cache by binary stat; no silent accepted-prompt replay.",
+      "packet_locations": [
+        "#/decisions/0/details/transport_health",
+        "#/decisions/0/details/protocol_compatibility",
+        "#/decisions/2/details/retry",
+        "#/resilience_gates/R_BULK/R-BULK-I3",
+        "#/verification_acceptance_matrix/resilience_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-001",
+      "source_findings": [
+        "PANEL-F-014"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Isolated per-spawn XDG_DATA_HOME, preserve models path, cleanup finally; risk/H3 and lifetime updated.",
+      "packet_locations": [
+        "#/decisions/0/details/data_isolation",
+        "#/risks/2",
+        "#/resilience_gates/T_LIFE_v1"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-002",
+      "source_findings": [
+        "PANEL-F-015"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "ADR0005+INDEX explicitly deferred outside frozen scope §10, materialization remains empty.",
+      "packet_locations": [
+        "#/deferred/3",
+        "#/materialization"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-003",
+      "source_findings": [
+        "PANEL-F-020"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Residual cross-provider reasoning replay risk accepted and mitigation short/infrequent nonsecret statuses recorded.",
+      "packet_locations": [
+        "#/risks/10",
+        "#/decisions/1/details/replay"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-004",
+      "source_findings": [
+        "PANEL-F-021"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "ruff format --check explicitly covers all3files alongside linter.",
+      "packet_locations": [
+        "#/verification_surface/3"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-005",
+      "source_findings": [
+        "PANEL-F-022"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "New JSON typed object+narrowing/TypedDict within server.py, no new module/allowlist expansion; reportAny/reportExplicitAny each<=125.",
+      "packet_locations": [
+        "#/decisions/0/details/typing",
+        "#/verification_surface/3"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-006",
+      "source_findings": [
+        "PANEL-F-023"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "File disable switch os.path.exists request-entry O(1), default ~/.dsh path/env override, same PID H9 toggle, no restart required; no live file modified.",
+      "packet_locations": [
+        "#/decisions/0/details/configuration/OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE",
+        "#/evolution/rollback",
+        "#/verification_acceptance_matrix/mode_matrix"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    },
+    {
+      "id": "FU-007",
+      "source_findings": [
+        "PANEL-F-024"
+      ],
+      "status": "RESOLVED",
+      "changes_made": "Budget51.6s<=54s, headroom2.4>=2.0, combinedadmission5+ready3+setup2+cleanup1.2 explicit.",
+      "packet_locations": [
+        "#/resilience_gates/R_BULK/R-BULK-I1",
+        "#/high_load_envelope/operational_profile"
+      ],
+      "verification": "Архитектурная delta внесена; JSON-pointer locations существуют и проверяются финальной semantic validation. VER-004/VER-005 — замороженные будущие проверки, НЕ выполнялись в Stage2; Council R2 и H0..H9 NOT_RUN."
+    }
+  ],
+  "rework_source": {
+    "path": "handoff/panel-rework-brief-arch-a1.json",
+    "sha256": "d173ff674c5a105fd85ab00a2a276ebcfb92d9b7295523721e9eed6503e5ed96",
+    "base_packet_path": "architecture/architecture-packet.v1.json",
+    "base_packet_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
+    "resolutions_count": 21,
+    "blocking_count": 14,
+    "nonblocking_count": 7,
+    "namespace": "Analyst F-01..F-49; council PANEL-F-001..024 = original brief finding ids prefixed PANEL-; RW/FU IDs unchanged"
+  }
 }
ARTIFACT_END>>>
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/handoff/panel-rework-brief-arch-a1.json sha256=d173ff674c5a105fd85ab00a2a276ebcfb92d9b7295523721e9eed6503e5ed96
{
  "schema_version": "1.0",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "teamlead_cycle": 1,
  "panel_slug": "analyst-teamlead-zen-realtime-reasoning-20261025-arch-council-1-a1",
  "panel_verdict": "NEEDS_WORK",
  "summarizer_slot": "gpt-6.1-sol",
  "instructions": [
    {
      "id": "RW-001",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.fallback_barrier, #R-BULK-I1, high_load_envelope.operational_profile",
      "rule_ref": "F-001: `R-BULK-I1` (`T_crit_aux` по всем попыткам ≤ 0.30×SLA); `REQ-001`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-001: `create+subscribe >= 2.0 с`; `prompt POST` по остатку first-event; `run` fallback только до заголовков ответа `POST`; `R-BULK-I1` пересчитан и записан. Не смешивать create+subscribe и потенциально долгий prompt POST; последний вести по остатку first-event watchdog. Согласовать единую state machine с RW-007, явно показав барьер неизвестной доставки и обработку заголовков ответа. Не снимать это разногласие молча.",
      "acceptance": "F-001: `VER-005` FakeClock, медленный create без заголовков POST → один `run`, `Popen<=3`; с заголовками POST → `run` нет; статическая сумма `<=54` с.",
      "source": "F-001: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F1`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-001: «create+event-subscription+prompt-send<=.2s»; «53.7s<=.30×180=54s»; «Начиная с попытки отправки prompt … silent fallback запрещён». F-19: `execution.started` 233 мс при ready около 109 мс. НЕСОГЛАСОВАННОСТЬ ИСХОДНЫХ ПОЗИЦИЙ: Seat 1 F1 требует fallback до заголовков ответа prompt POST; Seat 2, РИСКИ/4.3, считает защитой запрет уже после начала POST. Пакет AD-001.fallback_barrier также запрещает fallback с начала попытки отправки, включая неизвестную доставку. Сводка verdict-a1 заявляет отсутствие конфликтов, но эта разница границ сохранена; summarizer её не разрешает.",
      "source_findings": [
        "F-001"
      ],
      "finding_details": [
        {
          "id": "F-001",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F1`)",
          "status": "AGREED (blocking)",
          "criterion": "КОРРЕКТНОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#R-BULK-I1`, `#high_load_envelope`)",
          "rule": "`R-BULK-I1` (`T_crit_aux` по всем попыткам ≤ 0.30×SLA); `REQ-001`",
          "evidence": "«create+event-subscription+prompt-send<=.2s»; «53.7s<=.30×180=54s»; «Начиная с попытки отправки prompt … silent fallback запрещён». F-19: `execution.started` 233 мс при ready около 109 мс.",
          "expected_fix": "`create+subscribe >= 2.0 с`; `prompt POST` по остатку first-event; `run` fallback только до заголовков ответа `POST`; `R-BULK-I1` пересчитан и записан.",
          "acceptance": "`VER-005` FakeClock, медленный create без заголовков POST → один `run`, `Popen<=3`; с заголовками POST → `run` нет; статическая сумма `<=54` с.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-002",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.configuration, #AD-001.details.tool_policy, #RISK-001, #THREAT-002, #Q-002, #EVD-050",
      "rule_ref": "F-002: `REQ-012`; `THREAT-002`\nF-007: `REQ-012`, `REQ-003` (`AC-004`), `aisdlc-gcge/skills/architecture.md`\nF-018: `REQ-012`, `[F-08]`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-002: по умолчанию `ask` и немедленный программный `reject` (никогда `allow`); `deny` как выбираемая env-политика для проверки на H6; без ослабления в `allow`.\nF-007: сделать основным режимом для `serve` `permission={\"*\":\"ask\"}` + немедленный авто-отказ `reject` через `POST /api/session/{id}/permission/{requestID}/reply`, ввести `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject|deny` (default `ask_reject`), выделить `_serve_env(...)` поверх неизменного `_run_env(model_id)` и покрыть оба режима в `FakeServe`.\nF-018: ввести явный env-селектор политики инструментов `serve` с совместимым с Zen дефолтом `ask_reject` и fail-closed поведением. В AD-001 явно задать OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject|deny, default=ask_reject, неизменность _run_env(model_id), отдельный _serve_env поверх него и fail-closed при отсутствии безопасных permission endpoints/неподдерживаемой политике. Никогда allow; проверку совместимости с реальным Zen оставить H6, FakeServe её не доказывает. Любая смена deny→ask_reject допустима только до принятия prompt; после принятия prompt 403 не допускает silent run fallback. Учесть разногласие о предварительном автопереключении, приведённое в evidence.",
      "acceptance": "F-002: `VER-005`, запрос permission всегда получает `reject`; `deny` и `ask_reject` оба покрыты в `FakeServe`; при принятии prompt 403 остаётся fail-closed без silent fallback на `run`.\nF-007: `tests/test_run_env.py` проходит без правок; оба режима `ask_reject` и `deny` специфицированы и покрыты в `VER-005`.\nF-018: селектор описан в `AD-001` и проверяется в `FakeServe`. Дополнительно: отсутствие безопасной capability даёт явную ошибку; неподдержанная политика никогда не даёт allow; tests/test_run_env.py неизменен и зелёный. H6 доказывает живой отказ запрещённой записи, а не mock-совместимость Zen.",
      "source": "F-002: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F2`)\nF-007: Seat 2 (`gemini-4-argon-high`, `realist`, orig `1/9`)\nF-018: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `3/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-002: «Основная безопасная конфигурация — scoped … permission={\"*\":\"deny\"}»; «HTTP 401/403 … fail-closed, никакого ослабления policy через run»; `EVD-050`: `deny` может вызвать Zen 403.\nF-007: `AD-001:1000` делает `permission={\"*\":\"deny\"}` основной конфигурацией без env-переключателя, хотя `EVD-050` (`server.py:224-231`, `[F-08]`) фиксирует Zen `403`, а изменение `_run_env(model_id)` сломает неизменяемый `tests/test_run_env.py`.\nF-018: не определены переменная окружения, дефолт и fail-closed поведение для выбора между `ask_reject` и `deny`. НЕСОГЛАСОВАННОСТЬ ИСХОДНЫХ ПОЗИЦИЙ: Seat 1 F2 допускает один переход deny↔ask до принятия prompt, Seat 3 F-3 требует fail-closed без автопереключения при неподдержанной политике. Леджер согласовал default ask_reject и явный селектор; разрешение/запрет автоматической смены до prompt нельзя считать одинаковым требованием.",
      "source_findings": [
        "F-002",
        "F-007",
        "F-018"
      ],
      "finding_details": [
        {
          "id": "F-002",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F2`)",
          "status": "AGREED (blocking)",
          "criterion": "РИСКИ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#RISK-001`, `#EVD-050`)",
          "rule": "`REQ-012`; `THREAT-002`",
          "evidence": "«Основная безопасная конфигурация — scoped … permission={\"*\":\"deny\"}»; «HTTP 401/403 … fail-closed, никакого ослабления policy через run»; `EVD-050`: `deny` может вызвать Zen 403.",
          "expected_fix": "по умолчанию `ask` и немедленный программный `reject` (никогда `allow`); `deny` как выбираемая env-политика для проверки на H6; без ослабления в `allow`.",
          "acceptance": "`VER-005`, запрос permission всегда получает `reject`; `deny` и `ask_reject` оба покрыты в `FakeServe`; при принятии prompt 403 остаётся fail-closed без silent fallback на `run`.",
          "priority": "blocking"
        },
        {
          "id": "F-007",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `1/9`)",
          "status": "AGREED (blocking, дублирует корневую причину с `F-002` и `F-018`)",
          "criterion": "РЕАЛИЗУЕМОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`, `#RISK-001`, `#Q-002`, `#EVD-050`)",
          "rule": "`REQ-012`, `REQ-003` (`AC-004`), `aisdlc-gcge/skills/architecture.md`",
          "evidence": "`AD-001:1000` делает `permission={\"*\":\"deny\"}` основной конфигурацией без env-переключателя, хотя `EVD-050` (`server.py:224-231`, `[F-08]`) фиксирует Zen `403`, а изменение `_run_env(model_id)` сломает неизменяемый `tests/test_run_env.py`.",
          "expected_fix": "сделать основным режимом для `serve` `permission={\"*\":\"ask\"}` + немедленный авто-отказ `reject` через `POST /api/session/{id}/permission/{requestID}/reply`, ввести `OPENCODE_ZEN_BRIDGE_SERVE_PERMISSION_POLICY=ask_reject|deny` (default `ask_reject`), выделить `_serve_env(...)` поверх неизменного `_run_env(model_id)` и покрыть оба режима в `FakeServe`.",
          "acceptance": "`tests/test_run_env.py` проходит без правок; оба режима `ask_reject` и `deny` специфицированы и покрыты в `VER-005`.",
          "priority": "blocking"
        },
        {
          "id": "F-018",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `3/9`)",
          "status": "AGREED (duplicate of `F-007`)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`, `#Q-002`)",
          "rule": "`REQ-012`, `[F-08]`",
          "evidence": "не определены переменная окружения, дефолт и fail-closed поведение для выбора между `ask_reject` и `deny`.",
          "expected_fix": "ввести явный env-селектор политики инструментов `serve` с совместимым с Zen дефолтом `ask_reject` и fail-closed поведением.",
          "acceptance": "селектор описан в `AD-001` и проверяется в `FakeServe`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-003",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.spawn, #THREAT-001",
      "rule_ref": "F-003: `THREAT-001`; отсутствие границы доверия на loopback",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-003: порт выбирает родитель через `bind 127.0.0.1:0` / `getsockname`; `spawn` с явным `--port`; Basic Auth и prompt отправляются только после проверки принадлежности слушателя порту дочернему процессу/PGID. Зафиксировать проверяемый протокол доказательства PID/PGID владельца listener ДО первого Basic Auth и prompt; bind(127.0.0.1,0)→getsockname→release→явный --port; повтор при EADDRINUSE ограничен ready-бюджетом. Не оставлять способ проверки владения на догадку Coder.",
      "acceptance": "F-003: `VER-005`, чужой PID на том же порту → ноль байт пароля и промпта с секретами утекает в чужой процесс, попытка завершается ошибкой внутри ready-бюджета. Дополнительно негативный VER-005: порт захвачен между release и spawn, listener чужой, пароль/промпт не отправляются; EADDRINUSE retry не превышает ready ceiling.",
      "source": "F-003: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F3`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-003: «--port, ephemeral»; «если API не даёт port=0 … reserve-bind(0), release, spawn с ограниченным retry race».",
      "source_findings": [
        "F-003"
      ],
      "finding_details": [
        {
          "id": "F-003",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F3`)",
          "status": "AGREED (blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#THREAT-001`)",
          "rule": "`THREAT-001`; отсутствие границы доверия на loopback",
          "evidence": "«--port, ephemeral»; «если API не даёт port=0 … reserve-bind(0), release, spawn с ограниченным retry race».",
          "expected_fix": "порт выбирает родитель через `bind 127.0.0.1:0` / `getsockname`; `spawn` с явным `--port`; Basic Auth и prompt отправляются только после проверки принадлежности слушателя порту дочернему процессу/PGID.",
          "acceptance": "`VER-005`, чужой PID на том же порту → ноль байт пароля и промпта с секретами утекает в чужой процесс, попытка завершается ошибкой внутри ready-бюджета.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-004",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.event_contract",
      "rule_ref": "F-004: `REQ-001`, `REQ-010`, `REQ-014`; проверяемость `VER-005`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-004: в `AD-001.event_contract` вложен замороженный минимальный JSON-фикстур `opencode serve` v2.1.2 для reasoning delta, text delta, `step.ended` tokens (`input`/`output`/`cached`/`reasoning`), tool/permission lifecycle и `execution.failed`. Замороженный fixture должен быть независимой опорой и для адаптера, и для FakeServe: точные конверты и JSON field paths reasoning/text delta, step.ended с input/output/cached/reasoning, tool/permission lifecycle, execution.failed. Не поручать Coder придумывать совпадающий с собственным мок-клиентом протокол.",
      "acceptance": "F-004: `VER-005` падает, если адаптер или `FakeServe` расходится с замороженным фикстуром на любом из этих конвертов. Дополнительно негативные fixtures: смещённое поле delta, несовместимый token envelope и permission lifecycle обнаруживаются независимо от совпадения мок-сервера и адаптера.",
      "source": "F-004: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F4`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-004: «Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test». F-19/F-22 фиксируют имена событий и эндпоинты, не пути полей.",
      "source_findings": [
        "F-004"
      ],
      "finding_details": [
        {
          "id": "F-004",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F4`)",
          "status": "AGREED (blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`)",
          "rule": "`REQ-001`, `REQ-010`, `REQ-014`; проверяемость `VER-005`",
          "evidence": "«Конкретные field paths подтверждает Coder по v2 schema в FakeServe contract test». F-19/F-22 фиксируют имена событий и эндпоинты, не пути полей.",
          "expected_fix": "в `AD-001.event_contract` вложен замороженный минимальный JSON-фикстур `opencode serve` v2.1.2 для reasoning delta, text delta, `step.ended` tokens (`input`/`output`/`cached`/`reasoning`), tool/permission lifecycle и `execution.failed`.",
          "acceptance": "`VER-005` падает, если адаптер или `FakeServe` расходится с замороженным фикстуром на любом из этих конвертов.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-005",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#REQ-013, #AD-001.drivers, #RISK-002",
      "rule_ref": "F-005: `REQ-013` MUST; Forbidden Scope (конфиг georouter не трогать); `[F-15]`, `[F-27]`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-005: уточнить трактовку `REQ-013` и `AD-001` drivers в пакете под фактическую гарантию `AC-018` (сохранение per-spawn ротации прокси-окружения `_next_standalone_proxy`, как у `run`, с честной фиксацией в `RISK-002`, что loopback `georouter` не идёт через `HTTP_PROXY` дочернего процесса). Это уточнение гарантии пакета под существующий AC-018, без расширения Forbidden Scope и без правок конфигурации georouter; A1 обосновывать изоляцией failure domain и подтверждёнными дельтами, не доказанной сменой Zen egress IP.",
      "acceptance": "F-005: в пакете нет ложного утверждения, что env `serve` сам переключает IP внутри `georouter`; `AC-018` остаётся проверкой последовательности записей пула `_next_standalone_proxy`.",
      "source": "F-005: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F5`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-005: statement «Ротация чистых IP на каждый новый запуск»; `AC-018` проверяет `_next_standalone_proxy`. `[F-15]`: loopback мимо прокси. `[F-27]`: `baseURL=http://127.0.0.1:10830/v1`.",
      "source_findings": [
        "F-005"
      ],
      "finding_details": [
        {
          "id": "F-005",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F5`)",
          "status": "AGREED (blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#REQ-013`, `#AD-001`, `#RISK-002`)",
          "rule": "`REQ-013` MUST; Forbidden Scope (конфиг georouter не трогать); `[F-15]`, `[F-27]`",
          "evidence": "statement «Ротация чистых IP на каждый новый запуск»; `AC-018` проверяет `_next_standalone_proxy`. `[F-15]`: loopback мимо прокси. `[F-27]`: `baseURL=http://127.0.0.1:10830/v1`.",
          "expected_fix": "уточнить трактовку `REQ-013` и `AD-001` drivers в пакете под фактическую гарантию `AC-018` (сохранение per-spawn ротации прокси-окружения `_next_standalone_proxy`, как у `run`, с честной фиксацией в `RISK-002`, что loopback `georouter` не идёт через `HTTP_PROXY` дочернего процесса).",
          "acceptance": "в пакете нет ложного утверждения, что env `serve` сам переключает IP внутри `georouter`; `AC-018` остаётся проверкой последовательности записей пула `_next_standalone_proxy`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-006",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "high_load_envelope.memory_closure_check, #C-MULT-I1, #RISK-003, evolution.rollout",
      "rule_ref": "F-006: `HL-ENV-01` memory closure; `C-MULT-I1`; устойчивость при 6 параллельных запросах",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-006: устранить конкуренцию за общую `opencode.db` `2.27 GB` через эфемерный per-spawn `XDG_DATA_HOME` (удаляемый в `finally`) и/или зафиксировать жёсткий rollout-гейт H3 с проверкой фактического RSS одноразового `serve` (`1×parent + M×child <= 0.8×Mem_limit_per_pod`) и отсутствия `database is locked`. В H3 явно запретить rollout при нарушении 1×parent_RSS + M×child_RSS <= 0.80×Mem_limit_per_pod; численные design estimates не выдавать за измерение. C-MULT-I1 по SQLite не считать runtime PASS до H3 без database is locked вне FAIL_RETRY_LIMIT; не увеличивать слоты 6/12. Изоляция XDG_DATA_HOME должна сохранять OPENCODE_MODELS_PATH и иметь cleanup в finally, если выбрана. Согласовать с RW-009: дефолт включения не должен обходить обязательный H3.",
      "acceptance": "F-006: в `high_load_envelope`, `C-MULT-I1` и `evolution` зафиксированы изоляция SQLite / rollout-гейт H3 по RSS и блокировкам БД. H3 описан для 6 параллельных рабочих промптов 103 KB и повторных вызовов: реальные RSS и отсутствие DB-lock, измеренный провал запрещает enable. Stage2 не утверждает живой PASS.",
      "source": "F-006: Seat 1 (`grok-4.7-high`, `skeptic`, orig `F6`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-006: «6×192MiB=1152MiB»; `[F-20]`: долгий `serve` RSS 439 МиБ (тогда как короткоживущий `serve` 152 МиБ); «opencode_local_db=10 — design logical-child share … НЕ доказанный sqlite pool»; `[F-28]`: `opencode.db` 2.27 ГБ. Seat 1 F6 требует флаг выключенным при нарушении H3 и отсутствие runtime PASS для SQLite до H3. Seat 2 F-004 / ledger F-010 требует default=true ради LaunchAgent; это напряжение порядка включения и приёмки должно быть явно закрыто в пакете, не скрыто общей фразой rollout.",
      "source_findings": [
        "F-006"
      ],
      "finding_details": [
        {
          "id": "F-006",
          "source_seat": "Seat 1 (`grok-4.7-high`, `skeptic`, orig `F6`)",
          "status": "AGREED (blocking)",
          "criterion": "РИСКИ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#high_load_envelope`, `#C-MULT-I1`, `#RISK-003`)",
          "rule": "`HL-ENV-01` memory closure; `C-MULT-I1`; устойчивость при 6 параллельных запросах",
          "evidence": "«6×192MiB=1152MiB»; `[F-20]`: долгий `serve` RSS 439 МиБ (тогда как короткоживущий `serve` 152 МиБ); «opencode_local_db=10 — design logical-child share … НЕ доказанный sqlite pool»; `[F-28]`: `opencode.db` 2.27 ГБ.",
          "expected_fix": "устранить конкуренцию за общую `opencode.db` `2.27 GB` через эфемерный per-spawn `XDG_DATA_HOME` (удаляемый в `finally`) и/или зафиксировать жёсткий rollout-гейт H3 с проверкой фактического RSS одноразового `serve` (`1×parent + M×child <= 0.8×Mem_limit_per_pod`) и отсутствия `database is locked`.",
          "acceptance": "в `high_load_envelope`, `C-MULT-I1` и `evolution` зафиксированы изоляция SQLite / rollout-гейт H3 по RSS и блокировкам БД.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-007",
      "priority": "blocking",
      "criterion": "РЕАЛИЗУЕМОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.startup, #AD-001.details.session_flow, #R-BULK-I1, high_load_envelope.operational_profile",
      "rule_ref": "F-008: `aisdlc-gcge/agents/architecture.md` §3.4 `R-BULK-I1` и реалистичность NFR-бюджетов",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-008: использовать `GET /api/session/active` для readiness; объединить pre-spawn admission (`_StartupGate` + `_SpawnRateLimiter <= 5.0 s`) и поднять `ready_budget_s=3.0 s`, `session_setup_budget_s=2.0 s` (`15 + 3×(5.0 + 3.0 + 2.0 + 1.2) + 3 = 51.6 s <= 54.0 s`); зафиксировать точный wire-контракт `POST /api/session` (`model`/`variant`) и `POST /api/session/{id}/prompt` (`delivery` / параллельное чтение `/api/event`). Синхронно обновить AD-001, operational_profile, dependency budgets и R-BULK-I1; не сохранять старые независимые ожидания gate=5 + spawn=5 рядом с новым общим admission<=5.0. Точный delivery, model/variant и параллельное чтение /api/event зафиксировать до Coder. Согласовать с RW-001, сохранив в evidence обе позиции по fallback.",
      "acceptance": "F-008: `R-BULK-I1 <= 54.0 s` при `ready_budget_s >= 2.5 s` и `session_setup_budget_s >= 2.0 s`; wire-контракт `session` и `prompt` полностью определён в `AD-001`. Формула фиксируется явно: 15 + 3×(5.0 + 3.0 + 2.0 + 1.2) + 3 = 51.6 <= 54.0 s; запас 2.4 s. FakeClock/FakeServe проверяет медленный create, delivery и отсутствие четвёртого Popen совместно с RW-001.",
      "source": "F-008: Seat 2 (`gemini-4-argon-high`, `realist`, orig `2/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-008: `SERVE_READY_TIMEOUT_S=0.50` (с выгрузкой `281 KB` `/openapi.json`) и `session_setup_budget_s=0.20` меньше одиночного замера `233.06 ms` (`[F-19]`), при промптах `103 KB` (`[F-30]`) и `opencode.db` `2.27 GB` (`[F-28]`); семантика `delivery` у `POST /api/session/{id}/prompt` и передача `model`/`variant` не зафиксированы. Граница fallback в F-001 и Seat 2 РИСКИ/4.3 различна: headers response против начала POST. Также в исходном Seat 2 F-002 acceptance минимальный session_setup>=1.5s, тогда как expected_fix и согласованный ledger F-008 требуют 2.0s; в инструкции сохранён более конкретный согласованный леджер, расхождение не замолчано.",
      "source_findings": [
        "F-008"
      ],
      "finding_details": [
        {
          "id": "F-008",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `2/9`)",
          "status": "AGREED (blocking, расширяет `F-001`)",
          "criterion": "РЕАЛИЗУЕМОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:997` (`#AD-001`, `#high_load_envelope`, `#R-BULK-I1`)",
          "rule": "`aisdlc-gcge/agents/architecture.md` §3.4 `R-BULK-I1` и реалистичность NFR-бюджетов",
          "evidence": "`SERVE_READY_TIMEOUT_S=0.50` (с выгрузкой `281 KB` `/openapi.json`) и `session_setup_budget_s=0.20` меньше одиночного замера `233.06 ms` (`[F-19]`), при промптах `103 KB` (`[F-30]`) и `opencode.db` `2.27 GB` (`[F-28]`); семантика `delivery` у `POST /api/session/{id}/prompt` и передача `model`/`variant` не зафиксированы.",
          "expected_fix": "использовать `GET /api/session/active` для readiness; объединить pre-spawn admission (`_StartupGate` + `_SpawnRateLimiter <= 5.0 s`) и поднять `ready_budget_s=3.0 s`, `session_setup_budget_s=2.0 s` (`15 + 3×(5.0 + 3.0 + 2.0 + 1.2) + 3 = 51.6 s <= 54.0 s`); зафиксировать точный wire-контракт `POST /api/session` (`model`/`variant`) и `POST /api/session/{id}/prompt` (`delivery` / параллельное чтение `/api/event`).",
          "acceptance": "`R-BULK-I1 <= 54.0 s` при `ready_budget_s >= 2.5 s` и `session_setup_budget_s >= 2.0 s`; wire-контракт `session` и `prompt` полностью определён в `AD-001`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-008",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-003.details.clocks, #REQ-006, verification_acceptance_matrix.watchdog_matrix",
      "rule_ref": "F-009: `REQ-006` (`AC-008`: 20 с до первого события транспорта) и `REQ-016` (`AC-021`: `first_event_ms`)",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-009: развести `SERVE_READY_TIMEOUT_S` (до промпта -> `ServeUnavailable`) и часы `first_event` (`FIRST_EVENT_TIMEOUT_S=20.0`), которые на пути `serve` удовлетворяются только первым валидным SSE-событием созданной сессии после отправки промпта (`session.execution.started` / `session.step.started` / `session.reasoning.started`). Обновить также O-EXIT first_event_ms и watchdog_matrix: локальная HTTP-готовность не является событием исполнения сессии. Сохранить отдельные часы first-token/stall и неизменный общий deadline; started/control/comments не являются модельным токеном.",
      "acceptance": "F-009: сценарий `VER-005` «HTTP readiness прошёл и `POST /prompt` принят, но SSE-событий сессии нет» завершается по `first_event_timeout` за `FIRST_EVENT_TIMEOUT_S + 2 s`.",
      "source": "F-009: Seat 2 (`gemini-4-argon-high`, `realist`, orig `3/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-009: `architecture-packet.json:1119` и `:2481` разрешают гасить `first_event` локальным HTTP readiness `serve` (`~109 ms`), из-за чего зависание после `POST /prompt` без единого SSE-события ждёт `60 s` (`first_token_timeout`) вместо `20 s` (`first_event_timeout`).",
      "source_findings": [
        "F-009"
      ],
      "finding_details": [
        {
          "id": "F-009",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `3/9`)",
          "status": "AGREED (blocking)",
          "criterion": "КОРРЕКТНОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1119` (`#AD-003`, `#REQ-006`, `#verification_acceptance_matrix:2481`)",
          "rule": "`REQ-006` (`AC-008`: 20 с до первого события транспорта) и `REQ-016` (`AC-021`: `first_event_ms`)",
          "evidence": "`architecture-packet.json:1119` и `:2481` разрешают гасить `first_event` локальным HTTP readiness `serve` (`~109 ms`), из-за чего зависание после `POST /prompt` без единого SSE-события ждёт `60 s` (`first_token_timeout`) вместо `20 s` (`first_event_timeout`).",
          "expected_fix": "развести `SERVE_READY_TIMEOUT_S` (до промпта -> `ServeUnavailable`) и часы `first_event` (`FIRST_EVENT_TIMEOUT_S=20.0`), которые на пути `serve` удовлетворяются только первым валидным SSE-событием созданной сессии после отправки промпта (`session.execution.started` / `session.step.started` / `session.reasoning.started`).",
          "acceptance": "сценарий `VER-005` «HTTP readiness прошёл и `POST /prompt` принят, но SSE-событий сессии нет» завершается по `first_event_timeout` за `FIRST_EVENT_TIMEOUT_S + 2 s`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-009",
      "priority": "blocking",
      "criterion": "РЕАЛИЗУЕМОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.configuration, #REQ-003, #REQ-019, evolution.rollout, evolution.rollback",
      "rule_ref": "F-010: `REQ-001`, `REQ-003`, `REQ-019` и выполнимость живой приёмки `H0..H9`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-010: установить `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` в `default: true` при `OPENCODE_ZEN_BRIDGE_TRANSPORT=auto` (по прецеденту `STEP_RECOVERY=1` и `muse-bridge`: shebang-фильтр для fake-CLI автоматически сохраняет `run` на всех 378 существующих тестах, а `TRANSPORT=run` / `REALTIME_SERVE_ENABLED=0` и опциональный stat-файл kill-switch дают $O(1)$ отключение). Перевести согласованное требование F-010 в delta пакета с явным обоснованием изменения default=false→true; сохранить auto shebang-фильтр, TRANSPORT=run и REALTIME_SERVE_ENABLED=0. Не расширять allowlist на start.sh самовольно. Не объявлять пройденными H0..H9 или H3; отразить связь с обязательным RSS/SQLite rollout-гейтом RW-006 и отдельным non-blocking FU-006.",
      "acceptance": "F-010: после синхронизации `server.py` на `:9883` `serve`-транспорт активен для нативного бинарника `opencode` без ручной правки `start.sh`, все 378 fake-CLI тестов зелёные, документированный kill-switch работает мгновенно.",
      "source": "F-010: Seat 2 (`gemini-4-argon-high`, `realist`, orig `4/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-010: `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` имеет `default: false`, но неизменяемый `start.sh` читает из `~/.dsh/.env` только 3 ключа API и не пробрасывает флаги в LaunchAgent, поэтому после синхронизации `server.py` на `:9883` (`REQ-019`) `serve` не включится, а kill-switch через `~/.dsh/.env` не сработает. РАЗЛИЧИЕ ПОЗИЦИЙ: Seat 1 СООТВЕТСТВИЕ КОНТЕКСТУ/PASS считает default-disabled частью соблюдения контекста; Seat 2 F-004 требует default=true либо расширение scope на start.sh. Согласованный ledger F-010 выбирает default=true без start.sh. Действующий packet/evolution.feature_flag пока утверждает default=false; H3 из F-006 остаётся обязательным до rollout.",
      "source_findings": [
        "F-010"
      ],
      "finding_details": [
        {
          "id": "F-010",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `4/9`)",
          "status": "AGREED (blocking)",
          "criterion": "РЕАЛИЗУЕМОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:980` (`#AD-001`, `#REQ-003`, `#REQ-019`, `#evolution`)",
          "rule": "`REQ-001`, `REQ-003`, `REQ-019` и выполнимость живой приёмки `H0..H9`",
          "evidence": "`OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` имеет `default: false`, но неизменяемый `start.sh` читает из `~/.dsh/.env` только 3 ключа API и не пробрасывает флаги в LaunchAgent, поэтому после синхронизации `server.py` на `:9883` (`REQ-019`) `serve` не включится, а kill-switch через `~/.dsh/.env` не сработает.",
          "expected_fix": "установить `OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` в `default: true` при `OPENCODE_ZEN_BRIDGE_TRANSPORT=auto` (по прецеденту `STEP_RECOVERY=1` и `muse-bridge`: shebang-фильтр для fake-CLI автоматически сохраняет `run` на всех 378 существующих тестах, а `TRANSPORT=run` / `REALTIME_SERVE_ENABLED=0` и опциональный stat-файл kill-switch дают $O(1)$ отключение).",
          "acceptance": "после синхронизации `server.py` на `:9883` `serve`-транспорт активен для нативного бинарника `opencode` без ручной правки `start.sh`, все 378 fake-CLI тестов зелёные, документированный kill-switch работает мгновенно.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-010",
      "priority": "blocking",
      "criterion": "КОРРЕКТНОСТЬ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001.details.tool_policy, #EVD-050",
      "rule_ref": "F-011: трассируемость всех ссылок `F-NN` к `analysis/zen-realtime-reasoning/evidence-ledger.md` (`F-01..F-49`)\nF-016: трассируемость `F-NN` к `evidence-ledger.md`",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-011: заменить `F-50` на `EVD-050` (`bridges/opencode-zen-bridge/server.py:224-231`, `[F-08]`).\nF-016: заменить `F-50` на `EVD-050` + `[F-08]`. Не добавлять выдуманный новый F-50 в замороженный analyst ledger; исправить ссылку пакета на существующие EVD-050 + [F-08].",
      "acceptance": "F-011: поиск `F-\\d+` по `architecture-packet.json` возвращает только идентификаторы `F-01..F-49` (и ссылки на внутренние findings при необходимости помечены иначе).\nF-016: все `F-NN` в пакете присутствуют в `evidence-ledger.md`.",
      "source": "F-011: Seat 2 (`gemini-4-argon-high`, `realist`, orig `5/9`)\nF-016: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `1/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-011: `architecture-packet.json:1000` ссылается на несуществующий `F-50` (в реестре 49 фактов `F-01..F-49`).\nF-016: `AD-001.details.tool_policy` опирается на несуществующий `F-50` вместо `EVD-050` + `[F-08]`.",
      "source_findings": [
        "F-011",
        "F-016"
      ],
      "finding_details": [
        {
          "id": "F-011",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `5/9`)",
          "status": "AGREED (blocking)",
          "criterion": "КОРРЕКТНОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`)",
          "rule": "трассируемость всех ссылок `F-NN` к `analysis/zen-realtime-reasoning/evidence-ledger.md` (`F-01..F-49`)",
          "evidence": "`architecture-packet.json:1000` ссылается на несуществующий `F-50` (в реестре 49 фактов `F-01..F-49`).",
          "expected_fix": "заменить `F-50` на `EVD-050` (`bridges/opencode-zen-bridge/server.py:224-231`, `[F-08]`).",
          "acceptance": "поиск `F-\\d+` по `architecture-packet.json` возвращает только идентификаторы `F-01..F-49` (и ссылки на внутренние findings при необходимости помечены иначе).",
          "priority": "blocking"
        },
        {
          "id": "F-016",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `1/9`)",
          "status": "AGREED (duplicate of `F-011`)",
          "criterion": "КОРРЕКТНОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1000` (`#AD-001`)",
          "rule": "трассируемость `F-NN` к `evidence-ledger.md`",
          "evidence": "`AD-001.details.tool_policy` опирается на несуществующий `F-50` вместо `EVD-050` + `[F-08]`.",
          "expected_fix": "заменить `F-50` на `EVD-050` + `[F-08]`.",
          "acceptance": "все `F-NN` в пакете присутствуют в `evidence-ledger.md`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-011",
      "priority": "blocking",
      "criterion": "СООТВЕТСТВИЕ КОНТЕКСТУ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "high_load_envelope.required_hl_env_fields, high_load_envelope.units, high_load_envelope.memory_closure_check, #HL-ENV-01",
      "rule_ref": "F-012: Неснимаемый стоп-код `HL-ENV-01` в `aisdlc-gcge/agents/architecture.md` §3.0 (строки 18–20 таблицы: единицы `MiB`)",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-012: записать `Mem_limit_per_pod: 2048`, `Mem_rss_worker_max: 256`, `Mem_shared_max: 1152` в единицах `MiB` и согласовать `units`, `memory_closure_check` и `HL-ENV-01.substitution`. Сохранить ровно 46 канонических имён, согласовать units/field_sources, численные подстановки и связанные формулы; 1408<=1638.4 MiB. Это исправление единиц, а не доказательство RSS под нагрузкой из RW-006.",
      "acceptance": "F-012: все 46 полей `required_hl_env_fields` строго соответствуют единицам таблицы §3.0 `aisdlc-gcge/agents/architecture.md`, неравенство `1*256 + 1152 <= 0.80*2048` выполнено в `MiB`.",
      "source": "F-012: Seat 2 (`gemini-4-argon-high`, `realist`, orig `6/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-012: поля `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max` записаны в сырых байтах (`2147483648`, `268435456`, `1207959552`) вместо предписанных таблицей §3.0 единиц `MiB` (`2048`, `256`, `1152`). Seat 3 пишет, что арифметика памяти в байтах верна; Seat 2 блокирует канонические единицы MiB. Это разные проверки: правильное численное преобразование не снимает нарушение единиц HL-ENV-01.",
      "source_findings": [
        "F-012"
      ],
      "finding_details": [
        {
          "id": "F-012",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `6/9`)",
          "status": "AGREED (blocking, `[pre-existing]`)",
          "criterion": "СООТВЕТСТВИЕ КОНТЕКСТУ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1684` (`#high_load_envelope`, `#HL-ENV-01`)",
          "rule": "Неснимаемый стоп-код `HL-ENV-01` в `aisdlc-gcge/agents/architecture.md` §3.0 (строки 18–20 таблицы: единицы `MiB`)",
          "evidence": "поля `Mem_limit_per_pod`, `Mem_rss_worker_max`, `Mem_shared_max` записаны в сырых байтах (`2147483648`, `268435456`, `1207959552`) вместо предписанных таблицей §3.0 единиц `MiB` (`2048`, `256`, `1152`).",
          "expected_fix": "записать `Mem_limit_per_pod: 2048`, `Mem_rss_worker_max: 256`, `Mem_shared_max: 1152` в единицах `MiB` и согласовать `units`, `memory_closure_check` и `HL-ENV-01.substitution`.",
          "acceptance": "все 46 полей `required_hl_env_fields` строго соответствуют единицам таблицы §3.0 `aisdlc-gcge/agents/architecture.md`, неравенство `1*256 + 1152 <= 0.80*2048` выполнено в `MiB`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-012",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#VER-004, scope.coder_target_files",
      "rule_ref": "F-013: `aisdlc-gcge/AGENTS.md` п. 5 (`ruff format --check`, `ruff check`, `basedpyright` обязательны для всех изменяемых файлов)",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-013: расширить `VER-004` проверками `ruff format --check`, `ruff check` и `basedpyright` (0 ошибок `severity==\"error\"`) на все 3 файла из `scope.coder_target_files` (`server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`). В delta пакета явно описать команды и результат всех трёх проверок на трёх файлах; не ослаблять frozen warning budgets и не выдавать прежние разрешённые pyright error sites за ноль ошибок. Если наследуемые ошибки не дают выполнить согласованное acceptance 0 errors, предъявить evidence в no_architecture_delta/следующем проходе, а не молча изменить acceptance.",
      "acceptance": "F-013: команда `VER-004` покрывает все 3 целевых файла форматтером, линтером и тайпчекером и завершается с `exit 0`. Ни один из scope.coder_target_files не пропущен; форматтер присутствует явно, предупреждения не растут, различие текущего baseline и требуемого нуля ошибок отражено проверяемо.",
      "source": "F-013: Seat 2 (`gemini-4-argon-high`, `realist`, orig `7/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-013: `VER-004` проверяет `ruff check` только на `server.py` и `tests/test_realtime_reasoning.py`, пропуская изменяемый `tests/test_step_interruption.py`, и запускает `basedpyright` только на `server.py`. Согласованный ledger F-013 требует basedpyright 0 ошибок severity==error на всех трёх файлах; исходный Seat 2 F-007 допускал явный baseline наследованных диагностик test_step_interruption.py. Текущий VER-004 допускает 2 наследованных error sites в server.py. Это не эквивалент 0 errors; не снимать различие молчаливым переносом overlay.",
      "source_findings": [
        "F-013"
      ],
      "finding_details": [
        {
          "id": "F-013",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `7/9`)",
          "status": "AGREED (blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`, `#scope`)",
          "rule": "`aisdlc-gcge/AGENTS.md` п. 5 (`ruff format --check`, `ruff check`, `basedpyright` обязательны для всех изменяемых файлов)",
          "evidence": "`VER-004` проверяет `ruff check` только на `server.py` и `tests/test_realtime_reasoning.py`, пропуская изменяемый `tests/test_step_interruption.py`, и запускает `basedpyright` только на `server.py`.",
          "expected_fix": "расширить `VER-004` проверками `ruff format --check`, `ruff check` и `basedpyright` (0 ошибок `severity==\"error\"`) на все 3 файла из `scope.coder_target_files` (`server.py`, `tests/test_realtime_reasoning.py`, `tests/test_step_interruption.py`).",
          "acceptance": "команда `VER-004` покрывает все 3 целевых файла форматтером, линтером и тайпчекером и завершается с `exit 0`.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-013",
      "priority": "blocking",
      "criterion": "ПОЛНОТА",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-002.details.lifecycle, #AD-002.details.retry, #AD-002.details.pure_reasoning",
      "rule_ref": "F-017: `REQ-005` (`AC-006`) и `[F-37]` (`latestCompletedParagraphFirstLine`)",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-017: перед отправкой синтетической статусной дельты `[мост]`, если последний отправленный байт модельного `reasoning_content` не `\n`, вставлять ведущий `\n` как часть синтетического статуса (`\n[мост] ...\n`), чтобы модельные байты при фильтрации синтетических чанков оставались побайтно неизменными (`AC-006`). Ведущий LF принадлежит только synthetic status по provenance, не меняет модельные дельты и не добавляется в быстрый Simple greeting.; статус не сбрасывает watchdog и не входит в usage/prompt.",
      "acceptance": "F-017: `VER-005` проверяет вставку статусной дельты после модельного чанка без завершающего `\n`: строка `[мост]` отделена переводом строки, а конкатенация модельных чанков побайтно равна оригиналу.",
      "source": "F-017: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `2/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-017: статусные дельты `[мост]` оканчиваются `\n`, но если предыдущая модельная дельта `reasoning_content` не оканчивалась `\n`, heartbeat/retry-статус приклеится к недописанной строке модели и нарушит отображение и разделение строк.",
      "source_findings": [
        "F-017"
      ],
      "finding_details": [
        {
          "id": "F-017",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `2/9`)",
          "status": "AGREED (blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-002`)",
          "rule": "`REQ-005` (`AC-006`) и `[F-37]` (`latestCompletedParagraphFirstLine`)",
          "evidence": "статусные дельты `[мост]` оканчиваются `\n`, но если предыдущая модельная дельта `reasoning_content` не оканчивалась `\n`, heartbeat/retry-статус приклеится к недописанной строке модели и нарушит отображение и разделение строк.",
          "expected_fix": "перед отправкой синтетической статусной дельты `[мост]`, если последний отправленный байт модельного `reasoning_content` не `\n`, вставлять ведущий `\n` как часть синтетического статуса (`\n[мост] ...\n`), чтобы модельные байты при фильтрации синтетических чанков оставались побайтно неизменными (`AC-006`).",
          "acceptance": "`VER-005` проверяет вставку статусной дельты после модельного чанка без завершающего `\n`: строка `[мост]` отделена переводом строки, а конкатенация модельных чанков побайтно равна оригиналу.",
          "priority": "blocking"
        }
      ]
    },
    {
      "id": "RW-014",
      "priority": "blocking",
      "criterion": "РИСКИ",
      "file": ".ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json",
      "line_hint": "#AD-001, #AD-003.details.retry, #R-BULK-I3, risks, verification_acceptance_matrix.resilience_matrix",
      "rule_ref": "F-019: устойчивость к деградации `serve`-транспорта без блокировки всего моста (`REQ-003`)",
      "action": "Architect: изменить Architecture Packet, без правок продуктного кода.\nF-019: ввести в `AD-001`/`AD-003` отдельный индикатор здоровья `serve`-транспорта (`_ServeHealth` со sticky TTL авто-деградации на `run` для последующих запросов при серии специфичных для `serve` сбоев `first_event_timeout` / `invalid_serve_event`, не открывая общий `_UpstreamBreaker` модели). Явно отделить специфичные serve protocol/event failures от реальных provider failures; определить счётчик, условия sticky TTL/восстановления и transport_history. Не разрешать незаметный повтор prompt текущего запроса с неизвестной доставкой: авто-деградация относится к последующим запросам. Учесть исходный запрос Seat 3 проверять версию opencode/хеш OpenAPI на handshake и кэшировать по mtime_ns+size.",
      "acceptance": "F-019: `VER-005` проверяет, что серия специфичных для `serve` сбоев переводит следующий запрос на `run` по sticky TTL и не открывает общий `_UpstreamBreaker`. Негативный FakeServe: пять запросов со специфично глухим/несовместимым serve не открывают общий breaker; следующий запрос идёт run в пределах sticky TTL; общий MAX_TOTAL_SPAWNS=3 и fail-closed security сохраняются.",
      "source": "F-019: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `4/9`); findings-ledger.md: согласованные AGREED blocking; arch-council.md §3 → Architect.",
      "evidence": "F-019: если после апгрейда `opencode` изменится схема событий `serve` или SSE-подписка перестанет присылать события после `POST /prompt`, `first_event_timeout`/`first_token_timeout` за 5 запросов откроет общий `_UpstreamBreaker` моста, хотя legacy `opencode run` остаётся полностью рабочим.",
      "source_findings": [
        "F-019"
      ],
      "finding_details": [
        {
          "id": "F-019",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `4/9`)",
          "status": "AGREED (blocking)",
          "criterion": "РИСКИ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-001`, `#AD-003`, `#R-BULK-I3`)",
          "rule": "устойчивость к деградации `serve`-транспорта без блокировки всего моста (`REQ-003`)",
          "evidence": "если после апгрейда `opencode` изменится схема событий `serve` или SSE-подписка перестанет присылать события после `POST /prompt`, `first_event_timeout`/`first_token_timeout` за 5 запросов откроет общий `_UpstreamBreaker` моста, хотя legacy `opencode run` остаётся полностью рабочим.",
          "expected_fix": "ввести в `AD-001`/`AD-003` отдельный индикатор здоровья `serve`-транспорта (`_ServeHealth` со sticky TTL авто-деградации на `run` для последующих запросов при серии специфичных для `serve` сбоев `first_event_timeout` / `invalid_serve_event`, не открывая общий `_UpstreamBreaker` модели).",
          "acceptance": "`VER-005` проверяет, что серия специфичных для `serve` сбоев переводит следующий запрос на `run` по sticky TTL и не открывает общий `_UpstreamBreaker`.",
          "priority": "blocking"
        }
      ]
    }
  ],
  "non_blocking_followups": [
    {
      "id": "FU-001",
      "text": "Architect, по своему решению: зафиксировать в `AD-001` / `RISK-003` решение по per-spawn временному `XDG_DATA_HOME` (с удалением в `finally`) при сохранении `OPENCODE_MODELS_PATH`, чтобы исключить `SQLITE_BUSY` на `opencode.db` `2.27 GB`. Проверка: в `AD-001` и `RISK-003` явно описана изоляция `XDG_DATA_HOME` и очистка временного каталога в `finally`. Связано с RW-006, но статус данной находки CONSENTED non-blocking сохранён; OPENCODE_MODELS_PATH не терять.",
      "reason": "CONSENTED (non-blocking, усиливает митигацию `F-006`); правило: Модификатор режима `architecture` (снижение ресурсной конкуренции при росте нагрузки); якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:996` (`#AD-001`, `#RISK-003`); evidence: 6 процессов `opencode serve` и фоновый сервис PID 43288 конкурируют за общую `~/.local/share/opencode/opencode.db` (`2.27 GB`, `[F-28]`).; источник: Seat 2 (`gemini-4-argon-high`, `realist`, orig `8/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-014"
      ],
      "finding_details": [
        {
          "id": "F-014",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `8/9`)",
          "status": "CONSENTED (non-blocking, усиливает митигацию `F-006`)",
          "criterion": "РИСКИ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:996` (`#AD-001`, `#RISK-003`)",
          "rule": "Модификатор режима `architecture` (снижение ресурсной конкуренции при росте нагрузки)",
          "evidence": "6 процессов `opencode serve` и фоновый сервис PID 43288 конкурируют за общую `~/.local/share/opencode/opencode.db` (`2.27 GB`, `[F-28]`).",
          "expected_fix": "зафиксировать в `AD-001` / `RISK-003` решение по per-spawn временному `XDG_DATA_HOME` (с удалением в `finally`) при сохранении `OPENCODE_MODELS_PATH`, чтобы исключить `SQLITE_BUSY` на `opencode.db` `2.27 GB`.",
          "acceptance": "в `AD-001` и `RISK-003` явно описана изоляция `XDG_DATA_HOME` и очистка временного каталога в `finally`.",
          "priority": "non-blocking"
        }
      ]
    },
    {
      "id": "FU-002",
      "text": "Architect, по своему решению: добавить в `deferred[]` явную запись об оформлении `docs/adr/0005-zen-serve-realtime-reasoning.md` и обновлении `docs/adr/INDEX.md` отдельной задачей вне замороженного скоупа `handoff-architect.md` §10. Проверка: в `deferred[]` пакета присутствует явная запись про `ADR-0005` с обоснованием границ скоупа.",
      "reason": "CONSENTED (non-blocking); правило: `aisdlc-gcge/AGENTS.md` п. 13 и `aisdlc-gcge/skills/architecture.md` («ADR и proposals»); якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1648` (`#materialization`, `#deferred`); evidence: `materialization` пуст, а в `deferred` не указана причина переноса выпуска `docs/adr/0005-*` за пределы текущего скоупа `handoff-architect.md` §10.; источник: Seat 2 (`gemini-4-argon-high`, `realist`, orig `9/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-015"
      ],
      "finding_details": [
        {
          "id": "F-015",
          "source_seat": "Seat 2 (`gemini-4-argon-high`, `realist`, orig `9/9`)",
          "status": "CONSENTED (non-blocking)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:1648` (`#materialization`, `#deferred`)",
          "rule": "`aisdlc-gcge/AGENTS.md` п. 13 и `aisdlc-gcge/skills/architecture.md` («ADR и proposals»)",
          "evidence": "`materialization` пуст, а в `deferred` не указана причина переноса выпуска `docs/adr/0005-*` за пределы текущего скоупа `handoff-architect.md` §10.",
          "expected_fix": "добавить в `deferred[]` явную запись об оформлении `docs/adr/0005-zen-serve-realtime-reasoning.md` и обновлении `docs/adr/INDEX.md` отдельной задачей вне замороженного скоупа `handoff-architect.md` §10.",
          "acceptance": "в `deferred[]` пакета присутствует явная запись про `ADR-0005` с обоснованием границ скоупа.",
          "priority": "non-blocking"
        }
      ]
    },
    {
      "id": "FU-003",
      "text": "Architect, по своему решению: зафиксировать в `risks` принятый остаточный риск межпровайдерского реплея `reasoning_content` при ручном переключении модели в середине сессии DSH и минимизацию длины/частоты статусов `[мост]`. Проверка: риск и митигация явно отражены в `risks[]` пакета.",
      "reason": "CONSENTED (non-blocking); правило: полнота реестра рисков (`[F-33]`, `[F-38]`, `[F-39]`); якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-002`, `#risks`); evidence: строки `[мост]` сохраняются в журнале сессии DSH и при смене провайдера в середине чата (например, на `deepseek-account`) могут попасть во входящий `reasoning_content` другого провайдера.; источник: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `5/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-020"
      ],
      "finding_details": [
        {
          "id": "F-020",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `5/9`)",
          "status": "CONSENTED (non-blocking)",
          "criterion": "РИСКИ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#AD-002`, `#risks`)",
          "rule": "полнота реестра рисков (`[F-33]`, `[F-38]`, `[F-39]`)",
          "evidence": "строки `[мост]` сохраняются в журнале сессии DSH и при смене провайдера в середине чата (например, на `deepseek-account`) могут попасть во входящий `reasoning_content` другого провайдера.",
          "expected_fix": "зафиксировать в `risks` принятый остаточный риск межпровайдерского реплея `reasoning_content` при ручном переключении модели в середине сессии DSH и минимизацию длины/частоты статусов `[мост]`.",
          "acceptance": "риск и митигация явно отражены в `risks[]` пакета.",
          "priority": "non-blocking"
        }
      ]
    },
    {
      "id": "FU-004",
      "text": "Architect, по своему решению: включить `ruff format --check` на целевых файлах в `VER-004`. Проверка: `VER-004` содержит `ruff format --check`. Пересекается с RW-012; это согласованный non-blocking, не самостоятельное blocking-условие.",
      "reason": "CONSENTED (non-blocking, покрывается расширением `VER-004` в `F-013`); правило: `aisdlc-gcge/skills/architecture.md` Python overlay (`ruff format --check`); якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`); evidence: `VER-004` не включает `ruff format --check` на изменённых файлах.; источник: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `6/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-021"
      ],
      "finding_details": [
        {
          "id": "F-021",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `6/9`)",
          "status": "CONSENTED (non-blocking, покрывается расширением `VER-004` в `F-013`)",
          "criterion": "ПОЛНОТА",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`)",
          "rule": "`aisdlc-gcge/skills/architecture.md` Python overlay (`ruff format --check`)",
          "evidence": "`VER-004` не включает `ruff format --check` на изменённых файлах.",
          "expected_fix": "включить `ruff format --check` на целевых файлах в `VER-004`.",
          "acceptance": "`VER-004` содержит `ruff format --check`.",
          "priority": "non-blocking"
        }
      ]
    },
    {
      "id": "FU-005",
      "text": "Architect, по своему решению: зафиксировать в `AD-001` / `VER-004` требование типизировать новый код через `object` + type-narrowing / `TypedDict` без роста `reportAny`/`reportExplicitAny`. Проверка: `VER-004` проверяет невозрастание baseline предупреждений `reportAny`/`reportExplicitAny` в `server.py`. Исходный Seat 3 F-7 дополнительно предложил отдельный serve_transport.py через delta allowlist. Это лишь вариант вне текущего allowlist, не разрешение создавать модуль; смена scope требует отдельного решения владельца. Леджер предлагает типизацию внутри текущей зоны.",
      "reason": "CONSENTED (non-blocking); правило: соблюдение правил типизации `python-standards.md` без раздувания `Any`; якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`, `#AD-001`); evidence: новый код `serve`-клиента и парсера JSON в `server.py` должен использовать `TypedDict` / `object` с явным сужением типов (`isinstance`), чтобы не увеличивать счётчики `reportAny`/`reportExplicitAny` `basedpyright`.; источник: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `7/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-022"
      ],
      "finding_details": [
        {
          "id": "F-022",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `7/9`)",
          "status": "CONSENTED (non-blocking)",
          "criterion": "РЕАЛИЗУЕМОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json:886` (`#VER-004`, `#AD-001`)",
          "rule": "соблюдение правил типизации `python-standards.md` без раздувания `Any`",
          "evidence": "новый код `serve`-клиента и парсера JSON в `server.py` должен использовать `TypedDict` / `object` с явным сужением типов (`isinstance`), чтобы не увеличивать счётчики `reportAny`/`reportExplicitAny` `basedpyright`.",
          "expected_fix": "зафиксировать в `AD-001` / `VER-004` требование типизировать новый код через `object` + type-narrowing / `TypedDict` без роста `reportAny`/`reportExplicitAny`.",
          "acceptance": "`VER-004` проверяет невозрастание baseline предупреждений `reportAny`/`reportExplicitAny` в `server.py`.",
          "priority": "non-blocking"
        }
      ],
      "decision_required_human": true
    },
    {
      "id": "FU-006",
      "text": "Architect, по своему решению: предусмотреть опциональный файл-флаг отключения `serve` (`OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`, проверка `Path.exists()` на входе запроса за $O(1)$) в дополнение к env-переменной, чтобы в проде `:9883` можно было мгновенно выключить `serve` на `H9` без рестарта сервиса. Проверка: в `AD-001.details.configuration` и `evolution.rollback` описан мгновенный kill-switch без рестарта и его проверка в `VER-005`. Связано с RW-009, но остаётся самостоятельной non-blocking рекомендацией. Никаких фактических изменений ~/.dsh на этом проходе.",
      "reason": "CONSENTED (non-blocking); правило: быстрый операционный kill-switch без рестарта сервиса; якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#evolution`, `#AD-001`); evidence: env-флаг требует перезапуска процесса моста для переключения на живом `:9883`; `stat()` легковесного файла-переключателя (например, `~/.dsh/bridges/opencode-zen-bridge/disable-serve` или env-пути) даёт мгновенный kill-switch без рестарта LaunchAgent.; источник: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `8/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-023"
      ],
      "finding_details": [
        {
          "id": "F-023",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `8/9`)",
          "status": "CONSENTED (non-blocking)",
          "criterion": "СООТВЕТСТВИЕ КОНТЕКСТУ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#evolution`, `#AD-001`)",
          "rule": "быстрый операционный kill-switch без рестарта сервиса",
          "evidence": "env-флаг требует перезапуска процесса моста для переключения на живом `:9883`; `stat()` легковесного файла-переключателя (например, `~/.dsh/bridges/opencode-zen-bridge/disable-serve` или env-пути) даёт мгновенный kill-switch без рестарта LaunchAgent.",
          "expected_fix": "предусмотреть опциональный файл-флаг отключения `serve` (`OPENCODE_ZEN_BRIDGE_SERVE_DISABLE_FILE`, проверка `Path.exists()` на входе запроса за $O(1)$) в дополнение к env-переменной, чтобы в проде `:9883` можно было мгновенно выключить `serve` на `H9` без рестарта сервиса.",
          "acceptance": "в `AD-001.details.configuration` и `evolution.rollback` описан мгновенный kill-switch без рестарта и его проверка в `VER-005`.",
          "priority": "non-blocking"
        }
      ]
    },
    {
      "id": "FU-007",
      "text": "Architect, по своему решению: перебалансировать подбюджеты `R-BULK-I1` (единый pre-spawn admission `<= 5.0` с + реалистичные `ready=3.0` с и `session_setup=2.0` с → сумма `51.6 <= 54.0` с, запас `2.4` с). Проверка: сумма `R-BULK-I1` записана с явной формулой и запасом `>= 2.0` с. Пересекается с RW-007; статус CONSENTED non-blocking сохранён.",
      "reason": "CONSENTED (non-blocking, закрывается перебалансировкой `R-BULK-I1` в `F-008`); правило: устойчивость запаса `R-BULK-I1`; якорь: `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#R-BULK-I1`); evidence: запас `53.7` против `54.0` с составляет всего `0.3` с.; источник: Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `9/9`). Не блокирует Architect/Coder по arch-council.md §3.",
      "source_findings": [
        "F-024"
      ],
      "finding_details": [
        {
          "id": "F-024",
          "source_seat": "Seat 3 (`claude-sonnet-5-5-high`, `visionary`, orig `9/9`)",
          "status": "CONSENTED (non-blocking, закрывается перебалансировкой `R-BULK-I1` в `F-008`)",
          "criterion": "РЕАЛИЗУЕМОСТЬ",
          "locations": "`.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json` (`#R-BULK-I1`)",
          "rule": "устойчивость запаса `R-BULK-I1`",
          "evidence": "запас `53.7` против `54.0` с составляет всего `0.3` с.",
          "expected_fix": "перебалансировать подбюджеты `R-BULK-I1` (единый pre-spawn admission `<= 5.0` с + реалистичные `ready=3.0` с и `session_setup=2.0` с → сумма `51.6 <= 54.0` с, запас `2.4` с).",
          "acceptance": "сумма `R-BULK-I1` записана с явной формулой и запасом `>= 2.0` с.",
          "priority": "non-blocking"
        }
      ]
    }
  ],
  "excluded": [],
  "findings_total": 24,
  "do_not_change": [
    "Выбор Гибрид C/A1: одноразовый serve v2 на попытку, единый canonical event source для SSE и JSON, legacy run как обратимый путь; пересмотр только согласованных деталей из instructions[].",
    "Публичные OpenAI HTTP endpoints, порт :9883, auth, schema ответов, прямой Google route и test_google_direct.py.",
    "Замороженные analysis/zen-realtime-reasoning/**, bridges/muse-bridge/**, общие конфиги opencode/georouter, существующая opencode.db, зависимости и lockfiles.",
    "Продуктный allowlist без самовольного расширения: bridges/opencode-zen-bridge/server.py, tests/test_step_interruption.py и tests/test_realtime_reasoning.py относительно каталога моста; tests/test_run_env.py и start.sh не изменять.",
    "MAX_TOTAL_SPAWNS=3, общие RetryBudget/FAIL_RETRY_LIMIT, slot admission и лимиты deploy 6/12; не обходить security, cancel/cleanup, memory/SQLite rollout gates ради формального PASS.",
    "Модельные reasoning bytes, fast Simple greeting., synthetic provenance, отсутствие статусов в JSON reasoning/prompt/usage, отсутствие встроенного allow для инструментов.",
    "На текущем rework меняется только Architecture Packet; Stage3 код/тесты и живая ~/.dsh приёмка H0..H9 не выполняются и не объявляются пройденными."
  ],
  "coder_entry": "fix-from-panel",
  "iteration_budget_note": "Архитектурный handoff cycle 1 a1 → Architect. Константа coder_entry не означает запуск Coder. Architect ведёт delta-plan по 14 RW-ID: каждый закрыть проверяемым delta-пакетом либо no_architecture_delta с evidence для следующего полного арх-прохода. 7 FU не блокируют. Summarizer не разрешает противоречия судей и не выдаёт ARCH_PANEL_PASS/ACCEPT; Coder допускается только последующими гейтами оркестратора.",
  "artifact_sha256": "e620a689a0d665a2c7979eba5a7073af41d9ca9473ea906ff9cee316fa0c7e02",
  "recipient": "Architect",
  "translation_notes": [
    "Покрытие всего батча: 24 уникальных F-id ровно по одному разу в source_findings; детали каждого блока сохранены в finding_details. Текстовые ссылки между находками не являются повторным размещением.",
    "Сводка verdict-a1.md сообщает 16 blocking и 8 non-blocking; фактические priority/status 24 блоков ledger дают 17 blocking и 7 non-blocking. Применены статусы конкретных F-блоков: F-002/F-007/F-018 объединены по общей tool-policy причине, F-011/F-016 объединены по неверной ссылке. Получено 14 RW и 7 FU, excluded пуст.",
    "F-001 и F-008 оставлены раздельно: барьер доставки/fallback и расширение startup/session wire-контракта; разные обязательства не скрыты общей склейкой. F-014/F-021/F-024, хотя связаны с blocking, оставлены non-blocking.",
    "Сводка заявляет отсутствие конфликтов, но оригинальные r1 различаются по fallback-barrier, предварительному policy switching, default enable, минимальному session budget и baseline type errors; конкретные позиции сохранены в evidence соответствующих RW. Это не новый вердикт summarizer.",
    "reviewer.json в арх-проходе не создаётся, не требуется и не является ASK. Проверенный hash Architecture Packet совпадает с task.architecture_gate.packet_sha256 и artifact hash всех трёх судей."
  ]
}
ARTIFACT_END>>>

КОНТЕКСТ:
Ниже приложены целиком формулировка цели владельца, конверт задачи (`task.json`), полный аналитический пакет этапа 1 (`handoff-architect.md`, `evidence-ledger.md`, `research-plan.md`, `open-questions.md`, `handoff-qa.md`), а также стандарты проекта и Python-архитектуры (`aisdlc-gcge/AGENTS.md`, `aisdlc-gcge/skills/architecture.md`, `aisdlc-gcge/agents/scope-and-contracts.md`), соблюдение которых (включая все пункты `Definition of Done overlay` и все 5 групп Highload & Resilience гейтов `HL-ENV-01`, `C-MULT-I1..I5`, `S-HERD-I1..I5`, `H-CPU-I1..I5`, `R-BULK-I1..I5` + `T-LIFE/v1` + `O-EXIT/v1` + `M-SEM/v1`) входит в твои обязательные проверки. Примечание по самодостаточности ссылок внутри пакета: упоминания `EVD-060` («Текущий Brief Stage 2, Steps 1–4») и `route-manifest.json` внутри `architecture-packet.json` обозначают сводный бриф запуска Архитектора, составленный исключительно из приложенных ниже первичных файлов (`goal.md`, `task.json`, `analysis/zen-realtime-reasoning/*.md`, `handoff/panel-rework-brief-arch-a1.json`) и метаданных `preset=analyst-teamlead, criticality=S2, profile=python-aisdlc-gcge`, и не содержат никаких внешних требований вне вложенных артефактов:
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
<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/task.json sha256=857c9d4470261caaa90449aceda17d3258117160b7d2bb8415a970efaaac705d
{
  "task_id": "zen-realtime-reasoning",
  "run_id": "analyst-teamlead-zen-realtime-reasoning-20261025",
  "preset": "analyst-teamlead",
  "setup": "default",
  "criticality": "S2",
  "architecture_gate": {
    "packet_sha256": "c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d",
    "verification_surface_sha256": "66e68ca767d07b24b7afacb40f8c84abde9f26837a50d38ccba03a3824a5ce84",
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
<<<ARTIFACT analysis/zen-realtime-reasoning/open-questions.md sha256=2b584b43026f570898d9ced218e0d989f2d1f460dded380ad38c0df6defba79f
# Open Questions: zen-realtime-reasoning

Дата: 2026-10-25 (MSK). Блокеров нет: ни один вопрос не останавливает ветку Архитектора. Все вопросы класса «МОЖНО ПРОДОЛЖИТЬ»;
статус закрытия (`RESOLVED` — закрыт фактами ledger, `DEFERRED` — отложен с рабочим допущением) записан префиксом в поле «что мешает закрыть».
Формат строки: `OPEN-NN | класс | вопрос | что мешает закрыть | кто нужен | риск | допущение`.

OPEN-01 | МОЖНО ПРОДОЛЖИТЬ | Отправляет ли DSH размышление обратно мосту и что мост с ним делает | RESOLVED: DSH кладёт thinking в assistant-сообщение полем `reasoning_content`, мост его игнорирует (F-38, F-07) | никто | синтетические статусные строки не попадут в промпт модели | не требуется
OPEN-02 | МОЖНО ПРОДОЛЖИТЬ | Почему красны три теста базовой линии: загрязнение теста или реальная ошибка бюджета | RESOLVED: два теста ждут 4 запуска при потолке `MAX_TOTAL_SPAWNS=3` (красные и в изоляции), третий красный из-за общего `_RetryBudget` на класс (F-47, F-48, F-49) | никто | красная базовая линия блокирует Full Suite Gate | не требуется
OPEN-03 | МОЖНО ПРОДОЛЖИТЬ | Есть ли в репозитории решение совместимости «потоковый транспорт плюс тесты на поддельном CLI» | RESOLVED: muse-bridge держит serve как основной путь и тихо падает на exec при `ServeUnavailable` (F-40) | никто | паттерн применим как факт, выбор за Архитектором | не требуется
OPEN-04 | МОЖНО ПРОДОЛЖИТЬ | Входит ли исправление трёх красных тестов базовой линии в MR этой фичи | DEFERRED: решение о границах MR принимает владелец вместе с Архитектором | владелец, Архитектор | MR не пройдёт Full Suite Gate при красной базе | Входит: ожидание 4 приводится к потолку 3 и бюджет повтора изолируется на тест, поведение продукта не меняется
OPEN-05 | МОЖНО ПРОДОЛЖИТЬ | Какие заголовки или ключ нужны прямому анонимному HTTP-SSE к Zen (Option B) | DEFERRED: два PoC без `Authorization` дали HTTP 429 `FreeUsageLimitError`, а квота исчерпана до около 03:00 MSK 2026-10-26 (F-24, F-25) | Architect и Coder-спайк после сброса лимита | Option B может оказаться неосуществимым без перехвата заголовков `opencode` | Option B считается «выполнимо с условиями» и не выбирается без успешного PoC
OPEN-06 | МОЖНО ПРОДОЛЖИТЬ | Совместима ли пер-запросная ротация чистых IP (пул ProxyRack) с одним долгоживущим `opencode serve` | DEFERRED: у `serve` один набор переменных прокси на процесс, а поведение прокси при `baseURL` на loopback-georouter не проверено (F-15, F-26) | Architect | общий IP упирается в дневной лимит (22 срабатывания за день, F-32) | Предполагается один короткоживущий `serve` на запрос (старт 109 мс, F-20), чтобы ротация сохранялась
OPEN-07 | МОЖНО ПРОДОЛЖИТЬ | Как в режиме serve изолируются встроенные инструменты `opencode` и как события `session.tool.*` соответствуют текущему `tool_use` | DEFERRED: схема `permissions` есть (F-22), живой прогон невозможен из-за free-limit (F-23) | Architect, Coder | модель выполнит встроенный инструмент вместо эмуляции DSH | Нужна явная политика `deny` для всех встроенных инструментов и адаптер событий к текущему формату `tool_use`
OPEN-08 | МОЖНО ПРОДОЛЖИТЬ | Выдержат ли шесть параллельных процессов serve блокировки SQLite `opencode.db` 2.27 GB и бюджет памяти | DEFERRED: измерен только простаивающий serve (RSS 152 MiB, F-20), нагрузочный прогон не делался | QA, Coder | `database is locked` при параллельном старте (прецедент в комментарии к `FAIL_RETRY_LIMIT`) | Верхняя оценка 192 MiB на процесс и сохранение `_StartupGate` и `SPAWN_RATE_PER_S`
OPEN-09 | МОЖНО ПРОДОЛЖИТЬ | Каков TTFT через serve на промпте около 103 KB как в инциденте | DEFERRED: квота исчерпана (F-23), повторить после сброса лимита около 03:00 MSK 2026-10-26 | QA | цель отзывчивости может не достигаться на тяжёлых промптах | Берётся замер Zone B на коротком промпте (первая дельта 1811 мс, F-19)
OPEN-10 | МОЖНО ПРОДОЛЖИТЬ | Что именно блокирует холодный `opencode run --standalone` до сети (у PID 11488 нет TCP-соединений) | DEFERRED: первопричина (SQLite, каталог моделей, фоновый сервис) не установлена (F-30) | Coder-спайк | зависания могут повторяться на новом транспорте | Митигация независима от причины: watchdog первого события и паузы между чанками с убийством группы процессов
OPEN-11 | МОЖНО ПРОДОЛЖИТЬ | Какие числовые цели отзывчивости принимает владелец | DEFERRED: владелец сформулировал «отличную отзывчивость» без чисел | владелец | критерии приёмки останутся субъективными | Первая видимая строка не позже 1.0 с, первая реальная дельта размышления не позже 3.0 с на здоровом апстриме, пауза между чанками не больше 15 с, отсутствие первого события не больше 20 с до явной ошибки или повтора
OPEN-12 | МОЖНО ПРОДОЛЖИТЬ | Допустимы ли синтетические статусные строки моста в `reasoning_content` | DEFERRED: DSH сохраняет их в журнале сессии и показывает в строке Think (F-37, F-39), мост при реплее их игнорирует (F-07) | владелец, Architect | статусный текст смешивается с мышлением модели в транскрипте | Допустимы короткие строки, оканчивающиеся символом новой строки, с префиксом «[мост]»
OPEN-13 | МОЖНО ПРОДОЛЖИТЬ | Допустимо ли менять текст размышления модели, вставляя переводы строк для обновления inline-превью | DEFERRED: превью требует `\n` (F-37), а изменение текста затрагивает журнал и реплей | владелец, Architect | искажение размышления модели | Текст модели не изменяется, живость обеспечивают только отдельные статусные строки
OPEN-14 | МОЖНО ПРОДОЛЖИТЬ | Как показывать размышление повторной попытки, если часть размышления уже отдана клиенту | DEFERRED: при потоковой выдаче дубли неизбежны, текущий `dedup_prefix` работает только для видимого текста | Architect | двоение блока Think в UI | Размышление не дедуплицируется, между попытками вставляется отдельная статусная строка
OPEN-15 | МОЖНО ПРОДОЛЖИТЬ | Как трактовать метки гейтов из брифа `R-OUT`, `M-CONF`, `F-DEG`, `S-SEC`, `X-BOUND` | DEFERRED: в каноне `aisdlc-gcge/agents/architecture.md` этих меток нет, там `C-MULT`, `S-HERD`, `H-CPU`, `R-BULK`, `T-LIFE`, `O-EXIT`, `M-SEM` | владелец брифа | расхождение критериев приёмки гейтов | Заполнены 7 канонических гейтов и отдельная таблица доменных осей брифа с трактовкой аналитика
OPEN-16 | МОЖНО ПРОДОЛЖИТЬ | Дают ли режимы `opencode run --server <url>` и `--format default` потоковую выдачу | DEFERRED: проверялся только `--format json`, а справка показывает два формата без дельт (F-28) | Coder-спайк | пропущен более дешёвый путь | Не дают, путь через serve считается единственным готовым реалтаймом
OPEN-17 | МОЖНО ПРОДОЛЖИТЬ | Как синхронизировать копию `~/.dsh/bridges/opencode-zen-bridge/` и перезапустить LaunchAgent после MR | DEFERRED: деплой вне объёма анализа, развёрнутая копия сейчас идентична репозиторию (F-34) | владелец | живая проверка пойдёт на старой копии | Побайтовая сверка и перезапуск `com.user.dsh-opencode-zen-bridge` входят в живую приёмку

## ВОПРОСЫ ВЛАДЕЛЬЦУ

1. [МОЖНО ПРОДОЛЖИТЬ] Принимаете ли числовые цели отзывчивости (первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с)? Почему нужен: от них зависят пороги watchdog и критерии приёмки. Допущение: значения приняты. После ответа: пороги уходят в конфигурацию.
2. [МОЖНО ПРОДОЛЖИТЬ] Допустимы ли статусные строки моста с префиксом «[мост]» внутри блока Think? Почему нужен: они сохраняются в журнале DSH. Допущение: допустимы. После ответа: Architect фиксирует формат.
3. [МОЖНО ПРОДОЛЖИТЬ] Входит ли исправление трёх красных тестов базовой линии в этот MR? Почему нужен: от этого зависит Full Suite Gate. Допущение: входит. После ответа: QA включает правки тестов в план.
ARTIFACT_END>>>
<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-qa.md sha256=d78c3855467d1d7c7a97a0a62ab7f8b79b311b48665a0327d04cffaa1ecf0e3b
# Handoff to QA: реалтайм-размышление и отзывчивость `opencode-zen-bridge` (zen-realtime-reasoning)

Дата: 2026-10-25 (MSK). Автор: System Analyst (Stage 1). Потребители: QA и Coder (написание тестов red→green), Reviewer, живая приёмка.
Требования — `REQ-001..REQ-020` в `handoff-architect.md`; факты — `F-01..F-49` в `evidence-ledger.md`; вопросы — `OPEN-01..OPEN-17` в `open-questions.md`.
Архитектурный транспорт (serve, прямой HTTP, гибрид) выбирает Architect; сценарии ниже сформулированы относительно «нового быстрого транспорта» и не зависят от выбора.

## 1. Тестовые контуры и команды

| ID | Контур | Команда или способ | Состояние |
|---|---|---|---|
| VER-001 | Основной набор | `cd bridges/opencode-zen-bridge && uvx pytest -q -p no:cacheprovider tests/` | 378 тестов, на ветке красные 3 (F-42, F-45) |
| VER-002 | Только файл прерываний | `uvx pytest -q -p no:cacheprovider tests/test_step_interruption.py` | те же 3 красных (F-46) |
| VER-003 | Порядконезависимость | `uvx --with pytest-randomly pytest -q -p no:cacheprovider -p randomly tests/test_step_interruption.py` (3 разных `-p randomly_seed`) | после исправления базы красных нет при любом порядке |
| VER-004 | Fake-CLI | подмена `server.OPENCODE_BIN` скриптом с JSON-событиями (F-43), хелпер `allow_child_env` | рабочий |
| VER-005 | Fake-transport (новый) | локальный HTTP-сервер стандартной библиотеки, отдающий SSE по схеме транспорта | нужно написать |
| VER-006 | Живой мост | `http://127.0.0.1:9883` (LaunchAgent `com.user.dsh-opencode-zen-bridge`) | работает (F-34), квота Zen исчерпана (F-23) |
| VER-007 | Живой DSH | DSH Desktop, модель `DeepSeek V4.1 Flash (Zen) High`, `opencode-zen-bridge` | доступен (F-35) |

Базовой линией считается только `uvx pytest`: запуск с командой `pytest` и `python3 -m unittest discover` из корня не работают (F-45).
Ни один существующий тест не измеряет реальное время прихода чанков (F-44): `_post` читает ответ целиком `resp.read()`.

## 2. Красная базовая линия (до начала разработки)

| Тест | Симптом | Причина по фактам | Что проверять после правки |
|---|---|---|---|
| `test_unmapped_retries_do_not_exhaust_incomplete_budget_json` | `2 != 4` в полном прогоне, `3 != 4` в изоляции | ожидание 4 запусков при потолке `MAX_TOTAL_SPAWNS=3` (F-47); в полном прогоне добавляется исчерпание `_RetryBudget` (F-48) | ожидание согласовано с потолком 3 либо потолок задан тестом явно; результат одинаков в изоляции и в полном прогоне |
| `test_unmapped_retries_do_not_exhaust_incomplete_budget_stream` | `2 != 4` | то же | то же |
| `test_unmapped_then_error_stops_proc_json` | `1 != 2` только в составе класса, в изоляции зелёный | общий `_RetryBudget` одного `Server` на класс (`setUpClass`), токены расходуются предыдущими тестами (F-48) | бюджет повтора изолирован на тест (новый `_Resilience` или сброс токенов в `setUp`) |

Ни один тест не меняет `MAX_TOTAL_SPAWNS` (F-49); поведение продукта правкой этих тестов не меняется (OPEN-04: допущение «входит в MR»).
Контрольный критерий: три прогона VER-003 с разными seed и один прогон VER-001 — без красных.

## 3. Сценарии red→green (регрессионные тесты ДО фикса)

Обозначения: `FakeUpstream` — управляемый источник событий (fake-CLI либо fake-transport VER-005), у которого каждое событие выпускается по сигналу `threading.Event`
либо после заданной паузы; тест читает клиентский сокет построчно (`http.client` + `readline`, либо сырой `socket`) и фиксирует `time.monotonic()` прихода каждого чанка.

### 3.1. Реалтайм прихода чанков (REQ-001, REQ-020, AC-001, AC-002, AC-026)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-001 | `FakeUpstream` отдаёт 10 дельт размышления с паузой 150 мс и после десятой блокируется на `Event`, не закрывая поток | клиент получил все 10 `reasoning_content`-чанков до того, как тест освободил `Event`; интервалы между соседними чанками меньше 500 мс | да: новый транспорт отсутствует; на legacy-пути блок приходит целиком в конце (F-17) |
| QA-002 | то же для `content`: 17 text-дельт с паузой 114 мс, поток открыт | чанки `content` приходят инкрементально, сумма равна исходному тексту | да |
| QA-003 | замер накладных расходов: метка отправки дельты апстримом и метка записи в клиентский сокет | разница не больше 250 мс (AC-002), 50 дельт, p95 | да |
| QA-004 | характеризующий тест legacy: fake-CLI печатает JSON-строки `reasoning` с паузами и держит процесс | каждая строка видна клиенту без ожидания конца (текущее поведение F-05); тест страхует регресс, зелёный сразу | нет (контрольный) |
| QA-005 | порядок событий: размышление, затем текст, затем usage и `[DONE]` | порядок и `finish_reason` сохранены, `usage` присутствует (REQ-014, AC-019) | да |

### 3.2. Первая видимая реакция и контракт DSH (REQ-004, REQ-005, AC-005..AC-007)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-010 | `FakeUpstream` полностью молчит 5 с | первый чанк с непустым `reasoning_content` приходит не позже 1.0 с от запроса (сейчас только роль-чанк и keepalive с пустым `content` раз в 15 с, F-03, F-04) | да |
| QA-011 | формат статусной строки | строка начинается с «[мост]», не пустая после `strip()`, оканчивается `\n`; помощник `dsh_visible(text)` повторяет правило `blockIsVisible` (`text.strip() != ""`, F-37) | да |
| QA-012 | контракт превью | помощник `dsh_preview_ready(text)` возвращает истину только при наличии `\n` в завершённом абзаце (F-37); первая статусная строка проходит | да |
| QA-013 | текст модели не искажён | склейка `reasoning_content` без строк с префиксом «[мост]» побайтово равна исходному размышлению модели (AC-006, OPEN-13) | да |
| QA-014 | реплей истории | сообщение assistant с `reasoning_content`, содержащим статусные строки, не попадает в результат `_messages_to_prompt` (F-07, F-38, AC-007) | нет (контрольный: игнорирование уже есть) |
| QA-015 | пустая дельта и пробельная дельта | чанки с `reasoning_content` из пробелов не считаются «видимыми», статусная строка не подменяется ими | да |
| QA-016 | keepalive | пустой keepalive остаётся валидным парсируемым чанком (F-04), но не заменяет статусную строку | нет (контрольный) |

### 3.3. Watchdog, зависания, повторы (REQ-006..REQ-009, AC-008..AC-014)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-020 | процесс не выдаёт ни одного события | за порог first-event плюс 2 с группа убита, `exit_reason=first_event_timeout`, затем повтор или ошибка клиенту (пороги уменьшены переменными окружения до 1-2 с) | да (F-09: единственный потолок 1800 с) |
| QA-021 | события есть, токенов нет | `first_token_timeout` по порогу, повтор в пределах потолка | да |
| QA-022 | после первого токена поток замолкает | `stall_timeout` по порогу паузы, остановка и классификация | да |
| QA-023 | watchdog и потолок повторов | при подряд зависающих попытках запусков не больше 3 (`MAX_TOTAL_SPAWNS`), пауза между ними Full Jitter 0.5-2.0 с, `_RetryBudget` не уходит в минус (F-11, AC-013) | да |
| QA-024 | отдача размышления до зависания | после зависания второй попытки между попытками ровно одна статусная строка «[мост] повтор…», размышление не дедуплицируется (AC-014, OPEN-14) | да |
| QA-025 | осиротевшие процессы | fake-CLI порождает дочерний `sleep`; после watchdog, таймаута и ошибки ни один процесс группы не жив (проверка `os.killpg(pgid, 0)` и `ps`) (AC-011, F-14, F-30) | частично: убийство группы есть, а срабатывания по зависанию нет |
| QA-026 | отключение клиента | клиент закрывает сокет при полной тишине апстрима: процессы остановлены не позже 7 с, `exit_reason=client_gone` (ход 1 образца обнаруживал за 24.4 с, F-33, AC-011, AC-012) | да |
| QA-027 | `etype=error` до и после первого токена | поведение `test_step_interruption.py` сохраняется на новом транспорте: ранняя ошибка не убивает процесс, поздняя транзиентная ретраится, детерминированная (400, 401, 403, 404, 422) не ретраится | нет (контрольные, перенос на новый транспорт) |
| QA-028 | `FreeUsageLimitError` 429 | классифицируется как транзиентный отказ апстрима, не приводит к многоминутной тишине, ошибка клиенту содержит читаемое сообщение (F-23..F-25, F-32) | да |
| QA-029 | старт `startup_gate_timeout` | при ожидании замка более 5 с запуск идёт без замка (fail-open), статусная строка сообщает об ожидании (F-10, F-32) | частично |

### 3.4. Парсер инструментов на потоковых дельтах (REQ-010, REQ-011, AC-015, AC-016)

| ID | Сценарий | Проверка | Красный на текущем коде |
|---|---|---|---|
| QA-030 | текст перед `<tool_invoke>` приходит дельтами | текст вне тега выдаётся до прихода закрывающего тега, удерживается не более `len("<tool_invoke>")-1` символов (F-06) | нет (контрольный на уровне парсера) |
| QA-031 | перебор всех границ разбиения на дельты для фикстур `test_tool_emulation.py` и `test_lenient_tool_call.py` | набор `tool_calls` и `content` идентичны подаче целым текстом | нет (контрольный) |
| QA-032 | сквозной потоковый путь нового транспорта с `emulate_tools` | те же результаты на уровне SSE-ответа | да |
| QA-033 | оба тега `<tool_call>` и `<tool_invoke>` внутри потока | вызовы распознаются, сырой тег не протекает в `content` (REQ-010) | да (на новом транспорте) |
| QA-034 | завершение шага с вызовом | процесс или сессия остановлены, `finish_reason="tool_calls"`, последующий хвост не отдаётся (F-05) | да (на новом транспорте) |
| QA-035 | все сценарии `test_step_interruption.py` (107 тестов) на фейковом потоке дельт | зелёные (AC-016) | да |
| QA-036 | встроенный инструмент `opencode` в потоке | событие приводится к `unmapped`/`native`, повтор и `finish_reason` как на legacy (REQ-012, AC-017) | да |

### 3.5. Совместимость, секреты, наблюдаемость (REQ-002, REQ-003, REQ-015, REQ-016, REQ-018)

| ID | Сценарий | Проверка |
|---|---|---|
| QA-040 | kill-switch выключает новый транспорт | все 378 существующих тестов зелёные без правок (кроме OPEN-04), `H-CPU-I3`: выключенный путь не делает лишней работы |
| QA-041 | форма публичного ответа | `/health`, `/v1/models`, чанки OpenAI SSE, `finish_reason`, `usage` совпадают с эталонными фикстурами (AC-003) |
| QA-042 | `test_google_direct.py` (52 теста) | зелёные без правок (REQ-018, F-16) |
| QA-043 | секреты | `bridge.log` и тело ответов не содержат пароля `opencode serve`, значений `apiKey`, кредов прокси (AC-020) |
| QA-044 | `O-EXIT/v1` | строка содержит `transport`, `first_event_ms`, `ttft_ms` и новые `exit_reason` на каждом выходе `do_POST` (AC-021) |
| QA-045 | ротация IP | два подряд запуска получают разные записи пула (подмена `_next_standalone_proxy`, AC-018, F-15) |
| QA-046 | параллелизм | 6 одновременных запросов проходят, 7-й ждёт слот до 15 с и получает 503 при переполнении очереди из 12 (F-13) |
| QA-047 | порядконезависимость | VER-003 с тремя seed без красных (AC-023) |

## 4. Режимы отказа и краевые случаи (вход для негативных тестов)

| Случай | Источник факта | Ожидаемое поведение |
|---|---|---|
| Дневной лимит Zen (`FreeUsageLimitError`, `provider.free-limit`) | F-23, F-24, F-25 | быстрый отказ с понятным текстом, без зависания |
| `ECONNRESET` посреди ответа | F-31, F-43 | транзиентная ошибка, повтор в пределах потолка |
| Процесс без вывода и без сети | F-30 | watchdog первого события, убийство группы |
| Узел пула ProxyRack без ответа | F-31 | повтор на следующей записи пула |
| `database is locked` при параллельном старте | комментарий к `FAIL_RETRY_LIMIT` (F-11) | транзиентный повтор до `FAIL_RETRY_LIMIT` |
| Промпт около 103 KB | F-30 | передача через stdin или тело запроса целиком, без `Argument list too long` |
| Тег `<tool_invoke>` разорван между дельтами | F-06 | удержание хвоста и корректный разбор |
| Дельта из пустой строки или пробелов | F-36 | не создаёт видимого блока, не считается токеном для watchdog первого токена |
| Закрытие клиентского сокета во время размышления | F-33 | остановка процессов не позже 7 с |
| Ответ 401 от `opencode serve` | F-21 | детерминированная ошибка без повтора, пароль не в логе |
| Порт `opencode serve` занят или сервер упал | F-20 | откат на legacy-путь (REQ-003) либо явная ошибка; зависает не более порога first-event |
| Размышление с шифрованными деталями (`reasoning_details`) | F-02 | сохраняется как в текущем `parse_opencode_event` |
| 7-й параллельный запрос | F-13 | ожидание слота до 15 с, затем 503 |
| Повтор после отданного размышления | OPEN-14 | одна статусная строка между попытками |

## 5. Тестовые данные и стенды

- Fake-CLI: существующий `FAKE_OPENCODE` (F-43), переменные `FAKE_OC_MODE`, `FAKE_OC_COUNTER` и другие, `allow_child_env` пропускает их через белый список env (THREAT-003).
- Fake-transport (VER-005): локальный HTTP-сервер, отдающий события по схеме выбранного транспорта. Для варианта `opencode serve` схема событий: `session.execution.started`,
  `session.step.started`, `session.reasoning.started`, `session.reasoning.delta`, `session.reasoning.ended`, `session.text.delta`, `session.step.ended` с `tokens`,
  `session.execution.succeeded`/`session.execution.failed` (F-19, F-22); запросы `POST /api/session`, `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`,
  `DELETE /api/session/{id}`, Basic-аутентификация `opencode:<пароль>`, без заголовка 401 (F-21).
  Для варианта прямого HTTP: OpenAI SSE `data: {...}` с `delta.reasoning_content` и `delta.content`, завершение `[DONE]`, ответ 429 с телом `FreeUsageLimitError` (F-24).
- Образцы таймингов реального апстрима для эмуляции пауз: первая дельта размышления 1811 мс, интервалы 105-304 мс, первая text-дельта 3261 мс (F-19).
- Тяжёлый промпт: синтетический текст около 103000 символов из файлов репозитория (без секретов), как `prompt_chars=103088` в образце (F-30).
- Журнал сессии DSH `session.v4.jsonl.zstd`: события `assistant/attempt` с `stream[]` и временем каждого чанка (F-39) — источник для проверки TTFT по данным DSH (`zstd -dc`, разбор ключей без выгрузки текста).
- Секретов в тестовых данных нет; пароль serve в тестах генерируется на запуск.

## 6. Живая приёмка тяжёлым путём (протокол)

Лёгкая проверка (health 200, зелёные тесты, пинг свежей сессии) необходима, но не достаточна. Сдача возможна только после пунктов H1-H6.
Предусловие: квота Zen сброшена (около 03:00 MSK 2026-10-26, F-23, OPEN-09) либо есть другой допустимый маршрут. Пока квоты нет, статус — «не сдано, жду живой ход».

| Шаг | Что делается | Критерий и фиксируемый факт |
|---|---|---|
| H0 | Снимок до: `curl --noproxy '*' http://127.0.0.1:9883/health`, `git rev-parse HEAD`, `sha256` репозиторной и развёрнутой копии `server.py` (REQ-019), `ps` без `opencode run`/`serve` кроме демона PID 43288, позиция конца `bridge.log` | зафиксированы значения; копии совпадают после деплоя |
| H1 | Замер по сокету на :9883, модель `deepseek-v4.1-flash-free`, `reasoning_effort=high`, короткий промпт (умножение 37 на 43 по шагам): метка прихода каждого чанка | первая статусная строка не позже 1.0 с; первая дельта размышления не позже 3.0 с; интервалы дельт меньше 500 мс; текст идёт инкрементально; таблица `elapsed_ms` в отчёт |
| H2 | Тот же замер на промпте около 103 KB (повтор образца `prompt_chars=103088`) | первая статусная строка не позже 1.0 с; первое событие модели не позже порога first-event либо явная ошибка; нет тишины дольше 15 с без статусной строки |
| H3 | Параллелизм: 6 одновременных запросов плюс 7-й, затем повтор серии 3 раза | все 6 стартуют, 7-й ждёт или получает 503; нет `database is locked` либо он ретраится; TTFT каждого записан; процессов-сирот после серии нет (`ps`) |
| H4 | DSH Desktop (`DeepSeek V4.1 Flash (Zen) High`): сценарий образца — многошаговая цепочка с шагами `Bash`; снимки экрана на +1 с, +5 с, +35 с | строка `⚛ Think · …` видна на +1 с; на +35 с экран не состоит из одного «Deep diving for 35s ···» (образец инцидента F-30); размышление растёт по мере прихода |
| H5 | Остановка из DSH (кнопка Stop) в середине размышления | в течение 7 с `ps` без процессов группы, строка `O-EXIT/v1` с `exit_reason=client_gone`; повторный запрос работает |
| H6 | Запрещённое действие в реальном ходе: просьба создать файл встроенным инструментом модели `/tmp/probe-<ts>.txt` | файл НЕ создан самим `opencode`, DSH получил `tool_call` (или отказ), политика `deny` подтверждена фактом на диске (REQ-012); пробный файл убран |
| H7 | Инъекция сбоя на отдельном экземпляре моста (другой порт, `OPENCODE_BIN` на скрипт, который молчит, пороги watchdog уменьшены) | `first_event_timeout` и повтор в пределах 3 запусков, процессы группы убраны; боевой экземпляр :9883 не затронут |
| H8 | Регресс цепочки с эмуляцией инструментов (`glm-5.3-flash-free`, сценарий `zen-step-interruption`) | цепочка не обрывается, `finish_reason="tool_calls"` на шагах с вызовом |
| H9 | Откат: выключение нового транспорта переменной kill-switch и перезапуск | мост возвращается к legacy-поведению, `/health` 200, живой запрос проходит (временный возврат допустим, итоговое состояние восстановить) |

Шаблон сдачи:

```
ПРОВЕРЕНО ЛЁГКИМ: <health, pytest, sha256 копий>
ПРОВЕРЕНО ТЯЖЁЛЫМ: <H1-H9: какие дёрнули + таблица elapsed_ms + пути скриншотов и выдержки bridge.log>
НЕ ПРОВЕРЕНО: <остаток>   (при непустом остатке слова «готово» и «работает» запрещены)
```

## 7. Риски приёмки

- Квота Zen: PoC и живая приёмка заблокированы до сброса лимита (F-23, F-24); результаты замеров Zone B сняты до исчерпания (F-19).
- Прямой HTTP-SSE без заголовков даёт 429 (F-24, F-25): если Architect выберет прямой транспорт, нужен отдельный спайк по заголовкам (OPEN-05).
- Нагрузочные свойства `opencode serve` при 6 параллельных процессах и БД 2.27 GB не измерены (OPEN-08): включить в H3 замер RSS и FD.
- Тесты `ReasoningRow` в репозитории проверяют только контракт данных (непустой текст, `\n`); отрисовку проверяет только живой DSH (H4).
- Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/` должна быть синхронизирована до H0 (F-34, OPEN-17).

## 8. Трассируемость сценариев

| REQ | Сценарии |
|---|---|
| REQ-001 | QA-001, QA-002, QA-003, QA-005, H1 |
| REQ-002 | QA-041 |
| REQ-003 | QA-040, H9 |
| REQ-004 | QA-010, H1, H4 |
| REQ-005 | QA-011, QA-012, QA-013, QA-014, QA-015 |
| REQ-006 | QA-020, QA-029, H2, H7 |
| REQ-007 | QA-021, QA-022 |
| REQ-008 | QA-025, QA-026, H5 |
| REQ-009 | QA-023, QA-024 |
| REQ-010 | QA-030, QA-031, QA-033 |
| REQ-011 | QA-027, QA-032, QA-034, QA-035, H8 |
| REQ-012 | QA-036, H6 |
| REQ-013 | QA-045 |
| REQ-014 | QA-005 |
| REQ-015 | QA-043 |
| REQ-016 | QA-044 |
| REQ-017 | раздел 2, QA-047 |
| REQ-018 | QA-042 |
| REQ-019 | H0 |
| REQ-020 | QA-001, QA-002 |
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

📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и по исходникам, 2026-10-26):
- Репозиторий `cli-agent-bridge` (ветка `feature/zen-realtime-reasoning` от `origin/dev` `7eda27f9d82732bab726a420e31ea2adc15c2c39`): автономный Python stdlib-мост `bridges/opencode-zen-bridge/server.py` (`ThreadingHTTPServer` на `127.0.0.1:9883`), без корневого `AGENTS.md` и без сторонних runtime-зависимостей вне стандартной библиотеки Python 3.14.
- Установленный CLI `~/.opencode/bin/opencode` версии `v2.1.2` существует локально: команда `opencode run --format json --thinking` подписана только на `session.reasoning.ended` и `session.text.ended` (игнорирует `*.delta`, разрыв 0.00–0.17 мс в конце шага, `[F-17]`, `[F-18]`).
- Режим `opencode serve --port P --hostname 127.0.0.1` в `opencode` `v2.1.2` существует и проверен эмпирически (`[F-19]..[F-22]`): старт ~109 мс, Basic-аутентификация `opencode:<OPENCODE_SERVER_PASSWORD>`, OpenAPI `281456 B` включает `GET /api/event` (SSE с реальными дельтами `session.reasoning.delta` median 127 мс и `session.text.delta` median 114 мс), `POST /api/session` (с `permissions`), `POST /api/session/{id}/prompt`, `POST /api/session/{id}/interrupt`, `DELETE /api/session/{id}`.
- Локальный `model_georouter` (`127.0.0.1:10830`) и пул ротации чистых IP ProxyRack (`OPENCODE_ZEN_BRIDGE_STANDALONE_PROXY=pool`) существуют на хосте (`[F-15]`, `[F-26]`, `[F-27]`); прямой анонимный HTTP-вызов к `opencode.ai/inference/openai/v1` без заголовков CLI вернул `429 FreeUsageLimitError` (`[F-24]`, `[F-25]`).
- Потребитель DSH Desktop (`@earendil-works/pi-ai` `openai-completions.js` и `@deepseek-ai/dsh-client-ui-chat` `ReasoningRow`, `[F-35]..[F-38]`): строка `⚛ Think` скрыта (`blockIsVisible`), пока `reasoning_content` пуст; свёрнутое inline-превью обновляется через `latestCompletedParagraphFirstLine` только при наличии завершённого абзаца с символом `\n`; при реплее истории мост игнорирует входящий `assistant.reasoning_content` (`[F-07]`).
- Прецедент в том же репозитории: `bridges/muse-bridge/server.py` (ADR-0004, `[F-40]`, `[F-41]`) использует `serve` как основной транспорт с откатом на `exec` при `ServeUnavailable` и живой записью статусов в `reasoning_content`.
- Тестовый контур моста (`[F-42]..[F-49]`): `uvx pytest -q -p no:cacheprovider tests/` из `bridges/opencode-zen-bridge` (17 модулей, 378 тестов; 3 pre-existing падения в `tests/test_step_interruption.py` из-за `MAX_TOTAL_SPAWNS=3` против ожидания 4 запусков и общего `_RetryBudget` на класс).
Анти-галлюцинация по факт-карте: технологии, пути, версии и поведение CLI из списка выше проверены на целевой машине; по сведениям, которых нет в факт-карте и приложенных артефактах, указывается «не могу проверить».

РЕЖИМ: architecture
Модификатор режима `architecture`: Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки. Усиленные критерии режима `architecture` (вес ×1.5 на агрегации): 5. АЛЬТЕРНАТИВЫ и 4. РИСКИ.

Инструкции судье Архитектурного Совета Тимлидов (повторный проход после дельта-пакета, раунд R1):
- Если ты уже видел эту задачу, код или артефакты в другой роли или в прошлом проходе — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически.
- Проверь закрытие каждого обязательного пункта доработки `RW-001..RW-014` из приложенного вывода `panel-rework-summarizer` (`handoff/panel-rework-brief-arch-a1.json`) в актуальном `architecture-packet.json` и механической дельте `architecture-packet.v1-to-v2.diff` (режим `verify-fixed`); если какой-либо `RW-NNN` не закрыт проверяемым изменением в пакете или доказательным обоснованием с evidence — зафиксируй находку F-блоком.
- Проверь соответствие Architecture Packet каждому требованию `REQ-001..REQ-020`, каждому приёмочному критерию `AC-001..AC-026`, рабочим целевым значениям отзывчивости и каждому пункту разделов `Non-Goals` и `Forbidden Scope` из `handoff-architect.md`.
- Проверь, что все архитектурные решения опираются на факты `[F-NN]` и каждый факт `[F-NN]` находится в приложенном `evidence-ledger.md`.
- Проверь альтернативы: в Architecture Packet должно быть рассмотрено ≥2 альтернативы с явной причиной выбора; если в пакете меньше двух альтернатив или нет причины выбора — ставь FAIL по пункту об альтернативах (критерий 5. АЛЬТЕРНАТИВЫ).
- Проверь архитектурные границы и слои (`boundaries`), внешние контракты (HTTP/event/data/CLI/SDK и пустоту/обоснованность `contract_deltas`), сценарии качества (NFR, тайминги отзывчивости, конверт `HL-ENV/v1` из 46 полей и расчёты `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`, `T-LIFE/v1`, `O-EXIT/v1`, `M-SEM/v1`), модель угроз и защиту секретов (`threats` / `security`), а также проверяемость `verification_surface` и все пункты `Definition of Done overlay` из `aisdlc-gcge/skills/architecture.md`.
- FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.
- FAIL без оговорок: (1) пакет меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK) без явного указания в постановке задачи / task envelope (`scope-and-contracts.md`); (2) работа или пакет выходит за рамки текущей задачи (чужие Jira-KEY, чужой статус, правки чужих мостов или файлов «заодно»).
- Оцени все 6 критериев `universal-panel` (1. КОРРЕКТНОСТЬ, 2. ПОЛНОТА, 3. РЕАЛИЗУЕМОСТЬ, 4. РИСКИ, 5. АЛЬТЕРНАТИВЫ, 6. СООТВЕТСТВИЕ КОНТЕКСТУ) по единому блоку формата ответа из промпта твоей роли в начале брифа.

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

## Параллелизм
- Все независимые чтения (diff, AC-оракулы, правила, evidence) делай одной пачкой tool-calls, не по одному; независимые команды (grep, прогон проверок) — параллельно, долгие — в фон.
- За один проход проверь ВСЕ критерии и подкатегории и выдай ВСЕ F-блоки сразу; не останавливайся на первой находке.
- Заполняй SUB-строки по мере прохода, не копи в конец; HEARTBEAT и `[hb] ок` каждые 4,5 мин — как в шапке.
- Других судей не жди и не угадывай их вердикты (изоляция контекста).

Итоговую строку общего вердикта выводи строго с одним из значений `PASS`, `NEEDS WORK` или `RED FLAG` (без точки и комментариев в той же строке), а сразу после неё — обязательные строки покрытия и числа находок из п.6 блока «ПОЛНОТА ВЫДАЧИ».

---
PRIOR-LEDGER-SHA256: ea0c347aea93ebb5512c49ccebecc1a916cfbfb20a64c64616a69087d793c110
PANEL-NONCE: a49e26963757a645
ARTIFACT-SHA256: c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: a49e26963757a645» и «ARTIFACT-SHA256: c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d».

BRIEF_END>>>
