# Receiver experiment contract

Question: can a deliberately callback-free data receiver establish the finite
invariant at its own return boundary, without claiming recovery of arbitrary
ObjectInputStream histories? A second question asks whether certification adds
semantic protection beyond a direct eager check for this single frozen result.

The inherited passive bridge and canonical campaign remain immutable. This is
an additional, incompatible wire/API construction; UNKNOWN cases are not
relabelled as successful legacy deserializations.

## Prespecified evidence

- One worker; JVM `-XX:ActiveProcessorCount=1 -XX:+UseSerialGC -Xmx256m`;
  compiler `-proc:none`; standard libraries only.
- Exhaust all data graphs of size 1, 2, and 3: binary value vectors, all nullable
  successor vectors, and every root subset (4,248 distinct data inputs).
  `ready` is not a wire value: completion is established locally.
- Development: exact small inputs and the four-case pilot (safe, unsafe, cyclic,
  empty roots). Held-out fixtures: 96 deterministic graphs, 32 each of lollipop,
  shared-tail, and disconnected-cycle structures, sizes 16, 32, 64, 128.
  No model training or parameter tuning. After corrections, rerun every input;
  an inspected holdout is not a future untouched test set.
- Metamorphic controls: identity reversal of every held-out case; retained root
  multiplicity preserved. Require decisions unchanged and reconstruct alias
  identity exactly for every successful case.
- Corruption controls: one small safe certificate, every position in its
  certificate-only suffix individually flipped; all suffix truncations; an
  appended integer; missing/extra step, closure, obligation, and transcript
  values are naturally included. Data-domain/schema controls are separate.
- Benign wire controls: callback-bearing owned class, heterogeneous Object[],
  double[], string, null, second value, truncation, excessive int[] and byte
  frame. No callback-bearing class may run on the receiving path.
- Failure control: throw before constructing the first public node; expect no
  Graph and no publication event.
- Same-byte paired observation: optional temporary retention plus an owned
  Boolean observer; no arbitrary code/payload/target, no external effect. The
  public callback/final projection must be identical and observed-unready must
  differ. This fixes the precise observation interface in the limitation proof.
- Baselines: descriptor/shape-only acceptance and direct eager invariant check
  with the SAME frozen representation and input frame. The eager baseline
  intentionally does not validate the certificate. Do not imply it is unsafe
  merely because it ignores unnecessary certificate metadata.
- Performance: seven sequential size-specific JVM forks per size; six safe chain sizes 1,4,16,32,64,128;
  500 warmups and 200 timed calls per mode; mode order rotated by fork; retain raw
  batch timings, report medians and ranges, not a universal overhead claim.
- Publication failure, oracle disagreement, callback execution, broken alias
  identity, input alias mutation, and acceptance of a malformed certificate are
  errors. Slower certification and equality with the eager semantic guarantee
  are admissible, scientifically important results, not reasons to tune cases.

New data domain: same 128 logical objects and fixed predicate; protocol cap
24,576 signed 32-bit words and 131,072 bytes. No production application claim.

## Measurement repair after the pilot

The 20-warmup pilot reused each JVM across ascending sizes and showed strong JIT/order effects (including non-monotone size costs). Its entire output and the two affected source files are retained under `results/receiver-pilot/`. The final measurement isolates each size in its own JVM, increases warmup to 500, and uses 200 timed calls. This is a repair for measurement validity, not evidence of a speedup; slower certification remains an admissible result. Exact correctness inputs and predicates are unchanged.

## Framing negative control
A source review found that catching EOFException on a second read also accepts a truncated second value. A benign appended array tag reproduced that behavior. The receiver now re-encodes the already decoded primitive array with a trusted ObjectOutputStream and requires exact byte equality. The wire contract is explicitly canonical and rejects stream reset and extra material; this does not retrofit arbitrary Serializable streams. The control and pre-repair source/results remain in results/receiver-framing-control. This correction changes framing cost for all three receiving modes, so timing is rerun rather than reused.
