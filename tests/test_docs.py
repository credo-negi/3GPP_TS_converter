import unittest

from tests import support
from tools import check_docs


class DocsTest(unittest.TestCase):
    def test_documents_follow_the_rules(self):
        files = check_docs.targets([])
        self.assertTrue(files)
        for f in files:
            self.assertEqual(check_docs.check(f), [], str(f))


if __name__ == "__main__":
    unittest.main()
