# Evidence: Белая шляпа (As-Is факты)

## [W-01] Ограничение форматов в `core/tool_emulation.py:1366`
В `core/tool_emulation.py` строки 1366-1385:
```python
_IMAGE_FORMATS = (
    ("image/png", b"\x89PNG\r\n\x1a\n", "png"),
    ("image/jpeg", b"\xff\xd8\xff", "jpg"),
)

def _sniff_image_mime(data: bytes) -> str:
    """MIME по магическим байтам ('' — сигнатура неизвестна)."""
    for mime, magic, _ext in _IMAGE_FORMATS:
        if data.startswith(magic):
            return mime
    return ""
```
Факт: `_IMAGE_FORMATS` содержит только PNG и JPEG. Типы `image/webp` и `image/gif` отсутствуют.
Кроме того, `data.startswith(magic)` принципиально не может определить WebP, так как в WebP сигнатура `RIFF` идёт в байтах 0..3, размер файла в 4..7, а маркер `WEBP` — в байтах 8..11 (`data[:4] == b"RIFF" and data[8:12] == b"WEBP"`).

## [W-02] Рассогласование SSOT между `server.py` и `core/tool_emulation.py`
В `server.py` строки 459-474 и 1491-1498:
```python
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF8", "image/gif"),
)
KNOWN_IMAGE_MIMES = ("image/png", "image/jpeg", "image/gif", "image/webp")

def _sniff_image(data: bytes) -> str:
    """MIME по магическим байтам ('' — сигнатура неизвестна)."""
    for prefix, mime in IMAGE_SIGNATURES:
        if data.startswith(prefix):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""
```
Факт: Корневой `server.py` уже поддерживает `image/webp` и `image/gif`, а универсальное ядро `core/tool_emulation.py` не было синхронизировано. Вследствие этого `claude-p-bridge`, импортирующий `extract_data_url_images` из ядра, ломается при получении WebP и GIF.

## [W-03] Реальный инцидент в DeepSeek Harness
Файл вложения `/Users/aazhiry1/.dsh/attachments/v1/objects/5e/5e568ee7f2a94d293ac0ef92b78111294238ee7cb4d73e460b66bf94a0604c0e`:
`file` output: `RIFF (little-endian) data, Web/P image, VP8 encoding, 920x392`
В 17:46:59 HTTP POST в `claude-p-bridge` вернул 400:
`{"error": {"message": "invalid image input: unsupported_image_type", "type": "invalid_request_error"}}`.

## [W-04] Ограничение распознавания ошибок квоты в `bridges/opencode-zen-bridge/server.py:1741`
В `bridges/opencode-zen-bridge/server.py`:
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
        )
    )
```
Факт: Текст ошибки из логов и скриншота — `"Request quota exhausted."` (или `"Subscription quota exhausted."`).
Ни один из маркеров (`"free usage limit reached"`, `"usage limit reached"`, `"provider.free-limit"`) не содержит подстроку `"quota exhausted"`.
В результате `_is_free_quota_error` возвращает `False`, функция `_quarantine_proxy` не вызывается, а `allow_quota_rotation()` не разрешает переход на следующий порт пула прокси.
