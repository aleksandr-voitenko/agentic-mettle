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
