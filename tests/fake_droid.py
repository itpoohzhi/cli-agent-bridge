"""Фейковый `droid exec` для тестов моста: НАСТОЯЩИЙ subprocess, говорящий stream-jsonrpc.

Запускается заглушкой-лончером (`DROID_LAUNCHER`), читает JSON-RPC со stdin и пишет
ответы/нотификации в stdout по протоколу droid (конверт request/response,
`droid.session_notification`, ACK add_user_message мгновенный и НЕ завершает ход,
завершение — `agent_turn_completed`). Без сети, без ключей, без реального droid.

Управление — каталогом `FAKE_DROID_DIR`:
  config.json   — настройки (tools, substitute_model, load_scaffolding, ...) и очередь
                  сценариев хода (`scenarios`); читается на каждом запросе;
  turn.counter  — общий для процессов счётчик сценариев (flock);
  sessions/     — «диск» сессий (load_session после смерти процесса);
  log.jsonl     — журнал: spawn, каждый полученный запрос, exit (для проверок тестов).

Сценарий хода — список шагов {"op": ...} либо словарь {"steps": [...], "reason": ...,
"usage": {...}, "late": true}. Шаги: text, thinking, retry, retract, error, sleep, hang,
exit, garbage, foreign_terminal, stale_terminal, big_line, flood, notify.
Конфиг: stall_after=N — перестать читать stdin после N строк (завис); omit_autonomy,
omit_disabled_ids, raw_tools, echo_flags/flags_override — искажение read-back.
"""

from __future__ import annotations

import fcntl
import json
import os
import queue
import sys
import threading
import time
import uuid

API = "1.0.0"
DEFAULT_TOOLS = ["Read", "Execute", "Edit", "web_search"]
# Фиктивный ключ тестового окружения (bridge_testlib подставляет его вместо реального).
TEST_FACTORY_KEY = "bridge-test-factory-key-not-real"


class Fake:
    def __init__(self, base: str, argv: list):
        self.base = base
        self.argv = argv
        self.pid = os.getpid()
        self.inq: queue.Queue = queue.Queue()
        self.out_lock = threading.Lock()
        self.sid = ""
        self.messages: list = []
        self.settings: dict = {}
        self.cumulative = {"inputTokens": 0, "outputTokens": 0}
        self.seq = 0
        self.eof = False
        self.prev_turn_id = ""
        self.log({"ev": "spawn", "argv": argv, "cwd": os.getcwd(), **self._env_facts()})

    # -- журнал и конфиг -------------------------------------------------------
    def _env_facts(self) -> dict:
        cwd = os.getcwd()
        files = {}
        for name in sorted(os.listdir(cwd)):
            path = os.path.join(cwd, name)
            if os.path.isfile(path):
                files[name] = oct(os.stat(path).st_mode & 0o777)
        home = os.environ.get("FACTORY_HOME_OVERRIDE", "")
        return {
            "cwd_mode": oct(os.stat(cwd).st_mode & 0o777), "cwd_files": files,
            "bridge_key_in_env": "DROID_DSH_BRIDGE_KEY" in os.environ,
            # Значение ключа в журнал НЕ пишется: только факт наличия и совпадение с ожидаемым
            # (FAKE_DROID_EXPECT_KEY либо тестовый sentinel).
            "factory_api_key_present": bool(os.environ.get("FACTORY_API_KEY")),
            "factory_api_key_expected": os.environ.get("FACTORY_API_KEY", "") == (
                os.environ.get("FAKE_DROID_EXPECT_KEY") or TEST_FACTORY_KEY),
            "factory_home": home,
            "factory_home_mode": oct(os.stat(home).st_mode & 0o777) if home and os.path.isdir(home) else "",
            "droid_auto": os.environ.get("DROID_AUTO", ""),
            "droid_bin": os.environ.get("DROID_BIN", ""),
            "env_names": sorted(os.environ),
        }

    def log(self, record: dict) -> None:
        record = dict(record, pid=self.pid, t=time.time())
        line = json.dumps(record, ensure_ascii=False) + "\n"
        fd = os.open(os.path.join(self.base, "log.jsonl"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)

    def config(self) -> dict:
        try:
            with open(os.path.join(self.base, "config.json"), encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, ValueError):
            return {}

    def claim_scenario(self):
        path = os.path.join(self.base, "turn.counter")
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            raw = os.read(fd, 32).decode() or "0"
            index = int(raw)
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, str(index + 1).encode())
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        scenarios = self.config().get("scenarios") or []
        return scenarios[index] if index < len(scenarios) else None

    # -- вывод -----------------------------------------------------------------
    def emit(self, obj: dict) -> None:
        data = (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
        with self.out_lock:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()

    def raw(self, text: str) -> None:
        with self.out_lock:
            sys.stdout.buffer.write((text + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()

    def respond(self, rid, result=None, error=None) -> None:
        msg = {"type": "response", "jsonrpc": "2.0", "factoryApiVersion": API, "id": rid}
        if error is not None:
            msg["error"] = error
        else:
            msg["result"] = result if result is not None else {}
        self.emit(msg)

    def notify(self, ntype: str, sid=None, with_sid: bool = True, **fields) -> None:
        # Как у реального droid: settings_updated приходит БЕЗ sessionId в params (F-206, p2.jsonl).
        params = {"notification": dict({"type": ntype}, **fields)}
        if with_sid:
            params["sessionId"] = sid if sid is not None else self.sid
        self.emit({"type": "notification", "jsonrpc": "2.0", "factoryApiVersion": API,
                   "method": "droid.session_notification", "params": params})

    # -- сессии ------------------------------------------------------------------
    def _session_path(self, sid: str) -> str:
        os.makedirs(os.path.join(self.base, "sessions"), exist_ok=True)
        return os.path.join(self.base, "sessions", sid + ".json")

    def save(self) -> None:
        with open(self._session_path(self.sid), "w", encoding="utf-8") as handle:
            json.dump({"messages": self.messages, "settings": self.settings}, handle, ensure_ascii=False)

    def _model(self) -> str:
        return self.config().get("substitute_model") or self.settings.get("modelId", "")

    def public_settings(self) -> dict:
        shown = dict(self.settings)
        shown["modelId"] = self._model()
        cfg = self.config()
        if cfg.get("omit_autonomy"):
            shown.pop("autonomyLevel", None)
        if cfg.get("omit_disabled_ids"):
            shown.pop("disabledToolIds", None)
        if cfg.get("echo_flags"):
            # Реальный droid эти флаги в settings не сообщает; режим нужен для проверки расхождения.
            shown.update({"disableBuiltinSkills": True, "autoRejectPermissionRequests": True})
            shown.update(cfg.get("flags_override") or {})
        return shown

    def _service_message(self, text: str) -> dict:
        self.seq += 1
        return {"id": f"svc{self.seq}", "role": "user", "content": [{"type": "text", "text": text}]}

    # -- запросы -----------------------------------------------------------------
    def handle(self, req: dict) -> None:
        method = req.get("method")
        rid = req.get("id")
        params = req.get("params") or {}
        self.log({"ev": "rpc", "method": method, "params": params, "id": rid})
        cfg = self.config()
        if method == "droid.initialize_session":
            if cfg.get("exit_on_init") is not None:
                sys.stderr.write(str(cfg.get("exit_stderr") or "") + "\n")
                sys.stderr.flush()
                os._exit(int(cfg["exit_on_init"]))
            # Строгая схема как у реального droid: tags — список объектов, строки отвергаются.
            tags = params.get("tags")
            if tags is not None:
                if not isinstance(tags, list):
                    self.respond(rid, error={"code": -32602, "message":
                        "Invalid request for droid.initialize_session: params.tags: Expected array"})
                    return
                for i, tag in enumerate(tags):
                    if not isinstance(tag, dict):
                        got = "string" if isinstance(tag, str) else type(tag).__name__
                        self.respond(rid, error={"code": -32602, "message":
                            f"Invalid request for droid.initialize_session: params.tags.{i}: "
                            f"Expected object, received {got}"})
                        return
            time.sleep(float(cfg.get("init_delay") or 0))
            if cfg.get("bad_init"):
                self.respond(rid, {"settings": {}})
                return
            self.sid = "sid-" + uuid.uuid4().hex[:12]
            self.settings = {
                "modelId": params.get("modelId"), "reasoningEffort": params.get("reasoningEffort"),
                "autonomyLevel": params.get("autonomyLevel"), "disabledToolIds": [],
                "systemPrompt": params.get("systemPrompt"), "cwd": params.get("cwd"),
            }
            self.messages = [self._service_message("<system-reminder>\nAvailable subagents: none\n</system-reminder>")]
            self.save()
            self.notify("settings_updated", with_sid=False, settings=self.public_settings())
            self.respond(rid, {"sessionId": self.sid, "settings": self.public_settings(),
                               "session": {"messages": list(self.messages)}})
        elif method == "droid.load_session":
            sid = params.get("sessionId")
            try:
                with open(self._session_path(str(sid)), encoding="utf-8") as handle:
                    saved = json.load(handle)
            except (OSError, ValueError):
                self.respond(rid, error={"code": -32603, "message": "Session not found"})
                return
            self.sid = str(sid)
            self.messages = saved["messages"]
            self.settings = saved["settings"]
            if cfg.get("load_scaffolding"):
                self.messages.append(self._service_message("Unified tool catalog\n- Read\n- Execute"))
            if cfg.get("load_advances"):
                self.messages.append({"id": "extra", "role": "assistant",
                                      "content": [{"type": "text", "text": "ahead of bridge"}]})
            self.save()
            self.respond(rid, {"session": {"messages": list(self.messages)},
                               "settings": self.public_settings(), "isAgentLoopInProgress": False,
                               "workingState": "idle"})
        elif method == "droid.list_tools":
            if cfg.get("list_tools_error"):
                self.respond(rid, error={"code": -32603, "message": "list_tools failed"})
                return
            if cfg.get("raw_tools") is not None:
                self.respond(rid, {"tools": cfg["raw_tools"]})
                return
            tools = cfg.get("tools") if cfg.get("tools") is not None else DEFAULT_TOOLS
            self.respond(rid, {"tools": [{"id": t} for t in tools]})
        elif method == "droid.update_session_settings":
            for src, dst in (("modelId", "modelId"), ("reasoningEffort", "reasoningEffort"),
                             ("autonomyLevel", "autonomyLevel")):
                if src in params:
                    self.settings[dst] = params[src]
            if "disabledToolIds" in params:
                self.settings["disabledToolIds"] = list(params["disabledToolIds"])
            self.save()
            self.respond(rid, {})
            if not cfg.get("no_readback"):
                self.notify("settings_updated", with_sid=False, settings=self.public_settings())
        elif method == "droid.add_user_message":
            self.add_message(rid, params, cfg)
        elif method == "droid.interrupt_session":
            self.respond(rid, {})
        elif method == "droid.close_session":
            self.respond(rid, {})
            self.log({"ev": "exit", "reason": "close_session"})
            time.sleep(float(cfg.get("close_delay") or 0))
            sys.exit(0)
        else:
            self.respond(rid, error={"code": -32601, "message": f"Unknown method: {method}"})

    def add_message(self, rid, params: dict, cfg: dict) -> None:
        if not self.sid:
            self.respond(rid, {})
            self.respond(rid, error={"code": -32603, "message": "No active session."})
            return
        if cfg.get("ack_error") and not params.get("skipAgentLoop"):
            self.respond(rid, error={"code": -32603, "message": "add rejected"})
            return
        if not cfg.get("no_ack"):
            self.respond(rid, {})
        role = params.get("role") or "user"
        self.seq += 1
        message = {"id": f"u{self.seq}", "role": role, "content": [{"type": "text", "text": params.get("text", "")}]}
        self.messages.append(message)
        self.save()
        skip = bool(params.get("skipAgentLoop"))
        if not skip:
            self.notify("droid_working_state_changed", newState="streaming_assistant_message")
        self.notify("create_message", message=message, requestId=rid, messageId=message["id"])
        if cfg.get("dup_ack") and not skip:
            self.respond(rid, {})
        if not skip:
            self.run_turn()

    # -- ход ---------------------------------------------------------------------
    def interrupted(self) -> bool:
        """Неблокирующая обработка входящих во время хода: interrupt/close/прочее."""
        while True:
            try:
                req = self.inq.get_nowait()
            except queue.Empty:
                return False
            if req is None:
                self.eof = True
                continue
            if req.get("method") == "droid.interrupt_session":
                self.log({"ev": "rpc", "method": "droid.interrupt_session", "params": {}, "id": req.get("id")})
                self.respond(req.get("id"), {})
                if not self.config().get("ignore_interrupt"):
                    return True
            elif req.get("method") == "droid.close_session":
                self.respond(req.get("id"), {})
                os._exit(0)
            else:
                self.handle(req)

    def pause(self, seconds: float) -> bool:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.interrupted():
                return True
            time.sleep(0.02)
        return False

    def run_turn(self) -> None:
        scenario = self.claim_scenario()
        if isinstance(scenario, list):
            scenario = {"steps": scenario}
        scenario = scenario or {"steps": [{"op": "text", "text": "PONG"}]}
        steps = scenario.get("steps") or []
        reason = scenario.get("reason", "completed")
        usage = scenario.get("usage") or {"inputTokens": 10, "outputTokens": 5}
        turn_id = "turn-" + uuid.uuid4().hex[:8]
        started = time.monotonic()
        last_mid = ""
        pending_thinking = ""
        cancelled = False
        self.notify("droid_working_state_changed", newState="thinking")
        for step in steps:
            if self.interrupted():
                cancelled = True
                break
            op = step.get("op")
            if op == "text":
                self.seq += 1
                mid = f"m{self.seq}"
                text = step.get("text", "")
                blocks = []
                if pending_thinking:
                    blocks.append({"type": "thinking", "thinking": pending_thinking})
                    pending_thinking = ""
                half = max(1, len(text) // 2)
                for chunk in (text[:half], text[half:]):
                    self.notify("assistant_text_delta", messageId=mid, blockIndex=0, textDelta=chunk)
                if step.get("complete_with_text"):
                    self.notify("assistant_text_complete", messageId=mid, text=text)
                else:
                    self.notify("assistant_text_complete", messageId=mid)
                blocks.append({"type": "text", "text": text})
                msg = {"id": mid, "role": "assistant", "content": blocks}
                self.messages.append(msg)
                self.notify("create_message", message=msg, messageId=mid)
                last_mid = mid
                if step.get("pause"):
                    if self.pause(float(step["pause"])):
                        cancelled = True
                        break
            elif op == "thinking":
                self.seq += 1
                mid = f"t{self.seq}"
                text = step.get("text", "")
                pending_thinking = text
                self.notify("thinking_text_delta", messageId=mid, textDelta=text)
                self.notify("thinking_text_complete", messageId=mid, text=text, durationMs=5)
                if step.get("alone"):
                    msg = {"id": mid, "role": "assistant", "content": [{"type": "thinking", "thinking": text}]}
                    self.notify("create_message", message=msg, messageId=mid)
                    last_mid = mid
                    pending_thinking = ""
            elif op == "retry":
                self.notify("llm_retry", attempt=1, reason="timeout")
            elif op == "retract":
                self.notify("assistant_message_retracted", messageId=last_mid)
                self.messages = [m for m in self.messages if m.get("id") != last_mid]
            elif op == "error":
                self.notify("error", message=step.get("message", "boom"), errorType="Test")
            elif op == "sleep":
                if self.pause(float(step.get("s", 0.1))):
                    cancelled = True
                    break
            elif op == "hang":
                while not self.interrupted():
                    time.sleep(0.05)
                cancelled = True
                break
            elif op == "exit":
                if step.get("stderr"):
                    sys.stderr.write(step["stderr"] + "\n")
                    sys.stderr.flush()
                self.log({"ev": "exit", "reason": "scenario", "rc": step.get("rc", 1)})
                os._exit(int(step.get("rc", 1)))
            elif op == "notify":
                self.notify(step["type"], **(step.get("fields") or {}))
            elif op == "garbage":
                self.raw("{this is not json")
            elif op == "stale_terminal":
                # Запоздавший terminal ПРЕЖНЕГО хода (его turnId), пришедший после arming текущего.
                self.notify("agent_turn_completed", reason="completed", turnId=self.prev_turn_id,
                            tokenUsage={"inputTokens": 777, "outputTokens": 777})
            elif op == "big_line":
                self.raw("{" + '"pad":"' + "A" * int(step.get("bytes", 1000)) + '"}')
            elif op == "flood":
                chunk = "F" * int(step.get("size", 1000))
                for _ in range(int(step.get("count", 10))):
                    self.notify("assistant_text_delta", messageId="flood", blockIndex=0, textDelta=chunk)
            elif op == "foreign_terminal":
                self.notify("agent_turn_completed", sid="sid-foreign", reason="completed", turnId="x",
                            tokenUsage={"inputTokens": 999, "outputTokens": 999})
        self.save()
        if cancelled:
            reason = "cancelled"
        self.cumulative["inputTokens"] += usage.get("inputTokens", 0)
        self.cumulative["outputTokens"] += usage.get("outputTokens", 0)
        self.notify("session_token_usage_changed", tokenUsage=dict(self.cumulative),
                    lastCallTokenUsage={"inputTokens": 1, "outputTokens": 1})
        self.notify("agent_turn_completed", reason=reason, turnId=turn_id,
                    tokenUsage=dict(usage), cumulativeTokenUsage=dict(self.cumulative),
                    durationMs=int((time.monotonic() - started) * 1000))
        self.notify("droid_working_state_changed", newState="idle")
        self.prev_turn_id = turn_id
        if scenario.get("late"):
            # Запоздавшие события прежнего хода: не должны засчитываться следующему.
            self.pause(float(scenario["late"]))
            self.notify("assistant_text_delta", messageId="late1", blockIndex=0, textDelta="LATE")
            self.notify("agent_turn_completed", reason="completed", turnId=turn_id,
                        tokenUsage={"inputTokens": 777, "outputTokens": 777})

    # -- основной цикл -------------------------------------------------------------
    def _read_stdin(self) -> None:
        stall_after = self.config().get("stall_after")
        count = 0
        while True:
            if stall_after is not None and count >= int(stall_after):
                # Ребёнок «завис»: stdin больше не читается, pipe заполняется записью моста.
                while True:
                    time.sleep(3600)
            raw = sys.stdin.buffer.readline()
            if not raw:
                break
            count += 1
            try:
                req = json.loads(raw.decode("utf-8"))
            except ValueError:
                self.log({"ev": "bad_input", "line": raw.decode("utf-8", "replace")[:200]})
                continue
            self.inq.put(req)
        self.inq.put(None)

    def run(self) -> None:
        threading.Thread(target=self._read_stdin, daemon=True).start()
        while True:
            req = self.inq.get()
            if req is None:
                self.log({"ev": "exit", "reason": "stdin_eof"})
                return
            self.handle(req)
            if self.eof:
                self.log({"ev": "exit", "reason": "stdin_eof_after_turn"})
                return


def main(argv: list) -> None:
    Fake(os.environ["FAKE_DROID_DIR"], argv).run()


if __name__ == "__main__":
    main(sys.argv[1:])
