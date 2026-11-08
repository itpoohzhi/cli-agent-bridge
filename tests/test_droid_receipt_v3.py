from __future__ import annotations

# Квитанция droid v3 (qualified_models): схема, DTO, fail-closed проверка моста и `--verify-receipt`.

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

import server  # noqa: E402
from tools import droid_image  # noqa: E402
from tools import droid_receipt_verify as verify  # noqa: E402
from tools import receipt_schema as schema  # noqa: E402

QUALIFIED = {
    "claude-sonnet-5-5": ["Read", "edit-cli"],  # проб-модель droid_image
    "gpt-6.1-sol": ["Read", "apply-patch-cli"],
    "deepseek-v4.1-flash": ["Read", "edit-cli"],
    "kimi-k3.1-pro": ["Read", "edit-cli"],
}


def make_v3(models: dict[str, list[str]] | None = None, **over: Any) -> dict[str, Any]:
    qualified = {m: sorted(ids) for m, ids in (models or QUALIFIED).items()}
    first = sorted({tool for ids in qualified.values() for tool in ids})
    receipt: dict[str, Any] = {
        "schema": schema.RECEIPT_SCHEMA,
        "image_path": "/x/droid",
        "image_sha256": "a" * 64,
        "protocol": {
            "api_version": schema.RPC_API_VERSION,
            "protocol_version": "1.2.3",
        },
        "tools_policy": {
            "policy": schema.TOOLS_POLICY,
            "disabled_tool_ids": first,
            "digest": schema.tools_policy_digest(first, qualified),
        },
        "qualified_models": qualified,
        "qualified_targets": [{"model": m, "effort": "high"} for m in qualified],
        "settings_profile": {
            "profile": dict(schema.SETTINGS_PROFILE),
            "digest": schema.settings_profile_digest(),
        },
        "probes": {name: "ok" for name in schema.RECEIPT_PROBES},
    }
    receipt.update(over)
    return receipt


# ---- схема v3 -------------------------------------------------------------------------


def test_receipt_schema_is_3_and_digest_covers_qualified_models() -> None:
    assert schema.RECEIPT_SCHEMA == 3 == server.RECEIPT_SCHEMA
    every = sorted({tool for ids in QUALIFIED.values() for tool in ids})
    base = schema.tools_policy_digest(every, QUALIFIED)
    changed = dict(QUALIFIED, **{"deepseek-v4.1-flash": ["Read"]})
    assert base != schema.tools_policy_digest(every, changed)
    reordered = {m: list(reversed(ids)) for m, ids in QUALIFIED.items()}
    assert base == schema.tools_policy_digest(every, reordered)


def test_parse_accepts_v3_and_exposes_per_model_tools() -> None:
    parsed = schema.ReceiptV3.parse(make_v3())
    assert isinstance(parsed, schema.ReceiptV3)
    assert parsed.tools_for("gpt-6.1-sol") == ("Read", "apply-patch-cli")
    assert parsed.tools_for("deepseek-v4.1-flash") == ("Read", "edit-cli")
    assert parsed.tools_for("gemini-3.8-flash") is None
    assert parsed.qualified[0] == schema.QualifiedModelSpec(
        "claude-sonnet-5-5", ("Read", "edit-cli")
    )


@pytest.mark.parametrize(
    "mutate,slug",
    [
        (lambda r: r.pop("qualified_models"), "qualified_models_invalid"),
        (lambda r: r.update(qualified_models={}), "qualified_models_invalid"),
        (
            lambda r: r.update(qualified_models={"gpt-6.1-sol": []}),
            "qualified_models_invalid",
        ),
        (
            lambda r: r.update(qualified_models={"gpt-6.1-sol": "Read"}),
            "qualified_models_invalid",
        ),
        (
            lambda r: r["qualified_models"].update({"extra-model": ["Read"]}),
            "tools_policy_digest_mismatch",
        ),
        (lambda r: r.update(schema=2), "schema_mismatch"),
        (lambda r: r.update(tools_policy=None), "tools_policy_invalid"),
        (
            lambda r: r["tools_policy"].update(disabled_tool_ids=[]),
            "tools_policy_digest_mismatch",
        ),
    ],
)
def test_parse_is_fail_closed(mutate: Any, slug: str) -> None:
    receipt = make_v3()
    mutate(receipt)
    assert schema.ReceiptV3.parse(receipt) == slug
    assert schema.ReceiptV3.parse("not-a-mapping") == "receipt_malformed"


@pytest.mark.parametrize("bad", [[], [""], None, "Read", ["Read", ""]])
def test_parse_rejects_empty_disabled_tool_ids_with_matching_sha256(bad: Any) -> None:
    receipt = make_v3()
    qualified = receipt["qualified_models"]
    receipt["tools_policy"]["disabled_tool_ids"] = bad
    receipt["tools_policy"]["digest"] = schema.json_digest(
        {
            "policy": schema.TOOLS_POLICY,
            "disabled_tool_ids": [],
            "qualified_models": qualified,
        }
    )
    assert schema.ReceiptV3.parse(receipt) == "disabled_tool_ids_invalid"
    with pytest.raises(server.LauncherUnavailable, match="tools policy mismatch|invalid qualified_models"):
        server._check_receipt_quad(receipt)


def test_catalog_tool_ids_rejects_malformed_catalogues() -> None:
    # Порядок каталога list_tools сохраняется: он уходит в disabledToolIds без пересортировки.
    assert schema.catalog_tool_ids([{"id": "b"}, {"id": "a"}]) == ("b", "a")
    assert schema.catalog_tool_ids([{"id": "a"}, {"id": "a"}]) == ("a",)
    for bad in (None, [], {}, "x", [{"id": ""}], [{"id": 1}], [{}], ["a"], 5):
        assert schema.catalog_tool_ids(bad) == ()


def test_check_receipt_quad_requires_qualified_models() -> None:
    server._check_receipt_quad(make_v3())
    broken = make_v3()
    del broken["qualified_models"]
    with pytest.raises(server.LauncherUnavailable):
        server._check_receipt_quad(broken)


# ---- --verify-receipt --------------------------------------------------------------------


def _providers_with_droid(tmp_path: Path, models: list[str]) -> Path:
    directory = tmp_path / "providers.d"
    directory.mkdir(exist_ok=True)
    body = "".join(f"  {m}: {{}}\n" for m in models)
    (directory / "droid.yaml").write_text(
        "manifest_version: 1\nprovider_id: droid\nkind: droid\nowned_by: factory-droid\n"
        "transport:\n  bridge: {}\nmodels_overrides:\n" + body,
        encoding="utf-8",
    )
    return directory


def _receipt_path(tmp_path: Path) -> Path:
    return tmp_path / "workspace" / "state" / "droid-binary-receipt.json"


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Реальный `~/.local/bin/droid` не должен запускаться ни при каком сбое разбора аргументов."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def _verify(tmp_path: Path, models: list[str], *extra: str) -> int:
    providers = _providers_with_droid(tmp_path, models)
    args = ["--verify-receipt", str(_receipt_path(tmp_path)), "--providers-dir"]
    return droid_image.main([*args, str(providers), *extra])


def _installed(tmp_path: Path) -> None:
    """Receipt v3 на диске: образ в runtime/droid-image и записанный sha256 исходного бинаря."""
    image = tmp_path / "workspace" / "runtime" / "droid-image" / "x" / "droid"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"scripted-image")
    digest = hashlib.sha256(b"scripted-image").hexdigest()
    receipt = make_v3(
        image_path=str(image), image_sha256=digest, source={"sha256": digest}
    )
    path = _receipt_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(receipt), encoding="utf-8")


def test_verify_receipt_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _installed(tmp_path)
    assert _verify(tmp_path, list(QUALIFIED)) == 0
    assert (
        _verify(tmp_path, [*QUALIFIED, "gemini-3.8-flash"]) == verify.EXIT_VERIFY_FAILED
    )
    assert "gemini-3.8-flash" in capsys.readouterr().err
    other = tmp_path / "other-droid"
    other.write_bytes(b"different")
    assert _verify(tmp_path, list(QUALIFIED), "--source", str(other)) != 0
    image = Path(json.loads(_receipt_path(tmp_path).read_text())["image_path"])
    image.chmod(0o700)
    image.write_bytes(b"tampered")
    assert _verify(tmp_path, list(QUALIFIED)) != 0


def test_verify_receipt_verdicts_are_typed_and_fail_closed(tmp_path: Path) -> None:
    _installed(tmp_path)
    providers = _providers_with_droid(tmp_path, list(QUALIFIED))
    assert (
        verify.verify_receipt(_receipt_path(tmp_path), providers)
        == verify.ReceiptVerdict()
    )
    gone = verify.verify_receipt(tmp_path / "absent.json", providers)
    assert (gone.ok, gone.reason) == (False, "receipt_unreadable")
    empty = verify.verify_receipt(_receipt_path(tmp_path), tmp_path / "no-providers")
    assert empty.reason == "droid_manifest_empty"


def test_verify_receipt_tolerates_non_mapping_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _installed(tmp_path)
    receipt = json.loads(_receipt_path(tmp_path).read_text(encoding="utf-8"))
    receipt["source"] = ["bad"]  # внешний JSON: вместо mapping пришёл список
    _receipt_path(tmp_path).write_text(json.dumps(receipt), encoding="utf-8")
    other = tmp_path / "other-droid"
    other.write_bytes(b"different")
    assert _verify(tmp_path, list(QUALIFIED), "--source", str(other)) != 0
    assert "binary_sha256_mismatch" in capsys.readouterr().err
