# Targeted access design decision (0.4.0)

Recorded before implementation for PR 2. Accepted Markdown and immutable lesson
revisions remain the authority; record schema 1 and workspace format 2 stay intact.

- `show`, ordinary `search`, and `navigate` use a disposable, versioned SQLite
  catalogue under private state. It contains exact canonical references, normalized-content
  fingerprints, metadata, lexical sequences, and reverse relationships. Returned
  records always come from reread canonical files, never cached bodies.
- Every read compares a metadata inventory of canonical paths, sizes, modification
  and change times, device/inode identities. This is O(files/directories), not an
  archive decode. The catalogue is bound to its resolved root and format/lexical
  version. Missing, incompatible, structurally corrupt, or inventory-mismatched catalogues
  rebuild from a fully validated snapshot under the existing operation lock.
- Targeted reads check size/UTF-8/schema/kind/ID/path/revision and source content.
  A selected lesson reads its own complete revision sequence, checks contiguity,
  immutable identity and evidence-retaining transitions, and validates immediate
  reference identities/types and evidence/reconciliation constraints. Referenced
  records are checked structurally; their links are not recursively audited.
  Directly referenced lessons also have their own sequence checked. Selected
  latest lessons must agree with their current view; stale views fail with repair
  guidance. Historical reads use exact immutable revisions.
- Latest selection is derived from canonical inventory and lesson revision paths,
  never from `current.md`. A helper invalidates the catalogue before publishing
  accepted bytes. Interrupted publication therefore requires a full rebuild or
  visible repair, rather than serving an old head. Warm unchanged reads do not
  rewrite the catalogue. Explicit reindex rebuilds it from canonical material.
- Publication, workspace record mutations/checkpoints, installation, migration,
  and explicit `check`/`reindex` retain full validation. Check reuses its verified
  snapshot for workspace and existing-catalogue validation. Bootstrap/work continuity remain lightweight.
- Search retains the existing tokenizer, phrase expansion, scoped corpus,
  frequency/score calculation, ties, rejections and relationship meanings.
  `search --kind lessons --history` searches all revisions; each hit carries the
  matched and latest revision/status, exact revision path and supersession links.
  Default search still uses eligible latest revisions only. Historical pagination
  uses an explicit offset with unchanged query/filters/store.

The model assumes cooperating helpers and explicit repair after external archive
maintenance. Metadata is a change detector, not arbitrary tamper detection. A
canonical content fingerprint is rechecked for returned material; an undetected
metadata-preserving edit to an unselected record can affect completeness until
`reindex --repair`. A targeted success is not a whole-store health certificate.
Cold reconstruction may fail on unrelated damaged canonical history; no quarantine
or cached-content recovery is introduced. Out-of-band edits/additions/deletions,
backup restoration and relocation are reconciled by explicit full repair.

No consolidation, automatic promotion/retirement, scheduler, service, model calls,
new activity catalogue, or new canonical store is part of this decision.

## Call-path boundary

| Entry point | Canonical validation |
|---|---|
| `show`, `search`, `navigate` | Inventory/catalogue freshness, then selected material and local dependencies; cold rebuild takes one full snapshot. |
| `publish`, including workspace draft retry | Existing full snapshot guards, followed by immutable publication and selective view maintenance; invalidate catalogue before publication. |
| `work checkpoint`, `work reject` | Existing complete accepted-record validation. |
| `work list/show/history/update`, drafts and evidence attachments | Existing workspace/path/content checks; no new archive dependency. `show --work` also uses the targeted record checks. |
| `check` | One complete snapshot shared with workspace validation and an audit of any present catalogue. |
| `reindex [--repair]` | One complete canonical snapshot, derived views/navigation/catalogue rebuilt from it. Repair may tolerate stale derived views, never invalid canonical data. |
| Source installation / legacy migration | Existing complete canonical guards at their respective preflight/apply boundaries; install rebuilds disposable catalogue after deployment. |
| `bootstrap` | Required protocol/profiles, bounded navigation orientation and optional work headers; no catalogue or accepted archive. |

The existing workspace publication retry and installer/migration boundary checks
remain in place; this PR does not change mutation safety to reduce their scans.
