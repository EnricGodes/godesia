/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 */

let _currentPhotoData = null;
let _sidebarVisible = true;

const _DOC_TYPE_META = {
    'bautisme':    { label: 'Bautismos',           icon: '/icons/bautismo.svg' },
    'matrimoni':   { label: 'Matrimonios',          icon: '/icons/matrimonio.svg' },
    'defuncio':    { label: 'Defunciones',          icon: '/icons/defuncion.svg' },
    'naixement':   { label: 'Nacimientos',          icon: '/icons/nacimiento.svg' },
    'certificat':  { label: 'Certificados',         icon: '/icons/documentacion.svg' },
    'padro':       { label: 'Padrones',             icon: '/icons/padron.svg' },
    'testament':   { label: 'Testamentos',          icon: '/icons/carta.svg' },
    'arbre':       { label: 'Árboles Genealógicos', icon: '/icons/carta.svg' },
    'transcripcio':{ label: 'Transcripciones',      icon: '/icons/documentacion.svg' },
    'poema':       { label: 'Poemas',               icon: '/icons/documentacion.svg' },
    'invitacio':   { label: 'Invitaciones',         icon: '/icons/documentacion.svg' },
    'carta':       { label: 'Cartas',               icon: '/icons/carta.svg' },
    'dibuix':      { label: 'Dibujos y Planos',     icon: '/icons/documentacion.svg' },
    'biografia':   { label: 'Biografías',           icon: '/icons/biografia.svg' },
    'document':    { label: 'Documentos',           icon: '/icons/documentacion.svg' },
};

function escHtml(s) {
    return String(s ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

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

/**
 * Open photo modal with details
 * @param {number} photoId - Photo ID to display
 */
window.openPhotoModal = async function(photoId) {
    try {
        const res = await fetch(`/api/photo/${photoId}`);
        if (!res.ok) {
            console.error('Photo not found');
            return;
        }

        _currentPhotoData = await res.json();
        _sidebarVisible = true;
        renderPhotoModal();
        const overlay = document.getElementById('photo-modal-overlay');
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    } catch (e) {
        console.error('Error loading photo:', e);
    }
};

/**
 * Close photo modal
 */
window.closePhotoModal = function() {
    exitZoomMode();
    const overlay = document.getElementById('photo-modal-overlay');
    overlay.style.display = 'none';
    document.body.style.overflow = 'auto';
    _currentPhotoData = null;
};

/**
 * Toggle sidebar visibility with smooth animation
 */
window.togglePhotoSidebar = function() {
    _sidebarVisible = !_sidebarVisible;
    const sidebar = document.getElementById('photo-sidebar');
    const sidebarContent = document.getElementById('photo-sidebar-content');
    const toggleBtn = document.getElementById('toggle-sidebar-btn');
    const photoArea = document.getElementById('photo-area');

    if (!sidebar || !sidebarContent || !toggleBtn || !photoArea) return;

    if (_sidebarVisible) {
        // Show sidebar — keep overflow hidden until animation finishes
        sidebar.style.overflow = 'hidden';
        sidebar.style.width = '320px';
        sidebar.style.padding = '32px 24px 24px 24px';
        sidebar.style.borderRight = '1px solid rgba(114, 121, 113, 0.2)';
        setTimeout(() => {
            sidebarContent.style.opacity = '1';
            sidebar.style.overflow = 'auto';
        }, 650);
        toggleBtn.innerHTML = '←';
        toggleBtn.title = 'Ocultar panel';
    } else {
        // Hide sidebar — fade content first, then collapse
        sidebarContent.style.opacity = '0';
        sidebar.style.overflow = 'hidden';
        setTimeout(() => {
            sidebar.style.width = '0';
            sidebar.style.padding = '0';
            sidebar.style.borderRight = 'none';
        }, 150);
        toggleBtn.innerHTML = '→';
        toggleBtn.title = 'Mostrar panel';
    }
};

/**
 * Navigate to person's dossier
 */
window.gotoPersonDossier = function(personId) {
    personId = personId.replace(/@/g, '');
    window.location.href = `/dossier.html?id=${personId}`;
};

/**
 * Highlight face box when hovering over person in sidebar
 */
window.highlightFaceBox = function(personId, show) {
    const box = document.querySelector(`[data-person-box="${personId}"]`);
    if (box) {
        box.style.border = show ? '3px solid #2D4B33' : 'none';
        box.style.boxShadow = show ? '0 0 0 2px rgba(255, 255, 255, 0.8)' : 'none';
    }
};

/**
 * Render the modal content
 */
function renderPhotoModal() {
    if (!_currentPhotoData) return;

    const p = _currentPhotoData;

    // Build sidebar content
    let sidebarContent = '';

    // Breadcrumb from album context (set by albums.js before opening modal)
    const ctx = window.__photoModalContext;
    const breadcrumbHtml = ctx
        ? `<div style="font-size: 11px; color: #727971; margin-bottom: 16px;">
               <a href="/albums.html#${ctx.albumId}" style="color: #2D4B33; font-weight: 700; text-decoration: none;"
                  onmouseover="this.style.textDecoration='underline'"
                  onmouseout="this.style.textDecoration='none'">${ctx.albumTitle}</a>
               <span> › Foto</span>
           </div>`
        : '';

    // Title, date, place
    let infoHtml = '';
    if (p.title) {
        infoHtml += `<h2 style="font-size: 22px; font-weight: bold; color: #2D4B33; font-family: 'Noto Serif', serif; margin: 0 0 12px 0; line-height: 1.3;">${escHtml(p.title)}</h2>`;
    }
    if (p.date || p.place) {
        let datePlace = [];
        if (p.date) datePlace.push(p.date);
        if (p.place) datePlace.push(p.place);
        infoHtml += `<div style="font-size: 13px; color: #727971; margin-bottom: 28px;">${datePlace.join(' • ')}</div>`;
    }

    // Comentario
    const noteHtml = p.note
        ? `<div style="margin-bottom: 28px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 10px 0;">Comentario</h3>
             <p style="font-size: 13px; color: #424842; line-height: 1.65; white-space: pre-line;">${escHtml(p.note)}</p>
           </div>`
        : '';

    // Personas etiquetadas
    const tagsHtml = p.tagged_people && p.tagged_people.length > 0
        ? `<div style="margin-bottom: 28px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px 0;">Personas Etiquetadas</h3>
             <div style="display: flex; flex-direction: column; gap: 4px;">
               ${p.tagged_people.map(person => {
                 const cleanId = person.person_id.replace(/@/g, '');
                 const displayName = formatNameWithNickname(person.name, person.nickname, person.given_name, person.surname);
                 return `
                 <div style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 8px; border-radius: 6px; transition: background-color 0.2s;"
                      onmouseover="this.style.backgroundColor='rgba(45, 75, 51, 0.1)'; highlightFaceBox('${person.person_id}', true)"
                      onmouseout="this.style.backgroundColor='transparent'; highlightFaceBox('${person.person_id}', false)"
                      onclick="gotoPersonDossier('${person.person_id}')">
                   ${person.photo_file
                     ? `<img src="/photos/${person.photo_file}" alt="${displayName}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3); flex-shrink: 0;">`
                     : `<div style="width: 32px; height: 32px; border-radius: 50%; background-color: #f1eee5; flex-shrink: 0; display: flex; align-items: center; justify-content: center;">${personSvg(person.sex, person.birth_year, person.death_year, 20)}</div>`}
                   <span style="font-size: 13px; color: #1c1c17; flex: 1;">${displayName}</span>
                 </div>
               `}).join('')}
             </div>
           </div>`
        : '';

    // Álbums: MH album + virtual doc-type album
    const albumItems = [];
    if (p.album_title) {
        albumItems.push(
            `<a href="/albums.html#${p.album_id}" style="display:flex;align-items:center;gap:8px;font-size:13px;color:#2D4B33;font-weight:600;text-decoration:none;"
                onmouseover="this.style.textDecoration='underline'" onmouseout="this.style.textDecoration='none'">
               <span class="material-symbols-outlined" style="font-size:16px;color:#727971;">photo_album</span>
               ${p.album_title}
             </a>`
        );
    }
    if (p.is_document && p.doc_type) {
        const meta = _DOC_TYPE_META[p.doc_type] || (window.docTypeMeta || {})[p.doc_type] || { label: 'Documentos', icon: '/icons/documentacion.svg' };
        albumItems.push(
            `<div style="display:flex;align-items:center;gap:8px;font-size:13px;color:#2D4B33;font-weight:600;">
               <img src="${meta.icon}" style="width:16px;height:16px;flex-shrink:0;" alt="">
               ${meta.label}
             </div>`
        );
    }
    const albumHtml = albumItems.length
        ? `<div style="margin-bottom: 28px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px 0;">Álbums</h3>
             <div style="display:flex;flex-direction:column;gap:8px;">${albumItems.join('')}</div>
           </div>`
        : '';

    sidebarContent = `${breadcrumbHtml}${infoHtml}${noteHtml}${tagsHtml}${albumHtml}`;

    const modalHtml = `
        <style>
            #photo-sidebar {
                transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                            padding 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                            border-right 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
                overflow: hidden;
            }

            #photo-sidebar-content {
                transition: opacity 0.3s ease-out;
                opacity: 1;
            }

            #photo-area {
                transition: flex 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            }
        </style>

        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #fcf9f0; display: flex; flex-direction: row;">
            <!-- Sidebar (left) -->
            <div id="photo-sidebar" style="width: 320px; padding: 32px 24px 24px 24px; border-right: 1px solid rgba(114, 121, 113, 0.2); overflow-y: auto; background-color: #fcf9f0; flex-shrink: 0;">
                <div id="photo-sidebar-content" style="opacity: 1;">
                    ${sidebarContent}
                </div>
            </div>

            <!-- Photo area -->
            <div id="photo-area" style="flex: 1; display: flex; flex-direction: column; position: relative; min-width: 0; overflow: visible;">
                <!-- Toggle sidebar button -->
                <button id="toggle-sidebar-btn" onclick="togglePhotoSidebar()" title="Ocultar panel" style="position: absolute; top: 16px; left: 16px; z-index: 50; width: 40px; height: 40px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33; border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: all 0.2s;">
                    ←
                </button>

                <!-- Zoom button -->
                <button onclick="enterZoomMode()" title="Zoom x4" style="position: absolute; top: 16px; right: 66px; z-index: 50; width: 40px; height: 40px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33; border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: all 0.2s;"
                    onmouseover="this.style.backgroundColor='#2D4B33';this.style.color='white'"
                    onmouseout="this.style.backgroundColor='rgba(252,249,240,0.95)';this.style.color='#2D4B33'">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                </button>

                <!-- Close button (top right) -->
                <button onclick="closePhotoModal()" title="Cerrar" style="position: absolute; top: 16px; right: 16px; z-index: 50; width: 40px; height: 40px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33; border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: all 0.2s;">
                    ✕
                </button>

                <!-- Prev arrow -->
                ${ctx?.onPrev ? `<button onclick="window.__photoModalContext.onPrev()" title="Anterior"
                    style="position: absolute; left: 16px; top: 50%; transform: translateY(-50%); z-index: 50;
                           width: 44px; height: 44px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33;
                           border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer;
                           font-size: 22px; display: flex; align-items: center; justify-content: center;
                           box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.2s;"
                    onmouseover="this.style.backgroundColor='#2D4B33';this.style.color='white'"
                    onmouseout="this.style.backgroundColor='rgba(252,249,240,0.95)';this.style.color='#2D4B33'">‹</button>` : ''}

                <!-- Next arrow -->
                ${ctx?.onNext ? `<button onclick="window.__photoModalContext.onNext()" title="Siguiente"
                    style="position: absolute; right: 16px; top: 50%; transform: translateY(-50%); z-index: 50;
                           width: 44px; height: 44px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33;
                           border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer;
                           font-size: 22px; display: flex; align-items: center; justify-content: center;
                           box-shadow: 0 2px 8px rgba(0,0,0,0.1); transition: all 0.2s;"
                    onmouseover="this.style.backgroundColor='#2D4B33';this.style.color='white'"
                    onmouseout="this.style.backgroundColor='rgba(252,249,240,0.95)';this.style.color='#2D4B33'">›</button>` : ''}

                <!-- Photo container -->
                <div id="photo-container" style="flex: 1; display: flex; align-items: center; justify-content: center; background-color: #e5e2da; position: relative; overflow: hidden; padding: 24px;">
                    <div id="photo-wrapper" style="position: relative; display: inline-block;">
                        <img
                            src="/photos/${p.filename}"
                            alt="${escHtml(p.title || 'Foto')}"
                            style="max-width: 100%; max-height: calc(100vh - 48px); object-fit: contain; display: block;"
                            id="modal-photo"
                            onload="attachFaceBoxes()"
                        >
                        <div id="face-boxes-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('photo-modal-content').innerHTML = modalHtml;
}

/**
 * Attach face box tooltips to the modal photo using percentage-based positioning.
 * Percentages scale automatically when the image resizes, so no recalculation needed.
 */
function attachFaceBoxes() {
    if (!_currentPhotoData || !_currentPhotoData.tagged_people) return;

    const imgElement = document.getElementById('modal-photo');
    const container = document.getElementById('face-boxes-container');

    if (!imgElement || !container) return;

    // Wait for the image to fully render
    setTimeout(() => {
        container.innerHTML = '';

        const natW = imgElement.naturalWidth;
        const natH = imgElement.naturalHeight;
        if (!natW || !natH) return;

        _currentPhotoData.tagged_people.forEach(person => {
            if (!person.position) return;

            const coords = person.position.split(' ').map(Number);
            if (coords.length !== 4) return;

            const [x1, y1, x2, y2] = coords;

            // Convert to percentages of the natural image dimensions
            const leftPct = (x1 / natW * 100).toFixed(4);
            const topPct = (y1 / natH * 100).toFixed(4);
            const widthPct = ((x2 - x1) / natW * 100).toFixed(4);
            const heightPct = ((y2 - y1) / natH * 100).toFixed(4);

            const box = document.createElement('div');
            box.setAttribute('data-person-box', person.person_id);
            box.style.cssText = `
                position: absolute;
                left: ${leftPct}%;
                top: ${topPct}%;
                width: ${widthPct}%;
                height: ${heightPct}%;
                cursor: pointer;
                box-sizing: border-box;
                border-radius: 4px;
                transition: border 0.2s, box-shadow 0.2s;
            `;

            const tooltip = document.createElement('div');
            tooltip.textContent = person.name;
            tooltip.style.cssText = `
                position: absolute;
                top: calc(100% + 6px);
                left: 50%;
                transform: translateX(-50%);
                background-color: #2D4B33;
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                white-space: nowrap;
                opacity: 0;
                transition: opacity 0.2s;
                pointer-events: none;
                z-index: 100;
            `;

            box.appendChild(tooltip);

            box.addEventListener('mouseenter', () => {
                tooltip.style.opacity = '1';
                box.style.border = '3px solid #2D4B33';
                box.style.boxShadow = '0 0 0 2px rgba(255, 255, 255, 0.8)';
            });
            box.addEventListener('mouseleave', () => {
                tooltip.style.opacity = '0';
                box.style.border = 'none';
                box.style.boxShadow = 'none';
            });

            box.addEventListener('click', () => {
                gotoPersonDossier(person.person_id);
            });

            container.appendChild(box);
        });
    }, 50);
}

/**
 * Initialize modal HTML in page (must be called once on page load)
 */
window.initPhotoModal = function() {
    // Create modal HTML if it doesn't exist
    if (!document.getElementById('photo-modal-overlay')) {
        const modalHtml = `
            <div id="photo-modal-overlay" style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: rgba(0, 0, 0, 0.5);
                z-index: 1000;
                display: none;
                align-items: center;
                justify-content: center;
            ">
                <div id="photo-modal-content" style="width: 100%; height: 100%;"></div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
};

// Auto-initialize when script loads
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPhotoModal);
} else {
    initPhotoModal();
}

// ---------------------------------------------------------------------------
// Zoom mode
// ---------------------------------------------------------------------------

let _zoomLevel = 4;

function _zoomMouseMove(e) {
    const img = document.getElementById('zoom-mode-img');
    if (!img) return;
    const dx = e.clientX - window.innerWidth / 2;
    const dy = e.clientY - window.innerHeight / 2;
    // translate is in scaled space: viewport offset = scale × translate
    // to pan by (N-1)×dx in viewport, translate = -dx×(N-1)/N
    const f = (_zoomLevel - 1) / _zoomLevel;
    img.style.transform = `scale(${_zoomLevel}) translate(${-dx * f}px, ${-dy * f}px)`;
}

function _applyZoom(delta) {
    _zoomLevel = Math.max(1, Math.min(10, _zoomLevel + delta));
    const label = document.getElementById('zoom-level-label');
    if (label) label.textContent = `${_zoomLevel}×`;
    const img = document.getElementById('zoom-mode-img');
    if (img) img.style.transform = `scale(${_zoomLevel}) translate(0px,0px)`;
}

function _zoomKeyHandler(e) {
    if (e.key === 'Escape') exitZoomMode();
}

function _makeZoomBtn(label, title, clickFn) {
    const b = document.createElement('button');
    b.title = title;
    b.innerHTML = label;
    b.style.cssText = [
        'width:40px', 'height:40px', 'background:rgba(252,249,240,0.95)',
        'color:#2D4B33', 'border:1px solid rgba(114,121,113,0.3)',
        'border-radius:50%', 'cursor:pointer', 'font-size:20px',
        'display:flex', 'align-items:center', 'justify-content:center',
        'box-shadow:0 2px 8px rgba(0,0,0,0.2)', 'flex-shrink:0',
    ].join(';');
    b.onclick = clickFn;
    return b;
}

window.enterZoomMode = function() {
    if (!_currentPhotoData || document.getElementById('zoom-mode-overlay')) return;
    _zoomLevel = 4;

    const overlay = document.createElement('div');
    overlay.id = 'zoom-mode-overlay';
    overlay.style.cssText = [
        'position:fixed', 'top:0', 'left:0', 'width:100%', 'height:100%',
        'z-index:2000', 'background:#000', 'overflow:hidden', 'cursor:crosshair',
    ].join(';');

    const img = document.createElement('img');
    img.id = 'zoom-mode-img';
    img.src = `/photos/${_currentPhotoData.filename}`;
    img.style.cssText = [
        'position:absolute', 'top:0', 'left:0', 'width:100%', 'height:100%',
        'object-fit:contain', 'transform-origin:center center',
        `transform:scale(${_zoomLevel})`, 'pointer-events:none',
    ].join(';');

    // Close button (top-right)
    const closeBtn = _makeZoomBtn('✕', 'Cerrar zoom (Esc)', exitZoomMode);
    closeBtn.style.cssText += ';position:absolute;top:16px;right:16px;z-index:10;font-size:18px;';

    // +/- controls (bottom-center)
    const controls = document.createElement('div');
    controls.style.cssText = [
        'position:absolute', 'bottom:24px', 'left:50%', 'transform:translateX(-50%)',
        'display:flex', 'align-items:center', 'gap:12px', 'z-index:10',
    ].join(';');

    const minusBtn = _makeZoomBtn('−', 'Reducir zoom', () => _applyZoom(-1));
    const plusBtn  = _makeZoomBtn('+', 'Ampliar zoom',  () => _applyZoom(+1));

    const label = document.createElement('span');
    label.id = 'zoom-level-label';
    label.textContent = `${_zoomLevel}×`;
    label.style.cssText = [
        'color:rgba(255,255,255,0.85)', 'font-size:15px', 'font-weight:700',
        'min-width:36px', 'text-align:center', 'letter-spacing:0.03em',
    ].join(';');

    controls.appendChild(minusBtn);
    controls.appendChild(label);
    controls.appendChild(plusBtn);

    overlay.appendChild(img);
    overlay.appendChild(closeBtn);
    overlay.appendChild(controls);
    document.body.appendChild(overlay);

    overlay.addEventListener('mousemove', _zoomMouseMove);
    document.addEventListener('keydown', _zoomKeyHandler);
};

function exitZoomMode() {
    const overlay = document.getElementById('zoom-mode-overlay');
    if (!overlay) return;
    overlay.removeEventListener('mousemove', _zoomMouseMove);
    document.removeEventListener('keydown', _zoomKeyHandler);
    overlay.remove();
}
