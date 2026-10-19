"""Synthetic retrieval and retention contracts; not evidence of model learning."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import mettle as m
import mettle_work as w


class RefinementsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-refinements-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"

    def cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(self.helper), *arguments],
            capture_output=True, encoding="utf-8", timeout=30,
        )

    def record(self, identifier, title, observation="Authored fixture only."):
        meta, body = m.decode(m.template("episode"))
        meta.update(id=identifier, title=title, runtime="synthetic", model="none", session="synthetic-session")
        return m.encode(meta, body.replace("TODO", observation))

    def accept(self, identifier, title, observation="Authored fixture only."):
        with self.store.lock():
            self.store.publish(self.record(identifier, title, observation), None)

    def vocabulary(self, groups):
        m.write_atomic(self.store.path("memory/vocabulary.md"),
                       m.encode({"schema": 1, "groups": groups}, "# Synthetic aliases"))

    def results(self, *query, work_id=None):
        return m.search(self.store, list(query), 50, None, kind="episodes", work_id=work_id)

    def start(self):
        with self.store.lock():
            return w.start(m, self.store, "Read-only fixture investigation", "synthetic component")['id']

    def state_hashes(self, relative="memory"):
        return {p.relative_to(self.store.state).as_posix(): w.sha(p.read_bytes())
                for p in self.store.path(relative).rglob("*") if p.is_file()}

    def test_single_phrase_word_does_not_activate_group(self):
        self.accept("E-policy", "Policy verification")
        for query in (["source"], ["truth"], ["source", "filter", "release"]):
            with self.subTest(query=query):
                self.assertEqual(self.results(*query), [])

    def test_full_phrase_accepts_quoted_or_split_cli_arguments(self):
        self.accept("E-policy", "Policy verification")
        for query in (["source of truth"], ["source", "of", "truth"], ["SOURCE,", "OF\tTRUTH"]):
            with self.subTest(query=query):
                result = self.results(*query)
                self.assertEqual([r['id'] for r in result], ["E-policy"])
                self.assertIn("policy", result[0]['matches'])
        result = self.cli('search', '--kind', 'episodes', 'source', 'of', 'truth')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['candidates'][0]['id'], 'E-policy')

    def test_phrase_keeps_order_adjacency_and_stop_words(self):
        self.accept("E-policy", "Policy verification")
        for query in ("source truth", "truth of source", "source of another truth", "source_of_truth", "source-of-truth"):
            with self.subTest(query=query):
                self.assertEqual(self.results(query), [])

    def test_single_token_alias_remains_case_insensitive_and_whole(self):
        self.accept("E-auth", "Authorization boundaries")
        self.assertEqual(self.results('ACL')[0]['id'], 'E-auth')
        self.assertEqual(self.results('myacl'), [])

    def test_expanded_phrase_requires_whole_phrase_in_record(self):
        self.vocabulary([["policy", "source of truth"]])
        self.accept("E-code", "Source file cleanup")
        self.accept("E-truth", "Truth values")
        self.accept("E-order", "Truth of source")
        self.accept("E-phrase", "Repository evidence", "Inspect the source of truth before a claim.")
        result = self.results('policy')
        self.assertEqual([r['id'] for r in result], ['E-phrase'])
        self.assertEqual(result[0]['matches'], ['source of truth'])

    def test_expansion_does_not_join_separate_metadata_fields(self):
        self.vocabulary([["policy", "source of truth"]])
        meta, body = m.decode(self.record('E-fields', 'source'))
        meta.update(tags=['of truth'])
        with self.store.lock():
            self.store.publish(m.encode(meta, body), None)
        self.assertEqual(self.results('policy'), [])

    def test_expansion_is_not_transitive_between_groups(self):
        self.vocabulary([["alpha", "beta"], ["beta", "gamma"]])
        self.accept('E-beta', 'Beta checks')
        self.accept('E-gamma', 'Gamma checks')
        self.assertEqual([r['id'] for r in self.results('alpha')], ['E-beta'])

    def test_empty_aliases_are_ignored_and_compound_identifiers_preserved(self):
        self.vocabulary([[], ['', '  '], ['acme_source_release', 'lifetime']])
        self.accept('E-release', 'acme_source_release')
        self.assertEqual(self.results('lifetime')[0]['id'], 'E-release')
        self.assertEqual(self.results('release'), [])
        self.assertEqual(self.results('source'), [])

    def test_unicode_phrases_and_whitespace(self):
        self.vocabulary([["ÉTAT de référence", "canonical"]])
        self.accept('E-unicode', 'Canonical record')
        self.assertEqual(self.results('état', 'de', 'référence')[0]['id'], 'E-unicode')
        self.assertEqual(self.results('ÉTAT\tde\nréférence')[0]['id'], 'E-unicode')
        self.assertEqual(self.results('état référence'), [])

    def test_lessons_and_episodes_use_same_phrase_rules(self):
        self.accept('E-origin', 'Authored observation')
        meta, body = m.decode(m.template('lesson'))
        meta.update(id='L-policy', title='Policy verification', origin=['E-origin'], scope=['fixture'])
        with self.store.lock():
            self.store.publish(m.encode(meta, body.replace('TODO', 'Authored fixture only.')), 0)
        self.assertEqual(m.search(self.store, ['source'], 5, None), [])
        self.assertEqual(m.search(self.store, ['source', 'of', 'truth'], 5, None)[0]['id'], 'L-policy')

    def test_phrase_results_keep_each_lessons_own_scope(self):
        self.accept('E-origin', 'Authored observation')
        expected = {'L-first': ['component/one'], 'L-second': ['component/two']}
        for identifier, scope in expected.items():
            meta, body = m.decode(m.template('lesson'))
            meta.update(id=identifier, title='Policy verification', origin=['E-origin'], scope=scope)
            with self.store.lock():
                self.store.publish(m.encode(meta, body.replace('TODO', 'Authored fixture only.')), 0)
        result = m.search(self.store, ['source of truth'], 5, None)
        self.assertEqual({r['id']: r['scope'] for r in result}, expected)

    def test_query_rejection_preserves_phrase_order_and_stop_words(self):
        self.accept('E-source', 'Source inspection')
        identifier = self.start()
        with self.store.lock():
            w.reject_candidate(m, self.store, identifier, 'E-source', ['source', 'of', 'truth'], 'Not applicable here.')
        self.assertEqual(self.results('source of truth', work_id=identifier), [])
        self.assertTrue(self.results('truth of source', work_id=identifier))
        self.assertTrue(self.results('source truth', work_id=identifier))

    def test_legacy_bag_of_words_rejection_is_retained_not_reinterpreted(self):
        self.accept('E-source', 'Source inspection')
        identifier = self.start()
        with self.store.lock():
            meta, body = w.read_work(m, self.store, identifier)
            old = {'record': 'E-source', 'query': 'source truth', 'activity_revision': 1,
                   'reason': 'Legacy unordered query, not evidence about phrase order.', 'at': m.now()}
            meta['rejections'].append(old)
            w.save_work(m, self.store, meta, body)
        manifest = (w.work_path(m, self.store, identifier) / 'WORK.md').read_bytes()
        self.assertTrue(self.results('source of truth', work_id=identifier))
        self.assertEqual(w.read_work(m, self.store, identifier)[0]['rejections'], [old])
        self.assertEqual((w.work_path(m, self.store, identifier) / 'WORK.md').read_bytes(), manifest)

    def test_search_preserves_accepted_records_and_vocabulary(self):
        self.accept('E-source', 'Source file')
        before = self.state_hashes()
        self.results('source')
        self.results('source of truth')
        self.assertEqual(self.state_hashes(), before)

    def test_checkpoint_packet_separates_three_questions_without_writes(self):
        identifier = self.start()
        before = self.state_hashes('work')
        with self.store.lock():
            packet = w.checkpoint(m, self.store, identifier, None, None, [], None)
        self.assertTrue(any(q.startswith('Experience retention:') for q in packet['questions']))
        self.assertTrue(any(q.startswith('Practice learning:') for q in packet['questions']))
        self.assertTrue(any(q.startswith('Self-assessment:') for q in packet['questions']))
        self.assertIn('no-update', packet['note'])
        self.assertIn('episode', packet['note'])
        self.assertEqual(self.state_hashes('work'), before)
        self.assertEqual(self.store.snapshot(), ({}, {}))

    def test_cli_retains_episode_without_creating_lesson_or_self_assessment(self):
        identifier = self.start()
        profiles = self.state_hashes('personality')
        draft_result = self.cli('template', 'episode', '--work', identifier, '--session-id', 'synthetic-retention')
        self.assertEqual(draft_result.returncode, 0, draft_result.stderr)
        path = self.root / json.loads(draft_result.stdout)['draft']
        meta, body = m.decode(m.read(path))
        meta['title'] = 'Observed amberwidget boundary in the inspected revision'
        m.write_atomic(path, m.encode(meta, body.replace('TODO', 'Synthetic inspected result; no local execution or generality claimed.')))
        published = self.cli('publish', str(path))
        self.assertEqual(published.returncode, 0, published.stderr)
        checkpoint = self.cli('work', 'checkpoint', identifier, '--decision', 'no-update',
                              '--reason', 'Retained the useful revision-specific observation; no reusable practice or self-assessment warranted.',
                              '--records', meta['id'])
        self.assertEqual(checkpoint.returncode, 0, checkpoint.stderr)
        closed = self.cli('work', 'update', identifier, '--status', 'closed', '--next-action', 'Review complete.')
        self.assertEqual(closed.returncode, 0, closed.stderr)
        check = self.cli('check')
        self.assertEqual(check.returncode, 0, check.stderr)
        records, lessons = self.store.snapshot()
        self.assertEqual(len(records), 1)
        self.assertEqual(lessons, {})
        self.assertEqual(self.state_hashes('personality'), profiles)
        stored, _ = w.read_work(m, self.store, identifier)
        self.assertEqual(stored['checkpoints'][-1]['records'], [meta['id']])
        self.assertEqual(self.results('amberwidget')[0]['id'], meta['id'])
        self.assertEqual(records[meta['id']][0]['session'], 'synthetic-retention')
        self.assertTrue(path.is_file())

    def test_no_update_may_still_retain_nothing(self):
        identifier = self.start()
        profiles = self.state_hashes('personality')
        with self.store.lock():
            w.checkpoint(m, self.store, identifier, 'no-update', 'Routine inspection supplied no useful new information.', [], None)
            w.update(m, self.store, identifier, 'closed', 'Nothing pending.')
        self.assertEqual(self.store.snapshot(), ({}, {}))
        self.assertEqual(self.state_hashes('personality'), profiles)

    def test_episode_checkpoint_does_not_bypass_existing_record_guards(self):
        identifier = self.start()
        self.accept('E-only', 'Useful observation')
        with self.store.lock():
            for decision, refs in [('no-update', ['E-missing']), ('propose', ['E-only']),
                                   ('review', ['E-only']), ('reconcile', ['E-only'])]:
                with self.subTest(decision=decision), self.assertRaises(m.MettleError):
                    w.checkpoint(m, self.store, identifier, decision, 'A retained episode is not a lesson or review.', refs, None)
        self.assertEqual(w.read_work(m, self.store, identifier)[0]['checkpoints'], [])

    def test_upgrade_preserves_existing_work_profiles_and_custom_vocabulary(self):
        identifier = self.start()
        self.accept('E-kept', 'Existing observation')
        self.vocabulary([["reference phrase", "customalias"]])
        with self.store.lock():
            w.checkpoint(m, self.store, identifier, 'no-update', 'Existing checkpoint.', ['E-kept'], None)
        before = {name: self.state_hashes(name) for name in ['memory', 'work', 'personality']}
        m.write_atomic(self.store.home / 'PERSONALITY.md', '# Earlier installed protocol\nProtocol version: **0.2.0**.\n')
        m.install(self.root, [])
        self.assertEqual({name: self.state_hashes(name) for name in before}, before)
        self.assertIn(f'Protocol version: **{m.VERSION}**', m.read(self.store.home / 'PERSONALITY.md'))


if __name__ == '__main__':
    unittest.main()
