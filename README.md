# Agentic Mettle

A repository-local protocol for persistent AI agent identity,
structured self-reflection, and experience-driven behavioral development.

Agentic Mettle separates observed experiences, tentative interpretations,
revisable lessons, and evidence from later applications. Its goal is to
help an agent develop through its history, not merely recall that history.

> Can the agent make a better-informed decision because of an earlier experience,
> recognize when its lesson does not apply, and revise it when evidence changes?

**Version 0.1.0 — experimental V1 pilot.** This repository provides an operating
protocol, a standard-library-only Python helper, runtime configuration adapters,
record validation, and offline tests. It does not establish reliable reflective
identity across hundreds of real conversations. Live runtime integration and
behavioral effectiveness must be evaluated in the target project.

## What V1 includes

- **One personality per repository:** assigned identity, dispositions, and an
  evidence-linked, revisable self-model. No per-agent-ID subdirectory.
- **Observe → Interpret → Adjust → Review:** later application supplies evidence
  about a proposed lesson; a self-critique alone does not validate it.
- **Inspectable local memory:** Markdown with JSON metadata, scoped lexical
  retrieval, aliases, immutable records, versioned lessons, and counterevidence.
- **Native loading:** local Codex and Claude Code SessionStart hooks; explicitly
  configured OpenCode protocol and root-location files.
- **Controlled reconciliation:** explicit decisions and new revisions rather
  than repeated whole-history rewrites. No automatic model calls or embeddings.

**V1 never promotes learned lessons into `AGENTS.md`, `CLAUDE.md`,
`PERSONALITY.md`, or runtime instruction configuration.** Installation leaves
existing project and component instruction files unchanged. Reconciliation
changes lesson records, not the rules that authorize the agent.

## Quick start

Requirements: Python **3.11+**, a macOS/Linux or WSL environment, and a target
project with an existing **root `AGENTS.md`**. No package installation, API key,
model service, or database is required by the helper.

```sh
git clone https://github.com/aleksandr-voitenko/agentic-mettle.git

python3 agentic-mettle/mettle.py install \
  --root /absolute/path/to/existing-project \
  --runtimes codex claude opencode

python3 /absolute/path/to/existing-project/.agent-personality/tools/mettle.py check
```

Use only the runtimes needed for the pilot. Installation merges JSON settings,
backs up changed configurations, and retains existing personality state. Review
its output and the resulting commands **before enabling/trusting hooks** in the
runtimes. Generated hook commands contain absolute machine-local paths.

Edit the initial `state/personality/identity.md` and `dispositions.md` as the
operator. The initial self-model deliberately contains no invented history.
Then verify a fresh session, resume, and compaction using the
[integration checklist](docs/integrations.md). Configuration present on disk is
not proof that a runtime executed a hook or delivered its output to the model.

OpenCode uses the loaded protocol to request a bootstrap tool call; its adapter
is **not equivalent to a verified native post-compaction hook**. When an existing
`opencode.jsonc` is detected, installation stops before changing files. Install
other runtimes separately and use `adapter --runtime opencode` to obtain a
fragment for manual JSONC integration without destroying comments.

### Installed structure

```text
existing-project/
├── AGENTS.md                              # Unchanged; designated root anchor
├── .codex/hooks.json                      # Merged, review before trust
├── .claude/settings.local.json            # Merged
├── opencode.json                          # Merged when requested
└── .agent-personality/
    ├── PERSONALITY.md                     # Fixed protocol
    ├── LOCATION.md                        # Generated root/bootstrap location
    ├── REFERENCE.md                       # Record schema and workflow
    ├── tools/mettle.py                    # Installed helper
    ├── .gitignore                         # Excludes mutable state
    └── state/
        ├── personality/
        │   ├── identity.md
        │   ├── dispositions.md
        │   └── self-model.md
        ├── memory/
        │   ├── INDEX.md
        │   ├── vocabulary.md
        │   ├── lessons/<domain>/<lesson-id>/
        │   │   ├── current.md
        │   │   └── revisions/0001.md
        │   ├── episodes/<year>/<month>/
        │   ├── reviews/<year>/<month>/
        │   └── reconciliations/<year>/<month>/
        └── sessions/
```

Subdirectories are supported, including nested lesson domains. A lesson has one
canonical location and stable ID. The installed helper derives its root from
its own location, never from the current directory or a nearer component
`AGENTS.md`. After moving a checkout, rerun installation with `--configure-only`
to update absolute hook commands and `LOCATION.md`.

There is no independent `skills/` subsystem in V1. A lesson may describe a scoped
procedure; `tools/` contains maintained implementation code, not autonomously
acquired capabilities.

## How the loop works

### 1. Retrieve for a decision

Search using the intended action, component, and likely failure mode. Repeat
when a newly discovered subtask changes what matters—not before every tool call.

```sh
python3 /path/to/project/.agent-personality/tools/mettle.py search generated bindings
python3 /path/to/project/.agent-personality/tools/mettle.py search permissions --scope authorization
python3 /path/to/project/.agent-personality/tools/mettle.py show L-example
```

Search returns candidate IDs, current revisions, status, scope, and any pending
counterexample reviews. **Read the full record before applying it.** A keyword
match is not proof of relevance, a score is not confidence, and no applicable
lesson is a valid result. Archived or superseded wording is not an active rule.

### 2. Observe and propose an adjustment

An episode records observable actions, outcomes, sources, and tentative
interpretations. A lesson turns that evidence into a conditional practice:

> When modifying generated interfaces in component X, change the source schema
> and regenerate, unless the component explicitly uses hand-maintained bindings.

Keep scope, exceptions, expected benefit, and a later review plan. Do not turn
one event into a global self-description such as “I am careless.” Successes can
also yield practices worth preserving.

### 3. Review a later application

A review names an exact lesson revision and the episodes documenting its later
application. It can support the practice, report a counterexample, record
misapplication, or leave the result uncertain. Not applying an inapplicable
lesson can be a correct decision.

### 4. Reconcile without erasing history

Use explicit ADD, REVISE, LINK_EVIDENCE, MERGE, MARK_CONTESTED, or RETIRE decisions.
Publish a new lesson revision, retaining evidence references and contradictory
cases. Old revisions remain immutable. `current.md` and indexes are generated
views; `reindex --repair` can rebuild them after an interrupted publication.

There is **no background LLM worker**. The participating agent follows the
protocol, prepares drafts, and invokes the helper. Human operators can use the
same commands. The validator checks structure and provenance links, not whether
a reflection is psychologically or causally true.

## Record commands

Records use JSON metadata between `---` delimiters followed by Markdown. The
helper intentionally does not require a YAML library or accept arbitrary YAML.

```sh
# Generate a draft, replace all placeholders, then publish it.
python3 /path/to/project/.agent-personality/tools/mettle.py template episode > /tmp/episode.md
python3 /path/to/project/.agent-personality/tools/mettle.py publish /tmp/episode.md

# New lessons require the expected prior revision, zero for a new ID.
python3 /path/to/project/.agent-personality/tools/mettle.py template lesson > /tmp/lesson.md
python3 /path/to/project/.agent-personality/tools/mettle.py publish /tmp/lesson.md --expected-revision 0

# After publishing a review and reconciliation, publish a revised lesson.
python3 /path/to/project/.agent-personality/tools/mettle.py publish /tmp/lesson-v2.md --expected-revision 1

python3 /path/to/project/.agent-personality/tools/mettle.py check
```

See [the record specification](docs/records.md) for required fields, the full
publication sequence, recovery, and semantic checks. Run the isolated,
**synthetic** worked example with:

```sh
python3 examples/walkthrough.py
```

The example uses a temporary project and is never seeded into a real agent's
memory. Example success is a storage/protocol demonstration, not a learning
experiment.

## Boundaries and known limitations

Memory is evidence, not authority. It cannot grant permissions, override project
requirements, or authorize self-modification. Native hooks may inject text at a
high instruction priority; mutable profile data is explicitly labelled, but that
label is **not** a prompt-injection security boundary.

Use one authoritative writer. The helper serializes its own operations with a
filesystem lock, but cannot prevent direct file edits or resolve two independent
concurrent personalities sharing this store. Bootstrap logs record emission and
hashes, not delivery or obedience. A hook that never runs cannot report its own
absence.

State stays local but is sent to the configured model provider when an agent
reads it. Do not store secrets or unnecessary personal information. `.gitignore`
is not encryption, access control, synchronization, or backup. Review generated
absolute-path configurations and backups before committing. See
[security and privacy](SECURITY.md).

Lexical retrieval can miss paraphrases. Retrieval validates the local record
graph and is linear in the memory archive; it does not scan the source tree.
There is no measured large-memory performance guarantee. Startup context has an
explicit character budget and fails visibly rather than silently truncating a
personality. Character counts are not token or billing measurements.

This is not a claim of consciousness, an MBTI personality implementation, or a
proven remedy for model drift. Different models can use the same state
differently; record model/runtime provenance and evaluate changes.

## Evaluation and development

```sh
python3 -m unittest discover -s tests -v
python3 examples/walkthrough.py
python3 -m py_compile mettle.py examples/walkthrough.py
```

The offline suite checks installation safety, nested-root resolution, native
hook payloads, immutable records, references, revision conflicts, counterevidence,
recovery, and fresh-process persistence. Synthetic archives are not hundreds of
real conversations. Live Codex/Claude/OpenCode execution has not been certified.

[The evaluation plan](docs/evaluation.md) separates storage, loading, retrieval,
application, and correctability. It includes negative transfer, task-order
sensitivity, unseen applications, model changes, and **total** token/latency
cost including reflection and maintenance—not just fewer action steps.

## Related projects and research

This map records the work discussed while designing Agentic Mettle. Links point
to papers, official projects, or runtime documentation. Inclusion is not an
endorsement, a dependency, or a claim that results transfer to this protocol.
No benchmark results from these systems are presented as Agentic Mettle results.
Research and runtime documentation were reviewed on **2026-09-30**; preprints and
software interfaces can change.

### Experience-to-strategy learning and reconciliation

| Work | Relevant contribution | Boundary for this project |
|---|---|---|
| [ReasoningBank](https://arxiv.org/abs/2509.25140) · [code](https://github.com/google-research/reasoning-bank) | Distills strategies from successful and failed attempts and retrieves them for subsequent tasks. | Task-performance evidence, not persistent identity. Its released memory loop is not our full revision/counterevidence model. |
| [Reflexion](https://arxiv.org/abs/2303.11366) | Stores feedback-derived verbal reflections to improve later attempts without weight updates. | Repeated-attempt learning does not establish development across hundreds of independent conversations. |
| [ExpeL](https://arxiv.org/abs/2308.10144) · [code](https://github.com/LeapLabTHU/ExpeL) | Extracts and revises insights through explicit agreement, addition, editing, and removal operations. | Inspires explicit reconciliation; Mettle retires or supersedes evidence-backed records rather than silently erasing them. |
| [Agent Workflow Memory](https://arxiv.org/abs/2409.07429) · [code](https://github.com/zorazrw/agent-workflow-memory) | Abstracts reusable workflows from experience, including recurring subtasks. | Inspires action-level retrieval; a workflow engine is outside V1. |
| [Dynamic Cheatsheet](https://aclanthology.org/2026.eacl-long.333/) · [code](https://github.com/suzgunmirac/dynamic-cheatsheet) | Maintains evolving strategies and reusable methods across sequential problems. | Recurring benchmark families and model-dependent effects are not general lifetime validation. |
| [Agentic Context Engineering — ACE](https://arxiv.org/abs/2510.04618) | Separates generation, reflection, and curation; uses localized playbook updates. | Inspires stable records and incremental changes, not automatic rewriting of project instructions. |
| [MemRL](https://arxiv.org/abs/2601.03192) | Combines semantic relevance with feedback-derived utility for memory retrieval. | Relevance and usefulness differ. V1 records applications but does not implement reinforcement learning or utility optimization. |
| [Evo-Memory / ReMem](https://arxiv.org/abs/2511.20857) | Studies sequential experience reuse and active refinement of an evolving memory. | Informs ordering, failure-contamination, and distribution-shift tests. |

### Persistent agents, self-models, and memory architectures

| Work | Why it is relevant | Important distinction |
|---|---|---|
| [Generative Agents](https://arxiv.org/abs/2304.03442) | Experience streams, reflection, planning, and ongoing social behavior. | Short simulated social behavior is not indefinite autobiographical stability. |
| [MemGPT](https://arxiv.org/abs/2310.08560) / [Letta](https://docs.letta.com/concepts/stateful-agents) | Explicit state and memory management beyond a single context window. | Persistence infrastructure does not itself validate a coherent self-model. |
| [MemoryBank](https://arxiv.org/abs/2305.10250) | Long-term conversational memory and adaptation to users. | Learning about a user's preferences is different from developing the agent's own identity. |
| [Voyager](https://voyager.minedojo.org/) | Acquires and reuses executable skills through interaction and feedback. | Demonstrates procedural accumulation in Minecraft, not a runtime-neutral personality protocol. |
| [Hindsight](https://arxiv.org/abs/2512.12818) | Retain, recall, and reflect mechanisms with distinctions between facts and opinions. | Memory QA and opinion machinery are not longitudinal behavioral validation. |
| [Sophia](https://arxiv.org/abs/2512.18202) | Explicit self-model, narrative memory, reflection, and goal generation. | A close architectural comparison with exploratory pilot evidence. |
| [MIRROR](https://arxiv.org/abs/2506.00430) | Reflective context and continuing internal narrative for reasoning/constraint maintenance. | Its narrow evaluation should not be mistaken for hundreds of continuing conversations. Mettle records observable evidence, not hidden reasoning. |
| [PEPA](https://arxiv.org/abs/2603.00117) | Episodic experience and reflection can change embodied-agent goals and priorities. | Short embodied experiments are not a general conversational identity benchmark. |
| [Vigil](https://arxiv.org/abs/2604.09579) | Deployed on-call support with review-driven knowledge maintenance. | Shared support knowledge at deployment scale differs from one individual's autobiographical development. |

### Evaluation, self-correction, and persona persistence

| Work | Relevance |
|---|---|
| [LongMemEval](https://arxiv.org/abs/2410.10813) | Tests long-history extraction, updates, temporal reasoning, and abstention. Useful for memory, but history-question answering is not behavior developing through that history. |
| [Persistent Personas?](https://aclanthology.org/2026.eacl-long.246/) | Examines persona fidelity during extended task-oriented interaction; motivates testing more than initial personality prompting. |
| [InCharacter](https://aclanthology.org/2024.acl-long.102/) | Personality-fidelity assessment through psychological interviews; supplementary rather than sufficient behavioral evaluation. |
| [PersonaGym](https://personagym.com/) | Evaluates persona agents in relevant situations, including actions and consistency. |
| [Prompting Against Persona Drift](https://arxiv.org/abs/2609.24532) | Studies reminder and corrective interventions in a narrow simulation; preliminary, not lifetime reliability evidence. |
| [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798) | Warns against equating unsupported self-critique with reliable correction in the studied settings. |
| [ProCo: Key Condition Verification](https://arxiv.org/abs/2405.14092) | Examines an explicit verification method; distinguishes targeted checks from an unrestricted request to reflect more. |
| [A psychometric framework for evaluating and shaping personality traits in LLMs](https://www.nature.com/articles/s42256-025-01115-6) | Supports investigating measurable behavioral tendencies without assuming human psychological mechanisms or indefinite stability. |
| [LLM Agents Grounded in Self-Reports](https://arxiv.org/abs/2411.10109) | Models individuals from detailed evidence; representing an existing person differs from an agent developing through its own experience. |
| [Persona Vectors](https://arxiv.org/abs/2507.21509) / [The Assistant Axis](https://arxiv.org/abs/2601.10387) | Internal-activation approaches to monitoring or steering behavior. Architecturally different from a portable external state protocol. |

### MBTI work considered, not adopted

MBTI is not part of V1. The earlier discussion included
[Do LLMs Possess a Personality?](https://arxiv.org/abs/2307.16180),
[Machine Mindset](https://arxiv.org/abs/2312.12999),
[Open Models, Closed Minds?](https://arxiv.org/abs/2401.07115),
[Psychologically Enhanced AI Agents / MBTI-in-Thoughts](https://arxiv.org/abs/2509.04343),
and [Do Personality-Tuned LLMs Make Better Social Agents?](https://arxiv.org/abs/2609.21857).
These concern measuring or inducing personality-labelled behavior. Questionnaire
alignment, useful operational behavior, and long-term continuity remain distinct
claims; Mettle uses explicit, revisable dispositions rather than four-letter types.

### Context management and runtime foundations

[Codex's agent loop](https://openai.com/index/unrolling-the-codex-agent-loop/),
[Responses API compaction](https://developers.openai.com/api/docs/guides/compaction),
and [Anthropic's context engineering discussion](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
inform the distinction between a replaceable working context and durable evidence.
Compaction is not, by itself, reflective learning.

The adapters follow [Codex hooks](https://learn.chatgpt.com/docs/hooks),
[Claude Code hooks](https://code.claude.com/docs/en/hooks),
[Claude instruction discovery](https://code.claude.com/docs/en/memory),
[OpenCode rules](https://opencode.ai/docs/rules), and
[OpenCode plugins](https://opencode.ai/docs/plugins/).
See [integration details](docs/integrations.md) for differences and limitations.

## License

[MIT](LICENSE). Research references retain their authors' rights and licenses.
This initial implementation is original code inspired by published ideas; it
contains no vendored research implementation and has no affiliation with the
referenced projects.
