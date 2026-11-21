# Written reference

One page per subsystem of the SP-S2 system ROM, from the code (`src/`, `symbols/`) and the MAME runs.
Tags on every claim: **C** read in the code and run in MAME, **W** public reference (NeoGeoDev wiki,
data sheets), **I** inferred.

| Page | Subject |
|---|---|
| [boot.md](boot.md) | Reset, power-on tests, setup and slot scan, cartridge ID, system modes 0-2, hand-off to the game |
| [game_contract.md](game_contract.md) | Cartridge header fields, USER requests, SYSTEM_RETURN codes, BIOS calls, soft DIPs, backup data, BIOS RAM shared with games |
| [credits.md](credits.md) | Coins, credits, START handling, start compulsion, CREDIT_CHECK / CREDIT_DOWN, book keeping of a play, demo end |
| [calendar.md](calendar.md) | uPD4990A lines and commands, READ_CALENDAR, SETUP_CALENDAR, weekday, power-on calendar test, NEO-CLN |
| [memory_card.md](memory_card.md) | Card kinds, layout, CARD functions and results, CARD_ERROR, the hidden card utility |
| [test_mode.md](test_mode.md) | Ways in, menu, hard DIPs and the cartridge link, cabinet settings, hardware test, unreachable programs |
| [interrupts.md](interrupts.md) | Vector tables, VBlank and timer handlers, who maps which table |
| [sound.md](sound.md) | The 68000/Z80 channel, when the board's `sm1.sm1` runs, every sound command SP-S2 sends and what `sm1.sm1` does with it |
| [versions.md](versions.md) | What the 18 other SNK system ROMs tell about SP-S2: shared and special routines, the AES menus, the monitor builds, the tables for games, every unused part of SP-S2 |
| [bios_set.md](bios_set.md) | The four ROMs of the MVS board (system ROM, `sfix.sfix`, `sm1.sm1`, `000-lo.lo`): what each holds, which chip reads it, the shrink table rule |

Boot errors, the debug monitor, the 1M card cabinet backup, the eyecatcher assets, the board fix ROM
and the backup RAM map are in the top-level README.
