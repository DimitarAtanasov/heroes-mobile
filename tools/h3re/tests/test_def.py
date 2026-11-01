import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from h3re.defimg import (DefError, parse_def, frame_to_canvas, to_rgba, to_rgb,
                         write_png, write_ppm)

PAL = b"".join(bytes([i, 255 - i, (i * 7) & 255]) for i in range(256))


def frame_bytes(fmt, fw, fh, w, h, x, y, body):
    return struct.pack("<8I", len(body), fmt, fw, fh, w, h, x & 0xFFFFFFFF, y & 0xFFFFFFFF) + body


def build_def(frames, names=None):
    """One block holding `frames` (list of raw frame blobs)."""
    n = len(frames)
    head = struct.pack("<4I", 0x42, 8, 4, 1) + PAL
    bh = struct.pack("<4I", 0, n, 0, 0)
    nm = b"".join((names[i] if names else b"F%d.pcx" % i).ljust(13, b"\0") for i in range(n))
    off0 = len(head) + len(bh) + len(nm) + 4 * n
    offs, blob = [], b""
    for f in frames:
        offs.append(off0 + len(blob))
        blob += f
    return head + bh + nm + struct.pack("<%dI" % n, *offs) + blob


class DefTests(unittest.TestCase):
    def test_raw_format0(self):
        px = bytes(range(1, 9))
        d = parse_def(build_def([frame_bytes(0, 4, 2, 4, 2, 0, 0, px)]))
        self.assertEqual((d.type, d.width, d.height), (0x42, 8, 4))
        self.assertEqual(d.palette[3], (3, 252, 21))
        f = d.blocks[0].frames[0]
        self.assertEqual(f.name, "F0.pcx")
        self.assertEqual(f.pixels, px)

    def test_format1(self):
        # width 6, 2 lines. line0: fill 5 x3, raw [7]; line1: raw [1,2,3], fill 3 x9
        l0 = bytes([5, 4, 0xFF, 0]) + b"\x07"
        l0 = bytes([5, 4]) + bytes([0xFF, 0, 7])
        l1 = bytes([0xFF, 2, 1, 2, 3]) + bytes([9, 2])
        base = 8
        body = struct.pack("<2I", base, base + len(l0)) + l0 + l1
        d = parse_def(build_def([frame_bytes(1, 6, 2, 6, 2, 0, 0, body)]))
        self.assertEqual(d.blocks[0].frames[0].pixels,
                         bytes([5] * 5 + [7, 1, 2, 3, 9, 9, 9]))

    def test_format2(self):
        # width 8: code 2 len 3 ; raw len 5 (code7 -> 0xE0|4)
        line = bytes([(2 << 5) | 2]) + bytes([0xE0 | 4]) + b"\x0a\x0b\x0c\x0d\x0e"
        body = struct.pack("<H", 2) + line
        d = parse_def(build_def([frame_bytes(2, 8, 1, 8, 1, 0, 0, body)]))
        self.assertEqual(d.blocks[0].frames[0].pixels, bytes([2, 2, 2, 10, 11, 12, 13, 14]))

    def test_format3(self):
        # width 64 => 2 segments of 32, 1 line
        s0 = bytes([(1 << 5) | 31])
        s1 = bytes([(3 << 5) | 15, (4 << 5) | 15])
        body = struct.pack("<2H", 4, 5) + s0 + s1
        d = parse_def(build_def([frame_bytes(3, 64, 1, 64, 1, 0, 0, body)]))
        self.assertEqual(d.blocks[0].frames[0].pixels, bytes([1] * 32 + [3] * 16 + [4] * 16))

    def test_canvas_and_images(self):
        d = parse_def(build_def([frame_bytes(0, 4, 3, 2, 1, 1, 1, bytes([5, 6]))]))
        f = d.blocks[0].frames[0]
        c = frame_to_canvas(f)
        self.assertEqual(c, bytes([0] * 5 + [5, 6] + [0] * 5))
        rgba = to_rgba(c, d.palette)
        self.assertEqual(rgba[:4], b"\0\0\0\0")
        self.assertEqual(len(to_rgb(c, d.palette)), 36)
        ppm = write_ppm(4, 3, to_rgb(c, d.palette))
        self.assertTrue(ppm.startswith(b"P6\n4 3\n255\n"))
        png = write_png(4, 3, rgba)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        # verify IDAT decompresses to filtered rows
        i = png.index(b"IDAT")
        n = struct.unpack(">I", png[i - 4:i])[0]
        raw = zlib.decompress(png[i + 4:i + 4 + n])
        self.assertEqual(len(raw), 3 * (1 + 16))
        with self.assertRaises(ValueError):
            write_png(4, 3, b"x")

    def test_errors(self):
        good = build_def([frame_bytes(0, 4, 2, 4, 2, 0, 0, bytes(8))])
        with self.assertRaises(DefError):
            parse_def(b"")
        with self.assertRaises(DefError):
            parse_def(good[:100])
        with self.assertRaises(DefError):
            parse_def(good[:-1])  # truncated pixels
        with self.assertRaises(DefError):
            parse_def(build_def([frame_bytes(9, 4, 2, 4, 2, 0, 0, bytes(8))]))
        bad = bytearray(good)
        bad[12:16] = struct.pack("<I", 100000)
        with self.assertRaises(DefError):
            parse_def(bytes(bad))
        # RLE run overrunning the line
        body = struct.pack("<I", 4) + bytes([1, 99])
        with self.assertRaises(DefError):
            parse_def(build_def([frame_bytes(1, 4, 1, 4, 1, 0, 0, body)]))
        # bad frame offset
        bad = bytearray(good)
        bad[-8 - 32 - 4:-8 - 32] = b"\xff\xff\xff\x7f"
        with self.assertRaises(DefError):
            parse_def(bytes(bad))


if __name__ == "__main__":
    unittest.main()
