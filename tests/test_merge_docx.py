import tempfile
import unittest
import zipfile
from pathlib import Path

from tests import support  # noqa: F401  (sets sys.path)
from ts_converter import merge_docx

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
      'content-types"><Default Extension="xml" ContentType="a/xml"/>'
      '%s</Types>')


def make(path: Path, paras: list[str], rel_ids: dict[str, tuple[str, bytes]],
         ext_types: str = ""):
    """rel_ids: {rId: (media file name, data)}; one embed per paragraph."""
    body = "".join(
        f'<w:p><w:r><w:t>{t}</w:t><w:drawing r:embed="{rid}"/></w:r></w:p>'
        for t, rid in zip(paras, rel_ids)) + "<w:sectPr/>"
    doc = (f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body>{body}'
           f'</w:body></w:document>')
    rels = "".join(
        f'<Relationship Id="{rid}" Type="{R}/image" '
        f'Target="media/{name}"/>' for rid, (name, _) in rel_ids.items())
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", CT % ext_types)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels",
                   f'<Relationships xmlns="{PKG}">{rels}</Relationships>')
        for _, (name, data) in rel_ids.items():
            z.writestr(f"word/media/{name}", data)


class MergeDocxTest(unittest.TestCase):
    def test_part_order(self):
        def order(*names):
            got = sorted((Path(n + ".docx") for n in names),
                         key=merge_docx.part_order)
            return [p.stem for p in got]

        self.assertEqual(
            order("36211-j30_s09-sxx", "36211-j30_cover",
                  "36211-j30_s06-s08"),
            ["36211-j30_cover", "36211-j30_s06-s08", "36211-j30_s09-sxx"])
        self.assertEqual(
            order("38133-k10_10_sA", "38133-k10_2_s8", "38133-k10_0_cover"),
            ["38133-k10_0_cover", "38133-k10_2_s8", "38133-k10_10_sA"])
        self.assertEqual(
            order("38133-hn0_s10-11", "38133-hn0_sA.1-A.5",
                  "38133-hn0_s9-9"),
            ["38133-hn0_s9-9", "38133-hn0_s10-11", "38133-hn0_sA.1-A.5"])

    def test_merge_renames_collisions(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "36211-j30"
            d.mkdir()
            make(d / "36211-j30_cover.docx", ["cover"],
                 {"rId5": ("image1.wmf", b"A")}, '<Default Extension="wmf" '
                 'ContentType="image/x-wmf"/>')
            make(d / "36211-j30_s00-s05.docx", ["same", "other"],
                 {"rId5": ("image1.wmf", b"B"),
                  "rId6": ("image2.png", b"C")},
                 '<Default Extension="png" ContentType="image/png"/>')
            out = merge_docx.merge_dir(d, Path(td) / "merged")
            self.assertEqual(out.name, "36211-j30.docx")
            with zipfile.ZipFile(out) as z:
                doc = z.read("word/document.xml").decode()
                rels = z.read("word/_rels/document.xml.rels").decode()
                self.assertLess(doc.index("cover"), doc.index("same"))
                self.assertIn('r:embed="rIdP1_5"', doc)
                self.assertIn('Target="media/p1_image1.wmf"', rels)
                self.assertEqual(z.read("word/media/image1.wmf"), b"A")
                self.assertEqual(z.read("word/media/p1_image1.wmf"), b"B")
                self.assertEqual(z.read("word/media/image2.png"), b"C")
                self.assertIn('Extension="png"',
                              z.read("[Content_Types].xml").decode())
                self.assertEqual(doc.count("<w:sectPr"), 1)


if __name__ == "__main__":
    unittest.main()
