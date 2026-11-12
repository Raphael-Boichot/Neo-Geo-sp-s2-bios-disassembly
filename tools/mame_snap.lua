-- MAME autoboot script: save screenshots of the running BIOS at given frames.
-- mame ng_mv1 -bios euro -rompath roms -snapshot_directory snap -video none \
--      -sound none -nothrottle -autoboot_script tools/mame_snap.lua
local shots = {60, 180, 300, 600}
local i = 1
emu.register_frame_done(function()
  local scr = manager.machine.screens[":screen"]
  local f = scr:frame_number()
  if i <= #shots and f >= shots[i] then
    scr:snapshot(string.format("frame_%04d.png", f))
    i = i + 1
  end
  if f > shots[#shots] + 5 then manager.machine:exit() end
end)
