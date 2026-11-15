"""Регрессии независимого CI, карантинного POST и выбора провайдера."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from adapters import ADAPTER_KINDS
from core.http_post_ingress import begin_post
from tests.test_fleet_compiler import (
    build_manifests,
    compile_docs,
    header,
    manifest_doc,
)
from tests import test_transport_isolation as isolation
from tests import transport_test_support as support

ROOT = Path(__file__).resolve().parents[1]


def quarantine_handler() -> Any:
    handler = SimpleNamespace(path="/v1/quarantine?probe=1", observations=[])
    handler._telemetry_begin = lambda: handler.observations.append("begin")

    def respond() -> None:
        assert handler._headers_already_sent is False
        assert handler._response_status == 0
        assert handler._trace is None
        handler.observations.append("quarantine")

    handler._handle_quarantine_post = respond
    return handler


def dirty(handler: Any) -> None:
    handler._headers_already_sent = True
    handler._response_status = 502
    handler._trace = object()


def test_quarantine_repeated_post_resets_state_before_auth_and_drain() -> None:
    handler = quarantine_handler()
    # У host нет auth/drain-портов: карантин обязан ответить до их чтения.
    for _ in range(2):
        dirty(handler)
        assert begin_post(handler, SimpleNamespace()) is None
    assert handler.observations == ["begin", "quarantine"] * 2


def test_server_quarantine_uses_shared_post_entry() -> None:
    tree = ast.parse((ROOT / "server.py").read_bytes())
    method = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "do_POST"
    )
    calls: list[object] = []
    facade = SimpleNamespace(handle_post=lambda handler, host: calls.append(handler))
    namespace: dict[str, Any] = {
        "_transport_facade": facade,
        "sys": SimpleNamespace(modules={"probe": object()}),
        "__name__": "probe",
    }
    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "server.py", "exec"),
        namespace,
    )
    handler = quarantine_handler()
    dirty(handler)
    namespace["do_POST"](handler)
    assert calls == [handler]


def test_pre_rejected_provider_never_enters_backends() -> None:
    result = compile_docs(
        manifest_doc("alpha"),
        manifest_doc("beta"),
        hdr=dict(header(), default_model="beta-one"),
        rejected_providers={"alpha": ("pre_rejected",)},
    )
    assert "alpha" not in result.fleet["backends"]
    assert "alpha" not in result.sidecar["providers"]
    assert result.rejected_providers == {"alpha": ("pre_rejected",)}


def test_enabled_bridge_supplies_shared_model_before_disabled_bridge() -> None:
    from core.fleet_compiler import compile_catalog

    documents = [
        manifest_doc("alpha", enabled=False, models_overrides={"shared": {}}),
        manifest_doc("beta", models_overrides={"shared": {}}),
    ]
    result = compile_catalog(
        dict(header(), default_model="shared"),
        build_manifests(*documents),
        kinds=ADAPTER_KINDS,
    )
    assert result.fleet["models"][0]["backend"] == "beta"
    assert result.sidecar["models"]["shared"]["provider"] == "beta"


def test_core_has_zero_forbidden_imports_without_local_canon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    absent = tmp_path / "missing-architecture.md"
    monkeypatch.setattr(isolation, "CANON", absent, raising=False)
    monkeypatch.setattr(support, "CANON", absent, raising=False)
    assert isolation.categories(frozenset({"aiohttp.web"})) == {"TRANSPORT_IMPORTS"}
    # Чистые модули проверяются и без host-local канона, не skip.
    for name in isolation.PURE:
        source = (ROOT / (name.replace(".", "/") + ".py")).read_bytes()
        assert isolation.categories(isolation.imports(source, name)) == frozenset()


def test_relative_import_without_module_has_no_leading_dot() -> None:
    assert isolation.imports(b"from . import foo", "entry") == frozenset({"foo"})


def test_local_canon_drift_is_not_silently_accepted(tmp_path: Path) -> None:
    canon = tmp_path / "architecture.md"
    canon.write_text(
        '`TRANSPORT_IMPORTS = {"wrong"}`\n'
        '`PERSISTENCE_IMPORTS = {"wrong"}`\n'
        '`NET_PROC_IO_IMPORTS = {"wrong"}`\n'
    )
    with pytest.raises(AssertionError):
        support.canonical_prefixes(canon)


def test_missing_base_skips_only_snapshot_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def missing(arguments: list[str], **kwargs: Any) -> Any:
        calls.append(arguments)
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(support.subprocess, "run", missing)
    with pytest.raises(
        pytest.skip.Exception, match="base commit unavailable in shallow clone"
    ):
        support.require_base(tmp_path, "missing")
    assert calls[0][-3:] == ["cat-file", "-e", "missing^{commit}"]
    assert isolation.imports(b"from . import foo", "entry") == {"foo"}
