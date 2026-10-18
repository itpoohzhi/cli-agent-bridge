"""VER-007: эпохи, гистерезис 78% (10 append-ходов без смены эпохи), изоляция чатов, TTL/LRU.

Запуск: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest -v test_context_resilience_resident
"""

import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import context_resilience as ctx  # noqa: E402
from context_testlib import big, entry, flags, oa, oa_history  # noqa: E402

E = entry(60_000, 10_000)  # B_input = 50_000
NS = "ns"


def ident(sid="s1", chat=None, owner="owner-a"):
    headers = [("X-Session-Id", sid)] if sid else []
    if chat:
        headers.append(("x-dsh-chat-id", chat))
    return ctx.build_identity(owner, NS, headers)


def run(history, identity, store, e=E, f=None):
    return ctx.prepare(
        {"messages": history},
        e,
        f or flags(),
        identity=identity,
        store=store,
        serialize=False,
    )


def append_user(history, n=1, size=380):
    return history + [oa("user", f"n{i}-" + big(size)) for i in range(n)]


class TestHysteresisAndEpochs(unittest.TestCase):
    def setUp(self):
        self.store = ctx.EpochStore()
        self.identity = ident()
        self.history = oa_history(30, 500)

    def _epoch(self):
        (epoch,) = self.store._data.values()
        return epoch

    def test_first_prune_creates_epoch_at_hysteresis_target(self):
        out = run(self.history, self.identity, self.store)
        self.assertTrue(out.pruned)
        self.assertEqual(out.report.epoch, "new")
        self.assertEqual(out.report.generation, 1)
        self.assertLessEqual(out.report.t_after, (78 * out.report.b_input) // 100)
        self.assertEqual(len(self.store), 1)

    def test_ten_small_appends_keep_epoch_and_prefix_stable(self):
        first = run(self.history, self.identity, self.store)
        base = self._epoch()
        base_digest, retained = base.base_digest, base.retained
        prev = first.body["messages"]
        history = self.history
        for _ in range(10):
            history = append_user(history)  # ≈0.8% B_input на ход
            out = run(history, self.identity, self.store)
            self.assertEqual(out.report.epoch, "hit")
            self.assertEqual(out.report.generation, 1)
            self.assertTrue(out.pruned)
            self.assertLessEqual(out.report.t_after, out.report.b_input)
            msgs = out.body["messages"]
            self.assertEqual(msgs[: len(prev)], prev)  # префикс (кэш) не менялся
            self.assertEqual(len(msgs), len(prev) + 1)
            prev = msgs
        epoch = self._epoch()
        self.assertEqual((epoch.base_digest, epoch.retained), (base_digest, retained))
        self.assertEqual(epoch.generation, 1)

    def test_crossing_budget_creates_exactly_one_new_epoch(self):
        run(self.history, self.identity, self.store)
        history = self.history
        for _ in range(10):
            history = append_user(history)
            run(history, self.identity, self.store)
        history = history + [oa("user", "big-" + big(11_500))]  # ≈ +23% B_input
        out = run(history, self.identity, self.store)
        self.assertEqual(out.report.epoch, "rebuilt")
        self.assertEqual(out.report.generation, 2)
        self.assertLessEqual(
            out.report.t_after, (78 * out.report.b_input) // 100 + 11_600
        )
        self.assertLessEqual(out.report.t_after, out.report.b_input)
        history = append_user(history)
        again = run(history, self.identity, self.store)
        self.assertEqual((again.report.epoch, again.report.generation), ("hit", 2))

    def test_raw_resend_does_not_resurrect_dropped_units(self):
        run(self.history, self.identity, self.store)
        out = run(append_user(self.history), self.identity, self.store)
        text = " ".join(str(m.get("content")) for m in out.body["messages"])
        self.assertNotIn("u0-", text)
        self.assertEqual(text.count(ctx.MARKER_TEXT), 1)  # маркер не создаётся заново

    def test_epoch_not_used_when_history_fits(self):
        out = run(self.history[:8], self.identity, self.store)
        self.assertFalse(out.pruned)
        self.assertEqual(len(self.store), 0)

    def test_edit_of_retained_message_invalidates_epoch(self):
        run(self.history, self.identity, self.store)
        epoch = self._epoch()
        edited = list(self.history)
        idx = epoch.retained[len(epoch.retained) // 2]
        edited[idx] = dict(edited[idx], content="EDITED-" + str(edited[idx]["content"]))
        out = run(append_user(edited), self.identity, self.store)
        self.assertEqual(out.report.epoch, "rebuilt")
        self.assertEqual(out.report.generation, 2)

    def test_shorter_history_rollback_invalidates_epoch(self):
        run(self.history, self.identity, self.store)
        out = run(self.history[:-12] + [oa("user", "LAST")], self.identity, self.store)
        self.assertEqual(out.report.epoch, "rebuilt")

    def test_changed_system_prompt_is_a_different_epoch_key(self):
        run(self.history, self.identity, self.store)
        other = [oa("system", "OTHER-SYSTEM")] + self.history[1:]
        run(other, self.identity, self.store)
        self.assertEqual(len(self.store), 2)

    def test_model_switch_never_reuses_epoch(self):
        run(self.history, self.identity, self.store, entry(60_000, 10_000, model="m1"))
        run(self.history, self.identity, self.store, entry(40_000, 10_000, model="m2"))
        self.assertEqual(len(self.store), 2)
        back = run(
            self.history, self.identity, self.store, entry(60_000, 10_000, model="m1")
        )
        self.assertEqual((back.report.epoch, back.report.generation), ("hit", 1))

    def test_restart_means_fresh_safe_prepare(self):
        run(self.history, self.identity, self.store)
        fresh_store = ctx.EpochStore()
        out = run(append_user(self.history), self.identity, fresh_store)
        self.assertEqual(out.report.epoch, "new")
        self.assertEqual(out.report.generation, 1)
        self.assertLessEqual(out.report.t_after, out.report.b_input)

    def test_flag_off_does_not_use_or_fill_store(self):
        with self.assertRaises(ctx.ContextRejected):
            run(self.history, self.identity, self.store, f=flags(False))
        self.assertEqual(len(self.store), 0)


class TestIsolation(unittest.TestCase):
    def setUp(self):
        self.store = ctx.EpochStore()
        self.history = oa_history(30, 500)

    def test_two_chats_same_model_and_anchors_are_isolated(self):
        a, b = ident("sid-a"), ident("sid-b")
        run(self.history, a, self.store)
        run(self.history, b, self.store)
        self.assertEqual(len(self.store), 2)
        grown = append_user(self.history, 3)
        out_a = run(grown, a, self.store)
        self.assertEqual((out_a.report.epoch, out_a.report.generation), ("hit", 1))
        keys = list(self.store._data)
        self.assertNotEqual(keys[0], keys[1])

    def test_two_owners_same_session_id_are_isolated(self):
        run(self.history, ident("same", owner="o1"), self.store)
        run(self.history, ident("same", owner="o2"), self.store)
        self.assertEqual(len(self.store), 2)

    def test_session_chat_tuple_discriminates_shared_session(self):
        run(self.history, ident("sess", chat="c1"), self.store)
        run(self.history, ident("sess", chat="c2"), self.store)
        self.assertEqual(len(self.store), 2)
        again = run(append_user(self.history), ident("sess", chat="c1"), self.store)
        self.assertEqual(again.report.epoch, "hit")

    def test_no_id_requests_never_share_or_store_mutable_epoch(self):
        for identity in (None, ident(sid=None)):
            self.assertEqual(
                identity is None or identity.kind,
                True if identity is None else "anchor_hash_unverified",
            )
            a = run(self.history, identity, self.store)
            b = run(self.history, identity, self.store)
            self.assertEqual(a.body["messages"], b.body["messages"])
            self.assertLessEqual(a.report.t_after, a.report.b_input)
        self.assertEqual(len(self.store), 0)

    def test_unverified_identity_reports_stateless(self):
        out = run(self.history, ident(sid=None), self.store)
        self.assertEqual(out.report.epoch, "stateless")
        self.assertEqual(out.report.identity_kind, "anchor_hash_unverified")

    def test_identical_chats_without_ids_diverge_independently(self):
        grown_a = append_user(self.history, 2)
        grown_b = append_user(self.history, 5)
        a = run(grown_a, None, self.store)
        b = run(grown_b, None, self.store)
        self.assertNotEqual(a.body["messages"], b.body["messages"])
        self.assertEqual(len(self.store), 0)

    def test_forced_hash_collision_never_merges_epochs(self):
        original = ctx._epoch_key
        ctx._epoch_key = lambda descriptor: "0" * 64
        try:
            a, b = ident("sid-a"), ident("sid-b")
            first = run(self.history, a, self.store)
            self.assertEqual(len(self.store), 1)
            second = run(self.history, b, self.store)
            self.assertEqual(second.report.epoch, "collision")
            self.assertEqual(len(self.store), 0)  # обоим reuse запрещён
            third = run(self.history, a, self.store)
            self.assertEqual(third.report.epoch, "quarantined")
            self.assertEqual(len(self.store), 0)
            for out in (first, second, third):
                self.assertLessEqual(out.report.t_after, out.report.b_input)
                self.assertEqual(out.body["messages"], first.body["messages"])
        finally:
            ctx._epoch_key = original


class TestTrustedIds(unittest.TestCase):
    def test_priority_session_then_chat(self):
        self.assertEqual(ctx.trusted_ids([("x-dsh-chat-id", "c")]), ("c", None))
        self.assertEqual(ctx.trusted_ids([("X-Session-Id", "s")]), ("s", None))
        self.assertEqual(
            ctx.trusted_ids([("x-session-id", "s"), ("x-dsh-chat-id", "c")]), ("s", "c")
        )

    def test_spoof_and_malformed_ids_fall_back_to_no_id(self):
        bad = [
            [("x-session-id", "a"), ("x-session-id", "b")],  # конфликтующие дубликаты
            [("x-session-id", "")],
            [("x-session-id", "   ")],
            [("x-session-id", "a\nb")],
            [("x-session-id", "a\x7f")],
            [("x-session-id", "я" * 129)],  # 258 байт UTF-8
            [("x-session-id", " pad ")],
            [("x-session-id", "s"), ("x-dsh-chat-id", "c\x00")],
            [],
        ]
        for headers in bad:
            self.assertIsNone(ctx.trusted_ids(headers), headers)

    def test_identical_duplicate_is_accepted_and_boundary_length(self):
        self.assertEqual(
            ctx.trusted_ids([("x-session-id", "s"), ("x-session-id", "s")]), ("s", None)
        )
        self.assertIsNotNone(ctx.trusted_ids([("x-session-id", "a" * 256)]))
        self.assertIsNone(ctx.trusted_ids([("x-session-id", "a" * 257)]))

    def test_owner_scope_is_opaque_keyed_digest(self):
        s1 = ctx.owner_scope("token-1", b"k" * 32)
        self.assertNotIn("token-1", s1)
        self.assertEqual(s1, ctx.owner_scope("token-1", b"k" * 32))
        self.assertNotEqual(s1, ctx.owner_scope("token-1", b"j" * 32))
        self.assertNotEqual(s1, ctx.owner_scope("token-2", b"k" * 32))


class TestStoreBounds(unittest.TestCase):
    def _epoch(self, owner, tag):
        desc = (
            owner,
            "ns",
            "b",
            "m",
            "trusted",
            tag,
            "",
            "fp",
            "openai",
            "BYTE-V1",
            "1",
            "core-1",
        )
        return (
            ctx._epoch_key(desc),
            desc,
            ctx.Epoch(desc, 1, 3, (0,), (b"d",), None, b"b", True),
        )

    def test_ttl_expiry_drops_optional_state(self):
        now = [0.0]
        store = ctx.EpochStore(ttl_s=100, clock=lambda: now[0])
        key, desc, epoch = self._epoch("o", "a")
        store.put(key, epoch)
        now[0] = 99
        self.assertEqual(store.get(key, desc)[1], "hit")
        now[0] = 99 + 101
        self.assertEqual(store.get(key, desc), (None, "miss"))

    def test_per_owner_cap_evicts_oldest_of_that_owner(self):
        store = ctx.EpochStore(max_per_owner=2)
        keys = []
        for tag in "abc":
            key, desc, epoch = self._epoch("o", tag)
            store.put(key, epoch)
            keys.append((key, desc))
        other_key, _, other = self._epoch("p", "z")
        store.put(other_key, other)
        self.assertEqual(len(store), 3)
        self.assertEqual(store.get(*keys[0])[1], "miss")
        self.assertEqual(store.get(*keys[2])[1], "hit")

    def test_facade_lru_cap(self):
        store = ctx.EpochStore(max_epochs=2)
        pairs = []
        for tag in "abc":
            key, desc, epoch = self._epoch(f"o{tag}", tag)
            store.put(key, epoch)
            pairs.append((key, desc))
        self.assertEqual(len(store), 2)
        self.assertEqual(store.get(*pairs[0])[1], "miss")

    def test_lru_order_respects_recent_use(self):
        store = ctx.EpochStore(max_epochs=2)
        pairs = []
        for tag in "ab":
            key, desc, epoch = self._epoch(f"o{tag}", tag)
            store.put(key, epoch)
            pairs.append((key, desc))
        store.get(*pairs[0])  # a свежее b
        key, desc, epoch = self._epoch("oc", "c")
        store.put(key, epoch)
        self.assertEqual(store.get(*pairs[0])[1], "hit")
        self.assertEqual(store.get(*pairs[1])[1], "miss")

    def test_byte_budget_evicts_but_keeps_newest(self):
        store = ctx.EpochStore(max_bytes=600)
        for tag in "abc":
            key, _, epoch = self._epoch(f"o{tag}", tag)
            store.put(key, epoch)
        self.assertEqual(len(store), 1)
        self.assertLessEqual(store.total_bytes(), 600)

    def test_quarantine_expires(self):
        now = [0.0]
        store = ctx.EpochStore(ttl_s=10, clock=lambda: now[0])
        key, desc, epoch = self._epoch("o", "a")
        store.put(key, epoch)
        store.get(key, desc[:-1] + ("other",))  # коллизия → карантин
        self.assertEqual(store.get(key, desc)[1], "quarantined")
        now[0] = 11
        self.assertEqual(store.get(key, desc)[1], "miss")


class TestConcurrency(unittest.TestCase):
    def test_parallel_requests_of_one_chat_agree(self):
        store = ctx.EpochStore()
        history = oa_history(30, 500)
        results, errors = [], []

        def worker():
            try:
                results.append(run(history, ident("same"), store))
            except Exception as exc:  # noqa: BLE001 - фиксируем для assert
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 8)
        self.assertEqual(len(store), 1)
        first = results[0].body["messages"]
        self.assertTrue(all(r.body["messages"] == first for r in results))

    def test_parallel_distinct_chats_do_not_cross(self):
        store = ctx.EpochStore()
        outs = {}

        def worker(i):
            history = [oa("system", f"SYS{i}")] + oa_history(30, 500)[1:]
            outs[i] = run(history, ident(f"sid{i}"), store)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(len(store), 6)
        for i, out in outs.items():
            self.assertEqual(out.body["messages"][0]["content"], f"SYS{i}")


if __name__ == "__main__":
    unittest.main()
