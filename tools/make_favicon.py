#!/usr/bin/env python3
"""
Build src/static/favicon.ico from src/static/favicon-32.png (stdlib only).

An .ico file can wrap a PNG image directly (since Windows Vista): a 6-byte
ICONDIR header, one 16-byte ICONDIRENTRY, followed by the raw PNG bytes.

Usage: python tools/make_favicon.py
"""
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PNG_PATH = ROOT / "src" / "static" / "favicon-32.png"
ICO_PATH = ROOT / "src" / "static" / "favicon.ico"


def png_dimensions(data: bytes) -> tuple:
    # PNG signature (8 bytes) + IHDR chunk: length(4) type(4) width(4) height(4) ...
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def build_ico(png_bytes: bytes) -> bytes:
    width, height = png_dimensions(png_bytes)
    # ICO stores 256 as 0 in the single-byte width/height fields.
    w_byte = 0 if width >= 256 else width
    h_byte = 0 if height >= 256 else height

    # ICONDIR: reserved(2)=0, type(2)=1 (icon), count(2)=1
    icondir = struct.pack("<HHH", 0, 1, 1)
    # ICONDIRENTRY: width(1) height(1) colors(1)=0 reserved(1)=0
    #   planes(2)=1 bitcount(2)=32 bytesInRes(4) offset(4)
    offset = 6 + 16
    entry = struct.pack(
        "<BBBBHHII",
        w_byte, h_byte, 0, 0,
        1, 32,
        len(png_bytes), offset,
    )
    return icondir + entry + png_bytes


def main() -> int:
    if not PNG_PATH.exists():
        print(f"error: {PNG_PATH} not found (run tools/render-images.ps1 first)", file=sys.stderr)
        return 1
    png_bytes = PNG_PATH.read_bytes()
    ico_bytes = build_ico(png_bytes)
    ICO_PATH.write_bytes(ico_bytes)
    print(f"wrote {ICO_PATH} ({len(ico_bytes)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
