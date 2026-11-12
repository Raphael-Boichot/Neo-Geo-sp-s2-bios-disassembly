# How to build, regenerate and modify the SP-S2 system ROM

## 1. Requirements

- Python 3 with Capstone: `pip install capstone`
- GNU binutils for the 68000: `sudo apt install binutils-m68k-linux-gnu`
  (provides `m68k-linux-gnu-as`, `-ld`, `-objdump`)
- `make` (optional: the commands below can be typed by hand)
- For running a build: MAME (`neogeo` driver). For hardware: a 27C1024 EPROM or a flash adapter.

## 2. Check the build (no ROM needed)

```
make check
```

This assembles `src/sp-s2.s`, links it at `$C00000`, swaps the bytes into MAME order
(`build/sp-s2.sp1`) and prints `OK sha1 4f5ed7105b7128794654ce82b51723e16e389543`, then the
boot checksum (`stored $4D $4D, computed $4D`).

By hand:

```
m68k-linux-gnu-as -m68000 --register-prefix-optional -I src -o build/sp-s2.o src/sp-s2.s
m68k-linux-gnu-ld -Ttext=0xC00000 -e 0xC00402 --oformat binary -o build/sp-s2.bin build/sp-s2.o
python3 tools/romtool.py swap build/sp-s2.bin build/sp-s2.sp1
python3 tools/romtool.py check build/sp-s2.sp1 4f5ed7105b7128794654ce82b51723e16e389543
```

`build/sp-s2.lst` is the assembler listing (address and bytes of every line).

## 3. Regenerate the source from the ROM

Put your own dump, MAME order, in `roms/sp-s2.sp1` (the folder is git-ignored), then:

```
make source        # OVERWRITES src/sp-s2.s and src/neogeo.inc
python3 tools/stats.py roms/sp-s2.sp1
```

`gen_source.py` traces the code, writes the source and loops (assemble, compare) until the image is
identical; it prints the instructions it had to keep as raw words. `stats.py` prints the counts used in
the README level table.

Use regeneration while the tracer or the naming changes. Once hand comments and module splits start in
`src/`, regeneration must stop overwriting them (L5): from then on the source is edited directly and
`make check` is the guard.

## 4. Correct the trace

Add lines to `tools/hints.txt`, each with the reason in a comment:

```
entry     $C1xxxx   ; reached through a RAM pointer set at $C1yyyy
noreturn  $C1xxxx   ; ends with jmp to the reset code
longtable $C1xxxx   ; 6 code pointers read by movea.l at $C1yyyy
```

Then `make source` and `make check`.

## 5. Names

- All names are in `symbols/*.csv` (`addr,name,tag,note`, address in hex): `rom_names.csv` (ROM labels),
  `ram.csv` (work and backup RAM), `registers.csv`, `cart_header.csv` (cartridge program header fields).
  Tags: W (NeoGeoDev wiki), C (read in the code or seen in MAME), I (inferred), ? (doubt).
  `tools/symbols.py` refuses duplicate addresses or names and unknown tags.
- `make source` applies them: `src/neogeo.inc` (registers, header, `A5_BASE`) and `src/ram.inc`
  (every RAM address used; unnamed ones as `ram_XXXXXX` / `bram_XXXXXX`) are generated.
- Everything else keeps an automatic label: `sub_` (called), `loc_` (jumped to), `dat_` (data),
  `tbl_` (pointer table read through `x(pc,dN.w)`), followed by the address.
- A name is added only from reading the code, from a public document or from an emulator run, tagged
  C / I / ?. Names for reused routines can be ported from the other SNK system ROMs where the bytes match.

## 6. Modify the BIOS

1. Put new code in a free block, e.g. just before `.org 0x11000,0xFF` (the 52,480-byte gap at
   `$C04300`). Free space is written as `.org <next block>,0xFF`, so added code uses it up and the
   next block stays in place; the assembler stops if a block overflows. Code can also be inserted in
   the middle of the main code: everything is symbolic, and `tools/relocation_test.py` shows a build
   where 38,961 bytes moved and everything still runs in MAME (C).
2. Hook it: change a `jmp` in the BIOS call table or a `jsr` in the code to your label. Keep every
   BIOS call slot at its address: games call `$C00402-$C004DA` directly.
3. `make fixsum`: rewrites the checksum bytes `$C00080/$C00081`, otherwise the BIOS stops at boot with
   "SYSTEM ROM ERROR".
4. Run it in MAME: replace `sp-s2.sp1` in a copy of `neogeo.zip` and start a game with `-bios euro`.
   MAME prints `sp-s2.sp1 WRONG CHECKSUMS` and still runs it (C: MAME 0.264). Example:
   `python3 tools/relocation_test.py build/reloc` builds `build/reloc/sp-s2.sp1`.
5. Hardware: program `build/sp-s2.sp1` into a 27C1024 (byte order as on disk, already MAME/EPROM order)
   for socketed boards, or a flash adapter. Use a fast part (100 ns or better advised).

## 7. Screenshots in MAME (headless)

MAME 0.264 runs the BIOS without a screen; `tools/mame_run.lua` saves PNG frames. The BIOS set
(`neogeo.zip`, with a rebuilt `sp-s2.sp1` in it to test a build) and a game set you own go in a
ROM folder outside the repository:

```
mame <game> -bios euro -rompath mame/roms -cfg_directory mame/cfg_run1 -nvram_directory mame/nv_run1 \
     -snapshot_directory mame/snap -video none -sound none -nothrottle -skip_gameinfo \
     -autoboot_script tools/mame_run.lua
```

with, in the environment:

| Variables | Result |
|---|---|
| `MODE=boot LAST=1500 STEP=30` | boot sequence (`docs/boot_sequence.png`) |
| `MODE=dip LAST=800 STEP=40` | test mode main menu ("Setting Mode" DIP on) |
| `MODE=dip KEYS="420:P1 Down,440:P1 Down,460:P1 A"` | opens the third menu item (`docs/test_mode.png`) |
| `MODE=dip LAST=2400 KEYS="440:P1 A,600:1 Player Start,900:1 Player Start,..."` | hardware test, START steps to the next screen (`docs/hardware_test.png`) |

Give every run its own `-cfg_directory`: MAME saves the DIP switches there, and a later "normal" run
would start in test mode again. Without a cartridge, SP-S2 stops on a crosshatch after the boot tests
(C: seen in MAME); the boot animation and test mode need a game set.

## 8. Code coverage in MAME

```
MAME=/usr/games/mame MAME_ROMS=mame/roms tools/mame_coverage.sh boot sengoku2 LAST=1500
MAME=/usr/games/mame MAME_ROMS=mame/roms tools/mame_coverage.sh hw sengoku2 MODE=dip LAST=2300 \
     KEYS="440:P1 A,600:1 Player Start,900:1 Player Start,1200:1 Player Start"
python3 tools/coverage.py roms/sp-s2.sp1 coverage/*.txt
```

Each run writes the executed system ROM addresses to `coverage/NAME.txt` (a few KB; the full trace,
about 20,000 lines per frame, only passes through a pipe). `coverage.py` prints the share of traced code
that ran, executed addresses the tracer missed (add them to `tools/hints.txt` with the scenario as the
reason), the speculative entries that ran, and which scenarios use each BIOS call.

## 9. Commit

```
make source && make check && python3 tools/stats.py roms/sp-s2.sp1
git add -A && git commit
```

Update the README level table with the new counts in the same commit.
