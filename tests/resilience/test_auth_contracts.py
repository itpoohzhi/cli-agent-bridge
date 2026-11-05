"""Contract tests for bridge endpoint authentication resilience.

Validates that invalid or missing authentication tokens are rejected with 401
across all endpoints and peer IP types without leaking request bodies.
"""

from email.message import Message
import importlib.util
from pathlib import Path
import sys
from typing import Any
import unittest
from unittest.mock import Mock

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ROOT_SERVER = _REPO_ROOT / "server.py"


def _get_root_server() -> Any:
    mod = sys.modules.get("server")
    if mod is not None and getattr(mod, "__file__", "") == str(_ROOT_SERVER):
        return mod
    spec = importlib.util.spec_from_file_location("server", _ROOT_SERVER)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    sys.modules["server"] = loaded
    spec.loader.exec_module(loaded)
    return loaded


server = _get_root_server()


class TestCriticalFixes(unittest.TestCase):
    """Test suite ensuring all endpoints strictly require authentication."""

    def test_all_endpoints_require_auth(self) -> None:
        """Matrix test: 3 endpoints x 31 auth/peer variations = 93 subtests."""
        endpoints = [
            "/v1/chat/completions",
            "/v1/models",
            "/v1/models/refresh",
        ]
        tokens = [
            None,
            "",
            "Bearer wrong-token-1",
            "Bearer expired-token-2",
            "Bearer foreign-token-3",
            "Bearer invalid-signature-4",
            "Bearer ../escaped-token",
            "Basic dXNlcjpwYXNz",
            "Bearer ",
            "Token raw-format-unsupported",
        ]
        peers = ["127.0.0.1", "::1", "192.0.2.1"]

        # Build exactly 31 test variants (10 tokens x 3 peers + 1 malformed header)
        variants = []
        for peer in peers:
            for token in tokens:
                variants.append((peer, token))
        variants.append(("127.0.0.1", "Bearer \r\ninjected-header"))
        assert len(variants) == 31, f"Expected 31 variants, got {len(variants)}"

        subtest_count = 0
        for endpoint in endpoints:
            for peer, token in variants:
                subtest_count += 1
                with self.subTest(
                    endpoint=endpoint, peer=peer, token=token, count=subtest_count
                ):
                    handler = object.__new__(server.Handler)
                    handler.path = endpoint
                    handler.client_address = (peer, 12345)
                    handler.headers = Message()
                    if token is not None:
                        handler.headers["Authorization"] = token
                    handler.headers["Content-Length"] = "2"
                    handler.rfile = Mock()
                    sent_status = None
                    sent_body = None

                    def mock_send(status: int, body: dict) -> None:
                        nonlocal sent_status, sent_body
                        sent_status = status
                        sent_body = body

                    handler._send = mock_send
                    handler.close_connection = False

                    handler.do_POST()

                    # Critical invariant: must be 401 unauthorized, NEVER 503 bridge shutting down
                    self.assertEqual(
                        sent_status,
                        401,
                        f"Endpoint {endpoint} with peer {peer} and token {token!r} "
                        f"returned {sent_status} instead of 401: {sent_body}",
                    )
                    handler.rfile.read.assert_not_called()
                    self.assertTrue(handler.close_connection)

        self.assertEqual(subtest_count, 93, f"Expected 93 subtests, ran {subtest_count}")
