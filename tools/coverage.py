#!/usr/bin/env python3
"""Compare MAME execution coverage with the static trace.

Usage: coverage.py <rom.sp1> coverage/*.txt

Each coverage file lists executed instruction addresses (one hex address per
line, from tools/mame_coverage.sh). Prints the executed share of the traced
code, the executed addresses the tracer missed, the check of every speculative
entry, and which scenarios run each BIOS call.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_source as G  # noqa: E402
import symbols as S     # noqa: E402
import trace as T       # noqa: E402


def load(path):
    out = set()
    for line in open(path):
        line = line.strip()
        if line:
            try:
                out.add(int(line, 16))
            except ValueError:
                pass
    return {a for a in out if T.in_rom(a)}


def main():
    rom = G.swap(open(sys.argv[1], 'rb').read())
    t = T.trace(rom, T.load_hints(os.path.join(os.path.dirname(__file__), 'hints.txt')))
    runs = {os.path.splitext(os.path.basename(p))[0]: load(p) for p in sys.argv[2:]}
    allpc = set().union(*runs.values()) if runs else set()

    starts = set(t.insn)
    hit = allpc & starts
    code_bytes = sum(i.size for i in t.insn.values())
    hit_bytes = sum(t.insn[a].size for a in hit)
    print(f'scenarios: {", ".join(f"{k} ({len(v)})" for k, v in sorted(runs.items()))}')
    print(f'executed instructions: {len(hit)} of {len(starts)} traced '
          f'({100 * len(hit) / len(starts):.1f} %), {hit_bytes} of {code_bytes} code bytes '
          f'({100 * hit_bytes / code_bytes:.1f} %)')

    missed = sorted(a for a in allpc if a not in starts)
    inside = [a for a in missed if t.owner[a - T.BASE] is not None]
    outside = [a for a in missed if t.owner[a - T.BASE] is None]
    print(f'executed but not traced: {len(outside)} outside traced code, '
          f'{len(inside)} inside another instruction')
    for a in (outside + inside)[:60]:
        print(f'  {a:06X}')

    print('speculative entries:')
    for a, why in t.speculative:
        print(f'  {a:06X} ({why}): {"executed" if a in allpc else "not executed"}')

    print('BIOS calls executed, by scenario:')
    for a, n in sorted(S.ROM_NAMES.items()):
        tgt = a
        ins = t.insn.get(a)
        if ins is not None and ins.mnemonic == 'jmp':
            v, _ = t.ea_target(ins)
            tgt = v if v is not None else a
        where = [k for k, v in sorted(runs.items()) if tgt in v]
        print(f'  {n:18s} {a:06X} -> {tgt:06X}: {", ".join(where) or "-"}')


if __name__ == '__main__':
    main()
