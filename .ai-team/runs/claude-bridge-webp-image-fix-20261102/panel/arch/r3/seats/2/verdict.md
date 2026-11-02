PANEL-NONCE: eb55f899f5e907e7
ARTIFACT-SHA256: a63c0fc62f291f23726fcd23dd621d2a9bb658e2fc95dccc5ded54b1367e1707

DISPUTE RW-008 — контр-evidence: fleet.json:103-111,344-361; server.py:465,1492-1499,6442-6503; bridges/claude-p-bridge/server.py:914-919 — в хабе `server.py` поддержка `image/webp` и `image/gif` уже реализована (`KNOWN_IMAGE_MIMES` и `_sniff_image`), а запросы к `claude-opus-5-5` маршрутизируются через `PassthroughAdapter` на шаге `(8a)` (`server.py:6486`) до вызова `_collect_images` (`server.py:6597`) напрямую в `bridges/claude-p-bridge/server.py:914-919`, который вызывает `core/tool_emulation.py:1388` (`extract_data_url_images`) и формирует точный текст ошибки из инцидента (`{"message":"invalid image input: unsupported_image_type","type":"invalid_request_error"}`).
AGREE RW-010 — проверил: bridges/opencode-zen-bridge/server.py:1150-1166,1255-1260,2476-2498,7620-7622,9219-9222 — вызов `_is_free_quota_error(err)` в обоих циклах (`_run_serve_stream_attempts` на строке 7620 и `_serve_json_serve` на строке 9219) находится строго внутри ветки `if result.get("transient_error"):`, тогда как `_is_transient_stream_error` (строки 1255-1260) для статусов `400/401/403/404/422` возвращает `False`, а для прочих кодов вне `(None, 0, 408, 429, >=500)` (например, HTTP `402 Payment Required`) проверяет `_TRANSIENT_ERROR_MARKERS` (строки 1151-1166), где нет маркеров квоты и вызова `_is_free_quota_error`.

### Позиция РЕАЛИСТА по итогам D2

1. **По инциденту WebP (`RW-008` — отклонено):**
   Цепочка вызова однозначно подтверждается кодом: хаб `server.py` уже умеет распознавать `RIFF....WEBP` (`server.py:1492-1499`), а для `claude-opus-5-5` работает в режиме `passthrough` (`fleet.json:103-111, 344-361`), передавая сырой запрос в `bridges/claude-p-bridge/server.py:915`. Правка `core/tool_emulation.py:1366-1385` минимальна и закрывает проблему в единственной реальной точке отказа.

2. **По ротации квот OpenCode Zen (`RW-010` — поддержано):**
   С точки зрения эксплуатационной надёжности и минимальности диффа в пакете упущена связка между `_is_free_quota_error` и `_is_transient_stream_error`. Чтобы новые маркеры (`"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"`) гарантированно приводили к карантину прокси и `allow_quota_rotation()` независимо от HTTP-кода апстрима (`402`, `403`, `400`, `429` или `None`), достаточно однострочной доработки в пакете: учитывать `_is_free_quota_error(ev)` в `_is_transient_stream_error` (`bridges/opencode-zen-bridge/server.py:1255`) либо проверять `if result.get("transient_error") or _is_free_quota_error(err):` на строках `7620` и `9219` (и покрыть этот случай в `VER-006`).

VERDICT: NEEDS WORK
