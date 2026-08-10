/* ==========================================================================
   Emili Godes — microsite independiente
   Cabecera/navegación propia, selector ES/CA (hardcoded, sin i18n del backend),
   drawer móvil, carga de galerías desde JSON, lightbox y filtro por década.
   ========================================================================== */
(function () {
  'use strict';

  var BASE = '/emili-godes/';
  var _obraRerender = null;   // hook: re-render del explorador al cambiar idioma

  var NAV = [
    { href: 'biografia.html',      es: 'Biografía',      ca: 'Biografia' },
    { href: 'obra.html',           es: 'Obra',           ca: 'Obra' },
    { href: 'mirada-moderna.html', es: 'Mirada',         ca: 'Mirada' },
    { href: 'destacadas.html',     es: 'Destacadas',     ca: 'Destacades' },
    { href: 'legado.html',         es: 'Reconocimiento', ca: 'Reconeixement' },
    { href: 'investigacion.html',  es: 'Estudio',        ca: 'Estudi' }
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
    return l === 'es' ? 'es' : 'ca';   // por defecto catalán; solo 'es' si el usuario lo eligió
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
    window.EG.lang = lang;
    if (_obraRerender) _obraRerender();
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
        '<a class="eg-brand" href="' + BASE + 'index.html">Emili Godes</a>' +
        '<nav class="eg-nav">' + navLinks + '</nav>' +
        '<div class="eg-tools">' +
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
      '<div class="eg-container eg-footer__bottom">' +
        '<small>© Familia Godes · Emili Godes 1895–1970</small>' +
        '<div class="eg-lang" role="group" aria-label="Idioma / Llengua">' +
          '<button type="button" data-lang="es" aria-label="Castellano">ES</button>' +
          '<span>·</span>' +
          '<button type="button" data-lang="ca" aria-label="Català">CA</button>' +
        '</div>' +
      '</div>';
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
    if (!items.length) {
      mount.innerHTML = '<div class="eg-empty"><span class="material-symbols-outlined">photo_library</span>' +
        '<span data-es="' + STR.soon.es + '" data-ca="' + STR.soon.ca + '">' + STR.soon.es + '</span></div>';
      return;
    }
    items.sort(function (a, b) { return (a.orden || 0) - (b.orden || 0); });
    window.__destacadas = items;
    var grid = document.createElement('div');
    grid.className = 'eg-featgrid';
    items.forEach(function (it, i) {
      var card = document.createElement('article');
      card.className = 'eg-feat';
      var img = it.image
        ? '<div class="eg-feat__img"><img src="' + it.image + '" alt="' + esc(L(it, 'titulo')) + '"></div>'
        : '<div class="eg-feat__img"><span class="material-symbols-outlined" style="font-size:40px">image</span></div>';
      var meta = [it.fecha, L(it, 'lugar'), it.fondo].filter(Boolean).join(' · ');
      card.innerHTML = img +
        '<div class="eg-feat__body">' +
          '<div class="eg-feat__title">' + esc(L(it, 'titulo')) + '</div>' +
          '<div class="eg-feat__meta">' + esc(meta) + '</div>' +
        '</div>';
      if (it.image) { card.style.cursor = 'pointer'; card.addEventListener('click', function () { EG.destacadaOpen(i); }); }
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

  // ── Explorador de La obra (tipo álbumes) ────────────────────────────────────
  var OBRA_TEXTS = {
    fotografia_artistica: { es: ['Fotografía artística', 'La fotografía artística fue una dimensión constante en la trayectoria de Emili Godes. Desde sus primeros trabajos y participaciones en concursos hasta sus series de Córdoba, sus imágenes exploran la composición, la atmósfera, la luz y la capacidad de la fotografía para construir una mirada personal sobre el mundo.\n\nEsta categoría incluye únicamente imágenes concebidas principalmente como creación fotográfica, no cualquier fotografía visualmente atractiva realizada dentro de un encargo profesional.'],
      ca: ['Fotografia artística', 'La fotografia artística va ser una dimensió constant en la trajectòria d’Emili Godes. Des dels seus primers treballs i participacions en concursos fins a les seves sèries de Còrdova, les seves imatges exploren la composició, l’atmosfera, la llum i la capacitat de la fotografia per construir una mirada personal sobre el món.\n\nAquesta categoria inclou únicament imatges concebudes principalment com a creació fotogràfica, no qualsevol fotografia visualment atractiva realitzada dins d’un encàrrec professional.'] },
    fotografia_industrial: { es: ['Fotografía industrial', 'Godes realizó una extensa producción industrial para empresas y fábricas. Sus imágenes documentan instalaciones, procesos de fabricación, maquinaria, trabajadores y productos, pero no se limitan a registrar lo que encuentra: ordenan el espacio, estudian la luz y convierten la industria en una imagen de modernidad y progreso.'],
      ca: ['Fotografia industrial', 'Godes va realitzar una extensa producció industrial per a empreses i fàbriques. Les seves imatges documenten instal·lacions, processos de fabricació, maquinària, treballadors i productes, però no es limiten a registrar allò que troben: ordenen l’espai, estudien la llum i converteixen la indústria en una imatge de modernitat i progrés.'] },
    publicidad: { es: ['Publicidad y encargo', 'La fotografía publicitaria exigía claridad, precisión y capacidad para convertir un producto o un servicio en una imagen atractiva. Godes trabajó para distintas empresas y aplicó a estos encargos recursos asociados a la fotografía moderna: encuadres rigurosos, contrastes, geometrías y una atención especial a la iluminación.'],
      ca: ['Publicitat i encàrrec', 'La fotografia publicitària exigia claredat, precisió i capacitat per convertir un producte o un servei en una imatge atractiva. Godes va treballar per a diverses empreses i va aplicar a aquests encàrrecs recursos associats a la fotografia moderna: enquadraments rigorosos, contrastos, geometries i una atenció especial a la il·luminació.'] },
    ciencia_medicina: { es: ['Ciencia y medicina', 'La relación de Godes con científicos, médicos e instituciones de investigación lo llevó a trabajar con plantas, insectos, estructuras naturales, operaciones e investigaciones médicas. En estas imágenes la precisión técnica y la utilidad documental conviven con una fuerte dimensión visual. Su colaboración con Francisco García del Cid y la Escola Superior d’Agricultura fue clave.'],
      ca: ['Ciència i medicina', 'La relació de Godes amb científics, metges i institucions de recerca el va portar a treballar amb plantes, insectes, estructures naturals, operacions i investigacions mèdiques. En aquestes imatges la precisió tècnica i la utilitat documental conviuen amb una forta dimensió visual. La seva col·laboració amb Francisco García del Cid i l’Escola Superior d’Agricultura va ser clau.'] },
    reproduccion_arte: { es: ['Reproducción de obras de arte', 'Godes fotografió pinturas, esculturas, cerámicas, piezas de joyería y otras obras artísticas para artistas, galerías, publicaciones y catálogos. Esta actividad exigía dominar la iluminación, la reproducción tonal, la escala y la fidelidad al original, y lo mantuvo en contacto directo con la producción artística de su época.'],
      ca: ['Reproducció d’obres d’art', 'Godes va fotografiar pintures, escultures, ceràmiques, peces de joieria i altres obres artístiques per a artistes, galeries, publicacions i catàlegs. Aquesta activitat exigia dominar la il·luminació, la reproducció tonal, l’escala i la fidelitat a l’original, i el va mantenir en contacte directe amb la producció artística del seu temps.'] },
    foto_fija_cine: { es: ['Fotografía y cine', 'Desde los años treinta Godes trabajó como fotógrafo de foto fija, principalmente para los estudios Orphea. Documentó escenas, rodajes, decorados, actores y materiales de producción. La investigación ha identificado su participación en más de cincuenta películas.'],
      ca: ['Fotografia i cinema', 'Des dels anys trenta Godes va treballar com a fotògraf de foto fixa, principalment per als estudis Orphea. Va documentar escenes, rodatges, decorats, actors i materials de producció. La recerca ha identificat la seva participació en més de cinquanta pel·lícules.'] },
    arquitectura_instalaciones: { es: ['Arquitectura e instalaciones', 'La arquitectura aparece en muchos de sus reportajes: edificios, fábricas, laboratorios, instalaciones científicas, espacios expositivos y residencias. Godes utilizó la cámara para explicar cómo se organizan los espacios y cómo la arquitectura representa una idea de progreso, eficacia o distinción.'],
      ca: ['Arquitectura i instal·lacions', 'L’arquitectura apareix en molts dels seus reportatges: edificis, fàbriques, laboratoris, instal·lacions científiques, espais expositius i residències. Godes va utilitzar la càmera per explicar com s’organitzen els espais i com l’arquitectura representa una idea de progrés, eficàcia o distinció.'] },
    reportajes_urbanos_documentales: { es: ['Reportajes urbanos y documentales', 'Los reportajes de Córdoba, Barcelona y otros entornos muestran la capacidad de Godes para observar ciudades, calles, monumentos, actividades y transformaciones sociales. Son imágenes documentales, pero también construcciones visuales en las que importan la perspectiva, la luz, la escala y el ritmo.'],
      ca: ['Reportatges urbans i documentals', 'Els reportatges de Còrdova, Barcelona i altres entorns mostren la capacitat de Godes per observar ciutats, carrers, monuments, activitats i transformacions socials. Són imatges documentals, però també construccions visuals en què importen la perspectiva, la llum, l’escala i el ritme.'] },
    experimentacion_fotografica: { es: ['Experimentación fotográfica', 'Godes exploró dobles exposiciones, fotogramas, encuadres poco convencionales, contrastes, ampliaciones y técnicas de aproximación. En esta categoría se reúnen las imágenes en las que la investigación formal y técnica es el elemento principal.'],
      ca: ['Experimentació fotogràfica', 'Godes va explorar dobles exposicions, fotogrames, enquadraments poc convencionals, contrastos, ampliacions i tècniques d’aproximació. En aquesta categoria es reuneixen les imatges en què la recerca formal i tècnica és l’element principal.'] },
    fotografia_familiar: { es: ['Fotografía familiar', 'Godes dirigió la cámara también hacia los suyos. Estas imágenes retratan a la familia Godes entre las décadas de 1910 y 1920: retratos de su hija Montserrat, de sus hermanos y de sus padres, primeras comuniones, bodas, excursiones a Montserrat, la nevada de 1924 y la vida cotidiana en la casa de la calle Bertran de Barcelona.\n\nEl conjunto incluye placas estereoscópicas para taxifoto y constituye, además de un álbum familiar, un banco de pruebas donde ensayó encuadres, luz y retrato con los modelos que tenía más cerca.'],
      ca: ['Fotografia familiar', 'Godes va dirigir la càmera també cap als seus. Aquestes imatges retraten la família Godes entre les dècades de 1910 i 1920: retrats de la seva filla Montserrat, dels seus germans i dels seus pares, primeres comunions, casaments, excursions a Montserrat, la nevada del 1924 i la vida quotidiana a la casa del carrer Bertran de Barcelona.\n\nEl conjunt inclou plaques estereoscòpiques per a taxifot i constitueix, a més d’un àlbum familiar, un banc de proves on va assajar enquadraments, llum i retrat amb els models que tenia més a prop.'] },
  };
  var UI = {
    themes: { es: 'Temáticas', ca: 'Temàtiques' },
    allThemes: { es: 'Todas las temáticas', ca: 'Totes les temàtiques' },
    decades: { es: 'Décadas', ca: 'Dècades' },
    funds: { es: 'Fondos', ca: 'Fons' },
    all: { es: 'Todas', ca: 'Totes' },
    search: { es: 'Buscar proyecto, lugar…', ca: 'Cerca projecte, lloc…' },
    sortCount: { es: 'Más fotos', ca: 'Més fotos' },
    sortName: { es: 'Nombre A–Z', ca: 'Nom A–Z' },
    sortDate: { es: 'Fecha', ca: 'Data' },
    photos: { es: 'fotos', ca: 'fotos' },
    pick: { es: 'Elige una temática en el panel izquierdo para empezar a explorar.', ca: 'Tria una temàtica al panell esquerre per començar a explorar.' },
    noresults: { es: 'Sin resultados con estos filtros.', ca: 'Sense resultats amb aquests filtres.' },
    backAll: { es: 'Todos los proyectos', ca: 'Tots els projectes' },
    sf: { es: 's. f.', ca: 's. d.' },
  };

  var obra = { data: null, ambito: null, project: null, decade: 'all', fondo: 'all', q: '', sort: 'date' };

  function esc(s) { return (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function norm(s) { return (s || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''); }
  // Campo biling\u00fce: obj[f+'_'+lang] \u2192 obj[f+'_es'] \u2192 obj[f] \u2192 ''
  function L(obj, f) {
    if (!obj) return '';
    var lang = getLang(), v = obj[f + '_' + lang];
    return (v != null ? v : null) || obj[f + '_es'] || obj[f] || '';
  }

  // Etiqueta de una temática en el idioma activo (cae al slug si no está en OBRA_TEXTS).
  function ambitoLabel(k) {
    var txt = OBRA_TEXTS[k];
    return (txt && txt[getLang()]) ? txt[getLang()][0] : k;
  }
  // Temáticas ordenadas alfabéticamente por su etiqueta en el idioma activo.
  function orderedAmbitos() {
    if (!obra.data) return [];
    return (obra.data.ambito_order || []).slice().sort(function (a, b) {
      return ambitoLabel(a).localeCompare(ambitoLabel(b), getLang(), { sensitivity: 'base' });
    });
  }

  function initObra() {
    var root = document.getElementById('eg-obra');
    if (!root) return;
    fetch(BASE + 'data/obra.json').then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        obra.data = d || { ambito_order: [], ambitos: {}, decades: [] };
        if (obra.data.ambito_order.length) obra.ambito = orderedAmbitos()[0];
        _obraRerender = renderObra;
        _obraFromHash();
        window.addEventListener('hashchange', function () { _obraFromHash(); renderObra(); });
        renderObra();
      }).catch(function () {
        document.getElementById('eg-obra-main').innerHTML =
          '<p class="eg-empty">No se pudo cargar el catálogo.</p>';
      });
  }

  function _obraFromHash() {
    var h = decodeURIComponent((location.hash || '').replace(/^#/, ''));
    if (!h) return;
    var parts = h.split('/');
    if (obra.data.ambitos[parts[0]]) {
      obra.ambito = parts[0]; obra.project = parts[1] || null;
      obra._pendingPhoto = (parts[1] && parts[2] != null && parts[2] !== '') ? parseInt(parts[2], 10) : null;
    }
  }
  function _obraSetHash() {
    var h = obra.ambito ? obra.ambito + (obra.project ? '/' + obra.project : '') : '';
    if (decodeURIComponent((location.hash || '').replace(/^#/, '')) !== h) {
      history.replaceState(null, '', h ? '#' + h : location.pathname);
    }
  }
  function renderObra() {
    if (!obra.data) return;
    _obraSetHash();
    renderSide();
    renderMain();
    if (obra._pendingPhoto != null && obra._photos && obra._photos[obra._pendingPhoto]) {
      var idx = obra._pendingPhoto; obra._pendingPhoto = null;
      egViewerOpen(obra._photos, idx);
    } else { obra._pendingPhoto = null; }
  }

  function renderSide() {
    var d = obra.data;
    var themes = '<button class="eg-side-link' + (obra.ambito === null ? ' is-active' : '') +
      '" onclick="EG.obraAllThemes()"><span>' + esc(t(UI.allThemes)) + '</span>' +
      '<span class="eg-side-count">' + (d.total || '') + '</span></button>' +
      orderedAmbitos().map(function (k) {
        var a = d.ambitos[k]; if (!a) return '';
        var label = ambitoLabel(k);
        var active = k === obra.ambito ? ' is-active' : '';
        return '<button class="eg-side-link' + active + '" onclick="EG.obraTheme(\'' + k + '\')">' +
          '<span>' + esc(label) + '</span><span class="eg-side-count">' + a.count + '</span></button>';
      }).join('');
    var decs = ['<span class="eg-chip' + (obra.decade === 'all' ? ' is-active' : '') + '" onclick="EG.obraDecade(\'all\')">' + t(UI.all) + '</span>']
      .concat((d.decades || []).map(function (dc) {
        return '<span class="eg-chip' + (obra.decade === dc ? ' is-active' : '') + '" onclick="EG.obraDecade(\'' + dc + '\')">' + dc + 's</span>';
      })).join('');
    var fonds = ['<span class="eg-chip' + (obra.fondo === 'all' ? ' is-active' : '') + '" onclick="EG.obraFondo(-1)">' + t(UI.all) + '</span>']
      .concat((d.fondos || []).map(function (f, i) {
        return '<span class="eg-chip' + (obra.fondo === f ? ' is-active' : '') + '" onclick="EG.obraFondo(' + i + ')">' + esc(f) + '</span>';
      })).join('');
    document.getElementById('eg-obra-side').innerHTML =
      '<h4>' + t(UI.themes) + '</h4>' + themes +
      '<h4 style="margin-top:20px">' + t(UI.decades) + '</h4><div class="eg-side-decades">' + decs + '</div>' +
      '<h4 style="margin-top:20px">' + t(UI.funds) + '</h4><div class="eg-side-decades">' + fonds + '</div>';
  }

  function _matchDecade(photos) {
    if (obra.decade === 'all') return true;
    return photos.some(function (p) { return p.decada === obra.decade; });
  }
  function _matchFondo(photos) {
    if (obra.fondo === 'all') return true;
    return photos.some(function (p) { return p.fondo === obra.fondo; });
  }

  function renderMain() {
    var main = document.getElementById('eg-obra-main');
    if (obra.ambito === null) { main.innerHTML = renderFlat(); return; }
    if (!obra.ambito) { main.innerHTML = '<p class="eg-empty">' + t(UI.pick) + '</p>'; return; }
    var a = obra.data.ambitos[obra.ambito];
    var txt = OBRA_TEXTS[obra.ambito];
    var header = '';
    if (txt) {
      header = '<p class="eg-kicker">' + esc(txt[getLang()][0]) + '</p>' +
        '<div class="lang-es eg-prose" style="max-width:760px">' + txt.es[1].split('\n\n').map(function (p) { return '<p>' + esc(p) + '</p>'; }).join('') + '</div>' +
        '<div class="lang-ca eg-prose" style="max-width:760px">' + txt.ca[1].split('\n\n').map(function (p) { return '<p>' + esc(p) + '</p>'; }).join('') + '</div>';
    }
    var toolbar = '<div class="eg-obra-toolbar">' +
      '<input type="search" value="' + esc(obra.q) + '" placeholder="' + t(UI.search) + '" oninput="EG.obraSearch(this.value)">' +
      '<select onchange="EG.obraSort(this.value)">' +
        '<option value="count"' + (obra.sort==='count'?' selected':'') + '>' + t(UI.sortCount) + '</option>' +
        '<option value="name"' + (obra.sort==='name'?' selected':'') + '>' + t(UI.sortName) + '</option>' +
        '<option value="date"' + (obra.sort==='date'?' selected':'') + '>' + t(UI.sortDate) + '</option>' +
      '</select></div>';

    if (!obra.project) {
      main.innerHTML = header + toolbar + renderProjects(a);
    } else {
      main.innerHTML = renderProjectPhotos();
    }
  }

  // Al filtrar por década o fondo se sale de la agrupación temática: las fotos que casan
  // pueden estar en cualquier temática y obligarían a adivinar en cuál buscar.
  // `obra.ambito === null` ES el modo transversal; quitar los filtros no lo deshace
  // (se sale eligiendo una temática en el panel).
  function _syncCrossTheme() {
    if (obra.decade !== 'all' || obra.fondo !== 'all') { obra.ambito = null; obra.project = null; }
  }

  function _filterLabel() {
    return [obra.decade !== 'all' ? obra.decade + 's' : '', obra.fondo !== 'all' ? obra.fondo : '']
      .filter(Boolean).join(' · ');
  }

  // Vista transversal: todas las fotos que casan con los filtros, de cualquier temática.
  function renderFlat() {
    var q = norm(obra.q), photos = [];
    orderedAmbitos().forEach(function (k) {
      var a = obra.data.ambitos[k]; if (!a) return;
      a.projects.forEach(function (p) {
        p.photos.forEach(function (ph) {
          if (obra.decade !== 'all' && ph.decada !== obra.decade) return;
          if (obra.fondo !== 'all' && ph.fondo !== obra.fondo) return;
          if (q && norm(L(ph, 'descripcion') + ' ' + L(ph, 'lugar') + ' ' + L(p, 'nombre')).indexOf(q) === -1) return;
          photos.push(ph);
        });
      });
    });
    photos.sort(function (x, y) {                       // cronológico; sin fecha, al final
      var dx = x.decada === 'sf' ? '9999' : x.decada, dy = y.decada === 'sf' ? '9999' : y.decada;
      return dx === dy ? (x.orig || '').localeCompare(y.orig || '') : (dx < dy ? -1 : 1);
    });
    var label = _filterLabel();
    var head = '<p class="eg-kicker">' + esc(t(UI.allThemes)) + '</p>' +
      (label ? '<h2 style="font-size:1.5rem;margin:.2rem 0 .1rem">' + esc(label) + '</h2>' : '') +
      '<p class="eg-projcard__meta" style="margin-bottom:.6rem">' + photos.length + ' ' + t(UI.photos) + '</p>' +
      '<div class="eg-obra-toolbar"><input type="search" value="' + esc(obra.q) +
      '" placeholder="' + t(UI.search) + '" oninput="EG.obraSearch(this.value)"></div>';
    obra._photos = photos;                              // el visor navega sobre esta lista
    if (!photos.length) return head + '<p class="eg-empty">' + t(UI.noresults) + '</p>';
    var cells = photos.map(function (ph, i) {
      return '<div class="eg-photocell" onclick="EG.obraPhotoFlat(' + i + ')">' +
        (ph.image ? '<img loading="lazy" src="' + ph.image + '" alt="' + esc(L(ph, 'titulo')) + '">' : '') + '</div>';
    }).join('');
    return head + '<div class="eg-photogrid">' + cells + '</div>';
  }

  function renderProjects(a) {
    var q = norm(obra.q);
    var list = a.projects.filter(function (p) {
      if (!_matchDecade(p.photos)) return false;
      if (!_matchFondo(p.photos)) return false;
      if (q && norm(L(p, 'nombre') + ' ' + L(p, 'lugar')).indexOf(q) === -1) return false;
      return true;
    });
    list = list.slice().sort(function (x, y) {
      if (obra.sort === 'name') return L(x, 'nombre').localeCompare(L(y, 'nombre'));
      if (obra.sort === 'date') return (x.year || 9999) - (y.year || 9999);
      return y.count - x.count;
    });
    if (!list.length) return '<p class="eg-empty">' + t(UI.noresults) + '</p>';
    var cards = list.map(function (p) {
      var meta = [L(p, 'lugar'), p.decada !== 'sf' ? p.decada + 's' : ''].filter(Boolean).join(' · ');
      // proyecto de una sola foto → abre el visor directamente (sin página intermedia)
      var onclick = p.count === 1 ? 'EG.obraOpenSingle(\'' + p.slug + '\')' : 'EG.obraOpen(\'' + p.slug + '\')';
      return '<button class="eg-projcard" onclick="' + onclick + '">' +
        '<div class="eg-projcard__cover">' + (p.cover ? '<img loading="lazy" src="' + p.cover + '" alt="">' : '') + '</div>' +
        '<div class="eg-projcard__body">' +
          '<div class="eg-projcard__name">' + esc(L(p, 'nombre')) + '</div>' +
          (meta ? '<div class="eg-projcard__meta">' + esc(meta) + '</div>' : '') +
          '<div class="eg-projcard__count">' + p.count + ' ' + t(UI.photos) + '</div>' +
        '</div></button>';
    }).join('');
    return '<div class="eg-projgrid">' + cards + '</div>';
  }

  function _currentProject() {
    if (!obra.data) return null;
    var a = obra.data.ambitos[obra.ambito];
    return a && a.projects.filter(function (p) { return p.slug === obra.project; })[0];
  }

  function renderProjectPhotos() {
    var p = _currentProject();
    if (!p) { obra.project = null; return renderProjects(obra.data.ambitos[obra.ambito]); }
    var q = norm(obra.q);
    var photos = p.photos.filter(function (ph) {
      if (obra.decade !== 'all' && ph.decada !== obra.decade) return false;
      if (obra.fondo !== 'all' && ph.fondo !== obra.fondo) return false;
      if (q && norm(L(ph, 'descripcion') + ' ' + L(ph, 'lugar')).indexOf(q) === -1) return false;
      return true;
    });
    var themeLabel = OBRA_TEXTS[obra.ambito] ? OBRA_TEXTS[obra.ambito][getLang()][0] : obra.ambito;
    var crumbs = '<div class="eg-crumbs"><a onclick="EG.obraBack()">' + esc(themeLabel) + '</a> ▸ <span>' + esc(L(p, 'nombre')) + '</span></div>';
    var meta = [L(p, 'lugar'), p.fecha, p.count + ' ' + t(UI.photos)].filter(Boolean).join(' · ');
    var head = '<h2 style="font-size:1.5rem;margin:.2rem 0 0">' + esc(L(p, 'nombre')) + '</h2>' +
      (meta ? '<p class="eg-projcard__meta" style="margin-bottom:.5rem">' + esc(meta) + '</p>' : '') +
      '<div class="eg-obra-toolbar"><a class="eg-chip" onclick="EG.obraBack()">← ' + t(UI.backAll) + '</a>' +
      '<input type="search" value="' + esc(obra.q) + '" placeholder="' + t(UI.search) + '" oninput="EG.obraSearch(this.value)"></div>';
    if (!photos.length) return crumbs + head + '<p class="eg-empty">' + t(UI.noresults) + '</p>';
    var cells = photos.map(function (ph, i) {
      return '<div class="eg-photocell" onclick="EG.obraPhoto(\'' + p.slug + '\',' + i + ')">' +
        (ph.image ? '<img loading="lazy" src="' + ph.image + '" alt="' + esc(L(ph, 'titulo')) + '">' : '') + '</div>';
    }).join('');
    // guardamos la lista filtrada para el modal
    obra._photos = photos;
    return crumbs + head + '<div class="eg-photogrid">' + cells + '</div>';
  }

  // ── Visor de fotos (estilo Godesia: ficha lateral, flechas, zoom, compartir) ─
  var viewer = { photos: [], i: 0, ambito: '', project: '', sidebar: true };

  function VW() { return {
    L: getLang(),
    tr: function (es, ca) { return getLang() === 'ca' ? ca : es; }
  }; }

  function _vwFilename(ph) {
    var parts = [];
    if (ph.titulo) parts.push(ph.titulo);
    var ym = (ph.fecha || '').match(/\d{4}/); if (ym) parts.push(ym[0]);
    if (ph.lugar && ph.lugar !== 'por determinar') parts.push(ph.lugar);
    var base = parts.join('_').replace(/[\/\\:*?"<>|]/g, '').replace(/\s+/g, ' ').trim() || 'emili-godes';
    var ext = (ph.image || '').match(/\.[a-zA-Z0-9]+$/);
    return base + (ext ? ext[0] : '.jpg');
  }

  function egViewerOpen(photos, i, ctx) {
    viewer.photos = photos || []; viewer.i = i || 0;
    viewer.ambito = ctx && ('ambito' in ctx) ? ctx.ambito : obra.ambito;
    viewer.project = ctx && ('project' in ctx) ? ctx.project : obra.project;
    viewer.projObj = (ctx && ctx.projObj) || null;
    if (!document.getElementById('eg-viewer')) {
      var ov = document.createElement('div'); ov.id = 'eg-viewer'; document.body.appendChild(ov);
    }
    egViewerRender();
    document.body.style.overflow = 'hidden';
    document.addEventListener('keydown', egViewerKey);
  }

  function egViewerRender() {
    var v = VW(), ph = viewer.photos[viewer.i]; if (!ph) return;
    var proj = viewer.projObj || _currentProject();
    var theme = OBRA_TEXTS[viewer.ambito] ? OBRA_TEXTS[viewer.ambito][v.L][0] : '';
    var many = viewer.photos.length > 1;
    var rows = [
      [v.tr('Categoría', 'Categoria'), L(ph, 'categoria')],
      [v.tr('Fecha', 'Data'), ph.fecha + (ph.fecha_certeza && ph.fecha_certeza !== 'exacta' ? ' (' + ph.fecha_certeza + ')' : '')],
      [v.tr('Lugar', 'Lloc'), L(ph, 'lugar') && L(ph, 'lugar') !== 'por determinar' ? L(ph, 'lugar') : ''],
      [v.tr('Década', 'Dècada'), ph.decada && ph.decada !== 'sf' ? ph.decada + 's' : ''],
      [v.tr('Fondo', 'Fons'), ph.fondo],
      [v.tr('Signatura', 'Signatura'), ph.orig],
    ].filter(function (r) { return r[1]; });
    var fichaRows = rows.map(function (r) {
      return '<div style="display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-bottom:1px solid rgba(114,121,113,.15)">' +
        '<span style="color:#727971;font-size:12px">' + esc(r[0]) + '</span>' +
        '<span style="color:#1c1c17;font-size:12.5px;text-align:right">' + esc(r[1]) + '</span></div>';
    }).join('');
    var albumHtml = proj ? '<div style="margin-bottom:24px"><h3 style="font-size:11px;font-weight:700;color:#727971;text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px">' + v.tr('Álbum', 'Àlbum') + '</h3>' +
        '<button onclick="EG.egViewerToProject()" style="display:flex;align-items:center;gap:8px;font-size:13px;color:#17341e;font-weight:600;background:none;border:0;cursor:pointer;padding:0;text-align:left">' +
        '<span class="material-symbols-outlined" style="font-size:16px;color:#727971">photo_album</span>' + esc(L(proj, 'nombre')) + '</button></div>' : '';

    var desc = L(ph, 'descripcion');
    // El título del modal es el título de la obra (nombre del proyecto), no la descripción.
    var vwTitle = proj ? L(proj, 'nombre') : L(ph, 'titulo');
    var sidebar =
      (theme ? '<div style="font-size:11px;color:#727971;margin-bottom:16px">' + esc(theme) + '</div>' : '') +
      '<h2 style="font-size:20px;font-weight:700;color:#17341e;font-family:\'Noto Serif\',serif;margin:0 0 14px;line-height:1.3">' + esc(vwTitle) + '</h2>' +
      '<div style="margin-bottom:24px">' + fichaRows + '</div>' +
      (desc ? '<div style="margin-bottom:24px"><h3 style="font-size:11px;font-weight:700;color:#727971;text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px">' + v.tr('Descripción', 'Descripció') + '</h3>' +
        '<p style="font-size:13px;color:#424842;line-height:1.65;white-space:pre-line">' + esc(desc) + '</p></div>' : '') +
      albumHtml +
      (many ? '<div style="font-size:12px;color:#727971">' + (viewer.i + 1) + ' / ' + viewer.photos.length + '</div>' : '');

    function btn(onclick, title, right, svg) {
      return '<button onclick="' + onclick + '" title="' + title + '" class="eg-vw-btn" style="position:absolute;top:16px;right:' + right + 'px;z-index:50">' + svg + '</button>';
    }
    var ic = { close: '✕', dl: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="M7 11l5 5 5-5"/><path d="M4 19h16"/></svg>',
      share: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>',
      zoom: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' };

    var arrows = many ?
      '<button onclick="EG.egViewerNav(-1)" title="' + v.tr('Anterior', 'Anterior') + '" class="eg-vw-arrow" style="left:16px">‹</button>' +
      '<button onclick="EG.egViewerNav(1)" title="' + v.tr('Siguiente', 'Següent') + '" class="eg-vw-arrow" style="right:16px">›</button>' : '';

    document.getElementById('eg-viewer').innerHTML =
      '<div class="eg-vw-flex" id="eg-vw-flex">' +
        '<aside class="eg-vw-side" id="eg-vw-side">' + sidebar + '</aside>' +
        '<div class="eg-vw-area">' +
          '<button onclick="EG.egViewerSidebar()" title="' + v.tr('Panel', 'Panell') + '" class="eg-vw-btn eg-vw-toggle" style="position:absolute;top:16px;left:16px;z-index:50">' + (viewer.sidebar ? '←' : '→') + '</button>' +
          btn('EG.egViewerShare()', v.tr('Compartir', 'Comparteix'), 166, ic.share) +
          btn('EG.egViewerDownload()', v.tr('Descargar', 'Descarrega'), 116, ic.dl) +
          btn('EG.egViewerZoom()', 'Zoom', 66, ic.zoom) +
          btn('EG.egViewerClose()', v.tr('Cerrar', 'Tanca'), 16, ic.close) +
          arrows +
          '<div class="eg-vw-photo"><img id="eg-vw-img" src="' + ph.image + '" alt="' + esc(vwTitle) + '"></div>' +
        '</div>' +
      '</div>';
    document.getElementById('eg-viewer').classList.add('open');
    document.getElementById('eg-vw-side').style.display = viewer.sidebar ? '' : 'none';
  }

  function egViewerKey(e) {
    if (document.getElementById('eg-zoom')) { if (e.key === 'Escape') egZoomExit(); return; }
    if (e.key === 'Escape') egViewerClose();
    else if (e.key === 'ArrowLeft') egViewerNav(-1);
    else if (e.key === 'ArrowRight') egViewerNav(1);
  }

  // ── Zoom (x4, pan, +/-) ─────────────────────────────────────────────────────
  var _zL = 4, _pX = 0, _pY = 0, _drag = false, _dsX = 0, _dsY = 0, _psX = 0, _psY = 0;
  function _zApply() { var im = document.getElementById('eg-zoom-img'); if (im) im.style.transform = 'scale(' + _zL + ') translate(' + _pX + 'px,' + _pY + 'px)'; }
  function _zClamp() {
    var mx = (_zL - 1) / (2 * _zL) * window.innerWidth, my = (_zL - 1) / (2 * _zL) * window.innerHeight;
    _pX = Math.max(-mx, Math.min(mx, _pX)); _pY = Math.max(-my, Math.min(my, _pY));
  }
  function _zDown(e) { _drag = true; _dsX = e.clientX; _dsY = e.clientY; _psX = _pX; _psY = _pY;
    document.addEventListener('pointermove', _zMove); document.addEventListener('pointerup', _zUp); e.preventDefault(); }
  function _zMove(e) { if (!_drag) return; _pX = _psX + (e.clientX - _dsX) / _zL; _pY = _psY + (e.clientY - _dsY) / _zL; _zClamp(); _zApply(); }
  function _zUp() { _drag = false; document.removeEventListener('pointermove', _zMove); document.removeEventListener('pointerup', _zUp); }
  function _zStep(d) { _zL = Math.max(1, Math.min(10, _zL + d)); var l = document.getElementById('eg-zoom-lbl'); if (l) l.textContent = _zL + '×'; _pX = 0; _pY = 0; _zApply(); }
  function egZoomEnter() {
    var ph = viewer.photos[viewer.i]; if (!ph || document.getElementById('eg-zoom')) return;
    _zL = 4; _pX = 0; _pY = 0;
    var ov = document.createElement('div'); ov.id = 'eg-zoom';
    ov.innerHTML = '<img id="eg-zoom-img" src="' + ph.image + '">' +
      '<button id="eg-zoom-x" title="Esc">✕</button>' +
      '<div id="eg-zoom-ctrls"><button data-z="-1">−</button><span id="eg-zoom-lbl">4×</span><button data-z="1">+</button></div>';
    document.body.appendChild(ov);
    ov.querySelector('#eg-zoom-x').onclick = egZoomExit;
    ov.querySelectorAll('[data-z]').forEach(function (b) { b.onclick = function () { _zStep(parseInt(b.dataset.z, 10)); }; });
    ov.addEventListener('pointerdown', _zDown);
  }
  function egZoomExit() { var ov = document.getElementById('eg-zoom'); if (!ov) return;
    document.removeEventListener('pointermove', _zMove); document.removeEventListener('pointerup', _zUp); _drag = false; ov.remove(); }

  function egToast(msg) {
    var t = document.createElement('div'); t.className = 'eg-toast'; t.textContent = msg;
    document.body.appendChild(t); requestAnimationFrame(function () { t.style.opacity = '1'; });
    setTimeout(function () { t.style.opacity = '0'; setTimeout(function () { t.remove(); }, 250); }, 2200);
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  window.EG = {
    lang: getLang(), setLang: setLang, openLightbox: openLightbox, t: t,
    obraTheme: function (k) { obra.ambito = k; obra.project = null; obra.q = ''; renderObra(); window.scrollTo({top:0,behavior:'smooth'}); },
    obraAllThemes: function () { obra.ambito = null; obra.project = null; obra.q = ''; renderObra(); window.scrollTo({top:0,behavior:'smooth'}); },
    obraDecade: function (d) { obra.decade = d; _syncCrossTheme(); renderObra(); },
    obraFondo: function (i) { obra.fondo = (i < 0) ? 'all' : (obra.data.fondos[i] || 'all'); _syncCrossTheme(); renderObra(); },
    obraSearch: function (v) { obra.q = v; renderMain(); },
    obraSort: function (v) { obra.sort = v; renderMain(); },
    obraOpen: function (slug) { obra.project = slug; renderObra(); window.scrollTo({top:0,behavior:'smooth'}); },
    obraOpenSingle: function (slug) {
      var a = obra.data.ambitos[obra.ambito];
      var p = a && a.projects.filter(function (x) { return x.slug === slug; })[0];
      if (!p || !p.photos.length) return;
      egViewerOpen(p.photos, 0, { ambito: obra.ambito, project: slug, projObj: p });
    },
    obraBack: function () { obra.project = null; renderObra(); },
    obraPhoto: function (slug, i) { if (obra._photos && obra._photos[i] != null) egViewerOpen(obra._photos, i); },
    // En transversal no hay proyecto ni temática únicos: la ficha del visor sale de la propia foto.
    obraPhotoFlat: function (i) {
      if (!obra._photos || obra._photos[i] == null) return;
      egViewerOpen(obra._photos, i, { ambito: '', project: null, projObj: null });
    },
    destacadaOpen: function (i) {
      var items = window.__destacadas || []; if (items[i] == null) return;
      egViewerOpen(items, i, { ambito: items[i].ambito || '', project: null, projObj: null });
    },
    egViewerNav: function (d) { var n = viewer.photos.length; if (!n) return; viewer.i = (viewer.i + d + n) % n; egViewerRender(); },
    egViewerClose: function () { egZoomExit(); document.removeEventListener('keydown', egViewerKey); var el = document.getElementById('eg-viewer'); if (el) { el.classList.remove('open'); el.innerHTML = ''; } document.body.style.overflow = ''; },
    egViewerSidebar: function () { viewer.sidebar = !viewer.sidebar; egViewerRender(); },
    egViewerZoom: function () { egZoomEnter(); },
    egViewerToProject: function () { this.egViewerClose(); },
    egViewerDownload: function () {
      var ph = viewer.photos[viewer.i]; if (!ph || !ph.image) return;
      fetch(ph.image).then(function (r) { return r.blob(); }).then(function (b) {
        var u = URL.createObjectURL(b), a = document.createElement('a');
        a.href = u; a.download = _vwFilename(ph); document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(u);
      }).catch(function () { egToast(getLang() === 'ca' ? 'No s’ha pogut descarregar' : 'No se pudo descargar'); });
    },
    egViewerShare: function () {
      var ph = viewer.photos[viewer.i]; if (!ph) return;
      var url = location.origin + ph.image, title = ph.titulo || 'Emili Godes';
      if (navigator.share) {
        var data = { title: title, text: title, url: url };
        if (navigator.canShare) {
          fetch(ph.image).then(function (r) { return r.blob(); }).then(function (b) {
            var f = new File([b], _vwFilename(ph), { type: b.type || 'image/jpeg' });
            if (navigator.canShare({ files: [f] })) data = { files: [f], title: title };
            navigator.share(data).catch(function () {});
          }).catch(function () { navigator.share(data).catch(function () {}); });
        } else { navigator.share(data).catch(function () {}); }
        return;
      }
      navigator.clipboard && navigator.clipboard.writeText(url).then(function () {
        egToast(getLang() === 'ca' ? 'Enllaç copiat' : 'Enlace copiado');
      }).catch(function () { prompt('URL:', url); });
    },
  };
  function init() {
    buildHeader();
    buildFooter();
    // Selector de idioma por delegación (cubre pie y drawer, creados en distinto momento)
    document.addEventListener('click', function (e) {
      var btn = e.target.closest && e.target.closest('.eg-lang button');
      if (btn) setLang(btn.dataset.lang);
    });
    applyLang(getLang());
    loadObra();
    loadDestacadas();
    initDecadeFilter();
    initObra();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
