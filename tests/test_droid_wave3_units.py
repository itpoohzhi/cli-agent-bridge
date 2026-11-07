from __future__ import annotations

# Быстрые детерминированные проверки критических веток W3: атомарный промоушен, `--promote` пробника,
# `fleet_compile`, квалификация проб-модели (`core/catalog_promote.py`, `scripts/capability_probe.py`,
# `tools/fleet_compile.py`, `tools/droid_qualify_models.py`, `tools/droid_receipt_verify.py`, `tools/droid_image.py`).

import dataclasses
import hashlib
import importlib.util
import io
import json
import sys
from argparse import Namespace
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import droid_image  # noqa: E402
import droid_qualify_models as qualify  # noqa: E402
import droid_receipt_verify as verify  # noqa: E402
import receipt_schema as schema  # noqa: E402
import server  # noqa: E402
from core import catalog_promote as promote  # noqa: E402
from test_droid_receipt_v3 import (  # noqa: E402  # pyright: ignore[reportImplicitRelativeImport]
    QUALIFIED,
    PerModelRpc,
    make_v3,
    _installed,  # pyright: ignore[reportPrivateUsage]
    _providers_with_droid,  # pyright: ignore[reportPrivateUsage]
    _receipt_path,  # pyright: ignore[reportPrivateUsage]
)
from tools import fleet_compile  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "capability_probe_wave3_units", ROOT / "scripts" / "capability_probe.py"
)
assert _spec is not None and _spec.loader is not None
cp = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = cp
_spec.loader.exec_module(cp)

PROVIDERS = ROOT / "providers.d"
FP = "f" * 64
REQ = promote.PromoteRequest("droid", "gpt-6.1-sol", "r" * 64, FP, ("high",))


def test_receipt_verdict_is_frozen_and_slotted() -> None:
    verdict = verify.ReceiptVerdict()
    attribute = "reason"
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(verdict, attribute, "x")
    assert not hasattr(verdict, "__dict__")


# ---- capability_probe --promote -------------------------------------------------------


def _confirmed_result(verdict: str = "confirmed") -> SimpleNamespace:
    return SimpleNamespace(
        verdict=verdict,
        receipt_path=None,
        receipt_sha256="r" * 64,
        fingerprint_sha256=FP,
        efforts_proven=("high",),
        default_effort="high",
        reused=False,
        receipt={"checks": {}},
        exit_code=0,
    )


def _probe_cli(
    monkeypatch: pytest.MonkeyPatch, verdict: str, failure: str, **kwargs: Any
) -> tuple[int, mock.Mock]:
    promoted = mock.Mock(return_value=failure)
    monkeypatch.setattr(cp, "run_probe", lambda *a, **k: _confirmed_result(verdict))
    monkeypatch.setattr(cp, "promote_confirmed", promoted)
    env = {"BRIDGE_KEY": "key", **kwargs.pop("env", {})}
    code = cp.probe_cli(
        "gpt-6.1-sol", providers_dir=PROVIDERS, env=env, out=io.StringIO(), **kwargs
    )
    return code, promoted


def test_probe_cli_promotes_only_confirmed_when_requested(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    code, promoted = _probe_cli(
        monkeypatch, "confirmed", "", promote=True, state_dir=tmp_path
    )
    assert code == 0
    promoted.assert_called_once()
    assert promoted.call_args.args == (REQ, tmp_path)
    assert _probe_cli(monkeypatch, "confirmed", "")[1].call_count == 0
    assert (
        _probe_cli(monkeypatch, "quarantine_failed", "", promote=True)[1].call_count
        == 0
    )


def test_probe_cli_defaults_state_dir_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    env = {"BRIDGE_STATE_DIR": str(tmp_path)}
    _, promoted = _probe_cli(monkeypatch, "confirmed", "", promote=True, env=env)
    assert promoted.call_args.args[1] == tmp_path


def test_probe_cli_reports_promote_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, _ = _probe_cli(monkeypatch, "confirmed", "post_verify_mismatch", promote=True)
    assert code == cp.EXIT_FAILED
    assert "promote_failed (post_verify_mismatch)" in capsys.readouterr().err


# ---- fleet_compile --------------------------------------------------------------------


def test_explain_prints_sorted_unicode_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        fleet_compile, "load_manifests", lambda *a, **k: SimpleNamespace(manifests=())
    )
    result: Any = SimpleNamespace(sidecar={"models": {"модель": {"provider": "p"}}})
    args = Namespace(providers_dir=None, explain="модель")
    assert fleet_compile._explain(args, result) == 0
    out = capsys.readouterr().out
    assert "модель" in out
    assert list(json.loads(out)) == ["alternates", "candidates", "model_id", "primary"]


def test_main_writes_to_given_paths_else_state_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state = tmp_path / "state"
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(state))
    out, side = tmp_path / "out.json", tmp_path / "side.json"
    assert (
        fleet_compile.main(["--write", "--output", str(out), "--sidecar", str(side)])
        == 0
    )
    assert out.is_file() and side.is_file() and not state.exists()
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == 1 and printed[0].startswith("OK: wrote ")
    assert fleet_compile.main(["--write"]) == 0
    assert (state / fleet_compile.FLEET_FILE).is_file()
    assert (state / fleet_compile.SIDECAR_FILE).is_file()


def test_main_stops_on_unreadable_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("BRIDGE_STATE_DIR", str(tmp_path))
    (tmp_path / fleet_compile.REGISTRY_FILE).write_text("not json", encoding="utf-8")
    assert fleet_compile.main(["--check"]) == 1
    assert "lifecycle_unreadable" in capsys.readouterr().err


# ---- droid_image / droid_qualify_models -----------------------------------------------


def test_qualify_with_probe_sorts_probe_model_tools() -> None:
    settings = qualify.ProbeSettings(Path("/w"), "high", "high")
    rpc = PerModelRpc({"m2": ["z", "y"]})
    got = qualify.qualify_with_probe(lambda: rpc, settings, ("m1", ["b", "a"]), ["m2"])
    assert got == {"m1": ("a", "b"), "m2": ("z", "y")}


def test_install_image_probes_models_with_probe_effort(tmp_path: Path) -> None:
    seen: list[str] = []

    class Recording(PerModelRpc):
        def call(
            self, method: str, params: Mapping[str, object], timeout: float = 0.0
        ) -> droid_image.RpcExchange:
            if method == "droid.initialize_session":
                seen.append(str(params["reasoningEffort"]))
            return super().call(method, params, timeout)

    source = tmp_path / "droid-src"
    source.write_bytes(b"scripted-image")
    source.chmod(0o755)
    rpc = Recording({m: list(ids) for m, ids in QUALIFIED.items()})
    with mock.patch.object(droid_image, "_Rpc", lambda image, cwd, home: rpc):
        droid_image.install_image(source, tmp_path / "ws", models=["gpt-6.1-sol"])
    assert seen and set(seen) == {droid_image.PROBE_MODEL_EFFORT[1]}


def test_droid_image_help_uses_first_docstring_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("COLUMNS", "500")
    with pytest.raises(SystemExit):
        droid_image.main(["--help"])
    assert (droid_image.__doc__ or "").splitlines()[0] in capsys.readouterr().out


# ---- verify_receipt обязан отвергать всё, что отвергает рантайм-гейт моста ------------------


def _empty_disabled(rec: dict[str, Any]) -> None:
    rec["tools_policy"]["disabled_tool_ids"] = []
    rec["tools_policy"]["digest"] = schema.tools_policy_digest([], rec["qualified_models"])


@pytest.mark.parametrize(
    "mutate,slug",
    [
        (lambda r: r["protocol"].update(api_version="0.0.1"), "protocol_mismatch"),
        (lambda r: r["protocol"].update(protocol_version=""), "protocol_mismatch"),
        (lambda r: r.pop("protocol"), "protocol_mismatch"),
        (lambda r: r["settings_profile"].update(digest="x"), "settings_profile_mismatch"),
        (
            lambda r: r["settings_profile"]["profile"].update(interactionMode="spec"),
            "settings_profile_mismatch",
        ),
        (lambda r: r.pop("settings_profile"), "settings_profile_mismatch"),
        (lambda r: r["probes"].update(load="fail"), "probes_not_ok"),
        (lambda r: r.pop("probes"), "probes_not_ok"),
        (_empty_disabled, "disabled_tool_ids_invalid"),
    ],
)
def test_verify_receipt_matches_runtime_gate(
    tmp_path: Path, mutate: Any, slug: str
) -> None:
    _installed(tmp_path)
    path = _receipt_path(tmp_path)
    receipt = json.loads(path.read_text(encoding="utf-8"))
    mutate(receipt)
    path.write_text(json.dumps(receipt), encoding="utf-8")
    providers = _providers_with_droid(tmp_path, list(QUALIFIED))
    assert verify.verify_receipt(path, providers).reason == slug
    with pytest.raises(server.LauncherUnavailable):
        server._check_receipt_quad(receipt)


def test_receipt_gate_problem_accepts_valid_and_reports_first_refusal() -> None:
    good = make_v3()
    assert schema.receipt_gate_problem(good) == ""
    assert schema.receipt_gate_problem("not-a-mapping") == "protocol_mismatch"
    good["probes"] = {}
    good["protocol"] = {}
    assert schema.receipt_gate_problem(good) == "protocol_mismatch"


def test_sha256_file_hashes_content_and_is_fail_closed(tmp_path: Path) -> None:
    blob = tmp_path / "blob"
    blob.write_bytes(bytes(1048581))
    assert verify.sha256_file(blob) == hashlib.sha256(blob.read_bytes()).hexdigest()
    assert verify.sha256_file(tmp_path / "absent") == ""
    assert verify.sha256_file(None) == ""  # pyright: ignore[reportArgumentType]
