const MONTHS_ES = [
    '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
];

const BRANCH_LINKS = {
    'Godes Molina': '/godes_molina.html',
    'Garrido Godes': '/garrido_godes.html',
    'Godes Maté': '/godes_mate.html',
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
        renderPhotos(data.photos);
        renderFeatured(data.featured);
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
            ${b.photo ? `<a href="/dossier.html?id=${pid}"><img class="anniversary-photo" src="/photos/${b.photo}" alt="${displayName}"></a>` : ''}
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
    link.innerHTML = '<a href="/tree.html">Ver todas las fotografías →</a>';
    container.parentElement.appendChild(link);
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
                : `<div class="featured-no-photo"><span class="material-symbols-outlined">person</span></div>`
            }
            <div class="featured-info">
                <p class="featured-name">${displayName}</p>
                <p class="featured-years">${years}</p>
                ${descLine ? `<p class="featured-desc">${descLine}</p>` : ''}
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

    const docLabels = {
        'bautisme': 'Bautismo',
        'matrimoni': 'Matrimonio',
        'defuncio': 'Defunción',
        'naixement': 'Nacimiento',
        'certificat': 'Certificado',
        'padro': 'Padrón',
        'testament': 'Testamento',
        'arbre': 'Árbol',
        'transcripcio': 'Transcripción',
        'poema': 'Poema',
        'invitacio': 'Invitación',
        'carta': 'Carta',
        'dibuix': 'Dibujo',
        'biografia': 'Biografía',
        'document': 'Documento'
    };

    const d = documents[0];
    // Extract [Type] prefix from title if present
    const rawCaption = d.title || 'Documento';
    const typeMatch = rawCaption.match(/^\[([^\]]+)\]/);
    const docType = typeMatch ? typeMatch[1].toLowerCase() : '';
    const caption = rawCaption.replace(/^\[.*?\]\s*/, '');
    const typeLabel = docLabels[docType] || (docType || '');

    container.innerHTML = `
        <div class="document-single" onclick="openPhotoModal(${d.id})" style="cursor:pointer;">
            <div class="document-image-half">
                <img src="/photos/${d.filename}" alt="${caption}" loading="lazy">
            </div>
            <div class="document-content-full">
                <h4 class="document-title">${caption}</h4>
                <div class="document-meta">
                    ${typeLabel ? `<span class="doc-badge">${typeLabel}</span>` : ''}
                    ${d.date ? `<span class="doc-date">${d.date}</span>` : ''}
                </div>
            </div>
        </div>`;

    // Add link to see all documents
    const link = document.createElement('div');
    link.className = 'documents-see-all';
    link.innerHTML = '<a href="/arxiu.html">Ver todos los documentos →</a>';
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
