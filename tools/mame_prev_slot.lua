-- MV-6 board with three cartridges: a coin, then SELECT P2 ("Previous Game" in MAME) on the title.
-- PreviousSlot goes from slot 0 to slot 2; NextSlot would go to slot 1. Prints CurrentSlot on each change.
--   mame neogeo -bios euro -cart1 sengoku2 -cart2 lbowling -cart3 ridhero -rompath ROMS \
--        -video none -sound none -nothrottle -skip_gameinfo -autoboot_script tools/mame_prev_slot.lua
local mem = manager.machine.devices[":maincpu"].spaces["program"]
local function field(name)
  for _, port in pairs(manager.machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end
local coin, prev = field("Coin 1"), field("Previous Game")
local COIN, PREV, LAST = 1500, 1700, 2200
local last = -1
emu.register_frame_done(function()
  local f = manager.machine.screens[":screen"]:frame_number()
  local cs = mem:read_u8(0xD00108)                 -- CurrentSlot
  if cs ~= last then
    print(string.format("frame %d CurrentSlot %d EyecatchSlot %d", f, cs, mem:read_u8(0xD00058)))
    last = cs
  end
  coin:set_value((f >= COIN and f < COIN + 6) and 1 or 0)
  prev:set_value((f >= PREV and f < PREV + 6) and 1 or 0)
  if f >= LAST then manager.machine:exit() end
end)
