#!/usr/bin/env python3
"""Relocation test: build a modified BIOS where the main code has moved.

Usage: relocation_test.py <out_dir>

Copies src/ to <out_dir>, then
  1. inserts two NOPs at the start of Reset: everything from $C11002 moves by 4 bytes,
  2. adds CustomMenuLine (+ its MESS_OUT text) in the free block at $C04300,
  3. calls it from TestMenu: the code after that call moves by 6 more bytes,
assembles, swaps to MAME order and fixes the boot checksum. The result,
<out_dir>/sp-s2.sp1, should boot games and show "CUSTOM BIOS BUILD" under the
test mode menu. The .org lines keep every block after a free area in place.
"""
import os
import shutil
import subprocess
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for f in os.listdir(os.path.join(R, 'src')):
    shutil.copy(os.path.join(R, 'src', f), out)
files = {f: open(os.path.join(out, f)).read() for f in os.listdir(out) if f.endswith('.s')}


def edit(old, new):
    hits = [f for f, txt in files.items() if old in txt]
    assert len(hits) == 1 and files[hits[0]].count(old) == 1, old
    files[hits[0]] = files[hits[0]].replace(old, new)


edit('Reset:\n', 'Reset:\n\tnop\n\tnop\n')
edit('\t.org\t0x11000,0xFF', '''CustomMenuLine:                         | added: one MESS_OUT line under the menu
\taddq.b\t#0x1,(BIOS_MESS_BUSY-A5_BASE,a5)
\tmovea.l\t(BIOS_MESS_POINT-A5_BASE,a5),a0
\tmove.l\t#CustomText,(a0)+
\tmove.l\ta0,(BIOS_MESS_POINT-A5_BASE,a5)
\tsubq.b\t#0x1,(BIOS_MESS_BUSY-A5_BASE,a5)
\trts
CustomText:                             | command 3: VRAM address, then text up to $FF
\tdc.b\t0x00,0x03,0x71,0x5C,0x01,0x08
\t.ascii\t"CUSTOM BIOS BUILD"
\tdc.b\t0xFF,0x00,0x00
\t.even
\t.org\t0x11000,0xFF''')
edit('TestMenu:\n\tjsr\t(sub_C13A3C,pc)\t| C19072\n',
     'TestMenu:\n\tjsr\t(sub_C13A3C,pc)\t| C19072\n\tjsr\t(CustomMenuLine).l\n')
for f, txt in files.items():
    open(os.path.join(out, f), 'w').write(txt)

obj, binf, rom = (os.path.join(out, n) for n in ('sp-s2.o', 'sp-s2.bin', 'sp-s2.sp1'))
subprocess.run(['m68k-linux-gnu-as', '-m68000', '--register-prefix-optional', '-I', out,
                '-o', obj, os.path.join(out, 'sp-s2.s')], check=True)
subprocess.run(['m68k-linux-gnu-ld', '-Ttext=0xC00000', '-e', '0xC00402', '--oformat', 'binary',
                '-o', binf, obj], check=True)
tool = os.path.join(R, 'tools', 'romtool.py')
subprocess.run([sys.executable, tool, 'swap', binf, rom], check=True)
subprocess.run([sys.executable, tool, 'checksum', rom, '--fix'], check=True)
orig = open(os.path.join(R, 'roms', 'sp-s2.sp1'), 'rb').read() if os.path.exists(
    os.path.join(R, 'roms', 'sp-s2.sp1')) else None
new = open(rom, 'rb').read()
print(f'{rom}: {len(new)} bytes' + (f', {sum(a != b for a, b in zip(orig, new))} bytes differ from SP-S2'
                                     if orig else ''))
