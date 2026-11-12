# Neo-Geo-sp-s2-Bios-disassembly

Disassembly of the Neo Geo MVS system ROM **SP-S2** (Europe MVS V2, the default BIOS in MAME), with a
source tree that rebuilds the ROM byte for byte. The long-term goal is a custom system ROM built on it.

**Status: L0 done** (2026-11-12): `src/sp-s2.s` assembles to the original ROM (SHA-1 below). Naming has not
started; the BIOS has been run in MAME (screens below, levels in the table).

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

## Contents

| File | What it is |
|---|---|
| [`src/sp-s2.s`](src/sp-s2.s) | Generated 68000 source (GNU as, Motorola syntax), ROM addresses in comments |
| [`src/neogeo.inc`](src/neogeo.inc) | Public register and BIOS RAM names (NeoGeoDev wiki) |
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
| [`docs/`](docs/) | Screenshots of the BIOS running in MAME |

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
| L0 source rebuilds the ROM | done: SHA-1 `4f5ed710...` and boot checksum `$4D`; 8,024 instructions, 2 kept as raw words because GNU as would encode them as `moveq` |
| L1 every byte typed | done by the tracer: code 28,410 B, data 25,939 B (text runs as `.ascii`, 203 ROM pointers as `dc.l label`), free 76,723 B; 18 entries found speculatively, to review |
| L2 code traced and run | traced: 12 code-pointer tables followed, 1 indirect jump left (`jmp (a6)` at `$C131A8`, a return through a6 during the RAM test); runs in MAME 0.264 (boot, test mode, hand-over to a game); code coverage not measured yet |
| L3 names | 17 public names (BIOS calls), 1,373 automatic labels |
| L4 RAM and registers | registers and named BIOS RAM applied to absolute operands; left: 59 code lines with raw `$10xxxx`, 81 raw I/O or backup RAM, 25 absolute short, and 1,185 accesses through `x(a5)` (a5 = `$10F300`) |
| L5 editable tree | one file; no numeric ROM address left in operands (all symbolic); code relocation not tested yet |
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
