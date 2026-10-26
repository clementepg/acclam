"""One-time register initialization. Never use to regenerate an existing register."""
import csv
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import QUEST, WORKSPACE, REGISTER, read, write, digest

if REGISTER.exists():
    raise SystemExit('Register exists: edit it with dated history; do not reseed or overwrite human corrections.')

NOW=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
facts=read(WORKSPACE/'handoff/locked_baseline_facts.json')
schema=read(QUEST/'sources/schema_inventory.json')
PDF=schema['sourceRelativePath']
DICT=schema['dictionary']['relativePath'] if 'relativePath' in schema['dictionary'] else schema['collections'][0]['dictionaryRelativePath']
KIT='Website architecture/schema_v3_0/ACCLAM_V3_FROZEN_Collection_Kit.xlsx'
PACK='CMS/Draft preparation/outputs/01a17904-81c8-7fe3-8ac4-e3efb7e3fa16'

def source(path,label,locator,page=None):
    item={'path':path,'label':label,'locator':locator}
    if page:item['page']=page
    return item
def pdf(pages,label='Plan v3.0 bloqueado'):
    return source(PDF,label,'PDF físico: '+', '.join(map(str,pages)),pages[0])
def js(path,locator,label='Evidencia local'):
    return source(path,label,locator)
def proof(path,kind,finding,assertions=None,contains=None):
    return {'path':path,'sha256':digest(WORKSPACE/path),'class':kind,'finding':finding,
            'reviewedBy':'Codex, inspección local del 26 de octubre de 2026',
            'assertions':[{'pointer':p,'equals':v} for p,v in (assertions or [])], 'contains':contains or []}

# Directly measured files, not handoff completion claims.
csv_names={'speakers':'Ponentes','events':'Eventos','sessions':'Sesiones','relationships':'Relaciones_sesion_ponente','evidence':'Evidencia','issues':'Pendientes'}
counts={}; measured={}
for key,name in csv_names.items():
    path=f'{PACK}/CSV_preliminares/{name}.csv'
    with (WORKSPACE/path).open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    counts[key]=len(rows); measured[path]=digest(WORKSPACE/path)
    if key=='speakers':
        approval_fields=list(rows[0])
        counts['speakerApprovalColumn']=next((x for x in approval_fields if 'approv' in x.lower()),'not present')
inventory=read(WORKSPACE/'CMS/Draft preparation/sources/complete_inventory.json')
counts['inventoryFiles']=sum(x.get('file_or_folder')!='folder' for x in inventory)
counts['inventoryFolders']=sum(x.get('file_or_folder')=='folder' for x in inventory)
counts['selectedTextSources']=len(read(WORKSPACE/'CMS/Draft preparation/sources/drive_text.json'))
audit={'reviewedAt':NOW,'meaning':'Local file inventory and preliminary output counts only; no accuracy approval, final V3 mapping, Wix import or publication is established.',
       'lockedPdf':{'path':PDF,'sha256':digest(WORKSPACE/PDF),'physicalPages':schema['physicalPageCount']},
       'draftCounts':counts,'measuredFiles':measured,'wixIndependentlyInspected':False}
write(QUEST/'evidence/INITIAL_LOCAL_AUDIT.json',audit)

milestones=[]
def milestone(id,title,short,subtitle):
    item={'id':id,'title':title,'shortLabel':short,'subtitle':subtitle,'objectives':[]};milestones.append(item);return item
def task(m,id,title,phase,scope,pages,deps=None,owner='Technical Admin / responsable propuesto',reviewer='Data Steward ACCLAM / por confirmar',acceptance=None,next_action=None,blockers=None,sources=None,status='upcoming',evidence=None,proofs=None,summary=None):
    item={'id':id,'title':title,'phase':phase,'status':status,'scope':scope,'owner':owner,'reviewer':reviewer,
          'acceptance':acceptance or ['Guardar resultado y evidencia revisable del alcance descrito; documentar excepciones.'],
          'nextAction':next_action or 'Revisar la fuente indicada y preparar la evidencia del resultado descrito.',
          'dependencies':list(dict.fromkeys(deps or [])),
          'blockers':blockers or [],'sources':sources or [pdf(pages)],'evidence':evidence or [],'proofs':proofs or [],
          'evidenceSummary':summary or 'Requisito del plan bloqueado; ejecución y resultado aún sin verificar.',
          'history':[{'date':NOW,'status':status,'note':'Alta inicial desde fuentes bloqueadas; estado sustentado únicamente por la evidencia explícita.'}]}
    m['objectives'].append(item);return item

m=milestone('ACA-M00','Punto de partida y fuentes','Fuentes','Identidad del plan, preparación existente y siguiente trabajo local.')
audit_path='work/launch-quest/evidence/INITIAL_LOCAL_AUDIT.json'
task(m,'ACA-BASELINE','Verificar identidad de la fuente bloqueada','design','Confirmar el PDF autorizado, su hash y páginas físicas; establecer la convención de citas.',[1,15,108,205,232],status='done',
     evidence=[js(audit_path,'/lockedPdf','Medición del PDF'),js('work/launch-quest/sources/locked_pages.json','/physicalPageCount; /sourceSha256','Extracción por página')],
     proofs=[proof(audit_path,'source_review','Hash medido de la fuente autorizada y conteo de la extracción.',[('/lockedPdf/sha256',schema['sourceSha256']),('/lockedPdf/physicalPages',252)]),
             {'path':PDF,'sha256':schema['sourceSha256'],'class':'source_review','sourceIdentityOnly':True,'finding':'Fuente binaria fijada por SHA256; páginas y hallazgos en la extracción enlazada.','reviewedBy':'Codex, revisión local','assertions':[],'contains':[]}],
     summary='PDF autorizado fijado por SHA256 y 252 páginas físicas. Esto acredita la fuente de diseño.',next_action='Usar esta fuente y sus páginas físicas para cada cambio posterior.')
# Binary source proofs use the hash-only source identity exception in validator.
task(m,'ACA-DRAFT-LOCAL','Verificar el lote preliminar existente','preparation','Contar los CSV locales y fijar el alcance parcial del inventario, sin aprobar su contenido.',[251],deps=['ACA-BASELINE'],status='done',
     sources=[js('handoff/CURRENT_STATE.json','/verifiedLocalPreparation','Handoff fechado'),js(f'{PACK}/LEEME.txt','ALCANCE; reglas de extracción','Límites históricos del paquete')],
     evidence=[js(audit_path,'/draftCounts; /measuredFiles','Conteos locales')],proofs=[proof(audit_path,'local_preparation','CSV contados directamente; lectura parcial del Drive.',[(f'/draftCounts/{k}',v) for k,v in {'speakers':23,'events':3,'sessions':20,'relationships':23,'evidence':145,'issues':15,'inventoryFiles':455,'selectedTextSources':13}.items()])],
     summary='Existen 23 ponentes, 3 eventos, 20 sesiones y 145 filas de evidencia en el lote preliminar; falta el mapeo final v3.0 y revisión humana.',
     next_action='Conservar los originales y resolver fuentes, campos requeridos y conflictos durante la preparación.')
schema_path='work/launch-quest/sources/schema_inventory.json'
task(m,'ACA-SCHEMA-MAP','Mapear las 77 colecciones y sus fuentes','design','Inventariar nombres globales, carpetas, campos y referencias; delimitar exactamente las dimensiones comparadas.',[7,8,9,248],deps=['ACA-BASELINE'],status='done',
     evidence=[js(schema_path,'/collections; /reconciliation; /caveats','Cruce medido del esquema'),js('handoff/COLLECTION_SOURCE_MAP.json','colecciones y prefijos de fase','Mapa de fuentes del handoff')],
     proofs=[proof(schema_path,'source_review','Se revisó el inventario de fuentes y sus límites; no acredita Wix ni equivalencia integral.',[('/physicalPageCount',252),('/reconciliation/collectionCount',77),('/reconciliation/fieldKeyLabelTypeRequiredTextMatchCount',1083),('/reconciliation/referenceTargetTextMatchCount',456),('/reconciliation/allTemplateHeadersMatchDictionaryOrder',True)],contains=['"templateFilenamePrefixIsGlobalId": false'])],
     summary='77 colecciones identificadas con el índice global del PDF. Los prefijos de CSV indican fase de importación; Help Text, XLSX y revisión semántica siguen pendientes.',next_action='Completar ACA-SCHEMA-ALIGN antes de preparar archivos finales o construir el esquema.')
task(m,'ACA-SCHEMA-ALIGN','Cerrar la comparación integral PDF · XLSX · CSV','design','Completar la matriz de los 1,083 campos: Field ID, tipo, requerido, etiqueta, Help Text, primary display, referencias, índices, permisos y reglas. Conservar diferencias con decisión explícita.',[19,23,107,112,248],deps=['ACA-SCHEMA-MAP'],status='current',
     sources=[pdf([19,23,107,112,248]),js(schema_path,'/reconciliation; /caveats; /nextActions','Comparación parcial ya medida'),js(KIT,'hojas de colección y diccionario','Collection Kit de apoyo'),js(DICT,'1,083 filas de datos; columnas exactas','Diccionario CSV')],
     acceptance=['Matriz con todos los campos y localizadores exactos del PDF/XLSX/CSV; comparación de Help Text y metadatos faltantes.','Lista de diferencias, decisiones del responsable y campos pendientes; no sustituir tipos/relaciones por aproximaciones.','Fuentes y revisiones fijadas por hash; confirmar alcance de equivalencia y límites.'],
     next_action='Abrir el Collection Kit y comparar Help Text, primary display, índices y permisos de cada colección con las páginas del PDF; registrar diferencias sin editar las fuentes bloqueadas.',
     summary='El cruce automático ya cubre nombres, conteos, claves, etiquetas, tipos, requerido y targets de referencia; falta la comparación integral y su revisión semántica.')

m=milestone('ACA-M01','Entorno y control de acceso','Fundamentos','Preparar staging y la separación entre página, CMS, backend y autoridad institucional.')
task(m,'ACA-WIX-INVENTORY','Inspeccionar el estado real de Wix','design','Obtener inventario fechado del sitio/entornos, colecciones, roles, páginas, backend y automations; contrastar con la declaración de colecciones no creadas.',[235,236],deps=['ACA-BASELINE'],blockers=['Se requiere acceso autorizado a Wix para esta inspección futura.'],acceptance=['Inventario y capturas/exportaciones con fecha y sitio/entorno identificados.','Distinguir ausente, diseñado, construido y probado; no inferir por archivos locales.'])
task(m,'ACA-ENV-STAGING','Preparar respaldo y entorno staging','wix_construction','Respaldar/exportar datos críticos y definir entorno de ensayo y restauración antes de datos reales.',[235,252],deps=['ACA-WIX-INVENTORY'],blockers=['Acceso y cambios en Wix pendientes de autorización.'],acceptance=['Backup identificable y restaurable, staging aislado y registros sintéticos.','Responsable técnico y procedimiento de restauración documentados.'])
task(m,'ACA-CMS-FOLDERS','Crear las nueve carpetas CMS exactas','wix_construction','Crear etiquetas de carpeta congeladas y usar números globales 01–77; la carpeta no configura permisos.',[7,235],deps=['ACA-ENV-STAGING','ACA-SCHEMA-ALIGN'],acceptance=['Capturas/export del sitio con las nueve carpetas exactas del PDF.'])
task(m,'ACA-SEC-PLAN','Aprobar matriz de permisos, roles y autoridad','design','Separar Page permissions, CMS permissions, autorización backend, AccessAssignments, Appointments y AuthorityGrants. Incluir los 11 roles y restricciones de datos.',[11,19,20,209,236,237],deps=['ACA-BASELINE'],reviewer='Consejo / Compliance / Technical Admin, por confirmar',acceptance=['Matriz actor×acción×campo×estado; distinguir gobierno, acceso y autoridad legal.','Deliberación de exposición pública de DirectoryProfiles, geografía y Certificates; ningún booleano suple acceso.','Responsables/revisores confirmados institucionalmente y restricciones registradas.'])
task(m,'ACA-ROLES-CONFIG','Configurar roles y asignaciones vigentes','wix_construction','Crear acceso por rol con vigencias; mantener separación de funciones y capacidad de revocación.',[209,236,237],deps=['ACA-ENV-STAGING','ACA-SEC-PLAN','ACA-CMS-026-BUILD','ACA-CMS-027-BUILD','ACA-CMS-028-BUILD'],acceptance=['Roles reales configurados y sujetos de ensayo por rol; fechas y revocación comprobables.'])
task(m,'ACA-BACKEND','Construir autorización backend y DTOs seguros','wix_construction','Resolver identidad en servidor, validar rol/alcance/estado, devolver DTO permitido, registrar TimelineEvents; no confiar en personRef del navegador.',[210,228,245,246],deps=['ACA-ROLES-CONFIG','ACA-CMS-074-BUILD'],acceptance=['Código revisado con métodos y controles explícitos; patrón del PDF adaptado y verificado con documentación oficial vigente.','Inventario de acciones sensibles, validación de transición y auditoría.'])
task(m,'ACA-BACKEND-TEST','Probar el límite de autorización','testing','Probar URL/API directa, anónimo, miembro ajeno, rol equivocado, acceso revocado y nombramiento vencido.',[212,237,245,250,252],deps=['ACA-BACKEND'],acceptance=['Resultados por actor/acción/estado con datos sintéticos; ningún acceso indebido ni campos privados en DTO.'])
task(m,'ACA-BOOTSTRAP','Diseñar bootstrap y pasadas de referencias','design','Resolver ciclos y auto referencias, EntityRegistry, TaxonomyTerms, People e ImportBatches. Crear estructuras vacías antes de sembrar catálogos y fijar requiredness.',[24,26,39,185,186,188,235,251],deps=['ACA-SCHEMA-ALIGN'],sources=[pdf([24,26,39,185,186,188,235,251]),js(schema_path,'/reconciliation','Grafo de referencias y ciclos')],acceptance=['Orden concreto de creación y carga por pasadas con identidad de destino, relaciones requeridas y autociclos; ensayo planificado.','Cada excepción de bootstrap documentada sin relajar silenciosamente el esquema.'])
task(m,'ACA-INTEGRATIONS','Definir contratos con sistemas externos','design','Documentar Wix, Google Workspace, contabilidad, proveedores y autoridades externas señaladas por el plan; owner, datos, acceso, secreto en gestor institucional y evidencia requerida.',[4,75,77,88,224],deps=['ACA-SEC-PLAN'],acceptance=['Inventario de contratos y responsable; ninguna conexión presumida ni credenciales en CMS/Settings.','Contabilidad externa mantiene el ledger; destinos de reportes se validan con Compliance.'])

# One consistent five-stage chain per frozen collection. Reference graph remains
# source data, not task dependencies (cycles require a reviewed multipass plan).
by_name={c['name']:c for c in schema['collections']}
for folder in facts['cms_folders']:
    num=folder['number']; m=milestone(f'ACA-MCMS{num:02}',folder['name'],f'CMS {num:02}',folder['purpose'])
    for c in [x for x in schema['collections'] if x['folder']==folder['name']]:
        n=c['id'];base=f'ACA-CMS-{n.zfill(3)}';name=c['name'];pages=c['physicalPageRangeInclusive'];count=c['lockedFieldCount']
        refs=', '.join(x['field']+' → '+x['targetCollection'] for x in c['references']) or 'Sin referencias de colección especificadas.'
        sources=[pdf(pages,f'{n} {name} · especificación'),js(c['dictionaryRelativePath'],f'CSV filas {c["dictionaryCsvRowsInclusive"][0]}–{c["dictionaryCsvRowsInclusive"][1]}',f'{name} · diccionario'),js(c['templateRelativePath'],'Encabezado vacío; prefijo = fase de importación',f'{name} · plantilla'),js(schema_path,f'/collections/{int(n)-1}','Mapa de campos y referencias')]
        common=f'{n} {name}: {count} campos; primary display {c["primaryDisplay"]}; {c["privacyClassification"]}; permisos especificados {c["wixPermissionMode"]}. {c["purpose"]}'
        task(m,base+'-PREP',f'{n} {name} · preparar datos','preparation',common+' Preparar fuentes por campo, faltantes, conflictos y correcciones humanas. '+refs,pages,deps=['ACA-SCHEMA-ALIGN','ACA-MIG-SOURCES'],sources=sources,
             acceptance=['Mapeo origen→Field ID y evidencia por campo; ninguna invención para requeridos.','Claves estables, duplicados, datos faltantes y decisión de carga vacía/no aplicable documentados.','Archivos candidatos y decisiones de steward preservan correcciones previas.'],next_action=f'Localizar fuentes para {name}, comparar requeridos y preparar candidatos trazables; abrir DataQualityIssue si faltan datos.')
        task(m,base+'-BUILD',f'{n} {name} · construir esquema Wix','wix_construction',common+' Crear Field IDs/tipos/Help Text/índices/relaciones y permisos exactos antes de datos reales.',pages,deps=['ACA-CMS-FOLDERS','ACA-SEC-PLAN'],sources=sources,
             acceptance=[f'Export/capturas de {name} en staging: {count} campos y metadatos comparados con el PDF.','References/Multi-References con targets reales; privacy label no sustituye configuración CMS.','Registrar sitio, fecha, operador y diferencias aprobadas.'])
        task(m,base+'-TEST',f'{n} {name} · probar estructura y permisos','testing',common+' Ensayar registro sintético, validaciones, referencias y exposición efectiva.',pages,deps=[base+'-BUILD'],sources=sources,
             acceptance=['Registro sintético válido y casos inválidos/requeridos/referencias; round trip sin pérdidas.','Anónimo, miembro, creador, rol pertinente y admin: lecturas/escrituras positivas/negativas con evidencia.','Confirmar primary display e índices y ausencia de exposición privada antes de cargar datos reales.'])
        task(m,base+'-IMPORT',f'{n} {name} · importar en staging','import',common+' Ejecutar lote autorizado y resolver IDs por plan de pasadas; reconciliar contra origen.',pages,deps=[base+'-PREP',base+'-TEST','ACA-MIG-PLAN','ACA-BOOTSTRAP'],sources=sources,
             acceptance=['ImportBatch, LegacyRecordMap y correspondencia origen→ID real; conteos importado+fusionado+rechazado/cuestionado concilian con origen.','Referencia a targets reales, reporte de errores y export posterior; lote vacío justificado también exige evidencia.','Sin DataQualityIssue CRITICAL abierto; no sobrescribir correcciones humanas.'])
        task(m,base+'-REVIEW',f'{n} {name} · revisar contenido ACCLAM','acclam_review',common+' Revisar exactitud, vigencia, consentimiento y uso permitido del contenido cargado en staging.',pages,deps=[base+'-IMPORT'],owner='Responsable de contenido ACCLAM / por confirmar',reviewer='Revisor ACCLAM independiente / por confirmar',sources=sources,
             acceptance=['Revisor humano identificado, fecha, registros incluidos/excluidos y correcciones trazables.','Vigencias/autoridad/credenciales/participaciones verificadas con fuentes actuales aplicables.','Aprobación de contenido no equivale a publicar; resultados pendientes permanecen explícitos.'])

m=milestone('ACA-MMIG','Migración y calidad','Migración','Fuentes, lotes, identidades y ensayo completo antes de producción.')
task(m,'ACA-MIG-SOURCES','Congelar inventario de fuentes y responsables','preparation','Extender la instantánea parcial de 455 archivos/13 textos al alcance relevante de las 77 colecciones; fijar hash, fecha y owner de cada fuente.',[185,251],deps=['ACA-DRAFT-LOCAL'],acceptance=['Inventario con cobertura por colección y fuentes faltantes; snapshots/hashes y custodios.','La existencia en Drive no autoriza publicación; acceso a documentos privados separado.'])
task(m,'ACA-MIG-PLAN','Preparar transformación y conciliación por lotes','preparation','Definir ImportBatch, claves canónicas, LegacyRecordMap, normalización, deduplicación, Documents/DocumentVersions/ContextLinks y DataQualityIssues.',[177,179,181,185,186,188,251],deps=['ACA-MIG-SOURCES','ACA-BOOTSTRAP'],acceptance=['Mapeo de origen, reglas de descarte, normalización de fechas/zonas y catálogos; coincidencias débiles no se fusionan automáticamente.','Algoritmo/pasadas ensayables y conservación de correcciones humanas; fuente=importado+fusionado+rechazado/cuestionado.'])
task(m,'ACA-MIG-DRAFT-MAP','Mapear el lote de ponentes y congresos a v3.0','preparation','Convertir claves preliminares al esquema real; People requiere firstName/displayName/primaryEmail, entidad y estado. Invitaciones no prueban aceptación.',[29,125,128,130,251],deps=['ACA-MIG-PLAN'],sources=[pdf([29,125,128,130,251]),js(f'{PACK}/CSV_preliminares/Pendientes.csv','15 asuntos de revisión','Conflictos del lote')],acceptance=['Trazabilidad por campo para People/DirectoryProfiles/Events/Sessions/SpeakerAssignments y relaciones.','Requeridos faltantes quedan en staging con issue; resolver año 2027/2026, Guadalajara y horarios contradictorios sin adivinar.'])
task(m,'ACA-MIG-REHEARSAL','Cerrar ensayo integral de migración','testing','Ejecutar la migración completa en staging, conciliar todas las colecciones y probar recuperación.',[235,244,251,252],deps=[f'ACA-CMS-{i:03}-IMPORT' for i in range(1,78)],acceptance=['Informe de ensayo por colección y lote; errores críticos resueltos y diferencias explicadas.','Restauración probada y protección de correcciones humanas.'])

member=milestone('ACA-MMEMBER','Mi ACCLAM y área de estudiante','Mi ACCLAM','Once páginas de autoservicio con datos limitados a la persona autenticada.')
ops=milestone('ACA-MOPS','Centro de Operaciones','Operaciones','Paneles de Consejo, Presidencia, Tesorería, Membresía, Educación y Cumplimiento.')
for i,b in enumerate(facts['page_blueprints'],1):
    m=member if i<=11 else ops; base=f'ACA-PAGE-{i:02}';name=b['name'];pages=b['source_pdf_pages'];cols=b['collections']
    deps=['ACA-BACKEND']+[f'ACA-CMS-{int(by_name[x]["id"]):03}-BUILD' for x in cols]
    scope=b['purpose']+'. '+b['security_note']
    task(m,base+'-BUILD',f'{name} · construir','wix_construction',scope,pages,deps=deps,owner=f'{b["role"]} + Technical Admin / propuestos',acceptance=['Página restringida, DTO permitido, acciones autorizadas en servidor y ayuda vigente integrada.','Estados loading/sin registros/normal/bloqueado/vencido/error y filtros indexados/paginación.'])
    task(m,base+'-TEST',f'{name} · probar','testing',scope,pages+[228,252],deps=[base+'-BUILD','ACA-BACKEND-TEST'],acceptance=['Prueba de rol correcto/equivocado/anónimo, datos de otra persona, URL/API y acción material con auditoría.','Móvil/escritorio, teclado, etiquetas, contraste, vacíos/error y búsquedas paginadas con resultados guardados.'])
    task(m,base+'-REVIEW',f'{name} · revisión ACCLAM','acclam_review',scope,pages,deps=[base+'-TEST'],owner=f'{b["role"]} ACCLAM / por confirmar',reviewer='Revisor ACCLAM del área / por confirmar',acceptance=['Prueba de uso guiada por responsable humano, texto/acciones/contexto exactos y aceptación fechada.'])

m=milestone('ACA-MDOMAIN','Flujos institucionales de extremo a extremo','Flujos','La base CMS se traduce en acciones, evidencia y estados operables.')
domain_titles=['Identidad y directorio público','Solicitud y renovación de membresía','Gobierno y entrega de cargo','Acceso y autoridad institucional','Procedimientos, tareas y mensajes','Actividades, impacto y becas','Eventos, participación y créditos','Emisión, QR y revocación de constancias','Obligaciones y calendario','Filings, auditorías, casos y retención','Finanzas, donaciones, convenios y activos','Documentos, evidencia y trazabilidad']
for i,d in enumerate(facts['domain_model'],1):
    base=f'ACA-FLOW-{i:02}';title=domain_titles[i-1];pages=d['source_pdf_pages']
    task(m,base+'-DESIGN',title+' · definir transición','design',d['text'],pages,deps=['ACA-SEC-PLAN','ACA-SCHEMA-ALIGN'],acceptance=['Diagrama de estados/eventos/owner/revisor/autoridad y excepciones; entradas, salidas y fuentes actuales.','Dependencias de colecciones y métodos backend identificadas antes de implementación.'])
    task(m,base+'-BUILD',title+' · implementar flujo','wix_construction',d['text'],pages,deps=[base+'-DESIGN','ACA-BACKEND'],acceptance=['Código/interfaz/acciones conectados a colecciones y evidencia; transiciones autorizadas y auditadas.','Referenciar tareas de página/CMS relacionadas; no duplicar estados ni omitir validaciones.'])
    task(m,base+'-TEST',title+' · ensayo integral','testing',d['text'],pages+[252],deps=[base+'-BUILD','ACA-BACKEND-TEST'],acceptance=['Caso válido, inválido, duplicado, falta de referencia y estado/autoridad vencidos; evidencia de principio a fin.','Restricciones del dominio y revisión humana respetadas; fallos y corrección documentados.'])

m=milestone('ACA-MAUT','Automations deterministas','Automations','20 blueprints del plan: configurar, probar ramas y revisar cada resultado.')
task(m,'ACA-AUT-PLAN','Definir contratos de las 20 automations','design','Confirmar trigger/filtros, owner, estados, Patch frente a Update, idempotencia, no loops, reintentos, rollback y aprobación de comunicaciones.',[237,238,252],deps=['ACA-SEC-PLAN','ACA-INTEGRATIONS'],acceptance=['Matriz AUT-001–020 con dependencia de colección/flujo y rutas de aprobación; documentación Wix vigente al implementar.'])
for b in facts['automation_blueprints']:
    base='ACA-'+b['id'];pages=b['source_pdf_pages'];scope=f'Trigger: {b["trigger"]}. Acciones: {b["actions"]}. Construcción prevista: {b["planned_implementation"]}.'
    task(m,base+'-BUILD',b['id']+' · '+b['name'],'wix_construction',scope,pages,deps=['ACA-AUT-PLAN','ACA-BACKEND'],acceptance=['Configuración/código real en staging con trigger y filtros exactos, owner, approval cuando aplica y rollback.','La tarea de diseño enlaza las colecciones y flujos específicos necesarios antes de activar.'])
    task(m,base+'-TEST',b['id']+' · probar ramas','testing',scope,pages+[252],deps=[base+'-BUILD'],acceptance=['Trigger/caso negativo/repetición/reintento/sin loop y estado inválido; Activity Log y salidas verificadas.','Comunicaciones de prueba con destinatarios aprobados; decisiones sensibles siguen siendo deterministas y autorizadas.'])
    task(m,base+'-REVIEW',b['id']+' · revisar y habilitar','acclam_review',scope,pages,deps=[base+'-TEST'],owner='Owner operativo ACCLAM / por confirmar',reviewer='Aprobador ACCLAM / por confirmar',acceptance=['Aprobación humana de reglas, textos, destinatarios/segmentos, umbrales, calendario y responsabilidad; alcance exacto identificado.'])

m=milestone('ACA-MAI','Asistencia de IA con revisión humana','Asistencia IA','12 usos previstos; disponibilidad y límites se confirman al implementarlos.')
for b in facts['ai_assistance_blueprints']:
    base='ACA-'+b['id'];pages=b['source_pdf_pages'];scope=b['name']+'. Límites: '+b['boundary']
    task(m,base+'-PREP',b['id']+' · '+b['name'],'preparation',scope,pages,deps=['ACA-SEC-PLAN'],acceptance=['Ficha con herramienta/capacidad actual verificada, entradas mínimas, datos permitidos y revisor; decidir uso o alternativa con evidencia.','Prompt/configuración propuesta conserva IDs exactos y autoridad humana; no activar sistemas externos por esta tarea local.'])
    task(m,base+'-TEST',b['id']+' · validar asistencia','testing',scope,pages,deps=[base+'-PREP'],acceptance=['Piloto aislado con entradas sintéticas, revisión de salida, incertidumbre y fallos; humano confirma el uso permitido.','No aprueba membresía, credenciales, disciplina, dinero, autoridad, filings ni elegibilidad de certificados.'])

m=milestone('ACA-MGOV','Manuales, formularios y continuidad','Continuidad','Responsables humanos, memoria institucional y procedimientos dentro del trabajo.')
extras=[
('ACA-NAV','Construir My Work, búsqueda y Document Center','wix_construction','Navegación por responsabilidad; tareas accionables, documentos/versiones, búsqueda y ayuda/procedimiento contextual.',[13,208,230],['ACA-BACKEND']),
('ACA-FORM-MEMBER','Reconstruir solicitud de membresía en Wix','wix_construction','Reemplazar formulario legado de alta con validación, requeridos, consentimiento versionado y workflow de aplicación; no crear membresía por simple envío.',[48,55,225,238],['ACA-FLOW-02-BUILD']),
('ACA-FORM-ACTIVITY','Reconstruir reporte anual de actividades','wix_construction','Reemplazar Google Form legado por flujo de InstitutionalActivities y evidencia; reportingYear se deriva de fecha real, conservar formVersion. Destino/regulador requiere ratificación.',[91,93,239,250,251],['ACA-FLOW-06-BUILD','ACA-INTEGRATIONS']),
('ACA-LEGACY-POLICY','Revisar conmutador y uso del logo','acclam_review','Preservar ACCLAM-PR-CONM-005 y ACCLAM-PR-FORMATOS-001; revisar obsolescencia y ratificar responsables/textos antes de uso vigente.',[12,250,251],['ACA-BASELINE']),
('ACA-ROLE-MANUALS','Aprobar manuales para los 11 roles','acclam_review','Integrar procedimientos, permisos, aprobación independiente, excepciones, respaldo y responsabilidades; responsables nominales deben ser confirmados por ACCLAM.',[209,230,251],['ACA-NAV','ACA-SEC-PLAN']),
('ACA-HANDOVER','Ensayar relevo de cargo y accesos','testing','Transferir/revocar sistemas internos/externos; revisar documentos, tareas y obligaciones abiertas y registrar entrega-recepción antes de cerrar Appointments.',[11,230,239],['ACA-FLOW-03-TEST','ACA-FLOW-04-TEST']),
('ACA-PUBLIC-REVIEW','Aprobar directorio y exposición pública','acclam_review','Revisar consentimiento, vigencia, campos públicos y mecanismo efectivo de publicación con prueba de acceso; People permanece privado.',[30,31,212,218,237],['ACA-FLOW-01-TEST','ACA-PAGE-08-TEST']),
('ACA-COMPLIANCE-REVIEW','Ratificar obligaciones y autoridades actuales','acclam_review','Confirmar con owner institucional obligaciones, destinatarios, fundamento, umbrales, fechas y acreditaciones con fuentes oficiales vigentes; la lista del plan no prueba vigencia.',[147,149,150,243,250],['ACA-FLOW-09-DESIGN'])]
for id,title,phase,scope,pages,deps in extras:
    item=task(m,id,title,phase,scope,pages,deps=deps,reviewer='Responsable institucional ACCLAM / por confirmar',acceptance=['Resultado revisable con prueba funcional o aprobación humana acorde a la fase; decisiones y versiones fechadas.'])
    if id in ['ACA-FORM-MEMBER','ACA-FORM-ACTIVITY']:
        item['sources'].append(js('handoff/shared_chat_findings.txt','Forms and operational evidence','Petición histórica de formularios'))

task(m,'ACA-FORMS-SOURCE','Inventariar versiones de los dos formularios legados','preparation','Conservar preguntas, opciones, avisos, fechas y versiones de solicitud de membresía y reporte de actividades; definir correspondencia de campos y quién confirma destinatario y reglas actuales.',[48,50,56,91,94],deps=['ACA-MIG-SOURCES'],sources=[pdf([48,50,56,91,94]),js('handoff/shared_chat_findings.txt','Forms and operational evidence','Antecedente de formularios')],acceptance=['Cruce de preguntas y avisos originales hacia campos v3.0 con versiones conservadas.','Destinatario del reporte anual y reglas vigentes resueltos por owner institucional o explícitamente pendientes.'])
for id,title,scope,pages,deps in [
    ('ACA-MYWORK','My Work y tareas accionables','Alertas críticas, vencimientos y aprobaciones llevan a listas; procedimiento vigente, evidencia exigida y Awaiting Approval sin autoaprobación.',[230],['ACA-NAV','ACA-FLOW-05-BUILD']),
    ('ACA-DOCUMENT-CENTER','Document Center y versiones','Buscar por código/nombre/contexto y abrir versión vigente; una revisión no crea otro documento lógico; respetar rol, confidencialidad y retención.',[177,180,181,230],['ACA-NAV','ACA-FLOW-12-BUILD']),
    ('ACA-EXCEPTION','Case / Policy Exception','Capturar razón, autoridad y periodo de excepción; no alterar hechos para saltar reglas; ocultar notas internas al miembro.',[161,162,230],['ACA-FLOW-10-BUILD']),
    ('ACA-QR','Verificación pública de constancias','Token único devuelve solo certificateNumber/status/name/event/credits por backend; sin acceso directo público a Certificates ni PDF no autorizado; revocada/reemplazada visibles.',[145,146,217,252],['ACA-FLOW-08-BUILD']),
    ('ACA-DIRECTORY','Directorio público y control de publicación','Mostrar únicamente DirectoryProfiles autorizado con consentimiento y revisión; comprobar borradores/ocultos/no aprobados y referencias privadas por URL/API.',[20,30,31,218,237],['ACA-FLOW-01-BUILD'])]:
    task(m,id+'-BUILD',title+' · construir','wix_construction',scope,pages,deps=deps,acceptance=['Interfaz/endpoint real en staging con permisos exactos, estados y evidencia auditable.'])
    task(m,id+'-TEST',title+' · probar','testing',scope,pages,deps=[id+'-BUILD','ACA-BACKEND-TEST'],acceptance=['Casos válidos/negativos y estados, pruebas por rol y datos ajenos; evidencia del resultado específico del alcance.'])
for name in ['ACA-FORM-MEMBER','ACA-FORM-ACTIVITY']:
    task(m,name+'-TEST',('Solicitud de membresía' if 'MEMBER' in name else 'Reporte de actividades')+' · probar formulario','testing','Ensayar requeridos, opciones, consentimiento/versiones, envío duplicado, permisos, acuse y mapeo correcto sin activar decisiones institucionales.',[48,56,91,238,239],deps=[name,'ACA-BACKEND-TEST'],acceptance=['Pruebas de versión, datos requeridos/erróneos, duplicados y rutas de aprobación; fecha/año derivado según dominio.'])
    task(m,name+'-REVIEW',('Solicitud de membresía' if 'MEMBER' in name else 'Reporte de actividades')+' · aprobar formulario','acclam_review','Owner ACCLAM confirma preguntas, avisos, versiones, destinatario y procedimiento con evidencia vigente.',[48,56,91,250],deps=[name+'-TEST'],acceptance=['Aprobación humana identificada y fechada con versión exacta y asuntos pendientes/exclusiones.'])

# Tighten domain/automation prerequisites before writing the one register.
all_tasks={t['id']:t for group in milestones for t in group['objectives']}
domain_folders={1:[1],2:[2],3:[3],4:[3],5:[4],6:[5],7:[6],8:[6],9:[7],10:[7],11:[8],12:[9]}
for i,folders in domain_folders.items():
    t=all_tasks[f'ACA-FLOW-{i:02}-BUILD']
    t['dependencies']+= [f'ACA-CMS-{int(c["id"]):03}-BUILD' for c in schema['collections'] if int(c['folderId']) in folders]
aut_collections=[['MembershipApplications','OperationalTasks','TimelineEvents'],['MembershipApplications','OperationalTasks','MessageTemplates'],['MembershipApplications','Memberships','MembershipPeriods','AccessAssignments','DirectoryProfiles'],['Credentials','VerificationEvents','OperationalTasks'],['Appointments','ExternalSystemAccess','AccessAssignments','OperationalTasks'],['Appointments','AccessAssignments','ExternalSystemAccess','TimelineEvents'],['InstitutionalActivities','OperationalTasks'],['InstitutionalActivities','OperationalTasks'],['Events','OperationalTasks','TaskTemplates'],['SpeakerAssignments','ConflictDisclosures','OperationalTasks'],['Participations','MessageTemplates'],['AttendanceRecords','AssessmentAttempts','CreditDefinitions','CreditAwards'],['CreditAwards','Certificates','CertificateTemplates'],['Certificates','TimelineEvents'],['ObligationInstances','OperationalTasks'],['Submissions','ObligationInstances'],['Audits','OperationalTasks'],['AuditFindings','OperationalTasks'],['Donations','FinancialTransactions','OperationalTasks'],['DataQualityIssues','ImportBatches']]
for i,names in enumerate(aut_collections,1):
    all_tasks[f'ACA-AUT-{i:03}-BUILD']['dependencies'] += [f'ACA-CMS-{int(by_name[name]["id"]):03}-BUILD' for name in names]
for id in ['ACA-FORM-MEMBER','ACA-FORM-ACTIVITY']:
    all_tasks[id]['dependencies'].append('ACA-FORMS-SOURCE')

m=milestone('ACA-MQA','Aceptación integral y recuperación','Aceptación','Ocho frentes de prueba del plan; los resultados se guardan con sus límites.')
qa_ids=[]
for i,a in enumerate(facts['acceptance_criteria'],1):
    id=f'ACA-QA-{i:02}';qa_ids.append(id)
    deps=['ACA-MIG-REHEARSAL','ACA-BACKEND-TEST']
    if i==1: deps=[f'ACA-CMS-{n:03}-TEST' for n in range(1,78)]
    if i==4: deps=[f'ACA-AUT-{n:03}-TEST' for n in range(1,21)]
    if i==5: deps=[f'ACA-PAGE-{n:02}-TEST' for n in range(1,18)]+['ACA-NAV']
    if i==6: deps=['ACA-FLOW-08-TEST']
    task(m,id,'QA · '+['Esquema completo','Acceso y seguridad','Transiciones y auditoría','Automations','Interfaces y accesibilidad','Constancias y QR','Cumplimiento y recuperación','Rendimiento y preparación de lanzamiento'][i-1],'testing',a['text'],a['source_pdf_pages'],deps=deps,acceptance=['Informe reproducible con escenario, entorno, fecha, esperado/obtenido, evidencia y defectos/resolución.','No contar pruebas diseñadas como ejecutadas; defectos críticos bloquean aceptación.'])

m=milestone('ACA-MRELEASE','Revisión institucional y lanzamiento','Lanzamiento','Cada puerta exige su propia evidencia y autorización del alcance externo.')
task(m,'ACA-ACCEPTANCE','Aceptar el alcance v3.0 por ACCLAM','acclam_review','Obtener aprobación humana del alcance completo, pendientes/aceptaciones de riesgo y manuales; no confundir pruebas técnicas con aceptación institucional.',[230,252],deps=qa_ids+[f'ACA-CMS-{n:03}-REVIEW' for n in range(1,78)]+[f'ACA-PAGE-{n:02}-REVIEW' for n in range(1,18)]+[f'ACA-AUT-{n:03}-REVIEW' for n in range(1,21)]+['ACA-ROLE-MANUALS','ACA-PUBLIC-REVIEW','ACA-COMPLIANCE-REVIEW'],owner='Consejo ACCLAM / por confirmar',reviewer='Aprobador institucional autorizado / por confirmar',acceptance=['Acta/aprobación fechada con responsable identificado, evidencia de pruebas y contenido aprobado, exclusiones explícitas y siguientes responsables.'])
task(m,'ACA-RELEASE-PLAN','Aprobar freeze, rollback y ventana de salida','release','Definir freeze, backup final, migración, conciliación, smoke tests, responsables y monitoreo 48 horas; confirmar autorización para publicar.',[252],deps=['ACA-ACCEPTANCE'],blockers=['La solicitud actual autoriza solo archivos y visor local. Una publicación futura requiere autorización del usuario.'],acceptance=['Plan aprobado con ventana y responsables, criterios go/no-go, backup/restauración y autorización explícita del cambio externo.'])
task(m,'ACA-RELEASE-IMPORT','Migrar y conciliar producción','import','Ejecutar la migración final aprobada después del freeze y backup; preservar correcciones humanas y registrar lotes.',[251,252],deps=['ACA-RELEASE-PLAN'],acceptance=['Lotes, IDs, export posterior, conteos y diferencias de producción conciliados; sin issues críticos.'])
task(m,'ACA-RELEASE-LIVE','Publicar y ejecutar smoke tests','release','Publicar el resultado autorizado y probar acceso, directorio, membreśia, eventos, QR, tareas y controles de exposición según el alcance aprobado.',[252],deps=['ACA-RELEASE-IMPORT'],acceptance=['Receipt/URL/fecha/versión de publicación y pruebas públicas/restringidas con resultados; rollback disponible.'])
task(m,'ACA-RELEASE-MONITOR','Cerrar monitoreo de 48 horas y entrega','release','Vigilar errores, integridad, accesos, automations y reportes; entregar operación institucional con siguientes owners.',[252],deps=['ACA-RELEASE-LIVE'],acceptance=['Ventana real de 48h, observaciones y correcciones registradas, responsable de continuidad y aceptación de entrega.'])

all_tasks={t['id']:t for group in milestones for t in group['objectives']}
all_tasks['ACA-QA-05']['dependencies'] += [x+'-TEST' for x in ['ACA-MYWORK','ACA-DOCUMENT-CENTER','ACA-EXCEPTION','ACA-QR','ACA-DIRECTORY','ACA-FORM-MEMBER','ACA-FORM-ACTIVITY']]
all_tasks['ACA-ACCEPTANCE']['dependencies'] += ['ACA-FORM-MEMBER-REVIEW','ACA-FORM-ACTIVITY-REVIEW','ACA-HANDOVER','ACA-LEGACY-POLICY']
register={'schemaVersion':1,'asOf':NOW,'project':{
    'title':'ACCLAM · Launch Quest','subtitle':'De la arquitectura congelada a una oficina virtual operable.',
    'scopeNote':'El avance cuenta objetivos verificados del alcance registrado. No mide esfuerzo, tiempo transcurrido ni preparación para lanzar. Roles y revisores son propuestos hasta confirmación institucional. Wix no se ha inspeccionado en esta ejecución.',
    'checkpointSummary':'Registro inicial del alcance v3.0. Fuente bloqueada y preparación local verificadas; la implementación Wix y la revisión institucional siguen sin evidencia.',
    'nextGate':'Completar el cruce integral del esquema antes de preparar imports finales o construir Wix.',
    'workspaceLabel':'ACCLAM / Website / work / launch-quest','continuityUrl':'/source/work%2Flaunch-quest%2FREADME.txt','staleAfterDays':7},
    'sourceAuthority':{'path':PDF,'sha256':schema['sourceSha256'],'physicalPages':252},
    'authorization':'Solo archivos y visor local; ninguna acción externa se deriva de tareas futuras.',
    'inputSnapshots':[{'path':p,'sha256':digest(WORKSPACE/p)} for p in [DICT,KIT]+[c['templateRelativePath'] for c in schema['collections']]],
    'sourceSnapshots':['handoff/CURRENT_STATE.json','handoff/locked_baseline_facts.json','work/launch-quest/sources/schema_inventory.json'],
    'milestones':milestones,'checkpoints':[{'date':NOW,'note':'Inicialización desde fuente bloqueada, inventario parcial y comparaciones medidas; owners propuestos.'}]}
write(REGISTER,register)
coverage=[]
for c in schema['collections']:
    for suffix in ['PREP','BUILD','TEST','IMPORT','REVIEW']:
        coverage.append({'kind':'collection','sourceId':c['id'],'objectiveId':f'ACA-CMS-{int(c["id"]):03}-{suffix}'})
for group,items,suffixes in [('page',facts['page_blueprints'],['BUILD','TEST','REVIEW']),('automation',facts['automation_blueprints'],['BUILD','TEST','REVIEW']),('ai',facts['ai_assistance_blueprints'],['PREP','TEST'])]:
    for i,b in enumerate(items,1):
        base=f'ACA-PAGE-{i:02}' if group=='page' else 'ACA-'+b['id']
        for suffix in suffixes:coverage.append({'kind':group,'sourceId':b.get('id',b.get('name')),'objectiveId':base+'-'+suffix})
write(QUEST/'BASELINE_IDS.json',{'meaning':'Immutable scope/ID inventory, not a status store; extend explicitly when scope grows.','createdAt':NOW,'milestoneIds':[m['id'] for m in milestones],'objectiveIds':[t['id'] for m in milestones for t in m['objectives']],'requiredCoverage':coverage})
print(json.dumps({'register':str(REGISTER),'objectives':sum(len(m['objectives']) for m in milestones),'milestones':len(milestones)},ensure_ascii=False))
