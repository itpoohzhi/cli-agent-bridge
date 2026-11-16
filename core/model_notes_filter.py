"""Тонкий совместимый фасад model-notes и синхронная startup-валидация."""

from __future__ import annotations

import os
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from core.model_notes_parse import (
    ModelNotesRule,
    parse_model_notes,
    read_model_notes_file,
)
from core.model_notes_snapshot import ModelNotesSnapshotManager, select_source
from core.route_eligibility import EdgeSnapshot
from core.route_penalty_state import State

_alias_warned = False
_ALIAS_LOCK = threading.Lock()


def _warn_alias() -> None:
    global _alias_warned
    with _ALIAS_LOCK:
        if not _alias_warned:
            _alias_warned = True
            print(
                "MODEL_NOTES_PATH: устаревший alias; используйте BRIDGE_MODEL_NOTES_PATH",
                file=sys.stderr,
            )


def _configuration(
    path: str | os.PathLike[str] | None, ttl_s: float | None
) -> dict[str, object]:
    config: dict[str, object] = dict(os.environ)
    if path is not None:
        config["MODEL_NOTES_PATH"] = os.fspath(path)
    elif "MODEL_NOTES_PATH" in config:
        _warn_alias()
    if ttl_s is not None:
        config["MODEL_NOTES_REFRESH_INTERVAL_S"] = ttl_s
    return config


def _matches(pattern: str | None, value: str | None) -> bool:
    if pattern is None:
        return True
    if value is None:
        return False
    return value.startswith(pattern[:-1]) if pattern.endswith("*") else value == pattern


def _rule_matches(
    rule: ModelNotesRule,
    model: str,
    transport: str | None,
    effort: str | None,
    now: datetime,
) -> bool:
    return (rule.expires_at is None or now <= rule.expires_at) and all(
        _matches(pattern, value)
        for pattern, value in (
            (rule.model, model),
            (rule.transport, transport),
            (rule.effort, effort),
        )
    )


class ModelNotesFilter:
    """Делегирует обновление и fail-closed менеджеру; сопоставляет только правила."""

    def __init__(
        self,
        path: str | os.PathLike[str] | None = None,
        ttl_s: float | None = None,
    ) -> None:
        self.manager = ModelNotesSnapshotManager(_configuration(path, ttl_s))
        self.path = Path(self.manager.source)
        self.ttl_s = self.manager.refresh_interval_s

    def is_blocked(
        self,
        model: str,
        transport: str | None = None,
        effort: str | None = None,
    ) -> bool:
        """Закрывает любой dispatch без пригодного снимка, независимо от скоупа."""
        self.manager.maybe_trigger_refresh_async()
        notes = self.manager.snapshot
        if notes is None:
            return True
        alias = re.fullmatch(r"(.+)-(off|minimal|low|medium|high|xhigh|max)", model)
        if alias is not None:
            model, alias_effort = alias.groups()
            if effort is not None and effort != alias_effort:
                return True
            effort = alias_effort
        now = datetime.now(timezone.utc)
        return any(
            _rule_matches(rule, model, transport, effort, now) for rule in notes.rules
        )

    def edge_snapshot(
        self, model_id: str, backend: str, penalty_state: State | None
    ) -> EdgeSnapshot:
        """Собирает доменный edge из памяти; bypass-заголовки не участвуют."""
        return EdgeSnapshot(
            model_id=model_id,
            backend=backend,
            enabled=True,
            weight=100,
            is_blocked=self.is_blocked(model_id),
            notes_state=self.health_state(),
            penalty_state=penalty_state,
        )

    def health_state(self) -> str:
        """Возвращает безопасный статус без содержимого исходного файла."""
        return self.manager.status

    def is_failed_closed(self) -> bool:
        """Сохраняет единый источник решения о доступности снимка."""
        return self.health_state() == "FAILED_CLOSED"

    def close(self) -> None:
        """Передаёт остановку владельцу фонового жизненного цикла."""
        self.manager.close()


def validate_notes_cli(path: str | os.PathLike[str] | None = None) -> int:
    """Синхронно проверяет источник, не создавая и не ожидая daemon-потоки."""
    try:
        parse_model_notes(
            read_model_notes_file(select_source(_configuration(path, None)))
        )
    except ValueError:
        print(
            "model-notes: FAILED_CLOSED (источник недоступен или некорректен)",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(validate_notes_cli())
