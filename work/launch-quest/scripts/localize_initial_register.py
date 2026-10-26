"""Initial Spanish presentation pass, preserving IDs, evidence and statuses."""
from datetime import datetime
from zoneinfo import ZoneInfo
from quest import QUEST, REGISTER, read, write
r=read(REGISTER)
if r.get('spanishPresentationApplied'):raise SystemExit('Already applied; do not replay.')
now=datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(timespec='seconds')
schema=read(QUEST/'sources/schema_inventory.json')
tasks={t['id']:t for m in r['milestones'] for t in m['objectives']}
folder_text=['Identidad, organizaciones, geografía y vocabularios controlados.','Solicitudes, membresía, periodos, credenciales, verificación y consentimiento.','Gobierno, roles, nombramientos, autoridad, accesos y continuidad.','Políticas, procedimientos, tareas, mensajes y ajustes sin secretos.','Programas, actividad institucional, contribuciones, impacto y becas.','Eventos, educación, participación, asistencia, evaluación, créditos y constancias.','Cumplimiento, autorizaciones, obligaciones, filings, auditorías, casos y retención.','Finanzas operativas, donaciones, convenios, asignaciones y activos.','Documentos, versiones, contexto, historia, migración y calidad.']
for m in r['milestones']:
    if m['id'].startswith('ACA-MCMS'):m['subtitle']=folder_text[int(m['id'][-2:])-1]
for c in schema['collections']:
    for suffix in ['PREP','BUILD','TEST','IMPORT','REVIEW']:
        t=tasks[f'ACA-CMS-{int(c["id"]):03}-{suffix}']
        t['scope']=t['scope'].replace(c['purpose'],folder_text[int(c['folderId'])-1])
domains=[
'Una identidad People privada por persona y Organizations por organización; DirectoryProfiles es una proyección pública deliberada y revisada, con consentimiento. Relaciones personales y organizacionales fechadas; catálogos y taxonomías controlados.',
'MembershipApplications precede a la membresía. Solo una transición autorizada crea Memberships, MembershipPeriod vigente y AccessAssignment. Publicar directorio exige revisión adicional. Credentials y VerificationEvents conservan prueba puntual; la historia no demuestra vigencia. Versionar planes, precios y consentimiento.',
'GovernanceBodies y OrganizationalRoles persisten independientemente de ocupantes. Appointments son fechados; competencias y evaluación de candidatos no sustituyen decisiones estatutarias. Meetings, Resolutions y AuthorityGrants documentan decisiones y autoridad. Entrega de cargo revisa documentos, tareas, obligaciones y accesos.',
'Separar AccessRoles/AccessAssignments/RolePermissions del nombramiento y de la autoridad legal, financiera o de firma. Registrar sistemas externos, custodia y acceso fechado sin contraseñas, llaves ni secretos de MFA. Revocar/transmitir acceso durante el relevo.',
'KnowledgeItems versionados y ProcedureSteps ordenados explican el trabajo. TaskTemplates generan OperationalTasks; mensajes y ajustes se versionan y no guardan secretos. La ayuda vigente vive dentro de la interfaz. Awaiting Approval exige revisión independiente y no permite autoaprobación.',
'Programs agrupa InstitutionalActivities. ActivityContributions registra trabajo, voluntariado, servicio y aportes en especie; MetricDefinitions e ImpactMetrics separan definición y evidencia. ScholarshipApplications y ScholarshipAwards son distintos. Derivar reportingYear de fecha real y conservar formVersion y evidencia de preparación.',
'Events es oferta fechada; EducationCatalog contenido reutilizable; Sessions unidad de agenda. SpeakerAssignments requiere persona canónica, confirmación y snapshot de disclosure/credencial. Participations, AttendanceRecords y AssessmentAttempts sustentan elegibilidad. CreditDefinitions depende de autorización externa; CreditAwards usa reglas deterministas y snapshot de elegibilidad.',
'CertificateTemplates versionados y Certificates restringido conservan emisión/revocación/reemplazo, PDF/evidencia, token único y supersesión. QR público devuelve solamente número, estado, nombre, evento y créditos desde backend. Exigir elegibilidad determinista, autoridad de firma y pruebas de PDF, revocación, sustitución y acceso.',
'ExternalAuthorizations registra autorizaciones externas fechadas y evidencia; no presume CLUNI, Donataria, DIF o IBLCE vigentes. ObligationDefinitions define autoridad/fundamento, disparador, vencimiento, owner y frecuencia. ObligationInstances conserva ocurrencias, preparación, revisión y aprobación distintas.',
'Submissions conserva versiones de filing/acuse inmutables; corregir por nueva versión. Audits/AuditFindings enlaza requerimientos y correcciones. ConflictDisclosures y Cases cubren ética, privacidad, ARCO, quejas, incidentes y excepciones. RetentionRules y RecordHolds impiden disposición indebida y preservan revisión controlada.',
'FinancialTransactions es índice operativo con referencias Wix/externas/contables; contabilidad externa sigue siendo ledger. Donations conserva restricciones, valoración en especie e indicadores de diligencia. Agreements, FundingAllocations y Assets registran compromisos, apoyos y bienes. Umbrales son reglas deterministas configuradas y aprobadas.',
'Documents es documento lógico; DocumentVersions conserva archivos/versiones, URL fuente y hash recomendado. ContextLinks enlaza objetos de EntityRegistry y TimelineEvents registra acciones materiales. ImportBatches conserva procedencia; LegacyRecordMap cruza origen→destino; DataQualityIssues guarda excepciones sin resolver.'
]
for n,scope in enumerate(domains,1):
    for suffix in ['DESIGN','BUILD','TEST']:tasks[f'ACA-FLOW-{n:02}-{suffix}']['scope']=scope
auto=[
('Nueva solicitud de membresía','Al agregar MembershipApplications: crear tarea para Membership Staff, acuse al solicitante y TimelineEvent; Wix Automation y backend determinista.'),
('Solicitud incompleta','Al pasar a MISSING_INFORMATION: solicitud de información normalizada y tarea de seguimiento a siete días.'),
('Solicitud aprobada','Transición APPROVED autorizada: crear Membership, MembershipPeriod vigente y AccessAssignment; directorio solo con controles de publicación.'),
('Vencimiento de credencial 90/60/30','Consulta diaria de vigencias: tarea de renovación y aviso al miembro; escalamiento 30/7 según reglas revisadas.'),
('Nombramiento próximo a terminar','Consulta semanal: tareas de entrega-recepción y revisión de accesos internos y externos.'),
('Nombramiento terminado','Estado/fecha de término: expirar o revocar asignaciones, tarea de revisión técnica y TimelineEvent.'),
('Actividad institucional creada','Al crear InstitutionalActivity: lista de evidencia y preparación del expediente.'),
('Actividad incompleta tras siete días','Consulta de preparación inferior a100: recordar al responsable y escalar omisiones repetidas.'),
('Evento creado','Al crear Events: expandir plantillas de tareas de acreditación, ponentes, registro, constancias y comunicaciones.'),
('Asignación de ponente creada','Al agregar SpeakerAssignment: solicitar disclosure y abrir tarea de revisión de conflicto.'),
('Participación registrada','Al agregar Participation: confirmación, instrucciones y segmento de comunicación autorizado.'),
('Asistencia y evaluación satisfechas','Al actualizar Attendance/AssessmentAttempt: recalcular elegibilidad mediante reglas deterministas.'),
('Crédito otorgado','Al crear CreditAward: poner en cola la revisión de elegibilidad y generación de constancia.'),
('Constancia emitida','Al estado ISSUED de Certificate: aviso seguro de constancia y registro de historia.'),
('Vencimiento regulatorio 60/30/14/7','Consulta programada: recordatorios, escalamiento y visibilidad al Consejo.'),
('Filing con acuse','Submission bloqueado/acuse agregado: cierre condicional de obligación y evidencia inmutable.'),
('Auditoría abierta','Al crear Audit: tareas de evidencia con alcance y fecha límite.'),
('Hallazgo de auditoría creado','Al crear AuditFinding: tarea correctiva y escalamiento HIGH/CRITICAL.'),
('Donación registrada','Al agregar/actualizar Donation: indicadores de diligencia por umbrales configurados y tarea de Compliance requerida.'),
('Calidad de datos crítica','Al estado CRITICAL de DataQualityIssue: avisar al responsable técnico y bloquear cierre del lote de migración.')]
for n,(title,scope) in enumerate(auto,1):
    for suffix in ['BUILD','TEST','REVIEW']:tasks[f'ACA-AUT-{n:03}-{suffix}']['scope']=scope
    tasks[f'ACA-AUT-{n:03}-BUILD']['title']=f'AUT-{n:03} · {title}'
ai=[
('Esqueleto de colecciones','Solo staging; especificación exacta, sin registros de muestra; comparar kit y permisos manualmente.'),
('QA de campos','Comparar claves, tipos, requeridos y referencias con la fuente; revisor técnico decide diferencias.'),
('QA de permisos','Revisión de mínimo privilegio y pruebas reales por rol; la IA no prueba acceso por sí sola.'),
('Borrador de automation','Casos de ramas sintéticos; ninguna aprobación sensible autónoma; comunicaciones de prueba autorizadas.'),
('Esqueleto de Velo','Documentación oficial vigente, mínimo privilegio, revisión de código y pruebas por rol.'),
('Esqueleto de dashboard','UI en español con IDs técnicos exactos, revisión de diseño y accesibilidad.'),
('Análisis de migración','Proponer mapeo, normalización y duplicados; dudas a DataQualityIssues; steward aprueba; sin escritura en producción.'),
('Casos de prueba','Casos autorizado/no autorizado/anónimo/vencido/revocado, referencia faltante, estado inválido, duplicado y auditoría; ejecutar en staging.'),
('Resumen semanal de trabajo','Resumen asesor por responsable/severidad de tareas, problemas, solicitudes de esquema, ejecuciones fallidas y aprobaciones; no cerrar registros; correo requiere autorización.'),
('Investigación regulatoria','Fuentes oficiales gubernamentales/acreditadoras; Compliance valida; no cambiar definición ni presentar filing.'),
('Conversión de procedimiento','Conservar código/versión legado; roles, pasos, evidencia, plazos, aprobación y excepciones estructurados; marcar obsolescencia y revisión de Secretaría/Compliance.'),
('Ayuda contextual','Texto breve en español desde procedimiento aprobado; owner valida; preservar significado legal.')]
for n,(title,scope) in enumerate(ai,1):
    for suffix in ['PREP','TEST']:tasks[f'ACA-AI-{n:02}-{suffix}']['scope']=title+'. Límites: '+scope
    tasks[f'ACA-AI-{n:02}-PREP']['title']=f'AI-{n:02} · {title}'
qa=[
'Esquema: las77colecciones con Field IDs, tipos, referencias, carpetas, índices y Help Text exactos; un registro sintético verificado por colección antes de datos reales.',
'Acceso: anónimo, miembro, rol equivocado/correcto y admin; URL/API directa, nombramientos vencidos y accesos revocados. Cada botón revalida autoridad y estado en servidor; ningún campo/ID privado innecesario en UI.',
'Workflow: transiciones válidas/ inválidas, referencias requeridas faltantes, envíos duplicados, estados sin saltos y auditoría material completa.',
'Automations: trigger/filtros exactos, idempotencia, reintentos, sin loops, aprobaciones, pruebas de ramas en staging, Activity Log, owner y rollback. Preferir Patch parcial si Update puede sobrescribir campos ajenos.',
'Interfaces: rol correcto, datos permitidos, estados loading/vacío/normal/bloqueado/vencido/error, búsqueda indexada/acotada, paginación, móvil/escritorio, teclado, etiquetas, contraste y ayuda vigente.',
'Constancias: elegibilidad determinista, autoridad de firma, PDF, proyección pública QR, revocación/sustitución y autorización de acceso al PDF.',
'Cumplimiento y recuperación: vencimientos correctos, snapshot congelado de filing, acuse y reconstrucción de auditoría; respaldo manual, exports, restauración probada y owner nombrado.',
'Rendimiento y lanzamiento: índices y paginación para asistencia, constancias y tareas; freeze, backup, migración, conciliación, smoke tests y monitoreo real de48horas.'
]
for n,scope in enumerate(qa,1):tasks[f'ACA-QA-{n:02}']['scope']=scope
r['asOf']=now;r['spanishPresentationApplied']=True
r['checkpoints'].append({'date':now,'note':'Presentación institucional en español, conservando IDs y etiquetas técnicas Wix; sin cambios de estado/evidencia.'})
write(REGISTER,r)
print('Spanish presentation applied; task status and evidence unchanged.')
