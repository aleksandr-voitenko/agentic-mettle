# Runtime integrations

Documentation checked: **2026-09-30**. Generated configurations are checked with
offline contract tests. This repository does **not** claim that a live Codex,
Claude Code, or OpenCode agent has passed the pilot. Record actual runtime
versions and hook traces before declaring a deployment verified.

## Installation and root anchoring

The target must already contain its designated root `AGENTS.md`. Pass that
directory explicitly to `install`. The installer never creates or edits
`AGENTS.md`, `CLAUDE.md`, or component instruction files. It deploys the shared
protocol and helper into `.agent-personality/`, creates one fresh local state,
and merges only the requested runtime configuration. Existing state is retained.

Hook commands use a shell-quoted **absolute installed helper path**. The helper
derives its root from that fixed location, not from cwd or the nearest
`AGENTS.md`. This works from nested component directories. It deliberately
rejects missing root markers and symlinked state paths. After moving a checkout,
rerun `install --configure-only` with its new root to refresh hook commands and
the generated LOCATION.md. Local generated hook configurations contain machine
paths: review them before committing or sharing. Support targets macOS/Linux
and WSL with `python3` 3.11+; native Windows shell integration is not provided.

The installer preflights JSON and keeps backups of changed config files. Repeated
installation replaces only Mettle's own hook entry and preserves unrelated
handlers/settings. Filesystem writes are atomic per file, not an all-or-nothing
transaction across all configuration files. An interrupted installation can be
rerun. Operator edits to the installed fixed protocol/tools are replaced by a
source update; keep intentional protocol changes in the source package.

## Codex

The generated `.codex/hooks.json` registers `SessionStart` for startup, resume,
clear, and compact. The hook reads lifecycle JSON from stdin and emits
`hookSpecificOutput` with `hookEventName: SessionStart` and `additionalContext`.
The current Codex documentation supports project-local hooks and post-compaction
SessionStart context. Project trust and review of the exact hook definition are
required; inspect `/hooks`. Do not bypass trust merely to make a test pass.

Source: [Codex hooks](https://learn.chatgpt.com/docs/hooks).

Existing `.codex/config.toml` is not rewritten. If it already defines hooks,
inspect both sources for duplication. An older CLI, disabled hooks, managed
policy, or a cloud orchestration environment may not support this local path.
Do not treat a generated config file as proof that a hook executed.

## Claude Code

The generated `.claude/settings.local.json` uses `SessionStart` for startup,
resume, clear, compact, and fork. It runs the same helper with the Claude adapter.
No `CLAUDE.md` import file is created: adding such a file can change default
`AGENTS.md` discovery, especially in a large repository with scoped instructions.
Review the command in Claude's hook/settings UI and verify it actually executes.

Sources: [Claude hooks](https://code.claude.com/docs/en/hooks),
[Claude instruction discovery](https://code.claude.com/docs/en/memory).

The stdout contract is exercised locally with synthetic event payloads. A fork
shares the one personality; V1 still requires a single authoritative writer.
Do not use forks as simultaneous independent personalities.

## OpenCode

The installer adds these explicit entries to the `instructions` array:

```json
{
  "instructions": [
    ".agent-personality/PERSONALITY.md",
    ".agent-personality/LOCATION.md"
  ]
}
```

PERSONALITY.md is the fixed protocol; LOCATION.md is operator-generated runtime
location information containing the absolute bootstrap command. Neither is a
learned lesson or memory archive. Existing entries are preserved. Do not replace
these paths with a recursive Markdown glob.

This integration loads instructions, **not the mutable state by itself**. The
agent must run the supplied bootstrap command and consume its tool result.
Reinitialization after compaction is a protocol obligation in V1, not a claimed
native post-compaction guarantee. This is a deliberately weaker integration than
a verified SessionStart hook. Test it explicitly. No experimental OpenCode plugin
is installed. Its documented experimental compaction hook changes summarizer
input, which is not equivalent to post-compaction state reinjection.

Sources: [OpenCode rules](https://opencode.ai/docs/rules),
[OpenCode plugins](https://opencode.ai/docs/plugins/).

If `opencode.jsonc` exists, the installer refuses to rewrite it or discard
comments. Install the other runtimes, print the OpenCode fragment, and merge it
into the existing JSONC file yourself:

```sh
python3 mettle.py install --root /path/to/project --runtimes codex claude
python3 mettle.py adapter --root /path/to/project --runtime opencode
```

No automatic external-directory or broad tool permission is granted.

## Snapshot and failure semantics

Only the fixed protocol, compact personality files, directory map, resolved root,
and available runtime/model metadata enter a startup snapshot. Detailed lessons
are retrieved on demand. Mutable text is clearly labelled as data; this labelling
is not a prompt-injection security guarantee. Existing repository and higher
priority instructions remain authoritative.

A bootstrap log records hashes and `snapshot_emitted`, not "the model obeyed".
Character counts are not token measurements. Oversized snapshots fail visibly
rather than silently trimming a personality. Errors emit structured warnings and
`continue: false` for native hooks; exact stop/UI behavior is runtime-controlled.
If the hook never executes, it cannot report its own absence: inspect the runtime
trace and the recent bootstrap logs.

## Manual smoke test

In a target project, from a nested component, run the installed absolute helper:

```sh
printf '%s' '{"hook_event_name":"SessionStart","source":"compact","session_id":"manual-contract-test"}' \
  | python3 /path/to/project/.agent-personality/tools/mettle.py bootstrap --runtime codex --hook
```

Check that JSON parses, the root is the designated root, and hashes correspond
to its actual profile files. Repeat in the live runtime on fresh start, resume,
and compaction. Then test whether a later task applies the relevant lesson
without an explicit reminder; see [the evaluation plan](evaluation.md).
