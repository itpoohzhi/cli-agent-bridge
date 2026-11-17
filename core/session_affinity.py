"""Агент-агностическая привязка passthrough-запросов к непрозрачной сессии."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import stat
import threading
import time
import uuid
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, Iterator

import fcntl

from core.runtime_env import flag_enabled

FLAG_STABLE_SESSION = "BRIDGE_STABLE_SESSION_AFFINITY_ENABLED"
_DEFAULT_SALT_PATH = "~/.dsh/state/affinity_salt.bin"
_SALT: bytes | None = None
_BUSY_SALT: bytes | None = None
_SALT_LOCK = threading.Lock()


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= minimum else default


_RESPONSE_CHAINS: dict[str, tuple[str, float]] = {}
_CHAINS_LOCK = threading.Lock()
_MAX_RESPONSE_CHAINS = _env_int("BRIDGE_AFFINITY_MAX_CHAINS", 4096, minimum=1)
_AFFINITY_TTL_S = _env_int("BRIDGE_AFFINITY_TTL_S", 3600, minimum=0)


class SaltLockBusyError(RuntimeError):
    """Файловая блокировка соли занята другим процессом."""


def _max_response_chains() -> int:
    raw = os.environ.get("BRIDGE_AFFINITY_MAX_CHAINS", "").strip()
    if raw:
        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass
    return max(1, int(_MAX_RESPONSE_CHAINS))


def _affinity_ttl_s() -> int:
    raw = os.environ.get("BRIDGE_AFFINITY_TTL_S", "").strip()
    if raw:
        try:
            value = int(raw)
            if value >= 0:
                return value
        except ValueError:
            pass
    return max(0, int(_AFFINITY_TTL_S))


def _read_salt(salt_path: str) -> bytes:
    """Безопасно и неблокирующе читает ровно 32 байта приватной соли."""
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(salt_path, flags)
    try:
        st = os.fstat(fd)
        if (
            st.st_uid != os.getuid()
            or not stat.S_ISREG(st.st_mode)
            or stat.S_IMODE(st.st_mode) != 0o600
        ):
            raise PermissionError("unsafe salt file")
        salt = os.read(fd, 33)
    finally:
        os.close(fd)
    if len(salt) != 32:
        raise ValueError("must be 32 bytes")
    return salt


@contextmanager
def _file_lock(salt_path: str) -> Iterator[None]:
    """Пытается сериализовать работу с солью, никогда не ожидая flock."""
    lock_path = f"{salt_path}.lock"
    lock_flags = (
        os.O_CREAT
        | os.O_RDWR
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    fd = os.open(lock_path, lock_flags, 0o600)
    locked = False
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or not stat.S_ISREG(st.st_mode):
            raise PermissionError("unsafe lock file")
        os.fchmod(fd, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except (BlockingIOError, OSError) as exc:
            raise SaltLockBusyError("salt lock busy") from exc
        try:
            yield
        finally:
            if locked:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
    finally:
        os.close(fd)


def _write_salt_atomically(salt_path: str, salt: bytes) -> None:
    """Записывает соль во временный файл и атомарно заменяет целевой."""
    temporary_path = f"{salt_path}.tmp.{os.getpid()}"
    try:
        try:
            fd = os.open(temporary_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            st = os.lstat(temporary_path)
            if st.st_uid != os.getuid() or not stat.S_ISREG(st.st_mode):
                raise PermissionError("unsafe affinity salt temporary file")
            os.unlink(temporary_path)
            fd = os.open(temporary_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.fchmod(fd, 0o600)
            view = memoryview(salt)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise OSError("failed to write affinity salt")
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary_path, salt_path)
        dir_name = os.path.dirname(salt_path) or "."
        try:
            dir_fd = os.open(dir_name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    finally:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass


def _init_salt() -> bytes:
    """Загружает постоянную соль или при любой файловой ошибке использует память."""
    val = os.environ.get("BRIDGE_SESSION_AFFINITY_SALT", "").strip()
    if len(val) >= 16:
        return hashlib.sha256(val.encode()).digest()

    configured_path = os.environ.get("BRIDGE_AFFINITY_SALT_FILE")
    salt_path = os.path.expanduser(configured_path or _DEFAULT_SALT_PATH)
    try:
        parent = os.path.dirname(salt_path)
        if parent:
            os.makedirs(parent, mode=0o700, exist_ok=True)
            parent_st = os.stat(parent)
            if parent_st.st_uid != os.getuid() or parent_st.st_mode & 0o022 != 0:
                return secrets.token_bytes(32)

        with _file_lock(salt_path):
            try:
                return _read_salt(salt_path)
            except (FileNotFoundError, ValueError):
                pass

            salt = secrets.token_bytes(32)
            _write_salt_atomically(salt_path, salt)
            return _read_salt(salt_path)
    except (OSError, ValueError):
        return secrets.token_bytes(32)


def _get_salt() -> bytes:
    """Потокобезопасно и лениво инициализирует stable-affinity соль."""
    global _SALT, _BUSY_SALT
    if _SALT is None:
        with _SALT_LOCK:
            if _SALT is None:
                try:
                    _SALT = _init_salt()
                except SaltLockBusyError:
                    if _BUSY_SALT is None:
                        _BUSY_SALT = secrets.token_bytes(32)
                    return _BUSY_SALT
    return _SALT


def register_response_affinity(
    response_id: str, affinity_uuid: str, scope: str = ""
) -> None:
    """Связывает Responses API response id с affinity в пределах scope."""
    if not isinstance(response_id, str) or not response_id:
        return
    if not isinstance(affinity_uuid, str) or not affinity_uuid:
        return
    if not isinstance(scope, str):
        return
    key = f"{scope}:{response_id}"
    now = time.monotonic()
    ttl = _affinity_ttl_s()
    max_chains = _max_response_chains()
    with _CHAINS_LOCK:
        expired = [k for k, (_, ts) in _RESPONSE_CHAINS.items() if now - ts >= ttl]
        for k in expired:
            _RESPONSE_CHAINS.pop(k, None)
        _RESPONSE_CHAINS.pop(key, None)
        _RESPONSE_CHAINS[key] = (affinity_uuid, now)
        while len(_RESPONSE_CHAINS) > max_chains:
            oldest = next(iter(_RESPONSE_CHAINS))
            _RESPONSE_CHAINS.pop(oldest, None)


def _response_chain_affinity(
    previous_response_id: Any, scope: str = ""
) -> str | None:
    if not isinstance(previous_response_id, str) or not previous_response_id:
        return None
    if not isinstance(scope, str):
        return None
    key = f"{scope}:{previous_response_id}"
    now = time.monotonic()
    ttl = _affinity_ttl_s()
    with _CHAINS_LOCK:
        entry = _RESPONSE_CHAINS.pop(key, None)
        if entry is None:
            return None
        affinity_uuid, ts = entry
        if now - ts >= ttl:
            return None
        _RESPONSE_CHAINS[key] = (affinity_uuid, ts)
        return affinity_uuid


def _field(value: Any, name: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(name)
    return getattr(value, name, None)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _json_value(model_dump())
        except (TypeError, ValueError):
            pass
    attributes = getattr(value, "__dict__", None)
    if isinstance(attributes, Mapping):
        return _json_value(
            {key: item for key, item in attributes.items() if not key.startswith("_")}
        )
    try:
        return repr(value)
    except Exception:
        return str(type(value))


def _serialized_content(value: Any) -> str:
    return json.dumps(
        _json_value(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _content_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if isinstance(content, (list, tuple)):
        parts: list[str] = []
        for item in content:
            text = _content_text(item)
            parts.append(text if text is not None else _serialized_content(item))
        return _serialized_content(parts) if parts else None
    if isinstance(content, Mapping):
        for key in ("text", "content", "value"):
            if key in content:
                text = _content_text(content.get(key))
                if text is not None:
                    return text
        return None
    for name in ("text", "content", "value"):
        candidate = getattr(content, name, None)
        if candidate is not None:
            text = _content_text(candidate)
            if text is not None:
                return text
    if content is not None:
        return _serialized_content(content)
    return None


def _message_identity(message: Any) -> dict[str, Any]:
    role = _field(message, "role")
    message_type = _field(message, "type")
    content = _field(message, "content")
    text = _content_text(content)
    identity: dict[str, Any] = {
        "role": role if isinstance(role, str) else _json_value(role),
        "type": message_type if isinstance(message_type, str) else _json_value(message_type),
        "content": text if text is not None else _json_value(content),
    }
    name = _field(message, "name")
    if name is not None:
        identity["name"] = _json_value(name)
    return identity


def _top_level_instruction_identity(data: Mapping[str, Any]) -> list[dict[str, Any]]:
    anchor: list[dict[str, Any]] = []
    for field in ("system", "instructions"):
        value = data.get(field)
        if value is not None:
            text = _content_text(value)
            anchor.append(
                {
                    "role": field,
                    "type": "instruction",
                    "content": text if text is not None else _json_value(value),
                }
            )
    return anchor


def _response_content_identity(content: Any) -> Any:
    if isinstance(content, (list, tuple)):
        return [_response_item_identity(item) for item in content]
    if isinstance(content, Mapping) or hasattr(content, "__dict__"):
        return _response_item_identity(content)
    text = _content_text(content)
    return text if text is not None else _json_value(content)


def _response_item_identity(item: Any) -> dict[str, Any]:
    role = _field(item, "role")
    item_type = _field(item, "type")
    content = _field(item, "content")
    if content is None:
        content = _field(item, "text")
    if content is None:
        content = _field(item, "value")
    normalized_role = role if isinstance(role, str) else "input"
    normalized_type = item_type if isinstance(item_type, str) else "message"
    normalized_content = _response_content_identity(content)
    return {
        "anchor": (
            f"role={normalized_role}|type={normalized_type}|content="
            f"{_serialized_content(normalized_content)}"
        )
    }


def _input_identity(data: Mapping[str, Any]) -> list[dict[str, Any]] | None:
    if "input" not in data:
        return None
    value = data.get("input")
    if isinstance(value, str):
        return [{"anchor": f"role=user|type=input_text|content={_serialized_content(value)}"}]
    if isinstance(value, Mapping):
        return [_response_item_identity(value)]
    if not isinstance(value, (list, tuple)):
        return None

    instructions: list[dict[str, Any]] = []
    first_user: dict[str, Any] | None = None
    fallback: dict[str, Any] | None = None
    for item in value:
        identity = _response_item_identity(item)
        if fallback is None:
            fallback = identity
        role = _field(item, "role")
        item_type = _field(item, "type")
        if role in ("system", "developer") and first_user is None:
            instructions.append(identity)
            continue
        user_like = role == "user" or (
            role is None and isinstance(item_type, str) and item_type.startswith("input_")
        )
        if user_like:
            first_user = identity
            break
    if first_user is not None:
        return [*instructions, first_user]
    return [*instructions, fallback] if fallback is not None else None


def _identity(
    data: Mapping[str, Any], headers: Mapping[str, str], scope: str = ""
) -> Any:
    """Явная сессия и зарегистрированная Responses-цепочка задают диалоговый якорь."""
    prompt_key = data.get("prompt_cache_key")
    if isinstance(prompt_key, str) and prompt_key:
        return {"key": prompt_key}

    conv_id = (
        data.get("session_id")
        or data.get("conversation_id")
        or headers.get("x-session-id")
        or headers.get("x-opencode-session")
    )
    dialog_anchor: list[dict[str, Any]] = []
    if conv_id:
        dialog_anchor = [{"conversation_id": _json_value(conv_id)}]

    chain_affinity = _response_chain_affinity(
        data.get("previous_response_id"), scope=scope
    )
    if chain_affinity is not None:
        dialog_anchor = [{"chain_affinity": chain_affinity}]

    if dialog_anchor:
        return {"first": dialog_anchor, "tools": _json_value(data.get("tools"))}

    top_level = _top_level_instruction_identity(data)
    input_identity = _input_identity(data)
    messages = data.get("messages")
    if isinstance(messages, (list, tuple)) and messages:
        dialog_anchor = list(top_level)
        if input_identity is not None:
            dialog_anchor.extend(input_identity)
        dialog_anchor.extend(
            _message_identity(message)
            for message in messages
            if _field(message, "role") in ("system", "developer")
        )
        user_msg = next(
            (message for message in messages if _field(message, "role") == "user"), None
        )
        if user_msg is not None:
            dialog_anchor.append(_message_identity(user_msg))
        if not dialog_anchor:
            dialog_anchor.append(_message_identity(messages[0]))
        return {"first": dialog_anchor, "tools": _json_value(data.get("tools"))}

    dialog_anchor = list(top_level)
    if input_identity is not None:
        dialog_anchor.extend(input_identity)
    if dialog_anchor:
        return {"first": dialog_anchor, "tools": _json_value(data.get("tools"))}
    if "prompt" in data and data.get("prompt") is not None:
        return {"prompt": _json_value(data.get("prompt"))}
    return None


def _private_fingerprint(value: Any) -> str | None:
    if value is None:
        return None
    raw = value if isinstance(value, str) else str(value)
    return hmac.new(_get_salt(), raw.encode("utf-8"), hashlib.sha256).hexdigest()


def _scope(data: Mapping[str, Any], headers: Mapping[str, str], namespace: str) -> str:
    parts = [
        namespace,
        data.get("model"),
        data.get("user"),
        _private_fingerprint(headers.get("authorization")),
        _private_fingerprint(headers.get("x-api-key")),
        _private_fingerprint(headers.get("api-key")),
        headers.get("x-subagent-id"),
    ]
    raw = json.dumps(
        parts, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hmac.new(_get_salt(), raw, hashlib.sha256).hexdigest()


def request_scope(raw_body: bytes, headers: Mapping[str, str], namespace: str) -> str:
    """Вычисляет непрозрачный scope_hash для изоляции цепочек ответов."""
    if not flag_enabled(FLAG_STABLE_SESSION):
        return ""
    try:
        data = json.loads(raw_body)
    except (ValueError, UnicodeError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    lower = {name.lower(): value for name, value in headers.items()}
    return _scope(data, lower, namespace)


def session_affinity(raw_body: bytes, headers: Mapping[str, str], namespace: str) -> str:
    """HMAC из стабильного диалогового якоря и scope; default OFF даёт UUID4."""
    if not flag_enabled(FLAG_STABLE_SESSION):
        return str(uuid.uuid4())
    try:
        data = json.loads(raw_body)
    except (ValueError, UnicodeError):
        return str(uuid.uuid4())
    if not isinstance(data, dict):
        return str(uuid.uuid4())
    lower = {name.lower(): value for name, value in headers.items()}

    scope_hash = _scope(data, lower, namespace)
    inherited = _response_chain_affinity(
        data.get("previous_response_id"), scope=scope_hash
    )
    if inherited is not None:
        return inherited

    identity = _identity(data, lower, scope=scope_hash)
    if identity is None:
        return str(uuid.uuid4())
    material = json.dumps(
        [scope_hash, identity],
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hmac.new(_get_salt(), material, hashlib.sha256).hexdigest()
    return str(uuid.UUID(hex=digest[:32], version=5))
