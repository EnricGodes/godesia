async function loadDossier() {
    const params = new URLSearchParams(window.location.search);
    const personId = params.get('id');

    if (!personId) {
        showError('Persona no especificada');
        return;
    }

    try {
        const res = await fetch(`/api/dossier/${personId}`);
        if (!res.ok) {
            throw new Error('Persona no encontrada');
        }

        const data = await res.json();
        renderDossier(data);
    } catch (e) {
        showError(e.message);
    }
}

function showError(message) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('error').style.display = 'block';
    document.getElementById('error').textContent = 'Error: ' + message;
}

function renderDossier(data) {
    const person = data.person;

    // Title
    document.title = `${person.name} | Familia Godes`;
    document.getElementById('person-name').textContent = person.name;
    document.getElementById('person-name-breadcrumb').textContent = person.name;

    // Vital stats
    const stats = [];
    if (person.birth_date) {
        stats.push({
            label: 'Naixement',
            value: `${person.birth_date}${person.birth_place ? ' a ' + person.birth_place : ''}`
        });
    }
    if (person.death_date) {
        stats.push({
            label: 'Defunció',
            value: `${person.death_date}${person.death_place ? ' a ' + person.death_place : ''}`
        });
    }
    if (person.death_age) {
        stats.push({
            label: 'Edat',
            value: `${person.death_age} anys`
        });
    }

    const statsHtml = stats.map(s => `
        <div>
            <div style="font-size: 0.75rem; color: var(--on-surface-variant); text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 0.5rem;">${s.label}</div>
            <div style="font-family: 'Noto Serif', serif; font-size: 1.1rem; color: var(--on-primary-container); font-weight: 600;">${s.value}</div>
        </div>
    `).join('');
    document.getElementById('vital-stats').innerHTML = statsHtml;

    // Family relations
    renderFamily(data);

    // Residences
    renderResidences(data.residences);

    // Occupations
    renderOccupations(data.occupations);

    // Photos
    renderPhotos(data.photos);

    // Notes
    renderNotes(data.notes);

    document.getElementById('loading').style.display = 'none';
    document.getElementById('content').style.display = 'block';
}

function renderFamily(data) {
    const familySection = document.getElementById('family-section');
    let html = '';

    // Parents
    if (data.father || data.mother) {
        const parents = [];
        if (data.father) {
            parents.push(`<a href="?id=${encodeURIComponent(data.father.id)}" class="person-link">${data.father.name}</a> (${data.father.birth_year}${data.father.death_year ? '-' + data.father.death_year : ''})`);
        }
        if (data.mother) {
            parents.push(`<a href="?id=${encodeURIComponent(data.mother.id)}" class="person-link">${data.mother.name}</a> (${data.mother.birth_year}${data.mother.death_year ? '-' + data.mother.death_year : ''})`);
        }
        html += `
            <div class="dossier-section">
                <h4 style="font-family: 'Noto Serif', serif; font-size: 1.2rem; margin-bottom: 1rem; color: var(--on-surface);">Pares</h4>
                <div class="family-grid">${parents.map(p => `<div class="family-card"><p>${p}</p></div>`).join('')}</div>
            </div>
        `;
    }

    // Siblings
    if (data.siblings && data.siblings.length > 0) {
        const siblingsHtml = data.siblings.map(s => `
            <a href="?id=${encodeURIComponent(s.id)}" class="person-link">${s.name}</a> (${s.birth_year}${s.death_year ? '-' + s.death_year : ''})
        `).join('<br>');
        html += `
            <div class="dossier-section">
                <h4 style="font-family: 'Noto Serif', serif; font-size: 1.2rem; margin-bottom: 1rem; color: var(--on-surface);">Germans</h4>
                <div class="family-card"><p>${siblingsHtml}</p></div>
            </div>
        `;
    }

    // Spouse
    if (data.spouse) {
        html += `
            <div class="dossier-section">
                <h4 style="font-family: 'Noto Serif', serif; font-size: 1.2rem; margin-bottom: 1rem; color: var(--on-surface);">Cònjuge</h4>
                <div class="family-card">
                    <p><a href="?id=${encodeURIComponent(data.spouse.id)}" class="person-link">${data.spouse.name}</a> (${data.spouse.birth_year}${data.spouse.death_year ? '-' + data.spouse.death_year : ''})</p>
                </div>
            </div>
        `;
    }

    // Children
    if (data.children && data.children.length > 0) {
        const childrenHtml = data.children.map(c => `
            <a href="?id=${encodeURIComponent(c.id)}" class="person-link">${c.name}</a> (${c.birth_year}${c.death_year ? '-' + c.death_year : ''})
        `).join('<br>');
        html += `
            <div class="dossier-section">
                <h4 style="font-family: 'Noto Serif', serif; font-size: 1.2rem; margin-bottom: 1rem; color: var(--on-surface);">Fills</h4>
                <div class="family-card"><p>${childrenHtml}</p></div>
            </div>
        `;
    }

    if (html) {
        document.getElementById('family-section').innerHTML = html;
        document.getElementById('family-section').style.display = 'block';
    }
}

function renderResidences(residences) {
    if (!residences || residences.length === 0) return;

    const section = document.getElementById('residences-section');
    const timeline = document.getElementById('residences-timeline');

    const html = residences.map(r => `
        <div class="timeline-item">
            <div class="timeline-dot"></div>
            ${r.date ? `<div class="timeline-date">${r.date}</div>` : ''}
            <div class="timeline-title">${r.address}${r.address2 ? ', ' + r.address2 : ''}</div>
            <div class="timeline-description">${r.city}${r.country ? ', ' + r.country : ''}</div>
        </div>
    `).join('');

    timeline.innerHTML = html;
    section.style.display = 'block';
}

function renderOccupations(occupations) {
    if (!occupations || occupations.length === 0) return;

    const section = document.getElementById('occupations-section');
    const timeline = document.getElementById('occupations-timeline');

    const html = occupations.map(o => `
        <div class="timeline-item">
            <div class="timeline-dot"></div>
            ${o.date ? `<div class="timeline-date">${o.date}</div>` : ''}
            <div class="timeline-title">${o.title}</div>
            ${o.place ? `<div class="timeline-description">${o.place}</div>` : ''}
        </div>
    `).join('');

    timeline.innerHTML = html;
    section.style.display = 'block';
}

function renderPhotos(photos) {
    if (!photos || photos.length === 0) return;

    const section = document.getElementById('photos-section');
    const gallery = document.getElementById('photos-gallery');

    const html = photos.map(p => `
        <div class="photo-item">
            <img src="/photos/${p.filename}" alt="${p.title}" loading="lazy">
            <div class="photo-caption">
                ${p.title ? `<strong>${p.title}</strong><br>` : ''}
                ${p.date ? `<em>${p.date}</em>` : ''}
            </div>
        </div>
    `).join('');

    gallery.innerHTML = html;
    section.style.display = 'block';
}

function renderNotes(notes) {
    if (!notes || notes.length === 0) return;

    const section = document.getElementById('notes-section');
    const content = document.getElementById('notes-content');

    // Clean HTML from notes
    const cleanNotes = notes.map(n => {
        // Remove HTML tags
        return n.replace(/<[^>]+>/g, ' ')
                 .replace(/&[a-z]+;/g, ' ')
                 .replace(/\s+/g, ' ')
                 .trim();
    });

    content.innerHTML = cleanNotes.map(n => `<p>${n}</p>`).join('');
    section.style.display = 'block';
}

document.addEventListener('DOMContentLoaded', loadDossier);
