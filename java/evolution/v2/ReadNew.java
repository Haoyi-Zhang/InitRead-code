import evolution.EvolvingNode;
import java.io.*;
public final class ReadNew {
    public static void main(String[] args) throws Exception {
        if (args.length != 1) throw new IllegalArgumentException("input path required");
        EvolvingNode node;
        try (ObjectInputStream in = new ObjectInputStream(new FileInputStream(args[0]))) {
            node = (EvolvingNode) in.readObject();
        }
        System.out.println("{\"case\":\"missing-field\",\"success\":true,"
            + "\"defaulted_next\":" + node.defaultedNext + ","
            + "\"value\":" + node.value + ",\"next_is_null\":" + (node.next == null) + "}");
    }
}
