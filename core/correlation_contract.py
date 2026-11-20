"""Вендор-агностичный контракт корреляции заголовков и лог-суффиксов (D5)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

DEFAULT_CORR_MAX_LEN: Final[int] = 64
_ASCII_TOKEN_RE: Final[re.Pattern[str]] = re.compile(r"^[!-~]+$")


def sanitize_corr_token(value: object, *, max_len: int = DEFAULT_CORR_MAX_LEN) -> str:
    """Допускает только printable ASCII 0x21..0x7E длиной <= max_len; иначе '-'."""
    limit = max(1, int(max_len))
    raw = value.strip() if isinstance(value, str) else ""
    valid = all((bool(raw), len(raw) <= limit, bool(_ASCII_TOKEN_RE.fullmatch(raw))))
    result = raw if valid else "-"
    return result


def extract_correlation(
    headers: Mapping[str, str], *, max_len: int = DEFAULT_CORR_MAX_LEN
) -> tuple[str, str]:
    """Извлекает и санитизирует (req_id, sub_id) из HTTP-заголовков без учёта регистра."""
    lowered = {str(k).lower(): v for k, v in headers.items()}
    req_id = sanitize_corr_token(lowered.get("x-request-id"), max_len=max_len)
    sub_id = sanitize_corr_token(lowered.get("x-subagent-id"), max_len=max_len)
    return req_id, sub_id


def format_log_corr_suffix(
    req_id: str, sub_id: str, *, max_len: int = DEFAULT_CORR_MAX_LEN
) -> str:
    """Формирует безопасный суффикс лога без сырого chat_id и без управляющих символов."""
    clean_req = sanitize_corr_token(req_id, max_len=max_len)
    clean_sub = sanitize_corr_token(sub_id, max_len=max_len)
    return f" req_id={clean_req} sub_id={clean_sub}"


def build_validated_header(
    header_name: str,
    value: object,
    pattern: re.Pattern[str],
    *,
    enabled: bool = True,
) -> dict[str, str]:
    """Возвращает {header_name: value} только если включено и значение прошло regex-валидацию."""
    raw = value.strip() if isinstance(value, str) else ""
    ok = all((enabled, bool(header_name), bool(raw), bool(pattern.fullmatch(raw))))
    result = {header_name: raw} if ok else {}
    return result
