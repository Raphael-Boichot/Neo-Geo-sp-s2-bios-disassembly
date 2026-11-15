# Memory card

The memory card at `$800000` holds game saves (the CARD BIOS call) and, on a 1 Mbit card, the board's
own settings (the cabinet backup, README). This page is about the game saves.

Tags: **C** read in the code and run in MAME, **W** public reference (NeoGeoDev wiki), **I** inferred.
MAME emulates only the 2 KB 8-bit card; the two 16-bit kinds were run on cards emulated with memory
taps (`tools/mame_inputs.lua`: `CARD1M`, `CARD1M_SPARSE`).

## Card kinds (`CardDetect`, `$C14A3A`)

`CardFormat` calls `CardDetect`, which writes test patterns to find what is in the slot. It
destroys the card's contents, so only formatting calls it.

| `CardTypeLo` | Kind | Seen as | Size steps | Tag |
|---|---|---|---|---|
| 0 | 8-bit card: one byte per 16-bit word (the high byte reads `$FF`) | `$AA` comes back only in the low byte | `$1000` addresses (2 KB) up to `$8000` | C (MAME card) |
| 1 | 16-bit card | `$AAAA` comes back whole | `$800` bytes up to `$4000` | C (emulated) |
| `$80` | 16-bit card answering on every other word (address line A1 not decoded) | `$5555` written at +2 reads back at +0 | as the 8-bit card | C (emulated) |
| other | an SNK ROM card ("SNK ROM " in its header, `IsSnkRomCard`) | header text | | I (no ROM card run) |

The size is then found by writing `$55`, `$AA` and address patterns over the whole card. Each
kind has its own form of every file system routine: `...Byte`, `...Word`, `...Sparse` in
`symbols/rom_names.csv`.

A blank type `$80` card in the slot at power-on stops the boot with MEMORY CARD ERROR: the power-on
test of an unformatted card fails on the doubled words (C, emulated).

## Layout

The card is cut into 64-byte blocks. A layout table gives, per card size, where the directory and
the File Allocation Table (FAT) start, counted from the card base (`CardLayoutByte` /
`CardLayoutWord`, `$C14D30` / `$C14DE8`; offsets are CPU addresses, so on an 8-bit card two
addresses per byte):

| | 8-bit card, 2 KB (`$1000` addresses) | 16-bit card, 16 KB (`$4000`) |
|---|---|---|
| header | +`$000`, 64 bytes | +`$000`, 128 bytes |
| directory (`CardDirectory`) | +`$080`, 32 entries | +`$080`, 256 entries |
| FAT, two copies (`CardFat`, `CardFatSize` each) | +`$180`, `$80` each | +`$480`, `$100` each |
| data (`CardDataStart`) | +`$280` | +`$680` |
| blocks | 32, of which 5 hold the header, directory and FAT: 27 for saves | 256 |

A 2 KB card is therefore full after 27 one-block saves, as seen in MAME (`card_full_*`) (C).

**Header** (`CardFormat`, 8-bit card, byte offsets): 0-9 zero; 10-11 the card size; 12 the word
`CardFormatVersion` (`$0000`, at `$C11000` in the system ROM, the name is a guess); 13 and 14 the
checksums of the two FAT copies; 16-31 the user name (16 characters, spaces when formatted; CARD
functions 6/7); then the text NEO-GEO and the system ROM's region byte (C for what is written, I for
the meaning of the version word).

**Directory**: one entry per save; on the 8-bit card 4 bytes: file number (`$FF` = free entry), NGH
high and low byte (the game's number), then the first block (I: from the search and save code).

**FAT**: one byte per block: 0 free, 1-2 end of a file (formatting marks the system blocks 2), 3 and
up the next block of the file. The two copies carry a checksum each in the header; `CardCheckFat`
rewrites a bad copy from the good one and returns `$83` when both are bad (C).

## CARD (BIOS call, function in `BIOS_CRDF`)

| Function | Routine | What it does | Tag |
|---|---|---|---|
| 0 | `CardFormat` | detect, then write header, empty directory and both FATs | C |
| 1 | `CardDataSearch` | find the game's data (`BIOS_CRDNGH`, `BIOS_CRDFILE`) | C |
| 2 | `CardLoadData` | copy a save to `BIOS_CRDPTR` | C |
| 3 | `CardSaveData` | write `BIOS_CRDSIZE` bytes from `BIOS_CRDPTR`, replacing an older save of the same file | C |
| 4 | `CardDeleteData` | free the save's blocks and entry | C |
| 5 | `CardReadTitle` | next data title on the card (the card utility lists them) | C |
| 6, 7 | `CardSaveUserName`, `CardLoadUserName` | the 16-character user name in the header | C |

`Card` returns `$80` when the card-detect bits of `REG_STATUS_B` (bits 4-5) are not both 0; the
functions that write (format, save) return `$85` when bit 6 says the card is write-protected.

Results in `BIOS_CRDRESULT`:

| Code | Meaning |
|---|---|
| `$00` | done |
| `$80` | no card |
| `$81` | not formatted |
| `$82` | no such data (or the end of the title list) |
| `$83` | both FAT copies bad |
| `$84` | card full |
| `$85` | write-protected |

## CARD_ERROR (`CardError`, `$C133C0`)

A game calls it after a failed CARD. The result and the function pick a handler in `CardErrorTable`
(blank = no message):

| Result \ function | 0 | 2 load | 3 save | 4 delete | 6 save name | 7 load name |
|---|---|---|---|---|---|---|
| `$81` not formatted | | NO DATA | format | | format | NO DATA |
| `$82` no data | | | | | | |
| `$83` FAT error | | ERROR | format | | | |
| `$84` full | | | FULL | | | |
| `$85` write-protected | PROTECTED | NO DATA | PROTECTED | PROTECTED | PROTECTED | NO DATA |

The messages take over the screen: the game's fix layer is saved and put back
(`CardErrorSaveScreen`/`RestoreScreen`), the game's system mode is kept and restored. On an MVS a
message ends after 15 seconds by itself. Not formatted: an MVS formats at once, an AES asks DO YOU
WISH TO FORMAT?. Full: MEMORY CARD FULL with the saves listed 6 to a page; A deletes the selected
save and the game's save is tried again, B gives it up (C: `lbowling_card_*`, `card_full_*`).

## Card utility (hidden in SP-S2)

MEMORY CARD UTILITY: 1. CARD FORMAT, 2. DISPLAY DATA NAME, 3. COPY A DATA, 4. DELETE A DATA,
5. FILE USER'S NAME, 6. END. No menu item reaches it in SP-S2;
`tools/hidden_programs_test.py` builds a test BIOS that opens it from the test menu. COPY reads a save,
asks for the other card, and writes it there (with ALL COPY for every save) (C: `card_util_*`).

## Sources

`src/card.s`; `symbols/rom_names.csv` (every routine, with its runs); NeoGeoDev wiki: BIOS calls (CARD,
CARD_ERROR), BIOS RAM locations (`BIOS_CRDF`.. `BIOS_CRDFILE`).
