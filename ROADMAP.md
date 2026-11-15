# Roadmap

Where the SP-S2 disassembly stands and what comes next, in order. The priority is the disassembly itself:
full coverage, names and a written reference. Levels L0-L6 are defined in
`SKILL.md`; the measured counts come from `tools/stats.py` and `tools/coverage.py` (2026-11-15).

## Where we are

| Level | State |
|---|---|
| L0 rebuild | done: byte-identical, boot checksum `$4D` |
| L1 every byte typed | done: code 32,966 B, data 21,383 B, free 76,723 B |
| L2 traced and run | 9,252 instructions traced; 7,354 ran in MAME (79.5 %) over 77 scenarios, 6,541 without the forced ones; nothing ran outside the trace |
| L3 names | 574 names (C 476, I 67, W 31); 1,039 automatic labels left, all `loc_` |
| L4 RAM and registers | 225 RAM addresses used, 95 named; 30 backup RAM accesses through a4 left raw |
| L5 editable tree | done: 14 modules, all ROM addresses symbolic, relocation proven in MAME; the board fix ROM `sfix.sfix` rebuilt from 16 tile sheets (`gfx/sfix/`) |
| L6 understanding | started: screens, settings and BIOS calls seen in MAME; no written reference yet |

Coverage and automatic routines by module:

| Module | Ran in MAME | `sub_` left |
|---|---|---|
| `test_mode.s` | 90 % (2,061 / 2,294; 219 of the rest is the unreachable `CabinetSettingsOld`) | 0 |
| `card.s` (card utility, card errors, debug monitor) | 60 % (1,912 / 3,168) | 0 |
| `boot_error.s` | 86 % (76 / 88, forced) | 0 |
| `system.s` | 61 % | 0 |
| `calendar.s` | 98 % | 0 |
| `video_io.s` | 83 % | 0 |
| `power_on.s` | 93 % | 0 |
| `eyecatcher.s` | 96 % | 0 |
| `boot.s` | 95 % | 0 |
| `hardware_test.s` | 90 % | 0 |
| `how_to_play.s` | 90 % | 0 |

## 1. Test mode coverage (L2): done

`tools/test_mode_scenarios.py` drives every screen (18 scenarios, 7 games and no cartridge).

- [x] Hard DIP (switches changed while shown) and soft DIP: every row type (times, counts, lists),
      both pages, wraps, save; Sengoku 2, Riding Hero, Top Player's Golf, Alpha Mission II
- [x] Cabinet settings: both coin rates, game select, start compulsion, demo sound
- [x] Book keeping: CABINET/COIN, CABINET/PLAY, a game, every page, with played data
- [x] Calendar: every field both ways, set
- [x] Code number: every digit, no card, blank card, game card, 1M card (emulated)
- [x] EXIT with the Setting Mode DIP on, then off
- [x] The 1M card cabinet backup: format, save from two boards, recover (`card1m_*`)
- [ ] Book keeping with data on more than one day and month (needs the calendar moved between plays)

Not reachable: `CabinetSettingsOld` (`$C19CF6-$C1A105`), an older cabinet page after a `jmp`.

## 2. Error and rare paths (L2): done

Paths that need a fault, reached with `DEBUG_CMDS` breakpoints that fake the condition or with test
builds; `tools/fault_scenarios.py` (30 scenarios) says which runs are forced.

- [x] Boot error screens (`BootError`, `$C16ADA`): work RAM, backup RAM, both palette banks, video RAM,
      calendar, system ROM, memory card, Z80, and the AES colour form (forced, `boot_error_*`)
- [x] The checksum slot `CHECKSUM_LOOP` (`$C0047A` -> `$C16C0E`): nothing calls it; from a test build it
      sums the P ROM, stores the sum at `$100000` and waits for the watchdog (`checksum_loop`).
      `ChecksumCompare` (`$C16C42`) is still unreached
- [x] The work RAM test loop when every hard DIP is on (`WorkRamTestLoop`, `$C11BA8`, not forced)
- [x] The debug monitor (`$C16198-$C16AA9`, found in this step): every command, five exception types,
      from a test build (`monitor_*`). Not run: MONITOR ENTRY, uninitialised and spurious interrupt entries
- [x] The alternate calendar path (`$C12DB8-$C12EF0`): selected by a cartridge whose ID reads NEO-CLN
      (`CheckCartridgeId`); run in MAME with `tools/neo_cln_test.py` (scenario `neo_cln_cartridge`)
- [x] The `NoGoIdText` case of `CheckCartridgeId`: sets `SlotNumberMode` (`$D00060`): SLOT n before the game,
      no jump to the saved slot, duplicates kept, SELECT ends the demo without credits; run in MAME
      (`tools/neo_cln_test.py --nogo`, scenario `nogo_cartridge`)
- [x] `BackupRamTest` (`$C125C8`): a cleared `BackupRamSignature` makes the next boot run `ClearBackupRam`
      (all backup RAM zeroed, defaults written); seen in MAME with five boots sharing one nvram
- [x] Card error cases: blank card (League Bowling: CARD_ERROR formats it), write-protected card (League
      Bowling and the card utility); what 29 games do with a blank card
- [x] Card error: the full card (`CardErrorFull`): reached with `CardFillTest` (`$C132B4`), an unreferenced
      loop that fills the card, found typed as data and run from a test build (`card_full_*`)
- [x] Card utility COPY (`CardUtilCopy`) with two cards, the same card and an unformatted target, and the
      controller test, as coverage scenarios of the hidden-programs build
- [x] CREDIT_DOWN in Top Player's Golf and Baseball Stars Professional: only with the US country code
      (forced); Blue's Journey: its wrapper has no caller

## 3. Names (L3)

- [x] Every `sub_` named (0 left; 2026-11-15: card file system for the three card types, card utility
      helpers, slot scan and slot table merge, coins, software clock, controller reading, MESS_OUT
      commands, hardware test and eyecatcher helpers)
  - [x] `system.s`: CreditCheckPlayer, CallDeductStartCredits, DemoEndCheck
  - [x] `boot.s`: CardStillInserted, GetSoftDipPointer (with SystemType, SystemRegion and the two texts)
  - [x] `calendar.s`: RtcReadBits, RtcReadBitsAlt, CheckCartridgeId (and the three ID texts)
  - [x] `test_mode.s`: all 92 routines, tables and texts, `CodeNumberDraw` renamed (it was `TestCodeNumberCard`)
- [x] Every `dat_` and `tbl_` named (0 left): text tables, menu tables, palettes, sprite data; the FBI and
      JAPAN ONLY screens found among them (run forced, `eyecatcher_us`, `eyecatcher_japan`)
- [ ] `loc_` stay automatic unless a name helps reading (loop heads, error exits)
- [ ] Review the 67 I names (most are the 16-bit and type $80 card forms, never run: MAME has only the 8-bit card): confirm with a coverage run or a code read, or keep them as I with a reason
- [ ] Doubts list: one line per `?` name, kept in `symbols/`

Done when: `tools/stats.py` reports 0 automatic `sub_`, `dat_` and `tbl_` (reached 2026-11-15); left: the I review and the doubts list.

## 4. RAM, backup RAM and leftovers (L4)

- [ ] Name every work RAM variable used (130 automatic), checking all readers and writers first
- [ ] Backup RAM map at `$D00000`: board settings, soft DIPs per game, game names, book keeping rings and
      code/cabinet numbers are named; still to map: `$D0011A`, `$D09B20`, the slot data, the card area
- [ ] The 30 backup RAM accesses through a4 that cannot be proven: name them or explain each one
- [x] The 4 `move.l #$100000`: `$100000` is named `WorkRamStart` (work RAM start, RAM tests, the card
      utility's card buffer); `tools/stats.py` reports 0 raw RAM operands
- [x] Card utility dispatch `$C150A6`: the tracer now finds the table load 2 instructions before the
      `jmp` (a `pea` in between), so `tools/stats.py` reports 1 indirect jump, the `jmp (a6)` return

## 5. Written reference (L6)

One page per subsystem in `docs/`, from the code and the MAME runs, with addresses and tags:

- [ ] Boot: reset, hardware tests, eyecatcher, slot scan, hand-off to the game
- [ ] System modes and the game contract: BIOS calls, BIOS RAM read and written by games, vector switching
- [ ] Coins, credits and start buttons (CREDIT_CHECK, CREDIT_DOWN, P2 join, continue)
- [ ] Soft DIPs and the cartridge header fields the BIOS reads
- [ ] Calendar chip protocol
- [ ] Memory card: CARD functions, card format, the card utility
- [ ] Test mode: menu structure and how each item stores its settings
- [ ] Interrupts: VBlank (SystemInt1), timer (SystemInt2), when each vector table is mapped
- [ ] Sound commands sent to the Z80
- [ ] Board fix ROM: confirm every tile range of `symbols/sfix.csv` from the screens that use it (`$700-$8FF` not matched yet)

## 6. Other SNK system ROMs (L3, L6)

Public references, allowed for comparison.

- [ ] Match routines of the other MVS and AES system ROMs in `neogeo.zip` by their bytes (operands
      masked) and port the names
- [ ] Document what the region byte and the system type change
- [ ] List what differs between versions (bug fixes, new screens)

## Not now: custom system ROM

The priority is the disassembly. Work on a modified system ROM waits until steps 1-6 are done; the
only build changes meanwhile are test builds that help the disassembly (reaching hidden code,
relocation checks).

## Rules

- Every claim tagged C / I / W / ?; forced runs are said to be forced.
- `make source && make check` before every commit; update this file and the README level table together.
- Public references only (SNK ROMs, NeoGeoDev wiki, MAME).
