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
    } catch (e) {
        console.error('Error loading dashboard:', e);
    }
}

function renderStats(stats) {
    document.getElementById('stat-people').textContent = stats.total_people;
    document.getElementById('stat-families').textContent = stats.total_families;
    document.getElementById('stat-alive').textContent = stats.alive;
    document.getElementById('stat-cities').textContent = stats.cities;
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
    if (!birthdays.length) {
        container.innerHTML = '<p class="no-data">Cap aniversari aquesta setmana</p>';
        return;
    }
    container.innerHTML = birthdays.slice(0, 5).map(b => {
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
                ${b.is_alive ? '<span class="alive-badge">Viu</span>' : ''}
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
    const rotations = [-1, 2, -2, 1, -1.5, 2.5];
    container.innerHTML = photos.map((p, i) => {
        const years = p.birth_year ? `circa ${p.birth_year}` : '';
        const place = p.birth_place || '';
        const caption = [years, place].filter(Boolean).join(' \u2022 ');
        return `
        <div class="photo-card-dash" style="--rotate: ${rotations[i % rotations.length]}deg">
            <div class="photo-card-inner">
                <div class="photo-card-img">
                    <img src="/photos/${p.photo}" alt="${p.name}" loading="lazy">
                </div>
                <h5 class="photo-card-name">${p.name}</h5>
                <p class="photo-card-meta">${caption}</p>
            </div>
        </div>`;
    }).join('');
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
