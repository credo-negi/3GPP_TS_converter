"""MathType OLE equations -> MathML, via LibreOffice (headless).

LibreOffice imports ``Equation.3`` OLE objects as Math objects.
We copy the docx, put a marker before every OLE equation, convert
the copy to odt and read the MathML of the object after each marker.
Results are cached (keyed by the sha1 of the docx) in ``cache/``.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
O = "urn:schemas-microsoft-com:office:office"
SOFFICE_CANDIDATES = [
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "soffice",
    "libreoffice",
]
MARK = "@@OLE{}@@"
MARK_RE = re.compile(r"@@OLE(\d+)@@")
EQ_PROGIDS = ("Equation.3", "Equation.DSMT4", "Equation.DSMT5",
              "Equation.DSMT6", "Equation.2")


def find_soffice() -> str | None:
    for c in SOFFICE_CANDIDATES:
        if Path(c).exists() or shutil.which(c):
            return c
    return None


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ole_equation_objects(root) -> list:
    """w:object elements holding an equation, in document order."""
    res = []
    for obj in root.iter(f"{{{W}}}object"):
        ole = obj.find(f"{{{O}}}OLEObject")
        if ole is not None and ole.get("ProgID", "") in EQ_PROGIDS:
            res.append((obj, ole))
    return res


def make_marked_docx(src: Path, dst: Path) -> int:
    """Write a copy of ``src`` with markers; return the marker count."""
    with zipfile.ZipFile(src) as zin:
        root = etree.fromstring(zin.read("word/document.xml"))
        objs = ole_equation_objects(root)
        for i, (obj, ole) in enumerate(objs):
            ole.set("ProgID", "Equation.3")  # LO only imports this id
            run = obj.getparent()
            mr = etree.Element(f"{{{W}}}r")
            t = etree.SubElement(mr, f"{{{W}}}t")
            t.text = MARK.format(i)
            run.addprevious(mr)
        data = etree.tostring(root, xml_declaration=True,
                              encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == "word/document.xml":
                    zout.writestr(item, data)
                else:
                    zout.writestr(item, zin.read(item.filename))
    return len(objs)


def run_soffice(src: Path, outdir: Path, fmt: str, timeout: int = 1800):
    exe = find_soffice()
    if exe is None:
        raise RuntimeError("LibreOffice (soffice) not found")
    with tempfile.TemporaryDirectory() as prof:
        cmd = [exe, f"-env:UserInstallation=file://{prof}", "--headless",
               "--convert-to", fmt, "--outdir", str(outdir), str(src)]
        subprocess.run(cmd, check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def extract_mathml(odt: Path) -> dict[int, str]:
    """Map marker index -> MathML text of the following object."""
    draw = "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"
    xlink = "http://www.w3.org/1999/xlink"
    out: dict[int, str] = {}
    with zipfile.ZipFile(odt) as z:
        names = set(z.namelist())
        root = etree.fromstring(z.read("content.xml"))
        pending = None
        # events in true document order: text, children, tail
        for event, el in etree.iterwalk(root, events=("start", "end")):
            if event == "start":
                if el.tag == f"{{{draw}}}object" and pending is not None:
                    href = el.get(f"{{{xlink}}}href", "")
                    name = href[2:] if href.startswith("./") else href
                    if f"{name}/content.xml" in names:
                        out[pending] = z.read(f"{name}/content.xml").decode()
                    pending = None
                txt = el.text
            else:
                txt = el.tail
            if txt:
                for m in MARK_RE.finditer(txt):
                    pending = int(m.group(1))
    return out


def load_ole_mathml(docx: Path, cache_dir: Path,
                    log=print) -> dict[int, str]:
    """MathML for each OLE equation (marker index) of ``docx``."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = sha1_of(docx)[:16]
    cache = cache_dir / f"ole_mathml_{key}.json"
    if cache.exists():
        return {int(k): v for k, v in json.loads(cache.read_text()).items()}
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        marked = td / "marked.docx"
        n = make_marked_docx(docx, marked)
        log(f"  LibreOffice: converting {docx.name} ({n} OLE equations)")
        run_soffice(marked, td, "odt")
        res = extract_mathml(td / "marked.odt")
    cache.write_text(json.dumps(res))
    log(f"  LibreOffice: got MathML for {len(res)}/{n} equations")
    return res
