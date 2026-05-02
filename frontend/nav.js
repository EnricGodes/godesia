/**
 * nav.js — Godesia global navigation bar
 *
 * Usage: add  <script src="/nav.js"></script>  anywhere in <body>.
 * Requires Tailwind CSS and the Material Symbols Outlined font on the host page.
 */
(function () {
  'use strict';

  // ─── Menu structure ───────────────────────────────────────────────────────

  const RAMAS = [
    { label: 'Godes',          href: null },
    { label: 'Godes Diago',    href: null },
    { label: 'Godes Hospital', href: null },
    { label: 'Godes Molina',   href: '/godes_molina.html' },
    { label: 'Godes Schmid',   href: null },
    { label: 'Godes Terrats',  href: null },
    { label: 'Pujol Godes',    href: null },
  ];

  const ALBUM = [
    { label: 'Todos los álbumes', href: '/albums.html' },
    { label: 'Godes',             href: '/albums.html#A800008' },
    { label: 'Godes Diago',       href: '/albums.html#A800003' },
    { label: 'Godes Hospital',    href: '/albums.html#A800005' },
    { label: 'Godes Schmid',      href: '/albums.html#A800006' },
    { label: 'Godes Terrats',     href: '/albums.html#A800007' },
    { label: 'Pujol Godes',       href: '/albums.html#A800004' },
    { label: 'Fotos Familiares',  href: '/albums.html#__unassigned__' },
  ];

  const DOCUMENTOS = [
    { label: 'Todos los documentos', href: '/docs.html' },
    { label: 'Bautismos',            href: '/docs.html#bautisme' },
    { label: 'Biografías',           href: '/docs.html#biografia' },
    { label: 'Cartas',               href: '/docs.html#carta' },
    { label: 'Defunciones',          href: '/docs.html#defuncio' },
    { label: 'Matrimonios',          href: '/docs.html#matrimoni' },
    { label: 'Nacimientos',          href: '/docs.html#naixement' },
    { label: 'Padrones',             href: '/docs.html#padro' },
    { label: 'Testamentos',          href: '/docs.html#testament' },
    { label: 'Documentos',           href: '/docs.html#document' },
  ];

  const DIVERSOS = [
    { label: 'Casas Godes',  href: null },
    { label: 'Cementerios',  href: null },
  ];

  // ─── Helpers ──────────────────────────────────────────────────────────────

  const PATH = window.location.pathname;

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
          `<a href="${item.href}" class="block px-4 py-2 text-sm ${active} rounded-md transition-colors">` +
          `${item.label}</a>`
        );
      }
      return (
        `<span class="block px-4 py-2 text-sm text-[#b8b5ac] cursor-not-allowed select-none" title="Próximamente">` +
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
            `<a href="/" class="text-lg font-bold text-white hover:text-white/80 transition-colors"` +
            ` style="font-family:'Noto Serif',serif;letter-spacing:-.01em">Godesia</a>` +
          `</div>` +

          /* ── Col 2: Nav items ── */
          `<div class="flex items-center gap-0.5">` +
            `<a href="/arbol2.html" class="${linkCls}${arbolActive}">Árbol</a>` +
            renderDropdown('ramas',      'Ramas familiares', RAMAS) +
            `<a href="/chat.html" class="${linkCls}${chatActive}">Consultas</a>` +
            renderDropdown('album',      'Álbum',            ALBUM) +
            renderDropdown('documentos', 'Documentos',       DOCUMENTOS) +
            renderDropdown('diversos',   'Diversos',         DIVERSOS) +
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
            `<a href="/colaborar.html" id="gn-colaborar-btn" class="whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-medium text-white/90 border border-white hover:bg-white/15 hover:text-white transition-colors" style="background:transparent">` +
              `Colaborar` +
            `</a>` +

            /* Login — user icon circle */
            `<a href="/login.html" title="Login" class="flex items-center justify-center rounded-full border border-white text-white hover:border-white hover:text-white transition" style="width:28px;height:28px;background:transparent" id="gn-login-btn">` +
              `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">` +
                `<path d="M17 8.5C17 5.73858 14.7614 3.5 12 3.5C9.23858 3.5 7 5.73858 7 8.5C7 11.2614 9.23858 13.5 12 13.5C14.7614 13.5 17 11.2614 17 8.5Z" />` +
                `<path d="M19 20.5C19 16.634 15.866 13.5 12 13.5C8.13401 13.5 5 16.634 5 20.5" />` +
              `</svg>` +
            `</a>` +

            /* Search input (appears below on toggle) */
            `<div id="gn-search-expanded" style="display:none;width:calc(40vw - 2rem);max-width:720px;right:1rem;z-index:10000">` +
              `<div class="bg-white rounded-2xl shadow-2xl p-6 border border-[#e5e2da]">` +
                /* Título */
                `<h3 style="font-family:'Noto Serif',serif;font-size:1.1rem;color:#2D4B33;margin:0 0 0.75rem 0;font-weight:600">Buscador</h3>` +
                /* Texto intro */
                `<p style="font-size:0.85rem;color:#424842;margin:0 0 1.25rem 0;line-height:1.5">Pregúntame sobre la familia Godes. Usa <strong>@</strong> para acceder al listado de miembros</p>` +
                /* Search box */
                `<form id="gn-search-form" class="flex items-center gap-3 bg-[#fcf9f0] rounded-xl p-3 border border-[#e5e2da] mb-4">` +
                  `<span class="flex items-center justify-center text-[#2D4B33] flex-shrink-0">` +
                    `<span class="material-symbols-outlined" style="font-size:20px;font-variation-settings:'FILL' 0,'wght' 300,'GRAD' 0,'opsz' 20">auto_awesome</span>` +
                  `</span>` +
                  `<input id="gn-search-input" type="text" placeholder="Escribe tu pregunta" autocomplete="off" class="flex-1 border-0 bg-transparent text-[#1c1c17] placeholder-[#b8b5ac] focus:outline-none" style="font-size:0.95rem"/>` +
                  `<button type="submit" class="hidden"></button>` +
                `</form>` +
                /* Botón consultar */
                `<button type="button" id="gn-search-submit" class="w-full bg-[#2D4B33] text-white rounded-lg py-2.5 font-medium text-sm hover:bg-[#1a2f22] transition-colors">Consultar</button>` +
              `</div>` +
            `</div>` +

          `</div>` +

        `</div>` +
      `</nav>`
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

  function positionMenu(btn, menu) {
    const rect = btn.getBoundingClientRect();
    menu.style.top  = (rect.bottom + 4) + 'px';
    menu.style.left = rect.left + 'px';
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
    const toChat = () => { window.location.href = '/chat.html?q=' + encodeURIComponent(q); };

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
        window.location.href = '/chat.html?matches=' + encodeURIComponent(q);
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
        window.location.href = `/dossier.html?id=${person.id}`;
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
          positionMenu(btn, menu);
          menu.style.display = 'block';
          chevron.style.transform = 'rotate(180deg)';
          openMenu = { menu, chevron, btn };
        }
      });
    });

    /* 3. Reposition on scroll (nav is sticky so btn position changes when content scrolls) */
    window.addEventListener('scroll', () => {
      if (openMenu) positionMenu(openMenu.btn, openMenu.menu);
    }, { passive: true });

    window.addEventListener('resize', closeAll);

    /* 4. Close on outside click or Escape */
    document.addEventListener('click', closeAll);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeAll(); });

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
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    // Actualiza el menú Documentos dinámicamente según los tipos reales con fotos
    fetch('/api/documents').then(r => r.json()).then(data => {
      const menu = document.getElementById('gn-menu-documentos');
      if (!menu || !data.types) return;
      const items = data.types.filter(t => t.type !== '__all__');
      if (!items.length) return;
      const links = [
        `<a href="/docs.html" style="display:block;padding:8px 16px;font-size:13px;color:#1c1c17;text-decoration:none;white-space:nowrap;" onmouseover="this.style.background='#f1eee5'" onmouseout="this.style.background=''">Todos los documentos</a>`,
        `<div style="border-top:1px solid #e5e2da;margin:4px 0;"></div>`,
        ...items.map(t =>
          `<a href="/docs.html#${t.type}" style="display:block;padding:8px 16px;font-size:13px;color:#1c1c17;text-decoration:none;white-space:nowrap;" onmouseover="this.style.background='#f1eee5'" onmouseout="this.style.background=''">${t.label}</a>`
        )
      ].join('');
      menu.innerHTML = `<div style="padding:4px 0;">${links}</div>`;
    }).catch(() => {});

    init();
  }
}());
