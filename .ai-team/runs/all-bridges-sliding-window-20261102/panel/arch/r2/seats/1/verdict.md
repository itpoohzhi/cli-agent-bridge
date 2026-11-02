PANEL-NONCE: 8ea63032c8f7aede
ARTIFACT-SHA256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

AGREE RW-008 — проверил: bridges/opencode-zen-bridge/server.py:436,1611-1648 — дедлайн запроса считается как `attempts.deadline`, выведенный из `_zen_total_timeout`, то есть это статический настенный предел. План (AD-003) делает настраиваемым только `STALL_TIMEOUT_S` и этот предел не затрагивает. Инвариант скользящего окна по AGENTS.md не доказан.

AGREE RW-009 — проверил: bridges/claude-p-bridge/server.py:604 — `run.q.get(timeout=POLL_INTERVAL_S)` блокирует цикл на 1 с по умолчанию (:186). Если `check()` из AD-001 опрашивает ОС-процессы синхронно в этом же цикле, он добавляет задержку к выдаче SSE. План не требует троттлинга по времени и не задаёт бюджет задержки, поэтому проблема остаётся открытой.

AGREE RW-010 — проверил: у VER-001..VER-005 в плане нет теста, который доказывал бы основной результат. Нет теста скользящего окна (сброс таймера на чанках), нет теста `child_exited` без ложного 504, нет теста, что значение `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S` реально меняет поведение. Дополнительно: bridges/opencode-zen-bridge/server.py:1946 уже читает `OPENCODE_ZEN_BRIDGE_STALL_TIMEOUT_S`, значит EVD-002 устарел, а VER-004 проверяет уже существующее поведение.

AGREE RW-011 — проверил: `ls tests/` не находит `tests/test_claude_p_watchdog.py`. Есть только `test_claude_bridge.py`, `test_opencode_zen_bridge.py`, `test_stream_timeout_config.py`. Команды подтверждения AD-001, AD-002 и VER-001, VER-002, VER-004 не могут дать exit 0, поэтому решения в статусе APPROVED не подтверждены. Блокер снимается только созданием и прогоном этих тестов.

AGREE RW-012 — проверил: `grep` по bridges/claude-p-bridge/server.py не находит `AdaptiveTimeoutController`, `_read_dsh_env_file` и `_ALLOWED_SETTINGS_KEYS`. В server.py нет `BRIDGE_CLIENT_WRITE_TIMEOUT_S`, а `parse_live_write_timeout` (:394-406) читает только `DROID_BRIDGE_LIVE_WRITE_TIMEOUT_S`. Реализации в рабочем дереве нет, а `ASM-001..004` помечены VALIDATED и подкреплены лишь EVD-001..004, которые описывают исходное состояние, а не результат.

AGREE RW-013 — проверил: `parse_live_write_timeout` (server.py:394-406) и `AdaptiveTimeoutController` — потребители, которых план в `ASM-002` не разделяет. Вывод "whitelist полностью предотвращает утечку" непроверяем, потому что план не определяет, кто вызывает `_read_dsh_env_file`. Нет проверки того, что локальный dict не попадает в `child_env` через `{**env}` и `os.environ.copy()`. Нет и негативного теста, что ключи `*_KEY` отсекаются.

AMEND RW-014 — priority=BLOCKER-OPINION→MAJOR; fix=вынести интеграцию вотчдога в агент-агностический слой core/, а `claude-p-bridge` оставить тонким адаптером, который только вызывает общий хелпер — причина: AGENTS.md п.5 запрещает общую логику в адаптере, а bridges/claude-p-bridge/server.py:604 задаёт именно такое место вызова.

VERDICT: NEEDS WORK
