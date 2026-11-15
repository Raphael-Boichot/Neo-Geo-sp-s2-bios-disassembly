#!/usr/bin/env python3
"""Board fix ROM (sfix.sfix): tile sheets <-> ROM image.

Usage: sfix.py extract <sfix.sfix> <dir>   write <dir>/bank_0.png .. bank_F.png
       sfix.py build <dir> <out.sfix>       rebuild the ROM from the sheets
       sfix.py check <file> <sha1>

sfix.sfix is the fix-layer graphics ROM on the MVS motherboard (128 KB, 4096 tiles of 8x8 pixels,
4 bits per pixel, 32 bytes per tile). The system ROM selects it with REG_BRDFIX for its own screens
(test mode, eyecatcher, errors, the FBI screen) and the cartridge fix ROM with REG_CRTFIX.

Each sheet is one bank of 256 tiles, 16 x 16 tiles (128 x 128 pixels), an indexed PNG whose pixel
values are the 4-bit colour indexes (grey palette: the real colours come from the palette RAM).
Tile n is bank n >> 8, column n & 15, row (n >> 4) & 15.

Tile byte layout (NeoGeoDev wiki, Fix layer): 8 rows per column pair; bytes $10-$17 hold columns
0-1, $18-$1F columns 2-3, $00-$07 columns 4-5, $08-$0F columns 6-7; low nibble = left pixel.
"""
import hashlib
import os
import sys

from PIL import Image

PAIRS = ((0, 0x10), (2, 0x18), (4, 0x00), (6, 0x08))   # (first column, byte offset)
GREYS = [v for i in range(16) for v in (i * 17,) * 3]


def tile_pixels(t):
    px = [[0] * 8 for _ in range(8)]
    for y in range(8):
        for x, base in PAIRS:
            b = t[base + y]
            px[y][x], px[y][x + 1] = b & 15, b >> 4
    return px


def tile_bytes(px):
    t = bytearray(32)
    for y in range(8):
        for x, base in PAIRS:
            t[base + y] = px[y][x] | px[y][x + 1] << 4
    return bytes(t)


def extract(rom, out):
    data = open(rom, 'rb').read()
    assert len(data) == 0x20000, 'sfix.sfix must be 128 KB'
    os.makedirs(out, exist_ok=True)
    for bank in range(16):
        im = Image.new('P', (128, 128))
        im.putpalette(GREYS)
        for i in range(256):
            px = tile_pixels(data[(bank * 256 + i) * 32:][:32])
            for y in range(8):
                for x in range(8):
                    im.putpixel(((i & 15) * 8 + x, (i >> 4) * 8 + y), px[y][x])
        im.save(os.path.join(out, f'bank_{bank:X}.png'), bits=4, optimize=True)


def build(src, out):
    data = bytearray()
    for bank in range(16):
        im = Image.open(os.path.join(src, f'bank_{bank:X}.png'))
        assert im.mode == 'P' and im.size == (128, 128), f'bank_{bank:X}.png: 128x128 indexed expected'
        for i in range(256):
            px = [[im.getpixel(((i & 15) * 8 + x, (i >> 4) * 8 + y)) for x in range(8)] for y in range(8)]
            assert all(v < 16 for row in px for v in row), f'bank {bank:X} tile {i:02X}: index above 15'
            data += tile_bytes(px)
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    open(out, 'wb').write(data)


def check(path, sha1):
    h = hashlib.sha1(open(path, 'rb').read()).hexdigest()
    print(('OK   ' if h == sha1 else 'DIFF ') + f' sha1 {h}  {path}')
    sys.exit(0 if h == sha1 else 1)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if cmd == 'extract':
        extract(sys.argv[2], sys.argv[3])
    elif cmd == 'build':
        build(sys.argv[2], sys.argv[3])
    elif cmd == 'check':
        check(sys.argv[2], sys.argv[3])
    else:
        sys.exit(__doc__)
