#!/usr/bin/env python3
"""Check the system ROM's weekday computation against the real calendar.

Usage: check_weekday.py [build/sp-s2.bin]

CheckCalendarDate ($C12EF8) computes the weekday it writes to the calendar chip (0 = Sunday) as
(days of the months before + day - 1 + YearWeekdayTable[yy]) mod 7, with February = 29 days when
yy mod 4 = 0 (MonthDaysTable entry 0). YearWeekdayTable[yy] is the weekday of January 1st. This
script reads both tables from the ROM, finds the 100-year window they describe and checks every date.
"""
import csv
import datetime
import os
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
rom = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(R, 'build', 'sp-s2.bin'), 'rb').read()
addr = {r[1]: int(r[0], 16) - 0xC00000 for r in csv.reader(open(os.path.join(R, 'symbols', 'rom_names.csv')))
        if r and r[0] != 'addr' and not r[0].startswith('#')}
years = rom[addr['YearWeekdayTable']:][:100]
mdays = rom[addr['MonthDaysTable']:][:13]


def weekday(yy, m, d):
    days = sum(mdays[0] if mm == 2 and yy % 4 == 0 else mdays[mm] for mm in range(1, m))
    return (days + d - 1 + years[yy]) % 7


def real(y, m, d):
    return (datetime.date(y, m, d).weekday() + 1) % 7      # Python: Monday = 0


def jan1(y):
    return real(y, 1, 1)


# the century of each two-digit year, from the table itself
first = [yy for yy in range(100) if years[yy] != jan1(2000 + yy)]
pivot = first[0] if first else 100
assert all(years[yy] == jan1(1900 + yy) for yy in range(pivot, 100)), 'table matches neither century'
start = 1900 + pivot if pivot < 100 else 2000
print(f'YearWeekdayTable: years {pivot:02d}-99 are 19xx, 00-{pivot - 1:02d} are 20xx: {start}-{start + 99}')
n = bad = 0
for y in range(start, start + 100):
    for m in range(1, 13):
        last = mdays[0] if m == 2 and y % 4 == 0 else mdays[m]
        for d in range(1, last + 1):
            n += 1
            bad += weekday(y % 100, m, d) != real(y, m, d)
print(f'{n} dates checked, {bad} wrong')
sys.exit(1 if bad else 0)
