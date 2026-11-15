#!/usr/bin/env python3
"""sm1.sm1, the board's Z80 sound program: trace, source generation, build and check.

    sm1.py source ROM            trace the code and write sm1/src/sm1.asm
    sm1.py build ASM OUT         assemble with z80asm and write the 128 KB ROM (64 KB twice)
    sm1.py check FILE SHA1       compare a file with the SHA-1
    sm1.py stats ROM             code / data / padding counts and unresolved jumps

Names: sm1/names.csv (addr,name,tag,note: ROM labels and RAM / port names).
Hints: sm1/hints.txt, one per line:
    entry ADDR [reason]          code entry not found by the trace
    jptable ADDR COUNT           COUNT `jp nn` instructions in a row (a jump table)
    wtable ADDR COUNT [code|data] COUNT little-endian words pointing at code or data
    data ADDR LEN [WIDTH]        bytes kept as data, WIDTH per line
    imm ADDR                     the 16-bit operand of the instruction at ADDR is a ROM address
                                 (automatic for ld hl/ix/iy,nn with nn in the program)
    number ADDR                  the ROM-range operand at ADDR is a number, not an address
    jpind ADDR                   the jp (hl/ix/iy) at ADDR is resolved by another hint
    text ADDR LEN                ASCII text
"""
import csv
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from z80dis import decode  # noqa: E402
import sm1_data  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
SM1 = os.path.join(ROOT, 'sm1')
SIZE = 0x10000
VECTORS = [0x0000, 0x0008, 0x0010, 0x0018, 0x0020, 0x0028, 0x0038, 0x0066]


def load_names():
    """ROM and RAM names by address; ports (addr written P04) by port number."""
    names, ports = {}, {}
    path = os.path.join(SM1, 'names.csv')
    if os.path.exists(path):
        seen = set()
        for r in csv.DictReader(open(path, newline='')):
            if r['addr'].startswith('P'):
                ports[int(r['addr'][1:], 16)] = (r['name'], r['tag'], r.get('note', ''))
                seen.add(r['name'])
                continue
            a = int(r['addr'], 16)
            if a in names or r['name'] in seen:
                raise SystemExit(f'names.csv: {r["addr"]} or {r["name"]} twice')
            if r['tag'] not in ('W', 'C', 'I', '?'):
                raise SystemExit(f'names.csv: bad tag at {r["addr"]}')
            seen.add(r['name'])
            names[a] = (r['name'], r['tag'], r.get('note', ''))
    return names, ports


def load_hints():
    hints = []
    path = os.path.join(SM1, 'hints.txt')
    for line in open(path) if os.path.exists(path) else ():
        line = line.split('#')[0].split()
        if line:
            hints.append(line)
    return hints


class Trace:
    def __init__(self, rom):
        self.rom = rom
        self.code = {}          # address -> Insn
        self.owner = {}         # byte address -> instruction start
        self.data = {}          # start -> (len, width, kind)
        self.labels = {}        # address -> 'sub' | 'loc' | 'dat' | 'tbl'
        self.imm_ptr = set()    # instructions whose 16-bit operand is a ROM address
        self.unresolved = []    # (pc, text) of jp (hl) not covered by a table hint
        self.bad = []           # entries that ran into undecodable bytes
        # the program ends where the zero fill starts ($00 up to $F7FF, then $FF)
        self.end = max(i for i, b in enumerate(rom[:SIZE]) if b not in (0x00, 0xFF)) + 1
        self.resolved = set()
        self.numbers = set()   # instructions whose ROM-range operand is a number
        self.items = {}        # typed data: address -> (size, directive, values, comment)

    def run(self, hints):
        work = [(v, 'sub') for v in VECTORS]
        tables = set()
        for h in hints:
            k, a = h[0], int(h[1], 16)
            if k == 'entry':
                work.append((a, 'sub'))
            elif k == 'jptable':
                n = int(h[2])
                self.labels[a] = 'tbl'
                for i in range(n):
                    work.append((a + 3 * i, 'loc'))
                tables.add(a)
            elif k == 'wtable':
                n = int(h[2])
                kind = h[3] if len(h) > 3 else 'code'
                self.data[a] = (2 * n, 2, 'words')
                self.labels[a] = 'tbl'
                for i in range(n):
                    t = self.rom[a + 2 * i] | (self.rom[a + 2 * i + 1] << 8)
                    if kind == 'code':
                        work.append((t, 'loc'))
                    else:
                        self.labels.setdefault(t, 'dat')
            elif k in ('data', 'text'):
                width = int(h[3]) if len(h) > 3 else 16
                self.data[a] = (int(h[2], 16), width, 'text' if k == 'text' else 'bytes')
                self.labels.setdefault(a, 'dat')
            elif k == 'imm':
                self.imm_ptr.add(a)
            elif k == 'jpind':
                self.resolved.add(a)
            elif k == 'number':
                self.numbers.add(a)
            elif k == 'song':
                sm1_data.song(self.rom, a, self.items, self.labels)
            elif k == 'effect':
                sm1_data.effect(self.rom, a, self.items, self.labels)
            elif k == 'records':
                n, size = int(h[2]), int(h[3])
                width = int(h[4]) if len(h) > 4 else size
                sm1_data.records(self.rom, a, n, size, width, self.items, self.labels,
                                 ' '.join(h[5:]) or None)
            elif k == 'words':
                sm1_data.words(self.rom, a, int(h[2]), self.items, self.labels,
                               comment=' '.join(h[3:]) or None)
        self.tables = tables
        self.item_bytes = {i for s, it in self.items.items() for i in range(s, s + it[0])}
        while work:
            pc, kind = work.pop()
            if pc in self.code:
                if kind == 'sub' or self.labels.get(pc) is None:
                    self.labels[pc] = kind if self.labels.get(pc) != 'sub' else 'sub'
                continue
            self.labels[pc] = 'sub' if kind == 'sub' or self.labels.get(pc) == 'sub' else self.labels.get(pc, kind)
            while True:
                if pc in self.code:
                    break
                if pc in self.owner or pc in self.item_bytes or any(s <= pc < s + d[0] for s, d in self.data.items()):
                    self.bad.append((pc, 'runs into another instruction or data'))
                    break
                ins = decode(self.rom, pc)
                if ins is None:
                    self.bad.append((pc, 'undecodable'))
                    break
                self.code[pc] = ins
                for i in range(ins.size):
                    self.owner[pc + i] = pc
                if ins.target is not None and ins.kind in ('jp', 'jr', 'call', 'rst') and ins.target < self.end:
                    work.append((ins.target, 'sub' if ins.kind in ('call', 'rst') else 'loc'))
                for kind_, v in ins.refs:
                    if kind_ == 'mem' and v < self.end:
                        self.labels.setdefault(v, 'dat')
                if (ins.text.startswith(('ld hl,{N}', 'ld ix,{N}', 'ld iy,{N}')) and ins.refs
                        and 0x100 <= ins.refs[0][1] < self.end and pc not in self.numbers):
                    self.imm_ptr.add(pc)     # hl/ix/iy loaded with a ROM address: a pointer
                if pc in self.imm_ptr:
                    v = ins.refs[0][1]
                    self.labels.setdefault(v, 'dat')
                if ins.kind == 'jpind' and pc not in self.resolved:
                    self.unresolved.append(pc)
                if ins.kind in ('jp', 'jr', 'ret', 'jpind') and not ins.cond:
                    break
                pc += ins.size
        for t in tables:
            # a jump table is code, but keep its label kind
            self.labels[t] = 'tbl'


def label_name(names, labels, a):
    if a in names:
        return names[a][0]
    kind = labels.get(a)
    if kind is None:
        return None
    return f'{kind}_{a:04X}'


def h16(v):
    return f'0{v:04x}h'


def gen_source(rom, out):
    names, port_names = load_names()
    t = Trace(rom)
    t.run(load_hints())
    # every name in names.csv inside the ROM is a label too
    for a in names:
        if a < t.end:
            t.labels.setdefault(a, 'dat')
    lines = ['; sm1.sm1 - board Z80 sound program (64 KB, the ROM holds it twice)',
             '; generated by tools/sm1.py from sm1/names.csv and sm1/hints.txt - edit those',
             '; assemble: z80asm (tools/sm1.py build)', '']
    # RAM, ports and constants
    lines.append('; I/O ports')
    for a, (n, tag, note) in sorted(port_names.items()):
        lines.append(f'{n}:\tequ 0{a:02x}h\t; [{tag}] {note}'.rstrip())
    lines += ['', '; work RAM ($F800-$FFFF)']
    for a, (n, tag, note) in sorted(names.items()):
        if a >= t.end:
            lines.append(f'{n}:\tequ {h16(a)}\t; [{tag}] {note}'.rstrip())
    lines.append('')
    lines.append('\torg 00000h')
    ram = {a: n for a, (n, *_ ) in names.items() if a >= t.end}
    ports = {a: n for a, (n, *_ ) in port_names.items()}

    def operand(v, ins, kind):
        if kind == 'mem' and v in ram:
            return ram[v]
        if kind in ('addr',) or (kind == 'mem' and v < t.end) or (kind == 'imm' and ins.pc in t.imm_ptr):
            n = label_name(names, t.labels, v)
            if n:
                return n
        if kind == 'imm' and v in ram:
            return ram[v]
        return h16(v)

    pc = 0
    counts = {'code': 0, 'data': 0, 'pad': 0}
    while pc < SIZE:
        n = label_name(names, t.labels, pc)
        if n and pc < t.end:
            if pc in names and names[pc][2]:
                lines.append(f'; {n} [{names[pc][1]}] {names[pc][2]}')
            lines.append(f'{n}:')
        if pc in t.code:
            ins = t.code[pc]
            text = ins.text
            if '{T}' in text:
                text = text.replace('{T}', operand(ins.target, ins, 'addr'))
            if '{N}' in text:
                k, v = ins.refs[0]
                text = text.replace('{N}', operand(v, ins, k))
            if ins.text.startswith(('out (', 'in a,(')):
                p = rom[pc + 1]
                if p in ports:
                    text = text.replace(f'(0{p:02x}h)', f'({ports[p]})')
            lines.append(f'\t{text}\t; {pc:04X}')
            counts['code'] += ins.size
            pc += ins.size
            continue
        if pc in t.items:
            size, directive, values, comment = t.items[pc]
            if directive == 'defw':
                vals = ['0' if v == 0 else (label_name(names, t.labels, v) or h16(v)) for v in values]
            else:
                vals = [f'0{v:02x}h' for v in values]
            lines.append(f'\t{directive} ' + ','.join(vals) + f'\t; {pc:04X}' + (f' {comment}' if comment else ''))
            counts['data'] += size
            pc += size
            continue
        if pc >= t.end:
            while pc < SIZE:
                v = rom[pc]
                stop = pc
                while stop < SIZE and rom[stop] == v:
                    stop += 1
                lines.append(f'\tdefs {h16(stop - pc)},0{v:02x}h\t; {pc:04X} fill')
                counts['pad'] += stop - pc
                pc = stop
            break
        # data up to the next code byte or label
        stop = pc + 1
        while stop < t.end and stop not in t.code and stop not in t.items and label_name(names, t.labels, stop) is None:
            stop += 1
        d = t.data.get(pc)
        width = d[1] if d else 16
        if d and d[2] == 'words':
            for i in range(pc, min(stop, pc + d[0]) - 1, 2):
                v = rom[i] | (rom[i + 1] << 8)
                ln = label_name(names, t.labels, v)
                lines.append(f'\tdefw {ln or h16(v)}\t; {i:04X}')
            done = min(stop, pc + d[0]) & ~0 if (min(stop, pc + d[0]) - pc) % 2 == 0 else min(stop, pc + d[0]) - 1
            counts['data'] += done - pc
            pc = done
            continue
        i = pc
        while i < stop:
            run = i
            while run < stop and rom[run] == rom[i]:
                run += 1
            if run - i >= 16:
                lines.append(f'\tdefs {h16(run - i)},0{rom[i]:02x}h\t; {i:04X}')
                i = run
                continue
            chunk = rom[i:min(stop, i + width)]
            lines.append('\tdefb ' + ','.join(f'0{b:02x}h' for b in chunk) + f'\t; {i:04X}')
            i += len(chunk)
        counts['data'] += stop - pc
        pc = stop
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        f.write('\n'.join(lines) + '\n')
    return t, counts


def build(asm, out):
    tmp = out + '.64k'
    r = subprocess.run(['z80asm', '-i', asm, '-o', tmp], capture_output=True, text=True)
    if r.returncode or r.stderr.strip():
        sys.stderr.write(r.stderr)
        raise SystemExit(1)
    data = open(tmp, 'rb').read()
    os.remove(tmp)
    if len(data) != SIZE:
        raise SystemExit(f'assembled {len(data)} bytes, expected {SIZE}')
    open(out, 'wb').write(data * 2)


def main(argv):
    if len(argv) == 3 and argv[1] in ('source', 'stats'):
        rom = open(argv[2], 'rb').read()[:SIZE]
        out = os.path.join(SM1, 'src', 'sm1.asm') if argv[1] == 'source' else os.devnull
        t, c = gen_source(rom, out)
        print(f'code {c["code"]} bytes ({len(t.code)} instructions), data {c["data"]}, padding {c["pad"]}')
        for pc in t.unresolved:
            print(f'unresolved jp (hl/ix/iy) at {pc:04X}')
        for pc, why in t.bad:
            print(f'stopped at {pc:04X}: {why}')
        return 0
    if len(argv) == 4 and argv[1] == 'build':
        build(argv[2], argv[3])
        return 0
    if len(argv) == 4 and argv[1] == 'check':
        sha1 = hashlib.sha1(open(argv[2], 'rb').read()).hexdigest()
        ok = sha1 == argv[3].lower()
        print(f'{"OK  " if ok else "FAIL"}  sha1 {sha1}  {argv[2]}')
        return 0 if ok else 1
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
