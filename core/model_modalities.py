"""SSOT для модальностей моделей (текст, изображения) шлюза и фасада."""

from __future__ import annotations

import os
from typing import Any, Mapping

MULTIMODAL_MODELS: tuple[str, ...] = (
    "gpt-6.1-sol",
    "gemini-4-argon",
    "gemini-4-carbon",
    "gemini-4-hydrogen",
    "gemini-3.8-flash",
)


def supports_images(model_entry: Any = None, model_id: str = "") -> bool:
    """Проверяет, поддерживает ли модель обработку изображений.

    Поддерживает dict, объект или model_id:
    - наличие 'image' в поле 'input' (case-insensitive)
    - ИЛИ совпадение model_id (или префикса) с MULTIMODAL_MODELS
    """
    raw = None
    if isinstance(model_entry, dict):
        raw = model_entry.get("input")
        if not model_id and "id" in model_entry:
            model_id = str(model_entry.get("id", ""))
    elif model_entry is not None:
        raw = getattr(model_entry, "input", None)
        if not model_id and hasattr(model_entry, "id"):
            model_id = str(getattr(model_entry, "id", ""))

    if isinstance(raw, (list, tuple, set, frozenset)):
        if any(str(item).strip().lower() == "image" for item in raw):
            return True

    mid = (model_id or "").strip().lower()
    if not mid:
        return False

    for base in MULTIMODAL_MODELS:
        if mid == base or mid.startswith(base + "-"):
            return True

    return False


def model_modalities(model_entry: Any = None, model_id: str = "") -> list[str]:
    """Возвращает ['text', 'image'], если модель поддерживает изображения, иначе ['text']."""
    return ["text", "image"] if supports_images(model_entry, model_id) else ["text"]
