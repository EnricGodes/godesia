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
 * Toggle sidebar visibility
 */
window.togglePhotoSidebar = function() {
    _sidebarVisible = !_sidebarVisible;
    renderPhotoModal();
};

/**
 * Navigate to person's dossier
 */
window.gotoPersonDossier = function(personId) {
    personId = personId.replace(/@/g, '');
    window.location.href = `/dossier.html?id=${personId}`;
};

/**
 * Render the modal content
 */
function renderPhotoModal() {
    if (!_currentPhotoData) return;

    const p = _currentPhotoData;
    const sidebarWidth = _sidebarVisible ? 300 : 0;

    // Build sidebar content
    let sidebarHtml = '';

    if (_sidebarVisible) {
        // Title, date, place
        let infoHtml = '';
        if (p.title) {
            infoHtml += `<h2 style="font-size: 20px; font-weight: bold; color: #2D4B33; font-family: 'Noto Serif', serif; margin: 0 0 12px 0;">${p.title}</h2>`;
        }
        if (p.date || p.place) {
            let datePlace = [];
            if (p.date) datePlace.push(p.date);
            if (p.place) datePlace.push(p.place);
            infoHtml += `<div style="font-size: 13px; color: #727971; margin-bottom: 24px;">${datePlace.join(' • ')}</div>`;
        }

        // Personas etiquetadas
        const tagsHtml = p.tagged_people && p.tagged_people.length > 0
            ? `<div style="margin-bottom: 24px;">
                 <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em; margin: 0 0 12px 0;">Personas Etiquetadas</h3>
                 <div style="display: flex; flex-direction: column; gap: 10px;">
                   ${p.tagged_people.map(person => `
                     <div style="display: flex; align-items: center; gap: 10px; cursor: pointer; padding: 8px; border-radius: 6px; transition: background-color 0.2s;" onmouseover="this.style.backgroundColor='rgba(45, 75, 51, 0.1)'" onmouseout="this.style.backgroundColor='transparent'" onclick="gotoPersonDossier('${person.person_id}')">
                       ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3); flex-shrink: 0;">` : `<div style="width: 32px; height: 32px; border-radius: 50%; background-color: #f1eee5; flex-shrink: 0;"></div>`}
                       <span style="font-size: 13px; color: #1c1c17; flex: 1;">${person.name}</span>
                     </div>
                   `).join('')}
                 </div>
               </div>`
            : '';

        // Álbum
        const albumHtml = p.album_title
            ? `<div style="margin-bottom: 24px;">
                 <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em; margin: 0 0 8px 0;">Álbum</h3>
                 <div style="font-size: 13px; color: #1c1c17;">${p.album_title}</div>
               </div>`
            : '';

        sidebarHtml = `
            <div style="width: 300px; padding: 24px; border-left: 1px solid rgba(114, 121, 113, 0.2); overflow-y: auto; background-color: #fcf9f0;">
                ${infoHtml}
                ${tagsHtml}
                ${albumHtml}
            </div>
        `;
    }

    const modalHtml = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #fcf9f0; display: flex; flex-direction: row;">
            <!-- Photo area -->
            <div style="flex: 1; display: flex; flex-direction: column; position: relative;">
                <!-- Toggle button -->
                <button onclick="togglePhotoSidebar()" style="position: absolute; top: 16px; right: 16px; z-index: 50; padding: 8px 12px; background-color: rgba(45, 75, 51, 0.9); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; text-transform: uppercase;">
                    ${_sidebarVisible ? '✕' : '☰'}
                </button>

                <!-- Close button -->
                <button onclick="closePhotoModal()" style="position: absolute; top: 16px; left: 16px; z-index: 50; padding: 8px 12px; background-color: rgba(45, 75, 51, 0.9); color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 14px;">✕</button>

                <!-- Photo container -->
                <div style="flex: 1; display: flex; align-items: center; justify-content: center; background-color: #e5e2da; position: relative; overflow: hidden;">
                    <img
                        src="/photos/${p.filename}"
                        alt="${p.title || 'Foto'}"
                        style="max-width: 100%; max-height: 100%; object-fit: contain; display: block;"
                        id="modal-photo"
                        onload="attachFaceBoxes()"
                    >
                    <div id="face-boxes-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;"></div>
                </div>
            </div>

            <!-- Sidebar -->
            ${sidebarHtml}
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
    const container = document.getElementById('face-boxes-container');

    if (!imgElement || !container) return;

    // Clear existing boxes
    container.innerHTML = '';

    const img = new Image();
    img.src = imgElement.src;

    img.onload = function() {
        // Get actual displayed image dimensions
        const imgDisplayWidth = imgElement.offsetWidth;
        const imgDisplayHeight = imgElement.offsetHeight;

        // Get natural image dimensions
        const imgNaturalWidth = img.naturalWidth;
        const imgNaturalHeight = img.naturalHeight;

        // Calculate scale factors
        const scaleX = imgDisplayWidth / imgNaturalWidth;
        const scaleY = imgDisplayHeight / imgNaturalHeight;

        _currentPhotoData.tagged_people.forEach(person => {
            if (!person.position) return;

            const coords = person.position.split(' ').map(Number);
            if (coords.length !== 4) return;

            const [x1, y1, x2, y2] = coords;

            // Scale coordinates to displayed size
            const displayX1 = x1 * scaleX;
            const displayY1 = y1 * scaleY;
            const displayX2 = x2 * scaleX;
            const displayY2 = y2 * scaleY;

            const left = displayX1;
            const top = displayY1;
            const width = displayX2 - displayX1;
            const height = displayY2 - displayY1;

            // Create box element
            const box = document.createElement('div');
            box.style.cssText = `
                position: absolute;
                left: ${left}px;
                top: ${top}px;
                width: ${width}px;
                height: ${height}px;
                cursor: pointer;
            `;

            // Create tooltip
            const tooltip = document.createElement('div');
            tooltip.textContent = person.name;
            tooltip.style.cssText = `
                position: absolute;
                top: 100%;
                left: 50%;
                transform: translateX(-50%);
                margin-top: 6px;
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

            // Show tooltip on hover
            box.addEventListener('mouseenter', () => {
                tooltip.style.opacity = '1';
            });
            box.addEventListener('mouseleave', () => {
                tooltip.style.opacity = '0';
            });

            container.appendChild(box);
        });
    };
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
            " onclick="if(event.target === this) closePhotoModal()">
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
