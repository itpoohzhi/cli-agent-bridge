"""Помощники RPC-тестов: диалог по ключу чата и разбор журнала fake_droid (не собирается как тесты)."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import BridgeCase, pid_alive, wait_until  # noqa: E402

USAGE_LINE = re.compile(r"^usage sess=(?P<sess>\S+) raw=(?P<rin>\d+)/(?P<rout>\d+) "
                        r"rep=(?P<in>\d+)/(?P<out>\d+) resumed=(?P<resumed>[01]) turns=(?P<turns>\d+)$")
DONE_LINE = re.compile(r"^done model=\S+ rc=\d+ state=\S+ .*client=\S+ ua=.*$")
EXEC_LINE = re.compile(
    r"^exec model=(?P<model>\S+) effort=(?P<effort>\S+) effort_source=(?P<source>\S+) "
    r"autonomy=(?P<autonomy>\S+) autonomy_source=(?P<autonomy_source>\S+) "
    r"prompt_bytes=(?P<bytes>\d+) (?P<tag>client=\S+ ua=.*)$")
REJECT_LINE = re.compile(r"^reject reason=[a-z0-9_]+ model=\S+ model_len=[0-9]+ client=[0-9a-f.:]+$")


class Conv:
    """Диалог одного чата DSH: история растёт, ключ prompt_cache_key постоянный."""

    def __init__(self, case, key, **extra):
        self.case = case
        self.key = key
        self.extra = extra
        self.msgs = []

    def add(self, *messages):
        self.msgs.extend(messages)
        return self

    def send(self, **more):
        body = {"model": "claude-sonnet-5-5", "messages": list(self.msgs)}
        if self.key:
            body["prompt_cache_key"] = self.key
        body.update(self.extra)
        body.update(more)
        status, data = self.case._post_json(body)
        if status == 200:
            message = data["choices"][0]["message"]
            reply = {"role": "assistant", "content": message.get("content")}
            if message.get("tool_calls"):
                reply["tool_calls"] = message["tool_calls"]
            self.msgs.append(reply)
        return status, data

    def ask(self, text, **more):
        self.msgs.append({"role": "user", "content": text})
        return self.send(**more)


class RpcCase(BridgeCase):
    def conv(self, key="chat-1", **extra):
        return Conv(self, key, **extra)

    def chat_of(self, key):
        return server.REGISTRY.chats[server._key_hash(key)]

    def texts_by_pid(self):
        """pid процесса -> [(text, skipAgentLoop)] в порядке получения."""
        result = {}
        for rec in self.hub.rpcs("droid.add_user_message"):
            result.setdefault(rec["pid"], []).append(
                (rec["params"].get("text", ""), bool(rec["params"].get("skipAgentLoop"))))
        return result

    def wait_gone(self, pid, timeout=10.0):
        return wait_until(lambda: not pid_alive(pid), timeout)

    def health(self):
        return self._get("/health")[1]


class FakeClock:
    """Подменяемые monotonic-часы моста (idle-реап без реального ожидания)."""

    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        return self.now
