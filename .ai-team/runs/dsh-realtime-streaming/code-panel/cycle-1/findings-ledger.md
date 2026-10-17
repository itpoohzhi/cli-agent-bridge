# CONSENSUS LEDGER — CODE PANEL CYCLE 1 R1
Round: R1
Consensus status: NEEDS WORK (Majority 2/3: Realist [OpenAI], Skeptic [DeepSeek])

### F-201
- **id:** F-201
- origin: Realist (Seat 1) & Skeptic (Seat 2)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=FAIL Seat 3=PASS
- summary: keepalive в Handler._execute обходит защиту RW-009: не проверяет client_write_dead и использует таймаут соединения (300 с), что блокирует поток вычислений и держит блокировки L/T при заполнении окна сокета

### F-202
- **id:** F-202
- origin: Realist (Seat 1) & Skeptic (Seat 2)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=FAIL Seat 3=PASS
- summary: Wire-формат чанка ошибки при fail-close: отдаётся плоский data: {"error": ...} вместо OpenAI-совместимого конверта chat.completion.chunk с объектом ошибки (type: "stream_error", code: "live_prefix_invalidated", param: null)

### F-203
- **id:** F-203
- origin: Realist (Seat 1) & Skeptic (Seat 2)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=FAIL Seat 3=PASS
- summary: При сбое live-записи (таймаут/обрыв сокета) остаток ответа отсекается, но в конце хода всё равно отдаётся успешный finish_reason: "stop", usage и [DONE], скрывая потерю данных

### F-204
- **id:** F-204
- origin: Realist (Seat 1) & Skeptic (Seat 2)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=FAIL Seat 3=PASS
- summary: Run.q в server.py не имеет ограничения maxsize (рекомендация F-103), что создаёт риск неограниченного роста памяти при медленном потребителе

### F-205
- **id:** F-205
- origin: Realist (Seat 1) & Skeptic (Seat 2)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=FAIL Seat 3=PASS
- summary: Отсутствует проверка text.startswith(sent_prefix) при complete: если текст изменился без события retract (non-prefix / short complete), происходит молчаливая отдача среза вместо fail-close

### F-206
- **id:** F-206
- origin: Realist (Seat 1)
- priority: blocking
- status: CONSENTED
- outcome: blocking
- votes: Seat 1=FAIL Seat 2=PASS Seat 3=PASS
- summary: Резервирование _DELIVERY_BUDGET должно считаться в байтах UTF-8 (len(piece.encode("utf-8"))), а не символах len(piece); изоляция finish_reason: null только для Droid live stream

### F-207
- **id:** F-207
- origin: Skeptic (Seat 2)
- priority: non-blocking
- status: CONSENTED
- outcome: non-blocking
- votes: Seat 1=PASS Seat 2=FAIL Seat 3=PASS
- summary: В tests/test_live_stream.py тест модифицирует глобальный server.MAX_CONCURRENT = 1 без гарантированного восстановления в tearDown
