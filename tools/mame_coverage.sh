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
LOG="$R/coverage/$name.log"               # MAME's output, kept when the run fails
rc=0
env TRACEFILE="$W/trace" "$@" ${MAME:-mame} "$game" -bios euro -rompath "$ROMS" \
  -cfg_directory "$W/cfg" -nvram_directory "${NVRAM_DIR:-$W/nvram}" -video none -sound none -nothrottle \
  -debug -debugger none -autoboot_script "$R/tools/mame_trace.lua" -skip_gameinfo >"$LOG" 2>&1 || rc=$?
( exec 3>"$W/trace" ) >/dev/null 2>&1 &   # unblock the reader if MAME never opened the pipe
UNBLOCK=$!
wait $AGG
kill $UNBLOCK 2>/dev/null || true          # otherwise it waits forever for a reader and holds our output
rm -rf "$W"
# fail closed: MAME must exit normally (the trace script ends it with machine:exit()) and the trace
# must hold system ROM addresses; otherwise the coverage file is removed and the log kept
n=$(wc -l <"$R/coverage/$name.txt")
if [ "$rc" -ne 0 ] || [ "$n" -lt ${MIN_ADDRESSES:-20} ]; then
  echo "coverage run $name FAILED: MAME exit status $rc, $n addresses; log in coverage/$name.log" >&2
  tail -5 "$LOG" >&2
  rm -f "$R/coverage/$name.txt"
  exit 1
fi
rm -f "$LOG"
echo "$n $R/coverage/$name.txt"
