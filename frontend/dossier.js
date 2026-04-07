async function loadDossier() {
    const params = new URLSearchParams(window.location.search);
    const personId = params.get('id');

    if (!personId) {
        showError('Persona no especificada');
        return;
    }

    try {
        const res = await fetch(`/api/dossier/${personId}`);
        if (!res.ok) {
            throw new Error('Persona no encontrada');
        }

        const data = await res.json();
        renderDossier(data);
    } catch (e) {
        showError(e.message);
    }
}

function showError(message) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'block';
    document.getElementById('error').textContent = 'Error: ' + message;
}

// Global state for photo sorting
let _photosOriginal = [];
let _sortActive = null;

function extractYear(dateStr) {
    if (!dateStr) return null;
    const m = dateStr.match(/\d{4}/);
    return m ? parseInt(m[0]) : null;
}

window.sortPhotos = function(criterion) {
    if (_sortActive === criterion) {
        _sortActive = null;
        renderBentoGrid(_photosOriginal);
    } else {
        _sortActive = criterion;
        const sorted = [..._photosOriginal];
        if (criterion === 'oldest') {
            sorted.sort((a, b) => {
                const yA = extractYear(a.date) ?? Infinity;
                const yB = extractYear(b.date) ?? Infinity;
                return yA - yB;
            });
        } else if (criterion === 'newest') {
            sorted.sort((a, b) => {
                const yA = extractYear(a.date) ?? -Infinity;
                const yB = extractYear(b.date) ?? -Infinity;
                return yB - yA;
            });
        } else if (criterion === 'added') {
            sorted.sort((a, b) => a.id - b.id);
        }
        renderUniformGrid(sorted);
    }
    updateSortButtons();
};

function updateSortButtons() {
    ['oldest', 'newest', 'added'].forEach(c => {
        const btn = document.getElementById('sort-' + c);
        if (!btn) return;
        if (_sortActive === c) {
            btn.classList.add('bg-primary', 'text-on-primary');
            btn.classList.remove('border', 'border-primary', 'text-primary');
        } else {
            btn.classList.remove('bg-primary', 'text-on-primary');
            btn.classList.add('border', 'border-primary', 'text-primary');
        }
    });
}

function renderDossier(data) {
    const person = data.person;
    document.title = `${person.name} | Familia Godes`;

    // 1. HEADER
    if (person.photo_file && person.photo_file.trim()) {
        document.querySelector('#hero-photo img').src = `/photos/${person.photo_file}`;
    }
    document.getElementById('hero-name').textContent = person.name;

    const birthYear = person.birth_year || '?';
    const birthPlace = person.birth_place || 'Barcelona, España';
    const vitalDatesEl = document.getElementById('vital-dates');
    vitalDatesEl.classList.remove('flex-wrap', 'items-center', 'gap-6');
    vitalDatesEl.classList.add('flex-col', 'gap-2');

    // Only show death date if it exists or death_year is set
    let deathDisplay = '';
    if (person.death_date || person.death_year) {
        const deathYear = person.death_year || '?';
        deathDisplay = ` — ${person.death_date || deathYear}`;
    }

    vitalDatesEl.innerHTML = `
        <span>${person.birth_date || birthYear}${deathDisplay}</span>
        <span class="text-lg opacity-70">${birthPlace}</span>
    `;

    document.getElementById('stats-boxes').innerHTML = `
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">Inventario</span>
            <span class="font-bold">${person.photo_count || 0} Medios</span>
        </div>
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">Última Act.</span>
            <span class="font-bold">${data.gedcom_date || '—'}</span>
        </div>
        ${person.death_year && person.death_year >= 2021 && !person.is_alive ? `
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">Estado</span>
            <span class="font-bold text-secondary">† RECIENTE</span>
        </div>
        ` : ''}
    `;

    // 2. PERFIL BÁSICO
    renderPerfil(data);

    // 3. RED FAMILIAR
    renderFamilyTree(data);

    // 4. FOTOS (BENTO)
    renderPhotosGrid(data.photos);

    // 5. DOCUMENTOS
    renderDocuments(data);

    // 6. CRONOGRAMA
    renderTimeline(data);

    // 7. CARRERA
    renderCareer(data.occupations);

    // 8. MILITAR
    renderMilitary(data);

    // 9. NOTAS
    renderNotes(data.notes);

    document.getElementById('loading').style.display = 'none';
    document.getElementById('content').style.display = 'block';
}

function renderPerfil(data) {
    const person = data.person;

    // Extract baptism data from notes for baptism names
    let baptismNames = '';
    let baptismDate = person.baptism_date || '';
    let baptismPlace = person.baptism_place || '';
    let godparents = person.godparents || '';

    if (data.notes && data.notes.length > 0) {
        const notesText = data.notes.join(' ');

        // Extract baptism names: "amb els noms d'Artur, Carles i Mariano"
        const namesMatch = notesText.match(/amb els noms[s]? d[\'e]([^.]+)/);
        if (namesMatch) {
            baptismNames = namesMatch[1].trim();
        }
    }

    const html = `
        <div class="space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">fingerprint</span>
                Perfil de Registro
            </h2>
            <div class="bg-surface-container-low p-8 rounded-xl heritage-border space-y-6 min-h-[280px]">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Nombre Completo</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.name}</span>
                            ${baptismNames ? `<span class="italic opacity-80 text-xs mt-1 block">Nombres de bautismo: ${baptismNames}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Género</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.sex === 'M' ? 'Masculino' : 'Femenino'}</span>
                        </dd>
                    </div>
                </div>
                <div class="pt-6 border-t border-outline-variant/30 grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Nacimiento</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.birth_date || person.birth_year}</span>
                            ${person.birth_place ? `<span class="italic opacity-80 text-xs">${person.birth_place}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Bautismo</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${baptismDate || '—'}</span>
                            ${baptismPlace ? `<span class="italic opacity-80 text-xs">${baptismPlace}</span>` : '<span class="italic opacity-80 text-xs">No registrado</span>'}
                            ${godparents ? `<span class="italic opacity-80 text-xs block mt-1">Padrinos: ${godparents}</span>` : ''}
                        </dd>
                    </div>
                </div>
            </div>
        </div>
        ${person.death_date || person.death_year ? `
        <div class="space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">account_balance</span>
                Defunción y Sepelio
            </h2>
            <div class="bg-surface-container-highest/30 p-8 rounded-xl heritage-border space-y-6 min-h-[280px]">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Fallecimiento</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.death_date || person.death_year}${person.death_age ? ' (' + person.death_age + ' años)' : ''}</span>
                            ${person.death_place ? `<span class="italic opacity-80 text-xs">${person.death_place}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Causa</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.death_cause || '—'}</span>
                        </dd>
                    </div>
                </div>
                ${data.burial && data.burial.length > 0 ? `
                <div class="pt-6 border-t border-outline-variant/30">
                    <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-4">Localización Exacta Sepultura</dt>
                    <dd class="grid grid-cols-2 gap-4 text-xs">
                        ${data.burial.map((b, i) => `
                            ${b.place ? `
                            <div class="p-3 bg-white/50 rounded">
                                <span class="block text-outline font-bold mb-1">Cementerio</span>
                                <span class="text-xs">${b.place}</span>
                            </div>
                            ` : ''}
                            ${b.place_detail ? `
                            <div class="p-3 bg-white/50 rounded">
                                <span class="block text-outline font-bold mb-1">Referencia</span>
                                <span class="text-xs">${b.place_detail}</span>
                            </div>
                            ` : ''}
                        `).join('')}
                    </dd>
                </div>
                ` : `
                <div class="pt-6 border-t border-outline-variant/30">
                    <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-4">Localización Exacta Sepultura</dt>
                    <dd class="text-xs text-on-surface-variant italic">Información no disponible en el registro actual</dd>
                </div>
                `}
            </div>
        </div>
        ` : ''}
    `;
    document.getElementById('perfil-section').innerHTML = html;
}

function recentDeathTag(p) {
    if (!p.death_year || p.is_alive) return '';
    if (p.death_year < 2021) return '';
    return `<div class="mt-1 text-[9px] uppercase tracking-widest font-extrabold bg-secondary text-on-secondary px-2 py-0.5 rounded">† RECIENTE</div>`;
}

function renderFamilyTree(data) {
    const person = data.person;
    const parents = [];
    const siblings = [];
    const children = [];

    if (data.father) parents.push(data.father);
    if (data.mother) parents.push(data.mother);

    if (data.siblings) siblings.push(...data.siblings);
    if (data.children) children.push(...data.children);

    // Helper functions
    function dossierId(id) { return id ? id.replace(/@/g, '') : ''; }
    function formatYears(birth_year, death_year) {
        // If birth_year AND death_year: "birth_year - death_year"
        if (birth_year && death_year) return `${birth_year} - ${death_year}`;
        // If birth_year but NO death_year: "birth_year" (no " - ?")
        if (birth_year) return birth_year;
        // If NO birth_year but death_year: "? - death_year"
        if (death_year) return `? - ${death_year}`;
        // If neither: "? - ?"
        return '? - ?';
    }

    let html = `
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic text-center">Árbol Familiar Inmediato</h2>
        <div class="flex flex-col items-center">
    `;

    // Parents
    if (parents.length > 0) {
        html += `<div class="flex gap-24 items-start mb-6 relative">`;
        parents.forEach(p => {
            html += `
                <a href="/dossier.html?id=${dossierId(p.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                            ${p.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${p.photo_file}" alt="${p.name}">` : '<span class="material-symbols-outlined">person</span>'}
                        </div>
                        <h4 class="text-[11px] font-bold text-center leading-tight">${p.name}</h4>
                        <span class="text-[10px] opacity-60">${formatYears(p.birth_year, p.death_year)}</span>
                        ${recentDeathTag(p)}
                    </div>
                </a>
            `;
        });
        html += `<div class="absolute left-1/2 -bottom-6 w-px h-6 bg-outline-variant -translate-x-1/2"></div></div>`;
    }

    // Siblings
    if (siblings.length > 0) {
        // If only one sibling, align to the left so the parent line doesn't appear to come from the sibling
        const siblingsAlign = siblings.length === 1 ? 'justify-start pl-[22%]' : 'justify-center';
        html += `
            <div class="flex ${siblingsAlign} gap-6 mb-12 max-w-5xl w-full px-4 border-t border-outline-variant pt-6 flex-wrap">
        `;
        siblings.forEach(s => {
            html += `
                <a href="/dossier.html?id=${dossierId(s.id)}" class="cursor-pointer hover:opacity-90 transition-opacity">
                    <div class="flex flex-col items-center node-card opacity-80 shrink-0">
                        <div class="w-12 h-12 rounded-full overflow-hidden border border-outline-variant/30 mb-1 bg-surface-container-high flex items-center justify-center">
                            ${s.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${s.photo_file}" alt="${s.name}">` : '<span class="material-symbols-outlined text-sm">person</span>'}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${s.name}</h4>
                        <span class="text-[10px] opacity-40">${formatYears(s.birth_year, s.death_year)}</span>
                        ${recentDeathTag(s)}
                    </div>
                </a>
            `;
        });
        html += `</div>`;
    }

    // Connector line from parents/siblings down to the main subject
    html += `<div class="w-px h-12 bg-outline-variant"></div>`;

    // Main subject - centered at 50% with spouse to the right.
    // Uses an invisible spacer (same size as spouse) on the LEFT so that
    // flex justify-center mathematically centers the main-node at 50%.
    html += `
        <div class="relative w-full flex justify-center items-center gap-16 my-6">
    `;

    if (data.spouse) {
        html += `
                <div class="flex flex-col items-center node-card invisible" aria-hidden="true">
                    <div class="w-20 h-20 mb-2"></div>
                    <h4 class="text-[11px]">.</h4>
                    <span class="text-[10px]">.</span>
                </div>
        `;
    }

    html += `
                <div class="flex flex-col items-center main-node p-4 bg-primary/5 rounded-xl heritage-border border-primary/30 shadow-inner">
                    <div class="w-24 h-24 rounded-full overflow-hidden border-4 border-primary mb-3 shadow-lg bg-surface-container-high flex items-center justify-center">
                        ${person.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${person.photo_file}" alt="${person.name}">` : '<span class="material-symbols-outlined text-2xl">person</span>'}
                    </div>
                    <h3 class="font-headline font-bold text-primary text-center text-sm">${person.name}</h3>
                    <span class="text-xs opacity-60 italic text-center">${formatYears(person.birth_year, person.death_year)}</span>
                    <div class="mt-2 text-[8px] uppercase tracking-widest font-extrabold bg-primary text-on-primary px-2 py-0.5 rounded">Sujeto Central</div>
                    ${recentDeathTag(person)}
                </div>
    `;

    if (data.spouse) {
        html += `
                <a href="/dossier.html?id=${dossierId(data.spouse.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-20 h-20 rounded-full overflow-hidden border-2 border-secondary/20 mb-2 bg-surface-container-high flex items-center justify-center">
                            ${data.spouse.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${data.spouse.photo_file}" alt="${data.spouse.name}">` : '<span class="material-symbols-outlined">person</span>'}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${data.spouse.name}</h4>
                        <span class="text-[10px] opacity-60 text-center">${formatYears(data.spouse.birth_year, data.spouse.death_year)}</span>
                        ${recentDeathTag(data.spouse)}
                    </div>
                </a>
        `;
    }

    html += `
        </div>
    `;

    // Children
    if (children.length > 0) {
        html += `<div class="tree-connector"></div>
        <div class="flex justify-center gap-16 border-t border-outline-variant pt-6 w-full flex-wrap">`;
        children.forEach(c => {
            const childYears = c.is_alive ? c.birth_year : formatYears(c.birth_year, c.death_year);
            html += `
                <a href="/dossier.html?id=${dossierId(c.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                            ${c.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${c.photo_file}" alt="${c.name}">` : '<span class="material-symbols-outlined">person</span>'}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${c.name}</h4>
                        <span class="text-[10px] opacity-50">${childYears}</span>
                        ${recentDeathTag(c)}
                    </div>
                </a>
            `;
        });
        html += `</div>`;
    }

    html += `
        <div class="mt-12 text-center">
            <a href="/tree.html?id=${dossierId(person.id)}" class="inline-flex items-center gap-2 px-6 py-3 bg-primary text-on-primary rounded-lg hover:opacity-90 transition-opacity font-bold text-sm">
                <span class="material-symbols-outlined text-lg">account_tree</span>
                Ver árbol completo
            </a>
        </div>
    </div>`;
    document.getElementById('family-tree-section').innerHTML = html;
}

function renderBentoGrid(photos) {
    const gridHtml = `
        <div class="bento-grid">
            ${photos.map((p, i) => {
                const classMap = ['bento-med', 'bento-small', 'bento-xsmall', 'bento-small', 'bento-med', 'bento-xsmall', 'bento-small', 'bento-med', 'bento-xsmall', 'bento-small', 'bento-xsmall', 'bento-med', 'bento-small', 'bento-xsmall', 'bento-med', 'bento-small', 'bento-small', 'bento-hero', 'bento-xsmall', 'bento-small'];
                const cls = classMap[i % classMap.length];
                const lineClamps = {
                    'bento-hero': 'line-clamp-4',
                    'bento-med': 'line-clamp-2',
                    'bento-small': 'line-clamp-1',
                    'bento-xsmall': 'line-clamp-1'
                };
                const lineClamp = lineClamps[cls] || 'line-clamp-2';
                return `
                    <div class="${cls} heritage-border bg-white overflow-hidden group relative">
                        <img src="/photos/${p.filename}" alt="${p.title || 'Foto'}" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" ${p.position ? `onload="applyFaceBox(this, '${p.position}')"` : ''}>
                        ${p.position ? `<div class="face-box absolute border-2 pointer-events-none hidden" style="border-color: #2D4B33;"></div>` : ''}
                        ${p.title ? `
                            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                <p class="text-white text-[14px] font-bold ${lineClamp}">${p.title}</p>
                                ${p.date ? `<span class="text-white/60 text-[13px]">${p.date}</span>` : ''}
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('')}
        </div>
    `;
    document.getElementById('photos-grid-container').innerHTML = gridHtml;
}

function renderUniformGrid(photos) {
    const gridHtml = `
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            ${photos.map((p) => {
                return `
                    <div class="heritage-border bg-white overflow-hidden group relative aspect-square">
                        <img src="/photos/${p.filename}" alt="${p.title || 'Foto'}" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105" ${p.position ? `onload="applyFaceBox(this, '${p.position}')"` : ''}>
                        ${p.position ? `<div class="face-box absolute border-2 pointer-events-none hidden" style="border-color: #2D4B33;"></div>` : ''}
                        ${p.title ? `
                            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <p class="text-white text-[12px] font-bold line-clamp-2">${p.title}</p>
                                ${p.date ? `<span class="text-white/60 text-[11px]">${p.date}</span>` : ''}
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('')}
        </div>
    `;
    document.getElementById('photos-grid-container').innerHTML = gridHtml;
}

function renderPhotosGrid(photos) {
    if (!photos || photos.length === 0) {
        document.getElementById('photos-section').style.display = 'none';
        return;
    }

    document.getElementById('photos-section').style.display = 'block';

    // Function to apply face box overlay when image loads
    window.applyFaceBox = function(img, pos) {
        if (!pos) return;
        const box = img.nextElementSibling;
        if (!box || box.className.indexOf('face-box') === -1) return;
        const container = img.parentElement;
        const [x1, y1, x2, y2] = pos.split(' ').map(Number);
        const cW = container.offsetWidth, cH = container.offsetHeight;
        const iW = img.naturalWidth, iH = img.naturalHeight;
        const scale = Math.max(cW / iW, cH / iH);
        const offX = (cW - iW * scale) / 2;
        const offY = (cH - iH * scale) / 2;
        box.style.left = (offX + x1 * scale) + 'px';
        box.style.top = (offY + y1 * scale) + 'px';
        box.style.width = ((x2 - x1) * scale) + 'px';
        box.style.height = ((y2 - y1) * scale) + 'px';
        box.classList.remove('hidden');
    };

    _photosOriginal = photos;
    _sortActive = null;

    const html = `
        <div class="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-outline-variant pb-6 gap-6">
            <div class="space-y-2">
                <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                    <span class="material-symbols-outlined">collections</span>
                    Memoria Visual
                </h2>
                <p class="text-xs text-outline font-bold uppercase tracking-widest">Archivo Histórico (${photos.length} medios registrados)</p>
            </div>
            <div class="flex gap-2 flex-wrap">
                <button onclick="sortPhotos('oldest')" id="sort-oldest" class="sort-btn px-3 py-1 text-[11px] font-bold uppercase border border-primary text-primary rounded-full hover:bg-primary/10 transition-colors">Más antigua</button>
                <button onclick="sortPhotos('newest')" id="sort-newest" class="sort-btn px-3 py-1 text-[11px] font-bold uppercase border border-primary text-primary rounded-full hover:bg-primary/10 transition-colors">Más nueva</button>
                <button onclick="sortPhotos('added')" id="sort-added" class="sort-btn px-3 py-1 text-[11px] font-bold uppercase border border-primary text-primary rounded-full hover:bg-primary/10 transition-colors">Fecha incorporación</button>
            </div>
        </div>
        <div id="photos-grid-container"></div>
    `;

    document.getElementById('photos-section').innerHTML = html;
    renderBentoGrid(photos);
}

function renderDocuments(data) {
    if (!data.person.photo_file) {
        document.getElementById('docs-section').style.display = 'none';
        return;
    }

    document.getElementById('docs-section').style.display = 'block';
    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <span class="material-symbols-outlined">folder_open</span>
            Repositorio Documental
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div class="p-4 bg-white heritage-border rounded-lg flex items-center gap-4 hover:shadow-md transition-shadow cursor-pointer group">
                <div class="w-12 h-12 bg-red-50 text-red-700 rounded-lg flex items-center justify-center shrink-0">
                    <span class="material-symbols-outlined">picture_as_pdf</span>
                </div>
                <div>
                    <h4 class="text-sm font-bold group-hover:text-primary transition-colors">Documentos Vitales</h4>
                    <p class="text-[10px] text-outline uppercase tracking-tight">Registros disponibles</p>
                </div>
            </div>
        </div>
    `;
    document.getElementById('docs-section').innerHTML = html;
}

function renderTimeline(data) {
    const person = data.person;
    const events = [];

    // Extract baptism names from notes
    let baptismNames = '';
    if (data.notes && data.notes.length > 0) {
        const notesText = data.notes.join(' ');
        const namesMatch = notesText.match(/amb els noms[s]? d[\'e]([^.]+)/);
        if (namesMatch) {
            baptismNames = namesMatch[1].trim();
        }
    }

    function extractYear(dateStr) {
        if (!dateStr) return null;
        const str = String(dateStr);
        const match = str.match(/\d{4}/);
        return match ? parseInt(match[0]) : null;
    }

    function formatDateWithQualifier(dateStr) {
        if (!dateStr) return '';
        const str = String(dateStr);
        // Handle GEDCOM date qualifiers
        if (str.startsWith('ABT ')) return 'Aprox. ' + str.substring(4);
        if (str.startsWith('AFT ')) return 'Después de ' + str.substring(4);
        if (str.startsWith('BEF ')) return 'Antes de ' + str.substring(4);
        if (str.startsWith('FROM ') && str.includes(' TO ')) {
            const parts = str.split(' TO ');
            return 'Desde ' + parts[0].substring(5) + ' hasta ' + parts[1];
        }
        if (str.startsWith('BET ') && str.includes(' AND ')) {
            const parts = str.split(' AND ');
            return 'Entre ' + parts[0].substring(4) + ' y ' + parts[1];
        }
        return str;
    }

    function calculateAge(year) {
        if (!year || !person.birth_year) return null;
        return year - person.birth_year;
    }

    function ageText(year, hideIfZero = false) {
        const age = calculateAge(year);
        if (age === 0 && hideIfZero) return '';
        return age !== null ? `Edad ${age}` : '';
    }

    function ageRangeText(startYear, endYear) {
        if (!startYear || !endYear) return '';
        const ageStart = calculateAge(startYear);
        const ageEnd = calculateAge(endYear);
        if (ageStart === null || ageEnd === null) return '';
        return `Edades: ${ageStart} -`;  // Will be displayed inline with endYear on same line
    }

    function ageRangeEndText(endYear) {
        if (!endYear) return '';
        const ageEnd = calculateAge(endYear);
        if (ageEnd === null) return '';
        return `${ageEnd}`;
    }

    function formatDateRange(dateStr) {
        if (!dateStr) return '';
        // Check if it's a range like "19 de agosto 1917 - 1919"
        if (dateStr.includes(' - ')) {
            const [start, end] = dateStr.split(' - ').map(s => s.trim());
            return `desde ${start} hasta ${end}`;
        }
        return dateStr;
    }

    // Nacimiento
    if (person.birth_year) {
        const lines = [
            formatDateWithQualifier(person.birth_date) || `${person.birth_year}`,
            person.birth_place || ''
        ].filter(Boolean);

        // Add baptism names if available
        if (baptismNames) {
            lines.push(baptismNames);
        }

        events.push({
            year: person.birth_year,
            age: ageText(person.birth_year, true),
            type: 'Nacimiento',
            lines: lines,
            photo: null,
            name: person.name
        });
    }

    // Bautismo
    if (data.baptism_date) {
        const year = extractYear(data.baptism_date);
        if (year) {
            events.push({
                year: year,
                age: ageText(year),
                type: 'Bautismo',
                lines: [
                    formatDateWithQualifier(data.baptism_date) || '',
                    data.baptism_place || ''
                ].filter(Boolean),
                photo: null,
                name: person.name
            });
        }
    }

    // Matrimonios (use spouses array, with fallback to single spouse)
    const spousesList = (data.spouses && data.spouses.length > 0) ? data.spouses : (data.spouse ? [data.spouse] : []);
    if (spousesList && spousesList.length > 0) {
        spousesList.forEach(s => {
            const year = extractYear(s.marriage_date);
            if (year) {
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Matrimonio con:',
                    lines: [
                        s.name || '',
                        s.marriage_date ? formatDateWithQualifier(s.marriage_date) : '',
                        s.marriage_place ? `${s.marriage_place}` : ''
                    ].filter(Boolean),
                    photo: s.photo_file,
                    name: s.name
                });
            }
        });
    }

    // Hijos (with gender-specific text)
    if (data.children) {
        data.children.forEach(c => {
            const year = extractYear(c.birth_year);
            if (year) {
                const typeText = c.sex === 'F' ? 'Nacimiento de la hija:' : 'Nacimiento del hijo:';
                events.push({
                    year: year,
                    age: ageText(year),
                    type: typeText,
                    lines: [
                        c.name || '',
                        formatDateWithQualifier(c.birth_date) || `${c.birth_year}`,
                        c.birth_place || ''
                    ].filter(Boolean),
                    photo: c.photo_file,
                    name: c.name
                });
            }

            // Children's marriages
            if (c.marriages && c.marriages.length > 0) {
                c.marriages.forEach(m => {
                    const mYear = extractYear(m.marriage_date);
                    if (mYear) {
                        const lines = [
                            m.marriage_date ? formatDateWithQualifier(m.marriage_date) : 'Approx. ' + mYear,
                            m.marriage_place ? `${m.marriage_place}` : ''
                        ].filter(Boolean);

                        events.push({
                            year: mYear,
                            age: ageText(mYear),
                            type: `Matrimonio de ${c.sex === 'F' ? 'la hija' : 'el hijo'}:`,
                            lines: lines,
                            photo: m.spouse_photo,
                            name: m.spouse_name,
                            childPhoto: c.photo_file,
                            childName: c.name,
                            isChildMarriage: true
                        });
                    }
                });
            }
        });
    }

    // Ocupaciones (with date range support)
    if (data.occupations) {
        data.occupations.forEach(o => {
            const year = extractYear(o.date);
            if (year) {
                let ageDisplay = '';
                // Check if date contains a range like "1893 - 1923"
                if (o.date && o.date.includes(' - ')) {
                    const parts = o.date.split(' - ');
                    const endYear = extractYear(parts[1]);
                    if (endYear && endYear > year) {
                        const ageStart = calculateAge(year);
                        const ageEnd = calculateAge(endYear);
                        if (ageStart !== null && ageEnd !== null) {
                            ageDisplay = `Edades: ${ageStart} - ${ageEnd}`;
                        }
                    }
                }

                events.push({
                    year: year,
                    age: ageDisplay || ageText(year),
                    type: 'Ocupación',
                    lines: [
                        o.title || '',
                        formatDateRange(o.date) || '',
                        o.place || ''
                    ].filter(Boolean),
                    photo: null,
                    name: person.name
                });
            }
        });
    }

    // Residencias (with date range support)
    if (data.residences) {
        data.residences.forEach(r => {
            const year = extractYear(r.date);
            if (year) {
                let ageDisplay = '';
                // Check if date contains a range
                if (r.date && r.date.includes(' - ')) {
                    const parts = r.date.split(' - ');
                    const endYear = extractYear(parts[1]);
                    if (endYear) {
                        const ageStart = calculateAge(year);
                        const ageEnd = calculateAge(endYear);
                        if (ageStart !== null && ageEnd !== null) {
                            ageDisplay = `Edades: ${ageStart} - ${ageEnd}`;
                        }
                    }
                }
                events.push({
                    year: year,
                    age: ageDisplay || ageText(year),
                    type: 'Residencia',
                    lines: [
                        formatDateRange(r.date) || '',
                        r.address || '',
                        [r.city, r.country].filter(Boolean).join(', ') || ''
                    ].filter(Boolean),
                    photo: null,
                    name: person.name
                });
            }
        });
    }

    // Alistamiento militar
    if (data.military) {
        data.military.forEach(m => {
            const year = extractYear(m.date);
            if (year) {
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Alistamiento Militar',
                    lines: [
                        m.description || '',
                        m.date || '',
                        m.place || ''
                    ].filter(Boolean),
                    photo: null,
                    name: person.name
                });
            }
        });
    }

    // Defunción
    if (person.death_year) {
        events.push({
            year: person.death_year,
            age: ageText(person.death_year),
            type: 'Defunción',
            lines: [
                formatDateWithQualifier(person.death_date) || `${person.death_year}`,
                person.death_place || ''
            ].filter(Boolean),
            photo: null,
            name: person.name
        });
    }

    // Entierro (after death)
    if (data.burial && data.burial.length > 0) {
        data.burial.forEach(b => {
            const year = extractYear(b.date);
            if (year) {
                const lines = [formatDateWithQualifier(b.date) || ''];
                if (b.place) lines.push(b.place);
                if (b.place_detail) {
                    // place_detail might contain cemetery info and location details
                    const details = b.place_detail.split('\n').filter(d => d.trim());
                    lines.push(...details);
                }
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Entierro',
                    lines: lines.filter(Boolean),
                    photo: null,
                    name: person.name
                });
            }
        });
    }

    if (events.length === 0) {
        document.getElementById('timeline-section').style.display = 'none';
        return;
    }

    // Sort by year
    events.sort((a, b) => a.year - b.year);

    document.getElementById('timeline-section').style.display = 'block';

    const timelineHtml = events.map((e, idx) => {
        let photosHtml = '';
        if (e.isChildMarriage) {
            // Show two photos side by side for child's marriage
            photosHtml = `
                <div class="flex items-center gap-2 mb-3">
                    ${e.childPhoto ? `<img class="w-8 h-8 rounded-full object-cover border border-outline-variant/30" src="/photos/${e.childPhoto}" alt="${e.childName}">` : ''}
                    <span class="text-sm font-bold">${e.childName}</span>
                    <span class="text-xs text-outline mx-1">y</span>
                    ${e.photo ? `<img class="w-8 h-8 rounded-full object-cover border border-outline-variant/30" src="/photos/${e.photo}" alt="${e.name}">` : ''}
                    <span class="text-sm font-bold">${e.name}</span>
                </div>
            `;
        } else if (e.photo) {
            photosHtml = `<div class="flex items-center gap-3 mb-2"><img class="w-8 h-8 rounded-full object-cover border border-outline-variant/30" src="/photos/${e.photo}" alt="${e.name}"><span class="text-sm font-bold">${e.name}</span></div>`;
        }

        return `
        <div class="flex gap-8 mb-12 relative">
            <div class="w-20 text-right flex-shrink-0">
                <div class="text-2xl font-bold text-primary">${e.year}</div>
                ${e.age ? `<div class="text-xs text-outline mt-1 whitespace-nowrap">${e.age}</div>` : ''}
            </div>
            <div class="flex-grow pb-8 border-l-2 border-outline-variant pl-8 relative">
                <div class="absolute -left-[9px] top-2 w-4 h-4 rounded-full bg-primary"></div>
                <div class="font-bold text-sm mb-3">${e.type}</div>
                <div class="space-y-1">
                    ${photosHtml}
                    ${e.lines.map(line => `<div class="text-sm text-outline">${line}</div>`).join('')}
                </div>
            </div>
        </div>
    `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4 mb-8">
            <span class="material-symbols-outlined">event_note</span>
            Cronograma Biográfico
        </h2>
        <div class="space-y-2">
            ${timelineHtml}
        </div>
    `;
    document.getElementById('timeline-section').innerHTML = html;
}

function renderCareer(occupations) {
    if (!occupations || occupations.length === 0) {
        document.getElementById('career-section').style.display = 'none';
        return;
    }

    document.getElementById('career-section').style.display = 'block';

    const cards = occupations.map((o, i) => `
        <div class="p-6 bg-white heritage-border rounded-xl shadow-sm border-l-4 border-${i % 2 === 0 ? 'primary' : 'secondary'}">
            <h4 class="font-bold text-${i % 2 === 0 ? 'primary' : 'secondary'} text-sm uppercase">${o.title}</h4>
            <p class="text-[10px] text-outline mt-1">${o.date || 'Período desconocido'}</p>
            ${o.place ? `<p class="text-xs font-bold mt-3">${o.place}</p>` : ''}
        </div>
    `).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <span class="material-symbols-outlined">business_center</span>
            Trayectoria Profesional
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">${cards}</div>
    `;
    document.getElementById('career-section').innerHTML = html;
}

function renderMilitary(data) {
    if (!data.military || data.military.length === 0) {
        document.getElementById('military-section').style.display = 'none';
        return;
    }

    document.getElementById('military-section').style.display = 'block';

    const events = data.military.map(m => `
        <div class="border-b border-outline-variant/30 pb-4 last:border-0 last:pb-0">
            ${m.description ? `<p class="font-bold text-sm mb-2">${m.description}</p>` : ''}
            ${m.date ? `<span class="text-xs text-outline">${m.date}</span>` : ''}
            ${m.place ? `<p class="text-sm mt-2 italic text-on-surface/80">${m.place}</p>` : ''}
        </div>
    `).join('');

    const html = `
        <h3 class="font-headline text-2xl text-primary flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined">military_tech</span>
            Actividad Militar
        </h3>
        <div class="p-8 bg-surface-container-high rounded-xl border-l-8 border-primary relative overflow-hidden">
            <div class="absolute -right-8 -bottom-8 opacity-5">
                <span class="material-symbols-outlined text-9xl">swords</span>
            </div>
            <div class="space-y-4">
                ${events}
            </div>
        </div>
    `;
    document.getElementById('military-section').innerHTML = html;
}

function renderNotes(notes) {
    if (!notes || notes.length === 0) {
        document.getElementById('notes-section').style.display = 'none';
        return;
    }

    document.getElementById('notes-section').style.display = 'block';

    const articles = notes.map((n, i) => {
        const clean = n.replace(/<[^>]+>/g, '').replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();
        return `
            <article class="relative p-10 bg-white heritage-border shadow-inner rounded-sm font-headline">
                <div class="absolute top-0 right-0 p-4 text-[10px] font-bold text-outline">SIGNATURA: NOTA_${i+1}</div>
                <div class="space-y-6 text-lg italic leading-relaxed opacity-90">
                    <p>${clean}</p>
                </div>
            </article>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic">Notas Biográficas</h2>
        <div class="space-y-12">${articles}</div>
    `;
    document.getElementById('notes-section').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadDossier);
