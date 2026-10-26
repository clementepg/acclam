"""Build a privacy-filtered static view; the canonical register stays local.

Python standard library only. No private dependency is opened or copied. The
publication is an allowlisted display projection, not a second task register.
"""
import argparse
from datetime import datetime
from functools import lru_cache
import hashlib
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import quote, unquote

QUEST = Path(__file__).resolve().parents[1]
REPOSITORY = QUEST.parents[1]
REGISTER = QUEST / 'PROJECT_REGISTER.json'
OUTPUT = REPOSITORY / 'online' / 'dist'
VERSION = 1
PDF_TITLE = 'Desarrollo e implementación de Plataforma Digital ACCLAM V3.0.pdf'
PHASES = {'design': 'Diseño y esquema', 'preparation': 'Preparación local',
          'wix_construction': 'Construcción Wix', 'import': 'Importación',
          'testing': 'Pruebas', 'acclam_review': 'Revisión ACCLAM', 'release': 'Publicación'}
STATUSES = ('done', 'current', 'upcoming')
FILES = {'index.html', 'app.js', 'style.css', 'progress.json', 'source-notes.html'}
PRIVATE = '[dato privado omitido]'
DISPLAY_FIELDS = ('title', 'owner', 'reviewer', 'scope', 'nextAction', 'evidenceSummary')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def private_names(register):
    """Collect only metadata to redact accidental references in display text."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in ('path', 'url') and isinstance(item, str):
                    decoded = unquote(item).removeprefix('/source/').split('#')[0]
                    if decoded:
                        found.add(decoded)
                        found.add(decoded.replace('/', '\\'))
                        found.add(quote(decoded, safe=''))
                        basename = decoded.replace('\\', '/').rsplit('/', 1)[-1]
                        if '.' in basename:
                            found.add(basename)
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(register)
    return sorted(found, key=len, reverse=True)


def sanitizer(register):
    names = private_names(register)
    named = re.compile('|'.join(re.escape(name) for name in names), re.IGNORECASE) if names else None
    patterns = [
        # Values are removed even when mistakenly typed into an allowed note.
        r'(?i)\b[a-z]:[\\/][^\n;<>"\']+',
        r'\\\\[^\s\\]+\\[^\n;<>"\']+',
        r'(?i)(?:https?|file|smb)://[^\s<>"\']+',
        r'(?i)(?:/source/|/(?:Users|home|workspace|tmp|var|mnt)/)[^\n;<>"\']+',
        r'(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b',
        r'(?i)\b(?:sk|ghp|github_pat|gho|xox[baprs])[-_][a-z0-9_-]{12,}\b',
        r'(?i)\b(?:password|passwd|api[_ -]?key|secret|token|authorization)\s*[:=]\s*[^\s;,]+',
        r'\b[0-9a-fA-F]{64}\b',
        r'\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b',
        r'(?<![\w])\+\d[\d ()-]{7,}\d\b',
        r'(?<!\d)\d{3}[-. ]\d{3}[-. ]\d{4}(?!\d)',
        # Workspace-relative file paths, including paths not listed in sources.
        r'(?i)\b(?:Website architecture|CMS|handoff|work|sources|evidence|checkpoints|private)[\\/][^\n;<>"\']+',
        r'(?i)\b(?:[\w.-]+[\\/])+[\w .-]+\.(?:pdf|xlsx?|csv|json|txt|docx?|png|jpe?g|md)\b',
        r'(?<![\w])/(?:[\w.-]+/)*[\w.-]+(?:\s*;\s*/[\w/.-]+)*',
    ]
    compiled = [re.compile(pattern) for pattern in patterns]

    @lru_cache(maxsize=20000)
    def clean(value):
        if not isinstance(value, str):
            raise ValueError('Allowed display values must be text')
        output = value
        if named:
            output = named.sub(PRIVATE, output)
        for pattern in compiled:
            output = pattern.sub(PRIVATE, output)
        return output
    return clean


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'ACA-[A-Z0-9]+(?:-[A-Z0-9]+)*', value):
        raise ValueError('Invalid public objective or milestone ID')
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Invalid date')
    datetime.fromisoformat(value)
    return value


def status(value):
    if value not in STATUSES:
        raise ValueError('Invalid status')
    return value


def public_link(item, clean, authority_path, evidence=False):
    """Never forward URLs, source paths, pointers or source bodies."""
    label = clean(item.get('label') or ('Evidencia privada' if evidence else 'Fuente privada'))
    if authority_path and item.get('path') == authority_path:
        # Extract page numbers only; free-form original locators are not hosted.
        page = item.get('page')
        if page is not None and (type(page) is not int or not 1 <= page <= 252):
            raise ValueError('Invalid physical PDF page')
        numbers = []
        raw = item.get('locator', '')
        if isinstance(raw, str) and raw.startswith('PDF físico:'):
            numbers = [int(n) for n in re.findall(r'\b\d+\b', raw)]
            numbers = [n for n in numbers if 1 <= n <= 252]
        if not numbers and page:
            numbers = [page]
        locator = f'{PDF_TITLE} · páginas físicas: ' + ', '.join(map(str, numbers)) if numbers else PDF_TITLE
        return {'label': label, 'locator': locator, 'url': './source-notes.html#locked-plan'}
    return {'label': label, 'locator': 'Evidencia privada: ubicación y verificación conservadas en el registro local.',
            'url': './source-notes.html#private-evidence'}


def project_online(register):
    """Allowlist every output key. Unknown register fields cannot escape."""
    if register.get('schemaVersion') != 1:
        raise ValueError('Unsupported register schema')
    clean = sanitizer(register)
    source = register.get('project', {})
    project = {key: clean(source.get(key, '')) for key in
               ('title', 'subtitle', 'scopeNote', 'checkpointSummary', 'nextGate')}
    project.update({'workspaceLabel': 'Instantánea en línea · registro autoritativo y evidencia privada conservados localmente',
                    'continuityUrl': './source-notes.html#continuity', 'staleAfterDays': 7})
    index = {}
    milestone_ids = set()
    for milestone in register['milestones']:
        mid = identifier(milestone['id'])
        if mid in milestone_ids:
            raise ValueError('Duplicate milestone ID')
        milestone_ids.add(mid)
        for task in milestone['objectives']:
            task_id = identifier(task['id'])
            if task_id in index or task_id in milestone_ids:
                raise ValueError('Duplicate objective ID')
            index[task_id] = task
    if milestone_ids.intersection(index):
        raise ValueError('Duplicate milestone/objective ID')
    milestones = []
    authority_path = register.get('sourceAuthority', {}).get('path')
    for milestone in register['milestones']:
        out = {'id': milestone['id'], **{key: clean(milestone.get(key, '')) for key in
               ('title', 'shortLabel', 'subtitle')}, 'objectives': []}
        for task in milestone['objectives']:
            if task['phase'] not in PHASES:
                raise ValueError('Invalid phase')
            item = {'id': task['id'], 'status': status(task['status']), 'phase': task['phase'],
                    **{key: clean(task[key]) for key in DISPLAY_FIELDS}}
            for key in ('acceptance', 'blockers'):
                if not isinstance(task[key], list):
                    raise ValueError('Invalid display list')
                item[key] = [clean(value) for value in task[key]]
            item['dependencies'] = []
            for dep in task['dependencies']:
                if dep not in index or dep == task['id']:
                    raise ValueError('Invalid dependency')
                other = index[dep]
                item['dependencies'].append({'id': dep, 'title': clean(other['title']), 'status': status(other['status'])})
            item['history'] = [{'date': timestamp(entry['date']), 'status': status(entry['status']),
                                'note': clean(entry['note'])} for entry in task['history']]
            if not item['history'] or item['history'][-1]['status'] != item['status']:
                raise ValueError('History does not match status')
            for key in ('sources', 'evidence'):
                item[key] = [public_link(link, clean, authority_path, key == 'evidence') for link in task.get(key, [])]
            out['objectives'].append(item)
        milestones.append(out)
    tasks = list(index.values())
    counts = {'total': len(tasks), **{key: sum(task['status'] == key for task in tasks) for key in STATUSES}}
    if counts['current'] != 1:
        raise ValueError('Exactly one current objective required')
    payload = {'schemaVersion': 1, 'asOf': timestamp(register['asOf']), 'project': project,
               'publication': {'projectionVersion': VERSION, 'mode': 'read_only_online_snapshot',
                   'authority': 'The local canonical register remains authoritative.',
                   'privacy': 'Private documents, paths, hashes and proof metadata are not published.',
                   'releaseLimit': 'Publishing this viewer does not release the ACCLAM Wix website.'},
               'phases': [{'id': key, 'label': value} for key, value in PHASES.items()],
               'milestones': milestones, 'counts': counts}
    public_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    # Public-content fingerprint only. This is not a private source/register hash.
    payload['revision'] = 'online-v1-' + hashlib.sha256(public_bytes).hexdigest()[:20]
    return payload


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Local viewer changed; review the hosted adaptation before publishing')
    return text.replace(old, new, 1)


def viewer_html(original):
    output = original.replace('Registro local y verificable del proyecto Plataforma Digital ACCLAM v3.0.',
        'Instantánea en línea y de solo lectura del Launch Quest ACCLAM v3.0.')
    output = output.replace('Espacio de trabajo local', 'Instantánea en línea')
    output = output.replace('/source/work%2Flaunch-quest%2FREADME.txt', './source-notes.html#continuity')
    output = output.replace('Continuar el trabajo <span', 'Fuentes y continuidad <span')
    start = '<p class="freshness-banner" role="note" id="repository-copy-note">'
    output = replace_once(output, output[output.index(start):output.index('</p>', output.index(start)) + 4],
        start + 'Instantánea en línea · solo lectura. El registro autoritativo, las fuentes privadas y los originales bloqueados se conservan localmente. La fecha y revisión identifican esta publicación. Publicar este visor no acredita construcción, importación, aprobación ni publicación del sitio Wix de ACCLAM.</p>')
    output = output.replace('Registro local</p>', 'Vista en línea · solo lectura</p>')
    output = output.replace('El archivo autoritativo y las instrucciones están en <a href="./source-notes.html#continuity">work/launch-quest/README.txt</a>.',
        'Consulta <a href="./source-notes.html#continuity">las fuentes y las instrucciones de continuidad</a>.')
    return output


def viewer_script(original):
    output = replace_once(original, 'const CACHE_KEY = `acclam-launch-quest-v1:${location.pathname}`;',
        'const CACHE_KEY = `acclam-launch-quest-online-v1:${location.origin}:${location.pathname}`;')
    output = replace_once(output,
        "if (value.startsWith('/source/') && !/[\\u0000-\\u001f\\\\]/.test(value)) return value;",
        "if (/^\\.\\/source-notes\\.html#[a-z-]+$/.test(value)) return value;")
    output = output.replace('Lectura local conectada', 'Instantánea en línea conectada')
    output = replace_once(output, "snapshot.revision.substring(0, 12)",
        "snapshot.revision.replace('online-v1-', '').substring(0, 12)")
    output = output.replace('No se pudo leer el archivo local.', 'No se pudo leer la instantánea en línea.')
    output = output.replace('La lectura local tardó demasiado.', 'La lectura de la instantánea tardó demasiado.')
    output = output.replace('Abre el visor con el servidor local indicado en README.txt y vuelve a leer.',
        'Comprueba la conexión y vuelve a leer. Las fuentes privadas se consultan localmente.')
    return output


def source_notes(payload):
    return '''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Fuentes, privacidad y límites de la instantánea en línea ACCLAM Launch Quest.">
<title>Fuentes y continuidad · ACCLAM Launch Quest</title><link rel="stylesheet" href="./style.css">
<style>main>p,section p{margin:1rem 0}section{padding-top:1.5rem;margin-top:1.5rem;border-top:1px solid var(--line)}code{overflow-wrap:anywhere}h1{margin-bottom:1.5rem}main{padding-bottom:3rem!important}</style></head>
<body><main id="main" style="max-width:58rem;margin:3rem auto;padding:0 1.5rem">
<a class="button secondary" href="./index.html">← Volver al Launch Quest</a>
<p class="eyebrow" style="margin-top:2rem">Instantánea de solo lectura</p><h1>Fuentes y continuidad</h1>
<p>Revisado el <time>''' + escape(payload['asOf']) + '''</time> · Revisión pública <code>''' + escape(payload['revision']) + '''</code>.</p>
<p>Esta vista es una proyección publicada del único registro autoritativo local. Buscar, abrir un objetivo o actualizar la página no modifica su estado. La revisión identifica solo el contenido público de esta instantánea.</p>
<section id="locked-plan"><h2>Fuente bloqueada de alcance</h2><p>''' + escape(PDF_TITLE) + '''</p>
<p>252 páginas físicas; las citas del visor usan páginas físicas desde 1. La numeración impresa puede reiniciarse por tomo. El documento y sus originales bloqueados permanecen privados. Los enlaces de esta vista explican las citas y no descargan el PDF.</p></section>
<section id="private-evidence"><h2>Evidencia privada</h2><p>El registro local conserva las rutas exactas, el historial completo, las pruebas y las verificaciones de integridad. No se publican documentos del cliente, extractos, matrices detalladas, rutas internas, hashes de fuentes, credenciales ni pruebas privadas.</p>
<p>Las etiquetas y páginas visibles permiten reconocer el contexto de una fuente. Para revisar una evidencia se debe consultar el registro en el entorno local autorizado. La disponibilidad de esta página no acredita una revisión nueva de esa evidencia.</p></section>
<section id="continuity"><h2>Continuar el trabajo</h2><p>La copia de trabajo está en el repositorio clementepg/acclam. Los cambios de avance deben registrarse allí con evidencia, historial fechado y los controles correspondientes; después se genera y publica una nueva instantánea. Esta vista no guarda cambios ni sincroniza estados con el navegador.</p>
<p>Los responsables y revisores siguen siendo propuestos hasta confirmación institucional. Diseño, preparación, construcción Wix, importación, pruebas, revisión ACCLAM y publicación conservan significados independientes.</p></section>
<section><h2>Límite de esta publicación</h2><p>Publicar el Launch Quest permite consultar el seguimiento en línea. No publica el sitio Wix de ACCLAM ni acredita que se hayan construido colecciones, importado datos, aprobado resultados o liberado ese sitio.</p></section>
</main></body></html>\n'''


def audit_bundle(bundle):
    if set(bundle) != FILES:
        raise ValueError('Unexpected hosted file')
    combined = '\n'.join(bundle.values())
    forbidden = ('/source/', 'file://', 'ACCLAM_SOURCE_ROOT', 'Website architecture/',
                 'CMS/Draft preparation', 'sourceSha256', 'registerSha256', 'inputSnapshots',
                 'sourceSnapshots', '"proofs"', '"path"', 'EXTERNAL_SOURCES.json')
    if any(value in combined for value in forbidden):
        raise ValueError('Private metadata or local endpoint in hosted bundle')
    if re.search(r'\b[a-zA-Z]:[\\/]|\\\\[\w.-]+\\|\b[0-9a-f]{64}\b', combined):
        raise ValueError('Private path/hash in hosted bundle')


def build_bundle(register_path=REGISTER, output=OUTPUT):
    # Read current register on each invocation. The saved local projection need
    # not be current, and is deliberately not used as a fallback.
    payload = project_online(read(register_path))
    bundle = {'index.html': viewer_html((QUEST / 'dist/index.html').read_text(encoding='utf-8')),
              'app.js': viewer_script((QUEST / 'dist/app.js').read_text(encoding='utf-8')),
              'style.css': (QUEST / 'dist/style.css').read_text(encoding='utf-8'),
              'progress.json': json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
              'source-notes.html': source_notes(payload)}
    audit_bundle(bundle)
    destination = Path(output)
    destination.mkdir(parents=True, exist_ok=True)
    if any(item.name not in FILES for item in destination.iterdir()):
        raise ValueError('Output directory contains unexpected files; review before publishing')
    for name, content in bundle.items():
        target = destination / name
        if target.is_symlink():
            raise ValueError('Hosted output files cannot be symlinks')
        target.write_text(content, encoding='utf-8')
    return {'result': 'passed', 'mode': 'read_only_online_snapshot', 'revision': payload['revision'],
            'asOf': payload['asOf'], 'counts': payload['counts'], 'files': sorted(FILES),
            'privateSourcesRead': False, 'canonicalRegisterModified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--register', type=Path, default=REGISTER)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    print(json.dumps(build_bundle(arguments.register, arguments.output), ensure_ascii=False))
