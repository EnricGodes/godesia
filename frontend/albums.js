/* albums.js — Página de álbumes fotográficos */

/* i18n: t()/I18N vienen de i18n.js (inyectado por el backend) */
const _i18nT = window.t || function (k, p, f) { return f !== undefined ? f : k; };
const _lhref = window.I18N ? window.I18N.href : function (p) { return p; };

const STATE = {
    albums: [],
    unassigned: null,
    allPeople: [],
    filteredPeople: [],

    activeAlbumId: null,
    activePersonId: null,
    searchQuery: '',
    sortBy: 'date',
    viewMode: 'bento',
    showDocs: false,

    photos: [],
    total: 0,
    page: 1,
    isLoading: false,
    searchDebounce: null,
    currentPhotoIndex: -1,
};

const BENTO_PATTERN = [
    'bento-med','bento-small','bento-xsmall','bento-small',
    'bento-med','bento-xsmall','bento-small','bento-med',
    'bento-xsmall','bento-small','bento-xsmall','bento-med',
    'bento-small','bento-xsmall','bento-med','bento-small',
    'bento-small','bento-hero','bento-xsmall','bento-small',
];

// ─── Init ────────────────────────────────────────────────────────────────────

async function init() {
    const [albumsRes, peopleRes] = await Promise.all([
        fetch('/api/albums').then(r => r.json()),
        fetch('/api/albums/people').then(r => r.json()),
    ]);

    STATE.albums = albumsRes.albums || [];
    STATE.unassigned = albumsRes.unassigned || null;
    STATE.allPeople = peopleRes.people || [];
    STATE.filteredPeople = STATE.allPeople.slice();

    renderSidebarAlbums();
    renderSidebarPeople(STATE.allPeople);
    setupPersonSearch();
    setupInfiniteScroll();
    setupBackToTop();
    setupKeyboardNav();
    attachSearchListener();

    // Default: show all photos; hash overrides to a specific album
    if (window.location.hash) {
        checkUrlHash();
    } else {
        selectAlbum('__all__');
    }

    document.getElementById('albums-loading').classList.add('hidden');
}

// ─── URL hash navigation ──────────────────────────────────────────────────────

function checkUrlHash() {
    const hash = window.location.hash.replace('#', '');
    if (hash) {
        selectAlbum(hash);
    } else {
        selectAlbum('__all__');
    }
}

window.addEventListener('popstate', checkUrlHash);

// ─── Album selection ──────────────────────────────────────────────────────────

function selectAlbum(albumId) {
    STATE.activeAlbumId = albumId;
    STATE.page = 1;
    STATE.photos = [];

    history.replaceState(null, '', '#' + albumId);

    const album = albumId === '__unassigned__' ? STATE.unassigned
        : albumId === '__all__' ? { title: _i18nT('pages.albums.title', null, 'Álbum de fotos') }
        : STATE.albums.find(a => a.id === albumId || a.id === `@${albumId}@`);
    const title = album ? album.title : albumId;

    document.getElementById('page-title').textContent = title;

    // Sidebar highlight
    document.querySelectorAll('.sidebar-album-link').forEach(el => {
        el.classList.toggle('active', el.dataset.id === albumId || el.dataset.id === `@${albumId}@`);
    });

    document.getElementById('albums-overview').classList.add('hidden');
    document.getElementById('album-photos-section').classList.remove('hidden');

    fetchPhotos(false);
}

function showAlbumsOverview() {
    STATE.activeAlbumId = null;
    STATE.photos = [];
    history.replaceState(null, '', window.location.pathname);

    document.getElementById('page-title').textContent = _i18nT('pages.albums.title', null, 'Álbum de fotos');

    document.querySelectorAll('.sidebar-album-link').forEach(el => el.classList.remove('active'));

    document.getElementById('album-photos-section').classList.add('hidden');
    document.getElementById('albums-overview').classList.remove('hidden');

    renderAlbumCards();
    updatePageSubtitle();
}

// ─── Fetch photos ─────────────────────────────────────────────────────────────

async function fetchPhotos(append = false) {
    if (STATE.isLoading) return;
    STATE.isLoading = true;

    const albumId = STATE.activeAlbumId;
    const params = new URLSearchParams({
        sort: STATE.sortBy,
        page: STATE.page,
        limit: 50,
    });
    if (STATE.searchQuery) params.set('q', STATE.searchQuery);
    if (STATE.activePersonId) params.set('person_id', STATE.activePersonId);
    if (STATE.showDocs) params.set('show_docs', 'true');

    // Normalize albumId for URL: strip @ wrappers for the path
    const pathId = albumId === '__unassigned__' ? albumId
        : albumId.replace(/^@/, '').replace(/@$/, '');

    try {
        const data = await fetch((window.I18N ? I18N.apiUrl : (p => p))(`/api/album/${encodeURIComponent(pathId)}/photos?${params}`)).then(r => r.json());

        if (append) {
            STATE.photos.push(...data.photos);
        } else {
            STATE.photos = data.photos;
        }
        STATE.total = data.total;

        renderPhotos(append);
        updatePhotoCountLabel();
        updateLoadMoreSentinel();
    } catch (e) {
        console.error('Error fetching photos', e);
    } finally {
        STATE.isLoading = false;
    }
}

// ─── Render album cards (overview) ───────────────────────────────────────────

function renderAlbumCards() {
    const container = document.getElementById('albums-card-grid');
    const items = [...STATE.albums, ...(STATE.unassigned ? [STATE.unassigned] : [])];

    // Filter by search query (client-side on overview)
    const q = STATE.searchQuery.toLowerCase();
    const filtered = q ? items.filter(a => a.title.toLowerCase().includes(q)) : items;

    container.innerHTML = filtered.map(album => {
        const isUA = album.id === '__unassigned__';
        const yearRange = (album.min_year && album.max_year)
            ? `${album.min_year}–${album.max_year}` : '';

        return `
        <div class="album-card heritage-border bg-surface-container-lowest"
             onclick="selectAlbum('${album.id}')">
            <div class="aspect-[4/3] overflow-hidden bg-surface-container-highest">
                ${album.cover
                    ? `<img src="/photos/${album.cover}" alt="${album.title}"
                            class="w-full h-full object-cover transition-transform duration-500 hover:scale-105" loading="lazy"/>`
                    : `<div class="w-full h-full flex items-center justify-center">
                           <span class="material-symbols-outlined text-5xl text-outline-variant">photo_library</span>
                       </div>`
                }
            </div>
            <div class="p-3">
                <div class="flex items-start justify-between gap-1 mb-1">
                    <h3 class="font-headline text-sm font-semibold text-on-surface leading-tight">${album.title}</h3>
                    ${isUA ? `<span class="material-symbols-outlined text-base text-secondary shrink-0">family_home</span>` : ''}
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-[11px] text-outline">${album.photo_count} ${_i18nT('common.photos_lower', null, 'fotos')}</span>
                    ${yearRange ? `<span class="text-[11px] text-outline-variant">·</span>
                                   <span class="text-[11px] text-outline">${yearRange}</span>` : ''}
                </div>
            </div>
        </div>`;
    }).join('');
}

// ─── Render photos ────────────────────────────────────────────────────────────

function renderPhotos(append) {
    const container = document.getElementById('photos-grid-container');
    if (!append) container.innerHTML = '';

    if (!append && STATE.photos.length === 0) {
        container.innerHTML = `<p class="text-outline text-sm py-12 text-center">${_i18nT('pages.albums.no_photos', null, 'No se encontraron fotos.')}</p>`;
        return;
    }

    const photosToRender = append ? STATE.photos.slice(-50) : STATE.photos;
    const startIndex = append ? STATE.photos.length - photosToRender.length : 0;

    if (STATE.viewMode === 'bento') {
        renderBentoGrid(container, photosToRender, startIndex, append);
    } else {
        renderUniformGrid(container, photosToRender, startIndex, append);
    }
}

function renderBentoGrid(container, photos, startIndex, append) {
    let grid = append ? container.querySelector('.bento-grid') : null;
    if (!grid) {
        grid = document.createElement('div');
        grid.className = 'bento-grid';
        container.appendChild(grid);
    }

    photos.forEach((photo, i) => {
        const sizeClass = BENTO_PATTERN[(startIndex + i) % BENTO_PATTERN.length];
        const lineClamp = sizeClass === 'bento-hero' ? 'line-clamp-4'
            : sizeClass === 'bento-med' ? 'line-clamp-2' : 'line-clamp-1';
        const idx = startIndex + i;

        const el = document.createElement('div');
        el.className = `group relative overflow-hidden heritage-border rounded-lg cursor-pointer ${sizeClass}`;
        el.onclick = () => openPhotoFromAlbum(idx);
        el.setAttribute('tabindex', '0');
        el.onkeydown = e => { if (e.key === 'Enter') openPhotoFromAlbum(idx); };
        el.innerHTML = `
            <img src="/photos/${photo.filename}" alt="${photo.title || ''}"
                 class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                 loading="lazy"/>
            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 to-transparent p-3
                        opacity-0 group-hover:opacity-100 transition-opacity">
                ${photo.title ? `<p class="text-white text-[13px] font-bold ${lineClamp}">${photo.title}</p>` : ''}
                ${photo.date ? `<span class="text-white/60 text-[11px]">${photo.date}</span>` : ''}
            </div>`;
        grid.appendChild(el);
    });
}

function renderUniformGrid(container, photos, startIndex, append) {
    let grid = append ? container.querySelector('.uniform-grid') : null;
    if (!grid) {
        grid = document.createElement('div');
        grid.className = 'uniform-grid grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3';
        container.appendChild(grid);
    }

    photos.forEach((photo, i) => {
        const idx = startIndex + i;
        const el = document.createElement('div');
        el.className = 'group relative aspect-square overflow-hidden heritage-border rounded-lg cursor-pointer bg-surface-container-highest';
        el.onclick = () => openPhotoFromAlbum(idx);
        el.setAttribute('tabindex', '0');
        el.onkeydown = e => { if (e.key === 'Enter') openPhotoFromAlbum(idx); };
        el.innerHTML = `
            <img src="/photos/${photo.filename}" alt="${photo.title || ''}"
                 class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                 loading="lazy"/>
            <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2
                        opacity-0 group-hover:opacity-100 transition-opacity">
                ${photo.title ? `<p class="text-white text-[11px] font-semibold line-clamp-1">${photo.title}</p>` : ''}
                ${photo.date ? `<span class="text-white/60 text-[10px]">${photo.date}</span>` : ''}
            </div>`;
        grid.appendChild(el);
    });
}

// ─── Open photo with album context ───────────────────────────────────────────

function openPhotoFromAlbum(index) {
    STATE.currentPhotoIndex = index;
    const photo = STATE.photos[index];
    if (!photo) return;

    const album = STATE.activeAlbumId === '__unassigned__' ? STATE.unassigned
        : STATE.activeAlbumId === '__all__' ? null
        : STATE.albums.find(a => a.id === STATE.activeAlbumId || a.id === `@${STATE.activeAlbumId}@`);

    window.__photoModalContext = album ? {
        albumId: STATE.activeAlbumId,
        albumTitle: album.title,
        onPrev: index > 0 ? () => openPhotoFromAlbum(STATE.currentPhotoIndex - 1) : null,
        onNext: index < STATE.photos.length - 1 ? () => openPhotoFromAlbum(STATE.currentPhotoIndex + 1) : null,
    } : null;

    openPhotoModal(photo.id);
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function renderSidebarAlbums() {
    const nav = document.getElementById('sidebar-album-list');
    const totalPhotos = STATE.albums.reduce((s, a) => s + a.photo_count, 0)
        + (STATE.unassigned?.photo_count || 0);

    const allEntry = `
        <a class="sidebar-album-link" data-id="__all__" onclick="selectAlbum('__all__')">
            <span class="flex items-center gap-1.5">
                <span class="material-symbols-outlined text-sm text-outline">collections</span>
                <span class="truncate font-semibold">${_i18nT('pages.albums.all_photos', null, 'Todas las fotos')}</span>
            </span>
            <span class="text-[10px] text-outline shrink-0 ml-1">${totalPhotos}</span>
        </a>
        <div class="border-t border-outline-variant/20 my-1.5"></div>
        <a class="sidebar-album-link text-[11px] text-outline" onclick="showAlbumsOverview()">
            <span class="flex items-center gap-1.5">
                <span class="material-symbols-outlined text-sm">grid_view</span>
                <span>${_i18nT('pages.albums.view_albums', null, 'Ver álbumes')}</span>
            </span>
        </a>
        <div class="border-t border-outline-variant/20 my-1.5"></div>`;

    const albumLinks = [...STATE.albums, ...(STATE.unassigned ? [STATE.unassigned] : [])].map(album => {
        const isUA = album.id === '__unassigned__';
        const icon = isUA ? 'family_home' : 'photo_library';
        return `
        <a class="sidebar-album-link" data-id="${album.id}" onclick="selectAlbum('${album.id}')">
            <span class="flex items-center gap-1.5">
                <span class="material-symbols-outlined text-sm text-outline">${icon}</span>
                <span class="truncate">${album.title}</span>
            </span>
            <span class="text-[10px] text-outline shrink-0 ml-1">${album.photo_count}</span>
        </a>`;
    }).join('');

    nav.innerHTML = allEntry + albumLinks;
}

function renderSidebarPeople(people) {
    const list = document.getElementById('person-filter-list');
    list.innerHTML = people.slice(0, 60).map(p => {
        const initials = (p.given_name || p.name || '?')[0].toUpperCase();
        const isActive = STATE.activePersonId && (
            p.id === STATE.activePersonId || p.id === `@${STATE.activePersonId}@`
        );
        const parts = [p.given_name, p.nickname ? `"${p.nickname}"` : null, p.surname].filter(Boolean);
        const displayName = parts.length ? parts.join(' ') : (p.name || '?');
        return `
        <div class="person-pill ${isActive ? 'active' : ''}"
             data-person-id="${p.id}"
             onclick="selectPersonFilter('${p.id}')">
            ${p.photo_file
                ? `<img src="/photos/${p.photo_file}" class="w-6 h-6 rounded-full object-cover shrink-0" loading="lazy"/>`
                : `<div class="w-6 h-6 rounded-full bg-primary-container text-primary text-[10px] font-bold flex items-center justify-center shrink-0">${initials}</div>`
            }
            <span class="truncate flex-1">${displayName}</span>
            <span class="text-[10px] text-outline shrink-0">${p.photo_count}</span>
        </div>`;
    }).join('');
}

function setupPersonSearch() {
    document.getElementById('person-filter-input').addEventListener('input', function () {
        const q = this.value.toLowerCase();
        STATE.filteredPeople = q
            ? STATE.allPeople.filter(p =>
                (p.name || '').toLowerCase().includes(q) ||
                (p.given_name || '').toLowerCase().includes(q) ||
                (p.surname || '').toLowerCase().includes(q) ||
                (p.nickname || '').toLowerCase().includes(q)
              )
            : STATE.allPeople;
        renderSidebarPeople(STATE.filteredPeople);
    });
}

// ─── Person filter ────────────────────────────────────────────────────────────

function selectPersonFilter(personId) {
    STATE.activePersonId = STATE.activePersonId === personId ? null : personId;

    if (STATE.activePersonId) {
        const person = STATE.allPeople.find(p => p.id === personId);
        const chip = document.getElementById('active-person-chip');
        chip.classList.remove('hidden');
        chip.classList.add('flex');
        document.getElementById('chip-name').textContent = person ? (person.given_name || person.name) : personId;
        const avatar = document.getElementById('chip-avatar');
        if (person?.photo_file) {
            avatar.src = `/photos/${person.photo_file}`;
            avatar.classList.remove('hidden');
        } else {
            avatar.classList.add('hidden');
        }
        document.getElementById('clear-person-btn').classList.remove('hidden');
    } else {
        clearPersonFilter();
        return;
    }

    // Re-render sidebar to update active state
    renderSidebarPeople(STATE.filteredPeople);

    if (STATE.activeAlbumId) {
        STATE.page = 1;
        STATE.photos = [];
        fetchPhotos(false);
    }
}

function clearPersonFilter() {
    STATE.activePersonId = null;
    const chip = document.getElementById('active-person-chip');
    chip.classList.add('hidden');
    chip.classList.remove('flex');
    document.getElementById('clear-person-btn').classList.add('hidden');
    renderSidebarPeople(STATE.filteredPeople);

    if (STATE.activeAlbumId) {
        STATE.page = 1;
        STATE.photos = [];
        fetchPhotos(false);
    }
}

// ─── Search ───────────────────────────────────────────────────────────────────

function attachSearchListener() {
    document.getElementById('photo-search').addEventListener('input', function () {
        clearTimeout(STATE.searchDebounce);
        const q = this.value.trim();
        STATE.searchDebounce = setTimeout(() => {
            STATE.searchQuery = q;
            if (STATE.activeAlbumId) {
                STATE.page = 1;
                STATE.photos = [];
                fetchPhotos(false);
            } else {
                renderAlbumCards();
            }
        }, 350);
    });
}

// ─── Sort ─────────────────────────────────────────────────────────────────────

function setSort(criterion) {
    STATE.sortBy = criterion;
    document.querySelectorAll('.sort-btn').forEach(btn => {
        const isActive = btn.dataset.sort === criterion;
        btn.classList.toggle('active', isActive);
        btn.classList.toggle('text-outline', !isActive);
    });
    if (STATE.activeAlbumId) {
        STATE.page = 1;
        STATE.photos = [];
        fetchPhotos(false);
    }
}

// ─── View mode ────────────────────────────────────────────────────────────────

function setViewMode(mode) {
    STATE.viewMode = mode;
    document.getElementById('view-bento').classList.toggle('active', mode === 'bento');
    document.getElementById('view-grid').classList.toggle('active', mode === 'grid');
    document.getElementById('view-bento').classList.toggle('text-outline', mode !== 'bento');
    document.getElementById('view-grid').classList.toggle('text-outline', mode !== 'grid');

    if (STATE.photos.length > 0) {
        renderPhotos(false);
    }
}

// ─── Infinite scroll ──────────────────────────────────────────────────────────

function setupInfiniteScroll() {
    const sentinel = document.getElementById('load-more-sentinel');
    const observer = new IntersectionObserver(entries => {
        if (!entries[0].isIntersecting) return;
        if (STATE.isLoading || STATE.photos.length >= STATE.total) return;
        STATE.page++;
        fetchPhotos(true);
    }, { rootMargin: '400px', threshold: 0 });
    observer.observe(sentinel);
}

function updateLoadMoreSentinel() {
    const spinner = document.getElementById('load-more-spinner');
    spinner.classList.toggle('hidden', STATE.photos.length >= STATE.total);
}

// ─── Back to top ──────────────────────────────────────────────────────────────

function setupBackToTop() {
    const btn = document.getElementById('back-to-top');
    const observer = new IntersectionObserver(entries => {
        btn.classList.toggle('hidden', entries[0].isIntersecting);
        btn.classList.toggle('flex', !entries[0].isIntersecting);
    });
    // Observe the toolbar as the sentinel
    const toolbar = document.querySelector('.border-b.border-outline-variant\\/20.bg-surface-container\\/40');
    if (toolbar) observer.observe(toolbar);
}

// ─── Keyboard navigation ──────────────────────────────────────────────────────

function setupKeyboardNav() {
    document.addEventListener('keydown', e => {
        const overlay = document.getElementById('photo-modal-overlay');
        if (!overlay || overlay.style.display === 'none' || overlay.style.display === '') return;
        if (e.key === 'ArrowRight' && STATE.currentPhotoIndex < STATE.photos.length - 1) {
            openPhotoFromAlbum(STATE.currentPhotoIndex + 1);
        } else if (e.key === 'ArrowLeft' && STATE.currentPhotoIndex > 0) {
            openPhotoFromAlbum(STATE.currentPhotoIndex - 1);
        }
    });
}

// ─── Docs toggle ─────────────────────────────────────────────────────────────

function toggleDocs() {
    STATE.showDocs = !STATE.showDocs;
    const btn = document.getElementById('docs-toggle');
    if (STATE.showDocs) {
        btn.classList.add('bg-primary', 'text-on-primary', 'border-primary');
        btn.classList.remove('text-outline', 'border-outline-variant');
    } else {
        btn.classList.remove('bg-primary', 'text-on-primary', 'border-primary');
        btn.classList.add('text-outline', 'border-outline-variant');
    }
    if (STATE.activeAlbumId) {
        STATE.page = 1;
        STATE.photos = [];
        fetchPhotos(false);
    }
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

function updatePhotoCountLabel() {
    const label = document.getElementById('photo-count-label');
    label.textContent = `${STATE.total} ${STATE.total !== 1 ? _i18nT('common.photos_lower', null, 'fotos') : _i18nT('common.photo_lower', null, 'foto')}`;
}

function updatePageSubtitle() {
    const total = STATE.albums.reduce((s, a) => s + a.photo_count, 0)
        + (STATE.unassigned?.photo_count || 0);
    const albumCount = STATE.albums.length + (STATE.unassigned ? 1 : 0);
    document.getElementById('page-subtitle').textContent =
        `${albumCount} ${_i18nT('pages.albums.albums_lower', null, 'álbumes')} · ${total} ${_i18nT('common.photos_lower', null, 'fotos')}`;
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
