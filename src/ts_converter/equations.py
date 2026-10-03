"""Equation resolver: every math object of a docx -> LaTeX (or image).

Sources, in order of preference:
  1. manual overrides   (data/equation_overrides.json, sha1 -> LaTeX)
  2. OMML               (own converter, omml.py)
  3. MathType MTEF v3/v5 (own parser, mtef.py; OLE and pictures)
  4. MathType via LibreOffice MathML (fallback, mathml.py)
  5. image fallback     (preview picture kept as an image)
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

from lxml import etree

from . import mathml, mtef, omml, wmf
from .ir import Seg
from .ole_math import (O, W, ole_equation_objects, load_ole_mathml)

R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
V = "urn:schemas-microsoft-com:vml"


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def validate_latex(tex: str) -> list[str]:
    """Cheap structural checks; returns a list of problems."""
    probs: list[str] = []
    if not tex.strip():
        return ["empty"]
    flat = re.sub(r"\\[{}]", "", tex)
    if flat.count("{") != flat.count("}"):
        probs.append("unbalanced braces")
    if len(re.findall(r"\\left\b", tex)) != len(re.findall(r"\\right\b",
                                                          tex)):
        probs.append("unbalanced left/right")
    if len(re.findall(r"\\begin\{", tex)) != len(re.findall(r"\\end\{",
                                                           tex)):
        probs.append("unbalanced begin/end")
    no_text = re.sub(r"\\text\{[^{}]*\}", "", tex)
    if re.search(r"[^\x00-\x7f]", no_text):
        probs.append("non-ascii")
    if re.search(r"[\ue000-\uf8ff]", tex):
        probs.append("private-use char")
    return probs


class EquationResolver:
    def __init__(self, docx: Path, zf: zipfile.ZipFile, root,
                 cache_dir: Path, overrides_path: Path | None = None,
                 log=print):
        self.docx = docx
        self.zf = zf
        self.cache_dir = cache_dir
        self.log = log
        self.rels = {
            r.get("Id"): r.get("Target")
            for r in etree.fromstring(
                zf.read("word/_rels/document.xml.rels"))}
        self.overrides: dict[str, str] = {}
        if overrides_path and overrides_path.exists():
            self.overrides = json.loads(overrides_path.read_text("utf-8"))
        # keep the proxies alive so that id() stays stable
        self._ole_objs = [obj for obj, _ in ole_equation_objects(root)]
        self.ole_index = {id(obj): i for i, obj in
                          enumerate(self._ole_objs)}
        self._lo: dict[int, str] | None = None
        self.stats: Counter = Counter()
        self.report: list[dict] = []

    # -------------------------------------------------------- helpers
    def media(self, rid: str) -> str:
        return "word/" + self.rels[rid]

    def _lo_mathml(self) -> dict[int, str]:
        if self._lo is None:
            try:
                self._lo = load_ole_mathml(self.docx, self.cache_dir,
                                           self.log)
            except Exception as e:  # noqa: BLE001
                self.log(f"  LibreOffice unavailable: {e}")
                self._lo = {}
        return self._lo

    def _note(self, kind: str, method: str, key: str, tex: str = "",
              problems: list[str] | None = None, src: str = ""):
        self.stats[(kind, method)] += 1
        if method in ("image", "warn") or problems:
            self.report.append({"kind": kind, "method": method,
                                "key": key, "latex": tex,
                                "problems": problems or [], "src": src})

    def _accept(self, kind: str, method: str, key: str, tex: str,
                src: str, preview: Seg | None) -> Seg:
        probs = validate_latex(tex)
        fatal = [p for p in probs if p in (
            "empty", "unbalanced braces", "unbalanced left/right",
            "unbalanced begin/end")]
        if fatal and preview is not None:
            self._note(kind, "image", key, tex, probs, src)
            return preview
        self._note(kind, "warn" if probs else method, key, tex, probs, src)
        return Seg("math", tex)

    # ----------------------------------------------------------- OMML
    def omml(self, el) -> Seg:
        tex, warns = omml.omml_to_latex(el)
        if not tex:
            self._note("omml", "empty", "")
            return Seg("text", "")
        probs = validate_latex(tex)
        self._note("omml", "warn" if probs or warns else "omml",
                   "", tex, probs + warns)
        return Seg("math", tex)

    # ------------------------------------------------------------ OLE
    def ole(self, obj) -> Seg:
        """Resolve a w:object (OLE) holding an equation."""
        ole = obj.find(f"{{{O}}}OLEObject")
        progid = ole.get("ProgID", "")
        blob = self.zf.read(self.media(ole.get(f"{{{R}}}id")))
        key = sha1(blob)
        img = obj.find(f".//{{{V}}}imagedata")
        preview = None
        psrc = ""
        if img is not None and img.get(f"{{{R}}}id"):
            psrc = self.media(img.get(f"{{{R}}}id"))
            preview = Seg("image", "equation", psrc)
        if key in self.overrides:
            self._note("ole", "override", key, self.overrides[key])
            return Seg("math", self.overrides[key])
        # 3. own MTEF parser (v3 and v5)
        tex, note = mtef.mtef_any_to_latex(blob)
        if tex == "" and not note:       # an empty equation object
            self._note("ole", "empty", key)
            return Seg("text", "")
        if tex and not note:
            return self._accept("ole", "mtef", key, tex, psrc, preview)
        # 4. LibreOffice MathML (cross-check / fallback)
        idx = self.ole_index.get(id(obj))
        xml = self._lo_mathml().get(idx) if idx is not None else None
        if xml:
            lo_tex, warns = mathml.mathml_to_latex(xml)
            if lo_tex:
                return self._accept("ole", "libreoffice", key, lo_tex, psrc,
                                    preview)
        if tex:   # parsed, but some glyphs unknown
            return self._accept("ole", "mtef-warn", key, tex, psrc,
                                preview)
        self._note("ole", "image", key, "", ["no latex"], psrc)
        return preview or Seg("text", "")

    # -------------------------------------------------------- picture
    def picture(self, rid: str, alt: str = "") -> Seg:
        """A drawing/picture; MathType pictures are turned into LaTeX."""
        src = self.media(rid)
        data = self.zf.read(src)
        key = sha1(data)
        preview = Seg("image", alt or "image", src)
        if key in self.overrides:
            self._note("picture", "override", key, self.overrides[key])
            return Seg("math", self.overrides[key])
        if src.lower().endswith(".wmf"):
            m = wmf.embedded_mtef(data)
            if m:
                try:
                    tex = mtef.Emitter().top(mtef.parse_mtef(m)).strip()
                except mtef.MtefError:
                    tex = ""
                if tex:
                    return self._accept("picture", "mtef5", key, tex, src,
                                        preview)
            tex = wmf_text_latex(data)
            if tex:
                return self._accept("picture", "wmf-text", key, tex, src,
                                    preview)
            self._note("picture", "image", key, "", ["wmf unresolved"], src)
            return preview
        self._note("figure", "figure", key, "", [], src)
        return preview


def wmf_text_latex(data: bytes) -> str:
    """LaTeX from the text records of a MathType picture (or '')."""
    try:
        return wmf.text_latex(data)
    except Exception:  # noqa: BLE001
        return ""
