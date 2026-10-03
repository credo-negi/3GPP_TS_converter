import unittest

from tests import support  # noqa: F401
from ts_converter.sentences import split_sentences, split_with_atoms


class SplitTest(unittest.TestCase):
    def test_basic(self):
        t = "The UE shall act. Then the gNB shall respond."
        self.assertEqual(split_sentences(t), [
            "The UE shall act.", "Then the gNB shall respond."])

    def test_abbreviations_and_numbers(self):
        t = "Use e.g. a value of 1.5 in clause 5.3.1. Next sentence."
        self.assertEqual(split_sentences(t), [
            "Use e.g. a value of 1.5 in clause 5.3.1.", "Next sentence."])

    def test_lowercase_after_period_is_kept(self):
        self.assertEqual(len(split_sentences("see i.e. this one")), 1)

    def test_closing_bracket(self):
        t = "It is given (see Table 1.) Another one follows."
        self.assertEqual(len(split_sentences(t)), 2)

    def test_atoms_are_not_split(self):
        parts = [(False, "Value "), (True, "$a. B$"), (False, " ok. Next.")]
        out = split_with_atoms(parts)
        self.assertEqual(len(out), 2)
        self.assertIn((True, "$a. B$"), out[0])


if __name__ == "__main__":
    unittest.main()
