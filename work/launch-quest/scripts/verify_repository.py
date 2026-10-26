"""Verify the privacy-filtered transfer without claiming private proof validation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

QUEST=Path(__file__).resolve().parents[1]
REPO=QUEST.parents[1]
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args,**kwargs):
    kwargs['env']={**kwargs.pop('env',os.environ),'PYTHONIOENCODING':'utf-8'}
    checked=subprocess.run(args,cwd=REPO,capture_output=True,text=True,encoding='utf-8',**kwargs)
    if checked.returncode:raise ValueError(checked.stderr or checked.stdout)
    return checked.stdout.strip()

def verify():
    if sys.version_info<(3,10):raise ValueError('Python3.10+ required')
    node=shutil.which('node')
    if not node:
        fallback=Path(os.environ.get('USERPROFILE','~'))/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
        if fallback.is_file():node=str(fallback)
    if not node:raise ValueError('Node.js18+ required on PATH (or optional local Codex runtime)')
    node_version=run([node,'--version'])
    if int(node_version.lstrip('v').split('.')[0])<18:raise ValueError('Node.js18+ required')
    manifest=read(QUEST/'COPY_MANIFEST.json')
    authority=read(QUEST/'WORKING_AUTHORITY.json') if (QUEST/'WORKING_AUTHORITY.json').exists() else {}
    archives=authority.get('transferArchives',{})
    preserved_files=[]
    for item in manifest['files']:
        file=(REPO/archives.get(item['path'],item['path'])).resolve()
        if not file.is_relative_to(REPO.resolve()) or not file.is_file() or sha(file)!=item['sha256']:
            raise ValueError('Preserved original changed: '+item['path'])
        preserved_files.append((file,item['sha256']))
    # Only current/future Git contents are eligible for the publication audit.
    names=run(['git','ls-files','--cached','--others','--exclude-standard','-z']).split('\x00')
    names=sorted(set(name for name in names if name))
    patterns={
        'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
        'github_token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
        'aws_access_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
        'literal_personal_path':re.compile(r'(?i)\b[A-Z]:[\\/]Users[\\/][^\s"\x27]+'),
        'contact_email':re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b'),
    }
    issues=[]
    denied={'.pdf','.xlsx','.xls','.docx','.csv','.zip','.pem','.key','.pfx','.p12','.pyc','.log'}
    for name in names:
        file=REPO/name;parts=Path(name).parts
        if file.suffix.lower() in denied or 'sources' in parts or '__pycache__' in parts or file.name.startswith(('.env','.viewer')):
            issues.append(name+': excluded private/runtime file type');continue
        if file.suffix.lower() in {'.jpg','.jpeg','.png'}:continue
        data=file.read_text(encoding='utf-8-sig')
        for label,pattern in patterns.items():
            # Patterns in this verifier are generic expressions, never real values.
            matches=pattern.findall(data)
            # The hosted sanitization regression uses the reserved example.org
            # address as an explicit negative fixture, never a client contact.
            if label=='contact_email' and name.endswith('/scripts/test_online.py') and matches and all(x.rsplit('@',1)[-1]=='example.org' for x in matches):continue
            if matches:issues.append(name+': '+label)
    if issues:raise ValueError('\n'.join(issues))
    for file in sorted(QUEST.glob('*.mjs'))+sorted((QUEST/'dist').glob('*.js')):
        run([node,'--check',str(file)])
    clean_env={k:v for k,v in os.environ.items() if k!='ACCLAM_SOURCE_ROOT'}
    status=json.loads(run([sys.executable,str(QUEST/'scripts/quest.py'),'verify-copy'],env=clean_env))
    if status.get('fullEvidenceValidation') is not False or status.get('writesPerformed') is not False:
        raise ValueError('Copy validation must be explicitly bounded and read-only')
    register=read(QUEST/'PROJECT_REGISTER.json')
    tasks=[t for m in register['milestones'] for t in m['objectives']]
    expected={'objectives':len(tasks),'milestones':len(register['milestones']),'done':sum(t['status']=='done' for t in tasks)}
    if any(status[k]!=v for k,v in expected.items()):raise ValueError('Projection and authoritative register counts differ')
    omitted=read(QUEST/'EXTERNAL_SOURCES.json')['files']
    if len(status['unavailablePrivateSources'])!=len(omitted):raise ValueError('Private dependency inventory differs from standalone check')
    if any((REPO/x['path']).exists() for x in omitted):raise ValueError('Private source unexpectedly included in repository')
    for file,pinned in preserved_files:
        if sha(file)!=pinned:raise ValueError('Verification changed a preserved file')
    result={'result':'passed','scope':'Repository transfer, saved snapshot and available evidence only; private proof bodies deliberately unavailable.',
        'registerSha256':status['registerSha256'],'projectionRevision':status['projectionRevision'],
        **expected,'preservedOriginalFiles':len(manifest['files']),
        'excludedPrivateSourceFiles':len(omitted),'candidateFilesScanned':len(names),
        'secretAndContactPatternFindings':0,'fullPrivateEvidenceValidation':False,
        'runtimeVersions':{'node':node_version,'python':sys.version.split()[0]},
        'limits':'File allowlist, byte checks and high-confidence pattern scan support the transfer; private documents remain external. Original full evidence validation is a separate command.'}
    return result

if __name__=='__main__':
    try:print(json.dumps(verify(),ensure_ascii=False))
    except Exception as error:print(str(error));raise SystemExit(1)
