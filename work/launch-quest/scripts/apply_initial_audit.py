"""Bounded audit corrections; preserves task IDs/status and appends dated history."""
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import QUEST, WORKSPACE, REGISTER, read, write, digest
r=read(REGISTER)
if r.get('initialAuditApplied'):raise SystemExit('Already applied; do not replay or overwrite later corrections.')
now=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
tasks={t['id']:t for m in r['milestones'] for t in m['objectives']}
def add(id,dependencies,note):
    t=tasks[id];t['dependencies']=list(dict.fromkeys(t['dependencies']+dependencies))
    t['history'].append({'date':now,'status':t['status'],'note':note})
add('ACA-QA-03',[f'ACA-FLOW-{n:02}-TEST' for n in range(1,13)],'Auditoría inicial: aceptación de workflow exige los doce ensayos de dominio, no solo seguridad/migración.')
add('ACA-ACCEPTANCE',[f'ACA-AI-{n:02}-TEST' for n in range(1,13)],'Auditoría inicial: incluir los doce usos previstos de asistencia. Una alternativa/no uso requiere decisión documentada de alcance y evidencia, sin desaparición silenciosa de tareas.')
schema=read(QUEST/'sources/schema_inventory.json')
for c in schema['collections']:
    if c['name'] in ['People','DirectoryProfiles','Events','Sessions','SpeakerAssignments']:
        add(f'ACA-CMS-{int(c["id"]):03}-PREP',['ACA-MIG-DRAFT-MAP'],'Auditoría inicial: la preparación de este lote depende del mapeo específico del paquete preliminar y sus faltantes.')
draft=read(QUEST/'evidence/INITIAL_LOCAL_AUDIT.json')
paths=['handoff/START_HERE.txt','handoff/CURRENT_STATE.json','handoff/LAUNCH_QUEST_BRIEF.txt','handoff/locked_baseline.txt','handoff/locked_baseline_facts.json','handoff/COLLECTION_SOURCE_MAP.json','handoff/HANDOFF_READY.json','handoff/shared_chat_findings.txt','handoff/launch_quest_reference.txt',
       'work/launch-quest/sources/locked_pages.json','work/launch-quest/sources/schema_inventory.json','work/launch-quest/sources/scope_inventory.json',
       'CMS/Draft preparation/sources/complete_inventory.json','CMS/Draft preparation/sources/drive_text.json']+list(draft['measuredFiles'])
r['sourceSnapshots']=[{'path':path,'sha256':digest(WORKSPACE/path)} for path in paths]
r['asOf']=now
r['project']['checkpointSummary']='Registro inicial auditado: fuentes y preparación local verificadas; dependencias de todos los flujos incluidas y fuentes originales fijadas por hash. Wix sigue sin inspección independiente.'
r['checkpoints'].append({'date':now,'note':'Auditoría independiente: cierres de dependencias, mapeo del lote preliminar y detección de fuentes/evidencias obsoletas. No cambia la cantidad de objetivos completados.'})
r['initialAuditApplied']=True
write(REGISTER,r)
print('Initial audit corrections saved; status counts unchanged.')
