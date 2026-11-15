# Boot

From reset to the first game. Tags: **C** read in the code and run in MAME, **W** public reference
(NeoGeoDev wiki), **I** inferred.

## 1. Reset (`Reset`, `$C11002`)

The reset vector and the `ENTRY_RESET` slot both lead here. Interrupts masked (`sr` = `$2700`), the
watchdog kicked (`REG_DIPSW` write), every interrupt acknowledged (`REG_IRQACK` = 7), the LSPC timer
off (`REG_LSPCMODE` = `$4000`), `a5` = `BiosWorkRam` (the base of every `-A5_BASE` access), then
`PowerOnTest` (C).

## 2. Power-on tests (`PowerOnTest`, `$C11A84`)

In this order (error numbers in the README, Boot errors):

1. The three LED latches (`$F7`, `$EF`, `$DF`) pulsed with every segment off.
2. System ROM vectors and board fix layer mapped (`REG_SWPBIOS`, `REG_BRDFIX`); both coin
   lockouts reset (`REG_RESETCL1`, `REG_RESETCL2`).
3. Work RAM (error 0), backup RAM (1: tested and cleared only when `BackupRamSignature` is not
   BACKUP RAM OK !, so the settings survive a normal boot), palette banks 1 and 0 (2, 3), video RAM
   (4: `$0000-$7FFF`, then `$8000-$85FF`).
4. All hard DIP switches on (`REG_DIPSW` = 0): WORK RAM TEST, the work and backup RAM tests in a loop
   until a switch is turned off, then the backup RAM is cleared (`WorkRamTestLoop`).
5. Calendar: 57-63 VBlanks between two 1-second pulses, otherwise error 5 (docs/calendar.md).
6. System ROM checksum (error 6): the byte sum of the 128 bytes of the vector table and of
   `$C00082-$C1FFFF` must equal `SystemRomChecksum` (`$C00080`; the two bytes `$C00080-$C00081` are
   not summed). It runs only while the bus error slot still holds `jmp Reset`
   (`cmpi.l #Reset,(loc_C00408+2)`): a build whose exception slots point elsewhere, such as at the
   debug monitor, skips it (C for the code; I that this was meant for development builds).
7. Memory card: CARD function 5 (read a title). Only a 2 KB card that answers $81 (not formatted)
   is RAM-tested: `$55`, `$AA`, then the address over 2K words at `$800000`, error 7 on a mismatch.
   A formatted card or no card goes on untouched (C).

A failed test ends in `BootError` (`$C16ADA`), which never returns.

## 3. Setup (`PowerOnSetup`, `$C11DB0`)

1. Clears the per-boot fields in backup RAM (slot-number mode, play time, coin inputs, coin
   counts) and marks no NEO-CLN slot.
2. `ReadCalendar`; the time starts the software clock (`HourClockTick`). On a date other than
   `LastBootDate`: the day ring (36 records) advances and today's CABINET/PLAY and COIN records are
   cleared and dated; on a new month the month records too (C: MAME, `book_days_*`).
3. Slot count: 2 when `REG_SYSTYPE` bit 6 is 0, else 6 when `REG_STATUS_A` bit 5 is 1, else 4
   (`SlotCount`).
4. `Z80Check`: sound command 1 and a wait for the reply 1, otherwise error 8.
5. `ScanSlots`: each slot is selected and `CheckCartridgeId` run (below); the NGH numbers go to
   `ScanSlotTable`, and `EyecatchSlot` gets the first slot whose cartridge leaves the eyecatcher to
   the system ROM.
6. The scan is merged with the stored `SlotTable` (duplicates cleared, removed games listed, moved
   games keep their settings, new games dated), and on a new day each game's own day ring advances
   (`BookNewDayPerGame`).
7. Backup RAM locked, board fix and system ROM vectors mapped again.

### Cartridge ID (`CheckCartridgeId`, `$C12FFA`)

| `CART_NEOGEO_ID` | Result | Tag |
|---|---|---|
| NEO-GEO | a game, when the code at `CART_SECURITY_PTR` (an even address) equals the 122 bytes `$C146A2-$C1471B` of the system ROM | C |
| NEO-CLN | a cartridge with its own calendar: its date goes to the board calendar and the boot goes to `HardwareTest` on the calendar screen (README, NEO-CLN cartridges) | C (patched header) |
| `N 0 O 0 G 0 O 0` | a game, and slot-number mode: SLOT n instead of the eyecatcher, duplicates kept | C (patched header) |
| anything else | empty slot | C |

## 4. No game in any slot

If every `SlotTable` entry is 0: with the service switch held (`REG_STATUS_A` bit 2 = 0) and a 1M
card holding cabinet backups, `Card1MRecover` (README, 1M memory card); otherwise `HardwareTest`,
the test mode's hardware test screens (C).

## 5. Start (`ClearRamAndVideo`, `BiosStart`)

`ClearRamAndVideo` (`$C11038`) zeroes the 64 KB of work RAM (so every BIOS RAM variable starts at
0, `BIOS_SYSRET_STATUS` included), both palette banks, the fix layer and the sprite VRAM, then
`LspFirst`. `BIOS_MVS_FLAG` takes `SystemType` (`$C00400`). `BiosStart` points `BIOS_MESS_POINT`
at `MessBuffer`, runs `ControllerSetup` and falls into `SystemModeDispatch` (C).

## 6. System modes (`SystemModeDispatch`, `$C11142`)

Every pass resets the stack to `BiosWorkRam`, clears bit 7 of `BIOS_SYSTEM_MODE` (system ROM in
control) and jumps by `BIOS_SYSRET_STATUS` (the low byte of the word `BIOS_SYSTEM_MODE`):

| Status | Routine | What it does | Tag |
|---|---|---|---|
| 0 | `SystemMode0` | `RegisterNewGame`: the next slot (from `BookSlot`) whose game has no settings index yet gets the lowest free one, its book keeping cleared and its name copied from its soft DIP block; the cartridge's default soft DIPs go to `BIOS_GAME_DIP` (`LoadGameSoftDips`); then USER request 0 (init) | C |
| 1 | `SystemMode1` | `CART_EYECATCH_FLAG` 0: the system ROM's `Eyecatcher`; 1: USER request 1 (the game's own); 2: straight to status 2 | C |
| 2 | `SystemMode2` | slot-number mode only: SLOT n for 300 frames (SELECT P1 ends it). Then USER request 2 (demo), or 3 (title) when there are credits and GAME START COMPULSION is on | C |

`CallUser` (`$C11286`) clears `BIOS_PLAYER_MOD1-4`, sends sound command 3, waits a frame, turns the
timer off, stores the request in `BIOS_USER_REQUEST`, sets bit 7 of `BIOS_SYSTEM_MODE`, maps the
cartridge vectors, locks backup RAM and jumps to `CART_USER` (C).

The first passes therefore initialise every newly inserted game once (status 0, then the SYSTEM_RETURN
handler below saves its data and moves to the next slot). When all are done, `CheckSettingMode`:
hard DIP 1 on opens the test mode; otherwise the eyecatcher (status 1) on `EyecatchSlot`, or, in
slot-number mode or with no such slot, the demo of the next game (status 2) (C: MAME boot of one and of
two slots, `slots_*`).

The game's side of this (requests, SYSTEM_RETURN codes, header fields, soft DIPs) is in
docs/game_contract.md.

## Sources

`src/boot.s`, `src/power_on.s`, `symbols/rom_names.csv`, `symbols/ram.csv`; NeoGeoDev wiki: 68k program
header, BIOS RAM locations, Memory mapped registers (`REG_SYSTYPE`, `REG_STATUS_A`).
