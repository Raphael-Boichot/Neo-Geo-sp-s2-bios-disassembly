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

Sent with no reply expected except 1. `sm1.sm1` also accepts 4, 5, 6, 8, 9, `$10` and `$5F`, which
SP-S2 never sends (`CommandTypeTable` at `$51D4`).

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
  (`SequenceCommandTable`).

Disassembly status (`sm1/`, `make check` compares the rebuilt ROM):

| Level | State |
|---|---|
| L0 rebuilt byte for byte | done: `sm1/src/sm1.asm`, z80asm, SHA-1 `42f9d7dd...` |
| L2 code traced | 5,188 instructions (10,614 bytes), no indirect jump left unresolved (`sm1/hints.txt`); 2,324 ran in MAME (`sm1/coverage.txt`), none outside the trace |
| L1 data typed | not yet: `$2A16-$53D4` (10.7 KB: sound tables and music data) is still plain bytes |
| L3 names | 51 names in `sm1/names.csv` (vectors, commands, queue, the routines above); 576 labels automatic |
| L4 RAM | 15 RAM names; 585 lines still use raw RAM addresses |

## Sources

`src/power_on.s` (`SoundSlotSwitch`, `Z80Check`, `SwitchSlot`), `src/eyecatcher.s`,
`src/hardware_test.s`; `sm1/src/sm1.asm`, `sm1/names.csv`; NeoGeoDev wiki: Z80, Z80 port map,
68k/Z80 communication; MAME 0.264 runs with `tools/mame_z80.sh`.
