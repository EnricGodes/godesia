// arbol2.js — Family tree using family-chart library (HTML card variant)
// Requires: D3 v7, family-chart (loaded in arbol2.html)

const A2_DEFAULT_ID = 'I4'; // Artur Godes Caballeria

let a2Store  = null;
let a2Svg    = null;  // SVG DOM element (for links + zoom)
let a2MainId = null;  // Originally requested person ID (viewport center target)

// ─── Init ─────────────────────────────────────────────────────────────────────

async function a2Init(personId) {
  const res = await fetch(`/api/tree2/${encodeURIComponent(personId)}?up=6&down=6`);
  if (!res.ok) throw new Error(`Error carregant arbre: ${res.status}`);
  const { nodes, main_id } = await res.json();

  const cont = document.getElementById('FamilyChart');
  cont.innerHTML = '';
  a2Svg   = null;
  a2Store = null;
  a2MainId = main_id;

  // htmlHandlers.default creates SVG + #htmlSvg overlay with synced zoom
  const { svg, htmlSvg } = f3.htmlHandlers.default(cont);
  a2Svg = svg;

  // Use the main person as store_main_id so family-chart renders:
  //  - the main person and their siblings in the center row
  //  - both parents (father + mother) as the couple above
  //  - BOTH grandparent lines (paternal and maternal) above the parents
  //  - paternal uncles/aunts beside the father (children of paternal grandfather)
  //  - maternal uncles/aunts beside the mother (children of maternal grandfather)
  const store_main_id = main_id;

  a2Store = f3.createStore({
    data: nodes,
    main_id: store_main_id,
    node_separation: 260,   // wider spacing for 220px cards
    level_separation: 240,  // vertical gap: 240 - 132px card = 108px for connectors + mini-tree
    transition_time: 0,     // no entry animation — tree appears fully built
    // Render the main person's siblings via the library's setupSiblings.
    // Without this the parents end up with a mini-tree icon because their
    // children (the main's siblings) are missing from the tree.
    show_siblings_of_main: true,
    // Sort children and siblings by birth year (oldest first). family-chart
    // applies this both in hierarchyGetterChildren and inside setupSiblings.
    sortChildrenFunction: (a, b) => {
      const ay = (a && a.data && a.data.birth_year) || 9999;
      const by = (b && b.data && b.data.birth_year) || 9999;
      return ay - by;
    },
  });

  const Card = f3.elements.CardHtml({
    store:   a2Store,
    svg:     a2Svg,
    mini_tree: true,
    // Issue 3+4: tell family-chart the actual foreignObject size so the
    // SVG mini-tree icon and connector lines are not covered by the card.
    // Card renders at 220×132px (100px header + ~32px text block).
    card_dim: { w: 220, h: 156, text_x: 0, text_y: 0, img_x: 0, img_y: 0, img_w: 0, img_h: 0 },
    cardInnerHtmlCreator: d => a2CardHtml(d),
    onCardClick: (_e, d) => {
      // Center view on clicked card without reorganizing the tree.
      // We bypass f3.handlers.cardToMiddle because it has a library bug: it
      // omits the *k multiplier on the Y axis, so at any zoom != 1 the card
      // ends up off-centre vertically. We replicate positionTree() directly.
      try {
        const cont    = document.getElementById('FamilyChart');
        const svg_dim = cont.getBoundingClientRect();
        const k       = f3.handlers.getCurrentZoom(a2Svg).k;
        // d3.zoomIdentity.scale(k).translate(tx,ty) maps datum → screen as
        // screen = k*(datum + t), so to centre: t = dim/(2k) - datum.
        const tx = svg_dim.width  / (2 * k) - d.x;
        const ty = svg_dim.height / (2 * k) - d.y;
        const el = a2Svg.__zoomObj ? a2Svg : a2Svg.parentNode;
        d3.select(el).call(el.__zoomObj.transform, d3.zoomIdentity.scale(k).translate(tx, ty));
      } catch (_) {}
      a2OpenSidebar(d.data);
    },
  });

  a2Store.setOnUpdate(props => {
    const tree = a2Store.getTree();
    a2AddParentSiblings(tree);
    a2OffsetSpouseNodes(tree);  // offset before view so D3 animates to correct pos
    f3.view(tree, a2Svg, Card, {
      ...(props || {}),
      cardHtml:    true,
      cardHtmlDiv: htmlSvg,
    });
    setTimeout(a2ApplyDivorcedLines, 50);
    setTimeout(a2ApplyDivorcedLines, 200);
    a2BindMiniTreeClicks();
    setTimeout(a2BindMiniTreeClicks, 200);
  });

  a2Store.updateTree({ initial: true });

  // Center view on requested person and apply default zoom-out (2 clicks out = 0.77²)
  setTimeout(() => {
    if (!a2Store || !a2Svg) return;
    try {
      const svg_dim = cont.getBoundingClientRect();
      const datum   = a2FindDatumById(a2MainId) || a2Store.getTreeMainDatum();
      f3.handlers.cardToMiddle({ datum, svg: a2Svg, svg_dim, scale: 1, transition_time: 0 });
      // Apply 2 zoom-out steps (factor 0.77 each = ~0.59x total)
      f3.handlers.manualZoom({ amount: 0.77, svg: a2Svg, transition_time: 0 });
      f3.handlers.manualZoom({ amount: 0.77, svg: a2Svg, transition_time: 0 });
    } catch (_) {}
  }, 50);
}

document.addEventListener('DOMContentLoaded', async () => {
  let defaultId = A2_DEFAULT_ID;
  try {
    const res = await fetch('/api/settings');
    if (res.ok) {
      const s = await res.json();
      if (s.tree_default_person) defaultId = s.tree_default_person;
    }
  } catch (_) {}
  a2Init(defaultId).catch(err => {
    document.getElementById('FamilyChart').innerHTML =
      `<div style="padding:40px;font-family:Manrope,sans-serif;color:#ba1a1a;">Error: ${err.message}</div>`;
  });
});

// ─── Card HTML ────────────────────────────────────────────────────────────────

function a2CardHtml(d) {
  // d.data = store item {id, data:{custom…}, rels:{…}}
  // d.data.data = our custom data fields
  const data     = d.data.data;
  const given    = data['first name'] || '';
  const family   = data['last name']  || '';
  const info     = a2DisplayInfo(data);
  const avatar   = data.avatar || '';
  const isFemale = data.gender === 'F';

  const headerBg = isFemale ? '#fdd2b1' : '#78583e';

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

  <div style="
    height:112px;
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

  <div style="padding:10px 14px 12px;">
    <div style="
      font-family:'Noto Serif',Georgia,serif;
      font-size:13px;
      font-weight:600;
      color:#392d13;
      line-height:1.35;
      margin-bottom:3px;
    ">${given}<br>${family}</div>
    <div style="font-size:11px;color:#7a7a6e;">${info}</div>
  </div>

</div>`;
}

// ─── Formateo ─────────────────────────────────────────────────────────────────

function a2DisplayYears(data) {
  if (!data) return '';
  const b = data.birth_year || '?';
  // Issue 5+6: alive people show only birth year; unknown death → '?' only if deceased
  const d = data.death_year || (data.is_alive ? null : '?');
  return d ? `${b} – ${d}` : `${b}`;
}

function a2DisplayInfo(data) {
  if (!data) return '';
  const years = a2DisplayYears(data);
  const place = data.birth_city || data.birth_place || '';
  return place ? `${years} · ${place}` : years;
}

// ─── Inject parent siblings (uncles/aunts of main) ───────────────────────────
//
// family-chart only renders the direct ancestor line: it never shows the
// siblings of an ancestor. We want the parents of the main person to appear
// expanded with their siblings (the main's uncles and aunts) on both sides.
// We replicate the technique used internally by setupSiblings (lines 86+ of
// family-chart.js): create extra nodes with `sibling:true`, position them
// next to the parent, and link them to the grandparents already in the tree.
//
// Only depth-1 ancestors (the main's parents) are expanded. Grandparents stay
// collapsed (the mini-tree icon remains clickable to recenter on them).

function a2AddParentSiblings(tree) {
  if (!tree || !Array.isArray(tree.data) || !a2Store) return;
  const main = tree.data.find(d => d && d.data && d.data.main);
  if (!main || !main.parents || main.parents.length === 0) return;

  const dataStash = a2Store.getData();
  if (!dataStash || dataStash.length === 0) return;

  const nodeSep = (a2Store.state && a2Store.state.node_separation) || 260;
  const existingIds = new Set(tree.data.map(d => d.data && d.data.id).filter(Boolean));
  const newNodes = [];

  main.parents.forEach(parent => {
    if (!parent || !parent.data) return;
    const pDatum = parent.data;
    const pParentRels = (pDatum.rels && pDatum.rels.parents) || [];
    if (pParentRels.length === 0) return; // can't find siblings without grandparents

    const siblings = dataStash.filter(d => {
      if (!d || d.id === pDatum.id) return false;
      if (existingIds.has(d.id)) return false;
      const dParents = (d.rels && d.rels.parents) || [];
      return pParentRels.some(gpId => dParents.includes(gpId));
    });
    if (siblings.length === 0) return;

    siblings.sort((a, b) => {
      const ay = (a.data && a.data.birth_year) || 9999;
      const by = (b.data && b.data.birth_year) || 9999;
      return ay - by;
    });

    // Place siblings on the side of the parent farthest from main.
    const direction = parent.x <= main.x ? -1 : 1;
    const grandparentNodes = (parent.parents || []).filter(d => d && d.is_ancestry);

    siblings.forEach((sibDatum, i) => {
      const sib = {
        data: sibDatum,
        sibling: true,
        is_ancestry: true,
        depth: parent.depth,
        x: parent.x + direction * nodeSep * (i + 1),
        y: parent.y,
        parents: grandparentNodes.length > 0 ? grandparentNodes : undefined,
        // family-chart's calculateEnterAndExitPositions requires `parent` for
        // is_ancestry nodes (used as the animation origin). Anchor to the
        // genealogical parent so the sibling card flies out from its side.
        parent: parent,
        tid: `psib-${sibDatum.id}`,
        all_rels_displayed: false,
      };
      newNodes.push(sib);
      existingIds.add(sibDatum.id);
    });
  });

  if (newNodes.length === 0) return;

  newNodes.forEach(n => tree.data.push(n));

  // Recompute tree.dim so the initial fit zooms out enough to show new nodes.
  if (tree.dim) {
    const xs = tree.data.map(d => d.x).filter(v => typeof v === 'number');
    const ys = tree.data.map(d => d.y).filter(v => typeof v === 'number');
    if (xs.length && ys.length) {
      const xMin = Math.min(...xs), xMax = Math.max(...xs);
      const yMin = Math.min(...ys), yMax = Math.max(...ys);
      const levelSep = (a2Store.state && a2Store.state.level_separation) || 220;
      tree.dim.width  = (xMax - xMin) + nodeSep;
      tree.dim.height = (yMax - yMin) + levelSep;
      tree.dim.x_off  = -xMin + nodeSep / 2;
      tree.dim.y_off  = -yMin + levelSep / 2;
    }
  }
}

// ─── Divorced lines ───────────────────────────────────────────────────────────

function a2ApplyDivorcedLines() {
  if (!a2Svg) return;
  d3.select(a2Svg).select('.links_view').selectAll('path.link').each(function(d) {
    if (!d || !d.spouse) return;
    const srcData = d.source?.data?.data;
    const tgtData = d.target?.data?.data;
    const tgtId   = d.target?.data?.id;
    const srcId   = d.source?.data?.id;
    const divorced = (srcData?.divorced_spouses || []).includes(tgtId)
                  || (tgtData?.divorced_spouses || []).includes(srcId);
    if (divorced) {
      d3.select(this).style('stroke-dasharray', '8,5').style('stroke-opacity', '0.65');
    }
  });
}

function a2OffsetSpouseNodes(tree) {
  // When a person has multiple spouses, their connector lines overlap.
  // Fix: set lineYOffset on each spouse node — the card stays at natural y,
  // but the connecting line is routed at a different y level.
  if (!tree || !Array.isArray(tree.data)) return;
  const STEP = 14; // px between parallel lines

  const groups = new Map(); // mainId → [spouseNode, ...]
  tree.data.forEach(d => {
    if (!d.spouse) return;
    const mainId = d.spouse.data?.id;
    if (!mainId) return;
    if (!groups.has(mainId)) groups.set(mainId, []);
    groups.get(mainId).push(d);
  });

  groups.forEach(spouses => {
    if (spouses.length < 2) return;
    const n = spouses.length;
    spouses.forEach((d, i) => {
      d.lineYOffset = (i - (n - 1) / 2) * STEP;
    });
  });
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
  const birthLine = [data.birth_date, data.birth_city || data.birth_place].filter(Boolean).join(' · ');
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

      <div id="sidebar-minibio" style="margin-top:12px;font-size:0.82rem;color:#3d3d37;line-height:1.5;"></div>

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

  if (dosId) {
    fetch(`/api/minibio/${encodeURIComponent(dosId)}`)
      .then(r => r.json())
      .then(m => {
        const bio = m.bio_es || m.bio_ca || '';
        const el = document.getElementById('sidebar-minibio');
        if (el && bio) el.innerHTML = `<p style="margin:0;font-style:italic;">${bio}</p>`;
      })
      .catch(() => {});
  }
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

// ─── Tree helpers ─────────────────────────────────────────────────────────────

function a2BindMiniTreeClicks() {
  // The library renders <div class="mini-tree"> inside each card's
  // foreignObject (HTML, not SVG). Sizing is handled by CSS in
  // arbol2.html; here we just attach a click that recenters the tree
  // on the card the icon belongs to.
  const cont = document.getElementById('FamilyChart');
  if (!cont) return;
  cont.querySelectorAll('div.mini-tree').forEach(div => {
    if (div.dataset.bound) return;
    div.dataset.bound = '1';
    div.style.cursor = 'pointer';
    div.addEventListener('click', e => {
      e.stopPropagation();
      // Walk up the DOM (HTML and SVG) to find the bound D3 datum
      let datum = null;
      let node  = div.parentElement;
      while (node && !datum) {
        datum = d3.select(node).datum();
        node  = node.parentElement;
      }
      const id = datum?.data?.id;
      if (id) a2Init(id).catch(console.error);
    });
  });
}

function a2FindDatumById(nodeId) {
  if (!a2Store || !nodeId) return null;
  try {
    const tree = a2Store.getTree();
    if (!tree) return null;
    if (tree.data && Array.isArray(tree.data)) {
      return tree.data.find(d => d.data && d.data.id === nodeId) || null;
    }
    if (typeof tree.descendants === 'function') {
      return tree.descendants().find(d => d.data && d.data.id === nodeId) || null;
    }
    return null;
  } catch (_) { return null; }
}

// ─── Zoom ─────────────────────────────────────────────────────────────────────

function a2ZoomIn() {
  if (!a2Svg) return;
  try { f3.handlers.manualZoom({ amount: 1.3,  svg: a2Svg, transition_time: 125 }); }
  catch (_) {}
}

function a2ZoomOut() {
  if (!a2Svg) return;
  try { f3.handlers.manualZoom({ amount: 0.77, svg: a2Svg, transition_time: 125 }); }
  catch (_) {}
}

function a2ZoomReset() {
  if (!a2Store || !a2Svg) return;
  try {
    const datum   = a2FindDatumById(a2MainId) || a2Store.getTreeMainDatum();
    const cont    = document.getElementById('FamilyChart');
    const svg_dim = cont.getBoundingClientRect();
    f3.handlers.cardToMiddle({ datum, svg: a2Svg, svg_dim, scale: 1, transition_time: 200 });
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
        const _dy = r.death_year || (r.is_alive ? null : '?');
        const years = _dy ? `${r.birth_year || '?'} – ${_dy}` : `${r.birth_year || '?'}`;
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
