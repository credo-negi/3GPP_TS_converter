import tempfile
import unittest
import zipfile
from pathlib import Path

from tests import support  # noqa: F401
from ts_converter.docx_parser import DocxParser

NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
      'relationships" '
      'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
      'wordprocessingDrawing" '
      'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"')
PIC = ('<w:r><w:drawing><wp:inline><a:graphic><a:graphicData>'
       '<a:blip r:embed="rId5"/></a:graphicData></a:graphic></wp:inline>'
       '</w:drawing></w:r>')


def para(style: str, text: str = "", extra: str = "") -> str:
    t = f'<w:r><w:t>{text}</w:t></w:r>' if text else ""
    return (f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr>{t}{PIC}'
            f'{extra}</w:p>')


def convert(body: str):
    xml = f'<w:document {NS}><w:body>{body}</w:body></w:document>'
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "38300-j40.docx"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("word/document.xml", xml)
            z.writestr("word/_rels/document.xml.rels",
                       '<Relationships xmlns="http://schemas.openxmlformats'
                       '.org/package/2006/relationships"><Relationship '
                       'Id="rId5" Type="x/image" Target="media/image1.wmf"/>'
                       '</Relationships>')
            z.writestr("word/media/image1.wmf", b"not a real wmf")
        p = DocxParser(path, Path(td), None, log=lambda *a: None)
        p.parse()
        return p.res


class FigureTest(unittest.TestCase):
    def test_picture_alone_in_th_is_a_figure(self):
        res = convert(para("TH"))
        self.assertEqual(res.report, [])
        self.assertEqual(res.stats[("picture", "image")], 0)

    def test_field_code_text_does_not_count(self):
        instr = ('<w:r><w:instrText> \\* MERGEFORMAT </w:instrText></w:r>')
        res = convert(para("TH", extra=instr))
        self.assertEqual(res.report, [])

    def test_picture_in_body_text_is_an_equation_candidate(self):
        res = convert(para("B1", "where "))
        self.assertEqual([x["problems"] for x in res.report],
                         [["wmf unresolved"]])

    def test_th_with_text_is_not_a_figure(self):
        res = convert(para("TH", "Table 1: "))
        self.assertEqual(len(res.report), 1)


if __name__ == "__main__":
    unittest.main()
