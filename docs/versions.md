# What the other SNK system ROMs tell about SP-S2

The other SNK system ROMs are not disassembled here. They are used to understand SP-S2: whether a
routine of SP-S2 is common to every version or special to it, and what the code that SP-S2 never runs
was for. Tags: **C** checked (bytes, references, MAME), **W** public reference, **I** inferred.

## The ROMs compared

All 18 other SNK system ROMs of MAME 0.264's `neogeo.zip` (and its AES set), named by MAME's BIOS
options. `tools/compare_bios.py` traces each one and looks for every named SP-S2 routine (306 of 4
instructions or more), ROM addresses masked; `symbols/other_bios_routines.csv` holds the result.

| File | MAME BIOS | Header: type, region | SP-S2 routines identical / changed / not found |
|---|---|---|---|
| `sp-e.sp1` | US MVS (Ver. 1) | MVS, US | 293 / 5 / 8 |
| `sp-u2.sp1` | US MVS (Ver. 2?) | MVS, US | 289 / 7 / 10 |
| `sp-s.sp1` | Europe MVS (Ver. 1) | MVS, Europe | 280 / 10 / 16 |
| `sp-s3.sp1` | Asia MV1B | MVS, Europe | 270 / 16 / 20 |
| `sp1-u4.bin` | US MVS (U4) | MVS, US | 269 / 13 / 24 |
| `sp1-u3.bin` | US MVS (U3) | MVS, US | 266 / 14 / 26 |
| `sp1-u2` | US MVS (4 slot, Ver 2) | MVS, US | 265 / 15 / 26 |
| `sp-j2.sp1` | Japan MVS (Ver. 2) | MVS, Japan | 253 / 35 / 18 |
| `sp-45.sp1` | Asia NEO-MVH MV1C | MVS, Europe | 250 / 21 / 35 |
| `sp1.jipan.1024` | Japan MVS (Ver. 1) | MVS, Japan | 237 / 36 / 33 |
| `sp-j3.sp1` | Japan NEO-MVH MV1C | MVS, Japan | 234 / 36 / 36 |
| `sp1-j3.bin` | Japan MVS (J3, alt) | MVS, Japan | 233 / 38 / 35 |
| `vs-bios.rom` | Japan MVS (Ver. 3) | MVS, Japan | 226 / 40 / 40 |
| `sp-1v1_3db8c.bin` | Custom Japanese Hotel | MVS, Japan | 223 / 47 / 36 |
| `japan-j3.bin` | Japan MV1B | MVS, Japan | 217 / 41 / 48 |
| `neo-epo.bin` | AES Asia | AES, Europe | 211 / 7 / 88 |
| `neo-po.bin` | AES Japan | AES, Japan | 168 / 34 / 104 |
| `neodebug.bin` | AES Development System ROM | AES, Japan | 160 / 42 / 104 |

"Changed" is a match of 0.8 to 0.99 (some instructions differ); "not found" includes routines that
were rewritten. SP-S2 is closest to the first US and European MVS versions. The MV1B and MV1C
versions start their code at `$C10000` instead of `$C11000`.

## Findings about SP-S2

**The hidden programs are the AES boot menus (C).** `ControllerTest` and `CardUtility` are referenced
by no MVS ROM, SP-S2 included, but every AES ROM jumps to them from its start-up code: A+B+C+D held
on controller 1 opens the memory card utility, on controller 2 the controller test. Seen in MAME (AES,
Japan BIOS, A-D held from power-on):

![AES: A-D held on P1 (card utility, Japanese), on P2 (controller test), and nothing held](aes_hidden_programs.png)

So SP-S2 carries the AES menus in code shared by all versions, with no way in on an MVS.

**The debug monitor is the exception handler of two versions (C).** The exception slots of the
Development System ROM and of the Custom Japanese Hotel ROM jump into the monitor
(`MonitorEntry`, `MonitorAddressError`, `MonitorIllegal`, ...); in every other ROM, SP-S2 included,
they jump to `Reset`. Those two are also the only ROMs where the bus error slot is not `jmp Reset`, so
they skip the system ROM checksum test: the test in `PowerOnTest` that looks at that slot was meant
for monitor builds (docs/boot.md). MAME's AES development set has a jumper input named "Short JP1
(Debug Monitor)".

**`ScaleTableA`, `ScaleTableB` and `AbsSineTable` are for the games (C).** The three tables are
byte for byte the same at `$C02000`, `$C03000` and `$C04000` in all 19 ROMs, even in the versions
whose code moved, and no system ROM reads them. 15 of the 29 games of this project load them with
`lea $C02000` / `$C03000` / `$C04000` (`$C04200` too); in MAME Sengoku 2 read them 6,457, 6,457 and
2,537 times in its first 2,400 frames. They are a service of the system ROM at fixed addresses, like
the BIOS calls.

**Leftovers common to every version (C).** `CardFillTest`, `ChecksumCompare`, the debug monitor
routines and the six `HwCalendarFixAddresses` words exist in every ROM and nothing refers to them
outside the two monitor ROMs. `CabinetSettingsOld` is unreferenced everywhere except by one long
pointer in the development ROM (`$C184A4` there; not followed).

**`SystemIoBuildFlag` is an MVS switch that never switches (C for the code, I for the purpose).**
Every MVS version has the same `tst.w` of a word `$0001` followed by a `bne` to the next instruction;
the AES and development versions have no such test. The later Japanese and MV1B/MV1C versions add a
call before it.

**The Magician Lord patch is in every MVS version (C).** The test of NGH `$0005` with the cabinet's
DEMO SOUND (`NextSlot`, docs/game_contract.md) is in all 15 MVS ROMs, and in none of the AES ROMs,
which have no cabinet settings.

**Unchanged in every version (C).** `LoadGameSoftDips` copies 12 option nibbles in all 18 other ROMs
too: not an SP-S2 slip. The word `CardFormat` writes as the card format version is `$0000` at the
start of the code in every version. `HowToPlayFlag` is only ever cleared, `Card1MRecoverFlag` only
ever written, and `Credits2` is read by the LED code and written by no SNK system ROM.

## How to redo it

    python3 tools/compare_bios.py <other ROMs...> --csv out.csv     every named routine
    python3 tools/compare_bios.py --name SystemIo <other ROMs...>    one routine, differences listed

## Sources

MAME 0.264 BIOS list (`mame -listbios neogeo`, `aes`) and its ROM dumps; NeoGeoDev wiki: System ROM
(header bytes `$400`/`$401`); the game program ROMs of the project's MAME sets.
