#!/usr/bin/env python3
"""Make a copy of a game set whose cartridge header ID reads NEO-CLN (MAME only).

Usage: neo_cln_test.py <game.zip> <out_dir>

CheckCartridgeId ($C12FFA) treats a cartridge whose ID at $100 is NEO-CLN as one
with its own calendar chip: the system ROM copies that calendar to the board
calendar and opens the hardware test on its calendar screen (D also sets the
cartridge calendar). This writes <out_dir>/<game>.zip with only the ID changed in
the first program ROM (MAME order). Put neogeo.zip in <out_dir> too, then e.g.
  MAME_ROMS=<out_dir> tools/mame_coverage.sh neo_cln_cartridge sengoku2 LAST=900 KEYS="600:P1 D"
"""
import os
import sys
import zipfile

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
with zipfile.ZipFile(src) as zi, zipfile.ZipFile(os.path.join(out, os.path.basename(src)), 'w') as zo:
    p1 = sorted(n for n in zi.namelist() if 'p1' in n.lower())[0]
    for n in zi.namelist():
        d = bytearray(zi.read(n))
        if n == p1:
            assert bytes(d[i ^ 1] for i in range(0x100, 0x107)) == b'NEO-GEO', 'no NEO-GEO ID'
            for i, c in enumerate(b'NEO-CLN'):
                d[(0x100 + i) ^ 1] = c         # MAME order: bytes swapped in each word
        zo.writestr(n, bytes(d))
print(os.path.join(out, os.path.basename(src)), '(', p1, 'ID set to NEO-CLN )')
