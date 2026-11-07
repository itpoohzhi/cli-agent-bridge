from __future__ import annotations

# Офлайн-проверка receipt fail-closed: отсутствующий образ/источник с пустым записанным sha256 не годен.

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import droid_receipt_verify as verify  # noqa: E402
from test_droid_receipt_v3 import (  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
    QUALIFIED,
    _installed,  # pyright: ignore[reportPrivateUsage]
    _providers_with_droid,  # pyright: ignore[reportPrivateUsage]
    _receipt_path,  # pyright: ignore[reportPrivateUsage]
)


def _rewrite_receipt(tmp_path: Path, **changes: Any) -> None:
    path = _receipt_path(tmp_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    receipt.update(changes)
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_verify_receipt_rejects_missing_image_with_empty_recorded_sha(tmp_path: Path) -> None:
    _installed(tmp_path)
    _rewrite_receipt(tmp_path, image_path=str(tmp_path / "absent-image"), image_sha256="")
    providers = _providers_with_droid(tmp_path, list(QUALIFIED))
    verdict = verify.verify_receipt(_receipt_path(tmp_path), providers)
    assert (verdict.ok, verdict.reason) == (False, "image_sha256_mismatch")


@pytest.mark.parametrize("recorded", ["", None, 7])
def test_verify_receipt_rejects_missing_source_with_empty_recorded_sha(tmp_path: Path, recorded: Any) -> None:
    _installed(tmp_path)
    _rewrite_receipt(tmp_path, source={"sha256": recorded})
    providers = _providers_with_droid(tmp_path, list(QUALIFIED))
    verdict = verify.verify_receipt(_receipt_path(tmp_path), providers, tmp_path / "absent-source")
    assert (verdict.ok, verdict.reason) == (False, "binary_sha256_mismatch")
    assert verify.verify_receipt(_receipt_path(tmp_path), providers).reason == ""
