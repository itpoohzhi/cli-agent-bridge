from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools import receipt_schema as schema

EXIT_VERIFY_FAILED = 4
DROID_MANIFEST = "droid.yaml"


@dataclass(frozen=True, slots=True)
class ReceiptVerdict:
    """Итог проверки: `reason` пуст — годен, иначе slug отказа."""

    reason: str = ""

    @property
    def ok(self) -> bool:
        """True — receipt годен."""
        return not self.reason


def sha256_file(path: Path) -> str:
    """sha256 файла; нечитаемый файл — пустая строка."""
    try:
        with open(path, "rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except (OSError, TypeError):
        return ""


def _load_droid_manifest(providers_dir: Path) -> dict[str, Any]:
    """YAML манифеста droid; нет PyYAML, файла или mapping — пустой dict."""
    try:
        import yaml  # type: ignore[import-untyped]  # pyright: ignore[reportMissingModuleSource]
    except ImportError:
        return {}
    try:
        doc: object = yaml.safe_load(
            (providers_dir / DROID_MANIFEST).read_text(encoding="utf-8")
        )
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


def _read_receipt(path: Path) -> dict[str, Any]:
    """JSON receipt; нет файла, он нечитаем или не объект — пустой dict."""
    try:
        doc: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return doc if isinstance(doc, dict) else {}


def _sha_matches(actual: str, recorded: object) -> bool:
    """Оба sha256 непусты и равны: нечитаемый файл или пустая запись — отказ."""
    return bool(actual) and actual == recorded


def verify_receipt(
    receipt_path: Path, providers_dir: Path, source: Path | None = None
) -> ReceiptVerdict:
    """Первая причина отказа receipt для текущего манифеста droid либо пустой вердикт."""
    rec = _read_receipt(receipt_path)
    parsed = schema.ReceiptV3.parse(rec)
    gate = schema.receipt_gate_problem(rec)
    required = droid_models(providers_dir)
    have = (
        {q.model_id for q in parsed.qualified} if not isinstance(parsed, str) else set()
    )
    missing = [m for m in required if m not in have]
    meta = rec.get("source")
    recorded = meta.get("sha256") if isinstance(meta, dict) else None
    image_ok = _sha_matches(
        sha256_file(Path(str(rec.get("image_path")))), rec.get("image_sha256")
    )
    binary_ok = _sha_matches(sha256_file(source), recorded) if source else True
    problems = (
        ("receipt_unreadable", not rec),
        (gate, bool(gate)),
        ("image_sha256_mismatch", not image_ok),
        ("binary_sha256_mismatch", not binary_ok),
        ("droid_manifest_empty", not required),
        ("model_not_qualified: " + ",".join(missing), bool(missing)),
    )
    return ReceiptVerdict(next((slug for slug, bad in problems if bad), ""))


def verify_receipt_cli(
    receipt_path: Path, providers_dir: Path, source: Path | None
) -> int:
    """`droid_image --verify-receipt`: проверка без запуска образа; 0 — годен, иначе `EXIT_VERIFY_FAILED`."""
    verdict = verify_receipt(receipt_path, providers_dir, source)
    stream = sys.stdout if verdict.ok else sys.stderr
    stream.write(
        f"droid_image: receipt v3 {'годен' if verdict.ok else verdict.reason}\n"
    )
    return 0 if verdict.ok else EXIT_VERIFY_FAILED
