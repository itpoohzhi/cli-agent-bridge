# -*- coding: utf-8 -*-
"""Чистый домен проверки доставки канона DSH (AD-002, systemPrompt-only).

После миграции AD-002 канон доставляется симлинком-якорём `~/.dsh/canon/AGENTS.md`,
а старый user-global `~/.dsh/AGENTS.md` намеренно удалён. Модуль классифицирует
состояние доставки и возвращает готовые строки диагностики:

- `CANON_LOST ...` - канон пропал или подменён (fail-closed);
- `DUPLICATE_RETURNED ...` - user-global дубль вернулся после миграции.

Печать и структуры `b_guard` модулю неизвестны: только чистые проверки ФС.
"""

import os
import stat
from typing import Optional

# Отображаемые пути (без раскрытия `~`) для сообщений диагностики.
ANCHOR_DISPLAY = "~/.dsh/canon/AGENTS.md"
UG_DISPLAY = "~/.dsh/AGENTS.md"

__all__ = [
    "read_canon_bytes",
    "check_anchor_problem",
    "check_user_global_problem",
    "diagnose_delivery_error",
]


def read_canon_bytes(canon_path: str) -> Optional[bytes]:
    """Байты канона; None - файл отсутствует или нечитаем (fail-closed)."""
    try:
        with open(canon_path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def check_anchor_problem(
    anchor_path: str, canon_real: str, anchor_display: str
) -> Optional[str]:
    """Диагноз симлинка-якоря `~/.dsh/canon/AGENTS.md` (None - валидный симлинк на канон).

    Якорь - единственный легальный путь доставки канона после AD-002: отсутствует,
    не симлинк, висячий или перенацелённый - всё это потеря канона (CANON_LOST).
    """
    if not os.path.lexists(anchor_path):
        return "CANON_LOST anchor %s: симлинк-якорь отсутствует" % anchor_display
    if not os.path.islink(anchor_path):
        return (
            "CANON_LOST anchor %s: ожидается симлинк, а не обычный файл/каталог"
            % anchor_display
        )
    if not os.path.exists(anchor_path):
        return "CANON_LOST anchor %s: висячий симлинк" % anchor_display
    if os.path.realpath(anchor_path) != canon_real:
        return "CANON_LOST anchor %s: симлинк указывает не на канон" % anchor_display
    return None


def check_user_global_problem(
    ug_path: str, canon_real: str, canon_bytes: bytes, ug_display: str
) -> Optional[str]:
    """Диагноз user-global `~/.dsh/AGENTS.md` (None - отсутствует; при валидном якоре это норма).

    Присутствующий user-global - всегда проблема: симлинк на канон или байтовая копия
    означают возврат дубля (DUPLICATE_RETURNED), любое иное состояние - потерю канона.
    """
    if not os.path.lexists(ug_path):
        return None
    if os.path.islink(ug_path):
        return _linked_ug_problem(ug_path, canon_real, ug_display)
    return _plain_ug_problem(ug_path, canon_bytes, ug_display)


def diagnose_delivery_error(
    canon_bytes: bytes, canon_real: str, anchor_path: str, ug_path: str
) -> Optional[str]:
    """Полный диагноз доставки канона (None - доставка в порядке).

    Порядок строгий: сначала якорь `anchor_path` (потеря канона важнее дубля),
    затем user-global `ug_path`; отображаемые пути - константы модуля.
    """
    problem = check_anchor_problem(anchor_path, canon_real, ANCHOR_DISPLAY)
    if problem is not None:
        return problem
    return check_user_global_problem(ug_path, canon_real, canon_bytes, UG_DISPLAY)


def _duplicate_message(ug_display: str) -> str:
    """Сообщение о возвратившемся дубле user-global после миграции на якорь."""
    return "DUPLICATE_RETURNED user-global %s: удалите дубль после миграции на %s" % (
        ug_display,
        ANCHOR_DISPLAY,
    )


def _linked_ug_problem(ug_path: str, canon_real: str, ug_display: str) -> str:
    """Диагноз user-global, являющегося симлинком (висячий / перенацелённый / на канон)."""
    if not os.path.exists(ug_path):
        return "CANON_LOST user-global %s: висячий симлинк" % ug_display
    if os.path.realpath(ug_path) != canon_real:
        return "CANON_LOST user-global %s: симлинк указывает не на канон" % ug_display
    return _duplicate_message(ug_display)


def _read_regular_file(path: str) -> Optional[bytes]:
    """Байты обычного файла; None - спецфайл/каталог или ошибка чтения (fail-closed)."""
    try:
        if not stat.S_ISREG(os.lstat(path).st_mode):
            return None
        with open(path, "rb") as handle:
            return handle.read()
    except OSError:
        return None


def _plain_ug_problem(ug_path: str, canon_bytes: bytes, ug_display: str) -> str:
    """Диагноз user-global, не являющегося симлинком (обычный файл или спецфайл)."""
    data = _read_regular_file(ug_path)
    if data is None:
        return "CANON_LOST user-global %s: файл нечитаем или спецфайл" % ug_display
    if data == canon_bytes:
        return _duplicate_message(ug_display)
    return "CANON_LOST user-global %s: содержимое отличается от канона" % ug_display
