"""Хелперы телеметрии: «значение по умолчанию» и безопасные приведения без ветвлений.

Замена цепочек `a or b` и `x if cond else y` вызовами делает горячий путь
телеметрии линейным: каждое ветвление в этих модулях обязано быть покрыто
мутационным тестом (T-ISO-I1), поэтому ветви собираются здесь, в одном месте.
"""

from __future__ import annotations

from typing import Any


def first(*values: Any, default: Any = None) -> Any:
    """Первое «непустое» значение среди аргументов; если все пусты — `default` (по умолчанию None).

    В отличие от `a or b`, пустой последний аргумент не возвращается: фоллбэк `{}`/`0.0` передают как `default=`.
    """
    return next(filter(None, values), default)


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
    return str(first(value, default=default))


def header_value(headers: Any, name: str) -> Any:
    """Значение заголовка из email.message/словаря; None — источника или заголовка нет."""
    getter = getattr(headers, "get", lambda _name: None)
    return getter(name)


def close_quietly(resource: Any) -> None:
    """Закрыть ресурс, если он есть; повторный вызов и None безопасны."""
    close = getattr(resource, "close", None)
    if callable(close):
        close()
