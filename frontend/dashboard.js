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

const MONTHS_ES = [
    '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
];

const BRANCH_LINKS = {
    'Godes Molina': '/godes_molina.html',
    'Garrido Godes': '/garrido_godes.html',
    'Godes Maté': '/godes_mate.html',
    'Godes Diago': '/godes_diago.html',
    'Cabestany Godes': '/cabestany_godes.html',
    'Godes Faura': '/godes_faura.html',
    'Puig Godes': '/puig_godes.html',
    'Garrido Godes': '/garrido_godes.html',
    'Godes Maté': '/godes_mate.html',
    'Godes Hospital': '/godes_hospital.html',
    'Millán Godes': '/millan_godes.html',
    'Godes Schmid': '/godes_schmid.html',
    'Nolla Godes': '/nolla_godes.html',
    'Godes Terrats': '/godes_terrats.html',
    'Mestre Godes': '/mestre_godes.html',
    'Pujol Godes': '/pujol_godes.html',
    'Pujol Pérez': '/pujol_perez.html',
    'Godes Hurtado': '/godes_hurtado.html',
    'Godes Güell': '/godes_guell.html',
};

function dossierId(id) { return id ? id.replace(/@/g, '') : ''; }

/**
 * Format person name with nickname if available
 * Example: given_name "Josep Maria", surname "Godes Hurtado", nickname "Bep" -> 'Josep Maria "Bep" Godes Hurtado'
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

async function loadDashboard() {
    try {
        const res = await fetch('/api/dashboard');
        const data = await res.json();
        renderStats(data.stats);
        renderBranches(data.branches);
        renderBirthdays(data.birthdays);
        renderAnecdota(data.anecdota);
        renderInMemoriam(data.in_memoriam);
        renderPhotos(data.photos);
        renderFeatured(data.featured);
        renderRecentlyUpdated(data.recently_updated);
        renderDocuments(data.documents);
    } catch (e) {
        console.error('Error loading dashboard:', e);
    }
}

function renderStats(stats) {
    document.getElementById('stat-people').textContent = stats.total_people;
    document.getElementById('stat-families').textContent = stats.total_families;
    document.getElementById('stat-alive').textContent = stats.alive;
    document.getElementById('stat-photos').textContent = stats.photos_count;
    document.getElementById('stat-years').textContent = stats.years_span;
    document.getElementById('stat-updated').textContent = stats.last_updated;
}

function renderBranches(branches) {
    const container = document.getElementById('sidebar-branches');
    container.innerHTML = branches.map((b, i) => {
        const href = BRANCH_LINKS[b.surname] || '#';
        const cls = href === '#' ? 'branch-link disabled' : 'branch-link';
        return `
        <a href="${href}" class="${cls}${i === 0 ? ' active' : ''}"${href === '#' ? ' style="opacity:0.5;pointer-events:none"' : ''}>
            <span class="material-symbols-outlined branch-icon">family_history</span>
            <span class="branch-name">${b.surname}</span>
            <span class="branch-count">${b.count}</span>
        </a>`;
    }).join('');
}

function renderBirthdays(birthdays) {
    const container = document.getElementById('birthdays-list');
    const alive_birthdays = birthdays.filter(b => b.is_alive);
    if (!alive_birthdays.length) {
        container.innerHTML = '<p class="no-data">No hay aniversarios esta semana</p>';
        return;
    }
    container.innerHTML = alive_birthdays.slice(0, 5).map(b => {
        const monthLabel = MONTHS_ES[b.birth_month] || '';
        const isToday = b.is_today;
        const displayName = formatNameWithNickname(b.name, b.nickname, b.given_name, b.surname);
        const pid = dossierId(b.id);
        const mailIcon = `<a href="mailto:?subject=${encodeURIComponent('Felicidades ' + displayName)}&body=${encodeURIComponent('¡Feliz cumpleaños, ' + displayName + '!')}" class="anniversary-mail" title="Enviar felicitación" style="color:var(--on-surface-variant);flex-shrink:0;display:flex;align-items:center;">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
                <path d="M2 6L8.91302 9.91697C11.4616 11.361 12.5384 11.361 15.087 9.91697L22 6" />
                <path d="M2.01577 13.4756C2.08114 16.5412 2.11383 18.0739 3.24496 19.2094C4.37608 20.3448 5.95033 20.3843 9.09883 20.4634C11.0393 20.5122 12.9607 20.5122 14.9012 20.4634C18.0497 20.3843 19.6239 20.3448 20.7551 19.2094C21.8862 18.0739 21.9189 16.5412 21.9842 13.4756C22.0053 12.4899 22.0053 11.5101 21.9842 10.5244C21.9189 7.45886 21.8862 5.92609 20.7551 4.79066C19.6239 3.65523 18.0497 3.61568 14.9012 3.53657C12.9607 3.48781 11.0393 3.48781 9.09882 3.53656C5.95033 3.61566 4.37608 3.65521 3.24495 4.79065C2.11382 5.92608 2.08114 7.45885 2.01576 10.5244C1.99474 11.5101 1.99475 12.4899 2.01577 13.4756Z" />
            </svg>
        </a>`;
        return `
        <div class="anniversary-row">
            <div class="anniversary-date${isToday ? ' today' : ''}">
                <span class="anniversary-month">${monthLabel}</span>
                <span class="anniversary-day">${b.birth_day}</span>
            </div>
            <div class="anniversary-info">
                <p class="anniversary-name"><a href="/dossier.html?id=${pid}" style="color:inherit;text-decoration:none">${displayName}</a>${b.age ? ' (' + b.age + ' años)' : ''}</p>
            </div>
            ${mailIcon}
            ${b.photo
                ? `<a href="/dossier.html?id=${pid}"><img class="anniversary-photo" src="/photos/${b.photo}" alt="${displayName}"></a>`
                : `<a href="/dossier.html?id=${pid}" style="display:flex;align-items:center;justify-content:center;width:36px;height:36px;border-radius:50%;background:var(--surface-container-high);border:1px solid var(--outline-variant);flex-shrink:0;">${personSvg(b.sex, b.birth_year, b.death_year, 22)}</a>`
            }
        </div>`;
    }).join('');
}

function renderPhotos(photos) {
    const container = document.getElementById('photos-gallery');
    if (!photos.length) {
        container.innerHTML = '<p class="no-data">No hay fotografías disponibles</p>';
        return;
    }
    container.innerHTML = photos.map((p) => {
        const title = p.title || 'Fotografía';
        const year = p.date || '';
        const place = p.place || '';
        return `
        <div class="photo-card-full" onclick="openPhotoModal(${p.photo_id})" style="cursor: pointer;">
            <img src="/photos/${p.photo}" alt="${title}" loading="lazy">
            <div class="photo-card-info">
                <h4 class="line-clamp-2">${title}</h4>
                <p class="photo-meta">${[year, place].filter(Boolean).join(' • ')}</p>
            </div>
        </div>`;
    }).join('');

    // Add link to see all photos
    const link = document.createElement('div');
    link.className = 'photos-see-all';
    link.innerHTML = '<a href="/albums.html#__all__">Ver todas las fotografías →</a>';
    container.parentElement.appendChild(link);
}

function renderRecentlyUpdated(people) {
    const container = document.getElementById('recently-updated-list');
    if (!container || !people || !people.length) return;
    container.innerHTML = people.map(p => {
        const pid = dossierId(p.id);
        const displayName = formatNameWithNickname(p.name, p.nickname, p.given_name, p.surname);
        const birth = p.birth_year || '';
        const death = p.death_year || '';
        const years = [birth, death].filter(Boolean).join(' – ') || '';
        return `
        <a href="/dossier.html?id=${pid}" class="featured-member" style="text-decoration:none;">
            ${p.photo_file
                ? `<img src="/photos/${p.photo_file}" alt="${displayName}"
                        style="width:56px;height:56px;border-radius:8px;object-fit:cover;flex-shrink:0;">`
                : `<div class="featured-no-photo" style="width:56px;height:56px;border-radius:8px;flex-shrink:0;">${personSvg(p.sex, p.birth_year, p.death_year, 30)}</div>`
            }
            <div class="featured-info">
                <p style="font-size:0.6rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:var(--secondary);margin:0 0 2px 0;">Datos actualizados · ${p.updated_at_display}</p>
                <p class="featured-name">${displayName}</p>
                ${years ? `<p class="featured-years">${years}</p>` : ''}
            </div>
        </a>`;
    }).join('');
}

function renderFeatured(featured) {
    const container = document.getElementById('featured-list');
    container.innerHTML = featured.map(p => {
        const birth = p.birth_year || '';
        const death = p.death_year || '';
        const years = [birth, death].filter(Boolean).join(' - ') || '?';
        const pid = dossierId(p.id);
        const displayName = formatNameWithNickname(p.name, p.nickname, p.given_name, p.surname);
        const birthDate = p.birth_date || '';
        const parents = [p.father_name, p.mother_name].filter(Boolean).join(' y ');
        const descParts = [];
        if (birthDate) descParts.push(`Nacido: ${birthDate}`);
        if (parents) descParts.push(`Padres: ${parents}`);
        const descLine = descParts.join(' · ');
        return `
        <a href="/dossier.html?id=${pid}" class="featured-member">
            ${p.photo_file
                ? `<img class="featured-photo" src="/photos/${p.photo_file}" alt="${displayName}">`
                : `<div class="featured-no-photo">${personSvg(p.sex, p.birth_year, p.death_year, 30)}</div>`
            }
            <div class="featured-info">
                <p class="featured-name">${displayName}</p>
                <p class="featured-years">${years}</p>
                ${descLine ? `<p class="featured-desc">${descLine}</p>` : ''}
            </div>
        </a>`;
    }).join('');
}

function renderAnecdota(a) {
    const section = document.getElementById('anecdota-section');
    if (!a) return;
    const ctaName = a.cta && a.cta.includes('sobre ') ? a.cta.split('sobre ')[1] : null;
    const infoIcon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="text-secondary shrink-0 mt-0.5"><circle cx="12" cy="12" r="10"/><path d="M12 16V12"/><path d="M12.125 8.25H12M12.25 8.25C12.25 8.11193 12.1381 8 12 8C11.8619 8 11.75 8.11193 11.75 8.25C11.75 8.38807 11.8619 8.5 12 8.5C12.1381 8.5 12.25 8.38807 12.25 8.25Z"/></svg>`;
    section.innerHTML = `
        <div class="flex items-start gap-4 bg-surface-container rounded-2xl px-6 py-5 border border-outline-variant/20">
            ${infoIcon}
            <div class="flex-1 min-w-0">
                <p class="text-[0.65rem] uppercase tracking-[0.18em] font-extrabold text-secondary mb-1">Anécdotas familiares</p>
                <p class="font-serif text-[1.05rem] text-on-surface leading-snug mb-2">${a.titulo}</p>
                <p class="text-[0.88rem] text-on-surface-variant leading-relaxed mb-3">${a.texto}</p>
                <div class="flex items-center justify-between mt-1">
                    ${ctaName ? `<a id="anecdota-cta" href="/chat.html?q=${encodeURIComponent(ctaName)}" style="text-decoration:none;" class="text-[0.8rem] font-bold text-primary">${a.cta} →</a>` : '<span></span>'}
                    <a id="anecdota-colaborar" href="/colaborar.html?type=anecdota" style="text-decoration:none;" class="text-[0.8rem] font-bold text-secondary">Colabora →</a>
                </div>
            </div>
        </div>`;
    section.classList.remove('hidden');
    // Try to resolve person name → dossier link + enrich colaborar link with person id
    if (ctaName) {
        fetch(`/api/search?q=${encodeURIComponent(ctaName)}&limit=1`)
            .then(r => r.json())
            .then(data => {
                const match = data.results && data.results[0];
                if (match) {
                    const cta = document.getElementById('anecdota-cta');
                    if (cta) cta.href = `/dossier.html?id=${dossierId(match.id)}`;
                    const col = document.getElementById('anecdota-colaborar');
                    if (col) col.href = `/colaborar.html?type=anecdota&person=${dossierId(match.id)}`;
                }
            })
            .catch(() => {});
    }
}

function renderInMemoriam(people) {
    const container = document.getElementById('in-memoriam-list');
    if (!people || !people.length) return;
    container.innerHTML = people.map(p => {
        const years = [p.birth_year, p.death_year].filter(Boolean).join('–');
        const pid = dossierId(p.id);
        const displayName = formatNameWithNickname(p.name, p.nickname, p.given_name, p.surname);
        const deathInfo = [p.death_date, p.death_place ? p.death_place.split(',')[0].trim() : null].filter(Boolean).join(' · ');
        const photoEl = p.photo_file
            ? `<img src="/photos/${p.photo_file}" alt="${displayName}"
                    class="shrink-0 object-cover"
                    style="width:48px;height:64px;border-radius:6px;filter:grayscale(15%);">`
            : `<div class="featured-no-photo shrink-0" style="border-radius:6px;width:48px;height:64px;">${personSvg(p.sex, p.birth_year, p.death_year, 28)}</div>`;
        return `
        <a href="/dossier.html?id=${pid}" class="featured-member items-start" style="opacity:0.92; text-decoration:none;">
            ${photoEl}
            <div class="featured-info">
                <p class="text-[0.55rem] uppercase tracking-widest text-outline font-bold mb-0.5 italic">In Memoriam</p>
                <p class="featured-name">${displayName}</p>
                <p class="featured-years">${years}</p>
                ${deathInfo ? `<p class="featured-desc">${deathInfo}</p>` : ''}
            </div>
        </a>`;
    }).join('');
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-gallery');
    if (!documents || !documents.length) {
        container.innerHTML = '<p class="no-data">No hay documentos disponibles</p>';
        return;
    }

    const docIconMap = {
        'nacimiento':    '/icons/nacimiento.svg',
        'naixement':     '/icons/nacimiento.svg',
        'matrimonio':    '/icons/matrimonio.svg',
        'matrimoni':     '/icons/matrimonio.svg',
        'defunción':     '/icons/defuncion.svg',
        'defuncio':      '/icons/defuncion.svg',
        'bautismo':      '/icons/bautismo.svg',
        'bautisme':      '/icons/bautismo.svg',
        'obituario':     '/icons/obituario.svg',
        'obituari':      '/icons/obituario.svg',
        'cementerio':    '/icons/cementerio.svg',
        'documentación': '/icons/documentacion.svg',
        'documentacio':  '/icons/documentacion.svg',
        'documento':     '/icons/documentacion.svg',
        'certificado':   '/icons/documentacion.svg',
        'certificat':    '/icons/documentacion.svg',
        'biografia':     '/icons/biografia.svg',
        'padrón':        '/icons/padron.svg',
        'padro':         '/icons/padron.svg',
        'carta':         '/icons/carta.svg',
        'testamento':    '/icons/carta.svg',
        'testament':     '/icons/carta.svg',
        'diversos':      '/icons/diversos.svg',
        'militar':       '/icons/militar.svg',
    };

    const d = documents[0];
    // Extract [Type] from title if present
    const rawCaption = d.title || 'Documento';
    const typeMatch = rawCaption.match(/\[([^\]]+)\]/);
    const docType = typeMatch ? typeMatch[1].toLowerCase() : '';
    const caption = rawCaption.replace(/\s*\[.*?\]\s*/g, '').trim();
    const typeLabel = docType ? docType.charAt(0).toUpperCase() + docType.slice(1) : '';
    const iconPath = docIconMap[docType] || '/icons/documentacion.svg';

    container.innerHTML = `
        <div class="document-single" onclick="openPhotoModal(${d.id})" style="cursor:pointer;">
            <div class="document-image-half">
                <img src="/photos/${d.filename}" alt="${caption}" loading="lazy">
            </div>
            <div class="document-content-full">
                <h4 class="document-title">${caption}</h4>
                <div class="document-meta">
                    ${typeLabel ? `<span class="doc-badge"><img src="${iconPath}" alt="${typeLabel}" class="doc-badge-icon"> ${typeLabel}</span>` : ''}
                    ${d.date ? `<span class="doc-date">${d.date}</span>` : ''}
                </div>
            </div>
        </div>`;

    // Add link to see all documents
    const link = document.createElement('div');
    link.className = 'documents-see-all';
    link.innerHTML = '<a href="/docs.html">Ver todos los documentos →</a>';
    container.parentElement.appendChild(link);
}

// Hero search: smart routing (dossier if person, chat if question)
function doSearch() {
    const q = document.getElementById('hero-query').value.trim();
    if (q) {
        // Wait for nav.js to load smartSearch
        if (window.smartSearch) {
            window.smartSearch(q);
        } else {
            // Fallback to chat if nav.js not loaded yet
            window.location.href = '/chat.html?q=' + encodeURIComponent(q);
        }
    }
}

document.getElementById('hero-send').addEventListener('click', doSearch);
document.getElementById('hero-query').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
});

document.querySelectorAll('.hero-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        const q = chip.dataset.q;
        if (window.smartSearch) {
            window.smartSearch(q);
        } else {
            window.location.href = '/chat.html?q=' + encodeURIComponent(q);
        }
    });
});

loadDashboard();
