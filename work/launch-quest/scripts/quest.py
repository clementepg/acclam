"""Validate the single register and generate a read-only, allowlisted projection."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime
from source_resolver import configured_resolver, MissingExternalSource, relative_path

QUEST = Path(__file__).resolve().parents[1]
WORKSPACE = QUEST.parents[1]
REGISTER = QUEST / 'PROJECT_REGISTER.json'
PHASES = {'design': 'Diseño y esquema', 'preparation': 'Preparación local',
          'wix_construction': 'Construcción Wix', 'import': 'Importación',
          'testing': 'Pruebas', 'acclam_review': 'Revisión ACCLAM', 'release': 'Publicación'}
CLASSES = {'design': 'source_review', 'preparation': 'local_preparation',
           'wix_construction': 'implementation', 'import': 'import',
           'testing': 'test', 'acclam_review': 'human_review', 'release': 'release'}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(text, encoding='utf-8')
        temp.replace(path)

def local(path):
    return configured_resolver().resolve(path)

def pointer(data, key):
    if key == '':
        return data
    if not key.startswith('/'):
        raise ValueError('JSON assertions require RFC6901 pointer')
    for part in key[1:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        data = data[int(part)] if isinstance(data, list) else data[part]
    return data

def validate(register, verify_proofs=True, allow_missing_external=False):
    import re
    problems = []
    resolver = configured_resolver()
    unavailable = {}
    def locate(path):
        try:
            return resolver.resolve(path)
        except MissingExternalSource:
            if not allow_missing_external:
                raise
            unavailable[path] = {'path':path, 'sha256':resolver.external[path],
                                 'reason':'private_client_source', 'available':False}
            return None
    def need(ok, message):
        if not ok: problems.append(message)
    need(register.get('schemaVersion') == 1, 'Unsupported register schema')
    for snapshot in register.get('inputSnapshots',[])+register.get('sourceSnapshots',[]):
        try:
            need(bool(re.fullmatch('[0-9a-f]{64}',snapshot.get('sha256',''))),f'Invalid snapshot hash: {snapshot["path"]}')
            if snapshot['path'] in resolver.external:
                need(snapshot['sha256']==resolver.external[snapshot['path']],f'Input changed: {snapshot["path"]}; snapshot differs from external source pin')
            path = locate(snapshot['path'])
            if path: need(digest(path)==snapshot['sha256'],f'Input changed: {snapshot["path"]}; review before updating snapshot')
        except Exception as e: problems.append(f'Input snapshot: {e}')
    try: datetime.fromisoformat(register['asOf'])
    except Exception: problems.append('Invalid asOf review time')
    milestones = register.get('milestones', [])
    tasks = [t for m in milestones for t in m.get('objectives', [])]
    ids = [t.get('id') for t in tasks]
    mids = [m.get('id') for m in milestones]
    need(len(set(ids)) == len(ids), 'Duplicate task IDs')
    need(len(set(mids)) == len(mids), 'Duplicate milestone IDs')
    need(all(isinstance(i,str) and re.fullmatch(r'ACA-[A-Z0-9]+(?:-[A-Z0-9]+)*',i) for i in ids), 'Invalid task ID')
    index = {t['id']:t for t in tasks}
    need(sum(t.get('status') == 'current' for t in tasks) == 1, 'Exactly one current objective required')
    required = ['title','owner','reviewer','scope','nextAction','evidenceSummary']
    proof_count = 0
    verified_proof_count = 0
    for t in tasks:
        key = t['id']
        for field in required:
            need(isinstance(t.get(field),str) and bool(t[field].strip()), f'{key}: missing {field}')
        need(t.get('phase') in PHASES, f'{key}: invalid phase')
        need(t.get('status') in ['done','current','upcoming'], f'{key}: invalid status')
        for field in ['acceptance','sources','history']:
            need(isinstance(t.get(field),list) and bool(t[field]), f'{key}: empty {field}')
        need(isinstance(t.get('blockers'),list), f'{key}: blockers must be explicit array')
        deps=t.get('dependencies',[])
        need(len(set(deps))==len(deps), f'{key}: duplicate dependency')
        for d in deps:
            need(d in index and d != key, f'{key}: missing/self dependency {d}')
            if t.get('status') in ['done','current'] and d in index:
                need(index[d].get('status')=='done', f'{key}: {t["status"]} with unfinished dependency {d}')
        for h in t.get('history',[]):
            try: datetime.fromisoformat(h['date'])
            except Exception: problems.append(f'{key}: invalid history date')
            need(h.get('status') in ['done','current','upcoming'] and bool(h.get('note')),f'{key}: invalid history')
        if t.get('history'):
            need(t['history'][-1].get('status')==t.get('status'),f'{key}: latest history does not match status')
        for s in t.get('sources',[]) + t.get('evidence',[]):
            try: locate(s['path'])
            except Exception as e: problems.append(f'{key}: {e}')
            need(bool(s.get('label')) and bool(s.get('locator')),f'{key}: source needs precise label/locator')
            if 'page' in s: need(type(s['page']) is int and 1<=s['page']<=252,f'{key}: invalid physical PDF page')
        if t.get('status')=='done':
            need(bool(t.get('evidence')),f'{key}: done without visible evidence')
            need(bool(t.get('proofs')),f'{key}: done without verifiable proofs')
            for proof in t.get('proofs',[]):
                proof_count += 1
                need(proof.get('class')==CLASSES.get(t.get('phase')),f'{key}: wrong evidence class for phase')
                need(bool(proof.get('finding')) and bool(proof.get('reviewedBy')), f'{key}: missing reviewed finding/actor')
                if t.get('phase')=='acclam_review':
                    need(proof.get('humanApproval') is True,f'{key}: human approval required')
                try:
                    need(bool(re.fullmatch('[0-9a-f]{64}',proof.get('sha256',''))),f'{key}: invalid proof hash')
                    if proof['path'] in resolver.external:
                        need(proof['sha256']==resolver.external[proof['path']],f'{key}: evidence hash mismatch: {proof["path"]}')
                    source_identity = (proof.get('sourceIdentityOnly') is True and t.get('phase')=='design'
                        and proof['path']==register.get('sourceAuthority',{}).get('path')
                        and proof['sha256']==register.get('sourceAuthority',{}).get('sha256'))
                    need(bool(proof.get('assertions')) or bool(proof.get('contains')) or source_identity,f'{key}: no proof assertions')
                    for assertion in proof.get('assertions',[]):
                        need(isinstance(assertion.get('pointer'),str) and (assertion['pointer']=='' or assertion['pointer'].startswith('/')) and 'equals' in assertion,f'{key}: malformed proof assertion')
                    need(all(isinstance(q,str) and bool(q) for q in proof.get('contains',[])),f'{key}: malformed reviewed passage')
                    path = locate(proof['path'])
                    if path is None: continue
                    if verify_proofs:
                        need(digest(path)==proof['sha256'],f'{key}: evidence hash mismatch: {proof["path"]}')
                        for assertion in proof.get('assertions',[]):
                            got=pointer(read(path),assertion['pointer']); wanted=assertion['equals']
                            need(type(got) is type(wanted) and got==wanted,f'{key}: typed assertion fails {assertion["pointer"]}')
                        for quote in proof.get('contains',[]):
                            need(quote in path.read_text(encoding='utf-8-sig'),f'{key}: reviewed passage missing')
                        verified_proof_count += 1
                except Exception as e: problems.append(f'{key}: proof error: {e}')
    visiting=set();visited=set()
    def visit(i):
        if i in visiting: problems.append(f'Dependency cycle at {i}'); return
        if i in visited or i not in index:return
        visiting.add(i)
        for d in index[i].get('dependencies',[]):visit(d)
        visiting.remove(i);visited.add(i)
    for i in index:visit(i)
    baseline=read(QUEST/'BASELINE_IDS.json') if (QUEST/'BASELINE_IDS.json').exists() else None
    if baseline:
        need(set(baseline['objectiveIds']).issubset(set(ids)), 'Baseline objective IDs disappeared')
        need(set(baseline['milestoneIds']).issubset(set(mids)), 'Baseline milestone IDs disappeared')
        for coverage in baseline['requiredCoverage']:
            need(coverage['objectiveId'] in index, f'Missing scope: {coverage}')
    if problems:raise ValueError('\n'.join(problems))
    result = {'objectives':len(tasks),'milestones':len(milestones),'verifiedProofs':verified_proof_count,
              'done':sum(t['status']=='done' for t in tasks),'cycles':0,'errors':0}
    if allow_missing_external:
        result.update({'proofMetadataCount':proof_count,'unavailablePrivateSources':sorted(unavailable.values(),key=lambda x:x['path'])})
    return result

def source_link(s):
    from urllib.parse import quote
    return {'label':s['label'],'locator':s['locator'],
            'url':'/source/'+quote(s['path'],safe='')+('#page='+str(s['page']) if 'page' in s else '')}

def project(register):
    index={t['id']:t for m in register['milestones'] for t in m['objectives']}
    milestones=[]
    for m in register['milestones']:
        output={k:m[k] for k in ['id','title','shortLabel','subtitle']}; output['objectives']=[]
        for t in m['objectives']:
            item={k:t[k] for k in ['id','title','status','phase','owner','reviewer','scope','acceptance','nextAction','blockers','evidenceSummary','history']}
            item['dependencies']=[{k:index[d][k] for k in ['id','title','status']} for d in t['dependencies']]
            for k in ['sources','evidence']: item[k]=[source_link(s) for s in t.get(k,[])]
            output['objectives'].append(item)
        milestones.append(output)
    tasks=list(index.values())
    payload={'schemaVersion':1,'asOf':register['asOf'],'project':register['project'],
             'phases':[{'id':k,'label':v} for k,v in PHASES.items()], 'milestones':milestones,
             'counts':{'total':len(tasks),**{k:sum(t['status']==k for t in tasks) for k in ['done','current','upcoming']},
             'byPhase':[{'id':k,'label':v,'total':sum(t['phase']==k for t in tasks),'done':sum(t['phase']==k and t['status']=='done' for t in tasks)} for k,v in PHASES.items()]}}
    payload['revision']=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return payload

def build():
    r=read(REGISTER); result=validate(r); p=project(r)
    write(QUEST/'dist/progress.json',p)
    write(QUEST/'SOURCE_MAP.json',{'note':'Generated map; PROJECT_REGISTER.json is authoritative.',
        'revision':p['revision'],'tasks':[{'id':t['id'],'sources':t['sources'],'evidence':t.get('evidence',[])} for m in r['milestones'] for t in m['objectives']]})
    write(QUEST/'evidence/REGISTER_VERIFICATION.json',{'result':'passed','registerSha256':digest(REGISTER),'projectionRevision':p['revision'],'projectionSha256':digest(QUEST/'dist/progress.json'),**result})
    return {**result,'revision':p['revision']}

def verify_copy():
    """Read-only snapshot/metadata check. Never issues a full evidence receipt."""
    r = read(REGISTER)
    result = validate(r, allow_missing_external=True)
    receipt = read(QUEST/'evidence/REGISTER_VERIFICATION.json')
    projection = read(QUEST/'dist/progress.json')
    if (receipt.get('registerSha256') != digest(REGISTER)
            or receipt.get('projectionSha256') != digest(QUEST/'dist/progress.json')
            or receipt.get('projectionRevision') != projection.get('revision')
            or projection != project(r)):
        raise ValueError('Preserved register/projection integrity failed; strict validate/build with original sources is required')
    return {'mode':'repository_copy', 'result':'snapshot_and_available_evidence_verified',
            'fullEvidenceValidation':False, 'writesPerformed':False,
            'limits':'Private sources may be unavailable. Preserved task statuses/history are unchanged; this check does not re-certify the historical full evidence audit.',
            'registerSha256':digest(REGISTER), 'projectionRevision':projection['revision'], **result}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['validate','build','verify-copy']);args=parser.parse_args()
    try:
        result = build() if args.command=='build' else verify_copy() if args.command=='verify-copy' else validate(read(REGISTER))
        print(json.dumps(result,ensure_ascii=False))
    except Exception as e:
        print(str(e));raise SystemExit(1)
