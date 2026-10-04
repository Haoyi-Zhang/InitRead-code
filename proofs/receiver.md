# Observation limits and a callback-free receiving contract

This is a handwritten argument about an explicit receiver and its finite abstract model. It is not a proof-assistant development, verification of Java bytecode, a JVM correctness proof, or a claim that arbitrary Serializable objects satisfy the contract. The inherited argument in `argument.md` is used only for the shadow transitions defined below. The passive bridge in `concrete-bridge.md` remains partial.

## 1. Data, state, and attacker

Let O = {0,...,n-1}, 1 <= n <= 128. Data d consists of bit values v[O], references p[O] in O union {-1}, and a supplied root sequence rho of length m <= 128. Every root must be a genuine integer in O before duplicates are removed. The abstract retained set B is set(rho); public root order and duplicate identity are preserved in the returned root array.

The final heap is H_d(i) = (1,v[i],p[i]). Its required property is S(H_d,B): every object in the successor closure of B has ready=1 and either no successor or v[i] <= v[p[i]]. The policy is fixed, not supplied as executable code or arbitrary annotations. Objects unreachable from B need not satisfy the relational conjunct.

The untrusted party supplies a bounded byte array containing graph data and purported certificates. It does not control receiver classes, the JDK, a class loader, agents, the process-wide filter factory, the fixed policy, or code executing in the receiver's thread. Reflective access to private storage, Unsafe, JNI, mutation by agents, VM bugs, and concurrent interference are excluded. Only public Graph/Node navigation after return is covered. The package-private eager, snapshot, and fault hooks are owned test interfaces, not adversarial code entry points.

The receiving path uses the ordinary JDK 21 ObjectInputStream mechanism, but with a deliberately different wire contract from arbitrary application serialization. A hard resolveClass override accepts only the primitive-array descriptor `[I`; proxies are rejected. An ObjectInputFilter bounds depth, reference count, array length, and bytes. Top-level null and String values, whose treatment does not necessarily call the filter, are rejected by an exact post-read class check. The byte array is cloned before reading.

After decoding the primitive array, the receiver re-encodes it through a trusted ordinary ObjectOutputStream and requires exact byte equality with the owned frame. Thus the wire language consists of one canonical primitive int[] serialization, not all semantically equivalent Java streams. This check excludes extra values, reset tokens, and incomplete trailing objects. EOFException alone is insufficient: it may denote a truncated second value rather than an empty suffix. The owned regression records this distinction.

All accepted objects decoded from the wire are JDK primitive storage, not instances of sender-selected application classes. Primitive-array re-encoding calls no sender-selected callback. The class/array/filter claims assume the documented JDK mechanisms behave correctly. They are not assurances against defects in those mechanisms or resource exhaustion.

## 2. Evidence grammar and locally determined schedule

The integer packet has:

    magic, schema=1, n, m, values[n], links[n], roots[m], step_count, certificates...

No ready bit, event order, or external-root list is accepted from a certificate. The data root sequence is an untrusted *requested* export list, not a claim that arbitrary historical JVM roots were observed. The receiver itself controls which of these requested roots become accessible.

Starting with n records (0,0,-1) and B empty, the receiver derives exactly this schedule:

1. write each value, in increasing identity order;
2. write each successor, in increasing identity order;
3. write ready=1 for every identity;
4. for each supplied root, perform the same-value ready write and add that root.

The same-value write in step 4 reuses the inherited event language without altering its semantics. A successful schedule has 3n+m <= 512 transitions. No external object is returned during this computation.

A certificate encodes the exact candidate reachable set in sorted order, the exact number of affected obligations, each obligation's identity, Boolean result and ordered value-bearing reads, and the proposed decision. All counts and cells are read using bounded integer-cursor operations. Missing, additional, changed, reordered, or inconsistent cells are rejected. A denial certificate may terminate at the first unsafe root addition; it is a witnessed denial, not successful admission. Extra words after an accepting schedule are rejected.

The Java verifier separately reconstructs the schedule, candidate heap, closure and dependency frontier. It does not execute the Python producer. The Python data reference has no imports and neither decodes nor validates the certificate suffix: it checks the data language using its own dense closure and direct relational condition. It is deliberately not described as a second certificate implementation.

## 3. Shadow-state soundness

This section describes the logical/generic shadow state. The production receiver represents it using the exact schedule specialization proved in `specialization.md`, S1-S2. It no longer physically clones each preparatory heap. The logical state and accepted language are unchanged.

**Lemma R1 (fixed-schedule cache invariant).** At every accepted step, the private shadow heap is safe for the private shadow root set, and every cached transcript for a reachable identity equals a fresh evaluation there.

*Proof.* Initially there are no roots, so safety is vacuous and the empty cache is exact. In the first 3n steps there are still no roots; there are no required transcripts. After these steps fields will no longer change, except same-value ready writes at requested roots. Root additions can only increase reachability. Every newly reachable object is checked. An old reachable object whose transcript contains the written location is checked again; any other old transcript is unchanged by the inherited last-read lemma. The verifier checks identities, field locations, values, order, results and decision against its own candidate. It commits only if every required result is true. Induction proves both assertions. No assumption about unobserved JVM field writes is used: these are the verifier's own private transitions. □

**Corollary R2 (accepted data).** If the Java certificate gate reaches CERTIFICATE_ACCEPTED, its final shadow heap equals H_d, its roots equal set(rho), and S(H_d,set(rho)) holds.

*Proof.* Schedule reconstruction fixes all field writes and root additions from independently decoded data. Exact step count and end-of-cursor checking exclude a successful partial schedule. Apply R1. □

This argument is conditional on implementation correspondence. Code review, exhaustive small inputs and negative controls test that correspondence; they do not machine-prove it.

## 4. Concrete representation and publication

A concrete Graph owns fresh private clones of v, p, and rho, and a fresh Node array. There is exactly one Node per logical identity. Each Node has a private final owner reference and private final identity. A Node's `next()` returns null or the canonical Node at p[identity]; `value()` reads the owned value; `id()` returns its logical identity. `roots()` returns a fresh array whose entries are those same canonical Nodes. Neither Graph nor Node is Serializable, extensible, or equipped with application callbacks.

Define the boundary relation J(G,H_d,rho) by equal array dimensions, equal bit values and successor indices, a bijection i -> G.nodes[i], and root-sequence equality with identity preserved. The abstract ready bit is 1 because construction of this receiver-owned representation completed before publication. It is not deserialized metadata and does not attest the constructor history of an arbitrary application object. The proof uses ordinary trusted constructors for the receiver's wrappers; it never infers that constructors of an input Serializable class ran.

**Lemma R3 (private construction).** Before the receiving method returns a successful Result, no Graph or Node created by that invocation is available to a client through the public receiver API.

*Proof.* The incoming frame contains only primitive storage and cannot already reference a freshly allocated Graph or Node. Private state and data are local to the method. Graph's constructor only clones arrays, allocates final Node wrappers, and appends scalar diagnostic strings to a private list. Node constructors only assign owner and identity; they perform no callout. The owner-to-Node and Node-to-owner cycles are internal. Neither a static sink, a public callback, a listener nor a caller-owned array receives a graph reference. The only graph-bearing outward value is the successful Result created after construction. Failure Results contain graph=null. The separate harness's package-private fault hook returns through the same failure path. □

**Lemma R4 (representation and persistence).** Successful Graph construction establishes J. Public Graph/Node calls and retaining returned aliases preserve J and do not make an unreachable Node available.

*Proof.* Array cloning preserves every data cell while severing aliases to input storage. Construction installs exactly one wrapper in each array cell, so two paths reaching identity i return the same wrapper. All data are fixed before wrappers are returned. Public getters perform no writes; arrays returned by roots() and the owned scalar snapshot observation are fresh copies. Root retrieval exposes only rho; successor navigation exposes only its successor closure. Object count and scalar identity diagnostics do not reveal a Node outside that closure. With reflective/unsafe mutation and untrusted same-package test calls excluded, no public operation changes the representation. Induction on a sequence of public navigation calls proves persistence and exposure confinement. □

**Theorem R5 (bounded publication safety).** Assume the trusted-runtime and public-API contract above. Whenever receive(frame) returns a non-null Graph, every Node reachable through its public roots and successor operations satisfies the fixed invariant represented by S. The property remains true for subsequent public reads. If the method returns a failure Result, no Graph or Node from that invocation has been published through the API.

*Proof.* A non-null Graph can be returned only after R2 and successful construction. R4 maps all public paths and field reads to H_d, so every reachable conjunct is true. R4 also preserves the relation for later navigation. A failure returns graph=null, and R3 rules out earlier API publication. This is a failure-closed *receiving contract*, not rollback of arbitrary callback effects. VM failure, nontermination or out-of-memory conditions are not claimed to yield a diagnostic Result; they do not create a modeled public publication action. □

### Concrete traces versus shadow traces

The observed concrete phase sequence is FRAME_COPIED, PRIMITIVE_ARRAY_DECODED, DATA_VALIDATED, zero or more SHADOW_CHECK records, CERTIFICATE_ACCEPTED, NODE_INITIALIZED records, GRAPH_FROZEN, PUBLISH; any finite prefix may end in REJECT. Trace strings are diagnostics, not a source of authority supplied by the producer.

Before PUBLISH, the client-level abstract observation is a private region with no exported root; internal decoding and construction steps may stutter. At PUBLISH, J binds the actual newly returned graph to the already checked H_d. SHADOW_CHECK records are a locally defined validation schedule, **not** a recovered trace of ObjectInputStream's field assignments or arbitrary JVM constructor events. Consequently R5 closes the boundary connection only for this receiver. It does not repair the missing observation premise of the passive bridge.

## 5. Relative completeness, direct baseline, and size

**Theorem R6 (data-language characterization).** For well-formed d whose canonical packet fits the declared bounds, S(H_d,set(rho)) holds if and only if some certificate makes the certificate receiver accept d, assuming successful I/O, allocation and normal trusted-runtime operation. This is also exactly the data language accepted by the eager final-invariant baseline.

*Proof.* Acceptance implies S by R2. Conversely, suppose S holds. Prior to root additions the root set is empty. During root additions every reachable set is a subset of the final closure and the final fields are already installed, so each newly required predicate is true. The producer emits the exact deterministic reads, closure and decision for every step. A separate verifier implementing the specified cases accepts them, and construction succeeds under the stated normal-operation assumption. The eager baseline computes the final closure and each conjunct of S directly, so its accepted data are the same. □

The equivalence concerns data projected from successful packets, not arbitrary packet bytes. The eager baseline intentionally ignores the certificate suffix; it can accept safe data accompanied by a corrupt proof. This is not an eager safety failure. The certificate gate adds independently checkable decision evidence, not a larger safe language or a stronger invariant in this one-shot immutable setting. If no audit evidence is required, the direct check is the simpler sufficient mechanism.

**Lemma R7 (successful packet bound).** Every well-formed safe d has a deterministic proof requiring at most 5+26n+19m+nm integer words, hence at most 22,149 words at n=m=128.

*Proof.* The data prefix plus step count uses 5+2n+m words. The first 3n certificates have no roots or obligations and use 9n words. Each of the m root-step certificates uses at most n+3 words for closure count, closure, obligation count and decision. Across these root steps, each identity is newly reachable at most once (at most n obligations); each repeated/successive root addition can additionally invalidate at most the added root's cached ready read (at most m obligations). No other object's predicate reads that root's ready field. Each obligation occupies 3 header words and at most four 3-word reads, for at most 15 words. Summing gives 5+2n+m+9n+m(n+3)+15(n+m) = 5+26n+19m+nm. The configured 24,576-word cap leaves room. For the specified fresh, unmodified ObjectOutputStream with no preceding values or class annotations, the single primitive int[] encoding uses 27 fixed bytes: stream header4, array tag1, class descriptor tag1, UTF class name length2 plus name2, serial identifier8, flags1, field count2, end annotation1, null superclass1, and array length4. Each integer adds4 bytes. Thus 27+4*22,149=88,623 bytes is below131,072. This size statement is conditional on that exact writer/protocol, not arbitrary annotated or multi-object streams. All4,552 generated integer-array frames were also checked against27+4*word_count; zero differed. □

The preserved generic baseline clones n records for each schedule step. The current production verifier removes those clones by the exact specialization in `specialization.md`; the wire format is unchanged. S4 there sharpens the sufficient bound R7 to an attained maximum of 22,134 words (88,563 bytes). Neither optimization nor the bound establishes an additional data-safety policy relative to eager checking.

## 6. Observer-relative limitation

Let pi(t) retain the owned callback entry/exit sequence, selected public resolveObject observations and final graph/root snapshot, but omit transient stores and reads inside a callback. Define E(t) to mean that an owned observer reads a node while its callback-completion marker is false.

**Theorem O1 (nonseparability for pi).** If two feasible traces t0,t1 have the same pi but different E, no decision function of pi alone is both sound and complete for absence of E.

*Proof.* The function receives the same argument for t0 and t1 and therefore returns the same Boolean. Either it accepts the trace where E holds, violating soundness, or rejects the one where E does not hold, violating completeness. A sound three-valued decision must avoid certifying absence of E for that shared observation. □

`ObservationPair.java` realizes the premise with identical serialized bytes: an owned callback either does nothing observable externally or temporarily exposes itself to an owned Boolean observer and clears the slot before the same final snapshot. Both paths restore the same fields and completion marker. The public projections are equal; the owned unready-read outcomes differ. This is a benign indistinguishability example, not a third-party exploit. It establishes a limit for pi, not for every possible Java observer, an instrumented JVM, or a restricted receiver that prevents application callbacks.

## 7. Assumption-removal counterexamples

- Permit arbitrary readObject code: the executed passive pair has a transient unready read invisible to pi. A callback may also retain an alias and then throw; the old passive fixture records the alias after failure.
- Infer readiness from wire data: an integer supplied by the sender carries no constructor or callback provenance. The new wire format contains no ready bit.
- Share mutable representation: a client could change a value after a successful check without a revalidation event. The public receiver instead clones input arrays and exposes only copies/navigation. Tests mutate retained input bytes, root copies, and scalar snapshots.
- Accept sender-supplied roots as exhaustive JVM roots: an omitted external alias invalidates the ideal theorem. The new receiver controls initial exposure and derives roots from its own export API.
- Equate callback completion with object identity: readResolve can return a different pre-existing identity; that old passive case remains UNKNOWN and such application-class callbacks are excluded from the receiver.
- Treat end-of-read exception as framing proof: the pre-repair receiver accepted a truncated trailing object tag. Canonical re-encoding and a preserved negative control repair the framing contract without pretending the old run rejected it.
- Drop invariant validation but retain filtering: the shape-only baseline accepts 1,046 relationally unsafe data instances in the executed suite. Class filtering and framing are not value-invariant checks.

## 8. Status of the argument

O1 and R1-R7 are complete handwritten arguments for their stated models and assumptions. The concrete source has been reviewed against them and exercised by exact small data, larger structured data, malformed frames/certificates, alias checks and injected construction failure. No arbitrary Java trace-refinement theorem, proof of the JDK, machine verification of the Java source, production application study, cross-JDK proof, or general minimal construction witness is asserted. The eight passive UNKNOWN results are preserved. The positive receiving guarantee requires opting into the new data-only contract; the eager-equivalence result prevents that construction from being presented as a new generic security power of certificates.
