"""Synthetic record contracts, not tests of autonomous activity or LLM learning.

Recover a bad lesson revision with an ordinary REVISE publication. No operator
approval API, new schema, runtime launcher, or destructive rollback is involved.
All observations below are authored fixtures, never real experimental evidence.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import mettle as m


class AgentOwnedLearningTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-learning-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "AGENTS.md").write_bytes(b"# Existing mandate\n")
        m.install(self.root, [])
        self.store = m.Store(self.root)

    def record(self, kind, identifier, sections, **fields):
        meta, _ = m.decode(m.template(kind))
        meta.update(id=identifier, title="Synthetic recovery example", **fields)
        body = "# Synthetic fixture\n\n" + "\n\n".join(
            f"## {heading}\n{text}" for heading, text in sections.items()
        )
        return m.encode(meta, body)

    def publish(self, text, expected=None):
        with self.store.lock():
            return self.root / self.store.publish(text, expected)

    def episode(self, identifier, observation, origin="self-directed investigation", evidence=None):
        return self.publish(self.record("episode", identifier, {
            "Observe": f"Activity origin: {origin}. Standing goal: investigate demo-cache freshness. "
                       f"Opportunity: a pending review. Selected because it may resolve that uncertainty. {observation}",
            "Evidence": evidence or "Authored test fixture only; no real cache experiment or model run occurred. "
                                     "The scenario permits local disposable checks, not production changes.",
            "Interpret": "A cache shortcut may depend on whether inputs can change; this is a scoped hypothesis.",
            "Uncertainty": "Outcome and provenance are synthetic. No general effectiveness or causal result is asserted.",
        }, runtime="synthetic", model="none", session="fixture", corrects=[]))

    def initial(self):
        self.episode("E-origin", "The authored scenario finds that reuse works for immutable inputs.")
        sections = {
            "Trigger": "Repeated reads of immutable inputs in components/demo-cache.",
            "Practice": "Reuse the checked result only while the inputs remain immutable.",
            "Exceptions": "Recheck mutable inputs and any changed prerequisite; this does not authorize a deployment.",
            "Expected result": "Avoid repeated work without assuming that mutable input remains fresh.",
            "Review plan": "Investigate a later applicable case and a counterexample before extending scope.",
            "Change rationale": "Proposed from the authored incident E-origin; not independently validated.",
        }
        self.publish(self.record("lesson", "L-cache", sections, revision=1, status="proposed",
                                 domain="engineering", scope=["components/demo-cache: immutable inputs"],
                                 tags=["cache", "immutable"], aliases=["freshness"], origin=["E-origin"],
                                 support=[], counterevidence=[], reconciliations=[], supersedes=[], superseded_by=[]), 0)

    def review(self, identifier, revision, episode, assessment):
        return self.publish(self.record("review", identifier, {
            "Situation": "An opportunity under the standing demo-cache investigation; no new user task is assumed.",
            "Application": "The authored scenario records application to the described inputs within the permitted sandbox.",
            "Outcome": "See the linked synthetic episode, including what was only reported and what was inspected.",
            "Assessment": f"{assessment}; a fixture classification, not a measured LLM decision. Review scope again later.",
        }, lesson="L-cache", lesson_revision=revision, episodes=[episode], assessment=assessment))

    def reconcile(self, identifier, revision, evidence):
        return self.publish(self.record("reconciliation", identifier, {
            "Decision": "Revise the current practice within the existing learning scope, retaining all evidence.",
            "Evidence assessment": "Evidence remains synthetic and conditional; old support is not automatically new validation.",
            "Planned changes": f"Publish the next revision after L-cache@{revision}; this record alone does not execute the change.",
        }, operation="REVISE", inputs=[f"L-cache@{revision}"], evidence=evidence))

    def current(self):
        with self.store.lock():
            _, lessons = self.store.snapshot()
            meta, body, _ = lessons["L-cache"][-1]
        return copy.deepcopy(meta), body

    def supported_then_bad(self):
        self.initial()
        self.episode("E-support", "A later authored case also succeeds with immutable inputs.")
        self.review("V-support", 1, "E-support", "support")
        self.reconcile("C-overgeneralize", 1, ["V-support"])
        meta, body = self.current()
        meta.update(revision=2, status="active", scope=["components/demo-cache: all inputs"],
                    support=["V-support"], reconciliations=["C-overgeneralize"])
        body = body.replace("only while the inputs remain immutable", "for both immutable and mutable inputs")
        # This deliberately bad generalization is structurally legal. The helper
        # cannot infer that prose overextends the supporting evidence.
        self.publish(m.encode(meta, body), 1)
        self.episode("E-counter", "A mutable input changes and the authored scenario returns stale cached data.")
        self.review("V-counter", 2, "E-counter", "counterexample")

    def recovery_draft(self):
        meta, _ = self.current()
        first = self.store.path("memory/lessons/engineering/L-cache/revisions/0001.md")
        _, earlier_body = m.decode(m.read(first))
        meta.update(revision=3, status="proposed", scope=["components/demo-cache: immutable inputs"],
                    counterevidence=["V-counter"],
                    reconciliations=[*meta["reconciliations"], "C-recover"])
        # Retain current evidence arrays, not the old revision's empty arrays.
        body = earlier_body + "\n\nRecovery from L-cache@1 after the counterexample to L-cache@2. " \
               "The scenario rechecked immutability as a prerequisite. Earlier support is retained historically; " \
               "a new applicable review is pending. No broader permission or lifetime validity is inferred."
        return m.encode(meta, body)

    def test_recovery_publishes_new_revision_and_preserves_evidence(self):
        self.supported_then_bad()
        old_files = {p: p.read_bytes() for p in self.store.files("memory", "*.md")
                     if p.name not in {"current.md", "INDEX.md"}}
        self.reconcile("C-recover", 2, ["V-counter", "V-support"])
        self.publish(self.recovery_draft(), 2)
        for path, before in old_files.items():
            self.assertEqual(path.read_bytes(), before)
        meta, body = self.current()
        self.assertEqual(meta["revision"], 3)
        self.assertEqual(meta["status"], "proposed")
        self.assertEqual(meta["support"], ["V-support"])
        self.assertEqual(meta["counterevidence"], ["V-counter"])
        self.assertEqual(meta["reconciliations"], ["C-overgeneralize", "C-recover"])
        self.assertIn("Recovery from L-cache@1", body)
        self.assertIn("new applicable review is pending", body)
        self.assertEqual(m.search(self.store, ["cache"], 5, None)[0]["revision"], 3)

    def test_recovery_intent_is_not_a_completed_change(self):
        self.supported_then_bad()
        self.reconcile("C-recover", 2, ["V-counter"])
        self.assertEqual(self.current()[0]["revision"], 2)
        self.assertEqual(m.search(self.store, ["cache"], 5, None)[0]["pending_counterevidence"], ["V-counter"])

    def test_recovery_obeys_existing_publication_guards(self):
        self.supported_then_bad()
        draft = self.recovery_draft()
        with self.assertRaises(m.MettleError):
            self.publish(draft, 2)  # Missing reconciliation.
        self.reconcile("C-recover", 2, ["V-counter"])
        with self.assertRaises(m.MettleError):
            self.publish(draft, 1)  # Stale expected revision.
        meta, body = m.decode(draft)
        meta["support"] = []
        with self.assertRaises(m.MettleError):
            self.publish(m.encode(meta, body), 2)  # Cannot discard intervening evidence.
        self.assertEqual(self.current()[0]["revision"], 2)

    def test_recovery_does_not_revert_historical_bytes_or_instructions(self):
        protected = [self.root / "AGENTS.md", self.store.home / "PERSONALITY.md",
                     self.store.path("installation.json"), *self.store.path("personality").glob("*.md")]
        before = {p: p.read_bytes() for p in protected}
        self.supported_then_bad()
        self.reconcile("C-recover", 2, ["V-counter"])
        self.publish(self.recovery_draft(), 2)
        with self.store.lock():
            _, lessons = self.store.snapshot()
            self.store.reindex(lessons)
        for path, content in before.items():
            self.assertEqual(path.read_bytes(), content)

    def test_recovery_survives_fresh_process_and_reinstallation(self):
        self.supported_then_bad()
        self.reconcile("C-recover", 2, ["V-counter"])
        self.publish(self.recovery_draft(), 2)
        accepted = {p: p.read_bytes() for p in self.store.files("memory", "*.md")
                    if p.name not in {"current.md", "INDEX.md"}}
        m.install(self.root, [])
        helper = self.store.home / "tools/mettle.py"
        checked = subprocess.run([sys.executable, "-X", "utf8", str(helper), "check"],
                                 capture_output=True, encoding="utf-8", timeout=30, check=True)
        self.assertEqual(json.loads(checked.stdout)["revisions"], 3)
        shown = subprocess.run([sys.executable, "-X", "utf8", str(helper), "show", "L-cache"],
                               capture_output=True, encoding="utf-8", timeout=30, check=True)
        self.assertEqual(m.decode(shown.stdout)[0]["revision"], 3)
        for path, content in accepted.items():
            self.assertEqual(path.read_bytes(), content)

    def test_external_report_remains_an_episode_not_automatic_validation(self):
        self.initial()
        report = self.episode("E-peer", "A peer reports that the shortcut also works for mutable inputs.",
                              origin="peer interaction", evidence=(
                                  "Origin: peer P, repeating source S. Examination: report read, source not inspected, "
                                  "result not reproduced locally. Assessment: shared source, independence unknown. "
                                  "This is an invented fixture, not an actual peer or external paper."))
        # A useful external claim may be retained without inventing a test or
        # promoting a procedure. Free-form provenance is not semantically checked.
        self.assertEqual(self.current()[0]["support"], [])
        self.assertEqual(self.current()[0]["status"], "proposed")
        self.assertIn("not reproduced locally", m.read(report))
        self.reconcile("C-report", 1, ["E-peer"])
        meta, body = self.current()
        meta.update(revision=2, support=["E-peer"], reconciliations=["C-report"])
        with self.assertRaises(m.MettleError):
            self.publish(m.encode(meta, body), 1)  # Support needs a review, not just a reported claim.

    def test_non_task_origins_fit_existing_episode_schema(self):
        for number, origin in enumerate(("human request", "standing commitment", "self-directed exploration",
                                         "peer interaction", "external observation", "experiment")):
            self.episode(f"E-activity-{number}", "A bounded observation with unresolved interpretation.", origin)
        with self.store.lock():
            records, lessons = self.store.snapshot()
        self.assertEqual(len(records), 6)
        self.assertEqual(lessons, {})  # An experience need not create a lesson or personality claim.
        self.assertTrue(all(entry[0]["schema"] == 1 for entry in records.values()))

    def test_install_does_not_seed_experience_or_reset_existing_handoff(self):
        # A runner/agent may retain a private continuity note in the existing
        # sessions directory. Preservation is not automatic loading or scheduling.
        handoff = self.store.path("sessions/pending-investigation.md")
        note = b"# Pending question\nInvestigate within current permission; wait if no suitable opportunity.\n"
        handoff.write_bytes(note)
        m.install(self.root, [])
        self.assertEqual(handoff.read_bytes(), note)
        self.assertEqual(self.store.snapshot(), ({}, {}))


if __name__ == "__main__":
    unittest.main()
