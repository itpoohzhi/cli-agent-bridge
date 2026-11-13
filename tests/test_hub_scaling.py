"""Масштабирование хаба до 128 сессий и конфигурируемость лимитов (ADR-0018)."""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server  # noqa: E402
from adapters import ADAPTER_KINDS  # noqa: E402
from core.provider_manifest import (  # noqa: E402
    load_manifests,
    providers_dir,
    validate_manifest,
)


class TestHubScalingDefaults(unittest.TestCase):
    def test_max_concurrent_default_128_and_semaphore(self):
        self.assertEqual(server.MAX_CONCURRENT, 128)
        self.assertEqual(server._slots._initial_value, 128)

    def test_timeouts_are_floats_with_safe_defaults(self):
        self.assertEqual(server.QUEUE_TIMEOUT_S, 900.0)
        self.assertEqual(server.TIMEOUT_S, 1800.0)
        self.assertEqual(server.KEEPALIVE_S, 10.0)
        self.assertEqual(server.IDLE_TIMEOUT_S, 120.0)
        for value in (
            server.QUEUE_TIMEOUT_S,
            server.TIMEOUT_S,
            server.KEEPALIVE_S,
            server.IDLE_TIMEOUT_S,
        ):
            self.assertIsInstance(value, float)

    def test_turn_manager_scales_with_max_concurrent(self):
        self.assertEqual(
            server.TURN_MANAGER.max_concurrent, max(server.MAX_CONCURRENT * 8, 256)
        )

    def test_fleet_admission_limits(self):
        data = json.loads(
            (Path(server.ROOT) / "fleet.json").read_text(encoding="utf-8")
        )
        self.assertEqual(server.SUBAGENT_MAX_CONCURRENT, 128)
        self.assertEqual(data["admission"]["max_http_connections"], 128)
        self.assertEqual(data["admission"]["max_inflight_body_bytes"], 536870912)
        for name in ("codex", "agy", "opencode-zen", "claude-p"):
            self.assertEqual(data["backends"][name]["max_concurrent"], 128, name)
        self.assertEqual(data["backends"]["muse"]["max_concurrent"], 64)

    def test_shipped_muse_concurrency_matches_fleet_catalog(self):
        loaded = load_manifests(providers_dir(), ADAPTER_KINDS)
        muse = next(item for item in loaded.manifests if item.provider_id == "muse")
        fleet = json.loads(
            (Path(server.ROOT) / "fleet.json").read_text(encoding="utf-8")
        )
        self.assertEqual(muse.limits.max_concurrent, 64)
        self.assertEqual(fleet["backends"]["muse"]["max_concurrent"], 64)

    def test_muse_max_concurrent_has_no_kind_ceiling(self):
        for max_concurrent in (2, 8, 32):
            with self.subTest(max_concurrent=max_concurrent):
                doc = {
                    "manifest_version": 1,
                    "provider_id": "mus",
                    "kind": "muse",
                    "owned_by": "m",
                    "limits": {"max_concurrent": max_concurrent},
                    "fingerprint": {"binary_path": "~/.local/bin/muse"},
                }
                result = validate_manifest(doc, ADAPTER_KINDS, filename="mus.yaml")
                self.assertEqual(result.errors, ())


if __name__ == "__main__":
    unittest.main()
