-- Finite native attack-input test. Requires the isolated state with daggers equipped.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function u16(a)return tonumber(ffi.cast('const uint16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801ff000 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local frame,started,initial=0,false,nil
local log=assert(io.open('samples.jsonl','w'))
local function tick()
 frame=frame+1;release()
 assert(u32(0x69958)==0xaf840568,'Wrong executable in loaded state')
 local state=assert(ptr(u32(0xedb3c)),'Missing state')
 local actor=assert(ptr(u32(state+0x530)),'Missing player')
 assert(u32(0xeee64)==3 and u32(0xeee2c)==6,'Expected Crypt gameplay')
 local quantity=u16(state+0x94)
 if not initial then assert(u32(state+0xc)==3 and quantity>0 and quantity<0xffff,'Daggers must be equipped');initial=quantity end
 local phase='rest'
 if frame>=180 and frame<300 then phase='cross-attack';if frame%30<6 then pad.setOverride(14)end end
 if frame>=300 and frame<420 then phase='square-attack';if frame%30<6 then pad.setOverride(15)end end
 if frame>=540 then phase='finished' end
 log:write(string.format('{"phase":"%s","frame":%d,"mode":%d,"level":%d,"gameFrame":%d,"submode":%d,"actor":%d,"state":%d,"x":%d,"y":%d,"z":%d,"health":%d,"equippedWeapon":%d,"daggers":%d}\n',phase,frame,u32(0xeee64),u32(0xeee2c),u32(0xeee60),u32(0xeee70),actor+0x80000000,state+0x80000000,i32(actor+0x24),i32(actor+0x28),i32(actor+0x2c),i32(state),u32(state+0xc),quantity));log:flush()
 if frame==1 or frame%30==0 then
  local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,phase),'wb'));f:write(ffi.string(ram,0x200000));f:close()
 end
 if frame>=540 then
  release();log:close()
  PCSX.nextTick(function()PCSX.quit(quantity<initial and quantity~=0xffff and 0 or 1)end)
 end
end
DaggerUseProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()
  local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()
 end);return end
 local ok,err=pcall(tick)
 if not ok then release();print('DAGGER_PROBE_ERROR '..tostring(err));log:flush();PCSX.quit(1)end
end)
