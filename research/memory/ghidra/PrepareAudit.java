// Initialize analysis context IN THE DISPOSABLE COPY ONLY.
// GP is independently established by the executable entry's lui/addiu pair.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import java.math.BigInteger;

public class PrepareAudit extends GhidraScript {
    @Override
    public void run() throws Exception {
        Register gp = currentProgram.getRegister("gp");
        if (gp == null) throw new IllegalStateException("No MIPS gp register");
        currentProgram.getProgramContext().setValue(gp, toAddr(0x80010000L), toAddr(0x801fffffL), new BigInteger("800ed5d4", 16));
        var entry = toAddr(0x80099a54L);
        disassemble(entry);
        if (getFunctionAt(entry) == null) createFunction(entry, null);
        // Additional leaf/callback entries located in the same-hash community split
        // and the executable's HUD callback table. Names are not semantic evidence.
        long[] callbacks = {0x8006ecd0L,0x8006ecf4L,0x8006ed4cL,0x8006ed68L,0x8006ed78L,0x8006edccL,
            0x8006af00L,0x80075e30L,0x80075e7cL,0x80075ec8L,0x80075f10L,0x80075fbcL,0x80076098L,
            0x800762b0L,0x8007643cL,0x80077060L,0x80076480L,0x800786a0L,0x80076718L,
            0x800936c0L,0x80089904L,0x80093b70L,0x800930f8L,
            // Exact request-constructor call from the checked title confirm branch.
            0x8004e7b0L,0x8004e9f0L,0x8004ec8cL};
        for (long callback : callbacks) {
            var address = toAddr(callback);
            if (getFunctionContaining(address) == null) {
                disassemble(address);
                createFunction(address, null);
            }
        }
        // Bounded RNG-caller investigation: checked stack prologue immediately
        // follows the preceding procedure's jr ra / stack-restore delay slot.
        var effectEntry = toAddr(0x800283d0L);
        if (currentProgram.getMemory().getInt(effectEntry) != 0x27bdffc0 ||
            currentProgram.getMemory().getInt(toAddr(0x800283c8L)) != 0x03e00008 ||
            currentProgram.getMemory().getInt(toAddr(0x800283ccL)) != 0x27bd0030)
            throw new IllegalStateException("Unexpected checked RNG-caller boundary");
        if (getFunctionContaining(effectEntry) == null) {
            disassemble(effectEntry);
            createFunction(effectEntry, null);
        }
        // Exact direct-call target in the checked ZL skeleton collision callback.
        var hitEntry = toAddr(0x80047210L);
        if (getFunctionContaining(hitEntry) == null) {
            disassemble(hitEntry);
            createFunction(hitEntry, null);
        }
        println("Prepared entry, callback leads, checked RNG/hit callers and GP 0x800ed5d4; original project is not open");
    }
}
