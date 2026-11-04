"""Тесты универсальной отказоустойчивости шлюза (ADR-0020 Rev 4): `core/resilience.py` + фасад.

Восемь сценариев ADR: переходы брейкера, проба HALF_OPEN (успех/сбой), generation tokens,
`record_discard`, изоляция Bulkhead, RetryPolicy (Full Jitter, дедлайн, `bytes_delivered`),
флаги GigaRC (default=false, env-override). Плюс сквозные проверки через настоящий `Handler`:
503 + `Retry-After` без обращения к upstream, `GET /v1/resilience`, неизменный `/health`.
Время — мок-часы, джиттер брейкера выключен (`cooldown_jitter=0`), сна нет.
"""

from __future__ import annotations

import http.client
import json
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core.resilience import (  # noqa: E402
    BulkheadCapacityExceeded,
    CircuitBreaker,
    CircuitBreakerOpen,
    CircuitBreakerState,
    ResilienceFlags,
    ResilienceLease,
    ResilienceManager,
    RetryPolicy,
    SnapshotFlagSource,
    is_transient_backend_error,
)

ALL_ON = {
    "RESILIENCE_ENABLED": True,
    "CIRCUIT_BREAKER_ENABLED": True,
    "BULKHEAD_ENABLED": True,
    "RETRY_ENABLED": True,
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class StaticSource:
    """FlagSource с фиксированным снимком GigaRC."""

    def __init__(self, flags: dict[str, bool]) -> None:
        self.flags = flags

    def read(self) -> dict[str, bool]:
        return dict(self.flags)


def make_manager(env: dict[str, str] | None = None, flags=None, clock=None, **kw):
    clock = clock or FakeClock()
    resilience_flags = ResilienceFlags(
        StaticSource(ALL_ON if flags is None else flags),
        env={"BRIDGE_CIRCUIT_BREAKER_JITTER": "0", **(env or {})},
    )
    return ResilienceManager(resilience_flags, clock=clock, **kw), clock


def make_breaker(
    threshold=3, cooldown=30.0, clock=None
) -> tuple[CircuitBreaker, FakeClock]:
    clock = clock or FakeClock()
    breaker = CircuitBreaker(
        "b",
        fail_threshold=threshold,
        cooldown_s=cooldown,
        cooldown_jitter=0,
        clock=clock,
    )
    return breaker, clock


def trip(breaker: CircuitBreaker, times: int = 3) -> None:
    for _ in range(times):
        allowed, gen, _ = breaker.acquire()
        assert allowed
        breaker.record_failure(gen)


# --------------------------------------------------------------------------- 1..5: брейкер


def test_circuit_breaker_transitions():
    manager, _ = make_manager()
    for _ in range(3):
        with manager.acquire("codex") as lease:
            lease.record_failure()
    with pytest.raises(CircuitBreakerOpen) as caught:
        manager.acquire("codex")
    exc = caught.value
    assert exc.error_code == "CIRCUIT_BREAKER_OPEN"
    assert exc.backend_id == "codex"
    assert exc.retry_after == 30  # ceil(30.0 - 0): jitter выключен, время не шло
    # Изоляция по backend_id: другой бэкенд не затронут.
    with manager.acquire("agy") as lease:
        lease.record_success()


def test_circuit_breaker_below_threshold_and_success_reset():
    breaker, _ = make_breaker(threshold=3)
    trip(breaker, 2)
    assert breaker.state is CircuitBreakerState.CLOSED
    allowed, gen, probe = breaker.acquire()
    assert (allowed, probe) == (True, False)
    breaker.record_success(gen)  # успех обнуляет подряд идущие сбои
    trip(breaker, 2)
    assert breaker.state is CircuitBreakerState.CLOSED
    trip(breaker, 1)
    assert breaker.state is CircuitBreakerState.OPEN


def test_circuit_breaker_half_open_probe_success():
    breaker, clock = make_breaker()
    trip(breaker)
    assert breaker.acquire()[0] is False
    clock.advance(29.0)
    assert breaker.acquire()[0] is False
    assert breaker.retry_after == 1
    clock.advance(1.0)
    allowed, gen, is_probe = breaker.acquire()
    assert (allowed, is_probe) == (True, True)
    assert breaker.state is CircuitBreakerState.HALF_OPEN
    # Ровно одна проба: второй запрос отклонён, пока проба в полёте.
    assert breaker.acquire()[0] is False
    breaker.record_success(gen)
    assert breaker.state is CircuitBreakerState.CLOSED
    assert breaker.acquire() == (True, breaker.generation, False)


def test_circuit_breaker_half_open_probe_failure():
    breaker, clock = make_breaker()
    trip(breaker)
    clock.advance(30.0)
    allowed, gen, is_probe = breaker.acquire()
    assert allowed and is_probe
    breaker.record_failure(gen)
    assert breaker.state is CircuitBreakerState.OPEN
    assert breaker.retry_after == 30  # новый cooldown с момента сбоя пробы
    assert breaker.acquire()[0] is False
    clock.advance(30.0)
    assert breaker.acquire()[0] is True  # снова проба


def test_circuit_breaker_generation_token_safety():
    breaker, clock = make_breaker()
    # Три «долгих» запроса стартовали в CLOSED с поколением 0.
    slow = [breaker.acquire() for _ in range(3)]
    assert {gen for _, gen, _ in slow} == {0}
    # Быстрые сбои открыли брейкер (поколение 1), затем проба закрыла его (2 и 3).
    trip(breaker)
    clock.advance(30.0)
    _, probe_gen, _ = breaker.acquire()
    breaker.record_success(probe_gen)
    assert breaker.state is CircuitBreakerState.CLOSED
    generation = breaker.generation
    # Запоздавшие сбои устаревшего поколения не меняют ни счётчик, ни состояние.
    for _, gen, _ in slow:
        breaker.record_failure(gen)
    assert breaker.state is CircuitBreakerState.CLOSED
    assert breaker.failures == 0
    assert breaker.generation == generation
    # Запоздавший успех не закрывает HALF_OPEN и не сбрасывает слот пробы.
    trip(breaker)
    clock.advance(30.0)
    _, gen_probe, is_probe = breaker.acquire()
    assert is_probe
    breaker.record_success(slow[0][1])
    breaker.record_discard(slow[0][1])
    assert breaker.state is CircuitBreakerState.HALF_OPEN
    assert breaker.acquire()[0] is False  # слот пробы всё ещё занят


def test_circuit_breaker_record_discard():
    breaker, clock = make_breaker()
    trip(breaker)
    clock.advance(30.0)
    allowed, gen, is_probe = breaker.acquire()
    assert allowed and is_probe
    assert breaker.acquire()[0] is False
    breaker.record_discard(gen, "client_disconnected")
    assert breaker.state is CircuitBreakerState.HALF_OPEN  # не OPEN
    allowed2, gen2, is_probe2 = breaker.acquire()  # слот пробы свободен
    assert allowed2 and is_probe2 and gen2 == gen
    breaker.record_success(gen2)
    assert breaker.state is CircuitBreakerState.CLOSED


def test_discard_in_closed_does_not_count_failure():
    breaker, _ = make_breaker(threshold=1)
    allowed, gen, _ = breaker.acquire()
    assert allowed
    breaker.record_discard(gen, "client_disconnected")
    assert breaker.state is CircuitBreakerState.CLOSED
    assert breaker.failures == 0


# --------------------------------------------------------------------------- 6: Bulkhead


def test_bulkhead_concurrency_isolation():
    manager, _ = make_manager()
    leases = [manager.acquire("codex") for _ in range(64)]
    started = time.monotonic()
    with pytest.raises(BulkheadCapacityExceeded) as caught:
        manager.acquire("codex")
    assert time.monotonic() - started < 0.5  # отказ без ожидания слота
    assert caught.value.error_code == "BULKHEAD_CAPACITY_EXCEEDED"
    assert caught.value.retry_after == 1
    # Другие бэкенды живы, их брейкеры/отсеки не затронуты.
    for other in ("droid", "muse", "agy"):
        with manager.acquire(other) as lease:
            lease.record_success()
    # Отказ Bulkhead не учтён брейкером codex (запрос не дошёл до бэкенда).
    snap = manager.snapshot()["backends"]["codex"]
    assert snap["state"] == "CLOSED" and snap["failures"] == 0
    assert snap["active"] == 64 and snap["capacity"] == 64
    leases[0].close()
    with manager.acquire("codex") as lease:
        lease.record_success()
    for lease in leases[1:]:
        lease.close()
    assert manager.snapshot()["backends"]["codex"]["active"] == 0


def test_bulkhead_capacity_is_configurable_and_backend_limited():
    manager, _ = make_manager(
        env={"BRIDGE_BULKHEAD_MAX_CONCURRENT": "2"}, backend_limits={"muse": 1}
    )
    held = [manager.acquire("codex"), manager.acquire("codex")]
    with pytest.raises(BulkheadCapacityExceeded):
        manager.acquire("codex")
    muse = manager.acquire("muse")
    with pytest.raises(BulkheadCapacityExceeded):
        manager.acquire("muse")  # min(лимит бэкенда 1, настройка 2)
    for lease in (*held, muse):
        lease.close()


def test_bulkhead_rejection_frees_half_open_probe():
    manager, clock = make_manager(
        env={
            "BRIDGE_BULKHEAD_MAX_CONCURRENT": "2",
            "BRIDGE_CIRCUIT_BREAKER_FAIL_THRESHOLD": "2",
        }
    )
    first, second = manager.acquire("codex"), manager.acquire("codex")
    first.record_failure()
    second.record_failure()  # брейкер открыт, оба слота отсека ещё заняты
    clock.advance(30.0)
    with pytest.raises(BulkheadCapacityExceeded):
        manager.acquire("codex")  # проба допущена брейкером, но отсек полон
    assert manager.snapshot()["backends"]["codex"]["state"] == "HALF_OPEN"
    first.close()
    probe = manager.acquire("codex")  # слот пробы возвращён отказом отсека
    assert probe.is_probe
    probe.record_success()
    assert manager.snapshot()["backends"]["codex"]["state"] == "CLOSED"
    probe.close()
    second.close()


def test_bulkhead_capacity_change_applies_without_restart():
    env: dict[str, str] = {
        "BRIDGE_CIRCUIT_BREAKER_JITTER": "0",
        "BRIDGE_BULKHEAD_MAX_CONCURRENT": "1",
    }
    manager = ResilienceManager(ResilienceFlags(StaticSource(ALL_ON), env=env))
    first = manager.acquire("codex")
    with pytest.raises(BulkheadCapacityExceeded):
        manager.acquire("codex")
    env["BRIDGE_BULKHEAD_MAX_CONCURRENT"] = "3"
    second = manager.acquire("codex")
    first.close()  # слот старого отсека освобождает старый семафор, а не новый
    second.close()
    assert manager.snapshot()["backends"]["codex"]["active"] == 0


# --------------------------------------------------------------------------- 7: RetryPolicy


def test_retry_policy_full_jitter_and_deadline():
    ranges: list[tuple[float, float]] = []

    def spy(lo: float, hi: float) -> float:
        ranges.append((lo, hi))
        return hi

    policy = RetryPolicy(
        max_attempts=7, base_delay_s=1.0, max_delay_s=10.0, backoff_factor=2.0, rng=spy
    )
    delays = [policy.compute_delay(attempt) for attempt in range(6)]
    # Full Jitter: нижняя граница всегда 0, верхняя — min(max, base * 2**attempt).
    assert ranges == [
        (0.0, 1.0),
        (0.0, 2.0),
        (0.0, 4.0),
        (0.0, 8.0),
        (0.0, 10.0),
        (0.0, 10.0),
    ]
    assert delays == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]

    # Реальный джиттер лежит в [0, потолок] и не вырождается в константу.
    real = RetryPolicy(max_attempts=5, base_delay_s=1.0, max_delay_s=10.0)
    samples = [real.compute_delay(3) for _ in range(200)]
    assert all(s is not None and 0.0 <= s <= 8.0 for s in samples)
    assert len(set(samples)) > 50

    # Дедлайн: остаток исчерпан или задержка не помещается — повтора нет.
    assert policy.compute_delay(2, deadline_s=0) is None
    assert policy.compute_delay(2, deadline_s=-1.0) is None
    assert policy.compute_delay(2, deadline_s=4.0) is None  # delay=4.0 >= 4.0
    assert policy.compute_delay(2, deadline_s=4.5) == 4.0
    # Огромный номер попытки не переполняет степень.
    assert policy.compute_delay(10_000) == 10.0

    # Инвариант доставки: байты отданы — повтор запрещён при любой ошибке.
    transient = ConnectionError("upstream reset")
    assert policy.should_retry(0, bytes_delivered=False, exc=transient) is True
    assert policy.should_retry(0, bytes_delivered=True, exc=transient) is False
    assert policy.should_retry(0, bytes_delivered=True, exc=None) is False
    # Всего max_attempts попыток; нетранзитные ошибки не повторяются.
    three = RetryPolicy(max_attempts=3)
    assert [three.should_retry(a, False, transient) for a in range(4)] == [
        True,
        True,
        False,
        False,
    ]
    assert three.should_retry(0, False, ValueError("bad request")) is False
    assert (
        three.should_retry(0, False, None) is True
    )  # сбой без исключения (upstream 5xx)
    assert is_transient_backend_error(CircuitBreakerOpen("b", 1)) is False


def test_retry_policy_from_manager_follows_flag():
    manager, _ = make_manager(
        env={"BRIDGE_RETRY_MAX_ATTEMPTS": "5", "BRIDGE_RETRY_BASE_DELAY_S": "0.25"}
    )
    policy = manager.retry_policy()
    assert policy is not None
    assert (policy.max_attempts, policy.base_delay_s, policy.max_delay_s) == (
        5,
        0.25,
        10.0,
    )
    off, _ = make_manager(flags={**ALL_ON, "RETRY_ENABLED": False})
    assert off.retry_policy() is None


# --------------------------------------------------------------------------- 8: флаги GigaRC


def _write_snapshot(
    path: Path, flags: dict, *, now: datetime, ttl_s: float = 60.0
) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": now.isoformat(),
                "expires_at": (now + timedelta(seconds=ttl_s)).isoformat(),
                "flags": flags,
            }
        )
    )
    path.chmod(0o600)


def test_resilience_gigarc_flags(tmp_path: Path):
    # 1) Нет снимка и env — всё выключено, пороги по умолчанию.
    missing = SnapshotFlagSource(str(tmp_path / "absent.json"))
    off = ResilienceFlags(missing, env={}).current()
    assert (off.enabled, off.circuit_breaker, off.bulkhead, off.retry) == (False,) * 4
    manager = ResilienceManager(ResilienceFlags(missing, env={}))
    assert manager.acquire("codex").close() is None  # no-op lease
    for _ in range(100):
        manager.acquire("codex")  # без флага Bulkhead не ограничивает
    assert manager.snapshot()["backends"] == {}

    # 2) Снимок GigaRC включает флаги (дефолты порогов — из ADR).
    tmp_path.chmod(0o700)
    snap_path = tmp_path / "resilience.snapshot.json"
    now = datetime.now(timezone.utc)
    _write_snapshot(snap_path, ALL_ON, now=now)
    clock = SimpleNamespace(t=now.timestamp())
    source = SnapshotFlagSource(
        str(snap_path), clock=lambda: clock.t, max_true_age_s=30.0
    )
    on = ResilienceFlags(source, env={}).current()
    assert (on.enabled, on.circuit_breaker, on.bulkhead, on.retry) == (True,) * 4
    assert (on.bulkhead_max_concurrent, on.fail_threshold, on.cooldown_s) == (
        64,
        3,
        30.0,
    )
    assert (on.retry_max_attempts, on.retry_base_delay_s, on.retry_max_delay_s) == (
        3,
        1.0,
        10.0,
    )

    # 3) `true` живёт только пока снимок свеж: устаревший снимок гасит флаги (lastgood → false).
    clock.t += 31.0
    stale = ResilienceFlags(source, env={}).current()
    assert stale.enabled is False

    # 4) Env перекрывает снимок в обе стороны (kill-switch и принудительное включение).
    clock.t = now.timestamp()
    killed = ResilienceFlags(
        source, env={"BRIDGE_CIRCUIT_BREAKER_ENABLED": "false"}
    ).current()
    assert killed.enabled and not killed.circuit_breaker and killed.bulkhead
    master_off = ResilienceFlags(
        source, env={"BRIDGE_RESILIENCE_ENABLED": "0"}
    ).current()
    assert (master_off.circuit_breaker, master_off.bulkhead, master_off.retry) == (
        False,
    ) * 3
    forced = ResilienceFlags(
        StaticSource({}),
        env={"BRIDGE_RESILIENCE_ENABLED": "yes", "BRIDGE_RETRY_ENABLED": "on"},
    ).current()
    assert forced.enabled and forced.retry and not forced.bulkhead

    # 5) Пороги из env; мусор и недопустимые значения → безопасный fallback.
    tuned = ResilienceFlags(
        StaticSource(ALL_ON),
        env={
            "BRIDGE_BULKHEAD_MAX_CONCURRENT": "8",
            "BRIDGE_CIRCUIT_BREAKER_FAIL_THRESHOLD": "5",
            "BRIDGE_CIRCUIT_BREAKER_COOLDOWN_S": "12.5",
            "BRIDGE_RETRY_MAX_ATTEMPTS": "4",
            "BRIDGE_RETRY_BASE_DELAY_S": "0.5",
            "BRIDGE_RETRY_MAX_DELAY_S": "2",
        },
    ).current()
    assert (tuned.bulkhead_max_concurrent, tuned.fail_threshold, tuned.cooldown_s) == (
        8,
        5,
        12.5,
    )
    assert (
        tuned.retry_max_attempts,
        tuned.retry_base_delay_s,
        tuned.retry_max_delay_s,
    ) == (4, 0.5, 2.0)
    garbage = ResilienceFlags(
        StaticSource(ALL_ON),
        env={
            "BRIDGE_BULKHEAD_MAX_CONCURRENT": "zero",
            "BRIDGE_CIRCUIT_BREAKER_FAIL_THRESHOLD": "0",
            "BRIDGE_CIRCUIT_BREAKER_COOLDOWN_S": "-3",
            "BRIDGE_RETRY_BASE_DELAY_S": "nan",
            "BRIDGE_RESILIENCE_ENABLED": "maybe",  # невалидный env игнорируется → берётся снимок
        },
    ).current()
    assert garbage.enabled
    assert (
        garbage.bulkhead_max_concurrent,
        garbage.fail_threshold,
        garbage.cooldown_s,
    ) == (64, 3, 30.0)
    assert garbage.retry_base_delay_s == 1.0

    # 6) Небезопасный снимок (права 0644) игнорируется: флаги остаются false.
    snap_path.chmod(0o644)
    unsafe = SnapshotFlagSource(str(snap_path), clock=lambda: clock.t)
    assert ResilienceFlags(unsafe, env={}).current().enabled is False

    # 7) Падение источника флагов не ломает запрос.
    class Broken:
        def read(self):
            raise RuntimeError("boom")

    assert ResilienceFlags(Broken(), env={}).current().enabled is False


# --------------------------------------------------------------------------- Lease


def test_lease_has_no_default_success():
    manager, _ = make_manager()
    # Выход без исхода и без исключения — не успех и не сбой.
    for _ in range(5):
        with manager.acquire("codex"):
            pass
    snap = manager.snapshot()["backends"]["codex"]
    assert snap["state"] == "CLOSED" and snap["failures"] == 0 and snap["active"] == 0
    # Необработанное исключение — сбой; Bulkhead освобождён.
    for _ in range(3):
        with pytest.raises(RuntimeError):
            with manager.acquire("codex"):
                raise RuntimeError("adapter crashed")
    assert manager.snapshot()["backends"]["codex"]["state"] == "OPEN"
    assert manager.snapshot()["backends"]["codex"]["active"] == 0


def test_lease_first_outcome_is_final_and_probe_without_outcome_is_released():
    manager, clock = make_manager()
    for _ in range(3):
        with manager.acquire("codex") as lease:
            lease.record_failure()
    clock.advance(30.0)
    with manager.acquire("codex") as probe:
        assert probe.is_probe
        probe.record_discard("client_disconnected")
        probe.record_failure()  # игнорируется: исход уже зафиксирован
    assert manager.snapshot()["backends"]["codex"]["state"] == "HALF_OPEN"
    with manager.acquire("codex"):  # проба без исхода не залипает навсегда
        pass
    with manager.acquire("codex") as probe2:
        assert probe2.is_probe
        probe2.record_success()
    assert manager.snapshot()["backends"]["codex"]["state"] == "CLOSED"


def test_disabled_flags_give_noop_lease():
    manager = ResilienceManager(ResilienceFlags(StaticSource({}), env={}))
    lease = manager.acquire("codex")
    assert isinstance(lease, ResilienceLease)
    with lease:
        lease.record_failure()
    for _ in range(10):
        manager.acquire("codex").record_failure()
    manager.acquire("codex")  # брейкер не открывался


# --------------------------------------------------------------------------- фасад (HTTP)


@pytest.fixture
def facade(monkeypatch, tmp_path):
    """Настоящий Handler + управляемый upstream; RESILIENCE подменяется тестом."""
    state = SimpleNamespace(status=200, hits=0)
    lock = threading.Lock()

    class Upstream(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def do_POST(self):  # noqa: N802
            self.rfile.read(int(self.headers["Content-Length"]))
            with lock:
                state.hits += 1
            body = json.dumps({"id": "x", "choices": []}).encode()
            self.send_response(state.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    class Srv(ThreadingHTTPServer):
        request_queue_size = 64
        daemon_threads = True

    upstream = Srv(("127.0.0.1", 0), Upstream)
    threading.Thread(
        target=upstream.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()
    data = json.loads((server.ROOT / "fleet.json").read_text())
    for cfg in data["backends"].values():
        if cfg["kind"] == "passthrough":
            cfg.update(
                base_url=f"http://127.0.0.1:{upstream.server_port}/v1",
                api_key="",
                api_key_env="",
                enabled=True,
            )
    fleet = server._build_catalog(data)
    monkeypatch.setattr(server, "FLEET", fleet)
    monkeypatch.setattr(
        server,
        "BACKENDS",
        server.AdapterRegistry.from_fleet(
            fleet, server.ADAPTER_KINDS, lambda: server.FLEET, server
        ),
    )
    monkeypatch.setattr(server, "AUTH_KEY", "hub-test-key")
    monkeypatch.setattr(server, "BRIDGE_KEY", "hub-test-key")
    monkeypatch.setattr(
        server,
        "TOKEN_CACHE",
        server.TokenCache(
            path=tmp_path / "missing-facade.env",
            environ={"AUTH_KEY": "hub-test-key", "BRIDGE_KEY": "hub-test-key"},
        ),
    )
    monkeypatch.setattr(server, "_log", lambda message: None)
    monkeypatch.setattr(server, "_shutting_down", False)
    monkeypatch.setattr(server, "_is_drain_enabled", lambda: False)
    monkeypatch.setattr(server, "_is_detached_enabled", lambda: False)
    monkeypatch.setattr(server, "_budget", server._ByteBudget(1_000_000))
    monkeypatch.setattr(
        server,
        "_PENALTY_TRACKER",
        server.get_penalty_tracker().__class__(
            storage_path=tmp_path / "facade_penalties.json", max_start_fails=999
        ),
    )
    monkeypatch.setattr(
        server,
        "_QUOTA_CB_CACHE",
        server.QuotaCircuitBreakerCache(tmp_path / "facade_quota.json"),
    )
    bridge = Srv(("127.0.0.1", 0), server.Handler)
    threading.Thread(
        target=bridge.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    ).start()

    def call(body=None, path="/v1/chat/completions", method="POST", auth=True):
        conn = http.client.HTTPConnection("127.0.0.1", bridge.server_port, timeout=10)
        try:
            headers = {"Content-Type": "application/json"}
            if auth:
                headers["Authorization"] = "Bearer hub-test-key"
            conn.request(
                method,
                path,
                body=json.dumps(body or {"model": "gemini-4-argon"})
                if method == "POST"
                else None,
                headers=headers,
            )
            resp = conn.getresponse()
            raw = resp.read()
            return (
                resp.status,
                {k.lower(): v for k, v in resp.getheaders()},
                (json.loads(raw) if raw else None),
            )
        finally:
            conn.close()

    try:
        yield SimpleNamespace(call=call, state=state, monkeypatch=monkeypatch)
    finally:
        bridge.shutdown()
        bridge.server_close()
        upstream.shutdown()
        upstream.server_close()


def test_facade_open_breaker_returns_503_retry_after_without_upstream_call(facade):
    manager, _ = make_manager()
    facade.monkeypatch.setattr(server, "RESILIENCE", manager)
    facade.state.status = 502
    for _ in range(3):
        status, _, _ = facade.call()
        assert status == 502  # честный ответ upstream, без подмены
    assert facade.state.hits == 3
    status, headers, body = facade.call()
    assert status == 503
    assert facade.state.hits == 3  # fail-fast: upstream не вызывался
    assert headers["retry-after"] == "30"
    assert body["error"] == {
        "message": "Backend 'agy' is temporarily unavailable: circuit breaker is open",
        "type": "resilience_error",
        "code": "CIRCUIT_BREAKER_OPEN",
        "retry_after": 30,
    }
    # Другой бэкенд (opencode-zen) не задет и по-прежнему доходит до upstream.
    facade.state.status = 200
    status, _, _ = facade.call({"model": "big-pickle"})
    assert status == 200 and facade.state.hits == 4


def test_facade_4xx_and_success_do_not_trip_breaker(facade):
    manager, _ = make_manager()
    facade.monkeypatch.setattr(server, "RESILIENCE", manager)
    facade.state.status = 429
    for _ in range(6):
        assert facade.call()[0] == 429  # < 500 — бэкенд жив
    facade.state.status = 200
    assert facade.call()[0] == 200
    assert manager.snapshot()["backends"]["agy"]["state"] == "CLOSED"


def test_facade_flags_off_keeps_legacy_behavior(facade):
    facade.monkeypatch.setattr(
        server,
        "RESILIENCE",
        ResilienceManager(ResilienceFlags(StaticSource({}), env={})),
    )
    facade.state.status = 502
    for _ in range(8):
        assert facade.call()[0] == 502
    assert facade.state.hits == 8


def test_facade_bulkhead_503_before_headers(facade):
    manager, _ = make_manager(env={"BRIDGE_BULKHEAD_MAX_CONCURRENT": "1"})
    facade.monkeypatch.setattr(server, "RESILIENCE", manager)
    held = manager.acquire("agy")
    try:
        status, headers, body = facade.call()
        assert status == 503
        assert headers["retry-after"] == "1"
        assert body["error"]["code"] == "BULKHEAD_CAPACITY_EXCEEDED"
        assert facade.state.hits == 0
    finally:
        held.close()
    assert facade.call()[0] == 200


def test_facade_resilience_endpoint_requires_auth_and_health_contract_is_frozen(facade):
    manager, _ = make_manager()
    facade.monkeypatch.setattr(server, "RESILIENCE", manager)
    status, _, _ = facade.call(path="/v1/resilience", method="GET", auth=False)
    assert status == 401
    facade.state.status = 502
    for _ in range(3):
        facade.call()
    status, _, snap = facade.call(path="/v1/resilience", method="GET")
    assert status == 200
    assert snap["enabled"] is True
    assert snap["backends"]["agy"]["state"] == "OPEN"
    assert snap["backends"]["agy"]["retry_after"] >= 1
    # Бэкенды из каталога видны даже без трафика.
    assert snap["backends"]["codex"] == {
        "state": "CLOSED",
        "generation": 0,
        "failures": 0,
        "retry_after": 0,
        "active": 0,
        "capacity": 64,
    }
    status, _, health = facade.call(path="/health", method="GET", auth=False)
    assert status == 200
    assert sorted(health) == sorted(
        [
            "ok",
            "transport",
            "model",
            "active",
            "max_concurrent",
            "tool_emulation",
            "uptime_s",
        ]
    )
# --------------------------------------------------------------------------- Волна 3: QoSSlotManager

from core.lifecycle import (  # noqa: E402
    KeepaliveController,
    QoSSlotManager,
    get_qos_manager,
    reset_qos_manager,
    set_qos_manager,
)


def _wait_until(predicate, timeout: float = 1.5) -> bool:
    """Ждёт наблюдаемого состояния (синхронизация, а не тайминг): True — наступило."""
    deadline = time.monotonic() + timeout
    tick = threading.Event()
    while not predicate():
        if time.monotonic() >= deadline:
            return False
        tick.wait(0.002)
    return True


def _acquire_async(mgr: QoSSlotManager, is_interactive: bool, **kw):
    """acquire_slot в потоке: (поток, Event готовности, коробка результата)."""
    done = threading.Event()
    box: dict = {}

    def run() -> None:
        try:
            box["result"] = mgr.acquire_slot(is_interactive=is_interactive, **kw)
        finally:
            done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, done, box


def test_reserved_slots_block_background_but_allow_interactive():
    mgr = QoSSlotManager(max_concurrent=8, reserved_interactive=2, queue_timeout_s=5.0)
    # Фоновый лимит = 8 - 2 = 6: шесть фоновых слотов занимаются сразу.
    for _ in range(6):
        assert mgr.acquire_slot(is_interactive=False) == (True, "")
    # Седьмой фоновый не может занять зарезервированный слот и встаёт в очередь.
    bg_thread, bg_done, bg_box = _acquire_async(mgr, is_interactive=False)
    assert _wait_until(lambda: mgr.snapshot()["waiting_background"] == 1)
    assert not bg_done.is_set()
    # Интерактивный в это же время проходит немедленно в резервный слот.
    _, ui_done, ui_box = _acquire_async(mgr, is_interactive=True)
    assert ui_done.wait(1.0)
    assert ui_box["result"] == (True, "")
    snap = mgr.snapshot()
    assert (snap["active_total"], snap["active_background"]) == (7, 6)
    assert (snap["max_concurrent"], snap["reserved_interactive"]) == (8, 2)
    # Освобождение фонового слота будит ожидающего фонового (notify_all).
    mgr.release_slot(is_interactive=False)
    assert bg_done.wait(1.0)
    assert bg_box["result"] == (True, "")
    bg_thread.join(1.0)
    # Потолок total действует и на интерактивных: 7 занято + 1 = 8, дальше — таймаут.
    assert mgr.acquire_slot(is_interactive=True) == (True, "")
    started = time.monotonic()
    assert mgr.acquire_slot(is_interactive=True, timeout=0.15) == (
        False,
        "queue_timeout",
    )
    assert time.monotonic() - started < 1.0
    assert mgr.snapshot()["waiting_interactive"] == 0
    for _ in range(6):
        mgr.release_slot(is_interactive=False)
    mgr.release_slot(is_interactive=True)
    mgr.release_slot(is_interactive=True)
    snap = mgr.snapshot()
    assert snap["active_total"] == 0 and snap["active_background"] == 0


def test_draining_and_client_gone_and_keepalive_false():
    # Draining: отказ мгновенный, даже при свободных слотах, для обоих классов.
    drain = threading.Event()
    drain.set()
    draining = QoSSlotManager(max_concurrent=2, drain_event=drain)
    assert draining.acquire_slot(is_interactive=True) == (False, "draining")
    assert draining.acquire_slot(is_interactive=False) == (False, "draining")
    assert draining.snapshot()["active_total"] == 0

    # Ушедший клиент до ожидания: client_gone проверяется раньше выдачи слота.
    mgr = QoSSlotManager(max_concurrent=1)
    assert mgr.acquire_slot(is_interactive=True, client_gone_fn=lambda: True) == (
        False,
        "client_gone",
    )

    # Ушедший клиент ВО время ожидания: пробуждение release'ом не выдаёт слот.
    assert mgr.acquire_slot(is_interactive=True) == (True, "")
    gone = threading.Event()
    _, done, box = _acquire_async(
        mgr, is_interactive=False, client_gone_fn=gone.is_set, timeout=5.0
    )
    assert _wait_until(lambda: mgr.snapshot()["waiting_background"] == 1)
    gone.set()
    mgr.release_slot(is_interactive=True)  # слот свободен, но клиент уже ушёл
    assert done.wait(1.0)
    assert box["result"] == (False, "client_gone")
    assert mgr.snapshot()["active_total"] == 0

    # keepalive_cb -> False в очереди == клиент ушёл; счётчик ожидания не течёт.
    mgr2 = QoSSlotManager(
        max_concurrent=1, queue_timeout_s=0.3, keepalive_interval_s=0.1
    )
    assert mgr2.acquire_slot(is_interactive=True) == (True, "")
    calls: list[int] = []
    ok, reason = mgr2.acquire_slot(
        is_interactive=True, keepalive_cb=lambda: calls.append(1) or False
    )
    assert (ok, reason) == (False, "client_gone")
    assert calls  # keepalive реально вызывался до отказа
    assert mgr2.snapshot()["waiting_interactive"] == 0
    mgr2.release_slot(is_interactive=True)


def test_singleton_helpers():
    reset_qos_manager()
    try:
        first = get_qos_manager(max_concurrent=7, reserved_interactive=1)
        assert (first.max_concurrent, first.reserved_interactive) == (7, 1)
        # Повторный вызов игнорирует новые параметры и возвращает тот же объект.
        assert get_qos_manager(max_concurrent=99) is first
        # Гонка первого создания: все потоки получают один экземпляр.
        reset_qos_manager()
        barrier = threading.Barrier(8)
        got: list = []

        def grab() -> None:
            barrier.wait()
            got.append(get_qos_manager())

        threads = [threading.Thread(target=grab) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(1.0)
        assert len({id(m) for m in got}) == 1
        # set_qos_manager подменяет синглтон; reset возвращает ленивое создание.
        custom = QoSSlotManager(max_concurrent=2)
        set_qos_manager(custom)
        assert get_qos_manager() is custom
        set_qos_manager(None)
        fresh = get_qos_manager()
        assert fresh is not custom and fresh.max_concurrent == 128
    finally:
        reset_qos_manager()


def test_interactive_request_not_starved_by_background_subagents(facade):
    # Ключевое требование: 8 фоновых сабагентов не голодают интерактивный DSH-запрос.
    mgr = QoSSlotManager(max_concurrent=8, reserved_interactive=2, queue_timeout_s=5.0)
    set_qos_manager(mgr)
    release_upstream = threading.Event()
    acquired = threading.Semaphore(0)
    results: dict[str, tuple] = {}
    lock = threading.Lock()

    def background(idx: int) -> None:
        result = mgr.acquire_slot(is_interactive=False)
        with lock:
            results[f"panel-judge-{idx}"] = result
        if result[0]:
            acquired.release()
            release_upstream.wait(5.0)  # upstream «думает»: слот удерживается
            mgr.release_slot(is_interactive=False)

    threads = [
        threading.Thread(target=background, args=(i,), daemon=True) for i in range(1, 9)
    ]
    try:
        for t in threads:
            t.start()
        # Детерминированно: ровно 6 фоновых внутри (8 - резерв 2), 2 в очереди.
        for _ in range(6):
            assert acquired.acquire(timeout=1.5)
        assert _wait_until(lambda: mgr.snapshot()["waiting_background"] == 2)
        snap = mgr.snapshot()
        assert (snap["active_total"], snap["active_background"]) == (6, 6)
        # Интерактивный запрос из DSH (без subagent_id) — сразу 200, без 503.
        # Фасадный HTTP-запрос занимает зарезервированный интерактивный слот, обходя очередь фоновых.
        status, _, _ = facade.call({"model": "gemini-4-argon"})
        assert status == 200
    finally:
        release_upstream.set()
        for t in threads:
            t.join(1.5)
        assert _wait_until(lambda: mgr.snapshot()["active_total"] == 0, timeout=2.0)
        reset_qos_manager()


def test_bounded_queue_timeout_and_sse_keepalive(facade):
    mgr = QoSSlotManager(
        max_concurrent=1,
        reserved_interactive=0,
        queue_timeout_s=0.35,
        keepalive_interval_s=0.1,
    )
    set_qos_manager(mgr)
    try:
        assert mgr.acquire_slot(is_interactive=False) == (True, "")
        keepalives: list[float] = []

        def keepalive_cb() -> bool:
            keepalives.append(time.monotonic())
            return True  # клиент жив: сервер на этом месте пишет ": keepalive\n\n"

        assert KeepaliveController.sse_comment() == ": keepalive\n\n"
        started = time.monotonic()
        ok, reason = mgr.acquire_slot(is_interactive=True, keepalive_cb=keepalive_cb)
        elapsed = time.monotonic() - started
        # Очередь ограничена BRIDGE_QUEUE_TIMEOUT_S менеджера, а не бесконечна.
        assert (ok, reason) == (False, "queue_timeout")
        assert 0.3 <= elapsed < 1.5
        assert keepalives  # SSE-keepalive уходил, пока запрос ждал слот
        snap = mgr.snapshot()
        assert snap["waiting_interactive"] == 0 and snap["active_total"] == 1
        mgr.release_slot(is_interactive=False)
        # После таймаута очереди мост здоров: интерактивный HTTP-запрос — 200.
        status, _, _ = facade.call({"model": "gemini-4-argon"})
        assert status == 200
    finally:
        if mgr.snapshot()["active_total"]:
            mgr.release_slot(is_interactive=False)
        reset_qos_manager()


def test_graceful_drain_headers_and_rejection(facade):
    # Unit-уровень: drain_event менеджера отклоняет ожидание как "draining".
    drain = threading.Event()
    mgr = QoSSlotManager(max_concurrent=1, drain_event=drain)
    assert mgr.acquire_slot(is_interactive=True) == (True, "")
    _, done, box = _acquire_async(mgr, is_interactive=True, timeout=5.0)
    assert _wait_until(lambda: mgr.snapshot()["waiting_interactive"] == 1)
    drain.set()
    mgr.release_slot(is_interactive=True)  # пробуждение: drain проверяется первым
    assert done.wait(1.0)
    assert box["result"] == (False, "draining")

    # HTTP-уровень: настоящий Handler при shutdown — 503 + Retry-After + X-Bridge-Draining.
    facade.monkeypatch.setattr(server, "_shutting_down", True)
    status, headers, body = facade.call({"model": "gemini-4-argon"})
    assert status == 503
    assert headers["x-bridge-draining"] in ("1", "true")
    assert headers["retry-after"] == "3"  # BRIDGE_RETRY_AFTER_S=3
    assert body["error"]["message"] == "bridge is shutting down"
    assert facade.state.hits == 0  # upstream не вызывался
    # При переопределении BRIDGE_RETRY_AFTER_S через env заголовок меняется соответственно:
    facade.monkeypatch.setenv("BRIDGE_RETRY_AFTER_S", "5")
    status, headers, _ = facade.call({"model": "gemini-4-argon"})
    assert status == 503
    assert headers["retry-after"] == "5"
    assert headers["x-bridge-draining"] in ("1", "true")
    assert facade.state.hits == 0