"""La BD principal vive en el volumen persistente de Railway, no en el repo.

Problema que resuelve: Railway reconstruye /app desde el repo en cada deploy, así
que `data/godesia.db` volvía a la copia commiteada y se perdía todo lo hecho en
producción (importaciones GEDCOM desde el admin, fotos de Palazuelos descargadas,
duplicados de fotos, geocoder…). Para publicar código había que elegir entre no
publicar o perder datos.

Solución: en Railway la BD de verdad es `data/photos/_db/godesia.db` (el volumen,
`/photos/_*` → 403) y `data/godesia.db` pasa a ser un enlace simbólico hacia ella.
Así las ~40 rutas que abren `data/godesia.db` (app, admin, sync_catalog, scripts…)
siguen funcionando sin tocarlas, y SQLite deja el -wal/-shm junto al fichero real
(en el volumen). La copia del repo solo se usa UNA vez, para sembrar el volumen si
aún está vacío; a partir de ahí un deploy ya no toca los datos.

En local (sin variables RAILWAY_*) no hace nada: data/godesia.db es un fichero
normal, la copia de trabajo de desarrollo. Los datos buenos son los de producción.
"""

import os
import sqlite3
from pathlib import Path

_RAILWAY_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_PROJECT_ID", "RAILWAY_SERVICE_ID")


def on_railway() -> bool:
    return any(os.environ.get(v) for v in _RAILWAY_VARS)


def ensure_volume_db(base_dir: Path) -> str:
    """Deja data/godesia.db apuntando a la BD del volumen. Devuelve qué ha hecho."""
    if os.environ.get("GODESIA_DB_ON_VOLUME", "1" if on_railway() else "0") != "1":
        return "local: data/godesia.db del disco"

    repo_db = base_dir / "data" / "godesia.db"
    vol_db = base_dir / "data" / "photos" / "_db" / "godesia.db"
    vol_db.parent.mkdir(parents=True, exist_ok=True)

    msg = "volumen: BD existente"
    if not vol_db.exists():
        if repo_db.is_symlink() or not repo_db.exists():
            raise RuntimeError(f"No hay BD que sembrar en el volumen ({repo_db})")
        # backup API: copia consistente aunque la copia del repo tenga WAL.
        tmp = vol_db.with_suffix(".db.seed")
        src, dst = sqlite3.connect(str(repo_db)), sqlite3.connect(str(tmp))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        tmp.replace(vol_db)
        msg = "volumen: BD sembrada desde la copia del repo (primer arranque)"

    if not (repo_db.is_symlink() and repo_db.resolve() == vol_db.resolve()):
        for suffix in ("", "-wal", "-shm"):
            p = repo_db.with_name(repo_db.name + suffix)
            if p.exists() or p.is_symlink():
                p.unlink()
        repo_db.symlink_to(vol_db)
    return f"{msg} → {vol_db}"
