# Interrupts and vector tables

Tags: **C** read in the code and run in MAME, **W** public reference (NeoGeoDev wiki), **I** inferred.

## Two vector tables

The 68000 reads its vectors at `$000000`. On the Neo Geo that range shows either the system ROM's
vector table or the cartridge's, chosen by a write to `REG_SWPBIOS` (`$3A0003`: system ROM) or
`REG_SWPROM` (`$3A0013`: cartridge) (W). The system ROM maps its own table for its own screens and
the cartridge's whenever game code runs.

## The system ROM's vector table (`$C00000`)

| Vector | Entry | Target | Tag |
|---|---|---|---|
| 0 | initial SSP | `$10F300` (`BiosWorkRam`: the stack grows down below the BIOS variables) | C |
| 1 | reset | `ENTRY_RESET` `$C00402` -> `Reset` | C |
| 2, 3 | bus error, address error | slots `$C00408`, `$C0040E` | C |
| 4 | illegal instruction | slot `$C00414` | C |
| 8, 9 | privilege violation, trace | slots `$C0041A`, `$C00420` | C |
| 5-7, 10-14, 16-23, 27-31 | zero divide, CHK, TRAPV, line A/F, levels 3-7, reserved | slot `$C00426` | C |
| 15 | uninitialised interrupt | slot `$C0042C` | C |
| 24 | spurious interrupt | slot `$C00432` | C |
| 25 | level 1 | `SYSTEM_INT1` slot -> `SystemInt1` (VBlank) | C |
| 26 | level 2 | `SYSTEM_INT2` slot -> `SystemInt2` (LSPC timer) | C |

Every exception slot (`$C00408-$C00432`) is `jmp Reset`: in this release any exception restarts the
system. A debug monitor with one entry per exception sits unused at `$C16198` (README, Debug
monitor); a development build presumably pointed these slots at it (I).

The table stops after vector 31: `$C00080` holds the checksum byte and `$C00082` the ID text. So
the TRAP vectors (32-47) would read the text: TRAP #0 would jump to `$4D4D4E45`, an odd address,
and end in an address error, then a reset. No system ROM code uses TRAP (I: not run).

## Level 1: VBlank (`SystemInt1`, `$C11646`)

1. Acknowledge (`REG_IRQACK` = 4) and kick the watchdog (`REG_DIPSW` write).
2. Unless `BIOS_INT1_SKIP` is set: save d0-d7/a0-a6, run `MessOut` (the queued fix-layer text and
   VRAM writes) and `SystemIo` (inputs, coins, LEDs, the clock, the test button), clear
   `FrameWaitFlag`, restore the registers.
3. Add 1 to `BIOS_INT1_FRAME_COUNTER`.

`WaitFrame` sets `FrameWaitFlag` and waits until this handler clears it: every system screen runs one
step per VBlank this way. `BIOS_INT1_SKIP` is set only by the power-on calendar test, which counts
VBlanks between two calendar pulses (docs/calendar.md). `BIOS_FRAME_COUNTER` (`$10FE88`, a long) is
counted by `SystemIo` itself (C).

When a game runs, the cartridge's table is mapped and its own VBlank handler runs; the game calls
SYSTEM_IO through the BIOS call table (`$C0044A`) from it.

## Level 2: LSPC timer (`SystemInt2`, `$C118CA`)

Acknowledges (`REG_IRQACK` = 2) and turns the timer interrupt off (`REG_LSPCMODE` = `$4000`). It can
only run when a timer interrupt arrives while the system ROM's vectors are mapped. Of the system
ROM's paths that map them, only HOW_TO_PLAY lowers the interrupt mask without first turning the timer
off; no game checked does that, so SystemInt2 has only run when forced (README, SYSTEM_INT2).

## Who maps which table

| Address | Routine | Maps | Tag |
|---|---|---|---|
| `$C11ADC` | `PowerOnTest` | system ROM | C |
| `$C11F52` | `PowerOnSetup` (after the slot scan) | system ROM | C |
| `$C11FAA` | `SwitchSlot` | cartridge (of the selected slot) | C |
| `$C111FC` | `SystemMode2` | system ROM | C |
| `$C112C2` | `CallUser` (before the game's USER routine) | cartridge | C |
| `$C11300` | `SystemReturn` (the game hands control back) | system ROM | C |
| `$C1151A`, `$C115BA` | `CardStillInserted` | system ROM, then cartridge again | C |
| `$C1823A`, `$C182E0` | the last eyecatcher step (region screens) | system ROM, then cartridge | C |
| `$C18956`, `$C18AC8` | `HowToPlay` | system ROM, then cartridge | C |
| `$C17066` | `HardwareTest` | system ROM | C |
| `$C17CB4` | `HwTestCalendarFrame` (D with a NEO-CLN cartridge) | system ROM | C |
| `$C18F86` | `TestModeEntry` | system ROM | C |
| `$C1B4F0` | `Card1MRecover` | system ROM | C |
| `$C16C12` | `ChecksumLoop` (CHECKSUM_LOOP, never called) | cartridge, to sum its P ROM | C (test build) |
| `$C16C46` | `ChecksumCompare` (unreachable) | cartridge | I |

Most of these first acknowledge every pending interrupt (`REG_IRQACK` = 7) and mask them
(`sr` = `$2700`): `Reset`, `CallUser`, `SystemReturn`, `BootError`, `HardwareTest`, `HowToPlay`,
`TestModeEntry`, `Card1MRecover` and the debug monitor (C).

## Sources

`src/system.s` (`SystemInt1`, `SystemInt2`), `src/header.s` (vectors), `src/boot.s`; NeoGeoDev wiki:
Memory mapped registers (`REG_SWPBIOS`, `REG_SWPROM`, `REG_IRQACK`, `REG_LSPCMODE`), BIOS calls.
