# Research-lock review and repair record

## Decision

**Selected route: negative result / internal technical report.**

The preserved bounded checker remains a valid finite result under its explicit assumptions, but the current project does not establish a new deserialization-specific TIFS contribution, a refinement from general Java/JVM traces to the certificate model, or a production enforcement mechanism. Adding references, pages, enumeration cases, or a stronger title would not change that conclusion.

The report therefore asks a narrower executed question: which ordinary `ObjectInputStream` observations can be translated without invention into the fixed `(ready,value,next)` model, and which mechanisms require a sound consumer to return `UNKNOWN`?

## Why a positive research lock was not accepted

1. **Dependency monitoring is prior work.** InvCOP already tracks locations read by object invariants and rechecks dependent objects after state changes under explicit observation assumptions. The current read frontier is a bounded adaptation, not a new general monitoring principle.
2. **Partial initialization disciplines are prior work.** Masked types model partial field initialization and cyclic structures, while secure-object-initialization work gives a formal Java-oriented discipline. The single abstract `ready` bit is weaker and carries no constructor provenance.
3. **Certification is prior work.** Certifying algorithms already separate an untrusted computation from a checker, including stateful/reactive settings. Code-path separation here is useful assurance but not a new certification paradigm.
4. **Runtime initialization enforcement is prior work.** MUSTI monitors constructor-chain initialization behavior. The current Java harness is passive and does not intercept field writes, constructor chains, callback publication, or returned roots before effects occur.
5. **Deserialization callbacks and object construction are active prior areas.** Seneca models hidden deserialization callbacks for call-graph analysis; Sayar et al., ODDFuzz, GCMiner, and JDD study gadget paths and object construction. These works do not prove this fixed invariant property, but they prevent callback/object-generation complexity from being presented as unexplored.
6. **The missing refinement premise failed executed controls.** Actual `ObjectInputStream` cases exhibit cyclic callback order, early external publication, identity substitution, class-evolution provenance, out-of-model values, incomplete field-write observation, and failure side effects. A passive final snapshot cannot reconstruct all of those histories.

## Concrete Java model actually executed

The harness uses ordinary Java serialization on locally authored `Serializable` classes. The recorded run used Debian OpenJDK 21.0.11 and `javac` 21.0.11. It accepts no external serialized input, performs no network access, and uses no reflection, native code, GPU, model API, private data, or third-party target.

Recorded observations are limited to:

- owned `readObject` entry/exit and post-`defaultReadObject` facts;
- a transient owned callback-completion marker;
- a static early-publication slot owned by the fixture;
- `readResolve` identity substitution;
- an enabled `resolveObject` override's object-level callbacks;
- returned root, exception, final owned snapshot, and identity facts; and
- a two-version class-evolution case using `GetField.defaulted`.

The harness does not expose a complete JVM field-write stream, all external aliases, concurrent publication, arbitrary class-loader effects, native/unsafe writes, or a pre-write enforcement point.

## Concrete-to-abstract binding

`src/java_trace_bridge.py` is independent of the producer, production checker, and dense oracle. It returns `MAPPED` only when all of the following hold:

- deserialization returned normally;
- none of the named unsupported features occurred;
- a complete owned final snapshot with exactly three integer fields per modeled object is present;
- each field is inside the fixed domain;
- every root is an exact in-range Python integer before deduplication;
- identity and `next` aliases are represented by snapshot indices; and
- `ready` provenance is exactly the owned fixture's `readObject` callback-exit marker.

Under the additional completeness and identity assumptions written in `proofs/concrete-bridge.md`, copying this snapshot preserves evaluation of the same fixed predicate. This is a conditional structural-encoding proposition. It is **not** a theorem that arbitrary Java histories satisfy those assumptions.

The bridge returns `UNKNOWN` for:

- early external escape;
- `readResolve` substitution;
- missing-field provenance;
- type/shape mismatch;
- callback observation of an unfinished peer;
- public-hook field-write coverage gaps;
- failure after an external escape; or
- any malformed, exceptional, incomplete, or unsupported observation.

## Executed cases and result

The bridge runner executes ten main harness cases plus one class-evolution case. The recorded result is:

| Outcome | Count |
|---|---:|
| Java cases | 11 |
| `MAPPED` | 3 |
| `UNKNOWN` | 8 |
| mapped safe / unsafe | 2 / 1 |
| serializable-fixture constructors invoked during reading | 0 |
| bridge unit tests | 5 passed |

Named negative controls all occurred as expected: shared alias preservation, unfinished cyclic peer, early escape, `readResolve` canonical substitution, type/shape mismatch, zero individual field-write events from the tested public hook, closed failure, failure after escape, and a missing field reported by `GetField.defaulted`.

One callback publishes `this` and then throws. The external alias remains observable after `ObjectInputStream.readObject` fails. This is direct evidence that an exception is not a general rollback mechanism for arbitrary callback side effects.

## Root-admission repair

`src/checker.py` now validates every supplied root with `type(r) is int` and `0 <= r < n` before `frozenset` conversion. This prevents Python's equality and hash compatibility among `0`, `False`, and `0.0` from hiding an invalid element.

The directed regression covers both list and tuple containers, both orders of each equal mixed-type pair, a legal single root, legal duplicate exact integers, 128 repeated integers, and 129 supplied entries. The result is:

- eight mixed list/tuple permutations: reject;
- `[0]`: accept;
- `[0,0]` and `(0,0)`: accept and normalize to `{0}`;
- 128 entries: accept;
- 129 entries: reject.

A `set` or `frozenset` constructed by a caller before the API call may already have lost an equal mixed-type value; the checker cannot reconstruct an element that no longer exists in its input container. Existing set/frozenset support is retained with that explicit interface limitation.

## Production/reference separation

- `src/producer.py`: untrusted certificate producer using traversal and read recording;
- `src/checker.py`: stateful production checker with its own closure and explicit predicate cases;
- `src/oracle.py`: independently coded dense transitive-closure oracle;
- `src/witness.py`: whole-path witness logic and separate bounded oracle comparison;
- `src/java_trace_bridge.py`: independent fail-closed Java-observation translator.

The bridge imports none of the producer, checker, or oracle. The runner invokes the dense oracle and checker only after a snapshot has been mapped. This is separation inside one AI-assisted research execution; it is not independent external validation.

## Commands and recorded exits

Preserved finite campaign replay:

```sh
python3 reproduce.py \
  --out <fresh-empty-directory>/legacy-output \
  --verify-against results/campaign
```

Recorded exit: `0`. Result: seven scientific JSON files `MATCH` under the documented semantic comparison and five deterministic files `MATCH` byte-for-byte. The finite counts remain 615,984 candidates with zero frontier/oracle and checker/oracle disagreement.

Concrete Java boundary study:

```sh
python3 reproduce_trace_bridge.py \
  --out <fresh-empty-directory>/bridge-output
```

Recorded exit: `0`. Result: 11 cases, three `MAPPED`, eight `UNKNOWN`, and five passing bridge tests.

Paper build:

```sh
cd paper
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

Recorded exits: `0`, `0`. The resulting PDF is five pages. No overfull box, unresolved citation, undefined reference, or missing figure remains; all fonts are embedded.

The clean-extraction record normalizes only the environment-specific temporary output path; executable names and all scientific arguments are preserved. Portable reproduction commands are in `README.md`.

## Main-paper / proof / code / test / result correspondence

| Paper claim | Proof or boundary statement | Code/test | Raw evidence |
|---|---|---|---|
| Last-read agreement | `proofs/argument.md`, Lemma 1 | explicit evaluator cases in producer/checker | directed tests and exhaustive campaign |
| Sufficient frontier | `proofs/argument.md`, Theorem 1 | producer, checker, dense oracle | `results/campaign/exhaustive-*.json` |
| Conditional checker correctness | `proofs/argument.md`, Theorem 2 | checker plus malformed-certificate tests | unit log and exhaustive results |
| Root admission before deduplication | interface argument in this record | checker and both test suites | `results/final-replay/root-validation.json` |
| Partial Java snapshot encoding | `proofs/concrete-bridge.md` | independent bridge | `results/bridge-campaign/bridge-results.json` |
| Java mechanisms forcing `UNKNOWN` | concrete boundary analysis | Java harness and class-evolution fixture | `java-traces.jsonl` and evolution observation |
| Replay statement | environment/provenance rule | both reproduction runners | environment, commands, and comparison JSON |
| Negative research-lock decision | closest-work and missing-refinement analysis | absence of an enforcement mechanism plus executed controls | plan, this review, bridge summary |

The complete row-level claim mapping is in `claim_evidence_ledger.csv`.

## Unresolved issues and effect on conclusions

1. **No complete concrete trace.** The artifact does not observe every field write, root retention, callback side effect, substitution, validation event, or concurrent publication. Effect: no general concrete-to-abstract soundness theorem.
2. **No enforcement point.** It cannot block a JVM write or revoke an escaped alias. Effect: no production deserialization-defense claim.
3. **No constructor provenance.** `ready` is an owned callback marker only. Effect: no constructor-history or JVM-initialization attestation.
4. **No general Java semantics.** Records, all `Externalizable` behavior, arbitrary reflection, `Unsafe`, native code, custom loaders, concurrency, and independent applications remain outside evidence. Effect: limited external validity.
5. **No machine-checked general proof.** The arguments are handwritten, with finite executable checks. Effect: the theorem is conditional and not mechanized.
6. **No independent reproduction or peer review.** All code separation, tests, and review occurred inside one AI-assisted research execution. Effect: no claim of independent validation.
7. **No positive originality lock.** The closest-work delta does not justify a new TIFS defense, and the required JVM refinement is absent. Effect: current status remains an internal negative-result technical report, not submission-ready original research.

## Honest next positive route

A future positive project would need a real pre-write/pre-publication enforcement surface (for example, justified bytecode/JVM instrumentation), a complete observation contract for modeled writes and retained aliases, semantics for substitution/evolution/validation/failure/concurrency or enforceable exclusions, and a refinement proof from those concrete events to the abstract gate. It would then need independent application evidence and comparison with the strongest relevant implementations. None of those obligations is marked complete here.
