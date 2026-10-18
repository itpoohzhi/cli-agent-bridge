"""VER-001 / VER-002: бюджет, граница B-1/B/B+1, якоря, неделимость, маркер 8, одна сериализация.

Запуск: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest -v test_context_resilience
"""

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import context_resilience as ctx  # noqa: E402
from context_testlib import (  # noqa: E402
    big,
    count_marker,
    entry,
    flags,
    oa,
    oa_history,
    oa_tool_exchange,
    oracle_total,
    target,
    tool_ids,
)


def prep(body, e, f=None, **kw):
    return ctx.prepare(body, e, f or flags(), **kw)


class TestBudgetFormulas(unittest.TestCase):
    def test_ceildiv_matches_reference(self):
        for p in range(0, 60):
            for q in range(1, 9):
                self.assertEqual(ctx.ceildiv(p, q), -(-p // q))

    def test_ceildiv_rejects_nonpositive_denominator(self):
        with self.assertRaises(ValueError):
            ctx.ceildiv(1, 0)

    def test_rational_ratio_rounds_up_per_class(self):
        p = ctx.Passport(ascii_ratio=(1, 3), utf8_ratio=(3, 2))
        self.assertEqual(p.text_tokens(10, 3), 4 + 5)
        self.assertEqual(p.text_tokens(0, 0), 0)

    def test_b_input_formula(self):
        t = target(100_000, 10_000, h_hidden=500, s_uncertainty=300)
        self.assertEqual(t.b_input(10_000), 100_000 - 10_000 - 500 - 300)

    def test_output_reserve_clamped_to_model_max(self):
        t = target(100_000, 10_000)
        self.assertEqual(t.output_reserve(None), 10_000)
        self.assertEqual(t.output_reserve(0), 10_000)
        self.assertEqual(t.output_reserve(2_000), 2_000)
        self.assertEqual(t.output_reserve(99_999), 10_000)

    def test_passport_validation(self):
        with self.assertRaises(ValueError):
            ctx.Passport(marker_tokens=9)
        with self.assertRaises(ValueError):
            ctx.Passport(marker_tokens=3)
        with self.assertRaises(ValueError):
            ctx.Passport(ascii_ratio=(1, 0))
        with self.assertRaises(ValueError):
            ctx.Passport(f_msg=-1)

    def test_marker_reserve_is_eight_plus_frame(self):
        self.assertEqual(ctx.MARKER_TOKENS, 8)
        self.assertEqual(ctx.marker_weight(ctx.Passport()), 8 + 8)
        self.assertEqual(ctx.marker_weight(ctx.Passport(marker_tokens=4, f_msg=0)), 4)

    def test_weight_equals_independent_oracle(self):
        body = {
            "model": "m",
            "stream": False,
            "messages": [
                oa("system", "sys"),
                oa("user", "привет мир " + big(50)),
                {"role": "assistant", "content": None, "tool_calls": []},
            ],
        }
        report = prep(body, entry(10**9, 0), flags(False)).report
        self.assertEqual(report.t_before, oracle_total(body))

    def test_unicode_counts_utf8_bytes(self):
        a = prep({"messages": [oa("user", "a" * 100)]}, entry(10**9, 0)).report.t_before
        u = prep({"messages": [oa("user", "й" * 100)]}, entry(10**9, 0)).report.t_before
        self.assertEqual(u - a, 100)


class TestBoundary(unittest.TestCase):
    """VER-001: C-R-H-S-1 / 0 / +1."""

    def setUp(self):
        self.body = {"messages": [oa("user", big(1234))]}
        self.t = prep(self.body, entry(10**9, 0), flags(False)).report.t_before

    def _window(self, b_input, r=1000):
        return entry(b_input + r, r)

    def test_exact_budget_passes_without_pruning(self):
        out = prep(self.body, self._window(self.t), flags(False))
        self.assertFalse(out.pruned)
        self.assertEqual(out.header, ("X-DSH-Context-Pruned", "false"))
        self.assertIs(out.body["messages"], self.body["messages"])

    def test_one_below_budget_is_rejected_zero_send(self):
        with self.assertRaises(ctx.ContextRejected) as cm:
            prep(self.body, self._window(self.t - 1), flags(False))
        self.assertEqual(cm.exception.status, 400)
        self.assertIn(ctx.REASON_REQUIRED_EXCEEDS, cm.exception.message())

    def test_one_above_budget_passes(self):
        out = prep(self.body, self._window(self.t + 1), flags(False))
        self.assertFalse(out.pruned)

    def test_hidden_and_uncertainty_shrink_budget(self):
        e = entry(self.t + 1000 + 10, 1000, h_hidden=5, s_uncertainty=5)
        self.assertFalse(prep(self.body, e, flags(False)).pruned)
        e2 = entry(self.t + 1000 + 9, 1000, h_hidden=5, s_uncertainty=5)
        with self.assertRaises(ctx.ContextRejected):
            prep(self.body, e2, flags(False))

    def test_error_body_shape_is_existing_envelope(self):
        with self.assertRaises(ctx.ContextRejected) as cm:
            prep(self.body, self._window(self.t - 1), flags(False))
        err = cm.exception.error_body()["error"]
        self.assertEqual(sorted(err), ["code", "message", "type"])
        self.assertEqual((err["code"], err["type"]), (400, "invalid_request"))
        self.assertNotIn("xxxx", err["message"])

    def test_nonpositive_budget_is_unqualified(self):
        with self.assertRaises(ctx.ContextUnqualified):
            prep(self.body, entry(1000, 1000), flags(False))

    def test_unknown_route_is_unqualified_503(self):
        with self.assertRaises(ctx.ContextUnqualified) as cm:
            ctx.prepare(self.body, None, flags())
        self.assertEqual(cm.exception.status, 503)

    def test_unsupported_modality_fail_closed(self):
        body = {
            "messages": [
                oa(
                    "user",
                    [
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:..." + big(5000)},
                        }
                    ],
                )
            ]
        }
        with self.assertRaises(ctx.ContextUnqualified):
            prep(body, entry(), flags())
        qualified = entry(image_tokens=300)
        out = prep(body, qualified, flags())
        self.assertLess(out.report.t_before, 400)  # base64 не считается текстом

    def test_invalid_utf8_surrogate_rejected(self):
        with self.assertRaises(ctx.ContextRejected):
            prep({"messages": [oa("user", "bad\ud800")]}, entry(), flags())

    def test_depth_limit(self):
        deep = cur = {}
        for _ in range(ctx.MAX_DEPTH + 5):
            cur["x"] = {}
            cur = cur["x"]
        with self.assertRaises(ctx.ContextRejected):
            prep({"messages": [oa("user", deep)]}, entry(), flags())

    def test_invalid_messages_shape(self):
        for bad in (None, "x", [1, 2], {}):
            with self.assertRaises(ctx.ContextRejected):
                prep({"messages": bad}, entry(), flags())


class TestAnchorsAndOrder(unittest.TestCase):
    def setUp(self):
        self.history = oa_history(30, 500)
        self.body = {"messages": self.history}
        self.e = entry(60_000, 10_000)  # b_input = 50_000, история ≈ 100 КБ

    def test_prune_happens_and_fits_hysteresis_target(self):
        out = prep(self.body, self.e)
        self.assertTrue(out.pruned)
        b_input = out.report.b_input
        self.assertLessEqual(out.report.t_after, b_input)
        self.assertLessEqual(out.report.t_after, (78 * b_input) // 100)
        self.assertLessEqual(oracle_total(out.body), b_input)

    def test_anchors_survive_in_original_order(self):
        out = prep(self.body, self.e)
        kept = out.body["messages"]
        self.assertEqual(kept[0], self.history[0])  # system
        self.assertEqual(kept[1], self.history[1])  # стартовая постановка
        self.assertEqual(kept[-1], self.history[-1])  # последний user
        originals = [id(m) for m in self.history]
        pos = [originals.index(id(m)) for m in kept if id(m) in originals]
        self.assertEqual(pos, sorted(pos))

    def test_kept_messages_are_same_objects_not_rewritten(self):
        out = prep(self.body, self.e)
        originals = {id(m) for m in self.history}
        foreign = [m for m in out.body["messages"] if id(m) not in originals]
        self.assertEqual(len(foreign), 1)  # только маркер
        self.assertEqual(foreign[0]["content"], ctx.MARKER_TEXT)

    def test_developer_and_midstream_system_reminders_are_hard(self):
        msgs = oa_history(30, 500)
        msgs.insert(10, oa("developer", "DEV-RULES"))
        msgs.insert(40, oa("system", "REMINDER-MID"))
        out = prep({"messages": msgs}, self.e)
        contents = [m["content"] for m in out.body["messages"]]
        self.assertIn("DEV-RULES", contents)
        self.assertIn("REMINDER-MID", contents)

    def test_newest_units_win_over_oldest(self):
        out = prep(self.body, self.e)
        texts = " ".join(str(m.get("content")) for m in out.body["messages"])
        self.assertIn("u29-", texts)
        self.assertNotIn("u0-", texts)

    def test_active_turn_after_last_user_is_immutable(self):
        msgs = oa_history(30, 500)[:-1] + [oa("user", "ACTIVE")]
        msgs += oa_tool_exchange(999, 800)
        out = prep({"messages": msgs}, self.e)
        self.assertEqual(out.body["messages"][-3:], msgs[-3:])

    def test_input_history_is_not_mutated(self):
        before = copy.deepcopy(self.history)
        prep(self.body, self.e)
        self.assertEqual(self.history, before)

    def test_repeat_is_deterministic(self):
        a = prep(self.body, self.e)
        b = prep(self.body, self.e)
        self.assertEqual(a.body["messages"], b.body["messages"])
        self.assertEqual(a.report.t_after, b.report.t_after)

    def test_huge_mandatory_is_controlled_400(self):
        msgs = [oa("system", "S"), oa("user", big(200_000))]
        with self.assertRaises(ctx.ContextRejected) as cm:
            prep({"messages": msgs}, entry(60_000, 10_000))
        self.assertEqual(cm.exception.status, 400)
        self.assertIn(ctx.REASON_REQUIRED_EXCEEDS, cm.exception.message())

    def test_huge_latest_user_is_controlled_400_not_truncated(self):
        msgs = oa_history(5, 100)[:-1] + [oa("user", big(200_000))]
        with self.assertRaises(ctx.ContextRejected):
            prep({"messages": msgs}, entry(60_000, 10_000))

    def test_pruner_flag_off_still_strict_admission(self):
        with self.assertRaises(ctx.ContextRejected):
            prep(self.body, self.e, flags(False))

    def test_mandatory_dominates_hysteresis_degraded(self):
        # hard ≈ 85% от b_input: больше 78%, но помещается; мягкий хвост не выделяется.
        msgs = [oa("system", "S"), oa("user", "T"), oa("assistant", big(10_000))]
        msgs += [oa("user", big(42_500))]
        out = prep({"messages": msgs}, entry(60_000, 10_000))
        self.assertEqual(out.report.hysteresis_degraded, "mandatory_dominates")
        self.assertEqual(
            len(out.body["messages"]), 4
        )  # system, T, маркер, user; assistant снят
        self.assertLessEqual(out.report.t_after, out.report.b_input)

    def test_hard_message_in_middle_keeps_position(self):
        msgs = oa_history(30, 500)
        msgs.insert(35, oa("system", "MID-SYS"))
        out = prep({"messages": msgs}, self.e)
        kept = out.body["messages"]
        idx = [i for i, m in enumerate(kept) if m.get("content") == "MID-SYS"][0]
        self.assertTrue(all(m["role"] != "system" for m in kept[idx + 1 :]))


class TestToolClosures(unittest.TestCase):
    """I-04: вызовы и результаты неделимы, включая parallel и cross-turn."""

    def _assert_closed(self, msgs):
        provided, needed = tool_ids(msgs)
        self.assertEqual(provided, needed)

    def test_parallel_results_stay_or_go_together(self):
        msgs = [oa("system", "S"), oa("user", "T")]
        for i in range(25):
            msgs += oa_tool_exchange(i, 400, calls=3)
            msgs.append(oa("user", f"q{i}"))
        msgs.append(oa("user", "LAST"))
        out = prep({"messages": msgs}, entry(30_000, 5_000))
        self.assertTrue(out.pruned)
        self._assert_closed(out.body["messages"])
        self.assertLess(len(out.body["messages"]), len(msgs))

    def test_cross_turn_result_drags_call_with_it(self):
        call, res = oa_tool_exchange(0, 3000)
        msgs = [oa("system", "S"), oa("user", "T"), call]
        msgs += [oa("user", f"filler{i}-" + big(3000)) for i in range(6)]
        msgs += [res, oa("assistant", "ok"), oa("user", "LAST")]
        out = prep({"messages": msgs}, entry(14_000, 2_000))
        self.assertTrue(out.pruned)
        self._assert_closed(out.body["messages"])

    def test_oversized_closure_is_dropped_whole_never_split(self):
        msgs = [oa("system", "S"), oa("user", "T")]
        msgs += oa_tool_exchange(0, 30_000)
        msgs += [oa("user", "mid"), oa("user", "LAST")]
        out = prep({"messages": msgs}, entry(20_000, 2_000))
        self._assert_closed(out.body["messages"])
        self.assertEqual(tool_ids(out.body["messages"]), (set(), set()))

    def test_duplicate_call_ids_join_one_component(self):
        a = oa_tool_exchange(1, 3000)
        b = oa_tool_exchange(1, 3000)  # те же id в другом месте
        msgs = [oa("system", "S"), oa("user", "T")] + a
        msgs += [oa("user", "x" + big(4000))] + b + [oa("user", "LAST")]
        out = prep({"messages": msgs}, entry(12_000, 2_000))
        kept = out.body["messages"]
        calls = sum(1 for m in kept if m.get("tool_calls"))
        results = sum(1 for m in kept if m.get("role") == "tool")
        self.assertEqual(calls, results)

    def test_orphan_optional_result_is_dropped(self):
        msgs = [oa("system", "S"), oa("user", "T")]
        msgs.append({"role": "tool", "tool_call_id": "ghost", "content": "x"})
        msgs += [oa("user", f"f{i}-" + big(2000)) for i in range(10)]
        msgs.append(oa("user", "LAST"))
        out = prep({"messages": msgs}, entry(12_000, 2_000))
        self.assertTrue(out.pruned)
        self.assertFalse(
            any(m.get("tool_call_id") == "ghost" for m in out.body["messages"])
        )

    def test_unresolved_optional_call_is_dropped(self):
        pending = oa_tool_exchange(7, 10)[0]
        msgs = [oa("system", "S"), oa("user", "T"), pending]
        msgs += [oa("user", f"f{i}-" + big(2000)) for i in range(10)]
        msgs.append(oa("user", "LAST"))
        out = prep({"messages": msgs}, entry(12_000, 2_000))
        self.assertFalse(any(m.get("tool_calls") for m in out.body["messages"]))

    def test_dangling_result_in_active_turn_is_400(self):
        msgs = oa_history(30, 500)
        msgs.append({"role": "tool", "tool_call_id": "ghost", "content": "x"})
        with self.assertRaises(ctx.ContextRejected):
            prep({"messages": msgs}, entry(60_000, 10_000))

    def test_pending_last_call_is_allowed(self):
        msgs = oa_history(30, 500)
        msgs.append(
            oa_tool_exchange(999, 10)[0]
        )  # вызов без результата в активном ходе
        out = prep({"messages": msgs}, entry(60_000, 10_000))
        self.assertTrue(out.pruned)
        self.assertEqual(out.body["messages"][-1], msgs[-1])

    def test_reasoning_bundle_stays_with_its_message(self):
        msgs = oa_history(30, 500)
        msgs[-4] = dict(msgs[-4], reasoning_content="THINK", thoughtSignature="SIG")
        out = prep({"messages": msgs}, entry(60_000, 10_000))
        survivors = [m for m in out.body["messages"] if m.get("reasoning_content")]
        self.assertEqual(len(survivors), 1)
        self.assertEqual(survivors[0]["thoughtSignature"], "SIG")
        self.assertIs(survivors[0], msgs[-4])


class TestMarker(unittest.TestCase):
    def setUp(self):
        self.msgs = oa_history(30, 500)
        self.e = entry(60_000, 10_000)

    def test_exactly_one_fixed_marker_without_self_reference(self):
        out = prep({"messages": self.msgs}, self.e)
        self.assertEqual(count_marker(out.body["messages"]), 1)
        self.assertEqual(ctx.MARKER_TEXT, "[context pruned]")
        self.assertFalse(any(ch.isdigit() for ch in ctx.MARKER_TEXT))
        self.assertNotIn("tokens", ctx.MARKER_TEXT)

    def test_marker_role_is_user_not_system(self):
        out = prep({"messages": self.msgs}, self.e)
        marker = [m for m in out.body["messages"] if m["content"] == ctx.MARKER_TEXT][0]
        self.assertEqual(marker["role"], "user")

    def test_marker_is_not_multiplied_on_reprepare(self):
        first = prep({"messages": self.msgs}, self.e)
        again = prep({"messages": first.body["messages"]}, self.e)
        self.assertFalse(again.pruned)
        self.assertEqual(count_marker(again.body["messages"]), 1)
        self.assertEqual(again.body["messages"], first.body["messages"])

    def test_no_marker_when_nothing_dropped(self):
        out = prep({"messages": self.msgs[:6]}, self.e)
        self.assertEqual(count_marker(out.body["messages"]), 0)
        self.assertFalse(out.pruned)

    def test_marker_never_between_call_and_its_result(self):
        msgs = [oa("system", "S"), oa("user", "T")]
        msgs += [oa("user", f"f{i}-" + big(3000)) for i in range(8)]
        msgs += oa_tool_exchange(1, 100, calls=2)
        msgs.append(oa("user", "LAST"))
        out = prep({"messages": msgs}, entry(10_000, 2_000))
        kept = out.body["messages"]
        for i, m in enumerate(kept):
            if m.get("tool_calls"):
                n = len(m["tool_calls"])
                self.assertTrue(
                    all(x["role"] == "tool" for x in kept[i + 1 : i + 1 + n])
                )

    def test_marker_cost_is_counted_in_final_proof(self):
        out = prep({"messages": self.msgs}, self.e)
        weights = sum(
            prep({"messages": [m]}, entry(10**9, 0), flags(False)).report.t_before
            for m in out.body["messages"]
            if m["content"] != ctx.MARKER_TEXT
        )
        self.assertGreaterEqual(out.report.t_after, weights - 0)
        self.assertLessEqual(out.report.t_after, out.report.b_input)


class TestSingleSerialization(unittest.TestCase):
    """I-12: полных кандидатных сериализаций ровно одна, независимо от числа удалений."""

    def _count(self, turns):
        real = json.dumps
        calls = []

        def spy(obj, *a, **kw):
            if isinstance(obj, dict) and "messages" in obj:
                calls.append(1)
            return real(obj, *a, **kw)

        with mock.patch.object(ctx.json, "dumps", spy):
            out = prep({"messages": oa_history(turns, 200)}, entry(30_000, 5_000))
        return len(calls), out

    def test_one_serialization_for_small_and_large_k(self):
        small, out_small = self._count(40)
        large, out_large = self._count(400)
        self.assertEqual((small, large), (1, 1))
        self.assertEqual(out_small.report.serializations, 1)
        self.assertGreater(
            out_large.report.units_dropped, out_small.report.units_dropped
        )

    def test_body_bytes_are_exact_final_render(self):
        out = prep({"messages": oa_history(40, 200)}, entry(30_000, 5_000))
        self.assertEqual(
            out.body_bytes,
            json.dumps(out.body, ensure_ascii=False, separators=(",", ":")).encode(),
        )

    def test_serialize_false_skips_render(self):
        out = prep(
            {"messages": oa_history(40, 200)}, entry(30_000, 5_000), serialize=False
        )
        self.assertIsNone(out.body_bytes)
        self.assertEqual(out.report.serializations, 0)

    def test_visits_are_linear_in_input(self):
        a = prep({"messages": oa_history(100, 50)}, entry(10**9, 0), flags(False))
        b = prep({"messages": oa_history(200, 50)}, entry(10**9, 0), flags(False))
        ratio = b.report.nodes_visited / a.report.nodes_visited
        self.assertAlmostEqual(ratio, (4 * 200 + 3) / (4 * 100 + 3), places=2)

    def test_prepared_invocation_is_frozen(self):
        out = prep({"messages": [oa("user", "x")]}, entry())
        with self.assertRaises(Exception):
            out.mode = "other"  # type: ignore[misc]


class TestNoFailOpen(unittest.TestCase):
    """I-06: сбой сжатия не превращается в отправку исходного тела."""

    def test_internal_error_becomes_503_zero_send(self):
        body = {"messages": oa_history(30, 500)}
        with mock.patch.object(ctx, "_components", side_effect=RuntimeError("boom")):
            with self.assertRaises(ctx.ContextUnqualified) as cm:
                prep(body, entry(60_000, 10_000))
        self.assertEqual(cm.exception.reason, "compression_failed")
        self.assertNotIn("boom", cm.exception.message())

    def test_codec_validation_failure_is_zero_send(self):
        body = {"messages": oa_history(30, 500)}
        with mock.patch.object(ctx, "_validate", return_value="invalid_role"):
            with self.assertRaises(ctx.ContextUnqualified):
                prep(body, entry(60_000, 10_000))

    def test_report_is_content_free(self):
        out = prep({"messages": oa_history(30, 500)}, entry(60_000, 10_000))
        dumped = json.dumps(out.report.as_dict()) + out.report.log_line()
        for secret in ("SYS-ANCHOR", "TASK-ANCHOR", "LAST-USER", "xxxx", "uuuu"):
            self.assertNotIn(secret, dumped)


if __name__ == "__main__":
    unittest.main()
