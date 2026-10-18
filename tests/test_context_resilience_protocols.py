"""VER-003: роли, чередование, reasoning/signature, заголовок X-DSH-Context-Pruned по протоколам.

Запуск: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests python3 -m unittest -v test_context_resilience_protocols
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import context_resilience as ctx  # noqa: E402
from context_testlib import big, entry, flags, oa, oa_history, tool_ids  # noqa: E402


# ---- Anthropic ---------------------------------------------------------------


def an_history(turns, size):
    msgs = [{"role": "user", "content": "TASK-ANCHOR"}]
    for i in range(turns):
        msgs.append(
            {
                "role": "assistant",
                "content": [
                    {"type": "thinking", "thinking": f"t{i}", "signature": f"SIG{i}"},
                    {"type": "text", "text": f"a{i}-" + big(size)},
                    {
                        "type": "tool_use",
                        "id": f"tu_{i}",
                        "name": "f",
                        "input": {"k": 1},
                    },
                ],
            }
        )
        msgs.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": f"tu_{i}",
                        "content": big(size, "r"),
                    }
                ],
            }
        )
        msgs.append({"role": "assistant", "content": f"done{i}"})
        msgs.append({"role": "user", "content": f"u{i}-" + big(size, "u")})
    msgs.append({"role": "user", "content": "LAST-USER"})
    return msgs


def an_body(turns=30, size=400):
    return {
        "system": "SYS-ANCHOR",
        "max_tokens": 1000,
        "tools": [{"name": "f", "input_schema": {"type": "object"}}],
        "messages": an_history(turns, size),
    }


def an_pairs(msgs):
    use, res = set(), set()
    for m in msgs:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_use":
                    use.add(b["id"])
                elif b.get("type") == "tool_result":
                    res.add(b["tool_use_id"])
    return use, res


# ---- Google ---------------------------------------------------------------


def g_history(turns, size):
    msgs = [{"role": "user", "parts": [{"text": "TASK-ANCHOR"}]}]
    for i in range(turns):
        msgs.append(
            {
                "role": "model",
                "parts": [
                    {"text": f"think{i}", "thought": True},
                    {
                        "functionCall": {"name": "f", "args": {"i": i}},
                        "thoughtSignature": f"SIG{i}",
                    },
                ],
            }
        )
        msgs.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": "f",
                            "response": {"v": big(size, "r")},
                        }
                    }
                ],
            }
        )
        msgs.append({"role": "model", "parts": [{"text": f"a{i}-" + big(size)}]})
        msgs.append({"role": "user", "parts": [{"text": f"u{i}-" + big(size, "u")}]})
    msgs.append({"role": "user", "parts": [{"text": "LAST-USER"}]})
    return msgs


def g_body(turns=30, size=400):
    return {
        "systemInstruction": {"parts": [{"text": "SYS-ANCHOR"}]},
        "generationConfig": {"maxOutputTokens": 1000},
        "contents": g_history(turns, size),
    }


def g_counts(msgs):
    calls = resp = 0
    for m in msgs:
        for p in m["parts"]:
            calls += "functionCall" in p
            resp += "functionResponse" in p
    return calls, resp


class TestOpenAI(unittest.TestCase):
    def test_roles_and_pairs_after_prune(self):
        out = ctx.prepare(
            {"messages": oa_history(30, 500)}, entry(60_000, 10_000), flags()
        )
        self.assertTrue(out.pruned)
        roles = {m["role"] for m in out.body["messages"]}
        self.assertLessEqual(roles, {"system", "user", "assistant", "tool"})
        provided, needed = tool_ids(out.body["messages"])
        self.assertEqual(provided, needed)

    def test_reasoning_preserved_by_default_and_stripped_by_policy(self):
        msgs = oa_history(3, 50)
        msgs[2] = dict(
            msgs[2],
            reasoning_content="THINK",
            tool_calls=[
                {
                    "id": "c",
                    "type": "function",
                    "function": {"name": "f", "arguments": "{}"},
                    "extra_content": {"google": {"thought_signature": "SIG"}},
                }
            ],
        )
        msgs.insert(3, {"role": "tool", "tool_call_id": "c", "content": "r"})
        keep = ctx.prepare({"messages": msgs}, entry(), flags())
        self.assertEqual(keep.body["messages"][2]["reasoning_content"], "THINK")
        before = copy.deepcopy(msgs)
        strip = ctx.prepare(
            {"messages": msgs}, entry(reasoning_policy="strip"), flags()
        )
        sent = strip.body["messages"][2]
        self.assertNotIn("reasoning_content", sent)
        self.assertNotIn("extra_content", sent["tool_calls"][0])
        self.assertEqual(sent["tool_calls"][0]["id"], "c")  # связь с результатом цела
        self.assertEqual(strip.report.reasoning_stripped, 2)
        self.assertEqual(msgs, before)  # исходный журнал не мутирован


class TestAnthropic(unittest.TestCase):
    def setUp(self):
        self.e = entry(20_000, 2_000, protocol="anthropic")

    def test_prune_keeps_alternation_inputs_pairs_and_system(self):
        body = an_body()
        out = ctx.prepare(body, self.e, flags())
        self.assertTrue(out.pruned)
        kept = out.body["messages"]
        self.assertEqual({m["role"] for m in kept}, {"user", "assistant"})
        self.assertEqual(kept[0]["role"], "user")
        self.assertEqual(kept[0]["content"], "TASK-ANCHOR")
        use, res = an_pairs(kept)
        self.assertEqual(use, res)
        self.assertEqual(out.body["system"], "SYS-ANCHOR")
        self.assertEqual(out.body["tools"], body["tools"])
        self.assertEqual(kept[-1]["content"], "LAST-USER")

    def test_marker_is_user_text_block(self):
        out = ctx.prepare(an_body(), self.e, flags())
        markers = [
            m
            for m in out.body["messages"]
            if m["content"] == [{"type": "text", "text": ctx.MARKER_TEXT}]
        ]
        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["role"], "user")

    def test_thinking_signature_travels_with_its_message(self):
        body = an_body()
        out = ctx.prepare(body, self.e, flags())
        originals = {id(m) for m in body["messages"]}
        for m in out.body["messages"]:
            if (
                isinstance(m["content"], list)
                and m["content"][0].get("type") == "thinking"
            ):
                self.assertIn(
                    id(m), originals
                )  # исходный объект, подпись не пересоздана
                self.assertTrue(m["content"][0]["signature"].startswith("SIG"))

    def test_strip_policy_removes_whole_thinking_bundle_only(self):
        body = an_body(turns=3, size=20)
        before = copy.deepcopy(body)
        out = ctx.prepare(
            body, entry(protocol="anthropic", reasoning_policy="strip"), flags()
        )
        blocks = [
            b
            for m in out.body["messages"]
            if isinstance(m["content"], list)
            for b in m["content"]
        ]
        self.assertFalse(
            any(b.get("type") in ("thinking", "redacted_thinking") for b in blocks)
        )
        self.assertTrue(any(b.get("type") == "tool_use" for b in blocks))
        use, res = an_pairs(out.body["messages"])
        self.assertEqual(use, res)
        self.assertEqual(out.report.reasoning_stripped, 3)
        self.assertEqual(body, before)

    def test_thinking_only_message_is_not_emptied(self):
        msgs = [
            {"role": "user", "content": "T"},
            {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": "x", "signature": "S"}],
            },
            {"role": "user", "content": "LAST"},
        ]
        out = ctx.prepare(
            {"messages": msgs},
            entry(protocol="anthropic", reasoning_policy="strip"),
            flags(),
        )
        self.assertEqual(out.body["messages"][1]["content"][0]["type"], "thinking")

    def test_base64_image_is_not_text(self):
        msgs = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "data": big(100_000)},
                    },
                    {"type": "text", "text": "what"},
                ],
            }
        ]
        with self.assertRaises(ctx.ContextUnqualified):
            ctx.prepare({"messages": msgs}, entry(protocol="anthropic"), flags())
        out = ctx.prepare(
            {"messages": msgs}, entry(protocol="anthropic", image_tokens=1500), flags()
        )
        self.assertLess(out.report.t_before, 1700)

    def test_dangling_tool_result_in_first_message_is_validated(self):
        self.assertEqual(
            ctx._validate(
                "anthropic",
                [
                    {"role": "assistant", "content": "x"},
                    {"role": "user", "content": "y"},
                ],
                2,
            ),
            "first_message_not_user",
        )


class TestGoogle(unittest.TestCase):
    def setUp(self):
        self.e = entry(20_000, 2_000, protocol="google")

    def test_prune_keeps_roles_and_function_pairs(self):
        body = g_body()
        out = ctx.prepare(body, self.e, flags())
        self.assertTrue(out.pruned)
        kept = out.body["contents"]
        self.assertLessEqual({m["role"] for m in kept}, {"user", "model"})
        self.assertEqual(kept[0]["parts"][0]["text"], "TASK-ANCHOR")
        calls, resp = g_counts(kept)
        self.assertEqual(calls, resp)
        self.assertEqual(out.body["systemInstruction"], body["systemInstruction"])
        self.assertEqual(kept[-1]["parts"][0]["text"], "LAST-USER")
        self.assertNotIn("messages", out.body)

    def test_output_budget_read_from_generation_config(self):
        out = ctx.prepare(g_body(), self.e, flags())
        self.assertEqual(out.report.r_output, 1000)

    def test_thought_signature_preserved_on_same_target(self):
        out = ctx.prepare(g_body(), self.e, flags())
        sigs = [
            p["thoughtSignature"]
            for m in out.body["contents"]
            for p in m["parts"]
            if "thoughtSignature" in p
        ]
        self.assertTrue(sigs)
        self.assertTrue(all(s.startswith("SIG") for s in sigs))

    def test_strip_policy_drops_thought_parts_and_signatures(self):
        body = g_body(turns=3, size=20)
        before = copy.deepcopy(body)
        out = ctx.prepare(
            body, entry(protocol="google", reasoning_policy="strip"), flags()
        )
        for m in out.body["contents"]:
            for p in m["parts"]:
                self.assertNotIn("thoughtSignature", p)
                self.assertIsNot(p.get("thought"), True)
        calls, resp = g_counts(out.body["contents"])
        self.assertEqual((calls, resp), (3, 3))
        self.assertEqual(body, before)

    def test_inline_data_is_modality_not_text(self):
        contents = [
            {
                "role": "user",
                "parts": [
                    {"inlineData": {"mimeType": "image/png", "data": big(50_000)}}
                ],
            }
        ]
        with self.assertRaises(ctx.ContextUnqualified):
            ctx.prepare({"contents": contents}, entry(protocol="google"), flags())

    def test_tool_schema_property_named_like_media_is_text(self):
        body = {
            "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "f",
                            "parameters": {
                                "properties": {"image_url": {"type": "string"}}
                            },
                        }
                    ]
                }
            ],
        }
        out = ctx.prepare(body, entry(protocol="google"), flags())
        self.assertFalse(out.pruned)

    def test_validator_rejects_google_unpaired_response(self):
        bad = [
            {"role": "user", "parts": [{"text": "t"}]},
            {
                "role": "user",
                "parts": [{"functionResponse": {"name": "g", "response": {}}}],
            },
        ]
        self.assertEqual(ctx._validate("google", bad, 2), "dangling_tool_result")


class TestHeaderAndFinalProof(unittest.TestCase):
    def test_header_true_false_and_unknown(self):
        pruned = ctx.prepare(
            {"messages": oa_history(30, 500)}, entry(60_000, 10_000), flags()
        )
        self.assertEqual(pruned.header, (ctx.PRUNED_HEADER, "true"))
        plain = ctx.prepare({"messages": [oa("user", "hi")]}, entry(), flags())
        self.assertEqual(plain.header, ("X-DSH-Context-Pruned", "false"))
        off = ctx.prepare(
            {"messages": [oa("user", "hi")]}, entry(enrolled=False), flags(False)
        )
        self.assertIsNone(off.header)
        native = ctx.prepare(
            {"messages": []}, ctx.NATIVE_COMPACTION_ENTRY, flags(False)
        )
        self.assertIsNone(native.header)
        shadow = ctx.prepare(
            {"messages": oa_history(30, 500)},
            entry(60_000, 10_000, enrolled=False),
            flags(False, shadow=True),
        )
        self.assertIsNone(shadow.header)

    def test_no_post_proof_mutation_bytes_match_body(self):
        out = ctx.prepare(
            {"messages": oa_history(30, 500)}, entry(60_000, 10_000), flags()
        )
        self.assertEqual(json.loads(out.body_bytes), json.loads(json.dumps(out.body)))
        self.assertLessEqual(out.report.t_after, out.report.b_input)

    def test_protocol_detection(self):
        self.assertEqual(ctx.detect_protocol({"contents": []}), "google")
        self.assertEqual(ctx.detect_protocol({"messages": []}), "openai")

    def test_unknown_protocol_is_unqualified(self):
        with self.assertRaises(ctx.ContextUnqualified):
            ctx.prepare({"messages": []}, entry(), flags(), protocol="responses")

    def test_google_body_shape_is_not_changed_for_passthrough(self):
        body = g_body(2, 10)
        out = ctx.prepare(body, entry(protocol="google"), flags())
        self.assertIs(out.body["contents"], body["contents"])
        self.assertEqual(set(out.body), set(body))


if __name__ == "__main__":
    unittest.main()
