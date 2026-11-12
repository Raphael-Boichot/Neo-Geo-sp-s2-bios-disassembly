-- MAME autoboot script: screenshots of the running BIOS, optional test mode and joystick taps.
-- Environment: MODE=boot|dip|test (dip: "Setting Mode" DIP on, test: hold the test button),
--   LAST=<last frame>, STEP=<frames between shots>, KEYS="420:P1 Down,460:P1 A" (one-frame taps).
-- Use a fresh -cfg_directory per run: MAME saves DIP settings in its cfg files.
local mode = os.getenv("MODE") or "boot"
local last = tonumber(os.getenv("LAST") or "1800")
local step = tonumber(os.getenv("STEP") or "30")
local dsw = manager.machine.ioport.ports[":DSW"].fields["Setting Mode"]
local test = manager.machine.ioport.ports[":TEST"].fields["Service Mode"]
local p1 = manager.machine.ioport.ports[":edge:joy:JOY1"].fields
local keys = {}
for f, n in string.gmatch(os.getenv("KEYS") or "", "(%d+):([^,]+)") do keys[tonumber(f)] = n end
local held = nil
emu.register_frame_done(function()
  local scr = manager.machine.screens[":screen"]
  local f = scr:frame_number()
  if mode == "dip" and f < 2 then dsw.user_value = 0 end
  if mode == "test" then test:set_value(f < 300 and 1 or 0) end
  if held then held:set_value(0); held = nil end
  if keys[f] then held = p1[keys[f]]; held:set_value(1) end
  if f % step == 0 then scr:snapshot(string.format("%s_%05d.png", mode, f)) end
  if f >= last then manager.machine:exit() end
end)
