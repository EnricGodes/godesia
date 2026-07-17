function personSvg(sex, birth_year, death_year, px) {
    px = px || 24;
    const cy = new Date().getFullYear();
    const isKid = (birth_year && death_year && (death_year - birth_year) < 15)
        || (birth_year && birth_year >= cy - 15);
    const NEUTRO = 'M14.5 16.5001L18.216 17.6178C19.6034 18.0424 20.6341 19.1553 20.9763 20.51C21.1115 21.0457 20.6489 21.5001 20.0936 21.5001H3.90639C3.35107 21.5001 2.88845 21.0457 3.02375 20.51C3.36593 19.1553 4.39659 18.0424 5.78401 17.6178L9.5 16.5001V14.5623C7.71916 13.1685 6.5 11.4999 6.5 7.91674C6.5 4.32689 8.45474 2.49993 11.4923 2.49993C13.6433 2.49993 14.5385 3.49993 14.5385 3.49993C17.0769 3.49993 17.5 5.59712 17.5 7.91674C17.5 11.4999 16.2808 13.1685 14.5 14.5623V16.5001ZM10.65 8.25C10.9 7.45 11.5 7.05 12.25 7.05C13.05 7.05 13.65 7.55 13.65 8.3C13.65 9.45 12 9.55 12 10.85V11.35M12 13.25V13.3';
    let d;
    if (isKid) {
        if (sex === 'M')      d = 'M14 15.7L17.25 16.75C18.55 17.17 19.5 18.12 19.88 19.32C20.04 19.83 19.6 20.3 19.05 20.3H4.95C4.4 20.3 3.96 19.83 4.12 19.32C4.5 18.12 5.45 17.17 6.75 16.75L10 15.7V14.15C8.45 13.05 7.35 11.65 7.35 8.85C7.35 5.65 9.05 4.1 11.6 4.1C13.3 4.1 14.05 4.85 14.05 4.85C16.15 4.85 16.65 6.45 16.65 8.85C16.65 11.65 15.55 13.05 14 14.15V15.7Z';
        else if (sex === 'F') d = 'M14 15.6L17.25 16.63C18.54 17.03 19.49 17.98 19.87 19.18C20.03 19.69 19.59 20.15 19.05 20.15H4.95C4.41 20.15 3.97 19.69 4.13 19.18C4.51 17.98 5.46 17.03 6.75 16.63L10 15.6V14.05C8.45 12.95 7.35 11.5 7.35 8.85C7.35 5.65 9.05 4.1 11.6 4.1C14.15 4.1 15.85 5.65 15.85 8.85C15.85 11.5 14.75 12.95 13.2 14.05V15.6ZM6.35 9.7C5.65 10.05 5.35 10.75 5.55 11.45C5.77 12.25 6.47 12.83 7.35 12.95C7.9 12.2 8.05 11.38 7.8 10.63C7.57 9.95 7.02 9.65 6.35 9.7ZM17.65 9.7C16.98 9.65 16.43 9.95 16.2 10.63C15.95 11.38 16.1 12.2 16.65 12.95C17.53 12.83 18.23 12.25 18.45 11.45C18.65 10.75 18.35 10.05 17.65 9.7';
        else                  d = NEUTRO;
    } else {
        if (sex === 'M')      d = 'M14.5 16.5001L18.216 17.6178C19.6034 18.0424 20.6341 19.1553 20.9763 20.51C21.1115 21.0457 20.6489 21.5001 20.0936 21.5001H3.90639C3.35107 21.5001 2.88845 21.0457 3.02375 20.51C3.36593 19.1553 4.39659 18.0424 5.78401 17.6178L9.5 16.5001V14.5623C7.71916 13.1685 6.5 11.4999 6.5 7.91674C6.5 4.32689 8.45474 2.49993 11.4923 2.49993C13.6433 2.49993 14.5385 3.49993 14.5385 3.49993C17.0769 3.49993 17.5 5.59712 17.5 7.91674C17.5 11.4999 16.2808 13.1685 14.5 14.5623V16.5001Z';
        else if (sex === 'F') d = 'M14.5 16.5L18.216 17.6177C19.6034 18.0423 20.6341 19.1553 20.9763 20.5099C21.1115 21.0456 20.6489 21.5 20.0936 21.5H3.90639C3.35107 21.5 2.88845 21.0456 3.02375 20.5099C3.36593 19.1553 4.39659 18.0423 5.78401 17.6177L9.5 16.5V14.345C8.21522 14.1822 7.03039 13.897 6 13.5161C6.5 12.5322 7 11.0563 7 7.61264C7 1.70919 12.5 1.70912 14 3.67672C17 3.18499 17 5.64483 17 8.59655C17 10.9579 17.6667 12.8602 18 13.5161C16.9696 13.897 15.7848 14.1822 14.5 14.345V16.5Z';
        else                  d = NEUTRO;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="${px}" height="${px}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round" style="opacity:0.45"><path d="${d}"/></svg>`;
}

/* i18n: t()/I18N vienen de i18n.js (inyectado por el backend) */
const _i18nT = window.t || function (k, p, f) { return f !== undefined ? f : k; };
const _lhref = window.I18N ? window.I18N.href : function (p) { return p; };
const _api = window.I18N ? window.I18N.apiUrl : function (p) { return p; };

async function loadDossier() {
    const params = new URLSearchParams(window.location.search);
    const personId = params.get('id');

    if (!personId) {
        showError(_i18nT('pages.dossier.no_person', null, 'Persona no especificada'));
        return;
    }

    try {
        const res = await fetch(_api(`/api/dossier/${personId}`));
        if (!res.ok) {
            throw new Error(_i18nT('pages.dossier.not_found', null, 'Persona no encontrada'));
        }

        const data = await res.json();
        renderDossier(data);

        const ctaUrl = _lhref(`/colaborar.html?person=${personId}&source=dossier`);
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
    document.getElementById('error').textContent = _i18nT('common.error_prefix', null, 'Error') + ': ' + message;
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
        let url = `/api/default-photo?sex=${person.sex || ''}`;
        if (person.birth_year) url += `&birth_year=${person.birth_year}`;
        if (person.death_year) url += `&death_year=${person.death_year}`;
        document.querySelector('#hero-photo img').src = url;
    }
    document.getElementById('hero-name').textContent = displayName;

    const birthYear = person.birth_year || '?';
    const birthPlace = person.birth_city || person.birth_place || 'Barcelona, España';
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
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">${_i18nT('pages.dossier.inventory', null, 'Inventario')}</span>
            <span class="font-bold">${person.photo_count || 0} ${_i18nT('pages.dossier.media', null, 'Medios')}</span>
        </div>
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">${_i18nT('pages.dossier.last_update', null, 'Última Act.')}</span>
            <span class="font-bold">${data.gedcom_date || '—'}</span>
        </div>
        ${person.death_year && person.death_year >= 2021 && !person.is_alive ? `
        <div class="bg-surface-container px-4 py-2 rounded-lg border border-outline-variant/30 text-xs">
            <span class="block text-outline font-bold uppercase tracking-tighter mb-1">${_i18nT('pages.dossier.status', null, 'Estado')}</span>
            <span class="font-bold text-secondary">† ${_i18nT('common.recent', null, 'RECIENTE')}</span>
        </div>
        ` : ''}
    `;

    // 2. PERFIL BÁSICO
    renderPerfil(data, displayName);
    renderVitalMap(data.vital_points || []);

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

    // 7d. SEPULTURA (nicho asignado manualmente en el gestor de cementerios)
    renderBurialNiche(data.niche);

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
        <div class="flex flex-col space-y-8" id="card-minibio">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">history_edu</span>
                ${_i18nT('pages.dossier.minibio_title', null, 'Minibiografía')}
            </h2>
            <div class="flex-1 bg-surface-container-low p-8 rounded-xl heritage-border">
                <div id="card-minibio-text" class="text-sm text-on-surface-variant italic opacity-70">${_i18nT('common.loading', null, 'Cargando...')}</div>
            </div>
        </div>
        <div class="flex flex-col space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">explore</span>
                ${_i18nT('pages.dossier.vital_map', null, 'Mapa Vital')}
            </h2>
            <div class="flex-1 bg-surface-container-low p-4 rounded-xl heritage-border">
                <div id="vital-map" class="w-full heritage-border shadow-sm"></div>
                <div id="vital-map-empty" style="display:none;" class="flex items-center justify-center h-64 text-sm text-on-surface-variant italic opacity-70">${_i18nT('pages.dossier.no_geo', null, 'Sin datos geográficos')}</div>
            </div>
        </div>
        <div class="flex flex-col space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">fingerprint</span>
                ${_i18nT('pages.dossier.profile_title', null, 'Perfil de Registro')}
            </h2>
            <div class="flex-1 bg-surface-container-low p-8 rounded-xl heritage-border space-y-6">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('pages.dossier.full_name', null, 'Nombre Completo')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${displayName}</span>
                            ${baptismNames ? `<span class="italic opacity-80 text-xs mt-1 block">${_i18nT('pages.dossier.baptism_names', null, 'Nombres de bautismo')}: ${baptismNames}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('pages.dossier.gender', null, 'Género')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.sex === 'M' ? _i18nT('common.male', null, 'Masculino') : _i18nT('common.female', null, 'Femenino')}</span>
                        </dd>
                    </div>
                </div>
                <div class="pt-6 border-t border-outline-variant/30 grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('common.birth', null, 'Nacimiento')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.birth_date || person.birth_year}</span>
                            ${(person.birth_city || person.birth_place) ? `<span class="italic opacity-80 text-xs">${person.birth_city || person.birth_place}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('common.baptism', null, 'Bautismo')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${baptismDate || '—'}</span>
                            ${baptismPlace ? `<span class="italic opacity-80 text-xs">${baptismPlace}</span>` : `<span class="italic opacity-80 text-xs">${_i18nT('pages.dossier.not_registered', null, 'No registrado')}</span>`}
                            ${godparents ? `<span class="italic opacity-80 text-xs block mt-1">${_i18nT('pages.dossier.godparents', null, 'Padrinos')}: ${godparents}</span>` : ''}
                        </dd>
                    </div>
                </div>
            </div>
        </div>
        ${person.death_date || person.death_year || !person.is_alive ? `
        <div class="flex flex-col space-y-8">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">account_balance</span>
                ${_i18nT('pages.dossier.death_title', null, 'Defunción y Sepelio')}
            </h2>
            <div class="flex-1 bg-surface-container-highest/30 p-8 rounded-xl heritage-border space-y-6">
                <div class="grid grid-cols-2 gap-8">
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('pages.dossier.decease', null, 'Fallecimiento')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.death_date || person.death_year || '?'}${person.death_age ? ' (' + person.death_age + ' ' + _i18nT('common.years', null, 'años') + ')' : ''}</span>
                            ${(person.death_city || person.death_place) ? `<span class="italic opacity-80 text-xs">${person.death_city || person.death_place}</span>` : ''}
                        </dd>
                    </div>
                    <div>
                        <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-2">${_i18nT('pages.dossier.cause', null, 'Causa')}</dt>
                        <dd class="text-sm">
                            <span class="font-bold block">${person.death_cause || '—'}</span>
                        </dd>
                    </div>
                </div>
                ${data.burial && data.burial.length > 0 ? `
                <div class="pt-6 border-t border-outline-variant/30">
                    <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-4">${_i18nT('pages.dossier.burial_location', null, 'Localización Exacta Sepultura')}</dt>
                    <dd class="space-y-3 text-xs">
                        ${data.burial.map((b, i) => `
                            ${b.place ? `
                            <div>
                                <span class="block text-outline font-bold mb-1">${_i18nT('pages.dossier.cemetery', null, 'Cementerio')}</span>
                                <span class="text-xs">${b.place}</span>
                            </div>
                            ` : ''}
                            ${b.place_detail ? `
                            <div>
                                <span class="block text-outline font-bold mb-1">${_i18nT('pages.dossier.reference', null, 'Referencia')}</span>
                                <span class="text-xs break-words">${b.place_detail}</span>
                            </div>
                            ` : ''}
                        `).join('')}
                    </dd>
                </div>
                ` : `
                <div class="pt-6 border-t border-outline-variant/30">
                    <dt class="text-[10px] uppercase tracking-widest text-outline font-extrabold mb-4">${_i18nT('pages.dossier.burial_location', null, 'Localización Exacta Sepultura')}</dt>
                    <dd class="text-xs text-on-surface-variant italic">${_i18nT('pages.dossier.no_burial_info', null, 'Información no disponible en el registro actual')}</dd>
                </div>
                `}
            </div>
        </div>
        ` : ''}
    `;
    document.getElementById('perfil-section').innerHTML = html;

    // Fill Card1 minibio async
    fetch(_api(`/api/minibio/${encodeURIComponent((data.person.id || '').replace(/@/g, ''))}`))
        .then(r => r.json())
        .then(m => {
            const bio = m.bio || m.bio_es || m.bio_ca || '';
            const el = document.getElementById('card-minibio-text');
            if (el) {
                if (bio) {
                    el.innerHTML = `<p style="line-height:1.7;">${bio}</p>`;
                    el.classList.remove('opacity-70');
                } else {
                    el.textContent = _i18nT('pages.dossier.no_minibio', null, 'Sin minibiografía disponible.');
                }
            }
        })
        .catch(() => {
            const el = document.getElementById('card-minibio-text');
            if (el) el.textContent = _i18nT('pages.dossier.no_minibio', null, 'Sin minibiografía disponible.');
        });
}

const VITAL_ICONS = {
    birth: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#2d4b33" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M16.874 12C17.5826 13.037 18 14.3093 18 15.6842C18 16.5017 17.8524 17.2829 17.5838 18M7.12605 12C6.41738 13.037 6 14.3093 6 15.6842C6 19.1723 8.68629 22 12 22C14.5371 22 16.7064 20.3424 17.5838 18M17.5838 18C14.8509 16.8 12.0559 14.8333 11 14"/></svg>`,
    marriage: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#78583e" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8.5" cy="16.5" r="5.5"/><circle cx="15.5" cy="16.5" r="5.5"/><path d="M12 9C12 9 16 7.14706 16 4.13889C16 2.95761 15.1579 2 14 2C13.0526 2 12.4211 2.41176 12 3.23529C11.5789 2.41176 10.9474 2 10 2C8.84211 2 8 2.95761 8 4.13889C8 7.14706 12 9 12 9Z"/></svg>`,
    death: `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19 5.75C19 4.78352 18.9979 4.13591 18.9326 3.6543C18.8703 3.19512 18.763 3.00203 18.6338 2.875L18.6299 2.87012C18.4963 2.73657 18.2969 2.62964 17.8379 2.56739C17.3562 2.50206 16.7113 2.5 15.75 2.5H9.75C8.31373 2.5 7.31311 2.50184 6.55859 2.60352C5.8264 2.70223 5.43795 2.88237 5.16016 3.16016C4.88237 3.43795 4.70223 3.8264 4.60352 4.5586C4.50184 5.31311 4.5 6.31373 4.5 7.75V17.3037C4.87562 17.1107 5.30012 17 5.75 17H19V5.75ZM20.5 17.75C20.5 18.1642 20.1642 18.5 19.75 18.5H5.75C5.06421 18.5 4.5 19.0642 4.5 19.75C4.5 20.4358 5.06421 21 5.75 21H19.75C20.1642 21 20.5 21.3358 20.5 21.75C20.5 22.1642 20.1642 22.5 19.75 22.5H5.75C4.23579 22.5 3 21.2642 3 19.75V7.75C3 6.35628 2.99887 5.23639 3.11719 4.3584C3.2385 3.45843 3.4975 2.70173 4.09961 2.09961C4.70172 1.4975 5.45843 1.2385 6.3584 1.11719C7.23639 0.998873 8.35627 1 9.75 1H15.75C16.6687 1 17.4342 0.997909 18.04 1.08008C18.6659 1.16502 19.2292 1.35224 19.6846 1.80469C20.1453 2.25764 20.3347 2.82504 20.4199 3.45313C20.5021 4.05898 20.5 4.82661 20.5 5.75V17.75Z" fill="#2E4B33"/><path d="M11.46 13.51V5.51C11.46 5.09579 11.7958 4.76001 12.21 4.76001C12.6242 4.76001 12.96 5.09579 12.96 5.51V13.51C12.96 13.9242 12.6242 14.26 12.21 14.26C11.7958 14.26 11.46 13.9242 11.46 13.51Z" fill="#2E4B33"/><path d="M14.6897 7.76C15.1039 7.76 15.4397 8.09579 15.4397 8.51C15.4397 8.92422 15.1039 9.26 14.6897 9.26H9.72C9.30579 9.26 8.97 8.92422 8.97 8.51C8.97 8.09579 9.30579 7.76 9.72 7.76H14.6897Z" fill="#2E4B33"/></svg>`,
    burial: `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M19.7402 9.80957C19.74 5.77398 16.4653 2.5 12.4297 2.5C8.39298 2.50017 5.11058 5.7753 5.11035 9.80957V21.0703H19.7402V9.80957ZM11.6797 15.79V11.4697H9.94043C9.52622 11.4697 9.19043 11.1339 9.19043 10.7197C9.19058 10.3056 9.52631 9.96973 9.94043 9.96973H11.6797V7.79004C11.6797 7.37593 12.0156 7.04021 12.4297 7.04004C12.8439 7.04004 13.1797 7.37583 13.1797 7.79004V9.96973H14.9102C15.3242 9.96981 15.66 10.3057 15.6602 10.7197C15.6602 11.1339 15.3243 11.4696 14.9102 11.4697H13.1797V15.79C13.1797 16.2042 12.8439 16.54 12.4297 16.54C12.0156 16.5399 11.6797 16.2041 11.6797 15.79ZM21.2402 21.0801H23.1104C23.5244 21.0803 23.8604 21.416 23.8604 21.8301C23.8603 22.2441 23.5244 22.5799 23.1104 22.5801H1.75C1.33581 22.5801 1.00004 22.2443 1 21.8301C1 21.4159 1.33579 21.0801 1.75 21.0801H3.61035V9.80957C3.61058 4.94445 7.56697 1.00017 12.4297 1C17.2938 1 21.24 4.94555 21.2402 9.80957V21.0801Z" fill="#2E4B33"/></svg>`,
};

function renderVitalMap(points) {
    const mapEl = document.getElementById('vital-map');
    const emptyEl = document.getElementById('vital-map-empty');
    if (!mapEl) return;

    if (!points || !points.length) {
        mapEl.style.display = 'none';
        if (emptyEl) emptyEl.style.display = 'flex';
        return;
    }

    setTimeout(() => {
        const map = L.map('vital-map', { scrollWheelZoom: false });
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19,
        }).addTo(map);

        // Jitter markers sharing identical coords
        const seen = {};
        const jittered = points.map(p => {
            const key = `${p.lat.toFixed(5)},${p.lng.toFixed(5)}`;
            const n = seen[key] = (seen[key] || 0) + 1;
            const angle = (n - 1) * 2.4;
            const dist = n === 1 ? 0 : 0.0003 * Math.ceil((n - 1) / 6);
            return { ...p, lat: p.lat + dist * Math.cos(angle), lng: p.lng + dist * Math.sin(angle) };
        });

        const bounds = [];
        jittered.forEach(p => {
            const icon = VITAL_ICONS[p.type] || VITAL_ICONS.birth;
            const markerHtml = `<div style="background:white;border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(0,0,0,0.25);border:1.5px solid rgba(114,121,113,0.3);">${icon}</div>`;
            const marker = L.marker([p.lat, p.lng], {
                icon: L.divIcon({ className: '', html: markerHtml, iconSize: [32, 32], iconAnchor: [16, 16] })
            }).addTo(map);
            const typeLabel = {
                birth: _i18nT('common.birth', null, 'Nacimiento'),
                marriage: _i18nT('common.marriage', null, 'Matrimonio'),
                death: _i18nT('common.death', null, 'Defunción'),
                burial: _i18nT('common.burial', null, 'Sepultura')
            }[p.type] || p.type;
            marker.bindPopup(`<b style="color:#2D4B33;font-size:13px">${typeLabel}</b><div style="font-size:11px;color:#727971;margin-top:4px">${p.label}</div>`, { maxWidth: 240 });
            bounds.push([p.lat, p.lng]);
        });

        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 15 });
    }, 50);
}

function recentDeathTag(p) {
    if (!p.death_year || p.is_alive) return '';
    if (p.death_year < 2021) return '';
    return `<div class="mt-1 text-[9px] uppercase tracking-widest font-extrabold bg-secondary text-on-secondary px-2 py-0.5 rounded">† ${_i18nT('common.recent', null, 'RECIENTE')}</div>`;
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
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic text-center">${_i18nT('pages.dossier.family_tree_title', null, 'Árbol Familiar Inmediato')}</h2>
        <div class="flex flex-col items-center">
    `;

    // Parents
    if (parents.length > 0) {
        html += `<div class="flex gap-24 items-start mb-6 relative">`;
        parents.forEach(p => {
            const pDisplayName = getDisplayName(p);
            html += `
                <a href="${_lhref('/dossier.html?id=' + dossierId(p.id))}" class="cursor-pointer hover:opacity-80 transition-opacity">
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
                <a href="${_lhref('/dossier.html?id=' + dossierId(s.id))}" class="cursor-pointer hover:opacity-90 transition-opacity">
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
        <div class="relative w-full flex justify-center ${alignClass} gap-4 sm:gap-16 my-6">
    `;

    // Invisible spacer on the left to center main person (solo en pantallas
    // anchas; en móvil se oculta para que el cónyuge no quede cortado a la derecha)
    if (spousesList.length > 0) {
        html += `
                <div class="hidden sm:flex flex-col items-center node-card invisible" aria-hidden="true">
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
                    <div class="mt-2 text-[8px] uppercase tracking-widest font-extrabold bg-primary text-on-primary px-2 py-0.5 rounded">${_i18nT('pages.dossier.central_subject', null, 'Sujeto Central')}</div>
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
                <a href="${_lhref('/dossier.html?id=' + dossierId(s.id))}" class="cursor-pointer hover:opacity-80 transition-opacity">
                    <div class="flex flex-col items-center node-card">
                        <div class="w-20 h-20 rounded-full overflow-hidden border-2 border-secondary/20 mb-2 bg-surface-container-high flex items-center justify-center">
                            ${s.photo_file ? `<img class="w-full h-full object-cover" src="/photos/${s.photo_file}" alt="${spouseDisplayName}">` : personSvg(s.sex, s.birth_year, s.death_year, 36)}
                        </div>
                        <h4 class="text-[11px] font-bold text-center">${spouseDisplayName}</h4>
                        <span class="text-[10px] opacity-60 text-center">${formatYears(s.birth_year, s.death_year, s.is_alive)}</span>
                        ${s.marriage_date ? `<span class="text-[9px] opacity-50 inline-flex items-center gap-0.5" title="${_i18nT('common.marriage', null, 'Matrimonio')}"><svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" style="flex-shrink:0"><circle cx="9.5" cy="14" r="5.5"/><circle cx="14.5" cy="10" r="5.5"/></svg>${s.marriage_date}</span>` : ''}
                        ${s.divorce ? `<span class="text-[9px] opacity-40 text-center italic">${_i18nT('common.divorced', null, 'divorciado')} ${s.divorce.date || ''}</span>` : ''}
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
                <a href="${_lhref('/dossier.html?id=' + dossierId(c.id))}" class="cursor-pointer hover:opacity-80 transition-opacity">
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
            <a href="${_lhref('/arbol2.html?id=' + dossierId(person.id))}" style="color: var(--primary); text-decoration: none; font-weight: 600; font-size: 0.9rem; transition: opacity 0.2s; display: inline-block;" onmouseover="this.style.opacity='0.8'" onmouseout="this.style.opacity='1'">
                ${_i18nT('pages.dossier.view_full_tree', null, 'Ver árbol completo')} →
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
                    ${_i18nT('pages.dossier.photos_title', null, 'Memoria Visual')}
                </h2>
                <p class="text-xs text-outline font-bold uppercase tracking-widest">${_i18nT('pages.dossier.photos_subtitle', {count: photos.length}, 'Archivo Histórico ({count} medios registrados)')}</p>
            </div>
            <div class="flex gap-2 flex-wrap">
                <button onclick="sortPhotos('oldest')" id="sort-oldest" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">${_i18nT('pages.dossier.sort_oldest', null, 'Más antigua')}</button>
                <button onclick="sortPhotos('newest')" id="sort-newest" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">${_i18nT('pages.dossier.sort_newest', null, 'Más nueva')}</button>
                <button onclick="sortPhotos('added')" id="sort-added" class="sort-btn px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors border border-outline-variant text-outline-variant hover:bg-outline-variant/10">${_i18nT('pages.dossier.sort_added', null, 'Fecha incorporación')}</button>
            </div>
        </div>
        <div id="photos-grid-container"></div>
    `;

    document.getElementById('photos-section').innerHTML = html;
    renderBentoGrid(photos);
}

// Map tags (bracket labels) or doc_type values to SVG icons and display labels
const DOC_TYPE_META = {
    // bracket tags (title-based, display as-is)
    'Defunción':         { icon: '/icons/defuncion.svg' },
    'Nacimiento':        { icon: '/icons/nacimiento.svg' },
    'Bautismo':          { icon: '/icons/bautismo.svg' },
    'Acta de Matrimonio':{ icon: '/icons/matrimonio.svg' },
    'Matrimonio':        { icon: '/icons/matrimonio.svg' },
    'Certificado':       { icon: '/icons/documentacion.svg' },
    'Certificado Militar':{ icon: '/icons/militar.svg' },
    'Militar':           { icon: '/icons/militar.svg' },
    'Fotografia':        { icon: '/icons/foto.svg' },
    'Foto':              { icon: '/icons/foto.svg' },
    'Biografia':         { icon: '/icons/biografia.svg' },
    'Acta':              { icon: '/icons/carta.svg' },
    'Carta':             { icon: '/icons/carta.svg' },
    'Cementerio':        { icon: '/icons/cementerio.svg' },
    'Documentación':     { icon: '/icons/documentacion.svg' },
    'Obituario':         { icon: '/icons/obituario.svg' },
    'Padrón':            { icon: '/icons/padron.svg' },
    'Diversos':          { icon: '/icons/diversos.svg' },
    // doc_type values (DB, lowercase catalan) → label + icon
    'bautisme':    { label: 'Bautismos',             icon: '/icons/bautismo.svg' },
    'matrimoni':   { label: 'Matrimonios',            icon: '/icons/matrimonio.svg' },
    'defuncio':    { label: 'Defunciones',            icon: '/icons/defuncion.svg' },
    'naixement':   { label: 'Nacimientos',            icon: '/icons/nacimiento.svg' },
    'certificat':  { label: 'Certificados',           icon: '/icons/documentacion.svg' },
    'padro':       { label: 'Padrones',               icon: '/icons/padron.svg' },
    'testament':   { label: 'Testamentos',            icon: '/icons/carta.svg' },
    'arbre':       { label: 'Árboles Genealógicos',   icon: '/icons/carta.svg' },
    'transcripcio':{ label: 'Transcripciones',        icon: '/icons/documentacion.svg' },
    'poema':       { label: 'Poemas',                 icon: '/icons/documentacion.svg' },
    'invitacio':   { label: 'Invitaciones',           icon: '/icons/documentacion.svg' },
    'carta':       { label: 'Cartas',                 icon: '/icons/carta.svg' },
    'dibuix':      { label: 'Dibujos y Planos',       icon: '/icons/documentacion.svg' },
    'biografia':   { label: 'Biografías',             icon: '/icons/biografia.svg' },
    'document':    { label: 'Documentos',             icon: '/icons/documentacion.svg' },
};

function getIconForTag(tag) {
    return (DOC_TYPE_META[tag] || {}).icon || '/icons/documentacion.svg';
}

window.docTypeMeta = DOC_TYPE_META;

function renderDocuments(data) {
    if (!data.documents || data.documents.length === 0) {
        document.getElementById('docs-section').style.display = 'none';
        return;
    }

    document.getElementById('docs-section').style.display = 'block';

    const VITAL_ORDER = {
        'naixement': 0, 'nacimiento': 0,
        'bautisme': 1, 'bautismo': 1,
        'matrimoni': 2, 'matrimonio': 2,
        'certificat': 3, 'padro': 3, 'padron': 3, 'testament': 3,
        'transcripcio': 3, 'arbre': 3, 'poema': 3, 'carta': 3,
        'invitacio': 3, 'dibuix': 3, 'biografia': 3, 'document': 3,
        'militar': 3,
        'defuncio': 4, 'defuncion': 4,
    };
    const docOrder = d => VITAL_ORDER[d.doc_type] ?? VITAL_ORDER[d.tag?.toLowerCase()] ?? 3;
    const sorted = [...data.documents].sort((a, b) => docOrder(a) - docOrder(b));

    const documentCards = sorted.map(doc => {
        const metaLabel = (DOC_TYPE_META[doc.doc_type] || {}).label;
        const label = doc.tag
            ? _i18nT('doc_tags.' + doc.tag, null, doc.tag)
            : (metaLabel ? _i18nT('doc_types.' + doc.doc_type, null, metaLabel) : null)
              || _i18nT('common.doc_default', null, 'Documento');
        const iconPath = getIconForTag(doc.tag) !== '/icons/documentacion.svg'
            ? getIconForTag(doc.tag)
            : getIconForTag(doc.doc_type);
        return `
            <div onclick="openPhotoModal(${doc.id})"
               class="border border-outline-variant/20 rounded-xl p-6 hover:shadow-md hover:border-primary/30 transition-all duration-200 group cursor-pointer">
                <div class="flex items-start gap-4">
                    <div class="w-12 h-12 rounded-lg flex items-center justify-center shrink-0 group-hover:scale-110 transition-transform">
                        <img src="${iconPath}" alt="${label}" class="w-8 h-8" style="filter: drop-shadow(0 0 0); opacity: 1;">
                    </div>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-bold text-sm text-on-surface mb-1 group-hover:text-primary transition-colors">${label}</h4>
                        <p class="text-xs text-outline-variant truncate">${doc.title_clean || ''}</p>
                        ${doc.date ? `<p class="text-xs text-outline mt-2 font-medium">${doc.date}</p>` : ''}
                        ${doc.place ? `<p class="text-xs text-outline-variant mt-1">${doc.place}</p>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4 mb-8">
            <span class="material-symbols-outlined">folder_open</span>
            ${_i18nT('pages.dossier.docs_title', null, 'Repositorio Documental')}
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
            'ene': '01', 'enero': '01', 'january': '01', 'jan': '01', 'gen': '01', 'gener': '01',
            'feb': '02', 'febrero': '02', 'february': '02', 'febr': '02', 'febrer': '02',
            'mar': '03', 'marzo': '03', 'march': '03', 'març': '03',
            'abr': '04', 'abril': '04', 'april': '04', 'apr': '04',
            'may': '05', 'mayo': '05', 'maig': '05',
            'jun': '06', 'junio': '06', 'june': '06', 'juny': '06',
            'jul': '07', 'julio': '07', 'july': '07', 'juliol': '07',
            'ago': '08', 'agosto': '08', 'august': '08', 'aug': '08', 'agost': '08',
            'sept': '09', 'setembre': '09', 'september': '09', 'sep': '09', 'set': '09',
            'oct': '10', 'octubre': '10', 'october': '10',
            'nov': '11', 'noviembre': '11', 'november': '11', 'novembre': '11',
            'dic': '12', 'diciembre': '12', 'december': '12', 'dec': '12', 'des': '12', 'desembre': '12'
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
        if (str.startsWith('ABT ')) return _i18nT('dates.approx', null, 'Aprox.') + ' ' + str.substring(4);
        if (str.startsWith('AFT ')) return _i18nT('dates.after', null, 'Después de') + ' ' + str.substring(4);
        if (str.startsWith('BEF ')) return _i18nT('dates.before', null, 'Antes de') + ' ' + str.substring(4);
        if (str.startsWith('TO ')) return _i18nT('dates.until', null, 'hasta') + ' ' + str.substring(3);
        if (str.startsWith('FROM ') && str.includes(' TO ')) {
            const parts = str.split(' TO ');
            return _i18nT('dates.from_to', {from: parts[0].substring(5), to: parts[1]}, 'Desde {from} hasta {to}');
        }
        if (str.startsWith('BET ') && str.includes(' AND ')) {
            const parts = str.split(' AND ');
            return _i18nT('dates.between', {from: parts[0].substring(4), to: parts[1]}, 'Entre {from} y {to}');
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
        return age !== null ? _i18nT('common.age_label', {age: age}, 'Edad {age}') : '';
    }

    function ageRangeText(startYear, endYear) {
        if (!startYear || !endYear) return '';
        const ageStart = calculateAge(startYear);
        const ageEnd = calculateAge(endYear);
        if (ageStart === null || ageEnd === null) return '';
        return _i18nT('common.ages_label', {from: ageStart, to: ageEnd}, 'Edades: {from} - {to}');
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
            return _i18nT('dates.from_to_lower', {from: start, to: end}, 'desde {from} hasta {to}');
        }
        return dateStr;
    }

    /* Etiquetas de tipo de evento del cronograma: también sirven de clave de
       filtro, por lo que se definen una sola vez y se comparan entre sí. */
    const EVT = {
        birth: _i18nT('events.birth', null, 'Nacimiento'),
        baptism: _i18nT('events.baptism', null, 'Bautismo'),
        marriage_with: _i18nT('events.marriage_with', null, 'Matrimonio con:'),
        divorce_of: _i18nT('events.divorce_of', null, 'Divorcio de:'),
        partner: _i18nT('events.partner', null, 'Pareja:'),
        wife_death: _i18nT('events.wife_death', null, 'Fallecimiento de la esposa:'),
        husband_death: _i18nT('events.husband_death', null, 'Fallecimiento del esposo:'),
        daughter_birth: _i18nT('events.daughter_birth', null, 'Nacimiento de la hija'),
        son_birth: _i18nT('events.son_birth', null, 'Nacimiento del hijo'),
        daughter_death: _i18nT('events.daughter_death', null, 'Fallecimiento de la hija:'),
        son_death: _i18nT('events.son_death', null, 'Fallecimiento del hijo:'),
        daughter_marriage: _i18nT('events.daughter_marriage', null, 'Matrimonio de la hija:'),
        son_marriage: _i18nT('events.son_marriage', null, 'Matrimonio del hijo:'),
        occupation: _i18nT('events.occupation', null, 'Ocupación'),
        residence: _i18nT('events.residence', null, 'Residencia'),
        military: _i18nT('events.military', null, 'Alistamiento Militar'),
        anecdote: _i18nT('events.anecdote', null, 'Anécdota'),
        generic: _i18nT('events.generic', null, 'Evento'),
        death: _i18nT('events.death', null, 'Defunción'),
        burial: _i18nT('events.burial', null, 'Entierro'),
        ex_spouse_death: _i18nT('events.ex_spouse_death', null, 'Fallecimiento del ex-cónyuge'),
        child_partnership: _i18nT('events.child_partnership', null, 'Sociedad del hijo')
    };

    /* Traduce un tipo de evento de la BD (español, p.ej. "Trabajo", "Mudanza")
       vía event_types.<tipo>; si no hay clave, deja el original. Se usa como
       etiqueta y como clave del filtro, por lo que debe aplicarse al construir. */
    const evtType = (raw) => raw ? _i18nT('event_types.' + raw, null, raw) : EVT.generic;

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
            type: EVT.birth,
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
                type: EVT.baptism,
                lines: [
                    formatDateWithQualifier(person.baptism_date) || '',
                    person.baptism_place || '',
                    person.godparents ? `${_i18nT('pages.dossier.godparents', null, 'Padrinos')}: ${person.godparents}` : ''
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
                    type: EVT.marriage_with,
                    lines: [
                        s.marriage_date ? formatDateWithQualifier(s.marriage_date) : '',
                        s.marriage_place ? `${s.marriage_place}` : ''
                    ].filter(Boolean),
                    photo: s.photo_file,
                    personId: s.id, personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
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
                        type: EVT.divorce_of,
                        lines: [
                            formatDateWithQualifier(s.divorce.date) || '',
                            s.divorce.place ? `${s.divorce.place}` : ''
                        ].filter(Boolean),
                        note: s.divorce.note || '',
                        photo: s.photo_file,
                        personId: s.id, personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
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
                        type: EVT.partner,
                        lines: [
                            formatDateWithQualifier(s.partnership_date) || ''
                        ].filter(Boolean),
                        photo: s.photo_file,
                        personId: s.id, personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
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
                        type: isFemale ? EVT.wife_death : EVT.husband_death,
                        lines: [
                            s.death_date ? formatDateWithQualifier(s.death_date) : `${spouseDeathYear}`,
                            s.death_place || ''
                        ].filter(Boolean),
                        photo: s.photo_file,
                        personId: s.id, personSex: s.sex, personBirthYear: s.birth_year, personDeathYear: s.death_year,
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
                const typeText = c.sex === 'F' ? EVT.daughter_birth : EVT.son_birth;
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
                    personId: c.id, personSex: c.sex, personBirthYear: c.birth_year, personDeathYear: c.death_year,
                    name: childName
                });
            }

            // Fallecimiento del hijo/hija (only if before or same year as subject's death)
            if (c.death_year && !c.is_alive) {
                const childDeathYear = c.death_year;
                const subjectDeathYear = person.death_year || 9999;
                if (childDeathYear <= subjectDeathYear) {
                    const typeText = c.sex === 'F' ? EVT.daughter_death : EVT.son_death;
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
                        personId: c.id, personSex: c.sex, personBirthYear: c.birth_year, personDeathYear: c.death_year,
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
                            m.marriage_date ? formatDateWithQualifier(m.marriage_date) : _i18nT('dates.approx', null, 'Aprox.') + ' ' + mYear,
                            m.marriage_place ? `${m.marriage_place}` : ''
                        ].filter(Boolean);

                        const spouseName = formatNameWithNickname(m.spouse_name, m.spouse_nickname, m.spouse_given_name, m.spouse_surname) || m.spouse_name;
                        const childName = formatNameWithNickname(c.name, c.nickname, c.given_name, c.surname) || c.name;

                        events.push({
                            year: mYear,
                            age: ageText(mYear),
                            type: c.sex === 'F' ? EVT.daughter_marriage : EVT.son_marriage,
                            lines: lines,
                            photo: m.spouse_photo,
                            name: spouseName,
                            childPhoto: c.photo_file,
                            childId: c.id, childSex: c.sex, childBirthYear: c.birth_year, childDeathYear: c.death_year,
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
                            ageDisplay = ageRangeText(year, endYear);
                        }
                    }
                }

                events.push({
                    year: year,
                    age: ageDisplay || ageText(year),
                    type: EVT.occupation,
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
                            ageDisplay = ageRangeText(year, endYear);
                        }
                    }
                }
                events.push({
                    year: year,
                    age: ageDisplay || ageText(year),
                    type: EVT.residence,
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
                    type: EVT.military,
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
                    type: EVT.anecdote,
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
                    type: evtType(e.type),
                    lines: [
                        formatDateWithQualifier(e.date) || '',
                        e.place || ''
                    ].filter(Boolean),
                    note: e.description || '',  // Store note separately for italic rendering
                    photo: null,
                    name: personName,
                    extraNotes:   e.notes   || [],
                    extraSources: e.sources || [],
                    eventPhotos:  e.photos  || [],
                });
            }
        });
    }

    // Defunción
    if (person.death_year) {
        const personName = formatNameWithNickname(person.name, data.nickname, person.given_name, person.surname) || person.name;
        const deathLines = [formatDateWithQualifier(person.death_date) || `${person.death_year}`];
        if (person.death_place) deathLines.push(person.death_place);
        if (person.death_cause) deathLines.push(`${_i18nT('pages.dossier.cause', null, 'Causa')}: ${person.death_cause}`);

        events.push({
            year: person.death_year,
            age: ageText(person.death_year),
            type: EVT.death,
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
            const year = extractYear(b.date) || person.death_year || null;
            if (year) {
                const lines = [];
                if (b.date) lines.push(formatDateWithQualifier(b.date));
                if (b.place) lines.push(b.place);
                if (b.place_detail) {
                    const details = b.place_detail.split('\n').filter(d => d.trim());
                    lines.push(...details);
                }
                events.push({
                    year: year,
                    age: ageText(year),
                    type: EVT.burial,
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
                    type: EVT.ex_spouse_death,
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
                            photos.push({ name: childName, personId: child.id, photo: child.photo_file, personSex: child.sex, personBirthYear: child.birth_year, personDeathYear: child.death_year });
                        } else {
                            photos.push({ name: childName, personId: child.id, photo: null, personSex: child.sex, personBirthYear: child.birth_year, personDeathYear: child.death_year });
                        }
                        if (partnership.partner_photo) {
                            photos.push({ name: partnerName, photo: partnership.partner_photo });
                        } else {
                            photos.push({ name: partnerName, photo: null });
                        }

                        events.push({
                            year: year,
                            age: ageText(year),
                            type: EVT.child_partnership,
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
        if (a.type === EVT.birth && b.type !== EVT.birth) return -1;
        if (a.type !== EVT.birth && b.type === EVT.birth) return 1;

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
        <button onclick="setTimelineFilter(null)" class="px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors ${timelineFilter === null ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">${_i18nT('common.all', null, 'Todos')}</button>
        ${uniqueTypes.map(type => `
            <button onclick="setTimelineFilter('${type}')" class="px-3 py-1 text-xs font-bold uppercase rounded-full transition-colors ${timelineFilter === type ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">
                ${type}
            </button>
        `).join('')}
    `;

    const html = `
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
            <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
                <span class="material-symbols-outlined">event_note</span>
                ${_i18nT('pages.dossier.timeline_title', null, 'Cronograma Biográfico')}
            </h2>
            <div class="flex gap-2 shrink-0">
                <button onclick="setTimelineMode('graphic')" class="px-4 py-2 text-xs font-bold uppercase rounded-lg transition-colors ${timelineMode === 'graphic' ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">${_i18nT('pages.dossier.mode_graphic', null, 'Gráfico')}</button>
                <button onclick="setTimelineMode('list')" class="px-4 py-2 text-xs font-bold uppercase rounded-lg transition-colors ${timelineMode === 'list' ? 'bg-primary text-white' : 'border border-outline-variant text-outline-variant hover:bg-outline-variant/10'}">${_i18nT('pages.dossier.mode_list', null, 'Lista')}</button>
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
        const thumbDiv = (photo, sex, by, dy, name, id) => {
            const img = photo
                ? `<img class="w-8 h-8 rounded-full object-cover border border-outline-variant/30" src="/photos/${photo}" alt="${name}">`
                : `<div class="w-8 h-8 rounded-full border border-outline-variant/30 bg-surface-container-high flex items-center justify-center flex-shrink-0">${personSvg(sex, by, dy, 20)}</div>`;
            const inner = `${img}<span class="text-sm font-bold">${name}</span>`;
            // Si hay id (familiar del árbol), el chip es un enlace a su dossier.
            return id
                ? `<a href="${_lhref('/dossier.html?id=' + String(id).replace(/@/g, ''))}" class="flex items-center gap-1 hover:opacity-70 transition-opacity" style="text-decoration:none;color:inherit;">${inner}</a>`
                : `<div class="flex items-center gap-1">${inner}</div>`;
        };

        if (e.isChildMarriage) {
            photosHtml = `
                <div class="flex items-center gap-2 mb-3">
                    ${thumbDiv(e.childPhoto, e.childSex, e.childBirthYear, e.childDeathYear, e.childName, e.childId)}
                    <span class="text-xs text-outline mx-1">${_i18nT('common.and', null, 'y')}</span>
                    ${thumbDiv(e.photo, null, null, null, e.name)}
                </div>
            `;
        } else if (e.photos && e.photos.length > 0) {
            photosHtml = `
                <div class="flex items-center gap-3 mb-2">
                    ${e.photos.map(p => thumbDiv(p.photo, p.personSex, p.personBirthYear, p.personDeathYear, p.name, p.personId))
                        .join(`<span class="text-xs text-outline mx-1">${_i18nT('common.and', null, 'y')}</span>`)}
                </div>
            `;
        } else if (e.photo || e.personSex !== undefined) {
            photosHtml = `<div class="flex items-center gap-3 mb-2">${thumbDiv(e.photo, e.personSex, e.personBirthYear, e.personDeathYear, e.name, e.personId)}</div>`;
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
                    ${e.note ? `<div class="text-sm text-outline italic mt-2 pl-3 border-l-2 border-primary/30">${e.note}</div>` : ''}
                    ${(e.extraNotes && e.extraNotes.length > 0)
                        ? e.extraNotes.map(n => `<div class="text-sm text-outline italic mt-2 pl-3 border-l-2 border-primary/30">${n}</div>`).join('')
                        : ''}
                    ${(e.extraSources && e.extraSources.length > 0) ? `
                        <div class="mt-3 space-y-2">
                            ${e.extraSources.map(src => {
                                const quayLabels = _i18nT('pages.dossier.quay_labels', null, ['No fiable','Cuestionable','Evidencia secundaria','Evidencia directa','Primaria y directa']);
                                const quayLabel = (src.quay != null && quayLabels[src.quay]) ? quayLabels[src.quay] : '';
                                return `<div class="text-xs text-outline/70 border-l-2 border-outline-variant pl-2 space-y-0.5">
                                    ${src.source_title ? `<div><span class="font-semibold text-outline">${_i18nT('pages.dossier.source', null, 'Fuente')}:</span> ${src.source_title}</div>` : ''}
                                    ${src.data_text ? `<div><span class="font-semibold text-outline">${_i18nT('pages.dossier.note', null, 'Nota')}:</span> ${src.data_text}</div>` : ''}
                                    ${src.data_date ? `<div><span class="font-semibold text-outline">${_i18nT('common.date', null, 'Fecha')}:</span> ${src.data_date}</div>` : ''}
                                    ${quayLabel ? `<div><span class="font-semibold text-outline">${_i18nT('pages.dossier.reliability', null, 'Fiabilidad')}:</span> ${quayLabel}</div>` : ''}
                                    ${src.page ? `<div><span class="font-semibold text-outline">URL:</span> <a href="${src.page}" target="_blank" rel="noopener" class="underline break-all">${src.page}</a></div>` : ''}
                                </div>`;
                            }).join('')}
                        </div>` : ''}
                    ${(e.eventPhotos && e.eventPhotos.length > 0) ? `
                        <div class="flex gap-4 mt-3 flex-wrap">
                            ${e.eventPhotos.map(ph => `
                                <div class="flex flex-col items-center gap-1" style="max-width:96px">
                                    <img src="/photos/${ph.filename}" title="${(ph.title||'').replace(/"/g,'&quot;')}"
                                        class="h-16 w-16 object-cover rounded cursor-pointer border border-outline-variant/40 hover:opacity-80 transition-opacity"
                                        onclick="openPhotoModal(${ph.id})">
                                    ${ph.title ? `<div class="text-xs text-outline text-center leading-tight">${ph.title}</div>` : ''}
                                </div>`).join('')}
                        </div>` : ''}
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
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">${_i18nT('common.date', null, 'Fecha')}</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">${_i18nT('pages.dossier.event', null, 'Evento')}</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">${_i18nT('pages.dossier.description', null, 'Descripción')}</th>
                        <th class="text-left text-xs font-bold uppercase text-outline px-4 py-3">${_i18nT('pages.dossier.notes', null, 'Notas')}</th>
                    </tr>
                </thead>
                <tbody>
                    ${events.map(e => {
                        const fecha = e.lines[0] || '';
                        const descripcion = e.lines.slice(1).join(' • ') || '';
                        const notaBase = e.note ? `<div class="italic pl-2 border-l-2 border-primary/30">${e.note}</div>` : '';
                        const extraNotesHtml = (e.extraNotes && e.extraNotes.length > 0)
                            ? e.extraNotes.map(n => `<div class="italic mt-1 pl-2 border-l-2 border-primary/30">${n}</div>`).join('')
                            : '';
                        const extraSourcesHtml = (e.extraSources && e.extraSources.length > 0)
                            ? `<div class="mt-1 space-y-1">${e.extraSources.map(src => {
                                const quayLabels = _i18nT('pages.dossier.quay_labels', null, ['No fiable','Cuestionable','Evidencia secundaria','Evidencia directa','Primaria y directa']);
                                const quayLabel = (src.quay != null && quayLabels[src.quay]) ? quayLabels[src.quay] : '';
                                return `<div class="text-xs text-outline/70 pl-2 border-l-2 border-outline-variant space-y-0.5">
                                  ${src.source_title ? `<div><span class="font-semibold">${_i18nT('pages.dossier.source', null, 'Fuente')}:</span> ${src.source_title}</div>` : ''}
                                  ${src.data_text ? `<div><span class="font-semibold">${_i18nT('pages.dossier.note', null, 'Nota')}:</span> ${src.data_text}</div>` : ''}
                                  ${src.data_date ? `<div><span class="font-semibold">${_i18nT('common.date', null, 'Fecha')}:</span> ${src.data_date}</div>` : ''}
                                  ${quayLabel ? `<div><span class="font-semibold">${_i18nT('pages.dossier.reliability', null, 'Fiabilidad')}:</span> ${quayLabel}</div>` : ''}
                                  ${src.page ? `<div><span class="font-semibold">URL:</span> <a href="${src.page}" target="_blank" rel="noopener" class="underline break-all">${src.page}</a></div>` : ''}
                                </div>`;
                              }).join('')}</div>`
                            : '';
                        const eventPhotosHtml = (e.eventPhotos && e.eventPhotos.length > 0)
                            ? `<div class="flex gap-3 mt-1 flex-wrap">${e.eventPhotos.map(ph =>
                                `<div class="flex flex-col items-center gap-0.5" style="max-width:72px">
                                  <img src="/photos/${ph.filename}" title="${(ph.title||'').replace(/"/g,'&quot;')}"
                                    class="h-10 w-10 object-cover rounded cursor-pointer border border-outline-variant/40"
                                    onclick="openPhotoModal(${ph.id})">
                                  ${ph.title ? `<div class="text-xs text-outline text-center leading-tight">${ph.title}</div>` : ''}
                                </div>`).join('')}</div>`
                            : '';
                        return `
                            <tr class="border-b border-outline-variant/20 hover:bg-outline-variant/5 transition-colors" data-type="${e.type}">
                                <td class="px-4 py-3 text-xs whitespace-nowrap font-semibold text-primary">${e.year}</td>
                                <td class="px-4 py-3 font-semibold text-sm">${e.type}</td>
                                <td class="px-4 py-3 text-outline">${descripcion}</td>
                                <td class="px-4 py-3 text-outline">${notaBase}${extraNotesHtml}${extraSourcesHtml}${eventPhotosHtml}</td>
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
                <p class="text-[10px] text-outline font-medium mb-2">${c.date || _i18nT('pages.dossier.unknown_period', null, 'Período desconocido')}</p>
                ${c.place ? `<p class="text-sm font-bold text-on-surface mb-3">${c.place}</p>` : ''}
                <p class="text-xs text-outline">${linkifyCareerText(c.title)}</p>
            </div>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary flex items-center gap-4">
            <span class="material-symbols-outlined">business_center</span>
            ${_i18nT('pages.dossier.career_title', null, 'Trayectoria Profesional')}
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
            <p class="text-[10px] text-outline font-medium mb-2">${e.date || _i18nT('pages.dossier.unknown_period', null, 'Período desconocido')}</p>
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
            ${_i18nT('pages.dossier.education_title', null, 'Estudios')}
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
            source_type: e.type ? _i18nT('event_types.' + e.type, null, e.type) : '',
        }));

    // Birth place — always first, before any sort
    const birthEntry = (person?.birth_place || person?.birth_city) ? [{
        date: person.birth_date || '',
        address: person.birth_place || person.birth_city || '',
        city: person.birth_city || '',
        country: '',
        lat: null,
        lng: null,
        note: '',
        source_type: _i18nT('common.birth', null, 'Nacimiento'),
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
            ${houseIcon} ${_i18nT('pages.dossier.residences_title', null, 'Domicilios')}
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
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> © <a href="https://carto.com/">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19,
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

function renderBurialNiche(niche) {
    const section = document.getElementById('burial-niche-section');
    if (!niche) {
        section.style.display = 'none';
        return;
    }
    section.style.display = 'block';

    const kindLabel = {
        photo: _i18nT('pages.dossier.niche', null, 'Nicho'),
        record: _i18nT('pages.dossier.record', null, 'Registro')
    };
    const photos = niche.photos || [];
    const modalTitle = (niche.title || niche.name || '').replace(/'/g, "\\'");
    const photosHtml = photos.length ? `
        <div class="flex gap-3 mt-4 flex-wrap">
            ${photos.map(p => `
                <figure class="cursor-pointer" onclick="openPhotoModalUrl('/cemetery_photos/${p.filename}', { title: '${modalTitle}', place: '${(niche.cemetery_name || '').replace(/'/g, "\\'")}', note: '${kindLabel[p.kind] || ''}' })">
                    <img src="/cemetery_photos/${p.filename}" alt="${kindLabel[p.kind] || 'Foto'}"
                         class="w-32 h-24 object-cover rounded-lg border border-outline-variant/30 hover:opacity-90"/>
                    <figcaption class="text-[10px] uppercase tracking-wider text-outline mt-1">${kindLabel[p.kind] || ''}</figcaption>
                </figure>`).join('')}
        </div>` : '';

    section.innerHTML = `
        <h3 class="font-headline text-2xl text-primary flex items-center gap-3 mb-6">
            <img src="/icons/cementerio.svg" class="w-7 h-7" alt=""/>
            ${_i18nT('common.burial', null, 'Sepultura')}
        </h3>
        <div class="p-8 bg-surface-container-high rounded-xl border-l-8 border-primary relative overflow-hidden">
            <div class="absolute -right-8 -bottom-8 opacity-5">
                <img src="/icons/cementerio.svg" style="width:9rem;height:9rem;" alt=""/>
            </div>
            <div class="relative">
                <p class="font-bold text-lg">${niche.cemetery_name}${niche.cemetery_city ? ` <span class="font-normal text-on-surface/70">· ${niche.cemetery_city}</span>` : ''}</p>
                ${niche.title ? `<p class="text-base mt-1 font-semibold text-on-surface/90">${niche.title}</p>` : ''}
                <p class="text-sm mt-1 text-on-surface/80">${niche.name}</p>
                ${niche.notes ? `<p class="text-sm mt-2 italic text-on-surface/70">${niche.notes}</p>` : ''}
                ${photosHtml}
                <a href="${_lhref('/cementerios.html?niche=' + niche.id)}"
                   class="inline-flex items-center gap-1.5 mt-5 bg-primary text-on-primary px-4 py-2 rounded-full text-xs font-extrabold uppercase tracking-wide hover:bg-primary/90">
                    <span class="material-symbols-outlined text-[16px]">map</span>
                    ${_i18nT('pages.dossier.view_on_map', null, 'Ver en el mapa')}
                </a>
            </div>
        </div>
    `;
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
            ${_i18nT('pages.dossier.military_title', null, 'Actividad Militar')}
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
                <div class="absolute top-0 right-0 p-4 text-[10px] font-bold text-outline">${_i18nT('pages.dossier.note_label', {n: i+1}, 'NOTA {n}')}</div>
                <div class="space-y-6 text-lg italic leading-relaxed opacity-90">
                    <p>${formatted}</p>
                </div>
            </article>
        `;
    }).join('');

    const html = `
        <h2 class="font-headline text-3xl text-primary border-b border-outline-variant pb-4 italic">${_i18nT('pages.dossier.notes_title', null, 'Notas Biográficas')}</h2>
        <div class="space-y-12">${articles}</div>
    `;
    document.getElementById('notes-section').innerHTML = html;
}

document.addEventListener('DOMContentLoaded', loadDossier);
