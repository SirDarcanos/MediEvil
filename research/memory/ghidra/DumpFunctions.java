// Read-only selected native functions and their callers from a disposable project.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.program.model.listing.Function;
import java.nio.file.Files;
import java.nio.file.Path;
import java.io.PrintWriter;
import java.util.LinkedHashSet;

public class DumpFunctions extends GhidraScript {
    @Override public void run() throws Exception {
        String[] args=getScriptArgs();
        if(args.length!=2)throw new IllegalArgumentException("Expected output file and comma-separated entries");
        Path file=Path.of(args[0]);Files.createDirectories(file.getParent());
        LinkedHashSet<Function> functions=new LinkedHashSet<>();
        try(PrintWriter out=new PrintWriter(Files.newBufferedWriter(file))) {
            for(String value:args[1].split(",")) {
                boolean data=value.startsWith("@");
                boolean containing=value.startsWith("^");
                var address=toAddr(Long.parseUnsignedLong(data||containing?value.substring(1):value,16));
                if(!data) {
                    var f=containing?getFunctionContaining(address):getFunctionAt(address);
                    if(f==null)throw new IllegalArgumentException("No function at checked entry "+address);
                    functions.add(f);
                }
                var refs=currentProgram.getReferenceManager().getReferencesTo(address);
                while(refs.hasNext()) {
                    var r=refs.next();var caller=getFunctionContaining(r.getFromAddress());
                    out.println("XREF "+address+" FROM "+r.getFromAddress()+" TYPE "+r.getReferenceType()+" FUNCTION "+caller);
                    if(caller!=null)functions.add(caller);
                }
            }
            var decompiler=new DecompInterface();
            try {
                if(!decompiler.openProgram(currentProgram))throw new IllegalStateException(decompiler.getLastMessage());
                for(Function f:functions) {
                    monitor.checkCancelled();out.println("\nFUNCTION "+f.getEntryPoint()+" "+f.getName());
                    var d=decompiler.decompileFunction(f,30,monitor);
                    if(d.decompileCompleted())out.println(d.getDecompiledFunction().getC());
                    else out.println("DECOMPILE_FAILED "+d.getErrorMessage());
                    var instructions=currentProgram.getListing().getInstructions(f.getBody(),true);
                    while(instructions.hasNext()){var i=instructions.next();out.println(i.getAddress()+" "+i);}
                    out.flush();
                }
            } finally {decompiler.dispose();}
        }
    }
}
