"""WMF helpers: embedded MathType data and text-record scraping."""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass

META_ESCAPE = 0x0626
META_EXTTEXTOUT = 0x0A32
META_TEXTOUT = 0x0521
META_CREATEFONT = 0x02FB
META_SELECTOBJECT = 0x012D
META_DELETEOBJECT = 0x01F0
META_SETTEXTALIGN = 0x012E
GRAPHICS = {0x0213, 0x0214, 0x0324, 0x0325, 0x041B, 0x0538, 0x0418,
            0x0817, 0x0418, 0x0415, 0x0816, 0x0A16}
APPS_KEY = b"AppsMFCC"
DS_MARK = b"Design Science, Inc.\x00"


@dataclass
class WmfRecord:
    func: int
    body: bytes


def records(data: bytes):
    """Yield WmfRecord for a (placeable) WMF file."""
    pos = 22 if data[:4] == b"\xd7\xcd\xc6\x9a" else 0
    if len(data) < pos + 18:
        return
    pos += 18
    while pos + 6 <= len(data):
        size, func = struct.unpack_from("<IH", data, pos)
        if size < 3:
            break
        yield WmfRecord(func, data[pos + 6:pos + size * 2])
        pos += size * 2


def embedded_mtef(data: bytes) -> bytes | None:
    """MTEF bytes stored by MathType in a picture, if any."""
    for r in records(data):
        if r.func != META_ESCAPE or len(r.body) < 4:
            continue
        code = struct.unpack_from("<H", r.body, 0)[0]
        if code != 15:  # MFCOMMENT
            continue
        payload = r.body[4:]
        if payload.startswith(APPS_KEY):
            i = payload.find(DS_MARK)
            if i >= 0:
                return payload[i + len(DS_MARK):]
    return None


@dataclass
class TextItem:
    x: int
    y: int
    text: bytes
    face: str
    height: int
    italic: bool
    weight: int
    align: int


def text_items(data: bytes) -> tuple[list[TextItem], dict]:
    """ExtTextOut items with font info; plus counts of other records."""
    fonts: dict[int, tuple[str, int, bool, int]] = {}
    table: list = []        # object table (None = free slot)
    cur_font = ("", 0, False, 400)
    align = 0
    items: list[TextItem] = []
    other: dict[int, int] = {}

    def alloc(obj):
        for i, o in enumerate(table):
            if o is None:
                table[i] = obj
                return
        table.append(obj)

    for r in records(data):
        b = r.body
        if r.func == META_CREATEFONT and len(b) >= 18:
            h, _w, _esc, _ori, weight = struct.unpack_from("<hhhhh", b, 0)
            italic = bool(b[10])
            name = b[18:].split(b"\x00")[0].decode("latin-1", "replace")
            alloc(("font", (name, abs(h), italic, weight)))
        elif r.func in (0x02FC, 0x02FA, 0x02FD, 0x00F7):  # brush/pen/...
            alloc(("other", None))
        elif r.func == META_SELECTOBJECT and len(b) >= 2:
            idx = struct.unpack_from("<H", b, 0)[0]
            if idx < len(table) and table[idx] and table[idx][0] == "font":
                cur_font = table[idx][1]
        elif r.func == META_DELETEOBJECT and len(b) >= 2:
            idx = struct.unpack_from("<H", b, 0)[0]
            if idx < len(table):
                table[idx] = None
        elif r.func == META_SETTEXTALIGN and len(b) >= 2:
            align = struct.unpack_from("<H", b, 0)[0]
        elif r.func == META_EXTTEXTOUT and len(b) >= 8:
            y, x, n, opts = struct.unpack_from("<hhhH", b, 0)
            off = 8 + (8 if opts & 6 else 0)
            txt = b[off:off + n]
            items.append(TextItem(x, y, txt, cur_font[0], cur_font[1],
                                  cur_font[2], cur_font[3], align))
        elif r.func == META_TEXTOUT and len(b) >= 4:
            n = struct.unpack_from("<h", b, 0)[0]
            txt = b[2:2 + n]
            pos = 2 + n + (n & 1)
            if len(b) >= pos + 4:
                y, x = struct.unpack_from("<hh", b, pos)
                items.append(TextItem(x, y, txt, cur_font[0], cur_font[1],
                                      cur_font[2], cur_font[3], align))
        elif r.func not in (META_ESCAPE, 0x0102, 0x0103, 0x0104, 0x0107,
                            0x0108, 0x0127, 0x012C, 0x012E, 0x012F,
                            0x0201, 0x0209, 0x020A, 0x020B, 0x020C,
                            0x0213, 0x0214, 0x0000, 0x0105, 0x0106):
            other[r.func] = other.get(r.func, 0) + 1
    return items, other


def text_latex(data: bytes) -> str:
    """LaTeX from the text records of a simple MathType picture.

    Handles sub/superscripts only; anything else (fractions, brackets,
    lines) returns '' so that the caller falls back to the image.
    """
    from . import latex_util as lu
    from . import symbolfont

    items, other = text_items(data)
    if not items or other:
        return ""
    if any(r.func in GRAPHICS for r in records(data)):
        return ""   # lines (fraction bars, radicals, overbars...)
    for it in items:
        if it.face == "Symbol" and any(
                b in symbolfont.BRACKET_PIECES for b in it.text):
            return ""
        if it.face not in ("Times New Roman", "Symbol", "Arial",
                           "Courier New") or it.align & 24 != 24:
            return ""

    def chars(it: TextItem) -> str:
        raw = it.text
        s = symbolfont.decode(raw) if it.face == "Symbol" else raw.decode(
            "cp1252", "replace")
        return s

    BRACKETS = set("()[]{}|")
    ACCENTS = {"~": "tilde", "˜": "tilde", "∼": "tilde", "^": "hat",
               "ˆ": "hat", "¯": "bar", "→": "vec", "˙": "dot", "¨": "ddot"}

    def is_bracket(it: TextItem) -> bool:
        s = chars(it)
        return len(s) == 1 and s in BRACKETS

    def is_accent(it: TextItem) -> bool:
        return chars(it).strip() in ACCENTS

    def emit(group: list[TextItem]) -> str | None:
        if not group:
            return ""
        accents = [i for i in group if is_accent(i)]
        rest = [i for i in group if not is_accent(i)]
        if not rest:
            return None
        h = max((i.height for i in rest if not is_bracket(i)),
                default=max(i.height for i in rest))
        main = [i for i in rest if i.height >= 0.9 * h or is_bracket(i)]
        flat = [i for i in main if not is_bracket(i)]
        base = sorted(i.y for i in flat)[len(flat) // 2] if flat else 0
        if any(abs(i.y - base) > 0.12 * h for i in flat):
            return None  # stacked main items: fraction etc.
        main.sort(key=lambda i: i.x)

        def centre(i: TextItem) -> float:
            return i.x + len(i.text) * i.height * 0.25
        scripts: dict[int, list[TextItem]] = {id(m): [] for m in main}
        acc_of: dict[int, str] = {}
        for it in sorted(rest, key=lambda i: i.x):
            if it in main:
                continue
            owner = None
            for m in main:
                if m.x <= it.x:
                    owner = m
            if owner is None:
                return None
            scripts[id(owner)].append(it)
        for ac in accents:
            near = min((m for m in main if not is_bracket(m)),
                       key=lambda m: abs(centre(m) - centre(ac)),
                       default=None)
            if near is None:
                return None
            acc_of[id(near)] = ACCENTS[chars(ac).strip()]
        out = []
        for m in main:
            tex = item_tex(m)
            if id(m) in acc_of:
                tex = "\\" + acc_of[id(m)] + "{" + tex + "}"
            subs = [i for i in scripts[id(m)] if i.y >= base]
            sups = [i for i in scripts[id(m)] if i.y < base]
            sub_t = sup_t = ""
            if subs:
                sub_t = emit(subs)
                if sub_t is None:
                    return None
            if sups:
                sup_t = emit(sups)
                if sup_t is None:
                    return None
            if subs or sups:
                tex = lu.add_script(tex or "{}", sub_t, sup_t)
            pr = re.fullmatch(r"'_\{(.*)\}", tex)
            sc = lu._trailing_scripts(out[-1]) if out and pr else []
            if sc and sc[0][0] == "sub":
                # P_{a} then a primed sub: P'_{a b} (not P_{a}'_{b})
                st = sc[0][1]
                out[-1] = (out[-1][:st] + "'_{" + out[-1][st + 2:-1]
                           + pr.group(1) + "}")
            else:
                out.append(tex)
            nxt = main[main.index(m) + 1] if main.index(m) + 1 < len(
                main) else None
            if nxt is not None and not is_bracket(nxt) and not is_bracket(m):
                end = max([m.x + len(m.text) * m.height * 0.5] + [
                    i.x + len(i.text) * i.height * 0.5
                    for i in scripts[id(m)]])
                if nxt.x - end > 0.9 * h:
                    out.append(r"\; ")
        return "".join(out)

    def item_tex(it: TextItem) -> str:
        s = chars(it)
        if not s.strip():
            return ""
        if it.italic and it.face != "Symbol":
            return lu.text_to_latex(s)
        if it.face == "Symbol":
            return lu.text_to_latex(s)
        return lu.upright_text(s)

    tex = emit(items)
    return lu.tidy(tex) if tex else ""
