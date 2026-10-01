"""Offline tests exercise persistence/tool contracts, not LLM behavior."""
from __future__ import annotations

import copy
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m


class MettleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mettle test ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "AGENTS.md").write_text("# Existing project rules\nNever replace me.\n")
        m.install(self.root, [])
        self.store = m.Store(self.root)

    def draft(self, kind, identifier, **changes):
        meta, body = m.decode(m.template(kind))
        meta.update(id=identifier, title="An observed example")
        meta.update(changes)
        return m.encode(meta, body.replace("TODO", "Recorded, scoped evidence or uncertainty."))

    def publish(self, kind, identifier, expected=None, **changes):
        text = self.draft(kind, identifier, **changes)
        with self.store.lock():
            path = self.store.publish(text, expected)
        return self.root / path

    def initial(self):
        self.publish("episode", "E-origin")
        self.publish("lesson", "L-bindings", 0, origin=["E-origin"], scope=["components/bindings"], tags=["generated"], aliases=["regeneration"], title="Change the schema rather than generated output")

    def support(self):
        self.publish("episode", "E-later")
        self.publish("review", "V-support", lesson="L-bindings", lesson_revision=1, episodes=["E-later"], assessment="support")
        self.publish("reconciliation", "C-support", operation="LINK_EVIDENCE", inputs=["L-bindings@1"], evidence=["V-support"])

    def revise(self, **changes):
        with self.store.lock():
            _, lessons = self.store.snapshot()
            old, body, _ = lessons["L-bindings"][-1]
        meta = copy.deepcopy(old)
        meta.update(revision=meta["revision"] + 1, **changes)
        with self.store.lock():
            return self.store.publish(m.encode(meta, body), old["revision"])

    def test_install_preserves_agents_and_has_single_personality(self):
        before = (self.root / "AGENTS.md").read_bytes()
        m.install(self.root, ["codex", "claude", "opencode"])
        self.assertEqual(before, (self.root / "AGENTS.md").read_bytes())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertTrue(self.store.path("personality/identity.md").exists())
        self.assertFalse(self.store.path("pilot-agent-a").exists())
        self.assertFalse(self.store.path("skills").exists())
        self.assertIn("state/", (self.store.home / ".gitignore").read_text())

    def test_missing_root_agents_requires_installation_to_recreate_it(self):
        (self.root / "AGENTS.md").unlink()
        with self.assertRaisesRegex(m.MettleError, "Missing root AGENTS.md"):
            m.Store(self.root)
        helper = self.store.home / "tools/mettle.py"
        failed = subprocess.run([sys.executable, "-X", "utf8", str(helper), "bootstrap", "--hook"],
                                input=b"{}", capture_output=True, timeout=30)
        self.assertFalse(json.loads(failed.stdout)["continue"])
        self.assertFalse((self.root / "AGENTS.md").exists())
        nested = self.root / "component"
        nested.mkdir()
        (nested / "AGENTS.md").write_bytes(b"# Component instructions\n")
        configured = subprocess.run([sys.executable, "-X", "utf8", str(helper), "install", "--configure-only", "--runtimes", "claude"],
                                    cwd=nested, capture_output=True, timeout=30)
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertTrue(json.loads(configured.stdout)["agents_created"])
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"# Project instructions\n")
        self.assertEqual((nested / "AGENTS.md").read_bytes(), b"# Component instructions\n")
        checked = subprocess.run([sys.executable, "-X", "utf8", str(helper), "check"],
                                 cwd=nested, capture_output=True, timeout=30)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_install_is_idempotent_and_preserves_state(self):
        self.initial()
        profile = self.store.path("personality/self-model.md")
        profile.write_text("# Observed self-model\nOperator's customized file.\n")
        m.install(self.root, ["codex", "claude", "opencode"])
        m.install(self.root, ["codex", "claude", "opencode"])
        self.assertIn("customized", profile.read_text())
        for name in (".codex/hooks.json", ".claude/settings.local.json"):
            groups = json.loads((self.root / name).read_text())["hooks"]["SessionStart"]
            self.assertEqual(len(groups), 1)
        self.assertEqual(len(self.store.snapshot()[1]), 1)

    def test_preserve_unrelated_config_handlers(self):
        target = self.root / ".claude/settings.local.json"
        target.parent.mkdir()
        other = {"type": "command", "command": "echo existing"}
        target.write_text(json.dumps({"permissions": {"allow": ["Read"]}, "hooks": {"SessionStart": [{"matcher": "startup", "hooks": [other]}]}}))
        m.install(self.root, ["claude"])
        data = json.loads(target.read_text())
        self.assertEqual(data["permissions"], {"allow": ["Read"]})
        self.assertEqual(data["hooks"]["SessionStart"][0]["hooks"], [other])
        self.assertEqual(len(list(target.parent.glob("*.mettle-backup-*"))), 1)

    def test_jsonc_requires_manual_merge_without_changes(self):
        (self.root / "opencode.jsonc").write_text('{// preserve comments\n}')
        before = (self.store.home / "PERSONALITY.md").read_bytes()
        with self.assertRaises(m.MettleError):
            m.install(self.root, ["codex", "opencode"])
        self.assertFalse((self.root / ".codex/hooks.json").exists())
        self.assertEqual(before, (self.store.home / "PERSONALITY.md").read_bytes())

    def test_invalid_config_preflight(self):
        target = self.root / "opencode.json"
        target.write_text("not JSON")
        with self.assertRaises(ValueError):
            m.install(self.root, ["codex", "opencode"])
        self.assertFalse((self.root / ".codex/hooks.json").exists())
        self.assertEqual(target.read_text(), "not JSON")

    def test_opencode_loads_only_protocol(self):
        fragment = m.adapter(self.root, "opencode")
        self.assertEqual(fragment["instructions"], [".agent-personality/PERSONALITY.md", ".agent-personality/LOCATION.md"])
        merged = m.merge_config({"instructions": ["TEAM.md"], "model": "existing"}, fragment, "opencode")
        self.assertEqual(merged["instructions"], ["TEAM.md", ".agent-personality/PERSONALITY.md", ".agent-personality/LOCATION.md"])
        self.assertEqual(merged["model"], "existing")

    def test_opencode_locator_contains_absolute_root(self):
        content = (self.store.home / "LOCATION.md").read_text(encoding="utf-8")
        location = json.loads(content.split("```json\n", 1)[1].split("\n```", 1)[0])
        self.assertEqual(location["root"], str(self.store.root))
        self.assertEqual(location["argv_prefix"][1:3], ["-X", "utf8"])
        self.assertNotIn("state/personality", content)

    def test_native_hook_schema(self):
        for runtime in ("codex", "claude"):
            fragment = m.adapter(self.root, runtime)
            group = fragment["hooks"]["SessionStart"][0]
            self.assertIn("compact", group["matcher"])
            handler = group["hooks"][0]
            self.assertTrue(m.owned_handler(handler, runtime))
            if runtime == "claude":
                self.assertEqual(handler["args"][2], str(self.store.home / "tools/mettle.py"))
            elif os.name == "nt":
                self.assertIn("commandWindows", handler)

    def test_nested_directory_bootstrap_uses_fixed_root(self):
        nested = self.root / "components/nested"
        nested.mkdir(parents=True)
        (nested / "AGENTS.md").write_text("Wrong root\n")
        helper = self.store.home / "tools/mettle.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(helper), "bootstrap", "--runtime", "claude", "--hook"], cwd=nested, input=json.dumps({"hook_event_name": "SessionStart", "source": "compact", "session_id": "test-session"}), encoding="utf-8", capture_output=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "SessionStart")
        context = data["hookSpecificOutput"]["additionalContext"]
        snapshot = json.loads(context.rsplit("\n\n", 1)[1])
        self.assertEqual(snapshot["root"], str(self.store.root))
        self.assertNotIn("Wrong root", context)
        audits = list(self.store.path("sessions").glob("*.json"))
        self.assertEqual(json.loads(audits[0].read_text())["source"], "compact")

    def test_missing_state_hook_emits_explicit_failure(self):
        self.store.path("personality/identity.md").unlink()
        output = io.StringIO()
        with mock.patch("sys.stdin", io.StringIO('{"source":"startup"}')), contextlib.redirect_stdout(output):
            code = m.main(["bootstrap", "--root", str(self.root), "--runtime", "codex", "--hook"])
        self.assertEqual(code, 0)
        data = json.loads(output.getvalue())
        self.assertFalse(data["continue"])
        self.assertIn("Do not claim", data["hookSpecificOutput"]["additionalContext"])

    def test_oversized_bootstrap_fails_without_truncation(self):
        self.store.path("personality/self-model.md").write_text("x" * m.MAX_CONTEXT)
        with self.store.lock(), self.assertRaises(m.MettleError):
            m.bootstrap(self.store, "manual", {})
        self.assertEqual(list(self.store.path("sessions").glob("*.json")), [])

    def test_empty_history_valid_and_no_forced_retrieval(self):
        with self.store.lock():
            self.assertEqual(m.search(self.store, ["nonexistent"], 5, None), [])
            self.assertEqual(self.store.snapshot(), ({}, {}))

    def test_immutable_records_reject_overwrite(self):
        path = self.publish("episode", "E-original")
        before = path.read_bytes()
        with self.assertRaises(m.MettleError):
            self.publish("episode", "E-original")
        self.assertEqual(path.read_bytes(), before)

    def test_missing_evidence_rejected(self):
        with self.assertRaises(m.MettleError):
            self.publish("lesson", "L-missing", 0, scope=["general"], origin=["E-missing"])

    def test_full_supported_lifecycle(self):
        self.initial()
        self.support()
        old = self.store.path("memory/lessons/engineering/L-bindings/revisions/0001.md").read_bytes()
        self.revise(status="active", support=["V-support"], reconciliations=["C-support"])
        records, lessons = self.store.snapshot()
        self.assertEqual(lessons["L-bindings"][-1][0]["revision"], 2)
        self.assertEqual(len(records), 4)
        self.assertEqual(old, self.store.path("memory/lessons/engineering/L-bindings/revisions/0001.md").read_bytes())

    def test_stale_revision_number_rejected(self):
        self.initial()
        with self.assertRaises(m.MettleError):
            self.publish("lesson", "L-bindings", 0, origin=["E-origin"], scope=["general"])

    def test_active_requires_later_support(self):
        self.publish("episode", "E-origin")
        with self.assertRaises(m.MettleError):
            self.publish("lesson", "L-no-support", 0, origin=["E-origin"], scope=["general"], status="active")

    def test_review_requires_exact_accepted_revision(self):
        self.initial()
        with self.assertRaises(m.MettleError):
            self.publish("review", "V-future", lesson="L-bindings", lesson_revision=2, episodes=["E-origin"])

    def test_counterevidence_flagged_and_retained(self):
        self.initial()
        self.publish("episode", "E-counter")
        self.publish("review", "V-counter", lesson="L-bindings", lesson_revision=1, episodes=["E-counter"], assessment="counterexample")
        result = m.search(self.store, ["generated"], 5, None)
        self.assertEqual(result[0]["pending_counterevidence"], ["V-counter"])
        self.publish("reconciliation", "C-contest", operation="MARK_CONTESTED", inputs=["L-bindings@1"], evidence=["V-counter"])
        self.revise(status="contested", counterevidence=["V-counter"], reconciliations=["C-contest"])
        self.publish("reconciliation", "C-revise", operation="REVISE", inputs=["L-bindings@2"], evidence=["V-counter"])
        with self.assertRaises(m.MettleError):
            self.revise(counterevidence=[], reconciliations=["C-contest", "C-revise"])

    def test_wrong_evidence_classification_rejected(self):
        self.initial()
        self.support()
        with self.assertRaises(m.MettleError):
            self.revise(counterevidence=["V-support"], reconciliations=["C-support"])

    def test_alias_scope_and_historical_exclusion(self):
        self.initial()
        self.assertEqual(m.search(self.store, ["regeneration"], 5, "components/bindings")[0]["id"], "L-bindings")
        self.assertEqual(m.search(self.store, ["regeneration"], 5, "other-component"), [])
        self.support()
        self.revise(status="retired", support=["V-support"], reconciliations=["C-support"])
        self.assertEqual(m.search(self.store, ["generated"], 5, None), [])

    def test_new_revision_needs_reconciliation(self):
        self.initial()
        with self.assertRaises(m.MettleError):
            self.revise(title="A new title")

    def test_derived_view_repair_keeps_immutable_record(self):
        self.initial()
        current = self.store.path("memory/lessons/engineering/L-bindings/current.md")
        accepted = self.store.path("memory/lessons/engineering/L-bindings/revisions/0001.md").read_bytes()
        current.write_text("Interrupted generated view\n")
        with self.assertRaises(m.MettleError):
            self.store.snapshot()
        records, lessons = self.store.snapshot(verify_views=False)
        self.store.reindex(lessons)
        self.assertEqual(current.read_bytes(), accepted)
        self.store.snapshot()

    def test_lock_prevents_overlapping_helper_operations(self):
        with self.store.lock():
            with self.assertRaises(m.MettleError):
                with self.store.lock():
                    self.fail("Must not enter")
        self.assertFalse(self.store.path(".write-lock").exists())

    def test_traversal_and_symlinks_rejected(self):
        with self.assertRaises(m.MettleError):
            self.store.path("../outside")
        try:
            self.store.path("memory/episodes/link").symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            if exc.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP} or getattr(exc, "winerror", None) == 1314:
                self.skipTest(f"Symlink creation is unavailable to this account: {exc}")
            raise
        with self.assertRaises(m.MettleError):
            self.store.snapshot()

    def test_nested_domains(self):
        self.publish("episode", "E-origin")
        self.publish("lesson", "L-nested", 0, origin=["E-origin"], scope=["bindings"], domain="engineering/generated")
        self.assertTrue(self.store.path("memory/lessons/engineering/generated/INDEX.md").exists())

    def test_template_placeholders_rejected(self):
        with self.assertRaises(m.MettleError):
            self.store.publish(m.template("episode"), None)

    def test_malformed_metadata_rejected(self):
        for text in ("plain markdown", "---\n[]\n---\n", "---\n{\"schema\":1,\"kind\":[]}\n---\n"):
            with self.assertRaises(m.MettleError):
                meta, body = m.decode(text)
                m.validate_record(meta, body)

    def test_cli_check_and_search(self):
        for args in (["check", "--root", str(self.root)], ["search", "--root", str(self.root), "nothing"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(m.main(args), 0)
            json.loads(output.getvalue())

    def test_120_archived_episodes_survive_new_process(self):
        # Synthetic persistence stress test; NOT 120 AI conversations or behavioral evidence.
        for index in range(120):
            self.publish("episode", f"E-synthetic-{index}")
        result = subprocess.run([sys.executable, str(self.store.home / "tools/mettle.py"), "check"], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)["records"], 120)


if __name__ == "__main__":
    unittest.main()
