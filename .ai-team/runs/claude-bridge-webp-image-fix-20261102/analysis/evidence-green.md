# Evidence: Зелёная шляпа (Контракты, NFR, варианты)

## [G-01] Контрактная дельта `core/tool_emulation.py`
1. Расширение таблицы форматов и расширений файлов:
```python
# (MIME, расширение файла, функция проверки сигнатуры)
_KNOWN_IMAGE_FORMATS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
}
```
2. Обновление функции `_sniff_image_mime(data: bytes) -> str`:
- PNG: `data.startswith(b"\x89PNG\r\n\x1a\n")`
- JPEG: `data.startswith(b"\xff\xd8\xff")`
- GIF: `data.startswith(b"GIF87a") or data.startswith(b"GIF89a")` (или `data[:4] == b"GIF8"`)
- WebP: `len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"`
3. Поддержка `image/webp` и `image/gif` в генерации имён файлов: `image_{index}.webp`, `image_{index}.gif`.

## [G-02] Контрактная дельта `bridges/opencode-zen-bridge/server.py`
Расширение кортежа маркеров в `_is_free_quota_error`:
```python
    return any(
        marker in message
        for marker in (
            "free usage limit reached",
            "usage limit reached",
            "provider.free-limit",
            "quota exhausted",
            "subscription quota exhausted",
            "request quota exhausted",
        )
    )
```

## [G-03] Варианты реализации
- **Вариант 1 (Системный, агент-агностический в core, Рекомендуемый):**
  Централизовать таблицу форматов и сниффер в `core/tool_emulation.py`. Синхронизировать `KNOWN_IMAGE_MIMES` в `server.py` и `core`. `claude-p-bridge` автоматически получает полную поддержку без ad-hoc логики. В `opencode-zen-bridge` обновить маркеры квоты.
- **Вариант 2 (Локальные заплатки в claude-p-bridge):**
  Переопределить функцию валидации только внутри `bridges/claude-p-bridge/server.py`.
  *Отказ по правилу AGENTS.md §5*: запрещено дублировать и разносить системную логику по адаптерам.
