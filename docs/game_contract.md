# What the system ROM expects from a game

The cartridge header, the USER requests, the SYSTEM_RETURN codes, the BIOS calls and the BIOS RAM a
game shares with the system ROM. Tags: **C** read in the code and run in MAME, **W** public
reference (NeoGeoDev wiki), **I** inferred. The names are the wiki's (`symbols/cart_header.csv`,
`symbols/ram.csv`).

## Cartridge header (read by the system ROM)

| Address | Field | Read by | Use |
|---|---|---|---|
| `$000` | `CART_VECTORS` | checksum (system ROM side only), `REG_SWPROM` | the game's own vector table, mapped while the game runs |
| `$100` | `CART_NEOGEO_ID` | `CheckCartridgeId` | NEO-GEO, NEO-CLN or the slot-number ID (docs/boot.md) |
| `$108` | `CART_NGH` | `ScanSlots` | identifies the game in `SlotTable`, the card saves and the book keeping |
| `$10A` | `CART_PROM_SIZE` | `ChecksumLoop` | bytes summed by CHECKSUM_LOOP |
| `$10E`, `$112` | `CART_BACKUP_PTR`, `CART_BACKUP_SIZE` | `SaveGameBackupData`, `NextSlot` | the game's work RAM block kept in backup RAM |
| `$114` | `CART_EYECATCH_FLAG` | `SystemMode1`, `ScanSlots` | 0 system ROM eyecatcher, 1 the game's (USER request 1), 2 none |
| `$115` | `CART_EYECATCH_BANK` | `Eyecatcher` | sprite bank of the NEO-GEO letters in the game's C ROM |
| `$116`, `$11A`, `$11E` | `CART_SOFTDIP_JP/US/EU` | `GetSoftDipPointer`, `RegisterNewGame`, test mode | soft DIP layout for the system ROM's region (`SystemRegion`: SP-S2 is 2, EU) |
| `$122` | `CART_USER` | `CallUser` | entered with a request in `BIOS_USER_REQUEST` |
| `$128` | `CART_PLAYER_START` | `CheckPlayerStart` | called when a START is accepted (docs/credits.md) |
| `$12E` | `CART_DEMO_END` | `DemoEndCheck` | called before the system ROM ends the demo |
| `$134` | `CART_COIN_SOUND` | `PlayCoinSound` | called once per coin while the game runs |
| `$182` | `CART_SECURITY_PTR` | `CheckCartridgeId` | must point at a copy of the 122 bytes `$C146A2-$C1471B` |
| `$186` | `CART_HEADER_186` | `ChecksumLoop` | subtracted from the sum, then overwritten with it |

All C (code; each routine has run in MAME except `ChecksumLoop`, which only ran in a test build).

## USER requests (`BIOS_USER_REQUEST`)

| Request | From | Meaning | `BIOS_USER_MODE` |
|---|---|---|---|
| 0 | `SystemMode0` | init: the first time this game is seen in this slot; the game sets its defaults in its backup block | 0 |
| 1 | `SystemMode1` | the game's own eyecatcher (`CART_EYECATCH_FLAG` 1) | 0 |
| 2 | `SystemMode2` | demo | 1 |
| 3 | `SystemMode2` | title: credits in and GAME START COMPULSION on | 1 |

The game reports its state in `BIOS_USER_MODE` (wiki: 0 init/boot, 1 title or demo, 2 game) and its
players in `BIOS_PLAYER_MOD1-4`. While `BIOS_USER_MODE` is 1 the system ROM watches the start
buttons and SELECT; while it is not 0, a START is handled for the game (docs/credits.md) (C).

## SYSTEM_RETURN (`SystemReturn`, `$C112D2`)

The game jumps to `SYSTEM_RETURN` (`$C00444`) with a code in `BIOS_SYSRET_STATUS`. The system ROM
turns the timer off, waits a frame, maps its vectors, clears the palettes and the fix layer and the
sprites, runs `ControllerSetup`, and then the handler for the code (`SystemReturnModes`, `$C1137A`).
The handler leaves the status for the next `SystemModeDispatch` pass (docs/boot.md):

| Code | Set by | Handler | Next status |
|---|---|---|---|
| 0 | the game, after init | saves the soft DIPs and backup block, next slot to initialise (`BookSlot` + 1); after the last one `CheckSettingMode` | 0, then 1 or 2 |
| 1 | the game, after its eyecatcher | `LoadCurrentSlot`: the game's backup block and soft DIPs loaded | 2 |
| 2 | the game, demo over | backup block saved, `NextSlot` (the eyecatcher again when the next slot is `EyecatchSlot`) | 2 or 1 |
| 3 | `CheckPlayerStart` / `CreditDown` on a start; the game returns with it at game over | `BIOS_TITLE_MODE` cleared, play time added to the book keeping, backup block saved, start compulsion timer reloaded when credits are left, YOUR CARD IS STILL INSERTED when a card is in | 2 |
| 4 | `DemoEndCheck` (SELECT P1, compulsion timeout) | backup block saved, `NextSlot` | 2 |
| 5 | `DemoEndCheck` (SELECT P2) | backup block saved, `PreviousSlot` | 2 |
| 6 | `DemoEndCheck` (first credit, compulsion on) | nothing | 2 (then request 3, the title) |

C for 0-4 and 6 (MAME); 5 C for the code, not run (`PreviousSlot` needs two games, doubts.csv).

## BIOS calls

Jump slots at `$C00402-$C004D9`; the 11 slots `$C00480-$C004BC` lead to an `rts` (`$C004DA`).

| Slot | Call | Routine | Page |
|---|---|---|---|
| `$C00402` | ENTRY_RESET | `Reset` | docs/boot.md |
| `$C00438` | SYSTEM_INT1 | `SystemInt1` | docs/interrupts.md |
| `$C0043E` | SYSTEM_INT2 | `SystemInt2` | docs/interrupts.md |
| `$C00444` | SYSTEM_RETURN | `SystemReturn` | above |
| `$C0044A` | SYSTEM_IO | `SystemIo` | docs/credits.md |
| `$C00450` | CREDIT_CHECK | `CreditCheck` | docs/credits.md |
| `$C00456` | CREDIT_DOWN | `CreditDown` | docs/credits.md |
| `$C0045C` | READ_CALENDAR | `ReadCalendar` | docs/calendar.md |
| `$C00462` | SETUP_CALENDAR | `SetupCalendar` | docs/calendar.md |
| `$C00468` | CARD | `Card` | docs/memory_card.md |
| `$C0046E` | CARD_ERROR | `CardError` | docs/memory_card.md |
| `$C00474` | HOW_TO_PLAY | `HowToPlay` | README, BIOS calls used by games |
| `$C0047A` | CHECKSUM_LOOP | `ChecksumLoop` | below |
| `$C004C2` | FIX_CLEAR | `FixClear` | |
| `$C004C8` | LSP_1ST | `LspFirst` (clear the sprites) | |
| `$C004CE` | MESS_OUT | `MessOut` (fix layer command lists from `BIOS_MESS_POINT`) | |
| `$C004D4` | CONTROLLER_SETUP | `ControllerSetup` | |

Which calls 29 games use: README, BIOS calls used by games.

**CHECKSUM_LOOP** (`ChecksumLoop`, `$C16C0E`): adds every byte of the P ROM (`CART_PROM_SIZE`),
subtracts the header byte `$186`, writes the sum to `$186` and to the start of work RAM, then loops
forever. No checked game calls it (C: forced in a test build). A second routine that compares instead
(`ChecksumCompare`) is never reached (I).

## Soft DIPs

The layout in the cartridge (wiki: 16-byte name, two time settings, two count settings, then option
bytes whose high nibble is the default and low nibble the number of choices, then 12-byte texts).

- On the first init of a game, `LoadGameSoftDips` (`$C11612`) copies the 6 bytes of times and
  counts to `BIOS_GAME_DIP`, then the default nibble of 12 option bytes. The wiki layout has 10
  option bytes, so the last two copies are of text bytes and land on `BIOS_P1STATUS`/`BIOS_P1PREVIOUS`
  (`$10FD94-$10FD95`), which `SystemIo` rewrites at the next frame (C for the copy; I that it is
  harmless).
- After the init, `SaveGameSoftDips` keeps the 16 bytes of `BIOS_GAME_DIP` in `GameSoftDips` (16 per
  game index); `NextSlot` and `LoadCurrentSlot` copy them back before each game runs. The test mode's
  SOFT DIP screen edits them (docs/test_mode.md).
- One game is patched: when `NextSlot` loads the game whose `SlotTable` NGH is `$0005` (Magician
  Lord) and the cabinet's DEMO SOUND is WITHOUT (`DemoSoundOff`), the first option byte
  (`BIOS_GAME_DIP_06`) is set to 1. Magician Lord's first option is its own DEMO SOUND, 1 = OFF (its
  soft DIP block, NGH 0005). So the cabinet setting silences this game, which would otherwise ignore
  it (C for the code and the layout; not run in MAME).

## Backup data

`CART_BACKUP_SIZE` bytes from `CART_BACKUP_PTR` are copied to backup RAM at `GameBackupData`
(`$D00320`) + game index x `$1000` by `SaveGameBackupData` (after init, demo, game over and slot
changes) and back by `NextSlot` / `LoadCurrentSlot` before the game runs (C). The game index is the
settings index in `SlotTable` (0-7), given by `RegisterNewGame`.

## BIOS RAM shared with games

| Range | Names | Written by | Tag |
|---|---|---|---|
| `$10FD80-$10FD83` | `BIOS_SYSTEM_MODE`, `BIOS_SYSRET_STATUS`, `BIOS_MVS_FLAG`, `BIOS_COUNTRY_CODE` | system ROM; the game writes `BIOS_SYSRET_STATUS` before SYSTEM_RETURN | W, C |
| `$10FD84-$10FD93` | `BIOS_GAME_DIP` | system ROM | W, C |
| `$10FD94-$10FDAD` | `BIOS_P1STATUS`.. `BIOS_P4STATUS`, `BIOS_STATCURNT`, `BIOS_STATCHANGE` | `SystemIo` | W, C |
| `$10FDAE-$10FDAF` | `BIOS_USER_REQUEST`, `BIOS_USER_MODE` | system ROM / game | W, C |
| `$10FDB0-$10FDB3` | `BIOS_CREDIT_DEC1-4` | game (CREDIT_CHECK, CREDIT_DOWN) | W, C |
| `$10FDB4` | `BIOS_START_FLAG` | system ROM; `CART_PLAYER_START` may clear bits | W, C |
| `$10FDB6-$10FDB9` | `BIOS_PLAYER_MOD1-4` | game | W, C |
| `$10FDBE-$10FDC2` | `BIOS_MESS_POINT`, `BIOS_MESS_BUSY` | game (MESS_OUT) | W, C |
| `$10FDC4-$10FDD1` | `BIOS_CRDF`.. `BIOS_CRDFILE` | game (CARD) | W, C |
| `$10FDD2-$10FDD8` | `BIOS_YEAR`.. `BIOS_SECOND` | READ_CALENDAR | W, C |
| `$10FDDA-$10FDDB` | `BIOS_SELECT_TIMER`, `BIOS_COMPULSION_FRAME_TIMER` | system ROM | W, C |
| `$10FEC5` | `BIOS_TITLE_MODE` | game (title) | W, C |

Everything else from `$10F300` up is the system ROM's own work area (`symbols/ram.csv`,
`symbols/ram_scoped.csv`).

## Sources

`src/boot.s`, `src/power_on.s`, `src/system.s`, `src/header.s`; NeoGeoDev wiki: 68k program header,
BIOS calls, BIOS RAM locations, Software DIPs; MAME Magician Lord set (`maglord`, NGH 005), soft DIP
block at `$7096` of its P ROM.
