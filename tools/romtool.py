#!/usr/bin/env python3
"""Small helpers for Neo Geo system ROM images.

  romtool.py swap     <in> <out>          swap bytes of every 16-bit word
  romtool.py check    <rom.sp1> <sha1>    compare the SHA-1 of a MAME-order image
  romtool.py checksum <rom.sp1> [--fix]   verify (or rewrite) the boot checksum

Images on disk are in MAME order (word-swapped). The 68000 sees them
big-endian; `swap` converts in both directions.

Checksum (as checked at boot, NeoGeoDev wiki "Boot process"): low byte of the
sum of the 128 bytes $C00000-$C0007F and of every byte $C00082-$C1FFFF must
equal the byte at $C00080. In SP-S2 the byte at $C00081 holds the same value;
--fix writes both.
"""
import hashlib
import sys


def swap(b):
    return bytes(b[i ^ 1] for i in range(len(b)))


def checksum(native):
    return (sum(native[:0x80]) + sum(native[0x82:])) & 0xFF


def main():
    cmd = sys.argv[1]
    if cmd == 'swap':
        open(sys.argv[3], 'wb').write(swap(open(sys.argv[2], 'rb').read()))
    elif cmd == 'check':
        h = hashlib.sha1(open(sys.argv[2], 'rb').read()).hexdigest()
        if h != sys.argv[3]:
            sys.exit(f'FAIL  sha1 {h} (expected {sys.argv[3]})')
        print(f'OK    sha1 {h}')
    elif cmd == 'checksum':
        path = sys.argv[2]
        native = bytearray(swap(open(path, 'rb').read()))
        want = checksum(native)
        print(f'stored ${native[0x80]:02X} ${native[0x81]:02X}, computed ${want:02X}')
        if '--fix' in sys.argv:
            native[0x80] = native[0x81] = want
            open(path, 'wb').write(swap(bytes(native)))
            print('rewritten')
        elif native[0x80] != want:
            sys.exit(1)
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
