#!/usr/bin/env python3
"""DEP-09: неизменяемый образ droid и receipt допуска всех моделей fleet.

Копия runtime/droid-image/<sha256>/droid (0500, каталоги 0700) проходит spawn/update/load
в изолированном Factory home. Только после всех проб атомарно пишется schema-2 receipt
с протоколом, точными каталогами моделей и профилем настроек. Глобальный бинарь не меняется.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

sys.path.insert(0, str(Path(__file__).resolve().parent))

import receipt_schema as schema  # noqa: E402  - общая схема без импорта server.py
from droid_probe_config import ProbeError, probe_models as _probe_models  # noqa: E402

PROBE_TIMEOUT_S = float(os.environ.get("DROID_PROBE_TIMEOUT_S", "30.0"))
PROBE_AUTONOMY = "high"
READBACK_KEYS = (
    "modelId",
    "reasoningEffort",
    "autonomyLevel",
    "interactionMode",
    "disableBuiltinSkills",
    "autoRejectPermissionRequests",
)


def _settings_from_notes(notes: list) -> dict | None:
    """settings из первой нотификации settings_updated среди уже полученных call()."""
    for params in notes:
        note = params.get("notification") if isinstance(params, dict) else None
        if (
            isinstance(note, dict)
            and note.get("type") == "settings_updated"
            and isinstance(note.get("settings"), dict)
        ):
            return note["settings"]
    return None


def _verify_settings(
    stage: str, reported: object, expected: dict, required: tuple = ()
) -> set:
    """Сверка сообщённых droid настроек с профилем -> множество подтверждённых ключей.

    Сообщённое поле с другим значением (в том числе `1` вместо `true`) - ProbeError; отсутствующее
    поле не ошибка, кроме `required`: его молчание не доказывает профиль и в receipt не попадает.
    """
    confirmed: set = set()
    if not isinstance(reported, dict):
        if required:
            raise ProbeError(f"{stage}: read-back настроек отсутствует")
        return confirmed
    for key, want in expected.items():
        if key not in reported:
            if key in required:
                raise ProbeError(f"{stage}: в read-back нет {key}")
            continue
        got = reported[key]
        if got != want or type(got) is not type(want):
            raise ProbeError(
                f"{stage}: подмена {key}: ожидали {want!r}, получили {got!r}"
            )
        confirmed.add(key)
    return confirmed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _ensure_private(directory: Path) -> None:
    """Каталог обязан быть своим и 0700: права чинятся (в т.ч. у существующих), невозможность — исключение."""
    directory.mkdir(parents=True, exist_ok=True)
    info = os.stat(directory)
    if info.st_uid != os.getuid():
        raise PermissionError(
            f"{directory} принадлежит uid {info.st_uid}, а не текущему пользователю"
        )
    if info.st_mode & 0o077:
        os.chmod(directory, 0o700)


def _ensure_private_chain(directory: Path, workspace: Path) -> None:
    """0700 для directory и его родителей ВНУТРИ workspace (сам workspace и внешние каталоги не трогаются)."""
    root = workspace.resolve()
    target = directory.resolve()
    chain = [target]
    if root in target.parents:
        for parent in target.parents:
            if parent == root:
                break
            chain.append(parent)
    for item in reversed(chain):
        _ensure_private(item)


class _Rpc:
    """Минимальный клиент stream-jsonrpc одного процесса образа (только для проб)."""

    def __init__(self, image: Path, cwd: Path, home: Path):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("BRIDGE_KEY", "DROID_DSH_BRIDGE_KEY")
        }
        env["FACTORY_HOME_OVERRIDE"] = str(home)
        env["DROID_AUTO"] = "off"
        self.proc = subprocess.Popen(
            [
                str(image),
                "exec",
                "--input-format",
                "stream-jsonrpc",
                "--output-format",
                "stream-jsonrpc",
            ],
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=env,
        )
        self.inbox: queue.Queue = queue.Queue()
        self.protocol = ""
        self._next = 0
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        for raw in self.proc.stdout or ():
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("{"):
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if isinstance(msg, dict):
                if not self.protocol and isinstance(
                    msg.get("factoryProtocolVersion"), str
                ):
                    self.protocol = msg["factoryProtocolVersion"]
                self.inbox.put(msg)
        self.inbox.put(None)

    def call(
        self, method: str, params: dict, timeout: float = PROBE_TIMEOUT_S
    ) -> tuple:
        """-> (result, нотификации за время ожидания)."""
        self._next += 1
        rid = f"p{self._next}"
        frame = {
            "type": "request",
            "jsonrpc": "2.0",
            "factoryApiVersion": schema.RPC_API_VERSION,
            "id": rid,
            "method": method,
            "params": params,
        }
        try:
            stdin = self.proc.stdin
            if stdin is None:
                raise ProbeError(f"{method}: stdin образа недоступен")
            stdin.write((json.dumps(frame) + "\n").encode("utf-8"))
            stdin.flush()
        except OSError as exc:
            raise ProbeError(f"{method}: запись в stdin образа не удалась: {exc!r}")
        notes: list = []
        end = time.monotonic() + timeout
        while True:
            try:
                msg = self.inbox.get(timeout=max(0.05, end - time.monotonic()))
            except queue.Empty:
                raise ProbeError(f"{method}: нет ответа за {timeout:g} с")
            if msg is None:
                raise ProbeError(f"{method}: образ завершился до ответа")
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                if msg.get("error") is not None:
                    raise ProbeError(f"{method}: {str(msg['error'])[:200]}")
                result = msg.get("result")
                return (result if isinstance(result, dict) else {}), notes
            if msg.get("method") == "droid.session_notification" and isinstance(
                msg.get("params"), dict
            ):
                notes.append(msg["params"])
            if time.monotonic() > end:
                raise ProbeError(f"{method}: нет ответа за {timeout:g} с")

    def wait_settings(self, timeout: float = 5.0) -> dict:
        """settings из нотификации settings_updated (read-back)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                msg = self.inbox.get(timeout=0.1)
            except queue.Empty:
                continue
            if msg is None:
                break
            raw_params = msg.get("params")
            params = raw_params if isinstance(raw_params, dict) else {}
            raw_note = params.get("notification")
            note = raw_note if isinstance(raw_note, dict) else {}
            settings = note.get("settings")
            if note.get("type") == "settings_updated" and isinstance(settings, dict):
                return settings
        raise ProbeError(
            "update_session_settings: read-back settings_updated не получен"
        )

    @staticmethod
    def _close_quietly(stream: IO[bytes]) -> None:
        try:
            stream.close()
        except OSError:
            pass

    def close(self) -> None:
        if self.proc.stdin is not None:
            self._close_quietly(self.proc.stdin)
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        # stdout закрывается явно (иначе ResourceWarning: unclosed file); читатель после убийства группы видит EOF.
        # Читатель не завершился за join - close() BufferedReader ждал бы его лок, поэтому закрытие уходит в фон.
        self._reader.join(timeout=1.0)
        if self.proc.stdout is not None:
            if self._reader.is_alive():
                threading.Thread(
                    target=self._close_quietly, args=(self.proc.stdout,), daemon=True
                ).start()
            else:
                self._close_quietly(self.proc.stdout)


def _initialize_probe(rpc: _Rpc, cwd: Path, expected: dict) -> tuple[str, set]:
    """Открыть сессию и подтвердить обязательные настройки."""
    result, _ = rpc.call(
        "droid.initialize_session",
        {
            **expected,
            "machineId": "droid-image-probe",
            "cwd": str(cwd),
            "title": "droid-image-probe",
        },
    )
    sid, settings = result.get("sessionId"), result.get("settings")
    if not isinstance(sid, str) or not sid or not isinstance(settings, dict):
        raise ProbeError(
            "spawn: initialize_session без sessionId или с подменой модели"
        )
    confirmed = _verify_settings(
        "spawn",
        settings,
        expected,
        required=("modelId", "reasoningEffort", "autonomyLevel"),
    )
    return sid, confirmed


def _probe_tool_ids(rpc: _Rpc) -> set[str]:
    """Проверить непустой каталог инструментов одной модели."""
    tools, _ = rpc.call("droid.list_tools", {})
    listed = tools.get("tools")
    if not isinstance(listed, list) or not listed:
        raise ProbeError("update: list_tools вернул некорректный каталог")
    if not all(
        isinstance(t, dict) and isinstance(t.get("id"), str) and t["id"] for t in listed
    ):
        raise ProbeError("update: list_tools вернул некорректный каталог")
    return {t["id"] for t in listed}


def _disable_probe_tools(rpc: _Rpc, ids: set[str], expected: dict) -> set:
    """Подтвердить отключение каждого инструмента текущей модели."""
    _, stash = rpc.call(
        "droid.update_session_settings", {"disabledToolIds": sorted(ids)}
    )
    updated = _settings_from_notes(stash)
    if updated is None:
        updated = rpc.wait_settings()
    disabled = updated.get("disabledToolIds")
    if not isinstance(disabled, list) or not ids.issubset(set(map(str, disabled))):
        raise ProbeError("update: read-back не подтвердил отключение tools")
    return _verify_settings("update", updated, expected)


def _probe_model(image: Path, cwd: Path, home: Path, model: str, effort: str) -> tuple:
    """Пройти spawn/update/load одной модели с безусловным закрытием процессов."""
    expected = {
        "modelId": model,
        "reasoningEffort": effort,
        "autonomyLevel": PROBE_AUTONOMY,
        **schema.SETTINGS_PROFILE,
    }
    rpc = _Rpc(image, cwd, home)
    try:
        sid, confirmed = _initialize_probe(rpc, cwd, expected)
        protocol = rpc.protocol
        if not protocol:
            raise ProbeError("spawn: в кадрах droid нет factoryProtocolVersion")
        ids = _probe_tool_ids(rpc)
        confirmed |= _disable_probe_tools(rpc, ids, expected)
    finally:
        rpc.close()
    second = _Rpc(image, cwd, home)
    try:
        loaded, _ = second.call(
            "droid.load_session", {"sessionId": sid, "disableBuiltinSkills": True}
        )
        session = loaded.get("session")
        if not isinstance(session, dict) or not isinstance(
            session.get("messages"), list
        ):
            raise ProbeError("load: load_session не вернул сессию")
        confirmed |= _verify_settings("load", loaded.get("settings"), expected)
    finally:
        second.close()
    return protocol, ids, confirmed


def run_probes(image: Path, workspace: Path) -> dict:
    """Квалифицировать модели и объединить только подтверждённо отключённые tools."""
    runtime = workspace / "runtime"
    home, cwd = runtime / "probe-home", runtime / "probe-cwd"
    _ensure_private_chain(home, workspace)
    _ensure_private_chain(cwd, workspace)
    models = _probe_models()
    facts = [
        _probe_model(image, cwd, home, mid, effort) for mid, effort in models.items()
    ]
    if len({fact[0] for fact in facts}) != 1:
        raise ProbeError("spawn: модели сообщили разные factoryProtocolVersion")
    confirmed = set.intersection(*(fact[2] for fact in facts))
    return {
        "protocol_version": facts[0][0],
        "disabled_tool_ids": sorted(set.union(*(fact[1] for fact in facts))),
        "qualified_models": {mid: sorted(fact[1]) for mid, fact in zip(models, facts)},
        "probes": {name: "ok" for name in schema.RECEIPT_PROBES},
        "readback": {
            "confirmed": sorted(confirmed),
            "not_confirmed_readback": sorted(set(READBACK_KEYS) - confirmed),
        },
    }


def install_image(source: Path, workspace: Path) -> dict:
    """Скопировать образ, пройти пробы, записать receipt; вернуть содержимое receipt."""
    snapshot = source.stat()
    source_sha = _sha256(source)
    runtime = workspace / "runtime" / "droid-image"
    _ensure_private_chain(runtime, workspace)
    tmp = runtime / f".incoming-{os.getpid()}"
    shutil.copyfile(source, tmp)
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    image_sha = _sha256(tmp)
    image_dir = runtime / image_sha
    _ensure_private(image_dir)
    image = image_dir / "droid"
    if image.exists():
        os.chmod(image, 0o700)
    os.replace(tmp, image)
    os.chmod(image, 0o500)
    facts = run_probes(image, workspace)
    receipt = {
        "schema": schema.RECEIPT_SCHEMA,
        "image_path": str(image),
        "image_sha256": image_sha,
        "protocol": {
            "api_version": schema.RPC_API_VERSION,
            "protocol_version": facts["protocol_version"],
        },
        "tools_policy": {
            "policy": schema.TOOLS_POLICY,
            "disabled_tool_ids": facts["disabled_tool_ids"],
            "digest": schema.tools_policy_digest(facts["disabled_tool_ids"]),
        },
        "settings_profile": {
            "profile": schema.SETTINGS_PROFILE,
            "digest": schema.settings_profile_digest(),
            "readback": facts["readback"],
        },
        "probes": facts["probes"],
        "qualified_models": facts["qualified_models"],
        "source": {
            "path": str(source),
            "mtime_ns": snapshot.st_mtime_ns,
            "size": snapshot.st_size,
            "sha256": source_sha,
        },
        "created_at": int(time.time()),
    }
    state = workspace / "state"
    _ensure_private_chain(state, workspace)
    target = state / "droid-binary-receipt.json"
    staging = state / f".receipt-{os.getpid()}.tmp"
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(staging, target)
    return receipt


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="droid_image", description=__doc__.splitlines()[0]
    )
    parser.add_argument(
        "--source",
        default=os.path.expanduser("~/.local/bin/droid"),
        help="глобальный бинарь droid (не изменяется)",
    )
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parent.parent / "workspace"),
        help="workspace моста (runtime/droid-image и state/)",
    )
    args = parser.parse_args(argv)
    source = Path(args.source)
    if not source.is_file() or not os.access(source, os.X_OK):
        sys.stderr.write(
            f"droid_image: источник не найден или не исполняем: {source}\n"
        )
        return 2
    try:
        receipt = install_image(source, Path(args.workspace))
    except ProbeError as exc:
        sys.stderr.write(
            f"droid_image: проба квалификации не пройдена, receipt не записан: {exc}\n"
        )
        return 3
    sys.stdout.write(
        f"image={receipt['image_path']} sha256={receipt['image_sha256']} "
        f"protocol={receipt['protocol']['protocol_version']}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
