#!/opt/homebrew/bin/python3
"""fleet_check.py — read-only проверка каталога Droid-флота и профилей DSH.

C-07 / BND-002. Запуск: /opt/homebrew/bin/python3 fleet_check.py [ключи].
Вывод — JSON в stdout (ключи `ok`, `policy.sha_match`, `default_compat`, …);
exit 0 только если все проверки прошли. Файлы не пишутся, секреты не читаются
(значения `apiKeyEnv` не раскрываются), инференс не выполняется.

Проверки §9 брифа: (1) C-01 каталог (три класса), (2) sha models.md ==
policy_ref.sha256, (3) efforts ⊆ model-efforts.json и ровно dev-контекст,
(4) --live-droid: `--list-tools` по 6 id (rc=0) и контрольному id (rc≠0),
(5) профили по C-06 (модель/поле в ошибке), (6) allowlist == каталог,
(7б) default_compat (AD-029/RW4-003), (8) --web-dump, (9) opus_refs=0,
(10) --image-census (класс III и привязка proof к бинарю).
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
HOME = Path(os.path.expanduser("~"))

DEFAULT_CATALOGUE = ROOT / "fleet.json"
DEFAULT_DESKTOP = HOME / ".dsh/profiles/desktop/cordis.patch.yml"
DEFAULT_WEB = HOME / ".dsh/profiles/web/cordis.patch.yml"
DEFAULT_EFFORTS = HOME / ".hermes/droid-cli-proxy/model-efforts.json"
DEFAULT_POLICY = HOME / "Мой диск/Context/models.md"
DEFAULT_LAUNCHER = HOME / ".config/factory-launch/droid-cli.sh"

CONTROL_MODEL = "zzz-no-such-model-000"
LIVE_TOOLS_TIMEOUT_S = 90

LEVELS = {"minimal", "low", "medium", "high", "xhigh", "max"}
STATUSES = {"unsupported", "unverified", "probe", "confirmed"}
# RW-001/AD-022: допустимый набор effort — только dev-контекст, по моделям.
DEV_EFFORTS = {
    "claude-sonnet-5-5": ["high"],
    "gemini-3.8-flash": ["high"],
    "grok-4.7": ["high"],
    "deepseek-v4.1-flash": ["high", "max"],
    "gpt-6.1-sol": ["high"],
    "glm-5.3": ["max"],
}
METHOD_IMPL_VERSIONS = {"workspace-read": 1}
DROID_SECTION_RE = re.compile(r"^      droid-bridge:\s*$")


class Loader(yaml.SafeLoader):
    """SafeLoader с multi-constructor для js-тегов (как в VER-010)."""


for _prefix in ("tag:yaml.org,2002:js", "!"):
    Loader.add_multi_constructor(
        _prefix,
        lambda loader, suffix, node: (
            ("js", loader.construct_scalar(node))
            if isinstance(node, yaml.ScalarNode)
            else ("js", None)
        ),
    )


class Report:
    def __init__(self):
        self.checks = []
        self.ok = True

    def add(self, name, errors, details=None):
        errors = [str(e) for e in errors]
        if errors:
            self.ok = False
        self.checks.append(
            {"name": name, "ok": not errors, "errors": errors, "details": details or {}}
        )

    def fail(self, name, message):
        self.add(name, [message])


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def expand(path):
    return os.path.expanduser(str(path))


def droid_scope(cat):
    """Копия каталога только с моделями droid: droid-проверки (efforts, профили, live) не про Muse."""
    scoped = dict(cat)
    scoped["models"] = [
        m for m in cat.get("models") or [] if m.get("backend", "droid") == "droid"
    ]
    return scoped


def check_catalogue(cat, report):
    """(1) C-01: структурные инварианты каталога; класс III — здесь."""
    errs = []
    if not isinstance(cat, dict):
        report.add("catalogue", ["каталог не является JSON-объектом"])
        return
    schema = cat.get("schema_version")
    if schema not in (2, 3):
        errs.append("schema_version не 2 и не 3")
    backends = cat.get("backends")
    if schema == 3:
        if not isinstance(backends, dict) or not backends:
            errs.append("backends: пустой или не объект (schema 3)")
            backends = {}
        for bid, entry in backends.items():
            if not isinstance(entry, dict) or entry.get("kind") not in (
                "droid",
                "muse",
            ):
                errs.append("backend_kind_unknown: %s" % bid)
    elif backends is not None:
        errs.append("backends_in_schema_2")
    models = cat.get("models")
    if not isinstance(models, list) or not models:
        errs.append("models: пустой или не список")
        report.add("catalogue", errs)
        return
    ids = []
    for model in models:
        mid = model.get("id")
        if not isinstance(mid, str) or not mid:
            errs.append("model без id")
            continue
        if mid in ids:
            errs.append("duplicate_id: " + mid)
        ids.append(mid)
        efforts = model.get("efforts")
        if not isinstance(efforts, list) or not efforts or set(efforts) - LEVELS:
            errs.append("efforts_invalid: %s (%r)" % (mid, efforts))
            efforts = efforts if isinstance(efforts, list) else []
        if len(set(efforts)) != len(efforts):
            errs.append("efforts_invalid (дубли): " + mid)
        if model.get("default_effort") not in efforts:
            errs.append("default_effort_invalid: %s" % mid)
        if schema == 3 and model.get("backend") not in (backends or {}):
            errs.append("model_backend_unknown: %s (%r)" % (mid, model.get("backend")))
        if (
            not isinstance(model.get("context_window"), int)
            or model.get("context_window") <= 0
        ):
            errs.append("context_window_invalid: " + mid)
        if not isinstance(model.get("max_tokens"), int) or model.get("max_tokens") <= 0:
            errs.append("max_tokens_invalid: " + mid)
        images = model.get("images")
        if not isinstance(images, dict):
            errs.append("images_missing: " + mid)
            continue
        status = images.get("status")
        if status not in STATUSES:
            errs.append("status_invalid: %s (%r)" % (mid, status))
            continue
        if (
            images.get("cli_registry") == "explicit_unsupported"
            and status != "unsupported"
        ):
            errs.append(
                "status_inconsistent (explicit_unsupported != unsupported): " + mid
            )
        input_list = model.get("input")
        if status in ("unsupported", "unverified"):
            if images.get("method") is not None:
                errs.append(
                    "status_inconsistent (method != null при %s): %s" % (status, mid)
                )
            if input_list != ["text"]:
                errs.append(
                    "status_inconsistent (input != [text] при %s): %s" % (status, mid)
                )
        if status in ("probe", "confirmed"):
            if images.get("method") not in METHOD_IMPL_VERSIONS:
                errs.append(
                    "confirmed_method_missing/метод не реализован: %s (%r)"
                    % (mid, images.get("method"))
                )
            if "image" not in (input_list or []):
                errs.append("confirmed_input_missing: " + mid)
        if status == "confirmed":
            proof = images.get("proof")
            if not isinstance(proof, dict):
                errs.append("confirmed_proof_missing: " + mid)
            else:
                errs.extend(_proof_errors(mid, proof, efforts))
                if sorted(proof.get("efforts_proven") or []) != sorted(efforts):
                    errs.append("класс III (efforts_proven != efforts): " + mid)
    default_model = cat.get("default_model")
    if default_model not in ids:
        errs.append("default_model_invalid: %r" % default_model)
    env_model = os.environ.get("DROID_DSH_BRIDGE_MODEL", "").strip()
    if env_model and env_model not in ids:
        errs.append("env DROID_DSH_BRIDGE_MODEL вне каталога: %r" % env_model)
    limits = cat.get("image_limits")
    if not isinstance(limits, dict):
        errs.append("image_limits: блок отсутствует")
    else:
        for key in (
            "max_images",
            "max_image_bytes",
            "max_total_image_bytes",
            "max_body_bytes",
        ):
            if not isinstance(limits.get(key), int) or limits[key] <= 0:
                errs.append("image_limits.%s: не положительное целое" % key)
        types = limits.get("types")
        if not isinstance(types, list) or not types or set(types) - {"image/png"}:
            errs.append(
                "image_limits.types: %r (ожидается непустое подмножество image/png)"
                % types
            )
    admission = cat.get("admission")
    if not isinstance(admission, dict):
        errs.append("admission: блок отсутствует")
    else:
        for key in ("max_http_connections", "max_inflight_body_bytes"):
            if not isinstance(admission.get(key), int) or admission[key] <= 0:
                errs.append("admission.%s: не положительное целое" % key)
    policy_ref = cat.get("policy_ref")
    if not isinstance(policy_ref, dict) or not re.fullmatch(
        r"[0-9a-f]{64}", str(policy_ref.get("sha256", ""))
    ):
        errs.append("policy_ref.sha256: отсутствует или не hex64")
    technical = cat.get("technical_ref")
    if not isinstance(technical, dict) or not technical.get("droid_binary_path"):
        errs.append("technical_ref.droid_binary_path: отсутствует")
    report.add(
        "catalogue", errs, {"models": ids, "schema_version": cat.get("schema_version")}
    )


def _proof_errors(mid, proof, efforts):
    errs = []
    for key in (
        "droid_version",
        "droid_binary_sha256",
        "method",
        "impl_version",
        "formats",
    ):
        if key not in proof:
            errs.append("confirmed_proof_malformed (%s отсутствует): %s" % (key, mid))
    if proof.get("method") not in METHOD_IMPL_VERSIONS:
        errs.append("confirmed_proof_malformed (метод не реализован): %s" % mid)
    if proof.get("impl_version") != METHOD_IMPL_VERSIONS.get(proof.get("method")):
        errs.append("confirmed_proof_malformed (impl_version): %s" % mid)
    if not re.fullmatch(r"[0-9a-f]{64}", str(proof.get("droid_binary_sha256", ""))):
        errs.append("confirmed_proof_malformed (droid_binary_sha256): %s" % mid)
    formats = proof.get("formats")
    if not isinstance(formats, list) or not formats:
        errs.append("confirmed_proof_malformed (formats): %s" % mid)
    proven = proof.get("efforts_proven")
    if (
        not isinstance(proven, list)
        or not proven
        or len(set(proven)) != len(proven)
        or set(proven) - set(efforts)
    ):
        errs.append("confirmed_efforts_proven_invalid: %s" % mid)
    return errs


def check_policy(cat, policy_path, report):
    """(2) sha models.md == policy_ref.sha256 (BLOCKED-POLICY-DRIFT)."""
    expected = (cat.get("policy_ref") or {}).get("sha256")
    info = {"path": str(policy_path), "expected": expected}
    try:
        actual = sha256_file(policy_path)
    except OSError as exc:
        info["sha256"] = None
        info["sha_match"] = False
        report.add("policy", ["policy-файл не читается: %s" % exc])
        report.policy = info
        return
    info["sha256"] = actual
    info["sha_match"] = actual == expected
    errs = (
        []
        if info["sha_match"]
        else ["sha models.md != policy_ref.sha256 (BLOCKED-POLICY-DRIFT)"]
    )
    report.add("policy", errs, info)
    report.policy = info


def check_efforts(cat, efforts_path, report):
    """(3) efforts ⊆ model-efforts.json и ровно dev-контекст (RW-001/AD-022)."""
    errs = []
    info = {"path": str(efforts_path), "models": {}}
    try:
        with open(efforts_path, "r", encoding="utf-8") as fh:
            registry = json.load(fh)
    except (OSError, ValueError) as exc:
        report.add("efforts", ["model-efforts.json не читается: %s" % exc], info)
        return
    registry_models = registry.get("models") if isinstance(registry, dict) else None
    if not isinstance(registry_models, dict):
        report.add("efforts", ["model-efforts.json: нет объекта models"], info)
        return
    for model in cat.get("models") or []:
        mid = model.get("id")
        allowed = registry_models.get(mid)
        info["models"][mid] = sorted(model.get("efforts") or [])
        if not isinstance(allowed, dict):
            errs.append("модель отсутствует в model-efforts.json: " + str(mid))
            continue
        supported = set(allowed.get("supported") or [])
        if set(model.get("efforts") or []) - supported:
            errs.append(
                "efforts вне model-efforts.json: %s (%s ⊄ %s)"
                % (mid, sorted(model.get("efforts") or []), sorted(supported))
            )
        if (
            mid in DEV_EFFORTS
            and sorted(model.get("efforts") or []) != DEV_EFFORTS[mid]
        ):
            errs.append(
                "efforts != dev-контекст (RW-001): %s (%s != %s)"
                % (mid, sorted(model.get("efforts") or []), DEV_EFFORTS[mid])
            )
    report.add("efforts", errs, info)


def _load_records(path, report, name):
    try:
        docs = yaml.load(read_text(path), Loader=Loader)
    except (OSError, yaml.YAMLError) as exc:
        report.add(name, ["профиль не читается/не парсится: %s" % exc])
        return None
    if not isinstance(docs, list):
        report.add(name, ["профиль не является списком записей"])
        return None
    return docs


def _records_by_id(docs):
    out = {}
    for rec in docs:
        if isinstance(rec, dict) and isinstance(rec.get("id"), str):
            out.setdefault(rec["id"], []).append(rec)
    return out


def _droid_models(records, errs, name):
    models = None
    for rec in records.get("llm-pi-ai") or []:
        config = rec.get("config") if isinstance(rec.get("config"), dict) else {}
        providers = (
            config.get("providers") if isinstance(config.get("providers"), dict) else {}
        )
        provider = providers.get("droid-bridge")
        if isinstance(provider, dict):
            if models is not None:
                errs.append("%s: дублирующая запись llm-pi-ai с droid-bridge" % name)
            models = provider.get("models")
    if models is None:
        errs.append("%s: нет провайдера droid-bridge в записи llm-pi-ai" % name)
        return None
    if not isinstance(models, list):
        errs.append("%s: droid-bridge.models не список" % name)
        return None
    return models


def _droid_allowlist(records, errs, name):
    routes = None
    for rec in records.get("subagent-model-selection-settings") or []:
        config = rec.get("config") if isinstance(rec.get("config"), dict) else {}
        allowed = config.get("allowedModels")
        if isinstance(allowed, list):
            if routes is not None:
                errs.append(
                    "%s: дублирующая запись subagent-model-selection-settings" % name
                )
            routes = allowed
    if routes is None:
        errs.append(
            "%s: нет config.allowedModels в subagent-model-selection-settings" % name
        )
        return None
    return [
        r.get("model")
        for r in routes
        if isinstance(r, dict) and r.get("provider") == "droid-bridge"
    ]


def check_profile(path, name, cat, report):
    """(5)+(6) C-06: состав/поля droid-bridge в профиле и allowlist == каталог."""
    docs = _load_records(path, report, name)
    if docs is None:
        return None
    records = _records_by_id(docs)
    errs = []
    catalogue = {}
    for model in cat.get("models") or []:
        catalogue[model.get("id")] = model
    models = _droid_models(records, errs, name)
    seen = []
    if models is not None:
        for item in models:
            if not isinstance(item, dict):
                errs.append("%s: элемент models не объект" % name)
                continue
            mid = item.get("id")
            seen.append(mid)
            if mid not in catalogue:
                errs.append("%s: модель вне каталога: %r" % (name, mid))
                continue
            model = catalogue[mid]
            if item.get("name") != model.get("name"):
                errs.append(
                    "%s: %s имя %r != %r"
                    % (name, mid, item.get("name"), model.get("name"))
                )
            if item.get("contextWindow") != model.get("context_window"):
                errs.append(
                    "%s: %s contextWindow %r != %r"
                    % (
                        name,
                        mid,
                        item.get("contextWindow"),
                        model.get("context_window"),
                    )
                )
            if item.get("maxTokens") != model.get("max_tokens"):
                errs.append(
                    "%s: %s maxTokens %r != %r"
                    % (name, mid, item.get("maxTokens"), model.get("max_tokens"))
                )
            efforts = item.get("reasoningEfforts")
            if not isinstance(efforts, dict) or sorted(efforts.keys()) != sorted(
                model.get("efforts") or []
            ):
                errs.append(
                    "%s: %s reasoningEfforts %r != %r"
                    % (
                        name,
                        mid,
                        sorted((efforts or {}).keys())
                        if isinstance(efforts, dict)
                        else efforts,
                        sorted(model.get("efforts") or []),
                    )
                )
            elif any(value != key for key, value in efforts.items()):
                errs.append(
                    "%s: %s reasoningEfforts значения != ключам: %r"
                    % (name, mid, efforts)
                )
            want_input = (
                ["text", "image"]
                if model.get("images", {}).get("status") == "confirmed"
                else ["text"]
            )
            if item.get("input") != want_input:
                errs.append(
                    "%s: %s input %r != %r" % (name, mid, item.get("input"), want_input)
                )
        if sorted(seen) != sorted(catalogue.keys()) or len(seen) != len(set(seen)):
            errs.append(
                "%s: состав droid-моделей %r != каталог %r"
                % (name, sorted(seen), sorted(catalogue.keys()))
            )
    routes = _droid_allowlist(records, errs, name)
    if routes is not None and routes != [m.get("id") for m in cat.get("models") or []]:
        errs.append(
            "%s: allowlist droid-bridge %r != каталог %r"
            % (name, routes, [m.get("id") for m in cat.get("models") or []])
        )
    opus = [mid for mid in seen if isinstance(mid, str) and "opus" in mid.lower()]
    opus += [
        mid for mid in (routes or []) if isinstance(mid, str) and "opus" in mid.lower()
    ]
    if opus:
        errs.append("%s: opus в droid-секциях: %r" % (name, opus))
    report.add(name, errs, {"models": seen, "allowlist": routes})
    return {"records": records, "docs": docs, "models": models, "allowlist": routes}


def check_default_compat(profiles, cat, report):
    """(7б) AD-029/RW4-003: default-модель профилей против каталога."""
    ids = {m.get("id"): m for m in cat.get("models") or []}
    per_profile = {}
    worst = "not_applicable"
    detail = {"status": worst}
    for name, parsed in profiles.items():
        if not parsed:
            continue
        status, info = "not_applicable", {}
        for rec in parsed["records"].get("agent-default-model") or []:
            config = rec.get("config") if isinstance(rec.get("config"), dict) else {}
            provider = config.get("provider")
            model = config.get("model")
            effort = config.get("reasoningEffort")
            if provider != "droid-bridge":
                status, info = "not_applicable", {"provider": provider, "model": model}
                continue
            model = str(model) if model is not None else ""
            if model not in ids:
                status = "BLOCKED-DEFAULT"
                info = {
                    "reason": "model_not_in_roster",
                    "model": model,
                    "effort": effort,
                    "allowed": sorted(ids.keys()),
                }
            elif effort is not None and effort not in (ids[model].get("efforts") or []):
                status = "BLOCKED-DEFAULT"
                info = {
                    "reason": "effort_not_allowed",
                    "model": model,
                    "effort": effort,
                    "allowed": sorted(ids[model].get("efforts") or []),
                }
            else:
                status, info = (
                    "ok",
                    {"provider": provider, "model": model, "effort": effort},
                )
        per_profile[name] = dict(info, status=status)
        if status == "BLOCKED-DEFAULT":
            worst, detail = "BLOCKED-DEFAULT", dict(info, status=status)
        elif status == "ok" and worst != "BLOCKED-DEFAULT":
            worst, detail = "ok", dict(info, status=status)
    detail["profiles"] = per_profile
    report.add(
        "default_compat",
        []
        if worst != "BLOCKED-DEFAULT"
        else ["default_compat: %s" % json.dumps(detail, ensure_ascii=False)],
        detail,
    )
    report.default_compat = detail


def check_web_dump(dump_arg, cat, report):
    """(8) --web-dump: композитное дерево web (JSON) — провайдер и allowlist."""
    errs = []
    try:
        if dump_arg == "-":
            data = json.load(sys.stdin)
        else:
            with open(dump_arg, "r", encoding="utf-8") as fh:
                data = json.load(fh)
    except (OSError, ValueError) as exc:
        report.add("web_dump", ["dump не читается: %s" % exc])
        return
    found_models, found_routes = [], []

    def walk(node):
        if isinstance(node, dict):
            provider = node.get("droid-bridge")
            if isinstance(provider, dict) and isinstance(provider.get("models"), list):
                found_models.extend(
                    m.get("id") for m in provider["models"] if isinstance(m, dict)
                )
            allowed = node.get("allowedModels")
            if isinstance(allowed, list):
                found_routes.extend(
                    r.get("model")
                    for r in allowed
                    if isinstance(r, dict) and r.get("provider") == "droid-bridge"
                )
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    ids = [m.get("id") for m in cat.get("models") or []]
    if not found_models:
        errs.append("web dump: провайдер droid-bridge с models не найден")
    elif sorted(set(found_models)) != sorted(ids):
        errs.append(
            "web dump: модели %r != каталог %r"
            % (sorted(set(found_models)), sorted(ids))
        )
    if not found_routes:
        errs.append("web dump: allowlist droid-bridge не найден")
    elif sorted(set(found_routes)) != sorted(ids):
        errs.append(
            "web dump: allowlist %r != каталог %r"
            % (sorted(set(found_routes)), sorted(ids))
        )
    report.add(
        "web_dump",
        errs,
        {"models": sorted(set(found_models)), "allowlist": sorted(set(found_routes))},
    )


def check_opus(cat_path, profile_paths, report):
    """(9) opus_refs=0: каталог, droid-секции профилей, allowlist."""
    errs = []
    refs = {}
    try:
        refs["catalogue"] = len(re.findall(r"opus", read_text(cat_path), re.IGNORECASE))
    except OSError as exc:
        errs.append("каталог не читается: %s" % exc)
    for path in profile_paths:
        try:
            text = read_text(path)
        except OSError as exc:
            errs.append("%s не читается: %s" % (path, exc))
            continue
        count = 0
        in_droid = False
        for line in text.split("\n"):
            if DROID_SECTION_RE.match(line):
                in_droid = True
                continue
            if in_droid and re.match(r"^      [A-Za-z0-9._-]+:", line):
                in_droid = False
            if in_droid and re.search(r"opus", line, re.IGNORECASE):
                count += 1
        refs[str(path)] = count
    total = sum(refs.values())
    if total:
        errs.append("opus_refs=%d: %r" % (total, refs))
    report.add("opus_refs", errs, refs)
    report.opus_refs = refs


def check_live_droid(cat, launcher, report):
    """(4) --live-droid: 6 id → --list-tools rc=0, контрольный id rc≠0."""
    errs = []
    info = {"launcher": launcher, "results": {}}
    if not (os.path.isfile(launcher) and os.access(launcher, os.X_OK)):
        report.add(
            "live_droid", ["лончер отсутствует или не исполняем: %s" % launcher], info
        )
        return
    ids = [m.get("id") for m in cat.get("models") or []]
    procs = {}
    for mid in ids + [CONTROL_MODEL]:
        try:
            procs[mid] = subprocess.Popen(
                [launcher, "exec", "-m", mid, "--list-tools"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=dict(os.environ),
            )
        except OSError as exc:
            errs.append("запуск --list-tools не удался: %s: %s" % (mid, exc))
    for mid, proc in procs.items():
        try:
            proc.communicate(timeout=LIVE_TOOLS_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
        info["results"][mid] = proc.returncode
    for mid in ids:
        if info["results"].get(mid) != 0:
            errs.append("--list-tools %s: rc=%r" % (mid, info["results"].get(mid)))
    if info["results"].get(CONTROL_MODEL) == 0:
        errs.append(
            "--list-tools контрольного id %s: rc=0 (ожидался rc≠0)" % CONTROL_MODEL
        )
    report.add("live_droid", errs, info)
    report.live_droid = info


def check_image_census(path, cat, profiles, report):
    """(10) --image-census: класс III, привязка proof к версии/sha бинаря, множества."""
    errs = []
    info = {"path": str(path)}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            census = json.load(fh)
    except (OSError, ValueError) as exc:
        report.add("image_census", ["census не читается: %s" % exc], info)
        return
    confirmed = set(census.get("confirmed") or [])
    per_model = census.get("per_model") or {}
    formats_proven = set(census.get("formats_proven") or [])
    status = {
        m.get("id"): (m.get("images") or {}).get("status")
        for m in cat.get("models") or []
    }
    input_map = {
        m.get("id"): ("image" in (m.get("input") or []))
        for m in cat.get("models") or []
    }
    fleet_confirmed = {mid for mid, st in status.items() if st == "confirmed"}
    info["fleet_confirmed"] = sorted(fleet_confirmed)
    info["census_confirmed"] = sorted(confirmed)
    if fleet_confirmed != confirmed:
        errs.append(
            "множества confirmed fleet/census различаются: %r != %r"
            % (sorted(fleet_confirmed), sorted(confirmed))
        )
    if any(st == "probe" for st in status.values()):
        errs.append("probe в боевом каталоге запрещён")
    for name, parsed in profiles.items():
        if not parsed:
            continue
        advertised = []
        for model in parsed.get("models") or []:
            if isinstance(model, dict) and "image" in (model.get("input") or []):
                advertised.append(model.get("id"))
        info["advertised_" + name] = sorted(advertised)
        if set(advertised) != confirmed:
            errs.append(
                "реклама %s (%r) != census confirmed (%r)"
                % (name, sorted(advertised), sorted(confirmed))
            )
    if not set((cat.get("image_limits") or {}).get("types") or []) <= formats_proven:
        errs.append(
            "image_limits.types ⊄ census.formats_proven: %r"
            % sorted(
                set((cat.get("image_limits") or {}).get("types") or []) - formats_proven
            )
        )
    technical = cat.get("technical_ref") or {}
    binary_path = expand(technical.get("droid_binary_path") or "")
    for model in cat.get("models") or []:
        mid = model.get("id")
        if status.get(mid) != "confirmed":
            if input_map.get(mid):
                errs.append("input image без confirmed: " + str(mid))
            continue
        proof = (model.get("images") or {}).get("proof") or {}
        if proof.get("impl_version") != METHOD_IMPL_VERSIONS.get(proof.get("method")):
            errs.append("proof.impl_version не совпадает с реализацией: " + str(mid))
        if sorted(proof.get("efforts_proven") or []) != sorted(
            model.get("efforts") or []
        ):
            errs.append("класс III (proof.efforts_proven != efforts): " + str(mid))
        pm = per_model.get(mid) or {}
        if pm.get("efforts_missing"):
            errs.append(
                "census.efforts_missing непуст: %s %r"
                % (mid, pm.get("efforts_missing"))
            )
        if sorted((census.get("efforts_proven") or {}).get(mid) or []) != sorted(
            model.get("efforts") or []
        ):
            errs.append("census.efforts_proven != efforts: " + str(mid))
        try:
            live_sha = sha256_file(binary_path)
        except OSError as exc:
            errs.append("бином droid не читается (%s): %s" % (binary_path, exc))
            live_sha = None
        if live_sha and proof.get("droid_binary_sha256") != live_sha:
            errs.append("proof.droid_binary_sha256 != sha файла бинаря: " + str(mid))
        if census.get("droid_binary_sha256") and proof.get(
            "droid_binary_sha256"
        ) != census.get("droid_binary_sha256"):
            errs.append(
                "proof.droid_binary_sha256 != census.droid_binary_sha256: " + str(mid)
            )
        if census.get("droid_version") and proof.get("droid_version") != census.get(
            "droid_version"
        ):
            errs.append("proof.droid_version != census.droid_version: " + str(mid))
        if census.get("census_sha256") and proof.get("census_sha256") != census.get(
            "census_sha256"
        ):
            errs.append("proof.census_sha256 != census.census_sha256: " + str(mid))
        if proof.get("census_sha256") and proof.get("census_sha256") != sha256_file(
            path
        ):
            errs.append("proof.census_sha256 != sha файла census: " + str(mid))
    report.add("image_census", errs, info)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Проверка каталога Droid-флота и профилей DSH (C-07)."
    )
    parser.add_argument("--catalogue", default=str(DEFAULT_CATALOGUE))
    parser.add_argument("--desktop", default=str(DEFAULT_DESKTOP))
    parser.add_argument("--web", default=str(DEFAULT_WEB))
    parser.add_argument("--efforts", default=str(DEFAULT_EFFORTS))
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--web-dump", default=None)
    parser.add_argument("--live-droid", action="store_true")
    parser.add_argument("--image-census", default=None)
    args = parser.parse_args(argv)

    report = Report()
    report.policy = {}
    report.default_compat = {"status": "not_applicable"}
    report.opus_refs = {}
    try:
        with open(args.catalogue, "r", encoding="utf-8") as fh:
            cat = json.load(fh)
    except (OSError, ValueError) as exc:
        report.fail("catalogue", "каталог не читается: %s" % exc)
        cat = {}
    else:
        check_catalogue(cat, report)
        cat = droid_scope(
            cat
        )  # дальше — проверки Droid-флота и профилей DSH (Muse — вне их области)
        check_policy(cat, args.policy, report)
        check_efforts(cat, args.efforts, report)
        profiles = {}
        profiles["desktop"] = check_profile(args.desktop, "desktop", cat, report)
        profiles["web"] = check_profile(args.web, "web", cat, report)
        check_default_compat(profiles, cat, report)
        check_opus(args.catalogue, [args.desktop, args.web], report)
        if args.web_dump is not None:
            check_web_dump(args.web_dump, cat, report)
        if args.live_droid:
            launcher = os.environ.get("DROID_LAUNCHER") or str(DEFAULT_LAUNCHER)
            check_live_droid(cat, launcher, report)
        if args.image_census is not None:
            check_image_census(args.image_census, cat, profiles, report)

    out = {
        "ok": report.ok,
        "checks": report.checks,
        "policy": getattr(report, "policy", {}),
        "default_compat": getattr(report, "default_compat", {}),
        "opus_refs": getattr(report, "opus_refs", {}),
    }
    if getattr(report, "live_droid", None):
        out["live_droid"] = report.live_droid
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
