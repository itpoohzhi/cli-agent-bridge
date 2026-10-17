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
