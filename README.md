# Initialization-State Safety: bounded checker and Java observation-gap study

This repository contains two related but deliberately separated artifacts:

1. a finite object-graph invariant checker with an untrusted certificate producer,
   a separately implemented stateful checker, an exact dense oracle, and ordered
   witness fixtures; and
2. a CPU-only Java harness that executes ordinary `ObjectInputStream`
   deserialization on locally authored classes and asks when those passive
   observations can be translated into the bounded model.

**Scientific status:** negative-result technical report and research checkpoint.
The finite checker result is supported in its declared domain.  The Java study
shows that only a narrow class of owned final snapshots can be mapped; special
callbacks, early publication, missing fields, type/shape mismatch, failure side
effects, and incomplete write observation return `UNKNOWN`.  This is not a
production deserialization defense, constructor-history attestation, JVM proof,
or established TIFS original-research contribution.

## Requirements

- Linux;
- Python 3.9 or newer, standard library only; and
- a local JDK providing `java` and `javac`.

Python 3.9 is the minimum because runtime-evaluated built-in generic aliases
such as `tuple[...]` and `set[...]` occur in the source.  Neither runner uses a
network service, model API, GPU, private data, external serialized payload, or
third-party application.  Both use one worker and sequential Java children.

## Reproduce the preserved finite campaign

From this repository root:

```sh
python3 reproduce.py \
  --out replay-output \
  --verify-against results/campaign
```

`replay-output` must not exist or must be empty.  Exit code 0 means the tests,
experiments, and recorded comparisons completed; it does not prove general
correctness or novelty.  The comparison covers seven scientific JSON files
semantically after excluding timing/RSS fields and five deterministic files by
exact bytes.  It writes the per-file report before failing on a mismatch.

The latest clean run recorded Debian GNU/Linux 13 on amd64, CPython 3.13.5,
and Debian OpenJDK/javac 21.0.11.  It exited 0, matched all seven scientific
JSON files and all five deterministic files, and retained the original
canonical files unchanged.  The canonical run did not record its architecture
or exact Python/JDK versions; those historical fields remain unknown and are
not filled from the later machine.

### Preserved finite results

| Quantity | Result |
|---|---:|
| Two-/three-object heap/root states | 33,344 |
| Safe admitted pre-states | 10,438 |
| Changing-write/root-addition candidates | 615,984 |
| Frontier/dense-oracle disagreements | 0 |
| Checker/dense-oracle disagreements | 0 |
| Unsafe candidates accepted by written-object control | 4,296 |
| Directed test methods | 17 passed |
| Malformed certificates rejected without semantic commit | 18 |
| Ordered failing witnesses agreeing with a whole-path oracle | 5 |
| Passive owned Java round trips / callback snapshots | 24 / 66 |

The exact object domain is 1--128 fixed records `(ready,value,next)`, with bit
fields `ready` and `value` and one nullable reference.  The fixed predicate is:

```text
ready(o) and (next(o) is null or value(o) <= value(next(o)))
```

The `ready` bit is abstract metadata.  It is not a constructor-chain record or
JVM initialization proof.

## Run the concrete Java observation-gap study

```sh
python3 reproduce_trace_bridge.py --out bridge-output
```

`bridge-output` must not exist or must be empty.  The runner compiles and runs
ordinary in-memory Java serialization cases, including one two-version class
evolution fixture.  It records the actual operating system, architecture,
Python, Java/JDK, `javac`, JVM options, and a digest of executed code and inputs.
It then runs the independent bridge tests.

The recorded run used Debian GNU/Linux 13 amd64, CPython 3.13.5, and Debian
OpenJDK/javac 21.0.11 and exited 0.  Results were:

| Outcome | Count |
|---|---:|
| Executed Java cases | 11 |
| Narrow final snapshots mapped | 3 |
| Conservatively returned `UNKNOWN` | 8 |
| Mapped safe / unsafe | 2 / 1 |
| Serializable-fixture constructor calls during reading | 0 |
| Bridge unit tests | 5 passed |

The nine named negative-control facts all occurred as expected: alias identity
was preserved; a cyclic callback observed an unfinished peer; an owned callback
published `this` early; `readResolve` returned a pre-existing canonical object;
a type/shape mismatch was observed; public callbacks did not provide individual
field-write events; closed failure left no external alias; failure after escape
did leave one; and class evolution produced a missing field reported by
`GetField.defaulted`.

`src/java_trace_bridge.py` is independent of the producer, production checker,
and dense oracle.  It checks every supplied root's exact type and range before
deduplication.  Both `[0, False]` orderings, both `[0, 0.0]` orderings, and their
tuple counterparts return `UNKNOWN`; `[0]` and duplicate integer roots remain
valid subject to the 128-entry input bound.

The bridge is intentionally partial.  `MAPPED` means only that a final owned
snapshot met the narrow encoding discipline.  Its `ready` bit means “the owned
fixture's `readObject` callback set its marker before exit.”  It does not mean
that a constructor ran or that all concrete writes and aliases were observed.
See `proofs/concrete-bridge.md`.

## Files and evidence

- `src/checker.py`: production stateful checker;
- `src/producer.py`: untrusted certificate producer;
- `src/oracle.py`: independent dense finite oracle;
- `src/java_trace_bridge.py`: independent fail-closed observation translator;
- `java/BenignGraphs.java`: preserved passive round-trip campaign;
- `java/DeserializationTraceHarness.java`: callback/alias/failure harness;
- `java/evolution/`: two-version missing-field fixture;
- `proofs/argument.md`: bounded mathematical argument;
- `proofs/concrete-bridge.md`: exact partial Java-to-abstract binding and limits;
- `research-lock-review.md`: route decision, repair record, commands, and unresolved obligations;
- `results/campaign/`: preserved canonical finite campaign;
- `results/bridge-campaign/`: recorded Java bridge run;
- `results/final-replay/`: current recorded-environment finite replay;
- `results/clean-extraction-check.json`: portable clean-extraction command/exit summary;
- `claim_evidence_ledger.csv`: claim-to-evidence mapping; and
- `external_resources.csv`: source and tool provenance.

## Scope and non-claims

The finite checker assumes authentic complete events, complete retained roots,
protected checker state, and an atomic abstract commit gate.  The Java harness
provides passive observations only and does not implement that gate.  The work
does not cover native code, `Unsafe`, arbitrary reflection, arbitrary class
loaders, multithreaded publication, all class-evolution behavior, all
`Externalizable`/record semantics, or production compatibility.  A successful
command is evidence that the specified finite run completed, not an independent
review or a guarantee of external submission readiness.
