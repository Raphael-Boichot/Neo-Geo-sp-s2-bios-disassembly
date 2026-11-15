#!/usr/bin/env python3
"""Boot error and rare-path scenarios: faults faked with MAME debugger breakpoints (forced runs).

Usage: fault_scenarios.py list
       fault_scenarios.py run NAME [NAME...]     coverage runs through mame_coverage.sh
       fault_scenarios.py shot NAME OUT.png      one screenshot at the last frame (MAME with -debug)

Each breakpoint changes a register at the compare that detects the fault, so the system ROM code
runs unchanged from there on. The names say what is faked: these runs prove what the code does
when the fault happens, not that the fault happens. Environment: MAME, MAME_ROMS; HIDDEN_ROMS (a ROM
folder with the hidden-programs build), SAVED_CARD, FORMATTED_CARD (card images) for the card_util_* runs;
MONITOR_ROMS (a folder with one ROM folder per `monitor_test.py` build: illegal, address, privilege, trace,
zerodiv, checksum) for monitor_* and checksum_loop. The test stub's own addresses (free space in the
release) are dropped from those coverage files.
"""
import os
import shutil
import subprocess
import sys
import tempfile

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# MAME DIP switch fields of the MVS hard DIPs and their 'off' value (0 is on)
DIP_OFF = (('Setting Mode', 1), ('Cabinet', 2), ('Controller', 4), ('COMM Setting (Cabinet No.)', 24),
           ('COMM Setting (Link Enable)', 32), ('Free Play', 64), ('Freeze', 128))

# name: (game, LAST, DEBUG_CMDS, extra environment)
SCENARIOS = {
    # MemTestBlock compare at $C13154 (first pattern), test number in d6
    'boot_error_work_ram': ('sengoku2', 300, 'bpset c13154,d6==0,{d1=d1^1; g}', {}),
    'boot_error_backup_ram': ('sengoku2', 300, 'bpset c13154,d6==1,{d1=d1^1; g}', {}),
    'boot_error_palette_bank0': ('sengoku2', 300, 'bpset c13154,d6==2,{d1=d1^1; g}', {}),
    'boot_error_palette_bank1': ('sengoku2', 300, 'bpset c13154,d6==3,{d1=d1^1; g}', {}),
    # VramTest compare at $C130CA
    'boot_error_video_ram': ('sengoku2', 300, 'bpset c130ca,d6==4,{d1=d1^1; g}', {}),
    # VBlank count between two calendar pulses, checked at $C11C10
    'boot_error_calendar': ('sengoku2', 400, 'bpset c11c10,1,{d0=0; g}', {}),
    # system ROM checksum compared at $C11C5C
    'boot_error_system_rom': ('sengoku2', 400, 'bpset c11c5c,1,{d0=d0^1; g}', {}),
    # RAM test of an unformatted 2 KB card, compare at $C11CCA
    'boot_error_memory_card': ('sengoku2', 400, 'bpset c11cca,1,{d1=d1^1; g}', {'MEMCARD': 'card'}),
    # Z80 reply read from REG_SOUND at $C12028, tested at $C1202E
    'boot_error_z80': ('sengoku2', 900, 'bpset c1202e,1,{d0=0; g}', {}),
    # AES form of the error screen: Z set after tst.b SystemType, so the beq at $C16AEE is taken (with the work RAM fault)
    # BIOS_COUNTRY_CODE read as 1 (USA) by the game when it copies it (forced: SP-S2 is a European BIOS, code 2).
    # Top Player's Golf ($1001F1) and Baseball Stars Professional ($100006) then take the credit themselves
    # when play begins (CREDIT_CHECK then CREDIT_DOWN, credits 07 -> 06), not at START
    'tpgolf_us_credit_down': ('tpgolf', 2300, 'bpset 108a,1,{b@10fd83=1; g}||bpset 19ee,1,{b@10fd83=1; g}',
                              {'KEYS': '1500:Coin 1,1530:Coin 1,1560:Coin 1,1590:Coin 2,1620:Coin 2,1700:1 Player Start,' + ','.join(f'{f}:P1 A' for f in range(1800, 2300, 45))}),
    'bstars_us_credit_down': ('bstars', 2300, 'bpset 11fe,1,{b@10fd83=1; g}||bpset 12b6,1,{b@10fd83=1; g}',
                              {'KEYS': '1500:Coin 1,1530:Coin 1,1560:Coin 1,1590:Coin 2,1620:Coin 2,1700:1 Player Start,' + ','.join(f'{f}:P1 A' for f in range(1800, 2300, 45))}),
    # end of the eyecatcher with BIOS_COUNTRY_CODE forced (SP-S2 is European, code 2): USA shows the FBI screen,
    # Japan the JAPAN ONLY warning, each for 300 frames (Sengoku 2 leaves the eyecatcher to the system ROM)
    'eyecatcher_us': ('sengoku2', 1100, 'bpset c18208,1,{b@10fd83=1; g}', {'MODE': 'boot'}),
    'eyecatcher_japan': ('sengoku2', 1100, 'bpset c18208,1,{b@10fd83=0; g}', {'MODE': 'boot'}),
    'boot_error_aes_colours': ('sengoku2', 300,
                               'bpset c13154,d6==0,{d1=d1^1; g}||bpset c16aee,1,{sr=sr|4; g}', {}),
    # not forced: every hard DIP switch on at power-on repeats the work and backup RAM tests
    # (WorkRamTestLoop) until a switch is turned off, then the backup RAM is cleared
    'work_ram_test_loop': ('sengoku2', 900, '', {'DIPS': ','.join(
        [f'0:{n}=0' for n, _ in DIP_OFF] + [f'450:{n}={off}' for n, off in DIP_OFF])}),
    # Card utility COPY in the hidden-programs build (HIDDEN_ROMS, tools/hidden_programs_test.py), test-menu
    # EXIT opens the utility; SAVED_CARD is a card holding a save (the Sengoku 2 save of HOWTO section 7),
    # FORMATTED_CARD a formatted card without it. Not forced: the cards are swapped as an operator would.
    'card_util_copy': ('sengoku2', 1500, '', {'ROMS': 'HIDDEN_ROMS', 'MEMCARD': 'card:SAVED_CARD', 'MEMCARD_AT': '0',
        'MEMCARD_OUT': '880', 'MEMCARD2': 'card2:FORMATTED_CARD', 'MEMCARD2_AT': '920',
        'MODE': 'dip', 'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 Down,520:P1 Down,540:P1 A,640:P1 Down,680:P1 Down,720:P1 A,820:P1 A,1000:P1 A,1250:P1 B,1350:P1 Down,1400:P1 A'}),
    'card_util_copy_same_card': ('sengoku2', 1400, '', {'ROMS': 'HIDDEN_ROMS', 'MEMCARD': 'card:SAVED_CARD', 'MEMCARD_AT': '0',
        'MODE': 'dip', 'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 Down,520:P1 Down,540:P1 A,640:P1 Down,680:P1 Down,720:P1 A,820:P1 C,900:P1 A,1000:P1 A,1100:P1 B,1200:P1 A,1300:P1 B'}),
    'card_util_copy_unformatted': ('sengoku2', 1300, '', {'ROMS': 'HIDDEN_ROMS', 'MEMCARD': 'card:SAVED_CARD', 'MEMCARD_AT': '0',
        'MEMCARD_OUT': '880', 'MEMCARD2': 'card2:', 'MEMCARD2_AT': '920',
        'MODE': 'dip', 'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 Down,520:P1 Down,540:P1 A,640:P1 Down,680:P1 Down,720:P1 A,820:P1 A,1000:P1 A,1100:P1 A,1200:P1 A'}),
    # ControllerTest in the hidden-programs build (test-menu item 4): every input bit shown as 0/1; it never returns
    'controller_test': ('sengoku2', 1100, '', {'ROMS': 'HIDDEN_ROMS', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,600-620:P1 Up,640-660:P1 Down,'
                '680-700:P1 Left,720-740:P1 Right,760-780:P1 A,800-820:P1 B,840-860:P1 C,880-900:P1 D,'
                '920-940:1 Player Start,960-980:P2 Up,1000-1020:P2 A,1040-1060:2 Players Start'}),
    # write-protect read as set (MEMCARD_WP): FORMAT, DELETE and FILE USER'S NAME in the utility
    'card_util_write_protected': ('sengoku2', 2200, '', {'ROMS': 'HIDDEN_ROMS', 'MEMCARD': 'card:SAVED_CARD', 'MEMCARD_AT': '0',
        'MEMCARD_WP': '1', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 Down,520:P1 Down,540:P1 A,'
                '640:P1 A,740:P1 A,840:P1 A,940:P1 A,1040:P1 Down,1060:P1 Down,1080:P1 Down,1100:P1 A,'
                '1200:P1 A,1300:P1 A,1400:P1 A,1500:P1 A,1600:P1 Down,1620:P1 A,1720:P1 A,1820:P1 A,1920:P1 A,2020:P1 A'}),
    # CHECKSUM_LOOP called from test-menu item 4 (monitor_test.py checksum build, forced: nothing calls the slot):
    # sums the cartridge P ROM bytes, stores the sum at $100000, then loops until the watchdog resets the system
    'checksum_loop': ('sengoku2', 800, '', {'ROMS': 'MONITOR_ROMS/checksum', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A'}),
    # debug monitor, test builds of tools/monitor_test.py (forced: the release slots jump to Reset). The first one
    # goes through every command: display memory and V-RAM, modify memory, V-RAM and a register, TRACE, RUN
    'monitor_illegal_commands': ('sengoku2', 3720, '', {'ROMS': 'MONITOR_ROMS/illegal', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,620:P1 Right,640:P1 Right,660-700:P1 Up,720:P1 Down,740:P1 Left,760:P1 Left,780:P1 Left,800:P1 C,840:P1 D,870:P1 B,900:P1 Up,920:P1 C,960:P1 A,1000:P1 Right,1020:P1 Right,1040-1080:P1 Up,1100:P1 Down,1120:P1 Left,1140:P1 Left,1160:P1 Left,1180:P1 C,1220:P1 D,1250:P1 B,1280:P1 Up,1300:P1 C,1340:P1 A,1380:P1 Right,1400:P1 Right,1420-1460:P1 Up,1480:P1 Down,1500:P1 Left,1520:P1 Left,1540:P1 Left,1560:P1 C,1600:P1 D,1630:P1 B,1660:P1 Up,1680:P1 C,1720:P1 A,1760:P1 Right,1780:P1 Right,1800-1840:P1 Up,1860:P1 Down,1880:P1 Left,1900:P1 Left,1920:P1 Left,1940:P1 C,1980:P1 D,2010:P1 B,2040:P1 Up,2060:P1 C,2100:P1 A,2140:P1 Right,2160:P1 Right,2180-2220:P1 Up,2240:P1 Down,2260:P1 Left,2280:P1 Left,2300:P1 Left,2320:P1 C,2360:P1 D,2390:P1 B,2420:P1 Up,2440:P1 C,2480:P1 A,2520:P1 Right,2540:P1 Right,2560-2600:P1 Up,2620:P1 Down,2640:P1 Left,2660:P1 Left,2680:P1 Left,2700:P1 C,2740:P1 D,2770:P1 B,2800:P1 Up,2820:P1 C,2860:P1 A,2900:P1 Right,2920:P1 Right,2940-2980:P1 Up,3000:P1 Down,3020:P1 Left,3040:P1 Left,3060:P1 Left,3080:P1 C,3120:P1 D,3150:P1 B,3180:P1 Up,3200:P1 C,3240:P1 A,3280:P1 Right,3300:P1 Right,3320-3360:P1 Up,3380:P1 Down,3400:P1 Left,3420:P1 Left,3440:P1 Left,3460:P1 C,3500:P1 D,3530:P1 B,3560:P1 Up,3580:P1 C,3620:P1 A'}),
    'monitor_address': ('sengoku2', 700, '', {'ROMS': 'MONITOR_ROMS/address', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,600:P1 C,640:P1 A'}),
    'monitor_privilege': ('sengoku2', 700, '', {'ROMS': 'MONITOR_ROMS/privilege', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,600:P1 C,640:P1 A'}),
    'monitor_trace': ('sengoku2', 700, '', {'ROMS': 'MONITOR_ROMS/trace', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,600:P1 C,640:P1 A'}),
    'monitor_zerodiv': ('sengoku2', 700, '', {'ROMS': 'MONITOR_ROMS/zerodiv', 'MODE': 'dip',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,600:P1 C,640:P1 A'}),
    # CardFillTest (unreferenced card save loop) from test-menu item 4 (monitor_test.py cardfill build, forced): fills
    # a formatted card in one frame (27 saves), CARD 3 returns $84 and CardError shows the full-card list (both pages);
    # A deletes the selected data and saves again, B gives up; CardFillTest then loops until the watchdog resets
    'card_full_delete': ('sengoku2', 1300, '', {'ROMS': 'MONITOR_ROMS/cardfill', 'MODE': 'dip',
        'MEMCARD': 'card:FORMATTED_CARD', 'MEMCARD_AT': '0',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,'
                + ','.join(f'{700 + 30 * i}:P1 Down' for i in range(7)) + ',960:P1 Up,990:P1 Up,1100:P1 A'}),
    'card_full_exit': ('sengoku2', 1300, '', {'ROMS': 'MONITOR_ROMS/cardfill', 'MODE': 'dip',
        'MEMCARD': 'card:FORMATTED_CARD', 'MEMCARD_AT': '0',
        'KEYS': '420:P1 Down,440:P1 Down,460:P1 Down,480:P1 Down,500:P1 A,'
                + ','.join(f'{700 + 30 * i}:P1 Down' for i in range(7)) + ',960:P1 Up,990:P1 Up,1100:P1 B'}),
    # League Bowling offers MEMORY CARD SAVE before the first frame; YES (A) calls CARD 3 then CARD_ERROR.
    # Blank card: result $81, CardError formats it (MVS) and saves again. Write-protected (MEMCARD_WP):
    # $85, MEMORY CARD WRITE PROTECTED. PUSH ANY BUTTON. Not forced (the switch is emulated).
    'lbowling_card_format': ('lbowling', 2500, '', {'MEMCARD': 'card2:', 'MEMCARD_AT': '0', 'KEYS': '1500:Coin 1,1530:Coin 1,1560:Coin 1,1600:1 Player Start,1700:P1 A,1800:P1 A,1900:P1 A,2000:P1 A,2200:P1 A,2400:P1 A'}),
    'lbowling_card_write_protected': ('lbowling', 2500, '', {'MEMCARD': 'card2:', 'MEMCARD_AT': '0', 'MEMCARD_WP': '1',
                                                             'KEYS': '1500:Coin 1,1530:Coin 1,1560:Coin 1,1600:1 Player Start,1700:P1 A,1800:P1 A,1900:P1 A,2000:P1 A,2200:P1 A,2400:P1 A'}),
}


def env_of(name, tmp):
    g, last, cmds, extra = SCENARIOS[name]
    e = {'MODE': 'boot', 'LAST': str(last)}
    if cmds:
        e['DEBUG_CMDS'] = cmds
    for k, v in extra.items():
        if v == 'card':
            v = os.path.join(tmp, name + '.neo')
        elif v.startswith(('card:', 'card2:')):
            tag, src = v.split(':', 1)          # a fresh copy of a card image (or a blank card)
            v = os.path.join(tmp, f'{name}_{tag}.neo')
            if src:
                shutil.copy(os.environ[src], v)
        e[k] = v
    return g, e


def roms_of(e):
    roms = e.pop('ROMS', None)
    if not roms:
        return os.environ.get('MAME_ROMS', 'mame/roms')
    var, _, sub = roms.partition('/')
    return os.path.join(os.environ[var], sub)


def drop_stub(name):
    """Remove addresses in free space of the release (the monitor_test.py stub) from a coverage file."""
    rom = open(os.path.join(R, 'build', 'sp-s2.bin'), 'rb').read()
    path = os.path.join(R, 'coverage', name + '.txt')
    keep = [a for a in open(path).read().split() if rom[int(a, 16) - 0xC00000:][:2] != b'\xff\xff']
    open(path, 'w').write('\n'.join(keep) + '\n')


def main():
    if len(sys.argv) < 2 or sys.argv[1] == 'list':
        for n, (g, last, cmds, _) in SCENARIOS.items():
            print(f'{n:26s} {g:9s} {last:5d}  {cmds}')
        return
    tmp = tempfile.mkdtemp()
    if sys.argv[1] == 'run':
        for n in sys.argv[2:]:
            g, e = env_of(n, tmp)
            stub = e.get('ROMS', '').startswith('MONITOR_ROMS')
            env = dict(os.environ, MAME_ROMS=roms_of(e))
            subprocess.run([os.path.join(R, 'tools', 'mame_coverage.sh'), n, g] + [f'{a}={b}' for a, b in e.items()],
                           check=True, env=env)
            if stub:
                drop_stub(n)
    elif sys.argv[1] == 'shot':
        n, out = sys.argv[2], os.path.abspath(sys.argv[3])
        g, e = env_of(n, tmp)
        roms = roms_of(e)
        e['STEP'] = e['LAST']
        env = dict(os.environ, **e)
        subprocess.run([os.environ.get('MAME', 'mame'), g, '-bios', 'euro', '-rompath', roms,
                        '-cfg_directory', os.path.join(tmp, 'cfg'), '-nvram_directory', os.path.join(tmp, 'nv'),
                        '-snapshot_directory', os.path.join(tmp, 'snap'), '-video', 'none', '-sound', 'none',
                        '-nothrottle', '-skip_gameinfo', '-debug', '-debugger', 'none',
                        '-autoboot_script', os.path.join(R, 'tools', 'mame_run.lua')],
                       env=env, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        shots = sorted(os.path.join(r, f) for r, _, fs in os.walk(os.path.join(tmp, 'snap')) for f in fs)
        shutil.copy(shots[-1], out)          # the last frame (names end with the frame number)
        print(out)
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    main()
