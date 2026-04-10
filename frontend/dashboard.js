const MONTHS_CA = [
    '', 'Gen', 'Feb', 'Mar', 'Abr', 'Mai', 'Jun',
    'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Des'
];

/**
 * Format person name with nickname if available
 * Example: "Josep Maria Godes Hurtado" + nickname "Bep" -> 'Josep Maria "Bep" Godes Hurtado'
 */
function formatNameWithNickname(name, nickname) {
    if (!nickname) return name;
    const parts = name.trim().split(' ');
    if (parts.length < 2) return name;
    const surname = parts.pop();
    const givenNames = parts.join(' ');
    return `${givenNames} "${nickname}" ${surname}`;
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
    container.innerHTML = branches.map((b, i) => `
        <a href="/tree.html" class="branch-link${i === 0 ? ' active' : ''}">
            <span class="material-symbols-outlined branch-icon">family_history</span>
            <span class="branch-name">${b.surname}</span>
            <span class="branch-count">${b.count}</span>
        </a>
    `).join('');
}

function renderBirthdays(birthdays) {
    const container = document.getElementById('birthdays-list');
    const alive_birthdays = birthdays.filter(b => b.is_alive);
    if (!alive_birthdays.length) {
        container.innerHTML = '<p class="no-data">Cap aniversari aquesta setmana</p>';
        return;
    }
    container.innerHTML = alive_birthdays.slice(0, 5).map(b => {
        const monthLabel = MONTHS_CA[b.birth_month] || '';
        const isToday = b.is_today;
        const displayName = formatNameWithNickname(b.name, b.nickname);
        return `
        <div class="anniversary-row">
            <div class="anniversary-date${isToday ? ' today' : ''}">
                <span class="anniversary-month">${monthLabel}</span>
                <span class="anniversary-day">${b.birth_day}</span>
            </div>
            <div class="anniversary-info">
                <p class="anniversary-name">${displayName}${b.age ? ' (' + b.age + ' anys)' : ''}</p>
            </div>
            ${b.photo ? `<img class="anniversary-photo" src="/photos/${b.photo}" alt="${displayName}">` : ''}
        </div>`;
    }).join('');
}

function renderPhotos(photos) {
    const container = document.getElementById('photos-gallery');
    if (!photos.length) {
        container.innerHTML = '<p class="no-data">Cap fotografia disponible</p>';
        return;
    }
    container.innerHTML = photos.map((p) => {
        const title = p.title || 'Fotografia';
        const year = p.date || '';
        const place = p.place || '';
        return `
        <div class="photo-card-full" onclick="openPhotoModal(${p.photo_id})" style="cursor: pointer;">
            <img src="/photos/${p.photo}" alt="${title}" loading="lazy">
            <div class="photo-card-info">
                <h4>${title}</h4>
                <p class="photo-meta">${[year, place].filter(Boolean).join(' • ')}</p>
            </div>
        </div>`;
    }).join('');

    // Add link to see all photos
    const link = document.createElement('div');
    link.className = 'photos-see-all';
    link.innerHTML = '<a href="/tree.html">Ver totes les fotografies →</a>';
    container.parentElement.appendChild(link);
}

function renderFeatured(featured) {
    const container = document.getElementById('featured-list');
    container.innerHTML = featured.map(p => {
        const birth = p.birth_year || '';
        const death = p.death_year || '';
        const years = [birth, death].filter(Boolean).join(' - ') || '?';
        const pid = p.id.replace(/@/g, '');
        const displayName = formatNameWithNickname(p.name, p.nickname);
        return `
        <a href="/tree.html#${pid}" class="featured-member">
            ${p.photo_file
                ? `<img class="featured-photo" src="/photos/${p.photo_file}" alt="${displayName}">`
                : `<div class="featured-no-photo"><span class="material-symbols-outlined">person</span></div>`
            }
            <div class="featured-info">
                <p class="featured-name">${displayName}</p>
                <p class="featured-years">${years}</p>
            </div>
        </a>`;
    }).join('');
}

function renderDocuments(documents) {
    const container = document.getElementById('documents-gallery');
    if (!documents || !documents.length) {
        container.innerHTML = '<p class="no-data">Cap document disponible</p>';
        return;
    }

    const docLabels = {
        'bautisme': 'Bautisme',
        'matrimoni': 'Matrimoni',
        'defuncio': 'Defunció',
        'naixement': 'Naixement',
        'certificat': 'Certificat',
        'padro': 'Padró',
        'testament': 'Testament',
        'arbre': 'Arbre',
        'transcripcio': 'Transcripció',
        'poema': 'Poema',
        'invitacio': 'Invitació',
        'carta': 'Carta',
        'dibuix': 'Dibuix',
        'biografia': 'Biografia',
        'document': 'Document'
    };

    const d = documents[0];
    const caption = d.title || 'Document';
    const typeLabel = docLabels[d.doc_type] || d.doc_type;

    container.innerHTML = `
        <div class="document-single">
            <div class="document-image-half">
                <img src="/photos/${d.filename}" alt="${caption}" loading="lazy">
            </div>
            <div class="document-content-full">
                <h4 class="document-title">${caption}</h4>
                <div class="document-meta">
                    ${d.doc_type ? `<span class="doc-badge">${typeLabel}</span>` : ''}
                    ${d.date ? `<span class="doc-date">${d.date}</span>` : ''}
                </div>
                ${d.transcription ? `<p class="document-transcription">${d.transcription}</p>` : ''}
            </div>
        </div>`;

    // Add link to see all documents
    const link = document.createElement('div');
    link.className = 'documents-see-all';
    link.innerHTML = '<a href="/arxiu.html">Ver tots els documents →</a>';
    container.parentElement.appendChild(link);
}

// Hero search: redirect to chat with query
function doSearch() {
    const q = document.getElementById('hero-query').value.trim();
    if (q) {
        window.location.href = '/chat.html?q=' + encodeURIComponent(q);
    }
}

document.getElementById('hero-send').addEventListener('click', doSearch);
document.getElementById('hero-query').addEventListener('keydown', e => {
    if (e.key === 'Enter') doSearch();
});

document.querySelectorAll('.hero-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        window.location.href = '/chat.html?q=' + encodeURIComponent(chip.dataset.q);
    });
});

loadDashboard();
