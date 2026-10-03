"""Shared helpers to turn math characters/text into LaTeX."""
from __future__ import annotations

import re
import unicodedata

GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon",
    "ϵ": "epsilon", "ζ": "zeta", "η": "eta", "θ": "theta", "ϑ": "vartheta",
    "ι": "iota", "κ": "kappa", "λ": "lambda", "μ": "mu", "µ": "mu",
    "ν": "nu", "ξ": "xi", "π": "pi", "ϖ": "varpi", "ρ": "rho",
    "ϱ": "varrho", "σ": "sigma", "ς": "varsigma", "τ": "tau",
    "υ": "upsilon", "φ": "varphi", "ϕ": "phi", "χ": "chi", "ψ": "psi",
    "ω": "omega", "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta",
    "Λ": "Lambda", "Ξ": "Xi", "Π": "Pi", "Σ": "Sigma", "Υ": "Upsilon",
    "Φ": "Phi", "Ψ": "Psi", "Ω": "Omega",
}
# Greek capitals that look like Latin letters
GREEK_LATIN = {"Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I",
               "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T",
               "Χ": "X", "ο": "o"}

SYMBOLS = {
    "−": "-", "–": "-", "—": "-", "‐": "-", "‑": "-", "﹣": "-", "－": "-",
    "×": r"\times", "·": r"\cdot", "⋅": r"\cdot", "∙": r"\cdot",
    "•": r"\bullet", "∗": "*", "∘": r"\circ", "°": r"^{\circ}",
    "±": r"\pm", "∓": r"\mp", "÷": r"\div", "⊗": r"\otimes",
    "⊕": r"\oplus", "⊙": r"\odot", "∑": r"\sum", "∏": r"\prod",
    "∫": r"\int", "∬": r"\iint", "∮": r"\oint", "√": r"\surd",
    "∞": r"\infty", "∂": r"\partial", "∇": r"\nabla", "ℓ": r"\ell",
    "ℏ": r"\hbar", "ℜ": r"\Re", "ℑ": r"\Im", "ℵ": r"\aleph",
    "∅": r"\emptyset", "∈": r"\in", "∉": r"\notin", "∋": r"\ni",
    "⊂": r"\subset", "⊃": r"\supset", "⊆": r"\subseteq",
    "⊇": r"\supseteq", "∪": r"\cup", "∩": r"\cap", "∖": r"\setminus",
    "∧": r"\wedge", "∨": r"\vee", "¬": r"\neg", "∀": r"\forall",
    "∃": r"\exists", "∴": r"\therefore", "∵": r"\because",
    "≤": r"\le", "≥": r"\ge", "≦": r"\le", "≧": r"\ge", "⩽": r"\le",
    "⩾": r"\ge", "≠": r"\ne", "≈": r"\approx", "≃": r"\simeq",
    "≅": r"\cong", "≡": r"\equiv", "∼": r"\sim", "∝": r"\propto",
    "≪": r"\ll", "≫": r"\gg", "⊥": r"\perp", "∥": r"\parallel",
    "∠": r"\angle", "△": r"\triangle", "→": r"\rightarrow",
    "←": r"\leftarrow", "↔": r"\leftrightarrow", "⇒": r"\Rightarrow",
    "⇐": r"\Leftarrow", "⇔": r"\Leftrightarrow", "↦": r"\mapsto",
    "↑": r"\uparrow", "↓": r"\downarrow", "⌊": r"\lfloor",
    "⌋": r"\rfloor", "⌈": r"\lceil", "⌉": r"\rceil", "〈": r"\langle",
    "〉": r"\rangle", "⟨": r"\langle", "⟩": r"\rangle", "…": r"\ldots",
    "⋯": r"\cdots", "⋮": r"\vdots", "⋱": r"\ddots", "′": "'",
    "″": "''", "‴": "'''", "′": "'", "∣": r"\mid", "‖": r"\|",
    "∥": r"\|", "|": "|", "‘": "'", "’": "'", "“": "``", "”": "''",
    "ˆ": r"\hat{}", "‾": r"\overline{}", "~": r"\sim",
    "∶": ":", "∕": "/", "⁄": "/", "￼": "",
    "{": r"\{", "}": r"\}", "%": r"\%", "&": r"\&", "#": r"\#",
    "$": r"\$", "_": r"\_", "\\": r"\backslash", "^": r"\hat{}",
    "<": "<", ">": ">", "⊤": r"\top", "†": r"\dagger", "‡": r"\ddagger",
    "∆": r"\Delta", "Ω": r"\Omega",
}
SPACES = {
    " ": r"\ ", " ": r"\ ", " ": r"\;", " ": r"\quad ",
    " ": r"\;", " ": r"\;", " ": r"\,", " ": r"\,",
    " ": r"\,", " ": r"\,", " ": r"\;", " ": r"\,",
    "​": "", "⁠": "", "⁡": "", "⁢": "", "⁣": "",
    "⁤": "", "﻿": "", "\t": r"\ ",
}
COMBINING = {
    "̂": "hat", "̃": "tilde", "̄": "bar", "̅": "bar",
    "̇": "dot", "̈": "ddot", "̌": "check", "́": "acute",
    "̀": "grave", "̆": "breve", "⃗": "vec", "⃖": "vec",
    "̱": "underline",
}
ACCENT_CHARS = {
    "̂": "hat", "ˆ": "hat", "^": "hat", "̃": "tilde", "˜": "tilde",
    "~": "tilde", "̄": "bar", "¯": "bar", "‾": "bar", "̅": "bar",
    "⃗": "vec", "→": "vec", "⃖": "overleftarrow", "←": "overleftarrow",
    "˙": "dot", "̇": "dot", "¨": "ddot", "̈": "ddot", "̌": "check",
    "ˇ": "check", "́": "acute", "´": "acute", "̀": "grave", "`": "grave",
    "̆": "breve", "˘": "breve", "⏞": "overbrace", "⏟": "underbrace",
    "↔": "overleftrightarrow", "⃡": "overleftrightarrow",
    "°": "mathring", "˚": "mathring",
}
FUNCTIONS = {
    "sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos",
    "arctan", "sinh", "cosh", "tanh", "coth", "log", "ln", "lg", "exp",
    "min", "max", "sup", "inf", "lim", "det", "gcd", "arg", "deg", "dim",
    "ker", "Pr", "mod",
}
SCRIPT_FONTS = {"script": "mathcal", "double-struck": "mathbb",
                "fraktur": "mathfrak", "sans-serif": "mathsf",
                "monospace": "mathtt", "bold-script": "mathcal",
                "bold-fraktur": "mathfrak"}
PUNCT_CHARS = "(),;:=<>[]{}|!?.+*/'\""
PUNCT_SPLIT = "([" + re.escape(PUNCT_CHARS) + "]+)"
PUNCT_FULL = re.compile("[" + re.escape(PUNCT_CHARS) + "]+")
_TEXT_ESC = {"_": r"\_", "%": r"\%", "&": r"\&", "#": r"\#", "$": r"\$",
             "{": r"\{", "}": r"\}", "\\": r"\textbackslash{}",
             "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}


def escape_text(s: str) -> str:
    """Escape a string for ``\\text{}``."""
    out = []
    for ch in s:
        if ch in _TEXT_ESC:
            out.append(_TEXT_ESC[ch])
        elif ch in (" ", " ", " ", " "):
            out.append(" ")
        elif ch in ("−", "–", "—", "‐", "‑"):
            out.append("-")
        elif ch in GREEK:
            out.append(rf"\ensuremath{{\{GREEK[ch]}}}")
        elif ch in SYMBOLS and ch not in "|<>":
            out.append(rf"\ensuremath{{{SYMBOLS[ch]}}}")
        else:
            out.append(ch)
    return "".join(out)


def char_to_latex(ch: str) -> str:
    """One math-mode character -> LaTeX token (with trailing space
    when a command could swallow the next letter)."""
    if ch in SPACES:
        return SPACES[ch]
    if ch in GREEK:
        return "\\" + GREEK[ch] + " "
    if ch in GREEK_LATIN:
        return GREEK_LATIN[ch]
    if ch in SYMBOLS:
        v = SYMBOLS[ch]
        return v + " " if v.startswith("\\") and v[-1].isalpha() else v
    if ch.isascii():
        return ch
    name = unicodedata.name(ch, "")
    if name.startswith("MATHEMATICAL"):
        # math alphanumerics -> base letter with style
        base = unicodedata.normalize("NFKC", ch)
        if "DOUBLE-STRUCK" in name:
            return rf"\mathbb{{{base}}}"
        if "SCRIPT" in name:
            return rf"\mathcal{{{base}}}"
        if "FRAKTUR" in name:
            return rf"\mathfrak{{{base}}}"
        if "BOLD" in name:
            return rf"\mathbf{{{base}}}"
        return base
    if name.startswith("SUPERSCRIPT") or name.startswith("SUBSCRIPT"):
        base = unicodedata.normalize("NFKC", ch)
        op = "^" if name.startswith("SUPERSCRIPT") else "_"
        return f"{op}{{{base}}}"
    nf = unicodedata.normalize("NFKC", ch)
    if nf != ch and all(c.isascii() for c in nf):
        return nf
    return ch  # leave as is; reported by the validator


_SYM_CLASS = "".join(sorted(
    {c for c in list(SYMBOLS) + list(GREEK) if not c.isascii()}))
_SPLIT_RE = re.compile(
    "([" + re.escape(PUNCT_CHARS) + re.escape(_SYM_CLASS) + "]+)")
_FULL_RE = re.compile(
    "[" + re.escape(PUNCT_CHARS) + re.escape(_SYM_CLASS) + "]+")


def split_punct(s: str) -> list[tuple[bool, str]]:
    """Split into (is_punct, text) parts."""
    return [(bool(_FULL_RE.fullmatch(p)), p)
            for p in _SPLIT_RE.split(s) if p]


def punct_to_latex(s: str) -> str:
    return "".join(char_to_latex(c) for c in s)


def word_to_latex(s: str) -> str:
    """Upright word -> LaTeX (\\mathrm / function / text)."""
    if not s.strip():
        return r"\ " if s else ""
    st = s.strip()
    if st in ("-", "–", "−"):
        return "-"
    if st == "mod":
        return r"\bmod "
    if st in FUNCTIONS:
        return "\\" + st + " "
    if s.isascii() and s.isdigit():
        return s
    if s.isascii() and s.isalnum():
        return rf"\mathrm{{{s}}}"
    if "-" in s and re.search(r"\d-|-\d", s) and " " not in s:
        return "-".join(word_to_latex(x) if x else "" for x in s.split("-"))
    return rf"\text{{{escape_text(s)}}}"


def upright_text(s: str) -> str:
    """Upright text with punctuation kept in math mode."""
    if not s.strip():
        return r"\ " if s else ""
    out = []
    for chunk in re.split(r"(\s*\bmod\b\s*)", s):
        if chunk.strip() == "mod":
            out.append(r"\bmod ")
            continue
        for is_p, part in split_punct(chunk):
            out.append(punct_to_latex(part) if is_p
                       else word_to_latex(part))
    return _ldots("".join(out))


_EDGE_SPACE = re.compile(r"^(?:\\[ ,;]|\s)+|(?:\\[ ,;]|\s)+$")


def trim(tex: str) -> str:
    """strip() that also removes the TeX spaces ``\\ \\, \\;`` at the ends
    (a plain strip() would leave a dangling backslash)."""
    return _EDGE_SPACE.sub("", tex)


def _ldots(tex: str) -> str:
    return re.sub(r"(?<![.\d])\.\.\.(?!\.)", r"\\ldots ", tex)


def tidy(tex: str) -> str:
    """Final cosmetic clean-ups."""
    tex = _ldots(tex)
    while True:      # \mathrm{a}\mathrm{b} -> \mathrm{ab}
        new = re.sub(r"\\mathrm\{([^{}]*)\}\\mathrm\{([^{}]*)\}",
                     r"\\mathrm{\1\2}", tex)
        if new == tex:
            break
        tex = new
    tex = re.sub(r"\s+", " ", tex)
    return trim(tex)


def text_to_latex(s: str, style: str | None = None) -> str:
    """Convert the text of a math run (OMML) to LaTeX.

    style: None (default italic), 'p' (upright), 'b', 'bi', 'nor'
    (normal text) or a script font name.
    """
    s = s.replace("\u2061", "")
    if style == "nor":
        return upright_text(s)
    # attach combining marks to their base character
    pieces: list[str] = []
    chars = list(s)
    i = 0
    while i < len(chars):
        ch = chars[i]
        j = i + 1
        marks = []
        while j < len(chars) and chars[j] in COMBINING:
            marks.append(COMBINING[chars[j]])
            j += 1
        base = char_to_latex(ch)
        for m in marks:
            base = f"\\{m}{{{base.strip()}}}"
        pieces.append(base)
        i = j
    out = "".join(pieces)
    if style == "p":
        return upright_text(s) if all(
            c not in COMBINING for c in s) else out
    word = bool(s) and all(c.isalnum() or c == "-" for c in s)
    if style == "b" and word:
        return rf"\mathbf{{{out}}}"
    if style == "bi" and word:
        return rf"\boldsymbol{{{out}}}"
    if style in SCRIPT_FONTS and word:
        return rf"\{SCRIPT_FONTS[style]}{{{out}}}"
    return out


ALIGN = "\x01"          # alignment marker, resolved by the callers


def right_delim(d: str) -> str:
    """Right delimiter with a trailing space when it is a command."""
    return d + " " if d[-1:].isalpha() else d


def fence(left: str, right: str, inner: str) -> str:
    return rf"\left{left} {inner} \right{right_delim(right)}"


def cases(rows: list[list[str]]) -> str:
    """``cases`` for <= 2 columns, else a left-aligned array."""
    ncols = max((len(r) for r in rows), default=1)
    body = r"\\ ".join(" & ".join(r) for r in rows)
    if ncols <= 2:
        return r"\begin{cases}" + body + r"\end{cases}"
    return (r"\left\{\begin{array}{" + "l" * ncols + "}" + body
            + r"\end{array}\right.")
