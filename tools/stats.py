#!/usr/bin/env python3
"""Measured counts behind the disassembly levels (README table).

Usage: stats.py <rom.sp1> [src/sp-s2.s]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_source as G  # noqa: E402
import trace as T       # noqa: E402

rom = G.swap(open(sys.argv[1], 'rb').read())
src = open(sys.argv[2] if len(sys.argv) > 2 else 'src/sp-s2.s').read()
t = T.trace(rom, T.load_hints('tools/hints.txt'))
kinds, _ = T.summary(rom, t)

print('L1 bytes: code %d, data %d, free %d' % tuple(kinds.count(k) for k in 'CDF'))
print(f'   instructions {len(t.insn)}, code-pointer tables {len(t.tables)}, '
      f'speculative entries {len(t.speculative)}')

unres = []
for a, ins in sorted(t.insn.items()):
    if ins.mnemonic in ('jmp', 'jsr') and re.match(r'^\(a\d\)|^-?\$?[0-9a-f]*\(a\d', ins.op_str):
        loaders = {s for tb in t.tables for s, k in t.refs.get(tb, ()) if k == 'table'}
        if not any(a - d in loaders for d in range(2, 10, 2)):
            unres.append(a)
print(f'L2 indirect jmp/jsr through a register not resolved: {len(unres)}')
print('   ' + ' '.join(f'{a:06X}' for a in unres[:40]))

labels = re.findall(r'^(\w+):', src, re.M)
auto = [n for n in labels if re.match(r'(loc|sub|dat|tbl)_[0-9A-F]{6}$', n)]
print(f'L3 labels {len(labels)}: named {len(labels) - len(auto)}, automatic {len(auto)}')

code = [ln for ln in src.split('\n') if ln.startswith('\t') and not ln.startswith(('\tdc', '\t.'))]
raw_ram = [ln for ln in code if re.search(r'\(0x10[0-9A-F]{4}\)\.l', ln)]
raw_io = [ln for ln in code if re.search(r'\(0x(3[0-9A-F]|D0)[0-9A-F]{4}\)\.l', ln)]
raw_w = [ln for ln in code if re.search(r'\(0x[0-9A-F]{4}\)\.w', ln)]
print(f'L4 code lines with raw RAM $10xxxx: {len(raw_ram)}, raw I/O or backup RAM: {len(raw_io)}, '
      f'absolute short: {len(raw_w)}')
print(f'L5 numeric ROM addresses left in operands: '
      f'{len(re.findall(r"0x00?C[01][0-9A-F]{4}", chr(10).join(code)))}')
