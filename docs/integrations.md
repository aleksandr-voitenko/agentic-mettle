# Runtime integrations

Documentation and public source checked: **2026-10-01**. Generated launches are
executed in offline process tests, including native Windows shells. This does
**not** establish that a live agent loaded the context or followed the protocol.
Record runtime versions and lifecycle traces before declaring a deployment
verified. The helper remains Python 3.11+, standard library only.

| Runtime | Configuration baseline | Launch form |
|---|---|---|
| Codex | 0.153.0 or newer with the documented hooks interface; older versions not qualified | POSIX `command`; native Windows `commandWindows` for `cmd.exe /C` |
| Claude Code | 2.1.139+ (introduced hook `args`) | Absolute Python executable in `command`, argument array in `args`, no shell |
| OpenCode | 1.18.34 source and current `instructions`/`shell` documentation | Explicit instruction loading, then a tool command for the configured shell |

Later runtime releases can change behavior. The installer does not query runtime
versions or silently enable disabled hooks, change trust, or grant permissions.

## Installation and root anchoring

Pass the existing target project directory explicitly to `install --root`.
If its root `AGENTS.md` is missing, installation creates a UTF-8/LF file containing
only `# Project instructions`, after configuration and history validation. The
installer reports `agents_created` in its JSON result. Creation is exclusive: it
cannot overwrite a file created by an operator during installation. Existing
`AGENTS.md`, `CLAUDE.md`, and component instruction files are preserved byte for
byte; no learned lessons or runtime imports are added to them. The installer
deploys the shared protocol and helper into `.agent-personality/`, creates one
fresh local state, and merges only the requested runtime configuration. Existing
state is retained. It never chooses the root from cwd or component instructions.

Hook launches use a validated **absolute Python executable and installed helper
path**, with `-X utf8`. The helper
derives its root from that fixed location, not from cwd or the nearest
`AGENTS.md`. This works from nested component directories. Read/bootstrap commands
still reject missing root markers; rerun installation to recreate a missing
scaffold (this cannot recover deleted project instructions). Installation and
reads reject redirected state paths, including Windows junctions and reparse
points. After moving an installed target or its interpreter,
rerun `install --configure-only` with its new root to refresh hook commands and
the generated LOCATION.md. Local generated hook configurations contain machine
paths: review them before committing or sharing. Native Windows initially
targets local NTFS, with PowerShell 5.1 or 7 for operator commands. WSL is not
required. macOS/Linux retain POSIX command generation.

The running interpreter is the default. Supply `--python-executable` to choose
another stable console Python 3.11+ executable; the installer probes it directly
with isolated UTF-8 Python and records its concrete path. A later runtime's PATH
is irrelevant. Windows `.cmd`/`.bat` shims and `pythonw.exe` are refused. Virtual
environments work while present, but uninstalling/moving one requires reconfiguration.

From this source checkout in PowerShell, selecting an existing target directory:

```powershell
$Python = 'C:\Path\To\Python311\python.exe'
$Project = 'D:\path\to\existing-project'
& $Python -X utf8 .\mettle.py install --root $Project --python-executable $Python --runtimes codex claude opencode
$Mettle = Join-Path $Project '.agent-personality\tools\mettle.py'
& $Python -X utf8 $Mettle check
```

After moving the target, update `$Project` and `$Mettle`, then run:

```powershell
& $Python -X utf8 $Mettle install --root $Project --configure-only --python-executable $Python --runtimes codex claude opencode
```

`--configure-only` does not upgrade an old installed helper. Run a normal
installation from the updated source first when upgrading the helper itself.
Moving the source checkout alone does not affect already deployed helpers.

The installer preflights JSON and keeps backups of changed config files. Repeated
installation matches complete Mettle argument vectors, upgrades the earlier
`python3`/POSIX-quoted format (including its Windows paths), and replaces the
owned handler without accumulating duplicates. It recognizes `commandWindows`
and Claude's `args`. Unrelated handlers, matcher groups, settings, and instruction
entries are retained. A handler mixing a Mettle platform command with an unrelated
platform override is ambiguous and requires an operator to split it first.
No ownership metadata is inserted into runtime configuration. Changed configs
have byte-for-byte backups, including an original BOM or CRLF. New text is UTF-8
without a BOM and uses LF. JSONC is never destructively rewritten.
Filesystem writes are atomic per file, not an all-or-nothing
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

On Windows, `commandWindows` contains a CMD-quoted command. Codex 0.153.0 uses
`COMSPEC` (falling back to `cmd.exe`) with `/C` and outer command quotes; it does
not choose PowerShell just because the operator launched Codex there. Keep
`COMSPEC` pointed at `cmd.exe`. Every argument is individually quoted. Mettle
rejects paths containing `%` or `!` because CMD expansion can change them even
inside quotes, as well as embedded double quotes/control newlines. Choose a
different path or exclude the CMD-based runtime. Spaces, Unicode, `&`, parentheses,
carets, dollar signs, apostrophes, backticks, brackets, and semicolons are tested.
Stdin/stdout/stderr and the Python exit code flow through CMD without a wrapper.

Sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[0.153.0 command runner](https://github.com/openai/codex/blob/rust-v0.153.0/codex-rs/hooks/src/engine/command_runner.rs),
[Windows override selection](https://github.com/openai/codex/blob/rust-v0.153.0/codex-rs/hooks/src/engine/discovery.rs).

Existing `.codex/config.toml` is not rewritten. If it already defines hooks,
inspect both sources for duplication. An older CLI, disabled hooks, managed
policy, or a cloud orchestration environment may not support this local path.
Do not treat a generated config file as proof that a hook executed.

## Claude Code

The generated `.claude/settings.local.json` uses `SessionStart` for startup,
resume, clear, compact, and fork. It runs the same helper with the Claude adapter.
The documented executable-plus-args form invokes Python directly on Windows,
macOS, and Linux. There is no Bash/PowerShell wrapper and no quoting inside argv.
Paths with `${...}` are rejected: Claude performs placeholder substitution even
in exec form. No `CLAUDE.md` import file is created: adding such a file can change default
`AGENTS.md` discovery, especially in a large repository with scoped instructions.
Review the command in Claude's hook/settings UI and verify it actually executes.

Sources: [Claude hooks](https://code.claude.com/docs/en/hooks),
[2.1.139 changelog introducing exec-form hooks](https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#21139),
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

On native Windows, if `opencode.json` has no `shell`, the installer adds the
documented `shell` field with the absolute Windows PowerShell executable. This
pins the command language instead of depending on future shell discovery. An
existing `pwsh`, `powershell`, or `cmd` setting is preserved and LOCATION.md uses
that syntax. Other Windows shell choices fail preflight without modifying them;
select a supported shell yourself or configure that integration manually. The
PowerShell form configures UTF-8 pipe encoding and propagates `$LASTEXITCODE` in
the tool's child shell, without changing execution policy. CMD uses the same
path restrictions as Codex. Rerun configuration when changing the shell.

LOCATION.md also records an executable/argument vector for tools that support
direct invocation. This operator-generated information is separate from learned
records and does not change the shared reflection protocol.

This integration loads instructions, **not the mutable state by itself**. The
agent must run the supplied bootstrap command and consume its tool result.
Reinitialization after compaction is a protocol obligation in V1, not a claimed
native post-compaction guarantee. This is a deliberately weaker integration than
a verified SessionStart hook. Test it explicitly. No experimental OpenCode plugin
is installed. Its documented experimental compaction hook changes summarizer
input, which is not equivalent to post-compaction state reinjection.

Sources: [OpenCode rules](https://opencode.ai/docs/rules),
[OpenCode shell configuration](https://opencode.ai/docs/config/#shell),
[1.18.34 shell selection and invocation](https://github.com/anomalyco/opencode/blob/v1.18.34/packages/core/src/shell.ts),
[OpenCode plugins](https://opencode.ai/docs/plugins/).

If `opencode.jsonc` exists, the installer refuses to rewrite it or discard
comments. Install the other runtimes, print the OpenCode fragment, and merge it
into the existing JSONC file yourself:

PowerShell (the printed fragment also proposes a documented Windows `shell`;
retain your existing supported choice and match LOCATION.md to it):

```powershell
& $Python -X utf8 .\mettle.py install --root $Project --runtimes codex claude
& $Python -X utf8 .\mettle.py adapter --root $Project --runtime opencode --python-executable $Python
```

macOS/Linux:

```sh
python3 -X utf8 mettle.py install --root /path/to/project --runtimes codex claude
python3 -X utf8 mettle.py adapter --root /path/to/project --runtime opencode
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

In PowerShell 5.1 or 7, set `$Python`, `$Project`, and `$Mettle` as above. From a
nested component containing its own AGENTS.md, run the absolute installed helper:

```powershell
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$Event = '{"hook_event_name":"SessionStart","source":"compact","session_id":"manual-contract-test"}'
$Reply = $Event | & $Python -X utf8 $Mettle bootstrap --runtime codex --hook
$Reply | ConvertFrom-Json | Select-Object -ExpandProperty hookSpecificOutput
& $Python -X utf8 $Mettle check
```

This tests the helper's JSON contract. To test the **generated Codex command**
through its actual Windows shell without another layer of shell quoting:

```powershell
$Smoke = @'
import json, os, pathlib, runpy, subprocess, sys
root = pathlib.Path(sys.argv[1])
helper = runpy.run_path(str(root / ".agent-personality/tools/mettle.py"))
config = json.loads((root / ".codex/hooks.json").read_text(encoding="utf-8-sig"))
handlers = [h for g in config["hooks"]["SessionStart"] for h in g["hooks"]
            if helper["owned_handler"](h, "codex")]
assert len(handlers) == 1, "Review the hook configuration first"
shell = os.environ["COMSPEC"]
command = handlers[0]["commandWindows"]
result = subprocess.run('"' + shell + '" /C "' + command + '"', executable=shell,
                        input=b'{"source":"startup"}', capture_output=True)
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
'@
$Smoke | & $Python -X utf8 - $Project
```

Review the handler before executing it. For a manual bootstrap, LOCATION.md also
supplies a shell-labelled command. The automated suite executes all generated
handler forms in disposable targets. None of these is a live lifecycle test.

macOS/Linux helper contract check:

```sh
printf '%s' '{"hook_event_name":"SessionStart","source":"compact","session_id":"manual-contract-test"}' \
  | python3 -X utf8 /path/to/project/.agent-personality/tools/mettle.py bootstrap --runtime codex --hook
```

Check that JSON parses, the root is the designated root, and hashes correspond
to its actual profile files. Repeat in the live runtime on fresh start, resume,
and compaction. Then test whether a later task applies the relevant lesson
without an explicit reminder; see [the evaluation plan](evaluation.md).

Never bypass project trust, hook review, execution policy, or managed settings
to complete a smoke test. A denied/unapproved hook is not a verified lifecycle
integration. OpenCode's instruction-triggered bootstrap remains weaker than a
verified native lifecycle hook even when its shell command works.

## Windows validation record (2026-10-01)

The portability change was tested on native Windows 10 build 19045, with local
NTFS targets. Each interpreter ran the same commands from the source checkout:

```powershell
& $Python -X utf8 -m unittest discover -s tests -v
& $Python -X utf8 examples/walkthrough.py
& $Python -X utf8 -m py_compile mettle.py examples/walkthrough.py tests/test_mettle.py tests/test_portability.py tests/test_behavioral_review.py
```

| Python | Unit tests | Synthetic walkthrough | Compilation |
|---|---|---|---|
| 3.11.15 | 68 run, 64 passed, 4 skipped | Passed | Passed |
| 3.12.14 | 68 run, 64 passed, 4 skipped | Passed | Passed |
| 3.13.13 | 68 run, 64 passed, 4 skipped | Passed | Passed |
| 3.13.15 (machine-wide installation) | 68 run, 64 passed, 4 skipped | Passed | Passed |

Installation coverage includes projects without a root AGENTS.md, preserving
existing/scoped instructions, failed preflight without creating a marker,
exclusive creation when an operator writes the file concurrently, and
reconfiguration from a nested component after the root marker is removed.

The four skips were three POSIX-only checks and Windows symlink creation denied
with WinError 1314. Junction creation and rejection were exercised. The original
37-test suite initially had two failures and one error on native Windows:
duplicate hooks, a serialized-JSON path assertion, and the symlink privilege
assumption. The test host's sandbox also produced temporary-directory ACL
errors; the reported runs used approved execution outside that sandbox, without
changing Windows symlink privileges or runtime trust.

Generated launches ran through CMD, Windows PowerShell 5.1.19041.6456,
PowerShell 7.6.5, and direct executable/argument invocation (also via Node
20.19.6). Tests used disposable roots and a selected interpreter outside PATH,
including spaces, Unicode, and shell metacharacters. They exercised synthetic
startup/resume/compact payloads, output parsing, and exit-status propagation.
The walkthrough retained four evidence records and two revisions of one lesson;
it did not call a model or measure behavioral learning.

Codex CLI 0.153.0 was installed. Its live startup attempt reached the normal
project-trust prompt; the attempt was declined and produced no bootstrap audit
record. Startup, resume, and compaction therefore remain **not live-verified**.
Claude Code and OpenCode were not available on PATH, so neither integration was
live-verified. Their version baselines above describe documentation/source
inspection, not installed runtime tests. No trust, hook approval, or execution
policy was bypassed.

The Linux/Windows GitHub Actions matrix was updated but its jobs were not run as
part of this local validation. macOS/Linux process behavior, non-NTFS Windows
storage, network shares, and synchronized directories were not exercised here.
