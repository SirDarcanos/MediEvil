-- Exporter contract test with synthetic RAM and mocked BizHawk APIs.
-- Usage from a Lua host: dofile(this_file)(bridge_path, fixture_path, output_dir)
-- This tests the real Lua source, NOT BizHawk/NLua or Windows named mappings.
return function(source, fixture_path, output)
 local f=assert(io.open(fixture_path,'rb'));local ram=f:read('*a');f:close();assert(#ram==0x200000)
 local frame,stamp,paused,system,domain_size=0,1000,false,'PSX',0x200000
 local bytes,writes,reads,exit_callback={},0,0,nil
 local env=setmetatable({},{__index=_G})
 env.os={time=function()return stamp end}
 env.console={log=function()end}
 env.client={ispaused=function()return paused end}
 env.emu={framecount=function()return frame end,getsystemid=function()return system end,yield=function()coroutine.yield()end}
 env.event={onexit=function(fn)exit_callback=fn end}
 env.memory={getmemorydomainlist=function()return {[0]='MainRAM'}end,getmemorydomainsize=function(name)assert(name=='MainRAM');return domain_size end,
  read_bytes_as_array=function(address,length,domain)
   assert(domain=='MainRAM'and address>=0 and address+length<=#ram);reads=reads+1
   local t={};for i=1,length do t[i]=ram:byte(address+i)end;return t
  end}
 env.comm={mmfWriteBytes=function(name,t)
  assert(name=='MediEvilLiveMap-BizHawk-v1'and #t<=512);writes=writes+1
  if #bytes==0 then assert(#t==512,'Mapping must be allocated at full capacity')end
  for i,v in ipairs(t)do assert(v>=0 and v<=255 and v%1==0);bytes[i]=v end
  return #t
 end}
 local chunk
 if setfenv then chunk=assert(loadfile(source));setfenv(chunk,env)else chunk=assert(loadfile(source,'t',env))end
 local co=coroutine.create(chunk)
 local function step()local ok,e=coroutine.resume(co);assert(ok,e);assert(coroutine.status(co)=='suspended')end
 local function u32(at)return bytes[at+1]+bytes[at+2]*256+bytes[at+3]*65536+bytes[at+4]*16777216 end
 local function save(label)
  local chars={};for i=1,512 do chars[i]=string.char(bytes[i])end
  local file=assert(io.open(output..'/'..label..'.packet','wb'));file:write(table.concat(chars));file:close()
 end
 step();assert(u32(8)==2 and u32(16)==1 and u32(20)==9);save('live')
 frame=2;stamp=1001;paused=true;step();assert(u32(16)==2);save('paused')
 local old_writes=writes;step();assert(writes==old_writes,'Unchanged samples should not flood the host')
 stamp=1002;step();assert(writes==old_writes+3,'Paused exporter must keep its heartbeat');save('paused-heartbeat')
 local old_reads=reads;system='NES';frame=4;step();assert(u32(16)==0 and reads==old_reads,'Wrong core must not read PS1 memory');save('wrong-core')
 system='PSX';domain_size=1024;frame=6;step();assert(u32(16)==0 and reads==old_reads,'Wrong domain size must not export');save('wrong-domain')
 domain_size=0x200000;frame=8;stamp=1003;paused=false;step();assert(u32(16)==1);save('resumed')
 assert(exit_callback);exit_callback();assert(u32(16)==0);save('stopped')
 return {writes=writes,reads=reads,checks=7}
end
