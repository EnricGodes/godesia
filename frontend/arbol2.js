// arbol2.js — Family tree using family-chart library (HTML card variant)
// Requires: D3 v7, family-chart (loaded in arbol2.html)

const A2_DEFAULT_ID = 'I4'; // Artur Godes Caballeria

let a2Store  = null;
let a2Svg    = null;  // SVG DOM element (for links + zoom)

// ─── Init ─────────────────────────────────────────────────────────────────────

async function a2Init(personId) {
  const res = await fetch(`/api/tree2/${encodeURIComponent(personId)}?up=3&down=3`);
  if (!res.ok) throw new Error(`Error carregant arbre: ${res.status}`);
  const { nodes, main_id } = await res.json();

  const cont = document.getElementById('FamilyChart');
  cont.innerHTML = '';
  a2Svg   = null;
  a2Store = null;

  // Create SVG (links + zoom host) with custom onZoom that also moves the HTML cards overlay
  a2Svg = f3.createSvg(cont, {
    onZoom: function(e) {
      const t = e.transform;
      const tStr = `translate(${t.x}px, ${t.y}px) scale(${t.k})`;
      const svgView  = cont.querySelector('svg.main_svg .view');
      const htmlView = cont.querySelector('#htmlSvg .cards_view');
      if (svgView)  svgView.style.transform  = tStr;
      if (htmlView) htmlView.style.transform = tStr;
    },
  });

  // HTML overlay: positions card divs on top of the SVG link lines
  const f3Canvas = cont.querySelector('#f3Canvas');
  const htmlSvg = document.createElement('div');
  htmlSvg.id = 'htmlSvg';
  htmlSvg.style.cssText = 'position:absolute;width:100%;height:100%;z-index:2;top:0;left:0;pointer-events:none;';
  const cardsViewEl = document.createElement('div');
  cardsViewEl.className   = 'cards_view';
  cardsViewEl.style.cssText = 'transform-origin:0 0;pointer-events:auto;';
  htmlSvg.appendChild(cardsViewEl);
  f3Canvas.appendChild(htmlSvg);

  a2Store = f3.createStore({
    data: nodes,
    main_id,
    node_separation: 260,  // wider spacing for 220px cards
    level_separation: 220, // taller spacing for ~182px cards
    transition_time: 250,  // x4 faster than default
  });

  const Card = f3.elements.CardHtml({
    store:   a2Store,
    svg:     a2Svg,
    mini_tree: true,
    cardInnerHtmlCreator: d => a2CardHtml(d),
    onCardClick: (_e, d) => {
      // d = D3 datum; d.data = store item {id, data:{…}, rels:{…}}
      a2Store.updateMainId(d.data.id);
      a2Store.updateTree({});
      a2OpenSidebar(d.data);
    },
  });

  a2Store.setOnUpdate(props => {
    f3.view(a2Store.getTree(), a2Svg, Card, {
      ...(props || {}),
      cardComponent: true,
      cardHtmlDiv:   htmlSvg,
    });
  });

  a2Store.updateTree({ initial: true });

  // After initial scatter animation, center view on main person (issue 3)
  setTimeout(() => {
    if (!a2Store || !a2Svg) return;
    try {
      const datum   = a2Store.getTreeMainDatum();
      const svg_dim = cont.getBoundingClientRect();
      f3.handlers.cardToMiddle({ datum, svg: a2Svg, svg_dim, scale: 1, transition_time: 300 });
    } catch (_) {}
  }, 320);
}

document.addEventListener('DOMContentLoaded', () => {
  a2Init(A2_DEFAULT_ID).catch(err => {
    document.getElementById('FamilyChart').innerHTML =
      `<div style="padding:40px;font-family:Manrope,sans-serif;color:#ba1a1a;">Error: ${err.message}</div>`;
  });
});

// ─── Card HTML (reference design, photo 50% bigger: 60px→90px) ───────────────

function a2CardHtml(d) {
  // d.data = store item {id, data:{custom…}, rels:{…}}
  // d.data.data = our custom data fields
  const data     = d.data.data;
  const given    = data['first name'] || '';
  const family   = data['last name']  || '';
  const years    = a2DisplayYears(data);
  const avatar   = data.avatar || '';
  const isFemale = data.gender === 'F';

  // Header background differs by gender (design system surface tokens)
  const headerBg = isFemale ? '#f6f3ea' : '#ebe8df';

  return `
<div style="
  background:#ffffff;
  border-radius:8px;
  overflow:hidden;
  width:220px;
  font-family:'Manrope',sans-serif;
  box-shadow:0 4px 20px rgba(28,28,23,0.10);
  user-select:none;
" onmousedown="event.stopPropagation()">

  <!-- Foto circular: 90px (reference 60px + 50%) -->
  <div style="
    height:130px;
    background:${headerBg};
    display:flex;
    align-items:center;
    justify-content:center;
  ">
    <div style="
      width:90px;
      height:90px;
      border-radius:50%;
      overflow:hidden;
      box-shadow:0 2px 12px rgba(28,28,23,0.18);
      background:#d5d2c9;
      flex-shrink:0;
    ">
      ${avatar
        ? `<img src="${avatar}" alt="${given} ${family}"
             style="width:90px;height:90px;object-fit:cover;object-position:top 10%;"
             onerror="this.parentElement.style.background='#c2c8bf'">`
        : ''}
    </div>
  </div>

  <!-- Info -->
  <div style="padding:10px 14px 12px;">
    <div style="
      font-family:'Noto Serif',Georgia,serif;
      font-size:13px;
      font-weight:600;
      color:#392d13;
      line-height:1.35;
      margin-bottom:3px;
    ">${given}<br>${family}</div>
    <div style="font-size:11px;color:#7a7a6e;">${years}</div>
  </div>

</div>`;
}

// ─── Formateo ─────────────────────────────────────────────────────────────────

function a2DisplayYears(data) {
  if (!data) return '';
  const b = data.birth_year || '?';
  const d = data.death_year || (data.is_alive ? 'viu/a' : '?');
  return `${b} – ${d}`;
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function a2OpenSidebar(storeItem) {
  // storeItem = {id, data:{custom…}, rels:{…}}
  const data   = storeItem.data || {};
  const nodeId = storeItem.id   || '';
  const dosId  = (data.db_id || '').replace(/@/g, '');

  const given  = data['first name'] || '';
  const family = data['last name']  || '';
  const fullName  = [given, family].filter(Boolean).join(' ');
  const birthLine = [data.birth_date, data.birth_place].filter(Boolean).join(' · ');
  const deathLine = data.death_date || '';

  const sidebar = document.getElementById('a2-sidebar');
  sidebar.innerHTML = `
    <div style="padding:20px;position:relative;">
      <button onclick="a2CloseSidebar()"
        style="position:absolute;top:12px;right:12px;background:none;border:none;
               font-size:22px;line-height:1;cursor:pointer;color:#9e9b94;">✕</button>

      ${data.avatar
        ? `<img src="${data.avatar}" alt="${fullName}"
             style="width:84px;height:84px;border-radius:50%;object-fit:cover;
                    object-position:top 10%;border:3px solid #2d4b33;
                    display:block;margin:0 auto 14px;"
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
                      border:1px solid #c2c8bf;border-radius:8px;
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
  if (!a2Svg) return;
  try { f3.handlers.manualZoom({ amount: 1.3,  svg: a2Svg, transition_time: 250 }); }
  catch (_) {}
}

function a2ZoomOut() {
  if (!a2Svg) return;
  try { f3.handlers.manualZoom({ amount: 0.77, svg: a2Svg, transition_time: 250 }); }
  catch (_) {}
}

function a2ZoomReset() {
  if (!a2Store || !a2Svg) return;
  try {
    const datum   = a2Store.getTreeMainDatum();
    const cont    = document.getElementById('FamilyChart');
    const svg_dim = cont.getBoundingClientRect();
    f3.handlers.cardToMiddle({ datum, svg: a2Svg, svg_dim, scale: 1, transition_time: 350 });
  } catch (_) {}
}

// ─── Buscador ─────────────────────────────────────────────────────────────────

let a2SearchTimeout = null;
const a2SearchInput = document.getElementById('a2-search');
const a2ResultsBox  = document.getElementById('a2-results');

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
        const name  = r.nickname
          ? `${r.given_name || ''} "${r.nickname}" ${r.surname || ''}` : r.name;
        const years = `${r.birth_year || '?'} – ${r.death_year || (r.is_alive ? 'viu/a' : '?')}`;
        const cid   = r.id.replace(/@/g, '');
        return `<div class="a2-result-item" onclick="a2SelectPerson('${cid}')">
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</span>
          <small>${years}</small>
        </div>`;
      }).join('');
    }
    a2ResultsBox.style.display = 'block';
  } catch (_) {}
}

function a2SelectPerson(cid) {
  a2ResultsBox.style.display = 'none';
  a2SearchInput.value = '';
  a2Init(cid).catch(console.error);
}
