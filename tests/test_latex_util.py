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

    def test_accent_on_text_before_a_detached_mark(self):
        # "A" + NBSP + combining dot above (time derivative)
        self.assertEqual(lu.text_to_latex("A\u00a0\u0307"), r"\dot{A}")
        self.assertEqual(lu.text_to_latex("\u2206n\u00a0\u0307").strip(),
                         r"\dot{\Delta n}")

    def test_double_overline(self):
        self.assertEqual(lu.text_to_latex("b\u033f"), r"\bar{\bar{b}}")

    def test_ohm_sign_is_omega(self):
        self.assertEqual(lu.text_to_latex("\u2126").strip(), r"\Omega")
        self.assertEqual(lu.upright_text("\u2126").strip(), r"\Omega")

    def test_precomposed_accented_letter(self):
        self.assertEqual(lu.char_to_latex("\u00ca"), r"\hat{E}")
        self.assertEqual(validate_latex(lu.char_to_latex("\u00ca")), [])

    def test_assignment_and_circled_times(self):
        self.assertEqual(lu.text_to_latex("n\u2254n+1"), "n:=n+1")
        self.assertIn(r"\otimes", lu.text_to_latex("a\u2a02b"))

    def test_unicode_script_digits_in_text(self):
        t = lu.escape_text("r\u2081(k)")
        self.assertNotIn("\u2081", t)
        self.assertEqual(validate_latex(r"\text{" + t + "}"), [])

    def test_typed_backslash_is_not_a_command(self):
        self.assertNotIn("\\N", lu.text_to_latex(r"a\bmod \N").replace(
            r"\backslash N", ""))
        self.assertIn(r"\backslash", lu.text_to_latex("a\\b"))

    def test_lost_character_is_kept_as_a_question_mark(self):
        self.assertEqual(lu.escape_text("R\ufffdC"), "R?C")

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
