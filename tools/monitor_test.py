#!/usr/bin/env python3
"""Build a test BIOS that reaches the debug monitor left in SP-S2 (MAME only).

Usage: monitor_test.py <out_dir> [EXCEPTION]

In the release, every exception vector points to a BIOS call slot that does `jmp Reset`. This
build points those slots at the monitor entries of the matching exception instead, and points
test-menu item 4 (SETTING UP THE CODE NUMBER) at a stub in free space that raises EXCEPTION
(default illegal): illegal, address, privilege, trace, zerodiv; or checksum, which raises no
exception and calls the CHECKSUM_LOOP slot (nothing calls it in the release either); or cardfill,
which jumps to the unreferenced CardFillTest (saves until the memory card is full).
<out_dir>/sp-s2.sp1 has its checksum fixed.
"""
import os
import shutil
import subprocess
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
out = sys.argv[1]
exc = sys.argv[2] if len(sys.argv) > 2 else 'illegal'
os.makedirs(out, exist_ok=True)
for f in os.listdir(os.path.join(R, 'src')):
    shutil.copy(os.path.join(R, 'src', f), out)

# BIOS call slot used as exception vector -> monitor entry
SLOTS = {'loc_C00408': 'MonitorAddressError',      # bus error
         'loc_C0040E': 'MonitorAddressError',      # address error
         'loc_C00414': 'MonitorIllegal',           # illegal instruction
         'loc_C0041A': 'MonitorPrivilege',         # privilege violation
         'loc_C00420': 'MonitorTrace',             # trace
         'loc_C00426': 'MonitorUnassigned',        # zero divide, CHK, TRAPV, line A/F, traps
         'loc_C0042C': 'MonitorUninitialized',     # uninitialised interrupt
         'loc_C00432': 'MonitorSpurious'}          # spurious interrupt
STUBS = {'illegal': '\tillegal\n',
         'address': '\tmove.w\t(0x100001).l,d0\n',                    # word read at an odd address
         'privilege': '\tandi.w\t#0xDFFF,sr\n\tmove.w\t#0x2700,sr\n',   # leave supervisor mode, then a privileged instruction
         'trace': '\tori.w\t#0x8000,sr\n\tnop\n',
         'zerodiv': '\tmoveq\t#0,d1\n\tdivu.w\td1,d0\n',
         'checksum': '\tjsr\t(CHECKSUM_LOOP).l\n',
         'cardfill': '\tjmp\t(CardFillTest).l\n'}

path = os.path.join(out, 'header.s')
src = open(path).read()
for slot, entry in SLOTS.items():
    old = f'{slot}:\n\tjmp\t(Reset).l'
    assert src.count(old) == 1, old
    src = src.replace(old, f'{slot}:\n\tjmp\t({entry}).l')
open(path, 'w').write(src)

path = os.path.join(out, 'test_mode.s')
src = open(path).read()
old = '\tdc.l\tTestCodeNumber\n'
assert src.count(old) == 1
src = src.replace(old, '\tdc.l\tMonitorTestStub\n')
org = '\t.org\t0x1F000,0xFF'
assert src.count(org) == 1
src = src.replace(org, 'MonitorTestStub:\n' + STUBS[exc] + '\tbra.b\tMonitorTestStub\n' + org)
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
