-- Controlled level setup in OUR private emulator only; never run on a user's session.
-- Setup writes: next-level request, movie override, reload result. No HP, inventory,
-- actor-coordinate or boss-HUD values are injected. Subsequent changes are native.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function u16(a)return tonumber(ffi.cast('const uint16_t*',ram+a)[0])end
local function setupWord(a,v)ffi.cast('uint32_t*',ram+a)[0]=v end
local function ptr(v)if v>=0x80001000 and v<0x801ff000 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local level=tonumber(os.getenv('BOSS_LEVEL')or'10')
local header=tonumber(os.getenv('BOSS_HEADER')or'20')
assert(level>=1 and level<25 and header>=2 and header<=25)
local log=assert(io.open('samples.jsonl','w'))
local events=assert(io.open('setup-events.log','w'))
local frame,started,requested,ready,done=0,false,false,nil,false
local function dump(label)
 local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'));f:write(ffi.string(ram,0x200000));f:close()
end
local function checkpoint(label)
 dump(label)
 PCSX.nextTick(function()
  local f=Support.File.open(label..'.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
  local ss=PCSX.GPU.takeScreenShot();f=Support.File.open(label..'.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open(label..'-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close()
  if done then PCSX.quit(ready and 0 or 1)end
 end)
end
local function tick()
 if done then return end
 frame=frame+1;release()
 local mode=u32(0xeee64);local state=ptr(u32(0xedb3c));local actor=state and ptr(u32(state+0x530))
 local current=u32(0xeee2c)
 if requested and not ready and mode==3 and current==level and u32(0x10000)==header and actor and u32(0xeee60)>0 then
  ready=frame;events:write('TARGET_READY|'..frame..'\n');events:flush();checkpoint('ready')
 end
 local age=ready and frame-ready or -1
 local phase=not requested and 'seed-rest' or (not ready and 'level-setup' or 'target-observation')
 if frame>=5400 or (ready and age>=1800) or (ready and mode==2)then phase='finished' end
 local v={frame=frame,mode=mode,overlay=u32(0x10000),level=current,gameFrame=u32(0xeee60),submode=u32(0xeee70),state=u32(0xedb3c),gameFlags=u32(0xeee24),result=u32(0xeee6c),bossActive=i32(0xf170c),bossInput=i32(0xf1710),bossCached=i32(0xf1714),bossMax=i32(0xf171c)}
 if state then v.health=i32(state);v.reserveEnergy=i32(state+4);v.reserveCapacity=i32(state+8);v.deathSubstate=s16(state+0x6a0);v.weapon=i32(state+0xc);v.daggers=u16(state+0x94)end
 if actor then v.actor=actor+0x80000000;v.x=i32(actor+0x24);v.y=i32(actor+0x28);v.z=i32(actor+0x2c)end
 local fields={'"phase":"'..phase..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end
 log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame==1 or frame%120==0 then dump(phase)end
 if phase=='finished'then
  done=true;events:write('STOP|'..frame..'|targetAge='..age..'\n');events:close();log:close();checkpoint('end');return
 end
 if frame==180 then
  assert(mode==3 and current==6 and actor,'Expected our Crypt seed; refusing setup')
  events:write(string.format('SETUP|%d|0x800EEE30=%d|0x800ED6CC=1|0x800EEE6C=4\n',frame,level));events:flush()
  setupWord(0xeee30,level);setupWord(0xed6cc,1);setupWord(0xeee6c,4);requested=true
 end
 if ready and mode==3 and current==level and v.submode==2 then
  if frame%60<6 then pad.setOverride(12)end
 end
 if ready and mode==3 and current==level and v.submode==0 then
  if age>=360 and age<540 then pad.setOverride(4)end
  if age>=540 and age%30<6 then pad.setOverride(14)end
  if age==180 or age==900 then checkpoint('target-'..age)end
 end
end
BossProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()
  local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()
 end);return end
 local ok,err=pcall(tick)
 if not ok then release();print('BOSS_PROBE_ERROR '..tostring(err));log:flush();events:flush();PCSX.quit(1)end
end)
