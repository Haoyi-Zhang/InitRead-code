import java.io.*;
import java.util.*;

/** Same owned bytes and final graph; different transient exposure histories.
 * The benign observer records a Boolean only. No process/network/file effect.
 */
public final class ObservationPair {
    private static boolean expose;
    private static boolean observedUnready;
    private static Box slot;
    private static final List<String> publicEvents = new ArrayList<>();
    private static final List<String> hiddenEvents = new ArrayList<>();
    private static final class Box implements Serializable {
        private static final long serialVersionUID = 1;
        int value=1;
        transient boolean done;
        private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
            publicEvents.add("readObject:enter");
            if (expose) {
                slot=this; hiddenEvents.add("external-reference-set");
                observedUnready = !slot.done;
                hiddenEvents.add("external-read:done="+slot.done);
                slot=null; hiddenEvents.add("external-reference-cleared");
            }
            in.defaultReadObject(); publicEvents.add("defaultReadObject:return:value="+value);
            done=true; publicEvents.add("readObject:exit:done=true");
        }
    }
    private static final class Observer extends ObjectInputStream {
        Observer(InputStream in) throws IOException { super(in); enableResolveObject(true); }
        @Override protected Object resolveObject(Object o) {
            if(o instanceof Box) {
                Box b=(Box)o; publicEvents.add("resolveObject:Box:value="+b.value+":done="+b.done);
            }
            return o;
        }
    }
    private static String strings(List<String> ss) {
        StringJoiner j=new StringJoiner(",","[","]");
        for(String s:ss)j.add("\""+s+"\"");return j.toString();
    }
    public static void main(String[] args) throws Exception {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        try(ObjectOutputStream out=new ObjectOutputStream(bytes)){out.writeObject(new Box());}
        byte[] wire=bytes.toByteArray();List<String> first=null;
        for(boolean choice:new boolean[]{false,true}) {
            expose=choice; observedUnready=false;slot=null;publicEvents.clear();hiddenEvents.clear();
            Box result;
            try(Observer in=new Observer(new ByteArrayInputStream(wire))){result=(Box)in.readObject();}
            publicEvents.add("return:value="+result.value+":done="+result.done+":slot=null");
            if(!choice)first=new ArrayList<>(publicEvents);
            boolean equal=!choice||first.equals(publicEvents);
            if(!equal||observedUnready!=choice||slot!=null)throw new AssertionError();
            System.out.println("{\"expose\":"+choice+",\"observed_unready\":"+observedUnready+
                ",\"same_observation\":"+equal+",\"same_wire\":true,\"public_events\":"+strings(publicEvents)+
                ",\"hidden_events\":"+strings(hiddenEvents)+"}");
        }
    }
}
