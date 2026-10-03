import unittest

from lxml import etree

from tests import support  # noqa: F401
from ts_converter.omml import omml_to_latex

NS = ('xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/'
      'math" xmlns:w="http://schemas.openxmlformats.org/'
      'wordprocessingml/2006/main"')


def conv(inner: str, tag: str = "oMath") -> str:
    el = etree.fromstring(f"<m:{tag} {NS}>{inner}</m:{tag}>")
    return omml_to_latex(el)[0]


def r(text: str, extra: str = "") -> str:
    return f"<m:r>{extra}<m:t>{text}</m:t></m:r>"


NOR = "<m:rPr><m:nor/></m:rPr>"


class OmmlTest(unittest.TestCase):
    def test_fraction(self):
        x = f"<m:f><m:num>{r('1')}</m:num><m:den>{r('2')}</m:den></m:f>"
        self.assertEqual(conv(x), r"\frac{1}{2}")

    def test_sub_sup_text(self):
        x = (f"<m:sSubSup><m:e>{r('N')}</m:e><m:sub>{r('sc', NOR)}</m:sub>"
             f"<m:sup>{r('RB', NOR)}</m:sup></m:sSubSup>")
        self.assertEqual(conv(x), r"N_{\mathrm{sc}}^{\mathrm{RB}}")

    def test_delimiter_and_sqrt(self):
        x = (f"<m:d><m:e><m:rad><m:radPr><m:degHide m:val='1'/></m:radPr>"
             f"<m:deg/><m:e>{r('x')}</m:e></m:rad></m:e></m:d>")
        self.assertEqual(conv(x), r"\left( \sqrt{x} \right)")

    def test_matrix(self):
        row = (f"<m:mr><m:e>{r('1')}</m:e><m:e>{r('0')}</m:e></m:mr>")
        x = f"<m:m>{row}{row}</m:m>"
        self.assertEqual(
            conv(x), r"\begin{matrix}1 & 0\\ 1 & 0\end{matrix}")

    def test_align_marker_only_in_aligned(self):
        x = f"{r('a')}{r('=', '<m:rPr><m:aln/></m:rPr>')}{r('b')}"
        self.assertNotIn("&", conv(x))                       # inline
        para = conv(f"<m:oMath>{x}</m:oMath>", "oMathPara")
        self.assertIn(r"\begin{aligned}", para)
        self.assertIn("&=", para)

    def test_bar_accent_and_nary(self):
        x = ("<m:acc><m:accPr><m:chr m:val='̄'/></m:accPr>"
             f"<m:e>{r('k')}</m:e></m:acc>")
        self.assertEqual(conv(x), r"\bar{k}")
        n = ("<m:nary><m:naryPr><m:chr m:val='∑'/>"
             "<m:limLoc m:val='undOvr'/></m:naryPr>"
             f"<m:sub>{r('i=0')}</m:sub><m:sup>{r('N')}</m:sup>"
             f"<m:e>{r('x')}</m:e></m:nary>")
        self.assertEqual(conv(n), r"\sum\limits_{i=0}^{N} x")


if __name__ == "__main__":
    unittest.main()
