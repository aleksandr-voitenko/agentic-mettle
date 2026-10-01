# Pilot evaluation: behavior, not autobiography

The primary criterion is a later appropriate decision informed by an applicable
prior experience, not the ability to answer a question about history. Establishing
that a lesson caused improvement requires a suitable comparison, not just a
successful result. No longitudinal LLM result is claimed by this implementation.

## Separate the layers

| Layer | Evidence to collect |
|---|---|
| Persistence | Accepted record/revision survives a process restart unchanged. |
| Availability | The runtime actually supplies the correct protocol and current personality snapshot. |
| Retrieval | Relevant current lessons are found; irrelevant, stale, or superseded ones are rejected. |
| Applicability and authority | The candidate fits the current task and authorized actions; a remembered workflow does not expand permission. |
| Application | The agent changes an observable action where the lesson applies, or correctly declines an inapplicable practice. |
| Correctability | Counterexamples narrow, contest, or retire a lesson without erasing history. |
| Reflective self-model | An assessment of the agent's own behavior changes for traceable reasons, separately from user preferences or acquired procedures. |

The automated tests cover the filesystem/helper contracts. The synthetic
behavioral-review fixture tests record handling for rejection, support, and a
counterexample, not whether a model made those decisions. Synthetic episodes
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

In particular, include a read-only task that can retrieve a familiar procedure
with write or publish steps. Finding the procedure is not a failure; performing
unauthorized steps is. Record why the candidate was rejected rather than count
every retrieval as an application or every non-application as a failure.

A no-match cold start is not a retrieval error. Failure to find an existing
applicable lesson is a retrieval error. Applying an unsuitable lesson is negative
transfer. Successful recall without an appropriate behavioral consequence is not
by itself evidence of behavioral learning. Correct behavior that was already
present should not be reported as a newly learned improvement.

## Control other memory sources

A participating runtime may supply its own memories, user profiles, imported
skills, summaries, or earlier conversation context. These are possible alternative
sources of a decision, not evidence attributable to Mettle merely because Mettle
was enabled in the same run.

Record each source's read/use and write/generation state separately where known.
Generation disabled does not imply old memories were unavailable. Capture the
relevant versions or hashes and the files actually read when observable. Use
`unknown` when configuration, hidden context, or usage cannot be established;
absence of a visible read is not proof that a source was unavailable.

For an isolated comparison, disable or hold other memory sources constant using
supported controls and preserve their initial snapshots between conditions.
Do not erase a real user's memories or bypass permissions for an experiment.
A runtime-native-memory-only condition can be useful alongside no-memory,
raw-experience-only, and Mettle conditions. A combined deployment is also valid,
but report its outcome as combined-system behavior unless an ablation supports
attribution. Reset learned state between independent evaluation runs so previous
conditions do not contaminate later ones.

### Minimal run manifest

Keep a local manifest with the evaluation artifacts, not in startup context or
as new personal experience. This is a suggested report format, not a new accepted
record kind or CLI command:

```text
Run/task ID and repository snapshot:
Runtime/version and model:
Mettle protocol version/hash and initial state snapshot:
Other memory sources: source, read/use state, write/generation state,
                      initial snapshot/version, observed use, unknowns
Current request and authorized actions:
Candidate lesson IDs/revisions and search-term provenance:
Applicability decision and reason:
Observed action, artifact/test evidence, outcome and limitations:
Resulting review/reconciliation IDs and final state snapshot:
Actual token/latency measurements, or unknown:
```

Do not record secrets, unnecessary personal data, or hidden reasoning. Preserve
only the minimum evidence necessary to inspect the decision and its attribution.

## Comparison and ordering

Compare the same task snapshots with no Mettle, raw experiences only, and the
structured protocol where feasible, controlling the other sources above. Keep
tools, model versions, and budgets comparable. Separate initialization overhead
from useful work. Score outcomes using tests and reviewable artifacts, not merely
an LLM personality questionnaire.

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

## Evaluate development of the self-model separately

A better workflow result does not by itself show that an assessment about the
agent became more accurate. Inspect whether a self-model statement refers to
actual repeated behavior, keeps component/model boundaries, acknowledges
counterevidence, and changes after later evidence. Distinguish an assigned trait,
a tentative interpretation, and an evidence-supported pattern.

Include a case where a compensating practice works repeatedly: the current
assessment should be able to acknowledge improvement rather than repeat an
obsolete weakness forever. Preserve the previous assessment and its evidence
so that revision is inspectable. More confident wording, additional personality
labels, or a longer autobiography are not success metrics.

## Cost and reporting

Record actual input, output, and cached token counts when the provider exposes
them; otherwise record `unknown`. Keep separate totals for task execution,
retrieved memory, reflection, and reconciliation. Include tool calls, latency,
and human corrections. Fewer tool steps do not establish lower total cost.
Bootstrap emits hashes and character counts only.

Track record growth, redundant lessons, pending counterexamples, useful
applications, justified non-applications, harmful applications, and revisions.
Retrieval count is not usefulness, and neither is causal improvement. Publish
failures as well as successes. Hundreds of archived records, hundreds of turns,
and hundreds of independent conversations are distinct denominators and must
be labelled.
