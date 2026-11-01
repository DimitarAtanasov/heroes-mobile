"""Tests for h3re.txt using synthetic tables only."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG_ROOT))

from h3re.txt import TxtError, parse_txt, read_txt  # noqa: E402


def build(rows, eol="\r\n", final=True):
    s = eol.join("\t".join(r) for r in rows)
    return (s + (eol if final else "")).encode("cp1252")


class TxtTests(unittest.TestCase):
    def test_round_trip(self):
        rows = [["Name", "Cost"], ["Pikeman", "60"], ["Café", "7"]]
        for eol in ("\r\n", "\n"):
            t = parse_txt(build(rows, eol), header_rows=1)
            self.assertEqual([list(r) for r in t.header + t.rows], rows)
            self.assertEqual(len(t.header), 1)

    def test_no_trailing_newline(self):
        t = parse_txt(build([["a", "b"], ["c", "d"]], final=False))
        self.assertEqual(t.rows, (("a", "b"), ("c", "d")))

    def test_embedded_quotes_literal(self):
        t = parse_txt(b'"a\tb"\t\'c\'\t5" nails\r\n')
        self.assertEqual(t.rows, (('"a', 'b"', "'c'", '5" nails'),))

    def test_empty_trailing_field(self):
        t = parse_txt(b"a\tb\t\r\nc\t\t\r\n")
        self.assertEqual(t.rows, (("a", "b", ""), ("c", "", "")))

    def test_bom(self):
        t = parse_txt(b"\xef\xbb\xbfx\ty\n")
        self.assertEqual(t.rows, (("x", "y"),))

    def test_ragged_rows(self):
        t = parse_txt(b"a\tb\tc\nd\ne\tf\n\n", header_rows=1)
        self.assertEqual(t.header, (("a", "b", "c"),))
        self.assertEqual(t.rows, (("d",), ("e", "f"), ("",)))

    def test_mixed_eol_and_empty(self):
        self.assertEqual(parse_txt(b"a\r\nb\nc").rows, (("a",), ("b",), ("c",)))
        t = parse_txt(b"")
        self.assertEqual((t.header, t.rows), ((), ()))

    def test_cp1252_decoding(self):
        self.assertEqual(parse_txt(b"\x80\x93x\x94\n").rows, (("€“x”",),))
        with self.assertRaises(TxtError):
            parse_txt(b"\x81\n")

    def test_header_rows_more_than_lines(self):
        t = parse_txt(b"a\n", header_rows=3)
        self.assertEqual((len(t.header), len(t.rows)), (1, 0))

    def test_bad_header_rows(self):
        for bad in (-1, True, "1"):
            with self.assertRaises(TxtError):
                parse_txt(b"a", header_rows=bad)

    def test_caps(self):
        with self.assertRaises(TxtError):
            parse_txt(b"abcdef", max_bytes=5)
        parse_txt(b"abcde", max_bytes=5)
        with self.assertRaises(TxtError):
            parse_txt(b"a\nb\nc\n", max_lines=2)
        parse_txt(b"a\nb\nc\n", max_lines=3)
        self.assertTrue(issubclass(TxtError, ValueError))

    def test_read_txt_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.txt"
            p.write_bytes(b"h\n1\t2\n")
            t = read_txt(p, header_rows=1)
            self.assertEqual(t.rows, (("1", "2"),))
            with self.assertRaises(TxtError):
                read_txt(p, max_bytes=3)


if __name__ == "__main__":
    unittest.main()
