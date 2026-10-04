# Generic-schedule receiver baseline

`GenericReceiver.java` is the incoming receiver implementation retained as the generic-schedule comparison. Its sole source edit is the mechanical public class/constructor rename from `CertifiedReceiver` to `GenericReceiver`, required to compile both implementations in one owned harness. Its parser, predicate, graph construction, and slow shadow-state algorithm are otherwise unmodified. It is not used by the production receiver or the independent certificate reference.

The original `results/receiver-campaign/` and earlier scientific evidence remain unchanged. New paired runs exercise both receivers on the same exact locally generated primitive-array inputs.
