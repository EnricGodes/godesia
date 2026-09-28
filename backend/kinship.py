"""Parentesco entre dos personas del árbol, redactado desde quien mira.

`kinship_label(conn, viewer_id, target_id, lang)` devuelve cómo se llama TARGET
respecto a VIEWER ("Su hijo", "Su prima segunda", "Su cuñada"…) o None si no
hay parentesco razonable. Lo usa el dossier para el usuario registrado que el
admin ha asociado a una persona del árbol.

Consanguinidad: antepasado común más cercano; m = generaciones de VIEWER hasta
él, n = generaciones de TARGET. Afinidad: parientes del cónyuge, cónyuges de
parientes y consuegros.
"""
from collections import deque

MAX_UP = 12          # generaciones que se remontan buscando antepasado común
MAX_AFFINE = 4       # m+n máximo para dar nombre a un parentesco político


# ── Grafo ────────────────────────────────────────────────────────────────────

def _load_graph(conn):
    parents, sex, spouses, partners = {}, {}, {}, {}
    for r in conn.execute("SELECT id, sex, father_id, mother_id FROM people"):
        sex[r[0]] = r[1]
        ps = parents.setdefault(r[0], set())
        for p in (r[2], r[3]):
            if p:
                ps.add(p)
    for r in conn.execute("SELECT parent_id, child_id FROM children"):
        if r[0] and r[1]:
            parents.setdefault(r[1], set()).add(r[0])
    for table, dest in (("marriages", spouses), ("partnerships", partners)):
        try:
            rows = conn.execute(f"SELECT person1_id, person2_id FROM {table}").fetchall()
        except Exception:
            rows = []
        for a, b in rows:
            if a and b:
                dest.setdefault(a, set()).add(b)
                dest.setdefault(b, set()).add(a)
    children = {}
    for c, ps in parents.items():
        for p in ps:
            children.setdefault(p, set()).add(c)
    return {"parents": parents, "children": children, "sex": sex,
            "spouses": spouses, "partners": partners}


def _ancestors(g, pid):
    """{antepasado: generaciones} incluyendo a la propia persona (0)."""
    out = {pid: 0}
    q = deque([pid])
    while q:
        x = q.popleft()
        d = out[x]
        if d >= MAX_UP:
            continue
        for p in g["parents"].get(x, ()):
            if p not in out:
                out[p] = d + 1
                q.append(p)
    return out


def _blood(g, a, b):
    """(m, n, half) del antepasado común más cercano, o None."""
    if a == b:
        return (0, 0, False)
    anc_a, anc_b = _ancestors(g, a), _ancestors(g, b)
    best = None
    for c in anc_a.keys() & anc_b.keys():
        m, n = anc_a[c], anc_b[c]
        if best is None or m + n < best[0] + best[1]:
            best = (m, n)
    if best is None:
        return None
    m, n = best
    half = False
    if m == 1 and n == 1:
        pa, pb = g["parents"].get(a, set()), g["parents"].get(b, set())
        half = len(pa) == 2 and len(pb) == 2 and pa != pb
    return (m, n, half)


def _blood_kind(m, n, half=False):
    """Relación consanguínea como (clave, params)."""
    if m == 0 and n == 0:
        return ("self", {})
    if m == 0:
        return ("child", {"g": n})
    if n == 0:
        return ("parent", {"g": m})
    if m == 1 and n == 1:
        return ("sibling", {"half": half})
    if m == 1:
        return ("nephew", {"g": n - 1})
    if n == 1:
        return ("uncle", {"g": m - 1})
    if m == n:
        return ("cousin", {"k": m - 1})
    lo, d = min(m, n), abs(m - n)
    if d > 2:
        return ("distant", {})
    return ("cousin_down" if n > m else "cousin_up", {"ord": lo, "d": d})


# ── Resolución ───────────────────────────────────────────────────────────────

def kinship(conn, viewer_id, target_id):
    """(clave, params) de TARGET visto desde VIEWER, o None."""
    g = _load_graph(conn)
    if viewer_id not in g["sex"] or target_id not in g["sex"]:
        return None
    if viewer_id == target_id:
        return ("self", {})
    if target_id in g["spouses"].get(viewer_id, ()):
        return ("spouse", {})
    if target_id in g["partners"].get(viewer_id, ()):
        return ("partner", {})

    b = _blood(g, viewer_id, target_id)
    if b:
        m, n, half = b
        if m + n > 2 * MAX_UP:
            return ("distant", {})
        return _blood_kind(m, n, half)

    # Afinidad: nos quedamos con la más cercana (menor m+n)
    cands = []
    my_spouses = g["spouses"].get(viewer_id, set()) | g["partners"].get(viewer_id, set())
    for s in my_spouses:                      # parientes de mi cónyuge
        bb = _blood(g, s, target_id)
        if not bb:
            continue
        m, n, half = bb
        if (m, n) == (1, 0):
            cands.append((1, ("parent_in_law", {})))
        elif (m, n) == (1, 1):
            cands.append((2, ("sibling_in_law", {})))
        elif (m, n) == (0, 1):
            cands.append((1, ("stepchild", {})))
        elif m + n <= MAX_AFFINE:
            cands.append((m + n, ("affine", {"base": _blood_kind(m, n, half)})))
    t_spouses = g["spouses"].get(target_id, set()) | g["partners"].get(target_id, set())
    for t in t_spouses:                       # cónyuges de mis parientes
        bb = _blood(g, viewer_id, t)
        if not bb:
            continue
        m, n, half = bb
        if (m, n) == (1, 0):
            cands.append((1, ("stepparent", {})))
        elif (m, n) == (0, 1):
            cands.append((1, ("child_in_law", {})))
        elif (m, n) == (1, 1):
            cands.append((2, ("sibling_in_law", {})))
        elif m + n <= MAX_AFFINE:
            cands.append((m + n, ("affine", {"base": _blood_kind(m, n, half)})))
    # Consuegros: el hijo de TARGET está casado con un hijo mío
    my_children = g["children"].get(viewer_id, set())
    for c in g["children"].get(target_id, ()):
        cs = g["spouses"].get(c, set()) | g["partners"].get(c, set())
        if cs & my_children:
            cands.append((2, ("co_parent_in_law", {})))
    if not cands:
        return None
    cands.sort(key=lambda x: x[0])
    return cands[0][1]


# ── Redacción por idioma ─────────────────────────────────────────────────────
# Cada entrada: (masculino, femenino). El sexo desconocido usa el masculino.

_ES_ORD_M = {2: "segundo", 3: "tercero", 4: "cuarto", 5: "quinto", 6: "sexto"}
_ES_ORD_F = {2: "segunda", 3: "tercera", 4: "cuarta", 5: "quinta", 6: "sexta"}
_CA_ORD_M = {2: "segon", 3: "tercer", 4: "quart", 5: "cinquè", 6: "sisè"}
_CA_ORD_F = {2: "segona", 3: "tercera", 4: "quarta", 5: "cinquena", 6: "sisena"}
_EN_ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth"}
_EN_TIMES = {1: "once", 2: "twice"}


def _es(key, p):
    if key == "parent":
        t = {1: ("padre", "madre"), 2: ("abuelo", "abuela"), 3: ("bisabuelo", "bisabuela"),
             4: ("tatarabuelo", "tatarabuela"), 5: ("trastatarabuelo", "trastatarabuela")}
        return t.get(p["g"]) or (f"antepasado ({p['g']} generaciones)", f"antepasada ({p['g']} generaciones)")
    if key == "child":
        t = {1: ("hijo", "hija"), 2: ("nieto", "nieta"), 3: ("bisnieto", "bisnieta"),
             4: ("tataranieto", "tataranieta"), 5: ("trastataranieto", "trastataranieta")}
        return t.get(p["g"]) or (f"descendiente ({p['g']} generaciones)",) * 2
    if key == "sibling":
        return ("medio hermano", "media hermana") if p["half"] else ("hermano", "hermana")
    if key == "uncle":
        t = {1: ("tío", "tía"), 2: ("tío abuelo", "tía abuela"), 3: ("tío bisabuelo", "tía bisabuela")}
        return t.get(p["g"]) or ("pariente lejano", "pariente lejana")
    if key == "nephew":
        t = {1: ("sobrino", "sobrina"), 2: ("sobrino nieto", "sobrina nieta"),
             3: ("sobrino bisnieto", "sobrina bisnieta")}
        return t.get(p["g"]) or ("pariente lejano", "pariente lejana")
    if key == "cousin":
        k = p["k"]
        if k == 1:
            return ("primo hermano", "prima hermana")
        if k in _ES_ORD_M:
            return (f"primo {_ES_ORD_M[k]}", f"prima {_ES_ORD_F[k]}")
        return ("pariente lejano", "pariente lejana")
    if key in ("cousin_up", "cousin_down"):
        o = p["ord"]
        if o not in _ES_ORD_M:
            return ("pariente lejano", "pariente lejana")
        if key == "cousin_up":
            base = ("tío", "tía") if p["d"] == 1 else ("tío abuelo", "tía abuela")
        else:
            base = ("sobrino", "sobrina") if p["d"] == 1 else ("sobrino nieto", "sobrina nieta")
        return (f"{base[0]} {_ES_ORD_M[o]}", f"{base[1]} {_ES_ORD_F[o]}")
    return {
        "distant": ("pariente lejano", "pariente lejana"),
        "spouse": ("esposo", "esposa"),
        "partner": ("pareja", "pareja"),
        "parent_in_law": ("suegro", "suegra"),
        "sibling_in_law": ("cuñado", "cuñada"),
        "child_in_law": ("yerno", "nuera"),
        "stepchild": ("hijastro", "hijastra"),
        "stepparent": ("padrastro", "madrastra"),
        "co_parent_in_law": ("consuegro", "consuegra"),
    }[key]


def _ca(key, p):
    if key == "parent":
        t = {1: ("pare", "mare"), 2: ("avi", "àvia"), 3: ("besavi", "besàvia"), 4: ("rebesavi", "rebesàvia"),
             5: ("quadravi", "quadràvia")}
        return t.get(p["g"]) or (f"avantpassat ({p['g']} generacions)", f"avantpassada ({p['g']} generacions)")
    if key == "child":
        t = {1: ("fill", "filla"), 2: ("nét", "néta"), 3: ("besnét", "besnéta"), 4: ("rebesnét", "rebesnéta"),
             5: ("quadrinét", "quadrinéta")}
        return t.get(p["g"]) or (f"descendent ({p['g']} generacions)",) * 2
    if key == "sibling":
        return ("mig germà", "mitja germana") if p["half"] else ("germà", "germana")
    if key == "uncle":
        t = {1: ("oncle", "tia"), 2: ("besoncle", "bestia"), 3: ("rebesoncle", "rebestia")}
        return t.get(p["g"]) or ("parent llunyà", "parenta llunyana")
    if key == "nephew":
        t = {1: ("nebot", "neboda"), 2: ("renebot", "reneboda"), 3: ("besnebot", "besneboda")}
        return t.get(p["g"]) or ("parent llunyà", "parenta llunyana")
    if key == "cousin":
        k = p["k"]
        if k == 1:
            return ("cosí germà", "cosina germana")
        if k in _CA_ORD_M:
            return (f"cosí {_CA_ORD_M[k]}", f"cosina {_CA_ORD_F[k]}")
        return ("parent llunyà", "parenta llunyana")
    if key in ("cousin_up", "cousin_down"):
        o = p["ord"]
        if o not in _CA_ORD_M:
            return ("parent llunyà", "parenta llunyana")
        if key == "cousin_up":
            base = ("oncle", "tia") if p["d"] == 1 else ("besoncle", "bestia")
        else:
            base = ("nebot", "neboda") if p["d"] == 1 else ("renebot", "reneboda")
        return (f"{base[0]} {_CA_ORD_M[o]}", f"{base[1]} {_CA_ORD_F[o]}")
    return {
        "distant": ("parent llunyà", "parenta llunyana"),
        "spouse": ("espòs", "esposa"),
        "partner": ("parella", "parella"),
        "parent_in_law": ("sogre", "sogra"),
        "sibling_in_law": ("cunyat", "cunyada"),
        "child_in_law": ("gendre", "nora"),
        "stepchild": ("fillastre", "fillastra"),
        "stepparent": ("padrastre", "madrastra"),
        "co_parent_in_law": ("consogre", "consogra"),
    }[key]


def _en(key, p):
    if key == "parent":
        g = p["g"]
        if g == 1:
            return ("father", "mother")
        pre = "great-" * (g - 2)
        return (f"{pre}grandfather", f"{pre}grandmother")
    if key == "child":
        g = p["g"]
        if g == 1:
            return ("son", "daughter")
        pre = "great-" * (g - 2)
        return (f"{pre}grandson", f"{pre}granddaughter")
    if key == "sibling":
        return ("half-brother", "half-sister") if p["half"] else ("brother", "sister")
    if key == "uncle":
        pre = "great-" * (p["g"] - 1)
        return (f"{pre}uncle", f"{pre}aunt")
    if key == "nephew":
        pre = "great-" * (p["g"] - 1)
        return (f"{pre}nephew", f"{pre}niece")
    if key == "cousin":
        o = _EN_ORD.get(p["k"])
        return (f"{o} cousin",) * 2 if o else ("distant relative",) * 2
    if key in ("cousin_up", "cousin_down"):
        o = _EN_ORD.get(p["ord"] - 1)
        if not o:
            return ("distant relative",) * 2
        return (f"{o} cousin {_EN_TIMES[p['d']]} removed",) * 2
    return {
        "distant": ("distant relative", "distant relative"),
        "spouse": ("husband", "wife"),
        "partner": ("partner", "partner"),
        "parent_in_law": ("father-in-law", "mother-in-law"),
        "sibling_in_law": ("brother-in-law", "sister-in-law"),
        "child_in_law": ("son-in-law", "daughter-in-law"),
        "stepchild": ("stepson", "stepdaughter"),
        "stepparent": ("stepfather", "stepmother"),
        "co_parent_in_law": ("child's father-in-law", "child's mother-in-law"),
    }[key]


def _fr(key, p):
    if key == "parent":
        g = p["g"]
        if g == 1:
            return ("père", "mère")
        pre = "arrière-" * (g - 2)
        return (f"{pre}grand-père", f"{pre}grand-mère")
    if key == "child":
        g = p["g"]
        if g == 1:
            return ("fils", "fille")
        pre = "arrière-" * (g - 2)
        return (f"{pre}petit-fils", f"{pre}petite-fille")
    if key == "sibling":
        return ("demi-frère", "demi-sœur") if p["half"] else ("frère", "sœur")
    if key == "uncle":
        g = p["g"]
        if g == 1:
            return ("oncle", "tante")
        pre = "arrière-" * (g - 2)
        return (f"{pre}grand-oncle", f"{pre}grand-tante")
    if key == "nephew":
        g = p["g"]
        if g == 1:
            return ("neveu", "nièce")
        pre = "arrière-" * (g - 2)
        return (f"{pre}petit-neveu", f"{pre}petite-nièce")
    if key == "cousin":
        return {1: ("cousin germain", "cousine germaine"),
                2: ("cousin issu de germain", "cousine issue de germain")}.get(
            p["k"], ("cousin éloigné", "cousine éloignée"))
    if key in ("cousin_up", "cousin_down"):
        if p["ord"] == 2 and p["d"] == 1:
            base = ("oncle", "tante") if key == "cousin_up" else ("neveu", "nièce")
            return tuple(f"{b} à la mode de Bretagne" for b in base)
        return ("cousin éloigné", "cousine éloignée")
    return {
        "distant": ("parent éloigné", "parente éloignée"),
        "spouse": ("mari", "épouse"),
        "partner": ("compagnon", "compagne"),
        "parent_in_law": ("beau-père", "belle-mère"),
        "sibling_in_law": ("beau-frère", "belle-sœur"),
        "child_in_law": ("gendre", "belle-fille"),
        "stepchild": ("beau-fils", "belle-fille"),
        "stepparent": ("beau-père", "belle-mère"),
    }[key]


def _de(key, p):
    if key == "parent":
        g = p["g"]
        if g == 1:
            return ("Vater", "Mutter")
        pre = "Ur" * (g - 2)
        return ((f"{pre}großvater" if pre else "Großvater").capitalize(),
                (f"{pre}großmutter" if pre else "Großmutter").capitalize())
    if key == "child":
        g = p["g"]
        if g == 1:
            return ("Sohn", "Tochter")
        pre = "Ur" * (g - 2)
        return ((f"{pre}enkel" if pre else "Enkel").capitalize(),
                (f"{pre}enkelin" if pre else "Enkelin").capitalize())
    if key == "sibling":
        return ("Halbbruder", "Halbschwester") if p["half"] else ("Bruder", "Schwester")
    if key == "uncle":
        t = {1: ("Onkel", "Tante"), 2: ("Großonkel", "Großtante"), 3: ("Urgroßonkel", "Urgroßtante")}
        return t.get(p["g"]) or ("entfernter Verwandter", "entfernte Verwandte")
    if key == "nephew":
        t = {1: ("Neffe", "Nichte"), 2: ("Großneffe", "Großnichte"), 3: ("Urgroßneffe", "Urgroßnichte")}
        return t.get(p["g"]) or ("entfernter Verwandter", "entfernte Verwandte")
    if key == "cousin":
        k = p["k"]
        return ("Cousin", "Cousine") if k == 1 else (f"Cousin {k}. Grades", f"Cousine {k}. Grades")
    if key in ("cousin_up", "cousin_down"):
        o = p["ord"]
        if key == "cousin_up":
            base = ("Onkel", "Tante") if p["d"] == 1 else ("Großonkel", "Großtante")
        else:
            base = ("Neffe", "Nichte") if p["d"] == 1 else ("Großneffe", "Großnichte")
        return (f"{base[0]} {o}. Grades", f"{base[1]} {o}. Grades")
    return {
        "distant": ("entfernter Verwandter", "entfernte Verwandte"),
        "spouse": ("Ehemann", "Ehefrau"),
        "partner": ("Partner", "Partnerin"),
        "parent_in_law": ("Schwiegervater", "Schwiegermutter"),
        "sibling_in_law": ("Schwager", "Schwägerin"),
        "child_in_law": ("Schwiegersohn", "Schwiegertochter"),
        "stepchild": ("Stiefsohn", "Stieftochter"),
        "stepparent": ("Stiefvater", "Stiefmutter"),
    }[key]


_NOUNS = {"es": _es, "ca": _ca, "en": _en, "fr": _fr, "de": _de}

_SELF = {
    "es": "Esta es su ficha",
    "ca": "Aquesta és la seva fitxa",
    "en": "This is your profile",
    "fr": "C'est votre fiche",
    "de": "Das ist Ihr Profil",
}


def _phrase(lang, key, params, female):
    """Frase completa ("Su hijo") para una relación."""
    if key == "co_parent_in_law" and lang in ("fr", "de"):
        return {
            "fr": ("Le beau-père de votre enfant", "La belle-mère de votre enfant"),
            "de": ("Der Schwiegervater Ihres Kindes", "Die Schwiegermutter Ihres Kindes"),
        }[lang][female]
    def nouns(k, p):
        if k in ("ancestor", "descendant"):
            pair = _GENERIC[lang][0 if k == "ancestor" else 1]
            return tuple(x.format(g=p["g"]) for x in pair)
        return _NOUNS[lang](k, p)
    if key == "affine":
        bk, bp = params["base"]
        noun = nouns(bk, bp)[female]
        if lang == "es":
            noun += " política" if female else " político"
        elif lang == "ca":
            noun += " política" if female else " polític"
        elif lang == "en":
            noun += " by marriage"
        elif lang == "fr":
            noun += " par alliance"
        elif lang == "de":
            noun = ("angeheiratete " if female else "angeheirateter ") + noun
    else:
        noun = nouns(key, params)[female]
    if lang == "es":
        return f"Su {noun}"
    if lang == "ca":
        fem_noun = female or noun.startswith("parella")
        return f"{'La seva' if fem_noun else 'El seu'} {noun}"
    if lang == "en":
        return f"Your {noun}"
    if lang == "fr":
        return f"Votre {noun}"
    if lang == "de":
        return f"{'Ihre' if female else 'Ihr'} {noun}"
    return noun


_GENERIC = {
    "es": (("antepasado ({g} generaciones)", "antepasada ({g} generaciones)"),
           ("descendiente ({g} generaciones)", "descendiente ({g} generaciones)")),
    "ca": (("avantpassat ({g} generacions)", "avantpassada ({g} generacions)"),
           ("descendent ({g} generacions)", "descendent ({g} generacions)")),
    "en": (("ancestor ({g} generations back)",) * 2, ("descendant ({g} generations)",) * 2),
    "fr": (("ancêtre ({g} générations)",) * 2, ("descendant ({g} générations)", "descendante ({g} générations)")),
    "de": (("Vorfahr ({g} Generationen)", "Vorfahrin ({g} Generationen)"),
           ("Nachkomme ({g} Generationen)", "Nachkomme ({g} Generationen)")),
}


def _simplify(rel):
    """Cadenas demasiado largas → forma genérica."""
    key, p = rel
    if key in ("parent", "child") and p["g"] > 5:
        return ("ancestor" if key == "parent" else "descendant", p)
    if key in ("uncle", "nephew") and p["g"] > 3:
        return ("distant", {})
    if key == "affine":
        return ("affine", {"base": _simplify(p["base"])})
    return rel


def kinship_label(conn, viewer_id, target_id, lang="es"):
    """Texto del parentesco de TARGET visto desde VIEWER, o None."""
    rel = kinship(conn, viewer_id, target_id)
    if not rel:
        return None
    rel = _simplify(rel)
    lang = lang if lang in _NOUNS else "es"
    key, params = rel
    if key == "self":
        return _SELF[lang]
    sex = conn.execute("SELECT sex FROM people WHERE id = ?", (target_id,)).fetchone()
    female = 1 if (sex and sex[0] == "F") else 0
    return _phrase(lang, key, params, female)
