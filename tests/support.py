"""Shared helpers for the tests."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
TS_DIR = ROOT / "TS_docx"


def need_docx(name: str):
    """Skip the test when the (git-ignored) docx is not present."""
    p = TS_DIR / name
    return unittest.skipUnless(p.exists(), f"{name} not available")
