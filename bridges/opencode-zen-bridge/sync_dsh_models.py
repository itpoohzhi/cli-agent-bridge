#!/usr/bin/env python3
"""Синхронизация каталога бесплатных моделей OpenCode Zen: мост, кэш CLI и профили DSH.

Единственный писатель четырёх артефактов (stdlib, Python 3.9):

* `~/.cache/opencode/models.json` — полный `api.json`, его читает `opencode run`
  через `OPENCODE_MODELS_PATH` (и `--standalone`);
* `<мост>/state/zen-catalog.json` — производный каталог, его читает `server.py`;
* управляемые регионы `~/.dsh/profiles/{desktop,web}/cordis.patch.yml`: карточки
  провайдера `opencode-zen-bridge` и список `allowedModels`;
* `agent-default-model` desktop — только если его модель выпала из каталога.

Правки профилей хирургические: регионы обёрнуты маркерами
`# >>> zen-autosync:<имя> (managed) >>>` / `# <<< zen-autosync:<имя> <<<`;
всё вне регионов (включая теги `!!js`) сохраняется побайтно. Перед записью —
бэкап в `~/work/backups/<дата>-zen-autosync/`, запись атомарна (`os.replace`),
после записи `dsh --profile web --dump-config` сверяется с каталогом; при провале
профили восстанавливаются из бэкапа.

Коды возврата: 0 — готово или `no changes`; 1 — непредвиденная ошибка; 2 — нет данных
(api.json недоступен или невалиден), ничего не записано; 3 — защитный порог
(пустой каталог или сокращение > 50 %), ничего не записано; 4 — профиль не прошёл
проверку, восстановлен из бэкапа. Коды `--verify-dump`: 0 — совпало, 1 — расхождение.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import zen_catalog as zc

API_URL = "https://models.opencode.ai/api.json"
ZEN_URL = "http://127.0.0.1:10830/zen/v1/models"
API_TIMEOUT_S = 15
ZEN_TIMEOUT_S = 5
DUMP_TIMEOUT_S = 90
MAX_BODY_BYTES = 64 * 1024 * 1024
USER_AGENT = "dsh-zen-autosync/1.0"

PROVIDER = "opencode-zen-bridge"
REGION_MODELS = "models"
REGION_ALLOWED = "allowed"
REGION_NAMES = (REGION_MODELS, REGION_ALLOWED)

BRIDGE_DIR = Path(__file__).resolve().parent

EXIT_OK, EXIT_ERROR, EXIT_NO_DATA, EXIT_SAFETY, EXIT_PROFILE = 0, 1, 2, 3, 4


class SyncError(Exception):
    """Нарушение гарда: запись профиля запрещена."""


class FetchError(Exception):
    """Источник каталога недоступен или вернул мусор."""


class Paths(object):
    """Все пути синхронизатора; тесты подменяют их на временные."""

    def __init__(self, bridge_dir: Optional[Path] = None, home: Optional[Path] = None) -> None:
        home = home or Path.home()
        bridge_dir = bridge_dir or BRIDGE_DIR
        self.state_dir = bridge_dir / "state"
        self.catalog = self.state_dir / "zen-catalog.json"
        self.lock = self.state_dir / "sync.lock"
        self.models_json = Path(os.environ.get("OPENCODE_MODELS_PATH") or home / ".cache" / "opencode" / "models.json")
        self.profiles: Dict[str, Path] = {
            name: home / ".dsh" / "profiles" / name / "cordis.patch.yml" for name in ("desktop", "web")
        }
        self.backup_root = home / "work" / "backups"
        self.dsh_bin: Optional[Path] = home / ".local" / "bin" / "dsh"


# --------------------------------------------------------------------------- сеть и файлы

def fetch_bytes(url: str, timeout: float, use_proxy: bool) -> bytes:
    handlers: List[Any] = [] if use_proxy else [urllib.request.ProxyHandler({})]
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            data = response.read(MAX_BODY_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise FetchError("%s: %s" % (url, exc))
    if len(data) > MAX_BODY_BYTES:
        raise FetchError("%s: response too large" % url)
    return data


def atomic_write(path: Path, data: bytes, mode: Optional[int] = None) -> None:
    """tempfile в том же каталоге + `os.replace`: читатель видит либо старый, либо новый файл."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        try:
            mode = path.stat().st_mode & 0o777
        except OSError:
            mode = 0o644
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".%s." % path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, str(path))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def read_bytes(path: Path) -> Optional[bytes]:
    try:
        return path.read_bytes()
    except OSError:
        return None


# --------------------------------------------------------------------------- рендер YAML

def _yaml_scalar(value: str) -> str:
    """Значение уровня: булево-подобные слова YAML 1.1 берём в кавычки."""
    return json.dumps(value) if value in ("off", "on", "yes", "no", "true", "false", "null") else value


def card_lines(indent: int, model_id: str, name: str, entry: zc.Entry) -> List[str]:
    """Карточка модели в стиле действующих профилей (имя — JSON-строка: экранирование для YAML)."""
    if not zc.valid_model_id(model_id):
        raise SyncError("invalid model id %r" % (model_id,))
    cordis = entry["cordis"]
    pad = " " * indent
    efforts = ", ".join("%s: %s" % (k, _yaml_scalar(v)) for k, v in cordis["reasoningEfforts"].items())
    return [
        "%s- id: %s" % (pad, model_id),
        "%s  name: %s" % (pad, json.dumps(name)),
        "%s  contextWindow: %d" % (pad, cordis["contextWindow"]),
        "%s  maxTokens: %d" % (pad, cordis["maxTokens"]),
        "%s  input: [ %s ]" % (pad, ", ".join(cordis["input"])),
        "%s  reasoningEfforts: { %s }" % (pad, efforts),
    ]


def alias_ids(state: Dict[str, Any]) -> List[str]:
    """Id скрытых карточек: статические алиасы и retired; активные модели не затрагиваются."""
    active = set(state["active"])
    ids = (set(zc.DEPRECATED_MODEL_ALIASES) | set(state.get("retired") or [])) & set(state["aliases"])
    return sorted(i for i in ids if i not in active and zc.valid_model_id(i))


def render_models_region(indent: int, state: Dict[str, Any]) -> List[str]:
    by_id = {e["id"]: e for e in state["models"]}
    lines: List[str] = []
    for entry in sorted(state["models"], key=lambda e: e["id"]):
        lines.extend(card_lines(indent, entry["id"], zc.card_name(entry), entry))
    for old in alias_ids(state):
        target = state["aliases"][old]
        if target in by_id:
            lines.extend(card_lines(indent, old, "%s (deprecated -> %s)" % (old, target), by_id[target]))
    return lines


def render_allowed_region(indent: int, state: Dict[str, Any]) -> List[str]:
    pad = " " * indent
    lines: List[str] = []
    for model_id in sorted(state["active"]):
        lines.append("%s- provider: %s" % (pad, PROVIDER))
        lines.append("%s  model: %s" % (pad, model_id))
    return lines


# --------------------------------------------------------------------------- хирургия по тексту

_START_RE = re.compile(r"^(\s*)# >>> zen-autosync:([a-z]+) \(managed\) >>>\s*$")
_END_RE = re.compile(r"^(\s*)# <<< zen-autosync:([a-z]+) <<<\s*$")
_PROVIDER_KEY_RE = re.compile(r"^(\s*)%s:\s*$" % re.escape(PROVIDER))
_MODELS_KEY_RE = re.compile(r"^(\s*)models:\s*$")
_ALLOWED_PROVIDER_RE = re.compile(r"^(\s*)- provider: %s\s*$" % re.escape(PROVIDER))
_ALLOWED_MODEL_RE = re.compile(r"^(\s*)model: \S+\s*$")
_DEFAULT_ID_RE = re.compile(r"^- id: agent-default-model\s*$")
_DEFAULT_PROVIDER_RE = re.compile(r"^(\s+)provider: %s\s*(#.*)?$" % re.escape(PROVIDER))
_DEFAULT_MODEL_RE = re.compile(r"^(\s+model: )(\S+)(\s*(#.*)?)$")


class Region(object):
    """Управляемый регион: индексы строк-маркеров (если есть) и содержимого [first, last)."""

    def __init__(self, name: str, indent: int, first: int, last: int,
                 start_marker: Optional[int], end_marker: Optional[int]) -> None:
        self.name = name
        self.indent = indent
        self.first = first
        self.last = last
        self.start_marker = start_marker
        self.end_marker = end_marker

    def span(self) -> Tuple[int, int]:
        """Строки региона вместе с маркерами (для сравнения «вне регионов»), [from, to)."""
        if self.start_marker is not None and self.end_marker is not None:
            return self.start_marker, self.end_marker + 1
        return self.first, self.last


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_blank_or_comment(line: str) -> bool:
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def find_marked(lines: Sequence[str]) -> Dict[str, Region]:
    found: Dict[str, Region] = {}
    open_name: Optional[str] = None
    open_idx = -1
    for idx, line in enumerate(lines):
        start, end = _START_RE.match(line), _END_RE.match(line)
        if start:
            name = start.group(2)
            if open_name is not None or name not in REGION_NAMES or name in found:
                raise SyncError("unexpected region start %r at line %d" % (name, idx + 1))
            open_name, open_idx = name, idx
        elif end:
            name = end.group(2)
            if open_name != name:
                raise SyncError("unexpected region end %r at line %d" % (name, idx + 1))
            found[name] = Region(name, _indent_of(lines[open_idx]), open_idx + 1, idx, open_idx, idx)
            open_name = None
    if open_name is not None:
        raise SyncError("region %r is not closed" % open_name)
    return found


def locate_models(lines: Sequence[str]) -> Region:
    """Содержимое `models:` провайдера `opencode-zen-bridge` (первый запуск, без маркеров)."""
    hits = [i for i, line in enumerate(lines) if _PROVIDER_KEY_RE.match(line)]
    if len(hits) != 1:
        raise SyncError("provider block %r found %d times (need exactly 1)" % (PROVIDER, len(hits)))
    provider_idx = hits[0]
    provider_indent = _indent_of(lines[provider_idx])
    models_idx: Optional[int] = None
    block_end = len(lines)
    for idx in range(provider_idx + 1, len(lines)):
        line = lines[idx]
        if _is_blank_or_comment(line):
            continue
        if _indent_of(line) <= provider_indent:
            block_end = idx
            break
        if _MODELS_KEY_RE.match(line) and _indent_of(line) == provider_indent + 2:
            if models_idx is not None:
                raise SyncError("provider %r has several models: blocks" % PROVIDER)
            models_idx = idx
    if models_idx is None:
        raise SyncError("provider %r has no models: block" % PROVIDER)
    models_indent = _indent_of(lines[models_idx])
    last = block_end
    for idx in range(models_idx + 1, block_end):
        if not _is_blank_or_comment(lines[idx]) and _indent_of(lines[idx]) <= models_indent:
            last = idx
            break
    while last > models_idx + 1 and (
            not lines[last - 1].strip()
            or (lines[last - 1].lstrip().startswith("#") and _indent_of(lines[last - 1]) <= models_indent)):
        last -= 1
    return Region(REGION_MODELS, models_indent + 2, models_idx + 1, last, None, None)


def locate_allowed(lines: Sequence[str]) -> Optional[Region]:
    """Непрерывная группа `- provider: opencode-zen-bridge` / `model: ...` в `allowedModels`."""
    runs: List[Tuple[int, int, int]] = []
    idx = 0
    while idx < len(lines):
        head = _ALLOWED_PROVIDER_RE.match(lines[idx])
        if head and idx + 1 < len(lines) and _ALLOWED_MODEL_RE.match(lines[idx + 1]):
            first, indent = idx, _indent_of(lines[idx])
            while (idx + 1 < len(lines) and _ALLOWED_PROVIDER_RE.match(lines[idx])
                   and _ALLOWED_MODEL_RE.match(lines[idx + 1])
                   and _indent_of(lines[idx]) == indent):
                idx += 2
            runs.append((first, idx, indent))
        else:
            idx += 1
    if not runs:
        return None
    if len(runs) != 1:
        raise SyncError("allowedModels: %d separate groups of %r (need exactly 1)" % (len(runs), PROVIDER))
    first, last, indent = runs[0]
    return Region(REGION_ALLOWED, indent, first, last, None, None)


def locate_regions(lines: Sequence[str]) -> Dict[str, Region]:
    regions = find_marked(lines)
    if REGION_MODELS not in regions:
        regions[REGION_MODELS] = locate_models(lines)
    if REGION_ALLOWED not in regions:
        located = locate_allowed(lines)
        if located is not None:
            regions[REGION_ALLOWED] = located
    return regions


def _marker_lines(name: str, indent: int) -> Tuple[str, str]:
    pad = " " * indent
    return ("%s# >>> zen-autosync:%s (managed) >>>" % (pad, name), "%s# <<< zen-autosync:%s <<<" % (pad, name))


def _default_model_line(lines: Sequence[str]) -> Optional[Tuple[int, Any]]:
    """Строка `model:` блока `agent-default-model`, если его провайдер — `opencode-zen-bridge`."""
    for idx, line in enumerate(lines):
        if not _DEFAULT_ID_RE.match(line):
            continue
        end = len(lines)
        for j in range(idx + 1, len(lines)):
            if lines[j].startswith("- "):
                end = j
                break
        if not any(_DEFAULT_PROVIDER_RE.match(lines[j]) for j in range(idx + 1, end)):
            return None
        for j in range(idx + 1, end):
            match = _DEFAULT_MODEL_RE.match(lines[j])
            if match:
                return j, match
        return None
    return None


def _default_model_edit(lines: List[str], state: Dict[str, Any]) -> None:
    """Если модель по умолчанию выпала из каталога — подменить её целью алиаса."""
    found = _default_model_line(lines)
    if found is None:
        return
    idx, match = found
    current = match.group(2).strip("\"'")
    if current in state["active"]:
        return
    target, _ = zc.resolve_model(current, state["active"], state["aliases"])
    target = target or zc.pick_alias_target(state["active"])
    if target in state["active"] and zc.valid_model_id(target):
        lines[idx] = "%s%s%s" % (match.group(1), target, match.group(3))


def _outside(lines: Sequence[str], regions: Dict[str, Region]) -> List[str]:
    """Текст вне регионов; значение `model:` у `agent-default-model` не сравнивается (его меняет синк)."""
    out: List[str] = []
    cursor = 0
    for start, end in sorted(r.span() for r in regions.values()):
        out.extend(lines[cursor:start])
        cursor = end
    out.extend(lines[cursor:])
    found = _default_model_line(out)
    if found is not None:
        idx, match = found
        out[idx] = "%s<default>%s" % (match.group(1), match.group(3))
    return out


def render_profile(text: str, state: Dict[str, Any]) -> str:
    """Новый текст профиля с обновлёнными регионами; `SyncError`, если гард нарушен."""
    if "\r" in text:
        raise SyncError("CRLF line endings are not supported")
    old_lines = text.split("\n")
    old_regions = locate_regions(old_lines)
    if REGION_MODELS not in old_regions:
        raise SyncError("models region not found")
    for region in old_regions.values():
        if any("!!js" in ln for ln in old_lines[region.first:region.last]):
            raise SyncError("region %r contains !!js; refusing to overwrite" % region.name)

    new_lines = list(old_lines)
    _default_model_edit(new_lines, state)

    # замена регионов с конца файла: индексы ранних регионов остаются верными
    for region in sorted(old_regions.values(), key=lambda r: r.first, reverse=True):
        if region.name == REGION_MODELS:
            body = render_models_region(region.indent, state)
        else:
            body = render_allowed_region(region.indent, state)
        start_marker, end_marker = _marker_lines(region.name, region.indent)
        new_lines[region.span()[0]:region.span()[1]] = [start_marker] + body + [end_marker]

    new_text = "\n".join(new_lines)
    new_regions = find_marked(new_lines)
    if set(new_regions) != set(old_regions):
        raise SyncError("region set changed after render")
    if text.count("!!js") != new_text.count("!!js"):
        raise SyncError("!!js tag count changed")
    old_outside = _outside(old_lines, old_regions)
    new_outside = _outside(new_lines, new_regions)
    if old_outside != new_outside:
        raise SyncError("bytes outside managed regions changed")
    return new_text


# --------------------------------------------------------------------------- проверка дампа dsh

def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def parse_dump_cards(dump: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Карточки `opencode-zen-bridge` и zen-пары `allowedModels` из вывода `dsh --dump-config`."""
    lines = dump.splitlines()
    hits = [i for i, ln in enumerate(lines) if _PROVIDER_KEY_RE.match(ln)]
    if len(hits) != 1:
        raise SyncError("dump: provider block %r found %d times" % (PROVIDER, len(hits)))
    base = _indent_of(lines[hits[0]])
    cards: Dict[str, Dict[str, Any]] = {}
    current: Optional[Dict[str, Any]] = None
    mode = ""
    in_models = False
    for line in lines[hits[0] + 1:]:
        if not line.strip():
            continue
        indent = _indent_of(line)
        if indent <= base:
            break
        text = line.strip()
        if indent == base + 2:
            in_models = text == "models:"
            continue
        if not in_models:
            continue
        if indent == base + 4 and text.startswith("- id: "):
            current = {"id": _unquote(text[len("- id: "):]), "input": [], "reasoningEfforts": {}}
            cards[current["id"]] = current
            mode = ""
        elif current is not None and indent == base + 6:
            key, _, value = text.partition(":")
            mode = key if key in ("input", "reasoningEfforts") and not value.strip() else ""
            if not mode:
                current[key] = _unquote(value)
        elif current is not None and mode == "input" and text.startswith("- "):
            current["input"].append(_unquote(text[2:]))
        elif current is not None and mode == "reasoningEfforts":
            key, _, value = text.partition(":")
            current["reasoningEfforts"][_unquote(key)] = _unquote(value)
    allowed: List[str] = []
    for idx, line in enumerate(lines):
        if _ALLOWED_PROVIDER_RE.match(line) and idx + 1 < len(lines):
            match = re.match(r"^\s*model:\s*(\S+)\s*$", lines[idx + 1])
            if match:
                allowed.append(_unquote(match.group(1)))
    return cards, allowed


def verify_dump(dump: str, state: Dict[str, Any]) -> List[str]:
    """Расхождения дампа с каталогом; пустой список — карточки Zen совпали с эталоном."""
    try:
        cards, allowed = parse_dump_cards(dump)
    except SyncError as exc:
        return [str(exc)]
    problems: List[str] = []
    for entry in state["models"]:
        card = cards.get(entry["id"])
        if card is None:
            problems.append("card %s is missing" % entry["id"])
            continue
        cordis = entry["cordis"]
        actual = (card.get("contextWindow"), card.get("maxTokens"), card["input"], card["reasoningEfforts"])
        expected = (str(cordis["contextWindow"]), str(cordis["maxTokens"]), list(cordis["input"]),
                    dict(cordis["reasoningEfforts"]))
        if actual != expected:
            problems.append("card %s differs: %r != %r" % (entry["id"], actual, expected))
    extra = set(cards) - set(state["active"]) - set(alias_ids(state))
    if extra:
        problems.append("unexpected cards: %s" % ", ".join(sorted(extra)))
    if sorted(allowed) != sorted(state["active"]):
        problems.append("allowedModels differs: %s" % ", ".join(sorted(set(allowed) ^ set(state["active"]))))
    return problems


# --------------------------------------------------------------------------- шаги синхронизации

def parse_api(raw: bytes) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Проверить `api.json`: JSON, `opencode.models`, хотя бы одна активная free-модель."""
    try:
        api = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise FetchError("api.json is not valid JSON: %s" % exc)
    models = zc.api_models(api)
    if not any(zc.is_active_free(m) for m in models.values()):
        raise FetchError("api.json has no active free models in opencode.models")
    return api, models


def _same_catalog(left: Optional[Dict[str, Any]], right: Dict[str, Any]) -> bool:
    if left is None:
        return False
    keys = ("models", "aliases", "retired", "degraded")
    return all(left.get(k) == right.get(k) for k in keys)


def build_state(models: Dict[str, Any], zen: Optional[set], previous: Optional[Dict[str, Any]]
                ) -> Tuple[Dict[str, Any], Optional[str]]:
    """Новое состояние и причина блокировки (safety rail), если она есть."""
    prev_active = list(previous["active"]) if previous else []
    prev_retired = list(previous.get("retired") or []) if previous else []
    degraded = not zen
    available = set(zen) if zen else set(prev_active or [e["id"] for e in zc.STATIC_FALLBACK_CATALOG])
    entries = zc.build_catalog(models, available)
    active = [e["id"] for e in entries]
    violation = zc.shrink_violation(active, prev_active)
    aliases, retired = zc.derive_aliases(models, active, prev_active, prev_retired)
    generated = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    state = zc.make_state(entries, aliases, retired, degraded=degraded, generated_at=generated,
                          api_fetched=True, zen_fetched=not degraded)
    return state, violation


def backup_profile(paths: Paths, name: str, source: Path, stamp: str) -> Path:
    directory = paths.backup_root / ("%s-zen-autosync" % time.strftime("%Y-%m-%d"))
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("%s-%s-cordis.patch.yml" % (stamp, name))
    shutil.copy2(str(source), str(target))
    return target


def run_dump(paths: Paths) -> Optional[str]:
    """`dsh --profile web --dump-config`; `None`, если dsh недоступен (проверка пропускается)."""
    if paths.dsh_bin is None or not os.access(str(paths.dsh_bin), os.X_OK):
        return None
    try:
        result = subprocess.run([str(paths.dsh_bin), "--profile", "web", "--dump-config"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=DUMP_TIMEOUT_S,
                                universal_newlines=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise SyncError("dsh --dump-config failed to run: %s" % exc)
    if result.returncode != 0:
        raise SyncError("dsh --dump-config rc=%d: %s" % (result.returncode, result.stderr.strip()[-300:]))
    return result.stdout


def sync_profiles(paths: Paths, state: Dict[str, Any], dry_run: bool, out: Any) -> Tuple[int, int]:
    """Обновить профили; вернуть (код возврата 0/4, число изменённых профилей)."""
    planned: Dict[str, Tuple[Path, bytes, str]] = {}
    for name, path in paths.profiles.items():
        raw = read_bytes(path)
        if raw is None:
            out("profile %s: file not found, skipped" % name)
            continue
        try:
            new_text = render_profile(raw.decode("utf-8"), state)
        except (SyncError, UnicodeDecodeError) as exc:
            out("profile %s: refused, nothing written: %s" % (name, exc))
            return EXIT_PROFILE, 0
        if new_text.encode("utf-8") != raw:
            planned[name] = (path, raw, new_text)
    if not planned:
        return EXIT_OK, 0
    if dry_run:
        for name in sorted(planned):
            out("dry-run: would update profile %s" % name)
        return EXIT_OK, len(planned)

    stamp = time.strftime("%H%M%S")
    backups = {name: backup_profile(paths, name, item[0], stamp) for name, item in planned.items()}
    for name, (path, _raw, new_text) in planned.items():
        atomic_write(path, new_text.encode("utf-8"))
        out("updated profile %s (backup: %s)" % (name, backups[name]))
    try:
        dump = run_dump(paths)
        problems = verify_dump(dump, state) if dump is not None else []
        if dump is None:
            out("warning: dsh not found, post-check skipped")
    except SyncError as exc:
        problems = [str(exc)]
    if problems:
        for name, (path, raw, _text) in planned.items():
            atomic_write(path, raw)
        out("post-check failed, profiles restored from backup: %s" % "; ".join(problems[:5]))
        return EXIT_PROFILE, len(planned)
    return EXIT_OK, len(planned)


def run_sync(args: argparse.Namespace, paths: Paths, out: Any = None) -> int:
    out = out or (lambda message: print(message, flush=True))
    dry_run = bool(args.dry_run or args.print_golden)
    if dry_run:
        return _sync_locked(args, paths, dry_run, out)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(paths.lock), os.O_CREAT | os.O_RDWR, 0o644)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            out("already running")
            return EXIT_OK
        return _sync_locked(args, paths, dry_run, out)
    finally:
        os.close(lock_fd)


def _sync_locked(args: argparse.Namespace, paths: Paths, dry_run: bool, out: Any) -> int:
    try:
        api_raw = fetch_bytes(args.api_url, API_TIMEOUT_S, use_proxy=True)
        _api, models = parse_api(api_raw)
    except FetchError as exc:
        out("api.json unavailable, nothing written: %s" % exc)
        return EXIT_NO_DATA
    zen: Optional[set] = None
    try:
        zen = zc.zen_ids(json.loads(fetch_bytes(args.zen_url, ZEN_TIMEOUT_S, use_proxy=False).decode("utf-8")))
    except (FetchError, UnicodeDecodeError, ValueError) as exc:
        out("zen list unavailable, using previous catalog (degraded): %s" % exc)

    previous = zc.load_state_file(paths.catalog)
    state, violation = build_state(models, zen, previous)
    if violation:
        out("safety rail: %s; nothing written" % violation)
        return EXIT_SAFETY
    if args.print_golden:
        for entry in state["models"]:
            out(zc.golden_line(entry))
        return EXIT_OK

    changed = False
    if read_bytes(paths.models_json) != api_raw:
        changed = True
        if dry_run:
            out("dry-run: would update %s" % paths.models_json)
        else:
            atomic_write(paths.models_json, api_raw)
            out("updated %s" % paths.models_json)
    if not _same_catalog(previous, state):
        changed = True
        if dry_run:
            out("dry-run: would update %s (%d models)" % (paths.catalog, len(state["active"])))
        else:
            atomic_write(paths.catalog, (json.dumps(state, ensure_ascii=False, indent=1) + "\n").encode("utf-8"), 0o644)
            out("updated %s (%d models)" % (paths.catalog, len(state["active"])))
    code = EXIT_OK
    if not args.no_profiles:
        code, touched = sync_profiles(paths, state, dry_run, out)
        changed = changed or touched > 0
    if code == EXIT_OK and not changed:
        out("no changes")
    return code


def run_verify_dump(path: str, paths: Paths, out: Any) -> int:
    try:
        dump = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        out("cannot read dump: %s" % exc)
        return 1
    state = zc.load_state_file(paths.catalog) or zc.fallback_state()
    problems = verify_dump(dump, state)
    for problem in problems:
        out("MISMATCH: %s" % problem)
    if not problems:
        out("dump matches catalog (%d models)" % len(state["models"]))
    return 1 if problems else 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Синхронизация каталога Zen: мост, кэш CLI, профили DSH")
    parser.add_argument("--dry-run", action="store_true", help="ничего не писать, показать план")
    parser.add_argument("--print-golden", action="store_true", help="напечатать эталонную таблицу и выйти (без записи)")
    parser.add_argument("--verify-dump", metavar="FILE", help="сверить вывод `dsh --dump-config` с каталогом")
    parser.add_argument("--api-url", default=API_URL, help="источник api.json (по умолчанию models.opencode.ai)")
    parser.add_argument("--zen-url", default=ZEN_URL, help="источник списка Zen (по умолчанию :10830)")
    parser.add_argument("--no-profiles", action="store_true", help="не трогать cordis.patch.yml")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None, paths: Optional[Paths] = None) -> int:
    args = parse_args(argv)
    paths = paths or Paths()
    out = lambda message: print(message, flush=True)
    try:
        if args.verify_dump:
            return run_verify_dump(args.verify_dump, paths, out)
        return run_sync(args, paths, out)
    except (SyncError, OSError) as exc:
        out("error: %s" % exc)
        return EXIT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
