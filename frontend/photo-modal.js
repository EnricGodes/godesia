/**
 * Photo Modal Module
 * Global modal for viewing photos in detail across the entire application
 */

let _currentPhotoData = null;
let _tooltipTimeout = null;

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
        document.getElementById('photo-modal-overlay').style.display = 'flex';
        document.body.style.overflow = 'hidden';
    } catch (e) {
        console.error('Error loading photo:', e);
    }
};

/**
 * Close photo modal
 */
window.closePhotoModal = function() {
    document.getElementById('photo-modal-overlay').style.display = 'none';
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
        ? `<div class="space-y-2">
             ${p.tagged_people.map(person => `
               <div class="flex items-center gap-2">
                 ${person.photo_file ? `<img src="/photos/${person.photo_file}" alt="${person.name}" class="w-6 h-6 rounded-full object-cover border border-outline-variant/30">` : '<div class="w-6 h-6 rounded-full bg-surface-container"></div>'}
                 <span class="text-sm">${person.name}</span>
               </div>
             `).join('')}
           </div>`
        : '<span class="text-sm text-outline">Sin personas etiquetadas</span>';

    const infoHtml = [
        p.date ? `<div><span class="text-xs uppercase tracking-widest font-bold text-outline">Fecha</span><div class="text-sm">${p.date}</div></div>` : '',
        p.place ? `<div><span class="text-xs uppercase tracking-widest font-bold text-outline">Lugar</span><div class="text-sm">${p.place}</div></div>` : '',
        p.album_title ? `<div><span class="text-xs uppercase tracking-widest font-bold text-outline">Álbum</span><div class="text-sm">${p.album_title}</div></div>` : ''
    ].filter(Boolean).join('');

    const modalHtml = `
        <div class="bg-surface rounded-xl max-w-6xl w-full mx-4 max-h-[90vh] overflow-y-auto flex flex-col shadow-2xl">
            <!-- Header with close button -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-outline-variant/20 flex-shrink-0">
                <h2 class="font-headline text-2xl font-bold text-primary flex-1">
                    ${p.title || 'Foto sin título'}
                </h2>
                <button onclick="closePhotoModal()" class="p-2 hover:bg-surface-container rounded-full transition-colors">
                    <span class="material-symbols-outlined text-primary">close</span>
                </button>
            </div>

            <!-- Main content -->
            <div class="flex-1 overflow-y-auto p-6">
                <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    <!-- Large photo -->
                    <div class="lg:col-span-2">
                        <div class="relative bg-surface-container-highest overflow-hidden rounded-lg heritage-border aspect-auto max-h-[60vh] flex items-center justify-center">
                            <img
                                src="/photos/${p.filename}"
                                alt="${p.title || 'Foto'}"
                                class="max-w-full max-h-full object-contain"
                                id="modal-photo"
                                onload="attachFaceBoxesTool()"
                            >
                            <div id="face-boxes-container" class="absolute inset-0 pointer-events-none"></div>
                        </div>
                    </div>

                    <!-- Right sidebar with info -->
                    <div class="space-y-6">
                        <!-- Info boxes -->
                        ${infoHtml ? `<div class="space-y-4">${infoHtml}</div>` : ''}

                        <!-- Tagged people -->
                        <div>
                            <h3 class="text-sm font-bold uppercase tracking-widest text-outline mb-3">Personas etiquetadas</h3>
                            ${tagsHtml}
                        </div>
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

            // Create box element
            const box = document.createElement('div');
            box.className = 'absolute border-2 border-primary rounded opacity-0 hover:opacity-100 transition-opacity group cursor-pointer';
            box.style.left = left + 'px';
            box.style.top = top + 'px';
            box.style.width = width + 'px';
            box.style.height = height + 'px';

            // Create tooltip
            const tooltip = document.createElement('div');
            tooltip.className = 'absolute bottom-full left-1/2 -translate-x-1/2 mb-2 bg-primary text-on-primary px-2 py-1 rounded text-xs font-bold whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10';
            tooltip.textContent = person.name;
            tooltip.style.transform = 'translate(-50%, 0)';

            box.appendChild(tooltip);
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
            <div id="photo-modal-overlay" class="fixed inset-0 bg-black/50 z-50 flex items-center justify-center hidden overflow-y-auto" onclick="if(event.target === this) closePhotoModal()">
                <div id="photo-modal-content"></div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
};

// Auto-initialize when script loads
document.addEventListener('DOMContentLoaded', initPhotoModal);
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPhotoModal);
} else {
    initPhotoModal();
}
