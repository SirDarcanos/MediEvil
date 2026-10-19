-- EXPLICIT COMBAT LAB: living player HP/ammo refills; native controller combat.
-- Optional --boss-last-hit-setup lowers guarded boss HP to 6 ONCE, never zero.
-- Otherwise never edits bosses. Never edits actions, phases, RNG, positions or ownership.
-- Requires run.py --combat-supply-setup. Not a natural/full-run battle claim.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local limit=tonumber(os.getenv('BOSS_COMBAT_LIMIT')or'24000')
assert(limit>=600 and limit<=30000)
local goal=os.getenv('BOSS_GOAL')or'both';assert(goal=='both'or goal=='zarok')
local wantedWeapon=tonumber(os.getenv('BOSS_WEAPON')or'3');assert(wantedWeapon==0 or wantedWeapon==3)
local frame,started,done=0,false,false
local kardokDead,zarokDead,deadFrames=false,false,0
local lastHitSetup=os.getenv('BOSS_LAST_HIT_SETUP')=='1';local hpPrepared={}
local lastBoss,lastHP,lastPhase=nil,nil,nil
local yaw,active,lastMove=math.pi/3,0,nil
local dirs={{5},{5,4},{4},{4,7},{7},{7,6},{6},{6,5}}
local log=assert(io.open('samples.jsonl','w'));local edits=assert(io.open('setup-writes.jsonl','w'))
local function finish(ok)
 done=true;release();log:close();edits:close()
 local f=assert(io.open('final.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()
 PCSX.nextTick(function()
  local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
  local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();PCSX.quit(ok and 0 or 1)
 end)
end
local function refill(a,before,after,typ)
 edits:write(string.format('{"frame":%d,"address":%d,"before":%d,"after":%d,"type":"%s"}\n',frame,a+0x80000000,before,after,typ));edits:flush()
 if typ=='int' then ffi.cast('int32_t*',ram+a)[0]=after
 elseif typ=='short' then ffi.cast('int16_t*',ram+a)[0]=after
 else ffi.cast('uint16_t*',ram+a)[0]=after end
end
local function tick()
 if done then return end
 frame=frame+1;release()
 local mode,header,level=u32(0xeee64),u32(0x10000),u32(0xeee2c)
 local context=mode==3 and header==25 and level==23
 local g=context and ptr(u32(0xedb3c));local p=g and ptr(u32(g+0x530));local ld=context and ptr(u32(0xee978))
 local phase=ld and u32(ld)or-1;local boss=(phase==6 or phase==8)and ptr(u32(0x21508))
 local def=boss and ptr(u32(boss+8));local ctor=def and u32(def+0x88)or 0
 local expected=phase==6 and 0x80011f24 or 0x80018784
 if ctor~=expected then boss=nil end
 local rec=boss and ptr(u32(boss+0xc));if not rec then boss=nil end
 local hp=boss and s16(boss+0x5a)or-32768
 local action=boss and tonumber(ram[boss+0x5c])or-1
 local hpBeforeSetup=hp
 if lastHitSetup and boss and hp>6 then
  local key=phase..':'..boss..':'..ctor
  if not hpPrepared[key]then refill(boss+0x5a,hp,6,'short');hp=6;hpPrepared[key]=true end
 end
 if boss and boss==lastBoss and phase==lastPhase and lastHP>0 and hp<=0 and (action==11 or action==25)then
  if phase==6 then kardokDead=true elseif phase==8 then zarokDead=true end
 end
 lastBoss,lastHP,lastPhase=boss,hp,phase
 if zarokDead then deadFrames=deadFrames+1 end
 local health=g and i32(g)or-1;local ammo=g and tonumber(ffi.cast('const uint16_t*',ram+g+0x94)[0])or 65535
 if context and p and health>0 then
  if health<300 then refill(g,health,300,'int')end
  if ammo<100 then refill(g+0x94,ammo,100,'ushort')end
 end
 local weapon=g and i32(g+0xc)or-1
 local x,z=p and i32(p+0x24)or 0,p and i32(p+0x2c)or 0
 local bx,bz=boss and i32(boss+0x24)or 0,boss and i32(boss+0x2c)or 0
 local distance=math.sqrt((bx-x)^2+(bz-z)^2)
 if context and p and boss and hp>0 and u32(0xeee70)==0 then
  if frame%12==1 then
   if lastMove then local dx,dz=x-lastMove.x,z-lastMove.z;if dx*dx+dz*dz>64 then yaw=math.atan2(dz,dx)-lastMove.dir*math.pi/4 end end
   local angle=math.atan2(bz-z,bx-x)
   local near=phase==8 and 0 or 350;local far=phase==8 and 200 or 700
   if distance<near then angle=angle+math.pi end
   active=math.floor((angle-yaw)/(math.pi/4)+0.5)%8;lastMove=nil
   if distance>far or distance<near then lastMove={x=x,z=z,dir=active}end
  end
  if lastMove then for _,b in ipairs(dirs[active+1])do pad.setOverride(b)end end
  assert(weapon==wantedWeapon,'Wrong equipped weapon; prepare through inventory before combat')
  if frame%48<6 then pad.setOverride(14)end
 end
 local mask=0;for b=0,15 do if pad.getButton(b)then mask=mask+2^b end end
 local ok=(goal=='zarok'or kardokDead)and zarokDead and (deadFrames>=60 or not context)
 local stop=ok or frame>=limit or not context or health<=0
 local v={frame=frame,mode=mode,overlay=header,level=level,vblank=u32(0xeddac),gameFrame=u32(0xeee60),phaseIndex=phase,bossPointer=boss and boss+0x80000000 or 0,bossEntity=rec and u32(rec)or 0,bossHP=hp,bossHPBeforeSetup=hpBeforeSetup,bossAction=action,musicTrack=tonumber(ffi.cast('const uint16_t*',ram+0xeef00)[0]),scriptFlag17=tonumber(ram[0xee945]),scriptFlag18=tonumber(ram[0xee946]),scriptFlag19=tonumber(ram[0xee947]),bossDefinition=boss and u32(boss+8)or 0,bossConstructor=ctor,barActive=i32(0xf170c),barInput=i32(0xf1710),barCache=i32(0xf1714),barMax=i32(0xf171c),healthBeforeAssistance=health,ammoBeforeAssistance=ammo,weapon=weapon,wantedWeapon=wantedWeapon,goalZarokOnly=goal=='zarok'and 1 or 0,bossFlags=boss and u32(boss+0x50)or 0,bossPrivateState=boss and ptr(u32(boss+0x90))and i32(ptr(u32(boss+0x90)))or-1,x=x,y=p and i32(p+0x28)or 0,z=z,bossX=bx,bossY=boss and i32(boss+0x28)or 0,bossZ=bz,effectivePadMask=mask,kardokDeathObserved=kardokDead and 1 or 0,zarokDeathObserved=zarokDead and 1 or 0}
 local fields={'"phase":"'..(stop and'finished'or'assisted-native-boss-combat')..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end;log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if stop then finish(ok)end
end
BossCombat=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick);if not ok then release();print('BOSS_COMBAT_ERROR '..tostring(err));log:flush();edits:flush();PCSX.quit(1)end
end)
