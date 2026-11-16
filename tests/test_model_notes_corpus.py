"""VER-009: канонический корпус грамматики, скоупов и времени для C1-N."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import json
import os
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
    assert metadata["positive_count"] == sum("error" not in c["expected"] for c in CASES)
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
def test_canonical_parser_corpus(case: dict[str, Any], parser_module: ModuleType) -> None:
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
        if any(value > cap for value, cap in zip(metrics(node), (40, 5, 10), strict=True))
    }
    assert not violations, violations


def test_parser_portability_and_budgets(parser_module: ModuleType) -> None:
    """Проверяет переносимость и каждый лимит исходного модуля."""
    from tests.test_transport_modularity import exceeds, functions, metrics

    source = Path(str(parser_module.__file__)).read_bytes()
    assert len(source.splitlines()) <= 200
    assert not {n: metrics(f) for n, f in functions(source).items() if exceeds(metrics(f))}
    roots = {
        name.name.split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import)
        for name in node.names
    }
    roots |= {
        (node.module or "").split(".")[0]
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
    }
    assert roots <= sys.stdlib_module_names


@pytest.mark.parametrize("payload", [b"", b"a", "я".encode(), b"x" * 1048576])
def test_bounded_reader_edges(payload: bytes, tmp_path: Path, parser_module: ModuleType) -> None:
    """Лимит считается в байтах, включая точную границу и UTF-8."""
    path = tmp_path / "notes.md"
    path.write_bytes(payload)
    size = max(1, len(payload))
    assert parser_module.read_model_notes_file(path, max_bytes=size) == payload.decode()
    assert parser_module.read_model_notes_file(path) == payload.decode()
    path.write_bytes(payload + b"xx")
    with pytest.raises(parser_module.BlocklistParseError):
        parser_module.read_model_notes_file(path, max_bytes=size)
    path.write_bytes(b"\xff")
    with pytest.raises(parser_module.BlocklistParseError):
        parser_module.read_model_notes_file(path, max_bytes=size)


def test_reader_rejects_nonfiles_and_bad_limits(tmp_path: Path, parser_module: ModuleType) -> None:
    """FIFO без писателя не блокирует, отсутствующий источник не скрывается."""
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    for path in (tmp_path, fifo, tmp_path / "missing"):
        with pytest.raises(parser_module.BlocklistParseError):
            parser_module.read_model_notes_file(path)
    for limit in (0, -1, True, 1.5):
        with pytest.raises(parser_module.BlocklistParseError):
            parser_module.read_model_notes_file(fifo, max_bytes=limit)


@pytest.mark.parametrize(
    "replacement",
    [
        "| model-a / codex / droid | TEMP OFF | quota |",
        "| model-a, | TEMP OFF | quota |",
        "| | ACTIVE | quota |",
        "| model-a | `TEMP OFF | quota |",
        "| model-a | ACTIVE / BANNED | quota |",
        "| model-a | TEMP OFF до 18:00 MSK до 19:00 MSK | quota |",
    ],
)
def test_ambiguous_rows_fail_closed(replacement: str, parser_module: ModuleType) -> None:
    """Неоднозначность не превращается в молчаливое расширение или снятие бана."""
    case = next(c for c in CASES if c["id"] == "legacy-temp-off-bare")
    text = case["text"].replace("| model-a | TEMP-OFF | quota |", replacement)
    with pytest.raises(parser_module.BlocklistParseError):
        parser_module.parse_model_notes(text, now_dt=_aware(case["now_dt"]))


@pytest.mark.parametrize("payload", [b"a", b"xxx", b"\xff"])
def test_reader_growth_check_and_descriptor_cleanup(
    payload: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, parser_module: ModuleType
) -> None:
    """Повторная проверка ловит рост после fstat; fd закрывается на всех выходах."""
    path = tmp_path / "growing.md"
    path.write_bytes(payload)
    opened: list[int] = []
    real_open, real_fstat = os.open, os.fstat

    def track_open(source: str | os.PathLike[str], flags: int) -> int:
        fd = real_open(source, flags)
        opened.append(fd)
        return fd

    def stale_size(fd: int) -> os.stat_result:
        fields = list(real_fstat(fd))
        fields[6] = 0
        return os.stat_result(fields)

    with monkeypatch.context() as scoped:
        scoped.setattr(os, "open", track_open)
        scoped.setattr(os, "fstat", stale_size)
        if payload == b"a":
            assert parser_module.read_model_notes_file(path, max_bytes=2) == "a"
        else:
            with pytest.raises(parser_module.BlocklistParseError):
                parser_module.read_model_notes_file(path, max_bytes=2)
    assert len(opened) == 1
    with pytest.raises(OSError):
        real_fstat(opened[0])
