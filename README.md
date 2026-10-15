# InitRead

InitRead studies invariant checking during incremental object initialization.
The artifact contains a finite graph checker, a passive Java observation bridge,
and a callback-free receiver for a fixed primitive-array protocol. These are
three distinct execution paths: a final snapshot does not establish the event
history required by the finite checker.

## Requirements and quick checks

Use Python 3.9 or later. Python checks use the standard library. Native receiver
checks additionally require a locally installed JDK 17 or later; nothing is
downloaded by the runners. Full resource-accounted campaigns require POSIX.

From this directory:

```sh
python3 -B -m unittest discover -s portability_tests -v
python3 -B -m unittest discover -s receiver_tests -v
python3 -B -m unittest discover -s bridge_tests -v
```

Runners require a fresh output directory. Put it outside the project so retained
inputs and results remain unchanged. Set `PYTHONDONTWRITEBYTECODE=1` for child
Python processes when invoking individual tools outside the campaign drivers.

## Reproduce correctness

The portable route regenerates the finite Python campaign and integer inputs,
checks independent certificate/data references, and reinterprets the retained
passive observations. It does not execute a JVM or measure Java performance:

```sh
python3 -B reproduce_portable.py --out /absolute/fresh/python-scope
```

For current native correctness, supply a local JDK directory, or omit
`--java-home` when `JAVA_HOME` or `PATH` already identifies it:

```sh
python3 -B reproduce_java_conformance.py \
  --java-home /absolute/local/jdk --out /absolute/fresh/java-correctness
```

This route compiles the owned receivers/harnesses with `--release 17 -proc:none`,
runs 4,563 serialized receiver cases, 5,248 integer packets and 31,488 six-mode
observations, and checks 5,236 complete data prefixes through public navigation.
The seventeen current receiver tests include the six named complete-prefix
regressions in `inputs/data-prefix-regressions.json`. Outputs include generated
inputs, observations, comparisons, environment information and source bindings.

Individual POSIX campaigns remain available when their specific outputs are
needed. These commands skip optional timing forks:

```sh
python3 -B reproduce.py --out /absolute/fresh/finite --verify-against results/campaign
python3 -B reproduce_trace_bridge.py --out /absolute/fresh/passive-java
python3 -B reproduce_receiver.py --out /absolute/fresh/receiver \
  --verify-against results/receiver-campaign --skip-benchmark
python3 -B reproduce_specialization.py --out /absolute/fresh/specialization \
  --verify-against results/specialization-campaign --skip-benchmark
python3 -B reproduce_public_boundary.py --java-home /absolute/local/jdk \
  --out /absolute/fresh/public-navigation --skip-costs
```

Replay compares deterministic scientific outputs and the complete saved input
set. Timing and resource telemetry use their documented comparison exclusions.
The receiver comparison preserves exact input words while recording the named
`cert-short-009` data-oracle label correction; other differences fail. Canonical
JSON comparisons distinguish integer, Boolean and floating-point values.
Failures exit nonzero and leave diagnostics in the fresh output directory.

## Results and interpretation

| Evidence | Retained result | Location |
|---|---|---|
| Finite census | 615,984 transitions; zero checker/oracle disagreements | `results/campaign/` |
| Passive Java bridge | 11 cases: 3 mapped final snapshots, 8 unknown histories | `results/bridge-campaign/` |
| Native receiver | 4,563 cases; zero recorded decision/representation/alias discrepancies | `results/receiver-campaign/`, `results/native-replay/` |
| Integer specialization | 5,248 packets; agreement with the independent certificate reference | `results/specialization-campaign/` |
| Current public navigation | 5,236 complete-data packets; 15,708 observations | `results/public-navigation/` |

The receiver accepts a canonical serialized `int[]` encoding a fixed
`(ready,value,next)` graph of at most 128 nodes. Readiness, checking order and
publication are receiver-owned. Successful results expose a frozen graph.
Complete valid certificates and direct eager checking admit the same final data;
the measured certificate path was slower than eager checking. `DENY_UNSAFE`
reports a checked unsafe prefix rather than authenticating an unconsumed tail.

Timing is opt-in: omit `--skip-benchmark` for the receiver or specialization
campaign, or omit `--skip-costs` for the public-boundary campaign. The retained
Linux generic/specialized measurements precede the current matched buffer
preallocation and are not measurements of that later allocation change.
Pilot, interrupted and framing-control runs retain their own records and are
not pooled with complete campaigns. Windows Java replays are correctness checks.
Actual environments are recorded per run; missing historical machine facts are
not inferred from later runs.

## Code, proofs and tables

- `src/`: finite model, producer, checker, dense oracle and passive bridge.
- `receiver/`: packet producer and separate integer-data/certificate references;
  its README and specialization contract describe the wire and checking rules.
- `java/`, `baselines/`: owned native receivers, observation harnesses and the
  matched generic baseline.
- `proofs/`: finite, bridge, receiver and specialization arguments.
- `inputs/`: named data, root-type and complete-prefix controls.
- `claim_evidence_ledger.csv`, `reference-audit.csv`: claim and source locations.

Generate manuscript tables from the relevant retained campaign, without
requiring the paper directory:

```sh
python3 -B export_paper_data.py --results results/campaign --out /absolute/fresh/finite-tables
python3 -B export_receiver_data.py --results results/receiver-campaign --out /absolute/fresh/receiver-tables
python3 -B export_specialization_data.py --results results/specialization-campaign --out /absolute/fresh/specialization-tables
```

The receiver protocol is callback-free rather than a general replacement for
Java object deserialization. Its proof conditions include trusted receiver/JDK
configuration, protected checker state and the documented input/publication
boundary. The passive bridge deliberately returns unknown when those event
premises cannot be recovered. See the corresponding proof and experiment
contracts for the exact conditions of each path.
