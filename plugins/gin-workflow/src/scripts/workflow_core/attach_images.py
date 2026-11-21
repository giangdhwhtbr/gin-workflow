"""The image types gin attach accepts, by magic bytes, and EXIF/XMP removal before hashing."""

from __future__ import annotations

import struct

EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}
_PNG = b"\x89PNG\r\n\x1a\n"
_PNG_DROP = {b"eXIf", b"tEXt", b"zTXt", b"iTXt"}
_WEBP_DROP = {b"EXIF", b"XMP "}
_VP8X_EXIF_XMP = 0x08 | 0x04


def sniff(data: bytes) -> str | None:
    if data.startswith(_PNG):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


def clean(data: bytes, mime: str) -> bytes:
    """`data` without EXIF and XMP metadata; ValueError when its structure is broken."""
    if mime == "image/png":
        return _png(data)
    if mime == "image/jpeg":
        return _jpeg(data)
    if mime == "image/webp":
        return _webp(data)
    return data


def _png(data: bytes) -> bytes:
    if not data.startswith(_PNG):
        raise ValueError("not a PNG file")
    out, at = [_PNG], len(_PNG)
    while at < len(data):
        if at + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length, kind = struct.unpack(">I4s", data[at:at + 8])
        end = at + 12 + length
        if end > len(data):
            raise ValueError("truncated PNG chunk")
        if kind not in _PNG_DROP:
            out.append(data[at:end])
        at = end
        if kind == b"IEND":
            return b"".join(out)
    raise ValueError("PNG without IEND")


def _jpeg(data: bytes) -> bytes:
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("not a JPEG file")
    out, at = [data[:2]], 2
    while at + 1 < len(data):
        if data[at] != 0xFF:
            raise ValueError("JPEG marker expected")
        marker = data[at + 1]
        if marker == 0xFF:  # fill byte
            at += 1
            continue
        if marker == 0xD9:
            raise ValueError("JPEG ends before image data")
        if marker == 0xD8:
            raise ValueError("unexpected SOI in JPEG")
        if marker == 0xDA:  # start of scan: the rest is image data
            out.append(data[at:])
            return b"".join(out)
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:  # markers without a length
            out.append(data[at:at + 2])
            at += 2
            continue
        if at + 4 > len(data):
            raise ValueError("truncated JPEG segment")
        end = at + 2 + struct.unpack(">H", data[at + 2:at + 4])[0]
        if end > len(data):
            raise ValueError("truncated JPEG segment")
        if marker != 0xE1:  # APP1 holds Exif and XMP
            out.append(data[at:end])
        at = end
    raise ValueError("JPEG without image data")


def _webp(data: bytes) -> bytes:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise ValueError("not a WebP file")
    end = 8 + struct.unpack("<I", data[4:8])[0]
    if end > len(data) or end < 12:
        raise ValueError("truncated WebP")
    chunks, at = [], 12
    while at < end:
        if at + 8 > end:
            raise ValueError("truncated WebP chunk")
        kind, length = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
        stop = at + 8 + length + (length & 1)
        if stop > end:
            raise ValueError("truncated WebP chunk")
        if kind not in _WEBP_DROP:
            chunk = bytearray(data[at:stop])
            if kind == b"VP8X" and length:
                chunk[8] &= ~_VP8X_EXIF_XMP & 0xFF
            chunks.append(bytes(chunk))
        at = stop
    body = b"WEBP" + b"".join(chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body
