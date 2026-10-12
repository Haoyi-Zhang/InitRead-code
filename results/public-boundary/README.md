# Public boundary and costs, 2026-10-12

These fresh run receipts support ledger claims C34/C35. The 5,230 complete-data
inputs are in `valid-data-cases.tsv`, selected unchanged from
`../specialization-campaign/cases.tsv`. `public-boundary.stdout.txt` retains
15,690 actual public-navigation observations across three modes.
`summary.json` records zero mismatches, 1,046 unsafe-data cases, the unchanged
three MAPPED/eight UNKNOWN passive outcomes and the equal-projection pair.

The large navigation log and input table have lossless `.gz` representations.
`storage.json` supplies their logical filenames, stored filenames and byte
bindings. Decompression reconstructs the original text exactly; no observation,
input, timing value or recorded command is changed. Compressed files record
storage encoding rather than inheriting execution-file timestamps. They can be
read with Python's `gzip.open(path, 'rt')` or unpacked into a temporary folder.
The passive and class-evolution logs, `passive-results.json`, pair observations,
and the owned 55-byte evolution fixture are included.

`cost-cases.tsv` contains the four measured 128-node inputs. All 28 fork
stdout/stderr pairs are retained; their 84 JSON records agree exactly with
`java-costs.json`. `python-preparation.json` contains 56 raw batch records:
four families, two preparation modes and seven five-call batches. Java records
use 300 warm-ups and 200 measured calls per operation. `cost-summary.json`
retains all reported medians/minima/maxima and its original `_ns` Java field
names: those summary values are microseconds per call, as its `units` says.
Raw `_ns` totals in `java-costs.json` and `python-preparation.json` are actual
nanoseconds. They are not changed to repair the summary naming mismatch.
`cost-summary-us.json` is an explicitly derived view of `cost-summary.json`:
the 36 Java metric keys use `_us`; every numeric value and protocol statistic is
unchanged. Its `derived_from` and `derivation` fields explain the alias. It is
new documentation of the original units, not raw output of another source
version, and no executed Java source or source binding has been relabeled.
The Java pipeline was measured jointly; Python and JVM stages are not summed
into end-to-end latency. There is no network or memory measurement.

`environment.json` binds the exact run versions in `sources/`, and the retained
input corpus relative to the repository root. The saved driver predates the
current root driver's later test orchestration and summary-key changes;
use the snapshot for this run's provenance. The other saved source
versions also match the current root source bindings. The snapshot driver
requires the retained artifact inputs and is not runnable by itself: overlay
`sources/` onto a separate complete artifact copy, then run its driver with an
absent sibling output directory. The top-level README gives the command.

All 38 recorded subprocesses exited zero. Commands retain their recorded flags,
exit codes, UTC timestamps and wall seconds. Private absolute path fields in
`commands.json` and `environment.json` are replaced with repository-relative
paths and executable names; all other JSON values and source hashes are
unchanged. Uncompressed copies retain their original filesystem timestamps.
`classes/`, `v1/` and `v2/` paths in the command receipts are generated
class-output targets, not included binaries. The recorded runtime is Windows
11 AMD64, CPython 3.12.14 and Temurin 17.0.20.1+1; version logs are included.

The owned benign Java observations and generated data are covered by the
artifact's LICENSE. No third-party gadget, compiled class, local runtime,
credential or private absolute path is shipped here. These local receipts do
not claim a fresh remote-CI execution, deployment performance or broader
Serializable coverage.
