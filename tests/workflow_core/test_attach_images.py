"""Tests for workflow_core.attach_images."""

from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core.attach_images import clean, sniff  # noqa: E402


def png(*chunks):
    out = b"\x89PNG\r\n\x1a\n"
    for kind, data in chunks:
        out += struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return out


def jpeg(*segments):
    out = b"\xff\xd8"
    for marker, payload in segments:
        out += b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload
    return out + b"\xff\xda" + b"\x00\x08scandata" + b"\xff\xd9"


def webp(*chunks):
    body = b"WEBP"
    for fourcc, data in chunks:
        body += fourcc + struct.pack("<I", len(data)) + data + (b"\x00" if len(data) & 1 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body


IHDR = (b"IHDR", bytes(13))
PNG = png(IHDR, (b"eXIf", b"exifdata"), (b"tEXt", b"Comment\x00hi"), (b"IDAT", b"pixels"), (b"IEND", b""))
APP0 = (0xE0, b"JFIF\x00\x01\x01\x00")
EXIF = (0xE1, b"Exif\x00\x00GPS")
XMP = (0xE1, b"http://ns.adobe.com/xap/1.0/\x00<x/>")
DQT = (0xDB, bytes(65))
JPEG = jpeg(APP0, EXIF, XMP, DQT)
WEBP = webp((b"VP8X", bytes([0x0C | 0x10]) + bytes(9)), (b"EXIF", b"exif!"), (b"XMP ", b"xmp"), (b"VP8L", b"data"))
GIF = b"GIF89a" + bytes(7) + b";"


class SniffTests(unittest.TestCase):
    def test_recognises_the_four_types(self):
        self.assertEqual(sniff(PNG), "image/png")
        self.assertEqual(sniff(JPEG), "image/jpeg")
        self.assertEqual(sniff(WEBP), "image/webp")
        self.assertEqual(sniff(GIF), "image/gif")

    def test_refuses_everything_else(self):
        self.assertIsNone(sniff(b"%PDF-1.7"))
        self.assertIsNone(sniff(b""))
        self.assertIsNone(sniff(b"RIFF\x00\x00\x00\x00WAVE"))


class CleanTests(unittest.TestCase):
    def test_png_drops_metadata_chunks_and_trailing_bytes(self):
        want = png(IHDR, (b"IDAT", b"pixels"), (b"IEND", b""))
        self.assertEqual(clean(PNG + b"trailing", "image/png"), want)

    def test_jpeg_drops_app1_and_keeps_the_rest(self):
        want = jpeg(APP0, DQT)
        self.assertEqual(clean(JPEG, "image/jpeg"), want)

    def test_jpeg_skips_fill_byte_before_marker(self):
        filled = JPEG[:2] + b"\xff" + JPEG[2:]
        self.assertEqual(clean(filled, "image/jpeg"), jpeg(APP0, DQT))

    def test_webp_drops_chunks_and_clears_flags(self):
        out = clean(WEBP, "image/webp")
        self.assertNotIn(b"EXIF", out)
        self.assertNotIn(b"XMP ", out)
        self.assertEqual(out[20], 0x10)
        self.assertEqual(struct.unpack("<I", out[4:8])[0], len(out) - 8)
        self.assertEqual(sniff(out), "image/webp")

    def test_gif_is_unchanged(self):
        self.assertEqual(clean(GIF, "image/gif"), GIF)

    def test_broken_structure_raises(self):
        with self.assertRaises(ValueError):
            clean(PNG[:-6], "image/png")
        with self.assertRaises(ValueError):
            clean(b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 4) + b"ab", "image/jpeg")
        bad = b"RIFF" + struct.pack("<I", 16) + b"WEBP" + b"VP8L" + struct.pack("<I", 100) + b"x"
        with self.assertRaises(ValueError):
            clean(bad, "image/webp")


if __name__ == "__main__":
    unittest.main()
