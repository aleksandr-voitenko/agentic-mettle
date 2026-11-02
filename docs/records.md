# Record format and lifecycle

All record files are UTF-8 Markdown. Generated files use UTF-8 without a BOM and
LF line endings. User-edited inputs can have a UTF-8 BOM and CRLF; other encodings
are rejected rather than guessed. Accepted historical bytes are not rewritten
when read or reindexed. The first block contains **JSON** between
`---` delimiters. JSON is used to keep the helper dependency-free; arbitrary YAML
syntax is not supported. Markdown bodies remain readable with normal tools and
`grep`/`rg`. Prefer `template KIND --work W-ID` to create a correctly shaped
draft under its activity workspace (see WORK_REFERENCE.md). The explicit
`--output draft.md` form below remains available outside protected package
directories; it does not rely on shell redirection encoding. Output must be a
new file. Omitting both options retains stdout. A draft is not accepted evidence
until published.

## Kinds

| Kind | ID prefix | Required body sections | Purpose |
|---|---|---|---|
| `episode` | `E-` | Observe, Evidence, Interpret, Uncertainty | Observable event and explicitly tentative interpretation. |
| `lesson` | `L-` | Trigger, Practice, Exceptions, Expected result, Review plan, Change rationale | Scoped, revisable candidate practice. |
| `review` | `V-` | Situation, Application, Outcome, Assessment | A later assessment of an exact lesson revision. |
| `reconciliation` | `C-` | Decision, Evidence assessment, Planned changes | Evidence-linked explanation of a durable change. |

Common metadata: `schema: 1`, `kind`, `id`, `title`, `created_at` (ISO-8601 with a
timezone). Bodies and required metadata must not retain template TODOs. IDs are
unique within the one store, including case-insensitive comparisons. References
must still use the exact accepted spelling; the helper never folds or renames
IDs. Timestamps are recorded metadata, not independently
verified evidence that an event occurred.

An episode adds `runtime`, `model`, `session` (use `unknown`, never fabricate), and
`corrects` (earlier episode IDs, usually empty). Evidence should contain an exact
command/result, commit/path, source excerpt, or attributed report. Do not save
secrets or unnecessary personal information. An external URL alone may cease to
be sufficient; preserve a permitted minimal excerpt when needed.

A lesson adds `revision`, `status`, `domain`, `scope`, `tags`, `aliases`, `origin`,
`support`, `counterevidence`, `reconciliations`, `supersedes`, and `superseded_by`.
The evidence, scope, tag, alias, and supersession fields are arrays of strings. Domains allow
nested lowercase paths such as `engineering/generated-code`. They cannot contain
`..`, absolute or drive-relative paths, symlinks, junctions, or reserved Windows
components such as `con`, `aux`, and `lpt1`. Trailing dots/spaces and alternate
data stream syntax are also refused. `scope` must state relevant components and
conditions. Source-code paths are interpreted relative to root `AGENTS.md`; use
forward slashes for portable references. Generated publication paths, search
results, and index paths use forward slashes on every OS. Existing prose and
metadata are not silently migrated. New IDs/domains must be portable on every
OS. Existing POSIX-only domain names and case-distinct histories remain readable
on POSIX; Windows reports incompatible archives without changing the history.
Do not copy such an archive onto a case-insensitive filesystem without operator
review, where distinct files could otherwise be lost by the copy itself.

`origin` contains episode IDs. `support` and `counterevidence` contain review IDs,
not repeated summaries of the original incident. A new lesson starts at revision
1 with status `proposed`. This means evidential uncertainty, not pending human
approval. Ordinary learning within configured scope is agent-owned; publication
records a decision rather than proving it. `active` requires at least one later supporting review;
this is a structural gate, not a declaration of universal validity. `contested`,
`retired`, and `superseded` preserve uncertainty and replacement history.

A review adds `lesson`, `lesson_revision`, `episodes`, and `assessment`:
`support`, `counterexample`, `uncertain`, `not_applied`, `misapplied`, or `obsolete`.
A review must refer to an already accepted revision and episode. Its body should
say whether the lesson was actually applied, whether it fit, and what was
observable. Support for an earlier revision does not automatically prove a
broader new revision; explain how it transfers in the change rationale.

A reconciliation adds `operation`, `inputs` (exact `L-ID@N` strings), and `evidence`
(episode/review/reconciliation IDs). Operations are ADD, REVISE, LINK_EVIDENCE,
MERGE, MARK_CONTESTED, and RETIRE. It records an intended decision; the accepted
lesson revision establishes which changes were actually published. There is no
inference engine automatically performing these operations.

## A complete lifecycle

Commands below run from the target root for brevity. From a component directory,
use the installed helper's absolute path. Do not replace the designated root
with the component's `AGENTS.md`. Use the selected interpreter and argument
prefix recorded in `.agent-personality/LOCATION.md`.

Windows PowerShell 5.1 or 7:

```powershell
$Python = 'C:\Path\To\Python311\python.exe'  # Use LOCATION.md's selected executable.
$M = Join-Path $PWD '.agent-personality\tools\mettle.py'
& $Python -X utf8 $M template episode --output episode-draft.md
# Edit as UTF-8: fill in real evidence, runtime/model/session, and all sections.
& $Python -X utf8 $M publish episode-draft.md
& $Python -X utf8 $M template lesson --output lesson-draft.md
# Add the accepted episode ID to origin; write scoped practice and exceptions.
& $Python -X utf8 $M publish lesson-draft.md --expected-revision 0
& $Python -X utf8 $M search generated bindings
& $Python -X utf8 $M show L-REPLACE_WITH_ACTUAL_ID
```

Do not create drafts using PowerShell 5.1 `>`/`Out-File`, which can produce
UTF-16. The helper's `--output` works in both PowerShell versions. Keep private
drafts out of source commits. Use a new filename for each draft.

macOS/Linux (set `PYTHON` to the selected executable):

```sh
M=.agent-personality/tools/mettle.py
PYTHON=/absolute/path/to/python3
"$PYTHON" -X utf8 "$M" template episode --output /tmp/mettle-episode.md
# Fill in real evidence, runtime/model/session, and all body sections.
"$PYTHON" -X utf8 "$M" publish /tmp/mettle-episode.md

"$PYTHON" -X utf8 "$M" template lesson --output /tmp/mettle-lesson.md
# Add the accepted episode ID to origin; write scoped practice and exceptions.
"$PYTHON" -X utf8 "$M" publish /tmp/mettle-lesson.md --expected-revision 0
"$PYTHON" -X utf8 "$M" search generated bindings
"$PYTHON" -X utf8 "$M" show L-REPLACE_WITH_ACTUAL_ID
```

At a **later applicable opportunity**, publish a new episode and a review that
names revision 1. Keep pending work pending; do not manufacture a successful
application to complete the template. Then publish a reconciliation referencing
`L-ID@1` and the review. Obtain the accepted lesson with `show`, edit a draft to
revision 2, retain the prior evidence arrays, add the new reconciliation and
review, and publish with `--expected-revision 1`.

PowerShell:

```powershell
& $Python -X utf8 $M show L-REPLACE_WITH_ACTUAL_ID --output revision-draft.md
# Update the draft, not current.md or revisions/0001.md.
& $Python -X utf8 $M publish revision-draft.md --expected-revision 1
& $Python -X utf8 $M check
```

macOS/Linux:

```sh
"$PYTHON" -X utf8 "$M" show L-REPLACE_WITH_ACTUAL_ID --output /tmp/mettle-revision.md
# Update the draft, not current.md or revisions/0001.md.
"$PYTHON" -X utf8 "$M" publish /tmp/mettle-revision.md --expected-revision 1
"$PYTHON" -X utf8 "$M" check
```

A counterexample should cause prompt review, usually a contested or narrowed
revision. The record stays present after its issue is addressed. Search results
flag counterexamples not yet linked into the current lesson. A proposed lesson
can be experimentally applied, but should not masquerade as established policy.

For merging, create a new proposed canonical lesson with predecessor IDs in
`supersedes`, all relevant originating evidence, and preserved search aliases.
Retire predecessors via new superseded revisions pointing to the canonical ID.
Each predecessor update requires its own expected revision and a reconciliation
that names that revision. A multi-lesson merge is **not** one atomic transaction;
finish the recorded plan and run `check`. No automatic evidence inflation occurs.

## Bounded memory navigation

`memory/INDEX.md` stays a small orientation/continuation map, even with many
domains. Append these commands to the executable/argument prefix in LOCATION.md:

```text
navigate
navigate --offset 50 --limit 50
navigate --domain engineering/generated-code
```

`navigate` lists domains and their existing `memory/lessons/DOMAIN/INDEX.md`
paths. With `--domain`, it lists each lesson's latest accepted revision, including
retired/superseded lessons with their actual status. This is navigation, not a
change to search's default exclusion of those statuses. Domain indexes contain
the first bounded page as fenced JSON. No continuation files or lookup catalogue
are stored; `next_command` computes the next page from validated canonical records.

Follow the returned `next_command` until null. `total`, `remaining`, and
`next_offset` report coverage; an unknown valid domain or offset beyond the end
returns an empty page. Offsets start at zero and limits are 1..100 (default 50).
The UTF-8 byte budget can return fewer entries than the requested limit. Domains
sort by name and lessons by accepted ID. Pagination is deterministic for an
unchanged store; restart a traversal if another publication changes the listing.

Generated domain files and command pages fit within 16,000 serialized UTF-8 bytes,
including JSON escaping, headers, fences, and continuation information. Display
previews retain at most 160 characters per string and three entries per list;
`preview_truncated` explicitly names shortened title/scope/tag/alias fields.
When a single row still exceeds the budget, optional display fields are omitted
as needed (aliases, tags, scope, then title) and named in `preview_truncated`.
IDs, revisions, statuses, and record paths stay exact. `show ID` supplies full
metadata/body; `show ID --revision N` supplies retained history. Preview shortening
does not change canonical records or the full text used for search.
Generated commands use `--domain=DOMAIN` so valid leading-hyphen names such as
`-legacy` remain usable as command arguments.

The root map omits the listings and reports their counts and continuation route.
Bootstrap loads this small map, required protocol/profiles, and budgeted optional
work pointers; its separate 24,000-character budget is not a byte or token budget.
Neither memory growth nor navigation previews require injecting all domains at
startup. Required profiles and protocol are never trimmed to make them fit.

## Authority and recovery

Accepted records and `lessons/DOMAIN/L-ID/revisions/NNNN.md` are authoritative.
`current.md`, domain `INDEX.md` files, and the root memory index are derived views.
The helper publishes a complete immutable file without replacing an existing
one, then refreshes affected views. Episodes, reviews, and reconciliations do not
regenerate lesson views/indexes. A lesson updates its own `current.md`, its domain
preview, and root counts; byte-identical generated text is not rewritten.
It serializes cooperating readers/writers through a
store lock. If the process dies between publication and view refresh, inspection
and `reindex --repair` rebuild views from accepted revisions. It does not discard
evidence. A revision cannot change a lesson's ID, domain, or original creation
time; its next number must be contiguous. `check` compares expected indexes with
disk; missing indexes are reconstructed by `reindex`. `reindex --repair` also
permits rebuilding stale current views, while retaining full canonical validation.
Unknown files are not deleted or advertised as generated continuation pages.

Older helpers do not implement `navigate` and expect the former index formatting
in `check`; their reindex can recreate unbounded indexes. Upgrade the whole package
from source before using the new navigation. If an old generated index already
exceeds the old reader limit and blocks installation/bootstrap, run the **new source
helper** with `reindex --repair --root TARGET`, then install normally from that
source. See the source package's installer guide for shell examples. This replaces
only reconstructible views/indexes, never moves or republishes accepted history,
and does not relax canonical size, schema, link, lock, or path checks.

On native Windows the initial supported storage target is local NTFS. Publication
uses `os.link` to expose a complete file without replacing an accepted record;
views use `os.replace`. An unsupported hard link, sharing violation, unreadable
subtree, or lock error is visible and never triggers an overwrite fallback.
This is not a power-loss or hostile-concurrent-editor guarantee. Synchronized
folders, network shares, and other Windows filesystems have not been verified.

Normal edits must not erase historical origin, support, counterevidence,
reconciliations, or predecessors. A correction should explain why earlier
evidence was mistaken while leaving its reference inspectable. Administrative
privacy deletion is an explicit operator procedure: back up appropriately,
redact the sensitive content and repair references with a tombstone. Mettle has no
automated privacy-deletion command; append-only conventions never override a
legitimate deletion request.

The lock directory is `state/.write-lock/`. If a process crashes, inspect its
`owner.json`, verify no writer is running, then remove that lock directory. Never
remove a live lock. Back up before repairing a damaged store. Direct edits and
malicious processes can bypass these conventions; this is not a security sandbox,
a multi-machine database, or an adversarially tamper-proof audit ledger.

## Retrieval and cost

Search defaults to current lesson content/metadata, with optional scope filters
and small operator-editable alias groups. Explicit `--kind episodes` searches
accepted observations and reports correction links, not additional instructions.
Neither route searches workspaces, backups, or old lesson revisions as advice.
Safety validation may read supporting records mechanically; they are not all
injected into model context. Warm search scans cached lexical sequences using the
same tokenizer, phrase aliases, scoped corpus, term frequencies, scores and ties.
It rereads and validates selected canonical records and reported reverse links.
A pending review is excluded only when incorporated into the matched lesson
revision. A correction does not replace the observed episode it corrects.
Episode extensions are not lesson-schema requirements: retrieval uses a string
`domain` and string members of list-valued `tags`, `aliases`, and `scope`. Other
values remain intact as opaque metadata and do not become search terms. Scoped
episode search also retains its title/body substring fallback. This extraction
rule does not tighten accepted schema 1 or rewrite existing episodes; older
catalogue lexical versions are rebuilt automatically.
Every read still enumerates canonical file metadata. These operations grow with
archive size; no constant-time or large-archive latency guarantee is claimed.
Bootstrap reads the small map, profiles, and work headers without loading history.

## Targeted reads and historical discovery

`show ID` and `show L-ID --revision N` reread canonical Markdown. Output remains
record text, suitable for `--output` or `--work`; diagnostics use stderr. There is
no warning inserted into the record. `show L-ID` selects the latest accepted
revision, never the head suggested by `current.md`. An explicit revision selects
exactly that revision or fails. Neither command silently follows a replacement.

A warm targeted read validates file size and UTF-8, schema, kind, ID, canonical
path/metadata agreement, revision, and a normalized-content fingerprint. The
fingerprint uses the same decoded/re-encoded representation as publication (BOM
and line-ending normalization); accepted bytes are never rewritten by reading.
Selected lessons also validate their complete local revision sequence, immutable
identity, evidence retention, and immediate reference types and constraints.
Referenced lessons have their local sequence checked; referenced evidence is
read and structurally checked, without recursively auditing all its links.
Thus a lesson with a long history or many references costs more than an isolated
episode. Latest selected lessons must match their derived current view; a stale
view fails with `reindex --repair` guidance. An older exact revision does not
require a healthy current view. A selected invalid record fails the request; it
is never silently skipped in favor of a lower-ranked hit.

A successful targeted read says nothing about unrelated archive health. Full
`check` audits duplicate IDs, all links, revision sequences, evidence retention,
supersession cycles, current views, navigation, profiles, workspace references,
and any existing catalogue against canonical data. A missing catalogue is normal
after publication. Check reuses one verified snapshot for workspace/cache checks.
Publication, record-related workspace mutations/checkpoints, installation,
migration, and explicit `reindex` retain complete canonical validation.

Use **`search --kind lessons --history TERMS`** to discover all accepted lesson
revisions, including eligible latest revisions, retired/superseded lessons, and
earlier wording absent from the latest revision. Default search continues to
return only latest proposed/active/contested lessons, retaining their real status.
Historical hits report `revision`, `status` at that revision, `latest_revision`,
`latest_status`, `is_latest`, `discovery: historical-evidence`, and the exact
immutable revision `path`. `supersedes`/`superseded_by` describe the matched
revision; `latest_superseded_by` exposes the current replacement reference without
following it. Older does not mean false: an observation can remain useful under
its original conditions even when its former generalization is no longer advice.

Both searches return at most `--limit` records (1–50, default 5), with `total`
and `remaining` counts. Current search can be narrowed by query or scope. For
history, repeat the same query, scope, work ID and limit with **`--offset N`** from
`next_offset`. Offsets refer to the unchanged store/query; restart after a mutation.
History uses the same lexical policy over the all-revision corpus, so its scores
need not equal current-search scores. Ties sort by ID, then ascending revision.
`--history --kind episodes`, negative offsets, and nonzero offsets without
`--history` are rejected. Episodes remain separately labelled observations.
Closed activities remain discoverable through `work list --status all/closed`
and its existing query support; they are not part of accepted-memory search.

### Disposable catalogue and recovery

Private `state/memory/catalogue.sqlite3` is derived format 1, not accepted record
schema 1. It stores canonical references, metadata, lexical sequences, normalized
source fingerprints and reverse relationships. No body is served from it. It is
root-bound and disposable; source installations deploy `mettle_catalogue.py`
alongside the other helper modules. The private package remains git-ignored.

Each targeted command compares an inventory of canonical relative paths, file
sizes, modification/change timestamps, and device/inode identities. It also
checks catalogue format, root, structural integrity and path coverage. Unchanged
warm reads make no catalogue writes. Missing, structurally corrupt, incompatible,
or inventory-stale catalogues rebuild under the existing store lock from a fully
validated snapshot. A cold rebuild can therefore fail on unrelated broken
canonical history; reading cached content is never a fallback. Navigation uses
cached latest metadata and validates exposed lessons (one representative per
domain on domain-list pages); previews remain bounded and non-authoritative.

Publication removes the catalogue **before** writing accepted bytes. If accepted
publication succeeds but view/cache maintenance is interrupted, the next read
must rebuild or fail visibly; it cannot serve the previous cached head. Run the
source/installed helper's **`reindex --repair --root ROOT`** to rebuild current
views, bounded navigation and the catalogue, then `check`. Accepted records are
validated, not repaired from the cache. Existing workspace publication retries
remain supported. Do not remove a live lock to force repair.

Metadata inventories detect ordinary out-of-band additions, edits, deletion,
backup restoration and supported relocation. After any external archive
maintenance, run explicit repair even if automatic change detection succeeds.
Metadata is not arbitrary tamper detection: an edit preserving the observed
metadata of an unselected file can affect completeness until repair. Returned
canonical content is always rechecked. A logically edited/damaged cache may
fail visibly with repair guidance; full check compares its content and links to
canonical data. Do not edit the cache or use it to reconstruct accepted memory.
Profiles, vocabulary, workspaces and accepted history survive rebuild unchanged.

Upgrade the entire helper package. Older helpers ignore this cache but do not
share its read contract or historical-search interface. Do not run old/new
writers concurrently. After an older helper or backup has been used, reinstall
0.4.0+ and run `reindex --repair` before relying on targeted reads. No accepted
records need moving, republishing, or a new pilot-file migration.

A score is a lexical ranking, not confidence, truth, or measured causal utility.
No matches is valid. Bootstrap logs character counts, not fabricated token
counts. Record actual provider-reported tokens separately for task execution,
retrieval context, reflection, and reconciliation; use `unknown` when unavailable.

## Decision-to-review trace

The following strengthens the contents of existing review sections. It does not
add required metadata fields or change schema 1. The validator checks section
presence, assessment type, and references; it does not verify the truth of the
prose, authorization decisions, or a claimed causal explanation.

| Existing section | What a meaningful decision review should retain |
|---|---|
| Situation | Current request or standing goal; activity origin, opportunity, selection reason, and component; candidate ID/revision; terms from this context versus prior hints. |
| Application | Applicability and current authorization; applied, rejected, or deferred decision; observable action or deliberate non-application. |
| Outcome | Exact artifact, test, source, or attributed feedback; what was observed and what remains unknown. |
| Assessment | Support, counterexample, uncertainty, non-application, misapplication, or obsolescence; scope and what needs review next. |

Use `assessment: not_applied` for a rejected candidate, and for a deferred
application that did not occur. Explain the reason in Application and unresolved
questions in Assessment. Do not classify a justified refusal to apply a procedure
as evidence that the procedure works. In particular, its review cannot enter a
lesson's `support` array. A candidate with no relevant later outcome stays proposed.

If there were no candidates, record a meaningful retrieval miss in an episode,
not a review with a fabricated lesson reference. Keep this selective: a routine
successful search does not require a new record solely because a command ran.
Do not include hidden reasoning or the entire session; retain a concise, checkable
decision and its source evidence.

Preserve exact technical terms in `title`, `tags`, and `aliases`, and explicit
component/applicability boundaries in `scope` and the Trigger/Exceptions sections.
Generated indexes carry explicitly bounded metadata previews; they are not independent
sources of evidence. A procedure may include inputs, steps, stopping conditions,
and verification within the existing Practice/Exceptions/Review plan sections.
It remains a lesson, not a native skill registration or permission grant.

The source package includes `examples/behavioral-review.json`, an entirely
synthetic sequence of authored record metadata and body sections. Its tests
publish a proposed lesson, record justified non-application, link later support,
and retain a subsequent counterexample in a contested revision. Neither the
fixture nor the tests constitute an LLM behavior experiment. The fixture is not
copied into installed state. The runtime does not auto-dispatch its contents.

## Self-model changes and reconciliation

Keep a user's preferences, reusable procedures, and the agent's self-assessments
distinct. A self-assessment needs evidence about the agent's actual behavior, not
only knowledge of a useful method. It should identify scope, runtime/model,
supporting and contradictory cases, uncertainty, and reconsideration conditions.

Before editing a learned assessment, publish an episode whose Evidence section
preserves the prior and proposed text plus exact supporting record/revision
references. State the reason and uncertainty in Interpret/Uncertainty. After
editing, publish another episode that records the observed resulting text or its
verifiable hash and links the proposal in prose. Do not claim an intended edit
happened before checking it. Retain both IDs in the compact current assessment.
For a long learned-disposition section, record the complete affected assessment,
not unrelated profile contents.

This is a protocol obligation using existing episodes, not automatically versioned
profile storage. The helper does not validate those prose references or prevent
direct profile edits. Reconciliation must inspect them. Assigned identity and
commitments remain operator-controlled; do not rewrite the fixed protocol to
promote a learned habit. Revise an assessment when compensation works rather
than maintaining a negative label solely for narrative consistency.

Perform consolidation as a distinct pass over changed lessons and their linked
evidence. The same agent can perform this role after work; Mettle has no background
consolidation service. Preserve original evidence and accepted revisions, and
distinguish a reconciliation plan from the updates actually published. Frequency
of retrieval is not validation, and replacing a summary or Git baseline is not
historical preservation. Operator-authorized privacy redaction remains the
explicit exception described above.

## Experience context and evidence provenance

Meaningful experience can come from assigned work, a standing commitment,
self-directed investigation, a peer interaction, an external observation, or an
experiment. Do not invent a user request to fit the record. Put the relevant
context in Observe (episodes) or Situation (reviews), using concise labels when
helpful:

```text
Activity origin:
Goal or standing commitment:
Opportunity noticed and reason for choosing it:
Permitted boundaries:
Observable action and outcome:
```

These are body prompts, not new required metadata fields. Existing records remain
valid. A later review opportunity may be discovered by the agent when within its
mandate. Pending evidence is not an obligation to run an unauthorized experiment.
Session boundaries can require handoffs without producing learning; the helper
neither schedules work nor automatically loads a private agenda.

For a claim from another participant or an external source, retain three distinct
parts in Evidence/Uncertainty and Outcome/Assessment:

```text
Origin: reporter, underlying source/reference, known shared-source reports.
Examination: what I actually read, inspected, or reproduced; method/conditions.
Assessment: what is supported, exceptions, independence known/unknown, open questions.
```

A specialized result may be retained as reported without local reproduction.
"Reproduced" does not mean "universally true"; "reported" does not mean "useless."
These are not an automatic confidence ladder. Peer agreement and repeated reports
of one result are not independent evidence. A reported fact need not become a
procedural lesson, and neither justifies a self-assessment without evidence about
the agent's own behavior. A peer can propose a correction, not rewrite private
state or expand permissions.

The helper validates references and section structure, not provenance prose or
source independence. It cannot determine whether a cited test actually happened.
Use attributed observations and verifiable artifacts, and preserve uncertainty.

## Recover a mistaken lesson update

Semantic recovery restores a usable practice after a bad update. It is distinct
from repairing files with `reindex --repair` or restoring an installation backup.
Within its delegated learning scope, the agent can perform it without a routine
human approval queue. Current operator restrictions still apply.

Suppose L-example@1 is a narrow useful practice, @2 is a harmful generalization,
and later evidence challenges @2. Recovery publishes @3; it never deletes @2.
Use the existing commands and schema 1, not a new RECOVER enum or rollback CLI:

1. Read the current revision and the earlier source revision. Inspect intervening
   reviews and check that the older prerequisites still apply now. Use current
   metadata as the draft base; do not start with an old metadata snapshot that
   omits newer evidence.
2. Record the detected problem in an episode and review as appropriate. When a
   material issue is unresolved, contest or retire the practice rather than
   blindly reinstate an earlier one.
3. Publish a reconciliation with `operation: REVISE`, including the current exact
   revision in `inputs` and relevant episode/review IDs in `evidence`. Name the
   earlier source revision, restored parts, rejected parts, prerequisite checks,
   and uncertainty in Decision and Planned changes. Both revisions can be listed
   in `inputs` when useful.
4. Increment the current revision. Keep its origin, support, counterevidence,
   reconciliations, and predecessor references; add the new reconciliation and
   evidence. Restore only the still-applicable practice and exceptions. A retained
   historical support entry is not automatically support for the recovered scope.
   Reassess status; use `proposed` or `contested` when warranted, rather than copying
   the old `active` label.
5. Publish with `--expected-revision` equal to the current revision. On a conflict,
   reread and reconcile; do not force an old plan over newer state. Verify the
   published current record with `show` and `check`, and record a later applicable
   review when evidence becomes available.

For a synthetic @2 → @3 recovery, these are argument sequences to append to the
installed `LOCATION.md` executable/argv prefix. Substitute actual IDs and new
local draft filenames; edit drafts before publication:

```text
show L-example --output current-draft.md
show L-example --revision 1 --output earlier-reference.md
template reconciliation --output recovery-reconciliation.md
publish recovery-reconciliation.md
publish current-draft.md --expected-revision 2
show L-example
check
```

The reconciliation records intent. If final publication fails, it does not mean
the recovery happened. Existing immutable revisions remain the history, and the
current record establishes the result. The helper does not infer the right older
practice, choose its scope, or verify the semantic quality of the recovery.

For a mistaken learned self-assessment or disposition, use the recorded before/
proposed/after episode procedure above. Do not restore entire profile backups
that erase unrelated learning or change protected identity. Profile history is
still a protocol discipline, not an automatically enforced versioning engine.

`tests/test_agent_owned_learning.py` exercises synthetic recovery and publication
guards, an external report that does not automatically validate a lesson, and
non-task episode contexts. These are storage/protocol contracts, not evidence
that an LLM selected an activity or learned autonomously.


## Workspace-aware records (0.2.0)

Use `template KIND --work W-ID` and `show ID --work W-ID` for mutable drafts, then
publish their returned paths. Schema 1 and accepted revision semantics are
unchanged. New workspace drafts can carry an optional `provenance` object with
work ID, explicitly known session/runtime/model, protocol version, and hash.
Old records and unknown history are not backfilled. A workspace ledger links the
exact draft bytes to accepted IDs/revisions and supports publication retry after
interrupted bookkeeping. It is not another accepted record kind.

A scoped proposed lesson may follow one meaningful event; later local support,
untested generalization, and causal attribution should be assessed separately.
Activity checkpoints support that decision but cannot validate its reasoning.
`search --kind episodes` explicitly retrieves observations when lessons do not
fit; follow correction links and do not treat drafts as evidence. See
[workspace and migration details](workspaces.md), installed as WORK_REFERENCE.md.
