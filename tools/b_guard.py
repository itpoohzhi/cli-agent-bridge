#!/usr/bin/python3
"""Охранник B (AD-006): офлайн-прогноз размера блока agent-instructions в промпте DSH.

Зачем нужен. Плагин agent-instructions клиента DSH кладёт в запрос user-global канон
(`~/.dsh/AGENTS.md`) и проектные AGENTS.md/CLAUDE.md. В cwd=KB проектный AGENTS.md -
симлинк на тот же канон, поэтому при `maxBytes: 262144` канон попадает в запрос дважды
(блок 111 177 Б, строка session.v4.jsonl 113 105 Б, REQ-003). Правка `maxBytes` в
`preset-standard` до значения внутри окна [L .. U] выкидывает user-global-копию ровно там,
где она дублируется, и не трогает cwd без дубля. Окно зависит от размеров четырёх файлов
(канон и проектные файлы AB/WA), поэтому размеры надо проверять машинно - этот инструмент.

Что читает. ТОЛЬКО размеры (os.stat/os.lstat/os.path.realpath). Содержимое реальных
AGENTS.md/CLAUDE.md не открывается: канон нельзя утечь ни в лог, ни в диагностику.
Профили DSH не читаются и не пишутся (режим `--profiles` в dev-копии не реализован).

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

Метрики REQ-003 не смешиваются: block_bytes - длина текста блока (её считает этот
инструмент), journal_line_bytes - длина JSON-строки события в session.v4.jsonl
(`journal_line_bytes_est`; для прогноза запаса к блоку добавляется калиброванная обёртка
JOURNAL_WRAPPER_EST из F-712). Оба числа - ОЦЕНКА по размерам, не оракул приёмки.

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

Коды выхода `--check`: 0 - оба запаса >= 4096 Б и оценка запаса строки журнала до 60 000 Б
в KB >= 2048 Б; 1 - запас меньше порога (или блок/строка KB > 60 000 Б: причина
REQ003_SIZE_EXCEEDED, в этой dev-копии это предупреждение, `strict_req003=True` поднимает
до 2 - как в AD-006 дельта-4); 2 - канон теряется в каком-либо cwd (CANON_LOST) или дубль
возвращается (DUPLICATE_RETURNED). Граница 60 000 Б строгая: 60 000 проходит, 60 001 нет.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

CANON_PATH = "/Users/aazhiry1/Мой диск/Context/AGENTS.md"
KB_CWD = "/Users/aazhiry1/Мой диск/Работа/Sber/knowledge-base"
WA_CWD = "/Users/aazhiry1/src/saluteeye/gigabus/gigawebaccess/webaccess"
AB_CWD = "/Users/aazhiry1/Мой диск/Workshop/aibunker-workshop"
DW_CWD = "/Users/aazhiry1/Documents/deepseek-harness/default-workspace"
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
JOURNAL_WRAPPER_EST = 1225  # F-712: строка журнала KB (57 015) - блок (55 790)
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
    """Файл-кандидат: только размер и метаданные идентичности, без содержимого."""

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


def evaluate(
    canon_size: int,
    cwd_files: Dict[str, Sequence[FileEntry]],
    maxbytes: int,
    req003_cwds: Sequence[str] = (),
    strict_req003: bool = False,
) -> Result:
    """Чистая оценка окна maxBytes без файловой системы.

    `cwd_files` - метка cwd -> проектные файлы в порядке рендера (user-global добавляется
    здесь). `req003_cwds` - метки cwd, для которых действует ограничение 60 000 Б (по
    решению владельца REQ-003 принимается только в KB: для WA/AB условие недостижимо, F-724).
    """
    reasons: List[str] = []
    renders: Dict[str, RenderResult] = {}
    lowers: List[int] = []
    uppers: List[int] = []
    severe = False
    warn = False
    ug = make_user_global(canon_size)
    for label, files in cwd_files.items():
        entries = dedupe_entries([ug] + list(files))
        rend = render_plan(entries, maxbytes)
        renders[label] = rend
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
        line_est = rend.block_bytes + JOURNAL_WRAPPER_EST
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
                  renders, line_margin)


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


def collect_cwd_entries(cwd: str, canon_real: str) -> Tuple[List[FileEntry], bool]:
    """Проектные файлы цепочки root -> cwd по размерам; (список, cwd существует).

    Размер берётся через os.stat (симлинк следуется, как у клиента), идентичность - через
    realpath: симлинк на канон помечается is_canon, а один файл под двумя именами в одном
    каталоге схлопывается дедупом. Содержимое не читается.
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
            out.append(FileEntry(display, st.st_size, real == canon_real, directory, real, False))
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
    """Читает размеры, печатает прогноз по каждому cwd, запасы и причины; возвращает код выхода."""
    try:
        canon_size = os.stat(canon_path).st_size
    except FileNotFoundError:
        _say("CANON_LOST: канон не найден: %s" % canon_path)
        return 2
    canon_real = os.path.realpath(canon_path)
    _say("mode=PLANNED maxbytes=%d canon=%s size=%d" % (maxbytes, canon_path, canon_size))
    cwd_files: Dict[str, Sequence[FileEntry]] = {}
    exists: Dict[str, bool] = {}
    paths: Dict[str, str] = {}
    for label, path in cwds:
        files, ok = collect_cwd_entries(path, canon_real)
        cwd_files[label] = files
        exists[label] = ok
        paths[label] = path
    req_labels = [label for label, path in cwds if path == KB_CWD]
    res = evaluate(canon_size, cwd_files, maxbytes, req_labels)
    for label, _path in cwds:
        rend = (res.renders or {})[label]
        files = cwd_files[label]
        listing = ", ".join("%s=%d%s" % (f.display, f.size, "(canon)" if f.is_canon else "") for f in files) or "-"
        note = "" if exists[label] else " [cwd отсутствует]"
        canon_state = "present" if rend.canon_copies >= 1 else "LOST"
        dup_state = "RETURNED" if rend.canon_copies >= 2 else "absent"
        line_est = rend.block_bytes + JOURNAL_WRAPPER_EST
        _say("cwd[%s] %s%s" % (label, paths[label], note))
        _say("  files: %s" % listing)
        _say("  forecast block=%d class=%s sections=%d omitted=%s line_est=%d canon=%s dup=%s"
              % (rend.block_bytes, rend.cls, len(rend.kept), ",".join(rend.omitted) or "-",
                 line_est, canon_state, dup_state))
    _say("window=[%d..%s] maxbytes=%d" % (res.window_low, _fmt_margin(res.window_high), maxbytes))
    _say("lower_margin=%d upper_margin=%s line_margin=%s"
          % (res.lower_margin, _fmt_margin(res.upper_margin), _fmt_margin(res.line_margin)))
    _say("recommended_maxbytes=%s" % _fmt_margin(res.recommended))
    if res.reasons:
        for reason in res.reasons:
            _say("reason: %s" % reason)
    else:
        _say("OK: канон сохраняется везде, дубль в KB отсутствует; mode=PLANNED (профили не читались)")
    _say("exit=%d" % res.exit_code)
    return res.exit_code


def build_parser() -> argparse.ArgumentParser:
    """Парсер CLI: режимы self-test/check/profiles взаимоисключающие."""
    parser = argparse.ArgumentParser(prog="b_guard", description="Охранник B: прогноз блока agent-instructions DSH")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--self-test", action="store_true", help="сверить модель с границами zone-F")
    mode.add_argument("--check", action="store_true", help="прогноз по реальным размерам файлов (stat)")
    mode.add_argument("--profiles", action="store_true", help="чтение установленных профилей (не в dev-копии)")
    parser.add_argument("--maxbytes", type=int, default=DEFAULT_MAXBYTES, help="планируемый maxBytes")
    parser.add_argument("--cwd", action="append", default=None, metavar="PATH", help="cwd для проверки (повторяемый)")
    parser.add_argument("--canon", default=CANON_PATH, help="путь канона (для тестов)")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Точка входа: 0 - успех, 1 - мало запаса, 2 - потеря канона/дубль/не реализовано."""
    _safe_stdout()
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.profiles:
        _say("--profiles: not implemented in dev copy (профили DSH читать запрещено в этом проходе)",
             sys.stderr)
        return 2
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
    return run_check(args.maxbytes, cwds, args.canon)


if __name__ == "__main__":
    sys.exit(main())
