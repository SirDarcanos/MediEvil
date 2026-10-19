-- EXPLICIT LAB PREPARATION: restore living friendly skeletons to 500 HP.
-- Never writes boss HP/action, phase, RNG, player health or inventory.
-- Requires run.py --ally-heal-setup. Resulting army victory is assisted setup.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local frame,started,done,ready=0,false,false,0
local log=assert(io.open('samples.jsonl','w'));local edits=assert(io.open('setup-writes.jsonl','w'))
local function tick()
 if done then return end
 frame=frame+1;release()
 assert(u32(0xeee64)==3 and u32(0xeee2c)==23 and u32(0x10000)==25,'Lost final-level context')
 local g=assert(ptr(u32(0xedb3c)));local ld=assert(ptr(u32(0xee978)));local phase=u32(ld)
 if phase==2 then
  for slot=0,7 do
   local a=ptr(u32(0x1c958+slot*12));local rec=a and ptr(u32(a+0xc));local hp=a and s16(a+0x5a)or 0
   if a and rec and s16(rec+4)==3 and ram[rec+6]==0 and hp>0 and hp<500 then
    ffi.cast('int16_t*',ram+a+0x5a)[0]=500
    edits:write(string.format('{"frame":%d,"slot":%d,"actor":%d,"address":%d,"before":%d,"after":500}\n',frame,slot,a+0x80000000,a+0x8000005a,hp));edits:flush()
   end
  end
 end
 local boss=ptr(u32(0x21508));local rec=boss and ptr(u32(boss+0xc))
 local v={frame=frame,mode=3,level=23,overlay=25,gameFrame=u32(0xeee60),vblank=u32(0xeddac),phaseIndex=phase,armyOutcome=i32(ld+4),bossPointer=u32(0x21508),bossEntity=rec and u32(rec)or 0,bossHP=boss and s16(boss+0x5a)or-32768,bossAction=boss and tonumber(ram[boss+0x5c])or-1,bossDefinition=boss and u32(boss+8)or 0,barActive=i32(0xf170c),barInput=i32(0xf1710),barCache=i32(0xf1714),barMax=i32(0xf171c),transitionState=u32(0xeeef8),health=i32(g),gameFlags=u32(0xeee24)}
 if phase==6 and boss and v.bossEntity==0xb3c4 and v.bossDefinition==0x8001cdd4 and v.bossHP>0 and v.barActive==1 then ready=ready+1 else ready=0 end
 local ok=ready>=120;local stop=ok or frame>=15000 or v.health<=0
 local fields={'"phase":"'..(stop and'finished'or'assisted-boss-preparation')..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end;log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if stop then
  done=true;release();log:close();edits:close()
  local f=assert(io.open('final.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()
  PCSX.nextTick(function()
   local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
   local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
   f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();PCSX.quit(ok and 0 or 1)
  end)
 end
end
BossPreparation=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick);if not ok then release();print('BOSS_PREPARATION_ERROR '..tostring(err));log:flush();edits:flush();PCSX.quit(1)end
end)
