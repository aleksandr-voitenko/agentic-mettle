# Activity workspaces, retrieval, and safe legacy migration

Version **0.2.0**, within the experimental V1 pilot. This adds working-state
management, not another personality, an autonomous scheduler, or a new accepted
memory schema. Normal learning remains agent-owned within its existing mandate.

## Layout and authority

```text
.agent-personality/
├── PERSONALITY.md                 # Fixed operating protocol
├── LOCATION.md                    # Machine-specific launch information
├── REFERENCE.md                   # Installed accepted-record reference
├── WORK_REFERENCE.md              # This document, installed
├── tools/                         # Maintained helper modules; no scratch files
└── state/
    ├── personality/               # Current assigned identity and learned views
    ├── memory/
    │   ├── episodes/              # Accepted observations, not instructions
    │   ├── lessons/               # Accepted conditional practices and revisions
    │   ├── reviews/
    │   ├── reconciliations/
    │   └── evidence/<sha256>/      # Preserved supporting artifacts
    ├── work/
    │   ├── INDEX.md               # Generated navigation, not instructions
    │   └── W-<id>/
    │       ├── WORK.md            # Mutable handoff, checkpoint/publication ledger
    │       ├── drafts/            # Record drafts, created only when needed
    │       └── artifacts/         # Temporary reports/logs/scripts, never auto-run
    ├── migrations/M-<id>/         # Local migration journal and original bytes
    ├── backups/                   # Internal installer and imported recovery copies
    └── sessions/                  # Runtime audit records
```

A workspace follows an **activity across sessions**, not a runtime session or
identity. Several workspaces still belong to one personality and one authoritative
writer. Product code and maintained tests remain in their normal repository
locations. A published `proposed` lesson is accepted memory, not an unpublished
draft. Accepted history is not changed by moving working files.

Bootstrap supplies at most five compact unfinished-work pointers, the omitted
count, and its actual `session_id` when supplied by the runtime. Use `work list`
and `work show ID` for more detail. It does not load every handoff or establish a
new mandate. The current snapshot's session ID can be passed explicitly to draft
creation; do not guess from the most recent audit, which may belong to another
session. Large context still fails visibly instead of silently trimming profiles.

## Commands

From the installed helper's absolute location (or source with an explicit root),
append these arguments to the interpreter/argv prefix in LOCATION.md. In the
examples `$Python` is the selected Python 3.11+ console executable and `$Mettle`
is the installed `tools/mettle.py`. Set paths explicitly, not from a component
working directory.

```powershell
$Python = 'C:\Path\To\Python\python.exe'
$Project = 'D:\path\to\project'
$Mettle = Join-Path $Project '.agent-personality\tools\mettle.py'
& $Python -X utf8 $Mettle work start --title 'Investigate generated bindings' --scope 'components/example; authorized investigation'
# Copy the returned W-ID. No personality ID is created.
& $Python -X utf8 $Mettle work show W-ID
& $Python -X utf8 $Mettle template episode --work W-ID --session-id CURRENT_SESSION --runtime codex --model KNOWN_MODEL
# Edit the returned UTF-8 draft; never invent a model or session identifier.
& $Python -X utf8 $Mettle publish 'D:\path\to\project\.agent-personality\state\work\W-ID\drafts\E-ID.md'
& $Python -X utf8 $Mettle work update W-ID --status paused --next-action 'Inspect the remaining generator boundary'
```

On POSIX use the same arguments with your selected Python executable and absolute
helper path. For source commands, root precedes the work subcommand:
`python3 -X utf8 mettle.py work --root /project start --title TITLE --scope SCOPE`.
Other commands accept their existing `--root` option.

`template ... --work ID` and `show ID --work W-ID` (alias `--output-work`) create
new files in `drafts/`; they never overwrite. `show` copies the accepted revision
as-is: explicitly edit a lesson draft's next revision and preserve its metadata
before publishing with `--expected-revision N`. The normal explicit `--output`
and stdout forms remain supported, but managed draft output is refused in the
package root, tools, personality, and accepted-memory directories.

New workspace drafts record work ID, helper/protocol version and protocol hash.
Episodes use an explicit `--session-id`, then `METTLE_SESSION_ID` or
`CODEX_THREAD_ID` when available, otherwise `unknown`; no newest-audit fallback
is used. Runtime and model are explicit when known. Do not pass the literal
placeholders in the example as if they were real provenance. Existing accepted
records, timestamps, and unknown historical sessions are never backfilled.

Publication from a managed workspace records the exact draft hash, accepted ID
and revision, accepted path, and accepted hash in WORK.md. Drafts are retained.
If record publication succeeds but ledger updating is interrupted, rerun
`publish` on the same unchanged draft. The helper verifies that its content
matches the accepted record before repairing the ledger, without duplicating the
record. A same-ID content mismatch is a conflict. After an interrupted generated
view update, run the existing `reindex --repair`, then retry publication.
The original non-workspace duplicate-publication behavior remains unchanged.

WORK.md uses JSON frontmatter and editable Markdown notes. Use commands for
managed fields. Its contents are operational data, not accepted memory or
instructions. Helpers serialize mutations with the store lock; direct edits and
independent concurrent sessions are not coordinated by that convention.

## Learning checkpoint, not a lesson quota

```text
work checkpoint W-ID
work checkpoint W-ID --decision propose --reason "A bounded candidate is published; later application remains pending" --records L-ID@1
work checkpoint W-ID --decision defer --reason "No later applicable outcome yet" --next-review "Next change to this component's generated interface"
work update W-ID --status closed --next-action "Implementation complete; the lesson awaits its recorded future trigger"
```

With no decision, checkpoint returns a bounded packet of this activity's published
records and questions to inspect. Use `--limit` (1–30) and the publication ledger
for omitted items. Also search related accepted memory; this is not a complete
historical analysis or an automated model judgment. The agent chooses `propose`,
`review`, `reconcile`, `defer`, or `no-update`, with an explicit reason. Proposal
and review decisions must reference the appropriate accepted records. A completed
reconciliation must reference both its reconciliation record and a linked lesson
revision; intent alone does not count as a published update. These structural
checks do not validate the reason or establish semantic adequacy.

A single meaningful event may justify a **proposed** scoped practice. Supporting
later evidence may establish local usefulness while cross-platform transfer and
causal attribution remain uncertain. Do not require universal proof before
retaining a narrower candidate, and do not automatically activate one from a
single success. `no-update` and a concrete deferred review are valid outcomes.
Never manufacture episodes, recurrence, success, or a self-assessment to complete
a checklist.

Closing requires a checkpoint for the current activity revision and no changed
or untracked draft files. A new helper-created draft/publication or reopening
invalidates the old checkpoint. Pause instead of discarding unresolved work.
A completed activity may still have a proposed lesson awaiting a future case.
The current closure gate cannot detect semantic changes in directly edited
artifact/Markdown notes; inspect them explicitly. Closing does not delete files.

## Evidence and selective retrieval

Use `work evidence W-ID PATH` to preserve a file from that workspace's artifacts/
under `memory/evidence/<sha256>/<filename>` (maximum 16 MB). It copies bytes
without execution, verifies the destination, and links it in the workspace.
Reference this stable path/hash or a minimal excerpt in the accepted episode.
Do not let durable claims depend solely on disposable scratch material. This
command does not validate the artifact's truth or automatically make a lesson.
Existing external references are not rewritten or retrospectively verified.

`search` still prefers current lessons. Use **`search --kind episodes ...`** as an
explicit fallback when those lessons do not fit. Episodes return their status as
`observation-not-instruction`, their session, and correction links; read the full
record and its corrections before using it. Workspaces, drafts, backups, evidence
blobs, and old lesson revisions are not searched as current guidance.

Matching now uses complete lexical tokens (preserving compound API identifiers),
operator vocabulary aliases, and reduced weights for generic terms. For a query
containing a distinctive term, generic overlap alone is insufficient. There are
no embeddings or guarantees of semantic recall. Inspect missed synonyms and
improve aliases rather than treating a numeric rank as confidence.

`work reject W-ID L-ID@N --query TERMS --reason REASON` records a scoped decision.
`search --work W-ID ...` suppresses only that exact normalized query and revision
while the activity revision is unchanged. Changed queries, new lesson revisions,
new activity revisions, and ordinary search without `--work` reconsider it.
Rejection is not permanent deletion or proof that the lesson is wrong.

## Preview-first migration of existing pilot files

**Stop all agents/writers. Keep a complete pre-upgrade archive first.** Upgrade by
normal installation from this source without `--replace-profiles`; do not use only
`--configure-only`. Existing profiles, accepted history, and handoffs are retained.
New installed files are required before the following commands are available.
Migration is never an automatic installer side effect.

```powershell
$Plan = (& $Python -X utf8 $Mettle migrate-work) | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw 'Migration preview failed' }
$Plan.moves | Format-Table source, destination, category, accepted_record
$Plan.kept | Format-List
$Plan.warnings
# Review all entries. Apply exactly this plan, not a new silently changed one.
& $Python -X utf8 $Mettle migrate-work --apply --expect $Plan.plan_id
if ($LASTEXITCODE -ne 0) { throw 'Inspect the error/journal; do not delete files manually' }
& $Python -X utf8 $Mettle check
& $Python -X utf8 $Mettle work list
```

On POSIX, run `migrate-work`, inspect its JSON, then supply the returned `plan_id`
to `migrate-work --apply --expect TOKEN`. Default preview writes no state, logs,
workspaces, or plan file. JSON output is machine-readable. A changed plan is
refused; it is not silently accepted. The plan can be run from the source using
`migrate-work --root /project` before the source is installed.

The script recognizes record-shaped root drafts, draft-labelled root files,
legacy drafts/ contents, root text/log artifacts, and known installer backup names
at the root or under tools/. Installed files are untouched. Unknown files are
reported for manual review. A draft matching an accepted record is recorded as a
working copy, **never counted as independent experience or auto-published**.
Different/unpublished content is retained as ongoing work, not discarded.

Available `.agent-personality` text is scanned conservatively for filename
references. Referenced files remain at their old paths, listed under `kept`.
This avoids rewriting accepted evidence to accommodate tidying. Files outside
this private tree, excluded binary files, and external conversations are not
fully inspectable; there is no universal reference-resolution guarantee. A
non-UTF-8 possible reference file or excessive scan size stops migration rather
than silently ignoring it. Unknown activity attribution is kept unknown: migrated
work goes into one explicitly labelled paused **legacy-import workspace**.
Backups go to `state/backups/legacy-...`, not memory.

Before any move, the script writes a journal in `state/migrations/M-ID/`. Each
source is copied to `originals/<old-relative-path>`, verified, copied to its new
location, verified, and only then unlinked at the old location. It never overwrites
a conflicting destination. Original draft/artifact bytes, including BOM/CRLF,
are retained; metadata/text normalization is used only for duplicate classification.
Accepted records, revisions, profiles, and preserved evidence are fingerprinted
and must remain unchanged. Git metadata/index/history are neither moved nor
edited; review tracked-file changes separately. There is no deduplication deletion,
age-based cleanup, or execution of a legacy script/hook.

### Interrupted migration and recovery

A stale `.write-lock` is handled by the existing documented operator procedure:
verify no writer is alive before removing it. Do not run new work before resolving
an incomplete migration. Then:

```text
migrate-work --resume M-ID --apply
```

The journal's original plan, source/backup/destination hashes, and protected-state
hashes are checked. Already relocated entries are recognized without duplicating
records. An edited journal or changed file stops recovery for inspection.
Publication is atomic per file, not a power-loss-safe multi-file transaction or
protection against hostile concurrent edits.

To preview restoring the original paths after a completed migration:

```text
migrate-work --restore M-ID
migrate-work --restore M-ID --apply
```

Restore copies originals from verified backups, refusing different content now
occupying an original path. It **retains migrated copies and newer work** rather
than deleting them in an attempted global rollback. A restore can be repeated.
A restored migration is not resumed as if it were still moving files.

Migration plans/journals/backups are private data. Retain them for the next pilot
review. They map old paths to new ones and preserve the installed protocol hash
at cutover, without changing historical session IDs or inferred task ownership.

## Cleanup boundaries

There is deliberately no general cleanup/uninstall command in this iteration.
Published working copies can remain safely inside the workspace. Before any
later manual deletion, verify publication, outstanding work, and references, and
preserve indispensable evidence. Migration's `kept` list is a concrete review
queue, not permission to delete referenced or unknown material. When automatic
migration refuses a case, ask the agent to inspect those specific paths and report
unpublished differences or references; do not ask it to clear the package root
by wildcard.
