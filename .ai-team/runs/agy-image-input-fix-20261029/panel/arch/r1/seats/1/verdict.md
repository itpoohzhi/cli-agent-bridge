PANEL-NONCE: 460477a6b6fd67af
ARTIFACT-SHA256: ddcbc69fd277d74079d3868eb245a3c05c7d7ea00ddae6369fdc563982433466

1. ПОЛНОТА И СЛЕДОВАНИЕ ТРЕБОВАНИЯМ
VERDICT=FAIL
WHY=REQ-001..010 и AC-001..010 внутри пакета прослежены, но fleet-конфиг в AD-001 уже записан как confirmed с verified_at=2026-10-29 при доказанной лишь 1 из 24 комбинаций; статус APPROVED сосуществует с BLOCKED не-отменяемыми гейтами HL-ENV-01/C-MULT-I2,I5/H-CPU-I5/R-BULK-I1.
F-001 priority=BLOCKING
Якоря: AD-001 details.target_models, promotion, approval.status, resilience_gates HL-ENV-01, ASM-001, EVD-027
Правило: confirmed/proof допускается только по воспроизводимому evidence; APPROVED недопустим при открытых non-waivable stop-кодах.
Evidence: Доказан только PNG/gemini-4-argon/low (F-27). AD-001 тем не менее задаёт для обеих моделей status=confirmed, formats=4 MIME, efforts_proven=[low,medium,high], verified_at=2026-10-29. _image_proof_reason проверяет лишь SHA/версию/подмножество форматов/наличие effort в этом же self-asserted proof, поэтому после совпадения SHA 23 непроверенные комбинации пройдут гейт без матрицы. Оговорка «desired post-verification state» не является машинным барьером для Coder.
Действия: До матрицы держать status=probe/disabled либо proof только с фактически доказанными formats/efforts на модель; verified_at ставить по факту прогона; статус пакета понизить до условного до закрытия BLOCKED-гейтов либо явно запретить Coder материализовать target fleet.
Проверка: Негативный тест: fleet из пакета без матричного evidence обязан давать 400/no-spawn на JPEG/WebP/high/flash; VER-010 фиксирует 24/24 с артефактами до promotion.

2. КОРРЕКТНОСТЬ И БЕЗОПАСНОСТЬ
VERDICT=FAIL
WHY=Порядок валидации, актуальность flag/proof на момент spawn и границы декодирования заданы неполно; magic-sniff выдаётся за достаточную валидацию изображения.
F-002 priority=BLOCKING
Якоря: AD-002 ordered_validation шаги 1-3, AD-005 stage_location, HL queue=1800s, AD-001 flag TTL/emergency
Правило: Kill-switch и proof должны действовать на момент материализации/spawn, а не только на ingress.
Evidence: Flag и proof проверяются в _collect_images до ожидания слота. Запрос может ждать в очереди до 1800 с, после чего _stage_images и spawn выполняются без повторной проверки. Отключение IMAGE_INPUT_ENABLED и смена бинаря в этом окне не останавливают уже валидированныеQueued-запросы. Утверждение об emergency-off тем самым обходится очередью.
Действия: Повторно проверять _is_image_input_enabled() и _image_proof_reason() после _acquire_slot() непосредственно перед _stage_images/spawn; при отказе — 400, без staging.
Проверка: Тест с заблокированными слотами: валидировать запрос, выключить флаг/сменить SHA, освободить слот — ожидаются 0 mkdir и 0 spawn.
F-003 priority=BLOCKING
Якоря: AD-002 шаги 9-13, sniff, limits_scope, THREAT-002
Правило: Лимиты проверяются до дорогой/опасной обработки; sniff префикса не равен безопасному декодированию.
Evidence: base64-декодирование (шаг 9) и sniff (шаг 10) предшествуют проверкам count/per-image/total (шаги 11-13): 17-я картинка и oversize-blob сначала полностью декодируются в память. Нет оценки декодированного размера по длине base64 до decode. Нет проверки пиксельных размерностей: валидный по сигнатуре 20 MiB PNG/GIF может быть decompression-bomb для нативного view_file в дочернем процессе, чей RSS пакетом не ограничен (children_rss без бюджета).
Действия: Pre-check count до цикла decode; оценивать decoded length из base64 и отклонять до b64decode; парсить заголовки PNG/JPEG/GIF/WebP на width*height/frames с жёстким потолком пикселей или явно принять риск с лимитом RSS ребёнка.
Проверка: Граничные тесты 17 изображений и +1 байт без вызова b64decode для отклонённого элемента (spy); фикстура малой PNG с огромными IHDR-размерами отклоняется до spawn.
F-004 priority=WARNING
Якоря: AD-006 contract, AD-002 шаг 7 _parse_data_url, AD-001 _file_sha256
Правило: Пользовательские поля в журнале санитизируются; парсинг data URL и identity бинаря определены однозначно.
Evidence: В лог пишутся model=<id> и reason=<subreason> без спецификации экранирования newline/whitespace в model из запроса — возможна подделка строк журнала в обход _SECRET (короткий токен <24 символов маской не режется). Для _parse_data_url не заданы регистронезависимость MIME/base64-параметра, дубли параметров, пробелы. Identity кэша SHA — пара (st_mtime_ns, st_size): замена бинаря с сохранёнными mtime/size не инвалидирует кэш; привязка хэшируемого пути ~/.local/bin/agy.real к реально запускаемому через launcher бинарю не доказана.
Действия: Логировать model только после allowlist/экранирования управляющих символов; формализовать грамматику data URL; в identity включить st_ino/st_dev/ctime и хэшировать резолвленный launcher-путь запускаемого файла.
Проверка: Фикстуры model с \n, data:IMAGE/PNG;BASE64, дублей параметров; подмена бинаря in-place с тем же mtime/size обязана дать proof-mismatch.

3. НАДЁЖНОСТЬ, РЕСУРСНЫЕ ИНВАРИАНТЫ И ДЕГРАДАЦИЯ
VERDICT=FAIL
WHY=Спул ограничен слотами, но декодированные буферы удерживаются до слота всеми 32 обработчиками; реестр активных каталогов процессно-локальный и не защищает от соседнего процесса и гонок ФС.
F-005 priority=BLOCKING
Якоря: AD-005 allocation/stage_location/memory, EVD-036, memory_closure_check, QA-009, C-MULT-I2
Правило: Ресурсная граница должна замыкаться по всем удерживаемым копиям, а не только по диску после слота.
Evidence: _collect_images декодирует всю историю до _acquire_slot. При 32 admitted handlers одновременно живут JSON-строки, base64-строки и decoded bytes: потенциально 32×20 MiB только decoded плюс копии, против заявленных 176 MiB RSS. Пакет честно помечает bound UNPROVEN, но не предлагает проектного механизма ( семафор памяти до decode, декодирование после слота, потоковая запись), а лишь измерительную обязанность RES-01. Измерение не может починить архитектурно незамкнутую границу при adversarial-нагрузке.
Действия: Перенести decode/stage под слот или отдельный byte-bounded семафор, приобретаемый до b64decode по оценённому размеру; освобождать base64/JSON-ссылки после staging. RES-01 оставить подтверждением, не заменой механизма.
Проверка: 32 параллельных max-size запроса при 8 слотах: число одновременно декодированных запросов ≤8, пик RSS родителя в бюджете, очередники не удерживают decoded bytes.
F-006 priority=WARNING
Якоря: AD-005 registry/cleanup/sweep, BND-005, P_terminating_overlap=0
Правило: Очистка не удаляет чужие активные данные при любом числе процессов и не скрывает собственные сбои.
Evidence: _active_img_dirs — множество в памяти одного процесса. При overlap старого/нового процесса при рестарте (пакет предполагает 0 без доказательства) sweep нового процесса не знает активных каталогов старого при возрасте >3600 с (очередь+2 попытки способны выйти за час). Проверка is_symlink и последующий shutil.rmtree — TOCTOU-окно подмены. Cleanup задан как rmtree(ignore_errors=True) с последующим снятием из реестра при одновременном требовании «cleanup error must remain observable» — механизм наблюдаемости не определён. Закрытие fd при исключении на write в _stage_images и закрытие файла в _file_sha256 при исключении не специфицированы (риск утечки дескрипторов на error-path). Дополнительно: agy запускается с --dangerously-skip-permissions в том же UID и может изменить/удалить staged-файлы между попытками; повторная проверка целостности перед retry не задана, а data уже очищена — восстановить нечего.
Действия: Файл-маркер владения с PID/heartbeat или flock на каталог для межпроцессной защиты; удаление через openat/O_NOFOLLOW-стиль или перепроверку; логировать неудавшийся rmtree с reason; try/finally на каждый fd; перед retry сверять size/hash staged-файлов.
Проверка: Два процесса на одном WORKSPACE; подмена entry симлинком между check и delete; fault-injection на write второго файла с подсчётом открытых fd до/после; модификация staged-файла ребёнком перед второй попыткой детектируется.

4. ТЕСТИРУЕМОСТЬ И ВЕРИФИЦИРУЕМОСТЬ
VERDICT=FAIL
WHY=AO-01..10 содержательны, но машинные гейты VER-007/VER-009 проверяют форму, а не семантику, и обходятся тривиально.
F-007 priority=WARNING
Якоря: VER-006, VER-007, VER-009, VER-010, teamlead/verification-surface.json
Правило: Оракул должен быть фальсифицируемым по поведению, а не по именам и синтаксису.
Evidence: VER-007 засчитывает тест при наличии любого assert — assert True в функциях с нужными подстроками img01..ao10 даёт QA_ASSERT_COVERAGE_PASS. VER-009 ищет сетевые вызовы только по подстрокам в имени Call в замыкании функций со словом image: getattr/importlib/socket напрямую/subprocess с curl не ловятся. VER-010 полностью manual без машинного критерия полноты матрицы. В teamlead/verification-surface.json verifications=[] при ссылке пакета на VER-001..010. Сценарии F-002/F-005/F-006 (stale flag после очереди, pre-slot decode bound как поведенческий тест, межпроцессный sweep, pixel-bomb, log-injection) в AO отсутствуют.
Действия: Дополнить AO поведенческими тестами по F-002/F-005/F-006; VER-007 заменить мутационной/семантической проверкой ключевых инвариантов или ручным ревью маппинга ID→утверждения; VER-009 расширить на socket/subprocess/getattr-алиасы; заполнить verification-surface фактическими записями гейтов.
Проверка: Контрольный мутант (убрать recheck после слота / count до decode) обязан ронять хотя бы один тест; набор assert True не проходит покрытие.

5. АЛЬТЕРНАТИВЫ И АРХИТЕКТУРНЫЙ ВЫБОР
VERDICT=PASS
WHY=Workspace-read через --add-dir при сохранённом cwd/sess_key обоснованно выбран против прямого image_url в NDJSON (несовместим с parser, F-06/F-32), подмены cwd эталоном (ломает AC-005), сокрытия capability в DSH и staging только hot-subset (ломает cold fallback). Глобальная нумерация 1..K с msg_index-фильтром для resumed — разумная цена перематериализации истории против локальной перенумерации. Решение обратимо флагом для zero-image трафика; честно отмечено, что ходы с историей при выключенном флаге снова отклоняются. Альтернативы ресайза/перекодирования и decode-after-slot не рассмотрены, но это учтено в F-003/F-005 как доработка выбранного пути, а не опровержение выбора.

6. СООТВЕТСТВИЕ КОНТЕКСТУ И ПРОЦЕССУ
VERDICT=PASS
WHY=seed_recheck_duty по строковому сравнению сходится; границы изменений соблюдены на уровне дизайна. Пересчёт SHA без инструментов недоступен, сверены порядок и минимум по выданным дайджестам: rank_slots даёт 575707e1… (muse-wonder-full-1.0) < 622163df… (gemini-4-argon-high) < cc365dc5… (claude-sonnet-5-5-high) < cffd31df… (gpt-6.1-sol-high), ranked_order верен; исключение семейства автора OpenAI даёт triplet из трёх оставшихся семейств. В assign_hats минимум 09e444db… соответствует перестановке muse:claude:gemini и меньше остальных пяти (53391fa8…, 7472c2ef…, 9411074d…, ce379112…, fb031ff7…), рассадка k=1 muse-wonder-full-1.0, k=2 claude-sonnet-5-5-high, k=3 gemini-4-argon-high подтверждена. Coder-target ровно три файла (bridges/agy-bridge/server.py, fleet.json, tests/test_agy_bridge_resilience.py), core/корневой server.py/dynamic_config.json в git запрещены, frozen analysis не трогается. Замечание без отдельной находки: approval.decision_ids=[] при шести APPROVED AD и independent_review=NOT_REQUIRED при risk_triggers trust-boundary/external-attack-surface выглядят процессуально слабо, но пакет прямо передаёт обязательную внешнюю панель родителю и не симулирует её.

COVERAGE: 6/6 подкатегорий
FINDINGS_COMPLETE: 7
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
