PANEL-NONCE: e2fdf30bb07c8174
ARTIFACT-SHA256: 8edcb4c410579c365f825cdc74d5da7417e9dfaaebce5ac465cb2b103a44b608
Канон прочитан: AGENTS.md, 430 строк

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
WHY=В пакете одновременно записаны два несовместимых дерева процессов и валидация `form.created`, которая отвергает допустимую по исходной схеме форму. Оба места ломают уже заявленные RW-006 и RW-003.
СОВЕТЫ (при FAIL):
- Свести `AD-001.details.spawn`, `listener_ownership` и `crash_recovery.creation` к одному дереву: родительский `Popen` только stdlib-helper; helper сам запускает `opencode serve` и атомарно публикует pid/pgid/lstart в lease до READY/Auth/prompt.
- Пересчитать потоки и FD под это же дерево.
- В негативных мутациях `form.created` требовать `data.form.id`, вложенный `data.form.sessionID` и `fields`. `title` и `required` оставить необязательными, как в EVD-073.
- Форма без `title` всё равно отменяется за ≤0.25 с. `invalid_serve_event` только при отсутствии id, session или fields.

2. ПОЛНОТА: VERDICT=FAIL
WHY=Два нормативных текста статуса расходятся побайтно, а объявленная полной таблица fallback не содержит ветку protocol-caused `first_token_timeout`, которую отдельно считает `_ServeHealth`.
СОВЕТЫ (при FAIL):
- Оставить один шаблон ожидания первого токена. Либо убрать «(10 с)» из `status_protocol_examples.waiting`, либо вернуть тот же счётчик в `AD-002.details.lifecycle` и задать N от такта 5.0 с.
- Добавить в `fallback_decision_table` строку: `first_token_timeout` при доказанном дефекте протокола/capability → `ServeHealth +1`, `UpstreamBreaker 0`. Текущую строку оставить только для тишины модели при валидном протоколе.
- VER-005 сверяет одну байтовую строку статуса и обе строки таблицы.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=FAIL
WHY=Команда VER-004 передаёт в `ruff format --range` пару `start:end`. У ruff 0.17.2 это `строка:колонка` без конца диапазона, и проверка захватывает хвост файла, включая замороженные `_run_env` и Google-срезы. Отдельно пакет требует переименовать `CATALOG_SOURCE`, а `tests/test_catalog_mode.py` вне allowlist читает старое имя.
СОВЕТЫ (при FAIL):
- Заменить аргумент на закрытый диапазон `--range={start}:1-{end+1}:1`. Если ruff расширяет логическую строку за hunk, гейт красный и не принимает сдвиг байтов `_run_env` (sha256 `1c51b28f…`) и `_stream_google_sse` / `_execute_google_once`.
- Прогнать эту команду на текущем `server.py` с ранним synthetic hunk: хвост файла не должен попасть в diff форматтера.
- Убрать требование переименовать атрибут `CATALOG_SOURCE`, либо явно добавить в allowlist только `tests/test_catalog_mode.py` и две ссылки на атрибут (строки 64 и 93). `type: ignore` и правка `pyrightconfig` не использовать. HTTP-ключ `catalog_source` не менять.

4. РИСКИ: VERDICT=FAIL
WHY=При SIGKILL родителя дерево из `spawn` оставляет `opencode serve` без pid в lease: reaper не имеет права убивать неизвестного ребёнка. Форма без `title` уходит в `invalid_serve_event` и не отменяется, то есть вопрос снова висит до watchdog. Под ростом нагрузки внутри уже заданных 6 слотов формула CPU (`U_pod_sidecars=0.25`) не включает процессы node; design-гейт остаётся PASS, пока H3 не измерен.
СОВЕТЫ (при FAIL):
- Закрыть окно spawn→lease тем же helper-деревом из совета по корректности. VER-005: hard kill сразу после `Popen` и до READY не оставляет свой serve, чужие PID не трогает.
- Отмена формы без `title` входит в oracle ≤0.25 с, без инкремента `_ServeHealth`.
- В H3 оставить числовой стоп по RSS. Рядом записать, что насыщение CPU шестью `opencode serve` не ловится неравенством HL-ENV и до замера serve не включается.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
WHY=Сравнены и отвергнуты с причиной L (нет RC-1), A2 (общий failure domain и один env прокси), B (429 без PoC), пустой `XDG_DATA_HOME` (теряет `auth.json`), общая DB + `_StartupGate`, `--port 0` без доказанного объявления порта, и отдельный MR только на 3a. Выбран C/A1: короткий serve, `OPENCODE_DB=:memory:`, порт резервирует родитель. При росте выше 6 одновременных запросов bulkhead отвечает 503 и потолки не поднимаются. Внутри 6 слотов ломается незамеренный RSS/CPU serve+helper+lsof и дневная квота одного egress через georouter; это отдано в H3, а не в design-PASS.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=FAIL
WHY=RW-001 требовал исполнимый range-гейт без выдуманного синтаксиса CLI и без переформатирования замороженных срезов. Текущая команда VER-004 этому не соответствует. Переименование `CATALOG_SOURCE` выходит за `coder_target_files` и ломает REQ-003: модуль `test_catalog_mode.py` в правках 17 модулей не разрешён. Публичный контракт `:9883` и Google-маршрут пакетом не расширяются; CD-001/CD-002 заданы REQ-004 и REQ-006.
СОВЕТЫ (при FAIL):
- Переписать `VER-004.command`, `expected` и `baseline_transition` под закрытый `--range` и отрицательную проверку на байты `_run_env` и Google-функций.
- Согласовать имя `CATALOG_SOURCE` с allowlist до freeze. Пока тест вне трёх файлов читает старое имя, переименование в пакете запрещено.
- Остальные 16 тестовых модулей, `start.sh`, `_run_env`, `pyproject`/lockfile и `~/.dsh` не расширять.

F-01. priority=blocking. Якорь: architecture-packet.json#VER-004. Правило: RW-001, acceptance «воспроизводимые команды» и «без выдуманных CLI-флагов»; одновременно VER-005/`immutable_run_env`. Evidence: команда вызывает `ruff format --check --range {start}:{end}`. У ruff==0.17.2 формат такой: `<start_line>:<start_column>-<end_line>:<end_column>`; конец необязателен и тогда форматируется документ до EOF. Прогон: `--range 1:2` переписал весь файл; `--range 4:99` переписал хвост после точки старта. Ранний hunk в `server.py` поэтому требует формат замороженного тела (3216 строк diff, hash `_run_env` `1c51b28f…` → другой). Ожидание: закрытый диапазон и отказ гейта, если diff форматтера задевает `_run_env` или Google-функции. Проверка: synthetic early hunk на текущем `server.py` не помечает эти срезы unformatted.

F-02. priority=blocking. Якорь: architecture-packet.json#AD-001 (`details.typing`), дубль в VER-004. Правило: REQ-003/AC-004, `coder_target_files`, FU-002 (17 модулей не править). Evidence: пакет требует «Rename mutable internal CATALOG_SOURCE to lower-case». Вне allowlist `tests/test_catalog_mode.py:64` делает `self.assertEqual(server.CATALOG_SOURCE, "static")`, строка 93 печатает `server.CATALOG_SOURCE`. Переименование атрибута роняет VER-001/VER-002; сохранение имени оставляет `reportConstantRedefinition`, а VER-004 требует `errorCount==0`. Ожидание: одно из двух явных решений в пакете — не переименовывать атрибут, либо добавить в allowlist только этот файл и две ссылки. Проверка: после Stage3 `test_catalog_mode` зелёный и basedpyright `errorCount==0` без `type: ignore`.

F-03. priority=blocking. Якоря: architecture-packet.json#AD-001 `details.spawn`, `details.listener_ownership`, `details.crash_recovery`. Правило: T-LIFE/v1, RW-006. Evidence: spawn задаёт `Popen([OPENCODE_BIN, serve, --hostname, 127.0.0.1, --port, str(port)], stdin=DEVNULL, start_new_session=True)`. `crash_recovery.creation` задаёт другое дерево: «spawn under lease-named stdlib helper which publishes child identity atomically». Прямой `Popen` serve не публикует pid до отдельной записи lease; reaper при пустом pid убивать по имени не может. Ожидание: один текст дерева процессов и тот же учёт helper/FD. Проверка: VER-005 hard kill в щели после старта до READY даёт 0 своих serve и 0 чужих сигналов.

F-04. priority=blocking. Якоря: architecture-packet.json#AD-001 `event_contract` negative_mutations формы; architecture-packet.json#EVD-073. Правило: RW-003, REQ-012, THREAT-002. Evidence: мутация «missing form.id/fields/title -> invalid_serve_event». EVD-073: у Form.Info `title` необязателен, session id лежит в `data.form.sessionID`. Форма без title становится protocol failure и не идёт в cancel ≤0.25 с, то есть вопрос снова ждёт watchdog. Ожидание: обязательны id, вложенный sessionID и fields; отсутствие title не мешает cancel и не увеличивает `_ServeHealth`. Проверка: FakeServe шлёт `form.created` без title, cancel уходит ≤0.25 с, Step2 в сокет не попадает.

F-05. priority=non-blocking. Якоря: architecture-packet.json#AD-002 `status_protocol_examples.waiting` и `details.lifecycle`. Правило: FU-005, REQ-004/AC-005. Evidence: шаблон `"[мост] Ожидание первого токена (10 с)…\n"`, lifecycle — `"[мост] Ожидание первого токена…"` каждые 5.0 с, без счётчика. Ожидание: одна байтовая строка в шаблоне, lifecycle и VER-005. Проверка: тест падает при второй строке.

F-06. priority=non-blocking. Якоря: architecture-packet.json#AD-001 `fallback_decision_table` и `transport_health.counted_failures`. Правило: FU-004, RISK-012. Evidence: таблица объявлена авторитетной и для `first_token_timeout` содержит только «valid protocol and model silence» → ServeHealth 0, UpstreamBreaker 1. `counted_failures` отдельно считает `first_token_timeout` счётчиком `_ServeHealth`, если доказан дефект протокола. Строки на этот случай в таблице нет. Ожидание: отдельная строка таблицы с ServeHealth +1 и UpstreamBreaker 0. Проверка: VER-005 параметризует обе причины и видит ровно один инкремент нужного счётчика.

F-07. [sweep] priority=non-blocking. Якорь: architecture-packet.json#AD-003 `details.cleanup`. Правило: привязка утверждения к факту ledger. Evidence: cleanup ссылается на EVD-056 для убийства потомков после выхода leader. EVD-056 — это `WORKTREE_UNCHANGED`. Факт про `_stop_proc` и потомков — EVD-055. Ожидание: заменить ссылку на EVD-055, норматив killpg не менять. Проверка: в пакете нет утверждения, которое опирается на EVD-056 как на поведение процессов.

F-08. [sweep] priority=non-blocking. Якоря: architecture-packet.json#AD-001 `listener_ownership`; `resilience_gates` C-MULT-I5 oracle. Правило: RW-004 (один lsof на горячем пути) против явного reconnect. Evidence: горячий путь permission/form/interrupt/DELETE — ровно один lsof на spawn. Тот же пакет разрешает один повторный proof ≤0.35 с при обрыве control. Оракул «exactly one lsof per successful spawn including permission/form/interrupt/DELETE» не отделяет этот recovery. Ожидание: счётчик 1 обязателен для reply/interrupt/DELETE; второй lsof допустим только в явном reconnect и не входит в бюджеты 0.25 с и 0.20 с. Проверка: spy VER-005 различает эти два сценария.

SUB Корректность/логика: FAIL — architecture-packet.json#AD-001 spawn против crash_recovery
SUB Корректность/граничные условия: FAIL — architecture-packet.json#EVD-073 title необязателен, мутация требует title
SUB Корректность/обработка ошибок: FAIL — форма без title уходит в invalid_serve_event и не отменяется
SUB Полнота/покрытие AC: FAIL — два байтовых шаблона ожидания токена, FU-005
SUB Полнота/пропущенные ветки: FAIL — нет строки таблицы для protocol-caused first_token_timeout
SUB Риски/безопасность: PASS — allowlist на трёх ветках, пароль после фильтра, ask_reject, 401/403 fail-closed
SUB Риски/данные: PASS — OPENCODE_DB=:memory:, общая DB не открывается, auth остаётся в стандартном XDG_DATA_HOME
SUB Риски/прод: FAIL — щель lease при SIGKILL и зависание question без title
SUB Реализуемость: FAIL — VER-004 `--range start:end` и переименование CATALOG_SOURCE вне allowlist
SUB Альтернативы: PASS — L, A2, B, пустой XDG, общая DB, --port 0 и отдельный MR 3a сравнены с причиной
SUB Соответствие контексту: FAIL — RW-001 и REQ-003/coder_target_files не выполнены текстом пакета

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
