#!/usr/bin/python3
"""Охранник B (AD-006): офлайн-прогноз размера блока agent-instructions в промпте DSH.

Зачем нужен. Плагин agent-instructions клиента DSH кладёт в запрос user-global канон
(`~/.dsh/AGENTS.md`) и проектные AGENTS.md/CLAUDE.md. В cwd=KB проектный AGENTS.md -
симлинк на тот же канон, поэтому при `maxBytes: 262144` канон попадает в запрос дважды
(блок 111 177 Б, строка session.v4.jsonl 113 105 Б, REQ-003). Правка `maxBytes` в
`preset-standard` до значения внутри окна [L .. U] выкидывает user-global-копию ровно там,
где она дублируется, и не трогает cwd без дубля. Окно зависит от размеров четырёх файлов
(канон и проектные файлы AB/WA), поэтому размеры надо проверять машинно - этот инструмент.

Что читает. Файлы проектных AGENTS.md/CLAUDE.md и канон читаются целиком в память ровно для
двух целей: sha256 содержимого (ключ дедупа внутри каталога, F-314) и точный расчёт длины
строки журнала (RW-003). Содержимое нигде не печатается и не логируется: наружу выходят только
размеры, числа и пути. Профили DSH читает только режим `--profiles` и только для чтения
(`<profiles-dir>/<профиль>/cordis.patch.yml`, из него берётся одно число - maxBytes
плагина agent-instructions внутри `preset-standard`); ничего не пишется и не меняется.

Модель рендера (zone-F, F-706, откалибрована по F-703/F-707/F-709, точна до байта):
    block = 272 + Σ_секций (23 + len(display_path) + размер_файла) [+ метка]
Для типичного набора (user-global `~/.dsh/AGENTS.md` = 16 Б, остальные имена по 9 Б) это
ровно формула из AD-006: `279 + 32·N_секций + Σ байт файлов`; функция
`estimate_block_bytes` реализует её отдельно и тесты сверяют обе. Путь-зависимая форма
нужна, потому что display path входит в заголовок секции `Instructions from: <path>`.
Метка бюджета `Workspace instruction budget <N> bytes: omitted <пути>; truncated <путь>
from X to Y bytes` + пустая строка сама входит в бюджет, и в ней число N: поэтому текст
блока зависит от maxBytes (и меняет SHA, F-721).

Алгоритм рендера (F-706): порядок user-global -> корень проекта -> ... -> cwd, внутри
каталога AGENTS.md, CLAUDE.md, затем .local; (1) всё влезает - всё (класс ALL);
(2) иначе целиком отбрасываются файлы с широкого начала (user-global первым), пока остаток
вместе с меткой влезает (UG_OMITTED, а если отброшен и проектный файл - PROJECT_OMITTED,
F-708: короткий CLAUDE.md после отброшенного AGENTS.md сохраняется); (3) только если не
влезает даже последний файл - он усекается (TRUNCATED; модель даёт верхнюю оценку Y, реальная
граница UTF-8 может быть меньше на 1-3 Б, F-707); дедупликация только внутри одного каталога
по содержимому (F-314) - user-global и проектный файл НЕ схлопываются.

Метрики REQ-003 не смешиваются: block_bytes - длина текста блока (модель по размерам),
journal_line_bytes - длина JSON-строки события в session.v4.jsonl вместе с переводом строки.
Строка считается по реальной сериализации: `render_block_text` строит блок (рамка + секции
`Instructions from: <display>` + тело + метка), `render_journal_line` оборачивает его в событие
`user/message` (поля type/seq/time/data{content,source{baselineIdentity,changes},role,id}/surfaceOp)
и делает json.dumps - поэтому экранирование (кавычки, переводы строк, слеши), длина display paths и
маркер бюджета учитываются точно (`exact_journal_line_bytes`). Режим точного расчёта включается,
когда содержимое прочитано (`--check` и `--profiles` читают его для хеша); при отсутствии текстов
остаётся запасная оценка по размерам (`journal_line_bytes_fallback`: обёртка из реального рендера
плюс доля на экранирование ESCAPE_RATIO). Оба числа - прогноз, не оракул приёмки.

Окно и запасы (`evaluate`):
    L (нижняя граница) = макс. по cwd размер блока, который обязан влезть целиком вместе с
        user-global (для cwd с дублем канона - блок без user-global и с меткой);
    U (верхняя граница) = мин. по cwd с дублем канона (full_block - 1): при maxBytes >= full
        блок снова вернёт обе копии;
    запас снизу = maxBytes - L, запас сверху = U - maxBytes.
Рекомендуемый maxBytes - наибольшее кратное 4 КиБ, оставляющее запас сверху >= 4096 Б
(и снизу >= 4096): рост проектных файлов (сужает окно снизу) вероятнее уменьшения канона,
поэтому значение прижимается к верху окна, а не к середине (середина дала бы 102 400 с
запасом сверху всего ~4,4 КБ против 12,7 КБ у 106 496 снизу; при текущих файлах правило даёт
106 496 = 104 КиБ - значение, измеренное клиентом DSH в F-709). Если подходящего кратного
нет - берётся середина окна, округлённая вниз.

Коды выхода `--check` и `--profiles`: 0 - оба запаса >= 4096 Б и запас строки журнала до
60 000 Б в KB >= 2048 Б; 1 - запас меньше порога; 2 - канон теряется в каком-либо cwd
(CANON_LOST), дубль возвращается (DUPLICATE_RETURNED) или блок/строка KB > 60 000 Б
(REQ003_SIZE_EXCEEDED: в рабочем CLI `run_check` всегда вызывает evaluate со
`strict_req003=True`, AD-006 дельта-4; чистая функция `evaluate` по умолчанию остаётся
нестрогой и даёт 1). Граница 60 000 Б строгая: 60 000 проходит, 60 001 нет.

Режим `--profiles [--profiles-dir PATH]` (по умолчанию `~/.dsh/profiles`): для каждого профиля
с `cordis.patch.yml` (каталоги `*.bak*` пропускаются) читает maxBytes и прогоняет ту же проверку,
что `--check`, на реальных cwd; итог - худший код по профилям. Нет каталога/профилей/maxBytes -
сообщение и exit 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import posixpath
import re
import sys
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

CANON_PATH = os.path.expanduser("~/Мой диск/Context/AGENTS.md")
KB_CWD = os.path.expanduser("~/Мой диск/Работа/Sber/knowledge-base")
WA_CWD = os.path.expanduser("~/src/saluteeye/gigabus/gigawebaccess/webaccess")
AB_CWD = os.path.expanduser("~/Мой диск/Workshop/aibunker-workshop")
DW_CWD = os.path.expanduser("~/Documents/deepseek-harness/default-workspace")
UG_PATH = os.path.expanduser("~/.dsh/AGENTS.md")
PROFILES_DIR = os.path.expanduser("~/.dsh/profiles")
PROFILE_FILE = "cordis.patch.yml"
DEFAULT_CWDS: Tuple[Tuple[str, str], ...] = (
    ("KB", KB_CWD),
    ("WA", WA_CWD),
    ("AB", AB_CWD),
    ("DW", DW_CWD),
)

UG_DISPLAY = "~/.dsh/AGENTS.md"
FRAME_BASE = 272  # обёртка system-reminder, intro и т.п. (калибровка F-703/F-709)
SECTION_FIXED = 23  # заголовок `Instructions from: ` и разделители без самого пути
MARKER_PREFIX = "Workspace instruction budget "
MARKER_TAIL_BYTES = 2  # пустая строка после метки
FORMULA_BASE = 279  # AD-006: 279 + 32·N + Σ байт (путь-зависимая модель при 16/9 Б путях)
FORMULA_PER_SECTION = 32

BLOCK_LIMIT = 60000  # REQ-003, граница строгая: <= 60000 проходит
DEFAULT_MAXBYTES = 106496
MARGIN_MIN = 4096
LINE_MARGIN_MIN = 2048

# Реальный рендер блока и события журнала (снято с живого session.v4.jsonl, RW-003):
# block = HEAD + [метка + "\n\n"] + "\n\n".join(секции) + "\n" + TAIL, где секция =
# "Instructions from: <display>\n\n<тело>"; длина совпадает с моделью FRAME_BASE/SECTION_FIXED.
BLOCK_HEAD = ("<system-reminder>\nThe following workspace instructions may be relevant to your work. "
              "Use them as guidance when applicable. More specific instructions take precedence over "
              "broader ones. They do not override system, developer, or direct user instructions.\n\n")
BLOCK_TAIL = "</system-reminder>"
SECTION_HEADER = "Instructions from: "
JOURNAL_SEQ = 10  # номер события (поле seq) - в обёртке занимает 2-3 символа
JOURNAL_TIME = 1791393991696  # мс с эпохи, 13 цифр
JOURNAL_ID = "c3321a3c-6a0a-4d8e-8137-1dfd672f33fe"  # uuid события, 36 символов
MAX_SOURCE_BYTES = 1048576  # maxSourceBytes в baselineIdentity (7 цифр в живой строке)
ESCAPE_RATIO = 0.0125  # запасной вариант: доля JSON-экранирования текста блока (переводы строк, кавычки)
ALIGN = 4096

# Имена кандидатов. `.local`-варианты - предположение (F-313: «затем .local»), точные
# имена в рендере DSH не проверялись; отсутствие файла безвредно.
CANDIDATE_NAMES: Tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "AGENTS.local.md",
    "CLAUDE.local.md",
)
PROJECT_ROOT_MARKER = ".git"  # нет маркера - корнем считается сам cwd (F-313, F-704)

CLASS_ALL = "ALL"
CLASS_UG_OMITTED = "UG_OMITTED"
CLASS_PROJECT_OMITTED = "PROJECT_OMITTED"
CLASS_TRUNCATED = "TRUNCATED"


class FileEntry(NamedTuple):
    """Файл-кандидат: размер и метаданные идентичности (content_key - sha256 содержимого), без самого текста."""

    display: str
    size: int
    is_canon: bool = False
    directory: str = ""
    content_key: Optional[str] = None
    user_global: bool = False


class RenderResult(NamedTuple):
    """Итог рендера набора файлов под maxBytes."""

    cls: str
    kept: List[str]
    omitted: List[str]
    truncated: Optional[Tuple[str, int, int]]
    block_bytes: int
    canon_copies: int
    marker: str


class Result(NamedTuple):
    """Итог `evaluate`: код выхода, причины, запасы окна и рекомендуемый maxBytes."""

    exit_code: int
    reasons: List[str]
    lower_margin: int
    upper_margin: Optional[int]
    recommended: Optional[int]
    window_low: int = 0
    window_high: Optional[int] = None
    renders: Optional[Dict[str, RenderResult]] = None
    line_margin: Optional[int] = None
    line_estimates: Optional[Dict[str, Tuple[int, bool]]] = None  # cwd -> (байт строки журнала, точный ли расчёт)


def make_user_global(canon_size: int) -> FileEntry:
    """Секция user-global: всегда первая, всегда копия канона (CLAUDE.md/.local для неё не читаются, F-312)."""
    return FileEntry(UG_DISPLAY, canon_size, True, "~/.dsh", None, True)


def section_bytes(display: str, size: int) -> int:
    """Размер секции: заголовок с display path плюс тело файла."""
    return SECTION_FIXED + len(display.encode("utf-8")) + size


def estimate_block_bytes(n_sections: int, files_total: int) -> int:
    """Формула AD-006 `279 + 32·N + Σбайт` - быстрая оценка без меток; точная - `render_plan`."""
    return FORMULA_BASE + FORMULA_PER_SECTION * n_sections + files_total


def marker_text(maxbytes: int, omitted: Sequence[str], truncated: Optional[Tuple[str, int, int]]) -> str:
    """Строка-метка бюджета без завершающей пустой строки; пустая, если ничего не отброшено."""
    parts: List[str] = []
    if omitted:
        parts.append("omitted " + ", ".join(omitted))
    if truncated is not None:
        path, src, dst = truncated
        parts.append("truncated %s from %d to %d bytes" % (path, src, dst))
    if not parts:
        return ""
    return MARKER_PREFIX + "%d bytes: " % maxbytes + "; ".join(parts)


def _marker_bytes(marker: str) -> int:
    """Байты метки вместе с пустой строкой после неё (метка входит в бюджет)."""
    if not marker:
        return 0
    return len(marker.encode("utf-8")) + MARKER_TAIL_BYTES


def _block(entries: Sequence[FileEntry], marker: str) -> int:
    """Длина блока: рамка + секции + метка; пустой набор без метки не даёт блока вовсе."""
    if not entries and not marker:
        return 0
    return FRAME_BASE + sum(section_bytes(e.display, e.size) for e in entries) + _marker_bytes(marker)


def dedupe_entries(entries: Sequence[FileEntry]) -> List[FileEntry]:
    """Дедуп только внутри одного каталога по ключу содержимого (F-314).

    Разные каталоги не схлопываются даже при побайтово равных файлах - поэтому
    user-global и проектная копия канона остаются двумя секциями. Ключ None
    (содержимое неизвестно) никогда не считается совпадением.
    """
    seen = set()  # type: set
    out: List[FileEntry] = []
    for entry in entries:
        if entry.content_key is not None:
            ident = (entry.directory, entry.content_key)
            if ident in seen:
                continue
            seen.add(ident)
        out.append(entry)
    return out


def _canon_copies(kept: Sequence[FileEntry]) -> int:
    """Число полных (неусечённых) копий канона среди оставленных секций."""
    return sum(1 for e in kept if e.is_canon)


def render_plan(entries: Sequence[FileEntry], maxbytes: int) -> RenderResult:
    """Рендер по алгоритму F-706 на чистых размерах: что останется под maxBytes."""
    items = dedupe_entries(entries)
    n = len(items)
    if _block(items, "") <= maxbytes:
        return RenderResult(CLASS_ALL, [e.display for e in items], [], None,
                            _block(items, ""), _canon_copies(items), "")
    # Шаг 2: отбрасываем файлы целиком с широкого начала, пока остаток с меткой влезает.
    for k in range(1, n):
        omitted = [e.display for e in items[:k]]
        marker = marker_text(maxbytes, omitted, None)
        rest = items[k:]
        size = _block(rest, marker)
        if size <= maxbytes:
            cls = CLASS_UG_OMITTED if (k == 1 and items[0].user_global) else CLASS_PROJECT_OMITTED
            return RenderResult(cls, [e.display for e in rest], omitted, None,
                                size, _canon_copies(rest), marker)
    # Шаг 3: не влезает даже последний - усекаем его (двоичный поиск по длине Y).
    last = items[-1]
    omitted = [e.display for e in items[:-1]]
    lo, hi = 0, max(last.size - 1, 0)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        marker = marker_text(maxbytes, omitted, (last.display, last.size, mid))
        if _block([last._replace(size=mid)], marker) <= maxbytes:
            lo = mid
        else:
            hi = mid - 1
    marker = marker_text(maxbytes, omitted, (last.display, last.size, lo))
    return RenderResult(CLASS_TRUNCATED, [last.display], omitted, (last.display, last.size, lo),
                        _block([last._replace(size=lo)], marker), 0, marker)


def block_within_limit(block_bytes: int) -> bool:
    """Граница REQ-003 строгая: 60 000 Б проходит, 60 001 - нет."""
    return block_bytes <= BLOCK_LIMIT


def journal_line_bytes_est(text: str) -> int:
    """Оценка длины строки события в журнале без внешней оболочки события.

    Определение: UTF-8 длина `json.dumps(text, ensure_ascii=False)` - то есть JSON-строка
    блока вместе с обрамляющими кавычками: кавычки, обратные слеши, переводы строк и
    управляющие символы удлиняются экранированием, кириллица остаётся 2 Б/символ. Поэтому
    два текста одной длины дают разные оценки. Обёртка события (поля source, changes,
    id) сюда не входит - её добавляет `JOURNAL_WRAPPER_EST` при прогнозе запаса.
    """
    return len(json.dumps(text, ensure_ascii=False).encode("utf-8"))


def render_block_text(sections: Sequence[Tuple[str, str]], marker: str = "") -> str:
    """Реальный текст блока: рамка + (метка) + секции `Instructions from: <display>` + тело.

    `sections` - (display path, текст файла) в порядке рендера. Длина в байтах равна модели
    `_block` (272 + Σ(23 + len(display) + размер) + метка + 2). Пустой набор без метки - пустой блок.
    """
    if not sections and not marker:
        return ""
    body = "\n\n".join("%s%s\n\n%s" % (SECTION_HEADER, display, text) for display, text in sections)
    return BLOCK_HEAD + (marker + "\n\n" if marker else "") + body + "\n" + BLOCK_TAIL


def _change_entry(display: str, text: str) -> Dict[str, str]:
    """Запись changes события: scope = каталог NUL имя, path = display, digest = sha1 содержимого."""
    if display == UG_DISPLAY:
        directory, name = "user-global", posixpath.basename(display)
    else:
        directory, name = posixpath.dirname(display) or ".", posixpath.basename(display)
    return {"action": "set", "scope": directory + "\u0000" + name, "path": display,
            "digest": hashlib.sha1(text.encode("utf-8")).hexdigest()}


def _baseline_identity(maxbytes: int) -> str:
    """Строка baselineIdentity события (внутри JSON экранируется ещё раз, это и считается)."""
    return json.dumps({
        "projectRoot": "", "projectRootMarkers": [PROJECT_ROOT_MARKER], "maxBytes": maxbytes,
        "maxSourceBytes": MAX_SOURCE_BYTES,
        "instructionFileCandidates": list(CANDIDATE_NAMES[:2]),
        "localInstructionFileCandidates": list(CANDIDATE_NAMES[2:]),
    }, separators=(",", ":"))


def render_journal_line(block_text: str, sections: Sequence[Tuple[str, str]], maxbytes: int) -> str:
    """Строка session.v4.jsonl с событием agent-instructions: компактный json.dumps + перевод строки."""
    event = {
        "type": "user/message", "seq": JOURNAL_SEQ, "time": JOURNAL_TIME,
        "data": {
            "content": [{"type": "text", "text": block_text}],
            "source": {"kind": "agent-instructions", "form": "instructions", "baseline": True,
                       "baselineIdentity": _baseline_identity(maxbytes),
                       "changes": [_change_entry(d, t) for d, t in sections]},
            "role": "user", "id": JOURNAL_ID,
        },
        "surfaceOp": "append",
    }
    return json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"


def exact_journal_line_bytes(sections: Sequence[Tuple[str, str]], maxbytes: int, marker: str = "") -> int:
    """Точная длина строки журнала (UTF-8) по реальным текстам файлов: блок -> событие -> json.dumps."""
    block = render_block_text(sections, marker)
    return len(render_journal_line(block, sections, maxbytes).encode("utf-8"))


def journal_line_bytes_fallback(block_bytes: int, displays: Sequence[str], maxbytes: int) -> int:
    """Запасная оценка строки без текстов (только размеры): обёртка события из реального рендера
    с пустым телом (display paths входят в text, path и scope) плюс доля ESCAPE_RATIO на экранирование."""
    wrapper = len(render_journal_line("", [(d, "") for d in displays], maxbytes).encode("utf-8"))
    return wrapper + block_bytes + int(math.ceil(block_bytes * ESCAPE_RATIO))


def _line_estimate(rend: RenderResult, cwd_texts: Optional[Dict[str, str]], canon_text: Optional[str],
                   maxbytes: int) -> Tuple[int, bool]:
    """Длина строки журнала для рендера: точная (по текстам) или запасная оценка по размерам."""
    sections: List[Tuple[str, str]] = []
    for display in rend.kept:
        if display == UG_DISPLAY:
            text = canon_text
        else:
            text = (cwd_texts or {}).get(display)
        if text is None:
            return journal_line_bytes_fallback(rend.block_bytes, rend.kept, maxbytes), False
        if rend.truncated is not None and display == rend.truncated[0]:
            text = text.encode("utf-8")[:rend.truncated[2]].decode("utf-8", "ignore")
        sections.append((display, text))
    return exact_journal_line_bytes(sections, maxbytes, rend.marker), True


def evaluate(
    canon_size: int,
    cwd_files: Dict[str, Sequence[FileEntry]],
    maxbytes: int,
    req003_cwds: Sequence[str] = (),
    strict_req003: bool = False,
    texts: Optional[Dict[str, Dict[str, str]]] = None,
    canon_text: Optional[str] = None,
) -> Result:
    """Чистая оценка окна maxBytes без файловой системы.

    `cwd_files` - метка cwd -> проектные файлы в порядке рендера (user-global добавляется
    здесь). `req003_cwds` - метки cwd, для которых действует ограничение 60 000 Б (по
    решению владельца REQ-003 принимается только в KB: для WA/AB условие недостижимо, F-724).
    `texts` (метка cwd -> display -> текст файла) и `canon_text` включают точный расчёт строки
    журнала; нет текста хотя бы одной оставленной секции - запасная оценка по размерам.
    `strict_req003` поднимает REQ003_SIZE_EXCEEDED до exit 2 (рабочий CLI всегда включает его).
    """
    reasons: List[str] = []
    renders: Dict[str, RenderResult] = {}
    line_estimates: Dict[str, Tuple[int, bool]] = {}
    lowers: List[int] = []
    uppers: List[int] = []
    severe = False
    warn = False
    ug = make_user_global(canon_size)
    for label, files in cwd_files.items():
        entries = dedupe_entries([ug] + list(files))
        rend = render_plan(entries, maxbytes)
        renders[label] = rend
        line_estimates[label] = _line_estimate(rend, texts.get(label) if texts else None, canon_text, maxbytes)
        full = _block(entries, "")
        if rend.canon_copies == 0:
            reasons.append("CANON_LOST cwd=%s: канон не попал в запрос (класс %s, omitted=%s)"
                           % (label, rend.cls, ",".join(rend.omitted) or "-"))
            severe = True
        elif rend.canon_copies >= 2:
            reasons.append("DUPLICATE_RETURNED cwd=%s: копий канона в запросе %d" % (label, rend.canon_copies))
            severe = True
        if sum(1 for e in entries if e.is_canon) >= 2:
            uppers.append(full - 1)
            rest = entries[1:]
            lowers.append(_block(rest, marker_text(maxbytes, [ug.display], None)))
        else:
            lowers.append(full)
    window_low = max(lowers) if lowers else 0
    window_high = min(uppers) if uppers else None
    lower_margin = maxbytes - window_low
    upper_margin = None if window_high is None else window_high - maxbytes

    line_margin: Optional[int] = None
    for label in req003_cwds:
        rend = renders.get(label)
        if rend is None:
            continue
        line_est = line_estimates[label][0]
        margin = BLOCK_LIMIT - line_est
        line_margin = margin if line_margin is None else min(line_margin, margin)
        if not block_within_limit(rend.block_bytes):
            reasons.append("REQ003_SIZE_EXCEEDED cwd=%s basis=block block=%d limit=%d"
                           % (label, rend.block_bytes, BLOCK_LIMIT))
            warn = True
            severe = severe or strict_req003
        elif not block_within_limit(line_est):
            reasons.append("REQ003_SIZE_EXCEEDED cwd=%s basis=line_estimate line_est=%d limit=%d"
                           % (label, line_est, BLOCK_LIMIT))
            warn = True
            severe = severe or strict_req003
        elif margin < LINE_MARGIN_MIN:
            reasons.append("LINE_ORACLE_RISK cwd=%s: запас строки журнала %d Б < %d"
                           % (label, margin, LINE_MARGIN_MIN))
            warn = True

    if lower_margin < MARGIN_MIN:
        reasons.append("LOW_MARGIN_LOWER: запас снизу %d Б < %d (рост проектных файлов/канона съест окно)"
                       % (lower_margin, MARGIN_MIN))
        warn = True
    if upper_margin is not None and upper_margin < MARGIN_MIN:
        reasons.append("LOW_MARGIN_UPPER: запас сверху %d Б < %d (уменьшение канона вернёт дубль)"
                       % (upper_margin, MARGIN_MIN))
        warn = True

    exit_code = 2 if severe else (1 if warn else 0)
    return Result(exit_code, reasons, lower_margin, upper_margin,
                  recommend_maxbytes(window_low, window_high), window_low, window_high,
                  renders, line_margin, line_estimates)


def recommend_maxbytes(window_low: int, window_high: Optional[int]) -> Optional[int]:
    """Рекомендуемый maxBytes: наибольшее кратное 4 КиБ с запасом >= 4096 Б с обеих сторон.

    Нет верхней границы (в наборе cwd нет дубля) - наименьшее кратное 4 КиБ с запасом снизу.
    Нет подходящего кратного - середина окна, округлённая вниз; окно пусто - None.
    """
    if window_high is None:
        need = window_low + MARGIN_MIN
        return -(-need // ALIGN) * ALIGN
    if window_high < window_low:
        return None
    top = window_high - MARGIN_MIN
    cand = (top // ALIGN) * ALIGN
    if cand >= window_low + MARGIN_MIN:
        return cand
    return (window_low + window_high) // 2


# ---------------------------------------------------------------- файловая система (только stat)


def _find_project_root(cwd: str) -> str:
    """Ближайший предок с маркером корня проекта; нет маркера - сам cwd (F-313)."""
    cur = os.path.realpath(cwd)
    while True:
        if os.path.lexists(os.path.join(cur, PROJECT_ROOT_MARKER)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.realpath(cwd)
        cur = parent


def collect_cwd_entries(cwd: str, canon_real: str,
                        texts_out: Optional[Dict[str, str]] = None) -> Tuple[List[FileEntry], bool]:
    """Проектные файлы цепочки root -> cwd; (список, cwd существует).

    Файл читается один раз: размер - длина содержимого (симлинк следуется, как у клиента),
    `content_key` - sha256 содержимого (RW-003): два разных файла с одинаковым текстом и один файл
    под двумя именами в одном каталоге схлопываются `dedupe_entries`. Симлинк на канон помечается
    is_canon по realpath. Содержимое наружу не отдаётся и не печатается; `texts_out`
    (display -> текст) заполняется только по просьбе вызывающего для точного расчёта строки журнала.
    Нечитаемый файл получает ключ None (не схлопывается) и размер из os.stat.
    """
    if not os.path.isdir(cwd):
        return [], False
    real_cwd = os.path.realpath(cwd)
    root = _find_project_root(real_cwd)
    chain: List[str] = []
    cur = real_cwd
    while True:
        chain.append(cur)
        if cur == root:
            break
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    chain.reverse()
    out: List[FileEntry] = []
    for directory in chain:
        for name in CANDIDATE_NAMES:
            path = os.path.join(directory, name)
            try:
                st = os.stat(path)
            except FileNotFoundError:
                continue
            except NotADirectoryError:
                continue
            if not os.path.isfile(path):
                continue
            real = os.path.realpath(path)
            display = os.path.relpath(path, real_cwd).replace(os.sep, "/")
            size, key = st.st_size, None
            try:
                with open(path, "rb") as handle:
                    data = handle.read()
                size, key = len(data), hashlib.sha256(data).hexdigest()
                if texts_out is not None:
                    texts_out[display] = data.decode("utf-8", "replace")
            except OSError:
                pass
            out.append(FileEntry(display, size, real == canon_real, directory, key, False))
    return out, True


# ---------------------------------------------------------------- self-test


def _entries(canon: int, *project: Tuple[str, int, bool]) -> List[FileEntry]:
    """Набор модели zone-F: user-global плюс проектные файлы одного каталога `.`."""
    out = [make_user_global(canon)]
    for name, size, is_canon in project:
        out.append(FileEntry(name, size, is_canon, ".", None, False))
    return out


def self_test() -> List[str]:
    """Сверка модели с измерениями zone-F; возвращает список расхождений (пусто - успех)."""
    fails: List[str] = []
    canon = 55417  # снимок zone-F (F-704), не боевой файл
    kb = _entries(canon, ("AGENTS.md", canon, True))
    ab = _entries(canon, ("AGENTS.md", 37520, False), ("CLAUDE.md", 448, False))
    wa = _entries(canon, ("AGENTS.md", 23245, False), ("CLAUDE.md", 478, False))
    dw = _entries(canon)
    exact = [
        ("KB M=111177", kb, 111177, CLASS_ALL, 111177),
        ("KB M=111176", kb, 111176, CLASS_UG_OMITTED, 55790),
        ("KB M=98304", kb, 98304, CLASS_UG_OMITTED, 55789),
        ("AB M=93760", ab, 93760, CLASS_ALL, 93760),
        ("AB M=93759", ab, 93759, CLASS_UG_OMITTED, 38372),
        ("WA M=79515", wa, 79515, CLASS_ALL, 79515),
        ("WA M=79514", wa, 79514, CLASS_UG_OMITTED, 24127),
        ("DW M=55728", dw, 55728, CLASS_ALL, 55728),
        ("DW M=55731", dw, 55731, CLASS_ALL, 55728),
        ("DW M=55500", dw, 55500, CLASS_TRUNCATED, 55500),
        ("KB M=55500", kb, 55500, CLASS_TRUNCATED, 55500),
        ("AB M=30000", ab, 30000, CLASS_PROJECT_OMITTED, 831),
    ]
    for name, entries, maxbytes, cls, block in exact:
        got = render_plan(entries, maxbytes)
        if got.cls != cls or got.block_bytes != block:
            fails.append("%s: ожидалось %s/%d, получено %s/%d" % (name, cls, block, got.cls, got.block_bytes))
    # Усечение: реальная граница UTF-8 может быть на 1-3 Б ниже модельной (F-707).
    for name, entries, maxbytes, y_meas in (("KB M=40000", kb, 40000, 39580),
                                            ("KB M=55500", kb, 55500, 55081),
                                            ("DW M=55500", dw, 55500, 55093)):
        got = render_plan(entries, maxbytes)
        y_model = got.truncated[2] if got.truncated else -1
        if not (y_meas <= y_model <= y_meas + 3):
            fails.append("%s: усечение Y=%d вне [%d..%d]" % (name, y_model, y_meas, y_meas + 3))
    # Формула AD-006 совпадает с путь-зависимой моделью на типичных наборах.
    for name, entries in (("KB", kb), ("AB", ab), ("WA", wa), ("DW", dw)):
        formula = estimate_block_bytes(len(entries), sum(e.size for e in entries))
        model = _block(entries, "")
        if formula != model:
            fails.append("формула %s: %d != %d" % (name, formula, model))
    # Граница REQ-003 строгая.
    for value, ok in ((59999, True), (60000, True), (60001, False)):
        if block_within_limit(value) != ok:
            fails.append("граница 60000: %d -> %s" % (value, not ok))
    # Golden: равная длина, разное экранирование -> разные оценки, равные json.dumps.
    plain = "a" * 100
    quotes = '"' * 100
    newlines = "\n" * 100
    cyr = "я" * 100
    golden = ((plain, 102), (quotes, 202), (newlines, 202), (cyr, 202))
    for text, expected in golden:
        if journal_line_bytes_est(text) != expected:
            fails.append("golden journal_line_bytes_est(%r...) != %d" % (text[:3], expected))
    # Окно на снимке: запасы при 106 496 = 12 736 / 4 680.
    res = evaluate(canon, {"KB": kb[1:], "WA": wa[1:], "AB": ab[1:], "DW": []}, DEFAULT_MAXBYTES, ("KB",))
    if (res.lower_margin, res.upper_margin, res.exit_code) != (12736, 4680, 0):
        fails.append("окно снимка: %r/%r/exit %d" % (res.lower_margin, res.upper_margin, res.exit_code))
    if res.recommended != DEFAULT_MAXBYTES:
        fails.append("рекомендуемый maxBytes на снимке %r != %d" % (res.recommended, DEFAULT_MAXBYTES))
    return fails


# ---------------------------------------------------------------- CLI


def _say(message: str, stream=None) -> None:
    """Вывод CLI в stdout/stderr (встроенная печать в проекте не используется)."""
    (stream or sys.stdout).write(message + "\n")


def _safe_stdout() -> None:
    """Не падать на не-UTF-8 локали: пути кириллические, печатаем с заменой."""
    reconf = getattr(sys.stdout, "reconfigure", None)
    if reconf is not None:
        reconf(errors="backslashreplace")


def _fmt_margin(value: Optional[int]) -> str:
    return "n/a" if value is None else "%d" % value


def run_check(maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str) -> int:
    """Читает файлы, печатает прогноз по каждому cwd, запасы и причины; возвращает код выхода.

    REQ-003 строгий (strict_req003=True): превышение 60 000 Б блока/строки KB даёт exit 2.
    """
    try:
        canon_size = os.stat(canon_path).st_size
    except FileNotFoundError:
        _say("CANON_LOST: канон не найден: %s" % canon_path)
        return 2
    canon_real = os.path.realpath(canon_path)
    canon_text: Optional[str] = None
    try:
        with open(canon_path, "rb") as handle:
            canon_bytes = handle.read()
        canon_size = len(canon_bytes)
        canon_text = canon_bytes.decode("utf-8", "replace")
    except OSError:
        pass
    _say("mode=PLANNED maxbytes=%d canon=%s size=%d" % (maxbytes, canon_path, canon_size))
    cwd_files: Dict[str, Sequence[FileEntry]] = {}
    texts: Dict[str, Dict[str, str]] = {}
    exists: Dict[str, bool] = {}
    paths: Dict[str, str] = {}
    for label, path in cwds:
        texts[label] = {}
        files, ok = collect_cwd_entries(path, canon_real, texts[label])
        cwd_files[label] = files
        exists[label] = ok
        paths[label] = path
    req_labels = [label for label, path in cwds if path == KB_CWD]
    res = evaluate(canon_size, cwd_files, maxbytes, req_labels, strict_req003=True,
                   texts=texts, canon_text=canon_text)
    for label, _path in cwds:
        rend = (res.renders or {})[label]
        files = cwd_files[label]
        listing = ", ".join("%s=%d%s" % (f.display, f.size, "(canon)" if f.is_canon else "") for f in files) or "-"
        note = "" if exists[label] else " [cwd отсутствует]"
        canon_state = "present" if rend.canon_copies >= 1 else "LOST"
        dup_state = "RETURNED" if rend.canon_copies >= 2 else "absent"
        line_est, exact = (res.line_estimates or {})[label]
        _say("cwd[%s] %s%s" % (label, paths[label], note))
        _say("  files: %s" % listing)
        _say("  forecast block=%d class=%s sections=%d omitted=%s line_est=%d line_mode=%s canon=%s dup=%s"
              % (rend.block_bytes, rend.cls, len(rend.kept), ",".join(rend.omitted) or "-",
                 line_est, "exact" if exact else "size-estimate", canon_state, dup_state))
    _say("window=[%d..%s] maxbytes=%d" % (res.window_low, _fmt_margin(res.window_high), maxbytes))
    _say("lower_margin=%d upper_margin=%s line_margin=%s"
          % (res.lower_margin, _fmt_margin(res.upper_margin), _fmt_margin(res.line_margin)))
    _say("recommended_maxbytes=%s" % _fmt_margin(res.recommended))
    if res.reasons:
        for reason in res.reasons:
            _say("reason: %s" % reason)
    else:
        _say("OK: канон сохраняется везде, дубль в KB отсутствует; mode=PLANNED")
    _say("exit=%d" % res.exit_code)
    return res.exit_code


def _user_global_problem(canon_real: str, canon_bytes: bytes) -> Optional[str]:
    """Причина, по которой настоящий user-global файл не равен канону (None - равен).

    Рендер DSH берёт именно файл `UG_PATH`, а не канон: удалённый, подменённый по содержимому или
    перенацеленный симлинк означают, что канон в запросе пропал или заменён. Обычный файл допустим
    только как байтовая копия канона; симлинк - только на сам канон.
    """
    try:
        with open(UG_PATH, "rb") as handle:
            data = handle.read()
    except OSError:
        return "файл отсутствует или нечитаем"
    if os.path.islink(UG_PATH) and os.path.realpath(UG_PATH) != canon_real:
        return "симлинк указывает не на канон"
    if data != canon_bytes:
        return "содержимое отличается от канона"
    return None


def check_installed(maxbytes: int, cwds: Sequence[Tuple[str, str]], canon_path: str) -> Optional[Result]:
    """Тот же прогноз, что `run_check`, но без печати (для автоматического контура моста).

    None - канон не найден (CANON_LOST). Результат с exit_code 2 и причиной CANON_LOST - настоящий
    user-global `UG_PATH` удалён, изменён или указывает не на канон. REQ-003 строгий, как в рабочем CLI.
    Файлы читаются только для хеша и точной длины строки журнала; содержимое наружу не отдаётся.
    """
    try:
        with open(canon_path, "rb") as handle:
            canon_bytes = handle.read()
    except OSError:
        return None
    canon_text = canon_bytes.decode("utf-8", "replace")
    canon_real = os.path.realpath(canon_path)
    problem = _user_global_problem(canon_real, canon_bytes)
    if problem is not None:
        return Result(2, ["CANON_LOST user-global %s: %s" % (UG_DISPLAY, problem)], 0, None, None)
    cwd_files: Dict[str, Sequence[FileEntry]] = {}
    texts: Dict[str, Dict[str, str]] = {}
    for label, path in cwds:
        texts[label] = {}
        cwd_files[label], _ = collect_cwd_entries(path, canon_real, texts[label])
    req_labels = [label for label, path in cwds if path == KB_CWD]
    return evaluate(len(canon_bytes), cwd_files, maxbytes, req_labels, strict_req003=True,
                    texts=texts, canon_text=canon_text)


def parse_profile_maxbytes(text: str) -> Optional[int]:
    """maxBytes плагина agent-instructions внутри пресета `preset-standard` (YAML-патч профиля DSH).

    Построчный разбор без YAML-библиотеки: пресет - элемент верхнего уровня `- id: preset-standard`,
    плагин - `- id: agent-instructions` глубже, значение - единственная строка `maxBytes: <число>`
    пресета. Комментарии и другие пресеты игнорируются. Неоднозначность (повтор пресета или плагина,
    второй maxBytes в любом месте пресета, maxBytes вне плагина, нечисловое значение) и отсутствие
    значения - None: охранник считает такой профиль нечитаемым, а не берёт первое попавшееся число.
    """
    in_preset = False
    in_plugin = False
    presets = plugins = 0
    hits: List[Tuple[str, bool]] = []
    for line in text.splitlines():
        if re.match(r"^- id:", line):
            in_preset = re.match(r"^- id:\s*preset-standard\s*$", line) is not None
            presets += in_preset
            in_plugin = False
            continue
        if not in_preset:
            continue
        if re.match(r"^\s+- id:", line):
            in_plugin = re.match(r"^\s+- id:\s*agent-instructions\s*$", line) is not None
            plugins += in_plugin
            continue
        found = re.match(r"^\s+maxBytes:\s*(.*?)\s*$", line)
        if found:
            hits.append((found.group(1), in_plugin))
    if presets != 1 or plugins != 1 or len(hits) != 1 or not hits[0][1] or not (hits[0][0].isascii() and hits[0][0].isdigit()):
        return None
    return int(hits[0][0])


def find_profiles(profiles_dir: str) -> List[Tuple[str, str, Optional[int]]]:
    """Установленные профили: (имя, путь к cordis.patch.yml, maxBytes или None). Только чтение.

    Каталоги резервных копий (`*.bak*`) и каталоги без `cordis.patch.yml` пропускаются.
    Печатаются только имя, путь и число; остальное содержимое профиля не выводится.
    """
    if not os.path.isdir(profiles_dir):
        return []
    found: List[Tuple[str, str, Optional[int]]] = []
    for name in sorted(os.listdir(profiles_dir)):
        path = os.path.join(profiles_dir, name, PROFILE_FILE)
        if ".bak" in name or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                found.append((name, path, parse_profile_maxbytes(handle.read())))
        except OSError:
            found.append((name, path, None))
    return found


def run_profiles(profiles_dir: str, cwds: Sequence[Tuple[str, str]], canon_path: str) -> int:
    """Проверка установленных профилей: на каждом maxBytes - тот же прогноз, что и `--check`; итог - худший код."""
    profiles = find_profiles(profiles_dir)
    if not profiles:
        _say("профили не найдены: %s (ожидается <профиль>/%s)" % (profiles_dir, PROFILE_FILE))
        return 2
    worst = 0
    for name, path, maxbytes in profiles:
        if maxbytes is None:
            _say("profile=%s path=%s: maxBytes не найден (preset-standard / agent-instructions)" % (name, path))
            worst = 2
            continue
        _say("profile=%s path=%s maxBytes=%d" % (name, path, maxbytes))
        worst = max(worst, run_check(maxbytes, cwds, canon_path))
    _say("profiles exit=%d" % worst)
    return worst


def build_parser() -> argparse.ArgumentParser:
    """Парсер CLI: режимы self-test/check/profiles взаимоисключающие."""
    parser = argparse.ArgumentParser(prog="b_guard", description="Охранник B: прогноз блока agent-instructions DSH")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="сверить модель с границами zone-F")
    mode.add_argument("--check", action="store_true", help="прогноз по реальным размерам файлов (stat)")
    mode.add_argument("--profiles", action="store_true",
                      help="прочитать maxBytes установленных профилей DSH (только чтение) и проверить каждый")
    parser.add_argument("--maxbytes", type=int, default=DEFAULT_MAXBYTES, help="планируемый maxBytes")
    parser.add_argument("--cwd", action="append", default=None, metavar="PATH", help="cwd для проверки (повторяемый)")
    parser.add_argument("--canon", default=CANON_PATH, help="путь канона (для тестов)")
    parser.add_argument("--profiles-dir", default=PROFILES_DIR, metavar="PATH",
                        help="каталог профилей DSH для --profiles (по умолчанию ~/.dsh/profiles)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Точка входа: 0 - успех, 1 - мало запаса, 2 - потеря канона/дубль/превышение REQ-003/профили не найдены."""
    _safe_stdout()
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.self_test:
        fails = self_test()
        for item in fails:
            _say("SELF-TEST FAIL: %s" % item)
        _say("self-test: %s" % ("FAIL (%d)" % len(fails) if fails else "OK"))
        return 1 if fails else 0
    if args.cwd:
        # Известные пути получают свои метки (KB включает ограничение REQ-003), прочие - basename.
        known = {path: label for label, path in DEFAULT_CWDS}
        cwds = [(known.get(p, os.path.basename(p.rstrip("/")) or p), p) for p in args.cwd]
    else:
        cwds = list(DEFAULT_CWDS)
    if args.profiles:
        return run_profiles(args.profiles_dir, cwds, args.canon)
    return run_check(args.maxbytes, cwds, args.canon)


if __name__ == "__main__":
    sys.exit(main())
