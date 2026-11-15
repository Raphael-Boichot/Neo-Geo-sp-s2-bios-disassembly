"""Z80 instruction decoder for the sm1.sm1 disassembly.

decode(mem, pc) -> Insn with the length, the text (Zilog syntax as z80asm takes it, with
`{a16}`-style operands left to the caller through `refs`), and the flow:

  kind   'seq' falls through; 'jp' / 'jr' / 'call' / 'rst' with `target`;
         'ret' (unconditional return), 'jpind' (jp (hl)/(ix)/(iy)), 'halt'
  cond   True when the jump, call or return is conditional (it also falls through)
  refs   list of (kind, value) for 16-bit operands: 'imm' (ld rr,nn / ld (nn)...), 'addr'
         (jump or call target), 'mem' (ld a,(nn) and the like)

Undocumented opcodes return None: the generator keeps those bytes as data.
"""

R8 = ['b', 'c', 'd', 'e', 'h', 'l', '(hl)', 'a']
RP = ['bc', 'de', 'hl', 'sp']
RP2 = ['bc', 'de', 'hl', 'af']
CC = ['nz', 'z', 'nc', 'c', 'po', 'pe', 'p', 'm']
ALU = ['add a,', 'adc a,', 'sub ', 'sbc a,', 'and ', 'xor ', 'or ', 'cp ']
ROT = ['rlc', 'rrc', 'rl', 'rr', 'sla', 'sra', None, 'srl']   # 6 = sll, undocumented


class Insn:
    __slots__ = ('pc', 'size', 'text', 'kind', 'cond', 'target', 'refs')

    def __init__(self, pc):
        self.pc, self.size, self.text = pc, 1, ''
        self.kind, self.cond, self.target, self.refs = 'seq', False, None, []


def h8(v):
    return f'0{v:02x}h'


def h16(v):
    return f'0{v:04x}h'


def decode(mem, pc):
    def b(i):
        return mem[(pc + i) & 0xFFFF]

    def w(i):
        return b(i) | (b(i + 1) << 8)

    ins = Insn(pc)
    op = b(0)
    idx = None
    off = 0
    if op in (0xDD, 0xFD):
        idx = 'ix' if op == 0xDD else 'iy'
        off = 1
        op = b(1)
        if op in (0xDD, 0xFD, 0xED):
            return None
    if op == 0xCB:
        return _cb(ins, b, idx, off)
    if op == 0xED:
        if idx:
            return None
        return _ed(ins, b, w)

    x, y, z, p, q = op >> 6, (op >> 3) & 7, op & 7, (op >> 4) & 3, (op >> 3) & 1
    n = off + 1          # index of the byte after the opcode

    def r(i, allow_index=True):
        """8-bit register i, with (ix+d) replacing (hl) when indexed."""
        nonlocal n
        if idx and i == 6:
            d = b(off + 1)
            d = d - 256 if d >= 128 else d
            n = max(n, off + 2)
            return f'({idx}{d:+d})'.replace('+-', '-')
        if idx and i in (4, 5):
            return None            # ixh/ixl: undocumented
        return R8[i]

    def rp(i):
        return idx if (idx and i == 2) else RP[i]

    def rp2(i):
        return idx if (idx and i == 2) else RP2[i]

    text = None
    if x == 0:
        if z == 0:
            if y == 0:
                text = 'nop'
            elif y == 1:
                text = "ex af,af'"
            else:
                d = b(off + 1)
                tgt = (pc + off + 2 + (d - 256 if d >= 128 else d)) & 0xFFFF
                n = off + 2
                ins.kind, ins.target = 'jr', tgt
                if y == 2:
                    text = 'djnz {T}'
                    ins.cond = True
                elif y == 3:
                    text = 'jr {T}'
                else:
                    text = f'jr {CC[y - 4]},{{T}}'
                    ins.cond = True
        elif z == 1:
            if q == 0:
                v = w(off + 1)
                n = off + 3
                text = f'ld {rp(p)},{{N}}'
                ins.refs.append(('imm', v))
            else:
                text = f'add {rp(2)},{rp(p)}'
        elif z == 2:
            if q == 0:
                if p < 2:
                    text = f'ld ({RP[p]}),a'
                else:
                    v = w(off + 1)
                    n = off + 3
                    text = f'ld ({{N}}),{"hl" if p == 2 and not idx else (idx or "a")}' if p == 2 else 'ld ({N}),a'
                    ins.refs.append(('mem', v))
            else:
                if p < 2:
                    text = f'ld a,({RP[p]})'
                else:
                    v = w(off + 1)
                    n = off + 3
                    text = f'ld {idx or "hl"},({{N}})' if p == 2 else 'ld a,({N})'
                    ins.refs.append(('mem', v))
        elif z == 3:
            text = f'{"inc" if q == 0 else "dec"} {rp(p)}'
        elif z in (4, 5):
            reg = r(y)
            if reg is None:
                return None
            text = f'{"inc" if z == 4 else "dec"} {reg}'
        elif z == 6:
            reg = r(y)
            if reg is None:
                return None
            v = b(n)
            n += 1
            text = f'ld {reg},{h8(v)}'
        else:
            text = ['rlca', 'rrca', 'rla', 'rra', 'daa', 'cpl', 'scf', 'ccf'][y]
    elif x == 1:
        if z == 6 and y == 6:
            text = 'halt'
            ins.kind = 'halt'
        else:
            # with an index prefix only the (ix+d) operand is indexed; h/l stay h/l
            if idx and (y == 6 or z == 6):
                a_ = r(y) if y == 6 else R8[y]
                b_ = r(z) if z == 6 else R8[z]
            else:
                a_, b_ = r(y), r(z)
                if idx and (a_ is None or b_ is None or True):
                    return None        # prefix without (ix+d): undocumented
            text = f'ld {a_},{b_}'
    elif x == 2:
        reg = r(z)
        if reg is None or (idx and z != 6):
            return None
        text = ALU[y] + reg
    else:
        if z == 0:
            text = f'ret {CC[y]}'
            ins.kind, ins.cond = 'ret', True
        elif z == 1:
            if q == 0:
                text = f'pop {rp2(p)}'
            else:
                if p == 0:
                    text = 'ret'
                    ins.kind = 'ret'
                elif p == 1:
                    text = 'exx'
                elif p == 2:
                    text = f'jp ({idx or "hl"})'
                    ins.kind = 'jpind'
                else:
                    text = f'ld sp,{idx or "hl"}'
        elif z == 2:
            v = w(off + 1)
            n = off + 3
            text = f'jp {CC[y]},{{T}}'
            ins.kind, ins.cond, ins.target = 'jp', True, v
        elif z == 3:
            if y == 0:
                v = w(off + 1)
                n = off + 3
                text = 'jp {T}'
                ins.kind, ins.target = 'jp', v
            elif y == 2:
                text = f'out ({h8(b(off + 1))}),a'
                n = off + 2
            elif y == 3:
                text = f'in a,({h8(b(off + 1))})'
                n = off + 2
            elif y == 4:
                text = f'ex (sp),{idx or "hl"}'
            elif y == 5:
                text = 'ex de,hl'
            elif y == 6:
                text = 'di'
            elif y == 7:
                text = 'ei'
        elif z == 4:
            v = w(off + 1)
            n = off + 3
            text = f'call {CC[y]},{{T}}'
            ins.kind, ins.cond, ins.target = 'call', True, v
        elif z == 5:
            if q == 0:
                text = f'push {rp2(p)}'
            elif p == 0:
                v = w(off + 1)
                n = off + 3
                text = 'call {T}'
                ins.kind, ins.target = 'call', v
        elif z == 6:
            v = b(off + 1)
            n = off + 2
            text = ALU[y] + h8(v)
        else:
            text = f'rst {h8(y * 8)}'
            ins.kind, ins.target = 'rst', y * 8
    if text is None:
        return None
    if idx and not any(t in text for t in (idx,)):
        return None                # a prefix that changes nothing: keep as data
    ins.text, ins.size = text, n
    if ins.kind in ('jp', 'call'):
        ins.refs.append(('addr', ins.target))
    return ins


def _cb(ins, b, idx, off):
    if idx:
        d = b(off + 1)
        op = b(off + 2)
        size = off + 3
        if op & 7 != 6:
            return None
        d = d - 256 if d >= 128 else d
        reg = f'({idx}{d:+d})'.replace('+-', '-')
    else:
        op = b(1)
        size = 2
        reg = R8[op & 7]
    x, y = op >> 6, (op >> 3) & 7
    if x == 0:
        if ROT[y] is None:
            return None
        ins.text = f'{ROT[y]} {reg}'
    else:
        ins.text = f'{["", "bit", "res", "set"][x]} {y},{reg}'
    ins.size = size
    return ins


def _ed(ins, b, w):
    op = b(1)
    x, y, z, p, q = op >> 6, (op >> 3) & 7, op & 7, (op >> 4) & 3, (op >> 3) & 1
    ins.size = 2
    t = None
    if x == 1:
        if z == 0 and y != 6:
            t = f'in {R8[y]},(c)'
        elif z == 1 and y != 6:
            t = f'out (c),{R8[y]}'
        elif z == 2:
            t = f'{"sbc" if q == 0 else "adc"} hl,{RP[p]}'
        elif z == 3:
            v = w(2)
            ins.size = 4
            ins.refs.append(('mem', v))
            t = f'ld ({{N}}),{RP[p]}' if q == 0 else f'ld {RP[p]},({{N}})'
        elif z == 4 and y == 0:
            t = 'neg'
        elif z == 5 and y in (0, 1):
            t = 'retn' if y == 0 else 'reti'
            ins.kind = 'ret'
        elif z == 6 and y in (0, 2, 3):
            t = f'im {[0, None, 1, 2][y]}'
        elif z == 7 and y < 6:
            t = ['ld i,a', 'ld r,a', 'ld a,i', 'ld a,r', 'rrd', 'rld'][y]
    elif x == 2 and z < 4 and y >= 4:
        t = [['ldi', 'cpi', 'ini', 'outi'], ['ldd', 'cpd', 'ind', 'outd'],
             ['ldir', 'cpir', 'inir', 'otir'], ['lddr', 'cpdr', 'indr', 'otdr']][y - 4][z]
    if t is None:
        return None
    ins.text = t
    return ins
