#!/usr/bin/env python3
"""Consistency check of the whole repository. Run from the repository root: python3 tools/check_repo.py

1. symbol files: parse, unique names and addresses, valid tags, scoped ranges
2. doubts.csv: every row names an existing I or ? entry, every I entry has a row
3. sources: every label of symbols/rom_names.csv is in src/, every sm1 name in sm1/src/sm1.asm
4. documents: relative links and images exist; `Name` (`$addr`) pairs agree with the symbol files;
   backticked CamelCase names exist in a symbol file
5. counts stated in README.md, ROADMAP.md and docs/ against the symbol files
6. tools: every Python file compiles, every shell script parses
7. forbidden words in tracked files and commit messages

Prints one line per problem and a summary; exit code 1 when a problem was found.
The rebuild itself is `make source sm1-source && git diff --exit-code && make check`.
"""
import csv
import glob
import os
import py_compile
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
os.chdir(ROOT)
problems = []


def bad(msg):
    problems.append(msg)
    print('  ' + msg)


def rows(path):
    return list(csv.DictReader(open(path, newline='')))


print('1. symbol files')
rom = rows('symbols/rom_names.csv')
ram = rows('symbols/ram.csv')
scoped = rows('symbols/ram_scoped.csv')
hdr = rows('symbols/cart_header.csv')
sm1 = rows('sm1/names.csv')
TAGS = {'C', 'I', 'W', '?'}
for name, data in (('rom_names', rom), ('ram', ram), ('cart_header', hdr), ('sm1/names', sm1)):
    seen_n, seen_a = {}, {}
    for r in data:
        if r['tag'] not in TAGS:
            bad(f'{name}: {r["addr"]} {r["name"]}: tag {r["tag"]!r}')
        if r['name'] in seen_n:
            bad(f'{name}: name {r["name"]} twice ({seen_n[r["name"]]}, {r["addr"]})')
        if r['addr'] in seen_a:
            bad(f'{name}: address {r["addr"]} twice ({seen_a[r["addr"]]}, {r["name"]})')
        seen_n[r['name']] = r['addr']
        seen_a[r['addr']] = r['name']
        if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', r['name']):
            bad(f'{name}: {r["addr"]}: name {r["name"]!r} is not an identifier')
for r in rom:
    a = int(r['addr'], 16)
    if not 0xC00000 <= a < 0xC20000:
        bad(f'rom_names: {r["addr"]} outside the system ROM')
global_names = {r['name'] for r in rom} | {r['name'] for r in ram} | {r['name'] for r in hdr}
by_addr = {}
for r in scoped:
    if r['tag'] not in TAGS:
        bad(f'ram_scoped: {r["addr"]} {r["name"]}: tag {r["tag"]!r}')
    if int(r['first'], 16) > int(r['last'], 16):
        bad(f'ram_scoped: {r["name"]}: range {r["first"]}-{r["last"]} reversed')
    by_addr.setdefault(r['addr'], []).append(r)
    if r['name'] in global_names:
        bad(f'ram_scoped: {r["name"]} is also a global name')
for a, rs in by_addr.items():
    rs = sorted(rs, key=lambda r: int(r['first'], 16))
    for x, y in zip(rs, rs[1:]):
        if int(y['first'], 16) <= int(x['last'], 16):
            bad(f'ram_scoped: {a}: {x["name"]} and {y["name"]} overlap')
ram_addrs = {r['addr'] for r in ram}
for r in scoped:
    if r['addr'] in ram_addrs:
        bad(f'ram_scoped: {r["addr"]} {r["name"]} also has a global name')

print('2. doubts.csv')
doubts = rows('symbols/doubts.csv')
files = {'rom_names': rom, 'ram': ram, 'ram_scoped': scoped}
listed = set()
for d in doubts:
    src = files.get(d['file'])
    if src is None:
        bad(f'doubts: {d["name"]}: unknown file {d["file"]}')
        continue
    hit = [r for r in src if r['name'] == d['name']]
    if not hit:
        bad(f'doubts: {d["name"]} not in {d["file"]}')
        continue
    if hit[0]['addr'] != d['addr']:
        bad(f'doubts: {d["name"]}: address {d["addr"]}, {d["file"]} says {hit[0]["addr"]}')
    if hit[0]['tag'] not in ('I', '?'):
        bad(f'doubts: {d["name"]} is tagged {hit[0]["tag"]} in {d["file"]}: no longer a doubt')
    if d['tag'] != hit[0]['tag']:
        bad(f'doubts: {d["name"]}: tag {d["tag"]} here, {hit[0]["tag"]} in {d["file"]}')
    listed.add((d['file'], d['name']))
for f, src in files.items():
    for r in src:
        if r['tag'] in ('I', '?') and (f, r['name']) not in listed:
            bad(f'{f}: {r["name"]} is tagged {r["tag"]} but has no row in doubts.csv')

print('3. sources')
src_text = ''.join(open(p).read() for p in sorted(glob.glob('src/*.s')) + sorted(glob.glob('src/*.inc')))
labels = set(re.findall(r'^([A-Za-z_][A-Za-z0-9_]*):', src_text, re.M))
equs = set(re.findall(r'\.equ\s+([A-Za-z_][A-Za-z0-9_]*)', src_text))
for r in rom:
    if r['name'] not in labels and r['name'] not in equs:
        bad(f'rom_names: {r["name"]} ({r["addr"]}) is not a label in src/')
for r in ram + scoped:
    if r['name'] not in src_text:
        bad(f'{"ram" if r in ram else "ram_scoped"}: {r["name"]} never used in src/')
sm1_src = open('sm1/src/sm1.asm').read()
for r in sm1:
    if not re.search(r'\b' + re.escape(r['name']) + r'\b', sm1_src):
        bad(f'sm1/names: {r["name"]} not in sm1/src/sm1.asm')

print('4. documents')
docs = ['README.md', 'ROADMAP.md', 'HOWTO.md'] + sorted(glob.glob('docs/*.md'))
addr_of = {}
for r in rom + ram + hdr:
    addr_of.setdefault(r['name'], set()).add(int(r['addr'], 16))
for r in scoped:
    addr_of.setdefault(r['name'], set()).add(int(r['addr'], 16))
sm1_addr = {}
for r in sm1:
    if not r['addr'].startswith('P'):
        sm1_addr[r['name']] = int(r['addr'], 16)
known = set(addr_of) | set(sm1_addr) | {r['name'] for r in sm1}
for r in rows('symbols/sfix.csv'):
    known.add(r['name'])
known |= labels | equs
# former names quoted where a rename is recorded
known |= {'TestCodeNumberCard', 'MvsLedUpdate', 'SelectSlot'}
for doc in docs:
    text = open(doc).read()
    base = os.path.dirname(doc)
    for m in re.finditer(r'\]\(([^)#\s]+)(#[^)]*)?\)', text):
        target = m.group(1)
        if re.match(r'[a-z]+://', target):
            continue
        if not os.path.exists(os.path.join(base, target)):
            bad(f'{doc}: link to missing {target}')
    for m in re.finditer(r'`([A-Za-z_][A-Za-z0-9_]*)`,?\s*\(?`\$([0-9A-F]{4,6})`', text):
        name, a = m.group(1), int(m.group(2), 16)
        if name in addr_of:
            if a not in addr_of[name] and (a | 0xC00000) not in addr_of[name]:
                bad(f'{doc}: `{name}` given as ${m.group(2)}, symbol files say '
                    + ', '.join(f'${x:06X}' for x in sorted(addr_of[name])))
        elif name in sm1_addr and 'sound' in doc + text[:200].lower():
            if a != sm1_addr[name]:
                bad(f'{doc}: `{name}` given as ${m.group(2)}, sm1/names.csv says ${sm1_addr[name]:04X}')
    for m in set(re.findall(r'`([A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+)`', text)):
        if m not in known:
            bad(f'{doc}: `{m}` is not a known name')

print('5. counts')
def tagcount(data):
    c = {}
    for r in data:
        c[r['tag']] = c.get(r['tag'], 0) + 1
    return c
rc, mc, sc = tagcount(rom), tagcount(ram), tagcount(sm1)
checks = [
    (rf'{len(rom)} names \(C {rc.get("C", 0)}, I {rc.get("I", 0)}, W {rc.get("W", 0)}\)', ['ROADMAP.md']),
    (rf'{len(rom)} routines, tables and data blocks named \(C {rc.get("C", 0)}, I {rc.get("I", 0)}, W {rc.get("W", 0)}\)', ['README.md']),
    (rf'{len(ram)} names \(W {mc.get("W", 0)} from the NeoGeoDev wiki, C {mc.get("C", 0)}, I {mc.get("I", 0)}\)', ['README.md']),
    (rf'{len(scoped)} names valid in one part', ['README.md']),
    (rf'{len(sm1)} names in `sm1/names.csv` \(C {sc.get("C", 0)}, I {sc.get("I", 0)}, W {sc.get("W", 0)}, \? {sc.get("?", 0)}\)', ['docs/sound.md']),
]
for pattern, where in checks:
    for doc in where:
        if not re.search(pattern, open(doc).read()):
            bad(f'{doc}: count not found or stale: expected /{pattern}/')
ri = sum(1 for r in rom if r['tag'] == 'I')
ram_i = sum(1 for r in ram + scoped if r['tag'] == 'I')
if not re.search(rf'the {ri} I and {ram_i} RAM I in `symbols/doubts.csv`', open('ROADMAP.md').read()):
    bad(f'ROADMAP.md: doubt counts should read "the {ri} I and {ram_i} RAM I"')
if len(doubts) != ri + ram_i + sum(1 for r in rom + ram + scoped if r['tag'] == '?'):
    bad(f'doubts.csv: {len(doubts)} rows for {ri} + {ram_i} I names')

print('6. tools')
import tempfile
tmp = tempfile.mkdtemp()
for p in sorted(glob.glob('tools/*.py')):
    try:
        py_compile.compile(p, doraise=True, cfile=os.path.join(tmp, 'x.pyc'))
    except py_compile.PyCompileError as e:
        bad(f'{p}: {e.msg.splitlines()[0]}')
for p in sorted(glob.glob('tools/*.sh')):
    if subprocess.run(['bash', '-n', p]).returncode:
        bad(f'{p}: shell syntax error')

print('7. forbidden words')
# the words are kept out of this file: the pattern is decoded from hex at run time
FORBIDDEN = bytes.fromhex('756e692d3f62696f737c756e6976657273652062696f73').decode()
r = subprocess.run(['git', 'grep', '-il', '-E', FORBIDDEN], capture_output=True, text=True)
for f in r.stdout.split():
    bad(f'{f}: forbidden word')
r = subprocess.run(['git', 'log', '--all', '--format=%h %B'], capture_output=True, text=True)
for line in r.stdout.splitlines():
    if re.search(FORBIDDEN, line, re.I):
        bad(f'commit message: {line[:60]}')

print(f'{len(problems)} problem(s)')
sys.exit(1 if problems else 0)
