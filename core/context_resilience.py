"""Ядро отказоустойчивости контекста: бюджет, граф сообщений, прунинг, эпохи (ADR-0006 v3.0).

Модуль чистый и stdlib-only (BND-003): без импорта `server`/`adapters.*`, без сети,
LLM и CLI. Один и тот же алгоритм обслуживает любой фасад: политика не ветвится по
порту или имени модели, а читает бюджет из `RouteEntry` (каталог маршрутов).

Контракт одного запроса (`prepare`):
1. Один скан сообщений: ceildiv-вес (ASCII/UTF-8/модальности), SHA-256 дайджест,
   ссылки tool_calls/tool_results — O(P + V + E).
2. `T_bound <= B_input`, где `B_input = C - R_output - H_hidden - S_uncertainty`
   (I-01). Помещается — passthrough; иначе прунинг до `78% * B_input` (AD-004).
3. Граф неделимых компонент (вызов + все результаты, cross-turn) удаляется или
   сохраняется целиком (I-04). Якоря и активный ход неизменяемы (I-02, I-08).
4. Одна финальная сборка и одно финальное доказательство размера (I-07, I-12).
5. Сбой сжатия → структурированный отказ, а не fail-open (I-06, I-11).

Исходный журнал не мутируется (I-05): все сообщения возвращаются как исходные объекты
либо как копии с вырезанным reasoning. В отчётах и логах нет текстов и подписей (I-10).
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
import stat
import threading
import time
from typing import Any

CORE_CONTRACT_VERSION = 1
CORE_RELEASE = "core-1"

MARKER_TEXT = "[context pruned]"
MARKER_TOKENS = 8
HYSTERESIS_PERCENT = 78
N_RECENT = 10
MAX_DEPTH = 64
PRUNED_HEADER = "X-DSH-Context-Pruned"

PROTOCOLS = ("openai", "google", "anthropic")

REASON_REQUIRED_EXCEEDS = "context_required_exceeds_budget"

_IMAGE_TYPES = frozenset({"image_url", "image", "input_image", "input_audio", "audio"})
_MODALITY_PAYLOAD_KEYS = frozenset(
    {"image_url", "source", "input_audio", "data", "url", "image", "audio"}
)
_GOOGLE_MEDIA_KEYS = ("inlineData", "inline_data", "fileData", "file_data")
_GOOGLE_MEDIA_FIELDS = frozenset(
    {"data", "mimeType", "mime_type", "fileUri", "file_uri"}
)
_OPENAI_REASONING_KEYS = (
    "reasoning_content",
    "reasoning",
    "reasoning_details",
    "thinking",
)
_GOOGLE_SIG_KEYS = ("thoughtSignature", "thought_signature")


# --------------------------------------------------------------------------- ошибки


class ContextError(Exception):
    """База структурированных отказов ядра: только коды и числа, без содержимого."""

    status = 500
    error_type = "internal_error"

    def __init__(self, reason: str, **facts: int | str) -> None:
        super().__init__(reason)
        self.reason = reason
        self.facts = dict(facts)

    def message(self) -> str:
        tail = " ".join(f"{k}={v}" for k, v in sorted(self.facts.items()))
        return f"{self.reason}: {tail}" if tail else self.reason

    def error_body(self) -> dict[str, Any]:
        return {
            "error": {
                "message": self.message(),
                "type": self.error_type,
                "code": self.status,
            }
        }


class ContextRejected(ContextError):
    """Вход нельзя безопасно уместить в окно: 400 invalid_request, zero-send (I-11)."""

    status = 400
    error_type = "invalid_request"


class ContextUnqualified(ContextError):
    """Нет доказательства вместимости (окно/счётчик/модальность): 503, zero-send."""

    status = 503
    error_type = "launcher_unavailable"


# --------------------------------------------------------------------------- бюджет


def ceildiv(numerator: int, denominator: int) -> int:
    """Потолок целочисленного деления без float (формула §5.1)."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return (numerator + denominator - 1) // denominator


@dataclass(frozen=True)
class Passport:
    """Паспорт счётчика: рациональные коэффициенты и резервы (BYTE-V1 по умолчанию)."""

    name: str = "BYTE-V1"
    ascii_ratio: tuple[int, int] = (1, 1)
    utf8_ratio: tuple[int, int] = (1, 1)
    base64_ratio: tuple[int, int] = (1, 1)
    f_msg: int = 8
    f_decl: int = 8
    f_global: int = 0
    h_hidden: int = 0
    s_uncertainty: int = 0
    marker_tokens: int = MARKER_TOKENS
    image_tokens: int | None = None
    evidence_tier: str = "risk_accepted_estimate"

    def __post_init__(self) -> None:
        for ratio in (self.ascii_ratio, self.utf8_ratio, self.base64_ratio):
            if ratio[0] < 0 or ratio[1] <= 0:
                raise ValueError("ratio must be p>=0, q>0")
        if not 4 <= self.marker_tokens <= MARKER_TOKENS:
            raise ValueError("marker_tokens must be in 4..8")
        for value in (
            self.f_msg,
            self.f_decl,
            self.f_global,
            self.h_hidden,
            self.s_uncertainty,
        ):
            if value < 0:
                raise ValueError("reserves must be non-negative")

    def text_tokens(self, ascii_bytes: int, utf8_bytes: int) -> int:
        return ceildiv(
            self.ascii_ratio[0] * ascii_bytes, self.ascii_ratio[1]
        ) + ceildiv(self.utf8_ratio[0] * utf8_bytes, self.utf8_ratio[1])


@dataclass(frozen=True)
class TargetBudget:
    """Окно и выход целевой модели плюс паспорт счётчика."""

    context_window: int
    max_output: int
    passport: Passport = field(default_factory=Passport)

    def output_reserve(self, requested: int | None) -> int:
        """R_output: запрошенный максимум, но не выше допущенного предела модели."""
        if requested is None or requested <= 0:
            return self.max_output
        return min(requested, self.max_output)

    def b_input(self, r_output: int) -> int:
        p = self.passport
        return self.context_window - r_output - p.h_hidden - p.s_uncertainty


def marker_weight(passport: Passport) -> int:
    """Фиксированный резерв маркера: 8 токенов + оболочка F_msg, без самоссылки (I-09)."""
    return passport.marker_tokens + passport.f_msg


# --------------------------------------------------------------------------- каталог


@dataclass(frozen=True)
class RouteEntry:
    """Запись каталога маршрутов (иммутабельна, AD-006/AD-008)."""

    backend: str
    ingress: str
    route: str
    model: str
    request_class: str = "generation"
    enrollment: str = "protected"
    input_transform: str = "prune"
    prune: bool = True
    size_assurance: str = "ESTIMATED"
    target: TargetBudget | None = None
    protocol: str = "openai"
    enrolled: bool = True
    reasoning_policy: str = "preserve"
    revision: str = "1"

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.backend, self.ingress, self.route, self.model)


NATIVE_COMPACTION_ENTRY = RouteEntry(
    backend="opencode-go",
    ingress="model-georouter",
    route="/go/",
    model="deepseek-v4.1-flash",
    request_class="native_compaction",
    enrollment="legacy_native_compaction",
    input_transform="none",
    prune=False,
    size_assurance="UNPROVEN_LEGACY",
    target=None,
    enrolled=False,
)


class Catalog:
    """Каталог точных записей; неизвестный маршрут = None (zero-send у вызывающего)."""

    def __init__(self, entries: Iterable[RouteEntry] = ()) -> None:
        self._entries: dict[tuple[str, str, str, str], RouteEntry] = {
            e.key: e for e in entries
        }

    def lookup(
        self,
        backend: str,
        ingress: str,
        route: str,
        model: str,
        *,
        trusted_native_compaction: bool = False,
    ) -> RouteEntry | None:
        entry = self._entries.get((backend, ingress, route, model))
        if entry is None:
            return None
        if entry.request_class == "native_compaction" and not trusted_native_compaction:
            # Право на legacy-класс даёт только доверенная провенанс-операция DSH,
            # а не имя модели, заголовок пользователя или текст промпта (AD-008).
            return None
        return entry


DEFAULT_CATALOG = Catalog([NATIVE_COMPACTION_ENTRY])


# --------------------------------------------------------------------------- флаги GigaRC

SNAPSHOT_MAX_BYTES = 64 * 1024
SNAPSHOT_MAX_TRUE_AGE_S = 30.0


def default_snapshot_path() -> str:
    return os.path.expanduser(
        "~/.config/cli-agent-bridge/context-resilience.snapshot.json"
    )


@dataclass(frozen=True)
class Flags:
    """Иммутабельный снимок флагов хода (AD-006); по умолчанию всё выключено."""

    dynamic_pruner: bool = False
    shadow: bool = False
    revision: int = 0
    source: str = "default"
    content_sha256: str = ""


def _parse_utc(value: Any) -> float:
    if not isinstance(value, str) or not value:
        raise ValueError("timestamp")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp without tz")
    return parsed.astimezone(timezone.utc).timestamp()


@dataclass(frozen=True)
class _Snapshot:
    revision: int
    generated_at: float
    expires_at: float
    dynamic_pruner: bool
    shadow: bool
    content_sha256: str


class FlagSource:
    """Читатель локального атомарного JSON-снимка флагов: lastgood, default=false, без исключений.

    Снимок читается в начале каждого хода; внутри хода `Flags` иммутабелен. Любой сбой
    (нет файла, мусор, чужие права, устаревший снимок) оставляет lastgood, а при его
    отсутствии или истечении оба флага false. Строгий admission от флагов не зависит.
    """

    def __init__(
        self,
        path: str | None = None,
        *,
        clock: Any = time.time,
        max_true_age_s: float = SNAPSHOT_MAX_TRUE_AGE_S,
    ) -> None:
        self._path = path or default_snapshot_path()
        self._clock = clock
        self._max_true_age_s = max_true_age_s
        self._lock = threading.Lock()
        self._sig: tuple[int, int, int, int] | None = None
        self._lastgood: _Snapshot | None = None

    def current(self) -> Flags:
        with self._lock:
            try:
                fresh = self._read()
            except Exception:  # noqa: BLE001 - гонка/мусор не должны ронять ход
                fresh = None
            source = "snapshot"
            if fresh is not None:
                self._lastgood = fresh
            else:
                source = "lastgood"
            snap = self._lastgood
            if snap is None:
                return Flags()
            return self._effective(snap, source)

    def _effective(self, snap: _Snapshot, source: str) -> Flags:
        now = self._clock()
        alive = (
            now < snap.expires_at and (now - snap.generated_at) <= self._max_true_age_s
        )
        # `true` живёт только пока снимок свеж; `false` остаётся по умолчанию бессрочно.
        return Flags(
            dynamic_pruner=snap.dynamic_pruner and alive,
            shadow=snap.shadow and alive,
            revision=snap.revision,
            source=source,
            content_sha256=snap.content_sha256,
        )

    def _read(self) -> _Snapshot | None:
        euid = os.geteuid()
        st = os.lstat(self._path)
        if not stat.S_ISREG(st.st_mode):
            return None
        sig = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        if sig == self._sig and self._lastgood is not None:
            return self._lastgood
        parent = os.stat(os.path.dirname(self._path) or ".")
        if parent.st_uid != euid or parent.st_mode & 0o077:
            return None
        fd = os.open(
            self._path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
        )
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != euid
                or before.st_mode & 0o077
                or before.st_size > SNAPSHOT_MAX_BYTES
            ):
                return None
            raw = os.read(fd, SNAPSHOT_MAX_BYTES + 1)
            after = os.fstat(fd)
        finally:
            os.close(fd)
        if len(raw) > SNAPSHOT_MAX_BYTES or (
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (after.st_ino, after.st_size, after.st_mtime_ns):
            return None
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            return None
        revision = data.get("revision")
        flags = data.get("flags")
        if (
            isinstance(revision, bool)
            or not isinstance(revision, int)
            or not isinstance(flags, dict)
        ):
            return None
        pruner = flags.get("DYNAMIC_PRUNER_ENABLED", False)
        shadow = flags.get("CONTEXT_RESILIENCE_SHADOW_ENABLED", False)
        if not isinstance(pruner, bool) or not isinstance(shadow, bool):
            return None
        digest = hashlib.sha256(raw).hexdigest()
        last = self._lastgood
        if last is not None and (
            revision < last.revision
            or (revision == last.revision and digest != last.content_sha256)
        ):
            return None  # откат ревизии и подмена под тем же номером недопустимы
        snap = _Snapshot(
            revision=revision,
            generated_at=_parse_utc(data.get("generated_at")),
            expires_at=_parse_utc(data.get("expires_at")),
            dynamic_pruner=pruner,
            shadow=shadow,
            content_sha256=digest,
        )
        self._sig = sig
        return snap


# --------------------------------------------------------------------------- идентичность


_MAX_ID_BYTES = 256


def _valid_id(value: str) -> bool:
    raw = value.encode("utf-8", "surrogatepass")
    return (
        0 < len(raw) <= _MAX_ID_BYTES
        and all(31 < ord(ch) != 127 for ch in value)
        and value == value.strip()
    )


def trusted_ids(headers: Iterable[tuple[str, str]]) -> tuple[str, str | None] | None:
    """Доверенные `x-session-id` / `x-dsh-chat-id` из заголовков (после auth, вне core).

    Приоритет session, затем chat; если есть оба — chat становится дискриминатором.
    Дубликаты с разными значениями, пустые, длинные или с control-символами → None
    (режим no-ID). Возвращает (primary, chat_discriminator|None).
    """
    seen: dict[str, set[str]] = {"x-session-id": set(), "x-dsh-chat-id": set()}
    for name, value in headers:
        lowered = str(name).lower()
        if lowered in seen:
            seen[lowered].add(str(value))
    session, chat = seen["x-session-id"], seen["x-dsh-chat-id"]
    if len(session) > 1 or len(chat) > 1:
        return None
    sid = next(iter(session), None)
    cid = next(iter(chat), None)
    if sid is not None and not _valid_id(sid):
        return None
    if cid is not None and not _valid_id(cid):
        return None
    if sid is not None:
        return sid, cid
    if cid is not None:
        return cid, None
    return None


def owner_scope(principal: str, secret: bytes) -> str:
    """Непрозрачный keyed-дайджест владельца; сырой токен ключом не служит."""
    return hmac.new(secret, principal.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


@dataclass(frozen=True)
class Identity:
    """Идентичность чата: trusted (есть проверенные ID) либо anchor_hash_unverified."""

    owner_scope: str
    route_namespace: str
    session_id: str | None = None
    chat_id: str | None = None

    @property
    def kind(self) -> str:
        return "trusted" if self.session_id is not None else "anchor_hash_unverified"


def build_identity(
    owner: str, route_namespace: str, headers: Iterable[tuple[str, str]]
) -> Identity:
    ids = trusted_ids(headers)
    if ids is None:
        return Identity(owner, route_namespace)
    return Identity(owner, route_namespace, ids[0], ids[1])


def _lp(*parts: bytes | str) -> bytes:
    """Length-prefixed конкатенация: без склейки без разделителей и зависимости от порядка map."""
    out = bytearray()
    for part in parts:
        raw = part.encode("utf-8", "surrogatepass") if isinstance(part, str) else part
        out += len(raw).to_bytes(8, "big") + raw
    return bytes(out)


def _epoch_key(descriptor: tuple[str, ...]) -> str:
    return hashlib.sha256(_lp(*descriptor)).hexdigest()


# --------------------------------------------------------------------------- эпохи


@dataclass
class Epoch:
    """In-memory эпоха прунинга: заморожена база, к ней дописывается только хвост."""

    descriptor: tuple[str, ...]
    generation: int
    source_len: int
    retained: tuple[int, ...]
    digests: tuple[bytes, ...]
    marker_before: int | None
    base_digest: bytes
    pruned: bool
    last_used: float = 0.0

    def approx_bytes(self) -> int:
        return 256 + 80 * len(self.retained) + sum(len(p) for p in self.descriptor)


class EpochStore:
    """Ограниченное хранилище эпох: TTL 30 мин, LRU 1024 на фасад / 128 на владельца, 64 MiB."""

    def __init__(
        self,
        *,
        ttl_s: float = 1800.0,
        max_epochs: int = 1024,
        max_per_owner: int = 128,
        max_bytes: int = 64 * 1024 * 1024,
        clock: Any = time.monotonic,
    ) -> None:
        self._ttl = ttl_s
        self._max = max_epochs
        self._max_owner = max_per_owner
        self._max_bytes = max_bytes
        self._clock = clock
        self._lock = threading.Lock()
        self._data: OrderedDict[str, Epoch] = OrderedDict()
        self._quarantine: dict[str, float] = {}
        self._stripes = tuple(threading.Lock() for _ in range(64))

    def lock_for(self, key: str) -> threading.Lock:
        return self._stripes[int(key[:8], 16) % len(self._stripes)]

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def total_bytes(self) -> int:
        with self._lock:
            return sum(e.approx_bytes() for e in self._data.values())

    def get(self, key: str, descriptor: tuple[str, ...]) -> tuple[Epoch | None, str]:
        """(epoch, status): hit | miss | collision | quarantined."""
        now = self._clock()
        with self._lock:
            if key in self._quarantine and self._quarantine[key] > now:
                return None, "quarantined"
            epoch = self._data.get(key)
            if epoch is None:
                return None, "miss"
            if now - epoch.last_used > self._ttl:
                del self._data[key]
                return None, "miss"
            if epoch.descriptor != descriptor:
                del self._data[key]
                self._quarantine[key] = now + self._ttl
                return None, "collision"
            epoch.last_used = now
            self._data.move_to_end(key)
            return epoch, "hit"

    def put(self, key: str, epoch: Epoch) -> None:
        now = self._clock()
        epoch.last_used = now
        with self._lock:
            self._data[key] = epoch
            self._data.move_to_end(key)
            self._evict_locked(now, epoch.descriptor[0])

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def _evict_locked(self, now: float, owner: str) -> None:
        for key in [k for k, e in self._data.items() if now - e.last_used > self._ttl]:
            del self._data[key]
        for key in [k for k, t in self._quarantine.items() if t <= now]:
            del self._quarantine[key]

        def owned() -> list[str]:
            return [k for k, e in self._data.items() if e.descriptor[0] == owner]

        while len(owned()) > self._max_owner:
            del self._data[owned()[0]]
        while len(self._data) > self._max or (
            sum(e.approx_bytes() for e in self._data.values()) > self._max_bytes
            and len(self._data) > 1
        ):
            self._data.popitem(last=False)


# --------------------------------------------------------------------------- отчёт


@dataclass
class PruneReport:
    """Content-free отчёт: только счётчики, коды и идентификаторы режима (I-10)."""

    mode: str = "off"
    request_class: str = "generation"
    protocol: str = "openai"
    assurance: str = "none"
    pruned: bool | None = None
    context_window: int = 0
    r_output: int = 0
    b_input: int = 0
    t_before: int = 0
    t_after: int = 0
    messages_total: int = 0
    messages_kept: int = 0
    units_total: int = 0
    units_dropped: int = 0
    hard_weight: int = 0
    serializations: int = 0
    nodes_visited: int = 0
    reasoning_stripped: int = 0
    epoch: str = "none"
    generation: int = 0
    hysteresis_degraded: str = ""
    identity_kind: str = "none"
    flags_revision: int = 0
    outcome: str = "ok"

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)

    def log_line(self) -> str:
        return "context_resilience " + " ".join(
            f"{k}={v}" for k, v in self.__dict__.items() if v not in ("", None)
        )


@dataclass(frozen=True)
class PreparedInvocation:
    """Допущенный к отправке вызов: точные байты и отчёт; после proof не мутируется."""

    mode: str
    body: Mapping[str, Any]
    body_bytes: bytes | None
    pruned: bool | None
    report: PruneReport

    @property
    def header(self) -> tuple[str, str] | None:
        """Заголовок UI-сигнала CD-003; None = unknown (legacy/off/shadow)."""
        if self.pruned is None:
            return None
        return (PRUNED_HEADER, "true" if self.pruned else "false")


# --------------------------------------------------------------------------- скан и вес


class _Scan:
    """Накопитель одного скана сообщения: байты ASCII/UTF-8, модальности, дайджест."""

    __slots__ = ("ascii_bytes", "utf8_bytes", "images", "hasher")

    def __init__(self) -> None:
        self.ascii_bytes = 0
        self.utf8_bytes = 0
        self.images = 0
        self.hasher = hashlib.sha256()


def _scan_str(text: str, acc: _Scan) -> None:
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ContextRejected("invalid_utf8") from exc
    ascii_len = len(text) if text.isascii() else len(text.encode("ascii", "ignore"))
    acc.ascii_bytes += ascii_len
    acc.utf8_bytes += len(raw) - ascii_len
    acc.hasher.update(b"s" + len(raw).to_bytes(8, "big"))
    acc.hasher.update(raw)


def _is_modality(node: dict[str, Any]) -> bool:
    """Типизированная модальность сообщения; имена свойств tool-схем за модальность не считаются."""
    kind = node.get("type")
    if isinstance(kind, str) and kind in _IMAGE_TYPES:
        return any(k in node for k in _MODALITY_PAYLOAD_KEYS)
    for key in _GOOGLE_MEDIA_KEYS:
        inner = node.get(key)
        if isinstance(inner, dict) and _GOOGLE_MEDIA_FIELDS & inner.keys():
            return True
    return False


def _scan(value: Any, acc: _Scan, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ContextRejected("depth_exceeded", limit=MAX_DEPTH)
    if isinstance(value, str):
        _scan_str(value, acc)
    elif isinstance(value, dict):
        if _is_modality(value):
            acc.images += 1
            blob = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            acc.hasher.update(
                b"i" + hashlib.sha256(blob.encode("utf-8", "replace")).digest()
            )
            return
        acc.hasher.update(b"{")
        for key in sorted(value, key=str):
            _scan_str(str(key), acc)
            _scan(value[key], acc, depth + 1)
        acc.hasher.update(b"}")
    elif isinstance(value, (list, tuple)):
        acc.hasher.update(b"[")
        for item in value:
            _scan(item, acc, depth + 1)
        acc.hasher.update(b"]")
    elif value is None or isinstance(value, (bool, int, float)):
        text = json.dumps(value)
        acc.ascii_bytes += len(text)
        acc.hasher.update(b"n" + text.encode("ascii"))
    else:
        raise ContextRejected("unsupported_json_type")


def _weigh(value: Any, passport: Passport, *, extra: int = 0) -> tuple[int, bytes]:
    """(вес в токенах, дайджест) одного блока за один скан; модальность без паспорта — отказ."""
    acc = _Scan()
    _scan(value, acc)
    if acc.images and passport.image_tokens is None:
        raise ContextUnqualified("modality_unqualified")
    weight = passport.text_tokens(acc.ascii_bytes, acc.utf8_bytes)
    weight += acc.images * (passport.image_tokens or 0) + extra
    return weight, acc.hasher.digest()


# --------------------------------------------------------------------------- кодеки


def _messages_key(protocol: str) -> str:
    return "contents" if protocol == "google" else "messages"


def detect_protocol(body: Mapping[str, Any]) -> str:
    """Определение протокола по форме тела; Anthropic задаётся явно маршрутом."""
    return "google" if "contents" in body else "openai"


def _role(protocol: str, msg: Mapping[str, Any]) -> str:
    role = str(msg.get("role", ""))
    if role == "model":
        return "assistant"
    if role == "function":
        return "tool"
    return role


def _links(
    protocol: str, msgs: Sequence[Mapping[str, Any]]
) -> list[tuple[list[str], list[str]]]:
    """Для каждого сообщения: (идентификаторы вызовов, идентификаторы результатов)."""
    out: list[tuple[list[str], list[str]]] = []
    call_ord: dict[str, int] = {}
    resp_ord: dict[str, int] = {}
    for msg in msgs:
        provides: list[str] = []
        needs: list[str] = []
        if protocol == "openai":
            calls = msg.get("tool_calls")
            if isinstance(calls, list):
                provides += [
                    str(c.get("id"))
                    for c in calls
                    if isinstance(c, dict) and c.get("id")
                ]
            fcall = msg.get("function_call")
            if isinstance(fcall, dict) and fcall.get("name"):
                provides.append(f"fc:{fcall['name']}")
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                needs.append(str(msg["tool_call_id"]))
            elif msg.get("role") == "function" and msg.get("name"):
                needs.append(f"fc:{msg['name']}")
        elif protocol == "anthropic":
            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") == "tool_use" and block.get("id"):
                        provides.append(str(block["id"]))
                    elif block.get("type") == "tool_result" and block.get(
                        "tool_use_id"
                    ):
                        needs.append(str(block["tool_use_id"]))
        else:  # google: вызовы связываются по имени и порядковому номеру
            parts = msg.get("parts")
            if isinstance(parts, list):
                for part in parts:
                    if not isinstance(part, dict):
                        continue
                    call = part.get("functionCall") or part.get("function_call")
                    resp = part.get("functionResponse") or part.get("function_response")
                    if isinstance(call, dict) and call.get("name"):
                        name = str(call["name"])
                        provides.append(f"{name}#{call_ord.get(name, 0)}")
                        call_ord[name] = call_ord.get(name, 0) + 1
                    if isinstance(resp, dict) and resp.get("name"):
                        name = str(resp["name"])
                        needs.append(f"{name}#{resp_ord.get(name, 0)}")
                        resp_ord[name] = resp_ord.get(name, 0) + 1
        out.append((provides, needs))
    return out


def _marker_message(protocol: str) -> dict[str, Any]:
    if protocol == "google":
        return {"role": "user", "parts": [{"text": MARKER_TEXT}]}
    if protocol == "anthropic":
        return {"role": "user", "content": [{"type": "text", "text": MARKER_TEXT}]}
    return {"role": "user", "content": MARKER_TEXT}


def _strip_reasoning(
    protocol: str, msg: Mapping[str, Any]
) -> tuple[Mapping[str, Any], int]:
    """Копия сообщения без целых reasoning/signature-пакетов; исходник не трогается."""
    stripped = 0
    if protocol == "openai":
        keys = [k for k in _OPENAI_REASONING_KEYS if k in msg]
        calls = msg.get("tool_calls")
        has_extra = isinstance(calls, list) and any(
            isinstance(c, dict) and "extra_content" in c for c in calls
        )
        if not keys and not has_extra:
            return msg, 0
        copy = {k: v for k, v in msg.items() if k not in keys}
        stripped += len(keys)
        if has_extra and isinstance(calls, list):
            copy["tool_calls"] = [
                {k: v for k, v in c.items() if k != "extra_content"}
                if isinstance(c, dict)
                else c
                for c in calls
            ]
            stripped += 1
        return copy, stripped
    if protocol == "anthropic":
        content = msg.get("content")
        if not isinstance(content, list):
            return msg, 0
        kept = [
            b
            for b in content
            if not (
                isinstance(b, dict)
                and b.get("type") in ("thinking", "redacted_thinking")
            )
        ]
        if len(kept) == len(content) or not kept:
            return msg, 0
        return dict(msg, content=kept), len(content) - len(kept)
    parts = msg.get("parts")
    if not isinstance(parts, list):
        return msg, 0
    new_parts: list[Any] = []
    for part in parts:
        if isinstance(part, dict):
            if part.get("thought") is True:
                stripped += 1
                continue
            if any(k in part for k in _GOOGLE_SIG_KEYS):
                part = {k: v for k, v in part.items() if k not in _GOOGLE_SIG_KEYS}
                stripped += 1
        new_parts.append(part)
    if not stripped or not new_parts:
        return msg, 0
    return dict(msg, parts=new_parts), stripped


_VALID_ROLES = {
    "openai": {"system", "developer", "user", "assistant", "tool"},
    "anthropic": {"user", "assistant"},
    "google": {"user", "assistant", "tool"},
}


def _validate(
    protocol: str, msgs: Sequence[Mapping[str, Any]], pending_from: int
) -> str | None:
    """Финальный валидатор протокола: ролей, первой реплики и ссылок tool_call (None = ок)."""
    roles = [_role(protocol, m) for m in msgs]
    if any(r not in _VALID_ROLES[protocol] for r in roles):
        return "invalid_role"
    if protocol != "openai":
        first = next((r for r in roles if r != "system"), "")
        if first != "user":
            return "first_message_not_user"
    links = _links(protocol, msgs)
    provided: set[str] = set()
    needed: set[str] = set()
    for provides, needs in links:
        for need in needs:
            if need not in provided:
                return "dangling_tool_result"
            needed.add(need)
        provided.update(provides)
    for idx, (provides, _) in enumerate(links):
        if idx < pending_from and any(p not in needed for p in provides):
            return "unresolved_tool_call"
    return None


# --------------------------------------------------------------------------- нормализация


@dataclass
class _Node:
    idx: int
    role: str
    weight: int
    digest: bytes
    provides: list[str]
    needs: list[str]
    comp: int = -1
    hard: bool = False


def _requested_output(protocol: str, body: Mapping[str, Any]) -> int | None:
    candidates: list[Any]
    if protocol == "google":
        cfg = body.get("generationConfig") or body.get("generation_config") or {}
        candidates = (
            [cfg.get("maxOutputTokens"), cfg.get("max_output_tokens")]
            if isinstance(cfg, dict)
            else []
        )
    else:
        candidates = [body.get("max_completion_tokens"), body.get("max_tokens")]
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
    return None


def _components(nodes: list[_Node]) -> tuple[list[list[int]], list[bool], list[bool]]:
    """Связные компоненты dependency-графа за O(V+E).

    Возвращает (компоненты, broken, orphan): broken — вызов без результата либо сирота;
    orphan — результат без вызова (в обязательной цепочке это malformed вход).
    """
    provider_of: dict[str, list[int]] = {}
    needer_of: dict[str, list[int]] = {}
    for node in nodes:
        for pid in node.provides:
            provider_of.setdefault(pid, []).append(node.idx)
        for nid in node.needs:
            needer_of.setdefault(nid, []).append(node.idx)
    adjacency: list[list[int]] = [[] for _ in nodes]
    broken_nodes: set[int] = set()
    orphan_nodes: set[int] = set()

    def link(group: list[int]) -> None:
        head = group[0]
        for other in group[1:]:
            if other != head:
                adjacency[head].append(other)
                adjacency[other].append(head)

    for pid, owners in provider_of.items():
        users = needer_of.get(pid, [])
        if not users:
            broken_nodes.update(owners)
        link(owners + users)
    for nid, users in needer_of.items():
        if nid not in provider_of:
            broken_nodes.update(users)
            orphan_nodes.update(users)
    comps: list[list[int]] = []
    for start in range(len(nodes)):
        if nodes[start].comp != -1:
            continue
        label = len(comps)
        stack, members = [start], []
        nodes[start].comp = label
        while stack:
            cur = stack.pop()
            members.append(cur)
            for nxt in adjacency[cur]:
                if nodes[nxt].comp == -1:
                    nodes[nxt].comp = label
                    stack.append(nxt)
        members.sort()
        comps.append(members)
    broken = [any(m in broken_nodes for m in members) for members in comps]
    orphan = [any(m in orphan_nodes for m in members) for members in comps]
    return comps, broken, orphan


def _anchor_fingerprint(nodes: Sequence[_Node]) -> str:
    """SHA-256 канонических начальных anchors: system/developer до первого user и сам user."""
    parts: list[bytes] = []
    for node in nodes:
        if node.role in ("system", "developer"):
            parts += [node.role.encode(), node.digest]
        elif node.role == "user" and not node.needs:
            parts += [b"user", node.digest]
            break
    return hashlib.sha256(_lp(*parts)).hexdigest()


# --------------------------------------------------------------------------- режимы


def decide_mode(entry: RouteEntry | None, flags: Flags) -> str:
    """native | off | shadow | enforce. Незарегистрированный маршрут = enforce-отказ у вызывающего."""
    if entry is None:
        return "unknown"
    if entry.request_class == "native_compaction":
        return "native"
    if entry.enrolled:
        return "enforce"
    if flags.dynamic_pruner:
        return "enforce"
    if flags.shadow:
        return "shadow"
    return "off"


def prepare(
    body: Mapping[str, Any],
    entry: RouteEntry | None,
    flags: Flags | None = None,
    *,
    protocol: str | None = None,
    identity: Identity | None = None,
    store: EpochStore | None = None,
    serialize: bool = True,
) -> PreparedInvocation:
    """Допуск запроса в окно целевой модели: passthrough либо прунинг, иначе структурированный отказ."""
    flags = flags or Flags()
    mode = decide_mode(entry, flags)
    report = PruneReport(mode=mode, flags_revision=flags.revision)
    if entry is None or mode == "unknown":
        report.outcome = "unknown_route"
        raise ContextUnqualified("unknown_route")
    report.request_class = entry.request_class
    if mode == "native":
        # Точный legacy-класс: вход суммаризатора не трогаем (prune=false, transform none).
        report.assurance = "legacy"
        return PreparedInvocation("native", body, None, None, report)
    if mode == "off":
        return PreparedInvocation("off", body, None, None, report)
    if entry.target is None:
        report.outcome = "no_target_budget"
        raise ContextUnqualified("no_target_budget")
    proto = protocol or entry.protocol
    if proto not in PROTOCOLS:
        raise ContextUnqualified("unknown_protocol")
    report.protocol = proto
    allow_prune = flags.dynamic_pruner or mode == "shadow"
    try:
        return _prepare_enforced(
            body,
            entry,
            mode,
            proto,
            flags,
            report,
            allow_prune,
            identity,
            store,
            serialize,
        )
    except ContextError as exc:
        if mode == "shadow":
            report.outcome = f"would_{exc.error_type}:{exc.reason}"
            return PreparedInvocation("shadow", body, None, None, report)
        report.outcome = f"{exc.error_type}:{exc.reason}"
        raise
    except Exception as exc:  # noqa: BLE001 - любой сбой сжатия не должен стать fail-open
        if mode == "shadow":
            report.outcome = "would_internal_error"
            return PreparedInvocation("shadow", body, None, None, report)
        report.outcome = "internal_error"
        raise ContextUnqualified("compression_failed") from exc


def _prepare_enforced(
    body: Mapping[str, Any],
    entry: RouteEntry,
    mode: str,
    protocol: str,
    flags: Flags,
    report: PruneReport,
    allow_prune: bool,
    identity: Identity | None,
    store: EpochStore | None,
    serialize: bool,
) -> PreparedInvocation:
    target = entry.target
    assert target is not None  # noqa: S101 - проверено вызывающим
    passport = target.passport
    key = _messages_key(protocol)
    raw_msgs = body.get(key)
    if not isinstance(raw_msgs, list) or not all(isinstance(m, dict) for m in raw_msgs):
        raise ContextRejected("invalid_messages")
    r_output = target.output_reserve(_requested_output(protocol, body))
    b_input = target.b_input(r_output)
    report.context_window = target.context_window
    report.r_output = r_output
    report.b_input = b_input
    report.assurance = (
        "estimated"
        if passport.evidence_tier != "certified_upper_bound"
        else "certified"
    )
    if b_input <= 0:
        raise ContextUnqualified("budget_nonpositive", b_input=b_input)

    # Нормализация: одно чтение каждого блока (вес + дайджест); reasoning вырезается ДО счёта.
    msgs: list[Mapping[str, Any]] = list(raw_msgs)
    if entry.reasoning_policy == "strip":
        for i, m in enumerate(msgs):
            msgs[i], n = _strip_reasoning(protocol, m)
            report.reasoning_stripped += n
    base_w = passport.f_global
    decl = 0
    for field_name in ("tools", "functions"):
        value = body.get(field_name)
        if isinstance(value, list):
            decl += len(value)
    preamble = {k: v for k, v in body.items() if k != key}
    pre_w, _ = _weigh(preamble, passport, extra=decl * passport.f_decl)
    base_w += pre_w
    links = _links(protocol, msgs)
    nodes: list[_Node] = []
    for idx, msg in enumerate(msgs):
        weight, digest = _weigh(msg, passport, extra=passport.f_msg)
        nodes.append(
            _Node(
                idx, _role(protocol, msg), weight, digest, links[idx][0], links[idx][1]
            )
        )
    report.messages_total = len(nodes)
    report.nodes_visited = len(nodes)
    total = base_w + sum(n.weight for n in nodes)
    report.t_before = total

    descriptor: tuple[str, ...] | None = None
    ekey = ""
    use_epoch = (
        flags.dynamic_pruner
        and mode == "enforce"
        and identity is not None
        and identity.kind == "trusted"
        and store is not None
    )
    report.identity_kind = identity.kind if identity is not None else "none"
    if identity is not None and identity.kind != "trusted":
        report.epoch = "stateless"

    def finish(
        kept: list[int], marker_before: int | None, pruned: bool
    ) -> PreparedInvocation:
        out_msgs: list[Mapping[str, Any]] = []
        for i in kept:
            if marker_before == i:
                out_msgs.append(_marker_message(protocol))
            out_msgs.append(msgs[i])
        if marker_before is not None and marker_before >= len(nodes):
            out_msgs.append(_marker_message(protocol))
        t_final = base_w + sum(nodes[i].weight for i in kept)
        if marker_before is not None:
            t_final += marker_weight(passport)
        if t_final > b_input:  # I-01: нарушение композиционной границы = дефект кодека
            raise ContextUnqualified(
                "final_proof_failed", t_final=t_final, b_input=b_input
            )
        active = _active_start(nodes)
        pending_from = _out_pos(kept, marker_before, active)
        if pruned:
            problem = _validate(protocol, out_msgs, pending_from)
            if problem is not None:
                raise ContextUnqualified("codec_validation_failed", check=problem)
        new_body = dict(body)
        new_body[key] = out_msgs if pruned or report.reasoning_stripped else raw_msgs
        report.t_after = t_final
        report.messages_kept = len(out_msgs)
        report.pruned = pruned
        payload: bytes | None = None
        if serialize and mode != "shadow":
            payload = json.dumps(
                new_body, ensure_ascii=False, separators=(",", ":")
            ).encode("utf-8")
            report.serializations = 1
        header_pruned: bool | None = pruned if mode == "enforce" else None
        if mode == "shadow":
            report.outcome = "would_prune" if pruned else "would_pass"
            return PreparedInvocation("shadow", body, None, None, report)
        return PreparedInvocation(mode, new_body, payload, header_pruned, report)

    if use_epoch:
        assert identity is not None and store is not None  # noqa: S101
        descriptor = (
            identity.owner_scope,
            identity.route_namespace,
            entry.backend,
            entry.model,
            identity.kind,
            identity.session_id or "",
            identity.chat_id or "",
            _anchor_fingerprint(nodes),
            protocol,
            passport.name,
            entry.revision,
            CORE_RELEASE,
        )
        ekey = _epoch_key(descriptor)
        with store.lock_for(ekey):
            epoch, status = store.get(ekey, descriptor)
            report.epoch = status
            if epoch is not None:
                projection = _project_epoch(epoch, nodes)
                if projection is not None:
                    kept, marker_before = projection
                    t_proj = base_w + sum(nodes[i].weight for i in kept)
                    if epoch.marker_before is not None:
                        t_proj += marker_weight(passport)
                    if t_proj <= b_input:
                        report.generation = epoch.generation
                        report.epoch = "hit"
                        report.units_total = len(nodes)
                        try:
                            return finish(kept, marker_before, epoch.pruned)
                        except ContextUnqualified:
                            pass  # валидатор отверг проекцию: пересоздаём эпоху с нуля
                store.invalidate(ekey)
                report.epoch = "rebuilt"
            # Коллизия/карантин: reuse запрещён обоим, эпоха не сохраняется (stateless prepare).
            reusable = status not in ("collision", "quarantined")
            return _fresh(
                nodes,
                msgs,
                base_w,
                b_input,
                passport,
                protocol,
                report,
                allow_prune,
                finish,
                (store, ekey, descriptor, epoch.generation + 1 if epoch else 1)
                if reusable
                else None,
            )
    return _fresh(
        nodes,
        msgs,
        base_w,
        b_input,
        passport,
        protocol,
        report,
        allow_prune,
        finish,
        None,
    )


def _active_start(nodes: Sequence[_Node]) -> int:
    for node in reversed(nodes):
        if node.role == "user" and not node.needs:
            return node.idx
    return max(len(nodes) - 1, 0)


def _out_pos(kept: Sequence[int], marker_before: int | None, active: int) -> int:
    """Позиция активного хода в выходном списке (с учётом вставленного маркера)."""
    pos = 0
    for i in kept:
        if i >= active:
            break
        pos += 1
    if marker_before is not None and marker_before <= active:
        pos += 1
    return pos


def _project_epoch(
    epoch: Epoch, nodes: Sequence[_Node]
) -> tuple[list[int], int | None] | None:
    """Проекция истории на замороженную базу эпохи + новый хвост; None — атtestation провалена."""
    n = len(nodes)
    if epoch.source_len > n:
        return None
    for idx, digest in zip(epoch.retained, epoch.digests):
        if idx >= n or nodes[idx].digest != digest:
            return None
    tail = list(range(epoch.source_len, n))
    kept = list(epoch.retained) + tail
    return kept, epoch.marker_before


def _fresh(
    nodes: list[_Node],
    msgs: Sequence[Mapping[str, Any]],
    base_w: int,
    b_input: int,
    passport: Passport,
    protocol: str,
    report: PruneReport,
    allow_prune: bool,
    finish: Any,
    epoch_ctx: tuple[EpochStore, str, tuple[str, ...], int] | None,
) -> PreparedInvocation:
    n = len(nodes)
    total = base_w + sum(x.weight for x in nodes)
    report.units_total = n
    if total <= b_input:
        # Непрореженная история: без маркера и без пересчёта разреза ради 78%.
        report.hysteresis_degraded = ""
        return finish(list(range(n)), None, False)
    if not allow_prune:
        raise ContextRejected(REASON_REQUIRED_EXCEEDS, t_bound=total, b_input=b_input)

    # Граф: неделимые компоненты, якоря, активный ход (I-02/I-04/I-08).
    comps, broken, orphan = _components(nodes)
    report.units_total = len(comps)
    first_user = next((x.idx for x in nodes if x.role == "user" and not x.needs), -1)
    active = _active_start(nodes)
    comp_hard = [False] * len(comps)
    for node in nodes:
        if (
            node.role in ("system", "developer")
            or node.idx == first_user
            or node.idx >= active
        ):
            comp_hard[node.comp] = True
    for ci, members in enumerate(comps):
        if comp_hard[ci]:
            if orphan[ci]:
                # Результат без вызова в обязательной цепочке — malformed вход (400).
                raise ContextRejected("dangling_tool_result")
            for m in members:
                nodes[m].hard = True
    comp_weight = [sum(nodes[m].weight for m in members) for members in comps]
    hard_weight = sum(w for w, h in zip(comp_weight, comp_hard) if h)
    report.hard_weight = base_w + hard_weight
    mw = marker_weight(passport)
    if base_w + hard_weight + mw > b_input:
        raise ContextRejected(
            REASON_REQUIRED_EXCEEDS,
            t_required=base_w + hard_weight + mw,
            b_input=b_input,
        )
    target = (HYSTERESIS_PERCENT * b_input) // 100
    budget = target - (base_w + hard_weight + mw)
    if budget < 0:
        report.hysteresis_degraded = "mandatory_dominates"
        budget = 0

    # Выбор: самые новые optional-компоненты по убыванию последнего индекса, один проход.
    selected = [h for h in comp_hard]
    seen: set[int] = set()
    for node in reversed(nodes):
        ci = node.comp
        if ci in seen:
            continue
        seen.add(ci)
        if comp_hard[ci] or broken[ci]:
            continue
        if comp_weight[ci] <= budget:
            selected[ci] = True
            budget -= comp_weight[ci]
    kept = [x.idx for x in nodes if selected[x.comp]]
    dropped = [x.idx for x in nodes if not selected[x.comp]]
    report.units_dropped = sum(1 for ci in range(len(comps)) if not selected[ci])

    marker_before: int | None = None
    if dropped:
        # Маркер ставится перед первой оставшейся репликой после разреза, которая не
        # является результатом инструмента (результат обязан идти сразу за своим вызовом).
        first_drop = dropped[0]
        for i in kept:
            if i > first_drop and not nodes[i].needs:
                marker_before = i
                break
        if marker_before is None:
            marker_before = n
    if not dropped:
        return finish(kept, None, False)
    if epoch_ctx is not None:
        store, ekey, descriptor, generation = epoch_ctx
        retained = tuple(kept)
        base_digest = hashlib.sha256(
            _lp(*[nodes[i].digest for i in retained], MARKER_TEXT.encode())
        ).digest()
        store.put(
            ekey,
            Epoch(
                descriptor=descriptor,
                generation=generation,
                source_len=n,
                retained=retained,
                digests=tuple(nodes[i].digest for i in retained),
                marker_before=marker_before,
                base_digest=base_digest,
                pruned=True,
            ),
        )
        report.generation = generation
        if report.epoch not in ("rebuilt", "collision", "quarantined"):
            report.epoch = "new"
    return finish(kept, marker_before, True)
