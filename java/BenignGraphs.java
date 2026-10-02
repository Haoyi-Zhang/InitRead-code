/* Original benign fixtures. No network, arbitrary input, reflection, native
 * hooks, third-party classes, byte-level edits, or serialized payload files.
 * Only objects created below are round-tripped in memory. */
import java.io.*;
import java.util.*;

public final class BenignGraphs {
    private static int callbacks;
    private static int incompleteCallbacks;
    private static int constructorCalls;
    private static final List<String> callbackStates = new ArrayList<>();
    private static final class Node implements Serializable {
        private static final long serialVersionUID = 1L;
        int value;
        Node next;
        transient boolean ready;
        Node(int value) { this.value = value; this.ready = true; constructorCalls++; }
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            in.defaultReadObject();
            ready = true;
            callbacks++;
            // Passive observation of this owned graph, with no external effects.
            Snapshot observation = new Snapshot(new Node[]{this});
            if (!observation.allReady()) incompleteCallbacks++;
            callbackStates.add("{\"heap\":"+observation.heapJson()+",\"roots\":[0],\"all_ready\":"+
                observation.allReady()+",\"valid\":"+observation.valid()+"}");
        }
    }
    private static final class Snapshot {
        final List<Node> nodes = new ArrayList<>();
        final IdentityHashMap<Node,Integer> ids = new IdentityHashMap<>();
        final List<Integer> roots = new ArrayList<>();
        Snapshot(Node[] initial) {
            for (Node n : initial) roots.add(add(n));
            for (int i=0; i<nodes.size(); i++) {
                Node next=nodes.get(i).next;
                if (next != null) add(next);
            }
        }
        int add(Node n) {
            if (n == null) throw new IllegalArgumentException("null root");
            Integer prior=ids.get(n);
            if (prior != null) return prior;
            int id=nodes.size(); ids.put(n,id); nodes.add(n); return id;
        }
        boolean allReady() {
            for (Node n:nodes) if (!n.ready) return false;
            return true;
        }
        boolean valid() {
            for (Node n:nodes)
                if (!n.ready || (n.next != null && n.value > n.next.value)) return false;
            return true;
        }
        String heapJson() {
            StringBuilder b=new StringBuilder("[");
            for (int i=0;i<nodes.size();i++) {
                Node n=nodes.get(i);
                if (i>0) b.append(',');
                b.append('[').append(n.ready ? 1 : 0).append(',').append(n.value).append(',')
                 .append(n.next==null ? -1 : ids.get(n.next)).append(']');
            }
            return b.append(']').toString();
        }
    }
    private static final int[][] NEXT = {
        {-1}, {0}, {1,-1}, {1,2,-1}, {1,0}, {1,2,0}, {2,2,3,-1}, {1,2,3,4,5,2}
    };
    private static final int[][] ROOTS = {{0},{0},{0},{0},{0},{0},{0,1},{0}};
    public static void main(String[] args) throws Exception {
        if (args.length != 0) throw new IllegalArgumentException("no external inputs accepted");
        int caseId=0;
        for (int shape=0;shape<NEXT.length;shape++) {
            for (int pattern=0;pattern<3;pattern++) {
                Node[] nodes=new Node[NEXT[shape].length];
                for (int i=0;i<nodes.length;i++)
                    nodes[i]=new Node(pattern==0 ? 0 : (pattern==1 ? 1 : (i%2==0 ? 1 : 0)));
                for (int i=0;i<nodes.length;i++)
                    nodes[i].next=NEXT[shape][i]==-1 ? null : nodes[NEXT[shape][i]];
                Node[] roots=new Node[ROOTS[shape].length];
                for (int i=0;i<roots.length;i++) roots[i]=nodes[ROOTS[shape][i]];
                boolean inputValid = new Snapshot(roots).valid();
                ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                try (ObjectOutputStream out=new ObjectOutputStream(bytes)) { out.writeObject(roots); }
                callbacks=0; incompleteCallbacks=0; constructorCalls=0; callbackStates.clear();
                Node[] restored;
                try (ObjectInputStream in=new ObjectInputStream(new ByteArrayInputStream(bytes.toByteArray()))) {
                    restored=(Node[])in.readObject();
                }
                Snapshot snapshot=new Snapshot(restored);
                System.out.println("{\"case\":\"J"+String.format("%02d",caseId++)+"\",\"shape\":"+shape+
                    ",\"pattern\":"+pattern+",\"callbacks\":"+callbacks+
                    ",\"incomplete_callbacks\":"+incompleteCallbacks+",\"input_valid\":"+inputValid+
                    ",\"constructors_during_read\":"+constructorCalls+",\"callback_states\":"+callbackStates+
                    ",\"heap\":"+snapshot.heapJson()+
                    ",\"roots\":"+snapshot.roots+",\"valid\":"+snapshot.valid()+"}");
            }
        }
    }
}
