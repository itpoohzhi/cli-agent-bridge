"""Тесты image-пути моста (C-08…C-11): таксономия C-10, лимиты, хранение, proof."""

import json
import os
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from bridge_testlib import (  # noqa: E402
    BridgeCase, JPEG_MAGIC, GIF_MAGIC, WEBP_MAGIC,
    find_model, image_part, image_url_part, make_png, make_sig, make_proof,
    text_part,
)


def user_message(parts):
    return {"role": "user", "content": parts}


class ImageCase(BridgeCase):
    """Общие стенды: probe-модель и confirmed-модель с proof."""

    def probe_stand(self, model_id="claude-sonnet-5-5", limits=None):
        def mutate(data):
            item = find_model(data, model_id)
            item["input"] = ["text", "image"]
            item["images"]["status"] = "probe"
            item["images"]["method"] = "workspace-read"
            if limits:
                data["image_limits"].update(limits)
        return self.stand(mutate, probe=True)

    def confirmed_stand(self, model_id="deepseek-v4.1-flash", efforts_proven=None,
                        impl_version=1, formats=("image/png",), binary_bytes=b"stand-binary"):
        binary = Path(self._tmp.name) / ("droid-" + model_id)
        binary.write_bytes(binary_bytes)
        holder = {}

        def mutate(data):
            item = find_model(data, model_id)
            item["input"] = ["text", "image"]
            item["images"]["status"] = "confirmed"
            item["images"]["method"] = "workspace-read"
            item["images"]["proof"] = make_proof(
                binary, efforts_proven if efforts_proven is not None else item["efforts"],
                impl_version=impl_version, formats=formats)
            data["technical_ref"]["droid_binary_path"] = str(binary)
            holder["item"] = item
        self.stand(mutate)
        return binary, holder


class TestImagePositive(ImageCase):
    """Картинки идут в эфемерную RPC-сессию: проверяем фактический ввод и раскладку temp-файлов."""

    def _image_dir_prefix(self):
        return os.path.realpath(str(server.WORKSPACE)) + "/img-"

    def test_two_images_history_prompt_and_layout(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        first, second = make_png(64), make_png(80)
        messages = [
            user_message([text_part("first"), image_part(first)]),
            {"role": "assistant", "content": "ok"},
            user_message([image_part(second), text_part("second")]),
        ]
        with self.capture_logs() as lines:
            status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                    "messages": messages})
        self.assertEqual(status, 200)
        spawn = self.hub.spawns()[-1]
        self.assertEqual(spawn["cwd_mode"], "0o700")
        self.assertEqual(spawn["cwd_files"], {"img-1.png": "0o600", "img-2.png": "0o600"})
        self.assertTrue(spawn["cwd"].startswith(self._image_dir_prefix()))
        execs = [ln for ln in lines if ln.startswith("exec model=")]
        self.assertIn(" images=2 image_bytes=%d image_types=image/png,image/png"
                      % (len(first) + len(second)), execs[0])
        texts = self.hub.sent_texts()
        self.assertEqual(len(texts), 3)  # история replay-ится по сообщениям, цикл запускает последнее
        self.assertEqual(texts[0], "first\n[image 1]")
        self.assertEqual(texts[1], "ok")
        self.assertTrue(texts[2].startswith("[image 2]\nsecond"))
        self.assertIn("- [image 1] ./img-1.png (image/png, %d bytes)" % len(first), texts[2])
        self.assertIn("- [image 2] ./img-2.png (image/png, %d bytes)" % len(second), texts[2])
        self.assertIn("[attachments]", texts[2])
        self.assertIn("Open each image with the Read tool on exactly these paths", texts[2])
        self.assertTrue(self.hub.rpcs("droid.add_user_message")[0]["params"]["skipAgentLoop"])
        self.assertNotIn("skipAgentLoop", self.hub.rpcs("droid.add_user_message")[2]["params"])
        # Read остаётся доступным (нужен для чтения вложений), остальные нативные tools отключены.
        disabled = self.hub.rpcs("droid.update_session_settings")[0]["params"]["disabledToolIds"]
        self.assertNotIn("Read", disabled)
        self.assertIn("Execute", disabled)
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_sixteen_images_at_the_limit(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        parts = [image_part(make_png(64 + i)) for i in range(16)]
        status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                "messages": [user_message(parts)]})
        self.assertEqual(status, 200)
        spawn = self.hub.spawns()[-1]
        self.assertEqual(len(spawn["cwd_files"]), 16)
        prompt = self.hub.sent_texts()[-1]
        for index in range(1, 17):
            self.assertIn("- [image %d] ./img-%d.png (image/png," % (index, index), prompt)
        self.assertEqual(prompt.count("[image 1]"), 2)  # маркер и строка manifest

    def test_image_only_message_is_not_pong(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                "messages": [user_message([image_part(make_png(64))])]})
        self.assertEqual(status, 200)
        prompt = self.hub.sent_texts()[-1]
        self.assertNotIn("Reply with exactly: PONG", prompt)
        self.assertTrue(prompt.startswith("[image 1]"))

    def test_unknown_non_image_parts_are_skipped(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        with self.capture_logs() as lines:
            status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                    "messages": [user_message([
                                        text_part("hello"),
                                        {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
                                    ])]})
        self.assertEqual(status, 200)
        execs = [ln for ln in lines if ln.startswith("exec model=")]
        self.assertNotIn(" images=", execs[0])
        self.assertEqual(self.hub.sent_texts(), ["hello"])

    def test_tools_get_read_exception_with_attachments(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        tools = [{"type": "function", "function": {"name": "get_weather",
                                                   "description": "Get weather",
                                                   "parameters": {"type": "object"}}}]
        status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                "tools": tools,
                                "messages": [user_message([text_part("weather?"),
                                                           image_part(make_png(64))])]})
        self.assertEqual(status, 200)
        system = self.hub.inits()[-1]["params"]["systemPrompt"]
        self.assertIn("except Read on the attachment files listed under [attachments].", system)
        self.assertIn("[attachments]", self.hub.sent_texts()[-1])


class TestImageRejections(ImageCase):
    def test_unverified_and_unsupported_models_rejected(self):
        server.IMAGE_PROBE = True
        for model, expected in (("gemini-3.8-flash", "image_input_not_supported"),
                                ("glm-5.3", "image_input_not_supported")):
            before = len(self.hub.spawns())
            status, body = self._post_json({"model": model, "reasoning_effort":
                                            "max" if model == "glm-5.3" else "high",
                                            "messages": [user_message(
                                                [text_part("x"), image_part(make_png(64))])]})
            self.assertEqual(status, 400, model)
            self.assertEqual(body["error"]["type"], expected)
            self.assertEqual(len(self.hub.spawns()), before)

    def test_taxonomy(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        png = make_png(64)
        cases = [
            ("image_url_not_allowed", image_url_part("http://127.0.0.1:19886/a.png")),
            ("image_url_not_allowed", image_url_part("file:///etc/hosts")),
            ("image_url_not_allowed", image_url_part("https://example.com/a.png")),
            ("unsupported_image_type", image_url_part("data:text/plain;base64,aGk=")),
            ("unsupported_image_type", image_url_part("data:image/svg+xml;base64,PHN2Zy8+")),
            ("invalid_image_base64", image_url_part("data:image/png;base64,@@@@" )),
            ("invalid_image_base64", image_url_part("data:image/png;base64,")),
            ("image_type_mismatch", image_part(make_sig(JPEG_MAGIC, 64), "image/png")),
            ("unsupported_image_type", image_part(b"\x00" * 64, "image/png")),
            ("invalid_image_content", image_url_part("data:image/png,rawdata")),
            ("invalid_image_content", {"type": "image_url", "image_url": "data:image/png;base64,AAAA"}),
            ("invalid_image_content", {"type": "image_url", "image_url": {}}),
            ("unsupported_image_type", image_part(make_sig(JPEG_MAGIC, 64), "image/jpeg")),
            ("unsupported_image_type", image_part(make_sig(WEBP_MAGIC, 64), "image/webp")),
            ("unsupported_image_type", image_part(make_sig(GIF_MAGIC, 64), "image/gif")),
        ]
        for expected, part in cases:
            before = len(self.hub.spawns())
            status, body = self._post_json({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                            "messages": [user_message([text_part("x"), part])]})
            self.assertEqual(status, 400, expected)
            self.assertEqual(body["error"]["type"], expected)
            self.assertEqual(len(self.hub.spawns()), before)
        for role in ("assistant", "system", "tool"):
            messages = [user_message([text_part("hi")]),
                        {"role": role, "content": [image_part(png)]}]
            status, body = self._post_json({"model": "claude-sonnet-5-5",
                                            "reasoning_effort": "high", "messages": messages})
            self.assertEqual(status, 400, role)
            self.assertEqual(body["error"]["type"], "invalid_image_content")

    def test_reject_line_for_image_is_strict(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        with self.capture_logs() as lines:
            self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                        "messages": [user_message([text_part("x"), image_url_part(
                            "http://127.0.0.1:19886/a.png")])]})
        rejects = [ln for ln in lines if "reject reason=" in ln]
        self.assertEqual(len(rejects), 1)
        self.assertEqual(rejects[0], rejects[0].rstrip())
        self.assertRegex(rejects[0], r"^reject reason=image_url_not_allowed "
                                     r"model=claude-sonnet-5-5 model_len=\d+ client=[0-9.:]+$")

    def test_limits(self):
        server.IMAGE_PROBE = True
        self.probe_stand(limits={"max_images": 2, "max_image_bytes": 1000,
                                 "max_total_image_bytes": 1500})
        def post(parts):
            return self._post_json({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                    "messages": [user_message(parts)]})
        status, body = post([image_part(make_png(64))] * 3)
        self.assertEqual(body["error"]["type"], "too_many_images")
        status, body = post([image_part(make_png(1001))])
        self.assertEqual(body["error"]["type"], "image_too_large")
        status, body = post([image_part(make_png(800)), image_part(make_png(800))])
        self.assertEqual(body["error"]["type"], "images_too_large")
        status, _ = post([image_part(make_png(700)), image_part(make_png(700))])
        self.assertEqual(status, 200)


class TestImageCleanup(ImageCase):
    def test_cleanup_after_success(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        status, _ = self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                "messages": [user_message([image_part(make_png(64))])]})
        self.assertEqual(status, 200)
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_cleanup_after_exception(self):
        # Сбой запуска (лончер умирает сразу): 502 и ни одного каталога картинок.
        server.IMAGE_PROBE = True
        self.probe_stand()
        broken = Path(self._tmp.name) / "broken-launcher"
        broken.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        broken.chmod(0o755)
        server.LAUNCHER = str(broken)
        status, _ = self._post_json({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                     "messages": [user_message([image_part(make_png(64))])]})
        self.assertEqual(status, 502)
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_cleanup_after_retries(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        self.hub.legacy([[("stderr", "Exec failed"), ("done", (1, ""))] for _ in range(3)])
        status, _ = self._post_json({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                                     "messages": [user_message([image_part(make_png(64))])]})
        self.assertEqual(status, 502)
        self.assertEqual(len(self.hub.admissions()), 3)
        spawns = self.hub.spawns()
        self.assertEqual(len(spawns), 3)
        for spawn in spawns:  # temp-файлы жили до последней попытки
            self.assertEqual(spawn["cwd_files"], {"img-1.png": "0o600"})
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])

    def test_cleanup_after_client_gone(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        real_gone = server._client_gone
        server._client_gone = lambda sock: True
        try:
            raw = self._raw_request(json.dumps({
                "model": "claude-sonnet-5-5", "reasoning_effort": "high",
                "messages": [user_message([image_part(make_png(64))])]}).encode())
            sock = __import__("socket").create_connection(("127.0.0.1", self.port), timeout=5)
            sock.sendall(raw)
            time.sleep(0.7)
            sock.close()
        finally:
            server._client_gone = real_gone
        deadline = time.time() + 5
        while time.time() < deadline and list(server.WORKSPACE.glob("img-*")):
            time.sleep(0.1)
        self.assertEqual(list(server.WORKSPACE.glob("img-*")), [])
        # Клиент ушёл раньше хода: ход не доходит до модели, процесс не остаётся.
        self.assertLessEqual(len(self.hub.spawns()), 1)
        self.assertEqual(len(self.hub.admissions()), 0)


class TestProofFailClosed(ImageCase):
    def request(self, model, effort="high"):
        return self._post_json({"model": model, "reasoning_effort": effort,
                                "messages": [user_message([text_part("x"),
                                                           image_part(make_png(64))])]})

    def test_valid_proof_accepts_then_degrades_on_binary_change(self):
        binary, _ = self.confirmed_stand()
        status, _ = self.request("deepseek-v4.1-flash", "max")
        self.assertEqual(status, 200)
        self.assertEqual(len(self.hub.admissions()), 1)
        binary.write_bytes(b"other-binary-content")
        with self.capture_logs() as lines:
            status, body = self.request("deepseek-v4.1-flash", "max")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "image_input_not_supported")
        self.assertTrue(any("image_proof_invalid model=deepseek-v4.1-flash "
                            "reason=droid_binary_sha" in ln for ln in lines))
        status, _ = self._post_json({"model": "deepseek-v4.1-flash", "reasoning_effort": "max",
                                     "messages": [{"role": "user", "content": "text alive"}]})
        self.assertEqual(status, 200)

    def test_impl_version_mismatch_degrades(self):
        self.confirmed_stand(impl_version=2)
        with self.capture_logs() as lines:
            status, body = self.request("deepseek-v4.1-flash", "high")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "image_input_not_supported")
        self.assertTrue(any("reason=impl_version" in ln for ln in lines))
        status, _ = self._post_json({"model": "deepseek-v4.1-flash", "reasoning_effort": "high",
                                     "messages": [{"role": "user", "content": "still text"}]})
        self.assertEqual(status, 200)

    def test_formats_mismatch_degrades(self):
        self.confirmed_stand(formats=())
        with self.capture_logs() as lines:
            status, body = self.request("deepseek-v4.1-flash", "high")
        self.assertEqual(status, 400)
        self.assertTrue(any("reason=formats" in ln for ln in lines))

    def test_effort_not_proven_degrades_only_that_effort(self):
        self.confirmed_stand(efforts_proven=["high"])
        status, _ = self.request("deepseek-v4.1-flash", "high")
        self.assertEqual(status, 200)
        with self.capture_logs() as lines:
            status, body = self.request("deepseek-v4.1-flash", "max")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["type"], "image_input_not_supported")
        self.assertTrue(any("reason=effort" in ln for ln in lines))
        self.assertEqual(len([ln for ln in lines if ln.startswith("exec model=")]), 0)


class TestImageJournal(ImageCase):
    def test_exec_line_counters_only(self):
        server.IMAGE_PROBE = True
        self.probe_stand()
        with self.capture_logs() as lines:
            self._post({"model": "claude-sonnet-5-5", "reasoning_effort": "high",
                        "messages": [user_message([image_part(make_png(64))])]})
        execs = [ln for ln in lines if ln.startswith("exec model=")]
        self.assertEqual(len(execs), 1)
        self.assertIn(" images=1 image_bytes=64 image_types=image/png", execs[0])
        self.assertNotIn("iVBOR", execs[0])
        self.assertNotIn(str(server.WORKSPACE), execs[0])
        joined = "\n".join(lines)
        self.assertNotIn("iVBORw0KGgo", joined)
        self.assertNotIn(str(server.WORKSPACE), joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
