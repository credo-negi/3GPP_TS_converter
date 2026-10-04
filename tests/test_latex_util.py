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

    def test_add_script_merges_same_kind(self):
        self.assertEqual(lu.add_script("P", "a"), "P_{a}")
        self.assertEqual(lu.add_script(r"P_{\mathrm{CMAX}}", ",f,c"),
                         r"P_{\mathrm{CMAX},f,c}")
        self.assertEqual(lu.add_script("x^{a}", "", "b"), "x^{ab}")

    def test_add_script_groups_on_clash(self):
        self.assertEqual(lu.add_script("Z'", "r", "m"),
                         "{Z'}_{r}^{m}")
        self.assertEqual(lu.add_script("x_{a}^{b}", "c"),
                         "{x_{a}^{b}}_{c}")

    def test_group_keeps_accent_with_scripts(self):
        self.assertEqual(lu.group(r"\widetilde{w}_{k}^{n}"),
                         r"{\widetilde{w}_{k}^{n}{}}")
        self.assertEqual(lu.group(r"\tilde{r}(i)e^{x}"),
                         r"{\tilde{r}(i)e^{x}}")

    def test_split_top_ignores_nested(self):
        s = r"\begin{matrix}a & b\\ c\end{matrix} & x\\ y"
        rows = lu.split_top(s, r"\\ ")
        self.assertEqual(len(rows), 2)
        self.assertEqual(len(lu.split_top(rows[0], " & ")), 2)

    def test_matrix_columns_limit(self):
        self.assertTrue(lu.matrix(["a & b"], 2).startswith(
            r"\begin{matrix}"))
        wide = lu.matrix([" & ".join("x" * 1 for _ in range(11))], 11)
        self.assertTrue(wide.startswith(r"\begin{array}{ccccccccccc}"))

    def test_validate(self):
        self.assertEqual(validate_latex(r"\frac{a}{b}"), [])
        self.assertIn("unbalanced braces", validate_latex(r"\frac{a}{b"))
        self.assertIn("unbalanced left/right", validate_latex(r"\left( a"))
        self.assertIn("empty", validate_latex("  "))
        self.assertEqual(validate_latex(r"\{ a \}"), [])


if __name__ == "__main__":
    unittest.main()
