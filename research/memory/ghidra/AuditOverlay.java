// Read-only report of analyzed overlay functions. Load only into a disposable copy.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.FunctionIterator;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.PrintWriter;

public class AuditOverlay extends GhidraScript {
    @Override public void run() throws Exception {
        Path output=Path.of(getScriptArgs()[0]);
        Files.createDirectories(output);
        DecompInterface decompiler=new DecompInterface();
        try(PrintWriter out=new PrintWriter(Files.newBufferedWriter(output.resolve("overlay-audit.txt")))) {
            if(!decompiler.openProgram(currentProgram))throw new IllegalStateException(decompiler.getLastMessage());
            FunctionIterator functions=currentProgram.getFunctionManager().getFunctions(true);
            int count=0;
            while(functions.hasNext()) {
                var function=functions.next();
                long entry=function.getEntryPoint().getOffset();
                if(entry<0x80010000L || entry>=0x80021ca4L)continue;
                monitor.checkCancelled();
                out.println("\nFUNCTION "+function.getEntryPoint()+" "+function.getName());
                var results=decompiler.decompileFunction(function,20,monitor);
                if(results.decompileCompleted())out.println(results.getDecompiledFunction().getC());
                else out.println("DECOMPILE_FAILED "+results.getErrorMessage());
                var instructions=currentProgram.getListing().getInstructions(function.getBody(),true);
                while(instructions.hasNext()){var i=instructions.next();out.println(i.getAddress()+" "+i);}
                out.flush();count++;
            }
            println("OVERLAY_FUNCTIONS "+count+" OUTPUT "+output);
        } finally {decompiler.dispose();}
    }
}
