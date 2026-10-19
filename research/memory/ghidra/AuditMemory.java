// Read-only export for an ISOLATED COPY of the user's Ghidra project.
// Run with analyzeHeadless -readOnly -noanalysis -postScript AuditMemory.java EXE OUTPUT.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import java.io.PrintWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.LinkedHashSet;
import java.util.Set;

public class AuditMemory extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 2) throw new IllegalArgumentException("Expected original EXE path and output directory");
        Path output = Path.of(args[1]);
        Files.createDirectories(output);
        String name = currentProgram.getName().replaceAll("[^A-Za-z0-9_.-]", "_");
        try (PrintWriter out = new PrintWriter(Files.newBufferedWriter(output.resolve(name + "-audit.txt")))) {
            out.println("PROGRAM " + currentProgram.getName());
            out.println("LANGUAGE " + currentProgram.getLanguageID());
            out.println("EXECUTABLE_MD5 " + currentProgram.getExecutableMD5());
            for (MemoryBlock block : currentProgram.getMemory().getBlocks()) out.println("BLOCK " + block.getName() + " " + block.getStart() + " " + block.getSize());
            byte[] exe = Files.readAllBytes(Path.of(args[0]));
            ByteBuffer header = ByteBuffer.wrap(exe).order(ByteOrder.LITTLE_ENDIAN);
            long load = Integer.toUnsignedLong(header.getInt(0x18));
            int size = header.getInt(0x1c);
            try {
                byte[] actual = new byte[size];
                int count = currentProgram.getMemory().getBytes(toAddr(load), actual);
                int differences = 0;
                for (int i = 0; i < count; i++) if (actual[i] != exe[i + 0x800]) differences++;
                out.println("EXE_PAYLOAD_COMPARISON bytes=" + count + " expected=" + size + " differing=" + differences);
            } catch (Exception e) { out.println("EXE_PAYLOAD_COMPARISON_UNAVAILABLE " + e); }
            SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
            while (symbols.hasNext()) {
                Symbol symbol = symbols.next();
                String lower = symbol.getName().toLowerCase();
                if (lower.matches(".*(health|life|bottle|chalice|gold|inventory|gamestate|game_state|player|camera|level|newgame|new_game).*")) out.println("SYMBOL " + symbol.getAddress() + " " + symbol.getName(true));
            }
            long[] targets = {0x800edb3cL,0x800eee2cL,0x800eee30L,0x800eee60L,0x800eee64L,0x800eee6cL,0x800eee70L,0x800f1648L,0x800f170cL,0x800f1714L,0x800f8814L,0x80019134L,0x800f6e83L};
            long[] seeds = {0x8006993cL,0x800699b0L,0x80069a10L,0x80069b18L,0x80069bc0L,0x80069c30L,0x80045c74L,0x80045ca8L,0x8006a28cL,0x80093cc4L,0x8004c50cL,0x8006ecd0L,0x8006ecf4L,0x8006ed4cL,0x800761a8L,0x8004d42cL,0x80059e58L,0x8002364cL,0x8009374cL,0x80089970L,0x8006af70L,0x80069958L,0x800485ecL,0x8006ecd0L,0x8006ecf4L,0x8006ed4cL,0x8006ed68L,0x8006ed78L,0x8006edccL,0x8006af00L,0x80075e30L,0x80075e7cL,0x80075ec8L,0x80075f10L,0x80075fbcL,0x80076098L,0x800762b0L,0x8007643cL,0x80077060L,0x80076480L,0x800786a0L,0x80076718L,0x800936c0L,0x80089904L,0x80093b70L,0x800930f8L,0x80077398L,0x8007729cL,0x80065660L,0x800a8fecL,0x80011750L,0x8001203cL};
            Set<Function> functions = new LinkedHashSet<>();
            for (long seed : seeds) {
                Function function = getFunctionContaining(toAddr(seed));
                out.println("SEED " + Long.toHexString(seed) + " FUNCTION " + function);
                if (function != null) functions.add(function);
            }
            for (long target : targets) {
                Address address = toAddr(target);
                out.println("TARGET " + address + " SYMBOL " + getSymbolAt(address));
                ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(address);
                while (refs.hasNext()) {
                    Reference ref = refs.next();
                    Function function = getFunctionContaining(ref.getFromAddress());
                    out.println("XREF " + ref.getFromAddress() + " " + ref.getReferenceType() + " FUNCTION " + function);
                    if (function != null) functions.add(function);
                }
            }
            DecompInterface decompiler = new DecompInterface();
            try {
                if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException(decompiler.getLastMessage());
                for (Function function : functions) {
                    monitor.checkCancelled();
                    out.println("\nFUNCTION " + function.getEntryPoint() + " " + function.getName(true));
                    DecompileResults results = decompiler.decompileFunction(function, 45, monitor);
                    if (results.decompileCompleted()) out.println(results.getDecompiledFunction().getC());
                    else out.println("DECOMPILE_FAILED " + results.getErrorMessage());
                    InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
                    while (instructions.hasNext()) {
                        var instruction = instructions.next();
                        out.println(instruction.getAddress() + " " + instruction);
                    }
                    out.flush();
                }
            } finally { decompiler.dispose(); }
        }
        println("READ_ONLY_MEMORY_AUDIT " + output);
    }
}
