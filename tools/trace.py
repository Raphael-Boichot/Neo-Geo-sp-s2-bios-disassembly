#!/usr/bin/env python3
"""Recursive-descent code tracer for a Neo Geo 128 KiB system ROM.

Usage: trace.py <rom_swapped.bin> [hints.txt]

Marks every byte as CODE (part of a traced instruction), FREE (long $FF fill)
or DATA (everything else) and prints a region summary.  Used as a library by
gen_source.py.
"""
import re
import struct
import sys

import capstone as cs
from capstone import m68k as m

BASE = 0xC00000
SIZE = 0x20000

COND_BRANCH = re.compile(r'^b(hi|ls|cc|hs|cs|lo|ne|eq|vc|vs|pl|mi|ge|lt|gt|le)(\.[sbw])?$')
DBCC = re.compile(r'^db(t|f|ra|hi|ls|cc|hs|cs|lo|ne|eq|vc|vs|pl|mi|ge|lt|gt|le)$')
STOPPERS = {'rts', 'rte', 'rtr', 'illegal', 'jmp'}
ABS_RE = re.compile(r'\$([0-9a-f]+)\.([lw])')
PCREL_RE = re.compile(r'\$([0-9a-f]+)\(pc')


def in_rom(a):
    return BASE <= a < BASE + SIZE


class Tracer:
    def __init__(self, rom, hints=None):
        self.rom = rom
        self.md = cs.Cs(cs.CS_ARCH_M68K, cs.CS_MODE_M68K_000 | cs.CS_MODE_BIG_ENDIAN)
        self.md.detail = True
        self.insn = {}            # addr -> capstone insn
        self.owner = [None] * SIZE  # byte offset -> insn start addr
        self.refs = {}            # target addr -> set of (from, kind)
        self.tables = {}          # table addr -> (entry_size, count, kind)
        self.queue = []
        self.conflicts = []
        self.hints = hints or {}
        self.speculative = []

    # ---------------------------------------------------------------
    def decode(self, addr):
        off = addr - BASE
        for ins in self.md.disasm(self.rom[off:off + 10], addr, 1):
            return ins if ins.id != 0 else None   # id 0 = undecodable word
        return None

    def add_ref(self, target, src, kind):
        self.refs.setdefault(target, set()).add((src, kind))

    def push(self, addr, src=None, kind='code'):
        if src is not None:
            self.add_ref(addr, src, kind)
        if in_rom(addr) and addr % 2 == 0:
            self.queue.append(addr)

    @staticmethod
    def branch_target(ins):
        op = ins.operands[-1]
        if op.type == m.M68K_OP_BR_DISP:
            return ins.address + 2 + op.br_disp.disp
        return None

    @staticmethod
    def ea_target(ins):
        """Absolute or PC-relative address mentioned in the operand string."""
        mm = PCREL_RE.search(ins.op_str)
        if mm:
            return int(mm.group(1), 16), 'pc'
        mm = ABS_RE.search(ins.op_str)
        if mm:
            v = int(mm.group(1), 16)
            if mm.group(2) == 'w' and v >= 0x8000:
                v |= 0xFF0000  # sign-extended absolute short
            return v, 'abs'
        return None, None

    # ---------------------------------------------------------------
    def run(self):
        while self.queue:
            addr = self.queue.pop()
            prev = None
            while True:
                if not in_rom(addr):
                    break
                if addr in self.insn:
                    break
                off = addr - BASE
                if self.owner[off] is not None:
                    self.conflicts.append(addr)
                    break
                ins = self.decode(addr)
                if ins is None:
                    self.conflicts.append(addr)
                    break
                # refuse to overlap already-traced code
                if any(self.owner[off + k] is not None for k in range(ins.size)):
                    self.conflicts.append(addr)
                    break
                self.insn[addr] = ins
                for k in range(ins.size):
                    self.owner[off + k] = addr
                mn = ins.mnemonic
                nxt = addr + ins.size

                # references held in operands (lea/pea/move #imm etc.)
                t, kind = self.ea_target(ins)
                if t is not None and in_rom(t):
                    if mn.startswith('pea') and kind == 'pc':
                        self.push(t, addr, 'code')   # pushed return address, reached by rts
                    else:
                        self.add_ref(t, addr, 'data')
                for mm in re.finditer(r'#\$([0-9a-f]+)', ins.op_str):
                    v = int(mm.group(1), 16)
                    if in_rom(v) and v % 2 == 0 and mn.endswith('.l'):
                        self.add_ref(v, addr, 'imm')

                if mn in ('bra', 'bra.s', 'bra.b', 'bra.w'):
                    self.push(self.branch_target(ins), addr, 'code')
                    break
                if mn.startswith('bsr') or COND_BRANCH.match(mn) or DBCC.match(mn):
                    self.push(self.branch_target(ins), addr, 'code')
                elif mn in ('jsr', 'jmp'):
                    t, kind = self.ea_target(ins)
                    if t is not None and '(pc,' not in ins.op_str.replace(' ', '') \
                            and ',' not in ins.op_str:
                        self.push(t, addr, 'code')
                    else:
                        self.indirect_jump(ins, prev)
                if mn in STOPPERS:
                    break
                if addr in self.hints.get('noreturn', ()):
                    break
                prev = ins
                addr = nxt

    # ---------------------------------------------------------------
    def indirect_jump(self, ins, prev):
        """Recognise `movea.l tbl(pc,dN.w),aN ; jmp (aN)` style dispatch."""
        if prev is None:
            return
        mm = re.match(r'\$([0-9a-f]+)\(pc, d\d\.w\), a\d', prev.op_str)
        if prev.mnemonic in ('movea.l', 'move.l') and mm:
            self.long_table(int(mm.group(1), 16), prev.address)

    def long_table(self, tbl, src):
        n = 0
        a = tbl
        while in_rom(a) and (a - BASE) + 4 <= SIZE:
            if n and a in self.refs and any(k != 'table' for _, k in self.refs[a]):
                break
            if self.owner[a - BASE] is not None:
                break
            v = struct.unpack('>I', self.rom[a - BASE:a - BASE + 4])[0]
            if not in_rom(v) or v % 2:
                break
            self.push(v, a, 'code')
            n += 1
            a += 4
        if n:
            self.tables[tbl] = (4, n, 'code_ptr')
            self.add_ref(tbl, src, 'table')


def free_mask(rom, minrun=32):
    free = [False] * len(rom)
    i = 0
    while i < len(rom):
        j = i
        while j < len(rom) and rom[j] == 0xFF:
            j += 1
        if j - i >= minrun:
            for k in range(i, j):
                free[k] = True
        i = max(j, i + 1)
    return free


def load_hints(path):
    hints = {'entry': [], 'noreturn': set(), 'longtable': []}
    if not path:
        return hints
    for line in open(path):
        line = line.split(';')[0].strip()
        if not line:
            continue
        parts = line.split()
        key, val = parts[0], int(parts[1].lstrip('$'), 16)
        if key == 'entry':
            hints['entry'].append(val)
        elif key == 'noreturn':
            hints['noreturn'].add(val)
        elif key == 'longtable':
            hints['longtable'].append(val)
    return hints


def trace(rom, hints):
    t = Tracer(rom, hints)
    # exception vectors
    vec = struct.unpack('>64I', rom[:256])
    for i, v in enumerate(vec[1:], 1):
        if in_rom(v):
            t.push(v, BASE + 4 * i, 'vector')
    # BIOS call jump table: consecutive JMP abs.l starting at $C00402
    a = 0x402
    while rom[a:a + 2] in (b'\x4e\xf9', b'\x4e\xfa', b'\x4e\x75'):
        t.push(BASE + a)
        a += 6
    for e in hints['entry']:
        t.push(e)
    t.run()
    for tbl in hints['longtable']:
        t.long_table(tbl, None)
    t.run()
    # speculative: code pointers stored as immediates (move.l #$C1xxxx,...)
    changed = True
    while changed:
        changed = False
        for tgt, srcs in sorted(t.refs.items()):
            if not any(k == 'imm' for _, k in srcs):
                continue
            if not in_rom(tgt) or tgt % 2 or t.owner[tgt - BASE] is not None:
                continue
            if speculative_ok(t, tgt):
                t.speculative.append((tgt, 'pointer'))
                t.push(tgt)
                t.run()
                changed = True
    # orphan code: untraced region that starts right after a code stopper
    changed = True
    while changed:
        changed = False
        for off in range(2, SIZE, 2):
            if t.owner[off] is not None or t.owner[off - 1] is None:
                continue
            last = t.insn[t.owner[off - 1]]
            if not (last.mnemonic in STOPPERS or last.mnemonic.startswith('bra')):
                continue
            a = BASE + off
            if speculative_ok(t, a, strict=True):
                t.speculative.append((a, 'orphan'))
                t.push(a)
                t.run()
                changed = True
    return t


TEXTY = re.compile(rb'[ -~]{6,}')


def speculative_ok(t, start, limit=400, strict=False):
    """Accept start as code if linear decoding reaches rts/rte/jmp/bra
    without invalid opcodes, overlaps or running into free space."""
    for src, kind in t.refs.get(start, ()):
        if kind == 'data' and src in t.insn and '(pc, d' in t.insn[src].op_str:
            return False      # indexed table read: data, not code
    a = start
    n = 0
    for _ in range(limit):
        off = a - BASE
        if not in_rom(a) or t.owner[off] is not None:
            return a in t.insn   # falls into known code at a boundary
        if t.rom[off:off + 4] == b'\xff\xff\xff\xff':
            return False
        ins = t.decode(a)
        if ins is None:
            return False
        w = t.rom[off:off + 2]
        if strict and (w in (b'\x00\x00', b'\xff\xff') or TEXTY.match(t.rom[off:off + 8])):
            return False
        n += 1
        if ins.mnemonic in STOPPERS or ins.mnemonic.startswith('bra'):
            return n >= 3 or not strict
        a += ins.size
    return False


def summary(rom, t):
    free = free_mask(rom)
    kinds = []
    for off in range(len(rom)):
        kinds.append('C' if t.owner[off] is not None else ('F' if free[off] else 'D'))
    runs = []
    s = 0
    for i in range(1, len(kinds) + 1):
        if i == len(kinds) or kinds[i] != kinds[s]:
            runs.append((s, i, kinds[s]))
            s = i
    return kinds, runs


if __name__ == '__main__':
    rom = open(sys.argv[1], 'rb').read()
    hints = load_hints(sys.argv[2] if len(sys.argv) > 2 else None)
    t = trace(rom, hints)
    kinds, runs = summary(rom, t)
    tot = {k: kinds.count(k) for k in 'CDF'}
    for a, why in t.speculative:
        print(f"  speculative ${a:06X} ({why})")
    print(f"code {tot['C']}  data {tot['D']}  free {tot['F']}  insns {len(t.insn)}  conflicts {len(t.conflicts)}")
    for s, e, k in runs:
        if k == 'D' and e - s >= 16:
            print(f"  DATA ${BASE + s:06X}-${BASE + e - 1:06X} {e - s:6d}")
