-- LAB SETUP ONLY: place Dan near the authored final arena, not a demonstrated skip.
-- Writes only actor/physics position during setup. Never HP, RNG, phase or spawn flags.
local ffi=require('ffi')
local bit=require('bit')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function set(a,v)ffi.cast('int32_t*',ram+a)[0]=v end
local function release()for b=0,15 do pad.clearOverride(b)end end
local frame,started,done=0,false,false
local writes=assert(io.open('position-writes.jsonl','w'))
local watchers={}
local log=assert(io.open('samples.jsonl','w'))
local setup=assert(io.open('setup-events.json','w'))
local function dump(label)local f=assert(io.open(label..'.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()end
local function tick()
 if done then return end
 frame=frame+1;release()
 local g=ptr(u32(0xedb3c));local a=g and ptr(u32(g+0x530));local level=u32(0xeee2c)
 assert(u32(0xeee64)==3 and level==23 and u32(0x10000)==25 and a,'Expected owned final-level seed')
 if frame==60 then
  local physics=ptr(u32(a+0x80));assert(physics,'Missing player physics')
  local regs=PCSX.getRegisters()
  for label,address in pairs({actorX=a+0x24,physicsX=physics+0x30,previousX=physics+0x20,flags=a+0x50})do
   watchers[#watchers+1]=PCSX.addBreakpoint(address+0x80000000,'Write',4,'Own position setup observation',function()
    local pc=tonumber(regs.pc);local p=ptr(pc)
    writes:write(string.format('{"frame":%d,"field":"%s","pc":%d,"codeAtPC":%d,"codeBeforePC":%d,"ra":%d,"a0":%d,"a1":%d,"a2":%d,"a3":%d,"v0":%d,"v1":%d,"old":%d}\n',frame,label,pc,p and u32(p)or 0,p and u32(p-4)or 0,tonumber(regs.GPR.n.ra),tonumber(regs.GPR.n.a0),tonumber(regs.GPR.n.a1),tonumber(regs.GPR.n.a2),tonumber(regs.GPR.n.a3),tonumber(regs.GPR.n.v0),tonumber(regs.GPR.n.v1),u32(address)));writes:flush();return true
   end)
  end
  -- Clear both the train script flag and the independently traced platform-
  -- follow flag (0x10000000) before lab relocation; not an in-game detachment.
  set(a+0x50,bit.band(u32(a+0x50),0xe7ffffff))
  set(a+0x24,0);set(a+0x28,-100);set(a+0x2c,2000)
  -- Match the native setter's current/previous coordinates and motion reset;
  -- changing only current position produces a spurious old-to-new displacement.
  for _,off in ipairs({0x20,0x30})do set(physics+off,0);set(physics+off+4,-100*65536);set(physics+off+8,2000*65536)end
  for _,off in ipairs({0x48,0x4c,0x50,0xbc,0xc0,0xc4})do set(physics+off,0)end
  ffi.cast('int16_t*',ram+physics+0x78)[0]=0
  ffi.cast('int16_t*',ram+physics+0x7a)[0]=-100
  ffi.cast('int16_t*',ram+physics+0x7c)[0]=2000
  ffi.cast('int16_t*',ram+physics+0xb8)[0]=0
  ffi.cast('int16_t*',ram+g+0x68c)[0]=-100
  setup:write(string.format('{"frame":60,"actor":%d,"physics":%d,"position":[0,-100,2000],"method":"Explicit laboratory train-override detachment and relocation with native-setter mirrors/motion reset, not an in-game skip; no RNG/HP/phase/spawn flag writes"}',a+0x80000000,physics+0x80000000));setup:close();dump('post-setup')
 end
 local v={frame=frame,mode=u32(0xeee64),overlay=u32(0x10000),level=level,submode=u32(0xeee70),vblank=u32(0xeddac),gameFrame=u32(0xeee60),x=i32(a+0x24),y=i32(a+0x28),z=i32(a+0x2c),health=i32(g),rngState=u32(0xf3994)}
 local ld=ptr(u32(0xee978));if ld then for i=0,4 do v['levelWord'..i]=i32(ld+i*4)end end
 local stop=frame>=660
 local fields={'"phase":"'..(stop and'finished'or'arena-lab-setup')..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end;log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame==80 then for _,bp in ipairs(watchers)do bp:remove()end;watchers={}end
 if stop then
  done=true;for _,bp in ipairs(watchers)do bp:remove()end;writes:close();dump('final');log:close()
  PCSX.nextTick(function()
   local f=Support.File.open('arena.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
   local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
   f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();PCSX.quit(v.health>0 and math.abs(v.x)<1000 and math.abs(v.z-2000)<1000 and math.abs(v.y)<1000 and 0 or 1)
  end)
 end
end
ArenaSeed=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick);if not ok then release();print('ARENA_SETUP_ERROR '..tostring(err));log:flush();PCSX.quit(1)end
end)
