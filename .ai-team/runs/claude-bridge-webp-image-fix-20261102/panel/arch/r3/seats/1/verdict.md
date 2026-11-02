PANEL-NONCE: d914d92c0195f942
ARTIFACT-SHA256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707
AGREE RW-008 — проверил: server.py:6597, server.py:1563, server.py:1583 — хаб использует отдельный `_collect_images` с проверкой `max_types`; расширение `core/tool_emulation.py` этот допуск не меняет, а точка входа инцидента пакетом не подтверждена.
AGREE RW-010 — проверил: bridges/opencode-zen-bridge/server.py:1255, bridges/opencode-zen-bridge/server.py:7620, bridges/opencode-zen-bridge/server.py:9219 — статусы 400/401/403/404/422 дают `transient_error=False`; обе ветки распознавания квоты находятся внутри проверки transient, поэтому новый маркер сам по себе ротацию не гарантирует.
VERDICT: NEEDS WORK
