-- Finite controller-only first Crypt exit test, starting from our own acquired-rune state.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function u16(a)return tonumber(ffi.cast('const uint16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801ff000 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local route={{1721,-4,120},{2378,-139,100},{2920,-457,100},{3338,-928,100},{3590,-1504,100},{3654,-2010,100},{3654,-2769,90}}
local dirs={{5},{5,4},{4},{4,7},{7},{7,6},{6},{6,5}}
local frame,started,stage,active,blocked,mapFrames=0,false,1,0,0,0
local yaw,last=math.pi/3,nil
local mapWait=tonumber(os.getenv('CRYPT_MAP_WAIT')or'60')
assert(mapWait>=60 and mapWait<=2000)
local log=assert(io.open('samples.jsonl','w'))
local events=assert(io.open('route-events.log','w'))
local function dump(label)
 local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'));f:write(ffi.string(ram,0x200000));f:close()
end
local function finish(reason,code)
 release();events:write(string.format('STOP|%s|%d\n',reason,frame));events:close();log:close();dump('final')
 PCSX.nextTick(function()
  local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
  local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('final.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open('final-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close()
  PCSX.quit(code)
 end)
end
local function tick()
 frame=frame+1;release()
 local mode,overlay=u32(0xeee64),u32(0x10000)
 local state=ptr(u32(0xedb3c));local actor=state and ptr(u32(state+0x530))
 local completed=state and tonumber(ram[state+0x34+6])or 0
 local phase=(mode==4 and overlay==26)and 'map' or 'stairs-'..stage
 local v={frame=frame,mode=mode,overlay=overlay,level=u32(0xeee2c),vblank=u32(0xeddac),gameFrame=u32(0xeee60),submode=u32(0xeee70),result=u32(0xeee6c),transitionFlags=u32(0xeee24),state=u32(0xedb3c),cryptFlags=completed}
 if state then v.starRune=u16(state+0xc8);v.health=i32(state);v.reserveEnergy=i32(state+4);v.reserveCapacity=i32(state+8)end
 if actor then v.actor=actor+0x80000000;v.x=i32(actor+0x24);v.y=i32(actor+0x28);v.z=i32(actor+0x2c)end
 local parts={'"phase":"'..phase..'"'};for k,n in pairs(v)do parts[#parts+1]='"'..k..'":'..n end
 if frame>=6000 or (mapFrames>=mapWait-1 and mode==4 and overlay==26 and completed%2==1)then parts[1]='"phase":"finished"'end
 log:write('{'..table.concat(parts,',')..'}\n');log:flush()
 if frame==1 or frame%60==0 then dump(phase)end
 if frame==1 then assert(mode==3 and v.level==6 and v.starRune==1 and completed%2==0,'Need first-visit Crypt seed with Star Rune')end
 if mode==4 and overlay==26 and completed%2==1 then
  mapFrames=mapFrames+1
  if mapFrames>=mapWait then finish('natural-crypt-completion-map-and-flag',0)end
  return
 end
 if frame>=6000 then finish('frame-limit-no-completion',1);return end
 if mode~=3 or v.level~=6 or not actor then return end
 if frame<=180 then return end
 if v.submode~=0 then
  if frame%60<6 then pad.setOverride(14)end
  return
 end
 local target=route[stage]
 if frame%12==1 then
  if last then
   local dx,dz=v.x-last.x,v.z-last.z
   if dx*dx+dz*dz>64 then yaw=math.atan2(dz,dx)-active*math.pi/4;blocked=0 else blocked=blocked+1 end
  end
  if (v.x-target[1])^2+(v.z-target[2])^2<target[3]^2 then
   events:write(string.format('WAYPOINT|%d|%d|%d|%d|%d|rune=%d\n',frame,stage,v.x,v.y,v.z,v.starRune));events:flush();dump('waypoint-'..stage)
   if stage<#route then stage=stage+1;target=route[stage];last=nil end
  end
  active=math.floor((math.atan2(target[2]-v.z,target[1]-v.x)-yaw)/(math.pi/4)+0.5)%8
  if blocked>4 then active=(active+(blocked%2==0 and 1 or -1))%8 end
  last={x=v.x,z=v.z}
 end
 for _,b in ipairs(dirs[active+1])do pad.setOverride(b)end
 if (stage==1 or blocked>4)and frame%60<6 then pad.setOverride(13)end
 if blocked>8 and frame%60>=15 and frame%60<21 then pad.setOverride(14)end
end
CryptExitProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()
  local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()
 end);return end
 local ok,err=pcall(tick)
 if not ok then release();print('CRYPT_EXIT_PROBE_ERROR '..tostring(err));log:flush();events:flush();PCSX.quit(1)end
end)
