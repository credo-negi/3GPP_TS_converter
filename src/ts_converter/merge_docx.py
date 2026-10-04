"""Merge the docx parts of a TS split on the 3GPP FTP into one docx.

Some specs (36.211, 38.101-1, 38.133 ...) are published as a cover and
several section files. The parts come from one Word document, so the
body of every part is appended to the first one and only the images and
OLE objects the body refers to are copied (renamed on a collision).
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
PKG_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
DOC = "word/document.xml"
RELS = "word/_rels/document.xml.rels"
CT = "[Content_Types].xml"
FIXED_DATE = (2000, 1, 1, 0, 0, 0)


def natural_key(text: str) -> list:
    return [(0, int(t), "") if t.isdigit() else (1, 0, t)
            for t in re.split(r"(\d+)", text) if t]


def part_order(path: Path) -> list:
    """cover first, then by the part number or the section range."""
    tail = re.sub(r"^\d{5}(?:-\d)?-[0-9a-z]{3}_", "", path.stem)
    if "cover" in tail:
        return [(0, 0, "")]
    return [(1, 0, "")] + natural_key(tail)


def referenced_ids(root) -> set[str]:
    return {v for el in root.iter() for k, v in el.attrib.items()
            if k.startswith(f"{{{R}}}")}


def rel_target(target: str) -> str:
    """Path of a relationship target inside the zip (relative to word/)."""
    parts: list[str] = []
    for p in ("word/" + target).split("/"):
        if p == "..":
            parts.pop()
        elif p != ".":
            parts.append(p)
    return "/".join(parts)


def merge_parts(parts: list[Path], out: Path) -> Path:
    """Write the merged docx to `out` (the first part is the base)."""
    parts = sorted(parts, key=part_order)
    base = zipfile.ZipFile(parts[0])
    files = {n: base.read(n) for n in base.namelist()}
    root = etree.fromstring(files[DOC])
    body = root.find(f"{{{W}}}body")
    sect = body.find(f"{{{W}}}sectPr")
    rels = etree.fromstring(files[RELS])
    ct = etree.fromstring(files[CT])
    used_ids = {r.get("Id") for r in rels}
    defaults = {d.get("Extension").lower() for d in ct
                if d.tag == f"{{{PKG_CT}}}Default"}

    for n, part in enumerate(parts[1:], 1):
        zf = zipfile.ZipFile(part)
        proot = etree.fromstring(zf.read(DOC))
        prels = {r.get("Id"): r for r in
                 etree.fromstring(zf.read(RELS))}
        pct = etree.fromstring(zf.read(CT))
        pdefault = {d.get("Extension").lower(): d.get("ContentType")
                    for d in pct if d.tag == f"{{{PKG_CT}}}Default"}
        poverride = {o.get("PartName"): o.get("ContentType")
                     for o in pct if o.tag == f"{{{PKG_CT}}}Override"}
        idmap: dict[str, str] = {}
        for rid in sorted(referenced_ids(proot) & prels.keys()):
            rel = prels[rid]
            new_id = rid if rid not in used_ids else f"rIdP{n}_{rid[3:]}"
            used_ids.add(new_id)
            idmap[rid] = new_id
            new = etree.SubElement(rels, f"{{{PKG_REL}}}Relationship")
            for k, v in rel.attrib.items():
                new.set(k, v)
            new.set("Id", new_id)
            if rel.get("TargetMode") == "External":
                continue
            src = rel_target(rel.get("Target"))
            dst = src
            if dst in files and files[dst] != zf.read(src):
                dst = re.sub(r"([^/]+)$", rf"p{n}_\1", src)
                new.set("Target", dst[len("word/"):])
            files[dst] = zf.read(src)
            ext = dst.rsplit(".", 1)[-1].lower()
            if "/" + src in poverride:
                o = etree.SubElement(ct, f"{{{PKG_CT}}}Override")
                o.set("PartName", "/" + dst)
                o.set("ContentType", poverride["/" + src])
            elif ext not in defaults and ext in pdefault:
                d = etree.SubElement(ct, f"{{{PKG_CT}}}Default")
                d.set("Extension", ext)
                d.set("ContentType", pdefault[ext])
                defaults.add(ext)
        for el in proot.iter():
            for k in list(el.attrib):
                if k.startswith(f"{{{R}}}") and el.get(k) in idmap:
                    el.set(k, idmap[el.get(k)])
        for el in proot.find(f"{{{W}}}body"):
            if el.tag == f"{{{W}}}sectPr":
                continue
            if sect is not None:
                sect.addprevious(el)
            else:
                body.append(el)

    files[DOC] = etree.tostring(root, xml_declaration=True,
                                encoding="UTF-8", standalone=True)
    files[RELS] = etree.tostring(rels, xml_declaration=True,
                                 encoding="UTF-8", standalone=True)
    files[CT] = etree.tostring(ct, xml_declaration=True,
                               encoding="UTF-8", standalone=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in sorted(files, key=lambda x: (x != CT, x)):
            zout.writestr(zipfile.ZipInfo(name, FIXED_DATE), files[name],
                          zipfile.ZIP_DEFLATED)
    return out


def merge_dir(directory: Path, out_dir: Path) -> Path:
    """Merge DIR/*.docx into OUT_DIR/<dir name>.docx (reused if newer)."""
    parts = sorted(directory.glob("*.docx"))
    if not parts:
        raise FileNotFoundError(f"no docx in {directory}")
    out = out_dir / f"{directory.name}.docx"
    if out.exists() and out.stat().st_mtime >= max(
            p.stat().st_mtime for p in parts):
        return out
    return merge_parts(parts, out)
