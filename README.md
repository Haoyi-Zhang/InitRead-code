# Read certificates: bounded checking and a callback-free receiver

This standalone repository contains three related, explicitly different paths:

1. the inherited fixed object-graph checker, certificate producer, independent dense oracle, and bounded witness tests;
2. the passive Java deserialization observation study, still yielding three MAPPED final snapshots and eight UNKNOWN cases; and
3. a new data-only Java receiver, independent raw-data reference, private read-only graph representation, an exact schedule specialization and a conditional publication argument.

The new receiver changes the wire/API contract: it deserializes only a canonical primitive int[] and constructs application nodes only after validation. It is not an instrumentation layer or transparent replacement for arbitrary Serializable objects. Readiness is private checker metadata, not constructor-history evidence. The direct eager baseline implements the same final data policy without certificates and was faster in the measured batches.

## Requirements

Python 3.9 or newer and a local JDK providing java and javac are required; all Python dependencies are in the standard library. The original full campaigns used Debian GNU/Linux 13 x86-64, CPython 3.13.5 and Debian OpenJDK/javac 21.0.11. The paired measurements used in the manuscript's specialization tables were recorded separately on Ubuntu 24.04.5 x86-64, CPython 3.12.14 and Temurin 21.0.12.1+1, before matched canonical-buffer preallocation. The Windows x64 replay used CPython 3.12.14 and Temurin 17.0.20.1+1 and supplies correctness comparisons, not timings. These records are kept separate; no additional JDK/vendor combination has been evaluated. Runtime-evaluated built-in generic aliases require Python 3.9.

All output directories below must be absent or empty. All Java children are sequential; one active processor, SerialGC, a 256 MiB heap cap, and javac -proc:none are recorded by the runners. Each command records actual environment and code/input bindings. Original historical versions and architecture that were never recorded remain unknown.

### Portable Python-only execution

The bounded Python computation and integer references can also run without a
JDK or POSIX `resource`. This is an explicitly partial execution, not a new Java
stream-decoding, receiver-differential, or performance experiment:

```sh
python -B -m unittest discover -s portability_tests -v
python -B reproduce_portable.py --out /absolute/fresh/python-scope
```

This runs the complete two-/three-object enumeration, witness/capacity controls,
all 32 existing Python tests, receiver packet generation, the independent
5,248-packet certificate reference, and reinterpretation of the 11 archived
passive observations. It compares six inherited semantic JSON and four byte
files, plus both campaigns' generated input files. It never supplies synthetic
Java observations or serialized sizes. Wall time and Python CPU are measured;
unsupported peak RSS is JSON `null`, not zero or a Linux-equivalent estimate.

In the standalone InitRead code repository, the contents of this `artifact/`
directory are the repository root. Its `.github/workflows/scientific-checks.yml`
runs all four full campaigns and the portability regressions on Ubuntu,
Python 3.12, and Temurin 21. The retained pre-preallocation run passed all five commands:
615,984 finite transitions, 4,563 real Java receiver cases, 5,248 specialization
cases, 42 receiver timing forks, 28 paired specialization forks, and 30 exact
size-bound equalities. Raw observations and command logs are in `results/current/`.
They use their own measured Linux/OpenJDK 21 environment and original sources,
before the capacity pre-sizing below; they are not new timings of current code.
The workflow definition is not a receipt of a fresh CI execution.
The saved receiver streams reproduce the unchanged `results/receiver-campaign/`
streams byte-for-byte, so that input set is retained once rather than duplicated.

### Current-only portable Java correctness

With Python 3.9+ and a local JDK 17+ (no automatic download), run:

```sh
python -B reproduce_java_conformance.py --java-home /absolute/local/jdk \
  --out /absolute/fresh/java-correctness-output
```

From this artifact directory, the equivalent single-line PowerShell command is
`python -B reproduce_java_conformance.py --java-home "D:/your/local/jdk" --out "D:/your/fresh/java-correctness-output"`.
Replace both example paths with your chosen local JDK and absent output directory.

The input tables and retained observations are supplied under
`results/receiver-campaign/` and `results/specialization-campaign/`. The command
reads those canonical records directly; it does not require a separate
`results/current/` copy.

`--java-home` may be omitted when `JAVA_HOME`, or both `java` and `javac` on
`PATH`, select the intended JDK. The output directory must not exist and must
be outside this artifact. All classes, newly serialized inputs, raw observations,
fresh Python-reference results and command/version receipts stay there. The
driver has no timing option and invokes no benchmark branch. It uses no before
copy, private validation path, network service or third-party serialized input.

This compiles the two current receivers and three reviewed harnesses with
`--release 17 -proc:none`, runs the ten receiver test methods, and replays the
included 4,563 receiver observations and 5,248 integer cases. It compares full
receiver and integer outputs against `results/current/`, the complete serialized
input set byte-for-byte against `results/receiver-campaign/streams`, and 31,488
six-mode observations against a compact retained original-output fingerprint.
The added `CapacityObservationHarness` has no benchmark path. The fingerprint
and its exact canonicalization/provenance are in `java-conformance-contract.json`;
no second serialized stream archive is included.

Both independent Python references execute anew. Certificate classifications
are checked for every integer packet; the final-data reference independently
checks eager policy and published representation wherever it has complete valid
data. Six-mode matched comparisons retain reasons, traces, steps/read counters,
heap/ordered roots and alias-freeze observations, including negative controls.
References do not model Java serialization. This is bounded replay evidence,
not a universal proof or performance measurement. A mismatch, timeout or child
failure exits nonzero and preserves diagnostics; historical campaigns and
timings are never rewritten. Current portable execution metadata, when available,
is separate in `results/current/java-portable-conformance.json`.

## Commands

Preserved finite model, including 17 test methods and 7 scientific JSON / 5 deterministic file comparisons:

```sh
python3 reproduce.py --out legacy-output --verify-against results/campaign
```

Passive ordinary-object Java observations and five bridge test methods:

```sh
python3 reproduce_trace_bridge.py --out bridge-output
```

Receiver replay with ten receiver test methods, 4,563 actual Java cases and the paired observation. Omitting --skip-benchmark reruns the older six-size timing protocol on the current code, not the historical generic implementation:

```sh
python3 reproduce_receiver.py --out receiver-output --skip-benchmark
```

Deterministic receiver replay without requiring nondeterministic timings to match:

```sh
python3 reproduce_receiver.py --out receiver-replay \
  --verify-against results/receiver-campaign --skip-benchmark
```

The comparison checks five deterministic result/input files and all saved serialized input files as a complete set. The original finite replay excludes only documented timing/RSS fields from its seven scientific JSON comparisons. No runner overwrites the baseline to produce a match. Nonzero results produce diagnostics rather than a fabricated successful report.

Table generation has no dependency on a paper directory:

```sh
python3 export_paper_data.py --results results/campaign --out legacy-tables
python3 export_receiver_data.py --results results/receiver-campaign --out receiver-tables
```

## Exact specialization and three-way comparison

The production State represents the fixed schedule without cloning the whole heap at every step. The historical generic verifier was retained in `baselines/GenericReceiver.java` with a class/constructor rename. The current copy additionally pre-sizes the canonical transport buffer using `27 + Integer.BYTES * words.length`, exactly as the current specialized receiver does. Its generic shadow-state algorithm, parser and data policy remain unchanged. Frozen Linux/OpenJDK 21 measurements describe the original sources before this matched capacity change, not current preallocation performance. `receiver/certificate_reference.py` independently parses complete integer certificates and recomputes whole states; it imports no production component. Its scope is not Java stream decoding.

```sh
python3 reproduce_specialization.py --out specialization-output
python3 reproduce_specialization.py --out specialization-replay \
  --verify-against results/specialization-campaign --skip-benchmark
python3 export_specialization_data.py --results results/specialization-campaign \
  --out specialization-tables
```

The full command adds28 sequential JVM timing forks. The replay checks five deterministic input/result files and does not require timing equality. Plans and inclusion rules are in `receiver/specialization-contract.md`; complete proof arguments are in `proofs/specialization.md`. Safe packets require complete exact proof parsing. `DENY_UNSAFE` identifies a checked unsafe prefix and does not authenticate a later unconsumed tail. Both reject outcomes return a null graph.

An earlier attempt hit an outer execution timeout after completing its core comparison and some timing forks. Its unknown overall exit and partial files remain in `results/specialization-interrupted/`. The successful complete run is separate and its timings are not pooled with the partial attempt.

## Retained evidence

| Study | Result | Scope |
|---|---|---|
| Original finite campaign |615,984 transitions ; 0 checker/oracle disagreements ; 4,296 misses by written-object-only control|All two-/three-object cases in the fixed domain, not arbitrary Java|
| Passive Java bridge |11 cases; 3 MAPPED, 8 UNKNOWN|Original callback/alias/evolution boundary remains unresolved for that path|
| Receiver valid-data cases |4,443; 3,397 ALLOW, 1,046 DENY_UNSAFE|Includes 4,248 exact small inputs, 96 larger, 96 renamed, 3 capacity|
| Receiver controls |97 certificate, 12 data, 10 wire, 1 construction failure|All fail without returning a graph|
| Receiver total |4,563; 0 oracle/representation/alias/decision errors|Only the accepted primitive-data contract|
| Observation pair |same bytes and selected public projection; unfinished-read outcome differs|Limit for this projection, not all Java observers|
| Direct baseline |same data policy as an existent valid certificate|No extra semantic protection from certificates in this setting|
| Retained generic timing at128 nodes |420.45 µs generic vs39.85 µs eager|Historical six-size protocol, not current specialized cost|
| Exact specialization |5,248 integer packets; zero full-observation and independent-certificate-reference disagreement|4,552 retained inputs plus696 targeted/size cases, not new applications|
| Sharp accepting packet bound |22,134 words /88,563 canonical serialized bytes|Attained at128 nodes and128 repeated roots|
| Retained paired timing before preallocation |Median generic/specialized factors2.81–10.36; specialized/eager1.18–3.69|Original Linux/OpenJDK 21 sources; four controlled families, seven forks each; full ranges retained; no new capacity timing|
| Current Windows 17 finite conformance |4,563 receiver/serialized cases; 5,248 integer packets; 31,488 six-mode observations; ten receiver tests|Temurin 17.0.20.1+1; fresh independent Python references; exact retained comparisons; no benchmark or universal correctness claim|

## Evidence locations

- `proofs/argument.md`: inherited handwritten finite-model proof.
- `proofs/concrete-bridge.md`: retained partial snapshot-mapping conditions.
- `proofs/receiver.md`: observation limit, shadow soundness, representation, publication, eager-equivalence, and packet bound.
- `src/`: original model, producer, checker, oracle, witness and passive bridge.
- `receiver/`, `receiver_tests/`: packet producer, independent data and complete-certificate references; root, oracle, exact-bound and denial-tail tests.
- `java/CertifiedReceiver.java`, `ReceiverHarness.java`, `ObservationPair.java`: actual receiving path and benign experiments.
- `java/DeserializationTraceHarness.java`, `java/evolution/`: unchanged ordinary-object study.
- `results/campaign/`: immutable original scientific baseline.
- `results/final-replay/`, `results/bridge-campaign/`: inherited verified runs, with their own recorded environments.
- `results/receiver-campaign/`: unchanged generic receiving baseline and historical timing.
- `results/specialized-replay/`: current specialized code replaying all 4,563 original receiving cases.
- `results/specialization-campaign/`: independent certificate reference, generic/specialized differential results and paired timings.
- `results/continuation-clean/`: successful clean-extraction commands, all legacy/bridge/receiver/specialization comparisons and exported tables.
- `results/receiver-pilot/`, `results/receiver-framing-control/`: preserved measurement/framing repair evidence and affected source.
- `results/clean-check/`: retained clean verification of the incoming generic receiver; the current verification is in `results/continuation-clean/`.
- `claim_evidence_ledger.csv`, `reference-audit.csv`: evidence and interpretation records.

## Root interface

The original checker checks each root with exact `type(r) is int` and range checks before set conversion. Tests cover both orders of [0,False] and [0,0.0], list/tuple containers, a single legal integer, duplicate integers, and 128/129-entry limits. Sets preconstructed by the caller may have already discarded equal differently typed elements; that absent history is unrecoverable. The new Python producer has the same strict-before-normalization discipline; its accepted wire is a primitive integer array.

## Limits and scientific status

The old abstract model still assumes complete writes and roots. The new receiver does not claim to recover them from callback observations: it controls initial publication of newly constructed private objects. Its guarantees require trusted JDK/configuration/code and no privileged mutation of private storage. Public navigation is read-only; untrusted same-package, reflective, native, Unsafe, agent, class-loader, and concurrent interference are not covered. The package-private snapshot, eager and failure hooks are owned tests.

The bounded publication connection is implemented and argued by hand. It does not establish an original TIFS-wide security contribution, arbitrary-JVM initialization guarantees, machine-checked source correctness, production compatibility, or independent external validation. Code separation and the retained internal checks belong to one research execution.
