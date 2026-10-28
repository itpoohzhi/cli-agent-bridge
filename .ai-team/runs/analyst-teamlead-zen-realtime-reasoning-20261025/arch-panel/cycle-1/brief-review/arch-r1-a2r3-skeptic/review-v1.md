{
  "items": [
    {"id":"BR-01","evidence_quote":"При запуске DeepSeek (`deepseek-v4.1-flash-free` High) через `opencode-zen-bridge` в DSH Desktop размышления (`reasoning_content` / блок `Think`) и прогресс шагов стримятся в реалтайме по мере генерации, без «немой» паузы `Deep diving for 35s ...`.","status":"covered","fix":""},
    {"id":"BR-02","evidence_quote":"Полный цикл `analyst-teamlead` пройден с двумя `PANEL PROOF` (`verify_panel_proof.py` exit=0, `panel-proof.json` PASS на `arch` и `code`), всеми L1/L2 проверками (`ruff`, `basedpyright`, `pytest`) и открытым PR в `origin/dev` (без merge).","status":"covered","fix":""},
    {"id":"BR-03","evidence_quote":"Проведена живая проверка тяжёлым путём на реальном мосту и DSH.","status":"covered","fix":""},
    {"id":"BR-04","evidence_quote":"\"preset\": \"analyst-teamlead\",\n  \"setup\": \"default\",\n  \"criticality\": \"S2\",","status":"covered","fix":""},
    {"id":"BR-05","evidence_quote":"Подтверждены три независимые причины; устранять надо все три, иначе пользователь по-прежнему не увидит «процесс идёт».","status":"covered","fix":""},
    {"id":"BR-06","evidence_quote":"Вне периметра: правка кода, деплой, изменение DSH, смена модели, чужие мосты (кроме эталона muse-bridge).","status":"covered","fix":""},
    {"id":"BR-07","evidence_quote":"AC-001: на клиентском сокете интервал между соседними `reasoning_content`-чанками меньше 500 мс, пока апстрим-стрим ещё идёт","status":"covered","fix":""},
    {"id":"BR-08","evidence_quote":"AC-002: накладные расходы моста между приходом дельты и записью в сокет не больше 250 мс","status":"covered","fix":""},
    {"id":"BR-09","evidence_quote":"Публичный контракт не меняется: `/health`, `/v1/models`, `/v1/chat/completions`, формат OpenAI SSE, `finish_reason`, `usage`, порт :9883","status":"covered","fix":""},
    {"id":"BR-10","evidence_quote":"Прежний путь `opencode run --format json` остаётся рабочим как переключаемый запасной вариант и kill-switch (имя переменной и дефолт задаёт Архитектор); существующие тесты на fake-CLI остаются зелёными","status":"covered","fix":""},
    {"id":"BR-11","evidence_quote":"Первая видимая реакция моста в течение 1.0 с после открытия SSE: непустой `reasoning_content`, оканчивающийся `\\n` (статус подключения/ожидания модели), независимо от состояния апстрима","status":"covered","fix":""},
    {"id":"BR-12","evidence_quote":"Статусные строки моста отделены от текста модели, имеют префикс «[мост]» и завершаются `\\n`; текст размышления модели не модифицируется; статусные строки не попадают в промпт при реплее","status":"covered","fix":""},
    {"id":"BR-13","evidence_quote":"AC-007: `_messages_to_prompt` не содержит статусных строк при реплее","status":"covered","fix":""},
    {"id":"BR-14","evidence_quote":"Watchdog первого события: нет ни одного события транспорта в течение порога (допущение 20 с, OPEN-11) — группа процессов убивается, попытка повторяется по общему бюджету либо клиент получает явную ошибку","status":"covered","fix":""},
    {"id":"BR-15","evidence_quote":"Watchdog первого токена (reasoning или text, допущение 60 с) и watchdog паузы между чанками (допущение 60 с); пороги настраиваются переменными окружения","status":"covered","fix":""},
    {"id":"BR-16","evidence_quote":"AC-010: порог первого токена даёт `first_token_timeout`","status":"covered","fix":""},
    {"id":"BR-17","evidence_quote":"Отсутствие осиротевших процессов: при отключении клиента, таймауте и watchdog убивается вся группа (включая дочерний `opencode serve`); отключение клиента обнаруживается не позже 5 с","status":"covered","fix":""},
    {"id":"BR-18","evidence_quote":"AC-012: ход 1 образца (24.4 с на обнаружение) не воспроизводится","status":"covered","fix":""},
    {"id":"BR-19","evidence_quote":"Потолок `MAX_TOTAL_SPAWNS=3`, `FAIL_RETRY_LIMIT`, `_RetryBudget`, Full Jitter и Circuit Breaker сохраняются; повторы по watchdog считаются в общий потолок; при повторе после отданного размышления вставляется отдельная статусная строка","status":"covered","fix":""},
    {"id":"BR-20","evidence_quote":"AC-014: размышление не дедуплицируется, между попытками ровно одна статусная строка","status":"covered","fix":""},
    {"id":"BR-21","evidence_quote":"`ToolCallParser` на потоковых дельтах: текст вне тегов выдаётся инкрементально (удерживается не более `len(\"<tool_invoke>\")-1` символов хвоста и открытый блок), блоки `<tool_call>`/`<tool_invoke>` не попадают в `content` при любом разбиении на дельты","status":"covered","fix":""},
    {"id":"BR-22","evidence_quote":"Завершение шага с вызовом инструмента останавливает процесс или сессию и даёт `finish_reason=\"tool_calls\"`; детектор оборванного шага (`STEP_RECOVERY`), классификация `etype=error` и маркеры `_INTERRUPTED_RE` работают на накопленных данных потокового пути","status":"covered","fix":""},
    {"id":"BR-23","evidence_quote":"Встроенные инструменты `opencode` на новом транспорте запрещены (политика `deny` для всех) либо эквивалентно изолированы; события встроенных инструментов приводятся к текущему внутреннему виду (`tool_use`, unmapped, native)","status":"covered","fix":""},
    {"id":"BR-24","evidence_quote":"Ротация чистых IP на каждый новый запуск, `_StartupGate`, `SPAWN_RATE_PER_S`, bulkhead слотов и Circuit Breaker действуют и для нового транспорта","status":"covered","fix":""},
    {"id":"BR-25","evidence_quote":"`usage` собирается из токенов завершения шага нового транспорта и совпадает по полям (`input`, `output`, `cached`, `reasoning`) с текущим","status":"covered","fix":""},
    {"id":"BR-26","evidence_quote":"Секреты не пишутся в логи и артефакты: пароль `opencode serve` (случайный на процесс), ключи, креды прокси; применяется существующее маскирование","status":"covered","fix":""},
    {"id":"BR-27","evidence_quote":"Наблюдаемость `O-EXIT/v1`: новые значения `exit_reason` (`first_event_timeout`, `first_token_timeout`, `stall_timeout`, `client_gone`) и поля `transport`, `first_event_ms`, `ttft_ms` в строке выхода","status":"covered","fix":""},
    {"id":"BR-28","evidence_quote":"Базовая линия тестов приводится в зелёное: два теста ждут 4 запуска при потолке 3, третий страдает от общего `_RetryBudget` на класс","status":"covered","fix":""},
    {"id":"BR-29","evidence_quote":"AC-023: результат не зависит от порядка тестов","status":"covered","fix":""},
    {"id":"BR-30","evidence_quote":"Прямой Google-маршрут (`_stream_google_sse`, `_execute_google_once`) не затрагивается | F-16 | AC-024: `test_google_direct.py` проходит без правок","status":"covered","fix":""},
    {"id":"BR-31","evidence_quote":"Развёрнутая копия `~/.dsh/bridges/opencode-zen-bridge/server.py` синхронизируется с репозиторием и проверяется сверкой | F-34, OPEN-17 | AC-025: побайтовое совпадение после деплоя","status":"covered","fix":""},
    {"id":"BR-32","evidence_quote":"В набор тестов добавляется измерение реального времени прихода чанков на клиентском сокете при ещё идущем апстриме (сейчас таких тестов нет) | F-44 | AC-026: тест красный на текущем коде и зелёный на новом (red to green)","status":"covered","fix":""},
    {"id":"BR-33","evidence_quote":"<<<ARTIFACT analysis/zen-realtime-reasoning/handoff-architect.md sha256=9cd426324b8f49ddc760e3706e200709754a0a459b9e234f7b45b3b2669c6d9f","status":"covered","fix":""},
    {"id":"BR-34","evidence_quote":"Не менять публичный HTTP-контракт моста, порт и формат OpenAI SSE (REQ-002).","status":"covered","fix":""},
    {"id":"BR-35","evidence_quote":"Не менять DSH (бандл `app.asar`), профиль `cordis.patch.yml` и поведение `ReasoningRow`.","status":"covered","fix":""},
    {"id":"BR-36","evidence_quote":"Не модифицировать текст размышления модели ради превью (OPEN-13).","status":"covered","fix":""},
    {"id":"BR-37","evidence_quote":"Не менять модель, список моделей, логику выбора эффорта и каталог Zen.","status":"covered","fix":""},
    {"id":"BR-38","evidence_quote":"Не трогать `muse-bridge`, другие мосты и общий `~/.config/opencode/opencode.json` / конфиг `model_georouter`.","status":"covered","fix":""},
    {"id":"BR-39","evidence_quote":"Не вводить новые внешние зависимости Python вне стандартной библиотеки, если Architect не обоснует иное.","status":"covered","fix":""},
    {"id":"BR-40","evidence_quote":"Изменение чужих файлов репозитория вне `bridges/opencode-zen-bridge/` и тестов этого моста.","status":"covered","fix":""},
    {"id":"BR-41","evidence_quote":"Запись секретов (ключи, пароль serve, креды прокси, значения `apiKey`) в логи, артефакты, код и тесты.","status":"covered","fix":""},
    {"id":"BR-42","evidence_quote":"Мутирующие действия на боевом контуре без отката: правка `~/.dsh` и перезапуск LaunchAgent допустимы только в живой приёмке по протоколу из `handoff-qa.md`.","status":"covered","fix":""},
    {"id":"BR-43","evidence_quote":"Использование `security find-generic-password`.","status":"covered","fix":""},
    {"id":"BR-44","evidence_quote":"Правка `opencode.db` и общего каталога состояния `opencode` напрямую.","status":"covered","fix":""},
    {"id":"BR-45","evidence_quote":"Коммит в `main`, `master`, `dev`; merge выполняет человек.","status":"covered","fix":""},
    {"id":"BR-46","evidence_quote":"<<<ARTIFACT analysis/zen-realtime-reasoning/evidence-ledger.md sha256=2a5c9f7f8a8fc20573d69a4617da87bdfbf1f57e70681e7036ece27541fe0367","status":"covered","fix":""},
    {"id":"BR-47","evidence_quote":"Цели отзывчивости владельцем не заданы числами (OPEN-11); рабочие значения: первая видимая строка до 1.0 с, первая дельта размышления до 3.0 с, пауза до 15 с, молчание до 20 с.","status":"covered","fix":""},
    {"id":"BR-48","evidence_quote":"Для read-only роли это требование к handoff, а не\nразрешение писать в product worktree, пушить или сливать MR.","status":"covered","fix":""},
    {"id":"SK-A-01","evidence_quote":"<<<ARTIFACT .ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/architecture/architecture-packet.json sha256=c3936c99b53fc50508c113c88368f0b75b01d250d8345ee3be175c753a8b9a3d","status":"covered","fix":""},
    {"id":"SK-A-03","evidence_quote":"Проверь, что все архитектурные решения опираются на факты `[F-NN]` и каждый факт `[F-NN]` находится в приложенном `evidence-ledger.md`.","status":"covered","fix":""},
    {"id":"SK-A-04","evidence_quote":"РЕЖИМ: architecture\nМодификатор режима `architecture`: Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки.","status":"covered","fix":""},
    {"id":"SK-A-05","evidence_quote":"Проверь альтернативы: в Architecture Packet должно быть рассмотрено ≥2 альтернативы с явной причиной выбора; если в пакете меньше двух альтернатив или нет причины выбора — ставь FAIL по пункту об альтернативах (критерий 5. АЛЬТЕРНАТИВЫ).","status":"covered","fix":""},
    {"id":"SK-A-06","evidence_quote":"Проверь архитектурные границы и слои (`boundaries`), внешние контракты (HTTP/event/data/CLI/SDK и пустоту/обоснованность `contract_deltas`), сценарии качества","status":"covered","fix":""},
    {"id":"SK-A-07","evidence_quote":"FAIL без привязки к разделу пакета / `[F-NN]` / правилу не засчитывается.","status":"covered","fix":""},
    {"id":"SK-A-08","evidence_quote":"FAIL без оговорок: (1) пакет меняет согласованный внешний контракт (HTTP/event/data/CLI/SDK) без явного указания в постановке задачи / task envelope (`scope-and-contracts.md`);","status":"covered","fix":""},
    {"id":"SK-A-09","evidence_quote":"Анти-галлюцинация по факт-карте: технологии, пути, версии и поведение CLI из списка выше проверены на целевой машине; по сведениям, которых нет в факт-карте и приложенных артефактах, указывается «не могу проверить».","status":"covered","fix":""},
    {"id":"SK-A-10","evidence_quote":"<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md sha256=906aab1ea3b7cda57b9d788a3dd105f2f6d2e7be159a699eccaf3f93f6bba400","status":"covered","fix":""},
    {"id":"SK-A-11","evidence_quote":"","status":"missing","fix":"Для нового R1 подготовить вход доработки без следов прошлых вердиктов и комментариев судей; сохранить полный актуальный Packet, механическую delta и первичный вывод summarizer в согласованном для R1 составе."},
    {"id":"SK-A-13","evidence_quote":"ПОЛНОТА ВЫДАЧИ — ВСЕ ЗАМЕЧАНИЯ ЗА ОДИН ПРОХОД (обязательно, оба режима):","status":"covered","fix":""},
    {"id":"SK-A-14","evidence_quote":"ЯКОРЯ ПАКЕТА (арх-проход; предмет — Architecture Packet, не diff)\nВезде, где правила или формат ответа говорят «file:line», допустим один из якорей:","status":"covered","fix":""},
    {"id":"SK-T-01","evidence_quote":"Universal Architecture Packet валиден в `approved` phase.","status":"covered","fix":""},
    {"id":"SK-T-02","evidence_quote":"Все Python-утверждения подтверждены кодом/конфигом/официальной документацией.","status":"covered","fix":""},
    {"id":"SK-T-03","evidence_quote":"Для async Python явно спроектировать:\n\n- timeout для каждой I/O-операции и cleanup;\n- cancellation и partial failure;\n- retry только для перечисленных transient errors;\n- idempotency/deduplication для повторов;\n- concurrency limit, backpressure и порядок результатов;","status":"covered","fix":""},
    {"id":"SK-T-04","evidence_quote":"`contract_deltas[]` пуст либо в текущей задаче есть явное указание менять\n  согласованный внешний контракт (`.agents/agents/scope-and-contracts.md`).","status":"covered","fix":""},
    {"id":"SK-T-05","evidence_quote":"Stateful change имеет migration/rollout/rollback и integrity checks.","status":"covered","fix":""},
    {"id":"SK-T-06","evidence_quote":"Для каждого изменения определить чувствительность:\n\n- bugfix: red без fix → green с fix;\n- новый contract: negative/boundary test;\n- migration: upgrade + data check + допустимая rollback/forward-fix проверка;\n- concurrency/time/network: повтор/seed/fault injection по риску;","status":"covered","fix":""},
    {"id":"SK-T-07","evidence_quote":"ADR path/format не конфликтует с `.agents/agents/docs.md`.\n- Architect не изменил product worktree.","status":"covered","fix":""},
    {"id":"SK-T-08","evidence_quote":"## Обязательные Highload & Resilience гейты (`HL-ENV/v1`, `C-MULT/v1`, `S-HERD/v1`, `H-CPU/v1`, `R-BULK/v1`)","status":"covered","fix":""},
    {"id":"SK-P-01","evidence_quote":"Diff не меняет согласованный внешний контракт, либо в текущей задаче\n      есть явное указание это сделать и delta зафиксирована.","status":"covered","fix":""},
    {"id":"SK-P-02","evidence_quote":"Работа, ревью и отчёт только про текущую задачу / KEY; чужие KEY в\n      отчёте отсутствуют, если их не спросили.","status":"covered","fix":""},
    {"id":"SK-P-03","evidence_quote":"<<<ARTIFACT ~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md sha256=7e606a52d977e281e8eedc9f0482a0d8d83008a2106fc3d27bee00f3c62d384a","status":"covered","fix":""},
    {"id":"JD-02","evidence_quote":"","status":"covered","fix":""},
    {"id":"JD-03","evidence_quote":"Если ты уже видел эту задачу, код или артефакты в другой роли или в прошлом проходе — суди ЗАНОВО, не подтверждай прошлый вердикт автоматически.","status":"covered","fix":""},
    {"id":"JD-04","evidence_quote":"ФОРМАТ ОТВЕТА (строго):","status":"covered","fix":""},
    {"id":"JD-05","evidence_quote":"Независимо пересчитай `SEED = SHA-256(seed_input)` и порядок `ranked_order` по правилу `models.md` п.1.1/1.2","status":"covered","fix":""},
    {"id":"JD-06","evidence_quote":"\"panel_verdict\": \"NEEDS_WORK\",","status":"missing","fix":"Убрать из входа нового R1 прошлые вердикты и атрибутированные позиции судей, включая вложенные rework-артефакты и соответствующие разделы Packet/delta."},
    {"id":"JD-07","evidence_quote":"📋 ФАКТ-КАРТА (проверено оркестратором на целевой машине и по исходникам, 2026-10-26):","status":"covered","fix":""},
    {"id":"JD-08","evidence_quote":"с исключением семейства автора пакета `OpenAI` и ротацией семейств относительно предыдущего окна в `panel/history.jsonl`","status":"missing","fix":"Приложить необходимые правила models.md п.1.1/1.2, предыдущее окно panel/history.jsonl и проверяемый ranked_order; приложить исходный бриф Архитектора для утверждений, опирающихся на EVD-060."},
    {"id":"HY-02","evidence_quote":"","status":"covered","fix":""},
    {"id":"HY-04","evidence_quote":"","status":"covered","fix":""},
    {"id":"HY-05","evidence_quote":"","status":"covered","fix":""},
    {"id":"HY-06","evidence_quote":"","status":"covered","fix":""}
  ],
  "unmapped_requirements": [
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Входной-evidence",
      "quote":"До решения открыть и сослаться в packet минимум на:\n\n- точки входа API/consumer/job;\n- service/domain/repository границы;\n- модели и migrations затронутых данных;\n- `pyproject.toml`/lockfile и реальные версии;\n- существующие тесты, CI-команды и архитектурные правила;\n- последний успешный аналог изменения, если он есть.",
      "fix":"Добавить строку SK-T для проверки обязательного состава входного evidence и ссылок на него в Packet."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Входной-evidence",
      "quote":"Название файла, класса или метода\nне включать в handoff, если их существование не подтверждено кодом.",
      "fix":"Добавить строку SK-T о подтверждении существования упомянутых файлов и символов кодом."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Python-specific-boundaries",
      "quote":"В `boundaries[]` указать allowed/forbidden dependencies и `verification_ids`.",
      "fix":"Добавить строку SK-T, требующую эти поля у каждой границы."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Async-и-failure-semantics",
      "quote":"Для dynamic/paginated/streaming источника определить аккумуляцию и независимый сигнал\nполноты; один snapshot не считается полным источником.",
      "fix":"Добавить строку SK-T для аккумуляции и независимого сигнала полноты потокового источника."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Contract-deltas",
      "quote":"Cross-repo mirror, compatibility window и mixed-version behavior указывать явно.\nBreaking change, auth/security model, новая major dependency и cross-service contract —\none-way decision с человеческим approval.",
      "fix":"Добавить строку SK-T для применимости mixed-version требований и обязательного человеческого approval односторонних решений."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#ADR-и-proposals",
      "quote":"- ADR-full — дорогой откат, несколько репозиториев, NFR/security, спор или ≥3 опции.\n- Sensitivity check и PoC применять по командному ADR-full contract.",
      "fix":"Добавить строку SK-T для выбора ADR-full по триггерам и проверки sensitivity check/PoC."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#ADR-и-proposals",
      "quote":"Architect пишет proposal только в `architecture/proposals/`. Он не выполняет\n`uv add`, не меняет `pyproject.toml`, lockfile, CI, migrations и product code.\nТакие изменения перечисляются в contract/materialization plan и проходят approval.",
      "fix":"Добавить строку SK-T для разрешённого места proposals и запрета самостоятельных dependency/CI/migration изменений."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Views",
      "quote":"Каждый `views[]` содержит вопрос и artifact reference.",
      "fix":"Добавить строку SK-T для обоснованного выбора views и обязательных полей каждого view."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Python-verification-surface",
      "quote":"Verifier обязан запустить полный frozen\nнабор; Coder log не заменяет независимое выполнение.",
      "fix":"Добавить строку SK-T о независимом выполнении полного frozen verification surface."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Что-Architect-не-делает",
      "quote":"- Не пишет готовую реализацию и не фиксирует внутренние сигнатуры без контрактной причины.",
      "fix":"Добавить строку SK-T для запрета готовой реализации и необоснованного фиксирования внутренних сигнатур."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Что-Architect-не-делает",
      "quote":"- Не устанавливает зависимости и не ослабляет существующие gates.\n- Не выдаёт self-eval или grep по заголовкам за architecture review.",
      "fix":"Добавить строку SK-T для неизменности gates и запрета подмены независимого архитектурного ревью self-eval."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/architecture.md#Эскалация",
      "quote":"`BLOCKED`, если отсутствует NFR, schema ownership, compatibility policy, право на\nbreaking/security/dependency decision или способ проверить критичный contract. Не\nдодумывать значения и не передавать Coder условный пакет как approved.",
      "fix":"Добавить строку SK-T с обязательными основаниями BLOCKED и запретом условного approved."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md#Главные-правила",
      "quote":"**При ошибке — Identify → Assess → Communicate → Solutions.**",
      "fix":"Добавить строку SK-P для обязательного алгоритма реакции на ошибки."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md#Правила-коммитов-и-измерение-вклада-агента",
      "quote":"Каждый коммит должен быть помечен тегом в начале сообщения:",
      "fix":"Добавить строку SK-P для префикса вклада агента и формата Conventional Commits в downstream handoff."
    },
    {
      "source":"~/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md#Что-запрещено-делать",
      "quote":"**`git commit --no-verify`** — обход всех хуков, **никогда**.",
      "fix":"Добавить строку SK-P о запрете обхода pre-commit через --no-verify, SKIP и PRE_COMMIT_ALLOW_NO_CONFIG."
    },
    {
      "source":"brief-review/references/checklist-sources.md#SK-P",
      "quote":"обязательная техническая строка `PRIOR-LEDGER-SHA256` в подвале PoL рядом с `PANEL-NONCE` и `ARTIFACT-SHA256`",
      "fix":"Добавить строку чек-листа и явное указание судье вывести PRIOR-LEDGER-SHA256 в подвале PoL; наличия маркера во входном брифе недостаточно."
    }
  ],
  "bloat_flags": [
    {
      "category":"B1",
      "quote":"и не содержат никаких внешних требований вне вложенных артефактов",
      "fix":"Заменить заверение о содержимом отсутствующего брифа Архитектора первичным артефактом, подтверждающим используемые разрешения."
    }
  ],
  "leakage_flags": [
    {
      "category":"L1",
      "quote":"и не содержат никаких внешних требований вне вложенных артефактов",
      "fix":"Убрать вывод оркестратора о полноте происхождения требований и предоставить первичный бриф Архитектора."
    },
    {
      "category":"L3",
      "quote":"\"panel_verdict\": \"NEEDS_WORK\",",
      "fix":"Исключить прошлый вердикт из входа нового R1."
    },
    {
      "category":"L3",
      "quote":"\"PANEL-F-001: headers response barrier\",\n        \"RW-001.evidence: Seat2 начало POST barrier\"",
      "fix":"Убрать атрибутированные позиции прошлых судей из Packet и соответствующей delta для изолированного R1."
    },
    {
      "category":"L3",
      "quote":"Seat 1 СООТВЕТСТВИЕ КОНТЕКСТУ/PASS считает default-disabled частью соблюдения контекста; Seat 2 F-004 требует default=true либо расширение scope на start.sh.",
      "fix":"Убрать комментарии о прошлых голосах из входа R1; требования доработки передать без атрибуции и прежних оценок."
    }
  ],
  "verdict":"REJECT"
}
