"""Базовый класс тестов serve-транспорта с фикстурами FakeServe."""

from __future__ import annotations

import json
import os
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast
from unittest import mock

if TYPE_CHECKING:
    from typing import override
else:
    _OverrideT = TypeVar("_OverrideT")

    def override(method: _OverrideT) -> _OverrideT:
        """Сохранить декорируемый метод на Python без typing.override."""
        return method

import server
from tests.test_realtime_reasoning import (
    FAKE_SERVE,
    LEGACY_FAKE,
    MODEL,
    _Bridge,
    _FailingWfile,
    _FakeSock,
    _Patcher,
    _as_obj_dict,
    _deltas,
    _tool_names,
    _write_exe,
)

__all__ = [
    "BaseServeTest",
    "FAKE_SERVE",
    "LEGACY_FAKE",
    "MODEL",
    "_Bridge",
    "_FailingWfile",
    "_FakeSock",
    "_Patcher",
    "_as_obj_dict",
    "_callback",
    "_deltas",
    "_fake_result",
    "_tool_names",
    "_write_exe",
    "cast",
    "mock",
]


def _fake_result(**over: object) -> dict[str, object]:
    """Результат попытки serve для подмены `_serve_one_attempt`."""
    base: dict[str, object] = {
        "reasonings": [],
        "texts": [],
        "native_calls": [],
        "usage": {},
        "error": None,
        "exit_reason": "",
        "delivered": False,
        "terminal": "",
        "first_event_at": None,
        "first_token_at": None,
        "step_closed": False,
        "first_event_ms": None,
        "ttft_ms": None,
        "prompt_status": None,
        "transient_error": False,
    }
    base.update(over)
    return base


def _callback(args: tuple[object, ...], index: int) -> Callable[[str], None]:
    """Колбэк `_serve_one_attempt` по позиции (4 reasoning, 5 text)."""
    return cast("Callable[[str], None]", args[index])


class BaseServeTest(unittest.TestCase):
    """Базовый класс тестов serve-транспорта с инициализацией FakeServe."""

    bridge: _Bridge = cast(_Bridge, None)
    tmp: Path = Path()
    fake: Path = Path()
    cfg: Path = Path()
    saved_cfg: Path = Path()
    saved_lease: Path = Path()
    _had_dyn_cfg: bool = False
    _had_lease: bool = False
    env: object = None

    @override
    def setUp(self) -> None:
        self.bridge = _Bridge()
        self.tmp = Path(self.bridge.tmp.name)
        self.fake = _write_exe(self.tmp, "opencode-serve", FAKE_SERVE)
        server.OPENCODE_BIN = str(self.fake)
        self.cfg = self.tmp / "dynamic_config.json"
        _ = self.cfg.write_text(json.dumps({"REALTIME_SERVE_ENABLED": True}), "utf-8")
        self._had_dyn_cfg = hasattr(server, "DYNAMIC_CONFIG_PATH")
        self.saved_cfg = getattr(
            server, "DYNAMIC_CONFIG_PATH", self.tmp / "missing_dyn.json"
        )
        server.DYNAMIC_CONFIG_PATH = self.cfg
        self._had_lease = hasattr(server, "LEASE_DIR")
        self.saved_lease = getattr(server, "LEASE_DIR", self.tmp / "missing_leases")
        server.LEASE_DIR = self.tmp / "leases"
        self.env = mock.patch.dict(
            os.environ,
            {
                "OPENCODE_ZEN_BRIDGE_TRANSPORT": "serve",
                "HOME": str(self.tmp / "empty-home"),
            },
            clear=False,
        )
        _ = cast(_Patcher, self.env).start()
        (self.tmp / "empty-home").mkdir(exist_ok=True)

    @override
    def tearDown(self) -> None:
        _ = cast(_Patcher, self.env).stop()
        if self._had_dyn_cfg:
            server.DYNAMIC_CONFIG_PATH = self.saved_cfg
        else:
            delattr(server, "DYNAMIC_CONFIG_PATH")
        if self._had_lease:
            server.LEASE_DIR = self.saved_lease
        else:
            delattr(server, "LEASE_DIR")
        self.bridge.close()

    def _auto_mode(self) -> None:
        """auto + eligible: serve выбирается для скриптового FakeServe."""
        saved = server.SERVE_TEST_ELIGIBLE
        server.SERVE_TEST_ELIGIBLE = True
        self.addCleanup(setattr, server, "SERVE_TEST_ELIGIBLE", saved)
        os.environ["OPENCODE_ZEN_BRIDGE_TRANSPORT"] = "auto"

    def _patched_attempts(
        self, plan: list[Callable[[tuple[object, ...]], dict[str, object]]]
    ) -> tuple[list[tuple[object, ...]], mock._patch[mock.MagicMock]]:
        calls: list[tuple[object, ...]] = []
        queue_plan = list(plan)

        def fake(*args: object, **_kw: object) -> dict[str, object]:
            calls.append(args)
            return queue_plan.pop(0)(args)

        return calls, mock.patch.object(server, "_serve_one_attempt", side_effect=fake)

    def _c6_scenario(self, scenario: str, counter: Path) -> None:
        """Один сценарий с общим счётчиком попыток для настоящих serve и run."""
        fragment = r"""
            counter=Path(COUNTER)
            n=int(counter.read_text()) if counter.exists() else 0
            counter.write_text(str(n+1))
            scenario=SCENARIO
            if n==0 or scenario=="budget":
                if scenario=="unmapped":
                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":"Проверяю файлы."}})
                if scenario in ("text","broken","budget","transient"):
                    text=("Проверяю файлы..." if scenario=="text" else "Проверяю файлы.") + ('<tool_call>{"name":"bash","arguments":' if scenario in ("broken","budget") else "")
                    emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":text}})
                elif scenario=="reasoning":
                    emit({"type":"session.reasoning.delta","data":{"sessionID":sid,"delta":"I need to call bash next."}})
                elif scenario=="native":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"bash","input":{"command":"pwd"}}})
                elif scenario=="unmapped":
                    emit({"type":"session.tool.called","data":{"sessionID":sid,"id":"nc1","name":"todoread","input":{}}})
                if scenario in ("native","unmapped"):
                    emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
                if scenario=="native": time.sleep(2); return
                if scenario=="transient":
                    emit({"type":"session.execution.failed","data":{"sessionID":sid,"error":{"message":"overloaded","status":503}}}); return
            else:
                emit({"type":"session.text.delta","data":{"sessionID":sid,"delta":("Проверяю файлы... Ответ" if scenario=="text" else "Проверяю файлы. Ответ")}})
                emit({"type":"session.step.ended","data":{"sessionID":sid,"tokens":{"input":1,"output":1,"reasoning":0,"cache":{"read":0}}}})
            emit({"type":"session.execution.succeeded","data":{"sessionID":sid}}); return
""".replace("COUNTER", repr(str(counter))).replace("SCENARIO", repr(scenario))
        body = FAKE_SERVE.replace(
            '            if "__native_pause__" in prompt:',
            fragment + '            if "__native_pause__" in prompt:',
        )
        _ = self.fake.write_text(body)

    def _c6_response(self, stream: bool) -> tuple[str, str]:
        """Вернуть собранный текст и finish_reason обеих форм ответа."""
        if stream:
            chunks, _ = self.bridge.post_stream_timed("проверь файлы")
            text = "".join(t for _, t in _deltas(chunks, "content"))
            finish = ""
            for _, chunk in chunks:
                choices = cast("list[object]", chunk.get("choices") or [])
                if choices:
                    value = _as_obj_dict(choices[0]).get("finish_reason")
                    if isinstance(value, str):
                        finish = value
            return text, finish
        status, body = self.bridge.post_json("проверь файлы")
        self.assertEqual(status, 200, body)
        choice = _as_obj_dict(cast("list[object]", body["choices"])[0])
        return str(_as_obj_dict(choice.get("message")).get("content") or ""), str(
            choice.get("finish_reason")
        )

    def _c13_security_protocol_matrix(self, drain: bool) -> None:
        """Сбой любого security control завершает одну попытку без run/fallback."""
        from tests.serve_test_matrix_helpers import execute_security_protocol_matrix

        execute_security_protocol_matrix(
            self, drain, self.fake, self.bridge, FAKE_SERVE
        )

    def _c13_run_retry_http(self, *, timings: bool) -> None:
        """Пройти Run.execute и HTTP JSON с двумя внутренними попытками."""
        from tests.serve_test_matrix_helpers import execute_run_retry_http

        execute_run_retry_http(self, self.bridge, timings=timings)
