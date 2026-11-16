"""Единая живая граница credentials для readiness и непосредственного send."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping

from core.transport_settings import TransportSettings

_CREDENTIAL_FIELDS = ("api_key_ref", "api_key_env", "api_key")


def _validated_credential(value: object, limit: int) -> str:
    if not isinstance(value, str) or len(value) > limit:
        return ""
    key = value.strip()
    # Bearer передаётся в HTTP-заголовке: пробелы и управляющие байты недопустимы.
    if not key or any(not 33 <= ord(char) <= 126 for char in key):
        return ""
    return key


def _environment_key(name: object, env: Mapping[str, str]) -> str:
    if not isinstance(name, str):
        return ""
    if not name.isascii() or not name.isidentifier():
        return ""
    return env.get(name, "")


def _file_key(path: str, limit: int) -> str:
    """Читает ограниченный обычный файл; FIFO не может заблокировать open."""
    try:
        descriptor = os.open(os.path.expanduser(path), os.O_RDONLY | os.O_NONBLOCK)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                return ""
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                value = handle.read(limit + 1)
        finally:
            os.close(descriptor)
        if len(value) > limit:
            return ""
        return value.decode("utf-8")
    except (OSError, ValueError):
        return ""


def _reference_key(reference: object, env: Mapping[str, str], limit: int) -> str:
    if not isinstance(reference, str):
        return ""
    scheme, separator, target = reference.partition(":")
    if not separator or not target:
        return ""
    if scheme == "env":
        return _environment_key(target, env)
    if scheme == "file":
        return _file_key(target, limit)
    return ""


def resolve_credential(
    config: Mapping[str, object],
    env: Mapping[str, str] | None = None,
    settings: TransportSettings | None = None,
) -> str:
    """Разрешает ref → env → literal без кэша и без клиентского Authorization.

    Объявленный источник авторитетен: отсутствие, отзыв, ошибка чтения или
    невалидное значение не разрешают переход к другому, возможно старому ключу.
    Потребитель повторно вызывает resolver перед send, не сохраняя readiness-key.
    """
    limits = settings if settings is not None else TransportSettings.from_env(env)
    source = os.environ if env is None else env
    if config.get("api_key_ref") not in (None, ""):
        value = _reference_key(config["api_key_ref"], source, limits.credential_max_bytes)
    elif config.get("api_key_env") not in (None, ""):
        value = _environment_key(config["api_key_env"], source)
    else:
        value = config.get("api_key", "")
    return _validated_credential(value, limits.credential_max_bytes)


def credential_required(config: Mapping[str, object]) -> bool:
    """Отличает явный credential от разрешённого локального anonymous upstream."""
    return any(config.get(name) not in (None, "") for name in _CREDENTIAL_FIELDS)


def credential_ready(
    config: Mapping[str, object],
    env: Mapping[str, str] | None = None,
    settings: TransportSettings | None = None,
) -> bool:
    """Проверяет текущий источник тем же resolver, который используется send."""
    if not credential_required(config):
        return True
    return bool(resolve_credential(config, env, settings))
