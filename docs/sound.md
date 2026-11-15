# Sound commands

The 68000 talks to the Z80 sound CPU through one byte each way. Which Z80 program answers depends on
the board ROM selection: the board's own `sm1.sm1` or the cartridge's M1 ROM. Tags: **C** read in the
code and run in MAME, **W** public reference (NeoGeoDev wiki), **I** inferred.

## The channel

- 68000 -> Z80: a byte written to `REG_SOUND` (`$320000`) raises the Z80's NMI; the Z80 reads it on
  port `$00` (W).
- Z80 -> 68000: the Z80 writes port `$0C`; the 68000 reads it in `REG_SOUND`. No interrupt (W).
- The Z80 program is read from `sm1.sm1` after a write to `REG_BRDFIX` and from the cartridge's M1 ROM
  after `REG_CRTFIX`, together with the fix tiles (W; C: MAME traces below).

## Changing the Z80 ROM

The system ROM never swaps the ROM under a running Z80 program:

1. `SoundSlotSwitch` (`$C11FB2`) sends command 1 and waits for the reply 1 (8 x 4 VBlanks at most).
   The Z80 (`PrepareSwitch` in `sm1.sm1`) silences the YM2610, writes `jp $FFFD` at `$FFFD` in its
   RAM, replies 1 and loops there.
2. The system ROM writes `REG_BRDFIX` or `REG_CRTFIX` (and `REG_SLOT` for another slot).
3. It sends command 3: the Z80 resets (`SoftReset`, `jp $0000`) into the newly selected ROM.

Seen in MAME (C, `tools/mame_z80.sh`): the Z80 runs `sm1.sm1` from power-on, waits at `$FFFD` after
command 1, and the next instruction after command 3 is `$0000` of the other ROM.

## When the board program runs

| When | Z80 program | Tag |
|---|---|---|
| power-on, up to the first slot switch (`Z80Check` sends 1 and expects 1) | `sm1.sm1` | C (MAME) |
| no cartridge (hardware test at power-on) | `sm1.sm1` throughout | C (MAME) |
| a game, its eyecatcher and its demo (after `SwitchSlot`: `REG_CRTFIX`) | cartridge M1 | C (MAME, Sengoku 2) |
| the hardware test's sound test (`REG_BRDFIX`, then command 3) | `sm1.sm1` | C (MAME, Sengoku 2 in the slot) |
| HOW_TO_PLAY (`REG_BRDFIX` and command 3, then `REG_CRTFIX` and 3 at the end) | `sm1.sm1` | C (code), not traced |

So the eyecatcher jingle an MVS plays comes from the cartridge: command 2 is sent after
`SwitchSlot` has selected the cartridge ROMs. `sm1.sm1` has the same jingle (below), which SP-S2
never asks it for (C for the order of the code, I that no other path does).

## Commands sent by SP-S2

| Command | Sent by | `sm1.sm1` | Tag |
|---|---|---|---|
| 1 | `Z80Check` (power-on), `SoundSlotSwitch` | `PrepareSwitch`: silence, reply 1, wait in RAM | C |
| 2 | `Eyecatcher` (`$C1802E`); not on an MVS whose DEMO SOUND is WITHOUT | `Command2Eyecatcher`: plays sound `$5F`, the eyecatcher jingle | C (MAME) |
| 3 | `CallUser`, `CheckSettingMode`, `NextSlot`, `CardStillInserted`, `Eyecatcher`, `HowToPlay`, the hardware test | `SoftReset` | C |
| 7 | the sound test (after 3) | `Command7Enable`: clears the queue, silences, unlocks `PlaySound` | C (MAME) |
| `$5C`, `$5D`, `$5E` | the sound test: LEFT, RIGHT, CENTER | a test sound on the left channel only, the right only, both | C (MAME, no cartridge) |
| `$7F` | `PlayCoinSound`, a coin on a system screen | `CoinSound`, about a second | C (MAME) |

Sent with no reply expected except 1. `sm1.sm1` also accepts commands SP-S2 never sends
(`CommandTypeTable` at `$51D4`), all run in MAME by sending them from the 68000 side:

| Command | `sm1.sm1` |
|---|---|
| 4 | stop everything, then lock music and effects |
| 5 / 8 | stop and lock the music / unlock it |
| 6 / 9 | stop and lock the effects / unlock them |
| `$10` | self test: sum of `$0000-$EFFF` against the checksum byte at `$0014` (`$D4`), RAM `$55`/`$AA` and address tests; replies 1 when all pass (MAME: 1, about 64 frames later), 0 otherwise, then resets |
| `$5F` | the eyecatcher jingle, like command 2 |

The sound test's SOUND OFF sends 3 then 7. Command 7 is needed after a reset: `Init` sets `SoundLock`,
and until 7 clears it `$5C-$5F` play nothing (C: MAME, with and without 7).

The eyecatcher jingle of `sm1.sm1` (command 2 or sound `$5F`) and the one of Sengoku 2's M1 ROM, both
recorded in MAME, have the same 7-second loudness envelope (correlation 0.9996; the board's is about
20 % louder) (C).

## Inside sm1.sm1

`Ver 1.5b by Mr.Pac h Ber.02/01/08` at `$003E`. 21 KB of program and data, then zeros up to
`$F7FF` and `$FF` over the RAM range; the 128 KB dump holds the 64 KB twice.

- `Nmi` (`$0066`) reads the command. 1, 3 and `$10` are handled at once (they reset the stack); 0 is
  ignored; any other goes into an 8-entry queue (`CommandQueue`, `$FE48`). The reply after each
  command is a random byte with bit 7 set (`ReplyValue`).
- `MainLoop` (`$0135`) takes the next command; `DispatchCommand` looks up its type in
  `CommandTypeTable`: 1 system command (`rst 28h`, `SystemCommandTable`, 26 entries), 2 sound or tune
  (`PlaySound`, pointers in `SoundTable` from command `$20`), 5 coin sound.
- `rst 18h` / `rst 20h` write a YM2610 register (d = register, e = value) on port A / B, `rst 08h` /
  `rst 10h` are the waits between accesses. The YM2610 timer interrupt (`$0038`, `TimerIrq`) runs the
  sound engine, whose music sequences are read by an interpreter with 48 commands
  (`SequenceStep`, `SequenceCommandTable`).

### The data

Everything from `$1E75` to `$53D4` is typed in the source (`sm1/hints.txt`, `tools/sm1_data.py`):

| Address | Content | Tag |
|---|---|---|
| `$2A80` | `FmInstruments`: 103 FM instruments of 52 bytes (`LoadInstrument`) | C |
| `$3F6C` | `SoundTable`: 64 pointers, sounds `$20-$5F`; only `$5C-$5F` are filled | C |
| `$3FEC` | `EffectTable`: 32 pointers, effects `$60-$7F`; only `$7F` (the coin) is filled | C |
| `$402C-$43F6` | the four sounds: a 49-byte header (11 channel pointers: FM 1-4, ADPCM-A 8-13, ADPCM-B 14) and the channel sequences | C |
| `$43F7-$4498` | the coin effect: a 14-byte header (priority, SSG channels 5-7 and channel 0) and its sequences | C |
| `$5355`, `$5395` | FM F-numbers and SSG periods by note index | I |
| `$51D4` | `CommandTypeTable` | C |
| other tables | timer A values, per-algorithm carriers, records of 11 and 26 bytes (`$44B9`, `$47F6`), word tables `$4FA4` and `$50D4`, empty tables for the unused command types 3 and 4 | I (sizes from the code; meaning partly) |

A sequence is a list of events: a note, given as its length (`$01-$30`, or `$00` and a longer
length), a level byte (bits 0-4 an attenuation, bit 6 a rest) and a pitch byte (high nibble the
octave, low nibble the note, the index into `FmFnumTable` / `SsgPeriodTable`; I: the 203 notes never
use the table's empty slots). The note nibble spells the note name in hex: `A`-`F` are A-F, `0` is G,
`1`, `2`, `4`, `5`, `6` are C#, D#, F#, G#, A# (C: `NoteSemitoneTable` at `$1E75`, used to transpose);
the source comments give the notes that way (A octave 6 ...); an instrument (`$80` + number) with up to three bytes that have bit 7 set; or a command
`$31-$5F` with its parameters (call, loop, tempo, volume, timer A, YM2610 write, end, repeat ...).
Every one of the 50 sequences of the four sounds and the coin parses to its end marker, and the
sequences and headers tile `$402C-$4498` with no gap: that is the check on the parameter counts.
The sound test sounds use only channel 1 and repeat (command `42h`); the jingle uses the four FM
channels and two sub-sequences.

Disassembly status (`sm1/`, `make check` compares the rebuilt ROM):

| Level | State |
|---|---|
| L0 rebuilt byte for byte | done: `sm1/src/sm1.asm`, z80asm, SHA-1 `42f9d7dd...` |
| L2 code traced | 5,188 instructions (10,614 bytes), no indirect jump left unresolved (`sm1/hints.txt`); 2,324 ran in MAME (`sm1/coverage.txt`), none outside the trace |
| L1 data typed | done: 10,785 data bytes typed (tables, records, headers, 50 sequences, one event per line); the 62 bytes left are the filler between the vectors |
| L3 names | 188 names in `sm1/names.csv` (C 134, I 41, W 9, ? 4): every routine that runs in MAME, the commands, sequence commands, sounds and tables; 67 routines never run and stay `sub_` (engine paths no sound here uses), 419 `loc_` jump labels automatic as in the system ROM source |
| L4 RAM | channel blocks, loop and call stacks, modulation blocks, register copies, locks and the driver variables that are understood; 391 lines still use raw RAM addresses (fields of the engine's parameter blocks) |

## Sources

`src/power_on.s` (`SoundSlotSwitch`, `Z80Check`, `SwitchSlot`), `src/eyecatcher.s`,
`src/hardware_test.s`; `sm1/src/sm1.asm`, `sm1/names.csv`; NeoGeoDev wiki: Z80, Z80 port map,
68k/Z80 communication; MAME 0.264 runs with `tools/mame_z80.sh`.
