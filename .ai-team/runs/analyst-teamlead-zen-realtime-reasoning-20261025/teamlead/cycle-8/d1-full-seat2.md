PANEL-NONCE: 10a8d5bac8d7ca67
ARTIFACT-SHA256: 1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8
Канон прочитан: AGENTS.md, 429 строк

AMEND F-001 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:3355, bridges/opencode-zen-bridge/server.py:3371, bridges/opencode-zen-bridge/server.py:3885, bridges/opencode-zen-bridge/server.py:3893; fix=окно 0.15 с оставить как задано в FU-001; поздний второй native-вызов и пустой assistantMessageID вынести в follow-up — причина: RECHECK `server.py:3355` — дочитывание того же шага; бриф FU-001 задаёт это окно; `test_c8_fu001` зелёный в L2
NEW: bridges/opencode-zen-bridge/server.py:3355
ARG: visionary/R1 «FU-001 (все native-вызовы шага того же assistantMessageID, без следующего шага) ... закрыты тестами из пакета»

AMEND F-002 — priority=non-blocking; locations=bridges/opencode-zen-bridge/server.py:1580, bridges/opencode-zen-bridge/server.py:3580; fix=общий байтовый бюджет очереди оставить follow-up; предел 4096 объектов и 1 МиБ на строку сохраняет границу читателя, постановка в очередь при Full ждёт — причина: RECHECK `server.py:1580` — потолок строки, а не заранее выделенный буфер
NEW: bridges/opencode-zen-bridge/server.py:1580

AMEND F-004 — priority=non-blocking; locations=bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:881, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2423, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2754, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2825, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:2983, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3277, bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:3404; fix=сохранить unittest.TestCase: VER-002 (`unittest discover`) исполняет этот модуль, соседний `test_step_interruption.py` уже на TestCase — причина: RECHECK `test_realtime_reasoning.py:411`
NEW: bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py:411
ARG: visionary/R1 «Стиль нового тестового модуля следует существующему unittest-контуру моста при ограничении 0 внешних зависимостей»

F-003 остаётся blocking. Повторная проверка: `Run._execute_once` при дедлайне после резерва возвращает `state="timeout"` и `attempt_done(False, False)` (`server.py:5437-5454`); `_serve_json` принимает в ранний выход только `launcher_missing` / `spawn_failed` / `client_gone` (`server.py:7749-7765`), фазовые watchdog — только `first_event_timeout` / `first_token_timeout` / `stall_timeout` (`server.py:7821-7840`), пустой текст записывает `exit_reason=upstream_failed` (`server.py:7939-7942`). В `l2-green-ver002-unittest.log` сценарий FU-002 (JSON) даёт `total_spawns=0`, `duration_s=0.09`, `exit_reason=upstream_failed`.

1. КОРРЕКТНОСТЬ: VERDICT=FAIL
   WHY=RW-001 (повтор serve после раннего 429/503 без токенов и запрет run), RW-002 (непарный суррогат → `ServeProtocolError`) и обе serve-ветки RW-003 (локальный timeout нейтрален для breaker) подтверждены кодом и L2. В JSON-пути legacy общий `state="timeout"` до spawn теряет точную причину и становится `upstream_failed` — F-003 (`server.py:5437`, `server.py:7749`, `server.py:7939`; лог VER-002).
   СОВЕТЫ (при FAIL): в `_serve_json` обработать `state="timeout"` до ветки пустого content; сохранить HTTP 502, `attempt_done(False, False)` и возврат резерва; в оракуле FU-002 проверить одну строку O-EXIT с `exit_reason=timeout`, `total_spawns=0` и нулевой прирост отказов breaker.

2. ПОЛНОТА: VERDICT=PASS
   WHY=FU-001 закрыт для native-вызовов того же `assistantMessageID` внутри окна 0.15 с (`server.py:3355`, `test_c8_fu001`). Поздний вызов и пустой ID — non-blocking F-001. Матрица REQ-001..REQ-020 и AC-001..AC-026 на кандидате закрыта L2; REQ-019 / VER-006 / VER-007 законно DEFERRED_L3 до ACCEPT.

3. РЕАЛИЗУЕМОСТЬ: VERDICT=PASS
   WHY=Новых runtime-зависимостей нет (`dependencies = []`). Короткоживущий `opencode serve` v2.1.2, lease 0700, killpg, kill-switch и fallback на `run` до барьера доставки подтверждены L2. Очередь SSE ограничена 4096 объектами, строка — 1 МиБ (`server.py:1580`); байтовый потолок всего ответа — non-blocking F-002. Лестница H0..H9 остаётся после ACCEPT.

4. РИСКИ: VERDICT=PASS
   WHY=Clean-room L2: VER-001..VER-005 и AC-023 с rc=0, 478 passed; RED AC-026 на origin/dev — AssertionError «1 < 5»; VER-004 — 0 ошибок basedpyright; ровно 3 файла конверта; frozen `_run_env` / Google-direct совпали. Пароль serve, allowlist, `:memory:`, fail-closed 401/403/400/404/422 и маскирование `_error_payload` на месте. F-003 меняет подпись уже нейтрального для breaker исхода при HTTP 502; после правки подписи нужен повтор L2.

5. АЛЬТЕРНАТИВЫ: VERDICT=PASS
   WHY=Короткоживущий serve на попытку с откатом на `run` до барьера доставки закрывает RC-1 и сохраняет ротацию IP. Общий демон ломает ротацию, прямой Zen HTTP получил 429. Цикл 8 — точечные RW-001..RW-003 и FU-001..FU-003, архитектура не переписывалась.

6. СООТВЕТСТВИЕ КОНТЕКСТУ: VERDICT=PASS
   WHY=Diff внутри `bridges/opencode-zen-bridge/` (ровно 3 файла), публичные `/health`, `/v1/models`, `/v1/chat/completions` и форма SSE сохранены, Google-direct побайтно неизменен. Новый модуль остаётся в unittest-контуре моста (F-004 non-blocking): VER-002 discover его исполняет. Пересчёт сида r106: `seed_hex=36998d6685fcfe25481966619a844e55f268be26c0559a66f6ac4d0de9b410d9` MATCH, SEED=`36998d66`; `ranked_order` по `rank_slots(полный seed_hex)` из `select_round_seats.py` MATCH манифесту r106 (grok-4.7-high, gpt-6.1-sol-high, gemini-4-argon-high, muse-wonder-full-1.0, claude-sonnet-5-5-high).

POSITIONS: 0/0
ANSWERS: 0/0
ОБЩИЙ ВЕРДИКТ: NEEDS WORK
