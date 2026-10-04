"""Independent glyph-sequence views of an equation, for comparisons.

``mathml_glyphs``  : the characters of a <math> element, in order
``latex_glyphs``   : the characters a LaTeX string stands for
``alnum``          : letters and digits only (to compare with the docx)
They do not use ts_converter.latex_mathml, so a converter bug shows up
as a difference.
"""
import re
import unicodedata

from lxml import etree

from tests import support  # noqa: F401
from ts_converter import latex_util as lu

NS = "http://www.w3.org/1998/Math/MathML"
LEAVES = {f"{{{NS}}}{t}" for t in ("mi", "mn", "mo", "mtext")}
SAME = str.maketrans({
    "−": "-", "∗": "*", "·": "⋅", "〈": "⟨", "〉": "⟩", "ˆ": "^",
    "˜": "~", "¯": "‾", "′": "'", "ϵ": "ε", "∣": "|", "‖": "∥",
    "…": "…", "∆": "Δ",
})
# commands that only shape the layout: they stand for no glyph
LAYOUT = {
    "frac", "dfrac", "tfrac", "sqrt", "binom", "left", "right", "begin",
    "end", "mathrm", "mathbf", "mathit", "mathcal", "mathbb", "mathfrak",
    "mathsf", "mathtt", "boldsymbol", "bm", "bf", "textrm", "operatorname",
    "limits", "nolimits", "quad", "qquad",
}
STAND_ALONE = {"bmod": "mod", "dots": "…", "dfrac": "", "to": "→"}
ACCENTS = {"tilde": "~", "hat": "^", "bar": "¯", "vec": "→", "dot": "˙",
           "ddot": "¨", "widetilde": "~", "widehat": "^",
           "overline": "‾", "overrightarrow": "→", "check": "ˇ",
           "acute": "´", "grave": "`", "breve": "˘"}
TEXT_CMDS = ("text", "mbox", "textit", "textbf", "hbox")
TOK = re.compile(r"\\[A-Za-z]+|\\.|\s+|.", re.S)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = "".join(s.split()).replace(" ", "")
    return s.translate(SAME)


CANON_ACC = {"˜": "~", "~": "~", "ˆ": "^", "^": "^", "¯": "¯", "‾": "¯",
             "→": "→", "˙": "˙", "¨": "¨", "ˇ": "ˇ", "´": "´", "`": "`",
             "˘": "˘"}


def _result(glyphs: list[str], accents: list[str]) -> str:
    """Glyphs in order, then the accents (their place is not compared)."""
    return norm("".join(glyphs)) + "|" + "".join(sorted(accents))


def mathml_glyphs(xml: str) -> str:
    root = etree.fromstring(xml.replace("<math>", f'<math xmlns="{NS}">', 1))
    glyphs, accents = [], []
    acc_nodes = []
    for e in root.iter(f"{{{NS}}}mover"):
        if e.get("accent") == "true":
            acc_nodes.append(e[1])
            accents.append(CANON_ACC[(e[1].text or "").strip()])
    for e in root.iter():
        if e.tag in LEAVES and not any(e is a for a in acc_nodes):
            glyphs.append(e.text or "")
    return _result(glyphs, accents)


def _inverse() -> dict[str, str]:
    inv = {}
    for ch, name in lu.GREEK.items():
        inv.setdefault(name, ch)
    for ch, cmd in lu.SYMBOLS.items():
        if re.fullmatch(r"\\[A-Za-z]+", cmd):
            inv.setdefault(cmd[1:], ch)
    inv.update({"varepsilon": "ε", "epsilon": "ε", "phi": "ϕ",
                "varphi": "φ", "le": "≤", "ge": "≥", "ne": "≠",
                "lceil": "⌈", "rceil": "⌉", "lfloor": "⌊",
                "rfloor": "⌋", "langle": "⟨", "rangle": "⟩"})
    return inv


INV = _inverse()
FUNC = {"log", "ln", "exp", "min", "max", "sin", "cos", "tan", "lim",
        "sup", "inf", "gcd", "det", "deg", "arg", "mod"}


def latex_glyphs(tex: str) -> str:
    toks = TOK.findall(tex)
    out: list[str] = []
    accents: list[str] = []
    i = 0
    after_fence = False
    closers: list[tuple[int, str]] = []   # (token index, glyphs) to add
    while i <= len(toks):
        while closers and i >= closers[-1][0]:
            out.append(closers.pop()[1])
        if i == len(toks):
            break
        t = toks[i]
        i += 1
        if t.isspace() or t in "{}&_^":
            continue
        if t == "\\\\":
            continue
        if t[0] != "\\":
            if after_fence:
                after_fence = False
                if t == ".":
                    continue
            out.append(t)
            continue
        name = t[1:]
        if name in ("left", "right"):
            after_fence = True
            continue
        if after_fence:
            after_fence = False
            if name in ("{", "}"):
                out.append(name)
                continue
            if name == "|":
                out.append("‖")
                continue
        if name in ("begin", "end"):
            # skip {env} (and the {cols} of an array)
            while i < len(toks) and toks[i].isspace():
                i += 1
            env = ""
            if i < len(toks) and toks[i] == "{":
                i += 1
                while toks[i] != "}":
                    env += toks[i]
                    i += 1
                i += 1
            if name == "begin" and env == "array":
                while toks[i] != "}":
                    i += 1
                i += 1
            if name == "begin" and env == "cases":
                out.append("{")
            if name == "begin" and env in ("pmatrix", "bmatrix"):
                out.append("(" if env == "pmatrix" else "[")
            if name == "end" and env in ("pmatrix", "bmatrix"):
                out.append(")" if env == "pmatrix" else "]")
            continue
        if name in TEXT_CMDS:
            while toks[i] != "{":
                i += 1
            i += 1
            depth = 1
            while depth:
                x = toks[i]
                i += 1
                depth += (x == "{") - (x == "}")
                if depth:
                    out.append(x[1] if len(x) == 2 and x[0] == "\\" else x)
            continue
        if name == "binom":
            closers.append((_after_groups(toks, i, 2), ")"))
            out.append("(")
            continue
        if name == "sqrt" and toks[i] == "[":     # the index comes last
            j = toks.index("]", i)
            closers.append((_after_groups(toks, j + 1, 1),
                            "".join(toks[i + 1:j])))
            i = j + 1
            continue
        if name in LAYOUT:
            continue
        if name in FUNC:
            out.append(name)
        elif name in STAND_ALONE:
            out.append(STAND_ALONE[name])
        elif name in ACCENTS:
            accents.append(CANON_ACC[ACCENTS[name]])
        elif name in INV:
            out.append(INV[name])
        elif name in ("limits", ",", ";", ":", " ", "!"):
            continue
        elif name in "_%#$&{}":
            out.append(name)
        else:
            raise ValueError(f"no glyph for \\{name}")
    return _result(out, accents)


def _after_groups(toks: list[str], i: int, n: int) -> int:
    """Index just after ``n`` brace groups starting at ``i``."""
    for _ in range(n):
        while toks[i].isspace():
            i += 1
        depth = 0
        while True:
            depth += (toks[i] == "{") - (toks[i] == "}")
            i += 1
            if depth == 0:
                break
    return i


def alnum(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return "".join(c for c in s if c.isalnum())


def omml_text(el) -> str:
    """The m:t texts of an OMML equation (what Word shows)."""
    M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
    return alnum("".join(t.text or "" for t in el.iter(f"{{{M}}}t")))


def mathml_alnum(xml: str) -> str:
    return alnum(mathml_glyphs(xml).rsplit("|", 1)[0])
