"""Контракт DSH subagent на матрице из брифа владельца.

Upstream в памяти моделирует ответы моделей; запросы и ответы проходят настоящий
PassthroughAdapter. Это воспроизводимая проверка протокола, а не живой запуск DSH
или доказательство доступности моделей. Оракул ниже повторяет только границу
hasDelegationModelRequest/assertNonEmpty и требование парности provider/model из
@deepseek-ai/dsh-tool-subagent/lib/index.js (снимок исследования от 2026-10-30).
Вендорский код не загружается и не изменяется, внешние сервисы не требуются.
"""

from __future__ import annotations

import http.client
import io
import json
import unittest
from typing import Any
from unittest.mock import patch

from adapters.passthrough_adapter import PassthroughAdapter, ResponseSink
from core.backend_adapter import ToolCall, ToolFunction
from core.tool_emulation import build_tool_schemas, sanitize_tool_call


MODELS = (
    "gpt-6.1-terra",
    "gpt-6.1-sol",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
    "claude-opus-5-5",
    "gemini-3.8-flash",
    "gemini-4-argon",
    "muse-wonder-1.0",
    "muse-wonder-full-1.0",
    "deepseek-v4.1-flash",
)
SKEPTICS = ("gemini-3.8-flash", "deepseek-v4.1-flash", "gpt-6.1-terra")
ROUTE_FIELDS = ("provider", "model", "reasoning_effort")
OPTIONAL_FIELDS = (*ROUTE_FIELDS, "justification")
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "subagent",
            "parameters": {
                "type": "object",
                "properties": {
                    name: {"type": "string"}
                    for name in ("description", "prompt", "cwd", *OPTIONAL_FIELDS)
                },
                "required": ["description", "prompt"],
            },
        },
    }
]
# justification — опциональное расширение схемы для проверки общего санитайзера.
SCHEMAS = build_tool_schemas(TOOLS)
DONE = b"data: [DONE]\n\n"


def has_delegation_model_request(arguments: dict[str, Any]) -> bool:
    """Наличие поля эквивалентно JS-проверке request.field !== undefined."""
    return any(field in arguments for field in ROUTE_FIELDS)


def validate_dsh_request(arguments: dict[str, Any]) -> None:
    """Независимый оракул входной границы DSH, без нормализации внутри оракула."""
    for field in ("description", "prompt"):
        if not isinstance(arguments.get(field), str) or not arguments[field]:
            raise ValueError(f"subagent `{field}` must be non-empty")
    if not has_delegation_model_request(arguments):
        return
    for field in ROUTE_FIELDS:
        if field in arguments:
            if not isinstance(arguments[field], str):
                raise ValueError(f"child LLM `{field}` must be a string")
            if len(arguments[field]) == 0:
                raise ValueError(f"child LLM `{field}` must be non-empty")
    if ("provider" in arguments) != ("model" in arguments):
        raise ValueError("child LLM `provider` and `model` must be supplied together")


def delegation(child_model: str, **overrides: Any) -> dict[str, Any]:
    return {
        "description": "Проверка делегирования модели",
        "prompt": f"Проверь аргументы сабагента {child_model}",
        **overrides,
    }


def tool_call(
    arguments: dict[str, Any], name: str = "subagent", call_id: str = "call_src"
) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(arguments, ensure_ascii=False),
        },
    }


def completion(model: str, calls: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-discovery",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {"role": "assistant", "content": None, "tool_calls": calls},
            }
        ],
    }


def sse_frame(model: str, delta: dict[str, Any], reason: str | None = None) -> bytes:
    payload = {
        "id": "chatcmpl-discovery",
        "object": "chat.completion.chunk",
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": reason}],
    }
    return b"data: " + json.dumps(payload, ensure_ascii=False).encode() + b"\n\n"


class CollectSink(ResponseSink):
    def __init__(self) -> None:
        self.status: int | None = None
        self.headers: list[tuple[str, str]] = []
        self.chunks: list[bytes] = []

    def start(self, status: int, headers: list[tuple[str, str]]) -> None:
        self.status = status
        self.headers = headers

    def write(self, data: bytes) -> None:
        self.chunks.append(data)


class TestDshSubagentDiscovery(unittest.TestCase):
    """Матрица детерминированных ответов всех десяти моделей через HTTP-шов моста."""

    def setUp(self) -> None:
        self.response_body = b""
        self.response_stream = False
        self.requests: list[tuple[str, bytes]] = []
        owner = self

        class MemorySocket:
            def makefile(self, mode: str) -> io.BytesIO:
                content_type = (
                    "text/event-stream" if owner.response_stream else "application/json"
                )
                header = (
                    f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\n"
                    f"Content-Length: {len(owner.response_body)}\r\n\r\n"
                ).encode()
                return io.BytesIO(header + owner.response_body)

        class MemoryConnection:
            sock = None

            def __init__(self, host: str, port: int, timeout: float) -> None:
                self.closed = False
                self.response: http.client.HTTPResponse | None = None

            def connect(self) -> None:
                return

            def request(
                self, method: str, path: str, body: bytes, headers: dict[str, str]
            ) -> None:
                owner.assertEqual(method, "POST")
                owner.assertEqual(headers["Content-Length"], str(len(body)))
                owner.requests.append((path, body))

            def getresponse(self) -> http.client.HTTPResponse:
                self.response = http.client.HTTPResponse(MemorySocket())
                self.response.begin()
                return self.response

            def close(self) -> None:
                self.closed = True
                if self.response is not None:
                    self.response.close()

        # Подменяется только создание TCP-соединения. HTTPResponse, _open,
        # handle, нормализация JSON и relay SSE остаются настоящими.
        self.enterContext(
            patch(
                "adapters.passthrough_adapter.http.client.HTTPConnection",
                MemoryConnection,
            )
        )
        self.adapter = PassthroughAdapter(
            "codex",
            {"base_url": "http://127.0.0.1:2455/v1"},
            lambda: {},
            sanitize=True,
        )

    def exchange(
        self,
        model: str,
        response: dict[str, Any] | bytes,
        messages: list[dict[str, Any]] | None = None,
    ) -> CollectSink:
        self.response_stream = isinstance(response, bytes)
        self.response_body = (
            response if isinstance(response, bytes) else json.dumps(response).encode()
        )
        request = {
            "model": model,
            "stream": self.response_stream,
            "tools": TOOLS,
            "messages": messages
            if messages is not None
            else [{"role": "user", "content": "Делегируй проверку"}],
        }
        raw = json.dumps(request, ensure_ascii=False).encode()
        sink = CollectSink()
        self.adapter.handle(
            path="/v1/chat/completions",
            raw_body=raw,
            request=request,
            headers={},
            sink=sink,
        )
        self.assertEqual(sink.status, 200, b"".join(sink.chunks))
        self.assertEqual(self.requests[-1], ("/v1/chat/completions", raw))
        self.assertEqual(self.adapter.active_count(), 0)
        self.assertEqual(self.adapter.process_budget.used, 0)
        return sink

    def normalized_calls(
        self, model: str, calls: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        sink = self.exchange(model, completion(model, calls))
        body = json.loads(b"".join(sink.chunks))
        self.assertEqual(body["model"], model)
        self.assertEqual(body["choices"][0]["finish_reason"], "tool_calls")
        result = body["choices"][0]["message"]["tool_calls"]
        for call in result:
            self.assertEqual(call["function"]["name"], "subagent")
            validate_dsh_request(json.loads(call["function"]["arguments"]))
        return result

    def test_dsh_oracle_rejects_original_empty_route_and_partial_selection(
        self,
    ) -> None:
        """AC-3: отрицательный контроль ловит исходную ошибку до санитизации."""
        for field in ROUTE_FIELDS:
            with self.subTest(field=field):
                arguments = delegation("gpt-6.1-terra", **{field: ""})
                self.assertTrue(has_delegation_model_request(arguments))
                with self.assertRaisesRegex(
                    ValueError, f"child LLM `{field}` must be non-empty"
                ):
                    validate_dsh_request(arguments)
        with self.assertRaisesRegex(ValueError, "must be supplied together"):
            validate_dsh_request(delegation("gpt-6.1-terra", provider="codex"))

    def test_all_models_remove_blank_optional_strings_without_fallback(self) -> None:
        """AC-1/3: пустые параметры исчезают; маршрут остаётся не заданным."""
        for model in MODELS:
            for blank in ("", " \t\n"):
                with self.subTest(model=model, blank=repr(blank)):
                    expected = delegation(model)
                    arguments = {**expected, **dict.fromkeys(OPTIONAL_FIELDS, blank)}
                    calls = self.normalized_calls(model, [tool_call(arguments)])
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(calls[0]["id"], "call_src")
                    actual = json.loads(calls[0]["function"]["arguments"])
                    self.assertEqual(actual, expected)
                    self.assertFalse(has_delegation_model_request(actual))
                    self.assertEqual(arguments["provider"], blank)

    def test_all_models_preserve_explicit_route_and_nonempty_optional_values(
        self,
    ) -> None:
        """AC-2/3: provider=codex и каждый exact model ID сохраняются дословно."""
        for model in MODELS:
            with self.subTest(model=model):
                arguments = delegation(
                    model,
                    provider="codex",
                    model=model,
                    reasoning_effort="high",
                    justification="Проверка контракта",
                    cwd="/tmp",
                )
                source = tool_call(arguments)
                calls = self.normalized_calls(model, [source])
                self.assertEqual(calls, [source])
                self.assertTrue(
                    has_delegation_model_request(
                        json.loads(calls[0]["function"]["arguments"])
                    )
                )

    def test_valid_route_survives_blank_effort_and_justification(self) -> None:
        """AC-1/2: удаление пустого effort не меняет явно заданную пару маршрута."""
        for model in MODELS:
            with self.subTest(model=model):
                arguments = delegation(model, provider="codex", model=model)
                source = {**arguments, "reasoning_effort": "", "justification": ""}
                calls = self.normalized_calls(model, [tool_call(source)])
                self.assertEqual(
                    json.loads(calls[0]["function"]["arguments"]), arguments
                )

    def test_core_toolcall_objects_obey_the_same_dsh_contract(self) -> None:
        """AC-1/3: типизированный путь эмуляции очищается по той же схеме."""
        for model in MODELS:
            with self.subTest(model=model):
                expected = delegation(model)
                raw = json.dumps({**expected, **dict.fromkeys(OPTIONAL_FIELDS, "")})
                source = ToolCall(0, "call_core", ToolFunction("subagent", raw))
                result = sanitize_tool_call(source, SCHEMAS)
                self.assertEqual(len(result), 1)
                self.assertIsInstance(result[0], ToolCall)
                self.assertEqual((result[0].index, result[0].id), (0, "call_core"))
                arguments = json.loads(result[0].function.arguments)
                self.assertEqual(arguments, expected)
                validate_dsh_request(arguments)
                self.assertEqual(source.function.arguments, raw)

    def test_all_models_unpack_parallel_delegations(self) -> None:
        """AC-4: синтетический parallel выдаёт три самостоятельных subagent."""
        for model in MODELS:
            with self.subTest(model=model):
                expected = [
                    delegation(child, provider="codex", model=child)
                    for child in SKEPTICS
                ]
                parallel = {
                    "tool_uses": [
                        {
                            "recipient_name": "functions.subagent",
                            "parameters": {
                                **arguments,
                                "reasoning_effort": "",
                                "justification": "",
                            },
                        }
                        for arguments in expected
                    ]
                }
                calls = self.normalized_calls(model, [tool_call(parallel, "parallel")])
                self.assertEqual(
                    [json.loads(c["function"]["arguments"]) for c in calls], expected
                )
                ids = [c["id"] for c in calls]
                self.assertEqual(len(set(ids)), 3)
                self.assertNotIn("call_src", ids)

    def test_all_models_stream_interleaved_subagent_argument_deltas(self) -> None:
        """AC-5: фрагменты двух вызовов не смешиваются; публикация до finish/DONE."""
        for model in MODELS:
            with self.subTest(model=model):
                expected = [
                    delegation(model),
                    delegation(model, provider="codex", model=model),
                ]
                raw = [
                    json.dumps(
                        {
                            **a,
                            "reasoning_effort": "",
                            "justification": "",
                            **({"provider": "", "model": ""} if i == 0 else {}),
                        },
                        ensure_ascii=False,
                    )
                    for i, a in enumerate(expected)
                ]
                events = b""
                for phase in range(3):
                    for index, arguments in enumerate(raw):
                        cut = len(arguments) // 3
                        fragment = (
                            arguments[phase * cut : (phase + 1) * cut]
                            if phase < 2
                            else arguments[2 * cut :]
                        )
                        call = {"index": index, "function": {"arguments": fragment}}
                        if phase == 0:
                            call.update(id=f"call_{index}", type="function")
                            call["function"]["name"] = "subagent"
                        events += sse_frame(model, {"tool_calls": [call]})
                events += sse_frame(model, {}, "tool_calls") + DONE
                sink = self.exchange(model, events)
                self.assertEqual(sink.chunks[-1], DONE)
                self.assertEqual(sink.chunks.count(DONE), 1)
                frames = [
                    json.loads(line[5:])
                    for line in b"".join(sink.chunks).splitlines()
                    if line.startswith(b"data:") and line[5:].strip() != b"[DONE]"
                ]
                calls = []
                call_positions = []
                finish_positions = []
                for position, frame in enumerate(frames):
                    self.assertNotIn("error", frame)
                    self.assertEqual(frame["model"], model)
                    for choice in frame["choices"]:
                        published = choice["delta"].get("tool_calls", [])
                        if published:
                            call_positions.append(position)
                            calls.extend(published)
                        if choice.get("finish_reason"):
                            self.assertEqual(choice["finish_reason"], "tool_calls")
                            finish_positions.append(position)
                self.assertEqual([c["index"] for c in calls], [0, 1])
                self.assertEqual([c["id"] for c in calls], ["call_0", "call_1"])
                self.assertEqual(
                    [c["function"]["name"] for c in calls], ["subagent", "subagent"]
                )
                self.assertEqual(
                    [json.loads(c["function"]["arguments"]) for c in calls], expected
                )
                for call in calls:
                    validate_dsh_request(json.loads(call["function"]["arguments"]))
                self.assertEqual(len(finish_positions), 1)
                self.assertLess(max(call_positions), finish_positions[0])

    def test_fast_coordinator_two_rounds_of_three_skeptics(self) -> None:
        """AC-6: две волны тройки Скептиков и возврат результатов координатору."""
        for coordinator in SKEPTICS:
            with self.subTest(coordinator=coordinator):
                messages: list[dict[str, Any]] = [
                    {"role": "user", "content": "Проверь делегирование в два раунда"}
                ]
                seen_ids: set[str] = set()
                for round_number in range(2):
                    expected = [
                        delegation(child, provider="codex", model=child)
                        for child in SKEPTICS
                    ]
                    parallel = {
                        "tool_uses": [
                            {
                                "recipient_name": "functions.subagent",
                                "parameters": {**a, "reasoning_effort": ""},
                            }
                            for a in expected
                        ]
                    }
                    sink = self.exchange(
                        coordinator,
                        completion(coordinator, [tool_call(parallel, "parallel")]),
                        messages,
                    )
                    message = json.loads(b"".join(sink.chunks))["choices"][0]["message"]
                    calls = message["tool_calls"]
                    self.assertEqual(len(calls), 3)
                    self.assertEqual(
                        [c["function"]["name"] for c in calls], ["subagent"] * 3
                    )
                    self.assertEqual(
                        [json.loads(c["function"]["arguments"]) for c in calls],
                        expected,
                    )
                    messages.append(message)
                    for call in calls:
                        self.assertNotIn(call["id"], seen_ids)
                        seen_ids.add(call["id"])
                        validate_dsh_request(json.loads(call["function"]["arguments"]))
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call["id"],
                                "content": f"Контракт проверен, раунд {round_number}",
                            }
                        )
                final = {
                    "model": coordinator,
                    "choices": [
                        {
                            "index": 0,
                            "finish_reason": "stop",
                            "message": {
                                "role": "assistant",
                                "content": "Проверка завершена",
                            },
                        }
                    ],
                }
                sink = self.exchange(coordinator, final, messages)
                self.assertEqual(json.loads(b"".join(sink.chunks)), final)
                sent = json.loads(self.requests[-1][1])
                results = [m for m in sent["messages"] if m["role"] == "tool"]
                self.assertEqual(len(results), 6)
                self.assertEqual({m["tool_call_id"] for m in results}, seen_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
