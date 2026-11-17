"""L1: горячая перезагрузка `.env` (core/env_hot_reload.py) и ключа PassthroughAdapter."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.env_hot_reload import (
    DEFAULT_ENV_CACHE_TTL_S,
    EnvHotReloadCache,
    get_env_cache,
    get_hot_env_value,
    parse_env_text,
    resolve_env_cache_ttl_s,
    resolve_env_file_path,
)


class _Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def _bump(path: Path, text: str) -> None:
    """Записать файл и гарантированно сменить mtime_ns/size."""
    before = path.stat().st_mtime_ns if path.exists() else 0
    path.write_text(text, encoding="utf-8")
    os.utime(path, ns=(before + 10_000_000, before + 10_000_000))


def test_parse_env_text_handles_export_quotes_and_comments() -> None:
    parsed = parse_env_text(
        "# c\nA=1\nexport B='two words'\nC=\"x\" # tail\nD=val # inline\nbroken\nE='open\n"
    )
    assert parsed == {"A": "1", "B": "two words", "C": "x", "D": "val"}


def test_defaults_and_safe_config_parsing() -> None:
    assert resolve_env_file_path({}) == Path("~/.dsh/.env").expanduser()
    assert resolve_env_file_path({"BRIDGE_ENV_FILE_PATH": "/tmp/x.env"}) == Path("/tmp/x.env")
    assert resolve_env_cache_ttl_s({}) == DEFAULT_ENV_CACHE_TTL_S == 2.0
    for bad in ("abc", "-1", "nan", "inf"):
        assert resolve_env_cache_ttl_s({"BRIDGE_ENV_CACHE_TTL_S": bad}) == 2.0
    assert resolve_env_cache_ttl_s({"BRIDGE_ENV_CACHE_TTL_S": "0.5"}) == 0.5


def test_rotation_visible_only_after_ttl_and_signature_change(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=old\n", encoding="utf-8")
    clock = _Clock()
    cache = EnvHotReloadCache(env_file, 2.0, environ={}, clock=clock)
    assert cache.get("KEY") == "old"
    _bump(env_file, "KEY=newer-value\n")
    clock.now += 1.0
    assert cache.get("KEY") == "old"  # TTL ещё не истёк
    clock.now += 1.5
    assert cache.get("KEY") == "newer-value"


def test_falls_back_to_environment_and_default(tmp_path: Path) -> None:
    cache = EnvHotReloadCache(tmp_path / "missing.env", 0, environ={"K": "from-env"})
    assert cache.get("K") == "from-env"
    assert cache.get("NOPE", "dflt") == "dflt"


def test_file_value_wins_over_environment_and_missing_key_falls_back(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("A=file\n", encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={"A": "env", "B": "env-b"})
    assert cache.get("A") == "file"
    assert cache.get("B") == "env-b"


def test_unreadable_or_truncated_file_keeps_last_valid_snapshot(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=good\n", encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={})
    assert cache.get("KEY") == "good"
    _bump(env_file, "garbage without equals\n")  # запись «на лету»: непустой файл без пар
    assert cache.get("KEY") == "good"
    _bump(env_file, "KEY=fixed\n")
    assert cache.get("KEY") == "fixed"


def test_missing_file_after_seen_drops_overrides(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=file\n", encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={"KEY": "env"})
    assert cache.get("KEY") == "file"
    env_file.unlink()
    assert cache.get("KEY") == "env"


def test_warning_logged_once_per_transition_without_secret(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=super-secret-value\n", encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={})
    assert cache.get("KEY")
    env_file.unlink()
    with caplog.at_level("WARNING", logger="core.env_hot_reload"):
        cache.get("KEY")
        cache.get("KEY")
    assert len([r for r in caplog.records if "file_missing" in r.getMessage()]) == 1
    assert "super-secret-value" not in caplog.text


def test_shared_cache_follows_env_configuration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / "shared.env"
    env_file.write_text("SHARED_K=1\n", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("BRIDGE_ENV_CACHE_TTL_S", "0")
    assert get_hot_env_value("SHARED_K") == "1"
    _bump(env_file, "SHARED_K=22\n")
    assert get_hot_env_value("SHARED_K") == "22"


def test_passthrough_adapter_reads_rotated_key_per_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from adapters.passthrough_adapter import PassthroughAdapter

    env_file = tmp_path / ".env"
    env_file.write_text("PT_TEST_KEY=first-key\n", encoding="utf-8")
    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(env_file))
    monkeypatch.setenv("BRIDGE_ENV_CACHE_TTL_S", "0")
    monkeypatch.delenv("PT_TEST_KEY", raising=False)
    adapter = PassthroughAdapter(
        "pt-test",
        {"base_url": "http://127.0.0.1:9999/v1", "api_key_env": "PT_TEST_KEY"},
        lambda: {"models": []},
    )
    assert adapter.validate_client_token("first-key")
    _bump(env_file, "PT_TEST_KEY=rotated-key\n")
    assert adapter.validate_client_token("rotated-key")
    assert not adapter.validate_client_token("first-key")
    assert adapter._upstream_key == "rotated-key"
    adapter._upstream_key = "explicit"
    assert adapter._upstream_key == "explicit"


@pytest.mark.parametrize("declare_env", [False, True])
def test_passthrough_adapter_static_key_only_without_declared_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, declare_env: bool
) -> None:
    from adapters.passthrough_adapter import PassthroughAdapter

    monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(tmp_path / "none.env"))
    monkeypatch.delenv("PT_NOENV_KEY", raising=False)
    config = {"base_url": "http://127.0.0.1:9999/v1", "api_key": "static"}
    if declare_env:
        config["api_key_env"] = "PT_NOENV_KEY"
    adapter = PassthroughAdapter("pt-test2", config, lambda: {"models": []})
    try:
        assert adapter._upstream_key == ("" if declare_env else "static")
        assert adapter.validate_client_token("static") is (not declare_env)
    finally:
        adapter.shutdown()


def test_explicit_empty_value_revokes_stale_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text('KEY=""\nOTHER=x\n', encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={"KEY": "stale", "ABSENT": "from-env"})
    assert cache.get("KEY", "dflt") == ""
    assert cache.get("ABSENT", "dflt") == "from-env"
    assert cache.get("NOPE", "dflt") == "dflt"


def test_truncated_to_zero_bytes_keeps_last_valid_snapshot(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("KEY=good-value\n", encoding="utf-8")
    cache = EnvHotReloadCache(env_file, 0, environ={})
    assert cache.get("KEY") == "good-value"
    env_file.write_text("", encoding="utf-8")  # `>`-усечение перед записью нового содержимого
    with caplog.at_level("WARNING", logger="core.env_hot_reload"):
        assert cache.get("KEY") == "good-value"
        assert cache.get("KEY") == "good-value"
    assert len([r for r in caplog.records if "file_truncated" in r.getMessage()]) == 1
    _bump(env_file, "KEY=rewritten\n")
    assert cache.get("KEY") == "rewritten"


def test_escaped_quotes_in_quoted_values() -> None:
    parsed = parse_env_text(
        'A="foo\\"bar"\nB=\'it\\\'s\'\nC="back\\\\slash" # c\nD="x\\"\nE="a" junk\n'
    )
    # D (нет закрывающей кавычки) и E (мусор после значения) отбрасываются.
    assert parsed == {"A": 'foo"bar', "B": "it's", "C": "back\\slash"}


def test_shared_cache_registry_is_bounded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core import env_hot_reload as mod

    monkeypatch.setenv("BRIDGE_ENV_CACHE_MAX_INSTANCES", "3")
    monkeypatch.setattr(mod, "_CACHES", mod.OrderedDict())
    for i in range(10):
        monkeypatch.setenv("BRIDGE_ENV_FILE_PATH", str(tmp_path / f"{i}.env"))
        get_env_cache()
    assert len(mod._CACHES) == 3
    monkeypatch.setenv("BRIDGE_ENV_CACHE_MAX_INSTANCES", "garbage")
    assert mod.resolve_env_cache_max_instances() == 32
    assert mod.resolve_env_cache_max_instances({"BRIDGE_ENV_CACHE_MAX_INSTANCES": "0"}) == 32
