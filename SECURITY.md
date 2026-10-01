# Security, privacy, and operational boundaries

Agentic Mettle is an experimental local protocol and helper, not a sandbox,
credential manager, or proof that a model will follow its instructions.

## Before enabling hooks

Inspect the deployed Python helper, fixed protocol, and exact hook commands.
Use the runtime's normal project trust and hook review mechanisms. Do not bypass
trust, grant the entire home directory, or change repository policies merely to
make a test pass. Config files are merged and changed versions backed up; review
both the resulting config and machine-local backups before sharing them.

The helper uses only the Python standard library and makes no network or model
calls. The **agent runtime** may transmit anything it reads to its configured
model provider, including local profiles, source excerpts, and memories.

## Trust boundaries

Identity and assigned commitments are operator-maintained. Learned dispositions,
self-assessments, and experiences are fallible data. They cannot grant authority
or override system/user instructions, component requirements, or permissions.
Native hook context has the runtime's instruction priority. Labelling mutable
memory as data reduces ambiguity but does not provide technical isolation against
prompt injection. Never put secrets or arbitrary third-party instructions in a
profile to make them load automatically.

Accepted records must normally be published through the helper. It validates
schemas, paths, references, and revision history, but it cannot verify causal
truth, prevent a model inventing evidence, or stop another program editing files.
The lock serializes helper operations, not independent concurrent agent lives.
Run one authoritative writer for the single V1 personality.

## Filesystem and retention

The installer uses the explicitly designated target directory and creates a
minimal root AGENTS.md if missing, after configuration and history validation.
It preserves an existing AGENTS.md and uses exclusive publication so that
creation cannot overwrite a concurrent operator edit. Symlinked root instruction
files and state paths, Windows junctions, and other reparse-point entries are
rejected. Archive traversal checks entries before descending and reports
unreadable subtrees. Windows
drive-relative paths, reserved device names, trailing dots/spaces, alternate data
stream syntax, and case-insensitive logical ID collisions are refused on Windows.
New IDs/domains must be portable on every OS. Existing POSIX-only histories
remain readable on POSIX; on Windows incompatibilities are reported, never
silently renamed or discarded.
It does not edit existing instructions or create CLAUDE.md. Generated runtime
files contain absolute paths; rerun configuration after moving the checkout.
Installation is atomic per file, not a transaction spanning all configs.

Native Windows support initially targets **local NTFS**. Other Windows
filesystems, network shares, synchronized directories (including cloud-backed
reparse points), and unusual case-sensitivity settings are not qualified. A
fully written/flushed temporary file is published with `os.link` for immutable
records; `os.replace` updates generated views. There is no unsafe copy/overwrite
fallback if the filesystem refuses those operations. Cooperating helper readers
take the same lock as writers. Sharing violations, lock contention, and I/O
errors remain visible. This does not promise power-loss durability or defend
against a hostile process racing path checks or editing the archive directly.

The installer validates a concrete Python 3.11+ executable and generates UTF-8
launches. Claude's exec form needs no shell. Codex's native Windows hooks use
CMD; `%` and `!` in executable/target paths are refused before any installation
writes because CMD can expand them inside quotes. Runtime trust and hook approval
remain necessary. No execution-policy bypass is generated. JSONC requires a
manual merge; changed JSON configurations retain their exact original bytes in
backups. Reconfiguration changes operator-owned launches, never learned history.

Mutable state is ignored by the installed package's .gitignore. Git ignore rules
are not privacy protection, backup, or permission separation. Use appropriate
filesystem permissions and an explicit backup/retention policy. Avoid storing
credentials, unneeded personal information, complete command environments, or
unredacted transcripts. Evidence can be a minimal excerpt and a source reference.

Append-only means normal historical preservation, not a denial of authorized
erasure. V1 has no automated erasure command. An operator can redact sensitive
material and leave non-sensitive tombstones explaining affected references,
then run validation. Do not publish private evidence in bug reports.

## Recovery and reports

A stale current view is recoverable with `reindex --repair`; this does not alter
immutable revision files. Before removing a stale `.write-lock`, establish that
no writer is running. Back up the store before manual repair. A failed schema
check is not permission to delete contradictory evidence until the check passes.

Report reproducible issues through the repository with synthetic/redacted data.
Do not disclose exploitable private-project details publicly. Runtime loading
failures and longitudinal behavioral failures should be reported distinctly.
