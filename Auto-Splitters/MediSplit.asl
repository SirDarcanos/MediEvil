/**
 * MediSplit Any% — development ASL for MediEvil USA.
 * Route: 14 level completions, then Fazguls, Kardok and Zarok (17 splits).
 * No category selection, optional levels/bosses, HoH, Rune or automatic reset.
 * Original split policy: SirDarcanos, Xeelze, 7eraser7, BlackMenthol, NoobKillerRoof.
 * Xeelze's original credits Nazzareno96, TheReverendAlucard, Lalle and BlackMenthol.
 * Traditional ASL structure also informed by FranklyGD's Spyro PS1 splitter.
 * Legacy scripts remain unchanged. Actual LiveSplit/gameplay behavior is unverified.
 */
state("ePSXe") {}
state("duckstation") {}
state("duckstation-qt-x64-ReleaseLTCG") {}
state("duckstation-nogui-x64-ReleaseLTCG") {}
state("PCSX-Redux") {}
state("medievil") {}

startup
{
    settings.Add("autostart", true, "Autostart");
    settings.Add("autosplit", true, "Autosplit");
    settings.Add("autoend", true, "Autoend");

    // Native level IDs and their loaded headers, in Any% route order.
    // Crypt, Graveyard, Cemetery Hill, Mausoleum, Return, Enchanted Earth,
    // Pools, Lake, Crystal Caves, Gallows, Haunted Ruins, Ghost Ship, Entrance Hall, Time Device.
    vars.route = new int[] { 6, 1, 3, 4, 2, 15, 12, 22, 8, 16, 17, 19, 20, 21 };
    vars.headers = new int[] { 6, 12, 5, 7, 13, 8, 18, 17, 4, 10, 15, 11, 9, 23 };
    vars.step = 0;
    vars.processNames = new string[] { "ePSXe", "duckstation", "duckstation-qt-x64-ReleaseLTCG", "duckstation-nogui-x64-ReleaseLTCG", "PCSX-Redux", "medievil" };
    vars.baseRAMAddress = 0L;
    vars.ramPointerAddress = IntPtr.Zero;
    vars.ramMap = null;
    vars.ramView = null;
    vars.process = null;
    vars.recomp = false;
    vars.scanAfter = DateTime.MinValue;
    vars.producerStarted = 0L;
    vars.lastDiagnostic = "";
    vars.diagnose = (Action<string>)(message => {
        if (message != (string)vars.lastDiagnostic)
        {
            print("MediSplit: " + message);
            vars.lastDiagnostic = message;
        }
    });
    // Read gaps disarm observations, not the already-completed route.
    vars.clearObservation = (Action)(() => {
        vars.baseline = false;
        vars.armedBoss = null;
        vars.startEvent = false;
        vars.splitEvent = false;
    });
    vars.clearObservation();

    // ===== Read a PS1 field: host RAM base + offset, or the same offset in a named RAM view =====
    vars.read = (Func<uint, int, uint>)((address, width) => {
        if ((width != 1 && width != 2 && width != 4) || address < 0x80000000U ||
            address > 0x80200000U - (uint)width)
            throw new IOException("PS1 field outside main RAM");
        long offset = address - 0x80000000U;
        var view = (System.IO.MemoryMappedFiles.MemoryMappedViewAccessor)vars.ramView;
        if (view != null)
            return width == 4 ? view.ReadUInt32(offset) : width == 2 ? view.ReadUInt16(offset) : view.ReadByte(offset);
        long host = (long)vars.baseRAMAddress + offset;
        IntPtr at = IntPtr.Size == 4 ? new IntPtr(unchecked((int)host)) : new IntPtr(host);
        byte[] data;
        if (!((Process)vars.process).ReadBytes(at, width, out data))
            throw new IOException("RAM read failed");
        return width == 4 ? BitConverter.ToUInt32(data, 0)
            : width == 2 ? BitConverter.ToUInt16(data, 0) : data[0];
    });
    vars.supported = (Func<bool>)(() => {
        Func<uint, int, uint> read = (Func<uint, int, uint>)vars.read;
        try
        {
            // Two known USA instructions at each of three independent code locations.
            return read(0x80021ca4, 4) == 0x27bdffe8U && read(0x80021ca8, 4) == 0xafbf0010U &&
                read(0x800485ec, 4) == 0x3c021f80U && read(0x800485f0, 4) == 0x8c4200a4U &&
                read(0x80099ad0, 4) == 0x3c1c800fU && read(0x80099ad4, 4) == 0x279cd5d4U;
        }
        catch (IOException) { return false; }
    });
    vars.closeRAM = (Action)(() => {
        if (vars.ramView != null) ((IDisposable)vars.ramView).Dispose();
        if (vars.ramMap != null) ((IDisposable)vars.ramMap).Dispose();
        vars.ramView = null;
        vars.ramMap = null;
    });
    vars.findRAM = (Action<Process>)(process => {
        if (process.Is64Bit()) throw new IOException("ePSXe RAM lookup requires a 32-bit producer");
        var module = process.MainModule;
        if (module.ModuleMemorySize <= 0 || module.ModuleMemorySize > 0x4000000)
            throw new IOException("Unsupported ePSXe main module size");
        // Native RAM-base immediate: Jujstme/emu-help-v3 (GPL-3.0),
        // commit 10088d25496b3aa74023d89dda0a5c5193f2ebb1, Systems/PS1/Emulators/ePSXe.cs.
        var scanner = new SignatureScanner(process, module.BaseAddress, module.ModuleMemorySize);
        int candidates = 0, matches = 0;
        long found = 0;
        IntPtr pointerAddress = IntPtr.Zero;
        foreach (IntPtr at in scanner.ScanAll(new SigScanTarget(5, "C1 E1 10 8D 89 ?? ?? ?? ??")))
        {
            if (++candidates > 32) throw new IOException("Too many ePSXe RAM candidates");
            uint address;
            if (!process.ReadValue<uint>(at, out address) || address == 0 || address > uint.MaxValue - 0x200000U)
                continue;
            vars.baseRAMAddress = (long)address;
            if (!((Func<bool>)vars.supported)()) continue;
            matches++;
            found = address;
            pointerAddress = at;
        }
        if (matches != 1) throw new IOException(matches == 0
            ? "No supported ePSXe RAM base" : "Ambiguous ePSXe RAM bases");
        vars.baseRAMAddress = found;
        vars.ramPointerAddress = pointerAddress;
    });

    // Recomp v0.2b keeps PS1 RAM in a 4 MiB CoreCLR byte[]. Find its data, not the executable.
    vars.findRecompRAM = (Func<Process, long>)(process => {
        if (IntPtr.Size != 8 || !process.Is64Bit()) throw new IOException("Recomp needs a 64-bit ASL host");
        var matches = new HashSet<long>();
        foreach (var page in process.MemoryPages())
        {
            if (page.State != MemPageState.MEM_COMMIT || (page.Protect & MemPageProtect.PAGE_GUARD) != 0 ||
                ((uint)page.Protect & 0xeeU) == 0) continue;
            long start = page.BaseAddress.ToInt64();
            ulong length = page.RegionSize.ToUInt64();
            if (start <= 0 || length < 0x400000UL || length > (ulong)(long.MaxValue - start)) continue;
            long end = start + (long)length;
            // Overlap windows so a signature crossing their boundary is not lost.
            for (long offset = 0; offset < (long)length; offset += 0x100000 - 0x20)
            {
                if (process.HasExited) throw new IOException("Recomp exited during RAM lookup");
                int count = (int)Math.Min(0x100000L, (long)length - offset);
                if (count < 16) break;
                var scanner = new SignatureScanner(process, new IntPtr(start + offset), count);
                foreach (IntPtr at in scanner.ScanAll(new SigScanTarget(-0x21ca4, "E8 FF BD 27 10 00 BF AF BF 66 02 0C 00 00 00 00")))
                {
                    long address = at.ToInt64();
                    uint arrayLength;
                    // On 64-bit CoreCLR, a byte[] length is eight bytes before its data.
                    if (address < start + 8 || address > end - 0x400000 || (address & 7) != 0 ||
                        !process.ReadValue<uint>(new IntPtr(address - 8), out arrayLength) || arrayLength != 0x400000U) continue;
                    vars.baseRAMAddress = address;
                    if (!((Func<bool>)vars.supported)()) continue;
                    matches.Add(address);
                    if (matches.Count > 1) throw new IOException("Ambiguous Recomp RAM buffers; restart Recomp before the next attempt");
                }
            }
        }
        if (matches.Count == 0) throw new IOException("Recomp RAM not found; load the USA game first");
        return matches.First();
    });

    // Only check the live objects whose fields are used below.
    vars.pointerFits = (Func<uint, int, bool>)((pointer, length) =>
        length >= 0 && length <= 0x200000 && pointer >= 0x80000000U &&
        pointer <= 0x80200000U - (uint)length && (pointer & 3) == 0);
    vars.allocation = (Func<uint, int, int>)((pointer, required) => {
        if (pointer < 0x80000014U || !((Func<uint, int, bool>)vars.pointerFits)(pointer, required)) return 0;
        int signed = unchecked((int)((Func<uint, int, uint>)vars.read)(pointer - 4, 4));
        if (signed >= 0 || signed == int.MinValue) return 0;
        int capacity = -signed;
        return capacity >= required + 4 && (capacity & 3) == 0 &&
            ((Func<uint, int, bool>)vars.pointerFits)(pointer, capacity) ? capacity : 0;
    });
    vars.actorIdentity = (Func<uint, uint, uint, string>)((pointer, expectedDefinition, expectedConstructor) => {
        Func<uint, int, uint> read = (Func<uint, int, uint>)vars.read;
        Func<uint, int, bool> fits = (Func<uint, int, bool>)vars.pointerFits;
        int capacity = ((Func<uint, int, int>)vars.allocation)(pointer, 0x98);
        if (capacity == 0) return null;
        uint previous = read(pointer, 4), next = read(pointer + 4, 4);
        if (previous == pointer || next == pointer || !fits(previous, 8) || !fits(next, 8) ||
            read(previous + 4, 4) != pointer || read(next, 4) != pointer) return null;
        uint definition = read(pointer + 8, 4), record = read(pointer + 0xc, 4);
        if (definition != expectedDefinition || !fits(definition, 0x8c) || !fits(record, 8)) return null;
        uint constructor = read(definition + 0x88, 4);
        if ((expectedConstructor != 0 && constructor != expectedConstructor) ||
            constructor < 0x80010000U || !fits(constructor, 4)) return null;
        return pointer + ":" + capacity + ":" + definition + ":" + constructor + ":" + record + ":" + read(record, 4);
    });
}

init
{
    refreshRate = 30;
    vars.clearObservation();
    vars.closeRAM();
    vars.baseRAMAddress = 0L;
    vars.ramPointerAddress = IntPtr.Zero;
    vars.process = game;
    vars.recomp = string.Equals(game.ProcessName, "medievil", StringComparison.OrdinalIgnoreCase);
    vars.scanAfter = DateTime.MinValue;
    vars.producerStarted = game.StartTime.ToUniversalTime().Ticks;
}

update
{
    vars.startEvent = false;
    vars.splitEvent = false;
    try
    {
        int producers = 0;
        foreach (string name in (string[])vars.processNames)
            foreach (Process candidate in Process.GetProcessesByName(name))
                using (candidate) producers++;
        if (producers != 1) throw new IOException("No unique emulator process");
        game.Refresh();
        if (game.HasExited || game.StartTime.ToUniversalTime().Ticks != (long)vars.producerStarted)
            throw new IOException("Emulator process changed");
        if ((bool)vars.recomp)
        {
            if ((long)vars.baseRAMAddress == 0)
            {
                if (DateTime.UtcNow < (DateTime)vars.scanAfter) return false;
                vars.diagnose("Looking for Recomp RAM; wait for 'Any% USA' before New Game.");
                vars.baseRAMAddress = ((Func<Process, long>)vars.findRecompRAM)(game);
            }
            uint arrayLength;
            if (!game.ReadValue<uint>(new IntPtr((long)vars.baseRAMAddress - 8), out arrayLength) || arrayLength != 0x400000U)
                throw new IOException("Recomp RAM buffer changed");
        }
        else if (string.Equals(game.ProcessName, "ePSXe", StringComparison.OrdinalIgnoreCase))
        {
            if ((long)vars.baseRAMAddress == 0)
            {
                if (DateTime.UtcNow < (DateTime)vars.scanAfter) return false;
                vars.scanAfter = DateTime.UtcNow.AddSeconds(1);
                ((Action<Process>)vars.findRAM)(game);
            }
            uint address;
            if (!game.ReadValue<uint>((IntPtr)vars.ramPointerAddress, out address) || address != (long)vars.baseRAMAddress)
                throw new IOException("Emulator RAM base changed");
        }
        else
        {
            string mapping = string.Equals(game.ProcessName, "PCSX-Redux", StringComparison.OrdinalIgnoreCase)
                ? "pcsx-redux-wram-" + game.Id : "duckstation_" + game.Id;
            vars.ramMap = System.IO.MemoryMappedFiles.MemoryMappedFile.OpenExisting(mapping, System.IO.MemoryMappedFiles.MemoryMappedFileRights.Read);
            vars.ramView = ((System.IO.MemoryMappedFiles.MemoryMappedFile)vars.ramMap).CreateViewAccessor(0, 0x200000, System.IO.MemoryMappedFiles.MemoryMappedFileAccess.Read);
        }
        if (!((Func<bool>)vars.supported)()) throw new IOException("Unsupported USA code layout");
        Func<uint, int, uint> read = (Func<uint, int, uint>)vars.read;
        Func<uint, uint> u32 = address => read(address, 4);
        Func<uint, int> i32 = address => unchecked((int)read(address, 4));
        Func<uint, ushort> u16 = address => (ushort)read(address, 2);
        Func<uint, short> i16 = address => unchecked((short)read(address, 2));
        Func<uint, byte> u8 = address => (byte)read(address, 1);
        Func<uint, int, int> allocation = (Func<uint, int, int>)vars.allocation;
        Func<uint, uint, uint, string> actor = (Func<uint, uint, uint, string>)vars.actorIdentity;

        current.mode = i32(0x800eee64);
        current.level = i32(0x800eee2c);
        current.result = i32(0x800eee6c);
        current.header = u32(0x80010000);
        current.frame = u32(0x800eee60);
        current.vblank = u32(0x800eddac);
        current.gameRoot = u32(0x800edb3c);
        current.gameCapacity = 0;
        current.persistentValid = false;
        current.playerRoot = 0U;
        current.playerIdentity = null;
        current.deathSubstate = (short)0;
        current.liveOrigin = false;
        current.titleIdentity = null;
        current.titleValid = false;
        current.newGamePacket = false;
        current.controllerRoot = 0U;
        current.controllerCapacity = 0;
        current.finalContext = false;
        current.finalPhase = 0U;
        current.armyOutcome = 0;
        current.bossIdentity = null;
        current.bossHP = (short)0;
        current.bossAction = (byte)0;

        int step = (int)vars.step;
        int expectedLevel = step < 14 ? ((int[])vars.route)[step] : 23;
        int expectedHeader = step < 14 ? ((int[])vars.headers)[step] : 25;
        bool gameplay = current.mode == 3 && current.level == expectedLevel && current.header == (uint)expectedHeader;
        bool persistentContext = current.mode == 4 ||
            ((current.mode == 3 || current.mode == 5 || current.mode == 6) && current.level > 0 && current.level <= 24);
        uint root = (uint)current.gameRoot;
        if (u32(0x800ed6d0) == 1U && persistentContext)
        {
            current.gameCapacity = allocation(root, 0x6f0);
            current.persistentValid = current.gameCapacity != 0;
            if (current.persistentValid && gameplay)
            {
                current.deathSubstate = i16(root + 0x6a0);
                current.playerRoot = u32(root + 0x530);
                uint player = (uint)current.playerRoot;
                string identity = actor(player, 0x800d50b0, 0);
                if (identity != null && (u8(player + 0x34) & 0x20) != 0)
                    current.playerIdentity = identity;
                current.liveOrigin = current.playerIdentity != null;
            }
        }
        if (current.mode == 2 && current.header == 24U)
        {
            uint title = u32(0x800edc1c), transition = u32(0x800edb74);
            int capacity = allocation(title, 0x35c);
            if (capacity != 0)
            {
                current.titleIdentity = title + ":" + capacity;
                current.titleValid = i32(title) == 1 && i32(title + 0x190) == 0 &&
                    u32(title + 0x180) == 0x800142a8U && u32(title + 0x184) == 0x80014630U;
                if (current.titleValid && transition != 0)
                {
                    if (allocation(transition, 0x20) == 0) current.titleValid = false;
                    else current.newGamePacket = u32(transition) == 9 && u32(transition + 4) == 1 &&
                        u32(transition + 8) == 1 && u32(transition + 0x14) == 0;
                }
            }
        }
        if (current.liveOrigin && current.level == 23)
        {
            const uint descriptor = 0x800da674U + 23U * 0x64U;
            current.controllerRoot = u32(0x800ee978);
            if (u32(0x800ee92c) == descriptor && u32(descriptor + 0x40) == 0x800119b4U)
            {
                int size = u16(descriptor + 0x3e);
                if (size > 0) current.controllerCapacity = allocation((uint)current.controllerRoot, Math.Max(size, 0x14));
            }
            current.finalContext = current.controllerCapacity != 0;
            if (current.finalContext)
            {
                uint controller = (uint)current.controllerRoot;
                current.finalPhase = u32(controller);
                current.armyOutcome = i32(controller + 4);
                uint boss = u32(0x80021508);
                if (current.finalPhase == 6U || current.finalPhase == 8U)
                {
                    bool kardok = current.finalPhase == 6U;
                    uint definition = kardok ? 0x8001cdd4U : 0x8001d05cU;
                    uint constructor = kardok ? 0x80011f24U : 0x80018784U;
                    string identity = actor(boss, definition, constructor);
                    if (identity != null && u32(u32(boss + 0xc)) == (kardok ? 0xb3c4U : 0xb45dU))
                    {
                        current.bossIdentity = identity;
                        current.bossHP = i16(boss + 0x5a);
                        current.bossAction = u8(boss + 0x5c);
                        if (actor(boss, definition, constructor) != identity) throw new IOException("Boss changed during read");
                    }
                }
            }
        }
        if (i32(0x800eee64) != current.mode || u32(0x80010000) != current.header ||
            (current.persistentValid && (i32(0x800eee2c) != current.level || u32(0x800edb3c) != current.gameRoot ||
                u32(0x800ed6d0) != 1U || allocation(root, 0x6f0) != current.gameCapacity)) ||
            (current.liveOrigin && (u32(root + 0x530) != current.playerRoot ||
                actor((uint)current.playerRoot, 0x800d50b0, 0) != current.playerIdentity ||
                (u8((uint)current.playerRoot + 0x34) & 0x20) == 0)) ||
            (current.finalContext && (u32(0x800ee978) != current.controllerRoot ||
                allocation((uint)current.controllerRoot, 0x14) != current.controllerCapacity)))
            throw new IOException("Game context changed during read");
        game.Refresh();
        if (game.HasExited || game.StartTime.ToUniversalTime().Ticks != (long)vars.producerStarted)
            throw new IOException("Emulator changed during read");
        vars.diagnose("Any% USA; direct read-only fields. Runtime/gameplay timing unverified.");
        if (!(bool)vars.baseline)
        {
            vars.baseline = true;
            return false;
        }
        if (current.frame < old.frame || current.vblank < old.vblank)
        {
            vars.clearObservation();
            vars.baseline = true;
            return false;
        }

        bool running = timer.CurrentPhase == TimerPhase.Running || timer.CurrentPhase == TimerPhase.Paused;
        if (!running)
        {
            vars.armedBoss = null;
            vars.startEvent = current.titleValid && old.titleValid && current.titleIdentity == old.titleIdentity &&
                current.newGamePacket && !old.newGamePacket;
            return true;
        }
        bool sameGame = current.persistentValid && old.persistentValid &&
            current.gameRoot == old.gameRoot && current.gameCapacity == old.gameCapacity;
        bool playerReplaced = old.liveOrigin && gameplay && current.playerRoot != 0U &&
            current.playerIdentity != old.playerIdentity;
        if (!sameGame || playerReplaced || current.result == 3 || current.result == 4 || current.result == 6 ||
            (current.liveOrigin && current.deathSubstate != 0))
        {
            vars.armedBoss = null;
            return true;
        }

        bool advance = false;
        if (step < 14 && current.result == 5 && old.result != 5)
        {
            // Native successful exit, not merely a changed level/header. No HoH delay.
            int origin = -1;
            if (old.liveOrigin && old.deathSubstate == 0) origin = (int)old.level;
            else if (current.liveOrigin && current.deathSubstate == 0 && old.mode == 3 && old.level == current.level)
                origin = (int)current.level;
            advance = origin == expectedLevel;
        }
        bool sameFinal = current.finalContext && old.finalContext &&
            current.controllerRoot == old.controllerRoot && current.controllerCapacity == old.controllerCapacity;
        if (!sameFinal) vars.armedBoss = null;
        if (step == 14 && sameFinal)
            advance = old.finalPhase == 2U && old.armyOutcome != 1 && current.armyOutcome == 1 &&
                (current.finalPhase == 2U || current.finalPhase == 3U);
        if (step == 15 || step == 16)
        {
            uint phase = step == 15 ? 6U : 8U;
            if (!sameFinal || current.finalPhase != phase || current.bossIdentity == null)
                vars.armedBoss = null;
            else
            {
                bool sameBoss = current.finalPhase == old.finalPhase && current.bossIdentity == old.bossIdentity;
                if (!sameBoss || vars.armedBoss != current.bossIdentity) vars.armedBoss = null;
                if (sameBoss && old.bossHP > 0) vars.armedBoss = old.bossIdentity;
                if (current.bossHP > 0) vars.armedBoss = current.bossIdentity;
                advance = vars.armedBoss == current.bossIdentity && current.bossHP <= 0 &&
                    current.bossAction == (step == 15 ? 11 : 25);
            }
        }
        if (advance)
        {
            // Consume physical events even when their automatic action is disabled.
            vars.step = step + 1;
            vars.armedBoss = null;
            vars.splitEvent = step == 16 ? settings["autoend"] : settings["autosplit"];
        }
        return true;
    }
    catch (Exception error)
    {
        vars.clearObservation();
        vars.baseRAMAddress = 0L;
        vars.ramPointerAddress = IntPtr.Zero;
        if ((bool)vars.recomp) vars.scanAfter = DateTime.UtcNow.AddSeconds(1);
        vars.diagnose(error is IOException ? error.Message + "; automatic actions disarmed."
            : "RAM read unavailable (" + error.GetType().Name + "); automatic actions disarmed.");
        return false;
    }
    finally
    {
        vars.closeRAM();
    }
}

start
{
    return settings["autostart"] && (bool)vars.startEvent;
}
split
{
    return (bool)vars.splitEvent;
}
onStart
{
    vars.step = 0;
    vars.clearObservation();
}
onReset
{
    vars.step = 0;
    vars.clearObservation();
    if ((bool)vars.recomp) vars.baseRAMAddress = 0L;
}
exit
{
    vars.clearObservation();
    vars.closeRAM();
    vars.baseRAMAddress = 0L;
    vars.ramPointerAddress = IntPtr.Zero;
}
