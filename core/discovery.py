"""Discovery моделей провайдера (architecture-spec §4.2).

`discover(manifest, env=...)` возвращает :class:`DiscoveryResult` и **никогда не бросает**:
любая ошибка превращается в slug в поле ``error`` (класс I, без пользовательских данных),
``model_ids`` при ошибке пуст. Вызывающий обязан трактовать ``error`` как «не знаю», а не
как «модели исчезли» — набор моделей при этом не меняется.

Методы (``manifest.discovery.method``):

* ``http``  — ``GET <bridge.base_url><discovery.http.path>`` с Bearer-ключом из env-переменной
  ``bridge.api_key_env``; ``ProxyHandler({})``, без редиректов, лимит тела;
* ``cli``   — ``render_argv`` -> ``Popen`` в собственном PGID (``start_new_session``),
  ``strip_bridge_secrets``, ``cwd`` = свежий tempdir; таймаут — скользящее окно
  неактивности (каждый полученный чанк сдвигает дедлайн), ``killpg`` TERM -> KILL;
* ``static`` — список из манифеста.

Затем ``include``/``exclude`` (glob, ``fnmatch``; пустой ``include`` = всё; ``exclude`` после
``include``; совпадение с исходным или каноническим id) и ``canonical_id``
(``strip_suffixes`` + точная карта). Канонические id с суффиксом ``-free`` отбрасываются
всегда — глобальный инвариант, не настраивается.

Эксплуатационные параметры (env, безопасные дефолты):
``BRIDGE_DISCOVERY_MAX_BYTES`` (1 MiB), ``BRIDGE_DISCOVERY_SAFETY_CAP_S`` (предохранитель
CLI-прогона, 60), ``BRIDGE_DISCOVERY_KILL_GRACE_S`` (пауза TERM -> KILL, 2),
``BRIDGE_DISCOVERY_MAX_WORKERS`` (параллелизм `discover_all`, 8),
``BRIDGE_DISCOVERY_CACHE_ENABLED`` (1), ``BRIDGE_STATE_DIR`` (каталог состояния),
``BRIDGE_DIRECT_ARG_PATTERN`` (допустимый вид id).

Модуль не содержит имён вендоров/моделей и эвристик по семействам.
"""

from __future__ import annotations

import concurrent.futures
import fcntl
import fnmatch
import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from core.backend_adapter import strip_bridge_secrets
from core.param_adapter import resolve_state_dir
from core.provider_manifest import (
    DEFAULT_ARG_PATTERN,
    ManifestError,
    ProviderManifest,
    executable_allowed,
    render_argv,
)

DEFAULT_MAX_BYTES = 1 << 20
DEFAULT_SAFETY_CAP_S = 60.0
DEFAULT_KILL_GRACE_S = 2.0
DEFAULT_MAX_WORKERS = 8
FREE_SUFFIX = "-free"
NO_FINGERPRINT_SEED = "no-fingerprint"
CACHE_FILE = "discovery-cache.json"
CACHE_SCHEMA = 1
_TRUE = ("1", "true", "yes", "on")
_READ_CHUNK = 65536
_POLL_INTERVAL_S = 0.05
_VERSION_MAX_CHARS = 256

Clock = Callable[[], float]


@dataclass(frozen=True)
class DiscoveryResult:
    """Итог discovery одного провайдера."""

    provider_id: str
    fingerprint_sha256: str
    model_ids: Tuple[str, ...] = ()
    meta: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


class _DiscoveryFailure(Exception):
    """Внутренняя ошибка с slug'ом класса I (наружу не выходит)."""

    def __init__(self, slug: str) -> None:
        super().__init__(slug)
        self.slug = slug


# ---- env ----------------------------------------------------------------------------


def _env_num(
    env: Mapping[str, str], name: str, default: float, *, minimum: float = 0.0
) -> float:
    raw = env.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > minimum else default


def max_bytes(env: Mapping[str, str]) -> int:
    return int(_env_num(env, "BRIDGE_DISCOVERY_MAX_BYTES", float(DEFAULT_MAX_BYTES)))


def _safety_cap_s(env: Mapping[str, str]) -> float:
    return _env_num(env, "BRIDGE_DISCOVERY_SAFETY_CAP_S", DEFAULT_SAFETY_CAP_S)


def _kill_grace_s(env: Mapping[str, str]) -> float:
    return _env_num(env, "BRIDGE_DISCOVERY_KILL_GRACE_S", DEFAULT_KILL_GRACE_S)


def _max_workers(env: Mapping[str, str]) -> int:
    return max(
        1,
        int(_env_num(env, "BRIDGE_DISCOVERY_MAX_WORKERS", float(DEFAULT_MAX_WORKERS))),
    )


def _cache_enabled(env: Mapping[str, str]) -> bool:
    return str(env.get("BRIDGE_DISCOVERY_CACHE_ENABLED", "1")).strip().lower() in _TRUE


# ---- jsonpath-lite --------------------------------------------------------------------


def parse_path(path: str) -> Tuple[Tuple[str, bool], ...]:
    """`data[].id` -> (("data", True), ("id", False)); `[]` без имени — итерация по корню."""
    tokens: List[Tuple[str, bool]] = []
    for segment in path.split("."):
        if segment.endswith("[]"):
            tokens.append((segment[:-2], True))
        else:
            tokens.append((segment, False))
    return tuple(tokens)


def extract_values(node: Any, tokens: Sequence[Tuple[str, bool]]) -> List[Any]:
    """Все значения по пути; отсутствующие ветки молча пропускаются."""
    current: List[Any] = [node]
    for name, iterate in tokens:
        nxt: List[Any] = []
        for item in current:
            if name:
                if not isinstance(item, Mapping) or name not in item:
                    continue
                item = item[name]
            if iterate:
                if isinstance(item, list):
                    nxt.extend(item)
            else:
                nxt.append(item)
        current = nxt
    return current


def _split_items(
    doc: Any, id_field: str
) -> List[Tuple[Any, Tuple[Tuple[str, bool], ...]]]:
    """Элементы списка и относительный путь id внутри элемента."""
    tokens = parse_path(id_field)
    last_iter = max((i for i, (_, it) in enumerate(tokens) if it), default=-1)
    if last_iter < 0:
        return [(doc, tokens)]
    items = extract_values(doc, tokens[: last_iter + 1])
    rel = tokens[last_iter + 1 :]
    return [(item, rel) for item in items]


def extract_ids_and_meta(
    doc: Any, id_field: str, meta_fields: Optional[Mapping[str, str]] = None
) -> List[Tuple[str, Dict[str, Any]]]:
    """Пары (id, meta) из документа по jsonpath-lite; id — только строки."""
    found: List[Tuple[str, Dict[str, Any]]] = []
    for item, rel in _split_items(doc, id_field):
        values = extract_values(item, rel) if rel else [item]
        for value in values:
            if not isinstance(value, str) or not value:
                continue
            meta: Dict[str, Any] = {}
            for name, path in (meta_fields or {}).items():
                got = extract_values(item, parse_path(path))
                if got:
                    meta[name] = got[0]
            found.append((value, meta))
    return found


# ---- CLI в собственном PGID ------------------------------------------------------------


def _killpg(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except (OSError, ProcessLookupError):
        pass


def _terminate_group(proc: "subprocess.Popen[bytes]", grace_s: float) -> None:
    """TERM -> пауза -> KILL всей группы (паттерн `run_cli_pgid`)."""
    pgid = proc.pid
    _killpg(pgid, signal.SIGTERM)
    deadline = time.monotonic() + grace_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.01)
    _killpg(pgid, signal.SIGKILL)
    try:
        proc.wait(timeout=max(grace_s, 1.0))
    except subprocess.TimeoutExpired:  # pragma: no cover - SIGKILL не игнорируется
        pass


def run_cli(
    argv: Sequence[str],
    *,
    env: Mapping[str, str],
    idle_timeout_s: float,
    safety_cap_s: Optional[float] = None,
    limit_bytes: Optional[int] = None,
    grace_s: Optional[float] = None,
) -> bytes:
    """Запускает argv в своём PGID и возвращает stdout.

    Скользящее окно: каждый полученный чанк сдвигает дедлайн на `idle_timeout_s`;
    `safety_cap_s` — только предохранитель от бесконечного вывода. Бросает
    `_DiscoveryFailure` со slug'ом: `discovery_cli_unavailable`, `discovery_timeout`,
    `discovery_output_too_large`, `discovery_cli_failed`.
    """
    cap = safety_cap_s if safety_cap_s is not None else _safety_cap_s(env)
    limit = limit_bytes if limit_bytes is not None else max_bytes(env)
    grace = grace_s if grace_s is not None else _kill_grace_s(env)
    child_env = strip_bridge_secrets(dict(env))
    workdir = tempfile.mkdtemp(prefix="bridge-discovery-")
    proc: Optional["subprocess.Popen[bytes]"] = None
    try:
        try:
            proc = subprocess.Popen(
                list(argv),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd=workdir,
                env=child_env,
                start_new_session=True,
                close_fds=True,
            )
        except (OSError, ValueError) as exc:
            raise _DiscoveryFailure("discovery_cli_unavailable") from exc
        assert proc.stdout is not None
        fd = proc.stdout.fileno()
        selector = selectors.DefaultSelector()
        selector.register(fd, selectors.EVENT_READ)
        started = last_activity = time.monotonic()
        buf = bytearray()
        failure: Optional[str] = None
        try:
            while True:
                now = time.monotonic()
                if now - last_activity > idle_timeout_s or now - started > cap:
                    failure = "discovery_timeout"
                    break
                ready = selector.select(timeout=_POLL_INTERVAL_S)
                if ready:
                    chunk = os.read(fd, _READ_CHUNK)
                    if not chunk:
                        break
                    last_activity = time.monotonic()
                    buf.extend(chunk)
                    if len(buf) > limit:
                        failure = "discovery_output_too_large"
                        break
                elif proc.poll() is not None:
                    break
        finally:
            selector.close()
        if failure is not None:
            _terminate_group(proc, grace)
            raise _DiscoveryFailure(failure)
        try:
            proc.wait(timeout=max(idle_timeout_s, 0.1))
        except subprocess.TimeoutExpired:
            _terminate_group(proc, grace)
            raise _DiscoveryFailure("discovery_timeout")
        if proc.returncode != 0:
            raise _DiscoveryFailure("discovery_cli_failed")
        return bytes(buf)
    finally:
        if proc is not None:
            # добиваем возможных потомков группы; вывод уже снят
            _killpg(proc.pid, signal.SIGKILL)
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:  # pragma: no cover
                pass
            if proc.stdout is not None:
                proc.stdout.close()
        shutil.rmtree(workdir, ignore_errors=True)


# ---- HTTP -------------------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


def _http_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


def http_get(
    url: str,
    *,
    api_key: Optional[str],
    timeout_s: float,
    limit_bytes: int,
) -> bytes:
    """GET без прокси и редиректов с лимитом тела; бросает `_DiscoveryFailure`."""
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise _DiscoveryFailure("discovery_http_scheme_invalid")
    request = urllib.request.Request(url, method="GET")
    request.add_header("Accept", "application/json")
    if api_key:
        request.add_header("Authorization", "Bearer " + api_key)
    try:
        with _http_opener().open(request, timeout=timeout_s) as response:
            body = response.read(limit_bytes + 1)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise _DiscoveryFailure("discovery_http_status_%d" % exc.code) from exc
    except TimeoutError as exc:
        raise _DiscoveryFailure("discovery_timeout") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        slug = (
            "discovery_timeout"
            if isinstance(reason, TimeoutError)
            else "discovery_http_failed"
        )
        raise _DiscoveryFailure(slug) from exc
    if len(body) > limit_bytes:
        raise _DiscoveryFailure("discovery_output_too_large")
    return body


# ---- получение «сырых» id ----------------------------------------------------------------

RawModels = List[Tuple[str, Dict[str, Any]]]


def _bridge_url(manifest: ProviderManifest, path: str) -> str:
    bridge = manifest.transport.bridge
    if bridge is None or not bridge.base_url:
        raise _DiscoveryFailure("discovery_base_url_missing")
    return bridge.base_url.rstrip("/") + path


def _api_key(manifest: ProviderManifest, env: Mapping[str, str]) -> Optional[str]:
    bridge = manifest.transport.bridge
    name = bridge.api_key_env if bridge is not None else None
    return env.get(name) if name else None


def _parse_json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise _DiscoveryFailure("discovery_parse_failed") from exc


def _fetch_http(
    manifest: ProviderManifest, env: Mapping[str, str], timeout_s: float
) -> RawModels:
    cfg = manifest.discovery.http or {}
    path = cfg.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise _DiscoveryFailure("discovery_config_invalid")
    body = http_get(
        _bridge_url(manifest, path),
        api_key=_api_key(manifest, env),
        timeout_s=timeout_s,
        limit_bytes=max_bytes(env),
    )
    id_field = cfg.get("id_field") or "data[].id"
    meta_fields = cfg.get("meta_fields") or {}
    return extract_ids_and_meta(_parse_json(body), str(id_field), meta_fields)


def _fetch_cli(
    manifest: ProviderManifest, env: Mapping[str, str], timeout_s: float
) -> RawModels:
    cfg = manifest.discovery.cli or {}
    template = cfg.get("argv")
    if not isinstance(template, list) or not template:
        raise _DiscoveryFailure("discovery_config_invalid")
    try:
        argv = render_argv(template, {}, env=env)
    except ManifestError as exc:
        raise _DiscoveryFailure(exc.slug) from exc
    if not executable_allowed(argv[0], env):
        raise _DiscoveryFailure("discovery_executable_forbidden")
    argv[0] = os.path.expanduser(argv[0])
    output = run_cli(argv, env=env, idle_timeout_s=timeout_s)
    parse = cfg.get("parse") or {}
    fmt = parse.get("format") or "json"
    if fmt == "json":
        doc = _parse_json(output)
        id_field = parse.get("id_field")
        if id_field:
            return extract_ids_and_meta(doc, str(id_field))
        if isinstance(doc, list):
            return [(item, {}) for item in doc if isinstance(item, str) and item]
        raise _DiscoveryFailure("discovery_parse_failed")
    if fmt == "lines":
        regex = None
        line_regex = parse.get("line_regex")
        if line_regex:
            try:
                regex = re.compile(str(line_regex))
            except re.error as exc:
                raise _DiscoveryFailure("discovery_config_invalid") from exc
        found: RawModels = []
        for line in output.decode("utf-8", "replace").splitlines():
            text = line.strip()
            if not text:
                continue
            if regex is not None:
                match = regex.search(text)
                if not match:
                    continue
                text = (match.group(1) if match.groups() else match.group(0)).strip()
            if text:
                found.append((text, {}))
        return found
    raise _DiscoveryFailure("discovery_config_invalid")


def _fetch_raw(
    manifest: ProviderManifest, env: Mapping[str, str], timeout_s: float
) -> RawModels:
    method = manifest.discovery.method
    if method == "http":
        return _fetch_http(manifest, env, timeout_s)
    if method == "cli":
        return _fetch_cli(manifest, env, timeout_s)
    if method == "static":
        return [(item, {}) for item in manifest.discovery.static if item]
    raise _DiscoveryFailure("discovery_config_invalid")


# ---- фильтры и канонические id ------------------------------------------------------------


def canonical_id(raw_id: str, manifest: ProviderManifest) -> str:
    """`strip_suffixes` по порядку, затем точная карта (по исходному id, затем по очищенному)."""
    cfg = manifest.discovery
    if raw_id in cfg.canonical_map:
        return cfg.canonical_map[raw_id]
    value = raw_id
    for suffix in cfg.strip_suffixes:
        if suffix and value.endswith(suffix) and len(value) > len(suffix):
            value = value[: -len(suffix)]
    return cfg.canonical_map.get(value, value)


def _matches_any(patterns: Sequence[str], *candidates: str) -> bool:
    return any(fnmatch.fnmatchcase(c, p) for p in patterns for c in candidates)


def normalize_models(
    raw: RawModels, manifest: ProviderManifest, env: Mapping[str, str]
) -> Tuple[Tuple[str, ...], Dict[str, Dict[str, Any]]]:
    """include/exclude -> canonical_id -> drop `-free` -> дедуп с сохранением порядка."""
    cfg = manifest.discovery
    id_re = re.compile(env.get("BRIDGE_DIRECT_ARG_PATTERN") or DEFAULT_ARG_PATTERN)
    ids: List[str] = []
    meta: Dict[str, Dict[str, Any]] = {}
    for raw_id, item_meta in raw:
        canonical = canonical_id(raw_id, manifest)
        if cfg.include and not _matches_any(cfg.include, raw_id, canonical):
            continue
        if cfg.exclude and _matches_any(cfg.exclude, raw_id, canonical):
            continue
        if canonical.endswith(FREE_SUFFIX) or not id_re.fullmatch(canonical):
            continue
        if canonical in meta:
            continue
        ids.append(canonical)
        meta[canonical] = dict(item_meta)
    return tuple(ids), meta


# ---- fingerprint ----------------------------------------------------------------------------

_BINARY_HASH_CACHE: Dict[Tuple[str, int, int, int], str] = {}
_VERSION_CACHE: Dict[Tuple[Any, ...], Tuple[float, Optional[str]]] = {}


def _file_sha256(path: str) -> Optional[str]:
    """sha256 файла; кэш по (путь, inode, size, mtime_ns)."""
    real = os.path.expanduser(path)
    try:
        st = os.stat(real)
    except OSError:
        return None
    key = (real, st.st_ino, st.st_size, st.st_mtime_ns)
    cached = _BINARY_HASH_CACHE.get(key)
    if cached:
        return cached
    digest = hashlib.sha256()
    try:
        with open(real, "rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
    except OSError:
        return None
    _BINARY_HASH_CACHE[key] = digest.hexdigest()
    return _BINARY_HASH_CACHE[key]


def _version_from_text(text: str) -> Optional[str]:
    text = text.strip()
    if not text:
        return None
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, Mapping) and isinstance(doc.get("version"), str):
        return str(doc["version"])[:_VERSION_MAX_CHARS]
    return text.splitlines()[0][:_VERSION_MAX_CHARS]


def _version(
    manifest: ProviderManifest,
    env: Mapping[str, str],
    timeout_s: float,
    clock: Clock,
    binary_key: Optional[Tuple[Any, ...]],
) -> Optional[str]:
    fp = manifest.fingerprint
    if fp.version_cmd is None and fp.http_version_path is None:
        return fp.version
    key = (
        manifest.provider_id,
        binary_key,
        fp.version_cmd,
        fp.http_version_path,
    )
    now = clock()
    cached = _VERSION_CACHE.get(key)
    if cached is not None and now < cached[0]:
        return cached[1]
    version: Optional[str] = fp.version
    try:
        if fp.version_cmd is not None:
            argv = list(fp.version_cmd)
            if argv and executable_allowed(argv[0], env):
                argv[0] = os.path.expanduser(argv[0])
                out = run_cli(argv, env=env, idle_timeout_s=timeout_s)
                version = _version_from_text(out.decode("utf-8", "replace")) or version
        elif fp.http_version_path:
            body = http_get(
                _bridge_url(manifest, fp.http_version_path),
                api_key=_api_key(manifest, env),
                timeout_s=timeout_s,
                limit_bytes=max_bytes(env),
            )
            version = _version_from_text(body.decode("utf-8", "replace")) or version
    except _DiscoveryFailure:
        version = fp.version
        # неудача не кэшируется: следующая попытка повторит запрос
        return version
    _VERSION_CACHE[key] = (now + manifest.discovery.refresh_interval_s, version)
    return version


def fingerprint_parts(
    manifest: ProviderManifest,
    env: Mapping[str, str],
    *,
    timeout_s: Optional[float] = None,
    clock: Optional[Clock] = None,
) -> Dict[str, Optional[str]]:
    """`binary_path`, `binary_sha256`, `version` провайдера (None — не настроено/недоступно)."""
    fp = manifest.fingerprint
    use_clock = clock or time.time
    limit = timeout_s if timeout_s is not None else manifest.discovery.timeout_s
    binary_sha = fp.binary_sha256
    binary_key: Optional[Tuple[Any, ...]] = None
    if fp.binary_path:
        binary_sha = _file_sha256(fp.binary_path) or binary_sha
        try:
            st = os.stat(os.path.expanduser(fp.binary_path))
            binary_key = (fp.binary_path, st.st_ino, st.st_size, st.st_mtime_ns)
        except OSError:
            binary_key = (fp.binary_path,)
    return {
        "binary_path": fp.binary_path,
        "binary_sha256": binary_sha,
        "version": _version(manifest, env, limit, use_clock, binary_key),
    }


def compute_fingerprint(
    manifest: ProviderManifest,
    env: Mapping[str, str],
    *,
    timeout_s: Optional[float] = None,
    clock: Optional[Clock] = None,
) -> str:
    """sha256 канонического JSON `{binary_sha256, version}` либо константа «нет отпечатка»."""
    fp = manifest.fingerprint
    if not any(
        (
            fp.binary_path,
            fp.binary_sha256,
            fp.version,
            fp.version_cmd,
            fp.http_version_path,
        )
    ):
        return hashlib.sha256(NO_FINGERPRINT_SEED.encode("utf-8")).hexdigest()
    parts = fingerprint_parts(manifest, env, timeout_s=timeout_s, clock=clock)
    payload = json.dumps(
        {"binary_sha256": parts["binary_sha256"], "version": parts["version"]},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---- кэш ----------------------------------------------------------------------------------


def cache_path(env: Mapping[str, str]) -> Path:
    return resolve_state_dir(env) / CACHE_FILE


def _cache_key(provider_id: str, fingerprint: str) -> str:
    return provider_id + "|" + fingerprint


def _read_cache(env: Mapping[str, str]) -> Dict[str, Any]:
    try:
        doc = json.loads(cache_path(env).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entries = doc.get("entries") if isinstance(doc, dict) else None
    return entries if isinstance(entries, dict) else {}


def _source_digest(manifest: ProviderManifest) -> str:
    """Отпечаток способа получения списка: смена argv/path/static инвалидирует кэш."""
    cfg = manifest.discovery
    payload = json.dumps(
        [cfg.method, cfg.http, cfg.cli, list(cfg.static)],
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(
    env: Mapping[str, str],
    provider_id: str,
    fingerprint: str,
    source: str,
    ttl_s: float,
    now: float,
) -> Optional[RawModels]:
    entry = _read_cache(env).get(_cache_key(provider_id, fingerprint))
    if not isinstance(entry, dict) or entry.get("source") != source:
        return None
    fetched = entry.get("fetched_at")
    models = entry.get("models")
    if (
        not isinstance(fetched, (int, float))
        or not isinstance(models, list)
        or now - fetched >= ttl_s
        or now < fetched
    ):
        return None
    raw: RawModels = []
    for item in models:
        if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
            raw.append((item[0], dict(item[1]) if isinstance(item[1], dict) else {}))
    return raw


def _cache_put(
    env: Mapping[str, str],
    provider_id: str,
    fingerprint: str,
    source: str,
    raw: RawModels,
    now: float,
) -> None:
    """Best-effort: ошибки записи кэша не влияют на результат discovery."""
    path = cache_path(env)
    lock_path = path.parent / "locks" / "discovery-cache.lock"
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a+") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            try:
                entries = _read_cache(env)
                entries[_cache_key(provider_id, fingerprint)] = {
                    "fetched_at": now,
                    "source": source,
                    "models": [[mid, meta] for mid, meta in raw],
                }
                payload = json.dumps(
                    {"schema": CACHE_SCHEMA, "entries": entries},
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
                tmp = path.with_name(path.name + ".%d.tmp" % os.getpid())
                with open(tmp, "w", encoding="utf-8") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, path)
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    except (OSError, TypeError, ValueError):
        pass


# ---- публичный API --------------------------------------------------------------------------


def discover(
    manifest: ProviderManifest,
    *,
    env: Mapping[str, str],
    timeout_s: Optional[float] = None,
    clock: Optional[Clock] = None,
    force: bool = False,
) -> DiscoveryResult:
    """Discovery одного провайдера; не бросает. `force` — игнорировать кэш."""
    provider_id = getattr(manifest, "provider_id", "")
    fingerprint = hashlib.sha256(NO_FINGERPRINT_SEED.encode("utf-8")).hexdigest()
    try:
        use_clock = clock or time.time
        limit = timeout_s if timeout_s is not None else manifest.discovery.timeout_s
        fingerprint = compute_fingerprint(
            manifest, env, timeout_s=limit, clock=use_clock
        )
        use_cache = _cache_enabled(env) and manifest.discovery.method != "static"
        now = use_clock()
        source = _source_digest(manifest)
        raw: Optional[RawModels] = None
        if use_cache and not force:
            raw = _cache_get(
                env,
                provider_id,
                fingerprint,
                source,
                manifest.discovery.refresh_interval_s,
                now,
            )
        if raw is None:
            raw = _fetch_raw(manifest, env, limit)
            if use_cache:
                _cache_put(env, provider_id, fingerprint, source, raw, now)
        model_ids, meta = normalize_models(raw, manifest, env)
        return DiscoveryResult(provider_id, fingerprint, model_ids, meta, None)
    except _DiscoveryFailure as exc:
        return DiscoveryResult(provider_id, fingerprint, (), {}, exc.slug)
    except Exception:  # noqa: BLE001 - контракт: discovery не бросает
        return DiscoveryResult(
            provider_id, fingerprint, (), {}, "discovery_internal_error"
        )


def discover_all(
    manifests: Sequence[ProviderManifest],
    env: Mapping[str, str],
    *,
    timeout_s: Optional[float] = None,
    clock: Optional[Clock] = None,
    force: bool = False,
) -> Dict[str, DiscoveryResult]:
    """Discovery всех включённых провайдеров (параллельно); ошибка одного не влияет на других."""
    active = [m for m in manifests if getattr(m, "enabled", True)]
    results: Dict[str, DiscoveryResult] = {}
    if not active:
        return results
    workers = min(_max_workers(env), len(active))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(
                discover, m, env=env, timeout_s=timeout_s, clock=clock, force=force
            )
            for m in active
        ]
        for manifest, future in zip(active, futures):
            results[manifest.provider_id] = future.result()
    return results
