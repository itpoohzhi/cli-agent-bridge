"""Хелперы телеметрии: «значение по умолчанию» и безопасные приведения без ветвлений.

Замена цепочек `a or b` и `x if cond else y` вызовами делает горячий путь
телеметрии линейным: каждое ветвление в этих модулях обязано быть покрыто
мутационным тестом (T-ISO-I1), поэтому ветви собираются здесь, в одном месте.
"""

from __future__ import annotations

import functools
import itertools
import operator
from collections.abc import Callable, Mapping
from typing import Any

_IS_NONE = functools.partial(operator.is_, None)


def first(*values: Any, default: Any = None) -> Any:
    """Первое значение, не равное None; 0, 0.0, False и "" сохраняются. Если все None — `default`."""
    return next(itertools.filterfalse(_IS_NONE, values), default)


def present(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Копия словаря без значений None (0, 0.0, False и "" сохраняются)."""
    return {key: value for key, value in mapping.items() if not _IS_NONE(value)}


def first_truthy(*values: Any, default: Any = None) -> Any:
    """Первое «непустое» значение среди аргументов; если все пусты — `default` (по умолчанию None).

    В отличие от `a or b`, пустой последний аргумент не возвращается: фоллбэк `{}`/`0.0` передают как `default=`.
    """
    return next(filter(None, values), default)


def value_or_else(value: Any, supplier: Callable[[], Any]) -> Any:
    """`value`, если он не None, иначе результат `supplier()`; supplier вызывается только при необходимости."""
    resolved = value
    if _IS_NONE(resolved):
        resolved = supplier()
    return resolved


def as_int(value: Any, default: int = 0) -> int:
    """int(value); None и мусор дают `default` вместо исключения."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    """float(value); None и мусор дают `default` вместо исключения."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_str(value: Any, default: str = "") -> str:
    """str() для непустого значения, иначе `default` (None/0/"" дают default)."""
    return str(first_truthy(value, default=default))


def header_value(headers: Any, name: str) -> Any:
    """Значение заголовка из email.message/словаря; None — источника или заголовка нет."""
    getter = getattr(headers, "get", lambda _name: None)
    return getter(name)


def close_quietly(resource: Any) -> None:
    """Закрыть ресурс, если он есть; повторный вызов и None безопасны."""
    close = getattr(resource, "close", None)
    if callable(close):
        close()
