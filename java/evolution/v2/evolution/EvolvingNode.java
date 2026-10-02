package evolution;
import java.io.*;
public final class EvolvingNode implements Serializable {
    private static final long serialVersionUID = 1L;
    public int value;
    public Object next;
    public transient boolean defaultedNext;
    private void readObject(ObjectInputStream in) throws IOException, ClassNotFoundException {
        ObjectInputStream.GetField fields = in.readFields();
        value = fields.get("value", -1);
        next = fields.get("next", null);
        defaultedNext = fields.defaulted("next");
    }
}
