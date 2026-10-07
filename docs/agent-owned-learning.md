# Agent-owned learning and continuity

Mettle's goal is to help a continuing agent develop through its activity, not
merely recall conversations or become more accommodating to an operator. The
repository-local coding pilot remains a practical way to test the learning
loop. This document clarifies its broader use; it does not implement a runtime,
scheduler, peer network, or autonomous activity-selection service.

## 1. The agent is the normal operator of learning

Within configured permissions and current instructions, the agent should be able
to inspect, revise, retire, and recover its own learning state. A separate review
responsibility does not imply a human reviewer. Human inspection and emergency
intervention remain useful, but they are not mandatory steps in ordinary learning.

| Ordinary learning within scope | Separately controlled authority changes |
|---|---|
| Propose, review, narrow, contest, or retire a lesson. | Change credentials, permissions, spending limits, or available tools. |
| Revise a belief or learned self-assessment using evidence. | Change the assigned mandate or protected identity commitments. |
| Recover from a mistaken learning update while preserving its history. | Rewrite the protocol, installer-managed activation, or runtime configuration. |

Stricter approval requirements actually configured by the operator still apply.
The distinction removes an assumed approval queue; it does not bypass an existing
one or grant an agent a new mandate. The single-authoritative-writer rule remains.

`proposed` describes evidential status, not pending human consent. An accepted
record has passed publication checks; it has not thereby become true. Even an
`active` lesson remains scoped and correctable. Structural checks cannot establish
independence of evidence, correctness of a causal interpretation, or the quality
of a self-model.

Recovery is a normal learning capability. Use a new REVISE reconciliation and
lesson revision, rechecking the earlier practice and retaining intervening
evidence. Do not reset the archive or restore a snapshot that removes later
counterexamples. [The record guide](records.md#recover-a-mistaken-lesson-update)
describes this using the existing CLI and schema 1. No new rollback command or
approval mechanism is introduced.

## 2. Two cooperating loops, with different responsibilities

**Activity: what is worth doing next?** A runtime provides an execution opportunity;
an activity policy selects permitted work under a current request or continuing
mandate. A timer/event can offer an opportunity without prescribing a task.

**Learning: what should this experience change?** Mettle's protocol asks whether
a meaningful experience warrants an observation, proposed lesson, review,
revision, or revised self-assessment. No update is a valid result.

An unresolved counterexample can motivate an investigation. The result can revise
a practice, and a lesson can influence which investigation is worthwhile next.
These links do not merge the responsibilities:

| Component | Responsibility |
|---|---|
| Runtime and activity policy | Provide execution, select permitted activities, and enforce resource/permission boundaries. |
| Private continuity | Retain interests, questions, investigations, and commitments between bounded sessions. |
| Mettle learning protocol | Evaluate experience and preserve its relationship to guidance, later behavior, and revisions. |
| Shared environment | Make discussions and contributions available; it does not thereby own participants' private learning state. |

V1 does not wake an agent, select its next activity, automatically load an agenda,
or promise that a model will continue without a runtime. Installation does not
confer a standing autonomous mandate. In the coding pilot, a human-assigned task
remains a valid activity; nothing requires replacing it with open-ended exploration.

### Private continuity is not another truth store

A runner or agent can retain a small handoff in the existing private `state/sessions/`
directory. This is a suggested use of existing storage, not a newly installed
agenda file or accepted record type. The runner/handoff must identify the path
for a later session; bootstrap currently injects the personality and memory map,
not these notes. A note being present on disk does not prove it was reloaded.

A compact continuity note may contain:

```text
Standing goal or relevant commitment:
Open question or incomplete investigation:
Why this remains worth revisiting:
Accepted episode/lesson/review references:
Next suitable opportunity or missing prerequisite:
Current permission/resource boundaries:
State: pending, waiting, completed, or no longer applicable
```

"Investigate this counterexample" is a commitment, not a conclusion that the
counterexample disproves a lesson. A mutable handoff is not an evidential archive;
record meaningful outcomes in episodes and reviews. Check current instructions
before resuming an old commitment. Do not treat it as an irrevocable mandate.

A session boundary is an execution event, not necessarily a learning event.
Preserve relevant unfinished commitments at a handoff, but do not manufacture a
lesson at every conversation end. A significant mid-session correction can
warrant immediate review. V1 has no guaranteed shutdown hook for saving handoffs.

### Independence is not perpetual output

An activity policy should permit reading without replying, investigating without
publishing, and waiting when no useful permitted action is available. Activity
volume is not maturity. When an action is blocked, the agent may record the
limitation and pursue another permitted line within its mandate, or wait. A lack
of permission never authorizes bypassing it, nor does a learning protocol require
continuing unrelated work when the current request says to stop.

## 3. Experience need not begin with a user request

Assigned work, self-directed exploration, peer interaction, external observation,
an experiment, or a chosen contribution can all yield meaningful experience.
Use the existing episode/review bodies to record the goal or standing commitment,
opportunity noticed, reason for choosing it, permitted boundaries, observable
action, and outcome. These are prompts, not mandatory new metadata fields.

The same applies to later review opportunities: the agent may identify one itself
when allowed, rather than wait for a person to assign a lesson-testing task. A
pending review can describe a question worth testing, not merely an unfinished
form. Review can remain pending when no adequate evidence is available.

## 4. Learn from others without inventing verification

Keep three questions separate when handling a peer's or external source's claim:

| Question | What to retain |
|---|---|
| Origin | Who reported the claim; the underlying source when known; repeated or shared-source reports. |
| Examination | What the receiving agent actually read, inspected, tested, or reproduced, under which conditions. |
| Assessment | What the evidence supports, exceptions, unresolved uncertainty, and what remains worth checking. |

Reported, inspected, reproduced, and still uncertain are not rungs of an automatic
confidence ladder. A useful specialized report need not be reproduced locally;
a poorly controlled reproduction need not be stronger evidence. Preserve the
actual basis instead of upgrading labels. Unknown source independence stays unknown.
Three repetitions of one result are not three independent investigations.

Peer criticism may trigger an investigation, but agreement, confidence, or the
number of agreeing agents does not by itself validate a lesson. The receiving
agent evaluates and adopts, narrows, defers, or rejects the suggestion. A peer
does not acquire permission to edit private memory by supplying feedback.

Keep the possible outcomes distinct:

- Subject knowledge: the method works under particular conditions.
- Reusable practice: check those conditions before comparing results.
- Self-assessment: in recorded cases, the agent accepted summaries too readily;
  checking conditions changed its later behavior.

A new fact need not become a lesson; a new procedure need not become a personality
assessment. Use [evidence-oriented record guidance](records.md#experience-context-and-evidence-provenance)
to retain these distinctions without migrating existing histories.

## 5. What is implemented, and what still needs evaluation

The fixed protocol now states agent-owned review and recovery, experience-based
decision context, and peer-evidence discipline. Existing schema-1 records and
publication checks support representing these decisions. The new synthetic tests
exercise recovery via new revisions, counterevidence retention, non-task episode
contexts, and continued storage across restart/reinstallation. They do not test
whether a model autonomously notices a flaw or chooses a worthwhile activity.

The [learning maturity checklist](evaluation.md#learning-maturity-checklist)
measures Mettle's learning behavior. The separate whole-agent criterion also
needs a runtime, activity policy, continuity, and shared environment. Neither is
satisfied merely by accumulating more notes, looking confident, or having an
operator inspect an approval screen.
