# Черновой леджер совещания Совета Тимлидов по коду (цикл 12, после R1 r245, run analyst-teamlead-zen-realtime-reasoning-20261025)

- Всего находок R1: `5` (`F-001..F-005`: `skeptic` `нет (0 находок, ACCEPT)`, `realist` `F-001..F-005`, `visionary` `нет (0 находок, ACCEPT)`).
- Открытых blocking (`OPEN_BLOCKING`): `5`; открытых non-blocking: `0`.

### F-001
- origin: realist · R1 · realist-F-001
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-001 — priority=blocking: протокольная ошибка security-control допускает повтор.**
>
>    locations: `server.py:2873`, `server.py:2876`, `server.py:3508`, `server.py:3579`, `server.py:3988`, `server.py:4494`, `server.py:6785`, `server.py:8204`.
>
>    Правило: REQ-012, FALLBACK_DECISION_TABLE — ошибки permission/form должны завершаться fail-closed.
>
>    Evidence: `_serve_http` поднимает `ServeProtocolError` при превышении размера тела; разбор непарного суррогата также поднимает этот тип. Обработчики `_reject_and_interrupt`, drain-reject и `_ctrl_quiet` его не перехватывают. Исключение попадает в общий обработчик как `invalid_serve_event`, после чего SSE и JSON допускают `allow_retry`. Если исключение возникло при cancel/reject, обязательный следующий interrupt пропускается. Для drain-веток замечание **[pre-existing]**, для нового helper — непокрытая ветка исправления RW-001.
>
>    Исправление: преобразовать `ServeProtocolError` управляющих операций безопасности в `ServeSecurityError`; обеспечить попытку interrupt после неуспешного cancel/reject. Нейтральные disconnect/deadline сохранить.
>
>    Проверка: инъекция протокольной ошибки в cancel/reply/interrupt основного цикла и дренажа; одна serve-попытка, отсутствие run-fallback, терминальная ошибка безопасности и cleanup группы.

### F-002
- origin: realist · R1 · realist-F-002
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-002 [sweep] — priority=blocking: Run JSON вставляет немодельные байты в reasoning.**
>
>    locations: `server.py:5908`, `tests/test_realtime_reasoning.py:3453`.
>
>    Правило: REQ-005, AC-006 — reasoning модели сохраняется побайтово; синтетические строки должны быть явно обозначены.
>
>    Evidence: `_with_previous` объединяет reasoning через `"\n\n".join(...)`. Для последовательности `"мысль-run-1"` → `"мысль-run-2"` возвращаются дополнительные LF. Новый тест закрепляет именно эти добавленные байты. Serve JSON использует непосредственную конкатенацию.
>
>    Исправление: объединять исходные reasoning-фрагменты без добавления байтов; скорректировать оракул.
>
>    Проверка: после watchdog → успешного повтора reasoning равен конкатенации исходных байтов обеих попыток, включая исходные пробелы и LF.

### F-003
- origin: realist · R1 · realist-F-003
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-003 — priority=blocking: активный дренаж продолжает работу после отключения клиента.**
>
>    locations: `server.py:3474`, `server.py:3519`, `server.py:3521`, `server.py:3559`, `server.py:3775`, `server.py:3792`, `server.py:4409`.
>
>    Правило: REQ-008, AC-011/AC-012, C-MULT-I4, SK-T — обнаружение отключения ≤5 с, остановка группы ≤7 с.
>
>    Evidence: в drain не передаётся `is_client_gone`. Подходящие события продлевают ожидание до общего дедлайна. Последовательность `session.tool.input.delta` одной сессии/сообщения каждые 0,3 с обновляет окно без downstream-записей и без роста сохранённого tool input. После закрытия клиентского сокета основной цикл с проверкой отмены остаётся заблокирован в drain; группа и bulkhead-слот могут удерживаться значительно дольше 7 с.
>
>    Исправление: передать сигнал отмены через main → finish → drain; проверять его при событиях и коротких ожиданиях очереди; завершать через `ServeClientDisconnect` без публикации pending-вызовов и повторов.
>
>    Проверка: native-шаг с продолжающимися input-delta, затем FIN/RST клиента; проверить сроки обнаружения, смерть группы, освобождение слота и отсутствие опубликованных pending calls в SSE и JSON.

### F-004
- origin: realist · R1 · realist-F-004
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-004 [sweep] — priority=blocking: внутренний retry теряет первые временные метки запроса.**
>
>    locations: `server.py:5880`, `server.py:5905`, `server.py:6259`, `server.py:8480`, `server.py:8481`.
>
>    Правило: REQ-016, O-EXIT/v1 — `first_event_ms` и `ttft_ms` должны описывать первое наступление события в запросе.
>
>    Evidence: `_save_partial` сохраняет reasoning/text/usage, но не `first_event_at` и `first_token_at`. `_with_previous` возвращает метки последней попытки. Поэтому после частичного вывода → watchdog → успешного повтора O-EXIT сообщает время первого события/токена повторной попытки, хотя результат содержит вывод предыдущей.
>
>    Исправление: сохранять первые ненулевые метки через внутренние повторы и возвращать их вместе с объединённым результатом.
>
>    Проверка: на управляемых часах задать разные метки первой и второй попытки; проверить ранние значения в конечной строке O-EXIT, а также сумму usage.

### F-005
- origin: realist · R1 · realist-F-005
- rev: 1
- priority: blocking
- status: OPEN
- outcome: —
- resolved_in: —
- votes: R1 realist=AUTHOR
- dissent: —
- owner_decision: —
- amendments: —
- text (дословно, R1 realist):
> **F-005 [pre-existing] — priority=blocking: отсутствует обязательный удалённый фичефлаг.**
>
>    locations: `server.py:1531`, `server.py:1831`, `server.py:1909`.
>
>    Правило: общий `AGENTS.md`, раздел «Код», пункт 5 — новые фичи управляются удалённым GigaRC-флагом с default=false.
>
>    Evidence: `_read_dynamic_config_enabled` читает только соседний `dynamic_config.json`; `_select_transport` использует его и env overrides. `reverse-spec.md` §1 прямо подтверждает отсутствие интеграции с удалённым сервисом флагов. Локальный файл обеспечивает переключение между запросами, но не является указанным в каноне удалённым источником.
>
>    Исправление: согласовать и реализовать способ получения GigaRC-флага при сохранении ограничения stdlib и default=false. Если для автономного моста требуется исключение, получить его явным решением владельца; самостоятельно считать локальный JSON эквивалентом нельзя.
>
>    Проверка: на одном работающем сервере изменение удалённого флага переключает следующие запросы без рестарта; недоступный/невалидный источник сохраняет согласованное безопасное поведение.
