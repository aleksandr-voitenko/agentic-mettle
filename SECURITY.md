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

The installer requires the designated root AGENTS.md and rejects symlinked state
paths. It does not change AGENTS.md or CLAUDE.md. Generated runtime files contain
absolute paths; rerun configuration after moving the checkout. Installation is
atomic per file, not a transaction spanning all configs.

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
