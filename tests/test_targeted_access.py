"""Real synthetic stores exercise cache freshness and the targeted read boundary."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_catalogue as c
import mettle_work as w
from examples.scalability_fixture import put, record, seed
from reference_retrieval_031 import retrieve_031


class TargetedAccessTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-targeted-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"
        self.records, self.lessons = seed(self.store, episodes=30, lessons=6, domains=2)
        self.cache = self.store.path(c.RELATIVE)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args,
                               "--root", str(self.root)], cwd=self.root.parent,
                              capture_output=True, encoding="utf-8", timeout=60)

    def get(self, identifier, revision=None):
        with self.store.lock(), c.open_catalogue(m, self.store) as catalogue:
            return catalogue.get(identifier, revision)

    def query(self, *terms, **kwargs):
        with self.store.lock():
            return w.search_page(m, self.store, list(terms), kwargs.pop("limit", 3),
                                 kwargs.pop("scope", None), **kwargs)

    def publish(self, kind, identifier, **fields):
        with self.store.lock():
            self.store.publish(record(kind, identifier, **fields),
                               fields.get("revision", 1) - 1 if kind == "lesson" else None)

    def revise(self, identifier="L-00000", **fields):
        _, lessons = self.store.snapshot()
        meta, body, _ = lessons[identifier][-1]
        reconciliation = f"C-{identifier}-{meta['revision']}"
        self.publish("reconciliation", reconciliation, inputs=[f"{identifier}@{meta['revision']}"],
                     evidence=[], operation="REVISE")
        changed = dict(meta, revision=meta["revision"] + 1,
                       reconciliations=[*meta["reconciliations"], reconciliation])
        changed.update(fields)
        with self.store.lock():
            self.store.publish(m.encode(changed, body), meta["revision"])
        return changed

    def hashes(self):
        return {p.relative_to(self.store.state).as_posix(): w.sha(p.read_bytes())
                for folder in ("memory", "personality", "work")
                for p in self.store.path(folder).rglob("*")
                if p.is_file() and p != self.cache}

    def assert_cli_ok(self, *args):
        result = self.cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_exact_all_kinds_latest_and_historical_in_fresh_process(self):
        self.publish("review", "V-review", lesson="L-00000", lesson_revision=1,
                     episodes=["E-00001"], assessment="counterexample")
        self.revise(counterevidence=["V-review"], status="contested")
        records, lessons = self.store.snapshot()
        cases = [(identifier, None, entry) for identifier, entry in records.items()
                 if identifier in {"E-00000", "V-review", "C-L-00000-1"}]
        cases.extend([("L-00000", None, lessons["L-00000"][-1]),
                      ("L-00000", 1, lessons["L-00000"][0])])
        for identifier, revision, entry in cases:
            with self.subTest(identifier=identifier, revision=revision):
                args = ("--revision", str(revision)) if revision else ()
                result = self.assert_cli_ok("show", identifier, *args)
                self.assertEqual(result.stdout, m.encode(*entry[:2]))
                self.assertEqual(result.stderr, "")
        for args in [("E-missing",), ("L-00000", "--revision", "9"),
                     ("L-00000", "--revision", "0"), ("E-00000", "--revision", "1"),
                     ("../../outside",)]:
            self.assertNotEqual(self.cli("show", *args).returncode, 0)

    def test_warm_reads_measure_real_canonical_io_not_snapshot_stubs(self):
        self.get("E-00000")  # Cold validation/rebuild.
        cache_before = self.cache.read_bytes(), self.cache.stat().st_mtime_ns
        for action, expected in [(lambda: self.get("E-00000"), {self.records["E-00000"][2]}),
                                 (lambda: self.query("amberwidget", kind="episodes"),
                                  {self.records[f"E-{i:05d}"][2] for i in range(3)}),
                                 (lambda: self.query("needle00000"),
                                  {self.lessons["L-00000"][0][2], self.records["E-00000"][2]})]:
            reads = []
            original = m.read
            def read(path):
                if "revisions" in path.parts or any(part in m.DIRECTORIES.values() for part in path.parts):
                    reads.append(path)
                return original(path)
            with mock.patch.object(m, "read", side_effect=read), \
                    mock.patch.object(self.store, "snapshot", wraps=self.store.snapshot) as snapshots, \
                    mock.patch.object(c, "inventory", wraps=c.inventory) as inventory, \
                    mock.patch.object(c, "connect", wraps=c.connect) as connections:
                action()
            self.assertEqual(set(reads), expected)
            self.assertEqual(len(reads), len(expected))
            self.assertEqual(snapshots.call_count, 0)
            self.assertEqual(inventory.call_count, 1)
            self.assertEqual(connections.call_count, 1)
        self.assertEqual((self.cache.read_bytes(), self.cache.stat().st_mtime_ns), cache_before)

    def test_show_cost_does_not_decode_added_unrelated_history(self):
        for count in (0, 100):
            if count:
                for i in range(count):
                    put(self.store, record("episode", f"E-extra-{i}"))
            self.get("E-00000")
            with mock.patch.object(m, "decode", wraps=m.decode) as decodes, \
                    mock.patch.object(self.store, "snapshot", wraps=self.store.snapshot) as snapshots:
                self.get("E-00000")
            self.assertEqual(decodes.call_count, 1)
            self.assertEqual(snapshots.call_count, 0)
            self.assertEqual(len(c.inventory(m, self.store)), 36 + count)

    def test_default_search_exact_parity_with_031(self):
        self.publish("episode", "E-correction", corrects=["E-00000"])
        self.publish("review", "V-pending", lesson="L-00000", lesson_revision=1,
                     episodes=["E-00001"], assessment="counterexample")
        self.publish("review", "V-incorporated", lesson="L-00000", lesson_revision=1,
                     episodes=["E-00001"], assessment="counterexample")
        self.revise(counterevidence=["V-incorporated"], status="contested")
        self.revise("L-00001", status="retired")
        self.revise("L-00002", status="superseded", superseded_by=["L-00003"])
        with self.store.lock():
            work_id = w.start(m, self.store, "Synthetic rejection", "fixture")["id"]
            w.reject_candidate(m, self.store, work_id, "L-00000@2", ["amberwidget"], "Different scope.")
        for kind in ("lessons", "episodes"):
            for terms in (["amberwidget"], ["needle00000"], ["source", "of", "truth"],
                          ["source"], ["source_of_truth"], ["日本"], ["absent"]):
                for scope, work in [(None, None), ("component/0", None), (None, work_id)]:
                    with self.subTest(kind=kind, terms=terms, scope=scope, work=work):
                        expected = retrieve_031(m, self.store, terms, 3, scope, kind, work)
                        self.assertEqual(self.query(*terms, kind=kind, scope=scope, work_id=work)["candidates"], expected)
        self.assertEqual(self.query("needle00000")["candidates"][0]["pending_counterevidence"], ["V-pending"])
        self.assertEqual(self.query("needle00000", kind="episodes")["candidates"][0]["corrected_by"], ["E-correction"])

    def test_history_earlier_wording_status_exact_paths_and_continuation(self):
        self.publish("review", "V-support", lesson="L-00000", lesson_revision=1,
                     episodes=["E-00001"], assessment="support")
        self.revise(status="active", title="obsoleteword synthetic wording", support=["V-support"])
        self.revise(status="retired", title="replacementword changed conclusion")
        self.assertEqual(self.query("obsoleteword")["candidates"], [])
        hit = self.query("obsoleteword", history=True)["candidates"][0]
        self.assertEqual((hit["revision"], hit["status"], hit["latest_revision"], hit["latest_status"]),
                         (2, "active", 3, "retired"))
        self.assertFalse(hit["is_latest"])
        self.assertEqual(hit["discovery"], "historical-evidence")
        self.assertTrue(hit["path"].endswith("/revisions/0002.md"))
        self.assertEqual(m.read(self.root / hit["path"]), self.assert_cli_ok("show", hit["id"], "--revision", "2").stdout)
        seen, offset = [], 0
        while True:
            page = self.query("synthetic", history=True, limit=2, offset=offset)
            seen.extend((item["id"], item["revision"]) for item in page["candidates"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        self.assertEqual(len(seen), 8)
        self.assertEqual(len(set(seen)), 8)
        self.revise(status="contested")
        hit = self.query("obsoleteword", history=True)["candidates"][0]
        self.assertEqual((hit["status"], hit["latest_status"], hit["is_latest"]), ("active", "contested", False))
        self.assertEqual(self.query("absent", history=True)["candidates"], [])
        self.assertEqual(self.query("synthetic", history=True, offset=99)["remaining"], 0)
        for args in [("--history", "--kind", "episodes"), ("--offset", "1"),
                     ("--history", "--offset", "-1"), ("--limit", "0")]:
            self.assertNotEqual(self.cli("search", *args, "synthetic").returncode, 0)

    def test_history_rejections_and_counterevidence_are_revision_specific(self):
        self.publish("review", "V-counter", lesson="L-00000", lesson_revision=1,
                     episodes=["E-00001"], assessment="counterexample")
        self.revise(status="contested", counterevidence=["V-counter"])
        hits = self.query("needle00000", history=True)["candidates"]
        by_revision = {item["revision"]: item for item in hits}
        self.assertEqual(by_revision[1]["pending_counterevidence"], ["V-counter"])
        self.assertEqual(by_revision[2]["pending_counterevidence"], [])
        with self.store.lock():
            identifier = w.start(m, self.store, "Historical rejection", "fixture")["id"]
            w.reject_candidate(m, self.store, identifier, "L-00000@1", ["needle00000"], "Different conditions.")
        hits = self.query("needle00000", history=True, work_id=identifier, scope="component/0")["candidates"]
        self.assertEqual([item["revision"] for item in hits], [2])

    def test_installed_helper_uses_fixed_root_and_rejects_another_root(self):
        self.get("E-00000")
        args = [sys.executable, "-X", "utf8", str(self.helper), "show", "E-00000"]
        with tempfile.TemporaryDirectory(prefix="mettle-other-root-") as temporary:
            other = Path(temporary).resolve()
            m.install(other, [])
            result = subprocess.run(args, cwd=other, capture_output=True, encoding="utf-8", timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, m.encode(*self.records["E-00000"][:2]))
            result = subprocess.run([*args, "--root", str(other)], cwd=other,
                                    capture_output=True, encoding="utf-8", timeout=30)
            self.assertNotEqual(result.returncode, 0)

    @unittest.skipUnless(sys.platform == "win32", "Native Windows case behavior")
    def test_windows_catalogue_preserves_exact_id_case_and_rejects_collisions(self):
        self.publish("episode", "E-MixedCase")
        self.assertEqual(self.get("E-MixedCase")[0]["id"], "E-MixedCase")
        self.assertNotEqual(self.cli("show", "E-mixedcase").returncode, 0)
        path = self.store.path("memory/episodes/other/E-mixedcase.md")
        path.parent.mkdir()
        path.write_text(record("episode", "E-mixedcase"), encoding="utf-8")
        self.assertNotEqual(self.cli("show", "E-MixedCase").returncode, 0)
        self.assertNotEqual(self.cli("check").returncode, 0)

    def test_history_supersession_and_proposed_contested_are_not_relabelled(self):
        self.revise(status="superseded", superseded_by=["L-00001"])
        self.revise("L-00001", status="contested")
        page = self.query("amberwidget", history=True, limit=50)
        hits = {(x["id"], x["revision"]): x for x in page["candidates"]}
        self.assertEqual(hits["L-00000", 1]["latest_superseded_by"], ["L-00001"])
        self.assertEqual(hits["L-00000", 2]["superseded_by"], ["L-00001"])
        self.assertEqual(hits["L-00001", 2]["status"], "contested")
        self.assertEqual(hits["L-00002", 1]["status"], "proposed")
        self.assertNotIn("L-00000", [x["id"] for x in self.query("amberwidget", limit=50)["candidates"]])

    def test_publication_immediately_invalidates_corrections_reviews_and_heads(self):
        self.get("E-00000")
        self.publish("episode", "E-new", title="uniquecorrection", corrects=["E-00000"])
        self.assertFalse(self.cache.exists())
        self.assertEqual(self.query("uniquecorrection", kind="episodes")["candidates"][0]["id"], "E-new")
        self.assertEqual(self.query("needle00000", kind="episodes")["candidates"][0]["corrected_by"], ["E-new"])
        self.publish("review", "V-new", lesson="L-00000", lesson_revision=1,
                     episodes=["E-new"], assessment="counterexample")
        self.assertEqual(self.query("needle00000")["candidates"][0]["pending_counterevidence"], ["V-new"])
        self.revise(status="contested", counterevidence=["V-new"])
        hit = self.query("needle00000")["candidates"][0]
        self.assertEqual((hit["revision"], hit["status"], hit["pending_counterevidence"]), (2, "contested", []))
        self.revise(status="retired")
        self.assertEqual(self.query("needle00000")["candidates"], [])
        self.assertEqual(self.get("L-00000")[0]["revision"], 3)

    def test_interruption_after_acceptance_does_not_serve_cached_head(self):
        self.get("L-00000")
        self.publish("reconciliation", "C-interrupt", inputs=["L-00000@1"], evidence=[], operation="REVISE")
        self.get("L-00000")
        meta, body, _ = self.lessons["L-00000"][0]
        revised = dict(meta, revision=2, status="retired", reconciliations=["C-interrupt"])
        with self.store.lock(), mock.patch.object(self.store, "refresh_lesson", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.store.publish(m.encode(revised, body), 1)
        self.assertFalse(self.cache.exists())
        accepted = self.lessons["L-00000"][0][2].with_name("0002.md")
        self.assertEqual(m.read(accepted), m.encode(revised, body))
        self.assertNotEqual(self.cli("show", "L-00000").returncode, 0)
        self.assert_cli_ok("reindex", "--repair")
        self.assertEqual(self.get("L-00000")[0]["status"], "retired")
        self.assertEqual(self.query("needle00000")["candidates"], [])
        self.assertEqual(m.read(accepted), m.encode(revised, body))

    def test_catalogue_missing_corrupt_incompatible_wrong_root_and_incomplete_rebuild(self):
        self.get("E-00000")
        before = self.hashes()
        for damage in ("missing", "corrupt", "format", "root", "deleted-row", "traversal"):
            with self.subTest(damage=damage):
                if damage == "missing":
                    self.cache.unlink()
                elif damage == "corrupt":
                    self.cache.write_bytes(b"not a SQLite catalogue")
                else:
                    with contextlib.closing(sqlite3.connect(self.cache)) as db, db:
                        if damage in {"format", "root"}:
                            info = json.loads(db.execute("SELECT value FROM info").fetchone()[0])
                            info[damage] = -1 if damage == "format" else str(self.root.parent)
                            db.execute("UPDATE info SET value=?", (json.dumps(info),))
                        elif damage == "deleted-row":
                            db.execute("DELETE FROM records WHERE id='E-00000'")
                        else:
                            db.execute("UPDATE records SET path='../../outside.md' WHERE id='E-00000'")
                with mock.patch.object(self.store, "snapshot", wraps=self.store.snapshot) as snapshots:
                    self.assertEqual(self.get("E-00000")[0]["id"], "E-00000")
                self.assertEqual(snapshots.call_count, 1)
                self.assertEqual(self.hashes(), before)

    def test_out_of_band_add_edit_delete_restore_and_relocation(self):
        self.get("E-00000")
        saved_cache = self.cache.read_bytes()
        path = put(self.store, record("episode", "E-external", title="externalword"))
        self.assertEqual(self.query("externalword", kind="episodes")["total"], 1)
        original = path.read_bytes()
        path.write_text(record("episode", "E-external", title="changedword"), encoding="utf-8")
        self.assertEqual(self.query("externalword", kind="episodes")["total"], 0)
        self.assertEqual(self.query("changedword", kind="episodes")["total"], 1)
        path.unlink()
        self.assertEqual(self.query("changedword", kind="episodes")["total"], 0)
        path.write_bytes(original)
        self.cache.write_bytes(saved_cache)  # Restoring an older derived backup cannot hide the restored file.
        self.assertEqual(self.query("externalword", kind="episodes")["total"], 1)
        with tempfile.TemporaryDirectory(prefix="mettle-relocated-") as temporary:
            relocated = Path(temporary).resolve() / "copied root"
            shutil.copytree(self.root, relocated)
            target = m.Store(relocated)
            with target.lock(), c.open_catalogue(m, target) as catalogue:
                self.assertTrue(catalogue.get("E-external")[2].is_relative_to(relocated))

    def test_selected_corruption_and_reference_failure_are_visible(self):
        for damage in ("schema", "kind", "id", "encoding", "size", "reference"):
            with self.subTest(damage=damage):
                path = self.records["E-00001"][2]
                original = path.read_bytes()
                self.get("E-00001")
                meta, body = m.decode(original.decode())
                if damage == "encoding":
                    data = b"\xff\xfe\xff"
                elif damage == "size":
                    data = b"x" * (m.MAX_RECORD + 1)
                else:
                    meta.update({"schema": {"schema": 99}, "kind": {"kind": "review"},
                                 "id": {"id": "E-wrong"}, "reference": {"corrects": ["E-missing"]}}[damage])
                    data = m.encode(meta, body).encode()
                path.write_bytes(data)
                self.assertNotEqual(self.cli("show", "E-00001").returncode, 0)
                self.assertNotEqual(self.cli("search", "--kind", "episodes", "needle00001").returncode, 0)
                path.write_bytes(original)
        self.assert_cli_ok("reindex", "--repair")

    def test_targeted_success_does_not_assert_unrelated_current_views_healthy(self):
        self.revise()
        self.get("E-00000")
        unrelated = self.lessons["L-00001"][0][2].parent.parent / "current.md"
        unrelated.write_text("broken derived view", encoding="utf-8")
        self.assertEqual(self.get("E-00000")[0]["id"], "E-00000")
        self.assertNotEqual(self.cli("show", "L-00001").returncode, 0)
        self.assertNotEqual(self.cli("check").returncode, 0)
        # An old exact revision remains readable when its own current view is stale.
        current = self.lessons["L-00000"][0][2].parent.parent / "current.md"
        current.write_text("stale", encoding="utf-8")
        self.assertEqual(self.get("L-00000", 1)[0]["revision"], 1)
        self.assertNotEqual(self.cli("show", "L-00000").returncode, 0)
        self.assert_cli_ok("reindex", "--repair")
        self.assert_cli_ok("check")

    def test_selected_source_fingerprint_checks_bytes_even_without_inventory_change(self):
        # Simulate the documented limit of a metadata-preserving external editor.
        self.get("E-00000")
        observed = c.inventory(m, self.store)
        path = self.records["E-00000"][2]
        path.write_text(m.read(path).replace("needle00000", "needle99999"), encoding="utf-8")
        with mock.patch.object(c, "inventory", return_value=observed):
            with self.assertRaisesRegex(m.MettleError, "disagrees with catalogue"):
                self.get("E-00000")
        self.assert_cli_ok("reindex", "--repair")
        self.assertIn("needle99999", self.get("E-00000")[0]["title"])

    def test_full_check_still_detects_duplicate_ids_and_invalid_revision_sequences(self):
        self.get("E-00000")
        original = self.records["E-00000"][2]
        duplicate = original.parent.parent / original.name
        duplicate.write_bytes(original.read_bytes())
        self.assertNotEqual(self.cli("check").returncode, 0)
        self.assertNotEqual(self.cli("show", "E-00001").returncode, 0)  # Cold rebuild audits the archive.
        duplicate.unlink()
        self.revise()
        revision = self.lessons["L-00000"][0][2]
        revision.unlink()
        self.assertNotEqual(self.cli("check").returncode, 0)
        self.assertNotEqual(self.cli("reindex", "--repair").returncode, 0)

    def test_output_and_work_preserve_exact_revision_and_non_overwrite(self):
        self.revise(status="contested")
        output = self.root / "authored output.md"
        old = m.encode(*self.lessons["L-00000"][0][:2])
        self.assert_cli_ok("show", "L-00000", "--revision", "1", "--output", str(output))
        self.assertEqual(output.read_text(encoding="utf-8"), old)
        self.assertNotEqual(self.cli("show", "L-00000", "--output", str(output)).returncode, 0)
        self.assertEqual(output.read_text(encoding="utf-8"), old)
        with self.store.lock():
            identifier = w.start(m, self.store, "Synthetic exact draft", "fixture")["id"]
        result = self.assert_cli_ok("show", "L-00000", "--revision", "1", "--work", identifier)
        path = self.root / json.loads(result.stdout)["draft"]
        self.assertEqual(m.read(path), old)
        path.write_text(old + "\nAuthored draft note.\n", encoding="utf-8")
        second = self.assert_cli_ok("show", "L-00000", "--revision", "1", "--work", identifier)
        second_path = self.root / json.loads(second.stdout)["draft"]
        self.assertNotEqual(path, second_path)
        self.assertEqual(m.read(second_path), old)
        self.assertTrue(m.read(path).endswith("Authored draft note.\n"))

    def test_no_drafts_backups_or_workspace_notes_enter_search(self):
        with self.store.lock():
            identifier = w.start(m, self.store, "exclusiveterm", "fixture")["id"]
            w.make_draft(m, self.store, identifier, record("episode", "E-draft", title="exclusiveterm"))
        backup = self.store.path("backups/synthetic.md")
        backup.parent.mkdir(exist_ok=True)
        backup.write_text(record("episode", "E-backup", title="exclusiveterm"), encoding="utf-8")
        self.assertEqual(self.query("exclusiveterm", kind="episodes")["total"], 0)
        self.assertEqual(self.query("exclusiveterm", history=True)["total"], 0)

    def test_navigation_warm_long_unicode_hyphen_and_no_rewrites(self):
        for i in range(3):
            self.publish("lesson", f"L-hyphen-{i}", origin=["E-00000"], domain="-legacy",
                         title="日本" * 3000, scope=["café" * 1000])
        self.get("E-00000")
        before = self.hashes(), self.cache.stat().st_mtime_ns
        offset, found = 0, []
        while True:
            with self.store.lock(), c.open_catalogue(m, self.store) as catalogue:
                page = catalogue.navigation("-legacy", offset, 1)
            found.extend(item["id"] for item in page["items"])
            self.assertLessEqual(len(m.navigation_json(page).encode()), m.NAVIGATION_BYTES)
            if page["next_offset"] is None:
                break
            self.assertIn("--domain=-legacy", page["next_command"])
            offset = page["next_offset"]
        self.assertEqual(found, [f"L-hyphen-{i}" for i in range(3)])
        self.assertEqual((self.hashes(), self.cache.stat().st_mtime_ns), before)

    def test_rebuild_does_not_require_access_to_system_temp(self):
        before = self.hashes()
        self.cache.unlink(missing_ok=True)
        with mock.patch.object(tempfile, "tempdir", str(self.root / "unavailable-temp")):
            self.assertEqual(self.get("E-00000")[0]["id"], "E-00000")
        self.assertEqual(self.hashes(), before)
        self.assertEqual(list(self.cache.parent.glob(".mettle-catalogue-*")), [])
        self.assert_cli_ok("check")

    def test_cache_write_failure_keeps_accepted_state_recoverable(self):
        self.publish("episode", "E-accepted")
        original = m.write_atomic
        def write(path, text, **kwargs):
            if path.name == "catalogue.sqlite3":
                raise OSError("synthetic cache failure")
            return original(path, text, **kwargs)
        before = self.hashes()
        with mock.patch.object(m, "write_atomic", side_effect=write):
            with self.assertRaisesRegex(OSError, "synthetic"):
                self.get("E-accepted")
        self.assertEqual(self.hashes(), before)
        self.assertEqual(list(self.cache.parent.glob(".mettle-catalogue-*")), [])
        self.assert_cli_ok("reindex", "--repair")
        self.assertEqual(self.get("E-accepted")[0]["id"], "E-accepted")

    def test_install_rebuild_preserves_canonical_profile_work_and_unchanged_cache(self):
        self.get("E-00000")
        before = self.hashes()
        self.cache.write_bytes(b"older incompatible backup")
        m.install(self.root, [])
        self.assertEqual(self.hashes(), before)
        cache = self.cache.read_bytes(), self.cache.stat().st_mtime_ns
        m.install(self.root, [])
        self.assertEqual((self.cache.read_bytes(), self.cache.stat().st_mtime_ns), cache)
        self.assertEqual(self.hashes(), before)

    def test_symlink_cache_and_canonical_paths_rejected(self):
        self.get("E-00000")
        target = self.root / "outside.sqlite3"
        self.cache.replace(target)
        try:
            self.cache.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"Symlink permission unavailable: {exc}")
        self.assertNotEqual(self.cli("show", "E-00000").returncode, 0)
        self.cache.unlink()
        target.replace(self.cache)
        path = self.records["E-00000"][2]
        outside = self.root / "outside.md"
        path.replace(outside)
        path.symlink_to(outside)
        self.assertNotEqual(self.cli("show", "E-00000").returncode, 0)

    def test_check_verifies_cache_contents_without_another_snapshot(self):
        self.get("E-00000")
        with contextlib.closing(sqlite3.connect(self.cache)) as db, db:
            db.execute("UPDATE records SET lexical='{}' WHERE id='E-00000'")
        self.assertNotEqual(self.cli("check").returncode, 0)
        before = self.hashes()
        self.assert_cli_ok("reindex", "--repair")
        self.assert_cli_ok("check")
        self.assertEqual(self.hashes(), before)

    def test_check_reuses_one_verified_snapshot(self):
        output = io.StringIO()
        with mock.patch.object(m.Store, "snapshot", autospec=True, side_effect=m.Store.snapshot) as snapshots, \
                contextlib.redirect_stdout(output):
            self.assertEqual(m.main(["check", "--root", str(self.root)]), 0)
        self.assertEqual(snapshots.call_count, 1)


if __name__ == "__main__":
    unittest.main()
