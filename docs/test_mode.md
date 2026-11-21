# Test mode

The MVS operator screens. Tags: **C** read in the code and run in MAME, **W** public reference
(NeoGeoDev wiki), **I** inferred. Every screen and key was run in MAME
(`tools/test_mode_scenarios.py`); pictures and the details of each settings page are in the README
(Screens, Test mode settings).

## Ways in

| How | Where | Tag |
|---|---|---|
| hard DIP 1 (Setting Mode) on, after the first init pass of the games | `CheckSettingMode` (`$C113DE`) | C |
| the board's test button (`REG_SYSTYPE` bit 7, newly pressed), once the init pass is over (`BIOS_SYSRET_STATUS` not 0) | in `SystemIoMvs` at `$C12762` | C |
| no game in any slot at power-on (straight to the hardware test) | in `PowerOnTest` at `$C11D84`, docs/boot.md | C |
| a NEO-CLN cartridge (the hardware test's calendar screen) | `CheckCartridgeId` | C (patched header) |

`TestModeEntry` (`$C18F74`) clears `BIOS_SYSTEM_MODE`, maps the system ROM vectors and board fix,
zeroes the 64 KB of work RAM and both palette banks, sets `TestModeActive` (coins then count as
credits but not in the book keeping), copies `SystemRegion` to `BIOS_COUNTRY_CODE`, forces
`BIOS_MVS_FLAG` to `$80`, and opens `TestMenu`. Since work RAM is cleared, a game interrupted by the test
button is not resumed: EXIT resets the board (C).

## Menu (`TestMenu`, `$C19072`)

Up/Down move, A selects; `TestMenuJumpTable` (`$C19290`), in menu order:

| Item | Routine | Screen |
|---|---|---|
| 1 | `HardwareTest` (`$C17062`) | hardware test, below |
| 2 | `TestHardDip` (`$C196FA`) | SETTING UP THE HARD DIP: SETTING MODE, COMMUNICATION (4 settings), FREE PLAY, STOP MODE (`HardDipRows`); display only |
| 3 | `TestSoftDip` (`$C19B76`) | the cabinet page (`CabinetSettings`) and one line per slot (`SoftDipEditor`) |
| 4 | `TestBookKeeping` (`$C1A74A`) | CABINET/COIN, CABINET/PLAY, one page per game (docs/credits.md, Book keeping) |
| 5 | `TestCodeNumber` (`$C192AC`) | the 4-digit code that ties a board to a 1M card (README, 1M memory card) |
| 6 | `TestCalendar` (`$C1991A`) | SETTING UP THE CALENDAR: D sets the chip (docs/calendar.md) |
| 7 | `TestMenuExit` (`$C196A8`) | DIP-SW 1 OFF !! while hard DIP 1 is on, then `Reset` |

Keys on the settings pages: A and B change a value (held: repeat), Left/Right pick a column or digit,
C goes back (and saves on the soft DIP pages), D sets.

## Hard DIPs and the cartridge link

`HardDipRows` shows four rows. Outside this page and the raw bits of the I/O check screen, the system
ROM reads only these switches:
1 (`CheckSettingMode`), 7 (free play: `StartCreditCheck`, `CreditCheck`, `DeductPlayerCredit`) and 8
(STOP MODE: `SystemIoMvs` holds everything with interrupts off while it is on); 3 (mahjong panel) is
read by `ControllerSetup`; and all eight on together start `WorkRamTestLoop` (C).

| Switch (`REG_DIPSW` bit, 0 = on) | On the page | Read by the system ROM |
|---|---|---|
| 1 (bit 0) | SETTING MODE | `CheckSettingMode` |
| 2 (bit 1) | not shown (the US versions show it as COIN SWITCH 2 / 4; SP-S2 keeps the two texts, `HardDipCoin2Text`, `HardDipCoin4Text`, unused) | no |
| 3 (bit 2) | not shown | `ControllerSetup`: on, `BIOS_P1STATUS` = 3 (mahjong) |
| 4, 5, 6 (bits 3-5) | COMMUNICATION: OFF, or ON [No 1] to ON [No 4] (switch 6 on; 4 and 5 the cabinet number) | no |
| 7 (bit 6) | FREE PLAY | credit code |
| 8 (bit 7) | STOP MODE | `SystemIoMvs` |

The link between boards (NeoGeoDev wiki, Multiplayer and HD6301) is the cartridge's business: League
Bowling, Riding Hero and Thrash Rally carry an HD6301 microcontroller that talks to the other boards
over a serial cable, and the game reads `REG_DIPSW` itself (League Bowling copies it to its RAM every
frame). The system ROM's only link code is the COMMUNICATION row of this page (C: no other read of
bits 3-5 in SP-S2). In MAME 0.264 the page shows the switches (Riding Hero, switch 6 on, cabinet 2):

![SETTING UP THE HARD DIP with COMMUNICATION ON [No 2]](hard_dip_link.png)

MAME 0.264 cannot run a link: its Riding Hero set loads the HD6301 dump (`rhcom.bin`) but the driver
has no HD6301 CPU and no serial connection, so two MAME instances cannot be cabled together (C:
`mame -listxml ridhero` lists the 68000, the Z80 and the YM2610 only).

## Cabinet settings (`CabinetSettings`)

Stored in backup RAM (`symbols/ram.csv`, README Backup RAM map):

| Setting | Variable | Used by |
|---|---|---|
| COIN1, COIN2: coins = credits | `Coin1Coins`, `Coin1Credits`, `Coin2Coins`, `Coin2Credits` | `CountCoin` |
| GAME SELECT: ONLY WHEN CREDITED or FREE | `GameSelectFree` | `DemoEndCheck`: SELECT without credits when FREE |
| GAME START COMPULSION: seconds, 00 = WITHOUT | `StartCompulsionTime`, `NoStartCompulsion` | `SystemMode2`, `CheckPlayerStart`, `DemoEndCheck` |
| DEMO SOUND | `DemoSoundOff` | `NextSlot` (Magician Lord only, docs/game_contract.md) |

The page after the `jmp` to `CabinetSettings` (`CabinetSettingsOld`, `$C19CF6-$C1A105`) is an older
4-row version that nothing reaches (C: no reference).

## Hardware test (`HardwareTest`, `$C17062`)

Seven screens, one draw routine and one per-frame routine each (`HwTestStepTable`, 14 entries);
START goes to the next:

| Screen | Routines | Tag |
|---|---|---|
| crosshatch | `HwTestCrosshatch`, `...Frame` | C |
| colour bars (RED GREEN BLUE WHITE) | `HwTestColorBars`, `...Frame` | C |
| I/O CHECK: inputs, DIP switches, credit LED counters | `HwTestIoCheck`, `...Frame` | C |
| SOUND TEST | `HwTestSound`, `...Frame` | C |
| MEMORY CARD TEST: TEST OK / TEST ERROR | `HwTestMemCard`, `...Frame` | C |
| BACKUP CLEAR: A+B+C clears backup RAM | `HwTestBackupClear`, `...Frame` | C |
| SETTING UP THE CALENDAR (sets the cartridge calendar too with a NEO-CLN) | `HwTestCalendar`, `...Frame` | C |

A NEO-CLN cartridge starts it at the calendar screen (step `$0C`).

## Unreachable in SP-S2

`$C14EA2-$C16197` holds a CONTROLLER TEST (`ControllerTest`) and the MEMORY CARD UTILITY
(`CardUtility`, docs/memory_card.md), the AES boot menus (docs/versions.md); the debug monitor follows
at `$C16198-$C16AA9`. No call, jump or pointer reaches them;
`tools/hidden_programs_test.py` builds a test BIOS whose menu opens them, and both work in MAME (C:
test build).

## Sources

`src/test_mode.s`, `src/hardware_test.s`, `src/boot.s`, `src/power_on.s`; `symbols/rom_names.csv`;
NeoGeoDev wiki: Memory mapped registers (`REG_SYSTYPE`, `REG_DIPSW`), Hardware DIPs, Multiplayer,
HD6301; MAME 0.264 (`ridhero`).
