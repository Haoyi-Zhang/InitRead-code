import java.io.*;
import java.util.*;

/**
 * Callback-free bounded receiver. This is a new data-only wire contract, not
 * a monitor or compatible replacement for arbitrary Serializable classes.
 *
 * No caller-controlled class, callback, comparator, collection, or listener is
 * invoked by the receiving path. All materialized graph storage is private;
 * Graph/Node are final, non-Serializable, and expose read-only navigation.
 */
public final class GenericReceiver {
    public static final int MAGIC = 0x52434331;
    public static final int MAX_WORDS = 24576;
    public static final int MAX_BYTES = 131072;
    private GenericReceiver() { }

    /** Only scalar diagnostics: no private Node, Graph, or input array escapes. */
    public static final class Result {
        public final String status;
        public final String reason;
        public final Graph graph;
        public final List<String> trace;
        public final int inspectedReads;
        public final int checkedSteps;
        private Result(String status, String reason, Graph graph,
                       List<String> trace, int reads, int steps) {
            this.status = status; this.reason = reason; this.graph = graph;
            this.trace = Collections.unmodifiableList(new ArrayList<>(trace));
            this.inspectedReads = reads; this.checkedSteps = steps;
        }
    }

    /** Public access is through retained roots and their successor edges only. */
    public static final class Graph {
        private final int[] values;
        private final int[] links;
        private final int[] rootIds;
        private final Node[] nodes;
        private Graph(Data d, List<String> trace, int faultAfter) throws Reject {
            values = d.values.clone(); links = d.links.clone(); rootIds = d.roots.clone();
            nodes = new Node[values.length];
            for (int i = 0; i < nodes.length; i++) {
                if (faultAfter == i) throw new Reject("INJECTED_FAILURE", "materialization");
                nodes[i] = new Node(this, i);
                trace.add("NODE_INITIALIZED:" + i);
            }
            trace.add("GRAPH_FROZEN");
        }
        public Node[] roots() {
            Node[] copy = new Node[rootIds.length];
            for (int i = 0; i < copy.length; i++) copy[i] = nodes[rootIds[i]];
            return copy;
        }
        public int size() { return nodes.length; }
        /** Scalar-only owned test observation; returned arrays are fresh copies. */
        int[][] snapshot() {
            int[][] copy = new int[nodes.length][3];
            for (int i = 0; i < copy.length; i++) copy[i] = new int[]{1, values[i], links[i]};
            return copy;
        }
    }

    public static final class Node {
        private final Graph owner;
        private final int identity;
        private Node(Graph owner, int identity) { this.owner = owner; this.identity = identity; }
        public int id() { return identity; }
        public int value() { return owner.values[identity]; }
        public Node next() {
            int t = owner.links[identity];
            return t == -1 ? null : owner.nodes[t];
        }
    }

    private static final class Reject extends Exception {
        final String status;
        Reject(String status, String reason) { super(reason); this.status = status; }
    }
    private static final class Cursor {
        private final int[] words;
        private int pos;
        Cursor(int[] words) { this.words = words; }
        int take() throws Reject {
            if (pos >= words.length) throw new Reject("INVALID_CERT", "truncated-integer-frame");
            return words[pos++];
        }
        int count(int maximum) throws Reject {
            int n = take();
            if (n < 0 || n > maximum) throw new Reject("INVALID_CERT", "count-bound");
            return n;
        }
        void expect(int expected, String reason) throws Reject {
            if (take() != expected) throw new Reject("INVALID_CERT", reason);
        }
        void end() throws Reject {
            if (pos != words.length) throw new Reject("INVALID_CERT", "extra-certificate-words");
        }
    }
    private static final class Data {
        final int[] values, links, roots;
        Data(int[] values, int[] links, int[] roots) { this.values = values; this.links = links; this.roots = roots; }
    }
    private static Data decode(Cursor c) throws Reject {
        if (c.take() != MAGIC || c.take() != 1) throw new Reject("INVALID_DATA", "schema");
        int n = c.take(), m = c.take();
        if (n < 1 || n > 128 || m < 0 || m > 128) throw new Reject("INVALID_DATA", "dimensions");
        int[] v = new int[n], t = new int[n], r = new int[m];
        for (int i = 0; i < n; i++) {
            v[i] = c.take();
            if (v[i] != 0 && v[i] != 1) throw new Reject("INVALID_DATA", "value-domain");
        }
        for (int i = 0; i < n; i++) {
            t[i] = c.take();
            if (t[i] < -1 || t[i] >= n) throw new Reject("INVALID_DATA", "link-domain");
        }
        // Range checking precedes identity de-duplication. int[] forbids bool/float.
        for (int i = 0; i < m; i++) {
            r[i] = c.take();
            if (r[i] < 0 || r[i] >= n) throw new Reject("INVALID_DATA", "root-domain");
        }
        return new Data(v, t, r);
    }

    /** A hard descriptor check, not merely a user-replaceable filter factory. */
    private static final class IntStream extends ObjectInputStream {
        IntStream(InputStream in) throws IOException {
            super(in);
            setObjectInputFilter(info -> {
                if (info.depth() > 2 || info.references() > 8 || info.streamBytes() > MAX_BYTES ||
                    info.arrayLength() > MAX_WORDS) return ObjectInputFilter.Status.REJECTED;
                Class<?> k = info.serialClass();
                return k == null || k == int[].class
                    ? ObjectInputFilter.Status.UNDECIDED : ObjectInputFilter.Status.REJECTED;
            });
        }
        @Override protected Class<?> resolveClass(ObjectStreamClass d) throws IOException {
            if (!"[I".equals(d.getName())) throw new InvalidClassException("primitive-int-array-only");
            return int[].class;
        }
        @Override protected Class<?> resolveProxyClass(String[] interfaces) throws IOException {
            throw new InvalidClassException("proxies-unsupported");
        }
    }

    private static int[] deserialize(byte[] frame, List<String> trace) throws IOException, ClassNotFoundException, Reject {
        if (frame == null || frame.length == 0 || frame.length > MAX_BYTES)
            throw new Reject("INVALID_FRAME", "byte-bound");
        // The public byte array may be retained by the caller. Do not retain it.
        byte[] owned = frame.clone();
        trace.add("FRAME_COPIED:" + owned.length);
        try (IntStream in = new IntStream(new ByteArrayInputStream(owned))) {
            Object root = in.readObject();
            if (root == null || root.getClass() != int[].class)
                throw new Reject("INVALID_FRAME", "top-level-type");
            int[] words = (int[]) root;
            if (words.length < 5 || words.length > MAX_WORDS)
                throw new Reject("INVALID_FRAME", "word-bound");
            // EOFException is not a sufficient end-of-frame proof: it can be
            // thrown halfway through a second, truncated value. This deliberately
            // narrow wire contract accepts only the canonical OOS representation
            // of one int[]. Re-encoding invokes no application code.
            ByteArrayOutputStream canonical = new ByteArrayOutputStream();
            try (ObjectOutputStream out = new ObjectOutputStream(canonical)) {
                out.writeObject(words);
            }
            if (!Arrays.equals(owned, canonical.toByteArray()))
                throw new Reject("INVALID_FRAME", "noncanonical-or-trailing-frame");
            trace.add("PRIMITIVE_ARRAY_DECODED:" + words.length);
            return words;
        }
    }

    private static boolean[] closure(int[][] h, boolean[] roots) {
        boolean[] live = roots.clone();
        int[] work = new int[h.length]; int head = 0, tail = 0;
        for (int i = 0; i < live.length; i++) if (live[i]) work[tail++] = i;
        while (head < tail) {
            int t = h[work[head++]][2];
            if (t >= 0 && !live[t]) { live[t] = true; work[tail++] = t; }
        }
        return live;
    }
    private static int count(boolean[] x) { int n=0; for (boolean v : x) if (v) n++; return n; }
    private static int[][] transcript(int[][] h, int i) {
        if (h[i][0] == 0) return new int[][]{{i,0,0}};
        if (h[i][2] == -1) return new int[][]{{i,0,1},{i,2,-1}};
        return new int[][]{{i,0,1},{i,2,h[i][2]},{i,1,h[i][1]},{h[i][2],1,h[h[i][2]][1]}};
    }
    private static boolean predicate(int[][] h, int i) {
        return h[i][0] == 1 && (h[i][2] < 0 || h[i][1] <= h[h[i][2]][1]);
    }
    private static boolean contains(int[][] reads, int object, int field) {
        if (reads == null) return false;
        for (int[] r : reads) if (r[0] == object && r[1] == field) return true;
        return false;
    }
    private static final class State {
        int[][] heap;
        boolean[] roots;
        int[][][] cache;
        int reads, steps;
        State(int n) {
            heap = new int[n][3]; roots = new boolean[n]; cache = new int[n][][];
            for (int i = 0; i < n; i++) heap[i][2] = -1;
        }
        void step(int object, int field, int value, int root, Cursor c, List<String> log) throws Reject {
            int[][] h = new int[heap.length][];
            for (int i = 0; i < h.length; i++) h[i] = heap[i].clone();
            h[object][field] = value;
            boolean[] r = roots.clone(); if (root >= 0) r[root] = true;
            boolean[] live = closure(h, r), needed = new boolean[h.length];
            for (int i = 0; i < h.length; i++)
                needed[i] = live[i] && (cache[i] == null || contains(cache[i], object, field));
            c.expect(count(live), "closure-count");
            for (int i = 0; i < h.length; i++) if (live[i]) c.expect(i, "closure-identity");
            c.expect(count(needed), "obligation-count");
            int[][][] newCache = cache.clone();
            boolean allow = true;
            for (int i = 0; i < h.length; i++) if (needed[i]) {
                int[][] expected = transcript(h, i);
                boolean ok = predicate(h, i);
                c.expect(i, "obligation-identity"); c.expect(ok ? 1 : 0, "predicate-result");
                c.expect(expected.length, "read-count");
                for (int[] row : expected) for (int cell : row) c.expect(cell, "read-binding");
                reads += expected.length; allow &= ok; newCache[i] = expected;
            }
            c.expect(allow ? 1 : 0, "decision");
            steps++;
            log.add("SHADOW_CHECK:" + object + ":" + field + ":" + value + ":" + root + ":" + (allow ? "ALLOW" : "DENY_UNSAFE"));
            if (!allow) throw new Reject("DENY_UNSAFE", "reachable-invariant");
            heap = h; roots = r; cache = newCache;
        }
    }

    /** Exact certificate gate: all data and certificates are untrusted. */
    public static Result receive(byte[] frame) { return receiveForTest(frame, -1); }
    // Package-private fault hook, not part of the public receiving API.
    static Result receiveForTest(byte[] frame, int faultAfter) {
        ArrayList<String> trace = new ArrayList<>(); State state = null;
        try {
            int[] words = deserialize(frame, trace); Cursor c = new Cursor(words); Data d = decode(c);
            trace.add("DATA_VALIDATED:" + d.values.length + ":" + d.roots.length);
            int suppliedSteps = c.count(512);
            state = new State(d.values.length); int consumed = 0;
            for (int field : new int[]{1, 2, 0}) for (int i = 0; i < d.values.length; i++) {
                if (consumed++ >= suppliedSteps) throw new Reject("INVALID_CERT", "missing-step");
                int v = field == 1 ? d.values[i] : field == 2 ? d.links[i] : 1;
                state.step(i, field, v, -1, c, trace);
            }
            for (int root : d.roots) {
                if (consumed++ >= suppliedSteps) throw new Reject("INVALID_CERT", "missing-root-step");
                state.step(root, 0, 1, root, c, trace);
            }
            if (consumed != suppliedSteps) throw new Reject("INVALID_CERT", "extra-step");
            c.end();
            trace.add("CERTIFICATE_ACCEPTED");
            Graph graph = new Graph(d, trace, faultAfter);
            trace.add("PUBLISH");
            return new Result("ALLOW", "checked-frozen-graph", graph, trace, state.reads, state.steps);
        } catch (Reject e) {
            trace.add("REJECT:" + e.status + ":" + e.getMessage());
            return new Result(e.status, e.getMessage(), null, trace, state == null ? 0 : state.reads, state == null ? 0 : state.steps);
        } catch (IOException | ClassNotFoundException | RuntimeException e) {
            trace.add("REJECT:INVALID_FRAME:" + e.getClass().getSimpleName());
            return new Result("INVALID_FRAME", e.getClass().getSimpleName(), null, trace, state == null ? 0 : state.reads, state == null ? 0 : state.steps);
        }
    }

    /** Direct final-state gate: honest baseline, no certificate is needed for it. */
    static Result eagerForTest(byte[] frame, boolean checkInvariant) {
        ArrayList<String> trace = new ArrayList<>();
        try {
            Cursor c = new Cursor(deserialize(frame, trace)); Data d = decode(c);
            int[][] h = new int[d.values.length][3]; boolean[] r = new boolean[h.length];
            for (int i = 0; i < h.length; i++) h[i] = new int[]{1, d.values[i], d.links[i]};
            for (int root : d.roots) r[root] = true;
            boolean[] live = closure(h, r); int reads=0;
            for (int i = 0; i < h.length; i++) if (live[i] && checkInvariant) {
                reads += transcript(h,i).length;
                if (!predicate(h,i)) return new Result("DENY_UNSAFE", "eager-invariant", null, trace, reads, 1);
            }
            Graph graph = new Graph(d, trace, -1); trace.add("PUBLISH");
            return new Result("ALLOW", checkInvariant ? "eager" : "shape-only-control", graph, trace, reads, 1);
        } catch (Reject e) {
            return new Result(e.status, e.getMessage(), null, trace,0,0);
        } catch (IOException | ClassNotFoundException | RuntimeException e) {
            return new Result("INVALID_FRAME", e.getClass().getSimpleName(), null, trace,0,0);
        }
    }
}
