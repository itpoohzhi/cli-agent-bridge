PANEL-NONCE: a0d1ccfc7bb54b66
ARTIFACT-SHA256: 50eaf21d2d799b7469d428a6ba845ba4e8771643e10fc252c63e0be1d83914c0
DISPUTE RW-010 — контр-evidence: bridges/opencode-zen-bridge/server.py:335 — TIMEOUT_S настраивается через OPENCODE_ZEN_BRIDGE_TIMEOUT_S; min сохраняет конфигурируемый глобальный предел, прямо предусмотренный требованиями; отсутствие конфиг-объекта само по себе дефект не доказывает.
AGREE RW-011 — проверил: bridges/opencode-zen-bridge/server.py:5060 — начальный tool_event в serve не устанавливает first_token_at, поэтому активный tool может оборваться по TTFT; Run устанавливает его при tool_use/tool_call на строке 6838, стриминговый путь — на 8516. Семантика действительно расходится.
AGREE RW-012 — проверил: bridges/opencode-zen-bridge/server.py:413 — при отсутствии callID/id ключом становится имя инструмента; воспроизвёл running/bash → running/bash → completed/bash: активность False, хотя второй вызов ещё исполняется. Для разных непустых ID коллапса нет.
VERDICT: NEEDS WORK
