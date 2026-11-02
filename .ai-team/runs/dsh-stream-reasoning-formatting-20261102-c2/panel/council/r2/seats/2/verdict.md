PANEL-NONCE: e20a8d83c3838e78
ARTIFACT-SHA256: af59adc83bc9e4e7cf153c51733d7855b1b70dbc500dbed663f7ec6987958bf3

AGREE RW-008 — проверил: `bridges/agy-bridge/server.py:5504-5510` — при `content_streaming` каждый stdout-`text_delta` идёт в `offer_content("stdout", …)` и сразу в `content`. Изоляция tool-преамбул в `_emit_record` (`server.py:4551-4560`) работает только для пути transcript. Если stdout опережает transcript, преамбула шага с tool_calls попадает в `content` и закрывает аккордеон `<Think>`. Фикс небольшой: гейтить stdout-путь тем же флагом `isolate_tool_preambles`.

AGREE RW-009 — проверил: `scripts/smoke_models.py:146-167` — при `ttft is not None` сразу возвращается `STREAM_OK`, а `got_done` в этой ветке не проверяется. Оборванный поток после первого chunk считается успехом. Чанк `data: {"error":…}` не распознаётся: `finish_reason` и `error` в скрипте не разбираются. Фикс: требовать `[DONE]` и отсутствие `error`-чанка.

AGREE RW-010 — проверил: `server.py:5326` — условие `last_idx is not None and last_idx != step_index`. При `step_index=None` на следующем вызове `_last_step_index=None` и разделитель `\n\n` не ставится. Шаги без индекса по-прежнему склеиваются. Фикс: хранить отдельный флаг «был предыдущий шаг» либо считать `None` отдельным значением шага.

AGREE RW-011 — проверил: `tests/test_stream_formatting_and_subagents.py:1-48` и список тестов (строки 49, 95, 131, 201) — в файле нет HTTP-сервера и SSE-клиента. Тесты вызывают `srv.*` внутри процесса и не парсят SSE-кадры. Непрерывность родительского стрима при `invoke_subagent` проверяется только синтетически. Это противоречит заявленному в AGENTS.md L2 («валидация протокола SSE», «мультиагентный цикл»). Приоритет — major, но заявленное покрытие не соответствует фактическому.

AGREE RW-005 — проверил: `~/Мой диск/Context/models.md:93-105,162` и вывод `smoke_models.py --dry-run` — в dry-run только 20 записей. Пропущены модели роли Reviewer, Brief-review, Coordinator и Explorer: `gemini-4-argon-medium`, `gemini-3.8-flash-*`, `claude-haiku-5-5`, `gpt-6.1-terra`, `deepseek-v4.1-flash`, `claude-sonnet-5-5-xhigh`. Причина — `row_pattern` (`smoke_models.py:48-50`) принимает только таблицы вида «модель | effort | family», а 5-колоночные таблицы с колонкой роли и ячейки вроде `effort` не из `[a-zA-Z0-9]` не матчатся. Пропуск тихий, без предупреждения. Фикс: парсить все backtick-ID в таблицах либо падать, если число строк таблиц и число распарсенных записей расходится.

AGREE RW-012 — проверил: `server.py:4554-4558` и `5326` — при `idx=None` ключ дедупа `-1` общий для всех безиндексных преамбул. Второй и последующие tool-шаги без индекса теряются в reasoning, а `emit(0, …)` пишет их под чужим индексом. Склейка из RW-010 в той же ветке сохраняется. RW-012 включает RW-010: достаточно одного фикса, а `step_index=None` нужно покрыть тестом.

VERDICT: NEEDS WORK
