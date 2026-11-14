#!/usr/bin/env python3
"""Test mode coverage scenarios: key sequences for every test-mode screen, run with mame_coverage.sh.

Usage: test_mode_scenarios.py list
       test_mode_scenarios.py keys NAME           print the environment of one scenario
       test_mode_scenarios.py run NAME [NAME...]  run them (MAME, MAME_ROMS as for mame_coverage.sh)

All scenarios start in test mode ("Setting Mode" DIP on, MODE=dip): the menu is up at about frame 400.
Keys (seen in MAME): Up/Down move, A/B change a value (held: repeat), Left/Right change the column or
digit, C goes back, D sets (code number, calendar). Inputs are described in tools/mame_inputs.lua.
The card1m_* scenarios emulate a 1 Mbit RAM card (CARD1M in tools/mame_inputs.lua) and must run in order.
Environment: CARD_DIR (where card images and chained backup RAM are written, default .), FORMATTED_CARD (a card image
formatted by a game, for the card scenarios), PLAYED_NVRAM (a MAME nvram folder after a few played
credits, for test_book_keeping_played).
"""
import os
import shutil
import subprocess
import sys

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')


class Keys:
    """Builds a KEYS string: tap/hold at a running frame counter."""
    def __init__(self, start=420):
        self.t, self.k = start, []

    def tap(self, name, gap=20):
        self.k.append(f'{self.t}:P1 {name}' if name in ('Up', 'Down', 'Left', 'Right', 'A', 'B', 'C', 'D')
                      else f'{self.t}:{name}')
        self.t += gap
        return self

    def hold(self, name, frames, gap=20):
        self.k.append(f'{self.t}-{self.t + frames}:P1 {name}')
        self.t += frames + gap
        return self

    def wait(self, frames):
        self.t += frames
        return self

    def menu(self, item):
        """From the main menu (cursor on HARDWARE TEST), open item 0-6."""
        for _ in range(item):
            self.tap('Down')
        return self.tap('A', 60)

    def edit_row(self, holds=60):
        """Change the value under the cursor every way: A, B, held B and A (wraps), other column."""
        self.tap('A').tap('B').hold('B', holds).hold('A', holds)
        return self.tap('Right').tap('A').tap('B').tap('Left')

    def env(self, **extra):
        e = {'MODE': 'dip', 'LAST': str(self.t + 60), 'KEYS': ','.join(self.k)}
        e.update(extra)
        return e


def soft_dip_game(rows=16):
    """SETTING UP THE SOFT DIP (item 2), slot 1: every row of the game's soft DIP, both pages."""
    k = Keys().menu(2).tap('Down', 40).tap('A', 60)
    for _ in range(rows):
        k.edit_row().tap('Down')
    for _ in range(rows):
        k.tap('Up', 8)
    return k.tap('C', 60).tap('C', 60)


def cabinet():
    """SETTING UP THE SOFT DIP (item 2), first line SETTING UP THE CABINET: the 5 coin/cabinet rows."""
    k = Keys().menu(2).tap('A', 60)
    for _ in range(6):
        k.edit_row(100).tap('Down')
    for _ in range(6):
        k.tap('Up', 8)
    return k.tap('C', 60).tap('C', 60)


def book_keeping():
    """BOOK KEEPING (item 3): CABINET/COIN, CABINET/PLAY, slot 1 (daily, months 1-6, 7-12 + total)."""
    k = Keys().menu(3)
    for line in range(3):
        k.tap('A', 60)
        for key in ('Down', 'Down', 'Up', 'Right', 'Left', 'B', 'D', 'A', 'A', 'A', 'A'):
            k.tap(key, 30)
        k.tap('C', 60).tap('Down')
    return k.tap('C', 60)


def hard_dip():
    """SETTING UP THE HARD DIP (item 1) while every DIP switch is turned on, then off again."""
    k = Keys().menu(1).wait(40)
    fields = [('Free Play', 0, 64), ('COMM Setting (Cabinet No.)', 0, 24), ('COMM Setting (Link Enable)', 0, 32),
              ('Freeze', 0, 128), ('Cabinet', 0, 2), ('Controller', 0, 4)]
    dips = []
    for name, on, off in fields:
        dips.append(f'{k.t}:{name}={on}')
        k.wait(30)
    for name, on, off in fields:
        dips.append(f'{k.t}:{name}={off}')
        k.wait(30)
    for key in ('A', 'B', 'D', 'Down', 'Right'):
        k.tap(key, 20)
    k.tap('C', 60)
    return k, ','.join(dips)


def code_number():
    """SETTING UP THE CODE NUMBER (item 4), no card: every digit, wraps, D stores the code."""
    k = Keys().menu(4)
    for _ in range(4):
        k.edit_row(80).tap('Right')
    for _ in range(5):
        k.tap('Left')
    k.tap('A').tap('Right').tap('A').tap('A').tap('D', 120)
    return k.tap('C', 60)


def code_number_card():
    """SETTING UP THE CODE NUMBER with a card in the slot from power-on: set a code, D writes it."""
    k = Keys().menu(4).tap('A').tap('Right').tap('A').tap('A').tap('D', 400)
    return k.tap('C', 60)


def calendar():
    """SETTING UP THE CALENDAR (item 5): every field, wraps both ways, D sets."""
    k = Keys().menu(5)
    for _ in range(7):
        k.tap('A').tap('B').hold('B', 120).hold('A', 120).tap('Right')
    for _ in range(8):
        k.tap('Left')
    k.tap('D', 60)
    return k.tap('C', 60)


def menu_exit():
    """EXIT (item 6), with the Setting Mode DIP still on, then turned off."""
    k = Keys()
    k.tap('Up').menu(6).wait(120)
    dips = f'{k.t}:Setting Mode=1'
    k.wait(60).menu(6).wait(600)
    return k, dips


def scenarios():
    sc = {}
    for game in ('sengoku2', 'ridhero', 'alpham2', 'tpgolf'):
        sc[f'test_soft_dip_{game}'] = (game, soft_dip_game().env())
    sc['test_cabinet'] = ('sengoku2', cabinet().env())
    sc['test_book_keeping_pages'] = ('sengoku2', book_keeping().env())
    k, dips = hard_dip()
    sc['test_hard_dip_switches'] = ('sengoku2', k.env(DIPS=dips))
    sc['test_code_number_digits'] = ('sengoku2', code_number().env())
    sc['test_code_number_card'] = ('sengoku2', code_number_card().env(MEMCARD='card', MEMCARD_AT='0',
                                                                       MEMCARD_FROM='FORMATTED'))
    sc['test_code_number_blank_card'] = ('sengoku2', code_number_card().env(MEMCARD='card', MEMCARD_AT='0'))
    sc['test_book_keeping_played'] = ('sengoku2', book_keeping().env(NVRAM_FROM='PLAYED'))
    # 1M card cabinet backup, run in this order (state passed through CARD_DIR):
    # board A formats the card (code 1200) and saves itself; board B registers the same code and saves;
    # an empty board (no cartridge, Service held) recovers cabinet 1, then cabinet 0 is shown.
    code = Keys().menu(4).tap('A').tap('Right').tap('A').tap('A')
    sc['card1m_format'] = ('sengoku2', code.tap('D', 400).tap('C', 60).env(
        MEMCARD='card', MEMCARD_AT='0', CARD1M='new', NVRAM='keep'))
    sc['card1m_save_a'] = ('sengoku2', {'MODE': 'boot', 'LAST': '1700', 'KEYS': '900-905:P1 Select',
                                        'MEMCARD': 'card', 'MEMCARD_AT': '0', 'CARD1M': 'chain',
                                        'NVRAM': 'from:card1m_format'})
    code_b = Keys().menu(4).tap('A').tap('Right').tap('A').tap('A')
    sc['card1m_code_b'] = ('sengoku2', code_b.tap('D', 300).tap('C', 60).env(NVRAM='keep'))
    sc['card1m_save_b'] = ('sengoku2', {'MODE': 'boot', 'LAST': '1700', 'KEYS': '900-905:P1 Select',
                                        'MEMCARD': 'card', 'MEMCARD_AT': '0', 'CARD1M': 'chain',
                                        'NVRAM': 'from:card1m_code_b'})
    sc['card1m_recover'] = ('neogeo', {'MODE': 'boot', 'LAST': '1100',
                                       'KEYS': '0-400:Service 1,500:P1 Down,560:P1 Down,620:P1 Up,680:P1 Down,'
                                               '760-860:P1 A,760-860:P1 B,760-860:P1 C,760-860:P1 D',
                                       'MEMCARD': 'card', 'MEMCARD_AT': '0', 'CARD1M': 'chain',
                                       'NVRAM': 'from:card1m_save_a'})
    sc['test_calendar_fields'] = ('sengoku2', calendar().env())
    k, dips = menu_exit()
    sc['test_menu_exit'] = ('sengoku2', k.env(DIPS=dips))
    return sc


def main():
    sc = scenarios()
    if len(sys.argv) < 2 or sys.argv[1] == 'list':
        for n, (g, e) in sc.items():
            print(f'{n:28s} {g:9s} {e["LAST"]:>6s} frames')
        return
    if sys.argv[1] == 'keys':
        g, e = sc[sys.argv[2]]
        print(g)
        for a, b in e.items():
            print(f'{a}={b}')
        return
    for n in sys.argv[2:]:
        g, e = sc[n]
        e = dict(e)
        if 'MEMCARD' in e and not n.startswith('card1m'):
            e['MEMCARD'] = os.path.abspath(os.path.join(os.environ.get('CARD_DIR', '.'), n + '.neo'))
            if os.path.exists(e['MEMCARD']):
                os.remove(e['MEMCARD'])
        if e.get('MEMCARD_FROM') == 'FORMATTED':
            # a card formatted by a game, e.g. after the Sengoku 2 save (HOWTO section 7)
            e['MEMCARD_FROM'] = os.path.abspath(os.environ['FORMATTED_CARD'])
        env = dict(os.environ)
        cdir = os.path.abspath(os.environ.get('CARD_DIR', '.'))
        if e.get('MEMCARD') == 'card' and n.startswith('card1m'):
            e['MEMCARD'] = os.path.join(cdir, 'card1m_slot.neo')   # the 2 KB card that MAME sees as inserted
        c1 = e.pop('CARD1M', None)
        if c1:
            e['CARD1M'] = os.path.join(cdir, 'card1m.bin')
            if c1 == 'new':
                for f in (e['CARD1M'], e['MEMCARD']):
                    if os.path.exists(f):
                        os.remove(f)
        nvmode = e.pop('NVRAM', None)
        if nvmode:
            nv = os.path.join(cdir, n + '_nvram')
            shutil.rmtree(nv, ignore_errors=True)
            os.makedirs(os.path.join(nv, g))
            if nvmode.startswith('from:'):
                src = os.path.join(cdir, nvmode[5:] + '_nvram')
                sub = os.listdir(src)[0]   # the folder is named after the system (sengoku2, neogeo)
                shutil.copy(os.path.join(src, sub, 'saveram'), os.path.join(nv, g, 'saveram'))
            env['NVRAM_DIR'] = nv
        if e.pop('NVRAM_FROM', None):
            # backup RAM after a few played credits (PLAYED_NVRAM: a MAME nvram folder), copied
            nv = os.path.abspath(os.path.join(os.environ.get('CARD_DIR', '.'), n + '_nvram'))
            shutil.rmtree(nv, ignore_errors=True)
            shutil.copytree(os.environ['PLAYED_NVRAM'], nv)
            env['NVRAM_DIR'] = nv
        args = [f'{a}={b}' for a, b in e.items()]
        subprocess.run([os.path.join(R, 'tools', 'mame_coverage.sh'), n, g] + args, check=True, env=env)


if __name__ == '__main__':
    main()
