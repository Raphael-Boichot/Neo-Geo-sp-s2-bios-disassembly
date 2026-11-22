-- Mahjong Kyoretsuden with the mahjong panel on P1 and hard DIP 3 on: every mahjong key pressed in turn,
-- a coin and a start; traces the 68000 into TRACEF, where MahjongKeysToJoystick ($C1861C),
-- MahjongStartFilter, UpdateMahjongRow and ReadMahjongRows then appear.
--   TRACEF=out.trace mame neogeo -bios euro -cart1 mahretsu -ctrl1 mahjong -rompath ROMS -debug \
--        -debugger none -video none -sound none -nothrottle -skip_gameinfo -autoboot_script tools/mame_mahjong.lua
local dbg = manager.machine.debugger
dbg:command("trace " .. os.getenv("TRACEF") .. ",maincpu,noloop")
dbg:command("go")
local keys, dip, coin, start = {}, nil, nil, nil
for pn, port in pairs(manager.machine.ioport.ports) do
  if pn:find("ctrl1") then for _, fl in pairs(port.fields) do keys[#keys + 1] = fl end end
  if port.fields["Controller"] then dip = port.fields["Controller"] end
  if port.fields["Coin 1"] then coin = port.fields["Coin 1"] end
  if port.fields["1 Player Start"] then start = port.fields["1 Player Start"] end
end
emu.register_frame_done(function()
  local f = manager.machine.screens[":screen"]:frame_number()
  if f < 2 and dip then dip.user_value = 0 end      -- hard DIP 3 on: mahjong panel
  for i, fl in ipairs(keys) do fl:set_value(((f // 10) % (#keys + 4) == i and f > 600) and 1 or 0) end
  coin:set_value((f >= 1200 and f < 1206) and 1 or 0)
  start:set_value((f >= 1400 and f < 1406) and 1 or 0)
  if f >= 2400 then manager.machine:exit() end
end)
