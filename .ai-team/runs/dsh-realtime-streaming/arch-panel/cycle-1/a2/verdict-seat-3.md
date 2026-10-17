**Визионер, арх-проход. Пакет REQ-STREAM-001, редакция 2 (DRAFT_VALIDATED после rework a1). Предмет: Architecture Packet, не diff.**

Лёгкая проверка перед вердиктом: SHA-256 architecture-packet.json/md/delta совпали с receipts/architect.json (50c615a4…, 5f575f10…, 618a9323…); целевые тестовые модули VER-001…007 в репозитории существуют. Рантайм не проверялся (NOT_RUN по определению стадии).

## ПРОВЕРКА УСТРАНЕНИЯ ЗАМЕЧАНИЙ СОВЕТА (VERIFY-FIXED, RW-001..RW-011)

- **RW-001 (F-001): FIXED.** architecture-packet.json#EVD-017 фиксирует дословное делегирование владельца (2026-10-13 10:15 MSK) со ссылкой на ledger F-001/F-003; architecture-packet.json#AD-001 задает irreversible partial prefix: отправленные кадры не отзываются, retract/non-prefix complete или failure дают error-чанк и отдельный [DONE] без success finish/usage; architecture-packet.json#approval.delegation_quote, #ASM-002 VALIDATED, #Q-001 resolved=true. Универсальная клиентская совместимость явно не заявлена (architecture-packet.json#AD-001.error_frame.compatibility). Ложного требования повторного согласования нигде нет.
- **RW-002 (F-002): FIXED.** architecture-packet.json#AD-003.process_death_fence: допустимые доказательства fence перечислены (только matching own terminal Run._own_terminal либо фактический reaping), владелец перехода Execution, запрет pkill/lookup reused, join timeout прямо не считается fence; architecture-packet.json#BND-002 (forbidden: reuse lease без terminal/подтвержденной смерти); VER-005/VER-011 задают deterministic barriers (NOT_RUN).
- **RW-003 (F-003): FIXED.** architecture-packet.json#AD-002.parser_contract: strict_live=(stream=True и Droid sink присутствует), mode immutable; malformed/unclosed recognized XML в strict не уходит в legacy fallback, а дает parser error/fail-close; оракул 0 байт recognized XML в live content (architecture-packet.json#QA-002); #ASM-003 VALIDATED, #Q-002 resolved; парные регрессии именованы и помечены NOT_IMPLEMENTED.
- **RW-004 (F-004): FIXED.** architecture-packet.json#AD-001.plumbing: adapter_signature (sse_writer: Optional[StreamSink]=None), facade_chain (_serve_sse → _dispatch → execute_turn), execution_chain (_run_once → _execute; при None прежний buffered flow), pump_callback (tagged own events; RPC не пишет в socket), sink_contract (True = bounded acceptance; False/exception = attempt cancel/fail-close), sink_none. Развилка зафиксирована, а не оставлена Coder.
- **RW-005 (F-005): FIXED.** architecture-packet.json#AD-004.wire_contract: примеры finish- и usage-кадров, finish_reason_usage=null, порядок finish → 0/1 usage → ровно один [DONE], usage только при ненулевом input/output; client_gate это явный оракул VER-007/VER-008 с планом новой Architect delta, если DSH не читает null-usage. Потеря и задвоение завершения исключены формой и порядком.
- **RW-006 (F-006): FIXED.** architecture-packet.json#AD-003.process_death_fence.phases: interrupt 2 s → SIGTERM owned PGID + waitpid(WNOHANG) ≤1 s → SIGKILL + reap ≤1 s; #upper_bound ≤4 s; unconfirmed death → FAIL/quarantine без reuse; L/T отпускаются в finally после detach/quarantine, process capacity retired из admission до подтвержденного reaping, P не возвращается преждевременно. Интервалы продублированы в #QA-003 и #VER-005/009/011.
- **RW-007 (F-007): FIXED.** architecture-packet.json#AD-002.parser_contract.feed/finish/error_reset: отдельный live-контракт, recognized XML не проходит legacy fallback, valid complete call публикуется ровно один раз, reset только на завершении собственного attempt; architecture-packet.json#AD-001.delivery_states: not-accepted → queued → sent|discarded, queued ≠ sent, unsent-cancel до checkpoint дает DIRTY с discard и запретом replay; граница названа консервативным enqueue fence.
- **RW-008 (F-010): FIXED.** architecture-packet.json#AD-003.ownership: facade создает и завершает один request-scoped worker; worker владеет socket, ingress/data queue, coalescing timer и control reserve; parser остается в facade; Run владеет только tagged событиями и accumulator; flush немедленный перед terminal/error/DONE; coalescing-таймер в writer thread, control не ждет остаток timer; VIEW-001/VIEW-002 и BND-001..003 приведены к одному ownership, прежнее противоречие «parser в Run» снято.
- **RW-009 (F-011): FIXED.** architecture-packet.json#AD-003.attempt_outcome: CAS UNDECIDED→READY|DIRTY под per-attempt guard, READY только после durable checkpoint, cancel до checkpoint → DIRTY, cancel внутри guard линеаризуется (успешный checkpoint → READY, иначе DIRTY), persist failure → DIRTY/invalidate, postcommit disconnect = delivery abort без отмены процесса; error-чанк в chat.completion.chunk (architecture-packet.json#AD-001.error_frame), error → [DONE] без success finish/usage; VER-011 барьеры (NOT_RUN).
- **RW-010 (F-012): FIXED.** architecture-packet.json#AD-003.budgeting: единицы (encoded UTF-8 с envelope; frames считаются после coalescing), limits {16 MiB, 1024, 64 KiB, 40 ms, 5 s, 8192 control}, формула B_response без double-count, global (сумма B_response + control) ≤ MAX_DELIVERY_BYTES, control slot вне 1024 frames и вне 16 MiB DATA с global-учетом, ingress mailbox byte-bounded (один frame на токен запрещен), release идемпотентен; VER-005/VER-009 различают fast small chunks и true overflow.
- **RW-011 (F-013): FIXED.** architecture-packet.json#AD-002.parser_contract.interface: strict-live только stream=true; architecture-packet.json#CD-001: nonstream committed-only, legacy finish()/fallback и normalize_prompt_cache_details неизменны; парные регрессии на идентичном входе (nonstream byte-equivalent baseline против strict error) именованы в #AD-002.paired_regressions и #VER-004.
- **FU-001/FU-002: FIXED.** VER-006 добавлен в architecture-packet.json#AD-001.verification_ids, VER-010 в #BND-002; в #VER-001 назван delayed-delta regression и red→green запуск, tool-roundtrip в #QA-005/#VER-008, persist-failure barrier в #VER-011; авторство тестов разделено (Coder пишет, verifier независимо запускает).

## 1. КОРРЕКТНОСТЬ: VERDICT=PASS

SUB КОРРЕКТНОСТЬ/openai-sse-contract: PASS; evidence: architecture-packet.json#AD-004.wire_contract (примеры finish/usage, finish_reason=null у usage, порядок finish, 0/1 usage, ровно один [DONE]), architecture-packet.json#AD-001.error_frame (оболочка chat.completion.chunk, error-объект, error→[DONE], без success finish/usage).
SUB КОРРЕКТНОСТЬ/droid-rpc-streaming: PASS; evidence: architecture-packet.json#AD-001.plumbing.pump_callback и #AD-001.plumbing.identity (tagged incremental события, immutable attempt_id, offsets monotonic, foreign/late quarantined, suffix-only для matching complete).
SUB КОРРЕКТНОСТЬ/lock-release-L-T (RW-009): PASS; evidence: architecture-packet.json#AD-003.upper_bound (normal READY: release L/T после checkpoint, независимо от writer drain), #AD-001.delivery_states.unsent_cancel, #AD-003.attempt_outcome (все исходы ведут к release ровно один раз; cancel после ограниченного fence; unconfirmed death: quarantine + capacity retired из admission).
SUB КОРРЕКТНОСТЬ/tool-parser-no-leak: PASS; evidence: architecture-packet.json#AD-002.parser_contract.feed/finish/error_reset (strict-live только stream=true; recognized XML не уходит в legacy fallback; 0 сырых тегов), #QA-002, #CD-001 (legacy не тронут).

WHY=Контракты заданы проверяемо, а не обещаниями: форма и порядок SSE-кадров зафиксированы примерами; необратимость prefix описана как выбранная fail-close политика с явным клиентским гейтом, а не как заявление совместимости; инвариант RW-009 выполнен и для нормального хода (release после checkpoint), и для отмены (bounded fence). Непроверенное честно помечено NOT_RUN.

## 2. ПОЛНОТА: VERDICT=PASS

SUB ПОЛНОТА/decisions-boundaries-deltas: PASS; evidence: architecture-packet.json#AD-001..#AD-004 (AD-001/002 APPROVED, AD-003/004 PROPOSED с approval_required=false), #BND-001..#BND-003, #CD-001; связность через normative_contract_refs; 17 EVD, 4 ASM, 4 Q, 5 RISK, 3 THREAT на месте.
SUB ПОЛНОТА/verification-surface: PASS; evidence: architecture-packet.json#VER-001..#VER-012: 3 командных repo-гейта, 4 targeted suite, 5 manual live-гейтов; каждый AD/BND/RISK/THREAT/QA имеет verification_ids; test_author и execution_owner разделены; новые тесты помечены NOT_IMPLEMENTED.
SUB ПОЛНОТА/quality-scenarios: PASS; evidence: architecture-packet.json#QA-001..#QA-005 (stimulus, response_measure, verification_ids у каждого); FU-001 и FU-002 внесены.

WHY=Состав пакета полон по собственному реестру сущностей, followups прошлого раунда закрыты. Рантайм-полнота намеренно отложена (NOT_RUN), для стадии DRAFT это корректная позиция, а не пропуск.

## 3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS

SUB РЕАЛИЗУЕМОСТЬ/server-adapter-plumbing: PASS; evidence: architecture-packet.json#AD-001.plumbing (adapter_signature, facade_chain, execution_chain, pump_callback, sink_none), #AD-003.ownership (единственный владелец на компонент), #BND-001..#BND-003. RW-004 закрыт: выбор реализации больше не оставлен Coder.
SUB РЕАЛИЗУЕМОСТЬ/no-new-dependencies: PASS; evidence: architecture-packet.json#evolution.compatibility («No new technology/dependency»), #EVD-013 (stdlib), #CD-001 (ADAPTER_API=1, auth/model/fleet/schema без изменений), #EVD-015 (не изобретать pyproject/uv).

WHY=Цепочка интерфейсов непрерывна, ownership-модель однозначна, контур (writer thread, coalescing, CAS/fence) укладывается в stdlib. Инженерный вес fault-injection барьеров VER-005/VER-011 значителен, но специфицирован, это оцененный объем, а не сюрприз для Coder.

## 4. РИСКИ: VERDICT=PASS

SUB РИСКИ/disconnect-network-error: PASS; evidence: architecture-packet.json#AD-003.attempt_outcome (pre-commit cancel/disconnect: CAS DIRTY без success checkpoint; persist failure: DIRTY/invalidate или in-memory quarantine; postcommit disconnect: только delivery abort; duplicate callbacks идемпотентны), #AD-001.error_frame.framing (error→[DONE] best effort, close по 5 s), #RISK-004, #VER-011 (barriers, NOT_RUN).
SUB РИСКИ/slow-reader-overflow: PASS; evidence: architecture-packet.json#AD-003.budgeting (byte-bounded ingress, frames только после coalescing, 16 MiB / 1024 / 8192 control, global ≤ MAX_DELIVERY_BYTES, идемпотентный release), #QA-003 (4×3 MB slow + 5-й ход и repeat без drain; overflow → cancel с error/DONE либо close), #EVD-009 (RW-009-оракул сохранен), #VER-005/#VER-009.

WHY=Сценарии обрыва и медленного чтения имеют детерминированные исходы без небезопасного reuse; overflow дает явную отмену, а не тихую потерю. Неблокирующее наблюдение: per-response 16 MiB против теоретического максимума encoded-формы (MAX_TURN_TEXT_BYTES 10 MiB при худшем JSON escaping около 2x). Это открытый Q-004/ASM-004; к Coder стоит численно подтвердить, что легитимный максимальный ход не попадает в overflow.

## 5. АЛЬТЕРНАТИВЫ: VERDICT=PASS

SUB АЛЬТЕРНАТИВЫ/streaming-vs-artificial-delay: PASS; evidence: architecture-packet.json#AD-001.alternatives (terminal-buffered и message-complete варианты рассмотрены и отклонены), #AD-003.alternatives (синхронная запись из RPC и unbounded queue отклонены), #AD-004.alternatives (thinking в content и hold reasoning отклонены), #deferred (no fake pacing/token count), #QA-001 (цели не выданы за результаты, timing сохраняется честно).

WHY=Настоящий потоковый стриминг обоснован против всех существенных альтернатив, включая искусственную задержку между накопленными токенами; метрики не подменяются фейковым пейсингом, upstream и bridge замеряются раздельно. Для долгосрочной ценности это правильный выбор: token-live UX и переиспользуемый контур вместо косметической имитации.

## 6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS

SUB СООТВЕТСТВИЕ КОНТЕКСТУ/cached-tokens-no-clamp: PASS; evidence: architecture-packet.json#AD-004.wire_contract.usage_policy (честные значения, cached_tokens > prompt_tokens, нулевые/отсутствующие поля по существующему _wire_usage, clamp запрещен), #VER-007 (envelope-ассерты плюс baseline), #CD-001 и #evolution.compatibility (normalize_prompt_cache_details неизменен).
SUB СООТВЕТСТВИЕ КОНТЕКСТУ/nonstream-no-degradation: PASS; evidence: architecture-packet.json#AD-002.parser_contract.interface (strict live только stream=true), #AD-001.plumbing.sink_none, #CD-001 (nonstream committed-only; _serve_json и legacy finish()/fallback неизменны), #VER-004/#VER-006 (именованные парные регрессии), #EVD-008.

WHY=Телеметрия кэша честная, legacy/nonstream-контур изолирован, решения владельца отражены без ложного требования повторного согласования. Внешняя неточность процесса (не пакета): в handoff-брифе путь do_not_change указан как core/metrics_normalizer.py, такого файла в репозитории нет; символ normalize_prompt_cache_details живет в core/usage_wire.py:15 (импорт server.py:110, вызов :2199). Пакет ссылается только на символ, поэтому это поправка к брифу Coder.

## ОБЩИЙ ВЕРДИКТ: PASS

Все 11 блокирующих замечаний Раунда 1 закрыты на уровне спецификации; новых блокирующих находок нет, новые F-ID не завожу. Условия продолжения остаются процессными: принятие этого раунда советом, approved architecture gate и hash freeze, реализация Coder с red→green, независимый Verifier, затем рантайм-гейты VER-008/009/011/012 (распознавание DSH error-чанка как failure, null-finish usage с cached_tokens без clamp, TTFT и token rate на рабочем слоте, fence/overflow/quarantine).

Визионерская оценка: это изменение действительно меняет игру для моста. Batch переходит в token-live по единственному рабочему пути DSH; bounded-delivery контур с CAS-outcome, fence и quarantine защищает resident multi-chat процесс; nonstream и ADAPTER_API=1 сохраняют обратную совместимость; контур переиспользуем для остальных адаптеров дальше. Альтернативы (буферизация, фейковый пейсинг) отклонены обоснованно, это правильный долгосрочный выбор, а не локальная заплата.

Остаточные неблокирующие: Q-003/ASM-001 (цели TTFT<2 s и 20–80 tok/s не подтверждены замером), Q-004/ASM-004 плюс численный нюанс 16 MiB против worst-case encoding, поправка пути core/usage_wire.py в handoff-брифе.
