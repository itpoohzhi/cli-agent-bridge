"""Read-only адаптер быстрого выхода из дрена к чистому домену (AD-001/AD-002, W3-A).

Связывает живой объект ``tail`` и Zero-I/O домен ``drain_fast_path_domain``:
факты собираются только через ``getattr`` с fail-closed дефолтами — любое
отсутствующее/неизвестное состояние запрещает ``fast_clean``. Флаг включения
читается через ``read_bool_setting`` (os.environ > dynamic_config.json > False).
Адаптер НЕ мутирует ``tail`` и не выполняет I/O кроме чтения настройки флага.

Реальные имена полей сверены с ``server.py``: у ``_TranscriptTail`` публичные
``failed``/``stop_event``, ``_pending_steps`` — метод, а ``proc`` и
``_persistent_mode``/``_persistent_turn_ok`` живут на ``Run`` (``tail.run_ref``);
поэтому каждый факт читается с tail и с его run_ref (при наличии). Полей
``_has_tool_trace``/``_progressive_chunks_emitted`` в реальных объектах НЕТ:
tool trace определяется по ``_tool_step_indices``, progressive-выдача — по
``emitted``; отсутствие обоих источников факта fail-closed запрещает выход.
"""

# pyright: reportAny=false, reportExplicitAny=false

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Final

from .drain_fast_path_domain import DrainFacts, decide_fast_exit
from .long_session_config import read_bool_setting

__all__ = [
    "DRAIN_FAST_PATH_ENV",
    "DRAIN_FAST_PATH_FLAG",
    "collect_drain_facts",
    "is_drain_fast_path_enabled",
    "should_drain_fast_exit",
]

DRAIN_FAST_PATH_FLAG: Final[str] = "BRIDGE_AGY_DRAIN_FAST_PATH_ENABLED"
DRAIN_FAST_PATH_ENV: Final[str] = "AGY_BRIDGE_DRAIN_FAST_PATH_ENABLED"

_MISSING: Final[object] = object()
_LOGGER: Final[logging.Logger] = logging.getLogger(__name__)


def is_drain_fast_path_enabled(config_path: Path | str | None = None) -> bool:
    """Флаг os.environ > dynamic_config.json > False; fail-closed при любой ошибке."""
    try:
        path = Path(config_path) if config_path is not None else None
        return read_bool_setting(
            DRAIN_FAST_PATH_FLAG, DRAIN_FAST_PATH_ENV, False, config_path=path
        )
    except Exception as exc:
        _LOGGER.debug("drain_fast_path config read failed: %s", exc)
        return False


def _sources(tail: Any) -> tuple[Any, ...]:
    """tail и его run_ref: реальные поля распределены между обоими объектами."""
    return (tail, getattr(tail, "run_ref", None))


def _first_attr(sources: tuple[Any, ...], names: tuple[str, ...]) -> Any:
    """Первое найденное значение атрибута среди источников; иначе ``_MISSING``."""
    for src in sources:
        if src is None:
            continue
        for name in names:
            value = getattr(src, name, _MISSING)
            if value is not _MISSING:
                return value
    return _MISSING


def _bool_of(raw: Any, default: bool) -> bool:
    return default if raw is _MISSING else bool(raw)


def _count_of(raw: Any) -> int:
    """Длина коллекции; отсутствующее -> 0, нечитаемая длина -> 1 (fail-closed)."""
    if raw is _MISSING:
        return 0
    try:
        return len(raw)
    except TypeError:
        return 1


def _clean_rc(sources: tuple[Any, ...]) -> bool:
    if _bool_of(_first_attr(sources, ("_persistent_mode",)), False):
        return _bool_of(_first_attr(sources, ("_persistent_turn_ok",)), False)
    proc = _first_attr(sources, ("_proc", "proc"))
    if proc is _MISSING or proc is None:
        return False
    return getattr(proc, "returncode", None) == 0


def _pending_steps(sources: tuple[Any, ...]) -> int:
    raw = _first_attr(sources, ("_pending_steps",))
    if raw is _MISSING:
        return 1
    if callable(raw):
        raw = raw()
    return raw if isinstance(raw, int) else 1


def _buffered_events(sources: tuple[Any, ...]) -> int:
    buf = _first_attr(sources, ("_buf",))
    indices = _first_attr(sources, ("_tool_step_indices",))
    if buf is _MISSING or indices is _MISSING:
        return 1
    return _count_of(buf) + _count_of(indices)


def _has_tool_trace(sources: tuple[Any, ...]) -> bool:
    """Явный ``_has_tool_trace`` или реальные ``_tool_step_indices``; нет обоих -> True."""
    trace = _first_attr(sources, ("_has_tool_trace",))
    indices = _first_attr(sources, ("_tool_step_indices",))
    if trace is not _MISSING:
        return bool(trace) or _count_of(indices) > 0
    if indices is not _MISSING:
        return _count_of(indices) > 0
    return True


def _has_progressive_chunks(sources: tuple[Any, ...]) -> bool:
    """Явный ``_progressive_chunks_emitted`` или реальный ``emitted``; нет обоих -> True."""
    explicit = _first_attr(sources, ("_progressive_chunks_emitted",))
    if explicit is not _MISSING:
        return bool(explicit)
    emitted = _first_attr(sources, ("emitted",))
    if isinstance(emitted, int) and not isinstance(emitted, bool):
        return emitted > 0
    return True


def _stopped(sources: tuple[Any, ...]) -> bool:
    event = _first_attr(sources, ("_stop_event", "stop_event"))
    if event is _MISSING or event is None:
        return True
    is_set = getattr(event, "is_set", None)
    if not callable(is_set):
        return True
    return bool(is_set())


def _collect(
    tail: Any, *, flag_enabled: bool, authoritative_read_done: bool
) -> DrainFacts:
    sources = _sources(tail)
    return DrainFacts(
        flag_enabled=flag_enabled,
        authoritative_read_done=authoritative_read_done,
        clean_rc=_clean_rc(sources),
        pending_steps=_pending_steps(sources),
        buffered_events=_buffered_events(sources),
        has_tool_trace=_has_tool_trace(sources),
        has_progressive_chunks=_has_progressive_chunks(sources),
        failed=_bool_of(_first_attr(sources, ("_failed", "failed")), True),
        interrupted=_bool_of(_first_attr(sources, ("_interrupted",)), True),
        stopped=_stopped(sources),
    )


def collect_drain_facts(
    tail: Any, *, flag_enabled: bool, authoritative_read_done: bool
) -> DrainFacts:
    """Read-only снимок фактов ``tail``; любая ошибка чтения -> fail-closed."""
    try:
        return _collect(
            tail,
            flag_enabled=flag_enabled,
            authoritative_read_done=authoritative_read_done,
        )
    except Exception as exc:
        _LOGGER.debug("drain_fast_path fact collection failed: %s", exc)
        return DrainFacts(
            flag_enabled=flag_enabled,
            authoritative_read_done=authoritative_read_done,
        )


def should_drain_fast_exit(
    tail: Any,
    config_path: Path | str | None = None,
    *,
    authoritative_read_done: bool = False,
) -> bool:
    """Фасад AD-002: при выключенном флаге tail не читается (нулевой оверхед).

    ``authoritative_read_done`` fail-closed по умолчанию ``False``: вызывающий
    обязан явно подтвердить, что авторитетное чтение источников завершено.
    """
    if not is_drain_fast_path_enabled(config_path):
        return False
    facts = collect_drain_facts(
        tail, flag_enabled=True, authoritative_read_done=authoritative_read_done
    )
    return decide_fast_exit(facts).should_fast_exit
