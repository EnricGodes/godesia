function personSvg(sex, birth_year, death_year, px) {
    px = px || 24;
    const cy = new Date().getFullYear();
    const isKid = (birth_year && death_year && (death_year - birth_year) < 15)
        || (birth_year && birth_year >= cy - 15);
    let d;
    if (isKid) {
        if (sex === 'M')      d = 'M14.25 16.25L17.673 17.2794C18.9522 17.6708 19.9025 18.6969 20.218 19.9464C20.3428 20.4409 19.9163 20.8601 19.4042 20.8601H4.59584C4.08366 20.8601 3.65717 20.4409 3.78198 19.944C4.09753 18.6969 5.04776 17.6708 6.32701 17.2794L9.75 16.25V14.4039C8.19866 13.1157 7.05 11.5755 7.05 8.32592C7.05 5.07156 8.82684 3.39994 11.588 3.39994C13.543 3.39994 14.3564 4.29994 14.3564 4.29994C16.6636 4.29994 17.05 6.20012 17.05 8.32592C17.05 11.5755 15.9013 13.1157 14.35 14.4039V16.25Z';
        else if (sex === 'F') d = 'M14.15 16.25L17.55 17.2734C18.8248 17.6623 19.7721 18.6816 20.0867 19.9221C20.2111 20.413 19.7859 20.8299 19.2754 20.8299H4.72458C4.21409 20.8299 3.78889 20.413 3.91334 19.9221C4.22789 18.6816 5.17518 17.6623 6.45 17.2734L9.85 16.25V14.2187C8.67634 14.0716 7.59559 13.8118 6.65 13.4669C7.05 12.605 7.45 11.3391 7.45 8.43866C7.45 3.6536 11.85 3.6537 13.05 5.24827C15.45 4.84984 15.45 6.84588 15.45 9.33267C15.45 11.3409 16.0056 12.9574 16.2833 13.4669C15.3377 13.8118 14.2569 14.076 13.0833 14.2187V16.25Z';
        else                  d = 'M14.15 16.25L17.55 17.2734C18.8248 17.6623 19.7721 18.6816 20.0867 19.9221C20.2111 20.413 19.7859 20.8299 19.2754 20.8299H4.72458C4.21409 20.8299 3.78889 20.413 3.91334 19.9221C4.22789 18.6816 5.17518 17.6623 6.45 17.2734L9.85 16.25V14.2187C8.67634 14.0716 7.59559 13.8118 6.65 13.4669C7.05 12.605 7.45 11.3391 7.45 8.43866C7.45 3.65376 11.85 3.67 13.05 5.24827C15.45 4.84984 15.45 6.84588 15.45 9.33267C15.45 11.3409 16.0056 12.9574 16.2833 13.4669C15.3377 13.8118 14.2569 14.0716 13.0833 14.2187V16.25Z';
    } else {
        if (sex === 'M')      d = 'M14.5 16.5001L18.216 17.6178C19.6034 18.0424 20.6341 19.1553 20.9763 20.51C21.1115 21.0457 20.6489 21.5001 20.0936 21.5001H3.90639C3.35107 21.5001 2.88845 21.0457 3.02375 20.51C3.36593 19.1553 4.39659 18.0424 5.78401 17.6178L9.5 16.5001V14.5623C7.71916 13.1685 6.5 11.4999 6.5 7.91674C6.5 4.32689 8.45474 2.49993 11.4923 2.49993C13.6433 2.49993 14.5385 3.49993 14.5385 3.49993C17.0769 3.49993 17.5 5.59712 17.5 7.91674C17.5 11.4999 16.2808 13.1685 14.5 14.5623V16.5001Z';
        else if (sex === 'F') d = 'M14.5 16.5L18.216 17.6177C19.6034 18.0423 20.6341 19.1553 20.9763 20.5099C21.1115 21.0456 20.6489 21.5 20.0936 21.5H3.90639C3.35107 21.5 2.88845 21.0456 3.02375 20.5099C3.36593 19.1553 4.39659 18.0423 5.78401 17.6177L9.5 16.5V14.345C8.21522 14.1822 7.03039 13.897 6 13.5161C6.5 12.5322 7 11.0563 7 7.61264C7 1.70919 12.5 1.70912 14 3.67672C17 3.18499 17 5.64483 17 8.59655C17 10.9579 17.6667 12.8602 18 13.5161C16.9696 13.897 15.7848 14.1822 14.5 14.345V16.5Z';
        else                  d = 'M14.5 16.5001L18.216 17.6178C19.6034 18.0424 20.6341 19.1553 20.9763 20.51C21.1115 21.0457 20.6489 21.5001 20.0936 21.5001H3.90639C3.35107 21.5001 2.88845 21.0457 3.02375 20.51C3.36593 19.1553 4.39659 18.0424 5.78401 17.6178L9.5 16.5001V14.48C7.93012 13.2221 6.7 11.6426 6.7 7.95842C6.7 4.48276 8.71563 2.49993 11.7 2.49993C13.3812 2.49993 14.2558 3.09736 14.6923 3.49993C16.9538 3.49993 17.3 5.58519 17.3 7.95842C17.3 11.6426 16.0699 13.2221 14.5 14.48V16.5001Z';
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${px}" height="${px}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" style="opacity:0.45"><path d="${d}"/></svg>`;
}

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

        const ctaUrl = `/colaborar.html?person=${personId}&source=dossier`;
        ['cta-top', 'cta-bottom'].forEach(id => {
            const btn = document.getElementById(id);
            if (btn) btn.onclick = () => { window.location.href = ctaUrl; };
        });
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

/**
 * Format person name with nickname if available
 * Example: "Josep Maria Godes Hurtado" + nickname "Bep" -> 'Josep Maria "Bep" Godes Hurtado'
 */
function formatNameWithNickname(name, nickname, given_name, surname) {
    if (!nickname) return name;
    // If we have given_name and surname, use them
    if (given_name && surname) {
        return `${given_name} "${nickname}" ${surname}`;
    }
    // Fallback to splitting name
    const parts = name.trim().split(' ');
    if (parts.length < 2) return name;
    const surnameFromName = parts.pop();
    const givenNames = parts.join(' ');
    return `${givenNames} "${nickname}" ${surnameFromName}`;
}

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
            btn.classList.add('bg-primary', 'text-white');
            btn.classList.remove('border', 'border-outline-variant', 'text-outline-variant', 'hover:bg-outline-variant/10');
        } else {
            btn.classList.remove('bg-primary', 'text-white');
            btn.classList.add('border', 'border-outline-variant', 'text-outline-variant', 'hover:bg-outline-variant/10');
        }
    });
}

function renderDossier(data) {
    const person = data.person;
    const nickname = data.nickname;
    const displayName = formatNameWithNickname(person.name, nickname, person.given_name, person.surname);

    document.title = `${displayName} | Familia Godes`;

    // 1. HEADER
    if (person.photo_file && person.photo_file.trim()) {
        document.querySelector('#hero-photo img').src = `/photos/${person.photo_file}`;
    } else {
        const currentYear = new Date().getFullYear();
        const isChild = (person.birth_year && person.death_year && (person.death_year - person.birth_year) < 15)
            || (person.birth_year && person.birth_year >= currentYear - 15);
        let fallbackImg;
        if (isChild) {
            fallbackImg = person.sex === 'M' ? '/img/nino.jpg' : person.sex === 'F' ? '/img/nina.jpg' : '/img/nino_neutro.jpg';
        } else {
            fallbackImg = person.sex === 'M' ? '/img/hombre.jpg' : person.sex === 'F' ? '/img/mujer.jpg' : '/img/neutro.jpg';
        }
        document.querySelector('#hero-photo img').src = fallbackImg;
    }
    document.getElementById('hero-name').textContent = displayName;

    const birthYear = person.birth_year || '?';
    const birthPlace = person.birth_place || 'Barcelona, España';
    const vitalDatesEl = document.getElementById('vital-dates');
    vitalDatesEl.classList.remove('flex-wrap', 'items-center', 'gap-6');
    vitalDatesEl.classList.add('flex-col', 'gap-2');

    // Show death date, year, or '?' for deceased without date
    let deathDisplay = '';
    if (person.death_date || person.death_year) {
        const deathYear = person.death_year || '?';
        deathDisplay = ` — ${person.death_date || deathYear}`;
    } else if (!person.is_alive) {
        deathDisplay = ' — ?';
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
    renderPerfil(data, displayName);

    // 3. RED FAMILIAR
    renderFamilyTree(data);

    // 4. FOTOS (BENTO)
    renderPhotosGrid(data.photos);

    // 5. DOCUMENTOS
    renderDocuments(data);

    // 6. CRONOGRAMA
    renderTimeline(data);

    // 7. ESTUDIOS
    renderEducation(data.education);

    // 7b. TRAYECTORIA PROFESIONAL (Ocupación + Trabajo)
    renderCareer(data.career || data.occupations);

    // 7c. DOMICILIOS
    renderResidences(data.residences, data.events, data.person);

    // 8. MILITAR
    renderMilitary(data);

    // 9. NOTAS
    renderNotes(data.notes);

    document.getElementById('loading').style.display = 'none';
    document.getElementById('content').style.display = 'block';
}

function renderPerfil(data, displayName) {
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
                            <span class="font-bold block">${displayName}</span>
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
        ${person.death_date || person.death_year || !person.is_alive ? `
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
                            <span class="font-bold block">${person.death_date || person.death_year || '?'}${person.death_age ? ' (' + person.death_age + ' años)' : ''}</span>
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
    function formatYears(birth_year, death_year, is_alive = true) {
        if (birth_year && death_year) return `${birth_year} - ${death_year}`;
        if (birth_year && !death_year && !is_alive) return `${birth_year} - ?`;
        if (birth_year) return `${birth_year}`;
        if (death_year) return `? - ${death_year}`;
        if (!is_alive) return `? - ?`;
        return '';
    }
    function getDisplayName(person) {
        return formatNameWithNickname(person.name, person.nickname, person.given_name, person.surname);
    }

    let html = `
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic text-center">Árbol Familiar Inmediato</h2>
        <div class="flex flex-col items-center">
    `;

    // Parents
    if (parents.length > 0) {
        html += `<div class="flex gap-24 items-start mb-6 relative">`;
        parents.forEach(p => {
            const pDisplayName = getDisplayName(p);
            html += `
                <a href="/dossier.html?id=${dossierId(p.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                            ${p.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${p.photo_file}" alt="${pDisplayName}">` : personSvg(p.sex, p.birth_year, p.death_year, 32)}
                        </div>
                        <h4 class="text-[11px] font-bold text-center leading-tight">${pDisplayName}</h4>
                        <span class="text-[10px] opacity-60">${formatYears(p.birth_year, p.death_year, p.is_alive)}</span>
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
            const sDisplayName = getDisplayName(s);
            html += `
                <a href="/dossier.html?id=${dossierId(s.id)}" class="cursor-pointer hover:opacity-90 transition-opacity">
                    <div class="flex flex-col items-center node-card opacity-80 shrink-0">
                        <div class="w-12 h-12 rounded-full overflow-hidden border border-outline-variant/30 mb-1 bg-surface-container-high flex items-center justify-center">
                            ${s.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${s.photo_file}" alt="${sDisplayName}">` : personSvg(s.sex, s.birth_year, s.death_year, 26)}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${sDisplayName}</h4>
                        <span class="text-[10px] opacity-40">${formatYears(s.birth_year, s.death_year, s.is_alive)}</span>
                        ${recentDeathTag(s)}
                    </div>
                </a>
            `;
        });
        html += `</div>`;
    }

    // Connector line from parents/siblings down to the main subject
    html += `<div class="w-px h-12 bg-outline-variant"></div>`;

    // Main subject - centered at 50% with spouses to the right.
    // Uses an invisible spacer (same size as spouses column) on the LEFT so that
    // flex justify-center mathematically centers the main-node at 50%.

    // Get spouses list (use plural array if available, fallback to single spouse)
    const spousesList = (data.spouses && data.spouses.length > 0) ? data.spouses : (data.spouse ? [data.spouse] : []);

    const alignClass = spousesList.length === 1 ? 'items-center' : 'items-start';
    html += `
        <div class="relative w-full flex justify-center ${alignClass} gap-16 my-6">
    `;

    // Invisible spacer on the left to center main person
    if (spousesList.length > 0) {
        html += `
                <div class="flex flex-col items-center node-card invisible" aria-hidden="true">
                    <div class="w-20 h-20 mb-2"></div>
                    <h4 class="text-[11px]">.</h4>
                    <span class="text-[10px]">.</span>
                </div>
        `;
    }

    const personDisplayName = getDisplayName(person);
    html += `
                <div class="flex flex-col items-center main-node p-4 bg-primary/5 rounded-xl heritage-border border-primary/30 shadow-inner">
                    <div class="w-24 h-24 rounded-full overflow-hidden border-4 border-primary mb-3 shadow-lg bg-surface-container-high flex items-center justify-center">
                        ${person.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${person.photo_file}" alt="${personDisplayName}">` : personSvg(person.sex, person.birth_year, person.death_year, 44)}
                    </div>
                    <h3 class="font-headline font-bold text-primary text-center text-sm">${personDisplayName}</h3>
                    <span class="text-xs opacity-60 italic text-center">${formatYears(person.birth_year, person.death_year, person.is_alive)}</span>
                    <div class="mt-2 text-[8px] uppercase tracking-widest font-extrabold bg-primary text-on-primary px-2 py-0.5 rounded">Sujeto Central</div>
                    ${recentDeathTag(person)}
                </div>
    `;

    // Render all spouses in a vertical column
    if (spousesList.length > 0) {
        html += `<div class="flex flex-col gap-4">`;
        spousesList.forEach((s, idx) => {
            const spouseDisplayName = getDisplayName(s);
            const marriageInfo = s.marriage_date ? ` (${s.marriage_date})` : '';
            html += `
                <a href="/dossier.html?id=${dossierId(s.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-20 h-20 rounded-full overflow-hidden border-2 border-secondary/20 mb-2 bg-surface-container-high flex items-center justify-center">
                            ${s.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${s.photo_file}" alt="${spouseDisplayName}">` : personSvg(s.sex, s.birth_year, s.death_year, 36)}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${spouseDisplayName}</h4>
                        <span class="text-[10px] opacity-60 text-center">${formatYears(s.birth_year, s.death_year, s.is_alive)}</span>
                        ${s.marriage_date ? `<span class="text-[9px] opacity-50 text-center">${s.marriage_date}</span>` : ''}
                        ${s.divorce ? `<span class="text-[9px] opacity-40 text-center italic">divorciado ${s.divorce.date || ''}</span>` : ''}
                        ${recentDeathTag(s)}
                    </div>
                </a>
            `;
        });
        html += `</div>`;
    }

    html += `
        </div>
    `;

    // Children
    if (children.length > 0) {
        html += `<div class="tree-connector"></div>
        <div class="flex justify-center gap-16 border-t border-outline-variant pt-6 w-full flex-wrap">`;
        children.forEach(c => {
            const cDisplayName = getDisplayName(c);
            const childYears = formatYears(c.birth_year, c.death_year, c.is_alive);
            html += `
                <a href="/dossier.html?id=${dossierId(c.id)}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-16 h-16 rounded-full overflow-hidden heritage-border mb-2 bg-surface-container-high flex items-center justify-center">
                            ${c.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${c.photo_file}" alt="${cDisplayName}">` : personSvg(c.sex, c.birth_year, c.death_year, 32)}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${cDisplayName}</h4>
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
            <a href="/tree.html?id=${dossierId(person.id)}" style="color: var(--primary); text-decoration: none; font-weight: 600; font-size: 0.9rem; transition: opacity 0.2s; display: inline-block;" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                Ver árbol completo →
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
                    <div class="${cls} heritage-border bg-white overflow-hidden group relative cursor-pointer" onclick="openPhotoModal(${p.id})">
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
                    <div class="heritage-border bg-white overflow-hidden group relative aspect-square cursor-pointer" onclick="openPhotoModal(${p.id})">
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
                <button onclick="sortPhotos('oldest')" id="sort-oldest" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">Más antigua</button>
                <button onclick="sortPhotos('newest')" id="sort-newest" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">Más nueva</button>
                <button onclick="sortPhotos('added')" id="sort-added" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">Fecha incorporación</button>
            </div>
        </div>
        <div id="photos-grid-container"></div>
    `;

    document.getElementById('photos-section').innerHTML = html;
    renderBentoGrid(photos);
}

// Map tags to SVG icons
// Map tags to icon SVG files in frontend/icons/
function getIconForTag(tag) {
    const iconMap = {
        'Defunción': '/icons/defuncion.svg',
        'Nacimiento': '/icons/nacimiento.svg',
        'Bautismo': '/icons/bautismo.svg',
        'Acta de Matrimonio': '/icons/matrimonio.svg',
        'Matrimonio': '/icons/matrimonio.svg',
        'Certificado': '/icons/documentacion.svg',
        'Certificado Militar': '/icons/militar.svg',
        'Militar': '/icons/militar.svg',
        'Fotografia': '/icons/foto.svg',
        'Foto': '/icons/foto.svg',
        'Biografia': '/icons/biografia.svg',
        'Acta': '/icons/carta.svg',
        'Carta': '/icons/carta.svg',
        'Cementerio': '/icons/cementerio.svg',
        'Documentación': '/icons/documentacion.svg',
        'Obituario': '/icons/obituario.svg',
        'Padrón': '/icons/padron.svg',
        'Diversos': '/icons/diversos.svg',
    };
    return iconMap[tag] || '/icons/documentacion.svg';
}

function renderDocuments(data) {
    if (!data.documents || data.documents.length === 0) {
        document.getElementById('docs-section').style.display = 'none';
        return;
    }

    document.getElementById('docs-section').style.display = 'block';

    // Create grid of all documents with icons
    const documentCards = data.documents.map(doc => {
        const iconPath = getIconForTag(doc.tag);
        return `
            <a href="/photos/${doc.filename}" target="_blank"
               class="border border-outline-variant/20 rounded-xl p-6 hover:shadow-md hover:border-primary/30 transition-all duration-200 group cursor-pointer">
                <div class="flex items-start gap-4">
                    <div class="w-12 h-12 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                        <img src="${iconPath}" alt="${doc.tag}" class="w-8 h-8" style="filter: drop-shadow(0 0 0); opacity: 1;">
                    </div>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-bold text-sm text-on-surface mb-1 group-hover:text-primary transition-colors">${doc.tag}</h4>
                        <p class="text-xs text-outline-variant truncate">${doc.title_clean}</p>
                        ${doc.date ? `<p class="text-xs text-outline mt-2 font-medium">${doc.date}</p>` : ''}
                        ${doc.place ? `<p class="text-xs text-outline-variant mt-1">${doc.place}</p>` : ''}
                    </div>
                </div>
            </a>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4 mb-8">
            <span class="material-symbols-outlined">folder_open</span>
            Repositorio Documental
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            ${documentCards}
        </div>
    `;
    document.getElementById('docs-section').innerHTML = html;
}

// Timeline state variables
let timelineEvents = [];
let timelineMode = sessionStorage.getItem('timelineMode') || 'graphic'; // 'graphic' | 'list'
let timelineFilter = null;

function renderTimeline(data) {
    buildEvents(data);
    renderTimelineSection();
}

function buildEvents(data) {
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

    function dateToComparable(dateStr) {
        // Convert date string to comparable format YYYY-MM-DD
        // Handles formats like "9 mar. 1925", "10 sept. 1925", "22 may. 1920"
        if (!dateStr) return '9999-12-31'; // Return max date if no date

        const str = String(dateStr).toLowerCase();
        const months = {
            'ene': '01', 'enero': '01', 'january': '01', 'jan': '01',
            'feb': '02', 'febrero': '02', 'february': '02',
            'mar': '03', 'marzo': '03', 'march': '03',
            'abr': '04', 'abril': '04', 'april': '04', 'apr': '04',
            'may': '05', 'mayo': '05',
            'jun': '06', 'junio': '06', 'june': '06',
            'jul': '07', 'julio': '07', 'july': '07',
            'ago': '08', 'agosto': '08', 'august': '08', 'aug': '08',
            'sept': '09', 'setembre': '09', 'september': '09', 'sep': '09',
            'oct': '10', 'octubre': '10', 'october': '10',
            'nov': '11', 'noviembre': '11', 'november': '11',
            'dic': '12', 'diciembre': '12', 'december': '12', 'dec': '12'
        };

        const yearMatch = str.match(/\d{4}/);
        if (!yearMatch) return '9999-12-31';

        const year = yearMatch[0];
        let month = '01';
        let day = '01';

        // Extract day
        const dayMatch = str.match(/^(\d+)\s/);
        if (dayMatch) day = dayMatch[1].padStart(2, '0');

        // Extract month
        for (const [monthName, monthNum] of Object.entries(months)) {
            if (str.includes(monthName)) {
                month = monthNum;
                break;
            }
        }

        return `${year}-${month}-${day}`;
    }

    function formatDateWithQualifier(dateStr) {
        if (!dateStr) return '';
        const str = String(dateStr);
        // Handle GEDCOM date qualifiers
        if (str.startsWith('ABT ')) return 'Aprox. ' + str.substring(4);
        if (str.startsWith('AFT ')) return 'Después de ' + str.substring(4);
        if (str.startsWith('BEF ')) return 'Antes de ' + str.substring(4);
        if (str.startsWith('TO ')) return 'hasta ' + str.substring(3);
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
        return `Edades: ${ageStart} - ${ageEnd}`;
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
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        const lines = [
            formatDateWithQualifier(person.birth_date) || `${person.birth_year}`,
            person.birth_place || ''
        ].filter(Boolean);

        // Add birth note if available
        if (person.birth_note) {
            lines.push(person.birth_note);
        }

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
            name: personName
        });
    }

    // Bautismo
    if (person.baptism_date) {
        const year = extractYear(person.baptism_date);
        if (year) {
            const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
            events.push({
                year: year,
                age: ageText(year),
                type: 'Bautismo',
                lines: [
                    formatDateWithQualifier(person.baptism_date) || '',
                    person.baptism_place || '',
                    person.godparents ? `Padrinos: ${person.godparents}` : ''
                ].filter(Boolean),
                note: '',
                photo: null,
                name: personName
            });
        }
    }

    // Matrimonios (use spouses array, with fallback to single spouse)
    const spousesList = (data.spouses && data.spouses.length > 0) ? data.spouses : (data.spouse ? [data.spouse] : []);
    if (spousesList && spousesList.length > 0) {
        spousesList.forEach(s => {
            const year = extractYear(s.marriage_date);
            if (year) {
                const spouseName = formatNameWithNickname(s.name, s.nickname, s.given_name, s.surname) || s.name;
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Matrimonio con:',
                    lines: [
                        s.marriage_date ? formatDateWithQualifier(s.marriage_date) : '',
                        s.marriage_place ? `${s.marriage_place}` : ''
                    ].filter(Boolean),
                    photo: s.photo_file,
                    personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
                    name: spouseName
                });
            }

            // Divorcio
            if (s.divorce && s.divorce.date) {
                const divYear = extractYear(s.divorce.date);
                if (divYear) {
                    const spouseName = formatNameWithNickname(s.name, s.nickname, s.given_name, s.surname) || s.name;
                    events.push({
                        year: divYear,
                        age: ageText(divYear),
                        type: 'Divorcio de:',
                        lines: [
                            formatDateWithQualifier(s.divorce.date) || '',
                            s.divorce.place ? `${s.divorce.place}` : ''
                        ].filter(Boolean),
                        note: s.divorce.note || '',
                        photo: s.photo_file,
                        personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
                        name: spouseName
                    });
                }
            }

            // Pareja (partnership - only show if no marriage_date)
            if (s.partnership_date) {
                const partYear = extractYear(s.partnership_date);
                // Only show partnership event if there's no marriage date
                const hasMarriage = s.marriage_date && extractYear(s.marriage_date);
                if (partYear && !hasMarriage) {
                    const spouseName = formatNameWithNickname(s.name, s.nickname, s.given_name, s.surname) || s.name;
                    events.push({
                        year: partYear,
                        age: ageText(partYear),
                        type: 'Pareja:',
                        lines: [
                            formatDateWithQualifier(s.partnership_date) || ''
                        ].filter(Boolean),
                        photo: s.photo_file,
                        personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
                        name: spouseName
                    });
                }
            }

            // Fallecimiento del cónyuge (only if before or same year as subject's death)
            if (s.death_year && !s.is_alive) {
                const spouseDeathYear = s.death_year;
                const subjectDeathYear = person.death_year || 9999;
                if (spouseDeathYear <= subjectDeathYear) {
                    const spouseName = formatNameWithNickname(s.name, s.nickname, s.given_name, s.surname) || s.name;
                    const isFemale = (s.sex === 'F');
                    events.push({
                        year: spouseDeathYear,
                        age: ageText(spouseDeathYear),
                        type: isFemale ? 'Fallecimiento de la esposa:' : 'Fallecimiento del esposo:',
                        lines: [
                            s.death_date ? formatDateWithQualifier(s.death_date) : `${spouseDeathYear}`,
                            s.death_place || ''
                        ].filter(Boolean),
                        photo: s.photo_file,
                        personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
                        name: spouseName
                    });
                }
            }
        });
    }

    // Hijos (with gender-specific text)
    if (data.children) {
        data.children.forEach(c => {
            const year = extractYear(c.birth_year);
            if (year) {
                const typeText = c.sex === 'F' ? 'Nacimiento de la hija' : 'Nacimiento del hijo';
                const childName = formatNameWithNickname(c.name, c.nickname, c.given_name, c.surname) || c.name;
                events.push({
                    year: year,
                    age: ageText(year),
                    type: typeText,
                    lines: [
                        formatDateWithQualifier(c.birth_date) || `${c.birth_year}`,
                        c.birth_place || ''
                    ].filter(Boolean),
                    photo: c.photo_file,
                    personSex: c.sex, personBirthYear: c.birth_year, personDeathYear: c.death_year,
                    name: childName
                });
            }

            // Fallecimiento del hijo/hija (only if before or same year as subject's death)
            if (c.death_year && !c.is_alive) {
                const childDeathYear = c.death_year;
                const subjectDeathYear = person.death_year || 9999;
                if (childDeathYear <= subjectDeathYear) {
                    const typeText = c.sex === 'F' ? 'Fallecimiento de la hija:' : 'Fallecimiento del hijo:';
                    const childName = formatNameWithNickname(c.name, c.nickname, c.given_name, c.surname) || c.name;
                    events.push({
                        year: childDeathYear,
                        age: ageText(childDeathYear),
                        type: typeText,
                        lines: [
                            c.death_date ? formatDateWithQualifier(c.death_date) : `${childDeathYear}`,
                            c.death_place || ''
                        ].filter(Boolean),
                        photo: c.photo_file,
                        personSex: c.sex, personBirthYear: c.birth_year, personDeathYear: c.death_year,
                        name: childName
                    });
                }
            }

            // Children's marriages (but only if before parent's death)
            if (c.marriages && c.marriages.length > 0) {
                c.marriages.forEach(m => {
                    const mYear = extractYear(m.marriage_date);
                    // Only show marriage if it happened before or on the day of parent's death
                    const marriageDate = dateToComparable(m.marriage_date);
                    const deathDate = dateToComparable(person.death_date || person.death_year);
                    if (mYear && marriageDate <= deathDate) {
                        const lines = [
                            m.marriage_date ? formatDateWithQualifier(m.marriage_date) : 'Approx. ' + mYear,
                            m.marriage_place ? `${m.marriage_place}` : ''
                        ].filter(Boolean);

                        const spouseName = formatNameWithNickname(m.spouse_name, m.spouse_nickname, m.spouse_given_name, m.spouse_surname) || m.spouse_name;
                        const childName = formatNameWithNickname(c.name, c.nickname, c.given_name, c.surname) || c.name;

                        events.push({
                            year: mYear,
                            age: ageText(mYear),
                            type: `Matrimonio de ${c.sex === 'F' ? 'la hija' : 'el hijo'}:`,
                            lines: lines,
                            photo: m.spouse_photo,
                            name: spouseName,
                            childPhoto: c.photo_file,
                            childSex: c.sex, childBirthYear: c.birth_year, childDeathYear: c.death_year,
                            childName: childName,
                            isChildMarriage: true
                        });
                    }
                });
            }
        });
    }

    // Ocupaciones (with date range support)
    if (data.occupations) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        data.occupations.forEach(o => {
            let year = extractYear(o.date);
            // Only include occupations with actual dates in the timeline
            // Occupations without dates appear in the Career section
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
                        formatDateRange(o.date) || '',
                        o.title || '',
                        o.place || ''
                    ].filter(Boolean),
                    photo: null,
                    name: personName
                });
            }
        });
    }

    // Residencias (with date range support)
    if (data.residences) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
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
                    name: personName
                });
            }
        });
    }

    // Alistamiento militar
    if (data.military) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        data.military.forEach(m => {
            const year = extractYear(m.date);
            if (year) {
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Alistamiento Militar',
                    lines: [
                        formatDateWithQualifier(m.date) || '',
                        m.description || '',
                        m.place || ''
                    ].filter(Boolean),
                    photo: null,
                    name: personName
                });
            }
        });
    }

    // Anécdotas
    if (data.anecdotes) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        data.anecdotes.forEach(a => {
            const year = extractYear(a.date);
            if (year) {
                events.push({
                    year: year,
                    age: ageText(year),
                    type: 'Anécdota',
                    lines: [
                        formatDateWithQualifier(a.date) || '',
                        a.description || '',
                        a.place || ''
                    ].filter(Boolean),
                    photo: null,
                    name: personName
                });
            }
        });
    }

    // Generic events (Award, Illness, Funeral, Membership, etc.)
    if (data.events) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        data.events.forEach(e => {
            const year = extractYear(e.date);
            if (year) {
                let ageDisplay = '';
                // Check if date contains a range like "1957 - 1960" or "FROM ... TO ..."
                if (e.date && (e.date.includes(' - ') || e.date.includes(' TO '))) {
                    const parts = e.date.split(/\s-\s|\s+TO\s+/);
                    const startYear = extractYear(parts[0]);
                    const endYear = extractYear(parts[1]);
                    if (startYear && endYear) {
                        ageDisplay = ageRangeText(startYear, endYear);
                    }
                }
                events.push({
                    year: year,
                    age: ageDisplay || ageText(year),
                    type: e.type || 'Evento',
                    lines: [
                        formatDateWithQualifier(e.date) || '',
                        e.place || ''
                    ].filter(Boolean),
                    note: e.description || '',  // Store note separately for italic rendering
                    photo: null,
                    name: personName
                });
            }
        });
    }

    // Defunción
    if (person.death_year) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        const deathLines = [formatDateWithQualifier(person.death_date) || `${person.death_year}`];
        if (person.death_place) deathLines.push(person.death_place);
        if (person.death_cause) deathLines.push(`Causa: ${person.death_cause}`);

        events.push({
            year: person.death_year,
            age: ageText(person.death_year),
            type: 'Defunción',
            lines: deathLines,
            note: person.death_note || '',
            photo: null,
            name: personName
        });
    }

    // Entierro (after death)
    if (data.burial && data.burial.length > 0) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
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
                    name: personName
                });
            }
        });
    }

    if (events.length === 0) {
        timelineEvents = [];
        return;
    }

    // Fallecimiento de ex-cónyuge (si el cónyuge falleció)
    const spousesList2 = (data.spouses && data.spouses.length > 0) ? data.spouses : (data.spouse ? [data.spouse] : []);
    spousesList2.forEach(s => {
        if (s.death_year && s.divorce && s.divorce.date) {
            const divYear = extractYear(s.divorce.date);
            const deathYear = s.death_year;
            // Only show if death was after divorce
            if (deathYear >= divYear) {
                const spouseName = formatNameWithNickname(s.name, s.nickname, s.given_name, s.surname) || s.name;
                events.push({
                    year: deathYear,
                    age: ageText(deathYear),
                    type: 'Fallecimiento del ex-cónyuge',
                    lines: [
                        s.death_date ? formatDateWithQualifier(s.death_date) : `${deathYear}`,
                        s.death_place ? `${s.death_place}` : ''
                    ].filter(Boolean),
                    photo: s.photo_file,
                    name: spouseName
                });
            }
        }
    });

    // Sociedad del hijo - Dynamic from child partnerships
    if (data.children) {
        data.children.forEach(child => {
            if (child.partnerships && child.partnerships.length > 0) {
                child.partnerships.forEach(partnership => {
                    const year = extractYear(partnership.partnership_date);
                    if (year) {
                        const childName = formatNameWithNickname(child.name, child.nickname, child.given_name, child.surname) || child.name;
                        const partnerName = formatNameWithNickname(partnership.partner_name, partnership.partner_nickname, partnership.partner_given_name, partnership.partner_surname) || partnership.partner_name;

                        const photos = [];
                        if (child.photo_file) {
                            photos.push({ name: childName, photo: child.photo_file, personSex: child.sex, personBirthYear: child.birth_year, personDeathYear: child.death_year });
                        } else {
                            photos.push({ name: childName, photo: null, personSex: child.sex, personBirthYear: child.birth_year, personDeathYear: child.death_year });
                        }
                        if (partnership.partner_photo) {
                            photos.push({ name: partnerName, photo: partnership.partner_photo });
                        } else {
                            photos.push({ name: partnerName, photo: null });
                        }

                        events.push({
                            year: year,
                            age: ageText(year),
                            type: 'Sociedad del hijo',
                            lines: [formatDateWithQualifier(partnership.partnership_date) || ''],
                            photos: photos,
                            name: person.name
                        });
                    }
                });
            }
        });
    }

    // Sort by full date (year, month, day), not just year
    // Birth (Nacimiento) always comes first
    events.sort((a, b) => {
        // Birth events always come first
        if (a.type === 'Nacimiento' && b.type !== 'Nacimiento') return -1;
        if (a.type !== 'Nacimiento' && b.type === 'Nacimiento') return 1;

        // For other events, sort by date
        const dateA = dateToComparable(a.lines[0] || '');  // First line is the date
        const dateB = dateToComparable(b.lines[0] || '');
        return dateA.localeCompare(dateB);
    });

    timelineEvents = events;
}

function renderTimelineSection() {
    if (timelineEvents.length === 0) {
        document.getElementById('timeline-section').style.display = 'none';
        return;
    }

    document.getElementById('timeline-section').style.display = 'block';

    // Get unique event types for filters
    const uniqueTypes = [...new Set(timelineEvents.map(e => e.type))];

    // Filter events
    const filteredEvents = timelineFilter
        ? timelineEvents.filter(e => e.type === timelineFilter)
        : timelineEvents;

    // Generate content based on mode
    let contentHtml = '';
    if (timelineMode === 'list') {
        contentHtml = renderListMode(filteredEvents);
    } else {
        contentHtml = renderGraphicMode(filteredEvents);
    }

    // Generate filter buttons
    const filterButtonsHtml = `
        <button onclick="setTimelineFilter(null)" class="px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors ${timelineFilter === null ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">Todos</button>
        ${uniqueTypes.map(type => `
            <button onclick="setTimelineFilter('${type}')" class="px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors ${timelineFilter === type ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">
                ${type}
            </button>
        `).join('')}
    `;

    const html = `
        <div class="flex items-center justify-between mb-6">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">event_note</span>
                Cronograma Biográfico
            </h2>
            <div class="flex gap-2">
                <button onclick="setTimelineMode('graphic')" class="px-4 py-2 text-xs font-bold uppercase rounded-lg transition-colors ${timelineMode === 'graphic' ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">Gráfico</button>
                <button onclick="setTimelineMode('list')" class="px-4 py-2 text-xs font-bold uppercase rounded-lg transition-colors ${timelineMode === 'list' ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">Lista</button>
            </div>
        </div>
        <div class="flex flex-wrap gap-2 mb-6" id="timeline-filters">
            ${filterButtonsHtml}
        </div>
        <div id="timeline-content">
            ${contentHtml}
        </div>
    `;
    document.getElementById('timeline-section').innerHTML = html;
}

function renderGraphicMode(events) {
    const graphicHtml = events.map((e, idx) => {
        let photosHtml = '';
        const thumbDiv = (photo, sex, by, dy, name) => {
            const img = photo
                ? `<img class="w-8 h-8 rounded-full object-cover border border-outline-variant/30" src="/photos/${photo}" alt="${name}">`
                : `<div class="w-8 h-8 rounded-full border border-outline-variant/30 bg-surface-container-high flex items-center justify-center flex-shrink-0">${personSvg(sex, by, dy, 20)}</div>`;
            return `<div class="flex items-center gap-1">${img}<span class="text-sm font-bold">${name}</span></div>`;
        };

        if (e.isChildMarriage) {
            photosHtml = `
                <div class="flex items-center gap-2 mb-3">
                    ${thumbDiv(e.childPhoto, e.childSex, e.childBirthYear, e.childDeathYear, e.childName)}
                    <span class="text-xs text-outline mx-1">y</span>
                    ${thumbDiv(e.photo, null, null, null, e.name)}
                </div>
            `;
        } else if (e.photos && e.photos.length > 0) {
            photosHtml = `
                <div class="flex items-center gap-3 mb-2">
                    ${e.photos.map(p => thumbDiv(p.photo, p.personSex, p.personBirthYear, p.personDeathYear, p.name))
                        .join('<span class="text-xs text-outline mx-1">y</span>')}
                </div>
            `;
        } else if (e.photo || e.personSex !== undefined) {
            photosHtml = `<div class="flex items-center gap-3 mb-2">${thumbDiv(e.photo, e.personSex, e.personBirthYear, e.personDeathYear, e.name)}</div>`;
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
                    ${e.note ? `<div class="text-sm text-outline italic mt-2">${e.note}</div>` : ''}
                </div>
            </div>
        </div>
    `;
    }).join('');

    return `<div class="space-y-2">${graphicHtml}</div>`;
}

function renderListMode(events) {
    const listHtml = `
        <div class="overflow-x-auto">
            <table class="w-full text-sm">
                <thead>
                    <tr class="border-b border-outline-variant/30">
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">Fecha</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">Evento</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">Descripción</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">Notas</th>
                    </tr>
                </thead>
                <tbody>
                    ${events.map(e => {
                        const fecha = e.lines[0] || '';
                        const descripcion = e.lines.slice(1).join(' • ') || '';
                        const notas = e.note || '';
                        return `
                            <tr class="border-b border-outline-variant/20 hover:bg-outline-variant/5 transition-colors" data-type="${e.type}">
                                <td class="px-4 py-3 text-xs whitespace-nowrap font-semibold text-primary">${e.year}</td>
                                <td class="px-4 py-3 font-semibold text-sm">${e.type}</td>
                                <td class="px-4 py-3 text-outline">${descripcion}</td>
                                <td class="px-4 py-3 text-outline italic">${notas}</td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
    return listHtml;
}

function setTimelineMode(mode) {
    timelineMode = mode;
    sessionStorage.setItem('timelineMode', mode);
    renderTimelineSection();
}

function setTimelineFilter(type) {
    timelineFilter = type;
    renderTimelineSection();
}

function renderCareer(careerList) {
    if (!careerList || careerList.length === 0) {
        document.getElementById('career-section').style.display = 'none';
        return;
    }

    document.getElementById('career-section').style.display = 'block';

    function linkifyCareerText(text) {
        if (!text) return text;
        return text.replace(/(https?:\/\/[^\s]+)/g, url => {
            const display = url.length > 50 ? url.slice(0, 50) + '…' : url;
            return `<a href="${url}" target="_blank" rel="noopener" style="color:var(--primary);word-break:break-all;">${display}</a>`;
        });
    }

    const cards = careerList.map((c, i) => {
        return `
            <div class="p-6 bg-white heritage-border rounded-xl shadow-sm border-l-4 border-primary">
                <p class="text-[10px] text-outline font-medium mb-2">${c.date || 'Período desconocido'}</p>
                ${c.place ? `<p class="text-sm font-bold text-on-surface mb-3">${c.place}</p>` : ''}
                <p class="text-xs text-outline">${linkifyCareerText(c.title)}</p>
            </div>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <span class="material-symbols-outlined">business_center</span>
            Trayectoria Profesional
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">${cards}</div>
    `;
    document.getElementById('career-section').innerHTML = html;
}

function renderEducation(educationList) {
    if (!educationList || educationList.length === 0) {
        document.getElementById('education-section').style.display = 'none';
        return;
    }

    document.getElementById('education-section').style.display = 'block';

    const cards = educationList.map(e => `
        <div class="p-6 bg-white heritage-border rounded-xl shadow-sm border-l-4 border-primary">
            <p class="text-[10px] text-outline font-medium mb-2">${e.date || 'Período desconocido'}</p>
            ${e.place ? `<p class="text-sm font-bold text-on-surface mb-3">${e.place}</p>` : ''}
            <p class="text-xs text-outline">${e.title || ''}</p>
        </div>
    `).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="w-7 h-7">
                <path d="M5.33333 3.00001C7.79379 2.99657 10.1685 3.88709 12 5.5V21C10.1685 19.3871 7.79379 18.4966 5.33333 18.5C3.77132 18.5 2.99032 18.5 2.64526 18.2792C2.4381 18.1466 2.35346 18.0619 2.22086 17.8547C2 17.5097 2 16.8941 2 15.6629V6.40322C2 4.97543 2 4.26154 2.54874 3.68286C3.09748 3.10418 3.65923 3.07432 4.78272 3.0146C4.965 3.00491 5.14858 3.00001 5.33333 3.00001Z" />
                <path d="M18.6667 3.00001C16.2062 2.99657 13.8315 3.88709 12 5.5V21C13.8315 19.3871 16.2062 18.4966 18.6667 18.5C20.2287 18.5 21.0097 18.5 21.3547 18.2792C21.5619 18.1466 21.6465 18.0619 21.7791 17.8547C22 17.5097 22 16.8941 22 15.6629V6.40322C22 4.97543 22 4.26154 21.4513 3.68286C20.9025 3.10418 20.3408 3.07432 19.2173 3.0146C19.035 3.00491 18.8514 3.00001 18.6667 3.00001Z" />
                <path d="M19 7.32566C18.8893 7.32211 18.7782 7.32032 18.6667 7.32032C18.1048 7.31954 17.5475 7.36537 17 7.45576M19 11.0067C18.8893 11.0032 18.7782 11.0014 18.6667 11.0014C17.401 10.9996 16.158 11.2344 15 11.6824M19 14.501C18.8893 14.4975 18.7782 14.4957 18.6667 14.4957C17.401 14.4939 16.158 14.7287 15 15.1767" />
                <path d="M5 7.32566C5.11067 7.32211 5.22179 7.32032 5.33333 7.32032C5.89518 7.31954 6.45255 7.36537 7 7.45576M5 11.0067C5.11067 11.0032 5.22179 11.0014 5.33333 11.0014C6.599 10.9996 7.84198 11.2344 9 11.6824M5 14.501C5.11067 14.4975 5.22179 14.4957 5.33333 14.4957C6.599 14.4939 7.84198 14.7287 9 15.1767" />
            </svg>
            Estudios
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-8">${cards}</div>
    `;
    document.getElementById('education-section').innerHTML = html;
}

function extractYear(dateStr) {
    if (!dateStr) return 9999;
    const m = dateStr.match(/\d{4}/);
    return m ? parseInt(m[0]) : 9999;
}

function renderResidences(residences, events, person) {
    const section = document.getElementById('residences-section');
    if (!section) return;

    // Extract residence-like events (Mudanza, Emigración, Padrón, RESI)
    const residenceTags = new Set(['RESI', 'EMIG', 'CENS']);
    const residenceTypes = new Set(['Mudanza', 'Emigración', 'Residencia', 'Padrón', 'Censo']);
    const fromEvents = (events || [])
        .filter(e => residenceTags.has(e.tag) || residenceTypes.has(e.type))
        .map(e => ({
            date: e.date || '',
            address: e.place || '',
            city: '',
            country: '',
            lat: e.lat || null,
            lng: e.lng || null,
            note: e.description || '',
            source_type: e.type || '',
        }));

    // Birth place — always first, before any sort
    const birthEntry = (person?.birth_place) ? [{
        date: person.birth_date || '',
        address: person.birth_place,
        city: '',
        country: '',
        lat: null,
        lng: null,
        note: '',
        source_type: 'Nacimiento',
        _pinned_first: true,
    }] : [];

    const rest = [...(residences || []), ...fromEvents];
    const all = [...birthEntry, ...rest];
    if (!all.length) { section.style.display = 'none'; return; }
    section.style.display = 'block';

    // Sort the non-pinned entries by year; birth entry stays first
    const sorted = rest.slice().sort((a, b) => extractYear(a.date) - extractYear(b.date));
    residences = [...birthEntry, ...sorted];

    const houseIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-primary shrink-0"><path d="M1.5 10.002L7 4.00195M7 4.00195L11.311 8.70485C11.8967 9.34385 12.1896 9.66335 12.5745 9.83265C12.9593 10.002 13.3928 10.002 14.2596 10.002H22.5L18.189 5.29905C17.6033 4.66006 17.3104 4.34056 16.9255 4.17126C16.5407 4.00195 16.1072 4.00195 15.2404 4.00195H7Z"/><path d="M11 8.50028V19.9997H7C5.11438 19.9997 4.17157 19.9997 3.58579 19.4139C3 18.8281 3 17.8853 3 15.9997V8.5"/><path d="M11 19.9997H17C18.8856 19.9997 19.8284 19.9997 20.4142 19.4139C21 18.8281 21 17.8853 21 15.9997V10"/><path d="M4 7V4"/><path d="M7.125 11.25H7M7.25 11.25C7.25 11.3881 7.13807 11.5 7 11.5C6.86193 11.5 6.75 11.3881 6.75 11.25C6.75 11.1119 6.86193 11 7 11C7.13807 11 7.25 11.1119 7.25 11.25Z"/><path d="M7 20V16"/><path d="M15 14L17 14"/></svg>`;

    const geocodedCount = residences.filter(r => r.lat && r.lng).length;
    let geocodedIdx = 0;
    const cards = residences.map((r) => {
        const isBirth = r._pinned_first === true;
        const addrLine = r.address || '';
        const cityLine = [r.city, r.country].filter(Boolean).join(', ');
        const hasCoords = r.lat && r.lng;
        if (hasCoords) geocodedIdx++;
        const borderColor = isBirth ? 'border-secondary' : 'border-primary';
        const badge = hasCoords
            ? (isBirth
                ? `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-secondary text-on-secondary text-xs shrink-0 mt-0.5">★</span>`
                : `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-primary text-on-primary text-[10px] font-bold shrink-0 mt-0.5">${geocodedIdx}</span>`)
            : (isBirth ? `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-secondary/20 text-secondary text-xs shrink-0 mt-0.5">★</span>` : '');
        return `
        <div class="p-6 bg-white heritage-border rounded-xl shadow-sm border-l-4 ${borderColor} flex gap-3">
            ${badge}
            <div class="min-w-0">
                ${r.source_type ? `<p class="text-[10px] uppercase tracking-wide ${isBirth ? 'text-secondary/80' : 'text-primary/60'} font-semibold mb-0.5">${r.source_type}</p>` : ''}
                ${r.date ? `<p class="text-[10px] text-outline font-medium mb-1">${r.date}</p>` : ''}
                ${addrLine ? `<p class="text-sm font-bold text-on-surface mb-0.5">${addrLine}</p>` : ''}
                ${cityLine ? `<p class="text-xs text-outline">${cityLine}</p>` : ''}
                ${r.note ? `<p class="text-xs text-outline/80 mt-1 italic">${r.note}</p>` : ''}
            </div>
        </div>`;
    }).join('');

    section.innerHTML = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            ${houseIcon} Domicilios
        </h2>
        <div id="residences-map" class="w-full heritage-border shadow-sm"></div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6">${cards}</div>`;

    // Leaflet map — only geocoded entries get numbered markers matching card labels
    const geocoded = residences.filter(r => r.lat && r.lng).map((r, i) => ({ ...r, _mapN: i + 1 }));
    if (!geocoded.length) {
        document.getElementById('residences-map').style.display = 'none';
        return;
    }

    // Defer Leaflet init until after browser reflows the newly-visible section
    setTimeout(() => {
        const map = L.map('residences-map', { scrollWheelZoom: true });
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
            maxZoom: 18,
        }).addTo(map);

        const markerHtml = (n, isBirth) => isBirth
            ? `<div style="background:#78583e;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.25);">★</div>`
            : `<div style="background:#2D4B33;color:white;border-radius:50%;width:28px;height:28px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;border:2px solid white;box-shadow:0 2px 6px rgba(0,0,0,0.25);">${n}</div>`;

        // Offset markers that share identical coords so they're all visible
        const seen = {};
        const jittered = geocoded.map(r => {
            const key = `${r.lat.toFixed(5)},${r.lng.toFixed(5)}`;
            const n = seen[key] = (seen[key] || 0) + 1;
            const angle = (n - 1) * 2.4; // ~golden angle spread
            const dist = n === 1 ? 0 : 0.0003 * Math.ceil((n - 1) / 6);
            return { ...r, lat: r.lat + dist * Math.cos(angle), lng: r.lng + dist * Math.sin(angle) };
        });

        const bounds = [];
        jittered.forEach(r => {
            const marker = L.marker([r.lat, r.lng], {
                icon: L.divIcon({ className: '', html: markerHtml(r._mapN, r._pinned_first), iconSize: [28, 28], iconAnchor: [14, 14] })
            }).addTo(map);
            const addrParts = [r.address, r.city].filter(Boolean).join(', ');
            const dateStr = r.date ? `<div style="font-size:11px;color:#727971;margin-top:4px">${r.date}</div>` : '';
            marker.bindPopup(`<b style="color:#2D4B33;font-size:13px">${addrParts}</b>${dateStr}`, { maxWidth: 240 });
            bounds.push([r.lat, r.lng]);
        });

        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
    }, 50);
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
        const formatted = n
            .replace(/\n/g, '<br>')
            .replace(/^---$/gm, '<hr class="my-4 border-outline-variant">')
            .replace(/<a ([^>]*)>([^<]{60,})<\/a>/g, (match, attrs, text) => {
                const truncated = text.slice(0, 35) + '...' + text.slice(-15);
                return `<a ${attrs}>${truncated}</a>`;
            });
        return `
            <article class="relative p-10 bg-white heritage-border shadow-inner rounded-sm font-headline">
                <div class="absolute top-0 right-0 p-4 text-[10px] font-bold text-outline">NOTA ${i+1}</div>
                <div class="space-y-6 text-lg italic leading-relaxed opacity-90">
                    <p>${formatted}</p>
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
