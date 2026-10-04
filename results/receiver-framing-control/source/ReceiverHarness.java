import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;

/** Benign owned validation only. No arbitrary deserialization CLI is provided. */
public final class ReceiverHarness {
    private static int callbacks;
    private static final class CallbackMarker implements Serializable {
        private static final long serialVersionUID = 1;
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            callbacks++; in.defaultReadObject();
        }
        private Object readResolve() { callbacks++; return this; }
    }
    private static byte[] serialized(Object object) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(b)) { out.writeObject(object); }
        return b.toByteArray();
    }
    private static byte[] appended(int[] words) throws IOException {
        ByteArrayOutputStream b = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(b)) { out.writeObject(words); out.writeObject(null); }
        return b.toByteArray();
    }
    private static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n") + "\"";
    }
    private static String ints(int[] a) { return Arrays.toString(a); }
    private static String rows(int[][] a) { return Arrays.deepToString(a); }
    private static String strings(List<String> ss) {
        StringJoiner j = new StringJoiner(",", "[", "]"); for (String s : ss) j.add(quote(s)); return j.toString();
    }
    private static int[] roots(CertifiedReceiver.Graph graph) {
        CertifiedReceiver.Node[] nodes = graph.roots(); int[] r = new int[nodes.length];
        for (int i = 0; i < r.length; i++) r[i] = nodes[i].id(); return r;
    }
    private static boolean aliasAndFreeze(CertifiedReceiver.Graph graph, byte[] wire) {
        int[][] before = graph.snapshot();
        CertifiedReceiver.Node[] rootCopy = graph.roots();
        CertifiedReceiver.Node[] roots = graph.roots();
        Arrays.fill(rootCopy, null); Arrays.fill(wire, (byte)0);
        int[][] changed = graph.snapshot(); if (changed.length != 0) changed[0][1] ^= 1;
        if (!Arrays.deepEquals(before, graph.snapshot())) return false;
        if (!Arrays.equals(roots, graph.roots())) return false;
        Map<Integer, CertifiedReceiver.Node> seen = new HashMap<>();
        ArrayDeque<CertifiedReceiver.Node> q = new ArrayDeque<>(); Collections.addAll(q, roots);
        int budget = 0;
        while (!q.isEmpty() && budget++ < 1024) {
            CertifiedReceiver.Node node = q.removeFirst();
            CertifiedReceiver.Node old = seen.putIfAbsent(node.id(), node);
            if (old != null) { if (old != node) return false; continue; }
            if (node.value() != before[node.id()][1]) return false;
            CertifiedReceiver.Node next = node.next();
            if ((next == null ? -1 : next.id()) != before[node.id()][2]) return false;
            if (next != null) q.add(next);
        }
        return q.isEmpty();
    }
    private static void emit(String id, String kind, byte[] bytes, Path streams, int fault) throws IOException {
        // Preserve exact OOS bytes BEFORE input-mutation encapsulation test.
        Files.write(streams.resolve(id + ".ser"), bytes);
        callbacks = 0;
        CertifiedReceiver.Result r = CertifiedReceiver.receiveForTest(bytes, fault);
        int receiverCallbacks = callbacks;
        CertifiedReceiver.Result eager = CertifiedReceiver.eagerForTest(bytes, true);
        CertifiedReceiver.Result shape = CertifiedReceiver.eagerForTest(bytes, false);
        int[][] snapshot = r.graph == null ? null : r.graph.snapshot();
        int[] roots = r.graph == null ? null : roots(r.graph);
        boolean frozen = r.graph == null || aliasAndFreeze(r.graph, bytes);
        System.out.println("{\"id\":" + quote(id) + ",\"kind\":" + quote(kind) +
            ",\"status\":" + quote(r.status) + ",\"reason\":" + quote(r.reason) +
            ",\"eager\":" + quote(eager.status) + ",\"shape\":" + quote(shape.status) +
            ",\"has_graph\":" + (r.graph != null) + ",\"frozen_alias_ok\":" + frozen +
            ",\"callback_count\":" + receiverCallbacks + ",\"bytes\":" + Files.size(streams.resolve(id+".ser")) +
            ",\"steps\":" + r.checkedSteps + ",\"predicate_reads\":" + r.inspectedReads +
            ",\"heap\":" + (snapshot == null ? "null" : rows(snapshot)) +
            ",\"roots\":" + (roots == null ? "null" : ints(roots)) + ",\"trace\":" + strings(r.trace) + "}");
    }
    private static int[] words(String line) {
        String[] ss=line.split(",",-1); int[] w=new int[ss.length];
        for (int i=0;i<w.length;i++) w[i]=Integer.parseInt(ss[i]); return w;
    }
    private static CertifiedReceiver.Result mode(byte[] bytes, int mode) {
        return mode == 0 ? CertifiedReceiver.eagerForTest(bytes, false) : mode == 1
            ? CertifiedReceiver.eagerForTest(bytes, true) : CertifiedReceiver.receive(bytes);
    }
    private static volatile int blackhole;
    public static void main(String[] args) throws Exception {
        if (args.length < 2) throw new IllegalArgumentException("cases.tsv streams-dir | --benchmark cases.tsv fork");
        if (args[0].equals("--benchmark")) {
            int fork=Integer.parseInt(args[2]);
            for(String line:Files.readAllLines(Path.of(args[1]),StandardCharsets.UTF_8)) {
                String[] parts=line.split("\t",-1);
                if(args.length>3 && !parts[0].equals(args[3])) continue;
                byte[] b=serialized(words(parts[2]));
                for(int round=0;round<3;round++) {
                    int m=(round+fork)%3;
                    for(int i=0;i<500;i++) { CertifiedReceiver.Result r=mode(b,m); blackhole += r.checkedSteps; }
                    int iterations=200; long t=System.nanoTime();
                    for(int i=0;i<iterations;i++) {
                        CertifiedReceiver.Result r=mode(b,m);
                        if(r.graph==null) throw new AssertionError("benchmark must be safe");
                        blackhole += r.graph.size();
                    }
                    long elapsed=System.nanoTime()-t;
                    System.out.println("{\"id\":"+quote(parts[0])+",\"fork\":"+fork+",\"mode\":"+m+",\"iterations\":"+iterations+",\"ns_total\":"+elapsed+",\"bytes\":"+b.length+"}");
                }
            }
            return;
        }
        Path streams=Path.of(args[1]);Files.createDirectories(streams);
        int[] first=null;
        for(String line:Files.readAllLines(Path.of(args[0]),StandardCharsets.UTF_8)) {
            String[] p=line.split("\t",-1);
            if(!p[0].matches("[a-zA-Z0-9_-]+")) throw new IllegalArgumentException("case id");
            int[] w=words(p[2]);if(first==null && w[3]>0) first=w;
            emit(p[0],p[1],serialized(w),streams,-1);
        }
        if(first==null)throw new IllegalArgumentException("empty cases");
        emit("wire-callback-marker","wire-control",serialized(new CallbackMarker()),streams,-1);
        emit("wire-object-array","wire-control",serialized(new Object[]{0,Boolean.FALSE}),streams,-1);
        emit("wire-double-array","wire-control",serialized(new double[]{0.0}),streams,-1);
        emit("wire-string","wire-control",serialized("benign"),streams,-1);
        emit("wire-null","wire-control",serialized(null),streams,-1);
        emit("wire-trailing-value","wire-control",appended(first),streams,-1);
        byte[] full=serialized(first);
        emit("wire-truncated","wire-control",Arrays.copyOf(full,full.length-3),streams,-1);
        emit("wire-oversized-array","wire-control",serialized(new int[CertifiedReceiver.MAX_WORDS+1]),streams,-1);
        emit("wire-oversized-frame","wire-control",new byte[CertifiedReceiver.MAX_BYTES+1],streams,-1);
        emit("construction-failure","fault-control",serialized(first),streams,0);
    }
}
