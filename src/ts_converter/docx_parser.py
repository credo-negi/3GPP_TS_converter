"""3GPP TS docx -> Document (intermediate representation)."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

from .equations import EquationResolver, R, V
from .ir import (Cell, Document, DisplayMath, ImageBlock, Para, Section,
                 Seg, Table)
from .ole_math import EQ_PROGIDS, O, W

M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"

HEADING_RE = re.compile(r"^(?:Heading|H)(\d)$")
BULLET_STYLES = {"B1": 1, "B2": 2, "B3": 3, "B4": 4, "B5": 5}
DEF_STYLES = {"EW", "EX"}
NUM_RE = re.compile(
    r"^(?P<num>(?:\d+(?:\.\d+)*[a-zA-Z]?)|(?:[A-Z](?:\.\d+)+[a-zA-Z]?))"
    r"(?:\s+|$)")
ANNEX_RE = re.compile(
    r"^(Annex\s+[A-Z])\b\s*(?:\((\w+)\))?\s*:?\s*(.*)$", re.I | re.S)


def w(tag: str) -> str:
    return f"{{{W}}}{tag}"


def is_figure_paragraph(el) -> bool:
    """A picture alone in a TH paragraph is a figure, not an equation.

    Only the visible text (w:t) counts, not field codes."""
    for p in el.iterancestors(w("p")):
        text = "".join(t.text or "" for t in p.iter(w("t")))
        return style_of(p) == "TH" and not text.strip()
    return False


def style_of(p) -> str:
    st = p.find(f"{w('pPr')}/{w('pStyle')}")
    return st.get(w("val")) if st is not None else ""


class DocxParser:
    def __init__(self, path: Path, cache_dir: Path,
                 overrides: Path | None = None, log=print):
        self.path = path
        self.log = log
        self.zf = zipfile.ZipFile(path)
        self.root = etree.fromstring(self.zf.read("word/document.xml"))
        self.body = self.root.find(w("body"))
        self.res = EquationResolver(path, self.zf, self.root, cache_dir,
                                    overrides, log)

    # --------------------------------------------------------- runs
    def run_segs(self, r) -> list[Seg]:
        va = r.find(f"{w('rPr')}/{w('vertAlign')}")
        kind = "text"
        if va is not None:
            kind = {"superscript": "sup", "subscript": "sub"}.get(
                va.get(w("val")), "text")
        out: list[Seg] = []
        for c in r:
            tag = etree.QName(c).localname
            if tag == "t":
                out.append(Seg(kind, c.text or ""))
            elif tag == "tab":
                out.append(Seg("text", "\t"))
            elif tag in ("br", "cr"):
                if c.get(w("type")) not in ("page", "column"):
                    out.append(Seg("br"))
            elif tag == "noBreakHyphen":
                out.append(Seg("text", "-"))
            elif tag == "object":
                out.extend(self.object_segs(c))
            elif tag == "drawing":
                out.extend(self.drawing_segs(c))
            elif tag == "pict":
                out.extend(self.pict_segs(c))
        return out

    def object_segs(self, obj) -> list[Seg]:
        ole = obj.find(f"{{{O}}}OLEObject")
        pid = ole.get("ProgID", "") if ole is not None else ""
        if pid in EQ_PROGIDS:
            return [self.res.ole(obj)]
        img = obj.find(f".//{{{V}}}imagedata")
        if img is not None and img.get(f"{{{R}}}id"):
            return [self.res.picture(img.get(f"{{{R}}}id"), "figure",
                                     is_figure_paragraph(obj))]
        return []

    def drawing_segs(self, dr) -> list[Seg]:
        out = []
        for blip in dr.iter(f"{{{A}}}blip"):
            rid = blip.get(f"{{{R}}}embed")
            if rid:
                dp = dr.find(f".//{{{WP}}}docPr")
                alt = dp.get("descr", "") if dp is not None else ""
                out.append(self.res.picture(rid, alt,
                                            is_figure_paragraph(dr)))
        return out

    def pict_segs(self, pict) -> list[Seg]:
        out = []
        for img in pict.iter(f"{{{V}}}imagedata"):
            if img.get(f"{{{R}}}id"):
                out.append(self.res.picture(img.get(f"{{{R}}}id"), "",
                                            is_figure_paragraph(pict)))
        return out

    # ---------------------------------------------------- paragraphs
    def para_items(self, p) -> list:
        """Items of a paragraph: Seg or DisplayMath, in order."""
        items: list = []
        for c in p:
            tag = etree.QName(c).localname
            ns = etree.QName(c).namespace
            if ns == M and tag == "oMathPara":
                seg = self.res.omml(c)
                if seg.text:
                    items.append(DisplayMath(seg.text))
            elif ns == M and tag == "oMath":
                items.append(self.res.omml(c))
            elif tag == "r":
                items.extend(self.run_segs(c))
            elif tag in ("hyperlink", "smartTag", "ins", "sdt", "fldSimple"):
                for r in c.iter(w("r")):
                    items.extend(self.run_segs(r))
        return items

    @staticmethod
    def clean_segs(segs: list[Seg]) -> list[Seg]:
        """Normalise spaces, merge neighbours; keep a single tab marker."""
        out: list[Seg] = []
        for s in segs:
            if s.kind in ("text", "sup", "sub"):
                t = s.text.replace(" ", " ").replace(" ", " ")
                t = t.replace("​", "").replace("‑", "-")
                t = t.replace("­", "")
                if not t:
                    continue
                if out and out[-1].kind == s.kind:
                    out[-1] = Seg(s.kind, out[-1].text + t)
                else:
                    out.append(Seg(s.kind, t))
            else:
                if (s.kind == "math" and out and out[-1].kind == "math"):
                    out[-1] = Seg("math", out[-1].text + " " + s.text)
                    continue
                out.append(s)
        # collapse whitespace in text runs, trim ends
        res: list[Seg] = []
        for s in out:
            if s.kind == "text":
                t = re.sub(r"[ \r\n]+", " ", s.text)
                t = re.sub(r" ?\t ?", "\t", t)
                res.append(Seg("text", t))
            else:
                res.append(s)
        while res and res[0].kind == "text" and not res[0].text.strip(
                " \t"):
            res.pop(0)
        while res and res[-1].kind == "text" and not res[-1].text.strip(
                " \t"):
            res.pop()
        if res and res[0].kind == "text":
            res[0] = Seg("text", res[0].text.lstrip(" \t"))
        if res and res[-1].kind == "text":
            res[-1] = Seg("text", res[-1].text.rstrip(" \t"))
        res = [Seg(s.kind, s.text.strip()) if s.kind in ("sup", "sub")
               else s for s in res]
        return [s for s in res if s.kind != "text" or s.text]

    def plain(self, segs: list[Seg]) -> str:
        return "".join(s.text for s in segs
                       if s.kind in ("text", "sup", "sub")).replace("\t", " ")

    def paragraph_blocks(self, p) -> list:
        """Blocks produced by one paragraph (no headings here)."""
        style = style_of(p)
        items = self.para_items(p)
        blocks: list = []
        run: list[Seg] = []

        def flush_run():
            segs = self.clean_segs(run)
            run.clear()
            if segs:
                blocks.append(self.make_para(style, segs))

        for it in items:
            if isinstance(it, DisplayMath):
                flush_run()
                blocks.append(it)
            else:
                run.append(it)
        # whole paragraph = equation (EQ style) -> display math;
        # line breaks between formulas start a new row
        if style == "EQ" and run:
            rows: list[list[Seg]] = [[]]
            for sg in run:
                if sg.kind == "br":
                    rows.append([])
                else:
                    rows[-1].append(sg)
            cleaned = [c for c in (self.clean_segs(r) for r in rows) if c]
            if cleaned and all(self.is_formula_row(c) for c in cleaned):
                run.clear()
                tex = [self.join_formulas(c) for c in cleaned]
                if len(tex) > 1:
                    tex = [r"\begin{aligned}" + r"\\ ".join(
                        "&" + t for t in tex) + r"\end{aligned}"]
                blocks.append(DisplayMath(tex[0]))
                for c in cleaned:
                    blocks.extend(ImageBlock(sg.src, sg.text)
                                  for sg in c if sg.kind == "image")
                return blocks
        run[:] = [Seg("text", " ") if sg.kind == "br" else sg
                  for sg in run]
        flush_run()
        # image-only paragraphs -> image blocks
        out = []
        for b in blocks:
            if (isinstance(b, Para) and all(s.kind == "image"
                                            for s in b.segs)):
                out.extend(ImageBlock(s.src, s.text) for s in b.segs)
            else:
                out.append(b)
        return out

    @staticmethod
    def join_formulas(segs: list[Seg]) -> str:
        """Formulas side by side; a tab/space between them -> \\quad."""
        out, gap = "", False
        for sg in segs:
            if sg.kind == "math":
                out += (r" \quad " if gap and out else " " if out
                        else "") + sg.text
                gap = False
            elif sg.kind == "text":
                gap = True
        return out

    @staticmethod
    def is_formula_row(segs: list[Seg]) -> bool:
        return (any(s.kind == "math" for s in segs) and all(
            s.kind in ("math", "image") or (
                s.kind == "text" and not s.text.strip(" \t"))
            for s in segs))

    def make_para(self, style: str, segs: list[Seg]) -> Para:
        kind, level = "text", 1
        if style in BULLET_STYLES:
            kind, level = "bullet", BULLET_STYLES[style]
            segs = self.strip_bullet(segs)
        elif style in DEF_STYLES:
            kind = "def"
        elif style.startswith("NO") or style == "NF":
            kind = "note"
        elif style in ("TH", "TF"):
            kind = "caption"
        elif style.startswith(("Z", "FP", "TT")):
            kind = "cover"
        elif style == "EX" or style.startswith("EXAMPLE"):
            kind = "example"
        return Para(kind, segs, level, style)

    @staticmethod
    def strip_bullet(segs: list[Seg]) -> list[Seg]:
        if segs and segs[0].kind == "text":
            t = re.sub(r"^[-–•·]\s*\t?\s*", "", segs[0].text)
            t = t.lstrip("\t ")
            segs = [Seg("text", t)] + segs[1:] if t else segs[1:]
        return segs

    # ------------------------------------------------------ tables
    def table(self, tbl) -> Table:
        rows: list[list[Cell]] = []
        pending: dict[int, tuple[int, int]] = {}  # col -> (row, col)
        for ri, tr in enumerate(tbl.findall(w("tr"))):
            row: list[Cell] = []
            col = 0
            for tc in tr.findall(w("tc")):
                pr = tc.find(w("tcPr"))
                span = 1
                vm = None
                if pr is not None:
                    gs = pr.find(w("gridSpan"))
                    if gs is not None:
                        span = int(gs.get(w("val"), "1"))
                    vme = pr.find(w("vMerge"))
                    if vme is not None:
                        vm = vme.get(w("val"), "continue")
                cell = Cell(colspan=span)
                if vm == "continue" and col in pending:
                    cell.covered = True
                    cell.origin = pending[col]
                    orow, ocol = pending[col]
                    rows[orow][ocol].rowspan += 1
                else:
                    for p in tc.findall(w("p")):
                        segs = self.clean_segs(self.cell_items(p))
                        if segs:
                            cell.paras.append(segs)
                    for sub in tc.findall(w("tbl")):
                        cell.paras.append([Seg("text", self.flat_table(sub))])
                    if vm == "restart":
                        pending[col] = (ri, col)
                    else:
                        pending.pop(col, None)
                row.append(cell)
                for _ in range(1, span):
                    row.append(Cell(covered=True, origin=(ri, col)))
                col += span
            rows.append(row)
        return Table(rows)

    def cell_items(self, p) -> list[Seg]:
        segs = []
        for it in self.para_items(p):
            if isinstance(it, DisplayMath):
                it = Seg("math", it.latex)
            elif it.kind == "br":
                it = Seg("text", " ")
            segs.append(it)
        return segs

    def flat_table(self, tbl) -> str:
        t = self.table(tbl)
        return "; ".join(" | ".join(self.plain(s) for c in r
                                   if not c.covered for s in c.paras)
                         for r in t.rows)

    # ------------------------------------------------ whole document
    def parse(self) -> Document:
        spec, rel = parse_filename(self.path)
        doc = Document(spec=spec, release=rel, version="", title="",
                       source=self.path.name)
        cur = Section(0, "", "Cover", [])
        doc.sections.append(cur)
        for el in self.body:
            tag = etree.QName(el).localname
            if tag == "tbl":
                cur.blocks.append(self.table(el))
                continue
            if tag != "p":
                continue
            style = style_of(el)
            if style.startswith("TOC"):
                continue
            m = HEADING_RE.match(style)
            if m:
                level = int(m.group(1))
                text = self.plain(self.clean_segs(
                    [Seg("text", " ") if x.kind == "br" else x
                     for x in self.para_items(el)
                     if isinstance(x, Seg)]))
                if not text.strip():
                    continue
                num, title, level = split_heading(text, level)
                cur = Section(level, num, title, [])
                doc.sections.append(cur)
                continue
            if style == "TT":      # "Contents" title
                continue
            for b in self.paragraph_blocks(el):
                cur.blocks.append(b)
        meta_text = ""
        for b in doc.sections[0].blocks:
            if isinstance(b, Para) and b.style == "ZA":
                meta_text = self.plain(b.segs)
        if not meta_text:      # newer releases put the cover in a table
            for p in self.body.iter(w("p")):
                if style_of(p) == "ZA":
                    meta_text = "".join(p.itertext()).strip()
                    break
        mm = re.search(r"T[SR]\s+(\d+\.\d+(?:-\d+)?)\s+V(\d+\.\d+\.\d+)",
                       meta_text)
        if mm:
            doc.version = mm.group(2)
            doc.title = meta_text
        return doc


def split_heading(text: str, level: int) -> tuple[str, str, int]:
    text = text.strip()
    am = ANNEX_RE.match(text)
    if am:
        num = "Annex " + am.group(1)[-1].upper()
        title = am.group(3).strip()
        if am.group(2):
            title += f" ({am.group(2).lower()})"
        return num, title.strip(), 1
    m = NUM_RE.match(text)
    if m:
        num = m.group("num")
        title = text[m.end():].strip()
        if re.fullmatch(r"\d+", num) or "." in num or re.fullmatch(
                r"[A-Z]\.\d.*", num):
            return num, title, level
    return "", text, level


def parse_filename(path: Path) -> tuple[str, int]:
    """'38211-fa0.docx' -> ('38211', 15); version letter = base-36 major.

    A spec in several parts keeps the part: '38101-2-fu0' -> ('38101-2', 15).
    """
    m = re.match(r"(\d{5})(?:-(\d+))?-([0-9a-z])[0-9a-z]{2}$", path.stem)
    if not m:
        return path.stem, 0
    spec = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
    return spec, int(m.group(3), 36)
