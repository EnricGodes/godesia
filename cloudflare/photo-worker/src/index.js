/**
 * godes-photos — Worker de Cloudflare delante de las fotos de godes.org.
 *
 * Las fotos son privadas (hace falta sesión de un usuario aprobado), así que no
 * se pueden cachear con una regla normal de Cloudflare: la caché no mira quién
 * pide. Este Worker hace las dos cosas:
 *   1. Comprueba la sesión (cookie godesia_session) contra /api/auth/me del
 *      servidor y recuerda el resultado 10 minutos por sesión.
 *   2. Sirve la foto desde la caché de Cloudflare (Cache API, solo accesible
 *      desde este Worker) y solo la pide a Railway la primera vez.
 * Los nombres de fichero llevan hash (MyHeritage), por eso la foto puede quedar
 * en caché un año: si cambia, cambia el nombre.
 *
 * Rutas: godes.org/photos/*, /thumbs/*, /cemetery_photos/* (y www.).
 * Configurar las rutas en modo «fail open»: si se pasa del límite gratuito,
 * las peticiones van directas a Railway, que también comprueba la sesión.
 */

const SESSION_COOKIE = 'godesia_session';
const SESSION_TTL = 600;            // s que se recuerda una sesión válida
const PHOTO_TTL = 31536000;         // s en la caché de Cloudflare (1 año)
const BROWSER_CC = 'private, max-age=2592000, immutable';

function getCookie(request, name) {
  const header = request.headers.get('Cookie') || '';
  for (const part of header.split(';')) {
    const [k, ...v] = part.trim().split('=');
    if (k === name) return v.join('=');
  }
  return null;
}

async function sha256(text) {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
}

function unauthorized() {
  return new Response(JSON.stringify({ error: 'unauthorized' }), {
    status: 401, headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

/** true = sesión válida, false = inválida, null = no se pudo comprobar */
async function sessionValid(request, token, cache, ctx) {
  const url = new URL(request.url);
  const key = new Request(`${url.origin}/__godes_session/${await sha256(token)}`);
  if (await cache.match(key)) return true;
  const me = await fetch(`${url.origin}/api/auth/me`, {
    headers: { Cookie: `${SESSION_COOKIE}=${token}`, Accept: 'application/json' },
  });
  if (me.status === 200) {
    ctx.waitUntil(cache.put(key, new Response('1', {
      headers: { 'Cache-Control': `public, max-age=${SESSION_TTL}` },
    })));
    return true;
  }
  if (me.status === 401 || me.status === 403) return false;
  return null;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Nunca tocar lo que no sea una lectura de foto, ni las carpetas internas
    // del volumen (/photos/_auth, _db, _contrib…): el servidor responde 403.
    if (request.method !== 'GET' || url.pathname.split('/').some(seg => seg.startsWith('_'))) {
      return fetch(request);
    }

    const token = getCookie(request, SESSION_COOKIE);
    if (!token) return unauthorized();

    const cache = caches.default;
    const valid = await sessionValid(request, token, cache, ctx);
    if (valid === false) return unauthorized();
    if (valid === null) return fetch(request);   // servidor con problemas: que decida él

    // Clave de caché sin cookies ni query: la misma foto para todos los usuarios
    const cacheKey = new Request(`${url.origin}${url.pathname}`, { method: 'GET' });
    let resp = await cache.match(cacheKey);
    if (resp) {
      resp = new Response(resp.body, resp);
      resp.headers.set('Cache-Control', BROWSER_CC);
      resp.headers.set('x-godes-cache', 'HIT');
      return resp;
    }

    const origin = await fetch(request);
    const type = origin.headers.get('Content-Type') || '';
    if (origin.status !== 200 || !(type.startsWith('image/') || type === 'application/pdf')) {
      return origin;   // 302 de PDF, 404, 401… tal cual, sin cachear
    }
    const toCache = new Response(origin.clone().body, origin);
    toCache.headers.set('Cache-Control', `public, max-age=${PHOTO_TTL}`);
    toCache.headers.delete('Set-Cookie');
    ctx.waitUntil(cache.put(cacheKey, toCache));

    resp = new Response(origin.body, origin);
    resp.headers.set('Cache-Control', BROWSER_CC);
    resp.headers.set('x-godes-cache', 'MISS');
    return resp;
  },
};
