#!/usr/bin/env python3
"""
download_fs_records.py — Descarga las imágenes de las páginas del registre
d'enterraments enlazadas en niche_records.fs_url (FamilySearch) y las registra
como fotos de registro del nicho (niche_photos, kind='record').

AVISO: FamilySearch exige sesión para ver estas imágenes y sus condiciones de
uso prohíben el acceso automatizado. Este script usa TU sesión de navegador
(no automatiza el login), descarga solo las ~100 páginas enlazadas en el Excel
familiar, a ritmo lento (3s/petición) y se detiene ante errores de acceso.
El riesgo sobre la cuenta es del usuario.

Cómo obtener la cookie de sesión:
  1. Inicia sesión en https://www.familysearch.org en tu navegador.
  2. Abre las herramientas de desarrollador (F12) → pestaña Application/Almacenamiento
     → Cookies → www.familysearch.org → copia el valor de `fssessionid`.
  3. Ejecuta:  python3 scripts/download_fs_records.py --cookie 'VALOR_DE_FSSESSIONID'
     (o expórtala:  export FS_SESSION='VALOR' )

Opciones:
  --limit N    descarga como máximo N imágenes (prueba primero con --limit 1)
  --list       solo lista lo que descargaría, sin tocar la red
"""

import argparse
import io
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

from database import get_connection  # noqa: E402

DB_PATH = BASE_DIR / "data" / "godesia.db"
DEST_DIR = BASE_DIR / "data" / "cemetery_photos"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def ark_id(url):
    m = re.search(r"(3:1:[A-Z0-9-]+)", url or "")
    return m.group(1) if m else None


def candidate_endpoints(ark):
    return [
        f"https://www.familysearch.org/das/v2/{ark}/dist.jpg",
        f"https://sg30p0.familysearch.org/service/records/storage/deepzoomcloud/dz/v1/{ark}/$dist.jpg",
        f"https://www.familysearch.org/service/records/storage/dascloud/das/v2/{ark}/dist.jpg",
    ]


def fetch(url, session, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Cookie": f"fssessionid={session}",
        "Authorization": f"Bearer {session}",
        "Referer": referer,
        "Accept": "image/jpeg,image/*,*/*",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.headers.get("Content-Type", ""), resp.read()


def download_image(ark, fs_url, session):
    """Prueba los endpoints conocidos. Devuelve bytes JPEG o lanza PermissionError/IOError."""
    last_err = None
    for endpoint in candidate_endpoints(ark):
        try:
            status, ctype, data = fetch(endpoint, session, fs_url)
            if status == 200 and "image" in ctype and len(data) > 10_000:
                return data
            last_err = IOError(f"{endpoint} → {status} {ctype} {len(data)}b")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                last_err = PermissionError(f"{endpoint} → {e.code}")
            else:
                last_err = IOError(f"{endpoint} → {e.code}")
        except Exception as e:
            last_err = IOError(f"{endpoint} → {e}")
    raise last_err or IOError("sin endpoints")


def optimize(data):
    """Reescala a máx 1800px y comprime (q85). Si PIL falla, devuelve el original."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if max(img.size) > 1800:
            img.thumbnail((1800, 1800))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, "JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cookie", default=os.environ.get("FS_SESSION", ""),
                    help="valor de la cookie fssessionid (o env FS_SESSION)")
    ap.add_argument("--limit", type=int, default=0, help="máximo de imágenes a descargar")
    ap.add_argument("--list", action="store_true", help="solo listar, sin descargar")
    args = ap.parse_args()

    conn = get_connection(str(DB_PATH))
    rows = conn.execute("""
        SELECT nr.niche_id, nr.fs_url, MIN(nr.name) AS name, n.name AS niche_name
        FROM niche_records nr JOIN niches n ON n.id = nr.niche_id
        WHERE nr.fs_url IS NOT NULL AND nr.fs_url != ''
        GROUP BY nr.niche_id, nr.fs_url
        ORDER BY nr.niche_id
    """).fetchall()

    # Pendientes: sin foto ya registrada para ese ark en ese nicho
    pending = []
    for r in rows:
        ark = ark_id(r["fs_url"])
        if not ark:
            continue
        filename = f"fsrec_{ark.replace(':', '_')}.jpg"
        exists = conn.execute(
            "SELECT 1 FROM niche_photos WHERE niche_id = ? AND filename = ?",
            (r["niche_id"], filename)).fetchone()
        if not exists:
            pending.append((r["niche_id"], r["niche_name"], r["name"], r["fs_url"], ark, filename))

    print(f"Páginas de registro enlazadas (únicas por nicho): {len(rows)}")
    print(f"Pendientes de descargar: {len(pending)}")
    if args.list or not pending:
        for niche_id, niche_name, name, _, ark, _ in pending[:50]:
            print(f"  nicho {niche_id} ({niche_name[:40]}) — {name[:30]} — {ark}")
        return

    if not args.cookie:
        print("\nFalta la cookie de sesión. Inicia sesión en familysearch.org y pasa")
        print("el valor de `fssessionid` con --cookie o la variable FS_SESSION.")
        print("(ver instrucciones completas con --help)")
        sys.exit(1)

    DEST_DIR.mkdir(exist_ok=True)
    if args.limit:
        pending = pending[:args.limit]

    ok, failed, denied = 0, 0, 0
    for i, (niche_id, niche_name, name, fs_url, ark, filename) in enumerate(pending):
        if i:
            time.sleep(3)
        try:
            data = download_image(ark, fs_url, args.cookie.strip())
        except PermissionError as e:
            denied += 1
            print(f"✗ acceso denegado: {name[:30]} ({e})")
            if denied >= 3:
                print("Tres denegaciones seguidas: sesión caducada o acceso bloqueado. Paro aquí.")
                break
            failed += 1
            continue
        except Exception as e:
            failed += 1
            print(f"✗ error: {name[:30]} ({e})")
            continue
        denied = 0
        (DEST_DIR / filename).write_bytes(optimize(data))
        conn.execute("INSERT INTO niche_photos (niche_id, filename, kind) VALUES (?, ?, 'record')",
                     (niche_id, filename))
        conn.commit()
        ok += 1
        print(f"✓ {ok}/{len(pending)} nicho {niche_id} — {name[:34]} → {filename}")

    print(f"\nDescargadas: {ok} | fallidas: {failed} | quedan: {len(pending) - ok - failed}")
    if ok:
        print("Las imágenes ya aparecen como 'Registro' en el panel del nicho y el gestor.")


if __name__ == "__main__":
    main()
