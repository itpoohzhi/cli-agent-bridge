"""Регрессии нормализации cache usage, affinity и внутреннего SSE."""

import copy
import fcntl
import hashlib
import importlib
import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.nonstream_aggregator import CACHE_KEYS_TO_CLEAN, _wire_usage, internal_stream_body
from core.usage_wire import _is_count, build_wire_usage, extract_cache_read_tokens


@pytest.mark.parametrize(
    "usage",
    [
        {"prompt_cache_hit_tokens": 40},
        {"cached_tokens": 40},
        {"prompt_tokens_details": {"cached_tokens": 40}},
    ],
)
def test_new_cache_representations(usage):
    count = extract_cache_read_tokens(usage)
    assert count == 40
    wire, inconsistent = build_wire_usage(100, 5, count, input_includes_cache=True)
    assert not inconsistent
    assert wire["prompt_tokens_details"]["cached_tokens"] == 40
    assert "cached_tokens" not in wire


@pytest.mark.parametrize("bad", [None, True, -1, "40", 1.5, [], {}])
def test_new_cache_representations_invalid(bad):
    for usage in (
        {"prompt_cache_hit_tokens": bad},
        {"cached_tokens": bad},
        {"prompt_tokens_details": {"cached_tokens": bad}},
    ):
        assert extract_cache_read_tokens(usage) is None


def test_deepseek_has_precedence_without_double_counting():
    assert extract_cache_read_tokens(
        {
            "prompt_cache_hit_tokens": 0,
            "cached_tokens": 40,
            "prompt_tokens_details": {"cached_tokens": 50},
        }
    ) == 50


def test_extract_cache_read_tokens_supports_sdk_objects():
    class Details:
        cached_tokens = 41

    class Usage:
        prompt_tokens_details = Details()
        cached_tokens = 12

    assert extract_cache_read_tokens(Usage()) == 41


@pytest.mark.parametrize(
    "value, expected",
    [(0, True), (5, True), (True, False), (False, False), (-1, False), ("5", False)],
)
def test_is_count_strictly_excludes_bool(value, expected):
    assert _is_count(value) is expected


def test_internal_stream_requests_usage(monkeypatch):
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_INTERNAL_STREAM_USAGE_ENABLED", "true")
    request = {
        "model": "m",
        "stream": False,
        "stream_options": {"other": 1, "include_usage": False},
    }
    saved = copy.deepcopy(request)
    result = json.loads(
        internal_stream_body("/v1/chat/completions", request, json.dumps(request).encode())
    )
    assert result["stream_options"] == {"other": 1, "include_usage": True}
    assert request == saved


def test_internal_stream_body_respects_supports_stream_options(monkeypatch):
    monkeypatch.setenv("BRIDGE_NONSTREAM_VIA_STREAM_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_INTERNAL_STREAM_USAGE_ENABLED", "true")
    request = {
        "model": "m",
        "stream": False,
        "stream_options": {"other": 1, "include_usage": False},
    }
    saved = copy.deepcopy(request)
    result = json.loads(
        internal_stream_body(
            "/v1/chat/completions",
            request,
            json.dumps(request).encode(),
            supports_stream_options=False,
        )
    )
    assert result["stream"] is True
    assert "stream_options" not in result
    assert request == saved


def _reload_affinity(monkeypatch, *, enabled=True, salt_file=None, salt=None):
    monkeypatch.setenv(
        "BRIDGE_STABLE_SESSION_AFFINITY_ENABLED", "true" if enabled else "false"
    )
    if salt_file is None:
        monkeypatch.delenv("BRIDGE_AFFINITY_SALT_FILE", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_AFFINITY_SALT_FILE", str(salt_file))
    if salt is None:
        monkeypatch.delenv("BRIDGE_SESSION_AFFINITY_SALT", raising=False)
    else:
        monkeypatch.setenv("BRIDGE_SESSION_AFFINITY_SALT", salt)
    return importlib.reload(importlib.import_module("core.session_affinity"))


def _affinity_value(affinity, request, headers=None, namespace="openai"):
    return affinity.session_affinity(json.dumps(request).encode(), headers or {}, namespace)


def _scope_value(affinity, request, headers=None, namespace="openai"):
    return affinity.request_scope(json.dumps(request).encode(), headers or {}, namespace)


def test_session_affinity_import_is_lazy_when_disabled(tmp_path, monkeypatch):
    salt_file = tmp_path / "state" / "salt.bin"
    affinity = _reload_affinity(monkeypatch, enabled=False, salt_file=salt_file)
    request = {"model": "m", "messages": [{"role": "user", "content": "x"}]}
    affinity.session_affinity(json.dumps(request).encode(), {}, "openai")
    assert affinity._SALT is None
    assert not salt_file.exists()


def test_session_affinity_default_path_is_under_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    affinity = _reload_affinity(monkeypatch)
    request = {"model": "m", "messages": [{"role": "user", "content": "x"}]}
    affinity.session_affinity(json.dumps(request).encode(), {}, "openai")
    salt_file = tmp_path / ".dsh" / "state" / "affinity_salt.bin"
    assert len(salt_file.read_bytes()) == 32
    assert stat.S_IMODE(salt_file.stat().st_mode) == 0o600
    assert stat.S_IMODE(salt_file.parent.stat().st_mode) == 0o700


def test_session_affinity_preserves_existing_parent_permissions(tmp_path, monkeypatch):
    parent = tmp_path / "state"
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    salt_file = parent / "salt.bin"
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    affinity._get_salt()
    assert stat.S_IMODE(parent.stat().st_mode) == 0o755


def test_session_affinity_unsafe_parent_falls_back_to_memory(tmp_path, monkeypatch):
    parent = tmp_path / "shared"
    parent.mkdir()
    parent.chmod(0o777)
    salt_file = parent / "salt.bin"
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    result = affinity._get_salt()
    assert len(result) == 32
    assert not salt_file.exists()
    assert not Path(f"{salt_file}.lock").exists()


def test_session_affinity_rewrites_corrupt_salt_atomically(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    salt_file.write_bytes(b"short")
    salt_file.chmod(0o600)
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    result = affinity._get_salt()
    assert len(result) == 32
    assert salt_file.read_bytes() == result
    assert not list(tmp_path.glob("salt.bin.tmp.*"))


def test_session_affinity_unsafe_permissions_fall_back_to_memory(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    salt_file.write_bytes(b"x" * 32)
    salt_file.chmod(0o644)
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    result = affinity._get_salt()
    assert len(result) == 32
    assert result != b"x" * 32


def test_session_affinity_read_and_lock_use_nonblocking_flags(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    salt_file.write_bytes(b"x" * 32)
    salt_file.chmod(0o600)
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    real_open = affinity.os.open
    real_flock = affinity.fcntl.flock
    seen_open = []
    seen_flock = []

    def recording_open(path, flags, *args):
        seen_open.append((str(path), flags))
        return real_open(path, flags, *args)

    def recording_flock(fd, operation):
        seen_flock.append(operation)
        return real_flock(fd, operation)

    monkeypatch.setattr(affinity.os, "open", recording_open)
    monkeypatch.setattr(affinity.fcntl, "flock", recording_flock)
    assert affinity._read_salt(str(salt_file)) == b"x" * 32
    with affinity._file_lock(str(salt_file)):
        pass
    nonblock = getattr(os, "O_NONBLOCK", 0)
    assert nonblock
    assert seen_open[0][1] & nonblock
    lock_flags = next(flags for path, flags in seen_open if path.endswith(".lock"))
    assert lock_flags & nonblock
    assert fcntl.LOCK_EX | fcntl.LOCK_NB in seen_flock


def test_session_affinity_busy_flock_raises_and_uses_memory_salt(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    salt_file.write_bytes(b"x" * 32)
    salt_file.chmod(0o600)
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    lock_path = Path(f"{salt_file}.lock")
    lock_path.touch(mode=0o600)
    lock_path.chmod(0o600)
    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(affinity.SaltLockBusyError):
            with affinity._file_lock(str(salt_file)):
                pass

        def fail_disk_io(*args, **kwargs):
            raise AssertionError("disk I/O must not happen on busy lock")

        monkeypatch.setattr(affinity, "_read_salt", fail_disk_io)
        monkeypatch.setattr(affinity, "_write_salt_atomically", fail_disk_io)
        result = affinity._get_salt()
        assert len(result) == 32
        assert result != b"x" * 32
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def test_salt_lock_busy_error_does_not_memoize_emergency_salt(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    persisted_salt = b"p" * 32
    salt_file.write_bytes(persisted_salt)
    salt_file.chmod(0o600)
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)
    lock_path = Path(f"{salt_file}.lock")
    lock_path.touch(mode=0o600)
    lock_path.chmod(0o600)
    fd = os.open(lock_path, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        emergency_salt = affinity._get_salt()
        assert len(emergency_salt) == 32
        assert emergency_salt != persisted_salt
        assert affinity._SALT is None
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    loaded_salt = affinity._get_salt()
    assert loaded_salt == persisted_salt
    assert affinity._SALT == persisted_salt


def test_session_affinity_lock_error_falls_back_without_hanging(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file)

    def busy(*args):
        raise BlockingIOError("busy")

    def fail_disk_io(*args, **kwargs):
        raise AssertionError("disk I/O must not happen on busy lock")

    monkeypatch.setattr(affinity.fcntl, "flock", busy)
    monkeypatch.setattr(affinity, "_read_salt", fail_disk_io)
    monkeypatch.setattr(affinity, "_write_salt_atomically", fail_disk_io)
    result = affinity._get_salt()
    assert len(result) == 32
    assert not salt_file.exists()


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFO is not supported")
def test_session_affinity_rejects_fifo_salt_and_lock(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    salt_fifo = tmp_path / "salt-fifo"
    os.mkfifo(salt_fifo, 0o600)
    with pytest.raises(PermissionError, match="unsafe salt file"):
        affinity._read_salt(str(salt_fifo))

    lock_target = tmp_path / "locked-salt"
    os.mkfifo(f"{lock_target}.lock", 0o600)
    with pytest.raises(PermissionError, match="unsafe lock file"):
        with affinity._file_lock(str(lock_target)):
            pass


def test_session_affinity_rejects_short_environment_salt(tmp_path, monkeypatch):
    salt_file = tmp_path / "salt.bin"
    affinity = _reload_affinity(monkeypatch, salt_file=salt_file, salt="short")
    result = affinity._get_salt()
    assert len(result) == 32
    assert salt_file.read_bytes() == result
    assert result != hashlib.sha256(b"short").digest()


def test_session_affinity_salt_is_deterministic(monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt="regression-salt-16-bytes")
    expected = hashlib.sha256(b"regression-salt-16-bytes").digest()
    assert affinity._get_salt() == expected
    request = {
        "model": "m",
        "messages": [{"role": "user", "content": "salted dialog"}],
    }
    first = _affinity_value(affinity, request)
    affinity = importlib.reload(affinity)
    assert _affinity_value(affinity, request) == first


def test_fallback_affinity_is_stable_between_dialog_turns(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    turn_one = {
        "model": "m",
        "messages": [
            {"role": "system", "content": "stable dialog anchor"},
            {"role": "user", "content": "first question"},
        ],
    }
    turn_two = copy.deepcopy(turn_one)
    turn_two["messages"].extend(
        [
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
        ]
    )
    assert _affinity_value(affinity, turn_one) == _affinity_value(affinity, turn_two)


def test_responses_input_string_affects_affinity(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    first = {"model": "m", "instructions": "same", "input": "first question"}
    second = {"model": "m", "instructions": "same", "input": "different question"}
    assert _affinity_value(affinity, first) != _affinity_value(affinity, second)


def test_responses_previous_response_id_does_not_affect_unregistered_affinity(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    first = {
        "model": "m",
        "instructions": "stable instructions",
        "previous_response_id": "resp_first",
        "input": "first question",
    }
    second = copy.deepcopy(first)
    second["previous_response_id"] = "resp_second"
    assert _affinity_value(affinity, first) == _affinity_value(affinity, second)


def test_responses_registered_chain_inherits_parent_affinity(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    first = {"model": "m", "instructions": "same", "input": "first question"}
    parent_affinity = _affinity_value(affinity, first)
    scope = _scope_value(affinity, first)
    affinity.register_response_affinity("resp_parent", parent_affinity, scope=scope)
    child = {
        "model": "m",
        "previous_response_id": "resp_parent",
        "input": "completely different question",
    }
    assert _affinity_value(affinity, child) == parent_affinity


def test_passthrough_adapter_registers_response_affinity_on_200(tmp_path, monkeypatch):
    import adapters.passthrough_adapter as pa

    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    monkeypatch.setattr(pa, "session_affinity", affinity.session_affinity)
    monkeypatch.setattr(pa, "register_response_affinity", affinity.register_response_affinity)
    monkeypatch.setattr(pa, "request_scope", affinity.request_scope)

    adapter = pa.PassthroughAdapter.__new__(pa.PassthroughAdapter)
    adapter.id = "openai"
    adapter.config = {"per_request_headers": {"x-session-id": "{session_affinity}"}}
    monkeypatch.setattr(adapter, "_read_json_headers", lambda: {})
    monkeypatch.setattr(adapter, "_sanitize_enabled", lambda: False)
    monkeypatch.setattr(adapter, "_request_mode", lambda req: None)
    response_body = json.dumps({"id": "resp_xyz", "output": []}).encode()
    monkeypatch.setattr(adapter, "_response_body", lambda r, k: (response_body, False))
    monkeypatch.setattr(adapter, "_normalize_body", lambda r, pair, k: pair[0])
    monkeypatch.setattr(adapter, "_emit_response", lambda r, s, pair: True)

    req_one = {"model": "m", "instructions": "same", "input": "first question"}
    raw_one = json.dumps(req_one).encode()
    headers = {"api-key": "alice"}
    r_kw = {}
    upstream_headers_one = adapter._upstream_headers(raw_one, headers, affinity_out=r_kw)
    first_uuid = upstream_headers_one["x-session-id"]
    assert r_kw["affinity_uuid"] == first_uuid
    assert r_kw["affinity_scope"] == affinity.request_scope(raw_one, headers, adapter.id)

    resp = SimpleNamespace(
        status=200,
        getheader=lambda name, default=None: "application/json",
    )
    assert adapter._respond(resp, req_one, object(), None, **r_kw) is True

    req_two = {
        "model": "m",
        "previous_response_id": "resp_xyz",
        "input": "completely different question",
    }
    raw_two = json.dumps(req_two).encode()
    r_kw_two = {}
    upstream_headers_two = adapter._upstream_headers(raw_two, headers, affinity_out=r_kw_two)
    assert upstream_headers_two["x-session-id"] == first_uuid
    assert r_kw_two["affinity_uuid"] == first_uuid


def test_responses_registered_chain_is_scoped_by_tenant_model_namespace(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    alice_headers = {"api-key": "alice"}
    bob_headers = {"api-key": "bob"}
    first = {"model": "m", "instructions": "same", "input": "first question"}
    alice_affinity = _affinity_value(affinity, first, headers=alice_headers)
    alice_scope = _scope_value(affinity, first, headers=alice_headers)
    affinity.register_response_affinity("resp_shared", alice_affinity, scope=alice_scope)
    affinity.register_response_affinity("resp_unscoped", "unscoped-affinity")

    # Чужой API-ключ не наследует чужую цепочку.
    bob_child = {
        "model": "m",
        "previous_response_id": "resp_shared",
        "input": "completely different question",
    }
    assert _affinity_value(affinity, bob_child, headers=bob_headers) != alice_affinity

    # Другая модель или namespace также не наследуют цепочку.
    other_model_child = {**bob_child, "model": "other-model"}
    assert _affinity_value(affinity, other_model_child, headers=alice_headers) != alice_affinity
    assert _affinity_value(affinity, bob_child, headers=alice_headers, namespace="anthropic") != alice_affinity

    # Нескоупированная запись не сопоставляется со scoped-запросом.
    unscoped_probe = {**bob_child, "previous_response_id": "resp_unscoped"}
    assert _affinity_value(affinity, unscoped_probe, headers=alice_headers) != "unscoped-affinity"


def test_response_chain_registry_is_lru_bounded(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    monkeypatch.setattr(affinity, "_MAX_RESPONSE_CHAINS", 2)
    affinity.register_response_affinity("one", "a", scope="s")
    affinity.register_response_affinity("two", "b", scope="s")
    affinity.register_response_affinity("three", "c", scope="s")
    assert "s:one" not in affinity._RESPONSE_CHAINS
    assert set(affinity._RESPONSE_CHAINS.keys()) == {"s:two", "s:three"}
    assert affinity._RESPONSE_CHAINS["s:two"][0] == "b"
    assert affinity._RESPONSE_CHAINS["s:three"][0] == "c"


def test_response_chain_registry_respects_ttl_and_env_config(tmp_path, monkeypatch):
    monkeypatch.setenv("BRIDGE_AFFINITY_MAX_CHAINS", "2")
    monkeypatch.setenv("BRIDGE_AFFINITY_TTL_S", "10")
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    now = [1000.0]
    monkeypatch.setattr(affinity.time, "monotonic", lambda: now[0])
    affinity.register_response_affinity("r1", "a1", scope="s1")
    assert affinity._response_chain_affinity("r1", scope="s1") == "a1"
    now[0] = 1011.0
    assert affinity._response_chain_affinity("r1", scope="s1") is None


@pytest.mark.parametrize(
    "req_payload,headers",
    [
        ({"session_id": "dialog-1"}, {}),
        ({"conversation_id": "dialog-1"}, {}),
        ({}, {"x-session-id": "dialog-1"}),
        ({}, {"x-opencode-session": "dialog-1"}),
    ],
)
def test_explicit_session_identifiers_stabilize_affinity(
    tmp_path, monkeypatch, req_payload, headers
):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    first = {"model": "m", "input": "first", **req_payload}
    second = {"model": "m", "input": "different", **req_payload}
    assert _affinity_value(affinity, first, headers) == _affinity_value(
        affinity, second, headers
    )


def test_responses_multiturn_affinity_uses_only_first_user_turn(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    turn_one = {
        "model": "m",
        "instructions": "stable instructions",
        "previous_response_id": "resp_1",
        "input": [
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "input_text", "text": "first question"}],
            }
        ],
    }
    turn_two = copy.deepcopy(turn_one)
    turn_two["previous_response_id"] = "resp_2"
    turn_two["input"].extend(
        [
            {
                "role": "assistant",
                "type": "message",
                "content": [{"type": "output_text", "text": "first answer"}],
            },
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "input_text", "text": "second question"}],
            },
        ]
    )
    assert _affinity_value(affinity, turn_one) == _affinity_value(affinity, turn_two)


def test_responses_affinity_distinguishes_roles(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    user = {
        "model": "m",
        "input": [{"role": "user", "type": "message", "content": "same text"}],
    }
    assistant = {
        "model": "m",
        "input": [
            {"role": "assistant", "type": "message", "content": "same text"}
        ],
    }
    assert _affinity_value(affinity, user) != _affinity_value(affinity, assistant)


def test_responses_affinity_distinguishes_content_types(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    first = {
        "model": "m",
        "input": [
            {
                "role": "user",
                "type": "message",
                "content": [{"type": "input_text", "text": "same"}],
            }
        ],
    }
    second = copy.deepcopy(first)
    second["input"][0]["content"][0]["type"] = "output_text"
    assert _affinity_value(affinity, first) != _affinity_value(affinity, second)


def test_session_affinity_scope_isolated_by_api_key(tmp_path, monkeypatch):
    affinity = _reload_affinity(monkeypatch, salt_file=tmp_path / "salt.bin")
    request = {
        "model": "m",
        "messages": [{"role": "user", "content": "same dialog"}],
    }
    assert _affinity_value(affinity, request, {"API-Key": "alice"}) != _affinity_value(
        affinity, request, {"api-key": "bob"}
    )


def test_nonstream_usage_deep_merges_prompt_details_and_recomputes_total():
    result = _wire_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 5,
            "total_tokens": 999,
            "prompt_tokens_details": {"cached_tokens": 40, "audio_tokens": 17},
        }
    )
    assert result["prompt_tokens_details"] == {
        "cached_tokens": 40,
        "audio_tokens": 17,
    }
    assert "cached_tokens" not in result
    assert result["total_tokens"] == 105


def test_nonstream_usage_preserves_audio_tokens_without_cache():
    result = _wire_usage(
        {
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "prompt_tokens_details": {"audio_tokens": 7},
        }
    )
    assert result["prompt_tokens_details"] == {"audio_tokens": 7}
    assert "cached_tokens" not in result
    assert result["total_tokens"] == 12


def test_nonstream_anthropic_input_tokens_exclude_cache_read_tokens():
    result = _wire_usage(
        {
            "input_tokens": 100,
            "output_tokens": 5,
            "cache_read_input_tokens": 40,
        }
    )
    assert result["prompt_tokens"] == 140
    assert result["completion_tokens"] == 5
    assert result["prompt_tokens_details"] == {"cached_tokens": 40}
    assert "cached_tokens" not in result
    assert result["total_tokens"] == 145
    assert "input_tokens" not in result
    assert "output_tokens" not in result


def test_nonstream_anthropic_cache_creation_is_added_and_all_raw_keys_removed():
    result = _wire_usage(
        {
            "input_tokens": 100,
            "output_tokens": 5,
            "cache_read_input_tokens": 40,
            "cache_creation_tokens": 1,
            "cache_creation_input_tokens": 20,
            "cacheCreationTokens": 2,
        }
    )
    assert result["prompt_tokens"] == 142
    assert result["completion_tokens"] == 5
    assert result["prompt_tokens_details"]["cached_tokens"] == 40
    assert "cached_tokens" not in result
    assert result["total_tokens"] == 147
    for key in (
        "cache_creation_tokens",
        "cache_creation_input_tokens",
        "cacheCreationTokens",
        "input_tokens",
        "output_tokens",
    ):
        assert key not in result


@pytest.mark.parametrize("bad_total", [True, False, -1, "999"])
def test_nonstream_usage_never_preserves_invalid_or_inconsistent_total(bad_total):
    result = _wire_usage(
        {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": bad_total}
    )
    assert result["total_tokens"] == 12


def test_nonstream_inconsistent_cache_drops_cache_keys_and_preserves_details():
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 2,
        "prompt_tokens_details": {"cached_tokens": 20, "audio_tokens": 7},
    }
    for key in CACHE_KEYS_TO_CLEAN:
        if key != "prompt_tokens_details":
            usage[key] = 20
    result = _wire_usage(usage)
    assert result["prompt_tokens_details"] == {"audio_tokens": 7}
    for key in CACHE_KEYS_TO_CLEAN:
        if key != "prompt_tokens_details":
            assert key not in result
    assert result["total_tokens"] == 12


@pytest.mark.parametrize("bad", [-1, True, False, "4"])
def test_nonstream_usage_removes_all_invalid_cache_aliases(bad):
    usage = {
        "prompt_tokens": 10,
        "completion_tokens": 2,
        "prompt_tokens_details": {"cached_tokens": bad},
        "cached_tokens": bad,
        "prompt_cache_hit_tokens": bad,
        "cache_read_tokens": bad,
        "cache_read_input_tokens": bad,
        "cacheReadTokens": bad,
        "cachedTokens": bad,
        "cache_creation_tokens": bad,
        "cache_creation_input_tokens": bad,
        "cacheCreationTokens": bad,
        "input_tokens": bad,
        "output_tokens": bad,
    }
    result = _wire_usage(usage)
    for key in CACHE_KEYS_TO_CLEAN:
        assert key not in result
    assert result["total_tokens"] == 12


def test_nonstream_valid_cache_removes_noncanonical_aliases():
    result = _wire_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 5,
            "prompt_cache_hit_tokens": 40,
            "cache_read_tokens": True,
            "cache_read_input_tokens": -1,
            "cacheReadTokens": "bad",
            "cachedTokens": False,
        }
    )
    assert result["prompt_tokens_details"] == {"cached_tokens": 40}
    assert "cached_tokens" not in result
    for key in (
        "prompt_cache_hit_tokens",
        "cache_read_tokens",
        "cache_read_input_tokens",
        "cacheReadTokens",
        "cachedTokens",
    ):
        assert key not in result
    assert result["total_tokens"] == 105


def test_nonstream_usage_drops_top_level_cached_tokens():
    result = _wire_usage(
        {
            "prompt_tokens": 100,
            "completion_tokens": 5,
            "cached_tokens": 40,
        }
    )
    assert result["prompt_tokens_details"] == {"cached_tokens": 40}
    assert "cached_tokens" not in result
    assert result["total_tokens"] == 105


def test_supports_stream_options_prioritizes_explicit_config_over_heuristic():
    from adapters.passthrough_adapter import PassthroughAdapter

    method = PassthroughAdapter._supports_stream_options
    explicit_true = SimpleNamespace(config={"supports_stream_options": True})
    explicit_false = SimpleNamespace(config={"supports_stream_options": False})
    unconfigured = SimpleNamespace(config={})
    explicit_none = SimpleNamespace(config={"supports_stream_options": None})

    for model in ("claude-3-7-sonnet", "vendor-anthropic-model"):
        assert method(explicit_true, "/v1/chat/completions", {"model": model}) is True
        assert method(unconfigured, "/v1/chat/completions", {"model": model}) is False
        assert method(explicit_none, "/v1/chat/completions", {"model": model}) is False

    assert method(explicit_false, "/v1/chat/completions", {"model": "gpt-4o"}) is False
    assert method(unconfigured, "/v1/chat/completions", {"model": "gpt-4o"}) is True
    assert method(explicit_none, "/v1/chat/completions", {"model": "gpt-4o"}) is True
    assert method(explicit_true, "/v1/responses", {"model": "gpt-4o"}) is False


def test_request_scope_default_off_does_not_create_salt_file(tmp_path, monkeypatch):
    """При default-OFF request_scope возвращает пустую строку и не создает affinity_salt.bin."""
    import core.session_affinity as sa

    salt_file = tmp_path / "affinity_salt.bin"
    monkeypatch.setenv("BRIDGE_AFFINITY_SALT_FILE", str(salt_file))
    monkeypatch.delenv("BRIDGE_SESSION_AFFINITY_SALT", raising=False)
    monkeypatch.setattr(sa, "_SALT", None)

    monkeypatch.delenv("BRIDGE_STABLE_SESSION_AFFINITY_ENABLED", raising=False)
    assert sa.request_scope(b'{"model": "gpt-5"}', {"Authorization": "Bearer secret"}, "ns") == ""
    assert not salt_file.exists()
    assert sa._SALT is None

    monkeypatch.setenv("BRIDGE_STABLE_SESSION_AFFINITY_ENABLED", "0")
    assert sa.request_scope(b'{"model": "gpt-5"}', {"Authorization": "Bearer secret"}, "ns") == ""
    assert not salt_file.exists()
    assert sa._SALT is None


def test_passthrough_adapter_propagates_affinity_to_respond(monkeypatch):
    """_upstream_headers -> _respond пробрасывает affinity и регистрирует response_id при 200."""
    from unittest.mock import MagicMock

    import core.session_affinity as sa
    from adapters.passthrough_adapter import PassthroughAdapter

    monkeypatch.setenv("BRIDGE_STABLE_SESSION_AFFINITY_ENABLED", "1")
    monkeypatch.setenv("BRIDGE_SESSION_AFFINITY_SALT", "test-salt-0123456789abcdef")
    monkeypatch.setattr(sa, "_SALT", None)
    monkeypatch.setattr(sa, "_RESPONSE_CHAINS", {})

    adapter = PassthroughAdapter.__new__(PassthroughAdapter)
    adapter.id = "test-upstream"
    adapter.config = {"per_request_headers": {"X-Session-Affinity": "{session_affinity}"}}
    adapter._read_json_headers = lambda: {}
    adapter._sanitize_enabled = lambda: False
    adapter._request_mode = lambda req: None
    adapter._response_body = lambda resp, kw: (b'{"id": "resp_chain_001"}', False)
    adapter._normalize_body = lambda resp, body_agg, kw: body_agg[0]
    adapter._emit_response = lambda resp, sink, body_agg: True

    headers: dict[str, str] = {"authorization": "Bearer test-token"}
    raw_body = b'{"model": "gpt-5", "input": "hello"}'
    affinity_out: dict[str, str] = {}

    upstream_headers = adapter._upstream_headers(raw_body, headers, affinity_out=affinity_out)
    expected_aff = upstream_headers["X-Session-Affinity"]
    expected_scope = affinity_out["affinity_scope"]

    assert expected_aff
    assert expected_scope
    assert affinity_out["affinity_uuid"] == expected_aff
    assert affinity_out["affinity_scope"] == expected_scope

    resp = MagicMock()
    resp.status = 200
    resp.getheader.return_value = "application/json"

    ok = adapter._respond(resp, {"model": "gpt-5"}, object(), 100.0, affinity_uuid=expected_aff, affinity_scope=expected_scope)
    assert ok is True
    assert sa._response_chain_affinity("resp_chain_001", scope=expected_scope) == expected_aff


def test_get_salt_uses_stable_busy_salt_when_lock_is_busy(monkeypatch) -> None:
    import core.session_affinity as sa

    monkeypatch.setattr(sa, "_SALT", None)
    monkeypatch.setattr(sa, "_BUSY_SALT", None)

    def _busy() -> bytes:
        raise sa.SaltLockBusyError("busy")

    monkeypatch.setattr(sa, "_init_salt", _busy)

    first = sa._get_salt()
    second = sa._get_salt()

    assert isinstance(first, bytes)
    assert len(first) == 32
    assert first == second
    assert sa._SALT is None
    assert sa._BUSY_SALT == first


def test_upstream_headers_writes_affinity_only_to_affinity_out(monkeypatch) -> None:
    import core.session_affinity as sa
    from adapters.passthrough_adapter import PassthroughAdapter

    monkeypatch.setenv(sa.FLAG_STABLE_SESSION, "1")
    monkeypatch.setattr(sa, "_SALT", b"k" * 32)

    adapter = PassthroughAdapter.__new__(PassthroughAdapter)
    adapter.id = "test-passthrough"
    adapter.config = {"per_request_headers": {"X-Session-Affinity": "{session_affinity}"}}
    adapter._read_json_headers = lambda: {}

    client_headers = {"authorization": "Bearer secret"}
    affinity_out: dict[str, str] = {}
    body = b'{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}'

    extra = adapter._upstream_headers(body, client_headers, affinity_out=affinity_out)

    assert "_affinity_uuid" not in client_headers
    assert "_affinity_scope" not in client_headers
    assert affinity_out["affinity_uuid"] == extra["X-Session-Affinity"]
    assert affinity_out["affinity_scope"]


def test_relay_stream_registers_response_affinity_on_success(monkeypatch) -> None:
    import types
    import core.session_affinity as sa
    import adapters.passthrough_adapter as pa_mod
    from adapters.passthrough_adapter import PassthroughAdapter

    registered: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        pa_mod,
        "register_response_affinity",
        lambda resp_id, aff, scope="": registered.append((resp_id, aff, scope)),
    )
    monkeypatch.setattr(
        pa_mod,
        "relay_sse",
        lambda *args, **kwargs: types.SimpleNamespace(last_chunk={"id": "resp_stream_123"}),
    )

    adapter = PassthroughAdapter.__new__(PassthroughAdapter)
    adapter.host = types.SimpleNamespace(is_trusted_tool_streaming_enabled=lambda: False)
    adapter._limits = None
    adapter.process_budget = None
    adapter._response_headers = lambda resp: []
    adapter._stream_success = lambda outcome: True

    sink = types.SimpleNamespace(start=lambda *a, **k: None, write=lambda *a, **k: None)
    resp = types.SimpleNamespace(readline=lambda *a, **k: b"")
    result = adapter._relay_stream(
        resp,
        None,
        sink,
        False,
        affinity_uuid="aff-uuid-1",
        affinity_scope="scope-1",
    )

    assert result is True
    assert registered == [("resp_stream_123", "aff-uuid-1", "scope-1")]


def test_extract_response_id_both_formats() -> None:
    from adapters.passthrough_adapter import _extract_response_id

    assert _extract_response_id({"id": "resp_top_1"}) == "resp_top_1"
    assert _extract_response_id({"response": {"id": "resp_nested_2"}}) == "resp_nested_2"
    assert _extract_response_id({"id": "", "response": {"id": "resp_fallback"}}) == "resp_fallback"
    assert _extract_response_id({}) is None
    assert _extract_response_id({"response": {}}) is None
    assert _extract_response_id(None) is None
    assert _extract_response_id("not-a-mapping") is None


def test_relay_stream_nested_response_id_registers_affinity(monkeypatch) -> None:
    from types import SimpleNamespace
    import adapters.passthrough_adapter as pa

    class _StubAdapter(pa.PassthroughAdapter):
        pass

    adapter = _StubAdapter.__new__(_StubAdapter)
    adapter.limits = None
    adapter.process_budget = None
    adapter._trusted_tools = lambda resp, sanitize: False
    adapter._response_headers = lambda resp: []
    adapter._stream_success = lambda outcome: True

    recorded: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        pa,
        "relay_sse",
        lambda readline, write, **kw: SimpleNamespace(
            committed=True,
            last_chunk={"type": "response.completed", "response": {"id": "resp_nested_123"}},
        ),
    )
    monkeypatch.setattr(
        pa,
        "register_response_affinity",
        lambda resp_id, aff, scope="": recorded.append((resp_id, aff, scope)),
    )

    resp = SimpleNamespace(readline=lambda: b"")
    sink = SimpleNamespace(start=lambda status, headers: None, write=lambda data: None)

    ok = adapter._relay_stream(
        resp,
        None,
        sink,
        False,
        affinity_uuid="aff_uuid_1",
        affinity_scope="scope_1",
    )

    assert ok is True
    assert recorded == [("resp_nested_123", "aff_uuid_1", "scope_1")]
