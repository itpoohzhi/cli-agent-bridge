import importlib
import os
import queue
from collections.abc import Mapping
from typing import Any

_FLAG_NAME = "BRIDGE_STREAM_CONTENT_RECOVERY_ENABLED"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_COALESCIBLE_KINDS = frozenset({"heartbeat", "keepalive", "ping", "progress", "status"})
_TERMINAL_KINDS = frozenset({"done", "error", "live_invalidated", "pump_error", "stream_error"})


def _truthy(value: object) -> bool:
    """Правдивость значения фичефлага из env или dynamic_config."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_VALUES
    return False


def _config_value(config: object) -> object:
    """Значение флага из mapping/объекта/модуля dynamic_config, если есть."""
    if config is None:
        return None
    if isinstance(config, Mapping):
        if _FLAG_NAME in config:
            return config.get(_FLAG_NAME)
        return config.get(_FLAG_NAME.lower())
    for attr in ("get_bool", "get", "get_value", "lookup"):
        fn = getattr(config, attr, None)
        if callable(fn):
            try:
                return fn(_FLAG_NAME)
            except Exception:
                pass
    for attr in ("config", "CONFIG", "data", "values"):
        nested = getattr(config, attr, None)
        if nested is not None and nested is not config:
            value = _config_value(nested)
            if value is not None:
                return value
    if hasattr(config, _FLAG_NAME):
        return getattr(config, _FLAG_NAME)
    return getattr(config, _FLAG_NAME.lower(), None)


def stream_content_recovery_enabled(
    dynamic_config: object = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Фичефлаг сохранения контента стрима при переполнении очереди.

    env имеет приоритет и служит kill-switch; иначе читается переданный
    dynamic_config либо одноимённый модуль, если он есть в проекте.
    Значение перечитывается на каждый вызов — рестарт не требуется.
    """
    env = os.environ if environ is None else environ
    if _FLAG_NAME in env:
        return _truthy(env.get(_FLAG_NAME))
    config = dynamic_config
    if config is None:
        for module_name in ("core.dynamic_config", "dynamic_config"):
            try:
                candidate = importlib.import_module(module_name)
            except Exception:
                continue
            if _config_value(candidate) is not None:
                config = candidate
                break
    return _truthy(_config_value(config))


def _kind_of(item: object) -> str:
    """Вид элемента очереди: первый элемент tuple или поля kind/type."""
    if isinstance(item, tuple) and item and isinstance(item[0], str):
        return item[0]
    if isinstance(item, Mapping):
        kind = item.get("kind") or item.get("type")
        return kind if isinstance(kind, str) else ""
    return ""


def _merged_text(old: str, new: str) -> str:
    """Слияние монотонных текстов: полный snapshot заменяет, дельта дописывается."""
    if new.startswith(old):
        return new
    if old.startswith(new):
        return old
    return old + new


def _is_text_pair(item: object) -> bool:
    return (
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], str)
        and item[0] not in _TERMINAL_KINDS
        and item[0] not in _COALESCIBLE_KINDS
    )


def _merge_new_locked(items: Any, item: object) -> bool:
    """Дописать новый чанк в хвостовой чанк того же вида; очередь под mutex."""
    if not items or not _is_text_pair(item) or not _is_text_pair(items[-1]):
        return False
    last = items[-1]
    if last[0] != item[0]:  # type: ignore[index]
        return False
    items[-1] = (last[0], _merged_text(last[1], item[1]))  # type: ignore[index]
    return True


def _coalesce_adjacent_locked(items: Any) -> bool:
    """Слить соседние чанки одного вида, освобождая слот без потери текста."""
    for index in range(len(items) - 1):
        first, second = items[index], items[index + 1]
        if _is_text_pair(first) and _is_text_pair(second) and first[0] == second[0]:
            items[index] = (first[0], _merged_text(first[1], second[1]))
            del items[index + 1]
            return True
    return False


def publish_preserving(target: queue.Queue, item: object) -> bool:
    """Публикация без потери монотонного контента при полной очереди.

    Сначала обычный put_nowait. При переполнении: новый чанк сливается в
    хвостовой того же вида, соседние чанки коалесцируются ради места под
    terminal/error, вытесняются только коалесцируемые уведомления.
    Terminal/error/content не вытесняются; если место освободить нельзя —
    False, и вызывающая сторона идёт прежним fail-close путём.
    """
    kind = _kind_of(item)
    for _ in range(3):
        try:
            target.put_nowait(item)
            return True
        except queue.Full:
            pass
        if kind in _COALESCIBLE_KINDS:
            return True
        mutex = getattr(target, "mutex", None)
        items = getattr(target, "queue", None)
        if mutex is None or items is None:
            return False
        freed = False
        with mutex:
            if _merge_new_locked(items, item):
                return True
            if _coalesce_adjacent_locked(items):
                freed = True
            else:
                for index, existing in enumerate(list(items)):
                    if _kind_of(existing) in _COALESCIBLE_KINDS:
                        del items[index]
                        freed = True
                        break
        if not freed:
            return False
    return False


class BridgeBackpressureError(RuntimeError):
    pass


class BoundedBridgeWriteQueue:
    def __init__(self, maxsize: int = 128) -> None:
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)

    def put(self, item, block: bool = True, timeout: float | None = None) -> None:
        try:
            self._queue.put(item, block=block, timeout=timeout)
        except queue.Full as exc:
            raise BridgeBackpressureError("bridge write queue is full") from exc

    def get(self, block: bool = True, timeout: float | None = None):
        return self._queue.get(block=block, timeout=timeout)

    def put_nowait(self, item) -> None:
        self.put(item, block=False)

    def get_nowait(self):
        return self.get(block=False)

    def qsize(self) -> int:
        return self._queue.qsize()

    def empty(self) -> bool:
        return self._queue.empty()

    def full(self) -> bool:
        return self._queue.full()

    def task_done(self) -> None:
        self._queue.task_done()

    def join(self) -> None:
        self._queue.join()
