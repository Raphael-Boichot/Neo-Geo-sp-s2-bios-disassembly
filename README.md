# Neo-Geo-sp-s2-Bios-disassembly

Disassembly of the Neo Geo MVS system ROM **SP-S2** (Europe MVS V2, the default BIOS in MAME), with a
source tree that rebuilds the ROM byte for byte. The long-term goal is a custom system ROM built on it.

**Status: L0 and L5 done, L4 nearly (30 backup RAM accesses left); L1/L2 measured; naming in progress (157 names)** (2026-11-12): `src/sp-s2.s` assembles to the original ROM (SHA-1 below). Naming has not
started; the BIOS has been run in MAME (screens below, levels in the table).

## ROM map

One pixel per byte, coloured by type (`tools/rom_map.py`); bright blue code ran in MAME in at least
one of the coverage scenarios. Full ROM:

![SP-S2 byte map](docs/rom_map.png)

Used bytes only (free space folded, 256 bytes per row), with the named tables:

![SP-S2 used bytes](docs/rom_map_used.png)

## Screens

SP-S2 rebuilt from `src/` is byte-identical, so these MAME 0.264 captures show this code
(`tools/mame_run.lua`, HOWTO section 7). Boot sequence: start-up screen, the NEO·GEO logo animation,
"MAX 330 MEGA / PRO-GEAR SPEC", SNK logo:

![SP-S2 boot sequence](docs/boot_sequence.png)

Test mode ("Setting Mode" DIP on): main menu, hardware test (crosshatch), hard DIP, soft DIP (cabinet),
book keeping, code number, calendar:

![SP-S2 test mode](docs/test_mode.png)

Hardware test: START steps from the crosshatch to the colour bars, the I/O check (inputs, DIP switches,
credit LED counters), the sound test, the memory card test and the backup RAM clear:

![SP-S2 hardware test](docs/hardware_test.png)

Hidden programs: SP-S2 contains a controller test and a MEMORY CARD UTILITY (format, display data
names, copy, delete, user name) that nothing in the ROM calls (`$C14EA2-$C16AA9`, no call, jump or
pointer to them). A test build (`tools/hidden_programs_test.py`) points two test-menu items at them;
both still work in MAME:

![Unreferenced controller test and memory card utility](docs/hidden_programs.png)

Memory card in MAME: Sengoku 2 played by a bot (`tools/mame_bot_sengoku2.lua`) reaches its second
area; losing there brings the game's SAVE prompt (CARD save), a new game with that card offers LOAD and
resumes in the second area (CARD load), and the card utility deletes the data (CARD delete):

![Sengoku 2 save, load and delete through the BIOS CARD call](docs/card_save_load.png)

Relocation test (`tools/relocation_test.py`): a modified build where the main code has moved and a
new routine prints a line under the test menu; the boot sequence and the hardware test still work:

![Relocated build in MAME](docs/relocation_test.png)

## BIOS calls used by games

`tools/scan_bios_calls.py` counts references to each BIOS call slot in a game's program ROM
(MAME order). Checked so far:

| Game | SYSTEM_IO | CREDIT_CHECK | CREDIT_DOWN | READ_CALENDAR | CARD | HOW_TO_PLAY | FIX_CLEAR | LSP_1ST | SYSTEM_INT2 |
|---|---|---|---|---|---|---|---|---|---|
| Sengoku 2 | 1 | 1 | 0 | 0 | 7 | 0 | 0 | 0 | 0 |
| NAM-1975 | 1 | 6 | 0 | 0 | 3 | 1 (ran in MAME) | 2 | 2 | 0 |
| Cyber-Lip | 1 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 0 |
| Magician Lord | 3 | 1 | 1 (unused wrapper) | 1 | 1 | 0 | 0 | 0 | 0 |

None of them points its level 2 (HBL) interrupt vector at SYSTEM_INT2. HOW_TO_PLAY as called by
NAM-1975 (the BIOS animates the joystick and buttons, the captions come from the game):

![HOW_TO_PLAY in NAM-1975](docs/how_to_play_nam1975.png)

## Contents

| File | What it is |
|---|---|
| [`src/`](src/) | Generated 68000 source (GNU as, Motorola syntax), ROM addresses in comments: `sp-s2.s` includes 14 modules (`header.s`, `tables.s`, `boot.s`, `system.s`, `power_on.s`, `calendar.s`, `card.s`, `boot_error.s`, `hardware_test.s`, `eyecatcher.s`, `video_io.s`, `how_to_play.s`, `test_mode.s`, `data_end.s`) |
| [`src/neogeo.inc`](src/neogeo.inc), [`src/ram.inc`](src/ram.inc) | Registers, cartridge header, `A5_BASE`/`A4_BASE`; every RAM address used |
| [`Makefile`](Makefile) | `make`, `make check`, `make fixsum`, `make source` |
| [`HOWTO.md`](HOWTO.md) | Requirements, build, regeneration, trace hints, how to modify and test the BIOS |
| [`SKILL.md`](SKILL.md) | Working playbook: ROM facts, levels L0-L6, pipeline, pitfalls, rules |
| [`tools/trace.py`](tools/trace.py) | Recursive-descent tracer (Capstone): code, data and free bytes |
| [`tools/gen_source.py`](tools/gen_source.py) | Writes `src/` from the ROM and loops until the rebuild is identical |
| [`tools/symbols.py`](tools/symbols.py) | Public names: BIOS calls, registers, BIOS RAM |
| [`tools/romtool.py`](tools/romtool.py) | Byte swap, SHA-1 check, boot checksum check and fix |
| [`tools/stats.py`](tools/stats.py) | Counts behind the level table |
| [`tools/hints.txt`](tools/hints.txt) | Manual tracer hints (empty so far) |
| [`tools/mame_run.lua`](tools/mame_run.lua) | MAME autoboot script: headless screenshots, test mode, joystick taps |
| [`docs/`](docs/) | ROM byte maps and screenshots of the BIOS running in MAME |
| [`symbols/`](symbols/) | Names (`rom_names`, `ram`, `registers`, `cart_header`), named regions and module boundaries (`modules.csv`), tagged W / C / I / ? |
| [`coverage/`](coverage/) | Executed system ROM addresses of each MAME scenario (`tools/mame_coverage.sh`) |
| [`tools/coverage.py`](tools/coverage.py) | Compares MAME coverage with the static trace |
| [`tools/rom_map.py`](tools/rom_map.py) | Draws the ROM byte maps |
| [`tools/relocation_test.py`](tools/relocation_test.py) | Builds a modified BIOS with moved code and an added routine (L5 test) |
| [`tools/scan_bios_calls.py`](tools/scan_bios_calls.py) | Counts BIOS call references in game program ROMs |
| [`tools/mame_bot_sengoku2.lua`](tools/mame_bot_sengoku2.lua) | MAME play bot for Sengoku 2 (reaches level 2, card save/load) |
| [`tools/hidden_programs_test.py`](tools/hidden_programs_test.py) | Builds a test BIOS whose test menu opens the unreferenced controller test and card utility |
| [`tools/mame_trace.lua`](tools/mame_trace.lua), [`tools/mame_coverage.sh`](tools/mame_coverage.sh) | Traced MAME runs (debugger trace through a FIFO) |

The ROM is **not** in the repository (SNK copyright). Put your own dump in `roms/` (git-ignored).

## Building

```
make check    # build/sp-s2.sp1, SHA-1 must be 4f5ed7105b7128794654ce82b51723e16e389543
```

Needs Python 3 with `capstone` and GNU binutils for m68k (`binutils-m68k-linux-gnu`). Details in
[`HOWTO.md`](HOWTO.md).

## Disassembly status

| Level | State |
|---|---|
| L0 source rebuilds the ROM | done: SHA-1 `4f5ed710...` and boot checksum `$4D`; 8,030 instructions, 2 kept as raw words because GNU as would encode them as `moveq` |
| L1 every byte typed | done by the tracer: code 32,338 B, data 22,011 B (text as `.ascii`, ROM pointers as `dc.l label`), free 76,723 B; three numeric tables identified (scaling tables at `$C02000`/`$C03000`, sine table at `$C04000`, tag I); the unreferenced controller test and memory card utility traced from their pointer tables (`tools/hints.txt`) |
| L2 code traced and run | 15 code-pointer tables followed; indirect jumps: `jmp (a6)` at `$C131A8` (return through a6 during the RAM test) and the card utility dispatch (resolved by a hint). MAME, 21 scenarios with 3 games (Sengoku 2: boot, coins and START, hardware test, test-mode items, calendar set, memory card blank/formatted, card utility in a test build, played by a bot to level 2 then save, load and delete; NAM-1975: HOW_TO_PLAY; Magician Lord: start): 4,360 of 9,109 instructions ran (47.9 %); nothing ran outside the static trace. All 8 CARD functions and HOW_TO_PLAY ran. Never run: CREDIT_DOWN and SYSTEM_INT2 (no checked game uses them, table below), the checksum slot, the alternate calendar path |
| L3 names | 157 routines, tables and data blocks named in `symbols/rom_names.csv`: the 17 BIOS call slots and their targets and the 8 CARD functions (all seen running in MAME: C); boot path, system modes and the hand-off to the game, VBlank and SYSTEM_IO, start buttons, credits and their deduction, slot switching, calendar chip (and an alternate calendar path, never run), test mode, hardware test, the unreferenced controller test and memory card utility, the most-called helpers (C from code reading, MAME screens and coverage); some I. 1,424 automatic labels left |
| L4 RAM and registers | no raw RAM, register or cartridge-header operand left; `x(a5)` written `(NAME-A5_BASE,a5)`; backup RAM through a4 = `$D08000` written `(NAME-A4_BASE,a4)` where a4 is proven (30 accesses left raw where a4 cannot be proven). 216 RAM addresses used: 47 named (W/C/I), 169 automatic; 4 `move.l #$100000` left as numbers (start of work RAM used as the card buffer); 18 cartridge header fields named |
| L5 editable tree | done: 14 modules (`symbols/modules.csv`), no numeric ROM address left, free space as `.org`. Relocation proven in MAME (`tools/relocation_test.py`): with two NOPs at `Reset` and a new routine called from `TestMenu`, 38,961 bytes move and the BIOS still boots, plays the boot animation, starts Sengoku 2, runs the test menu (with the new line) and the hardware test |
| L6 understanding | started: boot sequence and every test-mode screen captured in MAME; screen texts match the ROM text tables (for example book keeping "CABINET/COIN" at `$C1AEB2`); routines not linked to screens yet |

## Sources

- NeoGeoDev wiki: [System ROM](https://wiki.neogeodev.org/index.php/System_ROM), [BIOS calls](https://wiki.neogeodev.org/index.php/BIOS_calls),
  [Memory mapped registers](https://wiki.neogeodev.org/index.php/Memory_mapped_registers), [68k ASM defines](https://wiki.neogeodev.org/index.php/68k_ASM_defines),
  [BIOS RAM locations](https://wiki.neogeodev.org/index.php?title=BIOS_RAM_locations), [Boot process](https://wiki.neogeodev.org/index.php/Boot_process).
- [MAME `neogeo.cpp`](https://github.com/mamedev/mame/blob/master/src/mame/snk/neogeo.cpp): ROM hashes and board notes.
- [Capstone](https://www.capstone-engine.org/) (disassembly) and GNU binutils (assembly).
- Method from the [Game Boy Printer](https://github.com/Raphael-Boichot/Game-Boy-Printer-disassembly) and
  [Game Boy Camera](https://github.com/Raphael-Boichot/Game-Boy-Camera-disassembly) disassemblies (levels L0-L6, C / I / ? tags).

## Licence

The tools, labels, comments and documents are GPLv3 (`LICENSE`). The ROM contents, and so the
instructions and data in `src/sp-s2.s`, remain SNK's: they are not covered by that licence.
