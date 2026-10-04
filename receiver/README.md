# Callback-free receiver

This is a deliberately different receiving protocol, not instrumentation of arbitrary Serializable classes. The previous passive bridge remains unchanged: three final snapshots map and eight cases return UNKNOWN.

## Contract

An untrusted sender submits one canonical ObjectOutputStream serialization of an int[]. The array contains a fixed schema, bit values, successor indices, requested roots, and certificates for a receiver-determined shadow plan. Only the primitive-array descriptor is admitted. The stream filter enforces allocation limits; an exact post-read class check rejects values that do not use that descriptor path. The receiver re-encodes the decoded int[] and compares the whole byte frame, rejecting trailing, alternative, and partial extra representations.

The receiving API is `CertifiedReceiver.receive(byte[])`. A successful Result contains a final, non-Serializable Graph; failures contain no Graph. Graph roots are returned in a fresh array. Final Node wrappers provide identity, value, and successor reads but no mutation. Package-private snapshot, eager-baseline, and construction-fault methods are owned test interfaces; untrusted same-package or privileged code is not the adversary.

The abstract schema remains exactly `(ready,value,next)`, at most128 nodes, and `ready && (next == null || value <= next.value)`. Readiness and the event plan are receiver-owned. Requested root data are not claims about historical JVM aliases. `SHADOW_CHECK` records are private verifier transitions, **not** deserializer/JVM write events. Public nodes are allocated after successful checking.

## Guarantee and limits

`proofs/receiver.md` proves, by handwritten arguments under explicit JDK/configuration and storage-integrity assumptions, that public navigation represents the accepted final data and preserves its invariant. It also proves that a valid certificate exists exactly for the data accepted by a direct eager invariant check. The certificate therefore adds checked transcripts, not stronger final-state safety. It was slower than eager checking in the measured batches.

There is no arbitrary Serializable compatibility, JVM-wide monitoring, constructor-history attestation, reflective/native/concurrent mutation coverage, proof-assistant verification, or production study. A configured filter factory, agents, receiver code, and JDK are trusted. A caller must not concurrently mutate its input during the defensive copy. Errors before a normal return are not all promised to become diagnostics; allocation/VM failure availability is excluded.

## Reproduce

From the artifact root, using Python3.9+ and a local JDK (recorded execution:JDK21):

```sh
python3 reproduce_receiver.py --out receiver-output
```

This executes five unit test methods, creates and saves all benign serialized inputs, compiles the Java source, runs4,563 Java cases and the same-byte observation pair, and measures42 sequential size-specific Java forks. No dependency is downloaded and no network or model API is used. The output directory must be absent or empty.

A deterministic replay without repeating variable timing measurements is:

```sh
python3 reproduce_receiver.py --out receiver-replay \
  --verify-against results/receiver-campaign --skip-benchmark
```

Comparison includes five deterministic result/input files and the complete set of saved `.ser` inputs. Timing is not required to match. Failures save diagnostics before a nonzero exit. Original baseline results are never rewritten by comparison.

To regenerate the manuscript tables from the recorded full run:

```sh
python3 export_receiver_data.py --results results/receiver-campaign --out tables
```

The artifact has no dependency on the paper directory. The `tables` files can be copied into a manuscript after generation.

## Implementations and evidence

- `receiver/producer.py`: domain validation, fixed plan, inherited producer integration, integer encoding.
- `receiver/reference.py`: separate raw integer data parser and dense closure, with no imports; does not validate certificates.
- `java/CertifiedReceiver.java`: independent Java gate, canonical transport restriction, private representation and publication point.
- `java/ReceiverHarness.java`: owned serialization, controls, snapshots, aliases, costs.
- `java/ObservationPair.java`: same serialized input and public projection with different owned unfinished-read observations.
- `receiver_tests/test_receiver.py`: raw-root, data, and code-separation tests.
- `results/receiver-campaign/`: current raw correctness and performance evidence.
- `results/receiver-pilot/`: retained shorter-warmup observations and affected source; not pooled with final timings.
- `results/receiver-framing-control/`: retained pre-canonical-check run, minimal acceptance probe, and affected source.

The earlier EOF-based framing check really accepted a truncated trailing value. The canonical restriction repaired that issue, changed receiving costs, and added a tenth wire control. It does not make old results into passing observations.

All implementations, proofs, and internal checks belong to the same research execution. Code separation is not independent external validation.
