"""Узкий адаптер параметров запроса (слой B, §4.5 архитектуры).

Чистая логика решения «что делать с 400/422 от апстрима» плюс небольшой
персистентный кэш выученных профилей параметров. Модуль агент-агностичен:
не знает имён вендоров и агентов, опирается только на тело ошибки и контракт
шлюза. Все эксплуатационные параметры настраиваются через окружение:

- ``BRIDGE_PARAM_ADAPTER_WHITELIST`` — сужает глобальный whitelist (только ∩);
- ``BRIDGE_PARAM_ADAPTER_ERROR_PATTERN`` — regex маркеров ошибки;
- ``BRIDGE_PARAM_ADAPTER_NEAR_CHARS`` — окно «рядом с маркером», символов;
- ``BRIDGE_PARAM_PROFILE_TTL_S`` — TTL выученного профиля, секунд;
- ``BRIDGE_QUORUM_ROLE_PREFIXES`` — префиксы ролей кворумных вызовов;
- ``BRIDGE_STATE_DIR`` — каталог состояния (``param-profiles.json``);
- ``BRIDGE_PARAM_TEMPERATURE_MAX`` / ``BRIDGE_PARAM_STOP_MAX`` — границы нормализации.

Решение ``decide`` ничего не отправляет и не пишет: ретрай (не более одного
на ход) выполняет вызывающий адаптер.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

GLOBAL_WHITELIST: Tuple[str, ...] = (
    "reasoning_effort",
    "effort",
    "thinking",
    "temperature",
    "top_p",
)

# Параметры «думающего» класса: в кворуме их нельзя молча снимать.
DEGRADE_PARAMS: Tuple[str, ...] = ("reasoning_effort", "effort", "thinking")

TRIGGER_STATUSES: Tuple[int, ...] = (400, 422)

DEFAULT_ERROR_PATTERN = r"unsupported|unknown|not supported|invalid|unrecognized"
DEFAULT_PROFILE_TTL_S = 86400.0
DEFAULT_NEAR_CHARS = 60
DEFAULT_QUORUM_PREFIXES: Tuple[str, ...] = (
    "coder",
    "reviewer",
    "judge",
    "skeptic",
    "architect",
    "analyst",
    "summarizer",
    "answer",
    "hats",
    "brief",
)
DEFAULT_STATE_DIR = "~/work/cli-agent-bridge/state"
PROFILE_FILENAME = "param-profiles.json"
REVIEW_PROFILE_HEADER_VALUE = "zero-canon"

HEADER_DEGRADED = "X-Bridge-Degraded"
HEADER_ADAPTED = "X-Bridge-Param-Adapted"

_EFFORT_KEYS: Tuple[str, ...] = ("reasoning_effort", "effort")
_EFFORT_FIELDS: Tuple[str, ...] = ("reasoning_effort", "effort", "none")


# --------------------------------------------------------------------------
# Конфигурация из окружения
# --------------------------------------------------------------------------


def _env(env: Optional[Mapping[str, str]]) -> Mapping[str, str]:
    return os.environ if env is None else env


def _env_float(
    name: str, default: float, env: Optional[Mapping[str, str]] = None
) -> float:
    raw = _env(env).get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(str(raw).strip())
    except ValueError:
        return default
    if math.isnan(value) or math.isinf(value) or value <= 0:
        return default
    return value


def _env_int(name: str, default: int, env: Optional[Mapping[str, str]] = None) -> int:
    return int(_env_float(name, float(default), env))


def _split_csv(raw: str) -> Tuple[str, ...]:
    return tuple(p.strip() for p in raw.split(",") if p.strip())


def resolve_whitelist(env: Optional[Mapping[str, str]] = None) -> Tuple[str, ...]:
    """Глобальный whitelist, суженный env (пересечение; расширять нельзя)."""
    raw = _env(env).get("BRIDGE_PARAM_ADAPTER_WHITELIST")
    if raw is None or not str(raw).strip():
        return GLOBAL_WHITELIST
    wanted = {p.lower() for p in _split_csv(str(raw))}
    return tuple(p for p in GLOBAL_WHITELIST if p in wanted)


def resolve_error_pattern(env: Optional[Mapping[str, str]] = None) -> "re.Pattern[str]":
    raw = _env(env).get("BRIDGE_PARAM_ADAPTER_ERROR_PATTERN")
    if raw and str(raw).strip():
        try:
            return re.compile(str(raw), re.IGNORECASE)
        except re.error:
            pass
    return re.compile(DEFAULT_ERROR_PATTERN, re.IGNORECASE)


def resolve_profile_ttl_s(env: Optional[Mapping[str, str]] = None) -> float:
    return _env_float("BRIDGE_PARAM_PROFILE_TTL_S", DEFAULT_PROFILE_TTL_S, env)


def resolve_quorum_prefixes(env: Optional[Mapping[str, str]] = None) -> Tuple[str, ...]:
    raw = _env(env).get("BRIDGE_QUORUM_ROLE_PREFIXES")
    if raw is not None and str(raw).strip():
        parsed = tuple(p.lower() for p in _split_csv(str(raw)))
        if parsed:
            return parsed
    return DEFAULT_QUORUM_PREFIXES


def resolve_state_dir(env: Optional[Mapping[str, str]] = None) -> Path:
    raw = _env(env).get("BRIDGE_STATE_DIR") or DEFAULT_STATE_DIR
    return Path(os.path.expanduser(str(raw)))


# --------------------------------------------------------------------------
# Решение
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Passthrough:
    """Ответ апстрима отдаётся как есть."""


@dataclass(frozen=True)
class RetryWithout:
    """Один ретрай хода без параметра ``param``."""

    param: str


@dataclass(frozen=True)
class Degraded:
    """Кворумный вызов: параметр нельзя снять молча, отвечаем 422 param_degraded."""

    param: str


Decision = Union[Passthrough, RetryWithout, Degraded]


def _body_text(body: Union[bytes, bytearray, str, Mapping[str, Any], None]) -> str:
    if body is None:
        return ""
    if isinstance(body, (bytes, bytearray)):
        return bytes(body).decode("utf-8", errors="replace")
    if isinstance(body, str):
        return body
    try:
        return json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(body)


def find_culprit(
    body: Union[bytes, bytearray, str, Mapping[str, Any], None],
    sent: Mapping[str, Any],
    whitelist: Sequence[str],
    env: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Однозначно названный в теле ошибки параметр из whitelist ∩ keys(sent).

    Возвращает None, если назван ни один либо больше одного параметра.
    """
    text = _body_text(body)
    if not text:
        return None
    marker = resolve_error_pattern(env)
    near = _env_int("BRIDGE_PARAM_ADAPTER_NEAR_CHARS", DEFAULT_NEAR_CHARS, env)
    allowed = [p for p in whitelist if p in GLOBAL_WHITELIST and p in sent]
    named = []
    for param in allowed:
        pattern = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(param) + r"(?![A-Za-z0-9_])", re.IGNORECASE
        )
        for match in pattern.finditer(text):
            window = text[max(0, match.start() - near) : match.end() + near]
            if marker.search(window):
                named.append(param)
                break
    if len(named) == 1:
        return named[0]
    return None


def decide(
    status: int,
    body: Union[bytes, bytearray, str, Mapping[str, Any], None],
    sent: Mapping[str, Any],
    profile: Optional["ParamProfile"],
    whitelist: Optional[Sequence[str]],
    quorum_call: bool,
) -> Decision:
    """Чистое решение по ответу апстрима. Не имеет побочных эффектов."""
    if status not in TRIGGER_STATUSES:
        return Passthrough()
    wl = resolve_whitelist() if whitelist is None else tuple(whitelist)
    param = find_culprit(body, sent, wl)
    if param is None:
        return Passthrough()
    if quorum_call and param in DEGRADE_PARAMS:
        return Degraded(param)
    return RetryWithout(param)


# --------------------------------------------------------------------------
# Кворумные вызовы и ответы
# --------------------------------------------------------------------------


def is_quorum_call(
    subagent_id: Optional[str],
    review_profile: Optional[str],
    prefixes: Optional[Iterable[str]] = None,
) -> bool:
    """Роль = часть ``X-Subagent-Id`` до первого ``-``; второй признак — Zero-Canon."""
    if (
        review_profile
        and str(review_profile).strip().lower() == REVIEW_PROFILE_HEADER_VALUE
    ):
        return True
    if not subagent_id:
        return False
    role = str(subagent_id).strip().split("-", 1)[0].lower()
    if not role:
        return False
    pool = (
        resolve_quorum_prefixes()
        if prefixes is None
        else tuple(str(p).strip().lower() for p in prefixes)
    )
    return role in pool


def degraded_response(
    param: str, model: str
) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    body = {"error": {"type": "param_degraded", "param": param, "model": model}}
    return 422, body, {HEADER_DEGRADED: param}


def adapted_headers(param: str) -> Dict[str, str]:
    return {HEADER_ADAPTED: param}


# --------------------------------------------------------------------------
# Профили параметров (выученные снятия)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamProfile:
    """Активные (неистёкшие) снятия параметров для одной тройки провайдер/модель/отпечаток."""

    dropped: Tuple[str, ...] = ()

    def drops(self, param: str) -> bool:
        return param in self.dropped

    def __bool__(self) -> bool:
        return bool(self.dropped)


def profile_key(provider_id: str, model_id: str, fingerprint_sha256: str) -> str:
    return "(%s|%s|%s)" % (provider_id, model_id, fingerprint_sha256)


class ParamProfileStore:
    """Файловый кэш профилей: ``{key: {param: {action, learned_at, expires_at}}}``.

    Запись атомарна (tmp -> fsync -> os.replace). Часы инъектируемы для тестов.
    """

    def __init__(
        self,
        path: Optional[Union[str, Path]] = None,
        ttl_s: Optional[float] = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = (
            Path(path) if path is not None else resolve_state_dir() / PROFILE_FILENAME
        )
        self._ttl_s = float(ttl_s) if ttl_s is not None else resolve_profile_ttl_s()
        self._clock = clock
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        profiles = raw.get("profiles") if isinstance(raw, dict) else None
        return profiles if isinstance(profiles, dict) else {}

    def _write(self, profiles: Dict[str, Dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"version": 1, "profiles": profiles},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        fd, tmp = tempfile.mkstemp(
            dir=str(self._path.parent), prefix=".param-profiles.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, str(self._path))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(
        self, provider_id: str, model_id: str, fingerprint_sha256: str
    ) -> ParamProfile:
        now = self._clock()
        with self._lock:
            entry = self._load().get(
                profile_key(provider_id, model_id, fingerprint_sha256)
            )
        if not isinstance(entry, dict):
            return ParamProfile()
        alive = []
        for param, meta in entry.items():
            if not isinstance(meta, dict) or meta.get("action") != "drop":
                continue
            try:
                expires_at = float(meta.get("expires_at", 0))
            except (TypeError, ValueError):
                continue
            if expires_at > now:
                alive.append(param)
        return ParamProfile(dropped=tuple(sorted(alive)))

    def record_drop(
        self, provider_id: str, model_id: str, fingerprint_sha256: str, param: str
    ) -> ParamProfile:
        now = self._clock()
        key = profile_key(provider_id, model_id, fingerprint_sha256)
        with self._lock:
            profiles = self._load()
            entry = profiles.get(key)
            entry = dict(entry) if isinstance(entry, dict) else {}
            entry[param] = {
                "action": "drop",
                "learned_at": now,
                "expires_at": now + self._ttl_s,
            }
            profiles[key] = entry
            # Попутно вычищаем истёкшее, чтобы файл не рос.
            for k in list(profiles):
                kept = {
                    p: m
                    for p, m in (
                        profiles[k].items() if isinstance(profiles[k], dict) else []
                    )
                    if isinstance(m, dict) and _alive(m, now)
                }
                if kept:
                    profiles[k] = kept
                else:
                    del profiles[k]
            self._write(profiles)
        return self.get(provider_id, model_id, fingerprint_sha256)


def _alive(meta: Mapping[str, Any], now: float) -> bool:
    try:
        return float(meta.get("expires_at", 0)) > now
    except (TypeError, ValueError):
        return False


def apply_profile(
    body: Mapping[str, Any], profile: Optional[ParamProfile]
) -> Dict[str, Any]:
    """Копия тела без выученно-снятых параметров."""
    if not profile:
        return dict(body)
    return strip_always(body, profile.dropped)


def strip_always(body: Mapping[str, Any], params: Iterable[str]) -> Dict[str, Any]:
    """Копия тела без перечисленных параметров (вход не мутируется)."""
    drop = set(params)
    return {k: v for k, v in body.items() if k not in drop}


# --------------------------------------------------------------------------
# Нормализация параметров по диалекту манифеста
# --------------------------------------------------------------------------


def _to_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        try:
            num = float(value.strip())
        except ValueError:
            return None
    else:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def _to_positive_int(value: Any) -> Optional[int]:
    num = _to_number(value)
    if num is None or num < 1 or num != int(num):
        return None
    return int(num)


def normalize_params(
    body: Mapping[str, Any],
    *,
    effort_field: str,
    effort_map: Optional[Mapping[str, Any]] = None,
    strip: Iterable[str] = (),
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Привести параметры запроса к диалекту бэкенда. Чистая, вход не мутируется."""
    field = effort_field if effort_field in _EFFORT_FIELDS else "none"
    emap = effort_map or {}
    out: Dict[str, Any] = copy.deepcopy(dict(body))

    # effort: переименование/патч по диалекту.
    effort_value: Any = None
    for key in _EFFORT_KEYS:
        if key in out:
            value = out.pop(key)
            if effort_value is None and value is not None:
                effort_value = value
    if effort_value is not None:
        patch = emap.get(effort_value) if isinstance(effort_value, str) else None
        if isinstance(patch, Mapping):
            out.update(copy.deepcopy(dict(patch)))
        elif field != "none":
            out[field] = effort_value

    # temperature / top_p: числа в допустимых границах, мусор снимается.
    t_max = _env_float("BRIDGE_PARAM_TEMPERATURE_MAX", 2.0, env)
    for key, upper in (("temperature", t_max), ("top_p", 1.0)):
        if key in out:
            num = _to_number(out[key])
            if num is None:
                del out[key]
            else:
                out[key] = min(max(num, 0.0), upper)

    # stop: str или list[str], не более N.
    if "stop" in out:
        stop = out["stop"]
        limit = _env_int("BRIDGE_PARAM_STOP_MAX", 4, env)
        if isinstance(stop, str):
            if not stop:
                del out["stop"]
        elif isinstance(stop, (list, tuple)):
            items = [s for s in stop if isinstance(s, str) and s][:limit]
            if items:
                out["stop"] = items
            else:
                del out["stop"]
        else:
            del out["stop"]

    # max_tokens / max_completion_tokens: положительный int.
    for key in ("max_tokens", "max_completion_tokens"):
        if key in out:
            number = _to_positive_int(out[key])
            if number is None:
                del out[key]
            else:
                out[key] = number

    # tools / tool_choice: пустые tools => снять оба; валидное не трогаем.
    if "tools" in out:
        tools = out["tools"]
        if not isinstance(tools, (list, tuple)) or not tools:
            del out["tools"]
            out.pop("tool_choice", None)
    elif "tool_choice" in out:
        del out["tool_choice"]

    for key in strip:
        out.pop(key, None)
    return out
