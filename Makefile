# Neo Geo SP-S2 system ROM - build from src/ with GNU binutils (m68k)
PY      ?= python3
AS      := m68k-linux-gnu-as -m68000 --register-prefix-optional
LD      := m68k-linux-gnu-ld -Ttext=0xC00000 -e 0xC00402 --oformat binary
ROM_SHA1 := 4f5ed7105b7128794654ce82b51723e16e389543
SFIX_SHA1 := fd4a618cdcdbf849374f0a50dd8efe9dbab706c3
LO_SHA1   := 5992277debadeb64d1c1c64b0a92d9293eaf7e4a
SM1_SHA1  := 42f9d7ddd6c0931fd64226a60dc73602b2819dcf
# original dump, MAME order; only needed for `make source`
ROM     ?= roms/sp-s2.sp1
SFIX    ?= roms/sfix.sfix
SM1     ?= roms/sm1.sm1

all: build/sp-s2.sp1 build/sfix.sfix build/000-lo.lo build/sm1.sm1

build/sp-s2.o: $(wildcard src/*.s src/*.inc)
	@mkdir -p build
	$(AS) -I src -al=build/sp-s2.lst -o $@ src/sp-s2.s

build/sp-s2.bin: build/sp-s2.o
	$(LD) -o $@ $<

# MAME/EPROM order (16-bit words byte-swapped)
build/sp-s2.sp1: build/sp-s2.bin
	$(PY) tools/romtool.py swap $< $@

# board fix ROM (sfix.sfix) from its tile sheets
build/sfix.sfix: $(wildcard gfx/sfix/*.png) tools/sfix.py
	$(PY) tools/sfix.py build gfx/sfix $@

# sprite shrink table (000-lo.lo, L0 ROM) from its rule
build/000-lo.lo: tools/lo_rom.py
	@mkdir -p build
	$(PY) tools/lo_rom.py build $@

# board Z80 sound program (sm1.sm1) from sm1/src/sm1.asm (z80asm)
build/sm1.sm1: sm1/src/sm1.asm tools/sm1.py
	@mkdir -p build
	$(PY) tools/sm1.py build $< $@

# compare with the original ROMs (no ROM needed: SHA-1 only)
check: build/sp-s2.sp1 build/sfix.sfix build/000-lo.lo build/sm1.sm1
	$(PY) tools/romtool.py check build/sp-s2.sp1 $(ROM_SHA1)
	$(PY) tools/romtool.py checksum build/sp-s2.sp1
	$(PY) tools/sfix.py check build/sfix.sfix $(SFIX_SHA1)
	$(PY) tools/lo_rom.py check build/000-lo.lo $(LO_SHA1)
	$(PY) tools/sm1.py check build/sm1.sm1 $(SM1_SHA1)

# rewrite the boot checksum of a modified build
fixsum: build/sp-s2.sp1
	$(PY) tools/romtool.py checksum $< --fix

# regenerate src/ from the ROM - OVERWRITES hand edits in src/
source:
	$(PY) tools/gen_source.py $(ROM) src tools/hints.txt

# consistency of symbols, doubts, sources, documents, stated counts, tools
consistency:
	$(PY) tools/check_repo.py

# regenerate sm1/src/sm1.asm from the sound ROM, sm1/names.csv and sm1/hints.txt
sm1-source:
	$(PY) tools/sm1.py source $(SM1)

# regenerate gfx/sfix/ from the board fix ROM - OVERWRITES edited sheets
sfix-source:
	$(PY) tools/sfix.py extract $(SFIX) gfx/sfix

clean:
	rm -rf build

.PHONY: all check fixsum source sfix-source sm1-source consistency clean
