"""Whole-document checks on the real 38.211 files (skipped if absent)."""
import collections
import json
import re
import unittest
from pathlib import Path

from lxml import etree

from tests import support
from tests.mathml_check import (NS, alnum, latex_glyphs, mathml_alnum,
                                mathml_glyphs, omml_text)
from ts_converter.docx_parser import DocxParser, style_of
from ts_converter.equations import validate_latex
from ts_converter.ir import DisplayMath, Para, Table
from ts_converter.latex_mathml import latex_to_mathml
from ts_converter.ole_math import sha1_of

FILES = ["38211-fa0.docx", "38211-ga0.docx", "38211-hb0.docx",
         "38211-ia0.docx", "38211-j50.docx"]
_cache: dict = {}


def parsed(name):
    if name not in _cache:
        p = DocxParser(support.TS_DIR / name, support.ROOT / "cache",
                       support.ROOT / "data" / "equation_overrides.json",
                       log=lambda *a: None)
        _cache[name] = (p, p.parse())
    return _cache[name]


def all_math(doc):
    for sec in doc.sections:
        for b in sec.blocks:
            if isinstance(b, DisplayMath):
                yield b.latex
            elif isinstance(b, Para):
                yield from (s.text for s in b.segs if s.kind == "math")
            elif isinstance(b, Table):
                for row in b.rows:
                    for c in row:
                        for segs in c.paras:
                            yield from (s.text for s in segs
                                        if s.kind == "math")


def merged_table_math(doc):
    """LaTeX of the math in tables that are written as HTML tables."""
    for sec in doc.sections:
        for b in sec.blocks:
            if isinstance(b, Table) and any(
                    c.covered or c.colspan > 1 or c.rowspan > 1
                    for r in b.rows for c in r):
                for row in b.rows:
                    for c in row:
                        for segs in c.paras:
                            yield from (s.text for s in segs
                                        if s.kind == "math")


def docx_glyphs(p) -> dict[str, list[str]]:
    """LaTeX -> letters/digits of the docx equation it came from.

    OMML: the m:t texts.  MathType (OLE): the MathML that LibreOffice made
    from the object (read from cache/, never regenerated here).
    """
    cache = support.ROOT / "cache" / f"ole_mathml_{sha1_of(p.path)[:16]}.json"
    lo = {int(k): v for k, v in json.loads(cache.read_text()).items()} \
        if cache.exists() else {}
    out = collections.defaultdict(list)
    for kind, src, tex in p.res.trace:
        if kind == "omml":
            out[tex].append(omml_text(src))
        elif src in lo:
            root = etree.fromstring(lo[src].encode())
            text = alnum("".join(
                e.text or "" for e in root.iter()
                if isinstance(e.tag, str) and e.tag.split("}")[-1] in
                ("mi", "mn", "mo", "mtext")))
            if text:
                out[tex].append(text)
    return out


class IntegrationBase:
    name = ""

    def test_no_unresolved_equations(self):
        p, _ = parsed(self.name)
        self.assertEqual(p.res.report, [])

    def test_math_is_well_formed(self):
        _, doc = parsed(self.name)
        bad = [m for m in all_math(doc) if validate_latex(m)]
        self.assertEqual(bad[:3], [])

    def test_table_math_becomes_mathml(self):
        _, doc = parsed(self.name)
        bad = []
        for tex in set(merged_table_math(doc)):
            try:
                m = latex_to_mathml(tex)
                etree.fromstring(m.replace("<math>", f'<math xmlns="{NS}">'))
                if mathml_glyphs(m) != latex_glyphs(tex):
                    bad.append(tex)
            except ValueError:
                bad.append(tex)
        self.assertEqual(bad[:3], [])

    def test_table_mathml_matches_docx(self):
        p, doc = parsed(self.name)
        srcs = docx_glyphs(p)
        checked, bad = 0, []
        for tex in set(merged_table_math(doc)):
            if tex in srcs:
                checked += 1
                if mathml_alnum(latex_to_mathml(tex)) not in srcs[tex]:
                    bad.append((tex, srcs[tex][:1]))
        self.assertEqual(bad[:3], [])
        print(f"\n{self.name}: {checked} of "
              f"{len(set(merged_table_math(doc)))} table equations "
              "checked against the docx", end=" ")

    def test_headings_match_toc(self):
        p, doc = parsed(self.name)
        toc = [x for x in p.body if etree.QName(x).localname == "p"
               and style_of(x).startswith("TOC")]
        h6 = [x for x in p.body if etree.QName(x).localname == "p"
              and re.fullmatch(r"H\d", style_of(x))]
        self.assertEqual(len(toc) + len(h6), len(doc.sections) - 1)

    def test_top_level_clauses(self):
        _, doc = parsed(self.name)
        top = {s.number for s in doc.sections if s.level == 1}
        # clause 8 (sidelink) only exists from Rel-16 on
        self.assertTrue({"1", "2", "3", "4", "5", "6", "7",
                         "Annex A"} <= top)

    def test_symbols_clause_has_definitions(self):
        _, doc = parsed(self.name)
        sec = next(s for s in doc.sections if s.number == "3.2")
        defs = [b for b in sec.blocks if isinstance(b, Para)
                and b.kind == "def"]
        self.assertGreater(len(defs), 20)


def make(name):
    return type("Integration_" + name.split("-")[1][:2],
                (IntegrationBase, unittest.TestCase),
                {"name": name})


for _n in FILES:
    globals()["Test" + _n.split("-")[1][:3].upper()] = support.need_docx(
        _n)(make(_n))

if __name__ == "__main__":
    unittest.main()
