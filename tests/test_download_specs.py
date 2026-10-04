import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import download_specs as ds

HTML = ('<a href="https://www.3gpp.org/ftp/Specs/latest/Rel-19/38_series/'
        '38211-j50.zip">x</a>'
        '<a href="https://www.3gpp.org/ftp/Specs/latest/Rel-19/38_series/'
        '38101-1-j70.zip">x</a>')


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


class DownloadSpecsTest(unittest.TestCase):
    def test_spec_prefix(self):
        self.assertEqual(ds.spec_prefix("38.211"), "38211")
        self.assertEqual(ds.spec_prefix("38.101-1"), "38101-1")

    def test_version_of(self):
        self.assertEqual(ds.version_of("38211-j50"), "19.5.0")
        self.assertEqual(ds.version_of("38101-1-fv0"), "15.31.0")
        self.assertEqual(ds.version_of("36211-i02"), "18.0.2")

    def test_parse_listing(self):
        self.assertEqual(ds.parse_listing(HTML), {
            "38211": "38211-j50", "38101-1": "38101-1-j70"})

    def test_missing(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td)
            (dest / "38211-j50.docx").write_bytes(b"")
            (dest / "38101-1-j70").mkdir()
            wanted = {"38211": "38211-j50", "38101-1": "38101-1-j70",
                      "38212": "38212-j40"}
            self.assertEqual(ds.missing(wanted, dest),
                             {"38212": "38212-j40"})

    def test_extract_single_file_is_flat(self):
        with tempfile.TemporaryDirectory() as td:
            data = make_zip({"38211-j50.docx": b"a", "x.zip": b"nested"})
            names = ds.extract(data, "38211-j50", Path(td))
            self.assertEqual(names, ["38211-j50.docx"])
            self.assertEqual(sorted(p.name for p in Path(td).iterdir()),
                             ["38211-j50.docx"])

    def test_extract_split_goes_to_subdir(self):
        with tempfile.TemporaryDirectory() as td:
            data = make_zip({"36211-j30_cover.docx": b"a",
                             "36211-j30_s00.docx": b"b"})
            ds.extract(data, "36211-j30", Path(td))
            self.assertEqual(
                sorted(p.name for p in (Path(td) / "36211-j30").iterdir()),
                ["36211-j30_cover.docx", "36211-j30_s00.docx"])

    def test_extract_ignores_zip_paths(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out"
            dest.mkdir()
            data = make_zip({"../evil.docx": b"a", "ok.docx": b"b"})
            ds.extract(data, "99999-a00", dest)
            self.assertFalse((Path(td) / "evil.docx").exists())
            self.assertTrue((dest / "99999-a00" / "evil.docx").exists())

    def test_recommended_list(self):
        specs = ds.load_specs()
        self.assertIn("38.211", specs)
        self.assertEqual(len(specs), len(set(specs)))
        self.assertEqual(ds.load_specs(["reports"]), ["21.905", "38.822"])


if __name__ == "__main__":
    unittest.main()
