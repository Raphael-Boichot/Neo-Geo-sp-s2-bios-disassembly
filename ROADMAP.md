# Roadmap

Where the SP-S2 disassembly stands and what comes next, in order. The disassembly itself (full coverage,
names and a written reference, steps 1-7) is done; step 8, a custom system ROM, is open. Levels L0-L6 are defined in
`SKILL.md`; the measured counts come from `tools/stats.py` and `tools/coverage.py` (2026-11-15).

## Where we are

| Level | State |
|---|---|
| L0 rebuild | done: byte-identical, boot checksum `$4D` |
| L1 every byte typed | done: code 32,966 B, data 21,383 B, free 76,723 B |
| L2 traced and run | 9,252 instructions traced; 8,088 ran in MAME (87.4 %) over 88 scenarios, 6,563 without the forced ones; nothing ran outside the trace |
| L3 names | 574 names (C 530, I 13, W 31), the 13 I and 15 RAM I in `symbols/doubts.csv`; 1,039 automatic labels left, all `loc_` |
| L4 RAM and registers | done: 274 RAM names over 227 addresses, nothing automatic (160 global names on 160 addresses, 128 scoped rows on 67 addresses; 14 rows reuse a name), no raw operand left, every a4 access proven |
| L5 editable tree | done: 14 modules, all ROM addresses symbolic, relocation proven in MAME; the board fix ROM `sfix.sfix` rebuilt from 16 tile sheets (`gfx/sfix/`) |
| L6 understanding | written reference done: 10 pages in [`docs/`](docs/README.md) (boot, game contract, credits, calendar, memory card, test mode, interrupts, sound, board ROMs, other versions); 28 doubts left |

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

`tools/test_mode_scenarios.py` drives every screen (25 scenarios, 5 games and no cartridge).

- [x] Hard DIP (switches changed while shown) and soft DIP: every row type (times, counts, lists),
      both pages, wraps, save; Sengoku 2, Riding Hero, Top Player's Golf, Alpha Mission II
- [x] Cabinet settings: both coin rates, game select, start compulsion, demo sound
- [x] Book keeping: CABINET/COIN, CABINET/PLAY, a game, every page, with played data
- [x] Calendar: every field both ways, set
- [x] Code number: every digit, no card, blank card, game card, 1M card (emulated)
- [x] EXIT with the Setting Mode DIP on, then off
- [x] The 1M card cabinet backup: format, save from two boards, recover (`card1m_*`)
- [x] Book keeping with data on more than one day and month: the date moved back in test mode between
      plays (`book_days_*`, `test_book_keeping_days`); a new day record opens on any date change

Not reachable: `CabinetSettingsOld` (`$C19CF6-$C1A105`), an older cabinet page after a `jmp`.

## 2. Error and rare paths (L2): done

Paths that need a fault, reached with `DEBUG_CMDS` breakpoints that fake the condition or with test
builds; `tools/fault_scenarios.py` (34 scenarios) says which runs are forced.

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

## 3. Names (L3): done

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
- [x] Review the 67 I names: 51 confirmed (the 16-bit and type $80 card forms run on emulated cards,
      `card_word_*` and `card_sparse_*`; the slot table merge run over three boots, `slots_*`; the rest by
      a full code read and their runs); `SelectSlot` renamed `RegisterNewGame`, `MvsLedUpdate` renamed
      `SystemIoMvs` (both did much more than their name)
- [x] Doubts list: `symbols/doubts.csv`, one line per I name (13 ROM, 15 RAM) with the doubt and how to
      settle it; step 6 settled what the other system ROMs could. Most of the rest need more MAME runs
      (multi-block saves on the emulated 16-bit cards, a board with two cartridges, a mahjong
      controller, timed runs) or a ROM card image; a few are leftovers that nothing reads

Done when: `tools/stats.py` reports 0 automatic `sub_`, `dat_` and `tbl_` (reached 2026-11-15) and every I name has a line in the doubts list (done).

## 4. RAM, backup RAM and leftovers (L4): done

- [x] Name every work RAM variable used: 274 names over 227 addresses, 0 automatic (2026-11-15); NeoGeoDev wiki names where
      the wiki has one (BIOS RAM locations), screen-scoped names where the BIOS reuses an area
- [x] Backup RAM map at `$D00000`: every area named (README, Backup RAM map); `$D0A4A0-$D0FFFF` unused
- [x] The 30 backup RAM accesses through a4 that could not be proven: all in the cabinet row handlers
      (both pages), reached through a table after `lea BramA4Base,a4`; proven by reading the callers
      (`a4` hints in `tools/hints.txt`)
- [x] The 4 `move.l #$100000`: `$100000` is named `WorkRamStart` (work RAM start, RAM tests, the card
      utility's card buffer); `tools/stats.py` reports 0 raw RAM operands
- [x] Card utility dispatch `$C150A6`: the tracer now finds the table load 2 instructions before the
      `jmp` (a `pea` in between), so `tools/stats.py` reports 1 indirect jump, the `jmp (a6)` return

## 5. Written reference (L6): done

One page per subsystem in `docs/`, from the code and the MAME runs, with addresses and tags: index in [`docs/README.md`](docs/README.md).

- [x] Boot: reset, hardware tests, eyecatcher, slot scan, hand-off to the game
- [x] System modes and the game contract: BIOS calls, BIOS RAM read and written by games, vector switching
- [x] Coins, credits and start buttons (CREDIT_CHECK, CREDIT_DOWN, P2 join, continue)
- [x] Soft DIPs and the cartridge header fields the BIOS reads
- [x] Calendar chip protocol
- [x] Memory card: CARD functions, card format, the card utility
- [x] Test mode: menu structure and how each item stores its settings
- [x] Interrupts: VBlank (SystemInt1), timer (SystemInt2), when each vector table is mapped
- [x] Sound commands sent to the Z80 (with step 7, `sm1.sm1`): [`docs/sound.md`](docs/sound.md)

## 6. Other SNK system ROMs (L3, L6): done

Public references, allowed for comparison. The goal is to understand SP-S2, not to disassemble the
other versions: what in SP-S2 is common, what is special, and what its unused code was for.

- [x] Find every named SP-S2 routine in the 18 other SNK system ROMs (`tools/compare_bios.py`,
      `symbols/other_bios_routines.csv`): [`docs/versions.md`](docs/versions.md)
- [x] Settle the doubts this can settle: the hidden programs are the AES boot menus (run in MAME),
      the debug monitor is the exception handler of the development and hotel ROMs, the scale and
      sine tables are read by the games, the leftovers are in every version
- [x] What the region byte and the system type change in SP-S2's own code paths (docs/versions.md)
- [x] The routines SP-S2 changed against its closest relatives (US Ver. 1 and 2, Europe Ver. 1):
      one credit pool instead of one per player (US), slot merge, book keeping totals, 1M card list,
      I/O check system bits added since Europe Ver. 1

## 7. The other ROMs of the BIOS set (L0-L3, L5): done

`neogeo.zip` holds three ROMs of the MVS motherboard besides the system ROM. They ship with every
board, whatever the cartridge, so they belong to the BIOS.

- [x] `sfix.sfix`, board fix ROM (128 KB): 16 tile sheets in `gfx/sfix/`, rebuilt and checked by
      `make check`; tile ranges in `symbols/sfix.csv`
- [x] `sfix.sfix`: `$700-$77F` / `$800-$87F` are the HOW_TO_PLAY picture, `$900-$AFF` the HOW_TO_PLAY
      text font (matched by `tools/mess_render.py`); every font range matched to the lists that use it;
      only the kana/kanji halves `$780-$7FF`, `$880-$8FF` and most kanji of `$500-$6FF` have no user in SP-S2 (I)
- [x] `sm1.sm1`, the Z80 sound program on the board (128 KB): Z80 disassembly in `sm1/` rebuilt byte
      for byte (`make check`), code traced (no unresolved jump), the commands SP-S2 sends run in MAME
      (`tools/mame_z80.sh`), the eyecatcher jingle found in it (docs/sound.md)
- [x] `sm1.sm1` L1: every data byte typed (instruments, sound and effect tables, 4 sounds and the coin
      effect as headers and 50 parsed sequences); see docs/sound.md
- [x] `sm1.sm1` short naming pass: every routine that runs in MAME named, commands 4-9 and `$10` run
- [x] `sm1.sm1` rest: the 67 routines that never run named from their code (ADPCM-A/B sound paths,
      fades, slides), every table named, no raw RAM operand left (`ramblock` hints)
- [x] `000-lo.lo`, the sprite zoom table read by the video hardware (128 KB): rebuilt from its rule
      by `tools/lo_rom.py` (row z adds line bitreverse(z XOR $11)), SHA-1 checked by `make check`;
      the four board ROMs described in [`docs/bios_set.md`](docs/bios_set.md)

## 8. Custom system ROM: open

Steps 1-7 are done, so work on a modified system ROM can start; its scope is not decided yet. So far
the only build changes are test builds that help the disassembly (reaching hidden code, relocation
checks).

## Line comments: started

The sources carry a header comment per routine; line comments come from `symbols/comments.csv`
(HOWTO, Names). Done: `boot.s`, the power-on tests, the slot scan and slot switching, the Z80
handshake, coins, credits, starts and the LEDs (`power_on.s`, `system.s`). Next, if wanted: the rest of
`power_on.s` (slot table merge, book keeping, 1M card save), `calendar.s`, `eyecatcher.s`, then the
`sm1.sm1` engine core (would need the same file for `tools/sm1.py`).

## Rules

- Every claim tagged C / I / W / ?; forced runs are said to be forced.
- `make source && make check` before every commit; update this file and the README level table together.
- Public references only (SNK ROMs, NeoGeoDev wiki, MAME).
