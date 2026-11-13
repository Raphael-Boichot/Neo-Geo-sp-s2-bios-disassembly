-- MAME autoboot script (needs -debug -debugger none -log): writes to error.log every frame where a
-- game turns the LSPC timer IRQ on (REG_LSPCMODE bit 4), every vector switch (REG_SWPBIOS /
-- REG_SWPROM) and every run of SystemInt2. Environment: LAST, KEYS (as mame_run.lua).
-- In debugger actions the program counter is `curpc` (`pc` is refused).
local last = tonumber(os.getenv("LAST") or "3000")
local d = manager.machine.debugger
local done = false
local function field(name) for _, p in pairs(manager.machine.ioport.ports) do if p.fields[name] then return p.fields[name] end end end
local keys = {}
for fr, nm in string.gmatch(os.getenv("KEYS") or "", "(%d+):([^,]+)") do keys[tonumber(fr)] = nm end
local held
emu.register_frame_done(function()
  local fr = manager.machine.screens[":screen"]:frame_number()
  if not done then done = true
    d:command('wpset 3c0006,2,w,(wpdata&10)!=0,{logerror "F%d LSPCMODE %04X pc=%06X\\n",frame,wpdata,curpc; g}')
    d:command('wpset 3a0002,2,w,1,{logerror "F%d SWPBIOS pc=%06X\\n",frame,curpc; g}')
    d:command('wpset 3a0012,2,w,1,{logerror "F%d SWPROM pc=%06X\\n",frame,curpc; g}')
    d:command('bpset c118ca,1,{logerror "F%d SYSTEMINT2\\n",frame; g}')
    d:command('g')
  end
  if held then held:set_value(0); held = nil end
  if keys[fr] then held = field(keys[fr]); held:set_value(1) end
  if fr >= last then manager.machine:exit() end
end)
