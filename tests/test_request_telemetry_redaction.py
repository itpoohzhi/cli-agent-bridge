"""Редакция секретов телеметрии (RW-001): канонические векторы Совета, first(), права на каталог и файл БД."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
_ROOT = _TESTS.parent
for _p in (str(_TESTS), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.request_telemetry import RequestTelemetryStore, classify_caller, sanitize_scalar  # noqa: E402
from core.telemetry_sql import make_row  # noqa: E402
from core.telemetry_util import first, first_truthy  # noqa: E402

VECTORS = (
    ("Authorization: bearer CANARY_LOWERCASE_123", "CANARY_LOWERCASE_123"),
    ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    ("Authorization: Token secret123", "secret123"),
    ("proxy-authorization=Digest abc123def", "abc123def"),
    ("Bearer head/TAIL_CANARY_456==", "TAIL_CANARY_456"),
    ("Bearer a+b/c~d==", "a+b/c~d=="),
    ("BASIC dXNlcjpwYXNz", "dXNlcjpwYXNz"),
    ('{"api_key": "secret123", "password": "pw_val"}', "secret123"),
    ("{'token': 'tok_single', 'client_secret': 'cs_val'}", "tok_single"),
    ('{"password": "pw_val"}', "pw_val"),
    ("http://user:pass@127.0.0.1:10809", "user:pass"),
    ("socks5h://u1:p%40ss@host:1080", "p%40ss"),
    ("sk_live_abc123456", "abc123456"),
    ("glpat-abc123456", "abc123456"),
    ("AKIAIOSFODNN7EXAMPLE", "IOSFODNN7EXAMPLE"),
    ("xoxb-" + "EXAMPLEVECTOR", "EXAMPLEVECTOR"),
    ("github_pat_abcdefghij1234567890", "abcdefghij1234567890"),
    ('x password="unterminated secret value', "unterminated"),
)


@pytest.mark.parametrize(("raw", "secret"), VECTORS)
def test_secret_vectors_are_fully_redacted(raw, secret):
    cleaned = sanitize_scalar(raw)
    assert "[REDACTED]" in cleaned, raw
    assert secret not in cleaned, raw


def test_url_credentials_keep_host_and_scheme():
    assert sanitize_scalar("http://user:pass@127.0.0.1:10809") == "http://[REDACTED]@127.0.0.1:10809"
    assert sanitize_scalar("http://127.0.0.1:10809") == "http://127.0.0.1:10809"
    assert sanitize_scalar("prompt_tokens: 5, max_tokens=7") == "prompt_tokens: 5, max_tokens=7"


def test_truncation_happens_before_redaction_and_limit_zero_is_honoured():
    assert sanitize_scalar("secret", 0) == ""
    assert sanitize_scalar("abcdef", max_len=0) == ""
    tail_secret = "x" * 5000 + " Bearer TAILSECRET99"
    assert sanitize_scalar(tail_secret, 10, 20) == "x" * 10  # хвост за пределом scan даже не разбирается
    assert sanitize_scalar("Bearer " + "A" * 5000, 160) == "[REDACTED]"
    assert sanitize_scalar(7, 0) == 7 and sanitize_scalar(True, 0) is True and sanitize_scalar(1.5, 0) == 1.5


def test_numbers_do_not_read_env_on_the_hot_path(monkeypatch):
    import core.telemetry_sql as sql

    calls = []
    monkeypatch.setattr(sql.D, "get_env_int", lambda *a, **k: calls.append(a) or 160)
    assert (sanitize_scalar(1), sanitize_scalar(None), sanitize_scalar(2.5)) == (1, None, 2.5)
    assert sanitize_scalar("v", 5, 50) == "v" and calls == []
    make_row({"request_id": "x", "user_agent": "ua"}, 8, 64)
    assert calls == []


def test_make_row_and_caller_never_store_vector_secrets(telemetry_event):
    event = telemetry_event(user_agent="Authorization: bearer CANARY_LOWERCASE_123", error_type="Bearer head/TAIL_CANARY_456==",
                            subagent_id="coder-1 api_key=abc999", outbound_target="http://user:pass@127.0.0.1:10809")
    dump = json.dumps(make_row(event, 160, 640)) + json.dumps(classify_caller(event["subagent_id"], None))
    assert not any(s in dump for s in ("CANARY_LOWERCASE_123", "TAIL_CANARY_456", "abc999", "user:pass"))


def test_first_keeps_falsy_values_and_first_truthy_skips_them():
    assert first(0, 10) == 0 and first(0.0, 1) == 0.0 and first(False, True) is False and first("", "x") == ""
    assert first(None, 0, 5) == 0 and first(None, None) is None and first(None, default=7) == 7 and first() is None
    assert first_truthy(0, 10) == 10 and first_truthy("", None, "x") == "x" and first_truthy(0, default=3) == 3


def test_store_directory_and_file_permissions(tmp_path):
    for engine, force in (("sqlite3", True), ("duckdb", False)):
        if not force:
            pytest.importorskip("duckdb")
        root = tmp_path / engine
        st = RequestTelemetryStore(str(root / "sub" / "bridge_telemetry.duckdb"), force_sqlite=force, autostart=False, enabled=True)
        try:
            assert st.ensure_open() and st.engine == engine
            assert (root / "sub").stat().st_mode & 0o777 == 0o700
            assert Path(st.db_path).stat().st_mode & 0o777 == 0o600
        finally:
            st.close()


def test_existing_directory_permissions_are_not_changed(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    shared.chmod(0o755)
    st = RequestTelemetryStore(str(shared / "t.duckdb"), force_sqlite=True, autostart=False, enabled=True)
    try:
        assert st.ensure_open() and shared.stat().st_mode & 0o777 == 0o755
    finally:
        st.close()
