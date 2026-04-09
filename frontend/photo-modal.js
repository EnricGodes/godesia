/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 */

let _currentPhotoData = null;

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
 * Render the modal content
 */
function renderPhotoModal() {
    if (!_currentPhotoData) return;

    const p = _currentPhotoData;

    // Build info sections
    const infoSections = [];

    if (p.date || p.place) {
        let datePlace = [];
        if (p.date) datePlace.push(p.date);
        if (p.place) datePlace.push(p.place);
        infoSections.push(`<div style="margin-bottom: 20px;"><div style="font-size: 13px; color: #727971;">${datePlace.join(' • ')}</div></div>`);
    }

    // Personas etiquetadas
    const tagsHtml = p.tagged_people && p.tagged_people.length > 0
        ? `<div style="margin-bottom: 24px;">
             <h3 style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em; margin: 0 0 12px 0;">Personas Etiquetadas</h3>
             <div style="display: flex; flex-direction: column; gap: 8px;">
               ${p.tagged_people.map(person => `
                 <div style="display: flex; align-items: center; gap: 8px;">
                   ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" style="width: 28px; height: 28px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3); flex-shrink: 0;">` : `<div style="width: 28px; height: 28px; border-radius: 50%; background-color: #f1eee5; flex-shrink: 0;"></div>`}
                   <span style="font-size: 13px; color: #1c1c17;">${person.name}</span>
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

    const modalHtml = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: #fcf9f0; display: flex; flex-direction: column;">
            <!-- Header -->
            <div style="padding: 24px; border-bottom: 1px solid rgba(114, 121, 113, 0.2); flex-shrink: 0;">
                <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 16px;">
                    <div style="flex: 1;">
                        <h1 style="font-size: 32px; font-weight: bold; color: #2D4B33; font-family: 'Noto Serif', serif; margin: 0 0 12px 0;">
                            ${p.title || 'Foto sin título'}
                        </h1>
                        <div style="font-size: 13px; color: #727971;">${p.date ? p.date : ''}${p.place ? (p.date ? ' • ' : '') + p.place : ''}</div>
                    </div>
                    <button onclick="closePhotoModal()" style="padding: 8px 12px; background: none; border: none; cursor: pointer; color: #2D4B33; font-size: 28px; line-height: 1;">✕</button>
                </div>
            </div>

            <!-- Main content -->
            <div style="flex: 1; display: flex; gap: 24px; padding: 24px; overflow: hidden;">
                <!-- Photo container -->
                <div style="flex: 1; display: flex; align-items: center; justify-content: center; background-color: #e5e2da; border-radius: 8px; border: 1px solid rgba(114, 121, 113, 0.2); position: relative; min-width: 0;">
                    <img
                        src="/photos/${p.filename}"
                        alt="${p.title || 'Foto'}"
                        style="max-width: 100%; max-height: 100%; object-fit: contain; display: block;"
                        id="modal-photo"
                        onload="attachFaceBoxes()"
                    >
                    <div id="face-boxes-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></div>
                </div>

                <!-- Right sidebar -->
                <div style="width: 280px; display: flex; flex-direction: column; gap: 0; overflow-y: auto;">
                    ${tagsHtml}
                    ${albumHtml}
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
    const container = document.getElementById('face-boxes-container');

    if (!imgElement || !container) return;

    // Clear existing boxes
    container.innerHTML = '';

    const img = new Image();
    img.src = imgElement.src;

    img.onload = function() {
        const imgWidth = imgElement.offsetWidth;
        const imgHeight = imgElement.offsetHeight;
        const imgRect = imgElement.getBoundingClientRect();
        const containerRect = container.getBoundingClientRect();

        const naturalWidth = img.naturalWidth;
        const naturalHeight = img.naturalHeight;

        _currentPhotoData.tagged_people.forEach(person => {
            if (!person.position) return;

            const coords = person.position.split(' ').map(Number);
            if (coords.length !== 4) return;

            const [x1, y1, x2, y2] = coords;

            // Scale to displayed image size
            const scaleX = imgWidth / naturalWidth;
            const scaleY = imgHeight / naturalHeight;

            const left = x1 * scaleX;
            const top = y1 * scaleY;
            const width = (x2 - x1) * scaleX;
            const height = (y2 - y1) * scaleY;

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
                bottom: 100%;
                left: 50%;
                transform: translateX(-50%);
                margin-bottom: 8px;
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
