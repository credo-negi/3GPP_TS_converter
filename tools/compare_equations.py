"""Visual check: original equation preview vs our LaTeX, side by side.

usage: python tools/compare_equations.py <docx> --out sheet.png
           [--select complex|random|all] [--start N] [--count N]
Handles OLE equations and MathType pictures (they have a preview image).
"""
from __future__ import annotations

import argparse
import random
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import fitz
from lxml import etree
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ts_converter.docx_parser import DocxParser  # noqa: E402
from ts_converter.md_writer import run_soffice_many  # noqa: E402
from ts_converter.ole_math import O, W, ole_equation_objects  # noqa: E402

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V = "urn:schemas-microsoft-com:vml"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
PRE = r"""\documentclass{article}
\usepackage{amsmath,amssymb,cancel}
\usepackage[active,tightpage]{preview}
\setlength\PreviewBorder{3pt}
\begin{document}
"""


def crop(im: Image.Image) -> Image.Image:
    bb = ImageChops.invert(im.convert("L")).getbbox()
    return im.crop(bb) if bb else im


def render_latex(items: list[str], td: Path) -> list[Image.Image]:
    body = PRE
    for t in items:
        body += f"\\begin{{preview}}$\\displaystyle {t}$\\end{{preview}}\n"
    body += "\\end{document}\n"
    (td / "e.tex").write_text(body, "utf-8")
    subprocess.run(["pdflatex", "-interaction=nonstopmode", "e.tex"],
                   cwd=td, capture_output=True, timeout=600)
    out = []
    try:
        pdf = fitz.open(td / "e.pdf")
        for page in pdf:
            pix = page.get_pixmap(dpi=130)
            im = Image.frombytes("RGB", (pix.width, pix.height),
                                 pix.samples)
            out.append(crop(im))
    except Exception:  # noqa: BLE001
        pass
    while len(out) < len(items):
        out.append(Image.new("RGB", (60, 20), "red"))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--select", default="complex")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    p = DocxParser(a.docx, ROOT / "cache", ROOT / "data" /
                   "equation_overrides.json", log=lambda *x: None)
    res = p.res
    rows, seen = [], set()
    for obj, ole in ole_equation_objects(p.root):
        seg = res.ole(obj)
        img = obj.find(f".//{{{V}}}imagedata")
        if seg.kind != "math" or img is None:
            continue
        src = res.media(img.get(f"{{{R}}}id"))
        if src in seen:
            continue
        seen.add(src)
        rows.append((src, seg.text))
    if a.select == "complex":
        rows.sort(key=lambda r: -len(r[1]))
    elif a.select == "random":
        random.Random(a.seed).shuffle(rows)
    rows = rows[a.start:a.start + a.count]
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        files = []
        for src, _ in rows:
            f = td / Path(src).name
            f.write_bytes(p.zf.read(src))
            files.append(f)
        run_soffice_many(files, td)
        ours = render_latex([t for _, t in rows], td)
        font = ImageFont.load_default()
        cells = []
        for (src, tex), f, im2 in zip(rows, files, ours):
            png = td / (f.stem + ".png")
            im1 = crop(Image.open(png).convert("RGB")) if png.exists() \
                else Image.new("RGB", (60, 20), "red")
            sc = min(1.0, 520 / max(im1.width, 1), 140 / max(im1.height, 1))
            im1 = im1.resize((max(1, int(im1.width * sc)),
                              max(1, int(im1.height * sc))))
            sc2 = min(1.0, 520 / max(im2.width, 1), 140 / max(im2.height, 1))
            im2 = im2.resize((max(1, int(im2.width * sc2)),
                              max(1, int(im2.height * sc2))))
            cells.append((Path(src).name, tex, im1, im2))
        rowh = [max(c[2].height, c[3].height) + 28 for c in cells]
        sheet = Image.new("RGB", (1100, sum(rowh) + 10), "white")
        d = ImageDraw.Draw(sheet)
        y = 5
        for (name, tex, im1, im2), h in zip(cells, rowh):
            d.text((5, y), f"{name}  {tex[:150]}", fill="blue", font=font)
            sheet.paste(im1, (5, y + 16))
            sheet.paste(im2, (560, y + 16))
            d.line((550, y + 14, 550, y + h - 4), fill="gray")
            y += h
        sheet.save(a.out)
        print("saved", a.out, len(cells))


main()
