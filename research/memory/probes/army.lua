-- Controller-only final-arena observation from an explicitly labeled lab state.
-- Default makes no guest RAM writes. Optional explicit intro prerequisite writes
-- one script flag; never a natural-entry or route-valid-glitch proof.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local variant=os.getenv('ARMY_INPUT')or'normal'
local menuAt=tonumber(os.getenv('ARMY_MENU_AT')or'120')
local menuHold=tonumber(os.getenv('ARMY_MENU_HOLD')or'6')
assert(menuHold>=1 and menuHold<=30)
local bufferClose=tonumber(os.getenv('ARMY_BUFFER_CLOSE_AT')or'0')
local bufferReopen=tonumber(os.getenv('ARMY_BUFFER_REOPEN_AT')or'0')
local closeButton=tonumber(os.getenv('ARMY_BUFFER_CLOSE_BUTTON')or'12')
local moveFrom=tonumber(os.getenv('ARMY_MOVE_FROM')or'1')
local fixedApproach=os.getenv('ARMY_FIXED_APPROACH')=='1'
local releaseSequence=tonumber(os.getenv('ARMY_RELEASE_SEQUENCE')or'-1')
local releaseFrame=-1
local fightAction=os.getenv('ARMY_FIGHT_ACTION')or'none'
local fightDelay=tonumber(os.getenv('ARMY_ACTION_DELAY')or'0')
assert(fightDelay>=0 and fightDelay<=600)
local stopPhase=tonumber(os.getenv('ARMY_STOP_PHASE')or'3')
local captureInterval=tonumber(os.getenv('ARMY_CAPTURE_INTERVAL')or'0')
local victoryMove=os.getenv('ARMY_VICTORY_MOVE')=='1'
local victoryAdaptive=os.getenv('ARMY_VICTORY_NAV')=='adaptive'
local victoryLast=nil
local victoryYaw=math.pi/3
local victoryDirection=3
assert(stopPhase>=3 and stopPhase<=8)
assert(fightAction=='none'or fightAction=='idle'or fightAction=='move'or fightAction=='jump'or fightAction=='dagger'or fightAction=='jump-dagger')
assert(closeButton==0 or closeButton==12)
local frameLimit=tonumber(os.getenv('ARMY_LIMIT')or'3600')
local stationary=os.getenv('ARMY_STATIONARY_WINDOW')=='1'
local centerRadius=tonumber(os.getenv('ARMY_CENTER_RADIUS')or'500')
local prepareOnly=os.getenv('ARMY_PREP_ONLY')=='1'
assert(centerRadius>=20 and centerRadius<=1000)
local skipMode=os.getenv('ARMY_SKIP_MODE')or'periodic'
assert(skipMode=='periodic'or skipMode=='none'or skipMode=='voice')
assert(variant=='normal'or variant=='inventory')
local frame,started,done=0,false,false
local introSetup=os.getenv('ARMY_INTRO_SETUP')=='1'
assert(not(prepareOnly and introSetup),'Preparation must not inject the introduction')
local sawInventory=false
local previousPadMask=0
local options=assert(io.open('probe-options.json','w'))
options:write(string.format('{"variant":"%s","menuAt":%d,"menuHold":%d,"frameLimit":%d,"stationary":%s,"skipMode":"%s","introSetup":%s}\n',variant,menuAt,menuHold,frameLimit,tostring(stationary),skipMode,tostring(introSetup)));options:close()
local bufferOptions=assert(io.open('buffer-options.json','w'));bufferOptions:write(string.format('{"closeAt":%d,"reopenAt":%d,"closeButton":%d,"moveFrom":%d,"fixedApproach":%s}\n',bufferClose,bufferReopen,closeButton,moveFrom,tostring(fixedApproach)));bufferOptions:close()
local rngLog,rngBreakpoint,rngLoaded,rngCount=nil,nil,false,0
local decisionLog,decisionBreakpoint=nil,nil
local pendingDecisions={}
local pendingHits={}
local hitLog,hitBreakpoint=nil,nil
local contactLog,contactBreakpoint=nil,nil
local pendingContacts={}
if os.getenv('ARMY_TRACE_RNG')=='1'then
 rngLog=assert(io.open('rng-calls.jsonl','w'))
 decisionLog=assert(io.open('combat-decisions.jsonl','w'))
 hitLog=assert(io.open('combat-hit-decisions.jsonl','w'))
 contactLog=assert(io.open('combat-contacts.jsonl','w'))
 local regs=PCSX.getRegisters();local scratch=ffi.cast('const uint8_t*',PCSX.getScratchPtr())
 rngBreakpoint=PCSX.addBreakpoint(0x800a43d8,'Exec',4,'Own army RNG observation',function()
  if not rngLoaded or done then return true end
  rngCount=rngCount+1;assert(rngCount<=100000,'Army RNG trace exceeded bound')
  local hint=tonumber(ffi.cast('const uint32_t*',scratch+0xa4)[0]);local actor=ptr(hint)
  local post=tonumber(regs.GPR.n.v0);local output=math.floor(post/65536)%32768
  local hp,action,delay,subtype=-32768,-1,-32768,-1
  local ld=ptr(u32(0xee978));local voice=ld and i32(ld+0x10)or-32768
  if actor then
   local rec=ptr(u32(actor+0xc));local private=ptr(u32(actor+0x90))
   if u32(0x10000)==25 and rec and s16(rec+4)==3 then subtype=tonumber(ram[rec+6]);hp=s16(actor+0x5a);action=tonumber(ram[actor+0x5c]);if private then delay=s16(private+4)end end
  end
  local ra=tonumber(regs.GPR.n.ra)
  if ra==0x80016b18 then pendingHits[hint]={output=output,hp=hp,subtype=subtype}end
  if ra==0x80016e20 then pendingDecisions[hint]={variant=output,frame=frame}end
  if ra==0x80016e58 and pendingDecisions[hint]then pendingDecisions[hint].delay=output end
  rngLog:write(string.format('{"frame":%d,"vblank":%d,"gameFrame":%d,"mode":%d,"submode":%d,"level":%d,"callerRA":%d,"actorScratchHint":%d,"before":%d,"afterRegister":%d,"output":%d,"actorHPBefore":%d,"actorActionBefore":%d,"actorDelayBefore":%d,"actorSubtype":%d,"levelVoiceHandleBefore":%d}\n',frame,u32(0xeddac),u32(0xeee60),u32(0xeee64),u32(0xeee70),u32(0xeee2c),tonumber(regs.GPR.n.ra),hint,u32(0xf3994),post,output,hp,action,delay,subtype,voice))
  return true
 end)
 contactBreakpoint=PCSX.addBreakpoint(0x80016aac,'Exec',4,'Own collision source observation',function()
  if not rngLoaded or done or u32(0x10000)~=25 then return true end
  local hint=tonumber(ffi.cast('const uint32_t*',scratch+0xa4)[0]);local actor=ptr(hint);local event=ptr(u32(0xedb28))
  if actor and event and s16(event)==1 then
   local source=u32(event+4);local attacker=ptr(source);local rec=attacker and ptr(u32(attacker+0xc))
   pendingContacts[hint]={hp=s16(actor+0x5a),source=source,form=rec and s16(rec+4)or-1}
  end
  return true
 end)
 hitBreakpoint=PCSX.addBreakpoint(0x80016b78,'Exec',4,'Own collision decision readback',function()
  if not rngLoaded or done or u32(0x10000)~=25 then return true end
  local hint=tonumber(ffi.cast('const uint32_t*',scratch+0xa4)[0]);local pending=pendingHits[hint]
  local contact=pendingContacts[hint]
  if contact then
   local actor=assert(ptr(hint));contactLog:write(string.format('{"frame":%d,"actor":%d,"sourceActor":%d,"sourceForm":%d,"hpBefore":%d,"hpAfter":%d}\n',frame,hint,contact.source,contact.form,contact.hp,s16(actor+0x5a)));pendingContacts[hint]=nil
  end
  if not pending then return true end
  local actor=assert(ptr(hint))
  hitLog:write(string.format('{"frame":%d,"actor":%d,"subtype":%d,"draw":%d,"hpBefore":%d,"hpAfter":%d,"actionAfter":%d}\n',frame,hint,pending.subtype,pending.output,pending.hp,s16(actor+0x5a),tonumber(ram[actor+0x5c])))
  pendingHits[hint]=nil;return true
 end)
 decisionBreakpoint=PCSX.addBreakpoint(0x80016ef8,'Exec',4,'Own soldier decision readback',function()
  if not rngLoaded or done or u32(0x10000)~=25 then return true end
  local hint=tonumber(ffi.cast('const uint32_t*',scratch+0xa4)[0]);local pending=pendingDecisions[hint]
  if not pending or not pending.delay then return true end
  local actor=assert(ptr(hint));local animation=assert(ptr(u32(actor+0x74)));local private=assert(ptr(u32(actor+0x90)))
  decisionLog:write(string.format('{"frame":%d,"actor":%d,"variantDraw":%d,"delayDraw":%d,"expectedVariant":%d,"actualVariant":%d,"expectedDelay":%d,"actualDelay":%d,"action":%d}\n',frame,hint,pending.variant,pending.delay,23+pending.variant%2,tonumber(ram[animation+0x20]),pending.delay%60,s16(private+4),tonumber(ram[actor+0x5c])))
  pendingDecisions[hint]=nil;return true
 end)
end
local fightOptions=assert(io.open('fight-options.json','w'));fightOptions:write(string.format('{"action":"%s","delayVsyncs":%d,"cadenceVsyncs":48,"attackPhase":[12,18],"jumpPhase":[0,6]}\n',fightAction,fightDelay));fightOptions:close()
local log=assert(io.open('samples.jsonl','w'))
local slots=assert(io.open('army-slots.jsonl','w'))
local last,active,blocked=nil,0,0;local yaw=math.pi/3
local dirs={{5},{5,4},{4},{4,7},{7},{7,6},{6},{6,5}}
local function dump(label)local f=assert(io.open(label..'.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()end
local function counts()
 local friendly,enemy,n=0,0,ptr(u32(0xee888));local seen={};local visits=0
 while n and n~=0xee884 and not seen[n]and visits<300 do
  seen[n]=true;visits=visits+1
  local rec=ptr(u32(n+0xc))
  if rec and s16(rec+4)==3 then if ram[rec+6]==0 then friendly=friendly+1 else enemy=enemy+1 end end
  n=ptr(u32(n+4))
 end
 return friendly,enemy
end
local function tick()
 if done then return end
 frame=frame+1;release()
 if rngLog and frame==1 then
  assert(u32(0xa43d8)==0xac223994,'Unexpected RNG store instruction')
  assert(u32(0x16e54)==0xa0620020 and u32(0x16e8c)==0xa6420004,'Unexpected soldier decision stores')
 end
 local g=ptr(u32(0xedb3c));local a=g and ptr(u32(g+0x530));local ld=ptr(u32(0xee978))
 assert(u32(0xeee64)==3 and u32(0xeee2c)==23 and u32(0x10000)==25 and g and ld,'Lost final-level context')
 if frame==120 and introSetup then
  assert(u32(ld)==0,'Refusing prerequisite write after encounter progression')
  ffi.cast('uint8_t*',ram+0xee93f)[0]=1
  dump('injected-introduction-prerequisite')
 end
 local f,e=counts()
 local v={frame=frame,mode=3,level=23,overlay=25,vblank=u32(0xeddac),gameFrame=u32(0xeee60),submode=u32(0xeee70),gameFlags=u32(0xeee24),audioStateCandidate=u32(0xeeef8),requestedTrackCandidate=s16(0xeeefc),queuedTrackCandidate=s16(0xeeefe),phaseIndex=u32(ld),armyOutcome=i32(ld+4),countedFriendly=f,countedEnemy=e,rngState=u32(0xf3994),health=i32(g)}
 local sequence=ptr(u32(0xedc18))
 v.sequencePointer=u32(0xedc18)
 v.previousEffectivePadMask=previousPadMask;v.menuRequestAt=menuAt;v.frameLimit=frameLimit;v.centerRadius=centerRadius;v.prepareOnly=prepareOnly and 1 or 0
 v.uiStackCount=u32(0xedbd8);v.uiBlockingCount=tonumber(ffi.cast('const uint16_t*',ram+0xedbe8)[0])
 local liveInventory=false
 if v.uiStackCount<=4 then
  for slot=0,v.uiStackCount-1 do
   local w=ptr(u32(0xef390+slot*4))
   if w then
    local desc=ptr(u32(w+4));local class=desc and u32(desc)or 0;local flags=s16(w+0x44)%65536
    v['uiClass'..slot]=class;v['uiFlags'..slot]=flags;v['uiAnimation'..slot]=s16(w+0x7a)
    if class==0x800da358 and math.floor(flags/32)%4==0 then liveInventory=true end
   end
  end
 end
 for slot=0,3 do
  local req=0xef3a0+slot*12;v['requestClass'..slot]=u32(req);v['requestFlags'..slot]=s16(req+4)%65536;v['requestDelay'..slot]=s16(req+10)
 end
 v.liveInventory=liveInventory and 1 or 0
 if v.submode==2 and math.floor(v.gameFlags/4)%2==1 and liveInventory and v.uiBlockingCount>0 then sawInventory=true end
 v.sawInventory=sawInventory and 1 or 0
 if sequence then v.sequenceFlags=u32(sequence+0x20);v.sequenceDescriptor=u32(sequence+0x24);v.sequenceFrame=u32(sequence+0x34);v.sequenceCameraTarget=u32(sequence+0x2c)end
 v.playerActorPointer=a and a+0x80000000 or 0
 v.cameraActorPointer=u32(0xeda48);v.cameraReferencePointer=u32(0xeda4c)
 v.releaseSequence=releaseSequence;v.releaseInputFrame=releaseFrame
 if a then
  v.x=i32(a+0x24);v.y=i32(a+0x28);v.z=i32(a+0x2c);v.actorFlags=u32(a+0x50)
  local p=ptr(u32(a+0x80));if p then v.motion48=i32(p+0x48);v.motion50=i32(p+0x50)end
 end
 v.stationaryWindow=stationary and 1 or 0
 v.triggerCode=s16(g+0x64e)
 v.equippedWeapon=i32(g+0xc);v.daggerAmmo=s16(g+0x94)%65536
 v.cpuPC=tonumber(PCSX.getRegisters().pc);v.stopPhase=stopPhase;v.victoryMove=victoryMove and 1 or 0
 if fightAction~='none'then assert(v.phaseIndex==2 or v.phaseIndex==3,'Fight comparison left army phase');assert(v.equippedWeapon==3,'Daggers must remain equipped')end
 for i=9,19 do v['scriptFlag'..i]=tonumber(ram[0xee934+i])end
 local stop=frame>=frameLimit or not a or v.health<=0 or v.phaseIndex>=stopPhase
 local fields={'"phase":"'..(stop and'finished'or variant)..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end;log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame%30==1 then
  for team,base in pairs({friendly=0x1c950,enemy=0x1c9b0})do
   for i=0,7 do
    local value=u32(base+i*12+8);local p=ptr(value)
    slots:write(string.format('{"frame":%d,"team":"%s","slot":%d,"actor":%d,"hp":%d,"action":%d}\n',frame,team,i,value,p and s16(p+0x5a)or-32768,p and tonumber(ram[p+0x5c])or-1))
   end
  end;slots:flush()
 end
 if frame==1 then dump('initial')end
 if captureInterval>0 and(frame-1)%captureInterval==0 then
  local captureFrame=frame
  PCSX.nextTick(function()
   local ss=PCSX.GPU.takeScreenShot();local stem=string.format('view-%05d',captureFrame)
   local f=Support.File.open(stem..'.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
   f=assert(io.open(stem..'.json','w'));f:write(string.format('{"frame":%d,"width":%d,"height":%d,"bpp":"%s"}',captureFrame,ss.width,ss.height,tostring(ss.bpp)));f:close()
  end)
 end
 if stop then
  done=true;release();if rngBreakpoint then rngBreakpoint:remove();decisionBreakpoint:remove();hitBreakpoint:remove();contactBreakpoint:remove();rngLog:close();decisionLog:close();hitLog:close();contactLog:close()end;dump('final');log:close();slots:close()
  PCSX.nextTick(function()
   local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
   local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
   f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();local objective=v.phaseIndex>=1 and (variant=='normal'or sawInventory)
   if prepareOnly then objective=v.phaseIndex==0 and a and v.health>0 and v.x*v.x+v.z*v.z<=centerRadius^2 end
   PCSX.quit(objective and 0 or 1)
  end);return
 end
 -- Walk toward the authored arena center, with no coordinate/phase writes.
 local movementInput=(v.submode==0 or (variant=='inventory'and v.submode==2))
 if stationary and frame>=60 and frame<132 then movementInput=false end
 if frame<moveFrom then movementInput=false end
 if frame%12==1 and a and movementInput then
  if last then local dx,dz=v.x-last.x,v.z-last.z;if dx*dx+dz*dz>64 then yaw=math.atan2(dz,dx)-active*math.pi/4;blocked=0 else blocked=blocked+1 end end
  active=math.floor((math.atan2(-v.z,-v.x)-yaw)/(math.pi/4)+0.5)%8
  if blocked>8 then active=(active+1)%8 end
  last={x=v.x,z=v.z}
 end
 if a and v.x*v.x+v.z*v.z>centerRadius^2 and v.phaseIndex<2 and movementInput then for _,b in ipairs(fixedApproach and {4,7}or dirs[active+1])do pad.setOverride(b)end end
 if variant=='inventory'and frame>=menuAt and frame<menuAt+menuHold then pad.setOverride(0)end
 if bufferClose>0 and frame>=bufferClose and frame<bufferClose+2 then pad.setOverride(closeButton)end
 if bufferReopen>0 and frame>=bufferReopen and frame<bufferReopen+2 then pad.setOverride(0)end
 -- Triangle is the observed book/dialogue dismissal control. An inventory-open
 -- trial needs interpretation of actual submode/flags, not an assumed open UI.
 local voiceWaiting=v.sequenceFlags and math.floor(v.sequenceFlags/4096)%2==1
 if releaseFrame<0 and releaseSequence>=0 and v.sequenceFrame and v.sequenceFrame>=releaseSequence and liveInventory then releaseFrame=frame end
 local releasing=releaseFrame>=0 and frame<releaseFrame+2
 if releasing then pad.setOverride(0)end
 if not releasing and skipMode~='none'and frame%60<6 and v.gameFlags%2==1 and (skipMode=='periodic'or voiceWaiting)then pad.setOverride(12)end
 local fightTick=frame-1-fightDelay
 if fightAction~='none'and fightTick>=0 and v.phaseIndex==2 and v.submode==0 and v.gameFlags%2==0 then
  assert(v.z>=150 and math.abs(v.x)<800,'Movement trial left bounded lower arena area')
  if fightAction=='move'then
   local buttons=math.floor((frame-1)/40)%2==0 and {5,6}or{4,7};for _,b in ipairs(buttons)do pad.setOverride(b)end
  end
  if (fightAction=='jump'or fightAction=='jump-dagger')and fightTick%48<6 then pad.setOverride(13)end
  if (fightAction=='dagger'or fightAction=='jump-dagger')and fightTick%48>=12 and fightTick%48<18 and v.daggerAmmo>0 then pad.setOverride(14)end
 end
 if victoryMove and v.armyOutcome==1 then
  if victoryAdaptive then
   if not victoryLast or frame-victoryLast.frame>=8 then
    if victoryLast then
     local dx,dz=v.x-victoryLast.x,v.z-victoryLast.z
     if dx*dx+dz*dz>16 then victoryYaw=math.atan2(dz,dx)-victoryDirection*math.pi/4 end
    end
    victoryDirection=math.floor((math.atan2(-1800-v.z,-v.x)-victoryYaw)/(math.pi/4)+0.5)%8
    victoryLast={frame=frame,x=v.x,z=v.z}
   end
   if v.x*v.x+(v.z+1800)^2>150^2 then for _,b in ipairs(dirs[victoryDirection+1])do pad.setOverride(b)end end
  elseif v.z>-1600 then pad.setOverride(4);pad.setOverride(7)end
 end
 previousPadMask=0;for b=0,15 do if pad.getButton(b)then previousPadMask=previousPadMask+2^b end end
end
ArmyProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close();rngLoaded=true end);return end
 local ok,err=pcall(tick);if not ok then release();print('ARMY_PROBE_ERROR '..tostring(err));log:flush();slots:flush();PCSX.quit(1)end
end)
