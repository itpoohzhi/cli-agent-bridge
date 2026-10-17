# consensus-ledger (арх-панель, cycle 1, a2)

### F-001
- origin: Визионер · R1 · F-001
- rev: 4
- priority: non-blocking
- status: OWNER_DECIDED
- outcome: blocking
- resolved_in: owner
- votes: R1 Визионер=AUTHOR | D1 Реалист=D Скептик=A | D2 Скептик=M Реалист=A | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=O
- dissent: Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-003, architecture-packet.json#ASM-010, architecture-packe»; Скептик C1 «OBJECT F-001 — дефект: architecture-packet.json#ASM-010 допускает действие без наблюдаемых сигналов, но #AD-003 разрешает повтор при их отсу» → debate/c1
- owner_decision: 2026-10-15 ~18:15 MSK «F-001 (барьер повтора / ненаблюдаемое действие, ASM-010 vs AD-003): **blocking**» (owner-decisions.md, раздел «Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2»)
- amendments: rev 2 (D2, Скептик): priority=non-blocking; rev 3 (D3, Визионер): priority=blocking; rev 4 (D3, Скептик): priority=non-blocking; rev 5 (D3, Реалист): priority=non-blocking
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
- rev: 6
- priority: non-blocking
- status: OWNER_DECIDED
- outcome: blocking
- resolved_in: owner
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=O Реалист=C Скептик=O
- dissent: Визионер C1 «OBJECT F-002 — дефект: architecture-packet.json#AD-004 и #BND-004 заявляют, что синхронный sink «блокирует цикл чтения MSP не дольше 3 с на » → debate/c1; Скептик C1 «OBJECT F-002 — дефект: architecture-packet.json#AD-004 обещает блокировку чтения MSP не дольше 3 с, однако timeout устанавливается после зах» → debate/c1
- owner_decision: 2026-10-15 ~18:15 MSK «F-002 (таймаут live-записи после захвата _wlock, AD-004/BND-004): **blocking**» (owner-decisions.md, раздел «Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2»)
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking; rev 5 (D3, Визионер): priority=blocking; rev 6 (D3, Скептик): priority=non-blocking; rev 7 (D3, Реалист): priority=blocking
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
- rev: 6
- priority: non-blocking
- status: OWNER_DECIDED
- outcome: non-blocking
- resolved_in: owner
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=O
- dissent: Скептик C1 «OBJECT F-003 — дефект: architecture-packet.json#QA-004 включает cleanup и финальную выдачу в потолок 1800 с, но #AD-003 передаёт попытке вес» → debate/c1
- owner_decision: 2026-10-15 ~18:15 MSK «F-003 (бюджет 1800 с без резерва на cleanup/выдачу, grace после cancel): **non-blocking** (учесть в брифе Coder)» (owner-decisions.md, раздел «Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2»)
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking; rev 5 (D3, Визионер): priority=blocking; rev 6 (D3, Скептик): priority=non-blocking; rev 7 (D3, Реалист): priority=non-blocking
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
- rev: 4
- priority: non-blocking
- status: OWNER_DECIDED
- outcome: non-blocking
- resolved_in: owner
- votes: R1 Визионер=AUTHOR | D1 Реалист=D Скептик=A | D2 Скептик=M Реалист=A | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=O
- dissent: Реалист D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#CD-001, architecture-packet»; Скептик C1 «OBJECT F-004 — дефект: architecture-packet.json#AD-004 при P=`a` и несовместимом F=`b\n\nc` отбрасывает авторитетный текст, сохраняя успешно» → debate/c1
- owner_decision: 2026-10-15 ~18:15 MSK «F-004 (потеря reasoning при расхождении snapshot, CD-001): **non-blocking** (учесть в брифе Coder)» (owner-decisions.md, раздел «Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2»)
- amendments: rev 2 (D2, Скептик): priority=non-blocking; rev 3 (D3, Визионер): priority=blocking; rev 4 (D3, Скептик): priority=non-blocking; rev 5 (D3, Реалист): priority=non-blocking
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
- rev: 6
- priority: non-blocking
- status: OWNER_DECIDED
- outcome: blocking
- resolved_in: owner
- votes: R1 Визионер=AUTHOR | D1 Реалист=M Скептик=A | D2 Скептик=M Реалист=M | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=O
- dissent: Скептик C1 «OBJECT F-005 — дефект: architecture-packet.json#AD-007 и evolution.rollback обещают откат политики в denyUnmatched, но #AD-006 при setup-оши» → debate/c1
- owner_decision: 2026-10-15 ~18:15 MSK «F-005 (откат denyUnmatched обходится exec --yolo, AD-006/AD-007): **blocking**» (owner-decisions.md, раздел «Решение владельца 2026-10-15 ~18:15 MSK — арх-панель cycle-1, проход a2»)
- amendments: rev 2 (D1, Реалист): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D2, Реалист): priority=blocking; rev 5 (D3, Визионер): priority=blocking; rev 6 (D3, Скептик): priority=non-blocking; rev 7 (D3, Реалист): priority=non-blocking
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A | D3 Визионер=A Скептик=M Реалист=A | C1 Реалист=C
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D3, Скептик): priority=non-blocking
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A | D3 Визионер=A Скептик=M Реалист=A | C1 Реалист=C
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D3, Скептик): priority=non-blocking
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
- rev: 4
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=C
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D3, Визионер): priority=non-blocking; rev 5 (D3, Скептик): priority=non-blocking; rev 6 (D3, Реалист): priority=non-blocking
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
- status: WITHDRAWN
- outcome: excluded
- resolved_in: d3
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D | D3 Визионер=D Скептик=D Реалист=W
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005 прямо перечисляет дополнительные запреты web/reminde»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-38] — EVD-0»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, [F-09], [F-10]»; Визионер D3 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005,architecture-packet.json#THREAT-001,[F-38] — дополни»; Скептик D3 «— класс: invalid — контр-evidence: architecture-packet.json#EVD-005, architecture-packet.json#THREAT-001, docs/adr/0003-»
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
- status: WITHDRAWN
- outcome: excluded
- resolved_in: d3
- votes: R1 Реалист=AUTHOR | D1 Визионер=D Скептик=D | D2 Скептик=D Визионер=D Реалист=W | D3 Визионер=D Скептик=D Реалист=W
- dissent: Визионер D1 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Скептик D1 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Скептик D2 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Визионер D2 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»; Визионер D3 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004,architecture-packet.json#BND-004,architect»; Скептик D3 «— класс: duplicate_of:F-002 — контр-evidence: architecture-packet.json#AD-004, architecture-packet.json#BND-004, archite»
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A | D3 Визионер=M Скептик=M Реалист=A | C1 Реалист=C Скептик=C
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D3, Визионер): priority=non-blocking; rev 5 (D3, Скептик): priority=non-blocking
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
- status: WITHDRAWN
- outcome: excluded
- resolved_in: d3
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D | D3 Визионер=D Скептик=D Реалист=W
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005 предусматривает отдельный baseline и ограниченную зо»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, цитата Python-over»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, architecture-packe»; Визионер D3 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005,architecture-packet.json#AD-007, Python-overlay «пор»; Скептик D3 «— класс: invalid — контр-evidence: architecture-packet.json#BND-005, architecture-packet.json#AD-007, architecture-packe»
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A | C1 Реалист=C
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A | C1 Реалист=C
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
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=A | C1 Реалист=C
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
- rev: 4
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: c1
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=M | D2 Скептик=M Визионер=A | D3 Визионер=M Скептик=M Реалист=M | C1 Визионер=C Реалист=C Скептик=C
- dissent: —
- owner_decision: —
- amendments: rev 2 (D1, Скептик): priority=non-blocking; rev 3 (D2, Скептик): priority=non-blocking; rev 4 (D3, Визионер): priority=non-blocking; rev 5 (D3, Скептик): priority=non-blocking; rev 6 (D3, Реалист): priority=non-blocking
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
- status: WITHDRAWN
- outcome: excluded
- resolved_in: d3
- votes: R1 Реалист=AUTHOR | D1 Визионер=A Скептик=D | D2 Скептик=D Визионер=D | D3 Визионер=D Скептик=D Реалист=W
- dissent: Скептик D1 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»; Скептик D2 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»; Визионер D2 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002, architecture-packet.json#AD-003, architecture-packet»; Визионер D3 «— класс: invalid — контр-evidence: architecture-packet.json#AD-002,architecture-packet.json#AD-003,architecture-packet.j»; Скептик D3 «— класс: invalid — контр-evidence: architecture-packet.json#AD-001, architecture-packet.json#AD-002, architecture-packet»
- owner_decision: —
- amendments: —
- text (дословно, R1 Реалист):
> **F-12 [non-blocking] Подрешения a2 не имеют отдельных альтернатив с причиной выбора**
> - Якорь: architecture-packet.json#AD-002 (grace 15 с, защёлкивание), #AD-003 (абсолютный дедлайн, предикат и барьер), #AD-004 (префикс-монотонная заморозка).
> - Правило: новое решение должно иметь ≥2 альтернативы с причиной выбора.
> - Evidence: у каждого AD-NNN ≥2 альтернативы, так что формально критерий выполнен. Но отдельные подрешения a2 не имеют альтернатив: значение grace 15 с (обосновано только «диапазон панели 10–30 с»), абсолютный дедлайн против отдельного лимита очереди, барьер активности против запрета повтора после любого turn/start, префикс-монотонная заморозка против стриминга по item/completed.
> - Исправление: добавить в соответствующие AD по одной-две альтернативы с причиной. В ASM-010 уже названа контингенция «ужесточить до turn/start», её стоит вынести в alternatives AD-003.
> - Критерий проверки: каждое из перечисленных подрешений присутствует в alternatives соответствующего AD.
