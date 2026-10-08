"""Регрессионные тесты cycle-4 rework (RW-005…RW-023, серверная часть): каждый красный на коде ad4c456.

Сценарии идут через настоящий HTTP-сервер моста и fake-subprocess (tests/fake_droid.py) либо напрямую
через Run._on_notif (корреляция событий хода). Реальный droid, сеть и боевые профили не используются.
Идентификаторы RW-NNN — в имени метода и docstring.
"""

import json
import os
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import server  # noqa: E402
from bridge_testlib import wait_until  # noqa: E402
from rpc_testlib import FakeClock, RpcCase  # noqa: E402
from test_images_strict import ImageCase  # noqa: E402
from test_rpc_cycle3 import GuardCase  # noqa: E402
from test_rpc_rework import BODY, msg, no_leaks, post_safely  # noqa: E402

HEAD = "Instructions from: /x/AGENTS.md\n"


def note(ntype, **fields):
    return {"sessionId": "sid-x", "notification": dict(fields, type=ntype)}


def user_create(with_ids=True):
    message = {"role": "user", "content": [{"type": "text", "text": "q"}]}
    fields = {"requestId": "r1"}
    if with_ids:
        message["id"] = "turn-1"
        fields["messageId"] = "turn-1"
    return note("create_message", message=message, **fields)


def asst_create(mid, parent, text="T"):
    return note(
        "create_message",
        messageId=mid,
        message={
            "id": mid,
            "role": "assistant",
            "parentId": parent,
            "content": [{"type": "text", "text": text}],
        },
    )


def terminal(turn_id="turn-1"):
    return note(
        "agent_turn_completed",
        turnId=turn_id,
        reason="completed",
        tokenUsage={"inputTokens": 1, "outputTokens": 1},
    )


def stub_proc():
    return types.SimpleNamespace(
        finished_turns=set(),
        finished_mids=set(),
        err_box=[],
        note_turn=lambda *_a, **_k: None,
    )


class RunCase(RpcCase):
    """Run без воркера: события подаются в _on_notif напрямую."""

    def make_run(self, path="cold", proc=None, droid_real=3):
        plan = {"path": path, "sid": "sid-x", "droid_real": droid_real}
        with mock.patch.object(server.Run, "_work", lambda self: None):
            run = server.Run(plan, proc, False)
        run.turn_req_id = "r1"
        run.sent = True
        run.sid = "sid-x"
        return run

    @staticmethod
    def drain(run):
        items = []
        while not run.q.empty():
            items.append(run.q.get_nowait())
        return items


class TestUnknownEvents(RunCase):
    """RW-005/RW-006: неизвестные события после arming не принимаются за текущий ход."""

    PATHS = ("cold", "hot", "restore")

    def _proc_for(self, path):
        return stub_proc() if path == "hot" else None

    def test_rw005_unknown_mid_and_parent_do_not_create_slot_or_progress(self):
        """RW-005: delta/complete неизвестного mid и create с неизвестным parent: нет слота, прогресса и текста."""
        for path in self.PATHS:
            with self.subTest(path):
                run = self.make_run(path, self._proc_for(path))
                self.assertFalse(run._on_notif(user_create()))
                progress = run.last_progress
                real = run.droid_real
                for event in (
                    note("assistant_text_delta", messageId="ghost", textDelta="GHOST"),
                    note("assistant_text_complete", messageId="ghost", text="GHOST"),
                    note("thinking_text_delta", messageId="ghost-t", textDelta="GHOST"),
                    asst_create("ghost-m", "turn-ghost", "GHOST"),
                    asst_create("ghost-e", "", "GHOST"),
                ):
                    self.assertFalse(run._on_notif(event))
                self.assertEqual(run._msgs, {})
                self.assertEqual(run.last_progress, progress)
                self.assertEqual(run.droid_real, real)
                run._on_notif(asst_create("m1", "turn-1", "OWN"))
                self.assertTrue(run._on_notif(terminal()))
                texts = [
                    value
                    for kind, value in self.drain(run)
                    if kind in ("text", "reasoning")
                ]
                self.assertEqual(texts, ["OWN"])

    def test_rw005_own_deltas_before_create_are_promoted_once(self):
        """RW-005: собственные дельты, пришедшие до create_message, не теряются и не дублируются."""
        run = self.make_run()
        run._on_notif(user_create())
        run._on_notif(note("assistant_text_delta", messageId="m1", textDelta="OW"))
        run._on_notif(note("assistant_text_delta", messageId="m1", textDelta="N"))
        self.assertEqual(run._msgs, {})
        run._on_notif(asst_create("m1", "turn-1", "OWN"))
        run._on_notif(
            asst_create("m2", "m1", "NEXT")
        )  # цепочка parent -> собственное сообщение
        self.assertTrue(run._on_notif(terminal()))
        texts = [value for kind, value in self.drain(run) if kind == "text"]
        self.assertEqual(texts, ["OWN", "NEXT"])

    def test_rw005_user_create_without_id_confirms_nothing(self):
        """RW-005/RW-006: user create без id -> parent не подтверждён, терминал не принимается."""
        run = self.make_run()
        run._on_notif(user_create(with_ids=False))
        self.assertEqual(run.active_turn, "")
        progress = run.last_progress
        run._on_notif(asst_create("m1", "turn-1", "NOT-CONFIRMED"))
        self.assertEqual(run._msgs, {})
        self.assertFalse(run._on_notif(terminal("turn-unknown")))
        self.assertEqual(run.last_progress, progress)
        self.assertEqual(self.drain(run), [])

    def test_rw006_empty_active_turn_rejects_unknown_terminal_and_keeps_watchdog(self):
        """RW-006: active_turn пуст + terminal с незнакомым turnId: ход не завершён, watchdog не сброшен."""
        run = self.make_run()
        run._on_notif(user_create(with_ids=False))
        progress = run.last_progress
        self.assertFalse(run._on_notif(terminal("turn-never-seen")))
        self.assertEqual(run.last_progress, progress)
        self.assertEqual(self.drain(run), [])

    def test_rw006_confirmed_terminal_still_completes(self):
        """RW-006: контроль: подтверждённый turnId завершает ход."""
        run = self.make_run()
        run._on_notif(user_create())
        run._on_notif(asst_create("m1", "turn-1", "OK"))
        self.assertTrue(run._on_notif(terminal()))
        self.assertEqual([v for k, v in self.drain(run) if k == "text"], ["OK"])


class TestUnknownEventsLive(RpcCase):
    """RW-005: тот же сценарий через живой fake_droid, включая restore (finished_* пусты)."""

    def test_rw005_ghost_events_on_restore_path_do_not_reach_answer(self):
        """RW-005: после idle->restore ghost-message и ghost-delta не попадают в ответ и не меняют usage."""
        clock = FakeClock(1000.0)
        server._clock = clock
        self.hub.script(
            [
                {"steps": [{"op": "text", "text": "A0"}]},
                {
                    "steps": [
                        {"op": "ghost_message"},
                        {"op": "ghost_delta"},
                        {"op": "text", "text": "A1"},
                    ],
                    "usage": {"inputTokens": 21, "outputTokens": 2},
                },
            ]
        )
        chat = self.conv("chat-ghost")
        self.assertEqual(chat.ask("q0")[0], 200)
        clock.advance(2700)
        self.assertEqual(len(server.REGISTRY.reap_once()), 1)
        status, body = chat.ask("q1")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), 1)
        self.assertEqual(body["choices"][0]["message"]["content"], "A1")
        self.assertEqual(body["usage"]["prompt_tokens"], 21)


class TestHistoryCounter(RunCase):
    """RW-007: поздний create_message завершённого assistant не меняет счётчик истории."""

    def test_rw007_late_create_of_finished_assistant_does_not_count(self):
        """RW-007: mid/parent прежнего хода (до и после arming) droid_real не увеличивают; собственное — да."""
        proc = stub_proc()
        proc.finished_mids.add("m-old")
        proc.finished_turns.add("turn-0")
        run = self.make_run("hot", proc, droid_real=3)
        run._on_notif(asst_create("m-old", "turn-0", "LATE"))
        self.assertEqual(run.droid_real, 3)
        run._on_notif(user_create())
        self.assertEqual(run.droid_real, 4)  # user текущего хода учитывается
        run._on_notif(asst_create("m-old", "turn-0", "LATE"))
        run._on_notif(asst_create("ghost", "turn-ghost", "LATE"))
        self.assertEqual(run.droid_real, 4)
        run._on_notif(asst_create("m1", "turn-1", "OWN"))
        self.assertEqual(run.droid_real, 5)

    def test_rw007_stale_message_then_idle_load_keeps_sid(self):
        """RW-007: два хода, поздний create_message, idle, load_session: тот же SID, без HISTORY_MISMATCH."""
        clock = FakeClock(1000.0)
        server._clock = clock
        self.hub.script(
            [
                {"steps": [{"op": "text", "text": "A0"}]},
                {"steps": [{"op": "stale_message"}, {"op": "text", "text": "A1"}]},
                {"steps": [{"op": "text", "text": "A2"}]},
            ]
        )
        chat = self.conv("chat-hist")
        self.assertEqual(chat.ask("q0")[0], 200)
        self.assertEqual(chat.ask("q1")[0], 200)
        state = self.chat_of("chat-hist")
        sid = state.sid
        clock.advance(2700)
        self.assertEqual(len(server.REGISTRY.reap_once()), 1)
        self.assertEqual(chat.ask("q2")[0], 200)
        self.assertEqual(state.sid, sid)
        self.assertEqual(len(self.hub.inits()), 1)
        self.assertEqual(len(self.hub.rpcs("droid.load_session")), 1)


def _inject_start_failure(case, targets):
    """Thread.start бросает RuntimeError для потоков с target из targets (закрытие процессов)."""
    real = threading.Thread.start

    def flaky(thread):
        target = getattr(thread, "_target", None)
        if getattr(target, "__func__", target) in targets:
            raise RuntimeError("can't start new thread")
        return real(thread)

    patcher = mock.patch.object(threading.Thread, "start", flaky)
    patcher.start()
    case.addCleanup(patcher.stop)


class TestCloseFallback(RpcCase):
    """RW-008: сбой Thread.start при закрытии процесса не оставляет процесс и слот P."""

    def test_rw008_ephemeral_success_closes_child_synchronously(self):
        """RW-008: nokey-ход успешен, start закрывающего потока падает: ребёнок убит, P свободен, следующий ход идёт."""
        _inject_start_failure(self, {server.RpcProcess.close})
        status, _ = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 200)
        pid = self.hub.spawns()[0]["pid"]
        self.assertTrue(self.wait_gone(pid))
        self.assertTrue(wait_until(lambda: server.POOL.used == 0))
        self.assertEqual(self._post_json(dict(BODY, messages=[msg("again")]))[0], 200)

    def test_rw008_keyed_failure_closes_child_and_frees_slots(self):
        """RW-008: keyed-ход упал (reason=failed), start падает: ребёнок убит, L/P/T свободны, чат DIRTY."""
        _inject_start_failure(self, {server.RpcProcess.close})
        self.hub.script([{"steps": [], "reason": "failed"}])
        chat = self.conv("chat-fail")
        status, _ = chat.ask("q0")
        self.assertEqual(status, 502)
        pid = self.hub.spawns()[0]["pid"]
        self.assertTrue(self.wait_gone(pid))
        state = self.chat_of("chat-fail")
        self.assertEqual(state.state, "DIRTY")
        self.assertFalse(state.lock.locked())
        self.assertTrue(wait_until(lambda: server.POOL.used == 0))
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()

    def test_rw008_shutdown_kills_every_child_when_thread_start_fails(self):
        """RW-008: shutdown_all: ошибка start для одного ребёнка не прерывает kill остальных."""
        self.assertEqual(self.conv("chat-a").ask("q0")[0], 200)
        self.assertEqual(self.conv("chat-b").ask("q0")[0], 200)
        pids = [spawn["pid"] for spawn in self.hub.spawns()]
        self.assertEqual(len(pids), 2)
        _inject_start_failure(self, {server._shutdown_one})
        closed = server.shutdown_all(grace=1.0)
        self.assertEqual(closed, 2)
        for pid in pids:
            self.assertTrue(self.wait_gone(pid, timeout=5))

    def test_rw008_cleanup_chain_releases_chat_lease_when_finish_attempt_raises(self):
        """RW-008: исключение из _finish_attempt во внешнем finally не оставляет аренду чата и ссылку."""
        chat = self.conv("chat-chain")
        self.assertEqual(chat.ask("q0")[0], 200)
        state = self.chat_of("chat-chain")

        def boom(*_args, **_kwargs):
            raise RuntimeError("execute failed")

        with (
            mock.patch.object(server.Handler, "_execute", boom),
            mock.patch.object(server, "_finish_attempt", side_effect=OSError("disk")),
        ):
            post_safely(
                self,
                dict(
                    BODY,
                    prompt_cache_key="chat-chain",
                    messages=chat.msgs + [msg("q1")],
                ),
            )
        self.assertFalse(state.lock.locked())
        self.assertEqual(state.refs, 0)


class TestKbScope(GuardCase):
    """RW-009: область KB-лимита не зависит от текущего содержимого канона."""

    def _canon_block(self, size):
        body = "k" * (size - len(HEAD.encode()))
        Path(server.GUARD_CANON).write_text(body + "\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        return HEAD + body

    def _ask_block(self, key, block, cwd=None):
        extra = {"extra_body": {"cwd": cwd}} if cwd else {}
        return self._post_json(
            dict(
                BODY, prompt_cache_key=key, messages=[msg("hello"), msg(block)], **extra
            )
        )

    def test_rw009_old_kb_block_stays_limited_after_canon_change(self):
        """RW-009: канон изменён после создания чата: старый KB-блок 61000 Б всё равно отклоняется."""
        block = self._canon_block(61000)
        self.assertEqual(
            self._ask_block("chat-kb-1", block)[0], 503
        )  # канон-форма: предел 60000
        Path(server.GUARD_CANON).write_text("new safe canon\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        status, body = self._ask_block("chat-kb-2", block)
        self.assertEqual(status, 503, body)
        self.assertEqual(self.hub.spawns(), [])

    def test_rw009_kb_cwd_with_extra_section_is_limited_to_60000(self):
        """RW-009: cwd=KB: блок с дополнительной секцией > 60000 Б отклонён; тот же блок в cwd=WA проходит."""
        block = HEAD + "a" * 69000
        cwds = self.fs["cwds"]
        status, body = self._ask_block("chat-kb-extra", block, str(cwds["KB"]))
        self.assertEqual(status, 503, body)
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self._ask_block("chat-wa", block, str(cwds["WA"]))[0], 200)


class TestStructuralJsonFlood(RpcCase):
    """RW-014: строка из миллионов {} отклоняется ДО json.loads; глубокая вложенность не убивает читателя."""

    def _loads_spy(self):
        real = json.loads
        seen = {"big": 0}

        def spy(text, *args, **kwargs):
            if isinstance(text, str) and len(text) > 500_000:
                seen["big"] += 1
            return real(text, *args, **kwargs)

        patcher = mock.patch.object(server.json, "loads", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return seen

    def test_rw014_struct_flood_rejected_before_parse(self):
        """RW-014: 400 000 пустых объектов в одной строке: json.loads не вызван, ход -> 502 proxy_error."""
        server.MAX_JSON_STRUCT_TOKENS = 50_000
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "struct_flood", "count": 400_000},
                        {"op": "text", "text": "late"},
                    ]
                }
            ]
        )
        seen = self._loads_spy()
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]))
        self.assertEqual(status, 502, body)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(seen["big"], 0)
        self.assertTrue(no_leaks(self))

    def test_rw014_deep_nesting_is_controlled_error_not_dead_reader(self):
        """RW-014: вложенность 150 000 уровней (ниже структурного предела): RecursionError не роняет читателя, ход -> 502 быстро (не по таймауту)."""
        server.SILENCE_WATCHDOG_S = 30.0
        server.FIRST_TOKEN_TIMEOUT_S = 30.0
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "deep_nesting", "depth": 150_000},
                        {"op": "text", "text": "late"},
                    ]
                }
            ]
        )
        started = time.monotonic()
        status, body = self._post_json(dict(BODY, messages=[msg("hi")]), timeout=40)
        self.assertEqual(status, 502, body)
        self.assertLess(time.monotonic() - started, 15.0)


class TestChmodSpool(ImageCase):
    """RW-015: ошибка chmod spool-каталога/файла картинки не глотается: 502, каталог удалён."""

    def _ask_with_failing_chmod(self, stream):
        from bridge_testlib import image_part, make_png, text_part

        server.IMAGE_PROBE = True
        self.probe_stand()
        real = os.chmod

        def failing(path, mode, *args, **kwargs):
            if "img-" in str(path):
                raise OSError(1, "Operation not permitted")
            return real(path, mode, *args, **kwargs)

        body = {
            "model": "claude-sonnet-5-5",
            "prompt_cache_key": "chat-img",
            "stream": stream,
            "messages": [
                {
                    "role": "user",
                    "content": [text_part("look"), image_part(make_png(64))],
                }
            ],
        }
        with mock.patch.object(os, "chmod", failing):
            return self._post(body)

    def test_rw015_chmod_failure_gives_502_json_and_cleans_spool(self):
        """RW-015: JSON: chmod -> OSError: 502 proxy_error, img-* не остаётся, слоты свободны."""
        status, raw = self._ask_with_failing_chmod(False)
        self.assertEqual(status, 502, raw)
        self.assertEqual(json.loads(raw)["error"]["type"], "proxy_error")
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])
        self.assertEqual(self.hub.spawns(), [])
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()

    def test_rw015_chmod_failure_gives_error_event_in_sse(self):
        """RW-015: SSE: ошибка chmod -> событие error proxy_error, ответ без контента, каталог удалён."""
        _status, raw = self._ask_with_failing_chmod(True)
        self.assertIn("proxy_error", raw)
        self.assertNotIn('"content": "PONG"', raw)
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])


class TestShorterComplete(RunCase):
    """RW-016: shorter complete не уменьшает верхнюю границу учтённого размера."""

    def test_rw016_shorter_complete_then_original_length_is_not_recharged(self):
        """RW-016: delta 600 Б, complete 100 Б, complete 600 Б: учёт равен учёту после delta."""
        run = self.make_run()
        run._on_notif(user_create())
        run._on_notif(asst_create("m1", "turn-1", ""))
        run._on_notif(note("assistant_text_delta", messageId="m1", textDelta="x" * 600))
        charged = run._acc_bytes
        run._on_notif(note("assistant_text_complete", messageId="m1", text="y" * 100))
        run._on_notif(note("assistant_text_complete", messageId="m1", text="x" * 600))
        self.assertEqual(run._acc_bytes, charged)


class TestRefusalTaxonomy(GuardCase):
    """RW-018: отказ REQ-003 — код из baseline-таксономии; внутреннее имя состояния остаётся в журнале."""

    def test_rw018_block_over_limit_gives_baseline_503_and_internal_alert(self):
        """RW-018: блок > предела -> 503 launcher_unavailable (не 400/REQ003 на проводе), до spawn/add, alert в журнале."""
        block = HEAD + "a" * 61000
        Path(server.GUARD_CANON).write_text(block[len(HEAD) :] + "\n", encoding="utf-8")
        server._canon_cache.update(key=None, digest="")
        with self.capture_logs() as lines:
            status, body = self._post_json(
                dict(
                    BODY,
                    prompt_cache_key="chat-tax",
                    messages=[msg("hello"), msg(block)],
                )
            )
        self.assertEqual(status, 503, body)
        self.assertEqual(body["error"]["type"], "launcher_unavailable")
        self.assertNotIn("REQ003", json.dumps(body))
        self.assertEqual(self.hub.spawns(), [])
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])
        self.assertTrue(
            any(
                "REQ003_SIZE_EXCEEDED" in ln
                for ln in lines
                if ln.startswith("instr_gate_alert ")
            )
        )


class TestPendingBeforeAdd(RpcCase):
    """RW-019: первый keyed-ход нового чата пишет PENDING до первого add_user_message."""

    def test_rw019_pending_write_failure_on_cold_keyed_chat_gives_502_without_add(self):
        """RW-019: ENOSPC при записи PENDING у чата без SID: 502 proxy_error, ни одного add, L/P/T свободны."""
        real = server._atomic_write

        def failing(path, data):
            if b'"PENDING"' in data:
                raise OSError(28, "No space left on device")
            return real(path, data)

        server._atomic_write = failing
        try:
            status, body = self._post_json(
                dict(BODY, prompt_cache_key="chat-new", messages=[msg("hi")])
            )
        finally:
            server._atomic_write = real
        self.assertEqual(status, 502, body)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(self.hub.rpcs("droid.add_user_message"), [])
        state = self.chat_of("chat-new")
        self.assertFalse(state.lock.locked())
        self.assertTrue(wait_until(lambda: server.POOL.used == 0))
        self.assertTrue(server._slots.acquire(blocking=False))
        server._slots.release()

    def test_rw019_pending_record_exists_before_first_add(self):
        """RW-019: к моменту первого add_user_message на диске уже запись PENDING нового SID."""
        seen = {}
        real = server.Run._send_items

        def spy(run, proc, items):
            record = server._read_record(
                server._record_path(server._key_hash("chat-order"))
            )
            seen["state"] = record["state"] if record else None
            seen["sid"] = record["sid"] if record else None
            return real(run, proc, items)

        with mock.patch.object(server.Run, "_send_items", spy):
            self.assertEqual(
                self._post_json(
                    dict(BODY, prompt_cache_key="chat-order", messages=[msg("hi")])
                )[0],
                200,
            )
        self.assertEqual(seen["state"], "PENDING")
        self.assertTrue(seen["sid"])


class TestGuardWarnings(GuardCase):
    """RW-021/RW-022: потеря профилей после ok — unsafe; предупреждения b_guard журналируются."""

    def test_rw021_profiles_lost_after_ok_turns_unsafe_and_refuses_new_chats(self):
        """RW-021: ok -> каталог профилей удалён -> unsafe; новый чат с блоком отклонён, живой продолжает."""
        import shutil

        self.write_profile(106496)
        self.assertEqual(server.GUARD.check_once(), "ok")
        self.assertEqual(self.block_ask("chat-live")[0], 200)
        shutil.rmtree(self.profiles)
        with self.capture_logs() as lines:
            self.assertEqual(server.GUARD.check_once(), "unsafe")
        self.assertTrue(
            any(
                "PROFILES_LOST" in ln
                for ln in lines
                if ln.startswith("instr_guard_alert ")
            )
        )
        self.assertEqual(self.block_ask("chat-live")[0], 200)
        status, body = self.block_ask("chat-brand-new")
        self.assertEqual(status, 503, body)

    def test_rw021_clean_start_without_profiles_stays_unknown(self):
        """RW-021: контроль: профилей не было с самого старта -> unknown (прежнее поведение)."""
        self.assertEqual(server.GUARD.check_once(), "unknown")

    def test_rw022_warning_thresholds_are_journaled_without_refusal(self):
        """RW-022: exit 1 (LOW_MARGIN_*, LINE_ORACLE_RISK) -> alert в журнале, состояние ok, трафик идёт."""
        self.write_profile(106496)
        warn = types.SimpleNamespace(
            exit_code=1,
            reasons=[
                "LOW_MARGIN_LOWER: запас снизу 10 Б < 2048",
                "LINE_ORACLE_RISK cwd=KB: запас строки 0 Б < 2048",
            ],
        )
        with mock.patch.object(server.b_guard, "check_installed", return_value=warn):
            with self.capture_logs() as lines:
                self.assertEqual(server.GUARD.check_once(), "ok")
        alerts = [ln for ln in lines if ln.startswith("instr_guard_alert ")]
        self.assertEqual(len(alerts), 1, lines)
        self.assertIn("LOW_MARGIN_LOWER", alerts[0])
        self.assertIn("LINE_ORACLE_RISK", alerts[0])
        self.assertIn("warnings=2", alerts[0])
        self.assertEqual(self.block_ask("chat-warn")[0], 200)

    def test_rw022_clean_ok_has_no_alert(self):
        """RW-022: контроль: чистый ok без причин не даёт alert."""
        self.write_profile(106496)
        with self.capture_logs() as lines:
            server.GUARD.check_once()
        self.assertEqual(
            [ln for ln in lines if ln.startswith("instr_guard_alert ")], []
        )


class TestTerminalBeforeAck(RpcCase):
    """RW-023: terminal до ACK add_user_message — один результат, без interrupt и ожидания grace."""

    def test_rw023_terminal_before_ack_gives_single_result_without_interrupt(self):
        """RW-023: create/delta/terminal приходят до ACK: ответ один, interrupt_session не отправлен."""
        self.hub.configure(ack_after_turn=True)
        self.hub.script([{"steps": [{"op": "text", "text": "ONCE"}]}])
        started = time.monotonic()
        status, body = self._post_json(
            dict(BODY, prompt_cache_key="chat-ack", messages=[msg("hi")])
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["choices"][0]["message"]["content"], "ONCE")
        self.assertEqual(self.hub.rpcs("droid.interrupt_session"), [])
        self.assertLess(time.monotonic() - started, server.INTERRUPT_GRACE_S + 0.5)
        self.assertTrue(no_leaks(self))


if __name__ == "__main__":
    unittest.main(verbosity=2)
