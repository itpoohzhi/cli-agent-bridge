"""Интеграция реального Run с локальной заглушкой лончера (без droid и сети).

Проверяются: форма argv текстового запроса (один -m, один -r, `--auto high`
по дефолту, `autonomy=off` — без флага, без запрещённых флагов), argv и
раскладка каталога image-запуска (0700/0600, prompt.txt внутри),
отсутствие ключа моста в окружении потомка, режим prompt-файла и его удаление.
"""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import (  # noqa: E402
    BridgeCase, find_model, image_part, make_png, text_part,
)

STUB_TEMPLATE = '''#!/usr/bin/python3
import json, os, sys
rec = {"argv": sys.argv, "cwd": os.getcwd(), "env_names": sorted(os.environ)}
rec["dir_mode"] = oct(os.stat(".").st_mode & 0o777)
rec["files"] = {}
for name in sorted(os.listdir(".")):
    if os.path.isfile(name):
        rec["files"][name] = oct(os.stat(name).st_mode & 0o777)
with open(%(log)r, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(rec) + "\\n")
print('{"type":"message","role":"assistant","text":"PONG"}')
print('{"type":"completion","finalText":"PONG","usage":{}}')
'''


class TestRealRun(BridgeCase):
    def setUp(self):
        super().setUp()
        server.Run = self._real_run
        self.log_path = Path(self._tmp.name) / "stub-log.jsonl"
        stub = Path(self._tmp.name) / "stub-launcher"
        stub.write_text(STUB_TEMPLATE % {"log": str(self.log_path)}, encoding="utf-8")
        stub.chmod(0o755)
        server.LAUNCHER = str(stub)
        self._env_key = os.environ.get("DROID_DSH_BRIDGE_KEY")
        os.environ["DROID_DSH_BRIDGE_KEY"] = "secret-in-env"

    def tearDown(self):
        if self._env_key is None:
            os.environ.pop("DROID_DSH_BRIDGE_KEY", None)
        else:
            os.environ["DROID_DSH_BRIDGE_KEY"] = self._env_key
        super().tearDown()

    def records(self):
        return [json.loads(line) for line in self.log_path.read_text().splitlines() if line.strip()]

    def test_text_argv_shape_and_prompt_cleanup(self):
        status, body = self._post_json({"model": "claude-sonnet-5-5",
                                        "reasoning_effort": "high",
                                        "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(status, 200)
        self.assertEqual(body["choices"][0]["message"]["content"], "PONG")
        records = self.records()
        self.assertEqual(len(records), 1)
        argv = records[0]["argv"]
        self.assertEqual(argv[0], server.LAUNCHER)
        self.assertEqual(argv[1:6], ["exec", "-o", "stream-json",
                                     "-m", "claude-sonnet-5-5"])
        self.assertEqual(argv.count("-m"), 1)
        self.assertEqual(argv.count("-r"), 1)
        self.assertEqual(argv[argv.index("-r") + 1], "high")
        self.assertEqual(argv.count("--auto"), 1)
        self.assertEqual(argv[argv.index("--auto") + 1], "high")
        self.assertNotIn("--skip-permissions-unsafe", argv)
        self.assertEqual(argv[argv.index("--cwd") + 1], str(server.WORKSPACE))
        self.assertEqual(argv[argv.index("--tag") + 1], "droid-dsh-bridge")
        prompt_file = argv[argv.index("-f") + 1]
        self.assertTrue(Path(prompt_file).name.startswith("prompt-"))
        self.assertEqual(os.path.realpath(records[0]["cwd"]),
                         os.path.realpath(str(server.WORKSPACE)))
        self.assertEqual(records[0]["files"][Path(prompt_file).name], "0o600")
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", records[0]["env_names"])
        self.assertEqual(list(server.WORKSPACE.glob("prompt-*")), [])

    def test_image_argv_and_layout(self):
        server.IMAGE_PROBE = True

        def mutate(data):
            item = find_model(data, "claude-sonnet-5-5")
            item["input"] = ["text", "image"]
            item["images"]["status"] = "probe"
            item["images"]["method"] = "workspace-read"
        self.stand(mutate, probe=True)
        status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                "messages": [{"role": "user",
                                              "content": [text_part("x"), image_part(make_png(64))]}]})
        self.assertEqual(status, 200)
        records = self.records()
        self.assertEqual(len(records), 1)
        argv = records[0]["argv"]
        cwd = argv[argv.index("--cwd") + 1]
        self.assertTrue(cwd.startswith(str(server.WORKSPACE) + "/img-"))
        self.assertEqual(argv.count("-m"), 1)
        self.assertEqual(argv.count("-r"), 1)
        self.assertEqual(argv.count("--auto"), 1)
        self.assertEqual(argv[argv.index("--auto") + 1], "high")
        prompt_file = Path(argv[argv.index("-f") + 1])
        self.assertEqual(str(prompt_file.parent), cwd)
        self.assertEqual(records[0]["dir_mode"], "0o700")
        self.assertEqual(records[0]["files"], {"img-1.png": "0o600", "prompt.txt": "0o600"})
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_readonly_off_omits_auto_and_low_passes(self):
        status, _ = self._post_json({"model": "gemini-3.8-flash",
                                     "reasoning_effort": "high",
                                     "autonomy": "off",
                                     "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(status, 200)
        status, _ = self._post_json({"model": "gemini-3.8-flash",
                                     "reasoning_effort": "high",
                                     "autonomy": "low",
                                     "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(status, 200)
        records = self.records()
        self.assertEqual(len(records), 2)
        self.assertNotIn("--auto", records[0]["argv"])
        self.assertNotIn("--skip-permissions-unsafe", records[0]["argv"])
        self.assertEqual(records[1]["argv"].count("--auto"), 1)
        self.assertEqual(records[1]["argv"][records[1]["argv"].index("--auto") + 1], "low")


if __name__ == "__main__":
    unittest.main(verbosity=2)
