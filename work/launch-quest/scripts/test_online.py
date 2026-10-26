"""Privacy, determinism and source-preservation checks for the hosted projection."""
import copy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest

from build_online import (FILES, PDF_TITLE, PRIVATE, QUEST, REGISTER, audit_bundle,
                          build_bundle, project_online, read, sanitizer)


def flat(register):
    return [task for milestone in register['milestones'] for task in milestone['objectives']]


def walk(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


class OnlineProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = read(REGISTER)

    def setUp(self):
        self.register = copy.deepcopy(self.original)

    def test_task_ids_statuses_dependencies_and_history_dates_preserved(self):
        public = project_online(self.register)
        original = flat(self.register)
        actual = flat(public)
        self.assertEqual(len(original), len(actual))
        self.assertEqual([m['id'] for m in self.register['milestones']], [m['id'] for m in public['milestones']])
        for before, after in zip(original, actual):
            self.assertEqual((before['id'], before['status'], before['phase']), (after['id'], after['status'], after['phase']))
            self.assertEqual(before['dependencies'], [dep['id'] for dep in after['dependencies']])
            self.assertEqual([(h['date'], h['status']) for h in before['history']], [(h['date'], h['status']) for h in after['history']])
        self.assertEqual(public['counts']['done'], sum(task['status'] == 'done' for task in original))
        self.assertEqual(public['counts']['current'], 1)

    def test_projection_explicitly_excludes_raw_metadata(self):
        self.register['privateSourceMap'] = {'secret': 'do not copy this'}
        flat(self.register)[0]['privateFinding'] = 'do not copy this either'
        public = project_online(self.register)
        forbidden = {'path', 'sha256', 'proofs', 'inputSnapshots', 'sourceSnapshots', 'sourceAuthority',
                     'authorization', 'privateSourceMap', 'privateFinding', 'reviewedBy', 'assertions'}
        for mapping in walk(public):
            self.assertFalse(forbidden.intersection(mapping))
        body = json.dumps(public, ensure_ascii=False)
        self.assertNotIn('do not copy this', body)
        self.assertNotIn('/source/', body)
        self.assertNotIn(self.register['sourceAuthority']['sha256'], body)
        self.assertNotIn(self.register['sourceAuthority']['path'], body)

    def test_all_links_target_only_source_information(self):
        public = project_online(self.register)
        urls = [mapping['url'] for mapping in walk(public) if 'url' in mapping]
        urls.append(public['project']['continuityUrl'])
        self.assertGreater(len(urls), 600)
        self.assertTrue(all(re.fullmatch(r'\./source-notes\.html#[a-z-]+', url) for url in urls))
        baseline = flat(public)[0]
        self.assertIn(PDF_TITLE, baseline['sources'][0]['locator'])
        self.assertIn('1, 15, 108, 205, 232', baseline['sources'][0]['locator'])
        self.assertEqual(baseline['evidence'][0]['url'], './source-notes.html#private-evidence')

    def test_free_text_redacts_paths_contacts_hashes_tokens_and_runtime_ids(self):
        examples = [r'E:\Private folder\client\ledger.xlsx', r'\\server\private\client.xlsx',
                    '/source/private%2Fsecret.pdf', '/Users/client/private.pdf', 'private/secret.csv',
                    'Website architecture/schema_v3_0/secret.xlsx', 'https://private.example/secret',
                    'file:///C:/private/secret.pdf', 'person@example.org', '+1 (415) 555-1212',
                    '415-555-1212', 'a' * 64, 'ghp_Abcdefghijklmnop123456789',
                    'api_key=ThisIsASecret', '01a17904-81c8-7fe3-8ac4-e3efb7e3fa16',
                    '/proofs/privatePath; /sourceSha256']
        clean = sanitizer(self.register)
        for example in examples:
            with self.subTest(example=example):
                self.assertNotIn(example, clean('Nota: ' + example))
                self.assertIn(PRIVATE, clean('Nota: ' + example))
        self.assertEqual(clean('Technical Admin / responsable propuesto'), 'Technical Admin / responsable propuesto')
        self.assertEqual(clean('People, 1,083 campos y 77 colecciones'), 'People, 1,083 campos y 77 colecciones')

    def test_source_metadata_injected_into_any_display_field_is_redacted(self):
        private_path = self.register['sourceAuthority']['path']
        source_name = 'ACCLAM_V3_FROZEN_Collection_Kit.xlsx'
        task = flat(self.register)[0]
        for key in ('title', 'owner', 'reviewer', 'scope', 'nextAction', 'evidenceSummary'):
            task[key] = 'Revisar ' + private_path + ' y ' + source_name
        task['acceptance'].append('Consulta: person@example.org')
        task['history'][0]['note'] = 'Fuente: E:\\private\\secret.pdf'
        task['sources'][0]['label'] = 'Evidencia: private/secret.csv'
        public = json.dumps(project_online(self.register), ensure_ascii=False)
        self.assertNotIn(private_path, public)
        self.assertNotIn(source_name, public)
        self.assertNotIn('person@example.org', public)
        self.assertNotIn('secret.pdf', public)
        self.assertNotIn('private/secret.csv', public)

    def test_revision_is_deterministic_and_uses_public_content_only(self):
        first = project_online(self.register)
        second = project_online(copy.deepcopy(self.register))
        self.assertEqual(first, second)
        self.register['sourceAuthority']['sha256'] = 'b' * 64
        flat(self.register)[0]['proofs'][0]['finding'] = 'Changed private-only assessment'
        flat(self.register)[0]['proofs'][0]['sha256'] = 'c' * 64
        self.assertEqual(first['revision'], project_online(self.register)['revision'])
        flat(self.register)[0]['nextAction'] = 'Nueva acción visible'
        self.assertNotEqual(first['revision'], project_online(self.register)['revision'])
        self.assertRegex(first['revision'], r'^online-v1-[a-f0-9]{20}$')

    def test_missing_current_or_unknown_dependencies_fail_closed(self):
        current = next(t for t in flat(self.register) if t['status'] == 'current')
        current['status'] = 'upcoming'
        current['history'][-1]['status'] = 'upcoming'
        with self.assertRaisesRegex(ValueError, 'Exactly one current'):
            project_online(self.register)
        self.register = copy.deepcopy(self.original)
        flat(self.register)[0]['dependencies'] = ['ACA-NONEXISTENT']
        with self.assertRaisesRegex(ValueError, 'Invalid dependency'):
            project_online(self.register)

    def test_link_page_and_id_cannot_carry_arbitrary_text(self):
        flat(self.register)[0]['sources'][0]['page'] = 'private path'
        with self.assertRaisesRegex(ValueError, 'physical PDF page'):
            project_online(self.register)
        self.register = copy.deepcopy(self.original)
        flat(self.register)[0]['id'] = 'ACA-BASELINE/private'
        with self.assertRaisesRegex(ValueError, 'Invalid public'):
            project_online(self.register)

    def test_build_only_writes_five_files_and_leaves_local_originals_unchanged(self):
        protected = [REGISTER, QUEST / 'SOURCE_MAP.json', QUEST / 'dist/progress.json',
                     QUEST / 'dist/index.html', QUEST / 'dist/app.js']
        hashes = {path: hashlib.sha256(path.read_bytes()).digest() for path in protected}
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'dist'
            result = build_bundle(output=output)
            self.assertEqual({p.name for p in output.iterdir()}, FILES)
            self.assertFalse(result['privateSourcesRead'])
            self.assertFalse(result['canonicalRegisterModified'])
            bundle = {p.name: p.read_text(encoding='utf-8') for p in output.iterdir()}
            audit_bundle(bundle)
            self.assertNotIn('acclam-launch-quest-v1:', bundle['app.js'])
            self.assertIn('acclam-launch-quest-online-v1:', bundle['app.js'])
            self.assertIn('Publicar este visor no acredita', bundle['index.html'])
            self.assertIn('construcción Wix', bundle['source-notes.html'])
            self.assertIn(PDF_TITLE, bundle['source-notes.html'])
            self.assertEqual(result['asOf'], self.original['asOf'])
            again = build_bundle(output=output)
            self.assertEqual(result, again)
            self.assertEqual(bundle, {p.name: p.read_text(encoding='utf-8') for p in output.iterdir()})
        self.assertEqual(hashes, {path: hashlib.sha256(path.read_bytes()).digest() for path in protected})

    def test_output_with_unreviewed_extra_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'private.txt').write_text('Do not publish', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'unexpected files'):
                build_bundle(output=output)

    def test_build_reads_current_register_instead_of_saved_local_projection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            register_path = root / 'register.json'
            next(t for t in flat(self.register) if t['status'] == 'current')['nextAction'] = 'Nueva acción revisada para esta instantánea'
            register_path.write_text(json.dumps(self.register, ensure_ascii=False), encoding='utf-8')
            build_bundle(register_path=register_path, output=root / 'dist')
            actual = read(root / 'dist/progress.json')
            self.assertEqual(next(t for t in flat(actual) if t['status'] == 'current')['nextAction'],
                             'Nueva acción revisada para esta instantánea')


if __name__ == '__main__':
    unittest.main()
