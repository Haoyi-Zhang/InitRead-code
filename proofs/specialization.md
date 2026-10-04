# Exact specialization of the bounded receiving schedule

These are handwritten source-level arguments for the existing fixed integer protocol. They neither mechanize Java nor establish a new general certifying-algorithm principle. The data, threat model, canonical stream, receiving API, and representation relation are exactly those in `receiver.md`. No application callback, predicate, object-domain dimension, or public mutator is added.

## S1. What the optimized state represents

Let D=(V,T,L), n=|V|, m=|L|. Preparation writes V, then T, then readiness=1 while the root set is empty. Afterwards the only abstract operations are same-value readiness assignments and root additions in L order. Let R_j be the set of the first j requested roots, K_j their successor closure in the final data, and K_0 be empty.

For a root r=L_j, the generic dependency frontier is exactly

    A_j = K_j \ K_(j-1), if r is not in K_(j-1);
    A_j = {r},             if r is in K_(j-1).

To justify the second case, the fixed predicate reads its own readiness, its own link and (on the non-null branch) its own value and its successor's value. It does NOT read its successor's readiness. Thus an idempotent write to r.ready affects only the predicate at r among already reachable nodes. To justify the first case, r was not previously reachable, so no old predicate reads r.ready. All new obligations are precisely newly reachable nodes. Walking T from a new root until null or an already marked identity finds exactly this difference, including cycles. Existing marked nodes are closed under T, so stopping at one cannot hide a new suffix.

The specialized State holds D and a BitSet for K_j. It does not physically replay preparatory heap assignments. This is a representation change of private validation state, NOT evidence that a JVM write was observed or skipped.

## S2. Observational equivalence of the two verifiers

**Theorem S2.** Fix a copied frame, normal trusted runtime operation, and the same receiving configuration. The original generic receiver and the specialized receiver have equal status, reason, diagnostic trace, checked-step count, and inspected-read count. On acceptance their graph snapshots and root sequences agree, with the same within-graph alias relation. The statement compares value observations, not reference equality across two different invocations.

*Proof.* Frame decoding, data parsing, schedule reconstruction, input caps, cursor checks, graph construction, and public result creation are unchanged. It suffices to compare State.step.

During preparation the generic root set, reachable set, and frontier are empty regardless of preparatory field values. Its exact expected certificate words are (0,0,1), followed by the same counter update and diagnostic. The specialized state expects those identical words in the same order. If a word is absent or wrong, the two cursors reject at the same position with the same reason and counters.

After preparation every field has its final value. Assume both paths have accepted the first j-1 root steps. Their reachable representations agree by S1. On step j, S1 identifies equal reachable and frontier sets. Both enumerate identities in increasing order. For each frontier identity, the same null/non-null branch determines the same Boolean, read count and ordered triples. Both compare these integers in the same order and update the read counter only after that obligation has been fully checked. They then compare the same decision word, increment the step counter at the same point, and append the same scalar trace. This proves equality both on a malformed certificate prefix and on a fully checked step. A validated unsafe step terminates both invocations with the same denial. An accepted step re-establishes the induction hypothesis. Final step-count and cursor-end checks are unchanged.

The specialized live mask may be updated before an invalid current certificate is discovered. That state is private to this terminating invocation, cannot be reused by a caller, and is never published as a graph. Therefore no rollback claim about public state is needed. Normal acceptance reaches the unchanged private constructor; its cloned data and canonical node wrappers establish the same representation. □

This reasoning assumes source-to-specification correspondence and ordinary execution, not arbitrary resource failures or hostile runtime mutation. It is supported, not replaced, by the independent oracle and the retained generic implementation.

## S3. Denial does not authenticate an unconsumed tail

The receiving interface distinguishes a checked unsafe prefix from complete certificate acceptance. On a fully validated first unsafe step, it returns DENY_UNSAFE immediately. Supplied later steps and suffix words are not consumed. A safe full packet requires the exact planned step count and end of cursor. Thus a denial is evidence that this data cannot safely publish the requested root encountered so far; it is not a statement that all remaining certificate words form a canonical proof.

The independent oracle implements this same grammar. Tests append a tail to an already denied packet and require DENY_UNSAFE, while appending to an accepting packet requires INVALID_CERT. Tightening denial-tail validation would change diagnostics and is not smuggled into an optimization. Neither outcome publishes a graph.

## S4. Sharp maximum size of an honest accepting packet

Let W(n,m) count all integer words, including the data header, step count and proof. For fixed n,m the maximum over safe data and its honest deterministic proof is

    W(n,0) = 5 + 11n;
    W(n,m) = nm + 26n + 19m - 10, for m >= 1.

*Proof.* The header and step count use 5+2n+m words. The 3n preparatory certificates use 9n. If k_j is the root-step closure size, the root-step overhead apart from predicate entries is k_j+3. Each obligation occupies 3 header words and either 6 or 12 read words, hence at most 15. Therefore the total is

    5 + 11n + 4m + sum_j k_j + sum_(obligations) entry_length.

For m=0 this is exactly 5+11n. For m>=1, sum k_j <= nm. Each node is newly reachable at most once, giving at most n new obligations. A root step can add at most one already-reachable obligation, but the first root cannot already be reachable because K_0 is empty. Therefore there are at most n+m-1 obligations. Substitution gives the stated maximum.

It is attained by n all-one nodes in a directed cycle and m repetitions of root 0 (a self-loop when n=1). The first exposure discovers all n nodes, every read has length four, and each later repeated root rechecks exactly that root. Each closure has size n. Thus every upper-bound inequality is an equality. □

At n=m=128 the maximum is exactly 22,134 words. Under the fresh default ObjectOutputStream integer-array encoding described in `receiver.md`, this is 27+4*22,134=88,563 bytes. The prior 22,149-word upper bound remains valid but was not sharp; historical results are not edited. Thirty n/m combinations execute the attaining construction and compare the formula to both packet words and actual Java serialized length.

## S5. What must be inspected, and what can be erased

**Lemma S5 (fixed-format exact checking).** Fix safe data D. Consider a deterministic validator of its canonical accepting integer proof, with no trusted preprocessing digest, in a word-probe model. On the accepting input it must inspect every certificate word, including the step-count word.

*Proof.* The schedule, closures, frontier ordering, predicate results, read triples and decision words are determined by D. Hence precisely one complete integer proof is accepted for D in this schema. Suppose an accepting run does not inspect position q. Change that integer to another signed 32-bit value without changing the length or any inspected position. The validator follows the same deterministic execution and accepts, but the proof is no longer the unique canonical proof. This contradicts exact validation. □

This elementary argument concerns exact recognition of this redundant format. It is NOT a lower bound on deciding the invariant, on authenticated or randomized validation, or on other certificate encodings. The eager data gate is explicitly allowed to erase the proof: it computes the same safety predicate from data and therefore does not satisfy the stronger exact-proof language requirement.

The specialization removes per-step whole-heap clones. At the declared 128-node limit its live and needed masks use at most two 64-bit words each. It discovers each node at most once, checks each preparatory triple directly, and enumerates every expected serialized closure/obligation entry once. The retained format still writes a whole reachable list at each root step, so m repeated roots in an n-cycle cause nm closure words. A linear-in-serialized-input scan cannot erase this wire cost without changing the contract. No JVM-level optimality, new compression scheme, or measured complexity law is asserted.

## S6. Independent evidence and assumptions removed

`receiver/certificate_reference.py` imports no module. It parses raw integers independently, reconstructs every whole heap, recomputes reachability to a set fixed point, recomputes old read transcripts, builds the declarative expected proof, and checks consumed words. It does not call the producer, Java parser, specialized State or a production decision function. It is a specification oracle for integer packets, not an independent Java stream decoder or a machine proof. The older data-only oracle remains separate.

The generic Java baseline is the incoming verifier with only its class name changed. Differential observations include rejection reasons, scalar traces and counters as well as final classifications. Both implementations share ancestor code outside State; that comparison alone is not independent truth. The whole-state Python oracle supplies a third algorithmic path within the same research execution, not an external reviewer.

The new corpus retains 4,552 old integer packets unchanged, adds five safe seeds, changes each of 328 certificate cells, truncates at the same 328 positions, adds five certificate tails, and executes 30 sharp-bound cases. These are 5,248 cases, not 5,248 independent applications. One-word controls test every certificate position in the five named seeds only; they do not constitute exhaustive malformed inputs across the entire domain.

Remove root-free preparation: a transient reachable unready object can no longer be summarized by (0,0,1). Permit value/link changes after root additions: a successor value can affect an already reachable predecessor, contradicting A_j. Let predicates read other nodes' readiness: the singleton old-root recheck is insufficient. Expose an internal graph before completion or add a public mutator: the original publication/persistence proof no longer applies. These are boundaries of the specialization, not supported extensions.

## S7. Research interpretation

S1-S5 finish the stated algorithmic optimization and size/format arguments. They do not establish a new invariant-monitoring paradigm. Program specialization, dynamic read dependencies and separate checking are existing ideas. Equal accepted data languages and the faster direct baseline remain explicit. A stronger original-security contribution, arbitrary Serializable support, machine-verified source and independent production evidence remain unestablished.
