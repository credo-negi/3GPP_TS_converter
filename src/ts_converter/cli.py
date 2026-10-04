"""Command line entry point: python -m ts_converter <docx...>."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .docx_parser import DocxParser
from .md_writer import ImageStore, MdWriter
from .merge_docx import merge_dir

ROOT = Path(__file__).resolve().parents[2]


def release_dir(doc) -> str:
    return f"Rel-{doc.release}_V{doc.version}"


def convert(path: Path, md_root: Path, xlsx_root: Path | None,
            cache: Path, overrides: Path, do_md=True, do_xlsx=True,
            log=print) -> dict:
    t0 = time.time()
    log(f"== {path.name}")
    parser = DocxParser(path, cache, overrides, log)
    doc = parser.parse()
    doc.version = doc.version or "unknown"
    res = {"file": path.name, "sections": len(doc.sections)}
    out = md_root / doc.spec / release_dir(doc)
    images = ImageStore(parser.zf, out, release_dir(doc))
    images.collect(doc)
    if do_md:
        images.flush(log)
        files = MdWriter(doc, images, out).write(log)
        res["md_files"] = len(files) + 1
        res["md_dir"] = str(out)
    if do_xlsx and xlsx_root is not None:
        from .xlsx_writer import write_xlsx
        xp = xlsx_root / f"{doc.spec}_{release_dir(doc)}.xlsx"
        write_xlsx(doc, xp, lambda s: f"{out.name}/{images.path(s)}")
        res["xlsx"] = str(xp)
    res["equations"] = {f"{k[0]}:{k[1]}": v
                        for k, v in sorted(parser.res.stats.items())}
    report = parser.res.report
    res["equation_issues"] = len(report)
    if do_md:
        meta = out / "_meta"
        meta.mkdir(exist_ok=True)
        (meta / "equation_issues.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    res["seconds"] = round(time.time() - t0, 1)
    log(json.dumps(res, ensure_ascii=False, indent=1))
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ts_converter",
                                 description="3GPP TS docx -> md / xlsx")
    ap.add_argument("docx", nargs="+", type=Path,
                    help="docx, or a directory of split docx parts")
    ap.add_argument("--md-dir", type=Path, default=ROOT / "md")
    ap.add_argument("--xlsx-dir", type=Path, default=ROOT / "xlsx")
    ap.add_argument("--cache-dir", type=Path, default=ROOT / "cache")
    ap.add_argument("--overrides", type=Path,
                    default=ROOT / "data" / "equation_overrides.json")
    ap.add_argument("--no-md", action="store_true")
    ap.add_argument("--no-xlsx", action="store_true")
    a = ap.parse_args(argv)
    for p in a.docx:
        if p.is_dir():     # TS split into parts: merge them first
            p = merge_dir(p, a.cache_dir / "merged")
        convert(p, a.md_dir, a.xlsx_dir, a.cache_dir, a.overrides,
                not a.no_md, not a.no_xlsx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
