from __future__ import annotations

# Квитанция droid v3 (qualified_models): схема, DTO, fail-closed проверка моста, квалификация моделей.

import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import droid_image  # noqa: E402
import receipt_schema as schema  # noqa: E402
import server  # noqa: E402

QUALIFIED = {
    "claude-sonnet-5-5": ["Read", "edit-cli"],  # проб-модель droid_image
    "gpt-6.1-sol": ["Read", "apply-patch-cli"],
    "deepseek-v4.1-flash": ["Read", "edit-cli"],
    "kimi-k3.1-pro": ["Read", "edit-cli"],
}


def make_v3(models: dict[str, list[str]] | None = None, **over: Any) -> dict[str, Any]:
    qualified = {m: sorted(ids) for m, ids in (models or QUALIFIED).items()}
    first = next(iter(qualified.values()))
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
    base = schema.tools_policy_digest(["Read"], QUALIFIED)
    changed = dict(QUALIFIED, **{"deepseek-v4.1-flash": ["Read"]})
    assert base != schema.tools_policy_digest(["Read"], changed)
    reordered = {m: list(reversed(ids)) for m, ids in QUALIFIED.items()}
    assert base == schema.tools_policy_digest(["Read"], reordered)


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
    receipt["tools_policy"]["digest"] = schema.tools_policy_digest([], qualified)
    assert schema.ReceiptV3.parse(receipt) == "disabled_tool_ids_invalid"
    with pytest.raises(server.LauncherUnavailable, match="tools policy mismatch"):
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


# ---- droid_image: квалификация моделей ---------------------------------------------------


class PerModelRpc:
    """Подмена droid_image._Rpc: каталог tools зависит от модели последней initialize_session."""

    protocol = "1.2.3"

    def __init__(
        self, tools_by_model: dict[str, list[str]], bad_model: str = ""
    ) -> None:
        self.tools_by_model, self.bad_model, self.model = tools_by_model, bad_model, ""

    def _settings(self, **extra: Any) -> dict[str, Any]:
        return {
            "modelId": self.model,
            "reasoningEffort": "high",
            "autonomyLevel": "high",
            **extra,
        }

    def call(
        self, method: str, params: Mapping[str, object], timeout: float = 0.0
    ) -> droid_image.RpcExchange:
        if method == "droid.initialize_session":
            self.model = str(params["modelId"])
            shown = "other" if self.model == self.bad_model else self.model
            settings = dict(self._settings(), modelId=shown)
            return droid_image.RpcExchange({"sessionId": "sid", "settings": settings}, [])
        if method == "droid.list_tools":
            tools = [{"id": i} for i in self.tools_by_model[self.model]]
            return droid_image.RpcExchange({"tools": tools}, [])
        if method == "droid.update_session_settings":
            settings = self._settings(disabledToolIds=params["disabledToolIds"])
            note = {"notification": {"type": "settings_updated", "settings": settings}}
            return droid_image.RpcExchange({}, [note])
        loaded = {"session": {"messages": []}, "settings": self._settings()}
        return droid_image.RpcExchange(loaded, [])

    def close(self) -> None:
        return None


def _install(tmp_path: Path, rpc: PerModelRpc, models: list[str]) -> dict[str, Any]:
    source = tmp_path / "droid-src"
    source.write_bytes(b"scripted-image")
    source.chmod(0o755)
    with mock.patch.object(droid_image, "_Rpc", lambda image, cwd, home: rpc):
        return droid_image.install_image(source, tmp_path / "workspace", models=models)


def test_install_image_qualifies_every_model(tmp_path: Path) -> None:
    rpc = PerModelRpc({m: list(ids) for m, ids in QUALIFIED.items()})
    receipt = _install(tmp_path, rpc, list(QUALIFIED))
    assert receipt["schema"] == 3
    assert receipt["qualified_models"] == {
        m: sorted(ids) for m, ids in QUALIFIED.items()
    }
    assert (
        receipt["qualified_models"]["gpt-6.1-sol"]
        != (receipt["qualified_models"]["deepseek-v4.1-flash"])
    )
    assert receipt["tools_policy"]["disabled_tool_ids"] == sorted(
        QUALIFIED["claude-sonnet-5-5"]
    )
    assert isinstance(schema.ReceiptV3.parse(receipt), schema.ReceiptV3)
    assert (tmp_path / "workspace" / "state" / "droid-binary-receipt.json").is_file()


def test_failed_model_qualification_writes_no_receipt(tmp_path: Path) -> None:
    rpc = PerModelRpc(
        {m: list(i) for m, i in QUALIFIED.items()}, bad_model="kimi-k3.1-pro"
    )
    with pytest.raises(droid_image.ProbeError):
        _install(tmp_path, rpc, list(QUALIFIED))
    assert not (tmp_path / "workspace" / "state" / "droid-binary-receipt.json").exists()
