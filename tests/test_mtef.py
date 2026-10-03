import unittest

from tests import support  # noqa: F401
from ts_converter import mtef


def v5(body: bytes) -> bytes:
    return bytes([5, 1, 0, 6, 9]) + b"DSMT6\x00" + b"\x01" + body


def char5(face: int, code: int) -> bytes:
    return bytes([2, 0, face + 128]) + code.to_bytes(2, "little")


def line5(*objs: bytes) -> bytes:
    return b"\x01\x00" + b"".join(objs) + b"\x00"


def tmpl5(sel: int, var: int, *slots: bytes) -> bytes:
    return bytes([3, 0, sel, var, 0]) + b"".join(slots) + b"\x00"


NULL_LINE = b"\x01\x01"


def latex(data: bytes) -> str:
    return mtef.Emitter().top(mtef.parse_mtef(data))


class Mtef5Test(unittest.TestCase):
    def test_single_variable(self):
        self.assertEqual(latex(v5(line5(char5(3, 0x6B)) + b"\x00")), "k")

    def test_subscript_text(self):
        sub = tmpl5(mtef.T_SUB, 0, line5(char5(1, 0x52), char5(1, 0x41)),
                    NULL_LINE)
        data = v5(line5(char5(3, 0x6E), sub) + b"\x00")
        self.assertEqual(latex(data), r"n_{\mathrm{RA}}")

    def test_fraction_and_root(self):
        fr = tmpl5(mtef.T_FRACT, 0, line5(char5(8, 0x31)),
                   line5(tmpl5(mtef.T_ROOT, 0, line5(char5(8, 0x32)),
                               NULL_LINE)))
        self.assertEqual(latex(v5(line5(fr) + b"\x00")),
                         r"\frac{1}{\sqrt{2}}")

    def test_sum_limits_order(self):
        s = tmpl5(mtef.T_SUM, 0, line5(char5(3, 0x78)),
                  line5(char5(3, 0x69)), line5(char5(3, 0x4E)),
                  char5(6, 0x2211))
        self.assertEqual(latex(v5(line5(s) + b"\x00")),
                         r"\sum\limits_{i}^{N} x")


class Mtef3Test(unittest.TestCase):
    def test_variable(self):
        data = bytes.fromhex("0301010 30a0a0112836b00000000".replace(
            " ", ""))
        self.assertEqual(mtef.Emitter().top(mtef.parse_mtef3(data)), "k")

    def test_embellished_char(self):
        # r with an over-bar (embellishment 17), 16-bit embell code
        data = bytes.fromhex("0301010 30a0a01 32 83 7200 06 1100 00 00 00"
                             .replace(" ", ""))
        self.assertEqual(mtef.Emitter().top(mtef.parse_mtef3(data)),
                         r"\bar{r}")

    def test_wrong_version(self):
        with self.assertRaises(mtef.MtefError):
            mtef.parse_mtef3(bytes([5, 0, 0, 0, 0]))


if __name__ == "__main__":
    unittest.main()
