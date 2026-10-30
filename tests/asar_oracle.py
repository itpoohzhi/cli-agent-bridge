"""Независимый read-only оракул целостности ASAR (ADR 0011, RW-001/RW-003; VER-008/VER-009).

Вендорское приложение и его пакет не изменяются: файл `app.asar` только читается. Проверка ASAR
не зависит от `shasum -c pre-delivery.sha256` (допустимое расхождение cordis после switch не
должно её пропускать через короткое замыкание `&&`): у неё свой результат и свой exit-код.

Запуск: `python3 -I tests/asar_oracle.py [--asar PATH] [--expected SHA256]` -> exit 0 только при
совпадении SHA256 фактических байтов и integrity записи `dsh-tool-subagent/lib/index.js` с ожидаемой.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ASAR = "/Applications/DeepSeek Harness.app/Contents/Resources/app.asar"
ENTRY = "dsh/node_modules/@deepseek-ai/dsh-tool-subagent/lib/index.js"
EXPECTED_HASH = "de7b10aaf52b1b1616d13a831a9ece1f820b8a6302fe94667f31b6d641b2f46e"
CODEX_BASE_URL_BEFORE = "http://127.0.0.1:2455/v1"
CODEX_BASE_URL_AFTER = "http://127.0.0.1:9882/v1"


class AsarError(Exception):
    """ASAR отсутствует, повреждён либо запись не найдена."""


@dataclass(frozen=True)
class OracleResult:
    ok: bool
    reason: str
    observed: str = ""


def read_entry_hash(path: str | Path, entry: str = ENTRY) -> str:
    """Проверка SHA256 байтов записи по offset/size и integrity.hash заголовка ASAR."""
    try:
        with open(path, "rb") as handle:
            prefix = handle.read(16)
            if len(prefix) < 16:
                raise AsarError("asar_truncated")
            size = struct.unpack("<I", prefix[12:16])[0]
            raw = handle.read(size)
    except OSError as exc:
        raise AsarError("asar_unreadable") from exc
    if len(raw) < size:
        raise AsarError("asar_truncated")
    try:
        header = json.loads(raw.decode("utf-8"))
        node = functools.reduce(lambda acc, key: acc["files"][key], entry.split("/"), header)
        digest = node["integrity"]["hash"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError) as exc:
        raise AsarError("asar_header_invalid") from exc
    if not isinstance(digest, str):
        raise AsarError("asar_header_invalid")
    try:
        size = node["size"]
        offset = int(node["offset"])
        if type(size) is not int or size < 0 or offset < 0 or node.get("unpacked") or node["integrity"]["algorithm"] != "SHA256":
            raise ValueError("unsupported entry")
        hasher = hashlib.sha256()
        with open(path, "rb") as handle:
            handle.seek(8 + struct.unpack("<I", prefix[4:8])[0] + offset)
            remaining = size
            while remaining:
                block = handle.read(min(remaining, 1024 * 1024))
                if not block:
                    raise AsarError("asar_truncated")
                hasher.update(block)
                remaining -= len(block)
        if hasher.hexdigest() != digest:
            raise AsarError("asar_integrity_mismatch")
    except OSError as exc:
        raise AsarError("asar_unreadable") from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise AsarError("asar_header_invalid") from exc
    return digest


def check_asar_integrity(
    path: str | Path = DEFAULT_ASAR, expected: str = EXPECTED_HASH, entry: str = ENTRY
) -> OracleResult:
    try:
        observed = read_entry_hash(path, entry)
    except AsarError as exc:
        return OracleResult(False, str(exc))
    if observed != expected:
        return OracleResult(False, "asar_integrity_mismatch", observed)
    return OracleResult(True, "", observed)


def _without_base_url(config: Any) -> Any:
    """Копия cordis-конфига с обнулённым `providers.codex.baseURL` (единственное допустимое изменение)."""
    if not isinstance(config, dict):
        return config
    clone = json.loads(json.dumps(config))
    codex = ((clone.get("providers") or {}) if isinstance(clone.get("providers"), dict) else {}).get("codex")
    if isinstance(codex, dict):
        codex["baseURL"] = None
    return clone


def check_cordis_switch(before: Any, after: Any) -> OracleResult:
    """После switch допустим единственный diff: `providers.codex.baseURL` :2455 -> :9882."""
    try:
        old = before["providers"]["codex"]["baseURL"]
        new = after["providers"]["codex"]["baseURL"]
    except (KeyError, TypeError):
        return OracleResult(False, "cordis_codex_baseurl_missing")
    if old != CODEX_BASE_URL_BEFORE:
        return OracleResult(False, "cordis_baseline_unexpected", str(old))
    if new != CODEX_BASE_URL_AFTER:
        return OracleResult(False, "cordis_final_baseurl_invalid", str(new))
    if _without_base_url(before) != _without_base_url(after):
        return OracleResult(False, "cordis_extra_diff")
    return OracleResult(True, "")


def gate(manifest: OracleResult, asar: OracleResult, cordis: OracleResult) -> int:
    """Общий exit=0 только при успехе ВСЕХ независимых проверок; ни одна не маскирует другую."""
    return 0 if manifest.ok and asar.ok and cordis.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asar", default=DEFAULT_ASAR)
    parser.add_argument("--expected", default=EXPECTED_HASH)
    parser.add_argument("--cordis-before", type=Path, help="JSON-снимок cordis до switch")
    parser.add_argument("--cordis-after", type=Path, help="JSON-снимок cordis после switch")
    parser.add_argument("--manifest-exit-code", type=int)
    args = parser.parse_args(argv)
    if bool(args.cordis_before) != bool(args.cordis_after):
        parser.error("--cordis-before and --cordis-after must be supplied together")
    asar = check_asar_integrity(args.asar, args.expected)
    print("asar-entry", asar.observed or "-", "PASS" if asar.ok else "FAIL " + asar.reason)
    cordis = OracleResult(True, "")
    if args.cordis_before:
        try:
            before = json.loads(args.cordis_before.read_text(encoding="utf-8"))
            after = json.loads(args.cordis_after.read_text(encoding="utf-8"))
            cordis = check_cordis_switch(before, after)
        except (OSError, ValueError, UnicodeDecodeError):
            cordis = OracleResult(False, "cordis_unreadable")
        print("cordis-switch", "PASS" if cordis.ok else "FAIL " + cordis.reason)
    manifest = OracleResult(args.manifest_exit_code in (None, 0), "manifest_mismatch")
    if args.manifest_exit_code is not None:
        print("manifest", "PASS" if manifest.ok else "FAIL " + manifest.reason)
    return gate(manifest, asar, cordis)


if __name__ == "__main__":
    sys.exit(main())
