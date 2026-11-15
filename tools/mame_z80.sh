#!/bin/bash
# Traced MAME run of the sound CPU: build/z80/NAME.tr (Z80 trace), NAME.out (sound commands by
# frame), NAME.wav (the sound). GAME neogeo = no cartridge, so the board's sm1.sm1 runs throughout.
# usage: tools/mame_z80.sh NAME GAME [VAR=value ...]  (SENDCMD, KEYS, MODE, LAST as in tools/mame_z80.lua)
# example, the sound test sounds with no cartridge:
#   tools/mame_z80.sh sounds neogeo MODE=boot LAST=800 SENDCMD="450:3,460:7,500:5D"
R=$(cd "$(dirname "$0")/.." && pwd)
name=$1; game=$2; shift 2
O=$R/build/z80; mkdir -p "$O"
W=$(mktemp -d)
env TRACEFILE=/dev/null DEBUG_CMDS="trace $O/$name.tr,audiocpu,noloop" "$@" ${MAME:-mame} "$game" -bios euro \
  -rompath "${MAME_ROMS:-$R/mame/roms}" -cfg_directory "$W/cfg" -nvram_directory "$W/nvram" \
  -video none -sound none -wavwrite "$O/$name.wav" -nothrottle -debug -debugger none \
  -autoboot_script "$R/tools/mame_z80.lua" -skip_gameinfo > "$O/$name.out" 2>&1
rm -rf "$W"
grep SOUNDCMD "$O/$name.out"
