"""Synthetic record contracts; these tests do not evaluate an LLM's behavior."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

import mettle as m


FIXTURE = Path(__file__).resolve().parents[1] / "examples/behavioral-review.json"


def record_text(item: dict) -> str:
    body = "# " + item["metadata"]["title"] + "\n\n" + "\n\n".join(
        f"## {heading}\n{text}" for heading, text in item["sections"].items()
    )
    return m.encode(item["metadata"], body)


class BehavioralReviewRecordsTest(unittest.TestCase):
    def setUp(self):
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertIs(fixture["synthetic"], True)
        self.items = fixture["records"]
        self.temporary = tempfile.TemporaryDirectory(prefix="mettle-review-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "AGENTS.md").write_text("# Synthetic target\n", encoding="utf-8")
        m.install(self.root, [])
        self.store = m.Store(self.root)

    def publish_item(self, item: dict) -> None:
        meta = item["metadata"]
        expected = meta["revision"] - 1 if meta["kind"] == "lesson" else None
        with self.store.lock():
            self.store.publish(record_text(item), expected)

    def publish_through(self, identifier: str, revision: int | None = None) -> None:
        for item in self.items:
            self.publish_item(item)
            meta = item["metadata"]
            if meta["id"] == identifier and (revision is None or meta.get("revision") == revision):
                return
        self.fail(f"Fixture endpoint not found: {identifier}@{revision}")

    def test_fixture_uses_existing_schema_and_preserves_all_outcomes(self):
        for item in self.items:
            self.publish_item(item)
        with self.store.lock():
            records, lessons = self.store.snapshot()
        self.assertEqual(len(records), 9)
        self.assertEqual([x[0]["revision"] for x in lessons["L-example-schema"]], [1, 2, 3])
        latest = lessons["L-example-schema"][-1][0]
        self.assertEqual(latest["status"], "contested")
        self.assertEqual(latest["support"], ["V-example-applied"])
        self.assertEqual(latest["counterevidence"], ["V-example-counter"])
        self.assertEqual(records["V-example-readonly"][0]["assessment"], "not_applied")

    def test_non_application_cannot_be_relabelled_as_support(self):
        self.publish_through("C-example-support")
        second = copy.deepcopy(next(item for item in self.items if item["metadata"].get("revision") == 2))
        second["metadata"]["support"] = ["V-example-readonly"]
        with self.assertRaises(m.MettleError):
            self.publish_item(second)
        with self.store.lock():
            _, lessons = self.store.snapshot()
        self.assertEqual(len(lessons["L-example-schema"]), 1)

    def test_counterexample_is_visible_before_and_after_reconciliation(self):
        self.publish_through("V-example-counter")
        with self.store.lock():
            candidates = m.search(self.store, ["demo-generator"], 5, "components/demo")
        self.assertEqual(candidates[0]["pending_counterevidence"], ["V-example-counter"])
        remaining = False
        for item in self.items:
            if remaining:
                self.publish_item(item)
            if item["metadata"]["id"] == "V-example-counter":
                remaining = True
        with self.store.lock():
            candidates = m.search(self.store, ["demo-generator"], 5, "components/demo")
            records, _ = self.store.snapshot()
        self.assertEqual(candidates[0]["status"], "contested")
        self.assertEqual(candidates[0]["pending_counterevidence"], [])
        self.assertIn("V-example-counter", records)

    def test_original_revision_survives_reconciliation_and_reindex(self):
        self.publish_through("L-example-schema", 1)
        revision = self.store.path("memory/lessons/engineering/generated/L-example-schema/revisions/0001.md")
        original = revision.read_bytes()
        for item in self.items[2:]:
            self.publish_item(item)
        with self.store.lock():
            _, lessons = self.store.snapshot()
            self.store.reindex(lessons)
        self.assertEqual(revision.read_bytes(), original)

    def test_source_faithful_alias_retrieves_without_changing_state(self):
        self.publish_through("L-example-schema", 1)
        before = {path.relative_to(self.store.state): path.read_bytes()
                  for path in self.store.state.rglob("*.md")}
        with self.store.lock():
            candidates = m.search(self.store, ["demo-generator"], 5, "components/demo")
            unrelated = m.search(self.store, ["nonexistent-diagnostic-913"], 5, None)
        after = {path.relative_to(self.store.state): path.read_bytes()
                 for path in self.store.state.rglob("*.md")}
        self.assertEqual(candidates[0]["id"], "L-example-schema")
        self.assertEqual(candidates[0]["status"], "proposed")
        self.assertEqual(unrelated, [])
        self.assertEqual(before, after)

    def test_install_never_seeds_synthetic_experiences(self):
        with self.store.lock():
            records, lessons = self.store.snapshot()
            context = m.bootstrap(self.store, "manual", {})
        self.assertEqual(records, {})
        self.assertEqual(lessons, {})
        self.assertNotIn("E-example-origin", context)
        self.assertIn("No experience-supported assessments", context)
        self.assertLessEqual(len(context), m.MAX_CONTEXT)


if __name__ == "__main__":
    unittest.main()
