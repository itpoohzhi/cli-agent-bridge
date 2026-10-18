"""VER-005: динамическая смена целевых окон Argon 1M → Wonder 400k → Claude 200k → Argon 1M.

Ядро политики не знает портов и имён моделей: смена маршрута = другой `RouteEntry`.

Запуск: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest -v test_context_resilience_switching
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from core import context_resilience as ctx  # noqa: E402
from context_testlib import entry, flags, oa, oa_history, oracle_total, tool_ids  # noqa: E402

ARGON = entry(1_000_000, 65_536, model="argon", protocol="openai")
WONDER = entry(400_000, 131_072, model="wonder")
CLAUDE = entry(200_000, 128_000, model="claude-p")
SEQUENCE = (ARGON, WONDER, CLAUDE, ARGON)


def history(total_bytes, per_turn=9_000):
    """История ≈ total_bytes: каждый ход = assistant + вызов + результат + user."""
    size = per_turn // 3
    return oa_history(max(1, total_bytes // per_turn), size)


def run(hist, e, **kw):
    return ctx.prepare({"messages": hist}, e, flags(), serialize=False, **kw)


class TestSwitchSequence(unittest.TestCase):
    def _walk(self, hist):
        outs = []
        for e in SEQUENCE:
            out = run(hist, e)
            outs.append(out)
            r = out.report
            self.assertLessEqual(r.t_after, r.b_input, e.model)
            self.assertLessEqual(
                oracle_total({"messages": out.body["messages"]}), r.b_input
            )
            msgs = out.body["messages"]
            self.assertEqual(msgs[0], hist[0])
            self.assertEqual(msgs[1], hist[1])
            self.assertEqual(msgs[-1], hist[-1])
            provided, needed = tool_ids(msgs)
            self.assertEqual(provided, needed)
        return outs

    def test_big_history_5_9_mib_fits_every_target_zero_oversized_send(self):
        hist = history(5_900_000)
        self.assertGreater(len(hist), 2_000)
        outs = self._walk(hist)
        self.assertTrue(all(o.pruned for o in outs))
        kept = [len(o.body["messages"]) for o in outs]
        self.assertGreater(kept[0], kept[1])
        self.assertGreater(kept[1], kept[2])
        self.assertEqual(kept[0], kept[3])  # возврат на Argon детерминирован

    def test_three_point_seven_mib_history(self):
        outs = self._walk(history(3_700_000))
        self.assertEqual(
            [o.report.context_window for o in outs],
            [1_000_000, 400_000, 200_000, 1_000_000],
        )

    def test_half_mib_history_passes_1m_prunes_smaller_windows(self):
        hist = history(500_000)
        flags_seen = [run(hist, e).pruned for e in SEQUENCE]
        self.assertEqual(flags_seen, [False, True, True, False])
        back = run(hist, ARGON)
        self.assertIs(
            back.body["messages"], hist
        )  # возврат на 1M: полная история, не обрезок

    def test_tokens_above_400k_and_above_1m_are_separate_cases(self):
        over_400k = history(600_000)
        self.assertEqual(
            [run(over_400k, e).pruned for e in (ARGON, WONDER)], [False, True]
        )
        over_1m = history(1_300_000)
        self.assertEqual(
            [run(over_1m, e).pruned for e in (ARGON, WONDER)], [True, True]
        )

    def test_requested_output_changes_budget_not_history(self):
        hist = history(300_000)
        small_out = ctx.prepare(
            {"messages": hist, "max_tokens": 1_000}, CLAUDE, flags(), serialize=False
        )
        big_out = ctx.prepare(
            {"messages": hist, "max_tokens": 128_000}, CLAUDE, flags(), serialize=False
        )
        self.assertEqual(small_out.report.r_output, 1_000)
        self.assertEqual(big_out.report.r_output, 128_000)
        self.assertGreater(small_out.report.b_input, big_out.report.b_input)
        self.assertGreaterEqual(
            len(small_out.body["messages"]), len(big_out.body["messages"])
        )
        over_max = ctx.prepare(
            {"messages": hist, "max_tokens": 10**9}, CLAUDE, flags(), serialize=False
        )
        self.assertEqual(
            over_max.report.r_output, 128_000
        )  # не выше допущенного предела модели

    def test_arbitrary_ids_and_unicode_do_not_matter(self):
        msgs = [oa("system", "S"), oa("user", "T")]
        for i in range(60):
            cid = f"вызов-{i}-☃-" + "x" * 40
            msgs.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": cid,
                            "type": "function",
                            "function": {"name": "f", "arguments": "{}"},
                        }
                    ],
                }
            )
            msgs.append({"role": "tool", "tool_call_id": cid, "content": "й" * 3000})
            msgs.append(oa("user", f"q{i}"))
        msgs.append(oa("user", "LAST"))
        out = run(msgs, entry(30_000, 5_000))
        self.assertTrue(out.pruned)
        provided, needed = tool_ids(out.body["messages"])
        self.assertEqual(provided, needed)
        self.assertLessEqual(out.report.t_after, out.report.b_input)

    def test_switch_with_trusted_chat_never_reuses_other_models_epoch(self):
        store = ctx.EpochStore()
        identity = ctx.build_identity("o", "ns", [("x-session-id", "chat-1")])
        hist = history(700_000)
        gens = []
        for e in SEQUENCE:
            out = run(hist, e, identity=identity, store=store)
            gens.append((out.report.epoch, out.report.generation))
            self.assertLessEqual(out.report.t_after, out.report.b_input)
        self.assertEqual(gens[0], ("miss", 0))  # 1M: история помещается, эпоха не нужна
        self.assertEqual(gens[1][1], 1)
        self.assertEqual(gens[2][1], 1)
        self.assertEqual(gens[3], ("miss", 0))
        self.assertEqual(len(store), 2)  # по эпохе на каждую меньшую модель
        wonder_again = run(hist, WONDER, identity=identity, store=store)
        self.assertEqual(
            (wonder_again.report.epoch, wonder_again.report.generation), ("hit", 1)
        )

    def test_headers_follow_each_target(self):
        hist = history(500_000)
        headers = [run(hist, e).header for e in SEQUENCE]
        self.assertEqual(
            [h[1] for h in headers if h], ["false", "true", "true", "false"]
        )

    def test_no_new_http_status_in_core(self):
        # Ядро никогда не порождает 413: транспортные лимиты принадлежат фасадам.
        statuses = {ctx.ContextRejected.status, ctx.ContextUnqualified.status}
        self.assertEqual(statuses, {400, 503})

    def test_route_specific_body_caps_are_not_touched(self):
        self.assertEqual(server.FLEET["image_limits"]["max_body_bytes"], 33_554_432)


class TestSwitchProtocolsAcrossTargets(unittest.TestCase):
    """Одна и та же нейтральная политика на трёх форматах при смене окон."""

    def test_google_to_openai_to_anthropic_budgets_are_recomputed(self):
        from test_context_resilience_protocols import an_body, g_body

        g = ctx.prepare(
            g_body(40, 600), entry(30_000, 2_000, protocol="google"), flags()
        )
        o = ctx.prepare({"messages": history(120_000)}, entry(30_000, 2_000), flags())
        a = ctx.prepare(
            an_body(40, 600), entry(30_000, 2_000, protocol="anthropic"), flags()
        )
        for out in (g, o, a):
            self.assertTrue(out.pruned)
            self.assertLessEqual(out.report.t_after, out.report.b_input)
            self.assertEqual(out.report.b_input, 30_000 - out.report.r_output)


if __name__ == "__main__":
    unittest.main()
