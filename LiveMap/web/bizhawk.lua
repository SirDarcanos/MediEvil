-- MediEvil LiveMap: read-only BizHawk 2.11.1 / Windows bridge.
-- Load once in Tools > Lua Console. Keep one EmuHawk instance open.
-- Exports only small RAM ranges to a host named mapping; never writes to game
-- memory, changes input, pauses/resumes, or calls emu.frameadvance().
local NAME, SIZE, RAM = 'MediEvilLiveMap-BizHawk-v1', 512, 0x200000
local DOMAIN = 'MainRAM'
assert(comm and comm.mmfWriteBytes, 'BizHawk named-mapping API is required')
assert(memory.read_bytes_as_array and emu.yield, 'BizHawk 2.11.1 Lua APIs are required')
local seq = 0
local function word(t, n)
 n = n % 4294967296
 for _=1,4 do t[#t+1]=n%256; n=math.floor(n/256) end
end
local function header(sequence, stamp, status, count)
 local t={77,76,66,72} -- MLBH
 for _,v in ipairs({1,sequence,stamp,status,count,0,0}) do word(t,v) end
 return t
end
local function u32(address)
 local b=memory.read_bytes_as_array(address,4,DOMAIN)
 return b[1]+b[2]*256+b[3]*65536+b[4]*16777216
end
local function physical(p, length)
 local a
 if p>=0x80000000 and p<0x80200000 then a=p-0x80000000
 elseif p>=0xa0000000 and p<0xa0200000 then a=p-0xa0000000 end
 if a and a%4==0 and a+length<=RAM then return a end
end
local function main_ram_ready()
 if emu.getsystemid()~='PSX' then return false end
 local found=false
 for _,name in pairs(memory.getmemorydomainlist()) do if name==DOMAIN then found=true end end
 return found and memory.getmemorydomainsize(DOMAIN)==RAM
end
local function export(stamp, paused)
 local status, chunks=0,{}
 local function add(address,length)
  chunks[#chunks+1]={address=address,bytes=memory.read_bytes_as_array(address,length,DOMAIN)}
 end
 if main_ram_ready() then
  status=paused and 2 or 1
  local frame,root=u32(0xeee60),u32(0xedb3c)
  add(0x21ca4,32);add(0x485ec,32);add(0x99ad0,32)
  add(0xeee24,80);add(0xedb3c,4)
  local g=physical(root,0x6f0)
  if g then
   add(g+0x530,4)
   local actor_pointer=u32(g+0x530);local a=physical(actor_pointer,0x98)
   if a then
    add(a+0x24,12);add(a+0x80,4)
    local p=physical(u32(a+0x80),0x3c)
    if p then add(p+0x30,12) end
   end
   if u32(g+0x530)~=actor_pointer then return end
  end
  if frame~=u32(0xeee60) or root~=u32(0xedb3c) then return end
 end
 local odd=(seq+1)%4294967296;local even=(seq+2)%4294967296
 local packet=header(odd,stamp,status,#chunks)
 for _,chunk in ipairs(chunks) do
  word(packet,chunk.address);word(packet,#chunk.bytes)
  for _,byte in ipairs(chunk.bytes) do packet[#packet+1]=byte end
 end
 assert(#packet<=SIZE,'LiveMap bridge packet overflow')
 while #packet<SIZE do packet[#packet+1]=0 end
 -- Mark busy, copy a busy-marked packet, then publish the completed header.
 comm.mmfWriteBytes(NAME,header(odd,stamp,status,#chunks))
 comm.mmfWriteBytes(NAME,packet)
 comm.mmfWriteBytes(NAME,header(even,stamp,status,#chunks))
 seq=even
end
local blank={};for i=1,SIZE do blank[i]=0 end
local ok,err=pcall(function() comm.mmfWriteBytes(NAME,blank) end)
if not ok then error('LiveMap bridge needs Windows named mappings: '..tostring(err)) end
local function stop()
 pcall(function()
  local stamp=os.time()
  comm.mmfWriteBytes(NAME,header((seq+1)%4294967296,stamp,0,0))
  comm.mmfWriteBytes(NAME,header((seq+2)%4294967296,stamp,0,0))
 end)
end
event.onexit(stop)
console.log('LiveMap read-only bridge active. Open Windows LiveMap in this same Windows session/VM.')
local last_frame,last_stamp,last_pause=nil,nil,nil
while true do
 local frame,stamp,paused=emu.framecount(),os.time(),client.ispaused()
 if last_frame==nil or frame<last_frame or frame-last_frame>=2 or stamp~=last_stamp or paused~=last_pause then
  local success,message=pcall(export,stamp,paused)
  if not success then stop();error('LiveMap export stopped: '..tostring(message)) end
  last_frame,last_stamp,last_pause=frame,stamp,paused
 end
 -- Cooperative Lua scheduling works while paused; does not advance the game.
 emu.yield()
end
