# Исследовательский план: Устранение дефектов unsupported_image_type (WebP/GIF) и незамеченного сбоя квоты (Request quota exhausted)

```text
РЕЖИМ | development
ЦЕЛЬ ИЗМЕНЕНИЯ | Поддержка форматов image/webp и image/gif в core/tool_emulation.py и claude-p-bridge; распознавание "quota exhausted" / "request quota exhausted" в opencode-zen-bridge для автоматического карантина и ротации прокси; 100% покрытие новыми L1/L2 тестами.
ЧТО МЕНЯЕТСЯ | core/tool_emulation.py (_IMAGE_FORMATS, _sniff_image_mime, extract_data_url_images), bridges/claude-p-bridge/server.py, bridges/opencode-zen-bridge/server.py (_is_free_quota_error), tests/test_claude_bridge.py, tests/test_images_strict.py, tests/test_opencode_zen_bridge.py.
ЧТО НЕЛЬЗЯ МЕНЯТЬ | OpenAI API-контракт /v1/chat/completions, вендорский код DSH/Claude CLI, логику strict_live парсинга, тайминги и политики безопасности (0700/0600).
ГРАНИЦА ВЛИЯНИЯ (гипотеза) | core/tool_emulation.py, bridges/claude-p-bridge/server.py, bridges/opencode-zen-bridge/server.py, callers extract_data_url_images, fleet.json, тесты мостов.
КРИТЕРИЙ ПРИЁМКИ | 1. Запрос с WebP data URL в claude-p-bridge и core валидируется, материализует image_N.webp и не бросает 400 unsupported_image_type.
                  2. Запрос с GIF data URL валидируется аналогично.
                  3. Ошибка "Request quota exhausted." в opencode-zen-bridge распознается как free quota error, прокси отправляется в карантин, запрос успешно ретраится на следующем порту.
                  4. Все юнит- и интеграционные тесты pytest зелёные.
                  5. ACCEPT обеих панелей Совета Тимлидов (архитектура и код).
ИСТОЧНИК ТРЕБОВАНИЯ | Инцидент в сессии DSH 2026-11-02 17:46 (unsupported_image_type) и 18:00 (Request quota exhausted. QUOTA).
NFR-ИСТОЧНИК | Hot-Path & HL-ENV: N/A (cold-path / admission path, T_budget ≤ 1 мс на валидацию сигнатуры).
```

## Вопросы и зоны обследования (INV-ID)
- INV-01: Контракты форматов изображений в `core/tool_emulation.py` vs `server.py` vs `fleet.json`.
- INV-02: Сигнатура и разбор WebP (RIFF/WEBP) и GIF (GIF87a/GIF89a).
- INV-03: Поведение `claude-p-bridge` при сохранении WebP/GIF во временную директорию (0700/0600) и передаче в Claude CLI (`--tools "Read"` / `--add-dir`).
- INV-04: Причины пропуска ошибок квоты `"Request quota exhausted."` в `_is_free_quota_error` моста `opencode-zen-bridge`.
- INV-05: Регрессионное покрытие тестами L1/L2.
