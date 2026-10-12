package evolution;
import java.io.Serializable;
public final class EvolvingNode implements Serializable {
    private static final long serialVersionUID = 1L;
    public int value;
    public EvolvingNode(int value) { this.value = value; }
}
