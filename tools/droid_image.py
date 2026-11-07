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
from typing import IO, cast

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import receipt_schema as schema  # noqa: E402
from tools.droid_probe_config import (  # noqa: E402
    ProbeError,
    ProbeFacts,
    ProbeTarget,
    get_probe_timeout_s as _get_probe_timeout_s,
    initialize_probe,
    load_droid_probe_targets,
    probe_directories,
    probe_models,
    verify_disk_profile,
)
from core.gateway_execution_policy import permission_frame, require  # noqa: E402

PROBE_AUTONOMY = "high"
_probe_models = (
    probe_models  # Прежняя точка чтения default-effort для внешних потребителей.
)
READBACK_KEYS = (
    "modelId",
    "reasoningEffort",
    "autonomyLevel",
    "interactionMode",
    "disableBuiltinSkills",
    "autoRejectPermissionRequests",
)


def _settings_from_notes(notes: list[dict[str, object]]) -> dict[str, object] | None:
    """settings из первой нотификации settings_updated среди уже полученных call()."""
    for params in notes:
        raw_note = params.get("notification")
        note = cast(dict[str, object], raw_note) if isinstance(raw_note, dict) else {}
        if note.get("type") == "settings_updated" and isinstance(
            note.get("settings"), dict
        ):
            return cast(dict[str, object], note["settings"])
    return None


def _verify_settings(
    stage: str,
    reported: object,
    expected: dict[str, object],
    required: tuple[str, ...] = (),
) -> set[str]:
    """Сверка сообщённых droid настроек с профилем -> множество подтверждённых ключей.

    Сообщённое поле с другим значением (в том числе `1` вместо `true`) - ProbeError; отсутствующее
    поле не ошибка, кроме `required`: его молчание не доказывает профиль и в receipt не попадает.
    """
    confirmed: set[str] = set()
    if not isinstance(reported, dict):
        if required:
            raise ProbeError(f"{stage}: read-back настроек отсутствует")
        return confirmed
    reported = cast(dict[str, object], reported)
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

    def __init__(self, image: Path, cwd: Path, home: Path) -> None:
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("BRIDGE_KEY", "DROID_DSH_BRIDGE_KEY")
        }
        env["FACTORY_HOME_OVERRIDE"] = str(home)
        env["DROID_AUTO"] = "off"
        self.proc: subprocess.Popen[bytes] = subprocess.Popen(
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
        self.inbox: queue.Queue[dict[str, object] | None] = queue.Queue()
        self.protocol: str = ""
        self._next: int = 0
        self._reader: threading.Thread = threading.Thread(
            target=self._read, daemon=True
        )
        self._reader.start()

    def _read(self) -> None:
        for raw in iter(cast(IO[bytes], self.proc.stdout).readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("{"):
                continue
            try:
                msg = cast(object, json.loads(line))
            except ValueError:
                continue
            if isinstance(msg, dict):
                frame = cast(dict[str, object], msg)
                protocol = frame.get("factoryProtocolVersion")
                if not self.protocol and isinstance(protocol, str):
                    self.protocol = protocol
                self.inbox.put(frame)
        self.inbox.put(None)

    def call(
        self, method: str, params: dict[str, object], timeout: float | None = None
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        """-> (result, нотификации за время ожидания)."""
        timeout = _get_probe_timeout_s() if timeout is None else timeout
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
            _ = stdin.write((json.dumps(frame) + "\n").encode("utf-8"))
            stdin.flush()
        except OSError as exc:
            raise ProbeError(f"{method}: запись в stdin образа не удалась: {exc!r}")
        notes: list[dict[str, object]] = []
        end = time.monotonic() + timeout
        while True:
            try:
                msg = self.inbox.get(timeout=max(0.05, end - time.monotonic()))
            except queue.Empty:
                raise ProbeError(f"{method}: нет ответа за {timeout:g} с")
            if msg is None:
                raise ProbeError(f"{method}: образ завершился до ответа")
            require(
                not permission_frame(msg),
                ProbeError("permission request during qualification"),
            )
            if msg.get("id") == rid and ("result" in msg or "error" in msg):
                if msg.get("error") is not None:
                    raise ProbeError(f"{method}: {str(msg['error'])[:200]}")
                result = msg.get("result")
                return (
                    cast(dict[str, object], result) if isinstance(result, dict) else {}
                ), notes
            if msg.get("method") == "droid.session_notification" and isinstance(
                msg.get("params"), dict
            ):
                notes.append(cast(dict[str, object], msg["params"]))
            if time.monotonic() > end:
                raise ProbeError(f"{method}: нет ответа за {timeout:g} с")

    def wait_settings(self, timeout: float = 5.0) -> dict[str, object]:
        """settings из нотификации settings_updated (read-back)."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            try:
                msg = self.inbox.get(timeout=0.1)
            except queue.Empty:
                continue
            if msg is None:
                break
            require(
                not permission_frame(msg),
                ProbeError("permission request during settings update"),
            )
            raw_params = msg.get("params")
            params = (
                cast(dict[str, object], raw_params)
                if isinstance(raw_params, dict)
                else {}
            )
            raw_note = params.get("notification")
            note = (
                cast(dict[str, object], raw_note) if isinstance(raw_note, dict) else {}
            )
            settings = note.get("settings")
            if note.get("type") == "settings_updated" and isinstance(settings, dict):
                return cast(dict[str, object], settings)
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
            _ = self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(self.proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        try:
            _ = self.proc.wait(timeout=3)
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


def _initialize_probe(
    rpc: _Rpc, cwd: Path, expected: dict[str, object]
) -> tuple[str, set[str]]:
    """Открыть сессию и подтвердить обязательные настройки."""
    return initialize_probe(rpc.call, cwd, expected, _verify_settings)


def _probe_tool_ids(rpc: _Rpc) -> set[str]:
    """Проверить непустой каталог инструментов одной модели."""
    tools, _ = rpc.call("droid.list_tools", {})
    listed = tools.get("tools")
    error = ProbeError("update: list_tools вернул некорректный каталог")
    require(all((isinstance(listed, list), bool(listed))), error)
    entries = cast(list[object], listed)
    for entry in entries:
        require(isinstance(entry, dict), error)
        tool = cast(dict[str, object], entry)
        require(isinstance(tool.get("id"), str), error)
        require(bool(tool["id"]), error)
    return {cast(str, cast(dict[str, object], t)["id"]) for t in entries}


def _disable_probe_tools(
    rpc: _Rpc, ids: set[str], expected: dict[str, object]
) -> set[str]:
    """Подтвердить отключение каждого инструмента текущей модели."""
    _, stash = rpc.call(
        "droid.update_session_settings", {"disabledToolIds": sorted(ids)}
    )
    updated = _settings_from_notes(stash)
    if updated is None:
        updated = rpc.wait_settings()
    disabled = updated.get("disabledToolIds")
    error = ProbeError("update: read-back не подтвердил отключение tools")
    require(isinstance(disabled, list), error)
    require(ids.issubset(set(map(str, cast(list[object], disabled)))), error)
    return _verify_settings("update", updated, expected)


def _probe_model(
    image: Path, cwd: Path, home: Path, model: str, effort: str
) -> tuple[str, set[str], set[str]]:
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
            cast(dict[str, object], session).get("messages"), list
        ):
            raise ProbeError("load: load_session не вернул сессию")
        confirmed |= _verify_settings("load", loaded.get("settings"), expected)
    finally:
        second.close()
    return protocol, ids, confirmed


def run_probes(image: Path, workspace: Path) -> ProbeFacts:
    """Квалифицировать модели и объединить только подтверждённо отключённые tools."""
    runtime = workspace / "runtime"
    home, cwd = runtime / "probe-home", runtime / "probe-cwd"
    targets = load_droid_probe_targets(
        Path(
            os.environ.get("DROID_DSH_BRIDGE_FLEET")
            or Path(__file__).resolve().parents[1] / "fleet.json"
        )
    )
    facts: list[tuple[str, set[str], set[str]]] = []
    for target in targets:
        with probe_directories(
            home, cwd, workspace, _ensure_private_chain
        ) as settings_path:
            facts.append(_probe_model(image, cwd, home, target.model, target.effort))
            verify_disk_profile(settings_path, _verify_settings)
    protocol, *_ = facts[0]
    require(
        not {fact[0] for fact in facts}.difference((protocol,)),
        ProbeError("spawn: модели сообщили разные factoryProtocolVersion"),
    )
    return _probe_facts(targets, facts)


def _probe_facts(
    targets: tuple[ProbeTarget, ...], facts: list[tuple[str, set[str], set[str]]]
) -> ProbeFacts:
    """Собрать JSON-совместимое доказательство всех квалифицированных пар."""
    confirmed = facts[0][2].intersection(*(fact[2] for fact in facts))
    catalogs: dict[str, set[str]] = {}
    missing: dict[str, set[str]] = {}
    for target, (_, ids, readback) in zip(targets, facts):
        catalogs.setdefault(target.model, set()).update(ids)
        missing.setdefault(target.model, set()).update(
            set(schema.SETTINGS_PROFILE) - readback
        )
    return {
        "protocol_version": facts[0][0],
        "disabled_tool_ids": sorted(set[str]().union(*(fact[1] for fact in facts))),
        "qualified_models": {mid: sorted(ids) for mid, ids in catalogs.items()},
        "not_confirmed_readback_by_model": {
            mid: sorted(keys) for mid, keys in missing.items()
        },
        "probes": {name: "ok" for name in schema.RECEIPT_PROBES},
        "readback": {
            "confirmed": sorted(confirmed),
            "not_confirmed_readback": sorted(set(READBACK_KEYS) - confirmed),
        },
    }


def install_image(source: Path, workspace: Path) -> schema.DroidReceipt:
    """Скопировать образ, пройти пробы, записать receipt; вернуть содержимое receipt."""
    snapshot = source.stat()
    source_sha = _sha256(source)
    runtime = workspace / "runtime" / "droid-image"
    _ensure_private_chain(runtime, workspace)
    tmp = runtime / f".incoming-{os.getpid()}"
    _ = shutil.copyfile(source, tmp)
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
    receipt: schema.DroidReceipt = {
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
            "digest": schema.tools_policy_digest(
                facts["disabled_tool_ids"], facts["qualified_models"]
            ),
        },
        "settings_profile": {
            "profile": schema.SETTINGS_PROFILE,
            "digest": schema.settings_profile_digest(),
            "readback": facts["readback"],
        },
        "probes": facts["probes"],
        "qualified_models": facts["qualified_models"],
        "not_confirmed_readback_by_model": facts["not_confirmed_readback_by_model"],
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="droid_image", description=__doc__.splitlines()[0]
    )
    _ = parser.add_argument(
        "--source",
        default=os.path.expanduser("~/.local/bin/droid"),
        help="глобальный бинарь droid (не изменяется)",
    )
    _ = parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parent.parent / "workspace"),
        help="workspace моста (runtime/droid-image и state/)",
    )
    args = parser.parse_args(argv)
    source = Path(cast(str, args.source))
    if not source.is_file() or not os.access(source, os.X_OK):
        _ = sys.stderr.write(
            f"droid_image: источник не найден или не исполняем: {source}\n"
        )
        return 2
    try:
        receipt = install_image(source, Path(cast(str, args.workspace)))
    except ProbeError as exc:
        _ = sys.stderr.write(
            f"droid_image: проба квалификации не пройдена, receipt не записан: {exc}\n"
        )
        return 3
    protocol = receipt["protocol"]
    _ = sys.stdout.write(
        f"image={receipt['image_path']} sha256={receipt['image_sha256']} "
        + f"protocol={protocol['protocol_version']}\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
