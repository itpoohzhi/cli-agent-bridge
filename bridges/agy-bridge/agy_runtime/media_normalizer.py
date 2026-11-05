"""Универсальная нормализация и очистка мультимодального медиа-контента (AD-002)."""

from __future__ import annotations

from typing import cast

_IMAGE_PART_TYPES = frozenset({"image_url", "image", "input_image"})
_IMAGE_PAYLOAD_KEYS = ("image_url", "image")
_MEDIA_PART_NAMES = (
    "input_audio",
    "audio",
    "video",
    "video_url",
    "file",
    "document",
    "inlineData",
    "inline_data",
    "fileData",
    "file_data",
)
_MEDIA_PART_TYPES = frozenset(name.lower() for name in _MEDIA_PART_NAMES)
_TEXT_PART_TYPES = frozenset({"text", "input_text", "output_text"})
_IMAGE_OMITTED = "[image omitted]"
_MEDIA_OMITTED = "[media omitted]"
_JSON_COPY_MAX_DEPTH = 32


def _lower_keys(part: dict[str, object]) -> dict[str, object]:
    """Копия part с ключами в нижнем регистре."""
    lowered: dict[str, object] = {}
    for key, value in part.items():
        lowered_key = str(key).lower()
        if lowered_key not in lowered:
            lowered[lowered_key] = value
    return lowered


def _classify_part(part: dict[str, object]) -> str:
    """'image' | 'media' | 'text' | 'unknown'; медиа определяется ДО чтения `text`."""
    lowered = _lower_keys(part)
    raw_kind = lowered.get("type")
    kind = raw_kind.strip().lower() if isinstance(raw_kind, str) else ""
    if kind in _IMAGE_PART_TYPES or any(
        lowered.get(key) is not None for key in _IMAGE_PAYLOAD_KEYS
    ):
        return "image"
    if kind in _MEDIA_PART_TYPES or any(
        lowered.get(key) is not None for key in _MEDIA_PART_TYPES
    ):
        return "media"
    text = lowered.get("text")
    only_text_keys = set(lowered) <= {"type", "text"}
    if kind in _TEXT_PART_TYPES and (
        isinstance(text, str) or (text is None and only_text_keys)
    ):
        return "text" if text or only_text_keys else "unknown"
    if not kind and isinstance(text, str):
        return "text" if text or only_text_keys else "unknown"
    return "unknown"


def _part_text(part: dict[str, object]) -> str:
    """Текст text-части."""
    value = _lower_keys(part).get("text")
    return value if isinstance(value, str) else ""


def _content_items(content: object) -> list[object]:
    """Части контента: list как есть, dict-content — одна часть, прочее — пусто."""
    if isinstance(content, list):
        return cast("list[object]", content)
    if isinstance(content, dict):
        return [content]
    return []


def _image_part_canonical(part: dict[str, object]) -> dict[str, object]:
    """Image-алиас в форме `image_url`."""
    lowered = _lower_keys(part)
    payload = lowered.get("image_url")
    if payload is None:
        payload = lowered.get("image")
    url: object = None
    if isinstance(payload, str):
        url = payload
    elif isinstance(payload, dict):
        url = cast("dict[str, object]", payload).get("url")
    return {"type": "image_url", "image_url": {"url": url}}


def _media_part_counts(messages: object) -> tuple[int, int]:
    """(image-частей, прочих media/неизвестных структурных частей) во всей истории."""
    images = 0
    other = 0
    if not isinstance(messages, list):
        return images, other
    for msg in cast("list[object]", messages):
        if not isinstance(msg, dict):
            continue
        for item in _content_items(cast("dict[str, object]", msg).get("content")):
            if not isinstance(item, dict):
                continue
            kind = _classify_part(cast("dict[str, object]", item))
            if kind == "image":
                images += 1
            elif kind != "text":
                other += 1
    return images, other


def _collect_image_parts_universal(
    messages: object,
) -> list[tuple[int, int, dict[str, object]]]:
    """Все image-части истории в форме `image_url`."""
    found: list[tuple[int, int, dict[str, object]]] = []
    if not isinstance(messages, list):
        return found
    number = 0
    for msg_index, msg in enumerate(cast("list[object]", messages)):
        if not isinstance(msg, dict):
            continue
        for item in _content_items(cast("dict[str, object]", msg).get("content")):
            if not isinstance(item, dict):
                continue
            part = cast("dict[str, object]", item)
            if _classify_part(part) == "image":
                number += 1
                found.append((msg_index, number, _image_part_canonical(part)))
    return found


def _json_copy(value: object, depth: int = 0) -> object:
    """Копия JSON-значения без разделяемых контейнеров."""
    if depth > _JSON_COPY_MAX_DEPTH:
        return None
    if isinstance(value, dict):
        return {
            str(k): _json_copy(v, depth + 1)
            for k, v in cast("dict[object, object]", value).items()
        }
    if isinstance(value, list):
        return [_json_copy(v, depth + 1) for v in cast("list[object]", value)]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _flatten_content_stripped(content: object) -> str:
    """Контент в безопасный текст без media."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    dropped = False
    for item in _content_items(content):
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict):
            part = cast("dict[str, object]", item)
            kind = _classify_part(part)
            if kind == "image":
                parts.append(_IMAGE_OMITTED)
            elif kind == "media":
                parts.append(_MEDIA_OMITTED)
            elif kind == "text":
                parts.append(_part_text(part))
            else:
                dropped = True
        elif isinstance(item, list):
            dropped = True
    if not parts and dropped:
        parts.append(_MEDIA_OMITTED)
    return "\n".join(p for p in parts if p)


def _strip_media_from_messages(messages: object) -> list[dict[str, object]]:
    """Новый список сообщений без media; вход не мутируется."""
    out: list[dict[str, object]] = []
    if not isinstance(messages, list):
        return out
    for msg in cast("list[object]", messages):
        if not isinstance(msg, dict):
            continue
        fresh: dict[str, object] = {}
        for key, value in cast("dict[object, object]", msg).items():
            if key == "content":
                fresh["content"] = _flatten_content_stripped(value)
            else:
                fresh[str(key)] = _json_copy(value)
        out.append(fresh)
    return out


def _universal_render_messages(messages: object) -> list[object]:
    """Копия истории для оптимистичной отправки: image — каноничные, прочее media — вон."""
    out: list[object] = []
    if not isinstance(messages, list):
        return out
    for msg in cast("list[object]", messages):
        if not isinstance(msg, dict):
            out.append(msg)
            continue
        src = cast("dict[str, object]", msg)
        fresh = dict(src)
        raw_content = src.get("content")
        if isinstance(raw_content, (list, dict)):
            items: list[object] = []
            for item in _content_items(src.get("content")):
                if isinstance(item, str):
                    items.append(item)
                elif isinstance(item, dict):
                    part = cast("dict[str, object]", item)
                    kind = _classify_part(part)
                    if kind == "image":
                        items.append(_image_part_canonical(part))
                    elif kind == "text":
                        items.append({"type": "text", "text": _part_text(part)})
            fresh["content"] = items
        out.append(fresh)
    return out
