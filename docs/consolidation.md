# Agent-owned consolidation

## Design decision (0.5.0)

`work consolidate W-ID [--records REF ...] [--query TERMS ...] [--limit N]
[--offset N]` produces an informational, transient review packet. It uses the
existing activity, catalogue, exact accepted references, and targeted validation.
It never publishes, changes status/profile/notes, or records a checkpoint.

Selection starts with up to eight explicit references, or eight recent distinct
activity publications. A focused query contributes up to five historical lesson
matches using the existing lexical ranking. Direct relationships take priority
over incidental matches. Up to eight related lesson revisions supply context;
their immediate evidence, reviews, corrections, and replacement links are exposed.
A correction seed also uses its direct corrected observations for reverse
discovery of dependent reviews/lessons. Up to eight review records (explicit inputs
first, then counterexamples, then other reviews) expose their source episode
pointers before correction lookup. These are fixed evidence paths, not recursive
graph traversal. Pagination covers this selected set, not the whole archive.
Omitted seeds, lexical matches, lesson/review expansion, counterevidence and page
items are reported separately with detail/continuation routes.

Each page has at most 30 items (default 12) and 16,000 serialized UTF-8 bytes,
including JSON indentation, notices, and continuations. Previews are optional;
identities and canonical paths are never shortened. A reference whose full path
cannot fit is explicitly reported with a `show` route. Inputs have a 2,048-byte
budget; split larger requests. Returned argument arrays follow the executable
prefix in LOCATION.md, avoiding shell quoting assumptions.

One catalogue opening/inventory serves the packet. Warm selection scans cached
metadata and, for a query, cached lexical features; it does not decode unrelated
canonical bodies. Returned records and explicit seeds use existing targeted
checks, which can read their lesson history and immediate references. A cold or
stale catalogue still needs a healthy full snapshot. Full `check`, publication,
installation, and `reindex --repair` retain whole-store validation. No new cache,
packet format on disk, learning status, or mutation contract is introduced.

The agent judges meaning. A finding/interpretation uses an episode (and `corrects`
when appropriate); an assessment uses a review of an exact lesson revision;
practice changes use reconciliation plus actual lesson publication. Retain or
defer may need only an existing checkpoint/handoff. A reconciliation is intent,
never proof that the planned revisions exist.

## When and how to compare

Use this route when a correction, counterexample, later outcome, overlapping
practice, changed environment/source/model, or newly available evidence makes a
comparison useful. Repeated difficulties or successes can prompt inspection;
their count is not a learning criterion. Do not wait for closure, or require a
pass at every checkpoint. Checkpoint preview points here without loading a packet.

Append commands to the executable/argument prefix in LOCATION.md:

```text
work consolidate W-ID
work consolidate W-ID --records E-ID V-ID L-ID@2 --query cache freshness --limit 12
work consolidate W-ID --records E-ID --offset 12 --limit 12
show L-ID --revision 2
search --kind lessons --history --limit 5 cache freshness
```

A bare lesson ID resolves to its latest exact revision; `L-ID@N` selects exactly
that revision. Missing/invalid explicit inputs fail visibly, even if off-page.
The default seeds are the activity's recent accepted publications, not its drafts
or notes. `work history W-ID --kind publications` finds older seeds; `work list
--status all --query TERMS` finds earlier activities. Search spans accepted memory
across activities. Query-only and no-matching-lesson cases are valid.

The helper exposes lexical matches and recorded relationships, not semantic
agreement, contradiction, independent confirmation, or authority. Historical hits
retain immutable paths, original status, and latest status. `current_candidate`
means latest and eligible for ordinary search, not proven effective. A proposed or
contested practice retains that status; retired/superseded wording is history.
The packet does not silently substitute a replacement for the matched lesson.

1. **Establish previous understanding.** Read the full exact record: what did it
   claim, under which conditions, based on which evidence?
2. **Examine new evidence.** Distinguish reported, inspected, and reproduced facts
   from interpretation. Identify which assumptions the evidence bears on.
3. **Compare before deciding.** Does it support the existing scope, reveal an
   exception, contradict an interpretation, reflect changed conditions, or describe
   a different situation? Repeated summaries of one incident and citations of one
   source are not independent experiences; unknown independence remains unknown.
4. **Decide what changes and what remains valid.** Retain or defer can be correct.
   A colleague, optional Loom discussion, local file, source document, user
   correction, or experiment can contribute evidence. None grants new authority,
   and not every external claim must be reproduced locally.
5. **Publish and verify when warranted.** Read full relevant records first, use
   current expected revisions, preserve evidence, and inspect actual outputs and
   retrieval. A useful retrospective interpretation is not a validated practice.

## Outcomes using existing records

| Decision | Existing route |
| --- | --- |
| Retain useful subject knowledge or revise an interpretation | Episode; use `corrects` for a genuine correction. Preserve the earlier observation and explain what remains valid. A qualification need not call it false. |
| Assess a later application or apparent exception | Review of the exact earlier lesson revision, with actual conditions, outcome, evidence and assessment. Do not fabricate support for an inapplicable case. |
| Narrow, link evidence, contest, retire, or replace a practice | Reconciliation naming exact inputs, then a new lesson revision retaining old evidence/counterevidence and the reconciliation link. Proposed remains a valid status; earlier support does not validate a broader scope. |
| Merge compatible practices | Establish compatible scope first; shared vocabulary is insufficient. Use the merge procedure in REFERENCE.md: new proposed lesson with predecessor links, evidence and aliases, then individual superseded revisions with expected-revision guards. No evidence inflation or atomic multi-record transaction. |
| Change self-assessment/dispositions | Only evidence about the agent's own behavior qualifies. Use the existing before/proposed and actual after-text/hash episodes. Record model/runtime/environment transfer limits. Repeating an old failure is not new evidence; no personality quota. |
| Update a known authorized instruction derivative | Consider the changed source lesson and use the existing traceable editing procedure. No automatic promotion; unrelated instructions, activation block, fixed protocol/tools, identity, credentials, budgets and mandate stay protected. Editing does not establish runtime reload. |
| Retain / no change / defer | A meaningful new assessment may merit a review. Otherwise use ordinary checkpoint/handoff; do not duplicate a lesson or make an artificial reconciliation. Defer with a question/revisit condition, not a schedule. An episode-only result can finish with `no-update --records E-ID`. |

## Bounds, continuation, and recovery

The packet previews only selected records. `omissions` distinguishes explicit
inputs absent from this page, older activity seeds, extra lexical matches,
unexpanded lesson contexts, and known counterevidence absent from this page
(including earlier pages). Direct corrections and counterexamples precede
incidental matches, but explicit seeds take first priority. Counterexample items
say whether the current lesson incorporates them. “None included” never establishes
“none exists.” Reviews point to exact lesson revisions; inspect their full record
for source conditions and applicability. `source_episodes_expanded` marks reviews
whose direct source episode pointers were included in correction discovery.
`review_sources_not_expanded` counts reviews not examined along that path;
`review_sources_next_argv` expands the first such review as an explicit input.
An unexpanded review item also has its own `expand_sources_argv`. These routes can
reveal additional corrections even when `counterevidence_known` is zero. They do
not imply that the review or practice is false. Item/byte pagination still applies
to all source pointers and discovered corrections; arbitrary correction chains
and the rest of the evidence graph are not recursively followed.

Use `next_argv` for the rest of this selected set; on an unchanged store pages are
deterministic and non-overlapping. Use `lexical_next_argv` for additional historical
search matches, then select useful references explicitly. `show ID --revision N`
opens any exact lesson; non-lessons use `show ID`. Rerun with a selected reference
in `--records` to expand its immediate context. An exceptionally long path may be
reported in `path_exceeds_page` with its exact detail command instead of a row.
The canonical record and identity are never truncated. Changed stores may change
page membership: restart at offset zero after publication or out-of-band changes.

Save the current question, exact references, provisional assessment, actual
published outputs, unresolved issue and next useful action concisely in WORK.md.
This is a handoff, not a mandatory form or a copy of every record. Pausing requires
no packet persistence. On resumption, inspect current relevant heads. An obsolete
expected revision must fail; refresh the comparison rather than overwrite.

Before claiming completion, verify the accepted outputs exist, current search
returns the intended guidance, retired/superseded guidance stays excluded, and
historical wording and counterevidence remain inspectable. A reconciliation alone
does not establish an applied change. The existing `reconcile` checkpoint still
requires an actual linked published revision; a partial multi-record change stays
partial in the handoff. Recover from saved notes and accepted records, not a
supposed replay log; use unchanged-input retry and existing immutable-ID guards.

Catalogue freshness/path protection and repair are unchanged from targeted access.
Warm calls enumerate protected canonical file metadata once, scan compact cached
metadata, and optionally rank the historical lexical corpus once. This is not
constant-time search. Targeted reads may decode local lesson histories and direct
references; there is no fixed bound on that validation cost. The selected activity's
publication ledgers are read for continuity. Cold/stale caches require full
canonical validation; missing/corrupt caches rebuild, or fail with the existing
repair guidance. `reindex --repair` never repairs accepted evidence from a cache.
Run `check` for complete integrity; a successful packet is not a whole-store audit.

Source installation upgrades 0.4.0 in place, adding the module and this reference
while preserving profiles, vocabulary, workspaces, accepted bytes and authorized
instruction content. No canonical schema/workspace-format or catalogue-format
migration is needed. Old helpers cannot run `work consolidate`; do not mix writers
of different helper versions. Existing downgrade boundaries in targeted-access
documentation still apply. No scheduler, new learning store, automatic semantic
decision, or stronger crash guarantee is supplied.
