# Bounded read-certificate argument

## Status and attribution

These are handwritten arguments about the mathematical algorithms below. They are not a machine-checked general proof of the Python implementation and do not establish a refinement from a production JVM. Dynamic last-read dependencies and their preservation argument are established ideas: see Gopinathan and Rajamani, *Runtime Monitoring of Object Invariants with Guarantee*, RV 2008, Theorem 1 and the dependency-tracking construction, DOI 10.1007/978-3-540-89247-2_10. Separately checking a producer's output, including stateful checking, is also established; see McConnell et al., *Certifying Algorithms*, Computer Science Review 5(2), 2011, Sections 1 and 12, DOI 10.1016/j.cosrev.2010.09.009. No originality claim is made for the following adaptations.

## Definitions

Fix an object domain O={0,...,n-1}, 1<=n<=128. A well-formed heap H maps each object to (ready,value,next). The first two fields are bits; next is null (-1) or an element of O. All object identities are allocated before admission and remain allocated; events never allocate or reclaim objects. A root set B is a subset of O. R(H,B) is the least set containing B and closed under non-null next edges.

B represents all retained external references. Its accuracy is an assumption, not something certified by an invariant transcript. A client retaining a reference must be represented by a root-addition event even when that object is already reachable. Removing a heap edge does not remove such a root. The abstract model has no root removal or garbage collection.

The fixed declared predicate is

    P_H(o) = (H[o].ready = 1) and
             (H[o].next = null or H[o].value <= H[H[o].next].value).

The safety predicate is S(H,B) = conjunction over o in R(H,B) of P_H(o). It is vacuously true for an empty root set, even if privately held objects are not ready. The ready field is supplied abstract metadata. It is not a proof that a Java constructor ran, returned normally, or established any unmodeled semantic property.

Evaluation is deterministic and short-circuiting: read ready; on zero return false; otherwise read next; on null return true; otherwise read the object's value and the target's value, in that order, and compare. Reads include repeated locations: a self-loop records the value field twice. L_H(o) is the ordered sequence of (object,field,value) reads. D_H(o) is its projection to a set of locations.

An event e=(i,f,v,a) proposes a single well-typed field assignment H[i,f]:=v and, if a is not -1, adds a to B. Both operations form one abstract atomic candidate. Values may be unchanged. Let (H',B') be the candidate, R=R(H,B), R'=R(H',B'), and delta=(i,f). The untrusted producer receives the previously accepted state and read transcripts. The checker retains its own copy of that state and transcripts.

A semantic checker state is (H,B,C), where C has exactly the keys R and C[o]=L_H(o), with every cached evaluation true. A separate diagnostic step counter is not part of this semantic state. The invariant policy and the checker state are assumed immutable to the certificate producer. The prototype separates code paths but does not implement process or memory isolation.

## Lemma 1: agreement on the last read set

If H and K are well-formed over the same object domain and agree on every location in D_H(o), evaluating P at o in K produces exactly the same result and ordered transcript as in H.

Proof. The initial ready read is in D_H(o), so both evaluations see the same bit. If it is zero, both terminate with the same one-entry transcript. Otherwise both read next, which is also in D_H(o). If it is null, both terminate with the same two-entry transcript. Otherwise its identical value selects the same valid target in both heaps. The two value locations read next belong to D_H(o); therefore both values and their comparison coincide. A self-alias merely repeats an already equal location. These cases exhaust the evaluator. No purity, determinism, termination, or alias property of an arbitrary Java method is inferred from this proof. QED.

## Theorem 1: sufficient revalidation frontier

Assume S(H,B). Define

    Q = (R' \ R) union {o in R' intersect R : delta in D_H(o)}.

Then S(H',B') holds if and only if P_H'(o) holds for every o in Q.

Proof. Necessity follows from Q being a subset of R'. For sufficiency, take an arbitrary o in R'. If o is in Q, its predicate holds by the premise. Otherwise it was already in R and delta is not in D_H(o). The heaps differ at no location except possibly delta, so they agree on D_H(o). Lemma 1 preserves the old true predicate at o. This covers all of R'. Objects that cease to be reachable impose no obligation under this particular root model. An externally retained alias must already be in B, so an edge deletion cannot hide it when the root assumption holds. QED.

This is a sufficient dependency frontier, not a minimum semantic revalidation set. An assignment of the same value may put objects in Q without changing their evaluations. A self-reference can cause both sides of a tautological comparison to be invalidated. Other invariants may be logically implied by the global contract.

## Theorem 2: checker decisions and cache preservation

Assume a well-formed safely admitted state satisfying the cache invariant, an authentic well-typed event, a fixed policy, protected checker memory, and atomic enforcement of the checker's commit decision. The specified checker:

1. recomputes H', B', and the exact R';
2. requires the certificate to name R' in sorted order without omissions or duplicates;
3. independently computes Q from its old cache;
4. requires exactly one entry, in object order, for every member of Q;
5. re-evaluates the fixed predicate for each entry and compares the full ordered transcript and Boolean result;
6. requires the claimed decision to be ALLOW exactly when all those results are true, otherwise DENY_UNSAFE.

Every accepted ALLOW yields a safe committed state and preserves the cache invariant. Every accepted DENY_UNSAFE correctly identifies an unsafe candidate and leaves the semantic state unchanged. Every safely formed candidate has an honestly generated certificate accepted as ALLOW, and every unsafe well-formed candidate has one accepted as DENY_UNSAFE. A malformed certificate is INVALID_CERT, not a claim that its candidate is unsafe.

Proof. Admission checks S directly and constructs the exact true transcripts, establishing the induction base. Schema and coverage validation force the candidate closure and Q to be the checker's independently obtained sets. Transcript validation forces every asserted result to equal the predicate's actual candidate evaluation. If all results are true, Theorem 1 establishes candidate safety. The updated cache keeps re-evaluated transcripts on Q and retains old transcripts on R'\Q. Lemma 1 shows that the latter are still exact, including order and values. Keys outside R' are discarded. Thus the cache invariant holds after commit. If any checked result is false, that member of Q belongs to R' and witnesses candidate unsafety. Denial and invalid-certificate paths perform no assignment to H, B, or C. The diagnostic counter may change. Finally, evaluating the specified policy on every required member and emitting the exact closure gives a certificate meeting every check, for either decision. Induction extends the argument to any finite sequence of accepted proposals. QED.

The result is relative completeness for this fixed predicate and abstract transition relation. It is not completeness for Java bytecode, constructor/factory contracts, deserializer callbacks, arbitrary invariant programs, or a faulty event observer. Resource exhaustion is UNKNOWN, not safety. There is no theorem that the checker is faster than directly evaluating all reachable predicates.

## Proposition 1: a retained alias cannot be silently discarded

Let H[0]=(1,0,1), H[1]=(1,0,null), B={0}. If a client retains object 1, then cuts 0.next and proposes 1.ready:=0, the last candidate is unsafe for B={0,1}. Omitting the retention from the observed roots makes the same field-write sequence appear safe for B={0}.

Proof. With B={0,1}, object 1 remains reachable after the cut and its zero ready bit makes S false. With B={0}, the cut leaves only object 0 reachable; changing the now-unreachable object does not falsify S for this different observed state. The unit fixture implements both observations and checks the difference. This is a failure of root-event coverage, not a violation of Theorem 2's premises. QED.

## Theorem 3: shortest ordered witnesses in the fixed transition systems

A witness-program state is (pc,H,B). There are finitely many program locations and finitely many well-formed heaps/root sets. Edges at each pc are ordered by distinct integer identifiers. Their four-integer events have the semantics above. All fixture edges are well-typed. A candidate that violates S is a violation; the monitor's decision is not used to prune candidate executions in this search. A diagnostic epoch increments on every edge but never affects enabling, updates, or the safety predicate.

Breadth-first search, with outgoing edges in ascending order, exact visited keys (pc,H,B), and a bad-state test before insertion, returns the shortest violating edge-identifier sequence, with lexicographically least sequence breaking length ties, if it returns VIOLATION before exhaustion. It returns SAFE only when the complete reachable semantic graph has been closed with no bad state. A node cap gives UNKNOWN.

Proof. An empty initial violation is least. Otherwise breadth-first queue order is increasing path length; within one length, expanding lexicographically ordered parents with ordered outgoing labels generates candidates in lexicographic order. The first discovery of a state therefore has the least length/lexicographic path to that state. A later path to the identical state has exactly the same available suffixes. Replacing its prefix by the first-discovery prefix cannot worsen total length or a same-length lexicographic order, so pruning that later visit cannot remove the least violating witness. A finite graph is exhausted exactly when every reachable state's outgoing candidates have been considered. The bad-state test prevents an invalid successor from being discarded by visited-state lookup. A resource cutoff does not establish closure. QED.

Deleting the diagnostic epoch from the key is valid because it is absent from all guards, updates, and observations. Deleting ready is invalid: W03 sets an unexposed object's ready bit to zero in a self-loop and then exposes it. The correct least trace is [0,1], whereas the deliberately incorrect phase-erasing search reports SAFE. Retaining an ever-increasing epoch in W04 produces UNKNOWN at 64 nodes even though the semantic graph has two safe states. The whole-path oracle searches to depth eight; for W04, its NO_WITNESS_TO_DEPTH is not independently a safety proof. Safety of W04 follows directly because no edge ever changes its initially true predicate.

The returned trace is an abstract write/exposure sequence. The certificate checker does not check a global shortest-path certificate; finite path-oracle agreement is reported for the five violating fixtures only.

## Proposition 2: indistinguishable hidden writes preclude exact certification

Suppose an observation interface admits two concrete histories with the same trusted observation and certificate input but different boundary-safety truth values. No decision procedure using only that input can simultaneously accept every safe history and reject every unsafe history.

Proof. A deterministic decision procedure returns the same result on identical inputs. Acceptance is unsound for the unsafe history; rejection is incomplete for the safe history. The same contradiction applies to a randomized procedure required to be correct with probability one. A finite witness uses two initially ready objects with 0.next=1 and both values 1. One history preserves them. The other performs an unobserved write 1.value:=0 before exposure. Object 0 satisfies the fixed predicate in the first history and violates it in the second. Protected-event coverage or a fresh trusted snapshot distinguishes these histories; a producer's unsupported assertion does not. QED.

This elementary observation limitation is not a novel impossibility theorem for all native code or reflection. Such operations can be modeled, restricted, or observed. The impossibility applies only to the specified indistinguishable-history interface.

## Proposition 3: the initial pilot predicate was logically redundant

The initial design used P_old(o)=ready(o) and value(o)=1 and (next(o)=null or value(next(o))=1). Over a root-closed reachable set R, the conjunction of P_old over R is equivalent to conjunction of ready(o) and value(o)=1 over R.

Proof. Forward implication follows by dropping conjuncts. For the converse, if o in R has a non-null successor p, closure puts p in R, and the assumed local value constraint gives value(p)=1. Hence the neighbor conjunct adds no global obligation. QED.

Its 4,968-transition two-object pilot therefore did not isolate the cross-object dependency phenomenon. The repaired relational predicate does: changing 1.value from 1 to 0 leaves P(1) true for a null successor but falsifies P(0) when 0.value=1 and 0.next=1. The original pilot is retained as a scientific negative-design control, not counted as evidence for a novel dependency algorithm.

## Finite-domain accounting

There are [4(n+1)]^n heaps and 2^n root sets. Each safe state has n(n+2)(n+1) value-changing write/optional-root-addition events: one ready alternative, one value alternative, and n next alternatives per object, times n+1 addition choices. The two-object campaign has 286 safe states and 6,864 events; the three-object campaign has 10,152 safe states and 609,120 events. Distinct labels that lead to identical post-states are counted separately. The checker also permits same-value and root-only-via-no-op events, covered by directed tests, not by the exhaustive changing-write census.

The bound of 128 objects is an admission/capacity bound, not an exhaustively checked state-space size. Even the finite representation grows exponentially; the exact census does not extend beyond n=3. All resource cutoffs must preserve UNKNOWN rather than manufacture a completed search.
