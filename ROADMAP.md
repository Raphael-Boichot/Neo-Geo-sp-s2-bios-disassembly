# Roadmap

Where the SP-S2 disassembly stands and what comes next, in order. The priority is the disassembly itself:
full coverage, names and a written reference. Levels L0-L6 are defined in
`SKILL.md`; the measured counts come from `tools/stats.py` and `tools/coverage.py` (2026-11-13).

## Where we are

| Level | State |
|---|---|
| L0 rebuild | done: byte-identical, boot checksum `$4D` |
| L1 every byte typed | done: code 32,338 B, data 22,011 B, free 76,723 B |
| L2 traced and run | 9,109 instructions traced; 4,386 ran in MAME (48.2 %) over 25 scenarios; nothing ran outside the trace |
| L3 names | 160 names (C 104, I 28, W 28); 1,421 automatic labels left: 158 `sub_`, 164 `dat_`, 38 `tbl_`, 1,061 `loc_` |
| L4 RAM and registers | 217 RAM addresses used, 54 named; 30 backup RAM accesses through a4 left raw |
| L5 editable tree | done: 14 modules, all ROM addresses symbolic, relocation proven in MAME |
| L6 understanding | started: screens and BIOS calls seen in MAME; no written reference yet |

Coverage and automatic routines by module:

| Module | Ran in MAME | `sub_` left |
|---|---|---|
| `test_mode.s` | 23 % (535 / 2,294) | 42 |
| `card.s` (with the card utility) | 31 % (950 / 3,025) | 51 |
| `boot_error.s` | 0 % (0 / 88) | 0 |
| `system.s` | 61 % | 0 |
| `calendar.s` | 67 % | 3 |
| `video_io.s` | 70 % | 14 |
| `power_on.s` | 81 % | 30 |
| `eyecatcher.s` | 84 % | 3 |
| `boot.s` | 85 % | 2 |
| `hardware_test.s` | 88 % | 13 |
| `how_to_play.s` | 90 % | 0 |

## 1. Test mode coverage (L2)

The largest block that never ran: about 1,760 instructions in `test_mode.s`. Most of it is the
editing side of the menus.

- [ ] Hard DIP and soft DIP: move the cursor, change every value type, save and leave
- [ ] Cabinet settings: coins per credit for each slot, game select, demo sound, etc.
- [ ] Book keeping: page through, clear
- [ ] Calendar: move the cursor over every field, set, cancel
- [ ] Code number entry and the EXIT item (with hard DIP 1 still on and off)
- [ ] One scenario per item with `tools/mame_coverage.sh` (`MODE=dip KEYS=...`), screenshots in `docs/`

Done when: every reachable test-mode path has run, and the rest is explained.

## 2. Error and rare paths (L2)

Paths that need a fault. Reach them with `DEBUG_CMDS` breakpoints that fake the condition (as done
for SYSTEM_INT2), and say in the scenario name that the condition was forced.

- [ ] Boot error screens (`BootError`, `$C16ADA`): work RAM, backup RAM, video RAM, palette RAM,
      calendar, memory card, system ROM checksum
- [ ] The checksum slot `CHECKSUM_LOOP` (`$C0047A` -> `$C16C0E`)
- [ ] The work RAM test loop when every hard DIP is on (`WorkRamTestLoop`, `$C11BA8`)
- [ ] The alternate calendar path (`$C12DB8-$C12EF0`): find what selects it
- [ ] Card error cases: no card, write-protected card, full card, wrong format (CARD_ERROR)
- [ ] Card utility COPY (`CardUtilCopy`) and the controller test, as coverage scenarios of the test build
- [ ] CREDIT_DOWN in Top Player's Golf and Baseball Stars Professional

## 3. Names (L3)

- [ ] Every `sub_` named (158 left), test mode and card first, then power_on and video_io
  - [x] `system.s`: CreditCheckPlayer, CallDeductStartCredits, DemoEndCheck
- [ ] Every `dat_` and `tbl_` named (202): text tables, menu tables, palettes, sprite data
- [ ] `loc_` stay automatic unless a name helps reading (loop heads, error exits)
- [ ] Review the 28 I names: confirm with a coverage run or a code read, or keep them as I with a reason
- [ ] Doubts list: one line per `?` name, kept in `symbols/`

Done when: `tools/stats.py` reports 0 automatic `sub_`, `dat_` and `tbl_`.

## 4. RAM, backup RAM and leftovers (L4)

- [ ] Name every work RAM variable used (163 automatic), checking all readers and writers first
- [ ] Backup RAM map at `$D00000`: book keeping, soft DIPs per slot, calendar, slot data, card area
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
