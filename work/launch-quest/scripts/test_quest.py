"""Meaningful invariants for evidence, state, dependencies and read-only transport."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from quest import QUEST, REGISTER, read, validate, project, verify_copy
from source_resolver import SourceResolver, MissingExternalSource, SourceHashMismatch, SourceError

def node_runtime():
    node=os.environ.get('ACCLAM_NODE') or shutil.which('node')
    if not node: raise RuntimeError('Node.js 18+ must be on PATH (or set ACCLAM_NODE)')
    checked=subprocess.run([node,'-p','Number(process.versions.node.split(".")[0]) >= 18'],capture_output=True,text=True)
    if checked.returncode or checked.stdout.strip()!='true':raise RuntimeError('Node.js 18+ required')
    return node

class RegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.original=read(REGISTER)
    def setUp(self): self.r=copy.deepcopy(self.original)
    def task(self,id): return next(t for m in self.r['milestones'] for t in m['objectives'] if t['id']==id)
    def reject(self,text):
        with self.assertRaisesRegex(ValueError,text):validate(self.r,allow_missing_external=True)
    def test_valid_source_bounded_state(self):
        result=validate(self.r,allow_missing_external=True)
        self.assertEqual(result['done'],3)
        self.assertGreaterEqual(result['objectives'],610)
    def test_duplicate_id_rejected(self):
        self.r['milestones'][0]['objectives'][1]['id']='ACA-BASELINE';self.reject('Duplicate task IDs')
    def test_missing_current_rejected(self):
        self.task('ACA-SCHEMA-ALIGN')['status']='upcoming';self.reject('Exactly one current')
    def test_cycle_rejected(self):
        self.task('ACA-BASELINE')['dependencies']=['ACA-SCHEMA-ALIGN'];self.reject('Dependency cycle')
    def test_done_with_open_dependency_rejected(self):
        self.task('ACA-DRAFT-LOCAL')['dependencies'].append('ACA-WIX-INVENTORY');self.reject('done with unfinished')
    def test_done_without_proof_rejected(self):
        self.task('ACA-DRAFT-LOCAL')['proofs']=[];self.reject('done without verifiable proofs')
    def test_hash_mismatch_rejected(self):
        self.task('ACA-DRAFT-LOCAL')['proofs'][0]['sha256']='0'*64;self.reject('evidence hash mismatch')
    def test_typed_assertion_rejected(self):
        self.task('ACA-DRAFT-LOCAL')['proofs'][0]['assertions'][0]['equals']='23';self.reject('typed assertion fails')
    def test_wrong_proof_class_rejected(self):
        self.task('ACA-DRAFT-LOCAL')['proofs'][0]['class']='implementation';self.reject('wrong evidence class')
    def test_source_traversal_rejected(self):
        self.task('ACA-WIX-INVENTORY')['sources'][0]['path']='../AGENTS.md';self.reject('Path escapes workspace')
    def test_baseline_id_cannot_disappear(self):
        self.r['milestones'][-1]['objectives'].pop();self.reject('Baseline objective IDs disappeared')
    def test_history_must_match_status(self):
        self.task('ACA-DRAFT-LOCAL')['history'][-1]['status']='upcoming';self.reject('latest history does not match')
    def test_changed_source_snapshot_rejected(self):
        self.r['sourceSnapshots'][0]['sha256']='0'*64;self.reject('Input changed:')
    def test_malformed_source_snapshot_rejected(self):
        self.r['sourceSnapshots']=['../missing.json'];self.reject('Input snapshot:')
    def test_all_scope_connects_to_release(self):
        index={t['id']:t for m in self.r['milestones'] for t in m['objectives']}
        seen=set()
        def visit(id):
            if id in seen:return
            seen.add(id)
            for dependency in index[id]['dependencies']:visit(dependency)
        visit('ACA-RELEASE-MONITOR')
        self.assertEqual(seen,set(index))
    def test_projection_is_deterministic_and_allowlisted(self):
        a=project(self.r);b=project(copy.deepcopy(self.r));self.assertEqual(a,b)
        self.assertNotIn('proofs',json.dumps(a));self.assertNotIn('inputSnapshots',a)
        self.assertNotIn('sourceSnapshots',a);self.assertNotIn('sourceAuthority',a)
    def test_full_frozen_scope_has_stages(self):
        index={t['id']:t for m in self.r['milestones'] for t in m['objectives']}
        for n in range(1,78):
            for suffix in ['PREP','BUILD','TEST','IMPORT','REVIEW']:self.assertIn(f'ACA-CMS-{n:03}-{suffix}',index)
        for n in range(1,18):
            for suffix in ['BUILD','TEST','REVIEW']:self.assertIn(f'ACA-PAGE-{n:02}-{suffix}',index)
        for n in range(1,21):
            for suffix in ['BUILD','TEST','REVIEW']:self.assertIn(f'ACA-AUT-{n:03}-{suffix}',index)
        self.assertTrue(all(t['phase'] in ['design','preparation'] for t in index.values() if t['status']=='done'))
    def test_snapshot_check_is_readonly_and_explicit(self):
        paths=[REGISTER,QUEST/'dist/progress.json',QUEST/'SOURCE_MAP.json',QUEST/'evidence/REGISTER_VERIFICATION.json',QUEST/'evidence/LOCAL_QA.json']
        before={p:p.read_bytes() for p in paths}
        result=verify_copy()
        self.assertIs(result['fullEvidenceValidation'],False)
        self.assertIs(result['writesPerformed'],False)
        self.assertEqual(before,{p:p.read_bytes() for p in paths})
    def test_strict_evidence_check_remains_strict(self):
        if os.environ.get('ACCLAM_SOURCE_ROOT'):
            result=validate(self.r);self.assertEqual(result['verifiedProofs'],4)
        else:
            with self.assertRaisesRegex(ValueError,'Private dependency unavailable'):validate(self.r)
    def test_copy_validation_does_not_hide_unlisted_missing_files(self):
        self.task('ACA-WIX-INVENTORY')['sources'][0]['path']='unlisted/missing.txt'
        self.reject('Missing file: unlisted/missing.txt')

class SourceResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.repo=self.base/'repo';self.repo.mkdir();self.attached=self.base/'attached';self.attached.mkdir()
        self.source=self.attached/'private.txt';self.source.write_text('pinned source',encoding='utf-8')
        self.manifest=self.repo/'manifest.json';self.manifest.write_text(json.dumps({'schemaVersion':1,'files':[{'path':'private.txt','sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),'reason':'private_client_source'}]}),encoding='utf-8')
    def tearDown(self):self.temp.cleanup()
    def resolver(self,attached=True):return SourceResolver(self.repo,self.manifest,self.attached if attached else None)
    def test_only_pinned_paths_can_fall_back_to_attachment(self):
        self.assertEqual(self.resolver().resolve('private.txt'),self.source.resolve())
        (self.attached/'secret.txt').write_text('never resolve',encoding='utf-8')
        with self.assertRaisesRegex(SourceError,'Missing file:'):self.resolver().resolve('secret.txt')
    def test_missing_attachment_is_explicit(self):
        with self.assertRaises(MissingExternalSource):self.resolver(False).resolve('private.txt')
    def test_attached_source_hash_is_required(self):
        self.source.write_text('changed',encoding='utf-8')
        with self.assertRaises(SourceHashMismatch):self.resolver().resolve('private.txt')
    def test_absolute_and_traversal_paths_rejected(self):
        for value in ['../private.txt','/private.txt','C:/private.txt','a/../private.txt','a\\private.txt','a//file']:
            with self.subTest(value=value), self.assertRaises(SourceError):self.resolver().resolve(value)
    def test_symlink_cannot_escape_attachment(self):
        outside=self.base/'outside.txt';outside.write_text('outside',encoding='utf-8')
        self.source.unlink()
        try:self.source.symlink_to(outside)
        except OSError:self.skipTest('This OS user cannot create symbolic links')
        with self.assertRaisesRegex(SourceError,'symbolic link'):self.resolver().resolve('private.txt')

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.base=Path(cls.temp.name)
        cls.root=cls.base/'work'/'launch-quest';cls.root.mkdir(parents=True)
        (cls.root/'dist').mkdir();(cls.root/'evidence').mkdir()
        shutil.copyfile(QUEST/'server.mjs',cls.root/'server.mjs')
        shutil.copyfile(QUEST/'source-resolver.mjs',cls.root/'source-resolver.mjs')
        cls.attachment=cls.base/'attachment';(cls.attachment/'private').mkdir(parents=True)
        cls.attached=cls.attachment/'private/source.txt';cls.attached.write_text('private pinned evidence',encoding='utf-8')
        manifest={'schemaVersion':1,'files':[{'path':p,'sha256':hashlib.sha256(cls.attached.read_bytes()).hexdigest(),'reason':'private_client_source'} for p in ['private/source.txt','private/missing.txt']]}
        (cls.root/'EXTERNAL_SOURCES.json').write_text(json.dumps(manifest),encoding='utf-8')
        cls.register=cls.root/'PROJECT_REGISTER.json';cls.register.write_text(json.dumps({'milestones':[{'objectives':[{'sources':[{'path':x['path']} for x in manifest['files']]}]}]}),encoding='utf-8')
        cls.feed=cls.root/'dist/progress.json';cls.feed.write_text('{"revision":"test"}',encoding='utf-8')
        (cls.root/'dist/index.html').write_text('<h1>test</h1>',encoding='utf-8')
        (cls.root/'README.txt').write_text('test continuity',encoding='utf-8')
        (cls.base/'private.txt').write_text('unlinked source',encoding='utf-8')
        cls.receipt={'registerSha256':hashlib.sha256(cls.register.read_bytes()).hexdigest(),'projectionRevision':'test','projectionSha256':hashlib.sha256(cls.feed.read_bytes()).hexdigest()}
        (cls.root/'evidence/REGISTER_VERIFICATION.json').write_text(json.dumps(cls.receipt),encoding='utf-8')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        cls.process=subprocess.Popen([node_runtime(),str(cls.root/'server.mjs')],env={**os.environ,'ACCLAM_QUEST_PORT':str(cls.port),'ACCLAM_SOURCE_ROOT':str(cls.attachment)},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags)
        cls.url=f'http://127.0.0.1:{cls.port}'
        for _ in range(30):
            try:
                with urlopen(cls.url,timeout=1):break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('Isolated transport did not start')
    @classmethod
    def tearDownClass(cls):cls.process.terminate();cls.process.wait(timeout=5);cls.temp.cleanup()
    def status(self,route,method='GET',headers=None):
        try:
            with urlopen(Request(self.url+route,method=method,headers=headers or {}),timeout=3) as r:return r.status
        except HTTPError as e:
            status=e.code;e.close();return status
    def test_readonly_and_allowlist(self):
        self.assertEqual(self.status('/'),200)
        self.assertEqual(self.status('/progress.json'),200)
        self.assertEqual(self.status('/progress.json','POST'),405)
        self.assertEqual(self.status('/source/private.txt'),404)
        self.assertEqual(self.status('/source/..%2Fprivate.txt'),404)
        self.assertEqual(self.status('/source/work%2Flaunch-quest%2FREADME.txt'),200)
    def test_host_bound_to_loopback(self):
        self.assertEqual(self.status('/',headers={'Host':'outside.example'}),403)
    def test_stale_register_rejected(self):
        before=self.register.read_bytes()
        try:self.register.write_bytes(before+b' ');self.assertEqual(self.status('/progress.json'),409)
        finally:self.register.write_bytes(before)
    def test_tampered_projection_rejected(self):
        before=self.feed.read_bytes()
        try:self.feed.write_bytes(before+b' ');self.assertEqual(self.status('/progress.json'),409)
        finally:self.feed.write_bytes(before)
    def test_attached_private_evidence_is_available_only_when_pinned(self):
        self.assertEqual(self.status('/source/private%2Fsource.txt'),200)
        self.assertEqual(self.status('/source/private%2Fmissing.txt'),424)
    def test_changed_private_evidence_is_conflict(self):
        before=self.attached.read_bytes()
        try:self.attached.write_bytes(b'changed');self.assertEqual(self.status('/source/private%2Fsource.txt'),409)
        finally:self.attached.write_bytes(before)
    def test_server_without_attachment_serves_snapshot_and_explains_missing_source(self):
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        env={**os.environ,'ACCLAM_QUEST_PORT':str(port)};env.pop('ACCLAM_SOURCE_ROOT',None)
        process=subprocess.Popen([node_runtime(),str(self.root/'server.mjs')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for _ in range(30):
                try:
                    with urlopen(f'http://127.0.0.1:{port}/progress.json',timeout=1) as response:self.assertEqual(response.status,200)
                    break
                except OSError:time.sleep(.1)
            else:self.fail('Snapshot viewer did not start')
            with self.assertRaises(HTTPError) as error:urlopen(f'http://127.0.0.1:{port}/source/private%2Fsource.txt',timeout=3)
            self.assertEqual(error.exception.code,424)
            self.assertIn('ACCLAM_SOURCE_ROOT',error.exception.read().decode())
            error.exception.close()
        finally:process.terminate();process.wait(timeout=5)

if __name__=='__main__':unittest.main(verbosity=2)
