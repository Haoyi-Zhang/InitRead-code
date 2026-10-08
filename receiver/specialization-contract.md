# Frozen continuation experiment contract

Question: Can specialization of the receiver-owned, no-root preparation schedule preserve the full accepted packet language while removing unnecessary heap snapshots? This is a semantics-preserving engineering question, not a claim of new initialization or certification theory.

Fixed scope: same predicate, 1–128 objects, 128 supplied roots, same integer schema, byte/word caps, canonical serialization contract, read-only publication API, and legacy passive UNKNOWN results.

Before implementation: preserve the incoming Java receiver as a mechanically renamed baseline. Implement an independent Python certificate parser/reference with no production imports. Preserve all incoming canonical results.

Checks: (1) exact 4,563 existing Java executions and canonical outputs, (2) fresh independent-reference comparison, including every single-word certificate edit and every proper prefix of selected owned valid packets, (3) equal status, reason, counters, trace, graph and root observations between generic and specialized gates, (4) sharp-size family including a 128-node cycle with 128 duplicate roots, (5) all existing root regression tests, (6) single-run clean offline replay. No third-party payloads, external targets, network experiments, GPU, model APIs, or people.

Performance: before measuring, fix four contrasting safe 128-node families: chain with one root; cycle with one root; isolated node with 128 duplicate roots; full cycle with 128 duplicate roots. Compare generic certificate, specialized certificate and unchanged direct eager gate on identical bytes. Seven sequential JVM forks per family; rotate mode order across forks; 1,000 warmup and 500 timed calls per mode. Report paired fork means, median and full min/max, not per-call latency quantiles or broad performance superiority. Do not discard slow forks or tune from these results.

Success: zero language/diagnostic/reference disagreements and original deterministic results unchanged. Slower specialization or direct checking is an allowed result.

Resource: one worker, local CPU, existing capped JVM options, each child bounded by timeout; record measured Python/JDK/system/options/input/code and commands/exits. Earlier aggregate event-ceiling overrun remains disclosed. New timing not backfilled into old environment or baselines.
