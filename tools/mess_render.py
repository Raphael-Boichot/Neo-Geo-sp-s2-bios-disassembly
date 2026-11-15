#!/usr/bin/env python3
"""Replay MESS_OUT lists of the system ROM on a model of the fix layer, without MAME.

Follows the command set of MessOut ($C1871E, commands 0-13) and draws the result with the
board fix ROM tiles and a palette block of the system ROM. Used to check which fix tiles a
screen uses (`--tiles`) and to draw it (`--png`).

    mess_render.py LIST [LIST ...] [--palettes LABEL] [--png OUT] [--tiles]

LIST and LABEL are names from symbols/rom_names.csv. Needs build/sp-s2.bin and
build/sfix.sfix (`make`).
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sfix  # noqa: E402

ROM = open('build/sp-s2.bin', 'rb').read()
NAMES = {r[1]: int(r[0], 16) for r in csv.reader(open('symbols/rom_names.csv'))
         if r and len(r[0]) == 6 and r[0] != 'addr'}


def rb(a):
    return ROM[a - 0xC00000]


def rw(a):
    return (rb(a) << 8) | rb(a + 1)


def rl(a):
    return (rw(a) << 16) | rw(a + 2)


def run(a1, vram):
    """Run one list from a1; vram maps VRAM word addresses to the words written."""
    st = {'addr': 0, 'd6': 0, 'inc': 1, 'd5': 0}
    stack = []

    def put(w):
        vram[st['addr']] = w & 0xFFFF
        st['addr'] = (st['addr'] + st['inc']) & 0xFFFF

    def text_char(page, c):   # MessOutText8x16Row
        if c < 0x20 or 0x60 <= c < 0x80:
            if c >= 0x60:
                c -= 0x40
            c = (c + 0x80) & 0xFF
            w = (page & 0xF000) | c
            if not page & 0x100:
                w = (w & 0xFF00) | ((c + 0x40) & 0xFF)
            return w
        return page | c

    while True:
        d1, cmd = rb(a1), rb(a1 + 1)
        a1 += 2
        if cmd == 0 or cmd >= 0xE:
            return
        if cmd == 1:
            st['d5'] = (d1 << 16) | rw(a1)
            a1 += 2
        elif cmd == 2:
            st['inc'] = d1 - 256 if d1 >= 128 else d1
        elif cmd == 3:
            st['d6'] = st['addr'] = rw(a1)
            a1 += 2
        elif cmd == 5:
            st['d6'] = st['addr'] = (st['d6'] + rw(a1)) & 0xFFFF
            a1 += 2
        elif cmd in (4, 6, 7):
            if cmd == 4:
                a2 = rl(a1)
                a1 += 4
            else:
                a2 = a1
            d5 = st['d5']
            if d5 & 0x20000:          # words
                if d5 & 0x10000:
                    for _ in range(d5 & 0xFFFF):
                        put(rw(a2))
                        a2 += 2
                else:
                    while rw(a2) != d5 & 0xFFFF:
                        put(rw(a2))
                        a2 += 2
                    a2 += 2
            else:                     # bytes with the high byte of the format word
                hi, end = d5 & 0xFF00, d5 & 0xFF
                if d5 & 0x10000:
                    for _ in range(end):
                        put(hi | rb(a2))
                        a2 += 1
                else:
                    while rb(a2) != end:
                        put(hi | rb(a2))
                        a2 += 1
                    a2 += 1
            if cmd != 4:
                a1 = (a2 + 1) & ~1
        elif cmd in (8, 9):
            st['inc'] = 0x20
            page = d1 << 8
            for half in (0, 1):
                a2 = a1
                while rb(a2) != 0xFF:
                    c = rb(a2)
                    a2 += 1
                    put(page | c if cmd == 8 else text_char(page, c))
                a2 += 1
                if half == 0:
                    st['d6'] += 1
                    st['addr'] = st['d6']
                    page += 0x100
            a1 = (a2 + 1) & ~1
        elif cmd == 10:
            stack.append(a1 + 4)
            a1 = rl(a1)
        elif cmd == 11:
            a1 = stack.pop()
        elif cmd == 12:
            w = rw(a1)
            a1 += 2
            for _ in range(d1 or 256):
                put(w)
        elif cmd == 13:
            w = rw(a1)
            a1 += 2
            for i in range(d1 or 256):
                put((w & 0xFF00) | ((w + i) & 0xFF))


def colour(w):
    r = ((w >> 8) & 15) << 1 | ((w >> 14) & 1)
    g = ((w >> 4) & 15) << 1 | ((w >> 13) & 1)
    b = (w & 15) << 1 | ((w >> 12) & 1)
    return tuple(c * 255 // 31 for c in (r, g, b))


def render(vram, palettes_at, count):
    from PIL import Image
    tiles = open('build/sfix.sfix', 'rb').read()
    pals = [[colour(rw(palettes_at + (p * 16 + i) * 2)) for i in range(16)] for p in range(count)]
    img = Image.new('RGB', (320, 224))
    for ad, w in vram.items():
        if not 0x7000 <= ad < 0x7500 or (w >> 12) >= count:
            continue
        col, row = divmod(ad - 0x7000, 32)
        if not 1 <= col <= 39 or not 2 <= row <= 29:
            continue
        t = w & 0xFFF
        px = sfix.tile_pixels(tiles[t * 32:t * 32 + 32])
        for y in range(8):
            for x in range(8):
                if px[y][x]:
                    img.putpixel(((col - 1) * 8 + x, (row - 2) * 8 + y), pals[w >> 12][px[y][x]])
    return img


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('lists', nargs='+')
    ap.add_argument('--palettes', default='HowToPlayPalettes')
    ap.add_argument('--count', type=int, default=16, help='palettes in the block')
    ap.add_argument('--png')
    ap.add_argument('--tiles', action='store_true')
    a = ap.parse_args()
    vram = {}
    for name in a.lists:
        run(NAMES[name], vram)
    if a.tiles:
        used = sorted({w & 0xFFF for ad, w in vram.items() if 0x7000 <= ad < 0x7500})
        ranges = []
        for t in used:
            if ranges and t == ranges[-1][1] + 1:
                ranges[-1][1] = t
            else:
                ranges.append([t, t])
        print(' '.join(f'${x:03X}' if x == y else f'${x:03X}-${y:03X}' for x, y in ranges))
    if a.png:
        render(vram, NAMES[a.palettes], a.count).save(a.png)


if __name__ == '__main__':
    main()
