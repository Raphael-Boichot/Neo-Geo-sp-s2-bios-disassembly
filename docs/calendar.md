# Calendar chip

The MVS board has an NEC uPD4990A calendar chip. The system ROM uses it for the date and time
(BIOS_YEAR..BIOS_SECOND, the book keeping days and months), and its 1-second pulse checks the
VBlank timing at power-on. AES consoles have no calendar.

Tags as in the rest of the repository: **C** read in the code and run in MAME, **W** from a public
reference (NeoGeoDev wiki, the chip's datasheet), **I** inferred.

## Lines

| Register | Bit | Use | Tag |
|---|---|---|---|
| `REG_RTCCTRL` (`$380051`), write | 0 | data in | C |
| | 1 | clock | C |
| | 2 | strobe (latches a command) | C |
| `REG_STATUS_A` (`$320001`), read | 6 | TP, the chip's timing pulse | C |
| | 7 | data out | C |

`WriteRtcCtrl` (`$C12DB0`) is the only routine that writes `REG_RTCCTRL`.

## Commands

A command is 4 bits sent low bit first (data bit, clock high, clock low), then the strobe:
`RtcCommand` (`$C12D6C`). Data bytes go the same way without the strobe (`RtcSendByte`, `$C12D48`)
and come back one bit per clock pulse on `REG_STATUS_A` bit 7, low bit first (`RtcReadByte`,
`$C12CD8`; `RtcReadBits` reads fewer bits).

| Code | Meaning | Sent by | Tag |
|---|---|---|---|
| 0 | register hold (the clock runs) | `SetupCalendar` after a time set | W (datasheet) |
| 1 | register shift (the shift register goes to data out) | `ReadCalendar`, `SetupCalendar` | W |
| 2 | time set and counter hold (shift register -> clock) | `SetupCalendar` | W |
| 3 | time read (clock -> shift register) | `ReadCalendar` | W |
| 7 | TP = 4096 Hz | power-on test, after the check | I (order of the datasheet's 8 TP commands, MAME's names) |
| 8 | TP = 1-second interval | power-on test | I (same) |

## The 48-bit register

Shifted low bit first, in this order (`ReadCalendar` stores each byte to its BIOS RAM place):

| Bits | Content | BIOS RAM |
|---|---|---|
| 0-7 | second (BCD) | `BIOS_SECOND` |
| 8-15 | minute (BCD) | `BIOS_MINUTE` |
| 16-23 | hour (BCD, 24 h) | `BIOS_HOUR` |
| 24-31 | day (BCD) | `BIOS_DAY` |
| 32-35 | weekday (0 = Sunday) | `BIOS_WEEKDAY` |
| 36-39 | month (binary 1-12) | `BIOS_MONTH`, turned into BCD: 10-12 get 6 added (`$0A` -> `$10`) |
| 40-47 | year (BCD, two digits) | `BIOS_YEAR` |

`ReadCalendar` then reads 4 more bits and drops them.

## Reading: READ_CALENDAR (`ReadCalendar`, `$C12C78`)

Command 3 (time read), a short delay, command 1 (shift), then the 6 bytes above. Called at
power-on (`PowerOnSetup`), by the test menu, the test-mode and hardware-test calendar screens, the 1M
card cabinet save, and by games through the BIOS call slot `$C0045C`.

## Setting: SETUP_CALENDAR (`SetupCalendar`, `$C12CF2`)

1. `CheckCalendarDate` (`$C12EF8`) checks the day against `MonthDaysTable` and computes the
   weekday (below); an invalid date returns with d7 = 1 and nothing is written.
2. Command 1, then second, minute, hour, day, month x 16 + weekday (`CalendarMonthWeekday`), year.
3. Command 2 (time set), then command 0: the clock runs from the new time.

Run in MAME by D on the test-mode calendar screen (C).

## Weekday

The chip counts the weekday by itself; the system ROM computes it only when a date is set:

    weekday = (days of the months before + day - 1 + YearWeekdayTable[year]) mod 7

`YearWeekdayTable` (`$C12F88`) gives the weekday of January 1st for each two-digit year: 90-99 are
1990-1999 and 00-89 are 2000-2089. February has 29 days when the two-digit year is a multiple of 4.
`tools/check_weekday.py` finds every one of the 36,525 dates 1990-2089 right (C). Outside that
window the weekday set from test mode is wrong, and 2100 would get a February 29th.

The book keeping draws the Sunday records in red (`BookPutDate`: weekday byte 0 selects palette 1).

## Power-on test (in `PowerOnTest` at `$C11BD6`)

1. Command 8: TP becomes a 1-second pulse.
2. Wait for a rising edge of TP (`WaitRtcPulse`: bit 6 of `REG_STATUS_A`).
3. Clear `BIOS_INT1_FRAME_COUNTER`, set `BIOS_INT1_SKIP` (SystemInt1 then only counts frames),
   enable interrupts, wait for the next edge, disable interrupts.
4. Command 7, then check the count: 57-63 VBlanks between the two pulses, otherwise boot error 5,
   CALENDAR ERROR (`BootErrorCalendar`).

So the test checks the chip and the 60 Hz VBlank against each other. Faked in MAME (scenario
`boot_error_calendar`) and seen at every boot (C).

## Cartridge calendar (NEO-CLN)

A cartridge whose ID reads NEO-CLN carries its own calendar on the same protocol: control at
`$280051`, data in at `$220001` (`WriteRtcCtrlAlt`, `RtcCommandAlt`, `RtcSendByteAlt`,
`RtcReadByteAlt`, `ReadCalendarAlt`, `SetupCalendarAlt`, `$C12DB8-$C12EF6`). At the slot scan its
date is read and written to the board calendar; the hardware-test calendar screen sets both. Run in
MAME with a patched header (`tools/neo_cln_test.py`); MAME has no chip there, so the values read
are open bus (C for the code path, the hardware itself not seen). Details in the README, NEO-CLN
cartridges.

## Sources

- The code: `src/calendar.s`, `src/power_on.s`, symbol descriptions in `symbols/rom_names.csv`.
- NEC uPD4990A data sheet (commands 0-3 and the counts of the other commands).
- MAME `src/devices/machine/upd1990a.cpp` (the order and names of the TP commands).
- NeoGeoDev wiki: Memory mapped registers (`REG_RTCCTRL`, `REG_STATUS_A`), BIOS RAM locations.
