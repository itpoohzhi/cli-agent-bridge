# Проверка устранения замечаний Совета (VERIFY-FIXED RW-001..RW-011)

| RW | Статус | Комментарий |
|---|---|---|
| RW-001 (F-001) | **ИСПРАВЛЕНО** | Делегирование владельца зафиксировано дословно (EVD-017), AD-001 APPROVED с явным выбором irreversible partial prefix + fail-close, ASM-002/Q-001 согласованы. |
| RW-002/RW-006 (F-002/F-006) | **ЧАСТИЧНО** | Числовой fence (2+1+1 с) задан (AD-003.process_death_fence), но `upper_bound` конфликтует с `cancel_linearization` (см. F-102 ниже) — реального верхнего предела 4 с нет для случая гонки с checkpoint. |
| RW-003/RW-007/RW-011 (F-003/F-007/F-013) | **ИСПРАВЛЕНО** | strict_live строго по `stream is True and sink is not None`, парные regression-тесты названы, legacy nonstream fallback явно неизменен. |
| RW-004 (F-004) | **ЧАСТИЧНО** | Сигнатуры/цепочка вызовов расписаны (AD-001.plumbing), но бюджет промежуточной очереди Run.q не закрыт (см. F-103). |
| RW-005 (F-005) | **ИСПРАВЛЕНО** | Конкретные wire-примеры finish/usage/DONE (AD-004.wire_contract). |
| RW-008 (F-010) | **ЧАСТИЧНО** | Единственный владелец на компонент задан (AD-003.ownership, VIEW-001/002), но не закрыта блокировка lock-contention между producer admission и writer.send() (см. F-106). |
| RW-009 (F-011) | **ИСПРАВЛЕНО** | Атомарный CAS state machine (attempt_outcome) и OpenAI-совместимый error envelope (error_frame) заданы. |
| RW-010 (F-012) | **ЧАСТИЧНО** | Байтовый/фреймовый бюджет и control slot заданы (AD-003.budgeting), но нет глобального потолка на параллельные accumulator-буферы (см. F-104) и Run.q (см. F-103). |

---

## 1. КОРРЕКТНОСТЬ: VERDICT=FAIL

SUB КОРРЕКТНОСТЬ/openai-sse-contract (RW-005,RW-009 verify-fixed): PASS — конкретные finish/usage/error JSON-примеры присутствуют (architecture-packet.json#AD-004, #AD-001).

SUB КОРРЕКТНОСТЬ/tool-parser-no-leak (RW-003/007/011 verify-fixed): PASS — strict_live изоляция по stream=true, парные тесты (architecture-packet.json#AD-002).

SUB КОРРЕКТНОСТЬ/attempt-key-quarantine-vs-tool-continuation: **FAIL [F-101]** — `process_death_fence.unconfirmed_at_deadline` квалифицирует quarantine не только по attempt, но и по **ключу** («quarantine owned process/attempt/key, запрет дальнейших RPC и reuse», architecture-packet.json#AD-003.process_death_fence). Это прямо противоречит QA-005/VER-008 требованию «same established key, distinct attempt» для role=tool continuation и RW-009-оракулу «повтор key проходит после checkpoint». Спецификация не описывает ни recovery-процедуру снятия quarantine, ни отличие «quarantine key до recovery» от «quarantine key навсегда».

SUB КОРРЕКТНОСТЬ/cancellation-fence-upper-bound-contradiction: **FAIL [F-102]** — `process_death_fence.upper_bound` заявляет «Fence escalation ≤4 s monotonic... normal READY release после checkpoint независимо от writer», но `attempt_outcome.cancel_linearization` говорит: «Cancel во время checkpoint сериализуется: если checkpoint успешен, READY побеждает» — т.е. cancel ждёт завершения checkpoint, а checkpoint (fsync) прямо помечен как неограниченный по времени («гарантировать finite disk fsync по процессному дедлайну нельзя», architecture-packet.json#AD-003.process_death_fence.upper_bound). Значит заявленные 4 с — верхняя граница только для ветки без гонки с checkpoint; для гонки с медленным diskwrite верхней границы фактически нет, а текст это не разграничивает явно.

**СОВЕТЫ (при FAIL):**
- Явно описать recovery/un-quarantine процедуру для ключа после unconfirmed death (таймаут, ручной supervisor-reset, новый attempt_id с принудительным re-fence) и согласовать её с QA-005/RW-009.
- Либо разделить quarantine уровня process/attempt (временный) и уровня key (постоянный до явного вмешательства), либо отказаться от блокировки key целиком.
- Переформулировать `upper_bound`: явно указать, что 4 с гарантируются только для ветки «cancel до входа в checkpoint critical section»; для гонки с in-flight checkpoint — отдельный (возможно неограниченный) путь, и это должно быть видно читателю без вывода по контексту.

## 2. ПОЛНОТА: VERDICT=FAIL

SUB ПОЛНОТА/decisions-boundaries-contract: PASS — AD-001..004, BND-001..003, CD-001, VER-001..012 присутствуют.

SUB ПОЛНОТА/queue-topology-completeness: **FAIL [F-103]** — AD-003.budgeting бюджетирует только мейлбокс/очередь request-scoped worker'a. Промежуточная очередь `Run.q`, через которую RPC pump публикует tagged incremental events до façade-consumer (architecture-packet.json#AD-001.plumbing, pump_callback), нигде не включена в формулу `B_response` и не имеет явного bound/owner в BND-001/BND-002. Это отдельный, неучтённый путь накопления памяти при всплеске upstream-дельт до того, как façade успеет их вычитать.

SUB ПОЛНОТА/global-accumulator-cap: **FAIL [F-104]** — для delivery есть явный глобальный пул (`MAX_DELIVERY_BYTES`, 256 MiB, architecture-packet.json#AD-003.budgeting.global), а для accumulator/reasoning/tool XML буферов («other_budgets», MAX_TURN_TEXT_BYTES 10 MiB) указан только per-turn предел — глобального потолка на сумму по всем параллельным live-ходам нет.

**СОВЕТЫ (при FAIL):**
- Включить Run.q в нормативный budgeting-раздел: владелец, единицы учёта, верхняя граница, политика backpressure/drop.
- Добавить глобальный агрегированный предел для accumulator-буферов аналогично MAX_DELIVERY_BYTES, с admission-проверкой при создании нового live-attempt.

## 3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL

SUB РЕАЛИЗУЕМОСТЬ/adapter-plumbing (RW-004 verify-fixed): PASS-с-оговоркой — сигнатуры/цепочка вызовов достаточно детальны для Coder (architecture-packet.json#AD-001.plumbing), оговорка — см. F-103.

SUB РЕАЛИЗУЕМОСТЬ/ownership-threads (RW-008 verify-fixed): **FAIL [F-106]** — `ownership`/`flush` заявляют «RPC sink enqueue-only, никогда не ждёт socket» и «Producers имеют только nonblocking admission API» (architecture-packet.json#AD-003.ownership), но архитектура не запрещает явно общий lock между admission-путём и веткой writer, выполняющей фактический (потенциально блокирующий до 5 с) `socket.send()`. Если Coder реализует это одним mutex'ом вокруг очереди (естественный первый вариант в stdlib-threading коде), promise «RPC никогда не блокируется» будет молча нарушен лок-контеншном, а verification surface (VER-005/009) это явно не проверяет.

SUB РЕАЛИЗУЕМОСТЬ/no-new-deps: PASS — stdlib-only, соответствует EVD-013/README.

**СОВЕТЫ (при FAIL):**
- Добавить явное архитектурное требование: lock, защищающий admission/enqueue, не должен удерживаться во время блокирующего `socket.send()`; writer обязан снять lock очереди перед системным вызовом записи.
- Включить в VER-005 сценарий: producer admission не замедляется во время активной медленной отправки (измерение задержки enqueue во время send()).
- Закрыть Run.q-бюджет (F-103) до передачи Coder, иначе RW-004 закрыт лишь частично.

## 4. РИСКИ: VERDICT=FAIL

SUB РИСКИ/network-disconnect: PASS-с-оговоркой — 5s write deadline, best-effort error/DONE, postcommit disconnect = delivery-only (architecture-packet.json#AD-003.ownership.flush, #RISK-004).

SUB РИСКИ/quarantine-dos: **FAIL [F-101]** (см. выше) — severity high: одна неоднозначная гонка disconnect/process-death превращает established-чат в постоянно недоступный без описанного восстановления — это самостоятельный DoS-вектор поверх уже перечисленных RISK-001..005.

SUB РИСКИ/slow-reader-and-accumulator-budget: **FAIL [F-103/F-104]** — неучтённые Run.q и глобальный accumulator-потолок означают, что заявленное «global≤MAX_DELIVERY_BYTES» и «0 leaked reservations» (QA-003) не покрывают весь путь памяти турна.

**СОВЕТЫ (при FAIL):** см. советы к F-101, F-103, F-104 выше; дополнительно добавить RISK-00X в risk-реестр архитектуры на quarantine-DoS явно (сейчас он отсутствует как отдельный риск, хотя логически вытекает из AD-003).

## 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS

WHY: AD-001/AD-003/AD-004 содержат по 2 явные отклонённые альтернативы с причиной отклонения (buffered-only, synchronous socket write, unbounded queue, text-in-content thinking), обоснованные REQ-STREAM-001 и EVD-016 (owner-запрошенный live SSE). Выбор потокового стриминга вместо задержки между накопленными токенами обоснован реальным требованием token-live, а не произволен.

## 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL

SUB СООТВЕТСТВИЕ/cached-tokens-no-clamp: PASS — `usage_policy` явно: «cached_tokens может быть >prompt_tokens: не clamp» (architecture-packet.json#AD-004).

SUB СООТВЕТСТВИЕ/nonstream-no-degradation (RW-011 verify-fixed): PASS — mode isolation + парные regression-имена, `do_not_change` соблюдён.

SUB СООТВЕТСТВИЕ/established-key-continuation-contract: **FAIL [F-101]** (повторная проекция того же корневого дефекта) — контракт «тот же established key, новый attempt» из QA-005/rollout нарушается описанным quarantine-поведением key в AD-003, что является несоответствием задаче REQ-STREAM-001 (сохранить рабочий слот живым для продолжения хода).

**СОВЕТЫ (при FAIL):** то же, что F-101 — развести quarantine процесса/attempt от quarantine key, либо явно задать условия и срок снятия блокировки key.

---

## ОБЩИЙ ВЕРДИКТ: NEEDS WORK

Старые 11 blocking-замечаний (RW-001..RW-011) в основном закрыты на уровне спецификации; расхождение видно только по трём (RW-002/006, RW-004, RW-008/010) — там фиксы частичны. Дополнительно найдены новые конкретные дефекты, не покрытые Round-1 находками:
- **F-101** (high) — quarantine ключа при unconfirmed death блокирует established-чат без recovery-процедуры, конфликтует с QA-005/RW-009.
- **F-102** (medium-high) — заявленный upper bound 4 с для cancellation fence не выполняется в гонке с in-flight checkpoint.
- **F-103** (medium) — промежуточная очередь Run.q не включена в budgeting.
- **F-104** (medium) — нет глобального потолка на параллельные accumulator-буферы.
- **F-106** (medium) — не исключена возможность lock-contention, нарушающего «RPC никогда не блокируется на socket».

Это специфичные, устранимые пробелы спецификации, а не признак неверного архитектурного направления — поэтому RED FLAG не ставлю, но для прохождения повторного совета пакету нужна ещё одна правка, закрывающая F-101..F-104 и F-106.
