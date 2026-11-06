"""Совместимость `dataclass(slots=True)` со штатным Python 3.9 (саб-мосты под `/usr/bin/python3`).

`slots` появился в 3.10: на 3.9.6 декоратор падает `TypeError` ещё на импорте модуля.
Универсальный слой отдаёт готовый набор kwargs, чтобы модули ядра не ветвились по версии.
"""

from __future__ import annotations

import sys
from typing import Any

DC_SLOTS: dict[str, Any] = {"slots": True} if sys.version_info >= (3, 10) else {}
"""Kwargs декоратора `dataclass`: слоты только там, где рантайм их понимает."""
