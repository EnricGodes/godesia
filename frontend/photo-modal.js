/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 */

let _currentPhotoData = null;
let _sidebarVisible = true;

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
    const photoArea = document.getElementById('photo-area');

    if (!sidebar || !photoArea) return;

    if (_sidebarVisible) {
        // Show sidebar
        sidebar.style.width = '320px';
        sidebar.style.opacity = '1';
        sidebar.style.visibility = 'visible';
        photoArea.style.flex = '1';
    } else {
        // Hide sidebar
        sidebar.style.width = '0px';
        sidebar.style.opacity = '0';
        sidebar.style.visibility = 'hidden';
        photoArea.style.flex = '1';
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
                 return `
                 <div style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 8px; border-radius: 6px; transition: background-color 0.2s;"
                      onmouseover="this.style.backgroundColor='rgba(45, 75, 51, 0.1)'; highlightFaceBox('${person.person_id}', true)"
                      onmouseout="this.style.backgroundColor='transparent'; highlightFaceBox('${person.person_id}', false)"
                      onclick="gotoPersonDossier('${person.person_id}')">
                   ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3); flex-shrink: 0;">` : `<div style="width: 32px; height: 32px; border-radius: 50%; background-color: #f1eee5; flex-shrink: 0;"></div>`}
                   <span style="font-size: 13px; color: #1c1c17; flex: 1;">${person.name}</span>
                 </div>
               `}).join('')}
             </div>
           </div>`
        : '';

    // Álbum con foto de portada
    const albumHtml = p.album_title
        ? `<div style="margin-bottom: 24px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.08em; margin: 0 0 12px 0;">Álbum</h3>
             ${p.album_cover ? `<div style="width: 100%; height: 140px; border-radius: 6px; overflow: hidden; margin-bottom: 10px; border: 1px solid rgba(114, 121, 113, 0.2);"><img src="/photos/${p.album_cover}" alt="${p.album_title}" style="width: 100%; height: 100%; object-fit: cover; display: block;"></div>` : ''}
             <div style="font-size: 13px; color: #1c1c17; font-weight: 600;">${p.album_title}</div>
           </div>`
        : '';

    sidebarContent = `${infoHtml}${tagsHtml}${albumHtml}`;

    const modalHtml = `
        <style>
            @keyframes slideOutLeft {
                from {
                    width: 320px;
                    opacity: 1;
                }
                to {
                    width: 0px;
                    opacity: 0;
                }
            }

            @keyframes slideInRight {
                from {
                    width: 0px;
                    opacity: 0;
                }
                to {
                    width: 320px;
                    opacity: 1;
                }
            }

            #photo-sidebar {
                transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                            opacity 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94),
                            visibility 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            }

            #photo-area {
                transition: flex 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
            }
        </style>

        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #fcf9f0; display: flex; flex-direction: row;">
            <!-- Sidebar (left) -->
            <div id="photo-sidebar" style="width: 320px; padding: 32px 24px 24px 24px; border-right: 1px solid rgba(114, 121, 113, 0.2); overflow-y: auto; background-color: #fcf9f0; flex-shrink: 0; opacity: 1; visibility: visible;">
                ${sidebarContent}
            </div>

            <!-- Photo area -->
            <div id="photo-area" style="flex: 1; display: flex; flex-direction: column; position: relative; min-width: 0;">
                <!-- Toggle sidebar button -->
                <button onclick="togglePhotoSidebar()" title="${_sidebarVisible ? 'Ocultar panel' : 'Mostrar panel'}" style="position: absolute; top: 16px; left: 16px; z-index: 50; width: 40px; height: 40px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33; border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: all 0.2s;">
                    ${_sidebarVisible ? '←' : '→'}
                </button>

                <!-- Close button (top right) -->
                <button onclick="closePhotoModal()" title="Cerrar" style="position: absolute; top: 16px; right: 16px; z-index: 50; width: 40px; height: 40px; background-color: rgba(252, 249, 240, 0.95); color: #2D4B33; border: 1px solid rgba(114, 121, 113, 0.3); border-radius: 50%; cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); transition: all 0.2s;">
                    ✕
                </button>

                <!-- Photo container -->
                <div style="flex: 1; display: flex; align-items: center; justify-content: center; background-color: #e5e2da; position: relative; overflow: hidden; padding: 24px;">
                    <div id="photo-wrapper" style="position: relative; max-width: 100%; max-height: 100%; display: inline-block;">
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
 * Attach face box tooltips to the modal photo
 */
function attachFaceBoxes() {
    if (!_currentPhotoData || !_currentPhotoData.tagged_people) return;

    const imgElement = document.getElementById('modal-photo');
    const wrapper = document.getElementById('photo-wrapper');
    const container = document.getElementById('face-boxes-container');

    if (!imgElement || !container || !wrapper) return;

    // Wait a moment for the image to fully render
    setTimeout(() => {
        // Clear existing boxes
        container.innerHTML = '';

        // Get actual displayed image dimensions
        const imgDisplayWidth = imgElement.clientWidth;
        const imgDisplayHeight = imgElement.clientHeight;

        // Resize wrapper to match image exactly
        wrapper.style.width = imgDisplayWidth + 'px';
        wrapper.style.height = imgDisplayHeight + 'px';

        // Get natural image dimensions
        const imgNaturalWidth = imgElement.naturalWidth;
        const imgNaturalHeight = imgElement.naturalHeight;

        if (!imgNaturalWidth || !imgNaturalHeight) return;

        // Calculate scale factors
        const scaleX = imgDisplayWidth / imgNaturalWidth;
        const scaleY = imgDisplayHeight / imgNaturalHeight;

        _currentPhotoData.tagged_people.forEach(person => {
            if (!person.position) return;

            const coords = person.position.split(' ').map(Number);
            if (coords.length !== 4) return;

            const [x1, y1, x2, y2] = coords;

            // Scale coordinates to displayed size
            const left = x1 * scaleX;
            const top = y1 * scaleY;
            const width = (x2 - x1) * scaleX;
            const height = (y2 - y1) * scaleY;

            // Create box element
            const box = document.createElement('div');
            box.setAttribute('data-person-box', person.person_id);
            box.style.cssText = `
                position: absolute;
                left: ${left}px;
                top: ${top}px;
                width: ${width}px;
                height: ${height}px;
                cursor: pointer;
                box-sizing: border-box;
                border-radius: 4px;
                transition: border 0.2s, box-shadow 0.2s;
            `;

            // Create tooltip
            const tooltip = document.createElement('div');
            tooltip.textContent = person.name;
            tooltip.className = 'face-tooltip';
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

            // Show tooltip and highlight box on hover
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

            // Click to navigate
            box.addEventListener('click', () => {
                gotoPersonDossier(person.person_id);
            });

            container.appendChild(box);
        });
    }, 50);
}

// Re-attach face boxes on window resize
window.addEventListener('resize', () => {
    if (_currentPhotoData) {
        attachFaceBoxes();
    }
});

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
