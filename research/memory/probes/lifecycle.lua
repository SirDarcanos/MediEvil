-- Follow our own naturally fatal state into Game Over/menu; no RAM pokes.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801ff800 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local frame,started,done,menuAt=0,false,false,nil
-- The freed game-state pointer is NOT necessarily zeroed. Menu ownership, not
-- pointer nullness, establishes that prior health/inventory bytes are invalid.
local log=assert(io.open('samples.jsonl','w'))
local function dump(label)local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'));f:write(ffi.string(ram,0x200000));f:close()end
local function tick()
 if done then return end
 frame=frame+1;release()
 local mode,header=u32(0xeee64),u32(0x10000)
 local state=ptr(u32(0xedb3c));local actor=state and u32(state+0x530)or 0
 local title=mode==2 and header==24 and ptr(u32(0xedc1c))or nil
 if title and i32(title)==1 and not menuAt then menuAt=frame end
 local ok=menuAt and frame-menuAt>=180
 local stop=ok or frame>=2400
 local press=-1
 if frame>=900 and mode==3 and frame%120<6 then press=14;pad.setOverride(press)end
 local v={frame=frame,mode=mode,overlay=header,vblank=u32(0xeddac),gameFrame=u32(0xeee60),gameFlags=u32(0xeee24),gameResult=u32(0xeee6c),submode=u32(0xeee70),state=u32(0xedb3c),actor=actor,inputButton=press,hudHealth=i32(0xf1648)}
 if state then v.health=i32(state);v.reserveEnergy=i32(state+4);v.deathSubstate=s16(state+0x6a0)end
 local f={'"phase":"'..(stop and'finished'or'fatal-lifecycle')..'"'};for k,n in pairs(v)do f[#f+1]='"'..k..'":'..n end;log:write('{'..table.concat(f,',')..'}\n');log:flush()
 if frame==1 or frame%120==0 then dump('lifecycle')end
 if stop then
  done=true;release();dump('end');log:close()
  PCSX.nextTick(function()
   local ss=PCSX.GPU.takeScreenShot();local f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
   f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close()
   f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close();PCSX.quit(ok and 0 or 1)
  end)
 end
end
LifecycleProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick);if not ok then release();print('LIFECYCLE_ERROR '..tostring(err));log:flush();PCSX.quit(1)end
end)
