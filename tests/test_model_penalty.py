"""Behavioral and persistence tests for core.model_penalty."""

import importlib
import json
import queue
import threading
import time
from pathlib import Path

import pytest

import core.model_penalty as model_penalty


MODEL_ID = "claude-sonnet-5-5"
START_TIME = 1_800_000_000.0
ENVIRONMENT_VARIABLES = (
    "BRIDGE_MAX_START_FAILS",
    "BRIDGE_COOLDOWN_SECONDS",
    "BRIDGE_MODEL_PENALTIES_PATH",
    "BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED",
)


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    """Do not let the host environment change test configuration."""
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def clock(monkeypatch):
    """A deterministic, manually advanced wall clock."""
    current = [START_TIME]
    monkeypatch.setattr(model_penalty.time, "time", lambda: current[0])
    return current


def _make_tracker(path, *, max_start_fails=3, cooldown_seconds=10800.0):
    return model_penalty.ModelPenaltyTracker(
        storage_path=path,
        max_start_fails=max_start_fails,
        cooldown_seconds=cooldown_seconds,
    )


def _stored_state(path, model_id, *, allow_missing=False):
    """Read a model record without depending on private tracker attributes.

    The JSON document may store model records directly or inside a metadata
    envelope. Model records themselves must expose fails and penalized_until.
    """
    path = Path(path)
    if not path.exists():
        assert allow_missing, f"Storage file was not created: {path}"
        return {"fails": 0, "penalized_until": 0.0}

    document = json.loads(path.read_text(encoding="utf-8"))
    matches = []

    def visit(value):
        if isinstance(value, dict):
            candidate = value.get(model_id)
            if isinstance(candidate, dict) and {
                "fails",
                "penalized_until",
            }.issubset(candidate):
                matches.append(candidate)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(document)
    if not matches and allow_missing:
        return {"fails": 0, "penalized_until": 0.0}

    assert len(matches) == 1, (
        f"Expected exactly one persisted record for {model_id!r}, "
        f"found {len(matches)} in {document!r}"
    )
    return matches[0]


def _assert_penalized(tracker, model_id, remaining):
    penalized, actual_remaining = tracker.is_penalized(model_id)
    assert penalized is True
    assert actual_remaining == pytest.approx(remaining, rel=0, abs=1e-6)


def test_default_state(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    assert model_penalty.DEFAULT_MAX_START_FAILS == 3
    assert model_penalty.DEFAULT_COOLDOWN_SECONDS == 10.0
    assert model_penalty.DEFAULT_STORAGE_PATH is not None
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    state = _stored_state(path, MODEL_ID, allow_missing=True)
    assert state["fails"] == 0
    assert state["penalized_until"] == 0.0


def test_threshold_to_penalty(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    for expected_fails in (1, 2):
        tracker.record_start_failure(MODEL_ID)
        assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
        state = _stored_state(path, MODEL_ID)
        assert state["fails"] == expected_fails
        assert state["penalized_until"] == 0.0

    tracker.record_start_failure(MODEL_ID)

    _assert_penalized(tracker, MODEL_ID, 10800.0)
    state = _stored_state(path, MODEL_ID)
    assert state["fails"] == 3
    assert state["penalized_until"] == pytest.approx(START_TIME + 10800.0)


def test_calls_during_cooldown_do_not_extend_penalty(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)

    before = _stored_state(path, MODEL_ID).copy()
    assert before["fails"] == 3

    for elapsed in (1.0, 60.0, 3600.0, 10799.0):
        clock[0] = START_TIME + elapsed
        tracker.record_start_failure(MODEL_ID)

        after = _stored_state(path, MODEL_ID)
        assert after["fails"] == before["fails"]
        assert after["penalized_until"] == before["penalized_until"]
        _assert_penalized(tracker, MODEL_ID, 10800.0 - elapsed)


def test_cooldown_auto_expiration(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)

    _assert_penalized(tracker, MODEL_ID, 10800.0)
    clock[0] += 10801.0

    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    # A new failure must begin a fresh streak, not reuse the expired streak.
    tracker.record_start_failure(MODEL_ID)
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    state = _stored_state(path, MODEL_ID)
    assert state["fails"] == 1
    assert state["penalized_until"] == 0.0


@pytest.mark.parametrize("failure_count", [1, 2, 3])
def test_reset_on_success(tmp_path, clock, failure_count):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    for _ in range(failure_count):
        tracker.record_start_failure(MODEL_ID)

    if failure_count == 3:
        _assert_penalized(tracker, MODEL_ID, 10800.0)

    tracker.record_start_success(MODEL_ID)

    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    state = _stored_state(path, MODEL_ID, allow_missing=True)
    assert state["fails"] == 0
    assert state["penalized_until"] == 0.0

    tracker.record_start_failure(MODEL_ID)
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    assert _stored_state(path, MODEL_ID)["fails"] == 1


def test_disk_persistence(tmp_path, clock):
    path = tmp_path / "penalties.json"
    partial_model = "partially-failed-model"
    tracker1 = _make_tracker(path)

    tracker1.record_start_failure(partial_model)
    tracker1.record_start_failure(partial_model)
    for _ in range(3):
        tracker1.record_start_failure(MODEL_ID)

    expected_penalty = _stored_state(path, MODEL_ID).copy()
    expected_partial = _stored_state(path, partial_model).copy()

    clock[0] += 123.0
    tracker2 = _make_tracker(path)

    assert tracker2 is not tracker1
    assert tracker2.is_penalized(MODEL_ID) == tracker1.is_penalized(MODEL_ID)
    _assert_penalized(tracker2, MODEL_ID, 10677.0)
    assert tracker2.is_penalized(partial_model) == (False, 0.0)
    assert _stored_state(path, MODEL_ID) == expected_penalty
    assert _stored_state(path, partial_model) == expected_partial

    # Crossing the threshold proves the partial streak was actually loaded.
    tracker2.record_start_failure(partial_model)
    _assert_penalized(tracker2, partial_model, 10800.0)
    assert _stored_state(path, partial_model)["fails"] == 3


def test_corrupt_json_fail_open(tmp_path, clock):
    path = tmp_path / "penalties.json"
    path.write_text("{invalid-json...", encoding="utf-8")

    tracker = _make_tracker(path)

    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    assert tracker.is_penalized("another-model") == (False, 0.0)

    tracker.record_start_failure(MODEL_ID)
    state = _stored_state(path, MODEL_ID)
    assert state["fails"] == 1
    assert state["penalized_until"] == 0.0

    tracker.record_start_failure(MODEL_ID)
    tracker.record_start_failure(MODEL_ID)
    _assert_penalized(tracker, MODEL_ID, 10800.0)

    reloaded = _make_tracker(path)
    _assert_penalized(reloaded, MODEL_ID, 10800.0)


def test_multithreaded_concurrency(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)
    worker_count = 10
    barrier = threading.Barrier(worker_count)
    errors = queue.Queue()

    def worker(index):
        try:
            barrier.wait(timeout=10.0)
            for _ in range(3):
                tracker.record_start_failure(MODEL_ID)
                tracker.record_start_failure(f"worker-model-{index}")
        except BaseException as exc:
            errors.put(exc)

    threads = [
        threading.Thread(target=worker, args=(index,), daemon=True)
        for index in range(worker_count)
    ]
    for thread in threads:
        thread.start()

    deadline = time.monotonic() + 20.0
    for thread in threads:
        thread.join(timeout=max(0.0, deadline - time.monotonic()))

    assert not any(thread.is_alive() for thread in threads), (
        "Concurrent failure recording did not finish; possible deadlock"
    )

    failures = []
    while not errors.empty():
        failures.append(errors.get_nowait())
    assert not failures, f"Worker threads raised exceptions: {failures!r}"

    for model_id in [MODEL_ID] + [
        f"worker-model-{index}" for index in range(worker_count)
    ]:
        _assert_penalized(tracker, model_id, 10800.0)
        state = _stored_state(path, model_id)
        assert state["fails"] == 3
        assert state["penalized_until"] == pytest.approx(START_TIME + 10800.0)

    reloaded = _make_tracker(path)
    for index in range(worker_count):
        _assert_penalized(reloaded, f"worker-model-{index}", 10800.0)
    _assert_penalized(reloaded, MODEL_ID, 10800.0)


def test_env_var_overrides(tmp_path, monkeypatch, clock):
    path = tmp_path / "environment-penalties.json"

    # Reload to cover implementations that read configuration at import time
    # and to avoid reusing a singleton constructed by an earlier test.
    try:
        with monkeypatch.context() as environment:
            environment.setenv("BRIDGE_MAX_START_FAILS", "2")
            environment.setenv("BRIDGE_COOLDOWN_SECONDS", "45.5")
            environment.setenv("BRIDGE_MODEL_PENALTIES_PATH", str(path))
            importlib.reload(model_penalty)

            tracker = model_penalty.get_penalty_tracker()
            assert model_penalty.get_penalty_tracker() is tracker

            tracker.record_start_failure(MODEL_ID)
            assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
            assert path.is_file()
            assert _stored_state(path, MODEL_ID)["fails"] == 1

            tracker.record_start_failure(MODEL_ID)
            _assert_penalized(tracker, MODEL_ID, 45.5)
            state = _stored_state(path, MODEL_ID)
            assert state["fails"] == 2
            assert state["penalized_until"] == pytest.approx(START_TIME + 45.5)

            clock[0] += 46.5
            assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    finally:
        # Do not leak environment-derived constants or the configured singleton.
        importlib.reload(model_penalty)


def test_model_id_normalization(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)
    decorated_id = "  Claude-Sonnet-5-5  "

    tracker.record_start_failure(decorated_id)
    tracker.record_start_failure(MODEL_ID)

    assert tracker.is_penalized(decorated_id) == (False, 0.0)
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    assert _stored_state(path, MODEL_ID)["fails"] == 2

    tracker.record_start_failure(decorated_id)

    _assert_penalized(tracker, MODEL_ID, 10800.0)
    assert tracker.is_penalized(decorated_id) == tracker.is_penalized(MODEL_ID)
    assert _stored_state(path, MODEL_ID)["fails"] == 3

    tracker.record_start_success(decorated_id)

    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)
    assert tracker.is_penalized(decorated_id) == (False, 0.0)
    state = _stored_state(path, MODEL_ID, allow_missing=True)
    assert state["fails"] == 0
    assert state["penalized_until"] == 0.0


def test_server_build_models_list_penalized(tmp_path, monkeypatch):
    import server
    tracker = model_penalty.ModelPenaltyTracker(
        storage_path=tmp_path / "penalties.json",
        max_start_fails=3,
        cooldown_seconds=10800.0,
    )
    monkeypatch.setattr(server, "_PENALTY_TRACKER", tracker)
    tracker.record_start_failure("gpt-6.1-sol")
    tracker.record_start_failure("gpt-6.1-sol")
    tracker.record_start_failure("gpt-6.1-sol")

    models = server._build_models_list()
    sol = next((m for m in models if m["id"] == "gpt-6.1-sol"), None)
    assert sol is not None
    assert sol["available"] is False
    assert sol["penalized_until"] is not None
    assert sol["penalized_until"] > time.time()


def test_passthrough_429_trips_penalty(tmp_path, monkeypatch):
    import server
    tracker = model_penalty.ModelPenaltyTracker(
        storage_path=tmp_path / "penalties.json",
        max_start_fails=3,
        cooldown_seconds=10800.0,
    )
    monkeypatch.setattr(server, "_PENALTY_TRACKER", tracker)

    class FakeAdapter:
        id = "anthropic"

        def __init__(self, status):
            self.status = status

        def handle(self, path, raw_body, request, headers, sink):
            sink.status = self.status

    handler = object.__new__(server.Handler)
    handler.path = "/v1/chat/completions"
    handler.headers = {}
    handler._trace = None
    handler._log_request_id = "req-test"
    handler._correlation_id = "corr-test"
    handler._trace_log_fields = lambda: "trace=1"

    fake_429 = FakeAdapter(status=429)
    for _ in range(2):
        handler._serve_passthrough(
            adapter=fake_429,
            raw=b"{}",
            req={"model": "claude-sonnet-5-5"},
            model_id="claude-sonnet-5-5",
        )
    is_pen, _ = tracker.is_penalized("claude-sonnet-5-5")
    assert not is_pen

    # Третий сбой 429 должен оштрафовать модель
    handler._serve_passthrough(
        adapter=fake_429,
        raw=b"{}",
        req={"model": "claude-sonnet-5-5"},
        model_id="claude-sonnet-5-5",
    )
    is_pen, rem = tracker.is_penalized("claude-sonnet-5-5")
    assert is_pen
    assert rem > 0

    # 400 Bad Request (клиентская ошибка) нейтральна и не сбрасывает штраф
    fake_400 = FakeAdapter(status=400)
    handler._serve_passthrough(
        adapter=fake_400,
        raw=b"{}",
        req={"model": "claude-sonnet-5-5"},
        model_id="claude-sonnet-5-5",
    )
    is_pen, _ = tracker.is_penalized("claude-sonnet-5-5")
    assert is_pen

    # 200 OK (успешный ответ модели) сбрасывает штраф
    fake_200 = FakeAdapter(status=200)
    handler._serve_passthrough(
        adapter=fake_200,
        raw=b"{}",
        req={"model": "claude-sonnet-5-5"},
        model_id="claude-sonnet-5-5",
    )
    is_pen, _ = tracker.is_penalized("claude-sonnet-5-5")
    assert not is_pen


def test_adaptive_backoff_steps(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = model_penalty.ModelPenaltyTracker(storage_path=path, max_start_fails=3)

    # Trip 1 (fails 1..3) -> cooldown 10s
    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)
    is_pen, rem = tracker.is_penalized(MODEL_ID)
    assert is_pen
    assert rem == pytest.approx(10.0, rel=0, abs=1e-3)

    # Advance clock past 10s
    clock[0] += 11.0
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    # Trip 2 (fails 1..3 again) -> cooldown 30s
    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)
    is_pen, rem = tracker.is_penalized(MODEL_ID)
    assert is_pen
    assert rem == pytest.approx(30.0, rel=0, abs=1e-3)

    # Advance clock past 30s
    clock[0] += 31.0
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    # Trip 3 (fails 1..3 again) -> cooldown 120s
    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)
    is_pen, rem = tracker.is_penalized(MODEL_ID)
    assert is_pen
    assert rem == pytest.approx(120.0, rel=0, abs=1e-3)

    # Advance clock past 120s
    clock[0] += 121.0
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    # Trip 4 -> cooldown 240s
    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)
    is_pen, rem = tracker.is_penalized(MODEL_ID)
    assert is_pen
    assert rem == pytest.approx(240.0, rel=0, abs=1e-3)

    # Advance clock past 240s
    clock[0] += 241.0
    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)

    # Trip 5 -> capped at 300s
    for _ in range(3):
        tracker.record_start_failure(MODEL_ID)
    is_pen, rem = tracker.is_penalized(MODEL_ID)
    assert is_pen
    assert rem == pytest.approx(300.0, rel=0, abs=1e-3)


def test_infrastructure_network_errors_neutral(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = model_penalty.ModelPenaltyTracker(storage_path=path, max_start_fails=3)

    for err in (
        "http_502",
        "http_504",
        "Connection refused",
        "connect_error",
        "network_error",
        "connection reset",
        "connectionreset",
        "econnreset",
        "Broken pipe",
        "Bad Gateway",
        "Gateway Timeout",
    ):
        for _ in range(5):
            tripped, fails, until = tracker.record_start_failure(MODEL_ID, error_reason=err)
            assert not tripped
            assert fails == 0
            assert until == 0.0

    assert tracker.is_penalized(MODEL_ID) == (False, 0.0)


def test_strict_classification_disabled_by_default(tmp_path, clock):
    path = tmp_path / "penalties.json"
    tracker = _make_tracker(path)

    penalized, fails, _ = tracker.record_start_failure("test-model", "client_gone_502")
    assert penalized is False
    assert fails == 1

    penalized, fails, _ = tracker.record_start_failure("test-model", "http_401")
    assert penalized is False
    assert fails == 2


def test_strict_classification_enabled_filters_client_gone_and_drain(
    tmp_path, clock, monkeypatch
):
    monkeypatch.setenv("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED", "1")
    tracker = _make_tracker(tmp_path / "penalties.json")

    for reason in ("client_gone_502", "sigterm drain", "http_401"):
        penalized, fails, _ = tracker.record_start_failure("test-model", reason)
        assert penalized is False
        assert fails == 0

    entry = tracker.get_model_status("test-model")
    assert entry["fails"] == 0


def test_strict_classification_negative_cases(tmp_path, clock, monkeypatch):
    monkeypatch.setenv("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED", "1")
    tracker = _make_tracker(tmp_path / "penalties.json")

    for index, reason in enumerate(
        (
            "drainage_problem",
            "some_unauthorized_token_in_prompt",
            "unknown_model_crash",
        )
    ):
        model_id = f"test-model-{index}"
        penalized, fails, _ = tracker.record_start_failure(model_id, reason)
        assert penalized is False
        assert fails == 1


def test_strict_classification_dynamic_toggle(tmp_path, clock, monkeypatch):
    tracker = _make_tracker(tmp_path / "penalties.json")

    monkeypatch.setenv("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED", "1")
    penalized, fails, _ = tracker.record_start_failure("test-model", "client_gone_502")
    assert penalized is False
    assert fails == 0

    monkeypatch.setenv("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED", "0")
    penalized, fails, _ = tracker.record_start_failure("test-model", "client_gone_502")
    assert penalized is False
    assert fails == 1

    monkeypatch.setenv("BRIDGE_QUARANTINE_STRICT_CLASSIFY_ENABLED", "1")
    penalized, fails, _ = tracker.record_start_failure("test-model", "client_gone_502")
    assert penalized is False
    assert fails == 1


def test_fsm_module_loc():
    lines = Path("core/model_penalty_fsm.py").read_text(encoding="utf-8").splitlines()

    assert len(lines) <= 300


