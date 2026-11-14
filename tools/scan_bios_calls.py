#!/usr/bin/env python3
"""Count references to the BIOS calls in Neo Geo game program ROMs.

Usage: scan_bios_calls.py <game.zip or P ROM file> ...

Looks for the 32-bit address of every BIOS call slot ($C00402-$C004DA) in the
first program ROM (MAME order, byte-swapped back) and prints the count and the
first offsets, plus the game's NGH number and level 2 (HBL) interrupt vector (header at $100 of the
program, or at $100000 in the file for a 2 MB P1 that MAME loads second half first). A reference is
usually `jsr`/`jmp` to the slot; 0 references means the game never calls it.
"""
import io
import os
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import symbols as S  # noqa: E402


def prom(path):
    if path.lower().endswith('.zip'):
        with zipfile.ZipFile(path) as z:
            names = sorted(n for n in z.namelist() if 'p1' in n.lower())
            return names[0], z.read(names[0])
    return os.path.basename(path), open(path, 'rb').read()


def main():
    slots = sorted((a, n) for a, n in S.ROM_NAMES.items() if 0xC00402 <= a <= 0xC004DA)
    for path in sys.argv[1:]:
        name, data = prom(path)
        rom = bytes(data[i ^ 1] for i in range(len(data)))
        # a 2 MB P1 (KOF '94) is loaded by MAME second half first: its header is at $100000 in the file
        hdr = 0 if rom[0x100:0x107] == b'NEO-GEO' else 0x100000
        assert rom[hdr + 0x100:hdr + 0x107] == b'NEO-GEO', 'no NEO-GEO header'
        hbl = struct.unpack('>I', rom[hdr + 0x68:hdr + 0x6C])[0]
        ngh = rom[hdr + 0x108] << 8 | rom[hdr + 0x109]
        print(f'{os.path.basename(path)} ({name}): NGH {ngh:03X}, level 2 (HBL) vector ${hbl:08X}')
        for a, n in slots:
            b, offs, i = a.to_bytes(4, 'big'), [], -1
            while True:
                i = rom.find(b, i + 1)
                if i < 0:
                    break
                offs.append(i - 2)
            print(f'  {n:18s} ${a:06X}: {len(offs):3d}  ' + ' '.join(f'{o:06X}' for o in offs[:5]))


if __name__ == '__main__':
    main()
