/* Read-only projection viewer. The durable register is maintained outside the browser. */
(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const CACHE_KEY = `acclam-launch-quest-v1:${location.pathname}`;
  const STATUS = { done: 'Verificado', current: 'En curso', upcoming: 'Pendiente' };
  const MARK = { done: '✓', current: '→', upcoming: '·' };
  let snapshot = null;
  let connected = false;
  let lastReadAt = null;
  let inFlight = false;
  let initialOpenApplied = false;
  let focusFromHashApplied = false;
  const filter = { search: '', phase: 'all', status: 'all', milestone: 'all' };
  const openIds = new Set();
  const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
  const normalize = (value) => String(value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase('es');
  const date = (value, options = {}) => {
    const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T12:00:00` : value);
    return Number.isNaN(parsed.getTime()) ? String(value || 'Sin fecha') : new Intl.DateTimeFormat('es', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'America/Los_Angeles', ...options }).format(parsed);
  };
  const safeUrl = (value) => {
    if (typeof value !== 'string') return null;
    if (value.startsWith('/source/') && !/[\u0000-\u001f\\]/.test(value)) return value;
    try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; } catch { return null; }
  };
  const phaseLabel = (id) => snapshot.phases.find((phase) => phase.id === id)?.label || id;
  const flatObjectives = () => snapshot.milestones.flatMap((milestone) => milestone.objectives.map((objective) => ({ ...objective, milestoneId: milestone.id })));

  function validate(data) {
    if (!data || data.schemaVersion !== 1 || typeof data.revision !== 'string' || !data.revision || !data.project || !Array.isArray(data.phases) || !Array.isArray(data.milestones) || !data.counts || !Number.isFinite(Date.parse(data.asOf))) throw new Error('El archivo no contiene una proyección válida del registro.');
    const ids = new Set();
    let done = 0, current = 0, total = 0;
    for (const milestone of data.milestones) {
      if (!milestone.id || ids.has(milestone.id) || !Array.isArray(milestone.objectives)) throw new Error('Hay un hito inválido en la proyección.');
      ids.add(milestone.id);
      for (const objective of milestone.objectives) {
        if (!/^[A-Za-z0-9_.-]+$/.test(objective.id) || ids.has(objective.id) || !STATUS[objective.status] || !Array.isArray(objective.dependencies) || !Array.isArray(objective.acceptance) || !Array.isArray(objective.sources) || !Array.isArray(objective.evidence) || !Array.isArray(objective.history) || !Array.isArray(objective.blockers)) throw new Error('Hay un objetivo inválido en la proyección.');
        ids.add(objective.id); total++; done += objective.status === 'done'; current += objective.status === 'current';
      }
    }
    if (current !== 1 || data.counts.total !== total || data.counts.done !== done || data.counts.current !== current || data.counts.upcoming !== total - done - current) throw new Error('Los recuentos de la proyección no coinciden con los objetivos.');
    return data;
  }

  function rememberOpen() {
    document.querySelectorAll('#milestone-list details[id]').forEach((details) => {
      if (details.open) openIds.add(details.id); else openIds.delete(details.id);
    });
  }

  function sourceLinks(items, emptyText) {
    if (!items?.length) return `<p class="no-dependencies">${escape(emptyText)}</p>`;
    return `<ul class="link-list">${items.map((item) => {
      const url = safeUrl(item.url);
      return `<li class="source-link">${url ? `<a href="${escape(url)}" target="_blank" rel="noopener">${escape(item.label)} <span aria-hidden="true">↗</span></a>` : `<span>${escape(item.label)}</span>`}${item.locator ? `<small>${escape(item.locator)}</small>` : ''}</li>`;
    }).join('')}</ul>`;
  }

  function dependencyLinks(items) {
    if (!items.length) return '<p class="no-dependencies">Sin dependencias previas registradas.</p>';
    return `<div class="dependencies">${items.map((dependency) => `<a class="dependency-link" href="#objective-${escape(dependency.id)}" data-objective-link="${escape(dependency.id)}"><span>${escape(dependency.id)} · ${escape(dependency.title)}</span><span class="dep-status ${escape(dependency.status)}">${escape(STATUS[dependency.status] || dependency.status)}</span></a>`).join('')}</div>`;
  }

  function renderObjective(objective) {
    const historyId = `history-${objective.id}`;
    return `<details class="objective is-${escape(objective.status)}" id="objective-${escape(objective.id)}" ${openIds.has(`objective-${objective.id}`) ? 'open' : ''}>
      <summary><span class="objective-status-mark" aria-hidden="true">${MARK[objective.status]}</span><div class="objective-summary-text"><div class="objective-heading"><h4>${escape(objective.title)}</h4></div><div class="objective-labels"><span class="task-id">${escape(objective.id)}</span><span class="state-pill ${escape(objective.status)}">${STATUS[objective.status]}</span><span class="phase-pill">${escape(phaseLabel(objective.phase))}</span></div></div><span class="chevron" aria-hidden="true"></span></summary>
      <div class="objective-body"><p class="objective-scope">${escape(objective.scope)}</p>
        <dl class="owners"><div><dt>Responsable</dt><dd>${escape(objective.owner || 'Por asignar')}</dd></div><div><dt>Revisión</dt><dd>${escape(objective.reviewer || 'Por asignar')}</dd></div></dl>
        <div class="action-box"><h5 class="detail-label">${objective.status === 'done' ? 'Siguiente seguimiento' : 'Siguiente acción'}</h5><p>${escape(objective.nextAction || 'Consultar las condiciones de aceptación y dependencias.')}</p></div>
        <div class="detail-grid"><section><h5 class="detail-label">Condiciones de aceptación</h5><ul class="criteria-list">${objective.acceptance.map((item) => `<li>${escape(item)}</li>`).join('')}</ul></section><section><h5 class="detail-label">Dependencias</h5>${dependencyLinks(objective.dependencies)}</section></div>
        ${objective.blockers.length ? `<div class="blocker-box"><h5 class="detail-label">Bloqueos y condiciones pendientes</h5><ul class="blocker-list">${objective.blockers.map((item) => `<li>${escape(item)}</li>`).join('')}</ul></div>` : ''}
        <div class="evidence-section"><h5 class="detail-label">Resultado y límites de la evidencia</h5><p class="evidence-summary">${escape(objective.evidenceSummary || 'Resultado aún no verificado. La definición del objetivo no acredita su ejecución.')}</p><div class="detail-grid"><section><h5 class="detail-label">Evidencia del resultado</h5>${sourceLinks(objective.evidence, 'Sin evidencia de finalización registrada.')}</section><section><h5 class="detail-label">Fuentes del alcance</h5>${sourceLinks(objective.sources, 'Consultar la fuente del hito en el registro.')}</section></div></div>
        <details class="history" id="${escape(historyId)}" ${openIds.has(historyId) ? 'open' : ''}><summary>Historial de estado · ${objective.history.length} ${objective.history.length === 1 ? 'entrada' : 'entradas'}</summary><ol class="history-list">${objective.history.map((entry) => `<li><div class="history-meta"><time datetime="${escape(entry.date)}">${escape(date(entry.date))}</time><span>${escape(STATUS[entry.status] || entry.status)}</span></div><p class="history-note">${escape(entry.note)}</p></li>`).join('')}</ol></details>
      </div></details>`;
  }

  function matches(objective, milestone) {
    if (filter.phase !== 'all' && filter.phase !== objective.phase) return false;
    if (filter.status !== 'all' && filter.status !== objective.status) return false;
    if (filter.milestone !== 'all' && filter.milestone !== milestone.id) return false;
    if (!filter.search) return true;
    const text = [objective.id, objective.title, objective.scope, objective.owner, objective.reviewer, objective.nextAction, objective.evidenceSummary, ...(objective.blockers || []), ...objective.acceptance, milestone.title, milestone.id, ...objective.sources.map((source) => `${source.label} ${source.locator}`)].join(' ');
    return normalize(text).includes(normalize(filter.search));
  }

  function renderList(expandFiltered = false) {
    if (!snapshot) return;
    rememberOpen();
    const isFiltered = Object.entries(filter).some(([key, value]) => key === 'search' ? value !== '' : value !== 'all');
    let shown = 0, shownMilestones = 0;
    $('milestone-list').innerHTML = snapshot.milestones.map((milestone, index) => {
      const objectives = milestone.objectives.filter((objective) => matches(objective, milestone));
      if (!objectives.length) return '';
      shown += objectives.length; shownMilestones++;
      const countDone = milestone.objectives.filter((objective) => objective.status === 'done').length;
      const isCurrent = milestone.objectives.some((objective) => objective.status === 'current');
      return `<details class="milestone ${isCurrent ? 'is-current' : ''}" id="milestone-${escape(milestone.id)}" ${expandFiltered || openIds.has(`milestone-${milestone.id}`) ? 'open' : ''}><summary><span class="milestone-index" aria-hidden="true">${String(index + 1).padStart(2, '0')}</span><div class="milestone-summary-text"><h3>${escape(milestone.title)}</h3><p>${escape(milestone.id)}${milestone.subtitle ? ` · ${escape(milestone.subtitle)}` : ''}</p></div><span class="milestone-summary-count"><b>${countDone}</b> / ${milestone.objectives.length} verificados</span><span class="chevron" aria-hidden="true"></span></summary><div class="milestone-objectives">${objectives.map(renderObjective).join('')}</div></details>`;
    }).join('');
    $('results-count').textContent = `${shown} de ${snapshot.counts.total} objetivos · ${shownMilestones} de ${snapshot.milestones.length} hitos`;
    $('empty-state').hidden = shown !== 0;
    $('clear-filters').hidden = !isFiltered;
  }

  function render() {
    rememberOpen();
    const current = flatObjectives().find((objective) => objective.status === 'current');
    if (!initialOpenApplied) {
      openIds.add(`milestone-${current.milestoneId}`); openIds.add(`objective-${current.id}`); initialOpenApplied = true;
    }
    $('project-title').textContent = snapshot.project.title;
    $('project-subtitle').textContent = snapshot.project.subtitle || '';
    $('scope-note').textContent = snapshot.project.scopeNote || '';
    $('checkpoint-date').textContent = date(snapshot.asOf);
    $('checkpoint-revision').textContent = snapshot.revision.substring(0, 12);
    $('checkpoint-revision').title = snapshot.revision;
    $('checkpoint-summary').textContent = snapshot.project.checkpointSummary || '';
    $('next-gate').textContent = snapshot.project.nextGate || '';
    $('workspace-label').textContent = snapshot.project.workspaceLabel || '';
    const continuity = safeUrl(snapshot.project.continuityUrl);
    if (continuity) $('continuity-link').href = continuity;
    $('current-card').innerHTML = `<div class="current-topline"><p class="eyebrow">Objetivo actual</p><span class="current-phase">${escape(phaseLabel(current.phase))}</span><span class="task-id">${escape(current.id)}</span></div><h2>${escape(current.title)}</h2><p class="next-action-label">Siguiente acción concreta</p><p class="current-action">${escape(current.nextAction)}</p><a class="button primary" href="#objective-${escape(current.id)}" data-objective-link="${escape(current.id)}">Ver objetivo y evidencia <span aria-hidden="true">↗</span></a>${current.blockers.length ? `<p class="current-note"><strong>Condición pendiente:</strong> ${escape(current.blockers.join(' '))}</p>` : ''}${current.dependencies.length ? `<div class="current-dependencies" aria-label="Dependencias del objetivo actual">${current.dependencies.map((dependency) => `<a href="#objective-${escape(dependency.id)}" data-objective-link="${escape(dependency.id)}">${escape(dependency.id)} · ${escape(STATUS[dependency.status] || dependency.status)}</a>`).join('')}</div>` : ''}`;
    $('completion-count').innerHTML = `<strong>${snapshot.counts.done}<span> / ${snapshot.counts.total}</span></strong><span>objetivos</span>`;
    $('overall-track').innerHTML = '<span class="is-done"></span><span class="is-current"></span>';
    $('overall-track').querySelector('.is-done').style.width = `${snapshot.counts.done / snapshot.counts.total * 100}%`;
    $('overall-track').querySelector('.is-current').style.width = `${snapshot.counts.current / snapshot.counts.total * 100}%`;
    $('overall-track').setAttribute('aria-label', `${snapshot.counts.done} objetivos verificados de ${snapshot.counts.total}; ${snapshot.counts.current} en curso; ${snapshot.counts.upcoming} pendientes. No mide preparación para lanzamiento.`);
    $('status-legend').innerHTML = ['done', 'current', 'upcoming'].map((status) => `<span class="legend-item"><span class="legend-dot ${status}" aria-hidden="true"></span>${snapshot.counts[status]} ${STATUS[status].toLocaleLowerCase('es')}${snapshot.counts[status] !== 1 && status === 'done' ? 's' : snapshot.counts[status] !== 1 && status === 'upcoming' ? 's' : ''}</span>`).join('');
    const byPhase = snapshot.phases.map((phase) => { const objectives = flatObjectives().filter((objective) => objective.phase === phase.id); return { ...phase, total: objectives.length, done: objectives.filter((objective) => objective.status === 'done').length }; });
    $('phase-grid').innerHTML = byPhase.map((phase) => `<div class="phase-stat"><span>${escape(phase.label)}</span><p>${phase.done} / ${phase.total}<small>verificados</small></p><div class="phase-stat-track" aria-hidden="true"><span></span></div></div>`).join('');
    $('phase-grid').querySelectorAll('.phase-stat-track span').forEach((bar,index) => { const phase = byPhase[index]; bar.style.width = `${phase.total ? phase.done / phase.total * 100 : 0}%`; });
    $('milestone-map').innerHTML = snapshot.milestones.map((milestone, index) => { const done = milestone.objectives.filter((objective) => objective.status === 'done').length; const status = milestone.objectives.some((objective) => objective.status === 'current') ? 'current' : done === milestone.objectives.length ? 'done' : 'upcoming'; return `<a class="map-node is-${status}" href="#milestone-${escape(milestone.id)}" data-milestone-link="${escape(milestone.id)}" aria-label="${escape(milestone.title)}: ${done} de ${milestone.objectives.length} objetivos verificados"><span class="map-number">${String(index + 1).padStart(2, '0')}<span class="map-dot" aria-hidden="true"></span></span><span class="map-title">${escape(milestone.shortLabel || milestone.title)}</span><span class="map-count">${done} / ${milestone.objectives.length} verificados</span></a>`; }).join('');
    $('phase-filter').innerHTML = '<option value="all">Todas las etapas</option>' + snapshot.phases.map((phase) => `<option value="${escape(phase.id)}">${escape(phase.label)}</option>`).join('');
    $('milestone-filter').innerHTML = '<option value="all">Todos los hitos</option>' + snapshot.milestones.map((milestone) => `<option value="${escape(milestone.id)}">${escape(milestone.id)} · ${escape(milestone.shortLabel || milestone.title)}</option>`).join('');
    if (![...$('phase-filter').options].some((option) => option.value === filter.phase)) filter.phase = 'all';
    if (![...$('milestone-filter').options].some((option) => option.value === filter.milestone)) filter.milestone = 'all';
    $('phase-filter').value = filter.phase; $('milestone-filter').value = filter.milestone;
    renderList();
    $('loading-state').hidden = true; $('fatal-state').hidden = true; $('dashboard').hidden = false;
    updateConnection();
    if (!focusFromHashApplied && location.hash) { focusFromHashApplied = true; revealHash(false); }
  }

  function updateConnection() {
    if (!snapshot) return;
    const staleDays = Math.max(1, Number(snapshot.project.staleAfterDays) || 7);
    const stale = Date.now() - Date.parse(snapshot.asOf) > staleDays * 86400000;
    $('connection-indicator').classList.toggle('is-offline', !connected);
    $('connection-indicator').innerHTML = `<span class="connection-dot" aria-hidden="true"></span><span>${connected ? 'Lectura local conectada' : 'Copia guardada · sin conexión'}</span>${lastReadAt && connected ? `<small aria-hidden="true">Leído ${new Intl.DateTimeFormat('es', { hour: '2-digit', minute: '2-digit', second: '2-digit', timeZone: 'America/Los_Angeles' }).format(lastReadAt)}</small>` : ''}`;
    const notes = [];
    if (!connected) notes.push('No se pudo leer el archivo local. Se muestra la última copia válida guardada en este navegador; puede haber cambios pendientes de lectura.');
    if (stale) notes.push(`El punto de control tiene más de ${staleDays} días. Revisa el registro y su evidencia antes de tomarlo como estado actual.`);
    $('freshness-banner').textContent = notes.join(' ');
    $('freshness-banner').hidden = !notes.length;
  }

  function clearFilters(renderNow = true) {
    filter.search = ''; filter.phase = 'all'; filter.status = 'all'; filter.milestone = 'all';
    $('search-input').value = ''; $('phase-filter').value = 'all'; $('status-filter').value = 'all'; $('milestone-filter').value = 'all';
    if (renderNow) renderList();
  }

  function revealObjective(id, moveFocus = true) {
    const objective = flatObjectives().find((item) => item.id === id);
    if (!objective) return;
    clearFilters(false);
    openIds.add(`milestone-${objective.milestoneId}`); openIds.add(`objective-${id}`);
    // Open existing details before a rerender so rememberOpen preserves this request.
    const existingMilestone = $(`milestone-${objective.milestoneId}`), existingObjective = $(`objective-${id}`);
    if (existingMilestone) existingMilestone.open = true;
    if (existingObjective) existingObjective.open = true;
    renderList();
    const target = $(`objective-${id}`);
    if (!target) return;
    requestAnimationFrame(() => { target.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); target.classList.remove('highlight-target'); void target.offsetWidth; target.classList.add('highlight-target'); if (moveFocus) target.querySelector('summary').focus({ preventScroll: true }); });
  }

  function revealMilestone(id, moveFocus = true) {
    if (!snapshot.milestones.some((milestone) => milestone.id === id)) return;
    clearFilters(false); openIds.add(`milestone-${id}`);
    const existing = $(`milestone-${id}`); if (existing) existing.open = true;
    renderList();
    const target = $(`milestone-${id}`);
    requestAnimationFrame(() => { target.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' }); if (moveFocus) target.querySelector('summary').focus({ preventScroll: true }); });
  }

  function revealHash(moveFocus = true) {
    let hash;
    try { hash = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (hash.startsWith('objective-')) revealObjective(hash.slice(10), moveFocus);
    else if (hash.startsWith('milestone-')) revealMilestone(hash.slice(10), moveFocus);
  }

  async function refresh() {
    if (inFlight) return;
    inFlight = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('./progress.json', { cache: 'no-store', signal: controller.signal });
      if (!response.ok) throw new Error(`No se pudo leer progress.json (${response.status}).`);
      const data = validate(await response.json());
      connected = true; lastReadAt = new Date();
      const changed = !snapshot || snapshot.revision !== data.revision || snapshot.asOf !== data.asOf;
      snapshot = data;
      try { localStorage.setItem(CACHE_KEY, JSON.stringify(data)); } catch { /* Storage can be unavailable; the in-memory copy remains usable. */ }
      if (changed) render(); else updateConnection();
    } catch (error) {
      connected = false;
      if (snapshot) updateConnection();
      else { $('loading-state').hidden = true; $('fatal-state').hidden = false; $('fatal-message').textContent = `${error.name === 'AbortError' ? 'La lectura local tardó demasiado.' : error.message} Abre el visor con el servidor local indicado en README.txt y vuelve a leer.`; }
    } finally { clearTimeout(timeout); inFlight = false; }
  }

  $('search-input').addEventListener('input', (event) => { filter.search = event.target.value.trim(); renderList(true); });
  [['phase-filter', 'phase'], ['status-filter', 'status'], ['milestone-filter', 'milestone']].forEach(([id, key]) => $(id).addEventListener('change', (event) => { filter[key] = event.target.value; renderList(true); }));
  $('clear-filters').addEventListener('click', () => clearFilters());
  $('clear-empty-filters').addEventListener('click', () => clearFilters());
  $('expand-all').addEventListener('click', () => { document.querySelectorAll('.milestone').forEach((details) => { details.open = true; openIds.add(details.id); }); });
  $('collapse-all').addEventListener('click', () => { document.querySelectorAll('#milestone-list details').forEach((details) => { details.open = false; openIds.delete(details.id); }); });
  $('retry-button').addEventListener('click', refresh);
  document.addEventListener('click', (event) => {
    const objectiveLink = event.target.closest('[data-objective-link]'), milestoneLink = event.target.closest('[data-milestone-link]');
    if (!objectiveLink && !milestoneLink) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    history.replaceState(null, '', (objectiveLink || milestoneLink).getAttribute('href'));
    if (objectiveLink) revealObjective(objectiveLink.dataset.objectiveLink); else revealMilestone(milestoneLink.dataset.milestoneLink);
  });
  window.addEventListener('hashchange', () => { if (snapshot) revealHash(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
  window.addEventListener('online', refresh);
  window.addEventListener('offline', () => { connected = false; updateConnection(); });
  try { const cached = localStorage.getItem(CACHE_KEY); if (cached) { snapshot = validate(JSON.parse(cached)); render(); } } catch { /* A malformed cache is never displayed. */ }
  refresh();
  setInterval(() => { if (!document.hidden) refresh(); }, 20000);
})();
