"""Render one picture of a docx (by media name) to a cropped PNG.

usage: python tools/show_wmf.py <docx> <media/imageN.wmf> <out.png>
"""
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image, ImageChops

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ts_converter.md_writer import run_soffice_many  # noqa: E402

docx, name, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
z = zipfile.ZipFile(docx)
data = z.read("word/" + name)
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    f = td / Path(name).name
    f.write_bytes(data)
    run_soffice_many([f], td)
    im = Image.open(td / (f.stem + ".png")).convert("RGB")
    bbox = ImageChops.invert(im.convert("L")).getbbox()
    if bbox:
        im = im.crop(bbox)
    pad = Image.new("RGB", (im.width + 20, im.height + 20), "white")
    pad.paste(im, (10, 10))
    pad.save(out)
    print(pad.size)
