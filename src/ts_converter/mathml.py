"""MathML (as written by LibreOffice's MathType import) -> LaTeX."""
from __future__ import annotations

import re

from lxml import etree

from . import latex_util as lu

NS = "{http://www.w3.org/1998/Math/MathML}"
DELIM = {
    "{": r"\{", "}": r"\}", "(": "(", ")": ")", "[": "[", "]": "]",
    "|": "|", "‖": r"\|", "∥": r"\|", "⌊": r"\lfloor", "⌋": r"\rfloor",
    "⌈": r"\lceil", "⌉": r"\rceil", "〈": r"\langle", "〉": r"\rangle",
    "⟨": r"\langle", "⟩": r"\rangle", "⟦": r"\llbracket",
    "⟧": r"\rrbracket", "/": "/", "∣": "|",
}
BIGOPS = {"∑", "∏", "∫", "∬", "∮", "⋃", "⋂", "∐", "⨁", "⨂"}
OVER_ACCENT = dict(lu.ACCENT_CHARS)


def _tag(el) -> str:
    return el.tag.replace(NS, "") if isinstance(el.tag, str) else ""


class Converter:
    def __init__(self):
        self.warnings: list[str] = []
        self.italic = 0

    # ------------------------------------------------------------ nodes
    def node(self, el) -> str:
        t = _tag(el)
        fn = getattr(self, "n_" + t, None)
        if fn is None:
            self.warnings.append(f"unhandled <{t}>")
            return self.children(el)
        return fn(el)

    def children(self, el) -> str:
        return self.seq(list(el))

    def seq(self, kids: list) -> str:
        """Concatenate siblings, turning fence pairs into \\left\\right."""
        toks: list = []
        for k in kids:
            if _tag(k) == "mo" and k.get("fence") == "true" \
                    and k.get("stretchy", "true") == "true":
                ch = (k.text or "").strip()
                form = k.get("form", "prefix")
                toks.append(("fence", form, DELIM.get(ch, ch), k))
            else:
                toks.append(("txt", self.node(k), k))
        out: list[str] = []
        stack: list[int] = []
        for tk in toks:
            if tk[0] == "fence" and tk[1] == "prefix":
                stack.append(len(out))
                out.append(("open", tk[2]))
            elif tk[0] == "fence":
                if stack:
                    i = stack.pop()
                    inner = "".join(x if isinstance(x, str) else "" for x in
                                    out[i + 1:])
                    left = out[i][1]
                    del out[i:]
                    out.append(self.fenced(left, tk[2], inner,
                                           out_idx=i))
                else:
                    out.append(("close", tk[2]))
            else:
                out.append(tk[1])
        # unmatched fences
        res = []
        for x in out:
            if isinstance(x, str):
                res.append(x)
            elif x[0] == "open":
                res.append(rf"\bigl{x[1]} ")
            else:
                res.append(rf"\bigr{x[1]} ")
        return "".join(res)

    def fenced(self, left: str, right: str, inner: str, out_idx=0) -> str:
        return lu.fence(left, right, inner)

    # leaf
    def n_mi(self, el) -> str:
        s = el.text or ""
        mv = el.get("mathvariant")
        if mv == "normal" and len(s) > 1 and s.isalnum():
            return lu.word_to_latex(s)
        if mv == "normal" and len(s) == 1 and s.isalpha() and s.isascii():
            return rf"\mathrm{{{s}}}"
        return lu.text_to_latex(s)

    def n_mn(self, el) -> str:
        return lu.text_to_latex(el.text or "")

    def n_mo(self, el) -> str:
        s = (el.text or "").strip()
        if not s:
            return ""
        if s in ("{", "}"):
            return DELIM[s]
        return lu.text_to_latex(s)

    def n_mtext(self, el) -> str:
        s = el.text or ""
        if not s:
            return ""
        if self.italic:
            return lu.text_to_latex(s)
        return lu.upright_text(s)

    def n_ms(self, el) -> str:
        return lu.upright_text(el.text or "")

    def n_mspace(self, el) -> str:
        return ""

    def n_none(self, el) -> str:
        return ""

    def n_mprescripts(self, el) -> str:
        return ""

    # grouping
    def n_math(self, el) -> str:
        return self.children(el)

    n_semantics = n_mrow = n_mpadded = n_mtd = n_math

    def n_mstyle(self, el) -> str:
        it = el.get("mathvariant") == "italic"
        self.italic += it
        try:
            return self.children(el)
        finally:
            self.italic -= it

    def n_annotation(self, el) -> str:
        return ""

    def n_mphantom(self, el) -> str:
        return ""

    def n_menclose(self, el) -> str:
        return rf"\boxed{{{self.children(el)}}}"

    # scripts
    def _g(self, s: str) -> str:
        return "{" + lu.trim(s) + "}"

    def n_msub(self, el) -> str:
        b, s = list(el)[:2]
        return self.base(b) + "_" + self._g(self.node(s))

    def n_msup(self, el) -> str:
        b, s = list(el)[:2]
        return self.base(b) + "^" + self._g(self.node(s))

    def n_msubsup(self, el) -> str:
        b, s, p = list(el)[:3]
        return (self.base(b) + "_" + self._g(self.node(s)) + "^"
                + self._g(self.node(p)))

    def base(self, el) -> str:
        r = self.node(el)
        if _tag(el) in ("mrow",) and len(el) > 1 and not r.startswith("\\left"):
            return "{" + r + "}"
        return r if r else "{}"

    def n_mmultiscripts(self, el) -> str:
        kids = list(el)
        base = kids[0]
        rest = kids[1:]
        pre: list = []
        post = rest
        for i, k in enumerate(rest):
            if _tag(k) == "mprescripts":
                post, pre = rest[:i], rest[i + 1:]
                break

        def pair(ks):
            s = self.node(ks[0]) if len(ks) > 0 else ""
            p = self.node(ks[1]) if len(ks) > 1 else ""
            return ("_" + self._g(s) if lu.trim(s) else "") + (
                "^" + self._g(p) if lu.trim(p) else "")
        pre_s = pair(pre)
        res = ("{}" + pre_s if pre_s else "") + self.base(base)
        return res + pair(post)

    def n_mfrac(self, el) -> str:
        a, b = list(el)[:2]
        return rf"\frac{self._g(self.node(a))}{self._g(self.node(b))}"

    def n_msqrt(self, el) -> str:
        return rf"\sqrt{self._g(self.children(el))}"

    def n_mroot(self, el) -> str:
        a, b = list(el)[:2]
        return rf"\sqrt[{self.node(b)}]{self._g(self.node(a))}"

    def n_mover(self, el) -> str:
        b, o = list(el)[:2]
        bt = self.node(b)
        if _tag(o) == "mo" and (o.text or "").strip() in OVER_ACCENT:
            ch = (o.text or "").strip()
            cmd = OVER_ACCENT[ch]
            if cmd == "bar" and len(bt.strip()) > 1:
                cmd = "overline"
            elif cmd in ("hat", "tilde") and len(bt.strip()) > 1:
                cmd = "wide" + cmd
            elif cmd == "vec" and len(bt.strip()) > 1:
                cmd = "overrightarrow"
            return rf"\{cmd}{self._g(bt)}"
        return rf"\overset{self._g(self.node(o))}{self._g(bt)}"

    def n_munder(self, el) -> str:
        b, u = list(el)[:2]
        bt = lu.trim(self.node(b))
        if _tag(b) == "mo" and (b.text or "").strip() in BIGOPS or \
                bt in ("\\lim", "\\min", "\\max", "\\sup", "\\inf"):
            return rf"{bt}\limits_{self._g(self.node(u))}"
        if _tag(u) == "mo" and (u.text or "").strip() in ("_", "‾", "¯"):
            return rf"\underline{self._g(bt)}"
        return rf"\underset{self._g(self.node(u))}{self._g(bt)}"

    def n_munderover(self, el) -> str:
        b, u, o = list(el)[:3]
        bt = lu.trim(self.node(b))
        if _tag(b) == "mo" and (b.text or "").strip() in BIGOPS:
            return (rf"{bt}\limits_{self._g(self.node(u))}"
                    rf"^{self._g(self.node(o))}")
        return rf"\overset{self._g(self.node(o))}" \
               rf"{{\underset{self._g(self.node(u))}{self._g(bt)}}}"

    # tables
    def n_mtable(self, el) -> str:
        rows = []
        ncols = 1
        for tr in el:
            cells = [self.node(td).strip() for td in tr]
            ncols = max(ncols, len(cells))
            rows.append(cells)
        return self.table(rows, ncols)

    def table(self, rows, ncols) -> str:
        if ncols == 1:
            return (r"\begin{aligned}" + r"\\ ".join(r[0] for r in rows)
                    + r"\end{aligned}")
        return (r"\begin{matrix}" + r"\\ ".join(" & ".join(r)
                                                for r in rows)
                + r"\end{matrix}")

    def n_mtr(self, el) -> str:
        return " & ".join(self.node(c) for c in el)


def _fix_cases(tex: str) -> str:
    """``\\bigl\\{ \\begin{matrix}..`` -> cases."""
    pat = re.compile(r"\\bigl\\\{ \\begin\{(matrix|aligned)\}(.*?)"
                     r"\\end\{\1\}", re.S)
    return pat.sub(lambda m: lu.cases(
        [r.split(" & ") for r in m.group(2).split(r"\\ ")]), tex)


def mathml_to_latex(xml: str) -> tuple[str | None, list[str]]:
    try:
        root = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        return None, [f"xml error {e}"]
    conv = Converter()
    tex = conv.node(root)
    tex = _fix_cases(tex)
    tex = lu.tidy(tex)
    if not tex:
        return None, ["empty"]
    return tex, conv.warnings
