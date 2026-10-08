"""RPC-ядро моста: дельта истории, изоляция чатов, title, протокольные аномалии, буфер хода.

Все сценарии идут через настоящий HTTP-сервер моста и настоящий fake-subprocess
(tests/fake_droid.py), говорящий stream-jsonrpc по stdin/stdout. Реальный droid и
сеть не используются. Идентификаторы TM-NNN — в имени метода и в docstring.
"""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import TOOLS, wait_until  # noqa: E402
from rpc_testlib import RpcCase, USAGE_LINE  # noqa: E402


def title_body(key="chat-title", filler="", max_tokens=64):
    """Запрос заголовка DSH по наблюдённой структуре (F-512)."""
    return {
        "model": "claude-sonnet-5-5",
        "max_tokens": max_tokens,
        "prompt_cache_key": key,
        "messages": [
            {
                "role": "system",
                "content": server.TITLE_SYSTEM_PREFIX
                + "\nReturn only the title on one line."
                + filler,
            },
            {
                "role": "user",
                "content": server.TITLE_USER_PREFIX + '\n[{"seq":8,"text":"hello"}]',
            },
        ],
    }


class TestDeltaAndIsolation(RpcCase):
    def test_tm001_one_chat_four_turns_one_spawn_suffix_only(self):
        """TM-001: один keyed-чат, 4 запроса: 1 spawn, 1 initialize, 4 хода; в RPC только суффикс; usage по ходу."""
        self.hub.script(
            [
                {
                    "steps": [{"op": "text", "text": f"A{i}"}],
                    "usage": {"inputTokens": 100 + 10 * i, "outputTokens": 5 + i},
                }
                for i in range(4)
            ]
        )
        chat = self.conv("chat-1")
        with self.capture_logs() as lines:
            results = [chat.ask(f"q{i}") for i in range(4)]
        for index, (status, body) in enumerate(results):
            self.assertEqual(status, 200)
            self.assertEqual(body["choices"][0]["message"]["content"], f"A{index}")
            # usage — из tokenUsage терминального события ПО ХОДУ, не кумулятив реестра droid.
            self.assertEqual(body["usage"]["prompt_tokens"], 100 + 10 * index)
            self.assertEqual(body["usage"]["completion_tokens"], 5 + index)
        self.assertEqual(len(self.hub.spawns()), 1)
        self.assertEqual(len(self.hub.inits()), 1)
        self.assertEqual(len(self.hub.admissions()), 4)
        # Эхо assistant не повторяется, предыдущие user не отправляются заново.
        self.assertEqual(self.hub.sent_texts(), ["q0", "q1", "q2", "q3"])
        usage = [USAGE_LINE.match(ln) for ln in lines if ln.startswith("usage ")]
        self.assertTrue(all(usage))
        # resumed=1 на старом мосте не различает hot-путь; различает отсутствие replay/initialize.
        self.assertEqual([m.group("resumed") for m in usage], ["0", "1", "1", "1"])
        self.assertEqual([m.group("turns") for m in usage], ["1", "2", "3", "4"])
        self.assertEqual([int(m.group("in")) for m in usage], [100, 110, 120, 130])
        self.assertEqual(len({m.group("sess") for m in usage}), 1)
        self.assertEqual(self.health()["active"], 1)

    def test_tm002_keys_isolate_chats_and_keyless_is_fresh_replay(self):
        """TM-002: разные ключи -> разные PID/SID без канарейки; без ключа — изолированный replay."""
        first = self.conv("chat-A")
        second = self.conv("chat-B")
        self.assertEqual(first.ask("привет")[0], 200)
        self.assertEqual(first.ask("CANARY-A remember")[0], 200)
        self.assertEqual(second.ask("привет")[0], 200)
        self.assertEqual(len(self.hub.spawns()), 2)
        by_pid = self.texts_by_pid()
        self.assertEqual(len(by_pid), 2)
        self.assertNotEqual(self.chat_of("chat-A").sid, self.chat_of("chat-B").sid)
        for texts in by_pid.values():
            joined = "\n".join(t for t, _ in texts)
            if "CANARY-A" in joined:
                self.assertNotIn("привет\nпривет", joined)
        other = [
            t
            for pid, texts in by_pid.items()
            for t, _ in texts
            if pid != self.chat_of("chat-A").proc.pid
        ]
        self.assertNotIn("CANARY-A remember", other)
        # Без ключа: каждое продолжение — новый процесс и replay всей истории запроса.
        keyless = self.conv(None)
        spawns_before = len(self.hub.spawns())
        self.assertEqual(keyless.ask("k0")[0], 200)
        self.assertEqual(keyless.ask("k1")[0], 200)
        self.assertEqual(len(self.hub.spawns()), spawns_before + 2)
        last_pid = self.hub.spawns()[-1]["pid"]
        self.assertEqual(
            self.texts_by_pid()[last_pid], [("k0", True), ("PONG", True), ("k1", False)]
        )
        # Форк: новый ключ с историей родителя — свой процесс и replay, родитель не затронут.
        fork = self.conv("chat-FORK")
        fork.msgs = [dict(m) for m in first.msgs]
        parent_pid = self.chat_of("chat-A").proc.pid
        self.assertEqual(fork.ask("fork-turn")[0], 200)
        fork_pid = self.chat_of("chat-FORK").proc.pid
        self.assertNotEqual(fork_pid, parent_pid)
        self.assertTrue(all(skip for _, skip in self.texts_by_pid()[fork_pid][:-1]))
        self.assertTrue(self.chat_of("chat-A").proc.alive())
        # Компакция без ключа — тоже изолированный replay (хеш префикса чаты не объединяет).
        compact = self.conv(None)
        compact.msgs = [
            {
                "role": "user",
                "content": "This is an automatically generated checkpoint",
            },
            {"role": "assistant", "content": "ok"},
        ]
        before = len(self.hub.spawns())
        self.assertEqual(compact.ask("after-compaction")[0], 200)
        self.assertEqual(len(self.hub.spawns()), before + 1)

    def test_tm003_title_is_ephemeral_by_structure_not_size(self):
        """TM-003: main+title параллельно с одним ключом: title — эфемерная сессия без записи в реестр."""
        self.hub.script(
            [{"steps": [{"op": "sleep", "s": 0.3}, {"op": "text", "text": "OK"}]}] * 2
        )
        results = {}

        def main_request():
            results["main"] = self._post_json(
                {
                    "model": "claude-sonnet-5-5",
                    "prompt_cache_key": "chat-T",
                    "messages": [{"role": "user", "content": "hello"}],
                }
            )

        def title_request():
            results["title"] = self._post_json(title_body("chat-T"))

        threads = [
            threading.Thread(target=main_request),
            threading.Thread(target=title_request),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(60)
        self.assertEqual(results["main"][0], 200)
        self.assertEqual(results["title"][0], 200)
        self.assertEqual(len(server.REGISTRY.chats), 1)  # title реестр не трогает
        chat = self.chat_of("chat-T")
        self.assertEqual(chat.state, "READY")
        inits = self.hub.inits()
        self.assertEqual(len(inits), 2)
        title_inits = [
            r
            for r in inits
            if r["params"]
            .get("systemPrompt", "")
            .startswith(server.TITLE_SYSTEM_PREFIX)
        ]
        self.assertEqual(len(title_inits), 1)
        self.assertNotEqual(title_inits[0]["pid"], chat.proc.pid)
        self.assertEqual(self.chat_of("chat-T").n, 2)  # только main: user + assistant
        # Эфемерный title-процесс закрывается и освобождает слот P.
        self.assertTrue(wait_until(lambda: server.POOL.used == 1))
        # Классификация — по структуре; размер сообщения не критерий.
        big = title_body(filler="x" * 50000)
        self.assertTrue(server._is_title_request(big["messages"], [], big))
        small = title_body()
        self.assertTrue(server._is_title_request(small["messages"], [], small))
        self.assertFalse(server._is_title_request(small["messages"], TOOLS, small))
        self.assertFalse(
            server._is_title_request(small["messages"], [], dict(small, max_tokens=65))
        )
        three = small["messages"] + [{"role": "user", "content": "more"}]
        self.assertFalse(server._is_title_request(three, [], small))
        wrong = [
            dict(small["messages"][0], content="Write a title"),
            small["messages"][1],
        ]
        self.assertFalse(server._is_title_request(wrong, [], small))

    def test_tm004_service_injections_echo_and_two_tool_calls(self):
        """TM-004: первый user != последний; echo assistant не повторяется; 2 tool_calls; суффикс из нескольких."""
        call = '<tool_call>{"name": "get_weather", "arguments": {"city": "%s"}}</tool_call>'
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "thinking", "text": "why"},
                        {"op": "text", "text": call % "A" + call % "B"},
                    ]
                },
                {"steps": [{"op": "text", "text": "done"}]},
                {"steps": [{"op": "text", "text": "ok"}]},
            ]
        )
        chat = self.conv("chat-tools", tools=TOOLS)
        chat.add(
            {"role": "system", "content": "SYS-PROMPT"},
            {"role": "user", "content": "prompt"},
            {
                "role": "user",
                "content": "<system-reminder>\nWorkspace instructions\n</system-reminder>",
            },
        )
        status, body = chat.send()
        self.assertEqual(status, 200)
        calls = body["choices"][0]["message"]["tool_calls"]
        self.assertEqual(len(calls), 2)
        self.assertNotEqual(calls[0]["id"], calls[1]["id"])
        init = self.hub.inits()[0]["params"]
        self.assertIn("SYS-PROMPT", init["systemPrompt"])
        self.assertIn("Tool calling protocol", init["systemPrompt"])
        pid = self.hub.spawns()[0]["pid"]
        first_texts = self.texts_by_pid()[pid]
        self.assertEqual(
            first_texts[0], ("prompt", True)
        )  # первый user != последний (служебный)
        self.assertTrue(first_texts[1][0].startswith("<system-reminder>"))
        self.assertFalse(first_texts[1][1])
        # Ход 2: два tool-результата + новый user: суффикс из трёх, assistant-эхо не повторяется.
        chat.add(
            {"role": "tool", "tool_call_id": calls[0]["id"], "content": "sunny"},
            {"role": "tool", "tool_call_id": calls[1]["id"], "content": "rain"},
            {"role": "user", "content": "and then?"},
        )
        self.assertEqual(chat.send()[0], 200)
        self.assertEqual(len(self.hub.spawns()), 1)  # горячий путь, без replay
        second = self.texts_by_pid()[pid][2:]
        self.assertEqual(
            second,
            [
                ("[tool result %s]\nsunny" % calls[0]["id"], True),
                ("[tool result %s]\nrain" % calls[1]["id"], True),
                ("and then?", False),
            ],
        )
        # Ход 3: reasoning в сверке не участвует — продолжение остаётся горячим.
        self.assertEqual(chat.ask("last")[0], 200)
        self.assertEqual(len(self.hub.spawns()), 1)
        self.assertEqual(len(self.hub.inits()), 1)

    def test_tm005_divergence_gives_new_generation_with_replay(self):
        """TM-005: форк, правка префикса, компакция, смена tools/system/cwd -> новая generation с replay."""
        other_cwd = tempfile.mkdtemp(prefix="bridge-cwd-")
        cases = {
            "prefix_edit": lambda c: (
                c.msgs.__setitem__(0, {"role": "user", "content": "EDITED"}),
                c.ask("next"),
            )[1],
            "compaction": lambda c: (
                setattr(
                    c,
                    "msgs",
                    [
                        {"role": "user", "content": "checkpoint"},
                        {"role": "assistant", "content": "ok"},
                    ],
                ),
                c.ask("next"),
            )[1],
            "tools_change": lambda c: c.ask("next", tools=TOOLS),
            "system_change": lambda c: (
                c.msgs.insert(0, {"role": "system", "content": "NEW-SYSTEM"}),
                c.ask("next"),
            )[1],
            "cwd_change": lambda c: c.ask("next", extra_body={"cwd": other_cwd}),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                key = "chat-" + name
                chat = self.conv(key)
                self.assertEqual(chat.ask("q0")[0], 200)
                self.assertEqual(chat.ask("q1")[0], 200)
                old = self.chat_of(key)
                old_pid, old_sid, generation = old.proc.pid, old.sid, old.generation
                inits_before = len(self.hub.inits())
                self.assertEqual(mutate(chat)[0], 200)
                new = self.chat_of(key)
                self.assertEqual(len(self.hub.inits()), inits_before + 1)
                self.assertNotEqual(new.proc.pid, old_pid)
                self.assertNotEqual(
                    new.sid, old_sid
                )  # скрытое состояние родителя не используется
                self.assertEqual(new.generation, generation + 1)
                texts = self.texts_by_pid()[new.proc.pid]
                self.assertTrue(
                    all(skip for _, skip in texts[:-1])
                )  # replay без LLM-ходов
                self.assertFalse(texts[-1][1])
                self.assertGreaterEqual(len(texts), 2)
                self.assertTrue(self.wait_gone(old_pid))
        # Новый ключ с историей чужого чата (форк) — отдельная generation без hot-пути.
        parent = self.conv("chat-parent")
        parent.ask("p0")
        parent.ask("p1")
        fork = self.conv("chat-forked")
        fork.msgs = [dict(m) for m in parent.msgs]
        self.assertEqual(fork.ask("fork")[0], 200)
        self.assertNotEqual(
            self.chat_of("chat-forked").sid, self.chat_of("chat-parent").sid
        )

    def test_tm006_ack_is_not_completion_and_anomalies_keep_error_taxonomy(self):
        """TM-006: ACK не завершает ход; чужой sessionId/дубль ACK/невалидный JSON/EOF -> прежние ошибки."""
        # ACK приходит мгновенно, текст — только после терминального события хода.
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "sleep", "s": 0.4},
                        {"op": "text", "text": "LATE-TEXT"},
                    ]
                }
            ]
        )
        started = time.monotonic()
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "prompt_cache_key": "c-ack",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "LATE-TEXT")
        self.assertGreaterEqual(time.monotonic() - started, 0.4)
        # Чужой sessionId, неизвестная необязательная нотификация и дубль ACK хода не ломают и не завершают.
        self.hub.configure(dup_ack=True)
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "foreign_terminal"},
                        {
                            "op": "notify",
                            "type": "some_new_optional_event",
                            "fields": {"x": 1},
                        },
                        {"op": "text", "text": "REAL"},
                    ],
                    "usage": {"inputTokens": 7, "outputTokens": 3},
                }
            ]
        )
        chat = self.conv("c-anomaly")
        status, body = chat.ask("hi")
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "REAL")
        self.assertEqual(
            body["usage"]["prompt_tokens"], 7
        )  # терминал чужой сессии не засчитан
        # Невалидный JSON посреди хода -> прежний 502 proxy_error без ретрая.
        self.hub.configure(dup_ack=False)
        self.hub.script([{"steps": [{"op": "garbage"}]}])
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        # EOF посреди хода: до 3 попыток, итог — прежний 502 proxy_error.
        before = len(self.hub.admissions())
        self.hub.script([{"steps": [{"op": "exit", "rc": 1, "stderr": "boom"}]}] * 3)
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")
        self.assertEqual(len(self.hub.admissions()) - before, 3)
        # Ошибка ответа на add (JSON-RPC error) — pump_error -> 502, без ретраев.
        self.hub.configure(ack_error=True)
        before = len(self.hub.admissions())
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "proxy_error")

    def test_tm007_settings_update_readback_and_no_silent_substitution(self):
        """TM-007: смена model/effort/autonomy на границе хода: update+read-back; подмена модели отвергается."""
        chat = self.conv(
            "chat-settings", model="deepseek-v4.1-flash", reasoning_effort="high"
        )
        self.assertEqual(chat.ask("q0")[0], 200)
        init = self.hub.inits()[0]["params"]
        self.assertEqual(init["autonomyLevel"], "high")
        self.assertIs(init["autoRejectPermissionRequests"], True)
        # Нативные tools отключены по актуальному list_tools независимо от autonomy.
        disabled = [
            r["params"]["disabledToolIds"]
            for r in self.hub.rpcs("droid.update_session_settings")
            if "disabledToolIds" in r["params"]
        ]
        self.assertEqual(disabled, [["Read", "Execute", "Edit", "web_search"]])
        # Смена effort и autonomy на горячем чате: update_session_settings, без нового spawn/init.
        chat.extra.update(reasoning_effort="max", autonomy="off")
        self.assertEqual(chat.ask("q1")[0], 200)
        updates = [
            r["params"]
            for r in self.hub.rpcs("droid.update_session_settings")
            if "reasoningEffort" in r["params"]
        ]
        self.assertEqual(
            updates,
            [
                {
                    "modelId": "deepseek-v4.1-flash",
                    "reasoningEffort": "max",
                    "autonomyLevel": "off",
                }
            ],
        )
        self.assertEqual(len(self.hub.spawns()), 1)
        self.assertEqual(len(self.hub.inits()), 1)
        self.assertEqual(
            self.chat_of("chat-settings").settings,
            ("deepseek-v4.1-flash", "max", "off"),
        )
        # Молчаливая подмена модели при update: read-back не совпал -> 502 droid_error.
        self.hub.configure(substitute_model="some-default-model")
        chat.extra.update(reasoning_effort="high")
        status, body = chat.ask("q2")
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "droid_error")
        self.assertIn("substituted", body["error"]["message"])
        # ...и при initialize (droid молча подставляет модель по умолчанию, F-214).
        admissions = len(self.hub.admissions())
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "prompt_cache_key": "chat-sub",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 502)
        self.assertEqual(body["error"]["type"], "droid_error")
        self.assertEqual(len(self.hub.admissions()), admissions)  # LLM-ход не начат
        self.hub.configure(substitute_model=None)
        # Смена systemPrompt (tools) -> rebase, а не update.
        other = self.conv("chat-system")
        other.ask("s0")
        inits_before = len(self.hub.inits())
        self.assertEqual(other.ask("s1", tools=TOOLS)[0], 200)
        self.assertEqual(len(self.hub.inits()), inits_before + 1)


class TestTurnBuffer(RpcCase):
    def test_tm011_retract_and_retry_commit_only_final(self):
        """TM-011: llm_retry/assistant_message_retracted после text_complete: отдаётся ровно закоммиченное."""
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "draft"},
                        {"op": "retry"},
                        {"op": "retract"},
                        {"op": "text", "text": "final"},
                    ]
                },
                {
                    "steps": [
                        {"op": "text", "text": "first message"},
                        {"op": "text", "text": "second message"},
                    ]
                },
                {
                    "steps": [
                        {"op": "thinking", "text": "because"},
                        {
                            "op": "text",
                            "text": server.TOOL_CALL_OPEN
                            + '{"name": "get_weather", "arguments": {"city": "X"}}'
                            + server.TOOL_CALL_CLOSE,
                        },
                    ]
                },
            ]
        )
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "one"}],
            }
        )
        self.assertEqual(body["choices"][0]["message"]["content"], "final")
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "messages": [{"role": "user", "content": "two"}],
            }
        )
        self.assertEqual(
            body["choices"][0]["message"]["content"], "first message\n\nsecond message"
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "tools": TOOLS,
                "messages": [{"role": "user", "content": "three"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertIn('"reasoning_content": "because"', stream)
        self.assertIn('"tool_calls"', stream)
        self.assertIn('"finish_reason": "tool_calls"', stream)
        self.assertNotIn("draft", stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))
        # Ошибка после retract: прежние error-кадр и DONE, незакоммиченное не утекло.
        self.hub.script(
            [
                {
                    "steps": [
                        {"op": "text", "text": "to-be-retracted"},
                        {"op": "retry"},
                        {"op": "retract"},
                        {"op": "error", "message": "model exploded"},
                    ],
                    "reason": "model_request_rejected",
                }
            ]
        )
        status, stream = self._post(
            {
                "model": "claude-sonnet-5-5",
                "stream": True,
                "messages": [{"role": "user", "content": "four"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertIn("model exploded", stream)
        self.assertNotIn("to-be-retracted", stream)
        self.assertNotIn('"finish_reason": "stop"', stream)
        self.assertTrue(stream.rstrip().endswith("data: [DONE]"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
