"""LaTeX (the subset this project emits) -> MathML for HTML tables.

Presentation MathML written as one line, without a namespace: the HTML
parser puts <math> into the MathML namespace by itself.  Unknown commands
raise ValueError so that the caller can keep the LaTeX text instead.
"""
from __future__ import annotations

import re
import unicodedata

from . import latex_util as lu

TOKEN = re.compile(r"\\[A-Za-z]+|\\.|\s+|.", re.S)

# command name -> character
CHARS: dict[str, str] = {}
for _ch, _name in lu.GREEK.items():
    CHARS.setdefault(_name, _ch)
for _ch, _cmd in lu.SYMBOLS.items():
    if re.fullmatch(r"\\[A-Za-z]+", _cmd):
        CHARS.setdefault(_cmd[1:], _ch)
CHARS.update({
    "epsilon": "ϵ", "varepsilon": "ε", "phi": "ϕ", "varphi": "φ",
    "upsilon": "υ", "cdot": "⋅", "langle": "⟨", "rangle": "⟩",
    "ldots": "…", "dots": "…", "mid": "∣", "vert": "|", "Vert": "‖",
    "lbrace": "{", "rbrace": "}", "backslash": "\\", "to": "→",
    "leq": "≤", "geq": "≥", "neq": "≠", "dagger": "†", "ddagger": "‡",
    "prime": "′", "bullet": "•", "circ": "∘", "ast": "∗", "star": "⋆",
    "lnot": "¬", "land": "∧", "lor": "∨", "iff": "⇔", "implies": "⇒",
    "oplus": "⊕", "otimes": "⊗", "odot": "⊙", "pm": "±", "mp": "∓",
    "div": "÷", "times": "×", "partial": "∂", "nabla": "∇", "infty": "∞",
    "ell": "ℓ", "hbar": "ℏ", "emptyset": "∅", "forall": "∀",
    "exists": "∃", "in": "∈", "notin": "∉", "subset": "⊂",
    "supset": "⊃", "cup": "∪", "cap": "∩", "approx": "≈", "sim": "∼",
    "equiv": "≡", "propto": "∝", "ll": "≪", "gg": "≫", "perp": "⊥",
    "angle": "∠", "lceil": "⌈", "rceil": "⌉", "lfloor": "⌊",
    "rfloor": "⌋", "le": "≤", "ge": "≥", "ne": "≠", "surd": "√",
    "sum": "∑", "prod": "∏", "int": "∫", "oint": "∮", "iint": "∬",
    "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔",
    "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
    "mapsto": "↦", "uparrow": "↑", "downarrow": "↓", "cdots": "⋯",
    "vdots": "⋮", "ddots": "⋱", "top": "⊤", "aleph": "ℵ", "Re": "ℜ",
    "Im": "ℑ", "setminus": "∖",
})
BIGOPS = {"sum", "prod", "int", "oint", "iint", "bigcup", "bigcap"}
CHARS.update({"bigcup": "⋃", "bigcap": "⋂"})
FUNCS = {"log", "ln", "exp", "min", "max", "sin", "cos", "tan", "lim",
         "sup", "inf", "gcd", "det", "deg", "arg", "mod", "lg", "sinh",
         "cosh", "tanh", "cot", "sec", "csc", "arcsin", "arccos",
         "arctan", "limsup", "liminf"}
SPACE = {",": "0.17em", ";": "0.28em", ":": "0.22em", " ": "0.28em",
         "quad": "1em", "qquad": "2em", "!": "-0.17em"}
ACCENT = {"tilde": "˜", "hat": "ˆ", "bar": "¯", "vec": "→", "dot": "˙",
          "ddot": "¨", "widetilde": "˜", "widehat": "ˆ", "check": "ˇ",
          "overline": "‾", "overrightarrow": "→", "acute": "´",
          "grave": "`", "breve": "˘"}
STRETCH_ACCENT = {"widetilde", "widehat", "overline", "overrightarrow"}
UNDER = {"underline": "_"}
FONTS = {"mathrm": "rm", "textrm": "rm", "mathbf": "bf", "bf": "bf",
         "boldsymbol": "bi", "bm": "bi", "mathit": "it", "mathcal": "cal",
         "mathbb": "bb", "mathfrak": "frak", "mathsf": "rm",
         "mathtt": "rm", "operatorname": "rm"}
STYLE_NAME = {"bf": "BOLD", "bi": "BOLD ITALIC", "cal": "SCRIPT",
              "bb": "DOUBLE-STRUCK", "frak": "FRAKTUR"}
DELIMS = {"(": "(", ")": ")", "[": "[", "]": "]", "|": "|", "/": "/",
          "\\{": "{", "\\}": "}", "\\|": "‖", "<": "⟨", ">": "⟩"}
MATRIX_FENCE = {"matrix": "", "pmatrix": "()", "bmatrix": "[]",
                "Bmatrix": "{}", "vmatrix": "||", "Vmatrix": "‖‖",
                "smallmatrix": ""}
ESC = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}


def esc(s: str) -> str:
    return "".join(ESC.get(c, c) for c in s)


def styled(ch: str, style: str) -> str:
    """Mathematical alphanumeric variant of ``ch`` (or ``ch`` itself)."""
    kind = STYLE_NAME.get(style)
    if not kind:
        return ch
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return ch
    if name.startswith("LATIN"):
        tail = name.replace("LATIN ", "").replace(" LETTER", "")
    elif name.startswith("GREEK"):
        tail = name.replace("GREEK ", "").replace(" LETTER", "")
    elif name.startswith("DIGIT"):
        tail = name
    else:
        return ch
    for cand in (f"MATHEMATICAL {kind} {tail}",
                 f"MATHEMATICAL {kind.replace(' ITALIC', '')} {tail}"):
        try:
            return unicodedata.lookup(cand)
        except KeyError:
            continue
    return ch


class Parser:
    def __init__(self, tex: str):
        self.toks = TOKEN.findall(tex)
        self.i = 0

    # --------------------------------------------------------- tokens
    def peek(self) -> str | None:
        while self.i < len(self.toks) and self.toks[self.i].isspace():
            self.i += 1
        return self.toks[self.i] if self.i < len(self.toks) else None

    def next(self) -> str:
        t = self.peek()
        if t is None:
            raise ValueError("unexpected end")
        self.i += 1
        return t

    def expect(self, t: str):
        if self.next() != t:
            raise ValueError(f"expected {t}")

    # ---------------------------------------------------------- nodes
    @staticmethod
    def row(nodes: list[str]) -> str:
        return nodes[0] if len(nodes) == 1 else \
            "<mrow>" + "".join(nodes) + "</mrow>"

    def seq(self, style: str = "", stop: tuple = ()) -> list[str]:
        """Nodes up to (not including) a stop token or a closing brace."""
        out: list[str] = []
        while True:
            t = self.peek()
            if t is None or t == "}" or t in stop or \
                    t in ("&", "\\\\", "\\end", "\\right"):
                return out
            out.extend(self.item(style))

    def group(self, style: str = "") -> str:
        """``{...}`` or a single token as one node."""
        if self.peek() == "{":
            self.next()
            nodes = self.seq(style)
            self.expect("}")
            return self.row(nodes) if nodes else "<mrow></mrow>"
        return self.row(self.item(style, scripts=False))

    def raw_text(self) -> str:
        """Brace-balanced raw text (for \\text)."""
        self.peek()
        if self.toks[self.i] != "{":
            raise ValueError("\\text needs braces")
        self.i += 1
        depth, buf = 1, []
        while self.i < len(self.toks):
            t = self.toks[self.i]
            self.i += 1
            if t == "{":
                depth += 1
            elif t == "}":
                depth -= 1
                if depth == 0:
                    return "".join(buf)
            if len(t) == 2 and t[0] == "\\" and t[1] in "_%&#$ {}":
                t = t[1]
            elif t[0] == "\\" and len(t) > 1:
                raise ValueError(f"command {t} in \\text")
            buf.append(t)
        raise ValueError("unterminated \\text")

    # ---------------------------------------------------------- items
    def item(self, style: str, scripts: bool = True) -> list[str]:
        base, kind = self.atom(style)
        if not scripts:
            return [base]
        limits = False
        if kind == "op" and self.peek() == "\\limits":
            self.next()
            limits = True
        elif self.peek() == "\\nolimits":
            self.next()
        sub = sup = None
        while True:
            t = self.peek()
            if t == "_" and sub is None:
                self.next()
                sub = self.group(style)
            elif t == "^" and sup is None:
                self.next()
                sup = self.group(style)
            elif t == "'" and sup is None:
                self.next()
                n = 1
                while self.peek() == "'":
                    self.next()
                    n += 1
                sup = f"<mo>{'′' * n}</mo>"
            else:
                break
        if sub is None and sup is None:
            return [base]
        if limits:
            tag, args = (("munderover", (sub, sup)) if sub and sup else
                         ("munder", (sub,)) if sub else ("mover", (sup,)))
        else:
            tag, args = (("msubsup", (sub, sup)) if sub and sup else
                         ("msub", (sub,)) if sub else ("msup", (sup,)))
        return [f"<{tag}>{base}" + "".join(args) + f"</{tag}>"]

    def atom(self, style: str) -> tuple[str, str]:
        t = self.next()
        if t == "{":
            nodes = self.seq(style)
            self.expect("}")
            return (self.row(nodes) if nodes else "<mrow></mrow>"), "grp"
        if t[0] == "\\":
            return self.command(t[1:], style)
        return self.char(t, style), "plain"

    def char(self, c: str, style: str) -> str:
        if c.isdigit():
            n = c
            while self.i < len(self.toks) and self.toks[self.i].isdigit():
                n += self.toks[self.i]
                self.i += 1
            if (self.i + 1 < len(self.toks) and self.toks[self.i] == "."
                    and self.toks[self.i + 1].isdigit()):
                n += "."
                self.i += 1
                while self.i < len(self.toks) and \
                        self.toks[self.i].isdigit():
                    n += self.toks[self.i]
                    self.i += 1
            if style in STYLE_NAME:
                n = "".join(styled(d, style) if d.isdigit() else d
                            for d in n)
            return f"<mn>{n}</mn>"
        if c.isalpha():
            return self.letter(c, style)
        if c == "-":
            return "<mo>−</mo>"
        if c == "*":
            return "<mo>∗</mo>"
        if c == "'":
            return "<mo>′</mo>"
        if c in "+=<>(),;:/|!?.[]":
            if c in "([|":
                return f"<mo>{c}</mo>"
            return f"<mo>{esc(c)}</mo>"
        if c in "~":
            return "<mspace width=\"0.28em\"></mspace>"
        if c in "^_":
            raise ValueError("dangling script")
        raise ValueError(f"character {c!r}")

    def letter(self, c: str, style: str) -> str:
        if style == "rm":
            run = c
            while (self.i < len(self.toks) and self.toks[self.i].isalpha()
                   and self.toks[self.i].isascii()):
                run += self.toks[self.i]
                self.i += 1
            return f'<mi mathvariant="normal">{run}</mi>'
        return f"<mi>{styled(c, style)}</mi>"

    # ------------------------------------------------------- commands
    def command(self, name: str, style: str) -> tuple[str, str]:
        if name in FONTS:
            return self.group(FONTS[name]), "grp"
        if name in ("text", "mbox", "textit", "textbf", "hbox"):
            s = self.raw_text().replace(" ", " ")
            return f"<mtext>{esc(s)}</mtext>", "plain"
        if name == "frac" or name == "dfrac" or name == "tfrac":
            a = self.group(style)
            b = self.group(style)
            return f"<mfrac>{a}{b}</mfrac>", "plain"
        if name == "binom":
            a = self.group(style)
            b = self.group(style)
            return (f'<mrow><mo>(</mo><mfrac linethickness="0">{a}{b}'
                    "</mfrac><mo>)</mo></mrow>"), "plain"
        if name == "sqrt":
            if self.peek() == "[":
                self.next()
                idx = self.row(self.seq(style, stop=("]",)) or [""])
                self.expect("]")
                return f"<mroot>{self.group(style)}{idx}</mroot>", "plain"
            return f"<msqrt>{self.group(style)}</msqrt>", "plain"
        if name in ACCENT:
            x = self.group(style)
            stretch = "true" if name in STRETCH_ACCENT else "false"
            return (f'<mover accent="true">{x}<mo stretchy="{stretch}">'
                    f"{ACCENT[name]}</mo></mover>"), "plain"
        if name in UNDER:
            x = self.group(style)
            return (f'<munder accentunder="true">{x}<mo stretchy="true">'
                    "_</mo></munder>"), "plain"
        if name in ("left",):
            return self.fenced(style), "plain"
        if name == "begin":
            return self.environment(style), "plain"
        if name in FUNCS:
            return f"<mi>{name}</mi>", "plain"
        if name == "bmod":
            return "<mo>mod</mo>", "plain"
        if name in ("limits", "nolimits"):
            return "", "plain"
        if name in SPACE or (len(name) == 1 and name in SPACE):
            return f'<mspace width="{SPACE[name]}"></mspace>', "plain"
        if name in ("_", "%", "#", "$", "&"):
            return f"<mo>{esc(name)}</mo>", "plain"
        if name in ("{", "}"):
            return f"<mo>{name}</mo>", "plain"
        if name == "|":
            return "<mo>‖</mo>", "plain"
        if name in CHARS:
            ch = CHARS[name]
            if name in BIGOPS:
                return f"<mo>{ch}</mo>", "op"
            if ch.isalpha():
                return f"<mi>{styled(ch, style)}</mi>", "plain"
            if name in ("ldots", "dots", "cdots", "vdots", "ddots"):
                return f"<mo>{ch}</mo>", "plain"
            return f"<mo>{esc(ch)}</mo>", "plain"
        raise ValueError(f"unknown command \\{name}")

    def delim(self) -> str:
        t = self.next()
        if t == ".":
            return ""
        key = t if t[0] != "\\" or t in ("\\{", "\\}", "\\|") else \
            None
        if key and key in DELIMS:
            return DELIMS[key]
        if t[0] == "\\" and t[1:] in CHARS:
            return CHARS[t[1:]]
        raise ValueError(f"bad delimiter {t}")

    def fenced(self, style: str) -> str:
        left = self.delim()
        nodes = self.seq(style)
        if self.next() != "\\right":
            raise ValueError("missing \\right")
        right = self.delim()
        out = []
        if left:
            out.append(f'<mo fence="true" stretchy="true">{esc(left)}</mo>')
        out += nodes
        if right:
            out.append(f'<mo fence="true" stretchy="true">{esc(right)}</mo>')
        return "<mrow>" + "".join(out) + "</mrow>"

    def environment(self, style: str) -> str:
        self.expect("{")
        env = ""
        while self.peek() != "}":
            env += self.next()
        self.expect("}")
        spec = ""
        if env == "array":
            self.expect("{")
            while self.peek() != "}":
                spec += self.next()
            self.expect("}")
        rows: list[list[str]] = [[]]
        while True:
            cell = self.seq(style)
            rows[-1].append(self.row(cell) if cell else "<mrow></mrow>")
            t = self.next()
            if t == "&":
                continue
            if t == "\\\\":
                rows.append([])
                continue
            if t == "\\end":
                break
            raise ValueError(f"unexpected {t} in {env}")
        self.expect("{")
        end = ""
        while self.peek() != "}":
            end += self.next()
        self.expect("}")
        if end != env:
            raise ValueError(f"\\begin{{{env}}} closed by {end}")
        if len(rows) > 1 and rows[-1] == ["<mrow></mrow>"]:
            rows.pop()
        ncols = max(len(r) for r in rows)
        attr = ""
        if env in ("aligned", "split", "align", "eqnarray"):
            attr = (' columnalign="' + " ".join(
                "right" if k % 2 == 0 else "left"
                for k in range(ncols)) + '" columnspacing="0em"')
        elif env == "cases":
            attr = ' columnalign="left"'
        elif env == "array":
            al = {"l": "left", "c": "center", "r": "right"}
            cols = [al[c] for c in spec if c in al]
            if cols:
                attr = ' columnalign="' + " ".join(cols) + '"'
        elif env not in MATRIX_FENCE:
            raise ValueError(f"unknown environment {env}")
        table = "<mtable" + attr + ">" + "".join(
            "<mtr>" + "".join(f"<mtd>{c}</mtd>" for c in r) + "</mtr>"
            for r in rows) + "</mtable>"
        fence = "{" if env == "cases" else MATRIX_FENCE.get(env, "")
        if fence:
            lft = fence[0]
            rgt = fence[-1] if env != "cases" else ""
            parts = [f'<mo fence="true" stretchy="true">{esc(lft)}</mo>',
                     table]
            if rgt:
                parts.append(
                    f'<mo fence="true" stretchy="true">{esc(rgt)}</mo>')
            return "<mrow>" + "".join(parts) + "</mrow>"
        return table


def latex_to_mathml(tex: str) -> str:
    """One-line ``<math>`` element; raises ValueError if not convertible."""
    p = Parser(tex)
    nodes = p.seq()
    if p.peek() is not None:
        raise ValueError(f"unexpected {p.peek()!r}")
    return "<math>" + "".join(nodes) + "</math>"
