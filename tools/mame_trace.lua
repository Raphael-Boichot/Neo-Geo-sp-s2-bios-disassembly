-- MAME autoboot script for coverage: starts the debugger trace (needs -debug),
-- then sets inputs and quits like mame_run.lua.
-- Environment: TRACEFILE=<file or fifo>, LAST, MODE=dip, KEYS="420:P1 Down,...", DEBUG_CMDS
local dbg = manager.machine.debugger
if dbg then
  dbg:command("trace " .. os.getenv("TRACEFILE") .. ",maincpu,noloop")
  -- DEBUG_CMDS: extra debugger commands separated by "||", e.g. a breakpoint that changes registers
  for c in string.gmatch(os.getenv("DEBUG_CMDS") or "", "([^|]+)") do dbg:command(c) end
  dbg:command("go")
  print("trace started")
else
  print("no debugger")
end
local last = tonumber(os.getenv("LAST") or "600")
local dsw = manager.machine.ioport.ports[":DSW"].fields["Setting Mode"]
local function field(name)
  for _, port in pairs(manager.machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end
local keys = {}
for f, n in string.gmatch(os.getenv("KEYS") or "", "(%d+):([^,]+)") do keys[tonumber(f)] = n end
local held = nil
emu.register_frame_done(function()
  local f = manager.machine.screens[":screen"]:frame_number()
  if os.getenv("MODE") == "dip" and f < 2 then dsw.user_value = 0 end
  if held then held:set_value(0); held = nil end
  if keys[f] then held = field(keys[f]); held:set_value(1) end
  if f >= last then manager.machine:exit() end
end)
