---
name: neogeo-sp-s2-disassembly
description: Disassemble, rebuild and modify the Neo Geo MVS system ROM SP-S2 (Europe MVS V2) in this repository - levels L0-L6, the tracer/generator pipeline, GNU as pitfalls and the boot checksum. Use when working in Neo-Geo-sp-s2-Bios-disassembly or on any Neo Geo cartridge system ROM.
---

# Neo Geo SP-S2 system ROM disassembly

Playbook for this repository. Step-by-step commands are in `HOWTO.md`; the
measured status is the level table in `README.md`. Same method and evidence
tags as the Game Boy Camera and Game Boy Printer disassemblies.

## The ROM

- `sp-s2.sp1`: 131,072 bytes, CRC32 `9036d879`, SHA-1 `4f5ed7105b7128794654ce82b51723e16e389543`.
  Never commit it: it lives in `roms/` (git-ignored); `make check` works from the SHA-1 alone.
- Files are in MAME / EPROM order: every 16-bit word is byte-swapped. The 68000 sees it big-endian,
  mapped at `$C00000-$C1FFFF` (mirrored up to `$CFFFFF`). `$D00000-$D0FFFF` is MVS backup RAM, not a mirror.
- Header: vectors `$C00000-$C0007F` (SSP `$10F300`, reset `$C00402`); checksum byte at `$C00080`
  (repeated at `$C00081`); `"NEO-GEO SYSTEM PROGRAM VERSION 0 COPYRIGHT BY SNK..."` from `$C00082`;
  `$C00400` system type (`$80` MVS), `$C00401` region (`2` Europe).
- BIOS call table `$C00402-$C004DA`: 6-byte slots, `jmp abs.l` or `jmp (d16,pc)` + `nop`, then `rts`.
  Games call these addresses: they must never move.
- Boot checksum: low byte of sum(`$C00000-$C0007F`) + sum(`$C00082-$C1FFFF`) = byte at `$C00080`.
- Free space (`$FF` fill, 76,723 B): `$C000BF-$C003FF` (833 B, in the header), `$C004DC-$C01FFF` (6,948 B), `$C04300-$C10FFF` (52,480 B),
  `$C1B86E-$C1EFFF` (14,226 B), `$C1F744-$C1FFFF` (2,236 B).
- BIOS work RAM is reached through `a5 = $10F300` (`lea $10F300,a5` at reset): `0xA82(a5)` is `$10FD82`.

## Levels (say which one a claim is about)

| Level | Meaning | Test |
|---|---|---|
| L0 | source rebuilds the ROM byte for byte | `make check` prints `OK sha1 4f5ed710...` |
| L1 | every byte typed: code, data (text, pointers, bytes), free | `tools/stats.py` |
| L2 | code proven by recursive descent, every indirect jump resolved or explained, then run in an emulator | stats + MAME trace |
| L3 | every routine, table and string named, tagged C / I / ? | names file, doubts list |
| L4 | RAM, backup RAM and registers named in the source (incl. `x(a5)`) | stats: raw operand counts |
| L5 | editable tree: modules, all ROM addresses symbolic, code can move | relocation test in MAME |
| L6 | understanding: boot, test mode, coin/credit, calendar, memory card, sound | written reference |

## Pipeline

1. `tools/trace.py`: recursive descent (Capstone) from the vectors and the BIOS call table; follows
   `movea.l tbl(pc,dN.w),aN` + `jmp/jsr (aN)` pointer tables; then two speculative passes
   (code pointers stored as `move.l #$C1xxxx`, orphan code right after `rts/jmp/bra`). Each speculative
   entry is listed; a decode that reaches an undecodable word (Capstone `id 0`) is rejected.
2. `tools/gen_source.py`: emits `src/sp-s2.s` (GNU as, Motorola syntax) and `src/neogeo.inc`, labels every
   target (`sub_`, `loc_`, `dat_`, `tbl_` + address, or a public name from `tools/symbols.py`), turns
   `$00C0xxxx`/`$00C1xxxx` longs in data into `dc.l label`, then assembles and compares in a loop until the
   image is identical.
3. `make check` / `make fixsum` / `tools/romtool.py` for swapping, hashing and the checksum.
4. Manual corrections go in `tools/hints.txt` (`entry`, `noreturn`, `longtable`), each with a reason.
5. `src/` is split into the modules of `symbols/modules.csv`; the generator converges on one combined
   file, then writes the modules and checks that the split source rebuilds the ROM.
6. Names live in `symbols/*.csv` (`addr,name,tag,note`): `rom_names.csv`, `ram.csv`, `registers.csv`,
   `cart_header.csv`. Never edit names in `src/`: `make source` regenerates it. `src/ram.inc` lists every
   RAM address used (named, else `ram_XXXXXX` / `bram_XXXXXX`); `x(a5)` is written `(NAME-A5_BASE,a5)`.
7. Coverage: `tools/mame_coverage.sh NAME GAME [MODE=dip KEYS=...]` runs MAME with the debugger trace
   streamed through a pipe and keeps the unique executed addresses in `coverage/NAME.txt`;
   `tools/coverage.py` compares them with the static trace (missed code, speculative entries, BIOS calls).

Status checks: `make check` (L0), `tools/stats.py` (L1-L5 counts), `tools/coverage.py` (L2),
`tools/relocation_test.py` + MAME (L5).

## Pitfalls (all hit once)

- GNU as optimises silently: `move.l #imm,dN` becomes `moveq` when it fits. Such lines stay as `dc.w`
  with the instruction in a comment (2 in SP-S2). Check every new tool for this kind of rewrite.
- After a size change, every later absolute target moves, and the first byte that differs is in an earlier
  `jmp` that points past it: blaming the first difference gave 138 false raw lines. Detect size changes from
  the assembler listing (location counter vs original address) instead.
- Capstone prints `moveq #$ff` unsigned (GNU wants `-0x1`), `abcd.b`/`sbcd.b`/`exg.l` with a size GNU refuses,
  and returns an `id 0` "dc.w" pseudo-instruction for invalid words: treat it as invalid, not as code.
- An address read through `x(pc,dN.w)` is a data table: never trace it as code (`$C199FC` was a false entry).
- `jmp (a6)` at `$C131A8` is a return through a6, used while the RAM (and so the stack) is being tested.
- The wiki pages disagree on `REG_PALBANK0`/`1`; the register page is followed. Note such conflicts.
- A dispatch can have instructions between the table load and the jump (`movea.l tbl(pc,d0.w),a0 ;
  pea (ret,pc) ; jmp (a0)` at `$C1509E`): the tracer looks back 3 instructions for a load into the
  jump register.
- `pea (label,pc)` pushes a return address that a later `rts` jumps to: it is code, not data
  (`$C133BA` was missed until MAME ran it).
- MAME: a read tap on the ROM does not see opcode fetches (only data reads): use the debugger trace
  (`-debug -debugger none`, started from Lua with `manager.machine.debugger:command`; `-debugscript`
  is ignored with `-debugger none`). A trace is ~20,000 lines per frame: stream it through a FIFO.
- MAME saves DIP switches in its cfg: give each run its own `-cfg_directory`.
- a4 is a general pointer: only after `lea $D08000,a4` is it the backup RAM base. The generator
  follows a4 per routine and through calls whose callers all set it; elsewhere `-0x7Fxx(a4)` stays raw.
  The tracer records `jsr (label,pc)` both as a code and as a data reference: count it once.
- RAM $10FCD8 was first named after the test menu, then found used as a frame count: check every
  user of a variable (all writes and reads) before giving it a specific name.
- Unreferenced code exists: a controller test and a memory card utility (`$C14EA2-$C16AA9`) that
  nothing calls. The tracer reached only their first routine by the orphan heuristic; the rest looked
  like data (`NqNq` "text" was a run of `nop`, `$4E71`). Look for 68000 patterns in big data blocks
  (`4E75` rts, `4EBA` jsr, `3B7C` move.w #,(d,a5)) and trace them from their pointer tables
  (`tools/hints.txt`), then check them by pointing a menu entry at them in a test build.
- MAME memory card: create it from Lua (`manager.machine.images[":memcard"]:create(path)`) before the
  BIOS checks it; `-memc` needs an existing file.
- Reaching game code paths (card save) needs play: a simple bot (walk right, mash A both sides,
  continues) plus MAME states every 1,200 frames, then replay only the interesting stretch traced.
  Ask the owner how the game behaves (Sengoku 2: too slow brings a spiked cart; SAVE only when you
  lose in level 2; fixed scenes: wait and mash A). The save prompt lasts about 10 s: snapshot every
  30 frames around it to time the keys.
- MAME debugger actions: the program counter is `curpc` (`pc` gives "unknown symbol" and the
  action does nothing); `frame` works. Lua write and read taps on the I/O registers and on the vector
  area gave nothing past the first vector switch: watch them with debugger `wpset` instead.
- Code that never runs may wait for a special cartridge: the alternate calendar routines run only for a
  header ID of NEO-CLN. Read the slot scan's ID checks, then patch the ID in a copy of a game set
  (`tools/neo_cln_test.py`); MAME accepts the changed ROM (wrong checksum warning only).
- A path no game takes (SYSTEM_INT2: a timer IRQ while the system ROM vectors are mapped) can be
  reached by a breakpoint that sets the game state at the right instruction (`DEBUG_CMDS`); such a run
  proves the code works, not that a game uses it: say so.
- One name in two symbol files (a routine `BookPlayDays` and a RAM area `BookPlayDays`) is one assembler
  symbol twice: the generator fell back to raw words. `tools/symbols.py` now refuses it.
- MAME Lua: keep the object returned by `emu.add_machine_stop_notifier` (garbage collection drops the
  subscription, so the card file was saved only in short runs); memory taps are dropped when the memory
  map is rebuilt (vector or bank switch): install them again every frame.
- MAME's memory card is 2 KB, 8-bit (high byte reads `$FF`, mirrored every `$1000`): code that expects the
  1M 16-bit RAM card fails its RAM test. Emulate the card with read/write taps instead of forcing the code.
  MAME has no MVS SELECT input either: a read tap on `REG_STATUS_B` gives it.
- A 2 MB P1 (KOF '94) is loaded by MAME second half first: its header is at `$100000` in the file.
- Some code waits for a board state, not a key: the 1M card recovery runs only with no cartridge and
  Service held at power-on. Read the branch conditions before concluding that code is unreachable.
- Printable bytes are not text: three numeric tables at `$C02000-$C042FF` were first shown as 57 % text.
  Text needs mostly letters and no long counting run, and is never looked for inside a named table.
- A comment like `| C1B86E-C1EFFF free` must not be read as an instruction address by the listing check.

## Discipline

- Tag claims W (public documentation: NeoGeoDev wiki), C (read in code or seen in an emulator),
  I (inferred), ? (doubt); say what was not checked.
- Public references only: SNK ROMs (other system ROM versions are fair comparisons), the NeoGeoDev wiki,
  MAME. Never quote, copy or name third-party replacement BIOSes in this repository.
- Names come from public documentation or from reading the code: do not invent names for unread routines.
- Regenerate, rebuild and `make check` before every commit; recompute numbers before quoting them.
- Never give one percentage for progress: give the level table with the counts from `tools/stats.py`.
