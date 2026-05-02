/* docs.js — Página de documentos */

const STATE = {
    docTypes: [],
    docAlbums: [],
    allPeople: [],
    filteredPeople: [],

    activeDocType: '__all__',
    activeAlbumId: null,
    activePersonId: null,
    searchQuery: '',
    sortBy: 'date',
    viewMode: 'bento',

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

const DOC_TYPE_ICONS = {
    'bautisme':        '/icons/bautismo.svg',
    'matrimoni':       '/icons/matrimonio.svg',
    'defuncio':        '/icons/defuncion.svg',
    'naixement':       '/icons/nacimiento.svg',
    'certificat':      '/icons/documentacion.svg',
    'padro':           '/icons/padron.svg',
    'testament':       '/icons/carta.svg',
    'arbre':           '/icons/documentacion.svg',
    'transcripcio':    '/icons/documentacion.svg',
    'poema':           '/icons/documentacion.svg',
    'invitacio':       '/icons/documentacion.svg',
    'carta':           '/icons/carta.svg',
    'dibuix':          '/icons/documentacion.svg',
    'biografia':       '/icons/biografia.svg',
    'document':        '/icons/documentacion.svg',
    '__unclassified__':'/icons/diversos.svg',
};

// ─── Init ────────────────────────────────────────────────────────────────────

async function init() {
    const [typesRes, peopleRes, albumsRes] = await Promise.all([
        fetch('/api/documents').then(r => r.json()),
        fetch('/api/documents/people').then(r => r.json()),
        fetch('/api/documents/albums').then(r => r.json()),
    ]);

    STATE.docTypes = typesRes.types || [];
    STATE.docAlbums = albumsRes.albums || [];
    STATE.allPeople = peopleRes.people || [];
    STATE.filteredPeople = STATE.allPeople.slice();

    renderSidebarTypes();
    renderSidebarDocAlbums();
    renderSidebarPeople(STATE.allPeople);
    setupPersonSearch();
    setupInfiniteScroll();
    setupBackToTop();
    setupKeyboardNav();
    attachSearchListener();

    if (window.location.hash) {
        checkUrlHash();
    } else {
        selectDocType('__all__');
    }

    document.getElementById('docs-loading').classList.add('hidden');
}

// ─── URL hash navigation ──────────────────────────────────────────────────────

function checkUrlHash() {
    const hash = window.location.hash.replace('#', '');
    selectDocType(hash || '__all__');
}

window.addEventListener('popstate', checkUrlHash);

// ─── Doc type selection ───────────────────────────────────────────────────────

function selectDocType(docType) {
    STATE.activeDocType = docType;
    STATE.page = 1;
    STATE.photos = [];

    history.replaceState(null, '', '#' + docType);

    const typeObj = STATE.docTypes.find(t => t.type === docType);
    const label = typeObj ? typeObj.label : 'Documentos';
    document.getElementById('page-title').textContent = label;

    document.querySelectorAll('.sidebar-type-link').forEach(el => {
        el.classList.toggle('active', el.dataset.type === docType);
    });

    document.getElementById('docs-photos-section').classList.remove('hidden');
    fetchPhotos(false);
}

// ─── Fetch photos ─────────────────────────────────────────────────────────────

async function fetchPhotos(append = false) {
    if (STATE.isLoading) return;
    STATE.isLoading = true;

    const params = new URLSearchParams({
        doc_type: STATE.activeDocType,
        sort: STATE.sortBy,
        page: STATE.page,
        limit: 50,
    });
    if (STATE.searchQuery) params.set('q', STATE.searchQuery);
    if (STATE.activePersonId) params.set('person_id', STATE.activePersonId);
    if (STATE.activeAlbumId) params.set('album_id', STATE.activeAlbumId);

    try {
        const data = await fetch(`/api/documents/photos?${params}`).then(r => r.json());

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
        console.error('Error fetching documents', e);
    } finally {
        STATE.isLoading = false;
    }
}

// ─── Render photos ────────────────────────────────────────────────────────────

function renderPhotos(append) {
    const container = document.getElementById('photos-grid-container');
    if (!append) container.innerHTML = '';

    if (!append && STATE.photos.length === 0) {
        container.innerHTML = '<p class="text-outline text-sm py-12 text-center">No se encontraron documentos.</p>';
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
        const isPdf = photo.filename.toLowerCase().endsWith('.pdf');

        const el = document.createElement('div');
        el.className = `group relative overflow-hidden heritage-border rounded-lg cursor-pointer ${sizeClass}`;
        el.onclick = () => isPdf ? window.open(`/photos/${photo.filename}`, '_blank') : openPhotoFromDocs(idx);
        el.setAttribute('tabindex', '0');
        el.onkeydown = e => { if (e.key === 'Enter') el.onclick(); };

        const typeLabel = STATE.activeDocType === '__all__' && photo.doc_type
            ? `<span class="doc-type-badge absolute top-2 left-2 z-10">${_docTypeLabel(photo.doc_type)}</span>`
            : '';

        el.innerHTML = isPdf
            ? `${typeLabel}
               <div class="w-full h-full flex flex-col items-center justify-center bg-surface-container-high gap-2 p-3">
                   <span class="material-symbols-outlined text-4xl text-outline">picture_as_pdf</span>
                   <p class="text-[11px] text-outline text-center line-clamp-3">${photo.title || photo.filename}</p>
               </div>`
            : `<img src="/photos/${photo.filename}" alt="${photo.title || ''}"
                 class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-105"
                 loading="lazy"/>
               ${typeLabel}
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
        const isPdf = photo.filename.toLowerCase().endsWith('.pdf');
        const el = document.createElement('div');
        el.className = 'group relative aspect-square overflow-hidden heritage-border rounded-lg cursor-pointer bg-surface-container-highest';
        el.onclick = () => isPdf ? window.open(`/photos/${photo.filename}`, '_blank') : openPhotoFromDocs(idx);
        el.setAttribute('tabindex', '0');
        el.onkeydown = e => { if (e.key === 'Enter') el.onclick(); };

        const typeLabel = STATE.activeDocType === '__all__' && photo.doc_type
            ? `<span class="doc-type-badge absolute top-2 left-2 z-10">${_docTypeLabel(photo.doc_type)}</span>`
            : '';

        el.innerHTML = isPdf
            ? `${typeLabel}
               <div class="w-full h-full flex flex-col items-center justify-center gap-2 p-3">
                   <span class="material-symbols-outlined text-4xl text-outline">picture_as_pdf</span>
                   <p class="text-[11px] text-outline text-center line-clamp-3">${photo.title || photo.filename}</p>
               </div>`
            : `<img src="/photos/${photo.filename}" alt="${photo.title || ''}"
                 class="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
                 loading="lazy"/>
               ${typeLabel}
               <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-2
                           opacity-0 group-hover:opacity-100 transition-opacity">
                   ${photo.title ? `<p class="text-white text-[11px] font-semibold line-clamp-1">${photo.title}</p>` : ''}
                   ${photo.date ? `<span class="text-white/60 text-[10px]">${photo.date}</span>` : ''}
               </div>`;
        grid.appendChild(el);
    });
}

function _docTypeLabel(type) {
    const t = STATE.docTypes.find(d => d.type === type);
    return t ? t.label : type;
}

// ─── Open photo ───────────────────────────────────────────────────────────────

function openPhotoFromDocs(index) {
    STATE.currentPhotoIndex = index;
    const photo = STATE.photos[index];
    if (!photo) return;

    window.__photoModalContext = {
        onPrev: index > 0 ? () => openPhotoFromDocs(STATE.currentPhotoIndex - 1) : null,
        onNext: index < STATE.photos.length - 1 ? () => openPhotoFromDocs(STATE.currentPhotoIndex + 1) : null,
    };

    openPhotoModal(photo.id);
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function renderSidebarTypes() {
    const nav = document.getElementById('sidebar-type-list');

    nav.innerHTML = STATE.docTypes.map(t => {
        const iconSrc = t.type === '__all__' ? null : (DOC_TYPE_ICONS[t.type] || '/icons/documentacion.svg');
        const isActive = t.type === STATE.activeDocType;
        const iconHtml = iconSrc
            ? `<img src="${iconSrc}" style="width:16px;height:16px;flex-shrink:0;opacity:0.6;" alt="">`
            : `<span class="material-symbols-outlined text-sm text-outline">folder_open</span>`;
        return `
        <a class="sidebar-type-link ${isActive ? 'active' : ''}" data-type="${t.type}"
           onclick="selectDocType('${t.type}')">
            <span class="flex items-center gap-1.5">
                ${iconHtml}
                <span class="truncate${t.type === '__all__' ? ' font-semibold' : ''}">${t.label}</span>
            </span>
            <span class="text-[10px] text-outline shrink-0 ml-1">${t.count}</span>
        </a>`;
    }).join('');
}

function renderSidebarDocAlbums() {
    const container = document.getElementById('sidebar-album-section');
    if (!container) return;
    if (STATE.docAlbums.length === 0) {
        container.classList.add('hidden');
        return;
    }
    container.classList.remove('hidden');
    const list = document.getElementById('sidebar-album-list');
    list.innerHTML = STATE.docAlbums.map(a => {
        const isActive = STATE.activeAlbumId === a.id;
        return `
        <a class="sidebar-type-link ${isActive ? 'active' : ''}" data-album-id="${a.id}"
           onclick="selectDocAlbum('${a.id}')">
            <span class="flex items-center gap-1.5">
                <span class="material-symbols-outlined text-sm text-outline">photo_library</span>
                <span class="truncate">${a.title}</span>
            </span>
            <span class="text-[10px] text-outline shrink-0 ml-1">${a.count}</span>
        </a>`;
    }).join('');
}

function selectDocAlbum(albumId) {
    STATE.activeAlbumId = STATE.activeAlbumId === albumId ? null : albumId;
    document.querySelectorAll('[data-album-id]').forEach(el => {
        el.classList.toggle('active', el.dataset.albumId === STATE.activeAlbumId);
    });
    STATE.page = 1;
    STATE.photos = [];
    fetchPhotos(false);
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

    renderSidebarPeople(STATE.filteredPeople);
    STATE.page = 1;
    STATE.photos = [];
    fetchPhotos(false);
}

function clearPersonFilter() {
    STATE.activePersonId = null;
    const chip = document.getElementById('active-person-chip');
    chip.classList.add('hidden');
    chip.classList.remove('flex');
    document.getElementById('clear-person-btn').classList.add('hidden');
    renderSidebarPeople(STATE.filteredPeople);

    STATE.page = 1;
    STATE.photos = [];
    fetchPhotos(false);
}

// ─── Search ───────────────────────────────────────────────────────────────────

function attachSearchListener() {
    document.getElementById('photo-search').addEventListener('input', function () {
        clearTimeout(STATE.searchDebounce);
        STATE.searchDebounce = setTimeout(() => {
            STATE.searchQuery = this.value.trim();
            STATE.page = 1;
            STATE.photos = [];
            fetchPhotos(false);
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
    STATE.page = 1;
    STATE.photos = [];
    fetchPhotos(false);
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
    const toolbar = document.querySelector('.border-b.border-outline-variant\\/20.bg-surface-container\\/40');
    if (toolbar) observer.observe(toolbar);
}

// ─── Keyboard navigation ──────────────────────────────────────────────────────

function setupKeyboardNav() {
    document.addEventListener('keydown', e => {
        const overlay = document.getElementById('photo-modal-overlay');
        if (!overlay || overlay.style.display === 'none' || overlay.style.display === '') return;
        if (e.key === 'ArrowRight' && STATE.currentPhotoIndex < STATE.photos.length - 1) {
            openPhotoFromDocs(STATE.currentPhotoIndex + 1);
        } else if (e.key === 'ArrowLeft' && STATE.currentPhotoIndex > 0) {
            openPhotoFromDocs(STATE.currentPhotoIndex - 1);
        }
    });
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

function updatePhotoCountLabel() {
    const label = document.getElementById('photo-count-label');
    label.textContent = `${STATE.total} documento${STATE.total !== 1 ? 's' : ''}`;
}

// ─── Boot ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', init);
