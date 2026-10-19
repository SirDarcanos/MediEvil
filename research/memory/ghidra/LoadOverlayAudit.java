// Static overlay analysis in OUR disposable project only; never executes the game.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.FunctionIterator;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.math.BigInteger;
import java.util.ArrayList;

public class LoadOverlayAudit extends GhidraScript {
    @Override public void run() throws Exception {
        Path project = Path.of(state.getProject().getProjectLocator().getLocation()).toRealPath();
        Path allowed = Path.of("/tmp/medievil-ghidra-memory-audit").toRealPath();
        if (!project.startsWith(allowed)) throw new IllegalStateException("Refusing non-disposable project");
        String[] args = getScriptArgs();
        if (args.length != 3) throw new IllegalArgumentException("Expected overlay file, header ID, comma-separated code entries");
        byte[] data = Files.readAllBytes(Path.of(args[0]));
        int header = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).getInt();
        if (header != Integer.parseInt(args[1]) || data.length > 0x11ca4 || data.length < 8)
            throw new IllegalArgumentException("Unexpected overlay identity/size");
        Address start=toAddr(0x80010000L), end=toAddr(0x80021ca3L);
        ArrayList<Address> remove=new ArrayList<>();
        FunctionIterator functions=currentProgram.getFunctionManager().getFunctions(true);
        while(functions.hasNext()) {
            var f=functions.next();
            if(f.getEntryPoint().compareTo(start)>=0 && f.getEntryPoint().compareTo(end)<=0)remove.add(f.getEntryPoint());
        }
        for(Address entry:remove)currentProgram.getFunctionManager().removeFunction(entry);
        clearListing(start,end);
        var memory=currentProgram.getMemory();
        var block=memory.getBlock(start);
        if(!block.isInitialized())block=memory.convertToInitialized(block,(byte)0);
        block.setExecute(true);
        memory.setBytes(start,new byte[0x11ca4]);
        memory.setBytes(start,data);
        currentProgram.getProgramContext().setValue(currentProgram.getRegister("gp"),start,end,BigInteger.valueOf(0x800ed5d4L));
        for(String value:args[2].split(",")) {
            Address entry=toAddr(Long.parseUnsignedLong(value,16));
            if(entry.compareTo(start)<0 || entry.compareTo(start.add(data.length))>=0)throw new IllegalArgumentException("Entry outside overlay");
            disassemble(entry);
            if(getFunctionAt(entry)==null)createFunction(entry,null);
        }
        // Do not globally analyze main-program calls into other overlays' fixed
        // addresses: they otherwise manufacture invalid functions in this overlay.
        // Launch with -noanalysis and seed only checked constructor/vtable entries.
        println("DISPOSABLE_OVERLAY_LOADED header="+header+" bytes="+data.length);
    }
}
