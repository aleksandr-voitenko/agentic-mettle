#!/usr/bin/env python3
"""Synthetic storage walkthrough; no model calls or real learning claims."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import mettle as m


def record(kind: str, identifier: str, title: str, sections: dict[str, str], **fields) -> str:
    meta, _ = m.decode(m.template(kind))
    meta.update(id=identifier, title=title, **fields)
    body = "# " + title + "\n\n" + "\n\n".join(f"## {key}\n{value}" for key, value in sections.items())
    return m.encode(meta, body)


def main() -> None:
    m.configure_stdio()
    with tempfile.TemporaryDirectory(prefix="mettle-synthetic-") as temporary:
        root = Path(temporary)
        (root / "AGENTS.md").write_text("# Synthetic example project\n", encoding="utf-8", newline="\n")
        m.install(root, [])
        store = m.Store(root)

        def publish(text: str, expected: int | None = None) -> None:
            with store.lock():
                print(store.publish(text, expected))

        def episode(identifier: str, observation: str) -> None:
            publish(record("episode", identifier, "Synthetic generated-binding example", {
                "Observe": observation,
                "Evidence": "This is an authored fixture in examples/walkthrough.py, not a real agent execution.",
                "Interpret": "The component may require schema-first edits; this remains a scoped interpretation.",
                "Uncertainty": "No causal or model-performance conclusion follows from this synthetic fixture.",
            }, runtime="synthetic", model="none", session="walkthrough"))

        episode("E-first", "In the hypothetical incident, regeneration overwrote a hand-edited generated file.")
        lesson = record("lesson", "L-schema", "Change the source of generated bindings", {
            "Trigger": "A change to generated bindings in components/demo.",
            "Practice": "Modify the schema and regenerate, then inspect the diff and run the component tests.",
            "Exceptions": "Hand-maintained bindings or a changed generator require independent verification.",
            "Expected result": "Regeneration preserves the intended change.",
            "Review plan": "Observe a later applicable change and a case where the procedure should not apply.",
            "Change rationale": "A tentative practice based on E-first, not a demonstrated personal trait.",
        }, scope=["components/demo"], tags=["generated", "bindings"], aliases=["regeneration"], origin=["E-first"])
        publish(lesson, 0)
        episode("E-later", "In the hypothetical later case, a schema-first change survives regeneration.")
        publish(record("review", "V-later", "Synthetic later application", {
            "Situation": "Another generated-binding change in the same hypothetical component.",
            "Application": "The fixture says the proposed practice was applied.",
            "Outcome": "The authored scenario says regeneration preserved the change; no tests were actually executed on a generator.",
            "Assessment": "Illustrates recording support for one scoped case, not proof of effectiveness.",
        }, lesson="L-schema", lesson_revision=1, episodes=["E-later"], assessment="support"))
        publish(record("reconciliation", "C-link", "Link the later application", {
            "Decision": "Retain the scope and link V-later; do not rewrite instructions.",
            "Evidence assessment": "One synthetic supporting review; no independent experimental results.",
            "Planned changes": "Publish L-schema revision 2 with the support reference and active status in this demo only.",
        }, inputs=["L-schema@1"], evidence=["V-later"], operation="LINK_EVIDENCE"))
        meta, body = m.decode(lesson)
        meta = copy.deepcopy(meta)
        meta.update(revision=2, status="active", support=["V-later"], reconciliations=["C-link"])
        publish(m.encode(meta, body + "\n\nRevision 2 links the synthetic later application without broadening scope."), 1)
        with store.lock():
            print(json.dumps(m.search(store, ["generated", "bindings"], 5, None), indent=2))
        # A fresh process validates the archive, not a long-lived model's behavior.
        subprocess.run([sys.executable, "-X", "utf8", str(root / m.PACKAGE / "tools/mettle.py"), "check"], check=True)
        assert (store.path("memory/lessons/engineering/L-schema/revisions/0001.md")).is_file()
        print("Synthetic walkthrough completed. No model was called; no real learning effectiveness was measured.")


if __name__ == "__main__":
    main()
