# Architecture Packet: Универсальная поддержка WebP/GIF в ядре и отказоустойчивость ротации квот OpenCode Zen

## Метаданные
- **Пакет:** `pol-architecture-packet/1`
- **Прогон:** `claude-bridge-webp-image-fix-20261102`
- **Дата:** 2026-11-02
- **Статус:** Revision r1 (направляется на Архитектурную панель Совета Тимлидов)
- **Целевые файлы:**
  - `/Users/aazhiry1/work/src/cli-agent-bridge/core/tool_emulation.py`
  - `/Users/aazhiry1/work/src/cli-agent-bridge/bridges/opencode-zen-bridge/server.py`
  - `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_claude_bridge.py`
  - `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_images_strict.py`
  - `/Users/aazhiry1/work/src/cli-agent-bridge/tests/test_opencode_zen_bridge.py`

---

## 1. Контекст и проблема

1. **Инцидент unsupported_image_type в DSH (17:46):**
   При передаче скриншота из буфера обмена macOS в сессии DSH с моделью `Claude Opus 5.5 (Claude Code)` запрос завершился ошибкой HTTP 400: `{"message":"invalid image input: unsupported_image_type","type":"invalid_request_error"}`.
   *RCA:* В `server.py` формат `image/webp` был объявлен в `KNOWN_IMAGE_MIMES`, но в универсальном слое `core/tool_emulation.py:1366` таблица `_IMAGE_FORMATS` осталась ограниченной только PNG и JPEG. Функция `_sniff_image_mime` не поддерживала двухпозиционную сигнатуру контейнера RIFF/WEBP (`RIFF....WEBP`).

2. **Инцидент Request quota exhausted в DSH (18:00):**
   При последующей попытке продолжить диалог через модель `MiMo-V2.6-Flash (Zen) Max` запрос завершился терминальной ошибкой: `This turn failed Request quota exhausted. QUOTA`.
   *RCA:* В `bridges/opencode-zen-bridge/server.py:1751` предикат `_is_free_quota_error` сопоставлял ошибки только с тремя фиксированными маркерами (`free usage limit reached`, `usage limit reached`, `provider.free-limit`). Строка ошибки `"Request quota exhausted."` от апстрима Zen не попала под эти маркеры, из-за чего прокси-порт не был помещен в карантин, а механизм `allow_quota_rotation()` не переключил запрос на следующий порт из пула.

---

## 2. Архитектурное решение и контракты

### 2.1. Доработка универсального ядра `core/tool_emulation.py`
1. **Расширение `_IMAGE_FORMATS`:**
   ```python
   _IMAGE_FORMATS = (
       ("image/png", b"\x89PNG\r\n\x1a\n", "png"),
       ("image/jpeg", b"\xff\xd8\xff", "jpg"),
       ("image/gif", b"GIF8", "gif"),
       ("image/webp", b"RIFF", "webp"),
   )
   ```
2. **Строгий сигнатурный анализ в `_sniff_image_mime(data: bytes) -> str`:**
   - Для PNG: `data.startswith(b"\x89PNG\r\n\x1a\n") -> "image/png"`
   - Для JPEG: `data.startswith(b"\xff\xd8\xff") -> "image/jpeg"`
   - Для GIF: `data.startswith(b"GIF87a") or data.startswith(b"GIF89a") -> "image/gif"`
   - Для WebP: `len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP" -> "image/webp"`
   - Иначе: возвращает пустую строку `""` (сигнатура неизвестна/не поддерживается).
3. **Безопасность и лимиты:**
   - Сохраняются строгие проверки `extract_data_url_images`: лимит на размер одного файла (`max_image_bytes`), суммарный размер (`max_total_bytes`), валидация base64 (`validate=True`), запрет внешних ссылок и `file://`.
   - Имена файлов генерируются безопасно: `image_{idx}.webp`, `image_{idx}.gif`.

### 2.2. Доработка отказоустойчивости `bridges/opencode-zen-bridge/server.py`
1. **Расширение маркеров квоты в `_is_free_quota_error`:**
   ```python
   def _is_free_quota_error(err: object) -> bool:
       """Распознать исчерпанную квоту по типу или тексту ошибки провайдера."""
       if isinstance(err, dict):
           if err.get("type") == "provider.free-limit":
               return True
           message = str(err.get("message") or err).lower()
       elif isinstance(err, str):
           message = err.lower()
       else:
           return False
       return any(
           marker in message
           for marker in (
               "free usage limit reached",
               "usage limit reached",
               "provider.free-limit",
               "quota exhausted",
               "request quota exhausted",
               "subscription quota exhausted",
           )
       )
   ```
2. **Поведение при срабатывании:**
   - Ошибка идентифицируется как исчерпание квоты на текущем прокси.
   - Порт отправляется в карантин на `PROXY_QUOTA_COOLDOWN_S` через `_quarantine_proxy`.
   - Запрос прозрачно переключается на следующий свободный прокси-порт через `allow_quota_rotation()`.

---

## 3. Матрица верификации (Verification Surface)
- `VER-001`: `extract_data_url_images` успешно парсит и валидирует data URL с WebP (`RIFF....WEBP`).
- `VER-002`: `extract_data_url_images` успешно парсит и валидирует data URL с GIF (`GIF89a` и `GIF87a`).
- `VER-003`: `extract_data_url_images` отклоняет `RIFF....WAVE` с ошибкой `unsupported_image_type`.
- `VER-004`: `test_claude_bridge.py` проверяет сквозную материализацию WebP во временный каталог (0700/0600) и передачу `--tools "Read"` / `--add-dir`.
- `VER-005`: `test_is_free_quota_error` возвращает `True` для `"Request quota exhausted."` и `"Subscription quota exhausted."`.
- `VER-006`: `test_serve_quota_rotations_can_exceed_base_spawn_limit` подтверждает автоматическую ротацию прокси при получении `"Request quota exhausted."`.
- `VER-007`: Полный регрессионный прогон существующих тестов `tests/test_images_strict.py`, `tests/test_claude_bridge.py`, `tests/test_opencode_zen_bridge.py`.
