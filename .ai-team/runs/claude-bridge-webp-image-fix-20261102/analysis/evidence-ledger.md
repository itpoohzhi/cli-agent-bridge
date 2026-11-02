# Сводный Evidence Ledger

| ID | Утверждение | Источник | Статус |
|---|---|---|---|
| E-01 | `_IMAGE_FORMATS` в `core/tool_emulation.py` содержит только PNG и JPEG | `core/tool_emulation.py:1366` | Подтверждено |
| E-02 | `_sniff_image_mime` в `core` проверяет только `startswith(magic)` | `core/tool_emulation.py:1380` | Подтверждено |
| E-03 | Скриншот DSH сохранен как RIFF/WebP (920x392) и вызвал HTTP 400 `unsupported_image_type` | `claude-p-bridge/logs/bridge.err:2026-11-02T14:46:59Z`, `/Users/aazhiry1/.dsh/attachments/v1/objects/5e/5e568ee7f2a94d293ac0ef92b78111294238ee7cb4d73e460b66bf94a0604c0e` | Подтверждено |
| E-04 | В корневом `server.py` `KNOWN_IMAGE_MIMES` уже содержит 4 формата (PNG, JPEG, GIF, WebP) | `server.py:464` | Подтверждено |
| E-05 | В `bridges/opencode-zen-bridge/server.py:1751` маркеры не содержат `quota exhausted` | `bridges/opencode-zen-bridge/server.py:1751` | Подтверждено |
| E-06 | `Request quota exhausted.` в DSH вызвал терминальный отказ вместо ротации прокси | Сессия DSH 2026-11-02 18:00, скриншот пользователя | Подтверждено |
