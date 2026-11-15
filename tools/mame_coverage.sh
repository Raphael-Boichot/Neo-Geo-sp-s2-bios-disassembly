#!/bin/bash
# Traced MAME run of SP-S2: writes the unique executed addresses to coverage/NAME.txt
# usage: tools/mame_coverage.sh NAME GAME [VAR=value ...]   (variables as in tools/mame_trace.lua)
# MAME binary: MAME (default mame). ROMs: MAME_ROMS (default mame/roms) must hold neogeo.zip and the game set.
# NVRAM_DIR: keep the backup RAM between runs (default: a fresh one per run).
set -e
R=$(cd "$(dirname "$0")/.." && pwd)
name=$1; game=$2; shift 2
ROMS=${MAME_ROMS:-$R/mame/roms}
W=$(mktemp -d)
mkfifo "$W/trace"
python3 -I -c '
import sys
seen = set()
for line in open(sys.argv[1], "rb"):
    if line[6:7] == b":":
        seen.add(line[:6].decode())
open(sys.argv[2], "w").write("".join(a + "\n" for a in sorted(seen) if a.startswith(("C0", "C1"))))
' "$W/trace" "$R/coverage/$name.txt" &
AGG=$!
mkdir -p "$R/coverage"
env TRACEFILE="$W/trace" "$@" ${MAME:-mame} "$game" -bios euro -rompath "$ROMS" \
  -cfg_directory "$W/cfg" -nvram_directory "${NVRAM_DIR:-$W/nvram}" -video none -sound none -nothrottle \
  -debug -debugger none -autoboot_script "$R/tools/mame_trace.lua" -skip_gameinfo >/dev/null 2>&1 || true
( exec 3>"$W/trace" ) >/dev/null 2>&1 &   # unblock the reader if MAME never opened the pipe
UNBLOCK=$!
wait $AGG
kill $UNBLOCK 2>/dev/null || true          # otherwise it waits forever for a reader and holds our output
rm -rf "$W"
wc -l "$R/coverage/$name.txt"
