import unittest

from lxml import etree

from tests import support  # noqa: F401
from tests.mathml_check import NS, latex_glyphs, mathml_glyphs
from ts_converter.latex_mathml import latex_to_mathml


def mml(tex):
    return latex_to_mathml(tex)


SAMPLES = [
    r"x_{1}+y^{2}-z_{a}^{b}",
    r"\frac{1}{\sqrt{2}}e^{j\pi/4}",
    r"\sqrt[3]{x}",
    r"N_{\mathrm{SF},m'}^{\mathrm{PUCCH},1}",
    r"\phi (0),\ldots ,\phi (5)",
    r"\tilde{p}+\overline{\boldsymbol{W}}_{1,\boldsymbol{i}}",
    r"\left\lceil \log _{2}N_{1} \right\rceil",
    r"\left\{ a,b \right\}",
    r"\sum\limits_{n=1}^{N}{L_{n}}",
    r"\min \left( 1,x \right)\bmod 4",
    r"15\cdot 2^{\mu }\text{ kHz}",
    r"\binom{a}{b}",
    r"\left[ \begin{matrix}1 & 0\\ 0 & 1\end{matrix} \right]",
    r"\left\{\begin{array}{ll}a & x<0\\ b & x>0\end{array}\right.",
    r"\begin{aligned}a&=b\\ c&=d\end{aligned}",
    r"x \in \left\{ 0,1 \right\}, a \le b, c \ge d",
    r"\mathbf{0}\ \boldsymbol{\varphi}\ \mathcal{N}",
]


class StructureTest(unittest.TestCase):
    def test_scripts_and_fractions(self):
        self.assertEqual(mml("x_{1}"),
                         "<math><msub><mi>x</mi><mn>1</mn></msub></math>")
        self.assertIn("<msubsup><mi>a</mi><mn>1</mn><mn>2</mn></msubsup>",
                      mml("a_{1}^{2}"))
        self.assertIn("<mfrac><mn>1</mn><mn>2</mn></mfrac>",
                      mml(r"\frac{1}{2}"))
        self.assertIn("<msqrt>", mml(r"\sqrt{x}"))
        self.assertIn("<mroot>", mml(r"\sqrt[3]{x}"))

    def test_limits_only_with_limits_command(self):
        self.assertIn("<munderover>", mml(r"\sum\limits_{n=1}^{N}"))
        self.assertIn("<msubsup>", mml(r"\sum_{n=1}^{N}"))

    def test_upright_text_and_prime(self):
        self.assertIn('<mi mathvariant="normal">SF</mi>',
                      mml(r"\mathrm{SF}"))
        self.assertIn("<mo>′</mo>", mml("m'"))
        self.assertIn("<mtext> kHz</mtext>", mml(r"\text{ kHz}"))

    def test_bold_uses_math_alphanumerics(self):
        self.assertIn("<mi>𝐱</mi>", mml(r"\mathbf{x}"))
        self.assertIn("<mi>𝒊</mi>", mml(r"\boldsymbol{i}"))

    def test_fences_and_tables(self):
        m = mml(r"\left[ \begin{matrix}1 & 0\\ 0 & 1\end{matrix} \right]")
        self.assertIn('<mo fence="true" stretchy="true">[</mo>', m)
        self.assertEqual(m.count("<mtr>"), 2)
        self.assertEqual(m.count("<mtd>"), 4)
        c = mml(r"\left\{\begin{array}{ll}a & b\\ c & d\end{array}"
                r"\right.")
        self.assertIn('columnalign="left left"', c)
        self.assertNotIn("</mo></mrow></math>", c.replace(
            "</mtable></mrow>", ""))     # no right fence for "\right."

    def test_escapes_markup_characters(self):
        m = mml(r"a<b \text{x&y}")
        self.assertIn("<mo>&lt;</mo>", m)
        self.assertIn("x&amp;y", m)

    def test_unknown_input_is_rejected(self):
        for bad in (r"\unknowncmd", r"\frac{1}", r"\left( x",
                    r"\begin{foo}a\end{foo}", r"a^"):
            with self.assertRaises(ValueError, msg=bad):
                mml(bad)


class AgreementTest(unittest.TestCase):
    """The glyphs of the MathML equal those of the LaTeX."""

    def test_well_formed_and_same_glyphs(self):
        for tex in SAMPLES:
            m = mml(tex)
            etree.fromstring(m.replace("<math>", f'<math xmlns="{NS}">'))
            self.assertEqual(mathml_glyphs(m), latex_glyphs(tex), tex)

    def test_comparison_detects_a_difference(self):
        m = mml(r"a+b")
        self.assertNotEqual(mathml_glyphs(m), latex_glyphs(r"a-b"))


if __name__ == "__main__":
    unittest.main()
