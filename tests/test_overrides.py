import json
import unittest

from tests import support
from ts_converter.equations import validate_latex


class OverridesTest(unittest.TestCase):
    def test_all_overrides_are_valid_latex(self):
        path = support.ROOT / "data" / "equation_overrides.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreater(len(data), 0)
        for key, tex in data.items():
            self.assertRegex(key, r"^[0-9a-f]{40}$")
            self.assertEqual(validate_latex(tex), [], key)
