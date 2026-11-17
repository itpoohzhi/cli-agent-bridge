"""Чистая политика восстановления по доказанной причинной связи событий."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import html
import re
import unicodedata
from urllib.parse import unquote_plus


def normalize_error_identity(text: str | None) -> str:
    """Нормализует только переводы строк и внешние пробелы полного сообщения."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def error_identity_digest(text: str | None) -> str:
    """Возвращает SHA-256 полной нормализованной строки, для пустой — пустоту."""
    normalized = normalize_error_identity(text)
    return sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


_SAFETY_MARKERS: tuple[str, ...] = (
    "content safety", "safety filter", "safety: request rejected", "content policy",
    "policy violation", "policy rejection", "safety policy", "safety violation",
    "policy_violation", "content_policy_violation", "safety_violation",
    "content_filter", "safety_check", "safety_policy", "refusal",
    "content_safety", "safety_filter", "prohibited_content", "recitation", "fatal_safety_error",
)
_FATAL_FINISH_FRAGMENTS: tuple[str, ...] = (
    "safety", "content_filter", "prohibited", "recitation", "refusal", "blocklist",
)
# Голова клаузы «safety»: начало строки либо структурный разделитель; проза
# вида "thread safety" сюда не попадает — нужен разделитель прямо перед словом.
_SAFETY_HEAD_RE: re.Pattern[str] = re.compile(r"(?:^|[:;,(\[]\s*)safety(?![\w-])")
_BLOCK_QUOTED_NEUTRAL: tuple[str, ...] = (
    "", "null", "none", "unspecified", "block_reason_unspecified",
)
_BLOCK_TOKEN_NEUTRAL: tuple[str, ...] = (*_BLOCK_QUOTED_NEUTRAL, "[]", "{}")


def _block_value_is_fatal(rest: str) -> bool:
    """Значение blockReason: нейтрально, только если оно пусто/neutral и без опасных данных."""
    m_quoted = re.match(r"""^\s*["']([^"']*)["'](?:\s*([^\s,;}\]\)]+))?""", rest)
    if m_quoted:
        inner = m_quoted.group(1).strip().lower()
        extra = m_quoted.group(2)
        if bool(extra):
            return True
        return inner not in _BLOCK_QUOTED_NEUTRAL
    m_unquoted = re.match(r"""^\s*((?:\[\s*\]|\{\s*\})[^,;}\]\)\r\n]*|[^,;}\]\)\r\n]+)""", rest)
    if not m_unquoted:
        return False
    raw_token = m_unquoted.group(1).strip().lower()
    if re.fullmatch(r"""\[\s*\]|\{\s*\}""", raw_token):
        return False
    return raw_token not in _BLOCK_TOKEN_NEUTRAL


def _has_fatal_finish_reason(reasons: list[str]) -> bool:
    """Фатальный finishReason по фрагменту enum, в том числе префиксному (FINISH_REASON_*)."""
    return any(fragment in reason for reason in reasons for fragment in _FATAL_FINISH_FRAGMENTS)


def meta_pair_is_fatal(key: str, value: object) -> bool:
    """Структурная классификация пары метаданных остановки без склейки в строку."""
    name = key.lower()
    if name == "depth_exceeded":
        return True
    if name in ("block_reason", "blockreason"):
        return str(value).strip().lower() not in _BLOCK_TOKEN_NEUTRAL
    text = str(value).lower()
    if name in ("finish_reason", "finishreason", "stop_reason", "stopreason"):
        return any(fragment in text for fragment in _FATAL_FINISH_FRAGMENTS)
    return is_fatal_safety_error(str(value))


def _normalize_safety_unicode(text: str) -> str:
    """Убрать Unicode-маскировку, не нормализуя ASCII-дампы."""
    if text.isascii():
        return text
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if unicodedata.category(c) not in ("Mn", "Mc", "Me", "Cf"))
    return unicodedata.normalize("NFKC", text)


def is_fatal_safety_error(text: str | None) -> bool:
    """Распознаёт отказ защитных механизмов: такой ход не восстанавливается."""
    cur = text or ""
    for _ in range(32):
        prev = cur
        if "%" in cur:
            cur = unquote_plus(cur)
        if "&" in cur:
            cur = html.unescape(cur)
        if "\\u" in cur:
            cur = re.sub(r"\\+u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), cur)
        if "\\U" in cur:
            if any(int(code, 16) > 0x10FFFF for code in re.findall(r"\\+U([0-9a-fA-F]{8})", cur)):
                return True
            cur = re.sub(r"\\+U([0-9a-fA-F]{8})", lambda m: chr(int(m.group(1), 16)), cur)
        if "\\" in cur:
            cur = re.sub(r"\\+x([0-9a-fA-F]{2})", lambda m: chr(int(m.group(1), 16)), cur)
            cur = re.sub(r"\\+([0-7]{3})", lambda m: chr(int(m.group(1), 8)), cur)
            cur = cur.replace('\\"', '"').replace("\\'", "'")
        cur = _normalize_safety_unicode(cur)
        if cur == prev:
            break
    else:
        if html.unescape(cur) != cur or re.search(r"%[0-9a-fA-F]{2}|&#x?[0-9a-fA-F]+;|\\+[uUx0-7]", cur):
            return True  # Неразрешённое остаточное кодирование: fail-closed.
    lowered = cur.replace("+", " ").casefold()
    has_block = any(
        _block_value_is_fatal(lowered[found.end():])
        for found in re.finditer(r"""\b(?:block_reason|blockreason)\b["\x27]?\s*[:=]\s*""", lowered)
    )
    finish_reasons = re.findall(r"""\b(?:finish_reason|finishreason|stop_reason|stopreason)\b["']?\s*[:=]\s*["']?([\w-]+)""", lowered)
    return (
        any(marker in lowered for marker in _SAFETY_MARKERS)
        or bool(_SAFETY_HEAD_RE.search(lowered))
        or has_block
        or _has_fatal_finish_reason(finish_reasons)
    )


@dataclass(frozen=True)
class CausalErrorIdentity:
    """Скалярная идентичность ошибки без хранения исходного текста."""

    seq: int
    attempt: int
    sha256: str
    length: int


@dataclass(frozen=True)
class CausalRecoveryConfig:
    """Переключатели, метка вызова и признак невосстановимого отказа защиты."""

    master_self_heal: bool
    causal_recovery_enabled: bool
    attempt: int
    is_fatal_safety: bool = False


@dataclass(frozen=True)
class CausalErrorFacts:
    """Структурированное происхождение ошибки и полное эхо результата."""

    identity: CausalErrorIdentity
    error_from_structured_record: bool
    result_status: str
    result_error_sha256: str


@dataclass(frozen=True)
class CausalCompletionFacts:
    """Финальный completion и его причинная позиция в попытке."""

    last_completion_seq: int
    completion_attempt: int
    completion_done_without_tools: bool
    has_final_text: bool


@dataclass(frozen=True)
class CausalDrainFacts:
    """Доказательства полного drain и остановки его производителя."""

    drain_complete: bool
    explicit_drain_complete: bool
    producer_stopped: bool


@dataclass(frozen=True)
class CausalProcessFacts:
    """Подтверждённый выход процесса, код выхода и фатальные признаки."""

    process_exited: bool
    returncode: int | None
    has_fatal_error: bool


@dataclass(frozen=True)
class CausalTerminalFacts:
    """Состояние текущего хвоста, не история ранее завершённых инструментов."""

    drain: CausalDrainFacts
    process: CausalProcessFacts
    tool_status: str
    has_late_error_or_open_step: bool


@dataclass(frozen=True)
class CausalOutcomeInput:
    """Замороженные группы фактов; каждый конструктор имеет не более 5 аргументов."""

    config: CausalRecoveryConfig
    error: CausalErrorFacts
    completion: CausalCompletionFacts
    terminal: CausalTerminalFacts


@dataclass(frozen=True)
class CausalOutcomeDecision:
    """Согласованное решение без исходных сообщений и независимых флагов."""

    recovered: bool
    outcome_mode: str
    reason: str
    detail: str

    @property
    def allow_reconcile(self) -> bool:
        """Разрешает реконсиляцию только после доказанного восстановления."""
        return self.recovered

    @property
    def clear_error(self) -> bool:
        """Снимает ошибку только одновременно с разрешением реконсиляции."""
        return self.recovered


def _causal_blocker(facts: CausalOutcomeInput) -> str:
    """Возвращает первую машинную причину отказа, без исходного payload."""
    config, error = facts.config, facts.error
    identity, completion = error.identity, facts.completion
    terminal = facts.terminal
    drain, process = terminal.drain, terminal.process
    checks = (
        ("fatal_safety_error", config.is_fatal_safety is True),
        ("self_heal_disabled", config.master_self_heal is not True),
        ("causal_recovery_disabled", config.causal_recovery_enabled is not True),
        ("missing_structured_error", identity.seq < 0),
        ("completion_not_after_error", completion.last_completion_seq <= identity.seq),
        (
            "attempt_mismatch",
            config.attempt < 0 or identity.attempt != config.attempt
            or completion.completion_attempt != config.attempt,
        ),
        ("non_error_result_status", error.result_status.strip().upper() != "ERROR"),
        ("unstructured_error", error.error_from_structured_record is not True),
        ("missing_error_identity", not identity.sha256),
        ("error_identity_mismatch", error.result_error_sha256 != identity.sha256),
        ("completion_has_tools", completion.completion_done_without_tools is not True),
        ("missing_final_text", completion.has_final_text is not True),
        ("late_error_or_open_step", terminal.has_late_error_or_open_step),
        ("fatal_error", process.has_fatal_error),
        ("drain_not_explicit", drain.explicit_drain_complete is not True),
        ("drain_incomplete", drain.drain_complete is not True),
        ("producer_not_stopped", drain.producer_stopped is not True),
        ("tools_not_closed", terminal.tool_status != "closed"),
        ("process_not_exited", process.process_exited is not True),
        (
            "unsupported_returncode",
            type(process.returncode) is not int or process.returncode not in (0, 1),
        ),
    )
    return next((reason for reason, blocked in checks if blocked), "")


def evaluate_causal_turn_recovery(facts: CausalOutcomeInput) -> CausalOutcomeDecision:
    """Разрешает только точное структурированное эхо после финального completion."""
    blocker = _causal_blocker(facts)
    if blocker:
        return CausalOutcomeDecision(False, "unrecovered", blocker, "")
    mode = (
        "causal_echo_only"
        if facts.terminal.process.returncode == 1
        else "causal_echo_zero_rc"
    )
    return CausalOutcomeDecision(True, mode, "causal_echo_recovered", "")
