import unittest

from tests import support  # noqa: F401
from ts_converter import latex_util as lu
from ts_converter.equations import validate_latex


class LatexUtilTest(unittest.TestCase):
    def test_upright_text(self):
        self.assertEqual(lu.upright_text("RA"), r"\mathrm{RA}")
        self.assertEqual(lu.upright_text("0,1,...,5"),
                         r"0,1,\ldots ,5")
        self.assertEqual(lu.upright_text("2×1"), r"2\times 1")

    def test_mod_is_an_operator(self):
        self.assertIn(r"\bmod", lu.upright_text(" mod 4"))

    def test_trim_keeps_commands(self):
        self.assertEqual(lu.trim(r"a\ "), "a")
        self.assertEqual(lu.trim(r"  \, a  "), "a")
        self.assertEqual(lu.trim(r"2^{\mu}\ "), r"2^{\mu}")

    def test_tidy_merges_mathrm(self):
        self.assertEqual(lu.tidy(r"\mathrm{r}\mathrm{ef}"),
                         r"\mathrm{ref}")

    def test_text_to_latex_styles(self):
        self.assertEqual(lu.text_to_latex("μ").strip(), r"\mu")
        self.assertEqual(lu.text_to_latex("x̃"), r"\tilde{x}")
        self.assertEqual(lu.text_to_latex("ab", "b"), r"\mathbf{ab}")

    def test_fence_adds_space_after_command(self):
        self.assertTrue(lu.fence(r"\lfloor", r"\rfloor", "x").endswith(
            r"\rfloor "))

    def test_cases_columns(self):
        self.assertTrue(lu.cases([["a", "b"]]).startswith(
            r"\begin{cases}"))
        self.assertIn("array", lu.cases([["a", "b", "c"]]))

    def test_validate(self):
        self.assertEqual(validate_latex(r"\frac{a}{b}"), [])
        self.assertIn("unbalanced braces", validate_latex(r"\frac{a}{b"))
        self.assertIn("unbalanced left/right", validate_latex(r"\left( a"))
        self.assertIn("empty", validate_latex("  "))
        self.assertEqual(validate_latex(r"\{ a \}"), [])


if __name__ == "__main__":
    unittest.main()
