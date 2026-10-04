import tempfile
import unittest
import zipfile
from pathlib import Path

from tests import support
from ts_converter.docx_parser import DocxParser, parse_filename

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
COVER = ('<w:p><w:pPr><w:pStyle w:val="ZA"/></w:pPr><w:r><w:t>'
         '3GPP TS 38.212 V18.8.0 (2025-12)</w:t></w:r></w:p>')


def parse(body: str):
    xml = (f'<?xml version="1.0" encoding="UTF-8"?><w:document '
           f'xmlns:w="{W}"><w:body>{body}</w:body></w:document>')
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "38212-i80.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", xml)
            z.writestr("word/_rels/document.xml.rels",
                       '<Relationships xmlns="http://schemas.openxmlformats'
                       '.org/package/2006/relationships"/>')
        p = DocxParser(path, Path(td), None, log=lambda *a: None)
        return p.parse()


class VersionTest(unittest.TestCase):
    def test_cover_paragraph(self):
        doc = parse(COVER)
        self.assertEqual((doc.release, doc.version), (18, "18.8.0"))

    def test_cover_inside_table(self):
        tbl = (f'<w:tbl><w:tr><w:tc>{COVER}</w:tc></w:tr></w:tbl>'
               '<w:p/>')
        doc = parse(tbl)
        self.assertEqual(doc.version, "18.8.0")
        self.assertIn("38.212", doc.title)

    def test_cover_of_a_tr_or_a_part(self):
        for text, ver in (("3GPP TR 38.822 V19.1.0 (2026-09)", "19.1.0"),
                          ("3GPP TS 38.101-2 V19.5.0 (2026-09)", "19.5.0")):
            cover = ('<w:p><w:pPr><w:pStyle w:val="ZA"/></w:pPr><w:r><w:t>'
                     f'{text}</w:t></w:r></w:p>')
            self.assertEqual(parse(cover).version, ver)

    def test_parse_filename(self):
        self.assertEqual(parse_filename(Path("38211-j50.docx")),
                         ("38211", 19))
        self.assertEqual(parse_filename(Path("38101-2-fu0.docx")),
                         ("38101-2", 15))
        self.assertEqual(parse_filename(Path("21905-h20.docx")),
                         ("21905", 17))

    def test_no_cover_leaves_version_empty(self):
        self.assertEqual(parse("<w:p/>").version, "")


if __name__ == "__main__":
    unittest.main()
