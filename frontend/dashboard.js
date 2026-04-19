const MONTHS_ES = [
    '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'
];

/**
 * Format person name with nickname if available
 */
function formatNameWithNickname(name, nickname, given_name, surname) {
    if (!nickname) return name;
    if (given_name && surname) {
        return `${given_name} "${nickname}" ${surname}`;
    }
    const parts = name.trim().split(' ');
    if (parts.length < 2) return name;
    const surnameFromName = parts.pop();
    const givenNames = parts.join(' ');
    return `${givenNames} "${nickname}" ${surnameFromName}`;
}

function dossierId(id) {
    return id ? id.replace(/@/g, '') : '';
}

const BRANCH_LINKS = {
    'Godes Molina': '/godes_molina.html',
    'Garrido Godes': '/garrido_godes.html',
    'Godes Maté': '/godes_mate.html',
};

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
        const disabled = href === '#' ? ' opacity-50 cursor-not-allowed' : ' hover:bg-surface-dim';
        return `
        <a href="${href}" class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm text-on-surface transition-colors${disabled}${i === 0 ? ' bg-surface-dim font-semibold' : ''}">
            <span class="material-symbols-outlined text-primary text-lg">family_history</span>
            <span class="flex-1 font-medium">${b.surname}</span>
            <span class="text-xs text-on-surface-variant/60 font-semibold">${b.count}</span>
        </a>`;
    }).join('');
}

function renderBirthdays(birthdays) {
    const container = document.getElementById('birthdays-list');
    const alive_birthdays = birthdays.filter(b => b.is_alive);
    if (!alive_birthdays.length) {
        container.innerHTML = '<p class="text-sm text-on-surface-variant italic">No hay aniversarios esta semana</p>';
        return;
    }
    container.innerHTML = alive_birthdays.slice(0, 5).map(b => {
        const monthLabel = MONTHS_ES[b.birth_month] || '';
        const isToday = b.is_today;
        const displayName = formatNameWithNickname(b.name, b.nickname, b.given_name, b.surname);
        const pid = dossierId(b.id);
        const todayBg = isToday ? 'bg-secondary-container' : 'bg-surface-dim';

        const mailIcon = `<a href="mailto:?subject=Felicidades ${encodeURIComponent(displayName)}&body=${encodeURIComponent('¡Feliz cumpleaños, ' + displayName + '!')}"
            class="flex-shrink-0 text-on-surface-variant hover:text-primary transition-colors" title="Enviar felicitación">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
                <path d="M2 6L8.91302 9.91697C11.4616 11.361 12.5384 11.361 15.087 9.91697L22 6" />
                <path d="M2.01577 13.4756C2.08114 16.5412 2.11383 18.0739 3.24496 19.2094C4.37608 20.3448 5.95033 20.3843 9.09883 20.4634C11.0393 20.5122 12.9607 20.5122 14.9012 20.4634C18.0497 20.3843 19.6239 20.3448 20.7551 19.2094C21.8862 18.0739 21.9189 16.5412 21.9842 13.4756C22.0053 12.4899 22.0053 11.5101 21.9842 10.5244C21.9189 7.45886 21.8862 5.92609 20.7551 4.79066C19.6239 3.65523 18.0497 3.61568 14.9012 3.53657C12.9607 3.48781 11.0393 3.48781 9.09882 3.53656C5.95033 3.61566 4.37608 3.65521 3.24495 4.79065C2.11382 5.92608 2.08114 7.45885 2.01576 10.5244C1.99474 11.5101 1.99475 12.4899 2.01577 13.4756Z" />
            </svg>
        </a>`;

        return `
        <div class="flex items-center gap-4">
            <div class="w-14 h-14 rounded-full ${todayBg} flex flex-col items-center justify-center flex-shrink-0">
                <span class="text-[0.6rem] font-bold uppercase text-on-surface-variant">${monthLabel}</span>
                <span class="font-headline text-xl leading-none text-on-surface">${b.birth_day}</span>
            </div>
            <div class="flex-1 min-w-0">
                <a href="/dossier.html?id=${pid}" class="font-semibold text-sm text-on-surface hover:text-primary transition-colors">
                    ${displayName}${b.age ? ' <span class="font-normal text-on-surface-variant">(' + b.age + ' años)</span>' : ''}
                </a>
            </div>
            ${mailIcon}
            ${b.photo ? `<a href="/dossier.html?id=${pid}"><img class="w-10 h-10 rounded-full object-cover flex-shrink-0" src="/photos/${b.photo}" alt="${displayName}"></a>` : ''}
        </div>`;
    }).join('');
}

function renderPhotos(photos) {
    const container = document.getElementById('photos-gallery');
    if (!photos.length) {
        container.innerHTML = '<p class="text-sm text-on-surface-variant italic">No hay fotografías disponibles</p>';
        return;
    }
    container.innerHTML = photos.map((p) => {
        const title = p.title || 'Fotografía';
        const year = p.date || '';
        const place = p.place || '';
        return `
        <div class="flex flex-col cursor-pointer transition-transform hover:-translate-y-1" onclick="openPhotoModal(${p.photo_id})">
            <img src="/photos/${p.photo}" alt="${title}" loading="lazy"
                 class="w-full aspect-[3/4] object-cover rounded-lg mb-3 shadow-md hover:scale-[1.02] transition-transform">
            <div class="px-1">
                <h4 class="font-headline text-sm text-primary font-semibold leading-tight line-clamp-2">${title}</h4>
                <p class="text-[0.7rem] text-on-surface-variant mt-1">${[year, place].filter(Boolean).join(' \u2022 ')}</p>
            </div>
        </div>`;
    }).join('');
}

function renderFeatured(featured) {
    const container = document.getElementById('featured-list');
    container.innerHTML = featured.map(p => {
        const birth = p.birth_year || '';
        const death = p.death_year || '';
        let years;
        if (birth && death) years = `${birth} - ${death}`;
        else if (birth && !death && !p.is_alive) years = `${birth} - ?`;
        else if (birth) years = `${birth}`;
        else years = '?';
        const pid = dossierId(p.id);
        const displayName = formatNameWithNickname(p.name, p.nickname, p.given_name, p.surname);

        // Build description line: birth date, parents
        let descParts = [];
        if (p.birth_date) descParts.push(`nacido/a el ${p.birth_date}`);
        if (p.father_name || p.mother_name) {
            const parents = [p.father_name, p.mother_name].filter(Boolean).join(' y ');
            descParts.push(`hijo/a de ${parents}`);
        }
        const descLine = descParts.length ? descParts.join(', ') : '';

        return `
        <a href="/dossier.html?id=${pid}" class="flex items-center gap-4 p-4 rounded-2xl text-on-surface hover:bg-surface-container-low transition-colors">
            ${p.photo_file
                ? `<img class="w-12 h-12 rounded-full object-cover flex-shrink-0" src="/photos/${p.photo_file}" alt="${displayName}">`
                : `<div class="w-12 h-12 rounded-full bg-surface-container-high flex items-center justify-center flex-shrink-0 text-secondary"><span class="material-symbols-outlined">person</span></div>`
            }
            <div class="min-w-0">
                <p class="font-semibold text-sm">${displayName}</p>
                <p class="text-xs text-on-surface-variant">${years}</p>
                ${descLine ? `<p class="text-xs text-on-surface-variant/70 mt-0.5">${descLine}</p>` : ''}
            </div>
        </a>`;
    }).join('');
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-gallery');
    if (!documents || !documents.length) {
        container.innerHTML = '<p class="text-sm text-on-surface-variant italic">No hay documentos disponibles</p>';
        return;
    }

    const docLabels = {
        'bautismo': 'Bautismo', 'matrimonio': 'Matrimonio', 'defuncion': 'Defunción',
        'nacimiento': 'Nacimiento', 'certificat': 'Certificado', 'padro': 'Padrón',
        'testament': 'Testamento', 'arbre': 'Árbol', 'transcripcio': 'Transcripción',
        'poema': 'Poema', 'invitacio': 'Invitación', 'carta': 'Carta',
        'dibuix': 'Dibujo', 'biografia': 'Biografía', 'document': 'Documento',
        'cementerio': 'Cementerio', 'obituario': 'Obituario',
    };

    const d = documents[0];
    const caption = d.title || 'Documento';
    // Extract doc type from [Type] in title
    const typeMatch = caption.match(/\[([^\]]+)\]/);
    const docType = typeMatch ? typeMatch[1].toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '') : '';
    const typeLabel = docLabels[docType] || docType || 'Documento';
    const cleanTitle = caption.replace(/\s*\[[^\]]+\]\s*/g, '').trim();

    container.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 gap-10 items-start cursor-pointer" onclick="openPhotoModal(${d.id})">
            <div class="w-full rounded-lg overflow-hidden bg-surface-container-high">
                <img src="/photos/${d.filename}" alt="${cleanTitle}" loading="lazy"
                     class="w-full h-auto object-contain">
            </div>
            <div class="flex flex-col gap-4">
                <h4 class="font-headline text-xl text-primary font-semibold leading-tight">${cleanTitle}</h4>
                <div class="flex flex-wrap gap-2">
                    ${docType ? `<span class="text-[0.65rem] text-white bg-secondary px-2.5 py-1 rounded font-bold uppercase tracking-wide">${typeLabel}</span>` : ''}
                    ${d.date ? `<span class="text-xs text-on-surface-variant bg-surface-container-high px-2.5 py-1 rounded font-medium">${d.date}</span>` : ''}
                </div>
                ${d.transcription ? `<p class="text-sm text-on-surface leading-relaxed pt-4 border-t border-surface-dim">${d.transcription}</p>` : ''}
            </div>
        </div>`;
}

// Hero search
function doSearch() {
    const q = document.getElementById('hero-query').value.trim();
    if (q) {
        if (window.smartSearch) {
            window.smartSearch(q);
        } else {
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

// Sidebar centering: match the dash-main centering logic
function adjustLayout() {
    const main = document.getElementById('dash-main');
    const sidebar = document.getElementById('sidebar');
    if (window.innerWidth >= 1024) {
        // Center content in space right of sidebar
        const half = window.innerWidth / 2;
        const marginLeft = Math.max(260, half - 470);
        main.style.marginLeft = marginLeft + 'px';
        main.style.marginRight = 'auto';
        main.style.maxWidth = '1200px';
    } else {
        main.style.marginLeft = '0';
        main.style.marginRight = 'auto';
        main.style.maxWidth = '';
    }
}

window.addEventListener('resize', adjustLayout);
adjustLayout();

loadDashboard();
