"""W1-G: честные маркеры усечения и уведомление (VER-010, AD-008, CD-005).

SSoT текстов усечения — core/prompt_truncation_notice.py: маркеры и
уведомление называют настроенный лимит промпта моста (configured prompt
cap / input_guard) и явно отрицают окно контекста модели; токен
[truncation-notice] сохранён для совместимости. Детерминированные
unit-тесты: 0 сокетов, 0 sleep, 0 обращений к окружению.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.prompt_truncation_notice import (  # noqa: E402
    DEFAULT_TRUNCATION_NOTICE_TEMPLATE,
    HISTORY_PRUNED_MARKER,
    MIDDLE_PRUNED_MARKER,
    TRUNCATION_NOTICE_MARKER,
    NoticePolicy,
    with_truncation_notice,
)

_CAP_TOKEN: Final = "configured prompt cap"
_GUARD_TOKEN: Final = "input_guard"
_DENIAL_EN: Final = "not the model context window"
_DENIAL_RU: Final = "а не окна контекста модели"
_BRIDGE_TOKEN: Final = "agy-bridge"
_DISHONEST_RU: Final = "лимита контекста"
_NOTICE_BYTE_BUDGET: Final = 300

# Канонический список запрещённых I/O-корней чистого домена (M-MOD-I3).
_FORBIDDEN_IMPORT_ROOTS: Final = frozenset(
    {
        "os",
        "subprocess",
        "threading",
        "socket",
        "httpx",
        "openai",
        "requests",
        "aiohttp",
        "urllib3",
        "fastapi",
        "litestar",
        "starlette",
        "sqlalchemy",
        "redis",
        "time",
    }
)

_OLD_HISTORY_LITERAL: Final = (
    "[ранняя история диалога опущена мостом для соблюдения лимита контекста]"
)
_OLD_MIDDLE_LITERAL: Final = (
    "\n[... часть содержимого сообщения опущена мостом для соблюдения лимита"
    " контекста agy ...]\n"
)


def _bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _assert_honest(text: str) -> None:
    assert _CAP_TOKEN in text
    assert _GUARD_TOKEN in text
    assert _BRIDGE_TOKEN in text
    assert _DENIAL_EN in text
    assert _DISHONEST_RU not in text
    assert "лимит контекста" not in text


def _assert_honest_marker(text: str) -> None:
    _assert_honest(text)
    assert _DENIAL_RU in text


def test_history_marker_names_cap_and_denies_context_window() -> None:
    assert isinstance(HISTORY_PRUNED_MARKER, str)
    assert HISTORY_PRUNED_MARKER
    _assert_honest_marker(HISTORY_PRUNED_MARKER)
    assert HISTORY_PRUNED_MARKER.startswith("[")
    assert HISTORY_PRUNED_MARKER.endswith("]")


def test_middle_marker_names_cap_and_denies_context_window() -> None:
    assert isinstance(MIDDLE_PRUNED_MARKER, str)
    _assert_honest_marker(MIDDLE_PRUNED_MARKER)
    # Форма маркера середины сохранена: ведущий/замыкающий перевод строки
    # и рамка "[... ...]" для вставки внутрь текста сообщения.
    assert MIDDLE_PRUNED_MARKER.startswith("\n[...")
    assert MIDDLE_PRUNED_MARKER.endswith("...]\n")
    # Компактность: тесный бюджет (256 B) должен вмещать маркер целиком.
    assert len(MIDDLE_PRUNED_MARKER.encode("utf-8")) <= 150


def test_markers_replaced_dishonest_context_limit_wording() -> None:
    assert HISTORY_PRUNED_MARKER != _OLD_HISTORY_LITERAL
    assert MIDDLE_PRUNED_MARKER != _OLD_MIDDLE_LITERAL
    for marker in (HISTORY_PRUNED_MARKER, MIDDLE_PRUNED_MARKER):
        assert "для соблюдения лимита контекста" not in marker


def test_markers_are_numberless_constants() -> None:
    # AD-008: константы без чисел и плейсхолдеров — стабильный хеш префикса
    # промпта и защита от интерполяции пользовательского текста.
    for marker in (HISTORY_PRUNED_MARKER, MIDDLE_PRUNED_MARKER):
        assert re.search(r"\d", marker) is None
        assert "{" not in marker
        assert "}" not in marker
    assert HISTORY_PRUNED_MARKER != MIDDLE_PRUNED_MARKER


def test_default_template_is_honest_and_keeps_compat_tokens() -> None:
    template = DEFAULT_TRUNCATION_NOTICE_TEMPLATE
    assert TRUNCATION_NOTICE_MARKER == "[truncation-notice]"
    assert TRUNCATION_NOTICE_MARKER in template
    _assert_honest(template)
    # Совместимость с прежним контрактом рендера (счётчики и суффикс).
    assert "{count} active tool result(s)" in template
    assert "{limit}-byte" in template
    assert template.endswith("instead.")


def test_rendered_default_notice_is_honest() -> None:
    rendered = DEFAULT_TRUNCATION_NOTICE_TEMPLATE.format(count=3, limit=98_304)
    _assert_honest(rendered)
    assert TRUNCATION_NOTICE_MARKER in rendered
    assert "3 active tool result(s)" in rendered
    assert "98304-byte" in rendered
    assert "{count}" not in rendered
    assert "{limit}" not in rendered
    assert rendered.endswith("instead.")


def test_notice_byte_budget_with_large_numbers() -> None:
    assert _bytes(DEFAULT_TRUNCATION_NOTICE_TEMPLATE) <= _NOTICE_BYTE_BUDGET
    rendered = DEFAULT_TRUNCATION_NOTICE_TEMPLATE.format(count=99, limit=1_000_000)
    assert _bytes(rendered) <= _NOTICE_BYTE_BUDGET


def test_with_truncation_notice_appends_honest_notice() -> None:
    blocks = [(0, "tool", "T" * 800)]

    def reprune(budget: int) -> str:
        return "T" * max(budget, 0)

    limit = 1000
    result = with_truncation_notice(
        "T", blocks, reprune, NoticePolicy(size_fn=_bytes), limit
    )
    assert result.count(TRUNCATION_NOTICE_MARKER) == 1
    assert _bytes(result) <= limit
    _assert_honest(result)
    assert "1 active tool result(s)" in result
    assert f"{limit}-byte" in result


def test_broken_custom_template_falls_back_to_honest_default() -> None:
    blocks = [(0, "tool", "T" * 100)]

    def reprune(budget: int) -> str:
        return "T" * max(budget, 0)

    for broken in ("{unknown}", "{", "{count[0]}"):
        result = with_truncation_notice(
            "T", blocks, reprune, NoticePolicy(size_fn=_bytes, template=broken), 1000
        )
        assert result.count(TRUNCATION_NOTICE_MARKER) == 1
        _assert_honest(result)


def test_module_is_pure_domain() -> None:
    source = (ROOT / "core" / "prompt_truncation_notice.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = [alias.name.split(".")[0] for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        else:
            continue
        for root in roots:
            assert root not in _FORBIDDEN_IMPORT_ROOTS, root
    # Никакого чтения окружения и часов: домен получает всё параметрами.
    assert "environ" not in source
    assert "time.time" not in source
