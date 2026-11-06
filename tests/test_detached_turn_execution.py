import dataclasses
import http.client
import json
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from bridge_testlib import BridgeCase, load_raw_fleet, wait_until  # noqa: E402
from core.backend_adapter import (  # noqa: E402
    AdapterRegistry,
    ToolCall,
    ToolFunction,
    TurnResult,
    Usage,
)
from core.liveness_registry import (  # noqa: E402
    LivenessRegistry,
    get_registry,
    new_passthrough_turn_id,
)
from core.liveness_signals import (  # noqa: E402
    FLAG_TELEMETRY,
    LivenessSnapshot,
    LivenessWindow,
    WindowSpec,
)
from core.turn_session_manager import (  # noqa: E402
    TURN_ID_RE,
    TurnForbiddenError,
    TurnSessionManager,
    hash_owner_token,
)
from test_passthrough_adapter import FakeUpstream  # noqa: E402


class DetachedTurnExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._state_dir = self._tmp.name

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_client_disconnect_detaches_and_finishes_in_background(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        turn, existing = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "hello"}],
            session_id="sess-01",
            owner_token_hash="owner-a",
            requested_turn_id="turn-detach-01",
            stream=True,
        )
        self.assertFalse(existing)
        self.assertEqual(turn.status, "RUNNING_ATTACHED")

        turn.buffer.append("content", "Hello ")
        turn.mark_detached()
        self.assertEqual(turn.status, "RUNNING_DETACHED")

        turn.buffer.append("content", "world!")
        result = TurnResult(
            state="done",
            rc=0,
            text="Hello world!",
            reasoning="step-by-step",
            usage=Usage(input_tokens=12, output_tokens=6),
            tool_calls=(
                ToolCall(
                    index=0,
                    id="call-1",
                    function=ToolFunction(name="read_file", arguments='{"path":"a.py"}'),
                ),
            ),
        )
        manager.complete_turn_from_result(turn, result, backend_kind="droid")

        snap = manager.get_turn_snapshot("turn-detach-01", owner_token_hash="owner-a")
        self.assertEqual(snap["schema_version"], "1.0")
        self.assertEqual(snap["status"], "completed")
        self.assertEqual(snap["state"], "COMPLETED")
        self.assertEqual(snap["content"], "Hello world!")
        self.assertEqual(snap["reasoning_content"], "step-by-step")
        self.assertEqual(len(snap["tool_calls"]), 1)
        self.assertEqual(snap["usage"]["prompt_tokens"], 12)
        self.assertEqual(snap["usage"]["completion_tokens"], 6)

        turn_file = Path(self._state_dir) / "turns" / "turn-detach-01.json"
        self.assertTrue(turn_file.exists())
        mode = os.stat(turn_file).st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_idempotent_retry_and_resume_turn_id(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        t1, ex1 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            requested_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertFalse(ex1)

        t2, ex2 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            requested_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertTrue(ex2)
        self.assertIs(t1, t2)

        t3, ex3 = manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "retry-test"}],
            session_id="sess-02",
            owner_token_hash="owner-a",
            resume_turn_id="turn-idem-01",
            stream=True,
        )
        self.assertTrue(ex3)
        self.assertIs(t1, t3)

    def test_owner_isolation_enforced(self) -> None:
        manager = TurnSessionManager(state_root=self._state_dir)
        manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "secret"}],
            session_id="sess-03",
            owner_token_hash="owner-a",
            requested_turn_id="turn-own-01",
            stream=False,
        )
        with self.assertRaises(TurnForbiddenError):
            manager.get_turn_snapshot("turn-own-01", owner_token_hash="owner-b")


# ---- ADR-0015 / AD-003: реестр passthrough и optional `liveness` (VER-003) -------------
WIRE_KEYS = frozenset(
    {
        "internal_stream",
        "stream_requested",
        "last_token_age_s",
        "last_reasoning_age_s",
        "last_progress_kind",
        "last_keepalive_age_s",
        "process_alive",
        "soft_budget_used_s",
        "soft_budget_limit_s",
        "idle_remaining_s",
        "safety_cap_remaining_s",
    }
)
BASE_SNAPSHOT_KEYS = frozenset(
    {
        "schema_version",
        "turn_id",
        "turn_key",
        "rid",
        "model",
        "backend",
        "status",
        "state",
        "created_at",
        "updated_at",
        "oldest_available_seq",
        "last_seq",
        "reasoning_content",
        "content",
        "tool_calls",
        "usage",
        "error",
        "owner_token_hash",
    }
)
DYNAMIC_CFG_ENV = "BRIDGE_DYNAMIC_CONFIG_PATH"


def _window(**overrides) -> LivenessWindow:
    spec = dict(first_timeout_s=30.0, idle_timeout_s=30.0, safety_cap_s=300.0)
    spec.update(overrides)
    return LivenessWindow(WindowSpec(**spec))


class LivenessRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reg = LivenessRegistry()
        self.owner = hash_owner_token("owner-a")

    def test_register_and_snapshot_is_frozen_with_eleven_wire_keys(self) -> None:
        self.reg.register("t1", self.owner, _window(internal_stream=True, stream_requested=False))
        snap = self.reg.get_snapshot("t1", self.owner)
        self.assertIsInstance(snap, LivenessSnapshot)
        self.assertTrue(dataclasses.is_dataclass(snap))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            snap.internal_stream = False  # type: ignore[misc]
        wire = snap.to_wire()
        self.assertEqual(len(wire), 11)
        self.assertEqual(set(wire), WIRE_KEYS)
        self.assertIs(wire["internal_stream"], True)
        self.assertIs(wire["stream_requested"], False)
        self.assertEqual(wire["last_progress_kind"], "none")
        # passthrough не принимает P и не имеет процесса
        self.assertIsNone(wire["process_alive"])
        self.assertIsNone(wire["soft_budget_used_s"])
        self.assertIsNone(wire["soft_budget_limit_s"])

    def test_snapshot_is_detached_copy_not_live_entry(self) -> None:
        window = _window()
        self.reg.register("t1", self.owner, window)
        before = self.reg.get_snapshot("t1", self.owner)
        window.record_signal("S", frozenset({"content"}))
        after = self.reg.get_snapshot("t1", self.owner)
        self.assertEqual(before.last_progress_kind, "none")
        self.assertEqual(after.last_progress_kind, "S")
        self.assertIsNotNone(after.last_token_age_s)
        self.assertIsNone(after.last_reasoning_age_s)

    def test_signal_t_only_touches_keepalive_not_progress(self) -> None:
        window = _window()
        self.reg.register("t1", self.owner, window)
        window.record_signal("T")
        snap = self.reg.get_snapshot("t1", self.owner)
        self.assertEqual(snap.last_progress_kind, "none")
        self.assertIsNotNone(snap.last_keepalive_age_s)
        self.assertIsNone(snap.last_token_age_s)

    def test_foreign_owner_permission_error_unknown_key_error(self) -> None:
        self.reg.register("t1", self.owner, _window())
        with self.assertRaises(PermissionError):
            self.reg.get_snapshot("t1", hash_owner_token("owner-b"))
        with self.assertRaises(KeyError):
            self.reg.get_snapshot("nope", self.owner)

    def test_finish_removes_entry_and_is_idempotent(self) -> None:
        self.reg.register("t1", self.owner, _window())
        self.assertEqual(self.reg.active_count(), 1)
        self.assertTrue(self.reg.finish("t1"))
        self.assertFalse(self.reg.finish("t1"))
        self.assertFalse(self.reg.finish("never-registered"))
        self.assertEqual(self.reg.active_count(), 0)
        with self.assertRaises(KeyError):
            self.reg.get_snapshot("t1", self.owner)
        # чужой владелец после finish: тоже KeyError (наличие хода не раскрывается)
        with self.assertRaises(KeyError):
            self.reg.get_snapshot("t1", hash_owner_token("owner-b"))

    def test_registry_has_no_update_api_and_signals_go_to_window(self) -> None:
        """F-021: `update()` удалён — единственный путь сигнала это `LivenessWindow.record_signal`."""
        self.assertFalse(hasattr(self.reg, "update"))
        with self.assertRaises(KeyError):
            self.reg.get_snapshot("ghost", self.owner)

    def test_registry_keeps_only_id_owner_hash_and_window(self) -> None:
        raw_token = "raw-secret-token-NOT-REAL"
        self.reg.register("t1", hash_owner_token(raw_token), _window())
        entries = self.reg._entries
        self.assertEqual(set(entries), {"t1"})
        entry = entries["t1"]
        self.assertEqual(
            {f.name for f in dataclasses.fields(entry)}, {"owner_token_hash", "window"}
        )
        self.assertNotIn(raw_token, repr(entry))
        self.assertEqual(entry.owner_token_hash, hash_owner_token(raw_token))
        wire_text = json.dumps(self.reg.get_snapshot("t1", entry.owner_token_hash).to_wire())
        self.assertNotIn(raw_token, wire_text)
        self.assertNotIn(entry.owner_token_hash, wire_text)
        for name in WIRE_KEYS:
            self.assertFalse(re.search(r"token(?!_)|body|prompt|secret|hash", name), name)

    def test_new_passthrough_turn_id_matches_turn_id_re_and_is_unique(self) -> None:
        ids = {new_passthrough_turn_id() for _ in range(200)}
        self.assertEqual(len(ids), 200)
        for turn_id in ids:
            self.assertRegex(turn_id, TURN_ID_RE)
            self.assertTrue(server.validate_turn_id(turn_id))

    def test_get_registry_is_process_singleton(self) -> None:
        self.assertIs(get_registry(), get_registry())
        self.assertIsInstance(get_registry(), LivenessRegistry)

    def test_threadsafe_register_update_finish_ends_with_zero_active(self) -> None:
        errors: list[BaseException] = []
        barrier = threading.Barrier(16)

        def worker(n: int) -> None:
            try:
                barrier.wait(timeout=10)
                for i in range(60):
                    turn_id = f"t-{n}-{i}"
                    window = _window()
                    self.reg.register(turn_id, self.owner, window)
                    window.record_signal("S", frozenset({"content"}))
                    self.reg.get_snapshot(turn_id, self.owner)
                    self.assertTrue(self.reg.finish(turn_id))
            except BaseException as exc:  # noqa: BLE001 - собираем сбои потоков
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        self.assertEqual(errors, [])
        self.assertFalse([t for t in threads if t.is_alive()])
        self.assertEqual(self.reg.active_count(), 0)


class ManagedTurnLivenessTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.dict(
            os.environ, {DYNAMIC_CFG_ENV: str(Path(self._tmp.name) / "absent.json")}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(FLAG_TELEMETRY, None)
        self.manager = TurnSessionManager(state_root=self._tmp.name)

    def _turn(self, turn_id: str = "turn-live-01", stream: bool = False):
        turn, _ = self.manager.create_or_attach_turn(
            model="claude-4.6-opus",
            backend="droid",
            cwd="/tmp",
            messages=[{"role": "user", "content": "hello"}],
            session_id="sess-live",
            owner_token_hash="owner-a",
            requested_turn_id=turn_id,
            stream=stream,
        )
        return turn

    def test_default_snapshot_has_base_keys_without_liveness(self) -> None:
        turn = self._turn()
        snap = self.manager.get_turn_snapshot(turn.turn_id, owner_token_hash="owner-a")
        self.assertEqual(snap["schema_version"], "1.0")
        self.assertNotIn("liveness", snap)
        self.assertEqual(len(snap), 18)
        self.assertEqual(set(snap), BASE_SNAPSHOT_KEYS)

    def test_update_liveness_adds_optional_nineteenth_key_with_eleven_fields(self) -> None:
        turn = self._turn(stream=True)
        snapshot = LivenessSnapshot(
            internal_stream=False,
            stream_requested=None,
            last_progress_kind="S",
            idle_remaining_s=12.5,
            safety_cap_remaining_s=99.0,
        )
        turn.update_liveness(snapshot)
        snap = self.manager.get_turn_snapshot(turn.turn_id, owner_token_hash="owner-a")
        self.assertEqual(snap["schema_version"], "1.0")
        self.assertEqual(len(snap), 19)
        self.assertEqual(set(snap), BASE_SNAPSHOT_KEYS | {"liveness"})
        live = snap["liveness"]
        self.assertEqual(set(live), WIRE_KEYS)
        self.assertEqual(len(live), 11)
        self.assertEqual(live["last_progress_kind"], "S")
        self.assertEqual(live["idle_remaining_s"], 12.5)
        # stream_requested берётся у хода, а не из переданного снимка
        self.assertIs(live["stream_requested"], True)

    def test_stream_requested_follows_turn_stream_false(self) -> None:
        turn = self._turn(turn_id="turn-live-02", stream=False)
        turn.update_liveness(LivenessSnapshot(stream_requested=True))
        live = turn.to_snapshot_dict()["liveness"]
        self.assertIs(live["stream_requested"], False)

    def test_get_turn_snapshot_keeps_owner_check_with_liveness(self) -> None:
        turn = self._turn(turn_id="turn-live-03")
        turn.update_liveness(LivenessSnapshot())
        with self.assertRaises(TurnForbiddenError):
            self.manager.get_turn_snapshot(turn.turn_id, owner_token_hash="owner-b")
        self.assertIn(
            "liveness",
            self.manager.get_turn_snapshot(turn.turn_id, owner_token_hash="owner-a"),
        )

    def test_touch_activity_updates_liveness_only_when_telemetry_enabled(self) -> None:
        turn = self._turn(turn_id="turn-live-04")
        turn.touch_activity("protocol")
        self.assertNotIn("liveness", turn.to_snapshot_dict())
        self.assertIsNone(turn._liveness_snapshot)
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            turn.touch_activity("protocol")  # протокольный пульс — T: прогресс не засчитан
            self.assertEqual(turn.to_snapshot_dict()["liveness"]["last_progress_kind"], "none")
            turn.touch_activity("content")  # фактический тип события -> S (F-016)
        live = turn.to_snapshot_dict()["liveness"]
        self.assertEqual(set(live), WIRE_KEYS)
        self.assertEqual(live["last_progress_kind"], "S")
        self.assertIsNotNone(live["last_token_age_s"])
        # CLI-ход: процессные поля присутствуют (не passthrough)
        self.assertIsNotNone(live["soft_budget_limit_s"])
        # флаг выключен снова: обновления снимка прекращаются, прежнее значение не меняется
        frozen = turn._liveness_snapshot
        turn.touch_activity("content")
        self.assertIs(turn._liveness_snapshot, frozen)

    def test_managed_turn_liveness_state_is_one_frozen_reference_without_own_lock(self) -> None:
        """F-008: фича не добавляет в `ManagedTurn` Lock — только frozen-срез (подмена ссылки атомарна)."""
        import copy
        import dataclasses

        names = {f.name for f in dataclasses.fields(type(self._turn(turn_id="turn-live-copy"))) if "liveness" in f.name}
        self.assertEqual(names, {"_liveness_snapshot"})
        turn = self._turn(turn_id="turn-live-copy2")
        turn.update_liveness(LivenessSnapshot(last_progress_kind="S"))
        snap = turn._liveness_snapshot
        self.assertEqual(dataclasses.asdict(snap)["last_progress_kind"], "S")
        self.assertEqual(copy.deepcopy(snap), snap)
        json.dumps(turn.to_snapshot_dict())  # wire-срез сериализуем без блокировок

    def test_touch_activity_detached_does_not_touch_liveness(self) -> None:
        turn = self._turn(turn_id="turn-live-05")
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            turn.touch_activity("detached")
        self.assertEqual(turn.status, "RUNNING_DETACHED")
        self.assertIsNone(turn._liveness_snapshot)


class HubLivenessTelemetryTests(BridgeCase):
    """AD-003 на HTTP-уровне: passthrough-ход через реальный хаб и FakeUpstream."""

    MODEL = "gpt-6.1-terra"

    def setUp(self) -> None:
        super().setUp()
        patcher = mock.patch.dict(
            os.environ, {DYNAMIC_CFG_ENV: str(Path(self._tmp.name) / "absent.json")}
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in (FLAG_TELEMETRY, "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED"):
            os.environ.pop(name, None)
        self.upstream = FakeUpstream()
        self.addCleanup(self.upstream.close)
        data = load_raw_fleet()
        data["backends"]["codex"]["enabled"] = True
        data["backends"]["codex"]["base_url"] = "http://127.0.0.1:%d/v1" % self.upstream.port
        data["backends"]["codex"].pop("api_key_env", None)
        server.FLEET = server._build_catalog(data)
        saved = server.BACKENDS
        self.addCleanup(setattr, server, "BACKENDS", saved)
        server.BACKENDS = AdapterRegistry.from_fleet(
            server.FLEET, ADAPTER_KINDS, lambda: server.FLEET, server
        )
        self.gate = threading.Event()
        self.addCleanup(self.gate.set)
        self.addCleanup(self._drop_registry_entries)
        self.seen_ids: list[str] = []
        real_new_id = server.new_passthrough_turn_id

        def capture() -> str:
            turn_id = real_new_id()
            self.seen_ids.append(turn_id)
            return turn_id

        patcher = mock.patch.object(server, "new_passthrough_turn_id", capture)
        patcher.start()
        self.addCleanup(patcher.stop)

    def assert_registry_drains(self, expected: int = 0) -> None:
        """Запись удаляется в `finally` хаба сразу после ответа: ждём без гонки с клиентом."""
        self.assertTrue(
            wait_until(lambda: get_registry().active_count() == expected, timeout=10),
            "активных записей реестра: %d" % get_registry().active_count(),
        )

    def _drop_registry_entries(self) -> None:
        for turn_id in self.seen_ids:
            get_registry().finish(turn_id)

    def _held_upstream(self) -> None:
        def respond(handler, body):
            self.gate.wait(20)
            FakeUpstream.json(handler, {"id": "x", "object": "chat.completion", "choices": []})

        self.upstream.respond = respond

    def _body(self) -> dict:
        return {"model": self.MODEL, "messages": [{"role": "user", "content": "hi"}]}

    def _post_raw(self, extra_headers=None, out=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=40)
        try:
            headers = {"Content-Type": "application/json", "Authorization": "Bearer test-key"}
            headers.update(extra_headers or {})
            conn.request("POST", "/v1/chat/completions", body=json.dumps(self._body()), headers=headers)
            resp = conn.getresponse()
            result = (resp.status, dict(resp.getheaders()), resp.read())
        except BaseException as exc:  # noqa: BLE001 - исход для проверки потоком теста
            result = exc
        if out is not None:
            out.append(result)
        return result

    def _get_turn(self, turn_id: str, extra_headers=None, auth="Bearer test-key"):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        try:
            headers = {"Authorization": auth} if auth else {}
            headers.update(extra_headers or {})
            conn.request("GET", "/v1/turns/" + turn_id, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8")
            return resp.status, (json.loads(raw) if raw else None)
        finally:
            conn.close()

    def _start_held_post(self, extra_headers=None):
        out: list = []
        thread = threading.Thread(target=self._post_raw, args=(extra_headers, out), daemon=True)
        thread.start()
        self.assertTrue(
            wait_until(lambda: bool(self.upstream.requests), timeout=15),
            "upstream не получил запрос",
        )
        return thread, out

    def _finish_post(self, thread, out):
        self.gate.set()
        thread.join(timeout=30)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(out), 1)
        return out[0]

    def test_telemetry_off_has_no_header_no_id_and_empty_registry(self) -> None:
        self.upstream.respond = lambda h, b: FakeUpstream.json(h, {"id": "x", "choices": []})
        before = get_registry().active_count()
        status, headers, _ = self._post_raw()
        self.assertEqual(status, 200)
        self.assertNotIn("x-turn-id", {k.lower() for k in headers})
        self.assertEqual(self.seen_ids, [])
        self.assert_registry_drains(before)

    def test_telemetry_off_lookup_of_arbitrary_id_is_404(self) -> None:
        status, body = self._get_turn("pt-" + "0" * 32)
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["type"], "not_found")

    def test_telemetry_on_live_lookup_owner_and_cleanup(self) -> None:
        self._held_upstream()
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            thread, out = self._start_held_post()
            self.assertEqual(len(self.seen_ids), 1)
            turn_id = self.seen_ids[0]
            self.assertRegex(turn_id, TURN_ID_RE)
            self.assertEqual(get_registry().active_count(), 1)
            status, snap = self._get_turn(turn_id)
            self.assertEqual(status, 200, snap)
            live = snap["liveness"]
            self.assertEqual(set(live), WIRE_KEYS)
            self.assertEqual(len(live), 11)
            self.assertEqual(snap["turn_id"], turn_id)
            self.assertEqual(snap["schema_version"], "1.0")
            self.assertIs(live["stream_requested"], False)
            self.assertIs(live["internal_stream"], False)
            self.assertEqual(live["last_progress_kind"], "none")
            self.assertIsNone(live["process_alive"])
            self.assertIsNone(live["soft_budget_limit_s"])
            self.assertGreater(live["idle_remaining_s"], 0)
            self.assertGreater(live["safety_cap_remaining_s"], 0)
            # raw-токен и его хеш наружу не возвращаются
            raw = json.dumps(snap)
            self.assertNotIn("test-key", raw)
            self.assertNotIn(hash_owner_token("test-key"), raw)
            # чужой владелец -> 403, несуществующий -> 404, невалидный -> 400
            status, body = self._get_turn(turn_id, extra_headers={"X-Turn-Owner-Token": "intruder"})
            self.assertEqual((status, body["error"]["type"]), (403, "forbidden"))
            status, body = self._get_turn("pt-" + "f" * 32)
            self.assertEqual((status, body["error"]["type"]), (404, "not_found"))
            status, body = self._get_turn("bad%20id")
            self.assertEqual((status, body["error"]["type"]), (400, "invalid_request"))
            status, headers, _ = self._finish_post(thread, out)
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("X-Turn-Id"), turn_id)
        self.assert_registry_drains()
        status, _ = self._get_turn(turn_id)
        self.assertEqual(status, 404)

    def test_telemetry_on_foreign_authorization_gets_403(self) -> None:
        self._held_upstream()
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            thread, out = self._start_held_post()
            turn_id = self.seen_ids[0]
            with mock.patch.object(server, "_auth_ok", return_value=True):
                status, _ = self._get_turn(turn_id, auth="Bearer another-token")
            self.assertEqual(status, 403)
            self._finish_post(thread, out)

    def test_owner_header_has_priority_over_authorization(self) -> None:
        self._held_upstream()
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            thread, out = self._start_held_post(extra_headers={"X-Turn-Owner-Token": "owner-A"})
            turn_id = self.seen_ids[0]
            # тот же Authorization без заголовка владельца -> чужой ход
            self.assertEqual(self._get_turn(turn_id)[0], 403)
            # заголовок владельца совпал -> 200, даже при другом Authorization-результате
            status, snap = self._get_turn(turn_id, extra_headers={"X-Turn-Owner-Token": "owner-A"})
            self.assertEqual(status, 200, snap)
            self.assertIn("liveness", snap)
            self._finish_post(thread, out)

    def test_cleanup_on_upstream_http_error(self) -> None:
        self.upstream.respond = lambda h, b: FakeUpstream.json(
            h, {"error": {"message": "boom"}}, status=500
        )
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            status, headers, _ = self._post_raw()
        self.assertEqual(status, 500)
        self.assertEqual(len(self.seen_ids), 1)
        self.assertEqual(headers.get("X-Turn-Id"), self.seen_ids[0])
        self.assert_registry_drains()
        self.assertEqual(self._get_turn(self.seen_ids[0])[0], 404)

    def test_cleanup_on_upstream_connection_drop(self) -> None:
        def drop(handler, body):
            handler.connection.shutdown(socket.SHUT_RDWR)

        self.upstream.respond = drop
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            result = self._post_raw()
        self.assertIsInstance(result, tuple, result)
        self.assertGreaterEqual(result[0], 500)
        self.assertEqual(len(self.seen_ids), 1)
        self.assert_registry_drains()

    def test_cleanup_on_upstream_timeout(self) -> None:
        self._held_upstream()
        env = {FLAG_TELEMETRY: "true", "BRIDGE_TOTAL_TIMEOUT_S": "1"}
        with mock.patch.dict(os.environ, env):
            started = time.monotonic()
            status, _, _ = self._post_raw()
            elapsed = time.monotonic() - started
            self.assertEqual(len(self.seen_ids), 1)
        self.assertEqual(status, 504)
        self.assertLess(elapsed, 15)
        self.gate.set()
        self.assert_registry_drains()
        self.assertEqual(self._get_turn(self.seen_ids[0])[0], 404)

    def test_cleanup_on_client_disconnect(self) -> None:
        self._held_upstream()
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            sock = socket.create_connection(("127.0.0.1", self.port), timeout=10)
            try:
                payload = json.dumps(self._body()).encode()
                sock.sendall(
                    (
                        "POST /v1/chat/completions HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                        "Content-Type: application/json\r\nAuthorization: Bearer test-key\r\n"
                        "Content-Length: %d\r\n\r\n" % len(payload)
                    ).encode()
                    + payload
                )
                self.assertTrue(wait_until(lambda: bool(self.upstream.requests), timeout=15))
                self.assertEqual(get_registry().active_count(), 1)
            finally:
                sock.close()  # обрыв клиента во время ожидания upstream
            self.assertTrue(
                wait_until(lambda: get_registry().active_count() == 0, timeout=20),
                "запись реестра не удалена после обрыва клиента",
            )
            self.gate.set()
        self.assertEqual(self._get_turn(self.seen_ids[0])[0], 404)

    def test_owner_token_value_is_not_echoed_in_response_or_wire(self) -> None:
        """Значение X-Turn-Owner-Token и его хеш не возвращаются клиенту ни в ответе, ни в `liveness`."""
        secret = "owner-secret-NOT-REAL"
        self._held_upstream()
        with mock.patch.dict(os.environ, {FLAG_TELEMETRY: "true"}):
            thread, out = self._start_held_post(extra_headers={"X-Turn-Owner-Token": secret})
            status, snap = self._get_turn(
                self.seen_ids[0], extra_headers={"X-Turn-Owner-Token": secret}
            )
            self.assertEqual(status, 200)
            wire = json.dumps(snap)
            self.assertNotIn(secret, wire)
            self.assertNotIn(hash_owner_token(secret), wire)
            status, headers, body = self._finish_post(thread, out)
        self.assertEqual(status, 200)
        self.assertNotIn(secret, json.dumps(headers) + body.decode("utf-8"))
        self.assert_registry_drains()


    def test_internal_stream_reports_s_progress_and_t_keepalive_in_liveness(self) -> None:
        """AD-001+AD-003: при внутреннем SSE полезный чанк (S) и пульс (T) видны в `liveness`."""

        def chunk(delta: dict, finish=None) -> bytes:
            payload = {
                "id": "c1", "object": "chat.completion.chunk", "created": 1, "model": "m",
                "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
            }
            return b"data: " + json.dumps(payload).encode() + b"\n\n"

        def respond(handler, body):
            handler.send_response(200)
            handler.send_header("Content-Type", "text/event-stream")
            handler.end_headers()
            handler.wfile.write(b": keepalive\n\n" + chunk({"content": "Hel"}))
            handler.wfile.flush()
            self.gate.wait(20)
            handler.wfile.write(chunk({"content": "lo"}, "stop") + b"data: [DONE]\n\n")
            handler.wfile.flush()

        self.upstream.respond = respond
        env = {FLAG_TELEMETRY: "true", "BRIDGE_NONSTREAM_VIA_STREAM_ENABLED": "true"}
        with mock.patch.dict(os.environ, env):
            thread, out = self._start_held_post()
            turn_id = self.seen_ids[0]
            live = {}

            def seen_s() -> bool:
                nonlocal live
                status, snap = self._get_turn(turn_id)
                live = snap.get("liveness", {}) if status == 200 else {}
                return live.get("last_progress_kind") == "S"

            self.assertTrue(wait_until(seen_s, timeout=10), live)
            self.assertIs(live["internal_stream"], True)
            self.assertIs(live["stream_requested"], False)
            self.assertIsNotNone(live["last_token_age_s"])
            self.assertIsNotNone(live["last_keepalive_age_s"])
            self.assertIsNone(live["last_reasoning_age_s"])
            self.assertIsNone(live["process_alive"])
            status, headers, body = self._finish_post(thread, out)
        self.assertEqual(status, 200)
        completion = json.loads(body)
        self.assertEqual(completion["object"], "chat.completion")
        self.assertEqual(completion["choices"][0]["message"]["content"], "Hello")
        self.assert_registry_drains()


class OwnerTokenHashContractTests(unittest.TestCase):
    """`server._owner_token_hash`: единый owner-контракт CLI и passthrough."""

    @staticmethod
    def _handler(headers: dict[str, str]):
        from types import SimpleNamespace

        class _Headers(dict):
            def get(self, key, default=None):
                for name, value in self.items():
                    if name.lower() == key.lower():
                        return value
                return default

        return SimpleNamespace(headers=_Headers(headers))

    def test_explicit_owner_header_wins_over_authorization(self) -> None:
        h = self._handler({"X-Turn-Owner-Token": "own", "Authorization": "Bearer other"})
        self.assertEqual(server._owner_token_hash(h), hash_owner_token("own"))

    def test_authorization_bearer_prefix_is_stripped(self) -> None:
        h = self._handler({"Authorization": "Bearer tok-1"})
        self.assertEqual(server._owner_token_hash(h), hash_owner_token("tok-1"))

    def test_blank_owner_header_falls_back_to_authorization(self) -> None:
        h = self._handler({"X-Turn-Owner-Token": "   ", "Authorization": "Bearer tok-2"})
        self.assertEqual(server._owner_token_hash(h), hash_owner_token("tok-2"))

    def test_no_headers_falls_back_to_hub_key(self) -> None:
        h = self._handler({})
        with mock.patch.object(server, "AUTH_KEY", "hub-key-NOT-REAL"):
            self.assertEqual(server._owner_token_hash(h), hash_owner_token("hub-key-NOT-REAL"))


if __name__ == "__main__":
    unittest.main()
