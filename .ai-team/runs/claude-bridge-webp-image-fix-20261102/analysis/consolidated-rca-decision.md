# Консолидированное RCA-решение (Рекомендация панели)

## 1. Первопричина дефекта 1 (unsupported_image_type)
Рассинхронизация между `server.py` и ядром `core/tool_emulation.py`. В `server.py` форматы `image/webp` и `image/gif` были добавлены в список `KNOWN_IMAGE_MIMES`, но кортеж `_IMAGE_FORMATS` и функция `_sniff_image_mime` в `core/tool_emulation.py` остались с устаревшим ограничением только на PNG и JPEG. Мост `claude-p-bridge` использует функцию `extract_data_url_images` из ядра, что привело к отказу 400 при отправке WebP скриншотов из macOS / DSH.

## 2. Первопричина дефекта 2 (Request quota exhausted)
Функция `_is_free_quota_error` в `bridges/opencode-zen-bridge/server.py` проверяла только три узких маркера (`"free usage limit reached"`, `"usage limit reached"`, `"provider.free-limit"`). Реальный апстрим OpenCode Zen вернул сообщение `"Request quota exhausted."` без типа `provider.free-limit`, из-за чего ошибка была классифицирована как терминальная вместо ротации прокси.

## 3. Рекомендация Архитектору
Реализовать Вариант V1:
1. В `core/tool_emulation.py` расширить `_IMAGE_FORMATS` и `_sniff_image_mime` поддержкой `image/gif` (сигнатура `GIF8`) и `image/webp` (сигнатура `RIFF....WEBP`).
2. В `bridges/opencode-zen-bridge/server.py` расширить кортеж маркеров квоты в `_is_free_quota_error` подстроками `"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"`.
3. Добавить исчерпывающие L1/L2 тесты в `tests/test_claude_bridge.py`, `tests/test_images_strict.py` и `tests/test_opencode_zen_bridge.py`.
