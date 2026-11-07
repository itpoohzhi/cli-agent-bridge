from __future__ import annotations

from pathlib import Path
from typing import Any

DROID_MANIFEST = "droid.yaml"


def _load_droid_manifest(providers_dir: Path) -> dict[str, Any]:
    """YAML манифеста droid; нет PyYAML, файла или mapping — пустой dict."""
    try:
        import yaml  # type: ignore[import-untyped]  # pyright: ignore[reportMissingModuleSource]
    except ImportError:
        return {}
    try:
        doc: object = yaml.safe_load((providers_dir / DROID_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return doc if isinstance(doc, dict) else {}


def droid_models(providers_dir: Path) -> list[str]:
    """Модели манифеста droid по порядку файла; нет файла или он пуст — пустой список."""
    doc = _load_droid_manifest(providers_dir)
    overrides, discovery = doc.get("models_overrides"), doc.get("discovery")
    static = discovery.get("static") if isinstance(discovery, dict) else None
    names = [*overrides] if isinstance(overrides, dict) else []
    extra = static if isinstance(static, list) else []
    return list(dict.fromkeys(map(str, (*names, *extra))))
