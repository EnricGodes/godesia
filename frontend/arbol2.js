// arbol2.js — Family tree using family-chart library
// Requires: D3 v7, family-chart UMD (loaded in arbol2.html)

const A2_DEFAULT_ID = 'I4'; // Artur Godes Caballeria

let a2Store = null;
let a2Svg = null;

// ─── Init ─────────────────────────────────────────────────────────────────────

async function a2Init(personId) {
  const res = await fetch(`/api/tree2/${encodeURIComponent(personId)}?up=3&down=3`);
  if (!res.ok) throw new Error(`Error carregant arbre: ${res.status}`);
  const { nodes, main_id } = await res.json();

  const cont = document.getElementById('FamilyChart');
  cont.innerHTML = '';
  a2Svg = null;
  a2Store = null;

  a2Store = f3.createStore({
    data: nodes,
    main_id: main_id,
    node_separation: 300,
    level_separation: 170,
  });

  a2Svg = f3.createSvg(cont);

  const Card = f3.elements.CardSvg({
    store: a2Store,
    svg: a2Svg,
    card_dim: {
      w: 220, h: 90,
      text_x: 78, text_y: 18,
      img_w: 66, img_h: 66,
      img_x: 6, img_y: 12,
    },
    card_display: [
      d => a2DisplayName(d.data),   // d = store item {id, data:{...}, rels:{...}}
      d => a2DisplayYears(d.data),  // d.data = our custom data object
    ],
    mini_tree: true,
    link_break: false,
    onCardClick: (_e, d) => {
      // d is D3 datum: d.data = store item {id, data:{...}, rels:{...}}
      a2Store.updateMainId(d.data.id);
      a2Store.updateTree({});
      a2OpenSidebar(d.data);
    },
  });

  a2Store.setOnUpdate(props => f3.view(a2Store.getTree(), a2Svg, Card, props || {}));
  a2Store.updateTree({ initial: true });
}

document.addEventListener('DOMContentLoaded', () => {
  a2Init(A2_DEFAULT_ID).catch(err => {
    document.getElementById('FamilyChart').innerHTML =
      `<div style="color:#fff;padding:40px;font-family:Manrope,sans-serif;">Error: ${err.message}</div>`;
  });
});

// ─── Formateo ─────────────────────────────────────────────────────────────────

function a2DisplayName(data) {
  if (!data) return '';
  const given  = data['first name'] || '';
  const family = data['last name']  || '';
  const nick   = data.nickname;
  const full   = nick ? `${given} "${nick}" ${family}` : `${given} ${family}`;
  const trimmed = full.trim();
  return trimmed.length > 23 ? trimmed.substring(0, 22) + '…' : trimmed;
}

function a2DisplayYears(data) {
  if (!data) return '';
  const b = data.birth_year || '?';
  const d = data.death_year || (data.is_alive ? 'viu/a' : '?');
  return `${b} – ${d}`;
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function a2OpenSidebar(storeItem) {
  // storeItem = {id, data: {custom fields...}, rels: {...}}
  const data   = storeItem.data || {};
  const nodeId = storeItem.id   || '';
  const dosId  = (data.db_id || '').replace(/@/g, '');

  const fullName = `${data['first name'] || ''} ${data['last name'] || ''}`.trim();
  const birthLine = [data.birth_date, data.birth_place].filter(Boolean).join(' · ');
  const deathLine = data.death_date || '';

  const sidebar = document.getElementById('a2-sidebar');
  sidebar.innerHTML = `
    <div style="padding:20px;position:relative;">
      <button onclick="a2CloseSidebar()"
        style="position:absolute;top:12px;right:12px;background:none;border:none;
               font-size:22px;line-height:1;cursor:pointer;color:#6b6b60;">✕</button>

      ${data.avatar
        ? `<img src="${data.avatar}" alt="${fullName}"
             style="width:84px;height:84px;border-radius:50%;object-fit:cover;
                    border:3px solid #2d4b33;display:block;margin:0 auto 14px;"
             onerror="this.style.display='none'">`
        : ''}

      <h2 style="font-family:'Noto Serif',serif;font-size:1.05rem;font-weight:600;
                 color:#17341e;text-align:center;margin:0 0 4px;">${fullName}</h2>

      ${data.nickname
        ? `<p style="text-align:center;color:#78583e;font-style:italic;
                     font-size:.875rem;margin:0 0 6px;">"${data.nickname}"</p>`
        : ''}

      <p style="text-align:center;color:#9e9b94;font-size:.8rem;margin:0 0 20px;">
        ${a2DisplayYears(data)}
      </p>

      ${birthLine ? a2Field('Naixement', birthLine) : ''}
      ${deathLine ? a2Field('Defunció',  deathLine) : ''}

      <div style="margin-top:20px;display:flex;flex-direction:column;gap:8px;">
        <button onclick="a2CenterOn('${nodeId}')"
          style="width:100%;padding:9px;background:#2d4b33;color:#fff;border:none;
                 border-radius:8px;cursor:pointer;font-family:Manrope,sans-serif;
                 font-size:.875rem;font-weight:500;">
          Centrar en l'arbre
        </button>
        ${dosId
          ? `<a href="/dossier.html?id=${dosId}"
               style="display:block;text-align:center;padding:9px;
                      background:#f1eee5;color:#2d4b33;
                      border:1px solid #d9d5cc;border-radius:8px;
                      font-family:Manrope,sans-serif;font-size:.875rem;
                      font-weight:500;text-decoration:none;">
               Veure dossier complet
             </a>`
          : ''}
      </div>
    </div>`;

  sidebar.style.display = 'block';
}

function a2Field(label, value) {
  return `<div class="a2-field">
    <div class="a2-label">${label}</div>
    <div class="a2-value">${value}</div>
  </div>`;
}

function a2CloseSidebar() {
  document.getElementById('a2-sidebar').style.display = 'none';
}

function a2CenterOn(nodeId) {
  a2Init(nodeId).catch(console.error);
}

// ─── Zoom ─────────────────────────────────────────────────────────────────────

function a2ZoomIn() {
  const svgEl = document.querySelector('#FamilyChart svg');
  if (svgEl) svgEl.dispatchEvent(new WheelEvent('wheel', { deltaY: -200, bubbles: true, cancelable: true }));
}

function a2ZoomOut() {
  const svgEl = document.querySelector('#FamilyChart svg');
  if (svgEl) svgEl.dispatchEvent(new WheelEvent('wheel', { deltaY: 200, bubbles: true, cancelable: true }));
}

function a2ZoomReset() {
  if (!a2Store) return;
  const mainId = a2Store.getMainId();
  if (mainId) {
    a2Store.updateMainId(mainId);
    a2Store.updateTree({});
  }
}

// ─── Buscador ─────────────────────────────────────────────────────────────────

let a2SearchTimeout = null;
const a2SearchInput   = document.getElementById('a2-search');
const a2ResultsBox    = document.getElementById('a2-results');

if (a2SearchInput) {
  a2SearchInput.addEventListener('input', () => {
    clearTimeout(a2SearchTimeout);
    const q = a2SearchInput.value.trim();
    if (q.length < 2) { a2ResultsBox.style.display = 'none'; return; }
    a2SearchTimeout = setTimeout(() => a2DoSearch(q), 280);
  });

  a2SearchInput.addEventListener('blur', () => {
    setTimeout(() => { a2ResultsBox.style.display = 'none'; }, 200);
  });
}

async function a2DoSearch(q) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=15`);
    if (!res.ok) return;
    const { results } = await res.json();

    if (!results || !results.length) {
      a2ResultsBox.innerHTML =
        '<div style="padding:10px 14px;color:#9e9b94;font-size:.875rem;">Sense resultats</div>';
    } else {
      a2ResultsBox.innerHTML = results.map(r => {
        const name = r.nickname
          ? `${r.given_name || ''} "${r.nickname}" ${r.surname || ''}`
          : r.name;
        const years = `${r.birth_year || '?'} – ${r.death_year || (r.is_alive ? 'viu/a' : '?')}`;
        const cid = r.id.replace(/@/g, '');
        return `<div class="a2-result-item" onclick="a2SelectPerson('${cid}')">
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</span>
          <small>${years}</small>
        </div>`;
      }).join('');
    }
    a2ResultsBox.style.display = 'block';
  } catch (_) { /* ignorar errors de xarxa */ }
}

function a2SelectPerson(cid) {
  a2ResultsBox.style.display = 'none';
  a2SearchInput.value = '';
  a2Init(cid).catch(console.error);
}
