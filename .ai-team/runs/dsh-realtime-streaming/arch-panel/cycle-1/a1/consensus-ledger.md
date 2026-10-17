# CONSENSUS LEDGER — ARCH PANEL CYCLE 1 A1
Round: R1
Consensus status: NEEDS WORK (Majority 2/3: Visionary [Anthropic], Skeptic [xAI])

### F-001
- origin: visionary · R1 · visionary-01
- rev: 1
- priority: blocking
- status: OWNER_DECIDED
- outcome: blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR skeptic=AGREE realist=AGREE
- dissent: —
- owner_decision: 2026-10-13 10:15 MSK "1 кажется да. главное что бы было по архитектуре. пусть архитектор говорит как делать."
- amendments: —
- text (дословно, R1 visionary):
> SUB КОРРЕКТНОСТЬ/openai-sse-contract: FAIL [F-001] — AD-001 вводит fail-close при retract/non-prefix complete (error+DONE на уже отправленный prefix), чего нет в реальном контракте OpenAI SSE (OpenAI никогда не отзывает отправленные кадры). Решение прямо названо блокером (ASM-002, Q-001) и ещё не одобрено владельцем — то есть на уровне пакета контракт с OpenAI-клиентами пока не зафиксирован как совместимый (architecture-packet.json#AD-001, #ASM-002, #EVD-008).

### F-002
- origin: visionary · R1 · visionary-02
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR skeptic=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> SUB КОРРЕКТНОСТЬ/rw009-lock-release-under-race: FAIL [F-002] — для нормального завершения L/T освобождаются до drain (AD-003), но для гонки cancel/disconnect фиксация «own terminal или подтверждённая смерть процесса перед переиспользованием lease» — это ПРЕДЛОЖЕНИЕ поверх известного пробела (EVD-006: «Join сам по себе не доказывает process death»), а не реализованный факт; VER-011 — manual/NOT_RUN (architecture-packet.json#RISK-004, #VER-011, #EVD-006).

### F-003
- origin: visionary · R1 · visionary-03
- rev: 1
- priority: blocking
- status: OWNER_DECIDED
- outcome: blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR skeptic=AGREE realist=AGREE
- dissent: —
- owner_decision: 2026-10-13 10:15 MSK "1 кажется да. главное что бы было по архитектуре. пусть архитектор говорит как делать."
- amendments: —
- text (дословно, R1 visionary):
> SUB КОРРЕКТНОСТЬ/tool-parser-no-leak: FAIL [F-003] — гарантия «0 тегов в live content» существует только как PROPOSED strict-policy (AD-002), требующая одобрения (ASM-003, Q-002); до одобрения baseline-поведение (malformed/unclosed XML → в текст) сохраняется, то есть защита от утечки сейчас не architecturally locked (architecture-packet.json#AD-002, #ASM-003).

### F-004
- origin: visionary · R1 · visionary-04
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 visionary=AUTHOR skeptic=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 visionary):
> SUB РЕАЛИЗУЕМОСТЬ/adapter-plumbing-gap: FAIL [F-004] — EVD-004 прямо фиксирует: «DroidAdapter его пока игнорирует, вызывает _run_once; изменение требует сквозного plumbing». Пакет не даёт технического моста (как _run_once синхронно превращается в incremental callback без поломки nonstream-пути) — это оставлено «Coder узнает по ходу», а не зафиксировано как архитектурное решение, что для S2-критичности и одного мейнтейнера stdlib-бриджа — реальный риск недооценки объёма работ (architecture-packet.json#EVD-004, #AD-001).

### F-005
- origin: skeptic · R1 · skeptic-01
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB КОРРЕКТНОСТЬ/OpenAI SSE и Droid JSON-RPC streaming: FAIL — architecture-packet.json#AD-004, architecture-packet.json#CD-001. F-001: успех описан как один finish_reason, затем отдельный optional usage, затем DONE. Сейчас usage едет во втором чанке, у которого finish_reason повторяется (server.py около _serve_sse). Пакет не говорит, какой finish_reason у usage-чанка. DSH читает usage из stream-chunk; пустой finish_reason: null на usage-чанке может потерять usage, повтор stop может задвоить завершение. Это ломает единственный путь, которым клиент получает cached_tokens.

### F-006
- origin: skeptic · R1 · skeptic-02
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB КОРРЕКТНОСТЬ/Освобождение L и T (RW-009): FAIL — architecture-packet.json#AD-003, architecture-packet.json#EVD-006. F-002: «release сразу после хода» и «checkpoint+L/T release before writer drain» несовместимы с fence. При precommit cancel L/T держатся до own terminal или waitpid. Если terminal не приходит, а waitpid не ограничен, аренда чата и слот вычисления не возвращаются, и RW-009 (5-й ход после 4 медленных) не выполняется. Дедлайна fence в пакете нет.

### F-007
- origin: skeptic · R1 · skeptic-03
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB КОРРЕКТНОСТЬ/ToolCallParser без утечки тегов: FAIL — architecture-packet.json#AD-002, architecture-packet.json#EVD-005. F-003: strict-live («malformed/unclosed recognized XML → error, 0 байт XML в content») нельзя получить переиспользованием текущего ToolCallParser без смены контракта. Сейчас незакрытый блок на finish() и невалидный блок отдаются в content (_flush_all, _emit(OPEN+inner+CLOSE)). Отдельного live-режима у парсера нет. Плюс «accepted queue payload = видимость» делает необратимым кадр, который клиент ещё не получил: cancel до send уже запрещает retry и оставляет DIRTY.

### F-008
- origin: skeptic · R1 · skeptic-04
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB ПОЛНОТА/Решения, границы, контракт: FAIL — architecture-packet.json#AD-001, architecture-packet.json#BND-002. F-004: AD-001 верифицируется только VER-008 и VER-012 (живой слот и тайминг). Retract, non-prefix complete, suffix-only complete и запрет повтора accumulator проверяет VER-006, но AD-001 на него не ссылается. Граница BND-002 запрещает retry after prefix и lease reuse без fence, а её verification_ids не включают VER-010, хотя без решения владельца эти проверки нельзя менять.

### F-009
- origin: skeptic · R1 · skeptic-05
- rev: 1
- priority: non-blocking
- status: AGREED
- outcome: non-blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB ПОЛНОТА/Verification и quality: FAIL — architecture-packet.json#VER-001, architecture-packet.json#QA-005. F-005: VER-001 требует red→green delayed-delta, но команда — весь unittest discover, без имени нового теста. VER-004 говорит «verifier добавляет» тесты, хотя пакет сам пишет, что тесты пишет Coder. F-006: в QA нет сценария tool-roundtrip. После live tool_calls клиент присылает role=tool, а CD-001 говорит «tools не исполняются, автоматического replay нет». Кто исполняет инструмент и как следующий ход склеивается с необратимым prefix, не задано. F-007: persist failure после prefix назван в тексте, но ни один VER не строит этот барьер, хотя VER-011 его упоминает в expected.

### F-010
- origin: skeptic · R1 · skeptic-06
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB РЕАЛИЗУЕМОСТЬ/server.py и droid_adapter.py: FAIL — architecture-packet.json#VIEW-001, architecture-packet.json#AD-003. F-008: component view рисует parser внутри Run (R --> P), sequence рисует P -> W напрямую, BND-002 говорит «ToolCallParser in facade», а BND-003 запрещает парсеру socket/RPC. Три владельца одного компонента. Writer описан и как очередь, и как поток сокета, и как участник sequence, который шлёт failure в Execution. Кто создаёт поток, кто его останавливает и кто владеет reserved control slot, не названо. F-009: coalesce ≤40 мс требует таймера, а sink обязан быть nonblocking. Кто коалесцирует (RPC-поток, writer, третий таймер) и что происходит с последним чанком короче 40 мс перед terminal, не задано. Иначе последний токен задерживается, либо таймер блокирует RPC.

### F-011
- origin: skeptic · R1 · skeptic-07
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB РИСКИ/Обрыв соединения: FAIL — architecture-packet.json#RISK-004, architecture-packet.json#AD-001. F-010: post-commit disconnect «только delivery abort» не определён, если disconnect приходит в окне между own terminal и durable checkpoint. Два исхода (READY+release и DIRTY+fence) могут примениться к одному attempt id. Writer при этом уже мог принять prefix. Итог: либо success finish на незакоммиченном ходе, либо DIRTY после частичного READY. F-011: error-кадр пакета («standard error frame») не совпадает с текущим {"error": err} без OpenAI chunk-обёртки. Клиент, который ждёт chat.completion.chunk, не увидит ошибку и будет ждать finish.

### F-012
- origin: skeptic · R1 · skeptic-08
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB РИСКИ/Медленный клиент и очередь: FAIL — architecture-packet.json#AD-003, architecture-packet.json#QA-003. F-012: лимит 1024 кадра при coalesce 40 мс не защищает быстрый upstream. Пока writer спит на coalesce, RPC продолжает enqueue. Overflow отменяет ход, который клиент читает нормально, только чанки мелкие. 16 МиБ на ответ при глобальных 256 МиБ и нескольких чатах с thinking+tool XML упирается в глобальный резерв раньше, чем в очередь, и тоже отменяет ход. Reserved control slot не описан как неучитываемый в 1024, поэтому error/DONE могут не влезть после discard.

### F-013
- origin: skeptic · R1 · skeptic-09
- rev: 1
- priority: blocking
- status: AGREED
- outcome: blocking
- resolved_in: r1
- votes: R1 skeptic=AUTHOR visionary=AGREE realist=AGREE
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 skeptic):
> SUB СООТВЕТСТВИЕ КОНТЕКСТУ/Non-streaming без деградации: FAIL — architecture-packet.json#AD-002, architecture-packet.json#CD-001. F-013: nonstream обещан committed-only и со старым XML fallback. Тот же ToolCallParser предлагается переиспользовать для strict-live. Если strict попадёт в общий finish(), nonstream начнёт отдавать error вместо текста на malformed XML. Пакет не фиксирует развилку по режиму и не даёт теста, что nonstream fallback не изменился. Это и есть деградация, которую критерий запрещает.
