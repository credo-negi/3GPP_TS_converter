"""Whole-document checks on the real 38.211 files (skipped if absent)."""
import re
import unittest
from pathlib import Path

from lxml import etree

from tests import support
from ts_converter.docx_parser import DocxParser, style_of
from ts_converter.equations import validate_latex
from ts_converter.ir import DisplayMath, Para, Table

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


class IntegrationBase:
    name = ""

    def test_no_unresolved_equations(self):
        p, _ = parsed(self.name)
        self.assertEqual(p.res.report, [])

    def test_math_is_well_formed(self):
        _, doc = parsed(self.name)
        bad = [m for m in all_math(doc) if validate_latex(m)]
        self.assertEqual(bad[:3], [])

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
