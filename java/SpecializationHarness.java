import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Differential validation of owned int[] cases; not an arbitrary-object loader. */
public final class SpecializationHarness {
    private static byte[] serialize(int[] words) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        try (ObjectOutputStream o = new ObjectOutputStream(b)) { o.writeObject(words); }
        return b.toByteArray();
    }
    private static int[] words(String text) {
        String[] parts = text.split(",", -1); int[] w = new int[parts.length];
        for (int i = 0; i < w.length; i++) w[i] = Integer.parseInt(parts[i]);
        return w;
    }
    private static int[] roots(CertifiedReceiver.Graph g) {
        if (g == null) return null;
        return Arrays.stream(g.roots()).mapToInt(CertifiedReceiver.Node::id).toArray();
    }
    private static int[] roots(GenericReceiver.Graph g) {
        if (g == null) return null;
        return Arrays.stream(g.roots()).mapToInt(GenericReceiver.Node::id).toArray();
    }
    private static String quote(String x) {
        return "\"" + x.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\"";
    }
    private static volatile long blackhole;
    private static int invoke(byte[] b, int mode) {
        if (mode == 0) {
            GenericReceiver.Result r = GenericReceiver.receive(b);
            if (r.graph == null) throw new AssertionError(r.status);
            return r.graph.size() + r.checkedSteps + r.inspectedReads;
        }
        CertifiedReceiver.Result r = mode == 1 ? CertifiedReceiver.receive(b)
            : CertifiedReceiver.eagerForTest(b, true);
        if (r.graph == null) throw new AssertionError(r.status);
        return r.graph.size() + r.checkedSteps + r.inspectedReads;
    }
    public static void main(String[] args) throws Exception {
        if (args.length == 0) throw new IllegalArgumentException("owned cases TSV required");
        if (args[0].equals("--benchmark")) {
            if (args.length != 4) throw new IllegalArgumentException("--benchmark TSV case-id fork");
            int fork = Integer.parseInt(args[3]);
            String line = Files.readAllLines(Path.of(args[1]), StandardCharsets.UTF_8).stream()
                .filter(s -> s.startsWith(args[2] + "\t")).findFirst().orElseThrow();
            String[] p = line.split("\t", -1); byte[] b = serialize(words(p[2]));
            for (int round = 0; round < 3; round++) {
                int mode = (round + fork) % 3;
                for (int i = 0; i < 1000; i++) blackhole += invoke(b, mode);
                int iterations = 500; long start = System.nanoTime();
                for (int i = 0; i < iterations; i++) blackhole += invoke(b, mode);
                long elapsed = System.nanoTime() - start;
                System.out.println("{\"id\":" + quote(p[0]) + ",\"fork\":" + fork +
                    ",\"mode\":" + mode + ",\"warmups\":1000,\"iterations\":" + iterations +
                    ",\"ns_total\":" + elapsed + ",\"bytes\":" + b.length + "}");
            }
            return;
        }
        for (String line : Files.readAllLines(Path.of(args[0]), StandardCharsets.UTF_8)) {
            String[] p = line.split("\t", -1); byte[] b = serialize(words(p[2]));
            CertifiedReceiver.Result a = CertifiedReceiver.receive(b);
            GenericReceiver.Result r = GenericReceiver.receive(b);
            int[][] ah = a.graph == null ? null : a.graph.snapshot();
            int[][] rh = r.graph == null ? null : r.graph.snapshot();
            boolean equal = a.status.equals(r.status) && a.reason.equals(r.reason) &&
                a.checkedSteps == r.checkedSteps && a.inspectedReads == r.inspectedReads &&
                a.trace.equals(r.trace) && Arrays.deepEquals(ah, rh) && Arrays.equals(roots(a.graph), roots(r.graph));
            System.out.println("{\"id\":" + quote(p[0]) + ",\"kind\":" + quote(p[1]) +
                ",\"specialized\":" + quote(a.status) + ",\"generic\":" + quote(r.status) +
                ",\"all_observations_equal\":" + equal + ",\"graph\":" + (a.graph != null) +
                ",\"checked_steps\":" + a.checkedSteps + ",\"reads\":" + a.inspectedReads +
                ",\"words\":" + words(p[2]).length + ",\"bytes\":" + b.length + "}");
        }
    }
}
