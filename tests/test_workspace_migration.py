"""Migration is tested only on authored disposable state, not real memories."""
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


class MigrationTest(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='mettle-migration-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()
        m.install(self.root,[])
        self.store=m.Store(self.root)
        meta,body=m.decode(m.template('episode'))
        meta.update(id='E-synthetic',title='Authored migration fixture')
        self.text=m.encode(meta,body.replace('TODO','Synthetic content, not experimental evidence.'))
        with self.store.lock():self.accepted=self.root/self.store.publish(self.text,None)
        self.source=self.store.home/'example-review-draft.md'
        self.source.write_bytes(b'\xef\xbb\xbf'+self.text.replace('\n','\r\n').encode('utf-8'))
        self.old_bytes=self.source.read_bytes()

    def hashes(self):
        return {p.relative_to(self.root).as_posix():w.sha(p.read_bytes()) for p in self.root.rglob('*') if p.is_file()}

    def apply(self):
        p=mg.plan(m,self.store)
        result=mg.apply(m,self.store,p['plan_id'])
        return p,result

    def test_preview_has_no_writes_and_identifies_semantic_duplicate(self):
        before=self.hashes();p=mg.plan(m,self.store)
        self.assertEqual(self.hashes(),before)
        entry=next(e for e in p['moves'] if e['source']==self.source.name)
        self.assertEqual(entry['accepted_record'],'E-synthetic')
        self.assertEqual(entry['sha256'],w.sha(self.old_bytes))
        self.assertEqual(list(self.store.path('migrations').glob('*/manifest.json')), [])

    def test_relocation_retains_original_bytes_and_all_accepted_history(self):
        original=self.accepted.read_bytes();profile=self.store.path('personality/identity.md').read_bytes()
        p,result=self.apply()
        self.assertFalse(self.source.exists())
        entry=p['moves'][0]
        self.assertEqual((self.store.home/entry['destination']).read_bytes(),self.old_bytes)
        backup=self.store.path(f"migrations/{p['id']}/originals/{entry['source']}")
        self.assertEqual(backup.read_bytes(),self.old_bytes)
        self.assertEqual(self.accepted.read_bytes(),original)
        self.assertEqual(self.store.path('personality/identity.md').read_bytes(),profile)
        self.assertEqual(len(self.store.snapshot()[0]),1)
        wm,_=w.read_work(m,self.store,p['work_id'])
        self.assertEqual(wm['status'],'paused')
        self.assertEqual(wm['publications'][0]['record'],'E-synthetic')
        self.assertTrue(result['history_unchanged'])

    def test_referenced_draft_stays_at_original_path(self):
        meta,body=m.decode(m.template('episode'));meta.update(id='E-ref',title='Source reference')
        body=body.replace('TODO','See '+self.source.name+' for the earlier material.')
        with self.store.lock():self.store.publish(m.encode(meta,body),None)
        p=mg.plan(m,self.store)
        self.assertEqual(p['moves'],[])
        self.assertTrue(any(e.get('references') for e in p['kept']))
        result=mg.apply(m,self.store,p['plan_id'])
        self.assertEqual(result['status'],'nothing-to-move')
        self.assertEqual(self.source.read_bytes(),self.old_bytes)

    def test_unknown_file_kept_and_unpublished_draft_moved_without_acceptance(self):
        (self.store.home/'custom-policy.md').write_text('Unrecognized operator text.')
        path=self.store.home/'drafts/unpublished.md';path.parent.mkdir();path.write_text('Unfinished TODO notes.')
        before=len(self.store.snapshot()[0]);p,result=self.apply()
        self.assertTrue((self.store.home/'custom-policy.md').exists())
        entry=next(e for e in p['moves'] if e['source']=='drafts/unpublished.md')
        self.assertIsNone(entry['accepted_record'])
        self.assertEqual((self.store.home/entry['destination']).read_text(),'Unfinished TODO notes.')
        self.assertEqual(len(self.store.snapshot()[0]),before)

    def test_backup_moves_to_backup_area_not_memory(self):
        name='tools/mettle.py.mettle-backup-1234abcd'
        (self.store.home/name).write_bytes(b'old helper; never run')
        p,_=self.apply()
        entry=next(e for e in p['moves'] if e['source']==name)
        self.assertTrue(entry['destination'].startswith('state/backups/'))
        self.assertEqual((self.store.home/entry['destination']).read_bytes(),b'old helper; never run')

    def test_changed_plan_fails_before_creating_journal_or_moving_source(self):
        p=mg.plan(m,self.store)
        self.source.write_bytes(self.old_bytes+b'changed')
        before=self.hashes()
        with self.assertRaisesRegex(m.MettleError,'changed'):mg.apply(m,self.store,p['plan_id'])
        self.assertEqual(self.hashes(),before)

    def test_active_writer_blocks_preview(self):
        with self.store.lock(),self.assertRaisesRegex(m.MettleError,'writers'):mg.plan(m,self.store)

    def test_destination_conflict_is_not_overwritten(self):
        p=mg.plan(m,self.store);target=self.store.home/p['moves'][0]['destination'];target.parent.mkdir(parents=True);target.write_bytes(b'other data')
        with self.assertRaises(m.MettleError):mg.apply(m,self.store,p['plan_id'])
        self.assertEqual(target.read_bytes(),b'other data')
        self.assertEqual(self.source.read_bytes(),self.old_bytes)

    def test_interruption_after_copy_recovers_from_original_journal(self):
        p=mg.plan(m,self.store);unlink=Path.unlink
        def interrupt(path,*args,**kwargs):
            if path==self.source:raise OSError('simulated before unlink')
            return unlink(path,*args,**kwargs)
        with mock.patch.object(Path,'unlink',interrupt),self.assertRaises(OSError):mg.apply(m,self.store,p['plan_id'])
        self.assertTrue(self.source.exists())
        with self.assertRaisesRegex(m.MettleError,'incomplete'):mg.plan(m,self.store)
        with self.store.lock():result=mg.resume(m,self.store,p['id'])
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.source.exists())
        with self.store.lock():self.assertEqual(mg.resume(m,self.store,p['id'])['status'],'completed')

    def test_resume_refuses_tampered_destination_or_journal(self):
        p=mg.plan(m,self.store);real=w.save_work
        with mock.patch('mettle_work.save_work',side_effect=OSError('journal finalization interruption')),self.assertRaises(OSError):
            mg.apply(m,self.store,p['plan_id'])
        dest=self.store.home/p['moves'][0]['destination'];dest.write_bytes(b'changed after interruption')
        with self.store.lock(),self.assertRaisesRegex(m.MettleError,'differs'):mg.resume(m,self.store,p['id'])
        dest.write_bytes(self.old_bytes)
        jp=mg.journal_path(m,self.store,p['id']);j=json.loads(jp.read_text());j['plan']['moves'][0]['destination']='state/personality/identity.md';jp.write_text(json.dumps(j))
        with self.store.lock(),self.assertRaises(m.MettleError):mg.resume(m,self.store,p['id'])

    def test_restore_is_preview_first_and_never_deletes_newer_work(self):
        p,_=self.apply();before=self.hashes()
        view=mg.restore(m,self.store,p['id'],False)
        self.assertFalse(view['writes']);self.assertEqual(self.hashes(),before)
        dest=self.store.home/p['moves'][0]['destination'];dest.write_bytes(b'new work at migrated path')
        with self.store.lock():mg.restore(m,self.store,p['id'],True)
        self.assertEqual(self.source.read_bytes(),self.old_bytes)
        self.assertEqual(dest.read_bytes(),b'new work at migrated path')
        with self.store.lock():self.assertEqual(mg.restore(m,self.store,p['id'],True)['status'],'restored')

    def test_restore_refuses_new_content_at_original_path(self):
        p,_=self.apply();self.source.write_bytes(b'new original-path work')
        with self.store.lock(),self.assertRaisesRegex(m.MettleError,'different content'):mg.restore(m,self.store,p['id'],True)
        self.assertEqual(self.source.read_bytes(),b'new original-path work')

    def test_symlink_in_candidate_tree_is_rejected(self):
        p=self.store.home/'drafts';p.mkdir()
        try:(p/'redirect').symlink_to(self.root,target_is_directory=True)
        except OSError as e:self.skipTest(f'Symlink capability unavailable: {e}')
        with self.assertRaises(m.MettleError):mg.plan(m,self.store)

    def test_migration_cli_requires_reviewed_plan(self):
        helper=self.store.home/'tools/mettle.py'
        missing=subprocess.run([sys.executable,str(helper),'migrate-work','--apply'],capture_output=True)
        self.assertEqual(missing.returncode,1)
        before=self.hashes()
        view=subprocess.run([sys.executable,str(helper),'migrate-work'],capture_output=True)
        self.assertEqual(view.returncode,0,view.stderr)
        self.assertEqual(self.hashes(),before)
        data=json.loads(view.stdout);self.assertFalse(data['writes']);self.assertNotIn('guards',data)

    def test_private_git_metadata_untouched(self):
        git=self.store.home/'.git';git.mkdir();(git/'config').write_bytes(b'do not execute or modify');before=(git/'config').read_bytes()
        self.apply()
        self.assertEqual((git/'config').read_bytes(),before)

    def test_non_utf8_reference_input_stops_instead_of_being_silently_ignored(self):
        (self.store.home/'notes.txt').write_bytes(b'\xfflegacy encoding')
        with self.assertRaisesRegex(m.MettleError,'non-UTF-8'):mg.plan(m,self.store)
        self.assertTrue(self.source.exists())


if __name__=='__main__':unittest.main()
