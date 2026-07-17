/**
 * nav.js — Godesia global navigation bar
 *
 * Usage: add  <script src="/nav.js"></script>  anywhere in <body>.
 * Requires Tailwind CSS and the Material Symbols Outlined font on the host page.
 */
(function () {
  'use strict';

  /* i18n: t() y helpers vienen de i18n.js (inyectado por el backend);
     shim de identidad para páginas internas servidas sin localizar */
  const t = window.t || function (k, p, f) { return f !== undefined ? f : k; };
  const lhref = window.I18N ? window.I18N.href : function (p) { return p; };

  // ─── Menu structure ───────────────────────────────────────────────────────

  const RAMAS = [
    { label: 'Godes Caballeria', href: '/godes_caballeria.html' },
    { label: 'Godes Diago',      href: '/godes_diago.html' },
    { label: 'Godes Ferrer',     href: '/godes_ferrer.html' },
    { label: 'Godes Güell',      href: '/godes_guell.html' },
    { label: 'Godes Hospital',   href: '/godes_hospital.html' },
    { label: 'Godes Hurtado',    href: '/godes_hurtado.html' },
    { label: 'Godes Molina',     href: '/godes_molina.html' },
    { label: 'Godes Schmid',     href: '/godes_schmid.html' },
    { label: 'Godes Segura',     href: '/godes_segura.html' },
    { label: 'Godes Terrats',    href: '/godes_terrats.html' },
    { label: 'Pujol Godes',      href: '/pujol_godes.html' },
  ];

  const ALBUM = [
    { label: t('nav.all_albums', null, 'Todos los álbumes'), href: '/albums.html' },
    { label: 'Godes',             href: '/albums.html#A800008' },
    { label: 'Godes Diago',       href: '/albums.html#A800003' },
    { label: 'Godes Güell',       href: '/albums.html#A800002' },
    { label: 'Godes Hospital',    href: '/albums.html#A800005' },
    { label: 'Godes Molina',      href: '/albums.html#A800001' },
    { label: 'Godes Schmid',      href: '/albums.html#A800006' },
    { label: 'Godes Terrats',     href: '/albums.html#A800007' },
    { label: 'Pujol Godes',       href: '/albums.html#A800004' },
    { label: t('nav.family_photos', null, 'Fotos Familiares'), href: '/albums.html#__unassigned__' },
  ];

  const DOCUMENTOS = [
    { label: t('nav.all_docs', null, 'Todos los documentos'), href: '/docs.html' },
    { label: t('doc_types.bautisme', null, 'Bautismos'),     href: '/docs.html#bautisme' },
    { label: t('doc_types.biografia', null, 'Biografías'),   href: '/docs.html#biografia' },
    { label: t('doc_types.carta', null, 'Cartas'),           href: '/docs.html#carta' },
    { label: t('doc_types.defuncio', null, 'Defunciones'),   href: '/docs.html#defuncio' },
    { label: t('doc_types.matrimoni', null, 'Matrimonios'),  href: '/docs.html#matrimoni' },
    { label: t('doc_types.naixement', null, 'Nacimientos'),  href: '/docs.html#naixement' },
    { label: t('doc_types.padro', null, 'Padrones'),         href: '/docs.html#padro' },
    { label: t('doc_types.testament', null, 'Testamentos'),  href: '/docs.html#testament' },
    { label: t('doc_types.document', null, 'Documentos'),    href: '/docs.html#document' },
  ];

  const DIVERSOS = [
    { label: t('nav.casas_godes', null, 'Casas Godes'), href: null },
    { label: t('nav.cemeteries', null, 'Cementerios'),  href: '/cementerios.html' },
  ];

  // ─── Helpers ──────────────────────────────────────────────────────────────

  /* Ruta actual sin el prefijo de idioma (/ca/x.html -> /x.html) */
  const PATH = window.location.pathname.replace(/^\/[a-z]{2,3}(\/|$)/, '/');

  function isActivePage(href) {
    if (!href) return false;
    const norm = p => p.replace(/\/$/, '') || '/';
    return norm(PATH) === norm(href);
  }

  function dropdownHasActive(items) {
    return items.some(i => i.href && isActivePage(i.href));
  }

  function chevronSVG() {
    return (
      '<svg class="gn-chevron w-3 h-3 transition-transform duration-200 shrink-0"' +
      ' fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">' +
      '<path stroke-linecap="round" stroke-linejoin="round" d="m6 9 6 6 6-6"/></svg>'
    );
  }

  // ─── Rendering ────────────────────────────────────────────────────────────

  function renderDropdownItems(items) {
    return items.map(item => {
      if (item.href) {
        const active = isActivePage(item.href)
          ? 'font-semibold text-[#2D4B33] bg-[#f1eee5]'
          : 'text-[#1c1c17] hover:bg-[#f1eee5]';
        return (
          `<a href="${lhref(item.href)}" class="block px-4 py-2 text-sm ${active} rounded-md transition-colors">` +
          `${item.label}</a>`
        );
      }
      return (
        `<span class="block px-4 py-2 text-sm text-[#b8b5ac] cursor-not-allowed select-none" title="${t('nav.coming_soon', null, 'Próximamente')}">` +
        `${item.label}</span>`
      );
    }).join('');
  }

  function renderDropdown(id, label, items) {
    const parentActive = dropdownHasActive(items) ? ' bg-white/20' : '';
    return (
      `<div class="gn-dropdown" data-menu-id="gn-menu-${id}">` +
        `<button type="button" class="gn-btn flex items-center gap-1 whitespace-nowrap px-3 py-1.5 rounded-md` +
        ` text-sm font-medium text-white/90 hover:bg-white/15 hover:text-white transition-colors${parentActive}">` +
          `${label}${chevronSVG()}` +
        `</button>` +
      `</div>` +
      /* Menu lives directly in <body> (appended in init) to avoid overflow clipping */
      `<div id="gn-menu-${id}" class="gn-menu" style="display:none;position:fixed;z-index:9999">` +
        `<div class="bg-white rounded-xl shadow-xl py-1.5 border border-[#e5e2da]" style="min-width:11rem">` +
          renderDropdownItems(items) +
        `</div>` +
      `</div>`
    );
  }

  /* Sección acordeón del drawer móvil — reutiliza renderDropdownItems (i18n,
     lhref, página activa) para que el contenido coincida con los dropdowns. */
  function renderDrawerSection(id, label, items) {
    return (
      `<button type="button" class="gn-acc-btn" data-acc="gn-acc-${id}">` +
        `<span>${label}</span>${chevronSVG()}` +
      `</button>` +
      `<div id="gn-acc-${id}" class="gn-acc-body" hidden>` +
        renderDropdownItems(items) +
      `</div>`
    );
  }

  function renderDrawer() {
    const arbolActive = isActivePage('/arbol2.html') ? ' gn-drawer-active' : '';
    const chatActive  = isActivePage('/chat.html')   ? ' gn-drawer-active' : '';
    return (
      `<div id="gn-drawer">` +
        `<div id="gn-drawer-backdrop"></div>` +
        `<div id="gn-drawer-panel">` +
          `<a href="${lhref('/arbol2.html')}" class="gn-drawer-link${arbolActive}">${t('nav.tree', null, 'Árbol')}</a>` +
          renderDrawerSection('ramas',      t('nav.menu_branches', null, 'Ramas familiares'), RAMAS) +
          `<a href="${lhref('/chat.html')}" class="gn-drawer-link${chatActive}">${t('nav.chat', null, 'Consultas')}</a>` +
          renderDrawerSection('album',      t('nav.menu_album', null, 'Álbum'),          ALBUM) +
          renderDrawerSection('documentos', t('nav.menu_documents', null, 'Documentos'), DOCUMENTOS) +
          renderDrawerSection('diversos',   t('nav.menu_misc', null, 'Diversos'),        DIVERSOS) +
          `<a href="${lhref('/colaborar.html')}" class="gn-drawer-link gn-drawer-pill">${t('nav.collaborate', null, 'Colaborar')}</a>` +
        `</div>` +
      `</div>`
    );
  }

  function renderNav() {
    const arbolActive  = isActivePage('/arbol2.html')  ? ' bg-white/20 font-semibold' : '';
    const chatActive   = isActivePage('/chat.html')    ? ' bg-white/20 font-semibold' : '';

    const linkCls = 'whitespace-nowrap px-3 py-1.5 rounded-md text-sm font-medium text-white/90' +
                    ' hover:bg-white/15 hover:text-white transition-colors';

    return (
      `<nav id="godesia-nav" class="z-50 bg-[#2D4B33] shadow-md" style="position:sticky;top:0;left:0;right:0;width:100%">` +
        /* 3-column Facebook-style layout: logo | center items | right actions */
        `<div class="px-4 flex items-center h-14" style="justify-content:space-between">` +

          /* ── Col 1: Logo (far left) ── */
          `<div class="flex items-center">` +
            `<button type="button" id="gn-burger" aria-label="${t('nav.menu', null, 'Menú')}" aria-expanded="false">` +
              `<svg xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>` +
            `</button>` +
            `<a href="${lhref('/')}" class="text-lg font-bold text-white hover:text-white/80 transition-colors"` +
            ` style="font-family:'Noto Serif',serif;letter-spacing:-.01em">Godesia</a>` +
          `</div>` +

          /* ── Col 2: Nav items ── */
          `<div class="gn-center flex items-center gap-0.5">` +
            `<a href="${lhref('/arbol2.html')}" class="${linkCls}${arbolActive}">${t('nav.tree', null, 'Árbol')}</a>` +
            renderDropdown('ramas',      t('nav.menu_branches', null, 'Ramas familiares'), RAMAS) +
            `<a href="${lhref('/chat.html')}" class="${linkCls}${chatActive}">${t('nav.chat', null, 'Consultas')}</a>` +
            renderDropdown('album',      t('nav.menu_album', null, 'Álbum'),          ALBUM) +
            renderDropdown('documentos', t('nav.menu_documents', null, 'Documentos'), DOCUMENTOS) +
            renderDropdown('diversos',   t('nav.menu_misc', null, 'Diversos'),        DIVERSOS) +
          `</div>` +

          /* ── Col 3: Action buttons (far right) ── */
          `<div class="flex items-center gap-2" style="position:relative">` +

            /* Search — icon only circle */
            `<button type="button" id="gn-search-toggle" class="flex items-center justify-center rounded-full border border-white text-white hover:border-white hover:text-white transition" style="width:28px;height:28px;background:transparent">` +
              `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">` +
                `<path d="M17 17L21 21" />` +
                `<path d="M19 11C19 6.58172 15.4183 3 11 3C6.58172 3 3 6.58172 3 11C3 15.4183 6.58172 19 11 19C15.4183 19 19 15.4183 19 11Z" />` +
              `</svg>` +
            `</button>` +

            /* Colaborar — stretched circle (rounded-full) with nav styling */
            `<a href="${lhref('/colaborar.html')}" id="gn-colaborar-btn" class="whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-medium text-white/90 border border-white hover:bg-white/15 hover:text-white transition-colors" style="background:transparent">` +
              `${t('nav.collaborate', null, 'Colaborar')}` +
            `</a>` +

            /* Login — user icon circle */
            `<a href="/login.html" title="Login" class="flex items-center justify-center rounded-full border border-white text-white hover:border-white hover:text-white transition" style="width:28px;height:28px;background:transparent" id="gn-login-btn">` +
              `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">` +
                `<path d="M17 8.5C17 5.73858 14.7614 3.5 12 3.5C9.23858 3.5 7 5.73858 7 8.5C7 11.2614 9.23858 13.5 12 13.5C14.7614 13.5 17 11.2614 17 8.5Z" />` +
                `<path d="M19 20.5C19 16.634 15.866 13.5 12 13.5C8.13401 13.5 5 16.634 5 20.5" />` +
              `</svg>` +
            `</a>` +

            /* Search input (appears below on toggle) — dims via CSS (responsive) */
            `<div id="gn-search-expanded" style="display:none;z-index:10000">` +
              `<div class="bg-white rounded-2xl shadow-2xl p-6 border border-[#e5e2da]">` +
                /* Título */
                `<h3 style="font-family:'Noto Serif',serif;font-size:1.1rem;color:#2D4B33;margin:0 0 0.75rem 0;font-weight:600">${t('nav.search_title', null, 'Buscador')}</h3>` +
                /* Texto intro */
                `<p style="font-size:0.85rem;color:#424842;margin:0 0 1.25rem 0;line-height:1.5">${t('nav.search_intro', null, 'Pregúntame sobre la familia Godes. Usa <strong>@</strong> para acceder al listado de miembros')}</p>` +
                /* Search box */
                `<form id="gn-search-form" class="flex items-center gap-3 bg-[#fcf9f0] rounded-xl p-3 border border-[#e5e2da] mb-4">` +
                  `<span class="flex items-center justify-center text-[#2D4B33] flex-shrink-0">` +
                    `<span class="material-symbols-outlined" style="font-size:20px;font-variation-settings:'FILL' 0,'wght' 300,'GRAD' 0,'opsz' 20">auto_awesome</span>` +
                  `</span>` +
                  `<input id="gn-search-input" type="text" placeholder="${t('nav.search_placeholder', null, 'Escribe tu pregunta')}" autocomplete="off" class="flex-1 border-0 bg-transparent text-[#1c1c17] placeholder-[#b8b5ac] focus:outline-none" style="font-size:0.95rem"/>` +
                  `<button type="submit" class="hidden"></button>` +
                `</form>` +
                /* Botón consultar */
                `<button type="button" id="gn-search-submit" class="w-full bg-[#2D4B33] text-white rounded-lg py-2.5 font-medium text-sm hover:bg-[#1a2f22] transition-colors">${t('nav.search_submit', null, 'Consultar')}</button>` +
              `</div>` +
            `</div>` +

          `</div>` +

        `</div>` +
      `</nav>` +
      renderDrawer()
    );
  }

  // ─── Nav reset styles (injected once, fixes pages with preflight:false) ─────

  function ensureNavResetStyles() {
    if (document.getElementById('gn-reset-styles')) return;
    const style = document.createElement('style');
    style.id = 'gn-reset-styles';
    style.textContent = `
      #godesia-nav { display: block; }
      #godesia-nav a { text-decoration: none; }
      /* Los menús desplegables y el drawer viven en <body>, fuera de #godesia-nav */
      .gn-menu a, #gn-drawer a { text-decoration: none; }
      #godesia-nav .gn-btn {
        border: none; background: none; margin: 0;
        cursor: pointer; -webkit-appearance: none; appearance: none;
        box-sizing: border-box;
      }
      #godesia-nav input:focus {
        outline: none; box-shadow: none !important;
      }
      #godesia-nav form { display: flex; align-items: center; }
      /* Action buttons styling */
      #gn-search-toggle,
      #gn-login-btn {
        border: 1px solid white !important;
        background: transparent !important;
        box-sizing: border-box;
        min-width: 0 !important;
        padding: 0 !important;
      }
      /* Colaborar button */
      #gn-colaborar-btn {
        border: 1px solid white !important;
        background: transparent !important;
        box-sizing: border-box;
      }
      /* Action buttons hover effects */
      #gn-search-toggle:hover,
      #gn-login-btn:hover {
        border-color: rgba(255,255,255,0.7) !important;
        background-color: rgba(255,255,255,0.15) !important;
      }
      #gn-search-toggle:hover svg,
      #gn-login-btn:hover svg {
        stroke: rgba(255,255,255,0.9);
      }
      #gn-colaborar-btn:hover {
        background-color: rgba(255,255,255,0.15) !important;
        color: white !important;
      }
      /* Search expanded visibility across all pages */
      #gn-search-expanded {
        position: fixed !important;
        z-index: 10000 !important;
        right: 1rem;
        width: calc(40vw - 2rem);
        max-width: 720px;
      }
      /* ── Hamburguesa + drawer móvil ── */
      #gn-burger {
        display: none; border: none; background: transparent; color: #fff;
        width: 36px; height: 36px; align-items: center; justify-content: center;
        border-radius: 8px; cursor: pointer; margin-right: 4px; padding: 0;
      }
      #gn-burger:hover { background-color: rgba(255,255,255,0.15); }
      #gn-drawer-backdrop {
        position: fixed; inset: 0; background: rgba(0,0,0,0.45);
        z-index: 9998; opacity: 0; pointer-events: none; transition: opacity .25s ease;
      }
      #gn-drawer.gn-open #gn-drawer-backdrop { opacity: 1; pointer-events: auto; }
      #gn-drawer-panel {
        position: fixed; top: 0; left: 0; bottom: 0; width: min(78vw, 320px);
        background: #2D4B33; z-index: 9999; overflow-y: auto;
        padding: 64px 12px 24px; box-shadow: 2px 0 24px rgba(0,0,0,0.25);
        transform: translateX(-100%); transition: transform .25s ease;
        -webkit-overflow-scrolling: touch;
      }
      #gn-drawer.gn-open #gn-drawer-panel { transform: translateX(0); }
      .gn-drawer-link, .gn-acc-btn {
        display: flex; width: 100%; box-sizing: border-box; align-items: center;
        justify-content: space-between; gap: 8px; padding: 12px 14px;
        border-radius: 10px; color: rgba(255,255,255,0.92); font-size: 0.95rem;
        font-weight: 500; background: none; border: none; text-align: left;
        cursor: pointer; text-decoration: none; font-family: inherit;
      }
      .gn-drawer-link:hover, .gn-acc-btn:hover { background: rgba(255,255,255,0.12); }
      .gn-drawer-active { background: rgba(255,255,255,0.2); font-weight: 600; }
      .gn-drawer-pill { border: 1px solid rgba(255,255,255,0.8); justify-content: center; margin-top: 12px; }
      .gn-acc-body { background: #fff; border-radius: 12px; margin: 2px 4px 8px; padding: 6px 0; }
      .gn-acc-btn .gn-chevron { transition: transform .2s; }
      @media (min-width: 768px) { #gn-drawer { display: none !important; } }
      @media (max-width: 767px) {
        #gn-burger { display: flex; }
        #godesia-nav .gn-center { display: none !important; }
        #gn-colaborar-btn { display: none !important; }
        #gn-search-expanded { left: .5rem !important; right: .5rem !important; width: auto !important; max-width: none !important; }
      }
    `;
    document.head.appendChild(style);
  }

  // ─── Mention autocomplete styles (injected once, for pages without style.css) ──

  function ensureMentionStyles() {
    if (document.getElementById('gn-mention-styles')) return;
    const style = document.createElement('style');
    style.id = 'gn-mention-styles';
    style.textContent = `
      .mention-dropdown {
        display: none; position: fixed; background: #fff; border: 1px solid #c2c8bf;
        border-radius: 10px; box-shadow: 0 6px 20px rgba(0,0,0,.12);
        max-height: 300px; overflow-y: auto; z-index: 10000; min-width: 200px;
      }
      .mention-item {
        display: flex; align-items: center; gap: 8px;
        padding: 7px 10px; cursor: pointer; transition: background .15s;
        border-bottom: 1px solid #f1eee5;
      }
      .mention-item:last-child { border-bottom: none; }
      .mention-item:hover, .mention-item.selected { background: #f1eee5; }
      .mention-photo { width: 28px; height: 28px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 1px solid #c2c8bf; }
      .mention-photo-placeholder {
        width: 28px; height: 28px; border-radius: 50%; background: #dddad1;
        display: flex; align-items: center; justify-content: center;
        flex-shrink: 0; font-weight: 600; color: #1c1c17; font-size: 12px;
      }
      .mention-name { font-size: 13px; color: #1c1c17; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
      .mention-name strong { font-weight: 700; color: #2D4B33; }
      .mention-years { font-size: 12px; color: #424842; flex-shrink: 0; white-space: nowrap; margin-left: auto; padding-left: 6px; }
    `;
    document.head.appendChild(style);
  }

  // ─── Load mention-autocomplete.js if not already present ──────────────────

  function loadMentionAutocomplete(onReady) {
    if (typeof MentionAutocomplete !== 'undefined') {
      onReady();
      return;
    }
    // Check if already being loaded by this page
    if (document.querySelector('script[src*="mention-autocomplete"]')) {
      // Wait for it to finish loading
      const check = setInterval(() => {
        if (typeof MentionAutocomplete !== 'undefined') {
          clearInterval(check);
          onReady();
        }
      }, 50);
      return;
    }
    const s = document.createElement('script');
    s.src = '/mention-autocomplete.js';
    s.onload = onReady;
    document.head.appendChild(s);
  }

  // ─── Behaviour ────────────────────────────────────────────────────────────

  let openMenu = null; // { menu: HTMLElement, chevron: HTMLElement, btn: HTMLElement }
  let closeDrawerFn = () => {}; // lo define init() cuando monta el drawer móvil

  function positionMenu(btn, menu) {
    const rect = btn.getBoundingClientRect();
    menu.style.top  = (rect.bottom + 4) + 'px';
    // Acotar al viewport: el menú (min-width 11rem) no debe salirse por la derecha.
    menu.style.left = '0px';
    const w = menu.offsetWidth;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - w - 8));
    menu.style.left = left + 'px';
  }

  function closeAll() {
    if (openMenu) {
      openMenu.menu.style.display = 'none';
      openMenu.chevron.style.transform = '';
      openMenu = null;
    }
  }

  function ensureMaterialSymbols() {
    if (document.querySelector('link[href*="Material+Symbols"]')) return;
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap';
    document.head.appendChild(link);
  }

  // ─── Smart search: person name → dossier, question → chat ─────────────────

  window.smartSearch = async function(q) {
    const toChat = () => { window.location.href = lhref('/chat.html?q=' + encodeURIComponent(q)); };

    // 1. Query terminada en "?" → chat (pregunta explícita)
    if (q.trim().endsWith('?')) { toChat(); return; }

    // 2. Buscar persona
    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=50`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();

      // 0 resultados → chat (que el LLM lo resuelva)
      if (!data.results || data.results.length === 0) { toChat(); return; }

      // Múltiples resultados → chat con lista de coincidencias
      if (data.results.length > 1) {
        window.location.href = lhref('/chat.html?matches=' + encodeURIComponent(q));
        return;
      }

      // 3. Un solo match: ¿la query es solo el nombre de esa persona?
      const person = data.results[0];
      const normalize = s => s.toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/[^\w\s]/g, ' ')
        .split(/\s+/).filter(Boolean);

      const queryWords = normalize(q);
      const nameWords = new Set(normalize(person.name || ''));
      const allInName = queryWords.length > 0 && queryWords.every(w => nameWords.has(w));

      if (allInName) {
        window.location.href = lhref(`/dossier.html?id=${(person.id || '').replace(/@/g, '')}`);
      } else {
        toChat();
      }
    } catch (e) {
      toChat();
    }
  };

  function init() {
    ensureMaterialSymbols();
    ensureNavResetStyles();
    /* 1. Parse the nav HTML — menus (gn-menu) are siblings of the nav, not inside it */
    const NAV_H = 56; // h-14 = 56px
    const wrapper = document.createElement('div');
    wrapper.innerHTML = renderNav();

    /* The nav element is the first child; gn-menu divs are subsequent siblings */
    const navEl = wrapper.querySelector('#godesia-nav');
    document.body.insertBefore(navEl, document.body.firstChild);

    /* Move gn-menu elements to body (they were rendered as nav siblings in wrapper) */
    [...wrapper.querySelectorAll('.gn-menu')].forEach(m => document.body.appendChild(m));

    /* Drawer móvil (hamburguesa): también sibling del nav → moverlo a body */
    const drawer = wrapper.querySelector('#gn-drawer');
    if (drawer) document.body.appendChild(drawer);
    const burger = navEl.querySelector('#gn-burger');
    if (drawer && burger) {
      const backdrop = drawer.querySelector('#gn-drawer-backdrop');
      const panel    = drawer.querySelector('#gn-drawer-panel');
      const openDrawer = () => {
        drawer.classList.add('gn-open');
        burger.setAttribute('aria-expanded', 'true');
        document.documentElement.style.overflow = 'hidden';
      };
      closeDrawerFn = () => {
        drawer.classList.remove('gn-open');
        burger.setAttribute('aria-expanded', 'false');
        document.documentElement.style.overflow = '';
      };
      burger.addEventListener('click', e => {
        e.stopPropagation();
        if (drawer.classList.contains('gn-open')) closeDrawerFn();
        else openDrawer();
      });
      backdrop.addEventListener('click', closeDrawerFn);
      /* Clic dentro del panel: no cerrar por el listener global; cerrar solo si es un enlace */
      panel.addEventListener('click', e => {
        e.stopPropagation();
        if (e.target.closest('a')) closeDrawerFn();
      });
      /* Acordeones */
      panel.querySelectorAll('.gn-acc-btn').forEach(accBtn => {
        accBtn.addEventListener('click', () => {
          const body = document.getElementById(accBtn.dataset.acc);
          const chev = accBtn.querySelector('.gn-chevron');
          if (!body) return;
          const isOpen = !body.hasAttribute('hidden');
          if (isOpen) { body.setAttribute('hidden', ''); if (chev) chev.style.transform = ''; }
          else        { body.removeAttribute('hidden'); if (chev) chev.style.transform = 'rotate(180deg)'; }
        });
      });
    }

    /* Sesión: si hay usuario, el icono pasa a ser botón de "Salir" (con su nombre). */
    (async function updateAuthButton() {
      const btn = document.getElementById('gn-login-btn');
      if (!btn) return;
      try {
        const res = await fetch('/api/auth/me', { credentials: 'same-origin' });
        if (!res.ok) return;
        const u = await res.json();
        btn.setAttribute('href', '#');
        btn.setAttribute('title', (u.name || u.email || '') + ' · ' + t('nav.logout', null, 'Salir'));
        btn.addEventListener('click', async e => {
          e.preventDefault();
          try { await fetch('/api/auth/logout', { method: 'POST', credentials: 'same-origin' }); } catch (err) {}
          window.location.href = '/login.html';
        });
      } catch (e) { /* sin sesión: se queda como enlace a /login.html */ }
    })();

    /* 2. Dropdown toggle — each .gn-dropdown has data-menu-id pointing to its menu */
    navEl.querySelectorAll('.gn-dropdown').forEach(dd => {
      const btn     = dd.querySelector('.gn-btn');
      const chevron = dd.querySelector('.gn-chevron');
      const menu    = document.getElementById(dd.dataset.menuId);

      btn.addEventListener('click', e => {
        e.stopPropagation();
        const isOpen = menu.style.display !== 'none';
        closeAll();
        if (!isOpen) {
          menu.style.display = 'block';   // visible antes de medir offsetWidth (clamp)
          positionMenu(btn, menu);
          chevron.style.transform = 'rotate(180deg)';
          openMenu = { menu, chevron, btn };
        }
      });
    });

    /* 3. Reposition on scroll (nav is sticky so btn position changes when content scrolls) */
    window.addEventListener('scroll', () => {
      if (openMenu) positionMenu(openMenu.btn, openMenu.menu);
    }, { passive: true });

    /* Resize: cierra dropdowns siempre; cierra el drawer solo si cambia el ANCHO
       (el teclado en pantalla móvil dispara resize vertical y no debe cerrarlo). */
    let lastW = window.innerWidth;
    window.addEventListener('resize', () => {
      closeAll();
      if (window.innerWidth !== lastW) { lastW = window.innerWidth; closeDrawerFn(); }
    });

    /* 4. Close on outside click or Escape */
    document.addEventListener('click', closeAll);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeAll(); closeDrawerFn(); } });

    /* 5. Layout compensation — fixes pages with body{display:flex} or fixed sidebars */
    const bodyFlex      = getComputedStyle(document.body).display === 'flex';
    const dashSidebar   = document.querySelector('.dash-sidebar');
    const needsFixed    = bodyFlex || !!dashSidebar;

    if (needsFixed) {
      // Switch nav from sticky to fixed so it breaks out of any flex/grid parent
      navEl.style.position = 'fixed';
    }

    if (bodyFlex) {
      // chat.html, tree.html: the single flex child needs to start below the fixed nav
      ['.app', '.tree-app'].forEach(sel => {
        const el = document.querySelector(sel);
        if (el) {
          el.style.marginTop = NAV_H + 'px';
          el.style.height    = `calc(100vh - ${NAV_H}px)`;
        }
      });
    }

    if (dashSidebar) {
      // Dashboard pages: old .dash-nav was 64px; new nav is 56px
      dashSidebar.style.top = NAV_H + 'px';
    }

    /* 5b. Prevent clicks inside menus from closing them */
    document.querySelectorAll('.gn-menu').forEach(m => {
      m.addEventListener('click', e => e.stopPropagation());
    });

    /* 5c. Also add search expanded to this rule */
    const searchExpandedLater = document.getElementById('gn-search-expanded');
    if (searchExpandedLater) searchExpandedLater.addEventListener('click', e => e.stopPropagation());

    /* 6. Search toggle: show/hide expanded search input */
    const searchToggle   = document.getElementById('gn-search-toggle');
    const searchExpanded = document.getElementById('gn-search-expanded');
    const searchInput    = document.getElementById('gn-search-input');
    const searchForm     = document.getElementById('gn-search-form');
    const searchSubmit   = document.getElementById('gn-search-submit');

    function positionSearchExpanded() {
      const rect = searchToggle.getBoundingClientRect();
      searchExpanded.style.position = 'fixed';
      searchExpanded.style.top = (rect.bottom + 12) + 'px';
    }

    function closeSearch() {
      searchExpanded.style.display = 'none';
      searchInput.value = '';
      if (openMenu && openMenu.menu === searchExpanded) openMenu = null;
    }

    searchToggle.addEventListener('click', e => {
      e.stopPropagation();
      if (searchExpanded.style.display === 'none') {
        closeAll(); // Close other dropdowns
        searchExpanded.style.display = 'block';
        positionSearchExpanded();
        openMenu = { menu: searchExpanded, chevron: null, btn: searchToggle }; // Track for repositioning on scroll
        searchInput.focus();
      } else {
        closeSearch();
      }
    });

    /* Reposition on scroll */
    window.addEventListener('scroll', () => {
      if (openMenu && openMenu.menu === searchExpanded) positionSearchExpanded();
    }, { passive: true });

    searchInput.addEventListener('blur', () => {
      if (!searchInput.value.trim()) closeSearch();
    });

    searchInput.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeSearch();
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        searchSubmit.click();
      }
    });

    /* Submit → smart routing (dossier if person, chat if question) */
    const handleSearch = () => {
      const q = searchInput.value.trim();
      if (q) {
        closeSearch();
        smartSearch(q);
      }
    };

    searchForm.addEventListener('submit', e => {
      e.preventDefault();
      handleSearch();
    });

    searchSubmit.addEventListener('click', handleSearch);

    /* 7. @ mention autocomplete on the nav search input */
    ensureMentionStyles();
    loadMentionAutocomplete(() => {
      new MentionAutocomplete('#gn-search-input');
    });

    /* 8. Actualiza el menú Documentos dinámicamente según los tipos reales con fotos */
    fetch('/api/documents').then(r => r.json()).then(data => {
      const menu = document.getElementById('gn-menu-documentos');
      if (!menu || !data.types) return;
      const items = data.types.filter(t => t.type !== '__all__');
      if (!items.length) return;
      const links = [
        `<a href="${lhref('/docs.html')}" style="display:block;padding:8px 16px;font-size:13px;color:#1c1c17;text-decoration:none;white-space:nowrap;" onmouseover="this.style.background='#f1eee5'" onmouseout="this.style.background=''">${t('nav.all_docs', null, 'Todos los documentos')}</a>`,
        `<div style="border-top:1px solid #e5e2da;margin:4px 0;"></div>`,
        ...items.map(item =>
          `<a href="${lhref('/docs.html#' + item.type)}" style="display:block;padding:8px 16px;font-size:13px;color:#1c1c17;text-decoration:none;white-space:nowrap;" onmouseover="this.style.background='#f1eee5'" onmouseout="this.style.background=''">${t('doc_types.' + item.type, null, item.label)}</a>`
        )
      ].join('');
      menu.innerHTML = `<div class="bg-white rounded-xl shadow-xl py-1.5 border border-[#e5e2da]" style="min-width:11rem">${links}</div>`;
      /* Reflejar los mismos tipos en el acordeón del drawer móvil */
      const accBody = document.getElementById('gn-acc-documentos');
      if (accBody) {
        const drawerItems = [{ label: t('nav.all_docs', null, 'Todos los documentos'), href: '/docs.html' }]
          .concat(items.map(item => ({ label: t('doc_types.' + item.type, null, item.label), href: '/docs.html#' + item.type })));
        accBody.innerHTML = renderDropdownItems(drawerItems);
      }
    }).catch(() => {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
