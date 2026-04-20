/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 */

let _currentPhotoData = null;
let _sidebarVisible = true;

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
        infoHtml += `<h2 style="font-size: 22px; font-weight: bold; color: #2D4B33; font-family: 'Noto Serif', serif; margin: 0 0 12px 0; line-height: 1.3;">${p.title}</h2>`;
    }
    if (p.date || p.place) {
        let datePlace = [];
        if (p.date) datePlace.push(p.date);
        if (p.place) datePlace.push(p.place);
        infoHtml += `<div style="font-size: 13px; color: #727971; margin-bottom: 28px;">${datePlace.join(' • ')}</div>`;
    }

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
                   ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${displayName}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3); flex-shrink: 0;">` : `<div style="width: 32px; height: 32px; border-radius: 50%; background-color: #f1eee5; flex-shrink: 0;"></div>`}
                   <span style="font-size: 13px; color: #1c1c17; flex: 1;">${displayName}</span>
                 </div>
               `}).join('')}
             </div>
           </div>`
        : '';

    // Álbum
    const albumHtml = p.album_title
        ? `<div style="margin-bottom: 28px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px 0;">Álbum</h3>
             <div style="font-size: 13px; color: #1c1c17;">${p.album_title}</div>
           </div>`
        : '';

    sidebarContent = `${breadcrumbHtml}${infoHtml}${tagsHtml}${albumHtml}`;

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
                            alt="${p.title || 'Foto'}"
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
