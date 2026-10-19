-- Bounded, controller-only Crypt pickup experiment; no game memory writes.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function u16(a)return tonumber(ffi.cast('const uint16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801ff000 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local log=assert(io.open('samples.jsonl','w'))
local events=assert(io.open('route-events.log','w'))
local frame,started,stage=0,false,1
local yaw=math.pi/3
local last,active,blocked=nil,0,0
local route={
 {name='corridor',x=-947,z=600,r=120},
 {name='star-rune',x=-947,z=2714,r=90},
 {name='back-to-room',x=-947,z=600,r=140},
 {name='sword',x=-1007,z=-176,r=90,jump=true},
 {name='sword-return',x=-950,z=650,r=100},
 {name='cross-left',x=-400,z=650,r=100},
 {name='cross-centre',x=250,z=650,r=100},
 {name='bottle',x=1218,z=510,r=100,jump=true},
 {name='daggers',x=960,z=-434,r=100,jump=true},
}
if os.getenv('PICKUP_FOCUS')=='bottle' then
 route={
  {name='bottle',x=1218,z=510,r=110,jump=true,require='bottle'},
  {name='daggers',x=960,z=-434,r=110,jump=true,require='daggers'},
 }
end
local directions={{5},{5,4},{4},{4,7},{7},{7,6},{6},{6,5}}
local function dump(label)
 local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'))
 f:write(ffi.string(ram,0x200000));f:close()
end
local function sample(phase,state,actor)
 local v={frame=frame,mode=u32(0xeee64),level=u32(0xeee2c),overlay=u32(0x10000),
  gameFrame=u32(0xeee60),submode=u32(0xeee70),state=u32(0xedb3c),
  legacyHealth=u32(0xf1648),starRune=u16(0xf823c),gold=u16(0xf828c),
  smallSword=u16(0xf81f4),daggers=u16(0xf8208),shield=u16(0xf827c),
  bottlesWord4=state and u32(state+4) or 0,bottlesWord8=state and u32(state+8) or 0}
 if state then v.health=u32(state);v.flags=u32(state+0x66c)end
 if actor then v.actor=actor+0x80000000;v.x=i32(actor+0x24);v.y=i32(actor+0x28);v.z=i32(actor+0x2c)end
 local parts={'"phase":"'..phase..'"'}
 for k,n in pairs(v)do parts[#parts+1]='"'..k..'":'..n end
 log:write('{'..table.concat(parts,',')..'}\n');log:flush()
end
local function tick()
 frame=frame+1;release()
 local state=ptr(u32(0xedb3c));local actor=state and ptr(u32(state+0x530))
 local target=route[stage]
 local phase=target and target.name or 'finished'
 if frame%60==0 or frame==1 then dump(phase)end
 if frame>=3600 or not target or u32(0xeee64)~=3 or u32(0xeee2c)~=6 or not actor then
  local reason=frame>=3600 and 'frame-limit' or (not target and 'all-targets-reached' or 'game-or-actor-unavailable')
  events:write(string.format('STOP|%s|frame=%d|stage=%d\n',reason,frame,stage));events:flush()
  dump('final');sample('finished',state,actor);log:close();events:close()
  PCSX.nextTick(function()
   local saved=Support.File.open('end.state','TRUNCATE');saved:writeMoveSlice(PCSX.createSaveState());saved:close()
   local ss=PCSX.GPU.takeScreenShot();local image=Support.File.open('final.pixels','TRUNCATE');image:writeMoveSlice(ss.data);image:close()
   local meta=assert(io.open('final-image.json','w'));meta:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));meta:close()
   PCSX.quit(0)
  end);return
 end
 if frame>180 and frame%12==1 then
  local x,z=i32(actor+0x24),i32(actor+0x2c)
  if last then
   local dx,dz=x-last.x,z-last.z
   if dx*dx+dz*dz>64 then yaw=math.atan2(dz,dx)-active*math.pi/4;blocked=0 else blocked=blocked+1 end
  end
  local acquired=not target.require or (target.require=='bottle' and u32(state+8)>0) or (target.require=='daggers' and u16(state+0x94)~=0xffff)
  if (x-target.x)^2+(z-target.z)^2<target.r^2 and acquired then
   events:write(string.format('REACHED|%d|%s|%d|%d|%d|star=%d|sword=%d|daggers=%d\n',frame,target.name,x,i32(actor+0x28),z,u16(0xf823c),u16(0xf81f4),u16(0xf8208)));events:flush()
   dump('reached-'..stage)
   stage=stage+1;target=route[stage]
   if target then last=nil else sample(phase,state,actor);return end
  end
  local angle=math.atan2(target.z-z,target.x-x)
  active=math.floor((angle-yaw)/(math.pi/4)+0.5)%8
  if blocked>4 then active=(active+(blocked%2==0 and 1 or -1))%8 end
  last={x=x,z=z}
 end
 if frame>180 and target then
  for _,b in ipairs(directions[active+1])do pad.setOverride(b)end
  if target.jump and frame%60<6 then pad.setOverride(13)end
 end
 sample(phase,state,actor)
end
PickupProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then
  started=true;PCSX.nextTick(function()
   local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()
  end);return
 end
 local ok,err=pcall(tick)
 if not ok then release();print('PICKUP_PROBE_ERROR '..tostring(err));log:flush();events:flush();PCSX.quit(1)end
end)
