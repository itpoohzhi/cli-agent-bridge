1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Три из четырёх проверяемых инвариантов либо зависят от неодобренных решений, либо не доказаны на уровне архитектуры.
   SUB КОРРЕКТНОСТЬ/openai-sse-contract: FAIL [F-001] — AD-001 вводит fail-close при retract/non-prefix complete (error+DONE на уже отправленный prefix), чего нет в реальном контракте OpenAI SSE (OpenAI никогда не отзывает отправленные кадры). Решение прямо названо блокером (ASM-002, Q-001) и ещё не одобрено владельцем — то есть на уровне пакета контракт с OpenAI-клиентами пока не зафиксирован как совместимый (architecture-packet.json#AD-001, #ASM-002, #EVD-008).
   SUB КОРРЕКТНОСТЬ/droid-jsonrpc-pump: PASS — владение turn/mid, offsets и identity-fencing для RPC pump описаны с опорой на код (architecture-packet.json#BND-002, #EVD-001-004).
   SUB КОРРЕКТНОСТЬ/rw009-lock-release-under-race: FAIL [F-002] — для нормального завершения L/T освобождаются до drain (AD-003), но для гонки cancel/disconnect фиксация «own terminal или подтверждённая смерть процесса перед переиспользованием lease» — это ПРЕДЛОЖЕНИЕ поверх известного пробела (EVD-006: «Join сам по себе не доказывает process death»), а не реализованный факт; VER-011 — manual/NOT_RUN (architecture-packet.json#RISK-004, #VER-011, #EVD-006).
   SUB КОРРЕКТНОСТЬ/tool-parser-no-leak: FAIL [F-003] — гарантия «0 тегов в live content» существует только как PROPOSED strict-policy (AD-002), требующая одобрения (ASM-003, Q-002); до одобрения baseline-поведение (malformed/unclosed XML → в текст) сохраняется, то есть защита от утечки сейчас не architecturally locked (architecture-packet.json#AD-002, #ASM-003).
   СОВЕТЫ: получить явное решение владельца по Q-001/Q-002 до перехода в approved; добавить в AD-003 конкретный технический механизм process-death fence (не «предложение», а алгоритм: PID/PGID waitpid + таймаут + поведение при зависшем процессе) и привязать его к VER-011 как blocking, а не NOT_RUN-manual; явно описать в CD-001, как OpenAI-совместимые клиенты (включая сторонние, не только DSH) должны интерпретировать error-on-retract кадр, раз это не часть официального контракта.

2. ПОЛНОТА: VERDICT=PASS
   WHY=Все заявленные решения, границы, контрактные дельты и verification surface присутствуют и структурно полны.
   SUB ПОЛНОТА/decisions-ad: PASS — AD-001..004 присутствуют с question/choice/alternatives/consequences/evidence/verification (architecture-packet.json#AD-001..AD-004).
   SUB ПОЛНОТА/boundaries-bnd: PASS — BND-001..003 с responsibility/allowed/forbidden dependencies (architecture-packet.json#BND-001..BND-003).
   SUB ПОЛНОТА/contract-delta-cd: PASS — CD-001 с producer/consumer/change/compatibility (architecture-packet.json#CD-001).
   SUB ПОЛНОТА/verification-surface: PASS — VER-001..012 покрывают автоматические и ручные гейты (architecture-packet.json#VER-001..VER-012).
   SUB ПОЛНОТА/quality-scenarios: PASS — QA-001..005 покрывают performance/privacy/reliability/compatibility×2 (architecture-packet.json#QA-001..QA-005).

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Отсутствует конкретный план перехода текущего синхронного вызова DroidAdapter к sink-driven потоку; остальная часть (переиспользование seam, отсутствие новых зависимостей) реализуема.
   SUB РЕАЛИЗУЕМОСТЬ/server-py-concurrency: PASS — новая машинерия (bounded queue, single writer, write deadline, coalescing) описана как надстройка над существующим typed sink-seam, а не новый фреймворк (architecture-packet.json#EVD-004, #AD-003).
   SUB РЕАЛИЗУЕМОСТЬ/adapter-plumbing-gap: FAIL [F-004] — EVD-004 прямо фиксирует: «DroidAdapter его пока игнорирует, вызывает _run_once; изменение требует сквозного plumbing». Пакет не даёт технического моста (как _run_once синхронно превращается в incremental callback без поломки nonstream-пути) — это оставлено «Coder узнает по ходу», а не зафиксировано как архитектурное решение, что для S2-критичности и одного мейнтейнера stdlib-бриджа — реальный риск недооценки объёма работ (architecture-packet.json#EVD-004, #AD-001).
   SUB РЕАЛИЗУЕМОСТЬ/no-new-deps: PASS — явно зафиксировано отсутствие новых зависимостей/фреймворков (architecture-packet.json#evolution.compatibility).
   СОВЕТЫ: добавить отдельный AD (или расширить AD-001) с конкретной сигнатурой: как `execute_turn(turn, sink)` будет передавать sink до `_run_once`/`_execute`, кто создаёт/закрывает writer-поток, где именно врезается coalescing-таймер; приложить хотя бы псевдокод интерфейса, а не только словесное намерение; явно зафиксировать, что nonstream-путь физически не трогает эту цепочку (сейчас это утверждается, но не привязано к конкретному guard в коде).

4. РИСКИ: VERDICT=PASS
   WHY=Сетевые обрывы, медленный клиент и переполнение очереди разобраны с конкретными мерами и verification-гейтами.
   SUB РИСКИ/network-disconnect: PASS — RISK-004 и AD-003 описывают атомарный исход, immutable attempt id, fence перед lease reuse, VER-011 как ручной гейт на повторяемую гонку (architecture-packet.json#RISK-004, #VER-011).
   SUB РИСКИ/slow-client-queue-overflow: PASS — AD-003 задаёт конкретные (пусть и предложенные) лимиты 16MiB/1024 frames/64KiB/5s deadline/40ms coalescing, поведение при overflow (cancel+interrupt+DIRTY+release), VER-009 — тест на 4 медленных читателя + 5-й ход + повтор key (architecture-packet.json#AD-003, #RISK-003, #VER-009).

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Альтернатива «искусственная задержка между накопленными токенами» явно названа и отвергнута по соображениям честности метрик, а не просто опущена.
   SUB АЛЬТЕРНАТИВЫ/streaming-vs-fake-pacing: PASS — AD-001 среди альтернатив прямо называет «оставить terminal-buffered SSE и исправить только метрику» и отвергает её; RISK-005 отдельно фиксирует запрет «fake pacing or fabricated target achievement»; QA-001 требует «No invented results» (architecture-packet.json#AD-001, #RISK-005, #QA-001).

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=cached_tokens сохраняются без clamp, non-stream путь явно не деградирует.
   SUB СООТВЕТСТВИЕ/cached-tokens-no-clamp: PASS — AD-004 сохраняет «baseline single optional usage(_wire_usage incl cached_tokens)»; VER-007 проверяет это против EVD-011 без изменения политики нулевых/отсутствующих полей (architecture-packet.json#AD-004, #VER-007, #EVD-011).
   SUB СООТВЕТСТВИЕ/nonstream-no-degradation: PASS — «Nonstream остаётся committed-only» (AD-001), «None sink/nonstream… keep buffered finalize_turn» (evolution.compatibility), VER-001/VER-006 держат nonstream-регрессии неизменными (architecture-packet.json#AD-001, #evolution.compatibility, #VER-006).

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

Обоснование общего вердикта: это добротный, честный draft — архитектор сам вскрывает главные компромиссы (ASM-002/ASM-003, RISK-001..005) и ничего не прячет, альтернативы и контекстные ограничения проработаны сильно. Но два блока пока не тянут на «архитектура готова к реализации»: (1) сам факт корректности нового SSE-поведения висит на двух неодобренных владельцем решениях (Q-001/Q-002) — без них Coder не может стартовать по AD-002/часть AD-001; (2) мост от сегодняшнего синхронного `_run_once` к sink-driven потоку в `droid_adapter.py` обозначен как «требуется plumbing», но не спроектирован — это крупнейший источник недооценки сложности и RED FLAG-кандидат, если его не закрыть до approved-фазы. Не RED FLAG целиком, потому что ни один из пробелов не скрыт и не выдаётся за решённый — но для перехода в approved нужны: owner-решения по Q-001/Q-002 и конкретизация AD-001/EVD-004 моста до уровня интерфейса.
