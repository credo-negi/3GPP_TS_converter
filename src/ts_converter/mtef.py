"""MathType (MTEF v5) equation parser -> LaTeX.

Used for OLE equations that LibreOffice cannot import (ProgID
``Equation.DSMT*``, MTEF v5).  Spec: rtf2latex2e MTEF5 / Wiris docs.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

import olefile

from . import latex_util as lu

# record types
END, LINE, CHAR, TMPL, PILE, MATRIX, EMBELL, RULER = range(8)
FONT_STYLE_DEF, SIZE, FULL, SUB, SUB2, SYM, SUBSYM = range(8, 15)
COLOR, COLOR_DEF, FONT_DEF, EQN_PREFS, ENCODING_DEF = range(15, 20)
OPT_NUDGE, OPT_LP_RULER, OPT_LINE_LSPACE = 0x08, 0x02, 0x04
OPT_LINE_NULL = 0x01
OPT_CHAR_EMBELL, OPT_CHAR_FUNC_START = 0x01, 0x02
OPT_CHAR_ENC_CHAR_8, OPT_CHAR_ENC_CHAR_16 = 0x04, 0x10
OPT_CHAR_ENC_NO_MTCODE = 0x20

# typefaces
FN_TEXT, FN_FUNCTION, FN_VARIABLE, FN_LCGREEK, FN_UCGREEK = 1, 2, 3, 4, 5
FN_SYMBOL, FN_VECTOR, FN_NUMBER, FN_USER1, FN_USER2 = 6, 7, 8, 9, 10
FN_MTEXTRA, FN_TEXT_FE, FN_EXPAND, FN_MARKER, FN_SPACE = 11, 12, 22, 23, 24

# template selectors
(T_ANGLE, T_PAREN, T_BRACE, T_BRACK, T_BAR, T_DBAR, T_FLOOR, T_CEIL,
 T_OBRACK, T_INTERVAL, T_ROOT, T_FRACT, T_UBAR, T_OBAR, T_ARROW,
 T_INTEG, T_SUM, T_PROD, T_COPROD, T_UNION, T_INTER, T_INTOP, T_SUMOP,
 T_LIM, T_HBRACE, T_HBRACK, T_LDIV, T_SUB, T_SUP, T_SUBSUP, T_DIRAC,
 T_VEC, T_TILDE, T_HAT, T_ARC, T_JSTATUS, T_STRIKE, T_BOX) = range(38)

EMBELLS = {
    2: r"\dot{%s}", 3: r"\ddot{%s}", 4: r"\dddot{%s}", 5: "%s'",
    6: "%s''", 7: "%s{}^{\\backprime}", 8: r"\tilde{%s}", 9: r"\hat{%s}",
    10: r"\not{%s}", 11: r"\vec{%s}", 12: r"\overleftarrow{%s}",
    13: r"\overleftrightarrow{%s}", 14: r"\vec{%s}",
    15: r"\overleftarrow{%s}", 16: "%s", 17: r"\bar{%s}", 18: "%s'''",
    19: r"\overset{\frown}{%s}", 20: r"\overset{\smile}{%s}",
    24: r"\ddddot{%s}", 25: r"\underset{\cdot}{%s}",
    26: r"\underset{\cdot\cdot}{%s}", 29: r"\underline{%s}",
    30: r"\underset{\sim}{%s}", 33: r"\underrightarrow{%s}",
    34: r"\underleftarrow{%s}",
}
FENCES = {
    T_ANGLE: (r"\langle", r"\rangle"), T_PAREN: ("(", ")"),
    T_BRACE: (r"\{", r"\}"), T_BRACK: ("[", "]"), T_BAR: ("|", "|"),
    T_DBAR: (r"\|", r"\|"), T_FLOOR: (r"\lfloor", r"\rfloor"),
    T_CEIL: (r"\lceil", r"\rceil"), T_OBRACK: ("[", "]"),
}
BIGOPS = {T_SUM: r"\sum", T_PROD: r"\prod", T_COPROD: r"\coprod",
          T_UNION: r"\bigcup", T_INTER: r"\bigcap", T_INTOP: r"\int",
          T_SUMOP: r"\sum"}
# MTCode private-use / special points seen in 3GPP equations
MTCODE = {
    0xEF00: "", 0xEF01: "", 0xEF02: "", 0xEF03: "", 0xEF04: "",
    0xEB01: "", 0xEB02: "", 0xEB03: "", 0xEB04: "", 0xEB05: "",
    0xEB06: "", 0xEB07: "", 0xEB08: "", 0xEB09: "",
    0xF8E5: "", 0xF8F2: "", 0xF8F7: "",
    0x2212: "-", 0x00B7: r"\cdot ", 0x2217: "*", 0x2032: "'",
    0x2223: r"\mid ", 0x2225: r"\| ", 0x2026: r"\ldots ",
    0x22EF: r"\cdots ", 0x22EE: r"\vdots ", 0x22F1: r"\ddots ",
    0x03D5: r"\varphi ", 0x03C6: r"\phi ", 0x03F5: r"\epsilon ",
    0x03B5: r"\varepsilon ", 0x220B: r"\ni ", 0x2208: r"\in ",
}


@dataclass
class Char:
    code: int
    face: int
    embells: list[int] = field(default_factory=list)
    func_start: bool = False


@dataclass
class Line:
    items: list = field(default_factory=list)
    null: bool = False


@dataclass
class Tmpl:
    sel: int
    var: int
    slots: list = field(default_factory=list)


@dataclass
class Pile:
    lines: list = field(default_factory=list)
    halign: int = 0


@dataclass
class Matrix:
    rows: int
    cols: int
    cells: list = field(default_factory=list)


def _align_at_relation(row: str) -> str:
    """Insert '&' before the first top-level relation symbol."""
    depth = 0
    for i, ch in enumerate(row):
        if ch in "{(":
            depth += 1
        elif ch in "})":
            depth -= 1
        elif depth == 0 and ch in "=<>" and not row[:i].endswith("\\"):
            return row[:i] + "&" + row[i:]
    return "&" + row


def _brace(x: str) -> str:
    x = lu.trim(x)
    return x if re.fullmatch(r"[A-Za-z0-9]|\\[A-Za-z]+", x) else "{" + x + "}"


class MtefError(Exception):
    pass


class Reader:
    def __init__(self, data: bytes, pos: int = 0):
        self.d, self.p = data, pos

    def u8(self) -> int:
        if self.p >= len(self.d):
            raise MtefError("eof")
        b = self.d[self.p]
        self.p += 1
        return b

    def u16(self) -> int:
        lo = self.u8()
        return lo | (self.u8() << 8)

    def uint(self) -> int:
        b = self.u8()
        return self.u16() if b == 255 else b

    def cstr(self) -> bytes:
        s = bytearray()
        while True:
            b = self.u8()
            if b == 0:
                return bytes(s)
            s.append(b)

    def nudge(self):
        dx, dy = self.u8(), self.u8()
        if dx == 128 and dy == 128:
            self.u16()
            self.u16()


def parse_objects(r: Reader, depth: int = 0) -> list:
    """Read records until END (consumed) or end of data."""
    if depth > 200:
        raise MtefError("too deep")
    items: list = []
    while r.p < len(r.d):
        tag = r.u8()
        if tag == END:
            return items
        if tag == LINE:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            if opt & OPT_LINE_LSPACE:
                r.u16()
            if opt & OPT_LP_RULER:
                parse_ruler(r)
            if opt & OPT_LINE_NULL:
                items.append(Line(null=True))
            else:
                items.append(Line(parse_objects(r, depth + 1)))
        elif tag == CHAR:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            face = r.u8() - 128
            code = 0
            if not opt & OPT_CHAR_ENC_NO_MTCODE:
                code = r.u16()
            if opt & OPT_CHAR_ENC_CHAR_8:
                pos = r.u8()
                code = code or pos
            if opt & OPT_CHAR_ENC_CHAR_16:
                pos = r.u16()
                code = code or pos
            ch = Char(code, face, func_start=bool(opt & OPT_CHAR_FUNC_START))
            if opt & OPT_CHAR_EMBELL:
                while True:
                    t = r.u8()
                    if t == END:
                        break
                    if t != EMBELL:
                        raise MtefError(f"bad embell tag {t}")
                    eo = r.u8()
                    if eo & OPT_NUDGE:
                        r.nudge()
                    ch.embells.append(r.u8())
            items.append(ch)
        elif tag == TMPL:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            sel = r.u8()
            var = r.u8()
            if var & 0x80:
                var = (var & 0x7F) | (r.u8() << 8)
            r.u8()  # template-specific options
            items.append(Tmpl(sel, var, parse_objects(r, depth + 1)))
        elif tag == PILE:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            ha = r.u8()
            r.u8()
            if opt & OPT_LP_RULER:
                parse_ruler(r)
            items.append(Pile(parse_objects(r, depth + 1), ha))
        elif tag == MATRIX:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            r.u8(), r.u8(), r.u8()
            rows, cols = r.u8(), r.u8()
            r.p += ((rows + 1) * 2 + 7) // 8 + ((cols + 1) * 2 + 7) // 8
            items.append(Matrix(rows, cols, parse_objects(r, depth + 1)))
        elif tag == EMBELL:
            opt = r.u8()
            if opt & OPT_NUDGE:
                r.nudge()
            r.u8()
        elif tag == RULER:
            parse_ruler(r, tagged=True)
        elif tag == FONT_STYLE_DEF:
            r.uint()
            r.u8()
        elif tag == SIZE:
            b = r.u8()
            if b == 101:
                r.u16()
            elif b == 100:
                r.u8()
                r.u16()
            else:
                r.u8()
        elif FULL <= tag <= SUBSYM:
            pass
        elif tag == COLOR:
            r.uint()
        elif tag == COLOR_DEF:
            opt = r.u8()
            for _ in range(4 if opt & 1 else 3):
                r.u16()
            if opt & 4:
                r.cstr()
        elif tag == FONT_DEF:
            r.uint()
            r.cstr()
        elif tag == EQN_PREFS:
            r.u8()
            skip_dims(r)
            skip_dims(r)
            n = r.u8()
            for _ in range(n):
                if r.uint():
                    r.u8()
        elif tag == ENCODING_DEF:
            r.cstr()
        elif tag >= 100:
            n = r.uint()
            r.p += n
        else:
            raise MtefError(f"unknown tag {tag} at {r.p - 1}")
    return items


def parse_ruler(r: Reader, tagged: bool = False):
    n = r.u8()
    for _ in range(n):
        r.u8()
        r.u16()


def skip_dims(r: Reader):
    count = r.u8()
    nib: list[int] = []
    done = 0
    while done < count:
        if r.p >= len(r.d):
            raise MtefError("eof in prefs")
        b = r.u8()
        for n in (b >> 4, b & 15):
            nib.append(n)
        # a dimension: units nibble, then value nibbles up to 0xF
        while True:
            try:
                i = nib.index(0xF, 1)
            except ValueError:
                break
            del nib[:i + 1]
            done += 1
            if done >= count:
                break
    return


def parse_mtef(data: bytes) -> list:
    """Parse an MTEF stream (without the OLE header)."""
    if data[0] != 5:
        raise MtefError(f"MTEF version {data[0]} unsupported")
    r = Reader(data, 5)
    r.cstr()  # application key
    r.u8()    # equation options
    return parse_objects(r)


def read_equation_native(blob: bytes) -> bytes | None:
    """MTEF bytes from an OLE ``embeddings/*.bin`` blob."""
    try:
        ole = olefile.OleFileIO(io.BytesIO(blob))
        s = ole.openstream("Equation Native").read()
    except Exception:  # noqa: BLE001
        return None
    hdr = int.from_bytes(s[:2], "little")
    return s[hdr:]


# ---------------------------------------------------------------- LaTeX

class Emitter:
    def __init__(self):
        self.unknown: set[int] = set()

    # -- characters
    def char_text(self, c: Char) -> str:
        code = c.code
        if code in MTCODE:
            return MTCODE[code]
        if 0xE000 <= code <= 0xF8FF and code not in MTCODE:
            self.unknown.add(code)
            return ""
        if code == 0:
            return ""
        return lu.char_to_latex(chr(code)).rstrip() + (
            " " if lu.char_to_latex(chr(code)).startswith("\\")
            and lu.char_to_latex(chr(code)).rstrip()[-1].isalpha() else "")

    def run(self, chars: list[Char]) -> str:
        """Emit a run of consecutive plain characters."""
        out = []
        i = 0
        while i < len(chars):
            c = chars[i]
            if c.face in (FN_TEXT, FN_FUNCTION, FN_TEXT_FE) and not c.embells:
                j = i
                s = ""
                while (j < len(chars) and chars[j].face == c.face
                       and not chars[j].embells):
                    s += chr(chars[j].code) if chars[j].code else ""
                    j += 1
                out.append(self.text_run(s, c.face))
                i = j
                continue
            out.append(self.one_char(c))
            i += 1
        return "".join(out)

    def text_run(self, s: str, face: int) -> str:
        return lu.upright_text(s)

    def one_char(self, c: Char) -> str:
        t = self.char_text(c)
        if c.face == FN_VARIABLE and 0x41 <= c.code <= 0x7A:
            t = chr(c.code)
        elif c.face == FN_NUMBER and c.code < 128:
            t = chr(c.code)
        elif c.face == FN_SPACE:
            t = r"\," if c.code else ""
        for e in c.embells:
            f = EMBELLS.get(e)
            if f:
                t = f % (t if len(t.strip()) == 1 or "%s'" in f
                         else "{" + t + "}")
            else:
                self.unknown.add(1000 + e)
        return t

    # -- structure
    def line(self, ln) -> str:
        if isinstance(ln, Line):
            return self.items(ln.items) if not ln.null else ""
        return self.items([ln])

    def items(self, items: list) -> str:
        out: list[str] = []
        run: list[Char] = []

        def flush():
            if run:
                out.append(self.run(run))
                run.clear()

        i = 0
        while i < len(items):
            it = items[i]
            if isinstance(it, Char):
                run.append(it)
            else:
                flush()
                if isinstance(it, Tmpl) and it.sel in (T_SUB, T_SUP,
                                                       T_SUBSUP):
                    base = out.pop() if out else ""
                    out.append(self.script(it, base))
                else:
                    out.append(self.obj(it))
            i += 1
        flush()
        return "".join(out)

    def script(self, t: Tmpl, base: str) -> str:
        lines = [s for s in t.slots if isinstance(s, Line)]
        nonnull = [s for s in lines if not s.null]
        sub = sup = ""
        if t.sel == T_SUB:
            sub = self.line(nonnull[0]) if nonnull else ""
        elif t.sel == T_SUP:
            sup = self.line(nonnull[0]) if nonnull else ""
        else:
            if len(lines) >= 2:
                sub = self.line(lines[0]) if not lines[0].null else ""
                sup = self.line(lines[1]) if not lines[1].null else ""
        pre = bool(t.var & 1)
        res = ""
        if pre:
            if sub:
                res += "_{" + sub + "}"
            if sup:
                res += "^{" + sup + "}"
            return "{}" + res + base
        return lu.add_script(base or "{}", sub, sup)

    def fence_parts(self, t: Tmpl):
        lines = [s for s in t.slots if isinstance(s, Line)]
        return lines[0] if lines else Line(), lines[1:]

    def obj(self, it) -> str:
        if isinstance(it, Char):
            return self.one_char(it)
        if isinstance(it, Line):
            return self.line(it)
        if isinstance(it, Pile):
            return self.pile(it)
        if isinstance(it, Matrix):
            return self.matrix(it)
        if isinstance(it, Tmpl):
            return self.tmpl(it)
        return ""

    def pile(self, p: Pile, env: str = "array") -> str:
        """Vertical stack; halign 1 left, 2 centre, 3 right, 4 at '='."""
        rows = [self.line(ln) for ln in p.lines]
        if p.halign == 2:
            return (r"\begin{gathered}" + r"\\ ".join(rows)
                    + r"\end{gathered}")
        if p.halign == 4:
            rows = [_align_at_relation(r) for r in rows]
        elif p.halign == 1:
            rows = ["&" + r for r in rows]
        return r"\begin{aligned}" + r"\\ ".join(rows) + r"\end{aligned}"

    def matrix(self, m: Matrix) -> str:
        cells = [self.line(c) for c in m.cells]
        rows = []
        for r in range(m.rows):
            rows.append(" & ".join(cells[r * m.cols:(r + 1) * m.cols]))
        return lu.matrix(rows, m.cols)

    def tmpl(self, t: Tmpl) -> str:
        sel = t.sel
        lines = [s for s in t.slots if isinstance(s, Line)]

        def L(i):
            return self.line(lines[i]) if i < len(lines) else ""

        def nonnull(i):
            return i < len(lines) and not lines[i].null

        if sel in FENCES:
            lf, rt = FENCES[sel]
            left = lf if t.var & 1 else "."
            right = rt if t.var & 2 else "."
            main = lines[0] if lines else Line()
            inner = self.fence_inner(main, left, right)
            if left == "." or right == ".":
                if left == "." and right == ".":
                    return inner
                if inner.startswith((r"\begin{cases}", r"\left\{\begin{array}")):
                    return inner
                big = left if right == "." else right
                cmd = r"\bigl" if right == "." else r"\bigr"
                return rf"{cmd}{big} {inner}"
            return lu.fence(left, right, inner)
        if sel == T_INTERVAL:
            lf = ["(", ")", "[", "]"][t.var & 3]
            rt = ["(", ")", "[", "]"][(t.var >> 4) & 3]
            return lu.fence(lf, rt, L(0))
        if sel == T_ROOT:
            if nonnull(1):
                return rf"\sqrt[{L(1)}]{{{L(0)}}}"
            return rf"\sqrt{{{L(0)}}}"
        if sel == T_FRACT:
            if t.var & 2:
                return _brace(L(0)) + "/" + _brace(L(1))
            return rf"\frac{{{L(0)}}}{{{L(1)}}}"
        if sel == T_UBAR:
            return rf"\underline{{{L(0)}}}"
        if sel == T_OBAR:
            return rf"\overline{{{L(0)}}}"
        if sel == T_ARROW:
            top = L(0) if nonnull(0) else ""
            bot = L(1) if nonnull(1) else ""
            arrow = r"\xrightarrow" if not t.var & 0x10 else r"\xleftarrow"
            if t.var & 1:
                arrow = r"\xrightleftharpoons" if t.var & 2 else arrow
            res = arrow + (f"[{bot}]" if bot else "") + f"{{{top}}}"
            return res
        if sel in BIGOPS:
            op = BIGOPS[sel]
            if sel == T_INTEG:
                op = r"\int"
            main, upper, lower = L(0), "", ""
            if nonnull(1):
                lower = L(1)
            if nonnull(2):
                upper = L(2)
            lim = r"\limits" if sel != T_INTOP else ""
            res = op + (lim if (upper or lower) else "")
            if lower:
                res += "_{" + lower + "}"
            if upper:
                res += "^{" + upper + "}"
            return res + " " + main
        if sel == T_INTEG:
            n = t.var & 3
            op = [r"\int", r"\int", r"\iint", r"\iiint"][n] if n else (
                r"\oint")
            if t.var & 0xC:
                op = r"\oint"
            lower = L(1) if nonnull(1) else ""
            upper = L(2) if nonnull(2) else ""
            res = op
            if lower:
                res += "_{" + lower + "}"
            if upper:
                res += "^{" + upper + "}"
            return res + " " + L(0)
        if sel == T_LIM:
            lower = L(1) if nonnull(1) else ""
            upper = L(2) if nonnull(2) else ""
            m = lu.trim(L(0))
            res = (m if m.startswith("\\") else m)
            if lower:
                res += r"\limits_{" + lower + "}" if m.startswith(
                    "\\") else r"_{" + lower + "}"
            if upper:
                res += "^{" + upper + "}"
            return res
        if sel in (T_HBRACE, T_HBRACK):
            top = bool(t.var & 1)
            cmd = r"\overbrace" if top else r"\underbrace"
            res = cmd + "{" + L(0) + "}"
            if nonnull(1):
                res += ("^{" if top else "_{") + L(1) + "}"
            return res
        if sel == T_VEC:
            under = t.var & 4
            if under:
                return rf"\underrightarrow{{{L(0)}}}" if t.var & 2 else (
                    rf"\underleftarrow{{{L(0)}}}")
            if t.var & 1 and t.var & 2:
                return rf"\overleftrightarrow{{{L(0)}}}"
            return (rf"\overrightarrow{{{L(0)}}}" if t.var & 2
                    else rf"\overleftarrow{{{L(0)}}}")
        if sel == T_TILDE:
            return rf"\widetilde{{{L(0)}}}"
        if sel == T_HAT:
            return rf"\widehat{{{L(0)}}}"
        if sel == T_ARC:
            return rf"\overset{{\frown}}{{{L(0)}}}"
        if sel == T_STRIKE:
            return rf"\cancel{{{L(0)}}}"
        if sel == T_BOX:
            return rf"\boxed{{{L(0)}}}"
        if sel == T_LDIV:
            return rf"{L(1)}\overline{{\left){L(0)}\right.}}"
        if sel == T_DIRAC:
            return rf"\langle {L(0)} | {L(1)} \rangle"
        self.unknown.add(2000 + sel)
        return "".join(self.line(s) for s in lines)

    def fence_inner(self, main: Line, left: str, right: str) -> str:
        """Fence content; a lone pile/matrix on a left brace -> cases."""
        if len(main.items) == 1 and left == r"\{" and right == ".":
            it = main.items[0]
            if isinstance(it, Pile):
                return lu.cases([[self.line(ln)] for ln in it.lines])
            if isinstance(it, Matrix):
                cells = [self.line(c) for c in it.cells]
                return lu.cases([cells[r * it.cols:(r + 1) * it.cols]
                                 for r in range(it.rows)])
        return self.line(main)

    def top(self, items: list) -> str:
        lines = [x for x in items if isinstance(x, (Line, Pile))]
        if len(lines) == 1 and isinstance(lines[0], Line):
            return self.line(lines[0])
        if len(lines) == 1 and isinstance(lines[0], Pile):
            return self.pile(lines[0])
        return self.items(items)


def mtef_to_latex(blob: bytes) -> tuple[str | None, str]:
    """(latex, note) for an OLE equation blob; latex None on failure."""
    data = read_equation_native(blob)
    if not data:
        return None, "no Equation Native stream"
    try:
        items = parse_mtef(data)
    except MtefError as e:
        return None, f"mtef parse error: {e}"
    em = Emitter()
    tex = lu.trim(em.top(items))
    note = ""
    if em.unknown:
        note = "unknown:" + ",".join(hex(x) for x in sorted(em.unknown))
    return tex, note


# ------------------------------------------------------------ MTEF v3
V3_FENCE_VAR = {0: 3, 1: 1, 2: 2}      # both / left / right -> v5 flags
V3_BIGOPS = {29: T_SUM, 30: T_SUM, 31: T_PROD, 32: T_PROD, 33: T_COPROD,
             34: T_COPROD, 35: T_UNION, 36: T_UNION, 37: T_INTER,
             38: T_INTER, 42: T_INTOP, 43: T_SUMOP}


class Mtef3Error(MtefError):
    pass


def _v3_char_code(face: int, code: int, fonts: dict) -> int:
    """MTEF v3 CHAR value -> Unicode code point.

    Observed in 3GPP files: the 16-bit value is already Unicode for
    Greek / symbol faces; MT Extra (private) glyphs are kept apart.
    """
    if face == FN_MTEXTRA:
        # MT Extra glyphs seen in 3GPP files
        return {0xEE: 0x22EE, 0xEF: 0x22EF, 0x26: 0x2026}.get(
            code & 0xFF, 0xE100 + (code & 0xFF))
    if fonts.get(face, "").lower() == "symbol" and code < 0x100:
        from . import symbolfont
        return ord(symbolfont.SYMBOL.get(code, chr(code)))
    return code


def _v3_tmpl(sel: int, var: int, slots: list):
    """Normalise a v3 template to the v5 numbering used by Emitter."""
    if 0 <= sel <= 5:
        return Tmpl(sel, V3_FENCE_VAR.get(var, 3), slots)
    if sel in (6, 7):
        return Tmpl(sel, 3, slots)
    if sel == 13:
        return Tmpl(T_ROOT, var, slots)
    if sel == 14:
        return Tmpl(T_FRACT, 0, slots)
    if sel == 41:
        return Tmpl(T_FRACT, 2, slots)
    if sel in (15, 44):
        kind = {0: T_SUP, 1: T_SUB, 2: T_SUBSUP}.get(var, T_SUBSUP)
        return Tmpl(kind, 0, slots)   # 44 (LSCRIPT) is a right script too
    if sel == 16:
        return Tmpl(T_UBAR, var, slots)
    if sel == 17:
        return Tmpl(T_OBAR, var, slots)
    if sel in V3_BIGOPS:
        return Tmpl(V3_BIGOPS[sel], var, slots)
    if sel in (21, 22, 23, 24, 25, 26):
        n = {21: 1, 22: 2, 23: 3, 24: 1, 25: 2, 26: 3}[sel]
        contour = (sel == 21 and var in (3, 4)) or (sel == 24 and var == 2)
        return Tmpl(T_INTEG, 4 if contour else n, slots)
    if sel == 39:
        return Tmpl(T_LIM, var, slots)
    if sel == 27:
        return Tmpl(T_HBRACE, 1, slots)
    if sel == 28:
        return Tmpl(T_HBRACE, 0, slots)
    if sel == 46:
        return Tmpl(T_VEC, {0: 1, 1: 2, 2: 3}.get(var, 2) | 4, slots)
    if sel == 47:
        return Tmpl(T_VEC, {0: 1, 1: 2, 2: 3}.get(var, 2), slots)
    if sel in (48,):
        return Tmpl(T_ARC, 0, slots)
    raise Mtef3Error(f"unsupported v3 template {sel}")


def parse_objects_v3(r: Reader, fonts: dict, depth: int = 0) -> list:
    if depth > 200:
        raise Mtef3Error("too deep")
    items: list = []
    while r.p < len(r.d):
        b = r.u8()
        tag, opt = b & 0x0F, b >> 4
        if tag == END:
            return items
        if tag == LINE:
            if opt & 8:
                r.nudge()
            if opt & 4:
                r.u8()
            if opt & 2:
                parse_ruler(r)
            if opt & 1:
                items.append(Line(null=True))
            else:
                items.append(Line(parse_objects_v3(r, fonts, depth + 1)))
        elif tag == CHAR:
            if opt & 8:
                r.nudge()
            face = r.u8() - 128
            code = r.u16()
            ch = Char(_v3_char_code(face, code, fonts), face,
                      func_start=bool(opt & 1))
            if opt & 2:
                while True:
                    t = r.u8()
                    if t & 0x0F == END:
                        break
                    if t & 0x0F != EMBELL:
                        raise Mtef3Error(f"bad embell tag {t}")
                    if t >> 4 & 8:
                        r.nudge()
                    ch.embells.append(r.u16())   # 16-bit in v3
            items.append(ch)
        elif tag == TMPL:
            if opt & 8:
                r.nudge()
            sel, var, _o = r.u8(), r.u8(), r.u8()
            slots = parse_objects_v3(r, fonts, depth + 1)
            items.append(_v3_tmpl(sel, var, slots))
        elif tag == PILE:
            if opt & 8:
                r.nudge()
            ha = r.u8()
            r.u8()
            if opt & 2:
                parse_ruler(r)
            items.append(Pile(parse_objects_v3(r, fonts, depth + 1), ha))
        elif tag == MATRIX:
            if opt & 8:
                r.nudge()
            r.u8(), r.u8(), r.u8()
            rows, cols = r.u8(), r.u8()
            r.p += ((rows + 1) * 2 + 7) // 8 + ((cols + 1) * 2 + 7) // 8
            items.append(Matrix(rows, cols,
                                parse_objects_v3(r, fonts, depth + 1)))
        elif tag == EMBELL:
            if opt & 8:
                r.nudge()
            r.u16()
        elif tag == RULER:
            parse_ruler(r)
        elif tag == 8:            # FONT
            num = r.u8()
            r.u8()
            name = r.cstr().decode("latin-1")
            fonts[num - 128] = name
            fonts[-(256 - num) if num > 127 else -num] = name
        elif tag == SIZE:
            sb = r.u8()
            if sb == 101:
                r.u16()
            elif sb == 100:
                r.u8()
                r.u16()
            else:
                r.u8()
        elif FULL <= tag <= SUBSYM:
            pass
        else:
            raise Mtef3Error(f"unknown v3 tag {tag}")
    return items


def parse_mtef3(data: bytes) -> list:
    if data[0] != 3:
        raise Mtef3Error(f"not MTEF 3 ({data[0]})")
    return parse_objects_v3(Reader(data, 5), {})


def mtef_any_to_latex(blob: bytes) -> tuple[str | None, str]:
    """Own parser for any MTEF version (3 or 5)."""
    data = read_equation_native(blob)
    if not data:
        return None, "no Equation Native stream"
    try:
        items = parse_mtef3(data) if data[0] == 3 else parse_mtef(data)
    except MtefError as e:
        return None, f"mtef parse error: {e}"
    em = Emitter()
    tex = lu.trim(em.top(items))
    return lu.tidy(tex), ("unknown:" + ",".join(
        hex(x) for x in sorted(em.unknown)) if em.unknown else "")
