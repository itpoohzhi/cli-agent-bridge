import queue


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
