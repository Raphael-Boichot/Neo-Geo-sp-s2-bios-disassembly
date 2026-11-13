-- Sengoku 2 play bot for MAME (autoboot script), used to reach level 2 and the card save.
-- Walk right 45 frames, mash A facing right 45 frames, turn left and mash A 45 frames;
-- coin + START for continues (NOCONT=1 disables them), IDLE=1 gives no input at all.
-- Creates/loads the memory card MEMCARD, saves a MAME state every 1,200 frames.
-- Rules from the repository owner: go right, mash A when enemies come, wait in the fixed
-- scenes; too slow brings the spiked cart; the game offers SAVE when you lose in level 2.
-- create (or load) a memory card image before the BIOS looks at it
local path = os.getenv("MEMCARD")
if path then
  local img = nil
  for tag, im in pairs(manager.machine.images) do
    if tag:find("memcard") then img = im end
  end
  if img then
    local f = io.open(path, "rb")
    if f then f:close(); print("load", img:load(path)) else print("create", img:create(path)) end
  else
    print("no memcard image device")
  end
end
-- Sengoku 2 bot: walk right, mash A facing right, then facing left; coin + START for continues.
-- Saves a state every 1200 frames and logs when the memory card contents change.
local function field(name)
  for _, port in pairs(manager.machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end
local right, left, a, b, c = field("P1 Right"), field("P1 Left"), field("P1 A"), field("P1 B"), field("P1 C")
local coin, start = field("Coin 1"), field("1 Player Start")
local cpu = manager.machine.devices[":maincpu"]
local space = cpu.spaces["program"]
local last = tonumber(os.getenv("LAST") or "30000")
local log = io.open(os.getenv("BOTLOG") or "bot.log", "w")
local function cardsum()
  local s = 0
  for i = 0, 0x7FF do s = (s * 31 + space:read_u8(0x800000 + i * 2 + 1)) % 1000000007 end
  return s
end
local prev = nil
emu.register_frame_done(function()
  local scr = manager.machine.screens[":screen"]
  local f = scr:frame_number()
  if f > tonumber(os.getenv("FIRST") or "1500") then
    local p = f % 135   -- walk right 45, attack right 45, turn left and attack 45
    right:set_value((p < 45) and 1 or 0)
    left:set_value((p >= 90 and p < 93) and 1 or 0)
    a:set_value((p >= 45 and f % 2 == 0) and 1 or 0)   -- fixed scenes: wait and mash A, both sides
    b:set_value(0)                                 -- no jump
    c:set_value(0)
    coin:set_value((os.getenv("NOCONT") == nil and f % 300 >= 10 and f % 300 < 14) and 1 or 0)
    start:set_value((os.getenv("NOCONT") == nil and f % 60 < 3) and 1 or 0)
  end
  if f % 60 == 0 then
    local s = cardsum()
    if prev and s ~= prev then log:write(string.format("card changed at frame %d\n", f)); log:flush() end
    prev = s
  end
  if f % 1200 == 0 and f >= 1200 then
    manager.machine:save(string.format("s%05d", f))
    scr:snapshot(string.format("%s_%05d.png", os.getenv("TAG") or "bot", f))
  end
  if f >= last then log:close(); manager.machine:exit() end
end)
