# Единый согласованный документ судейства Совета Тимлидов по коду (`final-panel-verdict.md`) — Cycle 8

- **Run ID:** `analyst-teamlead-zen-realtime-reasoning-20261025`
- **Проверяемый артефакт:** `.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/teamlead/package.md` (`sha256=1cb20e1b18d6a48062fd61f800051ee19c65200e6b0fc1a272a41ec2651cd5f8`)
- **Раунд R1 (`panel/council/r99`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r99/panel-proof.json sha256=dbeb8263cdcdb898348c5c4306cdb98e6da5693d6d3cf6a67ff118f5050e7de9 verify_panel_proof exit=0`
- **Раунд D1 (`panel/council/r106`):** `PANEL PROOF: /Users/aazhiry1/tmp/cli-agent-bridge/zen-realtime-reasoning/.ai-team/runs/analyst-teamlead-zen-realtime-reasoning-20261025/panel/council/r106/panel-proof.json sha256=f17dff442239ac621f908e3ded11e59185ccca00c67e650defd49b6e699f5554 verify_panel_proof exit=0`
- **Итоговый вердикт Совета Тимлидов:** **NEEDS WORK (Класс A — `2` согласованных первичных блокера `RW-001..RW-002` и `2` согласованных non-blocking `FU-001..FU-002`, `0` открытых `CONFLICT`)**

---

## Раздел А. Согласованные блокеры («что не так»)

Все `2` первичных блокера подтверждены большинством/единогласно после механического `RECHECK` (`recheck-r1.md`) и раунда дебатов `D1` (`panel/council/r106`):

- **`F-001` → `RW-001`** (`status=AGREED`, `outcome=blocking`, критерий `КОРРЕКТНОСТЬ`, локация `bridges/opencode-zen-bridge/server.py` `server.py:3355,3371,3885,3893`, правило `REQ-011, REQ-014, feature.md §2, §5`): В `_drain_serve_step_usage` (`server.py:3355-3398`, `:3885-3905`) расширить окно дочитывания завершения инструментального шага до `min(1.0, max(0.0, deadline - time.monotonic()))`, принимать дополнительные `session.tool.called`/`failed`/`success` того же `session_id`, когда `ev_msg_id == assistant_msg_id` либо когда `assistant_msg_id` или `ev_msg_id` пусты (отсекая только события с непустым отличающимся `ev_msg_id`), и различать подтверждённый `session.step.ended` и истечение окна дочитывания без подтверждения конца шага (при неподтверждённом конце шага после истечения окна возбуждать `ServeProtocolError("incomplete tool step without step.ended")`, чтобы не возвращать неполный пакет native-вызовов как успешный ответ).
- **`F-003` → `RW-002`** (`status=AGREED`, `outcome=blocking`, критерий `КОРРЕКТНОСТЬ`, локация `bridges/opencode-zen-bridge/server.py` `server.py:5438,7749,7821,7942`, правило `REQ-016 / AC-021, O-EXIT/v1`): В `Handler._serve_json` (`server.py:7749-7840`) обрабатывать `result.get("state") == "timeout"` терминально до ветки пустого текста (`upstream_failed` на `server.py:7942`): записывать `exit_reason = "timeout"`, возвращать прежний HTTP `502` с нейтральным учётом Circuit Breaker (`attempts.attempt_done(False, False)`, `0` инкрементов отказов).

---

## Раздел Б. План исправлений («что конкретно править до ACCEPT / PASS»)

Взаимно-однозначное соответствие `1 первичный блокер из Раздела А → 1 инструкция RW-NNN + 1 критерий приёмки` (противоречащих пунктов нет):

- **`RW-001` (`source_findings: ["F-001"]`, файл `bridges/opencode-zen-bridge/server.py`, строки `server.py:3355,3371,3885,3893`):** **Действие:** В `_drain_serve_step_usage` (`server.py:3355-3398`, `:3885-3905`) расширить окно дочитывания завершения инструментального шага до `min(1.0, max(0.0, deadline - time.monotonic()))`, принимать дополнительные `session.tool.called`/`failed`/`success` того же `session_id`, когда `ev_msg_id == assistant_msg_id` либо когда `assistant_msg_id` или `ev_msg_id` пусты (отсекая только события с непустым отличающимся `ev_msg_id`), и различать подтверждённый `session.step.ended` и истечение окна дочитывания без подтверждения конца шага (при неподтверждённом конце шага после истечения окна возбуждать `ServeProtocolError("incomplete tool step without step.ended")`, чтобы не возвращать неполный пакет native-вызовов как успешный ответ). **Критерий приёмки:** В SSE и JSON: (1) два native-вызова одного шага со вторым вызовом через `> 150 мс` (`200 мс`) и последующим `session.step.ended` доставляются полностью с точным `usage`, а события следующего `assistantMessageID` отсекаются; (2) дополнительные native-вызовы того же шага без `assistantMessageID` с последующим `session.step.ended` сохраняются; (3) при отсутствии `session.step.ended` до конца окна попытка не объявляется успешной с неполным набором.
- **`RW-002` (`source_findings: ["F-003"]`, файл `bridges/opencode-zen-bridge/server.py`, строки `server.py:5438,7749,7821,7942`):** **Действие:** В `Handler._serve_json` (`server.py:7749-7840`) обрабатывать `result.get("state") == "timeout"` терминально до ветки пустого текста (`upstream_failed` на `server.py:7942`): записывать `exit_reason = "timeout"`, возвращать прежний HTTP `502` с нейтральным учётом Circuit Breaker (`attempts.attempt_done(False, False)`, `0` инкрементов отказов). **Критерий приёмки:** При исчерпании локального дедлайна до legacy spawn (`state="timeout"`, сценарий FU-002 в JSON и SSE) в `O-EXIT/v1` записывается ровно одно событие с `exit_reason="timeout"`, `total_spawns=0`, `0` инкрементов отказов Circuit Breaker и возвращённым резервом `_RetryBudget`.

---

## Раздел В. Снятые и отклонённые находки (`excluded_findings`)

Отклонённых или снятых находок нет (`0`).

---

## Раздел Г. Неблокирующее и `Do-Not-Change`

### Неблокирующие улучшения (`non_blocking_followups`, `2` пункта `FU-001..FU-002`):
- **`F-002` → `FU-001`** (`status=AGREED`, `outcome=non-blocking`): Ввести в `_ServeSseStream` (`server.py:1580, 3580-3595`) и цикле накопления ответа (`server.py:3850-3865`) явный байтовый бюджет очереди SSE-событий (`MAX_SERVE_QUEUE_BYTES = 16 * 1024 * 1024`) и накопленного текста/reasoning на попытку (`MAX_SERVE_ACCUMULATED_BYTES = 16 * 1024 * 1024`), чтобы при 6 слотах суммарная память гарантированно укладывалась в конверт `HL-ENV-01` (`<= 2 GiB`), а при превышении попытка останавливалась через `ServeProtocolError` с `cleanup()`. (Согласовано квалифицированным большинством 2/3 в D1 (`skeptic`, `realist`) через `AMEND F-002 -> priority=non-blocking`; реализуем заодно в этом же проходе с детерминированным unit-тестом.)
- **`F-004` → `FU-002`** (`status=AGREED`, `outcome=non-blocking`): Сохранить совместимость `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py` с замороженным оракулом `VER-002` (`python3 -m unittest discover -s tests -p 'test_*.py'`) и существующим `unittest`-контуром моста (`tests/test_step_interruption.py`). (Согласовано квалифицированным большинством 2/3 в D1 (`skeptic` `DISPUTE -> invalid`, `realist` `AMEND -> non-blocking: сохранить unittest.TestCase, чтобы VER-002 исполнял модуль`).)

### Ограничения `Do-Not-Change` при доработке (`Coder` `rework` Цикла 9):
- Разрешено изменять исключительно 3 файла кодера из `allowed_envelope_changes`: `bridges/opencode-zen-bridge/server.py`, `bridges/opencode-zen-bridge/tests/test_realtime_reasoning.py`, `bridges/opencode-zen-bridge/tests/test_step_interruption.py`.
- Запрещено изменять замороженные функции в `bridges/opencode-zen-bridge/server.py`: `def _run_env` (`sha256=1c51b28fcb83fcc0f4d8b5204c858e11ab5ac975bfe40dca4a0bf61978008e31`), `def _stream_google_sse` (`sha256=5914c9654c7345692dd55e84cfd3765e27406f63a3df85df30bc798bc1778de3`), `def _execute_google_once` (`sha256=88d794cc42be4878e8ab35b00e4668c427929db2dfd0f2bb4b717a63fd0c70d6`).
- Запрещено добавлять внешние runtime-зависимости вне стандартной библиотеки Python 3.14 (`dependencies = []` в `pyproject.toml`).
- Запрещено модифицировать `zen_catalog.py`, `start.sh`, `muse-bridge`, существующие тестовые модули вне конверта и `dynamic_config.json` в git.
