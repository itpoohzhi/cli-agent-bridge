# Бриф для роли Coder: исправление поддержки WebP/GIF и ротации квот OpenCode Zen

## Контекст и архитектурное решение (ADR-0023 / Architecture Packet r2)
В шлюзе `cli-agent-bridge` обнаружены два критических дефекта:
1. `unsupported_image_type` (400 Bad Request) при передаче скриншотов macOS (формат WebP/RIFF) в Claude:
   - В `core/tool_emulation.py:1366` константа `_IMAGE_FORMATS` содержала только PNG и JPEG.
   - Метод `_sniff_image_mime` использовал только `data.startswith(magic)`, не способный валидировать составной контейнер WebP (байты `[:4] == b"RIFF"` и `[8:12] == b"WEBP"`).
2. Сбой `Request quota exhausted` в `opencode-zen-bridge` без переключения прокси:
   - В `bridges/opencode-zen-bridge/server.py:1255` проверка `_FATAL_STREAM_STATUSES` (куда входит HTTP 400) выполнялась ДО проверки ошибок квоты, из-за чего ошибка не классифицировалась как транзиентная и прокси не отправлялся в карантин.
   - В `_is_free_quota_error` отсутствовали маркеры `"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"`.

## Задачи реализации

### 1. `core/tool_emulation.py`
1. Обновить константу форматов изображений:
   Поддерживать 4 формата: PNG, JPEG, GIF, WebP:
   - PNG: `image/png`, магические байты `b"\x89PNG\r\n\x1a\n"`, расширение `png`
   - JPEG: `image/jpeg`, магические байты `b"\xff\xd8\xff"`, расширение `jpg`
   - GIF: `image/gif`, магические байты `GIF87a` / `GIF89a`, расширение `gif`
   - WebP: `image/webp`, контейнер RIFF (`data[:4] == b"RIFF"` и `data[8:12] == b"WEBP"`), расширение `webp`
   (Сохранить совместимость кортежа `_IMAGE_FORMATS` или предоставить `_SUPPORTED_IMAGE_MIMES` так, чтобы не ломался существующий код).
2. Обновить `_sniff_image_mime(data: bytes) -> str`:
   - Если `len(data) >= 8 and data.startswith(b"\x89PNG\r\n\x1a\n")`: вернуть `"image/png"`
   - Если `len(data) >= 3 and data.startswith(b"\xff\xd8\xff")`: вернуть `"image/jpeg"`
   - Если `len(data) >= 6 and (data.startswith(b"GIF87a") or data.startswith(b"GIF89a"))`: вернуть `"image/gif"`
   - Если `len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"`: вернуть `"image/webp"`
   - Иначе вернуть `""`.
3. В `extract_data_url_images`:
   - Убедиться, что для WebP и GIF корректно определяется расширение `webp` и `gif` и формируются файлы `image_N.webp` / `image_N.gif`.
   - Проверить строгую валидацию: при несовпадении заявленного MIME и sniffed MIME выбрасывать `ImageInputError("image_type_mismatch")`.
   - При невалидном формате выбрасывать `ImageInputError("unsupported_image_type")`.

### 2. `bridges/opencode-zen-bridge/server.py`
1. В `_is_free_quota_error(err)` (около строки 1741):
   - Добавить маркеры: `"quota exhausted"`, `"request quota exhausted"`, `"subscription quota exhausted"`.
2. В `_is_transient_stream_error(ev)` (около строки 1225):
   - ДО проверки `if status in _FATAL_STREAM_STATUSES:` проверять:
     ```python
     if _is_free_quota_error(ev):
         return True
     ```
     (Также проверить контейнеры/сообщения внутри `ev` через `_is_free_quota_error`).
   - Это гарантирует, что ошибка исчерпания квоты всегда распознается как транзиентная и вызовет карантин прокси и ротацию через `allow_quota_rotation`.

### 3. Тесты
1. В `tests/test_images_strict.py` (или `tests/test_claude_bridge.py`):
   - Добавить тесты на валидный WebP (`b"RIFF\x00\x00\x00\x00WEBPVP8 ..."`).
   - Добавить тесты на валидный GIF (`b"GIF89a..."`).
   - Добавить тест на отказ при инвалидном RIFF (например `b"RIFF\x00\x00\x00\x00WAVE..."` -> `unsupported_image_type`).
   - Добавить тест на `image_type_mismatch` (MIME `image/png`, а байты WebP).
   - Проверить сохранение расширений `image_1.webp` и `image_1.gif`.
2. В `tests/test_opencode_zen_bridge.py`:
   - Добавить тесты для `_is_free_quota_error` со строками `"Request quota exhausted."` и `"subscription quota exhausted"`.
   - Добавить тест, подтверждающий, что `_is_transient_stream_error` возвращает `True` при наличии текста ошибки квоты, даже если в событии статус 400.

## Требования к исполнению
1. Внеси изменения в `core/tool_emulation.py`, `bridges/opencode-zen-bridge/server.py` и файлы тестов.
2. Запусти тесты через `pytest tests/test_images_strict.py tests/test_opencode_zen_bridge.py tests/test_claude_bridge.py -v` и убедись, что все тесты проходят.
3. Выведи краткий структурированный отчёт о внесённых правках и результатах тестов.
