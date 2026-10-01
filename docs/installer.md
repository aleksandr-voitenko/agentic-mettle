# Guided installation and profile construction

Setup is available on native Windows, macOS, and Linux with Python 3.11+ and no
third-party Python dependencies. It writes one repository-local personality;
it does not install models, create fictional experiences, or grant permissions.

## One workflow, two interfaces

`python mettle.py install --root TARGET` opens the wizard when stdin and stderr
are terminals. With `--interactive`, terminal stdin is required. With
`--non-interactive` (alias `--yes`), stdin is never used for questions. A piped or
non-terminal run defaults to non-interactive. `--dry-run` defaults to no prompts;
combine it with `--interactive` to construct a plan in the wizard without applying
it. Prompts and human previews go to stderr; stdout remains JSON.

The target directory must already exist. The wizard can ask for a missing root,
with the current directory as a suggestion that you explicitly accept or replace.
Non-interactive source-checkout commands require `--root`; they never guess from
cwd. An installed helper resolves the designated root from its own location.
A missing root `AGENTS.md` is created; component-level instruction files are never
used as alternative roots.

The wizard chooses adapters, activation placement, interpreter, identity, and
dispositions. Flags supplied alongside `--interactive` take precedence for those
choices. It then validates the complete plan and shows changed paths, selected
profile contents, the activation block, and warnings. Final confirmation defaults
to **no**. Declining, EOF during questioning, or validation failure before applying
leaves the target untouched. Profile text may appear in terminal/JSON logs; do not
supply secrets in profiles.

### Repeatable command-line example

PowerShell (use your actual executable and target):

```powershell
$Python = 'C:\Path\To\Python313\python.exe'
$Project = 'D:\Work\My Project'
& $Python -X utf8 .\mettle.py install --root $Project --non-interactive --runtimes codex claude --agents-position prepend --identity-preset maintainer --agent-name Aster --focus 'Compatibility and recoverable migrations' --disposition-preset deliberate --communication concise --dry-run
```

Remove `--dry-run` after reviewing the plan. On macOS/Linux, use the same flags
with the appropriate interpreter and paths:

```sh
python3 -X utf8 mettle.py install --root /work/project --non-interactive \
  --runtimes codex claude --agents-position append \
  --identity-preset collaborator --disposition-preset balanced
```

`--yes` does not bypass profile replacement checks, invalid input, filesystem
boundaries, or runtime trust. An explicit `--replace-profiles` remains necessary
when selected existing profile contents would change.

## Option reference

| Option | Meaning/default |
|---|---|
| `--root PATH` | Existing designated project root; required for unattended source installation. |
| `--interactive` | Guided setup; terminal stdin required. |
| `--non-interactive`, `--yes` | Never prompt. Use flags, saved choices, and defaults. |
| `--dry-run` | Validate and return changes, hashes, warnings, and profile/block previews without target writes. |
| `--runtimes [codex claude opencode ...]` | Configure/update these adapters. Omitted: saved selections, otherwise detected executables or existing owned adapters. Empty: no adapter changes, not uninstall. |
| `--agents-position append\|prepend\|skip` | Placement of the static managed block. Omitted: saved choice or append. Skip preserves an existing block too. |
| `--python-executable PATH` | Validate and store a stable console Python 3.11+ executable. Default: running interpreter. |
| `--configure-only` | Refresh launch files/activation without updating package or profiles; an existing installation is required. |
| `--identity-preset NAME` | collaborator, reviewer, maintainer, researcher. Missing new identity defaults to collaborator. |
| `--agent-name TEXT` | Optional assigned name; no personality-ID folder is created. |
| `--role TEXT` | Override the selected identity role. |
| `--focus TEXT` | Repeat for up to eight project-focus statements; replaces preset focus statements. |
| `--identity-file PATH` | Use an operator-authored UTF-8 identity instead of a preset/constructor. |
| `--disposition-preset NAME` | balanced, deliberate, exploratory. Missing new dispositions default to balanced. |
| `--communication concise\|explanatory` | Override communication style. |
| `--initiative bounded\|ask-first` | Override initiative within current authorization. |
| `--verification focused\|thorough` | Override check selection without waiving mandatory checks. |
| `--disagreement direct\|gentle` | Override presentation of disagreement, not whether material evidence is disclosed. |
| `--dispositions-file PATH` | Use operator-authored UTF-8 dispositions instead of a preset/constructor. |
| `--replace-profiles` | Allow replacement of explicitly selected existing profiles, with backups. Never resets self-model or memories. |

Identity-file input cannot be combined with identity constructor fields;
dispositions-file input cannot be combined with disposition overrides. Profile
options are rejected with `--configure-only`, rather than silently ignored.
No options invoke a model, export data, or install runtime binaries.

## Identity templates

- **collaborator:** focused implementation, current requirements, explicit choices
  and validation. A general starting point.
- **reviewer:** trace changes to actual behavior; distinguish regressions, existing
  behavior, and unverified hypotheses. The role alone does not impose or waive a
  read-only task boundary.
- **maintainer:** compatibility, upgrade and recovery paths, ownership, tests, and
  maintainable documentation.
- **researcher:** competing hypotheses, discriminating experiments, reproducible
  evidence, and useful negative results.

A preset defines assigned focus, not demonstrated expertise. An optional name
makes the individual identifiable without inventing a biography. A role and focus
can be overridden. The initial self-model remains evidence-free until real
experiences support assessments.

## Disposition constructor

| Preset | Communication | Initiative | Verification | Disagreement |
|---|---|---|---|---|
| balanced | concise | bounded | focused | direct |
| deliberate | explanatory | ask-first | thorough | direct |
| exploratory | explanatory | bounded | focused | gentle |

Each value expands to a concrete sentence, visible before installation. For
example, bounded initiative means taking reasonable next steps **within** the
requested task and asking before expanding scope or taking unapproved side
effects. It is not permission to push, deploy, delete, or ignore project rules.
Gentle disagreement must still disclose material risks and contradictory evidence.

`python mettle.py presets` prints the complete catalog and wording as JSON,
without requiring a target or changing any files. Modify individual dimensions
instead of accepting every preference in a bundle. Presets are not MBTI types,
psychometric classifications, or claims about an LLM's inner experience.

Custom profiles accept UTF-8, including an optional BOM and CRLF. They must be
nonempty, at most 8000 bytes each, and contain no invalid control characters.
Generated profiles use UTF-8 without BOM and LF. Setup also checks the combined
startup context budget; a short individual file can still be too large when
combined with the existing protocol, self-model, and index.

## Managed AGENTS.md block

The operator selects prepend or append. The block is bounded by:

```markdown
<!-- agentic-mettle:begin -->
## Agentic Mettle
...
<!-- agentic-mettle:end -->
```

It tells the agent to read the fixed protocol and bootstrap location, use a
current snapshot without duplicating it, and re-establish state after context
reconstruction. It contains no learned lesson or personal profile. Existing task,
project, and component constraints remain applicable. Prepending changes position,
not instruction authority.

Installation replaces or moves only that block. It retains the original UTF-8
BOM, newline style, unrelated contents, and their order, adding minimal separating
whitespace. Repeating a placement is idempotent. Duplicate, orphaned, reversed,
or inline markers fail visibly rather than risking deletion of unrelated text.
Edited contents inside a valid managed block are replaced: put your independent
instructions outside it. `skip` means do not edit the file; it does not remove a
previously installed block. A missing file in skip mode gets a neutral heading.

This is **operator-directed installation**, not automatic lesson promotion. The
agent's reflection/reconciliation protocol still forbids modifying instruction
files. `CLAUDE.md` and component instruction files remain untouched.

## Existing installations and recovery

Omitting profile options keeps existing identity/dispositions files. Repeating
identical explicit profile choices is a no-op. A different selected profile
requires wizard approval or `--replace-profiles`; only selected profiles change.
Replacement is of the **whole selected file**, including learned dispositions it
may contain. Its exact old bytes are backed up; self-model and accepted history
remain unchanged. This is an operator action, not evidence of behavioral learning.
A preset is never seeded as an episode or supporting review.

`state/installation.json` remembers placement and adapter selections, not a second
copy of personality content. Saved adapters describe what to configure on the
next run; they are not proof of every adapter currently present. Omitting an
adapter does not uninstall it or silently delete user configuration.

The JSON plan includes paths, actions, before/after hashes, a plan fingerprint,
profile actions, warnings, and proposed text. Setup validates existing history
and startup inputs before writing, rechecks after confirmation under the store
lock, and refuses detected intervening edits. Source/config/profile changes
between preview and publication require reviewing a new plan. No unconditional
write is justified by an old preview. These checks are not a hostile-writer
security boundary; unrelated programs do not participate in the helper's lock.

Changed existing destinations get byte-for-byte adjacent backups named
`NAME.mettle-backup-SUFFIX`. This includes activation/configuration and replaced
profiles/package files. Unchanged files are not rewritten or backed up. Backups
can contain private settings: keep them out of public commits. There is no
automatic backup pruning, restore command, or uninstall in this change.

Publication is atomic **per file**, not transactional across all files. On an
I/O failure or interruption during application, some files may have changed;
inspect the JSON/error output and backups before retrying. Enabling instructions
are published after package assets; a newly created neutral marker in skip mode
is created exclusively before assets to preserve legacy safety. A failed/cancelled
preflight and a dry run create no target files, logs, or Python bytecode caches.

## Activation is observable, not assumed

After installation, inspect the block, generated handlers, selected profiles,
and `.agent-personality/LOCATION.md`. Start a new runtime session or use its
supported instruction reload, approve hooks through its normal trust interface,
and inspect actual bootstrap output. The installer does not start an agent,
answer trust prompts, change permissions, or certify loading.

Native runtime adapters retain their Windows/POSIX launch contracts. A runtime
that does not discover `AGENTS.md` needs its adapter or explicit loading. Existing
Claude instruction files and long root instructions may affect discovery; setup
warns rather than changing other instruction files or asserting success.
OpenCode's instruction-triggered bootstrap remains weaker than a verified native
lifecycle hook. JSONC is preserved, not parsed and rewritten destructively;
exclude OpenCode and use the existing adapter-fragment/manual-merge workflow.

Run `check` for local record integrity and test fresh sessions, resume, and
compaction as described in [runtime integrations](integrations.md). These checks
are separate from evaluating whether later behavior improves.
