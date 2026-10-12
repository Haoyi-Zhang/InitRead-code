/*
 * Benign, self-contained observations of Java ObjectInputStream behavior.
 * The program creates every object itself, serializes only to memory, accepts no
 * external input, and performs no reflection, native calls, network access, or
 * byte-stream mutation.  It is an observation harness, not an enforcement agent.
 */
import java.io.*;
import java.util.*;

public final class DeserializationTraceHarness {
    private static final List<String> EVENTS = new ArrayList<>();
    private static int constructorCalls;
    private static boolean callbackObservedUnready;

    private static String q(String value) {
        if (value == null) return "null";
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '\\': out.append("\\\\"); break;
                case '"': out.append("\\\""); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format("\\u%04x", (int)c));
                    else out.append(c);
            }
        }
        return out.append('"').toString();
    }

    private static String stringArray(Collection<String> values) {
        StringBuilder out = new StringBuilder("[");
        boolean first = true;
        for (String value : values) {
            if (!first) out.append(',');
            first = false;
            out.append(q(value));
        }
        return out.append(']').toString();
    }

    private static byte[] serialize(Object value) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
            out.writeObject(value);
        }
        return bytes.toByteArray();
    }

    private static Object deserialize(byte[] bytes) throws IOException, ClassNotFoundException {
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(bytes))) {
            return in.readObject();
        }
    }

    private static void reset() {
        EVENTS.clear();
        constructorCalls = 0;
        callbackObservedUnready = false;
        EscapeNode.escaped = null;
        FailingNode.escaped = null;
    }

    private static final class TraceNode implements Serializable {
        private static final long serialVersionUID = 1L;
        String label;
        int value;
        TraceNode next;
        transient boolean callbackDone;

        TraceNode(String label, int value) {
            this.label = label;
            this.value = value;
            this.callbackDone = true;
            constructorCalls++;
        }

        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            EVENTS.add("TraceNode.readObject.enter");
            in.defaultReadObject();
            boolean peerDone = next == null || next.callbackDone;
            EVENTS.add("TraceNode.afterDefault:" + label + ":nextDone=" + peerDone);
            if (!peerDone) callbackObservedUnready = true;
            callbackDone = true;
            EVENTS.add("TraceNode.readObject.exit:" + label);
        }
    }

    private static final class AliasHolder implements Serializable {
        private static final long serialVersionUID = 1L;
        TraceNode left;
        TraceNode right;
        AliasHolder(TraceNode node) { left = node; right = node; }
    }

    private static final class EscapeNode implements Serializable {
        private static final long serialVersionUID = 1L;
        static EscapeNode escaped;
        int value;
        transient boolean callbackDone;
        EscapeNode(int value) { this.value = value; callbackDone = true; constructorCalls++; }
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            EVENTS.add("EscapeNode.readObject.enter:value=" + value);
            escaped = this;
            EVENTS.add("EscapeNode.publishedBeforeDefault:value=" + value);
            in.defaultReadObject();
            callbackDone = true;
            EVENTS.add("EscapeNode.readObject.exit:value=" + value);
        }
    }

    private static final class CanonicalNode {
        final int value;
        CanonicalNode(int value) { this.value = value; }
    }

    private static final CanonicalNode CANONICAL = new CanonicalNode(7);

    private static final class ResolveProxy implements Serializable {
        private static final long serialVersionUID = 1L;
        int value;
        ResolveProxy(int value) { this.value = value; constructorCalls++; }
        private Object readResolve() throws ObjectStreamException {
            EVENTS.add("ResolveProxy.readResolve");
            return CANONICAL;
        }
    }

    private static final class TypeBox implements Serializable {
        private static final long serialVersionUID = 1L;
        Object payload;
        transient boolean mismatch;
        TypeBox(Object payload) { this.payload = payload; constructorCalls++; }
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            EVENTS.add("TypeBox.readObject.enter");
            in.defaultReadObject();
            mismatch = !(payload instanceof TraceNode);
            EVENTS.add("TypeBox.readObject.exit:mismatch=" + mismatch);
        }
    }

    private static final class FailingNode implements Serializable {
        private static final long serialVersionUID = 1L;
        static FailingNode escaped;
        boolean publishBeforeThrow;
        int value;
        FailingNode(boolean publishBeforeThrow, int value) {
            this.publishBeforeThrow = publishBeforeThrow;
            this.value = value;
            constructorCalls++;
        }
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            EVENTS.add("FailingNode.readObject.enter");
            in.defaultReadObject();
            if (publishBeforeThrow) {
                escaped = this;
                EVENTS.add("FailingNode.publishedBeforeThrow");
            }
            EVENTS.add("FailingNode.throw");
            throw new InvalidObjectException("owned failure fixture");
        }
    }

    private static final class ObservingInputStream extends ObjectInputStream {
        final List<String> resolvedClasses = new ArrayList<>();
        ObservingInputStream(InputStream in) throws IOException {
            super(in);
            enableResolveObject(true);
        }
        @Override protected Object resolveObject(Object obj) throws IOException {
            resolvedClasses.add(obj == null ? "null" : obj.getClass().getName());
            return obj;
        }
    }

    private static final class Snapshot {
        final List<TraceNode> nodes = new ArrayList<>();
        final IdentityHashMap<TraceNode,Integer> ids = new IdentityHashMap<>();
        final List<Integer> roots = new ArrayList<>();

        Snapshot(TraceNode... initial) {
            for (TraceNode node : initial) roots.add(add(node));
            for (int i = 0; i < nodes.size(); i++) {
                TraceNode next = nodes.get(i).next;
                if (next != null) add(next);
            }
        }

        int add(TraceNode node) {
            if (node == null) throw new IllegalArgumentException("null modeled root");
            Integer prior = ids.get(node);
            if (prior != null) return prior;
            int id = nodes.size();
            ids.put(node, id);
            nodes.add(node);
            return id;
        }

        String json() {
            StringBuilder heap = new StringBuilder("[");
            for (int i = 0; i < nodes.size(); i++) {
                if (i > 0) heap.append(',');
                TraceNode node = nodes.get(i);
                heap.append('[').append(node.callbackDone ? 1 : 0).append(',')
                    .append(node.value).append(',')
                    .append(node.next == null ? -1 : ids.get(node.next)).append(']');
            }
            heap.append(']');
            return "{\"heap\":" + heap + ",\"roots\":" + roots
                + ",\"ready_provenance\":\"owned_readObject_callback_exit\"}";
        }
    }

    private static String features(boolean earlyEscape, boolean readResolve,
                                   boolean missingField, boolean typeMismatch,
                                   boolean incompleteCallback, boolean coverageGap,
                                   boolean failureAfterEscape) {
        return "{\"early_external_escape\":" + earlyEscape
            + ",\"read_resolve_substitution\":" + readResolve
            + ",\"missing_field\":" + missingField
            + ",\"type_shape_mismatch\":" + typeMismatch
            + ",\"callback_observed_unready\":" + incompleteCallback
            + ",\"observer_coverage_gap\":" + coverageGap
            + ",\"failure_after_escape\":" + failureAfterEscape + "}";
    }

    private static void emit(String caseName, boolean success, String exception,
                             String features, String snapshot, String facts) {
        System.out.println("{\"case\":" + q(caseName)
            + ",\"success\":" + success
            + ",\"exception\":" + q(exception)
            + ",\"events\":" + stringArray(EVENTS)
            + ",\"constructor_calls_during_read\":" + constructorCalls
            + ",\"features\":" + features
            + ",\"snapshot\":" + (snapshot == null ? "null" : snapshot)
            + ",\"facts\":" + facts + "}");
    }

    private static void plainCase(String caseName, int leftValue, int rightValue) throws Exception {
        TraceNode left = new TraceNode("left", leftValue);
        TraceNode right = new TraceNode("right", rightValue);
        left.next = right;
        byte[] bytes = serialize(left);
        reset();
        TraceNode restored = (TraceNode) deserialize(bytes);
        emit(caseName, true, null,
             features(false, false, false, false, callbackObservedUnready, false, false),
             new Snapshot(restored).json(),
             "{\"root_class\":\"TraceNode\",\"callbacks_complete\":true}");
    }

    private static void sharedAliasCase() throws Exception {
        TraceNode node = new TraceNode("shared", 1);
        AliasHolder holder = new AliasHolder(node);
        byte[] bytes = serialize(holder);
        reset();
        AliasHolder restored = (AliasHolder) deserialize(bytes);
        boolean aliasPreserved = restored.left == restored.right;
        emit("shared-alias", true, null,
             features(false, false, false, false, callbackObservedUnready, false, false),
             new Snapshot(restored.left, restored.right).json(),
             "{\"alias_preserved\":" + aliasPreserved + ",\"root_slots\":2}");
    }

    private static void cycleCase() throws Exception {
        TraceNode a = new TraceNode("a", 1);
        TraceNode b = new TraceNode("b", 1);
        a.next = b; b.next = a;
        byte[] bytes = serialize(a);
        reset();
        TraceNode restored = (TraceNode) deserialize(bytes);
        emit("cycle-callback-order", true, null,
             features(false, false, false, false, callbackObservedUnready, false, false),
             new Snapshot(restored).json(),
             "{\"peer_seen_before_callback_exit\":" + callbackObservedUnready + "}");
    }

    private static void earlyEscapeCase() throws Exception {
        byte[] bytes = serialize(new EscapeNode(1));
        reset();
        EscapeNode restored = (EscapeNode) deserialize(bytes);
        boolean retained = EscapeNode.escaped == restored;
        emit("early-external-escape", true, null,
             features(true, false, false, false, false, false, false),
             null,
             "{\"escaped_alias_is_returned_root\":" + retained
                + ",\"final_value\":" + restored.value + "}");
        EscapeNode.escaped = null;
    }

    private static void readResolveCase() throws Exception {
        byte[] bytes = serialize(new ResolveProxy(3));
        reset();
        Object restored = deserialize(bytes);
        emit("read-resolve-external-alias", true, null,
             features(false, true, false, false, false, false, false),
             null,
             "{\"returned_preexisting_canonical\":" + (restored == CANONICAL)
                + ",\"returned_class\":" + q(restored.getClass().getName()) + "}");
    }

    private static void typeMismatchCase() throws Exception {
        byte[] bytes = serialize(new TypeBox("not-a-node"));
        reset();
        TypeBox restored = (TypeBox) deserialize(bytes);
        emit("type-shape-mismatch", true, null,
             features(false, false, false, restored.mismatch, false, false, false),
             null,
             "{\"payload_class\":" + q(restored.payload.getClass().getName()) + "}");
    }

    private static void observerGapCase() throws Exception {
        TraceNode[] roots = {new TraceNode("array-node", 1)};
        byte[] bytes = serialize(roots);
        reset();
        TraceNode[] restored;
        List<String> observed;
        try (ObservingInputStream in = new ObservingInputStream(new ByteArrayInputStream(bytes))) {
            restored = (TraceNode[]) in.readObject();
            observed = new ArrayList<>(in.resolvedClasses);
        }
        boolean sawArray = observed.stream().anyMatch(name -> name.startsWith("["));
        emit("resolve-object-field-write-gap", true, null,
             features(false, false, false, false, callbackObservedUnready, true, false),
             new Snapshot(restored).json(),
             "{\"resolve_object_classes\":" + stringArray(observed)
                + ",\"array_seen_by_resolveObject\":" + sawArray
                + ",\"field_write_events_observed\":0}");
    }

    private static void failureCase(boolean publish) throws Exception {
        byte[] bytes = serialize(new FailingNode(publish, 1));
        reset();
        String exception = null;
        boolean success = false;
        try {
            deserialize(bytes);
            success = true;
        } catch (InvalidObjectException expected) {
            exception = expected.getClass().getName();
        }
        boolean escaped = FailingNode.escaped != null;
        emit(publish ? "failure-after-external-escape" : "failure-closed", success, exception,
             features(escaped, false, false, false, false, false, escaped),
             null,
             "{\"external_alias_after_failure\":" + escaped + "}");
        FailingNode.escaped = null;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 0) throw new IllegalArgumentException("no external inputs accepted");
        plainCase("plain-safe", 0, 1);
        plainCase("plain-unsafe", 1, 0);
        sharedAliasCase();
        cycleCase();
        earlyEscapeCase();
        readResolveCase();
        typeMismatchCase();
        observerGapCase();
        failureCase(false);
        failureCase(true);
    }
}
