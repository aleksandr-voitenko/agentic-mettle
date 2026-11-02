"""Authored synthetic workflows, not evidence of autonomous model judgment."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import mettle as m
import mettle_catalogue as c
import mettle_consolidate as consolidation
import mettle_work as w
from examples.scalability_fixture import put, record


class ConsolidationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="mettle-consolidation-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        (self.root / "AGENTS.md").write_text("# Existing mandate\n", encoding="utf-8")
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"
        with self.store.lock():
            self.work = w.start(m, self.store, "Compare cache freshness", "demo cache")['id']

    def text(self, kind, identifier, prose="Synthetic fixture; no real experiment occurred.", **fields):
        meta, body = m.decode(m.template(kind))
        meta.update(id=identifier, title=prose[:100])
        meta.update(fields)
        return m.encode(meta, body.replace("TODO", prose))

    def publish(self, text, expected=None, activity=None):
        with self.store.lock():
            draft = w.make_draft(m, self.store, activity or self.work, text)
            return self.root / w.publish(m, self.store, self.root / draft['draft'], expected)

    def episode(self, identifier, prose="Authored cache observation", **fields):
        return self.publish(self.text("episode", identifier, prose, **fields))

    def lesson(self, identifier="L-cache", origin="E-origin", **fields):
        defaults = dict(domain="engineering", scope=["demo cache"], origin=[origin], tags=["cache"], aliases=["freshness"])
        defaults.update(fields)
        return self.publish(self.text("lesson", identifier, "Reuse cached input in the declared scope", **defaults), 0)

    def initial(self):
        self.episode("E-origin", "Immutable inputs supported reuse in this authored case")
        return self.lesson()

    def review(self, identifier, episode, assessment, revision=1, lesson="L-cache"):
        return self.publish(self.text("review", identifier, f"Authored {assessment}; see the exact conditions and source",
                           lesson=lesson, lesson_revision=revision, episodes=[episode], assessment=assessment))

    def reconcile(self, identifier, revision=1, evidence=(), operation="REVISE", lesson="L-cache"):
        return self.publish(self.text("reconciliation", identifier, "Intent only: inspect actual published outputs",
                           operation=operation, inputs=[f"{lesson}@{revision}"], evidence=list(evidence)))

    def revise(self, reconciliation, prose=None, identifier="L-cache", expected=None, **fields):
        with c.open_catalogue(m, self.store) as cat:
            meta, body, _ = cat.get(identifier)
        meta = copy.deepcopy(meta)
        old = meta['revision']
        meta.update(revision=old + 1, reconciliations=[*meta['reconciliations'], reconciliation], **fields)
        if prose:
            body = "\n\n".join(f"## {section}\n{prose}" for section in m.SECTIONS['lesson'])
        return self.publish(m.encode(meta, body), old if expected is None else expected)

    def packet(self, refs=(), query=(), limit=12, offset=0, activity=None):
        with self.store.lock():
            return consolidation.packet(m, self.store, activity or self.work, refs, query, limit, offset)

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args],
                              capture_output=True, encoding="utf-8", timeout=30, cwd=self.root)

    def protected(self):
        # Include work ledgers/drafts, vocabulary, profiles, instructions, accepted
        # and derived Markdown: the packet may only maintain its disposable cache.
        return {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()
                and "state/memory/catalogue.sqlite3" not in p.as_posix()}

    def test_seeds_cross_activity_query_and_read_only(self):
        self.initial()
        with self.store.lock():
            later = w.start(m, self.store, "Later observation", "mutable inputs")['id']
        self.publish(self.text("episode", "E-later", "Later cache freshness finding"), activity=later)
        self.review("V-counter", "E-later", "counterexample")
        before = self.protected()
        packet = self.packet(activity=later, query=["freshness"])
        refs = {item['ref']: item for item in packet['items']}
        self.assertIn("E-later", packet['seeds'])
        self.assertIn("L-cache@1", refs)  # Operator did not supply the lesson ID.
        self.assertIn("V-counter", refs)
        self.assertIn("pending", refs['V-counter']['reason'])
        self.assertEqual(self.protected(), before)
        empty = self.packet(refs=['E-later'], query=['unrelatedterm'])
        self.assertIn("L-cache@1", {i['ref'] for i in empty['items']})  # Direct link wins.

    def test_narrowing_preserves_history_and_counterevidence(self):
        original = self.initial()
        original_bytes = original.read_bytes()
        self.episode("E-counter", "Mutable cache input changed; the old wording overgeneralized")
        self.review("V-counter", "E-counter", "counterexample")
        self.assertIn('V-counter', {i['ref'] for i in self.packet(['L-cache'])['items']})
        self.reconcile("C-narrow", evidence=['V-counter'])
        self.revise("C-narrow", "Reuse only immutable cache inputs; recheck mutable ones", scope=['immutable input'], counterevidence=['V-counter'])
        hits = m.search(self.store, ['cache'], 5, None)
        self.assertEqual([(h['id'], h['revision'], h['status']) for h in hits], [('L-cache', 2, 'proposed')])
        self.assertEqual(hits[0]['pending_counterevidence'], [])
        packet = self.packet(['L-cache@1'])
        old = next(i for i in packet['items'] if i['ref'] == 'L-cache@1')
        self.assertFalse(old['current_candidate'])
        self.assertEqual(old['latest_revision'], 2)
        self.assertTrue(old['path'].endswith('/revisions/0001.md'))
        self.assertEqual('incorporated', next(i for i in packet['items'] if i['ref'] == 'V-counter')['counterevidence_state'])
        self.assertEqual(original.read_bytes(), original_bytes)
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'reconcile', 'Narrowed after comparison', ['C-narrow', 'L-cache@2'], None)
            self.store.snapshot()

    def test_outside_scope_retains_practice_without_fabricating_support(self):
        original = self.initial()
        before = original.read_bytes()
        self.episode('E-outside', 'Mutable production inputs differ from the immutable sandbox scope')
        self.review('V-outside', 'E-outside', 'not_applied')
        packet = self.packet(['E-outside'])
        self.assertIn('L-cache@1', {i['ref'] for i in packet['items']})
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'review', 'Case outside scope; retain, no effectiveness claim', ['V-outside'], None)
            records, lessons = self.store.snapshot()
        self.assertEqual(len(lessons['L-cache']), 1)
        self.assertEqual(lessons['L-cache'][0][0]['support'], [])
        self.assertFalse(any(r[0]['kind'] == 'reconciliation' for r in records.values()))
        self.assertEqual(original.read_bytes(), before)

    def test_subject_correction_no_practice_or_profile_change(self):
        profiles = {p: p.read_bytes() for p in self.store.path('personality').glob('*.md')}
        self.episode('E-subject', 'A reported source implied that the sample came from the production population')
        self.episode('E-correction', 'Inspected source: sample was sandbox only; observation remains valid there', corrects=['E-subject'])
        packet = self.packet(['E-subject'])
        self.assertIn('E-correction', {i['ref'] for i in packet['items']})
        self.assertEqual(packet['omissions']['counterevidence_known'], 1)
        hit = m.search(self.store, ['population'], 5, None, 'episodes')[0]
        self.assertEqual(hit['corrected_by'], ['E-correction'])
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'no-update', 'Useful subject correction retained; no procedure or trait inference', ['E-correction'], None)
            self.assertEqual(self.store.snapshot()[1], {})
        self.assertEqual({p: p.read_bytes() for p in profiles}, profiles)

    def test_merge_preserves_handles_and_does_not_inflate_support(self):
        self.initial()
        self.lesson('L-other', aliases=['unchanging source'])
        self.lesson('L-merged', supersedes=['L-cache', 'L-other'], aliases=['freshness', 'unchanging source'])
        for old in ('L-cache', 'L-other'):
            self.reconcile('C-' + old, operation='MERGE', lesson=old)
            self.revise('C-' + old, identifier=old, status='superseded', superseded_by=['L-merged'])
        packet = self.packet(['L-cache@1'], limit=30)
        refs = {i['ref']: i for i in packet['items']}
        self.assertIn('L-merged@1', refs)
        self.assertEqual(refs['L-cache@1']['latest_status'], 'superseded')
        self.assertFalse(refs['L-cache@2']['current_candidate'])
        hits = m.search(self.store, ['freshness'], 5, None)
        self.assertEqual([i['id'] for i in hits], ['L-merged'])
        records, lessons = self.store.snapshot()
        self.assertEqual(lessons['L-merged'][-1][0]['origin'], ['E-origin'])
        self.assertEqual(lessons['L-merged'][-1][0]['support'], [])
        self.assertEqual(lessons['L-merged'][-1][0]['status'], 'proposed')

    def test_retired_wording_historical_discovery_and_exact_status(self):
        self.initial()
        self.reconcile('C-retire', operation='RETIRE')
        self.revise('C-retire', 'Obsolete after a changed component', status='retired', tags=[], aliases=[])
        self.assertEqual(m.search(self.store, ['freshness'], 5, None), [])
        self.episode('E-unlinked', 'Unrelated later observation')
        packet = self.packet(['E-unlinked'], ['freshness'])
        items = {i['ref']: i for i in packet['items']}
        self.assertIn('L-cache@1', items)
        self.assertEqual(items['L-cache@1']['latest_status'], 'retired')
        self.assertFalse(items['L-cache@1']['current_candidate'])
        self.assertEqual(items['L-cache@2']['status'], 'retired')
        history = m.search(self.store, ['freshness'], 5, None, history=True)
        self.assertEqual(history[0]['revision'], 1)

    def test_peer_repetition_does_not_activate(self):
        self.initial()
        for identifier in ['E-peer', 'E-repeat']:
            self.episode(identifier, 'Reported by peer P citing source S; not inspected or reproduced; shared source, independence unknown')
        packet = self.packet(['E-peer', 'E-repeat'], ['cache'])
        self.assertIn('L-cache@1', {i['ref'] for i in packet['items']})
        self.assertIn('lexical candidate', next(i for i in packet['items'] if i['ref'] == 'L-cache@1')['reason'])
        meta = self.store.snapshot()[1]['L-cache'][-1][0]
        self.assertEqual((meta['status'], meta['support'], meta['revision']), ('proposed', [], 1))

    def test_defer_fresh_process_resume_without_lesson(self):
        self.episode('E-deferred', 'Reported exception; source details unavailable')
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'defer', 'Need the source conditions', ['E-deferred'], 'When source details become available')
            w.update(m, self.store, self.work, 'paused', 'Inspect source when available', notes='Question: different scope? E-deferred. No lesson or applied change; source details pending.')
        result = self.cli('work', 'consolidate', self.work, '--records', 'E-deferred')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['seeds'], ['E-deferred'])
        self.assertEqual(self.cli('work', 'update', self.work, '--status', 'open').returncode, 0)
        self.episode('E-resolved', 'Source inspected: different subject population, retain finding only')
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'no-update', 'Comparison resolved; no practice change warranted', ['E-resolved'], None)
            w.update(m, self.store, self.work, 'closed', 'None; comparison complete')
        self.assertEqual(self.store.snapshot()[1], {})

    def test_stale_revision_rejected_after_packet_and_unapplied_plan(self):
        self.initial()
        packet = self.packet(['L-cache'])
        self.assertIn('L-cache@1', packet['seeds'])
        self.reconcile('C-first')
        packet = self.packet(['C-first'])
        self.assertEqual(next(i for i in packet['items'] if i['ref'] == 'C-first')['status'], 'intent-not-proof-of-publication')
        with self.store.lock(), self.assertRaisesRegex(m.MettleError, 'published lesson revision'):
            w.checkpoint(m, self.store, self.work, 'reconcile', 'Cannot claim completion', ['C-first'], None)
        self.revise('C-first', status='contested')
        self.reconcile('C-later', revision=2)
        with self.assertRaises(m.MettleError):
            self.revise('C-later', expected=1)
        refreshed = self.packet(['L-cache'])
        latest = next(i for i in refreshed['items'] if i['ref'] == 'L-cache@2')
        self.assertEqual(latest['status'], 'contested')
        self.assertEqual(w.read_work(m, self.store, self.work)[0]['checkpoints'], [])

    def test_bounds_pagination_explicit_and_counterevidence_omissions(self):
        self.initial()
        for number in range(14):
            self.episode(f'E-counter-{number}', '界' * 600)
            self.review(f'V-counter-{number}', f'E-counter-{number}', 'counterexample')
        first = self.packet(['E-origin', 'L-cache@1'], limit=1)
        self.assertEqual(first['omissions']['explicit_not_on_page'], ['L-cache@1'])
        self.assertEqual(first['omissions']['counterevidence_not_on_page'], 14)
        seen, offset = [], 0
        while True:
            page = self.packet(['E-origin', 'L-cache@1'], limit=3, offset=offset)
            self.assertLessEqual(len(consolidation.serialized(page).encode()), consolidation.MAX_BYTES)
            self.assertLessEqual(len(page['items']), 3)
            seen.extend(i['ref'] for i in page['items'])
            if page['next_argv'] is None:
                break
            offset = int(page['next_argv'][-1])
            executed = self.cli(*page['next_argv'])
            self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(len(seen), first['total_selected'])
        self.assertTrue({f'V-counter-{n}' for n in range(14)} <= set(seen))
        self.assertEqual(self.packet(['E-origin'], offset=999)['items'], [])

    def test_long_unicode_metadata_adaptive_preview_and_lexical_continuation(self):
        self.episode('E-origin')
        for n in range(8):
            self.lesson(f'L-{n}', domain='-legacy', scope=['界' * 2000], title='界' * 2000)
        packet = self.packet(['E-origin'], ['cache'], limit=30)
        self.assertGreater(packet['omissions']['lexical_matches'], 0)
        more = self.cli(*packet['omissions']['lexical_next_argv'])
        self.assertEqual(more.returncode, 0, more.stderr)
        self.assertLessEqual(len(consolidation.serialized(packet).encode()), consolidation.MAX_BYTES)
        self.assertTrue(any(i.get('preview', {}).get('shortened') for i in packet['items']))
        self.assertEqual(self.packet(['E-origin'], ['cache'], 30), packet)

    def test_invalid_references_limits_and_empty_results(self):
        for ref in ['../E-x', 'E-none', 'E-x@1', 'L-x@0', 'L-x@2', 'l-x']:
            with self.subTest(ref=ref), self.assertRaises(m.MettleError):
                self.packet([ref])
        for limit, offset in [(0, 0), (31, 0), (1, -1)]:
            with self.assertRaises(m.MettleError):
                self.packet(limit=limit, offset=offset)
        with self.assertRaises(m.MettleError):
            self.packet(['E-x'] * 9)
        with self.assertRaises(m.MettleError):
            self.packet(query=['界' * 1000])
        self.assertEqual(self.packet(query=['unmatched'])['items'], [])
        self.assertEqual(self.packet()['seeds'], [])

    def test_adaptive_and_unrenderable_paths_preserve_exact_references(self):
        self.initial()
        original = c.Catalogue.get
        # Serialization boundary on every OS; native long-path validation is
        # already covered by navigation tests. Real reads still run first.
        length = 13_600
        def long_path(cat, identifier, revision=None):
            meta, body, path = original(cat, identifier, revision)
            if identifier == 'L-cache':
                path = self.store.path('memory') / ('d' * length) / 'L-cache/revisions/0001.md'
                meta = {**meta, 'title': '界' * 1000}
                body = '界' * 1000
            return meta, body, path
        with mock.patch.object(c.Catalogue, 'get', long_path):
            page = self.packet(['L-cache'], limit=1)
            self.assertEqual(page['items'][0]['ref'], 'L-cache@1')
            self.assertNotIn('preview', page['items'][0])
            self.assertIn('d' * length, page['items'][0]['path'])
            length = 16_000
            page = self.packet(['L-cache'], limit=1)
            self.assertEqual(page['items'], [])
            self.assertEqual(page['omissions']['path_exceeds_page'],
                             [{'ref': 'L-cache@1', 'detail_argv': ['show', 'L-cache', '--revision', '1']}])
            self.assertEqual(page['omissions']['explicit_not_on_page'], ['L-cache@1'])
            self.assertEqual(page['next_argv'][-1], '1')
            self.assertLessEqual(len(consolidation.serialized(page).encode()), consolidation.MAX_BYTES)

    def test_extra_activity_seeds_context_omissions_and_hyphen_query(self):
        self.initial()
        for n in range(10):
            self.lesson(f'L-extra-{n}')
        page = self.packet(['E-origin'], ['-cache'])
        self.assertGreater(page['omissions']['lesson_contexts_not_expanded'], 0)
        if page['next_argv']:
            result = self.cli(*page['next_argv'])
            self.assertEqual(result.returncode, 0, result.stderr)
        recent = self.packet()
        self.assertEqual(len(recent['seeds']), 8)
        self.assertEqual(recent['omissions']['older_activity_seeds'], 4)
        history = self.cli(*recent['omissions']['activity_history_argv'])
        self.assertEqual(history.returncode, 0, history.stderr)

    def test_upgrade_preserves_private_material_and_installs_discoverable_guide(self):
        self.initial()
        self.episode('E-pending', 'Subject finding, no profile implication')
        with self.store.lock():
            w.checkpoint(m, self.store, self.work, 'no-update', 'Episode retained', ['E-pending'], None)
            w.update(m, self.store, self.work, 'paused', 'Await applicable opportunity', notes='L-cache@1: comparison pending; E-pending retained.')
        # Compatibility fixture: the preceding protocol version and no new module
        # or guide. Actual 0.4.0 source upgrade is also exercised manually.
        protocol = self.store.home / 'PERSONALITY.md'
        protocol.write_text(protocol.read_text(encoding='utf-8').replace('0.5.0', '0.4.0'), encoding='utf-8')
        (self.store.home / 'tools/mettle_consolidate.py').unlink()
        (self.store.home / 'CONSOLIDATION_REFERENCE.md').unlink()
        (self.root / 'AGENTS.md').write_text('# Mandate\nOwned guidance: inspect scope (L-cache@1).\n', encoding='utf-8')
        vocabulary = self.store.path('memory/vocabulary.md')
        meta, body = m.decode(m.read(vocabulary))
        meta['groups'].append(['cache', 'local cache wording'])
        vocabulary.write_text(m.encode(meta, body), encoding='utf-8')
        paths = [p for p in self.store.state.rglob('*') if p.is_file()
                 and p.name != 'catalogue.sqlite3' and p.name != 'INDEX.md'] + [self.root / 'AGENTS.md']
        before = {p: p.read_bytes() for p in paths}
        m.install(self.root, [])
        self.assertEqual({p: p.read_bytes() for p in paths}, before)
        result = self.cli('work', 'consolidate', self.work, '--query', 'cache')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('CONSOLIDATION_REFERENCE.md', json.loads(result.stdout)['notice'])
        self.assertIn('work consolidate', (self.store.home / 'CONSOLIDATION_REFERENCE.md').read_text(encoding='utf-8'))
        self.assertEqual(self.cli('check').returncode, 0)
        self.assertEqual(self.cli('bootstrap').returncode, 0)

    def test_catalogue_freshness_corruption_and_episode_extensions(self):
        for n, field in enumerate(['scope', 'tags', 'aliases', 'domain']):
            self.episode(f'E-extra-{n}', **{field: None})
        before = self.protected()
        self.assertEqual(len(self.packet([f'E-extra-{n}' for n in range(4)])['items']), 4)
        self.assertEqual(self.protected(), before)
        cache = self.store.path('memory/catalogue.sqlite3')
        cache.write_bytes(b'corrupt disposable catalogue')
        self.assertEqual(self.packet(['E-extra-0'])['seeds'], ['E-extra-0'])
        self.episode('E-new', corrects=['E-extra-0'])
        self.assertIn('E-new', {i['ref'] for i in self.packet(['E-extra-0'])['items']})
        with c.open_catalogue(m, self.store) as cat:
            path = cat.get('E-extra-0')[2]
        path.write_text('malformed canonical record', encoding='utf-8')
        with self.assertRaises(m.MettleError):
            self.packet(['E-extra-0'])

    @unittest.skipIf(os.name == 'nt', 'Native Windows junction/path coverage remains in targeted-access tests')
    def test_redirected_canonical_and_wrong_root_rejected(self):
        path = self.episode('E-source')
        self.packet(['E-source'])
        backup = self.root / 'outside.md'
        backup.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(backup)
        with self.assertRaises(m.MettleError):
            self.packet(['E-source'])
        with self.assertRaises(m.MettleError):
            self.packet(activity='../W-other')

    def test_warm_reads_do_not_decode_unrelated_archive(self):
        self.initial()
        for n in range(500):
            put(self.store, record('episode', f'E-unrelated-{n}', title='Unrelated astronomy', body='Unrelated population'))
        self.store.snapshot()
        self.packet(['E-origin'], ['cache'])  # cold rebuild
        canonical, original = [], m.read
        def read(path):
            if 'revisions' in path.parts or any(part in path.parts for part in m.DIRECTORIES.values()):
                canonical.append(path)
            return original(path)
        with mock.patch.object(m, 'read', side_effect=read), mock.patch.object(m.Store, 'snapshot', wraps=self.store.snapshot) as snapshots, \
             mock.patch.object(c, 'inventory', wraps=c.inventory) as inventory, \
             mock.patch.object(w, 'rank_candidates', wraps=w.rank_candidates) as queries, \
             mock.patch.object(c, 'connect', wraps=c.connect) as connections, \
             mock.patch.object(m, 'write_atomic', wraps=m.write_atomic) as writes:
            packet = self.packet(['E-origin'], ['cache'])
        self.assertEqual(snapshots.call_count, 0)
        self.assertEqual(inventory.call_count, 1)
        self.assertEqual(queries.call_count, 1)
        self.assertEqual(connections.call_count, 1)
        self.assertEqual([call.args[0].name for call in writes.call_args_list], ["owner.json"])
        self.assertFalse(any('E-unrelated' in p.name for p in canonical))
        self.assertEqual(len(canonical), 2)
        self.assertLess(len(consolidation.serialized(packet).encode()), consolidation.MAX_BYTES)


if __name__ == '__main__':
    unittest.main()
