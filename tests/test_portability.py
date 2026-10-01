"""Offline process/filesystem contracts. These do not certify live agent loading."""
from __future__ import annotations

import contextlib
import errno
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import venv

import mettle as m


def snapshot(output: bytes) -> dict:
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
    return json.loads(context.rsplit("\n\n", 1)[1])


def run_cmd(command: str, **kwargs) -> subprocess.CompletedProcess:
    comspec = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
    # Match Codex 0.153.0: /C followed by raw outer quotes, not CRT escaping.
    return subprocess.run(f'"{comspec}" /C "{command}"', executable=comspec,
                          capture_output=True, timeout=30, **kwargs)


class PortabilityTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-port-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "projet café 日本 & (x)^$'`;[]"
        self.root.mkdir()
        (self.root / "AGENTS.md").write_bytes(b"# Existing root\r\n")
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"

    def draft(self, kind="episode", identifier="E-test", **fields):
        meta, body = m.decode(m.template(kind))
        meta.update(id=identifier, title="Evidence café 日本", **fields)
        return m.encode(meta, body.replace("TODO", "Observed café 日本; limited evidence."))

    def publish(self, **fields):
        with self.store.lock():
            return self.store.publish(self.draft(**fields), fields.get("expected"))

    def cli(self, *args, **kwargs):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args],
                              capture_output=True, timeout=30, **kwargs)

    def location(self):
        text = (self.store.home / "LOCATION.md").read_text(encoding="utf-8")
        return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0]), text

    def test_install_creates_root_agents_and_preserves_instructions_on_repeat(self):
        target = self.root / "new target"
        nested = target / "component"
        nested.mkdir(parents=True)
        scoped = nested / "AGENTS.md"
        scoped.write_bytes(b"# Component rules\r\n")
        claude = target / "CLAUDE.md"
        claude.write_bytes(b"# Existing Claude rules\r\n")
        source = Path(m.__file__).resolve()
        installed = subprocess.run([sys.executable, "-X", "utf8", str(source), "install", "--root", str(target),
                                    "--non-interactive", "--runtimes", "codex", "claude", "opencode"],
                                   cwd=nested, capture_output=True, timeout=30)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        result = json.loads(installed.stdout)
        self.assertTrue(result["agents_created"])
        self.assertEqual(result["root"], str(target))
        agents = target / "AGENTS.md"
        self.assertTrue(agents.read_bytes().startswith(b"# Project instructions\n"))
        self.assertEqual(agents.read_bytes().count(b"<!-- agentic-mettle:begin -->"), 1)
        self.assertIn(b".agent-personality/PERSONALITY.md", agents.read_bytes())
        self.assertEqual(m.Store(target).snapshot(), ({}, {}))
        handler = json.loads((target / ".claude/settings.local.json").read_bytes())["hooks"]["SessionStart"][0]["hooks"][0]
        boot = subprocess.run([handler["command"], *handler["args"]], input=b'{"source":"startup"}',
                              cwd=nested, capture_output=True, timeout=30)
        self.assertEqual((boot.returncode, boot.stderr), (0, b""))
        self.assertEqual(snapshot(boot.stdout)["root"], str(target))
        customized = b"\xef\xbb\xbf" + "# Project rules\r\nKeep café 日本 intact.\r\n".encode()
        agents.write_bytes(customized)
        for configure_only in (False, True):
            self.assertFalse(m.install(target, ["codex", "claude", "opencode"], configure_only)["agents_created"])
            self.assertEqual(agents.read_bytes(), customized)
            self.assertEqual(scoped.read_bytes(), b"# Component rules\r\n")
            self.assertEqual(claude.read_bytes(), b"# Existing Claude rules\r\n")
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"# Existing root\r\n")
        self.assertFalse((nested / m.PACKAGE).exists())

    def test_missing_agents_still_requires_an_explicit_existing_target(self):
        target = self.base / "unmarked target"
        target.mkdir()
        implicit = subprocess.run([sys.executable, "-X", "utf8", str(Path(m.__file__).resolve()), "install"],
                                  cwd=target, capture_output=True, timeout=30)
        self.assertEqual(implicit.returncode, 1)
        self.assertIn(b"Supply --root", implicit.stderr)
        self.assertEqual(list(target.iterdir()), [])
        preview = subprocess.run([sys.executable, "-X", "utf8", str(Path(m.__file__).resolve()), "adapter", "--root", str(target), "--runtime", "claude"],
                                 capture_output=True, timeout=30)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn("hooks", json.loads(preview.stdout))
        self.assertEqual(list(target.iterdir()), [])
        missing = target / "typo"
        with self.assertRaisesRegex(m.MettleError, "existing target directory"):
            m.install(missing, [])
        self.assertFalse(missing.exists())

    def test_failed_preflight_does_not_create_root_agents(self):
        for reason in ("interpreter", "config", "jsonc", "directory", "configure-only"):
            with self.subTest(reason=reason):
                target = self.base / reason
                target.mkdir()
                if reason == "config":
                    (target / ".claude").mkdir()
                    (target / ".claude/settings.local.json").write_bytes(b"invalid JSON")
                elif reason == "jsonc":
                    (target / "opencode.jsonc").write_bytes(b"{ /* keep comments */ }")
                elif reason == "directory":
                    (target / "AGENTS.md").mkdir()
                before = {p.relative_to(target): p.read_bytes() if p.is_file() else None for p in target.rglob("*")}
                with self.assertRaises((m.MettleError, ValueError)):
                    m.install(target, ["claude", "opencode"], configure_only=reason == "configure-only",
                              python=str(target / "missing.exe") if reason == "interpreter" else None)
                after = {p.relative_to(target): p.read_bytes() if p.is_file() else None for p in target.rglob("*")}
                self.assertEqual(after, before)

    def test_root_agents_creation_cannot_overwrite_a_concurrent_file(self):
        target = self.base / "unmarked target"
        target.mkdir()
        agents = target / "AGENTS.md"
        original = m.write_atomic
        def operator_creates_file(path, text, **kwargs):
            if path == agents:
                agents.write_bytes(b"# Operator instructions\r\n")
            original(path, text, **kwargs)
        with mock.patch("mettle.write_atomic", side_effect=operator_creates_file), self.assertRaises(FileExistsError):
            m.install(target, [])
        self.assertEqual(agents.read_bytes(), b"# Operator instructions\r\n")
        self.assertFalse((target / m.PACKAGE / "tools/mettle.py").exists())
        self.assertFalse((target / m.PACKAGE / "state/.write-lock").exists())

    def test_invalid_history_does_not_create_missing_root_agents(self):
        (self.root / "AGENTS.md").unlink()
        record = self.store.path("memory/episodes/invalid.md")
        record.write_bytes(b"Invalid accepted record\n")
        helper_before = self.helper.read_bytes()
        with self.assertRaisesRegex(m.MettleError, "Expected JSON metadata"):
            m.install(self.root, [])
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(record.read_bytes(), b"Invalid accepted record\n")
        self.assertEqual(self.helper.read_bytes(), helper_before)

    def test_utf8_bom_crlf_and_legacy_history_preserved(self):
        draft = self.root / "draft.md"
        draft.write_bytes(b"\xef\xbb\xbf" + self.draft().replace("\n", "\r\n").encode("utf-8"))
        result = self.cli("publish", str(draft))
        self.assertEqual(result.returncode, 0, result.stderr)
        relative = result.stdout.decode("utf-8").strip()
        self.assertNotIn("\\", relative)
        accepted = self.root / relative
        canonical = accepted.read_bytes()
        self.assertNotIn(b"\r", canonical)
        self.assertFalse(canonical.startswith(b"\xef\xbb\xbf"))
        self.assertIn("日本".encode(), canonical)
        # An existing BOM/CRLF history is readable and never silently rewritten.
        legacy = b"\xef\xbb\xbf" + canonical.replace(b"\n", b"\r\n")
        accepted.write_bytes(legacy)
        m.install(self.root, ["claude"])
        self.assertEqual(self.cli("check").returncode, 0)
        self.assertEqual(accepted.read_bytes(), legacy)

    def test_template_and_show_output_never_overwrite(self):
        output = self.root / "épisode.md"
        result = self.cli("template", "episode", "--output", str(output))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        first = output.read_bytes()
        m.decode(first.decode("utf-8"))
        self.assertNotIn(b"\r", first)
        self.assertEqual(self.cli("template", "episode", "--output", str(output)).returncode, 1)
        self.assertEqual(output.read_bytes(), first)
        self.publish()
        shown = self.root / "accepted-draft.md"
        self.assertEqual(self.cli("show", "E-test", "--output", str(shown)).returncode, 0)
        self.assertEqual(shown.read_bytes(), self.cli("show", "E-test").stdout)
        self.assertEqual(self.cli("show", "E-test", "--output", str(shown)).returncode, 1)

    def test_pipes_ignore_locale_and_accept_bom(self):
        profile = "# Identité\r\nMāori, 日本語, café.\r\n"
        self.store.path("personality/identity.md").write_bytes(b"\xef\xbb\xbf" + profile.encode())
        event = {"source": "compact", "session_id": "séance 日本", "model": "modèle"}
        env = dict(os.environ, PYTHONUTF8="0", PYTHONIOENCODING="cp1252")
        # Deliberately omit -X utf8: main also configures its streams explicitly.
        result = subprocess.run([sys.executable, str(self.helper), "bootstrap", "--runtime", "claude", "--hook"],
                                input=b"\xef\xbb\xbf" + json.dumps(event, ensure_ascii=False).encode() + b"\r\n",
                                env=env, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = snapshot(result.stdout)
        self.assertEqual(data["model"], event["model"])
        self.assertEqual(data["profiles"]["identity.md"]["content"], profile.replace("\r\n", "\n"))
        self.assertNotIn(b"\r", result.stdout)
        plain = self.cli("bootstrap", env=env)
        self.assertIn("Māori, 日本語, café.".encode(), plain.stdout)
        invalid = self.cli("bootstrap", "--hook", input=b"\xff")
        self.assertFalse(json.loads(invalid.stdout)["continue"])
        self.assertEqual(invalid.stderr, b"")

    def test_substituted_streams(self):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("sys.stdin", io.StringIO('\ufeff{"source":"resume","model":"日本"}')), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = m.main(["bootstrap", "--root", str(self.root), "--hook"])
        self.assertEqual(code, 0)
        self.assertEqual(snapshot(out.getvalue().encode())["model"], "日本")
        self.assertFalse(out.closed)
        self.assertEqual(err.getvalue(), "")

    def test_invalid_utf8_is_not_guessed(self):
        path = self.root / "invalid.md"
        path.write_bytes(b"---\n\xff\n---\n")
        result = self.cli("publish", str(path))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"utf-8", result.stderr)
        self.assertEqual(self.store.snapshot(), ({}, {}))

    def test_exact_config_backups_and_instruction_preservation(self):
        component = self.root / "component"
        component.mkdir()
        (component / "AGENTS.md").write_bytes(b"# Scoped\r\n")
        (self.root / "CLAUDE.md").write_bytes(b"# Existing Claude rules\r\n")
        instructions = {p: p.read_bytes() for p in [self.root / "AGENTS.md", self.root / "CLAUDE.md", component / "AGENTS.md"]}
        target = self.root / ".claude/settings.local.json"
        target.parent.mkdir()
        other = {"type": "command", "command": "echo unrelated"}
        original = b"\xef\xbb\xbf" + json.dumps({"permissions": {"allow": ["Read"]}, "label": "日本", "hooks": {"SessionStart": [{"matcher": "startup", "hooks": [other]}]}}, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode()
        target.write_bytes(original)
        m.install(self.root, ["claude", "opencode"])
        result = json.loads(target.read_bytes())
        self.assertEqual(result["label"], "日本")
        self.assertEqual(result["hooks"]["SessionStart"][0]["hooks"], [other])
        backups = list(target.parent.glob("*.mettle-backup-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        config_bytes = target.read_bytes()
        m.install(self.root, ["claude", "opencode"], configure_only=True)
        self.assertEqual(target.read_bytes(), config_bytes)
        self.assertEqual(len(list(target.parent.glob("*.mettle-backup-*"))), 1)
        for path, content in instructions.items():
            self.assertEqual(path.read_bytes(), content)
        for path in self.store.home.rglob("*"):
            if path.is_file() and path.suffix != ".pyc":
                self.assertNotIn(b"\r", path.read_bytes(), str(path))
                self.assertFalse(path.read_bytes().startswith(b"\xef\xbb\xbf"), str(path))

    def test_upgrade_old_hooks_preserves_unrelated_commands(self):
        for runtime in ("claude", "codex"):
            old_helper = r"C:\old checkout\日本\.agent-personality\tools\mettle.py"
            old = {"type": "command", "command": shlex.join(["python3", old_helper, "bootstrap", "--runtime", runtime, "--hook"])}
            direct = {"type": "command", "command": r"C:\Old Python\python.exe", "args": ["-X", "utf8", old_helper, "bootstrap", "--runtime", runtime, "--hook"]}
            old_direct = {**direct, "args": direct["args"][2:]}
            windows = {"type": "command", "commandWindows": m.cmd_command([direct["command"], *direct["args"]])}
            unrelated = [{"type": "command", "command": "echo " + shlex.quote(old["command"])},
                         {**direct, "command": "echo"},
                         {**direct, "args": [*direct["args"], "unrelated"]},
                         {"type": "prompt", "prompt": "Keep this"}]
            empty_group = {"matcher": "operator-placeholder", "hooks": []}
            existing = {"settings": {"keep": True}, "hooks": {"Stop": [{"hooks": unrelated}], "SessionStart": [{"matcher": "startup", "custom_existing_field": 1, "hooks": [old, direct, old_direct, windows, old, *unrelated]}, empty_group]}}
            fragment = m.adapter(self.root, runtime)
            merged = m.merge_config(existing, fragment, runtime)
            self.assertEqual(merged["settings"], existing["settings"])
            self.assertEqual(merged["hooks"]["Stop"], existing["hooks"]["Stop"])
            self.assertEqual(merged["hooks"]["SessionStart"][0]["hooks"], unrelated)
            self.assertEqual(merged["hooks"]["SessionStart"][0]["custom_existing_field"], 1)
            self.assertEqual(merged["hooks"]["SessionStart"][1], empty_group)
            self.assertEqual(len(merged["hooks"]["SessionStart"]), 3)
            self.assertEqual(m.merge_config(merged, fragment, runtime), merged)
            target = self.root / (".claude/settings.local.json" if runtime == "claude" else ".codex/hooks.json")
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(existing), encoding="utf-8")
            m.install(self.root, [runtime])
            m.install(self.root, [runtime])
            self.assertEqual(json.loads(target.read_bytes()), merged)
            self.assertEqual(len(list(target.parent.glob("*.mettle-backup-*"))), 1)

    def test_mixed_platform_ownership_fails_preflight(self):
        fragment = m.adapter(self.root, "codex")
        handler = {"type": "command", "command": "echo operator hook",
                   "commandWindows": m.cmd_command(m.helper_argv(self.root, sys.executable, "bootstrap", "--runtime", "codex", "--hook"))}
        with self.assertRaisesRegex(m.MettleError, "different owners"):
            m.merge_config({"hooks": {"SessionStart": [{"hooks": [handler]}]}}, fragment, "codex")

    def test_reconfigure_moved_install_from_nested_component(self):
        m.install(self.root, ["codex", "claude", "opencode"])
        relative = self.publish()
        accepted = (self.root / relative).read_bytes()
        protocol = (self.store.home / "PERSONALITY.md").read_bytes()
        old_root = self.root
        moved = self.base / "moved café & (target)"
        old_root.rename(moved)
        nested = moved / "component"
        nested.mkdir()
        (nested / "AGENTS.md").write_text("Wrong root\n", encoding="utf-8")
        helper = moved / m.PACKAGE / "tools/mettle.py"
        result = subprocess.run([sys.executable, "-X", "utf8", str(helper), "install", "--configure-only", "--python-executable", sys.executable],
                                cwd=nested, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        for runtime, name in [("claude", ".claude/settings.local.json"), ("codex", ".codex/hooks.json")]:
            config = json.loads((moved / name).read_bytes())
            groups = config["hooks"]["SessionStart"]
            self.assertEqual(len(groups), 1)
            self.assertEqual(groups, m.adapter(moved, runtime)["hooks"]["SessionStart"])
            self.assertEqual(len(list((moved / name).parent.glob("*.mettle-backup-*"))), 1)
        handler = json.loads((moved / ".claude/settings.local.json").read_bytes())["hooks"]["SessionStart"][0]["hooks"][0]
        boot = subprocess.run([handler["command"], *handler["args"]], input=b'{"source":"resume"}', cwd=nested, capture_output=True, timeout=30)
        self.assertEqual(snapshot(boot.stdout)["root"], str(moved))
        self.assertEqual((moved / relative).read_bytes(), accepted)
        self.assertEqual((moved / m.PACKAGE / "PERSONALITY.md").read_bytes(), protocol)
        location = (moved / m.PACKAGE / "LOCATION.md").read_text(encoding="utf-8")
        self.assertEqual(json.loads(location.split("```json\n")[1].split("\n```")[0])["root"], str(moved))

    def test_invalid_interpreter_stops_before_any_mutation(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        for executable in [str(self.base / "missing.exe"), "C:relative.exe"]:
            with self.assertRaises(m.MettleError):
                m.install(self.root, ["claude"], python=executable)
        old = subprocess.CompletedProcess([], 0, json.dumps({"executable": sys.executable, "version": [3, 10, 6]}), "")
        with mock.patch("mettle.subprocess.run", return_value=old), self.assertRaisesRegex(m.MettleError, "3.11"):
            m.install(self.root, ["claude"])
        after = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_relative_path_and_reserved_names(self):
        for path in ["../escape", "C:relative", "C:/absolute", "memory/C:relative", "\\rooted", "//host/share", "memory\\escape", "memory/../escape", "memory/con", "memory/NUL.md", "aux", "LPT1", "com¹.txt", "memory/trailing.", "memory/trailing ", "memory/a:b", "memory/a?b"]:
            with self.subTest(path=path), self.assertRaises(m.MettleError):
                m.portable_parts(path)
        self.publish()
        for domain in ["engineering/con", "aux", "lpt1"]:
            with self.store.lock(), self.assertRaisesRegex(m.MettleError, "Reserved"):
                self.store.publish(self.draft("lesson", "L-test", domain=domain, origin=["E-test"], scope=["test"]), 0)
        with self.assertRaises(m.MettleError):
            m.resolve_root("C:relative")

    def test_case_collisions_across_months_and_lesson_domains(self):
        self.publish(identifier="E-Mixed")
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, "Case-insensitive"):
            self.store.publish(self.draft(identifier="E-mixed", created_at="2000-01-01T00:00:00+00:00"), None)
        with self.store.lock():
            self.store.publish(self.draft("lesson", "L-Mixed", origin=["E-Mixed"], scope=["test"]), 0)
            with self.assertRaisesRegex(m.MettleError, "Case-insensitive"):
                self.store.publish(self.draft("lesson", "L-mixed", domain="other", origin=["E-Mixed"], scope=["test"]), 0)
        # Simulate a nonportable archive copied from a case-sensitive filesystem.
        other = self.store.path("memory/episodes/2000/01/E-mixed.md")
        m.write_atomic(other, self.draft(identifier="E-mixed", created_at="2000-01-01T00:00:00+00:00"))
        before = other.read_bytes()
        if os.name == "nt":
            with self.assertRaisesRegex(m.MettleError, "Case-insensitive"):
                self.store.snapshot()
        else:
            self.assertEqual(len(self.store.snapshot()[0]), 2)  # Preserve old POSIX histories.
        self.assertEqual(other.read_bytes(), before)

    def test_repository_relative_indexes_use_forward_slashes(self):
        self.publish()
        with self.store.lock():
            self.store.publish(self.draft("lesson", "L-test", origin=["E-test"], scope=["test"], domain="engineering/nested"), 0)
        candidate = m.search(self.store, ["café"], 5, None)[0]
        self.assertEqual(candidate["path"], ".agent-personality/state/memory/lessons/engineering/nested/L-test/current.md")
        index = self.store.path("memory/lessons/engineering/nested/INDEX.md").read_text(encoding="utf-8")
        row = json.loads(next(line for line in index.splitlines() if line.startswith("{")))
        self.assertEqual(row["path"], candidate["path"])

    def test_immutable_atomic_publication_and_no_unsafe_fallback(self):
        path = self.root / "immutable.md"
        data = "Full café 日本\n"
        real_link = os.link
        def inspect_link(source, destination):
            self.assertFalse(path.exists())
            self.assertEqual(Path(source).read_bytes(), data.encode())
            real_link(source, destination)
        with mock.patch("mettle.os.link", side_effect=inspect_link):
            m.write_atomic(path, data, exclusive=True)
        with self.assertRaises(FileExistsError):
            m.write_atomic(path, "must not overwrite", exclusive=True)
        self.assertEqual(path.read_bytes(), data.encode())
        with mock.patch("mettle.os.link", side_effect=OSError(errno.ENOTSUP, "Hard links unavailable")), self.assertRaises(OSError):
            m.write_atomic(self.root / "unsupported.md", data, exclusive=True)
        self.assertFalse((self.root / "unsupported.md").exists())
        self.assertEqual(list(self.root.glob(".mettle-*")), [])

    def test_interrupted_view_update_repairs_without_rewriting_history(self):
        self.publish()
        replace = os.replace
        def interrupt(source, destination):
            if Path(destination).name == "current.md":
                raise PermissionError("Simulated interrupted view update")
            replace(source, destination)
        with self.store.lock(), mock.patch("mettle.os.replace", side_effect=interrupt), self.assertRaises(PermissionError):
            self.store.publish(self.draft("lesson", "L-test", origin=["E-test"], scope=["test"]), 0)
        revision = self.store.path("memory/lessons/engineering/L-test/revisions/0001.md")
        accepted = revision.read_bytes()
        with self.assertRaisesRegex(m.MettleError, "Stale current"):
            self.store.snapshot()
        result = self.cli("reindex", "--repair")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(revision.read_bytes(), accepted)
        self.assertEqual(revision.parent.parent.joinpath("current.md").read_bytes(), accepted)
        self.assertEqual(self.cli("check").returncode, 0)

    def test_lock_contention_is_visible_to_another_process(self):
        with self.store.lock():
            result = self.cli("check")
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"Store is locked", result.stderr)
            hook = self.cli("bootstrap", "--hook", input=b"{}")
            self.assertEqual(hook.returncode, 0)  # Existing structured-hook failure contract.
            self.assertFalse(json.loads(hook.stdout)["continue"])
        self.assertEqual(self.cli("check").returncode, 0)

    def test_archive_traversal_errors_are_visible(self):
        def denied(*args, **kwargs):
            kwargs["onerror"](PermissionError("Unreadable archive subtree"))
        with mock.patch("mettle.os.walk", side_effect=denied), self.assertRaises(PermissionError):
            self.store.snapshot()

    @unittest.skipUnless(os.name == "nt", "Native Windows launch contract")
    def test_windows_selected_interpreter_and_generated_hook_launches(self):
        # A real interpreter away from PATH, with shell-significant path characters.
        environment = self.base / "Python café & (x)^$'`;[]"
        # venv's creation UI refuses PATH separators, although a relocated venv's
        # executable works there. Exercise the valid Windows filename too.
        staging = self.base / "venv"
        venv.EnvBuilder(with_pip=False, symlinks=False).create(staging)
        staging.rename(environment)
        executable = environment / "Scripts/python.exe"
        m.install(self.root, ["claude", "codex"])
        m.install(self.root, ["claude", "codex"], configure_only=True, python=str(executable))
        m.install(self.root, ["claude", "codex"], configure_only=True, python=str(executable))
        nested = self.root / "component"
        nested.mkdir()
        (nested / "AGENTS.md").write_text("Wrong root", encoding="utf-8")
        env = dict(os.environ, PATH=os.environ.get("SystemRoot", r"C:\Windows") + r"\System32", PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
        node = shutil.which("node")
        for runtime, name in [("claude", ".claude/settings.local.json"), ("codex", ".codex/hooks.json")]:
            handler = json.loads((self.root / name).read_bytes())["hooks"]["SessionStart"][0]["hooks"][0]
            self.assertEqual(len(json.loads((self.root / name).read_bytes())["hooks"]["SessionStart"]), 1)
            for event in ("startup", "resume", "compact"):
                payload = json.dumps({"source": event, "model": "日本"}, ensure_ascii=False).encode()
                if runtime == "codex":
                    result = run_cmd(handler["commandWindows"], input=payload, cwd=nested, env=env)
                else:
                    self.assertEqual(handler["command"], str(executable))
                    result = subprocess.run([handler["command"], *handler["args"]], input=payload, cwd=nested, env=env, capture_output=True, timeout=30)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                data = snapshot(result.stdout)
                self.assertEqual((data["root"], data["source"], data["model"]), (str(self.root), event, "日本"))
            if runtime == "claude" and node:
                # Exercise the documented exec form via Node's direct process API.
                script = "const h=JSON.parse(process.argv[1]);const p=require('child_process').spawnSync(h.command,h.args,{input:require('fs').readFileSync(0)});if(p.error)throw p.error;process.stdout.write(p.stdout);process.stderr.write(p.stderr);process.exit(p.status ?? 1)"
                result = subprocess.run([node, "-e", script, json.dumps(handler)], input=b'{"source":"startup"}', cwd=nested, env=env, capture_output=True, timeout=30)
                self.assertEqual((result.returncode, result.stderr), (0, b""))
                self.assertEqual(snapshot(result.stdout)["root"], str(self.root))
        # CMD must preserve the Python exit status, not turn failures into success.
        command = m.cmd_command(m.helper_argv(self.root, str(executable), "show", "E-missing"))
        failure = run_cmd(command, env=env)
        self.assertEqual(failure.returncode, 1)
        self.assertEqual(failure.stdout, b"")
        self.assertIn(b"Unknown record", failure.stderr)

    @unittest.skipUnless(os.name == "nt", "Windows CMD expansion")
    def test_cmd_unsafe_paths_fail_before_config_or_state_changes(self):
        with self.assertRaisesRegex(m.MettleError, "8000"):
            m.cmd_command(["x" * 8001])
        for suffix in ("percent%PATH%", "bang!VALUE!"):
            root = self.base / suffix
            root.mkdir()
            with self.assertRaisesRegex(m.MettleError, "cmd.exe"):
                m.install(root, ["claude", "codex"])
            self.assertEqual(list(root.iterdir()), [])
            # These names are safe in Claude's direct exec form.
            m.install(root, ["claude"])
            handler = json.loads((root / ".claude/settings.local.json").read_bytes())["hooks"]["SessionStart"][0]["hooks"][0]
            result = subprocess.run([handler["command"], *handler["args"]], input=b"{}", capture_output=True, timeout=30)
            self.assertEqual(snapshot(result.stdout)["root"], str(root))

    @unittest.skipUnless(os.name == "nt", "Windows PowerShell execution")
    def test_opencode_location_executes_in_powershell_51_and_7(self):
        shells = [m.windows_opencode_shell({})[0]]
        if shutil.which("pwsh"):
            shells.append(shutil.which("pwsh"))
        for shell in shells:
            config = self.root / "opencode.json"
            config.write_text(json.dumps({"shell": shell, "instructions": ["TEAM.md"], "model": "keep"}), encoding="utf-8")
            m.install(self.root, ["opencode"])
            result = json.loads(config.read_bytes())
            self.assertEqual(result["shell"], shell)
            self.assertEqual(result["model"], "keep")
            self.assertEqual(result["instructions"][0], "TEAM.md")
            location, text = self.location()
            self.assertEqual(location["shell"], "powershell")
            command = text.split("```powershell\n")[1].split("\n```")[0]
            process = subprocess.run([shell, "-NoProfile", "-Command", command], capture_output=True, timeout=30)
            self.assertEqual((process.returncode, process.stderr), (0, b""))
            self.assertIn("Runtime location".encode(), (self.store.home / "LOCATION.md").read_bytes())
            self.assertIn("Agentic Mettle".encode(), process.stdout)
            self.assertIn("—".encode(), process.stdout)
            # The same shell form must retain argparse's exit code and stderr.
            command = m.shell_command([*location["argv_prefix"], "invalid-command"], "powershell")
            failure = subprocess.run([shell, "-NoProfile", "-Command", command], capture_output=True, timeout=30)
            self.assertEqual(failure.returncode, 2)
            self.assertEqual(failure.stdout, b"")
            self.assertIn(b"invalid choice", failure.stderr)

    @unittest.skipUnless(os.name == "nt", "Windows OpenCode shell settings")
    def test_opencode_cmd_and_unsupported_shell(self):
        config = self.root / "opencode.json"
        config.write_text('{"shell":"cmd.exe"}', encoding="utf-8")
        m.install(self.root, ["opencode"])
        _, text = self.location()
        command = text.split("```bat\n")[1].split("\n```")[0]
        result = run_cmd(command)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertIn("—".encode(), result.stdout)
        m.install(self.root, ["claude"], configure_only=True)
        self.assertEqual(self.location()[0]["shell"], "cmd")
        config.write_text('{"shell":"unknown-shell"}', encoding="utf-8")
        before = (self.store.home / "LOCATION.md").read_bytes()
        with self.assertRaisesRegex(m.MettleError, "unsupported"):
            m.install(self.root, ["opencode"])
        self.assertEqual(config.read_bytes(), b'{"shell":"unknown-shell"}')
        self.assertEqual((self.store.home / "LOCATION.md").read_bytes(), before)
        config.write_text('{"shell":null}', encoding="utf-8")
        with self.assertRaisesRegex(m.MettleError, "nonempty string"):
            m.install(self.root, ["opencode"])
        self.assertEqual(config.read_bytes(), b'{"shell":null}')
        self.assertEqual((self.store.home / "LOCATION.md").read_bytes(), before)

    @unittest.skipUnless(os.name == "nt", "Windows filename aliases")
    def test_reserved_output_and_target_paths_fail_preflight(self):
        for name in ["NUL.md", "con .txt", "trailing.", "trailing "]:
            with self.subTest(name=name), self.assertRaises(m.MettleError):
                m.write_atomic(self.root / name, "must not write", exclusive=True)
        with self.assertRaisesRegex(m.MettleError, "Unsafe filename"):
            m.install(Path(str(self.root) + "."), [])

    @unittest.skipUnless(os.name == "nt", "Windows junctions")
    def test_junction_archive_root_and_ancestor_rejected(self):
        import _winapi
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "AGENTS.md").write_bytes(b"# Outside\n")
        sentinel = outside / "do-not-touch.md"
        sentinel.write_bytes(b"external data")
        link = self.store.path("memory/episodes/redirect")
        _winapi.CreateJunction(str(outside), str(link))
        try:
            with self.assertRaisesRegex(m.MettleError, "reparse"):
                self.store.snapshot()
            with self.assertRaisesRegex(m.MettleError, "reparse"):
                self.store.path("memory/episodes/redirect/new.md")
            with self.assertRaisesRegex(m.MettleError, "reparse"):
                m.install(link, [])
            child = outside / "child"
            child.mkdir()
            (child / "AGENTS.md").write_bytes(b"# Child\n")
            with self.assertRaisesRegex(m.MettleError, "reparse"):
                m.Store(link / "child")
            self.assertEqual(sentinel.read_bytes(), b"external data")
            self.assertFalse((outside / m.PACKAGE).exists())
        finally:
            link.rmdir()  # Remove just the junction, never recursively its target.

    @unittest.skipUnless(os.name != "nt", "POSIX shell execution")
    def test_posix_generated_command_executes(self):
        command = m.adapter(self.root, "codex")["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        result = subprocess.run(["/bin/sh", "-c", command], input=b'{"source":"startup"}', capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        self.assertEqual(snapshot(result.stdout)["root"], str(self.root))

    @unittest.skipUnless(os.name != "nt", "Legacy POSIX-only filename compatibility")
    def test_existing_posix_domain_remains_readable(self):
        self.publish()
        path = self.store.path("memory/lessons/con/L-legacy/revisions/0001.md")
        historical = self.draft("lesson", "L-legacy", domain="con", origin=["E-test"], scope=["test"]).encode()
        m.write_atomic(path, historical, exclusive=True)
        _, lessons = self.store.snapshot(verify_views=False)
        self.store.reindex(lessons)
        m.install(self.root, [])
        self.assertEqual(self.cli("check").returncode, 0)
        self.assertEqual(path.read_bytes(), historical)

    @unittest.skipUnless(os.name != "nt", "POSIX output aliases such as macOS /tmp")
    def test_draft_output_allows_posix_parent_alias_but_not_file_symlink(self):
        alias = self.base / "tmp-alias"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            if exc.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
                self.skipTest(f"Symlink creation unavailable: {exc}")
            raise
        self.assertEqual(self.cli("template", "episode", "--output", str(alias / "draft.md")).returncode, 0)
        self.assertTrue((self.root / "draft.md").is_file())
        link = self.root / "linked-draft.md"
        link.symlink_to(self.root / "must-not-write.md")
        self.assertEqual(self.cli("template", "episode", "--output", str(link)).returncode, 1)
        self.assertFalse((self.root / "must-not-write.md").exists())


if __name__ == "__main__":
    unittest.main()
