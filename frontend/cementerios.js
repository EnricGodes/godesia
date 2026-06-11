// Página pública de cementerios: vista general (CartoDB) → cementerio
// (satélite Esri) con nichos agrupados en clusters numerados por personas.

const Cementerios = {
    map: null,
    baseLayer: null,
    cemLayer: null,      // marcadores de cementerios (overview)
    clusterGroup: null,  // nichos del cementerio abierto
    nicheMarkers: {},    // niche_id → marker
    cemeteries: [],
    current: null,       // detalle del cementerio abierto
    highlightedId: null,

    async init() {
        this.map = L.map('cem-map', { zoomControl: true });
        this.map.setView([40.2, -3.5], 6);
        this._setBase('carto');

        try {
            this.cemeteries = await (await fetch('/api/cemeteries')).json();
        } catch (e) {
            this.toast('No se pudieron cargar los cementerios');
            return;
        }
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

    // -----------------------------------------------------------------------
    // Vista general
    // -----------------------------------------------------------------------

    showOverview(fly = true) {
        this.current = null;
        this.closeNichePanel();
        document.getElementById('btn-back').classList.add('hidden');
        document.getElementById('btn-back').classList.remove('flex');
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
        document.getElementById('cem-subtitle').textContent =
            `${detail.name}${detail.city ? ' — ' + detail.city : ''}. ${detail.description || ''}`;
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
        entry.marker.setIcon(this._numIconHighlight(entry.niche.people.length));
        setTimeout(() => {
            if (this.highlightedId === nicheId && this.nicheMarkers[nicheId]) {
                entry.marker.setIcon(this._numIcon(entry.niche.people.length, 28, 'godes-pin'));
            }
        }, 6000);
    },

    _numIconHighlight(count) {
        const size = Math.min(32 + String(count).length * 6, 64);
        return L.divIcon({
            html: `<div class="godes-pin highlight" style="width:${size}px;height:${size}px;">${count}</div>`,
            className: '', iconSize: [size, size], iconAnchor: [size / 2, size / 2],
        });
    },

    // -----------------------------------------------------------------------
    // Panel de nicho
    // -----------------------------------------------------------------------

    openNichePanel(n) {
        document.getElementById('np-name').textContent = n.name;
        document.getElementById('np-cemetery').textContent =
            `${this.current.name}${this.current.city ? ' · ' + this.current.city : ''}`;

        const photos = [];
        if (n.photo_file) photos.push({ file: n.photo_file, label: 'Nicho' });
        if (n.record_file) photos.push({ file: n.record_file, label: 'Registro' });
        document.getElementById('np-photos').innerHTML = photos.map(p => `
            <figure class="cursor-pointer" onclick="Cementerios.viewPhoto('/cemetery_photos/${p.file}')">
                <img src="/cemetery_photos/${p.file}" alt="${p.label}"
                     class="w-full h-28 object-cover rounded-lg border border-outline-variant/30 hover:opacity-90"/>
                <figcaption class="text-[10px] uppercase tracking-wider text-outline mt-1">${p.label}</figcaption>
            </figure>`).join('');

        document.getElementById('np-notes').textContent = n.notes || '';

        const peopleEl = document.getElementById('np-people');
        if (!n.people.length) {
            peopleEl.innerHTML = '<p class="text-sm text-on-surface-variant">Sin personas asignadas.</p>';
        } else {
            peopleEl.innerHTML = n.people.map(p => {
                const pid = (p.id || '').replace(/@/g, '');
                const img = p.photo_file
                    ? `/photos/${p.photo_file}`
                    : `/api/default-photo?sex=${p.sex || ''}&birth_year=${p.birth_year || ''}`;
                return `
                <a href="/dossier.html?id=${pid}"
                   class="flex items-center gap-3 p-2 rounded-lg hover:bg-surface-container transition">
                    <img src="${img}" class="w-10 h-10 rounded-full object-cover border border-outline-variant/40" onerror="this.style.visibility='hidden'"/>
                    <span class="flex-1">
                        <span class="block text-sm font-bold leading-tight">${esc(p.name)}</span>
                        <span class="block text-xs text-on-surface-variant">${p.birth_year || '?'} – ${p.death_year || '?'}</span>
                    </span>
                    <span class="material-symbols-outlined text-outline text-[18px]">chevron_right</span>
                </a>`;
            }).join('');
        }
        document.getElementById('niche-panel').classList.add('open');
    },

    closeNichePanel() {
        document.getElementById('niche-panel').classList.remove('open');
    },

    viewPhoto(url) {
        document.getElementById('photo-viewer-img').src = url;
        document.getElementById('photo-viewer').classList.add('open');
    },

    // -----------------------------------------------------------------------
    // Buscador de persona
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
                document.getElementById('photo-viewer').classList.remove('open');
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

    async locateNiche(nicheId) {
        // Resolver a qué cementerio pertenece el nicho recorriendo la lista
        for (const c of this.cemeteries) {
            const res = await fetch(`/api/cemeteries/${c.id}`);
            if (!res.ok) continue;
            const detail = await res.json();
            if (detail.niches.some(n => n.id === nicheId)) {
                this.enterCemetery(c.id, nicheId, true);
                return;
            }
        }
        this.toast('Nicho no encontrado');
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

document.addEventListener('DOMContentLoaded', () => Cementerios.init());
