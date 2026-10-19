-- Research only: controller input + read-only RAM, in an isolated Redux child.
-- No emulated RAM writes or edits to the game's executable.
local ffi = require('ffi')
local ram = ffi.cast('const uint8_t*', PCSX.getMemPtr())
local pad = PCSX.SIO0.slots[1].pads[1]
local scenario = assert(os.getenv('MEMORY_SCENARIO'))
local frame, started, playFrames = 0, false, 0
local lastPhase = ''
local log = assert(io.open('samples.jsonl', 'w'))
local function u32(a) return tonumber(ffi.cast('const uint32_t*', ram+a)[0]) end
local function i32(a) return tonumber(ffi.cast('const int32_t*', ram+a)[0]) end
local function u16(a) return tonumber(ffi.cast('const uint16_t*', ram+a)[0]) end
local function physical(v)
    if v >= 0x80001000 and v < 0x801ff000 and v%4 == 0 then return v-0x80000000 end
end
local function release() for b=0,15 do pad.clearOverride(b) end end
local function dump(label)
    local stem = string.format('frame-%05d-%s', frame, label)
    local f=assert(io.open(stem..'.ram','wb')); f:write(ffi.string(ram,0x200000)); f:close()
end
local function sample(phase)
    local values={frame=frame,mode=u32(0xeee64),level=u32(0xeee2c),overlay=u32(0x10000),
        gameFrame=u32(0xeee60),result=u32(0xeee6c),submode=u32(0xeee70),
        nextLevel=u32(0xeee30),state=u32(0xedb3c),legacyHealth=u32(0xf1648),
        gold=u16(0xf828c),starRune=u16(0xf823c),smallSword=u16(0xf81f4),
        daggers=u16(0xf8208),shield=u16(0xf827c),bottles=u32(0xf817c),
        boss=u32(0xf170c),bossHealth=u32(0xf1714),menuHighlight=tonumber(ram[0x19134]),
        newGamePressed=tonumber(ram[0xf6e83])}
    local state=physical(values.state)
    if state and state<0x1ff000 then
        values.health=u32(state); values.actor=u32(state+0x530)
        local actor=physical(values.actor)
        if actor and actor<0x1ff000 then
            values.x=i32(actor+0x24);values.y=i32(actor+0x28);values.z=i32(actor+0x2c)
            values.physics=u32(actor+0x80)
            local physics=physical(values.physics)
            if physics and physics<0x1ff000 then
                values.fixedX=i32(physics+0x30);values.fixedY=i32(physics+0x34);values.fixedZ=i32(physics+0x38)
            end
        end
    end
    local parts={'"phase":"'..phase..'"'}
    for k,v in pairs(values) do parts[#parts+1]='"'..k..'":'..v end
    log:write('{'..table.concat(parts,',')..'}\n'); log:flush()
end
local function stop()
    release();dump('final');sample('finished');log:close()
    PCSX.nextTick(function() PCSX.quit(0) end)
end
local function tick()
    frame=frame+1;release()
    local mode=u32(0xeee64)
    local phase='boot'
    if scenario=='boot' then
        -- Start/cross pulses, used only in this disposable no-save run.
        if frame>360 and mode~=3 then
            if frame%180<8 then pad.setOverride(3) end
            if frame%180>=90 and frame%180<98 then pad.setOverride(14) end
        end
        local state=physical(u32(0xedb3c))
        local actor=state and physical(u32(state+0x530))
        if mode==3 and u32(0xeee2c)==6 and actor and u32(0xeee60)>0 then
            playFrames=playFrames+1;phase='crypt'
        else playFrames=0 end
        if frame%60==0 then dump(phase) end
        if playFrames>=480 or frame>=10000 then stop();return end
    else
        -- Rest, horizontal movement, vertical movement/jump candidate, camera only,
        -- pause/unpause, return to rest. Button semantics need observation.
        if frame<180 then phase='rest'
        elseif frame<300 then phase='right';pad.setOverride(5)
        elseif frame<420 then phase='rest-after-right'
        elseif frame<540 then phase='up';pad.setOverride(4)
        elseif frame<660 then phase='rest-after-up'
        elseif frame<780 then phase='left';pad.setOverride(7)
        elseif frame<900 then phase='rest-after-left'
        elseif frame<1020 then phase='down';pad.setOverride(6)
        elseif frame<1140 then phase='jump-candidate';if frame%60<8 then pad.setOverride(14) end
        elseif frame<1260 then phase='camera';pad.setOverride(10)
        elseif frame<1380 then phase='rest-after-camera'
        elseif frame<1500 then phase='pause';if frame<1388 then pad.setOverride(3) end
        elseif frame<1620 then phase='unpause';if frame<1508 then pad.setOverride(3) end
        else phase='final-rest' end
        if phase~=lastPhase or frame%60==0 then dump(phase) end
        if frame>=1800 then stop();return end
    end
    sample(phase);lastPhase=phase
end
MemoryProbe=PCSX.Events.createEventListener('GPU::Vsync',function()
    if not started then
        started=true
        local state=os.getenv('MEMORY_SEED')
        if state and state~='' then
            PCSX.nextTick(function()
                local file=Support.File.open(state);PCSX.loadSaveState(file);file:close()
            end)
            return
        end
    end
    local ok,err=pcall(tick)
    if not ok then print('MEMORY_PROBE_ERROR '..tostring(err));log:flush();PCSX.quit(1) end
end)
