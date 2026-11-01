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
            t = parse_txt(build(rows, eol), header_rows=1, lenient_newlines=True)
            self.assertEqual([list(r) for r in t.header + t.rows], rows)
            self.assertEqual(len(t.header), 1)

    def test_no_trailing_newline(self):
        t = parse_txt(build([["a", "b"], ["c", "d"]], final=False))
        self.assertEqual(t.rows, (("a", "b"), ("c", "d")))

    def test_embedded_quotes_literal_when_unquoted(self):
        t = parse_txt(b'\'c\'\t5" nails\r\n')
        self.assertEqual(t.rows, (("'c'", '5" nails'),))

    def test_quoting_disabled_legacy(self):
        t = parse_txt(b'"a\tb"\t\'c\'\t5" nails\r\n', quoting=False)
        self.assertEqual(t.rows, (('"a', 'b"', "'c'", '5" nails'),))

    def test_empty_trailing_field(self):
        t = parse_txt(b"a\tb\t\r\nc\t\t\r\n")
        self.assertEqual(t.rows, (("a", "b", ""), ("c", "", "")))

    def test_bom(self):
        t = parse_txt(b"\xef\xbb\xbfx\ty\r\n")
        self.assertEqual(t.rows, (("x", "y"),))

    def test_ragged_rows(self):
        t = parse_txt(b"a\tb\tc\nd\ne\tf\n\n", header_rows=1, lenient_newlines=True)
        self.assertEqual(t.header, (("a", "b", "c"),))
        self.assertEqual(t.rows, (("d",), ("e", "f"), ("",)))

    def test_mixed_eol_and_empty(self):
        self.assertEqual(
            parse_txt(b"a\r\nb\nc", lenient_newlines=True).rows, (("a",), ("b",), ("c",))
        )
        t = parse_txt(b"")
        self.assertEqual((t.header, t.rows), ((), ()))

    def test_cp1252_decoding(self):
        self.assertEqual(parse_txt(b"\x80\x93x\x94\r\n").rows, (("€“x”",),))
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
            parse_txt(b"a\r\nb\r\nc\r\n", max_lines=2)
        parse_txt(b"a\r\nb\r\nc\r\n", max_lines=3, lenient_newlines=True)
        self.assertTrue(issubclass(TxtError, ValueError))

    def test_bare_lf_is_data_by_default(self):
        t = parse_txt(b"a\nb\tc\r\nd\r\n")
        self.assertEqual(t.rows, (("a\nb", "c"), ("d",)))
        t = parse_txt(b"a\nb\tc\r\nd\r\n", lenient_newlines=True)
        self.assertEqual(t.rows, (("a",), ("b", "c"), ("d",)))

    def test_double_quote_quoting(self):
        t = parse_txt(b'"a\tb"\t"say ""hi"""\t""\r\n')
        self.assertEqual(t.rows, (("a\tb", 'say "hi"', ""),))
        # quoted field may hold CR LF and bare LF
        t = parse_txt(b'"x\r\ny\nz"\tw\r\nnext\r\n')
        self.assertEqual(t.rows, (("x\r\ny\nz", "w"), ("next",)))
        # text may continue after the closing quote
        self.assertEqual(parse_txt(b'"ab"cd\te\r\n').rows, (("abcd", "e"),))
        # a quote not at field start is data
        self.assertEqual(parse_txt(b'a"b\r\n').rows, (('a"b',),))

    def test_unterminated_quote_ends_at_tab_or_record_end(self):
        self.assertEqual(parse_txt(b'"ab\tc\r\nd\r\n').rows, (("ab", "c"), ("d",)))
        self.assertEqual(parse_txt(b'"ab').rows, (("ab",),))

    def test_encoding_selectable(self):
        self.assertEqual(parse_txt("Łódź\r\n".encode("cp1250"), encoding="cp1250").rows, (("Łódź",),))
        self.assertEqual(parse_txt("Дом\r\n".encode("cp1251"), encoding="cp1251").rows, (("Дом",),))
        self.assertEqual(parse_txt("城堡\r\n".encode("gbk"), encoding="gbk").rows, (("城堡",),))
        self.assertEqual(parse_txt("Ünï€\r\n".encode("utf-8"), encoding="utf-8").rows, (("Ünï€",),))
        with self.assertRaises(TxtError):
            parse_txt(b"\xff\xfe", encoding="utf-8")
        with self.assertRaises(TxtError):
            parse_txt(b"a", encoding="no-such-codec")

    def test_read_txt_options(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.txt"
            p.write_bytes('"a ""q"""\n\u0414\r\n'.encode("cp1251"))
            t = read_txt(p, encoding="cp1251")
            self.assertEqual(t.rows, (('a "q"\n\u0414',),))
            t = read_txt(p, encoding="cp1251", lenient_newlines=True, quoting=False)
            self.assertEqual(t.rows, (('"a ""q"""',), ("\u0414",)))

    def test_read_txt_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.txt"
            p.write_bytes(b"h\r\n1\t2\r\n")
            t = read_txt(p, header_rows=1)
            self.assertEqual(t.rows, (("1", "2"),))
            with self.assertRaises(TxtError):
                read_txt(p, max_bytes=3)


if __name__ == "__main__":
    unittest.main()
