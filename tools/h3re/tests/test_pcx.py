import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from h3re.pcx import MODE_BGR24, MODE_INDEXED, PcxError, parse_pcx

PAL = [(i, 255 - i, (i * 7) & 255) for i in range(256)]
PAL_BYTES = b"".join(bytes(c) for c in PAL)


def indexed_2x2():
    # Pixels (row-major): 0, 1 / 200, 255
    return struct.pack("<3I", 4, 2, 2) + bytes([0, 1, 200, 255]) + PAL_BYTES


def bgr_2x2():
    # Pixel stored as (B, G, R): (10, 20, 30), (40, 50, 60), (70, 80, 90), (1, 2, 3)
    px = bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 1, 2, 3])
    return struct.pack("<3I", 12, 2, 2) + px


class PcxParseTests(unittest.TestCase):
    def test_indexed_2x2_pixel_exact(self):
        img = parse_pcx(indexed_2x2())
        self.assertEqual((img.width, img.height), (2, 2))
        self.assertEqual(img.mode, MODE_INDEXED)
        self.assertEqual(img.pixels, bytes([0, 1, 200, 255]))
        self.assertEqual(img.palette, PAL)
        self.assertEqual(img.to_rgb(), b"".join(bytes(PAL[p]) for p in (0, 1, 200, 255)))

    def test_bgr24_2x2_pixel_exact(self):
        img = parse_pcx(bgr_2x2())
        self.assertEqual((img.width, img.height), (2, 2))
        self.assertEqual(img.mode, MODE_BGR24)
        self.assertIsNone(img.palette)
        self.assertEqual(img.pixels, bytes([10, 20, 30, 40, 50, 60, 70, 80, 90, 1, 2, 3]))
        self.assertEqual(img.to_rgb(), bytes([30, 20, 10, 60, 50, 40, 90, 80, 70, 3, 2, 1]))

    def test_indexed_gap_between_pixels_and_palette_tolerated(self):
        gap = b"\xaa" * 5
        blob = struct.pack("<3I", 4, 2, 2) + bytes([0, 1, 200, 255]) + gap + PAL_BYTES
        img = parse_pcx(blob)
        self.assertEqual(img.pixels, bytes([0, 1, 200, 255]))
        self.assertEqual(img.palette, PAL)

    def test_indexed_palette_is_last_768_bytes(self):
        # Palette is read from the end of the file, so a gap before it must not
        # shift which bytes become the palette.
        other = [(255 - i, i, 0) for i in range(256)]
        other_bytes = b"".join(bytes(c) for c in other)
        blob = struct.pack("<3I", 4, 2, 2) + bytes([9, 8, 7, 6]) + b"\x11" * 40 + other_bytes
        img = parse_pcx(blob)
        self.assertEqual(img.pixels, bytes([9, 8, 7, 6]))
        self.assertEqual(img.palette, other)

    def test_indexed_bytes_after_palette_shift_palette(self):
        # Extra bytes after the palette are part of the "last 768 bytes" window,
        # so the palette is read from the shifted position (matches the engine).
        blob = indexed_2x2() + b"\x00\x00"
        img = parse_pcx(blob)
        self.assertEqual(img.pixels, bytes([0, 1, 200, 255]))
        # Palette = last 768 bytes: starts 2 bytes into PAL_BYTES.
        shifted = PAL_BYTES[2:] + b"\x00\x00"
        expected = [tuple(shifted[i * 3:i * 3 + 3]) for i in range(256)]
        self.assertEqual(img.palette, expected)

    def test_to_png_roundtrip_bgr(self):
        png = parse_pcx(bgr_2x2()).to_png()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack_from(">II", png, 16), (2, 2))
        # IDAT is the first chunk after IHDR (8 sig + 8+13+4 = 33 bytes in)
        idat_len = struct.unpack_from(">I", png, 33)[0]
        raw = zlib.decompress(png[41:41 + idat_len])
        self.assertEqual(raw, b"\x00" + bytes([30, 20, 10, 60, 50, 40])
                         + b"\x00" + bytes([90, 80, 70, 3, 2, 1]))


class PcxErrorTests(unittest.TestCase):
    def test_truncated_header(self):
        with self.assertRaises(PcxError):
            parse_pcx(b"\x04\x00\x00\x00\x02\x00")

    def test_truncated_indexed_palette(self):
        with self.assertRaises(PcxError):
            parse_pcx(indexed_2x2()[:-1])

    def test_truncated_indexed_pixels(self):
        with self.assertRaises(PcxError):
            parse_pcx(indexed_2x2()[:12 + 3])

    def test_truncated_bgr(self):
        with self.assertRaises(PcxError):
            parse_pcx(bgr_2x2()[:-1])

    def test_size_matches_neither_mode(self):
        data = struct.pack("<3I", 5, 2, 2) + bytes(5) + bytes(768)
        with self.assertRaises(PcxError):
            parse_pcx(data)

    def test_width_over_cap(self):
        data = struct.pack("<3I", 4, 8193, 1) + bytes(4) + bytes(768)
        with self.assertRaises(PcxError):
            parse_pcx(data)

    def test_height_over_cap(self):
        data = struct.pack("<3I", 4, 1, 8193) + bytes(4) + bytes(768)
        with self.assertRaises(PcxError):
            parse_pcx(data)

    def test_zero_dimensions(self):
        with self.assertRaises(PcxError):
            parse_pcx(struct.pack("<3I", 0, 0, 0))

    def test_non_bytes_input(self):
        with self.assertRaises(PcxError):
            parse_pcx("not bytes")


if __name__ == "__main__":
    unittest.main()
