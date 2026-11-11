import os
import queue
import sys
from collections.abc import Mapping
from typing import Any

_FLAG_NAME = "BRIDGE_STREAM_CONTENT_RECOVERY_ENABLED"
_LIMIT_NAME = "BRIDGE_STREAM_CONTENT_RECOVERY_MAX_MERGED_BYTES"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_COALESCIBLE_KINDS = frozenset({"heartbeat", "keepalive", "ping", "progress", "status"})
_TERMINAL_KINDS = frozenset({"done", "error", "live_invalidated", "pump_error", "stream_error"})
_CONTENT_KINDS = frozenset({"content"})


def _truthy(value: object) -> bool:
    """Правдивость значения фичефлага из env или dynamic_config."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in _TRUE_VALUES
    return False


def _config_value(config: object, name: str = _FLAG_NAME) -> object:
    """Значение параметра из mapping/объекта/модуля dynamic_config, если есть."""
    if config is None:
        return None
    if isinstance(config, Mapping):
        if name in config:
            return config.get(name)
        return config.get(name.lower())
    methods = (
        ("get_bool", "get", "get_value", "lookup")
        if name == _FLAG_NAME
        else ("get", "get_value", "lookup")
    )
    for attr in methods:
        fn = getattr(config, attr, None)
        if callable(fn):
            try:
                return fn(name)
            except Exception:
                pass
    for attr in ("config", "CONFIG", "data", "values"):
        nested = getattr(config, attr, None)
        if nested is not None and nested is not config:
            value = _config_value(nested, name)
            if value is not None:
                return value
    if hasattr(config, name):
        return getattr(config, name)
    return getattr(config, name.lower(), None)


def _loaded_dynamic_config() -> object:
    """Уже загруженный dynamic_config без импорта в горячем пути."""
    for module_name in ("core.dynamic_config", "dynamic_config"):
        candidate = sys.modules.get(module_name)
        if candidate is not None:
            return candidate
    return None


def _max_merged_bytes(
    dynamic_config: object = None,
    environ: Mapping[str, str] | None = None,
) -> int | None:
    """Байтовый предел слитого чанка; None — прежнее поведение без предела."""
    env = os.environ if environ is None else environ
    if _LIMIT_NAME in env:
        raw: object = env.get(_LIMIT_NAME)
    else:
        config = dynamic_config if dynamic_config is not None else _loaded_dynamic_config()
        raw = _config_value(config, _LIMIT_NAME)
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = int(str(raw).strip()) if isinstance(raw, str) else int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _exceeds_limit(text: str, limit: int | None) -> bool:
    """Проверка байтового предела слитого текста."""
    if limit is None:
        return False
    try:
        return len(text.encode("utf-8")) > limit
    except UnicodeEncodeError:
        return len(text) > limit


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
        candidate = _loaded_dynamic_config()
        if _config_value(candidate) is not None:
            config = candidate
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
    """Дельта всегда дописывается; у формата (kind, text) snapshot-признака нет."""
    return old + new


def _is_text_pair(item: object) -> bool:
    return (
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], str)
        and item[0] in _CONTENT_KINDS
    )


def _merge_new_into_tail(items: list[Any], item: object, limit: int | None) -> bool:
    """Дописать дельту в хвостовой чанк того же вида в снятом списке."""
    if not items or not _is_text_pair(item) or not _is_text_pair(items[-1]):
        return False
    last = items[-1]
    if last[0] != item[0]:  # type: ignore[index]
        return False
    merged = _merged_text(last[1], item[1])  # type: ignore[index]
    if _exceeds_limit(merged, limit):
        return False
    items[-1] = (last[0], merged)
    return True


def _coalesce_adjacent(items: list[Any], limit: int | None) -> bool:
    """Слить соседние чанки одного вида в снятом списке, освобождая слот."""
    for index in range(len(items) - 1):
        first, second = items[index], items[index + 1]
        if _is_text_pair(first) and _is_text_pair(second) and first[0] == second[0]:
            merged = _merged_text(first[1], second[1])
            if _exceeds_limit(merged, limit):
                continue
            items[index] = (first[0], merged)
            del items[index + 1]
            return True
    return False


def _requeue(target: queue.Queue, items: list[Any]) -> None:
    """Вернуть снятые элементы только публичным API очереди."""
    for existing in items:
        try:
            target.put_nowait(existing)
        except queue.Full:
            target.put(existing)


def publish_preserving(
    target: queue.Queue,
    item: object,
    dynamic_config: object = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Публикация без потери контента при полной очереди, только публичный API.

    Сначала обычный put_nowait. При переполнении элементы снимаются через
    get_nowait/task_done, дельты сливаются в списке в пределах байтового
    лимита, освобождённый слот сразу занимает item, затем всё возвращается
    через put_nowait. Terminal/error/content не вытесняются; если место
    освободить нельзя — False, прежний fail-close вызывающей стороны.
    """
    try:
        target.put_nowait(item)
        return True
    except queue.Full:
        pass
    if _kind_of(item) in _COALESCIBLE_KINDS:
        return True
    limit = _max_merged_bytes(dynamic_config, environ)
    items: list[Any] = []
    while True:
        try:
            existing = target.get_nowait()
        except queue.Empty:
            break
        items.append(existing)
        target.task_done()
    maxsize = getattr(target, "maxsize", 0)
    if not isinstance(maxsize, int) or maxsize <= 0 or len(items) < maxsize:
        items.append(item)
        _requeue(target, items)
        return True
    if _merge_new_into_tail(items, item, limit):
        _requeue(target, items)
        return True
    if _coalesce_adjacent(items, limit):
        items.append(item)
        _requeue(target, items)
        return True
    for index, existing in enumerate(items):
        if _kind_of(existing) in _COALESCIBLE_KINDS:
            del items[index]
            items.append(item)
            _requeue(target, items)
            return True
    _requeue(target, items)
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
