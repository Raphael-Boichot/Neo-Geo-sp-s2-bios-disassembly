#!/usr/bin/env python3
"""Draw a byte map of the system ROM: one pixel per byte, 512 bytes per row.

Usage: rom_map.py <rom.sp1> <out.png> [coverage/*.txt]

Colour = what the byte is (same classification as gen_source.py); brightness
follows the byte value so the texture of code and tables stays visible. With
coverage files, code that ran in MAME is drawn brighter than code that did not.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_source as G  # noqa: E402
import symbols as S     # noqa: E402
import trace as T       # noqa: E402

ROW = 512
SCALE = 2
COLORS = {
    'header':  (220, 60, 60),    # vectors, checksum, ID string, type/region
    'code':    (60, 120, 230),   # traced code (not run / no coverage given)
    'run':     (90, 200, 255),   # traced code executed in MAME
    'jmptab':  (255, 150, 40),   # BIOS call table and code-pointer tables
    'ptr':     (210, 80, 210),   # other ROM pointers in data
    'text':    (245, 215, 60),   # ASCII text
    'data':    (70, 190, 110),   # other data (byte/word tables)
    'free':    (45, 45, 50),     # $FF fill
}
LEGEND = [('header', 'Vectors and header'), ('code', 'Code (traced)'), ('run', 'Code run in MAME'),
          ('jmptab', 'BIOS call table, code-pointer tables'), ('ptr', 'Pointers in data'),
          ('text', 'Text'), ('data', 'Other data'), ('free', 'Free ($FF)')]


def classify(rom, t, g, ran):
    cls = ['data'] * len(rom)
    for off in range(len(rom)):
        k = g.kinds[off]
        if k == 'C':
            cls[off] = 'run' if t.owner[off] in ran else 'code'
        elif k == 'F':
            cls[off] = 'free'
    for off in g.ptr_longs:
        for k in range(4):
            cls[off + k] = 'ptr'
    for tbl, (size, n, _) in t.tables.items():
        for k in range(size * n):
            cls[tbl - T.BASE + k] = 'jmptab'
    for off in range(0x402, 0x4DC):          # BIOS call slots
        cls[off] = 'jmptab' if cls[off] in ('code', 'run') else cls[off]
    for off in range(0, 0x100):
        if g.kinds[off] != 'F':
            cls[off] = 'header'
    cls[0x400] = cls[0x401] = 'header'
    # text runs inside data
    off = 0
    while off < len(rom):
        if g.kinds[off] == 'D' and cls[off] == 'data':
            m = G.TEXT_RUN.match(rom[off:off + 256])
            if m and g.kinds[off + len(m.group()) - 1] == 'D':
                for k in range(len(m.group())):
                    cls[off + k] = 'text'
                off += len(m.group())
                continue
        off += 1
    for a, b in S.TABLE_RANGES:
        for off in range(a - T.BASE, b - T.BASE + 1):
            if cls[off] == 'text':
                cls[off] = 'data'
    return cls


def regions(cls, minlen=1024):
    """Big blocks for the side labels: runs separated by free space."""
    out, start = [], None
    for off in range(len(cls) + 1):
        free = off == len(cls) or cls[off] == 'free'
        if not free and start is None:
            start = off
        if free and start is not None:
            out.append((start, off))
            start = None
    blocks = []
    for s, e in out:
        if e - s < 64:
            continue
        comp = {}
        for c in cls[s:e]:
            comp[c] = comp.get(c, 0) + 1
        blocks.append((s, e, comp))
    frees, s = [], None
    for off in range(len(cls) + 1):
        f = off < len(cls) and cls[off] == 'free'
        if f and s is None:
            s = off
        if not f and s is not None:
            if off - s >= minlen:
                frees.append((s, off))
            s = None
    return blocks, frees


def compact(rom, cls, out, ran, font, small, bold):
    """Used bytes only: free runs of 1 KB or more become thin labelled bars."""
    import csv
    row, sc, bar = 256, 3, 18
    _, frees = regions(cls)
    segs, pos = [], 0
    for fs, fe in frees:
        if fs > pos:
            segs.append(('used', pos, fs))
        segs.append(('free', fs, fe))
        pos = fe
    if pos < len(cls):
        segs.append(('used', pos, len(cls)))
    left, top = 90, 50
    height = 0
    layout = []
    for kind, s0, e0 in segs:
        if kind == 'free':
            layout.append((kind, s0, e0, height))
            height += bar
        else:
            r0, r1 = s0 // row, (e0 + row - 1) // row
            layout.append((kind, s0, e0, height))
            height += (r1 - r0) * sc
    W, H = left + row * sc + 330, top + height + 120
    canvas = Image.new('RGB', (W, H), (250, 250, 248))
    d = ImageDraw.Draw(canvas)
    d.text((left, 14), 'SP-S2 used bytes  (free space folded, 256 bytes per row)', fill=(20, 20, 20), font=bold)
    px = canvas.load()
    for kind, s0, e0, y in layout:
        y += top
        if kind == 'free':
            d.rectangle([left, y + 3, left + row * sc - 1, y + bar - 4], fill=COLORS['free'])
            d.text((left + 8, y + 3), f'free ${T.BASE + s0:06X}-${T.BASE + e0 - 1:06X}  {e0 - s0:,} bytes',
                   fill=(220, 220, 220), font=small)
            continue
        r0 = s0 // row
        for off in range(s0, e0):
            c = COLORS[cls[off]]
            f = 1.0 if cls[off] == 'free' else 0.45 + 0.55 * rom[off] / 255
            col = tuple(int(v * f) for v in c)
            x, yy = left + (off % row) * sc, y + (off // row - r0) * sc
            for dx in range(sc):
                for dy in range(sc):
                    px[x + dx, yy + dy] = col
        for r in range(r0, (e0 + row - 1) // row):
            if r % 8 == 0 or r == r0:
                yy = y + (r - r0) * sc
                d.text((6, yy - 2), f'${T.BASE + r * row:06X}', fill=(60, 60, 60), font=small)
                d.line([(left - 5, yy), (left - 1, yy)], fill=(80, 80, 80))
    # named regions
    rpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'symbols', 'regions.csv')
    if os.path.exists(rpath):
        for r in csv.DictReader(open(rpath)):
            a0, a1 = int(r['start'], 16) - T.BASE, int(r['end'], 16) - T.BASE + 1
            for kind, s0, e0, y in layout:
                if kind == 'used' and s0 <= a0 < e0:
                    r0 = s0 // row
                    y0 = top + y + (a0 // row - r0) * sc
                    y1 = top + y + ((a1 - 1) // row - r0 + 1) * sc
                    x0 = left + (a0 % row) * sc if a1 - a0 < row else left
                    x1 = left + ((a1 - 1) % row + 1) * sc if a1 - a0 < row else left + row * sc
                    d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 255, 255))
                    xr = left + row * sc + 12
                    d.line([(x1, (y0 + y1) // 2), (xr - 2, (y0 + y1) // 2)], fill=(150, 150, 150))
                    d.text((xr, (y0 + y1) // 2 - 7), f"{r['name']} ({r['tag']})", fill=(30, 30, 30), font=font)
    y, x = top + height + 16, left
    for i, (k, label) in enumerate(LEGEND):
        if k == 'run' and not ran:
            continue
        d.rectangle([x, y, x + 16, y + 12], fill=COLORS[k])
        d.text((x + 22, y - 1), label, fill=(30, 30, 30), font=small)
        y += 20
        if y > H - 20:
            y, x = top + height + 16, x + 330
    canvas.save(out, optimize=True)
    print(f'{out}: {W}x{H}')


def main():
    rom = G.swap(open(sys.argv[1], 'rb').read())
    out = sys.argv[2]
    ran = set()
    for p in sys.argv[3:]:
        for line in open(p):
            line = line.strip()
            if line:
                ran.add(int(line, 16))
    t = T.trace(rom, T.load_hints(os.path.join(os.path.dirname(__file__), 'hints.txt')))
    g = G.Gen(rom, t)
    cls = classify(rom, t, g, ran)

    rows = len(rom) // ROW
    img = Image.new('RGB', (ROW, rows))
    px = img.load()
    for off, b in enumerate(rom):
        c = COLORS[cls[off]]
        f = 1.0 if cls[off] == 'free' else 0.45 + 0.55 * b / 255
        px[off % ROW, off // ROW] = tuple(int(v * f) for v in c)
    img = img.resize((ROW * SCALE, rows * SCALE), Image.NEAREST)

    left, right, top, bottom = 90, 430, 50, 150
    W, H = left + img.width + right, top + img.height + bottom
    canvas = Image.new('RGB', (W, H), (250, 250, 248))
    canvas.paste(img, (left, top))
    d = ImageDraw.Draw(canvas)
    fdir = '/usr/share/fonts/truetype/dejavu/'
    try:
        font = ImageFont.truetype(fdir + 'DejaVuSansMono.ttf', 13)
        bold = ImageFont.truetype(fdir + 'DejaVuSans-Bold.ttf', 18)
        small = ImageFont.truetype(fdir + 'DejaVuSansMono.ttf', 11)
    except OSError:
        font = bold = small = ImageFont.load_default()
    d.text((left, 14), 'SP-S2 system ROM byte map  ($C00000-$C1FFFF, 1 pixel = 1 byte, 512 bytes per row)',
           fill=(20, 20, 20), font=bold)
    for r in range(0, rows + 1, 16):                      # every $2000
        y = top + r * SCALE
        d.line([(left - 6, y), (left, y)], fill=(80, 80, 80))
        d.text((6, y - 7), f'${T.BASE + r * ROW:06X}', fill=(60, 60, 60), font=font)
    for col in range(0, ROW + 1, 128):
        x = left + col * SCALE
        d.text((x - 10, top - 18), f'+{col:03X}', fill=(110, 110, 110), font=small)

    # side labels
    blocks, frees = regions(cls)
    labels = []
    names = {'run': 'code', 'code': 'code', 'jmptab': 'tables', 'ptr': 'pointers',
             'text': 'text', 'data': 'data', 'header': 'header'}
    for s, e, comp in blocks:
        if e - s < 1024 and s > 0x100:
            continue
        agg = {}
        for k, v in comp.items():
            if k != 'free':
                agg[names[k]] = agg.get(names[k], 0) + v
        tot = sum(agg.values())
        parts = ', '.join(f'{k} {100 * v // tot}%' for k, v in sorted(agg.items(), key=lambda x: -x[1]) if 100 * v // tot >= 3)
        labels.append((s, e, f'${T.BASE + s:06X}-${T.BASE + e - 1:06X} {e - s:6,d} B', parts))
    for s, e in frees:
        labels.append((s, e, f'${T.BASE + s:06X}-${T.BASE + e - 1:06X} {e - s:6,d} B', 'free'))
    labels.sort()
    ytext = top
    for s, e, l1, l2 in labels:
        ymid = top + ((s + e) // 2 // ROW) * SCALE
        y = max(ytext, ymid - 14)
        x0 = left + img.width
        d.line([(x0 + 2, ymid), (x0 + 22, ymid), (x0 + 30, y + 13)], fill=(150, 150, 150))
        d.text((x0 + 34, y), l1, fill=(30, 30, 30), font=font)
        d.text((x0 + 34, y + 15), l2, fill=(90, 90, 90), font=font)
        ytext = y + 36

    # legend with byte counts
    counts = {}
    for c in cls:
        counts[c] = counts.get(c, 0) + 1
    y = top + img.height + 20
    x = left
    for k, label in LEGEND:
        if k == 'run' and not ran:
            continue
        d.rectangle([x, y, x + 18, y + 14], fill=COLORS[k])
        txt = f'{label} ({counts.get(k, 0):,} B)'
        d.text((x + 24, y), txt, fill=(30, 30, 30), font=font)
        y += 22
        if y > H - 30:
            y, x = top + img.height + 20, x + 420
    if ran:
        d.text((left + 420, H - 28), f'coverage: {len(sys.argv) - 3} MAME runs', fill=(90, 90, 90), font=font)
    # named regions (symbols/regions.csv): outline and label on the map
    import csv
    rpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'symbols', 'regions.csv')
    if os.path.exists(rpath):
        for r in csv.DictReader(open(rpath)):
            s0, e0 = int(r['start'], 16) - T.BASE, int(r['end'], 16) - T.BASE + 1
            y0, y1 = top + (s0 // ROW) * SCALE, top + ((e0 + ROW - 1) // ROW) * SCALE
            if e0 - s0 < ROW:            # short region inside one row
                x0, x1 = left + (s0 % ROW) * SCALE, left + ((e0 - 1) % ROW + 1) * SCALE
            else:
                x0, x1 = left, left + img.width
            d.rectangle([x0, y0, x1 - 1, y1 - 1], outline=(255, 255, 255), width=1)
            if y1 - y0 < 6:
                continue                 # too thin to label: see the compact map
            lab = f"{r['name']} ({r['tag']})"
            tx, ty = x0 + 4, y0 + 2 if y1 - y0 >= 16 else y1 + 1
            d.text((tx + 1, ty + 1), lab, fill=(0, 0, 0), font=small)
            d.text((tx, ty), lab, fill=(255, 255, 255), font=small)
    canvas.save(out, optimize=True)
    print(f'{out}: {W}x{H}', {k: counts.get(k, 0) for k in COLORS})
    compact(rom, cls, out.replace('.png', '_used.png'), ran, font, small, bold)


if __name__ == '__main__':
    main()
