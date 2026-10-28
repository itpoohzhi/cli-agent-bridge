PANEL-NONCE: 70ffa302d0155885
ARTIFACT-SHA256: 2ae457623c8fae473e1e768a9e2a798a9827630b0b7e7bdf15aba727d2f856cb
Канон прочитан: AGENTS.md, 430 строк

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=Цикл 6 закрывает RW-001, RW-002, RW-004, RW-005, RW-006, RW-007 и FU-001..FU-003: барьер `headers_at`, порог первого токена без пола 120 с, матрицы AC-016/AC-017, deadline/client_gone на старте serve, дренаж stderr, абсолютный HTTP-deadline и `skip_body`, байтовые потолки SSE/HTTP и строгие целые usage подтверждены кодом и зелёным L2 (VER-001: 466 passed). RW-003 по убийству группы и повтору внутри `MAX_TOTAL_SPAWNS` тоже закрыт. На исчерпанном JSON-пути `TRANSPORT=run` watchdog всё равно уходит клиенту и в `O-EXIT/v1` как `provider_fatal`. `Run._execute_once` при любом `watchdog_reason` ставит `fatal_error=True` (`server.py:5488`), словарь результата несёт и `fatal_error`, и `state` (`server.py:5507`), `Run.execute` при исчерпанном бюджете возвращает этот словарь (`server.py:5228-5238`), а `Handler._serve_json` на `fatal_error` без tool_calls пишет `xs["exit_reason"]="provider_fatal"` и тело «opencode provider error after partial output» (`server.py:7516-7527`). REQ-016 / AC-021 требуют на каждом `do_POST` коды `first_event_timeout`, `first_token_timeout`, `stall_timeout`. Clean-room VER-002 фиксирует ровно это: после `state=first_event_timeout` строка `O-EXIT/v1 mode=json … status=502 exit_reason=provider_fatal … duration_s=0.77` (`execution-evidence.md:3467-3470`); то же для `first_token_timeout` (`:3479-3482`, 0.79 с) и `stall_timeout` (`:3491-3494`, 0.54 с). Ветка `fatal_error=True` на детерминированном HTTP провайдера (`server.py:5442`) к этому дефекту не относится. SSE legacy и JSON serve выставляют имя фазы напрямую.
   СОВЕТЫ (при FAIL): В `Handler._serve_json` до ветки `fatal_error` обработать `out["state"]` из `{first_event_timeout, first_token_timeout, stall_timeout}`: `xs["exit_reason"]=state` и `_error_payload(f"opencode {state}")`, как на SSE. В `Run._execute_once` (`server.py:5488`) не ставить `fatal_error=True` из-за watchdog; `fatal_error=True` оставить только детерминированному HTTP (`server.py:5442`). В `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` для исчерпанного бюджета (`MAX_TOTAL_SPAWNS=1`) утверждать `exit_reason=<фаза>` в строке `O-EXIT/v1`, а не только подстроку фазы в логе и HTTP 502.

2. ПОЛНОТА: VERDICT=PASS
   WHY=Матрица AC-001..AC-024 и AC-026 закрыта автотестами и зелёным L2; AC-025 / VER-006 / VER-007 законно `DEFERRED_L3` до ACCEPT. Промах `exit_reason` — неверная метка уже реализованной ветки исчерпанного watchdog, а не отсутствующий сценарий. Исключение stall для живого `task` есть на JSON `Run` (`server.py:5302`, `:5343`, `:5395-5399`); объём RW-003 этим путём и ограничен.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Serve по умолчанию выключен (`auto` + `REALTIME_SERVE_ENABLED` только при boolean true). Новых runtime-зависимостей нет, stdlib Python 3.14. Дефолт `OPENCODE_CONFIG_CONTENT` (`server.py:513-516`) уже содержит `baseURL` georouter `127.0.0.1:10830`; `_serve_env` перезаписывает только ключ `permission` (`server.py:1869-1872`). `lsof`/`ps` на целевой машине есть (факт-карта). Память короткоживущего serve укладывается в оценку HL-ENV. Живой выкат на `:9883` остаётся лестницей H0..H9 после ACCEPT.

4. РИСКИ: VERDICT=FAIL
   WHY=Оракул `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` зелёный на L2, потому что проверяет HTTP 502, счётчик спавнов и наличие имени фазы в логе (`opencode run watchdog:` / `state=`). Строка `O-EXIT/v1` при этом `exit_reason=provider_fatal` (`execution-evidence.md:3470`, `:3482`, `:3494`). Оператор не отличает watchdog от фатального отказа провайдера. DSH ходит со `stream:true` (F-35), видимый Think этот JSON-путь не рисует; публичный non-stream и обязательное поле выхода REQ-016 всё равно ломаются. Полный сьют L2 зелёный (VER-001/002/003/003b/005, AC-023, rc=0); ранний лог кодера `1 failed, 465 passed` перекрыт clean-room 466 passed. RED на `origin/dev` (rc=1, 93 failed) — доказательство red→green, не дефект кандидата.
   СОВЕТЫ (при FAIL): Те же правки, что в КОРРЕКТНОСТЬ: классифицировать три фазы watchdog в `exit_reason` JSON-пути и закрепить это утверждением на строке `O-EXIT/v1`, а не на любой подстроке лога.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий `opencode serve` на запрос с откатом на `run` до барьера доставки — требуемый вариант A1/гибрид (RC-1 не закрывается упрочнением только `opencode run`). Объём в одном `server.py` задан конвертом из трёх файлов. Переписывания функции без необходимости нет. Таблица `FALLBACK_DECISION_TABLE` декларативна; переходы делают ветки, и это не раздувание ради раздувания.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff ровно в трёх разрешённых файлах. Замороженные срезы `_run_env`, `_stream_google_sse`, `_execute_google_once` совпали (VER-004, `google_direct_unchanged=True`). Публичные маршруты, порт `:9883` и форма SSE сохранены; строки `[мост]` требуются REQ-004/005. Новых зависимостей вне stdlib нет. Ранний выход `--serve-helper` и импорт `zen_catalog` только в основной ветке соответствуют VER-004. Kill-switch — env и `dynamic_config.json`, как задано конвертом.

F-001
priority: blocking
criterion: КОРРЕКТНОСТЬ, РИСКИ
locations: bridges/opencode-zen-bridge/server.py:5488, bridges/opencode-zen-bridge/server.py:5507, bridges/opencode-zen-bridge/server.py:5228, bridges/opencode-zen-bridge/server.py:7516, bridges/opencode-zen-bridge/server.py:7518
rule: REQ-016 MUST, AC-021, AC-010, RW-003 («классифицировать причину выхода `first_event_timeout`, `first_token_timeout`, `stall_timeout`»)
evidence: В `Run._execute_once` блок `if watchdog_reason: rc = 1; fatal_error = True` (`server.py:5486-5488`) помечает любой watchdog как фатальную ошибку провайдера. Возврат включает `"fatal_error": fatal_error` и `"state": state` (`server.py:5505-5508`). `Run.execute` при исчерпанном бюджете делает `return out` (`server.py:5237`). `Handler._serve_json` выполняет `if out.get("fatal_error") and not tool_calls:` → `xs["exit_reason"] = "provider_fatal"` и `_error_payload("opencode provider error after partial output …")` (`server.py:7516-7527`). Clean-room: `exec cli failed rc=-15 state=first_event_timeout` затем `O-EXIT/v1 mode=json … status=502 exit_reason=provider_fatal … duration_s=0.77` (`execution-evidence.md:3468-3470`); `state=first_token_timeout` → `exit_reason=provider_fatal` duration_s=0.79 (`:3480-3482`); `state=stall_timeout` → `exit_reason=provider_fatal` duration_s=0.54 (`:3492-3494`). Ветка детерминированного HTTP `fatal_error = True` на `server.py:5442` — другой root cause и в этот блок не входит.
expected: На исчерпанном JSON `run` `exit_reason` равен имени фазы (`first_event_timeout` / `first_token_timeout` / `stall_timeout`), тело 502 называет эту фазу. `fatal_error=True` остаётся только у детерминированного HTTP провайдера.
verification: `OPENCODE_ZEN_BRIDGE_TRANSPORT=run`, `stream=false`, `MAX_TOTAL_SPAWNS=1`, молчащий CLI / служебное событие без токена / пауза после токена: строка `O-EXIT/v1` содержит `exit_reason=<фаза>`, в теле нет «provider error after partial output». Успешный повтор при `MAX_TOTAL_SPAWNS=2` по-прежнему `exit_reason=ok`.
test_gap: `test_c6_rw003_nonstream_json_run_execute_enforces_phase_watchdogs` должен утверждать `exit_reason=<фаза>` в `O-EXIT/v1`, а не только подстроку фазы где-либо в логе.

SUB Корректность/логика: FAIL — JSON run при исчерпанном watchdog пишет exit_reason=provider_fatal (server.py:5488, server.py:7518; REQ-016/AC-021; execution-evidence.md:3470)
SUB Корректность/граничные условия: PASS — потолок спавнов, deadline, client_gone, байтовые капы SSE/HTTP и запрет bool/отрицательных токенов зелёные на L2 (server.py:1580-1581, VER-001 rc=0)
SUB Корректность/обработка ошибок: FAIL — тот же F-001: клиентский JSON 502 подписан «provider error after partial output» вместо имени фазы (server.py:7518-7524; AC-010)
SUB Полнота/покрытие AC: PASS — AC-001..AC-024 и AC-026 зелёные в verification-traceability; AC-025/VER-006/VER-007 = DEFERRED_L3 (execution-evidence.md)
SUB Полнота/пропущенные ветки: PASS — stall-исключение живого task есть на JSON Run, как просил RW-003 (server.py:5343, server.py:5395-5399)
SUB Реализуемость/общее: PASS — serve выключен по умолчанию, stdlib, baseURL georouter сохраняется в дефолтном OPENCODE_CONFIG_CONTENT (server.py:513-516, server.py:1871)
SUB Риски/безопасность: PASS — пароль serve через secrets.token_hex, allowlist env, маскирование Bearer/пароля/proxy, lease 0700; оракулы секретов в зелёном VER-005
SUB Риски/данные: PASS — OPENCODE_DB=:memory:, usage только неотрицательный int, запись в opencode.db отсутствует (server.py:1876, FU-002)
SUB Риски/прод: FAIL — тот же F-001: O-EXIT исчерпанного JSON run фиксирует provider_fatal (execution-evidence.md:3470, :3482, :3494; server.py:7518)
SUB Риски/regression red→green: PASS — L2-RED-sensitivity rc=1 на origin/dev (93 failed), кандидат VER-005 87 passed и VER-001 466 passed (code-gate.json)
SUB Риски/Full Suite (L2): PASS — VER-001/002/003/003b/005 и AC-023 rc=0, 466 passed (execution-evidence.md, l2-green-ver001-pytest.log)
SUB Риски/scope-diff: PASS — ровно 3 файла конверта, frozen sha256 совпали, google_direct_unchanged=True (code-gate.json)
SUB Альтернативы/общее: PASS — транспорт A1 с откатом на run до барьера доставки требуется RC-1; дробление модуля конверт запрещает
SUB Соответствие контексту/общее: PASS — публичный HTTP/SSE и :9883 сохранены, чужих путей нет, helper-ветка соответствует VER-004 (server.py, scope-and-contracts REQ-002)

ОБЩИЙ ВЕРДИКТ: NEEDS WORK
