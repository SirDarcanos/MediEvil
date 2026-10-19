// Load the user's TL overlay into THE DISPOSABLE PROJECT COPY for static analysis.
// Never run against the original project. This does not execute game code.
import ghidra.app.script.GhidraScript;
import java.nio.file.Files;
import java.nio.file.Path;

public class LoadTitleAudit extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args=getScriptArgs();
        if (args.length!=1) throw new IllegalArgumentException("Expected TL.BIN path");
        byte[] data=Files.readAllBytes(Path.of(args[0]));
        if (data.length<0x2100 || data.length>0x11ca4 || data[0]!=24 || data[1]!=0 || data[2]!=0 || data[3]!=0) {
            throw new IllegalArgumentException("Unexpected title-overlay header or size");
        }
        var memory=currentProgram.getMemory();
        var block=memory.getBlock(toAddr(0x80010000L));
        if (!block.isInitialized()) block=memory.convertToInitialized(block,(byte)0);
        block.setExecute(true);
        memory.setBytes(toAddr(0x80010000L),data);
        for(long entry:new long[]{0x80011750L,0x8001203cL}) {
            disassemble(toAddr(entry));
            if(getFunctionAt(toAddr(entry))==null)createFunction(toAddr(entry),null);
        }
        println("Loaded TL bytes in disposable analysis program; header=24");
    }
}
