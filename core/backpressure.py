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
) -> int:
    """Байтовый предел слитого чанка; 0 — слияние запрещено (fail-close).

    Отсутствующее, нулевое, отрицательное или ошибочное значение не даёт
    безлимит: безопасный дефолт может прийти только из dynamic_config.
    """
    env = os.environ if environ is None else environ
    if _LIMIT_NAME in env:
        raw: object = env.get(_LIMIT_NAME)
    else:
        config = dynamic_config if dynamic_config is not None else _loaded_dynamic_config()
        raw = _config_value(config, _LIMIT_NAME)
    if isinstance(raw, bool) or raw is None:
        return 0
    try:
        value = int(str(raw).strip()) if isinstance(raw, str) else int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    return value if value > 0 else 0


def _exceeds_limit(text: str, limit: int) -> bool:
    """Проверка байтового предела; неположительный предел запрещает слияние."""
    if limit <= 0:
        return True
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


def _merge_new_into_tail(dq: Any, item: object, limit: int) -> bool:
    """Дописать дельту в хвостовой чанк deque; вызывающий держит mutex."""
    if not dq or not _is_text_pair(item) or not _is_text_pair(dq[-1]):
        return False
    last = dq[-1]
    if last[0] != item[0]:  # type: ignore[index]
        return False
    merged = _merged_text(last[1], item[1])  # type: ignore[index]
    if _exceeds_limit(merged, limit):
        return False
    dq[-1] = (last[0], merged)
    return True


def _coalesce_adjacent(dq: Any, limit: int) -> bool:
    """Слить соседние чанки deque, освобождая слот; вызывающий держит mutex."""
    for index in range(len(dq) - 1):
        first, second = dq[index], dq[index + 1]
        if _is_text_pair(first) and _is_text_pair(second) and first[0] == second[0]:
            merged = _merged_text(first[1], second[1])
            if _exceeds_limit(merged, limit):
                continue
            dq[index] = (first[0], merged)
            del dq[index + 1]
            return True
    return False


class CoalescingQueue(queue.Queue):
    """Очередь со слиянием контент-дельт атомарно под собственным mutex.

    При выключенном фичефлаге поведение тождественно queue.Queue.
    Флаг и лимит перечитываются на каждый вызов — kill-switch без рестарта.
    """

    def __init__(
        self,
        maxsize: int = 0,
        dynamic_config: object = None,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(maxsize=maxsize)
        self._dynamic_config = dynamic_config
        self._environ = environ

    def _append_locked(self, item: object) -> None:
        """Добавление элемента; вызывающий держит mutex, слот свободен."""
        self.queue.append(item)
        self.unfinished_tasks += 1
        self.not_empty.notify()

    def _drop_locked(self, index: int) -> None:
        """Удаление элемента с коррекцией счётчика задач под mutex."""
        del self.queue[index]
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            self.all_tasks_done.notify_all()

    def _coalesce_locked(self, item: object, limit: int) -> bool:
        """Попытка размещения при полной очереди; вызывающий держит self.mutex."""
        dq = self.queue
        if self.maxsize <= 0 or len(dq) < self.maxsize:
            self._append_locked(item)
            return True
        if _kind_of(item) in _COALESCIBLE_KINDS:
            return True
        if _merge_new_into_tail(dq, item, limit):
            return True
        if _coalesce_adjacent(dq, limit):
            self.unfinished_tasks -= 1
            if self.unfinished_tasks == 0:
                self.all_tasks_done.notify_all()
            self._append_locked(item)
            return True
        for index in range(len(dq)):
            kind = _kind_of(dq[index])
            if kind in _TERMINAL_KINDS:
                continue
            if kind in _COALESCIBLE_KINDS:
                self._drop_locked(index)
                self._append_locked(item)
                return True
        return False

    def put_nowait(self, item: object) -> None:  # type: ignore[override]
        """Неблокирующая запись; слияние только при включённом фичефлаге."""
        try:
            return super().put_nowait(item)
        except queue.Full:
            pass
        if not stream_content_recovery_enabled(self._dynamic_config, self._environ):
            raise queue.Full
        limit = _max_merged_bytes(self._dynamic_config, self._environ)
        with self.mutex:
            if self._coalesce_locked(item, limit):
                return None
        raise queue.Full

    def put_preserving(
        self,
        item: object,
        dynamic_config: object = None,
        environ: Mapping[str, str] | None = None,
    ) -> bool:
        """Явная публикация с сохранением контента; флаг проверяет вызывающий."""
        try:
            super().put_nowait(item)
            return True
        except queue.Full:
            pass
        config = dynamic_config if dynamic_config is not None else self._dynamic_config
        env = environ if environ is not None else self._environ
        limit = _max_merged_bytes(config, env)
        with self.mutex:
            return self._coalesce_locked(item, limit)


def publish_preserving(
    target: queue.Queue,
    item: object,
    dynamic_config: object = None,
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Публикация без потери контента; слияние умеет только CoalescingQueue.

    Для обычной очереди — прежний fail-close без извлечения элементов:
    coalescible-уведомление отбрасывается, остальное даёт False.
    """
    if isinstance(target, CoalescingQueue):
        return target.put_preserving(item, dynamic_config, environ)
    try:
        target.put_nowait(item)
        return True
    except queue.Full:
        return _kind_of(item) in _COALESCIBLE_KINDS


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
