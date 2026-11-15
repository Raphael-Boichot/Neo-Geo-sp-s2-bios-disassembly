-- Shared inputs for mame_run.lua and mame_trace.lua (loaded with dofile). Environment:
--   KEYS="420:P1 Down,600-700:P1 A"   F: one-frame tap, F-G: held from F to G; any input name, several per frame.
--        "P1 Select" and "P2 Select" (not MAME inputs on MVS) clear bit 1 / 3 of REG_STATUS_B through a read tap
--   MEMCARD_WP=1   the same tap sets bit 6 of REG_STATUS_B: the memory card reads as write-protected
--   DIPS="2:Setting Mode=0,900:Free Play=0"   sets a DIP switch field (values as MAME lists them) at frame F
--   MEMCARD=<file> MEMCARD_AT=<frame>   creates (or loads) a memory card image at that frame (default 0);
--                                       MEMCARD_FROM=<file> first copies that image (a formatted card) to MEMCARD;
--                                       MEMCARD_OUT=<frame> removes it again;
--                                       MEMCARD2=<file> MEMCARD2_AT=<frame> then inserts a second card
--   CARD1M=<file>   emulates a 1 Mbit (64K x 16-bit) RAM card at $800000-$81FFFF with memory taps, kept in
--                   <file> (created blank if missing, saved when MAME stops). MAME itself only has the 2 KB
--                   8-bit card (high byte $FF, mirrored every $1000), so a MEMCARD must also be inserted for
--                   the card-present bits of REG_STATUS_B.
--   CARD1M_AT=<frame> install the emulated card at that frame only (default 0)
--   CARD1M_SPARSE=1 the same card without address line A1: $800000 and $800002 are the same word (the card
--                   type $80 of CardDetect, a 16-bit card answering on every other word)
-- Returns a function to call once per frame with the frame number.
local function field(name)
  for _, port in pairs(manager.machine.ioport.ports) do
    if port.fields[name] then return port.fields[name] end
  end
end
local keys = {}
for a, b, n in string.gmatch(os.getenv("KEYS") or "", "(%d+)%-?(%d*):([^,]+)") do
  keys[#keys + 1] = {tonumber(a), tonumber(b) or tonumber(a), n}
end
local dips = {}
for f, n, v in string.gmatch(os.getenv("DIPS") or "", "(%d+):([^=,]+)=(%d+)") do
  dips[#dips + 1] = {tonumber(f), n, tonumber(v)}
end
local card, card_at, card_out = os.getenv("MEMCARD"), tonumber(os.getenv("MEMCARD_AT") or "0"),
  tonumber(os.getenv("MEMCARD_OUT") or "-1")
local function card_image()
  for tag, im in pairs(manager.machine.images) do
    if tag:find("memcard") then return im end
  end
end
local c1m_path, c1m, c1m_taps = os.getenv("CARD1M"), nil, {}
local c1m_shift = os.getenv("CARD1M_SPARSE") == "1" and 2 or 1   -- word index = offset >> 1, or >> 2 without A1
local c1m_at = tonumber(os.getenv("CARD1M_AT") or "0")
if c1m_path then
  c1m = {}
  local h = io.open(c1m_path, "rb")
  local data = h and h:read("a") or ""
  if h then h:close() end
  for i = 0, 0xFFFF do
    local hi, lo = data:byte(2 * i + 1), data:byte(2 * i + 2)
    c1m[i] = hi and (hi << 8 | lo) or 0xFFFF
  end
  C1M_STOP = emu.add_machine_stop_notifier(function()   -- keep the subscription: garbage collection drops it
    local parts = {}
    for i = 0, 0xFFFF do parts[#parts + 1] = string.char(c1m[i] >> 8, c1m[i] & 0xFF) end
    local o = io.open(c1m_path, "wb"); o:write(table.concat(parts)); o:close()
  end)
end
local function c1m_install()   -- taps are dropped when MAME rebuilds the memory map: install them again each frame
  local sp = manager.machine.devices[":maincpu"].spaces["program"]
  for _, t in ipairs(c1m_taps) do t:remove() end
  c1m_taps = {
    sp:install_read_tap(0x800000, 0x81FFFF, "card1m_r", function(offset, data, mask)
      return c1m[(offset - 0x800000) >> c1m_shift] & mask | data & ~mask & 0xFFFF end),
    sp:install_write_tap(0x800000, 0x81FFFF, "card1m_w", function(offset, data, mask)
      local i = (offset - 0x800000) >> c1m_shift
      c1m[i] = c1m[i] & ~mask & 0xFFFF | data & mask end),
  }
end
local card_wp = os.getenv("MEMCARD_WP") == "1"   -- REG_STATUS_B bit 6 set: card write-protected
local sel_taps, sel_bits = {}, 0
local function sel_install()
  local sp = manager.machine.devices[":maincpu"].spaces["program"]
  for _, t in ipairs(sel_taps) do t:remove() end
  sel_taps = { sp:install_read_tap(0x380000, 0x380001, "select_r", function(offset, data, mask)
    local v = data & ~(sel_bits << 8) & 0xFFFF       -- REG_STATUS_B is the high byte; SELECT is active low
    if card_wp then v = v | 0x4000 end
    return v end) }
end
local has_select = (os.getenv("KEYS") or ""):find("Select") ~= nil or card_wp
return function(f)
  if c1m and f >= c1m_at then c1m_install() end
  if has_select then
    sel_bits = 0
    for _, k in ipairs(keys) do
      if f >= k[1] and f <= k[2] then
        if k[3] == "P1 Select" then sel_bits = sel_bits | 2 elseif k[3] == "P2 Select" then sel_bits = sel_bits | 8 end
      end
    end
    sel_install()
  end
  for _, k in ipairs(keys) do
    local fl = field(k[3])
    if fl then
      if f >= k[1] and f <= k[2] then fl:set_value(1) elseif f == k[2] + 1 then fl:set_value(0) end
    end
  end
  for _, d in ipairs(dips) do
    if f == d[1] then local fl = field(d[2]); if fl then fl.user_value = d[3] end end
  end
  if card and f == card_at then
    local from = os.getenv("MEMCARD_FROM")
    if from then
      local i, o = io.open(from, "rb"), io.open(card, "wb")
      o:write(i:read("a")); i:close(); o:close()
    end
    local img = card_image()
    if img then
      local h = io.open(card, "rb")
      if h then h:close(); img:load(card) else img:create(card) end
    end
  end
  if card and f == card_out then local img = card_image(); if img then img:unload() end end
  local card2, card2_at = os.getenv("MEMCARD2"), tonumber(os.getenv("MEMCARD2_AT") or "-1")
  if card2 and f == card2_at then
    local img = card_image()
    if img then
      local h = io.open(card2, "rb")
      if h then h:close(); img:load(card2) else img:create(card2) end
    end
  end
end
