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

function renderDossier(data) {
    const person = data.person;
    document.title = `${person.name} | Familia Godes`;

    // 1. HEADER
    if (person.photo_file && person.photo_file.trim()) {
        document.querySelector('#hero-photo img').src = `/photos/${person.photo_file}`;
    }
    document.getElementById('hero-name').textContent = person.name;

    const birthYear = person.birth_year || '?';
    const deathYear = person.death_year || '?';
    const birthPlace = person.birth_place || 'Barcelona, España';
    document.getElementById('vital-dates').innerHTML = `
        <span>${person.birth_date || birthYear} — ${person.death_date || deathYear}</span>
        <span class="text-lg opacity-70">${birthPlace}</span>
    `;

    document.getElementById('stats-boxes').innerHTML = `
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">Inventario</span>
            <span class="font-bold">${person.photo_count || 0} Medios</span>
        </div>
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">Última Act.</span>
            <span class="font-bold">Hoy</span>
        </div>
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

    // Extract baptism data from notes
    let baptismNames = '';
    let baptismDate = '';
    let baptismPlace = '';

    if (data.notes && data.notes.length > 0) {
        const notesText = data.notes.join(' ');

        // Extract baptism names: "amb els noms d'Artur, Carles i Mariano"
        const namesMatch = notesText.match(/amb els noms[s]? d[\'e]([^.]+)/);
        if (namesMatch) {
            baptismNames = namesMatch[1].trim();
        }

        // Extract baptism date
        const dateMatch = notesText.match(/Batejat[^,]* (\d{1,2} de \w+ de \d{4})/);
        if (dateMatch) {
            baptismDate = dateMatch[1];
        }

        // Extract baptism place (Bonanova, etc)
        if (notesText.includes('Bonanova')) {
            baptismPlace = 'Iglesia de la Bonanova';
        }
    }

    const html = `
        <div class="space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">fingerprint</span>
                Perfil de Registro
            </h2>
            <div class="bg-surface-container-low p-8 rounded-xl heritage-border space-y-6">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">Nombre Completo</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.name}</span>
                            ${baptismNames ? `<span class="italic opacity-80 text-xs mt-1">Nombres de bautismo: ${baptismNames}</span>` : ''}
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
                        </dd>
                    </div>
                </div>
            </div>
        </div>
        <div class="space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">account_balance</span>
                Defunción y Sepelio
            </h2>
            <div class="bg-surface-container-highest/30 p-8 rounded-xl heritage-border space-y-6">
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
                            <span class="font-bold block">${person.death_cause || 'Natural'}</span>
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
    `;
    document.getElementById('perfil-section').innerHTML = html;
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

    let html = `
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic text-center">Árbol Familiar Inmediato</h2>
        <div class="flex flex-col items-center">
    `;

    // Parents
    if (parents.length > 0) {
        html += `<div class="flex gap-24 items-end mb-6 relative">`;
        parents.forEach(p => {
            html += `
                <div class="flex flex-col items-center node-card">
                    <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                        ${p.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${p.photo_file}" alt="${p.name}">` : '<span class="material-symbols-outlined">person</span>'}
                    </div>
                    <h4 class="text-[10px] font-bold text-center leading-tight">${p.name}</h4>
                    <span class="text-[9px] opacity-60">${p.birth_year || '?'} - ${p.death_year || '?'}</span>
                </div>
            `;
        });
        html += `<div class="absolute left-1/2 -bottom-6 w-px h-6 bg-outline-variant -translate-x-1/2"></div></div>`;
    }

    // Siblings
    if (siblings.length > 0) {
        html += `
            <div class="flex justify-center gap-6 mb-12 max-w-5xl w-full px-4 border-t border-outline-variant pt-6 flex-wrap">
        `;
        siblings.forEach(s => {
            html += `
                <div class="flex flex-col items-center node-card opacity-80 shrink-0">
                    <div class="w-12 h-12 rounded-full overflow-hidden border border-outline-variant/30 mb-1 bg-surface-container-high flex items-center justify-center">
                        ${s.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${s.photo_file}" alt="${s.name}">` : '<span class="material-symbols-outlined text-sm">person</span>'}
                    </div>
                    <div class="flex items-center gap-1">
                        <h4 class="text-[9px] font-bold text-center">${s.name}</h4>
                        <span class="material-symbols-outlined text-[10px]">${s.sex === 'M' ? 'male' : 'female'}</span>
                    </div>
                    <span class="text-[8px] opacity-40">${s.birth_year || '?'} - ${s.death_year || '?'}</span>
                </div>
            `;
        });
        html += `</div>`;
    }

    // Main subject
    html += `
        <div class="flex items-center justify-center gap-16 mb-8 relative w-full">
            <div class="flex flex-col items-center main-node p-4 bg-primary/5 rounded-xl heritage-border border-primary/30 shadow-inner z-10">
                <div class="w-24 h-24 rounded-full overflow-hidden border-4 border-primary mb-3 shadow-lg bg-surface-container-high flex items-center justify-center">
                    ${person.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${person.photo_file}" alt="${person.name}">` : '<span class="material-symbols-outlined text-2xl">person</span>'}
                </div>
                <h3 class="font-headline font-bold text-primary text-center text-sm">${person.name}</h3>
                <span class="text-xs opacity-60 italic text-center">${person.birth_year || '?'} - ${person.death_year || '?'}</span>
                <div class="mt-2 text-[8px] uppercase tracking-widest font-extrabold bg-primary text-on-primary px-2 py-0.5 rounded">Sujeto Central</div>
            </div>
    `;

    // Spouse
    if (data.spouse) {
        html += `
            <div class="flex flex-col items-center node-card">
                <div class="w-20 h-20 rounded-full overflow-hidden border-2 border-secondary/20 mb-2 bg-surface-container-high flex items-center justify-center">
                    ${data.spouse.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${data.spouse.photo_file}" alt="${data.spouse.name}">` : '<span class="material-symbols-outlined">person</span>'}
                </div>
                <h4 class="text-[10px] font-bold text-center">${data.spouse.name}</h4>
                <span class="text-[9px] opacity-60 text-center">${data.spouse.birth_year || '?'} - ${data.spouse.death_year || '?'}</span>
            </div>
        `;
    }

    html += `<div class="absolute left-1/2 -top-12 w-px h-12 bg-outline-variant -translate-x-1/2"></div></div>`;

    // Children
    if (children.length > 0) {
        html += `<div class="tree-connector"></div>
        <div class="flex justify-center gap-16 border-t border-outline-variant pt-6 w-full flex-wrap">`;
        children.forEach(c => {
            html += `
                <div class="flex flex-col items-center node-card">
                    <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                        ${c.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${c.photo_file}" alt="${c.name}">` : '<span class="material-symbols-outlined">person</span>'}
                    </div>
                    <div class="flex items-center gap-1">
                        <h4 class="text-[10px] font-bold text-center">${c.name}</h4>
                        <span class="material-symbols-outlined text-[10px]">${c.sex === 'M' ? 'male' : 'female'}</span>
                    </div>
                    <span class="text-[9px] opacity-50">${c.birth_year || '?'}</span>
                </div>
            `;
        });
        html += `</div>`;
    }

    html += `</div>`;
    document.getElementById('family-tree-section').innerHTML = html;
}

function renderPhotosGrid(photos) {
    if (!photos || photos.length === 0) {
        document.getElementById('photos-section').style.display = 'none';
        return;
    }

    document.getElementById('photos-section').style.display = 'block';

    const html = `
        <div class="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-outline-variant pb-6 gap-6">
            <div class="space-y-2">
                <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                    <span class="material-symbols-outlined">collections</span>
                    Memoria Visual
                </h2>
                <p class="text-xs text-outline font-bold uppercase tracking-widest">Archivo Histórico (${photos.length} medios registrados)</p>
            </div>
        </div>
        <div class="bento-grid">
            ${photos.slice(0, 9).map((p, i) => {
                const classMap = ['bento-hero', 'bento-med', 'bento-small', 'bento-xsmall', 'bento-xsmall', 'bento-med', 'bento-med'];
                const cls = classMap[i] || 'bento-small';
                return `
                    <div class="${cls} heritage-border bg-white overflow-hidden group relative">
                        <img src="/photos/${p.filename}" alt="${p.title || 'Foto'}" class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105">
                        ${p.title ? `
                            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                <p class="text-white text-[10px] font-bold">${p.title}</p>
                                ${p.date ? `<span class="text-white/60 text-[9px]">${p.date}</span>` : ''}
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join('')}
        </div>
    `;

    document.getElementById('photos-section').innerHTML = html;
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
    const events = [];

    if (data.person.birth_year) {
        events.push({ date: data.person.birth_year, type: 'Naixement', detail: data.person.birth_place || '' });
    }

    if (data.residences) {
        data.residences.forEach(r => {
            events.push({ date: r.date || '', type: 'Residència', detail: r.address || '' });
        });
    }

    if (data.occupations) {
        data.occupations.forEach(o => {
            events.push({ date: o.date || '', type: 'Treball', detail: o.title || '' });
        });
    }

    if (data.person.death_year) {
        events.push({ date: data.person.death_year, type: 'Defunció', detail: data.person.death_place || '' });
    }

    if (events.length === 0) {
        document.getElementById('timeline-section').style.display = 'none';
        return;
    }

    document.getElementById('timeline-section').style.display = 'block';

    const rows = events.map(e => `
        <tr>
            <td class="px-6 py-4 font-bold text-primary">${e.date}</td>
            <td class="px-6 py-4 italic text-xs">${e.type}</td>
            <td class="px-6 py-4">${e.detail}</td>
        </tr>
    `).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <span class="material-symbols-outlined">event_note</span>
            Cronograma Biográfico
        </h2>
        <div class="overflow-x-auto shadow-sm heritage-border rounded-xl">
            <table class="w-full text-left border-collapse bg-white">
                <thead class="bg-surface-container-high text-on-surface uppercase text-[10px] tracking-widest font-bold">
                    <tr>
                        <th class="px-6 py-4 border-b border-outline-variant/30">Fecha</th>
                        <th class="px-6 py-4 border-b border-outline-variant/30">Tipo</th>
                        <th class="px-6 py-4 border-b border-outline-variant/30">Detalles</th>
                    </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant/20 text-sm">${rows}</tbody>
            </table>
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
    if (!data.person.death_note && !data.notes) {
        document.getElementById('military-section').style.display = 'none';
        return;
    }

    document.getElementById('military-section').style.display = 'block';

    const html = `
        <h3 class="font-headline text-2xl text-primary flex items-center gap-3 mb-6">
            <span class="material-symbols-outlined">military_tech</span>
            Actividad Militar
        </h3>
        <div class="p-8 bg-surface-container-high rounded-xl border-l-8 border-primary relative overflow-hidden">
            <div class="absolute -right-8 -bottom-8 opacity-5">
                <span class="material-symbols-outlined text-9xl">swords</span>
            </div>
            <div class="flex justify-between items-start mb-4">
                <span class="font-bold uppercase tracking-widest text-xs">Expediente Militar</span>
            </div>
            <p class="text-sm leading-relaxed italic text-on-surface/80">Sin información registrada</p>
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
