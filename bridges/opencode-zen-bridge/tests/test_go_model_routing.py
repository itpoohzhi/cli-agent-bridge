"""Маршрутизация Zen и Go в обоих режимах без запуска реальной модели."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import server
from tests._fixtures import install_test_models

install_test_models(server)

GO_MODEL = "gemini-4-argon-contributor"
GO_BASE_URL = "http://127.0.0.1:10830/go/v1/v1beta"
GO_CONFIG = Path(__file__).resolve().parent.parent / "opencode-go.json"


class GoModelRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        log_guard = patch.object(server, "_log")
        log_guard.start()
        self.addCleanup(log_guard.stop)
        # Здесь проверяем CLI-fallback; нативный Go HTTP покрыт test_google_direct.py.
        guard = patch.object(server, "_is_google_direct_model", return_value=False)
        guard.start()
        self.addCleanup(guard.stop)

    def test_go_model_metadata(self) -> None:
        self.assertEqual(
            server.ALLOWED_MODELS[GO_MODEL],
            {
                "context_length": 1048576,
                "max_output": 65536,
                "supports_variant": True,
                "provider": "opencode-go",
                "base_url": GO_BASE_URL,
            },
        )

    def test_go_config_preserves_permission_and_both_routes(self) -> None:
        config = json.loads(GO_CONFIG.read_text("utf-8"))
        self.assertEqual(config["permission"], {"*": "ask"})
        self.assertEqual(
            config["provider"]["opencode-go"]["options"]["baseURL"], GO_BASE_URL
        )
        self.assertEqual(
            config["provider"]["opencode"]["options"]["baseURL"],
            "http://127.0.0.1:10830/v1",
        )

    def test_go_env_has_local_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            env = server._run_env(GO_MODEL)
        self.assertEqual(env["OPENCODE_CONFIG"], str(GO_CONFIG))
        self.assertEqual(env["OPENCODE_CONFIG_CONTENT"], server.OPENCODE_CONFIG_CONTENT)

    def test_zen_env_has_no_added_config(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            env = server._run_env("big-pickle")
        self.assertNotIn("OPENCODE_CONFIG", env)

    def test_zen_does_not_inherit_foreign_config(self) -> None:
        # THREAT-003: Zen standalone получает окружение только по белому списку.
        with patch.dict(
            os.environ, {"OPENCODE_CONFIG": "/existing/config.json"}, clear=True
        ):
            env = server._run_env("big-pickle")
        self.assertNotIn("OPENCODE_CONFIG", env)

    def test_nonstream_provider_prefix_and_config(self) -> None:
        for model, provider in (("big-pickle", "opencode"), (GO_MODEL, "opencode-go")):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log"),
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    result = server.Run(
                        model, "Проверка", "", Path(tmp)
                    )._execute_once()
                self.assertEqual(result["state"], "spawn_failed")
                self.assertEqual(spawn.call_args.args[0][3], f"{provider}/{model}")
                env = spawn.call_args.args[3]
                self.assertEqual(
                    env.get("OPENCODE_CONFIG"),
                    str(GO_CONFIG) if model == GO_MODEL else None,
                )

    def test_stream_provider_prefix_and_config(self) -> None:
        for model, provider in (("big-pickle", "opencode"), (GO_MODEL, "opencode-go")):
            with self.subTest(model=model), tempfile.TemporaryDirectory() as tmp:
                handler = object.__new__(server.Handler)
                handler.wfile = io.BytesIO()
                handler.send_response = Mock()
                handler.send_header = Mock()
                handler.end_headers = Mock()
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "DEFAULTWORKDIR", Path(tmp)),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log"),
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    handler._stream_sse(model, "Проверка", "")
                self.assertEqual(spawn.call_args.args[0][3], f"{provider}/{model}")
                env = spawn.call_args.args[3]
                self.assertEqual(
                    env.get("OPENCODE_CONFIG"),
                    str(GO_CONFIG) if model == GO_MODEL else None,
                )

    def test_go_effort_ladder_flags_and_log(self) -> None:
        profile_efforts = {
            "off": "off",
            "low": "low",
            "medium": "medium",
            "high": "high",
        }
        self.assertEqual(
            server._map_effort({"model": GO_MODEL, "reasoning_effort": None}), ""
        )
        self.assertEqual(
            server._map_effort({"model": GO_MODEL, "reasoning": {"effort": None}}), ""
        )
        for level, wire_value in profile_efforts.items():
            effort = server._map_effort(
                {"model": GO_MODEL, "reasoning_effort": wire_value}
            )
            expected_effort = "" if level == "off" else level
            self.assertEqual(effort, expected_effort)
            with (
                self.subTest(mode="nonstream", level=level),
                tempfile.TemporaryDirectory() as tmp,
            ):
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log") as log_mock,
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    server.Run(GO_MODEL, "Проверка", effort, Path(tmp))._execute_once()
                cmd = spawn.call_args.args[0]
                logged = "\n".join(c.args[0] for c in log_mock.call_args_list)
                if level == "off":
                    self.assertNotIn("--variant", cmd)
                    self.assertNotIn("--thinking", cmd)
                    self.assertNotIn("--variant", logged)
                    self.assertNotIn("--thinking", logged)
                else:
                    self.assertEqual(
                        cmd[3:5],
                        [f"{server._model_route(GO_MODEL)}#{level}", "--thinking"],
                    )
                    self.assertIn(f"#{level} --thinking", logged)

            with (
                self.subTest(mode="stream", level=level),
                tempfile.TemporaryDirectory() as tmp,
            ):
                handler = object.__new__(server.Handler)
                handler.wfile = io.BytesIO()
                handler.send_response = Mock()
                handler.send_header = Mock()
                handler.end_headers = Mock()
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "DEFAULTWORKDIR", Path(tmp)),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log") as log_mock,
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    handler._stream_sse(GO_MODEL, "Проверка", effort)
                cmd = spawn.call_args.args[0]
                logged = "\n".join(c.args[0] for c in log_mock.call_args_list)
                if level == "off":
                    self.assertNotIn("--variant", cmd)
                    self.assertNotIn("--thinking", cmd)
                    self.assertNotIn("--variant", logged)
                    self.assertNotIn("--thinking", logged)
                else:
                    self.assertEqual(
                        cmd[3:5],
                        [f"{server._model_route(GO_MODEL)}#{level}", "--thinking"],
                    )
                    self.assertIn(f"#{level} --thinking", logged)

    def test_effort_states_zen_vs_go_routes(self) -> None:
        for default_req in (
            {},
            {"reasoning_effort": None},
            {"reasoning": {"effort": None}},
        ):
            with self.subTest(default_req=default_req):
                self.assertEqual(server._map_effort(default_req), "high")

        for zen_model in ("big-pickle", "muse-spark-1.3-contributor-free"):
            for state, extra in (
                ("absent", {}),
                ("null_top", {"reasoning_effort": None}),
                ("null_nested", {"reasoning": {"effort": None}}),
            ):
                with self.subTest(zen_model=zen_model, state=state):
                    self.assertEqual(
                        server._map_effort({"model": zen_model, **extra}),
                        "high",
                    )

        with self.subTest(explicit_model_id=True):
            self.assertEqual(
                server._map_effort({"reasoning_effort": None}, "big-pickle"),
                "high",
            )
            self.assertEqual(
                server._map_effort({"reasoning_effort": None}, GO_MODEL),
                "",
            )

        cases: tuple[tuple[str, str, dict[str, object], str], ...] = (
            ("big-pickle", "absent", {}, "high"),
            ("big-pickle", "null_top", {"reasoning_effort": None}, "high"),
            (
                "big-pickle",
                "null_nested",
                {"reasoning": {"effort": None}},
                "high",
            ),
            ("big-pickle", "off_str", {"reasoning_effort": "off"}, ""),
            (GO_MODEL, "absent", {}, "high"),
            (GO_MODEL, "null_top", {"reasoning_effort": None}, ""),
            (GO_MODEL, "null_nested", {"reasoning": {"effort": None}}, ""),
            (GO_MODEL, "off_str", {"reasoning_effort": "off"}, ""),
        )
        for model, state, extra, expected_effort in cases:
            req = {"model": model, **extra}
            with (
                self.subTest(mode="nonstream", model=model, state=state),
                tempfile.TemporaryDirectory() as tmp,
            ):
                effort = server._map_effort(req)
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log") as log_mock,
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    server.Run(model, "Проверка", effort, Path(tmp))._execute_once()
                cmd = spawn.call_args.args[0]
                logged = "\n".join(c.args[0] for c in log_mock.call_args_list)
                self.assertEqual(effort, expected_effort)
                if expected_effort == "" or model == "big-pickle":
                    self.assertNotIn("--variant", cmd)
                    self.assertNotIn("--thinking", cmd)
                    self.assertNotIn("--variant", logged)
                    self.assertNotIn("--thinking", logged)
                else:
                    self.assertEqual(
                        cmd[3:5],
                        [
                            f"{server._model_route(model)}#{expected_effort}",
                            "--thinking",
                        ],
                    )
                    self.assertIn(f"#{expected_effort} --thinking", logged)

            with (
                self.subTest(mode="stream", model=model, state=state),
                tempfile.TemporaryDirectory() as tmp,
            ):
                effort = server._map_effort(req)
                handler = object.__new__(server.Handler)
                handler.wfile = io.BytesIO()
                handler.send_response = Mock()
                handler.send_header = Mock()
                handler.end_headers = Mock()
                with (
                    patch.dict(os.environ, {}, clear=True),
                    patch.object(server, "DEFAULTWORKDIR", Path(tmp)),
                    patch.object(server, "_resolve_launcher", return_value="/bin/echo"),
                    patch.object(server, "_log") as log_mock,
                    patch.object(
                        server, "_spawn_with_stdin", side_effect=OSError("test spawn")
                    ) as spawn,
                ):
                    handler._stream_sse(model, "Проверка", effort)
                cmd = spawn.call_args.args[0]
                logged = "\n".join(c.args[0] for c in log_mock.call_args_list)
                self.assertEqual(effort, expected_effort)
                if expected_effort == "" or model == "big-pickle":
                    self.assertNotIn("--variant", cmd)
                    self.assertNotIn("--thinking", cmd)
                    self.assertNotIn("--variant", logged)
                    self.assertNotIn("--thinking", logged)
                else:
                    self.assertEqual(
                        cmd[3:5],
                        [
                            f"{server._model_route(model)}#{expected_effort}",
                            "--thinking",
                        ],
                    )
                    self.assertIn(f"#{expected_effort} --thinking", logged)

    def test_stream_go_model_success_with_fake_launcher(self) -> None:
        fake_script = (
            "#!/usr/bin/env python3\n"
            "import json, os, pathlib, sys\n"
            "pathlib.Path(os.environ['FAKE_META']).write_text(json.dumps({\n"
            "    'argv': sys.argv[1:],\n"
            "    'config': os.environ.get('OPENCODE_CONFIG'),\n"
            "    'stdin': sys.stdin.read(),\n"
            "}), encoding='utf-8')\n"
            "for ev in (\n"
            "    {'type': 'reasoning', 'part': {'text': 'Думаю...'}},\n"
            "    {'type': 'text', 'part': {'text': 'PO'}},\n"
            "    {'type': 'text', 'part': {'text': 'NG'}},\n"
            "    {'type': 'step_finish', 'part': {'tokens': {'input': 12, 'output': 4}}},\n"
            "):\n"
            "    print(json.dumps(ev, ensure_ascii=False), flush=True)\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "fake_opencode.py"
            fake_bin.write_text(fake_script, encoding="utf-8")
            fake_bin.chmod(0o755)
            meta_file = tmp_path / "meta.json"
            handler = object.__new__(server.Handler)
            handler.wfile = io.BytesIO()
            handler.send_response = Mock()
            handler.send_header = Mock()
            handler.end_headers = Mock()
            with (
                patch.dict(os.environ, {"FAKE_META": str(meta_file)}, clear=True),
                patch.object(server, "DEFAULTWORKDIR", tmp_path / "ws"),
                patch.object(server, "_resolve_launcher", return_value=str(fake_bin)),
                patch.object(server, "_log"),
            ):
                handler._stream_sse(GO_MODEL, "Reply with PONG", "low")

            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            self.assertEqual(
                meta["argv"],
                [
                    "run",
                    "-m",
                    f"opencode-go/{GO_MODEL}#low",
                    "--thinking",
                    "--format",
                    "json",
                ],
            )
            self.assertEqual(meta["config"], str(GO_CONFIG))
            self.assertEqual(meta["stdin"], "Reply with PONG")

            raw_sse = handler.wfile.getvalue().decode("utf-8")
            self.assertTrue(raw_sse.endswith("data: [DONE]\n\n"))
            chunks = [
                json.loads(line[6:])
                for line in raw_sse.splitlines()
                if line.startswith("data: {")
            ]
            self.assertGreaterEqual(len(chunks), 4)
            self.assertEqual(
                chunks[0]["choices"][0]["delta"],
                {"role": "assistant", "content": ""},
            )
            reasoning = "".join(
                c["choices"][0]["delta"].get("reasoning_content") or "" for c in chunks
            )
            content = "".join(
                c["choices"][0]["delta"].get("content") or "" for c in chunks
            )
            self.assertEqual(reasoning, "Думаю...")
            self.assertEqual(content, "PONG")
            self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "stop")
            self.assertEqual(
                chunks[-1]["usage"],
                {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
            )


if __name__ == "__main__":
    unittest.main()
