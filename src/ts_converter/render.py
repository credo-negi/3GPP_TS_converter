"""Inline rendering shared by the Markdown and xlsx writers."""
from __future__ import annotations

from .ir import Seg
from .sentences import split_with_atoms


def seg_atom(s: Seg, fmt: str, img_path) -> str:
    if s.kind == "math":
        return f"${s.text}$"
    if s.kind == "sup":
        return f"<sup>{s.text}</sup>" if fmt == "md" else f"^({s.text})"
    if s.kind == "sub":
        return f"<sub>{s.text}</sub>" if fmt == "md" else f"_({s.text})"
    if s.kind == "image":
        if fmt == "md":
            return f"![{s.text}]({img_path(s.src)})"
        return f"[image: {img_path(s.src)}]"
    return s.text


def _glued(neighbour: Seg, before: bool) -> bool:
    """True if a math atom touches a word without a space."""
    if neighbour.kind != "text" or not neighbour.text:
        return False
    ch = neighbour.text[-1] if before else neighbour.text[0]
    return ch.isalnum()


def segs_to_sentences(segs: list[Seg], fmt: str, img_path) -> list[str]:
    """Split inline segments into sentences, each a rendered string."""
    parts: list[tuple[bool, str]] = []
    for i, s in enumerate(segs):
        atom = s.kind != "text"
        if s.kind == "math" and i > 0 and _glued(segs[i - 1], True):
            parts.append((False, " "))
        parts.append((atom, seg_atom(s, fmt, img_path)))
        if s.kind == "math" and i + 1 < len(segs) and _glued(segs[i + 1],
                                                             False):
            parts.append((False, " "))
    out = []
    for sent in split_with_atoms(parts):
        text = "".join(t for _, t in sent)
        text = text.replace("\t", " ")
        text = " ".join(text.split(" ")).strip()
        if text:
            out.append(text)
    return out
