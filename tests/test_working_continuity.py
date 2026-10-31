"""Synthetic progress/discovery contracts, not evidence that an LLM resumes well."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_work as w


class WorkingContinuityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="mettle-continuity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"
        with self.store.lock():
            self.id = w.start(m, self.store, "Investigate callback lifetime", "Synthetic read-only review")['id']
        self.path = w.work_path(m, self.store, self.id) / "WORK.md"

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args],
                              capture_output=True, encoding="utf-8", timeout=30)

    def update(self, **kwargs):
        with self.store.lock():
            return w.update(m, self.store, self.id, kwargs.pop("status", None),
                            kwargs.pop("next_action", None), **kwargs)

    def hashes(self):
        return {p.relative_to(self.store.home).as_posix(): w.sha(p.read_bytes())
                for p in self.store.home.rglob("*") if p.is_file()}

    def close(self):
        with self.store.lock():
            w.checkpoint(m, self.store, self.id, 'no-update', 'No new learning is warranted.', [], None)
            w.update(m, self.store, self.id, 'closed', 'Delivered the scoped review; implementation remains separate.')

    def test_progress_does_not_publish_learning_or_change_profiles(self):
        profiles = {p.name: p.read_bytes() for p in self.store.path('personality').iterdir()}
        self.update(summary_text='Configuration ruled out; lifetime remains hypothetical.',
                    notes='## Results so far\nConfiguration checked.\n\n## Uncertainty\nNo reproduction yet.',
                    next_action='Inspect the owner destruction sequence.')
        meta, notes = w.read_work(m, self.store, self.id)
        self.assertIn('No reproduction yet', notes)
        self.assertEqual(meta['status'], 'open')
        self.assertEqual(meta['checkpoints'], [])
        self.assertEqual(self.store.snapshot(), ({}, {}))
        self.assertEqual(profiles, {p.name: p.read_bytes() for p in self.store.path('personality').iterdir()})

    def test_repeated_identical_progress_is_a_noop(self):
        args = dict(summary_text='A bounded finding.', notes='A useful handoff.', next_action='Inspect evidence.')
        first = self.update(**args)
        before = self.hashes()
        with self.store.lock(), mock.patch.object(m, 'write_atomic', side_effect=AssertionError('Healthy retry wrote a file')):
            second = w.update(m, self.store, self.id, None, **args)
        self.assertTrue(first['changed'])
        self.assertFalse(second['changed'])
        self.assertEqual(first['activity_revision'], second['activity_revision'])
        self.assertEqual(before, self.hashes())

    def test_identical_retry_repairs_interrupted_index_without_rewriting_handoff(self):
        for args in (dict(next_action='Inspect the retained evidence.'),
                     dict(summary_text='A new finding.', notes='Still uncertain; inspect the source.')):
            with self.subTest(args=args):
                index = self.store.path('work/INDEX.md')
                real_replace = os.replace

                def interrupted(src, dst):
                    if Path(dst) == index:
                        raise OSError('simulated index replacement failure')
                    return real_replace(src, dst)

                with mock.patch.object(os, 'replace', side_effect=interrupted), self.assertRaises(OSError):
                    self.update(**args)
                with self.assertRaisesRegex(m.MettleError, 'Stale work index'):
                    w.validate(m, self.store)
                saved = self.path.read_bytes()
                modified = self.path.stat().st_mtime_ns
                revision = w.read_work(m, self.store, self.id)[0]['activity_revision']
                with self.store.lock(), mock.patch.object(m, 'write_atomic', wraps=m.write_atomic) as writes:
                    retry = w.update(m, self.store, self.id, None, args.get('next_action'),
                                     summary_text=args.get('summary_text'), notes=args.get('notes'))
                self.assertFalse(retry['changed'])
                self.assertEqual(retry['activity_revision'], revision)
                self.assertEqual(self.path.read_bytes(), saved)
                self.assertEqual(self.path.stat().st_mtime_ns, modified)
                self.assertEqual([call.args[0] for call in writes.call_args_list], [index])
                self.assertEqual(w.validate(m, self.store)['workspaces'], 1)

    def test_identical_retry_recreates_missing_index(self):
        self.update(notes='Saved findings.')
        index = self.store.path('work/INDEX.md')
        index.unlink()
        saved = self.path.read_bytes()
        retry = self.update(notes='Saved findings.')
        self.assertFalse(retry['changed'])
        self.assertEqual(self.path.read_bytes(), saved)
        self.assertTrue(index.is_file())
        self.assertEqual(w.validate(m, self.store)['workspaces'], 1)

    def test_progress_save_needs_no_learning_checkpoint(self):
        for step in range(4):
            self.update(notes=f'Progress at step {step}; not final.', next_action='Continue the investigation.')
        meta, _ = w.read_work(m, self.store, self.id)
        self.assertEqual(meta['checkpoints'], [])
        self.assertEqual(meta['activity_revision'], 5)
        self.assertEqual(self.store.snapshot(), ({}, {}))

    def test_changed_summary_invalidates_old_checkpoint(self):
        with self.store.lock():
            w.checkpoint(m, self.store, self.id, 'no-update', 'Initial assessment.', [], None)
        self.update(summary_text='New material uncertainty.')
        with self.assertRaisesRegex(m.MettleError, 'checkpoint'):
            self.update(status='closed')
        self.close()

    def test_changed_notes_invalidates_old_checkpoint(self):
        with self.store.lock():
            w.checkpoint(m, self.store, self.id, 'no-update', 'Initial assessment.', [], None)
        self.update(notes='An earlier conclusion was challenged.')
        with self.assertRaisesRegex(m.MettleError, 'checkpoint'):
            self.update(status='closed')

    def test_combined_changed_progress_and_close_refused_without_writes(self):
        with self.store.lock():
            w.checkpoint(m, self.store, self.id, 'no-update', 'Initial assessment.', [], None)
        before = self.hashes()
        with self.assertRaisesRegex(m.MettleError, 'checkpoint'):
            self.update(summary_text='Materially different result.', status='closed')
        self.assertEqual(before, self.hashes())

    def test_closed_work_requires_reopening_for_new_progress(self):
        self.close()
        before = self.hashes()
        with self.assertRaisesRegex(m.MettleError, 'Reopen'):
            self.update(notes='A new investigation.')
        self.assertEqual(before, self.hashes())
        result = self.update(status='open', notes='A new investigation.')
        self.assertEqual(result['activity_revision'], 2)

    def test_silence_and_old_timestamp_do_not_close_work(self):
        meta, body = w.read_work(m, self.store, self.id)
        # An old timestamp is data, not a mandate for inactivity-based closure.
        meta['updated_at'] = '2000-01-01T00:00:00+00:00'
        m.write_atomic(self.path, m.encode({k: v for k, v in meta.items() if k not in w.LEDGER_KEYS}, body))
        before = self.path.read_bytes()
        result = self.cli('work', 'list', '--status', 'all')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['work']['items'][0]['status'], 'open')
        self.assertEqual(before, self.path.read_bytes())

    def test_partial_results_survive_exit_without_shutdown_hook(self):
        # Save once, then terminate immediately; no final reflection or hook runs.
        script = '''import os, sys
sys.path.insert(0, sys.argv[1])
import mettle as m, mettle_work as w
from pathlib import Path
s=m.Store(Path(sys.argv[2]))
with s.lock():
 w.update(m,s,sys.argv[3],None,"Inspect the callback",summary_text="First explanation ruled out",notes="## Remaining uncertainty\\nLifetime not reproduced. Partial output may be missing.")
os._exit(23)
'''
        result = subprocess.run([sys.executable, '-c', script, str(self.helper.parent), str(self.root), self.id],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 23, result.stderr)
        fresh = self.cli('work', 'show', self.id)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        view = json.loads(fresh.stdout)
        self.assertEqual(view['work']['summary'], 'First explanation ruled out')
        self.assertIn('not reproduced', view['notes'])
        self.assertEqual(view['work']['checkpoints'], [])
        self.assertEqual(view['work']['status'], 'open')

    def test_failed_atomic_replace_preserves_previous_handoff(self):
        self.update(notes='Previously saved findings.')
        before = self.path.read_bytes()
        real = os.replace
        def interrupted(src, dst):
            if Path(dst) == self.path:
                raise OSError('simulated disk/replace failure')
            return real(src, dst)
        with mock.patch.object(os, 'replace', side_effect=interrupted), self.assertRaises(OSError):
            self.update(notes='Not successfully saved.')
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(w.read_work(m, self.store, self.id)[1], 'Previously saved findings.')

    def test_oversized_notes_fail_before_changing_workspace(self):
        before = self.hashes()
        with self.assertRaises(m.MettleError):
            self.update(notes='x' * m.MAX_RECORD)
        self.assertEqual(before, self.hashes())

    def test_invalid_summary_and_notes_have_no_side_effects(self):
        for args in ({'summary_text': ''}, {'summary_text': 'a\nb'},
                     {'summary_text': 'x' * 1001}, {'notes': ''}, {'notes': 'binary\x00data'}):
            with self.subTest(args=list(args)):
                before = self.hashes()
                with self.assertRaises(m.MettleError):
                    self.update(**args)
                self.assertEqual(before, self.hashes())

    def test_notes_file_utf8_bom_and_crlf(self):
        source = self.root / 'handoff-input.md'
        source.write_bytes(b'\xef\xbb\xbf' + '## Results\r\nA café finding.\r\n'.encode('utf-8'))
        result = self.cli('work', 'update', self.id, '--notes-file', str(source), '--summary', 'A café finding.')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(w.read_work(m, self.store, self.id)[1], '## Results\nA café finding.')
        self.assertIn(b'\r\n', source.read_bytes())  # Input not rewritten or adopted as current state.
        source.unlink()
        self.assertIn('café', w.read_work(m, self.store, self.id)[1])

    def test_notes_and_notes_file_are_mutually_exclusive(self):
        result = self.cli('work', 'update', self.id, '--notes', 'text', '--notes-file', 'other.md')
        self.assertEqual(result.returncode, 2)

    def test_notes_file_missing_or_invalid_encoding_preserves_state(self):
        source = self.root / 'invalid.md'
        for data in (None, b'\xff'):
            if data is not None:
                source.write_bytes(data)
            before = self.hashes()
            result = self.cli('work', 'update', self.id, '--notes-file', str(source))
            self.assertEqual(result.returncode, 1)
            self.assertEqual(before, self.hashes())

    def test_completed_work_is_discoverable_but_not_in_default_list(self):
        self.update(summary_text='Callback report delivered; no implementation promised.',
                    notes='## Outcome\nReview delivered.\n\n## Limits\nNo native reproduction.')
        self.close()
        self.assertEqual(w.summary(m, self.store)['total'], 0)
        result = self.cli('work', 'list', '--status', 'closed', '--query', 'callback', 'report')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['work']['items'][0]['id'], self.id)
        self.assertEqual(self.store.snapshot(), ({}, {}))
        self.assertEqual(m.search(self.store, ['callback'], 5, None, kind='episodes'), [])

    def test_list_filters_open_paused_closed_all(self):
        self.update(status='paused', next_action='Wait for requested logs.')
        with self.store.lock():
            another = w.start(m, self.store, 'Other investigation', 'fixture')['id']
        self.assertEqual(w.summary(m, self.store, status='open')['items'][0]['id'], another)
        self.assertEqual(w.summary(m, self.store, status='paused')['items'][0]['id'], self.id)
        self.close()
        self.assertEqual(w.summary(m, self.store, status='closed')['items'][0]['id'], self.id)
        self.assertEqual(w.summary(m, self.store, status='all')['total'], 2)
        self.assertEqual(w.summary(m, self.store)['total'], 1)

    def test_activity_query_uses_notes_not_only_summary(self):
        self.update(notes='Inspected the zephyr boundary; result remains uncertain.')
        matches = w.summary(m, self.store, status='all', query=['ZEPHYR', 'boundary'])
        self.assertEqual(matches['items'][0]['id'], self.id)
        self.assertEqual(w.summary(m, self.store, query=['zephyr', 'nonexistent'])['total'], 0)
        self.assertEqual(w.summary(m, self.store, query=['phyr'])['total'], 0)

    def test_activity_query_excludes_scratch_and_ledgers(self):
        folder = w.work_path(m, self.store, self.id)
        (folder / 'artifacts').mkdir()
        (folder / 'artifacts/private.txt').write_text('scratchneedle')
        with self.store.lock():
            w.checkpoint(m, self.store, self.id, 'no-update', 'ledgerneedle', [], None)
        for term in ['scratchneedle', 'ledgerneedle']:
            self.assertEqual(w.summary(m, self.store, status='all', query=[term])['total'], 0)

    def test_listing_and_queries_do_not_hydrate_ledgers_or_write(self):
        self.update(notes='A retained question.')
        before = self.hashes()
        with mock.patch.object(w, 'read_ledger', side_effect=AssertionError('history loaded')):
            w.summary(m, self.store, status='all', query=['retained'])
            w.index_text(m, self.store)
        self.assertEqual(before, self.hashes())

    def test_pagination_retains_selection_and_reaches_old_work(self):
        for n in range(7):
            with self.store.lock():
                w.start(m, self.store, f'Other activity {n}', 'Synthetic review')
        ids, offset = set(), 0
        while True:
            page = w.summary(m, self.store, limit=3, offset=offset, status='all', query=['review'])
            self.assertEqual(page['status_filter'], 'all')
            self.assertEqual(page['query'], ['review'])
            ids.update(item['id'] for item in page['items'])
            if page['next_offset'] is None:
                break
            offset = page['next_offset']
        self.assertEqual(len(ids), 8)
        self.assertIn(self.id, ids)

    def test_bounded_previews_report_truncation_without_truncating_storage(self):
        text = 'z' * 1000
        self.update(summary_text=text, next_action=text)
        preview = w.summary(m, self.store)['items'][0]
        self.assertEqual(len(preview['summary']), w.PREVIEW_CHARS)
        self.assertEqual(preview['preview_truncated'], ['summary', 'next_action'])
        self.assertEqual(w.read_work(m, self.store, self.id)[0]['summary'], text)

    def test_bootstrap_contains_orientation_not_complete_notes(self):
        self.update(summary_text='Configuration ruled out.', notes='long-private-note-marker',
                    next_action='Inspect callback ownership.')
        with self.store.lock():
            context = m.bootstrap(self.store, 'manual', {})
        self.assertIn('Configuration ruled out.', context)
        self.assertIn('Inspect callback ownership.', context)
        self.assertNotIn('long-private-note-marker', context)
        self.assertLess(len(context), m.MAX_CONTEXT)

    def test_near_budget_installation_survives_progress_preview_growth(self):
        profiles = {'identity.md': '# Identity\n' + 'i' * 3500 + '\n',
                    'dispositions.md': '# Dispositions\n' + 'd' * 4500 + '\n'}
        plan = m.install(self.root, [], profiles=profiles, replace_profiles=True, dry_run=True)
        self.assertLessEqual(plan['startup_characters'] + 256, m.MAX_CONTEXT)
        m.install(self.root, [], profiles=profiles, replace_profiles=True, expected_plan=plan['plan_id'])
        identifiers = [self.id]
        with self.store.lock():
            for number in range(4):
                identifiers.append(w.start(m, self.store, f'Investigation {number}', 'Synthetic review')['id'])
            initial = m.bootstrap(self.store, 'manual', {})
            self.assertGreater(len(initial), m.MAX_CONTEXT - 3000)
        plan = m.install(self.root, [], dry_run=True)
        self.assertLessEqual(plan['startup_characters'] + 256, m.MAX_CONTEXT)
        with self.store.lock():
            for identifier in identifiers:
                w.update(m, self.store, identifier, None, 'n' * 240,
                         summary_text='s' * 240, notes='Complete saved findings, not a startup preview.')
        saved = {identifier: (w.work_path(m, self.store, identifier) / 'WORK.md').read_bytes()
                 for identifier in identifiers}
        result = self.cli('bootstrap', '--runtime', 'manual')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout), m.MAX_CONTEXT)
        data = json.loads(result.stdout.rstrip().rsplit('\n\n', 1)[1])
        navigation = data['unfinished_work']
        shown = len(navigation['items'])
        self.assertGreater(shown, 0)
        self.assertLess(shown, 5)
        self.assertEqual(navigation['total'], 5)
        self.assertEqual(navigation['remaining'], 5 - shown)
        self.assertEqual(navigation['next_offset'], shown)
        self.assertEqual(navigation['command'], 'work list')
        remainder = w.summary(m, self.store, offset=navigation['next_offset'])
        self.assertEqual({item['id'] for item in navigation['items'] + remainder['items']}, set(identifiers))
        for name, content in profiles.items():
            self.assertEqual(data['profiles'][name]['content'], content)
        self.assertTrue(result.stdout.startswith((self.store.home / 'PERSONALITY.md').read_text(encoding='utf-8')))
        for identifier, content in saved.items():
            self.assertEqual((w.work_path(m, self.store, identifier) / 'WORK.md').read_bytes(), content)
        # Reinstallation preflight must use the same optional-navigation budget.
        before = self.hashes()
        plan = m.install(self.root, [], dry_run=True)
        self.assertLessEqual(plan['startup_characters'] + 256, m.MAX_CONTEXT)
        self.assertEqual(self.hashes(), before)

    def test_installation_still_rejects_oversized_required_content_without_writes(self):
        before = self.hashes()
        profiles = {'identity.md': '# Identity\n' + 'i' * 7000 + '\n',
                    'dispositions.md': '# Dispositions\n' + 'd' * 7000 + '\n'}
        with self.assertRaisesRegex(m.MettleError, 'even without work pointers'):
            m.install(self.root, [], profiles=profiles, replace_profiles=True)
        self.assertEqual(self.hashes(), before)

    def test_bootstrap_can_omit_all_pointers_without_truncating_required_content(self):
        with self.store.lock():
            initial = m.bootstrap(self.store, 'manual', {})
        # Quotes/backslashes expand in JSON; budget the serialized snapshot.
        preview = 'é"\\' * 80
        self.update(summary_text=preview, next_action=preview)
        with mock.patch.object(m, 'MAX_CONTEXT', len(initial)), self.store.lock():
            context = m.bootstrap(self.store, 'manual', {})
        self.assertLessEqual(len(context), len(initial))
        before = json.loads(initial.rsplit('\n\n', 1)[1])
        data = json.loads(context.rsplit('\n\n', 1)[1])
        self.assertEqual(data['profiles'], before['profiles'])
        self.assertEqual(data['directory_map'], before['directory_map'])
        self.assertEqual(data['unfinished_work']['items'], [])
        self.assertEqual(data['unfinished_work']['total'], 1)
        self.assertEqual(data['unfinished_work']['remaining'], 1)
        self.assertEqual(data['unfinished_work']['next_offset'], 0)
        self.assertEqual(data['unfinished_work']['command'], 'work list')
        self.assertEqual(w.read_work(m, self.store, self.id)[0]['summary'], preview)

    def test_reinstallation_preserves_notes_status_and_accepted_state(self):
        self.update(summary_text='A useful partial result.', notes='Incomplete; no conclusion yet.')
        self.update(status='paused', next_action='Wait for the missing input.')
        before = self.path.read_bytes()
        profiles = {p.name: p.read_bytes() for p in self.store.path('personality').iterdir()}
        m.install(self.root, [])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(profiles, {p.name: p.read_bytes() for p in self.store.path('personality').iterdir()})
        self.assertEqual(self.store.snapshot(), ({}, {}))

    def test_older_workspace_without_summary_remains_readable_without_rewrite(self):
        before = self.path.read_bytes()
        self.assertNotIn('summary', w.read_work(m, self.store, self.id)[0])
        self.assertEqual(w.summary(m, self.store)['items'][0]['summary'], '')
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(w.validate(m, self.store)['workspaces'], 1)

    def test_phrase_aware_memory_retrieval_remains_unchanged(self):
        groups = [['source of truth', 'policy']]
        self.assertNotIn('policy', w.query_features(['source'], groups)[1])
        self.assertIn('policy', w.query_features(['source', 'of', 'truth'], groups)[1])
        self.assertNotEqual(w.query_key(['source', 'of', 'truth']), w.query_key(['truth', 'of', 'source']))

    def test_protocol_has_no_obsolete_release_label_and_is_bounded(self):
        text = (Path(m.__file__).parent / 'PERSONALITY.md').read_text(encoding='utf-8')
        self.assertIn(f'Protocol version: **{m.VERSION}**', text)
        self.assertNotRegex(text, r'\bV[0-9]\b')
        self.assertLess(len(text.encode('utf-8')), 12000)
        self.assertIn('Silence, elapsed time', text)
        self.assertIn('no episode, lesson, learning checkpoint', text)

    def test_installer_preserves_authorized_learned_section(self):
        agents = self.root / 'AGENTS.md'
        learned = '\n## Authorized learned guidance\nFixture rule with a lesson reference.\n'
        agents.write_text(agents.read_text(encoding='utf-8') + learned, encoding='utf-8')
        m.install(self.root, [], agents_position='append')
        text = agents.read_text(encoding='utf-8')
        self.assertIn(learned, text)
        self.assertIn('explicitly authorized owned instruction sections', text)
        self.assertNotIn('Learned lessons must not rewrite', text)


if __name__ == '__main__':
    unittest.main()
