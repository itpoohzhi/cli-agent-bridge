# CONSENSUS LEDGER — ARCH PANEL CYCLE 1 A2
Round: R1
Consensus status: PASS (Majority 2/3: Realist [Zhipu], Visionary [DeepSeek])

### F-101
- origin: skeptic · R1 · skeptic-01
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=DISPUTE visionary=DISPUTE
- dissent: skeptic r1 "quarantine owned process/attempt/key при unconfirmed death блокирует established key без recovery-процедуры"
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB КОРРЕКТНОСТЬ/attempt-key-quarantine-vs-tool-continuation: FAIL [F-101] — process_death_fence.unconfirmed_at_deadline квалифицирует quarantine не только по attempt, но и по ключу («quarantine owned process/attempt/key, запрет дальнейших RPC и reuse», architecture-packet.json#AD-003.process_death_fence). Это прямо противоречит QA-005/VER-008 требованию «same established key, distinct attempt» для role=tool continuation и RW-009-оракулу «повтор key проходит после checkpoint». Спецификация не описывает ни recovery-процедуру снятия quarantine, ни отличие «quarantine key до recovery» от «quarantine key навсегда».

### F-102
- origin: skeptic · R1 · skeptic-02
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=DISPUTE visionary=DISPUTE
- dissent: skeptic r1 "upper bound 4 с конфликтует с cancel_linearization во время checkpoint fsync"
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB КОРРЕКТНОСТЬ/cancellation-fence-upper-bound-contradiction: FAIL [F-102] — process_death_fence.upper_bound заявляет «Fence escalation ≤4 s monotonic... normal READY release после checkpoint независимо от writer», но attempt_outcome.cancel_linearization говорит: «Cancel во время checkpoint сериализуется: если checkpoint успешен, READY побеждает» — т.е. cancel ждёт завершения checkpoint, а checkpoint (fsync) прямо помечен как неограниченный по времени («гарантировать finite disk fsync по процессному дедлайну нельзя», architecture-packet.json#AD-003.process_death_fence.upper_bound). Значит заявленные 4 с — верхняя граница только для ветки без гонки с checkpoint; для гонки с медленным diskwrite верхней границы фактически нет, а текст это не разграничивает явно.

### F-103
- origin: skeptic · R1 · skeptic-03
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=DISPUTE visionary=DISPUTE
- dissent: skeptic r1 "Run.q между pump и facade не включена в формулу B_response"
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB ПОЛНОТА/queue-topology-completeness: FAIL [F-103] — AD-003.budgeting бюджетирует только мейлбокс/очередь request-scoped worker'a. Промежуточная очередь Run.q, через которую RPC pump публикует tagged incremental events до façade-consumer (architecture-packet.json#AD-001.plumbing, pump_callback), нигде не включена в формулу B_response и не имеет явного bound/owner в BND-001/BND-002. Это отдельный, неучтённый путь накопления памяти при всплеске upstream-дельт до того, как façade успеет их вычитать.

### F-104
- origin: skeptic · R1 · skeptic-04
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=DISPUTE visionary=DISPUTE
- dissent: skeptic r1 "нет глобального агрегированного потолка на параллельные accumulator-буферы"
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB ПОЛНОТА/global-accumulator-cap: FAIL [F-104] — для delivery есть явный глобальный пул (MAX_DELIVERY_BYTES, 256 MiB, architecture-packet.json#AD-003.budgeting.global), а для accumulator/reasoning/tool XML буферов («other_budgets», MAX_TURN_TEXT_BYTES 10 MiB) указан только per-turn предел — глобального потолка на сумму по всем параллельным live-ходам нет.

### F-106
- origin: skeptic · R1 · skeptic-05
- rev: 1
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR realist=DISPUTE visionary=DISPUTE
- dissent: skeptic r1 "не исключён lock contention между producer admission и socket.send"
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB РЕАЛИЗУЕМОСТЬ/ownership-threads (RW-008 verify-fixed): FAIL [F-106] — ownership/flush заявляют «RPC sink enqueue-only, никогда не ждёт socket» и «Producers имеют только nonblocking admission API» (architecture-packet.json#AD-003.ownership), но архитектура не запрещает явно общий lock между admission-путём и веткой writer, выполняющей фактический (потенциально блокирующий до 5 с) socket.send(). Если Coder реализует это одним mutex'ом вокруг очереди (естественный первый вариант в stdlib-threading коде), promise «RPC никогда не блокируется» будет молча нарушен лок-контеншном, а verification surface (VER-005/009) это явно не проверяет.
