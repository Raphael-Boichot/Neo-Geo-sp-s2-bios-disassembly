"""Typed data of sm1.sm1: song and effect headers, channel sequences, records and word tables.

Used by tools/sm1.py. Each item is (size, directive, values, comment):
  directive 'defb' (values: bytes) or 'defw' (values: words, written as labels when they point
  at a labelled address, 0 stays 0).

Sequence format (read by the interpreter at $226D, sm1/names.csv SequenceStep):
  $01-$30 a note of this length (sub_28AA turns it into the channel's +4/+5 times), then
          a level byte (bits 0-4 to +3: added to the operator levels, so an attenuation; bit 6 a
          rest; bit 7 a flag) and a pitch byte (FM and SSG: low nibble the note, the index into
          FmFnumTable / SsgPeriodTable, high nibble the octave; ADPCM channels: the sample).
          The meaning of the fields is inferred: the 203 notes of the four sounds and the coin never
          use the empty table slots 3, 7, 8 and 9.
  $00     escape for a longer length: the length is the next byte (4 bytes in all)
  $31-$5F command, index byte - $30 in SequenceCommandTable, PARAMS[byte] bytes follow
  $80-$FF instrument byte - $80, then up to 3 bytes with bit 7 set (sub_22AC, sub_22DC, sub_22D4)
  $60-$7F not valid: the interpreter would loop on them forever
"""

PARAMS = {0x30: 0, 0x31: 1, 0x32: 1, 0x33: 1, 0x34: 0, 0x35: 2, 0x36: 0, 0x37: 2, 0x38: 0,
          0x39: 2, 0x3A: 1, 0x3B: 1, 0x3C: 0, 0x3D: 1, 0x3E: 0, 0x3F: 1, 0x40: 0, 0x41: 0,
          0x42: 0, 0x43: 1, 0x44: 1, 0x45: 0, 0x46: 1, 0x47: 1, 0x48: 0, 0x49: 0, 0x4A: 0,
          0x4B: 8, 0x4C: 1, 0x4D: 0, 0x4E: 1, 0x4F: 1, 0x50: 2, 0x51: 1, 0x52: 1, 0x53: 3,
          0x54: 1, 0x55: 0, 0x56: 1, 0x57: 5, 0x58: 1, 0x59: 0, 0x5A: 0, 0x5B: 1, 0x5C: 1,
          0x5D: 1, 0x5E: 1, 0x5F: 1}

# what the commands do, from their handlers (sm1/names.csv has the handler names)
COMMANDS = {
    0x30: 'nop', 0x31: 'loop start, count', 0x32: 'loop start, count', 0x33: 'tempo',
    0x34: 'loop end', 0x38: 'loop end', 0x35: 'call', 0x36: 'return', 0x37: 'timer A (YM $25, $24)',
    0x3A: 'volume', 0x40: 'end of the sound', 0x42: 'repeat from the start', 0x47: 'start sound, end',
    0x4E: 'LFO (YM $22)', 0x50: 'YM2610 register, value', 0x53: 'SSG envelope (YM $0D, $0B, $0C)',
    0x55: 'end of the effect',
}
ENDS = {0x36, 0x40, 0x41, 0x42, 0x47, 0x55}

SONG_CHANNELS = [1, 2, 3, 4, 8, 9, 10, 11, 12, 13, 14]     # PlaySound order
EFFECT_CHANNELS = [5, 6, 7, 0]                              # sub_0881 order


def word(rom, a):
    return rom[a] | (rom[a + 1] << 8)


# the pitch nibble spells the note (NoteSemitoneTable at $1E75): A-F are A-F, 0 is G, sharps 1, 2, 4, 5, 6
NOTE_NAMES = {0xC: 'C', 0x1: 'C#', 0xD: 'D', 0x2: 'D#', 0xE: 'E', 0xF: 'F', 0x4: 'F#', 0x0: 'G',
              0x5: 'G#', 0xA: 'A', 0x6: 'A#', 0xB: 'B'}


def note_text(level, pitch):
    if level & 0x40:
        return f'rest ({level:02X}h, {pitch:02X}h)'
    name = NOTE_NAMES.get(pitch & 15, f'?{pitch & 15:X}')
    return f'level {level & 0x1F:02X}h{" +flag" if level & 0x80 else ""}, {name} octave {pitch >> 4:X}'


def parse_sequence(rom, a, items, labels, kind='seq'):
    """Type one channel sequence from a; returns the address after its last event."""
    labels.setdefault(a, kind)
    calls = []
    while True:
        b = rom[a]
        if b == 0x00:
            ev = (4, f'length {rom[a + 1]:02X}h (escaped), ' + note_text(rom[a + 2], rom[a + 3]))
        elif b < 0x31:
            fl = rom[a + 1]
            ev = (3, f'length {b:02X}h, ' + note_text(fl, rom[a + 2]))
        elif b < 0x60:
            n = 1 + PARAMS[b]
            what = COMMANDS.get(b, 'command')
            if b == 0x35:
                t = word(rom, a + 1)
                calls.append(t)
                items[a] = (1, 'defb', [b], f'{what}')
                items[a + 1] = (2, 'defw', [t], None)
                a += 3
                continue
            ev = (n, f'{b:02X}h {what}' + (f' {rom[a + 1:a + n].hex(" ")}' if n > 1 else ''))
        elif b < 0x80:
            raise ValueError(f'{a:04X}: byte {b:02X}h is not a sequence byte')
        else:
            n = 1
            while n < 4 and rom[a + n] & 0x80:
                n += 1
            ev = (n, f'instrument {b - 0x80:02X}h' + (f', {rom[a + 1:a + n].hex(" ")}' if n > 1 else ''))
        size, comment = ev
        items[a] = (size, 'defb', list(rom[a:a + size]), comment)
        a += size
        if 0x31 <= b < 0x60 and b in ENDS:
            break
    for t in calls:
        if t not in items:
            parse_sequence(rom, t, items, labels, 'sub_seq')
    return a


def song(rom, a, items, labels):
    """PlaySound header: byte, 11 channel pointers, 26 bytes (49 bytes)."""
    labels.setdefault(a, 'song')
    items[a] = (1, 'defb', [rom[a]], 'song header')
    ptrs = [word(rom, a + 1 + 2 * i) for i in range(11)]
    items[a + 1] = (22, 'defw', ptrs, 'channels ' + ' '.join(str(c) for c in SONG_CHANNELS))
    items[a + 23] = (4, 'defb', list(rom[a + 23:a + 27]), '+23 tempo ($FE2B, sub_28FE), +24 to $FABF, +25 ADPCM-A total level (YM port B $01) and $FAC4, +26 to $FAC5')
    items[a + 27] = (22, 'defb', list(rom[a + 27:a + 49]), 'per channel: 2 bytes (the first | $C0 into the channel)')
    for p in ptrs:
        parse_sequence(rom, p, items, labels)


def effect(rom, a, items, labels):
    """sub_0881 header: priority, 4 channel pointers, 5 bytes (14 bytes)."""
    labels.setdefault(a, 'sfx')
    items[a] = (1, 'defb', [rom[a]], 'effect header: priority')
    ptrs = [word(rom, a + 1 + 2 * i) for i in range(4)]
    items[a + 1] = (8, 'defw', ptrs, 'channels ' + ' '.join(str(c) for c in EFFECT_CHANNELS))
    items[a + 9] = (5, 'defb', list(rom[a + 9:a + 14]), 'per channel byte, then $FE1A')
    for p in ptrs:
        parse_sequence(rom, p, items, labels)


def records(rom, a, count, size, width, items, labels, comment=None):
    labels.setdefault(a, 'dat')
    for i in range(count):
        r = a + i * size
        for j in range(0, size, width):
            n = min(width, size - j)
            items[r + j] = (n, 'defb', list(rom[r + j:r + j + n]),
                            (f'{comment} {i:02X}h' if comment and j == 0 else None))


def words(rom, a, count, items, labels, per_line=8, comment=None):
    labels.setdefault(a, 'tbl')
    for i in range(0, count, per_line):
        n = min(per_line, count - i)
        items[a + 2 * i] = (2 * n, 'defw', [word(rom, a + 2 * (i + k)) for k in range(n)],
                            comment if i == 0 else None)
