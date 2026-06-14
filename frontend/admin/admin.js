'use strict';

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function esc(s) {
    return (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function fmtUptime(secs) {
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    return `${h}h ${m}m`;
}

function fmtSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1048576).toFixed(1)} MB`;
}

async function apiFetch(path, opts = {}) {
    const res = await fetch(path, opts);
    if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
}

function openModal(id) {
    document.getElementById(id).classList.add('open');
}

function closeModal(id) {
    document.getElementById(id).classList.remove('open');
}

// Close modal on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
        if (e.target === overlay) overlay.classList.remove('open');
    });
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
    }
});

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

const sections = ['status', 'import', 'suggestions', 'queries', 'geocoder', 'anecdotes', 'minibios', 'tests', 'comparador', 'classifier', 'palazuelos', 'dedup', 'cemeteries', 'config'];
const initialized = {};

function showSection(name) {
    sections.forEach(s => {
        document.getElementById(`s-${s}`).classList.toggle('active', s === name);
    });
    document.querySelectorAll('.admin-nav a').forEach(a => {
        a.classList.toggle('active', a.dataset.section === name);
    });

    if (!initialized[name]) {
        initialized[name] = true;
        const ctrl = { status: Status, import: Import, suggestions: Suggestions,
                       queries: Queries, geocoder: Geocoder, anecdotes: Anecdotes,
                       minibios: Minibios, tests: Tests,
                       config: Config, comparador: Comparador,
                       classifier: DocClassifier, palazuelos: Palazuelos,
                       dedup: Dedup, cemeteries: Cemeteries }[name];
        if (ctrl?.init) ctrl.init();
        else if (ctrl?.onActivate) ctrl.onActivate();
    }
}

document.querySelectorAll('.admin-nav a').forEach(a => {
    a.addEventListener('click', () => showSection(a.dataset.section));
});

// ---------------------------------------------------------------------------
// Status section
// ---------------------------------------------------------------------------

const Status = {
    init() {
        this.refresh();
        this.refreshLogs();
        this.refreshDbInfo();
    },

    async refresh() {
        try {
            const d = await apiFetch('/api/admin/status');
            document.getElementById('status-uptime').textContent = fmtUptime(d.uptime_seconds);
            document.getElementById('status-time').textContent = `Servidor: ${d.server_time?.slice(0, 19).replace('T', ' ')}`;
            document.getElementById('status-gedcom').textContent = d.gedcom_file ? `GEDCOM: ${d.gedcom_file}` : '';

            const grid = document.getElementById('stat-grid');
            const labels = {
                people: 'Personas', marriages: 'Matrimonios', photos: 'Fotos',
                photo_tags: 'Tags foto', albums: 'Álbumes', suggestions: 'Aportaciones',
                occupations: 'Ocupaciones', residences: 'Residencias',
                geocache: 'Geocache', notes: 'Notas', events: 'Eventos',
            };
            grid.innerHTML = Object.entries(d.db_row_counts || {}).map(([k, v]) => `
                <div class="stat-card">
                    <div class="stat-value">${v.toLocaleString()}</div>
                    <div class="stat-label">${labels[k] || k}</div>
                </div>
            `).join('');
        } catch (e) {
            console.error('Status error:', e);
        }
    },

    async refreshLogs() {
        try {
            const d = await apiFetch('/api/admin/logs?lines=150');
            const box = document.getElementById('log-box');
            if (!d.logs || !d.logs.length) {
                box.textContent = 'No hay logs disponibles.';
                return;
            }
            box.innerHTML = d.logs.map(l =>
                `<span class="log-${l.level}">[${esc(l.time)}] ${esc(l.message)}</span>`
            ).join('\n');
            box.scrollTop = box.scrollHeight;
        } catch (e) {
            document.getElementById('log-box').textContent = 'Error cargando logs.';
        }
    },

    async refreshDbInfo() {
        try {
            const d = await apiFetch('/api/admin/db/info');
            const el = document.getElementById('db-info');
            if (el) {
                el.textContent = `BD: ${fmtSize(d.db_size)}  ·  WAL: ${fmtSize(d.wal_size)}  ·  Modificada: ${d.last_modified?.slice(0,19).replace('T',' ')}`;
            }
        } catch {}
    },

    async serverAction(action) {
        const msg = document.getElementById('server-action-msg');
        msg.textContent = 'Ejecutando…';
        try {
            const d = await apiFetch('/api/admin/server/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action }),
            });
            msg.textContent = d.message || '✓';
            if (action === 'restart') {
                setTimeout(() => {
                    msg.textContent = 'Reconectando…';
                    setTimeout(() => window.location.reload(), 4000);
                }, 2000);
            }
        } catch (e) {
            msg.textContent = 'Error: ' + e.message;
        }
    },

    async dbAction(action) {
        const msg = document.getElementById('db-action-msg');
        msg.textContent = 'Ejecutando…';
        try {
            const d = await apiFetch('/api/admin/db/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action }),
            });
            msg.textContent = d.message || '✓';
            this.refreshDbInfo();
        } catch (e) {
            msg.textContent = 'Error: ' + e.message;
        }
    },
};

// ---------------------------------------------------------------------------
// Import section
// ---------------------------------------------------------------------------

const Import = {
    pollTimer: null,
    lastLogLen: 0,

    init() {
        this.checkCurrentGed();
        this.checkStatus();
    },

    async checkCurrentGed() {
        try {
            const d = await apiFetch('/api/admin/status');
            const el = document.getElementById('import-current-ged');
            if (d.gedcom_file) el.textContent = `GEDCOM actual: ${d.gedcom_file}`;
        } catch {}
    },

    onFileSelected(input) {
        const label = document.getElementById('ged-drop-label');
        if (input.files[0]) {
            label.innerHTML = `<strong>${esc(input.files[0].name)}</strong><br><small>${fmtSize(input.files[0].size)}</small>`;
        }
    },

    async checkStatus() {
        try {
            const d = await apiFetch('/api/admin/import/status');
            if (d.status === 'running' || d.status === 'done' || d.status === 'error') {
                this.showLogCard();
                this.updateLog(d);
                if (d.status === 'running') this.startPolling();
            }
        } catch {}
    },

    async start() {
        const mode = document.querySelector('input[name="import-mode"]:checked')?.value || 'fast';
        const deletePhotos = document.getElementById('delete-photos').checked;
        const fileInput = document.getElementById('ged-file');

        const fd = new FormData();
        fd.append('mode', mode);
        fd.append('delete_old_photos', deletePhotos ? 'true' : 'false');
        if (fileInput.files[0]) fd.append('file', fileInput.files[0]);

        const btn = document.getElementById('btn-start-import');
        btn.disabled = true;
        btn.textContent = 'Iniciando…';

        try {
            await apiFetch('/api/admin/import/gedcom', { method: 'POST', body: fd });
            this.showLogCard();
            this.lastLogLen = 0;
            this.startPolling();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = 'Iniciar importación';
            alert('Error: ' + e.message);
        }
    },

    showLogCard() {
        document.getElementById('import-log-card').style.display = '';
    },

    startPolling() {
        clearInterval(this.pollTimer);
        this.pollTimer = setInterval(() => this.poll(), 1500);
    },

    async poll() {
        try {
            const d = await apiFetch('/api/admin/import/status');
            this.updateLog(d);
            if (d.status !== 'running') {
                clearInterval(this.pollTimer);
                this.pollTimer = null;
                document.getElementById('btn-start-import').disabled = false;
                document.getElementById('btn-start-import').textContent = 'Iniciar importación';
                document.getElementById('btn-reset-import').style.display = '';
                document.getElementById('import-post-actions').style.display = '';
            }
        } catch {}
    },

    updateLog(d) {
        const badge = document.getElementById('import-status-badge');
        const statusMap = { idle: '', running: 'running', done: 'resolved', error: 'error' };
        const labelMap = { idle: '', running: 'En curso…', done: '✓ Completado', error: '✗ Error' };
        badge.className = `badge badge-${statusMap[d.status] || 'pending'}`;
        badge.textContent = labelMap[d.status] || d.status;

        const box = document.getElementById('import-log');
        const newLines = (d.log || []).slice(this.lastLogLen);
        if (newLines.length) {
            box.textContent += newLines.join('\n') + '\n';
            box.scrollTop = box.scrollHeight;
            this.lastLogLen = d.log.length;
        }
    },

    async reset() {
        try {
            await apiFetch('/api/admin/import/job', { method: 'DELETE' });
            document.getElementById('import-log-card').style.display = 'none';
            document.getElementById('import-log').textContent = '';
            document.getElementById('btn-reset-import').style.display = 'none';
            document.getElementById('import-post-actions').style.display = 'none';
            document.getElementById('import-status-badge').textContent = '';
            this.lastLogLen = 0;
        } catch (e) { alert(e.message); }
    },

    async syncPhotos() {
        try {
            const d = await apiFetch('/api/admin/sync-photos', { method: 'POST' });
            alert(d.message || 'Fotos sincronizadas.');
        } catch (e) { alert('Error: ' + e.message); }
    },
};

// Drag-drop for comparison GEDCOM file
const cmpDrop = document.getElementById('cmp-drop');
if (cmpDrop) {
    cmpDrop.addEventListener('dragover', e => { e.preventDefault(); cmpDrop.classList.add('drag-over'); });
    cmpDrop.addEventListener('dragleave', () => cmpDrop.classList.remove('drag-over'));
    cmpDrop.addEventListener('drop', e => {
        e.preventDefault();
        cmpDrop.classList.remove('drag-over');
        const f = e.dataTransfer.files[0];
        if (f && f.name.endsWith('.ged')) {
            document.getElementById('cmp-file').files = e.dataTransfer.files;
            Comparador.onFileSelected(document.getElementById('cmp-file'));
        }
    });
}

// Drag-drop for GEDCOM file
const gedDrop = document.getElementById('ged-drop');
gedDrop.addEventListener('dragover', e => { e.preventDefault(); gedDrop.classList.add('drag-over'); });
gedDrop.addEventListener('dragleave', () => gedDrop.classList.remove('drag-over'));
gedDrop.addEventListener('drop', e => {
    e.preventDefault();
    gedDrop.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f && f.name.endsWith('.ged')) {
        document.getElementById('ged-file').files = e.dataTransfer.files;
        Import.onFileSelected(document.getElementById('ged-file'));
    }
});

// ---------------------------------------------------------------------------
// Suggestions section
// ---------------------------------------------------------------------------

const Suggestions = {
    init() { this.load(); },

    async load() {
        const el = document.getElementById('suggestions-list');
        el.innerHTML = '<div class="empty-state">Cargando…</div>';
        try {
            const items = await apiFetch('/api/admin/suggestions');
            const badge = document.getElementById('badge-suggestions');
            const pending = items.filter(i => !i.resolved_at).length;
            badge.textContent = pending || '';

            if (!items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div>No hay aportaciones.</div>';
                return;
            }

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th>Fecha</th><th>Remitente</th><th>Persona afectada</th><th>Tipo</th><th>Mensaje</th>
                    <th>Archivos</th><th>Estado</th><th></th>
                </tr></thead>
                <tbody>${items.map(s => `
                    <tr>
                        <td style="white-space:nowrap;font-size:0.75rem;color:#727971;">${esc(s.created_at?.slice(0,16).replace('T',' '))}</td>
                        <td><strong>${esc(s.name || '—')}</strong>${s.email ? `<br><small style="color:#727971;">${esc(s.email)}</small>` : ''}</td>
                        <td style="font-size:0.82rem;">${s.person_name
                            ? `<a href="/index.html?person=${esc(s.person_id)}" target="_blank" style="color:var(--primary,#17341e);font-weight:600;">${esc(s.person_name)}</a>`
                            : s.person_id ? `<span style="color:#727971;font-size:0.75rem;">${esc(s.person_id)}</span>` : '—'}</td>
                        <td><span class="badge badge-pending">${esc(s.type || '—')}</span></td>
                        <td style="max-width:240px;font-size:0.8rem;">${esc((s.message || '').slice(0, 100))}${(s.message || '').length > 100 ? '…' : ''}</td>
                        <td style="text-align:center;">
                            ${s.files_count > 0
                                ? `<button class="btn btn-secondary btn-sm" onclick="Suggestions.viewFiles('${esc(s.id)}', '${esc(s.name || s.id)}')">${s.files_count} archivo${s.files_count > 1 ? 's' : ''}</button>`
                                : '<span style="color:#c2c8bf;">—</span>'}
                        </td>
                        <td>${s.resolved_at
                            ? `<span class="badge badge-resolved">✓ Resuelto</span>`
                            : `<span class="badge badge-pending">Pendiente</span>`}</td>
                        <td>
                            <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                                ${!s.resolved_at ? `<button class="btn btn-secondary btn-sm" onclick="Suggestions.resolve('${esc(s.id)}')">Resolver</button>` : ''}
                                <button class="btn btn-danger btn-sm" onclick="Suggestions.remove('${esc(s.id)}')">✕</button>
                            </div>
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`;
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    async viewFiles(id, name) {
        document.getElementById('files-modal-title').textContent = `Archivos — ${name}`;
        document.getElementById('files-modal-body').innerHTML = 'Cargando…';
        openModal('files-modal');
        try {
            const files = await apiFetch(`/api/admin/suggestions/${id}/files`);
            if (!files.length) {
                document.getElementById('files-modal-body').innerHTML = '<p style="color:#727971;">Sin archivos adjuntos.</p>';
                return;
            }
            document.getElementById('files-modal-body').innerHTML = files.map(f => `
                <div style="display:flex;align-items:center;gap:0.75rem;padding:0.6rem 0;border-bottom:1px solid var(--outline-variant,#c2c8bf);">
                    <span style="flex:1;font-size:0.84rem;">${esc(f.name)}</span>
                    <span style="font-size:0.75rem;color:#727971;">${fmtSize(f.size)}</span>
                    <a href="${esc(f.url)}" target="_blank" class="btn btn-secondary btn-sm">Descargar</a>
                </div>
            `).join('');
        } catch (e) {
            document.getElementById('files-modal-body').innerHTML = `<p style="color:red;">${esc(e.message)}</p>`;
        }
    },

    async resolve(id) {
        try {
            await apiFetch(`/api/admin/suggestions/${id}/resolve`, { method: 'POST' });
            this.load();
        } catch (e) { alert(e.message); }
    },

    async remove(id) {
        if (!confirm('¿Eliminar esta aportación y todos sus archivos?')) return;
        try {
            await apiFetch(`/api/admin/suggestions/${id}`, { method: 'DELETE' });
            this.load();
        } catch (e) { alert(e.message); }
    },
};

// ---------------------------------------------------------------------------
// Unresolved Queries section
// ---------------------------------------------------------------------------

const Queries = {
    items: [],
    selected: new Set(),

    init() { this.load(); },

    async load() {
        const el = document.getElementById('queries-list');
        el.innerHTML = '<div class="empty-state">Cargando…</div>';
        this.selected.clear();
        this.updateDeleteBtn();
        try {
            this.items = await apiFetch('/api/admin/queries');
            const badge = document.getElementById('badge-queries');
            badge.textContent = this.items.length || '';

            if (!this.items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div>Sin preguntas sin respuesta.</div>';
                return;
            }

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th style="width:32px;"><input type="checkbox" onchange="Queries.toggleAll(this)"/></th>
                    <th style="width:90px;">Data</th>
                    <th style="width:60px;">Hora</th>
                    <th>Pregunta</th>
                </tr></thead>
                <tbody>${this.items.map((q, i) => `
                    <tr>
                        <td><input type="checkbox" data-idx="${q.index}" onchange="Queries.toggleOne(this)"/></td>
                        <td style="font-size:0.78rem;color:#727971;">${esc(q.date)}</td>
                        <td style="font-size:0.78rem;color:#727971;">${esc(q.time)}</td>
                        <td style="font-size:0.84rem;">${esc(q.question)}</td>
                    </tr>
                `).join('')}</tbody>
            </table>`;
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    toggleAll(cb) {
        this.selected.clear();
        if (cb.checked) this.items.forEach(q => this.selected.add(q.index));
        document.querySelectorAll('#queries-list input[type=checkbox][data-idx]').forEach(c => {
            c.checked = cb.checked;
        });
        this.updateDeleteBtn();
    },

    toggleOne(cb) {
        const idx = parseInt(cb.dataset.idx);
        if (cb.checked) this.selected.add(idx);
        else this.selected.delete(idx);
        this.updateDeleteBtn();
    },

    updateDeleteBtn() {
        const btn = document.getElementById('btn-del-selected');
        btn.disabled = this.selected.size === 0;
        if (this.selected.size > 0) btn.textContent = `Borrar seleccionadas (${this.selected.size})`;
        else btn.textContent = 'Borrar seleccionadas';
    },

    async deleteSelected() {
        if (!this.selected.size) return;
        if (!confirm(`¿Borrar ${this.selected.size} preguntas?`)) return;
        try {
            await apiFetch('/api/admin/queries', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ indices: [...this.selected] }),
            });
            this.load();
        } catch (e) { alert(e.message); }
    },

    async deleteAll() {
        if (!confirm('¿Borrar TODAS las preguntas sin respuesta?')) return;
        try {
            const d = await apiFetch('/api/admin/queries/all', { method: 'DELETE' });
            alert(`${d.deleted} preguntas borradas.`);
            this.load();
        } catch (e) { alert(e.message); }
    },
};

// ---------------------------------------------------------------------------
// Geocoder section (ported from admin_geocoder.html)
// ---------------------------------------------------------------------------

const Geocoder = {
    pending: [], resolved: [], validated: [],
    activeTab: 'pending',
    currentEntry: null,
    selectedResult: null,
    geoMap: null,
    geoMarker: null,
    fetchAllRunning: false,

    init() { this.load(); },

    async load() {
        document.getElementById('geo-loading').style.display = '';
        document.getElementById('geo-table').style.display = 'none';
        document.getElementById('geo-empty').style.display = 'none';
        try {
            const [rP, rR, rV] = await Promise.all([
                apiFetch('/api/admin/geocoder/pending'),
                apiFetch('/api/admin/geocoder/resolved'),
                apiFetch('/api/admin/geocoder/validated'),
            ]);
            this.pending = rP;
            this.resolved = rR;
            this.validated = rV;
            document.getElementById('geo-loading').style.display = 'none';
            this.updateCounts();
            this.renderTable();
        } catch (e) {
            document.getElementById('geo-loading').textContent = 'Error: ' + e.message;
        }
    },

    updateCounts() {
        document.getElementById('geo-count-pending').textContent = this.pending.length;
        document.getElementById('geo-count-resolved').textContent = this.resolved.length;
        document.getElementById('geo-count-validated').textContent = this.validated.length;
        document.getElementById('geo-stats').textContent =
            `${this.pending.length} pendientes · ${this.resolved.length} resueltas · ${this.validated.length} validadas`;
        document.getElementById('badge-geo').textContent = this.pending.length || '';
    },

    setTab(tab) {
        this.activeTab = tab;
        document.querySelectorAll('#s-geocoder .admin-tab').forEach((b, i) => {
            const names = ['pending', 'resolved', 'validated'];
            b.classList.toggle('active', names[i] === tab);
        });
        this.renderTable();
    },

    renderTable() {
        const table = document.getElementById('geo-table');
        const empty = document.getElementById('geo-empty');
        const toolbar = document.getElementById('geo-resolved-toolbar');
        toolbar.style.display = 'none';

        const data = this[this.activeTab];
        if (!data.length) {
            table.style.display = 'none';
            empty.style.display = '';
            return;
        }
        empty.style.display = 'none';
        table.style.display = '';

        if (this.activeTab === 'pending') {
            document.getElementById('geo-thead').innerHTML = `<tr>
                <th>#</th><th>Lugar original</th><th>Query normalizada</th>
                <th style="text-align:center;">Afecta</th><th></th>
            </tr>`;
            document.getElementById('geo-tbody').innerHTML = data.map((e, i) => `
                <tr id="geo-row-${i}">
                    <td style="color:#727971;font-size:0.75rem;">${i + 1}</td>
                    <td><strong>${esc(e.raw_place || '—')}</strong></td>
                    <td style="color:#727971;font-size:0.75rem;font-family:monospace;">${esc(e.query)}</td>
                    <td style="text-align:center;">${e.affected > 0
                        ? `<span class="badge badge-running">${e.affected}</span>`
                        : '<span style="color:#c2c8bf;">—</span>'}</td>
                    <td style="text-align:right;">
                        <button class="btn btn-primary btn-sm" onclick="Geocoder.openPanel('pending',${i})">Resolver</button>
                    </td>
                </tr>
            `).join('');

        } else if (this.activeTab === 'resolved') {
            toolbar.style.display = '';
            document.getElementById('geo-thead').innerHTML = `<tr>
                <th>#</th><th>Lugar buscado</th><th>Dirección GPS</th>
                <th>Coordenadas</th><th></th>
            </tr>`;
            document.getElementById('geo-tbody').innerHTML = data.map((e, i) => `
                <tr id="geo-row-r-${i}">
                    <td style="color:#727971;font-size:0.75rem;">${i + 1}</td>
                    <td>${esc(e.raw_place || e.query || '—')}</td>
                    <td id="geo-dn-${i}" style="font-size:0.78rem;">
                        ${e.display_name
                            ? `<span style="color:#065f46;">${esc(e.display_name)}</span>`
                            : `<button class="btn btn-secondary btn-sm" onclick="Geocoder.fetchDN(${i})">cargar</button>`}
                    </td>
                    <td style="font-family:monospace;font-size:0.75rem;white-space:nowrap;">${e.lat.toFixed(4)}, ${e.lng.toFixed(4)}</td>
                    <td>
                        <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                            <button class="btn btn-sm" style="background:#d1fae5;color:#065f46;border:none;" id="geo-val-btn-${i}" onclick="Geocoder.validate(${i})">Validar</button>
                            <button class="btn btn-secondary btn-sm" onclick="Geocoder.openPanel('resolved',${i})">Editar</button>
                        </div>
                    </td>
                </tr>
            `).join('');

        } else {
            document.getElementById('geo-thead').innerHTML = `<tr>
                <th>#</th><th>Lugar buscado</th><th>Dirección GPS</th><th>Coordenadas</th>
            </tr>`;
            document.getElementById('geo-tbody').innerHTML = data.map((e, i) => `
                <tr>
                    <td style="color:#727971;font-size:0.75rem;">${i + 1}</td>
                    <td>${esc(e.raw_place || e.query || '—')}</td>
                    <td style="font-size:0.78rem;color:#065f46;">${esc(e.display_name || '—')}</td>
                    <td style="font-family:monospace;font-size:0.75rem;white-space:nowrap;">${e.lat.toFixed(4)}, ${e.lng.toFixed(4)}</td>
                </tr>
            `).join('');
        }
    },

    async fetchDN(idx) {
        const e = this.resolved[idx];
        const cell = document.getElementById(`geo-dn-${idx}`);
        if (!cell) return;
        cell.innerHTML = '<span style="color:#c2c8bf;">…</span>';
        try {
            const d = await apiFetch(`/api/admin/geocoder/reverse?lat=${e.lat}&lng=${e.lng}`);
            const dn = d.display_name || '';
            this.resolved[idx].display_name = dn;
            cell.innerHTML = dn ? `<span style="color:#065f46;">${esc(dn)}</span>` : '<span style="color:#c2c8bf;">—</span>';
        } catch {
            cell.innerHTML = '<span style="color:red;">error</span>';
        }
    },

    async fetchAllDisplayNames() {
        if (this.fetchAllRunning) return;
        this.fetchAllRunning = true;
        const btn = document.getElementById('btn-fetch-all-names');
        const missing = this.resolved.map((e, i) => ({ e, i })).filter(({ e }) => !e.display_name);
        if (!missing.length) { btn.textContent = 'Todo cargado'; this.fetchAllRunning = false; return; }
        btn.disabled = true;
        for (let k = 0; k < missing.length; k++) {
            btn.textContent = `Cargando ${k + 1}/${missing.length}…`;
            await this.fetchDN(missing[k].i);
            if (k < missing.length - 1) await new Promise(r => setTimeout(r, 1200));
        }
        btn.textContent = 'Cargado';
        btn.disabled = false;
        this.fetchAllRunning = false;
    },

    openPanel(source, idx) {
        this.currentEntry = source === 'pending' ? this.pending[idx] : this.resolved[idx];
        this.currentEntry._source = source;
        this.currentEntry._idx = idx;
        this.selectedResult = null;

        document.getElementById('geo-panel-raw').textContent = this.currentEntry.raw_place || this.currentEntry.query;
        document.getElementById('geo-panel-orig').textContent = `Query: ${this.currentEntry.query}`;
        document.getElementById('geo-panel-query').value = this.currentEntry.query;
        document.getElementById('geo-candidates').innerHTML = '';
        document.getElementById('geo-selected-info').style.display = 'none';
        document.getElementById('geo-btn-save').disabled = true;

        const mapEl = document.getElementById('geo-map');
        mapEl.style.display = 'none';
        if (this.geoMap) { this.geoMap.remove(); this.geoMap = null; this.geoMarker = null; }

        openModal('geo-modal');

        if (source === 'resolved' && this.currentEntry.lat) {
            this.showOnMap(this.currentEntry.lat, this.currentEntry.lng, this.currentEntry.query);
        }
        this.doSearch();
    },

    async doSearch() {
        const query = document.getElementById('geo-panel-query').value.trim();
        if (!query) return;
        const cands = document.getElementById('geo-candidates');
        cands.innerHTML = '<p style="font-size:0.8rem;color:#727971;">Buscando…</p>';
        try {
            const results = await apiFetch('/api/admin/geocoder/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });
            if (!results.length) {
                cands.innerHTML = '<p style="font-size:0.8rem;color:#727971;">Sin resultados.</p>';
                return;
            }
            cands.innerHTML = results.map((r, i) => `
                <button onclick="Geocoder.selectCandidate(${i})" id="geo-cand-${i}"
                    data-lat="${r.lat}" data-lng="${r.lng}" data-name="${esc(r.display_name)}"
                    style="display:block;width:100%;text-align:left;padding:0.5rem 0.75rem;border:1px solid var(--outline-variant,#c2c8bf);border-radius:7px;background:white;cursor:pointer;font-family:Manrope,sans-serif;font-size:0.8rem;transition:all 0.1s;">
                    <strong>${esc(r.display_name)}</strong>
                    <span style="display:block;font-size:0.72rem;color:#727971;">${r.lat.toFixed(5)}, ${r.lng.toFixed(5)} · ${esc(r.class)}/${esc(r.type)}</span>
                </button>
            `).join('');
            this.selectCandidate(0);
        } catch (e) {
            cands.innerHTML = `<p style="color:red;font-size:0.8rem;">${esc(e.message)}</p>`;
        }
    },

    selectCandidate(idx) {
        document.querySelectorAll('[id^="geo-cand-"]').forEach(b => {
            b.style.borderColor = 'var(--outline-variant,#c2c8bf)';
            b.style.background = 'white';
        });
        const btn = document.getElementById(`geo-cand-${idx}`);
        if (!btn) return;
        btn.style.borderColor = 'var(--primary,#17341e)';
        btn.style.background = 'rgba(23,52,30,0.05)';

        const lat = parseFloat(btn.dataset.lat);
        const lng = parseFloat(btn.dataset.lng);
        const name = btn.dataset.name;
        this.selectedResult = { lat, lng, name };

        document.getElementById('geo-sel-name').textContent = name;
        document.getElementById('geo-sel-coords').textContent = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        document.getElementById('geo-selected-info').style.display = '';
        document.getElementById('geo-btn-save').disabled = false;

        this.showOnMap(lat, lng, name);
    },

    showOnMap(lat, lng, label) {
        const mapEl = document.getElementById('geo-map');
        mapEl.style.display = '';
        if (!this.geoMap) {
            this.geoMap = L.map('geo-map', { scrollWheelZoom: false });
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap', maxZoom: 18,
            }).addTo(this.geoMap);
        }
        this.geoMap.setView([lat, lng], 14);
        if (this.geoMarker) this.geoMarker.remove();
        this.geoMarker = L.marker([lat, lng]).bindPopup(label).addTo(this.geoMap);
        setTimeout(() => this.geoMap.invalidateSize(), 50);
    },

    async validate(idx) {
        const e = this.resolved[idx];
        const btn = document.getElementById(`geo-val-btn-${idx}`);
        if (btn) { btn.disabled = true; btn.textContent = '…'; }
        try {
            await apiFetch('/api/admin/geocoder/validate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: e.query }),
            });
            this.validated.unshift({ ...e });
            this.resolved.splice(idx, 1);
            this.updateCounts();
            this.renderTable();
        } catch (e) { alert(e.message); }
    },

    async saveResolution() {
        if (!this.selectedResult || !this.currentEntry) return;
        const saveBtn = document.getElementById('geo-btn-save');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Guardando…';
        try {
            await apiFetch('/api/admin/geocoder/resolve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: this.currentEntry.query,
                    lat: this.selectedResult.lat,
                    lng: this.selectedResult.lng,
                    display_name: this.selectedResult.name || '',
                }),
            });
            closeModal('geo-modal');

            const src = this.currentEntry._source;
            const idx = this.currentEntry._idx;
            if (src === 'pending') {
                const entry = { ...this.pending[idx], lat: this.selectedResult.lat, lng: this.selectedResult.lng };
                this.resolved.unshift(entry);
                const row = document.getElementById(`geo-row-${idx}`);
                if (row) {
                    row.style.opacity = '0.4';
                    const btn = row.querySelector('button');
                    if (btn) { btn.textContent = '✓ Resuelto'; btn.disabled = true; }
                }
            } else {
                this.resolved[idx].lat = this.selectedResult.lat;
                this.resolved[idx].lng = this.selectedResult.lng;
                this.resolved[idx].display_name = this.selectedResult.name || '';
            }
            this.updateCounts();
        } catch (e) { alert(e.message); }
        saveBtn.disabled = false;
        saveBtn.textContent = 'Guardar';
    },

    async runVital() {
        const btn = document.getElementById('geo-run-vital-btn');
        const msg = document.getElementById('geo-run-vital-msg');
        if (btn) { btn.disabled = true; btn.textContent = 'Geocodificando...'; }
        if (msg) msg.textContent = 'Iniciando... puede tardar unos minutos (1s por lugar via Nominatim)';
        try {
            const d = await apiFetch('/api/admin/geocoder/run-vital', { method: 'POST' });
            if (d.status === 'already_running') {
                if (msg) msg.textContent = 'Ya hay una geocodificación en curso.';
            } else {
                if (msg) msg.textContent = 'Geocodificación iniciada en segundo plano. Recarga la página en unos minutos.';
            }
        } catch (e) {
            if (msg) msg.textContent = 'Error: ' + e.message;
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = 'Geocodificar lugares vitales'; }
        }
    },
};

// ---------------------------------------------------------------------------
// Anecdotes section
// ---------------------------------------------------------------------------

// Anecdotes — uses data/anecdotas.json (permanent, survives GEDCOM imports)
const Anecdotes = {
    searchQuery: '',
    searchTimer: null,
    _editIndex: null,       // null = new, number = editing existing
    _pendingDeleteIndex: null,

    init() { this.load(); },

    onSearch(val) {
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => {
            this.searchQuery = val;
            this.load();
        }, 300);
    },

    async load() {
        const el = document.getElementById('anec-list');
        el.innerHTML = '<div class="empty-state">Cargando…</div>';
        try {
            const url = `/api/admin/anecdotes?search=${encodeURIComponent(this.searchQuery)}&_t=${Date.now()}`;
            const d = await apiFetch(url);

            if (!d.items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✦</div>Sin anécdotas encontradas.</div>';
                document.getElementById('anec-pagination').style.display = 'none';
                return;
            }
            document.getElementById('anec-pagination').style.display = 'none';

            this._items = d.items;

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th style="width:40px;">#</th><th>Título</th><th>Texto</th><th>CTA</th><th></th>
                </tr></thead>
                <tbody>${d.items.map(a => `
                    <tr>
                        <td style="color:#727971;font-size:0.75rem;">${a.index + 1}</td>
                        <td style="font-size:0.82rem;font-weight:600;max-width:200px;">${esc((a.titulo || '').slice(0, 70))}${(a.titulo || '').length > 70 ? '…' : ''}</td>
                        <td style="font-size:0.8rem;max-width:280px;color:#3d3d37;">${esc((a.texto || '').slice(0, 100))}${(a.texto || '').length > 100 ? '…' : ''}</td>
                        <td style="font-size:0.75rem;color:#727971;max-width:150px;">${esc((a.cta || '').slice(0, 50))}${(a.cta || '').length > 50 ? '…' : ''}</td>
                        <td>
                            <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                                <button class="btn btn-secondary btn-sm" onclick="Anecdotes.openEdit(${a.index})">✎</button>
                                <button class="btn btn-danger btn-sm" onclick="Anecdotes.confirmRemove(${a.index})">✕</button>
                            </div>
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`;
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    openNew() {
        this._editIndex = null;
        document.getElementById('anec-modal-title').textContent = 'Nueva anécdota';
        document.getElementById('anec-titulo').value = '';
        document.getElementById('anec-texto').value = '';
        document.getElementById('anec-cta').value = '';
        openModal('anec-modal');
    },

    openEdit(index) {
        const a = (this._items || []).find(x => x.index === index);
        if (!a) { alert('Error: no se ha encontrado la anécdota. Recarga la página.'); return; }
        this._editIndex = index;
        document.getElementById('anec-modal-title').textContent = `Editar anécdota #${index + 1}`;
        document.getElementById('anec-titulo').value = a.titulo || '';
        document.getElementById('anec-texto').value = a.texto || '';
        document.getElementById('anec-cta').value = a.cta || '';
        openModal('anec-modal');
    },

    async save() {
        const body = {
            titulo: document.getElementById('anec-titulo').value.trim(),
            texto: document.getElementById('anec-texto').value.trim(),
            cta: document.getElementById('anec-cta').value.trim(),
        };
        try {
            if (this._editIndex !== null) {
                await apiFetch(`/api/admin/anecdotes/${this._editIndex}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            } else {
                await apiFetch('/api/admin/anecdotes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            }
            closeModal('anec-modal');
            this._editIndex = null;
            await this.load();
        } catch (e) { alert('Error guardando: ' + e.message); }
    },

    confirmRemove(index) {
        this._pendingDeleteIndex = index;
        openModal('anec-del-modal');
    },

    async confirmDelete() {
        const index = this._pendingDeleteIndex;
        closeModal('anec-del-modal');
        this._pendingDeleteIndex = null;
        if (index === null) return;
        await this.remove(index);
    },

    async remove(index) {
        try {
            await apiFetch(`/api/admin/anecdotes/${index}`, { method: 'DELETE' });
            await this.load();
        } catch (e) {
            console.error('Error eliminando anécdota:', e);
            alert('Error eliminando: ' + e.message);
        }
    },
};

// ---------------------------------------------------------------------------
// Minibios section
// ---------------------------------------------------------------------------

const Minibios = {
    _items: [],
    _editId: null,           // null = new, string = editing existing
    _pendingDeleteId: null,

    init() { this.load(); },

    async load() {
        const el = document.getElementById('mbio-list');
        el.innerHTML = '<div class="empty-state">Cargando…</div>';
        try {
            const d = await apiFetch(`/api/admin/minibios?_t=${Date.now()}`);
            this._items = d.items || [];
            if (!this._items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">📝</div>Sin minibio encontrada.</div>';
                return;
            }
            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th style="width:60px;">ID</th><th>Nom</th><th>Bio (es)</th><th></th>
                </tr></thead>
                <tbody>${this._items.map(m => `
                    <tr>
                        <td style="color:#727971;font-size:0.75rem;">${esc(m.id)}</td>
                        <td style="font-size:0.82rem;font-weight:600;max-width:180px;">${esc((m.nombre || '').slice(0, 60))}${(m.nombre || '').length > 60 ? '…' : ''}</td>
                        <td style="font-size:0.8rem;max-width:300px;color:#3d3d37;">${esc((m.bio_es || '').slice(0, 120))}${(m.bio_es || '').length > 120 ? '…' : ''}</td>
                        <td>
                            <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                                <button class="btn btn-secondary btn-sm" onclick="Minibios.openEdit('${m.id}')">✎</button>
                                <button class="btn btn-danger btn-sm" onclick="Minibios.confirmRemove('${m.id}')">✕</button>
                            </div>
                        </td>
                    </tr>
                `).join('')}</tbody>
            </table>`;
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    openNew() {
        this._editId = null;
        document.getElementById('mbio-modal-title').textContent = 'Nueva minibio';
        document.getElementById('mbio-id').value = '';
        document.getElementById('mbio-id').readOnly = false;
        document.getElementById('mbio-nombre').value = '';
        document.getElementById('mbio-bio-es').value = '';
        document.getElementById('mbio-bio-ca').value = '';
        openModal('mbio-modal');
    },

    openEdit(id) {
        const m = this._items.find(x => x.id === id);
        if (!m) { alert('Error: no se ha encontrado la minibio. Recarga la página.'); return; }
        this._editId = id;
        document.getElementById('mbio-modal-title').textContent = `Editar minibio ${id}`;
        document.getElementById('mbio-id').value = m.id;
        document.getElementById('mbio-id').readOnly = true;
        document.getElementById('mbio-nombre').value = m.nombre || '';
        document.getElementById('mbio-bio-es').value = m.bio_es || '';
        document.getElementById('mbio-bio-ca').value = m.bio_ca || '';
        openModal('mbio-modal');
    },

    async save() {
        const id = document.getElementById('mbio-id').value.trim();
        if (!id) { alert('Hay que especificar un ID'); return; }
        const body = {
            id,
            nombre: document.getElementById('mbio-nombre').value.trim(),
            bio_es: document.getElementById('mbio-bio-es').value.trim(),
            bio_ca: document.getElementById('mbio-bio-ca').value.trim(),
        };
        try {
            if (this._editId !== null) {
                await apiFetch(`/api/admin/minibios/${encodeURIComponent(this._editId)}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            } else {
                await apiFetch('/api/admin/minibios', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
            }
            closeModal('mbio-modal');
            this._editId = null;
            await this.load();
        } catch (e) { alert('Error guardando: ' + e.message); }
    },

    confirmRemove(id) {
        this._pendingDeleteId = id;
        openModal('mbio-del-modal');
    },

    async confirmDelete() {
        const id = this._pendingDeleteId;
        closeModal('mbio-del-modal');
        this._pendingDeleteId = null;
        if (id === null) return;
        await this.remove(id);
    },

    async remove(id) {
        try {
            await apiFetch(`/api/admin/minibios/${encodeURIComponent(id)}`, { method: 'DELETE' });
            await this.load();
        } catch (e) {
            console.error('Error eliminando minibio:', e);
            alert('Error eliminando: ' + e.message);
        }
    },
};

// ---------------------------------------------------------------------------
// Tests section
// ---------------------------------------------------------------------------

const Tests = {
    init() { this.loadBank(); },

    async runQuestion() {
        const q = document.getElementById('test-question').value.trim();
        if (!q) return;
        const resultEl = document.getElementById('test-question-result');
        resultEl.style.display = '';
        resultEl.innerHTML = '<span style="color:#727971;">Ejecutando…</span>';
        try {
            const d = await apiFetch('/api/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: q, history: [] }),
            });
            resultEl.innerHTML = `
                <div style="margin-bottom:0.5rem;">
                    <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#727971;">Handler</span><br/>
                    <code style="font-size:0.8rem;color:var(--primary,#17341e);">${esc(d.handler || '—')}</code>
                </div>
                <div style="margin-bottom:0.5rem;">
                    <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#727971;">Respuesta</span><br/>
                    <span style="font-size:0.84rem;">${esc(d.answer || '—')}</span>
                </div>
                ${d.people_mentioned?.length ? `<div>
                    <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#727971;">Personas</span><br/>
                    <span style="font-size:0.78rem;color:#727971;">${d.people_mentioned.map(p => esc(p.name)).join(', ')}</span>
                </div>` : ''}
            `;
        } catch (e) {
            resultEl.innerHTML = `<span style="color:red;">${esc(e.message)}</span>`;
        }
    },

    async loadBank() {
        const el = document.getElementById('tests-list');
        el.innerHTML = '<div class="empty-state">Cargando…</div>';
        try {
            const [bank, stats] = await Promise.all([
                apiFetch('/api/tests/bank'),
                apiFetch('/api/tests/stats'),
            ]);
            document.getElementById('tests-stats').textContent =
                `Total: ${stats.total || 0} · Aprobados: ${stats.approved || 0} · Rechazados: ${stats.rejected || 0} · Pendientes: ${stats.pending || 0}`;

            if (!bank.cases?.length) {
                el.innerHTML = '<div class="empty-state">Sin casos de test.</div>';
                return;
            }

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th>Pregunta</th><th>Respuesta esperada</th><th>Handler</th><th>Veredicto</th><th></th>
                </tr></thead>
                <tbody>${bank.cases.map(c => {
                    const rowCls = c.verdict === 'approved' ? 'test-row-ok' : c.verdict === 'rejected' ? 'test-row-fail' : '';
                    return `<tr class="${rowCls}">
                        <td style="font-size:0.82rem;max-width:240px;">${esc(c.question)}</td>
                        <td class="test-answer">${esc((c.expected_answer || '').slice(0, 80))}${(c.expected_answer || '').length > 80 ? '…' : ''}</td>
                        <td class="test-handler">${esc(c.handler || '—')}</td>
                        <td>${c.verdict === 'approved'
                            ? '<span class="badge badge-resolved">✓ Aprobado</span>'
                            : c.verdict === 'rejected'
                            ? '<span class="badge badge-error">✗ Rechazado</span>'
                            : '<span class="badge badge-pending">Pendiente</span>'}</td>
                        <td>
                            <div style="display:flex;gap:0.3rem;justify-content:flex-end;">
                                <button class="btn btn-sm" style="background:#d1fae5;color:#065f46;border:none;" title="Aprobar" onclick="Tests.verdict('${esc(c.id)}','approved')">✓</button>
                                <button class="btn btn-sm" style="background:#fee2e2;color:#991b1b;border:none;" title="Rechazar" onclick="Tests.verdict('${esc(c.id)}','rejected')">✗</button>
                            </div>
                        </td>
                    </tr>`;
                }).join('')}</tbody>
            </table>`;
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    async runAll() {
        try {
            const btn = document.getElementById('tests-run-all');
            btn.disabled = true;
            btn.textContent = 'Ejecutando…';
            const d = await apiFetch('/api/tests/bank/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'all', case_ids: [] }),
            });
            btn.disabled = false;
            btn.textContent = '▷ Ejecutar todos';
            alert(`Tests completados: ${d.passed || 0} aprobados, ${d.failed || 0} fallidos de ${d.total || 0} totales.`);
            this.loadBank();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    },

    async verdict(id, verdict) {
        try {
            await apiFetch('/api/tests/bank/verdict', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ case_id: id, verdict }),
            });
            this.loadBank();
        } catch (e) { alert(e.message); }
    },

    async autoReview() {
        const btn = document.getElementById('tests-autoqa-btn');
        const box = document.getElementById('tests-autoqa');
        btn.disabled = true;
        btn.textContent = 'Verificando…';
        box.style.display = 'block';
        box.innerHTML = '<div class="info-card">Ejecutando todas las preguntas y verificándolas contra la base de datos… (puede tardar)</div>';
        try {
            const d = await apiFetch('/api/tests/bank/auto-review', { method: 'POST' });
            const fails = d.oracle_fail || [];
            box.innerHTML = `
                <div class="info-card">
                    <h3>QA automático</h3>
                    <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin:.6rem 0;font-size:.86rem;">
                        <span>✅ Verificadas OK: <b>${d.verified_ok}</b></span>
                        <span>🟢 Línea base: <b>${d.baseline}</b></span>
                        <span>❔ No verificables: <b>${d.unverifiable}</b></span>
                        <span>↩︎ Regresiones: <b>${d.regressions}</b></span>
                        <span style="color:#a33;">✗ Fallos del oráculo: <b>${fails.length}</b></span>
                    </div>
                    <p style="font-size:.8rem;color:#727971;">Los fallos del oráculo son preguntas que el router no responde como dicta la base de datos: la lista de mejoras a corregir.</p>
                    ${fails.length ? `<div style="max-height:360px;overflow:auto;margin-top:.5rem;">
                        <table class="admin-table" style="font-size:.78rem;">
                          <thead><tr><th>Pregunta</th><th>Motivo</th></tr></thead>
                          <tbody>${fails.map(f => `<tr><td>${esc(f.question)}</td><td style="color:#a33;">${esc(f.reason)}</td></tr>`).join('')}</tbody>
                        </table></div>` : '<p style="color:#2d7a33;font-weight:600;">Sin fallos de lógica. 🎉</p>'}
                </div>`;
            this.loadBank();
        } catch (e) {
            box.innerHTML = `<div class="info-card" style="color:#a33;">Error: ${esc(e.message)}</div>`;
        } finally {
            btn.disabled = false;
            btn.textContent = '✓ QA automático';
        }
    },
};

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

// Initialize status section on load
initialized['status'] = true;
Status.init();

// Pre-fetch badges for sidebar
(async () => {
    try {
        const [suggestions, queries, geo] = await Promise.all([
            apiFetch('/api/admin/suggestions').catch(() => []),
            apiFetch('/api/admin/queries').catch(() => []),
            apiFetch('/api/admin/geocoder/pending').catch(() => []),
        ]);
        const pending = suggestions.filter(s => !s.resolved_at).length;
        document.getElementById('badge-suggestions').textContent = pending || '';
        document.getElementById('badge-queries').textContent = queries.length || '';
        document.getElementById('badge-geo').textContent = geo.length || '';
    } catch {}
})();

// ---------------------------------------------------------------------------
// Configuració
// ---------------------------------------------------------------------------

const Config = (() => {
    let selectedId   = null;
    let selectedName = null;
    let searchTimer  = null;

    async function init() {
        const settings  = await apiFetch('/api/settings');
        const currentId = settings.tree_default_person || 'I4';

        // Show current person name
        try {
            const sr     = await apiFetch(`/api/search?q=${encodeURIComponent(currentId)}&limit=5`);
            const person = sr.results?.find(p => p.id.replace(/@/g, '') === currentId);
            document.getElementById('config-current').textContent =
                `Persona actual: ${person ? person.name : currentId} (${currentId})`;
        } catch (_) {
            document.getElementById('config-current').textContent = `Persona actual: ${currentId}`;
        }

        const input   = document.getElementById('config-person-search');
        const results = document.getElementById('config-person-results');
        const saveBtn = document.getElementById('config-save-btn');

        input.addEventListener('input', () => {
            clearTimeout(searchTimer);
            const q = input.value.trim();
            if (q.length < 2) { results.style.display = 'none'; return; }
            searchTimer = setTimeout(async () => {
                const data = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
                results.innerHTML = (data.results || []).map(r => {
                    const cid   = r.id.replace(/@/g, '');
                    const years = `${r.birth_year || '?'} – ${r.death_year || (r.is_alive ? 'vivo/a' : '?')}`;
                    return `<div style="padding:9px 14px;cursor:pointer;font-size:.875rem;
                                border-bottom:1px solid #f1eee5;color:#1c1c17;"
                                onmousedown="Config._select('${cid}','${esc(r.name)}')">
                                ${esc(r.name)}
                                <small style="color:#9e9b94;margin-left:6px;">${years}</small>
                            </div>`;
                }).join('') || '<div style="padding:10px 14px;color:#9e9b94;font-size:.875rem;">Sin resultados</div>';
                results.style.display = 'block';
            }, 250);
        });

        input.addEventListener('blur', () => {
            setTimeout(() => { results.style.display = 'none'; }, 150);
        });

        saveBtn.addEventListener('click', async () => {
            if (!selectedId) return;
            await apiFetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ key: 'tree_default_person', value: selectedId })
            });
            document.getElementById('config-current').textContent =
                `Persona actual: ${selectedName} (${selectedId})`;
            const msg = document.getElementById('config-save-msg');
            msg.style.display = 'inline';
            setTimeout(() => { msg.style.display = 'none'; }, 2500);
        });
    }

    function _select(id, name) {
        selectedId   = id;
        selectedName = name;
        const selBox  = document.getElementById('config-selected');
        const saveBtn = document.getElementById('config-save-btn');
        selBox.textContent    = `Seleccionado: ${name} (${id})`;
        selBox.style.display  = 'block';
        saveBtn.disabled      = false;
        saveBtn.style.opacity = '1';
        document.getElementById('config-person-search').value = '';
    }

    return { init, _select };
})();

// ---------------------------------------------------------------------------
// Comparador GEDCOM
// ---------------------------------------------------------------------------

const Comparador = {
    _pollTimer: null,
    _lastLogLen: 0,
    _rows: {},

    init() {
        this.checkStatus();
        this.loadResults();
    },

    onFileSelected(input) {
        const label = document.getElementById('cmp-drop-label');
        if (input.files[0]) {
            label.innerHTML = `<strong>${esc(input.files[0].name)}</strong><br>
                <small style="color:#9e9b94;">${fmtSize(input.files[0].size)}</small>`;
        }
    },

    async checkStatus() {
        try {
            const d = await apiFetch('/api/admin/compare/status');
            if (d.status === 'running') {
                this._showLogCard();
                this._updateStatus(d);
                this._startPolling();
            } else if (d.status === 'done' || d.status === 'error') {
                this._showLogCard();
                this._updateStatus(d);
                document.getElementById('btn-clear-cmp').style.display = '';
            }
        } catch (_) {}
    },

    async startPalazuelos() {
        const btn = document.getElementById('btn-start-cmp-palaz');
        btn.disabled = true;
        btn.textContent = 'Iniciando…';
        try {
            await apiFetch('/api/admin/compare/start-palazuelos', { method: 'POST' });
            this._showLogCard();
            this._lastLogLen = 0;
            this._startPolling();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = '▶ Comparar con Palazuelos';
            alert('Error: ' + e.message);
        }
    },

    async start() {
        const input = document.getElementById('cmp-file');
        if (!input.files[0]) { alert('Selecciona un archivo .ged primero.'); return; }
        const btn = document.getElementById('btn-start-cmp');
        btn.disabled = true;
        btn.textContent = 'Iniciando…';

        const fd = new FormData();
        fd.append('file', input.files[0]);
        try {
            await apiFetch('/api/admin/compare/start', { method: 'POST', body: fd });
            this._showLogCard();
            this._lastLogLen = 0;
            this._startPolling();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = 'Iniciar comparación por nombre';
            alert('Error: ' + e.message);
        }
    },

    _showLogCard() {
        document.getElementById('cmp-log-card').style.display = '';
    },

    _startPolling() {
        clearInterval(this._pollTimer);
        this._pollTimer = setInterval(() => this._poll(), 2000);
    },

    async _poll() {
        try {
            const d = await apiFetch('/api/admin/compare/status');
            this._updateStatus(d);
            if (d.status !== 'running') {
                clearInterval(this._pollTimer);
                this._pollTimer = null;
                const btn = document.getElementById('btn-start-cmp');
                if (btn) { btn.disabled = false; btn.textContent = 'Iniciar comparación por nombre'; }
                const btnP = document.getElementById('btn-start-cmp-palaz');
                if (btnP) { btnP.disabled = false; btnP.textContent = '▶ Comparar con Palazuelos'; }
                if (d.status === 'done') {
                    this.loadResults();
                    document.getElementById('btn-clear-cmp').style.display = '';
                }
            }
        } catch (_) {}
    },

    _updateStatus(d) {
        const badge = document.getElementById('cmp-status-badge');
        const cls   = { idle: '', running: 'badge-pending', done: 'badge-resolved', error: 'badge-error' };
        const lbl   = { idle: '', running: 'En curso…', done: '✓ Completado', error: '✗ Error' };
        badge.className = `badge ${cls[d.status] || ''}`;
        badge.textContent = lbl[d.status] || d.status;

        const pct = d.total > 0 ? Math.round((d.progress / d.total) * 100) : 0;
        document.getElementById('cmp-progress-bar').style.width = pct + '%';
        document.getElementById('cmp-progress-text').textContent =
            d.total > 0 ? `${d.progress} / ${d.total} personas (${pct}%)` : '';

        const box = document.getElementById('cmp-log');
        const newLines = (d.log || []).slice(this._lastLogLen);
        if (newLines.length) {
            box.textContent += newLines.join('\n') + '\n';
            box.scrollTop = box.scrollHeight;
            this._lastLogLen = (d.log || []).length;
        }
    },

    async loadResults() {
        const section = document.getElementById('cmp-results-section');
        const list    = document.getElementById('cmp-results-list');
        try {
            const d = await apiFetch('/api/admin/compare/results');
            if (!d.rows || !d.rows.length) {
                section.style.display = 'none';
                document.getElementById('btn-clear-cmp').style.display = 'none';
                return;
            }

            section.style.display = '';
            document.getElementById('btn-clear-cmp').style.display = '';
            const lastRun = (d.last_run || '').slice(0, 16).replace('T', ' ');
            const nomatchCount = d.rows.filter(r =>
                (r.diff_types || '').split(',').includes('nomatch')).length;
            const withDiffs = d.total_count - nomatchCount;
            document.getElementById('cmp-results-meta').textContent =
                `${withDiffs} con diferencias · ${nomatchCount} no encontradas · `
                + `última comparación: ${lastRun || '—'}`;
            const badge = document.getElementById('badge-cmp');
            badge.textContent = d.total_count || '';

            const ICONS = {
                dates: '📅 Fechas', places: '📍 Lugares', notes: '📝 Notas',
                photos: '📸 Fotos', name: '💬 Nombre', nomatch: '❓ No encontrado',
                occupations: '💼 Oficios', residences: '🏠 Residencias',
                events: '🗓 Eventos',
                possible_match: '🔍 Posible',
            };

            this._rows = {};
            d.rows.forEach(r => { this._rows[r.id] = r; });

            list.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th>Persona (BD)</th>
                    <th>Coincidència GEDCOM</th>
                    <th style="text-align:center;">Conf.</th>
                    <th>Diferencias</th>
                    <th style="text-align:center;">Detall</th>
                    <th></th>
                </tr></thead>
                <tbody>
                ${d.rows.map(row => {
                    const types  = (row.diff_types || '').split(',').filter(Boolean);
                    const badges = types.map(t =>
                        `<span class="badge ${t === 'nomatch' ? 'badge-error' : 'badge-pending'}"
                               style="margin:1px 2px;font-size:.72rem;">${esc(ICONS[t] || t)}</span>`
                    ).join('');
                    const scoreColor = row.match_score >= 90 ? '#065f46'
                                     : row.match_score >= 70 ? '#92400e' : '#991b1b';
                    const personId = (row.db_person_id || '').replace(/@/g, '');
                    const dbName = row.db_person_name || row.db_person_id || '';
                    const gedName = row.ged_person_name || '';
                    return `
                    <tr id="cmp-row-${row.id}">
                        <td style="font-size:.84rem;">
                            <a href="/dossier.html?id=${esc(personId)}" target="_blank"
                               style="color:#2d4b33;font-weight:600;">${esc(dbName)}</a>
                            <span title="Copiar nombre" style="cursor:pointer;color:#b0b8b0;font-size:.72rem;margin-left:.3rem;user-select:none;"
                                  onclick="Comparador.copyName(${JSON.stringify(dbName)})">⊕</span>
                        </td>
                        <td style="font-size:.82rem;color:#3d3d37;">
                            ${gedName
                                ? `<span style="cursor:pointer;" title="Copiar nombre" onclick="Comparador.copyName(${JSON.stringify(gedName)})">${esc(gedName)}</span>`
                                : '—'}
                        </td>
                        <td style="text-align:center;">
                            ${row.match_score > 0
                                ? `<span style="font-weight:700;color:${scoreColor};">${row.match_score}%</span>`
                                : '<span style="color:#c2c8bf;">—</span>'}
                        </td>
                        <td style="white-space:nowrap;">${badges}</td>
                        <td style="text-align:center;">
                            <button class="btn btn-secondary btn-sm"
                                onclick="Comparador.toggleDetail(${row.id}, this)">▸ Ver</button>
                        </td>
                        <td>
                            <button class="btn btn-sm" style="background:#f1eee5;color:#727971;border:1px solid #c2c8bf;" title="Descartar (no reaparece si no hay cambios)" onclick="Comparador.dismissRow(${row.id})">✕</button>
                        </td>
                    </tr>
                    <tr id="cmp-detail-${row.id}" style="display:none;">
                        <td colspan="6"
                            style="padding:.6rem 1.25rem;background:#f1eee5;font-size:.8rem;line-height:1.7;">
                            <div id="cmp-detail-content-${row.id}"></div>
                        </td>
                    </tr>`;
                }).join('')}
                </tbody></table>`;
        } catch (e) {
            list.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    toggleDetail(id, btn) {
        const detailRow = document.getElementById(`cmp-detail-${id}`);
        const contentEl = document.getElementById(`cmp-detail-content-${id}`);
        const isOpen = detailRow.style.display !== 'none';
        detailRow.style.display = isOpen ? 'none' : '';
        btn.textContent = isOpen ? '▸ Ver' : '▾ Cerrar';
        if (!isOpen && contentEl && !contentEl._loaded) {
            contentEl._loaded = true;
            const row = this._rows[id];
            if (!row) return;
            let details = {};
            try { details = JSON.parse(row.diff_details || '{}'); } catch (_) {}
            const lines = Object.values(details).flat()
                .map(item => `<div>• ${esc(String(item))}</div>`);
            contentEl.innerHTML = lines.join('') || '<em style="color:#9e9b94;">Sin detalles.</em>';
        }
    },

    async deleteRow(id) {
        try {
            await apiFetch(`/api/admin/compare/result/${id}`, { method: 'DELETE' });
            document.getElementById(`cmp-row-${id}`)?.remove();
            document.getElementById(`cmp-detail-${id}`)?.remove();
            const badge = document.getElementById('badge-cmp');
            const n = parseInt(badge.textContent || '0') - 1;
            badge.textContent = n > 0 ? n : '';
        } catch (e) { alert(e.message); }
    },

    async dismissRow(id) {
        try {
            await apiFetch(`/api/admin/compare/result/${id}/dismiss`, { method: 'POST' });
            const row = document.getElementById(`cmp-row-${id}`);
            const detail = document.getElementById(`cmp-detail-${id}`);
            if (row) { row.style.transition = 'opacity .25s'; row.style.opacity = '0'; setTimeout(() => row.remove(), 260); }
            if (detail) { detail.style.transition = 'opacity .25s'; detail.style.opacity = '0'; setTimeout(() => detail.remove(), 260); }
            const badge = document.getElementById('badge-cmp');
            const n = parseInt(badge.textContent || '0') - 1;
            badge.textContent = n > 0 ? n : '';
        } catch (e) { alert(e.message); }
    },

    copyName(name) {
        if (!name) return;
        navigator.clipboard.writeText(name).catch(() => {});
    },

    async clearAll() {
        if (!confirm('¿Borrar todos los resultados y reiniciar?')) return;
        try {
            await apiFetch('/api/admin/compare/results/all', { method: 'DELETE' });
            document.getElementById('cmp-results-section').style.display = 'none';
            document.getElementById('cmp-log-card').style.display = 'none';
            document.getElementById('btn-clear-cmp').style.display = 'none';
            document.getElementById('badge-cmp').textContent = '';
            const btn = document.getElementById('btn-start-cmp');
            btn.disabled = false;
            btn.textContent = 'Iniciar comparación';
            this._lastLogLen = 0;
        } catch (e) { alert(e.message); }
    },
};

// ---------------------------------------------------------------------------
// DocClassifier — Photo/Document Classification (4-phase pipeline)
// ---------------------------------------------------------------------------

function _guessDocType(title) {
    if (!title) return null;
    // Normalize: lowercase, strip diacritics, strip non-alphanumeric (cleans mojibake artifacts like Ã³ → a3 → space)
    const t = title.toLowerCase()
        .normalize('NFD').replace(/[̀-ͯ]/g, '')  // strip combining chars
        .replace(/[^a-z0-9]+/g, ' ')                       // non-alphanum → space
        .trim();
    const m = (re) => re.test(t);
    if (m(/defunci|esquela|obituari|necrologica|cementir|cementerio|cemetery|enterrament|enterramiento|sepultura|sepulture|sepulcre|sepulcro|\bnicho\b|\bnixol\b|\bnínxol\b|\btumba\b|\bfossa\b|\bossari\b|sepeli|sepelio|inhumaci|funeral|requiem|panteon|\bmort\b|\bdeath\b|fallec|deceso/)) return 'defuncio';
    if (m(/bautis|bautiz|bateig|baptis|christening|\bpila\b/)) return 'bautisme';
    if (m(/naix|neix|naxie|nacimien|nacidos|\bbirth\b|\bborn\b/)) return 'naixement';
    if (m(/matrimoni|matrimony|casament|\bboda\b|\bnoces\b|nupci|mariage|\bmarriage\b/)) return 'matrimoni';
    if (m(/certificat|certifica|certificate|\bacta\b|\bacte\b/)) return 'certificat';
    if (m(/\bpadr|padron|empadronament|\bcenso\b|\bcens\b/)) return 'padro';
    if (m(/testament|testamento|herencia|codicil/)) return 'testament';
    if (m(/genealogi|\barbre\b|\barbol\b|\btree\b/)) return 'arbre';
    if (m(/transcripcio|transcripcion|transcript/)) return 'transcripcio';
    if (m(/\bpoema\b|\bpoesia\b|\bpoem\b/)) return 'poema';
    if (m(/invitaci/)) return 'invitacio';
    if (m(/\bcarta\b|\bletter\b|epistol/)) return 'carta';
    if (m(/\bdibuix\b|\bdibujo\b|\bdrawing\b/)) return 'dibuix';
    if (m(/biografia|biografi|biography/)) return 'biografia';
    return null;
}

const DOC_TYPE_OPTIONS = [
    'matrimoni','defuncio','naixement','bautisme','certificat','padro',
    'testament','arbre','transcripcio','poema','invitacio','carta','dibuix','biografia','document',
];

const DocClassifier = {
    _pollTimer: null,
    _offset: 0,
    _total: 0,
    BATCH_SIZE: 20,

    async init() {
        await this.loadStats();
        await this.loadPendingQueue();
        this.checkJobStatus();
    },

    async loadStats() {
        try {
            const d = await apiFetch('/api/admin/classifier/stats');
            document.getElementById('clf-stat-total').textContent = (d.total || 0).toLocaleString();
            document.getElementById('clf-stat-docs').textContent = (d.is_document || 0).toLocaleString();
            document.getElementById('clf-stat-pending').textContent = (d.pending_review || 0).toLocaleString();

            const badge = document.getElementById('badge-classifier');
            badge.textContent = d.pending_review > 0 ? d.pending_review : '';

            const modelEl = document.getElementById('clf-model-status');
            modelEl.textContent = d.model_exists ? '✓ Modelo entrenado' : 'Zero-shot (sin modelo)';
            modelEl.className = 'badge ' + (d.model_exists ? 'badge-resolved' : 'badge-pending');

            const clipEl = document.getElementById('clf-clip-status');
            clipEl.textContent = d.clip_available ? '✓ CLIP disponible' : '✗ CLIP no instalado (pip install open-clip-torch)';
            clipEl.style.color = d.clip_available ? '#17341e' : '#991b1b';

            const o = d.by_origin || {};
            document.getElementById('clf-breakdown').innerHTML = `
                <span class="badge" style="background:#e8f0e8;color:#17341e;">Tag: ${o.tag || 0}</span>
                <span class="badge" style="background:#dbeafe;color:#1e3a8a;">Auto-CLIP: ${o.clip_auto || 0}</span>
                <span class="badge badge-pending">Revisión: ${o.clip_pending || 0}</span>
                <span class="badge badge-resolved">Humano: ${o.human || 0}</span>
                <span class="badge" style="background:#f1eee5;color:#727971;">No procesado: ${o.unprocessed || 0}</span>
            `;
        } catch (e) { console.error('clf stats error', e); }
    },

    async loadPendingQueue(append = false) {
        if (!append) this._offset = 0;
        const el = document.getElementById('clf-queue');
        if (!append) el.innerHTML = '<div class="empty-state">Cargando…</div>';
        try {
            const d = await apiFetch(`/api/admin/classifier/pending?limit=${this.BATCH_SIZE}&offset=${this._offset}`);
            this._total = d.total;
            document.getElementById('clf-queue-count').textContent =
                d.total > 0 ? `${d.total} fotos pendientes de revisión` : 'No hay fotos pendientes';

            if (!d.items.length) {
                if (!append) {
                    el.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div>Sin fotos pendientes de revisión.</div>';
                }
                document.getElementById('clf-load-more').style.display = 'none';
                return;
            }

            const html = d.items.map(item => this._renderCard(item)).join('');
            if (append) {
                el.insertAdjacentHTML('beforeend', html);
            } else {
                el.innerHTML = html;
            }
            this._offset += d.items.length;
            document.getElementById('clf-load-more').style.display =
                this._offset < this._total ? '' : 'none';
        } catch (e) {
            if (!append) el.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    },

    _renderCard(item) {
        const pct = Math.round((item.doc_confidence || 0) * 100);
        const barColor = pct >= 75 ? '#17341e' : pct >= 35 ? '#b45309' : '#6b7280';
        const guessed = _guessDocType(item.title);
        const typeOpts = DOC_TYPE_OPTIONS.map(t =>
            `<option value="${t}" ${t === guessed ? 'selected' : ''}>${t}</option>`
        ).join('');
        const guessHint = guessed
            ? `<div style="font-size:.7rem;color:#065f46;margin-bottom:.2rem;">🤖 ${guessed}</div>`
            : '';
        return `
        <div class="clf-card" id="clf-card-${item.id}">
            <div class="clf-thumb-wrap" onclick="DocClassifier.openPhotoModal('${esc(item.filename)}')">
                <img src="/photos/${esc(item.filename)}" class="clf-thumb" loading="lazy"
                     onerror="this.parentElement.innerHTML='<div style=\\'padding:.5rem;font-size:.7rem;color:#999;\\'>Sense previsualització</div>'"/>
            </div>
            <div class="clf-card-body">
                <div class="clf-title" title="${esc(item.title || '')}">${esc((item.title || '(sin título)').slice(0, 60))}</div>
                ${item.persons ? `<div style="font-size:.72rem;color:#2d4b33;margin-bottom:.3rem;opacity:.8;">👤 ${esc(item.persons)}</div>` : ''}
                <div class="clf-conf-bar-wrap">
                    <div class="clf-conf-bar" style="width:${pct}%;background:${barColor};"></div>
                </div>
                <div class="clf-conf-label">Document: <strong>${pct}%</strong></div>
                <div class="clf-actions">
                    ${guessHint}<select class="form-input clf-doctype-sel" id="clf-type-${item.id}"
                            style="flex:1;min-width:0;font-size:.77rem;padding:3px 5px;">
                        <option value="">— tipus —</option>
                        ${typeOpts}
                    </select>
                </div>
                <div class="clf-actions" style="margin-top:.4rem;">
                    <button class="btn btn-sm" style="flex:1;background:#d1fae5;color:#065f46;border:none;font-size:.78rem;"
                            onclick="DocClassifier.decide(${item.id}, 1)">✓ Documento</button>
                    <button class="btn btn-sm" style="flex:1;background:#fee2e2;color:#991b1b;border:none;font-size:.78rem;"
                            onclick="DocClassifier.decide(${item.id}, 0)">✗ Foto</button>
                </div>
            </div>
        </div>`;
    },

    async decide(photoId, isDoc) {
        const typeEl = document.getElementById(`clf-type-${photoId}`);
        const docType = isDoc ? (typeEl?.value || null) : null;
        try {
            await apiFetch('/api/admin/classifier/review', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ photo_id: photoId, is_document: isDoc, doc_type: docType }),
            });
            const card = document.getElementById(`clf-card-${photoId}`);
            if (card) {
                card.style.transition = 'opacity .3s';
                card.style.opacity = '0';
                setTimeout(() => {
                    card.remove();
                    this._total = Math.max(0, this._total - 1);
                    const el = document.getElementById('clf-queue-count');
                    el.textContent = this._total > 0
                        ? `${this._total} fotos pendientes de revisión`
                        : 'No hay fotos pendientes';
                }, 320);
            }
        } catch (e) { alert('Error: ' + e.message); }
    },

    openPhotoModal(filename) {
        document.getElementById('clf-modal-img').src = `/photos/${filename}`;
        openModal('clf-photo-modal');
    },

    async startClipScan(rescanPending = false) {
        const msg = rescanPending
            ? '¿Re-clasificar pendientes con el modelo actual? Sobreescribirá los scores anteriores.'
            : '¿Iniciar scan CLIP? Puede tardar unos minutos dependiendo del número de fotos.';
        if (!confirm(msg)) return;
        try {
            await apiFetch('/api/admin/classifier/run-clip', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit: 0, rescan_pending: rescanPending }),
            });
            document.getElementById('clf-job-card').style.display = '';
            this._startPolling();
        } catch (e) { alert('Error: ' + e.message); }
    },

    _startPolling() {
        clearInterval(this._pollTimer);
        this._pollTimer = setInterval(() => this._poll(), 1500);
    },

    async _poll() {
        try {
            const d = await apiFetch('/api/admin/classifier/status');
            this._updateJobStatus(d);
            if (d.status !== 'running') {
                clearInterval(this._pollTimer);
                this._pollTimer = null;
                if (d.status === 'done') {
                    await this.loadStats();
                    await this.loadPendingQueue();
                }
            }
        } catch (_) {}
    },

    _updateJobStatus(d) {
        const badgeMap = { idle: '', running: 'badge-pending', done: 'badge-resolved', error: 'badge-error' };
        const labelMap = { idle: '—', running: 'En curso…', done: '✓ Completado', error: '✗ Error' };
        const badge = document.getElementById('clf-job-badge');
        badge.className = 'badge ' + (badgeMap[d.status] || '');
        badge.textContent = labelMap[d.status] || d.status;

        const pct = d.total > 0 ? Math.round((d.progress / d.total) * 100) : 0;
        document.getElementById('clf-job-bar').style.width = pct + '%';
        document.getElementById('clf-job-progress').textContent = d.total > 0
            ? `${d.progress} / ${d.total} (${pct}%)  ·  docs auto: ${d.auto_doc}  ·  no-doc auto: ${d.auto_photo}  ·  revisión: ${d.pending}`
            : '';

        const logEl = document.getElementById('clf-job-log');
        logEl.textContent = (d.log || []).slice(-15).join('\n');
        logEl.scrollTop = logEl.scrollHeight;
    },

    async checkJobStatus() {
        try {
            const d = await apiFetch('/api/admin/classifier/status');
            if (d.status === 'running' || d.status === 'done' || d.status === 'error') {
                document.getElementById('clf-job-card').style.display = '';
                this._updateJobStatus(d);
                if (d.status === 'running') this._startPolling();
            }
        } catch (_) {}
    },

    async trainModel() {
        const btn = document.getElementById('clf-btn-train');
        btn.disabled = true;
        btn.textContent = 'Entrenando…';
        try {
            const d = await apiFetch('/api/admin/classifier/train', { method: 'POST' });
            if (d.ok) {
                alert(
                    `Modelo entrenado!\n` +
                    `Muestras: ${d.n_samples} (${d.n_pos} docs · ${d.n_neg} no-docs)\n` +
                    `Accuracy CV: ${(d.cv_accuracy * 100).toFixed(1)}% ± ${(d.cv_std * 100).toFixed(1)}%`
                );
                await this.loadStats();
            } else {
                alert('No se ha podido entrenar el modelo:\n' + d.error);
            }
        } catch (e) { alert('Error: ' + e.message); }
        finally {
            btn.disabled = false;
            btn.textContent = '⚙ Entrenar modelo (fase 3)';
        }
    },

    async rerunTags() {
        try {
            const d = await apiFetch('/api/admin/classifier/reclassify-tags', { method: 'POST' });
            alert(`Tags re-aplicados: ${d.updated} fotos marcadas como documento (de ${d.total_checked} revisadas).`);
            await this.loadStats();
        } catch (e) { alert('Error: ' + e.message); }
    },
};

// CSS for classifier cards (injected so no separate .css file needed)
(function injectClfStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .clf-card {
            background: var(--surface, #fff);
            border: 1px solid #e0ddd4;
            border-radius: 10px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        .clf-thumb-wrap {
            background: #f1eee5;
            height: 160px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            cursor: zoom-in;
        }
        .clf-thumb {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        .clf-card-body { padding: .65rem .75rem .75rem; }
        .clf-title {
            font-size: .79rem;
            color: #3d3d37;
            margin-bottom: .45rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .clf-conf-bar-wrap {
            background: #e8e5dc;
            border-radius: 4px;
            height: 5px;
            margin-bottom: .25rem;
            overflow: hidden;
        }
        .clf-conf-bar { height: 100%; border-radius: 4px; }
        .clf-conf-label { font-size: .71rem; color: #727971; margin-bottom: .55rem; }
        .clf-actions { display: flex; gap: .35rem; align-items: center; }
    `;
    document.head.appendChild(style);
}());

// ---------------------------------------------------------------------------
// Palazuelos sync module
// ---------------------------------------------------------------------------

const Palazuelos = (() => {
    let _mapData = [];
    let _pendingPhotos = [];
    let _existingPhotos = [];
    let _pollTimer = null;
    let _activeFilter = '';

    // ── Build map ────────────────────────────────────────────────────────────

    async function buildMap() {
        document.getElementById('btn-build-map').disabled = true;
        document.getElementById('palaz-build-status').textContent = 'Iniciando…';
        document.getElementById('palaz-build-progress').style.display = '';
        document.getElementById('palaz-build-log').textContent = '';
        try {
            await apiFetch('/api/admin/palazuelos/build-map', { method: 'POST' });
            _pollBuild();
        } catch (e) {
            document.getElementById('palaz-build-status').textContent = `Error: ${e.message}`;
            document.getElementById('btn-build-map').disabled = false;
        }
    }

    function _pollBuild() {
        _pollTimer = setInterval(async () => {
            try {
                const d = await apiFetch('/api/admin/palazuelos/build-map/status');
                const pct = d.total > 0 ? Math.round(d.progress / d.total * 100) : 0;
                document.getElementById('palaz-progress-bar').style.width = pct + '%';
                document.getElementById('palaz-build-log').textContent = d.log.join('\n');
                document.getElementById('palaz-build-status').textContent =
                    d.status === 'running' ? `${d.progress}/${d.total} personas…` :
                    d.status === 'done' ? `Hecho — ${d.result?.matched_auto ?? 0} auto, ${d.result?.needs_review ?? 0} revisión, ${d.result?.no_match ?? 0} sin match` :
                    d.status === 'error' ? 'Error (ver log)' : d.status;
                if (d.status !== 'running') {
                    clearInterval(_pollTimer); _pollTimer = null;
                    document.getElementById('btn-build-map').disabled = false;
                    if (d.status === 'done') loadMap();
                }
            } catch (e) {
                clearInterval(_pollTimer); _pollTimer = null;
                document.getElementById('btn-build-map').disabled = false;
            }
        }, 800);
    }

    // ── Map table ─────────────────────────────────────────────────────────────

    function _cat(e) {
        if (e.match_type === 'rejected') return 'rejected';
        if (!e.palaz_id) return 'nomatch';
        if (e.match_type === 'manual' || e.confidence >= 80) return 'confirmed';
        return 'review';
    }

    function _updateCounters() {
        const tots = _mapData.length;
        const confirmed = _mapData.filter(e => _cat(e) === 'confirmed').length;
        const review = _mapData.filter(e => _cat(e) === 'review').length;
        const nomatch = _mapData.filter(e => _cat(e) === 'nomatch').length;
        const rejected = _mapData.filter(e => _cat(e) === 'rejected').length;
        document.getElementById('palaz-cnt-tots').textContent = tots;
        document.getElementById('palaz-cnt-confirmed').textContent = confirmed;
        document.getElementById('palaz-cnt-review').textContent = review;
        document.getElementById('palaz-cnt-nomatch').textContent = nomatch;
        document.getElementById('palaz-cnt-rejected').textContent = rejected;
        // Badge: entries needing attention (review + no-match, not rejected — those are handled)
        const badge = document.getElementById('badge-palazuelos');
        if (badge) badge.textContent = (review + nomatch) > 0 ? review + nomatch : '';
    }

    function setFilter(f) {
        _activeFilter = f;
        // Button active state
        ['tots','confirmed','review','nomatch','rejected'].forEach(k => {
            const btn = document.getElementById(`palaz-btn-${k}`);
            if (!btn) return;
            const isActive = (k === (f || 'tots'));
            btn.className = isActive ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm';
        });
        filterMap();
    }

    async function loadMap() {
        try {
            const d = await apiFetch('/api/admin/palazuelos/map');
            _mapData = d.entries || [];
            document.getElementById('palaz-map-section').style.display = '';
            _updateCounters();
            filterMap();
        } catch (e) { console.error('loadMap:', e); }
    }

    function filterMap() {
        const q = (document.getElementById('palaz-filter-q').value || '').toLowerCase();
        const filtered = _mapData.filter(e => {
            if (_activeFilter && _cat(e) !== _activeFilter) return false;
            if (q && !((e.godes_name || '').toLowerCase().includes(q)) &&
                     !((e.palaz_name || '').toLowerCase().includes(q))) return false;
            return true;
        });
        _renderMapRows(filtered);
    }

    function _statusBadge(e) {
        if (e.match_type === 'rejected') return '<span class="badge" style="background:#d32f2f;">Rechazado</span>';
        if (e.match_type === 'manual') return '<span class="badge" style="background:#1565c0;">Manual</span>';
        if (!e.palaz_id) return '<span class="badge" style="background:#9e9b94;">Sin match</span>';
        if (e.confidence >= 80) return '<span class="badge" style="background:#2d4b33;">Auto</span>';
        return '<span class="badge" style="background:#e65100;">Revisión</span>';
    }

    function _renderRow(e) {
        const rowBg = e.match_type === 'rejected' ? '#f5f5f5' :
                      !e.palaz_id ? '#fff8f6' :
                      e.match_type === 'manual' || e.confidence >= 80 ? '' : '#fffde7';
        const years = [e.birth_year, e.death_year].filter(Boolean).join('–') || '—';
        const cat = _cat(e);
        const confirmBtn = (cat === 'review')
            ? `<button class="btn btn-secondary btn-sm" style="background:#e8f5e9;border-color:#a5d6a7;" title="Confirmar correspondència"
                       onclick="Palazuelos.confirmMatch('${esc(e.godes_id)}','${esc(e.palaz_id)}','${esc(e.palaz_name||'')}')">✓</button>`
            : '';
        return `<tr style="background:${rowBg};" data-godes-id="${esc(e.godes_id)}">
            <td><strong>${esc(e.godes_name)}</strong><br><small style="color:#9e9b94;">${esc(e.godes_id)}</small></td>
            <td style="font-size:.8rem;color:#727971;">${esc(years)}</td>
            <td>${e.palaz_id ? `<strong>${esc(e.palaz_name)}</strong><br><small style="color:#9e9b94;">${esc(e.palaz_id)}</small>` : '<span style="color:#bbb;">—</span>'}</td>
            <td style="font-weight:700;color:${e.confidence >= 80 ? '#2d4b33' : e.confidence >= 50 ? '#e65100' : '#d32f2f'};">${e.confidence || 0}</td>
            <td>${_statusBadge(e)}</td>
            <td>
                <div style="position:relative;">
                    <input type="text" class="palaz-typeahead-input" placeholder="Buscar en Palazuelos…"
                           style="width:100%;font-size:.75rem;padding:.25rem .4rem;border:1px solid #c2c8bf;border-radius:4px;"
                           data-godes-id="${esc(e.godes_id)}"
                           oninput="Palazuelos.onTypeahead(this)"
                           onblur="Palazuelos.hideDropdown(this)"/>
                    <div class="palaz-typeahead-dropdown" style="display:none;position:absolute;left:0;right:0;top:100%;background:#fff;border:1px solid #c2c8bf;border-radius:4px;z-index:100;max-height:160px;overflow-y:auto;box-shadow:0 4px 12px rgba(0,0,0,.1);"></div>
                </div>
            </td>
            <td style="white-space:nowrap;">
                ${confirmBtn}
                <button class="btn btn-secondary btn-sm" title="Rechazar" onclick="Palazuelos.rejectMatch('${esc(e.godes_id)}')">✕</button>
            </td>
        </tr>`;
    }

    function _renderMapRows(entries) {
        const tbody = document.getElementById('palaz-map-body');
        if (!entries.length) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#9e9b94;padding:2rem;">Sin entradas</td></tr>';
            return;
        }
        tbody.innerHTML = entries.map(_renderRow).join('');
    }

    // Targeted single-row update (avoids full table re-render + page jump)
    function _updateRow(godesId) {
        const entry = _mapData.find(e => e.godes_id === godesId);
        if (!entry) return;
        const tr = document.querySelector(`tr[data-godes-id="${CSS.escape(godesId)}"]`);
        if (!tr) return;
        // If current filter hides this entry now, remove the row
        const q = (document.getElementById('palaz-filter-q').value || '').toLowerCase();
        const visible = (!_activeFilter || _cat(entry) === _activeFilter) &&
                        (!q || (entry.godes_name||'').toLowerCase().includes(q) || (entry.palaz_name||'').toLowerCase().includes(q));
        if (!visible) { tr.remove(); return; }
        const tmp = document.createElement('tbody');
        tmp.innerHTML = _renderRow(entry);
        tr.parentNode.replaceChild(tmp.firstElementChild, tr);
    }

    // ── Typeahead ─────────────────────────────────────────────────────────────

    let _taTimer = null;

    async function onTypeahead(input) {
        clearTimeout(_taTimer);
        const q = input.value.trim();
        const dropdown = input.nextElementSibling;
        if (q.length < 2) { dropdown.style.display = 'none'; return; }
        _taTimer = setTimeout(async () => {
            try {
                const d = await apiFetch(`/api/admin/palazuelos/candidates?q=${encodeURIComponent(q)}&limit=10`);
                const cands = d.candidates || [];
                if (!cands.length) { dropdown.style.display = 'none'; return; }
                dropdown.innerHTML = cands.map(c => {
                    const years = [c.birth_year, c.death_year].filter(Boolean).join('–') || '';
                    return `<div class="palaz-ta-item" style="padding:.35rem .6rem;cursor:pointer;font-size:.76rem;border-bottom:1px solid #f1eee5;"
                                 onmousedown="Palazuelos.selectCandidate(event,'${esc(input.dataset.godesId)}','${esc(c.palaz_id)}','${esc(c.name)}')"
                                 onmouseover="this.style.background='#f1eee5'" onmouseout="this.style.background=''">
                                <strong>${esc(c.name)}</strong>
                                ${years ? `<span style="color:#9e9b94;margin-left:.5rem;">${esc(years)}</span>` : ''}
                                <span style="color:#9e9b94;float:right;">${c.score}%</span>
                            </div>`;
                }).join('');
                dropdown.style.display = '';
            } catch (e) { dropdown.style.display = 'none'; }
        }, 300);
    }

    function hideDropdown(input) {
        setTimeout(() => { const d = input.nextElementSibling; if (d) d.style.display = 'none'; }, 200);
    }

    async function _patchMap(godesId, payload) {
        await apiFetch(`/api/admin/palazuelos/map/${encodeURIComponent(godesId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        // Update local data
        const e = _mapData.find(x => x.godes_id === godesId);
        if (e) Object.assign(e, payload);
        _updateCounters();
        _updateRow(godesId);
    }

    async function selectCandidate(evt, godesId, palazId, palazName) {
        evt.preventDefault();
        try {
            await _patchMap(godesId, { palaz_id: palazId, palaz_name: palazName, match_type: 'manual', confidence: 100 });
        } catch (e) { alert('Error: ' + e.message); }
    }

    async function confirmMatch(godesId, palazId, palazName) {
        try {
            await _patchMap(godesId, { palaz_id: palazId, palaz_name: palazName, match_type: 'manual', confidence: 100 });
        } catch (e) { alert('Error: ' + e.message); }
    }

    async function rejectMatch(godesId) {
        try {
            // Guarda la puntuación actual del candidato (no 0): así, si más tarde
            // se reabre por puntuar alto y se vuelve a rechazar, no reaparece en
            // el siguiente "Construir mapa" (a menos que suba aún más).
            const e = (_mapData || []).find(x => x.godes_id === godesId);
            const conf = e ? (e.confidence || 0) : 0;
            await _patchMap(godesId, { palaz_id: null, palaz_name: null, match_type: 'rejected', confidence: conf });
        } catch (e) { alert('Error: ' + e.message); }
    }

    // ── Pending photos ────────────────────────────────────────────────────────

    async function loadPendingPhotos() {
        document.getElementById('palaz-photos-loading').style.display = '';
        document.getElementById('palaz-photos-empty').style.display = 'none';
        document.getElementById('palaz-photos-list').innerHTML = '';
        document.getElementById('btn-download-selected').style.display = 'none';
        _pendingPhotos = [];
        _existingPhotos = [];
        try {
            const d = await apiFetch('/api/admin/palazuelos/pending-photos');
            _pendingPhotos = d.photos || [];
            const existingByPerson = d.existing_by_person || {};
            const cdnExpired = d.cdn_expired || false;
            const cdnExpiryDate = d.cdn_expiry_date || '';
            document.getElementById('palaz-photos-loading').style.display = 'none';
            if (!_pendingPhotos.length) { document.getElementById('palaz-photos-empty').style.display = ''; return; }
            // CDN expiry warning
            const warnEl = document.getElementById('palaz-cdn-warning');
            if (warnEl) {
                if (cdnExpired) {
                    warnEl.style.display = '';
                    warnEl.textContent = `⚠️ Las URLs del GEDCOM Palazuelos caducaron el ${cdnExpiryDate}. Las miniaturas y las descargas no funcionarán hasta que re-exportes palazuelos.ged desde MyHeritage.`;
                } else {
                    warnEl.style.display = 'none';
                }
            }

            const byPerson = {};
            for (const p of _pendingPhotos) {
                const k = p.godes_person_id;
                if (!byPerson[k]) byPerson[k] = { name: p.palaz_person_name || p.godes_person_id, photos: [] };
                byPerson[k].photos.push(p);
            }
            let html = '';
            for (const [gId, grp] of Object.entries(byPerson)) {
                // Clave de descarte por foto: RIN si existe, si no el filename
                // (siempre presente) — así también se descartan fotos sin RIN.
                const grpRins = grp.photos.map(p => p.photo_rin || p.filename).filter(Boolean);
                const grpRinsJson = esc(JSON.stringify(grpRins));
                html += `<div style="margin-bottom:1.5rem;padding-bottom:1rem;border-bottom:1px solid #e5e2da;">
                    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.5rem;">
                        <span style="font-weight:700;font-size:.85rem;color:#2d4b33;">
                            ${esc(grp.name)} <span style="color:#9e9b94;font-weight:400;">(${esc(gId)})</span>
                        </span>
                        <button onclick="Palazuelos.selectPersonPhotos('${esc(gId)}')"
                                style="font-size:.7rem;padding:.15rem .5rem;border:1px solid #b0c4b1;border-radius:4px;background:#f0f6f0;color:#2d6a4f;cursor:pointer;"
                                title="Seleccionar todas las fotos de esta persona">Seleccionar todas</button>
                        <button onclick="Palazuelos.dismissPersonPhotos('${esc(gId)}','${grpRinsJson}')"
                                style="font-size:.7rem;padding:.15rem .5rem;border:1px solid #d1c4b0;border-radius:4px;background:#faf7f2;color:#9e7a5a;cursor:pointer;"
                                title="Descartar estas fotos (si aparecen nuevas, se mostrarán)">Descartar</button>
                    </div>`;
                // Pending photos (selectable)
                html += `<div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:.5rem;">`;
                for (const ph of grp.photos) {
                    const isPdf = (ph.filename || '').endsWith('.pdf');
                    const proxyUrl = `/api/admin/palazuelos/thumb?url=${encodeURIComponent(ph.url)}`;
                    const idx = _pendingPhotos.indexOf(ph);
                    const clickable = !isPdf && !cdnExpired;
                    const thumbInner = isPdf
                        ? '<span style="font-size:2rem;">📄</span>'
                        : cdnExpired
                            ? '<span style="font-size:1.8rem;opacity:.4;">📷</span>'
                            : `<img src="${proxyUrl}" alt="" loading="lazy"
                                  style="width:80px;height:60px;object-fit:cover;border-radius:4px;display:block;"
                                  onerror="this.outerHTML='<span style=\\'font-size:1.8rem;opacity:.4;\\'>📷</span>'" />`;
                    html += `<div style="display:flex;flex-direction:column;align-items:center;padding:.4rem;border:1px solid #e5e2da;border-radius:6px;background:#fff;max-width:120px;font-size:.7rem;text-align:center;">
                                <label style="display:flex;align-items:center;gap:.3rem;margin-bottom:.3rem;cursor:pointer;">
                                    <input type="checkbox" class="palaz-photo-check" data-idx="${idx}"
                                           onchange="Palazuelos.updateSelCount()"/>
                                </label>
                                <div data-palaz-idx="${idx}"
                                     style="margin-bottom:.25rem;${clickable ? 'cursor:zoom-in;' : ''}"
                                     ${clickable ? `onclick="Palazuelos.openPhotoByIdx(${idx})"` : ''}>
                                    ${thumbInner}
                                </div>
                                <span style="color:#424842;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:110px;" title="${esc(ph.title || ph.filename)}">${esc(ph.title || ph.filename)}</span>
                            </div>`;
                }
                html += `</div>`;
                // Existing DB photos (non-selectable)
                const existing = existingByPerson[gId] || [];
                if (existing.length) {
                    html += `<div style="font-size:.72rem;color:#9e9b94;margin-bottom:.3rem;">Ya tienes:</div>`;
                    html += `<div style="display:flex;flex-wrap:wrap;gap:.4rem;">`;
                    const exBase = _existingPhotos.length;
                    for (const ex of existing) {
                        const isPdf = (ex.filename || '').endsWith('.pdf');
                        const exSrc = `/photos/${esc(ex.filename)}`;
                        const exIdx = _existingPhotos.length;
                        _existingPhotos.push({ src: exSrc, title: ex.title || ex.filename });
                        const thumb = isPdf
                            ? '<span style="font-size:1.5rem;display:block;margin-bottom:.2rem;">📄</span>'
                            : `<img src="${exSrc}" alt="" loading="lazy"
                                   style="width:60px;height:45px;object-fit:cover;border-radius:3px;display:block;margin-bottom:.2rem;opacity:.75;${!isPdf ? 'cursor:zoom-in;' : ''}"
                                   onerror="this.style.display='none'"/>`;
                        html += `<div style="display:flex;flex-direction:column;align-items:center;padding:.3rem;border:1px solid #e5e2da;border-radius:5px;background:#f8f6f2;max-width:90px;font-size:.65rem;text-align:center;opacity:.85;"
                                      title="${esc(ex.title || ex.filename)}"
                                      ${!isPdf ? `onclick="Palazuelos.openExistingByIdx(${exIdx})" style="cursor:zoom-in;"` : ''}>
                                    ${thumb}
                                    <span style="color:#9e9b94;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:80px;">${esc(ex.title || ex.filename)}</span>
                                </div>`;
                    }
                    html += `</div>`;
                }
                html += `</div>`;
            }
            document.getElementById('palaz-photos-list').innerHTML = html;
            document.getElementById('btn-download-selected').style.display = '';
            updateSelCount();
        } catch (e) {
            document.getElementById('palaz-photos-loading').style.display = 'none';
            alert('Error: ' + e.message);
        }
    }

    function updateSelCount() {
        const n = document.querySelectorAll('.palaz-photo-check:checked').length;
        document.getElementById('palaz-sel-count').textContent = n || 'todas';
        document.getElementById('btn-download-selected').style.display = _pendingPhotos.length ? '' : 'none';
    }

    async function downloadSelected() {
        const checked = [...document.querySelectorAll('.palaz-photo-check:checked')];
        const toDownload = checked.length ? checked.map(cb => _pendingPhotos[parseInt(cb.dataset.idx)]) : _pendingPhotos;
        if (!toDownload.length) { alert('No hay fotos seleccionadas.'); return; }

        const log = document.getElementById('palaz-download-log');
        log.style.display = '';
        log.textContent = '';
        document.getElementById('btn-download-selected').disabled = true;

        let ok = 0, err = 0;
        for (const ph of toDownload) {
            log.textContent += `Descargando ${ph.filename}…\n`;
            log.scrollTop = log.scrollHeight;
            try {
                const res = await apiFetch('/api/admin/palazuelos/download-photo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        photo_rin: ph.photo_rin || '',
                        url: ph.url,
                        filename: ph.filename,
                        title: ph.title || '',
                        palaz_person_id: ph.palaz_person_id,
                        godes_person_id: ph.godes_person_id,
                    }),
                });
                log.textContent += `  ✓ ${res.status} (photo_id: ${res.photo_id})\n`;
                ok++;
            } catch (e) {
                log.textContent += `  ✗ Error: ${e.message}\n`;
                err++;
                if (e.message.includes('expirada')) {
                    log.textContent += '  ⚠ Re-exporta el GEDCOM de Palazuelos en MyHeritage e inténtalo de nuevo.\n';
                    break;
                }
            }
            log.scrollTop = log.scrollHeight;
        }
        log.textContent += `\nHecho: ${ok} descargadas, ${err} errores.`;
        document.getElementById('btn-download-selected').disabled = false;
        if (ok > 0) loadPendingPhotos();
    }

    function openPhotoByIdx(idx) {
        const ph = _pendingPhotos[idx];
        if (!ph) return;
        const proxyUrl = `/api/admin/palazuelos/thumb?url=${encodeURIComponent(ph.url)}`;
        openPhotoModal(proxyUrl, ph.title || ph.filename);
    }

    function openExistingByIdx(idx) {
        const ex = _existingPhotos[idx];
        if (!ex) return;
        openPhotoModal(ex.src, ex.title);
    }

    function selectPersonPhotos(godesId) {
        const indices = _pendingPhotos
            .map((p, i) => ({ p, i }))
            .filter(({ p }) => p.godes_person_id === godesId)
            .map(({ i }) => i);
        document.querySelectorAll('.palaz-photo-check').forEach(cb => {
            if (indices.includes(Number(cb.dataset.idx))) cb.checked = true;
        });
        updateSelCount();
    }

    async function dismissPersonPhotos(godesId, rinsJson) {
        let rins;
        try { rins = JSON.parse(rinsJson); } catch { rins = []; }
        if (!rins.length) return;
        try {
            await apiFetch('/api/admin/palazuelos/dismiss-photos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ godes_person_id: godesId, photo_rins: rins }),
            });
            loadPendingPhotos();
        } catch (e) { alert('Error: ' + e.message); }
    }

    function openPhotoModal(src, title) {
        const img = document.getElementById('clf-modal-img');
        img.src = src;
        img.title = title || '';
        openModal('clf-photo-modal');
    }

    async function backfillTags() {
        const statusEl = document.getElementById('palaz-backfill-status');
        statusEl.textContent = 'Reparando…';
        try {
            const res = await apiFetch('/api/admin/palazuelos/backfill-tags', { method: 'POST' });
            statusEl.textContent = `✓ ${res.tagged} nuevos tags creados (${res.processed} fotos procesadas)`;
        } catch (e) {
            statusEl.textContent = 'Error: ' + e.message;
        }
    }

    function onActivate() { loadMap(); }

    return { buildMap, loadMap, filterMap, setFilter, onTypeahead, hideDropdown,
             selectCandidate, confirmMatch, rejectMatch,
             loadPendingPhotos, updateSelCount, downloadSelected,
             dismissPersonPhotos, selectPersonPhotos, openPhotoByIdx, openExistingByIdx, openPhotoModal,
             backfillTags, onActivate };
})();

// ---------------------------------------------------------------------------
// Dedup — review duplicate photos detected per person
// ---------------------------------------------------------------------------

const Dedup = (() => {
    let bucketFilter = '';

    async function init() {
        await loadStats();
        await loadPending();
    }

    async function loadStats() {
        try {
            const d = await apiFetch('/api/admin/dedup/stats');
            const b = d.pending?.B || 0;
            const c = d.pending?.C || 0;
            document.getElementById('dedup-stat-pending-b').textContent = b;
            document.getElementById('dedup-stat-pending-c').textContent = c;
            document.getElementById('dedup-stat-blocked').textContent = d.blocked || 0;
            document.getElementById('dedup-stat-kept').textContent = d.kept_pairs || 0;
            const badge = document.getElementById('badge-dedup');
            const total = b + c;
            badge.textContent = total > 0 ? total : '';
        } catch (e) { console.error('dedup stats', e); }
    }

    async function run() {
        const status = document.getElementById('dedup-run-status');
        status.textContent = 'Escaneando…';
        try {
            const d = await apiFetch('/api/admin/dedup/run', { method: 'POST' });
            status.textContent = `✓ Auto-aplicadas ${d.auto_applied_sha256} (SHA256). Pendientes revisión: ${d.pending_review} (B=${d.buckets.B}, C=${d.buckets.C}).`;
            await loadStats();
            await loadPending();
        } catch (e) {
            status.textContent = 'Error: ' + e.message;
        }
    }

    function setFilter(b) {
        bucketFilter = b;
        document.querySelectorAll('#s-dedup .toolbar button').forEach(btn => {
            btn.classList.remove('btn-primary');
            btn.classList.add('btn-secondary');
        });
        const id = b === '' ? 'dedup-btn-all' : `dedup-btn-${b}`;
        const el = document.getElementById(id);
        if (el) { el.classList.remove('btn-secondary'); el.classList.add('btn-primary'); }
        loadPending();
    }

    function fieldBadge(label, value) {
        const ok = value !== null && value !== '' && value !== undefined;
        const color = ok ? '#17341e' : '#9aa19a';
        const bg = ok ? '#e8f0e8' : '#f1eee5';
        const display = ok ? String(value).slice(0, 30) : '—';
        return `<span class="badge" style="background:${bg};color:${color};margin:2px;font-size:.7rem;" title="${esc(String(value || ''))}">${label}: ${esc(display)}</span>`;
    }

    function photoCard(p, isWinner, candidateId, action) {
        if (!p) return '<div class="info-card">Foto eliminada</div>';
        const border = isWinner ? '2px solid #2d4b33' : '2px dashed #b8442b';
        const badge = isWinner
            ? '<span class="badge badge-resolved">CONSERVAR</span>'
            : '<span class="badge" style="background:#fde2dd;color:#7a2814;">ELIMINAR</span>';
        const isPdf = (p.filename || '').toLowerCase().endsWith('.pdf');
        const thumb = isPdf
            ? `<div style="height:180px;display:flex;align-items:center;justify-content:center;background:#f1eee5;color:#727971;font-size:1.5rem;">📄 PDF</div>`
            : `<img src="/photos/${encodeURIComponent(p.filename)}" style="width:100%;max-height:240px;object-fit:contain;background:#1a1a1a;" loading="lazy"/>`;
        return `
            <div class="info-card" style="border:${border};padding:.5rem;flex:1;min-width:260px;">
                <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem;">
                    ${badge}
                    <span style="font-size:.72rem;color:#727971;">#${p.id}</span>
                </div>
                ${thumb}
                <div style="margin-top:.4rem;font-size:.78rem;font-weight:600;">${esc(p.title || '(sin título)')}</div>
                <div style="margin-top:.3rem;display:flex;flex-wrap:wrap;">
                    ${fieldBadge('date', p.date)}
                    ${fieldBadge('place', p.place)}
                    ${fieldBadge('doc', p.is_document ? (p.doc_type || 'doc') : 'foto')}
                    ${fieldBadge('rin', p.photo_rin)}
                    ${fieldBadge('dim', p.width && p.height ? `${p.width}x${p.height}` : null)}
                    ${fieldBadge('size', p.filesize ? Math.round(p.filesize/1024) + 'KB' : null)}
                    ${fieldBadge('origin', p.doc_origin)}
                </div>
                <div style="font-size:.7rem;color:#727971;margin-top:.3rem;word-break:break-all;">${esc(p.filename)}</div>
                ${!isWinner ? `<div style="margin-top:.4rem;"><button class="btn btn-secondary btn-sm" onclick="Dedup.decide(${candidateId}, 'swap')">↔ Conservar esta en su lugar</button></div>` : ''}
            </div>
        `;
    }

    async function loadPending() {
        const list = document.getElementById('dedup-pending-list');
        list.innerHTML = '<div class="empty-state">Cargando…</div>';
        const personFilter = document.getElementById('dedup-filter-person').value.trim();
        const qs = new URLSearchParams();
        qs.set('limit', 300);
        if (personFilter) qs.set('person_id', personFilter);
        try {
            const d = await apiFetch(`/api/admin/dedup/pending?${qs}`);
            let pairs = d.pairs || [];
            if (bucketFilter) pairs = pairs.filter(p => p.bucket === bucketFilter);
            if (!pairs.length) {
                list.innerHTML = '<div class="empty-state">Sin pares pendientes.</div>';
                return;
            }
            list.innerHTML = pairs.map(pair => `
                <div class="info-card" style="margin-bottom:1rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.5rem;flex-wrap:wrap;gap:.5rem;">
                        <div>
                            <span class="badge ${pair.bucket === 'B' ? 'badge-pending' : ''}" style="background:${pair.bucket === 'B' ? '#fef3c7' : '#e0e7ff'};color:#1f2937;">Bucket ${pair.bucket}</span>
                            <span style="font-size:.82rem;font-weight:600;margin-left:.5rem;">${esc(pair.person_name || pair.person_id)}</span>
                            <span style="font-size:.72rem;color:#727971;margin-left:.5rem;">${esc(pair.person_id)}  ·  ${esc(pair.metric)}  ·  score ${pair.kept_score} vs ${pair.drop_score}</span>
                        </div>
                        <div style="display:flex;gap:.4rem;">
                            <button class="btn btn-primary btn-sm" onclick="Dedup.decide(${pair.candidate_id}, 'confirm')">✓ Eliminar duplicado</button>
                            <button class="btn btn-secondary btn-sm" onclick="Dedup.decide(${pair.candidate_id}, 'reject')">↔ Conservar ambas</button>
                        </div>
                    </div>
                    <div style="display:flex;gap:.6rem;flex-wrap:wrap;">
                        ${photoCard(pair.keep, true, pair.candidate_id, 'swap')}
                        ${photoCard(pair.drop, false, pair.candidate_id, 'swap')}
                    </div>
                </div>
            `).join('');
        } catch (e) {
            list.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
        }
    }

    async function decide(candidateId, action) {
        try {
            await apiFetch('/api/admin/dedup/decide', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ candidate_id: candidateId, action }),
            });
            await loadStats();
            await loadPending();
        } catch (e) {
            alert('Error: ' + e.message);
        }
    }

    function onActivate() { loadStats(); loadPending(); }

    return { init, loadStats, loadPending, run, setFilter, decide, onActivate };
})();
