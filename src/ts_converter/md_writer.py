"""Document -> Markdown, one file per clause, one sentence per line."""
from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from .ir import (Document, DisplayMath, ImageBlock, Para, Section, Seg,
                 Table)
from .ole_math import run_soffice
from .render import segs_to_sentences

CONVERT_EXT = {".wmf", ".emf"}


def slugify(text: str, limit: int = 48) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return s[:limit].rstrip("_") or "untitled"


class ImageStore:
    """Collects images used by a document; copies / converts them."""

    def __init__(self, zf: zipfile.ZipFile, outdir: Path, rel: str):
        self.zf, self.outdir, self.rel = zf, outdir, rel
        self.map: dict[str, str] = {}
        self.alts: dict[str, str] = {}      # src -> OCR text

    def path(self, src: str) -> str:
        if src not in self.map:
            name = Path(src).stem
            ext = Path(src).suffix.lower()
            ext = ".png" if ext in CONVERT_EXT else ext
            self.map[src] = f"images/{name}{ext}"
        return self.map[src]

    def collect(self, doc: Document):
        """Register every image of the document (before writing)."""
        for sec in doc.sections:
            for b in sec.blocks:
                if isinstance(b, ImageBlock):
                    self.path(b.src)
                elif isinstance(b, Para):
                    for sg in b.segs:
                        if sg.kind == "image":
                            self.path(sg.src)
                elif isinstance(b, Table):
                    for row in b.rows:
                        for c in row:
                            for segs in c.paras:
                                for sg in segs:
                                    if sg.kind == "image":
                                        self.path(sg.src)

    def alt(self, src: str, default: str = "figure") -> str:
        return self.alts.get(src) or default

    def flush(self, log=print):
        if not self.map:
            shutil.rmtree(self.outdir / "images", ignore_errors=True)
            return
        imgdir = self.outdir / "images"
        shutil.rmtree(imgdir, ignore_errors=True)   # drop stale images
        imgdir.mkdir(parents=True, exist_ok=True)
        todo = []
        for src, rel in self.map.items():
            data = self.zf.read(src)
            if Path(src).suffix.lower() in CONVERT_EXT:
                todo.append((src, data))
            else:
                (self.outdir / rel).write_bytes(data)
        if todo:
            convert_images(todo, imgdir, log)
        for src, rel in self.map.items():
            self.alts[src] = ocr_text(self.outdir / rel)


def convert_images(items: list[tuple[str, bytes]], outdir: Path,
                   log=print):
    """wmf/emf -> png with LibreOffice.

    LibreOffice renders the picture on a page; we export a PDF (vector)
    and rasterise it with PyMuPDF at 220 dpi, cropped to the drawing.
    Without PyMuPDF a plain PNG export (cropped) is used.
    """
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        files = []
        for src, data in items:
            f = td / Path(src).name
            f.write_bytes(data)
            files.append(f)
        try:
            import fitz  # noqa: F401
            fmt = "pdf"
        except ImportError:
            fmt = "png"
        try:
            run_soffice_many(files, td, fmt)
        except Exception as e:  # noqa: BLE001
            log(f"  image conversion failed: {e}")
        for f in files:
            out = outdir / (f.stem + ".png")
            made = td / (f.stem + "." + fmt)
            if made.exists() and save_cropped(made, out):
                continue
            shutil.copy(f, outdir / f.name)      # keep the original


def ocr_text(path: Path, min_conf: int = 75) -> str:
    """Confident words found in a figure (tesseract), for the alt text."""
    try:
        import pytesseract
        from PIL import Image
        im = Image.open(path).convert("L")
        if im.width < 1200:
            im = im.resize((im.width * 2, im.height * 2))
        data = pytesseract.image_to_data(
            im, config="--psm 11", output_type=pytesseract.Output.DICT)
    except Exception:  # noqa: BLE001
        return ""
    words = []
    for w, conf in zip(data["text"], data["conf"]):
        w = w.strip()
        if (len(w) >= 2 and float(conf) >= min_conf
                and re.fullmatch(r"[A-Za-z][A-Za-z0-9\-_/.]*", w)):
            words.append(w)
    if len(words) >= 2 and any(len(w) >= 4 for w in words):
        return " ".join(words)[:160]
    return ""


def save_cropped(made: Path, out: Path) -> bool:
    """Render/crop LibreOffice's output into ``out`` (PNG)."""
    from PIL import Image, ImageChops
    try:
        if made.suffix == ".pdf":
            import fitz
            page = fitz.open(made)[0]
            pix = page.get_pixmap(dpi=220)
            im = Image.frombytes("RGB", (pix.width, pix.height),
                                 pix.samples)
        else:
            im = Image.open(made).convert("RGB")
        bb = ImageChops.invert(im.convert("L")).getbbox()
        if bb:
            pad = 8
            im = im.crop((max(bb[0] - pad, 0), max(bb[1] - pad, 0),
                          min(bb[2] + pad, im.width),
                          min(bb[3] + pad, im.height)))
        im.save(out)
        return True
    except Exception:  # noqa: BLE001
        return False


def run_soffice_many(files: list[Path], outdir: Path, fmt: str = "png"):
    import subprocess

    from .ole_math import find_soffice
    exe = find_soffice()
    if exe is None:
        raise RuntimeError("LibreOffice not found")
    with tempfile.TemporaryDirectory() as prof:
        # chunk to keep the command line short
        for i in range(0, len(files), 100):
            cmd = [exe, f"-env:UserInstallation=file://{prof}",
                   "--headless", "--convert-to", fmt, "--outdir",
                   str(outdir)] + [str(f) for f in files[i:i + 100]]
            subprocess.run(cmd, check=True, timeout=1800,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)


class MdWriter:
    def __init__(self, doc: Document, images: ImageStore, outdir: Path):
        self.doc, self.images, self.outdir = doc, images, outdir
        self.tag = (f"TS {doc.spec[:2]}.{doc.spec[2:]} Rel-{doc.release}"
                    f" V{doc.version}")
        self.files: list[tuple[Section, str]] = []

    # ------------------------------------------------------ text
    def sents(self, segs: list[Seg], cell: bool = False) -> list[str]:
        segs = [Seg("image", self.images.alt(g.src, g.text), g.src)
                if g.kind == "image" else g for g in segs]
        out = segs_to_sentences(segs, "md", self.images.path)
        if cell:
            out = [o.replace("|", r"\|") if "$" not in o
                   else self.cell_math(o) for o in out]
        return out

    @staticmethod
    def cell_math(s: str) -> str:
        """Escape '|' in table cells (inside $..$ use \\vert)."""
        parts = re.split(r"(\$[^$]*\$)", s)
        res = []
        for p in parts:
            if p.startswith("$") and p.endswith("$") and len(p) > 1:
                res.append(p.replace("|", r"\vert "))
            else:
                res.append(p.replace("|", r"\|"))
        return "".join(res)

    def para_lines(self, p: Para) -> list[str]:
        if p.kind == "def":
            segs = self.split_tab(p.segs)
            sents = self.sents(segs)
            return ["- " + sents[0]] + ["  " + x for x in sents[1:]] \
                if sents else []
        sents = self.sents(p.segs)
        if not sents:
            return []
        if p.kind == "bullet":
            ind = "  " * (p.level - 1)
            return [ind + "- " + sents[0]] + [ind + "  " + x
                                              for x in sents[1:]]
        if p.kind == "note" or p.kind == "example":
            return ["> " + x for x in sents]
        if p.kind == "caption":
            return ["**" + " ".join(sents) + "**"]
        return sents

    @staticmethod
    def split_tab(segs: list[Seg]) -> list[Seg]:
        """'symbol<TAB>description' -> 'symbol: description'."""
        out, done = [], False
        for s in segs:
            if not done and s.kind == "text" and "\t" in s.text:
                a, b = s.text.split("\t", 1)
                if out or a.strip():
                    out.append(Seg("text", a + ": " + b if a or out
                                   else b))
                else:
                    out.append(Seg("text", b))
                done = True
            else:
                out.append(s)
        return out

    def table_lines(self, t: Table) -> list[str]:
        if not t.rows:
            return []
        ncols = max(len(r) for r in t.rows)
        grid: list[list[str]] = []
        for ri, row in enumerate(t.rows):
            cells = []
            for ci in range(ncols):
                c = row[ci] if ci < len(row) else None
                if c is None:
                    cells.append("")
                    continue
                if c.covered and c.origin:
                    orow, ocol = c.origin
                    oc = t.rows[orow][ocol] if orow < len(
                        t.rows) and ocol < len(t.rows[orow]) else None
                    c = oc if oc is not None else c
                cells.append(self.cell_text(c))
            grid.append(cells)
        lines = ["| " + " | ".join(grid[0]) + " |",
                 "|" + "|".join(["---"] * ncols) + "|"]
        lines += ["| " + " | ".join(r) + " |" for r in grid[1:]]
        return lines

    def cell_text(self, c) -> str:
        sents: list[str] = []
        for segs in c.paras:
            sents.extend(self.sents(segs, cell=True))
        return "<br>".join(sents)

    # ------------------------------------------------------ files
    def section_lines(self, sec: Section, trail: str) -> list[str]:
        lines = [f"<!-- {self.tag} | {trail} -->"]
        if sec.level > 0:
            head = (sec.number + " " + sec.title).strip()
            lines += ["#" * min(sec.level, 6) + " " + head, ""]
        prev = None
        for b in sec.blocks:
            chunk: list[str] = []
            kind = None
            if isinstance(b, Para):
                chunk = self.para_lines(b)
                kind = b.kind
            elif isinstance(b, DisplayMath):
                chunk = [f"$${b.latex}$$"]
                kind = "math"
            elif isinstance(b, ImageBlock):
                chunk = [f"![{self.images.alt(b.src)}]"
                         f"({self.images.path(b.src)})"]
                kind = "image"
            elif isinstance(b, Table):
                chunk = self.table_lines(b)
                kind = "table"
            if not chunk:
                continue
            if prev is not None and not (kind in ("bullet", "def")
                                         and prev == kind):
                lines.append("")
            lines += chunk
            prev = kind
        return lines

    def write(self, log=print) -> list[Path]:
        self.outdir.mkdir(parents=True, exist_ok=True)
        for old in self.outdir.glob("*.md"):
            old.unlink()
        stack: list[Section] = []
        written = []
        for seq, sec in enumerate(self.doc.sections):
            while stack and stack[-1].level >= sec.level and sec.level > 0:
                stack.pop()
            trail = " > ".join(
                (s.number + " " + s.title).strip() for s in stack
                + ([sec] if sec.level > 0 else []))
            if sec.level == 0:
                trail = "Cover"
            lines = self.section_lines(sec, trail)
            if sec.level > 0:
                stack.append(sec)
            if sec.level == 0 and len(lines) <= 1:
                continue
            name = f"{seq:03d}_" + (
                (sec.number.replace(" ", "_") + "_" if sec.number else "")
                + slugify(sec.title if sec.level else "cover")) + ".md"
            path = self.outdir / name
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.files.append((sec, name))
            written.append(path)
        self.write_index()
        return written

    def write_index(self):
        lines = [f"# {self.tag}", ""]
        lines.append(f"Source: {self.doc.source}")
        lines.append("")
        for sec, name in self.files:
            ind = "  " * max(sec.level - 1, 0)
            label = (sec.number + " " + sec.title).strip() or "Cover"
            lines.append(f"{ind}- [{label}]({name})")
        (self.outdir / "index.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")
