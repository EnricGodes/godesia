/**
 * footer.js — pie de página global de Godesia
 *
 * Lo inyecta el backend en todas las páginas públicas (con defer). Sustituye
 * el <footer> existente de la página por la versión canónica traducible con
 * el selector de idioma; si la página no tiene <footer> (chat, árbol), no
 * hace nada. Requiere i18n.js (window.t / window.I18N).
 */
(function () {
  'use strict';

  const TEAM = [
    'Emili Godes i Faura',
    'Enric Godes Maté',
    'Ignasi Palazuelos Salvadó',
    'Oriol Mestre Campi',
    'Maria Rosa Godes Diago (+)',
    'Jesús Mestre Godes (+)',
    'Montserrat Godes Diago (+)',
    'Enric Cabestany Carreras (+)',
  ];

  function h4(text) {
    return '<h4 style="font-size:0.65rem;text-transform:uppercase;letter-spacing:0.2em;' +
      'font-weight:700;opacity:0.5;margin:0 0 0.75rem;">' + text + '</h4>';
  }

  function link(href, label) {
    return '<li><a href="' + I18N.href(href) + '" style="color:rgba(255,255,255,0.7);' +
      'text-decoration:none;">' + label + '</a></li>';
  }

  function languageSelector() {
    const current = I18N.lang();
    const items = I18N.langs().map(function (l) {
      if (l.code === current) {
        return '<li style="opacity:1;font-weight:700;">' + l.label + '</li>';
      }
      return '<li><a href="#" data-set-lang="' + l.code + '" style="color:rgba(255,255,255,0.7);' +
        'text-decoration:none;">' + l.label + '</a></li>';
    }).join('');
    return h4(t('footer.language', null, 'Idioma')) +
      '<ul style="list-style:none;padding:0;margin:0;font-size:0.85rem;line-height:2;">' + items + '</ul>';
  }

  function render(offset) {
    const ulStyle = 'list-style:none;padding:0;margin:0;font-size:0.85rem;line-height:2;';
    return (
      '<footer id="godesia-footer"' + (offset ? ' class="lg:ml-[260px]"' : '') +
      ' style="background:#2D4B33;color:#fff;margin-top:4rem;padding:3rem 2rem 2rem;">' +
        '<div style="max-width:1200px;margin:0 auto;display:grid;' +
        'grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:2rem;">' +
          '<div>' +
            '<h3 style="font-family:\'Noto Serif\',serif;font-size:1.1rem;font-weight:700;margin:0 0 0.75rem;">Godesia</h3>' +
            '<p style="font-size:0.85rem;opacity:0.7;line-height:1.6;margin:0;">' +
              t('footer.tagline', null, 'Archivo genealógico digital de la familia Godes. Preservando la memoria familiar para las generaciones futuras.') +
            '</p>' +
          '</div>' +
          '<div>' +
            h4(t('footer.nav_title', null, 'Navegación')) +
            '<ul style="' + ulStyle + '">' +
              link('/', t('footer.nav_home', null, 'Inicio')) +
              link('/arbol2.html', t('footer.nav_tree', null, 'Árbol')) +
              link('/chat.html', t('footer.nav_chat', null, 'Consultas')) +
            '</ul>' +
          '</div>' +
          '<div>' +
            h4(t('footer.project_title', null, 'Proyecto')) +
            '<ul style="' + ulStyle + '">' +
              link('/colaborar.html', t('footer.nav_collaborate', null, 'Colaborar')) +
            '</ul>' +
          '</div>' +
          '<div>' +
            h4(t('footer.team_title', null, 'Equipo de investigación')) +
            '<ul style="' + ulStyle + 'line-height:1.75;">' +
              TEAM.map(function (n) { return '<li style="opacity:0.7;">' + n + '</li>'; }).join('') +
            '</ul>' +
          '</div>' +
          '<div>' + languageSelector() + '</div>' +
        '</div>' +
        '<div style="border-top:1px solid rgba(255,255,255,0.15);margin-top:2rem;' +
        'padding-top:1.5rem;text-align:center;font-size:0.75rem;opacity:0.4;">' +
          '<em>' + t('footer.credits', null, 'Experiencia creada por Enric Godes') + '</em>' +
        '</div>' +
      '</footer>'
    );
  }

  function init() {
    if (typeof window.I18N === 'undefined') return;
    const existing = document.querySelector('footer');
    if (!existing) return;
    const offset = !!document.querySelector('.dash-sidebar') ||
      /lg:ml-\[260px\]/.test(existing.className || '');
    const wrapper = document.createElement('div');
    wrapper.innerHTML = render(offset);
    const footer = wrapper.firstChild;
    existing.replaceWith(footer);
    footer.querySelectorAll('[data-set-lang]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        I18N.setLang(a.getAttribute('data-set-lang'));
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
}());
