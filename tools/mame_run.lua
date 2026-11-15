-- MAME autoboot script: screenshots of the running BIOS, optional test mode and joystick taps.
-- Environment: MODE=boot|dip|test (dip: "Setting Mode" DIP on, test: hold the test button),
--   LAST=<last frame>, STEP=<frames between shots>; KEYS, DIPS, MEMCARD as in mame_inputs.lua.
-- Use a fresh -cfg_directory per run: MAME saves DIP settings in its cfg files.
local mode = os.getenv("MODE") or "boot"
local last = tonumber(os.getenv("LAST") or "1800")
local step = tonumber(os.getenv("STEP") or "30")
local dsw = manager.machine.ioport.ports[":DSW"].fields["Setting Mode"]
local test = manager.machine.ioport.ports[":TEST"].fields["Service Mode"]
local function field(name)   -- find an input by name in any port
  for _, port in pairs(manager.machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end
-- DEBUG_CMDS (needs -debug -debugger none): debugger commands separated by "||", e.g. a breakpoint faking a fault
local dbg = manager.machine.debugger
if dbg and os.getenv("DEBUG_CMDS") then
  for c in (os.getenv("DEBUG_CMDS") .. "||"):gmatch("(.-)||") do if c ~= "" then dbg:command(c) end end
  dbg:command("go")
end
local inputs = dofile((debug.getinfo(1, "S").source:match("^@(.*[/\\])") or "") .. "mame_inputs.lua")
emu.register_frame_done(function()
  local scr = manager.machine.screens[":screen"]
  local f = scr:frame_number()
  if mode == "dip" and f < 2 then dsw.user_value = 0 end
  if mode == "test" then test:set_value(f < 300 and 1 or 0) end
  inputs(f)
  if f % step == 0 then scr:snapshot(string.format("%s_%05d.png", mode, f)) end
  if f >= last then manager.machine:exit() end
end)
