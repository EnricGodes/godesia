#!/usr/bin/env python3
"""200 preguntas sobre PARENTESCOS RAROS (nomenclatura es.wikipedia):
concuñados, medios-hermanos, tíos-abuelos, tíos-bisabuelos, dobles-primos,
sobrinos-nietos/segundos, primos segundos/terceros, tíos/primos políticos, etc.
Ancladas en personas reales. FAIL = el router no entiende ("No he sabido…").
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE / "backend"))
import database  # noqa: E402
from query_router import QueryRouter  # noqa: E402

R = [
    "Emili Godes Hurtado", "Artur Godes Caballeria", "Ernest Godes Hurtado",
    "Rosa Godes Hurtado", "Mercè Godes Caballeria", "Pau Godes Caballeria",
    "Dolors Godes Caballeria", "Pasqual Godes Gomis", "Pasqual Godes Segura",
    "Francesc Godes Martí", "Jesus Godes Diago", "Maria Rosa Godes Diago",
    "Ramona Godes Caballeria", "Josep Godes Caballeria", "Emilia Hurtado Giró",
    "Rosa Caballeria Madiroles", "Antònia Diago Almuzara", "Ramón Godes Hurtado",
    "Josep Maria Godes Hurtado", "Nicómedes Diago Marín",
]

# (plantilla con {n}, nº de variantes de persona a emitir)
TEMPLATES = [
    # --- concuñados (esposo/a del hermano/a del cónyuge) ---
    ("¿Quiénes eran los concuñados de {n}?", 4),
    ("¿Tenía {n} concuñados documentados?", 3),
    ("¿Quién fue la concuñada de {n}?", 3),
    ("Dime los concuñados de {n}.", 2),
    # --- medios hermanos (comparten un solo progenitor) ---
    ("¿Quiénes eran los medios hermanos de {n}?", 4),
    ("¿Tenía {n} algún medio hermano?", 3),
    ("¿Quién era la media hermana de {n}?", 3),
    ("¿Tuvo {n} hermanastros?", 2),
    ("¿Quiénes fueron los hermanastros de {n}?", 2),
    # --- tíos abuelos (hermano del abuelo) ---
    ("¿Quiénes eran los tíos abuelos de {n}?", 4),
    ("¿Quién fue el tío abuelo de {n}?", 2),
    ("¿Tenía {n} alguna tía abuela?", 2),
    # --- tíos bisabuelos (hermano del bisabuelo) ---
    ("¿Quiénes eran los tíos bisabuelos de {n}?", 4),
    ("¿Quién fue el tío bisabuelo de {n}?", 2),
    ("¿Tenía {n} tías bisabuelas?", 2),
    # --- dobles primos (primos por las dos ramas) ---
    ("¿Tenía {n} dobles primos?", 3),
    ("¿Quiénes eran los dobles primos de {n}?", 3),
    ("¿Quién fue la doble prima de {n}?", 2),
    # --- sobrinos nietos (nieto del hermano) ---
    ("¿Quiénes eran los sobrinos nietos de {n}?", 3),
    ("¿Tenía {n} sobrinas nietas?", 2),
    # --- sobrinos segundos (hijo del primo) ---
    ("¿Quiénes eran los sobrinos segundos de {n}?", 3),
    ("¿Tenía {n} sobrinos segundos documentados?", 2),
    ("¿Quién fue la sobrina segunda de {n}?", 2),
    # --- sobrinos bisnietos (bisnieto del hermano) ---
    ("¿Tenía {n} sobrinos bisnietos?", 2),
    ("¿Quiénes eran los sobrinos bisnietos de {n}?", 2),
    # --- primos segundos (nieto del tío abuelo) ---
    ("¿Quiénes eran los primos segundos de {n}?", 3),
    ("¿Tenía {n} primas segundas?", 2),
    # --- primos terceros / cuartos ---
    ("¿Quiénes eran los primos terceros de {n}?", 3),
    ("¿Tenía {n} primos terceros documentados?", 2),
    ("¿Quién fue el primo cuarto de {n}?", 2),
    # --- medios primos / medios tíos ---
    ("¿Tenía {n} medios primos?", 3),
    ("¿Quiénes eran los medios tíos de {n}?", 2),
    ("¿Quién fue el medio tío de {n}?", 2),
    # --- tíos políticos (tío del cónyuge o cónyuge del tío) ---
    ("¿Quiénes eran los tíos políticos de {n}?", 3),
    ("¿Tenía {n} tías políticas?", 2),
    ("¿Quién fue el tío político de {n}?", 2),
    # --- primos políticos ---
    ("¿Quiénes eran los primos políticos de {n}?", 3),
    ("¿Tenía {n} primas políticas?", 2),
    # --- consuegros ---
    ("¿Quiénes eran los consuegros de {n}?", 3),
    ("¿Tenía {n} consuegros documentados?", 2),
    # --- cuñados / cuñadas ---
    ("¿Quiénes eran los cuñados de {n}?", 2),
    ("¿Quién fue la cuñada de {n}?", 2),
    # --- medios cuñados ---
    ("¿Tenía {n} medios cuñados?", 2),
    ("¿Quién fue el medio cuñado de {n}?", 2),
    # --- yernos / nueras / suegros ---
    ("¿Quiénes eran los yernos de {n}?", 2),
    ("¿Quién fue la nuera de {n}?", 2),
    ("¿Quiénes eran los suegros de {n}?", 2),
    # --- bisabuelos / tatarabuelos ---
    ("¿Quiénes eran los tíos tatarabuelos de {n}?", 2),
    ("¿Quiénes eran los tatarabuelos de {n}?", 2),
    # --- sobrinos tataranietos / contío (muy raros) ---
    ("¿Tenía {n} sobrinos tataranietos?", 2),
    ("¿Quién fue el contío de {n}?", 2),
]


def build():
    # Round-robin sobre las plantillas, rotando el roster, hasta 200 distintas.
    qs, used = [], set()
    rounds = 0
    while len(qs) < 200:
        for ti, (tpl, _k) in enumerate(TEMPLATES):
            cand = tpl.format(n=R[(ti + rounds) % len(R)])
            if cand not in used:
                used.add(cand)
                qs.append(cand)
                if len(qs) == 200:
                    return qs
        rounds += 1
    return qs


QUESTIONS = build()


def main():
    assert len(QUESTIONS) == 200, f"esperaba 200, hay {len(QUESTIONS)}"
    conn = database.get_connection(str(BASE / "data" / "godesia.db"))
    router = QueryRouter(conn)
    fails = []
    for i, q in enumerate(QUESTIONS, 1):
        plain = re.sub(r"<[^>]+>", "", router.route(q).get("answer", "") or "")
        if plain.startswith("No he sabido responder"):
            fails.append((i, q))
    print(f"Resueltas: {200 - len(fails)}/200  ·  No entendidas: {len(fails)}")
    from collections import Counter
    cat = Counter()
    for _, q in fails:
        ql = q.lower()
        key = next((w for w in ["concuñad", "medio", "media", "hermanastr", "tío abuelo", "tios abuelo",
                                 "tío bisabuelo", "tios bisabuelo", "doble prim", "sobrin", "primo segund",
                                 "prima segund", "primo tercer", "primo cuart", "tío polít", "tios polít",
                                 "prima polít", "primo polít", "consuegr", "cuñad", "yerno", "nuera",
                                 "suegr", "tatarab", "contío"] if w in ql), "otro")
        cat[key] += 1
    print("Fallan por categoría:", dict(cat))
    for i, q in fails:
        print(f"  ❌ #{i}: {q}")
    return fails


if __name__ == "__main__":
    main()
