#!/usr/bin/env python3
"""Find the routines of SP-S2 in another SNK system ROM, to learn about SP-S2 itself.

Both ROMs are traced (tools/trace.py; the other without hints). Each named SP-S2 routine
(symbols/rom_names.csv) is turned into a list of instructions with every ROM address, branch
target and pc-relative displacement masked (and, for the loose score, RAM addresses too); its
best place in the other ROM is found from the first instructions and scored over the whole
body with difflib.

    compare_bios.py OTHER.bin [--csv OUT]        one ROM (MAME dump, byte-swapped words)
    compare_bios.py --name NAME OTHER.bin ...    one routine, side by side

Scores: 1.00 = same instructions (addresses aside); 'ram' = 1.00 also with RAM addresses compared.
"""
import argparse
import csv
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import trace as tr  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
HEX = re.compile(r'\$([0-9a-f]+)')
MAXLEN = 400
KEY = 5


def load_swapped(path):
    d = open(path, 'rb').read()[:tr.SIZE]
    return bytes(b for i in range(0, len(d), 2) for b in (d[i + 1], d[i]))


def norm(ins, keep_ram):
    def sub(m):
        v = int(m.group(1), 16)
        if 0xC00000 <= v < 0xC20000:
            return 'ROM'
        if not keep_ram and (0x100000 <= v < 0x110000 or 0xD00000 <= v < 0xD10000):
            return 'RAM'
        return m.group(0)
    ops = HEX.sub(sub, ins.op_str)
    ops = re.sub(r'-?\$?[0-9a-fx]+\(pc', 'D(pc', ops)
    mn = ins.mnemonic
    if mn.startswith(('b', 'db')) and mn not in ('btst', 'bset', 'bclr', 'bchg'):
        mn = re.sub(r'\.[sbw]$', '', mn)     # branch size may change with distances
    return f'{mn} {ops}'


def linear(md, rom, addr, n, keep_ram):
    """n instructions decoded straight from addr (for code the hint-less trace did not reach)."""
    off = addr - tr.BASE
    out = []
    for ins in md.disasm(rom[off:off + 12 * n], addr):
        if ins.id == 0 or len(out) >= n:
            break
        out.append(norm(ins, keep_ram))
    return out


def pattern(t, addrs, index, start, n=8):
    """Regex of the first n instructions: opcode words literal, extension words wild."""
    parts = []
    i = index[start]
    for a in addrs[i:i + n]:
        ins = t.insn[a]
        parts.append(re.escape(bytes(ins.bytes[:2])) + b'.' * (ins.size - 2))
    return re.compile(b''.join(parts), re.S)


def sequences(t):
    addrs = sorted(t.insn)
    return addrs, {a: i for i, a in enumerate(addrs)}


def body(t, addrs, index, start, stops, keep_ram):
    out = []
    i = index[start]
    while i < len(addrs) and len(out) < MAXLEN:
        a = addrs[i]
        if out and a in stops:
            break
        if i and a != start and addrs[i - 1] + t.insn[addrs[i - 1]].size != a:
            break                               # gap: data between
        out.append(norm(t.insn[a], keep_ram))
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('other', nargs='+')
    ap.add_argument('--csv')
    ap.add_argument('--name')
    a = ap.parse_args()
    s2 = open(os.path.join(ROOT, 'build', 'sp-s2.bin'), 'rb').read()
    hints = tr.load_hints(os.path.join(ROOT, 'tools', 'hints.txt'))
    t1 = tr.trace(s2, hints)
    a1, i1 = sequences(t1)
    names = {}
    for r in csv.DictReader(open(os.path.join(ROOT, 'symbols', 'rom_names.csv'))):
        v = int(r['addr'], 16)
        if v in t1.insn:
            names[v] = r['name']
    stops = set(names)
    out = csv.writer(open(a.csv, 'w', newline='')) if a.csv else None
    if out:
        out.writerow(['addr', 'name', 'instructions'] + [os.path.basename(p) for p in a.other])
    others = []
    for p in a.other:
        rom = load_swapped(p)
        t2 = tr.trace(rom, tr.load_hints(None))
        a2, i2 = sequences(t2)
        loose = [norm(t2.insn[x], False) for x in a2]
        strict = [norm(t2.insn[x], True) for x in a2]
        idx = {}
        for k in range(len(loose) - KEY):
            idx.setdefault(tuple(loose[k:k + KEY]), []).append(k)
        others.append((p, t2, a2, loose, strict, idx, rom))
    for start, name in sorted(names.items()):
        if a.name and name != a.name:
            continue
        b_loose = body(t1, a1, i1, start, stops, False)
        b_strict = body(t1, a1, i1, start, stops, True)
        row = [f'{start:06X}', name, len(b_loose)]
        pat = pattern(t1, a1, i1, start)
        for p, t2, a2, loose, strict, idx, rom in others:
            best = (0, None, False)
            cands = idx.get(tuple(b_loose[:KEY]), []) if len(b_loose) >= KEY else \
                [k for k in range(len(loose)) if loose[k:k + len(b_loose)] == b_loose]
            for k in cands[:50]:
                seg = loose[k:k + len(b_loose) + 8]
                sm = difflib.SequenceMatcher(None, b_loose, seg[:len(b_loose)], autojunk=False)
                r = sm.ratio()
                if r > best[0]:
                    same_ram = strict[k:k + len(b_strict)] == b_strict
                    best = (r, a2[k], same_ram)
            if best[0] < 0.9 and len(b_loose) >= 4:
                # not in the traced code: search the whole ROM, decode straight from each hit
                for m in list(pat.finditer(rom))[:50]:
                    if m.start() % 2:
                        continue
                    at = tr.BASE + m.start()
                    seg = linear(t2.md, rom, at, len(b_loose), False)
                    r = difflib.SequenceMatcher(None, b_loose, seg, autojunk=False).ratio()
                    if r > best[0]:
                        best = (r, at, linear(t2.md, rom, at, len(b_strict), True) == b_strict, 'untraced')
            if best[1] is None:
                row.append('-')
            else:
                row.append(f'{best[1]:06X} {best[0]:.2f}{" ram" if best[2] else ""}{" untraced" if len(best) > 3 else ""}')
            if a.name and best[1] is not None:
                seg = linear(t2.md, rom, best[1], len(b_loose), False)
                print(f'== {os.path.basename(p)} at {best[1]:06X}, score {best[0]:.2f}')
                for tag, i, j, x, y in difflib.SequenceMatcher(None, b_loose, seg, autojunk=False).get_opcodes():
                    if tag != 'equal':
                        print(f'  {tag}: SP-S2 {b_loose[i:j]} | other {seg[x:y]}')
        if out:
            out.writerow(row)
        elif not a.name:
            print(' '.join(str(x) for x in row))


if __name__ == '__main__':
    main()
