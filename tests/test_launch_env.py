"""Тесты окружения потомка `droid exec`: что доезжает, что вырезается.

Проверяется контракт `_launch_env()`: FACTORY_API_KEY (headless-вход Droid)
сохраняется, авторизационный ключ моста DROID_DSH_BRIDGE_KEY вырезается.
Сеть и droid не вызываются; значение ключа в тесте фиктивное.
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402

FAKE_FACTORY_KEY = "fk-TEST-NOT-REAL"
FAKE_BRIDGE_KEY = "bridge-test-key-not-real"


class TestLaunchEnv(unittest.TestCase):
    """`_launch_env()` как единственная точка формирования окружения потомка."""

    def setUp(self):
        self._env = {
            k: os.environ.get(k) for k in ("FACTORY_API_KEY", "DROID_DSH_BRIDGE_KEY")
        }

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_factory_key_survives_and_bridge_key_is_dropped(self):
        os.environ["FACTORY_API_KEY"] = FAKE_FACTORY_KEY
        os.environ["DROID_DSH_BRIDGE_KEY"] = FAKE_BRIDGE_KEY
        env = server._launch_env()
        self.assertEqual(env.get("FACTORY_API_KEY"), FAKE_FACTORY_KEY)
        self.assertNotIn("DROID_DSH_BRIDGE_KEY", env)
        # Ключ моста не утёк под другим именем
        self.assertNotIn(FAKE_BRIDGE_KEY, set(env.values()))

    def test_absent_factory_key_does_not_appear(self):
        os.environ.pop("FACTORY_API_KEY", None)
        env = server._launch_env()
        self.assertNotIn("FACTORY_API_KEY", env)

    def test_masking_covers_short_factory_key(self):
        masked = server._mask_secrets("auth: " + FAKE_FACTORY_KEY)
        self.assertNotIn(FAKE_FACTORY_KEY, masked)
        self.assertIn("***", masked)

    def test_masking_leaves_ordinary_text_intact(self):
        plain = "no secrets here at all"
        self.assertEqual(server._mask_secrets(plain), plain)


if __name__ == "__main__":
    unittest.main(verbosity=2)
