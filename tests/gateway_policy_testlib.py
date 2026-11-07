"""Общие оракулы C2 и параметры существующих RPC-сценариев."""

from __future__ import annotations

import io
import json
from unittest import mock
from typing import Any

import server
from tests.bridge_testlib import wait_until

HIGH_SETTINGS = dict(
    model="deepseek-v4.1-flash", reasoning_effort="high", autonomy="high"
)
OFF_SETTINGS = dict(
    modelId="deepseek-v4.1-flash", reasoningEffort="off", autonomyLevel="off"
)


def no_leaks(case: Any) -> bool:
    """Процессы, слоты и билеты вернулись к согласованному состоянию."""
    return wait_until(
        lambda: server.POOL.used == len(server._rpc_procs) and not server.POOL.queue
    )


def assert_deepseek_defaults(wire: Any) -> None:
    """Проверить реальный HTTP/RPC-путь и журнал безопасных умолчаний."""
    status, _, body = wire.call(
        {
            "model": "deepseek-v4.1-flash",
            "messages": [{"role": "user", "content": "default"}],
        },
        {"X-Request-Id": "req_deepseek_default"},
    )
    assert status == 200, body
    assert any(
        line.startswith(
            "exec model=deepseek-v4.1-flash effort=off effort_source=default autonomy=off autonomy_source=default"
        )
        and "request_id=req_deepseek_default" in line
        for line in wire.logs
    )


def install_route_auth(monkeypatch: Any, directory: Any, label: str) -> None:
    """Изолировать тот же TokenCache существующих HTTP-фикстур."""
    keys: dict[str, str] = dict.fromkeys(("AUTH_KEY", "BRIDGE_KEY"), "hub-test-key")
    cache = server.TokenCache(path=directory / f"missing-{label}.env", environ=keys)
    monkeypatch.setattr(server, "TOKEN_CACHE", cache)


def baseline_rename_count(mapping: dict[str, list[str]]) -> int:
    """Посчитать отображения baseline, которые действительно переименованы."""
    return sum(targets != [old] for old, targets in mapping.items())


def child_identity_entries(own: Any, foreign: Any) -> list[dict[str, Any]]:
    """Описать свою и заведомо чужую группы для прежнего оракула reconcile."""
    return [
        dict(
            pid=own.pid,
            pgid=own.pid,
            start=server._proc_start_sig(own.pid),
            bridge_pid=1,
            kind="muse",
        ),
        dict(
            pid=foreign.pid,
            pgid=foreign.pid,
            start="Mon Jan  1 00:00:00 1990",
            bridge_pid=1,
            kind="muse",
        ),
    ]


def orphan_registry_entries(
    own: Any, reused: Any, foreign: Any
) -> list[dict[str, Any]]:
    """Сохранить три исходных случая TM-013: своя, подменённая и неподписанная группа."""
    return [
        dict(pid=own.pid, start=server._proc_start_sig(own.pid), bridge_pid=1),
        dict(pid=reused.pid, start="Mon Jan  1 00:00:00 1990", bridge_pid=1),
        dict(pid=foreign.pid, start="", bridge_pid=1),
    ]


class NoServe:
    """Сервер без фоновых потоков для существующей проверки startup."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def serve_forever(self) -> None:
        return None

    server_close = serve_forever


def prepare_guard_drift(case: Any) -> None:
    """Сохранить прежний порядок настройки и отката фонового guard-теста."""
    case.write_profile(106496)
    case.addCleanup(setattr, server, "GUARD_TICK_S", server.GUARD_TICK_S)
    server.GUARD_TICK_S = 0.1
    case.addCleanup(setattr, server, "_shutting_down", server._shutting_down)


def restrict_probe_models(case: Any, module: Any, model: str, effort: str) -> None:
    """Оставить одну модель в существующих изолированных cycle-4 пробах."""
    case.enterContext(
        mock.patch.object(
            module,
            "load_droid_probe_targets",
            lambda *_: (module.ProbeTarget(model, effort),),
        )
    )


def preflight_handler(bypass: bool, model: str) -> Any:
    from email.message import Message
    import server

    instance: Any = object.__new__(server.Handler)
    instance.headers = Message()
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": "test"}]}
    ).encode()
    instance.headers["Content-Length"] = str(len(body))
    instance.headers["X-Idempotency-Key"] = "idempotent-step"
    if bypass:
        instance.headers["X-Bypass-Model-Filter"] = "1"
    instance.rfile = io.BytesIO(body)
    instance.wfile = io.BytesIO()
    instance.path = "/v1/chat/completions"
    instance.client_address = ("127.0.0.1", 1)
    instance.statuses = []
    instance.send_response = instance.statuses.append
    instance.send_header = lambda *_args: None
    instance.end_headers = lambda: None
    return instance
