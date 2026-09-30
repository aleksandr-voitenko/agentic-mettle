# Pilot evaluation: behavior, not autobiography

The primary criterion is a later appropriate decision caused or informed by an
applicable prior experience, not the ability to answer a question about history.
No longitudinal LLM result is claimed by this initial implementation.

## Separate the layers

| Layer | Evidence to collect |
|---|---|
| Persistence | Accepted record/revision survives a process restart unchanged. |
| Availability | The runtime actually supplies the correct protocol and current personality snapshot. |
| Retrieval | Relevant current lessons are found; irrelevant, stale, or superseded ones are rejected. |
| Application | The agent changes an observable action where the lesson applies. |
| Correctability | Counterexamples narrow, contest, or retire a lesson without erasing history. |
| Identity continuity | The self-model describes evidenced patterns with scope, not fabricated traits. |

The automated tests cover the filesystem/helper contracts. Synthetic episodes
are not real conversations and are not evidence of personality persistence.

## A first behavioral trial

Choose a real, verifiable issue in an existing component. Record an actual
mistake or meaningful success, formulate one proposed lesson, and provide a
later independent opportunity in different wording. Do not tell the agent which
lesson to use. Inspect its retrieved IDs, decision, diff, test result, and review.

Include an unrelated task, a superficially similar case where the lesson must
not apply, changed requirements that invalidate its premise, a contradictory
observation, a fresh session, and a compaction boundary. For each runtime record
the exact version, model, permissions, loaded instructions, and available tools.
A different model may express the same stored personality differently.

A no-match cold start is not a retrieval error. Failure to find an existing
applicable lesson is a retrieval error. Applying an unsuitable lesson is negative
transfer. Successful recall with unchanged behavior is not behavioral learning.

## Comparison and ordering

Compare the same task snapshots with no Mettle, raw experiences only, and the
structured protocol where feasible. Keep tools, model versions, and budgets
comparable. Separate initialization overhead from useful work. Score outcomes
using tests and reviewable artifacts, not merely an LLM personality questionnaire.

For independent benchmark tasks, use multiple recorded random orders, clustered
orders, and distribution-shift sequences. Reset the memory bank between runs.
Do not randomly reorder dependency-bound repository tasks: preserve their valid
chronology or use isolated snapshots. Do not count repeated attempts or relabelled
summaries of one incident as independent supporting evidence.

ReasoningBank's reported improvements do not establish order-independent gains.
Evo-Memory explicitly examines easy-to-hard versus hard-to-easy streams. These
motivate this plan, not a claim that our implementation reproduces their results.
Sources: [ReasoningBank](https://arxiv.org/abs/2509.25140),
[Evo-Memory](https://arxiv.org/abs/2511.20857).

## Cost and reporting

Record actual input, output, and cached token counts when the provider exposes
them; otherwise record `unknown`. Keep separate totals for task execution,
retrieved memory, reflection, and reconciliation. Include tool calls, latency,
and human corrections. Fewer tool steps do not establish lower total cost.
Bootstrap emits hashes and character counts only.

Track record growth, redundant lessons, pending counterexamples, useful
applications, harmful applications, and revisions. Publish failures as well as
successes. Hundreds of archived records, hundreds of turns, and hundreds of
independent conversations are distinct denominators and must be labelled.
