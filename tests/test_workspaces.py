"""Synthetic workspace/retrieval contracts, not evidence of LLM learning."""
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
import mettle_work as w


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="mettle-work-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        m.install(self.root, [])
        self.store = m.Store(self.root)
        self.helper = self.store.home / "tools/mettle.py"

    def cli(self, *args, **kwargs):
        return subprocess.run([sys.executable, "-X", "utf8", str(self.helper), *args],
                              capture_output=True, timeout=30, **kwargs)

    def start(self):
        with self.store.lock():
            return w.start(m, self.store, "Verify generator output", "components/generator")['id']

    def record(self, kind, identifier, **fields):
        meta, body = m.decode(m.template(kind))
        meta.update(id=identifier, title="Generator output")
        meta.update(fields)
        return m.encode(meta, body.replace("TODO", "Synthetic observation; inspect actual evidence before generalizing."))

    def accept(self, kind="episode", identifier="E-example", **fields):
        text = self.record(kind, identifier, **fields)
        with self.store.lock():
            return self.store.publish(text, 0 if kind == "lesson" else None)

    def draft(self, identifier):
        with self.store.lock():
            result = w.make_draft(m, self.store, identifier, self.record("episode", "E-draft"))
        return self.root / result['draft']

    def test_start_does_not_create_personality_or_history(self):
        identifier = self.start()
        self.assertEqual(self.store.snapshot(), ({}, {}))
        meta, _ = w.read_work(m, self.store, identifier)
        self.assertEqual(meta['status'], 'open')
        self.assertFalse((w.work_path(m, self.store, identifier)/'drafts').exists())
        self.assertIn(identifier, self.store.path('work/INDEX.md').read_text())

    def test_workspace_ids_reject_traversal(self):
        for identifier in ['../x', 'W-x/..', 'W-CON', 'C:work']:
            with self.assertRaises(m.MettleError):
                w.work_path(m, self.store, identifier)

    def test_bootstrap_session_and_compact_work_navigation(self):
        ids = [self.start() for _ in range(7)]
        with self.store.lock():
            output = m.bootstrap(self.store, 'codex', {'source':'compact','session_id':'real-hook-id'})
        data = json.loads(output.rsplit('\n\n',1)[1])
        self.assertEqual(data['session_id'], 'real-hook-id')
        self.assertEqual(len(data['unfinished_work']['items']),5)
        self.assertEqual(data['unfinished_work']['remaining'],2)
        self.assertNotIn('checkpoints', data['unfinished_work']['items'][0])
        self.assertLess(len(output),m.MAX_CONTEXT)

    def test_cli_template_fills_work_and_explicit_provenance(self):
        identifier = self.start()
        result = self.cli('template','episode','--work',identifier,'--session-id','session-é', '--runtime','codex','--model','known-test-model')
        self.assertEqual(result.returncode,0,result.stderr)
        draft = self.root/json.loads(result.stdout)['draft']
        meta,_ = m.decode(draft.read_text(encoding='utf-8'))
        self.assertEqual(meta['session'],'session-é')
        self.assertEqual(meta['provenance']['work_id'],identifier)
        self.assertEqual(meta['provenance']['protocol_version'],m.VERSION)
        self.assertTrue(draft.is_relative_to(self.store.path('work')))
        self.assertFalse(list(self.store.home.glob('E-*.md')))

    def test_provenance_never_borrows_another_session_audit(self):
        with self.store.lock():
            m.bootstrap(self.store,'codex',{'session_id':'other-session'})
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(w.provenance(m,self.store)['session'],'unknown')
        with mock.patch.dict(os.environ, {'CODEX_THREAD_ID':'env-thread'}):
            self.assertEqual(w.provenance(m,self.store)['session'],'env-thread')
            self.assertEqual(w.provenance(m,self.store,'explicit')['session'],'explicit')

    def test_output_rejects_stable_managed_directories(self):
        for rel in ['new-draft.md','tools/new.md','state/personality/new.md','state/memory/episodes/new.md','drafts/old-style.md']:
            result=self.cli('template','episode','--output',str(self.store.home/rel))
            self.assertNotEqual(result.returncode,0)
            self.assertFalse((self.store.home/rel).exists())
        result=self.cli('template','episode','--output',str(self.root/'external-draft.md'))
        self.assertEqual(result.returncode,0,result.stderr)

    def test_publish_records_exact_link_and_retry_is_idempotent(self):
        identifier=self.start(); draft=self.draft(identifier)
        with self.store.lock():
            path=w.publish(m,self.store,draft,None)
            self.assertEqual(w.publish(m,self.store,draft,None),path)
        self.assertTrue(draft.is_file())
        meta,_=w.read_work(m,self.store,identifier)
        self.assertEqual(len(meta['publications']),1)
        self.assertEqual(meta['publications'][0]['accepted_sha256'],w.sha((self.root/path).read_bytes()))
        self.assertEqual(len(self.store.snapshot()[0]),1)

    def test_publication_ledger_failure_can_be_recovered(self):
        identifier=self.start();draft=self.draft(identifier)
        with self.store.lock(),mock.patch('mettle_work.save_work',side_effect=OSError('simulated ledger failure')):
            with self.assertRaises(OSError):w.publish(m,self.store,draft,None)
        self.assertIn('E-draft',self.store.snapshot()[0])
        with self.store.lock():w.publish(m,self.store,draft,None)
        self.assertEqual(len(w.read_work(m,self.store,identifier)[0]['publications']),1)

    def test_conflicting_same_id_is_not_accepted_as_retry(self):
        identifier=self.start();draft=self.draft(identifier)
        with self.store.lock():w.publish(m,self.store,draft,None)
        draft.write_text(draft.read_text()+'\nChanged claim.\n',encoding='utf-8')
        with self.store.lock(),self.assertRaisesRegex(m.MettleError,'different content'):
            w.publish(m,self.store,draft,None)
        self.assertNotIn('Changed claim',self.store.snapshot()[0]['E-draft'][1])

    def test_legacy_duplicate_publication_still_rejected(self):
        text=self.record('episode','E-one');draft=self.root/'external.md';draft.write_text(text)
        with self.store.lock():w.publish(m,self.store,draft,None)
        with self.store.lock(),self.assertRaises(m.MettleError):w.publish(m,self.store,draft,None)

    def test_close_requires_current_checkpoint(self):
        identifier=self.start()
        with self.store.lock(),self.assertRaises(m.MettleError):w.update(m,self.store,identifier,'closed',None)
        with self.store.lock():
            w.checkpoint(m,self.store,identifier,'no-update','No reusable result occurred.',[],None)
            w.update(m,self.store,identifier,'closed','No pending work.')
            w.update(m,self.store,identifier,'open','A new situation is available.')
            with self.assertRaises(m.MettleError):w.update(m,self.store,identifier,'closed',None)

    def test_unpublished_or_changed_draft_blocks_close_but_not_pause(self):
        identifier=self.start();draft=self.draft(identifier)
        with self.store.lock():
            w.checkpoint(m,self.store,identifier,'defer','Investigation incomplete.',[],'Next generator change')
            with self.assertRaisesRegex(m.MettleError,'draft'):w.update(m,self.store,identifier,'closed',None)
            w.update(m,self.store,identifier,'paused','Finish observation.')
        self.assertTrue(draft.exists())

    def test_checkpoint_can_link_proposed_practice_without_general_proof(self):
        identifier=self.start();self.accept()
        self.accept('lesson','L-proposed',origin=['E-example'],scope=['generator'])
        with self.store.lock():
            decision=w.checkpoint(m,self.store,identifier,'propose','Bounded candidate; portability untested.',['L-proposed@1'],None)
            w.update(m,self.store,identifier,'closed','Wait for a relevant future application.')
        self.assertEqual(decision['decision'],'propose')
        self.assertEqual(self.store.snapshot()[1]['L-proposed'][0][0]['status'],'proposed')

    def test_checkpoint_requires_revisit_or_actual_published_records(self):
        identifier=self.start()
        with self.store.lock():
            for decision in ['propose','review','reconcile','defer']:
                with self.subTest(decision=decision),self.assertRaises(m.MettleError):
                    w.checkpoint(m,self.store,identifier,decision,'A statement alone is not execution.',[],None)

    def test_evidence_copy_is_content_addressed_and_does_not_execute(self):
        identifier=self.start();folder=w.work_path(m,self.store,identifier)/'artifacts';folder.mkdir()
        path=folder/'unsafe.py';data=b'raise SystemExit("must not execute")\r\n';path.write_bytes(data)
        with self.store.lock():
            result=w.evidence(m,self.store,identifier,path)
            second=w.evidence(m,self.store,identifier,path)
        self.assertEqual(result,second)
        self.assertEqual((self.root/result['path']).read_bytes(),data)
        self.assertEqual(self.store.snapshot(),({},{}))
        with self.store.lock(),self.assertRaises(m.MettleError):w.evidence(m,self.store,identifier,self.root/'elsewhere.txt')

    def test_accepted_episode_fallback_excludes_drafts_and_shows_corrections(self):
        self.accept(identifier='E-original',title='Widget token verification')
        self.accept(identifier='E-correction',title='Widget correction',corrects=['E-original'])
        identifier=self.start();self.draft(identifier)
        matches=m.search(self.store,['widget'],5,None,kind='episodes')
        self.assertEqual({r['id'] for r in matches},{'E-original','E-correction'})
        original=next(r for r in matches if r['id']=='E-original')
        self.assertEqual(original['corrected_by'],['E-correction'])
        self.assertEqual(original['status'],'observation-not-instruction')
        self.assertEqual(m.search(self.store,['widget'],5,None),[])

    def test_whole_tokens_prevent_incidental_matches(self):
        self.accept();text=self.record('lesson','L-tests',title='Validation of performance',scope=['optimizer'],origin=['E-example'])
        with self.store.lock():self.store.publish(text,0)
        self.assertEqual(m.search(self.store,['id','form'],5,None),[])
        self.assertEqual(m.search(self.store,['GameSelector','test'],5,None),[])
        self.assertEqual(m.search(self.store,['performance'],5,None)[0]['id'],'L-tests')

    def test_aliases_remain_useful(self):
        self.accept();self.accept('lesson','L-auth',title='Verify authorization boundaries',origin=['E-example'],scope=['authorization'])
        self.assertEqual(m.search(self.store,['acl'],5,None)[0]['id'],'L-auth')

    def test_rejection_suppresses_only_exact_query_and_activity_revision(self):
        identifier=self.start();self.accept();self.accept('lesson','L-generator',scope=['generator'],origin=['E-example'])
        with self.store.lock():w.reject_candidate(m,self.store,identifier,'L-generator@1',['generator'],'This occurrence is not generated.')
        self.assertEqual(m.search(self.store,['generator'],5,None,work_id=identifier),[])
        self.assertTrue(m.search(self.store,['generator'],5,None))
        self.assertTrue(m.search(self.store,['generator','output'],5,None,work_id=identifier))
        with self.store.lock():
            w.update(m,self.store,identifier,'paused','Return after scope changes.')
            w.update(m,self.store,identifier,'open','New situation.')
        self.assertTrue(m.search(self.store,['generator'],5,None,work_id=identifier))

    def test_installer_keeps_handoff_and_internal_backups_out_of_package_root(self):
        identifier=self.start();workfile=w.work_path(m,self.store,identifier)/'WORK.md';before=workfile.read_bytes()
        (self.store.home/'PERSONALITY.md').write_text('# Older protocol\n',encoding='utf-8')
        result=m.install(self.root,[])
        self.assertEqual(before,workfile.read_bytes())
        backups=[p for p in result['backups'] if 'PERSONALITY.md' in p]
        self.assertEqual(len(backups),1)
        self.assertIn('/state/backups/',backups[0])
        self.assertEqual((self.root/backups[0]).read_text(),'# Older protocol\n')
        self.assertFalse(list(self.store.home.glob('*.mettle-backup-*')))

    def test_fresh_process_resume_and_dry_run_preserve_work(self):
        identifier=self.start();before=(w.work_path(m,self.store,identifier)/'WORK.md').read_bytes()
        result=self.cli('work','show',identifier)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['work']['id'],identifier)
        self.assertEqual(self.cli('install','--configure-only','--non-interactive','--dry-run','--runtimes').returncode,0)
        self.assertEqual((w.work_path(m,self.store,identifier)/'WORK.md').read_bytes(),before)


if __name__=='__main__':unittest.main()
