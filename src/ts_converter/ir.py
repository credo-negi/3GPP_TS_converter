"""Intermediate representation shared by the Markdown/xlsx writers."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Seg:
    """Inline segment.

    kind: text | math | sup | sub | image
    text: text, LaTeX, or image alt text
    src:  image path inside the docx (kind == image)
    """
    kind: str
    text: str = ""
    src: str = ""


@dataclass
class Para:
    """A paragraph; ``kind`` drives list/quote rendering."""
    kind: str                 # text|bullet|note|example|def|caption|cover
    segs: list[Seg]
    level: int = 1            # list nesting level (bullet)
    style: str = ""


@dataclass
class DisplayMath:
    latex: str


@dataclass
class ImageBlock:
    src: str
    alt: str = ""


@dataclass
class Cell:
    paras: list[list[Seg]] = field(default_factory=list)
    colspan: int = 1
    rowspan: int = 1
    covered: bool = False     # True: swallowed by a merged cell
    origin: tuple[int, int] | None = None   # (row, col) of the owner
    header: bool = False


@dataclass
class Table:
    rows: list[list[Cell]] = field(default_factory=list)


@dataclass
class Section:
    level: int
    number: str
    title: str
    blocks: list = field(default_factory=list)
    children: list["Section"] = field(default_factory=list)


@dataclass
class Document:
    spec: str                 # e.g. 38211
    release: int              # e.g. 15
    version: str              # e.g. 15.10.0
    title: str
    sections: list[Section] = field(default_factory=list)  # flat, in order
    source: str = ""
