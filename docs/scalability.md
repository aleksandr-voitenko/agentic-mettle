# Bounded navigation and retrieval costs (0.3.1)

This release bounds generated memory navigation, enriches only the selected
search results in one relationship pass, and avoids unrelated derived writes.
It does not change accepted-record schema 1, workspace format 2, ranking,
applicability, or learning decisions. The regression suite compares all result
fields against the frozen 0.3.0 retrieval implementation, including phrase aliases,
scope, ties, activity-scoped rejections, statuses, corrections, and pending reviews.

## Remaining full-archive work

Search, show, navigate, publication, installation, check, and reindex still
validate the complete accepted snapshot. Search still tokenizes the chosen
collection, computes term frequencies, and sorts matches. Relationship enrichment
now visits the record collection once after limiting results (zero passes for no
results), plus the correction links within those records. A selected lesson's
already incorporated counterevidence is excluded without hiding unresolved reviews.

No lookup catalogue, targeted validation/access, historical-discovery redesign,
consolidation, scheduler, model call, or service is included. Targeted access and
current-versus-historical discovery belong to PR 2; bounded agent-owned
consolidation belongs to PR 3. Bootstrap still avoids the accepted archive and
reads only required startup inputs and direct work headers.

## Reproduce the measurements

Run from the source checkout with Python 3.11+ (use your selected executable):

```sh
python examples/benchmark_scalability.py --episodes 1000 5000 10000 --lessons 100 --domains 10 --repetitions 3 --navigation-stress > scalability-results.json
```

PowerShell can use `& $Python -X utf8 examples/benchmark_scalability.py` with the
same arguments. The benchmark creates fresh temporary synthetic roots and removes
them afterward. Fixture setup writes
canonical files directly and then validates the complete graph before reindexing,
avoiding quadratic setup publication. The larger benchmark is opt-in, outside CI.

Each retrieval fixture has exactly the requested episode count, 100 proposed
lessons (one revision each) across 10 domains, fixed timestamps, and no workspaces.
All lessons originate from the first episode. Titles contain `amberwidget` plus
a unique `needleNNNNN`; the broad query matches the entire selected collection,
while `needle00000` matches one record. Both request three results. These performance
fixtures contain no reviews; the regression parity fixture separately exercises
incorporated/unresolved reviews, corrections, and revised lesson statuses.

The benchmark launches an instrumented subprocess for each command. The before
case swaps only retrieval for the frozen 0.3.0 algorithm, using the same complete
snapshot validator and CLI as after. It asserts result parity on every run.
`process_seconds` includes interpreter/wrapper startup; `command_seconds` covers
argument parsing, locking, validation, ranking/enrichment, and output. The wrapper
uses standard-library instrumentation, so this is not a bare CLI microbenchmark.
The output contains each repetition, medians, read/write counts, and byte/character
sizes. Read counts cover `mettle.read`, not filesystem metadata calls, OS cache
misses, or installer guard reads. Relationship counts start after snapshot validation.

## Local results, 2026-11-02

Environment: macOS 27.0.1, arm64, Homebrew CPython 3.14.7, local temporary storage.
Three repetitions per before/after query, in alternating before/after order;
bootstrap, publication, navigation, check, and reindex each measured once per
fixture. Caches were not flushed. These local warm-cache times are not predictions
for a Windows project and do not measure LLM behavior or learning effectiveness.
Other local validation was running during part of the benchmark.

Median end-to-end instrumented subprocess times, seconds (before → after):

| Episodes | Lesson narrow | Lesson broad | Episode narrow | Episode broad |
|---:|---:|---:|---:|---:|
| 1,000 | 0.377 → 0.381 | 0.380 → 0.375 | 0.384 → 0.382 | 0.470 → 0.394 |
| 5,000 | 1.102 → 1.092 | 1.151 → 1.137 | 1.126 → 1.132 | 3.100 → 1.132 |
| 10,000 | 2.075 → 2.042 | 2.065 → 2.035 | 2.153 → 2.119 | 9.939 → 2.257 |

Deterministic relationship record visits (before → after):

| Episodes | Lesson broad (100 matches) | Episode broad | Either narrow (one match) |
|---:|---:|---:|---:|
| 1,000 | 100,000 → 1,000 | 1,000,000 → 1,000 | 1,000 → 1,000 |
| 5,000 | 500,000 → 5,000 | 25,000,000 → 5,000 | 5,000 → 5,000 |
| 10,000 | 1,000,000 → 10,000 | 100,000,000 → 10,000 | 10,000 → 10,000 |

Every search still read 1,100 / 5,100 / 10,100 canonical files respectively,
plus 100 current lesson views. The operation count reduction is in enrichment,
not canonical I/O. Search wrote no derived files. Narrow searches show why a
constant-time or universal latency-improvement claim would be misleading.

One new episode took 0.373 / 1.048 / 2.009 seconds end to end and wrote **zero**
lesson views or navigation files. The old unconditional loop would write 111
derived files each time (100 current views + 10 domain indexes + root map); that
before count is calculated from the preserved loop, not a measured old publication
time. The new command still read all pre-existing canonical files/current views
and wrote its accepted record and lock owner. Explicit unchanged reindex wrote
zero memory views/indexes; the existing work-index rebuild still wrote one file.

In these modest-metadata fixtures the root map shrank from 801 to 386 UTF-8 bytes.
The largest domain file grew from 2,865 to 4,760 bytes because the new format uses
formatted JSON and continuation metadata; the objective is a fixed upper bound,
not making every small index smaller. Bootstrap emitted 15,331 characters
(including CLI newlines), read five noncanonical files, and read no canonical
records. Its measured process times were 0.080–0.084 seconds.

### Navigation stress fixture

Twenty episodes, **500 lessons in one domain**, plus 400 additional lessons in
400 distinct domains: 900 lessons, 401 domains, 402 generated index files.
The large domain includes Japanese text, accented characters, quotes/backslashes,
long title/scope/alias fields, and lists that require explicit preview shortening.

| Measurement | 0.3.0 serialization | 0.3.1 |
|---|---:|---:|
| Root map, UTF-8 bytes | 25,817 | 387 |
| Largest domain index, UTF-8 bytes | 1,500,595 | 14,880 |
| Generated-file budget | Could exceed 128,000-byte reader | ≤16,000 bytes including wrapper/continuation |
| Startup output, characters | Root alone exceeded 24,000-character limit | 15,354 |

Navigation's first domain page emitted 7,498 bytes and took 1.278 seconds end to
end, reading 920 canonical files and 900 current views. Full check took 2.479
seconds and read 1,840 canonical files plus 1,800 current views: workspace checks
currently take a second snapshot. Bootstrap took 0.084 seconds with no canonical
reads. Size/count tests verify that every domain and lesson is reached exactly
once by continuation in an unchanged store. Separate tests use near-budget required
profiles and optional work pointers to check installer/bootstrap agreement.

## Validation and compatibility

The full suite, synthetic walkthrough, Python compilation, and `git diff --check`
are required before publication. CI retains Linux and native Windows with Python
3.11, 3.12, and 3.13. See the PR for the actual final local and CI outcomes; these
measurements are not a claim that Windows ran locally.

Tests also cover unchanged file bytes/mtimes, interrupted derived maintenance,
repair/retry, missing indexes, full canonical validation during navigation/repair,
and exact profile/history preservation when upgrading old oversized indexes.
The installer still deploys all four helper modules and the matching protocol and
references. The protocol text changes only its version. Migration continues to
exclude generated navigation from its protected-history fingerprint; no migration
schema or relocation behavior changes. [The upgrade route](installer.md#upgrading-bounded-navigation-031)
uses the new source helper's existing `reindex --repair` before installation when
old oversized generated files block normal preflight.
