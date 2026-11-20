"""Каноническая конфигурация длинных сессий agy-bridge: os.environ > dynamic_config.json > default."""

from __future__ import annotations

import json
import math
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Final, cast

from core.correlation_contract import DEFAULT_CORR_MAX_LEN, build_validated_header
from core.prompt_budget_policy import LazyPromptMaterializer
from core.tool_turn_settle_policy import ToolTurnSettleConfig, decide_session_commit

AGY_CONV_HEADER_NAME: Final[str] = "X-Agy-Conversation-Id"
DEFAULT_PROMPT_BYTES_CAP: Final[int] = 98304
LOOPBACK_PEERS: Final[tuple[str, ...]] = ("127.0.0.1", "::1", "::ffff:127.0.0.1")

_LOOPBACK_SET: Final[frozenset[str]] = frozenset(LOOPBACK_PEERS)
_BOOL_MAP: Final[dict[str, bool]] = {
    "1": True, "true": True, "yes": True, "on": True,
    "0": False, "false": False, "no": False, "off": False,
}
_DIRECT_OVERRIDES: Final[dict[str, str]] = {"direct": "1", "georouter": "0"}
_DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).resolve().parent.parent / "dynamic_config.json"
_CACHE_TTL_S: Final[float] = 0.5
_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, tuple[object, ...], dict[str, object]]] = {}


def _present(val: object) -> bool:
    return not isinstance(val, type(None))


def _read_json_file(path: Path, hit: tuple[float, tuple[object, ...], dict[str, object]] | None) -> tuple[tuple[object, ...], dict[str, object]]:
    sig: tuple[object, ...] = ()
    result: dict[str, object] = {}
    try:
        st = os.stat(path)
        sig = (st.st_mtime_ns, st.st_size, st.st_ino)
        same = bool(hit) and not set(sig).symmetric_difference(hit[1]) if hit else False
        if same and hit:
            result = hit[2]
        else:
            parsed = cast("object", json.loads(path.read_text(encoding="utf-8")))
            result = cast("dict[str, object]", parsed) if isinstance(parsed, dict) else {}
    except (OSError, ValueError):
        result = {}
    return sig, result


def _load_dynamic_config(config_path: Path | None = None) -> dict[str, object]:
    path = config_path if _present(config_path) else _DEFAULT_CONFIG_PATH
    key = str(path)
    now = time.monotonic()
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    fresh = (now - hit[0]) < _CACHE_TTL_S if hit else False
    result: dict[str, object] = hit[2] if all((bool(hit), fresh)) and hit else {}
    if not fresh:
        sig, result = _read_json_file(path, hit)
        with _CACHE_LOCK:
            _CACHE[key] = (now, sig, result)
    return result


def is_loopback_peer(handler: object) -> bool:
    """Безопасно проверяет client_address[0] в LOOPBACK_PEERS; default-deny при отсутствии/моке."""
    addr: object = getattr(handler, "client_address", None)
    seq = cast("tuple[object, ...] | list[object]", addr) if isinstance(addr, (tuple, list)) else ()
    host: object = seq[0] if seq else ""
    return all((isinstance(host, str), _LOOPBACK_SET.__contains__(str(host))))


def _parse_bool(raw: object, default: bool) -> bool:
    result = raw if isinstance(raw, bool) else _BOOL_MAP.get(str(raw).strip().lower(), default)
    return result


def _raw_setting(dyn_key: str, env_key: str, config_path: Path | None) -> object:
    env_val = os.environ.get(env_key, "").strip()
    result: object = env_val if env_val else _load_dynamic_config(config_path).get(dyn_key)
    return result


def read_bool_setting(
    dyn_key: str, env_key: str, default: bool, *, config_path: Path | None = None
) -> bool:
    """Читает bool по приоритету os.environ > dynamic_config.json > default."""
    raw = _raw_setting(dyn_key, env_key, config_path)
    result = _parse_bool(raw, default) if _present(raw) else default
    return result


def read_float_setting(
    dyn_key: str,
    env_key: str,
    default: float,
    bounds: tuple[float, float],
    *,
    config_path: Path | None = None,
) -> float:
    """Читает ограниченный float по приоритету os.environ > dynamic_config.json > default."""
    raw = _raw_setting(dyn_key, env_key, config_path)
    value = default
    if all((_present(raw), bool(str(raw).strip()))):
        try:
            cand = float(str(raw).strip())
            if math.isfinite(cand):
                value = max(bounds[0], min(bounds[1], cand))
        except ValueError:
            value = default
    return value


def read_int_setting(
    dyn_key: str,
    env_key: str,
    default: int,
    bounds: tuple[int, int],
    *,
    config_path: Path | None = None,
) -> int:
    """Читает ограниченный int по приоритету os.environ > dynamic_config.json > default."""
    raw = _raw_setting(dyn_key, env_key, config_path)
    value = default
    if all((_present(raw), bool(str(raw).strip()))):
        try:
            cand = int(str(raw).strip())
            value = max(bounds[0], min(bounds[1], cand))
        except ValueError:
            value = default
    return value


def tool_settle_config(*, config_path: Path | None = None) -> ToolTurnSettleConfig:
    """Конфигурация окна завершения tool-turn (stall 30.0 с, settle 5.0 с, eof_grace 1.5 с)."""
    return ToolTurnSettleConfig(
        settle_timeout_s=read_float_setting(
            "tool_settle_timeout_s", "AGY_TOOL_SETTLE_TIMEOUT_S", 5.0, (0.05, 60.0), config_path=config_path
        ),
        stall_timeout_s=read_float_setting(
            "tool_call_stall_timeout_s", "AGY_TOOL_CALL_STALL_TIMEOUT_S", 30.0, (0.05, 300.0), config_path=config_path
        ),
        eof_grace_s=read_float_setting(
            "tool_settle_eof_grace_s", "AGY_TOOL_SETTLE_EOF_GRACE_S", 1.5, (0.0, 15.0), config_path=config_path
        ),
        eof_grace_enabled=read_bool_setting(
            "tool_settle_eof_grace_enabled", "AGY_TOOL_SETTLE_EOF_GRACE_ENABLED", True, config_path=config_path
        ),
    )


def prompt_bytes_cap(*, config_path: Path | None = None) -> int:
    """Верхний предел бюджета промпта (по умолчанию 98304 до калибровки VER-015)."""
    return read_int_setting(
        "max_prompt_bytes_cap", "AGY_BRIDGE_MAX_PROMPT_BYTES_CAP", DEFAULT_PROMPT_BYTES_CAP, (16384, 524288), config_path=config_path
    )


def max_prompt_bytes(*, config_path: Path | None = None) -> int | None:
    """Явно заданный бюджет промпта или None (если не переопределён)."""
    raw = _raw_setting("max_prompt_bytes", "AGY_BRIDGE_MAX_PROMPT_BYTES", config_path)
    value: int | None = None
    if all((_present(raw), bool(str(raw).strip()))):
        try:
            value = max(16384, int(str(raw).strip()))
        except ValueError:
            value = None
    return value


def lazy_prompt_enabled(*, config_path: Path | None = None) -> bool:
    """Включает ленивую материализацию full_prompt на горячих ходах (resume=1)."""
    return read_bool_setting("lazy_prompt_enabled", "AGY_BRIDGE_LAZY_PROMPT_ENABLED", True, config_path=config_path)


def post_turn_anchor_enabled(*, config_path: Path | None = None) -> bool:
    """Включает пост-ходовой индекс криптоякорей continuity (T1->T2 и T_k->T_{k+1})."""
    return read_bool_setting("post_turn_anchor_enabled", "AGY_BRIDGE_POST_TURN_ANCHOR_ENABLED", True, config_path=config_path)


def usage_drain_settings(*, config_path: Path | None = None) -> tuple[bool, float]:
    """Возвращает (enabled, drain_max_s) для bounded terminal_drain перед usage_snapshot."""
    enabled = read_bool_setting(
        "usage_drain_on_early_stop_enabled", "AGY_BRIDGE_USAGE_DRAIN_ON_EARLY_STOP_ENABLED", True, config_path=config_path
    )
    max_s = read_float_setting(
        "usage_drain_max_s", "AGY_BRIDGE_USAGE_DRAIN_MAX_S", 0.50, (0.0, 5.0), config_path=config_path
    )
    return enabled, max_s


def queue_keepalive_interval_s(*, config_path: Path | None = None) -> float:
    """Минимальный интервал SSE keepalive в очереди слотов (строго после t >= interval)."""
    return read_float_setting(
        "queue_keepalive_interval_s", "AGY_BRIDGE_QUEUE_KEEPALIVE_INTERVAL_S", 15.0, (1.0, 120.0), config_path=config_path
    )


def corr_max_len(*, config_path: Path | None = None) -> int:
    """Максимальная длина токенов корреляции X-Request-Id / X-Subagent-Id."""
    return read_int_setting("corr_max_len", "AGY_BRIDGE_CORR_MAX_LEN", DEFAULT_CORR_MAX_LEN, (8, 256), config_path=config_path)


def build_conv_headers(
    cid: object,
    cid_re: re.Pattern[str],
    *,
    peer_is_loopback: bool = True,
    config_path: Path | None = None,
) -> dict[str, str]:
    """Формирует X-Agy-Conversation-Id строго для loopback-пиров при включённом флаге."""
    expose = read_bool_setting("expose_conv_header", "AGY_BRIDGE_EXPOSE_CONV_HEADER", True, config_path=config_path)
    return build_validated_header(AGY_CONV_HEADER_NAME, cid, cid_re, enabled=all((peer_is_loopback, expose)))


def apply_direct_mode_policy(
    env: dict[str, str], *, config_path: Path | None = None
) -> dict[str, str]:
    """Применяет AGY_BRIDGE_DIRECT_MODE (inherit|direct|georouter), не меняя inherit."""
    raw = _raw_setting("direct_mode", "AGY_BRIDGE_DIRECT_MODE", config_path)
    mode = str(raw if _present(raw) else "inherit").strip().lower()
    target = _DIRECT_OVERRIDES.get(mode)
    if isinstance(target, str):
        env["AGY_DIRECT"] = target
    return env


def classify_cloud_mode(env: Mapping[str, str]) -> str:
    """Классифицирует сетевой режим запуска agy.real (direct vs georouter) за O(1)."""
    return {"1": "direct"}.get(str(env.get("AGY_DIRECT", "")).strip(), "georouter")


def build_lazy_prompt_pair(
    stripped_base: LazyPromptMaterializer | None,
    render_full: Callable[[], str],
    wrap_proto: Callable[[str, bool], str],
    flags: tuple[bool, bool],
) -> tuple[LazyPromptMaterializer, LazyPromptMaterializer]:
    """Создаёт ленивые материализаторы (full_mat, stripped_mat) без eager-обрезки."""
    use_stripped_for_full, full_attached = flags

    def _build_stripped() -> str:
        base = stripped_base.get() if isinstance(stripped_base, LazyPromptMaterializer) else ""
        wrapped = wrap_proto(base, False) if base else ""
        return wrapped

    def _build_full() -> str:
        raw_p = ""
        if isinstance(stripped_base, LazyPromptMaterializer):
            if use_stripped_for_full:
                raw_p = stripped_base.get()
        if not raw_p:
            raw_p = render_full()
        return wrap_proto(raw_p, full_attached)

    return LazyPromptMaterializer(_build_full), LazyPromptMaterializer(_build_stripped)


def register_post_turn_if_committed(
    out_map: Mapping[str, object],
    ctx: Mapping[str, object],
    continuity: object,
    anchor_meta: tuple[object, str, str, re.Pattern[str]],
    *,
    config_path: Path | None = None,
) -> bool:
    """Регистрирует криптоякорь строго после commit-исхода хода (D2)."""
    messages, scope, chat_id, cid_re = anchor_meta
    cid = str(next(filter(None, (out_map.get("conversation_id"),)), ""))
    raw_rc = out_map.get("rc")
    act = decide_session_commit(
        state=str(out_map.get("state", "")),
        rc=raw_rc if isinstance(raw_rc, int) else None,
        tool_turn_stop=bool(out_map.get("tool_turn_stop")),
        conversation_id=cid,
        cid_valid=bool(cid_re.fullmatch(cid)),
    )
    emitted_fn = ctx.get("emitted_call_ids")
    cids = emitted_fn() if callable(emitted_fn) else ()
    reg_fn = getattr(continuity, "register_post_turn", None)
    done = False
    if all((dict(commit=True).get(act, False), bool(cids), bool(scope), bool(chat_id), callable(reg_fn))):
        if callable(reg_fn):
            done = bool(reg_fn(messages, scope, chat_id, cids, enabled=post_turn_anchor_enabled(config_path=config_path)))
    return done
