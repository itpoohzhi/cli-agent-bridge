"""Автоматически ротируемый JSONL-журнал usage-телеметрии по ходам (fail-open)."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from core import defaults as D
from core.runtime_env import flag_enabled
from core.telemetry_sql import sanitize_scalar
from core.usage_schema import USAGE_LOG_FIELDS, resolve_usage_log_source_value


@dataclass(frozen=True)
class UsageLogConfig:
    """Параметры записи и ротации JSONL-лога использования токенов."""

    path: str
    max_bytes: int
    backup_count: int
    retention_days: int
    rotate_daily: bool
    enabled: bool | None = None


def _resolve_raw(row_map: Mapping[str, Any], field: str) -> Any:
    """Извлекает значение поля из row_map, делегируя в usage-схему."""
    return resolve_usage_log_source_value(row_map, field)


def row_to_usage_record(row_map: Mapping[str, Any]) -> dict[str, Any]:
    """Преобразует строку телеметрии в словарь строго из allowlist-полей USAGE_LOG_FIELDS (18)."""
    record: dict[str, Any] = {}
    for field in USAGE_LOG_FIELDS:
        clean = sanitize_scalar(_resolve_raw(row_map, field))
        if field == "elapsed_ms" and isinstance(clean, float):
            clean = round(clean, 2)
        record[field] = clean
    return record


def _encode_rows(rows: Sequence[Any], col_names: Sequence[str] | None) -> list[bytes]:
    """Кодирует последовательность отображений или кортежей в JSONL-строки."""
    encoded: list[bytes] = []
    for row in rows:
        if isinstance(row, Mapping):
            mapping: Mapping[str, Any] = row
        elif col_names is not None and isinstance(row, (tuple, list)):
            mapping = dict(zip(col_names, row, strict=False))
        else:
            raise TypeError("row must be Mapping or tuple/list with col_names")
        rec = row_to_usage_record(mapping)
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
        encoded.append(line.encode("utf-8"))
    return encoded


class RotatingUsageLogWriter:
    """Потокобезопасный fail-open JSONL-writer с ротацией по размеру, суткам и TTL."""

    def __init__(self, cfg: UsageLogConfig) -> None:
        """Инициализирует writer и внутренние счётчики состояния."""
        self._cfg = cfg
        self._path = os.path.expanduser(cfg.path)
        self._lock = threading.Lock()
        self._stats: dict[str, int] = {
            "written": 0, "rotations": 0, "pruned_files": 0, "usage_log_errors": 0,
        }
        self._active_day: str | None = None

    def is_enabled(self) -> bool:
        """Возвращает состояние kill-switch (явный override или GigaRC-флаг)."""
        en = self._cfg.enabled
        return flag_enabled("BRIDGE_USAGE_LOG_ENABLED") if en is None else bool(en)

    def write_rows(
        self, rows: Sequence[Any], col_names: Sequence[str] | None = None
    ) -> int:
        """Записывает пачку строк в JSONL с авторотацией; при ошибках не бросает."""
        if not self.is_enabled() or not rows:
            return 0
        try:
            lines = _encode_rows(rows, col_names)
            with self._lock:
                return self._write_locked(lines)
        except Exception:
            with self._lock:
                self._stats["usage_log_errors"] += 1
            return 0

    def status_snapshot(self) -> dict[str, Any]:
        """Возвращает копию конфигурации и счётчиков без ссылки на _stats."""
        with self._lock:
            stats = dict(self._stats)
        return {
            "enabled": self.is_enabled(), "path": self._path,
            "max_bytes": self._cfg.max_bytes, "backup_count": self._cfg.backup_count,
            "retention_days": self._cfg.retention_days, **stats,
        }

    def close(self) -> None:
        """Безопасное завершение работы writer."""

    def _prepare_day_locked(self, now_day: str) -> int:
        """Обеспечивает каталог, проверяет смену UTC-дня и возвращает размер."""
        parent = os.path.dirname(self._path)
        if parent and not os.path.exists(parent):
            os.makedirs(parent, mode=0o700, exist_ok=True)
            os.chmod(parent, 0o700)
        try:
            st = os.stat(self._path)
            size = st.st_size
            file_day: str | None = time.strftime("%Y-%m-%d", time.gmtime(st.st_mtime))
        except FileNotFoundError:
            size, file_day = 0, None
        if self._cfg.rotate_daily and size > 0 and (
            {file_day, self._active_day} - {None, now_day}
        ):
            self._rotate_locked()
            return 0
        return size

    def _rotate_locked(self) -> None:
        """Атомарно сдвигает архивы .1..backup_count и активный файл в .1."""
        backups = max(0, self._cfg.backup_count)
        if backups == 0 and os.path.exists(self._path):
            os.unlink(self._path)
            self._stats["rotations"] += 1
            return
        for idx in range(backups - 1, -1, -1):
            src = self._path if idx == 0 else f"{self._path}.{idx}"
            dst = f"{self._path}.{idx + 1}"
            if os.path.exists(src):
                os.replace(src, dst)
                os.chmod(dst, 0o600)
                if idx == 0:
                    self._stats["rotations"] += 1

    def _prune_archives_locked(self, now_ts: float) -> None:
        """Удаляет архивы сверх backup_count или старше retention_days."""
        parent = os.path.dirname(self._path) or "."
        prefix = f"{os.path.basename(self._path)}."
        backups = max(0, self._cfg.backup_count)
        retention = self._cfg.retention_days
        cutoff = now_ts - retention * 86400.0 if retention > 0 else None
        for entry in os.scandir(parent):
            if not entry.name.startswith(prefix):
                continue
            suffix = entry.name[len(prefix):]
            if not suffix.isdigit() or not entry.is_file(follow_symlinks=False):
                continue
            st = entry.stat(follow_symlinks=False)
            expired = cutoff is not None and st.st_mtime < cutoff
            if int(suffix) > backups or expired:
                os.unlink(entry.path)
                self._stats["pruned_files"] += 1

    def _write_locked(self, lines: list[bytes]) -> int:
        """Проверяет ротацию, дописывает строки и чистит устаревшие архивы."""
        now_ts = time.time()
        now_day = time.strftime("%Y-%m-%d", time.gmtime(now_ts))
        size = self._prepare_day_locked(now_day)
        payload = b"".join(lines)
        max_bytes = max(1, self._cfg.max_bytes)
        chunks = [payload] if len(payload) <= max_bytes else lines
        for chunk in chunks:
            if size > 0 and size + len(chunk) > max_bytes:
                self._rotate_locked()
                size = 0
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, "ab") as handle:
                os.chmod(self._path, 0o600)
                handle.write(chunk)
            size += len(chunk)
        self._active_day = now_day
        self._stats["written"] += len(lines)
        self._prune_archives_locked(now_ts)
        return len(lines)


def create_usage_log_writer(
    cfg: Mapping[str, Any] | None = None,
) -> RotatingUsageLogWriter:
    """Создаёт RotatingUsageLogWriter из явного конфига, env или defaults."""
    opts = cfg or {}
    en = opts.get("usage_log_enabled")

    def _i(k: str, e: str) -> int:
        return int(opts[k] if k in opts else D.get_env_int(e, getattr(D, e)))

    p = D.get_env_str("BRIDGE_USAGE_LOG_PATH", D.BRIDGE_USAGE_LOG_PATH)
    r = D.get_env_bool("BRIDGE_USAGE_LOG_ROTATE_DAILY", D.BRIDGE_USAGE_LOG_ROTATE_DAILY)
    return RotatingUsageLogWriter(UsageLogConfig(
        path=str(opts.get("usage_log_path", p)),
        max_bytes=_i("usage_log_max_bytes", "BRIDGE_USAGE_LOG_MAX_BYTES"),
        backup_count=_i("usage_log_backup_count", "BRIDGE_USAGE_LOG_BACKUP_COUNT"),
        retention_days=_i("usage_log_retention_days", "BRIDGE_USAGE_LOG_RETENTION_DAYS"),
        rotate_daily=bool(opts.get("usage_log_rotate_daily", r)),
        enabled=None if en is None else bool(en),
    ))


__all__: tuple[str, ...] = (
    "USAGE_LOG_FIELDS", "UsageLogConfig", "RotatingUsageLogWriter",
    "row_to_usage_record", "create_usage_log_writer",
)
