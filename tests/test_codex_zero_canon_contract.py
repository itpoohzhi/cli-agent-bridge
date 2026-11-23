"""Contract & expected-red tests for Codex Zero-Canon policy, FS, and attestation (W0-A)."""

from __future__ import annotations

import importlib
import json
import stat
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core import zero_canon_fs  # noqa: E402
from core.stdio_resident.codex_driver import CodexAppServerDriver  # noqa: E402
from core.stdio_resident.turn_error_sse import build_turn_error  # noqa: E402
from core.stdio_resident.zero_canon_router import (  # noqa: E402
    KIND_EPHEMERAL,
    KIND_RESIDENT,
    decide_zero_canon_route,
)
from core.subbridge_zero_canon import normalize_review_profile  # noqa: E402

EXPECTED_RED = "EXPECTED_RED:codex_v2"
DUMMY_API_KEY = "sk-dummy-test-000"
SOL_EFFORTS = ["low", "medium", "high", "xhigh", "max"]
TERRA_EFFORTS = ["low", "medium", "high"]


def _import_contract_module(module_name: str, defect: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        pytest.fail(f"{EXPECTED_RED}: {defect} (missing {module_name}: {exc})")


def _seed_fake_codex_home(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    home = tmp_path / "real_home"
    codex_home = home / ".codex"
    codex_home.mkdir(parents=True, mode=0o700)
    (codex_home / "config.toml").write_text(
        'model = "gpt-6.1-sol"\n[mcp_servers.bad]\ncommand = "echo"\n[hooks]\non_turn = "x"\n',
        encoding="utf-8",
    )
    (codex_home / "auth.json").write_text(
        json.dumps({"OPENAI_API_KEY": DUMMY_API_KEY}),
        encoding="utf-8",
    )
    zc_root = tmp_path / "zc-turn-1"
    zc_root.mkdir(mode=0o700)
    env = {
        "HOME": str(home),
        "CODEX_HOME": str(codex_home),
        "BRIDGE_KEY": DUMMY_API_KEY,
        "INTERNAL_SERVICE_KEY": DUMMY_API_KEY,
    }
    return codex_home, zc_root, env


def _assert_write_0600_rejected(dst: Path, data: bytes, reason: str) -> None:
    try:
        zero_canon_fs.write_atomic_0600(dst, data)
    except (FileExistsError, OSError, RuntimeError):
        return
    pytest.fail(f"{EXPECTED_RED}: write_atomic_0600 failed to reject {reason}")


def test_zero_canon_model_effort_matrix_and_no_clamp() -> None:
    """ADR-001 Policy: immutable Sol/Terra effort matrix without clamp or 6.2 alias."""
    codex_path = ROOT / "providers.d" / "codex.yaml"
    overrides = yaml.safe_load(codex_path.read_text(encoding="utf-8"))[
        "models_overrides"
    ]
    assert overrides["gpt-6.1-sol"]["efforts"] == SOL_EFFORTS, (
        f"{EXPECTED_RED}: Sol effort matrix mismatch: "
        f"{overrides['gpt-6.1-sol']['efforts']!r}"
    )
    assert overrides["gpt-6.1-terra"]["efforts"] == TERRA_EFFORTS, (
        f"{EXPECTED_RED}: Terra effort matrix mismatch in providers.d/codex.yaml"
    )
    _import_contract_module(
        "core.codex_zero_canon_policy",
        "pure codex zero-canon model/effort policy module not implemented",
    )


def test_zero_canon_tools_off_and_upstream_tool_event_forbidden() -> None:
    """ADR-001 Policy: strict Zero-Canon strips tools and fails closed on tool events."""
    _import_contract_module(
        "core.codex_zero_canon_policy",
        "zero-canon tools-off and zero_canon_tool_event_forbidden not implemented",
    )


def test_zero_canon_strict_review_profile_rejects_typos() -> None:
    """ADR-001 AD-014: typo Zero_Canon must raise invalid_review_profile, not standard."""
    http_mod = _import_contract_module(
        "core.zero_canon_http",
        f"strict review profile parser missing (baseline maps Zero_Canon -> "
        f"{normalize_review_profile('Zero_Canon')!r})",
    )
    parser = getattr(http_mod, "parse_strict_review_profile", None)
    assert callable(parser), (
        f"{EXPECTED_RED}: core.zero_canon_http lacks parse_strict_review_profile"
    )
    with pytest.raises((ValueError, RuntimeError)):
        parser("Zero_Canon")


def test_zero_canon_provider_filter_and_v2_flag_off_503(tmp_path: Path) -> None:
    """ADR-001 AD-014: exclude openai-key-3 & /sg-openai; V2 flag-off -> 503."""
    cfg_path = tmp_path / "dynamic_config.json"
    flag_default = zero_canon_fs.read_gigarc_bool(
        "BRIDGE_CODEX_APP_SERVER_V2_ENABLED",
        cfg_path,
        environ={},
        default=False,
    )
    assert flag_default is False
    http_mod = _import_contract_module(
        "core.zero_canon_http",
        "zero-canon provider filter and V2-off 503 guard not implemented",
    )
    assert callable(getattr(http_mod, "filter_zero_canon_providers", None)), (
        f"{EXPECTED_RED}: core.zero_canon_http lacks filter_zero_canon_providers"
    )


def test_zero_canon_attestation_header_and_strip_upstream_spoof() -> None:
    """ADR-001 AD-014 & Cycle 4: strip spoofed upstream attestation; emit trusted header."""
    http_mod = _import_contract_module(
        "core.zero_canon_http",
        "zero-canon attestation projection and upstream spoof stripper not implemented",
    )
    strip_fn = getattr(http_mod, "strip_upstream_attestation", None)
    assert callable(strip_fn), (
        f"{EXPECTED_RED}: core.zero_canon_http lacks strip_upstream_attestation"
    )
    raw_hdrs = {
        "x-zero-canon-attestation": "profile=zero-canon;backend=fake",
        "X-Ok": "1",
    }
    lower_keys = {k.lower() for k in strip_fn(raw_hdrs)}
    assert "x-zero-canon-attestation" not in lower_keys, (
        f"{EXPECTED_RED}: spoofed X-Zero-Canon-Attestation was not stripped"
    )


def test_zero_canon_fs_read_regular_file_nofollow_rejects_symlink_and_dir(
    tmp_path: Path,
) -> None:
    """ADR-001 AD-013 (W2-J): read_regular_file_nofollow uses O_NOFOLLOW+fstat(S_ISREG)."""
    reader = getattr(zero_canon_fs, "read_regular_file_nofollow", None)
    assert callable(reader), (
        f"{EXPECTED_RED}: core.zero_canon_fs lacks atomic read_regular_file_nofollow"
    )
    regular = tmp_path / "auth.json"
    regular.write_text(json.dumps({"api_key": DUMMY_API_KEY}), encoding="utf-8")
    link = tmp_path / "auth_link.json"
    link.symlink_to(regular)
    subdir = tmp_path / "dir_not_file"
    subdir.mkdir()

    assert DUMMY_API_KEY.encode("utf-8") in reader(regular)
    with pytest.raises((OSError, ValueError, RuntimeError)):
        reader(link)
    with pytest.raises((OSError, ValueError, RuntimeError)):
        reader(subdir)


def test_zero_canon_fs_write_atomic_0600_fail_closed_symlink_and_existing(
    tmp_path: Path,
) -> None:
    """ADR-001 AD-013 (W2-J): write_atomic_0600 enforces 0o600 and rejects existing/symlink."""
    payload = json.dumps({"api_key": DUMMY_API_KEY}).encode("utf-8")
    fresh = tmp_path / "fresh_auth.json"
    zero_canon_fs.write_atomic_0600(fresh, payload)
    assert stat.S_IMODE(fresh.stat().st_mode) == 0o600

    _assert_write_0600_rejected(
        fresh, b'{"api_key":"overwrite"}', "existing destination"
    )
    assert fresh.read_bytes() == payload

    target = tmp_path / "victim.json"
    target.write_bytes(b"original")
    symlink_dst = tmp_path / "link_auth.json"
    symlink_dst.symlink_to(target)
    _assert_write_0600_rejected(symlink_dst, payload, "symlink destination")
    assert symlink_dst.is_symlink()


def test_zero_canon_fs_prepare_codex_home_nofollow_and_modes(tmp_path: Path) -> None:
    """ADR-001 AD-013 (W2-J): prepare_codex_zero_canon_home filters config and nofollow."""
    prepare_fn = getattr(zero_canon_fs, "prepare_codex_zero_canon_home", None)
    assert callable(prepare_fn), (
        f"{EXPECTED_RED}: core.zero_canon_fs lacks prepare_codex_zero_canon_home"
    )
    codex_home, zc_root, base_env = _seed_fake_codex_home(tmp_path)
    isolated = prepare_fn(base_env, zc_root)
    dst_codex = Path(isolated["CODEX_HOME"])

    assert stat.S_IMODE(dst_codex.stat().st_mode) == 0o700
    assert stat.S_IMODE((dst_codex / "auth.json").stat().st_mode) == 0o600
    assert "BRIDGE_KEY" not in isolated and "INTERNAL_SERVICE_KEY" not in isolated
    cfg_text = (dst_codex / "config.toml").read_text(encoding="utf-8")
    assert "project_doc_max_bytes = 0" in cfg_text
    assert "mcp_servers" not in cfg_text and "hooks" not in cfg_text

    real_auth = tmp_path / "outside_auth.json"
    real_auth.write_text("{}", encoding="utf-8")
    (codex_home / "auth.json").unlink()
    (codex_home / "auth.json").symlink_to(real_auth)
    zc_root_2 = tmp_path / "zc-turn-2"
    zc_root_2.mkdir(mode=0o700)
    with pytest.raises((OSError, ValueError, RuntimeError)):
        prepare_fn(base_env, zc_root_2)


def test_codex_zero_canon_ephemeral_route_no_resident_reuse(tmp_path: Path) -> None:
    """ADR-001 AD-013 (W2-J): Codex Zero-Canon routes to KIND_EPHEMERAL with clean-home."""
    route = decide_zero_canon_route(
        "Zero-Canon",
        "codex-app-server-v2",
        environ={},
        backend_id="codex",
    )
    assert route.kind == KIND_EPHEMERAL and route.is_ephemeral is True
    assert route.kind != KIND_RESIDENT

    prepare_fn = getattr(zero_canon_fs, "prepare_codex_zero_canon_home", None)
    assert callable(prepare_fn), (
        f"{EXPECTED_RED}: ephemeral Zero-Canon turn lacks prepare_codex_zero_canon_home"
    )
    _, zc_root, base_env = _seed_fake_codex_home(tmp_path)
    env_out = prepare_fn(base_env, zc_root)
    assert env_out["HOME"] == str(zc_root)


def test_codex_driver_clean_home_rejects_symlink_auth(tmp_path: Path) -> None:
    """ADR-001 AD-013 (W2-A): driver clean-home must fail closed on symlink auth.json."""
    codex_home, zc_root, base_env = _seed_fake_codex_home(tmp_path)
    outside = tmp_path / "outside_secret.json"
    outside.write_text(json.dumps({"OPENAI_API_KEY": DUMMY_API_KEY}), encoding="utf-8")
    (codex_home / "auth.json").unlink()
    (codex_home / "auth.json").symlink_to(outside)

    driver = CodexAppServerDriver()
    try:
        driver.build_zero_canon_env(base_env, str(zc_root))
    except (OSError, ValueError, RuntimeError):
        return
    pytest.fail(
        f"{EXPECTED_RED}: CodexAppServerDriver.build_zero_canon_env ignored symlink auth"
    )


def test_zero_canon_sse_error_redacts_dummy_secret_before_truncation() -> None:
    """ADR-001 Stream/error boundary: build_turn_error redacts secrets before serialization."""
    resp = build_turn_error(
        RuntimeError(f"upstream failed with Bearer {DUMMY_API_KEY}")
    )
    assert DUMMY_API_KEY not in resp.message, (
        f"{EXPECTED_RED}: turn_error_sse leaked dummy secret in message"
    )
    assert DUMMY_API_KEY not in resp.sse, (
        f"{EXPECTED_RED}: turn_error_sse leaked dummy secret in SSE payload"
    )
    assert DUMMY_API_KEY not in json.dumps(resp.body), (
        f"{EXPECTED_RED}: turn_error_sse leaked dummy secret in JSON body"
    )
    assert resp.code
