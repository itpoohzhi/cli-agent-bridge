"""Чистая доменная аналитика использования токенов и детектор всплесков prompt_tokens."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median
from time import gmtime, strftime
from typing import Any

__all__: tuple[str, ...] = (
    "AnomalyThresholds",
    "aggregate_records",
    "compute_cache_hit_pct",
    "detect_prompt_anomalies",
    "enrich_with_cache_hit",
)

_TOKEN_FIELDS: tuple[str, ...] = (
    "prompt_tokens",
    "completion_tokens",
    "cached_tokens",
    "reasoning_tokens",
    "total_tokens",
)


@dataclass(frozen=True)
class AnomalyThresholds:
    """Пороги детектора аномальных всплесков prompt_tokens."""

    ratio_threshold: float = 2.0
    min_turn_prompt_tokens: int = 100000
    min_day_prompt_tokens: int = 5000000


def _opt_int(value: Any) -> int | None:
    """Приведение скаляра к int или None при отсутствии или ошибке разбора."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _as_int(value: Any) -> int:
    """Безопасное приведение скаляра к int (bool и некорректные значения -> 0)."""
    return _opt_int(value) or 0


def compute_cache_hit_pct(cached_tokens: int | None, prompt_tokens: int | None) -> float:
    """Доля кэшированных prompt-токенов в процентах, зажатая в [0.0, 100.0]."""
    prompt = _as_int(prompt_tokens)
    if prompt <= 0:
        return 0.0
    return min(100.0, max(0.0, round(100.0 * _as_int(cached_tokens) / prompt, 2)))


def enrich_with_cache_hit(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Вернуть копии строк с добавленным вычисленным полем cache_hit_pct."""
    return [
        {**r, "cache_hit_pct": compute_cache_hit_pct(r.get("cached_tokens"), r.get("prompt_tokens"))}
        for r in rows
    ]


def _normalize_role(record: Mapping[str, Any]) -> str:
    """Нормализовать subagent_role: пустая строка или None -> interactive."""
    raw = record.get("subagent_role")
    return (raw.strip() if isinstance(raw, str) else "") or "interactive"


def _extract_day(record: Mapping[str, Any]) -> str:
    """Извлечь UTC-дату YYYY-MM-DD из полей day, ts_iso, ts или ts_epoch."""
    for key in ("day", "ts_iso", "ts"):
        val = record.get(key)
        if isinstance(val, str) and len(val) >= 10 and val[4:5] == "-" and val[7:8] == "-":
            return val[:10]
    epoch = record.get("ts_epoch") if record.get("ts_epoch") is not None else record.get("ts")
    if isinstance(epoch, (int, float)) and not isinstance(epoch, bool):
        try:
            return strftime("%Y-%m-%d", gmtime(float(epoch)))
        except (OverflowError, OSError, ValueError):
            return "unknown"
    return "unknown"


def _new_bucket(keys: Mapping[str, Any], with_status: bool = False) -> dict[str, Any]:
    """Создать пустой словарь-счётчик агрегата по заданным ключам."""
    bucket: dict[str, Any] = {**keys, "requests": 0, **{field: 0 for field in _TOKEN_FIELDS}}
    if with_status:
        bucket["ok_requests"] = 0
        bucket["error_requests"] = 0
    return bucket


def _accumulate(
    bucket: dict[str, Any],
    record: Mapping[str, Any],
    with_status: bool = False,
    count_requests: bool = True,
) -> None:
    """Обновить счётчики запросов, статусов и сумм токенов для разреза."""
    if count_requests:
        bucket["requests"] += 1
    if with_status:
        status = _opt_int(record.get("status_code"))
        is_ok = status is not None and 200 <= status < 400
        bucket["ok_requests"] += int(is_ok)
        bucket["error_requests"] += int(not is_ok)
    for field in _TOKEN_FIELDS:
        bucket[field] += _as_int(record.get(field))


def _detect_day_spikes(
    by_day: Sequence[Mapping[str, Any]],
    thresholds: AnomalyThresholds,
) -> list[dict[str, Any]]:
    """Выявить дневные всплески prompt_tokens относительно медианы предшествующих дней."""
    alerts: list[dict[str, Any]] = []
    prior_prompts: list[int] = []
    for row in sorted(by_day, key=lambda item: str(item.get("day") or "")):
        day_prompt = _as_int(row.get("prompt_tokens"))
        if prior_prompts:
            baseline = float(median(prior_prompts))
            if (
                baseline > 0.0
                and day_prompt >= thresholds.min_day_prompt_tokens
                and day_prompt >= baseline * thresholds.ratio_threshold
            ):
                alerts.append({
                    "scope": "day",
                    "key": str(row.get("day") or ""),
                    "prompt_tokens": day_prompt,
                    "baseline_tokens": round(baseline, 2),
                    "ratio": round(day_prompt / baseline, 2),
                    "reason": "day_prompt_spike",
                })
        if day_prompt > 0:
            prior_prompts.append(day_prompt)
    return alerts


def _detect_turn_spikes(
    recent_turns: Sequence[Mapping[str, Any]],
    thresholds: AnomalyThresholds,
) -> list[dict[str, Any]]:
    """Выявить всплески prompt_tokens на отдельных ходах относительно медианы модели или пула."""
    all_prompts: list[int] = []
    by_model: dict[str, list[int]] = {}
    for turn in recent_turns:
        prompt = _as_int(turn.get("prompt_tokens"))
        if prompt > 0:
            all_prompts.append(prompt)
            by_model.setdefault(str(turn.get("model") or "unknown"), []).append(prompt)
    if len(all_prompts) < 3:
        return []
    pool_baseline = float(median(all_prompts))
    model_baselines = {m: float(median(vals)) for m, vals in by_model.items() if len(vals) >= 3}
    alerts: list[dict[str, Any]] = []
    for turn in recent_turns:
        prompt = _as_int(turn.get("prompt_tokens"))
        if prompt < thresholds.min_turn_prompt_tokens:
            continue
        model = str(turn.get("model") or "unknown")
        baseline = model_baselines.get(model, pool_baseline)
        if baseline > 0.0 and prompt >= baseline * thresholds.ratio_threshold:
            role = _normalize_role(turn)
            alerts.append({
                "scope": "turn",
                "key": f"{model}:{role}",
                "request_id": str(turn.get("request_id") or ""),
                "model": model,
                "subagent_role": role,
                "subagent_id": str(turn.get("subagent_id") or ""),
                "prompt_tokens": prompt,
                "baseline_tokens": round(baseline, 2),
                "ratio": round(prompt / baseline, 2),
                "reason": "turn_prompt_spike",
            })
    return alerts


def detect_prompt_anomalies(
    by_day: Sequence[Mapping[str, Any]],
    recent_turns: Sequence[Mapping[str, Any]],
    thresholds: AnomalyThresholds | None = None,
) -> list[dict[str, Any]]:
    """Детектор дневных и походовых всплесков prompt_tokens."""
    cfg = thresholds if thresholds is not None else AnomalyThresholds()
    return [*_detect_day_spikes(by_day, cfg), *_detect_turn_spikes(recent_turns, cfg)]


def aggregate_records(
    records: Sequence[Mapping[str, Any]],
    thresholds: AnomalyThresholds | None = None,
) -> dict[str, Any]:
    """Универсальная чистая агрегация записей usage (JSONL или строки БД)."""
    summary = _new_bucket({"total_requests": 0, "usage_present_requests": 0}, with_status=True)
    summary.pop("requests")
    by_model: dict[tuple[str, str], dict[str, Any]] = {}
    by_role: dict[tuple[str, str], dict[str, Any]] = {}
    by_day: dict[str, dict[str, Any]] = {}
    for rec in records:
        summary["total_requests"] += 1
        summary["usage_present_requests"] += int(bool(rec.get("usage_present")))
        _accumulate(summary, rec, with_status=True, count_requests=False)
        m_key = (str(rec.get("model") or ""), str(rec.get("backend_id") or ""))
        _accumulate(by_model.setdefault(m_key, _new_bucket({"model": m_key[0], "backend_id": m_key[1]})), rec)
        r_key = (_normalize_role(rec), str(rec.get("subagent_id") or ""))
        r_bucket = by_role.setdefault(r_key, _new_bucket({"subagent_role": r_key[0], "subagent_id": r_key[1]}))
        _accumulate(r_bucket, rec)
        day = _extract_day(rec)
        _accumulate(by_day.setdefault(day, _new_bucket({"day": day}, with_status=True)), rec, with_status=True)
    summary["cache_hit_pct"] = compute_cache_hit_pct(summary["cached_tokens"], summary["prompt_tokens"])
    models = sorted(
        enrich_with_cache_hit(list(by_model.values())),
        key=lambda x: (-x["requests"], -x["prompt_tokens"], x["model"], x["backend_id"]),
    )
    roles = sorted(
        enrich_with_cache_hit(list(by_role.values())),
        key=lambda x: (-x["prompt_tokens"], -x["requests"], x["subagent_role"], x["subagent_id"]),
    )
    days = sorted(enrich_with_cache_hit(list(by_day.values())), key=lambda x: x["day"])
    anomalies = detect_prompt_anomalies(days, records, thresholds)
    return {"summary": summary, "by_model": models, "by_role": roles, "by_day": days, "prompt_anomalies": anomalies}
