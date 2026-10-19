-- Read-only RNG execution tracing in OUR private interpreter (-debugger, no servers).
-- Never changes PC, registers, RNG state or guest memory. Actor scratch is a hint,
-- not proof that non-actor callers belong to that last processed actor.
local ffi=require('ffi')
local bit=require('bit')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local scratch=ffi.cast('const uint8_t*',PCSX.getScratchPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local regs=PCSX.getRegisters()
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local action=os.getenv('RNG_ACTION')or'idle'
assert(action=='idle'or action=='move'or action=='inventory'or action=='attack')
local log=assert(io.open('samples.jsonl','w'))
local trace=assert(io.open('rng-calls.jsonl','w'))
local frame,started,loaded,done,count,overflow=0,false,false,false,0,false
RngBreakpoint=PCSX.addBreakpoint(0x800a43d8,'Exec',4,'Memory audit RNG store',function()
 if not loaded or done then return true end
 count=count+1
 if count>100000 then overflow=true;return true end
 local pre,post=u32(0xf3994),tonumber(regs.GPR.n.v0)
 local hint=tonumber(ffi.cast('const uint32_t*',scratch+0xa4)[0])
 trace:write(string.format('{"frame":%d,"vblank":%d,"gameFrame":%d,"mode":%d,"submode":%d,"level":%d,"callerRA":%d,"actorScratchHint":%d,"before":%d,"afterRegister":%d,"output":%d}\n',frame,u32(0xeddac),u32(0xeee60),u32(0xeee64),u32(0xeee70),u32(0xeee2c),tonumber(regs.GPR.n.ra),hint,pre,post,bit.band(bit.rshift(post,16),0x7fff)))
 return true
end,'non-pausing RNG observation')
local function dump(label)local f=assert(io.open(label..'.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()end
local function tick()
 if done then return end
 frame=frame+1;release()
 if frame==1 then assert(u32(0xa43d8)==0xac223994,'Unexpected RNG store instruction');dump('initial')end
 local press=-1
 if action=='move'and frame>=120 and frame<360 then press=4 end
 if action=='inventory'and((frame>=120 and frame<126)or(frame>=360 and frame<366))then press=frame<360 and 0 or 12 end
 if action=='attack'and frame>=120 and frame%30<6 then press=14 end
 if press>=0 then pad.setOverride(press)end
 local v={frame=frame,mode=u32(0xeee64),level=u32(0xeee2c),overlay=u32(0x10000),submode=u32(0xeee70),gameFrame=u32(0xeee60),vblank=u32(0xeddac),rngState=u32(0xf3994),calls=count,inputButton=press}
 local g=ptr(u32(0xedb3c));local a=g and ptr(u32(g+0x530))
 if a then v.x=i32(a+0x24);v.y=i32(a+0x28);v.z=i32(a+0x2c)end
 if v.level==23 and v.overlay==25 then
  local ld=ptr(u32(0xee978));if ld then v.armyPhase=u32(ld);v.armyOutcome=i32(ld+4)end
  for team,base in pairs({friendly=0x1c950,enemy=0x1c9b0})do
   local total,live=0,0
   for slot=0,7 do
    local p=ptr(u32(base+slot*12+8))
    if p then
     local hp=tonumber(ffi.cast('const int16_t*',ram+p+0x5a)[0]);v[team..'HP'..slot]=hp
     if hp>0 then total=total+hp;live=live+1 end
    end
   end
   v[team..'RegisteredLive']=live;v[team..'RegisteredHP']=total
  end
 end
 local stop=frame>=600
 local f={'"phase":"'..(stop and'finished'or action)..'"'};for k,n in pairs(v)do f[#f+1]='"'..k..'":'..n end;log:write('{'..table.concat(f,',')..'}\n');log:flush();trace:flush()
 if stop then
  done=true;release();RngBreakpoint:remove();log:close();trace:close();dump('final')
  PCSX.nextTick(function()PCSX.quit(count>0 and not overflow and 0 or 1)end)
 end
end
RngProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()
  local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close();loaded=true
 end);return end
 local ok,err=pcall(tick);if not ok then release();print('RNG_PROBE_ERROR '..tostring(err));log:flush();trace:flush();PCSX.quit(1)end
end)
