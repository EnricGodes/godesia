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
    { label: 'Godes',          href: null },
    { label: 'Godes Diago',    href: null },
    { label: 'Godes Hospital', href: null },
    { label: 'Godes Molina',   href: null },
    { label: 'Godes Schmid',   href: null },
    { label: 'Godes Terrats',  href: null },
    { label: 'Pujol Godes',    href: null },
    { label: 'Diversos',       href: null },
  ];

  const DOCUMENTOS = [
    { label: 'Bautismo',      href: null },
    { label: 'Biografía',     href: null },
    { label: 'Carta',         href: null },
    { label: 'Cementerios',   href: null },
    { label: 'Defunción',     href: null },
    { label: 'Diversos',      href: null },
    { label: 'Documentación', href: null },
    { label: 'Matrimonio',    href: null },
    { label: 'Nacimiento',    href: null },
    { label: 'Obituario',     href: null },
    { label: 'Padrón',        href: null },
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
    const arbolActive = isActivePage('/tree.html') ? ' bg-white/20 font-semibold' : '';
    const chatActive  = isActivePage('/chat.html') ? ' bg-white/20 font-semibold' : '';

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
            `<a href="/tree.html" class="${linkCls}${arbolActive}">Árbol</a>` +
            renderDropdown('ramas',      'Ramas familiares', RAMAS) +
            `<a href="/chat.html" class="${linkCls}${chatActive}">Consultas</a>` +
            renderDropdown('album',      'Álbum',            ALBUM) +
            renderDropdown('documentos', 'Documentos',       DOCUMENTOS) +
            renderDropdown('diversos',   'Diversos',         DIVERSOS) +
          `</div>` +

          /* ── Col 3: Search + buttons (far right) ── */
          `<div class="flex items-center gap-2">` +

            /* Search — collapsed by default, expands on click */
            `<form id="gn-search-form" class="flex items-center">` +
              /* Collapsed state: just the icon + "Buscar" pill */
              `<button type="button" id="gn-search-toggle"` +
              ` class="flex items-center gap-1.5 whitespace-nowrap h-9 px-4 bg-white/10 border border-white/20` +
              ` rounded-full text-white/75 hover:bg-white/20 hover:text-white transition text-sm font-medium">` +
                `<span class="material-symbols-outlined"` +
                ` style="font-size:16px;font-variation-settings:'FILL' 0,'wght' 300,'GRAD' 0,'opsz' 20">auto_awesome</span>` +
                `Buscar` +
              `</button>` +
              /* Expanded state: input + submit (hidden until toggle) */
              `<div id="gn-search-expanded" class="items-center" style="display:none">` +
                `<div class="relative flex items-center">` +
                  `<span class="material-symbols-outlined absolute left-3 text-white/50 pointer-events-none select-none"` +
                  ` style="font-size:16px;font-variation-settings:'FILL' 0,'wght' 300,'GRAD' 0,'opsz' 20">auto_awesome</span>` +
                  `<input id="gn-search-input" type="text" placeholder="Buscar…" autocomplete="off"` +
                  ` class="w-52 lg:w-64 h-9 pl-9 pr-3 text-sm bg-white/10 border border-white/20 rounded-l-full` +
                  ` text-white placeholder-white/45 focus:outline-none focus:bg-white/20 focus:border-white/40 transition"/>` +
                `</div>` +
                `<button type="submit"` +
                ` class="whitespace-nowrap h-9 px-4 bg-white/10 border border-l-0 border-white/20 rounded-r-full` +
                ` text-white/75 hover:bg-white/20 hover:text-white transition text-sm font-medium">` +
                  `Buscar` +
                `</button>` +
              `</div>` +
            `</form>` +

            /* Colaborar — grey pill */
            `<a href="/colaborar.html"` +
            ` class="whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-semibold` +
            ` bg-white/20 text-white hover:bg-white/30 transition-colors">` +
            `Colaborar</a>` +

            /* Login — outlined pill */
            `<a href="/login.html"` +
            ` class="whitespace-nowrap px-4 py-1.5 rounded-full text-sm font-medium` +
            ` border border-white/30 text-white/90 hover:bg-white/15 hover:text-white transition-colors">` +
            `Login</a>` +

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

    /* 6. Search toggle: collapsed pill ↔ expanded input */
    const searchToggle   = document.getElementById('gn-search-toggle');
    const searchExpanded = document.getElementById('gn-search-expanded');
    const searchInput    = document.getElementById('gn-search-input');

    function expandSearch() {
      searchToggle.classList.add('hidden');
      searchExpanded.classList.remove('hidden');
      searchExpanded.style.display = 'flex';
      searchInput.focus();
    }
    function collapseSearch() {
      searchInput.value = '';
      searchExpanded.classList.add('hidden');
      searchExpanded.style.display = '';
      searchToggle.classList.remove('hidden');
    }

    searchToggle.addEventListener('click', e => { e.stopPropagation(); expandSearch(); });
    searchInput.addEventListener('blur', () => { if (!searchInput.value.trim()) collapseSearch(); });
    searchInput.addEventListener('keydown', e => { if (e.key === 'Escape') collapseSearch(); });

    /* Submit → chat page */
    document.getElementById('gn-search-form').addEventListener('submit', e => {
      e.preventDefault();
      const q = searchInput.value.trim();
      if (q) window.location.href = '/chat.html?q=' + encodeURIComponent(q);
    });

    /* 7. @ mention autocomplete on the nav search input */
    ensureMentionStyles();
    loadMentionAutocomplete(() => {
      new MentionAutocomplete('#gn-search-input');
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
