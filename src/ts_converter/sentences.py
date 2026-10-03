"""Sentence splitting for 3GPP specification text.

Inline math / images are replaced by placeholder characters before
splitting (see ``split_with_atoms``) so their content is never split.
"""
from __future__ import annotations

import re

ATOM_BASE = 0xE000   # private use area placeholders
ABBREVS = {
    "e.g", "i.e", "etc", "cf", "vs", "fig", "figs", "no", "nos", "approx",
    "resp", "incl", "excl", "eq", "eqs", "ref", "refs", "tel", "ca",
    "al", "sec", "vol", "min", "max", "st", "nd", "rd", "th", "wrt",
    "w.r.t", "p", "pp", "dr", "mr", "inc", "ltd", "co", "jan", "feb",
    "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec",
}
CLOSERS = ")]}\"'”’"
OPENERS = "([{\"'“‘"


def _is_start(ch: str) -> bool:
    """Can ``ch`` start a new sentence?"""
    if ch.isupper() or ch.isdigit():
        return True
    return ch in OPENERS or ord(ch) >= ATOM_BASE and ord(ch) < 0xF900


def split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences (one string each)."""
    text = text.strip()
    if not text:
        return []
    out: list[str] = []
    start = 0
    n = len(text)
    i = 0
    while i < n:
        ch = text[i]
        if ch in ".!?":
            j = i + 1
            while j < n and text[j] in CLOSERS + ".":
                j += 1
            if j < n and text[j] in " \t":
                k = j
                while k < n and text[k] in " \t":
                    k += 1
                if k < n and _is_start(text[k]) and _boundary_ok(
                        text, i, start):
                    out.append(text[start:j].strip())
                    start = k
                    i = k
                    continue
            elif j >= n:
                break
            i = j
            continue
        i += 1
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def _boundary_ok(text: str, i: int, start: int) -> bool:
    """False if the '.' at ``i`` ends an abbreviation / list marker."""
    if text[i] != ".":
        return True
    m = re.search(r"([A-Za-z.]+)$", text[start:i])
    if m:
        word = m.group(1).lower().rstrip(".")
        if word in ABBREVS:
            return False
        # single capital letter initial, e.g. "A. Smith"
        if len(word) == 1 and word.isalpha() and text[i - 1].isupper():
            return False
    # list marker such as "1." or "a." at the start of the sentence
    if re.fullmatch(r"\s*(\d+|[a-z])", text[start:i]):
        return False
    return True


def split_with_atoms(parts: list[tuple[bool, str]]) -> list[list[tuple[bool, str]]]:
    """Split a sequence of (is_atom, text) items into sentences.

    Atoms (math, images) are indivisible.  Returns a list of sentences,
    each a list of (is_atom, text) items.
    """
    atoms: list[str] = []
    buf: list[str] = []
    for is_atom, t in parts:
        if is_atom:
            buf.append(chr(ATOM_BASE + len(atoms)))
            atoms.append(t)
        else:
            buf.append(t)
    sentences = split_sentences("".join(buf))
    result = []
    for s in sentences:
        items: list[tuple[bool, str]] = []
        cur = ""
        for ch in s:
            o = ord(ch)
            if ATOM_BASE <= o < ATOM_BASE + len(atoms):
                if cur:
                    items.append((False, cur))
                    cur = ""
                items.append((True, atoms[o - ATOM_BASE]))
            else:
                cur += ch
        if cur:
            items.append((False, cur))
        result.append(items)
    return result
