-- Finite title input experiments in our private emulator; no guest RAM pokes.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function i32(a)return tonumber(ffi.cast('const int32_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801ffe00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local action=os.getenv('MENU_ACTION')or'seed'
assert(action=='seed'or action=='newgame'or action=='idle'or action=='navigate'or action=='load')
local confirm=tonumber(os.getenv('MENU_BUTTON')or'3')
local frame,started,done,readyAt=0,false,false,nil
local acceptedAt=nil
local log=assert(io.open('samples.jsonl','w'))
local function dump(label)
 local f=assert(io.open(string.format('frame-%05d-%s.ram',frame,label),'wb'));f:write(ffi.string(ram,0x200000));f:close()
end
local function finish(ok)
 done=true;release();dump('end');log:close()
 PCSX.nextTick(function()
  local f=Support.File.open(action=='seed'and'menu.state'or'end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close()
  local ss=PCSX.GPU.takeScreenShot();f=Support.File.open('end.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open('end-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close();PCSX.quit(ok and 0 or 1)
 end)
end
local function tick()
 if done then return end
 frame=frame+1;release()
 local mode,header=u32(0xeee64),u32(0x10000)
 local title=mode==2 and header==24 and ptr(u32(0xedc1c))or nil
 local flow=title and i32(title)or-1
 local highlight=title and u32(0x19134)or-1
 if action=='seed'and flow==1 and highlight==3 and not readyAt then readyAt=frame end
 if action=='newgame'and flow==2 and not acceptedAt then acceptedAt=frame end
 local press=-1
 if action=='seed'then
  if not readyAt and frame>360 and frame%240<6 then press=3 end
 elseif action=='newgame'then
  if frame>=1 and frame<7 then press=confirm end
 elseif action=='navigate'or action=='load'then
  if frame>=1 and frame<7 then press=6 end
  if frame>=60 and frame<66 then press=action=='load'and confirm or 4 end
 end
 if press>=0 then pad.setOverride(press)end
 local success=false;local terminal=false
 if action=='seed'then
  success=readyAt and frame-readyAt>=180 and flow==1 and highlight==3
  terminal=success or flow==2 or frame>=8400
 elseif action=='newgame'then
  success=acceptedAt~=nil;terminal=(acceptedAt and frame-acceptedAt>=180)or frame>=1200
 else
  terminal=frame>=840 or flow==2
  success=terminal and flow~=2
 end
 local mask=0;for b=0,15 do if pad.getButton(b)then mask=mask+2^b end end
 local v={frame=frame,mode=mode,overlay=header,gameFrame=u32(0xeee60),vblank=u32(0xeddac),titlePointer=u32(0xedc1c),titleFlow=flow,legacyHighlight=highlight,inputButton=press,effectivePadMask=mask,audioByte=tonumber(ram[0xf6e83])}
 if acceptedAt then v.acceptedAt=acceptedAt end
 if title and flow>=0 and flow<=6 then
  v.updateCallback=u32(title+0x180);v.finishCallback=u32(title+0x184);v.uiCountdown=i32(title+0x188);v.menuSelection=i32(title+0x190)
 end
 local ac=ptr(u32(0xedb74));v.transitionPointer=u32(0xedb74)
 if ac then for off=0,0x1c,4 do v['transitionWord'..off]=u32(ac+off)end end
 local fields={'"phase":"'..(terminal and'finished'or action)..'"'}
 for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end
 log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame==1 or frame%240==0 then dump(action)end
 if terminal then finish(success)end
end
TitleProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true
  if action~='seed'then PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end)end
  return
 end
 local ok,err=pcall(tick)
 if not ok then release();print('TITLE_PROBE_ERROR '..tostring(err));log:flush();PCSX.quit(1)end
end)
