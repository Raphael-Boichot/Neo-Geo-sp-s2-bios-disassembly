# Neo Geo SP-S2 system ROM - build from src/ with GNU binutils (m68k)
PY      ?= python3
AS      := m68k-linux-gnu-as -m68000 --register-prefix-optional
LD      := m68k-linux-gnu-ld -Ttext=0xC00000 -e 0xC00402 --oformat binary
ROM_SHA1 := 4f5ed7105b7128794654ce82b51723e16e389543
# original dump, MAME order; only needed for `make source`
ROM     ?= roms/sp-s2.sp1

all: build/sp-s2.sp1

build/sp-s2.o: src/sp-s2.s src/neogeo.inc src/ram.inc
	@mkdir -p build
	$(AS) -I src -al=build/sp-s2.lst -o $@ src/sp-s2.s

build/sp-s2.bin: build/sp-s2.o
	$(LD) -o $@ $<

# MAME/EPROM order (16-bit words byte-swapped)
build/sp-s2.sp1: build/sp-s2.bin
	$(PY) tools/romtool.py swap $< $@

# compare with the original ROM (no ROM needed: SHA-1 only)
check: build/sp-s2.sp1
	$(PY) tools/romtool.py check $< $(ROM_SHA1)
	$(PY) tools/romtool.py checksum $<

# rewrite the boot checksum of a modified build
fixsum: build/sp-s2.sp1
	$(PY) tools/romtool.py checksum $< --fix

# regenerate src/ from the ROM - OVERWRITES hand edits in src/
source:
	$(PY) tools/gen_source.py $(ROM) src tools/hints.txt

clean:
	rm -rf build

.PHONY: all check fixsum source clean
