"""W0-B, AD-004/CD-001/CD-002: контракт конфигурации и отбора кандидатов.

load_chains(chains_dir=..., env=...) возвращает каталог с chains и quota_rules.
catalog.select_candidates(alias, request, breaker) возвращает кандидатов
в исходном порядке, после фильтров и ограничения числа попыток.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FakeBreaker:
    """Изолированный порт квот: без диска, сетевых запросов и реального cooldown."""

    def __init__(self, blocked: tuple[str, ...] = ()) -> None:
        self.blocked = frozenset(blocked)

    def is_blocked(self, model_id: str) -> bool:
        return model_id in self.blocked


def _candidate(
    model: str, context_window: int = 1000, cost_class: str = "subscription"
) -> dict[str, Any]:
    return {"model": model, "cost_class": cost_class, "context_window": context_window}


def _document(candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if candidates is None:
        candidates = [_candidate("model-a"), _candidate("model-b")]
    return {
        "quota_rules": {
            "body_patterns": [r"plan\s+empty"],
            "error_codes": ["GoUsageLimitError"],
            "reset_body_patterns": [r"resets in (?P<duration>.+)"],
        },
        "chains": {
            "summary-alias": {
                "declared_context_window": 1000000,
                "disabled_target": candidates[-1]["model"] if candidates else "model-b",
                "preserve_alias_in_response": False,
                "exhausted_status_code": 503,
                "candidates": candidates,
            }
        },
    }


def _write_yaml(directory: Path, document: dict[str, Any], name: str = "chain.yaml") -> None:
    import yaml

    (directory / name).write_text(yaml.safe_dump(document), encoding="utf-8")


def _request(text: str = "hello", max_tokens: int = 50) -> dict[str, Any]:
    return {"messages": [{"role": "user", "content": text}], "max_tokens": max_tokens}


def test_load_yaml_chain_metadata_and_quota_rules(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    document = _document()
    _write_yaml(tmp_path, document)
    catalog = load_chains(chains_dir=tmp_path, env={})
    chain = catalog.chains["summary-alias"]
    assert chain.declared_context_window == 1000000
    assert chain.disabled_target == "model-b"
    assert chain.preserve_alias_in_response is False
    assert chain.exhausted_status_code == 503
    assert [
        (candidate.model, candidate.cost_class, candidate.context_window)
        for candidate in chain.candidates
    ] == [("model-a", "subscription", 1000), ("model-b", "subscription", 1000)]
    for key, value in document["quota_rules"].items():
        assert list(catalog.quota_rules[key]) == value


def test_load_chains_dir_from_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document())
    monkeypatch.setenv("BRIDGE_FALLBACK_CHAINS_PATH", str(tmp_path))
    catalog = load_chains()
    assert "summary-alias" in catalog.chains
    assert catalog.chains["summary-alias"].disabled_target == "model-b"


def test_load_multiple_yaml_files(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document(), "first.yaml")
    second = _document()
    second.pop("quota_rules")
    second["chains"]["second-alias"] = second["chains"].pop("summary-alias")
    _write_yaml(tmp_path, second, "second.yaml")
    catalog = load_chains(chains_dir=tmp_path, env={})
    assert set(catalog.chains) == {"summary-alias", "second-alias"}
    assert list(catalog.quota_rules["error_codes"]) == ["GoUsageLimitError"]


def test_optional_chain_fields_have_safe_defaults(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    document = _document()
    for key in ("disabled_target", "preserve_alias_in_response", "exhausted_status_code"):
        document["chains"]["summary-alias"].pop(key)
    _write_yaml(tmp_path, document)
    chain = load_chains(chains_dir=tmp_path, env={}).chains["summary-alias"]
    assert chain.disabled_target == "model-a"
    assert chain.preserve_alias_in_response is True
    assert chain.exhausted_status_code == 429


@pytest.mark.parametrize("count", [0, 1])
def test_reject_chain_with_fewer_than_two_candidates(tmp_path: Path, count: int) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document([_candidate("model-a")] * count))
    with pytest.raises(ValueError, match=r"(?i)candidate|chain"):
        load_chains(chains_dir=tmp_path, env={})


@pytest.mark.parametrize(
    ("allow_paid", "expected"),
    [(False, ["model-a", "model-b"]), (True, ["paid-model", "model-a", "model-b"])],
)
def test_paid_candidates_require_explicit_opt_in(
    tmp_path: Path, allow_paid: bool, expected: list[str]
) -> None:
    from core.model_fallback_chain import load_chains

    candidates = [
        _candidate("paid-model", cost_class="paid"),
        _candidate("model-a"),
        _candidate("model-b"),
    ]
    _write_yaml(tmp_path, _document(candidates))
    env = {"BRIDGE_FALLBACK_ALLOW_PAID": "true"} if allow_paid else {}
    catalog = load_chains(chains_dir=tmp_path, env=env)
    selected = catalog.select_candidates("summary-alias", _request(), FakeBreaker())
    assert [candidate.model for candidate in selected] == expected


@pytest.mark.parametrize(
    ("chars_per_token", "text_size", "max_tokens", "expected"),
    [
        ("2", 600, 50, ["exact", "large"]),
        ("2", 600, 51, ["large"]),
        ("2", 601, 50, ["large"]),
        ("4", 600, 50, ["small", "exact", "large"]),
    ],
)
def test_context_filter_includes_output_and_uses_configurable_estimate(
    tmp_path: Path, chars_per_token: str, text_size: int, max_tokens: int, expected: list[str]
) -> None:
    from core.model_fallback_chain import load_chains

    candidates = [_candidate("small", 349), _candidate("exact", 350), _candidate("large", 351)]
    _write_yaml(tmp_path, _document(candidates))
    catalog = load_chains(
        chains_dir=tmp_path, env={"BRIDGE_FALLBACK_CHARS_PER_TOKEN": chars_per_token}
    )
    selected = catalog.select_candidates(
        "summary-alias", _request("x" * text_size, max_tokens), FakeBreaker()
    )
    assert [candidate.model for candidate in selected] == expected


def test_context_estimate_counts_all_messages_with_default_ratio(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    candidates = [_candidate("small", 249), _candidate("exact", 250)]
    _write_yaml(tmp_path, _document(candidates))
    catalog = load_chains(chains_dir=tmp_path, env={})
    request = _request("x" * 300)
    request["messages"].insert(0, {"role": "system", "content": "y" * 300})
    selected = catalog.select_candidates("summary-alias", request, FakeBreaker())
    assert [candidate.model for candidate in selected] == ["exact"]


@pytest.mark.parametrize(
    ("blocked", "expected"),
    [
        (("model-a",), ["model-b"]),
        (("model-b",), ["model-a"]),
        (("model-a", "model-b"), []),
        (("unrelated",), ["model-a", "model-b"]),
    ],
)
def test_breaker_filters_only_blocked_candidate_models(
    tmp_path: Path, blocked: tuple[str, ...], expected: list[str]
) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document())
    catalog = load_chains(chains_dir=tmp_path, env={})
    selected = catalog.select_candidates("summary-alias", _request(), FakeBreaker(blocked))
    assert [candidate.model for candidate in selected] == expected


@pytest.mark.parametrize("max_hops", [1, 2, 3, 4])
def test_max_hops_caps_candidates_in_declared_order(tmp_path: Path, max_hops: int) -> None:
    from core.model_fallback_chain import load_chains

    models = ["model-a", "model-b", "model-c", "model-d"]
    _write_yaml(tmp_path, _document([_candidate(model) for model in models]))
    catalog = load_chains(chains_dir=tmp_path, env={"BRIDGE_FALLBACK_MAX_HOPS": str(max_hops)})
    selected = catalog.select_candidates("summary-alias", _request(), FakeBreaker())
    assert [candidate.model for candidate in selected] == models[:max_hops]


def test_filters_run_before_max_hops_cap(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    candidates = [
        _candidate("paid-model", cost_class="paid"),
        _candidate("small", 1),
        _candidate("blocked"),
        _candidate("model-a"),
        _candidate("model-b"),
        _candidate("model-c"),
    ]
    _write_yaml(tmp_path, _document(candidates))
    catalog = load_chains(chains_dir=tmp_path, env={"BRIDGE_FALLBACK_MAX_HOPS": "2"})
    selected = catalog.select_candidates("summary-alias", _request(), FakeBreaker(("blocked",)))
    assert [candidate.model for candidate in selected] == ["model-a", "model-b"]


@pytest.mark.parametrize(("budget", "expected_count"), [("60", 2), ("120", 4)])
def test_selection_hops_are_also_bounded_by_first_byte_budget(
    tmp_path: Path, budget: str, expected_count: int
) -> None:
    from core.model_fallback_chain import load_chains

    models = ["model-a", "model-b", "model-c", "model-d"]
    _write_yaml(tmp_path, _document([_candidate(model) for model in models]))
    catalog = load_chains(
        chains_dir=tmp_path,
        env={
            "BRIDGE_FALLBACK_MAX_HOPS": "4",
            "BRIDGE_FALLBACK_ATTEMPT_FIRST_BYTE_TIMEOUT_S": "30",
            "BRIDGE_FALLBACK_TOTAL_BUDGET_S": budget,
        },
    )
    selected = catalog.select_candidates("summary-alias", _request(), FakeBreaker())
    assert [candidate.model for candidate in selected] == models[:expected_count]


HAND_WRITTEN_YAML = """\
# комментарий
quota_rules:
  body_patterns:
    - 'plan\\s+empty'   # хвостовой комментарий
    - "quo\\\\ta"
  error_codes: [GoUsageLimitError, 'x']
chains:
  summary-alias:
    declared_context_window: 1000000
    disabled_target: "model-b"
    preserve_alias_in_response: false
    exhausted_status_code: 503
    candidates:
      - model: "model-a"
        quota_scope: 'acct'
        cost_class: subscription
        context_window: 1000
      - model: model-b   # без кавычек
        cost_class: "paid"
        context_window: 2000
"""


def test_load_chains_without_pyyaml_uses_stdlib_parser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.model_fallback_chain as module

    (tmp_path / "chain.yaml").write_text(HAND_WRITTEN_YAML, encoding="utf-8")
    monkeypatch.setattr(module, "yaml", None)
    catalog = module.load_chains(chains_dir=tmp_path, env={})
    chain = catalog.chains["summary-alias"]
    assert chain.preserve_alias_in_response is False and chain.exhausted_status_code == 503
    assert [(c.model, c.cost_class, c.context_window, c.quota_scope) for c in chain.candidates] == [
        ("model-a", "subscription", 1000, "acct"), ("model-b", "paid", 2000, "")]
    assert catalog.quota_rules["error_codes"] == ("GoUsageLimitError", "x")
    assert catalog.quota_rules["body_patterns"][0] == r"plan\s+empty"


def test_stdlib_parser_matches_pyyaml_on_repo_config() -> None:
    import yaml

    from core import simple_yaml

    text = (Path(__file__).resolve().parents[1] / "fallback_chains.d/compaction.yaml").read_text()
    assert simple_yaml.loads(text) == yaml.safe_load(text)
    assert simple_yaml.loads(HAND_WRITTEN_YAML) == yaml.safe_load(HAND_WRITTEN_YAML)


def test_stdlib_parser_json_scalars_and_errors() -> None:
    from core import simple_yaml

    assert simple_yaml.loads('{"a": [1, true]}') == {"a": [1, True]}
    assert simple_yaml.loads("a: 1\nb: False\nc: -2.5\nd: ~\ne: []\nf:\n- x\n- y\n") == {
        "a": 1, "b": False, "c": -2.5, "d": None, "e": [], "f": ["x", "y"]}
    for bad in ("a: 1\na: 2\n", "a: |\n  x\n", "a:\n\tb: 1\n", "a: &x 1\n", "just text\n"):
        with pytest.raises(ValueError):
            simple_yaml.loads(bad)


def test_broken_yaml_without_pyyaml_is_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.model_fallback_chain as module

    (tmp_path / "chain.yaml").write_text("chains:\n  a: [unterminated\n", encoding="utf-8")
    monkeypatch.setattr(module, "yaml", None)
    with pytest.raises(ValueError, match="invalid fallback YAML"):
        module.load_chains(chains_dir=tmp_path, env={})


def test_quota_scope_defaults_empty_and_must_be_string(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document())
    assert [c.quota_scope for c in load_chains(chains_dir=tmp_path, env={}).chains["summary-alias"].candidates] == ["", ""]
    bad = _document([{**_candidate("model-a"), "quota_scope": 5}, _candidate("model-b")])
    _write_yaml(tmp_path, bad)
    with pytest.raises(ValueError, match="quota_scope"):
        load_chains(chains_dir=tmp_path, env={})


def test_select_candidates_skips_blocked_quota_scope(tmp_path: Path) -> None:
    from core.model_fallback_chain import load_chains

    _write_yaml(tmp_path, _document([
        {**_candidate("model-a"), "quota_scope": "acct"},
        {**_candidate("model-b"), "quota_scope": "acct"},
        {**_candidate("model-c"), "quota_scope": "other"},
    ]))
    catalog = load_chains(chains_dir=tmp_path, env={})
    picked = catalog.select_candidates("summary-alias", _request(), FakeBreaker(("scope:acct",)))
    assert [c.model for c in picked] == ["model-c"]
    picked = catalog.select_candidates("summary-alias", _request(), FakeBreaker(("model-a",)))
    assert [c.model for c in picked] == ["model-b", "model-c"]
