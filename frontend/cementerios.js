// Página pública de cementerios: vista general (CartoDB) → cementerio
// (satélite Esri) con nichos agrupados en clusters numerados por personas.
// Sidebar tipo álbumes: nichos y personas enterradas, con acceso directo.

const Cementerios = {
    map: null,
    baseLayer: null,
    cemLayer: null,      // marcadores de cementerios (overview)
    clusterGroup: null,  // nichos del cementerio abierto
    nicheMarkers: {},    // niche_id → { marker, niche }
    cemeteries: [],
    overview: { niches: [], people: [] },
    current: null,       // detalle del cementerio abierto
    highlightedId: null,

    async init() {
        this.map = L.map('cem-map', { zoomControl: true });
        this.map.setView([40.2, -3.5], 6);
        this._setBase('carto');

        try {
            [this.cemeteries, this.overview] = await Promise.all([
                (await fetch('/api/cemeteries')).json(),
                (await fetch('/api/cemeteries/overview')).json(),
            ]);
        } catch (e) {
            this.toast('No se pudieron cargar los cementerios');
            return;
        }
        this.renderSidebar();
        this.showOverview(false);
        this.bindSearch();

        // Deep links: ?cemetery=ID, ?niche=ID, ?person=ID
        const params = new URLSearchParams(location.search);
        if (params.get('person')) {
            this.locatePerson(params.get('person'));
        } else if (params.get('niche')) {
            this.locateNiche(parseInt(params.get('niche'), 10));
        } else if (params.get('cemetery')) {
            this.enterCemetery(parseInt(params.get('cemetery'), 10));
        }
    },

    _setBase(kind) {
        if (this.baseLayer) this.baseLayer.remove();
        if (kind === 'esri') {
            this.baseLayer = L.tileLayer(
                'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                { attribution: 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics', maxNativeZoom: 19, maxZoom: 22 }
            );
        } else {
            this.baseLayer = L.tileLayer(
                'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
                { attribution: '© OpenStreetMap, © CARTO', maxZoom: 19 }
            );
        }
        this.baseLayer.addTo(this.map);
    },

    _numIcon(count, sizeBase, cls) {
        const size = Math.min(sizeBase + String(count).length * 6, 64);
        return L.divIcon({
            html: `<div class="${cls}" style="width:${size}px;height:${size}px;">${count}</div>`,
            className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        });
    },

    _nicheLabel(n) {
        return n.title || n.name;
    },

    // -----------------------------------------------------------------------
    // Sidebar (nichos + personas con sepultura)
    // -----------------------------------------------------------------------

    renderSidebar() {
        const nichesEl = document.getElementById('sb-niches');
        const peopleEl = document.getElementById('sb-people');

        if (!this.overview.niches.length) {
            nichesEl.innerHTML = '<p class="text-xs text-on-surface-variant px-1">Sin nichos registrados.</p>';
        } else {
            // Agrupados por cementerio
            const byCem = {};
            this.overview.niches.forEach(n => {
                (byCem[n.cemetery_id] = byCem[n.cemetery_id] || { name: n.cemetery_name, niches: [] }).niches.push(n);
            });
            nichesEl.innerHTML = Object.values(byCem).map(g => `
                <p class="text-[11px] font-bold text-on-surface-variant mt-2 mb-1 px-1">${esc(g.name)}</p>
                ${g.niches.map(n => `
                    <a class="sidebar-link flex items-center justify-between gap-2" data-niche="${n.id}"
                       onclick="Cementerios.locateNiche(${n.id})">
                        <span class="truncate">${esc(this._nicheLabel(n))}</span>
                        <span class="text-[10px] text-outline shrink-0">${n.people_count}</span>
                    </a>`).join('')}
            `).join('');
        }

        if (!this.overview.people.length) {
            peopleEl.innerHTML = '<p class="text-xs text-on-surface-variant px-1">Nadie asignado todavía.</p>';
        } else {
            peopleEl.innerHTML = this.overview.people.map(p => {
                const pid = (p.id || '').replace(/@/g, '');
                return `
                <a class="sidebar-link flex items-center gap-2" onclick="Cementerios.locatePerson('${pid}')">
                    <img src="${p.photo_file ? '/photos/' + p.photo_file : `/api/default-photo?sex=${p.sex || ''}&birth_year=${p.birth_year || ''}`}"
                         class="w-6 h-6 rounded-full object-cover border border-outline-variant/40 shrink-0"
                         onerror="this.style.visibility='hidden'"/>
                    <span class="truncate">${esc(p.name)}</span>
                    <span class="text-[10px] text-outline shrink-0 ml-auto">${p.death_year || ''}</span>
                </a>`;
            }).join('');
        }
    },

    _markSidebarNiche(nicheId) {
        document.querySelectorAll('#sb-niches .sidebar-link').forEach(a => {
            a.classList.toggle('active', a.dataset.niche === String(nicheId));
        });
    },

    // -----------------------------------------------------------------------
    // Vista general
    // -----------------------------------------------------------------------

    showOverview(fly = true) {
        this.current = null;
        this.closeNichePanel();
        this._markSidebarNiche(null);
        document.getElementById('btn-back').classList.add('hidden');
        document.getElementById('btn-back').classList.remove('flex');
        document.getElementById('cem-title').textContent = 'Cementerios';
        document.getElementById('cem-subtitle').textContent =
            'Los lugares de sepultura de la familia. Haz zoom en un cementerio para descubrir sus nichos.';
        if (this.clusterGroup) { this.clusterGroup.remove(); this.clusterGroup = null; }
        this._setBase('carto');

        if (this.cemLayer) this.cemLayer.remove();
        this.cemLayer = L.layerGroup().addTo(this.map);
        const points = [];
        this.cemeteries.forEach(c => {
            if (c.lat == null) return;
            points.push([c.lat, c.lng]);
            const m = L.marker([c.lat, c.lng], { icon: this._numIcon(c.people_count || 0, 34, 'godes-cluster') })
                .addTo(this.cemLayer);
            m.bindPopup(`
                <div style="font-family:Manrope,sans-serif;min-width:180px;">
                    <div style="font-family:'Noto Serif',serif;font-weight:700;font-size:1rem;color:#17341e;">${esc(c.name)}</div>
                    <div style="color:#727971;font-size:.8rem;margin:.15rem 0 .4rem;">${esc(c.city || '')}</div>
                    <div style="font-size:.8rem;">${c.niche_count} nichos · ${c.people_count} personas</div>
                    <button onclick="Cementerios.enterCemetery(${c.id})"
                            style="margin-top:.6rem;background:#17341e;color:#fff;border:none;border-radius:9999px;padding:.4rem 1rem;font-weight:700;font-size:.8rem;cursor:pointer;">
                        Entrar →
                    </button>
                </div>`);
        });
        const legend = document.getElementById('cem-legend');
        if (!this.cemeteries.length) {
            legend.textContent = 'Aún no hay cementerios registrados.';
        } else {
            legend.textContent = `${this.cemeteries.length} cementerios · los números indican las personas de la familia enterradas en cada uno.`;
        }
        if (points.length) {
            const bounds = L.latLngBounds(points);
            if (fly) this.map.flyToBounds(bounds, { padding: [60, 60], maxZoom: 12 });
            else this.map.fitBounds(bounds, { padding: [60, 60], maxZoom: 12 });
        }
    },

    exitCemetery() {
        this.showOverview(true);
    },

    // -----------------------------------------------------------------------
    // Vista cementerio (satélite + clusters)
    // -----------------------------------------------------------------------

    async enterCemetery(id, focusNicheId = null, highlight = false) {
        let detail;
        try {
            const res = await fetch(`/api/cemeteries/${id}`);
            if (!res.ok) throw new Error();
            detail = await res.json();
        } catch (e) {
            this.toast('Cementerio no encontrado');
            return;
        }
        this.current = detail;
        this.closeNichePanel();
        if (this.cemLayer) { this.cemLayer.remove(); this.cemLayer = null; }
        this._setBase('esri');
        const back = document.getElementById('btn-back');
        back.classList.remove('hidden');
        back.classList.add('flex');
        document.getElementById('cem-title').textContent =
            `${detail.name}${detail.city ? ', ' + detail.city : ''}`;
        document.getElementById('cem-subtitle').textContent = detail.description || '';
        document.getElementById('cem-legend').textContent =
            'Acércate para separar los grupos y toca un número para ver el nicho.';

        if (this.clusterGroup) this.clusterGroup.remove();
        const self = this;
        this.clusterGroup = L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 40,
            spiderfyOnMaxZoom: true,
            // El número del cluster suma las personas de sus nichos (estilo iPhone)
            iconCreateFunction(cluster) {
                const people = cluster.getAllChildMarkers()
                    .reduce((sum, m) => sum + (m.options.peopleCount || 0), 0);
                return self._numIcon(people || cluster.getChildCount(), 38, 'godes-cluster');
            },
        });
        this.nicheMarkers = {};
        const points = [];
        detail.niches.forEach(n => {
            if (n.lat == null) return;
            points.push([n.lat, n.lng]);
            const m = L.marker([n.lat, n.lng], {
                icon: this._numIcon(n.people.length, 28, 'godes-pin'),
                peopleCount: n.people.length,
            });
            m.on('click', () => this.openNichePanel(n));
            this.clusterGroup.addLayer(m);
            this.nicheMarkers[n.id] = { marker: m, niche: n };
        });
        this.map.addLayer(this.clusterGroup);

        if (focusNicheId && this.nicheMarkers[focusNicheId]) {
            const { marker, niche } = this.nicheMarkers[focusNicheId];
            this.clusterGroup.zoomToShowLayer(marker, () => {
                this.openNichePanel(niche);
                if (highlight) this._highlightNiche(focusNicheId);
            });
        } else if (points.length) {
            this.map.flyToBounds(L.latLngBounds(points), { padding: [60, 60], maxZoom: 18 });
        } else if (detail.lat != null) {
            this.map.flyTo([detail.lat, detail.lng], 17);
        }
    },

    _highlightNiche(nicheId) {
        this.highlightedId = nicheId;
        const entry = this.nicheMarkers[nicheId];
        if (!entry) return;
        const size = Math.min(32 + String(entry.niche.people.length).length * 6, 64);
        entry.marker.setIcon(L.divIcon({
            html: `<div class="godes-pin highlight" style="width:${size}px;height:${size}px;">${entry.niche.people.length}</div>`,
            className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        }));
        setTimeout(() => {
            if (this.highlightedId === nicheId && this.nicheMarkers[nicheId]) {
                entry.marker.setIcon(this._numIcon(entry.niche.people.length, 28, 'godes-pin'));
            }
        }, 6000);
    },

    // -----------------------------------------------------------------------
    // Panel de nicho
    // -----------------------------------------------------------------------

    openNichePanel(n) {
        this._markSidebarNiche(n.id);
        document.getElementById('np-title').textContent = this._nicheLabel(n);
        document.getElementById('np-location').textContent = n.title ? n.name : '';
        const cemEl = document.getElementById('np-cemetery');
        cemEl.innerHTML = esc(`${this.current.name}${this.current.city ? ' · ' + this.current.city : ''}`) +
            (n.fs_url
                ? ` · <a href="${esc(n.fs_url)}" target="_blank" rel="noopener"
                       style="color:#2D4B33;text-decoration:underline;">Volum a FamilySearch</a>`
                : '');

        const kindLabel = { photo: 'Nicho', record: 'Registro' };
        const photos = n.photos || [];
        document.getElementById('np-photos-title').style.display = photos.length ? '' : 'none';
        document.getElementById('np-photos').innerHTML = photos.map(p => `
            <figure class="cursor-pointer"
                    onclick="openPhotoModalUrl('/cemetery_photos/${p.filename}', { title: '${escAttr(this._nicheLabel(n))}', place: '${escAttr(this.current.name)}', note: '${escAttr(kindLabel[p.kind] || '')}' })">
                <img src="/cemetery_photos/${p.filename}" alt="${kindLabel[p.kind] || 'Foto'}"
                     class="w-full aspect-square object-cover rounded-lg border border-outline-variant/30 hover:opacity-90"/>
                <figcaption class="text-[10px] uppercase tracking-wider text-outline mt-1">${kindLabel[p.kind] || ''}</figcaption>
            </figure>`).join('');

        document.getElementById('np-notes').textContent = n.notes || '';

        const peopleEl = document.getElementById('np-people');
        // Notas del registro de enterramientos por persona identificada
        const recordNotes = {};
        (n.records || []).forEach(r => {
            if (r.person_id && (r.notes || '').trim()) recordNotes[r.person_id] = r.notes.trim();
        });
        if (!n.people.length) {
            peopleEl.innerHTML = '<p class="text-sm text-on-surface-variant">Sin personas asignadas.</p>';
        } else {
            peopleEl.innerHTML = n.people.map(p => {
                const pid = (p.id || '').replace(/@/g, '');
                const img = p.photo_file
                    ? `/photos/${p.photo_file}`
                    : `/api/default-photo?sex=${p.sex || ''}&birth_year=${p.birth_year || ''}`;
                const note = recordNotes[p.id];
                return `
                <a href="/dossier.html?id=${pid}"
                   class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-container transition">
                    <img src="${img}" class="w-10 h-10 rounded-full object-cover border border-outline-variant/40 shrink-0" onerror="this.style.visibility='hidden'"/>
                    <span class="flex-1 min-w-0">
                        <span class="block text-sm font-bold leading-tight">${esc(p.name)}</span>
                        <span class="block text-xs text-on-surface-variant">${p.birth_year || '?'} – ${p.death_year || '?'}</span>
                        ${note ? `<span class="block text-xs italic text-on-surface-variant/80 mt-0.5">${esc(note)}</span>` : ''}
                    </span>
                    <span class="material-symbols-outlined text-outline text-[18px] shrink-0">chevron_right</span>
                </a>`;
            }).join('');
        }
        this._renderRecords(n.records || []);
        document.getElementById('niche-panel').classList.add('open');
    },

    _renderRecords(records) {
        const section = document.getElementById('np-records-section');
        if (!records.length) {
            section.style.display = 'none';
            return;
        }
        section.style.display = '';
        document.getElementById('np-records-title').textContent =
            `Registro de enterramientos (${records.length})`;

        const allCols = [
            ['burial_date', 'Entierro'], ['age', 'Edad'], ['civil_status', 'Estado'],
            ['spouse', 'Cónyuge'], ['profession', 'Profesión'], ['parish', 'Parroquia'],
            ['address', 'Dirección'], ['origin', 'Origen'], ['notes', 'Notas'],
        ];
        // Oculta las columnas vacías para todos los registros de este nicho.
        const cols = allCols.filter(([key]) => records.some(r => (r[key] || '').trim()));
        const cell = (r, key) => {
            const v = (r[key] || '').trim();
            if (!v) return '<td class="empty">—</td>';
            const cls = key === 'notes' ? ' class="notes"' : '';
            return `<td${cls} title="${esc(v)}">${esc(v)}</td>`;
        };
        const nameCell = (r) => {
            const fs = r.fs_url
                ? ` <a href="${esc(r.fs_url)}" target="_blank" rel="noopener" title="Ver la página del registro en FamilySearch"
                     style="text-decoration:none;">📄</a>`
                : '';
            if (r.person_id) {
                const pid = r.person_id.replace(/@/g, '');
                return `<td><a class="rec-name in-db" href="/dossier.html?id=${pid}" title="Ver dossier">${esc(r.name)}</a>${fs}</td>`;
            }
            return `<td><span class="rec-name">${esc(r.name)}</span>${fs}</td>`;
        };
        document.getElementById('np-records').innerHTML = `
            <thead><tr><th>Nombre</th>${cols.map(([, label]) => `<th>${label}</th>`).join('')}</tr></thead>
            <tbody>${records.map(r =>
                `<tr>${nameCell(r)}${cols.map(([key]) => cell(r, key)).join('')}</tr>`).join('')}
            </tbody>`;
    },

    closeNichePanel() {
        document.getElementById('niche-panel').classList.remove('open');
    },

    // -----------------------------------------------------------------------
    // Buscador y localización
    // -----------------------------------------------------------------------

    bindSearch() {
        const input = document.getElementById('person-search');
        const results = document.getElementById('person-results');
        let timer = null;
        input.addEventListener('input', () => {
            clearTimeout(timer);
            const q = input.value.trim();
            if (q.length < 2) { results.style.display = 'none'; return; }
            timer = setTimeout(async () => {
                try {
                    const d = await (await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=8`)).json();
                    if (!d.results.length) { results.style.display = 'none'; return; }
                    results.innerHTML = d.results.map(p => `
                        <div class="result-item" onclick="Cementerios.selectPerson('${(p.id || '').replace(/@/g, '')}')">
                            <span class="block text-sm font-semibold">${esc(p.name)}</span>
                            <span class="block text-xs text-on-surface-variant">${p.birth_year || '?'} – ${p.death_year || ''}</span>
                        </div>`).join('');
                    results.style.display = 'block';
                } catch (e) { /* silencio */ }
            }, 250);
        });
        document.addEventListener('click', e => {
            if (!results.contains(e.target) && e.target !== input) results.style.display = 'none';
        });
        document.addEventListener('keydown', e => {
            if (e.key === 'Escape') {
                results.style.display = 'none';
                this.closeNichePanel();
            }
        });
    },

    selectPerson(personId) {
        document.getElementById('person-results').style.display = 'none';
        document.getElementById('person-search').value = '';
        this.locatePerson(personId);
    },

    async locatePerson(personId) {
        let loc;
        try {
            const res = await fetch(`/api/cemeteries/locate/${encodeURIComponent(personId)}`);
            if (!res.ok) { this.toast('Sin sepultura registrada para esta persona'); return; }
            loc = await res.json();
        } catch (e) {
            this.toast('Sin sepultura registrada para esta persona');
            return;
        }
        this.enterCemetery(loc.cemetery_id, loc.id, true);
    },

    locateNiche(nicheId) {
        const n = this.overview.niches.find(x => x.id === nicheId);
        if (!n) { this.toast('Nicho no encontrado'); return; }
        this.enterCemetery(n.cemetery_id, nicheId, true);
    },

    toast(msg) {
        const t = document.getElementById('cem-toast');
        t.textContent = msg;
        t.style.opacity = '1';
        setTimeout(() => { t.style.opacity = '0'; }, 2600);
    },
};

function esc(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Para strings JS dentro de atributos onclick: escapa primero para JS
// (\' y \\) y después para HTML; el navegador decodifica &#39; de vuelta a '.
function escAttr(s) {
    return esc(String(s == null ? '' : s).replace(/\\/g, '\\\\').replace(/'/g, "\\'"));
}

document.addEventListener('DOMContentLoaded', () => Cementerios.init());
