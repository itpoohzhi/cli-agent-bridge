"""Интеграция реального RPC-слоя моста с fake stream-jsonrpc subprocess (без droid и сети).

Проверяются: argv процесса (только режим stream-jsonrpc, без prompt-файла на ход и
без запрещённых флагов), параметры RPC initialize_session (model/effort/autonomy,
безопасные настройки), раскладка каталога image-запуска (0700/0600, без prompt.txt),
окружение ребёнка (ключ моста вырезан, чистый Factory home 0700) и отсутствие
prompt-файлов в workspace.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import (  # noqa: E402
    BridgeCase,
    find_model,
    image_part,
    make_png,
    text_part,
)

RPC_ARGV = [
    "exec",
    "--input-format",
    "stream-jsonrpc",
    "--output-format",
    "stream-jsonrpc",
]


class TestRealRun(BridgeCase):
    def setUp(self):
        super().setUp()
        self._env_key = os.environ.get("DROID_DSH_BRIDGE_KEY")
        os.environ["DROID_DSH_BRIDGE_KEY"] = "secret-in-env"

    def tearDown(self):
        if self._env_key is None:
            os.environ.pop("DROID_DSH_BRIDGE_KEY", None)
        else:
            os.environ["DROID_DSH_BRIDGE_KEY"] = self._env_key
        super().tearDown()

    def test_text_rpc_argv_init_and_env(self):
        status, body = self._post_json(
            {
                "model": "claude-sonnet-5-5",
                "reasoning_effort": "high",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "PONG")
        spawns = self.hub.spawns()
        self.assertEqual(len(spawns), 1)
        spawn = spawns[0]
        self.assertEqual(spawn["argv"], RPC_ARGV)
        for forbidden in ("--skip-permissions-unsafe", "-f", "--auto", "-m", "-r"):
            self.assertNotIn(forbidden, spawn["argv"])
        self.assertEqual(spawn["cwd"], os.path.realpath(str(server.WORKSPACE)))
        init = self.hub.inits()[0]["params"]
        self.assertEqual(init["modelId"], "claude-sonnet-5-5")
        self.assertEqual(init["reasoningEffort"], "high")
        self.assertEqual(init["autonomyLevel"], "high")
        self.assertEqual(init["cwd"], os.path.realpath(str(server.WORKSPACE)))
        self.assertIs(init["disableBuiltinSkills"], True)
        self.assertIs(init["autoRejectPermissionRequests"], True)
        self.assertTrue(
            init["title"]
        )  # явный title отключает фоновый LLM-заголовок droid
        self.assertFalse(spawn["bridge_key_in_env"])
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", spawn["env_names"])
        home = os.path.realpath(str(server.WORKSPACE / "runtime" / "factory-home"))
        self.assertEqual(os.path.realpath(spawn["factory_home"]), home)
        self.assertEqual(spawn["factory_home_mode"], "0o700")
        self.assertEqual(spawn["droid_auto"], "off")
        self.assertEqual(list(server.WORKSPACE.glob("prompt-*")), [])

    def test_image_layout_without_prompt_file(self):
        server.IMAGE_PROBE = True

        def mutate(data):
            item = find_model(data, "claude-sonnet-5-5")
            item["input"] = ["text", "image"]
            item["images"]["status"] = "probe"
            item["images"]["method"] = "workspace-read"

        self.stand(mutate, probe=True)
        status, _ = self._post(
            {
                "model": "claude-sonnet-5-5",
                "reasoning_effort": "high",
                "messages": [
                    {
                        "role": "user",
                        "content": [text_part("x"), image_part(make_png(64))],
                    }
                ],
            }
        )
        self.assertEqual(status, 200)
        spawns = self.hub.spawns()
        self.assertEqual(len(spawns), 1)
        self.assertEqual(spawns[0]["argv"], RPC_ARGV)
        self.assertTrue(
            spawns[0]["cwd"].startswith(
                os.path.realpath(str(server.WORKSPACE)) + "/img-"
            )
        )
        self.assertEqual(spawns[0]["cwd_mode"], "0o700")
        self.assertEqual(spawns[0]["cwd_files"], {"img-1.png": "0o600"})
        self.assertEqual(self.hub.inits()[0]["params"]["cwd"], spawns[0]["cwd"])
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_readonly_off_is_set_over_rpc_and_low_passes(self):
        status, _ = self._post_json(
            {
                "model": "gemini-3.8-flash",
                "reasoning_effort": "high",
                "autonomy": "off",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        status, _ = self._post_json(
            {
                "model": "gemini-3.8-flash",
                "reasoning_effort": "high",
                "autonomy": "low",
                "messages": [{"role": "user", "content": "hi"}],
            }
        )
        self.assertEqual(status, 200)
        inits = self.hub.inits()
        self.assertEqual(len(inits), 2)
        self.assertEqual(inits[0]["params"]["autonomyLevel"], "off")
        self.assertEqual(inits[1]["params"]["autonomyLevel"], "low")
        for record in self.hub.spawns():
            self.assertNotIn("--skip-permissions-unsafe", record["argv"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
