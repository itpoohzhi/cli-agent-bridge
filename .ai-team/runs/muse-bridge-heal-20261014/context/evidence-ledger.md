# Evidence ledger: muse-bridge-heal

Тема: доработка `bridges/muse-bridge/server.py` (репо `~/work/src/cli-agent-bridge`), живая копия `~/.dsh/bridges/muse-bridge/server.py`.
Дата сбора: 2026-10-14. Формат строки: `[F-NN] утверждение | источник | YYYY-MM-DD`.
Номера строк даны для репо-версии `bridges/muse-bridge/server.py` (1844 строки), если не указано иное. В живой копии строки после 77-й сдвинуты на +2.
Секреты и содержимое промптов в реестр не выносились.

## Код: логирование и диагностика ошибок

[F-01] `_serve_json` имеет три ранних выхода с HTTP 502 без вызова `_log`: spawn/launcher (1690-1701), провал хода state != ok или rc != 0 (1702-1717), пустой вывод (1722-1735); единственная итоговая запись `done` стоит на 1782-1786 и достигается только при успехе | `bridges/muse-bridge/server.py:1690-1735,1782-1786` | 2026-10-14
[F-02] `_log` пишет строку и в stderr, и в `LOG_PATH` (по умолчанию `<ROOT>/logs/bridge.log`) | `bridges/muse-bridge/server.py:70,156-165` | 2026-10-14
[F-03] Ответ об ошибке хода имеет вид `muse turn failed (rc=…, state=…)` в `message`, причина идёт отдельным полем `detail` (обрезка 500 символов), а не в хвосте message; при пустом `err` detail пустой | `bridges/muse-bridge/server.py:1705-1716` | 2026-10-14
[F-04] В `ServeRun.execute` при `turn/completed` читается только `params.terminal`; поля `params.error` и `params.reason` не читаются | `bridges/muse-bridge/server.py:1188-1196` | 2026-10-14
[F-05] Схема MSP (muse serve 1.4.7): `TurnCompletedParams.error` (объект `TurnError` с полями kind, message, retryable) присутствует при terminal=failed, `reason` содержит свободный текст причины, `terminal` принимает значения completed, failed, cancelled | `muse schema generate-json-schema --out /tmp/muse-schema-sa`, файл msp.schema.json, `#/$defs/TurnCompletedParams`, `#/$defs/TurnError`, `#/$defs/TurnTerminal`; версия serve из `~/.dsh/bridges/muse-bridge/logs/bridge.log:1045` | 2026-10-14
[F-06] При terminal != completed `ServeRun.execute` возвращает rc=1, state=`terminal_<terminal>`, err = последние 6 строк stderr процесса serve (текст из turn/completed туда не попадает) | `bridges/muse-bridge/server.py:1219,1231-1241` | 2026-10-14
[F-18] В SSE-режиме `_send` останавливает keepalive, отправляет кадр `{"error": …}` и `data: [DONE]`; при этом HTTP-статус уже 200 | `bridges/muse-bridge/server.py:1406-1416` | 2026-10-14

## Код: approval/request и встроенные инструменты Muse

[F-07] В MSP `approval/request` является серверным запросом, требующим ответа (ответ — квитанция показа), решение передаётся отдельным методом `approval/decide`; типы `ApprovalDecideParams` и `ApprovalRequestParams` есть в схеме | msp.schema.json, `requests["approval/request"]`, `#/$defs/ApprovalDecideParams`, `#/$defs/ApprovalRequestParams` | 2026-10-14
[F-08] Мост не отвечает на `approval/request`: `_handle_event` сразу бросает `ServeUnavailable("serve needs interaction (approval/request)")`; в файле нет ни `denied`, ни `decision` (проверка rg по словам denied и decision дала пустой вывод). Утверждение брифа «мост отвечает decision denied в 1145-1152» не подтверждено | `bridges/muse-bridge/server.py:1089-1090`; rg -n -i с шаблоном из слов denied и decision по `bridges/muse-bridge/server.py` (пусто) | 2026-10-14
[F-09] `ServeUnavailable` в `_serve_json` приводит к записи `serve unavailable (…), fallback exec model=…` и запуску `Run` (muse exec); запись есть в коде на 1654 | `bridges/muse-bridge/server.py:1642-1659` | 2026-10-14
[F-10] Argv `muse serve`: `--provider meta --model <id> --no-session-log --trust-workspace`; флагов `--disable-write` и `--disable-shell` нет | `bridges/muse-bridge/server.py:980-989` | 2026-10-14
[F-11] Argv `muse exec`: `--provider meta --model --reasoning-effort --yolo --trust-workspace --workspace --json --no-session-log --prompt-file`; флагов disable-* нет. Диапазон 1363-1384 из брифа относится к `_client_gone_probe`, а не к argv | `bridges/muse-bridge/server.py:718-733,1361-1383` | 2026-10-14
[F-12] `muse serve --help` содержит `--disable-write`, `--disable-shell`, `--disable-sandbox`; режим approval выбирается по wire, отдельного флага approval у serve нет | `~/.local/bin/muse serve --help` | 2026-10-14
[F-13] `muse exec --help` содержит `--disable-write`, `--disable-shell`, `--disable-web-tools`, `--disable-reminders`, `--approval-mode` со значениями untrusted, on-request, never, `--disable-approval`, `--yolo` | `~/.local/bin/muse exec --help` | 2026-10-14
[F-14] `session/start` отправляется без `approvalMode`; комментарий в коде фиксирует, что явные значения отвергает sealed ceiling неинтерактивного serve (commandRejected/approval_mode_ceiling), а запрос approval по ходу ведёт к fallback на exec | `bridges/muse-bridge/server.py:1143-1158` | 2026-10-14
[F-27] Запрет встроенных инструментов в системном промпте есть только текстом (`Never attempt to use built-in tools…`) и действует лишь при эмуляции tool_calls | `bridges/muse-bridge/server.py:272-273` | 2026-10-14
[F-24] В bridge.log запись `serve unavailable (serve needs interaction (approval/request))` встречается 5 раз за период 2026-10-09..2026-10-13, каждый раз с переходом на exec | `~/.dsh/bridges/muse-bridge/logs/bridge.log:792,807,814,821,1034` | 2026-10-14

## Код: SSE keepalive

[F-16] `_keepalive_loop` каждые `KEEPALIVE_S` (по умолчанию 15 с, env `MUSE_BRIDGE_KEEPALIVE_S`) пишет только SSE-комментарий `: keepalive`; docstring самого кода признаёт, что такие комментарии не сбрасывают idle-watchdog SDK | `bridges/muse-bridge/server.py:522,1347-1351` | 2026-10-14
[F-17] Помощники `_sse_chunk` и `_sse_emit` строят валидный `chat.completion.chunk`; кадр с пустой дельтой уже используется: role-кадр `{"role":"assistant","content":""}` в `_sse_begin` и финальный `chunk({}, finish)` с usage | `bridges/muse-bridge/server.py:1307-1317,1337,1475-1483` | 2026-10-14

## Клиент и конфигурация

[F-19] Провайдер muse-bridge в DSH: baseURL `http://127.0.0.1:9886/v1`, `timeoutMs` и `streamIdleTimeoutMs` равны 1900000 (31 мин 40 с); номер строки 628 из брифа неверен | `~/.dsh/profiles/desktop/cordis.patch.yml:327-333` | 2026-10-14
[F-20] Исходник клиента pi-ai и сессия `414ef0d0…jsonl` не найдены: каталога `~/.dsh/agent` нет, поиск по `~/.dsh/sessions` пуст, `rg "stream idle timeout"` в `~/.dsh/llm-deepseek` и `~/.dsh/dsh-runtimes` пуст; поведение клиента при SSE-комментариях не подтверждено | `ls ~/.dsh`; `find ~/.dsh/sessions -name "*414ef0d0*"`; `rg -l "stream idle timeout"` | 2026-10-14
[F-21] Бюджет хода моста `TIMEOUT_S` по умолчанию 1800 с (таймер exec и deadline serve), то есть меньше клиентского idle 1900 с; переопределения env в каталоге моста не найдено; ходы, упёршиеся в бюджет, пишутся как `rc=-9 state=timeout` | `bridges/muse-bridge/server.py:62,790,1024`; `~/.dsh/bridges/muse-bridge/logs/bridge.log:671,752,757,809` | 2026-10-14

## Рантайм: журнал моста

[F-22] В bridge.log нет записей за окно 2026-10-14 08:36-08:40 из брифа; ближайшие события: 2026-10-13 23:24:39 fallback на exec из-за approval/request, затем `exec … prompt_chars=1326216`, затем 2026-10-14 00:02:01 `client gone during run`. В диапазоне строк 1041-1054 четыре записи `serve turn` и только две записи `done`: два хода не имеют итоговой записи | `~/.dsh/bridges/muse-bridge/logs/bridge.log:1034-1054` | 2026-10-14
[F-23] Строка с `terminal_failed` в bridge.log одна: 2026-10-05 09:39:44 `done … state=terminal_failed` (формат более ранней версии кода); текущий код такой записи не создаёт | `~/.dsh/bridges/muse-bridge/logs/bridge.log:171`; `bridges/muse-bridge/server.py:1782-1786` | 2026-10-14

## Репозиторий и тесты

[F-25] `ALLOWED_MODELS` в репо содержит `muse-spark-1.3` и `muse-spark-1.3-contributor`; в живой копии добавлены `muse-wonder-1.0` и `muse-wonder-full-1.0` (по 1 048 576 контекст и 131 072 вывод) | `bridges/muse-bridge/server.py:72-77`; `~/.dsh/bridges/muse-bridge/server.py:72-78` | 2026-10-14
[F-26] Единственное различие репо и живой копии: две строки ALLOWED_MODELS (`diff` показал только их, 1844 против 1846 строк); репо-файл совпадает с HEAD (`cmp` без различий) | `diff bridges/muse-bridge/server.py ~/.dsh/bridges/muse-bridge/server.py`; `cmp <(git show HEAD:bridges/muse-bridge/server.py) bridges/muse-bridge/server.py` | 2026-10-14
[F-15] Моста касается один тестовый файл (rg -l по именам muse-bridge и muse_bridge в `tests`): `tests/test_muse_bridge_killpg.py`, 18 тестов, про убийство групп процессов, слоты и пробу клиента; тестов на argv, approval, keepalive, `_serve_json` нет; запуск `python3 -m unittest tests.test_muse_bridge_killpg` на 2026-10-14: Ran 18 tests, OK (16.7 с); pytest в системном python3 не установлен | `tests/test_muse_bridge_killpg.py:168-641`; вывод unittest | 2026-10-14
