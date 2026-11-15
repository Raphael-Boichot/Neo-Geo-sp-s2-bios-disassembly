-- MAME autoboot script for the Z80 (sound CPU): logs every sound command the Z80 reads on
-- port $00 with the frame number ("SOUNDCMD frame F port P value V" on stdout), optionally
-- writes commands to REG_SOUND from the 68k side, then runs mame_trace.lua (inputs, LAST).
-- Environment: SENDCMD="frame:hex,frame:hex" commands to send; the rest as in mame_trace.lua.
local here = debug.getinfo(1, "S").source:match("^@(.*[/\\])") or ""
local io = manager.machine.devices[":audiocpu"].spaces["io"]
local prog = manager.machine.devices[":maincpu"].spaces["program"]
local scr = manager.machine.screens[":screen"]
_G.z80_command_tap = io:install_read_tap(0x0000, 0xffff, "soundcmd", function(offset, data, mask)
  -- port $00 (read decode mask $0C): the command byte from the 68k
  if offset & 0x0c == 0 and offset & 0x10 == 0 and (offset & 0xff) < 4 then
    print(string.format("SOUNDCMD frame %d port %04X value %02X", scr:frame_number(), offset, data))
  end
  return data
end)
-- port $0C writes: the reply the 68k reads in REG_SOUND ("SOUNDREPLY frame F value V" when it changes;
-- set REPLYLOG=all to log every write)
local last_reply, all_replies = nil, os.getenv("REPLYLOG") == "all"
_G.z80_reply_tap = io:install_write_tap(0x0000, 0xffff, "soundreply", function(offset, data, mask)
  if offset & 0xff == 0x0c and (all_replies or data ~= last_reply) then
    print(string.format("SOUNDREPLY frame %d value %02X", scr:frame_number(), data))
    last_reply = data
  end
end)
local plan = {}
for f, v in (os.getenv("SENDCMD") or ""):gmatch("(%d+):(%x+)") do plan[tonumber(f)] = tonumber(v, 16) end
emu.register_frame_done(function()
  local f = scr:frame_number()
  if plan[f] then prog:write_u8(0x320000, plan[f]) end
end)
dofile(here .. "mame_trace.lua")
