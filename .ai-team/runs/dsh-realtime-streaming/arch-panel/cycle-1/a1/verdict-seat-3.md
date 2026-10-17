SEED_RECHECK: PASS
Пересчёт по `~/Мой диск/Context/models.md` п. 1.1–1.2 и 1.5: `SHA-256("45ad8ef8#dsh-realtime-streaming#c1#R1")[:8] = 2db18b15`. Якорь: `SHA-256(SEED+"#anchor#"+slot)` — `claude-sonnet-5-5` (`cf267dbd…`) меньше `gpt-6.1-sol` (`d0515f83…`). Ранг `SHA-256(SEED+"#"+slot)` возрастает ровно как заявлено: muse-spark-1.3, grok-4.7-high, gemini-3.8-flash-high, deepseek-v4.1-flash, hermes-glm-5.3-max. Сиденья: якорь на Seat 1, оба неякорных из native (gemini, grok) — external muse выше по рангу, но квота |native|≥2 его не пускает. `hat_index = int(SHA-256("2db18b15#hats")[:8], 16) % 6 = 5` → (В, Р, С) по pinned ID; grok-4.7-high = Скептик, Seat 3. Расхождений нет.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Контракт finish/usage и инвариант «префикс необратим» заданы, но три места ломают систему при реализации как написано.
   SUB КОРРЕКТНОСТЬ/OpenAI SSE и Droid JSON-RPC streaming: FAIL — architecture-packet.json#AD-004, architecture-packet.json#CD-001. F-001: успех описан как один `finish_reason`, затем отдельный optional usage, затем DONE. Сейчас usage едет во втором чанке, у которого `finish_reason` повторяется (`server.py` около `_serve_sse`). Пакет не говорит, какой `finish_reason` у usage-чанка. DSH читает usage из stream-chunk; пустой `finish_reason: null` на usage-чанке может потерять usage, повтор `stop` может задвоить завершение. Это ломает единственный путь, которым клиент получает `cached_tokens`.
   SUB КОРРЕКТНОСТЬ/Освобождение L и T (RW-009): FAIL — architecture-packet.json#AD-003, architecture-packet.json#EVD-006. F-002: «release сразу после хода» и «checkpoint+L/T release before writer drain» несовместимы с fence. При precommit cancel L/T держатся до own terminal или waitpid. Если terminal не приходит, а waitpid не ограничен, аренда чата и слот вычисления не возвращаются, и RW-009 (5-й ход после 4 медленных) не выполняется. Дедлайна fence в пакете нет.
   SUB КОРРЕКТНОСТЬ/ToolCallParser без утечки тегов: FAIL — architecture-packet.json#AD-002, architecture-packet.json#EVD-005. F-003: strict-live («malformed/unclosed recognized XML → error, 0 байт XML в content») нельзя получить переиспользованием текущего `ToolCallParser` без смены контракта. Сейчас незакрытый блок на `finish()` и невалидный блок отдаются в content (`_flush_all`, `_emit(OPEN+inner+CLOSE)`). Отдельного live-режима у парсера нет. Плюс «accepted queue payload = видимость» делает необратимым кадр, который клиент ещё не получил: cancel до send уже запрещает retry и оставляет DIRTY.
   СОВЕТЫ:
   - Заморозить точную форму usage-чанка: `finish_reason` равен finish успешного чанка или `null`, один usage, `cached_tokens` без clamp, затем ровно один `[DONE]`. Зафиксировать это в AD-004 и VER-007.
   - Ввести дедлайн cancellation fence. По истечении: kill process group, waitpid с пределом, затем обязательный release L/T и перевод в DIRTY. «Ждать terminal вечно» запретить.
   - Развести видимость: retry запрещён только после успешного send, не после enqueue. Либо явно принять и проверить ложный DIRTY до send.
   - Задать live-режим парсера отдельным контрактом (не молчаливая смена `finish()`), с красным тестом на split тега, malformed и unclosed до старта Coder.

2. ПОЛНОТА: VERDICT=FAIL
   WHY=AD-001..004, BND-001..003, CD-001, VER-001..012 и QA-001..005 присутствуют и связаны. Дыры в покрытии, не в списке ID.
   SUB ПОЛНОТА/Решения, границы, контракт: FAIL — architecture-packet.json#AD-001, architecture-packet.json#BND-002. F-004: AD-001 верифицируется только VER-008 и VER-012 (живой слот и тайминг). Retract, non-prefix complete, suffix-only complete и запрет повтора accumulator проверяет VER-006, но AD-001 на него не ссылается. Граница BND-002 запрещает retry after prefix и lease reuse без fence, а её verification_ids не включают VER-010, хотя без решения владельца эти проверки нельзя менять.
   SUB ПОЛНОТА/Verification и quality: FAIL — architecture-packet.json#VER-001, architecture-packet.json#QA-005. F-005: VER-001 требует red→green delayed-delta, но команда — весь `unittest discover`, без имени нового теста. VER-004 говорит «verifier добавляет» тесты, хотя пакет сам пишет, что тесты пишет Coder. F-006: в QA нет сценария tool-roundtrip. После live `tool_calls` клиент присылает `role=tool`, а CD-001 говорит «tools не исполняются, автоматического replay нет». Кто исполняет инструмент и как следующий ход склеивается с необратимым prefix, не задано. F-007: persist failure после prefix назван в тексте, но ни один VER не строит этот барьер, хотя VER-011 его упоминает в expected.
   СОВЕТЫ:
   - Привязать AD-001 к VER-006 и VER-011, BND-002 к VER-010.
   - В VER-001 указать модуль и имя нового теста, а не только discover.
   - Разделить роли: Coder пишет red→green, Verifier только гоняет замороженные команды.
   - Добавить QA на tool continuation: кто вызывает инструмент, что уходит в следующий ход, что запрещено реплеить.
   - Вынести persist-failure-after-prefix в отдельный проверяемый шаг VER-011 с барьером.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
   WHY=Новых зависимостей нет, шов `StreamSink` есть. Сборка, как нарисована, не сходится.
   SUB РЕАЛИЗУЕМОСТЬ/server.py и droid_adapter.py: FAIL — architecture-packet.json#VIEW-001, architecture-packet.json#AD-003. F-008: component view рисует parser внутри Run (`R --> P`), sequence рисует `P -> W` напрямую, BND-002 говорит «ToolCallParser in facade», а BND-003 запрещает парсеру socket/RPC. Три владельца одного компонента. Writer описан и как очередь, и как поток сокета, и как участник sequence, который шлёт failure в Execution. Кто создаёт поток, кто его останавливает и кто владеет reserved control slot, не названо. F-009: coalesce ≤40 мс требует таймера, а sink обязан быть nonblocking. Кто коалесцирует (RPC-поток, writer, третий таймер) и что происходит с последним чанком короче 40 мс перед terminal, не задано. Иначе последний токен задерживается, либо таймер блокирует RPC.
   SUB РЕАЛИЗУЕМОСТЬ/Новые зависимости: PASS — architecture-packet.json#EVD-013, evolution.compatibility. Stdlib `ThreadingHTTPServer`, `queue`, потоки. Новых пакетов нет.
   СОВЕТЫ:
   - Назначить одного владельца парсера: фасад. Run отдаёт только сырые text/reasoning offsets. Поправить VIEW-001 и sequence.
   - Назначить владельца writer: один request-scoped поток, очередь stdlib, sink только `put_nowait`. Останов writer — в том же request finally, без демона без учёта.
   - Coalesce делать в writer по дедлайну 40 мс, с немедленным flush перед finish/error/DONE. RPC таймер не ждёт.
   - Control slot резервировать при открытии очереди, не «находить» при overflow.

4. РИСКИ: VERDICT=FAIL
   WHY=Обрыв и медленный клиент названы, но два сценария остаются дырами, через которые система не сходится.
   SUB РИСКИ/Обрыв соединения: FAIL — architecture-packet.json#RISK-004, architecture-packet.json#AD-001. F-010: post-commit disconnect «только delivery abort» не определён, если disconnect приходит в окне между own terminal и durable checkpoint. Два исхода (READY+release и DIRTY+fence) могут примениться к одному attempt id. Writer при этом уже мог принять prefix. Итог: либо success finish на незакоммиченном ходе, либо DIRTY после частичного READY. F-011: error-кадр пакета («standard error frame») не совпадает с текущим `{"error": err}` без OpenAI chunk-обёртки. Клиент, который ждёт `chat.completion.chunk`, не увидит ошибку и будет ждать finish.
   SUB РИСКИ/Медленный клиент и очередь: FAIL — architecture-packet.json#AD-003, architecture-packet.json#QA-003. F-012: лимит 1024 кадра при coalesce 40 мс не защищает быстрый upstream. Пока writer спит на coalesce, RPC продолжает enqueue. Overflow отменяет ход, который клиент читает нормально, только чанки мелкие. 16 МиБ на ответ при глобальных 256 МиБ и нескольких чатах с thinking+tool XML упирается в глобальный резерв раньше, чем в очередь, и тоже отменяет ход. Reserved control slot не описан как неучитываемый в 1024, поэтому error/DONE могут не влезть после discard.
   СОВЕТЫ:
   - Сделать исход attempt однократным: compare-and-set до любого finish/error. Поздний disconnect не переписывает уже зафиксированный исход.
   - Зафиксировать error-кадр как OpenAI chunk плюс `error`, затем `[DONE]`, и добавить это в VER-006.
   - Считать overflow по байтам после coalesce, не по сырым кадрам. Control slot держать вне лимита 1024. Мелкие чанки не должны отменять ход у читающего клиента.
   - Проверить 4×3 МиБ против 16 МиБ очереди и 256 МиБ глобально отдельным числом в VER-009, не только «малый injected cap».

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Выбор live против искусственной задержки обоснован и честно ограничен.
   SUB АЛЬТЕРНАТИВЫ/Live вместо искусственной паузы: PASS — architecture-packet.json#AD-001, architecture-packet.json#RISK-005. Буфер до terminal и «подождать message complete» названы и отвергнуты: они не дают token-live. Подделка темпа и таймстампов запрещена. 20–80 tok/s и TTFT<2 с помечены целями, не гарантией. Этого достаточно.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
   WHY=Оба требуемых сохранения заявлены, но одно из них противоречит другому решению того же пакета.
   SUB СООТВЕТСТВИЕ КОНТЕКСТУ/cached_tokens без clamp: PASS — architecture-packet.json#AD-004, architecture-packet.json#VER-007, architecture-packet.json#EVD-011. Один optional usage, `cached_tokens` как есть, отсутствие и ноль сохраняются, clamp не предлагается. Совпадает с `normalize_prompt_cache_details`: при `cache_read > prompt` ключ не выдаётся, значение не подрезается.
   SUB СООТВЕТСТВИЕ КОНТЕКСТУ/Non-streaming без деградации: FAIL — architecture-packet.json#AD-002, architecture-packet.json#CD-001. F-013: nonstream обещан committed-only и со старым XML fallback. Тот же `ToolCallParser` предлагается переиспользовать для strict-live. Если strict попадёт в общий `finish()`, nonstream начнёт отдавать error вместо текста на malformed XML. Пакет не фиксирует развилку по режиму и не даёт теста, что nonstream fallback не изменился. Это и есть деградация, которую критерий запрещает.
   СОВЕТЫ:
   - Зафиксировать два входа парсера: live-strict только при `stream=true`, `finish()` nonstream не менять.
   - Добавить в VER-004 явный nonstream-кейс: malformed и unclosed по-прежнему попадают в content, не в error.
   - Не менять assertions `test_buffered_text_not_leaked_on_failed_turn` для nonstream. Для SSE менять только после approval AD-001, отдельным тестом.

ОБЩИЙ ВЕРДИКТ: NEEDS WORK

Пакет честно черновик: блокеры AD-001 и AD-002 вынесены владельцу, зависимости не добавляются, подделка метрик запрещена. Реализация по текущему тексту не сойдётся: форма usage-чанка не задана, fence L/T без дедлайна, парсер не умеет strict-live без поломки nonstream, у parser/writer/coalesce нет одного владельца, окно terminal-до-checkpoint двусмысленно, лимит 1024 кадров отменяет здоровый ход. До Coder эти шесть мест надо закрыть в пакете, не в коде.
