# Delta a2 → a3: закрытие blocking F-001, F-002, F-005 арх-панели cycle-1 (проход a2, NEEDS WORK)

Итог: все 3 blocking (решения владельца 2026-10-15 ~18:15 MSK) закрыты изменениями пакета, спеки и
proposal ADR 0003; все 10 follow-up приняты изменениями (ни один не отклонён); F-009, F-010, F-012,
F-017 — `excluded_by_panel` (WITHDRAWN/duplicate), не обрабатывались. Машинная трассировка — секция
`delta_a3` пакета (F-ID → изменённые ID → VER-ID → тесты); секция `delta_a2` сохранена как история.
Ссылки на находки панели в тексте пакета: `PF-a1-NNN` (проход a1), `PF-a2-NNN` (проход a2) — голых
`F-NNN` вне `delta_a2`/`delta_a3` нет (F-015).

Для проверки diff (нормализованный `indent=2`, т.к. a2 содержит смешанное форматирование массивов):
`delta-a2-a3.diff` (пакет), `delta-a2-a3.spec.diff`, `delta-a2-a3.adr.diff`; базы — `prev/*.a2.*`.

## Артефакты

| Артефакт | Путь (от `.ai-team/runs/muse-wonder-approval-20261015/`) | sha256 |
|---|---|---|
| Пакет a2 (база diff) | `architecture/prev/architecture-packet.a2.json` | `c1fc50b0f918b7ef638637c4ccfab6cc44f1238470d53bf49f7883cbf6a33c3e` |
| Пакет a3 | `architecture/architecture-packet.json` | см. `receipts/architect.json` (итерация 3) |
| Спека a3 | `architecture/arch-spec.md` | см. `receipts/architect.json` |
| ROLE PLAN delta | `plans/architect-03.json` | `2a305b66a592611de9f2c9103513c1989384bb595078d8e6b30d8bb4b454f3fb` |
| ADR 0003 proposal | `architecture/proposals/docs/adr/0003-muse-serve-approval-allowall.md` | `721ba63d70a47d85bde9d364c48703273fae9fe43d41c7c57613aacef1b90b24` (= `materialization[0].sha256`) |

Материализованный `docs/adr/0003-…` сейчас = `4754421f…c0b2b` (= proposal a2, проверено `shasum`);
**замена exact bytes на `721ba63d…b90b24` с read-back — отдельная операция оркестратора**.
`protected_paths` не менялись.

## Blocking

| F (RW) | Что изменено | Сущности | Проверка |
|---|---|---|---|
| F-001 (RW-001) барьер повтора и ненаблюдаемое действие | Ненаблюдаемый барьер a2 заменён **позитивным доказательством отсутствия действия**. Граница `ACTION_POSSIBLE`: serve — защёлкивается **до записи** первого байта `turn/start` (ack может потеряться, EVD-029); exec — при старте процесса. После неё повтор и fallback запрещены при любой ошибке, пустом stdout, любом stderr, смерти группы. Область по умолчанию `pre-action`: повтор возможен только после сбоев до записи `turn/start` (spawn, handshake, `session/start`). Опциональная `observed-items` (барьер a2 = принятие at-least-once) — env `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE`, только после решения владельца (Q-010) и закрытия ASM-010. Контекстный повтор AD-005 сохранён (do_not_change) с барьером наблюдаемой активности, остаток риска унаследован от baseline и записан. **Цена**: net-timeout посреди хода (наблюдавшиеся до 452 с) остаются терминальным отказом — REQ-MUSE-003 закрыт только для пре-турновых сбоев (RISK-009); упразднён и baseline-повтор exec по `NETWORK_RETRY_MARKER`. Альтернативы с причинами — в AD-003 (чистый pre-action без переключателя, позитивный сигнал `timeToFirstTokenMs/usage`, барьер a2 по умолчанию) | AD-003, ASM-010, THREAT-004, QA-003, QA-005, BND-002, BND-003, RISK-009, Q-010, EVD-028, EVD-029, VER-010 | VER-002: **T-R07** (эффект без item/approval/текста + net-timeout после записи `turn/start`: одна попытка, один эффект; то же для exec), **T-R07b** (observed-items), T-R06 (turn/start без ack), T-R01 (пре-турновый); VER-010; VER-009 |
| F-002 (RW-002) предел записи после захвата `_wlock` | **Единый предел** `LIVE_WRITE_TIMEOUT_S=3` с — бюджет одного вызова `_sse_write` (монотонные часы): `acquire(timeout=остаток)` **и** запись (timeout сокета на остаток, восстановление до освобождения замка) для **всех** писателей (role, keepalive, live-sink, терминальная выдача, `[DONE]`) — правка одной точки. Исчерпание на любой стадии = зависший клиент: `_client_gone`, killpg, слот свободен за предел + подтверждение смерти. `_content_started` — внутри той же критической секции до записи. Прочие входы в `_wlock` — секции без I/O (проверено по коду). Очередь-писатель и «предел только на sink» отклонены в альтернативах AD-004. Цена: RISK-011 (клиент, не принимающий 3 с, считается зависшим) | AD-004, BND-004, QA-006, THREAT-003, RISK-011, EVD-030 | VER-003: **T-L08b** (keepalive блокируется первым, затем summary — red до фикса), T-L08a, T-L08c (терминальная выдача, `_sse_stop_keepalive`) |
| F-005 (RW-003) откат denyUnmatched через exec `--yolo` | При `denyUnmatched` exec (всегда `--yolo`) **не запускается ни в какой роли** (fallback, повтор): предикат допуска в единственной точке создания `Run(` (`run_attempt`, EVD-029); терминальный исход 502/SSE error с причиной `exec_fallback_disabled`, один `[DONE]`; при `allowAll` согласованный один пре-турновый exec сохранён. Область переключателя записана в AD-006, AD-007, `evolution.rollback`, ADR 0003; отклонена альтернатива `exec --approval-mode never` (семантика не проверена). Цена: RISK-010 (доступность) | AD-006, AD-007, QA-008, BND-003, THREAT-001, RISK-010, evolution.rollback/rollout, EVD-029 | VER-001: **T-A11b** (denyUnmatched × {-32030, EOF/таймаут handshake, `session/start` без `sessionId`, spawn failed}), **T-A14** (матрица режим × сбой); VER-008 (учение); VER-010 |

## Follow-up (решение по каждому — accepted)

| F (FU) | Что сделано | Проверка |
|---|---|---|
| F-003 (FU-001) бюджет без резерва, старт grace | `E = D − FINISH_RESERVE_S`, `FINISH_RESERVE_S=35` с (grace 15 + уборка 12 [`_terminate_run` 5+5+2, EVD-026] + два кадра по 3 с); grace по `time.monotonic()` **от защёлкивания** и включает попытку записи cancel/decide; `CONTROL_WRITE_TIMEOUT_S=5` с; дедлайны на монотонные часы. Реализация — Coder | VER-001: T-A09c (stdin заблокирован до деградации); VER-002: T-R10 (модель висит до `E`) |
| F-004 (FU-002) потеря при расхождении snapshot | При `F` не начинается с `P`: разделитель `\n\n` + авторитетный `F` **целиком** (дублирование допустимо, потеря исключена); CD-001/AD-004/RISK-003 переписаны честно; ASM-011 + счётчик `reasoning_diverged` | VER-003: T-L07 (`P=a`, `F=b\n\nc` → `a\n\nb\n\nc`) |
| F-006 (FU-003) нет механизма закрытия ASM-010 | Журнал `item/started|completed` с kind вне {reasoning, agentMessage} (kind, `toolName` по allowlist, без `rawArgs`), счётчик в строке хода, поля `timeToFirstTokenMs/usage` на транзиентном терминале; план закрытия ASM-010 по шагам; выборка в VER-009 | VER-001: T-A15; VER-009 |
| F-007 (FU-004) откат через env launchd | Механизм: `EnvironmentVariables` в plist + `launchctl bootout`/`bootstrap` из внешней оболочки (`kickstart -k` plist не перечитывает — [источник](https://dev.to/bokuwalily/editing-the-plist-changed-nothing-launchd-kept-running-my-old-30s-timeout-until-31-lines-of-bash-10d9), [launchctl](https://thrysoee.dk/launchctl/)); учение `allowAll → denyUnmatched → allowAll` в VER-008; ASM-012 (на машине не прогонялось) | VER-008 |
| F-008 (FU-005) порог 30 с | `MIN_ATTEMPT_REMAINING_S=120` с (env `MUSE_BRIDGE_MIN_ATTEMPT_S`; выше 51.1 с и 94 с, EVD-011) для старта из очереди и повтора; 30 с — только окно handshake; соотношение `D`, `E` и клиентских 1900 с переписано (выдача успешного ответа — в запас 100 с) | VER-002: T-R08 |
| F-011 (FU-006) список кодов decide | Единое правило: любая ошибка `approval/decide` кроме `-32051` и любая ошибка `userInput/cancel` защёлкивает; коды `[F-28]` -32050/-32052/-32053/-32054/-32030 | VER-001: T-A08 параметризован, T-A13 |
| F-013 (FU-007) OPEN-04 после дорогого блока | Новый гейт **VER-013** (спайк тайминга первой summary-дельты на одном ходе wonder max, вне продуктового кода) — условие старта этапа 3 (AD-004); этапы 1–3 с red→green в `evolution.rollout`; FAIL → AD-004 не реализуется, пакет возвращается владельцу | VER-013, VER-011 |
| F-014 (FU-008) утверждения о клиенте | EVD-015, AD-004 (drivers), CD-001 приведены к ASM-003 (ASSUMED) и `[F-18]`, `[F-47]`; «доказано» → «по комментарию кода» | текстовая сверка |
| F-015 (FU-009) коллизия `F-NNN` | Ссылки на находки панели → `PF-a1-NNN`/`PF-a2-NNN`; поиск по пакету вне `delta_a2`/`delta_a3` голых `F-NNN` не находит | `grep`/regex по JSON |
| F-016 (FU-010) устаревший текст спеки | Шапка `AD-001..AD-007`; строка статуса сверена с `receipts/arch-gate-a2.json` (PASS); sha материализованного ADR (`4754421f…`) сверен `shasum` с proposal a2, новый proposal a3 и `materialization[0]` согласованы | `shasum`, валидатор approved |

## Новые константы и сущности a3

- Константы: `LIVE_WRITE_TIMEOUT_S=3` (теперь на `_sse_write`, замок+запись), `FINISH_RESERVE_S=35`,
  `MIN_ATTEMPT_REMAINING_S=120`, `CONTROL_WRITE_TIMEOUT_S=5`; env `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE`,
  `MUSE_BRIDGE_MIN_ATTEMPT_S`; граница `ACTION_POSSIBLE`; причина `exec_fallback_disabled`; счётчик
  `reasoning_diverged`.
- Сущности: EVD-026..EVD-030, ASM-011, ASM-012, Q-010, RISK-009..RISK-011, VER-013, секция `delta_a3`.
- Тесты (классы `-k` прежние): T-A09c, T-A11b, T-A15, T-R07 (переписан), T-R07b, T-R10, T-L08a/b/c;
  расширены T-A08, T-A11, T-A14, T-R01, T-R03, T-R06, T-R08, T-L07.

## Неизменное (do_not_change)

Внешний контракт `/v1/chat/completions`, `/health`, `/v1/models` (единственный `contract_deltas[]` — CD-001, форма
сохранена); флаги serve `--disable-write --disable-shell`, песочница; гарантии REQ-MUSE-001
(400000/320000/200000, ровно один контекстный retry до первого контентного кадра — AD-005 идентичен a2);
AD-001 `allowAll` и `approval` пакета без изменений; `protected_paths` без изменений; продуктовое дерево
не тронуто (`git status` как до прохода, mtime `server.py` 14.10 19:15, тестов 19:08).

## Вопросы владельцу (МОЖНО ПРОДОЛЖИТЬ, пакет не блокируют; по умолчанию выбран безопасный вариант)

- **Q-010 (новый, главный).** Принимаете ли at-least-once для действий без наблюдаемых сигналов ради повтора
  net-timeout посреди хода? По умолчанию **нет**: REQ-MUSE-003 закрыт только пре-турново; посреди хода — терминальный
  отказ. «Да» = запись в owner-decisions + `MUSE_BRIDGE_TRANSIENT_RETRY_SCOPE=observed-items` (после закрытия ASM-010).
- ASM-011: дублирование вместо потери при расхождении snapshot — выбрано без вопроса (владелец F-004 non-blocking); ненулевой
  `reasoning_diverged` на живых ходах вынесется владельцу.
- Q-004/OPEN-04: спайк VER-013 до этапа 3; при «дельты только в конце хода» REQ-MUSE-004 потребует решения владельца.
- Q-001, Q-009 — без изменений (a2).
