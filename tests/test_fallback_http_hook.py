"""F-015/F-016: kill-switch, устойчивость к битому конфигу и кэш каталога хука."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import core.fallback_http_hook as hook  # noqa: E402

VALID = """\
chains:
  alias-x:
    declared_context_window: 1000
    candidates:
      - model: m1
        cost_class: subscription
        context_window: 1000
      - model: m2
        cost_class: subscription
        context_window: 1000
"""


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRIDGE_MODEL_FALLBACK_ENABLED", raising=False)
    hook._CACHE.clear()


def _dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> Path:
    (tmp_path / "c.yaml").write_text(text, encoding="utf-8")
    monkeypatch.setenv("BRIDGE_FALLBACK_CHAINS_PATH", str(tmp_path))
    return tmp_path


def _forbid_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> Any:
        raise AssertionError("_catalog must not be called when the kill-switch is off")

    monkeypatch.setattr(hook, "_catalog", boom)


@pytest.mark.parametrize("value", [None, "false", "0", ""])
def test_dispatch_is_inert_when_disabled(monkeypatch: pytest.MonkeyPatch, value: str | None) -> None:
    if value is not None:
        monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", value)
    _forbid_catalog(monkeypatch)
    host = SimpleNamespace(_auth_ok=lambda handler: pytest.fail("auth must not be touched"))
    assert hook.dispatch(object(), {"model": "alias-x"}, host, lambda *a: None) is False


def test_append_models_returns_cards_untouched_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid_catalog(monkeypatch)
    cards = [{"id": "m1"}]
    assert hook.append_models(cards) is cards


def test_append_models_lists_alias_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dir(tmp_path, monkeypatch, VALID)
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "true")
    ids = [c["id"] for c in hook.append_models([{"id": "m1"}])]
    assert ids == ["m1", "alias-x"]
    assert hook.append_models([{"id": "m1"}], ("provider",)) == [{"id": "m1"}]


@pytest.mark.parametrize("text", ["chains: [unterminated\n", "chains:\n  a: {}\n", "- x\n"])
def test_broken_config_yields_empty_catalog_and_does_not_raise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, caplog: pytest.LogCaptureFixture
) -> None:
    _dir(tmp_path, monkeypatch, text)
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "true")
    with caplog.at_level("WARNING"):
        catalog = hook._catalog()
    assert dict(catalog.chains) == {}
    assert "invalid" in caplog.text
    cards = [{"id": "m1"}]
    assert hook.append_models(cards) == cards
    assert hook.dispatch(object(), {"model": "alias-x"}, object(), lambda *a: None) is False


def test_broken_env_does_not_break_the_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dir(tmp_path, monkeypatch, VALID)
    monkeypatch.setenv("BRIDGE_MODEL_FALLBACK_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_FALLBACK_MAX_HOPS", "not-a-number")
    assert dict(hook._catalog().chains) == {}


def test_catalog_is_cached_and_reloaded_on_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _dir(tmp_path, monkeypatch, VALID)
    calls: list[object] = []
    real = hook.load_chains
    monkeypatch.setattr(hook, "load_chains", lambda *a, **k: calls.append(a) or real(*a, **k))
    first = hook._catalog()
    assert hook._catalog() is first and len(calls) == 1
    path = tmp_path / "c.yaml"
    path.write_text(VALID.replace("alias-x", "alias-y"), encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))
    assert "alias-y" in hook._catalog().chains and len(calls) == 2
    monkeypatch.setenv("BRIDGE_FALLBACK_MAX_HOPS", "2")
    assert hook._catalog().max_hops == 2 and len(calls) == 3


def test_import_and_default_catalog_work_without_pyyaml(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.model_fallback_chain as module

    monkeypatch.setattr(module, "yaml", None)
    monkeypatch.delenv("BRIDGE_FALLBACK_CHAINS_PATH", raising=False)
    assert len(hook._catalog().chains) >= 1
