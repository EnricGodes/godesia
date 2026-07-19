/* ==========================================================================
   Emili Godes — microsite independiente
   Cabecera/navegación propia, selector ES/CA (hardcoded, sin i18n del backend),
   drawer móvil, carga de galerías desde JSON, lightbox y filtro por década.
   ========================================================================== */
(function () {
  'use strict';

  var BASE = '/emili-godes/';

  var NAV = [
    { href: 'index.html',          es: 'Inicio',                 ca: 'Inici' },
    { href: 'biografia.html',      es: 'Biografía',              ca: 'Biografia' },
    { href: 'obra.html',           es: 'La obra',                ca: "L'obra" },
    { href: 'mirada-moderna.html', es: 'Una mirada moderna',     ca: 'Una mirada moderna' },
    { href: 'destacadas.html',     es: 'Fotografías destacadas', ca: 'Fotografies destacades' },
    { href: 'legado.html',         es: 'Reconocimiento y legado', ca: 'Reconeixement i llegat' },
    { href: 'archivo.html',        es: 'El archivo',             ca: "L'arxiu" },
    { href: 'investigacion.html',  es: 'La investigación',       ca: 'La recerca' }
  ];

  var STR = {
    back:     { es: '← Godesia', ca: '← Godesia' },
    credits:  { es: 'Créditos y fuentes', ca: 'Crèdits i fonts' },
    tagline:  { es: 'Fotógrafo de la modernidad', ca: 'Fotògraf de la modernitat' },
    menu:     { es: 'Menú', ca: 'Menú' },
    soon:     { es: 'Galería en preparación. Las imágenes se incorporarán próximamente.',
                ca: 'Galeria en preparació. Les imatges s’incorporaran properament.' },
    footerNote: { es: 'Web dedicada al fotógrafo Emili Godes (1895–1970). Parte del proyecto Godesia.',
                  ca: 'Web dedicada al fotògraf Emili Godes (1895–1970). Part del projecte Godesia.' }
  };

  // ── Idioma ───────────────────────────────────────────────────────────────
  function getLang() {
    var l = null;
    try { l = localStorage.getItem('emili_lang'); } catch (e) {}
    return l === 'ca' ? 'ca' : 'es';
  }
  function setLang(lang) {
    lang = lang === 'ca' ? 'ca' : 'es';
    try { localStorage.setItem('emili_lang', lang); } catch (e) {}
    applyLang(lang);
  }
  function applyLang(lang) {
    document.body.classList.toggle('eg-ca', lang === 'ca');
    document.documentElement.setAttribute('lang', lang);
    // data-es / data-ca en cadenas cortas
    var nodes = document.querySelectorAll('[data-es]');
    for (var i = 0; i < nodes.length; i++) {
      var v = nodes[i].getAttribute('data-' + lang);
      if (v != null) nodes[i].textContent = v;
    }
    // data-alt-es / data-alt-ca en imágenes (texto alternativo bilingüe)
    var imgs = document.querySelectorAll('[data-alt-es]');
    for (var k = 0; k < imgs.length; k++) {
      var av = imgs[k].getAttribute('data-alt-' + lang);
      if (av != null) imgs[k].setAttribute('alt', av);
    }
    // botones del selector
    var b = document.querySelectorAll('.eg-lang button');
    for (var j = 0; j < b.length; j++) b[j].classList.toggle('is-active', b[j].dataset.lang === lang);
    document.title = document.title; // no-op, título ya bilingüe si procede
    window.EG.lang = lang;
  }
  function t(obj) { return obj[getLang()] || obj.es; }

  // ── Header ────────────────────────────────────────────────────────────────
  function currentPage() {
    var p = location.pathname.replace(BASE, '').replace(/^\//, '');
    return p === '' ? 'index.html' : p;
  }
  function buildHeader() {
    var cur = currentPage();
    var navLinks = NAV.map(function (n) {
      var active = n.href === cur ? ' is-active' : '';
      return '<a href="' + BASE + n.href + '" class="' + active.trim() + '" data-es="' + n.es + '" data-ca="' + n.ca + '">' + n.es + '</a>';
    }).join('');

    var header = document.createElement('header');
    header.className = 'eg-header';
    header.innerHTML =
      '<div class="eg-header__inner">' +
        '<a class="eg-brand" href="' + BASE + 'index.html">Emili Godes' +
          '<small data-es="' + STR.tagline.es + '" data-ca="' + STR.tagline.ca + '">' + STR.tagline.es + '</small>' +
        '</a>' +
        '<nav class="eg-nav">' + navLinks + '</nav>' +
        '<div class="eg-tools">' +
          '<div class="eg-lang" role="group" aria-label="Idioma / Llengua">' +
            '<button type="button" data-lang="es" aria-label="Castellano">ES</button>' +
            '<span>·</span>' +
            '<button type="button" data-lang="ca" aria-label="Català">CA</button>' +
          '</div>' +
          '<a class="eg-back" href="/" data-es="' + STR.back.es + '" data-ca="' + STR.back.ca + '">' + STR.back.es + '</a>' +
        '</div>' +
        '<button class="eg-burger" type="button" aria-label="Menú" aria-expanded="false"><span class="material-symbols-outlined">menu</span></button>' +
      '</div>';
    document.body.insertBefore(header, document.body.firstChild);

    // Drawer
    var backdrop = document.createElement('div');
    backdrop.className = 'eg-drawer-backdrop';
    var drawer = document.createElement('nav');
    drawer.className = 'eg-drawer';
    var drawerLinks = NAV.concat([{ href: 'creditos.html', es: STR.credits.es, ca: STR.credits.ca }]).map(function (n) {
      var active = n.href === cur ? ' is-active' : '';
      return '<a href="' + BASE + n.href + '" class="' + active.trim() + '" data-es="' + n.es + '" data-ca="' + n.ca + '">' + n.es + '</a>';
    }).join('');
    drawer.innerHTML =
      '<button class="eg-drawer__close" type="button" aria-label="Cerrar"><span class="material-symbols-outlined">close</span></button>' +
      drawerLinks +
      '<a href="/" style="margin-top:12px;color:var(--secondary)" data-es="' + STR.back.es + '" data-ca="' + STR.back.ca + '">' + STR.back.es + '</a>' +
      '<div class="eg-lang" style="margin-top:16px">' +
        '<button type="button" data-lang="es" style="color:var(--on-surface-variant)">ES</button><span>·</span>' +
        '<button type="button" data-lang="ca" style="color:var(--on-surface-variant)">CA</button>' +
      '</div>';
    document.body.appendChild(backdrop);
    document.body.appendChild(drawer);

    function closeDrawer() { drawer.classList.remove('open'); backdrop.classList.remove('open'); header.querySelector('.eg-burger').setAttribute('aria-expanded', 'false'); }
    header.querySelector('.eg-burger').addEventListener('click', function () { drawer.classList.add('open'); backdrop.classList.add('open'); this.setAttribute('aria-expanded', 'true'); });
    drawer.querySelector('.eg-drawer__close').addEventListener('click', closeDrawer);
    backdrop.addEventListener('click', closeDrawer);

    // Toggle de idioma (header + drawer)
    document.querySelectorAll('.eg-lang button').forEach(function (btn) {
      btn.addEventListener('click', function () { setLang(this.dataset.lang); });
    });
  }

  // ── Footer ────────────────────────────────────────────────────────────────
  function buildFooter() {
    var links = NAV.concat([{ href: 'creditos.html', es: STR.credits.es, ca: STR.credits.ca }]).map(function (n) {
      return '<a href="' + BASE + n.href + '" data-es="' + n.es + '" data-ca="' + n.ca + '">' + n.es + '</a>';
    }).join('');
    var footer = document.createElement('footer');
    footer.className = 'eg-footer';
    footer.innerHTML =
      '<div class="eg-container eg-footer__grid">' +
        '<div style="max-width:340px">' +
          '<div class="eg-brand" style="color:#fff;font-size:1.1rem">Emili Godes</div>' +
          '<p style="font-size:.85rem;margin:.6em 0 0" data-es="' + STR.footerNote.es + '" data-ca="' + STR.footerNote.ca + '">' + STR.footerNote.es + '</p>' +
        '</div>' +
        '<nav class="eg-footer__nav">' + links + '</nav>' +
      '</div>' +
      '<div class="eg-container" style="margin-top:26px"><small>© Familia Godes · Emili Godes 1895–1970</small></div>';
    document.body.appendChild(footer);
  }

  // ── Galerías desde JSON ────────────────────────────────────────────────────
  function ambitoLabel(item) {
    var lang = getLang();
    return item['titulo_' + lang] || item.titulo_es || item.title || '';
  }
  function renderThumbs(container, items) {
    if (!items || !items.length) {
      container.innerHTML = '<div class="eg-empty"><span class="material-symbols-outlined">image</span>' +
        '<span data-es="' + STR.soon.es + '" data-ca="' + STR.soon.ca + '">' + STR.soon.es + '</span></div>';
      applyLang(getLang());
      return;
    }
    var grid = document.createElement('div');
    grid.className = 'eg-gallery';
    items.forEach(function (it) {
      var cell = document.createElement('div');
      cell.className = 'eg-thumb';
      if (it.image) {
        cell.innerHTML = '<img loading="lazy" src="' + it.image + '" alt="' + (ambitoLabel(it) || '') + '">' +
          '<div class="eg-thumb__meta">' + (ambitoLabel(it) || '') + '</div>';
        cell.addEventListener('click', function () { openLightbox(it); });
      } else {
        cell.innerHTML = '<div class="eg-thumb__meta">' + (ambitoLabel(it) || '') + '</div>';
      }
      grid.appendChild(cell);
    });
    container.innerHTML = '';
    container.appendChild(grid);
  }

  function loadObra() {
    var mounts = document.querySelectorAll('[data-gallery]');
    if (!mounts.length) return;
    fetch(BASE + 'data/obra.json').then(function (r) { return r.ok ? r.json() : {}; }).then(function (data) {
      mounts.forEach(function (m) {
        var key = m.getAttribute('data-gallery');
        renderThumbs(m, (data && data[key]) || []);
      });
    }).catch(function () {
      mounts.forEach(function (m) { renderThumbs(m, []); });
    });
  }

  function loadDestacadas() {
    var mount = document.getElementById('eg-destacadas');
    if (!mount) return;
    fetch(BASE + 'data/destacadas.json').then(function (r) { return r.ok ? r.json() : []; }).then(function (items) {
      renderFeatured(mount, items || []);
    }).catch(function () { renderFeatured(mount, []); });
  }
  function renderFeatured(mount, items) {
    var lang = getLang();
    if (!items.length) {
      mount.innerHTML = '<div class="eg-empty"><span class="material-symbols-outlined">photo_library</span>' +
        '<span data-es="' + STR.soon.es + '" data-ca="' + STR.soon.ca + '">' + STR.soon.es + '</span></div>';
      return;
    }
    var grid = document.createElement('div');
    grid.className = 'eg-featgrid';
    items.sort(function (a, b) { return (a.orden || 0) - (b.orden || 0); });
    items.forEach(function (it) {
      var card = document.createElement('article');
      card.className = 'eg-feat';
      var img = it.image
        ? '<div class="eg-feat__img"><img loading="lazy" src="' + it.image + '" alt=""></div>'
        : '<div class="eg-feat__img"><span class="material-symbols-outlined" style="font-size:40px">image</span></div>';
      var meta = [it.fecha, it.institucion, it.num_catalogo].filter(Boolean).join(' · ');
      card.innerHTML = img +
        '<div class="eg-feat__body">' +
          '<div class="eg-feat__title">' + (it['titulo_' + lang] || it.titulo_es || '') + '</div>' +
          '<div class="eg-feat__meta">' + meta + '</div>' +
          '<div class="eg-feat__why">' + (it['porque_' + lang] || it.porque_es || '') + '</div>' +
          (it.fuente ? '<div class="eg-feat__src">' + it.fuente + '</div>' : '') +
        '</div>';
      grid.appendChild(card);
    });
    mount.innerHTML = '';
    mount.appendChild(grid);
  }

  // ── Lightbox ───────────────────────────────────────────────────────────────
  var lb;
  function ensureLightbox() {
    if (lb) return lb;
    lb = document.createElement('div');
    lb.className = 'eg-lb';
    lb.innerHTML = '<button class="eg-lb__close" aria-label="Cerrar"><span class="material-symbols-outlined">close</span></button>' +
      '<div class="eg-lb__panel"><div class="eg-lb__img"></div><div class="eg-lb__body"></div></div>';
    document.body.appendChild(lb);
    lb.querySelector('.eg-lb__close').addEventListener('click', closeLightbox);
    lb.addEventListener('click', function (e) { if (e.target === lb) closeLightbox(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeLightbox(); });
    return lb;
  }
  function openLightbox(it) {
    var lang = getLang();
    ensureLightbox();
    lb.querySelector('.eg-lb__img').innerHTML = it.image ? '<img src="' + it.image + '" alt="">' : '';
    var rows = [
      ['', it['titulo_' + lang] || it.titulo_es],
      [lang === 'ca' ? 'Data' : 'Fecha', it.fecha],
      [lang === 'ca' ? 'Àmbit' : 'Ámbito', it.ambito],
      [lang === 'ca' ? 'Tècnica' : 'Técnica', it.tecnica],
      ['Institució/Institución'.split('/')[lang === 'ca' ? 0 : 1], it.institucion],
      [lang === 'ca' ? 'Núm. catàleg' : 'Nº catálogo', it.num_catalogo],
      [lang === 'ca' ? 'Crèdit' : 'Crédito', it.credito]
    ].filter(function (r) { return r[1]; });
    var body = '<h3 style="margin:0 0 12px">' + (it['titulo_' + lang] || it.titulo_es || '') + '</h3>';
    body += rows.slice(1).map(function (r) {
      return '<div style="margin:.35em 0"><strong style="color:var(--secondary);font-size:.82rem">' + r[0] + ':</strong> ' + r[1] + '</div>';
    }).join('');
    var why = it['porque_' + lang] || it.porque_es;
    if (why) body += '<p style="margin-top:14px">' + why + '</p>';
    if (it.fuente) body += '<p class="eg-feat__src">' + it.fuente + '</p>';
    lb.querySelector('.eg-lb__body').innerHTML = body;
    lb.classList.add('open');
  }
  function closeLightbox() { if (lb) lb.classList.remove('open'); }

  // ── Filtro por década (legado) ─────────────────────────────────────────────
  function initDecadeFilter() {
    var bar = document.querySelector('[data-decade-filter]');
    if (!bar) return;
    bar.addEventListener('click', function (e) {
      var chip = e.target.closest('.eg-chip');
      if (!chip) return;
      var dec = chip.dataset.decade;
      bar.querySelectorAll('.eg-chip').forEach(function (c) { c.classList.toggle('is-active', c === chip); });
      document.querySelectorAll('[data-decades] tbody tr').forEach(function (row) {
        var ds = (row.getAttribute('data-decade') || '').split(' ');
        row.classList.toggle('is-hidden', dec !== 'all' && ds.indexOf(dec) === -1);
      });
    });
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  window.EG = { lang: getLang(), setLang: setLang, openLightbox: openLightbox, t: t };
  function init() {
    buildHeader();
    buildFooter();
    applyLang(getLang());
    loadObra();
    loadDestacadas();
    initDecadeFilter();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
