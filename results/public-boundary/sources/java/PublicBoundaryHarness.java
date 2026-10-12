import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Owned integer fixtures only. Observe public navigation, never snapshot(). */
public final class PublicBoundaryHarness {
    private static byte[] serialize(int[] words) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) { out.writeObject(words); }
        return bytes.toByteArray();
    }
    private static int[] parse(String text) {
        String[] cells = text.split(",", -1);
        if (cells.length > CertifiedReceiver.MAX_WORDS) throw new IllegalArgumentException("word cap");
        int[] words = new int[cells.length];
        for (int i = 0; i < words.length; i++) words[i] = Integer.parseInt(cells[i]);
        return words;
    }
    private static int[] dataOnly(int[] words) {
        int n = words[2], m = words[3];
        if (n < 1 || n > 128 || m < 0 || m > 128 || words.length < 5 + 2*n + m)
            throw new IllegalArgumentException("complete bounded data required");
        // Retain the existing header/data layout and one ignored zero step word.
        // This is an eager test frame, not an accepting certificate packet.
        int[] data = Arrays.copyOf(words, 5 + 2*n + m);
        data[data.length - 1] = 0;
        return data;
    }
    private static CertifiedReceiver.Result receive(byte[] frame, int mode) {
        return mode == 0 ? CertifiedReceiver.receive(frame) : CertifiedReceiver.eagerForTest(frame, true);
    }
    private static final String[] MODES = {"certificate", "eager_same_frame", "eager_data_only"};

    private static void observe(String id, int mode, int[] words) throws IOException {
        int[] sent = mode == 2 ? dataOnly(words) : words;
        byte[] frame = serialize(sent);
        CertifiedReceiver.Result result = receive(frame, mode);
        int[] roots = null;
        List<int[]> nodes = new ArrayList<>();
        boolean aliases = true, frozen = true;
        if (result.graph != null) {
            CertifiedReceiver.Node[] original = result.graph.roots();
            roots = Arrays.stream(original).mapToInt(CertifiedReceiver.Node::id).toArray();
            CertifiedReceiver.Node[] copy = result.graph.roots();
            Arrays.fill(copy, null); Arrays.fill(frame, (byte)0);
            frozen = Arrays.equals(original, result.graph.roots());
            Map<Integer, CertifiedReceiver.Node> seen = new TreeMap<>();
            ArrayDeque<CertifiedReceiver.Node> pending = new ArrayDeque<>();
            Collections.addAll(pending, original);
            int visits = 0;
            while (!pending.isEmpty()) {
                if (++visits > 512) throw new AssertionError("public traversal bound");
                CertifiedReceiver.Node node = pending.removeFirst();
                CertifiedReceiver.Node prior = seen.putIfAbsent(node.id(), node);
                if (prior != null) { aliases &= prior == node; continue; }
                if (node.next() != null) pending.add(node.next());
            }
            for (CertifiedReceiver.Node node : seen.values()) {
                CertifiedReceiver.Node next = node.next();
                nodes.add(new int[]{node.id(), node.value(), next == null ? -1 : next.id()});
            }
        }
        System.out.println("{\"id\":\"" + id + "\",\"mode\":\"" + MODES[mode]
            + "\",\"status\":\"" + result.status + "\",\"has_graph\":" + (result.graph != null)
            + ",\"roots\":" + (roots == null ? "null" : Arrays.toString(roots))
            + ",\"nodes\":" + Arrays.deepToString(nodes.toArray(new int[0][]))
            + ",\"canonical_aliases\":" + aliases + ",\"frozen\":" + frozen
            + ",\"words\":" + sent.length + ",\"bytes\":" + frame.length + "}");
    }

    private static volatile long blackhole;
    private static void consume(CertifiedReceiver.Result r) {
        if (r.graph == null) throw new AssertionError("safe cost fixture required: " + r.status);
        blackhole += r.graph.size() + r.checkedSteps + r.inspectedReads;
    }
    private static void benchmark(String id, int[] words, int fork) throws IOException {
        for (int round = 0; round < 3; round++) {
            int mode = (round + fork) % 3;
            int[] sent = mode == 2 ? dataOnly(words) : words;
            byte[] frame = serialize(sent);
            if (frame.length != 27 + 4*sent.length) throw new AssertionError("canonical size");
            // Warm every measured operation. No result-based exclusion/tuning.
            for (int i = 0; i < 300; i++) consume(receive(serialize(sent), mode));
            int repetitions = 200;
            long start = System.nanoTime();
            for (int i = 0; i < repetitions; i++) blackhole += serialize(sent).length;
            long framing = System.nanoTime() - start;
            start = System.nanoTime();
            for (int i = 0; i < repetitions; i++) consume(receive(frame, mode));
            long receiving = System.nanoTime() - start;
            start = System.nanoTime();
            for (int i = 0; i < repetitions; i++) consume(receive(serialize(sent), mode));
            long pipeline = System.nanoTime() - start;
            System.out.println("{\"id\":\"" + id + "\",\"mode\":\"" + MODES[mode]
                + "\",\"fork\":" + fork + ",\"warmups\":300,\"iterations\":" + repetitions
                + ",\"sender_framing_ns\":" + framing + ",\"receiving_ns\":" + receiving
                + ",\"java_pipeline_ns\":" + pipeline + ",\"words\":" + sent.length
                + ",\"bytes\":" + frame.length + "}");
        }
    }
    public static void main(String[] args) throws Exception {
        if (args.length != 1 && !(args.length == 4 && args[0].equals("--cost")))
            throw new IllegalArgumentException("owned TSV | --cost owned TSV id fork");
        boolean cost = args.length == 4;
        Path table = Path.of(args[cost ? 1 : 0]);
        int count = 0;
        for (String line : Files.readAllLines(table, StandardCharsets.UTF_8)) {
            if (++count > 6000) throw new IllegalArgumentException("owned case cap");
            String[] cells = line.split("\t", -1);
            if (cells.length != 3 || !cells[0].matches("[a-zA-Z0-9_-]+"))
                throw new IllegalArgumentException("owned case schema");
            if (cost && !cells[0].equals(args[2])) continue;
            int[] words = parse(cells[2]);
            if (cost) { benchmark(cells[0], words, Integer.parseInt(args[3])); return; }
            for (int mode = 0; mode < 3; mode++) observe(cells[0], mode, words);
        }
        if (cost) throw new IllegalArgumentException("missing cost fixture");
    }
}
