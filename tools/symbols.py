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


NOTES = {}      # address -> (tag, note) of every loaded name


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
            NOTES[a] = (r['tag'], r.get('note', ''))
    return rows



ROM_NAMES = load('rom_names.csv')
REGISTERS = load('registers.csv')
RAM = load('ram.csv')
CART = load('cart_header.csv')


def load_scoped(name):
    """symbols/ram_scoped.csv: RAM shared by several subsystems (the BIOS reuses its work areas per
    screen): addr,name,tag,first,last,note - the name applies to instructions from first to last."""
    rows = []
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return rows
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            if r['tag'] not in ('W', 'C', 'I', '?'):
                raise SystemExit(f'{name}: bad tag {r["tag"]!r} at {r["addr"]}')
            rows.append((int(r['addr'], 16), int(r['first'], 16), int(r['last'], 16), r['name']))
    for i, (a, f1, l1, n1) in enumerate(rows):
        if a in RAM:
            raise SystemExit(f'{name}: {a:06X} has a global name in ram.csv')
        for a2, f2, l2, n2 in rows[i + 1:]:
            if n1 == n2 and a != a2:
                raise SystemExit(f'{name}: name {n1} used for two addresses')
            if a == a2 and f1 <= l2 and f2 <= l1:
                raise SystemExit(f'{name}: {a:06X} scopes {n1} and {n2} overlap')
    return rows


RAM_SCOPED = load_scoped('ram_scoped.csv')
_seen = {}
for _file, _table in (('rom_names.csv', ROM_NAMES), ('registers.csv', REGISTERS), ('ram.csv', RAM),
                      ('cart_header.csv', CART), ('ram_scoped.csv', {a: n for a, _, _, n in RAM_SCOPED})):
    for _name in _table.values():
        if _name in _seen:   # one assembler symbol: a clash makes the generator fall back to raw words
            raise SystemExit(f'name {_name} is in both {_seen[_name]} and {_file}')
        _seen[_name] = _file
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


def load_modules():
    """symbols/modules.csv: (start address, file, description), in address order."""
    path = os.path.join(ROOT, 'modules.csv')
    if not os.path.exists(path):
        return []
    with open(path, newline='') as f:
        return sorted((int(r['start'], 16), r['file'], r['description']) for r in csv.DictReader(f))


MODULES = load_modules()
