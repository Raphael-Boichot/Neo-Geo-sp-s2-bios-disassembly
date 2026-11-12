"""Load the name tables in symbols/*.csv.

Files (one row per address, `addr,name,tag,note`, addr in hex without `$`):
  symbols/rom_names.csv   routines, tables and data in the system ROM
  symbols/ram.csv         work RAM ($100000-$10FFFF) and backup RAM ($D00000-$D0FFFF)
  symbols/registers.csv   memory-mapped registers
  symbols/cart_header.csv cartridge program header fields read by the BIOS
Tags: W = public documentation (NeoGeoDev wiki), C = read in the code or seen in
MAME, I = inferred, ? = doubt.
"""
import csv
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'symbols')


def load(name):
    rows = {}
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return rows
    names = set()
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            a = int(r['addr'], 16)
            if a in rows:
                raise SystemExit(f'{name}: address {a:06X} named twice')
            if r['name'] in names:
                raise SystemExit(f'{name}: name {r["name"]} used twice')
            if r['tag'] not in ('W', 'C', 'I', '?'):
                raise SystemExit(f'{name}: bad tag {r["tag"]!r} at {a:06X}')
            names.add(r['name'])
            rows[a] = r['name']
    return rows


ROM_NAMES = load('rom_names.csv')
REGISTERS = load('registers.csv')
RAM = load('ram.csv')
CART = load('cart_header.csv')
BIOS_CALLS = ROM_NAMES          # kept for older callers
ABS_SYMBOLS = dict(REGISTERS)
ABS_SYMBOLS.update(RAM)


def load_regions():
    """symbols/regions.csv: (start, end, name, tag) for named blocks (tables, call table)."""
    path = os.path.join(ROOT, 'regions.csv')
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        return [(int(r['start'], 16), int(r['end'], 16), r['name'], r['tag']) for r in csv.DictReader(f)]


REGIONS = load_regions()
# blocks whose bytes are a table: never shown as text
TABLE_RANGES = [(s, e) for s, e, n, _ in REGIONS if 'Table' in n and 'call' not in n]
