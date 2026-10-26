"""Record the reviewed source audit once; never changes locked source files."""
import os
from datetime import datetime
from pathlib import Path
from quest import QUEST, REGISTER, read, write, digest

private=Path(os.environ['ACCLAM_SOURCE_ROOT']).resolve()
workbook_path='work/launch-quest-private/schema-align-20261026/workbook/FINAL_AUDIT.json'
controls_path='work/launch-quest-private/schema-align-20261026/controls/controls_audit.json'
construction='Website architecture/schema_v3_0/ACCLAM_V3_Compendio_Maestro_CONSTRUCCION_FINAL/ACCLAM_V3_FROZEN_Collection_Kit_CONSTRUCTION.xlsx'
w=read(private/workbook_path);c=read(private/controls_path)
assert digest(private/workbook_path)=='bb7e196db0af35ca5e34ab76ee56431aaf7d9566b716ff736ffcc02f8c9c0e9e'
assert digest(private/controls_path)=='68aec6c99bc586e6e4746152b38ee6593ad4afbddbb7328cc1d35deddf1239b4'
assert w['summary']['sourceFilesUnchanged'] is True
assert w['summary']['lockedPdfHelpAndUseMismatches']==0
assert c['summary']['exceptions']==0
r=read(REGISTER)
if r.get('schemaAlignmentRecorded'):raise SystemExit('Already recorded. Preserve history; do not replay this migration.')
now=datetime.now().astimezone().isoformat(timespec='seconds')
summary={'schemaVersion':1,'reviewedAt':now,'result':'source_alignment_complete',
 'scope':'Comparación documental y reconciliación de fuentes del esquema v3.0. No acredita implementación, permisos efectivos, importación, revisión humana ACCLAM ni lanzamiento de Wix.',
 'collections':77,'fields':1083,'helpTextMatches':1083,'sharedWorkbookDictionaryCellsCompared':47652,
 'sharedWorkbookDictionaryDifferences':0,'collectionMetadataComparisons':770,'collectionMetadataDifferences':0,
 'relationshipRowsCompared':912,'relationshipDifferences':0,'folderMappingsCompared':77,'folderDifferences':0,
 'primaryDisplaysMapped':77,'permissionCellComparisons':616,'permissionCellMatches':616,
 'validationRulesCompared':207,'validationRulesMatches':207,
 'indexRecommendations':{'Unique':95,'Index':153,'unspecified':835},
 'sourceDisposition':[
  'El PDF bloqueado conserva autoridad para números globales, carpetas, primary display y permisos explícitos.',
  'El XLSX de construcción aporta Help Text en su columna W; el XLSX frozen y el CSV tienen 22 columnas y no incluyen esa columna.',
  'La falta de columnas explícitas de número global/primary display en los XLSX se resuelve con un cruce derivado privado citado al PDF, sin editar originales.',
  'Las 248 recomendaciones de índice se conservan como apoyo; el PDF no enumera una lista exhaustiva por campo ni prueba índices activos.',
  'La exposición de DirectoryProfiles queda como aceptación de seguridad futura. La clasificación de privacidad y los booleanos no configuran permisos efectivos.',
  'Los catálogos geográficos públicos y Certificates restringido conservan las excepciones explícitas del PDF.'],
 'blockingSourceComparisonDiscrepancies':0,'lockedOriginalsModified':False,
 'privateEvidence':'Las matrices completas, celdas exactas, páginas físicas y hashes de fuentes permanecen en el archivo local privado.'}
summary_path='work/launch-quest/evidence/SCHEMA_ALIGNMENT_SUMMARY.json'
write(QUEST/'evidence/SCHEMA_ALIGNMENT_SUMMARY.json',summary)

manifest=read(QUEST/'EXTERNAL_SOURCES.json')
known={s['path'] for s in manifest['files']}
for path in [workbook_path,controls_path,construction]:
 if path not in known:manifest['files'].append({'path':path,'sha256':digest(private/path),'reason':'private_client_source'})
 if not any(x['path']==path for x in r['sourceSnapshots']):r['sourceSnapshots'].append({'path':path,'sha256':digest(private/path)})
manifest['files'].sort(key=lambda x:x['path'])
write(QUEST/'EXTERNAL_SOURCES.json',manifest)
tasks={t['id']:t for m in r['milestones'] for t in m['objectives']}
t=tasks['ACA-SCHEMA-ALIGN'];assert t['status']=='current'
t['status']='done'
t['nextAction']='Usar el cruce verificado para preparar el bootstrap local; conservar los controles de exposición e índices para las pruebas de construcción correspondientes.'
t['evidenceSummary']='77 colecciones y 1,083 campos reconciliados. Coinciden 1,083 Help Text, 47,652 celdas compartidas y 616 celdas de permisos; cero discrepancias bloqueantes de comparación documental. Los originales no se modificaron. La configuración y seguridad efectiva de Wix siguen sin verificar.'
t['evidence']=[{'path':summary_path,'label':'Resumen verificado de alineación','locator':'resultado, métricas, decisiones y límites de la comparación'},
 {'path':workbook_path,'label':'Auditoría privada de XLSX y Help Text','locator':'/summary; /artifacts; cruces de celdas y páginas físicas'},
 {'path':controls_path,'label':'Auditoría privada de controles','locator':'/summary; /sourceInterpretationAndFutureAcceptance; /collections; /fields'}]
def proof(path,assertions,finding):
 file=private/path if path in [workbook_path,controls_path] else QUEST.parents[1]/path
 return {'path':path,'sha256':digest(file),'class':'source_review','reviewedBy':'Codex · auditoría documental local del 26 de octubre de 2026','finding':finding,'assertions':[{'pointer':p,'equals':v} for p,v in assertions]}
t['proofs']=[proof(summary_path,[('/result','source_alignment_complete'),('/blockingSourceComparisonDiscrepancies',0),('/lockedOriginalsModified',False),('/fields',1083)],'Resumen acotado a la comparación de fuentes y sus límites.'),
 proof(workbook_path,[('/summary/lockedPdfHelpTextMatches',1083),('/summary/lockedPdfHelpAndUseMismatches',0),('/summary/collectionMetadataMismatches',0),('/summary/sourceFilesUnchanged',True)],'Se compararon los dos XLSX, el CSV y el PDF con localizadores por campo/celda/página y sin modificar fuentes.'),
 proof(controls_path,[('/summary/permissionCellMatches',616)] if 'permissionCellMatches' in c['summary'] else [('/summary/permissionCellsExactMatches',616),('/summary/validationRulesIncludedVerbatimWhitespaceNormalized',207),('/summary/exceptions',0)],'Se revisaron las 77 matrices; las interpretaciones y pruebas futuras quedan explícitas sin acreditar comportamiento Wix.')]
t['history'].append({'date':now,'status':'done','note':'Comparación integral cerrada con auditorías documentales locales: Help Text, metadatos, referencias, primary display, permisos e índices de apoyo. Los controles de ejecución/exposición se conservan como aceptación futura.'})
next_task=tasks['ACA-BOOTSTRAP'];assert next_task['status']=='upcoming'
next_task['status']='current';next_task['nextAction']='Preparar en local el orden de creación y carga por pasadas: catálogos y campos requeridos primero, EntityRegistry/sourceItemId y enlaces opcionales después; conservar referencias y requiredness del esquema bloqueado.'
next_task['history'].append({'date':now,'status':'current','note':'Siguiente objetivo documental tras cerrar ACA-SCHEMA-ALIGN; todavía sin cambios en Wix.'})
for id in ['ACA-CMS-003-TEST','ACA-PUBLIC-REVIEW','ACA-BACKEND-TEST']:
 task=tasks[id]
 task['acceptance'].append('Checkpoint de DirectoryProfiles: probar lectura anónima/API y drafts para entityRef, recordCode, statusRef, personRef y perfiles ocultos/no aprobados; escalar cualquier conflicto efectivo antes de publicar.')
 task['history'].append({'date':now,'status':task['status'],'note':'Handoff explícito de la auditoría de fuentes: exposición de DirectoryProfiles pendiente de prueba efectiva, sin modificar esquema congelado.'})
r['asOf']=now;r['schemaAlignmentRecorded']=True
r['project']['workspaceLabel']='clementepg/acclam · main · registro autoritativo'
r['project']['checkpointSummary']='Alineación de fuentes cerrada para 77 colecciones y 1,083 campos, con originales preservados. El siguiente trabajo es el bootstrap local; Wix continúa sin implementación ni pruebas verificadas.'
r['project']['nextGate']='Diseñar y ensayar el plan de bootstrap y referencias por pasadas antes de preparar importaciones finales.'
r['checkpoints'].append({'date':now,'note':'Repositorio clementepg/acclam seleccionado como master por el usuario. ACA-SCHEMA-ALIGN cerrado con evidencia documental; ACA-BOOTSTRAP pasa a current. Publicar el visor no lanza el sitio Wix.'})
write(REGISTER,r)
print('Schema source alignment recorded with private evidence; no locked source file changed.')
