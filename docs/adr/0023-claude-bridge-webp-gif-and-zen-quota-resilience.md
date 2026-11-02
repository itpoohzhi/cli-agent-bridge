# 0023 — Поддержка WebP/GIF в ядре и отказоустойчивость ротации квот OpenCode Zen

## Status
Accepted / Approved, 2026-11-02.

## Context
Пользователи DeepSeek Harness прикрепляют изображения со скриншотами macOS в формате WebP, что приводило к ошибке 400 `unsupported_image_type` на модели `Claude Opus 5.5` из-за ограничения `_IMAGE_FORMATS` в `core/tool_emulation.py`. Последующая попытка продолжить диалог на `MiMo-V2.6-Flash (Zen) Max` завершалась терминальным сбоем `Request quota exhausted. QUOTA` из-за отсутствия маркера `quota exhausted` в предикате `_is_free_quota_error` моста `opencode-zen-bridge`.

## Decision
1. В `core/tool_emulation.py` расширить `_IMAGE_FORMATS` и добавить поддержку форматов `image/gif` и `image/webp`. В `_sniff_image_mime` реализовать строгую двухточечную проверку заголовков `RIFF` и `WEBP` (`data[:4] == b"RIFF" and data[8:12] == b"WEBP"`).
2. В `bridges/opencode-zen-bridge/server.py` расширить кортеж маркеров квоты в `_is_free_quota_error` фразами `"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"`.
3. Добавить регрессионные тесты в `tests/test_claude_bridge.py`, `tests/test_images_strict.py` и `tests/test_opencode_zen_bridge.py`.

## Consequences
- Все четыре формата из `KNOWN_IMAGE_MIMES` (PNG, JPEG, GIF, WebP) единообразно валидируются на системном уровне ядра.
- Сбои исчерпания бесплатной квоты OpenCode Zen автоматически изолируются карантином текущего порта и ротируются без сбоя в пользовательской сессии.
