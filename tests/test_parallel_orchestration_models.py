from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

import pytest

import core.model_resolver as model_resolver
import core.parallel_orchestration as orchestration


STARTUP_TIMEOUT = 11.0
TURN_TIMEOUT = 3.0
IDLE_TTL = 30.0


class Catalog(dict[str, dict[str, Any]]):
    """Small mapping/attribute catalog accepted by the L1 resolver API."""

    def __init__(
        self,
        models: dict[str, dict[str, Any]],
        aliases: dict[str, Any] | None = None,
        backends: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(models)
        self.models = models
        self.aliases = aliases or {}
        self.backends = backends or {"fake": {"adapter": "fake"}}


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class FakeAdapter:
    def __init__(self, *, reset_error: Exception | None = None) -> None:
        self.reset_error = reset_error
        self.calls: list[tuple[str, Any]] = []
        self.alive = True

    async def start(self) -> None:
        self.calls.append(("start", None))

    async def stop(self) -> None:
        self.calls.append(("stop", None))
        self.alive = False

    async def reset_context(self) -> None:
        self.calls.append(("reset_context", None))
        if self.reset_error is not None:
            raise self.reset_error

    async def execute_turn(self, request: Any) -> Any:
        self.calls.append(("execute_turn", request))
        return {"request": request}

    def is_alive(self) -> bool:
        return self.alive


class AdapterFactory:
    def __init__(self) -> None:
        self.created: list[FakeAdapter] = []
        self.fail_for: set[str] = set()
        self.reset_error_for: set[str] = set()

    def __call__(self, route: Any) -> FakeAdapter:
        backend_id = str(_field(route, "backend_id", "model_id", default=route))
        if backend_id in self.fail_for:
            raise RuntimeError(f"start failed: {backend_id}")
        reset_error = RuntimeError("reset failed") if backend_id in self.reset_error_for else None
        adapter = FakeAdapter(reset_error=reset_error)
        self.created.append(adapter)
        return adapter


def _field(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _run(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _resolver_error(name: str) -> type[Exception]:
    error = getattr(model_resolver, name, None)
    if error is not None:
        return error

    from core import errors

    return getattr(errors, name)


def _resolve(
    model_id: str,
    models: dict[str, dict[str, Any]],
    aliases: dict[str, Any] | None = None,
) -> Any:
    aliases = aliases or {}
    catalog = Catalog(models, aliases)
    signature = inspect.signature(model_resolver.resolve_model)
    parameters = list(signature.parameters.values())
    args: list[Any] = [model_id]
    kwargs: dict[str, Any] = {}

    for parameter in parameters[1:]:
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if "alias" in parameter.name:
            value = aliases
        elif parameter.name in {"models", "entries", "model_entries"}:
            value = models
        else:
            value = catalog

        if parameter.kind is parameter.POSITIONAL_ONLY:
            args.append(value)
        else:
            kwargs[parameter.name] = value

    return model_resolver.resolve_model(*args, **kwargs)


def _models() -> dict[str, dict[str, Any]]:
    return {
        "deepseek-v4.1-flash-free": {
            "backend_id": "deepseek-v4.1-flash-free",
            "backend": "fake",
        },
        "gemini-4-argon": {"backend_id": "gemini-4-argon", "backend": "fake"},
        "claude-opus-5-5": {"backend_id": "claude-opus-5-5", "backend": "fake"},
        "gemini-3.8-flash": {"backend_id": "gemini-3.8-flash", "backend": "fake"},
        "claude-sonnet-5-5": {"backend_id": "claude-sonnet-5-5", "backend": "fake"},
        "explicit-high": {
            "backend_id": "explicit-high",
            "backend": "fake",
            "effort": None,
        },
        "a": {"backend_id": "a", "backend": "fake"},
        "b": {"backend_id": "b", "backend": "fake"},
    }


def _pool(
    *,
    resident: str = "",
    clock: FakeClock | None = None,
    factory: AdapterFactory | None = None,
) -> Any:
    config = orchestration.PoolConfig(
        startup_timeout=STARTUP_TIMEOUT,
        turn_timeout=TURN_TIMEOUT,
        idle_ttl=IDLE_TTL,
    )
    return orchestration.ResidentPool(
        catalog=Catalog(
            _models(),
            aliases={"deepseek-v4.1-flash": {"backend_id": "deepseek-v4.1-flash-free"}},
        ),
        adapter_factory=factory or AdapterFactory(),
        resident=orchestration.parse_resident_models(resident),
        config=config,
        clock=clock or FakeClock(),
    )


def _slot(pool: Any, model_id: str, effort: str | None = None) -> Any:
    return pool.slot_for(model_id, effort=effort)


def _state_name(slot: Any) -> str:
    state = _field(slot, "state", default=slot)
    return str(_field(state, "name", "value", default=state)).upper()


def _readiness(pool: Any) -> Any:
    value = pool.readiness()
    return _run(value)


def test_alias_deepseek_flash_resolves_to_free() -> None:
    resolved = _resolve(
        "deepseek-v4.1-flash",
        _models(),
        {"deepseek-v4.1-flash": {"backend_id": "deepseek-v4.1-flash-free"}},
    )

    assert _field(resolved, "backend_id") == "deepseek-v4.1-flash-free"


def test_alias_cycle_detected() -> None:
    aliases = {
        "cycle-a": {"target": "cycle-b"},
        "cycle-b": {"upstream_model": "cycle-a"},
    }

    with pytest.raises(_resolver_error("AliasCycleError")):
        _resolve("cycle-a", _models(), aliases)


@pytest.mark.parametrize(
    ("requested", "base_id", "effort"),
    [
        ("gemini-4-argon-high", "gemini-4-argon", "high"),
        ("claude-opus-5-5-high", "claude-opus-5-5", "high"),
        ("gemini-3.8-flash-medium", "gemini-3.8-flash", "medium"),
        ("claude-sonnet-5-5-xhigh", "claude-sonnet-5-5", "xhigh"),
        ("gemini-4-argon-medium", "gemini-4-argon", "medium"),
    ],
)
def test_effort_suffix_normalization(requested: str, base_id: str, effort: str) -> None:
    resolved = _resolve(requested, _models())

    assert _field(resolved, "base_id", "model_id") == base_id
    assert _field(resolved, "effort") == effort


def test_explicit_registration_beats_suffix() -> None:
    resolved = _resolve("explicit-high", _models())

    assert _field(resolved, "backend_id") == "explicit-high"
    assert _field(resolved, "base_id", "model_id") == "explicit-high"
    assert _field(resolved, "effort") is None


def test_no_suffix_means_no_inferred_effort() -> None:
    resolved = _resolve("claude-opus-5-5", _models())

    assert _field(resolved, "effort") is None


def test_free_is_not_effort() -> None:
    resolved = _resolve("deepseek-v4.1-flash-free", _models())

    assert _field(resolved, "backend_id") == "deepseek-v4.1-flash-free"
    assert _field(resolved, "effort") is None


def test_unknown_model_404() -> None:
    with pytest.raises(_resolver_error("ModelNotFoundError")):
        _resolve("missing-model", _models())


def test_resident_env_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BRIDGE_RESIDENT_MODELS", "a,b:2")

    entries = orchestration.parse_resident_models()
    counts = {
        str(_field(entry, "model_id", "model", "id")): int(
            _field(entry, "slots", "count", default=1)
        )
        for entry in entries
    }

    assert counts == {"a": 1, "b": 2}


def test_slot_key_distinct_per_effort() -> None:
    pool = _pool()

    medium = pool.key_for("gemini-4-argon-medium")
    high = pool.key_for("gemini-4-argon-high")
    alias = pool.key_for("deepseek-v4.1-flash")
    backend = pool.key_for("deepseek-v4.1-flash-free")

    assert medium != high
    assert alias == backend


def test_pinned_not_evicted_on_idle() -> None:
    clock = FakeClock()
    pool = _pool(resident="a", clock=clock)
    _run(pool.prewarm())
    _run(pool.execute_turn("b", {"turn": 1}))

    clock.advance(IDLE_TTL + 1.0)
    _run(pool.evict_idle())

    assert _slot(pool, "a") is not None
    assert _slot(pool, "b") is None


def test_reset_called_before_every_turn() -> None:
    factory = AdapterFactory()
    pool = _pool(factory=factory)

    _run(pool.execute_turn("a", {"turn": 1}))
    _run(pool.execute_turn("a", {"turn": 2}))

    calls = [name for name, _ in factory.created[0].calls]
    assert calls == [
        "start",
        "reset_context",
        "execute_turn",
        "reset_context",
        "execute_turn",
    ]


def test_reset_failure_recycles_slot() -> None:
    factory = AdapterFactory()
    factory.reset_error_for.add("a")
    pool = _pool(factory=factory)

    with pytest.raises(RuntimeError, match="reset failed"):
        _run(pool.execute_turn("a", {"turn": 1}))

    assert _state_name(_slot(pool, "a")) == "RECYCLING"


def test_prewarm_marks_ready_only_after_all_required() -> None:
    pool = _pool(resident="a,b:2")

    before = _readiness(pool)
    assert not bool(_field(before, "ready", default=False))

    _run(pool.prewarm())
    after = _readiness(pool)

    assert bool(_field(after, "ready", default=False))
    assert list(_field(after, "not_ready", default=[])) == []


def test_prewarm_failure_yields_degraded_with_list() -> None:
    factory = AdapterFactory()
    factory.fail_for.add("b")
    pool = _pool(resident="a,b", factory=factory)

    _run(pool.prewarm())
    readiness = _readiness(pool)
    not_ready = [str(item) for item in _field(readiness, "not_ready", default=[])]

    assert bool(_field(readiness, "degraded", default=False))
    assert any("b" in item for item in not_ready)


def test_watchdog_restarts_dead_slot() -> None:
    factory = AdapterFactory()
    pool = _pool(resident="a", factory=factory)
    _run(pool.prewarm())
    original = factory.created[0]
    original.alive = False

    supervisor = orchestration.PoolSupervisor(pool)
    _run(supervisor.watchdog_once())

    assert len(factory.created) == 2
    assert factory.created[-1].alive
    assert _state_name(_slot(pool, "a")) == "READY"


def test_startup_validation_flags_missing_route() -> None:
    catalog = Catalog(
        {
            "valid": {"backend_id": "valid", "backend": "fake"},
            "missing": {"backend_id": "missing"},
        },
        backends={"fake": {"adapter": "fake"}},
    )

    result = orchestration.validate_catalog(catalog)
    errors = [str(item) for item in _field(result, "errors", default=result)]

    assert any("missing" in error for error in errors)


def test_timeouts_separated() -> None:
    config = orchestration.PoolConfig(
        startup_timeout=STARTUP_TIMEOUT,
        turn_timeout=TURN_TIMEOUT,
        idle_ttl=IDLE_TTL,
    )

    assert config.startup_timeout == STARTUP_TIMEOUT
    assert config.turn_timeout == TURN_TIMEOUT
    assert config.startup_timeout != config.turn_timeout


def test_core_has_no_vendor_literals() -> None:
    root = Path(__file__).resolve().parents[1] / "core"
    forbidden = ("/clear", "/new", "muse-bin", "--daemon")
    findings: list[str] = []

    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for literal in forbidden:
            if literal in text:
                findings.append(f"{path.relative_to(root)}: {literal}")

    assert findings == []
