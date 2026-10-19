"""Synthetic regressions for PR #6's size, recovery, and draft-lifecycle review.

No private pilot records, real session IDs, or model calls are used.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_migrate as mg
import mettle_work as w


class WorkspaceHardeningTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-hardening-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        with self.store.lock():
            self.id = w.start(m, self.store, "Synthetic investigation", "test component")['id']
        self.folder = w.work_path(m, self.store, self.id)
        self.manifest = self.folder / "WORK.md"
        self.helper = self.store.home / "tools/mettle.py"

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args],
                              capture_output=True, timeout=30)

    def record(self, kind="episode", identifier="E-test", **fields):
        meta, body = m.decode(m.template(kind))
        meta.update(id=identifier, title="Synthetic test evidence", **fields)
        return m.encode(meta, body.replace("TODO", "Authored fixture; not an observed model result."))

    def accept(self, kind="episode", identifier="E-test", **fields):
        with self.store.lock():
            return self.store.publish(self.record(kind, identifier, **fields), 0 if kind == "lesson" else None)

    def draft(self, text=None):
        with self.store.lock():
            result = w.make_draft(m, self.store, self.id, text or m.template("episode"))
        return self.root / result['draft']

    def checkpoint(self, reason="Nothing warrants an accepted update."):
        with self.store.lock():
            return w.checkpoint(m, self.store, self.id, 'no-update', reason, [], None)

    def hashes(self):
        return {p.relative_to(self.root).as_posix(): w.sha(p.read_bytes())
                for p in self.root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}

    def test_large_checkpoint_history_is_segmented_without_truncation(self):
        expected = []
        for index in range(75):
            # UTF-8 byte size, not just character count, is relevant to page limits.
            expected.append(self.checkpoint(f'{index}: ' + 'é' * 1950))
        meta, _ = w.read_work(m, self.store, self.id)
        self.assertEqual(meta['checkpoints'], expected)
        self.assertGreater(len(json.dumps(expected, ensure_ascii=False).encode()), m.MAX_RECORD)
        self.assertLess(self.manifest.stat().st_size, 3000)
        self.assertEqual(m.decode(m.read(self.manifest))[0]['schema'], 2)
        for page in (self.folder / 'ledger').glob('*.json'):
            self.assertLessEqual(page.stat().st_size, w.PAGE_BYTES)
            self.assertEqual(w.sha(page.read_bytes()), page.stem)
        with self.store.lock():
            w.update(m, self.store, self.id, 'closed', None)
            self.assertEqual(w.validate(m, self.store)['workspaces'], 1)
        self.assertEqual(self.cli('check').returncode, 0)

    def test_navigation_and_bootstrap_do_not_hydrate_ledgers(self):
        self.checkpoint()
        with mock.patch.object(w, 'read_ledger', side_effect=AssertionError('History loaded during navigation')):
            self.assertEqual(w.summary(m, self.store)['items'][0]['id'], self.id)
            self.assertIn(self.id, w.index_text(m, self.store))
            with self.store.lock():
                payload = json.loads(m.bootstrap(self.store, 'manual', {}).rsplit('\n\n', 1)[1])
            self.assertEqual(payload['unfinished_work']['items'][0]['id'], self.id)

    def test_unfinished_navigation_can_reach_every_activity(self):
        meta, _ = w.read_work(m, self.store, self.id)
        entries = [{**meta, 'id': f'W-{i}'} for i in range(130)]
        with mock.patch.object(w, 'all_work', return_value=entries):
            first = w.summary(m, self.store, 100)
            second = w.summary(m, self.store, 100, first['next_offset'])
            self.assertEqual(len(first['items']), 100)
            self.assertEqual(len(second['items']), 30)
            self.assertIsNone(second['next_offset'])
            self.assertEqual(first['remaining'], 30)
        page = self.cli('work', 'list', '--offset', '1', '--limit', '1')
        self.assertEqual(page.returncode, 0, page.stderr)
        self.assertEqual(json.loads(page.stdout)['work']['items'], [])

    def test_oversized_notes_leave_manifest_index_and_pages_unchanged(self):
        self.checkpoint()
        meta, _ = w.read_work(m, self.store, self.id)
        meta['checkpoints'].append({'reason': 'new entry that must not be written'})
        before = self.hashes()
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'header exceed'):
            w.save_work(m, self.store, meta, 'x' * m.MAX_RECORD)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(len(w.read_work(m, self.store, self.id)[0]['checkpoints']), 1)

    def test_one_oversized_entry_fails_before_any_page_or_manifest_write(self):
        meta, body = w.read_work(m, self.store, self.id)
        meta['checkpoints'].append({'reason': 'x' * w.PAGE_BYTES})
        before = self.hashes()
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'entry exceeds'):
            w.save_work(m, self.store, meta, body)
        self.assertEqual(self.hashes(), before)

    def test_interrupted_manifest_switch_keeps_prior_ledger_and_retry(self):
        first = self.checkpoint('First preserved decision.')
        meta, body = w.read_work(m, self.store, self.id)
        second = {**first, 'reason': 'Second decision.'}
        meta['checkpoints'].append(second)
        before = self.manifest.read_bytes()
        real = m.write_atomic
        def fail_switch(path, data, **kwargs):
            if path == self.manifest:
                raise OSError('Interrupted manifest switch')
            return real(path, data, **kwargs)
        with self.store.lock(), mock.patch.object(m, 'write_atomic', side_effect=fail_switch), self.assertRaises(OSError):
            w.save_work(m, self.store, meta, body)
        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertEqual(w.read_work(m, self.store, self.id)[0]['checkpoints'], [first])
        with self.store.lock():
            w.save_work(m, self.store, meta, body)
        self.assertEqual(w.read_work(m, self.store, self.id)[0]['checkpoints'], [first, second])

    def test_page_corruption_is_reported_without_reset(self):
        self.checkpoint()
        header, _ = m.decode(m.read(self.manifest))
        head = header['ledgers']['checkpoints']['head']
        page = self.folder / 'ledger' / (head + '.json')
        page.write_bytes(page.read_bytes().replace(b'\n', b'\r\n'))
        before = page.read_bytes()
        with self.assertRaisesRegex(m.MettleError, 'hash mismatch'):
            w.validate(m, self.store)
        self.assertEqual(page.read_bytes(), before)
        self.assertTrue(w.summary(m, self.store)['items'])

    def legacy_manifest(self, count=1):
        meta, body = w.read_work(m, self.store, self.id)
        meta.pop('ledgers', None)
        meta.pop('draft_decisions', None)
        meta['schema'] = 1
        meta['checkpoints'] = [{'activity_revision': 1, 'decision': 'no-update', 'reason': f'{i}: ' + 'x' * 2000,
                                'records': [], 'next_review': None, 'at': m.now()} for i in range(count)]
        raw = m.encode(meta, body).encode()
        self.manifest.write_bytes(raw)
        return meta, body, raw

    def test_small_legacy_workspace_upgrades_on_save_preserving_entries(self):
        old, _, _ = self.legacy_manifest()
        with self.store.lock():
            w.update(m, self.store, self.id, 'paused', 'Waiting for new evidence.')
        new, _ = w.read_work(m, self.store, self.id)
        self.assertEqual(new['schema'], 2)
        self.assertEqual(new['checkpoints'], old['checkpoints'])
        self.assertEqual(new['draft_decisions'], [])

    def test_explicit_recovery_of_oversized_legacy_work_keeps_original_bytes(self):
        old, _, raw = self.legacy_manifest(65)
        self.assertGreater(len(raw), m.MAX_RECORD)
        with self.assertRaises(m.MettleError):
            w.read_work(m, self.store, self.id)
        result = self.cli('work', 'repair-storage', self.id)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / json.loads(result.stdout)['backup']).read_bytes(), raw)
        self.assertEqual(w.read_work(m, self.store, self.id)[0]['checkpoints'], old['checkpoints'])
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertEqual(self.cli('work', 'repair-storage', self.id).returncode, 1)

    def test_work_show_is_bounded_and_history_paginates_without_writes(self):
        for i in range(27):
            self.checkpoint(f'Decision {i}')
        before = self.hashes()
        shown = json.loads(self.cli('work', 'show', self.id).stdout)
        self.assertEqual(len(shown['work']['checkpoints']), 10)
        self.assertEqual(shown['ledger_counts']['checkpoints'], 27)
        self.assertEqual(shown['omitted']['checkpoints'], 17)
        page = json.loads(self.cli('work', 'history', self.id, '--kind', 'checkpoints', '--offset', '20', '--limit', '4').stdout)
        self.assertEqual([x['reason'] for x in page['entries']], [f'Decision {i}' for i in range(20, 24)])
        self.assertEqual(page['next_offset'], 24)
        self.assertEqual(self.hashes(), before)

    def test_index_is_bounded_even_with_many_long_handoffs(self):
        meta, _ = w.read_work(m, self.store, self.id)
        entries = [{**meta, 'id': f'W-{i}', 'next_action': 'x' * 1000} for i in range(200)]
        with mock.patch.object(w, 'all_work', return_value=entries):
            text = w.index_text(m, self.store)
        self.assertLess(len(text.encode()), m.MAX_RECORD)
        self.assertIn('further activities omitted', text)

    def test_revision_draft_keeps_original_file_and_metadata_until_explicit_edit(self):
        self.accept()
        text = self.record('lesson', 'L-test', origin=['E-test'], scope=['test'])
        first = self.draft(text)
        with self.store.lock():
            accepted_path = w.publish(m, self.store, first, 0)
        before = first.read_bytes()
        copied = self.cli('show', 'L-test', '--work', self.id)
        self.assertEqual(copied.returncode, 0, copied.stderr)
        second = self.root / json.loads(copied.stdout)['draft']
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual(m.decode(m.read(second))[0]['revision'], 1)
        third = self.draft(text)
        self.assertNotEqual(third, second)
        reconciliation = self.record('reconciliation', 'C-revise', inputs=['L-test@1'], evidence=['E-test'], operation='REVISE')
        with self.store.lock():
            self.store.publish(reconciliation, None)
        meta, body = m.decode(m.read(second))
        meta.update(revision=2, reconciliations=['C-revise'])
        second.write_text(m.encode(meta, body), encoding='utf-8')
        with self.store.lock():
            w.publish(m, self.store, second, 1)
        self.assertEqual(first.read_bytes(), before)
        self.assertEqual((self.root / accepted_path).read_bytes(), before)
        self.assertEqual(len(self.store.snapshot()[1]['L-test']), 2)
        self.assertEqual(len(w.read_work(m, self.store, self.id)[0]['publications']), 2)
        # Explicit paths retain the old no-overwrite contract.
        self.assertEqual(self.cli('show', 'L-test', '--output', str(second)).returncode, 1)

    def test_abandon_retains_unpublishable_draft_and_permits_no_update_closure(self):
        draft = self.draft()  # Still contains TODO; it must not become accepted evidence.
        raw = draft.read_bytes()
        self.checkpoint()
        result = self.cli('work', 'abandon-draft', self.id, str(draft), '--reason', 'Investigation does not warrant a record.')
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = json.loads(result.stdout)
        self.assertEqual(entry['draft_sha256'], w.sha(raw))
        self.assertEqual(draft.read_bytes(), raw)
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'current learning checkpoint'):
            w.update(m, self.store, self.id, 'closed', None)
        self.checkpoint()
        with self.store.lock():
            w.update(m, self.store, self.id, 'closed', None)
        self.assertEqual(self.store.snapshot(), ({}, {}))
        self.assertEqual(self.cli('check').returncode, 0)

    def test_changed_abandoned_draft_needs_a_new_decision(self):
        draft = self.draft()
        with self.store.lock():
            w.draft_decision(m, self.store, self.id, draft, 'abandoned', 'Insufficient information.')
        draft.write_bytes(draft.read_bytes() + b'\nNew material.\n')
        self.checkpoint()
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'draft remains'):
            w.update(m, self.store, self.id, 'closed', None)
        self.assertTrue(w.validate(m, self.store)['work_warnings'])
        with self.store.lock():
            w.draft_decision(m, self.store, self.id, draft, 'abandoned', 'New material is still unsuitable.')
        self.checkpoint()
        with self.store.lock():
            w.update(m, self.store, self.id, 'closed', None)
        self.assertEqual(len(w.read_work(m, self.store, self.id)[0]['draft_decisions']), 2)

    def test_resume_abandonment_is_explicit_reversible_and_does_not_edit_bytes(self):
        draft = self.draft(self.record())
        raw = draft.read_bytes()
        with self.store.lock():
            w.draft_decision(m, self.store, self.id, draft, 'abandoned', 'Need to reconsider.')
            with self.assertRaisesRegex(m.MettleError, 'resume-draft'):
                w.publish(m, self.store, draft, None)
            w.draft_decision(m, self.store, self.id, draft, 'resumed', 'Evidence checked; resume publication.')
        self.assertEqual(draft.read_bytes(), raw)
        self.checkpoint()
        with self.store.lock():
            with self.assertRaises(m.MettleError):
                w.update(m, self.store, self.id, 'closed', None)
            w.publish(m, self.store, draft, None)
        self.checkpoint()
        with self.store.lock():
            w.update(m, self.store, self.id, 'closed', None)
        entries = w.read_work(m, self.store, self.id)[0]['draft_decisions']
        self.assertEqual([e['decision'] for e in entries], ['abandoned', 'resumed'])
        self.assertEqual(len(self.store.snapshot()[0]), 1)

    def test_draft_decision_is_idempotent_scoped_and_non_destructive(self):
        draft = self.draft(self.record())
        with self.store.lock():
            w.publish(m, self.store, draft, None)
            first = w.draft_decision(m, self.store, self.id, Path('drafts') / draft.name, 'abandoned', 'Keep only as a retained working copy.')
            second = w.draft_decision(m, self.store, self.id, draft, 'abandoned', 'Keep only as a retained working copy.')
            self.assertEqual(first['activity_revision'], second['activity_revision'])
            other = w.start(m, self.store, 'Another task', 'other')['id']
            with self.assertRaises(m.MettleError):
                w.draft_decision(m, self.store, other, draft, 'abandoned', 'Wrong workspace.')
        self.assertTrue(draft.exists())
        self.assertEqual(len(self.store.snapshot()[0]), 1)  # Abandonment never retires published evidence.
        self.assertEqual(len(w.read_work(m, self.store, self.id)[0]['draft_decisions']), 1)


class MigrationHardeningTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='mettle-journal-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)

    def originals(self, count=12):
        for i in range(count):
            (self.store.home / f'legacy-draft-{i:04}.md').write_bytes(b'Unpublished synthetic text.\n')

    def hashes(self):
        return {p.relative_to(self.root).as_posix(): w.sha(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}

    def unchecked_plan(self):
        with mock.patch.object(mg, 'journal_capacity', return_value=0):
            return mg.plan(m, self.store)

    def test_completed_size_is_reserved_in_preview_and_apply_before_mutation(self):
        self.originals(40)
        p = self.unchecked_plan()
        initial = len(mg.journal_text(mg.new_journal(m, p)).encode())
        complete = mg.journal_capacity(m, mg.new_journal(m, p))
        self.assertGreater(complete, initial)
        before = self.hashes()
        with mock.patch.object(m, 'MAX_RECORD', initial + 1):
            with self.assertRaisesRegex(m.MettleError, 'Completed migration manifest'):
                mg.plan(m, self.store)
            with self.assertRaisesRegex(m.MettleError, 'Completed migration manifest'):
                mg.apply(m, self.store, p['plan_id'])
        self.assertEqual(self.hashes(), before)
        self.assertEqual(list(self.store.path('migrations').glob('*/manifest.json')), [])

    def test_plan_at_exact_completed_capacity_can_finish_and_restore(self):
        self.originals(40)
        p = mg.plan(m, self.store)
        limit = mg.journal_capacity(m, mg.new_journal(m, p))
        before = {e['source']: (self.store.home / e['source']).read_bytes() for e in p['moves']}
        with mock.patch.object(m, 'MAX_RECORD', limit):
            self.assertEqual(mg.apply(m, self.store, p['plan_id'])['status'], 'completed')
            journal = mg.journal_path(m, self.store, p['id'])
            self.assertLessEqual(journal.stat().st_size, limit)
            with self.store.lock():
                self.assertEqual(mg.restore(m, self.store, p['id'], True)['status'], 'restored')
            self.assertLessEqual(journal.stat().st_size, limit)
        for name, data in before.items():
            self.assertEqual((self.store.home / name).read_bytes(), data)

    def partial_legacy(self, count=12):
        self.originals(count)
        p = self.unchecked_plan()
        journal = mg.new_journal(m, p)
        path = mg.journal_path(m, self.store, p['id'])
        m.write_atomic(path, mg.journal_text(journal), exclusive=True)
        # Reproduce interruption after unlink but before the completion update.
        e = p['moves'][0]
        source = self.store.home / e['source']
        backup = self.store.path(f"migrations/{p['id']}/originals/{e['source']}")
        dest = self.store.home / e['destination']
        mg.exact_copy(m, source, backup, e['sha256'])
        mg.exact_copy(m, backup, dest, e['sha256'])
        source.unlink()
        return p, path, source, dest, backup

    def test_restore_partial_legacy_migration_when_resume_cannot_fit(self):
        p, path, source, dest, backup = self.partial_legacy(40)
        limit = path.stat().st_size + 1
        expected = backup.read_bytes()
        dest.write_bytes(b'Newer work must be retained.')
        before = self.hashes()
        with mock.patch.object(m, 'MAX_RECORD', limit):
            with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'Completed migration manifest'):
                mg.resume(m, self.store, p['id'])
            view = mg.restore(m, self.store, p['id'], False)
            self.assertEqual(self.hashes(), before)
            self.assertEqual(view['copies_needed'], [p['moves'][0]['source']])
            with self.store.lock():
                result = mg.restore(m, self.store, p['id'], True)
                self.assertEqual(result['status'], 'restored')
                self.assertEqual(result['copied'], 1)
                self.assertEqual(mg.restore(m, self.store, p['id'], True)['copied'], 0)
            self.assertLessEqual(path.stat().st_size, limit)
        self.assertEqual(source.read_bytes(), expected)
        self.assertEqual(dest.read_bytes(), b'Newer work must be retained.')
        for e in p['moves']:
            self.assertEqual(w.sha((self.store.home / e['source']).read_bytes()), e['sha256'])
        with self.store.lock(), self.assertRaises(m.MettleError):
            mg.resume(m, self.store, p['id'])

    def test_restore_can_retry_after_its_own_interruption(self):
        p, _, source, _, _ = self.partial_legacy()
        with self.store.lock(), mock.patch.object(mg, 'exact_copy', side_effect=OSError('Interrupted restore')), self.assertRaises(OSError):
            mg.restore(m, self.store, p['id'], True)
        self.assertFalse(source.exists())
        self.assertEqual(mg.load_journal(m, self.store, p['id'])[1]['status'], 'restoring')
        with self.store.lock():
            self.assertEqual(mg.restore(m, self.store, p['id'], True)['status'], 'restored')
        self.assertTrue(source.exists())

    def test_partial_restore_conflicts_are_checked_before_writes(self):
        p, _, source, _, backup = self.partial_legacy()
        backup.write_bytes(b'corrupted')
        before = self.hashes()
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'Backup changed'):
            mg.restore(m, self.store, p['id'], True)
        self.assertEqual(self.hashes(), before)
        backup.unlink()
        with self.assertRaisesRegex(m.MettleError, 'Missing original'):
            mg.restore(m, self.store, p['id'], False)
        self.assertFalse(source.exists())

    def test_windows_case_and_separator_references_are_kept_on_every_host(self):
        for name, reference in [('evidence-draft.md', r'D:\project\.agent-personality\EVIDENCE-DRAFT.MD'),
                                ('café-draft.md', 'D:/project/.agent-personality/CAFÉ-DRAFT.MD')]:
            (self.store.home / name).write_bytes(b'Unpublished candidate.')
            meta, body = m.decode(m.template('episode'))
            meta.update(title='Synthetic evidence reference')
            with self.store.lock():
                self.store.publish(m.encode(meta, body.replace('TODO', 'Source: ' + reference)), None)
        before = self.hashes()
        plan = mg.plan(m, self.store)
        self.assertEqual(plan['moves'], [])
        self.assertEqual({e['source'] for e in plan['kept']}, {'evidence-draft.md', 'café-draft.md'})
        self.assertTrue(all(e['references'] for e in plan['kept']))
        self.assertEqual(self.hashes(), before)

    def test_reference_matching_does_not_match_larger_filenames(self):
        (self.store.home / 'evidence-draft.md').write_bytes(b'Candidate.')
        (self.store.home / 'operator-notes.md').write_text('Different filename: prefix-evidence-draft.md-suffix', encoding='utf-8')
        p = mg.plan(m, self.store)
        self.assertEqual([e['source'] for e in p['moves']], ['evidence-draft.md'])


if __name__ == '__main__':
    unittest.main()
