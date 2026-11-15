#!/usr/bin/env python3
"""Generate reassemblable 68000 source (GNU as, Motorola syntax) for a
Neo Geo system ROM and check that it rebuilds byte for byte.

Usage: gen_source.py <rom.sp1 (MAME word-swapped)> <out_dir> [hints.txt]

Writes <out_dir>/sp-s2.s and <out_dir>/neogeo.inc.  Any instruction that the
assembler would encode differently from the original (e.g. it silently picks
MOVEQ for MOVE.L #imm) is kept as raw words with the instruction in a comment.
"""
import os
import re
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import symbols as S  # noqa: E402
import trace as T    # noqa: E402

BASE, SIZE = T.BASE, T.SIZE
AS = ['m68k-linux-gnu-as', '-m68000', '--register-prefix-optional']
LD = ['m68k-linux-gnu-ld', '-Ttext=0xC00000', '-e', '0xC00402', '--oformat', 'binary']

COND = re.compile(r'^(b(hi|ls|cc|hs|cs|lo|ne|eq|vc|vs|pl|mi|ge|lt|gt|le|ra|sr)|db\w+)')
_TEXT_CAND = re.compile(rb'[ -!#-\[\]-~]{5,}')
_LETTERS = re.compile(rb'[A-Za-z ]')


class _TextRun:
    """Printable run that reads as text: at least 60 % letters or spaces and
    3 letters, so numeric tables in the $20-$7E range are not taken as text."""
    @staticmethod
    def _ok(m):
        g = m.group()
        letters = len(_LETTERS.findall(g))
        if any(all(g[i + k + 1] - g[i + k] == 1 for k in range(10)) for i in range(len(g) - 10)):
            return False                    # long counting run (ramp table), not text ("12345678" stays)
        return letters >= 0.6 * len(g) and sum(c.isalpha() for c in g.decode()) >= 3

    def match(self, b):
        m = _TEXT_CAND.match(b)
        return m if m and self._ok(m) else None

    def search(self, b):
        for m in _TEXT_CAND.finditer(b):
            if self._ok(m):
                return m
        return None


TEXT_RUN = _TextRun()


def swap(b):
    return bytes(b[i ^ 1] for i in range(len(b)))


A5_BASE = 0x10F300      # a5 always holds this in the BIOS (lea $10F300,a5)
A4_BASE = 0xD08000      # a4 holds this after lea $D08000,a4 (backup RAM), tracked per routine


def ram_kind(v):
    if 0x100000 <= v < 0x110000:
        return 'ram'
    if 0xD00000 <= v < 0xD10000:
        return 'bram'
    return None


class Gen:
    def __init__(self, rom, t):
        self.rom = rom
        self.t = t
        self.kinds, _ = T.summary(rom, t)
        self.labels = {}
        self.ptr_longs = set()     # data offsets holding a ROM pointer
        self.ram_used = {}         # RAM address -> name used in the source
        self.collect()
        self.a4_known = self.track_a4()

    def track_a4(self):
        """Instructions where a4 = A4_BASE: from `lea $D08000,a4` until a4 is
        written again or the flow ends. A routine entry starts with a4 known
        only when every call or jump to it comes from a known point."""
        seeds = set()
        while True:
            known, on = set(), False
            for a in sorted(self.t.insn):
                ins = self.t.insn[a]
                lab = self.labels.get(a, '')
                if lab:
                    srcs = [x for x, _ in self.t.refs.get(a, ()) if x in self.t.insn]
                    if lab.startswith('loc_') and on:
                        pass                       # fall-through into a local label
                    else:
                        on = a in seeds
                if on:
                    known.add(a)
                op = ins.op_str.replace(' ', '')
                writes_a4 = op.endswith(',a4') or (ins.mnemonic.startswith('movem') and op.startswith('(a7)+')
                                                   and 'a4' in op) or (ins.mnemonic.startswith('exg') and 'a4' in op)
                if writes_a4:
                    on = ins.mnemonic.startswith('lea') and '$d08000.l' in op
                if ins.mnemonic in ('rts', 'rte', 'rtr', 'jmp') or ins.mnemonic.startswith('bra'):
                    on = False
            new = set()
            for a in self.labels:
                srcs = [x for x, k in self.t.refs.get(a, ()) if x in self.t.insn and k == 'code']
                refs = self.t.refs.get(a, set())
                # a jsr/jmp (label,pc) is also recorded as a data reference: ignore that one
                others = [x for x, k in refs if k != 'code' and (x, 'code') not in refs]
                if srcs and not others and all(x in known for x in srcs):
                    new.add(a)
            if new <= seeds:
                return known
            seeds |= new

    # ------------------------------------------------------------ labels
    def want(self, addr, kind):
        if not T.in_rom(addr):
            return
        off = addr - BASE
        own = self.t.owner[off]
        if own is not None and own != addr:
            addr, kind = own, 'code'          # mid-instruction: label owner
        if addr in self.labels:
            return
        if addr in S.BIOS_CALLS:
            name = S.BIOS_CALLS[addr]
        elif own is not None:
            name = ('sub_' if kind == 'call' else 'loc_') + f'{addr:06X}'
        elif kind == 'table':
            name = f'tbl_{addr:06X}'
        else:
            name = f'dat_{addr:06X}'
        self.labels[addr] = name

    def collect(self):
        t = self.t
        for a in S.BIOS_CALLS:
            self.want(a, 'code')
        vec = struct.unpack('>32I', self.rom[:0x80])
        for v in vec[1:]:
            self.want(v, 'code')
        for a, ins in t.insn.items():
            mn = ins.mnemonic
            if ins.operands and ins.operands[-1].type == T.m.M68K_OP_BR_DISP:
                self.want(t.branch_target(ins), 'call' if mn.startswith('bsr') else 'code')
            v, kind = t.ea_target(ins)
            if v is not None and T.in_rom(v):
                self.want(v, 'call' if mn == 'jsr' else
                          ('table' if '(pc, d' in ins.op_str else 'data'))
            for mm in re.finditer(r'#\$([0-9a-f]+)', ins.op_str):
                v = int(mm.group(1), 16)
                if mn.endswith('.l') and T.in_rom(v) and v in t.refs:
                    self.want(v, 'code' if t.owner[v - BASE] is not None else 'data')
        for tbl, (_, n, _) in t.tables.items():
            self.want(tbl, 'table')
            for i in range(n):
                self.ptr_longs.add(tbl - BASE + 4 * i)
                self.want(struct.unpack('>I', self.rom[tbl - BASE + 4 * i:tbl - BASE + 4 * i + 4])[0], 'code')
        # pointer-looking longs inside data ($00C0xxxx / $00C1xxxx, even)
        for off in range(0x100, SIZE - 3, 2):
            if any(self.kinds[off + k] != 'D' for k in range(4)) or off in self.ptr_longs or \
                    off + BASE in t.hints.get('number', ()):
                continue
            v = struct.unpack('>I', self.rom[off:off + 4])[0]
            if T.in_rom(v) and self.kinds[v - BASE] != 'F' and \
                    (v % 2 == 0 or self.kinds[v - BASE] == 'D') and \
                    (off - 2) not in self.ptr_longs:
                self.ptr_longs.add(off)
                self.want(v, 'data')

    def ram(self, v):
        name = S.RAM.get(v) or f'{ram_kind(v)}_{v:06X}'
        self.ram_used[v] = name
        return name

    def ref(self, addr):
        """Symbolic expression for a ROM address."""
        if addr in self.labels:
            return self.labels[addr]
        off = addr - BASE
        own = self.t.owner[off] if 0 <= off < SIZE else None
        if own is not None and own in self.labels:
            return f'{self.labels[own]}+{addr - own}'
        return f'0x{addr:06X}'

    # ------------------------------------------------------- instructions
    def conv(self, ins):
        mn, op = ins.mnemonic, ins.op_str
        t = self.t
        if ins.operands and ins.operands[-1].type == T.m.M68K_OP_BR_DISP:
            tgt = t.branch_target(ins)
            op = re.sub(r'\$[0-9a-f]+$', self.ref(tgt), op)

        def pcrel(mm):
            idx = mm.group(2)
            return f'({self.ref(int(mm.group(1), 16))},pc' + (f',{idx})' if idx else ')')
        op = re.sub(r'\$([0-9a-f]+)\(pc(?:, ([ad][0-7]\.[wl]))?\)', pcrel, op)

        def absol(mm):
            v = int(mm.group(1), 16)
            if mm.group(2) == 'w':
                if (v & 0xFFFF) in S.CART:
                    return f'({S.CART[v & 0xFFFF]}).w'
                return f'(0x{v & 0xFFFF:04X}).w'
            if T.in_rom(v):
                return f'({self.ref(v)}).l'
            if v in S.REGISTERS:
                return f'({S.REGISTERS[v]}).l'
            if ram_kind(v):
                return f'({self.ram(v)}).l'
            return f'(0x{v:06X}).l'
        op = re.sub(r'\$([0-9a-f]+)\.([lw])', absol, op)

        def imm(mm):
            neg, v = mm.group(1), int(mm.group(2), 16)
            if not neg and mn.endswith('.l') and T.in_rom(v) and v in t.refs:
                return '#' + self.ref(v)
            if not neg and mn.endswith('.l') and ram_kind(v) and (v != 0x100000 or v in S.RAM) and v != 0xD00000:
                return '#' + self.ram(v)
            return f'#{neg}0x{v:X}'
        op = re.sub(r'#(-?)\$([0-9a-f]+)', imm, op)
        op = re.sub(r'(-?)\$([0-9a-f]+)(?=\()', lambda mm: f'{mm.group(1)}0x{mm.group(2).upper()}', op)
        op = op.replace('$', '0x').replace(', ', ',')

        def a5rel(mm):                      # x(a5) -> (NAME-A5_BASE,a5)
            d = int(mm.group(2), 16) * (-1 if mm.group(1) else 1)
            return f'({self.ram(A5_BASE + d)}-A5_BASE,a5{mm.group(3) or ""})'
        op = re.sub(r'(-?)0x([0-9A-Fa-f]+)\(a5(,[ad][0-7]\.[wl])?\)', a5rel, op)

        def a4rel(mm):                      # x(a4) with a4 = $D08000 -> (NAME-A4_BASE,a4)
            d = int(mm.group(2), 16) * (-1 if mm.group(1) else 1)
            return f'({self.ram(A4_BASE + d)}-A4_BASE,a4{mm.group(3) or ""})'
        if ins.address in self.a4_known:
            op = re.sub(r'(-?)0x([0-9A-Fa-f]+)\(a4(,[ad][0-7]\.[wl])?\)', a4rel, op)
        if mn == 'moveq':                   # GNU wants the signed value
            mm = re.match(r'#0x([0-9A-F]+),', op)
            v = int(mm.group(1), 16)
            if v >= 0x80:
                op = f'#-0x{0x100 - v:X},' + op.split(',', 1)[1]
        if mn in ('abcd.b', 'sbcd.b', 'exg.l'):  # GNU has no size suffix here
            mn = mn[:-2]
        return f'{mn}\t{op}' if op else mn

    # ----------------------------------------------------------- emitting
    def data_lines(self, start, end):
        out = []
        off = start
        while off < end:
            if off in self.ptr_longs and off + 4 <= end:
                v = struct.unpack('>I', self.rom[off:off + 4])[0]
                out.append(f'\tdc.l\t{self.ref(v)}')
                off += 4
                continue
            if off < 0x80 and off % 4 == 0 and off + 4 <= end:
                v = struct.unpack('>I', self.rom[off:off + 4])[0]
                out.append(f'\tdc.l\t{self.ref(v) if T.in_rom(v) else f"0x{v:08X}"}')
                off += 4
                continue
            # next pointer long limits the byte run
            stop = end
            for p in range(off + 1, end):
                if p in self.ptr_longs:
                    stop = p
                    break
            chunk = self.rom[off:stop]
            in_table = any(a <= BASE + off <= b for a, b in S.TABLE_RANGES)
            mm = None if in_table else TEXT_RUN.match(chunk)
            if mm:
                out.append(f'\t.ascii\t"{mm.group().decode()}"')
                off += len(mm.group())
                continue
            # bytes up to the next text run (max 16 per line)
            mt = None if in_table else TEXT_RUN.search(chunk)
            n = min(16, mt.start() if mt else len(chunk), len(chunk))
            out.append('\tdc.b\t' + ','.join(f'0x{b:02X}' for b in chunk[:n]))
            off += n
        return out

    def generate(self, fallback):
        L = ['| Neo Geo system ROM disassembly – generated by tools/gen_source.py',
             '| Assemble with GNU as (m68k), Motorola syntax: see Makefile and HOWTO.md',
             '',
             '\t.include\t"neogeo.inc"',
             '\t.include\t"ram.inc"',
             '\t.text',
             '']
        off = 0
        kinds = self.kinds
        bounds = {a - BASE: (f, d) for a, f, d in S.MODULES}
        while off < SIZE:
            addr = BASE + off
            if off in bounds:
                L.append(f'|@@MODULE {bounds[off][0]}|{bounds[off][1]}')
            if addr in self.labels:
                if addr in S.ROM_NAMES and addr in S.NOTES:
                    tag, note = S.NOTES[addr]
                    L.append(f'| {S.ROM_NAMES[addr]} [{tag}] {note}')
                L.append(f'{self.labels[addr]}:')
            if kinds[off] == 'C':
                ins = self.t.insn[addr]
                if addr in fallback:
                    words = ','.join(f'0x{ins.bytes[i]:02X}{ins.bytes[i + 1]:02X}'
                                     for i in range(0, ins.size, 2))
                    L.append(f'\tdc.w\t{words}\t| {addr:06X}: {ins.mnemonic} {ins.op_str}')
                else:
                    L.append(f'\t{self.conv(ins)}\t| {addr:06X}')
                off += ins.size
                continue
            # data or free run until a kind change / label / code
            end = off + 1
            while end < SIZE and kinds[end] == kinds[off] and BASE + end not in self.labels \
                    and end not in bounds:
                end += 1
            if kinds[off] == 'F':
                # .org pads to the next block's address: code added before a free
                # block uses it up, and overflowing into the next block is an error
                L.append(f'\t.org\t0x{end:05X},0xFF\t| {addr:06X}-{BASE + end - 1:06X} free ({end - off} bytes)')
            else:
                L.extend(self.data_lines(off, end))
            off = end
        return '\n'.join(L) + '\n'


def write_split(out_dir, text):
    """Write one file per module (markers from generate) and a main file
    that includes them in address order."""
    parts = text.split('\n|@@MODULE ')
    head, files = parts[0], []
    for part in parts[1:]:
        first, body = part.split('\n', 1)
        name, desc = first.split('|', 1)
        files.append(name)
        with open(os.path.join(out_dir, name), 'w') as f:
            f.write(f'| {name}: {desc}\n| generated by tools/gen_source.py from symbols/ - edit names there\n\n'
                    + body.rstrip('\n') + '\n')
    with open(os.path.join(out_dir, 'sp-s2.s'), 'w') as f:
        f.write(head.rstrip('\n') + '\n\n')
        for name in files:
            f.write(f'\t.include\t"{name}"\n')


def write_inc(path):
    with open(path, 'w') as f:
        f.write('| Neo Geo hardware registers (symbols/registers.csv)\n\n')
        for v, n in sorted(S.REGISTERS.items()):
            f.write(f'\t.equ\t{n},0x{v:06X}\n')
        f.write('\n| Cartridge program header (symbols/cart_header.csv)\n\n')
        for v, n in sorted(S.CART.items()):
            f.write(f'\t.equ\t{n},0x{v:06X}\n')
        f.write(f'\n| BIOS work RAM base, held in a5 by the BIOS code\n\t.equ\tA5_BASE,0x{A5_BASE:06X}\n')
        f.write(f'| backup RAM base, held in a4 after lea $D08000,a4\n\t.equ\tA4_BASE,0x{A4_BASE:06X}\n')


def write_ram_inc(path, used):
    """Every RAM address the source uses: names from symbols/ram.csv, else
    ram_XXXXXX (work RAM) / bram_XXXXXX (backup RAM)."""
    with open(path, 'w') as f:
        f.write('| RAM used by the system ROM - generated; names come from symbols/ram.csv\n\n')
        for v in sorted(set(used) | set(S.RAM)):
            n = S.RAM.get(v) or used[v]
            f.write(f'\t.equ\t{n},0x{v:06X}\n')


LIST_RE = re.compile(r'^\s*\d+\s+([0-9a-f]{4,5})\s.*\|\s([0-9A-F]{6})(?::|\s*$)')


def assemble(src_dir, src_name, want_listing=False):
    with tempfile.TemporaryDirectory() as tmp:
        obj, out = os.path.join(tmp, 'o.o'), os.path.join(tmp, 'o.bin')
        lst = os.path.join(tmp, 'o.lst')
        extra = [f'-al={lst}'] if want_listing else []
        r = subprocess.run(AS + extra + ['-I', src_dir, '-o', obj, os.path.join(src_dir, src_name)],
                           capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr, None
        r = subprocess.run(LD + ['-o', out, obj], capture_output=True, text=True)
        if r.returncode:
            return None, r.stderr, None
        return open(out, 'rb').read(), '', (open(lst).read() if want_listing else None)


def size_culprits(listing):
    """Instructions whose encoded size differs from the original: the
    location counter drifts from the original address right after them."""
    bad = set()
    prev_addr, prev_delta = None, 0
    for line in listing.split('\n'):
        mm = LIST_RE.match(line)
        if not mm:
            continue
        loc, orig = int(mm.group(1), 16), int(mm.group(2), 16)
        delta = loc - (orig - BASE)
        if delta != prev_delta and prev_addr is not None:
            bad.add(prev_addr)
        prev_addr, prev_delta = orig, delta
    return bad


def main():
    rom = swap(open(sys.argv[1], 'rb').read())
    out_dir = sys.argv[2]
    hints = T.load_hints(sys.argv[3] if len(sys.argv) > 3 else None)
    os.makedirs(out_dir, exist_ok=True)
    write_inc(os.path.join(out_dir, 'neogeo.inc'))
    t = T.trace(rom, hints)
    g = Gen(rom, t)
    fallback = set()
    src_path = os.path.join(out_dir, 'sp-s2.s')
    for it in range(5000):
        open(src_path, 'w').write(g.generate(fallback))
        write_ram_inc(os.path.join(out_dir, 'ram.inc'), g.ram_used)
        img, err, lst = assemble(out_dir, 'sp-s2.s', want_listing=True)
        if img is None:
            # assembler rejected lines: fall back on every instruction it names
            bad = set()
            lines = open(src_path).read().split('\n')
            for mm in re.finditer(r':(\d+): Error', err):
                ln = lines[int(mm.group(1)) - 1]
                ma = re.search(r'\| ([0-9A-F]{6})$', ln)
                if ma:
                    bad.add(int(ma.group(1), 16))
            if not bad - fallback:
                sys.exit('assembler error not tied to an instruction:\n' + err[:2000])
            fallback |= bad
            continue
        if img == rom:
            break
        drift = size_culprits(lst) - fallback
        if drift:
            fallback |= drift
            continue
        n = min(len(img), len(rom))
        i = next((k for k in range(n) if img[k] != rom[k]), n)
        own = t.owner[i] if i < SIZE else None
        if own is None or own in fallback:
            sys.exit(f'mismatch at ${BASE + i:06X} not fixable by fallback (kind {g.kinds[i]})')
        fallback.add(own)
    else:
        sys.exit('did not converge')
    write_split(out_dir, g.generate(fallback))
    img, err, _ = assemble(out_dir, 'sp-s2.s')
    if img != rom:
        sys.exit('split source does not rebuild the ROM:\n' + err[:2000])
    print(f'identical rebuild: {len(t.insn)} instructions, {len(fallback)} kept as raw words, '
          f'{len(g.labels)} labels, {it + 1} passes')
    for a in sorted(fallback):
        ins = t.insn[a]
        print(f'  raw {a:06X}: {ins.mnemonic} {ins.op_str}')


if __name__ == '__main__':
    main()
