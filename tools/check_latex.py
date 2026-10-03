"""Compile every LaTeX formula found in the generated Markdown.

usage: python tools/check_latex.py <md-dir> [...]
Reports formulas that make pdflatex fail (needs a TeX installation).
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

PREAMBLE = r"""\documentclass{article}
\usepackage{amsmath,amssymb,cancel}
\begin{document}
\sloppy
"""
INLINE = re.compile(r"(?<!\$)\$(?!\$)((?:[^$\\]|\\.)+?)\$(?!\$)")
DISPLAY = re.compile(r"\$\$(.+?)\$\$")


def formulas(mddirs: list[Path]) -> list[str]:
    seen: dict[str, None] = {}
    for d in mddirs:
        for f in sorted(d.glob("*.md")):
            for line in f.read_text("utf-8").splitlines():
                for m in DISPLAY.finditer(line):
                    seen.setdefault(m.group(1))
                rest = DISPLAY.sub("", line)
                for m in INLINE.finditer(rest):
                    seen.setdefault(m.group(1))
    return list(seen)


def check(forms: list[str], chunk: int = 400) -> list[tuple[str, str]]:
    bad: list[tuple[str, str]] = []
    for s in range(0, len(forms), chunk):
        part = forms[s:s + chunk]
        lines = [PREAMBLE]
        first = len(lines)
        for f in part:
            lines.append(f"\\par $\\displaystyle {f}$\n")
        lines.append("\\end{document}\n")
        with tempfile.TemporaryDirectory() as td:
            tex = Path(td) / "t.tex"
            tex.write_text("".join(lines), "utf-8")
            subprocess.run(["pdflatex", "-interaction=nonstopmode",
                            "-halt-on-error" if False else "-file-line-error",
                            "t.tex"], cwd=td, capture_output=True,
                           timeout=900)
            log = (Path(td) / "t.log").read_text("utf-8", "replace")
        # file-line-error: "./t.tex:LINE: message"
        src_lines = "".join(lines).split("\n")
        for m in re.finditer(r"t\.tex:(\d+): (.*)", log):
            ln = int(m.group(1))
            if 0 < ln <= len(src_lines):
                text = src_lines[ln - 1]
                mm = re.match(r"\\par \$\\displaystyle (.*)\$$", text)
                if mm:
                    bad.append((mm.group(1), m.group(2)))
    return bad


def main():
    dirs = [Path(a) for a in sys.argv[1:]]
    forms = formulas(dirs)
    print(f"{len(forms)} unique formulas")
    bad = check(forms)
    uniq: dict[str, str] = {}
    for f, msg in bad:
        uniq.setdefault(f, msg)
    print(f"{len(uniq)} formulas with errors")
    for f, msg in list(uniq.items())[:40]:
        print("-", msg, "::", f[:200])
    return 1 if uniq else 0


if __name__ == "__main__":
    sys.exit(main())
