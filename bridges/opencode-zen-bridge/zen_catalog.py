"""Чистые функции каталога бесплатных моделей OpenCode Zen для моста и синхронизатора.

Модуль общий для `server.py` (читает каталог) и `sync_dsh_models.py` (единственный
писатель). Здесь нет сети, записи файлов и сторонних библиотек: только `json`, `re`
и `typing`, синтаксис совместим с `/usr/bin/python3` (3.9) и с `.venv` (3.14).

Правила (архитектурный пакет dsh-zen-autosync-20261024, AD-001..AD-007):

* активный каталог = free-модели `api.json` (`cost.input == 0`, `status != "deprecated"`,
  `tool_call is True`) ∩ живой список Zen − `DENYLIST`;
* уровень мышления L -> `ceil_clamp`: минимальный уровень модели с рангом >= L,
  если такого нет — максимальный; `none` — выключение, в variant не попадает;
* `contextWindow = min(limit.context, limit.input)` (если `limit.input` задан),
  `maxTokens = limit.output`, `input = modalities ∩ [text, image] ∩ BRIDGE_INPUT_MODALITIES`.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

SCHEMA_VERSION = 1

# Шкала уровней мышления; ultra == max.
LEVEL_RANK: Dict[str, int] = {
    "none": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4, "xhigh": 5, "max": 6, "ultra": 6,
}
CARD_LEVELS: Tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
VARIANT_MAP_LEVELS: Tuple[str, ...] = ("minimal", "low", "medium", "high", "xhigh", "max", "ultra")

# Модели из Zen-списка, которых не должно быть в каталоге (служебные и тестовые).
DENYLIST = frozenset({"jev-1.13", "jev-1.13-free", "test", "claude-opus-5-5-backup"})

MODEL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")

# Модальности, которые мост реально доносит до модели (image_url заменяется заглушкой).
# Когда мост начнёт передавать картинки — заменить на ("text", "image").
BRIDGE_INPUT_MODALITIES: Tuple[str, ...] = ("text",)
_CARD_INPUTS: Tuple[str, ...] = ("text", "image")

ALIAS_TARGET = "deepseek-v4.1-flash-free"

# Устаревшие id из старых сессий DSH -> актуальная модель. Не удалять: сессии хранят id.
DEPRECATED_MODEL_ALIASES: Dict[str, str] = {
    "minimax-m3.1-flash-free": ALIAS_TARGET,
    "longcat-2.5-preview-free": ALIAS_TARGET,
    "muse-spark-1.3-contributor-free": ALIAS_TARGET,
    "qwen3.6-plus-free": ALIAS_TARGET,
    "trinity-large-preview-free": ALIAS_TARGET,
    "nemotron-3-super-free": ALIAS_TARGET,
    "mimo-v2-pro-free": ALIAS_TARGET,
    "mimo-v2-omni-free": ALIAS_TARGET,
    "gpt-5-nano": ALIAS_TARGET,
    "k2p5": ALIAS_TARGET,
}

# Защитный порог синка: сокращение активного набора более чем на долю блокирует запись профилей.
MAX_SHRINK_RATIO = 0.5

Entry = Dict[str, Any]


# --------------------------------------------------------------------------- уровни

def effort_values(model: Dict[str, Any]) -> List[str]:
    """Допустимые значения `effort` из `reasoning_options` модели `api.json` (порядок сохраняется)."""
    options = model.get("reasoning_options")
    if not isinstance(options, list):
        return []
    for option in options:
        if isinstance(option, dict) and option.get("type") == "effort":
            values = option.get("values")
            if isinstance(values, list):
                return [v for v in values if isinstance(v, str) and v in LEVEL_RANK]
    return []


def thinking_levels(values: Sequence[str]) -> List[str]:
    """Уровни, реально включающие мышление: все, кроме `none`."""
    return [v for v in values if v != "none"]


def ceil_clamp(level: str, values: Sequence[str]) -> str:
    """Минимальный из `values` (без `none`) с рангом >= `level`; если нет — максимальный.

    Пустой набор `values` недопустим (вызывающий проверяет `thinking_levels`).
    """
    levels = thinking_levels(values)
    if not levels:
        raise ValueError("ceil_clamp: no thinking levels")
    rank = LEVEL_RANK[level]
    upper = [v for v in levels if LEVEL_RANK[v] >= rank]
    if upper:
        return min(upper, key=lambda v: LEVEL_RANK[v])
    return max(levels, key=lambda v: LEVEL_RANK[v])


def reasoning_efforts(values: Sequence[str]) -> Dict[str, str]:
    """Карточка `reasoningEfforts` для DSH: ключ — уровень UI, значение — уходит в `reasoning_effort`."""
    levels = thinking_levels(values)
    cards: Dict[str, str] = {"off": "off"}
    if not levels:
        for level in CARD_LEVELS:
            cards[level] = level
        return cards
    if "minimal" in values:
        cards["minimal"] = ceil_clamp("minimal", values)
    for level in CARD_LEVELS:
        cards[level] = ceil_clamp(level, values)
    return cards


def variant_map(values: Sequence[str]) -> Optional[Dict[str, str]]:
    """Таблица уровень запроса -> `#variant` CLI; `None`, если у модели нет variants."""
    if not thinking_levels(values):
        return None
    out = {level: ceil_clamp(level, values) for level in VARIANT_MAP_LEVELS}
    out["off"] = ""
    out["none"] = ""
    return out


# --------------------------------------------------------------------------- лимиты и карточка

def _positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def context_window(limit: Dict[str, Any]) -> Optional[int]:
    """`min(context, input)` при заданном `input`, иначе `context`."""
    context = _positive_int(limit.get("context"))
    if context is None:
        return None
    input_limit = _positive_int(limit.get("input"))
    return min(context, input_limit) if input_limit is not None else context


def card_input(model: Dict[str, Any], bridge_modalities: Sequence[str] = BRIDGE_INPUT_MODALITIES) -> List[str]:
    """`modalities.input ∩ [text, image] ∩ bridge_modalities`, минимум `[text]`."""
    modalities = model.get("modalities")
    declared = modalities.get("input") if isinstance(modalities, dict) else None
    declared = declared if isinstance(declared, list) else []
    result = [m for m in _CARD_INPUTS if m in declared and m in bridge_modalities]
    return result or ["text"]


def valid_model_id(model_id: Any) -> bool:
    return isinstance(model_id, str) and MODEL_ID_RE.match(model_id) is not None


def build_entry(model_id: str, model: Dict[str, Any]) -> Optional[Entry]:
    """Запись каталога (карточка DSH + метаданные моста) или `None` при невалидных данных."""
    if not valid_model_id(model_id) or not isinstance(model, dict):
        return None
    limit = model.get("limit")
    if not isinstance(limit, dict):
        return None
    window = context_window(limit)
    output = _positive_int(limit.get("output"))
    if window is None or output is None:
        return None
    values = effort_values(model)
    api_name = model.get("name")
    return {
        "id": model_id,
        "api_name": api_name if isinstance(api_name, str) and api_name.strip() else model_id,
        "effort_values": values,
        "cordis": {
            "contextWindow": window,
            "maxTokens": output,
            "input": card_input(model),
            "reasoningEfforts": reasoning_efforts(values),
        },
        "bridge": {
            "context_length": window,
            "max_output": output,
            "supports_variant": bool(thinking_levels(values)),
            "variant_map": variant_map(values),
        },
    }


def card_name(entry: Entry) -> str:
    """Имя карточки в DSH: имя из api.json без суффикса ` Free` + ` (Zen)`."""
    name = str(entry.get("api_name") or entry["id"]).strip()
    if name.lower().endswith(" free"):
        name = name[: -len(" free")].rstrip()
    return "%s (Zen)" % name


# --------------------------------------------------------------------------- выбор активных моделей

def api_models(api: Any) -> Dict[str, Any]:
    """`api.json` -> словарь моделей провайдера `opencode`; пустой при неверной структуре."""
    provider = api.get("opencode") if isinstance(api, dict) else None
    models = provider.get("models") if isinstance(provider, dict) else None
    return models if isinstance(models, dict) else {}


def _cost_is_free(model: Dict[str, Any]) -> bool:
    cost = model.get("cost")
    value = cost.get("input") if isinstance(cost, dict) else None
    return not isinstance(value, bool) and isinstance(value, (int, float)) and value == 0


def is_active_free(model: Any) -> bool:
    """free (`cost.input == 0`), не deprecated, с поддержкой вызова инструментов."""
    if not isinstance(model, dict):
        return False
    return _cost_is_free(model) and model.get("status") != "deprecated" and model.get("tool_call") is True


def is_deprecated_free(model: Any) -> bool:
    return isinstance(model, dict) and _cost_is_free(model) and model.get("status") == "deprecated"


def zen_ids(payload: Any) -> Set[str]:
    """Идентификаторы из ответа `/zen/v1/models` (`{"data": [{"id": ...}]}` или список)."""
    items = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        return set()
    out: Set[str] = set()
    for item in items:
        model_id = item.get("id") if isinstance(item, dict) else item
        if isinstance(model_id, str):
            out.add(model_id)
    return out


def select_active(models: Dict[str, Any], zen: Iterable[str],
                  denylist: Iterable[str] = DENYLIST) -> List[str]:
    """Отсортированные id активного каталога."""
    available = set(zen)
    denied = set(denylist)
    return sorted(
        model_id for model_id, model in models.items()
        if model_id in available and model_id not in denied
        and valid_model_id(model_id) and is_active_free(model)
    )


def build_catalog(models: Dict[str, Any], zen: Iterable[str],
                  denylist: Iterable[str] = DENYLIST) -> List[Entry]:
    """Записи активных моделей, отсортированные по id; модели с битыми лимитами пропускаются."""
    entries: List[Entry] = []
    for model_id in select_active(models, zen, denylist):
        entry = build_entry(model_id, models[model_id])
        if entry is not None:
            entries.append(entry)
    return entries


def shrink_violation(new_ids: Sequence[str], previous_ids: Sequence[str]) -> Optional[str]:
    """Причина блокировки записи профилей: пустой набор или сокращение > 50 % к прошлому; иначе `None`."""
    if not new_ids:
        return "active catalog is empty"
    if previous_ids and len(new_ids) < len(previous_ids) * (1 - MAX_SHRINK_RATIO):
        return "active catalog shrank from %d to %d (>%d%%)" % (
            len(previous_ids), len(new_ids), int(MAX_SHRINK_RATIO * 100))
    return None


# --------------------------------------------------------------------------- алиасы

def pick_alias_target(active: Sequence[str], default_model: str = ALIAS_TARGET) -> str:
    """Куда уводить устаревшие id: `ALIAS_TARGET`, иначе модель по умолчанию, иначе первая активная."""
    if ALIAS_TARGET in active:
        return ALIAS_TARGET
    if default_model in active:
        return default_model
    return sorted(active)[0] if active else ALIAS_TARGET


def derive_aliases(models: Dict[str, Any], active: Sequence[str], previous_active: Sequence[str],
                   previous_retired: Sequence[str], default_model: str = ALIAS_TARGET
                   ) -> Tuple[Dict[str, str], List[str]]:
    """Алиасы = статические ∪ free deprecated из `api.json` ∪ retired (были активны, пропали).

    Возвращает (алиасы, retired). Активная модель алиасом не бывает.
    """
    target = pick_alias_target(active, default_model)
    active_set = set(active)
    retired = sorted((set(previous_retired) | set(previous_active)) - active_set)
    aliases: Dict[str, str] = {}
    for model_id in DEPRECATED_MODEL_ALIASES:
        aliases[model_id] = target
    for model_id, model in models.items():
        if valid_model_id(model_id) and is_deprecated_free(model):
            aliases[model_id] = target
    for model_id in retired:
        if valid_model_id(model_id):
            aliases[model_id] = target
    for model_id in list(aliases):
        if model_id in active_set:
            del aliases[model_id]
    return aliases, [m for m in retired if m in aliases]


def resolve_model(model_id: str, active: Sequence[str], aliases: Dict[str, str],
                  default_model: str = ALIAS_TARGET) -> Tuple[Optional[str], bool]:
    """(модель-исполнитель, был_ли_алиас); `(None, False)` — неизвестный id."""
    if model_id in active:
        return model_id, False
    if model_id in aliases or model_id in DEPRECATED_MODEL_ALIASES:
        target = aliases.get(model_id) or DEPRECATED_MODEL_ALIASES[model_id]
        if target not in active:
            target = pick_alias_target(active, default_model)
        return (target, True) if target in active else (None, False)
    return None, False


# --------------------------------------------------------------------------- состояние каталога

def make_state(entries: Sequence[Entry], aliases: Dict[str, str], retired: Sequence[str], *,
               degraded: bool, generated_at: str, api_fetched: bool, zen_fetched: bool) -> Dict[str, Any]:
    """Содержимое `state/zen-catalog.json` (производный каталог моста)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "degraded": bool(degraded),
        "sources": {"api": bool(api_fetched), "zen": bool(zen_fetched)},
        "active": [e["id"] for e in entries],
        "models": list(entries),
        "aliases": dict(sorted(aliases.items())),
        "retired": sorted(retired),
    }


def parse_state(obj: Any) -> Optional[Dict[str, Any]]:
    """Проверить и нормализовать состояние; `None`, если файл битый или каталог пуст."""
    if not isinstance(obj, dict) or obj.get("schema_version") != SCHEMA_VERSION:
        return None
    raw_models = obj.get("models")
    if not isinstance(raw_models, list):
        return None
    entries: List[Entry] = []
    for item in raw_models:
        if not isinstance(item, dict) or not valid_model_id(item.get("id")):
            return None
        cordis, bridge = item.get("cordis"), item.get("bridge")
        if not isinstance(cordis, dict) or not isinstance(bridge, dict):
            return None
        if _positive_int(bridge.get("context_length")) is None or _positive_int(bridge.get("max_output")) is None:
            return None
        if not isinstance(cordis.get("reasoningEfforts"), dict):
            return None
        vmap = bridge.get("variant_map")
        if bridge.get("supports_variant") and not isinstance(vmap, dict):
            return None
        entries.append(item)
    if not entries:
        return None
    aliases = obj.get("aliases")
    retired = obj.get("retired")
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": str(obj.get("generated_at") or ""),
        "degraded": bool(obj.get("degraded")),
        "sources": obj.get("sources") if isinstance(obj.get("sources"), dict) else {},
        "active": [e["id"] for e in entries],
        "models": entries,
        "aliases": {k: v for k, v in aliases.items() if isinstance(k, str) and isinstance(v, str)}
        if isinstance(aliases, dict) else {},
        "retired": [r for r in retired if isinstance(r, str)] if isinstance(retired, list) else [],
    }


def load_state_file(path: Any) -> Optional[Dict[str, Any]]:
    """Прочитать и проверить `zen-catalog.json`; `None`, если файла нет или он невалиден."""
    try:
        with open(str(path), "r", encoding="utf-8") as handle:
            return parse_state(json.load(handle))
    except (OSError, ValueError):
        return None


def entries_to_bridge_models(entries: Sequence[Entry]) -> Dict[str, Dict[str, Any]]:
    """Записи каталога -> формат `ALLOWED_MODELS` моста."""
    out: Dict[str, Dict[str, Any]] = {}
    for entry in entries:
        bridge = entry["bridge"]
        meta: Dict[str, Any] = {
            "context_length": bridge["context_length"],
            "max_output": bridge["max_output"],
            "supports_variant": bool(bridge.get("supports_variant")),
            "effort_values": list(entry.get("effort_values") or []),
            "reasoning_efforts": list(entry["cordis"]["reasoningEfforts"]),
        }
        if bridge.get("variant_map"):
            meta["variant_map"] = dict(bridge["variant_map"])
        out[entry["id"]] = meta
    return out


# --------------------------------------------------------------------------- встроенный снимок

# (id, имя в api.json, effort.values, limit.context, limit.input, limit.output) — api.json 2026-10-24.
_FALLBACK_SPEC: Tuple[Tuple[str, str, Tuple[str, ...], int, Optional[int], int], ...] = (
    ("beam-free", "Beam Free", ("low", "medium", "high", "xhigh", "max"), 1048576, None, 131072),
    ("big-pickle", "Big Pickle", (), 200000, 160000, 32000),
    ("deepseek-v4.1-flash-free", "DeepSeek V4.1 Flash Free", ("low", "high", "max"), 200000, None, 32000),
    ("flint-40b-free", "Flint 40B Free", ("low", "medium", "high", "xhigh", "max"), 262144, None, 65536),
    ("glm-5.3-flash-free", "GLM-5.3-Flash Free", ("low", "high", "max"), 200000, None, 32000),
    ("mimo-v2.6-flash-free", "MiMo-V2.6-Flash Free", (), 200000, None, 32000),
    ("nemotron-3.5-lightning-free", "Nemotron 3.5 Lightning Free", (), 262144, None, 262144),
    ("nemotron-3.5-super-vl-free", "Nemotron 3.5 Super VL Free",
     ("none", "minimal", "low", "medium", "high", "xhigh"), 1048576, 1048576, 131072),
)


def _fallback_entries() -> List[Entry]:
    entries: List[Entry] = []
    for model_id, name, values, context, input_limit, output in _FALLBACK_SPEC:
        limit: Dict[str, Any] = {"context": context, "output": output}
        if input_limit is not None:
            limit["input"] = input_limit
        model: Dict[str, Any] = {
            "name": name,
            "limit": limit,
            "modalities": {"input": ["text"]},
            "reasoning_options": [{"type": "effort", "values": list(values)}] if values else [],
        }
        entry = build_entry(model_id, model)
        assert entry is not None
        entries.append(entry)
    return entries


# Последний известный рабочий каталог (LKG): используется, если state-файла нет или он битый.
STATIC_FALLBACK_CATALOG: List[Entry] = _fallback_entries()


def fallback_state() -> Dict[str, Any]:
    """Состояние на основе `STATIC_FALLBACK_CATALOG` (алиасы — только статические)."""
    active = [e["id"] for e in STATIC_FALLBACK_CATALOG]
    target = pick_alias_target(active)
    aliases = {k: target for k in DEPRECATED_MODEL_ALIASES if k not in active}
    state = make_state(STATIC_FALLBACK_CATALOG, aliases, [], degraded=True, generated_at="",
                       api_fetched=False, zen_fetched=False)
    return state


# --------------------------------------------------------------------------- вывод эталона

def golden_line(entry: Entry) -> str:
    """Одна строка эталонной таблицы (`--print-golden`)."""
    cordis, bridge = entry["cordis"], entry["bridge"]
    efforts = ",".join("%s:%s" % (k, v) for k, v in cordis["reasoningEfforts"].items())
    return "%s | effort=%s | context=%d | max=%d | input=%s | efforts=%s | variant=%s" % (
        entry["id"], ",".join(entry.get("effort_values") or []) or "-",
        cordis["contextWindow"], cordis["maxTokens"], ",".join(cordis["input"]), efforts,
        "yes" if bridge.get("supports_variant") else "no")
