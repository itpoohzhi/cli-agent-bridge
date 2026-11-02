"""Тесты claude-p-bridge (ADR 0014, AD-001..AD-005) и универсального слоя core.

Покрытие: SSOT в репозитории и fail-closed импорт core (AD-002), изображения
через workspace-read с правами 0700/0600 и cleanup в finally (AD-003),
ALWAYS-ON санитизация ToolCallParser(strict_live=True) без утечки сырого XML и
без result-fallback (AD-004), real-time reasoning в SSE
(choices[0].delta.reasoning_content) и в JSON (message.reasoning_content)
(AD-005), флаги --tools "Read"/--add-dir при вложениях (REQ-03).
"""

import base64
import http.client
import importlib.util
import json
import os
import queue
import stat
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import core.tool_emulation as core_te  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BRIDGE_DIR = REPO / "bridges" / "claude-p-bridge"
BRIDGE_SERVER = BRIDGE_DIR / "server.py"

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF_BYTES = b"GIF89a" + b"\x00" * 16

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["city"],
            },
        },
    }
]


def _data_url(mime: str, data: bytes) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _image_part(mime: str = "image/png", data: bytes = PNG_BYTES) -> dict:
    return {"type": "image_url", "image_url": {"url": _data_url(mime, data)}}


def _load_bridge():
    spec = importlib.util.spec_from_file_location(
        "claude_p_bridge_server", BRIDGE_SERVER
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def bridge(monkeypatch):
    mod = _load_bridge()
    monkeypatch.setattr(mod, "AUTH_KEY", "test-key")
    return mod


class FakeRun:
    """Фейковый ход `claude -p`: скриптованные события очереди, без CLI."""

    script: list = []
    captured: dict = {}

    def __init__(self, prompt, model, effort, tag, img_dir=None):
        type(self).captured = {
            "prompt": prompt,
            "model": model,
            "effort": effort,
            "img_dir": None if img_dir is None else str(img_dir),
            "closed": False,
        }
        if img_dir is not None:
            root = Path(img_dir)
            files = {}
            for path in sorted(root.iterdir()):
                files[path.name] = {
                    "mode": stat.S_IMODE(path.stat().st_mode),
                    "data": path.read_bytes(),
                }
            type(self).captured["img_dir_mode"] = stat.S_IMODE(root.stat().st_mode)
            type(self).captured["img_files"] = files
        self.q = queue.Queue()
        for item in type(self).script:
            self.q.put(item)
        self.err_box = []

    def close(self):
        type(self).captured["closed"] = True


@pytest.fixture()
def http_bridge(bridge, monkeypatch):
    FakeRun.script = []
    FakeRun.captured = {}
    monkeypatch.setattr(bridge, "Run", FakeRun)
    server = bridge.Server(("127.0.0.1", 0), bridge.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield bridge, server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def _post(port: int, payload: dict):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
    try:
        conn.request(
            "POST",
            "/v1/chat/completions",
            body=json.dumps(payload),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-key",
            },
        )
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", "replace")
        return resp.status, body
    finally:
        conn.close()


def _sse_payloads(body: str) -> list:
    out = []
    for line in body.splitlines():
        if line.startswith("data: ") and line[6:] != "[DONE]":
            out.append(json.loads(line[6:]))
    return out


def _sse_delta_text(body: str, field: str) -> str:
    parts = []
    for payload in _sse_payloads(body):
        for choice in payload.get("choices") or []:
            value = (choice.get("delta") or {}).get(field)
            if value:
                parts.append(value)
    return "".join(parts)


def _done_script(*events, rc=0):
    return [
        *events,
        ("result", {"usage": {"input_tokens": 3, "output_tokens": 2}}),
        ("done", rc),
    ]


# ---- AD-002: SSOT в репозитории -------------------------------------------------


def test_config_bridge_ssot_in_repo():
    assert BRIDGE_SERVER.is_file()
    assert json.loads((BRIDGE_DIR / "empty-mcp.json").read_text()) == {"mcpServers": {}}
    src = BRIDGE_SERVER.read_text()
    # Канонический парсер берётся из core; локальной копии в мосте нет.
    assert "from core.tool_emulation import" in src
    assert "class ToolCallParser" not in src
    assert "strict_live=True" in src


def test_config_bridge_import_fails_without_core(tmp_path):
    """Fail-closed: без доступного core мост не импортируется молча с fallback-парсером."""
    isolated = tmp_path / "server.py"
    isolated.write_text(BRIDGE_SERVER.read_text())
    spec = importlib.util.spec_from_file_location("claude_p_bridge_isolated", isolated)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    saved = sys.path[:]
    sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != REPO]
    saved_core = {
        k: sys.modules.pop(k)
        for k in list(sys.modules)
        if k == "core" or k.startswith("core.")
    }
    try:
        with pytest.raises((SystemExit, ImportError)):
            spec.loader.exec_module(mod)
    finally:
        sys.path[:] = saved
        for k in [k for k in list(sys.modules) if k == "core" or k.startswith("core.")]:
            del sys.modules[k]
        sys.modules.update(saved_core)


# ---- AD-005: универсальный live reasoning в core ---------------------------------


def test_reasoning_tagged_stream_split_across_deltas():
    contents, reasonings, calls = [], [], []
    norm = core_te.StreamNormalizer(contents.append, reasonings.append, calls.append)
    for chunk in (
        "<thi",
        "nk>plan A</thi",
        "nk>Итог",
        " <thinking>B</thinking>!",
        "<thought>C</thought>",
    ):
        norm.feed_text(chunk)
    norm.finish()
    assert "".join(reasonings) == "plan ABC"
    assert norm.reasoning_content == "plan ABC"
    assert "".join(contents) == "Итог !"
    assert norm.content == "Итог !"
    assert calls == []


def test_reasoning_native_thinking_delta_helper_and_feed():
    assert (
        core_te.extract_thinking_delta({"type": "thinking_delta", "thinking": "abc"})
        == "abc"
    )
    assert core_te.extract_thinking_delta({"type": "text_delta", "text": "abc"}) == ""
    assert core_te.extract_thinking_delta({}) == ""
    norm = core_te.StreamNormalizer()
    norm.feed_thinking("нативная ")
    norm.feed_event_delta({"type": "thinking_delta", "thinking": "мысль"})
    norm.feed_event_delta({"type": "text_delta", "text": "ответ"})
    norm.finish()
    assert norm.reasoning_content == "нативная мысль"
    assert norm.content == "ответ"


def test_reasoning_tool_call_inside_think_is_not_a_call():
    norm = core_te.StreamNormalizer()
    norm.feed_text(
        '<think>пример <tool_call>{"name": "f", "arguments": {}}</tool_call></think>hi'
    )
    norm.finish()
    assert norm.tool_calls == []
    assert "<tool_call>" in norm.reasoning_content
    assert norm.content == "hi"


def test_reasoning_think_tag_inside_tool_json_does_not_switch():
    norm = core_te.StreamNormalizer()
    norm.feed_text(
        '<tool_call>{"name": "f", "arguments": {"q": "<think>x</think>"}}</tool_call>'
    )
    norm.finish()
    assert norm.reasoning_content == ""
    assert norm.tool_calls == [{"name": "f", "arguments": {"q": "<think>x</think>"}}]
    assert norm.content == ""


def test_reasoning_markdown_fence_preserves_literal_tags():
    norm = core_te.StreamNormalizer()
    norm.feed_text("```\n<tool_call>example</tool_call>\n```")
    norm.finish()
    assert norm.tool_calls == []
    assert "<tool_call>example</tool_call>" in norm.content


def test_reasoning_unclosed_tag_fails_closed():
    norm = core_te.StreamNormalizer()
    norm.feed_text("<think>незавершено")
    with pytest.raises(core_te.LiveParserError):
        norm.finish()
    assert "незавершено" not in norm.content


# ---- AD-004: строгая санитизация на уровне core ----------------------------------


def test_strict_malformed_tool_call_raises_not_leaks():
    norm = core_te.StreamNormalizer()
    with pytest.raises(core_te.LiveParserError):
        norm.feed_text('ok <tool_call>{"name": broken</tool_call>')
        norm.finish()
    assert "<tool_call>" not in norm.content


def test_strict_unclosed_tool_call_at_eof_raises():
    norm = core_te.StreamNormalizer()
    norm.feed_text('<tool_call>{"name": "f", "arguments": {}}')
    with pytest.raises(core_te.LiveParserError):
        norm.finish()
    assert "<tool_call>" not in norm.content


# ---- AD-003: извлечение картинок в core ------------------------------------------


def test_image_extract_order_names_and_jpeg():
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "смотри"}, _image_part()],
        },
        {"role": "assistant", "content": "ок"},
        {"role": "user", "content": [_image_part("image/jpeg", JPEG_BYTES)]},
    ]
    images = core_te.extract_data_url_images(messages)
    assert [im["name"] for im in images] == ["image_1.png", "image_2.jpg"]
    assert images[0]["data"] == PNG_BYTES and images[0]["mime"] == "image/png"
    assert images[1]["data"] == JPEG_BYTES and images[1]["mime"] == "image/jpeg"


def test_image_extract_rejects_url_bad_base64_and_mismatch():
    with pytest.raises(core_te.ImageInputError):
        core_te.extract_data_url_images(
            [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": "https://x/y.png"}}
                    ],
                }
            ]
        )
    with pytest.raises(core_te.ImageInputError):
        core_te.extract_data_url_images(
            [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "data:image/png;base64,!!!"},
                        }
                    ],
                }
            ]
        )
    with pytest.raises(core_te.ImageInputError):
        core_te.extract_data_url_images(
            [{"role": "user", "content": [_image_part("image/png", GIF_BYTES)]}]
        )
    with pytest.raises(core_te.ImageInputError):
        core_te.extract_data_url_images(
            [{"role": "user", "content": [_image_part(), _image_part()]}], max_images=1
        )


def test_image_only_prompt_keeps_marker_not_pong():
    messages = [{"role": "user", "content": [_image_part()]}]
    images = core_te.extract_data_url_images(messages)
    prompt = core_te._messages_to_prompt(messages, images=images)
    assert "[image 1]" in prompt
    assert "[attachments]" in prompt
    assert "PONG" not in prompt


# ---- AD-003/REQ-03: argv и workspace-read -----------------------------------------


def test_workspace_cmd_read_and_add_dir_only_with_images(bridge):
    cmd = bridge._build_claude_cmd(
        "claude-sonnet-5-5", "high", Path("/tmp/claude-img-x")
    )
    assert cmd[cmd.index("--tools") + 1] == "Read"
    assert cmd[cmd.index("--add-dir") + 1] == "/tmp/claude-img-x"
    plain = bridge._build_claude_cmd("claude-sonnet-5-5", "high", None)
    assert plain[plain.index("--tools") + 1] == ""
    assert "--add-dir" not in plain


def test_workspace_image_staging_permissions_and_cleanup(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(("text", "вижу картинку"))
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": "что тут?"}, _image_part()],
                }
            ],
        },
    )
    assert status == 200, body
    captured = FakeRun.captured
    img_dir = captured["img_dir"]
    assert img_dir and Path(img_dir).name.startswith("claude-img-")
    assert captured["img_dir_mode"] == 0o700
    assert captured["img_files"]["image_1.png"]["mode"] == 0o600
    assert captured["img_files"]["image_1.png"]["data"] == PNG_BYTES
    assert "[attachments]" in captured["prompt"] and "[image 1]" in captured["prompt"]
    # finally: каталог удалён после завершения хода, ребёнок закрыт раньше ответа.
    assert captured["closed"] is True
    assert not Path(img_dir).exists()


def test_cleanup_image_dir_removed_on_parser_error(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(("text", '<tool_call>{"name": broken</tool_call>'))
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": [_image_part()]}],
        },
    )
    assert status == 502, body
    assert "<tool_call>" not in body
    assert (
        FakeRun.captured["img_dir"] and not Path(FakeRun.captured["img_dir"]).exists()
    )


def test_image_rejected_before_spawn(http_bridge):
    _bridge, port = http_bridge
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": "file:///etc/passwd"},
                        }
                    ],
                }
            ],
        },
    )
    assert status == 400, body
    assert FakeRun.captured == {}


# ---- AD-005: reasoning в HTTP (SSE и JSON) ----------------------------------------


def test_reasoning_sse_deltas_before_content(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(
        ("thinking", "думаю "), ("thinking", "глубоко"), ("text", "Ответ")
    )
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200, body
    assert _sse_delta_text(body, "reasoning_content") == "думаю глубоко"
    assert _sse_delta_text(body, "content") == "Ответ"
    assert body.index("reasoning_content") < body.index("Ответ")


def test_reasoning_json_message_reasoning_content(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(
        ("thinking", "план"), ("text", "<think>ещё</think>Итог")
    )
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200, body
    message = json.loads(body)["choices"][0]["message"]
    assert message["reasoning_content"] == "планещё"
    assert message["content"] == "Итог"
    assert "<think>" not in message["content"]


def test_reasoning_sse_equals_json_for_same_transcript(http_bridge):
    _bridge, port = http_bridge
    script = _done_script(("thinking", "R1"), ("text", "<thinking>R2</thinking>Текст"))
    FakeRun.script = list(script)
    _, sse_body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    FakeRun.script = list(script)
    _, json_body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert _sse_delta_text(sse_body, "reasoning_content") == "R1R2"
    assert json.loads(json_body)["choices"][0]["message"]["reasoning_content"] == "R1R2"


# ---- AD-004: HTTP fail-closed ------------------------------------------------------


def test_strict_junk_sse_error_chunk_no_xml_leak(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(("text", 'ok <tool_call>{"name": broken</tool_call>'))
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200, body  # SSE-заголовки уже ушли; ошибка — data-кадром
    assert "<tool_call>" not in body
    errors = [p["error"] for p in _sse_payloads(body) if "error" in p]
    assert errors and errors[0]["type"] == "stream_error"
    finishes = [
        c.get("finish_reason")
        for p in _sse_payloads(body)
        for c in p.get("choices") or []
    ]
    assert finishes[-1] == "stop" and "tool_calls" not in finishes


def test_error_stream_has_finish_reason_stop_and_done(http_bridge: tuple[object, int]) -> None:
    _bridge, port = http_bridge
    FakeRun.script = [("done", -15)]
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200, body
    terminal = _sse_payloads(body)[-1]
    assert terminal["error"]["message"]
    assert terminal["choices"][0]["finish_reason"] == "stop"
    assert body.endswith("data: [DONE]\n\n")
    assert body.count("data: [DONE]\n\n") == 1


def test_strict_sigterm_cut_tool_call_no_xml_leak(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = [
        ("text", '<tool_call>{"name": "get_weather", "arguments": {"city": "Oslo"}}'),
        ("done", -15),
    ]
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": True,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200, body
    assert "<tool_call>" not in body
    errors = [p["error"] for p in _sse_payloads(body) if "error" in p]
    assert errors and errors[0]["type"] == "stream_error"


def test_strict_no_result_fallback_junk(http_bridge):
    """Терминальный result не подставляется в ответ (AD-004/бриф п.4)."""
    _bridge, port = http_bridge
    FakeRun.script = [
        (
            "result",
            {
                "result": '<tool_call>{"name": "x", "arguments": {}}</tool_call>',
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        ),
        ("done", 0),
    ]
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 502, body
    assert "<tool_call>" not in body


def test_sanitize_tool_call_once_and_published(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(
        (
            "text",
            '<tool_call>{"name": "get_weather", "arguments": {"city": "Oslo", "note": ""}}</tool_call>',
        )
    )
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "tools": TOOLS,
            "messages": [{"role": "user", "content": "погода?"}],
        },
    )
    assert status == 200, body
    payload = json.loads(body)
    calls = payload["choices"][0]["message"]["tool_calls"]
    assert len(calls) == 1
    assert json.loads(calls[0]["function"]["arguments"]) == {"city": "Oslo"}
    assert payload["choices"][0]["finish_reason"] == "tool_calls"


def test_tool_choice_none_real_call_is_protocol_error(http_bridge):
    _bridge, port = http_bridge
    FakeRun.script = _done_script(
        (
            "text",
            '<tool_call>{"name": "get_weather", "arguments": {"city": "Oslo"}}</tool_call>',
        )
    )
    status, body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "tools": TOOLS,
            "tool_choice": "none",
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 502, body
    assert "<tool_call>" not in body
    assert "get_weather" not in json.loads(body).get("choices", [{}])[0].get(
        "message", {}
    ).get("content", "")


def test_no_tmp_leak_after_success(http_bridge):
    """После успешного хода без картинок сессионных каталогов не создаётся."""
    _bridge, port = http_bridge
    FakeRun.script = _done_script(("text", "просто текст"))
    status, _body = _post(
        port,
        {
            "model": "claude-sonnet-5-5",
            "stream": False,
            "messages": [{"role": "user", "content": "hi"}],
        },
    )
    assert status == 200
    assert FakeRun.captured["img_dir"] is None
    assert (
        os.environ.get("CLAUDE_P_BRIDGE_KEY", "") != "test-key"
    )  # env тестов не трогаем

