"""Download the latest TS/TR of every Release from the 3GPP FTP.

usage: python tools/download_specs.py [--dry-run] [--dest DIR]
                                      [--specs 38.321 ...]
                                      [--tiers core cross_wg ...]

For each spec in data/recommended_specs.json and each Release
(Rel-15 up to the newest one on the server) the file under
Specs/latest/Rel-N/ is fetched when it is not in the destination
yet. Each zip is extracted and then deleted. A zip holding one file is
extracted into the destination, any other zip (a TS split into
several docx) into DEST/<file stem>/. Zips inside a zip are skipped.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC_LIST = ROOT / "data" / "recommended_specs.json"
DEFAULT_DEST = ROOT / "TS_docx"
BASE = "https://www.3gpp.org/ftp/Specs/latest"
FIRST_RELEASE = 15
# the server answers 403 to the default urllib/curl User-Agent
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
FILE_RE = re.compile(r'href="[^"]*/(\d{5}(?:-\d+)?-[0-9a-z]{3})\.zip"')


def load_specs(tiers: list[str] | None = None) -> list[str]:
    data = json.loads(SPEC_LIST.read_text("utf-8"))
    specs: list[str] = []
    for tier, body in data.items():
        if tiers and tier not in tiers:
            continue
        specs += [s for s in body["specs"] if s not in specs]
    return specs


def spec_prefix(spec: str) -> str:
    """'38.101-1' -> '38101-1', '38.211' -> '38211'."""
    number, _, part = spec.partition("-")
    return number.replace(".", "") + (f"-{part}" if part else "")


def version_of(stem: str) -> str:
    """'38211-j50' -> '19.5.0' (each field is one base-36 digit)."""
    major, minor, patch = (int(c, 36) for c in stem[-3:])
    return f"{major}.{minor}.{patch}"


def parse_listing(html: str) -> dict[str, str]:
    """Return {spec prefix: file stem} of one directory listing."""
    found: dict[str, str] = {}
    for stem in FILE_RE.findall(html):
        found[stem.rsplit("-", 1)[0]] = stem
    return found


def missing(wanted: dict[str, str], dest: Path) -> dict[str, str]:
    have = {p.stem.lower() for p in dest.glob("*.doc*")}
    have |= {p.name.lower() for p in dest.iterdir() if p.is_dir()}
    return {k: v for k, v in wanted.items() if v.lower() not in have}


def fetch(url: str, retries: int = 3) -> bytes:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as res:
                return res.read()
        except (urllib.error.URLError, TimeoutError) as e:
            client_error = isinstance(e, urllib.error.HTTPError) and e.code < 500
            if client_error or attempt == retries - 1:
                raise
            time.sleep(2 * (attempt + 1))
    raise AssertionError("unreachable")


def listing(release: int, series: str) -> dict[str, str]:
    url = f"{BASE}/Rel-{release}/{series}_series/"
    try:
        return parse_listing(fetch(url).decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        # a directory that does not exist is answered with 403
        if e.code in (403, 404):
            return {}
        raise


def latest_release() -> int:
    if not listing(FIRST_RELEASE, "38"):
        raise SystemExit("cannot read the 3GPP FTP listing (blocked?)")
    release = FIRST_RELEASE
    while listing(release + 1, "38"):
        release += 1
    return release


def unzip(zf: zipfile.ZipFile, out: Path, root: Path) -> list[str]:
    """Extract flat (names only, no zip slip); nested zips are skipped
    (e.g. the 28k band combination JSON files of TS 38.101)."""
    names: list[str] = []
    bad = zf.testzip()
    if bad:
        raise zipfile.BadZipFile(f"corrupt member: {bad}")
    for info in zf.infolist():
        name = Path(info.filename).name
        if info.is_dir() or not name:
            continue
        if name.lower().endswith(".zip"):
            continue
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_bytes(zf.read(info))
        names.append(str((out / name).relative_to(root)))
    return names


def extract(data: bytes, stem: str, dest: Path) -> list[str]:
    """Extract the zip data (one file -> dest, else dest/stem/)."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [Path(i.filename).name for i in zf.infolist()
                   if not i.is_dir() and not i.filename.lower().endswith(".zip")]
        flat = len(members) == 1 and Path(members[0]).stem.lower() == stem.lower()
        return unzip(zf, dest if flat else dest / stem, dest)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    ap.add_argument("--specs", nargs="+", help="e.g. 38.321 (default: all)")
    ap.add_argument("--tiers", nargs="+", help="tier names in the JSON")
    args = ap.parse_args(argv)

    specs = args.specs or load_specs(args.tiers)
    args.dest.mkdir(parents=True, exist_ok=True)
    top = latest_release()
    print(f"newest release on the server: Rel-{top}")

    todo: list[tuple[int, str, str]] = []
    absent: list[str] = []
    for release in range(FIRST_RELEASE, top + 1):
        series_list = sorted({s.split(".")[0] for s in specs})
        found: dict[str, str] = {}
        for series in series_list:
            found.update(listing(release, series))
        wanted = {}
        for spec in specs:
            prefix = spec_prefix(spec)
            if prefix in found:
                wanted[prefix] = found[prefix]
            else:
                absent.append(f"Rel-{release} {spec}")
        for prefix, stem in missing(wanted, args.dest).items():
            todo.append((release, prefix, stem))
        print(f"Rel-{release}: {len(wanted)} files, "
              f"{sum(1 for t in todo if t[0] == release)} to download")

    failed: list[str] = []
    for i, (release, prefix, stem) in enumerate(todo, 1):
        label = f"[{i}/{len(todo)}] Rel-{release} {stem} (V{version_of(stem)})"
        if args.dry_run:
            print(label)
            continue
        url = f"{BASE}/Rel-{release}/{prefix[:2]}_series/{stem}.zip"
        try:
            names = extract(fetch(url), stem, args.dest)
        except (urllib.error.URLError, zipfile.BadZipFile, TimeoutError) as e:
            print(f"{label} FAILED: {e}")
            failed.append(stem)
            continue
        print(f"{label} -> {', '.join(names)}")
        time.sleep(0.5)

    verb = "to download" if args.dry_run else "downloaded"
    print(f"done: {len(todo) - len(failed)} {verb}, "
          f"{len(failed)} failed, {len(absent)} not on the server")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
