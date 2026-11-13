#!/usr/bin/env python3
"""Count references to the BIOS calls in Neo Geo game program ROMs.

Usage: scan_bios_calls.py <game.zip or P ROM file> ...

Looks for the 32-bit address of every BIOS call slot ($C00402-$C004DA) in the
first program ROM (MAME order, byte-swapped back) and prints the count and the
first offsets, plus the game's level 2 (HBL) interrupt vector. A reference is
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
        hbl = struct.unpack('>I', rom[0x68:0x6C])[0]
        print(f'{os.path.basename(path)} ({name}): level 2 (HBL) vector ${hbl:08X}')
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
