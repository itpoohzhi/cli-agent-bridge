"""VER-009: канонический корпус грамматики, скоупов и времени для C1-N."""

from __future__ import annotations

import dataclasses
import importlib
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CORPUS_PATH = Path(__file__).parent / "fixtures/model_notes_corpus.json"
RULE_KEYS = {"model", "transport", "effort", "expires_at"}
RESULT_KEYS = {"generation", "expires_at", "rules"}
CASE_KEYS = {"id", "tags", "text", "now_dt", "expected"}
REQUIRED_TAGS = {
    "current",
    "legacy",
    "section-1",
    "section-2",
    "model",
    "effort",
    "transport",
    "global",
    "wildcard",
    "msk",
    "utc",
    "before",
    "equal",
    "after",
    "generation",
    "expiry",
    "expired-rule",
    "malformed",
}


def _aware(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.utcoffset() is not None, f"Ожидалась aware-дата: {value}"
    return parsed


def _count_tags(cases: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(tag for case in cases for tag in case["tags"]).items()))


def _load_corpus() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert set(data) == {"schema_version", "metadata", "cases"}
    assert data["schema_version"] == "1.0"
    assert isinstance(data["cases"], list)
    assert data["cases"]
    return data


CORPUS = _load_corpus()
CASES: list[dict[str, Any]] = CORPUS["cases"]


def _validate_rule(rule: dict[str, Any]) -> None:
    assert set(rule) == RULE_KEYS
    for field in ("model", "transport", "effort"):
        assert rule[field] is None or isinstance(rule[field], str)
        assert rule[field] != ""
    if rule["expires_at"] is not None:
        _aware(rule["expires_at"])


def _validate_expected(expected: dict[str, Any]) -> None:
    if "error" in expected:
        assert expected == {"error": "BlocklistParseError"}
        return
    assert set(expected) == RESULT_KEYS
    generation = expected["generation"]
    assert generation is None or (type(generation) is int and generation >= 0)
    if expected["expires_at"] is not None:
        _aware(expected["expires_at"])
    assert isinstance(expected["rules"], list)
    for rule in expected["rules"]:
        _validate_rule(rule)


def _validate_case(case: dict[str, Any]) -> None:
    assert set(case) == CASE_KEYS
    assert isinstance(case["id"], str) and case["id"]
    assert isinstance(case["text"], str)
    assert isinstance(case["tags"], list) and case["tags"]
    assert all(isinstance(tag, str) and tag for tag in case["tags"])
    assert len(case["tags"]) == len(set(case["tags"]))
    # Наивный now — намеренно отрицательный вход парсера.
    now = datetime.fromisoformat(case["now_dt"])
    if now.utcoffset() is None:
        assert case["expected"] == {"error": "BlocklistParseError"}
    _validate_expected(case["expected"])


def test_corpus_metadata_and_coverage() -> None:
    """Проверяет независимый от наличия C1-N контракт переносимой фикстуры."""
    metadata = CORPUS["metadata"]
    assert metadata["case_count"] == len(CASES)
    assert metadata["positive_count"] == sum(
        "error" not in c["expected"] for c in CASES
    )
    assert metadata["negative_count"] == sum("error" in c["expected"] for c in CASES)
    assert metadata["tag_counts"] == _count_tags(CASES)
    assert REQUIRED_TAGS <= set(metadata["tag_counts"])
    assert len({case["id"] for case in CASES}) == len(CASES)
    for case in CASES:
        _validate_case(case)


@pytest.fixture(scope="module")
def parser_module() -> ModuleType:
    """Отсутствие канонического модуля в W0 — RED, никогда skip/xfail."""
    module = importlib.import_module("core.model_notes_parse")
    expected = Path(__file__).resolve().parents[1] / "core/model_notes_parse.py"
    assert module.__file__ is not None
    assert Path(module.__file__).resolve() == expected
    return module


def _record(value: Any) -> Mapping[str, Any]:
    """Проекция DTO либо mapping без повторной реализации грамматики."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    assert isinstance(value, Mapping), f"Ожидался DTO/mapping, получен {type(value)}"
    return value


def _utc(value: Any) -> str | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else _aware(value)
    assert parsed.utcoffset() is not None
    return parsed.astimezone(timezone.utc).isoformat()


def _rule_projection(value: Any) -> dict[str, Any]:
    rule = _record(value)
    return {
        "model": rule["model"],
        "transport": rule["transport"],
        "effort": rule["effort"],
        "expires_at": _utc(rule["expires_at"]),
    }


def _projection(value: Any) -> dict[str, Any]:
    result = _record(value)
    generation = result["generation"]
    assert generation is None or type(generation) is int
    return {
        "generation": generation,
        "expires_at": _utc(result["expires_at"]),
        "rules": sorted(
            (_rule_projection(rule) for rule in result["rules"]),
            key=lambda rule: json.dumps(rule, sort_keys=True),
        ),
    }


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_canonical_parser_corpus(
    case: dict[str, Any], parser_module: ModuleType
) -> None:
    """Сверяет весь результат; просроченная строка не равна ошибке документа."""
    now = datetime.fromisoformat(case["now_dt"])
    expected = case["expected"]
    if "error" in expected:
        error_type = parser_module.BlocklistParseError
        assert issubclass(error_type, Exception)
        with pytest.raises(error_type, match=r"\S"):
            parser_module.parse_model_notes(case["text"], now_dt=now)
        return
    actual = parser_module.parse_model_notes(case["text"], now_dt=now)
    assert _projection(actual) == _projection(expected)


def test_corpus_and_function_size_budgets() -> None:
    """C0-7: не более 300 строк и 40/5/10 для каждой функции."""
    from tests.test_transport_modularity import functions, metrics

    source = Path(__file__).read_bytes()
    assert len(source.splitlines()) <= 300
    violations = {
        name: metrics(node)
        for name, node in functions(source).items()
        if any(
            value > cap for value, cap in zip(metrics(node), (40, 5, 10), strict=True)
        )
    }
    assert not violations, violations
