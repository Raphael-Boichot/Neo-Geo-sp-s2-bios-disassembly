#!/usr/bin/env python3
"""000-lo.lo, the sprite vertical shrink table (L0 ROM), rebuilt from its rule.

The table has 256 rows of 256 bytes, one row per vertical shrink value z (0-255).
Each byte is a sprite line number 0-255 (high nibble: tile of the column, low nibble:
pixel row in the tile; NeoGeoDev wiki, L0 ROM). Row z lists the z + 1 lines that are
drawn, in increasing order, then $FF.

Rule (found from the dump, every byte checked by `check`): going from z - 1 to z adds
one line, the bit-reversed value of (z XOR $11). So row 255 is 0, 1, 2 .. 255 and row 0
draws only line $88.

The ROM is 128 KB but the video hardware reads 64 KB: the dump holds the table twice.

    lo_rom.py build OUT       write the 128 KB ROM
    lo_rom.py check FILE SHA1 compare a file with the SHA-1
    lo_rom.py verify FILE     check a dump against the rule, row by row
"""
import hashlib
import sys


def bit_reverse8(x):
    return int(f'{x:08b}'[::-1], 2)


def table():
    """The 64 KB shrink table."""
    out = bytearray()
    lines = []
    for z in range(256):
        lines.append(bit_reverse8(z ^ 0x11))
        out += bytes(sorted(lines)) + b'\xff' * (255 - z)
    return bytes(out)


def rom():
    return table() * 2


def main(argv):
    if len(argv) == 3 and argv[1] == 'build':
        with open(argv[2], 'wb') as f:
            f.write(rom())
        return 0
    if len(argv) == 4 and argv[1] == 'check':
        sha1 = hashlib.sha1(open(argv[2], 'rb').read()).hexdigest()
        if sha1 != argv[3].lower():
            print(f'FAIL  sha1 {sha1}  {argv[2]} (expected {argv[3]})')
            return 1
        print(f'OK    sha1 {sha1}  {argv[2]}')
        return 0
    if len(argv) == 3 and argv[1] == 'verify':
        data = open(argv[2], 'rb').read()
        ref = rom()
        if len(data) != len(ref):
            print(f'size {len(data)}, expected {len(ref)}')
            return 1
        bad = [i // 256 for i in range(0, len(ref), 256) if data[i:i + 256] != ref[i:i + 256]]
        if bad:
            print(f'{len(bad)} rows differ, first: half {bad[0] // 256} row {bad[0] % 256}')
            return 1
        print('all 512 rows match the rule')
        return 0
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
