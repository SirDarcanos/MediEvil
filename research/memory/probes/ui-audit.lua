-- Bounded controller-only UI observation on an owned restored state.
-- All files/cards belong to this private run. No guest RAM/register pokes.
local ffi=require('ffi')
local ram=ffi.cast('const uint8_t*',PCSX.getMemPtr())
local pad=PCSX.SIO0.slots[1].pads[1]
local function u32(a)return tonumber(ffi.cast('const uint32_t*',ram+a)[0])end
local function s16(a)return tonumber(ffi.cast('const int16_t*',ram+a)[0])end
local function ptr(v)if v>=0x80001000 and v<0x801fff00 and v%4==0 then return v-0x80000000 end end
local function release()for b=0,15 do pad.clearOverride(b)end end
local button=tonumber(os.getenv('UI_BUTTON')or'-1')
local inputAt=tonumber(os.getenv('UI_INPUT_AT')or'300')
local limit=tonumber(os.getenv('UI_LIMIT')or'900')
local sequence={}
local schedule=os.getenv('UI_SEQUENCE')
if schedule then
 for at,b in schedule:gmatch('(%d+):(%d+)')do
  at,b=tonumber(at),tonumber(b);assert(at>=1 and at<limit and b<=15)
  sequence[#sequence+1]={at=at,button=b}
 end
 assert(#sequence>0)
else sequence={{at=inputAt,button=button}}end
local frame,started,done=0,false,false
local log=assert(io.open('samples.jsonl','w'))
local function image(stem)
 PCSX.nextTick(function()
  local ss=PCSX.GPU.takeScreenShot();local f=Support.File.open(stem..'.pixels','TRUNCATE');f:writeMoveSlice(ss.data);f:close()
  f=assert(io.open(stem..'-image.json','w'));f:write(string.format('{"width":%d,"height":%d,"bpp":"%s"}',ss.width,ss.height,tostring(ss.bpp)));f:close()
 end)
end
local function tick()
 if done then return end
 frame=frame+1;release()
 local requested=-1
 for _,event in ipairs(sequence)do
  if event.button>=0 and frame>=event.at and frame<event.at+6 then pad.setOverride(event.button);requested=event.button end
 end
 local mask=0;for b=0,15 do if pad.getButton(b)then mask=mask+2^b end end
 local stop=frame>=limit
 local v={frame=frame,mode=u32(0xeee64),overlay=u32(0x10000),gameFrame=u32(0xeee60),vblank=u32(0xeddac),submode=u32(0xeee70),gameFlags=u32(0xeee24),result=u32(0xeee6c),uiCount=u32(0xedbd8),uiBlocking=s16(0xedbe8),requestedButton=requested,effectivePadMask=mask,cpuPC=tonumber(PCSX.getRegisters().pc)}
 local g=v.mode==3 and ptr(u32(0xedb3c))
 if g then v.weapon=u32(g+0xc);v.health=u32(g)end
 if v.uiCount<=4 then for i=0,v.uiCount-1 do
  local w=ptr(u32(0xef390+i*4));local d=w and ptr(u32(w+4))
  if w then v['uiClass'..i]=d and u32(d)or 0;v['uiFlags'..i]=s16(w+0x44)%65536 end
 end end
 local fields={'"phase":"'..(stop and'finished'or'ui-observe')..'"'};for k,n in pairs(v)do fields[#fields+1]='"'..k..'":'..n end;log:write('{'..table.concat(fields,',')..'}\n');log:flush()
 if frame==inputAt-1 then image('before-input')end
 if stop then
  done=true;release();log:close();image('end')
  local f=assert(io.open('final.ram','wb'));f:write(ffi.string(ram,0x200000));f:close()
  PCSX.nextTick(function()local f=Support.File.open('end.state','TRUNCATE');f:writeMoveSlice(PCSX.createSaveState());f:close();PCSX.quit(0)end)
 end
end
UiAudit=PCSX.Events.createEventListener('GPU::Vsync',function()
 if not started then started=true;PCSX.nextTick(function()local f=Support.File.open(assert(os.getenv('MEMORY_SEED')));PCSX.loadSaveState(f);f:close()end);return end
 local ok,err=pcall(tick);if not ok then release();print('UI_AUDIT_ERROR '..tostring(err));log:flush();PCSX.quit(1)end
end)
