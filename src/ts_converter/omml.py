"""OMML (Office Math Markup Language) -> LaTeX."""
from __future__ import annotations

import re

from lxml import etree

from . import latex_util as lu

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NAMED_OPS = {"lim", "min", "max", "sup", "inf", "log", "ln", "sin", "cos",
             "tan", "exp", "det", "gcd", "arg", "mod"}
NARY = {"∑": r"\sum", "∏": r"\prod", "∐": r"\coprod", "∫": r"\int",
        "∬": r"\iint", "∭": r"\iiint", "∮": r"\oint", "⋃": r"\bigcup",
        "⋂": r"\bigcap", "⋁": r"\bigvee", "⋀": r"\bigwedge",
        "⨁": r"\bigoplus", "⨂": r"\bigotimes"}
DELIMS = {
    "(": "(", ")": ")", "[": "[", "]": "]", "{": r"\{", "}": r"\}",
    "|": "|", "‖": r"\|", "∥": r"\|", "⌊": r"\lfloor", "⌋": r"\rfloor",
    "⌈": r"\lceil", "⌉": r"\rceil", "〈": r"\langle", "〉": r"\rangle",
    "⟨": r"\langle", "⟩": r"\rangle", "⟦": r"\llbracket",
    "⟧": r"\rrbracket", "": ".",
}


def q(tag: str) -> str:
    return f"{{{M}}}{tag}"


def _local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


class Converter:
    def __init__(self):
        self.warnings: list[str] = []

    # helpers
    def prop(self, el, ppr: str, name: str, default=None):
        pr = el.find(q(ppr))
        if pr is None:
            return default
        node = pr.find(q(name))
        if node is None:
            return default
        return node.get(q("val"), default if default is not None else "1")

    def kid(self, el, name: str) -> str:
        sub = el.find(q(name))
        return self.seq(sub) if sub is not None else ""

    def seq(self, el) -> str:
        out: list[str] = []
        for k in el:
            if _local(k).endswith("Pr"):
                continue
            out.append(self.node(k))
        return "".join(out)

    def g(self, s: str) -> str:
        return "{" + lu.trim(s) + "}"

    def node(self, el) -> str:
        name = _local(el)
        fn = getattr(self, "n_" + name, None)
        if fn is None:
            if name in ("ctrlPr", "rPr"):
                return ""
            if name.endswith("Pr"):
                return ""
            self.warnings.append(f"unhandled m:{name}")
            return self.seq(el)
        return fn(el)

    # run
    def n_r(self, el) -> str:
        text = "".join(t.text or "" for t in el
                       if _local(t) == "t")
        if not text:
            return ""
        rpr = el.find(q("rPr"))
        style = None
        prefix = ""
        if rpr is not None:
            if rpr.find(q("nor")) is not None:
                style = "nor"
            else:
                sty = rpr.find(q("sty"))
                if sty is not None:
                    style = sty.get(q("val"))
                    if style == "i":
                        style = None
                scr = rpr.find(q("scr"))
                if scr is not None and scr.get(q("val")) not in (
                        None, "roman") and style is None:
                    style = scr.get(q("val"))
            if rpr.find(q("aln")) is not None:
                prefix = lu.ALIGN
        return prefix + lu.text_to_latex(text, style)

    # structures
    def n_oMathPara(self, el) -> str:
        rows = [self.node(c) for c in el if _local(c) == "oMath"]
        body = r"\\ ".join(rows)
        if len(rows) > 1 or lu.ALIGN in body:
            return (r"\begin{aligned}" + body.replace(lu.ALIGN, "&")
                    + r"\end{aligned}")
        return body

    def n_oMath(self, el) -> str:
        return self.seq(el)

    n_e = n_num = n_den = n_sub = n_sup = n_deg = n_lim = n_fName = n_oMath

    def n_f(self, el) -> str:
        num, den = self.kid(el, "num"), self.kid(el, "den")
        ftype = self.prop(el, "fPr", "type", "bar")
        if ftype == "noBar":
            return rf"\binom{self.g(num)}{self.g(den)}"
        if ftype in ("skw", "lin"):
            return self.g(num) + "/" + self.g(den)
        return rf"\frac{self.g(num)}{self.g(den)}"

    def n_sSub(self, el) -> str:
        return self.base(self.kid(el, "e")) + "_" + self.g(
            self.kid(el, "sub"))

    def n_sSup(self, el) -> str:
        return self.base(self.kid(el, "e")) + "^" + self.g(
            self.kid(el, "sup"))

    def n_sSubSup(self, el) -> str:
        return (self.base(self.kid(el, "e")) + "_"
                + self.g(self.kid(el, "sub")) + "^"
                + self.g(self.kid(el, "sup")))

    def n_sPre(self, el) -> str:
        return ("{}_" + self.g(self.kid(el, "sub")) + "^"
                + self.g(self.kid(el, "sup")) + self.base(
                    self.kid(el, "e")))

    def base(self, s: str) -> str:
        """Group a script base unless it is already one token."""
        s = lu.trim(s)
        if not s:
            return "{}"
        if (len(s) == 1 or re.fullmatch(r"\\[A-Za-z]+", s)
                or s.startswith("\\left") and s.endswith(tuple(
                    "|)]}.") ) or _balanced_single(s)
                or re.fullmatch(r"\\[A-Za-z]+\{.*\}", s) and
                _balanced_single(s[s.index("{"):])):
            return s
        return lu.group(s)

    def n_rad(self, el) -> str:
        e = self.kid(el, "e")
        hide = self.prop(el, "radPr", "degHide", "0")
        deg = self.kid(el, "deg")
        if hide in ("1", "on", "true") or not lu.trim(deg):
            return rf"\sqrt{self.g(e)}"
        return rf"\sqrt[{lu.trim(deg)}]{self.g(e)}"

    def n_d(self, el) -> str:
        pr = el.find(q("dPr"))
        beg, end, sep = "(", ")", "|"
        if pr is not None:
            b = pr.find(q("begChr"))
            if b is not None:
                beg = b.get(q("val"), "")
            e = pr.find(q("endChr"))
            if e is not None:
                end = e.get(q("val"), "")
            s = pr.find(q("sepChr"))
            if s is not None:
                sep = s.get(q("val"), "")
        items = [self.seq(c) for c in el if _local(c) == "e"]
        sep_t = DELIMS.get(sep, lu.char_to_latex(sep)) if sep else ""
        inner = (" " + sep_t + " ").join(lu.trim(i) for i in items)
        lb = DELIMS.get(beg, lu.char_to_latex(beg))
        rb = DELIMS.get(end, lu.char_to_latex(end))
        # cases environment: left brace, no right fence, matrix inside
        if beg == "{" and end == "" and len(items) == 1 and \
                items[0].startswith(r"\begin{matrix}"):
            body = items[0][len(r"\begin{matrix}"):-len(r"\end{matrix}")]
            return lu.cases([lu.split_top(r, " & ")
                             for r in lu.split_top(body, r"\\ ")])
        return lu.fence(lb, rb, inner)

    def n_m(self, el) -> str:
        rows = []
        ncols = 1
        for mr in el:
            if _local(mr) != "mr":
                continue
            cells = [self.seq(e) for e in mr if _local(e) == "e"]
            ncols = max(ncols, len(cells))
            rows.append(" & ".join(cells))
        return lu.matrix([r.replace(lu.ALIGN, "") for r in rows], ncols)

    def n_eqArr(self, el) -> str:
        rows = [self.seq(e) for e in el if _local(e) == "e"]
        return (r"\begin{aligned}" + r"\\ ".join(rows).replace(
            lu.ALIGN, "&") + r"\end{aligned}")

    def n_nary(self, el) -> str:
        pr = el.find(q("naryPr"))
        chr_ = "∫"
        undovr = False
        sub_hide = sup_hide = False
        if pr is not None:
            c = pr.find(q("chr"))
            if c is not None:
                chr_ = c.get(q("val"), "")
            ll = pr.find(q("limLoc"))
            undovr = ll is not None and ll.get(q("val")) == "undOvr"
            sh = pr.find(q("subHide"))
            sub_hide = sh is not None and sh.get(q("val"), "1") in (
                "1", "on", "true")
            ph = pr.find(q("supHide"))
            sup_hide = ph is not None and ph.get(q("val"), "1") in (
                "1", "on", "true")
        op = NARY.get(chr_, lu.char_to_latex(chr_).strip())
        sub = "" if sub_hide else self.kid(el, "sub")
        sup = "" if sup_hide else self.kid(el, "sup")
        res = op
        if undovr and (sub or sup):
            res += r"\limits"
        if lu.trim(sub):
            res += "_" + self.g(sub)
        if lu.trim(sup):
            res += "^" + self.g(sup)
        return res + " " + self.base(self.kid(el, "e"))

    def n_func(self, el) -> str:
        name = lu.trim(self.kid(el, "fName"))
        arg = self.kid(el, "e")
        return name + " " + arg

    def n_limLow(self, el) -> str:
        e = lu.trim(self.kid(el, "e"))
        lim = self.kid(el, "lim")
        if e.lstrip("\\").rstrip() in NAMED_OPS or e.startswith("\\mathrm"):
            return e + (r"\limits_" + self.g(lim) if lu.trim(lim) else "")
        return rf"\underset{self.g(lim)}{self.g(e)}"

    def n_limUpp(self, el) -> str:
        e = lu.trim(self.kid(el, "e"))
        lim = self.kid(el, "lim")
        return rf"\overset{self.g(lim)}{self.g(e)}"

    def n_acc(self, el) -> str:
        chr_ = "̂"
        pr = el.find(q("accPr"))
        if pr is not None:
            c = pr.find(q("chr"))
            if c is not None:
                chr_ = c.get(q("val"), "")
        e = lu.trim(self.kid(el, "e"))
        cmd = lu.ACCENT_CHARS.get(chr_) or lu.COMBINING.get(chr_)
        if cmd is None:
            self.warnings.append(f"accent {chr_!r}")
            return e
        single = len(e) == 1 or (e.startswith("\\") and e[1:].isalpha())
        if not single and cmd in ("hat", "tilde"):
            cmd = "wide" + cmd
        if not single and cmd == "bar":
            cmd = "overline"
        if not single and cmd == "vec":
            cmd = "overrightarrow"
        return rf"\{cmd}{self.g(e)}"

    def n_bar(self, el) -> str:
        pos = self.prop(el, "barPr", "pos", "top")
        e = self.kid(el, "e")
        return (rf"\underline{self.g(e)}" if pos == "bot"
                else rf"\overline{self.g(e)}")

    def n_groupChr(self, el) -> str:
        chr_ = self.prop(el, "groupChrPr", "chr", "⏟")
        e = self.kid(el, "e")
        pos = self.prop(el, "groupChrPr", "pos", "bot")
        if chr_ in ("⏞", "︷"):
            return rf"\overbrace{self.g(e)}"
        if chr_ in ("⏟", "︸"):
            return rf"\underbrace{self.g(e)}"
        cmd = r"\overset" if pos == "top" else r"\underset"
        return rf"{cmd}{self.g(lu.char_to_latex(chr_))}{self.g(e)}"

    def n_borderBox(self, el) -> str:
        return rf"\boxed{self.g(self.kid(el, 'e'))}"

    def n_box(self, el) -> str:
        return self.kid(el, "e")

    def n_phant(self, el) -> str:
        return ""

    def n_bookmarkStart(self, el) -> str:
        return ""

    n_bookmarkEnd = n_proofErr = n_bookmarkStart

    def n_t(self, el) -> str:
        return el.text or ""


def _balanced_single(s: str) -> bool:
    """True if s is ``{...}`` or ``\\cmd{...}`` (one top-level group)."""
    i = s.find("{")
    if i < 0 or not re.fullmatch(r"(\\[A-Za-z]+)?", s[:i]):
        return False
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return j == len(s) - 1
    return False


def omml_to_latex(el) -> tuple[str, list[str]]:
    """Convert an m:oMath / m:oMathPara element."""
    conv = Converter()
    tex = conv.node(el)
    return lu.tidy(tex.replace(lu.ALIGN, "")), conv.warnings
