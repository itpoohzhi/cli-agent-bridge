[F-01] Метод item/delta в Meta CLI ServeRun присылает чанки размышлений в поле summary.N с kind reasoning | bridges/muse-bridge/server.py:2248-2260 | 2026-10-17
[F-02] Мост искусственно замораживает live-стриминг размышлений при idx > 0 или item/completed для reasoning | bridges/muse-bridge/server.py:2229-2231/2261-2263 | 2026-10-17
[F-03] Метод _live_reasoning_sink принимает только summary.0 и прекращает отправку при нарушении префикса full_text | bridges/muse-bridge/server.py:2642-2657 | 2026-10-17
[F-04] Оставшиеся шаги summary.1..N отправляются единым блоком в _send_sse только после полного завершения хода модели | bridges/muse-bridge/server.py:2854-2875 | 2026-10-17
[F-05] Вызовы инструментов tool_item фиксируются в _handle_event но не передаются в live SSE поток клиенту | bridges/muse-bridge/server.py:2220-2228 | 2026-10-17
[F-06] При таймауте хода или ошибке метод _send с кодом 502 сразу закрывает поток кадром error и DONE без сброса накопленного reasoning | bridges/muse-bridge/server.py:2784-2794/3513-3524 | 2026-10-17
[F-07] Дедлайн хода TIMEOUT_S составляет 1800 секунд за вычетом FINISH_RESERVE_S 35 секунд | bridges/muse-bridge/server.py:66/2998-3000 | 2026-10-17
[F-08] DeepSeek Harness отображает поток размышлений из SSE-поля delta.reasoning_content чанка chat.completion.chunk | bridges/muse-bridge/server.py:2624-2631/2652-2654 | 2026-10-17
