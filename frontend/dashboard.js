const MONTHS_CA = [
    '', 'Gen', 'Feb', 'Mar', 'Abr', 'Mai', 'Jun',
    'Jul', 'Ago', 'Set', 'Oct', 'Nov', 'Des'
];

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
    const icons = ['account_tree', 'family_history', 'diversity_3', 'history', 'groups'];
    container.innerHTML = branches.map((b, i) => `
        <a href="/tree.html" class="branch-link${i === 0 ? ' active' : ''}">
            <span class="material-symbols-outlined branch-icon">${icons[i % icons.length]}</span>
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
        return `
        <div class="anniversary-row">
            <div class="anniversary-date${isToday ? ' today' : ''}">
                <span class="anniversary-month">${monthLabel}</span>
                <span class="anniversary-day">${b.birth_day}</span>
            </div>
            <div class="anniversary-info">
                <p class="anniversary-name">${b.name}${b.age ? ' (' + b.age + ' anys)' : ''}</p>
            </div>
            ${b.photo ? `<img class="anniversary-photo" src="/photos/${b.photo}" alt="${b.name}">` : ''}
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
        const years = p.birth_year ? `${p.birth_year}` : '';
        const place = p.birth_place ? p.birth_place : '';
        const meta = [years, place].filter(Boolean).join(' • ');
        return `
        <div class="photo-card-full">
            <img src="/photos/${p.photo}" alt="${p.name}" loading="lazy">
            <div class="photo-card-info">
                <h4>${p.name}</h4>
                ${meta ? `<p class="photo-meta">${meta}</p>` : ''}
                ${p.title ? `<p class="photo-title">${p.title}</p>` : ''}
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
        const years = p.is_alive
            ? `${p.birth_year || '?'} - Viu`
            : `${p.birth_year || '?'} - ${p.death_year || '?'}`;
        const pid = p.id.replace(/@/g, '');
        return `
        <a href="/tree.html#${pid}" class="featured-member">
            ${p.photo_file
                ? `<img class="featured-photo" src="/photos/${p.photo_file}" alt="${p.name}">`
                : `<div class="featured-no-photo"><span class="material-symbols-outlined">person</span></div>`
            }
            <div class="featured-info">
                <p class="featured-name">${p.name}</p>
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

    container.innerHTML = documents.map(d => {
        const caption = d.title || 'Document';
        const typeLabel = docLabels[d.doc_type] || d.doc_type;
        return `
        <div class="document-row">
            <div class="document-image">
                <img src="/photos/${d.filename}" alt="${caption}" loading="lazy">
            </div>
            <div class="document-content">
                <h4 class="document-title">${caption}</h4>
                <div class="document-meta">
                    ${d.doc_type ? `<span class="doc-badge">${typeLabel}</span>` : ''}
                    ${d.date ? `<span class="doc-date">${d.date}</span>` : ''}
                </div>
                ${d.transcription ? `<p class="document-transcription">${d.transcription}</p>` : ''}
            </div>
        </div>`;
    }).join('');

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
