"""Render a contact sheet: preview picture + our LaTeX, for review.

usage: python tools/contact_sheet.py <docx> <out.png> [--only-unresolved]
Lists pictures/equations whose LaTeX came from text-record scraping or
failed, so that they can be verified by eye (and overrides written).
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ts_converter import mtef, wmf  # noqa: E402
from ts_converter.md_writer import run_soffice_many  # noqa: E402

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--unresolved", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=30)
    a = ap.parse_args()
    seen, rows = set(), []
    for docx in a.docx:
        z = zipfile.ZipFile(docx)
        root = etree.fromstring(z.read("word/document.xml"))
        rels = {r.get("Id"): r.get("Target") for r in etree.fromstring(
            z.read("word/_rels/document.xml.rels"))}
        for dr in root.iter(f"{{{W}}}drawing"):
            for b in dr.iter(f"{{{A}}}blip"):
                t = rels[b.get(f"{{{R}}}embed")]
                if not t.endswith("wmf"):
                    continue
                d = z.read("word/" + t)
                h = hashlib.sha1(d).hexdigest()
                if h in seen or wmf.embedded_mtef(d):
                    continue
                seen.add(h)
                tex = wmf.text_latex(d)
                if a.unresolved and tex:
                    continue
                rows.append((h[:8] + " " + Path(t).name, tex, d))
    rows = rows[a.start:a.start + a.count]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        files = []
        for t, _, d in rows:
            f = td / Path(t).name
            f.write_bytes(d)
            files.append(f)
        run_soffice_many(files, td)
        font = ImageFont.load_default()
        cells = []
        for (t, tex, _), f in zip(rows, files):
            png = td / (f.stem + ".png")
            if not png.exists():
                continue
            im = Image.open(png).convert("RGB")
            bbox = ImageChops.invert(im.convert("L")).getbbox()
            if bbox:
                im = im.crop(bbox)
            sc = min(1.0, 300 / max(im.width, 1))
            if im.height * sc < 40 and im.width < 150:
                sc = 1.5
            im = im.resize((max(1, int(im.width * sc)),
                            max(1, int(im.height * sc))))
            cells.append((t, tex, im))
        cols, cw, ch = 2, 560, 120
        rowsn = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cw, rowsn * ch), "white")
        dr_ = ImageDraw.Draw(sheet)
        for i, (t, tex, im) in enumerate(cells):
            x, y = (i % cols) * cw, (i // cols) * ch
            dr_.text((x + 5, y + 3), Path(t).name + ": "
                     + (tex or "(unresolved)")[:90], fill="blue",
                     font=font)
            sheet.paste(im.crop((0, 0, min(im.width, cw - 20),
                                 min(im.height, ch - 20))), (x + 10, y + 20))
        sheet.save(a.out)
        print("rows", len(cells), "->", a.out)


main()
