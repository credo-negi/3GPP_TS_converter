"""Check the project documents: <= 200 lines, <= 50 chars per line.

usage: python tools/check_docs.py [files...]
Without arguments it checks CLAUDE.md, README.md and docs/**/*.md.
Characters are counted as Unicode code points (len of the line).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAX_LINES = 200
MAX_CHARS = 50


def targets(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    files = [ROOT / "CLAUDE.md", ROOT / "README.md"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.exists()]


def check(path: Path) -> list[str]:
    problems = []
    lines = path.read_text("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) > MAX_LINES:
        problems.append(f"{len(lines)} lines (max {MAX_LINES})")
    for i, line in enumerate(lines, 1):
        n = len(line)
        if n > MAX_CHARS:
            problems.append(f"line {i}: {n} chars (max {MAX_CHARS})")
    return problems


def main(argv: list[str]) -> int:
    bad = 0
    for f in targets(argv):
        probs = check(f)
        n = len(f.read_text("utf-8").splitlines())
        status = "NG" if probs else "OK"
        print(f"{status} {f.relative_to(ROOT) if f.is_absolute() else f}"
              f" ({n} lines)")
        for p in probs:
            print("   ", p)
        bad += bool(probs)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
