import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Portable correctness-only comparison on retained owned integer packets.
 * No benchmark branch, third-party object input, target, network, or agent.
 */
public final class CapacityObservationHarness {
    private static String quote(String text) {
        return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"")
            .replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + "\"";
    }
    private static String strings(List<String> items) {
        StringJoiner out = new StringJoiner(",", "[", "]");
        for (String item : items) out.add(quote(item));
        return out.toString();
    }
    private static byte[] serialize(int[] words) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(words); }
        return bytes.toByteArray();
    }
    private static int[] words(String text) {
        String[] cells = text.split(",", -1);
        if (cells.length > CertifiedReceiver.MAX_WORDS) throw new IllegalArgumentException("owned packet cap");
        int[] words = new int[cells.length];
        for (int i = 0; i < words.length; i++) words[i] = Integer.parseInt(cells[i]);
        return words;
    }
    private static int[] roots(CertifiedReceiver.Graph graph) {
        CertifiedReceiver.Node[] nodes = graph.roots();
        int[] ids = new int[nodes.length];
        for (int i = 0; i < nodes.length; i++) ids[i] = nodes[i].id();
        return ids;
    }
    private static int[] roots(GenericReceiver.Graph graph) {
        GenericReceiver.Node[] nodes = graph.roots();
        int[] ids = new int[nodes.length];
        for (int i = 0; i < nodes.length; i++) ids[i] = nodes[i].id();
        return ids;
    }
    private static boolean frozen(CertifiedReceiver.Graph graph, byte[] input) {
        if (graph == null) return true;
        int[][] before = graph.snapshot();
        CertifiedReceiver.Node[] copy = graph.roots(), original = graph.roots();
        Arrays.fill(copy, null); Arrays.fill(input, (byte) 0);
        int[][] changed = graph.snapshot(); changed[0][1] ^= 1;
        if (!Arrays.deepEquals(before, graph.snapshot()) || !Arrays.equals(original, graph.roots())) return false;
        Map<Integer, CertifiedReceiver.Node> seen = new HashMap<>();
        ArrayDeque<CertifiedReceiver.Node> queue = new ArrayDeque<>();
        Collections.addAll(queue, original);
        int budget = 0;
        while (!queue.isEmpty() && budget++ < 1024) {
            CertifiedReceiver.Node node = queue.removeFirst(), old = seen.putIfAbsent(node.id(), node);
            if (old != null) { if (old != node) return false; continue; }
            if (node.value() != before[node.id()][1]) return false;
            CertifiedReceiver.Node next = node.next();
            if ((next == null ? -1 : next.id()) != before[node.id()][2]) return false;
            if (next != null) queue.add(next);
        }
        return queue.isEmpty();
    }
    private static boolean frozen(GenericReceiver.Graph graph, byte[] input) {
        if (graph == null) return true;
        int[][] before = graph.snapshot();
        GenericReceiver.Node[] copy = graph.roots(), original = graph.roots();
        Arrays.fill(copy, null); Arrays.fill(input, (byte) 0);
        int[][] changed = graph.snapshot(); changed[0][1] ^= 1;
        if (!Arrays.deepEquals(before, graph.snapshot()) || !Arrays.equals(original, graph.roots())) return false;
        Map<Integer, GenericReceiver.Node> seen = new HashMap<>();
        ArrayDeque<GenericReceiver.Node> queue = new ArrayDeque<>();
        Collections.addAll(queue, original);
        int budget = 0;
        while (!queue.isEmpty() && budget++ < 1024) {
            GenericReceiver.Node node = queue.removeFirst(), old = seen.putIfAbsent(node.id(), node);
            if (old != null) { if (old != node) return false; continue; }
            if (node.value() != before[node.id()][1]) return false;
            GenericReceiver.Node next = node.next();
            if ((next == null ? -1 : next.id()) != before[node.id()][2]) return false;
            if (next != null) queue.add(next);
        }
        return queue.isEmpty();
    }
    private static void emit(String id, int mode, CertifiedReceiver.Result result, byte[] input) {
        CertifiedReceiver.Graph graph = result.graph;
        String heap = graph == null ? "null" : Arrays.deepToString(graph.snapshot());
        String rootIds = graph == null ? "null" : Arrays.toString(roots(graph));
        boolean ok = frozen(graph, input);
        if (!ok) throw new AssertionError("owned alias/freeze check");
        System.out.println("{\"id\":" + quote(id) + ",\"mode\":" + mode + ",\"status\":" + quote(result.status)
            + ",\"reason\":" + quote(result.reason) + ",\"steps\":" + result.checkedSteps
            + ",\"reads\":" + result.inspectedReads + ",\"trace\":" + strings(result.trace)
            + ",\"heap\":" + heap + ",\"roots\":" + rootIds + ",\"frozen_alias_ok\":" + ok + "}");
    }
    private static void emit(String id, int mode, GenericReceiver.Result result, byte[] input) {
        GenericReceiver.Graph graph = result.graph;
        String heap = graph == null ? "null" : Arrays.deepToString(graph.snapshot());
        String rootIds = graph == null ? "null" : Arrays.toString(roots(graph));
        boolean ok = frozen(graph, input);
        if (!ok) throw new AssertionError("owned alias/freeze check");
        System.out.println("{\"id\":" + quote(id) + ",\"mode\":" + mode + ",\"status\":" + quote(result.status)
            + ",\"reason\":" + quote(result.reason) + ",\"steps\":" + result.checkedSteps
            + ",\"reads\":" + result.inspectedReads + ",\"trace\":" + strings(result.trace)
            + ",\"heap\":" + heap + ",\"roots\":" + rootIds + ",\"frozen_alias_ok\":" + ok + "}");
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || args[0].startsWith("--")) throw new IllegalArgumentException("owned integer TSV only");
        int cases = 0;
        try (BufferedReader input = Files.newBufferedReader(Path.of(args[0]), StandardCharsets.UTF_8)) {
            String line;
            while ((line = input.readLine()) != null) {
                if (++cases > 6000) throw new IllegalArgumentException("owned case count cap");
                String[] cells = line.split("\t", -1);
                if (cells.length != 3 || !cells[0].matches("[a-zA-Z0-9_-]+")) throw new IllegalArgumentException("case schema");
                byte[] frame = serialize(words(cells[2]));
                byte[] owned = frame.clone(); emit(cells[0], 0, CertifiedReceiver.receive(owned), owned);
                owned = frame.clone(); emit(cells[0], 1, GenericReceiver.receive(owned), owned);
                owned = frame.clone(); emit(cells[0], 2, CertifiedReceiver.eagerForTest(owned, true), owned);
                owned = frame.clone(); emit(cells[0], 3, GenericReceiver.eagerForTest(owned, true), owned);
                owned = frame.clone(); emit(cells[0], 4, CertifiedReceiver.eagerForTest(owned, false), owned);
                owned = frame.clone(); emit(cells[0], 5, GenericReceiver.eagerForTest(owned, false), owned);
            }
        }
    }
}
