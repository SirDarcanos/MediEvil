-- Normally a controller-only continuation of OUR Pumpkin state. Optional explicit
-- wake setup clears ONE prerequisite counter, never HP/HUD/inventory/coordinates.
-- That injected counter and its derived wake phase are not natural-event proof.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local function name(a)
 local d=ptr(u32(a+8));local s=d and ptr(u32(d))
 return s and ffi.string(ram+s,40):match('^[^%z]+')or'?'
end
local function actors(player)
 local a=player;local seen={}
 for i=1,300 do
  local p=ptr(u32(a+4));if not p or seen[p]then break end
  seen[a]=true;a=p
 end
 seen={};local result={}
 for i=1,300 do
  if seen[a]then break end;seen[a]=true
  result[#result+1]={a=a,name=name(a),hp=s16(a+0x5a),x=i32(a+0x24),y=i32(a+0x28),z=i32(a+0x2c)}
  local n=ptr(u32(a));if not n then break end;a=n
 end
 return result
end
local frame,started,done=0,false,false
local wakeSetup=os.getenv('PUMPKIN_WAKE_SETUP')=='1'
local wakeDone=false
local equip,menuAt='close-book',0
local log=assert(io.open('samples.jsonl','w'))
local alog=assert(io.open('actors.jsonl','w'))
local last,active,blocked=nil,0,0
local yaw=math.pi/3
local dirs={{5},{5,4},{4},{4,7},{7},{7,6},{6},{6,5}}
local patrol={{359,769},{-1125,4500},{-3000,6500},{1000,6500},{-1125,8500}}
local waypoint=1
local function dump(label)
 local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'));f:write(ffi.string(ram,0x200000));f:close()
end
local function finish(ok)
 done=true;release();dump('end');log:close();alog:close()
 PCSX.nextTick(function()
  local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
  local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();PCSX.quit(ok and 0 or 1)
 end)
end
local function tick()
 if done then return end
 frame=frame+1;release()
 local state=ptr(u32(0xedb3c));local player=state and ptr(u32(state+0x530));local mode=u32(0xeee64);local sub=u32(0xeee70)
 if frame==1 then assert(mode==3 and u32(0xeee2c)==10 and player,'Expected our Pumpkin state')end
 local v={frame=frame,mode=mode,overlay=u32(0x10000),level=u32(0xeee2c),gameFrame=u32(0xeee60),submode=sub,bossActive=i32(0xf170c),bossInput=i32(0xf1710),bossCached=i32(0xf1714),bossMax=i32(0xf171c)}
 if state then v.health=i32(state);v.reserveEnergy=i32(state+4);v.reserveCapacity=i32(state+8);v.weapon=i32(state+0xc);v.deathSubstate=s16(state+0x6a0)end
 if player then v.actor=player+0x80000000;v.x=i32(player+0x24);v.y=i32(player+0x28);v.z=i32(player+0x2c)end
 local levelData=ptr(u32(0xee978))
 if levelData then v.pumpkinPhase=i32(levelData+0xc);v.wakeGateCount=i32(levelData+0x10)end
 local list=player and actors(player)or{}
 local target,best=nil,math.huge
 for _,a in ipairs(list)do
  if a.name=='PsMonster'then v.monsterActor=a.a+0x80000000;v.monsterHP=a.hp end
  if a.name=='PsPodball'and a.hp>0 then
   local dist=(a.x-v.x)^2+(a.z-v.z)^2
   if dist<best then target,best=a,dist end
  end
 end
 if (not target or wakeSetup)and v.bossActive==1 then
  for _,a in ipairs(list)do if a.name=='PsMonster'and a.hp>0 then target=a;best=(a.x-v.x)^2+(a.z-v.z)^2 end end
 end
 local phase=equip
 if frame>=7200 or (frame>=1800 and equip~='fight')or mode~=3 or not player then phase='finished'end
 local fields={'"phase":"'..phase..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end
 if target then fields[#fields+1]='"targetHP":'..target.hp;fields[#fields+1]='"targetActor":'..(target.a+0x80000000)end
 log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame==1 or frame%120==0 then
  dump(phase)
  for _,a in ipairs(list)do alog:write(string.format('{"frame":%d,"actor":%d,"name":"%s","hp":%d,"x":%d,"y":%d,"z":%d}\n',frame,a.a+0x80000000,a.name,a.hp,a.x,a.y,a.z))end;alog:flush()
 end
 if phase=='finished'then finish(equip=='fight');return end
 if equip=='close-book'then
  if sub==2 then if frame%60<6 then pad.setOverride(12)end;return end
  if sub==0 then
   if wakeSetup and v.weapon==3 then equip='fight';last=nil
   else equip='open-inventory';menuAt=frame end
  end
 end
 if equip~='fight'then
  local t=frame-menuAt
  if t<6 then pad.setOverride(0)
  elseif t>=60 and t<66 then pad.setOverride(7)
  elseif t>=120 and t<126 then pad.setOverride(14)
  elseif t>=180 then
   if v.weapon==0 then equip='fight';last=nil
   else menuAt=frame;equip='open-inventory' end
  end
  return
 end
 if sub~=0 then if frame%60<6 then pad.setOverride(12)end;return end
 if wakeSetup and not wakeDone then
  assert(mode==3 and v.level==10 and v.overlay==20 and levelData,'Refusing wake setup outside Pumpkin level')
  ffi.cast('int32_t*',ram+levelData+0x10)[0]=0
  wakeDone=true;dump('forced-wake-prerequisite');return
 end
 local stopRange=wakeSetup and 3000 or 240
 local attackRange=wakeSetup and 4500 or 550
 local tx,tz
 if target then tx,tz=target.x,target.z else
  tx,tz=patrol[waypoint][1],patrol[waypoint][2]
  if(v.x-tx)^2+(v.z-tz)^2<180^2 then waypoint=waypoint%#patrol+1 end
 end
 if frame%12==1 then
  if target and best<=stopRange^2 then last=nil;blocked=0 end
  if last then
   local dx,dz=v.x-last.x,v.z-last.z
   if dx*dx+dz*dz>64 then yaw=math.atan2(dz,dx)-active*math.pi/4;blocked=0 else blocked=blocked+1 end
  end
  active=math.floor((math.atan2(tz-v.z,tx-v.x)-yaw)/(math.pi/4)+0.5)%8
  if blocked>6 then active=(active+(blocked%2==0 and 1 or -1))%8 end
  last={x=v.x,z=v.z}
 end
 if not target or best>stopRange^2 or frame%30<3 then for _,b in ipairs(dirs[active+1])do pad.setOverride(b)end end
 if target and best<attackRange^2 and frame%30>=3 and frame%30<9 then pad.setOverride(14)end
 if blocked>8 and frame%60<6 then pad.setOverride(13)end
end
PumpkinProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick)
 if not ok then release();print('PUMPKIN_PROBE_ERROR '..tostring(err));log:flush();alog:flush();PCSX.quit(1)end
end)
