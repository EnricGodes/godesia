// ---------------------------------------------------------------------------
// Cemeteries section — manual cemetery/niche data (survives GEDCOM re-imports)
// Loaded before admin.js; registered in showSection() there.
// ---------------------------------------------------------------------------

const Cemeteries = {
    cemeteries: [],
    current: null,        // cemetery detail (with niches) currently open
    editingCemId: null,   // id being edited in the modal (null = new)
    editingNicheId: null, // id being edited in the niche view (null = new)
    deleteTarget: null,   // { type: 'cemetery'|'niche', id }
    maps: {},             // modal / detail / niche Leaflet instances
    markers: {},

    init() {
        this.load();
        this.bindPersonSearch();
    },

    _esriLayer() {
        return L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics',
            maxNativeZoom: 19, maxZoom: 22,
        });
    },

    _showView(view) {
        ['cem-view-list', 'cem-view-detail', 'cem-view-niche'].forEach(id => {
            document.getElementById(id).style.display = (id === view) ? '' : 'none';
        });
    },

    // -----------------------------------------------------------------------
    // Cemetery list
    // -----------------------------------------------------------------------

    async load() {
        try {
            this.cemeteries = await apiFetch('/api/cemeteries');
        } catch (e) {
            document.getElementById('cem-list').innerHTML = `<p style="color:#a33;">${e.message}</p>`;
            return;
        }
        const el = document.getElementById('cem-list');
        if (!this.cemeteries.length) {
            el.innerHTML = '<p style="color:#727971;font-size:.9rem;">Aún no hay cementerios. Crea el primero con «+ Nuevo cementerio».</p>';
            return;
        }
        el.innerHTML = `<table class="admin-table">
            <thead><tr><th>Nombre</th><th>Ciudad</th><th>Coordenadas</th><th>Nichos</th><th>Personas</th><th></th></tr></thead>
            <tbody>${this.cemeteries.map(c => `
                <tr>
                    <td><a href="#" onclick="Cemeteries.openDetail(${c.id});return false;" style="font-weight:600;">${esc(c.name)}</a></td>
                    <td>${esc(c.city || '')}</td>
                    <td style="font-size:.8rem;color:#727971;">${c.lat != null ? `${c.lat.toFixed(5)}, ${c.lng.toFixed(5)}` : '—'}</td>
                    <td>${c.niche_count}</td>
                    <td>${c.people_count}</td>
                    <td style="text-align:right;white-space:nowrap;">
                        <button class="btn btn-secondary btn-sm" onclick="Cemeteries.openDetail(${c.id})">Abrir</button>
                        <button class="btn btn-danger btn-sm" onclick="Cemeteries.askDelete('cemetery', ${c.id})">✕</button>
                    </td>
                </tr>`).join('')}
            </tbody></table>`;
    },

    showList() {
        this._showView('cem-view-list');
        this.load();
    },

    // -----------------------------------------------------------------------
    // Cemetery create/edit modal
    // -----------------------------------------------------------------------

    _initModalMap() {
        if (!this.maps.modal) {
            this.maps.modal = L.map('cem-map', { scrollWheelZoom: false }).setView([40.0, -3.5], 5);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap',
            }).addTo(this.maps.modal);
            this.maps.modal.on('click', e => this._setModalMarker(e.latlng.lat, e.latlng.lng));
        }
        setTimeout(() => this.maps.modal.invalidateSize(), 80);
    },

    _setModalMarker(lat, lng) {
        if (this.markers.modal) {
            this.markers.modal.setLatLng([lat, lng]);
        } else {
            this.markers.modal = L.marker([lat, lng], { draggable: true }).addTo(this.maps.modal);
            this.markers.modal.on('dragend', () => {
                const p = this.markers.modal.getLatLng();
                this._setModalMarker(p.lat, p.lng);
            });
        }
        document.getElementById('cem-coords').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    },

    _clearModalMarker() {
        if (this.markers.modal) { this.markers.modal.remove(); this.markers.modal = null; }
        document.getElementById('cem-coords').textContent = 'Sin coordenadas';
    },

    openNew() {
        this.editingCemId = null;
        document.getElementById('cem-modal-title').textContent = 'Nuevo cementerio';
        ['cem-name', 'cem-city', 'cem-description', 'cem-geo-query'].forEach(id => {
            document.getElementById(id).value = '';
        });
        openModal('cem-modal');
        this._initModalMap();
        this._clearModalMarker();
        this.maps.modal.setView([40.0, -3.5], 5);
    },

    openEdit() {
        const c = this.current;
        if (!c) return;
        this.editingCemId = c.id;
        document.getElementById('cem-modal-title').textContent = 'Editar cementerio';
        document.getElementById('cem-name').value = c.name || '';
        document.getElementById('cem-city').value = c.city || '';
        document.getElementById('cem-description').value = c.description || '';
        document.getElementById('cem-geo-query').value = '';
        openModal('cem-modal');
        this._initModalMap();
        this._clearModalMarker();
        if (c.lat != null) {
            this._setModalMarker(c.lat, c.lng);
            this.maps.modal.setView([c.lat, c.lng], 15);
        }
    },

    async geoSearch() {
        const q = document.getElementById('cem-geo-query').value.trim()
            || [document.getElementById('cem-name').value, document.getElementById('cem-city').value].filter(Boolean).join(', ');
        if (!q) return;
        try {
            const results = await apiFetch('/api/admin/geocoder/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: q }),
            });
            if (!results.length) { alert('Sin resultados en Nominatim.'); return; }
            this._setModalMarker(results[0].lat, results[0].lng);
            this.maps.modal.setView([results[0].lat, results[0].lng], 16);
        } catch (e) {
            alert('Error buscando: ' + e.message);
        }
    },

    async saveCemetery() {
        const name = document.getElementById('cem-name').value.trim();
        if (!name) { alert('El nombre es obligatorio.'); return; }
        const pos = this.markers.modal ? this.markers.modal.getLatLng() : null;
        const body = {
            name,
            city: document.getElementById('cem-city').value.trim(),
            description: document.getElementById('cem-description').value.trim(),
            lat: pos ? pos.lat : null,
            lng: pos ? pos.lng : null,
        };
        try {
            if (this.editingCemId) {
                await apiFetch(`/api/admin/cemeteries/${this.editingCemId}`, {
                    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
                });
            } else {
                await apiFetch('/api/admin/cemeteries', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
                });
            }
        } catch (e) {
            alert('Error guardando: ' + e.message);
            return;
        }
        closeModal('cem-modal');
        if (this.editingCemId && this.current && this.current.id === this.editingCemId) {
            this.openDetail(this.editingCemId);
        } else {
            this.showList();
        }
    },

    // -----------------------------------------------------------------------
    // Cemetery detail (satellite map + niche list)
    // -----------------------------------------------------------------------

    async openDetail(id) {
        try {
            this.current = await apiFetch(`/api/cemeteries/${id}`);
        } catch (e) {
            alert(e.message);
            return;
        }
        this._showView('cem-view-detail');
        const c = this.current;
        document.getElementById('cem-detail-name').textContent = `${c.name}${c.city ? ' — ' + c.city : ''}`;

        if (!this.maps.detail) {
            this.maps.detail = L.map('cem-detail-map', { scrollWheelZoom: true });
            this._esriLayer().addTo(this.maps.detail);
            this.markers.detail = L.layerGroup().addTo(this.maps.detail);
        }
        setTimeout(() => this.maps.detail.invalidateSize(), 80);
        this.markers.detail.clearLayers();
        const points = [];
        c.niches.forEach(n => {
            if (n.lat != null) {
                points.push([n.lat, n.lng]);
                L.marker([n.lat, n.lng])
                    .bindPopup(`<strong>${esc(n.name)}</strong><br>${n.people.length} personas`)
                    .addTo(this.markers.detail);
            }
        });
        if (points.length) {
            this.maps.detail.fitBounds(points, { maxZoom: 19, padding: [30, 30] });
        } else if (c.lat != null) {
            this.maps.detail.setView([c.lat, c.lng], 17);
        } else {
            this.maps.detail.setView([40.0, -3.5], 5);
        }

        const el = document.getElementById('cem-niche-list');
        if (!c.niches.length) {
            el.innerHTML = '<p style="color:#727971;font-size:.9rem;">Sin nichos todavía. Añade el primero con «+ Nuevo nicho».</p>';
            return;
        }
        el.innerHTML = `<table class="admin-table">
            <thead><tr><th>Nicho</th><th>Personas</th><th>Coordenadas</th><th>Fotos</th><th></th></tr></thead>
            <tbody>${c.niches.map(n => `
                <tr>
                    <td><a href="#" onclick="Cemeteries.openNicheEditor(${n.id});return false;" style="font-weight:600;">${esc(n.name)}</a></td>
                    <td>${n.people.map(p => esc(personShortName(p.name))).join(', ') || '—'}</td>
                    <td style="font-size:.8rem;color:#727971;">${n.lat != null ? `${n.lat.toFixed(5)}, ${n.lng.toFixed(5)}` : '—'}</td>
                    <td>${(n.photo_file ? '📷 ' : '') + (n.record_file ? '📄' : '') || '—'}</td>
                    <td style="text-align:right;white-space:nowrap;">
                        <button class="btn btn-secondary btn-sm" onclick="Cemeteries.openNicheEditor(${n.id})">Editar</button>
                        <button class="btn btn-danger btn-sm" onclick="Cemeteries.askDelete('niche', ${n.id})">✕</button>
                    </td>
                </tr>`).join('')}
            </tbody></table>`;
    },

    showDetail() {
        if (this.current) this.openDetail(this.current.id);
        else this.showList();
    },

    // -----------------------------------------------------------------------
    // Niche editor
    // -----------------------------------------------------------------------

    openNicheEditor(nicheId) {
        if (!this.current) return;
        this.editingNicheId = nicheId;
        const niche = nicheId ? this.current.niches.find(n => n.id === nicheId) : null;
        this._showView('cem-view-niche');
        document.getElementById('niche-editor-title').textContent =
            niche ? `Editar: ${niche.name}` : `Nuevo nicho en ${this.current.name}`;
        document.getElementById('niche-name').value = niche ? niche.name : '';
        document.getElementById('niche-notes').value = niche ? (niche.notes || '') : '';
        document.getElementById('niche-photo').value = '';
        document.getElementById('niche-record').value = '';
        this._renderNichePhotoPreviews(niche);

        if (!this.maps.niche) {
            this.maps.niche = L.map('niche-map', { scrollWheelZoom: true });
            this._esriLayer().addTo(this.maps.niche);
            this.maps.niche.on('click', e => this._setNicheMarker(e.latlng.lat, e.latlng.lng));
        }
        setTimeout(() => this.maps.niche.invalidateSize(), 80);
        if (this.markers.niche) { this.markers.niche.remove(); this.markers.niche = null; }
        document.getElementById('niche-coords').textContent = 'Sin coordenadas — haz clic en el mapa';
        if (niche && niche.lat != null) {
            this._setNicheMarker(niche.lat, niche.lng);
            this.maps.niche.setView([niche.lat, niche.lng], 19);
        } else if (this.current.lat != null) {
            this.maps.niche.setView([this.current.lat, this.current.lng], 17);
        } else {
            this.maps.niche.setView([40.0, -3.5], 5);
        }

        this._renderNichePeople(niche);
        this._loadSuggestions();
    },

    _setNicheMarker(lat, lng) {
        if (this.markers.niche) {
            this.markers.niche.setLatLng([lat, lng]);
        } else {
            this.markers.niche = L.marker([lat, lng], { draggable: true }).addTo(this.maps.niche);
            this.markers.niche.on('dragend', () => {
                const p = this.markers.niche.getLatLng();
                this._setNicheMarker(p.lat, p.lng);
            });
        }
        document.getElementById('niche-coords').textContent = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    },

    _renderNichePhotoPreviews(niche) {
        const photoEl = document.getElementById('niche-photo-preview');
        const recordEl = document.getElementById('niche-record-preview');
        photoEl.innerHTML = (niche && niche.photo_file)
            ? `<img src="/cemetery_photos/${niche.photo_file}" style="max-width:120px;border-radius:6px;"/>` : '';
        recordEl.innerHTML = (niche && niche.record_file)
            ? `<img src="/cemetery_photos/${niche.record_file}" style="max-width:120px;border-radius:6px;"/>` : '';
    },

    async saveNiche() {
        const name = document.getElementById('niche-name').value.trim();
        if (!name) { alert('El nombre del nicho es obligatorio.'); return; }
        const fd = new FormData();
        fd.append('name', name);
        fd.append('notes', document.getElementById('niche-notes').value.trim());
        if (this.markers.niche) {
            const p = this.markers.niche.getLatLng();
            fd.append('lat', p.lat);
            fd.append('lng', p.lng);
        }
        const photo = document.getElementById('niche-photo').files[0];
        const record = document.getElementById('niche-record').files[0];
        if (photo) fd.append('photo', photo);
        if (record) fd.append('record_photo', record);
        try {
            if (this.editingNicheId) {
                await apiFetch(`/api/admin/niches/${this.editingNicheId}`, { method: 'PUT', body: fd });
            } else {
                const r = await apiFetch(`/api/admin/cemeteries/${this.current.id}/niches`, { method: 'POST', body: fd });
                this.editingNicheId = r.id;
            }
        } catch (e) {
            alert('Error guardando el nicho: ' + e.message);
            return;
        }
        // Refresh detail data and stay in the editor (now in edit mode)
        this.current = await apiFetch(`/api/cemeteries/${this.current.id}`);
        this.openNicheEditor(this.editingNicheId);
    },

    // -----------------------------------------------------------------------
    // People assignment
    // -----------------------------------------------------------------------

    _renderNichePeople(niche) {
        const el = document.getElementById('niche-people-list');
        const searchInput = document.getElementById('niche-person-search');
        if (!this.editingNicheId) {
            searchInput.disabled = true;
            el.innerHTML = 'Guarda el nicho para poder asignar personas.';
            return;
        }
        searchInput.disabled = false;
        const people = niche ? niche.people : [];
        if (!people.length) {
            el.innerHTML = '<span style="color:#727971;">Nadie asignado todavía.</span>';
            return;
        }
        el.innerHTML = people.map(p => `
            <div style="display:flex;align-items:center;gap:.5rem;padding:.3rem 0;border-bottom:1px solid #eee;">
                <img src="${p.photo_file ? '/photos/' + p.photo_file : ''}" onerror="this.style.display='none'"
                     style="width:28px;height:28px;border-radius:50%;object-fit:cover;"/>
                <span style="flex:1;">${esc(p.name)} ${p.birth_year ? `(${p.birth_year}–${p.death_year || ''})` : ''}</span>
                <button class="btn btn-danger btn-sm" onclick="Cemeteries.removePerson('${p.id}')">✕</button>
            </div>`).join('');
    },

    bindPersonSearch() {
        const input = document.getElementById('niche-person-search');
        const results = document.getElementById('niche-person-results');
        let timer = null;
        input.addEventListener('input', () => {
            clearTimeout(timer);
            const q = input.value.trim();
            if (q.length < 2) { results.style.display = 'none'; return; }
            timer = setTimeout(async () => {
                try {
                    const d = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=8`);
                    if (!d.results.length) { results.style.display = 'none'; return; }
                    results.innerHTML = d.results.map(p => `
                        <div onclick="Cemeteries.assignPerson('${p.id}')"
                             style="padding:.45rem .6rem;cursor:pointer;border-bottom:1px solid #f0ede6;"
                             onmouseover="this.style.background='#f5f2ea'" onmouseout="this.style.background=''">
                            ${esc(p.name)} <span style="color:#727971;font-size:.8rem;">${p.birth_year || '?'}–${p.death_year || ''}</span>
                        </div>`).join('');
                    results.style.display = 'block';
                } catch (e) { /* silencio */ }
            }, 250);
        });
        document.addEventListener('click', e => {
            if (!results.contains(e.target) && e.target !== input) results.style.display = 'none';
        });
    },

    async assignPerson(personId) {
        if (!this.editingNicheId) return;
        document.getElementById('niche-person-results').style.display = 'none';
        document.getElementById('niche-person-search').value = '';
        try {
            await apiFetch(`/api/admin/niches/${this.editingNicheId}/people`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ person_id: personId }),
            });
        } catch (e) {
            alert('Error asignando: ' + e.message);
            return;
        }
        await this._refreshNiche();
    },

    async removePerson(personId) {
        try {
            await apiFetch(`/api/admin/niches/${this.editingNicheId}/people/${encodeURIComponent(personId.replace(/@/g, ''))}`, {
                method: 'DELETE',
            });
        } catch (e) {
            alert('Error quitando: ' + e.message);
            return;
        }
        await this._refreshNiche();
    },

    async _refreshNiche() {
        this.current = await apiFetch(`/api/cemeteries/${this.current.id}`);
        const niche = this.current.niches.find(n => n.id === this.editingNicheId);
        this._renderNichePeople(niche);
        this._loadSuggestions();
    },

    // -----------------------------------------------------------------------
    // GEDCOM burial suggestions
    // -----------------------------------------------------------------------

    async _loadSuggestions() {
        const el = document.getElementById('niche-suggestions');
        if (!this.current) return;
        try {
            const d = await apiFetch(`/api/admin/cemeteries/${this.current.id}/burial-suggestions`);
            if (!d.suggestions.length) {
                el.innerHTML = '<span style="color:#727971;font-size:.85rem;">Sin sugerencias pendientes.</span>';
                return;
            }
            const canAssign = !!this.editingNicheId;
            el.innerHTML = d.suggestions.map(s => `
                <div style="display:flex;align-items:flex-start;gap:.5rem;padding:.4rem 0;border-bottom:1px solid #eee;">
                    <div style="flex:1;">
                        <div style="font-weight:600;font-size:.85rem;">${esc(s.name)} <span style="font-weight:400;color:#727971;">${s.birth_year || '?'}–${s.death_year || ''}</span></div>
                        <div style="font-size:.78rem;color:#727971;">${esc(s.place_detail || s.place || '')}${s.date ? ' · ' + esc(s.date) : ''}</div>
                    </div>
                    ${canAssign ? `<button class="btn btn-primary btn-sm" onclick="Cemeteries.assignPerson('${s.person_id}')">+ Asignar</button>` : ''}
                </div>`).join('');
        } catch (e) {
            el.innerHTML = `<span style="color:#a33;font-size:.85rem;">${e.message}</span>`;
        }
    },

    // -----------------------------------------------------------------------
    // Deletion (shared confirm modal)
    // -----------------------------------------------------------------------

    askDelete(type, id) {
        this.deleteTarget = { type, id };
        if (type === 'cemetery') {
            const c = this.cemeteries.find(x => x.id === id) || this.current;
            document.getElementById('cem-del-title').textContent = 'Eliminar cementerio';
            document.getElementById('cem-del-text').textContent =
                `¿Seguro que quieres eliminar «${c ? c.name : ''}»? Se borrarán también sus nichos, fotos y asignaciones. Esta acción no se puede deshacer.`;
        } else {
            const n = this.current ? this.current.niches.find(x => x.id === id) : null;
            document.getElementById('cem-del-title').textContent = 'Eliminar nicho';
            document.getElementById('cem-del-text').textContent =
                `¿Seguro que quieres eliminar el nicho «${n ? n.name : ''}» con sus fotos y asignaciones?`;
        }
        openModal('cem-del-modal');
    },

    async confirmDelete() {
        const t = this.deleteTarget;
        if (!t) return;
        try {
            if (t.type === 'cemetery') {
                await apiFetch(`/api/admin/cemeteries/${t.id}?force=1`, { method: 'DELETE' });
            } else {
                await apiFetch(`/api/admin/niches/${t.id}`, { method: 'DELETE' });
            }
        } catch (e) {
            alert('Error eliminando: ' + e.message);
            closeModal('cem-del-modal');
            return;
        }
        closeModal('cem-del-modal');
        this.deleteTarget = null;
        if (t.type === 'cemetery') this.showList();
        else this.showDetail();
    },
};

function personShortName(name) {
    return (name || '').replace(/\s+/g, ' ').trim();
}
