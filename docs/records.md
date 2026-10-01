# Record format and lifecycle

All record files are UTF-8 Markdown. Generated files use UTF-8 without a BOM and
LF line endings. User-edited inputs can have a UTF-8 BOM and CRLF; other encodings
are rejected rather than guessed. Accepted historical bytes are not rewritten
when read or reindexed. The first block contains **JSON** between
`---` delimiters. JSON is used to keep the helper dependency-free; arbitrary YAML
syntax is not supported. Markdown bodies remain readable with normal tools and
`grep`/`rg`. Run `template KIND --output draft.md` to generate a correctly shaped
draft with a unique ID, without relying on shell redirection encoding. The
output must be a new file; no overwrite option is provided. Omitting `--output`
retains stdout. A draft is not accepted evidence until published.

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
1 with status `proposed`. `active` requires at least one later supporting review;
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

## Authority and recovery

Accepted records and `lessons/DOMAIN/L-ID/revisions/NNNN.md` are authoritative.
`current.md`, domain `INDEX.md` files, and the root memory index are derived views.
The helper publishes a complete immutable file without replacing an existing
one, then refreshes views. It serializes cooperating readers/writers through a
store lock. If the process dies between publication and view refresh, inspection
and `reindex --repair` rebuild views from accepted revisions. It does not discard
evidence. A revision cannot change a lesson's ID, domain, or original creation
time; its next number must be contiguous.

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
redact the sensitive content and repair references with a tombstone. V1 has no
automated privacy-deletion command; append-only conventions never override a
legitimate deletion request.

The lock directory is `state/.write-lock/`. If a process crashes, inspect its
`owner.json`, verify no writer is running, then remove that lock directory. Never
remove a live lock. Back up before repairing a damaged store. Direct edits and
malicious processes can bypass these conventions; this is not a security sandbox,
a multi-machine database, or an adversarially tamper-proof audit ledger.

## Retrieval and cost

Search only matches current lesson content/metadata, with optional scope filters
and small operator-editable alias groups. It does not return archived revisions
as current advice. Safety validation may read supporting records mechanically;
they are not all injected into model context. Search is linear in local memory,
not the millions of lines of project code. A future index can optimize this
without changing the protocol or record IDs. `show --revision N` is an explicit
historical lookup, not permission to follow obsolete instructions.

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
| Situation | Current request and component; candidate ID/revision; relevant terms from the request versus prior context; why the candidate was considered. |
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
Generated indexes already carry the relevant metadata; they are not independent
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
evidence. The same agent can perform this role after work; V1 has no background
consolidation service. Preserve original evidence and accepted revisions, and
distinguish a reconciliation plan from the updates actually published. Frequency
of retrieval is not validation, and replacing a summary or Git baseline is not
historical preservation. Operator-authorized privacy redaction remains the
explicit exception described above.
