"""Клиент квоты Muse через `usage --json` (VER-003, AD-003): запуск строго
через `muse-cli.sh`, single-flight + TTL от `time.monotonic()`, Fail-Open/Closed.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

_DEFAULT_TTL_S = 30.0
_DEFAULT_TIMEOUT_S = 15.0
_TTL_ENV = "MUSE_USAGE_CACHE_TTL_S"
_TIMEOUT_ENV = "MUSE_USAGE_TIMEOUT_S"
_WRAPPER_ENV = "MUSE_CLI_WRAPPER"
_WRAPPER_SUFFIX = ".config/muse-launch/muse-cli.sh"

Runner = Callable[[list[str]], tuple[int, str, str]]
Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class MuseUsageSnapshot:
    """Неизменяемый снимок квоты Muse."""

    status: str
    tier: str | None = None
    window_used_percent: float | None = None
    weekly_used_percent: float | None = None
    reset_at: int | None = None
    as_of_ms: int | None = None
    source: str | None = None
    error_code: str | None = None


def _unknown(error_code: str) -> MuseUsageSnapshot:
    return MuseUsageSnapshot(status="unknown", error_code=error_code)


def _positive_seconds(raw: object, default: float) -> float:
    try:
        value = float(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    if not math.isfinite(value) or value <= 0:
        return default
    return value


def usage_ttl_s(environ: Mapping[str, str] | None = None) -> float:
    """TTL кэша usage в секундах: env или дефолт 30 с (ASM-004)."""
    env = os.environ if environ is None else environ
    return _positive_seconds(env.get(_TTL_ENV, ""), _DEFAULT_TTL_S)


def resolve_wrapper_path(environ: Mapping[str, str] | None = None) -> str:
    """Путь обёртки запуска Muse: env или `~/.config/muse-launch/muse-cli.sh`."""
    env = os.environ if environ is None else environ
    override = env.get(_WRAPPER_ENV, "").strip()
    if override:
        return override
    home = env.get("HOME", "").strip()
    if home:
        return os.path.join(home, _WRAPPER_SUFFIX)
    return os.path.expanduser(os.path.join("~", _WRAPPER_SUFFIX))


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _number(mapping: Mapping[str, object], key: str) -> float:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{key} must be finite")
    return number


def _text(mapping: Mapping[str, object], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _window(allowance: Mapping[str, object], key: str) -> tuple[float, int]:
    window = _mapping(allowance.get(key), key)
    return _number(window, "usedPercent"), int(_number(window, "resetsAtMs"))


def parse_usage_json(text: str) -> MuseUsageSnapshot:
    """Парсит `muse usage --json` (`schemaVersion: 1`); иначе `ValueError`."""
    try:
        payload = _mapping(json.loads(text), "payload")
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid usage JSON") from exc
    version = payload.get("schemaVersion")
    if isinstance(version, bool) or version != 1:
        raise ValueError("unsupported usage schemaVersion")
    allowance = _mapping(payload.get("allowance"), "allowance")
    win_used, win_reset = _window(allowance, "window")
    week_used, week_reset = _window(allowance, "weekly")
    resets = [
        r // 1000
        for used, r in ((win_used, win_reset), (week_used, week_reset))
        if used >= 100
    ]
    exhausted = bool(resets)
    return MuseUsageSnapshot(
        status="exhausted" if exhausted else "ok",
        tier=_text(allowance, "tier"),
        window_used_percent=win_used,
        weekly_used_percent=week_used,
        reset_at=max(resets) if exhausted else None,
        as_of_ms=int(_number(allowance, "asOfMs")),
        source=_text(allowance, "source"),
    )


def _default_runner(argv: list[str]) -> tuple[int, str, str]:
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=_positive_seconds(
                os.environ.get(_TIMEOUT_ENV, ""), _DEFAULT_TIMEOUT_S
            ),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("muse usage timed out") from exc
    return done.returncode, done.stdout, done.stderr


class MuseUsageClient:
    """Единственный владелец состояния usage: кэш, inflight и замок."""

    def __init__(
        self,
        runner: Runner | None = None,
        *,
        ttl_s: float | None = None,
        wrapper_path: str | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._runner: Runner = _default_runner if runner is None else runner
        self._ttl_s = (
            usage_ttl_s() if ttl_s is None else _positive_seconds(ttl_s, _DEFAULT_TTL_S)
        )
        self._wrapper_path = wrapper_path if wrapper_path else resolve_wrapper_path()
        self._clock: Clock = time.monotonic if clock is None else clock
        self._cache: tuple[MuseUsageSnapshot, float] | None = None
        self._inflight: threading.Event | None = None
        self._lock = threading.Lock()

    def _fresh(self) -> MuseUsageSnapshot | None:
        if self._cache is None:
            return None
        snapshot, fetched_at = self._cache
        return snapshot if self._clock() - fetched_at < self._ttl_s else None

    def _run_refresh(self, event: threading.Event) -> MuseUsageSnapshot:
        try:
            snapshot = self._fetch()
            with self._lock:
                self._cache = (snapshot, self._clock())
            return snapshot
        finally:
            with self._lock:
                if self._inflight is event:
                    self._inflight = None
            event.set()

    def _acquire_slot(self, force_refresh: bool) -> tuple[MuseUsageSnapshot | None, MuseUsageSnapshot | None, threading.Event | None, bool]:
        with self._lock:
            if not force_refresh and (fresh := self._fresh()) is not None:
                return fresh, None, None, False
            stale = self._cache[0] if self._cache is not None else None
            if self._inflight is not None:
                return None, stale, self._inflight, False
            self._inflight = threading.Event()
            return None, stale, self._inflight, True

    def get_snapshot(self, *, force_refresh: bool = False, wait_timeout_s: float | None = None) -> MuseUsageSnapshot:
        """Снимок квоты: TTL-кэш + single-flight; ``wait_timeout_s`` ограничивает блок на hot-path."""
        while True:
            fresh, stale, event, leader = self._acquire_slot(force_refresh)
            if fresh is not None:
                return fresh
            assert event is not None
            if leader and wait_timeout_s is None:
                return self._run_refresh(event)
            if leader:
                threading.Thread(target=self._run_refresh, args=(event,), daemon=True).start()
            if not event.wait(timeout=wait_timeout_s):
                return stale if stale is not None else _unknown("refresh_pending")
            with self._lock:
                if self._cache is not None:
                    return self._cache[0]
            if wait_timeout_s is not None:
                return _unknown("refresh_pending")

    def _fetch(self) -> MuseUsageSnapshot:
        try:
            rc, stdout, _stderr = self._runner([self._wrapper_path, "usage", "--json"])
        except TimeoutError:
            return _unknown("timeout")
        except FileNotFoundError:
            return _unknown("wrapper_not_found")
        except OSError:
            return _unknown("runner_os_error")
        except Exception:
            return _unknown("runner_error")
        if rc != 0:
            return _unknown(f"exit_{rc}")
        try:
            return parse_usage_json(stdout)
        except ValueError:
            return _unknown("invalid_usage_json")
