Пока работаешь, каждые 4,5 минуты выводи отдельной строкой ровно `[hb] ок`; команду дольше 4 минут не жди молча — запусти в фоне и каждые 4,5 минуты выводи `[hb] ок`, проверяя, завершилась ли. Строки `[hb]` служебные, не часть ответа.

# РОЛЬ: Coder (AI-SDLC Rework Implementation, Cycle 1 Round 2)
# СКИЛЛ: /Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/skills/rework.md — прочитать целиком и следовать (anti-ballooning, surgical diff, оракул на каждое замечание, git-контракт реворка).
# ПРОЕКТНЫЙ КАНОН: /Users/aazhiry1/Мой диск/skils/ai-sdlc/python/aisdlc-gcge/AGENTS.md + agents/code.md + agents/python-standards.md + agents/scope-and-contracts.md + agents/testing.md
# МОДЕЛЬ: deepseek-v4.1-flash (effort max; транспорт — твой собственный запуск, Factory Droid)
# РАБОЧАЯ ДИРЕКТОРИЯ: /Users/aazhiry1/work/src/cli-agent-bridge
# ТЕКУЩАЯ ВЕТКА: dev (НЕ переключаться, НЕ создавать новую ветку, НЕ коммитить — только правки рабочего дерева; это продолжение незакоммиченной дельты Round 1)

## Задача
Устранить 3 блокирующих замечания Кодовой панели техлидов Раунда 2 (RW-203, RW-208,
RW-211) и реализовать 1 нетормозящую рекомендацию (FU-212) из утверждённого брифа
доработки:
`.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1r2.json`

## Входные артефакты (уже на диске, перечитывать не нужно — читай сам файл за фактурой)
- Бриф: `.ai-team/runs/dsh-realtime-streaming/handoff/panel-rework-brief-code-c1r2.json`
- Леджер замечаний: `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/findings-ledger-r2.md`
- Вердикт Round 2: `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/verdict-c1r2.md`
- Diff под ревью (контекст, не применять повторно — он уже в рабочем дереве): `.ai-team/runs/dsh-realtime-streaming/code-panel/cycle-1/diff-r2.patch`

## Запрещено изменять (do_not_change из брифа)
- `server.py:_serve_json` (non-stream flow)
- `core/metrics_normalizer.py:normalize_prompt_cache_details`
- `adapters/muse_adapter.py`

## Инструкции по замечаниям

### 1. RW-203 (блокирующее, server.py: Handler._execute, Handler._serve_sse)
Флаг `client_write_dead = [False]` сейчас изолирован внутри `_execute()`; внешний
`_serve_sse()` после `_execute()` ничего о нём не знает и пытается писать клиенту
терминальный `finish_reason: stop`, `usage` и `data: [DONE]\n\n`.
- Передать состояние `client_write_dead` из `_execute` во внешний `_serve_sse`
  (атрибут `self._client_write_dead` на Handler, сбрасываемый в начале каждого
  запроса, либо через возвращаемый `out`).
- В `_serve_sse()` после `_execute()`/`_dispatch`: если `client_write_dead == True`,
  полностью прекратить любые дальнейшие попытки записи клиенту — без
  terminal `stop`/`tool_call`, без `usage`, без error-кадра, без `[DONE]`.
- Сохранить `LIVE_WRITE_TIMEOUT_S` (3.0 с) и штатное освобождение ресурсов/блокировок
  L/T в `_execute` (RW-009) независимо от состояния клиента.
- Приёмка: после отказа sse_writer нет НИКАКИХ новых `_emit`; следующий запрос не
  наследует `client_write_dead`; здоровый ход сохраняет успешные терминальные кадры.

### 2. RW-208 (блокирующее, server.py: Run.__init__, Run._publish, Run._terminal)
`RUN_QUEUE_MAXSIZE` и отбрасывающий `put_nowait()` с `live_invalidated = True`
применены ко ВСЕМ вызовам, включая non-stream buffered (`sse_writer is None`), что
роняет легитимный non-stream запрос при >1024 событий на terminal.
- Ограничение емкости очереди и отбрасывание через `put_nowait()` — ТОЛЬКО при
  `self._sse_writer is not None` (активный live-стриминг).
- При `self._sse_writer is None` (non-stream buffered) — очередь не ограничена и не
  отбрасывает события, `live_invalidated` из-за размера очереди не выставляется
  (обычный `put()` / неограниченная очередь).
- Приёмка: non-stream запрос с >1024 событиями на terminal возвращает полный
  content/reasoning и прежний usage без потерь и без `live_invalidated`; live-очередь
  остаётся ограничена и честно fail-close при переполнении.

### 3. RW-211 (блокирующее, server.py: Handler._execute (kind == "done"), Handler._serve_sse)
`_execute` в ветке `kind == "done"` не проверяет `run.live_invalidated` до финализации
успеха; `_serve_sse` при сбое хода/адаптера после отправленного live-префикса не
отдаёт клиенту согласованный OpenAI error-конверт.
- В `_execute`, ветка `kind == "done"`: проверять `run.live_invalidated` ДО
  `parser.finish` и отдачи успеха; при `True` — fail-close даже при `rc == 0`.
- В `_serve_sse`: если после отправки live-префикса (`sent_live_bytes > 0`) произошёл
  сбой (`state == "error"` или исключение из dispatch) и сокет клиента жив
  (`not client_write_dead`):
  - отправить ровно один `chat.completion.chunk` с объектом
    `"error": {"message": ..., "type": "stream_error", "code": "live_prefix_invalidated", "param": null}`,
    `choices=[{"index": 0, "delta": {}, "finish_reason": None}]`, неизменными
    `id`/`created`/`model`;
  - затем отдельный `data: [DONE]\n\n`;
  - НЕ отправлять `finish_reason: stop` и НЕ отправлять `usage`.
- Приёмка: сценарий `live_invalidated=True` + `kind=done` + `rc=0` даёт fail-close;
  сбой после live-префикса даёт ровно один error-чанк + отдельный `[DONE]`, без
  finish/usage/сырого исключения; мёртвый сокет не получает новых попыток записи
  (соблюдается RW-203).

### 4. FU-212 (нетормозящее, tests/test_live_stream.py)
Расширить файл явными регрессионными тестами:
1. `_serve_sse` при отказе live-записи (mock/drop sse_writer): ни один терминальный
   кадр (`stop`, `usage`, `[DONE]`) не отправляется; флаг не протекает на следующий
   запрос.
2. Non-stream buffered ход с >1024 событиями на terminal: все события доходят, ответ
   полный, без ошибок `live_invalidated`.
3. Отправка live-префикса с последующим сбоем хода (`state="error"` или exception):
   клиент получает error chunk `chat.completion.chunk` со структурой OpenAI,
   `finish_reason: null`, отдельный `[DONE]`, без finish/usage.
4. `live_invalidated == True` перед `kind == "done"` с `rc == 0`: отдаётся fail-close.

Показать red → green по месту (временно откатить фикс локально в голове/логически не
нужно — тест должен падать на коде ДО твоей правки этого цикла и зеленеть после; если
правка уже частично в рабочем дереве — убедиться, что тест действительно покрывает
нужную ветку, а не тривиально проходит).

## Правила реворка (rework.md, сжато — прочитать файл целиком обязательно)
- Хирургическая дельта: 1–15 строк на замечание; превышение — только с явным
  объяснением в отчёте.
- Никакого попутного рефакторинга («заодно причесал») — запрещено.
- Править только файлы/блоки, на которые указали замечания.
- На каждое замечание класса КОРРЕКТНОСТЬ — воспроизводимый тест (red → green).
- Алгоритмический скелет Cycle 1 стабилен по умолчанию; полная замена метода —
  только с доказательством в отдельной секции отчёта.
- Ветка остаётся `dev` (текущая); НЕ коммитить, НЕ открывать MR, НЕ пушить.

## Проверка перед сдачей
```bash
python3 -m unittest tests/test_live_stream.py
python3 -m unittest tests/test_live_stream.py tests/test_tool_parser.py tests/test_cache_usage.py tests/test_rpc_core.py tests/test_bridge_http.py
ruff check server.py tests/test_live_stream.py
```
Все команды должны завершиться без ошибок (unittest — OK, ruff — без новых findings).
Приложить сырой вывод в отчёт.

## Формат отчёта (в конце ответа)
Для каждого ID (RW-203, RW-208, RW-211, FU-212): файл:строка правки + однострочное
объяснение + имя теста, который доказывает фикс. Плюс сырой вывод всех команд
проверки. Если что-то не удалось — честно BLOCKED с причиной, не изобретать успех.
Не выноси архитектурных решений за рамки do_not_change и этого брифа; неоднозначность
— выбери безопасный консервативный вариант и опиши его в отчёте, не спрашивай.
