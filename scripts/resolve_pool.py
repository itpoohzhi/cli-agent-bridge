#!/usr/bin/env python3
"""Детерминированный резолвер пулов моделей по сайдкару ``catalog-lock/1``.

Кандидаты берутся из карты ``models`` сайдкара; семейство, quota_group и статус
приходят только оттуда (никаких префиксных эвристик и имён вендоров).
Результат — ``pool-lock/1`` с ``lock_sha256`` над каноническим JSON.
Функция детерминирована: без ``random`` и без чтения времени.

CLI: ``resolve_pool.py --role judge --n 3 --seed s1 [--config catalog.lock.json]``.
Коды выхода: 0 — успех, 2 — ``QuorumUnavailable``, 3 — ошибка использования.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from core import quarantine_gate as qg
except ImportError:  # запуск как скрипта: корень репозитория не в sys.path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from core import quarantine_gate as qg

RESOLVER_VERSION = 1
LOCK_SCHEMA = "pool-lock/1"
DEGRADED_HATS = "QUORUM_DEGRADED_HATS"

ENV_CATALOG_LOCK = "BRIDGE_CATALOG_LOCK"
ENV_STATE_DIR = "BRIDGE_STATE_DIR"
ENV_PROBE_DIR = "BRIDGE_PROBE_DIR"
ENV_MAX_CANDIDATES = "BRIDGE_RESOLVER_MAX_CANDIDATES"
ENV_TEMP_OFF = "BRIDGE_RESOLVER_TEMP_OFF"
ENV_DENIED = "BRIDGE_RESOLVER_DENIED"
ENV_DENIED_SUFFIXES = "BRIDGE_RESOLVER_DENIED_SUFFIXES"
ENV_EFFORT_ORDER = "BRIDGE_EFFORT_ORDER"

DEFAULT_STATE_DIR = "~/work/cli-agent-bridge/state"
DEFAULT_MAX_CANDIDATES = 16
DEFAULT_DENIED_SUFFIXES = "-free"

ERROR_RATE_LIMITED = "rate_limited_429"
ERROR_QUOTA_EXHAUSTED = "quota_exhausted"
QUOTA_ERRORS = frozenset({ERROR_RATE_LIMITED, ERROR_QUOTA_EXHAUSTED})

EXIT_OK = 0
EXIT_QUORUM_UNAVAILABLE = 2
EXIT_USAGE = 3


class PolicyError(Exception):
    """Нарушение предусловий резолвера."""


class QuorumUnavailable(PolicyError):
    """Нет допустимой комбинации мест для пула."""

    def __init__(self, reason: str, considered: Mapping[str, str]) -> None:
        super().__init__(reason)
        self.reason = reason
        self.considered = dict(considered)


@dataclass(frozen=True)
class Seat:
    model: str
    effort: str
    family: str
    quota_group: str
    provider: str
    status: str
    probe_receipt_sha256: str
    reserve: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "effort": self.effort,
            "family": self.family,
            "quota_group": self.quota_group,
            "provider": self.provider,
            "status": self.status,
            "probe_receipt_sha256": self.probe_receipt_sha256,
            "reserve": self.reserve,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Seat":
        return cls(
            model=str(data["model"]),
            effort=str(data.get("effort", "")),
            family=str(data.get("family", "")),
            quota_group=str(data.get("quota_group", "")),
            provider=str(data.get("provider", "")),
            status=str(data.get("status", "")),
            probe_receipt_sha256=str(data.get("probe_receipt_sha256", "")),
            reserve=bool(data.get("reserve", False)),
        )


@dataclass(frozen=True)
class PoolLock:
    primary: Tuple[Seat, ...]
    reserves: Tuple[Seat, ...]
    excluded: Mapping[str, str]
    lock: Dict[str, Any]
    lock_sha256: str


# --------------------------------------------------------------------------- helpers


def canonical_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_lock_sha256(lock: Mapping[str, Any]) -> str:
    """sha256 канонического JSON без поля ``lock_sha256``."""
    body = {k: v for k, v in lock.items() if k != "lock_sha256"}
    return _sha256_hex(canonical_bytes(body))


def verify_lock_sha256(lock: Mapping[str, Any]) -> bool:
    return lock.get("lock_sha256") == compute_lock_sha256(lock)


def rank_of(seed: str, role: str, model: str, effort: str) -> str:
    return _sha256_hex("\x00".join((seed, role, model, effort)).encode("utf-8"))


def _state_dir() -> str:
    return os.path.expanduser(os.environ.get(ENV_STATE_DIR) or DEFAULT_STATE_DIR)


def default_catalog_path() -> str:
    env = os.environ.get(ENV_CATALOG_LOCK)
    if env:
        return os.path.expanduser(env)
    return os.path.join(_state_dir(), "catalog.lock.json")


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _env_list(name: str, default: str = "") -> List[str]:
    raw = os.environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


def _load_catalog(
    catalog: Any, config_path: Optional[str]
) -> Tuple[qg.SidecarView, bytes]:
    """Возвращает (представление сайдкара, байты для sha входов)."""
    if catalog is not None:
        if isinstance(catalog, qg.SidecarView):
            return catalog, canonical_bytes(catalog.raw)
        return qg.SidecarView.from_dict(catalog), canonical_bytes(catalog)
    path = os.fspath(config_path) if config_path else default_catalog_path()
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise PolicyError("catalog lock unreadable: %s" % path) from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError as exc:
        raise PolicyError("catalog lock is not valid JSON: %s" % path) from exc
    if not isinstance(data, dict):
        raise PolicyError("catalog lock must be a JSON object")
    return qg.SidecarView.from_dict(data), raw


def pick_default_effort(entry: Mapping[str, Any]) -> str:
    """Старший доказанный effort; иначе первый из ``efforts``/``default_effort``."""
    proven = [str(x) for x in (entry.get("efforts_proven") or [])]
    if proven:
        order = _env_list(ENV_EFFORT_ORDER)
        if order:
            known = [e for e in proven if e in order]
            if known:
                return max(known, key=order.index)
        return proven[-1]
    default = entry.get("default_effort")
    if isinstance(default, str) and default:
        return default
    efforts = entry.get("efforts") or []
    return str(efforts[0]) if efforts else ""


def _receipt_ok(probes_dir: str, sha: str) -> bool:
    path = os.path.join(probes_dir, "%s.json" % sha)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return False
    if _sha256_hex(raw) != sha:
        return False
    try:
        data = json.loads(raw.decode("utf-8"))
    except ValueError:
        return False
    if (
        isinstance(data, dict)
        and "verdict" in data
        and data["verdict"] != qg.STATUS_CONFIRMED
    ):
        return False
    return True


def _resolve_probes_dir(probes_dir: Optional[str]) -> Optional[str]:
    if probes_dir:
        return os.fspath(probes_dir)
    path = os.path.expanduser(
        os.environ.get(ENV_PROBE_DIR) or os.path.join(_state_dir(), "probes")
    )
    return path if os.path.isdir(path) else None


# --------------------------------------------------------------------------- resolver


@dataclass
class _Cand:
    model: str
    effort: str
    rank: str
    entry: Mapping[str, Any]
    reason: str = ""

    def seat(self, reserve: bool) -> Seat:
        probe = self.entry.get("probe") or {}
        return Seat(
            model=self.model,
            effort=self.effort,
            family=str(self.entry.get("family") or ""),
            quota_group=str(self.entry.get("quota_group") or ""),
            provider=str(self.entry.get("provider") or ""),
            status=str(self.entry.get("status") or ""),
            probe_receipt_sha256=str(probe.get("receipt_sha256") or ""),
            reserve=reserve,
        )


def _exclusion_reason(
    cand: _Cand,
    *,
    role_class: str,
    sidecar: qg.SidecarView,
    denied: frozenset,
    denied_suffixes: Sequence[str],
    temp_off: frozenset,
    excluded: frozenset,
    verify_receipts: bool,
    probes_dir: Optional[str],
    enforce_family: bool,
) -> str:
    entry = cand.entry
    model = cand.model
    gated = role_class != qg.CLASS_OPEN
    if model in denied or any(model.endswith(s) for s in denied_suffixes):
        return "denied"
    if model in temp_off:
        return "temp_off"
    if not qg.status_permitted(str(entry.get("status") or ""), role_class):
        return "status"
    probe = entry.get("probe") or {}
    if gated and probe.get("fingerprint_sha256"):
        provider = (sidecar.raw.get("providers") or {}).get(entry.get("provider")) or {}
        if probe.get("fingerprint_sha256") != provider.get("fingerprint_sha256"):
            return "fingerprint"
    if gated and verify_receipts and probes_dir and probe.get("receipt_sha256"):
        if not _receipt_ok(probes_dir, str(probe["receipt_sha256"])):
            return "receipt"
    family = entry.get("family")
    if role_class == qg.CLASS_QUORUM and (
        not family or not entry.get("quorum_eligible")
    ):
        return "not_eligible"
    if enforce_family and not family:
        return "not_eligible"
    if model in excluded:
        return "excluded"
    return ""


def _find_combo(
    cands: Sequence[_Cand], n: int, enforce_family: bool, distinct_quota: bool
) -> Optional[Tuple[_Cand, ...]]:
    for combo in itertools.combinations(cands, n):
        if enforce_family and len({c.entry.get("family") for c in combo}) != n:
            continue
        if distinct_quota and len({c.entry.get("quota_group") for c in combo}) != n:
            continue
        return combo
    return None


def _write_excl(path: str, data: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _write_lock_files(
    lock_path: str, lock: Mapping[str, Any], catalog_bytes: bytes
) -> None:
    directory = os.path.dirname(os.path.abspath(lock_path))
    os.makedirs(directory, exist_ok=True)
    payload = (
        json.dumps(lock, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    _write_excl(lock_path, payload)
    inputs_dir = os.path.join(directory, "pool-inputs")
    os.makedirs(inputs_dir, exist_ok=True)
    target = os.path.join(inputs_dir, _sha256_hex(catalog_bytes))
    if not os.path.exists(target):
        try:
            _write_excl(target, catalog_bytes)
        except FileExistsError:
            pass


def resolve_pool(
    role: str,
    n: int,
    distinct_family: bool = True,
    config_path: Optional[str] = None,
    *,
    distinct_quota: bool = True,
    seed: str = "",
    exclude: Iterable[str] = (),
    degraded_mode: Optional[str] = None,
    catalog: Any = None,
    write_lock_to: Optional[str] = None,
    role_classes: Optional[qg.RoleClasses] = None,
    verify_receipts: bool = True,
    probes_dir: Optional[str] = None,
    temp_off: Iterable[str] = (),
    denied: Iterable[str] = (),
) -> PoolLock:
    """Собирает пул из ``n`` мест для роли. Детерминированна по входам."""
    if n < 1:
        raise PolicyError("n must be >= 1")
    role_name = (role or "").strip().lower()
    if not role_name:
        raise PolicyError("role is required")
    classes = role_classes if role_classes is not None else qg.RoleClasses.from_env()
    role_class = classes.class_of(role_name)
    if (
        role_class == qg.CLASS_QUORUM
        and not distinct_family
        and degraded_mode != DEGRADED_HATS
    ):
        raise PolicyError(
            "distinct_family=False for a quorum role requires degraded_mode=%s"
            % DEGRADED_HATS
        )

    sidecar, catalog_bytes = _load_catalog(catalog, config_path)
    receipts_dir = _resolve_probes_dir(probes_dir) if verify_receipts else None
    denied_set = frozenset(denied) | frozenset(_env_list(ENV_DENIED))
    temp_off_set = frozenset(temp_off) | frozenset(_env_list(ENV_TEMP_OFF))
    suffixes = _env_list(ENV_DENIED_SUFFIXES, DEFAULT_DENIED_SUFFIXES)
    exclude_set = frozenset(exclude)

    cands: List[_Cand] = []
    for model in sorted(sidecar.models):
        entry = sidecar.entry(model)
        if entry is None:
            continue
        effort = pick_default_effort(entry)
        cands.append(
            _Cand(model, effort, rank_of(seed, role_name, model, effort), entry)
        )

    eligible: List[_Cand] = []
    excluded: Dict[str, str] = {}
    for cand in cands:
        cand.reason = _exclusion_reason(
            cand,
            role_class=role_class,
            sidecar=sidecar,
            denied=denied_set,
            denied_suffixes=suffixes,
            temp_off=temp_off_set,
            excluded=exclude_set,
            verify_receipts=verify_receipts,
            probes_dir=receipts_dir,
            enforce_family=distinct_family,
        )
        if cand.reason:
            excluded[cand.model] = cand.reason
        else:
            eligible.append(cand)
    eligible.sort(key=lambda c: (c.rank, c.model))

    max_candidates = _env_int(ENV_MAX_CANDIDATES, DEFAULT_MAX_CANDIDATES)
    combo = _find_combo(eligible[:max_candidates], n, distinct_family, distinct_quota)
    if combo is None:
        if len(eligible) < n:
            reason = "insufficient_candidates"
        elif distinct_family and len({c.entry.get("family") for c in eligible}) < n:
            reason = "insufficient_distinct_families"
        else:
            reason = "insufficient_candidates"
        considered = {
            c.model: ("excluded:%s" % c.reason if c.reason else "eligible")
            for c in cands
        }
        raise QuorumUnavailable(reason, considered)

    chosen = {c.model for c in combo}
    primary = tuple(c.seat(False) for c in combo)
    reserves = tuple(c.seat(True) for c in eligible if c.model not in chosen)

    considered_rows = []
    for cand in cands:
        if cand.reason:
            verdict = "excluded:%s" % cand.reason
        elif cand.model in chosen:
            verdict = "selected"
        else:
            verdict = "reserve"
        considered_rows.append(
            {
                "model": cand.model,
                "effort": cand.effort,
                "rank": cand.rank,
                "verdict": verdict,
            }
        )

    lock: Dict[str, Any] = {
        "schema": LOCK_SCHEMA,
        "resolver_version": RESOLVER_VERSION,
        "role": role_name,
        "n": n,
        "distinct_family": distinct_family,
        "distinct_quota": distinct_quota,
        "degraded_mode": degraded_mode,
        "seed": seed,
        "inputs": {"catalog_lock_sha256": _sha256_hex(catalog_bytes)},
        "considered": considered_rows,
        "primary": [s.to_dict() for s in primary],
        "reserves": [s.to_dict() for s in reserves],
    }
    lock["lock_sha256"] = compute_lock_sha256(lock)

    if write_lock_to:
        _write_lock_files(write_lock_to, lock, catalog_bytes)

    return PoolLock(
        primary=primary,
        reserves=reserves,
        excluded=dict(excluded),
        lock=lock,
        lock_sha256=lock["lock_sha256"],
    )


def next_candidate(
    lock: PoolLock,
    failed: Seat,
    error_class: str,
    active: Sequence[Seat],
) -> Tuple[Optional[Seat], Dict[str, Any]]:
    """Выбирает первый подходящий резерв взамен ``failed`` (§5.3)."""
    distinct_family = bool(lock.lock.get("distinct_family", True))
    distinct_quota = bool(lock.lock.get("distinct_quota", True))
    others = [s for s in active if s.model != failed.model]
    blocked_quotas = {failed.quota_group}
    blocked_quotas.update(s.quota_group for s in others)
    if error_class in QUOTA_ERRORS:
        blocked_quotas.add(failed.quota_group)
    active_families = {s.family for s in others}
    active_models = {s.model for s in active}

    selected: Optional[Seat] = None
    for reserve in lock.reserves:
        if reserve.model in active_models or reserve.model == failed.model:
            continue
        if distinct_family and reserve.family in active_families:
            continue
        if reserve.quota_group == failed.quota_group:
            continue
        if distinct_quota and reserve.quota_group in blocked_quotas:
            continue
        selected = reserve
        break

    chain = "requested=%s -> error=%s -> selected=%s" % (
        failed.model,
        error_class,
        selected.model if selected else "none",
    )
    receipt = {
        "requested": failed.model,
        "error_class": error_class,
        "selected": selected.model if selected else None,
        "excluded_quota_groups": sorted(q for q in blocked_quotas if q),
        "chain": chain,
    }
    return selected, receipt


# --------------------------------------------------------------------------- CLI


class _Parser(argparse.ArgumentParser):
    def error(
        self, message: str
    ) -> "Any":  # exit code 3 вместо 2 (2 = QuorumUnavailable)
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        raise SystemExit(EXIT_USAGE)


def _build_parser() -> argparse.ArgumentParser:
    p = _Parser(
        prog="resolve_pool", description="Резолвер пулов моделей по catalog-lock/1"
    )
    p.add_argument("--role", required=True)
    p.add_argument("--n", required=True, type=int)
    p.add_argument("--seed", default="")
    p.add_argument("--config", default=None, help="путь к catalog.lock.json")
    p.add_argument("--no-distinct-family", action="store_true")
    p.add_argument("--no-distinct-quota", action="store_true")
    p.add_argument("--degraded-mode", default=None)
    p.add_argument("--exclude", action="append", default=[])
    p.add_argument("--write-lock", default=None)
    p.add_argument("--probes-dir", default=None)
    p.add_argument("--no-verify-receipts", action="store_true")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = resolve_pool(
            args.role,
            args.n,
            distinct_family=not args.no_distinct_family,
            config_path=args.config,
            distinct_quota=not args.no_distinct_quota,
            seed=args.seed,
            exclude=args.exclude,
            degraded_mode=args.degraded_mode,
            write_lock_to=args.write_lock,
            verify_receipts=not args.no_verify_receipts,
            probes_dir=args.probes_dir,
        )
    except QuorumUnavailable as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "error": "quorum_unavailable",
                    "reason": exc.reason,
                    "considered": exc.considered,
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        )
        return EXIT_QUORUM_UNAVAILABLE
    except (PolicyError, OSError) as exc:
        sys.stderr.write("resolve_pool: %s\n" % exc)
        return EXIT_USAGE
    sys.stdout.write(json.dumps(result.lock, sort_keys=True, ensure_ascii=False) + "\n")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
