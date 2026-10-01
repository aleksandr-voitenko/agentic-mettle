"""Installer integration tests: temporary projects only, no model or runtime calls."""
from __future__ import annotations

import codecs
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_installer as setup


class Terminal(io.StringIO):
    def isatty(self):
        return True


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mettle setup ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.agents = self.root / "AGENTS.md"
        self.identity = self.root / m.PACKAGE / "state/personality/identity.md"
        self.dispositions = self.identity.with_name("dispositions.md")
        self.self_model = self.identity.with_name("self-model.md")

    def args(self, *flags):
        return m.parser().parse_args(["install", "--root", str(self.root), "--non-interactive", "--runtimes", *flags])

    def run_setup(self, *flags):
        return setup.run(m, self.args(*flags))

    def files(self):
        return {path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()}

    def test_dry_run_has_no_target_writes_and_previews_profiles(self):
        result = self.run_setup("--dry-run", "--identity-preset", "maintainer")
        self.assertEqual(self.files(), {})
        self.assertTrue(result["dry_run"])
        self.assertIn("maintenance", result["preview"]["profiles"]["identity.md"])
        self.assertIn(setup.BEGIN, result["preview"]["agents_block"])
        self.assertEqual(result["profiles"]["self-model.md"], "create")

    def test_fresh_install_creates_and_enables_root_without_fake_history(self):
        result = self.run_setup()
        self.assertIn(setup.BEGIN, self.agents.read_text(encoding="utf-8"))
        self.assertTrue(result["memory_history_preserved"])
        self.assertEqual(m.Store(self.root).snapshot(), ({}, {}))
        self.assertFalse((self.root / "CLAUDE.md").exists())
        self.assertIn("No experience-supported", self.self_model.read_text(encoding="utf-8"))
        self.assertFalse(list((self.root / m.PACKAGE / "state/sessions").iterdir()))

    def test_append_preserves_original_bytes_and_exact_backup(self):
        original = codecs.BOM_UTF8 + "# Проект\r\n\r\nKeep every setting.\r\n".encode("utf-8")
        self.agents.write_bytes(original)
        result = self.run_setup("--agents-position", "append")
        updated = self.agents.read_bytes()
        self.assertTrue(updated.startswith(original))
        self.assertEqual(updated.count(codecs.BOM_UTF8), 1)
        self.assertNotIn(b"\n", updated.replace(b"\r\n", b""))
        backup = [path for path in result["backups"] if path.startswith("AGENTS.md.")]
        self.assertEqual(len(backup), 1)
        self.assertEqual((self.root / backup[0]).read_bytes(), original)

    def test_prepend_preserves_unrelated_instructions(self):
        original = b"# Existing rules\n\nNo changes to component guidance."
        self.agents.write_bytes(original)
        self.run_setup("--agents-position", "prepend")
        self.assertTrue(self.agents.read_bytes().startswith(setup.BEGIN.encode()))
        self.assertTrue(self.agents.read_bytes().endswith(original))

    def test_reinstall_and_relocation_of_block_are_idempotent(self):
        self.agents.write_text("# Team rules\n", encoding="utf-8")
        for placement in ("append", "prepend", "append"):
            self.run_setup("--agents-position", placement)
            first = self.files()
            result = self.run_setup("--agents-position", placement)
            self.assertEqual(self.files(), first)
            self.assertEqual(result["backups"], [])
            self.assertTrue(all(item["action"] == "unchanged" for item in result["changes"]))
            self.assertEqual(self.agents.read_text(encoding="utf-8").count(setup.BEGIN), 1)
            self.assertEqual(self.agents.read_text(encoding="utf-8").count("# Team rules"), 1)

    def test_skip_preserves_existing_or_creates_neutral_marker(self):
        self.run_setup("--agents-position", "skip")
        self.assertEqual(self.agents.read_bytes(), b"# Project instructions\n")
        self.run_setup("--agents-position", "prepend")
        before = self.agents.read_bytes()
        self.run_setup("--agents-position", "skip")
        self.assertEqual(self.agents.read_bytes(), before)

    def test_malformed_markers_fail_before_any_changes(self):
        for text in (setup.BEGIN, setup.END, setup.BEGIN + "\n" + setup.BEGIN + "\n" + setup.END,
                     setup.END + "\n" + setup.BEGIN, "inline " + setup.BEGIN + "\n" + setup.END):
            self.agents.write_text(text, encoding="utf-8")
            before = self.files()
            with self.assertRaises(m.MettleError):
                self.run_setup()
            self.assertEqual(before, self.files())

    def test_updates_managed_body_not_user_body(self):
        self.agents.write_text("# Team\n\n" + setup.BEGIN + "\nold version\n" + setup.END + "\n\n## Footer\nKeep this.\n", encoding="utf-8")
        self.run_setup()
        after = self.agents.read_text(encoding="utf-8")
        self.assertNotIn("old version", after)
        self.assertIn("## Footer\nKeep this.\n", after)
        self.assertEqual(after.count(setup.BEGIN), 1)

    def test_default_profiles_and_no_learning_claims(self):
        self.run_setup()
        self.assertIn("preset: collaborator", self.identity.read_text(encoding="utf-8"))
        self.assertIn("preset: balanced", self.dispositions.read_text(encoding="utf-8"))
        self.assertIn("not learned traits", self.dispositions.read_text(encoding="utf-8"))

    def test_profile_constructor_and_trait_overrides(self):
        self.run_setup("--identity-preset", "reviewer", "--agent-name", "Марта", "--role", "Review API compatibility.",
                       "--focus", "Public interfaces", "--focus", "Recovery paths", "--disposition-preset", "deliberate",
                       "--communication", "concise", "--disagreement", "gentle")
        identity = self.identity.read_text(encoding="utf-8")
        self.assertIn("Assigned name: Марта", identity)
        self.assertIn("- Public interfaces\n- Recovery paths", identity)
        dispositions = self.dispositions.read_text(encoding="utf-8")
        self.assertIn("Communication (concise)", dispositions)
        self.assertIn("Verification (thorough)", dispositions)
        self.assertIn("Disagreement (gentle)", dispositions)

    def test_each_preset_and_dimension_is_renderable(self):
        for preset in setup.IDENTITIES:
            text = setup.identity_text(m, preset, None, None, None)
            self.assertIn("operator-assigned", setup.validate_profile(m, text, "identity.md"))
        for preset in setup.DISPOSITIONS:
            for dimension, options in setup.DIMENSIONS.items():
                for value in options:
                    text = setup.dispositions_text(m, preset, {dimension: value})
                    self.assertIn(f"{dimension.title()} ({value})", setup.validate_profile(m, text, "dispositions.md"))

    def test_custom_utf8_profile_files(self):
        identity = self.root / "input-identity.md"
        dispositions = self.root / "input-dispositions.md"
        identity.write_bytes(codecs.BOM_UTF8 + "# Identity\r\nAssigned: Zoë.\r\n".encode("utf-8"))
        dispositions.write_text("# Dispositions\nPrefer concrete examples.\n", encoding="utf-8")
        self.run_setup("--identity-file", str(identity), "--dispositions-file", str(dispositions))
        self.assertEqual(self.identity.read_bytes(), "# Identity\nAssigned: Zoë.\n".encode("utf-8"))
        self.assertEqual(self.dispositions.read_bytes(), b"# Dispositions\nPrefer concrete examples.\n")

    def test_invalid_profile_conflicts_and_oversize_fail_without_installing(self):
        identity = self.root / "input.md"
        identity.write_text("# Identity\n" + "x" * 8000, encoding="utf-8")
        for flags in (("--identity-file", str(identity)),
                      ("--identity-file", str(identity), "--agent-name", "A"),
                      ("--replace-profiles",),
                      ("--role", "one\ntwo")):
            before = self.files()
            with self.assertRaises(m.MettleError):
                self.run_setup(*flags)
            self.assertEqual(self.files(), before)

    def test_upgrade_preserves_personality_self_model_and_evidence(self):
        self.run_setup()
        self.identity.write_text("# My actual assigned identity\n", encoding="utf-8")
        self.dispositions.write_text("# Dispositions\nEvidence-developed preference.\n", encoding="utf-8")
        self.self_model.write_text("# Self-model\nActual recorded assessment.\n", encoding="utf-8")
        store = m.Store(self.root)
        meta, body = m.decode(m.template("episode"))
        meta["title"] = "Synthetic fixture"
        with store.lock():
            episode = store.publish(m.encode(meta, body.replace("TODO", "Synthetic evidence, not an LLM result.")), None)
        originals = {p: p.read_bytes() for p in (self.identity, self.dispositions, self.self_model, self.root / episode)}
        self.run_setup()
        self.assertTrue(all(path.read_bytes() == content for path, content in originals.items()))

    def test_existing_profiles_require_explicit_replacement(self):
        self.run_setup()
        before = self.files()
        with self.assertRaises(m.MettleError):
            self.run_setup("--identity-preset", "researcher")
        self.assertEqual(self.files(), before)
        original_dispositions = self.dispositions.read_bytes()
        original_self = self.self_model.read_bytes()
        original_identity = self.identity.read_bytes()
        result = self.run_setup("--identity-preset", "researcher", "--replace-profiles")
        self.assertEqual(self.dispositions.read_bytes(), original_dispositions)
        self.assertEqual(self.self_model.read_bytes(), original_self)
        backup = next(path for path in result["backups"] if "identity.md.mettle-backup" in path)
        self.assertEqual((self.root / backup).read_bytes(), original_identity)
        self.assertTrue(result["memory_history_preserved"])
        self.assertEqual(result["profiles"]["identity.md"], "replace")

    def test_runtime_configuration_preservation_and_repeated_merge(self):
        config = self.root / ".claude/settings.local.json"
        config.parent.mkdir()
        config.write_text(json.dumps({"permissions": {"allow": ["Read"]}, "hooks": {"SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": "echo preserve"}]}]}}), encoding="utf-8")
        flags = ("claude", "--agents-position", "prepend")
        self.run_setup(*flags)
        first = self.files()
        self.run_setup(*flags)
        self.assertEqual(self.files(), first)
        value = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(value["permissions"], {"allow": ["Read"]})
        self.assertEqual(len(value["hooks"]["SessionStart"]), 2)

    def test_saved_choices_are_reused_without_new_runtime_installation(self):
        self.run_setup("claude", "--agents-position", "prepend")
        args = m.parser().parse_args(["install", "--root", str(self.root), "--non-interactive"])
        with mock.patch.object(setup, "detected_runtimes", side_effect=AssertionError("Should use saved choices")):
            result = setup.run(m, args)
        self.assertEqual(result["runtimes"], ["claude"])
        self.assertEqual(result["agents_position"], "prepend")
        self.assertFalse((self.root / ".codex").exists())

    def test_invalid_runtime_config_and_jsonc_fail_before_marker(self):
        (self.root / "opencode.jsonc").write_text("{// keep comments\n}", encoding="utf-8")
        before = self.files()
        with self.assertRaises(m.MettleError):
            self.run_setup("opencode")
        self.assertEqual(self.files(), before)
        (self.root / "opencode.jsonc").unlink()
        (self.root / "opencode.json").write_text("bad JSON", encoding="utf-8")
        before = self.files()
        with self.assertRaises(ValueError):
            self.run_setup("opencode")
        self.assertEqual(self.files(), before)

    def test_changed_file_after_preview_is_not_overwritten(self):
        self.agents.write_text("# Before\n", encoding="utf-8")
        plan = m.install(self.root, [], agents_position="append", dry_run=True)
        self.agents.write_text("# Changed while reviewing\n", encoding="utf-8")
        before = self.files()
        with self.assertRaises(m.MettleError):
            m.install(self.root, [], agents_position="append", expected_plan=plan["plan_id"])
        self.assertEqual(before, self.files())

    def test_locked_or_damaged_store_is_not_reset(self):
        self.run_setup()
        store = m.Store(self.root)
        with store.lock():
            before = self.files()
            with self.assertRaises(m.MettleError):
                self.run_setup()
            self.assertEqual(self.files(), before)
        store.path("memory/vocabulary.md").write_text("invalid", encoding="utf-8")
        before = self.files()
        with self.assertRaises(m.MettleError):
            self.run_setup()
        self.assertEqual(self.files(), before)

    def test_configure_only_preserves_profiles_and_updates_placement(self):
        self.run_setup()
        identity = self.identity.read_bytes()
        result = self.run_setup("--configure-only", "--agents-position", "prepend")
        self.assertEqual(self.identity.read_bytes(), identity)
        self.assertEqual(result["profiles"]["identity.md"], "preserve")
        with self.assertRaises(m.MettleError):
            self.run_setup("--configure-only", "--identity-preset", "reviewer")

    def test_nested_installed_cli_and_no_implicit_cwd_root(self):
        self.run_setup()
        nested = self.root / "components/a"
        nested.mkdir(parents=True)
        (nested / "AGENTS.md").write_text("# Component only\n", encoding="utf-8")
        helper = self.root / m.PACKAGE / "tools/mettle.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(helper), "install", "--configure-only", "--non-interactive", "--dry-run"],
                                cwd=nested, capture_output=True, encoding="utf-8", check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["root"], str(self.root))
        self.assertFalse((nested / m.PACKAGE).exists())

    def test_presets_command_needs_no_target(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(m.main(["presets"]), 0)
        self.assertEqual(set(json.loads(out.getvalue())["identity_presets"]), set(setup.IDENTITIES))
        self.assertEqual(self.files(), {})

    def test_noninteractive_never_reads_stdin(self):
        with mock.patch("builtins.input", side_effect=AssertionError("No prompting in CI")):
            self.run_setup("--dry-run")
        self.assertEqual(self.files(), {})

    def test_explicit_interactive_requires_terminal(self):
        args = m.parser().parse_args(["install", "--root", str(self.root), "--interactive"])
        with mock.patch("sys.stdin", io.StringIO()), self.assertRaises(m.MettleError):
            setup.run(m, args)
        self.assertEqual(self.files(), {})

    def interactive(self, answers: list[str], *flags):
        args = m.parser().parse_args(["install", "--root", str(self.root), "--interactive", *flags])
        with mock.patch("sys.stdin", Terminal()), mock.patch("builtins.input", side_effect=answers), contextlib.redirect_stderr(io.StringIO()):
            return setup.run(m, args)

    def test_cancel_at_final_confirmation_leaves_target_unchanged(self):
        self.agents.write_text("# Existing\n", encoding="utf-8")
        before = self.files()
        result = self.interactive(["no"], "--runtimes", "--agents-position", "append", "--python-executable", sys.executable,
                                  "--identity-preset", "reviewer", "--disposition-preset", "balanced")
        self.assertTrue(result["cancelled"])
        self.assertEqual(self.files(), before)

    def test_interactive_constructor_matches_equivalent_flags(self):
        # All individual choices are editable, and final confirmation defaults to no.
        result = self.interactive(["preset", "reviewer", "Ada", "Review public APIs.", "Compatibility", "preset", "deliberate", "yes",
                                   "concise", "bounded", "thorough", "gentle", "yes"],
                                  "--runtimes", "--agents-position", "prepend", "--python-executable", sys.executable)
        self.assertIn("Ada", self.identity.read_text(encoding="utf-8"))
        expected = setup.identity_text(m, "reviewer", "Ada", "Review public APIs.", ["Compatibility"])
        self.assertEqual(self.identity.read_text(encoding="utf-8"), expected)
        expected = setup.dispositions_text(m, "deliberate", {"communication": "concise", "initiative": "bounded", "verification": "thorough", "disagreement": "gentle"})
        self.assertEqual(self.dispositions.read_text(encoding="utf-8"), expected)
        self.assertEqual(result["agents_position"], "prepend")

    def test_eof_cancels_before_writing(self):
        args = m.parser().parse_args(["install", "--root", str(self.root), "--interactive"])
        with mock.patch("sys.stdin", Terminal()), mock.patch("builtins.input", side_effect=EOFError), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(m.MettleError):
            setup.run(m, args)
        self.assertEqual(self.files(), {})

    def test_installed_dry_run_does_not_create_bytecode_or_logs(self):
        self.run_setup()
        before = self.files()
        helper = self.root / m.PACKAGE / "tools/mettle.py"
        subprocess.run([sys.executable, "-X", "utf8", str(helper), "install", "--configure-only", "--non-interactive", "--dry-run"],
                       capture_output=True, encoding="utf-8", check=True)
        self.assertEqual(before, self.files())

    def test_empty_constructor_values_rejected(self):
        for option in ("--agent-name", "--role"):
            with self.assertRaises(m.MettleError):
                self.run_setup(option, "")
        self.assertEqual(self.files(), {})

    def test_repeat_explicit_preset_flags_is_a_noop_without_reset_permission(self):
        flags = ("--identity-preset", "reviewer", "--agent-name", "Aster", "--disposition-preset", "deliberate")
        self.run_setup(*flags)
        before = self.files()
        result = self.run_setup(*flags)
        self.assertEqual(self.files(), before)
        self.assertEqual(result["backups"], [])
        self.assertEqual(result["profiles"]["identity.md"], "preserve")

    def test_low_level_api_keeps_legacy_no_augmentation_default(self):
        self.agents.write_bytes(b"# Existing API caller\n")
        m.install(self.root, [])
        self.assertEqual(self.agents.read_bytes(), b"# Existing API caller\n")

    def test_neutral_marker_concurrent_creation_aborts_before_deployment(self):
        original = m.write_atomic
        def create_operator_file(path, text, **kwargs):
            if path == self.agents:
                self.agents.write_bytes(b"# Operator rules\r\n")
            original(path, text, **kwargs)
        with mock.patch("mettle.write_atomic", side_effect=create_operator_file), self.assertRaises(FileExistsError):
            m.install(self.root, [])
        self.assertEqual(self.agents.read_bytes(), b"# Operator rules\r\n")
        self.assertFalse((self.root / m.PACKAGE / "tools/mettle.py").exists())

    def test_changed_agents_during_deployment_is_not_overwritten(self):
        self.agents.write_bytes(b"# Before\n")
        original = m.write_atomic
        def edit_during_deployment(path, text, **kwargs):
            result = original(path, text, **kwargs)
            if path == self.root / m.PACKAGE / "tools/mettle.py":
                self.agents.write_bytes(b"# Concurrent operator change\n")
            return result
        with mock.patch("mettle.write_atomic", side_effect=edit_during_deployment), self.assertRaises(m.MettleError):
            self.run_setup()
        self.assertEqual(self.agents.read_bytes(), b"# Concurrent operator change\n")


if __name__ == "__main__":
    unittest.main()
