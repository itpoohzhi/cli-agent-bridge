Ты — Скептик. Твоя задача — найти риски, слабые места, что сломается. Ключевой вопрос: «Почему это НЕ сработает?»

Ты оцениваешь архитектуру, а не код. Фокусируйся на структурных проблемах: циклические зависимости, нарушение слоёв, хардкод секретов, смешение ответственностей, отсутствие границ.

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

PANEL-NONCE: ab1999fe25d793a3
ARTIFACT-SHA256: ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22
Инструкция судье: первыми двумя строками ответа повтори дословно «PANEL-NONCE: ab1999fe25d793a3» и «ARTIFACT-SHA256: ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22».

Ты — судья архитектурного совета техлидов. Предмет оценки — Architecture Packet (машинный пакет архитектуры) для задачи muse-bridge (мост DeepSeek Harness → Meta Muse), а не код и не diff. Ниже приложен пакет, receipt ARCH_GATE, task envelope, handoff системного аналитика, evidence ledger, открытые вопросы, читаемая спецификация, proposal-ADR и решение владельца. Оцени, принял бы ты этот пакет как основу для кода (Coder стартует только после PASS панели).
Суди ЗАНОВО, не подтверждай прошлый вердикт автоматически. Других судей ты не видишь и их мнений не знаешь.
Все факты о системе в пакете должны опираться на факты [F-NN] приложенного evidence ledger. Каждое решение должно иметь альтернативы с причиной выбора, подтверждение (команду) и сценарии качества.

РЕЖИМ: architecture. Сравни с ≥2 альтернативными архитектурами; назови, что ломается при росте нагрузки.

КОНТЕКСТ. Владелец сообщил, что модель Muse Wonder в DeepSeek Harness «вообще не работает»: ход мышления до 7 минут, затем молчаливый перезапуск с нуля через exec и сетевой обрыв. Цель задачи, критерий готовности, REQ-ID и границы (внешний контракт моста заморожен) — в приложенных goal.md и task.json. Предыдущий этап (REQ-MUSE-001, прунинг контекста) уже в рабочем дереве и не пересматривается.

Анти-галлюцинация и факт-карта. Перед FAIL «нет X / не описано Y» перечитай приложенные артефакты целиком и не помечай то, что в тексте уже есть. Сущности из приложенного ledger и факт-карты существуют (имена команд, версии Muse CLI 1.4.7 и 1.4.8, поля протокола MSP). Чего нет в приложенных материалах и ты не уверен — пиши «не могу проверить», это не FAIL. Инструментов тебе не нужно: все входы ниже. Не изменяй никакие файлы.

ФАКТ-КАРТА (проверено оркестратором 2026-10-15; источники — в приложенном ledger):
- Muse CLI автообновился с 1.4.7 до 1.4.8 (15.10.2026 05:29 MSK); по методам, режимам approval и ошибкам схемы MSP stable они эквивалентны (ledger).
- На muse serve 1.4.7 и 1.4.8 явный approvalMode при session/start принимается для allowAll, promptUnmatched, onRequest, denyUnmatched; отказ approval_mode_ceiling (-32030) в логах моста встречался только на serve 1.4.2 (ledger).
- Решение владельца по политике approval: «Авторазрешение (allowAll)» (файл owner-decisions.md, приложен).
- Сетевые сбои Meta-стрима в этот день воспроизводились независимо от размера промпта (бенч в ledger); форвардер прокси 127.0.0.1:10816 — внешняя нестабильная зависимость вне репозитория.
- Версии и поля MSP проверяются по приложенному evidence ledger, не по памяти.

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

ПОДКАТЕГОРИИ РУБРИКИ (проходи по номерам; по каждой одна строка в формате `SUB <критерий>/<подкатегория>: PASS|FAIL|N/A — evidence (якорь пакета или правило)`):
1. Корректность: 1.1 логика решений AD-NNN и согласованность между ними; 1.2 граничные условия и режимы отказа; 1.3 соответствие фактам [F-NN] ledger.
2. Полнота: 2.1 покрытие REQ-MUSE-002, REQ-MUSE-003, REQ-MUSE-004 и ограничения REQ-MUSE-001; 2.2 пропущенные ветки, открытые ASM/OPEN и их допущения.
3. Реализуемость: 3.1 реализуемость в границах моста (bridges/muse-bridge/server.py) и тестов; 3.2 стоимость сопровождения, откат и деплой.
4. Риски: 4.1 безопасность и trust boundary (политика allowAll, инструменты не отключённые флагами); 4.2 данные, секреты, логирование; 4.3 эксплуатация (ретраи, прокси, автообновление CLI).
5. Альтернативы: 5.1 ≥2 альтернативы у каждого нового решения и причина выбора; 5.2 что ломается при росте нагрузки.
6. Соответствие контексту: 6.1 заморозка внешнего контракта и границы задачи; 6.2 правила репозитория и Python-overlay architecture.md; 6.3 verification surface (команды, red→green, тяжёлый путь).

ПРИЛОЖЕНИЕ architecture-packet:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/architecture-packet.json sha256=ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22
{
  "schema_version": "1.0",
  "task_id": "REQ-MUSE-002",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "profile": "python-aisdlc-gcge",
  "status": "APPROVED",
  "role_plan": {
    "path": ".ai-team/runs/muse-wonder-approval-20261015/plans/architect-01.json",
    "sha256": "7aacb3bf0bf5f3cd1857fad223dd66ae6551d3f5d626cbf0657222da6e2970af"
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
      "statement": "OPEN-04: item/delta с field summary.N могут приходить по ходу хода; мост логирует время первой summary-дельты от старта хода для закрытия вопроса наблюдением",
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
      "statement": "OPEN-06: approval/decide с разрешающим выбором продолжает ход; влияние turn/cancel на pending approval схемой не описано, поэтому cancel применяется только как терминальная деградация без ожидания продолжения хода",
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
      "choice": "Тот же ход продолжается: на запрос с id уходит receipt result={} тем же id, затем approval/decide с choiceId только из текущих availableChoices (decision=approved предпочтительнее approvedForSession, approvedPolicyAmendment не выбирается, requirementId дословно равен currentRequirementId, commandId через существующий _uuid7, sessionId из params); approval/requested без id ведёт к тому же decide без receipt, повтор по паре approvalId+requirementId подавляется дедупликацией, ошибка -32051 считается benign; terminal=false обрабатывается следующим обновлённым запросом; userInput/request получает receipt и userInput/cancel без передачи вопросов клиенту. Границы на ход: не более 10 approval/decide и не более 3 userInput/cancel (константы модуля); при отсутствии разрешающего choice, ошибке decide (-32052/-32053/-32050) или превышении границы ход завершается внутри serve выбором abort/denied при его наличии, иначе turn/cancel и терминальной ошибкой клиенту без exec-рестарта. Каждое решение логируется одной строкой безопасных полей через существующую редакцию без rawArgs. Запись в stdin serve после turn/start ограничена дедлайном хода, а не setup-окном 30 с",
      "alternatives": [
        "decide с denied при любом запросе: действие отклоняется, продолжение хода после отказа не наблюдалось (OPEN-06), противоречит смыслу allowAll из AD-001",
        "немедленный turn/cancel при любом запросе: ход теряется без переигрыва, REQ-MUSE-002 выполнен только формально, результат пользователю ошибка вместо ответа",
        "сохранить ServeUnavailable и exec-рестарт как fallback: возвращает измеренную потерю EVD-003 и двойной вызов модели"
      ],
      "drivers": [
        "receipt не меняет состояние, решение обязано идти отдельной командой, отклонить без решения нельзя (EVD-006)",
        "choiceId свободная строка без enum и живой payload неизвестен, поэтому выбор только из availableChoices по полю decision (EVD-021)",
        "approval приходил через 275 с и 412 с после старта хода при setup-окне записи 30 с (EVD-003, EVD-013): без продления _write_until decide упал бы в ServeUnavailable",
        "MAX_CONCURRENT=2: цикл запросов внутри хода обязан иметь счётный предел помимо дедлайна 1800 с (EVD-013)"
      ],
      "consequences": [
        "ServeRun получает отправку JSON-RPC ответа по чужому id и учёт pending decide в главном цикле (голые ack чужих rid по-прежнему игнорируются, ошибка pending decide ведёт в деградацию)",
        "политика выбора изолирована чистой границей ApprovalPolicy (BND-001): смена AD-001 не трогает транспорт, ретрай и SSE",
        "userInput без пользователя завершается cancelled; если модель после этого завершает ход ошибкой, действует существующий путь model error без fallback",
        "фикстура install_protocol_wrapper расширяется реальным payload с availableChoices и ветками terminal=false и userInput; старый тест approval заменяется, тесты ServeUnavailable для прочих транспортных сбоев сохраняются"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; receipt и decide в rpc.jsonl, choiceId из availableChoices, второй запрос при terminal=false решён, userInput отменён, границы 10 и 3 останавливают цикл, approval позже setup-окна решается в том же ходе, канарейка rawArgs отсутствует в логе, exec не запущен"
      }
    },
    {
      "id": "AD-003",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Как ограниченно повторять транзиентный net-timeout и родственные транспортные сбои, не нарушая бюджет контекстного retry и идемпотентность SSE (REQ-MUSE-003)?",
      "choice": "Единый транзиентный повтор на уровне цикла попыток Handler вместо внутреннего exec-only повтора: класс ошибки только по явным маркерам в сыром канале ошибки ([net-timeout], timed out waiting for response data, transport_connect_unreachable из текста REQ-MUSE-003, существующий network connection could not be opened), флаг в результате попытки по образцу hard_threshold; не более 2 повторов с паузой 2 с затем 4 с плюс джиттер до 1 с, пауза прерывается уходом клиента; общий бюджет хода TIMEOUT_S=1800 с от первой попытки, каждая следующая попытка получает только остаток и не стартует при остатке не больше 30 с; отдельный счётчик от контекстного retry ADR-001.3, при hard threshold приоритет у контекстного повтора с прунённым промптом; повтор только при rc не 0, клиент на месте, _content_started ложен, первая группа процессов подтверждена мёртвой, тот же слот без повторного acquire; состояния timeout, spawn_failed, client_gone не повторяются",
      "alternatives": [
        "только расширить список маркеров внутреннего exec-повтора: serve net-timeout по-прежнему терминальная ошибка без второй попытки, бюджет и fallback взаимодействуют неявно",
        "повтор только внутри ServeRun новым serve-процессом: exec-путь и exec-after-fallback остаются без покрытия, два механизма повтора расходятся",
        "без повтора моста с опорой на provider attempts CLI: бенч и лог показывают финальный отказ после исчерпания попыток провайдера (EVD-011), REQ-MUSE-003 не выполнен"
      ],
      "drivers": [
        "быстрые сбои за 20 с и 31.5 с при успешных ходах 51.1-281.3 с оставляют запас бюджета 1800 с на свежий процесс и новое соединение (EVD-011, EVD-013)",
        "CLI уже повторяет поток провайдера (attempt 3/4, 4/4, after 5 provider attempts), поэтому повтор моста мал и ограничен (EVD-011, ASM-005)",
        "клиентский предел 1900 с запрещает складывать полные 1800 с на попытку (EVD-016)",
        "повтор после первого контентного кадра ломает идемпотентность потока, инвариант EVD-018 расширяется на первую live reasoning-дельту из AD-004"
      ],
      "consequences": [
        "внутренний однократный network retry внутри exec-after-fallback поглощается транзиентным счётчиком; тест test_t18 обновляется с сохранением утверждения, что контекстный бюджет транзиентом не расходуется",
        "ServeRun и Run получают остаток бюджета вместо полного TIMEOUT_S на повторных попытках; контекстный повтор второй попытки получает тот же остаток, что ужесточает прежний допущенный предел 2xTIMEOUT_S до исходного замысла ADR-001.3",
        "худший случай остановок ограничен суммой пауз не более 8 с внутри бюджета 1800 с; частичный текст упавших попыток по-прежнему отбрасывается, клиенту виден один терминальный исход",
        "non-stream JSON повторяется на тех же условиях, так как кадров клиенту до исхода нет"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
        "expected": "exit 0; net-timeout затем успех даёт ровно 2 попытки и один [DONE] без error между ними, три отказа дают терминальную ошибку после 3 попыток, нет повтора после _content_started, при уходе клиента, при неподтверждённой смерти группы и при остатке бюджета не больше 30 с"
      }
    },
    {
      "id": "AD-004",
      "status": "APPROVED",
      "kind": "two-way",
      "question": "Что получает SSE-клиент во время долгого мышления, кроме пустых keepalive-чанков (REQ-MUSE-004)?",
      "choice": "Live reasoning_content только на serve-пути: ServeRun через sink Handler отдаёт прирост summary.N дельтами того же поля и той же формы чанка по мере накопления, включая добавки из item/completed; конкатенация live-дельт равна сегодняшнему единому reasoning-чанку того же хода, финальный _send_sse доотдаёт только неотправленный хвост без дубля; пустой data-keepalive каждые 15 с сохраняется без перехода на SSE-комментарии; content и tool_calls по-прежнему буферизуются до конца хода (разбор tool-разметки по полному тексту не меняется); первая непустая reasoning-дельта выставляет _content_started под _wlock и тем закрывает окно повторов AD-003 и контекстного retry; сбой live-записи отключает только live на этот ход без исключения в ServeRun; turn/modelRetryScheduled логируется полями attempt/maxAttempts/retryDelayMs/errorKind и клиенту текстом не отдаётся; время первой summary-дельты от старта хода логируется для OPEN-04; non-stream ответы без изменений",
      "alternatives": [
        "SSE-комментарий : keepalive по образцу droid-моста вместо пустых data-чанков: реакция pi-ai на комментарии не проверена (OPEN-03), тест test_s1 закрепляет обратное, выигрыш против working keepalive не показан фактами",
        "live content вместе с reasoning: частичная tool-разметка утекает клиенту до разбора _split_tool_calls по полному тексту, нужен потоковый парсер уровня droid-моста вне объёма REQ-MUSE-004",
        "статус-кво буферизации: клиент 205-237 с длинных ходов и дольше видит только пустые чанки, прогресс мышления не показан (EVD-011, EVD-014)"
      ],
      "drivers": [
        "тот же клиент DSH уже накапливает live reasoning_content от droid-моста, поле и форма чанка моста не меняются (EVD-015, EVD-016)",
        "пустые data-чанки доказано держат соединение против клиентского ожидания заголовков около 600 с (F-47 в ledger, EVD-014)",
        "summary.N единственный прогресс мышления в MSP v1, сырой reasoning-текст протокол не стримит (docstring ServeRun, EVD-014)",
        "первая live-дельта сдвигает границу безопасного повтора, инвариант обязан быть явным (EVD-018)"
      ],
      "consequences": [
        "единственный contract delta пакета CD-001: reasoning_content приходит несколькими кадрами вместо одного, порядок reasoning раньше content и финальная конкатенация сохранены",
        "тест test_s1 сохраняется по keepalive и дополняется порядком кадров; exec-ходы live reasoning не имеют и поведение не меняют",
        "если сервер шлёт summaries только в конце хода (OPEN-04), live вырождается в сегодняшнюю выдачу, соединение по-прежнему держит keepalive; факт фиксируется логом первой дельты на тяжёлом пути",
        "все записи SSE по-прежнему только через _sse_write под _wlock из Handler, ServeRun сокет не трогает (BND-004)"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
        "expected": "exit 0; reasoning-дельты приходят до финального кадра в порядке индексов, их конкатенация равна буферизованному варианту, дубля в финале нет, пустые keepalive-чанки сохранены и : keepalive отсутствует, ровно один [DONE]"
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
      "choice": "Каждый ServeRun логирует serverInfo.version, fingerprint схемы и эффективный approvalMode сессии; отказ session/start с -32030 approval_mode_ceiling один раз внутри того же ServeRun повторяет старт без approvalMode с warning в логе и опорой на внутриходовый decide AD-002; неизвестная версия CLI ход не блокирует и отдельно помечается в логе init; закрепление версии лаунчера вне объёма (OPEN-09)",
      "alternatives": [
        "жёсткий отказ хода на неизвестной версии: автообновление 1.4.7 -> 1.4.8 без участия моста остановило бы боевой мост (EVD-019)",
        "без деградации при -32030: возврат потолка старой версии снова уводит каждый ход с approval в exec-рестарт через ServeUnavailable общего вида"
      ],
      "drivers": [
        "потолок существовал на 1.4.2 и отсутствует на 1.4.7/1.4.8, поведение зависит от версии (EVD-004, EVD-008)",
        "лаунчер обновляется сам и удаляет прежний бинарь, мост версию не контролирует (EVD-019)"
      ],
      "consequences": [
        "деградация видна оператору одной warning строкой с версией сервера, политика AD-001 при этом честно помечена неприменённой на этом ходе",
        "фейковая фикстура получает ветку отказа -32030 на первый session/start"
      ],
      "approval_required": false,
      "confirmation": {
        "kind": "test",
        "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
        "expected": "exit 0; при -32030 на session/start с allowAll второй старт без поля в том же ServeRun, warning в логе, ход доводится через decide без второго процесса serve"
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
      "response": "тот же процесс serve продолжает ход после receipt и approval/decide, exec не запускается, второй turn/start не уходит",
      "response_measure": "в фейковом MSP ровно один turn/start и нет exec-argv; на тяжёлом пути в bridge.log строка решения approval и done via=serve без fallback exec по этому ходу",
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
      "response_measure": "строка лога содержит toolName, subject.kind, protectedWrite, judgeEscalated, choiceId и decision; канарейка rawArgs и тело промпта отсутствуют в логе, JSON и SSE; serve argv без --disable-sandbox",
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
      "response_measure": "ровно 2 попытки, пауза между ними 2 с плюс джиттер до 1 с, один [DONE] и ни одного error-кадра между попытками, суммарно не дольше TIMEOUT_S от первой попытки",
      "verification_ids": ["VER-002", "VER-010"]
    },
    {
      "id": "QA-004",
      "quality": "reliability",
      "source": "транспорт Meta через ProxyRack",
      "stimulus": "net-timeout на каждой попытке, включая длинный сбой 452 с из лога",
      "environment": "клиент на месте, MAX_CONCURRENT=2",
      "artifact": "цикл попыток Handler и освобождение слота",
      "response": "после исчерпания повторов один терминальный отказ существующего формата 502 или SSE error с одним [DONE]",
      "response_measure": "не более 3 попыток суммарно, сумма пауз не более 8 с, остаток бюджета не больше 30 с останавливает повтор раньше, все группы процессов мертвы и слот освобождён ровно один раз",
      "verification_ids": ["VER-002", "VER-005"]
    },
    {
      "id": "QA-005",
      "quality": "compatibility",
      "source": "serve присылает первую summary-дельту, затем ход падает net-timeout",
      "stimulus": "транзиентная ошибка после первой live reasoning-дельты клиенту",
      "environment": "stream=true, live reasoning включён AD-004",
      "artifact": "граница _content_started",
      "response": "повтор запрещён, клиент получает один терминальный error и один [DONE] без дубля reasoning",
      "response_measure": "ровно 1 попытка при _content_started истинном; тот же сбой до первой дельты повторяется по QA-003",
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
      "response_measure": "первый reasoning-кадр раньше финального кадра в фейковом тесте с задержанными дельтами; конкатенация дельт равна буферизованному reasoning; на тяжёлом пути лог фиксирует секунды до первой summary-дельты (закрытие OPEN-04 наблюдением, порог заранее не выдумывается)",
      "verification_ids": ["VER-003", "VER-009"]
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
      "response": "ход деградирует на старт без поля с warning и доводится внутриходовым decide, версия и fingerprint видны в логе",
      "response_measure": "фейковая ветка -32030 даёт второй session/start без поля в том же процессе и завершённый ход; строка serve init содержит версию сервера на каждом ходе",
      "verification_ids": ["VER-001", "VER-008"]
    }
  ],
  "boundaries": [
    {
      "id": "BND-001",
      "component": "ApprovalPolicy (чистое решение по снимку params внутри server.py)",
      "responsibility": "по params approval или userInput выдать действие approve с конкретным choiceId, deny/abort, cancel-user-input или fail-turn и аудит-запись только безопасных полей; единственное место знания политики AD-001",
      "allowed_dependencies": ["stdlib", "_redact_secrets для аудит-строки"],
      "forbidden_dependencies": ["ServeRun._send и любой I/O", "subprocess", "Handler и SSE-сокет", "чтение rawArgs дальше факта наличия", "глобальное изменяемое состояние между ходами"],
      "verification_ids": ["VER-001"]
    },
    {
      "id": "BND-002",
      "component": "ServeRun (MSP-транспорт одного хода serve)",
      "responsibility": "процесс serve на запрос, handshake с approvalMode и деградацией AD-006, receipt и команды decide/cancel/turn-cancel строго по решению BND-001, дедупликация и границы решений, накопление текста и summaries, вызов live-sink Handler без владения сокетом",
      "allowed_dependencies": ["ApprovalPolicy (BND-001)", "_uuid7", "_log", "_terminate_run", "live-sink колбэк Handler"],
      "forbidden_dependencies": ["прямая запись в SSE-сокет", "запуск exec Run", "захват _slots", "решение политики вне BND-001", "логирование rawArgs и тел вопросов"],
      "verification_ids": ["VER-001", "VER-003"]
    },
    {
      "id": "BND-003",
      "component": "Handler, цикл попыток хода (run_attempt и окружающие повторы)",
      "responsibility": "serve-first с exec fallback только по транспортному ServeUnavailable без approval, отдельные счётчики контекстного и транзиентного повторов, общий дедлайн TIMEOUT_S от первой попытки с передачей остатка, проверки клиента, _content_started и dead_confirmed, один слот на весь ход",
      "allowed_dependencies": ["ServeRun (BND-002)", "Run (exec)", "_prune_messages и _context_limit", "_slots один acquire на запрос", "_watch_client"],
      "forbidden_dependencies": ["повторный _slots.acquire для повтора", "повтор при _content_started или ушедшем клиенте", "второй контекстный retry", "полный TIMEOUT_S каждой повторной попытке", "content-кадры между попытками"],
      "verification_ids": ["VER-002", "VER-004"]
    },
    {
      "id": "BND-004",
      "component": "Handler, SSE-эмиттер (_sse_begin, _keepalive_loop, live reasoning sink, _send_sse)",
      "responsibility": "единственный писатель в сокет: role-кадр, пустой keepalive 15 с в фазе OPEN, live reasoning-дельты с выставлением _content_started под _wlock, финальная выдача без дубля reasoning, один [DONE]",
      "allowed_dependencies": ["_sse_write под _wlock", "_sse_chunk", "_split_sse_chunks"],
      "forbidden_dependencies": ["запись в обход _sse_write", "удержание _wlock во время выполнения модели", "live content и tool_calls до конца хода", "SSE-комментарии keepalive в этом изменении", "исключения live-записи в ServeRun"],
      "verification_ids": ["VER-003", "VER-005"]
    },
    {
      "id": "BND-005",
      "component": "Внешняя эксплуатационная граница (DSH, muse CLI и Meta, прокси :10816, launchd-зеркало)",
      "responsibility": "мост не меняет профили DSH, лаунчер и прокси; деплой только копией server.py в ~/.dsh/bridges/muse-bridge/ и перезапуском com.user.dsh-muse-bridge после бэкапа; источник net-timeout и версии CLI остаются внешними рисками",
      "allowed_dependencies": ["~/.dsh/bridges/muse-bridge/server.py зеркало", "launchctl kickstart com.user.dsh-muse-bridge", "GET /health и /v1/models с ключом моста"],
      "forbidden_dependencies": ["правки cordis.patch.yml профилей DSH в этом изменении", "закрепление или откат версии Muse CLI мостом", "изменения форвардера ProxyRack", "записи muse-spark-* в профилях"],
      "verification_ids": ["VER-008", "VER-009"]
    }
  ],
  "contract_deltas": [
    {
      "id": "CD-001",
      "type": "behavior",
      "producer": "muse-bridge SSE на POST /v1/chat/completions stream=true, только serve-путь",
      "consumer": "клиент DSH (openai-completions, OpenAI SDK и pi-ai)",
      "change": "delta.reasoning_content приходит несколькими кадрами по ходу мышления вместо одного кадра после хода; поле, форма чанка chat.completion.chunk, порядок reasoning раньше tool_calls и content, финальные кадры и [DONE] без изменений; конкатенация дельт равна прежнему единому значению того же хода",
      "compatibility": "аддитивная фрагментация существующего поля: OpenAI-стрим определён накоплением дельт, тот же клиент уже накапливает live reasoning_content droid-моста (EVD-015), профиль объявляет supportsReasoningEffort=true (EVD-016); non-stream JSON, exec-ходы, /health и /v1/models не затронуты; новых полей, путей и кодов нет",
      "verification_ids": ["VER-003", "VER-009"]
    }
  ],
  "views": [
    {
      "id": "VIEW-001",
      "type": "dynamic",
      "question": "Как ход переживает approval внутри serve: session/start allowAll, receipt, decide, terminal=false, userInput/cancel, деградация без exec?",
      "artifact_ref": ".ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md#2-req-muse-002-approval-без-перезапуска-хода"
    },
    {
      "id": "VIEW-002",
      "type": "dynamic",
      "question": "Как взаимодействуют контекстный и транзиентный повторы, общий дедлайн, _content_started и уход клиента?",
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
    "compatibility": "Внешний OpenAI-контракт заморожен, единственный дельта-эффект CD-001 внутри существующего поля; non-stream, exec-путь, /health, /v1/models, окна моделей и профили DSH без изменений; смешанных версий внутри одного процесса нет, перезапуск моста атомарно меняет поведение всех новых ходов, идущие ходы завершаются старым процессом только до перезапуска launchd",
    "migration": "NOT_APPLICABLE: персистентных данных и схем хранения нет, serve-сессия создаётся на запрос с --no-session-log, состояние повторов и approval живёт только внутри хода; обновляются код репозитория, тесты и деплой-копия server.py",
    "rollout": "Coder на ветке bugfix/muse-wonder-approval-retry-liveness от фактического дерева dev с REQ-MUSE-001 (git diff зафиксирован до работы, в dev не коммитить); red затем green тесты; бэкап repo и зеркала server.py в ~/work/backups с датой; после ACCEPT панели и MR человеком копия server.py в ~/.dsh/bridges/muse-bridge/server.py, launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge, проверка VER-008, затем тяжёлый путь VER-009 владельцем; строка ADR 0003 добавляется в docs/adr/INDEX.md тем же MR после материализации proposal оркестратором",
    "rollback": "Восстановить server.py из бэкапа в репозитории и в ~/.dsh/bridges/muse-bridge/server.py и перезапустить com.user.dsh-muse-bridge той же командой kickstart; данные не мигрировали, профили DSH не менялись, поведение возвращается к ServeUnavailable с exec-фолбэком и буферизованному reasoning целиком"
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
        "mitigation": "Write и shell остаются отключены хостом, песочница не отключается, workspace ограничен каталогом моста, каждое авторазрешение пишется аудит-строкой безопасных полей для последующего разбора владельцем; селективный запрет по факту payload отложен до данных OPEN-01 и не выдумывается",
        "verification_ids": ["VER-001", "VER-009"]
      },
      {
        "id": "THREAT-002",
        "scenario": "Логирование approval уносит rawArgs, вопросы userInput или отражённый промпт с секретами в bridge.log и ответы клиенту",
        "mitigation": "Allowlist полей аудита в BND-001, запрет rawArgs и тел вопросов, вся диагностика через _redact_secrets и удаление отражённых промптов обеих попыток как в REQ-MUSE-001, канареечные тесты",
        "verification_ids": ["VER-001", "VER-005"]
      },
      {
        "id": "THREAT-003",
        "scenario": "Цикл approval или userInput внутри хода либо каскад повторов удерживает оба слота MAX_CONCURRENT=2 и блокирует мост для владельца",
        "mitigation": "Счётные границы 10 decide и 3 cancel на ход, общий дедлайн 1800 с, не более 2 транзиентных повторов, надзор ухода клиента убивает группу, слот один на ход с карантином неподтверждённой смерти",
        "verification_ids": ["VER-001", "VER-002"]
      },
      {
        "id": "THREAT-004",
        "scenario": "Транзиентный повтор переигрывает промпт после частичных побочных эффектов первой попытки и удваивает действие или вывод",
        "mitigation": "На обоих путях write и shell отключены, повтор только до первого контентного кадра при подтверждённой смерти первой группы, частичный текст упавших попыток отбрасывается, клиент видит один исход",
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
      "mitigation": "Флаги хоста и песочница сохранены, аудит каждого решения безопасными полями с первого хода, тяжёлый путь владельца сверяет лог решений с ожидаемой работой; селективная политика только отдельным решением по собранным payload",
      "verification_ids": ["VER-001", "VER-009"]
    },
    {
      "id": "RISK-002",
      "scenario": "Повторы моста складываются с повторами провайдера CLI и растягивают отказ при живом общем сбое транспорта (OPEN-05, OPEN-08)",
      "probability": "high",
      "impact": "medium",
      "mitigation": "Не более 2 повторов, паузы суммарно не более 8 с, общий дедлайн 1800 с с остатком на попытку, modelRetryScheduled логируется для разбора наложения",
      "verification_ids": ["VER-002", "VER-010"]
    },
    {
      "id": "RISK-003",
      "scenario": "Live reasoning сужает окно безопасного повтора и при ошибке учёта хвоста дублирует или теряет часть reasoning в финале",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Инвариант конкатенации live равен буферизованному варианту, _content_started только под _wlock на первой непустой дельте, финальная доотдача только хвоста, парные тесты до и после первой дельты",
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
      "mitigation": "AD-006: версия и fingerprint в логе каждого хода, однократная деградация без поля при -32030, неизвестная версия не останавливает мост",
      "verification_ids": ["VER-001", "VER-008"]
    },
    {
      "id": "RISK-006",
      "scenario": "Незакоммиченный REQ-MUSE-001 в дереве dev и единственная деплой-копия делают откат зависимым от бэкапа, ошибка копирования затирает рабочее состояние",
      "probability": "medium",
      "impact": "high",
      "mitigation": "git diff до работы Coder, отдельная ветка, бэкап обеих копий server.py в ~/work/backups до перезаписи, cmp зеркала и health после перезапуска до тяжёлого пути",
      "verification_ids": ["VER-005", "VER-008"]
    },
    {
      "id": "RISK-007",
      "scenario": "Summary-дельты на effort=max приходят только в конце хода, и прогресс REQ-MUSE-004 сводится к прежнему keepalive (OPEN-04)",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Лог времени первой дельты на каждом serve-ходе и обязательная фиксация факта на тяжёлом пути; при подтверждении пакет честно помечает прогресс недостигнутым без смены транспорта в этом изменении",
      "verification_ids": ["VER-003", "VER-009"]
    },
    {
      "id": "RISK-008",
      "scenario": "Форма живого availableChoices отличается от схемы фикстуры (scope, policy amendment, пустой список), и decide получает -32052 или выбирает лишнее разрешение",
      "probability": "medium",
      "impact": "medium",
      "mitigation": "Выбор только из текущих choices по decision с запретом policy amendment, ошибки decide ведут в терминальную деградацию без exec, аудит пишет список choiceId для сверки с первым живым ходом",
      "verification_ids": ["VER-001", "VER-009"]
    }
  ],
  "verification_surface": [
    {
      "id": "VER-001",
      "requirement_ids": ["REQ-MUSE-002", "AD-001", "AD-002", "AD-006", "QA-001", "QA-002", "QA-008", "BND-001", "BND-002", "RISK-001", "RISK-004", "RISK-005", "RISK-008", "THREAT-001", "THREAT-002", "THREAT-003"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'Approval'",
      "expected": "exit 0; red без фикса и green с фиксом: allowAll в session/start, receipt и decide с choiceId из availableChoices, terminal=false, userInput/cancel, границы 10 и 3, деградация без exec, -32030 повтор без поля, канарейка rawArgs отсутствует в логе",
      "environment": "локальный репозиторий, фейковый MSP через расширенный install_protocol_wrapper, модельных ходов нет",
      "owner": "verifier"
    },
    {
      "id": "VER-002",
      "requirement_ids": ["REQ-MUSE-003", "AD-003", "QA-003", "QA-004", "QA-005", "BND-003", "RISK-002", "RISK-003", "THREAT-003", "THREAT-004"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'TransientRetry'",
      "expected": "exit 0; каждый маркер классифицируется, не более 2 повторов с паузами 2 с и 4 с плюс джиттер до 1 с (в тестах константы ужаты monkeypatch), общий дедлайн и остаток 30 с соблюдены, нет повтора после _content_started, при уходе клиента, неподтверждённой смерти группы и на состояния timeout и spawn_failed, контекстный счётчик не расходуется (обновлённый test_t18)",
      "environment": "локальный репозиторий, фейковые serve и exec с терминальными ошибками net-timeout",
      "owner": "verifier"
    },
    {
      "id": "VER-003",
      "requirement_ids": ["REQ-MUSE-004", "AD-004", "QA-005", "QA-006", "BND-002", "BND-004", "CD-001", "RISK-003", "RISK-007", "THREAT-004"],
      "kind": "command",
      "command": "uv run --no-project --with pytest python -m pytest -q tests/test_muse_bridge_killpg.py -k 'LiveReasoning or test_s1'",
      "expected": "exit 0; дельты reasoning_content до финального кадра в порядке summary-индексов, конкатенация равна буферизованному варианту без дубля хвоста, пустые data-keepalive сохранены, : keepalive отсутствует, ровно один [DONE], сбой live-записи не роняет ход",
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
      "expected": "exit 0; весь файл зелён: прежний baseline 67 passed сохранён по смыслу, заменён только тест approval-контракта и обновлён test_t18 по AD-003, добавлены Approval, TransientRetry и LiveReasoning тесты; ни один прежний тест не удалён и не помечен skip ради зелени",
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
      "requirement_ids": ["REQ-MUSE-002", "REQ-MUSE-003", "REQ-MUSE-004", "QA-001", "QA-006", "BND-005", "CD-001", "RISK-001", "RISK-004", "RISK-007", "RISK-008", "THREAT-001"],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate тяжёлого пути: в существующем DSH-слоте владельца на длинной сессии живой ход muse-wonder-full-1.0 effort=max рабочего размера с вызовом инструмента, повторный ход и два параллельных хода завершаются без fallback exec по approval и без потери хода; в UI виден прирост reasoning во время мышления либо лог первой summary-дельты честно фиксирует её приход только в конце (OPEN-04); в bridge.log аудит-строки approval безопасными полями сверены владельцем с выполненной работой, done via=serve; короткий контрольный ход muse-spark проходит. Без этого gate слова готово и работает запрещены",
      "environment": "живой DSH-слот владельца, боевой мост :9886 после VER-008, модельные ходы выполняет владелец или verifier его руками, не Coder",
      "owner": "owner"
    },
    {
      "id": "VER-010",
      "requirement_ids": ["REQ-MUSE-003", "AD-003", "QA-003", "RISK-002"],
      "kind": "manual",
      "command": null,
      "expected": "Бинарный gate: на отдельном экземпляре моста на другом порту с MUSE_BRIDGE_CLI на заглушку, отдающую net-timeout на первой попытке и успех на второй, запросы JSON и SSE завершаются успехом после ровно одного повтора внутри бюджета; при net-timeout на всех попытках терминальный 502 или SSE error и один [DONE] после 3 попыток; боевой мост не затронут",
      "environment": "отдельный экземпляр моста с заглушкой CLI, не боевой :9886",
      "owner": "verifier"
    }
  ],
  "protected_paths": ["docs/adr/0003-muse-serve-approval-allowall.md"],
  "materialization": [
    {
      "source": "architecture/proposals/docs/adr/0003-muse-serve-approval-allowall.md",
      "target": "docs/adr/0003-muse-serve-approval-allowall.md",
      "sha256": "fcf1aea898d05a67857bcf30d812c0217ede954f0fea5d17aba596d278335c30"
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
      "question": "OPEN-01: какой инструмент и какие choiceId приходят в живом approval/request на wonder при --disable-write --disable-shell; закрывается аудит-логом первого живого хода, селективная политика после этого отдельным решением",
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
      "question": "OPEN-04: приходят ли summary.N по ходу хода на effort=max и за сколько секунд до конца; закрывается логом первой дельты на тяжёлом пути",
      "blocking": false
    },
    {
      "id": "Q-005",
      "question": "OPEN-05: семантика after N provider attempts и конфигурируемые ключи повторов CLI, приход turn/modelRetryScheduled на живом ходе 1.4.8; мост ограничивается своими 2 повторами и логированием",
      "blocking": false
    },
    {
      "id": "Q-006",
      "question": "OPEN-06: гасит ли turn/cancel pending approval и как модель ведёт себя после denied; пакет применяет cancel только как терминальную деградацию и denied не использует как основной путь",
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
    }
  ],
  "deferred": [
    "селективная политика approval по собранным живым payload (deny по toolName или subject.kind) отдельным решением после OPEN-01",
    "переход keepalive на SSE-комментарии : keepalive и правка формулировки README после живой проверки OPEN-03",
    "live-стрим content с потоковым разбором tool-разметки уровня droid-моста",
    "проброс turn/modelRetryScheduled клиенту отдельным сигналом вместо только лога",
    "закрепление версии Muse CLI против автообновления лаунчера (OPEN-09)",
    "env-переопределение констант повторов и границ approval"
  ]
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ receipt-ARCH_GATE:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/receipts/arch-gate.json sha256=49bfc884c895d803efcf7129dfee7473a76ee78d3d111f21f1a307eb13a8fc9c
{
  "schema_version": "1.0",
  "gate": "ARCH_GATE",
  "status": "PASS",
  "run_id": "muse-wonder-approval-20261015",
  "criticality": "S2",
  "packet_sha256": "ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22",
  "verification_surface_sha256": "a2ced7f7f67c16cfc8b4efbdcaf68c0a3b317e99ca8e43c562d2d869adc2cab3",
  "protected_paths_sha256": "bd638019a75b48326596429c6bad22aacba068a0c93898603a23124255ae1015",
  "architect_worktree_sha256": "8a0ae60dc08692ca5421169b1e217b6fc705d3078df289c79127afd22cce6e39",
  "materialized_targets": 1
}
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ task-envelope:
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/task.json sha256=7644d129cdada3406f6a553811bece7c3cdd8228718e7a5469effc9fc7664875
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
    "packet_sha256": "ebfa59a9869c9deb8390e2fa060ccc980bbafb96ca7cb045a8e3e73e7a78ea22",
    "verification_surface_sha256": "a2ced7f7f67c16cfc8b4efbdcaf68c0a3b317e99ca8e43c562d2d869adc2cab3",
    "protected_paths_sha256": "bd638019a75b48326596429c6bad22aacba068a0c93898603a23124255ae1015"
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
<<<ARTIFACT /tmp/cel-runs/muse-wonder-serve-approval/owner-decisions.md sha256=670e8c22bbfdbd668b487898f440db7105b68aa1cd1625acee68d30a5eb63d7d
2026-10-15 05:44 MSK | OPEN-07 (политика approval для неинтерактивного моста) | владелец выбрал в чате: «Авторазрешение (allowAll)» | вопрос и варианты: denyUnmatched(рек.)/allowAll/передача пользователю DSH/сначала узнать payload | риск принят владельцем: модель получает свободу действий в рамках того, что не отключено флагами serve (--disable-write --disable-shell остаются; sandbox не отключать)
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
<<<ARTIFACT ~/work/src/cli-agent-bridge/.ai-team/runs/muse-wonder-approval-20261015/architecture/arch-spec.md sha256=9ad19b8f6da675cf31d9a86a93f126e06f3f77f40cc7177f86b8612e09871fb4
# Архитектурная спецификация: muse-bridge — approval без перезапуска хода, повтор net-timeout, живость долгих ходов

Статус пакета: `APPROVED` (валидатор фазы approved зелёный, ARCH_GATE впереди).
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
AD-006 (деградация при потолке версии, APPROVED). Границы: BND-001, BND-002.

### 2.1 Последовательность хода (VIEW-001)

```text
ServeRun: spawn serve (флаги без изменений)
  initialize -> лог serverInfo.version + schema fingerprint (уже есть)
  initialized (notify)
  session/start {commandId, workspaceRoot, providerId=meta, modelId,
                 approvalMode="allowAll"}
    -> ошибка -32030: один повтор session/start без approvalMode в том же
       процессе + warning с версией (AD-006)
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
выбранный `choiceId` и его `decision`, счётчик решения в ходе. Транспорт пишет её
одной строкой `_log` (редакция существующая). Пример формы (значения иллюстративны):

```text
approval_decide tool=web_search subject=tool protected=0 judge=0 choices=[c1,c2] chosen=c1 decision=approved n=1
```

### 2.3 Транспорт decide в ServeRun (BND-002)

- Receipt: новый путь отправки ответа по серверному `id` дословно (тип id не
  преобразуется), тело `result: {}` (RequestReceipt, EVD-006). Ошибка записи —
  существующий `ServeUnavailable` транспортного сбоя.
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

На один ход: не более 10 `approval/decide` и не более 3 `userInput/cancel`
(константы модуля, §8). Обоснование меры: в наблюдаемой истории ход умирал на
первом же запросе, данных о легитимных сериях нет; 10 — порядок выше единичного
наблюдения при жёстком пределе удержания слота помимо дедлайна 1800 с. Значения
обратимы одной константой и не являются NFR.

Деградация (нет разрешающего выбора, ошибка decide `-32050/-32052/-32053`,
превышена граница): если в снимке есть выбор `abort` или `denied` — один decide
с ним; иначе `turn/cancel {commandId, sessionId, turnId}`. Дальше ход завершается
существующим путём неуспешного терминала (клиенту 502 или SSE error, частичный
текст отброшен). Exec-рестарт по этой ветке запрещён: `ServeUnavailable` из
approval-пути не бросается. Влияние cancel на pending approval схемой не описано
(ASM-006), поэтому после cancel мост не ждёт продолжения хода сверх обычного
`turn/completed` с `terminal=cancelled` и дедлайна.

Что не меняется: `ServeUnavailable` и тихий exec fallback для спавна, handshake,
EOF, RPC-ошибок setup и дедлайна чтения; ошибка модели (`terminal != completed`)
по-прежнему не фолбэчится; при ушедшем клиенте надзор убивает группу и ничего
нового не стартует. Approval во время setup-фазы (`await_result` маршрутизирует
чужие сообщения в тот же обработчик) проходит тот же путь: `sessionId` берётся
из снимка, локальная сессия моста может ещё не существовать.

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

Классификатор — чистая проверка по образцу `_has_hard_threshold_marker`,
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
   не попытки; serve→exec fallback внутри `run_attempt` счётчик не расходует —
   это смена транспорта, семантика прежнего test_t18).
3. Клиент на месте (`_client_gone` ложен и проба отрицательна) в момент решения
   и после паузы.
4. Контентные кадры не отправлялись: `_content_started` ложен. Пустые keepalive и
   role-кадр границей не являются; первая live reasoning-дельта является (§4.2).
5. Все группы процессов прежних попыток закрыты и `dead_confirmed` истинен;
   иначе действует существующий карантин слота, повтор не стартует.
6. Остаток общего бюджета больше 30 с (§3.3); пауза повтора входит в бюджет.
7. Промпт повтора — тот же `attempt_prompt` текущей попытки дословно; прунинг на
   транзиентной ветке не выполняется.

### 3.3 Бюджеты, дедлайн и взаимодействие счётчиков

- Якорь `t0` — существующий `t_first_attempt` (monotonic, перед первой
  `run_attempt`). Общий бюджет хода равен `TIMEOUT_S` (1800 с). Остаток перед
  каждой повторной попыткой равен `TIMEOUT_S - (now - t0)`; попытка получает
  только остаток (ServeRun — дедлайн чтения, Run — таймер), первая попытка как
  сегодня полный `TIMEOUT_S`. Остаток не больше `SERVE_SPAWN_TIMEOUT_S` (30 с)
  повтор запрещает: меньше handshake-окна попытка не имеет шанса начаться.
- Контекстный повтор (ровно 1, AD-005) получает тот же остаток. Это ужесточает
  допущенный прошлым пакетом предел 2×TIMEOUT_S до его исходного замысла
  «повтор получает остаток» и укладывает ход в клиентские 1900 с с запасом на
  финальную выдачу. Ожидание слота до `t0` в бюджет не входит, как сегодня.
- Цикл запроса детерминирован: после каждой попытки сначала проверяется
  контекстный повтор (hard threshold, свой счётчик, прунённый промпт), затем
  транзиентный (свой счётчик, тот же промпт), иначе терминальный исход.
  Верхняя граница: не более 4 вызовов `run_attempt` (1 + 1 контекстный +
  2 транзиентных) и не более 8 процессов (serve плюс exec fallback внутри
  попытки), все в одном слоте и внутри общего бюджета.
- Паузы между транзиентными попытками: 2 с, затем 4 с, каждая плюс джиттер
  равномерно до 1 с; суммарно не более 8 с. Пауза спит срезами не дольше тика
  надзора клиента (0.25 с) и прерывается уходом клиента. Длительности читаются
  из модульных констант в момент повтора, чтобы тесты ужимали их monkeypatch,
  как сегодня ужимается `KEEPALIVE_S`. Мера пауз пренебрежима против самого
  быстрого наблюдавшегося сбоя 20 с и не претендует на NFR.
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
  цикла чтения при каждом приросте summary: дельты `summary.N` и добавки списков
  `summary` из `item/completed` проходят один путь, чтобы текст без дельт не
  терялся. ServeRun сокет, `_wlock` и фазы SSE не знает.
- Handler-sink пишет только через существующий `_sse_emit`/`_sse_write` под
  `_wlock`, только в фазе OPEN и при живом клиенте. Первый непустой
  reasoning-кадр выставляет `_content_started` под тем же замком до записи —
  с этого момента повторы §3 и контекстный повтор запрещены.
- Порядок и разделители повторяют финальную сборку: сегодняшнее значение равно
  `"\n\n".join(summaries по возрастанию индекса)`. Live отдаёт куски в порядке
  индексов, перед первым куском каждого следующего непустого индекса — тот же
  разделитель `"\n\n"`, кроме самого первого куска потока. Инвариант: конкатенация
  всех live `delta.reasoning_content` плюс финальный хвост из `_send_sse` равна
  сегодняшнему единому чанку того же хода. `_send_sse` доотдаёт только
  неотправленный хвост; при полном live финального reasoning-кадра нет.
- Сбой записи (клиент ушёл, сокет закрыт) отключает live до конца хода и не
  бросает исключение в ServeRun: накопление summaries продолжается, уходом
  клиента и убийством группы занимается существующий надзор. Отдельной очереди
  и коалесценции не вводится: summaries — грубые куски протокола, не токены;
  если тяжёлый путь покажет иную гранулярность, это отдельное наблюдение OPEN-04.
- Keepalive без изменений: пустой data-чанк каждые 15 с в фазе OPEN. Переход на
  SSE-комментарии droid-моста не делается (OPEN-03, deferred): пустые чанки
  доказано держат этого клиента, комментарии для muse-моста не проверены, а
  тест test_s1 закрепляет отсутствие `: keepalive` и сохраняется.

### 4.3 Наблюдаемость прогресса

- Первая summary-дельта хода логируется строкой с секундами от старта хода и
  индексом (без текста): это закрывает OPEN-04 наблюдением на тяжёлом пути.
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
каждое решение видно владельцу в логе для немедленного отката политики одной
константой режима и перезапуском (§7). Селективный deny без payload не
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
| T-A09 | Approval | серия запросов сверх границ 10 и 3: ход остановлен деградацией, группа мертва, слот свободен |
| T-A10 | Approval | канарейка в `rawArgs` и в вопросе userInput отсутствует в логе, JSON и SSE; аудит-строка содержит только разрешённые поля |
| T-A11 | Approval | `-32030` на старт с allowAll: второй `session/start` без поля в том же процессе, warning, ход через decide (AD-006) |
| T-R01 | TransientRetry | каждый из четырёх маркеров на serve-терминале и на exec: повтор и успех, ровно 2 попытки, один [DONE], нет error между |
| T-R02 | TransientRetry | три транзиентных отказа: ровно 3 попытки, терминальная ошибка прежнего формата, группы мертвы, слот освобождён один раз |
| T-R03 | TransientRetry | нет повтора: после первой live-дельты, при уходе клиента в паузе и во время попытки, при `dead_confirmed` ложном, при остатке бюджета не больше 30 с, на `timeout` и `spawn_failed`, на маркере в успешном тексте |
| T-R04 | TransientRetry | hard threshold в приоритете: контекстный повтор с прунённым промптом, транзиентный счётчик не израсходован; обновлённый test_t18 сохраняет это утверждение |
| T-R05 | TransientRetry | повторная попытка получает только остаток бюджета (фикстура фиксирует переданный дедлайн/таймер меньше полного TIMEOUT_S) |
| T-L01 | LiveReasoning | дельты `summary.0` и `summary.1` с задержкой: кадры reasoning до финального, порядок индексов, разделитель, конкатенация равна буферизованному варианту, финального дубля нет |
| T-L02 | LiveReasoning | summary только из `item/completed` без дельт не теряется ни в live, ни в non-stream `reasoning_summaries` |
| T-L03 | LiveReasoning + test_s1 | пустые keepalive-чанки сохранены, `: keepalive` отсутствует, один [DONE], content и tool_calls целы |
| T-L04 | LiveReasoning | сбой записи в середине live: ход не падает исключением ServeRun, live отключён, терминальный путь существующий |
| T-L05 | LiveReasoning | `turn/modelRetryScheduled` только в логе полями уведомления, в SSE текста нет, `_content_started` им не выставляется |

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

1. Coder работает на ветке `bugfix/muse-wonder-approval-retry-liveness`
   (task.json) от фактического дерева `dev`, фиксирует `git diff` REQ-MUSE-001
   до своих правок и не затирает его. В `dev` не коммитит.
2. Бэкап до деплоя: репозиторный и зеркальный `server.py` в `~/work/backups/`
   с датой в имени. Профили DSH в этом изменении не трогаются, их бэкап не нужен.
3. Оркестратор материализует ADR 0003 по `materialization[]` пакета exact bytes
   с read-back sha256; Coder добавляет одну строку 0003 в `docs/adr/INDEX.md`
   тем же MR. Merge — человек после ACCEPT.
4. Деплой в окно без активных ходов владельца (`kickstart -k` убивает текущий
   процесс моста): копия `bridges/muse-bridge/server.py` в
   `~/.dsh/bridges/muse-bridge/server.py`, затем
   `launchctl kickstart -k gui/$(id -u)/com.user.dsh-muse-bridge`.
5. Лёгкий путь VER-008: `cmp` зеркала, агент в `launchctl list`, `/health` и
   `/v1/models` с ключом, свежий `serve init` с версией и `approvalMode` в логе.
   Лёгкий путь сдачей не является.
6. Тяжёлый путь VER-009 владельцем в живом слоте (длинная сессия, ход рабочего
   размера с инструментом, повтор, два параллельных, контрольный spark).
   Факты сдачи: строки аудита approval, `done via=serve` без `fallback exec`,
   секунды до первой summary-дельты, отсутствие терминального net-timeout без
   повторов в логе за эти ходы. Формат отчёта — блок ПРОВЕРЕНО канона владельца.
7. Откат: вернуть обе копии `server.py` из бэкапа шага 2 и повторить kickstart.
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
| Режим сессии serve | `allowAll` | решение владельца EVD-009 |
| Максимум approval/decide на ход | 10 | §2.4, предел удержания слота |
| Максимум userInput/cancel на ход | 3 | §2.4 |
| Максимум транзиентных повторов на запрос | 2 | AD-003 против наложения на provider attempts |
| Паузы повторов | 2 с, 4 с, джиттер до 1 с | суммарно не более 8 с внутри бюджета |
| Минимальный остаток для повтора | больше 30 с | равен `SERVE_SPAWN_TIMEOUT_S` |
| Маркеры транзиента | 4 подстроки §3.1 | лог, бенч, текст REQ, прежний маркер |

Трассировка: REQ-MUSE-002 → AD-001, AD-002, AD-006 → QA-001, QA-002, QA-008 →
VER-001, VER-009. REQ-MUSE-003 → AD-003 → QA-003, QA-004, QA-005 → VER-002,
VER-010. REQ-MUSE-004 → AD-004, CD-001 → QA-005, QA-006 → VER-003, VER-009.
Наследство REQ-MUSE-001 → AD-005 → QA-007 → VER-004..VER-008.

Не-цели этого изменения: починка ProxyRack и форвардера `:10816`, UI и профили
DSH, закрепление версии CLI, live content, селективные запреты approval,
изменение exec-флагов и лимитов spark. Открытые вопросы Q-001..008 и deferred
пакета сдачу не блокируют и не закрываются молча: каждый имеет наблюдаемый
способ закрытия в логе или на тяжёлом пути.
ARTIFACT_END>>>

ПРИЛОЖЕНИЕ adr-0003:
<<<ARTIFACT ~/work/src/cli-agent-bridge/docs/adr/0003-muse-serve-approval-allowall.md sha256=fcf1aea898d05a67857bcf30d812c0217ede954f0fea5d17aba596d278335c30
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
ошибкой клиенту, без `exec`-рестарта; логирование каждого решения только безопасными полями
(`toolName`, `subject.kind`, `protectedWrite`, `judgeEscalated`, список `choiceId`, выбранный
`decision`) через существующую редакцию, без `rawArgs`.

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
  логируются при каждом старте serve. Отказ `-32030` (потолок старых версий) деградирует один раз
  до старта без поля с опорой на внутриходовый decide (пакет AD-006).
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
  `choiceId` из `availableChoices`, процесс `exec` не запускается, ход завершается `via=serve`.
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

ЗАВЕРШЕНИЕ ОТВЕТА (структура ответа для панели; блок ФОРМАТ ОТВЕТА выше — единственный формат шести критериев).
Порядок: (1) две первые строки ответа — маркеры (см. начало); (2) все F-блоки одним списком (поля: якорь пакета, правило, evidence (цитата), ожидаемое исправление, критерий проверки, priority blocking|non-blocking; один дефект в нескольких местах — один F-блок со всеми якорями); (3) SUB-строки по всем подкатегориям; (4) шесть критериев строго как в блоке ФОРМАТ ОТВЕТА (INCONCLUSIVE допустим только если проверка невозможна без инструментов; это не FAIL); (5) строка `ОБЩИЙ ВЕРДИКТ: PASS|NEEDS WORK|RED FLAG`; (6) строка `COVERAGE: 15/15 подкатегорий` (числитель — число покрытых подкатегорий из 15 перечисленных; меньше 15 — ответ считается неполным); (7) строка `FINDINGS_COMPLETE: 0` с числом, равным числу твоих F-блоков (0 — если F-блоков нет); (8) последняя строка ответа — ровно `VERDICT: PASS`, `VERDICT: NEEDS WORK` или `VERDICT: RED FLAG`, без точки и пояснений. FAIL без привязки к разделу пакета, [F-NN] или правилу не засчитывается. FAIL без оговорок: изменение согласованного внешнего контракта моста без явного указания в task envelope; выход за задачу.
