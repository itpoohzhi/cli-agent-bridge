# Open Questions

- **OQ-01 (МОЖНО ПРОДОЛЖИТЬ):** Поддерживает ли Claude Code CLI форматы WebP и GIF при чтении из staged-директории через инструмент `Read`?
  - *Допущение:* Claude CLI использует встроенный мультимодальный движок модели Anthropic Claude 3.5/3.7/Opus 5.5, поддерживающий PNG, JPEG, GIF, WebP согласно официальной документации Anthropic. Локальный инструмент `Read` передает бинарные файлы в контекст.
- **OQ-02 (МОЖНО ПРОДОЛЖИТЬ):** Требуется ли обновлять `fleet.json` для `claude-opus-5-5`?
  - *Допущение:* В `fleet.json` поле `image_limits.max_types` уже содержит все 4 формата (`image/png`, `image/jpeg`, `image/gif`, `image/webp`). Для модели `claude-opus-5-5` в `fleet.json` можно добавить `"image"` в `input: ["text", "image"]` и `"status": "confirmed"` для единообразия, хотя passthrough маршрутизирует запрос напрямую.
