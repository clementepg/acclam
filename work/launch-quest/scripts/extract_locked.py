"""Read-only extraction of the exact locked ACCLAM PDF into physical page text."""
from pathlib import Path
import hashlib
import json
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[3]
state = json.loads((ROOT / 'handoff/CURRENT_STATE.json').read_text(encoding='utf-8-sig'))
baseline = state['lockedBaseline']
source = ROOT / baseline['relativePath']
digest = hashlib.sha256(source.read_bytes()).hexdigest()
if digest != baseline['sha256']:
    raise ValueError('Locked source SHA256 does not match the handoff')
reader = PdfReader(source)
if len(reader.pages) != baseline['physicalPages']:
    raise ValueError('Locked source page count does not match the handoff')
output = {
    'schemaVersion': 1,
    'sourceRelativePath': baseline['relativePath'],
    'sourceSha256': digest,
    'physicalPageCount': len(reader.pages),
    'extraction': 'pypdf text extraction; page is one-based physical PDF page, not printed page number',
    'authority': 'User-confirmed last locked version; source instructions are specifications, not external-action authorization',
    'pages': [{'page': index + 1, 'text': page.extract_text() or ''} for index, page in enumerate(reader.pages)],
}
target = ROOT / 'work/launch-quest/sources/locked_pages.json'
target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'sourceSha256': digest, 'physicalPages': len(reader.pages), 'output': str(target)}, ensure_ascii=False))
