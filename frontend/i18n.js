/**
 * i18n.js — runtime de internacionalización de Godesia
 *
 * No hace falta incluirlo en el HTML: el backend lo inyecta en el <head> de
 * cada página pública junto con los datos:
 *   window.__I18N_LANG__   idioma servido ("es", "ca", ...)
 *   window.__I18N__        diccionario de UI (frontend/locales/ui.{lang}.json)
 *   window.__I18N_LANGS__  idiomas activos [{code,label}]
 *   window.__I18N_CONTENT__ contenido de saga por idioma (solo lang != es)
 *
 * El español es el idioma base: los textos del HTML ya están en español y
 * actúan de fallback cuando falta una clave.
 */
(function () {
  'use strict';

  function lang() { return window.__I18N_LANG__ || 'es'; }
  function dict() { return window.__I18N__ || {}; }
  function langs() { return window.__I18N_LANGS__ || [{ code: 'es', label: 'Español' }]; }

  function lookup(key) {
    let node = dict();
    const parts = String(key).split('.');
    for (let i = 0; i < parts.length; i++) {
      if (node == null || typeof node !== 'object') return undefined;
      node = node[parts[i]];
    }
    return (typeof node === 'string' || Array.isArray(node)) ? node : undefined;
  }

  /**
   * t('pages.chat.send') → traducción con placeholders {name}.
   * fallback: texto a usar si falta la clave (si se omite, la propia clave).
   */
  function t(key, params, fallback) {
    let str = lookup(key);
    if (str === undefined) {
      if (lang() !== 'es') console.warn('[i18n] falta clave:', key);
      str = (fallback !== undefined) ? fallback : key;
    }
    if (Array.isArray(str)) return str;
    if (params) {
      str = str.replace(/\{(\w+)\}/g, function (m, k) {
        return params[k] !== undefined ? params[k] : m;
      });
    }
    return str;
  }

  /** Antepone /{lang} a rutas de página raíz: '/x.html?a=1', '/'. Deja assets y URLs externas. */
  function i18nHref(path) {
    if (!path) return path;
    if (path === '/') return '/' + lang() + '/';
    if (/^\/[^/]+\.html([?#].*)?$/.test(path)) return '/' + lang() + path;
    return path;
  }

  /** Reescribe los <a href> de un fragmento insertado con innerHTML. */
  function localizeLinks(root) {
    if (!root) return;
    root.querySelectorAll('a[href]').forEach(function (a) {
      const href = a.getAttribute('href');
      const localized = i18nHref(href);
      if (localized !== href) a.setAttribute('href', localized);
    });
  }

  /** Añade lang= a una URL de la API. */
  function apiUrl(path) {
    return path + (path.indexOf('?') >= 0 ? '&' : '?') + 'lang=' + lang();
  }

  const ATTR_MAP = {
    'data-i18n-placeholder': 'placeholder',
    'data-i18n-title': 'title',
    'data-i18n-aria-label': 'aria-label',
    'data-i18n-alt': 'alt'
  };

  /** Aplica data-i18n / data-i18n-html / data-i18n-<attr> bajo root. */
  function applyTranslations(root) {
    root = root || document;
    root.querySelectorAll('[data-i18n]').forEach(function (el) {
      const v = lookup(el.getAttribute('data-i18n'));
      if (v !== undefined) el.textContent = v;
    });
    root.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      const v = lookup(el.getAttribute('data-i18n-html'));
      if (v !== undefined) { el.innerHTML = v; localizeLinks(el); }
    });
    Object.keys(ATTR_MAP).forEach(function (dataAttr) {
      root.querySelectorAll('[' + dataAttr + ']').forEach(function (el) {
        const v = lookup(el.getAttribute(dataAttr));
        if (v !== undefined) el.setAttribute(ATTR_MAP[dataAttr], v);
      });
    });
  }

  /** Sustituye la prosa de las sagas desde __I18N_CONTENT__ ([data-content]). */
  function applyContent(root) {
    const content = window.__I18N_CONTENT__;
    if (!content) return;
    (root || document).querySelectorAll('[data-content]').forEach(function (el) {
      const v = content[el.getAttribute('data-content')];
      if (v === undefined) return;
      if (Array.isArray(v)) {
        // En listas (p.ej. la cronología de las sagas) los ítems traducidos vienen
        // sin <li> (solo su contenido); hay que envolverlos o el <ul> queda roto.
        const isList = el.tagName === 'UL' || el.tagName === 'OL';
        el.innerHTML = isList
          ? v.map(function (x) { return /^\s*<li/i.test(x) ? x : '<li>' + x + '</li>'; }).join('')
          : v.join('\n');
      } else {
        el.innerHTML = v;
      }
      localizeLinks(el);
    });
  }

  /** Cambia de idioma: persiste cookie y navega a la misma página con otro prefijo. */
  function setLang(code) {
    document.cookie = 'godesia_lang=' + code + ';path=/;max-age=31536000;SameSite=Lax';
    const codes = langs().map(function (l) { return l.code; }).join('|');
    const re = new RegExp('^/(' + codes + ')(/|$)');
    let path = window.location.pathname;
    if (re.test(path)) {
      path = path.replace(re, '/' + code + '/');
    } else {
      path = '/' + code + path;
    }
    window.location.href = path + window.location.search + window.location.hash;
  }

  function ready() {
    applyTranslations(document);
    applyContent(document);
    document.documentElement.classList.remove('i18n-pending');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else {
    ready();
  }

  window.t = t;
  window.I18N = {
    t: t,
    lang: lang,
    langs: langs,
    href: i18nHref,
    localizeLinks: localizeLinks,
    apiUrl: apiUrl,
    apply: applyTranslations,
    applyContent: applyContent,
    setLang: setLang
  };
}());
