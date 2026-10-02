# Concrete Java trace to bounded-certificate bridge

## Status

This note specifies the **partial data bridge** exercised by
`reproduce_trace_bridge.py`.  It is not a JVM refinement theorem, a constructor
history proof, a bytecode monitor, or a deployment enforcement result.  The
bridge either maps one owned final observation to the existing bounded heap
model or returns `UNKNOWN`.

The implementation under discussion is `src/java_trace_bridge.py`.  That
module does not import the certificate producer, production checker, or dense
oracle.  The runner invokes the dense oracle and the production checker only
after the independent bridge has returned a bounded snapshot.

## Concrete execution envelope

The executable evidence uses ordinary `java.io.ObjectOutputStream` and
`java.io.ObjectInputStream` on locally authored classes.  The recorded run used
OpenJDK 21.0.11 on Debian GNU/Linux 13, amd64, with one sequential Java child at
a time and the JVM options recorded in `results/bridge-campaign/environment.json`.
The code accepts no serialized input from outside the repository and performs
no network, native, reflective-field-write, `Unsafe`, or class-loader experiment.

For a single call to `ObjectInputStream.readObject`, the harness records a
finite trace over the following event families:

- entry to and exit from an owned class's private `readObject` callback;
- the point immediately after `defaultReadObject` for the owned node;
- execution of `readResolve` in an owned proxy;
- callbacks made to an owned `ObjectInputStream.resolveObject` override;
- an exception thrown by an owned `readObject` callback;
- writes by owned callback code to an owned static escape slot; and
- the returned root and a final identity-based snapshot, when one is available.

These are application-level observations.  They are not a complete log of JVM
allocations, field writes, handle-table operations, alias transfers, or reads by
arbitrary callback code.

## Concrete records and stages

An owned `TraceNode` has integer `value`, reference `next`, transient Boolean
`callbackDone`, and a nonsemantic label used only in the trace.  During a normal
owned callback, `callbackDone` is false on entry, `defaultReadObject` restores
serialized fields, and the callback then sets `callbackDone=true` before exit.
The experiment observed zero invocations of the serializable fixture
constructors during reading.  That observation is consistent with the Java
serialization mechanism for these classes, but it is not encoded as the
abstract `ready` bit and is not generalized to all classes or mechanisms.

The harness distinguishes these coarse stages:

1. `CALLBACK_ACTIVE`: an owned `readObject` has entered and has not exited;
2. `CALLBACK_DONE`: the owned callback has set its local marker and exited;
3. `RETURNED`: `ObjectInputStream.readObject` returned a root; and
4. `FAILED`: the read threw and returned no root.

A cyclic graph can expose a peer in `CALLBACK_ACTIVE` while another callback is
executing.  Callback completion is therefore object-local and ordered; it is
not a graph-wide initialization barrier.

## Partial mapping

Let `J` be one JSON observation.  The bridge `M(J)` returns `MAPPED(H,B)` only
if all of the following hold:

1. the read returned successfully;
2. the feature vector is complete and every blocking feature is false;
3. an exact final owned snapshot is present;
4. the snapshot contains 1--128 records of exactly three Python integers;
5. each record belongs to the fixed domain `(ready,value,next)`, with the first
   two entries in `{0,1}` and `next` either `-1` or an in-range object index;
6. the supplied root collection is a list or tuple of at most 128 entries;
7. **before deduplication**, every root has exact type `int` and is in range;
8. the nonempty root set is formed only after the preceding checks; and
9. the recorded ready provenance is exactly
   `owned_readObject_callback_exit`.

The blocking features are early external escape, `readResolve` substitution,
missing-field provenance, type/shape mismatch, a callback observation of an
unfinished peer, a public-hook coverage gap, and failure after escape.  A
failed read also returns `UNKNOWN` even when no escape is observed.

For a mapped record, the abstract bit means only:

> the owned fixture's `readObject` callback set its marker before exiting.

It does not mean that a Java constructor ran, that every serializable superclass
completed a callback, that all aliases were captured, or that the JVM attested
an initialization protocol.

## Conditional correspondence proposition

**Proposition.**  Suppose `M(J)=MAPPED(H,B)`.  Suppose additionally that the
owned final snapshot enumerates every modeled object reachable from every
modeled retained root, preserves identity and `next` aliases, and reports the
three fixed fields without omission or substitution.  Then evaluation of the
fixed bounded predicate on `(H,B)` is exactly evaluation of the same three-field
predicate over that recorded final snapshot.

**Argument.**  `M` accepts only records whose fields and references are in the
bounded domains and copies those values position-for-position.  Exact-type and
range checks precede root deduplication.  Under the additional completeness and
identity assumptions, graph reachability from `B` is the same in the snapshot
and in `H`.  The predicate reads only `ready`, `value`, and `next`, all of which
are copied unchanged.  Therefore each reachable object's predicate value, and
hence their conjunction, is equal in the two representations.  This is a
structural encoding argument.  It says nothing about unobserved concrete
histories, later writes, other fields, or callbacks outside the owned fixture.

The runner checks mapped cases in two further, separately coded ways: the dense
oracle evaluates the snapshot by transitive closure, and the production checker
attempts initial admission.  In the recorded run both agree on the three mapped
cases: two safe and one unsafe.

## Why the bridge is intentionally incomplete

The following executed cases demonstrate why a generic concrete-to-abstract
refinement has not been established:

- **cycle callback order:** one node observes a reachable peer before that
  peer's callback marker is complete;
- **early external escape:** callback code stores `this` in an external static
  field before `defaultReadObject` restores the serialized value;
- **`readResolve` substitution:** the returned root is a pre-existing canonical
  object rather than the proxy instance restored from the stream;
- **missing field:** a stream written by a prior class version is read by a
  later version, and `GetField.defaulted("next")` reports that the field was
  absent rather than explicitly serialized as null;
- **type/shape mismatch:** an `Object`-typed field contains a `String`, so the
  fixed node shape does not describe the restored graph;
- **public-hook coverage gap:** `resolveObject` reports objects but provides no
  event for each individual field assignment needed by the incremental
  checker;
- **closed failure:** an exception returns no root, so there is no successful
  boundary value to map; and
- **failure after escape:** an exception returns no root but an external static
  alias written by the callback remains observable.

The fail-after-escape case is especially important: “`readObject` threw” is not
by itself a rollback guarantee for arbitrary callback side effects.  Conversely,
returning `UNKNOWN` does not assert that the run is unsafe; it states that the
passive evidence is insufficient for this abstract checker.

## Consequence for paper claims

The executable bridge supports only a bounded observation result:

- three uncomplicated owned final snapshots can be encoded and checked;
- eight special or incomplete-observation cases are conservatively refused; and
- passive `ObjectInputStream` callbacks do not supply the complete authentic
  write/root stream assumed by the atomic abstract transition checker.

Accordingly, the project does not claim a production deserialization monitor,
JVM-level initialization proof, constructor attestation, or a new TIFS-level
enforcement contribution.  Establishing such a result would require an actual
enforcement point, a coverage argument for all relevant aliases and writes, a
semantics for substitutions and failures, and a proved refinement from that
mechanism to the bounded checker.
