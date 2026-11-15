# Coins, credits and start buttons

How an MVS turns coins into credits and credits into games. On an AES (`BIOS_MVS_FLAG` 0) none of
this runs: the credit routines return at once and a START always starts.

Tags: **C** read in the code and run in MAME, **W** public reference (NeoGeoDev wiki), **I** inferred.

## Coins (every VBlank, `SystemIoMvs`)

`SystemIoMvs` (`$C126B4`) reads `REG_STATUS_A`, inverted, into `CoinInputs` (bit 0 coin 1, bit 1
coin 2, bit 2 service) and keeps the previous frame in `CoinInputsPrevious`. A coin counts on the
first frame its bit is 1 after two frames at 0 (C).

`CountCoin` (`$C128A6`), once per coin slot:

1. +1 in `CoinCounts` (coins toward the next credit) and in `CoinCounterPending` (the
   mechanical counter, below).
2. Unless `TestModeActive`: +1 in COIN1 or COIN2 of today's and this month's CABINET/COIN records.
3. When `CoinCounts` reaches the slot's coins (`Coin1Coins` / `Coin2Coins`, cabinet settings), it
   is reduced by that number and the slot's credits (`Coin1Credits` / `Coin2Credits`) are added to
   `Credits` in BCD, at most 99.

`CountService` (`$C128E6`): the service switch adds 1 credit (BCD, at most 99) and, unless
`TestModeActive`, 1 to SERVICE of today's and this month's records. A coin also resets the start
compulsion timer (`BIOS_SELECT_TIMER` = `StartCompulsionTime`) and queues a coin sound
(`CoinSoundCount`, played by `PlayCoinSound`: the cartridge's `CART_COIN_SOUND`, or sound command
`$7F` during a system screen) (C).

The two mechanical coin counters get one pulse per coin, one at a time: `CoinCounterPulse` counts
down from `$1F`, on (`REG_SETCC1`) while bit 4 is set, off (`REG_RESETCC1`) after (C).

The two LED counters on the MVS show `Credits` and `Credits2`, one per frame (latches `$EF` and
`$DF`). Nothing in SP-S2 writes `Credits2`: it is player 2's credits on the US MVS versions, which
count credits per player; SP-S2 keeps one pool (docs/versions.md, C: MAME with the US and European
BIOS). The start compulsion still reads the two bytes as a word.

`SystemIoMvs` starts with a `bra` over a block that would show the next slot number on the slot
LED every 4 frames (`$C126C4-$C126E9`): that block can never run (C: static; never seen in MAME).

Free play is hard DIP switch 7 on (`REG_DIPSW` bit 6 reads 0): coins still count, credits are
neither checked nor taken (C).

## Starts (`CheckPlayerStart`, `$C116C8`)

In game mode (`SystemIo` with `BIOS_SYSTEM_MODE` bit 7 set and `BIOS_USER_MODE` not 0), a START press
(`BIOS_STATCHANGE`) sets `BIOS_START_FLAG` (bit 0 P1, bit 1 P2), then `StartCreditCheck`
(`$C1177A`) keeps the bits the credits allow:

| Start bits | Situation | Credits needed | `BIOS_START_FLAG` |
|---|---|---|---|
| P1 | | 1 | 1 |
| P2 | while the game is played (join) | 1 | 2 |
| P2 | on the title or demo (`BIOS_USER_MODE` 1) | 2 | 3: both players start |
| P1 and P2 | | 2 | 3 |

(`StartCreditsNeeded`, `StartFlagResult`; the BCD credits are compared as bytes.) With too few
credits the flag is cleared. If a bit is left, the cartridge's `CART_PLAYER_START` runs; it can
clear the bits it refuses. For each bit still set, `DeductStartCredits` takes one credit
(`DeductPlayerCredit`) and counts the play, and `BIOS_SYSRET_STATUS` becomes 3 (C: MAME, credits 02
-> 01 on START).

### Start compulsion

On the title with credits in and GAME START COMPULSION set (cabinet settings), the BCD
`BIOS_SELECT_TIMER` counts the seconds down (`BIOS_COMPULSION_FRAME_TIMER`: 59 frames a second).
At 0 the system ROM presses START itself: P1, or P2 when only the second credit byte is non-zero,
and sets `CompulsionStart` until the start is taken (C for the code; I for the P2 case).

## CREDIT_CHECK and CREDIT_DOWN (games that handle credits themselves)

`CreditCheck` (`$C117CE`, BIOS call `CREDIT_CHECK`): MVS and no free play only. The game puts the
credits it wants per player in `BIOS_CREDIT_DEC1`/`DEC2`; the routine clears `DEC3`/`DEC4`, then
checks P1 against `Credits` and P2 against what is left, clearing a request that cannot be met. On
the title with P1 asking nothing, P2's request counts double (a two-player start, as above) (C).

`CreditDown` (`$C11820`, BIOS call `CREDIT_DOWN`): for P1 and P2 with a non-zero `DEC` byte, takes
the credits and counts the plays like a START (`CreditDownCount`), clears `CompulsionStart` and sets
`BIOS_SYSRET_STATUS` 3 (C).

Seen in MAME (README, BIOS calls used by games): King of the Monsters 2 (P2 join, continue, co-op),
King of the Monsters (co-op), League Bowling (game type); Top Player's Golf and Baseball Stars
Professional only with the US country code, which they copy at boot; Blue's Journey calls
CREDIT_CHECK every frame to show which player can start.

## Book keeping of a play (`DeductPlayerCredit`, `$C12934`)

Each start or CREDIT_DOWN of a player adds to five records through `BookKeepingCount`: the game's
today, total and this month, and CABINET/PLAY today and this month. A record is 16 bytes:

| Offset | CABINET/COIN | CABINET/PLAY and game records |
|---|---|---|
| +0 | date (year, month, day, weekday) | date |
| +4 | COIN1 | PLAY |
| +8 | COIN2 | CONT.: counted when the player's `PlayerModPrevious` byte was not 0 (already in the game: a continue or a join) |
| +C | SERVICE | play time in seconds (`BookAddPlayTime`); AV.TIME = time / plays |

It also adds 1 to the game's counter for the current hour of the software clock (`BookGameHours`,
not shown by the test mode). Play time counts while P1 or P2 is playing (`PlayTimeCount`) and is
added to the records at game over.

## Demo end (`DemoEndCheck`, `$C1183C`)

On the title or demo (`BIOS_USER_MODE` 1), `SystemIo` ends the cartridge's demo with a
`BIOS_SYSRET_STATUS` code, calls `CART_DEMO_END`, then `SystemReturn`:

| Code | When | Tag |
|---|---|---|
| 6 | credits in, start compulsion on, `BIOS_TITLE_MODE` not yet set: the game shows its title (sets `BIOS_TITLE_MODE`) | C |
| 4 | SELECT P1 (`BIOS_STATCHANGE_RAW` bit 1), or the start compulsion ran out: next slot | C |
| 5 | SELECT P2 (bit 3): previous slot | C (code), I (run: one slot in MAME) |

SELECT works only with credits in, unless GAME SELECT is FREE or the board is in slot-number mode.

## Sources

`src/system.s`, `src/power_on.s`, `symbols/ram.csv`; NeoGeoDev wiki: BIOS RAM locations
(`BIOS_START_FLAG`, `BIOS_CREDIT_DEC`, `BIOS_SYSRET_STATUS` codes), BIOS calls.
