"""Pure streaming FSM for separating reasoning tags from visible content."""

from dataclasses import dataclass
from enum import Enum, auto


class ParserState(Enum):
    OUTSIDE = auto()
    IN_OPEN_TAG = auto()
    IN_THINKING = auto()
    IN_CLOSE_TAG = auto()
    FINISHED = auto()


@dataclass
class TransitionResult:
    content: str = ""
    reasoning: str = ""


class ReasoningFSM:
    """Parse reasoning blocks, including nested blocks, without performing I/O.

    ``prefix`` and ``suffix`` are complete opening and closing delimiters.
    Recognized delimiters are omitted from output. Unmatched closing tags
    outside reasoning are ordinary content. Incomplete delimiters are emitted
    literally by ``flush()``, into whichever channel was active.

    For overlapping delimiters, the first complete delimiter wins. These
    rules depend only on characters, never on chunk boundaries.
    """

    def __init__(
        self, prefix: str = "<think>", suffix: str = "</think>"
    ) -> None:
        if not prefix or not suffix:
            raise ValueError("Reasoning delimiters must be nonempty")
        if prefix == suffix:
            raise ValueError("Opening and closing delimiters must differ")
        self._prefix = prefix
        self._suffix = suffix
        self.reset()

    def reset(self) -> None:
        """Discard buffered input and begin an independent stream."""
        self.state = ParserState.OUTSIDE
        self._partial = ""
        self._depth = 0

    @property
    def is_in_thinking(self) -> bool:
        """Whether an unfinished stream currently has an open reasoning block."""
        return self._depth > 0 and self.state is not ParserState.FINISHED

    def feed(self, chunk: str) -> list[TransitionResult]:
        """Consume a chunk, retaining only a possible incomplete delimiter.

        Feeding after finalization requires an explicit ``reset()``.
        """
        if self.state is ParserState.FINISHED:
            raise ValueError("Cannot feed a finished parser; call reset()")
        content: list[str] = []
        reasoning: list[str] = []
        for character in chunk:
            self._partial += character
            self._consume(content, reasoning)
        return self._result(content, reasoning)

    def flush(self) -> list[TransitionResult]:
        """Emit an incomplete delimiter literally and finalize; idempotent."""
        if self.state is ParserState.FINISHED:
            return []
        content: list[str] = []
        reasoning: list[str] = []
        target = reasoning if self._depth else content
        target.append(self._partial)
        self._partial = ""
        self.state = ParserState.FINISHED
        return self._result(content, reasoning)

    def _active_tags(self) -> tuple[tuple[str, int], ...]:
        if self._depth:
            return ((self._prefix, 1), (self._suffix, -1))
        return ((self._prefix, 1),)

    def _consume(self, content: list[str], reasoning: list[str]) -> None:
        while self._partial:
            tags = self._active_tags()
            match = next(
                (delta for tag, delta in tags if self._partial == tag),
                None,
            )
            if match is not None:
                self._depth += match
                self._partial = ""
                break
            if any(tag.startswith(self._partial) for tag, _ in tags):
                break
            target = reasoning if self._depth else content
            target.append(self._partial[0])
            self._partial = self._partial[1:]
        self._update_state()

    def _update_state(self) -> None:
        if not self._partial:
            self.state = (
                ParserState.IN_THINKING if self._depth else ParserState.OUTSIDE
            )
        elif self._prefix.startswith(self._partial):
            self.state = ParserState.IN_OPEN_TAG
        else:
            self.state = ParserState.IN_CLOSE_TAG

    @staticmethod
    def _result(
        content: list[str], reasoning: list[str]
    ) -> list[TransitionResult]:
        result = TransitionResult(
            content="".join(content),
            reasoning="".join(reasoning),
        )
        return [result] if result.content or result.reasoning else []
