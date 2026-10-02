import evolution.EvolvingNode;
import java.io.*;
public final class WriteOld {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("output path required");
        try (ObjectOutputStream out = new ObjectOutputStream(new FileOutputStream(args[0]))) {
            out.writeObject(new EvolvingNode(7));
        }
    }
}
