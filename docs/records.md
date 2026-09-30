# Record format and lifecycle

All record files are UTF-8 Markdown. The first block contains **JSON** between
`---` delimiters. JSON is used to keep the helper dependency-free; arbitrary YAML
syntax is not supported. Markdown bodies remain readable with normal tools and
`grep`/`rg`. Run `template KIND` to generate a correctly shaped draft with a
unique ID. A draft is not accepted evidence until published.

## Kinds

| Kind | ID prefix | Required body sections | Purpose |
|---|---|---|---|
| `episode` | `E-` | Observe, Evidence, Interpret, Uncertainty | Observable event and explicitly tentative interpretation. |
| `lesson` | `L-` | Trigger, Practice, Exceptions, Expected result, Review plan, Change rationale | Scoped, revisable candidate practice. |
| `review` | `V-` | Situation, Application, Outcome, Assessment | A later assessment of an exact lesson revision. |
| `reconciliation` | `C-` | Decision, Evidence assessment, Planned changes | Evidence-linked explanation of a durable change. |

Common metadata: `schema: 1`, `kind`, `id`, `title`, `created_at` (ISO-8601 with a
timezone). Bodies and required metadata must not retain template TODOs. IDs are
unique within the one store. Timestamps are recorded metadata, not independently
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
`..`, absolute paths, or symlinks. `scope` must state relevant components and
conditions. A source-code path is interpreted relative to root `AGENTS.md`.

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
with the component's `AGENTS.md`.

```sh
M=.agent-personality/tools/mettle.py
python3 "$M" template episode > /tmp/mettle-episode.md
# Fill in real evidence, runtime/model/session, and all body sections.
python3 "$M" publish /tmp/mettle-episode.md

python3 "$M" template lesson > /tmp/mettle-lesson.md
# Add the accepted episode ID to origin; write scoped practice and exceptions.
python3 "$M" publish /tmp/mettle-lesson.md --expected-revision 0
python3 "$M" search generated bindings
python3 "$M" show L-REPLACE_WITH_ACTUAL_ID
```

At a **later applicable opportunity**, publish a new episode and a review that
names revision 1. Keep pending work pending; do not manufacture a successful
application to complete the template. Then publish a reconciliation referencing
`L-ID@1` and the review. Obtain the accepted lesson with `show`, edit a draft to
revision 2, retain the prior evidence arrays, add the new reconciliation and
review, and publish with `--expected-revision 1`.

```sh
python3 "$M" show L-REPLACE_WITH_ACTUAL_ID > /tmp/mettle-revision.md
# Update the draft, not current.md or revisions/0001.md.
python3 "$M" publish /tmp/mettle-revision.md --expected-revision 1
python3 "$M" check
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
