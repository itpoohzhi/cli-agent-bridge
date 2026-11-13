"""Загрузка неизменяемых цепочек моделей и отбор допустимых кандидатов."""

from __future__ import annotations

import json
import logging
import math
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
from types import MappingProxyType
from typing import Protocol, cast

from core import simple_yaml

try:  # PyYAML отсутствует в рабочем интерпретаторе моста: тогда — парсер на stdlib.
    import yaml
except ImportError:  # pragma: no cover - зависит от окружения
    yaml = None

_LOG = logging.getLogger(__name__)


class QuotaBreakerPort(Protocol):
    """Единственный внешний владелец состояния квотного cooldown."""

    def record_429(self, model_id: str, ttl_s: float, reason: str) -> None: ...

    def is_blocked(self, model_id: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class FallbackCandidate:
    """Метаданные одной фактической модели."""

    model: str
    cost_class: str
    context_window: int
    quota_scope: str = ""  # аккаунт/провайдер, делящий квоту между моделями; "" — нет общего scope


def scope_key(candidate: FallbackCandidate) -> str:
    """Ключ breaker для общей квоты аккаунта/провайдера; пустая строка — нет scope."""
    return f"scope:{candidate.quota_scope}" if candidate.quota_scope else ""


def candidate_blocked(breaker: QuotaBreakerPort, candidate: FallbackCandidate) -> bool:
    """Заблокирована модель либо весь её quota_scope."""
    scope = scope_key(candidate)
    return breaker.is_blocked(candidate.model) or (bool(scope) and breaker.is_blocked(scope))


@dataclass(frozen=True, slots=True, kw_only=True)
class FallbackChain:
    """Порядок кандидатов и контракт ответа алиаса."""

    candidates: tuple[FallbackCandidate, ...]
    declared_context_window: int
    disabled_target: str
    preserve_alias_in_response: bool
    exhausted_status_code: int


def _positive_int(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(
        not isinstance(k, str) for k in cast(dict[object, object], value)
    ):
        raise ValueError(f"{label} must be a mapping with string keys")
    return cast(dict[str, object], value)


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _candidate(raw: object) -> FallbackCandidate:
    data = _mapping(raw, "candidate")
    cost = _name(data.get("cost_class"), "candidate cost_class")
    if cost not in ("subscription", "paid"):
        raise ValueError("candidate cost_class must be subscription or paid")
    scope = data.get("quota_scope", "")
    if not isinstance(scope, str):
        raise ValueError("candidate quota_scope must be a string")
    return FallbackCandidate(
        _name(data.get("model"), "candidate model"),
        cost,
        _positive_int(data.get("context_window"), "candidate context_window"),
        scope.strip(),
    )


def _chain(raw: object, env: Mapping[str, str]) -> FallbackChain:
    data = _mapping(raw, "chain")
    entries = data.get("candidates")
    if not isinstance(entries, list) or len(cast(list[object], entries)) < 2:
        raise ValueError("chain must contain at least two candidates")
    candidates = tuple(_candidate(entry) for entry in cast(list[object], entries))
    models = {candidate.model for candidate in candidates}
    if len(models) != len(candidates):
        raise ValueError("chain candidates must have distinct model IDs")
    disabled = data.get("disabled_target", candidates[0].model)
    if not isinstance(disabled, str) or disabled not in models:
        raise ValueError("chain disabled_target must name a candidate")
    preserve = data.get("preserve_alias_in_response", True)
    if not isinstance(preserve, bool):
        raise ValueError("chain preserve_alias_in_response must be boolean")
    status = (
        data["exhausted_status_code"]
        if "exhausted_status_code" in data
        else int(env.get("BRIDGE_FALLBACK_EXHAUSTED_STATUS", "429"))
    )
    if not isinstance(status, int) or status not in (429, 503):
        raise ValueError("chain exhausted_status_code must be 429 or 503")
    return FallbackChain(
        candidates=candidates,
        declared_context_window=_positive_int(data.get("declared_context_window"), "chain context"),
        disabled_target=disabled,
        preserve_alias_in_response=preserve,
        exhausted_status_code=status,
    )


def _positive(env: Mapping[str, str], key: str, default: float) -> float:
    value = float(env.get("BRIDGE_FALLBACK_" + key, str(default)))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"BRIDGE_FALLBACK_{key} must be positive and finite")
    return value


def _input_chars(request: Mapping[str, object]) -> int:
    total = 0
    messages = request.get("messages", ())
    if not isinstance(messages, (list, tuple)):
        raise ValueError("messages must be a list")
    for raw in cast(Sequence[object], messages):
        message = _mapping(raw, "message")
        content = message.get("content")
        if content is not None:
            total += (
                len(content)
                if isinstance(content, str)
                else len(json.dumps(content, ensure_ascii=False))
            )
        if message.get("tool_calls"):
            total += len(json.dumps(message["tool_calls"], ensure_ascii=False))
    if request.get("tools"):
        total += len(json.dumps(request["tools"], ensure_ascii=False))
    return total


@dataclass(frozen=True, slots=True, kw_only=True)
class FallbackCatalog:
    """Каталог и настройки отбора, не содержащие собственного состояния квот."""

    chains: Mapping[str, FallbackChain]
    quota_rules: Mapping[str, tuple[str, ...]]
    max_hops: int
    total_budget_s: float
    attempt_first_byte_timeout_s: float
    chars_per_token: float
    allow_paid: bool

    def select_candidates(
        self, alias: str, request: Mapping[str, object], breaker: QuotaBreakerPort
    ) -> tuple[FallbackCandidate, ...]:
        """Применяет стоимость, контекст и breaker до ограничения числа попыток."""
        output = request.get("max_tokens", request.get("max_completion_tokens", 0))
        if not isinstance(output, int) or isinstance(output, bool) or output < 0:
            raise ValueError("max_tokens must be a nonnegative integer")
        needed = math.ceil(_input_chars(request) / self.chars_per_token) + output
        hops = min(self.max_hops, int(self.total_budget_s / self.attempt_first_byte_timeout_s))
        selected = (
            candidate
            for candidate in self.chains[alias].candidates
            if (candidate.cost_class != "paid" or self.allow_paid)
            and candidate.context_window >= needed
            and not candidate_blocked(breaker, candidate)
        )
        return tuple(islice(selected, hops))


def _merge_rules(target: dict[str, tuple[str, ...]], raw: object) -> None:
    for key, values in _mapping(raw, "quota_rules").items():
        if key not in ("body_patterns", "error_codes", "reset_body_patterns"):
            raise ValueError(f"unknown quota_rules field: {key}")
        if not isinstance(values, list):
            raise ValueError(f"quota_rules.{key} must be a list of strings")
        items = cast(list[object], values)
        if any(not isinstance(v, str) for v in items):
            raise ValueError(f"quota_rules.{key} must be a list of strings")
        target[key] = tuple(dict.fromkeys((*target.get(key, ()), *cast(list[str], items))))


def _yaml_errors() -> tuple[type[Exception], ...]:
    return (ValueError,) if yaml is None else (ValueError, yaml.YAMLError)


def _parse_document(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    try:
        if yaml is None:
            return simple_yaml.loads(text)
        return cast(object, yaml.safe_load(text))
    except _yaml_errors() as exc:
        raise ValueError(f"invalid fallback YAML: {path.name}") from exc


def _load_documents(
    directory: Path, env: Mapping[str, str]
) -> tuple[dict[str, FallbackChain], dict[str, tuple[str, ...]]]:
    chains: dict[str, FallbackChain] = {}
    rules: dict[str, tuple[str, ...]] = {}
    if directory.exists() and not directory.is_dir():
        raise ValueError("fallback chains path must be a directory")
    for path in sorted((*directory.glob("*.yaml"), *directory.glob("*.yml"))):
        data = _mapping(_parse_document(path), "document")
        _merge_rules(rules, data.get("quota_rules", {}))
        for alias, raw in _mapping(data.get("chains", {}), "chains").items():
            alias = _name(alias, "chain alias")
            if alias in chains:
                raise ValueError(f"duplicate chain alias: {alias}")
            chains[alias] = _chain(raw, env)
    return chains, rules


def load_chains(
    chains_dir: str | Path | None = None, *, env: Mapping[str, str] | None = None
) -> FallbackCatalog:
    """Загружает YAML безопасно; отсутствие каталога не создаёт новых алиасов."""
    environ = os.environ if env is None else env
    directory = Path(
        chains_dir
        if chains_dir is not None
        else environ.get("BRIDGE_FALLBACK_CHAINS_PATH", "./fallback_chains.d")
    )
    chains, rules = _load_documents(directory, environ)
    return _build_catalog(chains, rules, environ)


def empty_catalog(env: Mapping[str, str] | None = None) -> FallbackCatalog:
    """Каталог без алиасов с дефолтными параметрами (безопасный откат при битом конфиге)."""
    return _build_catalog({}, {}, {} if env is None else env)


def _build_catalog(
    chains: dict[str, FallbackChain], rules: dict[str, tuple[str, ...]], environ: Mapping[str, str]
) -> FallbackCatalog:
    max_hops = _positive_int(int(environ.get("BRIDGE_FALLBACK_MAX_HOPS", "4")), "max_hops")
    timeout = _positive(environ, "ATTEMPT_FIRST_BYTE_TIMEOUT_S", 30)
    budget = _positive(environ, "TOTAL_BUDGET_S", 120)
    if max_hops * timeout > budget:
        _LOG.warning("Fallback max_hops exceeds total first-byte budget; selection will be capped")
    return FallbackCatalog(
        chains=MappingProxyType(chains),
        quota_rules=MappingProxyType(rules),
        max_hops=max_hops,
        total_budget_s=budget,
        attempt_first_byte_timeout_s=timeout,
        chars_per_token=_positive(environ, "CHARS_PER_TOKEN", 3.0),
        allow_paid=environ.get("BRIDGE_FALLBACK_ALLOW_PAID", "false").strip().lower() == "true",
    )
