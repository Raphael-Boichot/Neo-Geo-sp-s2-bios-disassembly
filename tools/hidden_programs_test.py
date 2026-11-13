#!/usr/bin/env python3
"""Build a test BIOS that reaches the two unreferenced programs of SP-S2.

Usage: hidden_programs_test.py <out_dir>

In TestMenuJumpTable, menu item 5 (CODE NUMBER) is pointed at ControllerTest
and item 7 (EXIT) at CardUtility. The result, <out_dir>/sp-s2.sp1 (checksum
fixed), is for MAME only: it shows that both programs still work.
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
path = os.path.join(out, 'test_mode.s')
src = open(path).read()
for old, new in (('\tdc.l\tTestCodeNumber\n', '\tdc.l\tControllerTest\n'),
                 ('\tdc.l\tTestMenuExit\n', '\tdc.l\tCardUtility\n')):
    assert src.count(old) == 1, old
    src = src.replace(old, new)
open(path, 'w').write(src)

obj, binf, rom = (os.path.join(out, n) for n in ('sp-s2.o', 'sp-s2.bin', 'sp-s2.sp1'))
subprocess.run(['m68k-linux-gnu-as', '-m68000', '--register-prefix-optional', '-I', out,
                '-o', obj, os.path.join(out, 'sp-s2.s')], check=True)
subprocess.run(['m68k-linux-gnu-ld', '-Ttext=0xC00000', '-e', '0xC00402', '--oformat', 'binary',
                '-o', binf, obj], check=True)
tool = os.path.join(R, 'tools', 'romtool.py')
subprocess.run([sys.executable, tool, 'swap', binf, rom], check=True)
subprocess.run([sys.executable, tool, 'checksum', rom, '--fix'], check=True)
print(rom)
