"""Переносимый канонический парсер блокировок и ограниченное чтение UTF-8."""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class BlocklistParseError(ValueError):
    """Источник блокировок некорректен или неоднозначен."""


@dataclass(frozen=True, slots=True)
class ModelNotesRule:
    model: str | None
    transport: str | None
    effort: str | None
    expires_at: datetime | None


@dataclass(frozen=True, slots=True)
class ModelNotes:
    generation: int | None
    expires_at: datetime | None
    rules: tuple[ModelNotesRule, ...]


def _time(value: str, now: datetime) -> datetime:
    match = re.fullmatch(r"(?:(\d{4}-\d{2}-\d{2}) )?(\d{2}:\d{2}) (MSK|UTC)", value)
    if match is None:
        raise BlocklistParseError("Некорректный срок или часовой пояс")
    day, clock, zone = match.groups()
    tz = timezone(timedelta(hours=3)) if zone == "MSK" else timezone.utc
    day = day or now.astimezone(tz).date().isoformat()
    return datetime.fromisoformat(f"{day}T{clock}").replace(tzinfo=tz)


def _metadata(text: str, key: str) -> str | None:
    values = []
    for match in re.finditer(r"<!--\s*" + key + r"\b[^\n]*", text):
        field = re.fullmatch(r"<!--\s*" + key + r":\s*(.*?)\s*-->\s*", match[0])
        if field is None:
            raise BlocklistParseError(f"Некорректный {key}")
        values.append(field[1])
    if len(set(values)) > 1:
        raise BlocklistParseError(f"Противоречивый {key}")
    return values[0] if values else None


def _expiry(value: str, now: datetime) -> datetime | None:
    starts = re.findall(r"\bдо\s+(?=\d)", value)
    matches = re.findall(r"\bдо\s+((?:\d{4}-\d{2}-\d{2} )?\d{2}:\d{2} (?:MSK|UTC))\b", value)
    if len(starts) != len(matches) or len(matches) > 1:
        raise BlocklistParseError("Неоднозначный срок строки")
    return _time(matches[0], now) if matches else None


def _tokens(value: str) -> list[str | None]:
    if value.count("`") % 2:
        raise BlocklistParseError("Незакрытая кавычка скоупа")
    value = re.sub(r"\([^()]*\)", "", value).strip()
    tokens = [part.strip() for part in value.split(",")]
    pattern = r"(?:`[a-zA-Z0-9_:.*-]+(?: -[a-zA-Z0-9-]+)?`|[a-zA-Z0-9_:.*-]+)"
    if not all(re.fullmatch(pattern, part) for part in tokens):
        raise BlocklistParseError("Некорректный скоуп")
    result = [part.strip("`") for part in tokens]
    if any("*" in part[:-1] for part in result):
        raise BlocklistParseError("Поддерживается только конечный wildcard")
    return [None if part == "*" else part for part in result]


def _scope(target: str, group: str) -> tuple[list[str | None], list[str | None]]:
    if group == "Транспорты":
        return [None], _tokens(re.sub(r",\s*все модели$", "", target))
    if group not in ("", "Модели"):
        raise BlocklistParseError("Неоднозначная группа скоупа")
    parts = target.split(" / ")
    if len(parts) > 2:
        raise BlocklistParseError("Неоднозначная пара модель/транспорт")
    return _tokens(parts[0]), _tokens(parts[1]) if len(parts) == 2 else [None]


def _rule(model: str | None, transport: str | None, expiry: datetime | None) -> ModelNotesRule:
    effort = None
    if model:
        match = re.fullmatch(r"(.+)-(off|minimal|low|medium|high|xhigh|max)", model)
        if match:
            model, effort = match.groups()
    return ModelNotesRule(model, transport, effort, expiry)


def _row(cells: list[str], section: str, now: datetime) -> list[ModelNotesRule]:
    group, target, status = ("", cells[0], cells[1])
    if section == "2":
        group, target, status = cells[:3]
    status = status.replace("`", "")
    head = re.match(r"(TEMP[ -]OFF|LIMIT[ -]BLOCKED|BANNED|RETIRED|ACTIVE|OK)\b", status)
    if head is None:
        raise BlocklistParseError("Неизвестный статус")
    active = head[1] in ("ACTIVE", "OK")
    if active and re.search(r"\b(BANNED|RETIRED|TEMP[ -]OFF|LIMIT[ -]BLOCKED)\b", status):
        raise BlocklistParseError("Противоречивый статус")
    if active:
        return []
    models, transports = _scope(target, group)
    expiry = _expiry(" ".join([status, *cells[4:]]), now)
    rules = [_rule(m, t, expiry) for m in models for t in transports]
    return rules if expiry is None or now <= expiry else []


def _header(header: list[str], separator: list[str], section: str) -> None:
    expected = ("Модель", "Статус") if section == "1" else ("Группа", "Что", "Статус")
    schemas = {("1", "Модель", 3), ("1", "Модель / транспорт", 5), ("2", "Группа", 4)}
    if (section, header[0], len(header)) not in schemas:
        raise BlocklistParseError("Некорректные колонки")
    if header[1 : len(expected)] != list(expected[1:]):
        raise BlocklistParseError("Неизвестная таблица")
    if len(separator) != len(header) or not all(re.fullmatch(r":?-{3,}:?", c) for c in separator):
        raise BlocklistParseError("Некорректный разделитель таблицы")


def _cells(body: str, section: str) -> list[list[str]]:
    lines = [line.strip() for line in body.splitlines() if line.lstrip().startswith("|")]
    if len(lines) < 2:
        raise BlocklistParseError("Нет явной таблицы блокировок")
    rows = [[cell.strip() for cell in line[1:-1].split("|")] for line in lines]
    _header(rows[0], rows[1], section)
    if any(not line.endswith("|") for line in lines):
        raise BlocklistParseError("Незакрытая строка таблицы")
    return rows


def _table(body: str, section: str, now: datetime) -> list[ModelNotesRule]:
    header, _, *rows = _cells(body, section)
    rules = []
    for cells in rows:
        if (
            len(cells) != len(header)
            or not all(cells[:2])
            or any(cell.count("`") % 2 for cell in cells)
        ):
            raise BlocklistParseError("Некорректное число ячеек")
        rules.extend(_row(cells, section, now))
    return rules


def _document(text: str, now: datetime) -> ModelNotes:
    generation = _metadata(text, "GENERATION")
    if generation is not None and re.fullmatch(r"[0-9]+", generation) is None:
        raise BlocklistParseError("Некорректное поколение")
    expiry_text = _metadata(text, "EXPIRY")
    if expiry_text is not None and not re.match(r"\d{4}-\d{2}-\d{2} ", expiry_text):
        raise BlocklistParseError("Срок документа требует даты")
    expiry = _time(expiry_text, now) if expiry_text is not None else None
    if expiry is not None and now >= expiry:
        raise BlocklistParseError("Срок документа истёк")
    return ModelNotes(int(generation) if generation is not None else None, expiry, ())


def parse_model_notes(text: str, now_dt: datetime | None = None) -> ModelNotes:
    """Разбирает §1/§2; ошибки и истёкший документ закрывают доступ."""
    now = now_dt if now_dt is not None else datetime.now(timezone.utc)
    if now.utcoffset() is None:
        raise BlocklistParseError("now_dt должен содержать часовой пояс")
    try:
        document = _document(text, now)
        selected = re.findall(r"(?ms)^##[ \t]*([12])\.[^\n]*\n(.*?)(?=^##(?!#)|\Z)", text)
        if not selected:
            raise BlocklistParseError("Нет разделов блокировок")
        rules = [rule for section, body in selected for rule in _table(body, section, now)]
        return ModelNotes(document.generation, document.expires_at, tuple(rules))
    except ValueError as exc:
        raise BlocklistParseError(str(exc)) from exc


def read_model_notes_file(path: str | os.PathLike[str], max_bytes: int = 1048576) -> str:
    """Читает только обычный UTF-8 файл, не более max_bytes + 1 байт."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise BlocklistParseError("max_bytes должен быть положительным целым")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size > max_bytes:
                raise BlocklistParseError("Необычный файл или превышение max_bytes")
            with os.fdopen(fd, "rb", closefd=False) as source:
                data = source.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise BlocklistParseError("Превышение max_bytes")
            return data.decode("utf-8")
        finally:
            os.close(fd)
    except (OSError, UnicodeError) as exc:
        raise BlocklistParseError("Ошибка чтения model-notes") from exc
