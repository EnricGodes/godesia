"""Subida automática de fotos al volumen de Railway.

Cuando el admin corre en LOCAL, las fotos (Palazuelos, nichos) se guardan en el
disco local. Para que estén en producción hay que empujarlas al volumen de Railway
(`data/photos/`) vía el endpoint /api/admin/upload-photos. Esto lo hace
automáticamente, en segundo plano y best-effort, tras descargar/subir una foto.

En Railway no hace nada: allí ya se escribe directamente en el volumen.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

# URL del despliegue de Railway (se puede sobreescribir por entorno).
RAILWAY_BASE = os.environ.get("RAILWAY_SYNC_URL", "https://godesia.up.railway.app")
_UPLOAD_ENDPOINT = f"{RAILWAY_BASE}/api/admin/upload-photos"


def on_railway() -> bool:
    """True si el proceso corre dentro de Railway (no hay que sincronizar nada)."""
    return any(os.environ.get(k) for k in
               ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID"))


def push_photos_to_railway(photos_dir, filenames) -> None:
    """En LOCAL, sube en segundo plano las fotos indicadas al volumen de Railway.
    En Railway no hace nada. Nunca lanza excepción (best-effort)."""
    if on_railway():
        return
    names = [f for f in dict.fromkeys(filenames) if f]
    if not names:
        return
    photos_dir = Path(photos_dir)

    def _do():
        try:
            import requests  # solo se necesita/instala en local
        except Exception:
            return
        files = []
        for fn in names:
            p = photos_dir / fn
            if p.exists():
                files.append(("files", (fn, p.read_bytes(), "image/jpeg")))
        if not files:
            return
        try:
            requests.post(_UPLOAD_ENDPOINT, files=files, timeout=120)
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True).start()
