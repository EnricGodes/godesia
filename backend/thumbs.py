"""Miniaturas de las fotos y cabeceras de caché.

Las páginas mostraban los originales (media ~400 KB, algunos de varios MB) incluso
para avatares de 40 px. `/thumbs/{w}/{fichero}` sirve una versión reducida que se
genera la primera vez y queda guardada en el volumen (`PHOTOS_DIR/_thumbs/{w}/`,
que `/photos/_*` nunca deja descargar). Pide sesión como cualquier otra ruta
(auth_middleware): no hay nada público aquí.

Los nombres de fichero de MyHeritage llevan hash (girar o recortar una foto le da
otro nombre), así que el navegador puede guardarlas un mes sin volver a pedirlas:
`Cache-Control: private` (no la guarda ningún proxy compartido, solo el navegador
del usuario y el Worker de Cloudflare, que comprueba la sesión antes).
"""

import io
import threading
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

PHOTO_CACHE_CONTROL = "private, max-age=2592000, immutable"   # 30 días
WIDTHS = (160, 480, 1200)
_IMAGE_EXT = (".jpg", ".jpeg", ".png")
_locks: dict = {}
_locks_guard = threading.Lock()


class CachedStaticFiles(StaticFiles):
    """StaticFiles que deja guardar las fotos en el navegador (ver docstring)."""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        if resp.status_code == 200:
            resp.headers["Cache-Control"] = PHOTO_CACHE_CONTROL
        return resp


_size_cache: dict = {}


def original_size(path: Path):
    """(ancho, alto) del original tal como lo muestra el navegador (con el giro
    EXIF aplicado). Solo lee la cabecera del fichero; se guarda en memoria.
    Lo usan los recuadros de cara, cuyas coordenadas son píxeles del original."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_mtime)
    if key not in _size_cache:
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
                if (img.getexif() or {}).get(0x0112) in (5, 6, 7, 8):   # girada 90°/270°
                    w, h = h, w
            _size_cache[key] = (w, h)
        except Exception:
            _size_cache[key] = None
    return _size_cache[key]


def _lock_for(key):
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _make_thumb(src: Path, dst: Path, w: int):
    from PIL import Image, ImageOps
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        img.thumbnail((w, w * 4))          # limita el ancho; las fotos muy altas no se deforman
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(buf.getvalue())
    tmp.replace(dst)


def register(app, photos_dir: Path):
    thumbs_dir = photos_dir / "_thumbs"

    @app.get("/thumbs/{w}/{filename}")
    async def thumb(w: int, filename: str):
        if w not in WIDTHS or "/" in filename or "\\" in filename or filename.startswith((".", "_")):
            raise HTTPException(404)
        src = photos_dir / filename
        if not src.is_file():
            raise HTTPException(404)
        if not filename.lower().endswith(_IMAGE_EXT):
            # PDF u otro formato: no hay miniatura, se sirve el original
            return RedirectResponse(f"/photos/{filename}", status_code=302)
        dst = thumbs_dir / str(w) / (filename if filename.lower().endswith((".jpg", ".jpeg")) else filename + ".jpg")
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            from starlette.concurrency import run_in_threadpool
            lock = _lock_for(str(dst))

            def build():
                with lock:
                    if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                        _make_thumb(src, dst, w)
            try:
                await run_in_threadpool(build)
            except Exception:
                # Imagen ilegible para Pillow: mejor el original que un hueco
                return RedirectResponse(f"/photos/{filename}", status_code=302)
        return FileResponse(dst, media_type="image/jpeg",
                            headers={"Cache-Control": PHOTO_CACHE_CONTROL})
