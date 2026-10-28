PANEL-NONCE: 07395d8f22bcbead
ARTIFACT-SHA256: a53012565332cab8140d26d43029b931ff6d6c1fe4c63612310567ecba6812b3

**Закрытие RW/FU (verify-fixed по `architecture-packet.v3-to-v4.diff`):**
- **RW-001 закрыт по существу.** `--range={start}:1-{end}:999` стоит во всех полях: `command`, `expected`, `baseline_transition.new`, `typing`. Заданы литеральные sha256 для `_run_env` и двух Google-срезов. В EVD-075 есть три отрицательные мутации. Остаётся замечание F-1: эксперимент с форматтером проведён не на копии `server.py`.
- **RW-002 закрыт.** `CATALOG_SOURCE` остаётся публичным атрибутом модуля. Изменение идёт через типизированный `_set_catalog_source`. EVD-076 показывает `errorCount=0` и 8 тестов `test_catalog_mode`, `coder_target_files` не расширен.
- **RW-003 закрыт.** Топология одна: родитель, затем `helper_proc` (лидер сессии), затем `serve_proc` в той же группе. Арифметика согласована: потоки 1+18+6+6+6+12+6=55, FD 108+6=114≤128, RSS 6·192+256=1408≤1638.4. Порядок lease → handshake → lsof/READY зафиксирован. Заданы пять точек SIGKILL в VER-005 и `terminal_quiescence`.
- **FU-001..FU-006 закрыты.** Порядок «cancel формы раньше schema-проверки» записан. Шаблон ожидания унифицирован. В `fallback_decision_table` появилась строка 5. Ссылка EVD-056 заменена на EVD-055. Горячий путь отделён от reconnect. Контракт H4/H5 («только `cp server.py`») добавлен.

1. КОРРЕКТНОСТЬ: VERDICT=PASS
   WHY=Дельта v3→v4 непротиворечива. Индексы `/evidence/69` и `/evidence/70` указывают на EVD-075 и EVD-076. Строки `fallback_decision_table/rows/4,5` существуют. Контракт REQ-002 не меняется, а поля O-EXIT разрешены REQ-016. Расхождения оформлены как F-5 и F-6, оба non-blocking.
   СОВЕТЫ: нет (см. F-2, F-5, F-6).

2. ПОЛНОТА: VERDICT=PASS
   WHY=Все RW-001..003 и FU-001..006 закрыты проверяемыми правками. Исключения F-009 и F-011 учтены без расширения scope. Покрыты REQ-001..020, AC-001..026 и гейты HL-ENV/C-MULT/S-HERD/H-CPU/R-BULK/T-LIFE/O-EXIT. Остаточные пробелы перечислены в F-1 и F-3.
   СОВЕТЫ: нет.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Топология реализуема на stdlib в рамках трёх файлов. Выполнимость подтверждена EVD-071 (старт 120.7 мс, 156.8 MiB, 0 открытых `.db`), EVD-075 и EVD-076. Живые H0..H9 честно помечены NOT_RUN. Риск: helper-код живёт строкой `_SERVE_HELPER_CODE` вне ruff и basedpyright (F-4). Ловушка VER-004 в F-2.
   СОВЕТЫ: нет (см. F-2, F-4).

4. РИСКИ: VERDICT=PASS
   WHY=Риски описаны с митигациями: SIGKILL родителя, подмена listener, утечка env, двойная доставка prompt, раздувание ресурсов, деградация транспорта. Вся мощность ограничена (6 слотов, cap=3, 1408 MiB), потолки не повышаются молча. При росте M>6 ломаются RSS и FD: линейно 192 MiB и ~58 FD на слот, плюс холодный старт на каждый запрос. Рост ограничен гейтом H3 «отклонить, не повышать лимиты». Главный стратегический риск — сложность кода в одном файле (F-3, F-4).
   СОВЕТЫ: нет.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Рассмотрено более двух альтернатив с причинами отказа: A2 (общий демон), B (прямой Zen, 429 по F-24/F-25), L (только watchdog), `--port 0` со stdout-анонсом, пустой `XDG_DATA_HOME`, общая БД, раздельная поставка 3a/3b. Критерий выполнен формально. Заметный пробел вынесен в F-3 как non-blocking.
   СОВЕТЫ: нет (см. F-3).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Периметр соблюдён: `bridges/opencode-zen-bridge/`, три целевых файла, Google-путь заморожен, `muse-bridge` не тронут, `~/.dsh` не затрагивается Architect-ом, `dynamic_config.json` не коммитится. Согласованные внешние контракты (HTTP, SSE, порт) не меняются. Чужих KEY нет. Новые env-поверхности описаны неаккуратно (F-5).
   СОВЕТЫ: нет.

**F-блоки (все non-blocking, поиск по всему пакету выполнен):**

F-1 [non-blocking] RW-001 acceptance подтверждён неполно.
- locations: architecture-packet.json#EVD-075; rework_resolutions_a3 RW-001.verification.
- Критерий RW-001 требует «реальный прогон раннего synthetic hunk на копии текущего server.py». В EVD-075 форматтер запускался на 6-строчном синтетическом `tmp_server.py` (`--range=1:1-6:999`), а не на копии боевого файла. Литеральные хэши и негативные мутации сняты на `server.py`-копии, это в порядке.
- Исправление: добавить в EVD прогон `--check --range` с ранним hunk на изолированной копии настоящего `server.py`. Записать rc и неизменность трёх хэшей.
- Проверка: EVD содержит `argv` с путём копии боевого файла.

F-2 [non-blocking] Проверка «до и после форматтера» в VER-004 не проверяет запись форматтера.
- locations: architecture-packet.json#VER-004 (`command`: второй `assert_frozen()` после цикла `ruff format --check`; `expected`: «Before and after formatter»).
- `--check` ничего не пишет, поэтому повторный `assert_frozen()` тавтологичен. Реальный риск возникает, когда Coder выполняет `ruff format --range` с записью и диапазон расширяется до enclosing-узла.
- Исправление: в VER-004 прогонять `ruff format --range` без `--check` на временной копии кандидата. Затем сравнивать три литеральных хэша и отсутствие hunk-пересечений.
- Проверка: мутация, дающая расширение диапазона на замороженную функцию, краснит гейт.

F-3 [non-blocking] Не оценена альтернатива `opencode serve --stdio` (стратегическая).
- locations: architecture-packet.json#AD-001.alternatives; [F-30] (дочерний `opencode serve --stdio --port 0` существует, PID 11488).
- Альтернативы по порту рассмотрены только как `--port 0` со stdout-анонсом. Транспорт через stdio, который `run --standalone` уже использует, мог бы убрать резервирование порта, `lsof`, listener-ownership и пароль, то есть заметную часть сложности RW-003. Пригодность протокола извне не доказана и не опровергнута.
- Исправление: добавить в `alternatives` вариант `serve --stdio` с доказательным отказом или с проверкой в provider-free preflight Stage3. Менять выбор A1 не требуется.
- Проверка: в `alternatives` есть запись со ссылкой на evidence.

F-4 [non-blocking] Helper-код живёт строкой `_SERVE_HELPER_CODE` вне покрытия `ruff` и `basedpyright`.
- locations: architecture-packet.json#AD-001.details.spawn; #VER-004; #T_LIFE_v1.
- Самая хрупкая логика (SIGSTOP-quiescence, lease, EOF-цикл) не попадает под VER-004, где «0 ошибок, 0 Any» заявлено для кода. Проверяется только fault-injection в VER-005.
- Исправление: описать запуск helper как режим того же `server.py` (`python -I server.py --serve-helper`). Тогда код типизируется и линтуется в рамках трёх файлов. Либо явно задокументировать исключение и усилить VER-005 тестами функций helper.
- Проверка: тело helper присутствует в диагностике basedpyright, либо исключение записано в пакете.

F-5 [non-blocking] Формулировки про env-переменные противоречат друг другу.
- locations: architecture-packet.json#AD-001.details.configuration (`OPENCODE_ZEN_BRIDGE_REALTIME_SERVE_ENABLED` как «Существующий env override»; `feature_flag_context`: «без … новых env-переменных»); #AD-001 (новые TRANSPORT, SERVE_PERMISSION_POLICY, SERVE_DISABLE_FILE); #AD-003 (watchdog-пороги).
- В evidence ledger нет подтверждения, что переменная `…REALTIME_SERVE_ENABLED` существует в базовом коде. При этом пакет добавляет минимум три новых env/файловых поверхности.
- Исправление: либо сослаться на `[F-NN]`/строку кода, где env существует, либо назвать её новой. Уточнить фразу «без новых env» до «без новых env для самого флага».
- Проверка: текст пакета не содержит противоречия.

F-6 [non-blocking] Хэш fixtures смешан с редакционной метаданной.
- locations: architecture-packet.json#AD-001.details.event_contract (`frozen_fixture_sha256` в v4 изменён при неизменных wire и canonical, `fixture_digest_revision_a3`).
- Сериализуется весь `frozen_v2_1_2_fixtures`, включая `negative_mutations` и `safety_order`, поэтому правка текста меняет «иммутабельный» оракул. Значение `e7871cd2…` я проверить не могу: не вижу вычисления.
- Исправление: считать digest только по `wire` и `canonical`, метаданные хэшировать отдельно. Либо зафиксировать, что digest включает метаданные.
- Проверка: правка текста мутаций не меняет wire-digest.

ОБЩИЙ ВЕРДИКТ: PASS
COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: 6
