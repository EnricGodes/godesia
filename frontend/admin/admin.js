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

const sections = ['status', 'import', 'suggestions', 'queries', 'geocoder', 'anecdotes', 'tests'];
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
                       queries: Queries, geocoder: Geocoder, anecdotes: Anecdotes, tests: Tests }[name];
        if (ctrl?.init) ctrl.init();
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
                people: 'Persones', marriages: 'Matrimonis', photos: 'Fotos',
                photo_tags: 'Tags foto', albums: 'Àlbums', suggestions: 'Aportacions',
                occupations: 'Ocupacions', residences: 'Residències', anecdotes: 'Anècdotes BD',
                geocache: 'Geocache', notes: 'Notes', events: 'Events',
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
                box.textContent = 'No hi ha logs disponibles.';
                return;
            }
            box.innerHTML = d.logs.map(l =>
                `<span class="log-${l.level}">[${esc(l.time)}] ${esc(l.message)}</span>`
            ).join('\n');
            box.scrollTop = box.scrollHeight;
        } catch (e) {
            document.getElementById('log-box').textContent = 'Error carregant logs.';
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
        msg.textContent = 'Executant…';
        try {
            const d = await apiFetch('/api/admin/server/action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action }),
            });
            msg.textContent = d.message || '✓';
            if (action === 'restart') {
                setTimeout(() => {
                    msg.textContent = 'Reconnectant…';
                    setTimeout(() => window.location.reload(), 4000);
                }, 2000);
            }
        } catch (e) {
            msg.textContent = 'Error: ' + e.message;
        }
    },

    async dbAction(action) {
        const msg = document.getElementById('db-action-msg');
        msg.textContent = 'Executant…';
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
        btn.textContent = 'Iniciant…';

        try {
            await apiFetch('/api/admin/import/gedcom', { method: 'POST', body: fd });
            this.showLogCard();
            this.lastLogLen = 0;
            this.startPolling();
        } catch (e) {
            btn.disabled = false;
            btn.textContent = 'Iniciar importació';
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
                document.getElementById('btn-start-import').textContent = 'Iniciar importació';
                document.getElementById('btn-reset-import').style.display = '';
                document.getElementById('import-post-actions').style.display = '';
            }
        } catch {}
    },

    updateLog(d) {
        const badge = document.getElementById('import-status-badge');
        const statusMap = { idle: '', running: 'running', done: 'resolved', error: 'error' };
        const labelMap = { idle: '', running: 'En curs…', done: '✓ Completat', error: '✗ Error' };
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
            alert(d.message || 'Fotos sincronitzades.');
        } catch (e) { alert('Error: ' + e.message); }
    },
};

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
        el.innerHTML = '<div class="empty-state">Carregant…</div>';
        try {
            const items = await apiFetch('/api/admin/suggestions');
            const badge = document.getElementById('badge-suggestions');
            const pending = items.filter(i => !i.resolved_at).length;
            badge.textContent = pending || '';

            if (!items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div>No hi ha aportacions.</div>';
                return;
            }

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th>Data</th><th>Qui envia</th><th>Persona afectada</th><th>Tipus</th><th>Missatge</th>
                    <th>Fitxers</th><th>Estat</th><th></th>
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
                                ? `<button class="btn btn-secondary btn-sm" onclick="Suggestions.viewFiles('${esc(s.id)}', '${esc(s.name || s.id)}')">${s.files_count} fitxer${s.files_count > 1 ? 's' : ''}</button>`
                                : '<span style="color:#c2c8bf;">—</span>'}
                        </td>
                        <td>${s.resolved_at
                            ? `<span class="badge badge-resolved">✓ Resolt</span>`
                            : `<span class="badge badge-pending">Pendent</span>`}</td>
                        <td>
                            <div style="display:flex;gap:0.4rem;justify-content:flex-end;">
                                ${!s.resolved_at ? `<button class="btn btn-secondary btn-sm" onclick="Suggestions.resolve('${esc(s.id)}')">Resoldre</button>` : ''}
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
        document.getElementById('files-modal-title').textContent = `Fitxers — ${name}`;
        document.getElementById('files-modal-body').innerHTML = 'Carregant…';
        openModal('files-modal');
        try {
            const files = await apiFetch(`/api/admin/suggestions/${id}/files`);
            if (!files.length) {
                document.getElementById('files-modal-body').innerHTML = '<p style="color:#727971;">Cap fitxer adjunt.</p>';
                return;
            }
            document.getElementById('files-modal-body').innerHTML = files.map(f => `
                <div style="display:flex;align-items:center;gap:0.75rem;padding:0.6rem 0;border-bottom:1px solid var(--outline-variant,#c2c8bf);">
                    <span style="flex:1;font-size:0.84rem;">${esc(f.name)}</span>
                    <span style="font-size:0.75rem;color:#727971;">${fmtSize(f.size)}</span>
                    <a href="${esc(f.url)}" target="_blank" class="btn btn-secondary btn-sm">Baixar</a>
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
        if (!confirm('Eliminar aquesta aportació i tots els seus fitxers?')) return;
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
        el.innerHTML = '<div class="empty-state">Carregant…</div>';
        this.selected.clear();
        this.updateDeleteBtn();
        try {
            this.items = await apiFetch('/api/admin/queries');
            const badge = document.getElementById('badge-queries');
            badge.textContent = this.items.length || '';

            if (!this.items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✓</div>Cap pregunta sense resposta.</div>';
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
        if (this.selected.size > 0) btn.textContent = `Esborrar seleccionades (${this.selected.size})`;
        else btn.textContent = 'Esborrar seleccionades';
    },

    async deleteSelected() {
        if (!this.selected.size) return;
        if (!confirm(`Esborrar ${this.selected.size} preguntes?`)) return;
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
        if (!confirm('Esborrar TOTES les preguntes sense resposta?')) return;
        try {
            const d = await apiFetch('/api/admin/queries/all', { method: 'DELETE' });
            alert(`${d.deleted} preguntes esborrades.`);
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
            `${this.pending.length} pendents · ${this.resolved.length} resoltes · ${this.validated.length} validades`;
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
                <th>#</th><th>Lloc original</th><th>Query normalitzada</th>
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
                        <button class="btn btn-primary btn-sm" onclick="Geocoder.openPanel('pending',${i})">Resoldre</button>
                    </td>
                </tr>
            `).join('');

        } else if (this.activeTab === 'resolved') {
            toolbar.style.display = '';
            document.getElementById('geo-thead').innerHTML = `<tr>
                <th>#</th><th>Lloc buscat</th><th>Adreça GPS</th>
                <th>Coordenades</th><th></th>
            </tr>`;
            document.getElementById('geo-tbody').innerHTML = data.map((e, i) => `
                <tr id="geo-row-r-${i}">
                    <td style="color:#727971;font-size:0.75rem;">${i + 1}</td>
                    <td>${esc(e.raw_place || e.query || '—')}</td>
                    <td id="geo-dn-${i}" style="font-size:0.78rem;">
                        ${e.display_name
                            ? `<span style="color:#065f46;">${esc(e.display_name)}</span>`
                            : `<button class="btn btn-secondary btn-sm" onclick="Geocoder.fetchDN(${i})">carregar</button>`}
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
                <th>#</th><th>Lloc buscat</th><th>Adreça GPS</th><th>Coordenades</th>
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
        if (!missing.length) { btn.textContent = 'Tot carregat'; this.fetchAllRunning = false; return; }
        btn.disabled = true;
        for (let k = 0; k < missing.length; k++) {
            btn.textContent = `Carregant ${k + 1}/${missing.length}…`;
            await this.fetchDN(missing[k].i);
            if (k < missing.length - 1) await new Promise(r => setTimeout(r, 1200));
        }
        btn.textContent = 'Carregat';
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
        cands.innerHTML = '<p style="font-size:0.8rem;color:#727971;">Cercant…</p>';
        try {
            const results = await apiFetch('/api/admin/geocoder/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });
            if (!results.length) {
                cands.innerHTML = '<p style="font-size:0.8rem;color:#727971;">Sense resultats.</p>';
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
        saveBtn.textContent = 'Guardant…';
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
                    if (btn) { btn.textContent = '✓ Resolt'; btn.disabled = true; }
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
};

// ---------------------------------------------------------------------------
// Anecdotes section
// ---------------------------------------------------------------------------

// Anecdotes — uses data/anecdotas.json (permanent, survives GEDCOM imports)
const Anecdotes = {
    searchQuery: '',
    searchTimer: null,
    _editIndex: null,  // null = new, number = editing existing

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
        el.innerHTML = '<div class="empty-state">Carregant…</div>';
        try {
            const url = `/api/admin/anecdotes?search=${encodeURIComponent(this.searchQuery)}&_t=${Date.now()}`;
            const d = await apiFetch(url);

            if (!d.items.length) {
                el.innerHTML = '<div class="empty-state"><div class="empty-icon">✦</div>Cap anècdota trobada.</div>';
                document.getElementById('anec-pagination').style.display = 'none';
                return;
            }
            document.getElementById('anec-pagination').style.display = 'none';

            this._items = d.items;

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th style="width:40px;">#</th><th>Títol</th><th>Text</th><th>CTA</th><th></th>
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
                                <button class="btn btn-danger btn-sm" onclick="Anecdotes.remove(${a.index})">✕</button>
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
        document.getElementById('anec-modal-title').textContent = 'Nova anècdota';
        document.getElementById('anec-titulo').value = '';
        document.getElementById('anec-texto').value = '';
        document.getElementById('anec-cta').value = '';
        openModal('anec-modal');
    },

    openEdit(index) {
        const a = (this._items || []).find(x => x.index === index);
        if (!a) { alert('Error: no s\'ha trobat l\'anècdota. Recarrega la pàgina.'); return; }
        this._editIndex = index;
        document.getElementById('anec-modal-title').textContent = `Editar anècdota #${index + 1}`;
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
        } catch (e) { alert('Error guardant: ' + e.message); }
    },

    async remove(index) {
        if (!confirm(`Eliminar anècdota #${index + 1}?`)) return;
        try {
            await apiFetch(`/api/admin/anecdotes/${index}`, { method: 'DELETE' });
            await this.load();
        } catch (e) { alert('Error eliminant: ' + e.message); }
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
        resultEl.innerHTML = '<span style="color:#727971;">Executant…</span>';
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
                    <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#727971;">Resposta</span><br/>
                    <span style="font-size:0.84rem;">${esc(d.answer || '—')}</span>
                </div>
                ${d.people_mentioned?.length ? `<div>
                    <span style="font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:#727971;">Persones</span><br/>
                    <span style="font-size:0.78rem;color:#727971;">${d.people_mentioned.map(p => esc(p.name)).join(', ')}</span>
                </div>` : ''}
            `;
        } catch (e) {
            resultEl.innerHTML = `<span style="color:red;">${esc(e.message)}</span>`;
        }
    },

    async loadBank() {
        const el = document.getElementById('tests-list');
        el.innerHTML = '<div class="empty-state">Carregant…</div>';
        try {
            const [bank, stats] = await Promise.all([
                apiFetch('/api/tests/bank'),
                apiFetch('/api/tests/stats'),
            ]);
            document.getElementById('tests-stats').textContent =
                `Total: ${stats.total || 0} · Aprovats: ${stats.approved || 0} · Rebutjats: ${stats.rejected || 0} · Pendents: ${stats.pending || 0}`;

            if (!bank.cases?.length) {
                el.innerHTML = '<div class="empty-state">Cap cas de test.</div>';
                return;
            }

            el.innerHTML = `<table class="admin-table">
                <thead><tr>
                    <th>Pregunta</th><th>Resposta esperada</th><th>Handler</th><th>Veredicte</th><th></th>
                </tr></thead>
                <tbody>${bank.cases.map(c => {
                    const rowCls = c.verdict === 'approved' ? 'test-row-ok' : c.verdict === 'rejected' ? 'test-row-fail' : '';
                    return `<tr class="${rowCls}">
                        <td style="font-size:0.82rem;max-width:240px;">${esc(c.question)}</td>
                        <td class="test-answer">${esc((c.expected_answer || '').slice(0, 80))}${(c.expected_answer || '').length > 80 ? '…' : ''}</td>
                        <td class="test-handler">${esc(c.handler || '—')}</td>
                        <td>${c.verdict === 'approved'
                            ? '<span class="badge badge-resolved">✓ Aprovat</span>'
                            : c.verdict === 'rejected'
                            ? '<span class="badge badge-error">✗ Rebutjat</span>'
                            : '<span class="badge badge-pending">Pendent</span>'}</td>
                        <td>
                            <div style="display:flex;gap:0.3rem;justify-content:flex-end;">
                                <button class="btn btn-sm" style="background:#d1fae5;color:#065f46;border:none;" title="Aprovar" onclick="Tests.verdict('${esc(c.id)}','approved')">✓</button>
                                <button class="btn btn-sm" style="background:#fee2e2;color:#991b1b;border:none;" title="Rebutjar" onclick="Tests.verdict('${esc(c.id)}','rejected')">✗</button>
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
            const btn = document.querySelector('#s-tests .toolbar-right .btn-primary');
            btn.disabled = true;
            btn.textContent = 'Executant…';
            const d = await apiFetch('/api/tests/bank/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode: 'all', case_ids: [] }),
            });
            btn.disabled = false;
            btn.textContent = '▷ Executar tots';
            alert(`Tests completats: ${d.passed || 0} aprovats, ${d.failed || 0} fallits de ${d.total || 0} totals.`);
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
