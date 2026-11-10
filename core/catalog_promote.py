from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core import model_lifecycle as ml
from core.catalog_flags import COMPILED_FLEET_FILE, SIDECAR_FILE
from core.discovery import DiscoveryResult, compute_fingerprint
from core.fleet_compiler import (
    CompileError,
    CompileResult,
    atomic_write_bytes,
    compile_from_disk,
    default_kinds,
    load_receipts,
    render_fleet_json,
)
from core.model_lifecycle import LifecycleError, LifecycleRegistry, ModelRecord
from core.provider_manifest import load_manifests

REGISTRY_FILE = "model-lifecycle.json"
LOCK_FILE = ".lifecycle.lock"
ENV_LOCK_WAIT = "BRIDGE_LIFECYCLE_LOCK_WAIT_S"
ENV_LOCK_POLL = "BRIDGE_LIFECYCLE_LOCK_POLL_S"
DEFAULT_LOCK_WAIT_S = 30.0
DEFAULT_LOCK_POLL_S = 0.05

_PROBE = (ml.EVENT_PROBE_START,)
_TO_PROBING: dict[str, tuple[str, ...]] = {
    ml.STATUS_DISCOVERED: (ml.EVENT_DISCOVERED_OK, *_PROBE),
    ml.STATUS_QUARANTINE: _PROBE,
    ml.STATUS_STALE: _PROBE,
    ml.STATUS_QUARANTINE_FAILED: _PROBE,
    ml.STATUS_DISABLED: (ml.EVENT_SEEN, ml.EVENT_DISCOVERED_OK, *_PROBE),
    ml.STATUS_REJECTED: (ml.EVENT_MANIFEST_CHANGED, ml.EVENT_DISCOVERED_OK, *_PROBE),
    ml.STATUS_CONFIRMED: (ml.EVENT_FINGERPRINT_CHANGED, *_PROBE),
}


class PromoteError(Exception):
    """Отказ промоушена; `slug` — короткая причина без пользовательских данных."""

    def __init__(self, slug: str) -> None:
        """Сохраняет `slug`."""
        super().__init__(slug)
        self.slug = slug


class ProbeOutcome(Protocol):
    """Результат пробника, нужный промоушену (`capability_probe.ProbeResult`)."""

    @property
    def receipt_sha256(self) -> str: ...

    @property
    def fingerprint_sha256(self) -> str: ...

    @property
    def efforts_proven(self) -> Sequence[str]: ...


@dataclass(frozen=True, slots=True)
class PromoteRequest:
    """Подтверждённая пробником модель: ключ реестра и квитанция."""

    provider_id: str
    model_id: str
    receipt_sha256: str
    fingerprint_sha256: str
    efforts_proven: tuple[str, ...]

    @classmethod
    def from_probe(cls, result: ProbeOutcome, provider_id: str, model_id: str) -> PromoteRequest:
        """Запрос из результата пробника."""
        return cls(
            provider_id,
            model_id,
            str(result.receipt_sha256),
            str(result.fingerprint_sha256),
            tuple(result.efforts_proven),
        )


@dataclass(frozen=True, slots=True)
class LockPolicy:
    """Сколько ждать блокировку и как часто опрашивать (секунды)."""

    wait_s: float
    poll_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LockPolicy:
        """Политика из окружения; мусор — значения по умолчанию."""
        wait = _env_float(env, ENV_LOCK_WAIT, DEFAULT_LOCK_WAIT_S)
        return cls(wait, _env_float(env, ENV_LOCK_POLL, DEFAULT_LOCK_POLL_S))


def add_promote_arguments(parser: argparse.ArgumentParser) -> None:
    """Флаги `--promote` и `--state-dir` для CLI пробника."""
    parser.add_argument("--promote", action="store_true", help="confirmed -> lifecycle + каталог атомарно")
    parser.add_argument("--state-dir", type=Path, default=None, help="каталог состояния (BRIDGE_STATE_DIR)")


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    """Неотрицательное число из окружения; нет или мусор — `default`."""
    try:
        return max(0.0, float(env.get(name, default)))
    except (TypeError, ValueError):
        return default


@contextlib.contextmanager
def lifecycle_lock(state_dir: Path, policy: LockPolicy) -> Iterator[None]:
    """Эксклюзивный `flock` на `<state>/.lifecycle.lock`; занят дольше `wait_s` — `PromoteError`."""
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    fd = os.open(Path(state_dir) / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    deadline = time.monotonic() + policy.wait_s
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise PromoteError("lifecycle_lock_busy") from None
                time.sleep(policy.poll_s)
        yield
    finally:
        os.close(fd)


def advance_to_confirmed(registry: LifecycleRegistry, request: PromoteRequest, now: float) -> ModelRecord:
    """Запись до `confirmed` допустимыми переходами; повтор той же квитанции — no-op."""
    key = (request.provider_id, request.model_id, request.fingerprint_sha256)
    record = registry.register(*key)
    done = (record.status, record.receipt_sha256) == (ml.STATUS_CONFIRMED, request.receipt_sha256)
    for event in () if done else _TO_PROBING.get(record.status, ()):
        registry.apply(key, event, now, {"force": True, "reason": "promote"})
    proof = {"receipt_sha256": request.receipt_sha256, "efforts_proven": request.efforts_proven}
    return record if done else registry.apply(key, ml.EVENT_PROBE_PASS, now, proof)


def write_compiled_state(result: CompileResult, fleet_path: Path, sidecar_path: Path) -> None:
    """Атомарная запись `fleet.compiled.json` и `catalog.lock.json`."""
    atomic_write_bytes(fleet_path, render_fleet_json(result.fleet))
    sidecar = json.dumps(result.sidecar, sort_keys=True, indent=2, ensure_ascii=False)
    atomic_write_bytes(sidecar_path, sidecar.encode("utf-8") + b"\n")


def _discovery(
    request: PromoteRequest, registry: LifecycleRegistry, providers_dir: Path | None, env: Mapping[str, str]
) -> dict[str, DiscoveryResult]:
    """Отпечатки провайдеров: проб-провайдер из запроса, прочие с записями — текущие."""
    known = {rec.provider_id for rec in registry.records()} - {request.provider_id}
    manifests = load_manifests(providers_dir, default_kinds(), env=env).manifests
    found = {
        m.provider_id: DiscoveryResult(m.provider_id, compute_fingerprint(m, env))
        for m in manifests
        if m.provider_id in known
    }
    return {**found, request.provider_id: DiscoveryResult(request.provider_id, request.fingerprint_sha256)}


def _confirmed_in_sidecar(path: Path, model_id: str) -> bool:
    """Post-verify: модель в сайдкаре `confirmed`; нечитаемый файл — False."""
    try:
        models = json.loads(path.read_text(encoding="utf-8"))["models"]
        return bool(models[model_id]["status"] == ml.STATUS_CONFIRMED)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _restore(snapshot: Mapping[Path, bytes | None]) -> None:
    """Файлы к исходным байтам (`None` — удалить); сбой любого отката — `rollback_failed`."""
    failed = False
    for path, data in snapshot.items():
        try:
            if data is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write_bytes(path, data)
        except OSError:
            failed = True
    if failed:
        raise PromoteError("rollback_failed")


def _promote_locked(
    request: PromoteRequest, state_dir: Path, providers_dir: Path | None, env: Mapping[str, str]
) -> None:
    """Под `flock`: каталог пишется и проверяется до реестра, реестр пишется последним."""
    registry_path = state_dir / REGISTRY_FILE
    registry = LifecycleRegistry.load(registry_path)
    advance_to_confirmed(registry, request, time.time())
    compiled = compile_from_disk(
        providers_dir,
        None,
        kinds=default_kinds(),
        discovery=_discovery(request, registry, providers_dir, env),
        registry=registry,
        receipts=load_receipts(state_dir / "probes"),
        now=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        env=env,
    )
    fleet, sidecar = state_dir / COMPILED_FLEET_FILE, state_dir / SIDECAR_FILE
    snapshot = {p: p.read_bytes() if p.exists() else None for p in (fleet, sidecar)}
    try:
        write_compiled_state(compiled, fleet, sidecar)
        if not _confirmed_in_sidecar(sidecar, request.model_id):
            raise PromoteError("post_verify_mismatch")
        registry.save(registry_path)
    except BaseException:
        _restore(snapshot)
        raise


def promote_confirmed(
    request: PromoteRequest,
    state_dir: Path,
    *,
    providers_dir: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """'' — модель подтверждена в реестре и сайдкаре; иначе slug причины."""
    source: Mapping[str, str] = os.environ if env is None else env
    try:
        with lifecycle_lock(Path(state_dir), LockPolicy.from_env(source)):
            _promote_locked(request, Path(state_dir), providers_dir, source)
    except PromoteError as exc:
        return exc.slug
    except LifecycleError:
        return "lifecycle_error"
    except CompileError as exc:
        return "compile_error:" + exc.slug
    except OSError:
        return "state_io_error"
    return ""
