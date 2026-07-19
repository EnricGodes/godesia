/* admin_emili.js — pestaña "Emili Godes": clasificador asistido del archivo. */
const Emili = {
    _pollTimer: null,
    _cats: [],
    _costCap: 1.0,

    async init() {
        await this.loadStats();
        await this.updateEstimate();
        await this.loadReview();
    },

    async loadStats() {
        try {
            const d = await apiFetch('/api/admin/emili/stats');
            this._cats = d.categories || [];
            this._costCap = d.cost_cap || 1.0;
            const main = document.getElementById('emili-main');
            const unav = document.getElementById('emili-unavailable');
            if (!d.archive_available) {
                main.style.display = 'none';
                unav.style.display = '';
                return;
            }
            main.style.display = '';
            unav.style.display = 'none';
            const bs = d.by_status || {};
            const cell = (label, val, color) =>
                `<div class="stat-card"><div class="stat-value" style="color:${color||'#e8e6df'}">${val||0}</div><div class="stat-label">${label}</div></div>`;
            document.getElementById('emili-stats').innerHTML =
                cell('Total', d.total) +
                cell('Pendientes', bs['pendiente'], '#c9a227') +
                cell('En lote', bs['en_lote'], '#5a8') +
                cell('Analizadas', bs['analizada'], '#6ab') +
                cell('Aprobadas', bs['aprobada'], '#7b7') +
                cell('Coste ac. ($)', (d.coste_acumulado||0).toFixed(3), '#b78');
        } catch (e) { console.error(e); }
    },

    async updateEstimate() {
        try {
            const limit = document.getElementById('emili-limit').value;
            const d = await apiFetch(`/api/admin/emili/estimate?limit=${limit}`);
            const el = document.getElementById('emili-estimate');
            const btn = document.getElementById('emili-analyze-btn');
            const over = d.coste_estimado > d.cost_cap;
            el.innerHTML = `≈ $${d.coste_estimado} · ${d.n} imgs` +
                (over ? ` <span style="color:#e57">(supera tope $${d.cost_cap})</span>` : '');
            btn.disabled = over || d.n <= 0;
            btn.style.opacity = btn.disabled ? .5 : 1;
        } catch (e) { console.error(e); }
    },

    async scan() {
        try {
            const d = await apiFetch('/api/admin/emili/scan', { method: 'POST' });
            alert(`Escaneo: ${d.added} nuevas, ${d.skipped} ya existentes.`);
            await this.loadStats();
            await this.updateEstimate();
        } catch (e) { alert('Error: ' + e.message); }
    },

    async analyze() {
        const limit = parseInt(document.getElementById('emili-limit').value, 10);
        if (!confirm(`¿Lanzar un lote de ${limit} imágenes? Esto consume saldo de la API.`)) return;
        try {
            const d = await apiFetch('/api/admin/emili/analyze', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ limit }),
            });
            document.getElementById('emili-job').style.display = '';
            this._startPolling();
            await this.loadStats();
        } catch (e) { alert('Error: ' + e.message); }
    },

    _startPolling() {
        clearInterval(this._pollTimer);
        this._pollTimer = setInterval(() => this._pollJob(), 3000);
        this._pollJob();
    },

    async _pollJob() {
        try {
            const d = await apiFetch('/api/admin/emili/status');
            document.getElementById('emili-job').style.display = '';
            document.getElementById('emili-job-phase').textContent =
                `Estado: ${d.status} · ${d.phase || ''} ${d.error ? '· ERROR: ' + d.error : ''}`;
            document.getElementById('emili-job-log').innerHTML =
                (d.log || []).slice(-40).map(l => `<div>${l}</div>`).join('');
            if (d.status !== 'running') {
                clearInterval(this._pollTimer);
                await this.loadStats();
                await this.loadReview();
            }
        } catch (_) {}
    },

    async poll() {
        try {
            const d = await apiFetch('/api/admin/emili/poll', { method: 'POST' });
            alert('Recogida: ' + JSON.stringify(d));
            await this.loadStats();
            await this.loadReview();
        } catch (e) { alert('Error: ' + e.message); }
    },

    async loadReview() {
        try {
            const d = await apiFetch('/api/admin/emili/review?status=analizada&limit=300');
            const items = d.items || [];
            const cont = document.getElementById('emili-review');
            if (!items.length) { cont.innerHTML = '<p class="section-subtitle">No hay fichas analizadas pendientes de revisión.</p>'; return; }
            // agrupar por proyecto
            const groups = {};
            items.forEach(it => { (groups[it.proyecto || 'Sin proyecto'] ||= []).push(it); });
            const catOpts = (sel) => this._cats.map(c =>
                `<option value="${c}"${c===sel?' selected':''}>${c}</option>`).join('');
            let html = '';
            for (const [proj, arr] of Object.entries(groups)) {
                const ids = arr.map(x => x.id);
                html += `<div style="margin:1rem 0;border:1px solid #2a2a24;border-radius:8px;padding:.75rem;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h3 style="margin:0;font-size:.95rem;">${proj} <span style="color:#727971;font-weight:400;">(${arr.length})</span></h3>
                        <button class="btn btn-primary btn-sm" onclick='Emili.approve(${JSON.stringify(ids)})'>✓ Aprobar grupo</button>
                    </div>
                    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:.75rem;margin-top:.75rem;">`;
                for (const it of arr) {
                    html += `<div style="background:#12120f;border:1px solid #2a2a24;border-radius:6px;padding:.5rem;">
                        <img src="/api/admin/emili/thumb/${it.id}" loading="lazy" style="width:100%;height:150px;object-fit:cover;border-radius:4px;background:#000;">
                        <div style="font-size:.7rem;color:#727971;margin:.3rem 0;">${it.orig_filename} · conf ${(it.confianza??0)}</div>
                        <input class="form-input" style="font-size:.8rem;margin-bottom:.25rem;" value="${(it.proyecto||'').replace(/"/g,'&quot;')}" placeholder="proyecto" onchange="Emili.savePhoto(${it.id},'proyecto',this.value)">
                        <select class="form-input" style="font-size:.8rem;margin-bottom:.25rem;" onchange="Emili.savePhoto(${it.id},'categoria',this.value)">${catOpts(it.categoria)}</select>
                        <div style="display:flex;gap:.25rem;margin-bottom:.25rem;">
                            <input class="form-input" style="font-size:.8rem;" value="${(it.fecha_estimada||'').replace(/"/g,'&quot;')}" placeholder="fecha" onchange="Emili.savePhoto(${it.id},'fecha_estimada',this.value)">
                            <input class="form-input" style="font-size:.8rem;" value="${(it.lugar||'').replace(/"/g,'&quot;')}" placeholder="lugar" onchange="Emili.savePhoto(${it.id},'lugar',this.value)">
                        </div>
                        <textarea class="form-input" style="font-size:.8rem;width:100%;min-height:52px;" placeholder="descripción" onchange="Emili.savePhoto(${it.id},'descripcion',this.value)">${it.descripcion||''}</textarea>
                        <div style="display:flex;gap:.25rem;margin-top:.25rem;">
                            <button class="btn btn-primary btn-sm" style="flex:1;" onclick="Emili.approve([${it.id}])">✓ Aprobar</button>
                        </div>
                    </div>`;
                }
                html += `</div></div>`;
            }
            cont.innerHTML = html;
        } catch (e) { console.error(e); }
    },

    async savePhoto(id, field, value) {
        try {
            await apiFetch(`/api/admin/emili/photo/${id}`, {
                method: 'PATCH', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [field]: value }),
            });
        } catch (e) { alert('Error guardando: ' + e.message); }
    },

    async approve(ids) {
        try {
            const d = await apiFetch('/api/admin/emili/approve', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids }),
            });
            await this.loadStats();
            await this.loadReview();
        } catch (e) { alert('Error: ' + e.message); }
    },

    async export() {
        try {
            const d = await apiFetch('/api/admin/emili/export', { method: 'POST' });
            alert(`Exportado: ${d.aprobadas} imágenes.\nobra.json y inventario_maestro.md regenerados.`);
        } catch (e) { alert('Error: ' + e.message); }
    },
};
