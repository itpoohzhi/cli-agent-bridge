"""Оракул ASAR integrity (RW-001/RW-003): положительный и отрицательные контроли без правки вендора."""

import json
import hashlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import asar_oracle as oracle  # noqa: E402

OK = oracle.OracleResult(True, "")
BAD = oracle.OracleResult(False, "manifest_mismatch")
BODY = b"body"
BODY_HASH = hashlib.sha256(BODY).hexdigest()


def build_asar(path: Path, digest: str, entry: str = oracle.ENTRY) -> None:
    node: dict = {"files": {}}
    cursor = node
    parts = entry.split("/")
    for part in parts[:-1]:
        cursor["files"][part] = {"files": {}}
        cursor = cursor["files"][part]
    cursor["files"][parts[-1]] = {"size": len(BODY), "offset": "0", "integrity": {"algorithm": "SHA256", "hash": digest}}
    payload = json.dumps(node).encode("utf-8")
    prefix = struct.pack("<IIII", 4, len(payload) + 8, len(payload) + 4, len(payload))
    path.write_bytes(prefix + payload + BODY)


def cordis(base_url: str, extra: str = "x") -> dict:
    return {"providers": {"codex": {"baseURL": base_url, "timeoutMs": 1}, "agy": {"baseURL": extra}}}


class TestAsarIntegrityOracle(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.asar = Path(self._tmp.name) / "app.asar"

    def test_matching_integrity_passes_and_is_read_only(self):
        build_asar(self.asar, BODY_HASH)
        before = self.asar.read_bytes()
        result = oracle.check_asar_integrity(self.asar, expected=BODY_HASH)
        self.assertTrue(result.ok)
        self.assertEqual(result.observed, BODY_HASH)
        self.assertEqual(self.asar.read_bytes(), before)

    def test_tampered_bytes_with_unchanged_header_hash_fail(self):
        build_asar(self.asar, BODY_HASH)
        raw = self.asar.read_bytes()
        self.asar.write_bytes(raw[:-len(BODY)] + b"evil")
        self.assertFalse(oracle.check_asar_integrity(self.asar, expected=BODY_HASH).ok)

    def test_integrity_mismatch_fails(self):
        build_asar(self.asar, "0" * 64)
        result = oracle.check_asar_integrity(self.asar, expected=BODY_HASH)
        self.assertEqual((result.ok, result.reason), (False, "asar_integrity_mismatch"))

    def test_missing_asar_fails(self):
        result = oracle.check_asar_integrity(self.asar, expected=BODY_HASH)
        self.assertEqual((result.ok, result.reason), (False, "asar_unreadable"))

    def test_corrupted_asar_fails(self):
        for label, blob in (("short", b"abc"), ("garbage", b"\x00" * 16 + b"not json"),
                            ("truncated", struct.pack("<IIII", 4, 100, 96, 90) + b"{}")):
            with self.subTest(label=label):
                self.asar.write_bytes(blob)
                self.assertFalse(oracle.check_asar_integrity(self.asar, expected=BODY_HASH).ok)

    def test_entry_absent_fails(self):
        build_asar(self.asar, BODY_HASH, entry="dsh/other/index.js")
        self.assertEqual(oracle.check_asar_integrity(self.asar, expected=BODY_HASH).reason, "asar_header_invalid")

    def test_asar_check_survives_manifest_failure_of_allowed_cordis_switch(self):
        # единственное разрешённое изменение cordis делает сырой shasum -c != 0; ASAR всё равно проверяется
        build_asar(self.asar, BODY_HASH)
        asar = oracle.check_asar_integrity(self.asar, expected=BODY_HASH)
        switch = oracle.check_cordis_switch(cordis(oracle.CODEX_BASE_URL_BEFORE), cordis(oracle.CODEX_BASE_URL_AFTER))
        self.assertTrue(asar.ok)
        self.assertTrue(switch.ok)
        self.assertEqual(oracle.gate(OK, asar, switch), 0)
        self.assertEqual(oracle.gate(BAD, asar, switch), 1)  # protected-файлы изменены -> общий FAIL

    def test_gate_fails_when_any_independent_check_fails(self):
        build_asar(self.asar, "f" * 64)
        self.assertEqual(oracle.gate(OK, oracle.check_asar_integrity(self.asar, expected=BODY_HASH), OK), 1)

    def test_cordis_extra_diff_fails(self):
        after = cordis(oracle.CODEX_BASE_URL_AFTER, extra="changed")
        result = oracle.check_cordis_switch(cordis(oracle.CODEX_BASE_URL_BEFORE), after)
        self.assertEqual(result.reason, "cordis_extra_diff")

    def test_cordis_wrong_final_baseurl_fails(self):
        result = oracle.check_cordis_switch(cordis(oracle.CODEX_BASE_URL_BEFORE), cordis("http://127.0.0.1:1/v1"))
        self.assertEqual(result.reason, "cordis_final_baseurl_invalid")

    def test_cordis_missing_data_fails(self):
        self.assertFalse(oracle.check_cordis_switch({}, cordis(oracle.CODEX_BASE_URL_AFTER)).ok)
        self.assertFalse(oracle.check_cordis_switch(cordis(oracle.CODEX_BASE_URL_BEFORE), None).ok)

    def test_cli_exit_codes(self):
        build_asar(self.asar, BODY_HASH)
        self.assertEqual(oracle.main(["--asar", str(self.asar), "--expected", BODY_HASH]), 0)
        self.assertEqual(oracle.main(["--asar", str(self.asar), "--expected", "1" * 64]), 1)

    def test_cli_runs_both_checks_when_either_fails(self):
        before = Path(self._tmp.name) / "before.json"
        after = Path(self._tmp.name) / "after.json"
        before.write_text(json.dumps(cordis(oracle.CODEX_BASE_URL_BEFORE)))
        after.write_text(json.dumps(cordis(oracle.CODEX_BASE_URL_AFTER)))
        for asar_result, cordis_result, expected in ((BAD, OK, 1), (OK, BAD, 1), (OK, OK, 0)):
            with patch.object(oracle, "check_asar_integrity", return_value=asar_result) as asar_check, patch.object(oracle, "check_cordis_switch", return_value=cordis_result) as cordis_check:
                self.assertEqual(oracle.main(["--asar", str(self.asar), "--cordis-before", str(before), "--cordis-after", str(after)]), expected)
                asar_check.assert_called_once()
                cordis_check.assert_called_once()

    def test_cli_manifest_failure_still_reports_asar_and_cordis(self):
        before = Path(self._tmp.name) / "before.json"
        after = Path(self._tmp.name) / "after.json"
        before.write_text(json.dumps(cordis(oracle.CODEX_BASE_URL_BEFORE)))
        after.write_text(json.dumps(cordis(oracle.CODEX_BASE_URL_AFTER)))
        build_asar(self.asar, BODY_HASH)
        with patch("builtins.print") as output:
            code = oracle.main(["--asar", str(self.asar), "--expected", BODY_HASH, "--cordis-before", str(before), "--cordis-after", str(after), "--manifest-exit-code", "1"])
        self.assertEqual(code, 1)
        self.assertEqual([call.args[0] for call in output.call_args_list], ["asar-entry", "cordis-switch", "manifest"])

    @unittest.skipUnless(Path(oracle.DEFAULT_ASAR).exists(), "DeepSeek Harness не установлен")
    def test_live_vendor_asar_matches_expected_integrity(self):
        result = oracle.check_asar_integrity()
        self.assertTrue(result.ok, result)


if __name__ == "__main__":
    unittest.main()
