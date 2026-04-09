/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 * Works with both Tailwind and standard CSS
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
    const tagsHtml = p.tagged_people && p.tagged_people.length > 0
        ? `<div style="display: flex; flex-direction: column; gap: 8px;">
             ${p.tagged_people.map(person => `
               <div style="display: flex; align-items: center; gap: 8px;">
                 ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover; border: 1px solid rgba(114, 121, 113, 0.3);">` : `<div style="width: 24px; height: 24px; border-radius: 50%; background-color: #f1eee5;"></div>`}
                 <span style="font-size: 14px;">${person.name}</span>
               </div>
             `).join('')}
           </div>`
        : '<span style="font-size: 14px; color: #727971;">Sin personas etiquetadas</span>';

    const infoHtml = [
        p.date ? `<div style="border-bottom: 1px solid rgba(114, 121, 113, 0.2); padding-bottom: 12px;"><span style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em;">Fecha</span><div style="font-size: 14px; margin-top: 4px;">${p.date}</div></div>` : '',
        p.place ? `<div style="border-bottom: 1px solid rgba(114, 121, 113, 0.2); padding-bottom: 12px;"><span style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em;">Lugar</span><div style="font-size: 14px; margin-top: 4px;">${p.place}</div></div>` : '',
        p.album_title ? `<div><span style="font-size: 11px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em;">Álbum</span><div style="font-size: 14px; margin-top: 4px;">${p.album_title}</div></div>` : ''
    ].filter(Boolean).join('');

    const modalHtml = `
        <div style="background-color: #fcf9f0; border-radius: 12px; max-width: 1200px; width: 100%; margin: 0 16px; max-height: 90vh; overflow-y: auto; box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);">
            <!-- Header with close button -->
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 24px; border-bottom: 1px solid rgba(114, 121, 113, 0.2); flex-shrink: 0;">
                <h2 style="font-size: 24px; font-weight: bold; color: #2D4B33; flex: 1; font-family: 'Noto Serif', serif; margin: 0;">
                    ${p.title || 'Foto sin título'}
                </h2>
                <button onclick="closePhotoModal()" style="padding: 8px; background: none; border: none; cursor: pointer; color: #2D4B33; font-size: 24px;">
                    ✕
                </button>
            </div>

            <!-- Main content -->
            <div style="flex: 1; overflow-y: auto; padding: 24px;">
                <div style="display: grid; grid-template-columns: 1fr; gap: 32px; margin-bottom: 24px;">
                    <!-- Large photo -->
                    <div style="grid-column: 1 / -1;">
                        <div style="position: relative; background-color: #e5e2da; overflow: hidden; border-radius: 8px; border: 1px solid rgba(114, 121, 113, 0.2); display: flex; align-items: center; justify-content: center; max-height: 60vh;">
                            <img
                                src="/photos/${p.filename}"
                                alt="${p.title || 'Foto'}"
                                style="max-width: 100%; max-height: 100%; object-fit: contain;"
                                id="modal-photo"
                                onload="attachFaceBoxesTool()"
                            >
                            <div id="face-boxes-container" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none;"></div>
                        </div>
                    </div>
                </div>

                <!-- Info and people -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 32px; padding-top: 24px; border-top: 1px solid rgba(114, 121, 113, 0.2);">
                    <!-- Info boxes -->
                    <div style="display: flex; flex-direction: column; gap: 16px;">
                        ${infoHtml ? infoHtml : ''}
                    </div>

                    <!-- Tagged people -->
                    <div>
                        <h3 style="font-size: 12px; font-weight: bold; color: #727971; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 12px; margin-top: 0;">Personas etiquetadas</h3>
                        ${tagsHtml}
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
function attachFaceBoxesTool() {
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

            // Create box element with tooltip
            const box = document.createElement('div');
            box.style.cssText = `
                position: absolute;
                left: ${left}px;
                top: ${top}px;
                width: ${width}px;
                height: ${height}px;
                border: 2px solid #2D4B33;
                border-radius: 4px;
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
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                white-space: nowrap;
                opacity: 0;
                transition: opacity 0.2s;
                pointer-events: none;
                z-index: 10;
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
                overflow-y: auto;
            " onclick="if(event.target === this) closePhotoModal()">
                <div id="photo-modal-content"></div>
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
