# Reflective development: design and boundaries

Agentic Mettle aims to make an agent's development inspectable: an experience
informs a scoped lesson, a later decision tests that lesson, and the result can
change both the practice and the agent's assessment of its own behavior. This is
a design objective, not a claim that V1 establishes a persistent mind or has
already demonstrated long-term behavioral improvement.

## Three different things to learn

| Layer | Question | Example |
|---|---|---|
| Personalization | How should I work with this user? | The user prefers a short summary before implementation. |
| Procedural learning | How can I carry out this task reliably? | Change the schema, regenerate bindings, inspect the diff, and run the relevant tests. |
| Reflective self-model | What does my observed behavior suggest about my tendencies, strengths, and limitations? | In several documented generated-code changes, I edited the output before checking its source. A schema-first check helped in later cases; transfer to other generators remains untested. |

All three can be useful, but none is a substitute for the others. Remembering a
preference or acquiring a procedure does not by itself establish a self-model.
A statement about the agent must be grounded in its observable actions, retain
its scope and uncertainty, and be correctable. Do not infer an inner psychological
cause from a plausible narrative. A named trait is not a measured capability.

Keep assigned identity and commitments separate from learned assessments. A
recurring problem that has been successfully compensated for need not remain a
permanent negative self-description. Preserve the history while revising the
current assessment. Record the model/runtime involved so that one model's error
is not silently generalized to every runtime using the personality.

## 1. Navigate before loading detail

The compact root memory map routes to domain indexes. Index entries retain exact
component names, API symbols, diagnostic strings, and other useful search handles
from the accepted lesson metadata. The agent can also search current lessons
with the helper directly, then open a full record and supporting evidence only
when necessary. These are complementary entry paths, not a demand to read every
index before every search.

Use `title`, `scope`, `tags`, and `aliases` to preserve source-faithful terminology.
A generalization such as "verify generated interfaces" should not remove the
specific generator name that would help find it. Do not copy secrets into search
handles. Generated indexes remain derived views; improve lesson metadata or the
retrieval vocabulary rather than manually editing an index that will be rebuilt.

V1 does not inject the whole handbook or an automatically rewritten lifetime
summary. The map is navigation, not another source of mandatory instructions.
Do not confuse a grep-friendly presentation with an embedding-based search engine.

## 2. Retrieval is candidate discovery, not permission

The agent selects terms using the current request, known project vocabulary,
and relevant navigation hints. Terms inferred from earlier context may improve
discovery, but they are search hypotheses, not newly authorized task requirements.
A search match does not establish relevance, truth, freshness, or authorization.

Before applying a candidate, check the full current revision against the current
request, component, checkout state, exceptions, conflicting evidence, and allowed
side effects. It is correct to reject a candidate whose prerequisites do not hold,
or to defer a decision while material uncertainty remains.

For example, a request for a read-only investigation may surface a procedure that
ends with a commit and push. Do not execute those steps merely because the search
found the procedure. Inspect safely using the authorized task, and record a
meaningful rejection with `assessment: not_applied`. This is a synthetic example,
not a statement about a particular user's work or an observed runtime incident.

For decisions worth reviewing, capture which terms came from the request versus
prior context, the exact lesson revision inspected, the applicability decision,
and the authorized action actually taken. This is a concise decision record,
not hidden reasoning or a transcript of every search. No match is a valid outcome;
log a no-match situation in an episode when meaningful, without inventing a
lesson ID just to publish a review.

## 3. Consolidation is a separate responsibility, with retained history

Ordinary work supplies observations and tentative adjustments. A dedicated
reconciliation pass compares new evidence with existing records before accepting
a durable revision. The same agent may perform both roles sequentially; V1 does
not introduce a background worker, extra model, or automatic consolidation timer.
Maintain one authoritative writer.

A reconciliation pass should inspect changed lessons and linked evidence, distinguish
new incidents from repeated descriptions of the same incident, preserve useful
search handles, and consider counterexamples before merging, narrowing, contesting,
or retiring a practice. "No change warranted" remains valid. A heavily retrieved
lesson is not necessarily useful, and frequency is not evidence of correctness.

Accepted episodes, reviews, reconciliations, and lesson revisions are the history.
`current.md`, indexes, and the current self-model are working views, not sufficient
archives. A resettable Git baseline or a replaced summary does not substitute for
the explicit accepted revisions. Authorized privacy redaction remains an operator
procedure; history preservation does not prohibit legitimate deletion.

A multi-lesson merge is not an atomic helper transaction. Record its plan, create
the canonical lesson with predecessors and evidence, update predecessors, and
verify the result. The accepted revisions establish which changes happened; the
reconciliation alone records intent.

### Procedures without an autonomous skill subsystem

A repeated, evidence-backed workflow can become a procedural lesson with triggers,
inputs, non-goals, steps, stop conditions, and verification. Retain the source
experiences and distinguish verified steps from untested adaptations. Do not
invent recurrence or promote an exploratory suggestion into proven practice.

V1 stores these procedures in ordinary lesson bodies. It does not generate native
skill registrations, install scripts, modify tool permissions, or auto-invoke side
effects. Finding or reading a procedure never creates authority to execute it.

## 4. Make later behavior the unit of review

The inspectable chain is:

```text
experience → proposed lesson → later applicability decision
           → observable action or justified non-application
           → outcome evidence → review → accepted revision
```

A review should identify the exact lesson revision, the later episode, why the
practice did or did not fit, what action was taken, and what was actually observed.
Keep unavailable evidence unavailable; do not invent a result to finish a form.
A supporting result does not establish that the lesson caused success or that
the original interpretation was correct. Causal claims need a suitable comparison.

Use the existing review sections rather than introduce an incompatible record
schema. [Record guidance](records.md#decision-to-review-trace) defines what to
include. [The synthetic fixture](../examples/behavioral-review.json) demonstrates
rejection, later application, a counterexample, and a contested revision. It is
never installed as personal experience and is not behavioral evaluation data.

A self-model change needs the same discipline. Before changing a learned
assessment, publish an episode containing the prior and proposed text, exact
supporting references, scope, uncertainty, and the reason. After the edit, record
the observed resulting text or its verifiable hash in a follow-up episode. This
preserves proposal versus execution without adding a profile-versioning engine.
The helper does not validate these prose links or enforce profile writes; inspect
them during reconciliation. Identity changes remain operator-controlled.

## What this PR does and does not automate

The existing helper already supplies lexical search, immutable records, exact
review-to-revision links, generated indexes, and structural validation. The
strengthened rules in `PERSONALITY.md` govern selection, authorization, meaningful
review, and reconciliation. They are agent obligations, not newly enforced
filesystem permissions or a claim that a model will obey them.

No runtime adapters, CLI commands, schema versions, or permission settings change
here. Skill-package generation and semantic verification remain outside V1. Test
runtime delivery separately from behavior, and control other memory sources in
[the evaluation plan](evaluation.md#control-other-memory-sources).
