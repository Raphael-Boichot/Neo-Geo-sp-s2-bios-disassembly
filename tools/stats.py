#!/usr/bin/env python3
"""Measured counts behind the disassembly levels (README table).

Usage: stats.py <rom.sp1> [src_dir]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_source as G  # noqa: E402
import trace as T       # noqa: E402

rom = G.swap(open(sys.argv[1], 'rb').read())
SRC_DIR = sys.argv[2] if len(sys.argv) > 2 else 'src'
src = '\n'.join(open(os.path.join(SRC_DIR, f)).read() for f in sorted(os.listdir(SRC_DIR)) if f.endswith('.s'))
t = T.trace(rom, T.load_hints('tools/hints.txt'))
kinds, _ = T.summary(rom, t)

print('L1 bytes: code %d, data %d, free %d' % tuple(kinds.count(k) for k in 'CDF'))
print(f'   instructions {len(t.insn)}, code-pointer tables {len(t.tables)}, '
      f'speculative entries {len(t.speculative)}, conflicts {len(t.conflicts)}')
print('   speculative: ' + ' '.join(f'{a:06X}' for a, _ in t.speculative))

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

code = [ln.split('|')[0] for ln in src.split('\n') if ln.startswith('\t') and not ln.startswith(('\tdc', '\t.'))]
raw_ram = [ln for ln in code if re.search(r'0x(10|D0)[0-9A-F]{4}\b', ln)]
raw_a5 = [ln for ln in code if re.search(r'0x[0-9A-F]+\(a5', ln)]
raw_a4 = [ln for ln in code if re.search(r'-0x[0-9A-F]+\(a4', ln)]
raw_io = [ln for ln in code if re.search(r'\(0x3[0-9A-F]{5}\)\.l', ln)]
raw_w = [ln for ln in code if re.search(r'\(0x[0-9A-F]{4}\)\.w', ln)]
inc = open(os.path.join(SRC_DIR, 'ram.inc')).read()
ram_names = re.findall(r'\.equ\t(\w+),0x', inc)
auto_ram = [n for n in ram_names if re.match(r'b?ram_[0-9A-F]{6}$', n)]
print(f'L4 RAM addresses used {len(ram_names)}: named {len(ram_names) - len(auto_ram)}, automatic {len(auto_ram)}; '
      f'raw RAM operands left {len(raw_ram)}, raw x(a5) {len(raw_a5)}, backup RAM through a4 left {len(raw_a4)}, unnamed I/O {len(raw_io)}, absolute short {len(raw_w)}')
print(f'L5 numeric ROM addresses left in operands: '
      f'{len(re.findall(r"0x00?C[01][0-9A-F]{4}", chr(10).join(code)))}')
