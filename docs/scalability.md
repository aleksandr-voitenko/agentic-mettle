# Scalability and bounded comparison (0.5.0)

## PR 3 packet measurements

The packet uses one protected metadata inventory/catalogue opening, one cached
metadata scan, and at most one historical lexical ranking. It validates explicit
seeds and returned records through existing targeted access. No unrelated canonical
bodies are decoded on the warm path; own lesson history/direct reference checks can
still grow. Cold cache reconstruction, publication, installation, full `check`,
and `reindex` remain complete-archive operations. See [the design](consolidation.md).

Reproduce (only disposable synthetic installations):

```sh
python examples/benchmark_scalability.py --consolidation-only --episodes 1000 5000 10000 --lessons 100 --domains 10 --repetitions 3 > consolidation-results.json
```

Measured locally: macOS 27.0.1 arm64, Python 3.14.7, temporary local filesystem,
three repetitions in fresh subprocesses, rerun after the correction-discovery fix.
The 1,000 and 5,000 episode sizes were
run; 10,000 remains available opt-in. Each archive has 100 proposed single-revision
lessons in ten domains, originating from E-00000, plus an empty activity. The
explicit seed E-00001 is unrelated; narrow `needle00000` matches one lesson and
broad `amberwidget` matches all 100. Each packet requests at most 12 items; lexical
selection takes five anchors. No reviews or corrections are in this measurement
fixture; regression scenarios exercise those links separately.

| Episodes | Query | Cold canonical reads | Warm canonical reads | Packet UTF-8 bytes | Cold median process s | Warm median process s |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1,000 | narrow | 1,103 | 3 | 3,473 | 0.715 | 0.247 |
| 1,000 | broad | 1,107 | 7 | 7,094 | 0.721 | 0.253 |
| 5,000 | narrow | 5,103 | 3 | 3,473 | 2.621 | 0.777 |
| 5,000 | broad | 5,107 | 7 | 7,094 | 2.627 | 0.779 |

Warm calls: zero snapshots, one catalogue connection, one ranking call, 1,100 or
5,100 canonical inventory entries and cached metadata rows, zero derived/cache
writes. Cold calls: one snapshot, two inventory passes/connections, one catalogue
write. Every call also writes the existing temporary lock-owner file. Counts
instrument real readers/decoders, not a mocked-out snapshot. Inventory counts are
entries, not syscall counts; catalogue connections are not physical SQLite page
reads. Process timings include instrumented wrapper/interpreter startup. Cold
means no catalogue, not flushed OS caches. These warm OS-cache local timings are
not Windows predictions or evidence of improved model learning.

The correction-discovery follow-up adds 76 bytes of review-expansion disclosure
to these packets (previously 3,397 / 7,018 bytes at e1c8985); read counts are
unchanged in this no-review benchmark fixture. Separate normal-publication tests
cover correction → originating evidence → lesson and lesson → supporting review
→ source episode → correction, including activity seeds and priority over lexical
matches. A nine-review fixture verifies the eight-review expansion cap, byte/count
bounds, pagination and executable continuation for unexamined source dependencies.

Deterministic regression guards cover item/serialized-byte bounds, complete
pagination in an unchanged store, optional preview removal, exact oversized-path
omissions, explicit-input and counterevidence omissions, one inventory/query,
real canonical reads, no warm derived writes, and unchanged records/profiles/work
from packet generation. The authored outcome scenarios test supported workflows,
not autonomous semantic judgment. The [manual pilot](evaluation.md#manual-consolidation-pilot)
was not run with a model.

Protocol size: **11,207 → 11,899 UTF-8 bytes; 1,509 → 1,595 whitespace-separated
words** (0.4.0 baseline to this release). No token savings are claimed. The startup
character budget is unchanged; the guide and packets are on demand. An actual
0.4.0 source installation from ed95314 was upgraded in a temporary synthetic root:
14 protected files/authorized-section checks retained identical SHA-256 values,
including canonical records, custom profiles/vocabulary and workspace content.
Installation metadata and the managed activation block retain their ordinary
upgrade behavior. Installed packet, `check`, and bootstrap passed; bootstrap was
17,445 characters for that fixture. The automated compatibility fixture also tests
preservation and installed discovery. See the PR for final local and CI outcomes.

The following PR 2/PR 1 sections are historical measurements and package descriptions.

## Archived PR 2: targeted access and historical discovery (0.4.0)

PR 2 changes ordinary read costs and adds explicit historical discovery; it does
not change learning decisions. See the [design decision](targeted-access.md) and
[validation/freshness contract](records.md#targeted-reads-and-historical-discovery).
Accepted schema 1, workspace format 2, immutable records, profiles, and default
ranking/eligibility remain unchanged. Consolidation was deferred to PR 3.

### Reproduce PR 2 measurements

```sh
python examples/benchmark_scalability.py --episodes 1000 5000 10000 --lessons 100 --domains 10 --repetitions 3 --navigation-stress > targeted-access-results.json
```

PowerShell can use `& $Python -X utf8 examples/benchmark_scalability.py` with the
same arguments. Only temporary synthetic installations are created. Setup writes
fixtures directly, then validates them; no pilot or model is involved. The large
benchmark remains opt-in, outside ordinary CI.

Each archive contains the requested 1,000/5,000/10,000 episodes and 100 proposed
lessons, one revision each, across ten domains. Each lesson originates from the
first episode. `needle00000` matches one item, while `amberwidget` matches the
whole selected corpus; both request three results. Fixed metadata, Japanese and
accented tags, and phrase aliases are present. Separate regression fixtures cover
revisions, all statuses, scope, compound identifiers, activity rejections,
corrections, and incorporated/pending reviews. Those tests compare every default
result field with frozen 0.3.1 retrieval; the older 0.3.0 parity fixture remains.

The benchmark runs each command in a fresh instrumented subprocess. The reference
uses frozen 0.3.1 retrieval, or its full-snapshot show lookup, with the same
validator. Every search pair asserts exact candidate equality. Warm means a
verified catalogue exists; cold means it was removed, **not** that OS caches were
flushed. Three repetitions cover each before/after query and cold/warm episode
show. Reference show, cold broad episode search, navigation, bootstrap,
publication, reindex, and stress check are each measured once. Raw JSON includes
all repetitions, command and end-to-end process time, read/decode counts,
snapshot calls, inventory entries/passes, catalogue connections/writes, other
writes, and output sizes. Process time includes interpreter/wrapper startup.

Canonical reads count real `mettle.read` calls, with the real decoder and snapshot
still running. Inventory entries count canonical file metadata, not individual
`stat`/directory syscalls. Catalogue connections count SQLite opens, not physical
page I/O or OS cache misses. The existing lock-owner write is included separately;
zero catalogue writes does not mean zero filesystem writes.

### Local results, 2026-11-02

macOS 27.0.1 arm64, Homebrew CPython 3.14.7, local temporary storage. OS caches were
not flushed. The completed benchmark ran separately from the full test suites. These are local observations,
not predictions for Windows or evidence of improved LLM learning.

Median instrumented end-to-end search times in seconds, **0.3.1 → warm 0.4.0**:

| Episodes | Lesson narrow | Lesson broad | Episode narrow | Episode broad |
|---:|---:|---:|---:|---:|
| 1,000 | 0.356 → 0.250 | 0.353 → 0.251 | 0.364 → 0.255 | 0.370 → 0.268 |
| 5,000 | 1.054 → 0.768 | 1.055 → 0.772 | 1.106 → 0.813 | 1.154 → 0.883 |
| 10,000 | 2.074 → 1.570 | 2.081 → 1.565 | 2.179 → 1.651 | 2.320 → 1.803 |

Episode `show E-00000`, end-to-end seconds (reference is one sample; cold/warm
are medians of three), and catalogue disk size:

| Episodes | 0.3.1 show | Cold 0.4.0 show | Warm 0.4.0 show | Catalogue bytes |
|---:|---:|---:|---:|---:|
| 1,000 | 0.357 | 0.723 | 0.248 | 1,708,032 |
| 5,000 | 1.045 | 2.615 | 0.764 | 7,569,408 |
| 10,000 | 2.069 | 5.441 | 1.555 | 14,893,056 |

The catalogue trades disk space and rebuild cost for fewer canonical decodes. It
preserves lexical sequences and episode scope text; it is not a bounded-size
replacement for the archive. At 10,000 episodes, cold broad search took
5.690 seconds versus 1.803 seconds warm. A read immediately after publication
can pay that cold cost because publication invalidates the catalogue.

Deterministic canonical reads, independent of wall-clock timing:

| Operation | 0.3.1 reads | Warm 0.4.0 reads |
|---|---:|---:|
| Isolated episode show | 1,100 / 5,100 / 10,100 | 1 |
| Lesson narrow search | 1,100 / 5,100 / 10,100 | 2 (lesson + origin) |
| Lesson broad search, limit 3 | 1,100 / 5,100 / 10,100 | 4 (three lessons + shared origin) |
| Episode narrow search | 1,100 / 5,100 / 10,100 | 1 |
| Episode broad search, limit 3 | 1,100 / 5,100 / 10,100 | 3 |
| Warm domain lesson navigation, limit 3 | Full archive | 4 |

Each warm command makes **zero snapshot calls**, one inventory pass over
1,100 / 5,100 / 10,100 canonical entries, one catalogue connection, and no
catalogue/view/navigation writes. Search additionally decodes the vocabulary;
selected current lessons read their current views. Cold show takes one snapshot,
N+1 canonical reads, two inventory passes (2N entries), two SQLite open attempts,
and one catalogue write. Cold broad episode search reads N+3 canonical files.
Warm relationship enrichment performs no full-record collection pass; reverse
links select relevant canonical reviews/corrections. The performance fixtures
have no such links; regression tests exercise their nonzero dependency costs.

Metadata enumeration still grows with all files/directories. SQLite structural
checks and path coverage inspect derived data; search scans cached lexical
features, computes frequencies, and sorts matches. A selected lesson can depend
on its entire local history and immediate evidence, so neither show nor search
has a fixed-cost guarantee. Full publication, installation, migration, explicit
check/reindex, workspace checkpoints and rejection guards retain archive work.
Workspace publication retry and installer boundary scans remain unchanged.

Episode publication still writes zero lesson views/navigation files and removes
the catalogue before accepted publication. The subsequent reindex rebuilds that
catalogue and the work index; unchanged lesson views/navigation are not rewritten.
Bootstrap reads zero canonical files and no catalogue. Its output is 15,515
characters in the standard fixture; required protocol/profiles retain the
24,000-character startup budget.

The PR 1 navigation stress fixture remains 20 episodes, 900 lessons (500 with
long Unicode metadata in one domain), and 401 domains. The root map is 387 UTF-8
bytes; the largest generated index is 14,880 bytes, below the 16,000-byte budget.
Bootstrap emits 15,538 characters. Cold domain navigation includes reconstruction
(971 canonical reads); full check reads 920 canonical files and 900 current views
**once**, compared with PR 1's two snapshots (1,840 + 1,800 reads). Full check took
1.951 seconds in this run and also compared the catalogue with canonical data.

### Validation and compatibility

Regression tests assert canonical read/decode counts, zero warm snapshots,
unchanged catalogue bytes/mtimes, real source validation, exact default-search
parity, historical pagination/labels, corruption and interruption recovery, and
canonical/profile/workspace hashes across rebuild/install. Existing full
integrity, immutable-publication, navigation stress, retention, path, migration,
and workspace tests remain. CI retains Linux/Windows on Python 3.11, 3.12, 3.13.
See the PR for final local/CI outcomes; Windows was not run locally.

Normal source installation deploys all five helper modules and rebuilds the
catalogue. Missing/stale/incompatible cache data is disposable; damaged accepted
history cannot be restored from it. See [upgrade and repair](installer.md#upgrading-targeted-access-040).
No new canonical schema, relocation, historical rewriting, automatic learning,
background work, or consolidation is included.

## Archived PR 1 measurements (0.3.1)

The following is the retained PR 1 measurement record. Its full-snapshot read
behavior and four-module package describe **0.3.1**, not the current release.
Reproducing that reference benchmark requires checkout
`f6d521ae03bc814016c14553e78dfce37d3a15c9`; the command above compares 0.3.1 with
current targeted access.

### Bounded navigation and retrieval costs (0.3.1)

This release bounds generated memory navigation, enriches only the selected
search results in one relationship pass, and avoids unrelated derived writes.
It does not change accepted-record schema 1, workspace format 2, ranking,
applicability, or learning decisions. The regression suite compares all result
fields against the frozen 0.3.0 retrieval implementation, including phrase aliases,
scope, ties, activity-scoped rejections, statuses, corrections, and pending reviews.

### Remaining full-archive work

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

### Reproduce the measurements

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

### Local results, 2026-11-02

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

#### Navigation stress fixture

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

### Validation and compatibility

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
