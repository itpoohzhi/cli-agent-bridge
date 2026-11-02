PANEL-NONCE: a28c2b38dfb81f22
ARTIFACT-SHA256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1
PANEL-NONCE: a28c2b38dfb81f22
ARTIFACT-SHA256: 8425114cd2bef4c3cefc42daa7a33de1d7caad86d1b73381e7e322550ea414b1

- DISPUTE RW-014 — контр-evidence: `core/watchdog.py:359` и `core/watchdog.py:515` (`AdaptiveTimeoutController` и алиас `TurnTimeoutController` живут в общем `core/`). Контроллер уже подключается на уровне хэндлера или адаптера в `bridges/agy-bridge/server.py:5202`, `core/turn_session_manager.py:1291` и `adapters/muse_adapter.py:65`, а в `server.py:5030` он создан с `watchdog_enabled=False`. Логика вотчдога не дублируется и находится в ядре, а точка вызова `check()` и `close()` в цикле чтения у каждого моста своя, потому что у каждого свой цикл. Тот же приём принят в agy-bridge. Вынос в общий враппер увеличил бы дифф без выигрыша, а откат уже есть через `CLAUDE_P_BRIDGE_WATCHDOG_ENABLED=0`.
- AMEND RW-013 — priority=MAJOR (не BLOCKER); fix=в AD-002 перечислить `_ALLOWED_SETTINGS_KEYS` литералом (только `*_TIMEOUT_S`/`*_INTERVAL_S`, deny-by-default) и убрать слова «полностью предотвращает» из ASM-002; добавить в VER-002 ассерт, что `child_env` и `os.environ` не содержат ни одного ключа вне whitelist — причина: `bridges/agy-bridge/server.py:78` (секреты уже подкладываются в процесс start.sh из `~/.dsh/.env` отдельно от настроек). Реальная граница риска — что именно попадает в `child_env`, а не само чтение файла. Замечание верно: whitelist задаёт, что читаем, но не что отдаём потомкам, а в артефакте список ключей не определён.

VERDICT: NEEDS WORK
